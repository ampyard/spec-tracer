from collections import defaultdict
from typing import Dict, List

from unified_test_tracer.models import Scenario, ScenarioView, TestResult


class ReportAggregator:

    LAYER_ORDER = ["e2e", "unit", "integration"]

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
