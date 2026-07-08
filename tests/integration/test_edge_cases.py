from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "edge_cases"


def test_tag_collision_across_features():
    """One test tagged @FC-001 links to scenarios in both feature files."""
    base = FIXTURES / "collision_across"
    output = base / "report.html"
    result = subprocess.run(
        [sys.executable, "build_pyramid.py",
         "--features", str(base / "features"),
         "--unit", str(base / "unit.xml"),
         "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "Successful login" in content
    assert "View profile" in content
    assert "<strong>unit</strong>" in content
    assert "2/2 scenarios tested" in content


def test_tag_collision_within_feature():
    """One test tagged @smoke links to both scenarios sharing that tag."""
    base = FIXTURES / "collision_within"
    output = base / "report.html"
    result = subprocess.run(
        [sys.executable, "build_pyramid.py",
         "--features", str(base / "features"),
         "--unit", str(base / "unit.xml"),
         "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "Successful login" in content
    assert "Failed login" in content
    assert "2/2 scenarios tested" in content


def test_feature_level_tags_not_inherited():
    """Tags on Feature: line are NOT inherited by scenarios."""
    base = FIXTURES / "feature_tags_not_inherited"
    output = base / "report.html"
    result = subprocess.run(
        [sys.executable, "build_pyramid.py",
         "--features", str(base / "features"),
         "--unit", str(base / "unit.xml"),
         "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    # @FC-001 test should link (scenario-level tag)
    assert "<strong>unit</strong>" in content
    # @FeatureTag test should NOT link (not on scenario)
    # Only 1 of 2 tests match, but scenario is tested via @FC-001
    assert "1/1 scenarios tested" in content
    assert "test_feature_tag_@FeatureTag" not in content


def test_no_matching_tags_shows_untested():
    """Scenario with no matching test results shows as untested."""
    base = FIXTURES / "no_match"
    output = base / "report.html"
    result = subprocess.run(
        [sys.executable, "build_pyramid.py",
         "--features", str(base / "features"),
         "--unit", str(base / "unit.xml"),
         "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "untested" in content
    assert "0/1 scenarios tested" in content
    assert "<strong>unit</strong>" not in content


def test_empty_result_file_produces_zero_tests():
    """Empty <testsuites/> produces zero unit results, scenario is untested."""
    base = FIXTURES / "empty_result"
    output = base / "report.html"
    result = subprocess.run(
        [sys.executable, "build_pyramid.py",
         "--features", str(base / "features"),
         "--unit", str(base / "unit.xml"),
         "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "untested" in content
    assert "0/1 scenarios tested" in content


def test_malformed_junit_xml_errors():
    """Malformed JUnit XML aborts with a clear error."""
    base = FIXTURES / "malformed_xml"
    output = base / "report.html"
    result = subprocess.run(
        [sys.executable, "build_pyramid.py",
         "--features", str(base / "features"),
         "--unit", str(base / "unit.xml"),
         "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
