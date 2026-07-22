from pathlib import Path
import subprocess
import sys

import pytest

from conftest import run_tool


ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "tests" / "fixtures" / "integration_linking" / "features"
INTEGRATION = ROOT / "tests" / "fixtures" / "integration_linking" / "integration.xml"
OUTPUT = ROOT / "tests" / "fixtures" / "integration_linking" / "report.html"


@pytest.mark.parametrize("tag", ["@FC-003"])
def test_cli_links_integration_results(tag):
    result = run_tool(FEATURES, OUTPUT, integration=INTEGRATION)

    assert result.returncode == 0, result.stderr
    assert OUTPUT.exists()

    content = OUTPUT.read_text(encoding="utf-8")
    assert "Testing Progress" in content
    assert "Report shows integration coverage" in content
    assert "0/1 scenarios complete" in content
    assert "<strong>integration</strong>" in content
    assert "@FC-003" in content


@pytest.mark.parametrize("tag", ["@FC-003"])
def test_report_includes_integration_layer_from_pytest_junit(tag, tmp_path):
    xml_path = tmp_path / "int.xml"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration/test_integration_linking.py",
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
    report_result = run_tool(FEATURES, report_path, integration=xml_path)

    assert report_result.returncode == 0, report_result.stderr
    content = report_path.read_text(encoding="utf-8")
    assert "<strong>integration</strong>" in content
