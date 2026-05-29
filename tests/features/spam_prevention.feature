Feature: Spam and duplication prevention
  As a job author
  I want seen-sets and throttles stored in context
  So that repeated wake-ups do not produce duplicate or rapid-fire actions

  Scenario: Seen-set suppresses a duplicate id
    Given a pulse "dedup" that records id "msg-1" in seen set "seen"
    When I trigger "dedup"
    Then the recorded id was new
    When I trigger "dedup"
    Then the recorded id was not new

  Scenario: Throttle blocks a rapid repeat
    Given a pulse "throttle" with a 3600 second throttle on "last_run"
    When I trigger "throttle"
    Then the action was allowed
    When I trigger "throttle"
    Then the action was blocked
