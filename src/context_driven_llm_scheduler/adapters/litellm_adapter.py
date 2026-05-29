"""LiteLLM-backed model adapter (the ``litellm`` extra).

Implements :class:`~context_driven_llm_scheduler.adapters.base.ModelAdapter` against LiteLLM, so
a pulse can run on any of its 100+ providers by changing the model string.
Adds :meth:`propose_memory_ops`, a convenience that asks the model to emit
memory operations via :data:`~context_driven_llm_scheduler.core.memory.MEMORY_TOOL_SCHEMA` and
returns them ready for :meth:`~context_driven_llm_scheduler.core.pulse.Pulse.persist`.
"""

import json
from typing import Any

from context_driven_llm_scheduler.core.memory import MEMORY_TOOL_SCHEMA


class LiteLLMAdapter:
    """Drive a pulse's model calls through LiteLLM.

    Construction sets call defaults once (timeout, retries, and anything else
    LiteLLM accepts) so the common case is config, not per-call discipline.
    The raw LiteLLM defaults are a 600s timeout and zero retries — a recurring
    pulse holds its store transaction across the model call, so a finite
    timeout here is what bounds how long that lock can be held. Per-call
    ``kwargs`` override these defaults; pass ``key=None`` to drop one.

    Attributes:
        model: The LiteLLM model string (e.g. ``"anthropic/claude-..."`` or
            ``"gpt-4o"``).
    """

    model: str
    _defaults: dict[str, Any]

    def __init__(
        self,
        model: str,
        *,
        timeout: float | None = 60.0,
        num_retries: int | None = 2,
        **defaults: Any,
    ) -> None:
        """Initialize the adapter for ``model`` with sensible call defaults.

        Args:
            model: A LiteLLM model identifier.
            timeout: Per-call timeout in seconds, applied to every completion.
                ``None`` drops it (falling back to LiteLLM's own default).
            num_retries: How many times LiteLLM retries a failed call, with
                its native backoff. ``None`` drops it.
            **defaults: Any other ``litellm.completion`` arguments to apply on
                every call (e.g. ``max_tokens``, ``temperature``,
                ``fallbacks``). ``None`` values are dropped.
        """
        self.model = model
        self._defaults = {
            "timeout": timeout,
            "num_retries": num_retries,
            **defaults,
        }

    def _call_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Merge per-call ``kwargs`` over the construction-time defaults.

        Args:
            kwargs: Per-call overrides.

        Returns:
            The merged kwargs with any ``None`` values dropped, so a default
            or override of ``None`` removes that argument entirely.
        """
        merged = {**self._defaults, **kwargs}
        return {key: value for key, value in merged.items()
                if value is not None}

    def complete(self, prompt: str, **kwargs: object) -> str:
        """Complete ``prompt`` as a single user message.

        Args:
            prompt: The assembled prompt.
            **kwargs: Extra arguments forwarded to ``litellm.completion``,
                overriding the construction-time defaults.

        Returns:
            The assistant message content.
        """
        import litellm

        response = litellm.completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **self._call_kwargs(kwargs),
        )
        return response.choices[0].message.content or ""

    def count_tokens(self, text: str) -> int:
        """Count tokens in ``text`` using LiteLLM's tokenizer for the model.

        Args:
            text: The text to measure.

        Returns:
            The token count.
        """
        import litellm

        return litellm.token_counter(
            model=self.model,
            messages=[{"role": "user", "content": text}],
        )

    def propose_memory_ops(
        self, prompt: str, **kwargs: object
    ) -> list[dict[str, Any]]:
        """Ask the model to emit memory operations for ``prompt``.

        Calls the model with the ``update_memory`` tool and parses the
        resulting ``operations`` array. The list is ready to hand to
        :meth:`~context_driven_llm_scheduler.core.pulse.Pulse.apply`.

        Args:
            prompt: The assembled prompt (e.g. from ``Pulse.recall``).
            **kwargs: Extra arguments forwarded to ``litellm.completion``,
                overriding the construction-time defaults.

        Returns:
            The proposed memory operations, or an empty list if the model
            chose not to record anything.
        """
        import litellm

        response = litellm.completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            tools=MEMORY_TOOL_SCHEMA,
            **self._call_kwargs(kwargs),
        )
        tool_calls = response.choices[0].message.tool_calls or []
        ops: list[dict[str, Any]] = []
        for call in tool_calls:
            if call.function.name != "update_memory":
                continue
            payload = json.loads(call.function.arguments)
            ops.extend(payload.get("operations", []))
        return ops
