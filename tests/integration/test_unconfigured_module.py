from pathlib import Path

import pytest

from conftest import run_tool


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "unconfigured_module"
FEATURES = FIXTURES / "features"
UNIT = FIXTURES / "unit.xml"
OUTPUT = FIXTURES / "report.html"


@pytest.mark.parametrize("tag", ["@scenario:FC-012"])
def test_cli_flags_unconfigured_module_distinctly_from_missing(tag):
    """A required module absent from config is flagged distinctly from a merely-empty one (#8)."""
    result = run_tool(FEATURES, OUTPUT, unit=UNIT)

    assert result.returncode == 0, result.stderr
    assert OUTPUT.exists()

    content = OUTPUT.read_text(encoding="utf-8")
    assert "required-chip ok" in content
    assert "required-chip unconfigured" in content
    assert "required-chip missing" not in content


@pytest.mark.parametrize("tag", ["@scenario:FC-012"])
def test_cli_prints_startup_diagnostic_for_unconfigured_module(tag):
    """The distinct diagnostic required by #8 is surfaced on stderr at run time."""
    result = run_tool(FEATURES, OUTPUT, unit=UNIT)

    assert result.returncode == 0
    assert "shipping" in result.stderr
    assert "no such module is configured" in result.stderr
