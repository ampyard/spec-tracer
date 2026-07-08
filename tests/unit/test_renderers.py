import pytest

from unified_test_tracer.models import Scenario, ScenarioView, TestResult
from unified_test_tracer.renderers import HtmlRenderer, _format_duration, _status_class, _status_label


def _build_views():
    scenario_a = Scenario(feature="Alpha Feature", name="Scenario A", tags=["@FC-100"])
    scenario_b = Scenario(feature="Zebra Feature", name="Scenario B", tags=["@FC-200"])
    result_a = TestResult(layer="unit", name="test_a", tags=["@FC-100"], status="passed")
    view_a = ScenarioView(scenario=scenario_a, linked_results=[result_a], layers=[[result_a]])
    view_b = ScenarioView(scenario=scenario_b, linked_results=[], layers=[])
    return [view_a, view_b]


def _render():
    views = _build_views()
    stats = {"tested": 1, "total": 2, "percentage": 50}
    feature_breakdown = [
        {"name": "Alpha Feature", "tested": 1, "total": 1, "percentage": 100},
        {"name": "Zebra Feature", "tested": 0, "total": 1, "percentage": 0},
    ]
    layer_stats = [
        {
            "name": "unit", "label": "UNIT", "count": 1, "passed": 1, "failed": 0, "skipped": 0,
            "duration": 0.5, "pass_pct": 100, "fail_pct": 0, "skip_pct": 0, "width_pct": 100.0,
        }
    ]
    health_checks = {
        "coverage": {"status": "warn", "message": "msg", "value": "1/2"},
    }
    return HtmlRenderer().render(
        views, stats, feature_breakdown,
        layer_stats=layer_stats, health_checks=health_checks,
        failed_results=[], unlinked_results=[],
    )


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_produces_three_page_containers(tag):
    html = _render()
    assert 'id="page-main"' in html
    assert 'id="page-features"' in html
    assert 'id="page-features" class="page-stack hidden"' in html
    assert 'id="page-feature-detail" class="page-stack hidden"' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_only_main_page_visible_by_default(tag):
    html = _render()
    assert 'id="page-main" class="page-stack">' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_groups_scenarios_by_feature_on_detail_page(tag):
    html = _render()
    assert 'data-feature="Alpha Feature"' in html
    assert 'data-feature="Zebra Feature"' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_feature_links_are_urlencoded(tag):
    scenario = Scenario(feature="Alpha Feature", name="S", tags=["@FC-1"])
    views = [ScenarioView(scenario=scenario, linked_results=[], layers=[])]
    feature_breakdown = [{"name": "Alpha Feature", "tested": 0, "total": 1, "percentage": 0}]
    html = HtmlRenderer().render(views, {"tested": 0, "total": 1, "percentage": 0}, feature_breakdown)
    assert 'href="#/features/Alpha%20Feature"' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_pyramid_tier_uses_layer_specific_class(tag):
    html = _render()
    assert 'class="tier unit"' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_search_placeholder_mentions_tag_example(tag):
    html = _render()
    assert "Search by tag, e.g. FC-001" in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_navigation_click_handler_present(tag):
    html = _render()
    assert "addEventListener('hashchange'" in html
    assert "addEventListener('click'" in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_includes_scenario_status_badges(tag):
    html = _render()
    assert 'class="badge tested"' in html
    assert 'class="badge untested"' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_format_duration_formats_milliseconds_and_seconds(tag):
    assert _format_duration(0) == "0.0s"
    assert _format_duration(0.25) == "250ms"
    assert _format_duration(2.5) == "2.5s"


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_status_class_maps_known_statuses(tag):
    assert _status_class("passed") == "passed"
    assert _status_class("failed") == "failed"
    assert _status_class("skipped") == "skipped"
    assert _status_class("bogus") == "unknown"


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_status_label_titlecases_status(tag):
    assert _status_label("passed") == "Passed"
    assert _status_label("failed") == "Failed"
    assert _status_label("skipped") == "Skipped"
