Feature: Test Coverage Tool Internals

  @FC-007
  Scenario: Malformed JUnit XML input is rejected with a clear error
    Given a feature file with scenario tagged "@FC-EDGE-006"
    And a unit JUnit XML result tagged "@FC-EDGE-006"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 1

  @FC-008
  Scenario: Aggregator computes pyramid and health metrics
    Given a feature file with scenario tagged "@FC-002"
    And a unit JUnit XML result tagged "@FC-002"
    And an E2E Cucumber JSON result tagged "@FC-002"
    When I run the tool with --features, --unit, --e2e, and --output
    Then the exit code should be 0
    And the report should contain "Test Pyramid"
    And the report should contain "Health Check"

  @FC-009
  Scenario: Dashboard renders multi-page navigation
    Given a feature file with scenario tagged "@FC-006"
    And a unit JUnit XML result tagged "@FC-006"
    And an E2E Cucumber JSON result tagged "@FC-006"
    When I run the tool with --features, --unit, --e2e, and --output
    Then the exit code should be 0
    And the report should contain "Feature Breakdown"
    And the report should contain "page-features"
    And the report should contain "Unified Test Tracer"
