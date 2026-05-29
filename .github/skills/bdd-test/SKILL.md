---
name: "bdd-test"
description: "BDD testing patterns for Python (Behave) and Java (Cucumber). Use whenever writing tests, adding test coverage, creating feature files, or writing step definitions in a Python or Java project — even if the user doesn't say 'BDD'. Covers Gherkin style, scenario design, test tagging, database setup, and assertions for non-deterministic outputs. Does not apply to Flutter projects."
metadata:
  tags: default
---

# BDD Testing Patterns (Behave / Cucumber)

## Philosophy

BDD tests are the executable flip side of requirements. Think of them as what happens when people walk up to a whiteboard to discuss a solution — they draw examples. Feature files capture those examples in a form that both humans and machines can run.

This means feature files are **functionally driven, not technically driven**. A scenario should read like a conversation about what the system does, not how it's implemented. A product owner, a developer, and a tester should all be able to read a scenario and agree on what it means. If a step mentions class names, database columns, or HTTP status codes, it's too technical.

Prefer real infrastructure over mocks (e.g., SQLite instead of a mocked DB, real API calls instead of stubbed responses). Mocks hide integration bugs and make tests less trustworthy as documentation.

### Why BDD pays off

- **Less code to read and maintain.** Well-written step definitions are reusable across scenarios. The feature file stays concise because it delegates to shared steps rather than repeating setup logic.
- **Failures point to requirements, not random tests.** When a scenario fails, its name tells you exactly which requirement broke — not just that "test_47" is red. Knowing which requirement is impacted by a change is an earth-moving improvement in understanding whether something matters.
- **Living documentation.** The feature files are always in sync with the code because they execute against it. Stale wiki pages and outdated specs become a thing of the past.

### Capturing requirements as scenarios

Sometimes a requirement is worth documenting even if the test isn't worth automating yet — or the feature hasn't been built. Write the scenario and tag it `@skip` (Behave) or `@Disabled` (Cucumber). This keeps requirements visible and traceable in the test suite, and the scenario is ready to activate when the time comes.

```gherkin
@skip
Scenario: Sommelier receives notification when a new wine is added to their region
  Given a sommelier specializing in "Napa Valley"
  When a new wine from "Napa Valley" is added to the catalog
  Then the sommelier receives a new wine notification
```

---

## References

When writing step definition code, load the reference for the project's language:

- [Python/Behave](references/python-behave.md) — project structure, environment.py hooks, run commands, and step definition examples. Load for Python projects.
- [Java/Cucumber](references/java-cucumber.md) — project structure, Maven setup, test runner, hooks, ScenarioContext, and step definition examples. Load for Java projects.

---

## Gherkin Style

### Write for humans first

Steps should be as simple as possible, but no simpler. Every word should earn its place. Read each scenario aloud — if it sounds like something you'd say at a whiteboard, it's right. If it sounds like a log message or an API spec, simplify it.

```gherkin
# GOOD — a person would say this
Scenario: Highly oaked wines are classified as bold
  Given a bottle of "Westend" "The Boxer Oak Age Durif" "2011"
  When the wine is classified
  Then the body is "FULL"

# BAD — technical jargon that only a developer can parse
Scenario: GET /wines/{id}/classify returns 200 and sets body_enum to FULL
  Given a GET request to /wines/42/classify with oak_level HIGH
  When the response status is 200
  Then the wine_attributes table contains body_enum "FULL" for wine_id 42
```

### Given/When/Then = Preconditions/Action/Postconditions

Each keyword maps to a logical role:

- **Given** — preconditions. Establish the state of the world before the behavior happens. No side effects, no assertions. "Given a bottle of Westend The Boxer Oak Age Durif 2011" sets the stage.
- **When** — the action. The single thing being tested. There should typically be one When per scenario. "When the wine is classified" is the behavior under test.
- **Then** — postconditions. Assert what should be true after the action. "Then the body is FULL" verifies the outcome.

Keeping this mapping in mind makes scenarios easier to reason about. Each scenario should focus on the single behavior it's testing, making failures easier to diagnose. Avoid chains of And/But — if a scenario needs many And steps, it may be testing too many things at once.

### Background for shared setup

When multiple scenarios need the same preconditions, use Background to avoid repeating setup steps. Background is especially valuable for expensive operations like loading test data or resetting the world to a clean state:

```gherkin
Background:
  Given wines have been loaded and classified
  And the following user preferences exist:
    | user       | preferred_regions |
    | sommelier1 | Napa Valley       |
    | sommelier2 | Barossa Valley    |
```

The "wines have been loaded and classified" step can reset the database, load test data, and run classification. This is better than after-scenario cleanup because it makes preconditions explicit in the feature file.

**Don't hand-roll one-time setup with static flags.** Patterns like `if (!initialized) { ... }` inside step definitions create hidden shared state between scenarios. If initialization fails once, every subsequent scenario fails with a cryptic error, and you have no way to retry. Use framework hooks (`before_all`/`@BeforeAll`) for truly one-time setup — the framework manages the lifecycle and gives you proper error handling. This is different from content-hash caching (covered under "Caching Expensive Calls" below), which can deduplicate genuinely expensive operations — but should only be used sparingly when the cost truly warrants it.

### Steps as requirement functions

Think of a parameterized step — one with `"{variables}"` or a data table — as a **requirement function**. The step text is the function signature describing the requirement, and each scenario or Scenario Outline row is a call to that function with different inputs. This makes it trivial to plug in new examples: you don't write new code, you just add another row or another scenario that calls the same step.

```gherkin
# The step 'a bottle of "{vineyard}" "{name}" is classified as "{body}"' is a requirement function.
# Adding a new wine to verify is just a new row — no new code needed.
Scenario Outline: Wine body is classified from label data
  Given a bottle of "<vineyard>" "<name>" "<year>"
  When the wine is classified
  Then the body is "<body>"

  Examples:
    | vineyard | name                    | year | body   |
    | Westend  | The Boxer Oak Age Durif | 2011 | FULL   |
    | Yalumba  | Y Series Viognier       | 2020 | LIGHT  |
    | Penfolds | Bin 389                 | 2018 | MEDIUM |
```

Similarly, a data table step like `Given a wine with the following attributes:` is a requirement function that accepts structured input. Change the table to test a different combination — the step definition stays the same.

This is why well-written BDD has less code to maintain: the step definitions are reusable functions, and the feature file is just a list of calls with different example data.

### Right number of scenarios

Cover the standard case, meaningful edge cases, and error cases — then stop. Enough examples that you're confident the behavior works; not so many that the feature file becomes a wall of repetition. For distinct edge cases, separate scenarios are better because each gets a descriptive name that tells you exactly which requirement broke.

### Scenario names are requirement labels

Name each scenario like you'd name a requirement. When this test fails in CI, the name is the first thing someone reads. It should immediately communicate what's broken without opening the file.

```gherkin
# GOOD — tells you what requirement failed
Scenario: Wines without a vineyard are rejected

# BAD — tells you nothing useful
Scenario: Test validation error case 3
```

### Data Tables for Structured Data

Use Gherkin pipe-delimited tables instead of inline key:value strings. Tables are self-documenting — readers can immediately see which fields are set without parsing a custom format, and adding new fields doesn't break existing step definitions:

```gherkin
# GOOD — readable data table
Scenario: A fully described wine is accepted into the catalog
  Given a wine with the following attributes:
    | vineyard | name                    | year | region       | varietal |
    | Westend  | The Boxer Oak Age Durif | 2011 | Barossa      | Durif    |
  When the wine is submitted to the catalog
  Then it is accepted

# BAD — opaque inline blob that requires a custom parser
Scenario Outline: Wine catalog enforces fields
  Given a wine built from <fields>
  ...
  Examples:
    | fields                                                              |
    | vineyard:"Westend" name:"Boxer" year:2011 region:"Barossa" ...     |
```

Data tables also work well with optional columns. Not every scenario needs every column — step definitions should check which columns are present and only set those fields. This lets the same step handle "all fields populated" and "only required fields" without separate step definitions.

### Edge Cases via Separate Scenarios

Each edge case deserves its own scenario with a descriptive name. When a test fails, the scenario name tells you exactly which behavior broke — no need to decode a row index in a Scenario Outline:

```gherkin
# Each scenario documents a specific requirement
Scenario: Wines without a year default to non-vintage
  Given a wine with the following attributes:
    | vineyard | name          | varietal |
    | Penfolds | Koonunga Hill | Shiraz   |
  When the wine is submitted to the catalog
  Then it is accepted as a non-vintage wine

Scenario: Wines require a vineyard
  Given a wine with the following attributes:
    | name          | year |
    | Koonunga Hill | 2019 |
  When the wine is submitted to the catalog
  Then it is rejected because vineyard is required
```

---

## Test Tagging

Separate tests that need external services from those that can run locally. Tests should run by default without requiring network access or API keys:

- Default (untagged): runs with local-only dependencies (SQLite, in-memory resources)
- `@integration-test`: requires external services (LLM APIs, real databases, cloud services) — run separately in CI or via a dedicated profile

---

## Asserting Non-Deterministic Outputs

When testing outputs from LLMs or other non-deterministic systems, exact string matching will produce flaky tests. Two strategies:

### Assert structure and type, not exact content

For LLM-generated text, verify that the response exists, has the right shape, and contains the right kind of information — not that it matches a specific string. Check event types, response sequences, and structural properties:

```gherkin
# GOOD — verifies the behavior happened, not the exact words
Scenario: Sommelier receives a tasting note summary for a new wine
  Given a bottle of "Westend" "The Boxer Oak Age Durif" "2011"
  When tasting notes are generated
  Then a tasting note summary is provided
  And the summary mentions oak characteristics

# BAD — brittle, will break when the LLM rephrases
Scenario: Sommelier receives a tasting note summary for a new wine
  Given a bottle of "Westend" "The Boxer Oak Age Durif" "2011"
  When tasting notes are generated
  Then the summary says "A bold, full-bodied Durif with prominent American oak and dark fruit notes."
```

### Fuzzy matching with tiered thresholds

When you do need to compare text, use fuzzy matching with a warning tier. See the language-specific references for implementation examples.

The warning tier (0.50–0.74) gives early signal that outputs are drifting before they fully break, letting you update expectations proactively.

### Caching Expensive Calls (Use Sparingly)

**This is an edge-case pattern, not a default.** Most test operations — database queries, local computations, in-memory service calls — are fast enough that caching adds complexity for no benefit. Only introduce content-hash caching when an operation is genuinely expensive or slow: LLM API calls, external service round-trips, or heavy computations that take seconds per invocation. If the operation completes in milliseconds, don't cache it.

When multiple scenarios do exercise the same expensive operation (e.g., generating tasting notes for the same wine via an LLM), cache results keyed by content hash. This avoids redundant API calls without compromising test isolation — each scenario still gets the same input, just without re-paying the cost.

This is not the same thing as one-time setup (which belongs in framework hooks like `before_all`/`@BeforeAll`). Content-hash caching is for operations that may be called many times with different inputs — you want to deduplicate calls with *identical* inputs, not skip setup entirely. See the language-specific references for implementation examples.
