"""Shared type aliases and reserved context-key constants.

The pulse *context* is always a plain, JSON-serializable ``dict`` so it can
be persisted by any backend and inspected by any system. A handler reads and
mutates this dict to implement proactive logic across wake-ups.
"""

from collections.abc import Callable
from typing import Any

# A pulse context is an ordinary JSON-serializable mapping.
Context = dict[str, Any]

# Signature for a markdown-pulse handler. Receives the bound ``Pulse`` and the
# per-trigger ``extra``; returns memory operations for the manager to apply, or
# applies them itself via ``pulse.apply`` and returns ``None``. Typed loosely
# (the first arg is a ``Pulse``) to avoid a core import cycle.
PulseHandler = Callable[
    [Any, "dict[str, Any] | None"], "list[dict[str, Any]] | None"
]

# Reserved keys the manager writes automatically on every trigger. Handlers
# may read these but should avoid overwriting them directly.
LAST_TRIGGERED = "last_triggered"
TRIGGER_COUNT = "trigger_count"
LAST_ERROR = "last_error"
ERROR_COUNT = "error_count"
