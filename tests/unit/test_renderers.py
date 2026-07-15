import pytest

from spec_tracer.models import Scenario, ScenarioView, TestResult
from spec_tracer.renderers import HtmlRenderer, _format_duration, _status_class, _status_label


def _build_views():
    scenario_a = Scenario(feature="Alpha Feature", name="Scenario A", tags=["@FC-100"])
    scenario_b = Scenario(feature="Zebra Feature", name="Scenario B", tags=["@FC-200"])
    result_a = TestResult(layer="unit", name="test_a", tags=["@FC-100"], status="passed")
    view_a = ScenarioView(scenario=scenario_a, linked_results=[result_a], layers=[[result_a]])
    view_b = ScenarioView(scenario=scenario_b, linked_results=[], layers=[])
    return [view_a, view_b]


def _render(**overrides):
    views = overrides.pop("views", _build_views())
    stats = overrides.pop("stats", {"tested": 1, "total": 2, "percentage": 50})
    feature_breakdown = overrides.pop("feature_breakdown", [
        {"name": "Alpha Feature", "tested": 1, "total": 1, "percentage": 100},
        {"name": "Zebra Feature", "tested": 0, "total": 1, "percentage": 0},
    ])
    layer_stats = overrides.pop("layer_stats", [
        {
            "name": "unit", "label": "UNIT", "count": 1, "passed": 1, "failed": 0, "skipped": 0,
            "duration": 0.5, "pass_pct": 100, "fail_pct": 0, "skip_pct": 0, "width_pct": 100.0,
        }
    ])
    health_checks = overrides.pop("health_checks", {
        "coverage": {"status": "warn", "message": "msg", "value": "1/2"},
        "unlinked": {"status": "pass", "message": "none", "value": "0"},
    })
    failed_results = overrides.pop("failed_results", [])
    unlinked_results = overrides.pop("unlinked_results", [])
    failure_breakdown = overrides.pop("failure_breakdown", [])
    return HtmlRenderer().render(
        views, stats, feature_breakdown,
        layer_stats=layer_stats, health_checks=health_checks,
        failed_results=failed_results, unlinked_results=unlinked_results,
        failure_breakdown=failure_breakdown,
        **overrides,
    )


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_produces_header_with_title_only_once(tag):
    html = _render()
    assert '<span class="app-title">SpecTracer</span>' in html
    assert html.count("SpecTracer") == 2  # <title> + header span


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_produces_five_page_containers(tag):
    html = _render()
    for page_id in ["page-dashboard", "page-pyramid", "page-features", "page-failures", "page-unlinked"]:
        assert f'id="{page_id}"' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_only_dashboard_page_visible_by_default(tag):
    html = _render()
    assert 'id="page-dashboard" class="page-stack">' in html
    assert 'id="page-pyramid" class="page-stack hidden">' in html
    assert 'id="page-features" class="page-stack hidden">' in html
    assert 'id="page-failures" class="page-stack hidden">' in html
    assert 'id="page-unlinked" class="page-stack hidden">' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_top_nav_has_five_links(tag):
    html = _render()
    for route, label in [
        ("/", "Dashboard"),
        ("/pyramid", "Test Pyramid"),
        ("/features", "Feature Breakdown"),
        ("/failures", "Failure Breakdown"),
        ("/unlinked", "Unlinked Tests"),
    ]:
        assert f'data-route="{route}"' in html
        assert label in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_feature_breakdown_tree_groups_scenarios_by_feature(tag):
    html = _render()
    assert 'data-sort-name="Alpha Feature"' in html
    assert 'data-sort-name="Zebra Feature"' in html
    assert 'data-sort-name="Scenario A"' in html
    assert 'data-sort-name="Scenario B"' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_pyramid_tier_uses_layer_specific_class(tag):
    html = _render()
    assert 'class="tier unit"' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_search_placeholder_present(tag):
    html = _render()
    assert 'placeholder="Search by name"' in html
    assert 'class="search-bar"' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_navigation_click_handler_present(tag):
    html = _render()
    assert "addEventListener('hashchange'" in html
    assert "addEventListener('click'" in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_tree_table_sort_buttons_present(tag):
    html = _render()
    assert 'data-sort-key="name"' in html
    assert 'data-sort-key="status"' in html
    assert 'data-sort-key="duration"' in html
    assert 'data-sort-key="coverage"' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_includes_scenario_status_badges(tag):
    html = _render()
    assert 'class="badge tested">Complete' in html
    assert 'class="badge incomplete">Incomplete' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_health_check_unlinked_entry_links_to_unlinked_page(tag):
    html = _render()
    assert 'href="#/unlinked">View unlinked tests' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_failure_breakdown_tree_present_when_failures_exist(tag):
    scenario = Scenario(feature="Alpha Feature", name="Scenario A", tags=["@FC-100"])
    failed_result = TestResult(layer="unit", name="test_a", tags=["@FC-100"], status="failed", failure_message="boom")
    view = ScenarioView(scenario=scenario, linked_results=[failed_result], layers=[[failed_result]])
    failure_breakdown = [{
        "name": "Alpha Feature",
        "scenarios": [{"view": view, "failed_results": [failed_result]}],
        "failed_count": 1,
    }]
    html = _render(views=[view], failure_breakdown=failure_breakdown)
    assert "boom" in html
    assert 'data-sort-name="Alpha Feature"' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_no_logo_by_default(tag):
    html = _render()
    assert '<img class="logo"' not in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_logo_rendered_when_provided(tag):
    html = _render(logo_data_uri="data:image/png;base64,abc")
    assert '<img class="logo" src="data:image/png;base64,abc"' in html


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
