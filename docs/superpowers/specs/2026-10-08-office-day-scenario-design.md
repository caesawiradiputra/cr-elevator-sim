# Full-day office scenario and energy metric: design

Status: **draft, awaiting user review** (brainstorming, architectural path).
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
- **Clock.** Time 0 is `day_start` (default 06:45). `max_time` is raised so the
  whole day fits.
- **Passenger count.** The trip count is derived, so `passengers` is ignored for
  this traffic and `employees` is the user-facing size.

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

- Results must be identical to a tick-by-tick run. This is tested on a short scenario.
- Parking behaviour (`idle_parking: "lobby"`, `park_delay`) must still happen at
  the correct simulated times, so the jump stops at those moments.
- If profiling shows the full day runs fast enough without it, drop this section.

### 3.3 Energy (`elevsim/energy.py`, new, plus engine counters)

- The engine records only raw facts per car: distance moved up and down weighted
  by load, time idle and time with doors open. These are plain counters on
  `Elevator`, like `floors_travelled` today.
- An `EnergyModel` turns the counters into kWh at summary time.
  - `simple`: `energy = distance x (base + k x load)`, constants configurable.
    It uses load so that an empty car and a full car are not scored the same.
  - Later models (`counterweight`, `full`) are new classes plus a change to
    `energy_model`. They need no engine or scheduler change.
- `energy_kwh` is added to `METRICS` (lower is better). Per-elevator energy is in
  the JSON and kWh per passenger is derived.

### 3.4 Config, API and CLI

- New keys: `employees`, `day_start`, `day_variation`, the shares and times from
  the table above, `energy_model` and the energy constants.
- Validation: shares in 0-1, times in order, `employees >= 1`.
- New `scenarios/office_day.json` (15 floors, 4 cars, capacity 10, 300 employees).
  `--traffic office_day` works on the CLI.
- `README.md`: document the new keys and the metric.

### 3.5 Viewer

- `office_day` appears in the scenario dropdown, and `energy_kwh` shows up in
  "Whole run" and the Compare charts, which both read `METRICS`.
- The time display and the "people waiting" chart need a full-day clock
  (07:50 instead of 2:20).
- **Open item:** `viewer/app.js` has not been read in detail yet. This section
  must be re-checked before the plan is written.

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

## 4. Risks and open questions

- Run time of a full day in the browser (see 3.2).
- Default shares are guesses until real numbers are supplied.
- Viewer changes are not yet scoped (see 3.5).
- The `simple` energy constants are arbitrary units until calibrated, so absolute
  kWh values are only meaningful for comparing algorithms against each other.

## 5. Out of scope

- Employee-aware engine behaviour (people reacting to queues). Rejected because
  it would make traffic depend on the strategy.
- Counterweight, regeneration and standby-power energy models. The design leaves
  room for them, but they are not built now.
- Pre-generated trace files.

## 6. Next steps

1. User reviews this spec.
2. After approval, invoke `writing-plans` to produce the implementation plan.
