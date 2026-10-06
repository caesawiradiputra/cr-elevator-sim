"""Command line interface: ``python -m elevsim <command>``."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

from .api import compare, list_strategies, run
from .config import TRAFFIC_PATTERNS, SimConfig
from .metrics import METRICS
from .strategies import STRATEGIES

TABLE_METRICS = ["avg_wait", "p95_wait", "max_wait", "avg_journey", "utilization", "floors_travelled",
                 "max_queue", "bottlenecks", "left_behind"]
SHORT = {"avg_wait": "avg wait", "p95_wait": "p95 wait", "max_wait": "max wait", "avg_journey": "journey",
         "utilization": "util %", "floors_travelled": "floors", "max_queue": "max q",
         "bottlenecks": "bottlenk", "left_behind": "full pass"}


def _add_config_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("scenario (overrides --config)")
    g.add_argument("--config", help="JSON scenario file (see scenarios/)")
    g.add_argument("--floors", type=int)
    g.add_argument("--elevators", type=int)
    g.add_argument("--capacity", type=int)
    g.add_argument("--passengers", type=int)
    g.add_argument("--rate", dest="arrival_rate", type=float, help="arrivals per minute")
    g.add_argument("--traffic", choices=sorted(TRAFFIC_PATTERNS))
    g.add_argument("--parking", dest="idle_parking", choices=["stay", "lobby"])
    g.add_argument("--seed", type=int)


def _config_from_args(args) -> SimConfig:
    data = {}
    if args.config:
        data = SimConfig.from_file(args.config).to_dict()
    for key in ("floors", "elevators", "capacity", "passengers", "arrival_rate", "traffic", "idle_parking", "seed"):
        val = getattr(args, key)
        if val is not None:
            data[key] = val
    return SimConfig.from_dict(data)


def _fmt(v) -> str:
    return f"{v:.1f}" if isinstance(v, float) else str(v)


def _print_table(rows: list[list[str]]) -> None:
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for n, r in enumerate(rows):
        print("  ".join(c.ljust(widths[i]) if i == 0 else c.rjust(widths[i]) for i, c in enumerate(r)))
        if n == 0:
            print("  ".join("-" * w for w in widths))


def cmd_list(args) -> None:
    for s in list_strategies():
        print(f"{s['name']:12} {s['label']}\n{'':12} {s['description']}\n")


def cmd_run(args) -> None:
    cfg = _config_from_args(args)
    res = run(cfg, args.strategy, record=bool(args.trace))
    s = res["summary"]
    print(f"{res['strategy_label']} on {cfg.floors} floors, {cfg.elevators} cars, "
          f"{cfg.passengers} passengers ({cfg.traffic}, {cfg.arrival_rate}/min, seed {cfg.seed})\n")
    for key, (label, unit, _) in METRICS.items():
        print(f"  {label:32} {_fmt(s[key]):>10} {unit}")
    if args.trace:
        with open(args.trace, "w") as fh:
            json.dump(res, fh)
        print(f"\ntrace written to {args.trace} (open it in the viewer with 'Load trace')")


def cmd_compare(args) -> None:
    cfg = _config_from_args(args)
    strategies = args.strategies.split(",") if args.strategies else None
    out = compare(cfg, strategies, args.seeds)
    print(f"{cfg.floors} floors, {cfg.elevators} cars x {cfg.capacity}, {cfg.passengers} passengers, "
          f"traffic={cfg.traffic}, {cfg.arrival_rate}/min, parking={cfg.idle_parking}, "
          f"seeds {out['seeds'][0]}..{out['seeds'][-1]} (mean over {len(out['seeds'])} runs)\n")
    ranked = sorted(out["results"], key=lambda r: r["metrics"][args.rank_by]["mean"],
                    reverse=METRICS[args.rank_by][2] is False)
    rows = [["strategy"] + [SHORT[k] for k in TABLE_METRICS]]
    for r in ranked:
        rows.append([r["strategy"]] + [_fmt(r["metrics"][k]["mean"]) for k in TABLE_METRICS])
    _print_table(rows)
    print(f"\nranked by {METRICS[args.rank_by][0].lower()}; times in seconds")

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "compare.json"), "w") as fh:
            json.dump(out, fh, indent=1)
        with open(os.path.join(args.out, "compare.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["strategy", "seed", *METRICS])
            for r in out["results"]:
                for seed, run_ in zip(out["seeds"], r["runs"]):
                    w.writerow([r["strategy"], seed, *(run_[k] for k in METRICS)])
        print(f"wrote {args.out}/compare.json and {args.out}/compare.csv")


def cmd_viewer(args) -> None:
    from .viewer_build import build_viewer
    path = build_viewer(args.out, demo=not args.no_demo, pyodide_base=args.pyodide_base, fragment=args.fragment)
    print(f"viewer written to {path}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="elevsim", description="Elevator algorithm simulator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list available strategies").set_defaults(func=cmd_list)

    p = sub.add_parser("run", help="run one strategy and print its metrics")
    p.add_argument("--strategy", "-s", default="collective", choices=sorted(STRATEGIES))
    p.add_argument("--trace", help="also write an animation trace JSON to this file")
    _add_config_args(p)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("compare", help="batch-compare strategies on identical seeded passengers")
    p.add_argument("--strategies", help="comma separated (default: all)")
    p.add_argument("--seeds", type=int, default=5, help="number of seeded runs per strategy")
    p.add_argument("--rank-by", default="avg_journey", choices=sorted(METRICS))
    p.add_argument("--out", help="directory for compare.json and compare.csv")
    _add_config_args(p)
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("viewer", help="build the standalone HTML viewer")
    p.add_argument("--out", default="dist/viewer.html")
    p.add_argument("--no-demo", action="store_true", help="skip the precomputed demo run")
    p.add_argument("--pyodide-base", default="https://cdn.jsdelivr.net/npm/pyodide@0.26.4/",
                   help="URL or relative path of the Pyodide files")
    p.add_argument("--fragment", action="store_true", help="omit the <html> wrapper")
    p.set_defaults(func=cmd_viewer)

    args = ap.parse_args(argv)
    try:
        args.func(args)
    except ValueError as exc:
        sys.exit(f"error: {exc}")


if __name__ == "__main__":
    main()
