from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "tests" / "fixtures" / "phase3" / "features"
INTEGRATION = ROOT / "tests" / "fixtures" / "phase3" / "integration.xml"
OUTPUT = ROOT / "tests" / "fixtures" / "phase3" / "report.html"


@pytest.mark.parametrize("tag", ["@FC-003"])
def test_phase3_cli_links_integration_results(tag):
    result = subprocess.run(
        [
            sys.executable,
            "build_pyramid.py",
            "--features",
            str(FEATURES),
            "--integration",
            str(INTEGRATION),
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
    assert "Report shows integration coverage" in content
    assert "1/1 scenarios tested" in content
    assert "<strong>integration</strong>" in content
    assert "@FC-003" in content


def test_phase3_report_includes_integration_layer_from_pytest_junit(tmp_path):
    xml_path = tmp_path / "int.xml"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration/test_phase3.py",
            "-k",
            "not report_includes",
            "--junitxml",
            str(xml_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    report_path = tmp_path / "report.html"
    report_result = subprocess.run(
        [
            sys.executable,
            "build_pyramid.py",
            "--features",
            str(FEATURES),
            "--integration",
            str(xml_path),
            "--output",
            str(report_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert report_result.returncode == 0, report_result.stderr
    content = report_path.read_text(encoding="utf-8")
    assert "<strong>integration</strong>" in content
