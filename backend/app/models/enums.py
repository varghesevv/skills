"""Allowed values for text columns that behave like enums (enforced with CHECK constraints)."""

USER_TYPES = ("freelancer", "workhost", "organisation", "admin")
LABEL_TYPES = ("skill", "language", "timing", "nativity", "skill_level")
VOUCH_STATUSES = ("pending", "approved", "revoked")
REPORT_RUN_STATUSES = ("running", "succeeded", "failed")


def sql_in(column: str, values: tuple[str, ...]) -> str:
    """Build a CHECK expression such as: label_type IN ('skill', 'language')."""
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"
