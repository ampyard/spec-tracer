Feature: Layer Requirement Checks

  @FC-005 @require-unit @require-e2e
  Scenario: Report flags missing e2e layer
    Given a scenario with unit and e2e requirements
    When only unit results exist
    Then the report shows e2e as missing
