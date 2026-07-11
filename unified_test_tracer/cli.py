import base64
import json
import sys
from pathlib import Path
from typing import Dict, List

from unified_test_tracer.aggregator import ReportAggregator
from unified_test_tracer.collectors import FileCollector
from unified_test_tracer.linker import ResultLinker
from unified_test_tracer.parsers import CucumberParser, FeatureParser, JunitParser
from unified_test_tracer.renderers import HtmlRenderer

DEFAULT_CONFIG_NAME = "spectracer.config.json"


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
    return config


def _load_logo(config_dir: Path) -> str:
    logo_path = config_dir / "docs" / "logo.png"
    if logo_path.exists():
        data = logo_path.read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    return ""


def _collect_and_parse_features(paths: List[str]) -> List:
    files = FileCollector.feature_files(paths)
    if not files:
        raise FileNotFoundError("No feature files were found")
    scenarios = []
    parser = FeatureParser()
    for f in files:
        scenarios.extend(parser.parse(f))
    return scenarios


def _collect_and_parse_junit_results(entries: Dict[str, List[str]], parser: JunitParser, layer: str) -> List:
    results = []
    for module, paths in entries.items():
        files = FileCollector.xml_files(paths)
        results.extend(parser.parse(files, layer=layer, module=module))
    return results


def _collect_and_parse_e2e_results(paths: List[str], parser: CucumberParser) -> List:
    files = FileCollector.json_files(paths)
    return parser.parse(files, layer="e2e")


def main(argv: List[str] | None = None) -> int:
    config_path = _find_config_path(argv)
    config = _load_config(config_path)

    scenarios = _collect_and_parse_features(config["features"])

    junit_parser = JunitParser()
    unit_results = _collect_and_parse_junit_results(config.get("unit", {}), junit_parser, "unit")
    integration_results = _collect_and_parse_junit_results(config.get("integration", {}), junit_parser, "integration")

    cucumber_parser = CucumberParser()
    e2e_results = _collect_and_parse_e2e_results(config.get("e2e", []), cucumber_parser)

    results = e2e_results + unit_results + integration_results

    links = ResultLinker.link(scenarios, results)
    views = ReportAggregator.build_views(scenarios, links)
    stats = ReportAggregator.coverage_stats(views)
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
        coverage_threshold_green=health_check_config.get("coverage_threshold_green", 80),
        coverage_threshold_amber=health_check_config.get("coverage_threshold_amber", 50),
        e2e_speed_threshold_pct=health_check_config.get("e2e_speed_threshold_pct", 50),
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

    if config.get("error_on_failure", False) and any(result.status == "failed" for result in results):
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
