# Step Definition Patterns

These patterns apply to step definition code regardless of language. For language-specific examples and setup, see [Python/Behave](python-behave.md) or [Java/Cucumber](java-cucumber.md).

---

## Singular/Plural Step Variants

When a step applies to both singular and plural cases, write both variants so the feature file reads naturally: "1 wine is returned" vs "3 wines are returned". The implementations should delegate to the same logic — the singular variant calls the plural one (Python) or a single regex handles both forms (Java).

---

## Optional Columns in Data Tables

Not every scenario needs every column in a data table. Step definitions should check which columns are present and only set those fields. This lets the same step handle "all fields populated" and "only required fields" without separate step definitions.

---

## Caching Expensive Calls

When multiple scenarios exercise the same expensive operation (e.g., classifying the same wine via an LLM), cache results keyed by content hash. This avoids redundant API calls without compromising test isolation — each scenario still gets the same input, just without re-paying the cost.

Content-hash caching is different from one-time setup. One-time setup (database init, loading fixtures) belongs in framework hooks (`before_all`/`@BeforeAll`). Content-hash caching is for deduplicating repeated expensive calls with identical inputs during a test run. Don't conflate the two — and don't use static boolean flags (`if (!initialized)`) for either purpose.

---

## Fuzzy Assertions for Non-Deterministic Outputs

When testing LLM or other non-deterministic outputs where you need to compare text, use fuzzy matching with tiered thresholds. The warning tier (0.50–0.74) gives early signal that outputs are drifting before they fully break.

---

## Assertion Messages

Always include descriptive messages in assertions. When a step fails, the message should tell you what went wrong without having to read the step definition code.
