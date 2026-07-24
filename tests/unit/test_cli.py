import json
from pathlib import Path

import pytest

from spec_tracer.cli import (
    FAIL_ON_ALIASES,
    _failing_gated_checks,
    _load_config,
)


def _write_config(tmp_path: Path, **extra) -> Path:
    config = {"features": ["./features"], "output": "./report.html"}
    config.update(extra)
    path = tmp_path / "spectracer.config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_fail_on_aliases_map_to_internal_health_check_keys(tag):
    assert FAIL_ON_ALIASES == {
        "progress": "Progress",
        "pyramid": "pyramid",
        "e2e_runtime": "end_to_end_runtime",
    }


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_load_config_accepts_known_fail_on_names(tag, tmp_path):
    path = _write_config(tmp_path, fail_on=["pyramid", "e2e_runtime"])
    config = _load_config(path)
    assert config["fail_on"] == ["pyramid", "e2e_runtime"]


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_load_config_rejects_unlinked_as_fail_on_name(tag, tmp_path):
    path = _write_config(tmp_path, fail_on=["unlinked"])
    with pytest.raises(ValueError, match="unknown health checks"):
        _load_config(path)


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_load_config_defaults_fail_on_to_absent(tag, tmp_path):
    path = _write_config(tmp_path)
    config = _load_config(path)
    assert "fail_on" not in config


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_load_config_rejects_unknown_fail_on_name(tag, tmp_path):
    path = _write_config(tmp_path, fail_on=["pyramid", "flakiness"])
    with pytest.raises(ValueError, match="unknown health checks"):
        _load_config(path)


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_load_config_rejects_non_list_fail_on(tag, tmp_path):
    path = _write_config(tmp_path, fail_on="pyramid")
    with pytest.raises(ValueError, match="must be a list"):
        _load_config(path)


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_load_config_rejects_non_string_fail_on_entry(tag, tmp_path):
    path = _write_config(tmp_path, fail_on=[{"name": "pyramid"}])
    with pytest.raises(ValueError, match="must be strings"):
        _load_config(path)


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_load_config_rejects_duplicate_fail_on_entries(tag, tmp_path):
    path = _write_config(tmp_path, fail_on=["pyramid", "pyramid"])
    with pytest.raises(ValueError, match="duplicate entries"):
        _load_config(path)


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_load_config_rejects_case_mismatched_fail_on_name(tag, tmp_path):
    path = _write_config(tmp_path, fail_on=["Pyramid"])
    with pytest.raises(ValueError, match="unknown health checks"):
        _load_config(path)


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_failing_gated_checks_flags_failing_listed_check(tag):
    health_checks = {
        "pyramid": {"status": "fail"},
        "end_to_end_runtime": {"status": "pass"},
    }
    assert _failing_gated_checks(health_checks, ["pyramid", "e2e_runtime"]) == ["pyramid"]


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_failing_gated_checks_ignores_warn_status(tag):
    health_checks = {"progress": {"status": "warn"}}
    assert _failing_gated_checks(health_checks, ["progress"]) == []


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_failing_gated_checks_ignores_unlisted_failures(tag):
    health_checks = {
        "Progress": {"status": "fail"},
        "pyramid": {"status": "pass"},
    }
    assert _failing_gated_checks(health_checks, ["pyramid"]) == []


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_failing_gated_checks_resolves_alias_to_internal_key(tag):
    health_checks = {"end_to_end_runtime": {"status": "fail"}}
    assert _failing_gated_checks(health_checks, ["e2e_runtime"]) == ["e2e_runtime"]


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_failing_gated_checks_empty_when_nothing_listed(tag):
    health_checks = {"pyramid": {"status": "fail"}}
    assert _failing_gated_checks(health_checks, []) == []


@pytest.mark.parametrize("tag", ["@FC-011"])
def test_failing_gated_checks_flags_multiple_failing_listed_checks(tag):
    health_checks = {
        "pyramid": {"status": "fail"},
        "end_to_end_runtime": {"status": "fail"},
        "Progress": {"status": "pass"},
    }
    assert _failing_gated_checks(health_checks, ["pyramid", "e2e_runtime", "progress"]) == [
        "pyramid",
        "e2e_runtime",
    ]
