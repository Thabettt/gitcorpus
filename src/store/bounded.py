"""Statement-timeout-bounded engine views for interactive page reads.

Page requests share the web connection pool. A page query that runs for
minutes holds its connection for minutes, and Postgres keeps running it even
after the browser has given up and reloaded — so a slow page plus a polling or
refreshing tab piles up queries until the pool is exhausted and every request,
including cheap status polls, times out. Bounding the page's statements turns
that failure into one fast, visible error for the one slow view.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine

PAGE_STATEMENT_TIMEOUT_MS = 15_000


def bounded(engine: Engine, timeout_ms: int = PAGE_STATEMENT_TIMEOUT_MS) -> Engine:
    """Return a view of ``engine`` whose connections cap each statement.

    The view shares ``engine``'s pool. The limit is a ``SET LOCAL``, so it
    lasts only for the transaction each ``connect()`` block opens and never
    leaks onto the pooled connection. Code that commits mid-block loses the
    limit for the rest of that block; page reads do not commit.
    """
    timeout = int(timeout_ms)
    if timeout <= 0:
        raise ValueError("timeout_ms must be positive")
    view = engine.execution_options()

    @event.listens_for(view, "engine_connect")
    def _limit(connection: Connection) -> None:
        connection.exec_driver_sql(f"SET LOCAL statement_timeout = {timeout}")

    return view


def is_statement_timeout(exc: BaseException) -> bool:
    """True when ``exc`` is Postgres cancelling a statement for its timeout."""
    from psycopg import errors

    return isinstance(getattr(exc, "orig", None), errors.QueryCanceled)
