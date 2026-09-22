"""Per-cell statistical audit of timing result files (journal upgrade).

Reads one or more results files (CSV, parquet, or the Stage-0 text log)
and writes one row per (file, row, metric) with n, mean, sd, CV, a
t-based 95% CI for the mean, min/max/raw values when raw per-repeat
times are stored, and, for every full/incremental pair, the speedup
ratio with two ratio CIs (endpoint and Fieller). Deterministic columns
(unit counts, ripple, bit-identical flags) are emitted with kind
"deterministic" and no interval. Read-only: never runs a build.

Usage (from the repo root, PYTHONPATH=src):
    python src/journal_stats_audit.py results/measurements_scale.csv ... \
        --out results/journal_upgrade_stats_existing.csv \
        [--repeats measurements_msl.csv=5]
    python src/journal_stats_audit.py --selftest

Repeat counts: taken from a `repeats`/`*_repeats` column, else the
length of a raw-times list column, else --repeats, else KNOWN_REPEATS
(hard-coded from the producing scripts, cited per entry). A cell whose
n cannot be established gets n=NaN and no CI rather than a guess.
"""
from __future__ import annotations

import argparse
import ast
import math
import re
import statistics
import sys
from pathlib import Path

import pandas as pd

# Two-sided 95% Student t critical values t_{0.975, df}, df = 1..30,
# copied from a standard t-table (scipy is not a project dependency).
# ponytail: df > 30 falls back to 1.96 (slightly narrow); add scipy if
# future cells use 30 < n < 120 and the ~2% difference matters.
T975 = [None, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
        2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
        2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def t_crit(df: int) -> float:
    if df < 1:
        return math.nan
    return T975[df] if df <= 30 else 1.96


# Repeat counts for files that do not store them, from the producing script.
KNOWN_REPEATS = {
    "measurements_msl": 5,              # src/measure_msl.py REPEATS = 5 (run_cell default)
    "measurements_break_even": 3,       # src/break_even.py FULL_REBUILD_REPEATS = 3
    "measurements_validate_scale": 1,   # src/validate_scale.py run_cell(..., repeats=1)
    "measurements_c_stage0_rerun": 5,   # src/measure_c.py REPEATS = 5
}

DETERMINISTIC = re.compile(
    r"^(total_units|affected_units|affected_fraction|n_rooms|n_equations|n_changes|batch_size|n_batches|"
    r"projected_speedup_ceiling|break_even_batch_size|repeats|compile_repeats)$|identical|matches|stable|cheaper")
KEY_COLS = ["model_name", "seed", "n_rooms", "batch_size"]


def mean_ci(mean: float, sd: float, n: float) -> tuple[float, float, float]:
    """Returns (se, t, half_width) of the t-based 95% CI for a mean."""
    if not (n and n >= 2) or math.isnan(sd):
        return math.nan, math.nan, math.nan
    se = sd / math.sqrt(n)
    t = t_crit(int(n) - 1)
    return se, t, t * se


def ratio_endpoint_ci(mf, hf, mi, hi) -> tuple[float, float]:
    """[ (mf-hf)/(mi+hi), (mf+hf)/(mi-hi) ] from the two means' 95% CIs.
    Wide by construction; its guaranteed coverage under independence is
    only >= 0.95^2 = 90.25%, although in practice it is far wider than
    an exact 95% interval. Upper bound is inf if the denominator CI reaches 0."""
    if any(math.isnan(x) for x in (hf, hi)):
        return math.nan, math.nan
    lo = (mf - hf) / (mi + hi)
    hi_ = (mf + hf) / (mi - hi) if mi - hi > 0 else math.inf
    return lo, hi_


def ratio_fieller_ci(mf, sef, mi, sei, t) -> tuple[float, float]:
    """Fieller 95% interval for mu_f/mu_i, independent samples, no
    covariance. t uses df = min(n_f, n_i) - 1 (conservative). Returns
    (nan, nan) if unavailable, (-inf, inf) if the denominator mean is not
    significantly different from 0 (g >= 1)."""
    if any(math.isnan(x) for x in (sef, sei, t)):
        return math.nan, math.nan
    q = mf / mi
    g = (t * sei / mi) ** 2
    if g >= 1:
        return -math.inf, math.inf
    rad = (t / mi) * math.sqrt(sef ** 2 * (1 - g) + q ** 2 * sei ** 2)
    return (q - rad) / (1 - g), (q + rad) / (1 - g)


def _parse_list(v):
    if isinstance(v, str) and v.strip().startswith("["):
        return [float(x) for x in ast.literal_eval(v)]
    if hasattr(v, "__len__") and not isinstance(v, str):
        return [float(x) for x in v]
    return None


def load(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix == ".txt":  # src/measure_c.py stdout (Stage-0 static-link rerun)
        rows, cur = [], None
        for line in path.read_text(encoding="utf-8").splitlines():
            if re.match(r"^\w+:$", line):
                cur = {"model_name": line[:-1]}
                rows.append(cur)
            m = re.search(r"(full_rebuild|incremental):\s+mean=([\d.]+)ms stdev=([\d.]+)ms", line)
            if m and cur is not None:
                cur[f"{m[1]}_mean_s"] = float(m[2]) / 1000
                cur[f"{m[1]}_stdev_s"] = float(m[3]) / 1000
            m = re.search(r"outputs_identical=(\w+)", line)
            if m and cur is not None:
                cur["outputs_identical"] = m[1] == "True"
        return pd.DataFrame(rows)
    raise ValueError(f"unsupported file type: {path}")


def _row_n(row, df_cols, base, fallback):
    for c in (f"{base}_repeats", "compile_repeats" if base == "compile_time" else None, "repeats"):
        if c and c in df_cols and pd.notna(row[c]):
            return float(row[c]), f"column {c}"
    for c in (f"{base}_times_s", f"{base}_all_s"):
        if c in df_cols and _parse_list(row[c]) is not None:
            return float(len(_parse_list(row[c]))), f"len({c})"
    if fallback is not None:
        return float(fallback), "script constant / --repeats"
    return math.nan, "unknown"


def audit_frame(df: pd.DataFrame, source: str, fallback_n) -> list[dict]:
    cols = list(df.columns)
    out = []
    means = [c[: -len("_mean_s")] for c in cols if c.endswith("_mean_s")]
    lists = [c for c in cols if c.endswith(("_times_s", "_all_s"))]
    list_bases = {re.sub(r"_(times|all)_s$", "", c) for c in lists}
    covered = set()
    for base in means:
        covered |= {f"{base}_mean_s", f"{base}_stdev_s", f"{base}_min_s", f"{base}_max_s"}
    for c in lists:
        covered.add(c)

    for _, row in df.iterrows():
        key = ";".join(f"{k}={row[k]}" for k in KEY_COLS if k in cols)
        stats = {}
        for base in sorted(set(means) | list_bases):
            raw = None
            for c in (f"{base}_times_s", f"{base}_all_s"):
                if c in cols:
                    raw = _parse_list(row[c])
            if raw:
                n, n_src = float(len(raw)), "raw values"
                mean = statistics.mean(raw)
                sd = statistics.stdev(raw) if len(raw) > 1 else math.nan
                mn, mx = min(raw), max(raw)
            else:
                n, n_src = _row_n(row, cols, base, fallback_n)
                mean = float(row[f"{base}_mean_s"])
                sd = float(row[f"{base}_stdev_s"]) if f"{base}_stdev_s" in cols else math.nan
                mn = float(row[f"{base}_min_s"]) if f"{base}_min_s" in cols else math.nan
                mx = float(row[f"{base}_max_s"]) if f"{base}_max_s" in cols else math.nan
            if n == 1:
                sd = math.nan  # a stored stdev of 0.0 at n=1 is a placeholder, not a measurement
            se, t, h = mean_ci(mean, sd, n)
            cv = sd / mean if mean else math.nan
            flags = []
            if not n >= 2:
                flags.append("NO_VARIANCE_ESTIMATE" if n == 1 else "N_UNKNOWN")
            if n == 3:
                flags.append("N3_WIDE_CI")
            if cv > 0.10:
                flags.append("CV_GT_10PCT")
            stats[base] = dict(mean=mean, sd=sd, n=n, se=se, t=t, h=h)
            out.append(dict(
                source_file=source, row_key=key, metric=base, kind="noisy_timing", n=n, n_source=n_src,
                mean_s=mean, sd_s=sd, cv=cv, se_s=se, t_crit=t, ci95_low_s=mean - h, ci95_high_s=mean + h,
                ci95_halfwidth_pct_of_mean=h / mean * 100 if mean else math.nan, min_s=mn, max_s=mx,
                raw_values=str(raw) if raw else "", flags=";".join(flags),
            ))

        # single-sample timings (no mean/stdev pair): n=1 by construction
        for c in cols:
            if c in covered or DETERMINISTIC.search(c) or not c.endswith("_s"):
                continue
            if re.search(r"_(low|high)$|_s_(mean|low|high)$", c) or c.startswith("batched_"):
                continue
            v = row[c]
            if not isinstance(v, (int, float)) or pd.isna(v):
                continue
            pair = re.match(r"^(full_rebuild|incremental)_s$", c)
            if pair:
                stats[pair[1]] = dict(mean=float(v), sd=math.nan, n=1.0, se=math.nan, t=math.nan, h=math.nan)
            out.append(dict(source_file=source, row_key=key, metric=c, kind="noisy_timing_single_sample",
                            n=1, n_source="single measurement", mean_s=float(v),
                            flags="NO_VARIANCE_ESTIMATE"))

        # derived columns and deterministic columns, value only
        for c in cols:
            if c in covered or not (DETERMINISTIC.search(c) or c.startswith("batched_") or "_over_" in c
                                    or c == "measured_speedup"):
                continue
            v = row[c]
            kind = "deterministic" if DETERMINISTIC.search(c) and not c.startswith("batched_") else "derived"
            out.append(dict(source_file=source, row_key=key, metric=c, kind=kind, value=v))

        if "full_rebuild" in stats and "incremental" in stats:
            f, i = stats["full_rebuild"], stats["incremental"]
            q = f["mean"] / i["mean"]
            elo, ehi = ratio_endpoint_ci(f["mean"], f["h"], i["mean"], i["h"])
            nmin = min(f["n"], i["n"])
            t = t_crit(int(nmin) - 1) if nmin >= 2 else math.nan
            flo, fhi = ratio_fieller_ci(f["mean"], f["se"], i["mean"], i["se"], t)
            out.append(dict(
                source_file=source, row_key=key, metric="speedup_full_over_incremental", kind="derived_ratio",
                n=nmin, value=q, ratio_endpoint_ci95_low=elo, ratio_endpoint_ci95_high=ehi,
                ratio_fieller_ci95_low=flo, ratio_fieller_ci95_high=fhi,
                flags="" if nmin >= 2 else "NO_VARIANCE_ESTIMATE",
            ))
    return out


def audit(paths: list[Path], repeats: dict[str, int]) -> pd.DataFrame:
    rows = []
    for p in paths:
        fallback = repeats.get(p.name, repeats.get(p.stem, KNOWN_REPEATS.get(p.stem)))
        rows += audit_frame(load(p), p.name, fallback)
    df = pd.DataFrame(rows)
    # break-even repeats its summary timings on every batch-size row; keep one copy of each timing
    df["_dedupe"] = df.apply(lambda r: (r.source_file, r.metric, str(r.mean_s) if r.kind.startswith("noisy")
                                        else r.row_key), axis=1)
    return df.drop_duplicates("_dedupe").drop(columns="_dedupe").reset_index(drop=True)


def _selftest() -> None:
    assert T975[2] == 4.303 and T975[4] == 2.776
    se, t, h = mean_ci(10.0, 1.0, 3)
    assert abs(h - 4.303 / math.sqrt(3)) < 1e-12
    # Fieller collapses to q +/- t*se_f/mi when the denominator is exact (se_i = 0)
    lo, hi = ratio_fieller_ci(10.0, 1.0, 2.0, 0.0, 2.0)
    assert abs(lo - 4.0) < 1e-12 and abs(hi - 6.0) < 1e-12
    # the endpoint interval contains the point estimate and the Fieller interval here
    elo, ehi = ratio_endpoint_ci(10.0, 2.0, 2.0, 0.2)
    flo, fhi = ratio_fieller_ci(10.0, 1.0, 2.0, 0.1, 2.0)
    assert elo < flo < 5.0 < fhi < ehi
    df = audit_frame(pd.DataFrame({"model_name": ["m"], "full_rebuild_times_s": [[3.0, 4.0, 5.0]],
                                   "incremental_times_s": [[1.0, 1.0, 1.0]]}), "x", None)
    fr = next(r for r in df if r["metric"] == "full_rebuild")
    assert fr["n"] == 3 and fr["mean_s"] == 4.0 and fr["sd_s"] == 1.0 and fr["min_s"] == 3.0
    print("selftest OK")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--repeats", action="append", default=[], metavar="FILE=N",
                    help="repeat count for a file that does not store one")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.paths:
        ap.error("give at least one results file")
    reps = {k: int(v) for k, v in (s.split("=", 1) for s in a.repeats)}
    df = audit(a.paths, reps)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(a.out, index=False)
        print(f"wrote {len(df)} rows to {a.out}")
    else:
        pd.set_option("display.width", 250)
        print(df.to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:])
