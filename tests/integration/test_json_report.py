import json
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


@pytest.mark.parametrize("tag", ["@FC-010"])
def test_output_json_conforms_to_schema(tag, tmp_path):
    output = tmp_path / "report.html"
    output_json = tmp_path / "report.json"

    result = run_tool(
        FC002_FEATURES,
        output,
        unit=FC002_UNIT,
        e2e=FC002_E2E,
        output_json=str(output_json),
    )

    assert result.returncode == 0, result.stderr
    assert output_json.exists()

    report = json.loads(output_json.read_text(encoding="utf-8"))
    Draft7Validator(SCHEMA).validate(report)

    assert report["summary"]["completion"]["total"] == 1
    feature = report["features"][0]
    assert feature["name"] == "User Login"
    scenario = feature["scenarios"][0]
    statuses = {r["status"] for r in scenario["results"]}
    assert statuses == {"passed", "failed", "skipped"}

    failed_result = next(r for r in scenario["results"] if r["status"] == "failed" and r["layer"] == "unit")
    assert failed_result["failureMessage"]

    passed_result = next(r for r in scenario["results"] if r["status"] == "passed")
    assert "failureMessage" not in passed_result


@pytest.mark.parametrize("tag", ["@FC-010"])
def test_output_json_omitted_when_not_configured(tag, tmp_path):
    output = tmp_path / "report.html"

    result = run_tool(FC001_FEATURES, output, unit=FC001_UNIT, e2e=FC001_E2E)

    assert result.returncode == 0, result.stderr
    assert output.exists()
    assert not (tmp_path / "report.json").exists()
    assert list(tmp_path.glob("*.json")) == []
