import shutil
import textwrap
import uuid
from pathlib import Path

import pytest

from conftest import ROOT, run_tool


@pytest.fixture
def workdir():
    """A scratch directory on the same drive as the repo (Windows relpath)."""
    path = ROOT / "reports" / f"ui-tabs-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _feature_dir(workdir: Path) -> Path:
    features = workdir / "features"
    features.mkdir()
    (features / "login.feature").write_text(
        textwrap.dedent(
            """\
            Feature: User Login

              @id:FC-001
              Scenario: Successful login
                Given the user is on the login page
                When they enter valid credentials
                Then they reach the dashboard
            """
        ),
        encoding="utf-8",
    )
    return features


def _unit_xml(workdir: Path) -> Path:
    path = workdir / "unit.xml"
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuites>\n'
        '  <testsuite name="pytest" tests="1" errors="0" failures="0" time="0.1">\n'
        '    <testcase classname="tests.unit" name="test_login_@scenario:FC-001" time="0.001"/>\n'
        "  </testsuite>\n"
        "</testsuites>\n",
        encoding="utf-8",
    )
    return path


_TABS = {
    "dashboard": ("/", "Dashboard"),
    "pyramid": ("/pyramid", "Test Pyramid"),
    "failures": ("/failures", "Failure Breakdown"),
    "unlinked": ("/unlinked", "Unlinked Tests"),
}


def _nav(route, label):
    return f'data-route="{route}" href="#{route}">{label}</a>'


@pytest.mark.parametrize("tag", ["@scenario:FC-011"])
def test_default_config_shows_only_feature_breakdown_in_server_html(tag, workdir):
    result = run_tool(
        _feature_dir(workdir), workdir / "report.html", unit=_unit_xml(workdir),
        render_mode="server", ui={"tabs": {}},
    )

    assert result.returncode == 0, result.stdout
    html = (workdir / "report.html").read_text(encoding="utf-8")
    assert _nav("/features", "Feature Breakdown") in html
    for route, label in _TABS.values():
        assert _nav(route, label) not in html
    assert 'const DEFAULT_ROUTE = "/features";' in html


@pytest.mark.parametrize("tag", ["@scenario:FC-011"])
def test_default_config_embeds_no_enabled_tabs_in_client_html(tag, workdir):
    result = run_tool(
        _feature_dir(workdir), workdir / "report.html", unit=_unit_xml(workdir),
        render_mode="client", ui={"tabs": {}},
    )

    assert result.returncode == 0, result.stdout
    html = (workdir / "report.html").read_text(encoding="utf-8")
    assert "const SHOW_DASHBOARD = UI_TABS.dashboard === true;" in html
    assert '"tabs": {}' in html


@pytest.mark.parametrize("name", list(_TABS))
@pytest.mark.parametrize("tag", ["@scenario:FC-011"])
def test_enabling_a_tab_shows_its_nav_link_in_server_html(tag, name, workdir):
    result = run_tool(
        _feature_dir(workdir), workdir / "report.html", unit=_unit_xml(workdir),
        render_mode="server", ui={"tabs": {name: True}},
    )

    assert result.returncode == 0, result.stdout
    html = (workdir / "report.html").read_text(encoding="utf-8")
    for other, (route, label) in _TABS.items():
        assert (_nav(route, label) in html) == (other == name)


@pytest.mark.parametrize("render_mode", ["server", "client"])
def test_metadata_is_rendered_separately_from_cli_and_config(render_mode, workdir):
    import json
    import subprocess
    import sys

    config = {
        "features": [str(_feature_dir(workdir))],
        "output": str(workdir / "report.html"),
        "output_json": str(workdir / "report.json"),
        "render_mode": render_mode,
        "metadata": {"build": "1", "env": "<ci>"},
    }
    config_path = workdir / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "build_pyramid.py", str(config_path), "--meta", "build=77", "--meta", "run=2026-10-16"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads((workdir / "report.json").read_text(encoding="utf-8"))
    assert report["metadata"] == {"build": "77", "env": "<ci>", "run": "2026-10-16"}
    html = (workdir / "report.html").read_text(encoding="utf-8")
    assert 'id="run-metadata"' in html
    if render_mode == "server":
        assert "<strong>build</strong>77" in html
        assert "<strong>env</strong>&lt;ci&gt;" in html
