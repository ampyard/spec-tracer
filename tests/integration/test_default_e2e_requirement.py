import json
import shutil
import subprocess
import sys
import textwrap
import uuid

import pytest

from conftest import ROOT, run_tool


@pytest.fixture
def workdir():
    path = ROOT / "reports" / f"default-e2e-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _features(workdir):
    features = workdir / "features"
    features.mkdir()
    (features / "login.feature").write_text(
        textwrap.dedent(
            """\
            Feature: User Login

              @id:FC-001
              Scenario: Untagged scenario
                Given a step
            """
        ),
        encoding="utf-8",
    )
    return features


def _scenario(report_path):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return report, report["features"][0]["scenarios"][0]


def _run_cli(workdir, features, extra_args, **config_extra):
    config = {"features": [str(features)], "output": str(workdir / "report.html"),
              "output_json": str(workdir / "report.json"), **config_extra}
    config_path = workdir / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return subprocess.run(
        [sys.executable, "build_pyramid.py", str(config_path), *extra_args],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def _required_count(report_path):
    return len(_scenario(report_path)[1]["requirements"])


@pytest.mark.parametrize("tag", ["@scenario:FC-014"])
def test_untagged_scenario_requires_e2e_by_default(tag, workdir):
    result = _run_cli(workdir, _features(workdir), [])
    assert result.returncode == 0, result.stderr
    assert _required_count(workdir / "report.json") == 1


@pytest.mark.parametrize("tag", ["@scenario:FC-014"])
def test_config_false_removes_implicit_requirement(tag, workdir):
    result = _run_cli(workdir, _features(workdir), [], default_e2e_requirement=False)
    assert result.returncode == 0, result.stderr
    assert _required_count(workdir / "report.json") == 0
    report = json.loads((workdir / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["completion"]["required"] == 1 and report["summary"]["completion"]["satisfied"] == 1


@pytest.mark.parametrize("tag", ["@scenario:FC-014"])
def test_cli_flag_overrides_config_in_both_directions(tag, workdir):
    features = _features(workdir)
    assert _run_cli(workdir, features, ["--no-default-e2e-requirement"]).returncode == 0
    assert _required_count(workdir / "report.json") == 0

    result = _run_cli(workdir, features, ["--default-e2e-requirement"], default_e2e_requirement=False)
    assert result.returncode == 0, result.stderr
    assert _required_count(workdir / "report.json") == 1


@pytest.mark.parametrize("tag", ["@scenario:FC-014"])
def test_non_boolean_config_value_is_rejected(tag, workdir):
    result = run_tool(_features(workdir), workdir / "report.html", default_e2e_requirement="no")
    assert result.returncode != 0
    assert "default_e2e_requirement" in result.stderr
