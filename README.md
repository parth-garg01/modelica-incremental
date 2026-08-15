# Drift-Triggered Incremental Recompilation

## Phase 1 (done): one-week feasibility study

Phase 1 asked whether a localized structural change to a Modelica model
touches a small, automatically identifiable fraction of the model's
recompilation units. It built the pipeline end to end on the exported
intermediate representation only (no code generation, no linking) and
measured ripple on two hand-written models, with a **projected**, not
measured, speedup ceiling. See `docs/paper.md` for the full write-up and
`prd.md` for phase 1's execution spec.

Phase 1's honest, mixed finding, which phase 2 exists to act on:
- **RLCCircuit**: a component swap stayed local -- 50% ripple (1 of 2
  units), matching the intended "changes are local" story.
- **ThermalNetwork**: the same kind of change produced **100% ripple** --
  the whole model collapsed into one dependency block, despite the model's
  topology being only nearest-neighbor (room 1 -- room 2 -- room 3). Phase 1
  flagged this as a real, non-spurious cycle in the equation-variable
  dependency graph (each state's derivative equation reads an algebraic
  heat-flow variable that is itself a function of that same state), but
  left open whether this is an artifact of *how the graph was built*
  (states shouldn't create integration cycles with their own algebraic
  outputs, since a real solver treats states as knowns each timestep) or a
  genuine simultaneous algebraic loop.

## Phase 2 (in progress): from projected to measured

Phase 2's job, in order: diagnose the thermal collapse (integration
artifact vs. genuine algebraic loop -- see `prd-phase2.md` Section 3),
fix the recompilation-unit definition so it survives feedback-heavy
models, then replace the projected speedup ceiling with a **measured**
one from a real partial recompile and relink through Rumoca's C backend,
validated for numerical correctness against a full rebuild. See
`prd-phase2.md` for the full execution spec.

What phase 1 **measured** (real runs, real numbers):
- Dependency graph and recompilation-unit partition of real Modelica models.
- Ripple: the fraction of recompilation units affected by an injected
  structural change.
- Full compile time (repeated, with spread reported).
- Soundness of the impact resolver against an actual before/after diff.

What phase 1 **projected**, not measured (phase 2's job to replace):
- Incremental speedup ceiling, computed as `1 / affected_fraction`, an
  optimistic upper bound that ignores relink and re-matching overhead.

## Layout

- `src/` — pipeline code (compile, graph, units, change injection, resolver, measurement)
- `models/` — Modelica source models used as fixtures
- `results/` — logged run data (parquet/json), figures, generated summaries
- `figures/` — generated plots
- `tests/` — pytest suite

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Compiler: [Rumoca](https://pypi.org/project/rumoca/), installed as a pinned
Python package (`rumoca==0.9.20`, verified via `rumoca.version()` at
`src/compile.py`). Python 3.11.9, Windows-10-10.0.26100-SP0, AMD64.
