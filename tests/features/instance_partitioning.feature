Feature: Instance partitioning and ad-hoc definition execution
  As a service running one pulse definition across many subjects
  I want isolated per-instance state and definitions I can run without registering
  So that one shared rule can serve many tenants sourced at runtime

  Scenario: Two instances of one pulse keep isolated state
    Given a pulse "readiness" that increments "count"
    When I trigger instance "team-a" of "readiness" 2 times
    And I trigger instance "team-b" of "readiness"
    Then the context field "count" equals 1

  Scenario: An instance does not touch the unpartitioned pulse key
    Given a pulse "readiness" that increments "count"
    When I trigger instance "team-a" of "readiness"
    Then loading key "readiness" returns an empty context

  Scenario: The default trigger stays isolated from every instance
    Given a pulse "readiness" that increments "count"
    When I trigger instance "team-a" of "readiness" 3 times
    And I trigger "readiness"
    Then the context field "count" equals 1

  Scenario: Coalescing is scoped per instance
    Given a pulse "readiness" that increments "count"
    When I trigger instance "team-a" of "readiness" with a 3600 second coalesce window
    And I trigger instance "team-b" of "readiness" with a 3600 second coalesce window
    Then the context field "count" equals 1

  Scenario: The same instance still coalesces a repeat run
    Given a pulse "readiness" that increments "count"
    When I trigger instance "team-a" of "readiness" with a 3600 second coalesce window
    And I trigger instance "team-a" of "readiness" with a 3600 second coalesce window
    Then the context field "count" equals 1

  Scenario: Lifecycle events carry the instance label
    Given a manager that captures events
    And a pulse "readiness" that increments "count"
    When I trigger instance "team-a" of "readiness"
    Then the "trigger_start" event has instance "team-a"
    And the "trigger_end" event has instance "team-a"

  Scenario: A definition built at call time runs without registration
    Given an unregistered pulse definition "adhoc-check"
    When I trigger the ad-hoc definition
    Then the context field "count" equals 1
    And triggering "adhoc-check" raises a not-registered error

  Scenario: An ad-hoc definition fans across isolated instances
    Given an unregistered pulse definition "adhoc-check"
    When I trigger the ad-hoc definition for instance "team-a" 2 times
    And I trigger the ad-hoc definition for instance "team-b"
    Then the context field "count" equals 1

  Scenario: Each instance gets its own run-log file
    Given a manager with a result log
    And a pulse "readiness" that increments "count"
    When I trigger instance "team-a" of "readiness"
    And I trigger instance "team-b" of "readiness"
    Then the result log has 2 distinct entry files
    And the result log has no file for "readiness"

  Scenario: An instance carrying the reserved separator is rejected
    Given a pulse "readiness" that increments "count"
    Then triggering instance "team::a" of "readiness" raises a value error
