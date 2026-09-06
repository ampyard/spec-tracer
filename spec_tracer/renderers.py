import json
import re
from typing import List

try:
    from jinja2 import Environment, select_autoescape
    from markupsafe import Markup
except ImportError:
    Environment = None
    Markup = None

from spec_tracer.models import ScenarioView, TestResult, completion_fraction, completion_ratio, requirement_state, worst_outcome

LOGO_DATA_URI = ""

_REQUIRED_STATUS_TAG = {"ok": "[OK]", "missing": "[MISSING]", "unconfigured": "[UNCONFIGURED]"}
_REQUIRED_CHIP_LABEL = {"ok": "OK", "missing": "Missing", "unconfigured": "Unconfigured"}


def _layer_satisfied(req, linked_results) -> bool:
    return any(
        r.layer == req.layer and (req.module == "" or r.module.lower() == req.module.lower())
        for r in linked_results
    )


def _required_status(view: ScenarioView, known_modules=None) -> str:
    parts = []
    for req in view.scenario.required_layers:
        state = requirement_state(req, view.linked_results, known_modules)
        label = f"{req.layer}({req.module})" if req.module else req.layer
        parts.append(f"{label} {_REQUIRED_STATUS_TAG[state]}")
    return " | ".join(parts) if parts else "none"


def _required_layers(view: ScenarioView, known_modules=None) -> list:
    result = []
    for req in view.scenario.required_layers:
        state = requirement_state(req, view.linked_results, known_modules)
        result.append({"layer": req.layer, "module": req.module, "ok": state == "ok", "state": state})
    return result


def _expected_test_count(scenario) -> int:
    return len(scenario.required_layers) if scenario.required_layers else 1


def _has_missing_required_layer(view: ScenarioView) -> bool:
    return any(not _layer_satisfied(req, view.linked_results) for req in view.scenario.required_layers)


def _result_satisfies_requirement(result: TestResult, view: ScenarioView) -> bool:
    return any(
        result.layer == req.layer and (req.module == "" or result.module.lower() == req.module.lower())
        for req in view.scenario.required_layers
    )


def _completion_bar(completion: dict) -> str:
    """HTML for the proportional completion bar with an in-bar percentage.

    Color: full (100%) green · partial (1–99%) amber · empty (0%) red/grey.
    The bar itself carries a centered ``NN%`` overlay (same treatment as the
    dashboard progress bar); the ``N/M`` requirement count sits beside it for
    additional context (it reveals how many requirements are in play).
    """
    html = (
        f'<span class="completion-bar completion-{completion["cls"]}">'
        f'<span class="completion-fill" style="width: {completion["pct"]}%;"></span>'
        f'<span class="completion-overlay">{completion["pct"]}%</span>'
        f'</span>'
        f'<span class="completion-count">{completion["count"]}</span>'
    )
    return Markup(html) if Markup is not None else html


def _completion(view: ScenarioView) -> dict:
    """Presence-based completion for a scenario, used by the tree-table bar.

    The bar measures how many declared ``@require-*`` requirements are present
    (layer + module match), NOT whether results passed. A present-but-failed
    result still fills its requirement. ``ratio`` is 0..1, ``count`` is ``N/M``.
    """
    satisfied, total = completion_fraction(view)
    ratio = (satisfied / total) if total else 0.0
    if ratio >= 1.0:
        cls = "full"
    elif ratio > 0.0:
        cls = "partial"
    else:
        cls = "empty"
    return {
        "satisfied": satisfied,
        "total": total,
        "ratio": ratio,
        "pct": int(round(ratio * 100)),
        "cls": cls,
        "count": f"{satisfied}/{total}",
    }


def _outcome(view: ScenarioView) -> dict:
    """Result outcome pill for a scenario (worst-case across linked results)."""
    status = worst_outcome(view)
    cls = {"passed": "passed", "failed": "failed", "skipped": "skipped"}.get(status, "skipped")
    word = {"passed": "Passed", "failed": "Failed", "skipped": "Skipped"}.get(status, "Skipped")
    return {"word": word, "cls": cls, "status": status}


def _scenario_id(view: ScenarioView) -> str:
    """The scenario's declared ``@id:...`` tag value, if any."""
    for tag in view.scenario.tags:
        if tag.startswith("@id:"):
            return tag[len("@id:"):]
    return ""


def _scenario_status(view: ScenarioView) -> dict:
    if any(r.status == "failed" for r in view.linked_results):
        return {"word": "Failed", "cls": "failed"}
    if not view.linked_results:
        return {"word": "Incomplete", "cls": "incomplete"}
    if _has_missing_required_layer(view):
        return {"word": "Incomplete", "cls": "incomplete"}
    if any(r.status == "skipped" for r in view.linked_results):
        return {"word": "Incomplete", "cls": "incomplete"}
    return {"word": "Complete", "cls": "complete"}


def _feature_completion(feature_views: list) -> dict:
    """Feature-level rollup: average child completion (same basis as the bar)."""
    ratios = [completion_ratio(v) for v in feature_views]
    ratio = (sum(ratios) / len(ratios)) if ratios else 0.0
    satisfied = sum(completion_fraction(v)[0] for v in feature_views)
    required = sum(completion_fraction(v)[1] for v in feature_views)
    if ratio >= 1.0:
        cls = "full"
    elif ratio > 0.0:
        cls = "partial"
    else:
        cls = "empty"
    return {
        "satisfied": satisfied,
        "required": required,
        "ratio": ratio,
        "pct": int(round(ratio * 100)),
        "cls": cls,
        "count": f"{satisfied}/{required}",
    }


def _feature_outcome(feature_views: list) -> dict:
    """Feature-level rollup: worst outcome across all the feature's results."""
    all_results = [r for v in feature_views for r in v.linked_results]
    if not all_results:
        return {"word": "Skipped", "cls": "skipped", "status": "skipped"}
    rank = {"failed": 0, "skipped": 1, "passed": 2}
    status = min((r.status for r in all_results), key=lambda s: rank.get(s, 0))
    cls = {"passed": "passed", "failed": "failed", "skipped": "skipped"}.get(status, "skipped")
    word = {"passed": "Passed", "failed": "Failed", "skipped": "Skipped"}.get(status, "Skipped")
    return {"word": word, "cls": cls, "status": status}


def _feature_status(feature_views: list) -> dict:
    statuses = [_scenario_status(view)["word"] for view in feature_views]
    if "Failed" in statuses:
        return {"word": "Failed", "cls": "failed"}
    if "Incomplete" in statuses:
        return {"word": "Incomplete", "cls": "incomplete"}
    return {"word": "Complete", "cls": "complete"}


def _format_duration(value: float) -> str:
    if value >= 1.0:
        return f"{value:.1f}s"
    if value == 0:
        return "0.0s"
    return f"{value * 1000:.0f}ms"


def _status_class(status: str) -> str:
    return {"passed": "passed", "failed": "failed", "skipped": "skipped"}.get(status, "unknown")


def _status_label(status: str) -> str:
    return status.replace("passed", "Passed").replace("failed", "Failed").replace("skipped", "Skipped").title()


def _status_rank(status: str) -> int:
    return {"passed": 2, "skipped": 1, "failed": 0}.get(status, 0)


def _progress_band(pct: int) -> str:
    """Color band for a 0–100 percentage, mirroring the Progress health gate.

    ``>= 80`` green, ``>= 50`` amber, otherwise red.
    """
    if pct >= 80:
        return "good"
    if pct >= 50:
        return "warn"
    return "bad"


def _pass_band(pct: int) -> str:
    """Color band for a pass-rate percentage — same sense as :func:`_progress_band`.

    ``>= 80`` green, ``>= 50`` amber, otherwise red.``0`` (all failing) is red.
    """
    if pct >= 80:
        return "good"
    if pct >= 50:
        return "warn"
    return "bad"



_TEMPLATE_STR = """<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SpecTracer</title>
  {% if logo_data_uri %}<link rel="icon" href="{{ logo_data_uri }}">{% endif %}
  <script>
    (function () {
      try {
        var t = localStorage.getItem('st-theme');
        if (t !== 'light' && t !== 'dark') {
          t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        document.documentElement.setAttribute('data-theme', t);
      } catch (e) {}
    })();
  </script>
  <style>
    :root {
      color-scheme: light;
      --page: #f9f9f7;
      --surface: #ffffff;
      --surface-alt: #f4f6f5;
      --text: #0b0b0b;
      --text-soft: #52514e;
      --muted: #898781;
      --primary: #2a78d6;
      --primary-soft: #e4eefb;
      --unit: #2a78d6;
      --unit-soft: #e4eefb;
      --integration: #4a3aa7;
      --integration-soft: #eae6f8;
      --e2e: #1baf7a;
      --e2e-soft: #e1f6ee;
      --danger: #d03b3b;
      --danger-soft: #fbe6e6;
      --success: #0ca30c;
      --success-soft: #e4f7e4;
      --warning: #fab219;
      --warning-soft: #fef2dc;
      --border: #e1e0d9;
      --border-strong: rgba(11, 11, 11, 0.10);
      --shadow-1: 0 1px 2px rgba(11, 11, 11, 0.08), 0 1px 3px rgba(11, 11, 11, 0.08);
      --shadow-2: 0 1px 3px rgba(11, 11, 11, 0.10), 0 6px 16px rgba(11, 11, 11, 0.10);
      --radius: 16px;
      --gap: 24px;
    }

    /* cascadia-mono-latin-wght-normal */
    @font-face {
      font-family: 'Cascadia Mono Variable';
      font-style: normal;
      font-display: swap;
      font-weight: 200 700;
      src: url(https://cdn.jsdelivr.net/fontsource/fonts/cascadia-mono:vf@latest/latin-wght-normal.woff2) format('woff2-variations');
      unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;
    }
    /* System dark when user has not picked an explicit theme */
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) {
        color-scheme: dark;
        --page: #0d0d0d;
        --surface: #1a1a19;
        --surface-alt: #202020;
        --text: #ffffff;
        --text-soft: #c3c2b7;
        --muted: #898781;
        --primary: #3987e5;
        --primary-soft: rgba(57, 135, 229, 0.16);
        --unit: #3987e5;
        --unit-soft: rgba(57, 135, 229, 0.16);
        --integration: #9085e9;
        --integration-soft: rgba(144, 133, 233, 0.18);
        --e2e: #199e70;
        --e2e-soft: rgba(25, 158, 112, 0.18);
        --danger: #e66767;
        --danger-soft: rgba(230, 103, 103, 0.16);
        --success: #0ca30c;
        --success-soft: rgba(12, 163, 12, 0.16);
        --warning: #fab219;
        --warning-soft: rgba(250, 178, 25, 0.16);
        --border: #2c2c2a;
        --border-strong: rgba(255, 255, 255, 0.10);
        --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.4), 0 1px 3px rgba(0, 0, 0, 0.3);
        --shadow-2: 0 1px 3px rgba(0, 0, 0, 0.4), 0 6px 16px rgba(0, 0, 0, 0.35);
      }
    }
    /* Explicit dark override (also covers light system preference) */
    :root[data-theme="dark"] {
      color-scheme: dark;
      --page: #0d0d0d;
      --surface: #1a1a19;
      --surface-alt: #202020;
      --text: #ffffff;
      --text-soft: #c3c2b7;
      --muted: #898781;
      --primary: #3987e5;
      --primary-soft: rgba(57, 135, 229, 0.16);
      --unit: #3987e5;
      --unit-soft: rgba(57, 135, 229, 0.16);
      --integration: #9085e9;
      --integration-soft: rgba(144, 133, 233, 0.18);
      --e2e: #199e70;
      --e2e-soft: rgba(25, 158, 112, 0.18);
      --danger: #e66767;
      --danger-soft: rgba(230, 103, 103, 0.16);
      --success: #0ca30c;
      --success-soft: rgba(12, 163, 12, 0.16);
      --warning: #fab219;
      --warning-soft: rgba(250, 178, 25, 0.16);
      --border: #2c2c2a;
      --border-strong: rgba(255, 255, 255, 0.10);
      --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.4), 0 1px 3px rgba(0, 0, 0, 0.3);
      --shadow-2: 0 1px 3px rgba(0, 0, 0, 0.4), 0 6px 16px rgba(0, 0, 0, 0.35);
    }
    * { box-sizing: border-box; }
    ::selection { background: var(--primary-soft); color: var(--primary); }
    body {
      margin: 0;
      font-family: "Cascadia Mono Variable", ui-monospace;
      -webkit-font-smoothing: antialiased;
      background: var(--page);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.5;
    }
    .app-header {
      display: flex;
      align-items: center;
      gap: 14px;
      padding: 16px 32px;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 20;
    }
    .app-header .logo { height: 32px; width: auto; border-radius: 6px; }
    .app-title { font-size: 1.15rem; font-weight: 700; letter-spacing: -0.01em; color: var(--text); }
    .theme-toggle {
      margin-left: auto;
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: var(--surface-alt);
      color: var(--text-soft);
      font-size: 1.05rem;
      line-height: 1;
      cursor: pointer;
      transition: color 140ms ease, border-color 140ms ease, background 140ms ease, box-shadow 140ms ease;
    }
    .theme-toggle:hover {
      color: var(--primary);
      border-color: var(--primary);
      background: var(--primary-soft);
      box-shadow: var(--shadow-1);
    }
    .theme-toggle:focus-visible {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 3px var(--primary-soft);
    }
    .app-nav {
      display: flex;
      gap: 4px;
      padding: 0 32px;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 65px;
      z-index: 19;
      overflow-x: auto;
    }
    .app-nav a {
      display: inline-flex;
      align-items: center;
      padding: 14px 16px;
      color: var(--text-soft);
      text-decoration: none;
      font-size: 0.92rem;
      font-weight: 600;
      border-bottom: 3px solid transparent;
      white-space: nowrap;
      transition: color 140ms ease, border-color 140ms ease;
    }
    .app-nav a:hover { color: var(--primary); }
    .app-nav a.active { color: var(--primary); border-bottom-color: var(--primary); }
    .page-shell { max-width: 1800px; width: 96%; margin: 0 auto; padding: 32px 0; display: grid; gap: var(--gap); }
    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow-1);
      padding: 24px 28px;
      margin: 10px;
    }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: clamp(1.6rem, 3vw, 2.1rem); font-weight: 600; letter-spacing: -0.01em; color: var(--text); }
    h2 { font-size: 1.15rem; font-weight: 600; letter-spacing: -0.005em; }
    .hero-subtitle { margin-top: 8px; color: var(--text-soft); max-width: 54ch; line-height: 1.6; font-size: 0.95rem; }
    .hero-stats { display: flex; gap: 12px; margin-top: 24px; flex-wrap: wrap; }
    .stat-card {
      background: var(--surface-alt);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px 18px;
      min-width: 150px;
      transition: box-shadow 160ms ease;
    }
    .stat-card:hover { box-shadow: var(--shadow-1); }
    .stat-card-link { cursor: pointer; }
    .stat-card-link:hover { box-shadow: var(--shadow-1); border-color: var(--primary); }
    .stat-card-anchor { display: block; color: inherit; text-decoration: none; }
    .stat-sub { margin-top: 4px; font-size: 0.76rem; color: var(--text-soft); }
    .stat-card strong { display: block; font-size: 1.5rem; font-weight: 700; margin-bottom: 2px; color: var(--text); letter-spacing: -0.01em; font-variant-numeric: tabular-nums; }
    .stat-card span { color: var(--text-soft); font-size: 0.84rem; }
    .bar-fill { height: 100%; border-radius: inherit; background: var(--primary); transition: width 420ms ease; }
    .bar-fill.good { background: var(--success); }
    .bar-fill.warn { background: var(--warning); }
    .bar-fill.bad { background: var(--danger); }
    .stat-bar { height: 8px; border-radius: 999px; overflow: hidden; background: var(--border); margin-top: 10px; }
    .stat-bar .bar-fill { border-radius: inherit; }
    .stat-card { position: relative; }

    .section-head .muted { color: var(--text-soft); font-size: 0.87rem; margin-top: 4px; }
    .health-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
    .health-card { position: relative; border-radius: 12px; padding: 16px 18px; border: 1px solid var(--border); background: var(--surface-alt); overflow: hidden; }
    .health-card::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--muted); }
    .health-card.pass::before { background: var(--success); }
    .health-card.warn::before { background: var(--warning); }
    .health-card.fail::before { background: var(--danger); }
    .health-title { font-weight: 600; margin-bottom: 6px; font-size: 0.92rem; color: var(--text); }
    .health-message { color: var(--text-soft); font-size: 0.87rem; line-height: 1.55; margin-top: 6px; }
    .health-value { font-size: 1rem; font-weight: 700; color: var(--primary); margin-top: 4px; font-variant-numeric: tabular-nums; }
    .pyramid-mini { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
    .pyramid-mini-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; background: var(--surface); border: 1px solid var(--border); font-size: 0.78rem; color: var(--text-soft); letter-spacing: 0.02em; }
    .pyramid-mini-chip strong { color: var(--text); font-variant-numeric: tabular-nums; }
    .health-link { display: inline-block; margin-top: 10px; font-size: 0.82rem; font-weight: 600; color: var(--primary); text-decoration: none; }
    .health-link:hover { text-decoration: underline; }
    .pyramid-shell { display: flex; flex-direction: column; gap: 14px; }
    .tier {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 16px 20px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: var(--surface-alt);
    }
    .tier-bar-track { height: 8px; border-radius: 999px; overflow: hidden; background: var(--border); width: 100%; }
    .tier-bar-fill { height: 100%; border-radius: inherit; transition: width 320ms ease; }
    .tier-bar-fill.unit { background: var(--unit); }
    .tier-bar-fill.integration { background: var(--integration); }
    .tier-bar-fill.e2e { background: var(--e2e); }
    .tier-content { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
    .tier-label { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
    .tier-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; flex: 0 0 auto; }
    .tier-dot.unit { background: var(--unit); }
    .tier-dot.integration { background: var(--integration); }
    .tier-dot.e2e { background: var(--e2e); }
    .tier-label strong { font-size: 0.98rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text); }
    .tier-count { font-size: 0.86rem; color: var(--text-soft); font-variant-numeric: tabular-nums; white-space: nowrap; }
    .tier-meta { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    .tier-chip { padding: 2px 9px; border-radius: 999px; font-size: 0.76rem; font-weight: 700; background: var(--surface); border: 1px solid var(--border); color: var(--text-soft); white-space: nowrap; }
    .badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px; border-radius: 999px; font-size: 0.74rem; font-weight: 700; letter-spacing: 0.03em; text-transform: uppercase; white-space: nowrap; }
    .badge.complete { background: var(--success-soft); color: var(--success); }
    .badge.incomplete { background: var(--danger-soft); color: var(--danger); }
    .badge.partial { background: var(--warning-soft); color: var(--warning); }
    .badge.incomplete { background: var(--warning-soft); color: var(--warning); }
    .badge.passed { background: var(--success-soft); color: var(--success); }
    .badge.failed { background: var(--danger-soft); color: var(--danger); }
    .badge.skipped { background: var(--warning-soft); color: var(--warning); }
    .pill { display: inline-flex; align-items: center; padding: 4px 12px; border-radius: 999px; border: 1px solid var(--border); color: var(--text-soft); font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; margin-right: 6px; background: var(--surface-alt); }
    .scenario-id-pill { text-transform: none; letter-spacing: 0; color: var(--primary); font-family: ui-monospace, SFMono-Regular, monospace; border-radius: 6px; white-space: normal; flex: 0 1 auto; }
    .steps { margin: 8px 0 0; padding-left: 52px; color: var(--text-soft); line-height: 1.65; font-size: 0.88rem; }
    .empty-state { padding: 14px 0 14px 32px; color: var(--text-soft); font-size: 0.88rem; }
    .table-list { display: grid; gap: 0; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
    .table-row { display: grid; grid-template-columns: 100px 1fr 1.4fr 1.5fr 80px 90px; gap: 12px; align-items: start; padding: 12px 16px; background: var(--surface); border-bottom: 1px solid var(--border); font-size: 0.86rem; }
    .table-row:last-child { border-bottom: none; }
    .table-row:nth-child(even) { background: var(--surface-alt); }
    .table-row:hover { background: var(--primary-soft); }
    .table-row .layer-pill { justify-content: center; width: 100%; }
    .table-row .mono { font-size: 0.79rem; color: var(--text-soft); font-variant-numeric: tabular-nums; }
    .table-row .wrap { overflow-wrap: anywhere; }
    .hidden { display: none !important; }
    .search-bar { display: flex; align-items: center; gap: 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 11px 16px; margin-bottom: 18px; max-width: 440px; box-shadow: var(--shadow-1); transition: border-color 160ms ease, box-shadow 160ms ease; }
    .search-bar:focus-within { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft); }
    .search-bar svg { width: 18px; height: 18px; flex: 0 0 auto; color: var(--muted); }
    .search-bar input { flex: 1 1 auto; min-width: 0; background: transparent; border: none; color: var(--text); outline: none; font-size: 0.92rem; }
    .search-bar input::-webkit-search-cancel-button,
    .search-bar input::-webkit-search-decoration { -webkit-appearance: none; appearance: none; display: none; }
    .search-bar input::-ms-clear { display: none; }
    .search-clear {
      flex: 0 0 auto;
      display: none;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      border: none;
      background: var(--surface-alt);
      color: var(--text-soft);
      font-size: 0.8rem;
      line-height: 1;
      cursor: pointer;
    }
    .search-bar.has-value .search-clear { display: flex; }
    .search-clear:hover { background: var(--border); color: var(--text); }
    .tree-table { border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
    .tree-head {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 16px;
      background: var(--surface-alt);
      border-bottom: 1px solid var(--border);
    }
    .sort-btn, .tree-head-label {
      background: none;
      border: none;
      color: var(--text-soft);
      font: inherit;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      font-size: 0.72rem;
      font-weight: 700;
      padding: 0;
      display: flex;
      align-items: center;
      gap: 4px;
      text-align: left;
      min-width: 0;
    }
    .sort-btn { cursor: pointer; }
    .sort-btn:hover { color: var(--primary); }
    .sort-btn .sort-caret { font-size: 0.68rem; opacity: 0; flex: 0 0 auto; transition: opacity 120ms ease; }
    .sort-btn:hover .sort-caret { opacity: 0.35; }
    .sort-btn.sort-active .sort-caret { opacity: 1; }
    .tree-row { display: block; width: 100%; border-bottom: 1px solid var(--border); background: var(--surface); font-size: 0.87rem; }
    .tree-row:last-child { border-bottom: none; }
    .tree-row > summary, .tree-row.leaf {
      display: flex;
      align-items: center;
      gap: 12px;
      width: 100%;
      padding: 11px 16px;
      cursor: pointer;
      list-style: none;
    }
    .tree-row.leaf { cursor: default; }
    .tree-row > summary::-webkit-details-marker { display: none; }
    .tree-row:hover { background: var(--primary-soft); }
    .tree-children { padding: 10px 16px 14px 16px; background: var(--surface-alt); width: 100%; }
    .tree-row.level-1 { font-weight: 600; }
    .col-name { flex: 1 1 auto; min-width: 0; display: flex; flex-wrap: wrap; align-items: flex-start; gap: 6px 8px; }
    .col-name .name-text { min-width: 0; flex: 1 1 auto; white-space: normal; overflow-wrap: anywhere; word-break: break-word; line-height: 1.35; }
    .col-name.lvl-2 { padding-left: 24px; }
    .col-name.lvl-3 { padding-left: 48px; }
    .col-status { flex: 0 0 110px; width: 110px; min-width: 0; overflow: hidden; }
    .col-status .badge { display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: middle; }
    .col-completion { flex: 1 1 200px; min-width: 120px; display: flex; align-items: center; gap: 8px; }
    .col-result { flex: 0 0 100px; width: 100px; min-width: 0; overflow: hidden; }
    .col-result .badge { display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: middle; }
    .col-expected, .col-actual { flex: 0 0 90px; width: 90px; text-align: center; }
    .col-duration { flex: 0 0 100px; width: 100px; }
    .tree-caret {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      width: 16px;
      height: 16px;
      color: var(--muted);
      font-size: 0.8rem;
      font-weight: 700;
    }
    .tree-caret::before { content: "+"; }
    details.tree-row[open] > summary .tree-caret::before { content: "−"; }
    .col-expected, .col-actual, .col-duration {  ui-monospace, SFMono-Regular, monospace; font-size: 0.8rem; color: var(--text-soft); font-variant-numeric: tabular-nums; }
    .completion-bar { flex: 1 1 auto; min-width: 60px; height: 20px; border-radius: 999px; overflow: hidden; background: var(--border); display: block; position: relative; }
    .completion-fill { display: block; height: 100%; border-radius: inherit; transition: width 420ms ease; }
    .completion-full .completion-fill { background: var(--success); }
    .completion-partial .completion-fill { background: var(--warning); }
    .completion-empty .completion-fill { background: var(--danger); }
    .completion-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.02em; color: var(--text); font-variant-numeric: tabular-nums; pointer-events: none; text-shadow: 0 1px 2px color-mix(in srgb, var(--page) 70%, transparent); }
    /* Dark mode: the bright yellow (partial) fill makes white text illegible.
       Switch to dark text with a white halo so it stays readable on both the
       yellow fill and the dark (unfilled) track. Light mode is unchanged. */
    :root[data-theme="dark"] .completion-partial .completion-overlay,
    :root:not([data-theme="light"]) .completion-partial .completion-overlay { color: #0d0d0d; text-shadow: 0 0 3px #fff, 0 0 3px #fff; }
    .completion-count { flex: 0 0 auto; font-size: 0.76rem; font-variant-numeric: tabular-nums; color: var(--text-soft); margin-left: 8px; }
    .required-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 8px 0 4px; padding-left: 32px; }
    .required-label { color: var(--text-soft); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; }
    .required-chip { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 999px; font-size: 0.76rem; font-weight: 600; text-transform: uppercase; }
    .required-chip.ok { background: var(--success-soft); color: var(--success); }
    .required-chip.missing { background: var(--danger-soft); color: var(--danger); }
    .required-chip.unconfigured { background: var(--warning-soft); color: var(--warning); }
    .required-chip.none { background: var(--surface); color: var(--text-soft); border: 1px solid var(--border); }
    .module-tag { font-weight: 400; text-transform: none; opacity: 0.75; }
    .module-chip {
      display: inline-flex;
      align-items: center;
      flex: 0 0 auto;
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: var(--surface-alt);
      color: var(--text-soft);
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      white-space: nowrap;
    }
    .req-tag { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.02em; white-space: nowrap; }
    .req-tag.matched { background: var(--primary-soft); color: var(--primary); }
    .req-tag.extra { background: var(--surface-alt); color: var(--text-soft); border: 1px solid var(--border); }
    .failure-block { margin: 4px 16px 14px 48px; padding: 12px; border-radius: 8px; background: var(--danger-soft); border: 1px solid var(--border); white-space: pre-wrap; ui-monospace, SFMono-Regular, monospace; font-size: 0.79rem; line-height: 1.5; color: var(--danger); }
    .nav-button {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 9px 18px;
      border-radius: 999px;
      border: 1px solid var(--primary);
      background: var(--surface);
      color: var(--primary);
      font-size: 0.85rem;
      font-weight: 600;
      text-decoration: none;
      white-space: nowrap;
      transition: background 140ms ease, box-shadow 140ms ease;
    }
    .nav-button:hover { background: var(--primary-soft); box-shadow: var(--shadow-1); }
    @media (max-width: 960px) {
      .app-header, .app-nav { padding-left: 16px; padding-right: 16px; }
      .page-shell { padding: 16px; }
      .panel { padding: 20px; margin: 10px;  }
      .health-grid { grid-template-columns: 1fr; }
      .table-row { grid-template-columns: 1fr; }
      .col-status { flex-basis: 90px; width: 90px; }
      .col-expected, .col-actual { flex-basis: 60px; width: 60px; }
      .col-duration { flex-basis: 70px; width: 70px; }
    }
  </style>
</head>
<body>
  <header class="app-header">
    {% if logo_data_uri %}<img class="logo" src="{{ logo_data_uri }}" alt="Logo">{% endif %}
    <span class="app-title">SpecTracer</span>
    <button type="button" class="theme-toggle" aria-label="Toggle theme" title="Toggle light/dark theme">&#9788;</button>
  </header>
  <nav class="app-nav">
    <a class="nav-link" data-route="/" href="#/">Dashboard</a>
    <a class="nav-link" data-route="/pyramid" href="#/pyramid">Test Pyramid</a>
    <a class="nav-link" data-route="/features" href="#/features">Feature Breakdown</a>
    <a class="nav-link" data-route="/failures" href="#/failures">Failure Breakdown</a>
    <a class="nav-link" data-route="/unlinked" href="#/unlinked">Unlinked Tests</a>
  </nav>
  <div class="page-shell">

    <main id="page-dashboard" class="page-stack">
      <section class="panel">
        <h1>Overview</h1>
        <div class="hero-stats">
          <div class="stat-card" title="{{ satisfied }}/{{ required }} declared tests are matched by at least one linked test (presence only — pass/fail not considered)">
            <strong>{{ satisfied }}/{{ required }}</strong> <span>declared tests matched &middot; {{ pct }}%</span>
            <div class="stat-bar"><div class="bar-fill {{ progress_band(pct) }}" style="width: {{ pct }}%;"></div></div>
          </div>
          <div class="stat-card" title="{{ complete }}/{{ total }} scenarios have every declared test matched">
            <strong>{{ complete }}/{{ total }}</strong> <span>scenarios fully matched &middot; {{ scenario_pct }}%</span>
            <div class="stat-bar"><div class="bar-fill {{ progress_band(scenario_pct) }}" style="width: {{ scenario_pct }}%;"></div></div>
          </div>
          <div class="stat-card stat-card-link" title="{{ passed_total }} of {{ passed_denom }} linked results passed (pass/fail, distinct from declared-tests matched)">
            <a class="stat-card-anchor" href="#/failures">
              <strong>{{ passed_total }}/{{ passed_denom }}</strong> <span>tests passed &middot; {{ passed_pct }}%</span>
              <div class="stat-sub">{{ failed_total }} failed</div>
              <div class="stat-bar"><div class="bar-fill {{ pass_band(passed_pct) }}" style="width: {{ passed_pct }}%;"></div></div>
            </a>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="section-head">
          <div>
            <h2>Health Check</h2>
            <div class="muted">Priority signals that deserve a closer look</div>
          </div>
        </div>
        <div class="health-grid">
          {% for key, item in health_checks.items() %}
          <div class="health-card {{ item.status }}">
            <div class="health-title">{{ {'end_to_end_runtime': 'E2E runtime', 'Progress': 'Progress', 'pyramid': 'Test pyramid', 'unlinked': 'Unlinked', 'unconfigured_modules': 'Unconfigured modules'}.get(key, key.replace('_', ' ') | title) }}</div>
            {% if key == 'pyramid' %}
            <div class="pyramid-mini">
              {% for entry in item.layers %}
              <span class="pyramid-mini-chip">
                <span class="tier-dot {{ entry.name }}"></span>
                <strong>{{ entry.count }}</strong> {{ entry.name | upper }}
              </span>
              {% endfor %}
            </div>
            {% elif key == 'Progress' %}
            <div class="health-value">{{ item.value }} declared tests matched</div>
            {% else %}
            <div class="health-value">{{ item.value }}</div>
            {% endif %}
            <div class="health-message">{{ item.message }}</div>
            {% if key == 'pyramid' %}
            <a class="health-link" href="#/pyramid">Open test pyramid &rarr;</a>
            {% elif key == 'end_to_end_runtime' %}
            <a class="health-link" href="#/pyramid">Open test pyramid &rarr;</a>
            {% elif key == 'unlinked' %}
            <a class="health-link" href="#/unlinked">View unlinked tests &rarr;</a>
            {% endif %}
          </div>
          {% endfor %}
        </div>
      </section>
    </main>

    <main id="page-pyramid" class="page-stack hidden">
      <section class="panel">
        <div class="section-head">
          <div>
            <h2>Test Pyramid</h2>
            <div class="muted">Execution mix across unit, integration, and E2E layers</div>
          </div>
        </div>
        <div class="pyramid-shell">
          {% for layer in layer_stats %}
          <div class="tier {{ layer.name }}">
            <div class="tier-bar-track"><div class="tier-bar-fill {{ layer.name }}" style="width: {{ layer.width_pct }}%;"></div></div>
            <div class="tier-content">
              <div class="tier-label">
                <span class="tier-dot {{ layer.name }}"></span>
                <strong>{{ layer.name }}</strong>
                <span class="tier-count">{{ layer.count }} tests &middot; {{ format_duration(layer.duration) }}</span>
              </div>
              <div class="tier-meta">
                <span class="tier-chip">Pass {{ layer.pass_pct }}%</span>
                <span class="tier-chip">Fail {{ layer.fail_pct }}%</span>
                <span class="tier-chip">Skip {{ layer.skip_pct }}%</span>
              </div>
            </div>
          </div>
          {% endfor %}
        </div>
      </section>
    </main>

    <main id="page-features" class="page-stack hidden">
      <section class="panel">
        <div class="section-head">
          <div>
            <h2>Feature Breakdown</h2>
            <div class="muted">Feature &rarr; Scenario &rarr; Layer result, expand a row for detail</div>
          </div>
        </div>
        <label class="search-bar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <input type="search" class="tree-filter-input" placeholder="Search by name" />
          <button type="button" class="search-clear" aria-label="Clear search">&#10005;</button>
        </label>
        <div class="tree-table">
          <div class="tree-head" data-tree-head>
            <button type="button" class="sort-btn col-name" data-sort-key="name">Name <span class="sort-caret">&#9660;</span></button>
            <button type="button" class="sort-btn col-completion" data-sort-key="completion">Completion <span class="sort-caret">&#9660;</span></button>
            <button type="button" class="sort-btn col-result" data-sort-key="result">Result <span class="sort-caret">&#9660;</span></button>
            <div class="col-expected tree-head-label">Declared</div>
            <div class="col-actual tree-head-label">Actual</div>
            <button type="button" class="sort-btn col-duration" data-sort-key="duration">Duration <span class="sort-caret">&#9660;</span></button>
          </div>
          <div class="tree-root" data-tree-group>
            {% for feature_name, feature_views in views | sort(attribute='scenario.feature') | groupby('scenario.feature') %}
            {% set feature_views = feature_views | list %}
            {% set feature_complete = feature_views | selectattr('is_complete') | list | length %}
            {% set feature_total = feature_views | length %}
            {% set feature_pct = ((feature_complete / feature_total * 100) | round | int) if feature_total else 0 %}
            {% set feature_completion = feature_completion(feature_views) %}
            {% set feature_outcome = feature_outcome(feature_views) %}
            {% set feature_ns = namespace(total=0, expected=0, actual=0) %}
            {% for view in feature_views %}
            {% set feature_ns.expected = feature_ns.expected + expected_test_count(view.scenario) %}
            {% set feature_ns.actual = feature_ns.actual + (view.linked_results | length) %}
            {% for r in view.linked_results %}{% set feature_ns.total = feature_ns.total + r.duration %}{% endfor %}
            {% endfor %}
            {% set fstatus = feature_status(feature_views) %}
            <details class="tree-row level-1" data-sort-name="{{ feature_name }}" data-sort-completion="{{ feature_completion.pct }}" data-sort-result="{{ status_rank(feature_outcome.status) }}" data-sort-status="{{ feature_pct }}" data-sort-duration="{{ feature_ns.total }}" data-search="{{ feature_name | lower }}">
              <summary>
                <span class="col-name lvl-1"><span class="tree-caret"></span><span class="pill"><strong>Feature</strong></span><span class="name-text"><strong>{{ feature_name }}</strong></span></span>
                <span class="col-completion">{{ _completion_bar(feature_completion) }}</span>
                <span class="col-result"><span class="badge {{ feature_outcome.cls }}">{{ feature_outcome.word }}</span></span>
                <span class="col-expected">{{ feature_ns.expected }}</span>
                <span class="col-actual">{{ feature_ns.actual }}</span>
                <span class="col-duration">{{ format_duration(feature_ns.total) }}</span>
              </summary>
              <div class="tree-children" data-tree-group>
                {% for view in feature_views %}
                {% set scenario_duration = view.linked_results | sum(attribute='duration') %}
                {% set scenario_expected = expected_test_count(view.scenario) %}
                {% set scenario_actual = view.linked_results | length %}
                {% set sstatus = scenario_status(view) %}
                {% set scompletion = completion(view) %}
                {% set soutcome = outcome(view) %}
                {% set sid = scenario_id(view) %}
                <details class="tree-row level-2" data-sort-name="{{ view.scenario.name }}" data-sort-completion="{{ scompletion.pct }}" data-sort-result="{{ status_rank(soutcome.status) }}" data-sort-status="{{ 100 if view.is_complete else 0 }}" data-sort-duration="{{ scenario_duration }}" data-search="{{ (view.scenario.name ~ ' ' ~ sid) | lower }}">
                  <summary>
                    <span class="col-name lvl-2"><span class="tree-caret"></span><span class="pill"><strong>Scenario</strong></span>{% if sid %}<span class="pill scenario-id-pill" title="Scenario id">{{ sid }}</span>{% endif %}<span class="name-text">{{ view.scenario.name }}</span></span>
                    <span class="col-completion">{{ _completion_bar(scompletion) }}</span>
                    <span class="col-result"><span class="badge {{ soutcome.cls }}">{{ soutcome.word }}</span></span>
                    <span class="col-expected">{{ scenario_expected }}</span>
                    <span class="col-actual">{{ scenario_actual }}</span>
                    <span class="col-duration">{{ format_duration(scenario_duration) }}</span>
                  </summary>
                  <div class="tree-children" data-tree-group>
                    {% set req_layers = required_layers(view) %}
                    <div class="required-row">
                      <span class="required-label">Required</span>
                      {% if req_layers %}
                      {% for item in req_layers %}
                      <span class="required-chip {{ item.state }}" title="{{ 'This module is not a registered config key — check for a typo.' if item.state == 'unconfigured' else '' }}">{{ item.layer }}{% if item.module %} <span class="module-tag">({{ item.module }})</span>{% endif %} <strong>{{ {'ok': 'OK', 'missing': 'Missing', 'unconfigured': 'Unconfigured'}[item.state] }}</strong></span>
                      {% endfor %}
                      {% else %}
                      <span class="required-chip none">No required layers</span>
                      {% endif %}
                    </div>
                    {% if view.scenario.steps %}
                    <ul class="steps" type="none">
                      {% for step in view.scenario.steps %}
                      <li>{{ step }}</li>
                      {% endfor %}
                    </ul>
                    {% endif %}
                    {% if view.linked_results %}
                    {% for result in view.linked_results %}
                    {% set is_required = result_satisfies_requirement(result, view) %}
                    <div class="tree-row level-3 leaf" data-sort-name="{{ result.name }}" data-sort-status="{{ status_rank(result.status) }}" data-sort-duration="{{ result.duration }}" data-search="{{ result.name | lower }} {{ 'matched' if is_required else 'extra' }}">
                      <span class="col-name lvl-3"><span class="pill"><strong>{{ result.layer }}</strong></span><span class="name-text">{{ result.name }}</span>{% if result.module %}<span class="module-chip" title="Discovered under module &quot;{{ result.module }}&quot;">{{ result.module }}</span>{% endif %}</span>
                      <span class="col-status"><span class="badge {{ _status_class(result.status) }}">{{ _status_label(result.status) }}</span></span>
                      <span class="col-expected"><span class="req-tag {{ 'matched' if is_required else 'extra' }}">{{ 'Matched' if is_required else 'Extra' }}</span></span>
                      <span class="col-actual">&mdash;</span>
                      <span class="col-duration">{{ format_duration(result.duration) }}</span>
                    </div>
                    {% endfor %}
                    {% else %}
                    <div class="empty-state">No linked test results found for this scenario.</div>
                    {% endif %}
                  </div>
                </details>
                {% endfor %}
              </div>
            </details>
            {% endfor %}
          </div>
        </div>
      </section>
    </main>

    <main id="page-failures" class="page-stack hidden">
      <section class="panel">
        <div class="section-head">
          <div>
            <h2>Failure Breakdown</h2>
            <div class="muted">Feature &rarr; Scenario &rarr; Failed result, expand a row for the failure message</div>
          </div>
        </div>
        {% if failure_breakdown %}
        <label class="search-bar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <input type="search" class="tree-filter-input" placeholder="Search by name" />
          <button type="button" class="search-clear" aria-label="Clear search">&#10005;</button>
        </label>
        <div class="tree-table">
          <div class="tree-head" data-tree-head>
            <button type="button" class="sort-btn col-name" data-sort-key="name">Name <span class="sort-caret">&#9660;</span></button>
            <button type="button" class="sort-btn col-status" data-sort-key="status">Status <span class="sort-caret">&#9660;</span></button>
            <button type="button" class="sort-btn col-duration" data-sort-key="duration">Duration <span class="sort-caret">&#9660;</span></button>
          </div>
          <div class="tree-root" data-tree-group>
            {% for feature in failure_breakdown %}
            {% set feature_ns = namespace(total=0) %}
            {% for s in feature.scenarios %}{% for r in s.failed_results %}{% set feature_ns.total = feature_ns.total + r.duration %}{% endfor %}{% endfor %}
            <details class="tree-row level-1" data-sort-name="{{ feature.name }}" data-sort-status="{{ feature.failed_count }}" data-sort-duration="{{ feature_ns.total }}" data-search="{{ feature.name | lower }}">
              <summary>
                <span class="col-name lvl-1"><span class="tree-caret"></span><span class="pill"><strong>Feature</strong></span><span class="name-text"><strong>{{ feature.name }}</strong></span></span>
                <span class="col-status"><span class="badge failed">{{ feature.failed_count }} failing</span></span>
                <span class="col-duration">{{ format_duration(feature_ns.total) }}</span>
              </summary>
              <div class="tree-children" data-tree-group>
                {% for s in feature.scenarios %}
                {% set scenario_duration = s.failed_results | sum(attribute='duration') %}
                <details class="tree-row level-2" data-sort-name="{{ s.view.scenario.name }}" data-sort-status="{{ s.failed_results | length }}" data-sort-duration="{{ scenario_duration }}" data-search="{{ (s.view.scenario.name ~ ' ' ~ (s.view.scenario.tags | join(' '))) | lower }}">
                  <summary>
                    <span class="col-name lvl-2"><span class="tree-caret"></span><span class="pill"><strong>Scenario</strong></span><span class="name-text">{{ s.view.scenario.name }}</span></span>
                    <span class="col-status"><span class="badge failed">{{ s.failed_results | length }} failing</span></span>
                    <span class="col-duration">{{ format_duration(scenario_duration) }}</span>
                  </summary>
                  <div class="tree-children" data-tree-group>
                    {% for result in s.failed_results %}
                    <details class="tree-row level-3" data-sort-name="{{ result.name }}" data-sort-status="0" data-sort-duration="{{ result.duration }}" data-search="{{ result.name | lower }}">
                      <summary>
                        <span class="col-name lvl-3"><span class="tree-caret"></span><span class="pill"><strong>{{ result.layer }}</strong></span><span class="name-text">{{ result.name }}</span>{% if result.module %}<span class="module-chip" title="Discovered under module &quot;{{ result.module }}&quot;">{{ result.module }}</span>{% endif %}</span>
                        <span class="col-status"><span class="badge failed">{{ _status_label(result.status) }}</span></span>
                        <span class="col-duration">{{ format_duration(result.duration) }}</span>
                      </summary>
                      {% if result.failure_message %}
                      <div class="failure-block">{{ result.failure_message }}</div>
                      {% endif %}
                    </details>
                    {% endfor %}
                  </div>
                </details>
                {% endfor %}
              </div>
            </details>
            {% endfor %}
          </div>
        </div>
        {% else %}
        <div class="empty-state">No failures detected.</div>
        {% endif %}
      </section>
    </main>

    <main id="page-unlinked" class="page-stack hidden">
      <section class="panel">
        <div class="section-head">
          <div>
            <h2>Unlinked Tests</h2>
            <div class="muted">Tests whose tags did not match any scenario</div>
          </div>
        </div>
        {% if unlinked_results %}
        <div class="table-list">
          {% for result in unlinked_results %}
          <div class="table-row">
            <span class="pill layer-pill"><strong>{{ result.layer }}</strong></span>
            <span class="wrap">{{ result.name }}</span>
            <span class="wrap">{{ result.tags | join(', ') }}</span>
            <span class="mono">{{ _status_label(result.status) }}</span>
            <span class="mono">{{ format_duration(result.duration) }}</span>
          </div>
          {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">Every parsed result was linked to a scenario.</div>
        {% endif %}
      </section>
    </main>

  </div>
  <script>
    const ROUTES = ['/', '/pyramid', '/features', '/failures', '/unlinked'];
    const PAGE_BY_ROUTE = {
      '/': 'page-dashboard',
      '/pyramid': 'page-pyramid',
      '/features': 'page-features',
      '/failures': 'page-failures',
      '/unlinked': 'page-unlinked',
    };

    (function initThemeToggle() {
      const btn = document.querySelector('.theme-toggle');
      if (!btn) return;

      function currentTheme() {
        const attr = document.documentElement.getAttribute('data-theme');
        if (attr === 'light' || attr === 'dark') return attr;
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }

      function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        try { localStorage.setItem('st-theme', theme); } catch (e) {}
        // Sun when dark (click to go light), moon when light (click to go dark)
        btn.textContent = theme === 'dark' ? '\\u2600' : '\\u263E';
        btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
        btn.title = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';
      }

      applyTheme(currentTheme());
      btn.addEventListener('click', () => {
        applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
      });
    })();

    function currentRoute() {
      const path = (window.location.hash || '#/').replace(/^#/, '');
      return ROUTES.includes(path) ? path : '/';
    }

    function route(pathOverride) {
      const path = pathOverride !== undefined ? pathOverride : currentRoute();
      Object.values(PAGE_BY_ROUTE).forEach((id) => {
        document.getElementById(id).classList.add('hidden');
      });
      document.getElementById(PAGE_BY_ROUTE[path] || 'page-dashboard').classList.remove('hidden');
      document.querySelectorAll('.app-nav a').forEach((link) => {
        link.classList.toggle('active', link.getAttribute('data-route') === path);
      });
      window.scrollTo(0, 0);
    }

    window.addEventListener('hashchange', () => route());
    document.addEventListener('click', (event) => {
      const link = event.target.closest('a[href^="#/"]');
      if (!link) return;
      event.preventDefault();
      const targetPath = link.getAttribute('href').slice(1);
      window.location.hash = targetPath;
      route(targetPath);
    });
    route();

    function sortTree(wrapper, key, dir) {
      wrapper.querySelectorAll('[data-tree-group]').forEach((group) => {
        const items = Array.from(group.children).filter((el) => el.classList.contains('tree-row'));
        items.sort((a, b) => {
          const av = a.getAttribute('data-sort-' + key) || '';
          const bv = b.getAttribute('data-sort-' + key) || '';
          const an = parseFloat(av);
          const bn = parseFloat(bv);
          let cmp;
          if (!isNaN(an) && !isNaN(bn)) {
            cmp = an - bn;
          } else {
            cmp = av.localeCompare(bv);
          }
          return dir === 'desc' ? -cmp : cmp;
        });
        items.forEach((el) => group.appendChild(el));
      });
    }

    document.querySelectorAll('.tree-table').forEach((table) => {
      const wrapper = table.closest('section');
      const buttons = table.querySelectorAll('[data-sort-key]');
      buttons.forEach((btn) => {
        btn.addEventListener('click', () => {
          const key = btn.getAttribute('data-sort-key');
          const currentKey = table.getAttribute('data-sort-key');
          const currentDir = table.getAttribute('data-sort-dir') || 'asc';
          const dir = currentKey === key && currentDir === 'asc' ? 'desc' : 'asc';
          table.setAttribute('data-sort-key', key);
          table.setAttribute('data-sort-dir', dir);
          buttons.forEach((b) => b.classList.toggle('sort-active', b === btn));
          sortTree(wrapper, key, dir);
        });
      });
    });

    function filterTree(wrapper, query) {
      const q = query.trim().toLowerCase();
      wrapper.querySelectorAll('.tree-row.level-3').forEach((leaf) => {
        const text = (leaf.getAttribute('data-search') || '').toLowerCase();
        leaf.classList.toggle('hidden', !(!q || text.includes(q)));
      });
      wrapper.querySelectorAll('.tree-row.level-2').forEach((scenario) => {
        const text = (scenario.getAttribute('data-search') || '').toLowerCase();
        const selfMatch = !q || text.includes(q);
        if (selfMatch && q) {
          scenario.querySelectorAll(':scope > .tree-children > .tree-row.level-3').forEach((l) => l.classList.remove('hidden'));
        }
        const visibleChildren = scenario.querySelectorAll(':scope > .tree-children > .tree-row.level-3:not(.hidden)').length > 0;
        const show = selfMatch || visibleChildren;
        scenario.classList.toggle('hidden', !show);
        if (show && q) scenario.open = true;
      });
      wrapper.querySelectorAll('.tree-row.level-1').forEach((feature) => {
        const text = (feature.getAttribute('data-search') || '').toLowerCase();
        const selfMatch = !q || text.includes(q);
        if (selfMatch && q) {
          feature.querySelectorAll(':scope > .tree-children > .tree-row.level-2').forEach((s) => s.classList.remove('hidden'));
        }
        const visibleChildren = feature.querySelectorAll(':scope > .tree-children > .tree-row.level-2:not(.hidden)').length > 0;
        const show = selfMatch || visibleChildren;
        feature.classList.toggle('hidden', !show);
        if (show && q) feature.open = true;
      });
      if (!q) {
        wrapper.querySelectorAll('details.tree-row').forEach((d) => { d.open = false; });
      }
    }

    document.querySelectorAll('.tree-filter-input').forEach((input) => {
      const bar = input.closest('.search-bar');
      input.addEventListener('input', (event) => {
        const wrapper = event.target.closest('section');
        bar.classList.toggle('has-value', event.target.value.length > 0);
        filterTree(wrapper, event.target.value);
      });
    });

    document.querySelectorAll('.search-clear').forEach((btn) => {
      btn.addEventListener('click', () => {
        const bar = btn.closest('.search-bar');
        const input = bar.querySelector('.tree-filter-input');
        input.value = '';
        bar.classList.remove('has-value');
        filterTree(btn.closest('section'), '');
        input.focus();
      });
    });
  </script>
</body>
</html>"""


def _json_for_script(report: dict) -> str:
    """Serialize a report dict for safe inline embedding in an HTML ``<script>`` block.

    ``json.dumps`` output can legitimately contain ``</script>`` (a failure
    message with ``</script>`` inside, or any string with ``<``/``&``), which
    would terminate the data block early and break the self-contained single
    file. Escaping ``<``, ``>``, ``&`` and the JS line/paragraph separators to
    ``\\uXXXX`` keeps the payload byte-safe for ``JSON.parse`` (#36).
    """
    text = json.dumps(report, ensure_ascii=False, indent=2)
    for char, escape in (
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
        ("&", "\\u0026"),
        ("<", "\\u003c"),
        (">", "\\u003e"),
    ):
        text = text.replace(char, escape)
    return text


# The `render_mode: "client"` shell (#36): a static single-file HTML page that
# embeds the report JSON inline (`<script type="application/json">`) and builds
# the same DOM the Jinja server path produces, from that JSON, in the browser.
# Keeping the intrinsic markup (data-sort-*, data-tree-group, .tree-row,
# .tree-children) identical to the server path lets the shared theme/route/
# sort/filter JavaScript run unchanged against the client-built trees.
_TEMPLATE_CLIENT_STR = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SpecTracer</title>
  {% if logo_data_uri %}<link rel="icon" href="{{ logo_data_uri }}">{% endif %}
  <script>
    (function () {
      try {
        var t = localStorage.getItem('st-theme');
        if (t !== 'light' && t !== 'dark') {
          t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        document.documentElement.setAttribute('data-theme', t);
      } catch (e) {}
    })();
  </script>
  <style>
    :root {
      color-scheme: light;
      --page: #f9f9f7;
      --surface: #ffffff;
      --surface-alt: #f4f6f5;
      --text: #0b0b0b;
      --text-soft: #52514e;
      --muted: #898781;
      --primary: #2a78d6;
      --primary-soft: #e4eefb;
      --unit: #2a78d6;
      --unit-soft: #e4eefb;
      --integration: #4a3aa7;
      --integration-soft: #eae6f8;
      --e2e: #1baf7a;
      --e2e-soft: #e1f6ee;
      --danger: #d03b3b;
      --danger-soft: #fbe6e6;
      --success: #0ca30c;
      --success-soft: #e4f7e4;
      --warning: #fab219;
      --warning-soft: #fef2dc;
      --border: #e1e0d9;
      --border-strong: rgba(11, 11, 11, 0.10);
      --shadow-1: 0 1px 2px rgba(11, 11, 11, 0.08), 0 1px 3px rgba(11, 11, 11, 0.08);
      --shadow-2: 0 1px 3px rgba(11, 11, 11, 0.10), 0 6px 16px rgba(11, 11, 11, 0.10);
      --radius: 16px;
      --gap: 24px;
    }

    /* cascadia-mono-latin-wght-normal */
    @font-face {
      font-family: 'Cascadia Mono Variable';
      font-style: normal;
      font-display: swap;
      font-weight: 200 700;
      src: url(https://cdn.jsdelivr.net/fontsource/fonts/cascadia-mono:vf@latest/latin-wght-normal.woff2) format('woff2-variations');
      unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;
    }
    /* System dark when user has not picked an explicit theme */
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) {
        color-scheme: dark;
        --page: #0d0d0d;
        --surface: #1a1a19;
        --surface-alt: #202020;
        --text: #ffffff;
        --text-soft: #c3c2b7;
        --muted: #898781;
        --primary: #3987e5;
        --primary-soft: rgba(57, 135, 229, 0.16);
        --unit: #3987e5;
        --unit-soft: rgba(57, 135, 229, 0.16);
        --integration: #9085e9;
        --integration-soft: rgba(144, 133, 233, 0.18);
        --e2e: #199e70;
        --e2e-soft: rgba(25, 158, 112, 0.18);
        --danger: #e66767;
        --danger-soft: rgba(230, 103, 103, 0.16);
        --success: #0ca30c;
        --success-soft: rgba(12, 163, 12, 0.16);
        --warning: #fab219;
        --warning-soft: rgba(250, 178, 25, 0.16);
        --border: #2c2c2a;
        --border-strong: rgba(255, 255, 255, 0.10);
        --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.4), 0 1px 3px rgba(0, 0, 0, 0.3);
        --shadow-2: 0 1px 3px rgba(0, 0, 0, 0.4), 0 6px 16px rgba(0, 0, 0, 0.35);
      }
    }
    /* Explicit dark override (also covers light system preference) */
    :root[data-theme="dark"] {
      color-scheme: dark;
      --page: #0d0d0d;
      --surface: #1a1a19;
      --surface-alt: #202020;
      --text: #ffffff;
      --text-soft: #c3c2b7;
      --muted: #898781;
      --primary: #3987e5;
      --primary-soft: rgba(57, 135, 229, 0.16);
      --unit: #3987e5;
      --unit-soft: rgba(57, 135, 229, 0.16);
      --integration: #9085e9;
      --integration-soft: rgba(144, 133, 233, 0.18);
      --e2e: #199e70;
      --e2e-soft: rgba(25, 158, 112, 0.18);
      --danger: #e66767;
      --danger-soft: rgba(230, 103, 103, 0.16);
      --success: #0ca30c;
      --success-soft: rgba(12, 163, 12, 0.16);
      --warning: #fab219;
      --warning-soft: rgba(250, 178, 25, 0.16);
      --border: #2c2c2a;
      --border-strong: rgba(255, 255, 255, 0.10);
      --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.4), 0 1px 3px rgba(0, 0, 0, 0.3);
      --shadow-2: 0 1px 3px rgba(0, 0, 0, 0.4), 0 6px 16px rgba(0, 0, 0, 0.35);
    }
    * { box-sizing: border-box; }
    ::selection { background: var(--primary-soft); color: var(--primary); }
    body {
      margin: 0;
      font-family: "Cascadia Mono Variable", ui-monospace;
      -webkit-font-smoothing: antialiased;
      background: var(--page);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.5;
    }
    .app-header {
      display: flex;
      align-items: center;
      gap: 14px;
      padding: 16px 32px;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 20;
    }
    .app-header .logo { height: 32px; width: auto; border-radius: 6px; }
    .app-title { font-size: 1.15rem; font-weight: 700; letter-spacing: -0.01em; color: var(--text); }
    .theme-toggle {
      margin-left: auto;
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: var(--surface-alt);
      color: var(--text-soft);
      font-size: 1.05rem;
      line-height: 1;
      cursor: pointer;
      transition: color 140ms ease, border-color 140ms ease, background 140ms ease, box-shadow 140ms ease;
    }
    .theme-toggle:hover {
      color: var(--primary);
      border-color: var(--primary);
      background: var(--primary-soft);
      box-shadow: var(--shadow-1);
    }
    .theme-toggle:focus-visible {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 3px var(--primary-soft);
    }
    .app-nav {
      display: flex;
      gap: 4px;
      padding: 0 32px;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 65px;
      z-index: 19;
      overflow-x: auto;
    }
    .app-nav a {
      display: inline-flex;
      align-items: center;
      padding: 14px 16px;
      color: var(--text-soft);
      text-decoration: none;
      font-size: 0.92rem;
      font-weight: 600;
      border-bottom: 3px solid transparent;
      white-space: nowrap;
      transition: color 140ms ease, border-color 140ms ease;
    }
    .app-nav a:hover { color: var(--primary); }
    .app-nav a.active { color: var(--primary); border-bottom-color: var(--primary); }
    .page-shell { max-width: 1800px; width: 96%; margin: 0 auto; padding: 32px 0; display: grid; gap: var(--gap); }
    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow-1);
      padding: 24px 28px;
      margin: 10px;
    }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: clamp(1.6rem, 3vw, 2.1rem); font-weight: 600; letter-spacing: -0.01em; color: var(--text); }
    h2 { font-size: 1.15rem; font-weight: 600; letter-spacing: -0.005em; }
    .hero-subtitle { margin-top: 8px; color: var(--text-soft); max-width: 54ch; line-height: 1.6; font-size: 0.95rem; }
    .hero-stats { display: flex; gap: 12px; margin-top: 24px; flex-wrap: wrap; }
    .stat-card {
      background: var(--surface-alt);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px 18px;
      min-width: 150px;
      transition: box-shadow 160ms ease;
    }
    .stat-card:hover { box-shadow: var(--shadow-1); }
    .stat-card-link { cursor: pointer; }
    .stat-card-link:hover { box-shadow: var(--shadow-1); border-color: var(--primary); }
    .stat-card-anchor { display: block; color: inherit; text-decoration: none; }
    .stat-sub { margin-top: 4px; font-size: 0.76rem; color: var(--text-soft); }
    .stat-card strong { display: block; font-size: 1.5rem; font-weight: 700; margin-bottom: 2px; color: var(--text); letter-spacing: -0.01em; font-variant-numeric: tabular-nums; }
    .stat-card span { color: var(--text-soft); font-size: 0.84rem; }
    .bar-fill { height: 100%; border-radius: inherit; background: var(--primary); transition: width 420ms ease; }
    .bar-fill.good { background: var(--success); }
    .bar-fill.warn { background: var(--warning); }
    .bar-fill.bad { background: var(--danger); }
    .stat-bar { height: 8px; border-radius: 999px; overflow: hidden; background: var(--border); margin-top: 10px; }
    .stat-bar .bar-fill { border-radius: inherit; }
    .stat-card { position: relative; }

    .section-head .muted { color: var(--text-soft); font-size: 0.87rem; margin-top: 4px; }
    .health-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
    .health-card { position: relative; border-radius: 12px; padding: 16px 18px; border: 1px solid var(--border); background: var(--surface-alt); overflow: hidden; }
    .health-card::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--muted); }
    .health-card.pass::before { background: var(--success); }
    .health-card.warn::before { background: var(--warning); }
    .health-card.fail::before { background: var(--danger); }
    .health-title { font-weight: 600; margin-bottom: 6px; font-size: 0.92rem; color: var(--text); }
    .health-message { color: var(--text-soft); font-size: 0.87rem; line-height: 1.55; margin-top: 6px; }
    .health-value { font-size: 1rem; font-weight: 700; color: var(--primary); margin-top: 4px; font-variant-numeric: tabular-nums; }
    .pyramid-mini { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
    .pyramid-mini-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; background: var(--surface); border: 1px solid var(--border); font-size: 0.78rem; color: var(--text-soft); letter-spacing: 0.02em; }
    .pyramid-mini-chip strong { color: var(--text); font-variant-numeric: tabular-nums; }
    .health-link { display: inline-block; margin-top: 10px; font-size: 0.82rem; font-weight: 600; color: var(--primary); text-decoration: none; }
    .health-link:hover { text-decoration: underline; }
    .pyramid-shell { display: flex; flex-direction: column; gap: 14px; }
    .tier {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 16px 20px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: var(--surface-alt);
    }
    .tier-bar-track { height: 8px; border-radius: 999px; overflow: hidden; background: var(--border); width: 100%; }
    .tier-bar-fill { height: 100%; border-radius: inherit; transition: width 320ms ease; }
    .tier-bar-fill.unit { background: var(--unit); }
    .tier-bar-fill.integration { background: var(--integration); }
    .tier-bar-fill.e2e { background: var(--e2e); }
    .tier-content { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
    .tier-label { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
    .tier-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; flex: 0 0 auto; }
    .tier-dot.unit { background: var(--unit); }
    .tier-dot.integration { background: var(--integration); }
    .tier-dot.e2e { background: var(--e2e); }
    .tier-label strong { font-size: 0.98rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text); }
    .tier-count { font-size: 0.86rem; color: var(--text-soft); font-variant-numeric: tabular-nums; white-space: nowrap; }
    .tier-meta { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    .tier-chip { padding: 2px 9px; border-radius: 999px; font-size: 0.76rem; font-weight: 700; background: var(--surface); border: 1px solid var(--border); color: var(--text-soft); white-space: nowrap; }
    .badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px; border-radius: 999px; font-size: 0.74rem; font-weight: 700; letter-spacing: 0.03em; text-transform: uppercase; white-space: nowrap; }
    .badge.complete { background: var(--success-soft); color: var(--success); }
    .badge.incomplete { background: var(--danger-soft); color: var(--danger); }
    .badge.partial { background: var(--warning-soft); color: var(--warning); }
    .badge.passed { background: var(--success-soft); color: var(--success); }
    .badge.failed { background: var(--danger-soft); color: var(--danger); }
    .badge.skipped { background: var(--warning-soft); color: var(--warning); }
    .pill { display: inline-flex; align-items: center; padding: 4px 12px; border-radius: 999px; border: 1px solid var(--border); color: var(--text-soft); font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; margin-right: 6px; background: var(--surface-alt); }
    .scenario-id-pill { text-transform: none; letter-spacing: 0; color: var(--primary); font-family: ui-monospace, SFMono-Regular, monospace; border-radius: 6px; white-space: normal; flex: 0 1 auto; }
    .steps { margin: 8px 0 0; padding-left: 52px; color: var(--text-soft); line-height: 1.65; font-size: 0.88rem; }
    .empty-state { padding: 14px 0 14px 32px; color: var(--text-soft); font-size: 0.88rem; }
    .table-list { display: grid; gap: 0; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
    .table-row { display: grid; grid-template-columns: 100px 1fr 1.4fr 1.5fr 80px 90px; gap: 12px; align-items: start; padding: 12px 16px; background: var(--surface); border-bottom: 1px solid var(--border); font-size: 0.86rem; }
    .table-row:last-child { border-bottom: none; }
    .table-row:nth-child(even) { background: var(--surface-alt); }
    .table-row:hover { background: var(--primary-soft); }
    .table-row .layer-pill { justify-content: center; width: 100%; }
    .table-row .mono { font-size: 0.79rem; color: var(--text-soft); font-variant-numeric: tabular-nums; }
    .table-row .wrap { overflow-wrap: anywhere; }
    .hidden { display: none !important; }
    .search-bar { display: flex; align-items: center; gap: 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 11px 16px; margin-bottom: 18px; max-width: 440px; box-shadow: var(--shadow-1); transition: border-color 160ms ease, box-shadow 160ms ease; }
    .search-bar:focus-within { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft); }
    .search-bar svg { width: 18px; height: 18px; flex: 0 0 auto; color: var(--muted); }
    .search-bar input { flex: 1 1 auto; min-width: 0; background: transparent; border: none; color: var(--text); outline: none; font-size: 0.92rem; }
    .search-bar input::-webkit-search-cancel-button,
    .search-bar input::-webkit-search-decoration { -webkit-appearance: none; appearance: none; display: none; }
    .search-bar input::-ms-clear { display: none; }
    .search-clear {
      flex: 0 0 auto;
      display: none;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      border: none;
      background: var(--surface-alt);
      color: var(--text-soft);
      font-size: 0.8rem;
      line-height: 1;
      cursor: pointer;
    }
    .search-bar.has-value .search-clear { display: flex; }
    .search-clear:hover { background: var(--border); color: var(--text); }
    .tree-table { border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
    .tree-head {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 16px;
      background: var(--surface-alt);
      border-bottom: 1px solid var(--border);
    }
    .sort-btn, .tree-head-label {
      background: none;
      border: none;
      color: var(--text-soft);
      font: inherit;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      font-size: 0.72rem;
      font-weight: 700;
      padding: 0;
      display: flex;
      align-items: center;
      gap: 4px;
      text-align: left;
      min-width: 0;
    }
    .sort-btn { cursor: pointer; }
    .sort-btn:hover { color: var(--primary); }
    .sort-btn .sort-caret { font-size: 0.68rem; opacity: 0; flex: 0 0 auto; transition: opacity 120ms ease; }
    .sort-btn:hover .sort-caret { opacity: 0.35; }
    .sort-btn.sort-active .sort-caret { opacity: 1; }
    .tree-row { display: block; width: 100%; border-bottom: 1px solid var(--border); background: var(--surface); font-size: 0.87rem; }
    .tree-row:last-child { border-bottom: none; }
    .tree-row > summary, .tree-row.leaf {
      display: flex;
      align-items: center;
      gap: 12px;
      width: 100%;
      padding: 11px 16px;
      cursor: pointer;
      list-style: none;
    }
    .tree-row.leaf { cursor: default; }
    .tree-row > summary::-webkit-details-marker { display: none; }
    .tree-row:hover { background: var(--primary-soft); }
    .tree-children { padding: 10px 16px 14px 16px; background: var(--surface-alt); width: 100%; }
    .tree-row.level-1 { font-weight: 600; }
    .col-name { flex: 1 1 auto; min-width: 0; display: flex; flex-wrap: wrap; align-items: flex-start; gap: 6px 8px; }
    .col-name .name-text { min-width: 0; flex: 1 1 auto; white-space: normal; overflow-wrap: anywhere; word-break: break-word; line-height: 1.35; }
    .col-name.lvl-2 { padding-left: 24px; }
    .col-name.lvl-3 { padding-left: 48px; }
    .col-status { flex: 0 0 110px; width: 110px; min-width: 0; overflow: hidden; }
    .col-status .badge { display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: middle; }
    .col-completion { flex: 1 1 200px; min-width: 120px; display: flex; align-items: center; gap: 8px; }
    .col-result { flex: 0 0 100px; width: 100px; min-width: 0; overflow: hidden; }
    .col-result .badge { display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: middle; }
    .col-expected, .col-actual { flex: 0 0 90px; width: 90px; text-align: center; }
    .col-duration { flex: 0 0 100px; width: 100px; }
    .tree-caret {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      width: 16px;
      height: 16px;
      color: var(--muted);
      font-size: 0.8rem;
      font-weight: 700;
    }
    .tree-caret::before { content: "+"; }
    details.tree-row[open] > summary .tree-caret::before { content: "−"; }
    .col-expected, .col-actual, .col-duration {  ui-monospace, SFMono-Regular, monospace; font-size: 0.8rem; color: var(--text-soft); font-variant-numeric: tabular-nums; }
    .completion-bar { flex: 1 1 auto; min-width: 60px; height: 20px; border-radius: 999px; overflow: hidden; background: var(--border); display: block; position: relative; }
    .completion-fill { display: block; height: 100%; border-radius: inherit; transition: width 420ms ease; }
    .completion-full .completion-fill { background: var(--success); }
    .completion-partial .completion-fill { background: var(--warning); }
    .completion-empty .completion-fill { background: var(--danger); }
    .completion-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.02em; color: var(--text); font-variant-numeric: tabular-nums; pointer-events: none; text-shadow: 0 1px 2px color-mix(in srgb, var(--page) 70%, transparent); }
    /* Dark mode: the bright yellow (partial) fill makes white text illegible.
       Switch to dark text with a white halo so it stays readable on both the
       yellow fill and the dark (unfilled) track. Light mode is unchanged. */
    :root[data-theme="dark"] .completion-partial .completion-overlay,
    :root:not([data-theme="light"]) .completion-partial .completion-overlay { color: #0d0d0d; text-shadow: 0 0 3px #fff, 0 0 3px #fff; }
    .completion-count { flex: 0 0 auto; font-size: 0.76rem; font-variant-numeric: tabular-nums; color: var(--text-soft); margin-left: 8px; }
    .required-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 8px 0 4px; padding-left: 32px; }
    .required-label { color: var(--text-soft); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; }
    .required-chip { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 999px; font-size: 0.76rem; font-weight: 600; text-transform: uppercase; }
    .required-chip.ok { background: var(--success-soft); color: var(--success); }
    .required-chip.missing { background: var(--danger-soft); color: var(--danger); }
    .required-chip.unconfigured { background: var(--warning-soft); color: var(--warning); }
    .required-chip.none { background: var(--surface); color: var(--text-soft); border: 1px solid var(--border); }
    .module-tag { font-weight: 400; text-transform: none; opacity: 0.75; }
    .module-chip {
      display: inline-flex;
      align-items: center;
      flex: 0 0 auto;
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: var(--surface-alt);
      color: var(--text-soft);
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      white-space: nowrap;
    }
    .req-tag { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.02em; white-space: nowrap; }
    .req-tag.matched { background: var(--primary-soft); color: var(--primary); }
    .req-tag.extra { background: var(--surface-alt); color: var(--text-soft); border: 1px solid var(--border); }
    .failure-block { margin: 4px 16px 14px 48px; padding: 12px; border-radius: 8px; background: var(--danger-soft); border: 1px solid var(--border); white-space: pre-wrap; ui-monospace, SFMono-Regular, monospace; font-size: 0.79rem; line-height: 1.5; color: var(--danger); }
    .nav-button {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 9px 18px;
      border-radius: 999px;
      border: 1px solid var(--primary);
      background: var(--surface);
      color: var(--primary);
      font-size: 0.85rem;
      font-weight: 600;
      text-decoration: none;
      white-space: nowrap;
      transition: background 140ms ease, box-shadow 140ms ease;
    }
    .nav-button:hover { background: var(--primary-soft); box-shadow: var(--shadow-1); }
    @media (max-width: 960px) {
      .app-header, .app-nav { padding-left: 16px; padding-right: 16px; }
      .page-shell { padding: 16px; }
      .panel { padding: 20px; margin: 10px;  }
      .health-grid { grid-template-columns: 1fr; }
      .table-row { grid-template-columns: 1fr; }
      .col-status { flex-basis: 90px; width: 90px; }
      .col-expected, .col-actual { flex-basis: 60px; width: 60px; }
      .col-duration { flex-basis: 70px; width: 70px; }
    }
  </style>
</head>
<body>
  <header class="app-header">
    {% if logo_data_uri %}<img class="logo" src="{{ logo_data_uri }}" alt="Logo">{% endif %}
    <span class="app-title">SpecTracer</span>
    <button type="button" class="theme-toggle" aria-label="Toggle theme" title="Toggle light/dark theme">&#9788;</button>
  </header>
  <nav class="app-nav">
    <a class="nav-link" data-route="/" href="#/">Dashboard</a>
    <a class="nav-link" data-route="/pyramid" href="#/pyramid">Test Pyramid</a>
    <a class="nav-link" data-route="/features" href="#/features">Feature Breakdown</a>
    <a class="nav-link" data-route="/failures" href="#/failures">Failure Breakdown</a>
    <a class="nav-link" data-route="/unlinked" href="#/unlinked">Unlinked Tests</a>
  </nav>
  <div class="page-shell">

    <main id="page-dashboard" class="page-stack">
      <div id="dashboard-root"></div>
    </main>

    <main id="page-pyramid" class="page-stack hidden">
      <section class="panel">
        <div class="section-head">
          <div>
            <h2>Test Pyramid</h2>
            <div class="muted">Execution mix across unit, integration, and E2E layers</div>
          </div>
        </div>
        <div class="pyramid-shell" id="pyramid-root"></div>
      </section>
    </main>

    <main id="page-features" class="page-stack hidden">
      <section class="panel">
        <div class="section-head">
          <div>
            <h2>Feature Breakdown</h2>
            <div class="muted">Feature &rarr; Scenario &rarr; Layer result, expand a row for detail</div>
          </div>
        </div>
        <label class="search-bar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <input type="search" class="tree-filter-input" placeholder="Search by name" />
          <button type="button" class="search-clear" aria-label="Clear search">&#10005;</button>
        </label>
        <div class="tree-table">
          <div class="tree-head" data-tree-head>
            <button type="button" class="sort-btn col-name" data-sort-key="name">Name <span class="sort-caret">&#9660;</span></button>
            <button type="button" class="sort-btn col-completion" data-sort-key="completion">Completion <span class="sort-caret">&#9660;</span></button>
            <button type="button" class="sort-btn col-result" data-sort-key="result">Result <span class="sort-caret">&#9660;</span></button>
            <div class="col-expected tree-head-label">Declared</div>
            <div class="col-actual tree-head-label">Actual</div>
            <button type="button" class="sort-btn col-duration" data-sort-key="duration">Duration <span class="sort-caret">&#9660;</span></button>
          </div>
          <div class="tree-root" data-tree-group id="feature-tree-root"></div>
        </div>
      </section>
    </main>

    <main id="page-failures" class="page-stack hidden">
      <section class="panel">
        <div class="section-head">
          <div>
            <h2>Failure Breakdown</h2>
            <div class="muted">Feature &rarr; Scenario &rarr; Failed result, expand a row for the failure message</div>
          </div>
        </div>
        <div id="failures-root"></div>
      </section>
    </main>

    <main id="page-unlinked" class="page-stack hidden">
      <section class="panel">
        <div class="section-head">
          <div>
            <h2>Unlinked Tests</h2>
            <div class="muted">Tests whose tags did not match any scenario</div>
          </div>
        </div>
        <div id="unlinked-root"></div>
      </section>
    </main>

  </div>
  <script type="application/json" id="report-data">{{ json_data }}</script>
  <script>
    const REPORT = JSON.parse(document.getElementById('report-data').textContent);

    function esc(s) {
      return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
        return c === '&' ? '&amp;' : c === '<' ? '&lt;' : c === '>' ? '&gt;' : c === '"' ? '&quot;' : '&#39;';
      });
    }

    function formatDuration(ms) {
      ms = ms || 0;
      if (ms >= 1000) return (ms / 1000).toFixed(1) + 's';
      if (ms === 0) return '0.0s';
      return Math.round(ms) + 'ms';
    }

    function statusRank(s) {
      return { passed: 2, skipped: 1, failed: 0 }[s] != null ? { passed: 2, skipped: 1, failed: 0 }[s] : 0;
    }

    function statusLabel(s) {
      return { passed: 'Passed', failed: 'Failed', skipped: 'Skipped' }[s] || String(s || '');
    }

    function progressBand(pct) {
      return pct >= 80 ? 'good' : pct >= 50 ? 'warn' : 'bad';
    }

    function passBand(pct) {
      return progressBand(pct);
    }

    function completion(reqs) {
      const total = (reqs && reqs.length) || 1;
      let satisfied = 0;
      (reqs || []).forEach(function (r) { if (r.satisfied) satisfied++; });
      const ratio = satisfied / total;
      const cls = ratio >= 1 ? 'full' : ratio > 0 ? 'partial' : 'empty';
      return {
        satisfied: satisfied, total: total, ratio: ratio,
        pct: Math.round(ratio * 100), cls: cls, count: satisfied + '/' + total
      };
    }

    function outcome(results) {
      results = results || [];
      if (!results.length) return { word: 'Skipped', cls: 'skipped', status: 'skipped' };
      const rank = { failed: 0, skipped: 1, passed: 2 };
      let worst = results[0].status;
      results.forEach(function (r) {
        if ((rank[r.status] != null ? rank[r.status] : 0) < (rank[worst] != null ? rank[worst] : 0)) worst = r.status;
      });
      return { word: statusLabel(worst), cls: worst, status: worst };
    }

    function featureCompletion(scenarios) {
      let ratioSum = 0, satisf = 0, req = 0;
      scenarios.forEach(function (sc) {
        const c = completion(sc.requirements);
        ratioSum += c.ratio; satisf += c.satisfied; req += c.total;
      });
      const ratio = scenarios.length ? ratioSum / scenarios.length : 0;
      const cls = ratio >= 1 ? 'full' : ratio > 0 ? 'partial' : 'empty';
      return { satisfied: satisf, required: req, ratio: ratio, pct: Math.round(ratio * 100), cls: cls, count: satisf + '/' + req };
    }

    function featureOutcome(scenarios) {
      let results = [];
      scenarios.forEach(function (sc) { results = results.concat(sc.results || []); });
      return outcome(results);
    }

    function scenarioId(tags) {
      tags = tags || [];
      for (let i = 0; i < tags.length; i++) {
        if (tags[i].indexOf('@id:') === 0) return tags[i].slice(4);
      }
      return '';
    }

    function matchesRequirement(result, requirements) {
      requirements = requirements || [];
      const rm = (result.module || '').toLowerCase();
      return requirements.some(function (req) {
        return req.layer === result.layer && (!req.module || rm === req.module.toLowerCase());
      });
    }

    function completionBar(c) {
      return '<span class="completion-bar completion-' + c.cls + '">' +
        '<span class="completion-fill" style="width: ' + c.pct + '%;"></span>' +
        '<span class="completion-overlay">' + c.pct + '%</span>' +
        '</span>' +
        '<span class="completion-count">' + c.count + '</span>';
    }

    function healthTitle(key) {
      return {
        end_to_end_runtime: 'E2E runtime', Progress: 'Progress', pyramid: 'Test pyramid',
        unlinked: 'Unlinked', unconfigured_modules: 'Unconfigured modules'
      }[key] || String(key).replace(/_/g, ' ');
    }

    function moduleChip(module) {
      return '<span class="module-chip" title="Discovered under module &quot;' + esc(module) + '&quot;">' + esc(module) + '</span>';
    }

    function requiredRow(reqs) {
      let h = '<div class="required-row"><span class="required-label">Required</span>';
      if (reqs && reqs.length) {
        reqs.forEach(function (req) {
          const state = req.unconfigured ? 'unconfigured' : (req.satisfied ? 'ok' : 'missing');
          const word = { ok: 'OK', missing: 'Missing', unconfigured: 'Unconfigured' }[state];
          const title = state === 'unconfigured' ? 'This module is not a registered config key — check for a typo.' : '';
          h += '<span class="required-chip ' + state + '"' + (title ? ' title="' + esc(title) + '"' : '') + '>' + req.layer;
          if (req.module) h += ' <span class="module-tag">(' + esc(req.module) + ')</span>';
          h += ' <strong>' + word + '</strong></span>';
        });
      } else {
        h += '<span class="required-chip none">No required layers</span>';
      }
      h += '</div>';
      return h;
    }

    function resultLeaf(r, reqs) {
      const isRequired = matchesRequirement(r, reqs);
      let h = '<div class="tree-row level-3 leaf" data-sort-name="' + esc(r.name) + '" data-sort-status="' + statusRank(r.status) + '" data-sort-duration="' + ((r.duration || 0) / 1000) + '" data-search="' + esc((r.name + (isRequired ? ' matched' : ' extra')).toLowerCase()) + '">';
      h += '<span class="col-name lvl-3"><span class="pill"><strong>' + r.layer + '</strong></span><span class="name-text">' + esc(r.name) + '</span>' + (r.module ? moduleChip(r.module) : '') + '</span>';
      h += '<span class="col-status"><span class="badge ' + r.status + '">' + statusLabel(r.status) + '</span></span>';
      h += '<span class="col-expected"><span class="req-tag ' + (isRequired ? 'matched' : 'extra') + '">' + (isRequired ? 'Matched' : 'Extra') + '</span></span>';
      h += '<span class="col-actual">&mdash;</span>';
      h += '<span class="col-duration">' + formatDuration(r.duration) + '</span>';
      h += '</div>';
      return h;
    }

    function scenarioBlock(sc) {
      const sid = scenarioId(sc.tags);
      const c = completion(sc.requirements);
      const o = outcome(sc.results);
      let dur = 0;
      (sc.results || []).forEach(function (r) { dur += r.duration || 0; });
      const comp = (sc.results && sc.results.length) ? 100 : 0;
      const search = (sc.name + ' ' + sid).toLowerCase();
      let h = '<details class="tree-row level-2" data-sort-name="' + esc(sc.name) + '" data-sort-completion="' + c.pct + '" data-sort-result="' + statusRank(o.status) + '" data-sort-status="' + comp + '" data-sort-duration="' + (dur / 1000) + '" data-search="' + esc(search) + '">';
      h += '<summary>';
      h += '<span class="col-name lvl-2"><span class="tree-caret"></span><span class="pill"><strong>Scenario</strong></span>';
      if (sid) h += '<span class="pill scenario-id-pill" title="Scenario id">' + esc(sid) + '</span>';
      h += '<span class="name-text">' + esc(sc.name) + '</span></span>';
      h += '<span class="col-completion">' + completionBar(c) + '</span>';
      h += '<span class="col-result"><span class="badge ' + o.cls + '">' + o.word + '</span></span>';
      h += '<span class="col-expected">' + ((sc.requirements && sc.requirements.length) || 1) + '</span>';
      h += '<span class="col-actual">' + ((sc.results && sc.results.length) || 0) + '</span>';
      h += '<span class="col-duration">' + formatDuration(dur) + '</span>';
      h += '</summary>';
      h += '<div class="tree-children" data-tree-group>';
      h += requiredRow(sc.requirements);
      if (sc.steps && sc.steps.length) {
        h += '<ul class="steps" type="none">';
        sc.steps.forEach(function (s) { h += '<li>' + esc(s) + '</li>'; });
        h += '</ul>';
      }
      if (sc.results && sc.results.length) {
        sc.results.forEach(function (r) { h += resultLeaf(r, sc.requirements); });
      } else {
        h += '<div class="empty-state">No linked test results found for this scenario.</div>';
      }
      h += '</div></details>';
      return h;
    }

    function renderFeatureTree(features) {
      let out = '';
      features.slice().sort(function (a, b) { return a.name.localeCompare(b.name); }).forEach(function (f) {
        const scs = f.scenarios || [];
        const fc = featureCompletion(scs);
        const fo = featureOutcome(scs);
        let expected = 0, actual = 0, dur = 0;
        scs.forEach(function (sc) {
          expected += (sc.requirements && sc.requirements.length) || 1;
          actual += (sc.results && sc.results.length) || 0;
          (sc.results || []).forEach(function (r) { dur += r.duration || 0; });
        });
        const fpn = scs.length ? Math.round(scs.filter(function (sc) { return sc.results && sc.results.length; }).length / scs.length * 100) : 0;
        out += '<details class="tree-row level-1" data-sort-name="' + esc(f.name) + '" data-sort-completion="' + fc.pct + '" data-sort-result="' + statusRank(fo.status) + '" data-sort-status="' + fpn + '" data-sort-duration="' + (dur / 1000) + '" data-search="' + esc(f.name.toLowerCase()) + '">';
        out += '<summary>';
        out += '<span class="col-name lvl-1"><span class="tree-caret"></span><span class="pill"><strong>Feature</strong></span><span class="name-text"><strong>' + esc(f.name) + '</strong></span></span>';
        out += '<span class="col-completion">' + completionBar(fc) + '</span>';
        out += '<span class="col-result"><span class="badge ' + fo.cls + '">' + fo.word + '</span></span>';
        out += '<span class="col-expected">' + expected + '</span>';
        out += '<span class="col-actual">' + actual + '</span>';
        out += '<span class="col-duration">' + formatDuration(dur) + '</span>';
        out += '</summary>';
        out += '<div class="tree-children" data-tree-group>';
        scs.forEach(function (sc) { out += scenarioBlock(sc); });
        out += '</div></details>';
      });
      return out;
    }

    function renderFailures(features) {
      const feats = [];
      (features || []).forEach(function (f) {
        const scenarios = [];
        (f.scenarios || []).forEach(function (sc) {
          const failed = (sc.results || []).filter(function (r) { return r.status === 'failed'; });
          if (failed.length) scenarios.push({ scenario: sc, failed: failed });
        });
        if (scenarios.length) {
          let dur = 0;
          scenarios.forEach(function (s) { s.failed.forEach(function (r) { dur += r.duration || 0; }); });
          feats.push({
            name: f.name,
            scenarios: scenarios,
            failedCount: scenarios.reduce(function (n, s) { return n + s.failed.length; }, 0),
            duration: dur
          });
        }
      });
      if (!feats.length) return '<div class="empty-state">No failures detected.</div>';
      feats.sort(function (a, b) { return a.name.localeCompare(b.name); });
      let h = '<label class="search-bar">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>' +
        '<input type="search" class="tree-filter-input" placeholder="Search by name" />' +
        '<button type="button" class="search-clear" aria-label="Clear search">&#10005;</button>' +
        '</label>';
      h += '<div class="tree-table">';
      h += '<div class="tree-head" data-tree-head>';
      h += '<button type="button" class="sort-btn col-name" data-sort-key="name">Name <span class="sort-caret">&#9660;</span></button>';
      h += '<button type="button" class="sort-btn col-status" data-sort-key="status">Status <span class="sort-caret">&#9660;</span></button>';
      h += '<button type="button" class="sort-btn col-duration" data-sort-key="duration">Duration <span class="sort-caret">&#9660;</span></button>';
      h += '</div>';
      h += '<div class="tree-root" data-tree-group>';
      feats.forEach(function (ft) {
        h += '<details class="tree-row level-1" data-sort-name="' + esc(ft.name) + '" data-sort-status="' + ft.failedCount + '" data-sort-duration="' + (ft.duration / 1000) + '" data-search="' + esc(ft.name.toLowerCase()) + '">';
        h += '<summary>';
        h += '<span class="col-name lvl-1"><span class="tree-caret"></span><span class="pill"><strong>Feature</strong></span><span class="name-text"><strong>' + esc(ft.name) + '</strong></span></span>';
        h += '<span class="col-status"><span class="badge failed">' + ft.failedCount + ' failing</span></span>';
        h += '<span class="col-duration">' + formatDuration(ft.duration) + '</span>';
        h += '</summary>';
        h += '<div class="tree-children" data-tree-group>';
        ft.scenarios.forEach(function (s) {
          let sdur = 0;
          s.failed.forEach(function (r) { sdur += r.duration || 0; });
          const search = (s.scenario.name + ' ' + ((s.scenario.tags || []).join(' '))).toLowerCase();
          h += '<details class="tree-row level-2" data-sort-name="' + esc(s.scenario.name) + '" data-sort-status="' + s.failed.length + '" data-sort-duration="' + (sdur / 1000) + '" data-search="' + esc(search) + '">';
          h += '<summary>';
          h += '<span class="col-name lvl-2"><span class="tree-caret"></span><span class="pill"><strong>Scenario</strong></span><span class="name-text">' + esc(s.scenario.name) + '</span></span>';
          h += '<span class="col-status"><span class="badge failed">' + s.failed.length + ' failing</span></span>';
          h += '<span class="col-duration">' + formatDuration(sdur) + '</span>';
          h += '</summary>';
          h += '<div class="tree-children" data-tree-group>';
          s.failed.forEach(function (r) {
            h += '<details class="tree-row level-3" data-sort-name="' + esc(r.name) + '" data-sort-status="0" data-sort-duration="' + ((r.duration || 0) / 1000) + '" data-search="' + esc(r.name.toLowerCase()) + '">';
            h += '<summary>';
            h += '<span class="col-name lvl-3"><span class="tree-caret"></span><span class="pill"><strong>' + r.layer + '</strong></span><span class="name-text">' + esc(r.name) + '</span>' + (r.module ? moduleChip(r.module) : '') + '</span>';
            h += '<span class="col-status"><span class="badge failed">' + statusLabel(r.status) + '</span></span>';
            h += '<span class="col-duration">' + formatDuration(r.duration) + '</span>';
            h += '</summary>';
            if (r.failureMessage) h += '<div class="failure-block">' + esc(r.failureMessage) + '</div>';
            h += '</details>';
          });
          h += '</div></details>';
        });
        h += '</div></details>';
      });
      h += '</div></div>';
      return h;
    }

    function renderDashboard(summary) {
      const c = summary.completion;
      const scPct = c.total ? Math.round(c.tested / c.total * 100) : 0;
      let total = 0, failed = 0;
      (REPORT.features || []).forEach(function (f) {
        (f.scenarios || []).forEach(function (sc) {
          (sc.results || []).forEach(function (r) {
            total++;
            if (r.status === 'failed') failed++;
          });
        });
      });
      const passed = total - failed;
      const passedPct = total ? Math.round(passed / total * 100) : 0;

      let h = '<section class="panel"><h1>Overview</h1><div class="hero-stats">';
      h += '<div class="stat-card" title="' + c.satisfied + '/' + c.required + ' declared tests are matched by at least one linked test (presence only — pass/fail not considered)">';
      h += '<strong>' + c.satisfied + '/' + c.required + '</strong> <span>declared tests matched &middot; ' + c.pct + '%</span>';
      h += '<div class="stat-bar"><div class="bar-fill ' + progressBand(c.pct) + '" style="width: ' + c.pct + '%;"></div></div>';
      h += '</div>';
      h += '<div class="stat-card" title="' + c.tested + '/' + c.total + ' scenarios have every declared test matched">';
      h += '<strong>' + c.tested + '/' + c.total + '</strong> <span>scenarios fully matched &middot; ' + scPct + '%</span>';
      h += '<div class="stat-bar"><div class="bar-fill ' + progressBand(scPct) + '" style="width: ' + scPct + '%;"></div></div>';
      h += '</div>';
      h += '<div class="stat-card stat-card-link" title="' + passed + ' of ' + total + ' linked results passed (pass/fail, distinct from declared-tests matched)">';
      h += '<a class="stat-card-anchor" href="#/failures">';
      h += '<strong>' + passed + '/' + total + '</strong> <span>tests passed &middot; ' + passedPct + '%</span>';
      h += '<div class="stat-sub">' + failed + ' failed</div>';
      h += '<div class="stat-bar"><div class="bar-fill ' + passBand(passedPct) + '" style="width: ' + passedPct + '%;"></div></div>';
      h += '</a></div></div></section>';

      h += '<section class="panel"><div class="section-head"><div><h2>Health Check</h2><div class="muted">Priority signals that deserve a closer look</div></div></div><div class="health-grid">';
      (summary.healthChecks || []).forEach(function (item) {
        h += '<div class="health-card ' + item.status + '">';
        h += '<div class="health-title">' + esc(healthTitle(item.key)) + '</div>';
        if (item.key === 'pyramid' && item.layers) {
          h += '<div class="pyramid-mini">';
          item.layers.forEach(function (l) {
            h += '<span class="pyramid-mini-chip"><span class="tier-dot ' + l.name + '"></span><strong>' + l.count + '</strong> ' + String(l.name).toUpperCase() + '</span>';
          });
          h += '</div>';
        } else if (item.key === 'Progress') {
          h += '<div class="health-value">' + esc(item.value) + ' declared tests matched</div>';
        } else {
          h += '<div class="health-value">' + esc(item.value) + '</div>';
        }
        h += '<div class="health-message">' + esc(item.message) + '</div>';
        if (item.key === 'pyramid' || item.key === 'end_to_end_runtime') {
          h += '<a class="health-link" href="#/pyramid">Open test pyramid &rarr;</a>';
        } else if (item.key === 'unlinked') {
          h += '<a class="health-link" href="#/unlinked">View unlinked tests &rarr;</a>';
        }
        h += '</div>';
      });
      h += '</div></section>';
      return h;
    }

    function renderPyramid(layerStats) {
      let h = '';
      (layerStats || []).forEach(function (m) {
        h += '<div class="tier ' + m.name + '">';
        h += '<div class="tier-bar-track"><div class="tier-bar-fill ' + m.name + '" style="width: ' + m.widthPct + '%;"></div></div>';
        h += '<div class="tier-content"><div class="tier-label">';
        h += '<span class="tier-dot ' + m.name + '"></span><strong>' + m.name + '</strong>';
        h += '<span class="tier-count">' + m.count + ' tests &middot; ' + formatDuration(m.duration) + '</span>';
        h += '</div><div class="tier-meta">';
        h += '<span class="tier-chip">Pass ' + m.passRate + '%</span>';
        h += '<span class="tier-chip">Fail ' + m.failRate + '%</span>';
        h += '<span class="tier-chip">Skip ' + m.skipRate + '%</span>';
        h += '</div></div></div>';
      });
      return h;
    }

    function renderUnlinked(list) {
      if (!list || !list.length) return '<div class="empty-state">Every parsed result was linked to a scenario.</div>';
      let h = '<div class="table-list">';
      list.forEach(function (r) {
        h += '<div class="table-row">';
        h += '<span class="pill layer-pill"><strong>' + r.layer + '</strong></span>';
        h += '<span class="wrap">' + esc(r.name) + '</span>';
        h += '<span class="wrap">' + esc((r.tags || []).join(', ')) + '</span>';
        h += '<span class="mono">' + statusLabel(r.status) + '</span>';
        h += '<span class="mono">' + formatDuration(r.duration) + '</span>';
        h += '</div>';
      });
      h += '</div>';
      return h;
    }

    document.getElementById('dashboard-root').innerHTML = renderDashboard(REPORT.summary);
    document.getElementById('pyramid-root').innerHTML = renderPyramid(REPORT.summary.layerStats || []);
    document.getElementById('feature-tree-root').innerHTML = renderFeatureTree(REPORT.features || []);
    document.getElementById('failures-root').innerHTML = renderFailures(REPORT.features || []);
    document.getElementById('unlinked-root').innerHTML = renderUnlinked(REPORT.unlinkedTests || []);

    const ROUTES = ['/', '/pyramid', '/features', '/failures', '/unlinked'];
    const PAGE_BY_ROUTE = {
      '/': 'page-dashboard',
      '/pyramid': 'page-pyramid',
      '/features': 'page-features',
      '/failures': 'page-failures',
      '/unlinked': 'page-unlinked',
    };

    (function initThemeToggle() {
      const btn = document.querySelector('.theme-toggle');
      if (!btn) return;

      function currentTheme() {
        const attr = document.documentElement.getAttribute('data-theme');
        if (attr === 'light' || attr === 'dark') return attr;
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }

      function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        try { localStorage.setItem('st-theme', theme); } catch (e) {}
        // Sun when dark (click to go light), moon when light (click to go dark)
        btn.textContent = theme === 'dark' ? '\\u2600' : '\\u263E';
        btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
        btn.title = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';
      }

      applyTheme(currentTheme());
      btn.addEventListener('click', () => {
        applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
      });
    })();

    function currentRoute() {
      const path = (window.location.hash || '#/').replace(/^#/, '');
      return ROUTES.includes(path) ? path : '/';
    }

    function route(pathOverride) {
      const path = pathOverride !== undefined ? pathOverride : currentRoute();
      Object.values(PAGE_BY_ROUTE).forEach((id) => {
        document.getElementById(id).classList.add('hidden');
      });
      document.getElementById(PAGE_BY_ROUTE[path] || 'page-dashboard').classList.remove('hidden');
      document.querySelectorAll('.app-nav a').forEach((link) => {
        link.classList.toggle('active', link.getAttribute('data-route') === path);
      });
      window.scrollTo(0, 0);
    }

    window.addEventListener('hashchange', () => route());
    document.addEventListener('click', (event) => {
      const link = event.target.closest('a[href^="#/"]');
      if (!link) return;
      event.preventDefault();
      const targetPath = link.getAttribute('href').slice(1);
      window.location.hash = targetPath;
      route(targetPath);
    });
    route();

    function sortTree(wrapper, key, dir) {
      wrapper.querySelectorAll('[data-tree-group]').forEach((group) => {
        const items = Array.from(group.children).filter((el) => el.classList.contains('tree-row'));
        items.sort((a, b) => {
          const av = a.getAttribute('data-sort-' + key) || '';
          const bv = b.getAttribute('data-sort-' + key) || '';
          const an = parseFloat(av);
          const bn = parseFloat(bv);
          let cmp;
          if (!isNaN(an) && !isNaN(bn)) {
            cmp = an - bn;
          } else {
            cmp = av.localeCompare(bv);
          }
          return dir === 'desc' ? -cmp : cmp;
        });
        items.forEach((el) => group.appendChild(el));
      });
    }

    document.querySelectorAll('.tree-table').forEach((table) => {
      const wrapper = table.closest('section');
      const buttons = table.querySelectorAll('[data-sort-key]');
      buttons.forEach((btn) => {
        btn.addEventListener('click', () => {
          const key = btn.getAttribute('data-sort-key');
          const currentKey = table.getAttribute('data-sort-key');
          const currentDir = table.getAttribute('data-sort-dir') || 'asc';
          const dir = currentKey === key && currentDir === 'asc' ? 'desc' : 'asc';
          table.setAttribute('data-sort-key', key);
          table.setAttribute('data-sort-dir', dir);
          buttons.forEach((b) => b.classList.toggle('sort-active', b === btn));
          sortTree(wrapper, key, dir);
        });
      });
    });

    function filterTree(wrapper, query) {
      const q = query.trim().toLowerCase();
      wrapper.querySelectorAll('.tree-row.level-3').forEach((leaf) => {
        const text = (leaf.getAttribute('data-search') || '').toLowerCase();
        leaf.classList.toggle('hidden', !(!q || text.includes(q)));
      });
      wrapper.querySelectorAll('.tree-row.level-2').forEach((scenario) => {
        const text = (scenario.getAttribute('data-search') || '').toLowerCase();
        const selfMatch = !q || text.includes(q);
        if (selfMatch && q) {
          scenario.querySelectorAll(':scope > .tree-children > .tree-row.level-3').forEach((l) => l.classList.remove('hidden'));
        }
        const visibleChildren = scenario.querySelectorAll(':scope > .tree-children > .tree-row.level-3:not(.hidden)').length > 0;
        const show = selfMatch || visibleChildren;
        scenario.classList.toggle('hidden', !show);
        if (show && q) scenario.open = true;
      });
      wrapper.querySelectorAll('.tree-row.level-1').forEach((feature) => {
        const text = (feature.getAttribute('data-search') || '').toLowerCase();
        const selfMatch = !q || text.includes(q);
        if (selfMatch && q) {
          feature.querySelectorAll(':scope > .tree-children > .tree-row.level-2').forEach((s) => s.classList.remove('hidden'));
        }
        const visibleChildren = feature.querySelectorAll(':scope > .tree-children > .tree-row.level-2:not(.hidden)').length > 0;
        const show = selfMatch || visibleChildren;
        feature.classList.toggle('hidden', !show);
        if (show && q) feature.open = true;
      });
      if (!q) {
        wrapper.querySelectorAll('details.tree-row').forEach((d) => { d.open = false; });
      }
    }

    document.querySelectorAll('.tree-filter-input').forEach((input) => {
      const bar = input.closest('.search-bar');
      input.addEventListener('input', (event) => {
        const wrapper = event.target.closest('section');
        bar.classList.toggle('has-value', event.target.value.length > 0);
        filterTree(wrapper, event.target.value);
      });
    });

    document.querySelectorAll('.search-clear').forEach((btn) => {
      btn.addEventListener('click', () => {
        const bar = btn.closest('.search-bar');
        const input = bar.querySelector('.tree-filter-input');
        input.value = '';
        bar.classList.remove('has-value');
        filterTree(btn.closest('section'), '');
        input.focus();
      });
    });
  </script>
</body>
</html>"""


class HtmlRenderer:

    def render(
        self,
        views: List[ScenarioView],
        stats: dict,
        feature_breakdown: List[dict],
        layer_stats: List[dict] | None = None,
        health_checks: dict | None = None,
        failed_results: List[TestResult] | None = None,
        unlinked_results: List[TestResult] | None = None,
        failure_breakdown: List[dict] | None = None,
        logo_data_uri: str | None = None,
        known_modules: dict | None = None,
        render_mode: str = "server",
        json_report: dict | None = None,
    ) -> str:
        layer_stats = layer_stats or []
        health_checks = health_checks or {}
        failed_results = failed_results or []
        unlinked_results = unlinked_results or []
        failure_breakdown = failure_breakdown or []
        logo_data_uri = logo_data_uri if logo_data_uri is not None else LOGO_DATA_URI

        if render_mode == "client":
            if json_report is None:
                raise ValueError(
                    "render_mode 'client' requires a report dict (json_report)"
                )
            return self._render_client(json_report=json_report, logo_data_uri=logo_data_uri)

        if Environment is not None:
            env = Environment(autoescape=select_autoescape(["html", "xml"]))
            template = env.from_string(_TEMPLATE_STR)
            template.globals["_required_status"] = lambda view: _required_status(view, known_modules)
            template.globals["required_layers"] = lambda view: _required_layers(view, known_modules)
            template.globals["result_satisfies_requirement"] = _result_satisfies_requirement
            template.globals["expected_test_count"] = _expected_test_count
            template.globals["scenario_status"] = _scenario_status
            template.globals["scenario_id"] = _scenario_id
            template.globals["feature_status"] = _feature_status
            template.globals["completion"] = _completion
            template.globals["outcome"] = _outcome
            template.globals["feature_completion"] = _feature_completion
            template.globals["feature_outcome"] = _feature_outcome
            template.globals["_completion_bar"] = _completion_bar
            template.globals["format_duration"] = _format_duration
            template.globals["_status_class"] = _status_class
            template.globals["_status_label"] = _status_label
            template.globals["status_rank"] = _status_rank
            template.globals["progress_band"] = _progress_band
            template.globals["pass_band"] = _pass_band
            failed_total = sum(metric["failed"] for metric in layer_stats)
            result_total = sum(metric["count"] for metric in layer_stats)
            passed_total = result_total - failed_total
            passed_pct = int(round((passed_total / result_total * 100) if result_total else 0))
            return template.render(
                tested=stats["complete"],
                complete=stats["complete"],
                total=stats["total"],
                percentage=stats["percentage"],
                pct=stats["pct"],
                scenario_pct=int(round((stats["complete"] / stats["total"] * 100) if stats["total"] else 0)),
                satisfied=stats["satisfied"],
                required=stats["required"],
                passed_total=passed_total,
                passed_denom=result_total,
                passed_pct=passed_pct,
                failed_total=failed_total,
                feature_breakdown=feature_breakdown,
                views=views,
                layer_stats=layer_stats,
                health_checks=health_checks,
                failed_results=failed_results,
                unlinked_results=unlinked_results,
                failure_breakdown=failure_breakdown,
                logo_data_uri=logo_data_uri,
            )

        lines = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            '<head><meta charset="utf-8"><title>SpecTracer</title></head>',
            "<body>",
            "<h1>Testing Progress</h1>",
            f"<p>{stats['complete']}/{stats['total']} scenarios complete</p>",
            "<ul>",
        ]
        for view in views:
            status = "complete" if view.is_complete else "incomplete"
            lines.append(f"<li>{view.scenario.feature}: {view.scenario.name} - {status}</li>")
        lines.extend(["</ul>", "</body>", "</html>"])
        return "\n".join(lines)

    def _render_client(self, json_report: dict, logo_data_uri: str) -> str:
        """Render the browser-driven HTML page from an embedded report dict (#36).

        The matching ``render_mode: "client"`` config flips navigation to
        client-side routing; the standalone ``output_html`` file embeds the
        report JSON inline and builds its own DOM, so it never needs the Jinja
        helper functions the server template depends on.
        """
        if Environment is None:
            shell = _TEMPLATE_CLIENT_STR
            if not logo_data_uri:
                shell = re.sub(r"{% if logo_data_uri %}.*?{% endif %}", "", shell, flags=re.S)
            return (
                shell.replace("{{ json_data }}", _json_for_script(json_report))
                .replace("{{ logo_data_uri }}", logo_data_uri or "")
            )
        env = Environment(autoescape=select_autoescape(["html", "xml"]))
        template = env.from_string(_TEMPLATE_CLIENT_STR)
        return template.render(
            json_data=Markup(_json_for_script(json_report)),
            logo_data_uri=logo_data_uri,
        )
