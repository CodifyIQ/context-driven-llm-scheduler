"""Abstract persistence layer for pulse contexts."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager

from context_driven_llm_scheduler.core.types import Context


class ContextStore(ABC):
    """Pluggable backend that persists one context dict per pulse id.

    Implementations must guarantee that everything done inside a
    :meth:`transaction` block is atomic with respect to other processes or
    threads operating on the same key, so a load → mutate → save cycle cannot
    lose updates under concurrency.
    """

    @abstractmethod
    def load(self, key: str) -> Context:
        """Load the stored context for ``key``.

        Args:
            key: The pulse id whose context should be loaded.

        Returns:
            The stored context, or an empty dict if nothing is stored yet.

        Raises:
            StoreError: If the backend fails to read or decode the context.
        """

    @abstractmethod
    def save(self, key: str, context: Context) -> None:
        """Persist ``context`` for ``key``, replacing any prior value.

        Args:
            key: The pulse id whose context should be saved.
            context: The JSON-serializable context dict to persist.

        Raises:
            StoreError: If the backend fails to encode or write the context.
        """

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove any stored context for ``key``.

        Args:
            key: The pulse id whose context should be removed. Deleting a
                missing key is a no-op.
        """

    @contextmanager
    def transaction(self, key: str) -> Iterator[None]:
        """Hold an exclusive lock on ``key`` for a read-modify-write cycle.

        The default implementation provides no isolation; concurrency-safe
        backends override it. Used by the manager to wrap the whole
        load → handler → save cycle.

        Args:
            key: The pulse id to lock for the duration of the block.

        Yields:
            None.
        """
        yield
