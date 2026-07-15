Feature: User Login

  @FC-001
  Scenario: Successful login with valid credentials
    Given the user is on the login page
    When they enter valid credentials
    Then they should be redirected to the dashboard
