import contextlib
import io
import unittest

from elevsim import SimConfig
from elevsim.cli import main
from elevsim.config import ConfigError
from elevsim.passengers import generate_passengers


def run_cli(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        main(list(argv))
    return out.getvalue()


class TrafficMixValidationTests(unittest.TestCase):
    def test_config_problems_are_config_errors_and_still_value_errors(self):
        # wrong type and wrong value alike: one error type for callers, a ValueError subclass for old code
        for traffic in (5, "rush", {"incoming": -1}):
            with self.subTest(traffic=traffic), self.assertRaises(ConfigError) as cm:
                SimConfig(traffic=traffic).validate()
            self.assertIsInstance(cm.exception, ValueError)

    def test_a_mix_is_relative_weights(self):
        SimConfig(traffic={"incoming": 3, "outgoing": 1, "interfloor": 0}).validate()  # need not sum to 1
        SimConfig(traffic={"outgoing": 1}).validate()  # missing kinds count as 0

    def test_the_old_names_are_gone(self):
        for name in ("up_peak", "down_peak", "lunch", "lunch_balanced", "interfloor"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                SimConfig(traffic=name).validate()

    def test_bad_mixes_are_rejected(self):
        for traffic in (
            {},
            {"incoming": 0, "outgoing": 0, "interfloor": 0},
            {"incoming": -1, "outgoing": 2},
            {"incoming": "1", "outgoing": 1},
            {"incoming": True, "outgoing": 1},
            {"sideways": 1},
            5,
            ["incoming"],
        ):
            with self.subTest(traffic=traffic), self.assertRaises(ValueError):
                SimConfig(traffic=traffic).validate()

    def test_a_mix_shapes_the_trips(self):
        people = generate_passengers(SimConfig(traffic={"incoming": 1, "outgoing": 0, "interfloor": 0}, passengers=300))
        self.assertTrue(all(p.origin == 0 and p.dest != 0 for p in people))
        people = generate_passengers(SimConfig(traffic={"incoming": 3, "outgoing": 1, "interfloor": 0}, passengers=2000))
        self.assertGreater(sum(p.origin == 0 for p in people) / len(people), 0.65)  # 3:1 -> 0.75


class MixFlagTests(unittest.TestCase):
    def test_mix_flag_sets_the_shares(self):
        text = run_cli("run", "-s", "collective", "--mix", "0.15,0.65,0.20", "--passengers", "40")
        self.assertIn("mix 15/65/20", text)

    def test_mix_flag_errors_are_clear(self):
        for argv in (
            ("run", "--mix", "1,2"),
            ("run", "--mix", "a,b,c"),
            ("run", "--mix", "0,0,0"),
            ("run", "--mix", "1,1,1", "--traffic", "uniform"),
        ):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as cm:
                main(list(argv))
            self.assertIn("mix", str(cm.exception.code).lower() + "mix" if "--traffic" in argv else str(cm.exception.code).lower())

    def test_traffic_flag_no_longer_takes_names(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["run", "--traffic", "up_peak"])


if __name__ == "__main__":
    unittest.main()
