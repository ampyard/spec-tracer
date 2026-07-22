Feature: Test Coverage Linking

  @FC-001 @require-unit:linker @require-e2e:linker
  Scenario: Generate report with linked unit and E2E coverage
    Given a feature file with scenario tagged "@FC-001"
    And a unit JUnit XML result tagged "@FC-001"
    And the unit result is scoped to module "linker"
    And an E2E Cucumber JSON result tagged "@FC-001"
    When I run the tool with --features, --unit, --e2e, and --output
    Then the exit code should be 0
    And the report should contain "1/1 scenarios tested"
    And the report should contain "<strong>e2e</strong>"
    And the report should contain "<strong>unit</strong>"

  @FC-002 @require-unit:linker @require-e2e:linker
  Scenario: Report shows passed, failed, and skipped statuses
    Given a feature file with scenario tagged "@FC-002"
    And a unit JUnit XML result tagged "@FC-002"
    And the unit result is scoped to module "linker"
    And an E2E Cucumber JSON result tagged "@FC-002"
    When I run the tool with --features, --unit, --e2e, and --output
    Then the exit code should be 0
    And the report should contain "badge passed"
    And the report should contain "badge failed"
    And the report should contain "badge skipped"

  @FC-003 @require-integration:linker @require-e2e:linker
  Scenario: Generate report with linked integration coverage
    Given a feature file with scenario tagged "@FC-003"
    And an integration JUnit XML result tagged "@FC-003"
    And the integration result is scoped to module "linker"
    When I run the tool with --features, --integration, and --output
    Then the exit code should be 0
    And the report should contain "1/1 scenarios tested"
    And the report should contain "<strong>integration</strong>"

  @FC-004 @require-unit:collectors @require-integration:collectors @require-e2e:collectors
  Scenario: Generate report when unit and integration flags are repeated
    Given a feature file with scenario tagged "@FC-004"
    And a unit JUnit XML result tagged "@FC-004"
    And the unit result is scoped to module "collectors"
    And an integration JUnit XML result tagged "@FC-004"
    And the integration result is scoped to module "collectors"
    When I run the tool with --features, --unit, --integration, and --output
    Then the exit code should be 0
    And the report should contain "1/1 scenarios tested"
    And the report should contain "<strong>unit</strong>"
    And the report should contain "<strong>integration</strong>"
