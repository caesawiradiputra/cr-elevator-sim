import unittest

from elevsim import SimConfig, Simulation, compare, run
from elevsim.model import Passenger
from elevsim.passengers import generate_passengers
from elevsim.strategies import STRATEGIES, get_strategy

UP_PEAK = {"incoming": 0.85, "outgoing": 0.05, "interfloor": 0.10}
DOWN_PEAK = {"incoming": 0.05, "outgoing": 0.85, "interfloor": 0.10}
LUNCH = {"incoming": 0.15, "outgoing": 0.65, "interfloor": 0.20}
INTERFLOOR = {"incoming": 0.05, "outgoing": 0.05, "interfloor": 0.90}

SCENARIOS = [
    {},
    {"floors": 15, "elevators": 4, "traffic": UP_PEAK, "arrival_rate": 30, "passengers": 250},
    {"floors": 6, "elevators": 1, "capacity": 4, "traffic": DOWN_PEAK, "arrival_rate": 10},
    {"floors": 2, "elevators": 2, "passengers": 60},
    {"traffic": LUNCH, "idle_parking": "lobby", "dt": 0.25},
    {"floors": 8, "lobby_floor": 3, "traffic": INTERFLOOR, "capacity": 2, "arrival_rate": 15},
]


class InvariantTests(unittest.TestCase):
    def test_everyone_delivered_and_physics_hold(self):
        for scenario in SCENARIOS:
            cfg = SimConfig.from_dict({"passengers": 150, **scenario})
            for name in STRATEGIES:
                with self.subTest(scenario=scenario, strategy=name):
                    res = run(cfg, name, record=True)
                    s = res["summary"]
                    self.assertEqual(s["served"], cfg.passengers)
                    self.assertEqual(s["unserved"], 0)
                    for arr, origin, dest, board, alight, car in res["trace"]["passengers"]:
                        self.assertNotEqual(origin, dest)
                        self.assertLessEqual(arr, board)
                        self.assertLess(board, alight)
                        self.assertIn(car, range(cfg.elevators))
                    for _t, cars in res["trace"]["frames"]:
                        for pos, _state, _d, load in cars:
                            self.assertGreaterEqual(pos, -1e-6)
                            self.assertLessEqual(pos, cfg.floors - 1 + 1e-6)
                            self.assertLessEqual(load, cfg.capacity)
                    self.assertGreaterEqual(s["utilization"], 0)
                    self.assertLessEqual(s["utilization"], 100)

    def test_single_passenger_timing(self):
        # One person on floor 0 going to floor 3; car waits at the lobby.
        cfg = SimConfig(floors=5, elevators=1, passengers=1)
        p = Passenger(id=0, arrival=1.0, origin=0, dest=3)
        sim = Simulation(cfg, get_strategy("collective"), passengers=[p]).run()
        # arrives at t=1, doors open 2s, board 1s, doors close 2s, 3 floors x 1.5s,
        # doors open 2s, alight 1s (alight is stamped when stepping out starts).
        self.assertAlmostEqual(p.board, 3.0)
        self.assertAlmostEqual(p.alight, 3.0 + 1 + 2 + 4.5 + 2, delta=cfg.dt)


class FairnessTests(unittest.TestCase):
    def test_passengers_are_seeded_and_strategy_independent(self):
        cfg = SimConfig(seed=42)
        a = [(p.arrival, p.origin, p.dest) for p in generate_passengers(cfg)]
        b = [(p.arrival, p.origin, p.dest) for p in generate_passengers(cfg)]
        self.assertEqual(a, b)
        r1 = run(cfg, "scan", record=True)["trace"]["passengers"]
        r2 = run(cfg, "eta", record=True)["trace"]["passengers"]
        self.assertEqual([x[:3] for x in r1], [x[:3] for x in r2])

    def test_runs_are_deterministic(self):
        self.assertEqual(run({"seed": 7}, "eta")["summary"], run({"seed": 7}, "eta")["summary"])

    def test_compare_shape(self):
        out = compare({"passengers": 60}, ["collective", "nearest_car"], seeds=2)
        self.assertEqual(out["seeds"], [1, 2])
        self.assertEqual([r["strategy"] for r in out["results"]], ["collective", "nearest_car"])
        self.assertEqual(len(out["results"][0]["runs"]), 2)


class TrafficTests(unittest.TestCase):
    def test_up_peak_mostly_from_lobby(self):
        ps = generate_passengers(SimConfig(traffic=UP_PEAK, passengers=2000))
        share = sum(p.origin == 0 for p in ps) / len(ps)
        self.assertGreater(share, 0.75)

    def test_custom_weights(self):
        cfg = SimConfig(floors=4, origin_weights=[0, 0, 1, 0], passengers=50)
        self.assertTrue(all(p.origin == 2 for p in generate_passengers(cfg)))

    def test_known_traffic_values_validate(self):
        for traffic in ("uniform", UP_PEAK, DOWN_PEAK, LUNCH, INTERFLOOR):
            SimConfig(traffic=traffic).validate()
        with self.assertRaises(ValueError):
            SimConfig(traffic="rush").validate()


if __name__ == "__main__":
    unittest.main()
