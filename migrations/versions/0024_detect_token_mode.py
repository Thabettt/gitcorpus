"""Add the API detection token-mode setting

Revision ID: 0024
Revises: 0023
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "detect_token_mode",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'single'"),
        ),
    )
    op.create_check_constraint(
        "app_settings_detect_token_mode",
        "app_settings",
        "detect_token_mode IN ('single','pool4')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "app_settings_detect_token_mode",
        "app_settings",
        type_="check",
    )
    op.drop_column("app_settings", "detect_token_mode")
