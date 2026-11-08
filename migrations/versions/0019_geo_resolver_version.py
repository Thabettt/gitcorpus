"""version geo resolution cache and owner enrichment

Revision ID: 0019
Revises: 0018
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("owners", sa.Column("geo_version", sa.Text(), nullable=True))
    op.add_column(
        "geo_cache",
        sa.Column(
            "resolver_version",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'legacy'"),
        ),
    )
    # Owner countries are derived and the previous resolver is known to have
    # confident state-code false positives. Frozen run_items remain untouched;
    # mutable owner enrichment is intentionally recomputed under the new rules.
    op.execute("UPDATE owners SET country_iso = NULL, geo_confidence = NULL")


def downgrade() -> None:
    op.drop_column("geo_cache", "resolver_version")
    op.drop_column("owners", "geo_version")
