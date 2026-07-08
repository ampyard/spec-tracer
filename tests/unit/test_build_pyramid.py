from pathlib import Path
import sys

import pytest

from build_pyramid import parse_args, parse_feature_file, parse_e2e_results, parse_junit_results


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


@pytest.mark.parametrize("tag", ["@FC-001"])
def test_parse_feature_file_returns_scenarios(tag):
    scenarios = parse_feature_file(FIXTURES / "phase1" / "features" / "login.feature")
    assert len(scenarios) == 1
    assert scenarios[0].name == "Successful login with valid credentials"
    assert tag in scenarios[0].tags


@pytest.mark.parametrize("tag", ["@FC-001"])
def test_parse_e2e_results_extracts_tags(tag):
    results = parse_e2e_results([FIXTURES / "phase1" / "e2e.json"])
    assert len(results) == 1
    assert results[0].layer == "e2e"
    assert tag in results[0].tags


@pytest.mark.parametrize("tag", ["@FC-001"])
def test_parse_junit_results_extracts_tags(tag):
    results = parse_junit_results([FIXTURES / "phase2" / "unit.xml"])
    assert len(results) == 1
    assert results[0].layer == "unit"
    assert tag in results[0].tags


def test_parse_junit_results_extracts_tags_from_classname_and_properties(tmp_path):
    xml_path = tmp_path / "integration.xml"
    xml_path.write_text(
        """<testsuite><testcase classname=\"tests.integration @FC-004\" name=\"some test\"><properties><property name=\"@FC-005\" value=\"x\" /></properties></testcase></testsuite>""",
        encoding="utf-8",
    )

    results = parse_junit_results([xml_path], layer="integration")

    assert len(results) == 1
    assert results[0].layer == "integration"
    assert "@FC-004" in results[0].tags
    assert "@FC-005" in results[0].tags


def test_parse_junit_results_raises_clear_error_on_malformed_xml(tmp_path):
    xml_path = tmp_path / "broken.xml"
    xml_path.write_text("<testsuite><testcase></testsuite>", encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed JUnit XML"):
        parse_junit_results([xml_path], layer="integration")


def test_parse_args_supports_repeated_integration_flags(monkeypatch):
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


def test_parse_args_supports_repeated_unit_flags(monkeypatch):
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
    results = parse_junit_results([FIXTURES / "fc002" / "unit.xml"])
    assert len(results) == 3
    statuses = {r.status for r in results}
    assert statuses == {"passed", "failed", "skipped"}
    assert all(tag in r.tags for r in results)


@pytest.mark.parametrize("tag", ["@FC-002"])
def test_parse_e2e_results_passed_failed_skipped(tag):
    results = parse_e2e_results([FIXTURES / "fc002" / "e2e.json"])
    assert len(results) == 3
    statuses = {r.status for r in results}
    assert statuses == {"passed", "failed", "skipped"}
    assert all(tag in r.tags for r in results)
