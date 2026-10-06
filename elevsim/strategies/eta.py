"""Estimated-time-of-arrival dispatcher."""
from .base import DispatcherStrategy, route_distance


class EstimatedTime(DispatcherStrategy):
    name = "eta"
    label = "Estimated time (ETA)"
    description = (
        "A dispatcher estimates, for every car, how long until it could pick up "
        "the new call (travel along its current LOOK route plus the stops already "
        "planned) and assigns the call to the fastest car. Calls are re-planned "
        "every few seconds while nobody has been picked up."
    )

    def setup(self, sim) -> None:
        self.reassign_every = float(self.options.get("reassign_every", 5.0))
        # A call only moves to another car if that saves at least this many seconds.
        self.hysteresis = float(self.options.get("hysteresis", 4.0))
        self._last_replan = 0.0
        self._previous: dict = {}

    def assign_calls(self, sim) -> None:
        if sim.t - self._last_replan >= self.reassign_every:
            self._last_replan = sim.t
            self._previous = {}
            for key, call in sim.hall_calls.items():
                if call.assigned is not None:
                    self._previous[key] = call.assigned
                call.assigned = None
        super().assign_calls(sim)
        self._previous = {}

    def stop_time(self, sim) -> float:
        cfg = sim.cfg
        return 2 * cfg.door_time + cfg.board_time * 2

    def estimate(self, sim, car, call) -> float:
        cfg = sim.cfg
        assigned = {(c.floor, c.direction) for c in sim.hall_calls.values() if c.assigned == car.id}
        targets = car.car_calls | {f for f, _ in assigned}
        dist = route_distance(sim, car, call.floor, call.direction, targets)
        # Stops the car makes before reaching this call.
        stops_before = 0
        for f in targets:
            d = car.direction if f in car.car_calls else next(dd for ff, dd in assigned if ff == f)
            if f != call.floor and route_distance(sim, car, f, d, targets) < dist:
                stops_before += 1
        eta = dist * cfg.floor_travel_time + stops_before * self.stop_time(sim)
        if car.state not in ("idle", "moving"):
            eta += cfg.door_time  # finishing its current stop
        if car.full:
            eta += 1e6
        # Mild penalty for a crowded car: fewer free places, more boarding time.
        eta += car.load * cfg.board_time * 0.5
        return eta

    def pick_car(self, sim, call) -> int:
        times = {car.id: self.estimate(sim, car, call) for car in sim.elevators}
        best = min(times, key=lambda cid: (times[cid], cid))
        prev = self._previous.get((call.floor, call.direction))
        if prev is not None and times[prev] - times[best] < self.hysteresis:
            return prev
        return best
