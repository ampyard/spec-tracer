from pathlib import Path

import pytest

from conftest import run_tool


ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "tests" / "fixtures" / "repeatable" / "features"
UNIT = ROOT / "tests" / "fixtures" / "repeatable" / "unit.xml"
INTEGRATION = ROOT / "tests" / "fixtures" / "repeatable" / "integration.xml"


@pytest.mark.parametrize("tag", ["@scenario:FC-004"])
def test_cli_accepts_repeated_unit_and_integration_flags(tag, tmp_path):
    output = tmp_path / "report.html"
    result = run_tool(
        FEATURES,
        output,
        unit={"collectors": [str(UNIT)]},
        integration={"collectors": [str(INTEGRATION)]},
    )

    assert result.returncode == 0, result.stderr
    assert output.exists()

    content = output.read_text(encoding="utf-8")
    assert "<strong>0/1</strong>" in content
    assert "scenarios fully matched" in content
    assert "<strong>unit</strong>" in content
    assert "<strong>integration</strong>" in content
