Feature: Module Scoped Layer Requirements

  @FC-007 @require-unit:parsers
  Scenario: Report requires unit coverage from the parsers module
    Given a scenario tagged "@FC-007" requiring unit coverage from module "parsers"
    When only unit results exist
    Then the report shows unit as satisfied
