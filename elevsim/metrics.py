"""Turn a finished Simulation into summary metrics."""
from __future__ import annotations

import math
import statistics

from .energy import get_energy_model


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _mean(values) -> float:
    values = list(values)
    return statistics.fmean(values) if values else 0.0


# Metric name -> (label, unit, lower_is_better). Used by the CLI and viewer.
METRICS = {
    "avg_wait": ("Average wait", "s", True),
    "p95_wait": ("95th percentile wait", "s", True),
    "max_wait": ("Maximum wait", "s", True),
    "avg_travel": ("Average travel (in car)", "s", True),
    "avg_journey": ("Average total journey", "s", True),
    "max_journey": ("Maximum journey", "s", True),
    "long_wait_pct": ("Long waits", "%", True),
    "served": ("Passengers served", "", False),
    "unserved": ("Passengers not served", "", True),
    "makespan": ("Time to deliver everyone", "s", True),
    "utilization": ("Elevator utilization", "%", None),
    "avg_occupancy": ("Average car occupancy", "%", None),
    "idle_time": ("Elevator idle time (total)", "s", None),
    "floors_travelled": ("Floors travelled (total)", "", True),
    "energy_kwh": ("Energy use (estimate)", "kWh", True),
    "stops": ("Stops (total)", "", True),
    "avg_queue": ("Average queue per floor", "", True),
    "max_queue": ("Longest queue", "", True),
    "bottlenecks": ("Bottleneck episodes", "", True),
    "bottleneck_time": ("Time floors were bottlenecked", "s", True),
    "left_behind": ("Full-car pass-bys", "", True),
}


def summarize(sim) -> dict:
    cfg = sim.cfg
    ps = sim.passengers
    boarded = [p for p in ps if p.board is not None]
    done = [p for p in ps if p.alight is not None]
    waits = [p.board - p.arrival for p in boarded]
    # People still waiting at the end count with their wait so far.
    waits_all = waits + [sim.t - p.arrival for p in ps if p.board is None and p.arrival <= sim.t]
    travels = [p.alight - p.board for p in done]
    journeys = [p.alight - p.arrival for p in done]
    T = sim.t or 1.0
    E = len(sim.elevators)

    idle = sum(e.time_in_state["idle"] for e in sim.elevators)
    energy_model = get_energy_model(cfg)
    energy = sum(energy_model.car_energy_kwh(e) for e in sim.elevators)
    out = {
        "avg_wait": _mean(waits),
        "p95_wait": _pct(waits, 0.95),
        "max_wait": max(waits_all, default=0.0),
        "avg_travel": _mean(travels),
        "avg_journey": _mean(journeys),
        "max_journey": max(journeys, default=0.0),
        "long_wait_pct": 100.0 * sum(w >= cfg.long_wait for w in waits_all) / len(waits_all) if waits_all else 0.0,
        "served": len(done),
        "unserved": len(ps) - len(done),
        "makespan": sim.t,
        "utilization": 100.0 * (1 - idle / (T * E)),
        "avg_occupancy": 100.0 * sum(e.load_time for e in sim.elevators) / (T * E * cfg.capacity),
        "idle_time": idle,
        "floors_travelled": sum(e.floors_travelled for e in sim.elevators),
        "energy_kwh": energy,
        "energy_per_passenger": energy / len(done) if done else 0.0,
        "stops": sum(e.stops for e in sim.elevators),
        "avg_queue": sum(sim.queue_area) / (T * cfg.floors),
        "max_queue": max(sim.queue_max),
        "bottlenecks": sum(sim.bottleneck_episodes),
        "bottleneck_time": sum(sim.bottleneck_time),
        "left_behind": sim.left_behind_events,
        "passengers_total": len(ps),
        "horizon": sim.horizon,
    }
    out = {k: round(v, 3) if isinstance(v, float) else v for k, v in out.items()}
    out["per_floor"] = [
        {
            "floor": f,
            "avg_queue": round(sim.queue_area[f] / T, 3),
            "max_queue": sim.queue_max[f],
            "bottlenecks": sim.bottleneck_episodes[f],
            "bottleneck_time": round(sim.bottleneck_time[f], 3),
            "arrivals": sum(p.origin == f for p in ps),
        }
        for f in range(cfg.floors)
    ]
    out["per_elevator"] = [
        {
            "id": e.id,
            "served": e.served,
            "utilization": round(100.0 * (1 - e.time_in_state["idle"] / T), 2),
            "idle_time": round(e.time_in_state["idle"], 3),
            "moving_time": round(e.time_in_state["moving"], 3),
            "door_time": round(sum(e.time_in_state[s] for s in ("opening", "loading", "closing")), 3),
            "floors_travelled": e.floors_travelled,
            "loaded_floor_distance": e.loaded_floor_distance,
            "energy_kwh": round(energy_model.car_energy_kwh(e), 4),
            "stops": e.stops,
            "reversals": e.reversals,
            "avg_occupancy": round(100.0 * e.load_time / (T * cfg.capacity), 2),
        }
        for e in sim.elevators
    ]
    return out
