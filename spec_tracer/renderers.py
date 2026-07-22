from typing import List

try:
    from jinja2 import Template
except ImportError:
    Template = None

from spec_tracer.models import ScenarioView, TestResult

LOGO_DATA_URI = ""


def _layer_satisfied(req, linked_results) -> bool:
    return any(
        r.layer == req.layer and (req.module == "" or r.module == req.module)
        for r in linked_results
    )


def _required_status(view: ScenarioView) -> str:
    parts = []
    for req in view.scenario.required_layers:
        has = _layer_satisfied(req, view.linked_results)
        label = f"{req.layer}({req.module})" if req.module else req.layer
        parts.append(f"{label} {'[OK]' if has else '[MISSING]'}")
    return " | ".join(parts) if parts else "none"


def _required_layers(view: ScenarioView) -> list:
    result = []
    for req in view.scenario.required_layers:
        has = _layer_satisfied(req, view.linked_results)
        result.append({"layer": req.layer, "module": req.module, "ok": has})
    return result


def _expected_test_count(scenario) -> int:
    return len(scenario.required_layers) if scenario.required_layers else 1


def _has_missing_required_layer(view: ScenarioView) -> bool:
    return any(not _layer_satisfied(req, view.linked_results) for req in view.scenario.required_layers)


def _scenario_status(view: ScenarioView) -> dict:
    if any(r.status == "failed" for r in view.linked_results):
        return {"word": "Failed", "cls": "failed"}
    if not view.linked_results:
        return {"word": "Incomplete", "cls": "incomplete"}
    if _has_missing_required_layer(view):
        return {"word": "Incomplete", "cls": "incomplete"}
    if any(r.status == "skipped" for r in view.linked_results):
        return {"word": "Incomplete", "cls": "incomplete"}
    return {"word": "Complete", "cls": "tested"}


def _feature_status(feature_views: list) -> dict:
    statuses = [_scenario_status(view)["word"] for view in feature_views]
    if "Failed" in statuses:
        return {"word": "Failed", "cls": "failed"}
    if "Incomplete" in statuses:
        return {"word": "Incomplete", "cls": "incomplete"}
    return {"word": "Complete", "cls": "tested"}


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


_TEMPLATE_STR = """<!DOCTYPE html>
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
    .stat-card strong { display: block; font-size: 1.5rem; font-weight: 700; margin-bottom: 2px; color: var(--text); letter-spacing: -0.01em; font-variant-numeric: tabular-nums; }
    .stat-card span { color: var(--text-soft); font-size: 0.84rem; }
    .bar-shell { height: 8px; border-radius: 999px; overflow: hidden; background: var(--border); margin-top: 18px; }
    .bar-fill { height: 100%; border-radius: inherit; background: var(--primary); transition: width 420ms ease; }
    .section-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
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
    .badge.tested { background: var(--success-soft); color: var(--success); }
    .badge.untested { background: var(--danger-soft); color: var(--danger); }
    .badge.partial { background: var(--warning-soft); color: var(--warning); }
    .badge.incomplete { background: var(--warning-soft); color: var(--warning); }
    .badge.passed { background: var(--success-soft); color: var(--success); }
    .badge.failed { background: var(--danger-soft); color: var(--danger); }
    .badge.skipped { background: var(--warning-soft); color: var(--warning); }
    .pill { display: inline-flex; align-items: center; padding: 4px 12px; border-radius: 999px; border: 1px solid var(--border); color: var(--text-soft); font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; margin-right: 6px; background: var(--surface-alt); }
    .steps { margin: 8px 0 0; padding-left: 52px; color: var(--text-soft); line-height: 1.65; font-size: 0.88rem; }
    .empty-state { padding: 14px 0 14px 32px; color: var(--text-soft); font-size: 0.88rem; }
    .table-list { display: grid; gap: 0; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
    .table-row { display: grid; grid-template-columns: 100px 1fr 1.4fr 1.5fr 80px 90px; gap: 12px; align-items: start; padding: 12px 16px; background: var(--surface); border-bottom: 1px solid var(--border); font-size: 0.86rem; }
    .table-row:last-child { border-bottom: none; }
    .table-row:nth-child(even) { background: var(--surface-alt); }
    .table-row:hover { background: var(--primary-soft); }
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
    .sort-btn {
      background: none;
      border: none;
      cursor: pointer;
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
    .sort-btn:hover { color: var(--primary); }
    .sort-btn .sort-caret { font-size: 0.68rem; opacity: 0; flex: 0 0 auto; }
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
    .col-name { flex: 1 1 auto; min-width: 0; display: flex; align-items: center; gap: 8px; }
    .col-name .name-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; flex: 1 1 auto; }
    .col-name.lvl-2 { padding-left: 24px; }
    .col-name.lvl-3 { padding-left: 48px; }
    .col-status { flex: 0 0 110px; width: 110px; min-width: 0; overflow: hidden; }
    .col-status .badge { display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: middle; }
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
    .required-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 8px 0 4px; padding-left: 32px; }
    .required-label { color: var(--text-soft); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; }
    .required-chip { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 999px; font-size: 0.76rem; font-weight: 600; text-transform: uppercase; }
    .required-chip.ok { background: var(--success-soft); color: var(--success); }
    .required-chip.missing { background: var(--danger-soft); color: var(--danger); }
    .required-chip.none { background: var(--surface); color: var(--text-soft); border: 1px solid var(--border); }
    .module-tag { font-weight: 400; text-transform: none; opacity: 0.75; }
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
        <h1>Testing Progress</h1>
        <div class="hero-stats">
          <div class="stat-card" title="{{ tested }}/{{ total }} scenarios complete">
            <strong>{{ tested }}/{{ total }}</strong>
            <span>scenarios complete</span>
          </div>
          <div class="stat-card">
            <strong>{{ percentage }}%</strong>
            <span>progress</span>
          </div>
        </div>
        <div class="bar-shell"><div class="bar-fill" style="width: {{ percentage }}%;"></div></div>
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
            <div class="health-title">{{ key.replace('_', ' ') | title }}</div>
            {% if key == 'pyramid' %}
            <div class="pyramid-mini">
              {% for entry in item.layers %}
              <span class="pyramid-mini-chip">
                <span class="tier-dot {{ entry.name }}"></span>
                <strong>{{ entry.count }}</strong> {{ entry.name | upper }}
              </span>
              {% endfor %}
            </div>
            {% else %}
            <div class="health-value">{{ item.value }}</div>
            {% endif %}
            <div class="health-message">{{ item.message }}</div>
            {% if key == 'unlinked' %}
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
            <button type="button" class="sort-btn col-status" data-sort-key="status">Status <span class="sort-caret">&#9660;</span></button>
            <div class="col-expected">Expected</div>
            <div class="col-actual">Actual</div>
            <button type="button" class="sort-btn col-duration" data-sort-key="duration">Duration <span class="sort-caret">&#9660;</span></button>
          </div>
          <div class="tree-root" data-tree-group>
            {% for feature_name, feature_views in views | sort(attribute='scenario.feature') | groupby('scenario.feature') %}
            {% set feature_views = feature_views | list %}
            {% set feature_tested = feature_views | selectattr('is_tested') | list | length %}
            {% set feature_total = feature_views | length %}
            {% set feature_pct = ((feature_tested / feature_total * 100) | round | int) if feature_total else 0 %}
            {% set feature_ns = namespace(total=0, expected=0, actual=0) %}
            {% for view in feature_views %}
            {% set feature_ns.expected = feature_ns.expected + expected_test_count(view.scenario) %}
            {% set feature_ns.actual = feature_ns.actual + (view.linked_results | length) %}
            {% for r in view.linked_results %}{% set feature_ns.total = feature_ns.total + r.duration %}{% endfor %}
            {% endfor %}
            {% set fstatus = feature_status(feature_views) %}
            <details class="tree-row level-1" data-sort-name="{{ feature_name }}" data-sort-status="{{ feature_pct }}" data-sort-duration="{{ feature_ns.total }}" data-search="{{ feature_name | lower }}">
              <summary>
                <span class="col-name lvl-1"><span class="tree-caret"></span><span class="pill"><strong>Feature</strong></span><span class="name-text"><strong>{{ feature_name }}</strong></span></span>
                <span class="col-status"><span class="badge {{ fstatus.cls }}">{{ fstatus.word }}</span></span>
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
                <details class="tree-row level-2" data-sort-name="{{ view.scenario.name }}" data-sort-status="{{ 100 if view.is_tested else 0 }}" data-sort-duration="{{ scenario_duration }}" data-search="{{ view.scenario.name | lower }}">
                  <summary>
                    <span class="col-name lvl-2"><span class="tree-caret"></span><span class="pill"><strong>Scenario</strong></span><span class="name-text">{{ view.scenario.name }}</span></span>
                    <span class="col-status"><span class="badge {{ sstatus.cls }}">{{ sstatus.word }}</span></span>
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
                      <span class="required-chip {{ 'ok' if item.ok else 'missing' }}">{{ item.layer }}{% if item.module %} <span class="module-tag">({{ item.module }})</span>{% endif %} <strong>{{ 'OK' if item.ok else 'Missing' }}</strong></span>
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
                    <div class="tree-row level-3 leaf" data-sort-name="{{ result.name }}" data-sort-status="{{ status_rank(result.status) }}" data-sort-duration="{{ result.duration }}" data-search="{{ result.name | lower }}">
                      <span class="col-name lvl-3"><span class="pill"><strong>{{ result.layer }}</strong></span><span class="name-text">{{ result.name }}</span></span>
                      <span class="col-status"><span class="badge {{ _status_class(result.status) }}">{{ _status_label(result.status) }}</span></span>
                      <span class="col-expected">&mdash;</span>
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
                        <span class="col-name lvl-3"><span class="tree-caret"></span><span class="pill"><strong>{{ result.layer }}</strong></span><span class="name-text">{{ result.name }}</span></span>
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
            <span class="pill">{{ result.layer }}</span>
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
    ) -> str:
        layer_stats = layer_stats or []
        health_checks = health_checks or {}
        failed_results = failed_results or []
        unlinked_results = unlinked_results or []
        failure_breakdown = failure_breakdown or []
        logo_data_uri = logo_data_uri if logo_data_uri is not None else LOGO_DATA_URI

        if Template is not None:
            template = Template(_TEMPLATE_STR)
            template.globals["_required_status"] = _required_status
            template.globals["required_layers"] = _required_layers
            template.globals["expected_test_count"] = _expected_test_count
            template.globals["scenario_status"] = _scenario_status
            template.globals["feature_status"] = _feature_status
            template.globals["format_duration"] = _format_duration
            template.globals["_status_class"] = _status_class
            template.globals["_status_label"] = _status_label
            template.globals["status_rank"] = _status_rank
            return template.render(
                tested=stats["tested"],
                total=stats["total"],
                percentage=stats["percentage"],
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
            f"<p>{stats['tested']}/{stats['total']} scenarios complete</p>",
            "<ul>",
        ]
        for view in views:
            status = "tested" if view.is_tested else "untested"
            lines.append(f"<li>{view.scenario.feature}: {view.scenario.name} - {status}</li>")
        lines.extend(["</ul>", "</body>", "</html>"])
        return "\n".join(lines)
