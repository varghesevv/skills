#!/usr/bin/env python3
"""Fails when a workflow that starts on `pull_request` has a job without the fork guard.

The guard keeps pull requests from forks away from our runners and secrets (see the
"Pull requests from forks" section of docs/operations-runbook.md). Standard library only.
Also fails on `pull_request_target`, which would run with secrets for fork code.
"""

import re
import sys
from pathlib import Path

GUARD = "github.event.pull_request.head.repo.full_name == github.repository"


def jobs_of(lines: list[str]) -> dict[str, str]:
    """Job name -> its text, for the 2-space-indented keys under `jobs:`."""
    try:
        start = lines.index("jobs:") + 1
    except ValueError:
        return {}
    jobs: dict[str, list[str]] = {}
    current = None
    for line in lines[start:]:
        if line and not line.startswith((" ", "#")):
            break
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            current = match.group(1)
            jobs[current] = []
        elif current:
            jobs[current].append(line)
    return {name: "\n".join(body) for name, body in jobs.items()}


def main(root: str) -> int:
    problems: list[str] = []
    checked = 0
    for path in sorted(Path(root, ".github", "workflows").glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        header = "\n".join(lines[: lines.index("jobs:")]) if "jobs:" in lines else text
        if re.search(r"(?m)^\s*pull_request_target\s*:", header):
            problems.append(f"{path.name}: uses pull_request_target (not allowed)")
        if not re.search(r"(?m)^\s*pull_request\s*:", header):
            continue
        for name, body in jobs_of(lines).items():
            checked += 1
            if not re.search(r"(?m)^    if:", body) or GUARD not in body:
                problems.append(f"{path.name}: job '{name}' has no fork guard")
    for p in problems:
        print(f"FORK GUARD CHECK FAILED  {p}")
    if problems:
        print("\nAdd to the job:  if: github.event_name != 'pull_request' || " + GUARD)
        return 1
    print(f"Fork guard check passed ({checked} jobs).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
