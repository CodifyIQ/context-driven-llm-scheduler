# Python / Behave

## Project Structure

```
tests/
├── features/
│   ├── domain_feature.feature     # Gherkin feature files
│   └── steps/
│       └── domain_feature_steps.py  # One step file per feature file
└── environment.py                   # Behave hooks (before_all, before_scenario, etc.)
```

One step file per feature file. Name the step file to match its feature file (e.g., `wine_classification.feature` → `wine_classification_steps.py`).

---

## environment.py — Test Hooks

Use `environment.py` for setup/teardown that applies across all features. This keeps step files focused on behavior, not infrastructure:

```python
# environment.py
import os
from sqlmodel import SQLModel, create_engine, Session

DB_URL = "sqlite:///test.db"

def before_all(context):
    """Set up test database and shared resources."""
    os.environ["DB_URL"] = DB_URL
    engine = create_engine(DB_URL)
    SQLModel.metadata.create_all(engine)
    context.engine = engine

def before_scenario(context, scenario):
    """Give each scenario a clean database session."""
    context.session = Session(context.engine)

def after_scenario(context, scenario):
    """Roll back to keep scenarios isolated."""
    context.session.rollback()
    context.session.close()

def after_all(context):
    """Clean up test database."""
    os.remove("test.db")
```

---

## Running Tests

```bash
# Run all local tests (excludes @integration-test)
behave --tags="not @integration-test"

# Run only integration tests
behave --tags="@integration-test"

# Run a specific feature
behave tests/features/wine_classification.feature
```

---

## Step Definition Patterns

### Singular/Plural Step Variants

```python
@then("{count:d} wine is returned")
def step_validate_count_singular(context, count):
    step_validate_count_plural(context, count)

@then("{count:d} wines are returned")
def step_validate_count_plural(context, count):
    assert len(context.wines) == count
```

### Optional Columns in Data Tables

```python
@given("a wine with the following attributes")
def step_build_wine(context):
    row = {h: v for h, v in zip(context.table.headings, context.table[0].cells)}
    # Convert numeric fields only if present — table values are always strings
    if "year" in row and row["year"]:
        row["year"] = int(row["year"])
    context.wine = Wine(**row)
```

### Caching Expensive Calls

Store the cache on Behave's `context` object so it's scoped to the test run and cleaned up automatically:

```python
@when("tasting notes are generated")
def step_generate_tasting_notes(context):
    import hashlib
    content_hash = hashlib.sha256(context.wine_label_bytes).hexdigest()
    if not hasattr(context, "_tasting_cache"):
        context._tasting_cache = {}
    if content_hash not in context._tasting_cache:
        context._tasting_cache[content_hash] = context.sommelier.generate_notes(context.wine_label_bytes)
    context.tasting_notes = context._tasting_cache[content_hash]
```

### Fuzzy Assertions

```python
import difflib
import logging

logger = logging.getLogger(__name__)

def assert_fuzzy_match(expected: str, actual: str, strict: float = 0.75, warn: float = 0.50):
    """Assert that actual is close enough to expected, with a warning tier."""
    ratio = difflib.SequenceMatcher(None, expected, actual).ratio()
    if ratio >= strict:
        pass  # close enough
    elif ratio >= warn:
        logger.warning(f"Fuzzy match {ratio:.2f} for '{expected}' vs '{actual}'")
    else:
        assert False, f"Match ratio {ratio:.2f} too low for '{expected}' vs '{actual}'"
```

Usage in step definitions:

```python
@then('the tasting note describes "{expected}"')
def step_assert_tasting_note(context, expected):
    assert_fuzzy_match(expected, context.tasting_notes.summary)
```

### Assertion Messages

```python
assert wine is not None, f"No wine found for vineyard '{vineyard}'"
assert wine.body == expected_body, (
    f"Expected body '{expected_body}' but got '{wine.body}' for '{wine.name}'"
)
```
