import unittest
from pathlib import Path

from elevsim import SimConfig
from elevsim.config import TRAFFIC_PATTERNS
from elevsim.passengers import generate_passengers
from elevsim.viewer_build import _presets, build_viewer

SCENARIOS = Path(__file__).resolve().parent.parent / "scenarios"


class LunchPatternTests(unittest.TestCase):
    def test_every_pattern_shares_sum_to_one(self):
        for name, mix in TRAFFIC_PATTERNS.items():
            if mix is None:
                continue
            with self.subTest(pattern=name):
                self.assertAlmostEqual(sum(mix.values()), 1.0)

    def test_lunch_is_mostly_down_and_lunch_balanced_keeps_the_old_mix(self):
        lunch = TRAFFIC_PATTERNS["lunch"]
        self.assertGreater(lunch["outgoing"], 2 * lunch["incoming"])
        self.assertEqual(TRAFFIC_PATTERNS["lunch_balanced"], {"incoming": 0.40, "outgoing": 0.40, "interfloor": 0.20})

    def test_lunch_passengers_mostly_end_at_the_lobby(self):
        people = generate_passengers(SimConfig(traffic="lunch", passengers=2000))
        share = sum(p.dest == 0 for p in people) / len(people)
        self.assertGreater(share, 0.55)  # configured 0.65


class VariationFileTests(unittest.TestCase):
    def test_variations_do_not_reach_the_engine_config(self):
        cfg = SimConfig.from_file(str(SCENARIOS / "office_lunch.json"))
        self.assertEqual(cfg.traffic, "lunch")

    def test_presets_carry_merged_variations(self):
        presets = {p["id"]: p for p in _presets()}
        lunch = presets["office_lunch"]
        self.assertEqual(lunch["config"]["traffic"], "lunch")
        self.assertNotIn("variations", lunch["config"])
        self.assertEqual([v["name"] for v in lunch["variations"]], ["Balanced, both ways"])
        variation = lunch["variations"][0]
        self.assertGreaterEqual(len(variation["description"]), 80)
        self.assertEqual(variation["config"]["traffic"], "lunch_balanced")
        self.assertEqual(variation["config"]["floors"], lunch["config"]["floors"])  # base settings kept
        SimConfig.from_dict(variation["config"])  # a variation is a valid engine config
        self.assertEqual(presets["office_morning"]["variations"], [])

    def test_page_has_the_variation_control(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "viewer.html"
            build_viewer(str(out), demo=False)
            page = out.read_text()
        self.assertIn('id="variation"', page)
        self.assertIn('value="lunch_balanced"', page)


if __name__ == "__main__":
    unittest.main()
