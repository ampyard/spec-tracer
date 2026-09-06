from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from spec_tracer.models import ScenarioView, TestResult, completion_fraction, requirement_state

SCHEMA_VERSION = "3"

_HEALTH_STATUS_RANK = {"pass": 0, "warn": 1, "fail": 2}
_HEALTH_STATUS_LABEL = {"pass": "green", "warn": "amber", "fail": "red"}


def _duration_ms(result: TestResult) -> float:
    return result.duration * 1000


def _result_dict(result: TestResult) -> dict:
    data = {
        "layer": result.layer,
        "testId": result.name,
        "name": result.name,
        "status": result.status,
    }
    if result.module:
        data["module"] = result.module
    if result.duration:
        data["duration"] = _duration_ms(result)
    if result.status == "failed" and result.failure_message:
        data["failureMessage"] = result.failure_message
    return data


def _requirements(view: ScenarioView, known_modules: Optional[Dict[str, Set[str]]] = None) -> List[dict]:
    requirements = []
    for req in view.scenario.required_layers:
        state = requirement_state(req, view.linked_results, known_modules)
        entry = {"layer": req.layer, "satisfied": state == "ok"}
        if req.module:
            entry["module"] = req.module
        # Only present when a config cross-check ran and flagged the module as
        # unregistered — additive so reports built without known_modules (or
        # where nothing is unconfigured) keep the old requirement shape (#8).
        if state == "unconfigured":
            entry["unconfigured"] = True
        requirements.append(entry)
    return requirements


def _scenario_result(view: ScenarioView, known_modules: Optional[Dict[str, Set[str]]] = None) -> dict:
    return {
        "name": view.scenario.name,
        "tags": list(view.scenario.tags),
        "requirements": _requirements(view, known_modules),
        "results": [_result_dict(result) for result in view.linked_results],
        "steps": list(view.scenario.steps),
    }


def _features(views: List[ScenarioView], feature_files: dict, known_modules: Optional[Dict[str, Set[str]]] = None) -> List[dict]:
    order: List[str] = []
    by_feature: dict = {}
    for view in views:
        name = view.scenario.feature
        if name not in by_feature:
            by_feature[name] = []
            order.append(name)
        by_feature[name].append(_scenario_result(view, known_modules))
    return [
        {
            "name": name,
            "file": feature_files.get(name, ""),
            "scenarios": by_feature[name],
        }
        for name in order
    ]


def _layer_stats(layer_stats: List[dict]) -> dict:
    return {
        metric["name"]: {
            "testCount": metric["count"],
            "duration": metric["duration"] * 1000,
            "passRate": metric["pass_pct"],
        }
        for metric in layer_stats
    }


def _layer_stats_detail(layer_stats: List[dict]) -> List[dict]:
    """Full per-layer stats in presentation order (``LAYER_ORDER``).

    The render contract for the Test Pyramid page and the pyramid health card.
    ``summary.pyramid`` stays a lean CI-facing rollup; this carries everything
    the tree tier needs (pass/fail/skip split, width, duration) (#36).
    """
    return [
        {
            "name": metric["name"],
            "count": metric["count"],
            "passed": metric["passed"],
            "failed": metric["failed"],
            "skipped": metric["skipped"],
            "duration": metric["duration"] * 1000,
            "passRate": metric["pass_pct"],
            "failRate": metric["fail_pct"],
            "skipRate": metric["skip_pct"],
            "widthPct": metric["width_pct"],
        }
        for metric in layer_stats
    ]


def _health_checks(health_checks: dict) -> List[dict]:
    """Individual health-check cards in display order.

    The render contract for the dashboard Health Check grid (#36). Keeps the
    same order as ``ReportAggregator.health_checks`` so the client renderer can
    reproduce the server-side card sequence without re-deriving statuses.
    """
    checks = []
    for key, item in health_checks.items():
        entry = {
            "key": key,
            "status": item["status"],
            "message": item["message"],
            "value": item["value"],
        }
        if item.get("layers"):
            entry["layers"] = item["layers"]
        checks.append(entry)
    return checks


def _health_summary(health_checks: dict) -> dict:
    worst_status = "pass"
    reasons: List[str] = []
    for check in health_checks.values():
        if check["status"] != "pass":
            reasons.append(check["message"])
        if _HEALTH_STATUS_RANK[check["status"]] > _HEALTH_STATUS_RANK[worst_status]:
            worst_status = check["status"]
    return {"status": _HEALTH_STATUS_LABEL[worst_status], "reasons": reasons}


def _unlinked_tests(unlinked_results: List[TestResult]) -> List[dict]:
    entries = []
    for result in unlinked_results:
        entry = {
            "layer": result.layer,
            "testId": result.name,
            "name": result.name,
            "status": result.status,
            "tags": list(result.tags),
        }
        if result.module:
            entry["module"] = result.module
        if result.duration:
            entry["duration"] = _duration_ms(result)
        entries.append(entry)
    return entries


def build_report(
    config: dict,
    views: List[ScenarioView],
    stats: dict,
    layer_stats: List[dict],
    health_checks: dict,
    unlinked_results: List[TestResult],
    feature_files: dict | None = None,
    known_modules: Optional[Dict[str, Set[str]]] = None,
) -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config": config,
        "summary": {
            "completion": {
                "tested": stats["complete"],
                "total": stats["total"],
                "percent": stats["percentage"],
                "pct": stats["pct"],
                "satisfied": stats["satisfied"],
                "required": stats["required"],
            },
            "pyramid": _layer_stats(layer_stats),
            "layerStats": _layer_stats_detail(layer_stats),
            "health": _health_summary(health_checks),
            "healthChecks": _health_checks(health_checks),
        },
        "features": _features(views, feature_files or {}, known_modules),
        "unlinkedTests": _unlinked_tests(unlinked_results),
    }
