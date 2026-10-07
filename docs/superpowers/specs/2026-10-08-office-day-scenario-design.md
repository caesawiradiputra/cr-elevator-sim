# Full-day office scenario and energy metric: design

Status: **draft v3, two external reviews incorporated, awaiting user approval**
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
| Headcount | The number of employees is set. Each stays in the building until they go home. |
| Energy | Measure elevator movement energy as an effectiveness metric. Start simple, allow a more complex model later. |
| Variation | Each run may deviate from the defaults. |

Decisions taken in the session:

- Building and headcount defaults are configurable, defaulting to 15 floors,
  4 cars, capacity 10 and about 300 employees (desks spread evenly over floors 1-14).
- The cafeteria and the lobby are floor 0.
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
  3. short cafeteria breaks (desk -> 0 -> desk);
  4. lunch: out of the building (desk -> lobby, back later lobby -> desk),
     cafeteria only (desk -> 0 -> desk), or at the desk;
  5. go home (desk -> lobby).
- **Consistency.** Segments for one person are laid out sequentially, so a trip's
  from-floor always equals where the person is. A random segment that would
  overlap another is dropped, never squeezed in.
- **Clock.** Time 0 is `day_start` (default 06:45). The day window is the config
  pair `day_start` and `day_end` (default 20:00, the latest planned departure),
  not hard-coded times, so a longer window such as 00:00-23:59 is a config
  change (see Future work). Every generated trip falls inside the window.
  `max_time` is derived so the whole day fits (see the timeline invariant below).
- **Passenger count.** The trip count is derived (about 7 trips per person, so
  about 2,000 for 300 employees), and `employees` is the user-facing size. The
  derived count is written back to `passengers` in the resolved config so results
  never show a misleading value. The CLI rejects `--passengers` together with
  `office_day`, instead of silently ignoring it.
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
  engine (desk -> floor 0 -> desk). They differ only in the absence duration:
  out of the building is longer (default 30-60 minutes), cafeteria only is
  shorter (default 15-40 minutes).
- **Timeline invariant.** `max_time` is at least the latest generated arrival plus
  a drain margin (default 1 hour), so no generated trip is cut off.
  - `max_time` changes from a fixed `4 * 3600.0` to `float | None = None`, meaning
    "auto". The engine reads it in one place (`engine.py`, the `run` loop).
  - Auto for existing traffic is exactly the old 4 hours, so current scenarios
    behave identically. Auto for `office_day` is the latest arrival plus the drain
    margin.
  - An explicit `max_time` is never overridden. If it is smaller than the
    `office_day` requirement, generation raises a `ValueError` naming both values.
- **Temporal order.** Within one employee's trips, each trip's arrival time is
  after the previous trip's arrival time plus a minimum gap (default 60 s) for the
  activity in between, so the order is strictly increasing.

**Day variation contract.** With `day_variation = 0` the configured day-level
values are used exactly. With a value above 0 each day-level value (late share,
going-out lunch share, stay-late share, arrival-peak shift) is drawn uniformly
from `value ± spread x day_variation`, using the seed. Shares are clamped to
0-1, and the lunch shares are renormalized to sum to 1. The result is
deterministic and bounded; the exact distribution is an implementation detail.

Default day shape (all values are config keys; `±` is the day-level deviation):

| Phase | Default |
| --- | --- |
| Arrival | 85% arrive 07:00-08:00 with a peak near 07:50. 15% (±5 points) arrive late, 08:00-09:30, on a tail. |
| Lunch (12:00-13:00) | 40% (±10) leave the building, 30% go to the cafeteria and back to the desk, 30% stay at the desk. Departures spread about 30 minutes either side of 12:00. |
| Mid-day (09:00-17:00) | On average about 1 meeting trip and 0.7 cafeteria breaks per person, at random times in working hours. |
| Going home | 80% leave 17:00-17:45. 20% (±8) stay late and leave 17:45-20:00. |

The lunch split and the stay-late share are placeholders. They can be replaced
with real numbers.

### 3.2 Idle fast-forward (engine, small change)

A 13-hour day is about 94k ticks per run at `dt = 0.5 s`. Five algorithms times
several seeds in the browser (Pyodide) could be slow.

When all cars are idle, nobody is waiting and the next arrival is far away, the
engine jumps the clock forward and credits the skipped time to idle.

- Fast-forward is an execution optimization only. With it on or off, the same
  config, seed and algorithm must give identical per-passenger board and alight
  times, identical per-elevator statistics and identical summary metrics. This
  is tested on a short scenario by comparing the full result, not only the
  aggregates.
- A jump always lands on the tick grid (a multiple of `dt`), so the rounding of
  `t` matches the tick-by-tick run.
- Parking behaviour (`idle_parking: "lobby"`, `park_delay`) must still happen at
  the correct simulated times, so the jump stops at those moments.
- If profiling shows the full day runs fast enough without it, drop this section.

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
  the JSON and kWh per passenger is derived.

### 3.4 Config, API and CLI

- New keys: `employees`, `day_start`, `day_end`, `day_variation`, the shares and times from
  the table above, `energy_model` and the energy constants.
- Validation: shares in 0-1, times in order, `day_start < day_end`, `employees >= 1`, `max_time` covers
  the day (see the timeline invariant).
- `office_day` is not a traffic mix like the entries in `TRAFFIC_PATTERNS`, so it
  is registered as a separate scheduler name. `validate()`, the CLI `--traffic`
  choices and the viewer dropdown must all accept it.
- New `scenarios/office_day.json` (15 floors, 4 cars, capacity 10, 300 employees).
  `--traffic office_day` works on the CLI.
- `README.md`: document the new keys and the metric.

### 3.5 Viewer

- `office_day` appears in the scenario dropdown, and `energy_kwh` shows up in
  "Whole run" and the Compare charts, which both read `METRICS`.
- The time display and the "people waiting" chart need a full-day clock
  (07:50 instead of 2:20).
- **Checked in `viewer/app.js` and `viewer_build.py` (2026-10-08):**
  - Metric labels and units are read generically from `METRICS`, so `energy_kwh`
    and its unit appear in the Compare table and bar chart without special code.
  - The form rejects `passengers` outside 1-3000 (`app.js`, around line 73). For
    `office_day` it must validate `employees` instead. The derived count of about
    2,000 for 300 employees is near that cap.
  - `api.run(record=True)` records a frame every 0.5 s by default. A 13-hour day
    is about 95k frames per run, which is large to build and ship to the browser.
  - `viewer_build.py` lists every file in `scenarios/` as a dropdown preset, but
    precomputes runs and a 5-seed comparison only for `DEMO_PRESET`
    (`office_lunch`), or for all presets with `demo_all`.
  - The viewer reads `trace.frame_interval` from the result, so a coarser
    interval needs no change to how frames are consumed. Playback advances by
    `dt x speed` per animation step.
- **Decisions:**
  - **Frame interval.** Simulation `dt` stays 0.5 s. The viewer trace interval is
    separate and is chosen so a run has at most about 10,000 frames:
    `frame_interval = max(requested, max_time / 10000)`, about 5 s for a full day.
    Whether the viewer interpolates car positions between frames is to be
    checked in the plan; if it does not, the animation needs it for 5 s frames.
  - **Build precompute.** `office_day` is excluded from precompute even under
    `demo_all`, through a `NO_PRECOMPUTE` set in `viewer_build.py`. Its dropdown
    preset still exists and runs on the live Pyodide engine. Without the engine
    the viewer shows its existing "pick a precomputed scenario" message.
  - **Playback speed.** At the current top speed of 8x a 13-hour day takes more
    than 1.5 hours to watch, so the speed selector gains faster options (for
    example 60x and 300x) when the scenario is a full day.
- **Still to do in the plan:** the full-day clock format and the "people waiting"
  chart axis in `app.js`.

### 3.6 Testing (standard library `unittest`, CI matrix 3.10 / 3.12 / 3.13)

- Same seed gives the same list, and the list is strategy-independent (existing contract).
- Different seeds give different day profiles when `day_variation > 0`, and
  identical shapes when it is `0`.
- Every employee's trips chain: each from-floor equals the previous destination,
  and the last trip ends in the lobby.
- Every trip is served in a full run of each strategy on `office_day`.
- Fast-forward gives metrics identical to the tick-by-tick run.
- The energy model gives zero for a stationary run and more energy for longer
  trips and heavier loads.
- Exact raw counters on a tiny scenario: one car, floors 0 -> 2, two passengers,
  gives `floors_travelled = 2` and `loaded_floor_distance = 4`, and the exact
  `simple` result for known constants.
- Strategy independence for `office_day` specifically: the passenger list is
  identical for every registered strategy, extending the existing test.
- Scheduler rules: the realized meeting rate stays at or below the candidate
  rate, each employee's trips are strictly increasing in time, and
  `--passengers` with `office_day` is rejected.
- `max_time`: auto for `office_day` covers the latest arrival plus the drain
  margin, an explicit smaller value raises `ValueError`, and auto for existing
  traffic is still 4 hours (a legacy scenario behaves exactly as before).
- Frame cap: a full-day recorded run has at most about 10,000 frames.

## 4. Risks and open questions

- Run time of a full day in the browser (see 3.2).
- Default shares are guesses until real numbers are supplied.
- Viewer: trace size, precompute and playback speed are decided in 3.5. Still open
  for the plan: whether the viewer interpolates between 5 s frames, the
  passenger cap, and the clock and chart-axis format.
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
