"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-21 23:30:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

USER_TYPES = "'freelancer', 'workhost', 'organisation', 'admin'"


def _id() -> sa.Column:
    return sa.Column(
        "id",
        sa.Uuid(),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _tstz(name: str, *, nullable: bool = False, now: bool = False) -> sa.Column:
    """A timestamptz column, optionally defaulting to now()."""
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.func.now() if now else None,
        nullable=nullable,
    )


def _fk(
    name: str, target: str, ondelete: str, *, primary_key: bool = False, nullable: bool = False
) -> sa.Column:
    return sa.Column(
        name,
        sa.Uuid(),
        sa.ForeignKey(target, ondelete=ondelete),
        primary_key=primary_key,
        nullable=nullable,
    )


def _bool(name: str, default: str = "false") -> sa.Column:
    return sa.Column(name, sa.Boolean(), server_default=sa.text(default), nullable=False)


def _timestamps() -> list[sa.Column]:
    return [_tstz("created_at", now=True), _tstz("updated_at", now=True)]


def _account_columns() -> list[sa.Column]:
    return [
        sa.Column("user_email", sa.String(320), nullable=False, unique=True),
        sa.Column("mobile_number", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        _tstz("last_login_at", nullable=True),
    ]


def _email_check() -> sa.CheckConstraint:
    return sa.CheckConstraint("user_email = lower(user_email)", name="email_lowercase")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # ---- accounts -------------------------------------------------------------------------
    op.create_table(
        "work_hosts",
        _id(),
        *_account_columns(),
        *[_bool(f"avail_{day}") for day in ("sun", "mon", "tue", "wed", "thu", "fri", "sat")],
        *_timestamps(),
        _email_check(),
    )
    op.create_index(op.f("ix_work_hosts_created_at"), "work_hosts", ["created_at"])

    op.create_table(
        "freelancers",
        _id(),
        *_account_columns(),
        _bool("whatsapp_availability"),
        sa.Column("nationality", sa.String(100), nullable=True),
        sa.Column("primary_language", sa.String(100), nullable=True),
        sa.Column("rate_per_hour", sa.Numeric(10, 2), nullable=True),
        sa.Column("rate_currency", sa.String(3), nullable=True),
        _bool("is_rate_negotiable"),
        *_timestamps(),
        _email_check(),
        sa.CheckConstraint("rate_per_hour IS NULL OR rate_per_hour >= 0", name="rate_non_negative"),
        sa.CheckConstraint(
            "rate_currency IS NULL OR rate_currency ~ '^[A-Z]{3}$'", name="currency_iso"
        ),
        sa.CheckConstraint(
            "(rate_per_hour IS NULL) = (rate_currency IS NULL)", name="rate_with_currency"
        ),
    )
    op.create_index(op.f("ix_freelancers_created_at"), "freelancers", ["created_at"])

    op.create_table(
        "organisations",
        _id(),
        *_account_columns(),
        sa.Column("org_name", sa.String(200), nullable=False),
        *_timestamps(),
        _email_check(),
    )
    op.create_index(op.f("ix_organisations_created_at"), "organisations", ["created_at"])

    op.create_table("admins", _id(), *_account_columns(), *_timestamps(), _email_check())
    op.create_index(op.f("ix_admins_created_at"), "admins", ["created_at"])

    # ---- labels ---------------------------------------------------------------------------
    op.create_table(
        "labels",
        _id(),
        sa.Column("label_name", sa.String(100), nullable=False),
        sa.Column("label_type", sa.String(20), nullable=False),
        _bool("is_active", "true"),
        sa.UniqueConstraint("label_type", "label_name", name="type_name"),
        sa.CheckConstraint(
            "label_type IN ('skill', 'language', 'timing', 'nativity', 'skill_level')",
            name="label_type_valid",
        ),
    )

    op.create_table(
        "freelancer_labels",
        _fk("freelancer_id", "freelancers.id", "CASCADE", primary_key=True),
        _fk("label_id", "labels.id", "RESTRICT", primary_key=True),
        _fk("level_label_id", "labels.id", "RESTRICT", nullable=True),
        sa.CheckConstraint(
            "level_label_id IS NULL OR level_label_id <> label_id", name="level_differs"
        ),
    )
    op.create_index(op.f("ix_freelancer_labels_label_id"), "freelancer_labels", ["label_id"])
    # level_label_id may only be set on skill labels and must point at a skill_level label.
    op.execute(
        """
        CREATE FUNCTION check_freelancer_label_level() RETURNS trigger AS $$
        BEGIN
            IF NEW.level_label_id IS NOT NULL THEN
                IF (SELECT label_type FROM labels WHERE id = NEW.label_id) <> 'skill' THEN
                    RAISE EXCEPTION 'level_label_id is only allowed on skill labels';
                END IF;
                IF (SELECT label_type FROM labels WHERE id = NEW.level_label_id)
                        <> 'skill_level' THEN
                    RAISE EXCEPTION 'level_label_id must reference a skill_level label';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER freelancer_labels_level_check
        BEFORE INSERT OR UPDATE ON freelancer_labels
        FOR EACH ROW EXECUTE FUNCTION check_freelancer_label_level()
        """
    )

    # ---- vouching and availability ----------------------------------------------------------
    op.create_table(
        "org_freelancers",
        _fk("org_id", "organisations.id", "CASCADE", primary_key=True),
        _fk("freelancer_id", "freelancers.id", "CASCADE", primary_key=True),
        _bool("is_active", "true"),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        _tstz("created_at", now=True),
        sa.CheckConstraint("status IN ('pending', 'approved', 'revoked')", name="status_valid"),
    )
    op.create_index(op.f("ix_org_freelancers_freelancer_id"), "org_freelancers", ["freelancer_id"])

    op.create_table(
        "freelancer_unavailability",
        _id(),
        _fk("freelancer_id", "freelancers.id", "CASCADE"),
        _tstz("unavailable_from"),
        _tstz("unavailable_to"),
        sa.CheckConstraint("unavailable_from < unavailable_to", name="range_valid"),
        postgresql.ExcludeConstraint(
            ("freelancer_id", "="),
            (sa.text("tstzrange(unavailable_from, unavailable_to)"), "&&"),
            using="gist",
            name="ex_freelancer_unavailability_no_overlap",
        ),
    )

    # ---- login history, ratings, tokens ---------------------------------------------------
    op.create_table(
        "login_history",
        _id(),
        sa.Column("user_type", sa.String(20), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("login_email", sa.String(320), nullable=False),
        _tstz("login_time", now=True),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.CheckConstraint(f"user_type IN ({USER_TYPES})", name="user_type_valid"),
    )
    op.create_index(op.f("ix_login_history_login_time"), "login_history", ["login_time"])
    op.create_index("ix_login_history_email_time", "login_history", ["login_email", "login_time"])

    op.create_table(
        "user_ratings",
        _id(),
        _fk("work_host_id", "work_hosts.id", "CASCADE"),
        _fk("freelancer_id", "freelancers.id", "CASCADE"),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        _tstz("rated_on", now=True),
        _tstz("updated_at", nullable=True),
        sa.UniqueConstraint("work_host_id", "freelancer_id", name="host_freelancer"),
        sa.CheckConstraint("rating BETWEEN 1 AND 10", name="rating_range"),
    )
    op.create_index(op.f("ix_user_ratings_freelancer_id"), "user_ratings", ["freelancer_id"])

    op.create_table(
        "password_reset_tokens",
        _id(),
        sa.Column("user_type", sa.String(20), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        _tstz("expires_at"),
        _tstz("used_at", nullable=True),
        _tstz("created_at", now=True),
        sa.CheckConstraint(f"user_type IN ({USER_TYPES})", name="user_type_valid"),
    )
    op.create_index(
        "ix_password_reset_tokens_user", "password_reset_tokens", ["user_type", "user_id"]
    )

    op.create_table(
        "refresh_tokens",
        _id(),
        sa.Column("user_type", sa.String(20), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        _tstz("expires_at"),
        _tstz("revoked_at", nullable=True),
        _tstz("created_at", now=True),
        _fk("replaced_by_id", "refresh_tokens.id", "SET NULL", nullable=True),
        sa.CheckConstraint(f"user_type IN ({USER_TYPES})", name="user_type_valid"),
    )
    op.create_index("ix_refresh_tokens_user", "refresh_tokens", ["user_type", "user_id"])

    # ---- reports --------------------------------------------------------------------------
    op.create_table(
        "report_schedules",
        _id(),
        sa.Column("report_name", sa.String(100), nullable=False, unique=True),
        sa.Column("cron_expression", sa.String(100), nullable=False),
        sa.Column("timezone", sa.String(64), server_default="Asia/Dubai", nullable=False),
        _bool("is_enabled", "true"),
        sa.Column("recipients", sa.Text(), server_default="", nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "report_runs",
        _id(),
        sa.Column("report_name", sa.String(100), nullable=False),
        _tstz("window_from"),
        _tstz("window_to"),
        _tstz("started_at", now=True),
        _tstz("finished_at", nullable=True),
        sa.Column("status", sa.String(20), server_default="running", nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.UniqueConstraint("report_name", "window_from", "window_to", name="window"),
        sa.CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="status_valid"),
    )


def downgrade() -> None:
    for table in (
        "report_runs",
        "report_schedules",
        "refresh_tokens",
        "password_reset_tokens",
        "user_ratings",
        "login_history",
        "freelancer_unavailability",
        "org_freelancers",
    ):
        op.drop_table(table)
    op.execute("DROP TRIGGER IF EXISTS freelancer_labels_level_check ON freelancer_labels")
    op.drop_table("freelancer_labels")
    op.execute("DROP FUNCTION IF EXISTS check_freelancer_label_level()")
    for table in ("labels", "admins", "organisations", "freelancers", "work_hosts"):
        op.drop_table(table)
