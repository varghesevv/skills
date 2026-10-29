from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from app.core.logging_config import register_secret

# Environments where secrets must be strong. "local" and "ci" accept anything non-empty.
STRICT_ENVIRONMENTS = frozenset({"demo", "prod"})
MIN_STRICT_SECRET_LENGTH = 16
MIN_STRICT_JWT_SECRET_LENGTH = 32
WEAK_SECRETS = frozenset(
    {"password", "postgres", "changeme", "admin", "secret", "skills", "123456", "123456789"}
)


class ConfigError(RuntimeError):
    """A setting is missing or invalid. The message names variables, never values."""


class SecretsError(ConfigError):
    """A secret is missing or too weak. The message never contains the secret itself."""


class Settings(BaseSettings):
    """Application settings, read from environment variables (and .env locally).

    Secrets are SecretStr so they print as ********** in repr(), logs and error messages.
    There are deliberately no default values: every setting must be set in the environment
    (for local development the defaults live in .env.example and are copied to .env by `make env`),
    so a missing value stops the application at startup instead of silently using a guess.
    """

    # hide_input_in_errors keeps secret values out of pydantic validation error messages.
    # ".env" in the backend folder, or the repository-level one when running from backend/.
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), extra="ignore", hide_input_in_errors=True
    )

    environment: Literal["local", "ci", "demo", "prod"]
    database_url: SecretStr | None = None  # required by the API; checked by require_database_url()
    cors_origins: str
    report_timezone: str
    reports_output_dir: str  # where generated report files are written
    frontend_base_url: str  # used to build password reset links
    access_token_minutes: int
    refresh_token_days: int
    reset_token_minutes: int
    login_max_failures: int  # failed logins allowed per email and IP ...
    login_window_minutes: int  # ... within this many minutes
    # Mobile number reveals allowed per work host per hour and per 24 hours. These two are the
    # only settings with defaults, because the limits are a safety net, not a deployment choice.
    reveal_max_per_hour: int = Field(default=10, ge=1)
    reveal_max_per_day: int = Field(default=20, ge=1)
    jwt_secret: SecretStr | None = None  # required by the API; checked by require_jwt_secret()
    demo_user_password: SecretStr | None = None  # only used by `python -m app.cli seed-demo`

    @field_validator("reveal_max_per_day")
    @classmethod
    def _daily_reveals_cover_hourly(cls, daily: int, info: ValidationInfo) -> int:
        hourly = info.data.get("reveal_max_per_hour")
        if hourly is not None and daily < hourly:
            raise ValueError("REVEAL_MAX_PER_DAY must not be lower than REVEAL_MAX_PER_HOUR")
        return daily

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def require_database_url(self) -> str:
        if self.database_url is None or not self.database_url.get_secret_value():
            raise RuntimeError("DATABASE_URL is not set")
        return self.database_url.get_secret_value()

    def require_jwt_secret(self) -> str:
        if self.jwt_secret is None or not self.jwt_secret.get_secret_value():
            raise RuntimeError("JWT_SECRET is not set")
        return self.jwt_secret.get_secret_value()

    def secret_values(self) -> list[str]:
        """Every secret value (and the password inside the database URL), for log redaction."""
        values: list[str] = []
        for secret in (self.jwt_secret, self.demo_user_password):
            if secret is not None and secret.get_secret_value():
                values.append(secret.get_secret_value())
        if self.database_url is not None and self.database_url.get_secret_value():
            url = self.database_url.get_secret_value()
            values.append(url)
            try:
                password = make_url(url).password
            except Exception:  # noqa: BLE001 - never include the URL in an error message
                password = None
            if password:
                values.append(password)
        return values


def validate_secrets(settings: Settings) -> None:
    """Fail fast, with a message that never contains the secret, when a secret is unacceptable."""
    if settings.environment not in STRICT_ENVIRONMENTS:
        return
    try:
        url = settings.require_database_url()
        password = make_url(url).password or ""
    except RuntimeError as exc:
        raise SecretsError(str(exc)) from None
    except Exception:  # noqa: BLE001
        raise SecretsError("DATABASE_URL is not a valid database URL") from None
    if password.lower() in WEAK_SECRETS:
        raise SecretsError("The database password is a well-known weak password")
    if len(password) < MIN_STRICT_SECRET_LENGTH:
        raise SecretsError(
            f"The database password must be at least {MIN_STRICT_SECRET_LENGTH} characters long"
        )
    try:
        jwt_secret = settings.require_jwt_secret()
    except RuntimeError as exc:
        raise SecretsError(str(exc)) from None
    if jwt_secret.lower() in WEAK_SECRETS:
        raise SecretsError("The JWT secret is a well-known weak value")
    if len(jwt_secret) < MIN_STRICT_JWT_SECRET_LENGTH:
        raise SecretsError(
            f"The JWT secret must be at least {MIN_STRICT_JWT_SECRET_LENGTH} characters long"
        )


@lru_cache
def get_settings() -> Settings:
    try:
        settings = Settings()  # every value comes from the environment
    except ValidationError as exc:
        names = sorted({str(error["loc"][0]).upper() for error in exc.errors() if error["loc"]})
        raise ConfigError(f"Missing or invalid environment variables: {', '.join(names)}") from None
    validate_secrets(settings)
    for value in settings.secret_values():
        register_secret(value)
    return settings
