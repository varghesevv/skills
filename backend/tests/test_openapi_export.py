import json
from pathlib import Path

import pytest

from app.openapi_export import DEFAULT_FILE, EXPORT_VERSION, main, render


def test_committed_contract_matches_the_api() -> None:
    """Fails when an endpoint or schema changed without `make openapi`."""
    assert DEFAULT_FILE.exists(), "docs/openapi.json is missing: run `make openapi`"
    assert DEFAULT_FILE.read_text(encoding="utf-8") == render(), (
        "docs/openapi.json is out of date: run `make openapi` and commit it"
    )


def test_render_is_stable_and_readable() -> None:
    text = render()
    assert text == render()
    assert text.endswith("\n") and not text.endswith("\n\n")
    document = json.loads(text)
    assert document["info"]["version"] == EXPORT_VERSION
    assert document["info"]["title"] == "Skills API"
    assert json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n" == text


def test_contract_lists_the_endpoints_clients_use() -> None:
    paths = json.loads(render())["paths"]
    for path, method in [
        ("/api/v1/app/config", "get"),
        ("/api/v1/auth/login", "post"),
        ("/api/v1/auth/refresh", "post"),
        ("/api/v1/me", "get"),
        ("/api/v1/freelancers/{freelancer_id}/reveal-mobile", "post"),
    ]:
        assert method in paths[path], (path, method)


def test_contract_holds_no_secret_looking_values() -> None:
    text = render().lower()
    for word in ("jwt_secret", "database_url", "begin private key"):
        assert word not in text


def test_write_then_check(tmp_path: Path) -> None:
    target = tmp_path / "contract" / "openapi.json"
    assert main(["--check", "--file", str(target)]) == 1  # missing
    assert main(["--write", "--file", str(target)]) == 0
    assert main(["--check", "--file", str(target)]) == 0
    target.write_text(target.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert main(["--check", "--file", str(target)]) == 1  # edited by hand


def test_check_failure_message_names_the_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--check", "--file", str(tmp_path / "missing.json")]) == 1
    assert "make openapi" in capsys.readouterr().err
