from collections import defaultdict
from typing import Dict, List

from spec_tracer.models import Scenario, ScenarioView, TestResult


class ReportAggregator:

    LAYER_ORDER = ["e2e", "integration", "unit"]

    @staticmethod
    def build_views(
        scenarios: List[Scenario],
        links: Dict[int, List[TestResult]],
    ) -> List[ScenarioView]:
        layer_rank = {layer: i for i, layer in enumerate(ReportAggregator.LAYER_ORDER)}
        views: List[ScenarioView] = []
        for scenario in scenarios:
            linked = sorted(links.get(id(scenario), []), key=lambda r: layer_rank.get(r.layer, len(layer_rank)))
            by_layer: Dict[str, List[TestResult]] = {}
            for result in linked:
                by_layer.setdefault(result.layer, []).append(result)
            layers = [by_layer.get(layer, []) for layer in ReportAggregator.LAYER_ORDER if by_layer.get(layer)]
            views.append(ScenarioView(scenario=scenario, linked_results=linked, layers=layers))
        return views

    @staticmethod
    def coverage_stats(views: List[ScenarioView]) -> dict:
        total = len(views)
        tested = sum(1 for v in views if v.is_tested)
        percentage = int(round((tested / total * 100) if total else 0))
        return {"total": total, "tested": tested, "percentage": percentage}

    @staticmethod
    def feature_breakdown(views: List[ScenarioView]) -> List[dict]:
        features: Dict[str, List[ScenarioView]] = defaultdict(list)
        for view in views:
            features[view.scenario.feature].append(view)

        breakdown: List[dict] = []
        for feature_name, feature_views in sorted(features.items()):
            feature_tested = sum(1 for v in feature_views if v.is_tested)
            feature_total = len(feature_views)
            feature_pct = int(round((feature_tested / feature_total * 100) if feature_total else 0))
            breakdown.append({
                "name": feature_name,
                "tested": feature_tested,
                "total": feature_total,
                "percentage": feature_pct,
            })
        return breakdown

    MIN_TIER_WIDTH_PCT = 28

    @staticmethod
    def layer_stats(views: List[ScenarioView]) -> List[dict]:
        linked_results = [result for view in views for result in view.linked_results]
        metrics: List[dict] = []
        for layer in ReportAggregator.LAYER_ORDER:
            layer_results = [result for result in linked_results if result.layer == layer]
            if not layer_results:
                continue
            passed = sum(1 for result in layer_results if result.status == "passed")
            failed = sum(1 for result in layer_results if result.status == "failed")
            skipped = sum(1 for result in layer_results if result.status == "skipped")
            duration = sum(result.duration for result in layer_results)
            total = len(layer_results)
            metrics.append(
                {
                    "name": layer,
                    "label": layer.upper(),
                    "count": total,
                    "passed": passed,
                    "failed": failed,
                    "skipped": skipped,
                    "duration": duration,
                    "pass_pct": int(round((passed / total * 100) if total else 0)),
                    "fail_pct": int(round((failed / total * 100) if total else 0)),
                    "skip_pct": int(round((skipped / total * 100) if total else 0)),
                }
            )
        max_count = max((metric["count"] for metric in metrics), default=0)
        for metric in metrics:
            share = (metric["count"] / max_count * 100) if max_count else 0
            metric["width_pct"] = round(max(share, ReportAggregator.MIN_TIER_WIDTH_PCT if metric["count"] else 0), 1)
        return metrics

    @staticmethod
    def failure_breakdown(views: List[ScenarioView]) -> List[dict]:
        features: Dict[str, List[ScenarioView]] = defaultdict(list)
        for view in views:
            if any(result.status == "failed" for result in view.linked_results):
                features[view.scenario.feature].append(view)

        breakdown: List[dict] = []
        for feature_name, feature_views in sorted(features.items()):
            scenarios = []
            for view in feature_views:
                failed_results = [r for r in view.linked_results if r.status == "failed"]
                scenarios.append({"view": view, "failed_results": failed_results})
            breakdown.append({
                "name": feature_name,
                "scenarios": scenarios,
                "failed_count": sum(len(s["failed_results"]) for s in scenarios),
            })
        return breakdown

    @staticmethod
    def health_checks(
        views: List[ScenarioView],
        layer_stats: List[dict],
        progress_stats: dict,
        unlinked_count: int = 0,
        progress_threshold_green: float = 80,
        progress_threshold_amber: float = 50,
        e2e_duration_amber_seconds: float = 600,
        e2e_duration_red_seconds: float = 1800,
    ) -> dict:
        progress_pct = progress_stats["percentage"]
        if progress_pct >= progress_threshold_green:
            progress_status = "pass"
            progress_message = "Progress is healthy."
        elif progress_pct >= progress_threshold_amber:
            progress_status = "warn"
            progress_message = "Progress still needs attention."
        else:
            progress_status = "fail"
            progress_message = "Progress is below the comfort threshold."

        unit_count = next((metric["count"] for metric in layer_stats if metric["name"] == "unit"), 0)
        integration_count = next((metric["count"] for metric in layer_stats if metric["name"] == "integration"), 0)
        e2e_count = next((metric["count"] for metric in layer_stats if metric["name"] == "e2e"), 0)
        if unit_count > integration_count + e2e_count:
            pyramid_status = "pass"
            pyramid_message = "Unit coverage is strong enough for the pyramid."
        elif unit_count == integration_count + e2e_count:
            pyramid_status = "warn"
            pyramid_message = "Unit coverage is exactly at parity — add more unit tests."
        else:
            pyramid_status = "fail"
            pyramid_message = "The pyramid is inverted and needs more unit coverage."

        e2e_duration = next((metric["duration"] for metric in layer_stats if metric["name"] == "e2e"), 0.0)
        if e2e_duration <= e2e_duration_amber_seconds:
            e2e_status = "pass"
            e2e_message = "End to end Runtime is within the healthy envelope."
        elif e2e_duration <= e2e_duration_red_seconds:
            e2e_status = "warn"
            e2e_message = "End to end Runtime is getting slow."
        else:
            e2e_status = "fail"
            e2e_message = "End to end Runtime exceeds the configured threshold."

        if unlinked_count == 0:
            unlinked_status = "pass"
            unlinked_message = "Every parsed result was linked to a scenario."
        elif unlinked_count <= 3:
            unlinked_status = "warn"
            unlinked_message = "A few results didn't link to any scenario."
        else:
            unlinked_status = "fail"
            unlinked_message = "Several results didn't link to any scenario."

        return {
            "Progress": {"status": progress_status, "message": progress_message, "value": f"{progress_stats['tested']}/{progress_stats['total']}"},
            "pyramid": {
                "status": pyramid_status,
                "message": pyramid_message,
                "value": f"e2e {e2e_count} · integration {integration_count} · unit {unit_count}",
                "layers": [
                    {"name": "e2e", "count": e2e_count},
                    {"name": "integration", "count": integration_count},
                    {"name": "unit", "count": unit_count},
                ],
            },
            "end_to_end_runtime": {"status": e2e_status, "message": e2e_message, "value": f"{e2e_duration:.1f}s"},
            "unlinked": {"status": unlinked_status, "message": unlinked_message, "value": str(unlinked_count)},
        }

    @staticmethod
    def unlinked_results(scenarios: List[Scenario], results: List[TestResult]) -> List[TestResult]:
        """Return results whose tags matched no scenario.

        A result counts as unlinked when it carries at least one tag but none of
        those tags match a scenario's tags. The ``@FC-``-prefix gate was removed:
        tagging a test with e.g. ``@smoke``/``@regression`` and failing to link it
        must surface it as unlinked, exactly as the report's "Unlinked Tests" section
        promises. Results with no tags at all are excluded because, being tag-based,
        they can never link to a scenario and would otherwise flood the section with
        noise from untagged test runners.
        """
        scenario_tags = {tag for scenario in scenarios for tag in scenario.tags}
        return [
            result
            for result in results
            if result.tags
            and not any(tag in scenario_tags for tag in result.tags)
        ]
