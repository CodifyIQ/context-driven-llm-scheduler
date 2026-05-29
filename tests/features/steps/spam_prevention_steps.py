"""Step definitions for spam_prevention.feature."""

from behave import given, then

from context_driven_llm_scheduler import (
    PulseDefinition,
    add_to_seen_set,
    check_throttle,
)


@given('a pulse "{pulse_id}" that records id "{value}" in seen set "{field}"')
def step_register_dedup(context, pulse_id, value, field):
    context.pulse_id = pulse_id

    @context.manager.pulse(PulseDefinition(id=pulse_id, instructions=""))
    def handler(pulse, extra=None):
        pulse.context["_was_new"] = add_to_seen_set(
            pulse.context, field, value
        )


@given('a pulse "{pulse_id}" with a {seconds:d} second throttle on "{field}"')
def step_register_throttle(context, pulse_id, seconds, field):
    context.pulse_id = pulse_id

    @context.manager.pulse(PulseDefinition(id=pulse_id, instructions=""))
    def handler(pulse, extra=None):
        pulse.context["_allowed"] = check_throttle(
            pulse.context, field, seconds, pulse.trigger_time
        )


@then('the recorded id was new')
def step_was_new(context):
    assert context.result["_was_new"] is True


@then('the recorded id was not new')
def step_was_not_new(context):
    assert context.result["_was_new"] is False


@then('the action was allowed')
def step_allowed(context):
    assert context.result["_allowed"] is True


@then('the action was blocked')
def step_blocked(context):
    assert context.result["_allowed"] is False
