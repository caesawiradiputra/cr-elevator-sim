"""Discrete-time simulation engine.

Each tick (``cfg.dt`` seconds):
  1. passengers whose arrival time has come join their floor's up/down queue
     and press the hall button (creating a HallCall if none is active);
  2. the strategy may assign hall calls to cars (dispatcher strategies);
  3. every elevator advances its state machine:
       idle -> moving -> (arrive at floor) -> opening -> loading -> closing -> idle
     The strategy decides which way an idle car goes and whether a moving car
     stops at the floor it is arriving at;
  4. statistics are sampled and, optionally, an animation frame is recorded.

Passengers get out first, then waiting passengers travelling in the car's
direction board one at a time until the car is full.
"""
from __future__ import annotations

import math
from collections import deque

from .config import DEFAULT_MAX_TIME, SimConfig
from .model import (
    CLOSING, DOWN, IDLE, LOADING, MOVING, NONE, OPENING, STATE_CODES, UP,
    Elevator, HallCall, Passenger,
)
from .passengers import generate_passengers

EPS = 1e-9
MAX_FRAMES = 10_000  # most frames a recorded office_day run may hold


class Simulation:
    def __init__(self, cfg: SimConfig, strategy, passengers: list[Passenger] | None = None):
        self.cfg = cfg.validate()
        self.strategy = strategy
        self.passengers = passengers if passengers is not None else generate_passengers(cfg)
        self.horizon = self._resolve_horizon()
        self._pending = deque(sorted(self.passengers, key=lambda p: p.arrival))
        self.queues: dict[tuple[int, int], deque[Passenger]] = {
            (f, d): deque() for f in range(cfg.floors) for d in (UP, DOWN)
        }
        self.hall_calls: dict[tuple[int, int], HallCall] = {}
        self.elevators = [
            Elevator(id=i, capacity=cfg.capacity, floor=cfg.lobby_floor) for i in range(cfg.elevators)
        ]
        self.t = 0.0
        self.delivered = 0

        # floor statistics
        self.queue_area = [0.0] * cfg.floors  # integral of queue length
        self.queue_max = [0] * cfg.floors
        self.bottleneck_episodes = [0] * cfg.floors
        self.bottleneck_time = [0.0] * cfg.floors
        self._in_bottleneck = [False] * cfg.floors
        self.left_behind_events = 0
        self.call_assignments = 0

        # animation
        self.frames: list | None = None
        self._frame_every = 1
        self.frame_interval: float | None = None  # effective seconds between frames, set by run(record=True)
        self._tick = 0

        strategy.setup(self)

    # ------------------------------------------------------------------ helpers
    @property
    def top_floor(self) -> int:
        return self.cfg.floors - 1

    def waiting_at(self, floor: int) -> int:
        return len(self.queues[(floor, UP)]) + len(self.queues[(floor, DOWN)])

    def finished(self) -> bool:
        return not self._pending and self.delivered == len(self.passengers)

    def _resolve_horizon(self) -> float:
        """Stop time in seconds: an explicit max_time, else 4 hours (office_day: last request + margin).

        Resolved here, from the passengers actually given, because every path (CLI, compare, viewer,
        tests) goes through Simulation; the config is never changed, so a copy made for another seed
        resolves its own horizon.
        """
        cfg = self.cfg
        if cfg.traffic != "office_day":
            return DEFAULT_MAX_TIME if cfg.max_time is None else cfg.max_time
        last = max((p.arrival for p in self.passengers), default=0.0)
        needed = last + float(cfg.office_settings()["drain_margin_s"])
        if cfg.max_time is None:
            return needed
        if cfg.max_time < needed:
            raise ValueError(
                f"max_time {cfg.max_time:g} s is shorter than the {needed:g} s this office_day needs "
                f"(last request at {last:g} s plus a {needed - last:g} s margin)"
            )
        return cfg.max_time

    # --------------------------------------------------------------------- run
    def run(self, record: bool = False, frame_interval: float = 0.5) -> Simulation:
        if record:
            self.frames = []
            self._frame_every = self._frames_every(frame_interval)
            self.frame_interval = self._frame_every * self.cfg.dt
            self._record_frame()
        while not self.finished() and self.t < self.horizon - EPS:
            self.step()
        if record and (self._tick % self._frame_every):
            self._record_frame()
        return self

    def _frames_every(self, requested: float) -> int:
        """Ticks between recorded frames.

        The requested interval, widened for office_day so a run records at most MAX_FRAMES
        frames. 9997 = MAX_FRAMES minus the initial frame, the final frame and one tick of
        slack. Existing traffic is never widened: with the 4-hour default horizon the cap
        would change every existing scenario's frames.
        """
        dt = self.cfg.dt
        every = max(1, round(requested / dt))
        if self.cfg.traffic == "office_day":
            every = max(every, math.ceil(self.horizon / (MAX_FRAMES - 3) / dt - 1e-9))
        return every

    def step(self) -> None:
        dt = self.cfg.dt
        self.t = round(self.t + dt, 9)
        self._tick += 1
        self._admit_arrivals()
        self.strategy.assign_calls(self)
        for e in self.elevators:
            e.time_in_state[e.state] += dt
            e.load_time += e.load * dt
            self._step_elevator(e, dt)
        self._sample_floors(dt)
        if self.frames is not None and self._tick % self._frame_every == 0:
            self._record_frame()

    # ---------------------------------------------------------------- arrivals
    def _admit_arrivals(self) -> None:
        while self._pending and self._pending[0].arrival <= self.t + EPS:
            p = self._pending.popleft()
            key = (p.origin, p.direction)
            self.queues[key].append(p)
            if key not in self.hall_calls:
                self.hall_calls[key] = HallCall(p.origin, p.direction, self.t)

    # --------------------------------------------------------------- elevators
    def _step_elevator(self, e: Elevator, dt: float) -> None:
        cfg = self.cfg
        if e.state == IDLE:
            self._decide(e)
        elif e.state == MOVING:
            e.timer -= dt
            if e.timer <= EPS:
                e.floor += e.direction
                e.floors_travelled += 1
                e.loaded_floor_distance += e.load  # load only changes while stopped
                self._arrive(e)
        elif e.state == OPENING:
            e.timer -= dt
            if e.timer <= EPS:
                e.state, e.timer = LOADING, 0.0
                self._load_step(e)
        elif e.state == LOADING:
            e.timer -= dt
            if e.timer <= EPS:
                self._load_step(e)
        elif e.state == CLOSING:
            e.timer -= dt
            if e.timer <= EPS:
                self._doors_closed(e)
                e.state = IDLE
                e.idle_since = self.t
                self._decide(e)

    def _decide(self, e: Elevator) -> None:
        """Idle car: open for a call here, start moving, park, or stay idle."""
        d = self.strategy.choose_direction(self, e)
        if not e.passengers and self._boardable_here(e, d):
            e.parking = False
            self._open(e)
            return
        if d != NONE:
            e.parking = False
            self._start_moving(e, d)
            return
        if (
            self.cfg.idle_parking == "lobby"
            and e.floor != self.cfg.lobby_floor
            and self.t - e.idle_since >= self.cfg.park_delay - EPS
        ):
            e.parking = True
            self._start_moving(e, UP if self.cfg.lobby_floor > e.floor else DOWN)
            return
        e.direction = NONE

    def _boardable_here(self, e: Elevator, d: int) -> bool:
        if e.full:
            return False
        visible = self.strategy.visible_calls(self, e)
        dirs = (d,) if d != NONE else (UP, DOWN)
        return any((e.floor, dd) in visible for dd in dirs)

    def _start_moving(self, e: Elevator, d: int) -> None:
        if e.direction not in (NONE, d):
            e.reversals += 1
        e.direction = d
        e.state = MOVING
        e.timer = self.cfg.floor_travel_time

    def _arrive(self, e: Elevator) -> None:
        """Car reaches e.floor while moving: stop, continue, reverse or halt."""
        if e.parking:
            stop = bool(e.passengers) or self.strategy.should_stop(self, e, e.floor)
            if stop or e.floor == self.cfg.lobby_floor:
                e.parking = False
                if stop:
                    self._open(e)
                else:
                    e.state, e.direction, e.idle_since = IDLE, NONE, self.t
                return
            if self.strategy.choose_direction(self, e) == NONE:
                e.timer += self.cfg.floor_travel_time
                return
            e.parking = False
        if self.strategy.should_stop(self, e, e.floor):
            self._open(e)
            return
        d = self.strategy.choose_direction(self, e)
        if d == e.direction and not self._can_continue(e):
            d = NONE
        if d == e.direction:
            e.timer += self.cfg.floor_travel_time
        elif d != NONE:
            self._start_moving(e, d)
        else:
            e.state, e.direction, e.idle_since = IDLE, NONE, self.t

    def _can_continue(self, e: Elevator) -> bool:
        nxt = e.floor + e.direction
        return 0 <= nxt <= self.top_floor

    def _open(self, e: Elevator) -> None:
        e.state = OPENING
        e.timer = self.cfg.door_time
        e.stops += 1

    def _load_step(self, e: Elevator) -> None:
        """One door action: unload one, else board one, else start closing."""
        for p in e.passengers:
            if p.dest == e.floor:
                e.passengers.remove(p)
                p.alight = self.t
                e.served += 1
                self.delivered += 1
                e.timer = self.cfg.board_time
                return

        d = self._boarding_direction(e)
        e.direction = d
        if d != NONE and not e.full:
            q = self.queues[(e.floor, d)]
            if q:
                p = q.popleft()
                p.board, p.car = self.t, e.id
                e.passengers.append(p)
                if not q:
                    self.hall_calls.pop((e.floor, d), None)
                e.timer = self.cfg.board_time
                return
        e.state = CLOSING
        e.timer = self.cfg.door_time

    def _boarding_direction(self, e: Elevator) -> int:
        f = e.floor
        if e.passengers:
            if any((p.dest - f) * e.direction > 0 for p in e.passengers):
                return e.direction
            return UP if any(p.dest > f for p in e.passengers) else DOWN
        if e.direction != NONE and self.queues[(f, e.direction)]:
            return e.direction
        override = self.strategy.boarding_direction(self, e)
        if override is not None:
            return override
        d = self.strategy.choose_direction(self, e)
        if d != NONE and self.queues[(f, d)]:
            return d
        up, down = self.queues[(f, UP)], self.queues[(f, DOWN)]
        if up and down:
            return UP if up[0].arrival <= down[0].arrival else DOWN
        if up:
            return UP
        if down:
            return DOWN
        return d

    def _doors_closed(self, e: Elevator) -> None:
        """Passengers still waiting in the car's direction were left behind."""
        if e.direction == NONE:
            return
        key = (e.floor, e.direction)
        q = self.queues[key]
        if q and e.full:
            for p in q:
                p.left_behind += 1
            self.left_behind_events += 1
            call = self.hall_calls.get(key)
            if call is not None and call.assigned == e.id:
                call.assigned = None  # let the dispatcher pick another car

    # -------------------------------------------------------------- statistics
    def _sample_floors(self, dt: float) -> None:
        thr = self.cfg.bottleneck_queue
        for f in range(self.cfg.floors):
            n = self.waiting_at(f)
            self.queue_area[f] += n * dt
            if n > self.queue_max[f]:
                self.queue_max[f] = n
            over = n >= thr
            if over:
                self.bottleneck_time[f] += dt
                if not self._in_bottleneck[f]:
                    self.bottleneck_episodes[f] += 1
            self._in_bottleneck[f] = over

    def _record_frame(self) -> None:
        tt = self.cfg.floor_travel_time
        self.frames.append([
            round(self.t, 3),
            [[round(e.position(tt), 3), STATE_CODES[e.state], e.direction, e.load] for e in self.elevators],
        ])
