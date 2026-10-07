import unittest

from elevsim import SimConfig, Simulation, compare
from elevsim.config import ENERGY_MODELS
from elevsim.energy import MODELS, get_energy_model
from elevsim.metrics import METRICS, summarize
from elevsim.model import Passenger
from elevsim.strategies import get_strategy


def ride(dest, riders, **cfg_kwargs):
    """One car at the lobby; `riders` people arrive together on floor 0 and all go to `dest`."""
    cfg = SimConfig(floors=6, elevators=1, **cfg_kwargs)
    people = [Passenger(id=i, arrival=1.0, origin=0, dest=dest) for i in range(riders)]
    return Simulation(cfg, get_strategy("collective"), passengers=people).run()


class EnergyCounterTests(unittest.TestCase):
    def test_raw_counters_for_two_riders_over_two_floors(self):
        sim = ride(dest=2, riders=2)
        car = sim.elevators[0]
        self.assertEqual(car.floors_travelled, 2)
        self.assertEqual(car.loaded_floor_distance, 4)

    def test_empty_car_adds_floors_but_no_loaded_distance(self):
        cfg = SimConfig(floors=6, elevators=1, idle_parking="lobby")
        # served at floor 3 -> 0, then the car has nothing to do; parking moves are empty moves
        person = Passenger(id=0, arrival=1.0, origin=3, dest=0)
        car = Simulation(cfg, get_strategy("collective"), passengers=[person]).run().elevators[0]
        self.assertEqual(car.loaded_floor_distance, 3)  # 3 floors down with one rider
        self.assertGreaterEqual(car.floors_travelled, 6)  # 3 empty up to the rider, 3 loaded down


class EnergyModelTests(unittest.TestCase):
    CONSTANTS = {"energy_base": 1.0, "energy_per_passenger": 0.5}

    def test_simple_model_exact_value(self):
        sim = ride(dest=2, riders=2, **self.CONSTANTS)
        s = summarize(sim)
        self.assertEqual(s["energy_kwh"], 4.0)  # 2 floors x 1.0 + 4 loaded floors x 0.5
        self.assertEqual(s["per_elevator"][0]["energy_kwh"], 4.0)
        self.assertEqual(s["per_elevator"][0]["loaded_floor_distance"], 4)
        self.assertEqual(s["energy_per_passenger"], 2.0)

    def test_longer_trips_and_heavier_loads_cost_more(self):
        short = summarize(ride(dest=2, riders=1, **self.CONSTANTS))["energy_kwh"]
        long_ = summarize(ride(dest=4, riders=1, **self.CONSTANTS))["energy_kwh"]
        heavy = summarize(ride(dest=2, riders=3, **self.CONSTANTS))["energy_kwh"]
        self.assertEqual((short, long_), (3.0, 6.0))
        self.assertGreater(long_, short)
        self.assertGreater(heavy, short)

    def test_nobody_served_means_zero_energy_and_no_division_by_zero(self):
        sim = Simulation(SimConfig(), get_strategy("collective"), passengers=[]).run()
        s = summarize(sim)
        self.assertEqual(s["energy_kwh"], 0.0)
        self.assertEqual(s["energy_per_passenger"], 0.0)

    def test_model_names_match_the_config(self):
        self.assertEqual(set(MODELS), set(ENERGY_MODELS))
        cfg = SimConfig()
        cfg.energy_model = "magic"
        with self.assertRaises(ValueError):
            get_energy_model(cfg)


class EnergyMetricTests(unittest.TestCase):
    def test_metric_is_registered_and_lower_is_better(self):
        self.assertEqual(METRICS["energy_kwh"], ("Energy use (estimate)", "kWh", True))

    def test_compare_aggregates_energy(self):
        out = compare({"passengers": 40}, ["collective"], seeds=2)
        self.assertGreater(out["results"][0]["metrics"]["energy_kwh"]["mean"], 0)
        self.assertIn("energy_kwh", out["metrics"])


if __name__ == "__main__":
    unittest.main()
