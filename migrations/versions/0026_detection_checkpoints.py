"""detection checkpoints: per-repo resume state for detection runs

Revision ID: 0026
Revises: 0025
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "detection_checkpoints",
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("repo_id", sa.BigInteger(), nullable=False),
        sa.Column("clean", sa.Boolean(), nullable=False),
        sa.Column("contribution", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"]),
        sa.PrimaryKeyConstraint("run_id", "repo_id"),
    )


def downgrade() -> None:
    op.drop_table("detection_checkpoints")
