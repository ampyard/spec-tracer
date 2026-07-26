from pathlib import Path

import pytest

from conftest import run_tool


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "status_badges"
FEATURES = FIXTURES / "features"
UNIT = FIXTURES / "unit.xml"
E2E = FIXTURES / "e2e.json"
OUTPUT = FIXTURES / "report.html"


@pytest.mark.parametrize("tag", ["@FC-002"])
def test_passed_failed_skipped_displayed_in_report(tag):
    result = run_tool(FEATURES, OUTPUT, unit=UNIT, e2e=E2E)

    assert result.returncode == 0, result.stderr
    content = OUTPUT.read_text(encoding="utf-8")

    assert "<strong>1/1</strong>" in content
    assert "scenarios fully matched" in content
    assert "<strong>unit</strong>" in content
    assert "<strong>e2e</strong>" in content

    assert "badge passed" in content
    assert "badge failed" in content
    assert "badge skipped" in content

    # Hero "tests passed" card (outcome metric, distinct from declared-tests matched)
    assert "tests passed" in content
    assert 'href="#/failures"' in content
    import re
    m = re.search(r"<strong>(\d+)/(\d+)</strong>\s*<span>tests passed", content)
    assert m, "hero tests-passed card missing its N/M count"
    passed, total = int(m.group(1)), int(m.group(2))
    assert total > 0
    failed = int(re.search(r"(\d+) failed", content).group(1))
    assert passed == total - failed, "passed + failed should equal total"
    assert failed > 0, "expected at least one failed test in this fixture"
