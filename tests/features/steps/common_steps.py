"""Steps shared across features: triggering and generic assertions.

Behave registers every step file globally, so trigger/assertion steps used by
multiple features live here once to avoid ambiguous redefinitions.
"""

import json

from behave import then, when


@when('I trigger "{pulse_id}"')
def step_trigger(context, pulse_id):
    context.result = context.manager.trigger(pulse_id)


@when('I trigger "{pulse_id}" {count:d} times')
def step_trigger_n(context, pulse_id, count):
    for _ in range(count):
        context.result = context.manager.trigger(pulse_id)


@when('I trigger "{pulse_id}" expecting an error')
def step_trigger_expect_error(context, pulse_id):
    context.raised = None
    try:
        context.result = context.manager.trigger(pulse_id)
    except Exception as exc:  # noqa: BLE001 - test captures any handler error
        context.raised = exc


@then('the context field "{field}" equals {expected}')
def step_field_equals(context, field, expected):
    expected_value = json.loads(expected)
    actual = context.result[field]
    assert actual == expected_value, (
        f"expected {field}={expected_value!r}, got {actual!r}"
    )


@then('the context field "{field}" is null')
def step_field_null(context, field):
    actual = context.result.get(field)
    assert actual is None, f"expected {field} to be null, got {actual!r}"


@then('the context has field "{field}"')
def step_has_field(context, field):
    assert field in context.result and context.result[field] is not None, (
        f"expected non-null field '{field}' in {context.result}"
    )


@then('the stored context field "{field}" equals {expected}')
def step_stored_field_equals(context, field, expected):
    expected_value = json.loads(expected)
    stored = context.store.load(context.pulse_id)
    actual = stored.get(field)
    assert actual == expected_value, (
        f"expected stored {field}={expected_value!r}, got {actual!r}"
    )


# --- Backend-neutral store steps (operate on context.store) ---


@when('I save context {payload} under key "{key}"')
def step_save(context, payload, key):
    context.store.save(key, json.loads(payload))


@when('I delete key "{key}"')
def step_delete(context, key):
    context.store.delete(key)


@then('loading key "{key}" returns an empty context')
def step_load_empty(context, key):
    loaded = context.store.load(key)
    assert loaded == {}, f"expected empty context, got {loaded!r}"


@then('loading key "{key}" returns context {payload}')
def step_load_equals(context, key, payload):
    expected = json.loads(payload)
    loaded = context.store.load(key)
    assert loaded == expected, f"expected {expected!r}, got {loaded!r}"
