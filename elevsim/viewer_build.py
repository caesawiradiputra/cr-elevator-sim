"""Build the standalone HTML viewer.

The viewer is one HTML file holding the page, its script, the Python source of
this package (run in the browser by Pyodide), the scenario presets and a
precomputed demo runs: they are on screen before the engine loads, and they
are all a reader can watch where the engine cannot load at all.
"""
from __future__ import annotations

import json
from pathlib import Path

from .api import compare, list_strategies, run
from .config import SimConfig
from .metrics import METRICS
from .strategies import STRATEGIES

ROOT = Path(__file__).resolve().parent.parent
PYODIDE_CDN = "https://cdn.jsdelivr.net/npm/pyodide@0.26.4/"
DEMO_PRESET = "office_lunch"


def _presets() -> list[dict]:
    out = []
    for path in sorted((ROOT / "scenarios").glob("*.json")):
        data = json.loads(path.read_text())
        name = data.pop("name", path.stem)
        data.pop("description", None)
        out.append({"id": path.stem, "name": name, "config": data})
    return out


def _sources() -> dict[str, str]:
    pkg = Path(__file__).resolve().parent
    return {
        str(p.relative_to(pkg.parent)).replace("\\", "/"): p.read_text()
        for p in sorted(pkg.rglob("*.py"))
        if "__pycache__" not in p.parts
    }


def build_data(demo: bool = True, pyodide_base: str = PYODIDE_CDN, demo_all: bool = False) -> dict:
    presets = _presets()
    data = {
        "pyodideBase": pyodide_base,
        "sources": _sources(),
        "presets": presets,
        "defaults": SimConfig().to_dict(),
        "strategies": list_strategies(),
        "metrics": {k: {"label": v[0], "unit": v[1], "lower_is_better": v[2]} for k, v in METRICS.items()},
        "demo": None,
    }
    if demo:
        ids = [p["id"] for p in presets] if demo_all else [DEMO_PRESET]
        scenarios = {}
        for p in presets:
            if p["id"] not in ids:
                continue
            runs = {name: run(p["config"], name, record=True, frame_interval=1.0) for name in STRATEGIES}
            cmp = compare(p["config"], seeds=5)
            for r in cmp["results"]:
                r.pop("runs")  # per-seed detail is not needed in the page
            scenarios[p["id"]] = {"runs": runs, "compare": cmp}
        data["demo"] = {"default": DEMO_PRESET if DEMO_PRESET in scenarios else next(iter(scenarios), None),
                        "default_strategy": "eta", "scenarios": scenarios}
    data["defaults"].pop("extra", None)
    return data


def build_viewer(out: str = "dist/viewer.html", demo: bool = True, pyodide_base: str = PYODIDE_CDN,
                 fragment: bool = False, demo_all: bool = False) -> str:
    """Write the viewer. ``fragment`` omits the <!doctype>/<html> wrapper (for hosts that add their own)."""
    vdir = ROOT / "viewer"
    page = (vdir / "index.html").read_text()
    payload = json.dumps(build_data(demo, pyodide_base, demo_all), separators=(",", ":")).replace("</", "<\\/")
    # Data goes in last: it contains this file's source, placeholders included.
    page = page.replace("/*__STYLE__*/", (vdir / "style.css").read_text())
    page = page.replace("/*__SCRIPT__*/", (vdir / "app.js").read_text())
    page = page.replace("/*__DATA__*/null", payload)
    if not fragment:
        page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n'
                + page + "\n</body>\n</html>\n")
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page)
    return str(path)
