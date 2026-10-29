import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import ConfigError, get_settings
from app.main import app
from app.services.app_config import load_profiles

client = TestClient(app)
TERM_KEYS = {
    "organisation", "organisations", "organisation_path", "organisations_path",
    "workhost", "workhosts", "workhost_path",
    "freelancer", "freelancers", "freelancer_path", "freelancers_path",
    "badge_organisation", "badge_workhost", "badge_freelancer",
}  # fmt: skip
WEB_PROFILES = Path(__file__).resolve().parents[2] / "frontend/src/terminology/profiles.json"


@pytest.fixture(autouse=True)
def fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_config_is_public_and_cacheable() -> None:
    response = client.get("/api/v1/app/config")  # no Authorization header
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    body = response.json()
    assert body["terminology"]["profile"] == "default"
    assert set(body["terminology"]["terms"]) == TERM_KEYS
    assert body["terminology"]["terms"]["workhost"] == "Work host"
    assert body["app"] == {"min_version": "0.0.0", "latest_version": "0.0.0"}


def test_church_profile_gives_the_church_words(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERMINOLOGY_PROFILE", "church")
    terms = client.get("/api/v1/app/config").json()["terminology"]
    assert terms["profile"] == "church"
    assert terms["terms"]["workhost"] == "Provider"
    assert terms["terms"]["freelancer"] == "Searcher"
    assert terms["terms"]["organisation_path"] == "church"


def test_unknown_profile_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERMINOLOGY_PROFILE", "no-such-profile")
    assert client.get("/api/v1/app/config").json()["terminology"]["profile"] == "default"


def test_versions_come_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MIN_VERSION", "1.2.0")
    monkeypatch.setenv("APP_LATEST_VERSION", "1.4.1")
    assert client.get("/api/v1/app/config").json()["app"] == {
        "min_version": "1.2.0",
        "latest_version": "1.4.1",
    }


def test_bad_version_stops_startup_without_echoing_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MIN_VERSION", "one.two")
    with pytest.raises(ConfigError) as error:
        get_settings()
    assert "APP_MIN_VERSION" in str(error.value)
    assert "one.two" not in str(error.value)


def test_every_profile_defines_every_term() -> None:
    for name, terms in load_profiles().items():
        assert set(terms) == TERM_KEYS | {"freelancers_path"}, name


@pytest.mark.skipif(not WEB_PROFILES.exists(), reason="frontend sources not in this checkout")
def test_words_match_the_web_profiles() -> None:
    """The API and the web must give the same words; this fails when only one is edited."""
    assert load_profiles() == json.loads(WEB_PROFILES.read_text(encoding="utf-8"))
