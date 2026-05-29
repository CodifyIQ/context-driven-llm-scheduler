Feature: Observability event seam
  As an operator
  I want each trigger to emit structured events with what memory changed
  So that I can route pulse activity to my own logging, metrics, or tracing

  Scenario: triggers emit lifecycle events carrying the memory changeset
    Given a manager that captures events
    And a pulse defined by markdown
      """
      ---
      id: triage
      ---
      Triage the inbox.
      """
    And a handler emitting memory operations
      """
      [{"op": "note", "text": "did a thing"}]
      """
    When I trigger "triage"
    Then an event "trigger_start" was emitted
    And an event "trigger_end" was emitted
    And the "trigger_end" event recorded 1 change
