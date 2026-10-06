"""Round robin dispatcher."""
from .base import DispatcherStrategy


class RoundRobin(DispatcherStrategy):
    name = "round_robin"
    label = "Round robin"
    description = (
        "A dispatcher hands each new hall call to the next car in turn, ignoring "
        "where the cars are. Spreads load evenly but often sends a distant car."
    )

    def setup(self, sim) -> None:
        self._next = 0

    def pick_car(self, sim, call) -> int:
        n = len(sim.elevators)
        for _ in range(n):
            car = sim.elevators[self._next]
            self._next = (self._next + 1) % n
            if not car.full:
                return car.id
        car = sim.elevators[self._next]
        self._next = (self._next + 1) % n
        return car.id
