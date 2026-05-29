"""The PulseManager: register handlers and drive the trigger cycle."""

import logging
from collections.abc import Callable
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Any

from context_driven_llm_scheduler.core.exceptions import (
    PulseNotRegisteredError,
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
from context_driven_llm_scheduler.util import utcnow


class PulseManager:
    """Registry of pulse handlers wired to a single context store.

    A *pulse* is a named unit of proactive, memoryful work. Each wake-up
    calls :meth:`trigger`, which loads the pulse's context, runs the handler,
    and persists the result — so handlers carry state across wake-ups without
    any external bookkeeping. The concept is inspired by OpenClaw's Heartbeat;
    we call ours a Pulse.

    Attributes:
        swallow_errors: When True, handler exceptions are recorded in context
            but not re-raised.
    """

    swallow_errors: bool

    def __init__(
        self,
        store: ContextStore,
        *,
        swallow_errors: bool = False,
        logger: logging.Logger | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize the manager.

        Args:
            store: The backend used to load and persist pulse contexts.
            swallow_errors: If True, handler exceptions are persisted to
                context and suppressed instead of re-raised.
            logger: Optional logger used to warn on handler failures. No
                logging occurs when this is None.
            on_event: Optional callback fired with a structured event dict at
                each trigger boundary (``trigger_start``, ``trigger_end`` with
                the memory ``changes``, ``trigger_error``). Route it to your
                own logging/metrics/tracing; context_driven_llm_scheduler owns no sink. The
                callback runs inside the trigger transaction, so keep it cheap
                and non-blocking — an exception from it is logged and swallowed
                so observability never breaks a pulse.
        """
        self._store = store
        self.swallow_errors = swallow_errors
        self._logger = logger
        self._on_event = on_event
        self._definitions: dict[str, PulseDefinition] = {}
        self._pulse_handlers: dict[str, PulseHandler] = {}

    @classmethod
    def from_dir(
        cls,
        directory: str | PathLike[str],
        store: ContextStore,
        **kwargs: object,
    ) -> "PulseManager":
        """Build a manager and load every ``*.md`` pulse in ``directory``.

        Each markdown file is parsed into a :class:`PulseDefinition` and
        registered by its frontmatter ``id``. Attach handlers afterwards with
        :meth:`pulse`.

        Args:
            directory: Folder containing ``pulse.md`` files.
            store: The backend used to load and persist pulse contexts.
            **kwargs: Forwarded to :class:`PulseManager` (e.g.
                ``swallow_errors``, ``logger``).

        Returns:
            A manager with all definitions loaded.
        """
        manager = cls(store, **kwargs)  # type: ignore[arg-type]
        for path in sorted(Path(directory).glob("*.md")):
            manager.add_definition(PulseDefinition.from_file(path))
        return manager

    def add_definition(self, definition: PulseDefinition) -> None:
        """Register a markdown pulse definition.

        Args:
            definition: The parsed pulse definition to register.
        """
        self._definitions[definition.id] = definition

    def pulse(
        self, definition: "PulseDefinition | str"
    ) -> Callable[[PulseHandler], PulseHandler]:
        """Register a handler for a markdown pulse.

        Args:
            definition: A :class:`PulseDefinition` to register, or the id of
                one already loaded (e.g. via :meth:`from_dir`).

        Returns:
            A decorator that registers and returns the handler unchanged.

        Raises:
            PulseNotRegisteredError: If an id is given for an unknown pulse.
        """
        if isinstance(definition, PulseDefinition):
            self.add_definition(definition)
            pulse_id = definition.id
        else:
            if definition not in self._definitions:
                raise PulseNotRegisteredError(
                    f"No pulse definition loaded for '{definition}'"
                )
            pulse_id = definition

        def decorator(handler: PulseHandler) -> PulseHandler:
            """Register ``handler`` for the resolved pulse id.

            Args:
                handler: The pulse handler to register.

            Returns:
                The handler unchanged, so the decorator is transparent.
            """
            self._pulse_handlers[pulse_id] = handler
            return handler

        return decorator

    def trigger(
        self, pulse_id: str, extra: dict | None = None
    ) -> Context:
        """Run one proactive cycle for ``pulse_id``.

        Loads the context, stamps trigger metadata, runs the handler, and
        persists the result — all under an exclusive store transaction so
        concurrent triggers of the same id cannot lose updates.

        Args:
            pulse_id: The id of a registered pulse.
            extra: Optional per-trigger payload passed straight to the handler
                (not persisted).

        Returns:
            The context as persisted after this trigger.

        Raises:
            PulseNotRegisteredError: If no handler is registered for the id.
            Exception: Whatever the handler raised, unless ``swallow_errors``.
        """
        if pulse_id not in self._pulse_handlers:
            raise PulseNotRegisteredError(
                f"No handler registered for pulse '{pulse_id}'"
            )

        with self._store.transaction(pulse_id):
            context = self._store.load(pulse_id) or {}

            trigger_time = utcnow()
            context[LAST_TRIGGERED] = trigger_time.isoformat()
            context[TRIGGER_COUNT] = context.get(TRIGGER_COUNT, 0) + 1
            self._emit({
                "event": "trigger_start",
                "pulse_id": pulse_id,
                "at": trigger_time.isoformat(),
            })

            try:
                context, changes = self._run_pulse(
                    pulse_id, context, trigger_time, extra
                )
                context[LAST_ERROR] = None
            except Exception as exc:
                error = {
                    "message": str(exc),
                    "type": type(exc).__name__,
                    "at": trigger_time.isoformat(),
                }
                context[LAST_ERROR] = error
                context[ERROR_COUNT] = context.get(ERROR_COUNT, 0) + 1
                self._store.save(pulse_id, context)
                if self._logger is not None:
                    self._logger.warning(
                        "Pulse '%s' handler failed: %s", pulse_id, exc
                    )
                self._emit({
                    "event": "trigger_error",
                    "pulse_id": pulse_id,
                    "error": error,
                })
                if not self.swallow_errors:
                    raise
                return context

            self._store.save(pulse_id, context)
            self._emit({
                "event": "trigger_end",
                "pulse_id": pulse_id,
                "at": trigger_time.isoformat(),
                "trigger_count": context.get(TRIGGER_COUNT),
                "changes": changes,
            })
            return context

    def _run_pulse(
        self,
        pulse_id: str,
        context: Context,
        trigger_time: datetime,
        extra: dict | None,
    ) -> tuple[Context, list[dict[str, Any]]]:
        """Run a markdown pulse: bind context, call handler, apply ops.

        Args:
            pulse_id: The pulse id being triggered.
            context: The loaded context for this trigger.
            trigger_time: The trigger time.
            extra: The per-trigger payload passed to the handler.

        Returns:
            A ``(context, changes)`` tuple: the pulse context after the handler
            ran, and the memory changeset from applying its ops (empty if the
            handler returned ``None``).

        Raises:
            PulseNotRegisteredError: If no definition is loaded for the id.
        """
        definition = self._definitions.get(pulse_id)
        if definition is None:
            raise PulseNotRegisteredError(
                f"No pulse definition loaded for '{pulse_id}'"
            )
        pulse = Pulse(definition, context, trigger_time)
        ops = self._pulse_handlers[pulse_id](pulse, extra)
        changes = pulse.persist(ops) if ops is not None else []
        return pulse.context, changes

    def _emit(self, event: dict[str, Any]) -> None:
        """Fire the ``on_event`` callback, never letting it break a trigger.

        Args:
            event: The structured event dict to deliver.
        """
        if self._on_event is None:
            return
        try:
            self._on_event(event)
        except Exception as exc:  # observability must not break the pulse
            if self._logger is not None:
                self._logger.warning(
                    "on_event callback raised: %s", exc
                )
