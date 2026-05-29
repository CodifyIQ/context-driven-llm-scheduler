"""Exception hierarchy for context_driven_llm_scheduler."""


class ContextDrivenLLMSchedulerError(Exception):
    """Base class for all context_driven_llm_scheduler errors."""


class PulseNotRegisteredError(ContextDrivenLLMSchedulerError):
    """Raised when triggering a pulse id that has no registered handler."""


class StoreError(ContextDrivenLLMSchedulerError):
    """Raised when a context store fails to load or persist context."""
