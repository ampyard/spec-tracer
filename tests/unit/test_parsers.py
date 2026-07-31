import pytest

from spec_tracer.parsers import CucumberParser, FeatureParser, JunitParser


@pytest.mark.parametrize("tag", ["@scenario:FC-007"])
def test_junit_parser_rejects_malformed_xml_with_clear_error(tag, tmp_path):
    bad_xml = tmp_path / "unit.xml"
    bad_xml.write_text("<testsuite><testcase name=\"t\"", encoding="utf-8")

    with pytest.raises(ValueError, match=f"Malformed JUnit XML in {bad_xml}"):
        JunitParser().parse([bad_xml], layer="unit")


def test_junit_parser_extracts_tags_status_and_module(tmp_path):
    xml = tmp_path / "unit.xml"
    xml.write_text(
        '<testsuite><testcase classname="c" name="t @scenario:FC-100" time="0.5">'
        "<failure message=\"boom\">trace</failure>"
        "</testcase></testsuite>",
        encoding="utf-8",
    )

    results = JunitParser().parse([xml], layer="unit", module="parsers")

    assert len(results) == 1
    result = results[0]
    assert result.status == "failed"
    assert result.module == "parsers"
    assert "@scenario:FC-100" in result.tags
    assert result.duration == 0.5


def test_feature_parser_reads_scenario_tags_and_required_layers():
    feature_file_content = (
        "Feature: Sample\n\n"
        '  @id:FC-900 @scenario:FC-900 @require-unit:parsers\n'
        "  Scenario: A scenario\n"
        "    Given a step\n"
    )

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "sample.feature"
        path.write_text(feature_file_content, encoding="utf-8")

        scenarios = FeatureParser.parse(path)

    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert "@id:FC-900" in scenario.tags
    assert scenario.required_layers[0].layer == "unit"
    assert scenario.required_layers[0].module == "parsers"


def test_cucumber_parser_reads_scenario_status_and_tags(tmp_path):
    payload_path = tmp_path / "e2e.json"
    payload_path.write_text(
        """
        [{
          "elements": [{
            "keyword": "Scenario",
            "name": "A scenario",
            "status": "passed",
            "tags": [{"name": "@scenario:FC-200"}],
            "steps": [{"result": {"status": "passed", "duration": 1000000000}}]
          }]
        }]
        """,
        encoding="utf-8",
    )

    results = CucumberParser().parse([payload_path], module="parsers")

    assert len(results) == 1
    assert results[0].status == "passed"
    assert results[0].module == "parsers"
    assert "@scenario:FC-200" in results[0].tags
    assert results[0].duration == 1.0
