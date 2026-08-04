import pytest

from spec_tracer.aggregator import ReportAggregator
from spec_tracer.models import RequiredLayer, Scenario, ScenarioView, TestResult


def _view(feature, name, results=None, required_layers=None):
    scenario = Scenario(
        feature=feature, name=name, tags=[f"@id:{name}"],
        required_layers=required_layers or [],
    )
    return ScenarioView(scenario=scenario, linked_results=results or [])


@pytest.mark.parametrize("tag", ["@scenario:FC-008"])
def test_layer_order_is_unit_integration_e2e(tag):
    assert ReportAggregator.LAYER_ORDER == ["e2e", "integration", "unit"]


def test_build_views_orders_layers_by_layer_order():
    scenario = Scenario(feature="F", name="S", tags=["@id:S"])
    e2e_result = TestResult(layer="e2e", name="e2e test", tags=["@scenario:S"])
    unit_result = TestResult(layer="unit", name="unit test", tags=["@scenario:S"])
    integration_result = TestResult(layer="integration", name="integration test", tags=["@scenario:S"])
    links = {id(scenario): [e2e_result, unit_result, integration_result]}

    views = ReportAggregator.build_views([scenario], links)

    assert len(views) == 1
    layer_names = [group[0].layer for group in views[0].layers]
    assert layer_names == ["e2e", "integration", "unit"]


@pytest.mark.parametrize("tag", ["@scenario:FC-008"])
def test_layer_stats_width_pct_proportional_to_max_count(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name="u1"), TestResult(layer="unit", name="u2")]),
        _view("F", "S2", [TestResult(layer="e2e", name="e1")]),
    ]

    metrics = ReportAggregator.layer_stats(views)
    by_name = {m["name"]: m for m in metrics}

    assert by_name["unit"]["count"] == 2
    assert by_name["e2e"]["count"] == 1
    assert by_name["unit"]["width_pct"] == 100.0
    assert by_name["e2e"]["width_pct"] == 50.0


@pytest.mark.parametrize("tag", ["@scenario:FC-008"])
def test_layer_stats_width_pct_has_minimum_floor_for_nonzero_layers(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name=f"u{i}") for i in range(20)]),
        _view("F", "S2", [TestResult(layer="e2e", name="e1")]),
    ]

    metrics = ReportAggregator.layer_stats(views)
    by_name = {m["name"]: m for m in metrics}

    assert by_name["unit"]["width_pct"] == 100.0
    assert by_name["e2e"]["width_pct"] == ReportAggregator.MIN_TIER_WIDTH_PCT


@pytest.mark.parametrize("tag", ["@scenario:FC-008"])
def test_layer_stats_omits_layers_with_no_results(tag):
    views = [_view("F", "S1", [TestResult(layer="unit", name="u1")])]

    metrics = ReportAggregator.layer_stats(views)

    assert {m["name"] for m in metrics} == {"unit"}


@pytest.mark.parametrize("tag", ["@scenario:FC-008"])
def test_layer_stats_empty_views_returns_empty_list(tag):
    assert ReportAggregator.layer_stats([]) == []


@pytest.mark.parametrize("tag", ["@scenario:FC-008"])
def test_feature_breakdown_sorted_by_feature_name(tag):
    views = [_view("Zebra", "S1"), _view("Alpha", "S2")]

    breakdown = ReportAggregator.feature_breakdown(views)

    assert [b["name"] for b in breakdown] == ["Alpha", "Zebra"]


@pytest.mark.parametrize("tag", ["@scenario:FC-008"])
def test_health_checks_flags_inverted_pyramid(tag):
    views = [
        _view("F", "S1", [TestResult(layer="e2e", name="e1")]),
        _view("F", "S2", [TestResult(layer="e2e", name="e2")]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    completion_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, completion_stats)

    assert health["pyramid"]["status"] == "fail"


@pytest.mark.parametrize("tag", ["@scenario:FC-008"])
def test_health_checks_passes_when_unit_dominates(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name="u1")]),
        _view("F", "S2", [TestResult(layer="unit", name="u2")]),
        _view("F", "S3", [TestResult(layer="e2e", name="e1")]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    completion_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, completion_stats)

    assert health["pyramid"]["status"] == "pass"


@pytest.mark.parametrize("tag", ["@scenario:FC-008"])
def test_health_checks_pyramid_warns_when_at_parity(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name="u1")]),
        _view("F", "S2", [TestResult(layer="unit", name="u2")]),
        _view("F", "S3", [TestResult(layer="integration", name="i1")]),
        _view("F", "S4", [TestResult(layer="e2e", name="e1")]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    progress_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, progress_stats)

    assert health["pyramid"]["status"] == "warn"


@pytest.mark.parametrize("tag", ["@scenario:FC-008"])
def test_health_checks_end_to_end_runtime_passes_when_below_amber(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name="u1", duration=0.5)]),
        _view("F", "S2", [TestResult(layer="e2e", name="e1", duration=300)]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    progress_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, progress_stats)

    assert health["end_to_end_runtime"]["status"] == "pass"


@pytest.mark.parametrize("tag", ["@scenario:FC-008"])
def test_health_checks_end_to_end_runtime_warns_when_between_amber_and_red(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name="u1", duration=0.5)]),
        _view("F", "S2", [TestResult(layer="e2e", name="e1", duration=900)]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    progress_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, progress_stats)

    assert health["end_to_end_runtime"]["status"] == "warn"


@pytest.mark.parametrize("tag", ["@scenario:FC-008"])
def test_health_checks_end_to_end_runtime_fails_when_exceeds_red(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name="u1", duration=0.5)]),
        _view("F", "S2", [TestResult(layer="e2e", name="e1", duration=2000)]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    progress_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, progress_stats)

    assert health["end_to_end_runtime"]["status"] == "fail"


def test_unlinked_results_excludes_tags_matching_scenarios():
    scenarios = [Scenario(feature="F", name="S1", tags=["@id:FC-001"])]
    linked = TestResult(layer="unit", name="t1", tags=["@scenario:FC-001"])
    unlinked = TestResult(layer="unit", name="t2", tags=["@scenario:FC-999"])

    result = ReportAggregator.unlinked_results(scenarios, [linked, unlinked])

    assert result == [unlinked]


def test_unlinked_results_surfaces_non_scenario_tags():
    """A result tagged with a non-@scenario tag that matches no scenario @id is unlinked.

    Category tags like ``@smoke``/``@regression`` that lack the ``@scenario:``
    prefix are correctly surfaced as unlinked since they carry no linking weight.
    """
    scenarios = [Scenario(feature="F", name="S1", tags=["@id:FC-001"])]
    linked = TestResult(layer="unit", name="t1", tags=["@scenario:FC-001"])
    unlinked = TestResult(layer="unit", name="t2", tags=["@regression"])

    result = ReportAggregator.unlinked_results(scenarios, [linked, unlinked])

    assert result == [unlinked]


def test_unlinked_results_excludes_tagless_results():
    """Results carrying no tags are excluded — they can never link to a scenario.

    This keeps untagged test-runner output (e.g. plain pytest) from flooding the
    Unlinked Tests section as false positives.
    """
    scenarios = [Scenario(feature="F", name="S1", tags=["@id:FC-001"])]
    tagless = TestResult(layer="unit", name="t1", tags=[])

    result = ReportAggregator.unlinked_results(scenarios, [tagless])

    assert result == []


@pytest.mark.parametrize("tag", ["@scenario:FC-009"])
def test_health_checks_progress_passes_when_all_declared_tests_matched(tag):
    views = [
        _view("F", "S1", [TestResult(layer="e2e", name="e1")], required_layers=[RequiredLayer(layer="e2e")]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    progress_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, progress_stats)

    assert progress_stats["satisfied"] == progress_stats["required"]
    assert health["Progress"]["status"] == "pass"
    assert health["Progress"]["message"] == "All declared tests are matched."


@pytest.mark.parametrize("tag", ["@scenario:FC-009"])
def test_health_checks_progress_passing_but_incomplete_never_claims_all_matched(tag):
    # 44 of 50 declared requirements matched → 88% clears the green (80%)
    # threshold but must not read "All declared tests are matched." (#28).
    matched = [
        _view("F", f"S{i}", [TestResult(layer="e2e", name="e")], required_layers=[RequiredLayer(layer="e2e")])
        for i in range(44)
    ]
    unmatched = [
        _view("F", f"S{i}", required_layers=[RequiredLayer(layer="e2e")])
        for i in range(44, 50)
    ]
    views = matched + unmatched
    layer_stats = ReportAggregator.layer_stats(views)
    progress_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, progress_stats)

    assert progress_stats["satisfied"] == 44
    assert progress_stats["required"] == 50
    assert health["Progress"]["value"] == "44/50"
    assert health["Progress"]["status"] == "pass"
    assert health["Progress"]["message"] == "Most declared tests are matched."


@pytest.mark.parametrize("tag", ["@scenario:FC-009"])
def test_health_checks_progress_warns_below_green_threshold(tag):
    views = [
        _view("F", f"S{i}", [TestResult(layer="e2e", name="e")], required_layers=[RequiredLayer(layer="e2e")])
        for i in range(6)
    ] + [
        _view("F", f"S{i}", required_layers=[RequiredLayer(layer="e2e")])
        for i in range(6, 10)
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    progress_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, progress_stats)

    assert progress_stats["pct"] == 60
    assert health["Progress"]["status"] == "warn"
    assert health["Progress"]["message"] == "Progress still needs attention."


@pytest.mark.parametrize("tag", ["@scenario:FC-009"])
def test_health_checks_progress_fails_below_amber_threshold(tag):
    views = [
        _view("F", f"S{i}", [TestResult(layer="e2e", name="e")], required_layers=[RequiredLayer(layer="e2e")])
        for i in range(3)
    ] + [
        _view("F", f"S{i}", required_layers=[RequiredLayer(layer="e2e")])
        for i in range(3, 10)
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    progress_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, progress_stats)

    assert progress_stats["pct"] == 30
    assert health["Progress"]["status"] == "fail"
    assert health["Progress"]["message"] == "Progress is below the comfort threshold."


@pytest.mark.parametrize("tag", ["@scenario:FC-009"])
def test_health_checks_unlinked_entry_passes_when_zero(tag):
    views = [_view("F", "S1", [TestResult(layer="unit", name="u1")])]
    layer_stats = ReportAggregator.layer_stats(views)
    completion_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, completion_stats, unlinked_count=0)

    assert health["unlinked"]["status"] == "pass"
    assert health["unlinked"]["value"] == "0"


@pytest.mark.parametrize("tag", ["@scenario:FC-009"])
def test_health_checks_unlinked_entry_fails_when_many(tag):
    views = [_view("F", "S1", [TestResult(layer="unit", name="u1")])]
    layer_stats = ReportAggregator.layer_stats(views)
    completion_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, completion_stats, unlinked_count=5)

    assert health["unlinked"]["status"] == "fail"
    assert health["unlinked"]["value"] == "5"


@pytest.mark.parametrize("tag", ["@scenario:FC-009"])
def test_failure_breakdown_groups_failed_results_by_feature_and_scenario(tag):
    passing = TestResult(layer="unit", name="p1", status="passed")
    failing = TestResult(layer="unit", name="f1", status="failed")
    views = [
        _view("Alpha", "S1", [passing]),
        _view("Alpha", "S2", [failing]),
        _view("Zebra", "S3", [failing]),
    ]

    breakdown = ReportAggregator.failure_breakdown(views)

    assert [b["name"] for b in breakdown] == ["Alpha", "Zebra"]
    alpha = breakdown[0]
    assert alpha["failed_count"] == 1
    assert len(alpha["scenarios"]) == 1
    assert alpha["scenarios"][0]["view"].scenario.name == "S2"
    assert alpha["scenarios"][0]["failed_results"] == [failing]


@pytest.mark.parametrize("tag", ["@scenario:FC-009"])
def test_failure_breakdown_empty_when_no_failures(tag):
    views = [_view("F", "S1", [TestResult(layer="unit", name="p1", status="passed")])]

    assert ReportAggregator.failure_breakdown(views) == []


@pytest.mark.parametrize("tag", ["@scenario:FC-014"])
def test_completion_stats_presence_based_not_link_count(tag):
    # Scenario declares @require-e2e (parser injects it when none declared).
    # A linked UNIT result is present but does NOT satisfy e2e, so the
    # presence-based completion is 0% -> the summary % reflects that.
    views = [_view("F", "S1", [TestResult(layer="unit", name="u1", status="passed")])]
    stats = ReportAggregator.completion_stats(views)
    assert stats["total"] == 1
    # 0 of the 1 requirement (default e2e) is satisfied.
    assert stats["pct"] == 0
    assert stats["satisfied"] == 0
    assert stats["required"] == 1
    # No scenario is fully satisfied -> complete is 0 (not the is_complete count).
    assert stats["complete"] == 0


@pytest.mark.parametrize("tag", ["@scenario:FC-014"])
def test_completion_stats_satisfied_when_requirement_present(tag):
    views = [_view("F", "S1", [TestResult(layer="e2e", name="e1", status="failed")], required_layers=[RequiredLayer("e2e")])]
    stats = ReportAggregator.completion_stats(views)
    # Present-but-failed still fills the requirement: 100% completion.
    assert stats["pct"] == 100
    assert stats["satisfied"] == 1
    assert stats["required"] == 1


@pytest.mark.parametrize("tag", ["@scenario:FC-014"])
def test_completion_stats_average_across_scenarios(tag):
    a = _view("F", "S1", [TestResult(layer="e2e", name="e1", status="passed")], required_layers=[RequiredLayer("e2e")])
    b = _view("F", "S2", [], required_layers=[RequiredLayer("e2e")])
    stats = ReportAggregator.completion_stats([a, b])
    assert stats["pct"] == 50
    assert stats["satisfied"] == 1
    assert stats["required"] == 2


@pytest.mark.parametrize("tag", ["@scenario:FC-012"])
def test_unconfigured_requirements_flags_module_absent_from_config(tag):
    scenario = Scenario(
        feature="F", name="S1", tags=["@id:FC-012"],
        required_layers=[RequiredLayer(layer="e2e", module="shipping")],
    )

    entries = ReportAggregator.unconfigured_requirements(
        [scenario], known_modules={"unit": set(), "integration": set(), "e2e": {"billing"}}
    )

    assert entries == [{"feature": "F", "scenario": "S1", "layer": "e2e", "module": "shipping"}]


@pytest.mark.parametrize("tag", ["@scenario:FC-012"])
def test_unconfigured_requirements_ignores_configured_module(tag):
    scenario = Scenario(
        feature="F", name="S1", tags=["@id:FC-012"],
        required_layers=[RequiredLayer(layer="e2e", module="shipping")],
    )

    entries = ReportAggregator.unconfigured_requirements(
        [scenario], known_modules={"unit": set(), "integration": set(), "e2e": {"shipping"}}
    )

    assert entries == []


@pytest.mark.parametrize("tag", ["@scenario:FC-012"])
def test_unconfigured_requirements_ignores_unscoped_requirements(tag):
    scenario = Scenario(
        feature="F", name="S1", tags=["@id:FC-012"],
        required_layers=[RequiredLayer(layer="e2e")],
    )

    entries = ReportAggregator.unconfigured_requirements(
        [scenario], known_modules={"unit": set(), "integration": set(), "e2e": set()}
    )

    assert entries == []


@pytest.mark.parametrize("tag", ["@scenario:FC-012"])
def test_unconfigured_requirements_case_insensitive(tag):
    scenario = Scenario(
        feature="F", name="S1", tags=["@id:FC-012"],
        required_layers=[RequiredLayer(layer="e2e", module="Shipping")],
    )

    entries = ReportAggregator.unconfigured_requirements(
        [scenario], known_modules={"unit": set(), "integration": set(), "e2e": {"shipping"}}
    )

    assert entries == []


@pytest.mark.parametrize("tag", ["@scenario:FC-012"])
def test_health_checks_unconfigured_modules_entry_passes_when_zero(tag):
    views = [_view("F", "S1", [TestResult(layer="unit", name="u1")])]
    layer_stats = ReportAggregator.layer_stats(views)
    completion_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, completion_stats, unconfigured_count=0)

    assert health["unconfigured_modules"]["status"] == "pass"
    assert health["unconfigured_modules"]["value"] == "0"


@pytest.mark.parametrize("tag", ["@scenario:FC-012"])
def test_health_checks_unconfigured_modules_entry_fails_when_nonzero(tag):
    views = [_view("F", "S1", [TestResult(layer="unit", name="u1")])]
    layer_stats = ReportAggregator.layer_stats(views)
    completion_stats = ReportAggregator.completion_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, completion_stats, unconfigured_count=1)

    assert health["unconfigured_modules"]["status"] == "fail"
    assert health["unconfigured_modules"]["value"] == "1"


@pytest.mark.parametrize("tag", ["@scenario:FC-014"])
def test_feature_breakdown_uses_average_completion(tag):
    a = _view("F", "S1", [TestResult(layer="e2e", name="e1", status="passed")], required_layers=[RequiredLayer("e2e")])
    b = _view("F", "S2", [], required_layers=[RequiredLayer("e2e")])
    breakdown = ReportAggregator.feature_breakdown([a, b])
    assert breakdown[0]["completion_pct"] == 50
    assert breakdown[0]["satisfied"] == 1
    assert breakdown[0]["required"] == 2
