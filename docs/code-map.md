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
| `scenarios/*.json` | named scenario presets: the viewer's dropdown, and its `description` is the note shown under it | add a preset, add a `variations` entry, or reword how a scenario is explained |
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
