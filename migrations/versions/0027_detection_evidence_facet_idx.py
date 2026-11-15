"""detection_evidence indexes that keep the detection detail page bounded

Revision ID: 0027
Revises: 0026

The detection detail page lists the distinct `rule_lifecycle` and
`evidence_semantics` values of a run and filters its repositories by agent,
channel, lifecycle, semantics and current/historical state. Without matching
indexes those lookups read every evidence row of the run — or, for the facet
lists, every row of the table — which on a multi-GB table took tens of seconds
per page view and, under concurrent page loads, exhausted the connection pool.

Each index here ends in `repo_id`, so "which repos match" is answered from the
index alone, and the facet lists come from a skip scan over the leading
columns. The agent and channel indexes from 0016 are replaced by covering
versions with the same leading columns, so existing plans keep working.

Locking: every index is built (and the old ones dropped) CONCURRENTLY in an
autocommit block, so detection runs keep writing evidence during the upgrade.
"""

from __future__ import annotations

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

_INDEXES = (
    ("de_run_lifecycle_repo_idx", "(run_id, rule_lifecycle, repo_id)"),
    ("de_run_semantics_repo_idx", "(run_id, evidence_semantics, repo_id)"),
    ("de_run_current_repo_idx", "(run_id, repo_id) WHERE is_current IS TRUE"),
    ("de_run_historical_repo_idx", "(run_id, repo_id) WHERE is_historical IS TRUE"),
    ("de_run_agent_channel_repo_idx", "(run_id, agent, channel, repo_id)"),
    ("de_run_channel_repo_idx", "(run_id, channel, repo_id)"),
)
# Superseded by the covering indexes above (same leading columns).
_REPLACED = (
    ("de_run_agent_idx", "(run_id, agent)"),
    ("de_run_channel_idx", "(run_id, channel)"),
)


def _create(name: str, definition: str) -> None:
    # A failed concurrent build leaves an INVALID index behind; drop it so a
    # rerun rebuilds instead of silently keeping the broken one.
    op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
    op.execute(f"CREATE INDEX CONCURRENTLY {name} ON detection_evidence {definition}")


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for name, definition in _INDEXES:
            _create(name, definition)
        for name, _definition in _REPLACED:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, definition in _REPLACED:
            _create(name, definition)
        for name, _definition in _INDEXES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
