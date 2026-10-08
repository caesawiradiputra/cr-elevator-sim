"""Simulation configuration."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields

DEFAULT_MAX_TIME = 4 * 3600.0  # hard stop used when max_time is None and the traffic is not scheduled
SCHEDULED_TRAFFIC = ("office_day",)  # traffic built by a scheduler (elevsim/schedule.py), not a mix below
ENERGY_MODELS = ("simple",)  # names known to elevsim/energy.py

# Defaults for traffic="office_day". Times are "HH:MM", durations are minutes, the
# rest are shares (0-1), rates per person or seconds. Override any of them with the
# `office` config key; unknown keys are rejected. These are placeholders, not real
# office statistics.
OFFICE_DEFAULTS = {
    "arrival_window": ["07:00", "08:00"],  # on-time arrivals, triangular
    "arrival_peak": "07:50",  # most likely arrival time inside the window
    "late_share": 0.15,  # share who arrive late, between the window end and late_end
    "late_end": "09:30",
    "lunch_center": "12:00",  # lunch departures spread around this time
    "lunch_spread_min": 30,  # +/- minutes
    "lunch_out_share": 0.40,  # leave the building (desk -> lobby -> desk)
    "lunch_cafe_share": 0.30,  # cafeteria on the lobby floor only; the rest eat at the desk
    "lunch_out_min": [30, 60],  # time away
    "lunch_cafe_min": [15, 40],
    "work_window": ["09:00", "17:00"],  # meetings and breaks start inside this window
    "meetings_per_person": 1.0,  # candidate rate; some are dropped when they overlap
    "breaks_per_person": 0.7,
    "meeting_min": [30, 60],
    "break_min": [10, 20],
    "home_window": ["17:00", "17:45"],  # most leave here; stay-late people leave until day_end
    "stay_late_share": 0.20,
    "min_trip_gap_s": 600,  # minimum seconds between one person's consecutive requests
    "drain_margin_s": 3600,  # time after the last request that the simulation may run
}

# Named traffic mixes: share of passengers that are incoming (lobby -> upper
# floor), outgoing (upper floor -> lobby) or interfloor (upper -> upper).
TRAFFIC_PATTERNS = {
    "uniform": None,  # origin and destination uniformly random over all floors
    "up_peak": {"incoming": 0.85, "outgoing": 0.05, "interfloor": 0.10},
    "down_peak": {"incoming": 0.05, "outgoing": 0.85, "interfloor": 0.10},
    "lunch": {"incoming": 0.40, "outgoing": 0.40, "interfloor": 0.20},
    "interfloor": {"incoming": 0.05, "outgoing": 0.05, "interfloor": 0.90},
}


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_hhmm(text: str) -> int:
    """Seconds since midnight for an "HH:MM" string; ValueError for anything else."""
    try:
        hours, minutes = text.split(":")
        h, m = int(hours), int(minutes)
    except (AttributeError, ValueError):
        raise ValueError(f"time must look like HH:MM, got {text!r}") from None
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f"time must look like HH:MM between 00:00 and 23:59, got {text!r}")
    return h * 3600 + m * 60


@dataclass
class SimConfig:
    # Building
    floors: int = 10
    elevators: int = 3
    capacity: int = 8
    lobby_floor: int = 0

    # Timing (seconds)
    floor_travel_time: float = 1.5  # time to move one floor
    door_time: float = 2.0  # time to open (and, separately, to close) the doors
    board_time: float = 1.0  # time for one passenger to get in or out

    # Passengers
    passengers: int = 200  # total passengers generated
    arrival_rate: float = 20.0  # mean arrivals per minute (Poisson process)
    traffic: str | dict = "uniform"  # name from TRAFFIC_PATTERNS or a custom mix dict
    origin_weights: list[float] | None = None  # optional per-floor weights (overrides traffic origin choice)
    destination_weights: list[float] | None = None  # optional per-floor weights for destinations

    # Operational rules
    idle_parking: str = "stay"  # "stay" or "lobby": where idle cars wait
    park_delay: float = 10.0  # seconds idle before a car heads to the parking floor

    # Engine
    seed: int = 1
    dt: float = 0.5  # simulation tick in seconds
    max_time: float | None = None  # hard stop in seconds; None = auto (4 h, or last office_day request + margin)

    # Metric thresholds
    bottleneck_queue: int = 6  # a floor queue at or above this counts as a bottleneck
    long_wait: float = 60.0  # waits at or above this (s) count as long waits

    # Office-day scenario (traffic="office_day"); `passengers` and `arrival_rate` do not apply to it
    employees: int = 300  # fixed headcount; each has a fixed desk floor
    day_start: str = "06:45"  # simulation time 0, as HH:MM
    day_end: str = "20:00"  # latest time any request may be generated
    day_variation: float = 1.0  # 0 = day-level shares exactly as configured, 1 = default spread
    office: dict = field(default_factory=dict)  # overrides for OFFICE_DEFAULTS

    # Energy (see elevsim/energy.py). The simple model's constants are uncalibrated, so
    # energy_kwh is a comparative estimate for ranking algorithms, not an absolute figure.
    energy_model: str = "simple"
    energy_base: float = 0.01  # kWh per floor a car moves, empty
    energy_per_passenger: float = 0.002  # extra kWh per passenger per floor moved

    extra: dict = field(default_factory=dict)  # free-form, passed to strategies

    def validate(self) -> "SimConfig":
        if self.floors < 2:
            raise ValueError("floors must be >= 2")
        if self.elevators < 1:
            raise ValueError("elevators must be >= 1")
        if self.capacity < 1:
            raise ValueError("capacity must be >= 1")
        if not 0 <= self.lobby_floor < self.floors:
            raise ValueError("lobby_floor must be a valid floor")
        if self.arrival_rate <= 0:
            raise ValueError("arrival_rate must be > 0")
        if self.dt <= 0:
            raise ValueError("dt must be > 0")
        if isinstance(self.traffic, str) and self.traffic not in TRAFFIC_PATTERNS and self.traffic not in SCHEDULED_TRAFFIC:
            raise ValueError(
                f"unknown traffic pattern {self.traffic!r}; choose from {sorted([*TRAFFIC_PATTERNS, *SCHEDULED_TRAFFIC])}"
            )
        for name in ("origin_weights", "destination_weights"):
            w = getattr(self, name)
            if w is not None and len(w) != self.floors:
                raise ValueError(f"{name} must have one weight per floor ({self.floors})")
        if self.idle_parking not in ("stay", "lobby"):
            raise ValueError("idle_parking must be 'stay' or 'lobby'")
        if self.max_time is not None and self.max_time <= 0:
            raise ValueError("max_time must be > 0 (or null for auto)")
        if self.energy_model not in ENERGY_MODELS:
            raise ValueError(f"unknown energy_model {self.energy_model!r}; choose from {list(ENERGY_MODELS)}")
        if self.energy_base < 0 or self.energy_per_passenger < 0:
            raise ValueError("energy_base and energy_per_passenger must be >= 0")
        if not isinstance(self.office, dict):
            raise ValueError("office must be a dict of overrides")
        unknown = set(self.office) - set(OFFICE_DEFAULTS)
        if unknown:
            raise ValueError(f"unknown office keys: {sorted(unknown)}")
        if self.traffic == "office_day":
            self._validate_office_day()
        return self

    def office_settings(self) -> dict:
        """OFFICE_DEFAULTS with the `office` overrides applied."""
        return {**OFFICE_DEFAULTS, **self.office}

    @staticmethod
    def _validate_office_types(o: dict) -> None:
        """Wrong types must be a ValueError here, not a TypeError halfway through generation."""
        for name in ("late_share", "lunch_spread_min", "lunch_out_share", "lunch_cafe_share", "meetings_per_person",
                     "breaks_per_person", "stay_late_share", "min_trip_gap_s", "drain_margin_s"):
            if not _is_number(o[name]):
                raise ValueError(f"office.{name} must be a number")
        for name in ("lunch_out_min", "lunch_cafe_min", "meeting_min", "break_min"):
            value = o[name]
            if not (isinstance(value, (list, tuple)) and len(value) == 2 and all(_is_number(x) for x in value)):
                raise ValueError(f"office.{name} must be [low, high] minutes (two numbers)")
        for name in ("arrival_window", "work_window", "home_window"):
            value = o[name]
            if not (isinstance(value, (list, tuple)) and len(value) == 2):
                raise ValueError(f'office.{name} must be ["HH:MM", "HH:MM"]')

    def _validate_office_day(self) -> None:
        if isinstance(self.employees, bool) or not isinstance(self.employees, int):
            raise ValueError("employees must be a whole number")
        if self.employees < 1:
            raise ValueError("employees must be >= 1")
        if not _is_number(self.day_variation) or self.day_variation < 0:
            raise ValueError("day_variation must be a number >= 0")
        if self.origin_weights is not None:
            desk_weights = [w for f, w in enumerate(self.origin_weights) if f != self.lobby_floor]
            if any(w < 0 for w in desk_weights) or not any(w > 0 for w in desk_weights):
                raise ValueError("origin_weights must be >= 0 and leave at least one desk floor besides the lobby")
        o = self.office_settings()
        self._validate_office_types(o)
        for name in ("late_share", "lunch_out_share", "lunch_cafe_share", "stay_late_share"):
            if not 0.0 <= o[name] <= 1.0:
                raise ValueError(f"office.{name} must be between 0 and 1")
        if o["lunch_out_share"] + o["lunch_cafe_share"] > 1.0:
            raise ValueError("office.lunch_out_share + office.lunch_cafe_share must not exceed 1")
        for name in ("meetings_per_person", "breaks_per_person", "drain_margin_s", "lunch_spread_min"):
            if o[name] < 0:
                raise ValueError(f"office.{name} must be >= 0")
        gap = o["min_trip_gap_s"]
        if gap <= 0:
            raise ValueError("office.min_trip_gap_s must be > 0")
        for name in ("lunch_out_min", "lunch_cafe_min", "meeting_min", "break_min"):
            low, high = o[name]
            if not low <= high or low * 60 < gap:
                raise ValueError(
                    f"office.{name} must be [low, high] minutes with low <= high and low x 60 >= min_trip_gap_s"
                )
        start, end = parse_hhmm(self.day_start), parse_hhmm(self.day_end)
        a0, a1 = (parse_hhmm(t) for t in o["arrival_window"])
        peak, late_end = parse_hhmm(o["arrival_peak"]), parse_hhmm(o["late_end"])
        w0, w1 = (parse_hhmm(t) for t in o["work_window"])
        h0, h1 = (parse_hhmm(t) for t in o["home_window"])
        lunch, spread = parse_hhmm(o["lunch_center"]), o["lunch_spread_min"] * 60
        longest_lunch = max(o["lunch_out_min"][1], o["lunch_cafe_min"][1]) * 60
        longest_optional = max(o["meeting_min"][1], o["break_min"][1]) * 60
        checks = [
            (start <= a0 < a1 <= late_end < h0 < h1 <= end,
             "times must be in order: day_start <= arrival_window < late_end < home_window <= day_end"),
            (a0 <= peak <= a1, "office.arrival_peak must lie inside office.arrival_window"),
            (w0 < w1, "office.work_window must be in order"),
            (w0 <= lunch - spread and lunch + spread + longest_lunch <= w1,
             "lunch (centre +/- spread, plus the longest lunch) must fit inside office.work_window"),
            (late_end + gap <= lunch - spread and lunch + spread + longest_lunch + gap <= h0,
             "lunch (centre +/- spread, plus the longest lunch) must stay min_trip_gap_s clear of late_end and home_window"),
            (w1 + longest_optional <= end, "day_end must leave room for the longest meeting or break after work_window"),
        ]
        for ok, message in checks:
            if not ok:
                raise ValueError(message)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SimConfig":
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        return cls(**data).validate()

    @classmethod
    def from_file(cls, path: str) -> "SimConfig":
        with open(path) as fh:
            data = json.load(fh)
        data.pop("name", None)
        data.pop("description", None)
        return cls.from_dict(data)
