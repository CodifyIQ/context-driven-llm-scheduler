Feature: Markdown run log
  As an operator of unattended jobs
  I want each run recorded in markdown with its result and the context it saw
  So that a single run is auditable and reproducible from the log alone

  Scenario: A run logs its result, carried context, and memory changes
    Given a manager with a result log
    And a pulse defined by markdown
      """
      ---
      id: digest
      model: bedrock/anthropic.claude-3-5-sonnet
      ---
      Summarize the day.
      """
    And the stored pulse has fact "open_incidents" = "2"
    And a handler that records result "Wrote the daily digest" and persists note "summarized 3 alerts"
    When I trigger "digest"
    Then the run log for "digest" contains "run #1 · ok"
    And the run log for "digest" contains "model: bedrock/anthropic.claude-3-5-sonnet"
    And the run log for "digest" contains "Wrote the daily digest"
    And the run log for "digest" contains "open_incidents"
    And the run log for "digest" contains "note: summarized 3 alerts"

  Scenario: A failed run is logged with its error
    Given a manager with a result log
    And a pulse "errjob" that raises ValueError "boom"
    When I trigger "errjob" expecting an error
    Then the run log for "errjob" contains "· error"
    And the run log for "errjob" contains "boom"
