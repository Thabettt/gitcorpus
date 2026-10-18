"""detect evidence filters: compact per-repo facet table

Revision ID: 0018
Revises: 0017
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "detection_repo_filters",
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("repo_id", sa.BigInteger(), nullable=False),
        sa.Column("agent", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"]),
        sa.PrimaryKeyConstraint("run_id", "repo_id", "agent", "channel"),
    )
    op.create_index(
        "drf_run_agent_idx",
        "detection_repo_filters",
        ["run_id", "agent", "channel", "repo_id"],
    )
    op.execute(
        "INSERT INTO detection_repo_filters (run_id, repo_id, agent, channel)"
        " SELECT DISTINCT run_id, repo_id, agent, channel FROM detection_evidence"
        " ON CONFLICT DO NOTHING"
    )
    op.execute(
        "ALTER TABLE detection_evidence SET ("
        " autovacuum_vacuum_insert_scale_factor = 0.02,"
        " autovacuum_analyze_scale_factor = 0.02)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE detection_evidence RESET ("
        " autovacuum_vacuum_insert_scale_factor, autovacuum_analyze_scale_factor)"
    )
    op.drop_index("drf_run_agent_idx", table_name="detection_repo_filters")
    op.drop_table("detection_repo_filters")
