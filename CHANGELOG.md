# Changelog

All notable changes are listed here, newest first. The version lives in
`elevsim/__version__` (`elevsim/__init__.py`) and follows
[Semantic Versioning](https://semver.org/) while still in 0.x:

| Change | Bump |
| --- | --- |
| New feature or metric | minor (`0.1.0` to `0.2.0`) |
| Bug fix, docs or config only | patch (`0.2.0` to `0.2.1`) |
| Breaking change to config keys or JSON output | minor while in 0.x |

The minor number is a plain counter that grows by one per release and may go
well past 9 (`0.25.0`, `0.37.0`, even `0.100.0`) before `1.0.0`. Versions record
release order, not feature order, so planned ideas (see `docs/ideas.md`) carry no
version until they ship. `1.0.0` is a deliberate decision, made when the config
and output formats are stable enough to promise compatibility.

The version is bumped in the last commit of the implementation branch, so the
PR into `dev` is complete when it is opened. The git tag is created on `main`
when `dev` is promoted. Each entry links to its design spec when there is one.

## [Unreleased]

## [0.2.0] - 2026-10-07

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

## [0.1.0] - 2026-10-06

Baseline, as found in the repository when this changelog was started. The
version string was already `0.1.0`; no tag exists for it.

### Added

- Discrete-time Python engine (`elevsim/`, standard library only) with
  configurable floors, cars, capacity, timing and passenger traffic.
- Five algorithms: `collective`, `scan`, `round_robin`, `nearest_car`, `eta`.
- Batch comparison over seeded, strategy-independent passengers, with JSON/CSV output.
- CLI (`list`, `run`, `compare`, `viewer`) and scenario files under `scenarios/`.
- Single-page animated viewer that runs the engine in the browser via Pyodide,
  with precomputed runs for every strategy and a fallback mode without the engine.
- GitHub Actions workflow running the tests on Python 3.10, 3.12 and 3.13 (2026-10-07).
