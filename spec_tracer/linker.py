from typing import Dict, List

from spec_tracer.models import Scenario, TestResult


def _scenario_ids(scenario: Scenario) -> set:
    return {tag[4:] for tag in scenario.tags if tag.startswith("@id:")}


def result_matches_any_id(result: TestResult, scenario_ids: set) -> bool:
    return any(_result_carries_id(result, sid) for sid in scenario_ids)


def _result_carries_id(result: TestResult, scenario_id: str) -> bool:
    """Whether a result carries a ``@scenario:<id>`` (or ``@id:<id>`` for e2e).

    Matching is by containment rather than exact tag equality: a JUnit test
    name/classname can glue extra characters onto the tag with no whitespace
    (e.g. a parametrization suffix), so the id need not appear as its own
    separate word — it only needs to be present.
    """
    needles = [f"@scenario:{scenario_id}"]
    if result.layer == "e2e":
        needles.append(f"@id:{scenario_id}")
    return any(needle in tag for tag in result.tags for needle in needles)


class ResultLinker:

    @staticmethod
    def link(scenarios: List[Scenario], results: List[TestResult]) -> Dict[int, List[TestResult]]:
        links: Dict[int, List[TestResult]] = {}
        for scenario in scenarios:
            ids = _scenario_ids(scenario)
            links[id(scenario)] = [
                result
                for result in results
                if result_matches_any_id(result, ids)
            ]
        return links
