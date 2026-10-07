# Ideas and side notes

A parking lot for thoughts that are not committed work. Nothing here has an
order, a version or a promise to be built. When stuck or choosing what to do
next, scan this list and pick whatever looks interesting. When an idea is
picked up, it gets its own brainstorming and spec under `docs/superpowers/specs/`,
and gets a version at release time (see `CHANGELOG.md`). Mark it `[x]` when it
ships, and add the version and date.

Add new ideas at the top of their group. One line is enough. Add a source date
so the thought can be traced back to a conversation.

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

- [ ] Interpolate car positions between sparse frames (needed for 5 s frames on a
  full day, if the viewer does not already). (2026-10-08)
- [ ] Full-day clock (HH:MM) and chart axis in the viewer. (2026-10-08)

## Engine and behavior (probably rejected, kept so the reason is not lost)

- [ ] Employee-aware behavior, for example skipping the cafeteria when the queue
  is long. Rejected for now: it makes traffic depend on the strategy and breaks
  the "every algorithm sees identical traffic" rule. (2026-10-08)
