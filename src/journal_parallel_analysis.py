"""Statistics over the parallel journal-upgrade timing results (Experiment 5).

Read-only: consumes
  results/journal_upgrade/link_ablation_parallel/link_ablation.csv
  results/journal_upgrade/locality_parallel/locality_timing.csv
  results/journal_upgrade/rc_ladder_parallel/rc_ladder_timing.csv
  results/measurements_scale.csv (the paper's Table "speedup vs model size")
and writes docs/journal_upgrade/parallel_analysis/tables.md.

Every interval is a 95% t-interval over the repeats of ONE configuration
(repeated builds of one cell, not independent populations); speedup
intervals are Fieller intervals on the ratio of two such means
(src/journal_stats_audit.py). "disc" = first pair discarded (n=5),
"all" = all six pairs (n=6). Cross-config ratios pair two different cells
measured in the same session; they share the machine drift of that
session, which these intervals do not model.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

import numpy as np
import pandas as pd

from journal_parallel_timing import speedup

R = Path("results/journal_upgrade")
OUT = Path("docs/journal_upgrade/parallel_analysis/tables.md")


def raw(row, col, disc=True):
    xs = json.loads(row[col])
    return xs[1:] if disc else xs


def ci(row, kind, tag="disc"):
    return f"{row[f'{kind}_{tag}_mean_s']:.2f} [{row[f'{kind}_{tag}_ci_low_s']:.2f}, {row[f'{kind}_{tag}_ci_high_s']:.2f}]"


def sp(row, tag="disc"):
    return f"{row[f'speedup_{tag}']:.2f} [{row[f'speedup_{tag}_fieller_low']:.2f}, {row[f'speedup_{tag}_fieller_high']:.2f}]"


def ok(row):
    flags = [row.outputs_identical, row.reused_byte_identical, row.c_diff_subset_of_affected]
    return "yes" if all(str(f) == "True" for f in flags) else "NO"


def clean_link_rows(lines) -> pd.DataFrame | None:
    """One row per (n_rooms, config): rows flagged by src/journal_suspend_check.py are
    excluded (a rerun row replaces them); every exclusion is listed, nothing is dropped
    silently. Falls back to the raw CSV if the suspend check has not been run."""
    p = R / "link_ablation_parallel/link_ablation.csv"
    if not p.exists():
        return None
    chk = p.with_name(p.stem + "_suspend_check.csv")
    d = pd.read_csv(chk if chk.exists() else p)
    if "suspend_in_window" in d.columns:
        bad = d[d.suspend_in_window.astype(str) == "True"]
        if len(bad):
            lines += ["Excluded (overlapped a Windows suspend event; see results *_suspend_check.csv):", ""]
            lines += [f"- N={r.n_rooms} {r.config} ({r.start} to {r.end}): {r.suspend_events[:160]}" for _, r in bad.iterrows()]
            lines.append("")
        d = d[d.suspend_in_window.astype(str) != "True"]
    dup = d.duplicated(["n_rooms", "config"], keep=False)
    if dup.any():
        raise SystemExit(f"more than one clean row per cell: {d[dup][['n_rooms', 'config']].values.tolist()}")
    return d


def link_tables(lines):
    d = clean_link_rows(lines)
    if d is None:
        return
    lines += ["## Link ablation (ThermalChain N, room loss edit at N/2, 2 units affected)", "",
              "| N | config | full s, disc [CI] | incr s, disc [CI] | speedup disc [Fieller] | speedup all [Fieller] "
              "| incr CV disc | first incr / median rest | median incr link s | correct |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in d.sort_values(["n_rooms", "config"]).iterrows():
        lines.append(f"| {r.n_rooms} | {r.config} | {ci(r, 'full')} | {ci(r, 'incr')} | {sp(r)} | {sp(r, 'all')} | "
                     f"{r.incr_disc_cv:.1%} | {r.first_incr_over_median_rest:.2f} | "
                     f"{statistics.median(raw(r, 'incr_link_raw_s')):.3f} | {ok(r)} |")
    lines += ["", "Cross-configuration ratios (same session; first pair discarded; Fieller):", "",
              "| N | numerator (full) | denominator (incr) | ratio [Fieller] |", "|---|---|---|---|"]
    for n, g in d.groupby("n_rooms"):
        g = g.set_index("config")
        for num, den in (("static", "dynamic_stripped"), ("dynamic_unstripped", "dynamic_stripped"),
                         ("dynamic_stripped", "dynamic_stripped"), ("static", "static")):
            if num in g.index and den in g.index:
                q, lo, hi = speedup(raw(g.loc[num], "full_raw_s"), raw(g.loc[den], "incr_raw_s"))
                lines.append(f"| {n} | {num} | {den} | {q:.2f} [{lo:.2f}, {hi:.2f}] |")
        if {"static", "dynamic_stripped"} <= set(g.index):
            q, lo, hi = speedup(raw(g.loc["dynamic_stripped"], "full_raw_s"), raw(g.loc["static"], "full_raw_s"))
            lines.append(f"| {n} | dynamic_stripped full | static full | {q:.2f} [{lo:.2f}, {hi:.2f}] (full-rebuild cost ratio) |")
    scale = pd.read_csv("results/measurements_scale.csv").set_index("n_rooms")
    lines += ["", "Paper Table (measurements_scale.csv, n=3, warm-up discarded) vs this session's dynamic_stripped:", "",
              "| N | paper speedup | this run speedup disc [Fieller] | paper inside interval |", "|---|---|---|---|"]
    for _, r in d[d.config == "dynamic_stripped"].iterrows():
        if r.n_rooms in scale.index:
            ps = scale.loc[r.n_rooms, "measured_speedup"]
            inside = r.speedup_disc_fieller_low <= ps <= r.speedup_disc_fieller_high
            lines.append(f"| {r.n_rooms} | {ps:.2f} | {sp(r)} | {inside} |")
    lines.append("")


def cell_table(lines, path, title, key_cols):
    if not path.exists():
        return None
    d = pd.read_csv(path)
    lines += [f"## {title}", "",
              "| " + " | ".join(key_cols) + " | affected/total | recompiled frac | full s disc [CI] | incr s disc [CI] "
              "| speedup disc [Fieller] | speedup all | first incr / median rest | correct |",
              "|" + "---|" * (len(key_cols) + 8)]
    for _, r in d.iterrows():
        lines.append("| " + " | ".join(str(r[k]) for k in key_cols) +
                     f" | {r.affected_units}/{r.total_units} | {r.recompile_fraction:.4f} | {ci(r, 'full')} | "
                     f"{ci(r, 'incr')} | {sp(r)} | {r.speedup_all:.2f} | {r.first_incr_over_median_rest:.2f} | {ok(r)} |")
    lines.append("")
    return d


def locality_fit(lines, d):
    for fam, g in d.groupby("family"):
        x, y = g.n_recompiled.to_numpy(float), g.incr_disc_mean_s.to_numpy()
        if np.ptp(x) > 0:
            slope, icpt = np.polyfit(x, y, 1)
            r2 = np.corrcoef(x, y)[0, 1] ** 2
            lines.append(f"- {fam}: incr_mean = {icpt:.3f} s + {slope * 1000:.2f} ms x (units recompiled), "
                         f"R^2 = {r2:.3f} over {len(g)} positions (least squares on cell means, descriptive only).")
        else:
            lo, hi = g.incr_disc_mean_s.min(), g.incr_disc_mean_s.max()
            overlap = g.incr_disc_ci_low_s.max() <= g.incr_disc_ci_high_s.min()
            lines.append(f"- {fam}: recompiled set constant ({int(x[0])} units) at all {len(g)} positions; incr mean "
                         f"ranges {lo:.2f}-{hi:.2f} s; all position CIs share a common point: {overlap}; "
                         f"speedup ranges {g.speedup_disc.min():.2f}-{g.speedup_disc.max():.2f}.")
    lines.append("")


def first_touch(lines, frames):
    rows = pd.concat([f[["first_incr_over_median_rest", "first_full_over_median_rest"]] for f in frames if f is not None])
    if rows.empty:
        return
    a, b = rows.first_incr_over_median_rest, rows.first_full_over_median_rest
    lines += ["## First-rebuild (warm-up candidate) effect across all cells", "",
              f"- cells: {len(rows)}; first incremental / median of the other 5: median {a.median():.2f}, "
              f"min {a.min():.2f}, max {a.max():.2f}; cells with ratio > 2: {(a > 2).sum()}",
              f"- first full / median of the other 5: median {b.median():.2f}, min {b.min():.2f}, max {b.max():.2f}", ""]


def main():
    lines = ["# Parallel experiments: statistical tables", "",
             "Generated by src/journal_parallel_analysis.py. Intervals: 95% t over repeats of one cell; "
             "speedups: Fieller. These are repeated measurements of one configuration, not samples of "
             "independent populations; they describe measurement noise on this machine only.", ""]
    link_tables(lines)
    loc = cell_table(lines, R / "locality_parallel/locality_timing.csv", "Locality timing (edit position sweep)",
                     ["family", "n", "position"])
    if loc is not None:
        locality_fit(lines, loc)
    rc = cell_table(lines, R / "rc_ladder_parallel/rc_ladder_timing.csv", "RC ladder timing", ["n", "change", "position"])
    link = clean_link_rows([])
    first_touch(lines, [link, loc, rc])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
