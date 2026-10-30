#!/usr/bin/env python3
"""Adds an APK to the downloads folder the API serves (GET /api/v1/app/downloads).

    python3 scripts/add-download.py --dir /opt/skills/data/downloads --apk app.apk \
        --version 1.2.0 --build 17 [--notes-file notes.md] [--keep 10]

Layout written (see backend/app/services/downloads.py, which reads it):
    <dir>/android/<version>/skills-demo-<version>.apk
    <dir>/index.json        {"android": [{version, build, released_at, size_bytes, sha256, notes, file}]}

Publishing a version again replaces it. Versions beyond the newest --keep are removed. Files are
written to a temporary name and renamed, so the API never sees a half-written file or index.
Only debug-free, signed release builds belong here; the script cannot tell, the caller must.
Prints the version, size and SHA-256 only. Standard library only.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

VERSION_RE = re.compile(r"^\d{1,5}\.\d{1,5}\.\d{1,5}$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}\.apk$")
MAX_NOTES = 4000


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def make_dir(path: Path) -> None:
    """Creates a folder (and any missing parents) that the API container, another user, can
    enter, whatever the umask is. Folders that already exist are left as they are."""
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for folder in reversed(missing):
        folder.mkdir()
        os.chmod(folder, 0o755)


def write_atomic(path: Path, data: bytes) -> None:
    make_dir(path.parent)
    handle = tempfile.NamedTemporaryFile(dir=path.parent, delete=False)
    temp = Path(handle.name)
    try:
        with handle:
            handle.write(data)
        temp.chmod(0o644)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)  # nothing is left behind when a step fails


def copy_atomic(source: Path, path: Path) -> None:
    make_dir(path.parent)
    handle = tempfile.NamedTemporaryFile(dir=path.parent, delete=False)
    temp = Path(handle.name)
    handle.close()
    try:
        shutil.copyfile(source, temp)
        temp.chmod(0o644)  # the API runs as another user and must be able to read it
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def load_index(index_path: Path) -> dict:
    """The existing index, checked for the shape this script and the API rely on.

    Raises ValueError (before anything is copied) when it is not usable, so a damaged index never
    leaves a half-published build behind."""
    if not index_path.is_file():
        return {}
    try:
        index = json.loads(index_path.read_text("utf-8"))
    except (OSError, ValueError):
        raise ValueError("index.json is not valid JSON; fix or remove it first") from None
    entries = index.get("android", []) if isinstance(index, dict) else None
    if not isinstance(entries, list):
        raise ValueError("index.json has an unexpected shape; fix or remove it first")
    for entry in entries:
        if not (
            isinstance(entry, dict)
            and isinstance(entry.get("version"), str)
            and VERSION_RE.fullmatch(entry["version"])
            and isinstance(entry.get("build"), int)
        ):
            raise ValueError("index.json has an invalid entry; fix or remove it first")
    return index


def add_download(
    folder: Path,
    apk: Path,
    *,
    version: str,
    build: int,
    notes: str = "",
    name: str | None = None,
    released_at: datetime | None = None,
    keep: int = 10,
) -> dict[str, object]:
    if not VERSION_RE.fullmatch(version):
        raise ValueError("version must look like 1.2.3")
    name = name or f"skills-demo-{version}.apk"
    if not NAME_RE.fullmatch(name):
        raise ValueError("file name may use letters, digits, . _ - and must end in .apk")
    if build < 1:
        raise ValueError("build must be 1 or more")
    if keep < 1:
        raise ValueError("keep must be 1 or more")
    if len(notes) > MAX_NOTES:
        raise ValueError(f"notes are limited to {MAX_NOTES} characters")
    if not apk.is_file():
        raise ValueError("the APK file does not exist")

    index_path = folder / "index.json"
    index = load_index(index_path)  # before anything is written

    target = folder / "android" / version / name
    copy_atomic(apk, target)

    entry: dict[str, object] = {
        "version": version,
        "build": build,
        "released_at": (released_at or datetime.now(UTC)).isoformat(),
        "size_bytes": target.stat().st_size,
        "sha256": sha256_of(target),
        "notes": notes,
        "file": name,
    }
    entries = [e for e in index.get("android", []) if e.get("version") != version]
    entries.append(entry)
    entries.sort(key=lambda e: (version_key(e["version"]), e["build"]), reverse=True)
    index["android"] = entries[:keep]
    # The index goes first: if it cannot be written, no build has been deleted yet.
    write_atomic(index_path, (json.dumps(index, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    android = (folder / "android").resolve()
    for old in entries[keep:]:
        # Versions were checked in load_index; the path must also stay inside the android folder.
        doomed = (android / old["version"]).resolve()
        if doomed.parent == android:
            shutil.rmtree(doomed, ignore_errors=True)
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, required=True, help="the downloads folder")
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--version", required=True, help="X.Y.Z")
    parser.add_argument("--build", type=int, required=True)
    parser.add_argument("--notes-file", type=Path, help="release notes, plain text or Markdown")
    parser.add_argument("--name", help="file name (default skills-demo-<version>.apk)")
    parser.add_argument("--keep", type=int, default=10, help="newest versions to keep")
    args = parser.parse_args(argv)
    try:
        notes = args.notes_file.read_text("utf-8").strip() if args.notes_file else ""
        entry = add_download(
            args.dir,
            args.apk,
            version=args.version,
            build=args.build,
            notes=notes,
            name=args.name,
            keep=args.keep,
        )
    except (ValueError, OSError) as error:
        print(f"add-download: {error}", file=sys.stderr)
        return 1
    print(f"Published {entry['version']} (build {entry['build']}), {entry['size_bytes']} bytes")
    print(f"SHA-256 {entry['sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
