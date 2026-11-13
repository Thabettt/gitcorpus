"""index committed file evidence used by analysis diagnostics

Revision ID: 0022
Revises: 0021
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "de_run_committed_file_repo_idx",
        "detection_evidence",
        ["run_id", "repo_id"],
        postgresql_where=sa.text(
            "channel = 'file' AND COALESCE(evidence->>'source', 'tree') <> 'gitignore'"
        ),
    )


def downgrade() -> None:
    op.drop_index("de_run_committed_file_repo_idx", table_name="detection_evidence")
