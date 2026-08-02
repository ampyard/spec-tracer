# AGENTS.md

## What this is

SpecTracer: a Python 3.12+ CLI (`spec_tracer.cli:main`) that collates JUnit XML (unit/integration) and Cucumber JSON (e2e) test results against Gherkin `.feature` files into a self-contained HTML report plus an optional JSON twin. All behavior is driven by a single JSON config file (`spectracer.config.json`); the only CLI argument is an optional config path. It never runs tests — it only parses their output.

## Toolchain

- Managed with **uv** (no pip/pipenv). Use `uv sync --group dev` to install runtime + dev deps.
- There is **no linter or typechecker** configured (no ruff/black/mypy in `pyproject.toml` or the lockfile). Skip any "lint/typecheck" step.

## Commands

```bash
uv sync --group dev                                   # install deps (requires Python 3.12+)
uv run pytest                                         # all unit + integration tests (testpaths=tests)
uv run pytest tests/unit/                             # pure unit tests only
uv run pytest tests/integration/test_fail_on.py       # a single test file
uv run behave features/                               # the repo's own BDD suite (behave)
uv run python build_pyramid.py                        # run the CLI on this repo's dogfood config
uv run python run_local.py                            # reproduce CI end-to-end, see below
uv build                                              # build wheel into dist/
```

There is no test runner other than pytest/behave; no `make`, `nox`, or task-runner config.

## The `run_local.py` / CI pipeline

`.github/workflows/ci.yml` is the source of truth; `run_local.py` mirrors it exactly: run unit pytest, per-module unit pytest (one test file → one JUnit XML under `reports/`), integration pytest (same per-module split), then behave per feature/tag combo into `reports/*.json`, then `build_pyramid.py`. If you need the generated report or any `reports/*.xml`/`*.json` to exist, run `uv run python run_local.py` first.

Gotchas:
- `reports/` is **gitignored** — all test-result files that `spectracer.config.json` points at are generated artifacts. Running `build_pyramid.py` against a clean checkout without first running the pipeline will find no results.
- This repo's `spectracer.config.json` sets `error_on_failure: true` and `fail_on: ["pyramid", "e2e_runtime"]`, so `build_pyramid.py` **exits non-zero** when health checks go red. `run_local.py` returns that exit code too. A non-zero exit is not necessarily a code failure.
- CI validates the JSON output against `spectracer-report.schema.json` (Draft 7) with `jsonschema`. That schema is the authoritative contract for `output_json` — change it in lockstep with `spec_tracer/report_model.py` and the tests.

## Test layout (important)

- `tests/unit/` — pure unit tests, no subprocess. Import `spec_tracer.*` directly.
- `tests/integration/` — drive the real CLI by shelling out to `python build_pyramid.py` with a temp config. All of them use `run_tool(...)` from `tests/integration/conftest.py` (that's why they `from conftest import ROOT, run_tool`). They write scratch configs/files under `reports/` and expect `build_pyramid.py` to exist at repo root.
- `tests/fixtures/<case>/` — checked-in feature files and result files (`features/`, `unit.xml`, `integration.xml`, `e2e.json`) that both integration tests and the behave suite read. **Do not rename fixture dirs** — `features/steps/coverage_steps.py` hardcodes a tag→fixture-dir map (`TAG_FIXTURES`).
- `features/` + `features/steps/coverage_steps.py` — behave BDD suite. It is both the tool's end-to-end test suite **and** sample Gherkin input for the dogfood report (`spectracer.config.json` reads `./features`). Scenario ids like `FC-001`, `FC-EDGE-006` must stay in sync between `features/*.feature`, `TAG_FIXTURES`, and the config's module map.

## Linking & tagging model

This is the core logic and easy to get subtly wrong:
- `@id:FC-42` on a **scenario** declares identity. `@scenario:FC-42` on a **test result** links to it. Matching is **exact string equality** on the value only — no `not`/`and`/`or`, no partials, no tag expressions.
- `@require-unit[:module]`, `@require-integration[:module]`, `@require-e2e[:module]` declare required coverage layers. Module-scoped results only satisfy same-module requirements; key `""` in config means unscoped. Presence-based: a failed-but-present result still satisfies the requirement.
- Feature-level tags are **not** inherited by scenarios. Scenario Outline parses as a single scenario; Examples rows aren't expanded.

## Module boundaries

- `cli.py` — entrypoint; config loading/validation; wires the pipeline.
- `collectors.py` — file discovery (`.feature`/`.xml`/`.json`).
- `parsers.py` — Feature/JUnit/Cucumber parsing.
- `linker.py` — the `@id`/`@scenario` tag matching (`_scenario_ids`, `_result_scenario_tags`).
- `aggregator.py` — views, completion stats, layer stats, health checks, unlinked results. Health check keys are `Progress` (note the capital P), `pyramid`, `end_to_end_runtime`, `unlinked`; `cli.py` maps config aliases (`progress`/`e2e_runtime`) via `FAIL_ON_ALIASES`.
- `models.py` — `Scenario`, `TestResult`, `ScenarioView`, requirement/completion helpers.
- `renderers.py` — HTML output (by far the largest file, ~58K).
- `report_model.py` — JSON report builder (mirrors `spectracer-report.schema.json`).

## Style conventions

- Comments reference issues/PRs as `#9`, `#module-scope` style tags — keep this style in new code.
- Dataclasses, `List`/`Dict` from `typing`, static methods on classes (not module functions).
- Release flow (`.github/workflows/release.yml`) bumps the version via `sed` in `pyproject.toml` and the version badge in `docs/index.html` — don't hand-edit the version string inconsistently.
