import json
import subprocess
import sys
import uuid
from pathlib import Path

from behave import given, when, then
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
SCHEMA = json.loads((ROOT / "spectracer-report.schema.json").read_text(encoding="utf-8"))

TAG_FIXTURES = {
    "@FC-001": "fc001",
    "@FC-002": "fc002",
    "@FC-003": "integration_linking",
    "@FC-004": "repeatable",
    "@FC-005": "missing_required_layer",
    "@FC-006": "fc002",
    "@FC-007": "module_scope",
    "@FC-EDGE-001": "edge_cases/collision_across",
    "@FC-EDGE-002": "edge_cases/collision_within",
    "@FC-EDGE-003": "edge_cases/feature_tags_not_inherited",
    "@FC-EDGE-004": "edge_cases/no_match",
    "@FC-EDGE-005": "edge_cases/empty_result",
    "@FC-EDGE-006": "edge_cases/malformed_xml",
}


@given('a feature file with scenario tagged "{tag}"')
def step_feature_with_tag(context, tag):
    dir_name = TAG_FIXTURES.get(tag, "e2e_coverage")
    context.features = str(FIXTURES / dir_name / "features")


@given('a unit JUnit XML result tagged "{tag}"')
def step_unit_with_tag(context, tag):
    dir_name = TAG_FIXTURES.get(tag, "unit_linking")
    context.unit = str(FIXTURES / dir_name / "unit.xml")


@given('a module-scoped unit JUnit XML result tagged "{tag}" for module "{module}"')
def step_unit_with_tag_and_module(context, tag, module):
    dir_name = TAG_FIXTURES.get(tag, "unit_linking")
    context.unit = str(FIXTURES / dir_name / (module + "_unit.xml"))
    context.unit_module = module


@given('the unit result is scoped to module "{module}"')
def step_unit_scoped_to_module(context, module):
    context.unit_module = module


@given('an E2E Cucumber JSON result tagged "{tag}"')
def step_e2e_with_tag(context, tag):
    dir_name = TAG_FIXTURES.get(tag, "e2e_coverage")
    context.e2e = str(FIXTURES / dir_name / "e2e.json")


@given('a module-scoped E2E Cucumber JSON result tagged "{tag}" for module "{module}"')
def step_e2e_with_tag_and_module(context, tag, module):
    dir_name = TAG_FIXTURES.get(tag, "module_scope")
    context.e2e = str(FIXTURES / dir_name / (module + "_e2e.json"))
    context.e2e_module = module


@given('the E2E result is scoped to module "{module}"')
def step_e2e_scoped_to_module(context, module):
    context.e2e_module = module


@given('an integration JUnit XML result tagged "{tag}"')
def step_integration_with_tag(context, tag):
    dir_name = TAG_FIXTURES.get(tag, "integration_linking")
    context.integration = str(FIXTURES / dir_name / "integration.xml")


@given('the integration result is scoped to module "{module}"')
def step_integration_scoped_to_module(context, module):
    context.integration_module = module


@given("the config requests a JSON report")
def step_request_json_report(context):
    context.output_json = str(ROOT / "reports" / f"e2e-report-{uuid.uuid4().hex}.json")


def _build_config(context) -> dict:
    config = {
        "features": [context.features],
        "output": str(ROOT / "reports" / "e2e-report.html"),
    }
    if hasattr(context, "unit"):
        module = getattr(context, "unit_module", "")
        config["unit"] = {module: [context.unit]}
    if hasattr(context, "integration"):
        module = getattr(context, "integration_module", "")
        config["integration"] = {module: [context.integration]}
    if hasattr(context, "e2e"):
        module = getattr(context, "e2e_module", "")
        config["e2e"] = {module: [context.e2e]}
    if hasattr(context, "output_json"):
        config["output_json"] = context.output_json
    return config


def _run_tool(context):
    config = _build_config(context)
    output_path = Path(config["output"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    context.output_path = output_path

    config_path = ROOT / "reports" / f"config-{uuid.uuid4().hex}.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, "build_pyramid.py", str(config_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        config_path.unlink(missing_ok=True)
    context.returncode = result.returncode


@when("I run the tool with --features, --unit, --e2e, and --output")
def step_run_tool(context):
    _run_tool(context)


@when("I run the tool with --features, --integration, and --output")
def step_run_tool_with_integration(context):
    _run_tool(context)


@when("I run the tool with --features, --unit, and --output")
def step_run_tool_with_unit(context):
    _run_tool(context)


@when("I run the tool with --features, --e2e, and --output")
def step_run_tool_with_e2e(context):
    _run_tool(context)


@when("I run the tool with --features, --unit, --integration, and --output")
def step_run_tool_with_unit_and_integration(context):
    _run_tool(context)


@then("the exit code should be {code}")
def step_exit_code(context, code):
    assert context.returncode == int(code), f"Expected {code}, got {context.returncode}"


@then('the report should contain "{text}"')
def step_report_contains(context, text):
    content = context.output_path.read_text(encoding="utf-8")
    assert text in content, f"Expected {text!r} in report"


@then('the report should list the unlinked test "{name}"')
def step_report_lists_unlinked_test(context, name):
    """The named unlinked test appears in the Unlinked Tests section."""
    content = context.output_path.read_text(encoding="utf-8")
    assert "Unlinked Tests" in content, "Report is missing the Unlinked Tests section"
    assert name in content, f"Expected unlinked test {name!r} to be listed"


@then("the JSON report file should exist")
def step_json_report_exists(context):
    assert Path(context.output_json).exists()


@then("the JSON report file should not exist")
def step_json_report_not_exists(context):
    assert not hasattr(context, "output_json")


@then("the JSON report should conform to the SpecTracer report schema")
def step_json_report_conforms(context):
    report = json.loads(Path(context.output_json).read_text(encoding="utf-8"))
    Draft7Validator(SCHEMA).validate(report)
