from pathlib import Path

import pytest

from conftest import run_tool


ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "tests" / "fixtures" / "e2e_coverage" / "features"
E2E = ROOT / "tests" / "fixtures" / "e2e_coverage" / "e2e.json"
OUTPUT = ROOT / "tests" / "fixtures" / "e2e_coverage" / "report.html"


@pytest.mark.parametrize("tag", ["@scenario:FC-001"])
def test_cli_generates_coverage_report(tag):
    result = run_tool(FEATURES, OUTPUT, e2e=E2E)

    assert result.returncode == 0, result.stderr
    assert OUTPUT.exists()

    content = OUTPUT.read_text(encoding="utf-8")
    assert "Overview" in content
    assert "Successful login with valid credentials" in content
    assert "<strong>1/1</strong>" in content
    assert "scenarios fully matched" in content
    assert "tests passed" in content
    assert 'href="#/failures"' in content
    import re
    m = re.search(r"<strong>(\d+)/(\d+)</strong>\s*<span>tests passed", content)
    assert m, "hero tests-passed card missing its N/M count"
    passed, total = int(m.group(1)), int(m.group(2))
    assert total > 0
    assert passed == total - int(re.search(r"(\d+) failed", content).group(1))
