"""Shared helper: a valid office_day config built from the shipped scenario file.

The office-day numbers live in scenarios/office_day.json (not in the code), so the tests
take them from there too.
"""
import json
from pathlib import Path

from elevsim.config import resolve_scenario

SCENARIO_FILE = Path(__file__).resolve().parent.parent / "scenarios" / "office_day.json"


def office_data(**overrides) -> dict:
    """The default version of the shipped office_day scenario as a config dict.

    Keyword arguments override top-level settings; an ``office`` dict is merged into the file's
    office block (anything else given for ``office`` replaces it, for testing bad input).
    """
    data = resolve_scenario(json.loads(SCENARIO_FILE.read_text()))
    given = overrides.pop("office", {})
    office = {**data["office"], **given} if isinstance(given, dict) else given
    return {**data, **overrides, "office": office}
