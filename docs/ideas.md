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
- [ ] Documentation session: README, `docs/code-map.md` and docstrings brought up
  to date with the code, written for a reader new to the codebase. (2026-10-08)
- [ ] Mentoring walkthrough after each mid or big feature: explain each module and
  where to find code to check or change by hand. (2026-10-08)

## Game and reuse

- [ ] Reuse the modelling in a game later: the office-day scheduler as the source
  of randomized passengers, and/or the engine and strategies as the elevator
  logic (for example, the player writes or picks a strategy). (2026-10-08)

## Traffic and scenarios

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

## Viewer

- [ ] Smoother animation between sparse frames. The viewer interpolates a car only
  when it moved at most 1.01 floors between frames, so 5 s frames on a full day
  snap. (2026-10-08)
- [ ] Full-day clock (HH:MM) and chart axis in the viewer. (2026-10-08)

## Engine and behavior (probably rejected, kept so the reason is not lost)

- [ ] Employee-aware behavior, for example skipping the cafeteria when the queue
  is long. Rejected for now: it makes traffic depend on the strategy and breaks
  the "every algorithm sees identical traffic" rule. (2026-10-08)
