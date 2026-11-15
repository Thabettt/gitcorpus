"""Add lifecycle-aware trace-pack and evidence metadata

Revision ID: 0025
Revises: 0024
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

CHANNELS = (
    "file",
    "content",
    "author",
    "branch",
    "label",
    "bot",
    "commit_trailer",
    "pr_metadata",
    "issue",
    "hidden_ref",
)


def _channel_check(channels: tuple[str, ...]) -> str:
    return "channel IN (" + ",".join(f"'{channel}'" for channel in channels) + ")"


def upgrade() -> None:
    op.add_column(
        "trace_packs",
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column("trace_packs", sa.Column("document", postgresql.JSONB(), nullable=True))

    for name, column_type in (
        ("family_id", sa.Text()),
        ("family_name", sa.Text()),
        ("observed_as", sa.Text()),
        ("variant", sa.Text()),
        ("rule_id", sa.Text()),
        ("rule_lifecycle", sa.Text()),
        ("evidence_semantics", sa.Text()),
        ("forge", sa.Text()),
        ("role", sa.Text()),
        ("confidence", sa.Text()),
        ("provenance_ref", sa.Text()),
        ("is_current", sa.Boolean()),
        ("is_historical", sa.Boolean()),
        ("metric_eligibility", postgresql.JSONB()),
        ("explanatory_note", sa.Text()),
    ):
        op.add_column(
            "detection_evidence", sa.Column(name, column_type, nullable=True)
        )

    op.drop_constraint("detection_evidence_channel_check", "detection_evidence", type_="check")
    op.create_check_constraint(
        "detection_evidence_channel_check", "detection_evidence", _channel_check(CHANNELS)
    )
    op.create_index("de_run_family_idx", "detection_evidence", ["run_id", "family_id"])
    op.create_index("de_run_rule_idx", "detection_evidence", ["run_id", "rule_id"])


def downgrade() -> None:
    # Refuse rather than silently stripping lifecycle meaning from frozen packs
    # or evidence. A clean/test database remains fully downgradeable.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM trace_packs WHERE schema_version >= 2)
             OR EXISTS (
               SELECT 1 FROM detection_evidence
               WHERE family_id IS NOT NULL OR rule_id IS NOT NULL OR channel = 'hidden_ref'
             ) THEN
            RAISE EXCEPTION 'cannot downgrade 0025 while lifecycle-aware data exists';
          END IF;
        END
        $$
        """
    )
    op.drop_index("de_run_rule_idx", table_name="detection_evidence")
    op.drop_index("de_run_family_idx", table_name="detection_evidence")
    op.drop_constraint("detection_evidence_channel_check", "detection_evidence", type_="check")
    op.create_check_constraint(
        "detection_evidence_channel_check",
        "detection_evidence",
        _channel_check(CHANNELS[:-1]),
    )
    for name in (
        "explanatory_note",
        "metric_eligibility",
        "is_historical",
        "is_current",
        "provenance_ref",
        "confidence",
        "role",
        "forge",
        "evidence_semantics",
        "rule_lifecycle",
        "rule_id",
        "variant",
        "observed_as",
        "family_name",
        "family_id",
    ):
        op.drop_column("detection_evidence", name)
    op.drop_column("trace_packs", "document")
    op.drop_column("trace_packs", "schema_version")
