from pathlib import Path
import sys

import pytest

from unified_test_tracer.parsers import FeatureParser, JunitParser, CucumberParser
from unified_test_tracer.models import TestResult
from unified_test_tracer.renderers import _required_status
from unified_test_tracer.cli import _parse_args


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


def parse_args():
    return _parse_args()


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
def test_parse_args_supports_repeated_integration_flags(tag, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_pyramid.py",
            "--features",
            "features",
            "--integration",
            "one.xml",
            "--integration",
            "two.xml",
            "--output",
            "report.html",
        ],
    )

    args = parse_args()

    assert args.integration == ["one.xml", "two.xml"]


@pytest.mark.parametrize("tag", ["@FC-004"])
def test_parse_args_supports_repeated_unit_flags(tag, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_pyramid.py",
            "--features",
            "features",
            "--unit",
            "one.xml",
            "--unit",
            "two.xml",
            "--output",
            "report.html",
        ],
    )

    args = parse_args()

    assert args.unit == ["one.xml", "two.xml"]


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
    assert "@require:unit" not in scenario.tags
    assert "@require:e2e" not in scenario.tags


@pytest.mark.parametrize("tag", ["@FC-005"])
def test_require_tags_stored_as_required_layers(tag):
    scenarios = _parse_feature_file(FIXTURES / "phase4" / "features" / "login.feature")
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert "unit" in scenario.required_layers
    assert "e2e" in scenario.required_layers
    assert "integration" not in scenario.required_layers


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
