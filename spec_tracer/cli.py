import base64
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

from spec_tracer.aggregator import ReportAggregator
from spec_tracer.collectors import FileCollector
from spec_tracer.linker import ResultLinker
from spec_tracer.parsers import CucumberParser, FeatureParser, JunitParser
from spec_tracer.renderers import HtmlRenderer
from spec_tracer.report_model import build_report

DEFAULT_CONFIG_NAME = "spectracer.config.json"

# Maps the friendly names accepted in the `fail_on` config to the internal
# health-check keys produced by ReportAggregator.health_checks.
FAIL_ON_ALIASES = {
    "progress": "Progress",
    "pyramid": "pyramid",
    "e2e_runtime": "end_to_end_runtime",
}


def _find_config_path(argv: List[str] | None = None) -> Path:
    args = sys.argv[1:] if argv is None else argv
    if args:
        path = Path(args[0])
    else:
        path = Path(DEFAULT_CONFIG_NAME)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    return path


def _load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if "features" not in config:
        raise ValueError("Config is missing required key: 'features'")
    if "output" not in config:
        raise ValueError("Config is missing required key: 'output'")
    fail_on = config.get("fail_on", [])
    if not isinstance(fail_on, list):
        raise ValueError("Config key 'fail_on' must be a list of health check names")
    not_strings = [name for name in fail_on if not isinstance(name, str)]
    if not_strings:
        raise ValueError(
            f"Config key 'fail_on' entries must be strings, got: {not_strings}"
        )
    unknown = [name for name in fail_on if name not in FAIL_ON_ALIASES]
    if unknown:
        accepted = ", ".join(sorted(FAIL_ON_ALIASES))
        raise ValueError(
            f"Config key 'fail_on' has unknown health checks: {unknown}. Accepted values: {accepted}"
        )
    duplicates = sorted({name for name in fail_on if fail_on.count(name) > 1})
    if duplicates:
        raise ValueError(f"Config key 'fail_on' has duplicate entries: {duplicates}")
    return config


def _failing_gated_checks(health_checks: dict, fail_on: List[str]) -> List[str]:
    """Return the ``fail_on`` names whose health check is in a failing state."""
    return [
        name
        for name in fail_on
        if health_checks.get(FAIL_ON_ALIASES[name], {}).get("status") == "fail"
    ]


def _load_logo(config_dir: Path) -> str:
    logo_path = config_dir / "docs" / "logo.png"
    if logo_path.exists():
        data = logo_path.read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    return ""


def _collect_and_parse_features(paths: List[str], base_dir: Path) -> tuple:
    files = FileCollector.feature_files(paths)
    if not files:
        raise FileNotFoundError("No feature files were found")
    scenarios = []
    feature_files: Dict[str, str] = {}
    parser = FeatureParser()
    resolved_base = base_dir.resolve()
    for f in files:
        parsed = parser.parse(f)
        relative = os.path.relpath(f, resolved_base)
        for scenario in parsed:
            feature_files.setdefault(scenario.feature, relative.replace("\\", "/"))
        scenarios.extend(parsed)
    return scenarios, feature_files


def _collect_and_parse_junit_results(entries: Dict[str, List[str]], parser: JunitParser, layer: str) -> List:
    results = []
    for module, paths in entries.items():
        files = FileCollector.xml_files(paths)
        results.extend(parser.parse(files, layer=layer, module=module))
    return results


def _collect_and_parse_e2e_results(entries: Dict[str, List[str]], parser: CucumberParser) -> List:
    results = []
    for module, paths in entries.items():
        files = FileCollector.json_files(paths)
        results.extend(parser.parse(files, layer="e2e", module=module))
    return results


def main(argv: List[str] | None = None) -> int:
    config_path = _find_config_path(argv)
    config = _load_config(config_path)

    scenarios, feature_files = _collect_and_parse_features(config["features"], config_path.parent)

    junit_parser = JunitParser()
    unit_results = _collect_and_parse_junit_results(config.get("unit", {}), junit_parser, "unit")
    integration_results = _collect_and_parse_junit_results(config.get("integration", {}), junit_parser, "integration")

    cucumber_parser = CucumberParser()
    e2e_results = _collect_and_parse_e2e_results(config.get("e2e", {}), cucumber_parser)

    results = e2e_results + unit_results + integration_results

    links = ResultLinker.link(scenarios, results)
    views = ReportAggregator.build_views(scenarios, links)
    stats = ReportAggregator.completion_stats(views)
    breakdown = ReportAggregator.feature_breakdown(views)
    layer_stats = ReportAggregator.layer_stats(views)
    failed_results = [result for result in results if result.status == "failed"]
    unlinked_results = ReportAggregator.unlinked_results(scenarios, results)
    health_check_config = config.get("health_checks", {})
    health_checks = ReportAggregator.health_checks(
        views,
        layer_stats,
        stats,
        unlinked_count=len(unlinked_results),
        progress_threshold_green=health_check_config.get("progress_threshold_green", 80),
        progress_threshold_amber=health_check_config.get("progress_threshold_amber", 50),
        e2e_duration_amber_seconds=health_check_config.get("e2e_duration_amber_seconds", 600),
        e2e_duration_red_seconds=health_check_config.get("e2e_duration_red_seconds", 1800),
    )
    failure_breakdown = ReportAggregator.failure_breakdown(views)

    renderer = HtmlRenderer()
    html = renderer.render(
        views,
        stats,
        breakdown,
        layer_stats=layer_stats,
        health_checks=health_checks,
        failed_results=failed_results,
        unlinked_results=unlinked_results,
        failure_breakdown=failure_breakdown,
        logo_data_uri=_load_logo(config_path.parent),
    )

    output_path = Path(config["output"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    if config.get("output_json"):
        report = build_report(
            config,
            views,
            stats,
            layer_stats,
            health_checks,
            unlinked_results,
            feature_files=feature_files,
        )
        output_json_path = Path(config["output_json"])
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    failing_checks = _failing_gated_checks(health_checks, config.get("fail_on", []))
    if failing_checks:
        print(
            "Health check gate failed (fail_on): " + ", ".join(failing_checks),
            file=sys.stderr,
        )

    error_on_failure = config.get("error_on_failure", False) and any(
        result.status == "failed" for result in results
    )
    if error_on_failure or failing_checks:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
