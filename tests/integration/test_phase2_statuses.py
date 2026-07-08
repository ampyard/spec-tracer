from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "phase2_statuses"
FEATURES = FIXTURES / "features"
UNIT = FIXTURES / "unit.xml"
E2E = FIXTURES / "e2e.json"
OUTPUT = FIXTURES / "report.html"


def test_passed_failed_skipped_displayed_in_report():
    result = subprocess.run(
        [
            sys.executable,
            "build_pyramid.py",
            "--features",
            str(FEATURES),
            "--unit",
            str(UNIT),
            "--e2e",
            str(E2E),
            "--output",
            str(OUTPUT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    content = OUTPUT.read_text(encoding="utf-8")

    assert "1/1 scenarios tested" in content
    assert "<strong>unit</strong>" in content
    assert "<strong>e2e</strong>" in content

    assert "(passed)" in content
    assert "(failed)" in content
    assert "(skipped)" in content
