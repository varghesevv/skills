"""the people rules check the row as it is at commit, not as it was when the change was made

Revision ID: 0009
Revises: 0008

A deferred constraint trigger receives the row as it was when the statement ran. Checking that
version meant a transaction was refused when it first made someone a VERIFIER (still in their old
group) and then moved them into the group they lead, although the final state is valid. The
function now reads the person again when the check runs.
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_CURRENT = """
CREATE OR REPLACE FUNCTION trg_people_rules() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    n integer; cur people%ROWTYPE; grp home_groups%ROWTYPE; admin_of_church uuid;
BEGIN
    SELECT count(*) INTO n FROM people WHERE status = 'owner' AND closed_at IS NULL;
    IF n <> 1 THEN
        RAISE EXCEPTION 'there must be exactly one open OWNER (found %)', n
            USING ERRCODE = '23514';
    END IF;
    -- The groups and churches the change touched (both before and after).
    PERFORM check_church_rules(NEW.church_id);
    IF NEW.home_group_id IS NOT NULL THEN PERFORM check_group_rules(NEW.home_group_id); END IF;
    IF TG_OP = 'UPDATE' THEN
        PERFORM check_church_rules(OLD.church_id);
        IF OLD.home_group_id IS NOT NULL THEN
            PERFORM check_group_rules(OLD.home_group_id);
        END IF;
    END IF;
    -- The rules about this person use the row as it is now, not as it was when it changed.
    SELECT * INTO cur FROM people WHERE id = NEW.id;
    IF NOT FOUND OR cur.closed_at IS NOT NULL THEN RETURN NULL; END IF;
    IF cur.home_group_id IS NOT NULL THEN PERFORM check_group_rules(cur.home_group_id); END IF;
    PERFORM check_church_rules(cur.church_id);
    IF cur.status = 'verifier' THEN
        SELECT * INTO grp FROM home_groups WHERE id = cur.home_group_id;
        IF NOT FOUND OR grp.leader_id <> cur.id THEN
            RAISE EXCEPTION 'a VERIFIER must lead their own home group' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF cur.status = 'owner' THEN
        SELECT admin_id INTO admin_of_church FROM churches WHERE id = cur.church_id;
        IF admin_of_church IS DISTINCT FROM cur.id THEN
            RAISE EXCEPTION 'the OWNER must be the ADMIN of their own church'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NULL;
END $$
"""

_PREVIOUS = """
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
"""


def upgrade() -> None:
    op.execute(_CURRENT)


def downgrade() -> None:
    op.execute(_PREVIOUS.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
