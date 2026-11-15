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


def test_the_access_log_never_shows_a_query_string() -> None:
    """uvicorn logs the whole address; a name typed into a search must not reach the log."""
    from app.core.logging_config import configure_logging

    configure_logging()
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        (
            "203.0.113.7:50000",
            "GET",
            "/api/v1/search/freelancers?name=Anna+Smith&skills=x",
            "1.1",
            200,
        ),
        None,
    )
    assert logging.getLogger("uvicorn.access").filter(record)
    line = RedactingFormatter("%(message)s").format(record)
    assert "Anna" not in line and "?" not in line
    assert '"GET /api/v1/search/freelancers HTTP/1.1" 200' in line


def test_a_line_without_a_query_string_is_left_alone() -> None:
    from app.core.logging_config import StripQueryString

    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, "%s %s", ("a", "b"), None
    )
    assert StripQueryString().filter(record)
    assert record.getMessage() == "a b"
