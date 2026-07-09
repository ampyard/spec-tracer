import argparse
import sys
from pathlib import Path
from typing import List

from unified_test_tracer.aggregator import ReportAggregator
from unified_test_tracer.collectors import FileCollector
from unified_test_tracer.linker import ResultLinker
from unified_test_tracer.parsers import CucumberParser, FeatureParser, JunitParser
from unified_test_tracer.renderers import HtmlRenderer


def _parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a unified test coverage HTML report")
    parser.add_argument("--features", required=True, nargs="+", help="Feature file(s) or directory")
    parser.add_argument("--unit", action="append", default=[], help="Unit test JUnit XML file(s) or directory")
    parser.add_argument("--integration", action="append", default=[], help="Integration test JUnit XML file(s) or directory")
    parser.add_argument("--e2e", nargs="+", default=[], help="Cucumber JSON file(s) or directory")
    parser.add_argument("--output", required=True, help="Path to output HTML report")
    parser.add_argument("--error-on-failure", action="store_true", help="Exit non-zero on any failing result")
    return parser.parse_args(argv)


def _collect_and_parse_features(paths: List[str]) -> List:
    files = FileCollector.feature_files(paths)
    if not files:
        raise FileNotFoundError("No feature files were found")
    scenarios = []
    parser = FeatureParser()
    for f in files:
        scenarios.extend(parser.parse(f))
    return scenarios


def _collect_and_parse_results(paths: List[str], parser, layer: str) -> List:
    files = FileCollector.xml_files(paths) if layer != "e2e" else FileCollector.json_files(paths)
    return parser.parse(files, layer=layer)


def main(argv: List[str] | None = None) -> int:
    args = _parse_args(argv)

    scenarios = _collect_and_parse_features(args.features)

    junit_parser = JunitParser()
    unit_results = _collect_and_parse_results(args.unit, junit_parser, "unit")
    integration_results = _collect_and_parse_results(args.integration, junit_parser, "integration")

    cucumber_parser = CucumberParser()
    e2e_results = _collect_and_parse_results(args.e2e, cucumber_parser, "e2e")

    results = e2e_results + unit_results + integration_results

    links = ResultLinker.link(scenarios, results)
    views = ReportAggregator.build_views(scenarios, links)
    stats = ReportAggregator.coverage_stats(views)
    breakdown = ReportAggregator.feature_breakdown(views)
    layer_stats = ReportAggregator.layer_stats(views)
    failed_results = [result for result in results if result.status == "failed"]
    unlinked_results = ReportAggregator.unlinked_results(scenarios, results)
    health_checks = ReportAggregator.health_checks(views, layer_stats, stats, unlinked_count=len(unlinked_results))
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
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    if args.error_on_failure and any(result.status == "failed" for result in results):
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
