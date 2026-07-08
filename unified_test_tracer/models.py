from dataclasses import dataclass, field
from typing import List


@dataclass
class Scenario:
    feature: str
    name: str
    tags: List[str] = field(default_factory=list)
    required_layers: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)


@dataclass
class TestResult:
    __test__ = False
    layer: str
    name: str
    tags: List[str] = field(default_factory=list)
    status: str = "passed"
    duration: float = 0.0
    failure_message: str = ""


@dataclass
class ScenarioView:
    scenario: Scenario
    linked_results: List[TestResult] = field(default_factory=list)
    layers: List[List[TestResult]] = field(default_factory=list)

    @property
    def is_tested(self) -> bool:
        return bool(self.linked_results)
