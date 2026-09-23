"""Phase 1 discriminating experiment: is the N=5,000 incremental-rebuild anomaly
a first-read-of-freshly-written-executables cost (on-access antivirus scan),
a scan backlog that drains with time, or something in the build itself?

Reuses the N=5,000 cache left on disk by src/journal_profile_scale.py
(build_cache_profile/ThermalChain5000/cache, 14,999 DLLs) and the unmodified
c_build.incremental_rebuild_dynamic(). Pre-registered conditions:

  W  : warm cache (already read before), 5 consecutive incremental rebuilds
  F  : fresh copy of the cache (brand-new files), rebuild immediately; 3 reps
  FW : fresh copy, idle 10 minutes, then rebuild; 2 reps

During every timed rebuild, Defender's CPU use is sampled once per second
(typeperf on the MsMpEng % Processor Time counter), for direct attribution.
Correctness: every rebuild's simulation output must equal the reference
incremental build from the profiler run (itself one incremental build of the
same change; bit-identity of incremental vs full at this size was verified by
the original validate_scale run), and reused DLL bytes must equal the cache.
Output: results/journal_upgrade_phase1_firsttouch.csv (new file).
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from c_build import BuildSources, incremental_rebuild_dynamic, run_sim
from compile import compile_model
from matched_graph import build_matched_graph
from measure_msl import _affected_c_filenames
from resolver import resolve_impact

N = 5000
MODEL = f"ThermalChain{N}"
CELL = Path("build_cache_profile") / MODEL
OUT = Path("results") / "journal_upgrade_phase1_firsttouch.csv"
WAIT_S = 600


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class DefenderSampler:
    def __enter__(self):
        self.proc = subprocess.Popen(
            ["typeperf", r"\Process(MsMpEng)\% Processor Time", "-si", "1"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        return self

    def __exit__(self, *exc):
        self.proc.terminate()
        out, _ = self.proc.communicate(timeout=10)
        vals = []
        for row in csv.reader(out.splitlines()):
            if len(row) == 2:
                try:
                    vals.append(float(row[1]))
                except ValueError:
                    pass
        self.samples = vals
        return False


def main():
    src_dir = CELL / "changed_src"
    cache = CELL / "cache"
    unit_c = sorted(p.name for p in src_dir.glob(f"{MODEL}_unit_*.c"))
    sources = BuildSources(MODEL, None, {c: None for c in unit_c}, (f"{MODEL}_driver.c", None), (f"{MODEL}.h", None))

    changed = compile_model(str(Path("models/scaled_profile") / f"ThermalChainProfile{N}_chg" / f"{MODEL}.mo"), MODEL)
    impact = resolve_impact(changed.ir, [f"Q{N // 2}env"], graph_builder=build_matched_graph)
    affected = _affected_c_filenames(MODEL, changed.ir, impact)
    reference_out = run_sim(CELL / "incr_e2e" / f"{MODEL}_incremental.exe", 2.0, 1.0)
    cache_sha = {c: _sha(cache / (Path(c).stem + ".dll")) for c in unit_c if c not in affected}

    rows = []

    def rebuild(condition, rep, cache_dir, extra):
        build_dir = CELL / f"ft_{condition}_{rep}"
        cached = {c: cache_dir / (Path(c).stem + ".dll") for c in unit_c}
        with DefenderSampler() as s:
            t0 = time.perf_counter()
            res = incremental_rebuild_dynamic(sources, src_dir, build_dir, affected, cached)
            dt = time.perf_counter() - t0
        identical = run_sim(res.exe_path, 2.0, 1.0) == reference_out
        reuse_ok = all(_sha(res.object_paths[c]) == cache_sha[c] for c in cache_sha)
        row = {"condition": condition, "rep": rep, "incremental_s": dt,
               "defender_cpu_mean_pct": sum(s.samples) / len(s.samples) if s.samples else float("nan"),
               "defender_cpu_samples": json.dumps(s.samples), "outputs_identical_to_reference": identical,
               "reused_dlls_identical_to_cache": reuse_ok, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), **extra}
        print({k: v for k, v in row.items() if k != "defender_cpu_samples"}, flush=True)
        rows.append(row)
        shutil.rmtree(build_dir, ignore_errors=True)
        _write(rows)

    for rep in range(5):
        rebuild("W", rep, cache, {"fresh_copy_s": "", "wait_s": 0})

    for cond, reps, wait in (("F", 3, 0), ("FW", 2, WAIT_S)):
        for rep in range(reps):
            fresh = CELL / f"cache_fresh_{cond}_{rep}"
            shutil.rmtree(fresh, ignore_errors=True)
            t0 = time.perf_counter()
            shutil.copytree(cache, fresh)
            copy_s = time.perf_counter() - t0
            if wait:
                time.sleep(wait)
            rebuild(cond, rep, fresh, {"fresh_copy_s": copy_s, "wait_s": wait})
            shutil.rmtree(fresh, ignore_errors=True)


def _write(rows):
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
    print(f"wrote {OUT}")
