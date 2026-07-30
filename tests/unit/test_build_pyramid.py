import json
from pathlib import Path

import pytest

from spec_tracer.parsers import FeatureParser, JunitParser, CucumberParser
from spec_tracer.models import TestResult
from spec_tracer.renderers import _required_status
from spec_tracer.cli import (
    _collect_and_parse_e2e_results,
    _collect_and_parse_features,
    _collect_and_parse_junit_results,
    _load_config,
)


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


def test_parse_feature_file_returns_scenarios():
    scenarios = _parse_feature_file(FIXTURES / "e2e_coverage" / "features" / "login.feature")
    assert len(scenarios) == 1
    assert scenarios[0].name == "Successful login with valid credentials"
    assert "@id:FC-001" in scenarios[0].tags


def test_parse_e2e_results_extracts_tags():
    results = _parse_e2e_results([FIXTURES / "e2e_coverage" / "e2e.json"])
    assert len(results) == 1
    assert results[0].layer == "e2e"
    assert "@scenario:FC-001" in results[0].tags


def test_parse_junit_results_extracts_tags():
    results = _parse_junit_results([FIXTURES / "unit_linking" / "unit.xml"])
    assert len(results) == 1
    assert results[0].layer == "unit"
    assert "@scenario:FC-001" in results[0].tags


def test_parse_junit_results_extracts_tags_from_classname_and_properties(tmp_path):
    xml_path = tmp_path / "integration.xml"
    xml_path.write_text(
        """<testsuite><testcase classname=\"tests.integration @scenario:FC-004\" name=\"some test\"><properties><property name=\"@scenario:FC-005\" value=\"x\" /></properties></testcase></testsuite>""",
        encoding="utf-8",
    )

    results = _parse_junit_results([xml_path], layer="integration")

    assert len(results) == 1
    assert results[0].layer == "integration"
    assert "@scenario:FC-004" in results[0].tags
    assert "@scenario:FC-005" in results[0].tags


def test_parse_junit_results_raises_clear_error_on_malformed_xml(tmp_path):
    xml_path = tmp_path / "broken.xml"
    xml_path.write_text("<testsuite><testcase></testsuite>", encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed JUnit XML"):
        _parse_junit_results([xml_path], layer="integration")


def test_load_config_requires_features_and_output(tmp_path):
    config_path = tmp_path / "spectracer.config.json"
    config_path.write_text(json.dumps({"features": ["features"]}), encoding="utf-8")

    with pytest.raises(ValueError, match="output"):
        _load_config(config_path)


def test_collect_and_parse_junit_results_groups_by_module(tmp_path):
    module_a = tmp_path / "a.xml"
    module_a.write_text(
        '<testsuite><testcase name="test_a @scenario:FC-004" time="0.1" /></testsuite>', encoding="utf-8"
    )
    module_b = tmp_path / "b.xml"
    module_b.write_text(
        '<testsuite><testcase name="test_b @scenario:FC-004" time="0.1" /></testsuite>', encoding="utf-8"
    )

    results = _collect_and_parse_junit_results(
        {"billing": [str(module_a)], "": [str(module_b)]}, _junit_parser, "unit"
    )

    modules = {r.module for r in results}
    assert modules == {"billing", ""}
    assert all(r.layer == "unit" for r in results)


def test_collect_and_parse_e2e_results_groups_by_module(tmp_path):
    tag = "@scenario:FC-007"
    module_a = tmp_path / "a.json"
    module_a.write_text(
        json.dumps(
            [
                {
                    "keyword": "Feature",
                    "name": "A",
                    "elements": [
                        {
                            "keyword": "Scenario",
                            "name": "a",
                            "tags": [{"name": tag}],
                            "steps": [],
                            "status": "passed",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    module_b = tmp_path / "b.json"
    module_b.write_text(
        json.dumps(
            [
                {
                    "keyword": "Feature",
                    "name": "B",
                    "elements": [
                        {
                            "keyword": "Scenario",
                            "name": "b",
                            "tags": [{"name": tag}],
                            "steps": [],
                            "status": "passed",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    results = _collect_and_parse_e2e_results(
        {"parsers": [str(module_a)], "": [str(module_b)]}, _cucumber_parser
    )

    modules = {r.module for r in results}
    assert modules == {"parsers", ""}
    assert all(r.layer == "e2e" for r in results)


def test_require_e2e_accepts_module_suffix():
    scenarios = _parse_feature_file(FIXTURES / "module_scope" / "features" / "parsers.feature")
    e2e_scenario = next(s for s in scenarios if any(r.layer == "e2e" for r in s.required_layers))
    e2e_req = next(r for r in e2e_scenario.required_layers if r.layer == "e2e")
    assert e2e_req.module == "parsers"


def test_parse_e2e_ignores_tag_filtered_unexecuted_scenarios(tmp_path):
    """Behave tag filters leave non-selected scenarios as skipped without step results."""
    tag = "@scenario:FC-007"
    path = tmp_path / "mixed.json"
    path.write_text(
        json.dumps(
            [
                {
                    "keyword": "Feature",
                    "name": "F",
                    "elements": [
                        {
                            "keyword": "Scenario",
                            "name": "ran",
                            "tags": [{"name": tag}],
                            "steps": [
                                {
                                    "keyword": "Given",
                                    "name": "x",
                                    "result": {"status": "passed", "duration": 1},
                                }
                            ],
                            "status": "passed",
                        },
                        {
                            "keyword": "Scenario",
                            "name": "tag-filtered never ran",
                            "tags": [{"name": "@scenario:FC-OTHER"}],
                            "steps": [
                                {"keyword": "Given", "name": "y", "location": "features/x.feature:1"}
                            ],
                            "status": "skipped",
                        },
                        {
                            "keyword": "Scenario",
                            "name": "real skip",
                            "tags": [{"name": tag}],
                            "steps": [
                                {
                                    "keyword": "Then",
                                    "name": "z",
                                    "result": {"status": "skipped"},
                                }
                            ],
                            "status": "skipped",
                        },
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    results = _parse_e2e_results([path])
    names = {r.name for r in results}
    assert names == {"ran", "real skip"}
    assert {r.status for r in results} == {"passed", "skipped"}


def test_parse_junit_results_passed_failed_skipped():
    results = _parse_junit_results([FIXTURES / "fc002" / "unit.xml"])
    assert len(results) == 3
    statuses = {r.status for r in results}
    assert statuses == {"passed", "failed", "skipped"}
    assert all("@scenario:FC-002" in r.tags for r in results)


def test_parse_e2e_results_passed_failed_skipped():
    results = _parse_e2e_results([FIXTURES / "fc002" / "e2e.json"])
    assert len(results) == 3
    statuses = {r.status for r in results}
    assert statuses == {"passed", "failed", "skipped"}
    assert all("@scenario:FC-002" in r.tags for r in results)


def test_require_tags_excluded_from_linking():
    scenarios = _parse_feature_file(FIXTURES / "missing_required_layer" / "features" / "login.feature")
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert "@id:FC-005" in scenario.tags
    assert "@require-unit" not in scenario.tags
    assert "@require-e2e" not in scenario.tags


def test_require_tags_stored_as_required_layers():
    scenarios = _parse_feature_file(FIXTURES / "missing_required_layer" / "features" / "login.feature")
    assert len(scenarios) == 1
    scenario = scenarios[0]
    layers = [r.layer for r in scenario.required_layers]
    assert "unit" in layers
    assert "e2e" in layers
    assert "integration" not in layers


def test_require_layer_status_missing_e2e(tmp_path):
    from spec_tracer.models import ScenarioView, Scenario
    scenario = _parse_feature_file(FIXTURES / "missing_required_layer" / "features" / "login.feature")[0]
    unit_result = TestResult(layer="unit", name="test", tags=["@scenario:FC-005"], status="passed")
    view = ScenarioView(scenario=scenario, linked_results=[unit_result])
    status = _required_status(view)
    assert "unit [OK]" in status
    assert "e2e [MISSING]" in status
    assert "integration" not in status


def test_collect_and_parse_features_returns_path_relative_to_base_dir(tmp_path):
    features_dir = tmp_path / "features"
    features_dir.mkdir()
    (features_dir / "login.feature").write_text(
        "Feature: Login\n\n  @id:FC-010\n  Scenario: Sign in\n    Given a user\n",
        encoding="utf-8",
    )

    scenarios, feature_files = _collect_and_parse_features([str(features_dir)], tmp_path)

    assert len(scenarios) == 1
    assert feature_files["Login"] == "features/login.feature"


def test_collect_and_parse_features_never_returns_absolute_path(tmp_path):
    config_dir = tmp_path / "config_dir"
    config_dir.mkdir()
    features_dir = tmp_path / "elsewhere" / "features"
    features_dir.mkdir(parents=True)
    (features_dir / "login.feature").write_text(
        "Feature: Login\n\n  @id:FC-010\n  Scenario: Sign in\n    Given a user\n",
        encoding="utf-8",
    )

    _, feature_files = _collect_and_parse_features([str(features_dir)], config_dir)

    path = feature_files["Login"]
    assert not Path(path).is_absolute()
    assert path == "../elsewhere/features/login.feature"
