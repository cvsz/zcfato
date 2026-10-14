"""Database engine and per-request SQLAlchemy session lifecycle."""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine


def make_engine(database_url: str) -> Engine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite:"):
        options["connect_args"] = {"check_same_thread": False}
    else:
        # Keep each process bounded; size the total across all workers for the DB capacity.
        options.update(pool_size=5, max_overflow=5, pool_timeout=10)

    engine = create_engine(database_url, **options)
    if database_url.startswith("sqlite:"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine
