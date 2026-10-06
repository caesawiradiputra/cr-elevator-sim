"""SCAN: sweep end to end like a disk head."""
from ..model import DOWN, NONE, UP
from .base import Strategy


class Scan(Strategy):
    name = "scan"
    label = "SCAN (full sweeps)"
    description = (
        "While any call exists, each car sweeps all the way to the top and bottom "
        "floors before reversing, stopping for calls in its direction. Simple and "
        "starvation-free, but travels further than needed."
    )

    def choose_direction(self, sim, car) -> int:
        targets = self.target_floors(sim, car)
        if not targets or targets == {car.floor} and not car.passengers:
            return NONE
        if car.direction == UP:
            return UP if car.floor < sim.top_floor else DOWN
        if car.direction == DOWN:
            return DOWN if car.floor > 0 else UP
        return super().choose_direction(sim, car)

    def should_stop(self, sim, car, floor: int) -> bool:
        if floor in car.car_calls:
            return True
        if car.full:
            return False
        calls = self.visible_calls(sim, car)
        if (floor, car.direction) in calls:
            return True
        at_end = floor in (0, sim.top_floor)
        return at_end and ((floor, UP) in calls or (floor, DOWN) in calls)
