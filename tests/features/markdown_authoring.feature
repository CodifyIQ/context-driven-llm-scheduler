Feature: Frontmatter-optional pulse authoring
  As a job author
  I want a plain markdown file to be a valid pulse
  So that the simple case needs no frontmatter and the id comes from the filename

  Scenario: A prose-only file is a pulse whose id is the filename
    Given a pulse file "daily-digest.md" containing
      """
      Summarize what happened today and write it down.
      """
    Then the loaded pulse id is "daily-digest"
    And the loaded pulse instructions contain "Summarize what happened today"

  Scenario: A prose-only pulse triggers like any other
    Given a pulse file "watcher.md" containing
      """
      Watch the thing.
      """
    And the loaded pulse increments "count"
    When I trigger "watcher"
    Then the context field "count" equals 1

  Scenario: Frontmatter id still overrides the filename
    Given a pulse file "on-disk-name.md" containing
      """
      ---
      id: chosen-id
      schedule: "*/15 * * * *"
      ---
      Do the work.
      """
    Then the loaded pulse id is "chosen-id"
    And the pulse schedule is "*/15 * * * *"

  Scenario: Markdown with no id and no filename is rejected
    When I parse pulse markdown
      """
      Just instructions, no id anywhere.
      """
    Then a ValueError was raised
