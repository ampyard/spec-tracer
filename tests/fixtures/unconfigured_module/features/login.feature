Feature: Module Configuration Checks

  @id:FC-012 @require-unit @require-e2e:shipping
  Scenario: Report flags an e2e module that was never configured
    Given a scenario with unit and e2e:shipping requirements
    When only unit results exist and e2e is never configured
    Then the report shows e2e:shipping as unconfigured, not missing
