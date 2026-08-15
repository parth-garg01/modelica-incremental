# Progress log

Living document. Update this after every commit so a fresh session (or a
fresh agent with no memory of this conversation) can pick up work without
re-deriving context. Newest entries at the top of each phase's log. Do
not delete history -- this is a log, not a status snapshot.

**How to use this file if you are picking up cold:**
1. Read this file top to bottom.
2. Read `prd.md` (phase 1 spec, done) and `prd-phase2.md` (phase 2 spec,
   in progress) for the full execution rules and feature definitions.
3. Run `python -m pytest tests/ -v` from the repo root (after activating
   `.venv`) to confirm the standing regression suite still passes before
   touching anything.
4. Check the "Next up" line at the top of the Phase 2 log for where to resume.

---

## Phase 2 status: IN PROGRESS

**Next up:** Section 8 (Features B1-B3) -- MSL models spanning the
coupling spectrum, plus sensor-add and component-removal change
injectors. Then Section 9 (characterization), Section 11 (figures),
Section 16 (paper upgrade).

**Section 7 (Features C1-C2) is DONE.** `src/correctness_c.py` formalizes
the correctness check into a real numeric diff (atol=rtol=1e-9); both
real change cells show EXACTLY zero error (bit-identical binaries).
Teeth proven by corrupting a value and confirming the diff reports it.
Edge cases (`tests/test_c2_edge_cases.py`): a new synthetic `models/chain`
fixture (pure forward chain, no feedback) shows 100% predicted ripple
still produces a byte-identical incremental build; an empty change
(same model as its own "changed" variant) recompiles 0/N units and still
matches. "Change inside a genuine algebraic loop" is NOT exercised --
none exists in any fixture per D2's diagnosis -- and this is recorded
explicitly in the test module rather than silently skipped.

**Section 5 (Features M1-M5) is DONE, and landed on Rung 1 of the
fallback ladder (Section 6) -- the best case: a real per-unit C compile
and relink with measured, not projected, speedup.** Rumoca's
`embedded-c` codegen target turned out to emit one monolithic `.c` file
per model, not one file per recompilation unit, so a bespoke C emitter
was written instead (tractable, since fixture equations are simple
Binary/BuiltinCall/VarRef/Literal trees) rather than post-processing
Rumoca's monolithic output. gcc is available on this machine
(`C:\msys64\mingw64\bin\gcc.exe`) and works from PowerShell (NOT
reliably from this session's Bash -- a `gcc -c foo.c` invoked from Bash
failed silently with exit 1 and no stderr for unclear reasons; the same
command via PowerShell worked fine. **Do all C build/measurement work
via PowerShell, not Bash.**).

**Measured (not projected) speedup, replacing phase 1's projected
ceiling entirely:**
- RLCCircuit: 1/3 units recompiled, full=414.9ms±12.8ms,
  incremental=269.6ms±9.5ms, **measured_speedup=1.54x**
- ThermalNetwork: 2/9 units recompiled, full=910.7ms±50.6ms,
  incremental=408.7ms±41.1ms, **measured_speedup=2.23x**
- Both cells: fingerprint-verified true object reuse, and
  `outputs_identical=True` -- the incrementally-linked binary and a
  from-scratch binary produce byte-identical stdout on the same changed
  model. This IS a strong correctness proof already, though Feature C1
  below formalizes it as a proper numeric diff with tolerance.

Run `python src\measure_c.py` from PowerShell (repo root, venv active)
to reproduce; it deletes nothing on its own, so `rm -rf build_cache`
first if re-running from a clean cache is wanted (harmless either way,
just slower the second time since the "cold cache" build re-happens).

### Phase 2 commit log (newest last, matches `git log`)

1. `docs: open phase two, record phase-one findings in the readme` --
   opened README's phase-2 section with phase-1's mixed finding.
2. `feat: build causalized dependency graph with states as knowns` --
   **found and fixed a real Phase 1 bug**: `graph.py` identified each
   `f_x[i]`'s target *positionally* (assumed `f_x` ordered as
   `[y in dict-key order] + [x in dict-key order]`). Actually `f_x` is
   ordered by *equation appearance in source*, which differs from
   variable *declaration* order whenever a model's equation section
   isn't written in the same order as its declarations (true of
   ThermalNetwork). Fixed via `src/ir_equations.py`, which reads each
   equation's target from its own content (the arg of its
   `BuiltinCall{Der}` for a state equation, or the left operand of its
   top-level residual subtraction for an algebraic one), validated
   against `ir["y"]`/`ir["x"]` on every call. This bug did NOT change
   Phase 1's raw-graph headline SCC sizes (still `[8,1]` for
   ThermalNetwork) but DID corrupt my first causalization attempt before
   I caught it (see the note in this commit's body). Added
   `src/causal_graph.py`: a state's own equation now writes a distinct
   `("der", name)` node, never `("var", name)` -- states are knowns each
   timestep, not solved simultaneously with the algebraics that read
   them, so they can never sit on a cycle. Result: causalized largest SCC
   drops from 8 -> 1 (ThermalNetwork) and 2 -> 1 (RLCCircuit), matching
   `Model.structure()`'s independent BLT-based `algebraic_loops=0` for
   both.
3. `feat: diagnose integration-artifact versus genuine algebraic loops` --
   `src/diagnostic.py` classifies every fixture by comparing raw vs.
   causalized largest-SCC size. Verdict for both real fixtures:
   `integration-artifact`, not `genuine-algebraic-loop`. This means
   **Feature G2 (tearing/residual refinement) is not needed** -- no
   fixture currently has a genuine algebraic loop. (Stays in scope if a
   future model does.)
4. `test: add causalized-graph and diagnostic tests with teeth` -- 18
   new tests. Teeth proven by reverting the D1 fix and watching 5 tests
   go red with exactly the expected wrong verdict.
5. `feat: define recompilation units on the causalized graph` --
   `src/causal_units.py` wires `compute_units` (unchanged, already
   graph-agnostic) to the causalized graph. **Headline numbers:**
   ThermalNetwork raw_unit_count=2 -> causal_unit_count=9 (all
   singleton); RLCCircuit raw=2 -> causal=3 (all singleton).
6. `test: re-validate resolver soundness for the new unit definition` --
   `resolve_impact` and `check_soundness` both gained a `graph_builder`
   parameter so the same logic runs over either graph. Also fixed
   `actually_changed_equations`, which had the identical positional
   `f_x`-ordering bug. **Headline ripple numbers on the causalized graph,
   both independently confirmed sound:**
   - RLCCircuit: total_units=3, affected=['i'], ripple=1/3=33% (was 50% raw)
   - ThermalNetwork: total_units=9, affected=['Q1','T1'], ripple=2/9=22% (was 100% raw)

   This is the granularity-fix payoff: Phase 1's "the whole model
   collapsed" result for ThermalNetwork was the integration-artifact bug,
   not reality; the true ripple is small (2 of 9 units), consistent with
   the model's actual nearest-neighbor topology.
7. `feat: emit one C translation unit per recompilation unit` -- bespoke
   C emitter (`src/expr_c.py`, `src/model_layout.py`,
   `src/codegen_units.py`, `src/eval_order.py`), since Rumoca's own
   `embedded-c` target is monolithic. 9/9 ThermalNetwork unit files
   compiled standalone to non-empty `.o`.
8. `feat: compile per-unit objects and link a runnable simulation, and
   add full-rebuild baseline path` -- `src/c_build.py`: real subprocess
   `gcc` calls, timed. Linked and ran a real `.exe`, output matched the
   hand-verified trajectory exactly.
9. `feat: recompile only affected objects and relink incrementally, with
   measured timing` -- `src/measure_c.py`. **Measured speedup: RLCCircuit
   1.54x (1/3 units recompiled), ThermalNetwork 2.23x (2/9 units
   recompiled).** Fingerprint-verified true object reuse;
   `outputs_identical=True` for both (incremental and full-rebuild
   binaries produce byte-identical output on the same changed model).
   This is Rung 1 of the Section 6 fallback ladder -- the best case.
10. `test: validate incremental output against full rebuild` -- Feature
    C1. `src/correctness_c.py`: real numeric diff, atol=rtol=1e-9. Both
    cells: max_abs_error=0.0 exactly. Corrupted-output teeth test.
11. `test: cover incremental correctness edge cases` -- Feature C2. New
    `models/chain` fixture (pure forward chain) for the near-full-ripple
    case (3/3 units predicted affected, still byte-identical output);
    empty-change case (same model vs. itself, 0 units recompiled).
    "Genuine algebraic loop" case recorded as not-yet-exercised.

**Section 3 (diagnosis), Section 4 (granularity fix), Section 5
(measured incremental recompile+relink), and Section 7 (correctness
validation) are all complete.** This covers roughly Weeks 1-6 of the
phase-2 PRD's own 8-10 week estimate, and crucially includes Section 5,
which the PRD itself calls "the hard, risk-bearing part" that "may take
longer than the rest of the phase combined" -- it did not turn out to be
a hard wall on this codebase.

### What's left in Phase 2 (not started)

- **Section 8 (Features B1-B3):** pull in real MSL models spanning the
  coupling spectrum; add sensor-add and component-removal change
  injectors, each with its own soundness check.
- **Section 9 (Features S1-S2):** structural metrics per model (largest
  SCC/tearing-block size, coupling density, states:algebraic ratio);
  relate ripple and measured speedup to those metrics across the suite.
- **Section 11:** six new figures from measured (not projected) data.
- **Section 16:** upgrade `docs/paper.md` to a full paper with measured
  results, the granularity fix as a named contribution, and the
  characterization findings.

### Known constraints / environment notes for whoever picks this up

- No Rust toolchain on this machine; the whole pipeline is
  Python-only, driving `rumoca` (pip package, `rumoca==0.9.20`) via its
  Python API (`rumoca.Session().load(...)`), not by building the Rust
  compiler from source.
- Python: use `.venv\Scripts\python.exe` (a venv built from the Windows
  Store Python 3.11.9 install, NOT the `python` on PATH in Bash, which
  resolves to a pip-less MSYS2 Python 3.14). PowerShell is the primary
  shell for anything venv-related; Bash is fine for git/file operations.
- gcc is available at `C:\msys64\mingw64\bin\gcc.exe`, confirmed working,
  for whatever C toolchain Section 5 ends up needing.
- Rumoca's Python API surface relevant to this project: `Session().load()`,
  `Model.to_json(stage="dae")` / `.to_dict(stage="dae")` (the IR this
  whole pipeline is built on), `Model.structure()` (independent BLT
  info: `n_blocks`, `n_algebraic_loops`, `is_matched` -- used as a
  cross-check, not a data source), `Model.simulate()`, `Model.codegen(target)`
  (target `"embedded-c"` emits one monolithic `.h`/`.c` pair, not
  per-unit -- relevant to Section 5's decision above).
- Git identity is already configured correctly at the global level
  (parth-garg01 / parth.garg2024@vitstudent.ac.in) -- no per-repo config
  needed, per the user's global CLAUDE.md instructions.

---

## Phase 1 status: COMPLETE (12 commits, see `prd.md`)

Built the full feasibility-study pipeline on the exported IR only (no
codegen, no linking): dependency graph -> recompilation units (SCCs) ->
change injection (component swap) -> graph-based impact resolver ->
ripple measurement -> soundness validation against an independent diff
-> figures -> paper draft (`docs/paper.md`).

**Headline phase-1 finding (superseded by phase-2's granularity fix for
ThermalNetwork, see above -- kept here for history):** RLCCircuit showed
50% ripple (1/2 units); ThermalNetwork showed 100% ripple (1/1 unit,
whole model collapsed) -- later diagnosed in phase 2 as an integration
artifact, not real coupling. The projected speedup ceiling
(`1/affected_fraction`) was explicitly labeled a projection, not a
measurement, per phase 1's own honesty rules.

Four fixture models (hand-written, since MSL is not bundled with the
`rumoca` pip package -- disclosed in `README.md` and `docs/paper.md`):
`OneLine`, `DecoupledPair`, `RLCCircuit`, `ThermalNetwork`, plus their
`_swapped` variants (component-swap change: nonlinear resistor for RLC,
proportional thermostat for ThermalNetwork's heater).

22 tests passing at phase-1 close (now 53, after phase-2 additions).
