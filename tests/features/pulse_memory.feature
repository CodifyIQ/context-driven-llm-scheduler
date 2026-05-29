Feature: Markdown pulses and the memory protocol
  As a pulse author
  I want a pulse defined in markdown to carry memory across wake-ups
  So that the model gets the right context in and its decisions persist out

  Scenario: Frontmatter parses schedule, throttle, and retention
    Given a pulse defined by markdown
      """
      ---
      id: triage
      schedule: "*/15 * * * *"
      throttle: { notify: 1h }
      keep: { notes: 2, seen: 500 }
      ---
      Triage the inbox.
      """
    Then the pulse schedule is "*/15 * * * *"
    And the pulse throttle "notify" is 3600 seconds
    And the pulse keep "notes" is 2

  Scenario: A pulse handler's memory operations persist
    Given a pulse defined by markdown
      """
      ---
      id: triage
      throttle: { notify: 1h }
      ---
      Triage the inbox.
      """
    And a handler emitting memory operations
      """
      [{"op": "note", "text": "did a thing"},
       {"op": "seen", "field": "emails", "id": "msg-1"},
       {"op": "throttle", "field": "notify"},
       {"op": "set", "key": "mood", "value": "calm"}]
      """
    When I trigger "triage"
    Then memory note 0 equals "did a thing"
    And memory has seen "emails" id "msg-1"
    And memory throttle "notify" is stamped
    And memory fact "mood" equals "calm"

  Scenario: Seen ids dedupe and notes respect retention across triggers
    Given a pulse defined by markdown
      """
      ---
      id: triage
      keep: { notes: 2 }
      ---
      Triage the inbox.
      """
    And a handler emitting memory operations
      """
      [{"op": "note", "text": "tick"},
       {"op": "seen", "field": "emails", "id": "msg-1"}]
      """
    When I trigger "triage" 3 times
    Then memory has 2 notes
    And memory has seen "emails" id "msg-1"
    And the recorded seen set "emails" has 1 item

  Scenario: recall surfaces instructions and remembered notes
    Given a pulse defined by markdown
      """
      ---
      id: triage
      ---
      Triage the inbox carefully.
      """
    And the pulse memory has note "earlier observation"
    When I recall the pulse
    Then the recalled prompt contains "Triage the inbox carefully."
    And the recalled prompt contains "earlier observation"

  Scenario: compact folds older notes into one durable summary
    Given a pulse defined by markdown
      """
      ---
      id: triage
      ---
      Triage the inbox.
      """
    And the pulse memory has note "first"
    And the pulse memory has note "second"
    And the pulse memory has note "third"
    When I compact the pulse keeping 1 notes with summary "DIGEST"
    Then the compaction prompt contains "first"
    And the compacted notes number 2
    And a compacted note contains "DIGEST"
    And a compacted note contains "third"
    And no compacted note contains "first"

  Scenario: malformed frontmatter is rejected, not silently misparsed
    When I parse pulse markdown
      """
      ---
      id: triage
      throttle: { notify: { nested: bad } }
      ---
      Triage the inbox.
      """
    Then a ValueError was raised

  Scenario: recall budgeting drops oldest notes to fit a token ceiling
    Given a pulse defined by markdown
      """
      ---
      id: triage
      ---
      Triage the inbox.
      """
    And the pulse memory has note "ALPHA flagged a stuck deploy on the billing service worker queue last night"
    And the pulse memory has note "OMEGA confirmed the cache warmer finished and latency returned to normal again"
    When I recall the pulse with a 32 token ceiling
    Then the recalled prompt contains "OMEGA"
    And the recalled prompt contains "omitting"
    And the recalled prompt does not contain "ALPHA"
