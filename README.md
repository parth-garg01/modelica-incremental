# Drift-Triggered Incremental Recompilation: One-Week Feasibility Study

## Paper claim

For realistic localized structural changes to Modelica models, the set of
compiled blocks that would need regenerating is a small, automatically
identifiable fraction of the whole model. We measure that fraction on real
models and use it to project an upper bound on the achievable speedup from
incremental recompilation.

This is a **feasibility study**, not a working incremental compiler. See
`docs/paper.md` for the full write-up, and `prd.md` for the execution spec
this repository follows.

What is **measured** (real runs, real numbers):
- Dependency graph and recompilation-unit partition of real Modelica models.
- Ripple: the fraction of recompilation units affected by an injected
  structural change.
- Full compile time (repeated, with spread reported).
- Soundness of the impact resolver against an actual before/after diff.

What is **projected**, not measured:
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
