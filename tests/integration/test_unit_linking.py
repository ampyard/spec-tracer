from pathlib import Path

import pytest

from conftest import run_tool


ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "tests" / "fixtures" / "unit_linking" / "features"
UNIT = ROOT / "tests" / "fixtures" / "unit_linking" / "unit.xml"
OUTPUT = ROOT / "tests" / "fixtures" / "unit_linking" / "report.html"


@pytest.mark.parametrize("tag", ["@FC-001"])
def test_cli_links_unit_results(tag):
    result = run_tool(FEATURES, OUTPUT, unit=UNIT)

    assert result.returncode == 0, result.stderr
    assert OUTPUT.exists()

    content = OUTPUT.read_text(encoding="utf-8")
    assert "Testing Progress" in content
    assert "Successful login with valid credentials" in content
    assert "1/1 scenarios complete" in content
    assert "<strong>unit</strong>" in content
    assert "@FC-001" in content
