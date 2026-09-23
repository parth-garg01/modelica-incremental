"""Journal upgrade, phase 3: graph-level and codegen-text-level validation
of generate_rc_ladder(N), its change injectors (src/journal_rc_changes.py),
a matched-size thermal-chain comparison, and the BridgedStar generator
(src/journal_generators.py). NO C build: nothing here calls gcc or
src/c_build.py; code generation is pure-Python text emission only.

Writes results/journal_upgrade/rc_ladder_parallel/rc_validation.csv.
Run: PYTHONPATH=src python src/journal_phase3_validate.py
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import rumoca as rm

from codegen_units import generate_header
from journal_generators import generate_bridged_star, swap_branch_bridge
from journal_rc_changes import add_segment_probe, swap_segment_resistance
from matched_graph import build_matched_graph
from matched_units import compute_matched_units
from matching import compute_matching
from model_layout import build_layout
from resolver import resolve_impact
from scaled_models import generate_rc_ladder, generate_thermal_chain, swap_room_conductance
from soundness import check_soundness
from unit_codegen import generate_all_unit_sources, generate_unit_driver_dynamic

ROOT = Path("models") / "journal_rc_parallel"
OUT_CSV = Path("results") / "journal_upgrade" / "rc_ladder_parallel" / "rc_validation.csv"


def load(path: Path, model_name: str) -> tuple[dict, object, float]:
    """Same calls as src/compile.py's compile_model, plus Rumoca's own
    structure() from the SAME loaded model (compile_model discards it)."""
    t0 = time.perf_counter()
    model = rm.Session().load(str(path), model=model_name)
    elapsed = time.perf_counter() - t0
    ir = json.loads(model.to_json(stage="dae"))
    # Rumoca structure() is superlinear (> 90 s on ThermalChain1000); only used as a cross-check up to 800 equations
    return ir, (model.structure() if len(ir["f_x"]) <= 800 else None), elapsed


def graph_row(family: str, n: int, ir: dict, st, compile_s: float, expected_eq: int) -> dict:
    m = compute_matching(ir)
    units = compute_matched_units(ir)
    sizes = sorted((len(v) for v in units.values()), reverse=True)
    g = build_matched_graph(ir)
    states = list(ir["x"].keys())
    # States-as-knowns: src/matching.py drops states from eq_involves, so
    # ("var", state) never appears in the matched graph at all; the
    # state's own row writes ("der", state), which no equation reads.
    states_ok = all(("var", s) not in g and g.out_degree(("der", s)) == 0 for s in states)
    n_eq = len(ir["f_x"])
    return {
        "row_type": "graph", "family": family, "n": n, "n_equations": n_eq,
        "expected_equations": expected_eq, "eq_count_ok": n_eq == expected_eq,
        "n_states": len(states), "n_algebraic": len(ir["y"]) + len(ir.get("w", {})),
        "is_matched": m.is_matched, "n_unmatched": len(m.unmatched_equations),
        "agrees_with_natural_targets": m.agrees_with_natural_targets(),
        "n_units": len(units), "n_coupled_units": sum(1 for s in sizes if s > 1),
        "largest_unit": sizes[0], "rumoca_n_blocks": st.n_blocks if st else "skipped",
        "rumoca_algebraic_loops": st.n_algebraic_loops if st else "skipped", "rumoca_matched": st.is_matched if st else "skipped",
        "units_eq_rumoca_blocks": len(units) == st.n_blocks if st else "skipped",
        "states_are_non_edge_sources": states_ok, "compile_s": round(compile_s, 3),
    }


def codegen_check(model_name: str, ir: dict, layout) -> dict:
    """Exactly measure_msl._as_build_sources's three generator calls,
    without importing c_build."""
    t0 = time.perf_counter()
    units_c = generate_all_unit_sources(model_name, ir, layout)
    driver = generate_unit_driver_dynamic(model_name, ir, layout)
    header = generate_header(model_name, layout)
    elapsed = time.perf_counter() - t0
    return {"units_c": units_c, "driver": driver, "header": header, "codegen_s": elapsed}


def change_row(family, n, idx, change, seed, base_ir, chg_ir, model_name, codegen=True) -> dict:
    impact = resolve_impact(chg_ir, seed, graph_builder=build_matched_graph)
    sound = check_soundness(base_ir, chg_ir, impact, graph_builder=build_matched_graph)
    row = {
        "row_type": "change", "family": family, "n": n, "n_equations": len(chg_ir["f_x"]),
        "change": change, "index": idx, "seed": ",".join(seed),
        "n_units": impact["total_units"], "affected_units": len(impact["affected_units"]),
        "affected_unit_ids": " ".join(impact["affected_units"]),
        "ripple_fraction": round(len(impact["affected_units"]) / impact["total_units"], 6),
        "actually_changed_units": " ".join(sound["actually_changed_units"]),
        "sound": sound["sound"], "missed_units": " ".join(sound["missed_units"]),
    }
    if codegen:
        cg = codegen_check(model_name, chg_ir, build_layout(base_ir, chg_ir))
        row["codegen_units_emitted"] = len(cg["units_c"])
        row["codegen_s"] = round(cg["codegen_s"], 3)
    return row


def main() -> None:
    rows: list[dict] = []

    # 1-2. RC ladder: graph validation + codegen text at every size.
    rc_irs = {}
    for n in [10, 50, 100, 250, 500, 1000]:
        name = f"RcLadder{n}"
        path = generate_rc_ladder(n, ROOT / name / f"{name}.mo")
        ir, st, cs = load(path, name)
        rc_irs[n] = ir
        row = graph_row("rc_ladder", n, ir, st, cs, 2 * n + 1)
        cg = codegen_check(name, ir, build_layout(ir))
        vs_src = cg["units_c"][f"{name}_unit_Vs.c"]
        row["codegen_units_emitted"] = len(cg["units_c"])
        row["codegen_s"] = round(cg["codegen_s"], 3)
        row["vs_unit_has_sin_of_time"] = "sin(" in vs_src and "v->time" in vs_src
        row["driver_sets_and_advances_time"] = "v.time = 0.0;" in cg["driver"] and "v.time += dt;" in cg["driver"]
        row["header_has_time_field"] = "real_t time;" in cg["header"]
        rows.append(row)
        if n == 10:
            print(vs_src)
        print(n, {k: row[k] for k in ("n_equations", "is_matched", "n_units", "rumoca_n_blocks", "largest_unit")})

    # 3. RC injectors at N in {50, 250, 1000}, segment 1 / middle / N.
    for n in [50, 250, 1000]:
        name = f"RcLadder{n}"
        base = ROOT / name / f"{name}.mo"
        for i in sorted({1, n // 2, n}):
            for change, fn, seed in [
                ("swap_segment_resistance", swap_segment_resistance, [f"I{i}"]),
                ("add_segment_probe", add_segment_probe, [f"P{i}"]),
            ]:
                chg = fn(base, i, ROOT / f"{name}_{change}_{i}" / f"{name}.mo")
                chg_ir, _, _ = load(chg, name)
                row = change_row("rc_ladder", n, i, change, seed, rc_irs[n], chg_ir, name)
                rows.append(row)
                print(change, n, i, row["affected_unit_ids"], row["sound"])

    # 4. Thermal chain at matched equation counts (3M-1 ~= 2N+1).
    for m_rooms in [34, 167, 667]:
        name = f"ThermalChain{m_rooms}"
        base = generate_thermal_chain(m_rooms, ROOT / f"{name}_cmp" / f"{name}.mo")
        ir, st, cs = load(base, name)
        rows.append(graph_row("thermal_chain", m_rooms, ir, st, cs, 3 * m_rooms - 1))
        for i in sorted({1, m_rooms // 2, m_rooms}):
            chg = swap_room_conductance(base, i, ROOT / f"{name}_cmp_swapped_{i}" / f"{name}.mo")
            chg_ir, _, _ = load(chg, name)
            rows.append(change_row("thermal_chain", m_rooms, i, "swap_room_conductance",
                                   [f"Q{i}env"], ir, chg_ir, name, codegen=False))

    # 6. BridgedStar: graph + codegen + injector.
    for n in [10, 50, 100, 250, 500]:
        name = f"BridgedStar{n}"
        base = generate_bridged_star(n, ROOT / name / f"{name}.mo")
        ir, st, cs = load(base, name)
        row = graph_row("bridged_star", n, ir, st, cs, 6 * n + 1)
        cg = codegen_check(name, ir, build_layout(ir))
        row["codegen_units_emitted"] = len(cg["units_c"])
        row["codegen_s"] = round(cg["codegen_s"], 3)
        rows.append(row)
        print(n, {k: row[k] for k in ("n_equations", "is_matched", "n_units", "n_coupled_units", "largest_unit",
                                      "rumoca_n_blocks", "rumoca_algebraic_loops")})
        if n in (50, 250):
            for k in sorted({1, n // 2, n}):
                chg = swap_branch_bridge(base, k, ROOT / f"{name}_swapR2_{k}" / f"{name}.mo")
                chg_ir, _, _ = load(chg, name)
                r = change_row("bridged_star", n, k, "swap_branch_bridge", [f"J{k}"], ir, chg_ir, name)
                rows.append(r)
                print("swap_branch_bridge", n, k, r["affected_unit_ids"], r["sound"])

    fields: list[str] = []
    for r in rows:
        fields += [k for k in r if k not in fields]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT_CSV}")


if __name__ == "__main__":
    main()
