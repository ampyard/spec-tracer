Feature: User Login

  @smoke
  Scenario: Successful login
    Given the user is on the login page

  @smoke
  Scenario: Failed login
    Given the user enters wrong password
