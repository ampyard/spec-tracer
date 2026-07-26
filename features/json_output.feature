Feature: Machine Readable JSON Report

  @FC-010 @require-unit:report_model @require-e2e:report_model
  Scenario: JSON report is written alongside the HTML report and matches the schema
    Given a feature file with scenario tagged "@FC-002"
    And a unit JUnit XML result tagged "@FC-002"
    And an E2E Cucumber JSON result tagged "@FC-002"
    And the config requests a JSON report
    When I run the tool with --features, --unit, --e2e, and --output
    Then the exit code should be 0
    And the JSON report file should exist
    And the JSON report should conform to the SpecTracer report schema

  @FC-010 @require-unit:report_model @require-e2e:report_model
  Scenario: JSON report is not written when output_json is omitted
    Given a feature file with scenario tagged "@FC-001"
    And a unit JUnit XML result tagged "@FC-001"
    When I run the tool with --features, --unit, and --output
    Then the exit code should be 0
    And the JSON report file should not exist
