Feature: Pulse trigger cycle
  As a job author
  I want each trigger to load context, run my handler, and persist the result
  So that state carries across wake-ups without external bookkeeping

  Scenario: First trigger records the field
    Given a pulse "counter" that increments "count"
    When I trigger "counter"
    Then the context field "count" equals 1

  Scenario: Context persists across triggers
    Given a pulse "counter" that increments "count"
    When I trigger "counter" 3 times
    Then the context field "count" equals 3

  Scenario: Trigger metadata is recorded automatically
    Given a pulse "counter" that increments "count"
    When I trigger "counter" 2 times
    Then the context field "trigger_count" equals 2
    And the context has field "last_triggered"
