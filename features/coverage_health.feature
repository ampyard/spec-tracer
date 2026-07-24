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

  @FC-011 @require-unit:aggregator @require-e2e:aggregator
  Scenario: CI gate fails the build when a listed health check is red
    Given a feature file with scenario tagged "@FC-011"
    And a unit JUnit XML result tagged "@FC-011"
    And the config gates CI on the "progress" health check
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 1

  @FC-011 @require-unit:aggregator @require-e2e:aggregator
  Scenario: CI gate stays green when the listed health check is healthy
    Given a feature file with scenario tagged "@FC-011"
    And a unit JUnit XML result tagged "@FC-011"
    And the config gates CI on the "pyramid" health check
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0

  @FC-011 @require-unit:aggregator @require-e2e:aggregator
  Scenario: A failing health check is only visual without a CI gate
    Given a feature file with scenario tagged "@FC-011"
    And a unit JUnit XML result tagged "@FC-011"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0

