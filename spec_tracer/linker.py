from typing import Dict, List

from spec_tracer.models import Scenario, TestResult


class ResultLinker:

    @staticmethod
    def link(scenarios: List[Scenario], results: List[TestResult]) -> Dict[int, List[TestResult]]:
        links: Dict[int, List[TestResult]] = {}
        for scenario in scenarios:
            links[id(scenario)] = [
                result
                for result in results
                if any(tag in scenario.tags for tag in result.tags)
            ]
        return links
