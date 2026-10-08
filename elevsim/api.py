"""High-level entry points used by the CLI and the browser viewer."""
from __future__ import annotations

import json
import statistics
from dataclasses import replace

from .config import SimConfig
from .engine import Simulation
from .metrics import METRICS, summarize
from .passengers import generate_passengers
from .strategies import STRATEGIES, get_strategy


def _config(cfg) -> SimConfig:
    if isinstance(cfg, SimConfig):
        return cfg.validate()
    return SimConfig.from_dict(dict(cfg or {}))


def run(cfg, strategy: str = "collective", record: bool = False, frame_interval: float = 0.5,
        strategy_options: dict | None = None) -> dict:
    """Run one simulation; with ``record`` also return an animation trace."""
    cfg = _config(cfg)
    sim = Simulation(cfg, get_strategy(strategy, **(strategy_options or {})))
    sim.run(record=record, frame_interval=frame_interval)
    result = {
        "strategy": strategy,
        "strategy_label": STRATEGIES[strategy].label,
        "config": cfg.to_dict(),
        "summary": summarize(sim),
    }
    if record:
        result["trace"] = {
            "frame_interval": sim.frame_interval,
            # [t, [[position, state, direction, load], ...per car]]
            "frames": sim.frames,
            # [arrival, origin, dest, board, alight, car]
            "passengers": [[p.arrival, p.origin, p.dest, p.board, p.alight, p.car] for p in sim.passengers],
        }
    return result


def compare(cfg, strategies: list[str] | None = None, seeds: int | list[int] = 5) -> dict:
    """Run every strategy on the same seeded passenger sets and aggregate."""
    cfg = _config(cfg)
    strategies = strategies or list(STRATEGIES)
    seed_list = list(range(cfg.seed, cfg.seed + seeds)) if isinstance(seeds, int) else list(seeds)
    runs: dict[str, list[dict]] = {s: [] for s in strategies}
    for seed in seed_list:
        seeded = replace(cfg, seed=seed)
        people = generate_passengers(seeded)
        for name in strategies:
            # Fresh copies so every strategy starts from identical passengers.
            fresh = [replace(p) for p in people]
            sim = Simulation(seeded, get_strategy(name), passengers=fresh).run()
            runs[name].append(summarize(sim))

    results = []
    for name in strategies:
        agg = {}
        for key in METRICS:
            vals = [r[key] for r in runs[name]]
            agg[key] = {
                "mean": round(statistics.fmean(vals), 3),
                "std": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0,
                "min": min(vals),
                "max": max(vals),
            }
        results.append({"strategy": name, "label": STRATEGIES[name].label, "metrics": agg, "runs": runs[name]})
    return {
        "config": cfg.to_dict(),
        "seeds": seed_list,
        "metrics": {k: {"label": v[0], "unit": v[1], "lower_is_better": v[2]} for k, v in METRICS.items()},
        "results": results,
    }


def list_strategies() -> list[dict]:
    return [{"name": c.name, "label": c.label, "description": c.description} for c in STRATEGIES.values()]


# JSON-in / JSON-out wrappers for the browser (Pyodide) viewer.
def run_json(cfg_json: str, strategy: str) -> str:
    return json.dumps(run(json.loads(cfg_json), strategy, record=True))


def compare_json(cfg_json: str, strategies_json: str, seeds: int) -> str:
    return json.dumps(compare(json.loads(cfg_json), json.loads(strategies_json) or None, int(seeds)))


def strategies_json() -> str:
    return json.dumps(list_strategies())
