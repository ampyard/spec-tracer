import pytest

from spec_tracer.models import RequiredLayer, Scenario, ScenarioView, TestResult
from spec_tracer.renderers import (
    HtmlRenderer,
    _completion,
    _completion_bar,
    _feature_completion,
    _feature_outcome,
    _format_duration,
    _outcome,
    _status_class,
    _status_label,
)


def _build_views():
    scenario_a = Scenario(feature="Alpha Feature", name="Scenario A", tags=["@FC-100"])
    scenario_b = Scenario(feature="Zebra Feature", name="Scenario B", tags=["@FC-200"])
    result_a = TestResult(layer="unit", name="test_a", tags=["@FC-100"], status="passed")
    view_a = ScenarioView(scenario=scenario_a, linked_results=[result_a], layers=[[result_a]])
    view_b = ScenarioView(scenario=scenario_b, linked_results=[], layers=[])
    return [view_a, view_b]


def _render(**overrides):
    views = overrides.pop("views", _build_views())
    stats = overrides.pop("stats", {
        "complete": 1, "total": 2, "percentage": 50,
        "pct": 50, "satisfied": 1, "required": 2,
    })
    feature_breakdown = overrides.pop("feature_breakdown", [
        {"name": "Alpha Feature", "complete": 1, "total": 1, "percentage": 100, "satisfied": 1, "required": 1, "completion_pct": 100},
        {"name": "Zebra Feature", "complete": 0, "total": 1, "percentage": 0, "satisfied": 0, "required": 1, "completion_pct": 0},
    ])
    layer_stats = overrides.pop("layer_stats", [
        {
            "name": "unit", "label": "UNIT", "count": 1, "passed": 1, "failed": 0, "skipped": 0,
            "duration": 0.5, "pass_pct": 100, "fail_pct": 0, "skip_pct": 0, "width_pct": 100.0,
        }
    ])
    health_checks = overrides.pop("health_checks", {
        "progress": {"status": "warn", "message": "msg", "value": "1/2"},
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
def test_render_includes_theme_switcher(tag):
    html = _render()
    assert 'class="theme-toggle"' in html
    assert "localStorage.getItem('st-theme')" in html
    assert 'data-theme' in html
    assert ':root[data-theme="dark"]' in html
    assert ':root:not([data-theme="light"])' in html


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
def test_render_feature_and_scenario_rows_have_type_pills(tag):
    html = _render()
    # Feature rows are identified with a pill (like test layers)
    assert '<span class="pill"><strong>Feature</strong></span>' in html
    # Scenario rows are identified with a pill
    assert '<span class="pill"><strong>Scenario</strong></span>' in html
    # Ensure the pills appear near their names (basic presence check)
    assert 'Feature</strong></span><span class="name-text"><strong>Alpha Feature' in html
    assert 'Scenario</strong></span><span class="name-text">Scenario A' in html


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
    assert 'data-sort-key="completion"' in html
    assert 'data-sort-key="result"' in html
    assert 'data-sort-key="duration"' in html
    assert 'data-sort-key="status"' not in html
    # The feature/scenario tree header no longer uses the single status column.
    assert 'class="sort-btn col-status"' not in html
    assert "col-coverage" not in html
    assert "Coverage %" not in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_completion_bar_and_result_pill_present(tag):
    html = _render()
    assert "completion-bar" in html
    assert "completion-count" in html
    assert 'class="badge passed">' in html or 'class="badge failed">' in html or 'class="badge skipped">' in html


@pytest.mark.parametrize("tag", ["@FC-009"])
def test_render_includes_scenario_status_badges(tag):
    # Status badges still appear in the Failure Breakdown tree (and the
    # summary helpers are intact), so assert on the failure-breakdown path.
    scenario = Scenario(feature="Alpha Feature", name="Scenario A", tags=["@FC-100"])
    failed_result = TestResult(layer="unit", name="test_a", tags=["@FC-100"], status="failed", failure_message="boom")
    view = ScenarioView(scenario=scenario, linked_results=[failed_result], layers=[[failed_result]])
    failure_breakdown = [
        {
            "name": "Alpha Feature",
            "scenarios": [{"view": view, "failed_results": [failed_result]}],
            "failed_count": 1,
        }
    ]
    html = _render(views=[view], failure_breakdown=failure_breakdown)
    assert 'class="badge failed">' in html


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


def _view_with(required_layers, results):
    scenario = Scenario(feature="F", name="S", tags=["@FC"], required_layers=required_layers)
    return ScenarioView(scenario=scenario, linked_results=results)


@pytest.mark.parametrize("tag", ["@FC-014"])
def test_completion_empty_when_no_results(tag):
    view = _view_with([RequiredLayer("e2e")], [])
    c = _completion(view)
    assert c["satisfied"] == 0
    assert c["total"] == 1
    assert c["count"] == "0/1"
    assert c["cls"] == "empty"
    assert c["pct"] == 0


@pytest.mark.parametrize("tag", ["@FC-014"])
def test_completion_full_counts_presence_not_pass(tag):
    # A present-but-FAILED result still fills the requirement (presence-based).
    view = _view_with(
        [RequiredLayer("unit"), RequiredLayer("e2e")],
        [
            TestResult(layer="unit", name="t", status="failed"),
            TestResult(layer="e2e", name="e", status="passed"),
        ],
    )
    c = _completion(view)
    assert c["count"] == "2/2"
    assert c["cls"] == "full"
    assert c["pct"] == 100


@pytest.mark.parametrize("tag", ["@FC-014"])
def test_completion_empty_when_result_on_wrong_layer(tag):
    view = _view_with([RequiredLayer("e2e")], [TestResult(layer="unit", name="t", status="passed")])
    c = _completion(view)
    assert c["count"] == "0/1"
    assert c["cls"] == "empty"


@pytest.mark.parametrize("tag", ["@FC-014"])
def test_outcome_worst_case_across_results(tag):
    view = _view_with(
        [RequiredLayer("unit")],
        [
            TestResult(layer="unit", name="p", status="passed"),
            TestResult(layer="unit", name="f", status="failed"),
        ],
    )
    assert _outcome(view)["cls"] == "failed"

    view_skipped = _view_with(
        [RequiredLayer("unit")],
        [TestResult(layer="unit", name="s", status="skipped"), TestResult(layer="unit", name="p", status="passed")],
    )
    assert _outcome(view_skipped)["cls"] == "skipped"


@pytest.mark.parametrize("tag", ["@FC-014"])
def test_outcome_skipped_when_no_results(tag):
    view = _view_with([RequiredLayer("e2e")], [])
    assert _outcome(view)["cls"] == "skipped"


@pytest.mark.parametrize("tag", ["@FC-014"])
def test_completion_bar_renders_count_and_color_class(tag):
    view = _view_with([RequiredLayer("unit")], [TestResult(layer="unit", name="t", status="passed")])
    bar = _completion_bar(_completion(view))
    assert 'class="completion-bar completion-full"' in bar
    assert "completion-count" in bar
    assert "1/1" in bar


@pytest.mark.parametrize("tag", ["@FC-014"])
def test_feature_completion_is_average_child_completion(tag):
    a = _view_with([RequiredLayer("e2e")], [TestResult(layer="e2e", name="e", status="passed")])
    b = _view_with([RequiredLayer("e2e")], [])
    fc = _feature_completion([a, b])
    # One scenario 100%, one 0% -> average 50%.
    assert fc["pct"] == 50
    assert fc["satisfied"] == 1
    assert fc["required"] == 2
    assert fc["cls"] == "partial"


@pytest.mark.parametrize("tag", ["@FC-014"])
def test_feature_outcome_worst_across_feature_results(tag):
    a = _view_with([RequiredLayer("unit")], [TestResult(layer="unit", name="p", status="passed")])
    b = _view_with([RequiredLayer("unit")], [TestResult(layer="unit", name="f", status="failed")])
    assert _feature_outcome([a, b])["cls"] == "failed"
