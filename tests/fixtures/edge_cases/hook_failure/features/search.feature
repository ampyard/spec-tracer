Feature: Search

  @id:FC-EDGE-007
  Scenario: Basic DuckDuckGo Search
    Given the browser is launched
    When the user searches for "spec-tracer"
    Then results should be displayed
