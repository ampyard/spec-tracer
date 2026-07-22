from pathlib import Path
import subprocess
import sys

import pytest

from conftest import run_tool


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "edge_cases"


def test_edge_case_pytest_junit_contains_tag(tmp_path):
    xml_path = tmp_path / "edge.xml"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration/test_edge_cases.py",
            "-k",
            "tag_collision_across_features",
            "--junitxml",
            str(xml_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "@FC-EDGE-001" in xml_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("tag", ["@FC-EDGE-001"])
def test_tag_collision_across_features(tag):
    """One test tagged @FC-001 links to scenarios in both feature files."""
    base = FIXTURES / "collision_across"
    output = base / "report.html"
    result = run_tool(base / "features", output, unit=base / "unit.xml")
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "Successful login" in content
    assert "View profile" in content
    assert "<strong>unit</strong>" in content
    assert "0/2 scenarios satisfied" in content


@pytest.mark.parametrize("tag", ["@FC-EDGE-002"])
def test_tag_collision_within_feature(tag):
    """One test tagged @smoke links to both scenarios sharing that tag."""
    base = FIXTURES / "collision_within"
    output = base / "report.html"
    result = run_tool(base / "features", output, unit=base / "unit.xml")
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "Successful login" in content
    assert "Failed login" in content
    assert "0/2 scenarios satisfied" in content


@pytest.mark.parametrize("tag", ["@FC-EDGE-003"])
def test_feature_level_tags_not_inherited(tag):
    """Tags on Feature: line are NOT inherited by scenarios.

    The scenario ``@FC-001`` links to the matching unit test, so coverage is
    0/1 under the presence-based basis (the linked unit result does not satisfy
    the default injected ``e2e`` requirement). The other unit test carries
    ``@FeatureTag`` (taken from its name), which matches no scenario — it must
    appear under Unlinked Tests rather than being silently dropped.
    """
    base = FIXTURES / "feature_tags_not_inherited"
    output = base / "report.html"
    result = run_tool(base / "features", output, unit=base / "unit.xml")
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    # @FC-001 test should link (scenario-level tag)
    assert "<strong>unit</strong>" in content
    # Only the @FC-001 scenario exists, but its default e2e requirement is unmet
    assert "0/1 scenarios satisfied" in content
    # The @FeatureTag test matches no scenario and must be listed as unlinked
    assert "Unlinked Tests" in content
    assert "test_feature_tag_@FeatureTag" in content


@pytest.mark.parametrize("tag", ["@FC-EDGE-004"])
def test_no_matching_tags_shows_incomplete(tag):
    """Scenario with no matching test results shows as incomplete."""
    base = FIXTURES / "no_match"
    output = base / "report.html"
    result = run_tool(base / "features", output, unit=base / "unit.xml")
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "0/1 scenarios satisfied" in content
    assert "<strong>unit</strong>" not in content


@pytest.mark.parametrize("tag", ["@FC-EDGE-005"])
def test_empty_result_file_produces_zero_tests(tag):
    """Empty <testsuites/> produces zero unit results, scenario is incomplete."""
    base = FIXTURES / "empty_result"
    output = base / "report.html"
    result = run_tool(base / "features", output, unit=base / "unit.xml")
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "0/1 scenarios satisfied" in content
    assert "<strong>unit</strong>" not in content

@pytest.mark.parametrize("tag", ["@FC-EDGE-006"])
def test_malformed_junit_xml_errors(tag):
    """Malformed JUnit XML aborts with a clear error."""
    base = FIXTURES / "malformed_xml"
    output = base / "report.html"
    result = run_tool(base / "features", output, unit=base / "unit.xml")
    assert result.returncode != 0
