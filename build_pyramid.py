#!/usr/bin/env python3
import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

try:
    from jinja2 import Template
except ImportError:  # pragma: no cover - fallback for environments without Jinja2
    Template = None


@dataclass
class Scenario:
    feature: str
    name: str
    tags: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    linked_results: List["TestResult"] = field(default_factory=list)

    @property
    def is_tested(self) -> bool:
        return bool(self.linked_results)


@dataclass
class TestResult:
    layer: str
    name: str
    tags: List[str] = field(default_factory=list)
    status: str = "passed"
    duration: float = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a unified test coverage HTML report")
    parser.add_argument("--features", required=True, nargs="+", help="Feature file(s) or directory")
    parser.add_argument("--e2e", nargs="+", default=[], help="Cucumber JSON file(s) or directory")
    parser.add_argument("--output", required=True, help="Path to output HTML report")
    parser.add_argument("--error-on-failure", action="store_true", help="Exit non-zero on any failing result")
    return parser.parse_args()


def collect_feature_files(paths: List[str]) -> List[Path]:
    files: List[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"Feature path does not exist: {path}")
        if path.is_file() and path.suffix == ".feature":
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.feature")))
    return sorted({path.resolve() for path in files})


def collect_result_files(paths: List[str]) -> List[Path]:
    files: List[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.json")))
    return sorted({path.resolve() for path in files})


def parse_feature_file(path: Path) -> List[Scenario]:
    scenarios: List[Scenario] = []
    feature_name = path.stem
    current_tags: List[str] = []
    current_scenario: Scenario | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("Feature:"):
            feature_name = stripped.split(":", 1)[1].strip()
            current_tags = []
            continue
        if stripped.startswith("@"):
            current_tags.append(stripped)
            continue
        if stripped.startswith(("Scenario:", "Scenario Outline:")):
            if current_scenario is not None:
                scenarios.append(current_scenario)
            current_scenario = Scenario(
                feature=feature_name,
                name=stripped.split(":", 1)[1].strip(),
                tags=current_tags.copy(),
                steps=[],
            )
            current_tags = []
            continue
        if current_scenario is not None:
            current_scenario.steps.append(stripped)

    if current_scenario is not None:
        scenarios.append(current_scenario)

    return scenarios


def parse_e2e_results(paths: List[Path]) -> List[TestResult]:
    results: List[TestResult] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            payload = [payload]
        for feature in payload:
            for element in feature.get("elements", []):
                if not isinstance(element, dict):
                    continue
                if element.get("keyword", "").lower() != "scenario":
                    continue
                tags = [tag.get("name", "") for tag in element.get("tags", []) if isinstance(tag, dict)]
                status = element.get("status", "passed")
                if status == "undefined":
                    status = "skipped"
                results.append(
                    TestResult(
                        layer="e2e",
                        name=element.get("name", ""),
                        tags=tags,
                        status=status,
                    )
                )
    return results


def build_report_html(scenarios: List[Scenario], results: List[TestResult]) -> str:
    for scenario in scenarios:
        scenario.linked_results = [
            result
            for result in results
            if any(tag in scenario.tags for tag in result.tags)
        ]

    total = len(scenarios)
    tested = sum(1 for scenario in scenarios if scenario.is_tested)
    percentage = int(round((tested / total * 100) if total else 0))

    feature_breakdown = []
    features = defaultdict(list)
    for scenario in scenarios:
        features[scenario.feature].append(scenario)

    for feature_name, feature_scenarios in sorted(features.items()):
        feature_tested = sum(1 for scenario in feature_scenarios if scenario.is_tested)
        feature_total = len(feature_scenarios)
        feature_percentage = int(round((feature_tested / feature_total * 100) if feature_total else 0))
        feature_breakdown.append(
            {
                "name": feature_name,
                "tested": feature_tested,
                "total": feature_total,
                "percentage": feature_percentage,
            }
        )

    if Template is not None:
        template = Template(
            """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Unified Test Tracer</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; color: #123; }
    .hero { background: #f5f7fb; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .progress { height: 16px; background: #e5e7eb; border-radius: 999px; overflow: hidden; }
    .progress > div { height: 100%; background: #2f855a; }
    .feature-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; }
    .pill { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; background: #dbeafe; font-size: 0.9rem; }
  </style>
</head>
<body>
  <div class=\"hero\">
    <h1>Scenario Coverage Progress</h1>
    <p>{{ tested }}/{{ total }} scenarios tested</p>
    <div class=\"progress\"><div style=\"width: {{ percentage }}%;\"></div></div>
  </div>

  <h2>Feature Breakdown</h2>
  {% for feature in feature_breakdown %}
  <div class=\"feature-card\">
    <strong>{{ feature.name }}</strong>
    <div style=\"margin: 0.5rem 0;\">{{ feature.tested }}/{{ feature.total }} scenarios tested</div>
    <div class=\"progress\"><div style=\"width: {{ feature.percentage }}%;\"></div></div>
  </div>
  {% endfor %}

  <h2>Scenarios</h2>
  <ul>
    {% for scenario in scenarios %}
    <li>
      <span class=\"pill\">{{ scenario.feature }}</span>
      {{ scenario.name }} - {% if scenario.is_tested %}tested{% else %}untested{% endif %}
    </li>
    {% endfor %}
  </ul>
</body>
</html>
            """
        )
        return template.render(
            tested=tested,
            total=total,
            percentage=percentage,
            feature_breakdown=feature_breakdown,
            scenarios=scenarios,
        )

    # Fallback renderer if Jinja2 is unavailable.
    lines = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head><meta charset=\"utf-8\"><title>Unified Test Tracer</title></head>",
        "<body>",
        "<h1>Scenario Coverage Progress</h1>",
        f"<p>{tested}/{total} scenarios tested</p>",
        "<ul>",
    ]
    for scenario in scenarios:
        status = "tested" if scenario.is_tested else "untested"
        lines.append(f"<li>{scenario.feature}: {scenario.name} - {status}</li>")
    lines.extend(["</ul>", "</body>", "</html>"])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    feature_files = collect_feature_files(args.features)
    if not feature_files:
        raise FileNotFoundError("No feature files were found")

    scenarios: List[Scenario] = []
    for feature_file in feature_files:
        scenarios.extend(parse_feature_file(feature_file))

    result_files = collect_result_files(args.e2e)
    results = parse_e2e_results(result_files)
    html = build_report_html(scenarios, results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    if args.error_on_failure and any(result.status == "failed" for result in results):
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
