"""Allowed values for text columns that behave like enums (enforced with CHECK constraints)."""

from typing import Literal

# "person" is the identity of the church trust model (ADR-0017); the other four are the older
# accounts and go when their features move to it (decision D-20).
USER_TYPES = ("freelancer", "workhost", "organisation", "admin", "person")
LABEL_TYPES = ("skill", "language", "timing", "nativity", "skill_level")
APPROVAL_STATUSES = ("pending", "approved", "rejected")
VOUCH_STATUSES = ("pending", "approved", "revoked")
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
