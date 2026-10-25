#!/usr/bin/env python3
"""Fails when a workflow that starts on `pull_request` has a job without the fork guard.

The guard keeps pull requests from forks away from our runners and secrets (see the
"Pull requests from forks" section of docs/operations-runbook.md). Standard library only.

Rules, per workflow file under .github/workflows:
- `pull_request_target` as a trigger (any form) is an error.
- If `pull_request` is a trigger (any form of `on:`), every job needs a job-level `if:` that is
  FALSE for a pull request from a fork. The condition is evaluated for that case with the
  worst case for everything unknown: the guard is false, `github.event_name` is
  `pull_request`, and any other term (`always()`, `draft == false`, ...) may be true. So
  `always() || <guard>`, `!<guard>` or a missing `if:` fail, while `<guard> && x` and
  `event_name == 'push' || <guard>` pass.
- Every 2-space key under `jobs:` must be a plain job name (letters, digits, `_`, `-`), so no job
  can be hidden inside another one's text.
- A workflow whose triggers or jobs cannot be found is an error, never silently skipped.

This is a text check, not a YAML parser: it understands the layout used in this repository
(top-level keys at column 0, jobs at 2 spaces, job keys at 4 spaces).
"""

import re
import sys
from pathlib import Path

GUARD = "github.event.pull_request.head.repo.full_name == github.repository"
JOB_KEY = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
EVENT_TERM = re.compile(r"^github\.event_name\s*(==|!=)\s*'([^']*)'$")
TOP_KEY = re.compile(r"^[^\s#]")


def strip_comment(line: str) -> str:
    """Remove a trailing YAML comment (a # at the start or after whitespace)."""
    return re.sub(r"(^|\s)#.*$", "", line).rstrip()


def clean_lines(text: str) -> list[str]:
    return [strip_comment(line) for line in text.split("\n")]


def top_level_block(lines: list[str], key: str) -> list[str] | None:
    """Lines of a top-level key: the key line itself and the indented lines after it."""
    pattern = re.compile(rf"""^(?:"{key}"|'{key}'|{key})\s*:""")
    for i, line in enumerate(lines):
        if pattern.match(line):
            block = [line]
            for later in lines[i + 1:]:
                if later and TOP_KEY.match(later):
                    break
                block.append(later)
            return block
    return None


def split_jobs(jobs_block: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Returns (job name -> body lines, 2-space keys that are not plain job names)."""
    jobs: dict[str, list[str]] = {}
    odd: list[str] = []
    current = None
    for line in jobs_block[1:]:
        match = JOB_KEY.match(line)
        if match:
            current = match.group(1)
            jobs[current] = []
        elif re.match(r"^  \S", line):
            odd.append(line.strip())
            current = None
        elif current is not None:
            jobs[current].append(line)
    return jobs, odd


def runs_for_fork_pr(condition: str) -> bool | None:
    """Can this condition be true for a pull request from a fork? None when it cannot be read."""
    text = condition.strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    text = re.sub(r"[A-Za-z_]+\([^()]*\)", " __call__ ", text)  # always(), contains(a, b)
    tokens = [t.strip() for t in re.split(r"(\|\||&&|!(?!=)|\(|\))", text) if t.strip()]
    pos = 0

    def atom(term: str) -> bool:
        if term == GUARD:
            return False  # a fork pull request is not from this repository
        event = EVENT_TERM.match(term)
        if event:
            return (event.group(2) == "pull_request") == (event.group(1) == "==")
        return True  # unknown term: assume it can be true

    def parse_or() -> bool:
        nonlocal pos
        value = parse_and()
        while pos < len(tokens) and tokens[pos] == "||":
            pos += 1
            right = parse_and()
            value = value or right
        return value

    def parse_and() -> bool:
        nonlocal pos
        value = parse_not()
        while pos < len(tokens) and tokens[pos] == "&&":
            pos += 1
            right = parse_not()
            value = value and right
        return value

    def parse_not() -> bool:
        nonlocal pos
        if pos < len(tokens) and tokens[pos] == "!":
            pos += 1
            return not parse_not()
        return parse_primary()

    def parse_primary() -> bool:
        nonlocal pos
        if pos >= len(tokens):
            raise ValueError("unexpected end")
        token = tokens[pos]
        if token == "(":
            pos += 1
            value = parse_or()
            if pos >= len(tokens) or tokens[pos] != ")":
                raise ValueError("missing )")
            pos += 1
            return value
        if token in ("||", "&&", ")"):
            raise ValueError(f"unexpected {token}")
        pos += 1
        return atom(token)

    try:
        result = parse_or()
        if pos != len(tokens):
            return None
        return result
    except ValueError:
        return None


def job_if_value(body: list[str]) -> str | None:
    """The job-level `if:` value (4-space indent), joining folded or literal block scalars."""
    for i, line in enumerate(body):
        match = re.match(r"^    if:\s*(.*)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if value[:1] in (">", "|"):
            parts = []
            for later in body[i + 1:]:
                if later.strip() and len(later) - len(later.lstrip()) <= 4:
                    break
                parts.append(later.strip())
            value = " ".join(p for p in parts if p)
        return value
    return None


def check_file(name: str, text: str) -> tuple[list[str], int]:
    """Returns (problems, jobs checked)."""
    lines = clean_lines(text)
    on_block = top_level_block(lines, "on")
    if on_block is None:
        return [f"{name}: no `on:` section found"], 0
    triggers = "\n".join(on_block)
    problems = []
    if re.search(r"\bpull_request_target\b", triggers):
        problems.append(f"{name}: uses pull_request_target (not allowed)")
    if not re.search(r"\bpull_request\b", triggers):
        return problems, 0
    jobs_block = top_level_block(lines, "jobs")
    jobs, odd = split_jobs(jobs_block) if jobs_block else ({}, [])
    if not jobs and not odd:
        return problems + [f"{name}: starts on pull_request but no jobs were found"], 0
    for key in odd:
        problems.append(f"{name}: job key '{key}' is not a plain job name; rename it so it can be checked")
    for job, body in jobs.items():
        value = job_if_value(body)
        if value is None:
            problems.append(f"{name}: job '{job}' has no job-level `if:` (fork guard)")
            continue
        verdict = runs_for_fork_pr(value)
        if verdict is None:
            problems.append(f"{name}: job '{job}': cannot read the `if:` condition; keep it to ||, &&, !, ( )")
        elif verdict:
            problems.append(f"{name}: job '{job}': its `if:` can be true for a pull request from a fork")
    return problems, len(jobs)


def main(root: str) -> int:
    problems: list[str] = []
    checked = 0
    for path in sorted(Path(root, ".github", "workflows").glob("*.y*ml")):
        found, count = check_file(path.name, path.read_text(encoding="utf-8"))
        problems += found
        checked += count
    for p in problems:
        print(f"FORK GUARD CHECK FAILED  {p}")
    if problems:
        print("\nAdd to the job:  if: github.event_name != 'pull_request' || " + GUARD)
        return 1
    print(f"Fork guard check passed ({checked} jobs).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
