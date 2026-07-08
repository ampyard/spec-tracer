from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "tests" / "fixtures" / "phase2" / "features"
UNIT = ROOT / "tests" / "fixtures" / "phase2" / "unit.xml"
OUTPUT = ROOT / "tests" / "fixtures" / "phase2" / "report.html"


@pytest.mark.parametrize("tag", ["@FC-001"])
def test_phase2_cli_links_unit_results(tag):
    result = subprocess.run(
        [
            sys.executable,
            "build_pyramid.py",
            "--features",
            str(FEATURES),
            "--unit",
            str(UNIT),
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
    assert "<strong>unit</strong>" in content
    assert "@FC-001" in content
