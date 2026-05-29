"""Step definitions for trigger_cycle.feature."""

from behave import given

from context_driven_llm_scheduler import PulseDefinition


@given('a pulse "{pulse_id}" that increments "{field}"')
def step_register_increment(context, pulse_id, field):
    context.pulse_id = pulse_id

    @context.manager.pulse(PulseDefinition(id=pulse_id, instructions=""))
    def handler(pulse, extra=None):
        pulse.context[field] = pulse.context.get(field, 0) + 1

    context.pulse_field = field
