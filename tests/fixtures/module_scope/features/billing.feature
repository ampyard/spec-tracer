Feature: Module Scoped Layer Requirements

  @FC-007 @require-unit:billing
  Scenario: Report requires unit coverage from the billing module
    Given a scenario tagged "@FC-007" requiring unit coverage from module "billing"
    When only unit results exist
    Then the report shows unit as satisfied
