import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from elevsim import SimConfig
from elevsim.cli import main
from elevsim.config import resolve_scenario, scenario_variations
from elevsim.passengers import generate_passengers
from elevsim.viewer_build import _presets, build_viewer

SCENARIOS = Path(__file__).resolve().parent.parent / "scenarios"
LUNCH = str(SCENARIOS / "office_lunch.json")


def scenario(**extra):
    base = {
        "name": "Test", "floors": 6, "elevators": 2, "passengers": 20, "traffic": "uniform",
        "variations": [
            {"id": "a", "name": "A", "description": "first", "arrival_rate": 5},
            {"id": "b", "name": "B", "description": "second", "traffic": {"incoming": 1, "outgoing": 1, "interfloor": 0}},
            {"id": "c", "name": "C", "description": "third", "capacity": 3},
        ],
    }
    return {**base, **extra}


class LunchMixTests(unittest.TestCase):
    def test_default_lunch_is_mostly_down_and_the_balanced_version_keeps_the_old_mix(self):
        rush = SimConfig.from_file(LUNCH).traffic
        self.assertGreater(rush["outgoing"], 2 * rush["incoming"])
        self.assertEqual(SimConfig.from_file(LUNCH, variation="balanced").traffic,
                         {"incoming": 0.40, "outgoing": 0.40, "interfloor": 0.20})

    def test_lunch_passengers_mostly_end_at_the_lobby(self):
        cfg = SimConfig.from_file(LUNCH)
        cfg.passengers = 2000
        people = generate_passengers(cfg)
        share = sum(p.dest == 0 for p in people) / len(people)
        self.assertGreater(share, 0.55)  # configured 0.65


class ResolveScenarioTests(unittest.TestCase):
    def test_a_file_without_variations_is_one_implicit_version(self):
        data = {"name": "Flat", "description": "x", "floors": 4, "traffic": "uniform"}
        self.assertEqual(resolve_scenario(data), {"floors": 4, "traffic": "uniform"})
        self.assertEqual(scenario_variations(data), [])
        with self.assertRaises(ValueError):
            resolve_scenario(data, "anything")

    def test_root_settings_then_the_chosen_variation_on_top(self):
        data = scenario()
        self.assertEqual(resolve_scenario(data, "a")["arrival_rate"], 5)
        self.assertEqual(resolve_scenario(data, "a")["traffic"], "uniform")  # inherited from the root
        self.assertEqual(resolve_scenario(data, "b")["traffic"], {"incoming": 1, "outgoing": 1, "interfloor": 0})
        self.assertNotIn("arrival_rate", resolve_scenario(data, "b"))
        for key in ("name", "description", "variations", "enabled_variations", "default_variation", "id"):
            self.assertNotIn(key, resolve_scenario(data, "a"))

    def test_the_default_is_default_variation_else_the_first_enabled(self):
        self.assertEqual(resolve_scenario(scenario(default_variation="b", enabled_variations=["a", "b"]))["traffic"], {"incoming": 1, "outgoing": 1, "interfloor": 0})
        self.assertEqual(resolve_scenario(scenario(enabled_variations=["b", "a"]))["traffic"], {"incoming": 1, "outgoing": 1, "interfloor": 0})  # first enabled
        self.assertEqual(resolve_scenario(scenario())["arrival_rate"], 5)  # first listed when nothing is enabled explicitly

    def test_enabled_variations_limit_what_the_viewer_lists_but_not_what_can_be_asked_for(self):
        data = scenario(enabled_variations=["b", "a"])
        self.assertEqual([v["id"] for v in scenario_variations(data)], ["b", "a"])  # enabled order
        self.assertEqual(resolve_scenario(data, "c")["capacity"], 3)  # a disabled one can still be asked for by id

    def test_bad_files_are_rejected_with_a_clear_error(self):
        bad = [
            scenario(enabled_variations=["a", "zzz"]),
            scenario(enabled_variations=[]),
            scenario(default_variation="c", enabled_variations=["a", "b"]),  # default must be enabled
            scenario(default_variation="zzz"),
            {**scenario(), "variations": [{"id": "a", "name": "A"}, {"id": "a", "name": "A2"}]},  # duplicate id
            {**scenario(), "variations": [{"name": "no id"}]},
            {"name": "x", "enabled_variations": ["a"]},  # enabled without any variations
        ]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(ValueError):
                resolve_scenario(data)
        with self.assertRaises(ValueError):
            resolve_scenario(scenario(), "zzz")


class ScenarioFileTests(unittest.TestCase):
    def test_every_shipped_scenario_lists_its_versions(self):
        for path in sorted(SCENARIOS.glob("*.json")):
            data = json.loads(path.read_text())
            with self.subTest(scenario=path.stem):
                self.assertTrue(data["variations"])
                self.assertIn(data["default_variation"], data["enabled_variations"])
                for variation in scenario_variations(data):
                    self.assertGreaterEqual(len(variation["description"]), 80)  # explains how it runs
                for variation in data["variations"]:
                    SimConfig.from_dict(resolve_scenario(data, variation["id"]))  # every version runs

    def test_office_lunch_has_a_down_rush_and_a_balanced_version(self):
        data = json.loads(Path(LUNCH).read_text())
        self.assertEqual([v["id"] for v in data["variations"]], ["rush_down", "balanced"])
        self.assertEqual(data["default_variation"], "rush_down")
        self.assertEqual(SimConfig.from_file(LUNCH).traffic["outgoing"], 0.65)
        self.assertEqual(SimConfig.from_file(LUNCH, variation="balanced").traffic["outgoing"], 0.40)
        self.assertEqual(SimConfig.from_file(LUNCH, variation="balanced").arrival_rate, 25)  # inherited


class ViewerPresetTests(unittest.TestCase):
    def test_presets_list_the_enabled_versions_with_merged_settings(self):
        presets = {p["id"]: p for p in _presets()}
        lunch = presets["office_lunch"]
        self.assertEqual([v["id"] for v in lunch["variations"]], ["rush_down", "balanced"])
        self.assertEqual(lunch["default_variation"], "rush_down")
        self.assertEqual(lunch["config"]["traffic"]["outgoing"], 0.65)  # the default version
        self.assertEqual(lunch["variations"][1]["config"]["traffic"]["outgoing"], 0.40)
        self.assertEqual(lunch["variations"][1]["config"]["floors"], lunch["config"]["floors"])
        self.assertEqual(lunch["variations"][0]["name"], "Rush down")
        for preset in presets.values():
            self.assertNotIn("variations", preset["config"])
            self.assertNotIn("default_variation", preset["config"])
        self.assertEqual(len(presets["office_morning"]["variations"]), 1)

    def test_disabled_versions_are_not_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.json"
            path.write_text(json.dumps(scenario(enabled_variations=["b"], default_variation="b")))
            self.assertEqual([v["id"] for v in scenario_variations(json.loads(path.read_text()))], ["b"])

    def test_page_has_the_variation_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "viewer.html"
            build_viewer(str(out), demo=False)
            page = out.read_text()
        self.assertIn('id="variation"', page)
        self.assertIn('id="mix_incoming"', page)
        self.assertIn('value="mix"', page)


class CliVariationTests(unittest.TestCase):
    def _run(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main(list(argv))
        return out.getvalue()

    def test_variation_flag_picks_a_version(self):
        self.assertIn("mix 15/65/20", self._run("run", "-s", "collective", "--config", LUNCH, "--passengers", "40"))
        text = self._run("run", "-s", "collective", "--config", LUNCH, "--variation", "balanced", "--passengers", "40")
        self.assertIn("mix 40/40/20", text)

    def test_variation_errors_are_clear(self):
        for argv in (
            ("run", "--variation", "balanced"),  # no scenario file to take it from
            ("run", "--config", LUNCH, "--variation", "zzz"),
        ):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as cm:
                main(list(argv))
            self.assertIn("variation", str(cm.exception.code))


if __name__ == "__main__":
    unittest.main()
