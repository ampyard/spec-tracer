from pathlib import Path

import pytest

from conftest import run_tool

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "module_scope"
FEATURES = FIXTURES / "features"


@pytest.mark.parametrize("tag", ["@scenario:FC-007"])
def test_e2e_module_match_marks_requirement_ok(tag, tmp_path):
    output = tmp_path / "report.html"
    result = run_tool(
        FEATURES,
        output,
        e2e={"parsers": [FIXTURES / "parsers_e2e.json"]},
    )
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "required-chip ok" in content
    assert "e2e" in content


@pytest.mark.parametrize("tag", ["@scenario:FC-007"])
def test_e2e_module_mismatch_marks_requirement_unconfigured(tag, tmp_path):
    """The required module ("parsers") is never registered as a config key here — only
    "other" is — so this is the #8 "unconfigured" case (likely typo), not a generic
    "missing" (configured-but-empty) requirement."""
    output = tmp_path / "report.html"
    result = run_tool(
        FEATURES,
        output,
        e2e={"other": [FIXTURES / "other_e2e.json"]},
    )
    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "required-chip unconfigured" in content
    assert "required-chip missing" not in content
