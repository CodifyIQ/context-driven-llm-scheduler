"""Steps for the on_event observability seam."""

from behave import given, then

from context_driven_llm_scheduler import PulseManager


@given("a manager that captures events")
def step_capture_manager(context):
    """Replace the scenario manager with one wired to an event sink."""
    context.events = []
    context.manager = PulseManager(
        context.store, on_event=context.events.append
    )


@then('an event "{name}" was emitted')
def step_event_emitted(context, name):
    names = [event["event"] for event in context.events]
    assert name in names, f"expected a {name!r} event, got {names!r}"


@then('the "{name}" event recorded {count:d} change')
def step_event_change_count(context, name, count):
    event = next(
        item for item in context.events if item["event"] == name
    )
    changes = event.get("changes", [])
    assert len(changes) == count, (
        f"expected {count} change(s) on {name!r}, got {changes!r}"
    )
