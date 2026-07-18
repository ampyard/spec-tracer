Feature: Test Coverage Edge Cases

  @FC-EDGE-001
  Scenario: Generate report with linked edge case coverage
    Given a feature file with scenario tagged "@FC-EDGE-001"
    And a unit JUnit XML result tagged "@FC-EDGE-001"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0
    And the report should contain "2/2 scenarios tested"
    And the report should contain "<strong>unit</strong>"

  @FC-EDGE-002
  Scenario: One test tag links to multiple scenarios sharing that tag
    Given a feature file with scenario tagged "@FC-EDGE-002"
    And a unit JUnit XML result tagged "@FC-EDGE-002"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0
    And the report should contain "2/2 scenarios tested"

  @FC-EDGE-003
  Scenario: Tags on the Feature line are not inherited by scenarios
    Given a feature file with scenario tagged "@FC-EDGE-003"
    And a unit JUnit XML result tagged "@FC-EDGE-003"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0
    And the report should contain "1/1 scenarios tested"
    And the report should contain "<strong>unit</strong>"

  @FC-EDGE-004
  Scenario: Scenario with no matching test results shows as untested
    Given a feature file with scenario tagged "@FC-EDGE-004"
    And a unit JUnit XML result tagged "@FC-EDGE-004"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0
    And the report should contain "0/1 scenarios tested"
    And the report should contain "untested"
    And the report should list the unlinked test "test_unrelated_@OTHER-999"

  @FC-EDGE-004b
  Scenario: Untagged result with no matching scenario still appears as unlinked
    Given a feature file with scenario tagged "@FC-EDGE-004"
    And a unit JUnit XML result tagged "@FC-EDGE-004"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0
    And the report should contain "Unlinked Tests"
    And the report should list the unlinked test "test_unrelated_@OTHER-999"

  @FC-EDGE-005
  Scenario: Empty JUnit XML result file produces zero test results
    Given a feature file with scenario tagged "@FC-EDGE-005"
    And a unit JUnit XML result tagged "@FC-EDGE-005"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0
    And the report should contain "0/1 scenarios tested"
    And the report should contain "untested"

  @FC-EDGE-006
  Scenario: Malformed JUnit XML aborts with a non-zero exit code
    Given a feature file with scenario tagged "@FC-EDGE-006"
    And a unit JUnit XML result tagged "@FC-EDGE-006"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 1
