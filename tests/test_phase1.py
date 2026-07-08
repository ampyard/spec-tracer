from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "tests" / "fixtures" / "phase1" / "features"
E2E = ROOT / "tests" / "fixtures" / "phase1" / "e2e.json"
OUTPUT = ROOT / "tests" / "fixtures" / "phase1" / "report.html"


def test_phase1_cli_generates_coverage_report():
    result = subprocess.run(
        [
            sys.executable,
            "build_pyramid.py",
            "--features",
            str(FEATURES),
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
    assert OUTPUT.exists()

    content = OUTPUT.read_text(encoding="utf-8")
    assert "Scenario Coverage Progress" in content
    assert "Successful login with valid credentials" in content
    assert "1/1 scenarios tested" in content
