import json
import logging
import subprocess
import sys
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import Principal, create_access_token
from app.main import app
from app.services import downloads

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "add-download.py"
APK_BYTES = b"PK-fake-apk-bytes-for-tests"
LIST_URL = "/api/v1/app/downloads"


def publish(folder: Path, apk: Path, version: str, build: int, notes: str = "") -> None:
    """Uses the real publishing script, so the API and the script cannot disagree on the layout."""
    command = [sys.executable, "-I", str(SCRIPT), "--dir", str(folder), "--apk", str(apk)]
    command += ["--version", version, "--build", str(build)]
    if notes:
        notes_file = apk.with_name("notes.txt")
        notes_file.write_text(notes, encoding="utf-8")
        command += ["--notes-file", str(notes_file)]
    subprocess.run(command, check=True, capture_output=True)  # noqa: S603 - our own script


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    downloads_dir = tmp_path / "downloads"
    apk = tmp_path / "build.apk"
    apk.write_bytes(APK_BYTES)
    publish(downloads_dir, apk, "1.9.0", 4, "Older build")
    publish(downloads_dir, apk, "1.10.0", 5, "Newer build")
    monkeypatch.setenv("DOWNLOADS_DIR", str(downloads_dir))
    get_settings.cache_clear()
    downloads.limiter.reset()
    yield downloads_dir
    get_settings.cache_clear()
    downloads.limiter.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def auth(user_type: str = "freelancer", user_id: uuid.UUID | None = None) -> dict[str, str]:
    token, _ = create_access_token(
        Principal(user_type=user_type, user_id=user_id or uuid.uuid4()),
        secret=get_settings().require_jwt_secret(),
        lifetime_minutes=5,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    "path",
    [
        LIST_URL,
        f"{LIST_URL}/android/1.10.0",
        f"{LIST_URL}/android/9.9.9",
        f"{LIST_URL}/android/latest",
    ],
)
def test_a_login_is_required(client: TestClient, folder: Path, path: str) -> None:
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer not-a-token"}).status_code == 401


@pytest.mark.parametrize("role", ["freelancer", "workhost", "organisation", "admin"])
def test_every_role_can_list_and_download(client: TestClient, folder: Path, role: str) -> None:
    assert client.get(LIST_URL, headers=auth(role)).status_code == 200
    assert client.get(f"{LIST_URL}/android/1.10.0", headers=auth(role)).content == APK_BYTES


def test_list_is_newest_first_by_number(client: TestClient, folder: Path) -> None:
    response = client.get(LIST_URL, headers=auth())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    items = response.json()["items"]
    assert [item["version"] for item in items] == ["1.10.0", "1.9.0"]  # not text order
    newest = items[0]
    assert newest["platform"] == "android"
    assert newest["build"] == 5
    assert newest["notes"] == "Newer build"
    assert newest["size_bytes"] == len(APK_BYTES)
    assert len(newest["sha256"]) == 64
    assert newest["filename"] == "skills-demo-1.10.0.apk"


def test_the_listed_hash_matches_the_file(client: TestClient, folder: Path) -> None:
    import hashlib

    item = client.get(LIST_URL, headers=auth()).json()["items"][0]
    body = client.get(f"{LIST_URL}/android/{item['version']}", headers=auth()).content
    assert hashlib.sha256(body).hexdigest() == item["sha256"]


def test_download_headers(client: TestClient, folder: Path) -> None:
    response = client.get(f"{LIST_URL}/android/1.10.0", headers=auth())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.android.package-archive"
    assert "skills-demo-1.10.0.apk" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "private, no-store"


def test_empty_list_when_the_feature_is_off(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOWNLOADS_DIR", raising=False)
    get_settings.cache_clear()
    try:
        assert client.get(LIST_URL, headers=auth()).json() == {"items": []}
        assert client.get(f"{LIST_URL}/android/1.0.0", headers=auth()).status_code == 404
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "version",
    ["9.9.9", "1.2", "1.2.3.4", "latest", "%2e%2e", "1.10.0%2f..%2f..%2findex.json"],
)
def test_unknown_or_malformed_versions_are_404(
    client: TestClient, folder: Path, version: str
) -> None:
    response = client.get(f"{LIST_URL}/android/{version}", headers=auth())
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_file_that_is_not_in_the_index_cannot_be_fetched(
    client: TestClient, folder: Path
) -> None:
    (folder / "android" / "3.0.0").mkdir()
    (folder / "android" / "3.0.0" / "skills-demo-3.0.0.apk").write_bytes(b"unlisted")
    assert client.get(f"{LIST_URL}/android/3.0.0", headers=auth()).status_code == 404
    (folder / "secret.txt").write_text("outside the android folder", encoding="utf-8")
    assert client.get(f"{LIST_URL}/android/secret.txt", headers=auth()).status_code == 404


def test_every_kind_of_not_found_looks_the_same(client: TestClient, folder: Path) -> None:
    """The caller cannot tell a missing build from a bad version or a missing file."""
    (folder / "android" / "1.9.0" / "skills-demo-1.9.0.apk").unlink()  # listed, file gone
    answers = {
        client.get(f"{LIST_URL}/android/{version}", headers=auth()).text
        for version in ("9.9.9", "latest", "1.2", "1.9.0")
    }
    assert len(answers) == 1


def test_a_listed_version_whose_file_is_gone_is_404(client: TestClient, folder: Path) -> None:
    (folder / "android" / "1.10.0" / "skills-demo-1.10.0.apk").unlink()
    assert client.get(f"{LIST_URL}/android/1.10.0", headers=auth()).status_code == 404


def test_a_link_leading_outside_the_folder_is_refused(
    client: TestClient, folder: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "skills-demo-1.10.0.apk").write_bytes(b"outside")
    version_dir = folder / "android" / "1.10.0"
    (version_dir / "skills-demo-1.10.0.apk").unlink()
    version_dir.rmdir()
    version_dir.symlink_to(outside, target_is_directory=True)
    assert client.get(f"{LIST_URL}/android/1.10.0", headers=auth()).status_code == 404


def test_an_index_with_an_unsafe_file_name_is_unusable(
    client: TestClient, folder: Path, caplog: pytest.LogCaptureFixture
) -> None:
    index = json.loads((folder / "index.json").read_text("utf-8"))
    index["android"][0]["file"] = "../../../etc/passwd"
    (folder / "index.json").write_text(json.dumps(index), encoding="utf-8")
    with caplog.at_level(logging.ERROR):
        assert client.get(LIST_URL, headers=auth()).json() == {"items": []}
    assert "unreadable or invalid" in caplog.text
    assert "passwd" not in caplog.text  # the content of the file is never logged


def test_a_broken_index_gives_an_empty_list(client: TestClient, folder: Path) -> None:
    (folder / "index.json").write_text("{ not json", encoding="utf-8")
    assert client.get(LIST_URL, headers=auth()).json() == {"items": []}


def test_downloads_are_limited_per_person(
    client: TestClient, folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOWNLOAD_MAX_PER_HOUR", "2")
    get_settings.cache_clear()
    person = auth("workhost", uuid.uuid4())
    other = auth("workhost", uuid.uuid4())
    url = f"{LIST_URL}/android/1.10.0"
    assert client.get(url, headers=person).status_code == 200
    assert client.get(url, headers=person).status_code == 200
    blocked = client.get(url, headers=person)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "download_limit_reached"
    assert int(blocked.headers["retry-after"]) > 0
    assert client.get(url, headers=other).status_code == 200  # someone else is not affected
    assert client.get(LIST_URL, headers=person).status_code == 200  # the list is not limited


def test_the_limit_frees_up_after_an_hour() -> None:
    now = [0.0]
    limiter = downloads.DownloadLimiter(clock=lambda: now[0])
    limiter.check("a", 1)
    with pytest.raises(Exception) as error:
        limiter.check("a", 1)
    assert getattr(error.value, "status_code", None) == 429
    now[0] = downloads.WINDOW_SECONDS + 1
    limiter.check("a", 1)


def test_a_download_is_logged_without_the_person_or_the_token(
    client: TestClient, folder: Path, caplog: pytest.LogCaptureFixture
) -> None:
    headers = auth("freelancer", uuid.uuid4())
    with caplog.at_level(logging.INFO, logger="app.api.v1.app_info"):
        client.get(f"{LIST_URL}/android/1.10.0", headers=headers)
    assert "download android version=1.10.0" in caplog.text
    assert headers["Authorization"].split()[-1] not in caplog.text


def test_parallel_requests_cannot_exceed_the_limit() -> None:
    """The check runs in a thread pool: 40 threads against a limit of 2 let exactly 2 through."""
    limiter = downloads.DownloadLimiter()
    allowed: list[int] = []
    refused: list[int] = []
    gate = threading.Barrier(40)

    def attempt(number: int) -> None:
        gate.wait()
        try:
            limiter.check("same-person", 2)
            allowed.append(number)
        except ApiError:
            refused.append(number)

    threads = [threading.Thread(target=attempt, args=(n,)) for n in range(40)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(allowed) == 2
    assert len(refused) == 38


def test_idle_people_are_dropped_so_memory_stays_bounded() -> None:
    now = [0.0]
    limiter = downloads.DownloadLimiter(clock=lambda: now[0])
    for number in range(downloads.DownloadLimiter.SWEEP_ABOVE + 5):
        limiter.check(f"person-{number}", 5)
    assert limiter.tracked_people() > downloads.DownloadLimiter.SWEEP_ABOVE
    now[0] = downloads.WINDOW_SECONDS + 1  # an hour later, nobody is counted any more
    limiter.check("someone-new", 5)
    assert limiter.tracked_people() == 1


def test_a_refused_download_is_not_logged_as_a_download(
    client: TestClient,
    folder: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("DOWNLOAD_MAX_PER_HOUR", "1")
    get_settings.cache_clear()
    headers = auth("workhost", uuid.uuid4())
    url = f"{LIST_URL}/android/1.10.0"
    with caplog.at_level(logging.INFO, logger="app.api.v1.app_info"):
        assert client.get(url, headers=headers).status_code == 200
        assert client.get(url, headers=headers).status_code == 429
    assert caplog.text.count("download android version=1.10.0") == 1


def test_settings_default_to_off_and_twenty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOWNLOADS_DIR", raising=False)
    monkeypatch.delenv("DOWNLOAD_MAX_PER_HOUR", raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.downloads_dir == ""
        assert settings.download_max_per_hour == 20
    finally:
        get_settings.cache_clear()
