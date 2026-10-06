"""Strategy interface plus the shared LOOK movement logic.

A strategy controls the cars through four hooks the engine calls:

* ``assign_calls(sim)``           every tick, before cars move. Dispatcher
                                  strategies set ``HallCall.assigned`` here.
* ``visible_calls(sim, car)``     the hall calls this car should respond to.
* ``choose_direction(sim, car)``  which way an idle car (or a car passing a
                                  floor) should go: UP, DOWN or NONE (stay).
* ``should_stop(sim, car, floor)`` whether a moving car stops at the floor it
                                  has just reached.

Optionally ``boarding_direction(sim, car)`` can force which waiting queue an
empty car takes at a stop (return None to use the engine default).

The default implementation is LOOK ("collective control"): keep going while
there is something to do ahead, stop for car calls and for hall calls in the
travel direction, reverse when nothing is left ahead.
"""
from __future__ import annotations

from ..model import DOWN, NONE, UP


class Strategy:
    name = "base"
    label = "Base"
    description = ""
    uses_dispatcher = False

    def __init__(self, **options):
        self.options = options

    # ------------------------------------------------------------------ hooks
    def setup(self, sim) -> None:
        pass

    def assign_calls(self, sim) -> None:
        pass

    def visible_calls(self, sim, car) -> dict:
        if not self.uses_dispatcher:
            return sim.hall_calls
        return {k: c for k, c in sim.hall_calls.items() if c.assigned == car.id}

    def boarding_direction(self, sim, car):
        return None

    # ---------------------------------------------------------- LOOK defaults
    def target_floors(self, sim, car) -> set[int]:
        return car.car_calls | {f for (f, _d) in self.visible_calls(sim, car)}

    def choose_direction(self, sim, car) -> int:
        targets = self.target_floors(sim, car)
        f = car.floor
        above = any(x > f for x in targets)
        below = any(x < f for x in targets)
        if car.direction == UP and above:
            return UP
        if car.direction == DOWN and below:
            return DOWN
        if above and below:
            nearest = min((x for x in targets if x != f), key=lambda x: (abs(x - f), x))
            return UP if nearest > f else DOWN
        if above:
            return UP
        if below:
            return DOWN
        return NONE

    def should_stop(self, sim, car, floor: int) -> bool:
        if floor in car.car_calls:
            return True
        if car.full:
            return False
        calls = self.visible_calls(sim, car)
        d = car.direction
        if (floor, d) in calls:
            return True
        if (floor, -d) in calls:
            # Turn around here only if nothing else is waiting further ahead.
            targets = self.target_floors(sim, car)
            return not any((x - floor) * d > 0 for x in targets)
        return False


class DispatcherStrategy(Strategy):
    """Base for strategies where a central dispatcher assigns each hall call to
    exactly one car; cars then run LOOK over their car calls and assigned calls.
    """

    uses_dispatcher = True

    def assign_calls(self, sim) -> None:
        for call in sorted(sim.hall_calls.values(), key=lambda c: c.time):
            if call.assigned is None:
                call.assigned = self.pick_car(sim, call)
                sim.call_assignments += 1

    def pick_car(self, sim, call) -> int:
        raise NotImplementedError


def route_distance(sim, car, floor: int, direction: int, targets: set[int] | None = None) -> float:
    """Floors a LOOK car must travel before it can serve a call at (floor, direction).

    ``targets`` are the car's current committed stops; they determine how far
    the car runs before reversing.
    """
    pos = car.position(sim.cfg.floor_travel_time)
    d = car.direction
    if targets is None:
        targets = car.car_calls
    if d == NONE or (not targets and car.load == 0):
        return abs(floor - pos)
    if d == UP:
        if floor >= pos and direction != DOWN:
            return floor - pos
        top = max([*targets, floor, pos])
        if direction == DOWN or floor >= pos:
            return (top - pos) + (top - floor)
        bottom = min([*targets, floor])
        return (top - pos) + (top - bottom) + (floor - bottom)
    # moving down
    if floor <= pos and direction != UP:
        return pos - floor
    bottom = min([*targets, floor, pos])
    if direction == UP or floor <= pos:
        return (pos - bottom) + (floor - bottom)
    top = max([*targets, floor])
    return (pos - bottom) + (top - bottom) + (top - floor)
