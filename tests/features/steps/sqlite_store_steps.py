"""Step definitions specific to sqlite_store.feature."""

from behave import given

from context_driven_llm_scheduler import SQLiteStore


@given('a sqlite store')
def step_use_sqlite_store(context):
    context.store = SQLiteStore(str(context.tmpdir / "pulses.sqlite"))
