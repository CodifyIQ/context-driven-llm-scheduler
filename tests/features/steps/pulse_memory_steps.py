"""Steps for markdown pulses and the memory protocol.

Exercises the membrane: parse a ``pulse.md``, recall memory in, persist the
model's memory operations out, and assert what persisted.
"""

import json

from behave import given, then, when

from context_driven_llm_scheduler import Pulse, PulseDefinition, utcnow


class _StubAdapter:
    """Deterministic adapter for recall-budget tests (no model, no network)."""

    def complete(self, prompt: str, **kwargs: object) -> str:
        """Echo the prompt; unused by these scenarios."""
        return prompt

    def count_tokens(self, text: str) -> int:
        """Approximate tokens as whitespace-delimited words."""
        return len(text.split())


@given("a pulse defined by markdown")
def step_define_pulse(context):
    context.definition = PulseDefinition.from_markdown(context.text)
    context.manager.add_definition(context.definition)
    context.pulse_id = context.definition.id


@when("I parse pulse markdown")
def step_parse_pulse(context):
    """Attempt a parse, capturing any error for malformed-input scenarios."""
    context.raised = None
    try:
        context.definition = PulseDefinition.from_markdown(context.text)
    except Exception as exc:  # noqa: BLE001 - test inspects the failure
        context.raised = exc


@given("a handler emitting memory operations")
def step_handler_ops(context):
    ops = json.loads(context.text)

    @context.manager.pulse(context.definition.id)
    def handler(pulse, extra=None):
        return ops


@given('the pulse memory has note "{text}"')
def step_memory_note(context, text):
    notes = context.__dict__.setdefault("seed_notes", [])
    notes.append(text)


@then('the pulse schedule is "{expected}"')
def step_schedule(context, expected):
    assert context.definition.schedule == expected, (
        f"expected schedule {expected!r}, got "
        f"{context.definition.schedule!r}"
    )


@then('the pulse throttle "{field}" is {seconds:d} seconds')
def step_throttle_seconds(context, field, seconds):
    actual = context.definition.throttles.get(field)
    assert actual == seconds, (
        f"expected throttle {field}={seconds}, got {actual!r}"
    )


@then('the pulse keep "{field}" is {count:d}')
def step_keep(context, field, count):
    actual = context.definition.keep.get(field)
    assert actual == count, (
        f"expected keep {field}={count}, got {actual!r}"
    )


@then('memory note {index:d} equals "{expected}"')
def step_note_equals(context, index, expected):
    notes = context.result["memory"]["notes"]
    assert notes[index] == expected, (
        f"expected note {index}={expected!r}, got {notes[index]!r}"
    )


@then("memory has {count:d} notes")
def step_note_count(context, count):
    notes = context.result["memory"]["notes"]
    assert len(notes) == count, (
        f"expected {count} notes, got {len(notes)}: {notes!r}"
    )


@then('memory has seen "{field}" id "{value}"')
def step_seen(context, field, value):
    seen = context.result["memory"]["seen"].get(field, [])
    assert value in seen, f"expected {value!r} in seen[{field}], got {seen!r}"


@then('the recorded seen set "{field}" has {count:d} item')
def step_seen_count(context, field, count):
    seen = context.result["memory"]["seen"].get(field, [])
    assert len(seen) == count, (
        f"expected {count} item(s) in seen[{field}], got {seen!r}"
    )


@then('memory throttle "{field}" is stamped')
def step_throttle_stamped(context, field):
    throttles = context.result["memory"]["throttles"]
    assert throttles.get(field), (
        f"expected throttle {field} stamped, got {throttles!r}"
    )


@then('memory fact "{key}" equals "{expected}"')
def step_fact(context, key, expected):
    facts = context.result["memory"]["facts"]
    assert facts.get(key) == expected, (
        f"expected fact {key}={expected!r}, got {facts.get(key)!r}"
    )


@when("I recall the pulse")
def step_recall(context):
    context.recalled = _build_pulse(context).recall()


@when("I recall the pulse with a {ceiling:d} token ceiling")
def step_recall_budget(context, ceiling):
    context.recalled = _build_pulse(context).recall(
        adapter=_StubAdapter(), max_tokens=ceiling
    )


@then('the recalled prompt contains "{needle}"')
def step_recall_contains(context, needle):
    assert needle in context.recalled, (
        f"expected {needle!r} in recalled prompt:\n{context.recalled}"
    )


@then('the recalled prompt does not contain "{needle}"')
def step_recall_not_contains(context, needle):
    assert needle not in context.recalled, (
        f"did not expect {needle!r} in recalled prompt:\n{context.recalled}"
    )


@when('I compact the pulse keeping {keep:d} notes with summary "{summary}"')
def step_compact(context, keep, summary):
    pulse = _build_pulse(context)
    context.compact_prompt = pulse.compact_prompt(keep=keep)
    if context.compact_prompt is not None:
        pulse.compact(summary, keep=keep)
    context.compacted_notes = list(pulse.memory.notes)


@then('the compaction prompt contains "{needle}"')
def step_compact_prompt_contains(context, needle):
    assert context.compact_prompt is not None, "no compaction prompt produced"
    assert needle in context.compact_prompt, (
        f"expected {needle!r} in compaction prompt:\n{context.compact_prompt}"
    )


@then("the compacted notes number {count:d}")
def step_compacted_count(context, count):
    actual = len(context.compacted_notes)
    assert actual == count, (
        f"expected {count} notes after compaction, got {actual}: "
        f"{context.compacted_notes!r}"
    )


@then('a compacted note contains "{needle}"')
def step_compacted_contains(context, needle):
    assert any(needle in note for note in context.compacted_notes), (
        f"expected a note containing {needle!r}, got "
        f"{context.compacted_notes!r}"
    )


@then('no compacted note contains "{needle}"')
def step_compacted_not_contains(context, needle):
    assert not any(needle in note for note in context.compacted_notes), (
        f"did not expect {needle!r} in any note: "
        f"{context.compacted_notes!r}"
    )


def _build_pulse(context):
    """Construct a Pulse seeded with any notes from prior steps."""
    ctx = {}
    pulse = Pulse(context.definition, ctx, utcnow())
    for note in context.__dict__.get("seed_notes", []):
        pulse.memory.notes.append(note)
    return pulse
