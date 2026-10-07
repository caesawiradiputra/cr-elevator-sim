---
name: add-strategy
description: Add a new elevator dispatch algorithm to elevsim — new Strategy/DispatcherStrategy class, registry entry, test, and README row. Use when the user wants to add, prototype, or compare a new elevator control algorithm.
disable-model-invocation: true
---

# Add an elevator strategy

Argument: the algorithm idea / name (e.g. `/add-strategy zoned dispatch`).

1. **Read** `elevsim/strategies/base.py` (hook docs, `route_distance`) and the closest
   existing strategy (`round_robin.py` for a simple dispatcher, `eta.py` for a
   cost-based one, `collective.py` / `scan.py` for non-dispatcher control).
2. **Pick the base class.**
   - Central assignment of each hall call to one car → subclass `DispatcherStrategy`
     and implement `pick_car(sim, call) -> car id`.
   - Cars decide for themselves → subclass `Strategy` and override
     `choose_direction` / `should_stop` as needed.
3. **Create `elevsim/strategies/<snake_name>.py`** with class attributes `name`
   (snake_case, unique CLI id), `label`, `description` (one or two sentences).
   Per-run state goes in `setup(self, sim)`, not `__init__` or module globals —
   strategy instances are reused across seeds. Standard library only.
4. **Register** it in the `STRATEGIES` tuple in `elevsim/strategies/__init__.py`.
   The CLI, `compare` and the viewer read this registry; no other file hardcodes
   strategy names.
5. **Test**: `tests/test_engine.py` already loops over `STRATEGIES` for the
   delivery/physics invariants, so a registered strategy is covered automatically.
   Add a targeted test only for behavior specific to the new algorithm.
6. **README**: add a row to the Algorithms table (`name`, kind, idea).
7. **Verify**:
   ```bash
   python3 -m unittest discover -s tests -t .
   python3 -m elevsim compare --passengers 80 --seeds 2
   python3 -m elevsim viewer --out dist/viewer.html
   ```
   Report the new strategy's wait/journey numbers next to the existing ones.
