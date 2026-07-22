import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _layer_config(value):
    """Normalize a layer argument to a module-keyed path map.

    Accepts a single path (unscoped under ``""``) or an already module-keyed dict.
    """
    if isinstance(value, dict):
        return {module: [str(p) for p in paths] for module, paths in value.items()}
    return {"": [str(value)]}


def run_tool(features, output, unit=None, integration=None, e2e=None, **extra):
    config = {"features": [str(features)], "output": str(output)}
    if unit is not None:
        config["unit"] = _layer_config(unit)
    if integration is not None:
        config["integration"] = _layer_config(integration)
    if e2e is not None:
        config["e2e"] = _layer_config(e2e)
    config.update(extra)

    config_path = ROOT / "reports" / f"config-{uuid.uuid4().hex}.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config), encoding="utf-8")
    try:
        return subprocess.run(
            [sys.executable, "build_pyramid.py", str(config_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        config_path.unlink(missing_ok=True)
