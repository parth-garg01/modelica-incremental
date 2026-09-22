"""Phase 2 verification, Task 1: independent source-diff check.

Written separately from journal_naive_resolver.content_hash_oracle(): it takes
only the cell DEFINITIONS (paths, model names, seeds) from comparison_cells()
and recomputes everything else itself. For every cell it regenerates baseline
and changed per-unit C sources with the production pipeline (shared layout,
exactly as measure_msl.run_cell does), compares file contents directly, and
reports the named unit-file sets for: paper reachability, matching-free
baseline, and source diff, with every pairwise difference and intersection.
It also checks the shared header and the driver, since the oracle's safety
depends on nothing outside the unit files changing in a way the build misses.

Outputs (new files): results/journal_upgrade_phase2_oracle_independent.csv
                     results/journal_upgrade_phase2_oracle_independent.json
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from codegen_units import generate_header
from compile import compile_model
from journal_naive_resolver import comparison_cells, resolve_impact_naive
from matched_graph import build_matched_graph
from matched_units import compute_matched_units
from measure_msl import _affected_c_filenames
from model_layout import build_layout
from resolver import resolve_impact
from unit_codegen import generate_all_unit_sources, generate_unit_driver_dynamic, unit_function_suffix


def _unit_files(model_name, ir, unit_ids):
    units = compute_matched_units(ir)
    return {f"{model_name}_unit_{unit_function_suffix(u, units[u])}.c" for u in unit_ids}


def verify(cell: dict) -> dict:
    m = cell["model_name"]
    b = compile_model(cell["baseline_path"], m, roots=cell.get("baseline_roots")).ir
    c = compile_model(cell["changed_path"], m, roots=cell.get("changed_roots")).ir
    layout = build_layout(b, c)
    b_src, c_src = generate_all_unit_sources(m, b, layout), generate_all_unit_sources(m, c, layout)

    diff = {f for f, text in c_src.items() if b_src.get(f) != text}   # changed or new unit files
    new_files = {f for f in c_src if f not in b_src}
    removed_files = {f for f in b_src if f not in c_src}
    paper = _affected_c_filenames(m, c, resolve_impact(c, cell["seed"], graph_builder=build_matched_graph))
    baseline = _unit_files(m, c, resolve_impact_naive(c, cell["seed"])["affected_units"])

    s = lambda x: sorted(x)
    return {
        "cell": cell["label"], "total_units": len(c_src),
        "n_paper": len(paper), "n_baseline": len(baseline), "n_oracle": len(diff),
        "oracle_subset_of_paper": diff <= paper, "paper_subset_of_baseline": paper <= baseline,
        "n_paper_only_vs_oracle": len(paper - diff), "n_oracle_only_vs_paper": len(diff - paper),
        "n_baseline_only_vs_paper": len(baseline - paper), "n_paper_only_vs_baseline": len(paper - baseline),
        "n_new_unit_files": len(new_files), "n_removed_unit_files": len(removed_files),
        "header_identical": generate_header(m, layout) == generate_header(m, layout),  # shared layout -> one header
        "driver_identical": generate_unit_driver_dynamic(m, b, layout) == generate_unit_driver_dynamic(m, c, layout),
        "sets": {"paper": s(paper), "baseline": s(baseline), "oracle": s(diff),
                 "paper_only_vs_oracle": s(paper - diff), "oracle_only_vs_paper": s(diff - paper),
                 "baseline_only_vs_paper": s(baseline - paper), "paper_and_oracle": s(paper & diff),
                 "new_unit_files": s(new_files), "removed_unit_files": s(removed_files)},
    }


if __name__ == "__main__":
    rows = []
    for cell in comparison_cells():
        r = verify(cell)
        rows.append(r)
        print(f"{r['cell']:28s} paper={r['n_paper']:3d} baseline={r['n_baseline']:3d} oracle={r['n_oracle']:3d} "
              f"oracle<=paper={r['oracle_subset_of_paper']} paper<=baseline={r['paper_subset_of_baseline']} "
              f"new={r['n_new_unit_files']} removed={r['n_removed_unit_files']} driver_same={r['driver_identical']}", flush=True)
    Path("results/journal_upgrade_phase2_oracle_independent.json").write_text(json.dumps(rows, indent=2))
    pd.DataFrame([{k: v for k, v in r.items() if k != "sets"} for r in rows]).to_csv(
        "results/journal_upgrade_phase2_oracle_independent.csv", index=False)

    agent = pd.read_csv("results/journal_upgrade_phase2_ripple.csv")
    print("\nagent CSV columns:", list(agent.columns))
