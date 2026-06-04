"""context_driven_llm_scheduler — proactive, memoryful pulses for any scheduled job.

Inspired by OpenClaw's Heartbeat concept; we call our unit a *Pulse*. Each
wake-up runs ``manager.trigger(pulse_id)``, which loads a per-pulse context,
runs your handler, and persists the result for next time.

The core surface (``PulseManager``, ``FileStore``, helpers) imports with no
optional dependencies. ``SQLiteStore`` and ``APSchedulerPulse`` are imported
lazily so the ``sqlite`` / ``scheduler`` extras stay optional.
"""

from typing import Any

from context_driven_llm_scheduler.adapters.base import ModelAdapter
from context_driven_llm_scheduler.core.exceptions import (
    ContextDrivenLLMSchedulerError,
    PulseNotRegisteredError,
    StoreError,
)
from context_driven_llm_scheduler.core.manager import PulseManager
from context_driven_llm_scheduler.core.memory import (
    MEMORY_OPS,
    MEMORY_TOOL_SCHEMA,
    Memory,
    apply_ops,
)
from context_driven_llm_scheduler.core.pulse import Pulse, PulseDefinition
from context_driven_llm_scheduler.core.store import ContextStore
from context_driven_llm_scheduler.core.types import (
    ERROR_COUNT,
    LAST_ERROR,
    LAST_TRIGGERED,
    TRIGGER_COUNT,
    Context,
    PulseHandler,
)
from context_driven_llm_scheduler.result_log import ResultLog
from context_driven_llm_scheduler.stores.file import FileStore
from context_driven_llm_scheduler.util import (
    add_to_seen_set,
    check_throttle,
    migrate_context,
    prune_history,
    utcnow,
)

__version__ = "0.1.0"

__all__ = [
    "PulseManager",
    "ContextStore",
    "FileStore",
    "ResultLog",
    "SQLiteStore",
    "APSchedulerPulse",
    "Pulse",
    "PulseDefinition",
    "Memory",
    "apply_ops",
    "MEMORY_OPS",
    "MEMORY_TOOL_SCHEMA",
    "ModelAdapter",
    "LiteLLMAdapter",
    "Context",
    "PulseHandler",
    "ContextDrivenLLMSchedulerError",
    "PulseNotRegisteredError",
    "StoreError",
    "LAST_TRIGGERED",
    "TRIGGER_COUNT",
    "LAST_ERROR",
    "ERROR_COUNT",
    "add_to_seen_set",
    "check_throttle",
    "prune_history",
    "migrate_context",
    "utcnow",
    "__version__",
]


def __getattr__(name: str) -> Any:
    """Lazily import optional-dependency symbols on first access.

    Args:
        name: The attribute being accessed.

    Returns:
        The resolved class for ``SQLiteStore`` / ``APSchedulerPulse``.

    Raises:
        AttributeError: If ``name`` is not a known lazy export.
    """
    if name == "SQLiteStore":
        from context_driven_llm_scheduler.stores.sqlite import SQLiteStore

        return SQLiteStore
    if name == "APSchedulerPulse":
        from context_driven_llm_scheduler.schedulers.apscheduler_wrapper import (
            APSchedulerPulse,
        )

        return APSchedulerPulse
    if name == "LiteLLMAdapter":
        from context_driven_llm_scheduler.adapters.litellm_adapter import (
            LiteLLMAdapter,
        )

        return LiteLLMAdapter
    raise AttributeError(f"module 'context_driven_llm_scheduler' has no attribute '{name}'")
