import unittest
from dataclasses import replace

from elevsim import SimConfig, Simulation, compare, run
from elevsim.config import parse_hhmm
from elevsim.passengers import generate_passengers
from elevsim.schedule import generate_office_day
from elevsim.strategies import STRATEGIES, get_strategy


def office(**kw):
    base = {"floors": 15, "elevators": 4, "capacity": 10, "traffic": "office_day", "employees": 60, "seed": 1}
    return SimConfig.from_dict({**base, **kw})


def as_tuples(people):
    return [(p.arrival, p.origin, p.dest) for p in people]


class SchedulerTests(unittest.TestCase):
    def test_deterministic_and_seed_dependent(self):
        self.assertEqual(as_tuples(generate_passengers(office())), as_tuples(generate_passengers(office())))
        self.assertNotEqual(as_tuples(generate_passengers(office())), as_tuples(generate_passengers(office(seed=2))))

    def test_passengers_key_is_ignored(self):
        a = generate_passengers(office(passengers=5))
        b = generate_passengers(office(passengers=999))
        self.assertEqual(as_tuples(a), as_tuples(b))

    def test_passenger_list_is_well_formed(self):
        cfg = office()
        people = generate_passengers(cfg)
        window = parse_hhmm(cfg.day_end) - parse_hhmm(cfg.day_start)
        self.assertEqual([p.id for p in people], list(range(len(people))))
        self.assertEqual([p.arrival for p in people], sorted(p.arrival for p in people))
        for p in people:
            self.assertNotEqual(p.origin, p.dest)
            self.assertTrue(0 <= p.arrival <= window)

    def test_every_employee_chains_and_ends_in_the_lobby(self):
        cfg = office(employees=80)
        day, people = generate_office_day(cfg)
        gap = cfg.office_settings()["min_trip_gap_s"]
        lobby = cfg.lobby_floor
        self.assertEqual(len(day.employees), 80)
        for emp in day.employees:
            trips = day.trips[emp.id]
            self.assertNotEqual(emp.desk, lobby)
            self.assertEqual((trips[0].origin, trips[0].dest), (lobby, emp.desk))
            self.assertEqual((trips[-1].origin, trips[-1].dest), (emp.desk, lobby))
            for prev, nxt in zip(trips, trips[1:]):
                self.assertEqual(nxt.origin, prev.dest)
                self.assertGreaterEqual(nxt.time - prev.time, gap)
        self.assertEqual(sum(len(t) for t in day.trips.values()), len(people))

    def test_lunch_choice_is_recorded_for_everyone(self):
        day, _ = generate_office_day(office(employees=80))
        s = day.stats
        self.assertEqual(s["lunch_out"] + s["lunch_cafe"] + s["lunch_desk"], 80)

    def test_realized_rates_stay_between_a_lower_bound_and_the_candidate_rate(self):
        day, _ = generate_office_day(office(employees=300))
        s = day.stats
        self.assertGreater(s["meeting_candidates"], 0)
        self.assertLessEqual(s["meeting_placed"], s["meeting_candidates"])
        self.assertGreaterEqual(s["meeting_placed"], 0.6 * s["meeting_candidates"])  # prototype: about 0.78
        self.assertLessEqual(s["break_placed"], s["break_candidates"])
        self.assertGreaterEqual(s["break_placed"], 0.5 * s["break_candidates"])  # prototype: about 0.70

    def test_day_variation_zero_fixes_the_profile_but_not_the_people(self):
        d1, p1 = generate_office_day(office(day_variation=0.0, seed=1))
        d2, p2 = generate_office_day(office(day_variation=0.0, seed=2))
        self.assertEqual(d1.profile, d2.profile)
        self.assertNotEqual(as_tuples(p1), as_tuples(p2))
        self.assertEqual(d1.profile["late_share"], 0.15)

    def test_day_variation_changes_the_profile_between_seeds(self):
        d1, _ = generate_office_day(office(day_variation=1.0, seed=1))
        d2, _ = generate_office_day(office(day_variation=1.0, seed=2))
        self.assertNotEqual(d1.profile, d2.profile)

    def test_variation_clamps_shares(self):
        cfg_kwargs = {"office": {"lunch_out_share": 0.9, "lunch_cafe_share": 0.1}, "day_variation": 3.0, "employees": 5}
        for seed in range(30):
            with self.subTest(seed=seed):
                day, _ = generate_office_day(office(seed=seed, **cfg_kwargs))
                p = day.profile
                for key in ("late_share", "lunch_out_share", "lunch_cafe_share", "stay_late_share"):
                    self.assertTrue(0.0 <= p[key] <= 1.0, (key, p[key]))
                self.assertLessEqual(p["lunch_out_share"] + p["lunch_cafe_share"], 1.0 + 1e-9)

    def test_tiny_buildings(self):
        cases = [
            {"floors": 2, "employees": 3},  # only one non-lobby floor: no meetings possible
            {"floors": 3, "employees": 1},
            {"floors": 8, "employees": 20, "lobby_floor": 3, "elevators": 2, "capacity": 4},
        ]
        for kw in cases:
            with self.subTest(**kw):
                cfg = office(**kw)
                day, people = generate_office_day(cfg)
                lobby = cfg.lobby_floor
                for emp in day.employees:
                    trips = day.trips[emp.id]
                    self.assertNotEqual(emp.desk, lobby)
                    self.assertEqual(trips[0].origin, lobby)
                    self.assertEqual(trips[-1].dest, lobby)
                    for prev, nxt in zip(trips, trips[1:]):
                        self.assertEqual(nxt.origin, prev.dest)
                fresh = [replace(p) for p in people]
                sim = Simulation(cfg, get_strategy("eta"), passengers=fresh).run()
                self.assertEqual(sim.delivered, len(people))

    def test_origin_weights_place_desks_and_reject_lobby_only(self):
        day, _ = generate_office_day(office(floors=3, origin_weights=[0, 0, 1], employees=10))
        self.assertTrue(all(e.desk == 2 for e in day.employees))
        with self.assertRaises(ValueError):
            generate_office_day(office(floors=3, origin_weights=[1, 0, 0], employees=10))

    def test_desks_spread_evenly_by_default(self):
        day, _ = generate_office_day(office(floors=5, employees=8))
        desks = [e.desk for e in day.employees]
        self.assertEqual(sorted(set(desks)), [1, 2, 3, 4])
        self.assertEqual(max(desks.count(f) for f in (1, 2, 3, 4)), 2)


class IntegrationTests(unittest.TestCase):
    def test_every_strategy_serves_everyone_and_sees_the_same_trips(self):
        cfg = office(employees=30)
        expected = len(generate_passengers(cfg))
        seen = []
        for name in STRATEGIES:
            with self.subTest(strategy=name):
                res = run(cfg, name, record=True)
                self.assertEqual(res["summary"]["served"], expected)
                self.assertEqual(res["summary"]["unserved"], 0)
                self.assertEqual(res["summary"]["passengers_total"], expected)
                seen.append([x[:3] for x in res["trace"]["passengers"]])
        self.assertTrue(all(trips == seen[0] for trips in seen))

    def test_explicit_max_time_too_small(self):
        with self.assertRaises(ValueError):
            run(office(employees=10, max_time=1000.0), "collective")

    def test_compare_over_seeds(self):
        cfg = office(employees=20)
        out = compare(cfg, ["collective", "eta"], seeds=2)
        self.assertIsNone(out["config"]["max_time"])
        for result in out["results"]:
            self.assertEqual(len(result["runs"]), 2)
            for summary in result["runs"]:
                self.assertGreater(summary["passengers_total"], 0)
                self.assertEqual(summary["unserved"], 0)
        self.assertIsNone(cfg.max_time)


class OrderingTests(unittest.TestCase):
    """A person's next request should not come before the previous trip has finished."""

    def _violation_share(self, cfg, strategy):
        day, people = generate_office_day(cfg)
        fresh = [replace(p) for p in people]
        Simulation(cfg, get_strategy(strategy), passengers=fresh).run()
        by_id = {p.id: p for p in fresh}
        pairs = bad = 0
        for trips in day.trips.values():
            for prev, nxt in zip(trips, trips[1:]):
                pairs += 1
                a, b = by_id[prev.passenger_id], by_id[nxt.passenger_id]
                if a.alight is None or b.arrival < a.alight:
                    bad += 1
        return bad / pairs

    def test_eta_and_collective_stay_within_one_percent(self):
        for seed in range(1, 6):
            cfg = office(employees=300, seed=seed)
            for name in ("eta", "collective"):
                with self.subTest(seed=seed, strategy=name):
                    self.assertLessEqual(self._violation_share(cfg, name), 0.01)  # prototype: 0

    def test_share_is_reported_for_every_strategy(self):
        cfg = office(employees=300, seed=1)
        shares = {name: self._violation_share(cfg, name) for name in STRATEGIES}
        print(f"\nrequest-before-alight share by strategy (seed 1): {shares}")
        for name, share in shares.items():
            self.assertTrue(0.0 <= share <= 1.0, name)


if __name__ == "__main__":
    unittest.main()
