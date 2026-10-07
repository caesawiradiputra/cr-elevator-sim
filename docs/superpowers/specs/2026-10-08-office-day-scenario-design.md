# Full-day office scenario and energy metric: design

Status: **approved (v5); amended on 2026-10-08 while planning: 3.2 (fast-forward dropped after profiling), 3.4 (`office` dict instead of flat keys), 3.5 (frame cap divisor 9997, `office_day` only). The amendments need the user's confirmation.**
(brainstorming, architectural path).
Date: 2026-10-08. Branch: `feat/office-day-scenario`.
Current version: `0.1.0`. Target version: `0.2.0` (minor: new feature), a plan
that can change before release. The bump to `__version__` happens in the last
commit of the implementation branch. Changelog: `CHANGELOG.md` (Unreleased).

## 1. Goal

Add a scenario that simulates a whole office day for a fixed headcount of
employees, and add an energy-use metric so algorithms can be compared on
effectiveness as well as waiting time.

Success criteria:

- One run covers arrival (from about 1 hour before 08:00), the working day,
  the 12:00-13:00 lunch break and the evening exodus.
- Every employee is a continuing individual: a fixed desk floor, trips that chain
  correctly, and a final trip home to the lobby.
- Runs are deterministic per seed and identical for every algorithm, but
  different seeds give days with different shapes ("each run can have some
  deviation").
- `energy_kwh` appears in the summary, the CLI and the viewer, and the energy
  model can be replaced by a more detailed one later without touching the engine.

## 2. Requirements (from the user)

| Phase | Behaviour |
| --- | --- |
| Arrival | Office hours 08:00-17:00. People start arriving 1 hour before, and some arrive late. |
| Lunch 12:00-13:00 | Some leave the building. Some only go to the cafeteria (ground floor) and return to their desk to eat. |
| Mid-day | Movement between floors for meetings, and short cafeteria breaks. |
| 17:00 | Most go home, some stay late. |
| Headcount | The number of employees is set. Each follows a continuous daily schedule, apart from the explicit lunch-out absence, and ends the day by going home through the lobby. |
| Energy | Measure elevator movement energy as an effectiveness metric. Start simple, allow a more complex model later. |
| Variation | Each run may deviate from the defaults. |

Decisions taken in the session:

- Building and headcount defaults are configurable, defaulting to 15 floors,
  4 cars, capacity 10 and about 300 employees (desks spread evenly over floors 1-14).
- The cafeteria is on the lobby floor (`lobby_floor`, default 0). The scheduler
  always uses `cfg.lobby_floor`, never a literal 0, and desks are never on it.
- Approach 1: a separate scheduler produces the existing `Passenger` list. The
  engine does not become employee-aware.

## 3. Design

### 3.1 Day scheduler (`elevsim/schedule.py`, new)

- `traffic: "office_day"` makes `generate_passengers()` delegate to the
  scheduler. It returns the same `Passenger` list, sorted by arrival time, so
  the engine, `compare` and every strategy are unchanged.
- **Day profile.** The seed first draws the day profile: the headline shares
  and the arrival-peak shift, scaled by `day_variation`. `0` gives an identical
  day shape for every seed, `1` is the default spread.
- **Employees.** The scheduler creates `employees` people, each with a fixed desk
  floor (even over non-lobby floors, or per `origin_weights` when given) and
  their own random times.
- **Day as segments.** Each person's day is a sequence of timed segments:
  1. arrive (lobby -> desk);
  2. mid-day meetings (desk -> floor F -> desk);
  3. short cafeteria breaks (desk -> lobby floor -> desk);
  4. lunch: out of the building (desk -> lobby, back later lobby -> desk),
     cafeteria only (desk -> lobby floor -> desk), or at the desk;
  5. go home (desk -> lobby).
- **Consistency and priority.** Segments for one person are laid out sequentially,
  so a trip's from-floor always equals where the person is.
  1. **Fixed segments first:** arrival, lunch and go-home are placed before
     anything else. They are never dropped, so everyone enters, has lunch as
     assigned, and leaves.
  2. **Optional segments second:** meetings and cafeteria breaks are candidates.
     Each candidate is a whole round trip (out and back) and is kept or dropped
     as one unit, so nobody is left on the wrong floor.
  3. **Overlap includes the gap:** a candidate is dropped if any of its requests
     would fall within the minimum gap (see Temporal order) of another segment's
     requests, never squeezed in.
  4. **Window:** the arrival-peak shift is clamped so no arrival falls before
     `day_start`, and every request is at or before `day_end`.
- **Clock.** Time 0 is `day_start` (default 06:45). The day window is the config
  pair `day_start` and `day_end` (default 20:00, the latest planned departure),
  not hard-coded times, so a longer window such as 00:00-23:59 is a config
  change (see Future work). Every generated trip falls inside the window.
  The simulation horizon (`max_time`) is resolved from the generated passengers
  (see the timeline invariant below).
- **Passenger count.** The trip count is derived (about 7 candidate trips per
  person, so up to about 2,000 for 300 employees, fewer after dropped candidates),
  and `employees` is the user-facing size. `cfg.passengers` is **ignored** for
  `office_day` and the config is never mutated, because `compare()` generates
  passengers per seed on a copy of the config and `Simulation` skips generation
  when it is given a passenger list. Instead the per-run result reports the real
  count (`passengers_total` in the summary), and the CLI compare header reads it
  from the results. The CLI rejects `--passengers` together with `office_day`
  (it tests `args.passengers is not None`, because a config loaded from file
  always carries a `passengers` value).
- **Internal representation.** Employees (id and fixed desk floor) are created
  separately from any day's trips. An `OfficeDay` is one day built from those
  employees: the day profile and each employee's ordered trips, with a
  `day_index` that defaults to 0. The scheduler flattens it to the `Passenger`
  list. The engine boundary does not change, and the timeline logic can be
  unit-tested without running a simulation. A multi-day week later becomes a loop
  over `OfficeDay` with the same employees (see Future work).

**Scheduler contract.** The scheduler is a deterministic demand generator:

- For a given config and seed it always produces the same schedule, and the
  schedule never depends on the strategy.
- Each employee's trips form a valid location chain (every from-floor equals the
  previous destination), and the last trip of every employee ends in the lobby.
- The configured meeting and break rates are **candidate** rates. A candidate
  that would overlap another segment is discarded, so the realized number of
  trips can be lower than the configured rate. This is documented, and a test
  measures the realized rate on a large headcount.
- Lunch out of the building and lunch in the cafeteria are the same trip to the
  engine (desk -> lobby floor -> desk). They differ only in the absence duration:
  out of the building is longer (default 30-60 minutes), cafeteria only is
  shorter (default 15-40 minutes).
- **Timeline invariant.** `max_time` is at least the latest generated
  `Passenger.arrival` plus a drain margin (default 1 hour), so no generated trip
  is cut off. `Passenger.arrival` is the moment the person presses the hall
  button, which the scheduler knows before the simulation runs (it is not the
  time the person reaches the destination). `day_end` limits when the scheduler
  may generate demand; `max_time` is the simulation horizon needed to finish
  serving it. Example: the latest request at 19:57 and a 1-hour margin give a
  `max_time` equal to 20:57.
  - `max_time` changes from a fixed `4 * 3600.0` to `float | None = None`, meaning
    "auto". `cfg.max_time` stays `None` and is never overwritten with a resolved
    value, so a copy made by `replace(cfg, seed=n)` resolves its own horizon.
  - The horizon is resolved in `Simulation.__init__` from `self.passengers`,
    because that is the one place every path goes through (CLI, `compare`, the
    viewer and the tests). Auto for existing traffic is exactly the old 4 hours,
    so current scenarios behave identically. Auto for `office_day` is the latest
    `Passenger.arrival` plus the drain margin. The resolved value is reported as
    `horizon` in the summary.
  - An explicit `max_time` is never overridden. If it is smaller than the
    `office_day` requirement, `Simulation.__init__` raises a `ValueError` naming
    both values. This cannot be a `validate()` check, because arrivals are not
    known until generation.
- **Temporal order.** Within one employee's trips, each trip's `Passenger.arrival`
  is after the previous trip's `Passenger.arrival` plus a minimum gap, so the
  order is strictly increasing. The default gap is 600 s, equal to the shortest
  planned dwell (a 10-minute cafeteria break). The scheduler is strategy-independent
  and cannot know real ride times, so the gap is a conservative proxy for "the
  person has arrived and spent some time there".
  - A next request can still come before the previous trip's actual `alight` time
    when an algorithm is slow or the building is congested. That is a symptom of
    the algorithm, not a scheduler bug, and it is measured, not forbidden.
  - **Acceptance criterion.** On the default `office_day` scenario over 5 seeds,
    the share of consecutive trip pairs where the next `arrival` is before the
    previous `alight` is at most 1% for `eta` and `collective`. If a default
    scenario exceeds that, the gap default is raised, not the algorithm changed.
    The share is computed and reported for every strategy (a high value for
    `scan` or `round_robin` is useful information about those algorithms).
- **Boundary check.** `Passenger` (`elevsim/model.py`) carries `id`, `arrival`,
  `origin` and `dest`, with the direction derived. That is all the scheduler
  needs to emit, so no engine-side model change is required.

**Day variation contract.** With `day_variation = 0` the configured day-level
values are used exactly, so the day-level values (the headline shares and the
peak shift) are identical for every seed. Individual employee schedules still
depend on the seed: their own times and choices are random draws from the same
configured distributions, so different seeds still give different trips. With a value above 0 each day-level value (late share,
going-out lunch share, stay-late share, arrival-peak shift) is drawn uniformly
from `value ± spread x day_variation`, using the seed. Shares are clamped to
0-1, and the lunch shares are renormalized to sum to 1. The result is
deterministic and bounded; the exact distribution is an implementation detail.

Default day shape (all values are config keys; `±` is the day-level deviation):

| Phase | Default |
| --- | --- |
| Arrival | 85% arrive 07:00-08:00 with a peak near 07:50. 15% (±5 points) arrive late, 08:00-09:30, on a tail. |
| Lunch (12:00-13:00) | 40% (±10) leave the building, 30% go to the cafeteria and back to the desk, 30% stay at the desk. Departures spread about 30 minutes either side of 12:00. |
| Mid-day (09:00-17:00) | On average about 1 meeting trip and 0.7 cafeteria breaks per person, at random times in working hours. A meeting lasts 30-60 minutes and a break 10-20 minutes. |
| Going home | 80% leave 17:00-17:45. 20% (±8) stay late and leave 17:45-20:00. |

The lunch split and the stay-late share are placeholders. They can be replaced
with real numbers.

### 3.2 Idle fast-forward (dropped from 0.2.0)

The spec allowed dropping this optimization if a full day ran fast enough without
it. A throwaway prototype of the scheduler run on the unmodified engine
(2026-10-08, 300 employees, 15 floors, 4 cars, `dt = 0.5 s`, about 95k ticks)
took 0.7-1.1 s per full-day run natively for each of the five strategies, over
seeds 1, 2, 3 and 7. That is fast enough, so 0.2.0 has **no** fast-forward, no
`skip_idle` strategy hook and no engine timing change. The engine keeps stepping
every tick.

Still to check in the browser (Pyodide is slower than native Python): the plan
includes a manual timing of one live full-day run. If it is unacceptably slow, the
optimization comes back as its own change; the constraints found in review are
kept in `docs/ideas.md` so they are not lost. It becomes mandatory for the 24-hour
window and multi-day weeks.

### 3.3 Energy (`elevsim/energy.py`, new, plus engine counters)

- **Energy accounting contract.** The engine records movement as discrete floor
  transitions. Passengers only board or leave while a car is stopped, so a car's
  load is constant across one transition. For each car:
  - `floors_travelled` (exists today): the number of floor transitions, including
    empty and parking moves.
  - `loaded_floor_distance` (new): the sum, over every floor transition, of the
    passenger count on board during it. Load is the passenger count, not a ratio.
  - idle time and door-open time (opening + loading + closing) already exist in
    `time_in_state`. They are raw telemetry for future models.
  - Example: one car, floors 0 -> 1 -> 2, two passengers on board throughout, gives
    `floors_travelled = 2` and `loaded_floor_distance = 4`.
- The energy calculation is deterministic and depends on the strategy only
  through the resulting movement and load.
- An `EnergyModel` turns the counters into kWh at summary time.
  - `simple` (movement energy only):
    `energy = floors_travelled x base + loaded_floor_distance x per_passenger`,
    constants configurable. It uses load so that an empty car and a full car are
    not scored the same. Idle time and door-open time do **not** affect
    `energy_kwh` in 0.2.0.
  - Later models (`counterweight`, `full`) are new classes plus a change to
    `energy_model`. They need no engine or scheduler change.
- The metric keeps the name `energy_kwh` because kWh is the intended unit. In
  0.2.0 the `simple` constants are calibration parameters, not physical
  measurements, so the value is a **comparative estimate**: meaningful for ranking
  algorithms against each other, not as an absolute figure. The README and the
  config comments say so.
- `energy_kwh` is added to `METRICS` (lower is better). Per-elevator energy is in
  the JSON, and kWh per passenger is derived (0 when nobody was served).

### 3.4 Config, API and CLI

- New keys: `employees`, `day_start`, `day_end`, `day_variation`, `energy_model`,
  `energy_base` and `energy_per_passenger`, plus one dict key `office` that holds
  the shares, time windows, rates, durations, minimum gap and drain margin from
  the table above (unknown keys are rejected, defaults are documented in the
  README). One dict instead of about 25 flat keys keeps the config and the viewer
  form readable.
- Validation in `validate()`: shares in 0-1, times in order,
  `day_start < day_end`, `employees >= 1`. The `max_time` check happens in
  `Simulation.__init__` (see the timeline invariant).
- `office_day` is not a traffic mix like the entries in `TRAFFIC_PATTERNS`, so it
  is registered as a separate scheduler name. `validate()`, the CLI `--traffic`
  choices and the viewer dropdown must all accept it.
- New `scenarios/office_day.json` (15 floors, 4 cars, capacity 10, 300 employees).
- CLI (`elevsim/cli.py`): `--traffic` choices come from `TRAFFIC_PATTERNS` today, so
  `office_day` is added to the choices; a `--employees` flag is added to the
  override list; `energy_kwh` is added to the hardcoded `TABLE_METRICS` and
  `SHORT` so it appears in the compare table.
- `README.md`: document the new keys and the metric.

### 3.5 Viewer

- `office_day` appears in the scenario dropdown, and `energy_kwh` is added to the
  places that hardcode metric lists (see the findings below).
- The time display and the "people waiting" chart need a full-day clock
  (07:50 instead of 2:20).
- **Checked in `viewer/app.js` and `viewer_build.py` (2026-10-08):**
  - Only the Compare bar-chart metric selector reads `METRICS` (`DATA.metrics`).
    The "Whole run" rows (`renderFinal`) and the Compare table columns (`cols`)
    are hardcoded lists, so `energy_kwh` must be added to both.
  - `readForm()` sends only the fields in `CFG_FIELDS`, so a preset's other keys
    (`employees`, `day_*`, `energy_*`) would be silently dropped and a live
    `office_day` run would use defaults. The traffic `<select>` is static HTML
    without an `office_day` option, and `fillForm` would leave it empty.
  - The form rejects `passengers` outside 1-3000 (`app.js`, around line 73). For
    `office_day` it validates `employees` instead. The derived count of up to
    about 2,000 for 300 employees is near that cap.
  - `api.run(record=True)` records a frame every 0.5 s by default. A 13-hour day
    is about 95k frames per run, which is large to build and ship to the browser.
  - `viewer_build.py` lists every file in `scenarios/` as a dropdown preset, but
    precomputes runs and a 5-seed comparison only for `DEMO_PRESET`
    (`office_lunch`), or for all presets with `demo_all`.
  - The viewer reads `trace.frame_interval` from the result, so a coarser
    interval needs no change to how frames are consumed. Playback advances by
    `dt x speed` per animation step.
- **Decisions:**
  - **Form wiring.** `readForm()` starts from the selected preset's full config
    and overlays the form fields, so non-form keys reach the engine. An
    `office_day` option is added to the traffic select. For `office_day` the
    form shows an `employees` input and hides `passengers` and `arrival_rate`,
    which do not apply.
  - **Frame interval.** Simulation `dt` stays 0.5 s. The viewer trace interval is
    separate. A recorded trace has at most 10,000 frames, counting the initial
    frame and a possible final frame. For `office_day` the engine computes
    `frames_every = max(round(requested / dt), ceil(horizon / 9997 / dt))`
    (rounding up for the cap, because `round` could exceed it; 9997 leaves room
    for the initial frame, the final frame and one tick of slack) and the trace
    reports the effective interval `frames_every x dt`, not the requested one,
    because the viewer uses it to locate frames. About 5.5 s for a full day. The
    cap applies to `office_day` only: with the 4-hour default horizon it would
    widen the frames of every existing scenario.
  - **Playback with coarse frames.** The viewer is time-based: playback time
    advances in seconds and `frameAt` finds the surrounding frames. It
    interpolates a car's position only when the car moved at most 1.01 floors
    between frames, otherwise it snaps. With 5 s frames, moving cars will snap
    between positions. This is accepted for 0.2.0; smoother animation is an idea
    in `docs/ideas.md`.
  - **Build precompute.** `office_day` is excluded from precompute even under
    `demo_all`, through a `NO_PRECOMPUTE` set in `viewer_build.py`. Its dropdown
    preset still exists and runs on the live Pyodide engine. Without the engine
    the viewer shows its existing "pick a precomputed scenario" message.
  - **Playback speed.** The selector offers 1x to 32x, with 8x as the default. A
    13-hour day takes about 1.65 hours at 8x and about 25 minutes at 32x, so the
    selector gains faster options (for example 120x and 600x) for a full day.
- **Still to do in the plan:** the full-day clock format and the "people waiting"
  chart axis in `app.js`. The sparkline uses 400 samples, about 128 s apart over a
  full day, so its peak label can miss a short peak; accepted for 0.2.0.
  `liveStats` and `draw` cost O(passengers) per animation frame, which is
  negligible at about 2,000 passengers.

### 3.6 Testing (standard library `unittest`, CI matrix 3.10 / 3.12 / 3.13)

- Same seed gives the same list, and the list is strategy-independent (existing contract).
- Different seeds give different day-level values when `day_variation > 0`. With
  `day_variation = 0` the day-level values are identical across seeds, while the
  individual employee schedules still differ between seeds.
- Every employee's trips chain: each from-floor equals the previous destination,
  and the last trip ends in the lobby.
- Every trip is served in a full run of each strategy on `office_day`.
- The energy model gives zero for a stationary run and more energy for longer
  trips and heavier loads.
- Exact raw counters on a tiny scenario: one car, floors 0 -> 2, two passengers,
  gives `floors_travelled = 2` and `loaded_floor_distance = 4`, and the exact
  `simple` result for known constants.
- Strategy independence for `office_day` specifically: the passenger list is
  identical for every registered strategy, extending the existing test.
- Scheduler rules: the realized meeting rate is at or below the candidate rate
  and above a lower bound (so the test can fail in both directions), each
  employee's trips are strictly increasing in time, fixed segments (arrival,
  lunch, go-home) are never dropped, everyone ends in the lobby, and
  `--passengers` with `office_day` is rejected. Also run with a non-zero
  `lobby_floor`.
- Request-versus-alight ordering stays within the 1% acceptance criterion for
  `eta` and `collective`, and the share is reported for all strategies.
- `max_time`: auto for `office_day` covers the latest `Passenger.arrival` plus the
  drain margin, an explicit smaller value raises `ValueError` in
  `Simulation.__init__`, `cfg.max_time` is still `None` after a run, `compare()`
  over several seeds works (each seed resolves its own horizon), and auto for
  existing traffic is still 4 hours.
- Frame cap: a full-day recorded run has at most 10,000 frames, including the
  initial and final frames, and the reported `frame_interval` equals the effective
  one. Existing scenarios record exactly the same frames as before.

## 4. Risks and open questions

- Run time of a full day in the browser (see 3.2: about 1 s native, not yet
  measured under Pyodide).
- Default shares are guesses until real numbers are supplied.
- Viewer: form wiring, trace size, precompute, coarse-frame playback and speed are
  decided in 3.5. Still open for the plan: the clock and chart-axis format.
- `max_time` becoming `float | None` changes a public config default. Existing
  scenarios are unaffected (auto means 4 hours), but it is called out in the
  changelog.
- The default shares are placeholders, not real office statistics. The README
  should say so.
- The `simple` energy constants are uncalibrated, so `energy_kwh` is a comparative
  estimate (see 3.3).

## 5. Out of scope

- Employee-aware engine behaviour (people reacting to queues). Rejected because
  it would make traffic depend on the strategy.
- Counterweight, regeneration and standby-power energy models. The design leaves
  room for them, but they are not built now.
- Pre-generated trace files.
- Night and early-morning groups (security rounds, cleaners), a 24-hour window,
  multi-day weeks, and attendance states (holiday, sick, half day, truant). All
  are planned; see Future work.

## 6. Future work

Later ideas live in `docs/ideas.md`, an unordered list with no versions. Nothing
there has an order or a promise to be built, and each idea gets its own
brainstorming and spec when it is picked up. A version is assigned when a feature
ships, in release order (see `CHANGELOG.md`).

The ideas most related to this feature:

- Night and early-morning users (security checks, cleaners) and a 24-hour window.
  Cosmetic for algorithm ranking alone, but meaningful with a fuller energy model
  that counts idle and standby power. Idle fast-forward (3.2) would become
  mandatory, not optional.
- A fuller energy model (`counterweight`, standby and door power), using the raw
  telemetry already collected in this release.
- Multi-day weeks. Employees persist across days. Each day has a day type
  (workday, holiday, weekend) and each employee an attendance state (present,
  absent or sick, half day, late, truant). Needs day numbers in the viewer clock,
  a rethink of the frame and passenger caps, and per-day metrics.

Built now as hooks: the `day_start` / `day_end` window and the `Employee` /
`OfficeDay` split with `day_index`.

Open questions for those ideas, not for this release:

- Whether attendance states are drawn per employee per day or follow longer
  streaks (a sick person stays out for several days).
- Whether night groups are modeled as employees with a different `group` or as a
  separate generator.

## 7. Next steps

1. User reviews this spec.
2. After approval, invoke `writing-plans` to produce the implementation plan.
