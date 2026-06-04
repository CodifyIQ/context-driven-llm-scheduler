"""Steps for result_log.feature: the markdown run log."""

from behave import given, then

from context_driven_llm_scheduler import PulseManager, ResultLog


@given("a manager with a result log")
def step_manager_with_log(context):
    """Wire the scenario manager to a ResultLog under the scenario tmpdir."""
    context.result_log = ResultLog(context.tmpdir / "results")
    context.manager = PulseManager(
        context.store, result_log=context.result_log
    )


@given('the stored pulse has fact "{key}" = "{value}"')
def step_stored_fact(context, key, value):
    """Seed a fact into stored memory so it is carried into the next run."""
    context.store.save(
        context.pulse_id, {"memory": {"facts": {key: value}}}
    )


@given('a handler that records result "{body}" and persists note "{note}"')
def step_handler_records(context, body, note):
    @context.manager.pulse(context.definition.id)
    def handler(pulse, extra=None):
        pulse.record_result(body)
        return [{"op": "note", "text": note}]


@then('the run log for "{pulse_id}" contains "{needle}"')
def step_log_contains(context, pulse_id, needle):
    log = context.result_log.read(pulse_id)
    assert needle in log, f"expected {needle!r} in run log:\n{log}"
