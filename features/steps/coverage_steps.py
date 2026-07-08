import subprocess
import sys
from pathlib import Path

from behave import given, when, then


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"

TAG_FIXTURES = {
    "@FC-001": "fc001",
    "@FC-002": "fc002",
}


@given('a feature file with scenario tagged "{tag}"')
def step_feature_with_tag(context, tag):
    dir_name = TAG_FIXTURES.get(tag, "phase1")
    context.features = str(FIXTURES / dir_name / "features")


@given('a unit JUnit XML result tagged "{tag}"')
def step_unit_with_tag(context, tag):
    dir_name = TAG_FIXTURES.get(tag, "phase2")
    context.unit = str(FIXTURES / dir_name / "unit.xml")


@given('an E2E Cucumber JSON result tagged "{tag}"')
def step_e2e_with_tag(context, tag):
    dir_name = TAG_FIXTURES.get(tag, "phase1")
    context.e2e = str(FIXTURES / dir_name / "e2e.json")


@when("I run the tool with --features, --unit, --e2e, and --output")
def step_run_tool(context):
    output = ROOT / "reports" / "e2e-report.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    context.output_path = output
    result = subprocess.run(
        [
            sys.executable,
            "build_pyramid.py",
            "--features",
            context.features,
            "--unit",
            context.unit,
            "--e2e",
            context.e2e,
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    context.returncode = result.returncode


@then("the exit code should be {code}")
def step_exit_code(context, code):
    assert context.returncode == int(code), f"Expected {code}, got {context.returncode}"


@then('the report should contain "{text}"')
def step_report_contains(context, text):
    content = context.output_path.read_text(encoding="utf-8")
    assert text in content, f"Expected {text!r} in report"
