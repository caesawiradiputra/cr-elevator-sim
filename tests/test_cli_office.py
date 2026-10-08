import contextlib
import io
import unittest
from pathlib import Path

from elevsim.cli import main

SCENARIO = str(Path(__file__).resolve().parent.parent / "scenarios" / "office_day.json")


def run_cli(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        main(list(argv))
    return out.getvalue()


class CliOfficeTests(unittest.TestCase):
    def test_run_prints_energy_and_headcount(self):
        text = run_cli("run", "-s", "eta", "--config", SCENARIO, "--employees", "20")
        self.assertIn("Energy use (estimate)", text)
        self.assertIn("20 employees", text)
        self.assertIn("trips", text)

    def test_compare_table_has_an_energy_column(self):
        text = run_cli("compare", "--config", SCENARIO, "--employees", "20", "--seeds", "2",
                       "--strategies", "collective,eta")
        self.assertIn("kWh", text)
        self.assertIn("20 employees", text)

    def test_passengers_flag_is_rejected_for_office_day(self):
        for argv in (
            ("run", "--config", SCENARIO, "--passengers", "100"),
            ("run", "--traffic", "office_day", "--passengers", "100"),
        ):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as cm:
                main(list(argv))
            self.assertIn("--employees", str(cm.exception.code))

    def test_office_day_needs_the_scenario_file(self):
        with self.assertRaises(SystemExit) as cm:
            main(["run", "-s", "collective", "--traffic", "office_day", "--employees", "10"])
        self.assertIn("scenarios/office_day.json", str(cm.exception.code))
        text = run_cli("run", "-s", "collective", "--config", SCENARIO, "--traffic", "office_day", "--employees", "10")
        self.assertIn("10 employees", text)

    def test_existing_output_keeps_its_shape(self):
        text = run_cli("run", "-s", "collective", "--passengers", "40")
        self.assertIn("40 passengers (uniform, 20.0/min, seed 1)", text)


if __name__ == "__main__":
    unittest.main()
