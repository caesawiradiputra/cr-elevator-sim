"""Nearest car dispatcher using the classic 'figure of suitability'."""
from ..model import NONE
from .base import DispatcherStrategy


class NearestCar(DispatcherStrategy):
    name = "nearest_car"
    label = "Nearest car"
    description = (
        "A dispatcher gives each hall call to the most suitable car: one already "
        "heading toward the call in the same direction scores best, then idle cars "
        "by distance, and cars moving away score worst."
    )

    def suitability(self, sim, car, call) -> float:
        n = sim.cfg.floors - 1
        pos = car.position(sim.cfg.floor_travel_time)
        dist = abs(call.floor - pos)
        if car.direction == NONE:
            return n + 1 - dist
        towards = (call.floor - pos) * car.direction > 0
        if towards and call.direction == car.direction:
            return n + 2 - dist
        if towards:
            return n + 1 - dist
        return 1

    def pick_car(self, sim, call) -> int:
        load = {c.id: 0 for c in sim.elevators}
        for other in sim.hall_calls.values():
            if other.assigned is not None:
                load[other.assigned] += 1
        best = max(
            sim.elevators,
            key=lambda car: (not car.full, self.suitability(sim, car, call), -load[car.id], -car.id),
        )
        return best.id
