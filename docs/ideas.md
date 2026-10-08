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
- [ ] Documentation session: README, `docs/code-map.md` and docstrings brought up
  to date with the code, written for a reader new to the codebase. (2026-10-08)
- [ ] Mentoring walkthrough after each mid or big feature: explain each module and
  where to find code to check or change by hand. (2026-10-08)

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

## Energy

- [ ] Counterweight energy model (balanced at about 40-50% load). (2026-10-08)
- [ ] Standby, door and idle power in the energy model. (2026-10-08)
- [ ] Regeneration when a heavy car descends or a light one climbs. (2026-10-08)
- [ ] Calibrate the `simple` model constants against real figures so `energy_kwh`
  becomes an absolute number, not only a comparative one. (2026-10-08)

## Engine performance

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
