"""Allowed values for text columns that behave like enums (enforced with CHECK constraints)."""

from typing import Literal

LABEL_TYPES = ("skill", "language", "timing", "nativity", "skill_level")
CHAT_SIDES = ("starter", "provider")
PUSH_PLATFORMS = ("android",)
PUSH_STATES = ("pending", "sent", "cancelled")
CHAT_REPORT_REASONS = ("spam", "harassment", "inappropriate", "scam", "other")
REVEAL_CHANNELS = ("dial", "show")
REVEAL_SOURCES = ("search", "detail")
STATUSES = ("revoked", "pending", "searcher", "provider", "verifier", "admin", "owner")
REQUESTED_STATUSES = ("searcher", "provider")
STATUS_CHANGE_KINDS = (
    "signup",
    "admit",
    "appoint",
    "step-down",
    "revoke",
    "reinstate",
    "reconfirm",
    "handover",
    "operator",
)
Status = Literal["revoked", "pending", "searcher", "provider", "verifier", "admin", "owner"]
STATUS_RANK = {status: rank for rank, status in enumerate(STATUSES)}
GROUP_REQUEST_STATES = ("open", "approved", "declined")
REPORT_RUN_STATUSES = ("running", "succeeded", "failed")


def sql_in(column: str, values: tuple[str, ...]) -> str:
    """Build a CHECK expression such as: label_type IN ('skill', 'language')."""
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"
