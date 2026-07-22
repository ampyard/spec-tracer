from datetime import datetime, timezone
from typing import List

from spec_tracer.models import ScenarioView, TestResult

SCHEMA_VERSION = "2"

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


def _requirements(view: ScenarioView) -> List[dict]:
    requirements = []
    for req in view.scenario.required_layers:
        satisfied = any(
            r.layer == req.layer and (req.module == "" or r.module == req.module)
            for r in view.linked_results
        )
        entry = {"layer": req.layer, "satisfied": satisfied}
        if req.module:
            entry["module"] = req.module
        requirements.append(entry)
    return requirements


def _scenario_result(view: ScenarioView) -> dict:
    return {
        "name": view.scenario.name,
        "tags": list(view.scenario.tags),
        "requirements": _requirements(view),
        "results": [_result_dict(result) for result in view.linked_results],
    }


def _features(views: List[ScenarioView], feature_files: dict) -> List[dict]:
    order: List[str] = []
    by_feature: dict = {}
    for view in views:
        name = view.scenario.feature
        if name not in by_feature:
            by_feature[name] = []
            order.append(name)
        by_feature[name].append(_scenario_result(view))
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
            "tags": list(result.tags),
        }
        if result.module:
            entry["module"] = result.module
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
            },
            "pyramid": _layer_stats(layer_stats),
            "health": _health_summary(health_checks),
        },
        "features": _features(views, feature_files or {}),
        "unlinkedTests": _unlinked_tests(unlinked_results),
    }
