# Product Requirements Document (PRD)
## Project Name: Unified Test Tracer

### 1. Overview
The **Unified Test Tracer** is a CLI-based tool that takes **Gherkin feature files** as the single source of truth for what scenarios need testing, then collates test results from **Unit, Integration, and E2E** test suites into a single HTML report.

Feature files define the scope. Tags on scenarios link to test results across layers. The report shows:
- What percentage of scenarios have test coverage (the headline "progress" metric).
- Where coverage exists across layers (per-scenario pass/fail/skip breakdown).
- The global test pyramid (test count, duration, pass rate per layer).
- Detailed failure stack traces in one place.

The tool is tech-stack agnostic. It relies on Gherkin for scenario definition and JUnit XML / Cucumber JSON for results.

### 2. Problem Statement
- **Fragmented Visibility:** Unit, Integration, and E2E tests live in different repos or directories. CI pipelines run them separately, so no single view exists for overall test health or feature coverage.
- **Inverted Pyramids:** Teams unknowingly accumulate too many slow E2E tests and not enough Unit tests, leading to slow, flaky CI pipelines.
- **No Progress Signal:** Teams cannot easily answer "what percentage of our scenarios actually have test coverage?" — a metric that should be discussable in daily standups.
- **Lack of Traceability:** It is difficult to know if a specific business scenario is tested across all necessary layers.
- **Tooling Lock-in:** Existing reporting tools are often tied to specific frameworks (Allure for Java, Cypress Dashboard for Cypress). We need a solution that works for any tech stack.

### 3. Goals & Non-Goals

**Goals:**
- Accept Gherkin `.feature` files as the definitive list of scenarios that require coverage.
- Parse JUnit XML results from Unit and Integration test suites.
- Parse Cucumber JSON results from the E2E test suite.
- Link test results to scenarios via shared tags (exact match, OR logic — any matching tag links).
- Show a prominent **Scenario Coverage Progress** (% tested vs. untested) as the headline metric.
- Visualize the global Test Pyramid (E2E counts scenarios, other layers count individual testcases).
- Display per-scenario, per-layer pass/fail/skip breakdowns with full Gherkin text.
- Flag missing layers per scenario via `@require:*` tags.
- Feature a configurable health-check summary (inverted pyramid detection, E2E speed check).
- Require zero heavy infrastructure — just a CLI run in CI producing a self-contained static HTML file.

**Non-Goals:**
- **v1 does not need historical trending:** This is a point-in-time snapshot for the current CI run (v2 candidate).
- **Not a test runner:** The tool does not execute tests; it only parses results after tests have run.
- **Not a source-code parser:** The tool does not read `.java`, `.py`, or `.js` files.
- **No tag expressions:** Tag matching is exact string match only — no Boolean expressions (`not`, `and`, `or`).

### 4. Target Audience
- **QA Engineers / SDETs:** To validate feature coverage and identify missing layers of testing.
- **Developers:** To quickly view pass/fail statuses and failure stack traces across all layers in one place.
- **Engineering Managers / Tech Leads:** To assess the % tested progress, pyramid health, and distribution of effort.

### 5. Technical Architecture & Inputs

**Tech Stack for the Tool:**
- **Language:** Python.
- **Templating:** Jinja2 for HTML generation.
- **Dependencies:** Minimal (standard library + Jinja2 + a Gherkin parser).

**Input Formats:**
- **Feature files:** Standard Gherkin `.feature` files. Each scenario declares its own tags (feature-level tags are NOT inherited by scenarios).
- **Test results (unit / integration):** JUnit XML. The tool reads `<testcase>` elements and their tags. Tag location depends on the framework output (name attribute, classname attribute, or `<properties>` block — the tool supports multiple locations).
- **Test results (E2E):** Cucumber JSON only. Preserves native scenario->steps->tags structure.

**CLI Interface:**
```bash
python build_pyramid.py \
  --features ./features \
  --unit ./reports/unit.xml \
  --integration ./reports/int.xml \
  --e2e ./reports/e2e.json \
  --output ./report.html \
  --config .tracer-config.json \
  --error-on-failure
```

| Flag | Required | Description |
|---|---|---|
| `--features` | Yes | Path to Gherkin `.feature` file(s). Accepts a directory (recursive) or individual files. |
| `--unit` | No | Unit test JUnit XML file(s). Repeatable. E.g., `--unit ./backend/unit.xml --unit ./frontend/unit.xml`. |
| `--integration` | No | Integration test JUnit XML file(s). Repeatable. E.g., `--integration ./backend/int.xml --integration ./frontend/int.xml`. |
| `--e2e` | No | E2E test results. Directory or individual file(s). Cucumber JSON format. |
| `--output` | Yes | Path for the generated HTML report. |
| `--config` | No | JSON configuration file. CLI flags override config values. |
| `--error-on-failure` | No | If set, exit non-zero when any test result is a failure. Default: exit 0. |

### 6. The Tag-Based Linking System

Feature files and test results connect via **shared tags**.

**In feature files:**
```gherkin
Feature: User Login

  @FC-42 @regression @require:unit @require:integration @require:e2e
  Scenario: Successful login with valid credentials
    Given the user is on the login page
    When they enter valid credentials
    Then they should be redirected to the dashboard

  @FC-43
  Scenario: Login with invalid password shows error
    Given the user is on the login page
    When they enter an invalid password
    Then an error message should be displayed
```

**Two kinds of tags on a scenario:**
- **Linking tags** (`@FC-42`, `@regression`): Shared with test results. A test result carrying this tag links to the scenario.
- **Layer requirement tags** (`@require:unit`, `@require:integration`, `@require:e2e`): Tell the tool which layers are expected to have coverage for this scenario. These are NOT used for linking — test results never carry them. After processing, the tool checks each declared required layer and flags any that have zero linked results.

**In JUnit XML:**
A unit test with `@FC-42` in its name/properties links to the "Successful login" scenario. An E2E test with `@FC-42` also links.

**Matching rules:**
- **Exact string match** — `@FC-42` matches `@FC-42`, not `@FC-4` or `@FC-42-smoke`.
- **OR logic** — if a scenario has tags `[@FC-42, @regression]` and a test has only `@regression`, they still link.
- **Scenario tags only** — tags on the `Feature:` line are NOT inherited by scenarios.
- **`@require:*` tags** are excluded from linking logic — no collision possible.
- **Tag collision across features** — if two `.feature` files have a scenario tagged `@FC-42`, a test with that tag links to BOTH.
- **Tag collision within a feature** — if two scenarios share a tag (e.g., both `@smoke`), a test with `@smoke` links to BOTH.

### 7. Feature Requirements (The Report)

The HTML report is a self-contained single file (all CSS/JS inlined). It consists of five sections:

#### Section A: Coverage Progress Summary (Headline Metric)
The very first thing visible in the report — designed for daily standup discussion.

- **Overall progress bar** showing `Tested: X / Y scenarios (Z%)`
  - A scenario counts as **"tested"** if at least one test result (across any layer) links to it.
  - A scenario counts as **"untested"** if zero test results link to it.
- **Per-feature breakdown:** Each feature listed with its own mini progress bar.
- **Color coding:** Green if >80%, amber 50–80%, red <50% (configurable thresholds).

#### Section B: Global Pyramid Dashboard
A visual 3-tiered pyramid (E2E on top, Integration in middle, Unit on bottom).

- **Metrics per layer:**
  - Total test count (E2E layer counts scenarios, not individual step testcases; other layers count individual JUnit testcases).
  - Total execution time.
  - Pass / Fail / Skip percentage.
- **Health indicators:**
  - **Speed Check:** Flags RED if E2E takes more than a configurable % of total execution time.
  - **Ratio Check:** Flags RED if Unit test count < Integration + E2E count combined (inverted pyramid).
- **Insight:** Instantly shows if the pyramid is inverted or if the E2E layer dominates runtime.

#### Section C: Feature Traceability & Scenario Matrix
A searchable tree table:

```
Feature: User Login
  [=== 75% coverage ===] (2 of 3 scenarios tested)

  ├─ Scenario: Successful login (tested)
  │   Required: unit ✓  integration ✓  e2e ✓
  │   Layer     │ Tests │ Pass │ Fail │ Skip │ Duration
  │  ───────────────────────────────────────────────────
  │  Unit       │   3   │  3   │   0  │   0  │  0.4s
  │  Integration│   1   │  1   │   0  │   0  │  2.1s
  │  E2E        │   2   │  2   │   0  │   0  │ 12.3s
  │
  ├─ Scenario: Invalid password (no coverage)  [red highlight]
  │   Required: none
  │   (No test results found for @FC-43)
  │
  └─ Scenario: Lockout after 3 attempts (partial)
      Required: unit ✓  e2e ✗
      Layer     │ Tests │ Pass │ Fail │ Skip │ Duration
       Unit     │   1   │  1   │   0  │   0  │  0.1s
```

- Each scenario shows the full Gherkin Given/When/Then text.
- Each scenario row shows declared layer requirements and their status (✓ covered, ✗ missing).
- Each scenario row shows a per-layer accordion with pass/fail/skip counts and total duration.
- Expand a layer pill to see individual test names, statuses, and expand failure stack traces.
- **Tag filter:** A text input at the top of the matrix. Type a tag name and the matrix filters to show only matching scenarios. Client-side JavaScript — no page reload.

#### Section D: Detailed Failure Breakdown
An accordion-style table listing every failed test across all layers.

- Columns: Layer | Feature | Scenario | Test Name | Status | Duration.
- Clicking a failed test expands to show the full `<failure>` or `<error>` stack trace from the JUnit XML.

#### Section E: Unlinked Tests
A section at the bottom listing every test result whose tags did not match any scenario.

- Shows: Layer | Test Name | Tags Found | Status.
- Helps teams identify orphaned or mis-tagged tests.

### 8. Quality Standards & Health Checks

A "Health Check" banner at the top of the report shows:

| Check | Condition | Result |
|---|---|---|
| Coverage Progress | % of scenarios with >=1 linked test | Pass / Warn / Fail (configurable thresholds) |
| Pyramid Ratio | Unit count >= Integration + E2E count | Pass / Fail |
| E2E Speed | E2E duration <= X% of total duration | Pass / Fail (X configurable, default 50%) |

Health checks are **visual indicators only** — they do not affect the exit code. Exit code is controlled solely by `--error-on-failure`.

### 9. Configuration File

JSON format (`.tracer-config.json`):

```json
{
  "exit_on_failure": false,
  "health_checks": {
    "coverage_threshold_green": 80,
    "coverage_threshold_amber": 50,
    "e2e_speed_threshold_pct": 50
  }
}
```

CLI flags override config file values when both are present.

### 10. Edge Cases & Behavior

| Scenario | Behavior |
|---|---|
| No `--features` provided | Error out. Feature files are mandatory. |
| Empty / missing test result directory | Silently ignored (zero tests for that layer). |
| Malformed JUnit XML | Abort on first error with a clear message. |
| Malformed Cucumber JSON | Abort on first error with a clear message. |
| Malformed `.feature` file | Whatever the E2E framework would do (typically parse error). |
| Test matches no scenario | Placed in "Unlinked Tests" section. |
| Scenario matches no test | Shown as "untested" in the matrix. |
| Scenario has `@require:*` but no matching test | Required layer flagged as missing in the matrix. |
| Tag collision across feature files | Test result is duplicated under both features. |
| Tag collision within a feature file | Test result is duplicated under both scenarios. |
| Feature-level tags (`@Feature:`) | NOT inherited by scenarios. Only scenario-level tags match. |
| Scenario Outline / Examples | Defer to whatever the E2E framework outputs. |
| Gherkin `Rule:` blocks | Defer to whatever the E2E framework does. |
| Gherkin `Background:` | Defer to whatever the E2E framework does. |
| Gherkin dialects (non-English) | Defer to what the E2E framework supports. |
| Unicode / special characters in names | Preserved with HTML escaping. |
| Output directory does not exist | Create it. |
| Output file already exists | Overwrite. |

### 11. Future Enhancements (Phase 2)
- **Historical Trending:** Store results in a lightweight SQLite DB to show charts of "Coverage % over Time", "Test Count over Time", and "Execution Duration over Time."
- **CI/CD Integrations:** Publish the HTML report directly as a GitHub Action artifact or GitLab Merge Request widget.
- **Gating:** Use health check thresholds to block PRs from merging.

### 12. Testing Strategy (Outside-In Dogfooding)

The tool tests itself using its own input formats and a true outside-in TDD approach.

**Three testing layers:**

| Layer | Framework | Output Format | Feeds Tool As |
|---|---|---|---|
| E2E tests | behave (`--format json`) | Cucumber JSON | `--e2e` |
| Unit tests | pytest | JUnit XML | `--unit` |
| Integration tests | pytest | JUnit XML | `--integration` |

**Principle:** Every feature starts with a `.feature` file defining the scenarios, followed by a behave scenario that asserts the desired behavior (red). Implementation makes it pass (green). Then lower-layer tests fill in coverage.

**Dogfooding CI pipeline:**
```bash
behave features/ --format json -o reports/e2e.json
pytest tests/unit --junitxml=reports/unit.xml
pytest tests/integration --junitxml=reports/int.xml

python build_pyramid.py \
  --features ./features \
  --unit ./reports/unit.xml \
  --integration ./reports/int.xml \
  --e2e ./reports/e2e.json \
  --output ./self-report.html \
  --error-on-failure
```

### 13. Implementation Roadmap

**Guiding rules for every phase:**
- All `.feature` files describe the **tool's own behavior** and live in `features/`. Never use fake placeholder features (e.g. "User Login").
- Every phase **must include a behave E2E scenario** in `features/` that validates the phase's deliverable by running the tool CLI and asserting on its output/exit code. This is not optional.
- Phase-specific fixture data (pre-canned `.xml` / `.json` inputs) lives in `tests/fixtures/<phase>/`. These are used by both behave steps and pytest integration tests.
- "Dogfooding" means the tool consumes **its own test outputs**: `pytest --junitxml=` and `behave --format json -o`. Until dogfooding starts, behave still runs to validate the tool, but the tool does not process its own `reports/` output.

#### Phase 1: Thinnest Vertical Slice (E2E Only)
- Write one `.feature` file in `features/` with one scenario tagged `@FC-001` describing the tool's core behavior.
- Write **behave step definitions** that: run the tool with `--features` + `--e2e` + `--output` -> verify HTML contains scenario name and "1/1 tested".
- Implement the minimum: CLI skeleton, feature file parser, Cucumber JSON parser, tag matcher, bare-bones Jinja2 template.
- No dogfooding yet (tool does not process its own behave output — use fixture `e2e.json`).

#### Phase 2: Add Unit Layer
- Add `--unit` flag + JUnit XML parser.
- Add a behave scenario + step definitions: feature file + unit JUnit XML (matching tag) -> report shows unit coverage.
- **First dogfooding milestone:** write a real pytest unit test tagged `@FC-001`, run it (`pytest --junitxml=`), point the tool at the output. The self-report now links a real test to a real scenario. Behave E2E output is also consumed by the tool (full `reports/` pipeline).
- Add edge-case tests: tag collision, no match, empty results, malformed XML.

#### Phase 3: Add Integration Layer
- Add `--integration` flag. Reuse the JUnit XML parser from Phase 2.
- Add a behave scenario + step definitions: feature file + integration JUnit XML (matching tag) -> report shows integration coverage.
- Dogfooding: write a real pytest integration test tagged with the phase's tag, run it, include in self-report.
- Add `--integration` to the dogfooding CI pipeline.

#### Phase 4: Layer Requirement Checks
- Implement `@require:*` tag matching against all three layers.
- Add a behave scenario: scenario tagged `@require:unit @require:e2e` but only unit has results -> report flags missing E2E.
- Add `@require:*` tags to the tool's own feature files + step assertions.
- Dogfooding: self-report shows required-layer status.

#### Phase 5: Report Polish
- Pyramid visualization, health checks (inverted pyramid, E2E speed), failure accordion, tag filter JS.
- Each feature driven by a behave scenario first (validate the HTML contains the new UI elements).
- Dogfooding: self-report includes all visual sections.

#### Phase 6: Coverage Completion
- Fill gaps in the tool's own test suite (unit, integration, E2E).
- Self-report becomes the team's quality dashboard for the tool.
- Full dogfooding CI pipeline is the single source of truth.
