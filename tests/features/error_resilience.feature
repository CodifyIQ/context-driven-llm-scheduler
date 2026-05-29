Feature: Error resilience
  As a job author
  I want handler failures recorded in context
  So that the next wake-up can see the error and react

  Scenario: Handler error is recorded and re-raised
    Given a pulse "boom" that raises ValueError "kaboom"
    When I trigger "boom" expecting an error
    Then a ValueError was raised
    And the stored context field "error_count" equals 1
    And the stored context has a last_error with message "kaboom"

  Scenario: swallow_errors suppresses the exception
    Given a manager configured to swallow errors
    And a pulse "boom" that raises ValueError "kaboom"
    When I trigger "boom"
    Then no error was raised
    And the context field "error_count" equals 1

  Scenario: A successful trigger clears a prior error
    Given a pulse "flaky" that fails only on its first trigger
    When I trigger "flaky" expecting an error
    And I trigger "flaky"
    Then the context field "last_error" is null
    And the context field "error_count" equals 1
