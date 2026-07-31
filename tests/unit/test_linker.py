import pytest

from spec_tracer.linker import ResultLinker
from spec_tracer.models import Scenario, TestResult


@pytest.mark.parametrize("tag", ["@scenario:FC-001"])
def test_link_matches_result_to_scenario_by_id_and_scenario_tag(tag):
    scenario = Scenario(feature="F", name="S1", tags=["@id:FC-001"])
    unit_result = TestResult(layer="unit", name="u1", tags=["@scenario:FC-001"])
    e2e_result = TestResult(layer="e2e", name="e1", tags=["@scenario:FC-001"])

    links = ResultLinker.link([scenario], [unit_result, e2e_result])

    assert links[id(scenario)] == [unit_result, e2e_result]


@pytest.mark.parametrize("tag", ["@scenario:FC-001"])
def test_link_ignores_results_with_no_matching_scenario_tag(tag):
    scenario = Scenario(feature="F", name="S1", tags=["@id:FC-001"])
    other_result = TestResult(layer="unit", name="u1", tags=["@scenario:FC-999"])

    links = ResultLinker.link([scenario], [other_result])

    assert links[id(scenario)] == []


@pytest.mark.parametrize("tag", ["@scenario:FC-002"])
def test_link_preserves_result_status_for_passed_failed_and_skipped(tag):
    scenario = Scenario(feature="F", name="S1", tags=["@id:FC-002"])
    passed = TestResult(layer="unit", name="p", tags=["@scenario:FC-002"], status="passed")
    failed = TestResult(layer="unit", name="f", tags=["@scenario:FC-002"], status="failed")
    skipped = TestResult(layer="unit", name="s", tags=["@scenario:FC-002"], status="skipped")

    links = ResultLinker.link([scenario], [passed, failed, skipped])

    assert [r.status for r in links[id(scenario)]] == ["passed", "failed", "skipped"]


@pytest.mark.parametrize("tag", ["@scenario:FC-002"])
def test_link_matches_a_result_carrying_any_of_multiple_scenario_tags(tag):
    scenario = Scenario(feature="F", name="S1", tags=["@id:FC-002"])
    multi_tagged = TestResult(layer="unit", name="u1", tags=["@scenario:FC-999", "@scenario:FC-002"])

    links = ResultLinker.link([scenario], [multi_tagged])

    assert links[id(scenario)] == [multi_tagged]


def test_link_matches_scenario_carrying_multiple_id_tags():
    scenario = Scenario(feature="F", name="S1", tags=["@id:FC-100", "@id:FC-200"])
    result = TestResult(layer="unit", name="u1", tags=["@scenario:FC-200"])

    links = ResultLinker.link([scenario], [result])

    assert links[id(scenario)] == [result]


def test_link_returns_empty_list_for_every_scenario_when_no_results():
    scenarios = [Scenario(feature="F", name="S1", tags=["@id:FC-001"])]

    links = ResultLinker.link(scenarios, [])

    assert links[id(scenarios[0])] == []
