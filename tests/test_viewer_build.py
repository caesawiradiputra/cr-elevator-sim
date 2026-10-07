import json
import tempfile
import unittest
from pathlib import Path

from elevsim.viewer_build import NO_PRECOMPUTE, _presets, build_viewer, precompute_ids


class ViewerBuildTests(unittest.TestCase):
    def test_office_day_is_a_preset(self):
        presets = {p["id"]: p for p in _presets()}
        self.assertEqual(presets["office_day"]["config"]["traffic"], "office_day")
        json.dumps(presets["office_day"])

    def test_office_day_is_never_precomputed(self):
        presets = _presets()
        self.assertIn("office_day", NO_PRECOMPUTE)
        self.assertNotIn("office_day", precompute_ids(presets, demo_all=True))
        self.assertIn("office_lunch", precompute_ids(presets, demo_all=True))
        self.assertEqual(precompute_ids(presets, demo_all=False), ["office_lunch"])

    def test_page_has_the_new_controls_and_bundles_the_new_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "viewer.html"
            build_viewer(str(out), demo=False)
            page = out.read_text()
        self.assertIn('id="employees"', page)
        self.assertIn('value="office_day"', page)
        self.assertIn('value="600"', page)
        self.assertIn("elevsim/schedule.py", page)
        self.assertIn("elevsim/energy.py", page)


if __name__ == "__main__":
    unittest.main()
