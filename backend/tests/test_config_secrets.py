"""Secrets come from the environment, are validated, and never appear in text output."""

import secrets
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core.config import (
    MIN_STRICT_SECRET_LENGTH,
    ConfigError,
    SecretsError,
    Settings,
    get_settings,
    validate_secrets,
)


def settings_with_password(password: str, environment: str = "demo") -> Settings:
    url = f"postgresql+psycopg://app:{password}@db.internal:5432/app"
    return Settings(
        environment=environment,
        database_url=SecretStr(url),
        jwt_secret=SecretStr(secrets.token_hex(32)),
    )


def test_strong_password_is_accepted_in_demo() -> None:
    validate_secrets(settings_with_password(secrets.token_hex(16)))


def test_short_password_is_rejected_in_demo_without_leaking_it() -> None:
    password = secrets.token_hex(4)
    with pytest.raises(SecretsError) as error:
        validate_secrets(settings_with_password(password))
    assert password not in str(error.value)
    assert str(MIN_STRICT_SECRET_LENGTH) in str(error.value)


@pytest.mark.parametrize("weak", ["changeme", "password", "postgres"])
def test_well_known_password_is_rejected_in_prod(weak: str) -> None:
    with pytest.raises(SecretsError) as error:
        validate_secrets(settings_with_password(weak, environment="prod"))
    # Exact fixed text: it cannot contain the password that was rejected.
    assert str(error.value) == "The database password is a well-known weak password"


def test_missing_database_url_is_rejected_in_demo() -> None:
    with pytest.raises(SecretsError):
        validate_secrets(Settings(environment="demo", database_url=None))


def test_weak_password_is_tolerated_locally() -> None:
    validate_secrets(settings_with_password("short", environment="local"))


def test_secrets_are_hidden_in_repr_and_str() -> None:
    password = secrets.token_hex(16)
    settings = settings_with_password(password)
    assert password not in repr(settings)
    assert password not in str(settings)
    assert password not in repr(settings.model_dump())


def test_require_database_url_without_value_names_only_the_variable() -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        Settings(database_url=None).require_database_url()


def test_secret_values_include_url_and_password() -> None:
    password = secrets.token_hex(16)
    values = settings_with_password(password).secret_values()
    assert password in values
    assert any(password in value and "://" in value for value in values)


def test_missing_setting_stops_startup_and_names_the_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)  # so no .env file is picked up
    monkeypatch.delenv("REPORT_TIMEZONE", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(ConfigError, match="REPORT_TIMEZONE"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_unknown_environment_name_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "production")  # typo for "prod" must not skip validation
    get_settings.cache_clear()
    try:
        with pytest.raises(ConfigError, match="ENVIRONMENT"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_weak_jwt_secret_is_rejected_in_demo() -> None:
    settings = settings_with_password(secrets.token_hex(16))
    settings.jwt_secret = SecretStr(secrets.token_hex(4))
    with pytest.raises(SecretsError) as error:
        validate_secrets(settings)
    assert settings.jwt_secret.get_secret_value() not in str(error.value)


def test_reveal_limits_default_and_are_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import ValidationError

    monkeypatch.delenv("REVEAL_MAX_PER_HOUR", raising=False)
    monkeypatch.delenv("REVEAL_MAX_PER_DAY", raising=False)
    defaults = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (defaults.reveal_max_per_hour, defaults.reveal_max_per_day) == (10, 20)

    for hourly, daily in ((0, 20), (-1, 20), (10, 0), (30, 20)):
        with pytest.raises(ValidationError) as error:
            Settings(  # type: ignore[call-arg]
                _env_file=None, reveal_max_per_hour=hourly, reveal_max_per_day=daily
            )
        assert "reveal_max_per" in str(error.value)
