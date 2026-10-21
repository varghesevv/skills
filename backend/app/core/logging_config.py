"""Logging that never writes secrets.

Defence in depth: code must not log secrets in the first place, and this module removes
anything that still looks like one before a log line is written.
"""

import logging
import re

MIN_SECRET_LENGTH = 8  # shorter values would mangle ordinary words if registered

_registered: set[str] = set()

# A password inside a URL (scheme://user:<password>@host) is replaced by ***.
_URL_CREDENTIALS = re.compile(r"(\b[a-zA-Z][\w+.-]*://[^\s:/@]+:)[^\s@/]+(@)")
# password=..., "token": "...", api_key: ..., Authorization: ... (also password_hash, jwt_secret)
_KEY_VALUE = re.compile(
    r"(?i)(\w*(?:password|passwd|pwd|secret|token|api[_-]?key|authorization|credential)\w*"
    r"[\"']?\s*[:=]\s*[\"']?)(?:bearer\s+)?([^\s,;\"'&})]+)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")

REDACTED = "***"


def register_secret(value: str | None) -> None:
    """Remember an exact secret value so it is replaced wherever it appears in a log line."""
    if value and len(value) >= MIN_SECRET_LENGTH:
        _registered.add(value)


def redact(text: str) -> str:
    for secret in sorted(_registered, key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    text = _URL_CREDENTIALS.sub(rf"\1{REDACTED}\2", text)
    text = _BEARER.sub(f"Bearer {REDACTED}", text)
    return _KEY_VALUE.sub(rf"\1{REDACTED}", text)


class RedactingFormatter(logging.Formatter):
    """Redacts the final text, including exception tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        # A password reset link is deliberately logged (there is no email delivery yet). Pass it
        # in `extra={"reset_link": link}`: everything else on the line is still redacted.
        link = getattr(record, "reset_link", None)
        if isinstance(link, str) and link and link in text:
            marker = "\x00RESET_LINK\x00"
            return redact(text.replace(link, marker)).replace(marker, link)
        return redact(text)


def configure_logging(level: int = logging.INFO) -> None:
    """Send all logs (application, uvicorn, SQLAlchemy) through one redacting handler."""
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    # SQL statements with bound parameters can contain secrets and hashes.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
