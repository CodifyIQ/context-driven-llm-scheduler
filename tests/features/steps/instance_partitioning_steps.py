"""Steps for instance_partitioning.feature.

Covers the two additive capabilities: triggering a pulse under an isolated
state partition (``instance=``) and running a definition built at call time
(``trigger_definition``) without registering it first.
"""

from behave import given, then, when

from context_driven_llm_scheduler import PulseDefinition, PulseNotRegisteredError


def _increment_count(pulse, extra=None):
    """Minimal handler used by the ad-hoc scenarios: bump ``count``."""
    pulse.context["count"] = pulse.context.get("count", 0) + 1


@when('I trigger instance "{instance}" of "{pulse_id}"')
def step_trigger_instance(context, instance, pulse_id):
    context.result = context.manager.trigger(pulse_id, instance=instance)


@when('I trigger instance "{instance}" of "{pulse_id}" {count:d} times')
def step_trigger_instance_n(context, instance, pulse_id, count):
    for _ in range(count):
        context.result = context.manager.trigger(pulse_id, instance=instance)


@when(
    'I trigger instance "{instance}" of "{pulse_id}" '
    "with a {window:d} second coalesce window"
)
def step_trigger_instance_coalesced(context, instance, pulse_id, window):
    context.result = context.manager.trigger(
        pulse_id, instance=instance, coalesce_window=window
    )


@given('an unregistered pulse definition "{pulse_id}"')
def step_unregistered_definition(context, pulse_id):
    """Build a definition via ``from_markdown`` without registering it."""
    body = context.text if getattr(context, "text", None) else f"Handle {pulse_id}."
    context.adhoc_def = PulseDefinition.from_markdown(body, default_id=pulse_id)


@when("I trigger the ad-hoc definition")
def step_trigger_adhoc(context):
    context.result = context.manager.trigger_definition(
        context.adhoc_def, _increment_count
    )


@when('I trigger the ad-hoc definition for instance "{instance}"')
def step_trigger_adhoc_instance(context, instance):
    context.result = context.manager.trigger_definition(
        context.adhoc_def, _increment_count, instance=instance
    )


@when('I trigger the ad-hoc definition for instance "{instance}" {count:d} times')
def step_trigger_adhoc_instance_n(context, instance, count):
    for _ in range(count):
        context.result = context.manager.trigger_definition(
            context.adhoc_def, _increment_count, instance=instance
        )


@then('the "{name}" event has instance "{instance}"')
def step_event_instance(context, name, instance):
    event = next(item for item in context.events if item["event"] == name)
    assert event.get("instance") == instance, (
        f"expected instance {instance!r} on {name!r}, got {event.get('instance')!r}"
    )


@then('triggering "{pulse_id}" raises a not-registered error')
def step_trigger_raises_not_registered(context, pulse_id):
    try:
        context.manager.trigger(pulse_id)
    except PulseNotRegisteredError:
        return
    raise AssertionError(
        f"expected PulseNotRegisteredError triggering unregistered {pulse_id!r}"
    )


@then('triggering instance "{instance}" of "{pulse_id}" raises a value error')
def step_trigger_instance_raises_value(context, instance, pulse_id):
    try:
        context.manager.trigger(pulse_id, instance=instance)
    except ValueError:
        return
    raise AssertionError(
        f"expected ValueError triggering instance {instance!r} of {pulse_id!r}"
    )


@then("the result log has {count:d} distinct entry files")
def step_log_file_count(context, count):
    files = sorted(context.result_log.root.glob("*.md"))
    assert len(files) == count, (
        f"expected {count} run-log file(s), got {[path.name for path in files]}"
    )


@then('the result log has no file for "{pulse_id}"')
def step_no_log_file(context, pulse_id):
    path = context.result_log.path(pulse_id)
    assert not path.exists(), (
        f"did not expect a run-log file for unpartitioned {pulse_id!r}: {path.name}"
    )
