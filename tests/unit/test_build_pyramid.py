import json
from pathlib import Path

import pytest

from unified_test_tracer.parsers import FeatureParser, JunitParser, CucumberParser
from unified_test_tracer.models import TestResult
from unified_test_tracer.renderers import _required_status
from unified_test_tracer.cli import _collect_and_parse_junit_results, _load_config


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"

_feature_parser = FeatureParser()
_junit_parser = JunitParser()
_cucumber_parser = CucumberParser()


def _parse_feature_file(path):
    return _feature_parser.parse(path)


def _parse_e2e_results(paths):
    return _cucumber_parser.parse(paths, layer="e2e")


def _parse_junit_results(paths, layer="unit"):
    return _junit_parser.parse(paths, layer=layer)


@pytest.mark.parametrize("tag", ["@FC-001"])
def test_parse_feature_file_returns_scenarios(tag):
    scenarios = _parse_feature_file(FIXTURES / "phase1" / "features" / "login.feature")
    assert len(scenarios) == 1
    assert scenarios[0].name == "Successful login with valid credentials"
    assert tag in scenarios[0].tags


@pytest.mark.parametrize("tag", ["@FC-001"])
def test_parse_e2e_results_extracts_tags(tag):
    results = _parse_e2e_results([FIXTURES / "phase1" / "e2e.json"])
    assert len(results) == 1
    assert results[0].layer == "e2e"
    assert tag in results[0].tags


@pytest.mark.parametrize("tag", ["@FC-001"])
def test_parse_junit_results_extracts_tags(tag):
    results = _parse_junit_results([FIXTURES / "phase2" / "unit.xml"])
    assert len(results) == 1
    assert results[0].layer == "unit"
    assert tag in results[0].tags


@pytest.mark.parametrize("tag", ["@FC-007"])
def test_parse_junit_results_extracts_tags_from_classname_and_properties(tag, tmp_path):
    xml_path = tmp_path / "integration.xml"
    xml_path.write_text(
        """<testsuite><testcase classname=\"tests.integration @FC-004\" name=\"some test\"><properties><property name=\"@FC-005\" value=\"x\" /></properties></testcase></testsuite>""",
        encoding="utf-8",
    )

    results = _parse_junit_results([xml_path], layer="integration")

    assert len(results) == 1
    assert results[0].layer == "integration"
    assert "@FC-004" in results[0].tags
    assert "@FC-005" in results[0].tags


@pytest.mark.parametrize("tag", ["@FC-007"])
def test_parse_junit_results_raises_clear_error_on_malformed_xml(tag, tmp_path):
    xml_path = tmp_path / "broken.xml"
    xml_path.write_text("<testsuite><testcase></testsuite>", encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed JUnit XML"):
        _parse_junit_results([xml_path], layer="integration")


@pytest.mark.parametrize("tag", ["@FC-004"])
def test_load_config_requires_features_and_output(tag, tmp_path):
    config_path = tmp_path / "spectracer.config.json"
    config_path.write_text(json.dumps({"features": ["features"]}), encoding="utf-8")

    with pytest.raises(ValueError, match="output"):
        _load_config(config_path)


@pytest.mark.parametrize("tag", ["@FC-004"])
def test_collect_and_parse_junit_results_groups_by_module(tag, tmp_path):
    module_a = tmp_path / "a.xml"
    module_a.write_text(
        '<testsuite><testcase name="test_a @FC-004" time="0.1" /></testsuite>', encoding="utf-8"
    )
    module_b = tmp_path / "b.xml"
    module_b.write_text(
        '<testsuite><testcase name="test_b @FC-004" time="0.1" /></testsuite>', encoding="utf-8"
    )

    results = _collect_and_parse_junit_results(
        {"billing": [str(module_a)], "": [str(module_b)]}, _junit_parser, "unit"
    )

    modules = {r.module for r in results}
    assert modules == {"billing", ""}
    assert all(r.layer == "unit" for r in results)


@pytest.mark.parametrize("tag", ["@FC-002"])
def test_parse_junit_results_passed_failed_skipped(tag):
    results = _parse_junit_results([FIXTURES / "fc002" / "unit.xml"])
    assert len(results) == 3
    statuses = {r.status for r in results}
    assert statuses == {"passed", "failed", "skipped"}
    assert all(tag in r.tags for r in results)


@pytest.mark.parametrize("tag", ["@FC-002"])
def test_parse_e2e_results_passed_failed_skipped(tag):
    results = _parse_e2e_results([FIXTURES / "fc002" / "e2e.json"])
    assert len(results) == 3
    statuses = {r.status for r in results}
    assert statuses == {"passed", "failed", "skipped"}
    assert all(tag in r.tags for r in results)


@pytest.mark.parametrize("linking_tag", ["@FC-005"])
def test_require_tags_excluded_from_linking(linking_tag):
    scenarios = _parse_feature_file(FIXTURES / "phase4" / "features" / "login.feature")
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert linking_tag in scenario.tags
    assert "@require-unit" not in scenario.tags
    assert "@require-e2e" not in scenario.tags


@pytest.mark.parametrize("tag", ["@FC-005"])
def test_require_tags_stored_as_required_layers(tag):
    scenarios = _parse_feature_file(FIXTURES / "phase4" / "features" / "login.feature")
    assert len(scenarios) == 1
    scenario = scenarios[0]
    layers = [r.layer for r in scenario.required_layers]
    assert "unit" in layers
    assert "e2e" in layers
    assert "integration" not in layers


@pytest.mark.parametrize("tag", ["@FC-005"])
def test_require_layer_status_missing_e2e(tag, tmp_path):
    from unified_test_tracer.models import ScenarioView, Scenario
    scenario = _parse_feature_file(FIXTURES / "phase4" / "features" / "login.feature")[0]
    unit_result = TestResult(layer="unit", name="test", tags=["@FC-005"], status="passed")
    view = ScenarioView(scenario=scenario, linked_results=[unit_result])
    status = _required_status(view)
    assert "unit [OK]" in status
    assert "e2e [MISSING]" in status
    assert "integration" not in status
