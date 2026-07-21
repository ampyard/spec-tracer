Feature: Module Scoped Layer Requirements

  @FC-007 @require-unit:parsers
  Scenario: Report requires unit coverage from the parsers module
    Given a scenario tagged "@FC-007" requiring unit coverage from module "parsers"
    When only unit results exist
    Then the report shows unit as satisfied

  @FC-007 @require-e2e:parsers
  Scenario: Report requires e2e coverage from the parsers module
    Given a scenario tagged "@FC-007" requiring e2e coverage from module "parsers"
    When only e2e results exist
    Then the report shows e2e as satisfied
