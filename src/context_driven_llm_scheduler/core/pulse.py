"""Markdown-defined pulses: instructions in, memory out.

A ``pulse.md`` file *is* the pulse: YAML-ish frontmatter for the schedule and
memory policy, and a plain-language body that tells the model what to do each
wake-up. :class:`PulseDefinition` parses that file; :class:`Pulse` binds a
definition to a live context for one trigger and exposes the two operations
that make a pulse contextual:

* :meth:`Pulse.recall` — assemble the standing instructions plus a budgeted
  view of memory into the prompt you feed the model (read memory *in*).
* :meth:`Pulse.persist` — fold the model's memory operations back into stored
  state (write memory *out*).

The model call between them is yours; context_driven_llm_scheduler owns only the membrane.
"""

from dataclasses import dataclass, field
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any

from context_driven_llm_scheduler.core.memory import Memory, apply_ops
from context_driven_llm_scheduler.core.types import Context

if TYPE_CHECKING:
    from context_driven_llm_scheduler.adapters.base import ModelAdapter

_RESERVED_MEMORY_KEY = "memory"


@dataclass
class PulseDefinition:
    """The static definition of a pulse, parsed from a ``pulse.md`` file.

    Attributes:
        id: Unique pulse id (frontmatter ``id``).
        instructions: The markdown body — the standing prompt for the pulse.
        schedule: Optional crontab expression (frontmatter ``schedule``), used
            by schedulers; the core never reads it.
        model: Optional model hint (frontmatter ``model``) for the adapter.
        throttles: Field name to minimum seconds between actions, parsed from
            the ``throttle`` map (e.g. ``{ notify: 1h }`` → ``{"notify":
            3600.0}``).
        keep: Field name to retention cap, parsed from the ``keep`` map
            (``notes`` trims the note log, ``seen`` caps de-dup sets).
    """

    id: str
    instructions: str
    schedule: str | None = None
    model: str | None = None
    throttles: dict[str, float] = field(default_factory=dict)
    keep: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_markdown(
        cls, text: str, *, default_id: str | None = None
    ) -> "PulseDefinition":
        """Parse a pulse definition from markdown text.

        Frontmatter is optional. A file may be pure prose — its whole body is
        the standing instruction — in which case ``default_id`` supplies the
        id (the caller derives one, e.g. from the filename). Frontmatter is
        only needed when a file wants to carry its own id or policy overrides.

        Args:
            text: The full markdown contents.
            default_id: Fallback id used when the frontmatter has none, e.g.
                the filename stem. :meth:`from_file` passes this automatically.

        Returns:
            The parsed definition.

        Raises:
            ValueError: If no ``id`` is given in frontmatter and no
                ``default_id`` is supplied.
        """
        meta, body = _split_frontmatter(text)
        pulse_id = meta.get("id") or default_id
        if not pulse_id:
            raise ValueError(
                "pulse markdown has no 'id': add one to frontmatter or load "
                "it from a file so the id can be derived from the filename"
            )

        throttle_raw = meta.get("throttle", {})
        keep_raw = meta.get("keep", {})
        return cls(
            id=str(pulse_id),
            instructions=body.strip(),
            schedule=_as_str(meta.get("schedule")),
            model=_as_str(meta.get("model")),
            throttles={
                key: _parse_duration(value)
                for key, value in _as_map(throttle_raw).items()
            },
            keep={
                key: int(value)
                for key, value in _as_map(keep_raw).items()
            },
        )

    @classmethod
    def from_file(cls, path: str | PathLike[str]) -> "PulseDefinition":
        """Parse a pulse definition from a markdown file on disk.

        The filename stem is used as the id when the file has no frontmatter
        ``id``, so ``inbox-triage.md`` defines the pulse ``inbox-triage`` with
        no frontmatter at all.

        Args:
            path: Path to the markdown file.

        Returns:
            The parsed definition.
        """
        path = Path(path)
        return cls.from_markdown(
            path.read_text(encoding="utf-8"), default_id=path.stem
        )


class Pulse:
    """A pulse definition bound to a live context for one trigger.

    Constructed by :class:`~context_driven_llm_scheduler.core.manager.PulseManager` on each
    trigger and handed to the registered handler. The handler recalls a prompt,
    calls its model, and returns memory operations (or persists them directly).

    Attributes:
        definition: The static :class:`PulseDefinition`.
        context: The mutable pulse context for this trigger.
        trigger_time: When this trigger fired (timezone-aware UTC).
        memory: Typed view over the structured memory in ``context``.
        result: The run result recorded via :meth:`record_result`, or ``None``
            if the handler recorded nothing. Read by the manager to render a
            run-log entry.
    """

    def __init__(
        self,
        definition: PulseDefinition,
        context: Context,
        trigger_time: datetime,
    ) -> None:
        """Bind ``definition`` to ``context`` for a single trigger.

        Args:
            definition: The static pulse definition.
            context: The loaded pulse context (mutated in place).
            trigger_time: The trigger time.
        """
        self.definition = definition
        self.context = context
        self.trigger_time = trigger_time
        self.memory = Memory(context.setdefault(_RESERVED_MEMORY_KEY, {}))
        self.result: dict[str, Any] | None = None
        # Snapshot what fed this run, before persist mutates memory, so a
        # run-log entry can show the context the model actually saw.
        self._carried_facts: dict[str, Any] = dict(self.memory.facts)
        self._carried_notes: list[str] = list(self.memory.notes)

    @property
    def carried_facts(self) -> dict[str, Any]:
        """Snapshot of ``memory.facts`` as it was at the start of the trigger."""
        return self._carried_facts

    @property
    def carried_notes(self) -> list[str]:
        """Snapshot of ``memory.notes`` as it was at the start of the trigger."""
        return self._carried_notes

    def record_result(self, body: str, **fields: Any) -> None:
        """Record this run's result for the markdown run log.

        Call this from the handler with the human-readable outcome (e.g. the
        model's output) plus any structured detail worth logging. The manager
        renders it, alongside the carried context and memory changes, into the
        pulse's append-only ``ResultLog`` when one is configured. Recording a
        result is independent of memory: a pulse can log a result, persist
        memory ops, or both.

        Args:
            body: The result text to show under the entry's "Result" heading.
            **fields: Optional scalar detail (e.g. ``tokens=2140``,
                ``duration=1.8``) rendered as a bullet list in the entry.
        """
        self.result = {"body": body, **fields}

    def seconds_until_available(self, field_name: str) -> float:
        """Return seconds remaining before ``field_name`` may act again.

        Combines the throttle duration from the definition with the last
        stamped time in memory.

        Args:
            field_name: The throttle field to check.

        Returns:
            ``0.0`` if no throttle is configured, none has been stamped, or it
            has elapsed; otherwise the remaining seconds.
        """
        duration = self.definition.throttles.get(field_name)
        last_iso = self.memory.throttles.get(field_name)
        if duration is None or last_iso is None:
            return 0.0
        elapsed = (
            self.trigger_time - datetime.fromisoformat(last_iso)
        ).total_seconds()
        return max(0.0, duration - elapsed)

    def recall(
        self,
        *,
        extra: dict[str, Any] | None = None,
        adapter: "ModelAdapter | None" = None,
        max_tokens: int | None = None,
    ) -> str:
        """Read memory into a prompt: instructions + a budgeted view of memory.

        Without an adapter and budget, the recalled memory is whatever
        retention left in place. With both, the oldest notes are dropped from
        the *recalled* view (memory itself is untouched) until the prompt fits
        ``max_tokens``; the dropped count is stated in the prompt so nothing is
        silently lost. Use :meth:`compact` to fold old notes into a durable
        summary instead of dropping them at recall time.

        Args:
            extra: Optional per-trigger inputs to surface to the model.
            adapter: Model adapter used only to count tokens for budgeting.
            max_tokens: Token ceiling for the whole prompt. Ignored without an
                adapter.

        Returns:
            The assembled prompt string.
        """
        notes = list(self.memory.notes)
        dropped = 0
        text = self._compose(notes, dropped, extra)
        if adapter is not None and max_tokens is not None:
            while notes and adapter.count_tokens(text) > max_tokens:
                notes.pop(0)
                dropped += 1
                text = self._compose(notes, dropped, extra)
        return text

    def persist(self, ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Write memory operations back into stored state.

        Args:
            ops: Memory operations emitted by the model. See
                :data:`~context_driven_llm_scheduler.core.memory.MEMORY_TOOL_SCHEMA`.

        Returns:
            The changeset returned by
            :func:`~context_driven_llm_scheduler.core.memory.apply_ops` — one record per op
            describing what changed.

        Raises:
            ValueError: If any op is malformed or names an unknown operation.
        """
        return apply_ops(
            self.memory, ops, self.trigger_time, self.definition.keep
        )

    def compact_prompt(self, *, keep: int = 5) -> str | None:
        """Build the prompt that summarizes all but the newest ``keep`` notes.

        Compaction is split into this prompt-builder and :meth:`compact` so the
        model call stays yours — run it outside the trigger transaction, with
        your own timeout and retries — just as :meth:`recall` and
        :meth:`persist` keep the membrane's model call in the caller's hands.

        Args:
            keep: Number of most-recent notes to leave untouched.

        Returns:
            The summarization prompt, or ``None`` if there is nothing to
            compact (``keep`` or fewer notes).
        """
        notes = self.memory.notes
        if len(notes) <= keep:
            return None
        older = notes[:-keep] if keep else list(notes)
        older_text = "\n".join(f"- {note}" for note in older)
        return (
            "Summarize these notes into one concise paragraph, preserving "
            "facts, ids, and decisions:\n\n" + older_text
        )

    def compact(self, summary: str, *, keep: int = 5) -> None:
        """Fold ``summary`` over the older notes, keeping the newest ``keep``.

        Pass the model output for :meth:`compact_prompt` (with the same
        ``keep``). Replaces the older notes in memory with the single summary
        digest, durably shrinking memory rather than dropping context at recall
        time. A no-op when there is nothing to compact.

        Args:
            summary: The model-written digest of the older notes.
            keep: Number of most-recent notes to leave untouched.
        """
        notes = self.memory.notes
        if len(notes) <= keep:
            return
        older, recent = (notes[:-keep], notes[-keep:]) if keep \
            else (list(notes), [])
        notes[:] = [f"(summary of {len(older)} earlier notes) {summary}"]
        notes.extend(recent)

    def _compose(
        self,
        notes: list[str],
        dropped: int,
        extra: dict[str, Any] | None,
    ) -> str:
        """Build the prompt text from a snapshot of memory.

        Args:
            notes: The notes to include (already budget-trimmed).
            dropped: How many older notes were omitted, for disclosure.
            extra: Optional per-trigger inputs.

        Returns:
            The composed prompt.
        """
        sections = [self.definition.instructions, "## What you remember"]

        if dropped:
            sections.append(
                f"(omitting {dropped} older notes to fit context)"
            )
        if notes:
            sections.append(
                "Notes:\n"
                + "\n".join(f"- {note}" for note in notes)
            )
        elif not dropped:
            sections.append("Notes: (none yet)")

        if self.memory.facts:
            sections.append(
                "Facts:\n"
                + "\n".join(
                    f"- {key}: {value}"
                    for key, value in self.memory.facts.items()
                )
            )

        for field_name in self.definition.throttles:
            remaining = self.seconds_until_available(field_name)
            if remaining > 0:
                sections.append(
                    f"Throttle '{field_name}': wait "
                    f"{int(remaining)}s before acting again."
                )
            else:
                sections.append(f"Throttle '{field_name}': available now.")

        for field_name, ids in self.memory.seen.items():
            sections.append(
                f"Already handled in '{field_name}': {len(ids)} item(s)."
            )

        if extra:
            sections.append(f"## New this pulse\n{extra}")

        return "\n\n".join(sections)


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split ``---`` frontmatter from the markdown body.

    A deliberately small parser for the documented frontmatter shape — scalar
    ``key: value`` lines and inline maps ``key: { a: x, b: y }`` — so the core
    needs no YAML dependency.

    Args:
        text: The full file contents.

    Returns:
        A ``(metadata, body)`` tuple. Metadata is empty and body is the whole
        text when no frontmatter block is present.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    meta: dict[str, Any] = {}
    body_start = len(lines)
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            body_start = index + 1
            break
        key, _, raw = lines[index].partition(":")
        key = key.strip()
        if key:
            meta[key] = _parse_scalar_or_map(raw.strip())
    return meta, "\n".join(lines[body_start:])


def _parse_scalar_or_map(raw: str) -> Any:
    """Parse a frontmatter value as an inline map or a bare scalar string.

    The parser supports exactly two shapes: a bare scalar, and a single-level
    inline map ``{ a: x, b: y }``. Anything outside that — unbalanced braces,
    nested maps, list syntax, or a map entry missing its colon — raises rather
    than silently misparsing, since the saved cost of a YAML dep is not worth a
    value that parses to something subtly wrong. Generate richer config from
    the markdown body instead of widening this grammar.

    Args:
        raw: The text after the ``key:`` on a frontmatter line.

    Returns:
        A ``dict[str, str]`` for ``{ a: x, b: y }`` syntax, else the raw
        string with surrounding quotes stripped.

    Raises:
        ValueError: If the value uses an unsupported or malformed shape.
    """
    if raw.startswith("{") or raw.endswith("}"):
        if not (raw.startswith("{") and raw.endswith("}")):
            raise ValueError(
                f"Unbalanced '{{}}' in frontmatter value: {raw!r}"
            )
        inner = raw[1:-1]
        if "{" in inner or "}" in inner:
            raise ValueError(
                f"Nested maps are not supported in frontmatter: {raw!r}"
            )
        result: dict[str, str] = {}
        for pair in inner.split(","):
            if not pair.strip():
                continue
            key, sep, value = pair.partition(":")
            if not sep:
                raise ValueError(
                    f"Map entry missing ':' in frontmatter value: {pair!r}"
                )
            result[key.strip()] = value.strip()
        return result
    if raw.startswith("[") or raw.endswith("]"):
        raise ValueError(
            f"List syntax is not supported in frontmatter: {raw!r}"
        )
    return raw.strip("'\"")


def _parse_duration(value: str | float) -> float:
    """Parse a duration like ``90s``, ``15m``, ``1h``, ``2d`` into seconds.

    Args:
        value: A suffixed duration string, or a bare number of seconds.

    Returns:
        The duration in seconds.

    Raises:
        ValueError: If the string is not a recognized duration.
    """
    if isinstance(value, (int, float)):
        return float(value)
    text = value.strip()
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if text and text[-1] in units:
        return float(text[:-1]) * units[text[-1]]
    return float(text)


def _as_map(value: Any) -> dict[str, Any]:
    """Return ``value`` if it is a dict, else an empty dict."""
    return value if isinstance(value, dict) else {}


def _as_str(value: Any) -> str | None:
    """Return ``value`` as a string, or None if it is falsy/absent."""
    return str(value) if value else None
