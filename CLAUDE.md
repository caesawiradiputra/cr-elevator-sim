# CLAUDE.md

Elevator algorithm simulator: a discrete-time Python engine (`elevsim/`), a CLI,
and a single-page viewer (`viewer/`) that runs the same engine in the browser
via Pyodide. See `README.md` for configuration keys and algorithm descriptions.

## Commands

```bash
python3 -m unittest discover -s tests -t .                       # tests (same as CI)
python3 -m elevsim list                                          # registered algorithms
python3 -m elevsim compare --passengers 80 --seeds 2             # CI smoke test
python3 -m elevsim viewer --out dist/viewer.html                 # build the viewer
```

## Conventions

- **Standard library only** — no third-party runtime dependencies. The engine
  must stay importable under Pyodide and on Python 3.10, 3.12 and 3.13 (the CI matrix).
- There is no `pyproject.toml`, ruff or mypy config; don't assume `uv run` tooling.
- The editor runs Ruff anyway (UP and TRY rules; TRY003 is not enforced). Before finishing a change run
  `uvx ruff check --no-cache --select UP,TRY --ignore TRY003 .` (a one-off, no dependency added). With
  `from __future__ import annotations` do not quote annotations (UP037), and do not `raise ValueError`
  after an `isinstance` check (TRY004): raise `ConfigError` (a `ValueError` subclass in `elevsim/config.py`).
- Runs must stay deterministic and fair: passengers are generated from the seed
  only, never from the strategy, so every algorithm sees identical traffic
  (covered by `tests/test_engine.py`).
- Strategies are registered in `elevsim/strategies/__init__.py`; nothing else
  hardcodes algorithm names. Use `/add-strategy` to add one.
- Traffic that needs a scheduler (`office_day`) lives in `elevsim/schedule.py` and is selected through
  `SCHEDULED_TRAFFIC` in `elevsim/config.py`; energy models live in `elevsim/energy.py`. See `docs/code-map.md`.
- `dist/` and `results/` are generated and gitignored.

## Git

Branches on the remote: `main` (default), `master`, `dev`, `sit`. CI runs on
pushes to those branches and on pull requests.
