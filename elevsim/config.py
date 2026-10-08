"""Simulation configuration."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields

class ConfigError(ValueError):
    """Invalid configuration, whether a value is out of range or of the wrong type.

    A ValueError subclass, so callers (the CLI, the tests) catch one type for every config problem.
    """


DEFAULT_MAX_TIME = 4 * 3600.0  # hard stop used when max_time is None and the traffic is not scheduled
SCHEDULED_TRAFFIC = ("office_day",)  # traffic built by a scheduler (elevsim/schedule.py), not a mix below
ENERGY_MODELS = ("simple",)  # names known to elevsim/energy.py

# The settings traffic="office_day" needs in the `office` config key. Their values are written in
# scenarios/office_day.json (times are "HH:MM", durations are minutes, the rest are shares between 0
# and 1, rates per person, or seconds); the code has no defaults for them. `day_spread` is how far
# each day-level value may move between seeds when day_variation is 1.
OFFICE_KEYS = (
    "arrival_window", "arrival_peak", "late_share", "late_end",
    "lunch_center", "lunch_spread_min", "lunch_out_share", "lunch_cafe_share", "lunch_out_min", "lunch_cafe_min",
    "work_window", "meetings_per_person", "breaks_per_person", "meeting_min", "break_min",
    "home_window", "stay_late_share", "min_trip_gap_s", "drain_margin_s", "day_spread",
)
SPREAD_KEYS = ("late_share", "lunch_out_share", "stay_late_share", "peak_shift_s")

# Passenger traffic is "uniform" (any floor to any floor), a scheduled scenario such as
# "office_day" (SCHEDULED_TRAFFIC), or a mix: a dict of relative weights for three kinds of trip.
#   incoming    lobby -> upper floor
#   outgoing    upper floor -> lobby
#   interfloor  upper floor -> another upper floor
# The mixes the shipped scenarios use are written in scenarios/*.json, not here.
TRAFFIC_MIX_KEYS = ("incoming", "outgoing", "interfloor")


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_hhmm(text: str) -> int:
    """Seconds since midnight for an "HH:MM" string; ValueError for anything else."""
    try:
        hours, minutes = text.split(":")
        h, m = int(hours), int(minutes)
    except (AttributeError, ValueError):
        raise ConfigError(f"time must look like HH:MM, got {text!r}") from None
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ConfigError(f"time must look like HH:MM between 00:00 and 23:59, got {text!r}")
    return h * 3600 + m * 60


# Scenario files (scenarios/*.json): the settings shared by every version sit at the top level,
# and `variations` lists the versions (each has an `id`, a `name`, a `description` and the settings
# it sets on top). `enabled_variations` are the ids the viewer offers; `default_variation` is the
# one used when none is asked for. Files without `variations` are one implicit version.
SCENARIO_META_KEYS = ("name", "description", "variations", "enabled_variations", "default_variation")
VARIATION_META_KEYS = ("id", "name", "description")


def _variations_by_id(data: dict) -> dict:
    by_id: dict = {}
    for variation in data.get("variations") or []:
        vid = variation.get("id") if isinstance(variation, dict) else None
        if not isinstance(vid, str) or not vid:
            raise ConfigError("every variation needs a non-empty string id")
        if vid in by_id:
            raise ConfigError(f"duplicate variation id {vid!r}")
        by_id[vid] = variation
    if not by_id:
        for key in ("enabled_variations", "default_variation"):
            if key in data:
                raise ConfigError(f"{key} needs a variations list")
    return by_id


def _enabled_ids(data: dict, by_id: dict) -> list[str]:
    enabled = list(data.get("enabled_variations", by_id))
    unknown = [i for i in enabled if i not in by_id]
    if unknown:
        raise ConfigError(f"enabled_variations names unknown variations: {unknown}")
    if by_id and not enabled:
        raise ConfigError("enabled_variations must not be empty")
    return enabled


def scenario_default_id(data: dict) -> str | None:
    """The variation used when none is asked for: default_variation, else the first enabled one."""
    by_id = _variations_by_id(data)
    if not by_id:
        return None
    enabled = _enabled_ids(data, by_id)
    default = data.get("default_variation", enabled[0])
    if default not in enabled:
        raise ConfigError(f"default_variation {default!r} must be one of enabled_variations {enabled}")
    return default


def scenario_variations(data: dict) -> list[dict]:
    """The enabled variations, in the order of enabled_variations."""
    by_id = _variations_by_id(data)
    return [by_id[i] for i in _enabled_ids(data, by_id)]


def resolve_scenario(data: dict, variation: str | None = None) -> dict:
    """Engine settings of a scenario file: the root settings with one variation on top.

    ``variation`` is a variation id; any defined id may be asked for, enabled or not.
    """
    by_id = _variations_by_id(data)
    default = scenario_default_id(data)  # also validates enabled_variations and default_variation
    root = {k: v for k, v in data.items() if k not in SCENARIO_META_KEYS}
    if not by_id:
        if variation is not None:
            raise ConfigError(f"this scenario has no variations (asked for {variation!r})")
        return root
    chosen = default if variation is None else variation
    if chosen not in by_id:
        raise ConfigError(f"unknown variation {chosen!r}; choose from {sorted(by_id)}")
    return {**root, **{k: v for k, v in by_id[chosen].items() if k not in VARIATION_META_KEYS}}


@dataclass
class SimConfig:
    # Building
    floors: int = 10
    elevators: int = 3
    capacity: int = 8
    lobby_floor: int = 0

    # Timing (seconds)
    floor_travel_time: float = 1.5  # time to move one floor
    door_time: float = 2.0  # time to open (and, separately, to close) the doors
    board_time: float = 1.0  # time for one passenger to get in or out

    # Passengers
    passengers: int = 200  # total passengers generated
    arrival_rate: float = 20.0  # mean arrivals per minute (Poisson process)
    traffic: str | dict = "uniform"  # "uniform", "office_day", or a mix dict (see TRAFFIC_MIX_KEYS)
    origin_weights: list[float] | None = None  # optional per-floor weights (overrides traffic origin choice)
    destination_weights: list[float] | None = None  # optional per-floor weights for destinations

    # Operational rules
    idle_parking: str = "stay"  # "stay" or "lobby": where idle cars wait
    park_delay: float = 10.0  # seconds idle before a car heads to the parking floor

    # Engine
    seed: int = 1
    dt: float = 0.5  # simulation tick in seconds
    max_time: float | None = None  # hard stop in seconds; None = auto (4 h, or last office_day request + margin)

    # Metric thresholds
    bottleneck_queue: int = 6  # a floor queue at or above this counts as a bottleneck
    long_wait: float = 60.0  # waits at or above this (s) count as long waits

    # Office-day scenario (traffic="office_day"); `passengers` and `arrival_rate` do not apply to it
    employees: int = 300  # fixed headcount; each has a fixed desk floor
    day_start: str = "06:45"  # simulation time 0, as HH:MM
    day_end: str = "20:00"  # latest time any request may be generated
    day_variation: float = 1.0  # 0 = day-level shares exactly as configured, 1 = default spread
    office: dict = field(default_factory=dict)  # the office_day settings (OFFICE_KEYS), from scenarios/office_day.json

    # Energy (see elevsim/energy.py). The simple model's constants are uncalibrated, so
    # energy_kwh is a comparative estimate for ranking algorithms, not an absolute figure.
    energy_model: str = "simple"
    energy_base: float = 0.01  # kWh per floor a car moves, empty
    energy_per_passenger: float = 0.002  # extra kWh per passenger per floor moved

    extra: dict = field(default_factory=dict)  # free-form, passed to strategies

    def validate(self) -> SimConfig:
        if self.floors < 2:
            raise ConfigError("floors must be >= 2")
        if self.elevators < 1:
            raise ConfigError("elevators must be >= 1")
        if self.capacity < 1:
            raise ConfigError("capacity must be >= 1")
        if not 0 <= self.lobby_floor < self.floors:
            raise ConfigError("lobby_floor must be a valid floor")
        if self.arrival_rate <= 0:
            raise ConfigError("arrival_rate must be > 0")
        if self.dt <= 0:
            raise ConfigError("dt must be > 0")
        self._validate_traffic()
        for name in ("origin_weights", "destination_weights"):
            w = getattr(self, name)
            if w is not None and len(w) != self.floors:
                raise ConfigError(f"{name} must have one weight per floor ({self.floors})")
        if self.idle_parking not in ("stay", "lobby"):
            raise ConfigError("idle_parking must be 'stay' or 'lobby'")
        if self.max_time is not None and self.max_time <= 0:
            raise ConfigError("max_time must be > 0 (or null for auto)")
        if self.energy_model not in ENERGY_MODELS:
            raise ConfigError(f"unknown energy_model {self.energy_model!r}; choose from {list(ENERGY_MODELS)}")
        if self.energy_base < 0 or self.energy_per_passenger < 0:
            raise ConfigError("energy_base and energy_per_passenger must be >= 0")
        if not isinstance(self.office, dict):
            raise ConfigError("office must be a dict of overrides")
        unknown = set(self.office) - set(OFFICE_KEYS)
        if unknown:
            raise ConfigError(f"unknown office keys: {sorted(unknown)}")
        if self.traffic == "office_day":
            self._validate_office_day()
        return self

    def _validate_traffic(self) -> None:
        t = self.traffic
        if isinstance(t, str):
            if t != "uniform" and t not in SCHEDULED_TRAFFIC:
                raise ConfigError(
                    f"unknown traffic {t!r}; choose from {sorted(['uniform', *SCHEDULED_TRAFFIC])} "
                    f"or give a mix of {list(TRAFFIC_MIX_KEYS)} weights"
                )
            return
        if not isinstance(t, dict):
            raise ConfigError("traffic must be a name or a mix dict")
        if not t or set(t) - set(TRAFFIC_MIX_KEYS):
            raise ConfigError(f"traffic mix keys must be among {list(TRAFFIC_MIX_KEYS)}, got {sorted(t)}")
        if not all(_is_number(w) and w >= 0 for w in t.values()):
            raise ConfigError("traffic mix weights must be numbers >= 0")
        if sum(t.values()) <= 0:
            raise ConfigError("traffic mix weights must not all be zero")

    def office_settings(self) -> dict:
        """The `office` block (office_day settings, as written in the scenario file)."""
        return dict(self.office)

    @staticmethod
    def _validate_office_types(o: dict) -> None:
        """Wrong types must be a ValueError here, not a TypeError halfway through generation."""
        for name in ("late_share", "lunch_spread_min", "lunch_out_share", "lunch_cafe_share", "meetings_per_person",
                     "breaks_per_person", "stay_late_share", "min_trip_gap_s", "drain_margin_s"):
            if not _is_number(o[name]):
                raise ConfigError(f"office.{name} must be a number")
        for name in ("lunch_out_min", "lunch_cafe_min", "meeting_min", "break_min"):
            value = o[name]
            if not (isinstance(value, (list, tuple)) and len(value) == 2 and all(_is_number(x) for x in value)):
                raise ConfigError(f"office.{name} must be [low, high] minutes (two numbers)")
        for name in ("arrival_window", "work_window", "home_window"):
            value = o[name]
            if not (isinstance(value, (list, tuple)) and len(value) == 2):
                raise ConfigError(f'office.{name} must be ["HH:MM", "HH:MM"]')
        spread = o["day_spread"]
        if not isinstance(spread, dict) or set(spread) != set(SPREAD_KEYS) or not all(
            _is_number(x) and x >= 0 for x in spread.values()
        ):
            raise ConfigError(f"office.day_spread must give a number >= 0 for each of {list(SPREAD_KEYS)}")

    def _validate_office_day(self) -> None:
        missing = [k for k in OFFICE_KEYS if k not in self.office]
        if missing:
            raise ConfigError(
                f"office_day needs these office settings: {missing}; they are written in "
                f"scenarios/office_day.json (run it with --config scenarios/office_day.json)"
            )
        if isinstance(self.employees, bool) or not isinstance(self.employees, int):
            raise ConfigError("employees must be a whole number")
        if self.employees < 1:
            raise ConfigError("employees must be >= 1")
        if not _is_number(self.day_variation) or self.day_variation < 0:
            raise ConfigError("day_variation must be a number >= 0")
        if self.origin_weights is not None:
            desk_weights = [w for f, w in enumerate(self.origin_weights) if f != self.lobby_floor]
            if any(w < 0 for w in desk_weights) or not any(w > 0 for w in desk_weights):
                raise ConfigError("origin_weights must be >= 0 and leave at least one desk floor besides the lobby")
        o = self.office_settings()
        self._validate_office_types(o)
        for name in ("late_share", "lunch_out_share", "lunch_cafe_share", "stay_late_share"):
            if not 0.0 <= o[name] <= 1.0:
                raise ConfigError(f"office.{name} must be between 0 and 1")
        if o["lunch_out_share"] + o["lunch_cafe_share"] > 1.0:
            raise ConfigError("office.lunch_out_share + office.lunch_cafe_share must not exceed 1")
        for name in ("meetings_per_person", "breaks_per_person", "drain_margin_s", "lunch_spread_min"):
            if o[name] < 0:
                raise ConfigError(f"office.{name} must be >= 0")
        gap = o["min_trip_gap_s"]
        if gap <= 0:
            raise ConfigError("office.min_trip_gap_s must be > 0")
        for name in ("lunch_out_min", "lunch_cafe_min", "meeting_min", "break_min"):
            low, high = o[name]
            if not low <= high or low * 60 < gap:
                raise ConfigError(
                    f"office.{name} must be [low, high] minutes with low <= high and low x 60 >= min_trip_gap_s"
                )
        start, end = parse_hhmm(self.day_start), parse_hhmm(self.day_end)
        a0, a1 = (parse_hhmm(t) for t in o["arrival_window"])
        peak, late_end = parse_hhmm(o["arrival_peak"]), parse_hhmm(o["late_end"])
        w0, w1 = (parse_hhmm(t) for t in o["work_window"])
        h0, h1 = (parse_hhmm(t) for t in o["home_window"])
        lunch, spread = parse_hhmm(o["lunch_center"]), o["lunch_spread_min"] * 60
        longest_lunch = max(o["lunch_out_min"][1], o["lunch_cafe_min"][1]) * 60
        longest_optional = max(o["meeting_min"][1], o["break_min"][1]) * 60
        checks = [
            (start <= a0 < a1 <= late_end < h0 < h1 <= end,
             "times must be in order: day_start <= arrival_window < late_end < home_window <= day_end"),
            (a0 <= peak <= a1, "office.arrival_peak must lie inside office.arrival_window"),
            (w0 < w1, "office.work_window must be in order"),
            (w0 <= lunch - spread and lunch + spread + longest_lunch <= w1,
             "lunch (centre +/- spread, plus the longest lunch) must fit inside office.work_window"),
            (late_end + gap <= lunch - spread and lunch + spread + longest_lunch + gap <= h0,
             "lunch (centre +/- spread, plus the longest lunch) must stay min_trip_gap_s clear of late_end and home_window"),
            (w1 + longest_optional <= end, "day_end must leave room for the longest meeting or break after work_window"),
        ]
        for ok, message in checks:
            if not ok:
                raise ConfigError(message)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SimConfig:
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ConfigError(f"unknown config keys: {sorted(unknown)}")
        return cls(**data).validate()

    @classmethod
    def from_file(cls, path: str, variation: str | None = None) -> SimConfig:
        with open(path) as fh:
            data = json.load(fh)
        return cls.from_dict(resolve_scenario(data, variation))
