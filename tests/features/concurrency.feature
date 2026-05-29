Feature: Concurrent triggers do not lose updates
  As a library user
  I want the store transaction to serialize concurrent triggers
  So that simultaneous wake-ups of the same pulse cannot clobber each other

  Scenario: Twenty threads each increment exactly once
    Given a pulse "counter" that increments "count"
    When 20 threads trigger "counter" at once
    Then the stored context field "count" equals 20
