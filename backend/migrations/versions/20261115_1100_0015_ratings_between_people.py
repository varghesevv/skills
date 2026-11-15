"""ratings between people (S5.2)

A rating is given by a person (a SEARCHER or above) to a provider (decision D-42). The older
`user_ratings` table stays until slice S5.3, because the reports still read it.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-15 11:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ratings",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "rater_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "provider_id",
            sa.Uuid(),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "rated_on", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("rater_id", "provider_id", name="rater_provider"),
        sa.CheckConstraint("rating BETWEEN 1 AND 10", name="rating_range"),
        sa.CheckConstraint("rater_id <> provider_id", name="not_self"),
    )
    op.create_index(op.f("ix_ratings_provider_id"), "ratings", ["provider_id"])


def downgrade() -> None:
    op.drop_table("ratings")
