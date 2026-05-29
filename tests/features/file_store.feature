Feature: FileStore persistence
  As a library user
  I want the file store to round-trip contexts and handle missing keys
  So that pulse state survives between processes

  Scenario: A missing key loads as an empty context
    Then loading key "never-saved" returns an empty context

  Scenario: Nested JSON round-trips intact
    When I save context {"a": {"b": [1, 2, 3]}, "n": 5} under key "k1"
    Then loading key "k1" returns context {"a": {"b": [1, 2, 3]}, "n": 5}

  Scenario: Delete removes the stored context
    When I save context {"x": 1} under key "k2"
    And I delete key "k2"
    Then loading key "k2" returns an empty context
