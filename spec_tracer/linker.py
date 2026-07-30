from typing import Dict, List

from spec_tracer.models import Scenario, TestResult


def _scenario_ids(scenario: Scenario) -> set:
    return {tag[4:] for tag in scenario.tags if tag.startswith("@id:")}


def _result_scenario_tags(result: TestResult) -> list:
    return [tag[10:] for tag in result.tags if tag.startswith("@scenario:")]


class ResultLinker:

    @staticmethod
    def link(scenarios: List[Scenario], results: List[TestResult]) -> Dict[int, List[TestResult]]:
        links: Dict[int, List[TestResult]] = {}
        for scenario in scenarios:
            ids = _scenario_ids(scenario)
            links[id(scenario)] = [
                result
                for result in results
                if any(rsid in ids for rsid in _result_scenario_tags(result))
            ]
        return links
