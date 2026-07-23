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
]

BEHAVE_STEPS = [
    ("BDD suite (HTML report)", [
        "uv", "run", "behave", "features/", "-f", "modern", "-o", "reports/e2e-report.html",
    ]),
    ("E2E: linker", [
        "uv", "run", "behave", "features/coverage_linking.feature",
        "--tags=-@FC-004", "-f", "json", "-o", "reports/e2e-linker.json",
    ]),
    ("E2E: linker (edge)", [
        "uv", "run", "behave", "features/coverage_edge_cases.feature",
        "--tags=-@FC-EDGE-006", "-f", "json", "-o", "reports/e2e-linker-edge.json",
    ]),
    ("E2E: collectors", [
        "uv", "run", "behave", "features/coverage_linking.feature",
        "--tags=@FC-004", "-f", "json", "-o", "reports/e2e-collectors.json",
    ]),
    ("E2E: aggregator", [
        "uv", "run", "behave", "features/coverage_health.feature",
        "-f", "json", "-o", "reports/e2e-aggregator.json",
    ]),
    ("E2E: aggregator (internals)", [
        "uv", "run", "behave", "features/coverage_internals.feature",
        "--tags=@FC-008", "-f", "json", "-o", "reports/e2e-aggregator-internals.json",
    ]),
    ("E2E: renderers", [
        "uv", "run", "behave", "features/coverage_dashboard.feature",
        "-f", "json", "-o", "reports/e2e-renderers.json",
    ]),
    ("E2E: renderers (internals)", [
        "uv", "run", "behave", "features/coverage_internals.feature",
        "--tags=@FC-009", "-f", "json", "-o", "reports/e2e-renderers-internals.json",
    ]),
    ("E2E: parsers", [
        "uv", "run", "behave", "features/coverage_module_scope.feature",
        "-f", "json", "-o", "reports/e2e-parsers.json",
    ]),
    ("E2E: parsers (edge)", [
        "uv", "run", "behave", "features/coverage_edge_cases.feature",
        "--tags=@FC-EDGE-006", "-f", "json", "-o", "reports/e2e-parsers-edge.json",
    ]),
    ("E2E: parsers (internals)", [
        "uv", "run", "behave", "features/coverage_internals.feature",
        "--tags=@FC-007", "-f", "json", "-o", "reports/e2e-parsers-internals.json",
    ]),
    ("E2E: report_model", [
        "uv", "run", "behave", "features/coverage_json_output.feature",
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
