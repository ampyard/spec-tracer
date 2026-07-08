from typing import List

try:
    from jinja2 import Template
except ImportError:
    Template = None

from unified_test_tracer.models import ScenarioView, TestResult

ALL_LAYERS = ["unit", "integration", "e2e"]


def _required_status(view: ScenarioView) -> str:
    parts = []
    for layer in ALL_LAYERS:
        if layer not in view.scenario.required_layers:
            continue
        has = any(r.layer == layer for r in view.linked_results)
        parts.append(f"{layer} {'[OK]' if has else '[MISSING]'}")
    return " | ".join(parts) if parts else "none"


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


_TEMPLATE_STR = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Unified Test Tracer</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f6fb;
      --surface: #ffffff;
      --surface-alt: #f6f8fc;
      --text: #202124;
      --text-soft: #5f6368;
      --primary: #1a73e8;
      --primary-soft: #e8f0fe;
      --unit: #e8710a;
      --unit-soft: #fce8d6;
      --integration: #9334e6;
      --integration-soft: #f3e8fd;
      --e2e: #188038;
      --e2e-soft: #e6f4ea;
      --danger: #d93025;
      --danger-soft: #fce8e6;
      --success: #188038;
      --success-soft: #e6f4ea;
      --warning: #f29900;
      --warning-soft: #fef7e0;
      --border: #dadce0;
      --shadow-1: 0 1px 2px rgba(60, 64, 67, 0.15), 0 1px 3px rgba(60, 64, 67, 0.1);
      --shadow-2: 0 1px 3px rgba(60, 64, 67, 0.15), 0 4px 12px rgba(60, 64, 67, 0.12);
      --radius: 16px;
      --gap: 24px;
    }
    * { box-sizing: border-box; }
    ::selection { background: var(--primary-soft); color: var(--primary); }
    body {
      margin: 0;
      font-family: "Google Sans", "Segoe UI", Roboto, Inter, Arial, sans-serif;
      -webkit-font-smoothing: antialiased;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 32px;
      line-height: 1.5;
    }
    .page-shell { max-width: 1280px; margin: 0 auto; display: grid; gap: var(--gap); }
    .hero, .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow-1);
    }
    .hero {
      padding: 32px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .eyebrow {
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.72rem;
      color: var(--primary);
      margin-bottom: 8px;
      font-weight: 700;
    }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: clamp(1.6rem, 3vw, 2.1rem); font-weight: 500; letter-spacing: -0.01em; color: var(--text); }
    h2 { font-size: 1.15rem; font-weight: 500; letter-spacing: -0.005em; }
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
    .stat-card strong { display: block; font-size: 1.5rem; font-weight: 500; margin-bottom: 2px; color: var(--text); letter-spacing: -0.01em; }
    .stat-card span { color: var(--text-soft); font-size: 0.84rem; }
    .bar-shell { height: 6px; border-radius: 999px; overflow: hidden; background: var(--border); margin-top: 18px; }
    .bar-fill { height: 100%; border-radius: inherit; background: var(--primary); transition: width 420ms ease; }
    .panel { padding: 24px 28px; }
    .section-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
    .section-head .muted { color: var(--text-soft); font-size: 0.87rem; margin-top: 4px; }
    .health-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
    .health-card { position: relative; border-radius: 12px; padding: 16px 18px; border: 1px solid var(--border); background: var(--surface-alt); overflow: hidden; }
    .health-card::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--text-soft); }
    .health-card.pass::before { background: var(--success); }
    .health-card.warn::before { background: var(--warning); }
    .health-card.fail::before { background: var(--danger); }
    .health-title { font-weight: 500; margin-bottom: 6px; font-size: 0.92rem; color: var(--text); }
    .health-message { color: var(--text-soft); font-size: 0.87rem; line-height: 1.55; margin-top: 6px; }
    .health-value { font-size: 1rem; font-weight: 500; color: var(--primary); margin-top: 4px; }
    .pyramid-shell { display: flex; flex-direction: column; align-items: center; gap: 10px; }
    .tier {
      position: relative;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 14px 20px;
      border-radius: 10px;
      border: 1px solid transparent;
      transition: width 320ms ease;
      color: #fff;
    }
    .tier.unit { background: var(--unit); }
    .tier.integration { background: var(--integration); }
    .tier.e2e { background: var(--e2e); }
    .tier-label { display: flex; align-items: baseline; gap: 10px; }
    .tier-label strong { font-size: 0.98rem; text-transform: capitalize; letter-spacing: 0.02em; }
    .tier-count { font-size: 1.2rem; font-weight: 600; }
    .tier-meta { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    .tier-chip { padding: 2px 9px; border-radius: 999px; font-size: 0.76rem; font-weight: 600; background: rgba(255,255,255,0.22); white-space: nowrap; }
    .feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }
    .feature-card { border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; background: var(--surface-alt); transition: box-shadow 160ms ease, border-color 160ms ease; }
    .feature-card:nth-child(even) { background: var(--primary-soft); }
    .feature-card:hover { box-shadow: var(--shadow-2); border-color: var(--primary); }
    .feature-card .count { color: var(--text-soft); font-size: 0.85rem; margin-top: 6px; }
    .page-stack { display: grid; gap: var(--gap); }
    .filter-box { display: flex; align-items: center; gap: 10px; background: var(--surface-alt); border: 1px solid var(--border); border-radius: 999px; padding: 9px 16px; transition: border-color 160ms ease, box-shadow 160ms ease; }
    .filter-box:focus-within { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft); }
    .filter-box input { background: transparent; border: none; color: var(--text); outline: none; width: 220px; font-size: 0.9rem; }
    .scenario-list { display: grid; gap: 0; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
    .scenario-card { padding: 18px 20px; background: var(--surface); transition: background 140ms ease; border-bottom: 1px solid var(--border); }
    .scenario-card:last-child { border-bottom: none; }
    .scenario-card:nth-child(even) { background: var(--surface-alt); }
    .scenario-card:hover { background: var(--primary-soft); }
    .scenario-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
    .scenario-head h3 { font-size: 1.02rem; margin-top: 4px; font-weight: 500; }
    .scenario-meta { color: var(--text-soft); margin-top: 6px; font-size: 0.85rem; }
    .badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px; border-radius: 999px; font-size: 0.74rem; font-weight: 700; letter-spacing: 0.03em; text-transform: uppercase; white-space: nowrap; }
    .badge.tested { background: var(--success-soft); color: var(--success); }
    .badge.untested { background: var(--danger-soft); color: var(--danger); }
    .badge.passed { background: var(--success-soft); color: var(--success); }
    .badge.failed { background: var(--danger-soft); color: var(--danger); }
    .badge.skipped { background: var(--warning-soft); color: var(--warning); }
    .pill { display: inline-flex; align-items: center; padding: 4px 12px; border-radius: 999px; border: 1px solid var(--border); color: var(--text-soft); font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; margin-right: 6px; background: var(--surface-alt); }
    .required-row { margin-top: 14px; color: var(--text-soft); font-size: 0.85rem; }
    .steps { margin-top: 12px; padding-left: 20px; color: var(--text-soft); line-height: 1.65; font-size: 0.88rem; }
    .layer-stack { display: grid; gap: 8px; margin-top: 14px; }
    .layer-card { border: 1px solid var(--border); border-radius: 10px; background: var(--surface); overflow: hidden; }
    .layer-card summary { cursor: pointer; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; list-style: none; font-size: 0.88rem; }
    .layer-card summary::-webkit-details-marker { display:none; }
    .layer-card summary strong { text-transform: capitalize; }
    .layer-body { padding: 0 14px 14px; color: var(--text-soft); }
    .stats-line { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }
    .stats-line span { padding: 3px 10px; border-radius: 999px; background: var(--surface-alt); font-size: 0.78rem; }
    .result-list { margin: 6px 0 0; padding-left: 14px; display: grid; gap: 7px; }
    .result-row { display: flex; justify-content: space-between; gap: 12px; align-items: center; font-size: 0.85rem; }
    .result-name { font-weight: 500; color: var(--text); }
    .failure-block { margin-top: 8px; padding: 12px; border-radius: 8px; background: var(--danger-soft); border: 1px solid #f6c6c2; white-space: pre-wrap; font-family: "Roboto Mono", ui-monospace, SFMono-Regular, monospace; font-size: 0.79rem; line-height: 1.5; color: #7a1f14; }
    .empty-state { padding: 14px 0; color: var(--text-soft); font-size: 0.88rem; }
    .table-list { display: grid; gap: 0; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
    .table-row { display: grid; grid-template-columns: 100px 1fr 1.4fr 1.5fr 80px 90px; gap: 12px; align-items: start; padding: 12px 16px; background: var(--surface); border-bottom: 1px solid var(--border); font-size: 0.86rem; }
    .table-row:last-child { border-bottom: none; }
    .table-row:nth-child(even) { background: var(--surface-alt); }
    .table-row:hover { background: var(--primary-soft); }
    .table-row summary { cursor: pointer; display: grid; grid-template-columns: subgrid; grid-column: 1 / -1; align-items: center; list-style: none; }
    .table-row summary::-webkit-details-marker { display:none; }
    .table-row .mono { font-family: "Roboto Mono", ui-monospace, SFMono-Regular, monospace; font-size: 0.79rem; color: var(--text-soft); }
    .table-row .wrap { overflow-wrap: anywhere; }
    .hidden { display: none !important; }
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
      font-weight: 500;
      text-decoration: none;
      white-space: nowrap;
      transition: background 140ms ease, box-shadow 140ms ease;
    }
    .nav-button:hover { background: var(--primary-soft); box-shadow: var(--shadow-1); }
    .feature-card-link { text-decoration: none; color: inherit; cursor: pointer; display: block; }
    .feature-detail-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    @media (max-width: 960px) {
      body { padding: 16px; }
      .hero { grid-template-columns: 1fr; padding: 24px; }
      .panel { padding: 20px; }
      .health-grid { grid-template-columns: 1fr; }
      .table-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="page-shell">
    <header class="hero">
      <div class="eyebrow">Unified Test Tracer</div>
      <h1>Scenario Coverage Progress</h1>
      <p class="hero-subtitle">A release dashboard for feature coverage, layer maturity, and release risk.</p>
      <div class="hero-stats">
        <div class="stat-card" title="{{ tested }}/{{ total }} scenarios tested">
          <strong>{{ tested }}/{{ total }}</strong>
          <span>scenarios tested</span>
        </div>
        <div class="stat-card">
          <strong>{{ percentage }}%</strong>
          <span>coverage</span>
        </div>
      </div>
      <div class="bar-shell"><div class="bar-fill" style="width: {{ percentage }}%;"></div></div>
    </header>

    <main id="page-main" class="page-stack">
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
          <div class="health-value">{{ item.value }}</div>
          <div class="health-message">{{ item.message }}</div>
        </div>
        {% endfor %}
      </div>
    </section>

    <section class="panel">
      <div class="section-head">
        <div>
          <h2>Feature Breakdown</h2>
          <div class="muted">Coverage per feature file &mdash; click Features List for full detail</div>
        </div>
        <a class="nav-button" href="#/features">View Features List &rarr;</a>
      </div>
      <div class="feature-grid">
        {% for feature in feature_breakdown %}
        <div class="feature-card">
          <strong>{{ feature.name }}</strong>
          <div class="count">{{ feature.tested }}/{{ feature.total }} scenarios tested</div>
          <div class="bar-shell"><div class="bar-fill" style="width: {{ feature.percentage }}%;"></div></div>
        </div>
        {% endfor %}
      </div>
    </section>

    <section class="panel">
      <div class="section-head">
        <div>
          <h2>Test Pyramid</h2>
          <div class="muted">Execution mix across unit, integration, and E2E layers</div>
        </div>
      </div>
      <div class="pyramid-shell">
        {% for layer in layer_stats | reverse %}
        <div class="tier {{ layer.name }}" style="width: {{ layer.width_pct }}%;">
          <div class="tier-label">
            <strong>{{ layer.name }}</strong>
            <span class="tier-count">{{ layer.count }} tests · {{ format_duration(layer.duration) }}</span>
          </div>
          <div class="tier-meta">
            <span class="tier-chip">Pass {{ layer.pass_pct }}%</span>
            <span class="tier-chip">Fail {{ layer.fail_pct }}%</span>
            <span class="tier-chip">Skip {{ layer.skip_pct }}%</span>
          </div>
        </div>
        {% endfor %}
      </div>
    </section>

    <section class="panel">
      <div class="section-head">
        <div>
          <h2>Failure Breakdown</h2>
          <div class="muted">Expanding details for every failed result</div>
        </div>
      </div>
      {% if failed_results %}
      <div class="table-list">
        {% for result in failed_results %}
        <details class="table-row">
          <summary>
            <span class="pill">{{ result.layer }}</span>
            <span class="wrap">{{ result.name }}</span>
            <span class="wrap">{{ result.tags | join(', ') }}</span>
            <span class="mono">{{ _status_label(result.status) }}</span>
            <span class="mono">{{ format_duration(result.duration) }}</span>
          </summary>
          {% if result.failure_message %}
          <div class="failure-block">{{ result.failure_message }}</div>
          {% endif %}
        </details>
        {% endfor %}
      </div>
      {% else %}
      <div class="empty-state">No failures detected.</div>
      {% endif %}
    </section>

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

    <main id="page-features" class="page-stack hidden">
      <div class="panel">
        <div class="section-head">
          <div>
            <div class="eyebrow">Unified Test Tracer</div>
            <h2>Features List</h2>
            <div class="muted">Click a feature to see its full scenario matrix and traceability</div>
          </div>
          <a class="nav-button" href="#/">&larr; Back to Dashboard</a>
        </div>
        <div class="feature-grid">
          {% for feature in feature_breakdown %}
          <a class="feature-card feature-card-link" href="#/features/{{ feature.name | urlencode }}">
            <strong>{{ feature.name }}</strong>
            <div class="count">{{ feature.tested }}/{{ feature.total }} scenarios tested</div>
            <div class="bar-shell"><div class="bar-fill" style="width: {{ feature.percentage }}%;"></div></div>
          </a>
          {% endfor %}
        </div>
      </div>
    </main>

    <main id="page-feature-detail" class="page-stack hidden">
      {% for feature_name, feature_views in views | sort(attribute='scenario.feature') | groupby('scenario.feature') %}
      <section class="panel feature-detail-page" data-feature="{{ feature_name }}">
        <div class="section-head">
          <div>
            <div class="eyebrow">Feature</div>
            <h2>{{ feature_name }}</h2>
            <div class="muted">Search by tag to focus on the stories that matter</div>
          </div>
          <div class="feature-detail-actions">
            <label class="filter-box" for="tag-filter-{{ loop.index }}">
              <span>&#128269;</span>
              <input id="tag-filter-{{ loop.index }}" class="tag-filter-input" type="search" placeholder="Search by tag, e.g. FC-001" />
            </label>
            <a class="nav-button" href="#/features">&larr; All Features</a>
          </div>
        </div>
        <div class="scenario-list">
          {% for view in feature_views %}
          <article class="scenario-card" data-tags="{{ view.scenario.tags | join(' ') }}">
            <div class="scenario-head">
              <div>
                <div class="eyebrow">{{ view.scenario.feature }}</div>
                <h3>{{ view.scenario.name }}</h3>
                <div class="scenario-meta">{{ view.scenario.tags | join(', ') if view.scenario.tags else 'No linking tags' }}</div>
              </div>
              <span class="badge {{ 'tested' if view.is_tested else 'untested' }}">{{ 'tested' if view.is_tested else 'untested' }}</span>
            </div>
            <div class="required-row">Required: {{ _required_status(view) }}</div>
            {% if view.scenario.steps %}
            <ol class="steps">
              {% for step in view.scenario.steps %}
              <li>{{ step }}</li>
              {% endfor %}
            </ol>
            {% endif %}
            <div class="layer-stack">
              {% if view.layers %}
              {% for layer_group in view.layers %}
              <details class="layer-card">
                <summary>
                  <span><strong>{{ layer_group[0].layer }}</strong></span>
                  <span>{{ layer_group | length }} results · {{ format_duration(layer_group | sum(attribute='duration')) }}</span>
                </summary>
                <div class="layer-body">
                  <div class="stats-line">
                    {% for result in layer_group %}
                    <span class="badge {{ _status_class(result.status) }}">{{ _status_label(result.status) }}</span>
                    {% endfor %}
                  </div>
                  <ul class="result-list">
                    {% for result in layer_group %}
                    <li class="result-row">
                      <span class="result-name">{{ result.name }}</span>
                      <span>({{ result.status }})</span>
                      <span>{{ format_duration(result.duration) }}</span>
                    </li>
                    {% endfor %}
                  </ul>
                </div>
              </details>
              {% endfor %}
              {% else %}
              <div class="empty-state">No linked test results found for this scenario.</div>
              {% endif %}
            </div>
          </article>
          {% endfor %}
        </div>
      </section>
      {% endfor %}
    </main>
  </div>
  <script>
    function currentRoute() {
      return (window.location.hash || '#/').replace(/^#/, '');
    }

    function showFeatureDetail(featureName) {
      const pages = document.querySelectorAll('.feature-detail-page');
      pages.forEach((page) => {
        page.classList.toggle('hidden', page.getAttribute('data-feature') !== featureName);
      });
    }

    function route(pathOverride) {
      const path = pathOverride !== undefined ? pathOverride : currentRoute();
      const main = document.getElementById('page-main');
      const featuresList = document.getElementById('page-features');
      const featureDetail = document.getElementById('page-feature-detail');
      main.classList.add('hidden');
      featuresList.classList.add('hidden');
      featureDetail.classList.add('hidden');
      window.scrollTo(0, 0);

      const detailMatch = path.match(/^[/]features[/](.+)$/);
      if (detailMatch) {
        featureDetail.classList.remove('hidden');
        showFeatureDetail(decodeURIComponent(detailMatch[1]));
      } else if (path === '/features') {
        featuresList.classList.remove('hidden');
      } else {
        main.classList.remove('hidden');
      }
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

    document.querySelectorAll('.tag-filter-input').forEach((input) => {
      input.addEventListener('input', (event) => {
        const query = event.target.value.trim().toLowerCase();
        const section = event.target.closest('.feature-detail-page');
        const cards = section ? section.querySelectorAll('.scenario-card') : [];
        cards.forEach((card) => {
          const tags = (card.getAttribute('data-tags') || '').toLowerCase();
          const visible = !query || tags.includes(query);
          card.classList.toggle('hidden', !visible);
        });
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
    ) -> str:
        layer_stats = layer_stats or []
        health_checks = health_checks or {}
        failed_results = failed_results or []
        unlinked_results = unlinked_results or []

        if Template is not None:
            template = Template(_TEMPLATE_STR)
            template.globals["_required_status"] = _required_status
            template.globals["format_duration"] = _format_duration
            template.globals["_status_class"] = _status_class
            template.globals["_status_label"] = _status_label
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
            )

        lines = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            '<head><meta charset="utf-8"><title>Unified Test Tracer</title></head>',
            "<body>",
            "<h1>Scenario Coverage Progress</h1>",
            f"<p>{stats['tested']}/{stats['total']} scenarios tested</p>",
            "<ul>",
        ]
        for view in views:
            status = "tested" if view.is_tested else "untested"
            lines.append(f"<li>{view.scenario.feature}: {view.scenario.name} - {status}</li>")
        lines.extend(["</ul>", "</body>", "</html>"])
        return "\n".join(lines)
