"""Steps for markdown_authoring.feature: frontmatter-optional pulse files."""

from behave import given, then

from context_driven_llm_scheduler import PulseDefinition


@given('a pulse file "{filename}" containing')
def step_pulse_file(context, filename):
    """Write a markdown file to the scenario tmpdir and load it from disk."""
    path = context.tmpdir / filename
    path.write_text(context.text, encoding="utf-8")
    context.definition = PulseDefinition.from_file(path)
    context.manager.add_definition(context.definition)
    context.pulse_id = context.definition.id


@given('the loaded pulse increments "{field}"')
def step_loaded_increments(context, field):
    """Register a minimal handler on the loaded definition."""
    @context.manager.pulse(context.definition.id)
    def handler(pulse, extra=None):
        pulse.context[field] = pulse.context.get(field, 0) + 1


@then('the loaded pulse id is "{expected}"')
def step_loaded_id(context, expected):
    assert context.definition.id == expected, (
        f"expected id {expected!r}, got {context.definition.id!r}"
    )


@then('the loaded pulse instructions contain "{needle}"')
def step_loaded_instructions(context, needle):
    assert needle in context.definition.instructions, (
        f"expected {needle!r} in instructions:\n"
        f"{context.definition.instructions}"
    )
