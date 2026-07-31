#!/usr/bin/env python3
"""Reproduce the CI test/report pipeline locally, in one command.

Runs the same pytest + behave invocations as .github/workflows/ci.yml,
in the same order, writing to the same ./reports/ paths that
spectracer.config.json expects. Then generates the SpecTracer report.

Usage:
    uv run python run_local.py
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
REPORTS_DIR = REPO_ROOT / "reports"

PYTEST_STEPS = [
    ("Unit tests", [
        "uv", "run", "pytest", "tests/unit/",
        "--junitxml=reports/unit.xml",
        "--html=reports/unit.html", "--self-contained-html", "-v",
    ]),
    ("Integration tests", [
        "uv", "run", "pytest", "tests/integration/",
        "--junitxml=reports/int.xml",
        "--html=reports/int.html", "--self-contained-html", "-v",
    ]),
    # Per-module JUnit XML for SpecTracer dogfood — one test file, one module,
    # one XML, matching spectracer.config.json's module map (#module-scope).
    ("Unit: aggregator", [
        "uv", "run", "pytest", "tests/unit/test_aggregator.py",
        "--junitxml=reports/unit-aggregator.xml", "-q",
    ]),
    ("Unit: renderers", [
        "uv", "run", "pytest", "tests/unit/test_renderers.py",
        "--junitxml=reports/unit-renderers.xml", "-q",
    ]),
    ("Unit: report_model", [
        "uv", "run", "pytest", "tests/unit/test_report_model.py",
        "--junitxml=reports/unit-report_model.xml", "-q",
    ]),
    ("Unit: cli", [
        "uv", "run", "pytest", "tests/unit/test_cli.py",
        "--junitxml=reports/unit-cli.xml", "-q",
    ]),
    ("Unit: linker", [
        "uv", "run", "pytest", "tests/unit/test_linker.py",
        "--junitxml=reports/unit-linker.xml", "-q",
    ]),
    ("Unit: collectors", [
        "uv", "run", "pytest", "tests/unit/test_collectors.py",
        "--junitxml=reports/unit-collectors.xml", "-q",
    ]),
    ("Unit: parsers", [
        "uv", "run", "pytest", "tests/unit/test_parsers.py",
        "--junitxml=reports/unit-parsers.xml", "-q",
    ]),
    ("Unit: build_pyramid", [
        "uv", "run", "pytest", "tests/unit/test_build_pyramid.py",
        "--junitxml=reports/unit-build_pyramid.xml", "-q",
    ]),
    ("Integration: linker", [
        "uv", "run", "pytest", "tests/integration/test_integration_linking.py",
        "--junitxml=reports/int-linker.xml", "-q",
    ]),
    ("Integration: collectors", [
        "uv", "run", "pytest", "tests/integration/test_collectors_integration.py",
        "--junitxml=reports/int-collectors.xml", "-q",
    ]),
    ("Integration: e2e_coverage", [
        "uv", "run", "pytest", "tests/integration/test_e2e_coverage.py",
        "--junitxml=reports/int-e2e_coverage.xml", "-q",
    ]),
    ("Integration: e2e_module_scope", [
        "uv", "run", "pytest", "tests/integration/test_e2e_module_scope.py",
        "--junitxml=reports/int-e2e_module_scope.xml", "-q",
    ]),
    ("Integration: edge_cases", [
        "uv", "run", "pytest", "tests/integration/test_edge_cases.py",
        "--junitxml=reports/int-edge_cases.xml", "-q",
    ]),
    ("Integration: fail_on", [
        "uv", "run", "pytest", "tests/integration/test_fail_on.py",
        "--junitxml=reports/int-fail_on.xml", "-q",
    ]),
    ("Integration: json_report", [
        "uv", "run", "pytest", "tests/integration/test_json_report.py",
        "--junitxml=reports/int-json_report.xml", "-q",
    ]),
    ("Integration: missing_required_layer", [
        "uv", "run", "pytest", "tests/integration/test_missing_required_layer.py",
        "--junitxml=reports/int-missing_required_layer.xml", "-q",
    ]),
    ("Integration: status_badges", [
        "uv", "run", "pytest", "tests/integration/test_status_badges.py",
        "--junitxml=reports/int-status_badges.xml", "-q",
    ]),
    ("Integration: unit_linking", [
        "uv", "run", "pytest", "tests/integration/test_unit_linking.py",
        "--junitxml=reports/int-unit_linking.xml", "-q",
    ]),
]

BEHAVE_STEPS = [
    ("BDD suite (HTML report)", [
        "uv", "run", "behave", "features/", "-f", "modern", "-o", "reports/e2e-report.html",
    ]),
    ("E2E: linker", [
        "uv", "run", "behave", "features/linking.feature",
        "--tags=not @scenario:FC-004", "-f", "json", "-o", "reports/e2e-linker.json",
    ]),
    ("E2E: linker (edge)", [
        "uv", "run", "behave", "features/edge_cases.feature",
        "--tags=not @scenario:FC-EDGE-006", "-f", "json", "-o", "reports/e2e-linker-edge.json",
    ]),
    ("E2E: collectors", [
        "uv", "run", "behave", "features/linking.feature",
        "--tags=@scenario:FC-004", "-f", "json", "-o", "reports/e2e-collectors.json",
    ]),
    ("E2E: aggregator", [
        "uv", "run", "behave", "features/health.feature",
        "-f", "json", "-o", "reports/e2e-aggregator.json",
    ]),
    ("E2E: aggregator (internals)", [
        "uv", "run", "behave", "features/internals.feature",
        "--tags=@scenario:FC-008", "-f", "json", "-o", "reports/e2e-aggregator-internals.json",
    ]),
    ("E2E: renderers", [
        "uv", "run", "behave", "features/dashboard.feature",
        "-f", "json", "-o", "reports/e2e-renderers.json",
    ]),
    ("E2E: renderers (internals)", [
        "uv", "run", "behave", "features/internals.feature",
        "--tags=@scenario:FC-009", "-f", "json", "-o", "reports/e2e-renderers-internals.json",
    ]),
    ("E2E: parsers", [
        "uv", "run", "behave", "features/module_scope.feature",
        "-f", "json", "-o", "reports/e2e-parsers.json",
    ]),
    ("E2E: parsers (edge)", [
        "uv", "run", "behave", "features/edge_cases.feature",
        "--tags=@scenario:FC-EDGE-006", "-f", "json", "-o", "reports/e2e-parsers-edge.json",
    ]),
    ("E2E: parsers (internals)", [
        "uv", "run", "behave", "features/internals.feature",
        "--tags=@scenario:FC-007", "-f", "json", "-o", "reports/e2e-parsers-internals.json",
    ]),
    ("E2E: report_model", [
        "uv", "run", "behave", "features/json_output.feature",
        "-f", "json", "-o", "reports/e2e-report-model.json",
    ]),
]


def run_step(label: str, cmd: list[str]) -> bool:
    print(f"\n=== {label} ===")
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    # pytest/behave exit non-zero on test failures; that's expected and
    # shouldn't abort the pipeline — we still want a report generated.
    return result.returncode == 0


def main() -> int:
    REPORTS_DIR.mkdir(exist_ok=True)

    all_ok = True
    for label, cmd in PYTEST_STEPS + BEHAVE_STEPS:
        if not run_step(label, cmd):
            all_ok = False

    print("\n=== Generating SpecTracer report ===")
    report_result = subprocess.run(
        ["uv", "run", "python", "build_pyramid.py"], cwd=REPO_ROOT
    )

    if not all_ok:
        print(
            "\nNote: one or more test steps failed above (expected if you have "
            "failing tests) — the report reflects those failures.",
            file=sys.stderr,
        )

    return report_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
