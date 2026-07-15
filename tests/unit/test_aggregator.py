import pytest

from spec_tracer.aggregator import ReportAggregator
from spec_tracer.models import Scenario, ScenarioView, TestResult


def _view(feature, name, results=None):
    scenario = Scenario(feature=feature, name=name, tags=[f"@{name}"])
    results = results or []
    return ScenarioView(scenario=scenario, linked_results=results)


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_layer_order_is_unit_integration_e2e(tag):
    assert ReportAggregator.LAYER_ORDER == ["e2e", "integration", "unit"]


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_build_views_orders_layers_by_layer_order(tag):
    scenario = Scenario(feature="F", name="S", tags=["@S"])
    e2e_result = TestResult(layer="e2e", name="e2e test", tags=["@S"])
    unit_result = TestResult(layer="unit", name="unit test", tags=["@S"])
    integration_result = TestResult(layer="integration", name="integration test", tags=["@S"])
    links = {id(scenario): [e2e_result, unit_result, integration_result]}

    views = ReportAggregator.build_views([scenario], links)

    assert len(views) == 1
    layer_names = [group[0].layer for group in views[0].layers]
    assert layer_names == ["e2e", "integration", "unit"]


@pytest.mark.parametrize("tag", ["@FC-008"])
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


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_layer_stats_width_pct_has_minimum_floor_for_nonzero_layers(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name=f"u{i}") for i in range(20)]),
        _view("F", "S2", [TestResult(layer="e2e", name="e1")]),
    ]

    metrics = ReportAggregator.layer_stats(views)
    by_name = {m["name"]: m for m in metrics}

    assert by_name["unit"]["width_pct"] == 100.0
    assert by_name["e2e"]["width_pct"] == ReportAggregator.MIN_TIER_WIDTH_PCT


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_layer_stats_omits_layers_with_no_results(tag):
    views = [_view("F", "S1", [TestResult(layer="unit", name="u1")])]

    metrics = ReportAggregator.layer_stats(views)

    assert {m["name"] for m in metrics} == {"unit"}


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_layer_stats_empty_views_returns_empty_list(tag):
    assert ReportAggregator.layer_stats([]) == []


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_feature_breakdown_sorted_by_feature_name(tag):
    views = [_view("Zebra", "S1"), _view("Alpha", "S2")]

    breakdown = ReportAggregator.feature_breakdown(views)

    assert [b["name"] for b in breakdown] == ["Alpha", "Zebra"]


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_health_checks_flags_inverted_pyramid(tag):
    views = [
        _view("F", "S1", [TestResult(layer="e2e", name="e1")]),
        _view("F", "S2", [TestResult(layer="e2e", name="e2")]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    coverage_stats = ReportAggregator.coverage_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, coverage_stats)

    assert health["pyramid"]["status"] == "fail"


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_health_checks_passes_when_unit_dominates(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name="u1")]),
        _view("F", "S2", [TestResult(layer="unit", name="u2")]),
        _view("F", "S3", [TestResult(layer="e2e", name="e1")]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    coverage_stats = ReportAggregator.coverage_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, coverage_stats)

    assert health["pyramid"]["status"] == "pass"


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_health_checks_pyramid_warns_when_at_parity(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name="u1")]),
        _view("F", "S2", [TestResult(layer="unit", name="u2")]),
        _view("F", "S3", [TestResult(layer="integration", name="i1")]),
        _view("F", "S4", [TestResult(layer="e2e", name="e1")]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    progress_stats = ReportAggregator.coverage_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, progress_stats)

    assert health["pyramid"]["status"] == "warn"


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_health_checks_end_to_end_runtime_passes_when_below_amber(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name="u1", duration=0.5)]),
        _view("F", "S2", [TestResult(layer="e2e", name="e1", duration=300)]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    progress_stats = ReportAggregator.coverage_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, progress_stats)

    assert health["end_to_end_runtime"]["status"] == "pass"


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_health_checks_end_to_end_runtime_warns_when_between_amber_and_red(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name="u1", duration=0.5)]),
        _view("F", "S2", [TestResult(layer="e2e", name="e1", duration=900)]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    progress_stats = ReportAggregator.coverage_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, progress_stats)

    assert health["end_to_end_runtime"]["status"] == "warn"


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_health_checks_end_to_end_runtime_fails_when_exceeds_red(tag):
    views = [
        _view("F", "S1", [TestResult(layer="unit", name="u1", duration=0.5)]),
        _view("F", "S2", [TestResult(layer="e2e", name="e1", duration=2000)]),
    ]
    layer_stats = ReportAggregator.layer_stats(views)
    progress_stats = ReportAggregator.coverage_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, progress_stats)

    assert health["end_to_end_runtime"]["status"] == "fail"


@pytest.mark.parametrize("tag", ["@FC-008"])
def test_unlinked_results_excludes_tags_matching_scenarios(tag):
    scenarios = [Scenario(feature="F", name="S1", tags=["@FC-001"])]
    linked = TestResult(layer="unit", name="t1", tags=["@FC-001"])
    unlinked = TestResult(layer="unit", name="t2", tags=["@FC-999"])

    result = ReportAggregator.unlinked_results(scenarios, [linked, unlinked])

    assert result == [unlinked]


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_health_checks_unlinked_entry_passes_when_zero(tag):
    views = [_view("F", "S1", [TestResult(layer="unit", name="u1")])]
    layer_stats = ReportAggregator.layer_stats(views)
    coverage_stats = ReportAggregator.coverage_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, coverage_stats, unlinked_count=0)

    assert health["unlinked"]["status"] == "pass"
    assert health["unlinked"]["value"] == "0"


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_health_checks_unlinked_entry_fails_when_many(tag):
    views = [_view("F", "S1", [TestResult(layer="unit", name="u1")])]
    layer_stats = ReportAggregator.layer_stats(views)
    coverage_stats = ReportAggregator.coverage_stats(views)

    health = ReportAggregator.health_checks(views, layer_stats, coverage_stats, unlinked_count=5)

    assert health["unlinked"]["status"] == "fail"
    assert health["unlinked"]["value"] == "5"


@pytest.mark.parametrize("tag", ["@FC-009"])
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


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_failure_breakdown_empty_when_no_failures(tag):
    views = [_view("F", "S1", [TestResult(layer="unit", name="p1", status="passed")])]

    assert ReportAggregator.failure_breakdown(views) == []
