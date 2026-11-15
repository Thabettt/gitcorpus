from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from store.bounded import bounded, is_statement_timeout


@pytest.fixture()
def single_connection_engine(test_database_url):
    engine = create_engine(test_database_url, pool_size=1, max_overflow=0)
    yield engine
    engine.dispose()


def test_bounded_view_caps_statements(single_connection_engine):
    view = bounded(single_connection_engine, 100)
    with view.connect() as connection:
        assert connection.execute(text("SHOW statement_timeout")).scalar_one() == "100ms"
        with pytest.raises(OperationalError) as caught:
            connection.execute(text("SELECT pg_sleep(2)"))
    assert is_statement_timeout(caught.value)


def test_bounded_limit_does_not_leak_onto_the_shared_pool(single_connection_engine):
    view = bounded(single_connection_engine, 100)
    with view.connect() as connection:
        connection.execute(text("SELECT 1"))
    # Same single pooled connection, used through the plain engine.
    with single_connection_engine.connect() as connection:
        assert connection.execute(text("SHOW statement_timeout")).scalar_one() == "0"
        connection.execute(text("SELECT pg_sleep(0.3)"))


def test_other_operational_errors_are_not_timeouts(single_connection_engine):
    with single_connection_engine.connect() as connection:
        with pytest.raises(Exception) as caught:
            connection.execute(text("SELECT 1/0"))
    assert not is_statement_timeout(caught.value)


def test_bounded_rejects_non_positive_timeouts(single_connection_engine):
    with pytest.raises(ValueError):
        bounded(single_connection_engine, 0)
