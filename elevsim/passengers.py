"""Seeded passenger generation.

Passenger lists depend only on the config (including its seed), never on the
strategy, so every algorithm sees exactly the same people at the same times.
"""
from __future__ import annotations

import random

from .config import TRAFFIC_PATTERNS, SimConfig
from .model import Passenger


def _weighted_floor(rng: random.Random, weights: list[float], exclude: int | None = None) -> int:
    floors = [f for f in range(len(weights)) if f != exclude and weights[f] > 0]
    if not floors:
        raise ValueError("floor weights leave no valid floor to choose")
    return rng.choices(floors, weights=[weights[f] for f in floors])[0]


def _pick_trip(rng: random.Random, cfg: SimConfig) -> tuple[int, int]:
    n, lobby = cfg.floors, cfg.lobby_floor
    uniform = [1.0] * n

    if cfg.origin_weights or cfg.destination_weights:
        origin = _weighted_floor(rng, cfg.origin_weights or uniform)
        dest = _weighted_floor(rng, cfg.destination_weights or uniform, exclude=origin)
        return origin, dest

    mix = TRAFFIC_PATTERNS[cfg.traffic] if isinstance(cfg.traffic, str) else cfg.traffic
    if mix is None:
        origin = rng.randrange(n)
        dest = _weighted_floor(rng, uniform, exclude=origin)
        return origin, dest

    others = [1.0 if f != lobby else 0.0 for f in range(n)]
    kinds = ["incoming", "outgoing", "interfloor"]
    kind = rng.choices(kinds, weights=[mix.get(k, 0.0) for k in kinds])[0]
    if kind == "incoming":
        return lobby, _weighted_floor(rng, others)
    if kind == "outgoing":
        return _weighted_floor(rng, others), lobby
    if n < 3:  # no two distinct non-lobby floors; fall back to uniform
        origin = rng.randrange(n)
        return origin, _weighted_floor(rng, uniform, exclude=origin)
    origin = _weighted_floor(rng, others)
    return origin, _weighted_floor(rng, others, exclude=origin)


def generate_passengers(cfg: SimConfig) -> list[Passenger]:
    rng = random.Random(cfg.seed)
    mean_gap = 60.0 / cfg.arrival_rate
    t = 0.0
    out = []
    for i in range(cfg.passengers):
        t += rng.expovariate(1.0 / mean_gap)
        origin, dest = _pick_trip(rng, cfg)
        out.append(Passenger(id=i, arrival=round(t, 3), origin=origin, dest=dest))
    return out
