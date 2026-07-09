Feature: Module Scoped Layer Requirements

  @FC-007 @require-unit:billing
  Scenario: Report marks the requirement satisfied when the module matches
    Given a feature file with scenario tagged "@FC-007"
    And a module-scoped unit JUnit XML result tagged "@FC-007" for module "billing"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0
    And the report should contain "unit"
    And the report should contain "required-chip ok"

  @FC-007 @require-unit:billing
  Scenario: Report flags the requirement missing when the module does not match
    Given a feature file with scenario tagged "@FC-007"
    And a module-scoped unit JUnit XML result tagged "@FC-007" for module "other"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0
    And the report should contain "required-chip missing"
