# Changelog

All notable changes are listed here, newest first. The version lives in
`elevsim/__version__` (`elevsim/__init__.py`) and follows
[Semantic Versioning](https://semver.org/) while still in 0.x:

| Change | Bump |
| --- | --- |
| New feature or metric | minor (`0.1.0` to `0.2.0`) |
| Bug fix, docs or config only | patch (`0.2.0` to `0.2.1`) |
| Breaking change to config keys or JSON output | minor while in 0.x |

The version is bumped in the last commit of the implementation branch, so the
PR into `dev` is complete when it is opened. The git tag is created on `main`
when `dev` is promoted. Each entry links to its design spec when there is one.

## [Unreleased]

### Planned for 0.2.0

- Full-day office scenario (`traffic: "office_day"`): employees with fixed desk
  floors, arrivals from an hour before 08:00 with late arrivals, a 12:00-13:00
  lunch (out of the building or cafeteria only), mid-day meeting and cafeteria
  trips, an evening exodus with some staying late, and per-run day variation.
- Energy metric (`energy_kwh`) with a replaceable `EnergyModel`, starting with a
  simple load-weighted distance model.
- `max_time` default becomes `None` (auto): 4 hours for existing traffic, as before,
  and derived from the latest arrival for `office_day`.
- Design: `docs/superpowers/specs/2026-10-08-office-day-scenario-design.md`

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
