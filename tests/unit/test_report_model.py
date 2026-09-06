import pytest

from spec_tracer.models import RequiredLayer, Scenario, ScenarioView, TestResult
from spec_tracer.report_model import build_report


def _view(feature, name, tags=None, required_layers=None, results=None):
    scenario = Scenario(
        feature=feature,
        name=name,
        tags=tags or [f"@{name}"],
        required_layers=required_layers or [],
    )
    return ScenarioView(scenario=scenario, linked_results=results or [])


def _build(views, stats=None, layer_stats=None, health_checks=None, unlinked_results=None, config=None, feature_files=None, known_modules=None):
    return build_report(
        config or {"features": ["./features"], "output": "./out.html"},
        views,
        stats or {
            "complete": len(views), "total": len(views), "percentage": 100,
            "pct": 100, "satisfied": len(views), "required": len(views),
        },
        layer_stats or [],
        health_checks
        or {"Progress": {"status": "pass", "message": "ok", "value": "1/1"}},
        unlinked_results or [],
        feature_files=feature_files,
        known_modules=known_modules,
    )


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_result_omits_duration_when_zero(tag):
    view = _view("F", "S1", results=[TestResult(layer="unit", name="t1", status="passed", duration=0.0)])

    report = _build([view])

    result = report["features"][0]["scenarios"][0]["results"][0]
    assert "duration" not in result


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_result_converts_duration_seconds_to_milliseconds(tag):
    view = _view("F", "S1", results=[TestResult(layer="unit", name="t1", status="passed", duration=1.5)])

    report = _build([view])

    result = report["features"][0]["scenarios"][0]["results"][0]
    assert result["duration"] == 1500.0


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_result_omits_failure_message_when_passed(tag):
    view = _view(
        "F", "S1",
        results=[TestResult(layer="unit", name="t1", status="passed", failure_message="should not appear")],
    )

    report = _build([view])

    result = report["features"][0]["scenarios"][0]["results"][0]
    assert "failureMessage" not in result


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_result_includes_failure_message_when_failed(tag):
    view = _view(
        "F", "S1",
        results=[TestResult(layer="unit", name="t1", status="failed", failure_message="boom")],
    )

    report = _build([view])

    result = report["features"][0]["scenarios"][0]["results"][0]
    assert result["failureMessage"] == "boom"


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_result_omits_failure_message_when_failed_but_message_empty(tag):
    view = _view(
        "F", "S1",
        results=[TestResult(layer="unit", name="t1", status="failed", failure_message="")],
    )

    report = _build([view])

    result = report["features"][0]["scenarios"][0]["results"][0]
    assert "failureMessage" not in result


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_result_omits_module_when_blank(tag):
    view = _view("F", "S1", results=[TestResult(layer="unit", name="t1", status="passed", module="")])

    report = _build([view])

    result = report["features"][0]["scenarios"][0]["results"][0]
    assert "module" not in result


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_requirement_satisfied_when_module_matches(tag):
    view = _view(
        "F", "S1",
        required_layers=[RequiredLayer(layer="unit", module="billing")],
        results=[TestResult(layer="unit", name="t1", status="passed", module="billing")],
    )

    report = _build([view])

    req = report["features"][0]["scenarios"][0]["requirements"][0]
    assert req == {"layer": "unit", "satisfied": True, "module": "billing"}


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_requirement_satisfied_when_module_matches_case_insensitively(tag):
    view = _view(
        "F", "S1",
        required_layers=[RequiredLayer(layer="unit", module="Billing")],
        results=[TestResult(layer="unit", name="t1", status="passed", module="billing")],
    )

    report = _build([view])

    req = report["features"][0]["scenarios"][0]["requirements"][0]
    assert req == {"layer": "unit", "satisfied": True, "module": "Billing"}


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_requirement_unsatisfied_when_module_does_not_match(tag):
    view = _view(
        "F", "S1",
        required_layers=[RequiredLayer(layer="unit", module="billing")],
        results=[TestResult(layer="unit", name="t1", status="passed", module="other")],
    )

    report = _build([view])

    req = report["features"][0]["scenarios"][0]["requirements"][0]
    assert req["satisfied"] is False


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_requirement_omits_module_key_when_unscoped(tag):
    view = _view(
        "F", "S1",
        required_layers=[RequiredLayer(layer="e2e")],
        results=[TestResult(layer="e2e", name="t1", status="passed")],
    )

    report = _build([view])

    req = report["features"][0]["scenarios"][0]["requirements"][0]
    assert "module" not in req


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_e2e_requirement_satisfied_when_module_matches(tag):
    view = _view(
        "F", "S1",
        required_layers=[RequiredLayer(layer="e2e", module="parsers")],
        results=[TestResult(layer="e2e", name="t1", status="passed", module="parsers")],
    )

    report = _build([view])

    req = report["features"][0]["scenarios"][0]["requirements"][0]
    assert req == {"layer": "e2e", "satisfied": True, "module": "parsers"}


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_e2e_requirement_unsatisfied_when_module_does_not_match(tag):
    view = _view(
        "F", "S1",
        required_layers=[RequiredLayer(layer="e2e", module="parsers")],
        results=[TestResult(layer="e2e", name="t1", status="passed", module="other")],
    )

    report = _build([view])

    req = report["features"][0]["scenarios"][0]["requirements"][0]
    assert req["satisfied"] is False


@pytest.mark.parametrize("tag", ["@scenario:FC-012"])
def test_requirement_flagged_unconfigured_when_module_absent_from_known_modules(tag):
    view = _view(
        "F", "S1",
        required_layers=[RequiredLayer(layer="e2e", module="shipping")],
        results=[],
    )

    report = _build([view], known_modules={"unit": set(), "integration": set(), "e2e": {"billing"}})

    req = report["features"][0]["scenarios"][0]["requirements"][0]
    assert req == {"layer": "e2e", "satisfied": False, "module": "shipping", "unconfigured": True}


@pytest.mark.parametrize("tag", ["@scenario:FC-012"])
def test_requirement_not_flagged_unconfigured_when_module_is_known(tag):
    view = _view(
        "F", "S1",
        required_layers=[RequiredLayer(layer="e2e", module="shipping")],
        results=[],
    )

    report = _build([view], known_modules={"unit": set(), "integration": set(), "e2e": {"shipping"}})

    req = report["features"][0]["scenarios"][0]["requirements"][0]
    assert req == {"layer": "e2e", "satisfied": False, "module": "shipping"}


@pytest.mark.parametrize("tag", ["@scenario:FC-012"])
def test_requirement_omits_unconfigured_key_when_known_modules_not_supplied(tag):
    view = _view(
        "F", "S1",
        required_layers=[RequiredLayer(layer="e2e", module="shipping")],
        results=[],
    )

    report = _build([view])

    req = report["features"][0]["scenarios"][0]["requirements"][0]
    assert req == {"layer": "e2e", "satisfied": False, "module": "shipping"}


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_features_group_scenarios_and_preserve_first_seen_order(tag):
    views = [
        _view("Zebra", "S1"),
        _view("Alpha", "S2"),
        _view("Zebra", "S3"),
    ]

    report = _build(views)

    feature_names = [f["name"] for f in report["features"]]
    assert feature_names == ["Zebra", "Alpha"]
    zebra = next(f for f in report["features"] if f["name"] == "Zebra")
    assert len(zebra["scenarios"]) == 2


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_features_use_provided_feature_file_path(tag):
    view = _view("F", "S1")

    report = _build([view], feature_files={"F": "features/f.feature"})

    assert report["features"][0]["file"] == "features/f.feature"


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_features_default_file_to_empty_string_when_unknown(tag):
    view = _view("F", "S1")

    report = _build([view])

    assert report["features"][0]["file"] == ""


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_health_status_green_when_all_checks_pass(tag):
    report = _build(
        [],
        health_checks={"Progress": {"status": "pass", "message": "ok", "value": "0/0"}},
    )

    assert report["summary"]["health"] == {"status": "green", "reasons": []}


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_health_status_amber_when_worst_check_warns(tag):
    report = _build(
        [],
        health_checks={
            "Progress": {"status": "pass", "message": "ok", "value": "0/0"},
            "pyramid": {"status": "warn", "message": "at parity", "value": "x"},
        },
    )

    assert report["summary"]["health"]["status"] == "amber"
    assert report["summary"]["health"]["reasons"] == ["at parity"]


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_health_status_red_when_any_check_fails(tag):
    report = _build(
        [],
        health_checks={
            "Progress": {"status": "warn", "message": "needs attention", "value": "x"},
            "pyramid": {"status": "fail", "message": "inverted", "value": "y"},
        },
    )

    assert report["summary"]["health"]["status"] == "red"
    assert set(report["summary"]["health"]["reasons"]) == {"needs attention", "inverted"}


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_pyramid_summary_converts_duration_to_milliseconds(tag):
    metric = {
        "name": "unit", "label": "UNIT", "count": 3, "passed": 3, "failed": 0, "skipped": 0,
        "duration": 0.25, "pass_pct": 100, "fail_pct": 0, "skip_pct": 0, "width_pct": 100.0,
    }
    report = _build([], layer_stats=[metric])

    assert report["summary"]["pyramid"]["unit"] == {"testCount": 3, "duration": 250.0, "passRate": 100}


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_unlinked_tests_included_with_tags_and_optional_module(tag):
    unlinked = [
        TestResult(layer="unit", name="orphan", tags=["@scenario:FC-999"], module="billing"),
    ]

    report = _build([], unlinked_results=unlinked)

    assert report["unlinkedTests"] == [
        {"layer": "unit", "testId": "orphan", "name": "orphan", "status": "passed", "tags": ["@scenario:FC-999"], "module": "billing"}
    ]


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_unlinked_tests_include_status_and_duration_ms(tag):
    unlinked = [
        TestResult(layer="e2e", name="orphan", status="failed", duration=2.5, tags=["@scenario:FC-999"]),
    ]

    report = _build([], unlinked_results=unlinked)

    assert report["unlinkedTests"] == [
        {"layer": "e2e", "testId": "orphan", "name": "orphan", "status": "failed", "duration": 2500.0, "tags": ["@scenario:FC-999"]}
    ]


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_unlinked_tests_omit_duration_when_zero(tag):
    unlinked = [
        TestResult(layer="unit", name="orphan", status="skipped", tags=["@scenario:FC-999"]),
    ]

    report = _build([], unlinked_results=unlinked)

    entry = report["unlinkedTests"][0]
    assert entry["status"] == "skipped"
    assert "duration" not in entry


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_config_is_echoed_verbatim(tag):
    config = {"features": ["./features"], "output": "./out.html", "output_json": "./out.json"}

    report = _build([], config=config)

    assert report["config"] == config


@pytest.mark.parametrize("tag", ["@scenario:FC-010"])
def test_schema_version_and_generated_at_present(tag):
    report = _build([])

    assert report["schemaVersion"] == "3"
    assert report["generatedAt"].endswith("Z")


@pytest.mark.parametrize("tag", ["@scenario:FC-018"])
def test_scenario_result_carries_steps_in_order(tag):
    view = _view("F", "S1")
    view.scenario.steps = ["Given a user", "When they log in", "Then they land on home"]

    report = _build([view])

    scenario = report["features"][0]["scenarios"][0]
    assert scenario["steps"] == ["Given a user", "When they log in", "Then they land on home"]


@pytest.mark.parametrize("tag", ["@scenario:FC-018"])
def test_scenario_result_steps_default_to_empty_list(tag):
    report = _build([_view("F", "S1")])

    assert report["features"][0]["scenarios"][0]["steps"] == []


@pytest.mark.parametrize("tag", ["@scenario:FC-018"])
def test_summary_layer_stats_carry_render_detail_in_order(tag):
    layer_stats = [
        {
            "name": "e2e", "label": "E2E", "count": 2, "passed": 1, "failed": 1, "skipped": 0,
            "duration": 10.0, "pass_pct": 50, "fail_pct": 50, "skip_pct": 0, "width_pct": 100.0,
        },
        {
            "name": "integration", "label": "INTEGRATION", "count": 3, "passed": 3, "failed": 0, "skipped": 0,
            "duration": 5.0, "pass_pct": 100, "fail_pct": 0, "skip_pct": 0, "width_pct": 90.0,
        },
    ]

    report = _build([], layer_stats=layer_stats)

    assert report["summary"]["layerStats"] == [
        {
            "name": "e2e", "count": 2, "passed": 1, "failed": 1, "skipped": 0,
            "duration": 10000.0, "passRate": 50, "failRate": 50, "skipRate": 0, "widthPct": 100.0,
        },
        {
            "name": "integration", "count": 3, "passed": 3, "failed": 0, "skipped": 0,
            "duration": 5000.0, "passRate": 100, "failRate": 0, "skipRate": 0, "widthPct": 90.0,
        },
    ]


@pytest.mark.parametrize("tag", ["@scenario:FC-018"])
def test_summary_health_checks_reflect_individual_cards_in_order(tag):
    health_checks = {
        "Progress": {"status": "pass", "message": "All declared tests are matched.", "value": "2/3"},
        "pyramid": {
            "status": "fail",
            "message": "The pyramid is inverted and needs more unit tests.",
            "value": "e2e 2 \u00b7 integration 0 \u00b7 unit 1",
            "layers": [
                {"name": "e2e", "count": 2},
                {"name": "integration", "count": 0},
                {"name": "unit", "count": 1},
            ],
        },
    }

    report = _build([], health_checks=health_checks)

    assert report["summary"]["healthChecks"] == [
        {"key": "Progress", "status": "pass", "message": "All declared tests are matched.", "value": "2/3"},
        {
            "key": "pyramid",
            "status": "fail",
            "message": "The pyramid is inverted and needs more unit tests.",
            "value": "e2e 2 \u00b7 integration 0 \u00b7 unit 1",
            "layers": [
                {"name": "e2e", "count": 2},
                {"name": "integration", "count": 0},
                {"name": "unit", "count": 1},
            ],
        },
    ]


@pytest.mark.parametrize("tag", ["@scenario:FC-018"])
def test_summary_health_checks_omit_layers_for_non_pyramid(tag):
    report = _build(
        [],
        health_checks={"Progress": {"status": "warn", "message": "needs attention", "value": "1/2"}},
    )

    assert report["summary"]["healthChecks"] == [
        {"key": "Progress", "status": "warn", "message": "needs attention", "value": "1/2"}
    ]
