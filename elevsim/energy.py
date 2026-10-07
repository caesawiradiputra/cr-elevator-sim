"""Energy models: turn the raw counters the engine records for each car into kWh.

The engine only counts facts (``Elevator.floors_travelled``, ``loaded_floor_distance``,
``time_in_state``). A model decides what they cost. To add a model, subclass
``EnergyModel``, register it in ``MODELS`` and add its name to ``ENERGY_MODELS`` in
``config.py``; the engine does not change.

The ``simple`` constants are uncalibrated, so ``energy_kwh`` is a comparative estimate
for ranking algorithms against each other, not an absolute figure.
"""
from __future__ import annotations


class EnergyModel:
    name = "base"

    def __init__(self, cfg):
        self.cfg = cfg

    def car_energy_kwh(self, car) -> float:
        raise NotImplementedError


class SimpleEnergy(EnergyModel):
    """Movement energy only: a cost per floor moved plus a cost per passenger per floor.

    Idle time and door-open time are collected by the engine but do not count here.
    """

    name = "simple"

    def car_energy_kwh(self, car) -> float:
        return (
            car.floors_travelled * self.cfg.energy_base
            + car.loaded_floor_distance * self.cfg.energy_per_passenger
        )


MODELS = {SimpleEnergy.name: SimpleEnergy}


def get_energy_model(cfg) -> EnergyModel:
    name = getattr(cfg, "energy_model", None)
    try:
        return MODELS[name](cfg)
    except KeyError:
        raise ValueError(f"unknown energy_model {name!r}; choose from {sorted(MODELS)}") from None
