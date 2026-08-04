from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


def requirement_satisfied(req, linked_results: List["TestResult"]) -> bool:
    """Whether a ``@require-*`` requirement is met by the linked results.

    A requirement is satisfied when at least one linked result matches on
    layer (and module, when the requirement is module-scoped). This is a
    *presence* check only — result pass/fail status does not matter, so a
    failed-but-present result still fills the requirement.
    """
    return any(
        r.layer == req.layer and (req.module == "" or r.module.lower() == req.module.lower())
        for r in linked_results
    )


def requirement_state(req, linked_results: List["TestResult"], known_modules: Optional[Dict[str, Set[str]]] = None) -> str:
    """Three-way state of a ``@require-*`` requirement: ``"ok"``, ``"missing"``, or ``"unconfigured"``.

    ``"unconfigured"`` means the requirement names a module that isn't a
    registered config key for that layer at all — distinct from ``"missing"``,
    where the module is configured but has zero linked results (#8). This
    distinction only applies to module-scoped requirements; when
    ``known_modules`` is not supplied the state degrades to the old two-way
    ``"ok"``/``"missing"`` split.
    """
    if requirement_satisfied(req, linked_results):
        return "ok"
    if req.module and known_modules is not None:
        configured = known_modules.get(req.layer)
        if configured is not None and req.module.lower() not in configured:
            return "unconfigured"
    return "missing"


def completion_fraction(view) -> tuple:
    """Presence-based completion for a scenario, as ``(satisfied, total)``.

    ``total`` is the number of declared ``@require-*`` requirements (always at
    least 1 because ``FeatureParser`` injects a default ``e2e`` requirement when
    none are declared, so there is never a divide-by-zero). A requirement counts
    toward ``satisfied`` when it is met by layer + module match (presence only).
    """
    total = len(view.scenario.required_layers) or 1
    satisfied = sum(
        1 for req in view.scenario.required_layers if requirement_satisfied(req, view.linked_results)
    )
    return satisfied, total


def completion_ratio(view) -> float:
    """Presence-based completion as a 0..1 ratio (avg child completion basis)."""
    satisfied, total = completion_fraction(view)
    return satisfied / total


def worst_outcome(view) -> Optional[str]:
    """Worst result outcome across a scenario's linked results.

    Ranking (worst first): ``failed`` > ``skipped`` > ``passed``. When a
    scenario has no linked results the requirement set is unmet and the honest
    outcome is ``skipped`` (nothing ran). Returns ``None`` only if there are no
    requirements at all (which cannot happen — a default requirement is always
    injected).
    """
    if not view.linked_results:
        return "skipped"
    rank = {"failed": 0, "skipped": 1, "passed": 2}
    return min((r.status for r in view.linked_results), key=lambda s: rank.get(s, 0))


@dataclass
class RequiredLayer:
    layer: str
    module: str = ""


@dataclass
class Scenario:
    feature: str
    name: str
    tags: List[str] = field(default_factory=list)
    required_layers: List[RequiredLayer] = field(default_factory=list)
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
    module: str = ""


@dataclass
class ScenarioView:
    scenario: Scenario
    linked_results: List[TestResult] = field(default_factory=list)
    layers: List[List[TestResult]] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return bool(self.linked_results)
