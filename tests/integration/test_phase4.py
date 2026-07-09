from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "phase4"
FEATURES = FIXTURES / "features"
UNIT = FIXTURES / "unit.xml"
OUTPUT = FIXTURES / "report.html"


@pytest.mark.parametrize("tag", ["@FC-005"])
def test_phase4_cli_flags_missing_required_layer(tag):
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
    assert "Report flags missing e2e layer" in content
    assert "1/1 scenarios tested" in content
    assert "Required" in content
    assert "unit" in content
    assert "e2e" in content
    assert "required-chip ok" in content
    assert "required-chip missing" in content
