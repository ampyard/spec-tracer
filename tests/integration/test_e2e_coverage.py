from pathlib import Path

import pytest

from conftest import run_tool


ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "tests" / "fixtures" / "e2e_coverage" / "features"
E2E = ROOT / "tests" / "fixtures" / "e2e_coverage" / "e2e.json"
OUTPUT = ROOT / "tests" / "fixtures" / "e2e_coverage" / "report.html"


@pytest.mark.parametrize("tag", ["@FC-001"])
def test_cli_generates_coverage_report(tag):
    result = run_tool(FEATURES, OUTPUT, e2e=E2E)

    assert result.returncode == 0, result.stderr
    assert OUTPUT.exists()

    content = OUTPUT.read_text(encoding="utf-8")
    assert "Testing Progress" in content
    assert "Successful login with valid credentials" in content
    assert "1/1 scenarios tested" in content
