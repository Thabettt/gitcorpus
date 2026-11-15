"""Allow the content-attribution evidence channel

Revision ID: 0023
Revises: 0022
"""

from __future__ import annotations

from alembic import op

revision = "0023"
down_revision = "0022"
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
)


def upgrade() -> None:
    op.drop_constraint("detection_evidence_channel_check", "detection_evidence", type_="check")
    op.create_check_constraint(
        "detection_evidence_channel_check",
        "detection_evidence",
        "channel IN (" + ",".join(f"'{channel}'" for channel in CHANNELS) + ")",
    )


def downgrade() -> None:
    op.execute("DELETE FROM detection_evidence WHERE channel = 'content'")
    op.drop_constraint("detection_evidence_channel_check", "detection_evidence", type_="check")
    op.create_check_constraint(
        "detection_evidence_channel_check",
        "detection_evidence",
        "channel IN ('file','author','branch','label','bot','commit_trailer',"
        "'pr_metadata','issue')",
    )
