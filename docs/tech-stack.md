# Tech stack and upgrade strategy

What the project is built with, the exact versions in use, and how each one is
upgraded. The second half looks ahead: where the simulator, or the process of
comparing algorithms, could be used later, and which choices today keep those
uses open.

Decided in the tech decisions session on 2026-10-08 (see `docs/ideas.md`).
Update this file in the same PR that changes a version.

## What is in use

| Part | Version | Where it is set | Why this one |
| --- | --- | --- | --- |
| Python (engine, CLI, tests) | 3.10, 3.12, 3.13 | `.github/workflows/tests.yml` matrix | 3.10 is the oldest supported; 3.12 matches Pyodide; 3.13 is the newest tested |
| Python dependencies | none (standard library only) | `CLAUDE.md` conventions | the engine must import under Pyodide with no extra packages, and stays easy to port |
| Pyodide (Python in the browser) | 0.26.4, from jsDelivr | `PYODIDE_CDN` in `elevsim/viewer_build.py`, `--pyodide-base` default in `elevsim/cli.py` | ships Python 3.12, which the CI matrix covers |
| Viewer | plain HTML, CSS and JavaScript, no framework, no build step besides `elevsim viewer` | `viewer/` | one generated file (`dist/viewer.html`) that any static host serves |
| Viewer fonts | Google Fonts (DotGothic16, IBM Plex Mono, IBM Plex Sans Condensed) | `viewer/index.html` | needs internet; self-host if the viewer must work offline |
| GitHub Actions | `actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4` | `.github/workflows/tests.yml` | current major versions |
| Node (CI only, `node --check viewer/app.js`) | 22 (LTS) | `.github/workflows/tests.yml` | pinned so the syntax check does not change with the runner image |
| Playwright MCP (Claude Code browser checks, not used by the app) | `@playwright/mcp@0.0.82` | `.mcp.json` | pinned; was `@latest` |
| Test runner | `unittest` (standard library) | `tests/`, CI | no dependency |
| Lint (editor and pre-finish, not in CI) | Ruff via `uvx`, rules UP and TRY | `CLAUDE.md` | a one-off run, nothing installed in the project |

Known gaps, left as they are on purpose:

- **Python 3.11 and 3.14 are not in the CI matrix.** 3.11 sits between two tested versions;
  3.14 is the next one to add (see the Python rule below).
- **Python 3.10 reaches end of life in October 2026.** Dropping it is a minor release
  (it changes who can run the CLI), done the next time the matrix is touched.
- **Pyodide 0.26.4 is behind.** npm shows 0.29.5 (September 2026) and a newer release line
  numbered after the Python version (314.x). An upgrade changes the browser's Python to 3.13 or
  3.14 and needs its own check (below), so it is not part of this session.
- **No `pyproject.toml`.** Nothing needs packaging yet. Add one when the engine is published
  as a library (see "Where this could be used").

## Upgrade strategy

General rules:

1. **Pin everything that runs in CI or ships to users.** No `@latest`, no unpinned runtime.
   Major-version tags (`@v4`) are fine for GitHub's own actions.
2. **Wait two weeks after a release** before adopting it, unless it fixes a security issue
   that affects this project.
3. **One upgrade per PR**, with this file updated in the same PR, and an entry in
   `CHANGELOG.md` (a patch bump unless it changes who can run the project).
4. **The proof is identical results.** Runs are deterministic per seed, so an upgrade must give
   the same summary for the same scenario and seed. Compare
   `python -m elevsim compare --passengers 80 --seeds 2` and an `office_day` run before and after.
   A difference is a bug to explain, not noise.
5. **Caesa decides** on anything that changes who can run the project (dropping a Python
   version), the browser runtime (Pyodide), or adds a dependency. Claude may propose and open
   the PR; routine bumps (an action's major version, Node LTS) need only a green CI.

Per part:

| Part | When to upgrade | What to test |
| --- | --- | --- |
| Python matrix | add a version when it has been out for two months; drop one at end of life | full test suite on every matrix entry, plus the CI smoke commands |
| Pyodide | when its Python version is in the CI matrix, or when a fix is needed | build the viewer, open it, run every scenario in the live engine, compare the summary with the native CLI for the same seed |
| GitHub Actions | when GitHub deprecates the current major (it warns in the run log) | CI green |
| Node | at the next LTS, or when the current one ends | CI green (it only checks syntax) |
| Playwright MCP | when a browser check in Claude Code needs a newer feature, or every few months | one viewer check through it |
| Google Fonts | never pinned by version; self-host if offline use is needed | the viewer renders |
| New Python dependency | only outside the engine (analysis scripts, a future server), never inside `elevsim/` | the engine still imports with no packages installed |

## Where this could be used

The simulator is three separate things that can travel on their own: the **engine**
(strategies and metrics), the **traffic models** (seeded passengers, the office day), and the
**comparison process** (same traffic for every algorithm, several seeds, one table). Ways they
could be used, and what each would need:

| Use | Who | What it needs from the stack |
| --- | --- | --- |
| Comparing algorithms for a building (sizing how many cars, testing a dispatch rule) | architects, elevator consultants, facility managers | realistic building models (served floor ranges, car parks, sky lobbies), calibrated energy, exportable reports; the CLI and JSON already fit |
| Teaching scheduling, queueing and simulation | universities, coding bootcamps | the viewer hosted as a static page; readable code and docs (the documentation session) |
| Algorithm benchmark or coding challenge ("write the best strategy") | developers, interview kata, competitions | a stable strategy interface, a restricted view of the simulation, server-side re-runs to verify scores |
| Game | players | the stepping API (advance, read state, decide), mid-run events, smooth animation, accounts and leaderboards |
| Library for research and notebooks | researchers, data analysts | `pyproject.toml` and a PyPI package; results into pandas or `sqlite3` on the analysis side |
| Engine behind other apps (web, mobile, desktop) | future UIs | the JSON contract written down and versioned; see "Platform and architecture" in `docs/ideas.md` |
| Testing ground for the same process elsewhere | any dispatch problem: lifts, warehouse robots, ride-hailing, call centres | the "identical traffic, many strategies, many seeds" pattern; reuse the comparison and metrics code with a different engine |

Where it could run:

| Platform | How | Trade-off |
| --- | --- | --- |
| Static website (today) | `dist/viewer.html` on GitHub Pages, Cloudflare Pages or Netlify, Python in the browser through Pyodide | free and serverless; several MB download on first load; no shared data |
| Server API | the same Python engine behind HTTP | least rewriting; needed for leaderboards and saved results; needs a host and a network |
| Mobile app | a native or cross-platform UI calling the server API, or a ported engine | a port works offline but means two engines to keep identical |
| Desktop | the static viewer wrapped (for example Tauri), or the CLI | offline with a self-hosted Pyodide |
| Command line and CI | `python -m elevsim` (today) | already works; fits automated regression checks of a strategy |
| Notebooks | `import elevsim` in Jupyter, or JupyterLite (Pyodide again) | needs packaging |

What keeps all of these open, and should stay true:

- **The engine stays standard library only and free of browser or UI code.** It runs on
  CPython, Pyodide and a server unchanged.
- **A run is JSON in and JSON out** (`run_json`, `compare_json` in `elevsim/api.py`). The next
  cheap step is to write that contract down (config keys, summary keys, trace format) and put a
  version number in the trace, so any future UI or port can check what it receives.
- **Runs are deterministic per seed.** Saved results become golden files that prove a port, an
  upgrade or a server gives identical output, and they let a server verify a submitted score.
- **Scenarios are data files**, not code, so other tools can create and share them.
- **Licence:** the repository has no licence file yet. Pick one before anyone outside the
  project uses it (MIT or Apache-2.0 for an open library; keep it private if it becomes a product).
