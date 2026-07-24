import shutil
import textwrap
import uuid
from pathlib import Path

import pytest

from conftest import ROOT, run_tool


@pytest.fixture
def workdir():
    """A scratch directory on the same drive as the repo (Windows relpath)."""
    path = ROOT / "reports" / f"fail-on-{uuid.uuid4().hex}"
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

              @FC-001
              Scenario: Successful login
                Given the user is on the login page
                When they enter valid credentials
                Then they reach the dashboard
            """
        ),
        encoding="utf-8",
    )
    return features


def _unit_xml(workdir: Path, testcases: str) -> Path:
    path = workdir / "unit.xml"
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuites>\n'
        '  <testsuite name="pytest" tests="0" errors="0" failures="0" time="0.1">\n'
        f"{testcases}\n"
        "  </testsuite>\n"
        "</testsuites>\n",
        encoding="utf-8",
    )
    return path


def _linked_case() -> str:
    return '    <testcase classname="tests.unit" name="test_login_@FC-001" time="0.001"/>'


def _orphan_cases(count: int) -> str:
    return "\n".join(
        f'    <testcase classname="tests.unit" name="test_orphan{i}_@NOPE-{i}" time="0.001"/>'
        for i in range(count)
    )


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_fail_on_progress_exits_nonzero_when_check_fails(tag, workdir):
    features = _feature_dir(workdir)
    # No linked case -> 0% complete -> progress check fails (< 50% amber threshold).
    unit = _unit_xml(workdir, _orphan_cases(4))

    result = run_tool(
        features,
        workdir / "report.html",
        unit=unit,
        fail_on=["progress"],
    )

    assert result.returncode == 1, result.stdout
    assert "Health check gate failed" in result.stderr
    assert "progress" in result.stderr


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_no_fail_on_keeps_exit_zero_despite_failing_health_check(tag, workdir):
    features = _feature_dir(workdir)
    unit = _unit_xml(workdir, _linked_case() + "\n" + _orphan_cases(4))

    result = run_tool(features, workdir / "report.html", unit=unit)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_fail_on_passing_check_keeps_exit_zero(tag, workdir):
    features = _feature_dir(workdir)
    # Many unit results, no integration/e2e -> pyramid check passes.
    unit = _unit_xml(workdir, _linked_case() + "\n" + _orphan_cases(4))

    result = run_tool(
        features,
        workdir / "report.html",
        unit=unit,
        fail_on=["pyramid"],
    )

    assert result.returncode == 0, result.stderr


def _integration_xml(workdir: Path, testcases: str) -> Path:
    path = workdir / "integration.xml"
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuites>\n'
        '  <testsuite name="pytest" tests="0" errors="0" failures="0" time="0.1">\n'
        f"{testcases}\n"
        "  </testsuite>\n"
        "</testsuites>\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_fail_on_reports_all_simultaneously_failing_checks(tag, workdir):
    features = _feature_dir(workdir)
    # No unit results vs. 2 integration results -> progress stays incomplete
    # (fail) and pyramid is inverted (fail).
    integration = _integration_xml(
        workdir,
        '    <testcase classname="tests.integration" name="test_a_@FC-001" time="0.001"/>\n'
        '    <testcase classname="tests.integration" name="test_b_@FC-001" time="0.001"/>',
    )

    result = run_tool(
        features,
        workdir / "report.html",
        integration=integration,
        fail_on=["progress", "pyramid"],
    )

    assert result.returncode == 1, result.stdout
    assert "progress" in result.stderr
    assert "pyramid" in result.stderr


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_unknown_fail_on_name_is_a_config_error(tag, workdir):
    features = _feature_dir(workdir)
    unit = _unit_xml(workdir, _linked_case())

    result = run_tool(
        features,
        workdir / "report.html",
        unit=unit,
        fail_on=["not_a_real_check"],
    )

    assert result.returncode == 1
    assert "unknown health checks" in result.stderr
