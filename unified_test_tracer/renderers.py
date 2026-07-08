from typing import List

try:
    from jinja2 import Template
except ImportError:
    Template = None

from unified_test_tracer.models import ScenarioView

ALL_LAYERS = ["unit", "integration", "e2e"]


def _required_status(view: ScenarioView) -> str:
    parts = []
    for layer in ALL_LAYERS:
        if layer not in view.scenario.required_layers:
            continue
        has = any(r.layer == layer for r in view.linked_results)
        parts.append(f"{layer} {'[OK]' if has else '[MISSING]'}")
    return " | ".join(parts) if parts else "none"


_TEMPLATE_STR = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Unified Test Tracer</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; color: #123; }
    .hero { background: #f5f7fb; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .progress { height: 16px; background: #e5e7eb; border-radius: 999px; overflow: hidden; }
    .progress > div { height: 100%; background: #2f855a; }
    .feature-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; }
    .pill { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; background: #dbeafe; font-size: 0.9rem; }
    .required { margin: 0.5rem 0; font-size: 0.9rem; }
    .required .ok { color: #2f855a; }
    .required .missing { color: #c53030; }
  </style>
</head>
<body>
  <div class="hero">
    <h1>Scenario Coverage Progress</h1>
    <p>{{ tested }}/{{ total }} scenarios tested</p>
    <div class="progress"><div style="width: {{ percentage }}%;"></div></div>
  </div>

  <h2>Feature Breakdown</h2>
  {% for feature in feature_breakdown %}
  <div class="feature-card">
    <strong>{{ feature.name }}</strong>
    <div style="margin: 0.5rem 0;">{{ feature.tested }}/{{ feature.total }} scenarios tested</div>
    <div class="progress"><div style="width: {{ feature.percentage }}%;"></div></div>
  </div>
  {% endfor %}

  <h2>Scenarios</h2>
  <ul>
    {% for view in views %}
    <li>
      <span class="pill">{{ view.scenario.feature }}</span>
      {{ view.scenario.name }} - {% if view.is_tested %}tested{% else %}untested{% endif %}
      <div class="required">
        Required: {{ _required_status(view) }}
      </div>
      {% if view.layers %}
      <ul>
        {% for layer_group in view.layers %}
        {% set layer_name = layer_group[0].layer %}
        <li><strong>{{ layer_name }}</strong> ({{ layer_group | length }})
          <ul>
            {% for result in layer_group %}
            <li>{{ result.name }} ({{ result.status }})</li>
            {% endfor %}
          </ul>
        </li>
        {% endfor %}
      </ul>
      {% endif %}
    </li>
    {% endfor %}
  </ul>
</body>
</html>"""


class HtmlRenderer:

    def render(
        self,
        views: List[ScenarioView],
        stats: dict,
        feature_breakdown: List[dict],
    ) -> str:
        if Template is not None:
            template = Template(_TEMPLATE_STR)
            template.globals["_required_status"] = _required_status
            return template.render(
                tested=stats["tested"],
                total=stats["total"],
                percentage=stats["percentage"],
                feature_breakdown=feature_breakdown,
                views=views,
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
