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


@pytest.mark.parametrize("render_mode", ["server", "client"])
@pytest.mark.parametrize("tag", ["@scenario:FC-011"])
def test_default_config_shows_both_tabs(tag, render_mode, workdir):
    features = _feature_dir(workdir)
    unit = _unit_xml(workdir)

    result = run_tool(
        features,
        workdir / "report.html",
        unit=unit,
        render_mode=render_mode,
    )

    assert result.returncode == 0, result.stdout
    html = (workdir / "report.html").read_text(encoding="utf-8")
    assert 'data-route="/" href="#/">Dashboard</a>' in html
    assert 'data-route="/pyramid" href="#/pyramid">Test Pyramid</a>' in html


@pytest.mark.parametrize("render_mode", ["server", "client"])
@pytest.mark.parametrize("tag", ["@scenario:FC-011"])
def test_hiding_pyramid_tab_removes_nav_link_in_server_html(tag, render_mode, workdir):
    features = _feature_dir(workdir)
    unit = _unit_xml(workdir)

    result = run_tool(
        features,
        workdir / "report.html",
        unit=unit,
        render_mode=render_mode,
        ui={"tabs": {"pyramid": False}},
    )

    assert result.returncode == 0, result.stdout
    html = (workdir / "report.html").read_text(encoding="utf-8")
    assert 'data-route="/" href="#/">Dashboard</a>' in html
    if render_mode == "server":
        # Server template omits the hidden tab's nav link entirely.
        assert 'data-route="/pyramid" href="#/pyramid">Test Pyramid</a>' not in html
    else:
        # Client template hides it at runtime via JS; config is embedded for the browser to read.
        assert '"pyramid": false' in html or '"pyramid":false' in html


@pytest.mark.parametrize("render_mode", ["server", "client"])
@pytest.mark.parametrize("tag", ["@scenario:FC-011"])
def test_hiding_dashboard_tab_removes_nav_link_in_server_html(tag, render_mode, workdir):
    features = _feature_dir(workdir)
    unit = _unit_xml(workdir)

    result = run_tool(
        features,
        workdir / "report.html",
        unit=unit,
        render_mode=render_mode,
        ui={"tabs": {"dashboard": False}},
    )

    assert result.returncode == 0, result.stdout
    html = (workdir / "report.html").read_text(encoding="utf-8")
    assert 'data-route="/pyramid" href="#/pyramid">Test Pyramid</a>' in html
    if render_mode == "server":
        assert 'data-route="/" href="#/">Dashboard</a>' not in html


@pytest.mark.parametrize("render_mode", ["server", "client"])
@pytest.mark.parametrize("tag", ["@scenario:FC-011"])
def test_hiding_both_tabs_falls_back_to_feature_breakdown(tag, render_mode, workdir):
    features = _feature_dir(workdir)
    unit = _unit_xml(workdir)

    result = run_tool(
        features,
        workdir / "report.html",
        unit=unit,
        render_mode=render_mode,
        ui={"tabs": {"dashboard": False, "pyramid": False}},
    )

    assert result.returncode == 0, result.stdout
    html = (workdir / "report.html").read_text(encoding="utf-8")
    assert 'data-route="/features" href="#/features">Feature Breakdown</a>' in html
    if render_mode == "server":
        assert 'data-route="/" href="#/">Dashboard</a>' not in html
        assert 'data-route="/pyramid" href="#/pyramid">Test Pyramid</a>' not in html
        assert "const DEFAULT_ROUTE = \"/features\";" in html
