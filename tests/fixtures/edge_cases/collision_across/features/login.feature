Feature: User Login

  @FC-001
  Scenario: Successful login
    Given the user is on the login page
    When they enter valid credentials
    Then they should be redirected
