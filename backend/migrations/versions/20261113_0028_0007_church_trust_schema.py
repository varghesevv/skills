"""church trust schema: churches, home groups, people, vouching and requests

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-13 00:28:11.210692
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


# The rules of the church trust model that Alembic does not model: deferrable exclusion
# constraints ("at most one") and deferred constraint triggers ("at least one", and who may hold
# which role). All of them are checked at COMMIT, so succession and handover can change several
# rows in one transaction. They raise check_violation (23514), which SQLAlchemy reports as
# IntegrityError. See docs/specification/03-data-model.md, "The six invariants".
_FUNCTIONS = [
    """
    CREATE FUNCTION status_rank(s text) RETURNS integer
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
        SELECT CASE s WHEN 'revoked' THEN 0 WHEN 'pending' THEN 1 WHEN 'searcher' THEN 2
            WHEN 'provider' THEN 3 WHEN 'verifier' THEN 4 WHEN 'admin' THEN 5
            WHEN 'owner' THEN 6 END
    $$
    """,
    """
    CREATE FUNCTION check_church_rules(c uuid) RETURNS void LANGUAGE plpgsql AS $$
    DECLARE ch churches%ROWTYPE; adm people%ROWTYPE; n integer;
    BEGIN
        SELECT * INTO ch FROM churches WHERE id = c;
        IF NOT FOUND OR ch.closed_at IS NOT NULL THEN RETURN; END IF;
        SELECT * INTO adm FROM people WHERE id = ch.admin_id;
        IF NOT FOUND OR adm.church_id <> c OR adm.closed_at IS NOT NULL
           OR adm.status NOT IN ('admin', 'owner') THEN
            RAISE EXCEPTION 'church % needs an open ADMIN of its own (or the OWNER)', c
                USING ERRCODE = '23514';
        END IF;
        SELECT count(*) INTO n FROM people
            WHERE church_id = c AND status = 'admin' AND closed_at IS NULL;
        IF (adm.status = 'owner' AND n <> 0) OR (adm.status = 'admin' AND n <> 1) THEN
            RAISE EXCEPTION 'church % must have exactly one ADMIN', c USING ERRCODE = '23514';
        END IF;
        -- The OWNER is always the ADMIN of their own church.
        IF EXISTS (SELECT 1 FROM people WHERE church_id = c AND status = 'owner'
                   AND closed_at IS NULL AND id <> ch.admin_id) THEN
            RAISE EXCEPTION 'the OWNER must be the ADMIN of their own church %', c
                USING ERRCODE = '23514';
        END IF;
    END $$
    """,
    """
    CREATE FUNCTION check_group_rules(g uuid) RETURNS void LANGUAGE plpgsql AS $$
    DECLARE hg home_groups%ROWTYPE; lead people%ROWTYPE;
    BEGIN
        SELECT * INTO hg FROM home_groups WHERE id = g;
        IF NOT FOUND OR hg.closed_at IS NOT NULL THEN RETURN; END IF;
        SELECT * INTO lead FROM people WHERE id = hg.leader_id;
        IF NOT FOUND OR lead.closed_at IS NOT NULL OR lead.home_group_id IS DISTINCT FROM g
           OR status_rank(lead.status) < 4 THEN
            RAISE EXCEPTION 'home group % needs an open leader of status VERIFIER or higher '
                'who belongs to it', g USING ERRCODE = '23514';
        END IF;
    END $$
    """,
    """
    CREATE FUNCTION trg_churches_rules() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        PERFORM check_church_rules(NEW.id);
        RETURN NULL;
    END $$
    """,
    """
    CREATE FUNCTION trg_home_groups_rules() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        PERFORM check_group_rules(NEW.id);
        RETURN NULL;
    END $$
    """,
    """
    CREATE FUNCTION trg_people_rules() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE n integer; grp home_groups%ROWTYPE; admin_of_church uuid;
    BEGIN
        SELECT count(*) INTO n FROM people WHERE status = 'owner' AND closed_at IS NULL;
        IF n <> 1 THEN
            RAISE EXCEPTION 'there must be exactly one open OWNER (found %)', n
                USING ERRCODE = '23514';
        END IF;
        PERFORM check_church_rules(NEW.church_id);
        IF NEW.home_group_id IS NOT NULL THEN PERFORM check_group_rules(NEW.home_group_id); END IF;
        IF TG_OP = 'UPDATE' THEN
            PERFORM check_church_rules(OLD.church_id);
            IF OLD.home_group_id IS NOT NULL THEN
                PERFORM check_group_rules(OLD.home_group_id);
            END IF;
        END IF;
        IF NEW.closed_at IS NULL THEN
            IF NEW.status = 'verifier' THEN
                SELECT * INTO grp FROM home_groups WHERE id = NEW.home_group_id;
                IF NOT FOUND OR grp.leader_id <> NEW.id THEN
                    RAISE EXCEPTION 'a VERIFIER must lead their own home group'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            IF NEW.status = 'owner' THEN
                SELECT admin_id INTO admin_of_church FROM churches WHERE id = NEW.church_id;
                IF admin_of_church IS DISTINCT FROM NEW.id THEN
                    RAISE EXCEPTION 'the OWNER must be the ADMIN of their own church'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
        END IF;
        RETURN NULL;
    END $$
    """,
    """
    CREATE FUNCTION trg_status_changes_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'status_changes is append-only' USING ERRCODE = '23514';
    END $$
    """,
    """
    CREATE FUNCTION trg_move_requests_rules() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE from_church uuid; to_church uuid;
    BEGIN
        SELECT church_id INTO from_church FROM home_groups WHERE id = NEW.from_group_id;
        SELECT church_id INTO to_church FROM home_groups WHERE id = NEW.to_group_id;
        IF from_church IS DISTINCT FROM to_church THEN
            RAISE EXCEPTION 'a move stays within one church' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$
    """,
    """
    CREATE FUNCTION trg_vouches_rules() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE voucher people%ROWTYPE; applicant people%ROWTYPE;
    BEGIN
        SELECT * INTO voucher FROM people WHERE id = NEW.voucher_id;
        IF NOT FOUND OR voucher.closed_at IS NOT NULL OR status_rank(voucher.status) < 2 THEN
            RAISE EXCEPTION 'only an admitted, open person can vouch' USING ERRCODE = '23514';
        END IF;
        SELECT * INTO applicant FROM people WHERE id = NEW.applicant_id;
        IF NOT FOUND OR applicant.closed_at IS NOT NULL
           OR NOT (applicant.status = 'pending'
                   OR (applicant.status = 'searcher'
                       AND applicant.requested_status IS NOT DISTINCT FROM 'provider'))
        THEN
            RAISE EXCEPTION 'a vouch is for a pending applicant, or a searcher applying to provide'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$
    """,
]

_LIFECYCLE_CHECKS = [
    (
        "group_requests",
        "decision_matches_state",
        "(state = 'open') = (decided_at IS NULL AND decided_by_id IS NULL)",
    ),
    (
        "admin_invitations",
        "one_outcome",
        "NOT (accepted_at IS NOT NULL AND cancelled_at IS NOT NULL)",
    ),
    (
        "admin_invitations",
        "email_cleared_when_decided",
        "email IS NULL OR (accepted_at IS NULL AND cancelled_at IS NULL)",
    ),
    (
        "handover_requests",
        "one_outcome",
        "NOT (accepted_at IS NOT NULL AND cancelled_at IS NOT NULL)",
    ),
    (
        "move_requests",
        "one_outcome",
        "NOT (completed_at IS NOT NULL AND cancelled_at IS NOT NULL)",
    ),
]

_EXCLUSIONS = [
    (
        "people",
        "ex_people_one_owner",
        "EXCLUDE USING btree (status WITH =) WHERE (status = 'owner' AND closed_at IS NULL)",
    ),
    (
        "people",
        "ex_people_one_admin_per_church",
        "EXCLUDE USING btree (church_id WITH =) WHERE (status = 'admin' AND closed_at IS NULL)",
    ),
    (
        "home_groups",
        "ex_home_groups_one_group_per_leader",
        "EXCLUDE USING btree (leader_id WITH =) WHERE (closed_at IS NULL)",
    ),
]

_TRIGGERS = [
    """
    CREATE CONSTRAINT TRIGGER people_rules
        AFTER INSERT OR UPDATE OF status, church_id, home_group_id, closed_at ON people
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION trg_people_rules()
    """,
    """
    CREATE CONSTRAINT TRIGGER churches_rules
        AFTER INSERT OR UPDATE OF admin_id, closed_at ON churches
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION trg_churches_rules()
    """,
    """
    CREATE CONSTRAINT TRIGGER home_groups_rules
        AFTER INSERT OR UPDATE OF leader_id, closed_at ON home_groups
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION trg_home_groups_rules()
    """,
    """
    CREATE TRIGGER status_changes_append_only
        BEFORE UPDATE OR DELETE ON status_changes
        FOR EACH ROW EXECUTE FUNCTION trg_status_changes_append_only()
    """,
    """
    CREATE TRIGGER move_requests_rules
        BEFORE INSERT ON move_requests
        FOR EACH ROW EXECUTE FUNCTION trg_move_requests_rules()
    """,
    """
    CREATE TRIGGER vouches_rules
        BEFORE INSERT ON vouches
        FOR EACH ROW EXECUTE FUNCTION trg_vouches_rules()
    """,
]


def _create_rules() -> None:
    for table, name, definition in _EXCLUSIONS:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} {definition} DEFERRABLE INITIALLY DEFERRED"
        )
    for statement in _FUNCTIONS + _TRIGGERS:
        op.execute(statement)


def _drop_rules() -> None:
    for statement in (
        "DROP TRIGGER vouches_rules ON vouches",
        "DROP TRIGGER move_requests_rules ON move_requests",
        "DROP TRIGGER status_changes_append_only ON status_changes",
        "DROP TRIGGER home_groups_rules ON home_groups",
        "DROP TRIGGER churches_rules ON churches",
        "DROP TRIGGER people_rules ON people",
        "DROP FUNCTION trg_vouches_rules()",
        "DROP FUNCTION trg_move_requests_rules()",
        "DROP FUNCTION trg_status_changes_append_only()",
        "DROP FUNCTION trg_people_rules()",
        "DROP FUNCTION trg_home_groups_rules()",
        "DROP FUNCTION trg_churches_rules()",
        "DROP FUNCTION check_group_rules(uuid)",
        "DROP FUNCTION check_church_rules(uuid)",
        "DROP FUNCTION status_rank(text)",
    ):
        op.execute(statement)
    for table, name, _ in _EXCLUSIONS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")


def upgrade() -> None:
    op.create_table(
        "churches",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_churches")),
    )
    op.create_index(
        "uq_churches_open_name",
        "churches",
        [sa.literal_column("lower(name)")],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    op.create_table(
        "home_groups",
        sa.Column("church_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("leader_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["church_id"], ["churches.id"], name=op.f("fk_home_groups_church_id_churches")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_home_groups")),
        sa.UniqueConstraint("id", "church_id", name=op.f("uq_home_groups_id")),
    )
    op.create_index(op.f("ix_home_groups_church_id"), "home_groups", ["church_id"], unique=False)
    op.create_index(
        "uq_home_groups_open_name",
        "home_groups",
        ["church_id", sa.literal_column("lower(name)")],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    op.create_table(
        "people",
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("church_id", sa.Uuid(), nullable=False),
        sa.Column("home_group_id", sa.Uuid(), nullable=True),
        sa.Column("last_home_group_id", sa.Uuid(), nullable=True),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("mobile_number", sa.String(length=20), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("requested_status", sa.String(length=20), nullable=True),
        sa.Column("status_set_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "flagged_for_recheck", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "whatsapp_availability", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("nationality", sa.String(length=100), nullable=True),
        sa.Column("primary_language", sa.String(length=100), nullable=True),
        sa.Column("rate_per_hour", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("rate_currency", sa.String(length=3), nullable=True),
        sa.Column(
            "is_rate_negotiable", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(home_group_id IS NULL) = (status = 'revoked' OR closed_at IS NOT NULL)",
            name=op.f("ck_people_group_matches_status"),
        ),
        sa.CheckConstraint(
            "rate_currency IS NULL OR rate_currency ~ '^[A-Z]{3}$'",
            name=op.f("ck_people_currency_iso"),
        ),
        sa.CheckConstraint(
            "requested_status IS NULL OR requested_status IN ('searcher', 'provider')",
            name=op.f("ck_people_requested_status_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('revoked', 'pending', 'searcher', 'provider', "
            "'verifier', 'admin', 'owner')",
            name=op.f("ck_people_status_valid"),
        ),
        sa.CheckConstraint(
            "(rate_per_hour IS NULL) = (rate_currency IS NULL)",
            name=op.f("ck_people_rate_with_currency"),
        ),
        sa.CheckConstraint(
            "closed_at IS NOT NULL OR (full_name IS NOT NULL AND email IS NOT NULL "
            "AND mobile_number IS NOT NULL AND password_hash IS NOT NULL)",
            name=op.f("ck_people_open_has_details"),
        ),
        sa.CheckConstraint(
            "closed_at IS NULL OR (full_name IS NULL AND email IS NULL "
            "AND mobile_number IS NULL AND password_hash IS NULL)",
            name=op.f("ck_people_closed_has_no_details"),
        ),
        sa.CheckConstraint(
            "email IS NULL OR email = lower(email)", name=op.f("ck_people_email_lowercase")
        ),
        sa.CheckConstraint(
            "full_name IS NULL OR char_length(full_name) >= 2", name=op.f("ck_people_name_length")
        ),
        sa.CheckConstraint(
            "rate_per_hour IS NULL OR rate_per_hour >= 0", name=op.f("ck_people_rate_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["church_id"], ["churches.id"], name=op.f("fk_people_church_id_churches")
        ),
        sa.ForeignKeyConstraint(
            ["home_group_id", "church_id"],
            ["home_groups.id", "home_groups.church_id"],
            name="fk_people_home_group_id_home_groups",
        ),
        sa.ForeignKeyConstraint(
            ["last_home_group_id", "church_id"],
            ["home_groups.id", "home_groups.church_id"],
            name="fk_people_last_home_group_id_home_groups",
        ),
        sa.ForeignKeyConstraint(
            ["status_set_by_id"], ["people.id"], name=op.f("fk_people_status_set_by_id_people")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_people")),
    )
    op.create_index(op.f("ix_people_church_id"), "people", ["church_id", "status"], unique=False)
    op.create_index(op.f("ix_people_created_at"), "people", ["created_at"], unique=False)
    op.create_index(
        op.f("ix_people_home_group_id"), "people", ["home_group_id", "status"], unique=False
    )
    op.create_index(
        op.f("ix_people_last_home_group_id"), "people", ["last_home_group_id"], unique=False
    )
    op.create_index(
        "ix_people_providers",
        "people",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text(
            "status IN ('provider', 'verifier', 'admin', 'owner') AND closed_at IS NULL"
        ),
    )
    op.create_index(
        op.f("ix_people_status_set_by_id"), "people", ["status_set_by_id"], unique=False
    )
    op.create_index(
        "uq_people_open_email",
        "people",
        [sa.literal_column("lower(email)")],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    op.create_index(
        "uq_people_open_mobile",
        "people",
        ["mobile_number"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )

    # The circular references (a church needs its ADMIN, a group its leader, a person a church)
    # are added now and checked at COMMIT, so a succession can change several rows in one
    # transaction in any order.
    op.create_foreign_key(
        op.f("fk_churches_admin_id_people"),
        "churches",
        "people",
        ["admin_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        op.f("fk_home_groups_leader_id_people"),
        "home_groups",
        "people",
        ["leader_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "admin_invitations",
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("church_name", sa.String(length=200), nullable=False),
        sa.Column("invited_by_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["invited_by_id"], ["people.id"], name=op.f("fk_admin_invitations_invited_by_id_people")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_admin_invitations_token_hash")),
    )
    op.create_index(
        op.f("ix_admin_invitations_invited_by_id"),
        "admin_invitations",
        ["invited_by_id"],
        unique=False,
    )
    op.create_table(
        "contact_views",
        sa.Column("viewer_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("screen", sa.String(length=50), nullable=False),
        sa.Column(
            "viewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name=op.f("fk_contact_views_person_id_people")
        ),
        sa.ForeignKeyConstraint(
            ["viewer_id"], ["people.id"], name=op.f("fk_contact_views_viewer_id_people")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_views")),
    )
    op.create_index(
        op.f("ix_contact_views_person_id"), "contact_views", ["person_id"], unique=False
    )
    op.create_index(
        op.f("ix_contact_views_viewer_id"),
        "contact_views",
        ["viewer_id", "viewed_at"],
        unique=False,
    )
    op.create_table(
        "group_invitations",
        sa.Column("home_group_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["people.id"], name=op.f("fk_group_invitations_created_by_id_people")
        ),
        sa.ForeignKeyConstraint(
            ["home_group_id"],
            ["home_groups.id"],
            name=op.f("fk_group_invitations_home_group_id_home_groups"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_group_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_group_invitations_token_hash")),
    )
    op.create_index(
        op.f("ix_group_invitations_created_by_id"),
        "group_invitations",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_group_invitations_home_group_id"),
        "group_invitations",
        ["home_group_id"],
        unique=False,
    )
    op.create_table(
        "group_requests",
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("church_id", sa.Uuid(), nullable=False),
        sa.Column("group_name", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('open', 'approved', 'declined')", name=op.f("ck_group_requests_state_valid")
        ),
        sa.ForeignKeyConstraint(
            ["church_id"], ["churches.id"], name=op.f("fk_group_requests_church_id_churches")
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"], ["people.id"], name=op.f("fk_group_requests_decided_by_id_people")
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"], ["people.id"], name=op.f("fk_group_requests_requester_id_people")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_group_requests")),
    )
    op.create_index(
        op.f("ix_group_requests_church_id"), "group_requests", ["church_id"], unique=False
    )
    op.create_index(
        op.f("ix_group_requests_decided_by_id"), "group_requests", ["decided_by_id"], unique=False
    )
    op.create_index(
        "uq_group_requests_one_open",
        "group_requests",
        ["requester_id"],
        unique=True,
        postgresql_where=sa.text("state = 'open'"),
    )
    op.create_table(
        "handover_requests",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("new_owner_id", sa.Uuid(), nullable=False),
        sa.Column("successor_admin_id", sa.Uuid(), nullable=True),
        sa.Column("successor_leader_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "owner_id <> new_owner_id", name=op.f("ck_handover_requests_different_people")
        ),
        sa.ForeignKeyConstraint(
            ["new_owner_id"], ["people.id"], name=op.f("fk_handover_requests_new_owner_id_people")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["people.id"], name=op.f("fk_handover_requests_owner_id_people")
        ),
        sa.ForeignKeyConstraint(
            ["successor_admin_id"],
            ["people.id"],
            name=op.f("fk_handover_requests_successor_admin_id_people"),
        ),
        sa.ForeignKeyConstraint(
            ["successor_leader_id"],
            ["people.id"],
            name=op.f("fk_handover_requests_successor_leader_id_people"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_handover_requests")),
    )
    op.create_index(
        op.f("ix_handover_requests_new_owner_id"),
        "handover_requests",
        ["new_owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_handover_requests_successor_admin_id"),
        "handover_requests",
        ["successor_admin_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_handover_requests_successor_leader_id"),
        "handover_requests",
        ["successor_leader_id"],
        unique=False,
    )
    op.create_index(
        "uq_handover_requests_one_open",
        "handover_requests",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL AND cancelled_at IS NULL"),
    )
    op.create_table(
        "move_requests",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("from_group_id", sa.Uuid(), nullable=False),
        sa.Column("to_group_id", sa.Uuid(), nullable=False),
        sa.Column("agreed_by_person_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agreed_by_from_leader_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agreed_by_to_leader_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "from_group_id <> to_group_id", name=op.f("ck_move_requests_different_groups")
        ),
        sa.ForeignKeyConstraint(
            ["from_group_id"],
            ["home_groups.id"],
            name=op.f("fk_move_requests_from_group_id_home_groups"),
        ),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name=op.f("fk_move_requests_person_id_people")
        ),
        sa.ForeignKeyConstraint(
            ["to_group_id"],
            ["home_groups.id"],
            name=op.f("fk_move_requests_to_group_id_home_groups"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_move_requests")),
    )
    op.create_index(
        op.f("ix_move_requests_from_group_id"), "move_requests", ["from_group_id"], unique=False
    )
    op.create_index(
        op.f("ix_move_requests_person_id"), "move_requests", ["person_id"], unique=False
    )
    op.create_index(
        op.f("ix_move_requests_to_group_id"), "move_requests", ["to_group_id"], unique=False
    )
    op.create_table(
        "notifications",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name=op.f("fk_notifications_person_id_people")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        "ix_notifications_person_read_created",
        "notifications",
        ["person_id", "read_at", "created_at"],
        unique=False,
    )
    op.create_table(
        "status_changes",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("changed_by_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "(changed_by_id IS NULL) = (kind IN ('signup', 'operator'))",
            name=op.f("ck_status_changes_actor_matches_kind"),
        ),
        sa.CheckConstraint(
            "changed_by_id IS DISTINCT FROM person_id OR kind = 'handover'",
            name=op.f("ck_status_changes_not_self"),
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN ('revoked', 'pending', 'searcher', "
            "'provider', 'verifier', 'admin', 'owner')",
            name=op.f("ck_status_changes_from_status_valid"),
        ),
        sa.CheckConstraint(
            "kind IN ('signup', 'admit', 'appoint', 'step-down', 'revoke', "
            "'reinstate', 'reconfirm', 'handover', 'operator')",
            name=op.f("ck_status_changes_kind_valid"),
        ),
        sa.CheckConstraint(
            "to_status IN ('revoked', 'pending', 'searcher', 'provider', "
            "'verifier', 'admin', 'owner')",
            name=op.f("ck_status_changes_to_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"], ["people.id"], name=op.f("fk_status_changes_changed_by_id_people")
        ),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name=op.f("fk_status_changes_person_id_people")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_status_changes")),
    )
    op.create_index(
        op.f("ix_status_changes_changed_by_id"), "status_changes", ["changed_by_id"], unique=False
    )
    op.create_index(
        "ix_status_changes_person_at", "status_changes", ["person_id", "at"], unique=False
    )
    op.create_table(
        "vouch_links",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["person_id"], ["people.id"], name=op.f("fk_vouch_links_person_id_people")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vouch_links")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_vouch_links_token_hash")),
    )
    op.create_index(op.f("ix_vouch_links_person_id"), "vouch_links", ["person_id"], unique=False)
    op.create_table(
        "vouches",
        sa.Column("applicant_id", sa.Uuid(), nullable=False),
        sa.Column("voucher_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("applicant_id <> voucher_id", name=op.f("ck_vouches_not_self")),
        sa.ForeignKeyConstraint(
            ["applicant_id"], ["people.id"], name=op.f("fk_vouches_applicant_id_people")
        ),
        sa.ForeignKeyConstraint(
            ["voucher_id"], ["people.id"], name=op.f("fk_vouches_voucher_id_people")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vouches")),
        sa.UniqueConstraint("applicant_id", "voucher_id", name=op.f("uq_vouches_applicant_id")),
    )
    op.create_index(op.f("ix_vouches_voucher_id"), "vouches", ["voucher_id"], unique=False)
    for table, name, condition in _LIFECYCLE_CHECKS:
        op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)
    _create_rules()


def downgrade() -> None:
    _drop_rules()
    op.drop_constraint(op.f("fk_home_groups_leader_id_people"), "home_groups", type_="foreignkey")
    op.drop_constraint(op.f("fk_churches_admin_id_people"), "churches", type_="foreignkey")
    op.drop_index(op.f("ix_vouches_voucher_id"), table_name="vouches")
    op.drop_table("vouches")
    op.drop_index(op.f("ix_vouch_links_person_id"), table_name="vouch_links")
    op.drop_table("vouch_links")
    op.drop_index("ix_status_changes_person_at", table_name="status_changes")
    op.drop_index(op.f("ix_status_changes_changed_by_id"), table_name="status_changes")
    op.drop_table("status_changes")
    op.drop_index("ix_notifications_person_read_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_move_requests_to_group_id"), table_name="move_requests")
    op.drop_index(op.f("ix_move_requests_person_id"), table_name="move_requests")
    op.drop_index(op.f("ix_move_requests_from_group_id"), table_name="move_requests")
    op.drop_table("move_requests")
    op.drop_index(
        "uq_handover_requests_one_open",
        table_name="handover_requests",
        postgresql_where=sa.text("accepted_at IS NULL AND cancelled_at IS NULL"),
    )
    op.drop_index(op.f("ix_handover_requests_successor_leader_id"), table_name="handover_requests")
    op.drop_index(op.f("ix_handover_requests_successor_admin_id"), table_name="handover_requests")
    op.drop_index(op.f("ix_handover_requests_new_owner_id"), table_name="handover_requests")
    op.drop_table("handover_requests")
    op.drop_index(
        "uq_group_requests_one_open",
        table_name="group_requests",
        postgresql_where=sa.text("state = 'open'"),
    )
    op.drop_index(op.f("ix_group_requests_decided_by_id"), table_name="group_requests")
    op.drop_index(op.f("ix_group_requests_church_id"), table_name="group_requests")
    op.drop_table("group_requests")
    op.drop_index(op.f("ix_group_invitations_home_group_id"), table_name="group_invitations")
    op.drop_index(op.f("ix_group_invitations_created_by_id"), table_name="group_invitations")
    op.drop_table("group_invitations")
    op.drop_index(op.f("ix_contact_views_viewer_id"), table_name="contact_views")
    op.drop_index(op.f("ix_contact_views_person_id"), table_name="contact_views")
    op.drop_table("contact_views")
    op.drop_index(op.f("ix_admin_invitations_invited_by_id"), table_name="admin_invitations")
    op.drop_table("admin_invitations")
    op.drop_index(
        "uq_people_open_mobile", table_name="people", postgresql_where=sa.text("closed_at IS NULL")
    )
    op.drop_index(
        "uq_people_open_email", table_name="people", postgresql_where=sa.text("closed_at IS NULL")
    )
    op.drop_index(op.f("ix_people_status_set_by_id"), table_name="people")
    op.drop_index(
        "ix_people_providers",
        table_name="people",
        postgresql_where=sa.text(
            "status IN ('provider', 'verifier', 'admin', 'owner') AND closed_at IS NULL"
        ),
    )
    op.drop_index(op.f("ix_people_last_home_group_id"), table_name="people")
    op.drop_index(op.f("ix_people_home_group_id"), table_name="people")
    op.drop_index(op.f("ix_people_created_at"), table_name="people")
    op.drop_index(op.f("ix_people_church_id"), table_name="people")
    op.drop_table("people")
    op.drop_index(
        "uq_home_groups_open_name",
        table_name="home_groups",
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    op.drop_index(op.f("ix_home_groups_church_id"), table_name="home_groups")
    op.drop_table("home_groups")
    op.drop_index(
        "uq_churches_open_name",
        table_name="churches",
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    op.drop_table("churches")
