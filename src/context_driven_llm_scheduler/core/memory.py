"""Pulse memory and the closed memory-operation protocol.

A pulse's *memory* is the structured state it carries between wake-ups. It
lives under the reserved ``"memory"`` key of the pulse context, so it persists
through any :class:`~context_driven_llm_scheduler.core.store.ContextStore` unchanged and stays
plain JSON.

The agent never edits memory directly. It emits a small, closed set of
*memory operations* — ``note``, ``seen``, ``throttle``, ``set``, ``forget`` —
which :func:`apply_ops` applies atomically inside the trigger transaction.
Those five verbs are the whole vocabulary a pulse speaks to its own memory;
see :data:`MEMORY_TOOL_SCHEMA` for the model-facing tool definition.
"""

from datetime import datetime
from typing import Any

from context_driven_llm_scheduler.util import add_to_seen_set, prune_history

# The closed set of memory operations a pulse may emit. New verbs are added
# here deliberately; anything outside this set is rejected by apply_ops.
MEMORY_OPS = frozenset({"note", "seen", "throttle", "set", "forget"})


class Memory:
    """Typed view over the structured memory inside a pulse context.

    Wraps the nested ``memory`` dict and guarantees its four sections exist so
    callers can read them without defensive checks.

    Attributes:
        notes: Free-text observations, newest last; capped by ``keep.notes``.
        seen: De-duplication sets keyed by field name.
        throttles: Last-acted ISO timestamps keyed by field name.
        facts: Scalar key/value state the pulse wants to remember.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        """Wrap ``data`` in place, creating any missing sections.

        Args:
            data: The ``memory`` sub-dict of a pulse context.
        """
        self._data = data
        data.setdefault("notes", [])
        data.setdefault("seen", {})
        data.setdefault("throttles", {})
        data.setdefault("facts", {})

    @property
    def notes(self) -> list[str]:
        """The free-text note log, oldest first."""
        return self._data["notes"]

    @property
    def seen(self) -> dict[str, list[str]]:
        """De-duplication sets keyed by field name."""
        return self._data["seen"]

    @property
    def throttles(self) -> dict[str, str]:
        """Last-acted ISO timestamps keyed by field name."""
        return self._data["throttles"]

    @property
    def facts(self) -> dict[str, Any]:
        """Scalar key/value state."""
        return self._data["facts"]


def apply_ops(
    memory: Memory,
    ops: list[dict[str, Any]],
    now: datetime,
    keep: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Apply a batch of memory operations to ``memory`` in place.

    Each op is a dict with an ``"op"`` key naming one of :data:`MEMORY_OPS`.
    Operations are applied in order; a single bad op raises before any further
    ops are applied, so callers run this inside the trigger transaction where
    the surrounding save is what commits the result.

    Args:
        memory: The pulse memory to mutate.
        ops: The operations to apply.
        now: The trigger time, stamped by ``throttle`` operations.
        keep: Optional caps — ``keep["notes"]`` trims the note log and
            ``keep["seen"]`` caps each de-duplication set.

    Returns:
        A changeset: one record per applied op describing what actually
        changed (e.g. whether a ``seen`` id was new, the ``previous`` value a
        ``set`` overwrote). Suitable for an audit log or observability emit.

    Raises:
        ValueError: If an op is missing its ``"op"`` key, names an unknown
            operation, or omits a field that operation requires.
    """
    keep = keep or {}
    changes: list[dict[str, Any]] = []
    for index, op in enumerate(ops):
        name = op.get("op")
        if name is None:
            raise ValueError(f"Op {index} is missing its 'op' key: {op!r}")
        if name not in MEMORY_OPS:
            raise ValueError(
                f"Unknown memory op '{name}'; expected one of "
                f"{sorted(MEMORY_OPS)}"
            )
        changes.append(_apply_one(memory, name, op, now, keep))
    return changes


def _apply_one(
    memory: Memory,
    name: str,
    op: dict[str, Any],
    now: datetime,
    keep: dict[str, int],
) -> dict[str, Any]:
    """Apply a single validated-by-name operation.

    Args:
        memory: The pulse memory to mutate.
        name: The operation name (already known to be in ``MEMORY_OPS``).
        op: The full operation dict.
        now: The trigger time for ``throttle`` stamps.
        keep: Retention caps for ``note`` and ``seen``.

    Returns:
        A record of what changed, always carrying the ``op`` name plus
        operation-specific detail.

    Raises:
        ValueError: If a required field for the operation is absent.
    """
    if name == "note":
        text = _require(op, "text")
        memory.notes.append(text)
        if "notes" in keep:
            prune_history(memory._data, "notes", keep["notes"])
        return {"op": "note", "text": text}
    if name == "seen":
        field, id_ = _require(op, "field"), _require(op, "id")
        added = add_to_seen_set(
            memory.seen, field, id_, max_size=keep.get("seen")
        )
        return {"op": "seen", "field": field, "id": id_, "added": added}
    if name == "throttle":
        field = _require(op, "field")
        stamp = now.isoformat()
        memory.throttles[field] = stamp
        return {"op": "throttle", "field": field, "at": stamp}
    if name == "set":
        key, value = _require(op, "key"), _require(op, "value")
        previous = memory.facts.get(key)
        memory.facts[key] = value
        return {"op": "set", "key": key, "value": value,
                "previous": previous}
    # name == "forget"
    key = _require(op, "key")
    existed = key in memory.facts
    previous = memory.facts.pop(key, None)
    return {"op": "forget", "key": key, "existed": existed,
            "previous": previous}


def _require(op: dict[str, Any], field: str) -> Any:
    """Return ``op[field]`` or raise a clear error naming the operation.

    Args:
        op: The operation dict.
        field: The required field name.

    Returns:
        The value at ``field``.

    Raises:
        ValueError: If ``field`` is absent from ``op``.
    """
    if field not in op:
        raise ValueError(
            f"Memory op '{op.get('op')}' requires field '{field}': {op!r}"
        )
    return op[field]


# Model-facing tool definition (OpenAI/LiteLLM "tools" format). Hand this to
# your model so it emits memory operations as a single tool call; map the
# returned ``operations`` array straight into apply_ops / Pulse.persist.
MEMORY_TOOL_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "update_memory",
            "description": (
                "Record what you learned this pulse so you remember it next "
                "time. Emit one operation per distinct change."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "op": {
                                    "type": "string",
                                    "enum": sorted(MEMORY_OPS),
                                },
                                "text": {"type": "string"},
                                "field": {"type": "string"},
                                "id": {"type": "string"},
                                "key": {"type": "string"},
                                "value": {},
                            },
                            "required": ["op"],
                        },
                    }
                },
                "required": ["operations"],
            },
        },
    }
]
