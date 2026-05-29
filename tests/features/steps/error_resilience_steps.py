"""Step definitions for error_resilience.feature."""

from behave import given, then

from context_driven_llm_scheduler import PulseDefinition, PulseManager

_EXCEPTION_TYPES = {
    "ValueError": ValueError,
    "RuntimeError": RuntimeError,
    "KeyError": KeyError,
}


@given('a manager configured to swallow errors')
def step_swallow_manager(context):
    context.manager = PulseManager(context.store, swallow_errors=True)


@given('a pulse "{pulse_id}" that raises {exc_type} "{message}"')
def step_register_boom(context, pulse_id, exc_type, message):
    context.pulse_id = pulse_id
    error_class = _EXCEPTION_TYPES[exc_type]

    @context.manager.pulse(PulseDefinition(id=pulse_id, instructions=""))
    def handler(pulse, extra=None):
        raise error_class(message)


@given('a pulse "{pulse_id}" that fails only on its first trigger')
def step_register_flaky(context, pulse_id):
    context.pulse_id = pulse_id

    @context.manager.pulse(PulseDefinition(id=pulse_id, instructions=""))
    def handler(pulse, extra=None):
        if pulse.context.get("trigger_count") == 1:
            raise ValueError("first-time failure")


@then('a {exc_type} was raised')
def step_assert_raised(context, exc_type):
    assert context.raised is not None, "expected an exception, none raised"
    assert type(context.raised).__name__ == exc_type, (
        f"expected {exc_type}, got {type(context.raised).__name__}"
    )


@then('no error was raised')
def step_assert_no_error(context):
    assert context.raised is None, f"unexpected error: {context.raised!r}"


@then('the stored context has a last_error with message "{message}"')
def step_assert_last_error(context, message):
    stored = context.store.load(context.pulse_id)
    last_error = stored.get("last_error")
    assert last_error is not None, "expected a recorded last_error"
    assert last_error["message"] == message, (
        f"expected message '{message}', got {last_error['message']!r}"
    )
