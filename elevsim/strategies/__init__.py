"""Strategy registry. Add a new algorithm by subclassing Strategy (or
DispatcherStrategy) and listing it in STRATEGIES."""
from .base import DispatcherStrategy, Strategy
from .collective import CollectiveLook
from .eta import EstimatedTime
from .nearest_car import NearestCar
from .round_robin import RoundRobin
from .scan import Scan

STRATEGIES = {cls.name: cls for cls in (CollectiveLook, Scan, RoundRobin, NearestCar, EstimatedTime)}


def get_strategy(name: str, **options) -> Strategy:
    try:
        return STRATEGIES[name](**options)
    except KeyError:
        raise ValueError(f"unknown strategy {name!r}; choose from {sorted(STRATEGIES)}") from None


__all__ = ["STRATEGIES", "Strategy", "DispatcherStrategy", "get_strategy"]
