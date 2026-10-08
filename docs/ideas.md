# Ideas and side notes

A parking lot for thoughts that are not committed work. Nothing here has an
order, a version or a promise to be built. When stuck or choosing what to do
next, scan this list and pick whatever looks interesting. When an idea is
picked up, it gets its own brainstorming and spec under `docs/superpowers/specs/`,
and gets a version at release time (see `CHANGELOG.md`). Mark it `[x]` when it
ships, and add the version and date.

Add new ideas at the top of their group. One line is enough. Add a source date
so the thought can be traced back to a conversation.

## Maintenance sessions

Dedicated sessions, separate from feature work. Behavior stays identical: run the
tests and the CI smoke commands before and after.

- [ ] Refactor session: review module boundaries and size (`engine.py`, `cli.py`,
  `viewer/app.js`), remove duplication, tighten names. (2026-10-08)
- [ ] Re-organize session: decide whether the layout still fits (for example a
  package for scheduling and energy, splitting the viewer script). (2026-10-08)
- [ ] Tech decisions session: lock the technology, modules and versions in use (Python 3.10/3.12/3.13,
  standard library only, Pyodide 0.26.4, GitHub Actions versions, Node for the JS syntax check,
  the unpinned `@playwright/mcp@latest`) in a `docs/tech-stack.md`, and write the upgrade strategy:
  when and how each is bumped, what to test, who decides. (2026-10-08)
- [ ] Typed models for the dict-shaped parts: small dataclasses (for example `TrafficMix`,
  `OfficeSettings`, `Scenario` with `Variation`) that load from and save to the same JSON, so a
  typo is caught and attribute access replaces string keys, while JSON stays the file format and
  the engine and Pyodide boundary keep passing plain dicts. `SimConfig` and the strategies are
  already classes. If plain dicts turn out simpler, keeping them and adding only the class
  names is fine. Better done as one refactor session after the scenario-file layout settles.
  (2026-10-08)
- [ ] Documentation session: README, `docs/code-map.md` and docstrings brought up
  to date with the code, written for a reader new to the codebase. (2026-10-08)
- [ ] Mentoring walkthrough after each mid or big feature: explain each module and
  where to find code to check or change by hand. (2026-10-08)

## Platform and architecture

- [ ] After the in-browser Python: the user's direction on 2026-10-08 is that Pyodide in the
  viewer is only for the beginning and for testing, and a more complex UI (even a mobile app)
  comes later. Three ways to run the engine behind such a UI, to be chosen in its own
  brainstorm: (a) keep the Python engine on a server behind an API, which needs the least
  rewriting and is also what verifying a leaderboard needs, but the app then needs a network;
  (b) port the engine to the UI's language (TypeScript, Kotlin, Swift or Dart), which works
  offline but means maintaining two engines; (c) run Python on the device, which is heavy and
  rarely worth it. What keeps every option open today: the engine is pure standard library with
  no browser code in it; a run is a JSON config in and a JSON result out (`run_json`,
  `compare_json`); scenarios are JSON files. Cheap preparation: write that JSON contract down
  (config keys, summary keys, trace format) and give the trace a version number. Because runs
  are deterministic per seed, saved results (golden files) can prove that a port or a rewritten
  engine gives identical output, so the existing tests double as the port's conformance suite.
  Knock-on effects: the hosting entry below assumes a static site, which only holds while the
  engine runs in the browser; a server engine needs a real host; `viewer/app.js` is the part
  that gets replaced, not the engine. (2026-10-08)

## Hosting and accounts

- [ ] Publish the app. Assessment on 2026-10-08: the viewer is one generated file
  (`dist/viewer.html`, about 0.5 MB) and the Python engine runs inside the browser through
  Pyodide, so it needs a static host only: no server, no database. Free options: GitHub Pages
  (the repo is already on GitHub; a CI step builds the file and publishes it), Cloudflare Pages
  or Netlify. For early testing, `python3 -m http.server` from `dist/` is enough. Needs: HTTPS,
  and internet access for the Pyodide files from the jsDelivr CDN, unless they are self-hosted
  (`--pyodide-base`, adds several MB of files). Optional: a domain name. (2026-10-08)
- [ ] Database and sign-in (Google or others). Not needed today: nothing is stored and nobody
  has an account. It becomes necessary for saving scenarios or results across devices, shared
  comparisons, or the game (progress, leaderboards). Free-tier options: Supabase or Firebase
  (database plus Google sign-in), or Cloudflare D1 with Workers. Costs to plan for: storing
  emails brings privacy duties, and a leaderboard cannot trust scores computed in the browser,
  so the server would re-run the submitted seed and strategy with the same Python engine to
  verify them. (2026-10-08)

## Game and reuse

- [ ] Reuse the modelling in a game later: the office-day scheduler as the source
  of randomized passengers, and/or the engine and strategies as the elevator
  logic (for example, the player writes or picks a strategy). (2026-10-08)

## Traffic and scenarios

- [ ] Elevators that do not serve every floor: a car-park shuttle (car park to lobby only) with a
  separate bank from the lobby upward, and high-rise serial banks (floors 1-50, 50-100, with a sky
  lobby). The engine today assumes every car serves every floor (`_can_continue` uses
  0..top_floor, strategies assume all cars reach all calls), so each car would need a served floor
  range. Caveat: a passenger who must transfer is two legs, and the second leg's arrival depends
  on when the first finished, which would make traffic depend on the strategy, against the
  "identical traffic for every algorithm" rule. It would have to be modeled as a chained passenger
  inside the engine. (2026-10-08)
- [ ] More than one entry and exit floor: trips that start or end at a basement (underground
  car park) as well as the lobby. Note: the engine already handles floors below the lobby
  (floor 0 is just the lowest floor and `lobby_floor` can be 1 or more), so the missing part is
  traffic with several entry floors, in `office_day` and in the plain traffic mixes. Check
  `strategies/scan.py`, which assumes floor 0 is the bottom. (2026-10-08)
- [ ] Night and early-morning users (security checks, cleaners) as another group
  of actors with their own trips. (2026-10-08)
- [ ] 24-hour window, 00:00-23:59, using the `day_start` / `day_end` config. (2026-10-08)
- [ ] Multi-day weeks: employees persist across days, with day types (workday,
  holiday, weekend). (2026-10-08)
- [ ] Attendance states per employee per day: sick, leave, half day (morning or
  afternoon), late, truant. Decide whether absences come in streaks. (2026-10-08)

## Algorithms

- [ ] Cooperative cars: a strategy where each car knows the other cars' positions and current and
  next actions and plans its own next move around them (no central dispatcher assigning calls).
  The cars must not know how many passengers wait for a call (only that a hall call exists), and
  a config option sets a direction preference: prioritise up-to-down, down-to-up, or none.
  Status on 2026-10-08: nearest car and ETA already use other cars' positions and assigned stops,
  but through a central dispatcher; no strategy lets each car decide for itself, and none has a
  direction preference. Today no strategy reads queue sizes, but that is a convention, not
  enforced (a strategy receives the whole simulation). Strategy options exist (only `eta` uses
  them) but the viewer does not expose them yet. Open questions for the brainstorm: what
  "prioritise" means exactly (tie-break only, or also where idle cars park), and whether to
  give strategies a restricted view of the simulation so the "does not know passenger counts"
  rule is enforced by a test. (2026-10-08)

## Energy

- [ ] Counterweight energy model (balanced at about 40-50% load). (2026-10-08)
- [ ] Standby, door and idle power in the energy model. (2026-10-08)
- [ ] Regeneration when a heavy car descends or a light one climbs. (2026-10-08)
- [ ] Calibrate the `simple` model constants against real figures so `energy_kwh`
  becomes an absolute number, not only a comparative one. (2026-10-08)

## Engine performance

- [ ] Bigger data: dataframes (pandas) or a database for results once runs, seeds and
  scenarios pile up. Constraints on 2026-10-08: the project is standard library only and the
  engine must import under Pyodide, so keep pandas out of the engine and use it only on the
  analysis side (for example reading `compare.csv`). pandas does exist as a Pyodide package but
  adds a large download to the viewer. The standard library already has `sqlite3`, which also
  works in Pyodide, so a results database can start there with no new dependency. Not needed
  yet: a full-day run is about 1 s and the outputs are small JSON and CSV files. (2026-10-08)
- [ ] Events in the middle of a simulation: a car breaks down, its lights go out, a door
  sticks, random incidents. Today the engine runs a whole run in one call and all passengers
  are generated up front, but it already advances one tick at a time (`step`), so injecting
  events is feasible. Design points: events drawn from the seed and scheduled in advance keep
  every algorithm facing the same incidents (fair, reproducible); events a person injects live
  are not reproducible unless they are recorded in the trace; strategies must be told a car is
  out of service. Related to the interactive game idea and to cooperative cars. (2026-10-08)
- [ ] Real-time decisions during a run: pause, inspect and decide while the simulation is
  running (needed for a game, and for reacting to events). Today the viewer plays a precomputed
  trace: the Python side returns a whole run, so live control needs an incremental interface
  (advance N ticks, read state, apply a decision) exposed through Pyodide. Strategies already
  decide every tick, so the engine side is mostly a thin stepping API. (2026-10-08)

- [ ] Idle fast-forward: when all cars are idle and nothing is waiting, jump the clock to the next
  event. Dropped from 0.2.0 because a full-day run takes about 1 s natively (2026-10-08 profiling).
  Needed for the 24-hour window and multi-day weeks. Constraints found in review: strategies with
  timers need a hook (`eta` re-plans on `sim.t`), the tick counter and the frames on the frame grid
  must still advance, `dt` must be a power of two for exact time sums, `bottleneck_queue` must be at
  least 1, parking (`park_delay`) must still fire on time, and the result must equal the
  tick-by-tick run exactly (compare per-passenger times, per-car stats and summary). (2026-10-08)

## Viewer

- [ ] Scenario notes in the viewer: show a short description of the selected scenario under the
  Scenario dropdown (like the strategy note) or in a pop-up, at least for the template scenarios,
  so the setup can be read without opening the JSON. The scenario files already carry a
  `description`; `viewer_build._presets()` currently drops it. (2026-10-08)
- [ ] Game-quality smoothness: the animation is grainy and jumpy. Scale time range, speed and
  number of people by a ratio so playback looks smooth, for example a view scale that picks
  the display speed from the simulated span, draws one dot per N people when queues are large,
  and animates cars between positions from their state and timers instead of snapping between
  sparse frames. Related to the entry below; do them together. (2026-10-08)
- [ ] Smoother animation between sparse frames. The viewer interpolates a car only
  when it moved at most 1.01 floors between frames, so 5 s frames on a full day
  snap. (2026-10-08)
- [x] Full-day clock (HH:MM) in the viewer. Shipped in 0.2.0. The sparkline has no time
  axis; adding one is still open. (2026-10-08)

## Engine and behavior (probably rejected, kept so the reason is not lost)

- [ ] Employee-aware behavior, for example skipping the cafeteria when the queue
  is long. Rejected for now: it makes traffic depend on the strategy and breaks
  the "every algorithm sees identical traffic" rule. (2026-10-08)
