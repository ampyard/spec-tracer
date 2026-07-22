Feature: Test Coverage Health Signals

  @FC-005 @require-unit:aggregator @require-e2e:aggregator
  Scenario: Report flags missing required layer
    Given a feature file with scenario tagged "@FC-005"
    And a unit JUnit XML result tagged "@FC-005"
    And the unit result is scoped to module "aggregator"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0
    And the report should contain "0/1 scenarios complete"
    And the report should contain "Required"
    And the report should contain "required-chip ok"
    And the report should contain "required-chip missing"
