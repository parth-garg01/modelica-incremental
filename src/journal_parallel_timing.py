"""Shared timing harness for the parallel journal-upgrade experiments
(link ablation, locality timing, RC ladder timing).

Implements the pre-registered policy in docs/journal_upgrade/STATUS.md:
1 first rebuild (warm-up candidate) + REPEATS timed repeats, full and
incremental interleaved (full_0, incr_0, full_1, incr_1, ...), every raw
time stored, statistics reported both with the first pair discarded and
over all pairs. No adaptive re-running, no outlier removal.

Correctness per cell, on the LAST timed full/incremental builds (no extra
reference builds):
  outputs_identical        simulation stdout of full == incremental, string-equal
  reused_byte_identical    every non-recompiled artifact equals its cache copy
  incr_equals_full_unaffected  every non-recompiled artifact equals the full build's
                           (can be False for non-deterministic toolchains, e.g. PE timestamps)
  c_diff_subset_of_affected  the unit .c files whose generated TEXT differs between
                           baseline and changed sources are a subset of the recompiled set
                           (a codegen-level oracle independent of the resolver)
"""
from __future__ import annotations

import json
import math
import statistics
import subprocess
import time
from pathlib import Path

from c_build import fingerprint_objects, run_sim
from journal_stats_audit import mean_ci, ratio_fieller_ci, t_crit

REPEATS = 5


def phase2_running() -> bool:
    """True while the main process's Phase 2 build is still running (hard rule 2)."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
          "Where-Object CommandLine -match 'journal_baseline_compare' | Measure-Object | "
          "Select-Object -ExpandProperty Count")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    return out.strip() not in ("", "0")


def on_ac_power() -> bool:
    """All earlier timing ran on AC power; a battery-powered laptop may throttle under the
    Balanced plan, so timed cells only start on AC (pre-registered, not adaptive)."""
    ps = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SystemInformation]::PowerStatus.PowerLineStatus"
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    return out.strip() == "Online"


def wait_until_idle(poll_s: int = 120) -> None:
    while phase2_running() or not on_ac_power():
        why = "Phase 2 build running" if phase2_running() else "on battery power"
        print(f"  waiting: {why} ({time.strftime('%H:%M:%S')})", flush=True)
        time.sleep(poll_s)


def machine_state() -> str:
    """Power plan, AC/battery, Defender real-time flag, and a 1 s CPU load sample."""
    ps = ("$p=(powercfg /getactivescheme) -replace '.*\\((.*)\\).*','$1';"
          "$b=(Get-CimInstance Win32_Battery | Select-Object -First 1).BatteryStatus;"
          "$d=try{(Get-MpComputerStatus).RealTimeProtectionEnabled}catch{'unknown'};"
          "$c=(Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average;"
          "\"plan=$p;battery_status=$b;defender_rt=$d;cpu_load_pct=$c\"")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    return out.strip().replace("\n", " ")


def timed_pairs(full, incr, csrc, cdir: Path, cell: Path, affected: set[str], cache, bsrc,
                t_end: float = 2.0, dt: float = 1.0, repeats: int = REPEATS) -> dict:
    """full(sources, src_dir, build_dir) / incr(sources, src_dir, build_dir, affected, cached)
    must return c_build.BuildResult. `cache` is the BuildResult of the baseline build."""
    rec = {"start": time.strftime("%Y-%m-%d %H:%M:%S"), "machine_state_start": machine_state()}
    full_raw, incr_raw, full_link, incr_link = [], [], [], []
    for i in range(repeats + 1):
        t0 = time.perf_counter()
        fr = full(csrc, cdir, cell / f"full_{i}")
        full_raw.append(time.perf_counter() - t0)
        full_link.append(fr.link_seconds)
        t0 = time.perf_counter()
        ir = incr(csrc, cdir, cell / f"incr_{i}", affected, cache.object_paths)
        incr_raw.append(time.perf_counter() - t0)
        incr_link.append(ir.link_seconds)
    rec["end"] = time.strftime("%Y-%m-%d %H:%M:%S")
    rec["machine_state_end"] = machine_state()

    cache_fp, incr_fp, full_fp = fingerprint_objects(cache), fingerprint_objects(ir), fingerprint_objects(fr)
    unaffected = [c for c in incr_fp if c not in affected]
    c_diff = {f for f, src in csrc.unit_files.items() if bsrc.unit_files.get(f) != src}
    rec.update(
        full_raw_s=json.dumps(full_raw), incr_raw_s=json.dumps(incr_raw),
        full_link_raw_s=json.dumps(full_link), incr_link_raw_s=json.dumps(incr_link),
        n_recompiled=len(affected), n_c_files_text_changed=len(c_diff),
        c_diff_subset_of_affected=c_diff <= affected,
        reused_byte_identical=all(incr_fp[c] == cache_fp[c] for c in unaffected),
        incr_equals_full_unaffected=all(incr_fp[c] == full_fp[c] for c in unaffected),
        outputs_identical=run_sim(fr.exe_path, t_end, dt) == run_sim(ir.exe_path, t_end, dt),
    )
    rec.update(summarize(full_raw, incr_raw))
    return rec


def describe(xs: list[float], prefix: str) -> dict:
    n = len(xs)
    mean = statistics.mean(xs)
    sd = statistics.stdev(xs) if n > 1 else math.nan
    se, _, h = mean_ci(mean, sd, n)
    return {f"{prefix}_n": n, f"{prefix}_mean_s": mean, f"{prefix}_median_s": statistics.median(xs),
            f"{prefix}_sd_s": sd, f"{prefix}_cv": sd / mean, f"{prefix}_ci_low_s": mean - h,
            f"{prefix}_ci_high_s": mean + h, f"{prefix}_min_s": min(xs), f"{prefix}_max_s": max(xs),
            f"{prefix}_se_s": se}


def speedup(full_xs: list[float], incr_xs: list[float]) -> tuple[float, float, float]:
    """Ratio of means and its Fieller 95% interval (independent samples, df = min(n)-1)."""
    f, i = describe(full_xs, "f"), describe(incr_xs, "i")
    t = t_crit(min(len(full_xs), len(incr_xs)) - 1)
    lo, hi = ratio_fieller_ci(f["f_mean_s"], f["f_se_s"], i["i_mean_s"], i["i_se_s"], t)
    return f["f_mean_s"] / i["i_mean_s"], lo, hi


def summarize(full_raw: list[float], incr_raw: list[float]) -> dict:
    out = {}
    for tag, sl in (("disc", slice(1, None)), ("all", slice(None))):
        out |= describe(full_raw[sl], f"full_{tag}") | describe(incr_raw[sl], f"incr_{tag}")
        q, lo, hi = speedup(full_raw[sl], incr_raw[sl])
        out |= {f"speedup_{tag}": q, f"speedup_{tag}_fieller_low": lo, f"speedup_{tag}_fieller_high": hi}
    out["first_incr_over_median_rest"] = incr_raw[0] / statistics.median(incr_raw[1:])
    out["first_full_over_median_rest"] = full_raw[0] / statistics.median(full_raw[1:])
    return out


if __name__ == "__main__":
    s = summarize([10.0, 4.0, 4.0, 4.0, 4.0, 4.0], [2.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    assert s["speedup_disc"] == 4.0 and s["full_disc_n"] == 5 and s["full_all_n"] == 6
    assert s["speedup_disc_fieller_low"] == 4.0 == s["speedup_disc_fieller_high"]  # zero variance
    assert abs(s["first_incr_over_median_rest"] - 2.0) < 1e-12
    q, lo, hi = speedup([10.0, 11.0, 9.0], [2.0, 2.2, 1.8])
    assert lo < q == 5.0 < hi
    print("selftest OK", machine_state())
