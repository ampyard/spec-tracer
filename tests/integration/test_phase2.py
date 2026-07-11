from pathlib import Path

import pytest

from conftest import run_tool


ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "tests" / "fixtures" / "phase2" / "features"
UNIT = ROOT / "tests" / "fixtures" / "phase2" / "unit.xml"
OUTPUT = ROOT / "tests" / "fixtures" / "phase2" / "report.html"


@pytest.mark.parametrize("tag", ["@FC-001"])
def test_phase2_cli_links_unit_results(tag):
    result = run_tool(FEATURES, OUTPUT, unit=UNIT)

    assert result.returncode == 0, result.stderr
    assert OUTPUT.exists()

    content = OUTPUT.read_text(encoding="utf-8")
    assert "Testing Progress" in content
    assert "Successful login with valid credentials" in content
    assert "1/1 scenarios tested" in content
    assert "<strong>unit</strong>" in content
    assert "@FC-001" in content
