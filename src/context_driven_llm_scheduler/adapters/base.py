"""The ModelAdapter contract.

The membrane needs only two things from a model: turn a prompt into text, and
count tokens for context budgeting. Anything that provides those two methods is
a valid adapter — LiteLLM, a raw provider SDK, or an in-house gateway — so the
core never depends on any particular model library.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ModelAdapter(Protocol):
    """Minimal interface context_driven_llm_scheduler needs to drive a model.

    Implement these two methods against any backend. See ``LiteLLMAdapter`` for
    a reference implementation covering 100+ providers.
    """

    def complete(self, prompt: str, **kwargs: object) -> str:
        """Return the model's text completion for ``prompt``.

        Args:
            prompt: The fully assembled prompt (e.g. from
                :meth:`~context_driven_llm_scheduler.core.pulse.Pulse.recall`).
            **kwargs: Backend-specific options forwarded to the model.

        Returns:
            The model's response text.
        """
        ...

    def count_tokens(self, text: str) -> int:
        """Return the token count of ``text`` for context budgeting.

        Args:
            text: The text to measure.

        Returns:
            The number of tokens.
        """
        ...
