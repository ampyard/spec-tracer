from collections import defaultdict
from typing import Dict, List

from unified_test_tracer.models import Scenario, ScenarioView, TestResult


class ReportAggregator:

    LAYER_ORDER = ["e2e", "integration", "unit"]

    @staticmethod
    def build_views(
        scenarios: List[Scenario],
        links: Dict[int, List[TestResult]],
    ) -> List[ScenarioView]:
        views: List[ScenarioView] = []
        for scenario in scenarios:
            linked = links.get(id(scenario), [])
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
        coverage_stats: dict,
        unlinked_count: int = 0,
        coverage_threshold_green: float = 80,
        coverage_threshold_amber: float = 50,
        e2e_speed_threshold_pct: float = 50,
    ) -> dict:
        coverage_pct = coverage_stats["percentage"]
        if coverage_pct >= coverage_threshold_green:
            coverage_status = "pass"
            coverage_message = "Coverage is healthy and trending forward."
        elif coverage_pct >= coverage_threshold_amber:
            coverage_status = "warn"
            coverage_message = "Coverage is improving but still needs attention."
        else:
            coverage_status = "fail"
            coverage_message = "Coverage is below the comfort threshold."

        unit_count = next((metric["count"] for metric in layer_stats if metric["name"] == "unit"), 0)
        integration_count = next((metric["count"] for metric in layer_stats if metric["name"] == "integration"), 0)
        e2e_count = next((metric["count"] for metric in layer_stats if metric["name"] == "e2e"), 0)
        pyramid_ok = unit_count >= integration_count + e2e_count
        pyramid_status = "pass" if pyramid_ok else "fail"
        pyramid_message = "Unit coverage is strong enough for the pyramid." if pyramid_ok else "The pyramid is inverted and needs more unit coverage."

        e2e_duration = next((metric["duration"] for metric in layer_stats if metric["name"] == "e2e"), 0.0)
        total_duration = sum(metric["duration"] for metric in layer_stats)
        e2e_speed_ok = total_duration == 0 or e2e_duration <= total_duration * (e2e_speed_threshold_pct / 100)
        e2e_status = "pass" if e2e_speed_ok else "fail"
        e2e_message = "E2E runtime stays within the healthy envelope." if e2e_speed_ok else "E2E runtime dominates the suite."

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
            "coverage": {"status": coverage_status, "message": coverage_message, "value": f"{coverage_stats['tested']}/{coverage_stats['total']}"},
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
            "e2e_speed": {"status": e2e_status, "message": e2e_message, "value": f"{e2e_duration:.1f}s / {total_duration:.1f}s"},
            "unlinked": {"status": unlinked_status, "message": unlinked_message, "value": str(unlinked_count)},
        }

    @staticmethod
    def unlinked_results(scenarios: List[Scenario], results: List[TestResult]) -> List[TestResult]:
        scenario_tags = {tag for scenario in scenarios for tag in scenario.tags}
        return [
            result
            for result in results
            if not any(tag in scenario_tags for tag in result.tags)
            and any(tag.startswith("@FC-") for tag in result.tags)
        ]
