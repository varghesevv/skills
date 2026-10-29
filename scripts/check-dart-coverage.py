#!/usr/bin/env python3
"""Fails when line coverage of lib/ in an lcov file is below a floor (percent).

Usage: check-dart-coverage.py <lcov.info> <floor>. Generated files are ignored.
Standard library only.
"""

import sys

GENERATED = (".g.dart", ".freezed.dart", "/generated/", "/l10n/app_localizations")


def coverage(lcov_text: str) -> float:
    found = hit = 0
    current: str | None = None
    for line in lcov_text.splitlines():
        if line.startswith("SF:"):
            current = line[3:]
        elif line.startswith("DA:") and current and not any(g in current for g in GENERATED):
            found += 1
            hit += 1 if int(line[3:].split(",")[1]) > 0 else 0
    return 100.0 if found == 0 else 100.0 * hit / found


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as handle:
        percent = coverage(handle.read())
    floor = float(argv[2])
    print(f"Line coverage of lib/: {percent:.1f}% (floor {floor:.0f}%)")
    return 0 if percent >= floor else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
