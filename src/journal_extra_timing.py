"""Timing cells that extend Phase 2's three-strategy comparison (paper reachability,
matching-free baseline, generated-source diff) to the topologies found informative at
graph level. Reuses journal_baseline_compare.run_cell_strategies unchanged (same compile,
cache build, warm-up + 5 repeats, fingerprint and bit-identical checks, oracle guard),
with its own build root. Strategy order rotates per cell. Timed cells wait for AC power.

  SignalChain500, stage-gain edit at k=1, 250, 500 : scope varies 500 / 251 / 1 (paper), 500 (baseline), 1 (diff)
  BridgedStar250, bridge edit at branch 125        : coupled 5-equation blocks at scale
  RcLadder1000, segment-resistance edit at 500     : confirms sin(time) codegen builds bit-identically

Output: results/journal_upgrade/extra_timing/extra_timing.csv (rewritten after every cell).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import journal_baseline_compare as jbc
from journal_generators import generate_bridged_star, swap_branch_bridge
from journal_locality import generate_signal_chain, swap_signal_gain
from journal_parallel_timing import machine_state, wait_until_idle
from journal_rc_changes import swap_segment_resistance
from scaled_models import generate_rc_ladder

sys.setrecursionlimit(20000)  # Kuhn's augmenting-path DFS recurses along the signal chain
jbc.BUILD_ROOT = Path("build_cache_journal_extra")
MODELS = Path("models/journal_extra_timing")
OUT = Path("results/journal_upgrade/extra_timing/extra_timing.csv")
STRATEGIES = ["matching", "naive", "oracle"]


def cells() -> list[dict]:
    out = []
    sig = generate_signal_chain(500, MODELS / "sig_base" / "SignalChain500.mo")
    for k in (1, 250, 500):
        chg = swap_signal_gain(sig, k, MODELS / f"sig_{k}" / "SignalChain500.mo")
        out.append(dict(label=f"SignalChain500/stage{k}", baseline_path=str(sig), changed_path=str(chg),
                        model_name="SignalChain500", seed=[f"y{k}"], t_end=2.0, dt=1.0))
    star = generate_bridged_star(250, MODELS / "star_base" / "BridgedStar250.mo")
    chg = swap_branch_bridge(star, 125, MODELS / "star_125" / "BridgedStar250.mo")
    out.append(dict(label="BridgedStar250/branch125", baseline_path=str(star), changed_path=str(chg),
                    model_name="BridgedStar250", seed=["J125"], t_end=2.0, dt=1.0))
    rc = generate_rc_ladder(1000, MODELS / "rc_base" / "RcLadder1000.mo")
    chg = swap_segment_resistance(rc, 500, MODELS / "rc_500" / "RcLadder1000.mo")
    out.append(dict(label="RcLadder1000/segment500", baseline_path=str(rc), changed_path=str(chg),
                    model_name="RcLadder1000", seed=["I500"], t_end=3.0, dt=0.5))
    return out


def main(only: list[str]) -> None:
    rows: list[dict] = []
    for k, c in enumerate(cells()):
        if only and not any(s in c["label"] for s in only):
            continue
        order = STRATEGIES[k % 3:] + STRATEGIES[:k % 3]
        wait_until_idle()
        state = machine_state()
        print(f"[{c['label']}] order {order} {state}", flush=True)
        new = jbc.run_cell_strategies(c["label"], c["baseline_path"], c["changed_path"], c["model_name"], c["seed"],
                                      c["t_end"], c["dt"], strategies=order)
        for r in new:
            r["machine_state"] = state
            print(f"  {r['strategy']:>8}: recompiled {r['n_units_recompiled']}/{r['total_units']} "
                  f"incr={r['incremental_mean_s']:.3f}s full={r['full_rebuild_mean_s']:.3f}s "
                  f"speedup={r['measured_speedup']:.2f} identical={r['outputs_identical']}", flush=True)
        rows += new
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
