"""labels and unavailability periods that belong to a person (S5.1)

The older tables (`freelancer_labels`, `freelancer_unavailability`) stay until slice S5.2 moves the
search and removes the older identity tables, because the search still reads them.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-15 09:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "person_labels",
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "label_id",
            sa.Uuid(),
            sa.ForeignKey("labels.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "level_label_id",
            sa.Uuid(),
            sa.ForeignKey("labels.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "level_label_id IS NULL OR level_label_id <> label_id", name="level_differs"
        ),
    )
    op.create_index(op.f("ix_person_labels_label_id"), "person_labels", ["label_id"])
    # level_label_id may only be set on skill labels and must point at a skill_level label.
    op.execute(
        """
        CREATE FUNCTION check_person_label_level() RETURNS trigger AS $$
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
        CREATE TRIGGER person_labels_level_check
        BEFORE INSERT OR UPDATE ON person_labels
        FOR EACH ROW EXECUTE FUNCTION check_person_label_level()
        """
    )

    op.create_table(
        "person_unavailability",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("unavailable_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unavailable_to", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("unavailable_from < unavailable_to", name="range_valid"),
        postgresql.ExcludeConstraint(
            ("person_id", "="),
            (sa.text("tstzrange(unavailable_from, unavailable_to)"), "&&"),
            using="gist",
            name="ex_person_unavailability_no_overlap",
        ),
    )


def downgrade() -> None:
    op.drop_table("person_unavailability")
    op.execute("DROP TRIGGER IF EXISTS person_labels_level_check ON person_labels")
    op.drop_table("person_labels")
    op.execute("DROP FUNCTION IF EXISTS check_person_label_level()")
