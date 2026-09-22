"""Phase 2 timing analysis. Win/tie rule fixed before the final cell finished:
strategy A beats B on a cell only if the 95% Welch CI for mean(incr_A) - mean(incr_B)
excludes 0; otherwise it is a tie. Calibration: pairs that recompile the SAME unit
set do identical work, so any "win" among them measures the rule's false-positive
rate on this machine. Raw repeat times come from the timing CSV; no outlier removal.

Outputs: results/journal_upgrade_phase2_timing_stats.csv, results/journal_upgrade_phase2_pairwise.csv
"""
from __future__ import annotations

import json
import math
import statistics as st
from pathlib import Path

import pandas as pd

from journal_stats_audit import mean_ci, ratio_fieller_ci, t_crit

TIMING = Path("results/journal_upgrade_phase2_timing.csv")
SETS = Path("results/journal_upgrade_phase2_oracle_independent.json")
KEY = {"matching": "paper", "naive": "baseline", "oracle": "oracle"}


def _raw(s: str) -> list[float]:
    return [float(x) for x in str(s).split(";") if x]


def _summ(xs):
    n, m, sd = len(xs), st.mean(xs), st.stdev(xs) if len(xs) > 1 else math.nan
    se, t, h = mean_ci(m, sd, n)
    return n, m, st.median(xs), sd, se, h, min(xs), max(xs)


def welch(a, b):
    ma, mb, va, vb, na, nb = st.mean(a), st.mean(b), st.variance(a), st.variance(b), len(a), len(b)
    se = math.sqrt(va / na + vb / nb)
    df = se ** 4 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    h = t_crit(int(df)) * se  # floor(df): conservative
    return ma - mb, ma - mb - h, ma - mb + h


def main():
    df = pd.read_csv(TIMING)
    sets = {r["cell"]: r["sets"] for r in json.loads(SETS.read_text())}
    stats, pairs = [], []
    for _, r in df.iterrows():
        f, i = _raw(r.full_rebuild_times_s), _raw(r.incremental_times_s)
        nf, mf, medf, sdf, sef, hf, minf, maxf = _summ(f)
        ni, mi, medi, sdi, sei, hi, mini, maxi = _summ(i)
        lo, up = ratio_fieller_ci(mf, sef, mi, sei, t_crit(min(nf, ni) - 1))
        stats.append(dict(cell=r.cell, strategy=r.strategy, strategy_order=r.strategy_order,
                          units_recompiled=r.n_units_recompiled, total_units=r.total_units, n=ni,
                          full_mean_s=mf, full_median_s=medf, full_sd_s=sdf, full_ci95_half_s=hf, full_min_s=minf, full_max_s=maxf,
                          incr_mean_s=mi, incr_median_s=medi, incr_sd_s=sdi, incr_cv=sdi / mi, incr_ci95_half_s=hi,
                          incr_min_s=mini, incr_max_s=maxi, speedup=mf / mi, speedup_ci95_lo=lo, speedup_ci95_hi=up,
                          outputs_identical=r.outputs_identical, reuse_ok=r.reused_objects_byte_identical_to_cache))
    for cell, g in df.groupby("cell", sort=False):
        by = {r.strategy: _raw(r.incremental_times_s) for _, r in g.iterrows()}
        for a, b in (("matching", "naive"), ("oracle", "matching"), ("oracle", "naive")):
            if a in by and b in by:
                d, lo, hi = welch(by[a], by[b])
                same_set = cell in sets and set(sets[cell][KEY[a]]) == set(sets[cell][KEY[b]])
                verdict = "tie" if lo <= 0 <= hi else (f"{a} faster" if hi < 0 else f"{b} faster")
                pairs.append(dict(cell=cell, a=a, b=b, same_recompile_set=same_set, diff_mean_s=d,
                                  diff_ci95_lo_s=lo, diff_ci95_hi_s=hi, verdict=verdict))
    pd.DataFrame(stats).to_csv("results/journal_upgrade_phase2_timing_stats.csv", index=False)
    p = pd.DataFrame(pairs)
    p.to_csv("results/journal_upgrade_phase2_pairwise.csv", index=False)
    pd.set_option("display.width", 220)
    print(pd.DataFrame(stats)[["cell", "strategy", "units_recompiled", "total_units", "incr_mean_s", "incr_cv",
                               "speedup", "speedup_ci95_lo", "speedup_ci95_hi", "outputs_identical"]].round(3).to_string(index=False))
    print(p.round(3).to_string(index=False))
    same = p[p.same_recompile_set]
    print(f"\ncalibration: {int((same.verdict != 'tie').sum())}/{len(same)} identical-work pairs classified as a win")


if __name__ == "__main__":
    main()
