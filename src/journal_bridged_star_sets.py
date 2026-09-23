"""Graph-level Phase 2 comparison extended to the BridgedStar topology (star with genuine
coupled blocks): paper reachability vs matching-free baseline vs generated-source diff.
Pure Python, no builds. Output: results/journal_upgrade/bridged_star_sets.csv"""
from pathlib import Path

import pandas as pd

from compile import compile_model
from journal_generators import generate_bridged_star, swap_branch_bridge
from journal_naive_resolver import resolve_impact_naive
from journal_phase2_verify_oracle import _unit_files
from matched_graph import build_matched_graph
from measure_msl import _affected_c_filenames
from model_layout import build_layout
from resolver import resolve_impact
from unit_codegen import generate_all_unit_sources

ROOT = Path("models/journal_bridged_star_sets")
rows = []
for n in (10, 50, 250):
    name = f"BridgedStar{n}"
    base = generate_bridged_star(n, ROOT / f"{name}_base" / f"{name}.mo")
    b = compile_model(str(base), name).ir
    for k in (1, n // 2, n):
        chg = swap_branch_bridge(base, k, ROOT / f"{name}_chg{k}" / f"{name}.mo")
        c = compile_model(str(chg), name).ir
        seed = [f"J{k}"]
        layout = build_layout(b, c)
        bs, cs = generate_all_unit_sources(name, b, layout), generate_all_unit_sources(name, c, layout)
        oracle = {f for f, t in cs.items() if bs.get(f) != t}
        paper = _affected_c_filenames(name, c, resolve_impact(c, seed, graph_builder=build_matched_graph))
        naive = _unit_files(name, c, resolve_impact_naive(c, seed)["affected_units"])
        rows.append(dict(n=n, branch=k, total_units=len(cs), paper=len(paper), baseline=len(naive), oracle=len(oracle),
                         oracle_subset_paper=oracle <= paper, paper_subset_baseline=paper <= naive))
        print(rows[-1], flush=True)
out = Path("results/journal_upgrade/bridged_star_sets.csv")
pd.DataFrame(rows).to_csv(out, index=False)
print("wrote", out)
