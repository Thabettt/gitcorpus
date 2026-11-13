"""persist versioned analysis snapshots

Revision ID: 0021
Revises: 0020
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_snapshots",
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("source_finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "generated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("build_seconds", sa.Float(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
        sa.CheckConstraint(
            "build_seconds >= 0 AND build_seconds < 86400",
            name="analysis_snapshots_build_seconds_check",
        ),
    )


def downgrade() -> None:
    op.drop_table("analysis_snapshots")
