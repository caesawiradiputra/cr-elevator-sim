"""Core data types shared by the engine and strategies."""
from __future__ import annotations

from dataclasses import dataclass, field

UP, DOWN, NONE = 1, -1, 0

# Elevator states
IDLE = "idle"  # stationary, doors closed, waiting for a decision
MOVING = "moving"
OPENING = "opening"
LOADING = "loading"  # doors open, passengers getting in/out
CLOSING = "closing"
STATE_CODES = {IDLE: 0, MOVING: 1, OPENING: 2, LOADING: 3, CLOSING: 4}


@dataclass
class Passenger:
    id: int
    arrival: float
    origin: int
    dest: int
    board: float | None = None
    alight: float | None = None
    car: int | None = None
    left_behind: int = 0  # times a car going their way left without them (full)

    @property
    def direction(self) -> int:
        return UP if self.dest > self.origin else DOWN


@dataclass
class HallCall:
    floor: int
    direction: int
    time: float  # when the button was first pressed
    assigned: int | None = None  # elevator id, for dispatcher-based strategies


@dataclass
class Elevator:
    id: int
    capacity: int
    floor: int = 0  # current floor, or the floor last departed while moving
    direction: int = NONE
    state: str = IDLE
    timer: float = 0.0
    passengers: list[Passenger] = field(default_factory=list)
    parking: bool = False
    idle_since: float = 0.0

    # statistics
    time_in_state: dict = field(default_factory=lambda: {s: 0.0 for s in STATE_CODES})
    load_time: float = 0.0  # integral of load over time (passenger-seconds)
    floors_travelled: int = 0
    stops: int = 0
    reversals: int = 0
    served: int = 0

    @property
    def load(self) -> int:
        return len(self.passengers)

    @property
    def full(self) -> bool:
        return len(self.passengers) >= self.capacity

    @property
    def car_calls(self) -> set[int]:
        return {p.dest for p in self.passengers}

    def position(self, floor_travel_time: float) -> float:
        """Continuous position in floors, for rendering and ETA estimates."""
        if self.state == MOVING:
            return self.floor + self.direction * (1.0 - self.timer / floor_travel_time)
        return float(self.floor)
