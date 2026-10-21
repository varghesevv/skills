import logging
import secrets

from app.core.logging_config import RedactingFormatter, redact, register_secret


def test_url_credentials_are_redacted() -> None:
    password = secrets.token_hex(12)
    text = redact(f"connecting to postgresql://app:{password}@db:5432/app")
    assert password not in text
    assert "postgresql://app:***@db:5432/app" in text


def test_key_value_pairs_are_redacted() -> None:
    value = secrets.token_hex(12)
    for line in (
        f"password={value}",
        f'"password": "{value}"',
        f"jwt_secret: {value}",
        f"password_hash={value}",
        f"api_key={value}",
        f"Authorization: Bearer {value}",
    ):
        assert value not in redact(line), line


def test_bearer_tokens_are_redacted() -> None:
    token = secrets.token_urlsafe(24)
    assert token not in redact(f"header was Bearer {token} here")


def test_registered_secret_is_redacted_anywhere() -> None:
    secret = secrets.token_hex(12)
    register_secret(secret)
    assert secret not in redact(f"something odd happened with {secret} today")


def test_ordinary_text_is_left_alone() -> None:
    message = "Freelancer 42 updated their hourly rate to 25 AED"
    assert redact(message) == message


def test_formatter_redacts_messages_and_tracebacks() -> None:
    value = secrets.token_hex(12)
    formatter = RedactingFormatter("%(message)s")
    try:
        raise ValueError(f"bad password={value}")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "test", logging.ERROR, __file__, 1, "login failed password=%s", (value,), sys.exc_info()
        )
    assert value not in formatter.format(record)
