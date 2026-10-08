"""Office-day traffic: a deterministic scheduler for a fixed headcount.

Every employee has a fixed desk floor and a day made of timed segments: arrival,
optional meetings and cafeteria breaks, lunch (out of the building, cafeteria only,
or at the desk) and going home. The day is flattened into the same ``Passenger``
list the engine already consumes, so the engine and every strategy are unchanged
and every algorithm sees identical traffic: the schedule depends on the config and
the seed only, never on the strategy.

Building blocks, so a multi-day week can reuse them later:

* ``Employee``  id and fixed desk floor, created once.
* ``OfficeDay`` one day built from those employees (``day_index`` defaults to 0).
* ``Trip``      one hall-call request; ``Trip.time`` is seconds since midnight.

Rules (see docs/superpowers/specs/2026-10-08-office-day-scenario-design.md):

* Arrival, lunch and going home are placed first and never dropped.
* Meetings and cafeteria breaks are candidates. Each is a whole round trip
  (desk -> away -> desk), kept or dropped as one unit, and must lie inside
  [arrival + gap, go_home - gap] and at least ``min_trip_gap_s`` away from every
  other segment. So the configured meeting and break rates are candidate rates;
  the realized number is lower when candidates collide.
* The lobby and the cafeteria are the same floor, ``cfg.lobby_floor``.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .config import SimConfig, parse_hhmm
from .model import Passenger

_STAT_KEYS = (
    "lunch_out", "lunch_cafe", "lunch_desk",
    "meeting_candidates", "meeting_placed", "break_candidates", "break_placed",
)


@dataclass(frozen=True)
class Employee:
    id: int
    desk: int


@dataclass
class Trip:
    """One request: the person presses the hall button at ``time`` (seconds since midnight)."""

    time: float
    employee: int
    origin: int
    dest: int
    passenger_id: int | None = None


@dataclass
class OfficeDay:
    day_index: int
    profile: dict  # the day-level values drawn for this day
    employees: list[Employee]
    trips: dict[int, list[Trip]]  # employee id -> trips in time order
    stats: dict = field(default_factory=dict)

    def passengers(self, day_start: float) -> list[Passenger]:
        """Flatten to Passengers (arrival counted from ``day_start``) and number the trips."""
        order = sorted((t for trips in self.trips.values() for t in trips), key=lambda t: (t.time, t.employee))
        out = []
        for i, trip in enumerate(order):
            trip.passenger_id = i
            out.append(Passenger(id=i, arrival=round(trip.time - day_start, 3), origin=trip.origin, dest=trip.dest))
        return out


def _times(o: dict) -> dict:
    """The HH:MM entries of the office settings as seconds since midnight."""
    return {
        "arrival": tuple(parse_hhmm(t) for t in o["arrival_window"]),
        "late_end": parse_hhmm(o["late_end"]),
        "lunch": parse_hhmm(o["lunch_center"]),
        "work": tuple(parse_hhmm(t) for t in o["work_window"]),
        "home": tuple(parse_hhmm(t) for t in o["home_window"]),
    }


def build_employees(cfg: SimConfig, rng: random.Random) -> list[Employee]:
    """``cfg.employees`` people with fixed desk floors (never the lobby)."""
    lobby = cfg.lobby_floor
    floors = [f for f in range(cfg.floors) if f != lobby]
    if cfg.origin_weights:
        weights = [0.0 if f == lobby else w for f, w in enumerate(cfg.origin_weights)]
        if not any(w > 0 for w in weights):
            raise ValueError("origin_weights leave no desk floor besides the lobby")
        desks = rng.choices(range(cfg.floors), weights=weights, k=cfg.employees)
    else:
        desks = [floors[i % len(floors)] for i in range(cfg.employees)]
    return [Employee(i, d) for i, d in enumerate(desks)]


def draw_profile(cfg: SimConfig, o: dict, tm: dict, rng: random.Random) -> dict:
    """The day-level values for one day. With day_variation 0 they equal the configured values."""
    k = cfg.day_variation

    def vary(value: float, spread: float) -> float:
        u = rng.uniform(-1.0, 1.0)  # always drawn, so the random stream does not depend on day_variation
        return min(1.0, max(0.0, value + u * spread * k))

    late = vary(o["late_share"], o["day_spread"]["late_share"])
    lunch_out = vary(o["lunch_out_share"], o["day_spread"]["lunch_out_share"])
    stay_late = vary(o["stay_late_share"], o["day_spread"]["stay_late_share"])
    shift = rng.uniform(-1.0, 1.0) * o["day_spread"]["peak_shift_s"] * k
    a0, a1 = tm["arrival"]
    peak = min(a1, max(a0, parse_hhmm(o["arrival_peak"]) + shift))
    return {
        "late_share": late,
        "lunch_out_share": lunch_out,
        "lunch_cafe_share": min(o["lunch_cafe_share"], 1.0 - lunch_out),
        "stay_late_share": stay_late,
        "arrival_peak": peak,
    }


def _count(rng: random.Random, mean: float) -> int:
    """A whole number with the given mean (floor, plus one with the fractional probability)."""
    whole = int(mean)
    return whole + (1 if rng.random() < mean - whole else 0)


def _employee_trips(cfg, o, tm, profile, emp, rng, day_end, stats) -> list[Trip]:
    lobby, desk = cfg.lobby_floor, emp.desk
    gap = float(o["min_trip_gap_s"])
    a0, a1 = tm["arrival"]
    h0, h1 = tm["home"]
    w0, w1 = tm["work"]

    # Fixed segments: arrival and going home.
    if rng.random() < profile["late_share"]:
        t_arrive = rng.uniform(a1, tm["late_end"])
    else:
        t_arrive = rng.triangular(a0, a1, profile["arrival_peak"])
    if rng.random() < profile["stay_late_share"]:
        t_home = rng.uniform(h1, day_end)
    else:
        t_home = rng.uniform(h0, h1)
    busy = [(t_arrive, t_arrive), (t_home, t_home)]
    trips = [Trip(t_arrive, emp.id, lobby, desk), Trip(t_home, emp.id, desk, lobby)]

    def add_round_trip(start: float, length: float, away: int) -> bool:
        """Desk -> away -> desk, unless it leaves the person's day or comes within ``gap`` of anything placed."""
        end = start + length
        if start < t_arrive + gap or end > t_home - gap:
            return False
        if any(start < e + gap and s < end + gap for s, e in busy):
            return False
        busy.append((start, end))
        trips.append(Trip(start, emp.id, desk, away))
        trips.append(Trip(end, emp.id, away, desk))
        return True

    # Fixed segment: lunch. Placed before the optional ones so it is never dropped.
    draw = rng.random()
    if draw < profile["lunch_out_share"]:
        kind, minutes = "lunch_out", o["lunch_out_min"]
    elif draw < profile["lunch_out_share"] + profile["lunch_cafe_share"]:
        kind, minutes = "lunch_cafe", o["lunch_cafe_min"]
    else:
        kind, minutes = "lunch_desk", None
    stats[kind] += 1
    if minutes is not None:
        spread = o["lunch_spread_min"] * 60
        start = rng.uniform(tm["lunch"] - spread, tm["lunch"] + spread)
        if not add_round_trip(start, rng.uniform(*minutes) * 60, lobby):
            raise ValueError("lunch collides with arrival or going home; check the office time settings")

    # Optional segments: candidates that are kept or dropped as whole round trips.
    others = [f for f in range(cfg.floors) if f not in (lobby, desk)]
    for _ in range(_count(rng, o["meetings_per_person"])):
        start = rng.uniform(w0, w1)
        length = rng.uniform(*o["meeting_min"]) * 60
        if not others:  # no second non-lobby floor to meet on
            continue
        away = rng.choice(others)
        stats["meeting_candidates"] += 1
        stats["meeting_placed"] += add_round_trip(start, length, away)
    for _ in range(_count(rng, o["breaks_per_person"])):
        start = rng.uniform(w0, w1)
        length = rng.uniform(*o["break_min"]) * 60
        stats["break_candidates"] += 1
        stats["break_placed"] += add_round_trip(start, length, lobby)

    trips.sort(key=lambda t: t.time)
    return trips


def build_day(cfg: SimConfig, employees: list[Employee], rng: random.Random, day_index: int = 0) -> OfficeDay:
    """One office day for the given employees. ``day_index`` is the hook for multi-day weeks."""
    o = cfg.office_settings()
    tm = _times(o)
    profile = draw_profile(cfg, o, tm, rng)
    day_end = parse_hhmm(cfg.day_end)
    stats = dict.fromkeys(_STAT_KEYS, 0)
    trips = {e.id: _employee_trips(cfg, o, tm, profile, e, rng, day_end, stats) for e in employees}
    return OfficeDay(day_index, profile, employees, trips, stats)


def generate_office_day(cfg: SimConfig) -> tuple[OfficeDay, list[Passenger]]:
    """The structured day and its flattened Passenger list, both from the config and seed only."""
    rng = random.Random(cfg.seed)
    employees = build_employees(cfg, rng)
    day = build_day(cfg, employees, rng)
    return day, day.passengers(parse_hhmm(cfg.day_start))


def office_day_passengers(cfg: SimConfig) -> list[Passenger]:
    return generate_office_day(cfg)[1]
