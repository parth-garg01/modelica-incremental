# Finding: Rumoca's own algebraic-loop solver is wrong on a coupled block that depends on a state

Discovered while building Feature 4's ground truth (a coupled linear block
whose solution needs checking against something). `models/coupled_dynamic/CoupledDynamic.mo`:

```
Real x(start=1.0, fixed=true);
Real y1, y2;
equation
  der(x) = -x;
  y1 = 2*y2 + x;
  y2 = 3*y1 - 2*x;
```

Hand-solved (substitute one equation into the other): `y1 = 0.6*x`, `y2 = -0.2*x`,
exactly, at every instant, for any `x`. `Model.structure()` confirms the
structure is valid: `states=1, algebraic=2, matched=true, blocks=2, algebraic_loops=1`.

## What Rumoca's `Model.simulate()` actually returns

At `t=0`: `x=1.0, y1=0.6, y2=-0.2` -- correct.

From the **second** timestep onward, on every one of the 5 solvers exposed
by `rumoca.solvers()` (`auto`, `rk-like`, `bdf`, `esdirk34`, `trbdf2`):
`y2` comes out **exactly equal to `x`** (e.g. at `t=0.1`, `x=0.904837`,
`y2=0.904837` -- should be `y2=-0.2*0.904837=-0.180967`), and `y1` comes out
wildly wrong (`13.57` instead of the expected `0.6*0.904837=0.542902`).
`rk-like` additionally gets even `t=0` wrong (`y1=15.0, y2=1.0`, not `0.6,-0.2`
like every other solver).

This is consistent and reproducible, not solver-choice noise or a transient
convergence issue -- confirmed with `PYTHONHASHSEED` irrelevant here (this is
Rumoca's own compiled Rust runtime, not this project's Python matching code)
and reproduced identically across repeated runs.

## Why this isn't a bug in this project's code

This project's own linear block solve (`src/linear_block.py` +
`src/block_codegen.py`, Feature 4) produces `y1=0.6*x`, `y2=-0.2*x` **exactly**
at every timestep of a real compiled-and-run C binary, cross-checked against
the independently hand-derived formula (`tests/test_unit_codegen.py::
test_coupled_block_matches_independent_analytical_solution`, `max_abs_error
== 0.0`). Rumoca's own separate error (`"solve-IR evaluation failed:
projected runtime assignments and relation memory did not converge at t=0"`)
on the STATE-FREE version of this model (`models/coupled_algebraic/
CoupledAlgebraic.mo`, structurally identical coupling with no `x`) is a
second, independent symptom of the same underlying area: Rumoca's runtime
appears to solve algebraic loops via some form of iterative/relaxation
scheme (glimpsed earlier in generated `embedded-c` output: a capped
`for (__it < 100)` fixed-point loop) rather than a direct linear solve, and
that iteration does not reliably converge to the correct answer for at
least these two small, exactly-linear test cases.

## Consequence

Feature 4's "bit-identical to a full Rumoca compile" check (prd-combined.md's
literal wording) is satisfied instead against the independently-verified
analytical solution, which is the more rigorous ground truth here -- matching
a known-buggy reference would validate the wrong answer. Recorded as an
`xfail` regression test (`tests/test_unit_codegen.py::
test_rumoca_simulate_has_a_known_bug_on_this_model`) so this is automatically
re-flagged if a future Rumoca version changes this behavior.
