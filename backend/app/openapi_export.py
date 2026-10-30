"""Writes or checks the committed copy of the API contract, `docs/openapi.json`.

    python -m app.openapi_export --write    # after changing an endpoint or a schema
    python -m app.openapi_export --check    # CI: fails when the committed file is out of date

The file lets clients (the mobile app, tests, tools) read the contract without running the
server, and a CI check keeps it from drifting. Output is deterministic: sorted keys, two-space
indent, a fixed version string, a final newline. The command needs no database and no secrets.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FILE = REPO_ROOT / "docs" / "openapi.json"
# The real build version would make the file change with every release.
EXPORT_VERSION = "dev"

# Non-secret settings the application needs in order to start. Used only when the command runs
# without a configured environment; real values are never overridden.
_STARTUP_DEFAULTS = {
    "ENVIRONMENT": "ci",
    "CORS_ORIGINS": "http://localhost:5173",
    "REPORT_TIMEZONE": "UTC",
    "REPORTS_OUTPUT_DIR": "reports_output",
    "FRONTEND_BASE_URL": "http://localhost:5173",
    "ACCESS_TOKEN_MINUTES": "15",
    "REFRESH_TOKEN_DAYS": "30",
    "RESET_TOKEN_MINUTES": "60",
    "LOGIN_MAX_FAILURES": "5",
    "LOGIN_WINDOW_MINUTES": "15",
}


def build_schema() -> dict[str, Any]:
    from app.main import app

    schema: dict[str, Any] = json.loads(json.dumps(app.openapi()))
    schema["info"]["version"] = EXPORT_VERSION
    return schema


def render() -> str:
    return json.dumps(build_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write the file")
    mode.add_argument("--check", action="store_true", help="fail if the file is out of date")
    parser.add_argument(
        "--file", type=Path, default=DEFAULT_FILE, help="default: docs/openapi.json"
    )
    args = parser.parse_args(argv)

    for name, value in _STARTUP_DEFAULTS.items():
        os.environ.setdefault(name, value)
    expected = render()
    if args.write:
        args.file.parent.mkdir(parents=True, exist_ok=True)
        args.file.write_text(expected, encoding="utf-8")
        print(f"Wrote {args.file}")
        return 0
    current = args.file.read_text(encoding="utf-8") if args.file.exists() else None
    if current == expected:
        print("docs/openapi.json is up to date.")
        return 0
    print(
        "docs/openapi.json is missing or out of date with the API.\n"
        "Run: make openapi   (or: cd backend && uv run python -m app.openapi_export --write)\n"
        "and commit the result.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
