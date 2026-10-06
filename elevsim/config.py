"""Simulation configuration."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields

# Named traffic mixes: share of passengers that are incoming (lobby -> upper
# floor), outgoing (upper floor -> lobby) or interfloor (upper -> upper).
TRAFFIC_PATTERNS = {
    "uniform": None,  # origin and destination uniformly random over all floors
    "up_peak": {"incoming": 0.85, "outgoing": 0.05, "interfloor": 0.10},
    "down_peak": {"incoming": 0.05, "outgoing": 0.85, "interfloor": 0.10},
    "lunch": {"incoming": 0.40, "outgoing": 0.40, "interfloor": 0.20},
    "interfloor": {"incoming": 0.05, "outgoing": 0.05, "interfloor": 0.90},
}


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
    max_time: float = 4 * 3600.0  # hard stop

    # Metric thresholds
    bottleneck_queue: int = 6  # a floor queue at or above this counts as a bottleneck
    long_wait: float = 60.0  # waits at or above this (s) count as long waits

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
        if isinstance(self.traffic, str) and self.traffic not in TRAFFIC_PATTERNS:
            raise ValueError(f"unknown traffic pattern {self.traffic!r}; choose from {sorted(TRAFFIC_PATTERNS)}")
        for name in ("origin_weights", "destination_weights"):
            w = getattr(self, name)
            if w is not None and len(w) != self.floors:
                raise ValueError(f"{name} must have one weight per floor ({self.floors})")
        if self.idle_parking not in ("stay", "lobby"):
            raise ValueError("idle_parking must be 'stay' or 'lobby'")
        return self

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
