"""SQLite context store backed by SQLAlchemy Core.

Requires the ``sqlite`` extra (``pip install context_driven_llm_scheduler[sqlite]``). All
contexts live in a single ``pulse_context`` table keyed by pulse id.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import (
    Column,
    Connection,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    select,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from context_driven_llm_scheduler.core.exceptions import StoreError
from context_driven_llm_scheduler.core.store import ContextStore
from context_driven_llm_scheduler.core.types import Context
from context_driven_llm_scheduler.util import utcnow

_metadata = MetaData()
_pulse_context = Table(
    "pulse_context",
    _metadata,
    Column("key", String, primary_key=True),
    Column("context", Text, nullable=False),
    Column("updated_at", String, nullable=False),
)


class SQLiteStore(ContextStore):
    """Persist pulse contexts in a single-table SQLite database.

    Concurrency safety relies on SQLite's own locking: :meth:`transaction`
    opens a ``BEGIN IMMEDIATE`` transaction that takes the write lock up
    front, so concurrent writers serialize (each waits up to ``busy_timeout``)
    rather than losing updates. The active connection is shared with
    ``load``/``save`` inside the block via a :class:`~contextvars.ContextVar`.

    Attributes:
        url: The SQLAlchemy database URL in use.
    """

    url: str

    def __init__(
        self, path: str = ":memory:", *, busy_timeout: float = 30.0
    ) -> None:
        """Initialize the store and create the table if needed.

        Args:
            path: A filesystem path for the SQLite database, or a full
                SQLAlchemy URL (anything starting with ``sqlite:``). Defaults
                to a shared in-memory database.
            busy_timeout: Seconds a writer waits for the lock before failing.
        """
        if path.startswith("sqlite:"):
            self.url = path
        elif path == ":memory:":
            self.url = "sqlite://"
        else:
            self.url = f"sqlite:///{path}"

        self._active: ContextVar[Connection | None] = ContextVar(
            "active_connection", default=None
        )
        self._engine = create_engine(
            self.url,
            connect_args={
                "check_same_thread": False,
                "timeout": busy_timeout,
            },
        )
        self._install_immediate_transactions()
        _metadata.create_all(self._engine)

    def _install_immediate_transactions(self) -> None:
        """Make SQLAlchemy emit ``BEGIN IMMEDIATE`` for transactions.

        pysqlite's default transaction handling is disabled so we can control
        when (and how) ``BEGIN`` is emitted, giving us up-front write locks.
        """

        @event.listens_for(self._engine, "connect")
        def _disable_pysqlite_begin(dbapi_conn, _record):  # noqa: ANN001
            dbapi_conn.isolation_level = None

        @event.listens_for(self._engine, "begin")
        def _emit_begin_immediate(conn):  # noqa: ANN001
            conn.exec_driver_sql("BEGIN IMMEDIATE")

    def load(self, key: str) -> Context:
        """Load the context for ``key`` (empty dict if absent)."""
        stmt = select(_pulse_context.c.context).where(
            _pulse_context.c.key == key
        )
        try:
            conn = self._active.get()
            if conn is not None:
                row = conn.execute(stmt).first()
            else:
                with self._engine.connect() as conn:
                    row = conn.execute(stmt).first()
            return json.loads(row[0]) if row is not None else {}
        except (SQLAlchemyError, json.JSONDecodeError) as exc:
            raise StoreError(
                f"Failed to load context for '{key}': {exc}"
            ) from exc

    def save(self, key: str, context: Context) -> None:
        """Upsert ``context`` for ``key``."""
        try:
            payload = json.dumps(context, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise StoreError(
                f"Context for '{key}' is not JSON-serializable: {exc}"
            ) from exc

        now = utcnow().isoformat()
        stmt = (
            sqlite_insert(_pulse_context)
            .values(key=key, context=payload, updated_at=now)
            .on_conflict_do_update(
                index_elements=[_pulse_context.c.key],
                set_={"context": payload, "updated_at": now},
            )
        )
        conn = self._active.get()
        if conn is not None:
            conn.execute(stmt)
        else:
            with self._engine.begin() as conn:
                conn.execute(stmt)

    def delete(self, key: str) -> None:
        """Delete the row for ``key`` if present."""
        stmt = _pulse_context.delete().where(_pulse_context.c.key == key)
        conn = self._active.get()
        if conn is not None:
            conn.execute(stmt)
        else:
            with self._engine.begin() as conn:
                conn.execute(stmt)

    @contextmanager
    def transaction(self, key: str) -> Iterator[None]:
        """Open a ``BEGIN IMMEDIATE`` transaction shared with load/save."""
        conn = self._engine.connect()
        trans = conn.begin()
        token = self._active.set(conn)
        try:
            yield
            trans.commit()
        except Exception:
            trans.rollback()
            raise
        finally:
            self._active.reset(token)
            conn.close()
