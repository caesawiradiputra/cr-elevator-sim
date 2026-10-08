import unittest

from tests.office_helpers import office_data

from elevsim import SimConfig, Simulation
from elevsim.config import OFFICE_KEYS, SCHEDULED_TRAFFIC, parse_hhmm
from elevsim.metrics import summarize
from elevsim.model import Passenger
from elevsim.strategies import get_strategy


def office_cfg(**overrides):
    return SimConfig.from_dict(office_data(**overrides))


class OfficeConfigTests(unittest.TestCase):
    def test_defaults(self):
        cfg = SimConfig().validate()
        self.assertIsNone(cfg.max_time)
        self.assertEqual(cfg.employees, 300)
        self.assertEqual((cfg.day_start, cfg.day_end), ("06:45", "20:00"))
        self.assertEqual(cfg.office, {})  # the office numbers are not in the code
        self.assertEqual(cfg.energy_model, "simple")

    def test_the_shipped_scenario_has_every_office_setting(self):
        cfg = office_cfg()
        self.assertEqual(set(cfg.office), set(OFFICE_KEYS))
        self.assertEqual(cfg.office_settings(), cfg.office)

    def test_office_day_needs_its_office_settings(self):
        with self.assertRaises(ValueError) as cm:
            SimConfig(traffic="office_day").validate()
        self.assertIn("scenarios/office_day.json", str(cm.exception))
        for key in OFFICE_KEYS:
            data = office_data()
            del data["office"][key]
            with self.subTest(missing=key), self.assertRaises(ValueError) as cm:
                SimConfig.from_dict(data)
            self.assertIn(key, str(cm.exception))

    def test_office_day_is_valid_traffic(self):
        self.assertEqual(SCHEDULED_TRAFFIC, ("office_day",))
        office_cfg()
        with self.assertRaises(ValueError) as cm:
            SimConfig(traffic="rush").validate()
        self.assertIn("office_day", str(cm.exception))

    def test_office_overrides_merge_over_the_scenario_values(self):
        cfg = office_cfg(office={"late_share": 0.3})
        self.assertEqual(cfg.office_settings()["late_share"], 0.3)
        self.assertEqual(cfg.office_settings()["late_end"], "09:30")

    def test_round_trip_keeps_max_time_auto(self):
        data = office_cfg().to_dict()
        self.assertIsNone(data["max_time"])
        self.assertIsNone(SimConfig.from_dict(data).max_time)

    def test_bad_values_are_rejected(self):
        bad = [
            {"office": {"nonsense": 1}},
            {"energy_model": "magic"},
            {"energy_base": -1.0},
            {"energy_per_passenger": -0.1},
            {"max_time": 0},
            {"employees": 0},
            {"day_variation": -0.1},
            {"day_start": "7am"},
            {"day_start": "25:00"},
            {"day_start": "21:00"},  # after day_end
            {"day_end": "17:30"},  # before the home window ends
            {"office": {"late_share": 1.5}},
            {"office": {"lunch_out_share": 0.8, "lunch_cafe_share": 0.4}},
            {"office": {"home_window": ["17:45", "17:00"]}},
            {"office": {"break_min": [5, 20]}},  # shorter than min_trip_gap_s
            {"office": {"min_trip_gap_s": 0}},
            {"office": {"arrival_peak": "09:00"}},  # outside arrival_window
            {"office": {"late_end": "11:40"}},  # a late arrival can collide with lunch
            {"office": {"home_window": ["13:30", "17:45"]}},  # lunch can run into going home
            # the day-to-day spread block
            {"office": {"day_spread": {"late_share": 0.05}}},  # incomplete
            {"office": {"day_spread": {"late_share": -0.1, "lunch_out_share": 0.1, "stay_late_share": 0.08, "peak_shift_s": 300}}},
            {"office": {"day_spread": {"late_share": "x", "lunch_out_share": 0.1, "stay_late_share": 0.08, "peak_shift_s": 300}}},
            {"office": {"day_spread": 5}},
            # malformed values must be ValueError at validate(), never a TypeError at run time
            {"employees": 2.5},
            {"employees": True},
            {"day_variation": "1"},
            {"office": []},
            {"office": {"lunch_out_min": [10, "20"]}},
            {"office": {"lunch_out_min": [10]}},
            {"office": {"late_share": "0.1"}},
            {"office": {"arrival_window": "07:00"}},
            {"office": {"home_window": [7, 8]}},
            # origin_weights that leave no desk floor besides the lobby
            {"floors": 3, "origin_weights": [1, 0, 0]},
            {"floors": 3, "origin_weights": [1, -1, 1]},
        ]
        for case in bad:
            with self.subTest(case=case), self.assertRaises(ValueError):
                SimConfig.from_dict(office_data(**case))

    def test_parse_hhmm(self):
        self.assertEqual(parse_hhmm("06:45"), 6 * 3600 + 45 * 60)
        self.assertEqual(parse_hhmm("00:00"), 0)
        for text in ("nine", "24:00", "12:60", "", None):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_hhmm(text)


class HorizonTests(unittest.TestCase):
    def _sim(self, cfg, arrival=1000.0):
        person = Passenger(id=0, arrival=arrival, origin=0, dest=1)
        return Simulation(cfg, get_strategy("collective"), passengers=[person])

    def test_legacy_default_is_four_hours(self):
        self.assertEqual(self._sim(SimConfig(floors=3)).horizon, 4 * 3600.0)

    def test_legacy_explicit_max_time_is_kept(self):
        self.assertEqual(self._sim(SimConfig(floors=3, max_time=5000.0)).horizon, 5000.0)

    def test_office_day_auto_is_last_arrival_plus_margin(self):
        self.assertEqual(self._sim(office_cfg(floors=3)).horizon, 1000.0 + 3600.0)

    def test_office_day_margin_is_configurable(self):
        cfg = office_cfg(floors=3, office={"drain_margin_s": 100})
        self.assertEqual(self._sim(cfg).horizon, 1100.0)

    def test_explicit_max_time_is_never_overridden(self):
        cfg = office_cfg(floors=3, max_time=9000.0)
        self.assertEqual(self._sim(cfg).horizon, 9000.0)

    def test_explicit_max_time_too_small_raises(self):
        cfg = office_cfg(floors=3, max_time=1000.0)
        with self.assertRaises(ValueError) as cm:
            self._sim(cfg)
        self.assertIn("1000", str(cm.exception))
        self.assertIn("4600", str(cm.exception))

    def test_config_is_not_mutated_and_summary_reports_the_horizon(self):
        cfg = office_cfg(floors=3)
        sim = self._sim(cfg).run()
        self.assertIsNone(cfg.max_time)
        summary = summarize(sim)
        self.assertEqual(summary["passengers_total"], 1)
        self.assertEqual(summary["horizon"], 4600.0)
        self.assertEqual(summary["served"], 1)


if __name__ == "__main__":
    unittest.main()
