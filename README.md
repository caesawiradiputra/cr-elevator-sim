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
python3 -m elevsim viewer                                 # writes dist/viewer.html
python3 -m unittest discover -s tests -t .                # tests
```

Open `dist/viewer.html` in a browser. It loads Pyodide from the jsDelivr CDN
the first time; without network it still shows the built-in demo run and can
open trace files written by `run --trace`.

## Configuration

Any option can come from a scenario file (`scenarios/*.json`) and be
overridden on the command line.

| Key | Default | Meaning |
| --- | --- | --- |
| `floors`, `elevators`, `capacity` | 10, 3, 8 | building size |
| `lobby_floor` | 0 | floor index of the lobby |
| `floor_travel_time` | 1.5 s | time to move one floor |
| `door_time` | 2.0 s | time to open, and separately to close, the doors |
| `board_time` | 1.0 s | time per passenger getting in or out |
| `passengers` | 200 | total passengers generated |
| `arrival_rate` | 20 / min | mean Poisson arrival rate |
| `traffic` | `uniform` | `uniform`, `up_peak`, `down_peak`, `lunch`, `interfloor`, or a mix dict `{"incoming": .5, "outgoing": .3, "interfloor": .2}` |
| `origin_weights`, `destination_weights` | none | per-floor weights that override the traffic pattern |
| `idle_parking` | `stay` | `stay` or `lobby` (idle cars return to the lobby after `park_delay`) |
| `seed` | 1 | passenger generation seed |
| `dt` | 0.5 s | simulation tick |
| `bottleneck_queue` | 6 | a floor queue at or above this counts as a bottleneck |
| `long_wait` | 60 s | waits at or above this count as long waits |

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

## How the engine works

Every tick: arriving passengers join their floor's up or down queue and press
the hall button; dispatcher strategies assign calls; each car advances through
`idle → moving → opening → loading → closing`. Strategies decide which way an
idle car goes and whether a moving car stops at the floor it reaches. At a
stop, riders get out first, then waiting passengers going the car's way board
one at a time until it is full.
