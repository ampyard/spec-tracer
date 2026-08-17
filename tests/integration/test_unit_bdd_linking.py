from pathlib import Path

import pytest

from conftest import run_tool


ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "tests" / "fixtures" / "unit_bdd_linking" / "features"
UNIT = ROOT / "tests" / "fixtures" / "unit_bdd_linking" / "unit.json"
OUTPUT = ROOT / "tests" / "fixtures" / "unit_bdd_linking" / "report.html"


@pytest.mark.parametrize("tag", ["@scenario:FC-013"])
def test_cli_links_unit_layer_cucumber_json_result(tag):
    """A unit-layer result can be a Cucumber JSON scenario, not just JUnit XML.

    Format is auto-detected per file, so `unit` config entries work the same
    whether the underlying test framework is JUnit-based or BDD-based.
    """
    result = run_tool(FEATURES, OUTPUT, unit=UNIT)

    assert result.returncode == 0, result.stderr
    assert OUTPUT.exists()

    content = OUTPUT.read_text(encoding="utf-8")
    assert "Successful login with valid credentials" in content
    assert "<strong>0/1</strong>" in content
    assert "scenarios fully matched" in content
    assert "<strong>unit</strong>" in content
    assert "Login form accepts valid credentials" in content
