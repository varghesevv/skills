#!/usr/bin/env python3
"""Checks the relative links in the Markdown files: the target file or folder exists and, for a
link into a Markdown file, the #section exists. Web addresses are not visited (offline), which
is what the old lychee --offline check did. Standard library only, so it runs on any runner.

    python3 scripts/check-md-links.py [folder]
"""

import os
import re
import sys
from urllib.parse import unquote

SKIP_DIRS = {".git", "node_modules", ".venv", ".terraform", "dist", "__pycache__", ".pytest_cache"}
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
INLINE = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
REFERENCE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+.*)?$")
FENCE = re.compile(r"^\s{0,3}(```+|~~~+)")


def markdown_files(root):
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if name.lower().endswith(".md"):
                yield os.path.join(folder, name)


def read_lines(path):
    """The lines of a file with fenced code blocks emptied, so code is never read as links."""
    out = []
    fence = None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            match = FENCE.match(line)
            if match:
                marker = match.group(1)[0]
                if fence is None:
                    fence = marker
                elif fence == marker:
                    fence = None
                out.append("")
                continue
            out.append("" if fence else line.rstrip("\n"))
    return out


def plain_heading(text):
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links and images keep their text
    text = re.sub(r"<[^>]+>", "", text)  # html tags
    text = text.replace("`", "")
    text = re.sub(r"[*~]", "", text)
    return text.strip()


def slug(text):
    """GitHub's heading anchor: lower case, punctuation removed, spaces become hyphens."""
    text = plain_heading(text).lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


_anchor_cache = {}


def anchors(path):
    if path in _anchor_cache:
        return _anchor_cache[path]
    seen = {}
    found = set()
    for line in read_lines(path):
        match = re.match(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not match:
            continue
        base = slug(match.group(1))
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.add(base if count == 0 else "%s-%d" % (base, count))
    # explicit html anchors: <a id="x"> or <a name="x">
    with open(path, encoding="utf-8") as handle:
        for value in re.findall(r"<a\s+[^>]*(?:id|name)=[\"']([^\"']+)[\"']", handle.read()):
            found.add(value)
    _anchor_cache[path] = found
    return found


def targets(path):
    for number, line in enumerate(read_lines(path), start=1):
        line_no_code = re.sub(r"`[^`]*`", "", line)  # inline code is not a link
        for match in INLINE.finditer(line_no_code):
            yield number, match.group(1)
        match = REFERENCE.match(line_no_code)
        if match:
            yield number, match.group(1)


def check(root):
    problems = []
    root = os.path.abspath(root)
    for path in markdown_files(root):
        for number, target in targets(path):
            if SCHEME.match(target) or target.startswith("//"):
                continue  # web addresses, mailto: and similar are not visited
            location, _, fragment = target.partition("#")
            location = unquote(location.split("?", 1)[0])
            fragment = unquote(fragment)
            if location == "":
                destination = path
            elif location.startswith("/"):
                destination = os.path.join(root, location.lstrip("/"))
            else:
                destination = os.path.normpath(os.path.join(os.path.dirname(path), location))
            where = "%s:%d" % (os.path.relpath(path, root), number)
            if not os.path.exists(destination):
                problems.append("%s: missing file or folder: %s" % (where, target))
                continue
            if fragment and os.path.isfile(destination) and destination.lower().endswith(".md"):
                if fragment.lower() not in {a.lower() for a in anchors(destination)}:
                    problems.append("%s: no section '#%s' in %s" % (where, fragment, location or "this file"))
    return problems


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    problems = check(root)
    for problem in problems:
        print(problem)
    count = sum(1 for _ in markdown_files(root))
    if problems:
        print("\n%d broken link(s) in %d Markdown file(s)." % (len(problems), count))
        return 1
    print("All relative Markdown links are fine (%d files checked)." % count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
