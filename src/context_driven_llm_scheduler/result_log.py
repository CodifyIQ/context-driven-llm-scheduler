"""Append-only markdown run log: results plus the context that produced them.

A pulse's JSON context is its *machine* state — what :meth:`recall` reads back
next run. A :class:`ResultLog` is the *human* artifact alongside it: one
markdown file per pulse id, appended once per trigger. Each entry carries the
run's result, the context the model was fed, and the memory changes persisted
for next time, so a single run is auditable and reproducible from the file
alone.

The log is a separate sink from the :class:`~context_driven_llm_scheduler.core.store.ContextStore`
— it never holds machine state — so it stays purely a readable record and a
missing or hand-edited log can never corrupt a pulse. Wire one into
:class:`~context_driven_llm_scheduler.core.manager.PulseManager` to have entries written
automatically inside each trigger.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import portalocker

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")
_RECENT_NOTES = 5


class ResultLog:
    """Persist one append-only markdown run log per pulse id.

    Appends are serialized with an exclusive ``portalocker`` lock on a per-key
    lock file, so concurrent triggers of the same pulse never interleave a
    half-written entry — matching the concurrency guarantee of
    :class:`~context_driven_llm_scheduler.stores.file.FileStore`.

    Attributes:
        root: Directory that holds the ``<key>.md`` and ``<key>.lock`` files.
    """

    root: Path

    def __init__(self, root: str | os.PathLike[str]) -> None:
        """Initialize the log directory, creating ``root`` if needed.

        Args:
            root: Directory in which per-pulse markdown logs are stored.
        """
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_key(self, key: str) -> str:
        """Return a filesystem-safe stem for ``key``.

        Args:
            key: The raw pulse id.

        Returns:
            A sanitized stem with unsafe characters replaced by ``_``.
        """
        return _UNSAFE_CHARS.sub("_", key)

    def path(self, key: str) -> Path:
        """Return the markdown log path for ``key``.

        Args:
            key: The pulse id.

        Returns:
            The ``<key>.md`` path under :attr:`root`.
        """
        return self.root / f"{self._safe_key(key)}.md"

    def read(self, key: str) -> str:
        """Return the full markdown log for ``key`` (empty string if none).

        Args:
            key: The pulse id.

        Returns:
            The log contents, or ``""`` if nothing has been logged yet.
        """
        path = self.path(key)
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def append_entry(self, key: str, markdown: str) -> None:
        """Append a rendered ``markdown`` entry to ``key``'s log, locked.

        Args:
            key: The pulse id whose log to append to.
            markdown: The fully rendered entry to append.
        """
        lock = self.root / f"{self._safe_key(key)}.lock"
        with portalocker.Lock(str(lock), mode="w", flags=portalocker.LOCK_EX):
            with self.path(key).open("a", encoding="utf-8") as handle:
                handle.write(markdown)

    def record(
        self,
        key: str,
        *,
        trigger_time: datetime,
        trigger_count: int | None,
        status: str,
        model: str | None = None,
        result: dict[str, Any] | None = None,
        carried_facts: dict[str, Any] | None = None,
        carried_notes: list[str] | None = None,
        changes: list[dict[str, Any]] | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        """Render one run entry and append it to ``key``'s log.

        Args:
            key: The pulse id.
            trigger_time: When the trigger fired.
            trigger_count: The pulse's run number, shown in the header.
            status: ``"ok"`` or ``"error"``.
            model: The pulse's configured model string, if any.
            result: The result recorded via
                :meth:`~context_driven_llm_scheduler.core.pulse.Pulse.record_result`.
            carried_facts: Facts the model was fed this run.
            carried_notes: Notes the model was fed this run.
            changes: The memory changeset persisted for next run.
            error: The recorded error, for ``status == "error"`` entries.
        """
        self.append_entry(
            key,
            render_entry(
                trigger_time=trigger_time,
                trigger_count=trigger_count,
                status=status,
                model=model,
                result=result,
                carried_facts=carried_facts,
                carried_notes=carried_notes,
                changes=changes,
                error=error,
            ),
        )


def render_entry(
    *,
    trigger_time: datetime,
    trigger_count: int | None,
    status: str,
    model: str | None = None,
    result: dict[str, Any] | None = None,
    carried_facts: dict[str, Any] | None = None,
    carried_notes: list[str] | None = None,
    changes: list[dict[str, Any]] | None = None,
    error: dict[str, Any] | None = None,
) -> str:
    """Render a single run-log entry as a markdown block.

    The entry leads with a status header, then the result, the context fed to
    the run, and the memory changes persisted for next run — so the entry is
    self-contained: what was remembered, what the run produced, and how state
    moved.

    Args:
        trigger_time: When the trigger fired.
        trigger_count: The pulse's run number.
        status: ``"ok"`` or ``"error"``.
        model: The pulse's configured model string, if any.
        result: The recorded result (``body`` plus optional scalar fields).
        carried_facts: Facts the model was fed this run.
        carried_notes: Notes the model was fed this run.
        changes: The memory changeset persisted for next run.
        error: The recorded error, for ``status == "error"`` entries.

    Returns:
        The rendered entry, terminated by a blank line so successive entries
        stay separated.
    """
    run = f"run #{trigger_count}" if trigger_count is not None else "run"
    header = f"## {trigger_time.isoformat()} · {run} · {status}"
    lines = [header, ""]

    detail = {"model": model} if model else {}
    if result:
        detail.update(
            {key: value for key, value in result.items() if key != "body"}
        )
    for field_name, value in detail.items():
        lines.append(f"- {field_name}: {value}")
    if detail:
        lines.append("")

    if error:
        lines.append("**Error**")
        lines.append("")
        lines.append(f"{error.get('type', 'Error')}: {error.get('message', '')}")
        lines.append("")
    elif result and result.get("body"):
        lines.append("**Result**")
        lines.append("")
        lines.append(str(result["body"]))
        lines.append("")

    if carried_facts or carried_notes:
        lines.append("**Carried context (fed to this run)**")
        lines.append("")
        if carried_facts:
            lines.append(f"- facts: {carried_facts}")
        notes = carried_notes or []
        if len(notes) > _RECENT_NOTES:
            lines.append(
                f"- _… {len(notes) - _RECENT_NOTES} older note(s) elided; "
                f"showing the {_RECENT_NOTES} most recent of {len(notes)}_"
            )
        for note in notes[-_RECENT_NOTES:]:
            lines.append(f"- note: {note}")
        lines.append("")

    if changes:
        lines.append("**Memory changes (persisted for next run)**")
        lines.append("")
        for change in changes:
            lines.append(f"- {_describe_change(change)}")
        lines.append("")

    return "\n".join(lines) + "\n"


def _describe_change(change: dict[str, Any]) -> str:
    """Render one memory changeset record as a compact human line.

    Args:
        change: A single record from
            :func:`~context_driven_llm_scheduler.core.memory.apply_ops`.

    Returns:
        A one-line description, e.g. ``set last_digest = 2026-06-02``.
    """
    op = change.get("op")
    if op == "note":
        return f"note: {change.get('text')}"
    if op == "seen":
        state = "new" if change.get("added") else "already seen"
        return f"seen {change.get('field')}/{change.get('id')} ({state})"
    if op == "throttle":
        return f"throttle {change.get('field')} stamped at {change.get('at')}"
    if op == "set":
        return f"set {change.get('key')} = {change.get('value')}"
    if op == "forget":
        return f"forget {change.get('key')}"
    return str(change)
