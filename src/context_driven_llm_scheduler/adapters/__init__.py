"""Model adapters: the third pluggable seam, alongside scheduler and store.

The core is model-agnostic. :class:`~context_driven_llm_scheduler.adapters.base.ModelAdapter`
is the contract the membrane needs — complete a prompt and count tokens — and
:data:`~context_driven_llm_scheduler.core.memory.MEMORY_TOOL_SCHEMA` is the tool the model uses
to emit memory operations.

``LiteLLMAdapter`` (the ``litellm`` extra) implements the contract against 100+
providers and is imported lazily so this package stays dependency-free.
"""

from typing import Any

from context_driven_llm_scheduler.adapters.base import ModelAdapter

__all__ = ["ModelAdapter", "LiteLLMAdapter"]


def __getattr__(name: str) -> Any:
    """Lazily import ``LiteLLMAdapter`` so litellm stays optional.

    Args:
        name: The attribute being accessed.

    Returns:
        The resolved ``LiteLLMAdapter`` class.

    Raises:
        AttributeError: If ``name`` is not a known lazy export.
    """
    if name == "LiteLLMAdapter":
        from context_driven_llm_scheduler.adapters.litellm_adapter import (
            LiteLLMAdapter,
        )

        return LiteLLMAdapter
    raise AttributeError(
        f"module 'context_driven_llm_scheduler.adapters' has no attribute '{name}'"
    )
