Feature: Integration Coverage

  @FC-003
  Scenario: Report shows integration coverage
    Given an integration result is present
    When the tool runs
    Then the report includes the integration layer
