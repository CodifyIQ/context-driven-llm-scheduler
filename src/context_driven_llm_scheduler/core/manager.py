"""The PulseManager: register handlers and drive the trigger cycle."""

import logging
from collections.abc import Callable
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from context_driven_llm_scheduler.result_log import ResultLog

# Separator that joins a pulse id and an instance into one store key. Chosen so
# that under a ``ResultLog`` (which replaces non-``[A-Za-z0-9._-]`` characters
# with ``_``) a partitioned key renders as ``<id>__<instance>.md``.
_INSTANCE_SEPARATOR = "::"


def _store_key(pulse_id: str, instance: str | None) -> str:
    """Compose the effective store key for a pulse id and optional instance.

    Instance partitioning lets one pulse definition run across many isolated
    state partitions. The manager owns the composition so callers address a
    ``(pulse_id, instance)`` pair and never construct the composite key
    themselves; the store, result log, and events see the composed key.

    Args:
        pulse_id: The pulse's registration id.
        instance: The partition to isolate, or None for the unpartitioned key.

    Returns:
        ``pulse_id`` unchanged when ``instance`` is None (so the default path is
        byte-for-byte identical to an unpartitioned pulse), otherwise
        ``f"{pulse_id}{_INSTANCE_SEPARATOR}{instance}"``.

    Raises:
        ValueError: If a partitioned key would be ambiguous — either the
            ``instance`` or the ``pulse_id`` contains the reserved separator, so
            two distinct ``(pulse_id, instance)`` pairs could collapse onto one
            key and silently share state. Rejected up front rather than parsed
            into something subtly wrong. Unpartitioned keys are returned as-is
            and never validated, keeping ``instance=None`` unchanged.
    """
    if instance is None:
        return pulse_id
    if _INSTANCE_SEPARATOR in pulse_id or _INSTANCE_SEPARATOR in instance:
        raise ValueError(
            f"pulse id and instance must not contain the reserved instance "
            f"separator {_INSTANCE_SEPARATOR!r}, which would make the partition "
            f"key ambiguous: pulse_id={pulse_id!r}, instance={instance!r}"
        )
    return f"{pulse_id}{_INSTANCE_SEPARATOR}{instance}"


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
        result_log: "ResultLog | None" = None,
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
                the memory ``changes``, ``trigger_skipped``, ``trigger_error``).
                Route it to your own logging/metrics/tracing; context_driven_llm_scheduler owns
                no sink. The callback runs inside the trigger transaction, so
                keep it cheap and non-blocking — an exception from it is logged
                and swallowed so observability never breaks a pulse.
            result_log: Optional markdown run log. When set, each trigger
                appends an entry (result, carried context, memory changes) for
                that pulse. The log is a human/audit artifact, separate from
                the context store.
        """
        self._store = store
        self.swallow_errors = swallow_errors
        self._logger = logger
        self._on_event = on_event
        self._result_log = result_log
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
        self,
        pulse_id: str,
        extra: dict | None = None,
        *,
        instance: str | None = None,
        coalesce_window: float | None = None,
    ) -> Context:
        """Run one proactive cycle for ``pulse_id``.

        Loads the context, stamps trigger metadata, runs the handler, and
        persists the result — all under an exclusive store transaction so
        concurrent triggers of the same id cannot lose updates.

        With ``coalesce_window`` set, a trigger whose last run was fewer than
        that many seconds ago is skipped without running the handler. Because
        the check and the timestamp stamp both happen inside the per-pulse
        transaction, this collapses a herd of near-simultaneous triggers —
        e.g. one scheduler per web worker firing the same schedule — into a
        single run: the first stamps the time, the rest acquire the lock,
        find the run too recent, and no-op. It needs no leader election or
        external coordination beyond the store the manager already owns.

        With ``instance`` set, the same pulse id runs against an isolated state
        partition: the effective store key becomes ``(pulse_id, instance)``, so
        one definition can serve many independent subjects (tenants, teams,
        accounts) without sharing memory. Coalescing is per-instance because
        the window reads the partition's own context. ``instance=None`` is
        byte-for-byte identical to the unpartitioned pulse.

        Args:
            pulse_id: The id of a registered pulse.
            extra: Optional per-trigger payload passed straight to the handler
                (not persisted).
            instance: Optional partition to isolate this run's state under, or
                None for the unpartitioned pulse.
            coalesce_window: If set, skip when the previous run was within this
                many seconds, returning the stored context unchanged.

        Returns:
            The context as persisted after this trigger (or the unchanged
            stored context when the trigger was coalesced away).

        Raises:
            PulseNotRegisteredError: If no handler is registered for the id.
            ValueError: If ``instance`` or ``pulse_id`` contains the reserved
                partition separator ``"::"``.
            Exception: Whatever the handler raised, unless ``swallow_errors``.
        """
        if pulse_id not in self._pulse_handlers:
            raise PulseNotRegisteredError(
                f"No handler registered for pulse '{pulse_id}'"
            )
        return self._run_cycle(
            pulse_id,
            self._definitions.get(pulse_id),
            self._pulse_handlers[pulse_id],
            extra,
            instance=instance,
            coalesce_window=coalesce_window,
        )

    def trigger_definition(
        self,
        definition: PulseDefinition,
        handler: PulseHandler,
        extra: dict | None = None,
        *,
        instance: str | None = None,
        coalesce_window: float | None = None,
    ) -> Context:
        """Run one proactive cycle for a definition built at call time.

        Like :meth:`trigger`, but the definition and handler are supplied
        directly instead of resolved from the registry, so a ``pulse.md`` body
        sourced at runtime — a database row, remote config, an API response —
        can run without :meth:`add_definition` / :meth:`pulse`. Nothing is
        registered as a side effect; the call is self-contained.

        The run is keyed by ``definition.id`` (plus ``instance``), so pairing
        this with ``instance`` is the intended way to fan one runtime-sourced
        definition across many isolated partitions.

        Args:
            definition: The pulse definition to run.
            handler: The handler to invoke for this run.
            extra: Optional per-trigger payload passed straight to the handler
                (not persisted).
            instance: Optional partition to isolate this run's state under, or
                None for the unpartitioned pulse.
            coalesce_window: If set, skip when the previous run was within this
                many seconds, returning the stored context unchanged.

        Returns:
            The context as persisted after this trigger (or the unchanged
            stored context when the trigger was coalesced away).

        Raises:
            ValueError: If ``instance`` or ``definition.id`` contains the
                reserved partition separator ``"::"``.
            Exception: Whatever the handler raised, unless ``swallow_errors``.
        """
        return self._run_cycle(
            definition.id,
            definition,
            handler,
            extra,
            instance=instance,
            coalesce_window=coalesce_window,
        )

    def _run_cycle(
        self,
        pulse_id: str,
        definition: PulseDefinition | None,
        handler: PulseHandler,
        extra: dict | None,
        *,
        instance: str | None,
        coalesce_window: float | None,
    ) -> Context:
        """Run the load → handler → persist → save cycle for one trigger.

        Shared by :meth:`trigger` (registry-resolved) and
        :meth:`trigger_definition` (call-time), keyed by the effective
        ``(pulse_id, instance)`` store key.

        Args:
            pulse_id: The pulse's registration id, used for events and the
                error log message.
            definition: The definition to bind, or None if the id has a handler
                but no loaded definition (surfaces as a run error, as before).
            handler: The handler to invoke.
            extra: The per-trigger payload passed to the handler.
            instance: The partition to isolate under, or None.
            coalesce_window: The de-duplication window, or None.

        Returns:
            The persisted context (or the unchanged stored context when
            coalesced away).

        Raises:
            ValueError: If ``instance`` or ``pulse_id`` contains the reserved
                partition separator ``"::"`` (raised before the transaction, so
                it is never suppressed by ``swallow_errors``).
            Exception: Whatever the handler raised, unless ``swallow_errors``.
        """
        store_key = _store_key(pulse_id, instance)

        with self._store.transaction(store_key):
            context = self._store.load(store_key) or {}

            trigger_time = utcnow()
            if self._is_too_soon(context, trigger_time, coalesce_window):
                self._emit({
                    "event": "trigger_skipped",
                    "pulse_id": pulse_id,
                    "instance": instance,
                    "at": trigger_time.isoformat(),
                    "reason": "coalesced",
                })
                return context

            context[LAST_TRIGGERED] = trigger_time.isoformat()
            context[TRIGGER_COUNT] = context.get(TRIGGER_COUNT, 0) + 1
            self._emit({
                "event": "trigger_start",
                "pulse_id": pulse_id,
                "instance": instance,
                "at": trigger_time.isoformat(),
            })

            try:
                pulse, changes = self._run_pulse(
                    pulse_id, definition, handler, context, trigger_time, extra
                )
                context = pulse.context
                context[LAST_ERROR] = None
            except Exception as exc:
                error = {
                    "message": str(exc),
                    "type": type(exc).__name__,
                    "at": trigger_time.isoformat(),
                }
                context[LAST_ERROR] = error
                context[ERROR_COUNT] = context.get(ERROR_COUNT, 0) + 1
                self._store.save(store_key, context)
                self._record_result(
                    store_key, definition, context, trigger_time, "error",
                    error=error,
                )
                if self._logger is not None:
                    self._logger.warning(
                        "Pulse '%s' handler failed: %s", pulse_id, exc
                    )
                self._emit({
                    "event": "trigger_error",
                    "pulse_id": pulse_id,
                    "instance": instance,
                    "error": error,
                })
                if not self.swallow_errors:
                    raise
                return context

            self._store.save(store_key, context)
            self._record_result(
                store_key, definition, context, trigger_time, "ok",
                pulse=pulse, changes=changes,
            )
            self._emit({
                "event": "trigger_end",
                "pulse_id": pulse_id,
                "instance": instance,
                "at": trigger_time.isoformat(),
                "trigger_count": context.get(TRIGGER_COUNT),
                "changes": changes,
            })
            return context

    @staticmethod
    def _is_too_soon(
        context: Context,
        trigger_time: datetime,
        coalesce_window: float | None,
    ) -> bool:
        """Return whether ``coalesce_window`` should skip this trigger.

        Args:
            context: The loaded context, read for ``LAST_TRIGGERED``.
            trigger_time: The current trigger time.
            coalesce_window: The minimum seconds between runs, or None to
                never coalesce.

        Returns:
            True if a previous run is recent enough to skip this one.
        """
        if not coalesce_window:
            return False
        last_iso = context.get(LAST_TRIGGERED)
        if last_iso is None:
            return False
        elapsed = (trigger_time - datetime.fromisoformat(last_iso)).total_seconds()
        return elapsed < coalesce_window

    def _run_pulse(
        self,
        pulse_id: str,
        definition: PulseDefinition | None,
        handler: PulseHandler,
        context: Context,
        trigger_time: datetime,
        extra: dict | None,
    ) -> tuple[Pulse, list[dict[str, Any]]]:
        """Run a markdown pulse: bind context, call handler, apply ops.

        Args:
            pulse_id: The pulse id being triggered, for the error message.
            definition: The definition to bind, or None if none is available.
            handler: The handler to invoke.
            context: The loaded context for this trigger.
            trigger_time: The trigger time.
            extra: The per-trigger payload passed to the handler.

        Returns:
            A ``(pulse, changes)`` tuple: the bound pulse after the handler ran
            (carrying any recorded result and the carried-context snapshot),
            and the memory changeset from applying its ops (empty if the
            handler returned ``None``).

        Raises:
            PulseNotRegisteredError: If no definition is available for the id.
        """
        if definition is None:
            raise PulseNotRegisteredError(
                f"No pulse definition loaded for '{pulse_id}'"
            )
        pulse = Pulse(definition, context, trigger_time)
        ops = handler(pulse, extra)
        changes = pulse.persist(ops) if ops is not None else []
        return pulse, changes

    def _record_result(
        self,
        log_key: str,
        definition: PulseDefinition | None,
        context: Context,
        trigger_time: datetime,
        status: str,
        *,
        pulse: Pulse | None = None,
        changes: list[dict[str, Any]] | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        """Append a run-log entry when a result log is configured.

        The write is best-effort: the run log is a human/audit artifact and can
        never be allowed to change a pulse's outcome. A failure here is logged
        and swallowed so it neither breaks an otherwise-successful pulse nor
        masks the handler error on the failure path (where this runs before the
        original exception is re-raised).

        Args:
            log_key: The effective store key, so a partitioned pulse gets its
                own per-instance log file.
            definition: The bound definition, read for the model string, or
                None if none is available.
            context: The context after this trigger, read for the run number.
            trigger_time: The trigger time.
            status: ``"ok"`` or ``"error"``.
            pulse: The bound pulse, present on the success path so the result
                and carried context can be rendered.
            changes: The memory changeset, present on the success path.
            error: The recorded error, present on the error path.
        """
        if self._result_log is None:
            return
        try:
            self._result_log.record(
                log_key,
                trigger_time=trigger_time,
                trigger_count=context.get(TRIGGER_COUNT),
                status=status,
                model=definition.model if definition is not None else None,
                result=pulse.result if pulse is not None else None,
                carried_facts=pulse.carried_facts if pulse is not None else None,
                carried_notes=pulse.carried_notes if pulse is not None else None,
                changes=changes,
                error=error,
            )
        except Exception as exc:  # the audit log must not break the pulse
            if self._logger is not None:
                self._logger.warning(
                    "Result log write failed for pulse '%s': %s", log_key, exc
                )

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
