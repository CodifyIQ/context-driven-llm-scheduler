Feature: Coalescing concurrent triggers
  As an operator running one scheduler per web worker
  I want a coalesce window to collapse near-simultaneous triggers
  So that the same scheduled tick runs once, not once per worker

  Scenario: A repeat trigger inside the window is skipped
    Given a pulse "counter" that increments "count"
    When I trigger "counter" with a 3600 second coalesce window
    And I trigger "counter" with a 3600 second coalesce window
    Then the stored context field "count" equals 1

  Scenario: A herd of triggers collapses to a single run
    Given a pulse "counter" that increments "count"
    When 20 threads trigger "counter" with a 3600 second coalesce window at once
    Then the stored context field "count" equals 1

  Scenario: A skipped trigger emits a trigger_skipped event
    Given a manager that captures events
    And a pulse "counter" that increments "count"
    When I trigger "counter" with a 3600 second coalesce window
    And I trigger "counter" with a 3600 second coalesce window
    Then an event "trigger_skipped" was emitted
