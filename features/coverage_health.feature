Feature: Test Coverage Health Signals

  @FC-005 @require:unit @require:e2e
  Scenario: Report flags missing required layer
    Given a feature file with scenario tagged "@FC-005"
    And a unit JUnit XML result tagged "@FC-005"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0
    And the report should contain "1/1 scenarios tested"
    And the report should contain "Required"
    And the report should contain "required-chip ok"
    And the report should contain "required-chip missing"
