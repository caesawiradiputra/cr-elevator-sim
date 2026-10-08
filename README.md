# Elevator Algorithm Simulator

A simulation lab for testing and comparing elevator control algorithms under
identical, reproducible conditions.

* **Python engine** (`elevsim/`, standard library only): a discrete-time
  building simulation with configurable floors, cars, capacity, timing and
  passenger traffic.
* **Batch comparison**: every algorithm runs on exactly the same seeded
  passengers; results are averaged over several seeds and written as JSON/CSV.
* **Animated viewer** (`viewer/`): a single HTML page that runs the same Python
  engine in the browser (via Pyodide), animates the building, and runs
  comparisons with charts.

## Quick start

```bash
python3 -m elevsim list                                   # available algorithms
python3 -m elevsim compare --config scenarios/office_lunch.json --seeds 10 --out results
python3 -m elevsim run -s eta --floors 12 --elevators 3 --traffic up_peak --trace trace.json
python3 -m elevsim run -s eta --config scenarios/office_day.json --employees 100   # one full office day
python3 -m elevsim viewer                                 # writes dist/viewer.html
python3 -m unittest discover -s tests -t .                # tests
```

Open `dist/viewer.html` in a browser. It loads Pyodide from the jsDelivr CDN
the first time; without network it still shows the built-in demo run and can
open trace files written by `run --trace`.

## Configuration

Any option can come from a scenario file (`scenarios/*.json`) and be
overridden on the command line. A scenario file may also list `variations`
(a `name`, a `description` and the settings they override); the viewer shows them
in a Variation dropdown, and the engine and CLI ignore them.

| Key | Default | Meaning |
| --- | --- | --- |
| `floors`, `elevators`, `capacity` | 10, 3, 8 | building size |
| `lobby_floor` | 0 | floor index of the lobby |
| `floor_travel_time` | 1.5 s | time to move one floor |
| `door_time` | 2.0 s | time to open, and separately to close, the doors |
| `board_time` | 1.0 s | time per passenger getting in or out |
| `passengers` | 200 | total passengers generated |
| `arrival_rate` | 20 / min | mean Poisson arrival rate |
| `traffic` | `uniform` | `uniform`, `up_peak`, `down_peak`, `lunch` (the rush down at the start of lunch), `lunch_balanced` (both ways), `interfloor`, `office_day`, or a mix dict `{"incoming": .5, "outgoing": .3, "interfloor": .2}` |
| `origin_weights`, `destination_weights` | none | per-floor weights that override the traffic pattern |
| `idle_parking` | `stay` | `stay` or `lobby` (idle cars return to the lobby after `park_delay`) |
| `seed` | 1 | passenger generation seed |
| `dt` | 0.5 s | simulation tick |
| `bottleneck_queue` | 6 | a floor queue at or above this counts as a bottleneck |
| `long_wait` | 60 s | waits at or above this count as long waits |
| `max_time` | auto | hard stop in seconds. Auto is 4 hours, or for `office_day` the last request plus `office.drain_margin_s`. An explicit value that is too small for `office_day` is an error |
| `employees` | 300 | headcount for `traffic: "office_day"` (`passengers` and `arrival_rate` do not apply to it) |
| `day_start`, `day_end` | `06:45`, `20:00` | `office_day` window: simulation time 0 is `day_start`; no request is generated after `day_end` |
| `day_variation` | 1.0 | 0 = day-level shares exactly as configured, 1 = default spread between seeds. Individual employee schedules always depend on the seed |
| `office` | `{}` | overrides for the `office_day` defaults (see below); unknown keys are rejected |
| `energy_model`, `energy_base`, `energy_per_passenger` | `simple`, 0.01, 0.002 | energy model and its constants (kWh per floor moved, extra kWh per passenger per floor) |

## Algorithms

| Name | Kind | Idea |
| --- | --- | --- |
| `collective` | no dispatcher | LOOK: every car answers every call, keeps going while there is work ahead |
| `scan` | no dispatcher | full end-to-end sweeps whenever any call exists |
| `round_robin` | dispatcher | each new hall call goes to the next car in turn |
| `nearest_car` | dispatcher | classic "figure of suitability": same-direction approaching car first |
| `eta` | dispatcher | lowest estimated pickup time along each car's route, re-planned every 5 s |

Add your own by subclassing `Strategy` or `DispatcherStrategy` in
`elevsim/strategies/` and registering it in `elevsim/strategies/__init__.py`.
The hooks are documented in `elevsim/strategies/base.py`.

## Metrics

Average / 95th percentile / maximum wait, average travel time in the car,
average and maximum total journey, share of long waits, passengers served,
time to deliver everyone, elevator utilization (non-idle share), average car
occupancy, idle time, floors travelled, stops, average and longest floor
queues, bottleneck episodes and duration (per floor too), and full-car
pass-bys (a full car left people behind). Per-elevator and per-floor
breakdowns are in the JSON output.

**Energy** (`energy_kwh`) is a comparative estimate: the `simple` model charges a cost per floor a
car moves plus a cost per passenger on board per floor. Its constants are uncalibrated, so use the
number to rank algorithms against each other, not as an absolute figure. Idle and door time are
recorded but not charged. The model is replaceable (`elevsim/energy.py`).

## Office-day scenario

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

Every tick: arriving passengers join their floor's up or down queue and press
the hall button; dispatcher strategies assign calls; each car advances through
`idle → moving → opening → loading → closing`. Strategies decide which way an
idle car goes and whether a moving car stops at the floor it reaches. At a
stop, riders get out first, then waiting passengers going the car's way board
one at a time until it is full.
