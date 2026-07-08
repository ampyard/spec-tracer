from pathlib import Path
import pytest

from build_pyramid import parse_feature_file, parse_e2e_results, parse_junit_results


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
