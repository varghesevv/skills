"""What the apps need to know before anyone logs in: the installation's words and app versions."""

import json
from functools import lru_cache
from pathlib import Path

from app.core.config import Settings
from app.schemas.app_config import AppConfig, AppVersions, Terminology

DEFAULT_PROFILE = "default"
PROFILES_FILE = Path(__file__).resolve().parents[1] / "core" / "terminology_profiles.json"


@lru_cache
def load_profiles() -> dict[str, dict[str, str]]:
    """The word profiles. Same content as frontend/src/terminology/profiles.json (a test checks)."""
    with PROFILES_FILE.open(encoding="utf-8") as handle:
        profiles: dict[str, dict[str, str]] = json.load(handle)
    return profiles


def build_app_config(settings: Settings) -> AppConfig:
    """Words for the active profile; an unknown name falls back to `default`, like the web."""
    profiles = load_profiles()
    name = (
        settings.terminology_profile
        if settings.terminology_profile in profiles
        else DEFAULT_PROFILE
    )
    return AppConfig(
        terminology=Terminology(profile=name, terms=profiles[name]),
        app=AppVersions(
            min_version=settings.app_min_version,
            latest_version=settings.app_latest_version,
        ),
    )
