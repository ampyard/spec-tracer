from pathlib import Path

import pytest

from conftest import run_tool


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "missing_required_layer"
FEATURES = FIXTURES / "features"
UNIT = FIXTURES / "unit.xml"
OUTPUT = FIXTURES / "report.html"


@pytest.mark.parametrize("tag", ["@FC-005"])
def test_cli_flags_missing_required_layer(tag):
    result = run_tool(FEATURES, OUTPUT, unit=UNIT)

    assert result.returncode == 0, result.stderr
    assert OUTPUT.exists()

    content = OUTPUT.read_text(encoding="utf-8")
    assert "Testing Progress" in content
    assert "Report flags missing e2e layer" in content
    assert "0/1 scenarios satisfied" in content
    assert "Required" in content
    assert "unit" in content
    assert "e2e" in content
    assert "required-chip ok" in content
    assert "required-chip missing" in content
