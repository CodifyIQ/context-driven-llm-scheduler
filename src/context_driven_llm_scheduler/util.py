"""Context helpers for common proactive-handler patterns.

These operate on the plain context dict and keep everything JSON-serializable,
so the resulting state persists cleanly across wake-ups.
"""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from context_driven_llm_scheduler.core.types import Context


def add_to_seen_set(
    context: Context,
    field: str,
    value: str,
    max_size: int | None = None,
) -> bool:
    """Record ``value`` as seen under ``field``, for de-duplication.

    The set is stored as an insertion-ordered list so it stays
    JSON-serializable and can be capped to the most recent entries.

    Args:
        context: The pulse context to mutate.
        field: Context key holding the seen list.
        value: The value to record.
        max_size: If set, keep only the most recent ``max_size`` values.

    Returns:
        True if ``value`` was newly added, False if it was already seen.
    """
    seen: list[str] = context.setdefault(field, [])
    if value in seen:
        return False
    seen.append(value)
    if max_size is not None and len(seen) > max_size:
        del seen[: len(seen) - max_size]
    return True


def check_throttle(
    context: Context,
    field: str,
    throttle_seconds: float,
    now: datetime,
) -> bool:
    """Return whether an action is allowed under a throttle, stamping it.

    On the first call, or once ``throttle_seconds`` have elapsed since the
    last allowed call, this returns True and records ``now`` as the new
    timestamp. Otherwise it returns False and leaves the timestamp untouched.

    Args:
        context: The pulse context to mutate.
        field: Context key holding the last-allowed ISO timestamp.
        throttle_seconds: Minimum seconds between allowed actions.
        now: The current time (timezone-aware recommended).

    Returns:
        True if the action is allowed now, False if still throttled.
    """
    last_iso = context.get(field)
    if last_iso is not None:
        last = datetime.fromisoformat(last_iso)
        if (now - last).total_seconds() < throttle_seconds:
            return False
    context[field] = now.isoformat()
    return True


def prune_history(
    context: Context, field: str, max_items: int
) -> None:
    """Trim a list under ``field`` to its most recent ``max_items`` entries.

    Args:
        context: The pulse context to mutate.
        field: Context key holding the history list.
        max_items: Maximum number of trailing items to keep.
    """
    history = context.get(field)
    if isinstance(history, list) and len(history) > max_items:
        del history[: len(history) - max_items]


def migrate_context(
    context: Context,
    target_version: int,
    migrations: dict[int, Callable[[Context], Context]],
    version_field: str = "schema_version",
) -> Context:
    """Apply forward migrations until the context reaches ``target_version``.

    Each migration ``migrations[v]`` upgrades a context from version ``v`` to
    ``v + 1``. Migrations are applied in order from the context's current
    version up to ``target_version``.

    Args:
        context: The pulse context to migrate.
        target_version: The schema version to reach.
        migrations: Mapping of source version to upgrade function.
        version_field: Context key tracking the schema version.

    Returns:
        The migrated context.

    Raises:
        KeyError: If a required migration step is missing.
    """
    version = context.get(version_field, 0)
    while version < target_version:
        context = migrations[version](context)
        version += 1
        context[version_field] = version
    return context


def utcnow() -> datetime:
    """Return the current timezone-aware UTC time.

    Returns:
        A timezone-aware :class:`datetime` in UTC.
    """
    return datetime.now(timezone.utc)


# Re-exported for handlers that want to annotate their own state payloads.
JsonValue = Any
