"""freeze repository age and commit depth in run snapshots

Revision ID: 0020
Revises: 0019
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run_items",
        sa.Column("repo_created_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column("run_items", sa.Column("commit_count", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "run_items_commit_count_nonnegative",
        "run_items",
        "commit_count IS NULL OR commit_count >= 0",
    )
    op.create_index(
        "run_items_commit_count_idx",
        "run_items",
        ["run_id", "commit_count"],
    )

    # Repository creation time is immutable GitHub metadata. Backfilling it
    # makes old runs usable without consulting mutable repository attributes at
    # report time.
    op.execute(
        "UPDATE run_items i SET repo_created_at = r.created_at "
        "FROM repos r WHERE i.repo_id = r.id AND i.repo_created_at IS NULL"
    )
    # Older searches only retained commit count when a commit filter was used.
    # Recover those values, but leave all genuinely unmeasured rows NULL.
    op.execute(
        "UPDATE run_items SET commit_count = (virtuals->>'commit_count')::integer "
        "WHERE commit_count IS NULL "
        "AND jsonb_typeof(virtuals->'commit_count') = 'number' "
        "AND (virtuals->>'commit_count') ~ '^[0-9]+$' "
        "AND (virtuals->>'commit_count')::numeric <= 2147483647"
    )


def downgrade() -> None:
    op.drop_index("run_items_commit_count_idx", table_name="run_items")
    op.drop_constraint("run_items_commit_count_nonnegative", "run_items", type_="check")
    op.drop_column("run_items", "commit_count")
    op.drop_column("run_items", "repo_created_at")
