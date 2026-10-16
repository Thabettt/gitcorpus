"""app settings: detection worker count

Revision ID: 0017
Revises: 0016
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "detect_concurrency",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("32"),
        ),
    )
    op.create_check_constraint(
        "app_settings_detect_concurrency",
        "app_settings",
        "detect_concurrency BETWEEN 1 AND 64",
    )


def downgrade() -> None:
    op.drop_constraint("app_settings_detect_concurrency", "app_settings", type_="check")
    op.drop_column("app_settings", "detect_concurrency")
