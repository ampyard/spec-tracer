import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from conftest import run_tool


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "spectracer-report.schema.json").read_text(encoding="utf-8"))

FC001_FEATURES = ROOT / "tests" / "fixtures" / "fc001" / "features"
FC001_UNIT = ROOT / "tests" / "fixtures" / "fc001" / "unit.xml"
FC001_E2E = ROOT / "tests" / "fixtures" / "fc001" / "e2e.json"
FC002_FEATURES = ROOT / "tests" / "fixtures" / "fc002" / "features"
FC002_UNIT = ROOT / "tests" / "fixtures" / "fc002" / "unit.xml"
FC002_E2E = ROOT / "tests" / "fixtures" / "fc002" / "e2e.json"


def _extract_report_data(html: str) -> dict:
    match = re.search(
        r'<script type="application/json" id="report-data">(.*?)</script>',
        html, re.S,
    )
    assert match is not None, "no report-data script block found"
    return json.loads(match.group(1))


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_client_render_embeds_valid_report_json(tag, tmp_path):
    output = tmp_path / "report.html"

    result = run_tool(
        FC002_FEATURES,
        output,
        unit=FC002_UNIT,
        e2e=FC002_E2E,
        render_mode="client",
    )

    assert result.returncode == 0, result.stderr
    assert output.exists()

    html = output.read_text(encoding="utf-8")
    report = _extract_report_data(html)
    Draft7Validator(SCHEMA).validate(report)

    assert report["schemaVersion"] == "4"
    assert report["summary"]["completion"]["total"] == 1
    feature = report["features"][0]
    assert feature["name"] == "User Login"
    statuses = {r["status"] for s in feature["scenarios"] for r in s["results"]}
    assert statuses == {"passed", "failed", "skipped"}

    # The static shell the browser renders from the JSON is present too.
    assert "JSON.parse(document.getElementById('report-data').textContent)" in html


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_client_render_escapes_script_closers_in_results(tag, tmp_path):
    output = tmp_path / "report.html"

    result = run_tool(
        FC001_FEATURES,
        output,
        unit=FC001_UNIT,
        render_mode="client",
    )

    assert result.returncode == 0, result.stderr
    html = output.read_text(encoding="utf-8")
    match = re.search(
        r'<script type="application/json" id="report-data">(.*?)</script>',
        html, re.S,
    )
    assert match is not None
    assert "</script>" not in match.group(1)
    report = json.loads(match.group(1))
    assert report["schemaVersion"] == "4"


@pytest.mark.parametrize("tag", ["@scenario:FC-011"])
def test_client_render_requires_no_output_json(tag, tmp_path):
    output = tmp_path / "report.html"

    result = run_tool(
        FC001_FEATURES,
        output,
        unit=FC001_UNIT,
        e2e=FC001_E2E,
        render_mode="client",
    )

    assert result.returncode == 0, result.stderr
    assert output.exists()
    assert list(tmp_path.glob("*.json")) == []


@pytest.mark.parametrize("tag", ["@scenario:FC-011"])
def test_client_render_rejects_unknown_render_mode(tag, tmp_path):
    output = tmp_path / "report.html"

    result = run_tool(
        FC001_FEATURES,
        output,
        unit=FC001_UNIT,
        render_mode="magic",
    )

    assert result.returncode == 1
    assert "render_mode" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("tag", ["@scenario:FC-006"])
def test_client_render_builds_dashboard_sections(tag, tmp_path):
    """Renders the standard dashboard sections in client mode.

    Mirrors tests/unit/test_renderers.py::test_render_dashboard_sections_present
    so the dogfood report can link @require-integration:renderers to FC-006 the
    same way the unit twin covers @require-unit:renderers."""
    output = tmp_path / "report.html"

    result = run_tool(
        FC001_FEATURES,
        output,
        unit=FC001_UNIT,
        e2e=FC001_E2E,
        render_mode="client",
    )

    assert result.returncode == 0, result.stderr
    html = output.read_text(encoding="utf-8")
    assert "Overview" in html
    assert "Test Pyramid" in html
    assert "Health Check" in html
    assert 'placeholder="Search by name"' in html
    assert "Failure Breakdown" in html
    assert "Unlinked Tests" in html
    assert "JSON.parse(document.getElementById('report-data').textContent)" in html


MODULE_SCOPE_FEATURES = ROOT / "tests" / "fixtures" / "module_scope" / "features"
MODULE_SCOPE_UNIT_PARSERS = ROOT / "tests" / "fixtures" / "module_scope" / "parsers_unit.xml"
MODULE_SCOPE_UNIT_OTHER = ROOT / "tests" / "fixtures" / "module_scope" / "other_unit.xml"


@pytest.mark.parametrize("tag", ["@scenario:FC-007"])
def test_client_render_module_pages_embedded_json(tag, tmp_path):
    """Client mode carries per-module cards in the embedded JSON (#36 item 2)."""
    output = tmp_path / "report.html"

    result = run_tool(
        MODULE_SCOPE_FEATURES,
        output,
        unit={"parsers": [MODULE_SCOPE_UNIT_PARSERS], "other": [MODULE_SCOPE_UNIT_OTHER]},
        render_mode="client",
    )

    assert result.returncode == 0, result.stderr
    html = output.read_text(encoding="utf-8")
    report = _extract_report_data(html)
    Draft7Validator(SCHEMA).validate(report)

    keys = [m["key"] for m in report["modules"]]
    assert keys == ["other", "parsers"]
    assert report["modules"][1]["completion"]["total"] >= 1

    # Multi-module config => the Modules tab is active client-side.
    assert "const HAS_MODULES = MODULES.length >= 2;" in html


@pytest.mark.parametrize("tag", ["@scenario:FC-007"])
def test_client_render_single_module_hides_modules_tab(tag, tmp_path):
    """Guardrail: a single-module report must not gain module navigation (#36)."""
    output = tmp_path / "report.html"

    result = run_tool(
        MODULE_SCOPE_FEATURES,
        output,
        unit={"parsers": [MODULE_SCOPE_UNIT_PARSERS]},
        render_mode="client",
    )

    assert result.returncode == 0, result.stderr
    assert output.exists()