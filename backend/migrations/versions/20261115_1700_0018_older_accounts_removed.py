"""the older accounts are gone: drop their tables and give the authentication tables to people

The last slice of S5.12a (D-46, D-48, D-49). The tables of freelancers, work hosts, organisations,
administrators and everything that hung on them (vouches of organisations, the older ratings, the
older record of number reveals, the older labels and time off) are dropped, with their data.
`login_history`, `refresh_tokens` and `password_reset_tokens` lose `user_type`: they hold people
only, and their `user_id` now points at `people` (rows of older accounts, and rows whose person is
unknown, are deleted first). `person_phone_reveals` becomes `phone_reveals`, the name of the data
model.

The downgrade recreates the older tables (empty) so that the earlier migrations can be undone; the
data of the older accounts is not brought back.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-15 17:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

# Children first: each of these references a table that comes later in the list.
_OLDER_TABLES = (
    "org_freelancers",
    "user_ratings",
    "phone_reveals",
    "freelancer_labels",
    "freelancer_unavailability",
    "organisations",
    "freelancers",
    "work_hosts",
    "admins",
)

_USER_TYPES = "'freelancer', 'workhost', 'organisation', 'admin', 'person'"

# The older tables as the migrations before this one left them (taken from a migrated database),
# so that the downgrade can put them back.
_LEVEL_FUNCTION = """
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

_OLDER_DDL = (
    """
    CREATE TABLE public.admins (
        id uuid DEFAULT gen_random_uuid() NOT NULL,
        user_email character varying(320) NOT NULL,
        mobile_number character varying(20) NOT NULL,
        password_hash text NOT NULL,
        last_login_at timestamp with time zone,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        updated_at timestamp with time zone DEFAULT now() NOT NULL,
        CONSTRAINT ck_admins_email_lowercase CHECK (((user_email)::text =
            lower((user_email)::text)))
    )
    """,
    """
    CREATE TABLE public.freelancer_labels (
        freelancer_id uuid NOT NULL,
        label_id uuid NOT NULL,
        level_label_id uuid,
        CONSTRAINT ck_freelancer_labels_level_differs CHECK (((level_label_id IS NULL) OR
            (level_label_id <> label_id)))
    )
    """,
    """
    CREATE TABLE public.freelancer_unavailability (
        id uuid DEFAULT gen_random_uuid() NOT NULL,
        freelancer_id uuid NOT NULL,
        unavailable_from timestamp with time zone NOT NULL,
        unavailable_to timestamp with time zone NOT NULL,
        CONSTRAINT ck_freelancer_unavailability_range_valid CHECK ((unavailable_from <
            unavailable_to))
    )
    """,
    """
    CREATE TABLE public.freelancers (
        id uuid DEFAULT gen_random_uuid() NOT NULL,
        user_email character varying(320) NOT NULL,
        mobile_number character varying(20) NOT NULL,
        password_hash text NOT NULL,
        last_login_at timestamp with time zone,
        whatsapp_availability boolean DEFAULT false NOT NULL,
        nationality character varying(100),
        primary_language character varying(100),
        rate_per_hour numeric(10,2),
        rate_currency character varying(3),
        is_rate_negotiable boolean DEFAULT false NOT NULL,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        updated_at timestamp with time zone DEFAULT now() NOT NULL,
        full_name character varying(200),
        CONSTRAINT ck_freelancers_currency_iso CHECK (((rate_currency IS NULL) OR
            ((rate_currency)::text ~ '^[A-Z]{3}$'::text))),
        CONSTRAINT ck_freelancers_email_lowercase CHECK (((user_email)::text =
            lower((user_email)::text))),
        CONSTRAINT ck_freelancers_rate_non_negative CHECK (((rate_per_hour IS NULL) OR
            (rate_per_hour >= (0)::numeric))),
        CONSTRAINT ck_freelancers_rate_with_currency CHECK (((rate_per_hour IS NULL) =
            (rate_currency IS NULL)))
    )
    """,
    """
    CREATE TABLE public.org_freelancers (
        org_id uuid NOT NULL,
        freelancer_id uuid NOT NULL,
        is_active boolean DEFAULT true NOT NULL,
        status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        CONSTRAINT ck_org_freelancers_status_valid CHECK (((status)::text = ANY
            ((ARRAY['pending'::character varying, 'approved'::character varying,
                'revoked'::character varying])::text[])))
    )
    """,
    """
    CREATE TABLE public.organisations (
        id uuid DEFAULT gen_random_uuid() NOT NULL,
        user_email character varying(320) NOT NULL,
        mobile_number character varying(20) NOT NULL,
        password_hash text NOT NULL,
        last_login_at timestamp with time zone,
        org_name character varying(200) NOT NULL,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        updated_at timestamp with time zone DEFAULT now() NOT NULL,
        approval_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
        approved_at timestamp with time zone,
        approved_by_admin_id uuid,
        CONSTRAINT ck_organisations_approval_status_valid CHECK (((approval_status)::text = ANY
            ((ARRAY['pending'::character varying, 'approved'::character varying,
                'rejected'::character varying])::text[]))),
        CONSTRAINT ck_organisations_email_lowercase CHECK (((user_email)::text =
            lower((user_email)::text)))
    )
    """,
    """
    CREATE TABLE public.phone_reveals (
        id uuid DEFAULT gen_random_uuid() NOT NULL,
        work_host_id uuid NOT NULL,
        freelancer_id uuid NOT NULL,
        revealed_at timestamp with time zone DEFAULT now() NOT NULL,
        channel character varying(10) NOT NULL,
        source character varying(10) NOT NULL,
        searched_skills character varying(100)[],
        CONSTRAINT ck_phone_reveals_channel_valid CHECK (((channel)::text = ANY
            ((ARRAY['dial'::character varying, 'show'::character varying])::text[]))),
        CONSTRAINT ck_phone_reveals_source_valid CHECK (((source)::text = ANY
            ((ARRAY['search'::character varying, 'detail'::character varying])::text[])))
    )
    """,
    """
    CREATE TABLE public.user_ratings (
        id uuid DEFAULT gen_random_uuid() NOT NULL,
        work_host_id uuid NOT NULL,
        freelancer_id uuid NOT NULL,
        rating smallint NOT NULL,
        comment text,
        rated_on timestamp with time zone DEFAULT now() NOT NULL,
        updated_at timestamp with time zone,
        CONSTRAINT ck_user_ratings_rating_range CHECK (((rating >= 1) AND (rating <= 10)))
    )
    """,
    """
    CREATE TABLE public.work_hosts (
        id uuid DEFAULT gen_random_uuid() NOT NULL,
        user_email character varying(320) NOT NULL,
        mobile_number character varying(20) NOT NULL,
        password_hash text NOT NULL,
        last_login_at timestamp with time zone,
        avail_sun boolean DEFAULT false NOT NULL,
        avail_mon boolean DEFAULT false NOT NULL,
        avail_tue boolean DEFAULT false NOT NULL,
        avail_wed boolean DEFAULT false NOT NULL,
        avail_thu boolean DEFAULT false NOT NULL,
        avail_fri boolean DEFAULT false NOT NULL,
        avail_sat boolean DEFAULT false NOT NULL,
        created_at timestamp with time zone DEFAULT now() NOT NULL,
        updated_at timestamp with time zone DEFAULT now() NOT NULL,
        full_name character varying(200),
        CONSTRAINT ck_work_hosts_email_lowercase CHECK (((user_email)::text =
            lower((user_email)::text)))
    )
    """,
    """
    ALTER TABLE ONLY public.freelancer_unavailability
        ADD CONSTRAINT ex_freelancer_unavailability_no_overlap EXCLUDE USING gist
            (freelancer_id WITH =, tstzrange(unavailable_from, unavailable_to) WITH &&)
    """,
    """
    ALTER TABLE ONLY public.user_ratings
        ADD CONSTRAINT host_freelancer UNIQUE (work_host_id, freelancer_id)
    """,
    """
    ALTER TABLE ONLY public.admins
        ADD CONSTRAINT pk_admins PRIMARY KEY (id)
    """,
    """
    ALTER TABLE ONLY public.freelancer_labels
        ADD CONSTRAINT pk_freelancer_labels PRIMARY KEY (freelancer_id, label_id)
    """,
    """
    ALTER TABLE ONLY public.freelancer_unavailability
        ADD CONSTRAINT pk_freelancer_unavailability PRIMARY KEY (id)
    """,
    """
    ALTER TABLE ONLY public.freelancers
        ADD CONSTRAINT pk_freelancers PRIMARY KEY (id)
    """,
    """
    ALTER TABLE ONLY public.org_freelancers
        ADD CONSTRAINT pk_org_freelancers PRIMARY KEY (org_id, freelancer_id)
    """,
    """
    ALTER TABLE ONLY public.organisations
        ADD CONSTRAINT pk_organisations PRIMARY KEY (id)
    """,
    """
    ALTER TABLE ONLY public.phone_reveals
        ADD CONSTRAINT pk_phone_reveals PRIMARY KEY (id)
    """,
    """
    ALTER TABLE ONLY public.user_ratings
        ADD CONSTRAINT pk_user_ratings PRIMARY KEY (id)
    """,
    """
    ALTER TABLE ONLY public.work_hosts
        ADD CONSTRAINT pk_work_hosts PRIMARY KEY (id)
    """,
    """
    ALTER TABLE ONLY public.admins
        ADD CONSTRAINT uq_admins_user_email UNIQUE (user_email)
    """,
    """
    ALTER TABLE ONLY public.freelancers
        ADD CONSTRAINT uq_freelancers_user_email UNIQUE (user_email)
    """,
    """
    ALTER TABLE ONLY public.organisations
        ADD CONSTRAINT uq_organisations_user_email UNIQUE (user_email)
    """,
    """
    ALTER TABLE ONLY public.work_hosts
        ADD CONSTRAINT uq_work_hosts_user_email UNIQUE (user_email)
    """,
    """
    CREATE INDEX ix_admins_created_at ON public.admins USING btree (created_at)
    """,
    """
    CREATE INDEX ix_freelancer_labels_label_id ON public.freelancer_labels USING btree
        (label_id)
    """,
    """
    CREATE INDEX ix_freelancers_created_at ON public.freelancers USING btree (created_at)
    """,
    """
    CREATE INDEX ix_freelancers_rate_currency ON public.freelancers USING btree (rate_currency,
        rate_per_hour)
    """,
    """
    CREATE INDEX ix_org_freelancers_freelancer_id ON public.org_freelancers USING btree
        (freelancer_id)
    """,
    """
    CREATE INDEX ix_organisations_approval_status ON public.organisations USING btree
        (approval_status)
    """,
    """
    CREATE INDEX ix_organisations_created_at ON public.organisations USING btree (created_at)
    """,
    """
    CREATE INDEX ix_phone_reveals_freelancer_id ON public.phone_reveals USING btree
        (freelancer_id)
    """,
    """
    CREATE INDEX ix_phone_reveals_host_time ON public.phone_reveals USING btree (work_host_id,
        revealed_at)
    """,
    """
    CREATE INDEX ix_phone_reveals_revealed_at ON public.phone_reveals USING btree (revealed_at)
    """,
    """
    CREATE INDEX ix_user_ratings_freelancer_id ON public.user_ratings USING btree
        (freelancer_id)
    """,
    """
    CREATE INDEX ix_work_hosts_created_at ON public.work_hosts USING btree (created_at)
    """,
    """
    CREATE TRIGGER freelancer_labels_level_check BEFORE INSERT OR UPDATE ON
        public.freelancer_labels FOR EACH ROW EXECUTE FUNCTION
            public.check_freelancer_label_level()
    """,
    """
    ALTER TABLE ONLY public.freelancer_labels
        ADD CONSTRAINT fk_freelancer_labels_freelancer_id_freelancers FOREIGN KEY
            (freelancer_id) REFERENCES public.freelancers(id) ON DELETE CASCADE
    """,
    """
    ALTER TABLE ONLY public.freelancer_labels
        ADD CONSTRAINT fk_freelancer_labels_label_id_labels FOREIGN KEY (label_id) REFERENCES
            public.labels(id) ON DELETE RESTRICT
    """,
    """
    ALTER TABLE ONLY public.freelancer_labels
        ADD CONSTRAINT fk_freelancer_labels_level_label_id_labels FOREIGN KEY (level_label_id)
            REFERENCES public.labels(id) ON DELETE RESTRICT
    """,
    """
    ALTER TABLE ONLY public.freelancer_unavailability
        ADD CONSTRAINT fk_freelancer_unavailability_freelancer_id_freelancers FOREIGN KEY
            (freelancer_id) REFERENCES public.freelancers(id) ON DELETE CASCADE
    """,
    """
    ALTER TABLE ONLY public.org_freelancers
        ADD CONSTRAINT fk_org_freelancers_freelancer_id_freelancers FOREIGN KEY (freelancer_id)
            REFERENCES public.freelancers(id) ON DELETE CASCADE
    """,
    """
    ALTER TABLE ONLY public.org_freelancers
        ADD CONSTRAINT fk_org_freelancers_org_id_organisations FOREIGN KEY (org_id) REFERENCES
            public.organisations(id) ON DELETE CASCADE
    """,
    """
    ALTER TABLE ONLY public.organisations
        ADD CONSTRAINT fk_organisations_approved_by_admin_id_admins FOREIGN KEY
            (approved_by_admin_id) REFERENCES public.admins(id) ON DELETE SET NULL
    """,
    """
    ALTER TABLE ONLY public.phone_reveals
        ADD CONSTRAINT fk_phone_reveals_freelancer_id_freelancers FOREIGN KEY (freelancer_id)
            REFERENCES public.freelancers(id) ON DELETE CASCADE
    """,
    """
    ALTER TABLE ONLY public.phone_reveals
        ADD CONSTRAINT fk_phone_reveals_work_host_id_work_hosts FOREIGN KEY (work_host_id)
            REFERENCES public.work_hosts(id) ON DELETE CASCADE
    """,
    """
    ALTER TABLE ONLY public.user_ratings
        ADD CONSTRAINT fk_user_ratings_freelancer_id_freelancers FOREIGN KEY (freelancer_id)
            REFERENCES public.freelancers(id) ON DELETE CASCADE
    """,
    """
    ALTER TABLE ONLY public.user_ratings
        ADD CONSTRAINT fk_user_ratings_work_host_id_work_hosts FOREIGN KEY (work_host_id)
            REFERENCES public.work_hosts(id) ON DELETE CASCADE
    """,
)

# renames of the table that replaces `phone_reveals`: (old name, new name) of indexes and rules
_RENAMED_INDEXES = (
    ("ix_person_phone_reveals_revealer_time", "ix_phone_reveals_revealer_time"),
    ("ix_person_phone_reveals_provider_id", "ix_phone_reveals_provider_id"),
    ("ix_person_phone_reveals_revealed_at", "ix_phone_reveals_revealed_at"),
)
_RENAMED_RULES = (
    ("pk_person_phone_reveals", "pk_phone_reveals"),
    ("ck_person_phone_reveals_channel_valid", "ck_phone_reveals_channel_valid"),
    ("ck_person_phone_reveals_not_self", "ck_phone_reveals_not_self"),
    ("ck_person_phone_reveals_source_valid", "ck_phone_reveals_source_valid"),
    ("fk_person_phone_reveals_provider_id_people", "fk_phone_reveals_provider_id_people"),
    ("fk_person_phone_reveals_revealer_id_people", "fk_phone_reveals_revealer_id_people"),
)


def _rename_reveals(table_from: str, table_to: str, indexes: tuple, rules: tuple) -> None:
    op.rename_table(table_from, table_to)
    for old, new in indexes:
        op.execute(sa.text(f"ALTER INDEX {old} RENAME TO {new}"))  # noqa: S608
    for old, new in rules:
        op.execute(sa.text(f"ALTER TABLE {table_to} RENAME CONSTRAINT {old} TO {new}"))  # noqa: S608


def upgrade() -> None:
    for table in _OLDER_TABLES:
        op.drop_table(table)
    op.execute("DROP FUNCTION IF EXISTS check_freelancer_label_level()")

    # The authentication tables hold people only. Rows of older accounts have no person, and a
    # row whose person is unknown cannot get the new reference.
    for table in ("login_history", "refresh_tokens", "password_reset_tokens"):
        op.execute(sa.text(f"DELETE FROM {table} WHERE user_type <> 'person'"))  # noqa: S608
        op.drop_constraint(op.f(f"ck_{table}_user_type_valid"), table, type_="check")
    op.execute("DELETE FROM refresh_tokens WHERE user_id NOT IN (SELECT id FROM people)")
    op.execute("DELETE FROM password_reset_tokens WHERE user_id NOT IN (SELECT id FROM people)")
    op.execute(
        "UPDATE login_history SET user_id = NULL WHERE user_id NOT IN (SELECT id FROM people)"
    )

    op.drop_index("ix_refresh_tokens_user", table_name="refresh_tokens")
    op.drop_index("ix_password_reset_tokens_user", table_name="password_reset_tokens")
    for table in ("login_history", "refresh_tokens", "password_reset_tokens"):
        op.drop_column(table, "user_type")

    op.create_foreign_key(
        op.f("fk_refresh_tokens_user_id_people"),
        "refresh_tokens",
        "people",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_password_reset_tokens_user_id_people"),
        "password_reset_tokens",
        "people",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_login_history_user_id_people"),
        "login_history",
        "people",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"])
    op.create_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"])
    op.create_index(op.f("ix_login_history_user_id"), "login_history", ["user_id"])

    _rename_reveals("person_phone_reveals", "phone_reveals", _RENAMED_INDEXES, _RENAMED_RULES)


def downgrade() -> None:
    _rename_reveals(
        "phone_reveals",
        "person_phone_reveals",
        tuple((new, old) for old, new in _RENAMED_INDEXES),
        tuple((new, old) for old, new in _RENAMED_RULES),
    )

    op.drop_index(op.f("ix_login_history_user_id"), table_name="login_history")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_constraint(op.f("fk_login_history_user_id_people"), "login_history", type_="foreignkey")
    op.drop_constraint(
        op.f("fk_password_reset_tokens_user_id_people"), "password_reset_tokens", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_refresh_tokens_user_id_people"), "refresh_tokens", type_="foreignkey"
    )
    for table in ("login_history", "refresh_tokens", "password_reset_tokens"):
        op.add_column(
            table,
            sa.Column("user_type", sa.String(20), nullable=False, server_default="person"),
        )
        op.alter_column(table, "user_type", server_default=None)
        op.create_check_constraint(
            op.f(f"ck_{table}_user_type_valid"), table, f"user_type IN ({_USER_TYPES})"
        )
    op.create_index("ix_refresh_tokens_user", "refresh_tokens", ["user_type", "user_id"])
    op.create_index(
        "ix_password_reset_tokens_user", "password_reset_tokens", ["user_type", "user_id"]
    )

    op.execute(_LEVEL_FUNCTION)
    for statement in _OLDER_DDL:
        op.execute(sa.text(statement))
