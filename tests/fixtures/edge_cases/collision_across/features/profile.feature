Feature: User Profile

  @FC-001
  Scenario: View profile
    Given the user is logged in
    When they view their profile
    Then they should see their details
