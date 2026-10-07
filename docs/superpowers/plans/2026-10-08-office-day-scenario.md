# Office-Day Scenario and Energy Metric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic full-day office scenario (`traffic: "office_day"`) with a fixed headcount of employees, and an energy metric (`energy_kwh`) so algorithms can be compared on effectiveness as well as waiting time.

**Architecture:** A new scheduler (`elevsim/schedule.py`) turns employees into timed trips and flattens them into the existing `Passenger` list, so the engine and all five strategies are unchanged for traffic. The engine gains one raw counter (`loaded_floor_distance`) and resolves its stop time from the passengers it is given; a replaceable `EnergyModel` (`elevsim/energy.py`) turns the counters into kWh at summary time. The CLI and the browser viewer are extended to select the scenario and show the metric.

**Tech Stack:** Python standard library only (3.10, 3.12, 3.13; importable under Pyodide), `unittest`, plain HTML/JS viewer, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-08-office-day-scenario-design.md` (approved v5, section 3.2 amended: fast-forward is **not** part of this plan). Read it before starting.

**Branch:** work continues on `feat/office-day-scenario` (already created from `dev`; it holds the spec, this plan, `CHANGELOG.md` and `docs/ideas.md`). Do not commit to `dev` or `main` directly.

## Global Constraints

- **Standard library only.** No third-party runtime dependencies. The engine must stay importable under Pyodide and on Python 3.10, 3.12 and 3.13 (the CI matrix).
- No `pyproject.toml`, ruff or mypy config exists. Do not assume `uv run` tooling. Run tests with `python3 -m unittest discover -s tests -t .`.
- **Deterministic and fair:** passengers are generated from the config and seed only, never from the strategy, so every algorithm sees identical traffic.
- Strategies are registered in `elevsim/strategies/__init__.py`; nothing else hardcodes algorithm names.
- `dist/` and `results/` are generated and gitignored.
- Version: `elevsim.__version__` is the single source of truth. Current `0.1.0`, target `0.2.0` (minor, new feature). The bump and the `CHANGELOG.md` entry happen in the last commit of this branch (Task 8), not earlier.
- Commits: Conventional Commits with gitmoji. End every commit message with the two trailer lines shown in the commit steps.
- Markdown style: code fences always have a language (use `text` for plain text), table separators have spaces (`| --- | --- |`), no bare fences.
- `office_day` rules fixed by the spec: `day_start` default `06:45`, `day_end` default `20:00`; default `min_trip_gap_s` 600; drain margin 3600 s; `max_time` default becomes `None` (auto); `cfg.passengers` is ignored for `office_day` and the config is never mutated; the trace cap applies to `office_day` only and is at most 10,000 frames including the initial and final frame.
- `energy_kwh` is a **comparative estimate** in 0.2.0 (uncalibrated constants). Say so in the README and config comments.

## Deviations from the spec (decided while planning, tell the user)

1. **Fast-forward dropped.** A prototype run on the unmodified engine took 0.7-1.1 s per full-day run (300 employees, all five strategies). The spec allowed dropping it. Spec section 3.2 was amended.
2. **`office` dict.** The shares, windows, rates and durations live in one dict key `office` (defaults in `OFFICE_DEFAULTS`), not about 25 flat keys. Spec section 3.4 was amended.
3. **Frame cap divisor 9997 and `office_day` only.** The spec's `max_time / 9998` on the 4-hour legacy default would widen the frames of every existing scenario, contradicting its own "existing scenarios unchanged" test. Spec section 3.5 was amended.
4. **Scheduling bound.** Optional round trips must lie inside `[arrival + gap, go_home - gap]`; the prototype and spec text only checked overlaps, which would let a custom config schedule a meeting before arrival or after going home.

## Measured baseline (prototype, 2026-10-08; use to sanity-check your implementation)

- 300 employees, 15 floors, 4 cars, capacity 10, seed 1: about 1,800 trips (about 6.1 per person), last request at about 47,670 s after `day_start`.
- Meeting candidates placed about 77-78% of the time, break candidates about 69-78%.
- Every strategy served every trip; the share of consecutive trip pairs where the next request comes before the previous drop-off was 0% for all five strategies (seeds 1, 2, 3, 7 for `collective` and `eta`).
- A full-day run took 0.7-1.1 s natively. Pyodide speed is not yet measured (Task 7 measures it).
- Edge cases that worked: `floors=2, employees=3`; `floors=3, employees=1`; `floors=8, lobby_floor=3, employees=20`.

## Review Focus

Inputs the spec implies but a normal happy-path test would miss, most likely first. Each line has a test in the named task.

- **Tiny buildings and headcounts** (`floors=2`, `floors=3 employees=1`, `employees=3`): no other floor for meetings must mean no meetings, not a crash; everyone still gets in, has lunch and goes home. Task 4 `test_tiny_buildings`.
- **`lobby_floor` other than 0** (for example 3 of 8 floors): desks never sit on the lobby, trips end at the lobby, nothing hardcodes floor 0. Task 4 `test_tiny_buildings` (third case) and `test_origin_weights_*`.
- **Extreme `day_variation` and lunch shares that sum to 1:** shares must stay inside 0-1 and `lunch_out + lunch_cafe` must never exceed 1. Task 4 `test_variation_clamps_shares`.
- **Explicit `max_time` too small, and `compare()` over several seeds:** an explicit value is never overridden (clear `ValueError`), and each seed resolves its own horizon without mutating the config. Task 2 `HorizonTests`, Task 4 `test_explicit_max_time_too_small` and `test_compare_over_seeds`.
- **`--passengers` with `office_day`, unknown `office` keys, bad `HH:MM` strings:** must fail with a clear message, never be silently ignored. Task 1 `test_bad_values_are_rejected`, Task 6 `test_passengers_flag_is_rejected_for_office_day`.

## File Structure

| File | Action | Responsibility |
| --- | --- | --- |
| `elevsim/config.py` | modify | new keys, `max_time=None`, `office_day` registration, `parse_hhmm`, `OFFICE_DEFAULTS`, validation |
| `elevsim/engine.py` | modify | `horizon` resolution, `loaded_floor_distance` counting, frame cap |
| `elevsim/model.py` | modify | `Elevator.loaded_floor_distance` |
| `elevsim/energy.py` | create | `EnergyModel`, `SimpleEnergy`, `get_energy_model` |
| `elevsim/metrics.py` | modify | `energy_kwh` metric, `passengers_total`, `horizon`, per-car energy |
| `elevsim/schedule.py` | create | `Employee`, `Trip`, `OfficeDay`, `generate_office_day`, `office_day_passengers` |
| `elevsim/passengers.py` | modify | dispatch `office_day` to the scheduler |
| `elevsim/api.py` | modify | report the effective frame interval |
| `elevsim/cli.py` | modify | `--traffic office_day`, `--employees`, energy column, headers |
| `elevsim/viewer_build.py` | modify | `NO_PRECOMPUTE`, `precompute_ids` |
| `viewer/index.html`, `viewer/app.js`, `viewer/style.css` | modify | scenario option, employees field, energy rows, HH:MM clock, faster speeds |
| `scenarios/office_day.json` | create | the preset |
| `tests/test_office_config.py` | create | config and horizon tests |
| `tests/test_energy.py` | create | counters, models, metric |
| `tests/test_office_day.py` | create | scheduler, integration, ordering, frame cap |
| `tests/test_cli_office.py` | create | CLI behavior |
| `tests/test_viewer_build.py` | create | viewer build helpers and page contents |
| `README.md`, `CHANGELOG.md`, `CLAUDE.md`, `docs/code-map.md`, `docs/ideas.md`, `.github/workflows/tests.yml`, `elevsim/__init__.py` | modify/create | docs, version, CI smoke test |

Run all commands from `/home/patst/repo/cr-elevator-sim/cr-elevator-sim`. Baseline before starting: `python3 -m unittest discover -s tests -t .` must pass.

---

### Task 1: Config keys and `office_day` registration

**Files:**
- Modify: `elevsim/config.py`
- Create: `tests/test_office_config.py`

**Interfaces:**
- Consumes: nothing new.
- Produces (later tasks rely on these exact names):
  - `config.DEFAULT_MAX_TIME: float` (14400.0), `config.SCHEDULED_TRAFFIC: tuple[str, ...]` (`("office_day",)`), `config.ENERGY_MODELS: tuple[str, ...]` (`("simple",)`), `config.OFFICE_DEFAULTS: dict`
  - `config.parse_hhmm(text: str) -> int` (seconds since midnight, `ValueError` on bad input)
  - `SimConfig` fields: `max_time: float | None = None`, `employees: int = 300`, `day_start: str = "06:45"`, `day_end: str = "20:00"`, `day_variation: float = 1.0`, `office: dict`, `energy_model: str = "simple"`, `energy_base: float = 0.01`, `energy_per_passenger: float = 0.002`
  - `SimConfig.office_settings() -> dict` (defaults merged with the `office` overrides)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_office_config.py`:

```python
import unittest

from elevsim import SimConfig
from elevsim.config import OFFICE_DEFAULTS, SCHEDULED_TRAFFIC, parse_hhmm


class OfficeConfigTests(unittest.TestCase):
    def test_defaults(self):
        cfg = SimConfig().validate()
        self.assertIsNone(cfg.max_time)
        self.assertEqual(cfg.employees, 300)
        self.assertEqual((cfg.day_start, cfg.day_end), ("06:45", "20:00"))
        self.assertEqual(cfg.office_settings(), OFFICE_DEFAULTS)
        self.assertEqual(cfg.energy_model, "simple")

    def test_office_day_is_valid_traffic(self):
        self.assertEqual(SCHEDULED_TRAFFIC, ("office_day",))
        SimConfig(traffic="office_day").validate()
        with self.assertRaises(ValueError) as cm:
            SimConfig(traffic="rush").validate()
        self.assertIn("office_day", str(cm.exception))

    def test_office_overrides_merge_over_defaults(self):
        cfg = SimConfig(traffic="office_day", office={"late_share": 0.3}).validate()
        self.assertEqual(cfg.office_settings()["late_share"], 0.3)
        self.assertEqual(cfg.office_settings()["late_end"], "09:30")

    def test_round_trip_keeps_max_time_auto(self):
        data = SimConfig(traffic="office_day").to_dict()
        self.assertIsNone(data["max_time"])
        self.assertIsNone(SimConfig.from_dict(data).max_time)

    def test_bad_values_are_rejected(self):
        bad = [
            {"office": {"nonsense": 1}},
            {"energy_model": "magic"},
            {"energy_base": -1.0},
            {"energy_per_passenger": -0.1},
            {"max_time": 0},
            {"traffic": "office_day", "employees": 0},
            {"traffic": "office_day", "day_variation": -0.1},
            {"traffic": "office_day", "day_start": "7am"},
            {"traffic": "office_day", "day_start": "25:00"},
            {"traffic": "office_day", "day_start": "21:00"},  # after day_end
            {"traffic": "office_day", "day_end": "17:30"},  # before the home window ends
            {"traffic": "office_day", "office": {"late_share": 1.5}},
            {"traffic": "office_day", "office": {"lunch_out_share": 0.8, "lunch_cafe_share": 0.4}},
            {"traffic": "office_day", "office": {"home_window": ["17:45", "17:00"]}},
            {"traffic": "office_day", "office": {"break_min": [5, 20]}},  # shorter than min_trip_gap_s
            {"traffic": "office_day", "office": {"min_trip_gap_s": 0}},
            {"traffic": "office_day", "office": {"arrival_peak": "09:00"}},  # outside arrival_window
        ]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(ValueError):
                SimConfig.from_dict(data)

    def test_parse_hhmm(self):
        self.assertEqual(parse_hhmm("06:45"), 6 * 3600 + 45 * 60)
        self.assertEqual(parse_hhmm("00:00"), 0)
        for text in ("nine", "24:00", "12:60", "", None):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_hhmm(text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_office_config -v`
Expected: FAIL / ERROR with `ImportError: cannot import name 'OFFICE_DEFAULTS' from 'elevsim.config'`.

- [ ] **Step 3: Patch `elevsim/config.py`**

Run this patch script (it fails loudly if an anchor is not found exactly once):

```bash
python3 - <<'PYEOF'
p = "elevsim/config.py"
s = open(p).read()

def rep(old, new):
    global s
    assert s.count(old) == 1, "anchor not found exactly once: " + old[:60]
    s = s.replace(old, new, 1)

# 1. constants, placed before the traffic-pattern comment
rep("# Named traffic mixes: share of passengers that are incoming (lobby -> upper\n",
'''DEFAULT_MAX_TIME = 4 * 3600.0  # hard stop used when max_time is None and the traffic is not scheduled
SCHEDULED_TRAFFIC = ("office_day",)  # traffic built by a scheduler (elevsim/schedule.py), not a mix below
ENERGY_MODELS = ("simple",)  # names known to elevsim/energy.py

# Defaults for traffic="office_day". Times are "HH:MM", durations are minutes, the
# rest are shares (0-1), rates per person or seconds. Override any of them with the
# `office` config key; unknown keys are rejected. These are placeholders, not real
# office statistics.
OFFICE_DEFAULTS = {
    "arrival_window": ["07:00", "08:00"],  # on-time arrivals, triangular
    "arrival_peak": "07:50",  # most likely arrival time inside the window
    "late_share": 0.15,  # share who arrive late, between the window end and late_end
    "late_end": "09:30",
    "lunch_center": "12:00",  # lunch departures spread around this time
    "lunch_spread_min": 30,  # +/- minutes
    "lunch_out_share": 0.40,  # leave the building (desk -> lobby -> desk)
    "lunch_cafe_share": 0.30,  # cafeteria on the lobby floor only; the rest eat at the desk
    "lunch_out_min": [30, 60],  # time away
    "lunch_cafe_min": [15, 40],
    "work_window": ["09:00", "17:00"],  # meetings and breaks start inside this window
    "meetings_per_person": 1.0,  # candidate rate; some are dropped when they overlap
    "breaks_per_person": 0.7,
    "meeting_min": [30, 60],
    "break_min": [10, 20],
    "home_window": ["17:00", "17:45"],  # most leave here; stay-late people leave until day_end
    "stay_late_share": 0.20,
    "min_trip_gap_s": 600,  # minimum seconds between one person's consecutive requests
    "drain_margin_s": 3600,  # time after the last request that the simulation may run
}

# Named traffic mixes: share of passengers that are incoming (lobby -> upper
''')

# 2. parse_hhmm before the dataclass
rep("@dataclass\nclass SimConfig:\n",
'''def parse_hhmm(text: str) -> int:
    """Seconds since midnight for an "HH:MM" string; ValueError for anything else."""
    try:
        hours, minutes = text.split(":")
        h, m = int(hours), int(minutes)
    except (AttributeError, ValueError):
        raise ValueError(f"time must look like HH:MM, got {text!r}") from None
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f"time must look like HH:MM between 00:00 and 23:59, got {text!r}")
    return h * 3600 + m * 60


@dataclass
class SimConfig:
''')

# 3. max_time becomes auto
rep("    max_time: float = 4 * 3600.0  # hard stop\n",
    "    max_time: float | None = None  # hard stop in seconds; None = auto (4 h, or last office_day request + margin)\n")

# 4. new fields, placed before `extra`
rep("    extra: dict = field(default_factory=dict)  # free-form, passed to strategies\n",
'''    # Office-day scenario (traffic="office_day"); `passengers` and `arrival_rate` do not apply to it
    employees: int = 300  # fixed headcount; each has a fixed desk floor
    day_start: str = "06:45"  # simulation time 0, as HH:MM
    day_end: str = "20:00"  # latest time any request may be generated
    day_variation: float = 1.0  # 0 = day-level shares exactly as configured, 1 = default spread
    office: dict = field(default_factory=dict)  # overrides for OFFICE_DEFAULTS

    # Energy (see elevsim/energy.py). The simple model's constants are uncalibrated, so
    # energy_kwh is a comparative estimate for ranking algorithms, not an absolute figure.
    energy_model: str = "simple"
    energy_base: float = 0.01  # kWh per floor a car moves, empty
    energy_per_passenger: float = 0.002  # extra kWh per passenger per floor moved

    extra: dict = field(default_factory=dict)  # free-form, passed to strategies
''')

# 5. traffic validation
rep('''        if isinstance(self.traffic, str) and self.traffic not in TRAFFIC_PATTERNS:
            raise ValueError(f"unknown traffic pattern {self.traffic!r}; choose from {sorted(TRAFFIC_PATTERNS)}")
''', '''        if isinstance(self.traffic, str) and self.traffic not in TRAFFIC_PATTERNS and self.traffic not in SCHEDULED_TRAFFIC:
            raise ValueError(
                f"unknown traffic pattern {self.traffic!r}; choose from {sorted([*TRAFFIC_PATTERNS, *SCHEDULED_TRAFFIC])}"
            )
''')

# 6. tail of validate + new methods
rep('''        if self.idle_parking not in ("stay", "lobby"):
            raise ValueError("idle_parking must be 'stay' or 'lobby'")
        return self
''', '''        if self.idle_parking not in ("stay", "lobby"):
            raise ValueError("idle_parking must be 'stay' or 'lobby'")
        if self.max_time is not None and self.max_time <= 0:
            raise ValueError("max_time must be > 0 (or null for auto)")
        if self.energy_model not in ENERGY_MODELS:
            raise ValueError(f"unknown energy_model {self.energy_model!r}; choose from {list(ENERGY_MODELS)}")
        if self.energy_base < 0 or self.energy_per_passenger < 0:
            raise ValueError("energy_base and energy_per_passenger must be >= 0")
        unknown = set(self.office) - set(OFFICE_DEFAULTS)
        if unknown:
            raise ValueError(f"unknown office keys: {sorted(unknown)}")
        if self.traffic == "office_day":
            self._validate_office_day()
        return self

    def office_settings(self) -> dict:
        """OFFICE_DEFAULTS with the `office` overrides applied."""
        return {**OFFICE_DEFAULTS, **self.office}

    def _validate_office_day(self) -> None:
        if self.employees < 1:
            raise ValueError("employees must be >= 1")
        if self.day_variation < 0:
            raise ValueError("day_variation must be >= 0")
        o = self.office_settings()
        for name in ("late_share", "lunch_out_share", "lunch_cafe_share", "stay_late_share"):
            if not 0.0 <= o[name] <= 1.0:
                raise ValueError(f"office.{name} must be between 0 and 1")
        if o["lunch_out_share"] + o["lunch_cafe_share"] > 1.0:
            raise ValueError("office.lunch_out_share + office.lunch_cafe_share must not exceed 1")
        for name in ("meetings_per_person", "breaks_per_person", "drain_margin_s", "lunch_spread_min"):
            if o[name] < 0:
                raise ValueError(f"office.{name} must be >= 0")
        gap = o["min_trip_gap_s"]
        if gap <= 0:
            raise ValueError("office.min_trip_gap_s must be > 0")
        for name in ("lunch_out_min", "lunch_cafe_min", "meeting_min", "break_min"):
            low, high = o[name]
            if not low <= high or low * 60 < gap:
                raise ValueError(
                    f"office.{name} must be [low, high] minutes with low <= high and low x 60 >= min_trip_gap_s"
                )
        start, end = parse_hhmm(self.day_start), parse_hhmm(self.day_end)
        a0, a1 = (parse_hhmm(t) for t in o["arrival_window"])
        peak, late_end = parse_hhmm(o["arrival_peak"]), parse_hhmm(o["late_end"])
        w0, w1 = (parse_hhmm(t) for t in o["work_window"])
        h0, h1 = (parse_hhmm(t) for t in o["home_window"])
        lunch, spread = parse_hhmm(o["lunch_center"]), o["lunch_spread_min"] * 60
        longest_lunch = max(o["lunch_out_min"][1], o["lunch_cafe_min"][1]) * 60
        longest_optional = max(o["meeting_min"][1], o["break_min"][1]) * 60
        checks = [
            (start <= a0 < a1 <= late_end < h0 < h1 <= end,
             "times must be in order: day_start <= arrival_window < late_end < home_window <= day_end"),
            (a0 <= peak <= a1, "office.arrival_peak must lie inside office.arrival_window"),
            (w0 < w1, "office.work_window must be in order"),
            (w0 <= lunch - spread and lunch + spread + longest_lunch <= w1,
             "lunch (centre +/- spread, plus the longest lunch) must fit inside office.work_window"),
            (w1 + longest_optional <= end, "day_end must leave room for the longest meeting or break after work_window"),
        ]
        for ok, message in checks:
            if not ok:
                raise ValueError(message)
''')
open(p, "w").write(s)
PYEOF
```

- [ ] **Step 4: Run the new tests and the whole suite**

Run: `python3 -m unittest tests.test_office_config -v && python3 -m unittest discover -s tests -t .`
Expected: all `test_office_config` tests PASS and the existing suite still PASSES (`max_time` is only read in `engine.py`, which Task 2 changes; until then `self.cfg.max_time - EPS` would fail on `None`, so **run Task 2 immediately** — if the existing suite fails with `TypeError: unsupported operand type(s) for -: 'NoneType' and 'float'`, that is expected here and fixed in Task 2 Step 3).

- [ ] **Step 5: Commit (together with Task 2 if the suite is red)**

If the existing suite is red only because of the `max_time` `TypeError`, skip this commit and commit after Task 2 Step 5 using the combined message there. Otherwise:

```bash
git add elevsim/config.py tests/test_office_config.py
git commit -m "$(cat <<'EOF'
✨ feat(config): add office_day keys, energy keys and auto max_time

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VLPdWXWxBs7xJ8CVRrQMXM
EOF
)"
```

---

### Task 2: Resolve the simulation horizon from the passengers

**Files:**
- Modify: `elevsim/engine.py`, `elevsim/metrics.py`
- Modify (append class): `tests/test_office_config.py`

**Interfaces:**
- Consumes: `config.DEFAULT_MAX_TIME`, `SimConfig.max_time`, `SimConfig.office_settings()["drain_margin_s"]`.
- Produces: `Simulation.horizon: float` (stop time in seconds, resolved in `__init__`); summary keys `passengers_total: int` and `horizon: float`; `Simulation._resolve_horizon()` raising `ValueError` for an explicit `max_time` that is too small for `office_day`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_office_config.py` (and add the imports shown at the top of the snippet to the file's import block in the same edit):

```python
from elevsim import Simulation
from elevsim.metrics import summarize
from elevsim.model import Passenger
from elevsim.strategies import get_strategy


class HorizonTests(unittest.TestCase):
    def _sim(self, cfg, arrival=1000.0):
        person = Passenger(id=0, arrival=arrival, origin=0, dest=1)
        return Simulation(cfg, get_strategy("collective"), passengers=[person])

    def test_legacy_default_is_four_hours(self):
        self.assertEqual(self._sim(SimConfig(floors=3)).horizon, 4 * 3600.0)

    def test_legacy_explicit_max_time_is_kept(self):
        self.assertEqual(self._sim(SimConfig(floors=3, max_time=5000.0)).horizon, 5000.0)

    def test_office_day_auto_is_last_arrival_plus_margin(self):
        self.assertEqual(self._sim(SimConfig(floors=3, traffic="office_day")).horizon, 1000.0 + 3600.0)

    def test_office_day_margin_is_configurable(self):
        cfg = SimConfig(floors=3, traffic="office_day", office={"drain_margin_s": 100})
        self.assertEqual(self._sim(cfg).horizon, 1100.0)

    def test_explicit_max_time_is_never_overridden(self):
        cfg = SimConfig(floors=3, traffic="office_day", max_time=9000.0)
        self.assertEqual(self._sim(cfg).horizon, 9000.0)

    def test_explicit_max_time_too_small_raises(self):
        cfg = SimConfig(floors=3, traffic="office_day", max_time=1000.0)
        with self.assertRaises(ValueError) as cm:
            self._sim(cfg)
        self.assertIn("1000", str(cm.exception))
        self.assertIn("4600", str(cm.exception))

    def test_config_is_not_mutated_and_summary_reports_the_horizon(self):
        cfg = SimConfig(floors=3, traffic="office_day")
        sim = self._sim(cfg).run()
        self.assertIsNone(cfg.max_time)
        summary = summarize(sim)
        self.assertEqual(summary["passengers_total"], 1)
        self.assertEqual(summary["horizon"], 4600.0)
        self.assertEqual(summary["served"], 1)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_office_config.HorizonTests -v`
Expected: FAIL / ERROR (`AttributeError: 'Simulation' object has no attribute 'horizon'`, or the `NoneType` `TypeError` from the run loop).

- [ ] **Step 3: Patch `elevsim/engine.py` and `elevsim/metrics.py`**

Apply all edits in one script so the new import and its usage land together:

```bash
python3 - <<'PYEOF'
def patch(path, edits):
    s = open(path).read()
    for old, new in edits:
        assert s.count(old) == 1, path + ": anchor not found exactly once: " + old[:60]
        s = s.replace(old, new, 1)
    open(path, "w").write(s)

patch("elevsim/engine.py", [
    ("from .config import SimConfig\n", "from .config import DEFAULT_MAX_TIME, SimConfig\n"),
    ("        self.passengers = passengers if passengers is not None else generate_passengers(cfg)\n",
     "        self.passengers = passengers if passengers is not None else generate_passengers(cfg)\n"
     "        self.horizon = self._resolve_horizon()\n"),
    ("    def finished(self) -> bool:\n        return not self._pending and self.delivered == len(self.passengers)\n",
     '''    def finished(self) -> bool:
        return not self._pending and self.delivered == len(self.passengers)

    def _resolve_horizon(self) -> float:
        """Stop time in seconds: an explicit max_time, else 4 hours (office_day: last request + margin).

        Resolved here, from the passengers actually given, because every path (CLI, compare, viewer,
        tests) goes through Simulation; the config is never changed, so a copy made for another seed
        resolves its own horizon.
        """
        cfg = self.cfg
        if cfg.traffic != "office_day":
            return DEFAULT_MAX_TIME if cfg.max_time is None else cfg.max_time
        last = max((p.arrival for p in self.passengers), default=0.0)
        needed = last + float(cfg.office_settings()["drain_margin_s"])
        if cfg.max_time is None:
            return needed
        if cfg.max_time < needed:
            raise ValueError(
                f"max_time {cfg.max_time:g} s is shorter than the {needed:g} s this office_day needs "
                f"(last request at {last:g} s plus a {needed - last:g} s margin)"
            )
        return cfg.max_time
'''),
    ("        while not self.finished() and self.t < self.cfg.max_time - EPS:\n",
     "        while not self.finished() and self.t < self.horizon - EPS:\n"),
])

patch("elevsim/metrics.py", [
    ('        "left_behind": sim.left_behind_events,\n    }\n    out = {k: round(v, 3)',
     '        "left_behind": sim.left_behind_events,\n        "passengers_total": len(ps),\n        "horizon": sim.horizon,\n    }\n    out = {k: round(v, 3)'),
])
PYEOF
```

- [ ] **Step 4: Run the new tests and the whole suite**

Run: `python3 -m unittest tests.test_office_config -v && python3 -m unittest discover -s tests -t .`
Expected: all PASS (the existing suite included).

- [ ] **Step 5: Commit (Tasks 1 and 2 together if Task 1 was left uncommitted)**

```bash
git add elevsim/config.py elevsim/engine.py elevsim/metrics.py tests/test_office_config.py
git commit -m "$(cat <<'EOF'
✨ feat(engine): resolve the simulation horizon from the passengers

max_time becomes None (auto): 4 hours for existing traffic, last office_day
request plus a drain margin otherwise. The config is never mutated, so compare()
resolves a horizon per seed.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VLPdWXWxBs7xJ8CVRrQMXM
EOF
)"
```

---

### Task 3: Energy counters, `EnergyModel` and the `energy_kwh` metric

**Files:**
- Create: `elevsim/energy.py`, `tests/test_energy.py`
- Modify: `elevsim/model.py`, `elevsim/engine.py`, `elevsim/metrics.py`

**Interfaces:**
- Consumes: `SimConfig.energy_model`, `energy_base`, `energy_per_passenger`; `Elevator.floors_travelled`.
- Produces: `Elevator.loaded_floor_distance: int`; `energy.MODELS: dict[str, type[EnergyModel]]`; `energy.get_energy_model(cfg) -> EnergyModel` with `EnergyModel.car_energy_kwh(car) -> float`; `METRICS["energy_kwh"] == ("Energy use (estimate)", "kWh", True)`; summary keys `energy_kwh`, `energy_per_passenger` (0.0 when nobody was served) and per-elevator `loaded_floor_distance`, `energy_kwh`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_energy.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_energy -v`
Expected: ERROR with `ModuleNotFoundError: No module named 'elevsim.energy'`.

- [ ] **Step 3: Create `elevsim/energy.py`**

```python
"""Energy models: turn the raw counters the engine records for each car into kWh.

The engine only counts facts (``Elevator.floors_travelled``, ``loaded_floor_distance``,
``time_in_state``). A model decides what they cost. To add a model, subclass
``EnergyModel``, register it in ``MODELS`` and add its name to ``ENERGY_MODELS`` in
``config.py``; the engine does not change.

The ``simple`` constants are uncalibrated, so ``energy_kwh`` is a comparative estimate
for ranking algorithms against each other, not an absolute figure.
"""
from __future__ import annotations


class EnergyModel:
    name = "base"

    def __init__(self, cfg):
        self.cfg = cfg

    def car_energy_kwh(self, car) -> float:
        raise NotImplementedError


class SimpleEnergy(EnergyModel):
    """Movement energy only: a cost per floor moved plus a cost per passenger per floor.

    Idle time and door-open time are collected by the engine but do not count here.
    """

    name = "simple"

    def car_energy_kwh(self, car) -> float:
        return (
            car.floors_travelled * self.cfg.energy_base
            + car.loaded_floor_distance * self.cfg.energy_per_passenger
        )


MODELS = {SimpleEnergy.name: SimpleEnergy}


def get_energy_model(cfg) -> EnergyModel:
    name = getattr(cfg, "energy_model", None)
    try:
        return MODELS[name](cfg)
    except KeyError:
        raise ValueError(f"unknown energy_model {name!r}; choose from {sorted(MODELS)}") from None
```

- [ ] **Step 4: Patch `model.py`, `engine.py` and `metrics.py`**

```bash
python3 - <<'PYEOF'
def patch(path, edits):
    s = open(path).read()
    for old, new in edits:
        assert s.count(old) == 1, path + ": anchor not found exactly once: " + old[:60]
        s = s.replace(old, new, 1)
    open(path, "w").write(s)

patch("elevsim/model.py", [
    ("    floors_travelled: int = 0\n",
     "    floors_travelled: int = 0\n"
     "    loaded_floor_distance: int = 0  # passengers on board, summed over every floor transition\n"),
])

patch("elevsim/engine.py", [
    ("                e.floor += e.direction\n                e.floors_travelled += 1\n",
     "                e.floor += e.direction\n                e.floors_travelled += 1\n"
     "                e.loaded_floor_distance += e.load  # load only changes while stopped\n"),
])

patch("elevsim/metrics.py", [
    ("import statistics\n\n\ndef _pct", "import statistics\n\nfrom .energy import get_energy_model\n\n\ndef _pct"),
    ('    "floors_travelled": ("Floors travelled (total)", "", True),\n',
     '    "floors_travelled": ("Floors travelled (total)", "", True),\n'
     '    "energy_kwh": ("Energy use (estimate)", "kWh", True),\n'),
    ('    idle = sum(e.time_in_state["idle"] for e in sim.elevators)\n    out = {\n',
     '    idle = sum(e.time_in_state["idle"] for e in sim.elevators)\n'
     '    energy_model = get_energy_model(cfg)\n'
     '    energy = sum(energy_model.car_energy_kwh(e) for e in sim.elevators)\n'
     '    out = {\n'),
    ('        "floors_travelled": sum(e.floors_travelled for e in sim.elevators),\n',
     '        "floors_travelled": sum(e.floors_travelled for e in sim.elevators),\n'
     '        "energy_kwh": energy,\n'
     '        "energy_per_passenger": energy / len(done) if done else 0.0,\n'),
    ('            "floors_travelled": e.floors_travelled,\n            "stops": e.stops,\n',
     '            "floors_travelled": e.floors_travelled,\n'
     '            "loaded_floor_distance": e.loaded_floor_distance,\n'
     '            "energy_kwh": round(energy_model.car_energy_kwh(e), 4),\n'
     '            "stops": e.stops,\n'),
])
PYEOF
```

- [ ] **Step 5: Run the new tests and the whole suite**

Run: `python3 -m unittest tests.test_energy -v && python3 -m unittest discover -s tests -t .`
Expected: all PASS. If `test_empty_car_adds_floors_but_no_loaded_distance` fails on `floors_travelled`, print the car's counters and confirm the car really travelled up empty before loading (the car starts at the lobby, the rider waits on floor 3); fix the test's expected numbers only after reasoning about the engine, not by loosening to `>= 0`.

- [ ] **Step 6: Commit**

```bash
git add elevsim/energy.py elevsim/model.py elevsim/engine.py elevsim/metrics.py tests/test_energy.py
git commit -m "$(cat <<'EOF'
✨ feat(energy): add loaded-floor counter, EnergyModel and energy_kwh metric

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VLPdWXWxBs7xJ8CVRrQMXM
EOF
)"
```

---

### Task 4: The office-day scheduler

**Files:**
- Create: `elevsim/schedule.py`, `scenarios/office_day.json`, `tests/test_office_day.py`
- Modify: `elevsim/passengers.py`

**Interfaces:**
- Consumes: `SimConfig` (all Task 1 keys, `office_settings()`), `config.parse_hhmm`, `model.Passenger`, `Simulation.horizon` (Task 2).
- Produces:
  - `schedule.Employee(id: int, desk: int)` (frozen dataclass)
  - `schedule.Trip(time: float, employee: int, origin: int, dest: int, passenger_id: int | None)`; `time` is seconds since midnight
  - `schedule.OfficeDay(day_index, profile: dict, employees: list[Employee], trips: dict[int, list[Trip]], stats: dict)` with `.passengers(day_start: float) -> list[Passenger]`
  - `schedule.build_employees(cfg, rng) -> list[Employee]`, `schedule.draw_profile(cfg, o, tm, rng) -> dict`, `schedule.build_day(cfg, employees, rng, day_index=0) -> OfficeDay`
  - `schedule.generate_office_day(cfg) -> tuple[OfficeDay, list[Passenger]]` and `schedule.office_day_passengers(cfg) -> list[Passenger]`
  - `generate_passengers(cfg)` returns the office-day list when `cfg.traffic == "office_day"`
  - `OfficeDay.stats` keys: `lunch_out`, `lunch_cafe`, `lunch_desk`, `meeting_candidates`, `meeting_placed`, `break_candidates`, `break_placed`
  - `OfficeDay.profile` keys: `late_share`, `lunch_out_share`, `lunch_cafe_share`, `stay_late_share`, `arrival_peak` (seconds since midnight)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_office_day.py`:

```python
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
        for seed in (1, 2):
            cfg = office(employees=300, seed=seed)
            for name in ("eta", "collective"):
                with self.subTest(seed=seed, strategy=name):
                    self.assertLessEqual(self._violation_share(cfg, name), 0.01)  # prototype: 0

    def test_share_is_computable_for_every_strategy(self):
        cfg = office(employees=300, seed=1)
        for name in STRATEGIES:
            with self.subTest(strategy=name):
                share = self._violation_share(cfg, name)
                self.assertTrue(0.0 <= share <= 1.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_office_day -v`
Expected: ERROR with `ModuleNotFoundError: No module named 'elevsim.schedule'`.

- [ ] **Step 3: Create `elevsim/schedule.py`**

```python
"""Office-day traffic: a deterministic scheduler for a fixed headcount.

Every employee has a fixed desk floor and a day made of timed segments: arrival,
optional meetings and cafeteria breaks, lunch (out of the building, cafeteria only,
or at the desk) and going home. The day is flattened into the same ``Passenger``
list the engine already consumes, so the engine and every strategy are unchanged
and every algorithm sees identical traffic: the schedule depends on the config and
the seed only, never on the strategy.

Building blocks, so a multi-day week can reuse them later:

* ``Employee``  id and fixed desk floor, created once.
* ``OfficeDay`` one day built from those employees (``day_index`` defaults to 0).
* ``Trip``      one hall-call request; ``Trip.time`` is seconds since midnight.

Rules (see docs/superpowers/specs/2026-10-08-office-day-scenario-design.md):

* Arrival, lunch and going home are placed first and never dropped.
* Meetings and cafeteria breaks are candidates. Each is a whole round trip
  (desk -> away -> desk), kept or dropped as one unit, and must lie inside
  [arrival + gap, go_home - gap] and at least ``min_trip_gap_s`` away from every
  other segment. So the configured meeting and break rates are candidate rates;
  the realized number is lower when candidates collide.
* The lobby and the cafeteria are the same floor, ``cfg.lobby_floor``.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .config import SimConfig, parse_hhmm
from .model import Passenger

# Day-level deviation: each value is drawn uniformly within value +/- spread * day_variation.
SPREADS = {"late_share": 0.05, "lunch_out_share": 0.10, "stay_late_share": 0.08, "peak_shift_s": 300.0}

_STAT_KEYS = (
    "lunch_out", "lunch_cafe", "lunch_desk",
    "meeting_candidates", "meeting_placed", "break_candidates", "break_placed",
)


@dataclass(frozen=True)
class Employee:
    id: int
    desk: int


@dataclass
class Trip:
    """One request: the person presses the hall button at ``time`` (seconds since midnight)."""

    time: float
    employee: int
    origin: int
    dest: int
    passenger_id: int | None = None


@dataclass
class OfficeDay:
    day_index: int
    profile: dict  # the day-level values drawn for this day
    employees: list[Employee]
    trips: dict[int, list[Trip]]  # employee id -> trips in time order
    stats: dict = field(default_factory=dict)

    def passengers(self, day_start: float) -> list[Passenger]:
        """Flatten to Passengers (arrival counted from ``day_start``) and number the trips."""
        order = sorted((t for trips in self.trips.values() for t in trips), key=lambda t: (t.time, t.employee))
        out = []
        for i, trip in enumerate(order):
            trip.passenger_id = i
            out.append(Passenger(id=i, arrival=round(trip.time - day_start, 3), origin=trip.origin, dest=trip.dest))
        return out


def _times(o: dict) -> dict:
    """The HH:MM entries of the office settings as seconds since midnight."""
    return {
        "arrival": tuple(parse_hhmm(t) for t in o["arrival_window"]),
        "late_end": parse_hhmm(o["late_end"]),
        "lunch": parse_hhmm(o["lunch_center"]),
        "work": tuple(parse_hhmm(t) for t in o["work_window"]),
        "home": tuple(parse_hhmm(t) for t in o["home_window"]),
    }


def build_employees(cfg: SimConfig, rng: random.Random) -> list[Employee]:
    """``cfg.employees`` people with fixed desk floors (never the lobby)."""
    lobby = cfg.lobby_floor
    floors = [f for f in range(cfg.floors) if f != lobby]
    if cfg.origin_weights:
        weights = [0.0 if f == lobby else w for f, w in enumerate(cfg.origin_weights)]
        if not any(w > 0 for w in weights):
            raise ValueError("origin_weights leave no desk floor besides the lobby")
        desks = rng.choices(range(cfg.floors), weights=weights, k=cfg.employees)
    else:
        desks = [floors[i % len(floors)] for i in range(cfg.employees)]
    return [Employee(i, d) for i, d in enumerate(desks)]


def draw_profile(cfg: SimConfig, o: dict, tm: dict, rng: random.Random) -> dict:
    """The day-level values for one day. With day_variation 0 they equal the configured values."""
    k = cfg.day_variation

    def vary(value: float, spread: float) -> float:
        u = rng.uniform(-1.0, 1.0)  # always drawn, so the random stream does not depend on day_variation
        return min(1.0, max(0.0, value + u * spread * k))

    late = vary(o["late_share"], SPREADS["late_share"])
    lunch_out = vary(o["lunch_out_share"], SPREADS["lunch_out_share"])
    stay_late = vary(o["stay_late_share"], SPREADS["stay_late_share"])
    shift = rng.uniform(-1.0, 1.0) * SPREADS["peak_shift_s"] * k
    a0, a1 = tm["arrival"]
    peak = min(a1, max(a0, parse_hhmm(o["arrival_peak"]) + shift))
    return {
        "late_share": late,
        "lunch_out_share": lunch_out,
        "lunch_cafe_share": min(o["lunch_cafe_share"], 1.0 - lunch_out),
        "stay_late_share": stay_late,
        "arrival_peak": peak,
    }


def _count(rng: random.Random, mean: float) -> int:
    """A whole number with the given mean (floor, plus one with the fractional probability)."""
    whole = int(mean)
    return whole + (1 if rng.random() < mean - whole else 0)


def _employee_trips(cfg, o, tm, profile, emp, rng, day_end, stats) -> list[Trip]:
    lobby, desk = cfg.lobby_floor, emp.desk
    gap = float(o["min_trip_gap_s"])
    a0, a1 = tm["arrival"]
    h0, h1 = tm["home"]
    w0, w1 = tm["work"]

    # Fixed segments: arrival and going home.
    if rng.random() < profile["late_share"]:
        t_arrive = rng.uniform(a1, tm["late_end"])
    else:
        t_arrive = rng.triangular(a0, a1, profile["arrival_peak"])
    if rng.random() < profile["stay_late_share"]:
        t_home = rng.uniform(h1, day_end)
    else:
        t_home = rng.uniform(h0, h1)
    busy = [(t_arrive, t_arrive), (t_home, t_home)]
    trips = [Trip(t_arrive, emp.id, lobby, desk), Trip(t_home, emp.id, desk, lobby)]

    def add_round_trip(start: float, length: float, away: int) -> bool:
        """Desk -> away -> desk, unless it leaves the person's day or comes within ``gap`` of anything placed."""
        end = start + length
        if start < t_arrive + gap or end > t_home - gap:
            return False
        if any(start < e + gap and s < end + gap for s, e in busy):
            return False
        busy.append((start, end))
        trips.append(Trip(start, emp.id, desk, away))
        trips.append(Trip(end, emp.id, away, desk))
        return True

    # Fixed segment: lunch. Placed before the optional ones so it is never dropped.
    draw = rng.random()
    if draw < profile["lunch_out_share"]:
        kind, minutes = "lunch_out", o["lunch_out_min"]
    elif draw < profile["lunch_out_share"] + profile["lunch_cafe_share"]:
        kind, minutes = "lunch_cafe", o["lunch_cafe_min"]
    else:
        kind, minutes = "lunch_desk", None
    stats[kind] += 1
    if minutes is not None:
        spread = o["lunch_spread_min"] * 60
        start = rng.uniform(tm["lunch"] - spread, tm["lunch"] + spread)
        if not add_round_trip(start, rng.uniform(*minutes) * 60, lobby):
            raise ValueError("lunch collides with arrival or going home; check the office time settings")

    # Optional segments: candidates that are kept or dropped as whole round trips.
    others = [f for f in range(cfg.floors) if f not in (lobby, desk)]
    for _ in range(_count(rng, o["meetings_per_person"])):
        start = rng.uniform(w0, w1)
        length = rng.uniform(*o["meeting_min"]) * 60
        if not others:  # no second non-lobby floor to meet on
            continue
        away = rng.choice(others)
        stats["meeting_candidates"] += 1
        stats["meeting_placed"] += add_round_trip(start, length, away)
    for _ in range(_count(rng, o["breaks_per_person"])):
        start = rng.uniform(w0, w1)
        length = rng.uniform(*o["break_min"]) * 60
        stats["break_candidates"] += 1
        stats["break_placed"] += add_round_trip(start, length, lobby)

    trips.sort(key=lambda t: t.time)
    return trips


def build_day(cfg: SimConfig, employees: list[Employee], rng: random.Random, day_index: int = 0) -> OfficeDay:
    """One office day for the given employees. ``day_index`` is the hook for multi-day weeks."""
    o = cfg.office_settings()
    tm = _times(o)
    profile = draw_profile(cfg, o, tm, rng)
    day_end = parse_hhmm(cfg.day_end)
    stats = dict.fromkeys(_STAT_KEYS, 0)
    trips = {e.id: _employee_trips(cfg, o, tm, profile, e, rng, day_end, stats) for e in employees}
    return OfficeDay(day_index, profile, employees, trips, stats)


def generate_office_day(cfg: SimConfig) -> tuple[OfficeDay, list[Passenger]]:
    """The structured day and its flattened Passenger list, both from the config and seed only."""
    rng = random.Random(cfg.seed)
    employees = build_employees(cfg, rng)
    day = build_day(cfg, employees, rng)
    return day, day.passengers(parse_hhmm(cfg.day_start))


def office_day_passengers(cfg: SimConfig) -> list[Passenger]:
    return generate_office_day(cfg)[1]
```

- [ ] **Step 4: Dispatch from `passengers.py` and add the scenario file**

```bash
python3 - <<'PYEOF'
p = "elevsim/passengers.py"
s = open(p).read()
for old, new in [
    ("from .model import Passenger\n", "from .model import Passenger\nfrom .schedule import office_day_passengers\n"),
    ("def generate_passengers(cfg: SimConfig) -> list[Passenger]:\n    rng = random.Random(cfg.seed)\n",
     "def generate_passengers(cfg: SimConfig) -> list[Passenger]:\n"
     "    if cfg.traffic == \"office_day\":  # built by a scheduler; cfg.passengers does not apply\n"
     "        return office_day_passengers(cfg)\n"
     "    rng = random.Random(cfg.seed)\n"),
]:
    assert s.count(old) == 1, "anchor not found exactly once: " + old[:60]
    s = s.replace(old, new, 1)
open(p, "w").write(s)
PYEOF
cat > scenarios/office_day.json <<'EOF'
{
  "name": "Office full day",
  "description": "A fixed headcount through one office day: early and late arrivals, lunch (out or cafeteria), meetings and breaks, then the evening exodus. Energy use is a comparative estimate.",
  "floors": 15, "elevators": 4, "capacity": 10,
  "traffic": "office_day", "employees": 300
}
EOF
```

- [ ] **Step 5: Run the new tests and the whole suite**

Run: `python3 -m unittest tests.test_office_day -v && python3 -m unittest discover -s tests -t .`
Expected: all PASS (the ordering tests take a few seconds: each 300-employee run is about 1 s). If a bound fails, print the observed number (for example the placed/candidate ratio) and compare with the baseline in "Measured baseline"; investigate the scheduler before changing a threshold.

- [ ] **Step 6: Commit**

```bash
git add elevsim/schedule.py elevsim/passengers.py scenarios/office_day.json tests/test_office_day.py
git commit -m "$(cat <<'EOF'
✨ feat(schedule): add the deterministic office-day scheduler

Employees with fixed desks, arrival/lunch/go-home placed first, meetings and
breaks as whole round trips, flattened into the existing Passenger list.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VLPdWXWxBs7xJ8CVRrQMXM
EOF
)"
```

---

### Task 5: Cap the recorded trace for long days

**Files:**
- Modify: `elevsim/engine.py`, `elevsim/api.py`
- Modify (append class): `tests/test_office_day.py`

**Interfaces:**
- Consumes: `Simulation.horizon` (Task 2), `SimConfig.traffic`.
- Produces: `Simulation.frame_interval: float | None` (effective seconds between frames, set by `run(record=True)`); `Simulation.MAX_FRAMES = 10_000`; the trace's `frame_interval` is the effective one.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_office_day.py` (add `from elevsim.model import Passenger` to the imports in the same edit):

```python
class FrameTests(unittest.TestCase):
    def test_office_day_trace_is_capped(self):
        res = run(office(employees=20), "collective", record=True)
        frames = res["trace"]["frames"]
        interval = res["trace"]["frame_interval"]
        self.assertLessEqual(len(frames), 10_000)
        self.assertGreater(interval, 0.5)
        self.assertAlmostEqual(frames[1][0] - frames[0][0], interval, places=3)

    def test_cap_holds_for_a_very_long_day(self):
        cfg = SimConfig(floors=3, traffic="office_day")
        person = Passenger(id=0, arrival=60000.0, origin=0, dest=1)
        sim = Simulation(cfg, get_strategy("collective"), passengers=[person]).run(record=True)
        self.assertLessEqual(len(sim.frames), 10_000)
        self.assertGreater(sim.frame_interval, 6.0)

    def test_existing_traffic_keeps_the_requested_interval(self):
        res = run({"passengers": 50, "seed": 3}, "eta", record=True, frame_interval=1.0)
        frames = res["trace"]["frames"]
        self.assertEqual(res["trace"]["frame_interval"], 1.0)
        self.assertAlmostEqual(frames[1][0] - frames[0][0], 1.0)

    def test_default_interval_is_unchanged_for_existing_traffic(self):
        res = run({"passengers": 50, "seed": 3}, "eta", record=True)
        self.assertEqual(res["trace"]["frame_interval"], 0.5)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_office_day.FrameTests -v`
Expected: FAIL (`len(frames)` is about 95,000 for the day run; `AttributeError: 'Simulation' object has no attribute 'frame_interval'`).

- [ ] **Step 3: Patch `engine.py` and `api.py`**

```bash
python3 - <<'PYEOF'
def patch(path, edits):
    s = open(path).read()
    for old, new in edits:
        assert s.count(old) == 1, path + ": anchor not found exactly once: " + old[:60]
        s = s.replace(old, new, 1)
    open(path, "w").write(s)

patch("elevsim/engine.py", [
    ("from collections import deque\n", "import math\nfrom collections import deque\n"),
    ("EPS = 1e-9\n", "EPS = 1e-9\nMAX_FRAMES = 10_000  # most frames a recorded office_day run may hold\n"),
    ("        self._frame_every = 1\n        self._tick = 0\n",
     "        self._frame_every = 1\n        self.frame_interval: float | None = None  # effective seconds between frames, set by run(record=True)\n        self._tick = 0\n"),
    ("            self._frame_every = max(1, round(frame_interval / self.cfg.dt))\n            self._record_frame()\n",
     '''            self._frame_every = self._frames_every(frame_interval)
            self.frame_interval = self._frame_every * self.cfg.dt
            self._record_frame()
'''),
    ("    def step(self) -> None:\n",
     '''    def _frames_every(self, requested: float) -> int:
        """Ticks between recorded frames.

        The requested interval, widened for office_day so a run records at most MAX_FRAMES
        frames. 9997 = MAX_FRAMES minus the initial frame, the final frame and one tick of
        slack. Existing traffic is never widened: with the 4-hour default horizon the cap
        would change every existing scenario's frames.
        """
        dt = self.cfg.dt
        every = max(1, round(requested / dt))
        if self.cfg.traffic == "office_day":
            every = max(every, math.ceil(self.horizon / (MAX_FRAMES - 3) / dt - 1e-9))
        return every

    def step(self) -> None:
'''),
])

patch("elevsim/api.py", [
    ('            "frame_interval": frame_interval,\n', '            "frame_interval": sim.frame_interval,\n'),
])
PYEOF
```

- [ ] **Step 4: Run the new tests and the whole suite**

Run: `python3 -m unittest tests.test_office_day.FrameTests -v && python3 -m unittest discover -s tests -t .`
Expected: all PASS. (`step` appears once as `def step(self) -> None:`; if the anchor assertion fails, the file changed; re-read `elevsim/engine.py` and anchor on the real line.)

- [ ] **Step 5: Commit**

```bash
git add elevsim/engine.py elevsim/api.py tests/test_office_day.py
git commit -m "$(cat <<'EOF'
✨ feat(engine): cap recorded frames for long office_day traces

The trace reports the effective frame interval; existing traffic keeps the
requested interval.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VLPdWXWxBs7xJ8CVRrQMXM
EOF
)"
```

---

### Task 6: CLI support

**Files:**
- Modify: `elevsim/cli.py`
- Create: `tests/test_cli_office.py`

**Interfaces:**
- Consumes: `config.SCHEDULED_TRAFFIC`, summary keys `passengers_total`, `energy_kwh`, `METRICS`.
- Produces: `--traffic office_day`, `--employees N`, an `energy_kwh` column ("kWh") in the compare table, headers that print the real trip count, and a `ValueError` (printed as `error: ...`) for `--passengers` together with `office_day`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli_office.py`:

```python
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

    def test_traffic_flag_accepts_office_day(self):
        text = run_cli("run", "-s", "collective", "--traffic", "office_day", "--employees", "10")
        self.assertIn("10 employees", text)

    def test_existing_output_keeps_its_shape(self):
        text = run_cli("run", "-s", "collective", "--passengers", "40")
        self.assertIn("40 passengers (uniform, 20.0/min, seed 1)", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_cli_office -v`
Expected: FAIL / `SystemExit` from argparse (`invalid choice: 'office_day'`, `unrecognized arguments: --employees`).

- [ ] **Step 3: Patch `elevsim/cli.py`**

```bash
python3 - <<'PYEOF'
p = "elevsim/cli.py"
s = open(p).read()
edits = [
    ("from .config import TRAFFIC_PATTERNS, SimConfig\n", "from .config import SCHEDULED_TRAFFIC, TRAFFIC_PATTERNS, SimConfig\n"),
    ('TABLE_METRICS = ["avg_wait", "p95_wait", "max_wait", "avg_journey", "utilization", "floors_travelled",\n                 "max_queue", "bottlenecks", "left_behind"]\n',
     'TABLE_METRICS = ["avg_wait", "p95_wait", "max_wait", "avg_journey", "utilization", "floors_travelled",\n                 "energy_kwh", "max_queue", "bottlenecks", "left_behind"]\n'),
    ('         "utilization": "util %", "floors_travelled": "floors", "max_queue": "max q",\n',
     '         "utilization": "util %", "floors_travelled": "floors", "energy_kwh": "kWh", "max_queue": "max q",\n'),
    ('    g.add_argument("--passengers", type=int)\n',
     '    g.add_argument("--passengers", type=int, help="total passengers (not used by office_day)")\n'
     '    g.add_argument("--employees", type=int, help="headcount for --traffic office_day")\n'),
    ('    g.add_argument("--traffic", choices=sorted(TRAFFIC_PATTERNS))\n',
     '    g.add_argument("--traffic", choices=sorted([*TRAFFIC_PATTERNS, *SCHEDULED_TRAFFIC]))\n'),
    ('    for key in ("floors", "elevators", "capacity", "passengers", "arrival_rate", "traffic", "idle_parking", "seed"):\n'
     '        val = getattr(args, key)\n        if val is not None:\n            data[key] = val\n    return SimConfig.from_dict(data)\n',
     '    for key in ("floors", "elevators", "capacity", "passengers", "employees", "arrival_rate", "traffic",\n'
     '                "idle_parking", "seed"):\n'
     '        val = getattr(args, key)\n        if val is not None:\n            data[key] = val\n'
     '    if args.passengers is not None and data.get("traffic") == "office_day":\n'
     '        raise ValueError("--passengers does not apply to office_day traffic; use --employees")\n'
     '    return SimConfig.from_dict(data)\n'),
    ('def _fmt(v) -> str:\n',
     'def _traffic_text(cfg: SimConfig, trips: int) -> str:\n'
     '    if cfg.traffic == "office_day":\n'
     '        return f"office_day, {cfg.employees} employees, {trips} trips, seed {cfg.seed}"\n'
     '    return f"{trips} passengers ({cfg.traffic}, {cfg.arrival_rate}/min, seed {cfg.seed})"\n\n\n'
     'def _fmt(v) -> str:\n'),
    ('    print(f"{res[\'strategy_label\']} on {cfg.floors} floors, {cfg.elevators} cars, "\n'
     '          f"{cfg.passengers} passengers ({cfg.traffic}, {cfg.arrival_rate}/min, seed {cfg.seed})\\n")\n',
     '    print(f"{res[\'strategy_label\']} on {cfg.floors} floors, {cfg.elevators} cars, "\n'
     '          f"{_traffic_text(cfg, s[\'passengers_total\'])}\\n")\n'),
    ('    print(f"{cfg.floors} floors, {cfg.elevators} cars x {cfg.capacity}, {cfg.passengers} passengers, "\n'
     '          f"traffic={cfg.traffic}, {cfg.arrival_rate}/min, parking={cfg.idle_parking}, "\n',
     '    totals = sorted({r["passengers_total"] for r in out["results"][0]["runs"]})\n'
     '    trips = str(totals[0]) if len(totals) == 1 else f"{totals[0]}-{totals[-1]}"\n'
     '    if cfg.traffic == "office_day":\n'
     '        load = f"{cfg.employees} employees ({trips} trips), traffic=office_day"\n'
     '    else:\n'
     '        load = f"{trips} passengers, traffic={cfg.traffic}, {cfg.arrival_rate}/min"\n'
     '    print(f"{cfg.floors} floors, {cfg.elevators} cars x {cfg.capacity}, {load}, parking={cfg.idle_parking}, "\n'),
]
for old, new in edits:
    assert s.count(old) == 1, "anchor not found exactly once: " + old[:70]
    s = s.replace(old, new, 1)
open(p, "w").write(s)
PYEOF
```

- [ ] **Step 4: Run the new tests and the whole suite**

Run: `python3 -m unittest tests.test_cli_office -v && python3 -m unittest discover -s tests -t . && python3 -m elevsim compare --passengers 80 --seeds 2 | head -12`
Expected: all PASS; the compare table now has a `kWh` column and the header line still reads like `... , 80 passengers, traffic=uniform, 20.0/min, parking=stay, seeds 1..2 ...`.

- [ ] **Step 5: Commit**

```bash
git add elevsim/cli.py tests/test_cli_office.py
git commit -m "$(cat <<'EOF'
✨ feat(cli): office_day traffic, --employees and an energy column

--passengers together with office_day is rejected instead of silently ignored.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VLPdWXWxBs7xJ8CVRrQMXM
EOF
)"
```

---

### Task 7: Viewer

**Files:**
- Modify: `elevsim/viewer_build.py`, `viewer/index.html`, `viewer/app.js`, `viewer/style.css`
- Create: `tests/test_viewer_build.py`

**Interfaces:**
- Consumes: `scenarios/office_day.json` (Task 4), summary key `energy_kwh`, `result.config.traffic`, `result.config.day_start`.
- Produces: `viewer_build.NO_PRECOMPUTE: set[str]` (`{"office_day"}`), `viewer_build.precompute_ids(presets, demo_all) -> list[str]`; in the page: an `office_day` traffic option, an `employees` input shown only for it (hiding `passengers` and `arrival_rate`), `readForm()` that overlays the form on the selected preset's full config, an HH:MM clock for `office_day` runs, an "Energy (est.)" row in "Whole run", an `energy_kwh` column in the Compare table, and 120x / 600x speeds.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_viewer_build.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_viewer_build -v`
Expected: ImportError (`cannot import name 'NO_PRECOMPUTE'`).

- [ ] **Step 3: Patch `viewer_build.py`, `index.html`, `style.css`**

```bash
grep -n "\.field" viewer/style.css | head -5
python3 - <<'PYEOF'
def patch(path, edits):
    s = open(path).read()
    for old, new in edits:
        assert s.count(old) == 1, path + ": anchor not found exactly once: " + old[:70]
        s = s.replace(old, new, 1)
    open(path, "w").write(s)

patch("elevsim/viewer_build.py", [
    ('DEMO_PRESET = "office_lunch"\n',
     'DEMO_PRESET = "office_lunch"\n'
     'NO_PRECOMPUTE = {"office_day"}  # a full day is too large to embed; it runs on the live engine\n\n\n'
     'def precompute_ids(presets: list[dict], demo_all: bool) -> list[str]:\n'
     '    """Preset ids whose runs and comparison are computed at build time."""\n'
     '    ids = [p["id"] for p in presets] if demo_all else [DEMO_PRESET]\n'
     '    return [i for i in ids if i not in NO_PRECOMPUTE]\n'),
    ('        ids = [p["id"] for p in presets] if demo_all else [DEMO_PRESET]\n        scenarios = {}\n',
     '        ids = precompute_ids(presets, demo_all)\n        scenarios = {}\n'),
])

patch("viewer/index.html", [
    ('<div class="field"><label for="passengers">',
     '<div class="field" id="field-passengers"><label for="passengers">'),
    ('<div class="field"><label for="arrival_rate">Arrivals / min</label><input id="arrival_rate" type="number" min="0.1" step="0.5"></div>\n',
     '<div class="field" id="field-arrival_rate"><label for="arrival_rate">Arrivals / min</label><input id="arrival_rate" type="number" min="0.1" step="0.5"></div>\n'
     '        <div class="field" id="field-employees" hidden><label for="employees">Employees</label><input id="employees" type="number" min="1" max="600"></div>\n'),
    ('            <option value="interfloor">Interfloor (between upper floors)</option>\n',
     '            <option value="interfloor">Interfloor (between upper floors)</option>\n'
     '            <option value="office_day">Office full day (employees)</option>\n'),
    ('<option value="16">16×</option><option value="32">32×</option>',
     '<option value="16">16×</option><option value="32">32×</option>\n'
     '          <option value="120">120×</option><option value="600">600×</option>'),
])
PYEOF
printf '\n.field[hidden] { display: none; }\n' >> viewer/style.css
```

- [ ] **Step 4: Patch `viewer/app.js`**

```bash
python3 - <<'PYEOF'
p = "viewer/app.js"
s = open(p).read()
edits = [
    # employees field joins the form fields and defaults
    ('    "idle_parking", "floor_travel_time", "door_time", "board_time", "lobby_floor"];\n',
     '    "idle_parking", "floor_travel_time", "door_time", "board_time", "lobby_floor", "employees"];\n'),
    ('    idle_parking: "stay", floor_travel_time: 1.5, door_time: 2, board_time: 1, lobby_floor: 0,\n  }, DATA.defaults || {});\n',
     '    idle_parking: "stay", floor_travel_time: 1.5, door_time: 2, board_time: 1, lobby_floor: 0, employees: 300,\n  }, DATA.defaults || {});\n'),
    # fillForm keeps the visible fields in sync; readForm overlays the form on the preset's full config
    ('''  function fillForm(cfg) {
    for (const f of CFG_FIELDS) if (cfg[f] !== undefined && $(f)) $(f).value = cfg[f];
  }
  function readForm() {
    const cfg = {};
    for (const f of CFG_FIELDS) {
''', '''  // office_day is sized by employees; passengers and arrivals/min do not apply to it.
  function syncTrafficFields() {
    const office = $("traffic").value === "office_day";
    $("field-employees").hidden = !office;
    $("field-passengers").hidden = office;
    $("field-arrival_rate").hidden = office;
  }
  function fillForm(cfg) {
    for (const f of CFG_FIELDS) if (cfg[f] !== undefined && $(f)) $(f).value = cfg[f];
    syncTrafficFields();
  }
  function readForm() {
    // Start from the selected preset's full config so keys that have no form field (for
    // example the office settings) reach the engine, then let the form fields win.
    const sel = $("preset").value;
    const preset = sel !== "" ? DATA.presets[Number(sel)] : null;
    const cfg = preset ? Object.assign({}, preset.config) : {};
    for (const f of CFG_FIELDS) {
'''),
    # validation
    ('''    if (!(cfg.passengers >= 1 && cfg.passengers <= 3000)) return "Passengers must be between 1 and 3000.";
    if (!(cfg.arrival_rate > 0)) return "Arrivals per minute must be above 0.";
''', '''    if (cfg.traffic === "office_day") {
      if (!(cfg.employees >= 1 && cfg.employees <= 600)) return "Employees must be between 1 and 600.";
    } else {
      if (!(cfg.passengers >= 1 && cfg.passengers <= 3000)) return "Passengers must be between 1 and 3000.";
      if (!(cfg.arrival_rate > 0)) return "Arrivals per minute must be above 0.";
    }
'''),
    # re-sync when the traffic pattern changes
    ('    $("run-btn").onclick = runSimulation;\n    $("compare-btn").onclick = runCompare;\n',
     '    $("traffic").addEventListener("change", syncTrafficFields);\n    $("run-btn").onclick = runSimulation;\n    $("compare-btn").onclick = runCompare;\n'),
    # clock: HH:MM for a full-day run
    ('  const fmtT = (s) => { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };\n',
     '''  // office_day runs show the time of day (day_start + elapsed); other runs show elapsed m:ss.
  const dayStartSeconds = (cfg) => {
    const [h, m] = String(cfg.day_start || "00:00").split(":").map(Number);
    return h * 3600 + m * 60;
  };
  const fmtT = (s) => {
    s = Math.max(0, Math.round(s));
    if (result && result.config.traffic === "office_day") {
      const abs = s + dayStartSeconds(result.config);
      return String(Math.floor(abs / 3600) % 24).padStart(2, "0") + ":" + String(Math.floor((abs % 3600) / 60)).padStart(2, "0");
    }
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  };
'''),
    # Whole run: energy row (older trace files have no energy_kwh)
    ('      ["Longest queue", s.max_queue], ["Bottleneck episodes", s.bottlenecks], ["Full-car pass-bys", s.left_behind],\n',
     '      ["Longest queue", s.max_queue], ["Bottleneck episodes", s.bottlenecks], ["Full-car pass-bys", s.left_behind],\n'
     '      ["Energy (est.)", s.energy_kwh === undefined ? "n/a" : num(s.energy_kwh, 2) + " kWh"],\n'),
    # Compare table column
    ('      "idle_time", "floors_travelled", "stops", "max_queue", "bottlenecks", "left_behind"];\n',
     '      "idle_time", "floors_travelled", "energy_kwh", "stops", "max_queue", "bottlenecks", "left_behind"];\n'),
]
for old, new in edits:
    assert s.count(old) == 1, "anchor not found exactly once: " + old[:70]
    s = s.replace(old, new, 1)
open(p, "w").write(s)
PYEOF
node --check viewer/app.js && echo "app.js syntax OK"
```

Note on `readForm()`: editing any field already resets the preset dropdown to "Custom" (existing `input` listener), after which only form fields are sent. That is fine: no preset carries a key without a form field today; the overlay matters for presets that gain such keys (for example an `office` override in a scenario file).

- [ ] **Step 5: Run the tests**

Run: `python3 -m unittest tests.test_viewer_build -v && python3 -m unittest discover -s tests -t . && python3 -m elevsim viewer --out dist/viewer.html`
Expected: all PASS, `viewer written to dist/viewer.html`.

- [ ] **Step 6: Manual browser verification (Playwright MCP is configured in this repo)**

The viewer loads Pyodide from the jsDelivr CDN, so this needs network.

1. Serve the build: `cd dist && python3 -m http.server 8765 --bind 127.0.0.1` (run in the background; stop it afterwards with `kill %1` or the task id, **not** `pkill -f`, which can kill your own shell).
2. Navigate to `http://127.0.0.1:8765/viewer.html` (Playwright blocks `file:` URLs).
3. Wait for the status text "Python engine ready".
4. Choose the "Office full day" scenario. Check: the Employees field is visible; Passengers and Arrivals / min are hidden; Traffic pattern shows "Office full day (employees)".
5. Click "Run simulation". **Record how long the live full-day run takes** (this is the Pyodide timing the spec left open; native is about 1 s). Expected: it finishes; if it takes more than about 30 s, report it to the user as a decision point (the fast-forward optimization in `docs/ideas.md` would come back) instead of "fixing" it here.
6. Check: the clock shows `HH:MM` (for example `06:45` at the start), "Whole run" has an "Energy (est.)" row, the speed selector has 120× and 600×, and the console has no errors except the favicon 404.
7. Open the Compare tab, run 1 seed for the office scenario, and confirm the table has an "Energy use (estimate) (kWh)" column.
8. Take a screenshot for the user and stop the server.

- [ ] **Step 7: Commit**

```bash
git add elevsim/viewer_build.py viewer/index.html viewer/app.js viewer/style.css tests/test_viewer_build.py
git commit -m "$(cat <<'EOF'
✨ feat(viewer): office full-day scenario, energy rows and HH:MM clock

office_day runs on the live engine only (never precomputed), readForm overlays
the form on the preset config, and faster playback speeds suit a 13-hour day.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VLPdWXWxBs7xJ8CVRrQMXM
EOF
)"
```

---

### Task 8: Docs, code map, version and CI (the release commit)

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `docs/ideas.md`, `.github/workflows/tests.yml`, `elevsim/__init__.py`
- Create: `docs/code-map.md`

**Interfaces:**
- Consumes: everything above.
- Produces: `__version__ == "0.2.0"`, a `0.2.0` changelog entry, a durable code map for the user (they asked for walkthroughs so they can find and change code by hand).

- [ ] **Step 1: Patch `README.md`**

```bash
python3 - <<'PYEOF'
p = "README.md"
s = open(p).read()
edits = [
    ("python3 -m elevsim viewer                                 # writes dist/viewer.html\n",
     "python3 -m elevsim run -s eta --config scenarios/office_day.json --employees 100   # one full office day\n"
     "python3 -m elevsim viewer                                 # writes dist/viewer.html\n"),
    ("| `long_wait` | 60 s | waits at or above this count as long waits |\n",
     "| `long_wait` | 60 s | waits at or above this count as long waits |\n"
     "| `max_time` | auto | hard stop in seconds. Auto is 4 hours, or for `office_day` the last request plus `office.drain_margin_s`. An explicit value that is too small for `office_day` is an error |\n"
     "| `employees` | 300 | headcount for `traffic: \"office_day\"` (`passengers` and `arrival_rate` do not apply to it) |\n"
     "| `day_start`, `day_end` | `06:45`, `20:00` | `office_day` window: simulation time 0 is `day_start`; no request is generated after `day_end` |\n"
     "| `day_variation` | 1.0 | 0 = day-level shares exactly as configured, 1 = default spread between seeds. Individual employee schedules always depend on the seed |\n"
     "| `office` | `{}` | overrides for the `office_day` defaults (see below); unknown keys are rejected |\n"
     "| `energy_model`, `energy_base`, `energy_per_passenger` | `simple`, 0.01, 0.002 | energy model and its constants (kWh per floor moved, extra kWh per passenger per floor) |\n"),
    ("breakdowns are in the JSON output.\n",
     "breakdowns are in the JSON output.\n\n"
     "**Energy** (`energy_kwh`) is a comparative estimate: the `simple` model charges a cost per floor a\n"
     "car moves plus a cost per passenger on board per floor. Its constants are uncalibrated, so use the\n"
     "number to rank algorithms against each other, not as an absolute figure. Idle and door time are\n"
     "recorded but not charged. The model is replaceable (`elevsim/energy.py`).\n"),
    ("## How the engine works\n",
     """## Office-day scenario

`traffic: "office_day"` simulates one office day for a fixed headcount (`scenarios/office_day.json`).
Every employee has a fixed desk floor and a day of timed trips:

* **Arrival** from about an hour before 08:00 (a share arrive late, until 09:30).
* **Lunch** around 12:00: some leave the building, some only visit the cafeteria (on the lobby
  floor) and return to their desk, the rest eat at the desk.
* **During the day**: meetings on other floors and short cafeteria breaks.
* **Going home** from 17:00; some stay late, until `day_end`.

The schedule depends on the seed only, never on the algorithm, so every algorithm sees identical
traffic. With `day_variation` above 0 each seed also gets slightly different day-level shares
(late arrivals, lunch-out share, stay-late share, arrival peak). Meetings and breaks are
*candidates*: one that would overlap another segment is dropped, so fewer than the configured
number happen. The defaults are placeholders, not real office statistics; override them with the
`office` key:

| `office` key | Default | Meaning |
| --- | --- | --- |
| `arrival_window`, `arrival_peak` | `["07:00","08:00"]`, `07:50` | on-time arrivals (triangular) |
| `late_share`, `late_end` | 0.15, `09:30` | share who arrive late, and the latest late arrival |
| `lunch_center`, `lunch_spread_min` | `12:00`, 30 | lunch departures spread around this time |
| `lunch_out_share`, `lunch_cafe_share` | 0.40, 0.30 | leave the building / cafeteria only (the rest eat at the desk) |
| `lunch_out_min`, `lunch_cafe_min` | `[30,60]`, `[15,40]` | minutes away |
| `work_window` | `["09:00","17:00"]` | meetings and breaks start inside it |
| `meetings_per_person`, `breaks_per_person` | 1.0, 0.7 | candidate rates |
| `meeting_min`, `break_min` | `[30,60]`, `[10,20]` | minutes away |
| `home_window`, `stay_late_share` | `["17:00","17:45"]`, 0.20 | when most leave; the rest leave until `day_end` |
| `min_trip_gap_s` | 600 | minimum seconds between one person's consecutive requests |
| `drain_margin_s` | 3600 | time after the last request the simulation may run |

In the viewer the scenario runs on the live engine only (it is never precomputed), the clock shows
the time of day, and playback speeds go up to 600x.

## How the engine works
"""),
]
for old, new in edits:
    assert s.count(old) == 1, "anchor not found exactly once: " + old[:70]
    s = s.replace(old, new, 1)
open(p, "w").write(s)

p = "CLAUDE.md"
s = open(p).read()
old = "- `dist/` and `results/` are generated and gitignored.\n"
new = ("- Traffic that needs a scheduler (`office_day`) lives in `elevsim/schedule.py` and is selected through\n"
       "  `SCHEDULED_TRAFFIC` in `elevsim/config.py`; energy models live in `elevsim/energy.py`. See `docs/code-map.md`.\n"
       "- `dist/` and `results/` are generated and gitignored.\n")
assert s.count(old) == 1
open(p, "w").write(s.replace(old, new, 1))
PYEOF
```

- [ ] **Step 2: Create `docs/code-map.md`**

```markdown
# Code map

Where things live, for reading or changing the code by hand. Names point to
functions and classes, not line numbers, because line numbers drift: search for the
name. The standard library is the only dependency.

## How a run flows

```text
config (JSON scenario / CLI flags / viewer form)
  -> SimConfig                elevsim/config.py       validates and holds every setting
  -> generate_passengers      elevsim/passengers.py   seeded traffic mixes (uniform, up_peak, ...)
     or office_day_passengers elevsim/schedule.py     employees -> timed trips (office_day)
  -> Simulation.run           elevsim/engine.py       the tick loop, with a Strategy deciding the cars
  -> summarize                elevsim/metrics.py      wait/journey/queue metrics, plus energy via
                                                      elevsim/energy.py
  -> run / compare            elevsim/api.py          one run, or all algorithms over several seeds
  -> cli.py prints and writes files, or viewer/app.js draws the result in the browser
```

## Modules

| File | What it does | Look here to change |
| --- | --- | --- |
| `elevsim/config.py` | `SimConfig` dataclass, validation, `OFFICE_DEFAULTS`, `parse_hhmm` | add or rename a setting, change a default, add a validation rule |
| `elevsim/model.py` | `Passenger`, `HallCall`, `Elevator` and the state names | add a per-car or per-passenger counter |
| `elevsim/engine.py` | `Simulation`: arrivals, car state machine, statistics, frame recording | how cars move, board and open doors; the stop time (`_resolve_horizon`); frame sampling (`_frames_every`) |
| `elevsim/passengers.py` | `generate_passengers`: seeded Poisson arrivals and traffic mixes | add a traffic mix |
| `elevsim/schedule.py` | office-day scheduler: `Employee`, `Trip`, `OfficeDay`, `build_day`, `generate_office_day` | change the day shape, lunch rules, meeting and break rules |
| `elevsim/energy.py` | `EnergyModel`, `SimpleEnergy`, `MODELS` | add an energy model (also add its name to `ENERGY_MODELS` in `config.py`) |
| `elevsim/metrics.py` | `METRICS` table and `summarize` | add a metric (add it to `METRICS`; the CLI table and the viewer lists are separate, see below) |
| `elevsim/strategies/` | the algorithms: `base.py` (hooks and LOOK logic), one file per algorithm, `__init__.py` registry | add or tune an algorithm |
| `elevsim/api.py` | `run`, `compare`, and the JSON wrappers the browser calls | what the viewer gets back from a run |
| `elevsim/cli.py` | `python -m elevsim run / compare / list / viewer` | flags, printed tables (`TABLE_METRICS`, `SHORT`) |
| `elevsim/viewer_build.py` | builds `dist/viewer.html`: bundles the viewer files, the Python sources and the precomputed demo | which scenarios are precomputed (`DEMO_PRESET`, `NO_PRECOMPUTE`) |
| `viewer/index.html`, `app.js`, `style.css` | the single-page viewer | form fields, readouts (`renderFinal`), Compare table (`cols`), clock (`fmtT`), playback |
| `scenarios/*.json` | named scenario presets, also the viewer's dropdown | add a preset |
| `tests/` | `unittest` suites; run `python3 -m unittest discover -s tests -t .` | one file per area: engine, energy, office config, office day, CLI, viewer build |

## If you want to change...

| Goal | Edit |
| --- | --- |
| The office day's shape (arrival times, lunch split, meetings per person) | the `OFFICE_DEFAULTS` dict in `config.py`, or the `office` key of a scenario JSON, no code needed |
| How the schedule is built | `_employee_trips` in `schedule.py` |
| What energy costs | `SimpleEnergy.car_energy_kwh` in `energy.py`, or the `energy_*` settings |
| A new metric shown everywhere | `METRICS` and `summarize` in `metrics.py`, then `TABLE_METRICS` / `SHORT` in `cli.py`, then `renderFinal` and `cols` in `viewer/app.js` (these three lists are hardcoded separately) |
| How a car chooses where to go | `elevsim/strategies/base.py` (`choose_direction`, `should_stop`) or the algorithm's own file |
| How long a run may last | `max_time` in the config; the auto rule is `_resolve_horizon` in `engine.py` |
| How many frames the viewer gets | `_frames_every` and `MAX_FRAMES` in `engine.py` |

## Rules that must keep holding

- Traffic depends on the config and seed only, never on the strategy (`tests/test_engine.py`, `tests/test_office_day.py`).
- Standard library only; importable under Pyodide and Python 3.10, 3.12, 3.13.
- The config is never changed by a run: derived values (trip count, horizon) are reported in the summary.
```

- [ ] **Step 3: Version, changelog, ideas and CI**

```bash
python3 - <<'PYEOF'
import datetime

today = datetime.date.today().isoformat()

# version
p = "elevsim/__init__.py"
s = open(p).read()
assert s.count('__version__ = "0.1.0"') == 1
open(p, "w").write(s.replace('__version__ = "0.1.0"', '__version__ = "0.2.0"'))

# changelog: move the planned entry into a real 0.2.0 release
p = "CHANGELOG.md"
s = open(p).read()
a = s.index("## [Unreleased]")
b = s.index("## [0.1.0]")
release = f"""## [Unreleased]

## [0.2.0] - {today}

### Added

- Full-day office scenario (`traffic: "office_day"`, `scenarios/office_day.json`): a fixed
  headcount of employees with fixed desk floors, arrivals from an hour before 08:00 with late
  arrivals, a 12:00-13:00 lunch (out of the building or cafeteria only), mid-day meetings and
  cafeteria breaks, an evening exodus with some staying late, and per-seed day variation.
  Settings: `employees`, `day_start`, `day_end`, `day_variation` and the `office` dict.
- Energy metric `energy_kwh` (a comparative estimate) with a replaceable `EnergyModel`
  (`elevsim/energy.py`), a `loaded_floor_distance` counter per car, and `energy_per_passenger`
  in the summary.
- Summary keys `passengers_total` and `horizon`; CLI `--employees` and a kWh column in the compare table.
- Viewer: the office scenario (live engine only), an HH:MM clock, energy rows, 120x and 600x speeds.
- `docs/code-map.md`, `docs/ideas.md` and the design spec and plan under `docs/superpowers/`.

### Changed

- `max_time` now defaults to `None` (auto): 4 hours for existing traffic, exactly as before, and the
  last request plus a drain margin for `office_day`. An explicit value is never overridden; one too
  small for `office_day` raises an error.
- The recorded trace of an `office_day` run is capped at 10,000 frames, and the trace reports the
  effective `frame_interval`. Existing scenarios record the same frames as before.
- `--passengers` together with `--traffic office_day` is rejected.

"""
open(p, "w").write(s[:a] + release + s[b:])

# ideas: shipped item, and the fast-forward idea with its constraints
p = "docs/ideas.md"
s = open(p).read()
old = "- [ ] Full-day clock (HH:MM) and chart axis in the viewer. (2026-10-08)"
new = ("- [x] Full-day clock (HH:MM) in the viewer. Shipped in 0.2.0. The sparkline has no time\n"
       "  axis; adding one is still open. (2026-10-08)")
assert s.count(old) == 1
s = s.replace(old, new, 1)
old = "## Viewer\n"
new = """## Engine performance

- [ ] Idle fast-forward: when all cars are idle and nothing is waiting, jump the clock to the next
  event. Dropped from 0.2.0 because a full-day run takes about 1 s natively (2026-10-08 profiling).
  Needed for the 24-hour window and multi-day weeks. Constraints found in review: strategies with
  timers need a hook (`eta` re-plans on `sim.t`), the tick counter and the frames on the frame grid
  must still advance, `dt` must be a power of two for exact time sums, `bottleneck_queue` must be at
  least 1, parking (`park_delay`) must still fire on time, and the result must equal the
  tick-by-tick run exactly (compare per-passenger times, per-car stats and summary). (2026-10-08)

## Viewer
"""
assert s.count(old) == 1
open(p, "w").write(s.replace(old, new, 1))

# CI smoke test and a JS syntax check
p = ".github/workflows/tests.yml"
s = open(p).read()
old = "          python -m elevsim compare --passengers 80 --seeds 2\n"
new = ("          python -m elevsim compare --passengers 80 --seeds 2\n"
       "          python -m elevsim run -s eta --config scenarios/office_day.json --employees 30\n"
       "          node --check viewer/app.js\n")
assert s.count(old) == 1
open(p, "w").write(s.replace(old, new, 1))
PYEOF
grep -n "__version__" elevsim/__init__.py; sed -n 1,12p CHANGELOG.md | head -3
```

- [ ] **Step 4: Final verification (evidence before claims)**

Run each and read the output:

```bash
python3 -m unittest discover -s tests -t . 2>&1 | tail -5
python3 -m elevsim list
python3 -m elevsim compare --passengers 80 --seeds 2
python3 -m elevsim run -s eta --config scenarios/office_day.json --employees 30
python3 -m elevsim run -s eta --config scenarios/office_day.json --employees 300 | head -30
python3 -m elevsim viewer --out dist/viewer.html
node --check viewer/app.js
git status --short
```

Expected: tests `OK`; the compare table includes `kWh`; the 300-employee run prints about 1,800 trips and `Passengers served` equal to it; the viewer builds; `git status` shows only the intended files (and `.playwright-mcp/`, untracked, which must not be committed unless PR #2's ignore rule has landed). On Python 3.10 and 3.13 (CI): if those interpreters are installed locally, run the test suite with each (`python3.10 -m unittest discover -s tests -t .`); otherwise say CI is the check for them.

- [ ] **Step 5: Commit the release**

```bash
git add README.md CLAUDE.md CHANGELOG.md docs/ideas.md docs/code-map.md .github/workflows/tests.yml elevsim/__init__.py
git commit -m "$(cat <<'EOF'
🔖 chore(release): 0.2.0 office-day scenario and energy metric

README, code map, changelog, version bump and CI smoke test.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VLPdWXWxBs7xJ8CVRrQMXM
EOF
)"
```

- [ ] **Step 6: Hand back to the user (do not push or open a PR without asking)**

Report: the test results, the Pyodide timing measured in Task 7, the four deviations listed at the top of this plan, and offer the mentoring walkthrough the user asked for after each mid or big feature: a live explanation of each touched module (use `docs/code-map.md` as the script: the data-flow diagram, then `config.py`, `schedule.py`, `engine.py`, `energy.py`, `metrics.py`, `cli.py`, the viewer files) with "if you want to change X, edit Y". Then ask whether to push the branch and open a PR into `dev` (squash merge; the PR is already complete: changelog, version and docs are in the branch).

---

## Self-Review (done against the spec)

**Spec coverage**

| Spec section | Task |
| --- | --- |
| 3.1 scheduler: employees, segments, priority and window rules, contract, variation, passenger count, `OfficeDay`/`day_index`, `lobby_floor`, temporal order, boundary check | Task 4 (code and tests), Task 1 (settings, validation) |
| 3.1 timeline invariant and `max_time` auto/explicit | Task 1 (`None` default), Task 2 (`_resolve_horizon`, tests) |
| 3.2 fast-forward | dropped by decision (see Deviations and `docs/ideas.md`) |
| 3.3 energy counters, models, comparative estimate, 0 when none served | Task 3, README in Task 8 |
| 3.4 config, API, CLI (`--employees`, kWh column, `--passengers` rejection, `office_day` registration) | Tasks 1, 4, 6 |
| 3.5 viewer: wiring, frame cap, precompute exclusion, speeds, clock | Task 5 (cap), Task 7 |
| 3.6 testing (all bullets except fast-forward) | Tasks 1-7 |
| 4 risks: browser run time | Task 7 Step 6 measures it |
| 5/6 out of scope and future work | `docs/ideas.md` (already committed) |
| Changelog, version `0.2.0`, README | Task 8 |

**Placeholder scan:** no TBD/TODO; every code step has full code. The two places that depend on observed behavior (Task 3 `floors_travelled` expectation, Task 7 Pyodide timing) say what to do and what not to do.

**Type consistency:** `generate_office_day` returns `(OfficeDay, list[Passenger])` everywhere; `Trip.passenger_id` is set by `OfficeDay.passengers`; `OfficeDay.stats` keys match `_STAT_KEYS` and the test; `profile` keys match `draw_profile`; `Simulation.horizon` and `Simulation.frame_interval` are used by `metrics.py`, `api.py` and the tests under the same names; summary keys `passengers_total`, `horizon`, `energy_kwh`, `energy_per_passenger` match the CLI, the tests and the viewer.

**Review Focus:** all five lines have tests (Task 1 `test_bad_values_are_rejected`, Task 2 `HorizonTests`, Task 4 `test_tiny_buildings`, `test_variation_clamps_shares`, `test_explicit_max_time_too_small`, `test_compare_over_seeds`, Task 6 `test_passengers_flag_is_rejected_for_office_day`).
