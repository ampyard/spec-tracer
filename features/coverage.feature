Feature: Test Coverage Report

  @FC-001
  Scenario: Generate report with linked unit and E2E coverage
    Given a feature file with scenario tagged "@FC-001"
    And a unit JUnit XML result tagged "@FC-001"
    And an E2E Cucumber JSON result tagged "@FC-001"
    When I run the tool with --features, --unit, --e2e, and --output
    Then the exit code should be 0
    And the report should contain "1/1 scenarios tested"
    And the report should contain "<strong>e2e</strong>"
    And the report should contain "<strong>unit</strong>"

  @FC-002
  Scenario: Report shows passed, failed, and skipped statuses
    Given a feature file with scenario tagged "@FC-002"
    And a unit JUnit XML result tagged "@FC-002"
    And an E2E Cucumber JSON result tagged "@FC-002"
    When I run the tool with --features, --unit, --e2e, and --output
    Then the exit code should be 0
    And the report should contain "(passed)"
    And the report should contain "(failed)"
    And the report should contain "(skipped)"
