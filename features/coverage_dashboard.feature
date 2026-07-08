Feature: Test Coverage Dashboard Rendering

  @FC-006 @require:unit @require:e2e
  Scenario: Report renders polished dashboard sections
    Given a feature file with scenario tagged "@FC-006"
    And a unit JUnit XML result tagged "@FC-006"
    And an E2E Cucumber JSON result tagged "@FC-006"
    When I run the tool with --features, --unit, --e2e, and --output
    Then the exit code should be 0
    And the report should contain "Scenario Coverage Progress"
    And the report should contain "Test Pyramid"
    And the report should contain "Health Check"
    And the report should contain "Search by tag, e.g. FC-001"
    And the report should contain "Failure Breakdown"
    And the report should contain "Unlinked Tests"
