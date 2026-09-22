"""Journal upgrade, phase 2: a fair simpler incremental-recompilation
baseline, plus a content-hash oracle reference point.

BASELINE: undirected incidence closure, states as knowns.

What the baseline is allowed to know (no matching of algebraic rows):
  - the equation-variable INCIDENCE of every residual in ir["f_x"] (which
    non-state unknowns an equation mentions), read straight off the IR;
  - which rows are state rows (contain der(x)), a purely syntactic fact
    (ir_equations.equation_target's der() test, the same classification
    matching.compute_matching makes BEFORE running any matching);
  - that states are knowns within a step (their value comes from the
    integrator), so a state row can only ever write der(x), which no
    per-step equation reads: a state row may be reached but never
    propagates further;
  - the seed equations the change injector edited.
What it is NOT allowed to know: which unknown each algebraic row is
solved for, i.e. data-flow direction. Without it, an equation sharing an
unknown with a changed equation might be the one that consumes it or the
one that produces it, so a sound closure must follow shared incidence in
both directions, transitively.

To keep builds comparable, the decision is expressed on the SAME unit
partition (matched_units.compute_matched_units) and code generator as the
paper's method: affected units = every unit containing an equation in the
closure. The matching is consulted only for that bookkeeping (naming
equations/units and turning seed names into equation indices), never for
the closure itself.

`states_as_knowns=False` is the considered-and-rejected weaker variant
(states propagate like any other shared variable, state rows are not
sinks); it is kept only so the evidence for choosing the primary variant
can be regenerated.
"""
from __future__ import annotations

from collections import defaultdict

from graph import _varrefs
from ir_equations import _find_der_targets
from matched_units import compute_matched_units
from matching import compute_matching
from model_layout import build_layout
from unit_codegen import generate_all_unit_sources, unit_function_suffix


def _eq_names(m, n_eqs: int) -> list[str]:
    return [m.eq_to_var.get(i, f"UNMATCHED_{i}") for i in range(n_eqs)]


def incidence_closure(ir: dict, seed_indices: list[int], states_as_knowns: bool = True) -> set[int]:
    """Equation indices reachable from the seeds over the undirected
    equation-variable incidence graph. Uses no matching information."""
    unknowns = set(ir["y"]) | set(ir.get("w", {}))
    if not states_as_knowns:
        unknowns |= set(ir["x"])
    incidence, sinks = [], set()
    for i, expr in enumerate(ir["f_x"]):
        incidence.append((_varrefs(expr) - {"time"}) & unknowns)
        # syntactic state row, same test as matching.compute_matching's eq_kind
        if states_as_knowns and len(set(_find_der_targets(expr))) == 1:
            sinks.add(i)

    var_to_eqs = defaultdict(list)
    for i, vs in enumerate(incidence):
        for v in vs:
            var_to_eqs[v].append(i)

    reached = set(seed_indices)
    stack = [i for i in seed_indices if i not in sinks]
    seen_vars: set[str] = set()
    while stack:
        i = stack.pop()
        for v in incidence[i] - seen_vars:
            seen_vars.add(v)
            for j in var_to_eqs[v]:
                if j not in reached:
                    reached.add(j)
                    if j not in sinks:
                        stack.append(j)
    return reached


def resolve_impact_naive(post_change_ir: dict, seed_equation_names: list[str], states_as_knowns: bool = True) -> dict:
    """Same return shape as resolver.resolve_impact."""
    m = compute_matching(post_change_ir)
    units = compute_matched_units(post_change_ir)
    names = _eq_names(m, len(post_change_ir["f_x"]))
    name_to_idx = {n: i for i, n in enumerate(names)}
    for s in seed_equation_names:
        if s not in name_to_idx:
            raise ValueError(f"seed equation {s!r} not found in the post-change model")

    closure = incidence_closure(post_change_ir, [name_to_idx[s] for s in seed_equation_names], states_as_knowns)
    affected_eq_names = {names[i] for i in closure}
    eq_to_unit = {eq: uid for uid, members in units.items() for eq in members}
    return {
        "seed_equations": sorted(seed_equation_names),
        "affected_equations": sorted(affected_eq_names),
        "affected_units": sorted({eq_to_unit[eq] for eq in affected_eq_names}),
        "total_units": len(units),
        "units": units,
    }


MODELS_ROOT = "models/journal_baseline"
SCALE_SIZES = [50, 250, 1000]

FIXTURE_CELLS = [
    dict(label="ThermalNetwork/swap", baseline_path="models/thermal_network/ThermalNetwork.mo",
         changed_path="models/thermal_network_swapped/ThermalNetwork.mo", model_name="ThermalNetwork",
         seed=["Q1"], t_end=3.0, dt=0.5),
    dict(label="RLCCircuit/swap", baseline_path="models/rlc_circuit/RLCCircuit.mo",
         changed_path="models/rlc_circuit_swapped/RLCCircuit.mo", model_name="RLCCircuit",
         seed=["i"], t_end=3.0, dt=0.5),
    dict(label="ThermalNetwork/sensor-add", baseline_path="models/thermal_network/ThermalNetwork.mo",
         changed_path="models/thermal_network_sensor/ThermalNetwork.mo", model_name="ThermalNetwork",
         seed=["Qtotal"], t_end=3.0, dt=0.5),
    dict(label="ThermalNetwork/removal", baseline_path="models/thermal_network/ThermalNetwork.mo",
         changed_path="models/thermal_network_removed/ThermalNetwork.mo", model_name="ThermalNetwork",
         seed=["T2"], t_end=3.0, dt=0.5),
]


def comparison_cells(sizes: list[int] = SCALE_SIZES) -> list[dict]:
    """Every cell in measure_msl.run_cell's keyword format plus a label:
    the 4 MSL cells, the 4 change.py fixture changes, and ThermalChain{N}
    with swap_room_conductance at the middle room. Chain variants are
    written to their own directories under models/journal_baseline/."""
    from measure_msl import CELLS
    from scaled_models import generate_thermal_chain, swap_room_conductance

    msl_labels = ["MslRcCircuit/swap", "MslThermalChain/swap", "MslRcCircuit/sensor-add", "MslResistorNetwork/removal"]
    cells = [dict(c, label=lbl) for c, lbl in zip(CELLS, msl_labels)] + list(FIXTURE_CELLS)
    for n in sizes:
        name, mid = f"ThermalChain{n}", n // 2
        base = generate_thermal_chain(n, f"{MODELS_ROOT}/{name}/{name}.mo")
        chg = swap_room_conductance(base, mid, f"{MODELS_ROOT}/{name}_swapped/{name}.mo")
        cells.append(dict(label=f"{name}/swap", baseline_path=str(base), changed_path=str(chg),
                          model_name=name, seed=[f"Q{mid}env"], t_end=2.0, dt=1.0))
    return cells


def content_hash_oracle(model_name: str, baseline_ir: dict, changed_ir: dict) -> dict:
    """Units whose generated C source text is new or differs from the
    baseline's, with the shared layout exactly as measure_msl.run_cell
    builds it. This is what a Make/Bazel content-hash build would
    recompile. Same return shape as resolve_impact, plus the filenames."""
    layout = build_layout(baseline_ir, changed_ir)
    base_src = generate_all_unit_sources(model_name, baseline_ir, layout)
    chg_src = generate_all_unit_sources(model_name, changed_ir, layout)
    units = compute_matched_units(changed_ir)
    file_to_unit = {f"{model_name}_unit_{unit_function_suffix(uid, mem)}.c": uid for uid, mem in units.items()}
    changed_files = {f for f, text in chg_src.items() if base_src.get(f) != text}
    return {
        "affected_units": sorted(file_to_unit[f] for f in changed_files),
        "affected_c_filenames": sorted(changed_files),
        "removed_c_filenames": sorted(set(base_src) - set(chg_src)),
        "total_units": len(units),
        "units": units,
    }


def _timed(fn, repeats: int) -> tuple[object, list[float]]:
    import time
    times, out = [], None
    for _ in range(repeats):
        t0 = time.perf_counter()
        out = fn()
        times.append(time.perf_counter() - t0)
    return out, times


def graph_level_comparison(cells: list[dict], repeats: int = 5) -> list[dict]:
    """Per cell: units, affected units, ripple and soundness for the
    paper's method / the naive baseline / the content-hash oracle, plus
    pure-Python resolver wall time (perf_counter, `repeats` runs). No gcc."""
    import statistics

    from compile import compile_model
    from matched_graph import build_matched_graph
    from resolver import resolve_impact
    from soundness import check_soundness

    rows = []
    for c in cells:
        base = compile_model(c["baseline_path"], c["model_name"], roots=c.get("baseline_roots")).ir
        chg = compile_model(c["changed_path"], c["model_name"], roots=c.get("changed_roots")).ir
        seed = c["seed"]
        methods = {
            "matching": lambda: resolve_impact(chg, seed, graph_builder=build_matched_graph),
            "naive": lambda: resolve_impact_naive(chg, seed),
            "oracle": lambda: content_hash_oracle(c["model_name"], base, chg),
        }
        row = {"cell": c["label"], "model_name": c["model_name"], "seed": ",".join(seed),
               "n_equations": len(chg["f_x"])}
        sets = {}
        for name, fn in methods.items():
            result, times = _timed(fn, repeats)
            sets[name] = set(result["affected_units"])
            snd = check_soundness(base, chg, result, graph_builder=build_matched_graph)
            row["total_units"] = result["total_units"]
            row[f"{name}_affected"] = len(sets[name])
            row[f"{name}_ripple"] = len(sets[name]) / result["total_units"]
            row[f"{name}_sound"] = snd["sound"]
            row[f"{name}_time_mean_s"] = statistics.mean(times)
            row[f"{name}_time_stdev_s"] = statistics.stdev(times) if repeats > 1 else 0.0
        # The baseline's own decision work alone (no matching, no unit mapping).
        names = _eq_names(compute_matching(chg), len(chg["f_x"]))
        seed_idx = [names.index(s) for s in seed]
        _, times = _timed(lambda: incidence_closure(chg, seed_idx), repeats)
        row["naive_closure_only_time_mean_s"] = statistics.mean(times)
        row["actually_changed_units"] = len(snd["actually_changed_units"])
        row["oracle_equals_actually_changed"] = sets["oracle"] == set(snd["actually_changed_units"])
        weak = resolve_impact_naive(chg, seed, states_as_knowns=False)
        row["naive_no_state_knowledge_affected"] = len(weak["affected_units"])
        row["naive_no_state_knowledge_ripple"] = len(weak["affected_units"]) / weak["total_units"]
        row["matching_subset_of_naive"] = sets["matching"] <= sets["naive"]
        row["oracle_subset_of_matching"] = sets["oracle"] <= sets["matching"]
        row["repeats"] = repeats
        rows.append(row)
        print(f"{row['cell']}: units={row['total_units']} matching={row['matching_affected']} "
              f"naive={row['naive_affected']} oracle={row['oracle_affected']} "
              f"naive_no_states={row['naive_no_state_knowledge_affected']}", flush=True)
    return rows


if __name__ == "__main__":
    import csv
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else "results/journal_upgrade_phase2_ripple.csv"
    rows = graph_level_comparison(comparison_cells())
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")
