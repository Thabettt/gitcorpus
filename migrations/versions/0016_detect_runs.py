"""detect runs: trace packs + detection evidence

Revision ID: 0016
Revises: 0015
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

CHANNELS = "'file','author','branch','label','bot','commit_trailer','pr_metadata','issue'"


def upgrade() -> None:
    op.create_table(
        "trace_packs",
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("authors", postgresql.JSONB(), nullable=False),
        sa.Column("files", postgresql.JSONB(), nullable=False),
        sa.Column("branches", postgresql.JSONB(), nullable=False),
        sa.Column("labels", postgresql.JSONB(), nullable=False),
        sa.Column(
            "bots", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "generic_weights",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "exclusions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[\"CONVENTIONS.md\"]'::jsonb"),
        ),
        sa.Column(
            "frozen_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("version"),
    )
    op.add_column(
        "runs",
        sa.Column("kind", sa.Text(), nullable=False, server_default=sa.text("'find'")),
    )
    op.create_check_constraint("runs_kind_check", "runs", "kind IN ('find','detect')")
    op.add_column(
        "runs",
        sa.Column("source_run_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key("runs_source_run_id_fkey", "runs", "runs", ["source_run_id"], ["id"])
    op.add_column("runs", sa.Column("result_summary", postgresql.JSONB(), nullable=True))
    op.create_index("runs_kind_idx", "runs", ["kind", sa.text("created_at DESC")])
    op.create_index(
        "runs_source_idx",
        "runs",
        ["source_run_id"],
        postgresql_where=sa.text("source_run_id IS NOT NULL"),
    )
    op.add_column("run_items", sa.Column("detection", postgresql.JSONB(), nullable=True))
    op.create_table(
        "detection_evidence",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("repo_id", sa.BigInteger(), nullable=False),
        sa.Column("agent", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("pack_version", sa.Text(), nullable=False),
        sa.Column(
            "detected_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(f"channel IN ({CHANNELS})", name="detection_evidence_channel_check"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"]),
        sa.ForeignKeyConstraint(["pack_version"], ["trace_packs.version"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("de_run_repo_idx", "detection_evidence", ["run_id", "repo_id"])
    op.create_index("de_run_agent_idx", "detection_evidence", ["run_id", "agent"])
    op.create_index("de_run_channel_idx", "detection_evidence", ["run_id", "channel"])
    op.create_index("de_repo_idx", "detection_evidence", ["repo_id"])


def downgrade() -> None:
    op.drop_index("de_repo_idx", table_name="detection_evidence")
    op.drop_index("de_run_channel_idx", table_name="detection_evidence")
    op.drop_index("de_run_agent_idx", table_name="detection_evidence")
    op.drop_index("de_run_repo_idx", table_name="detection_evidence")
    op.drop_table("detection_evidence")
    op.drop_column("run_items", "detection")
    op.drop_index("runs_source_idx", table_name="runs")
    op.drop_index("runs_kind_idx", table_name="runs")
    op.drop_column("runs", "result_summary")
    op.drop_constraint("runs_source_run_id_fkey", "runs", type_="foreignkey")
    op.drop_column("runs", "source_run_id")
    op.drop_constraint("runs_kind_check", "runs", type_="check")
    op.drop_column("runs", "kind")
    op.drop_table("trace_packs")
