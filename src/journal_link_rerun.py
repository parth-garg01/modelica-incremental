"""Reruns single link-ablation cells that the suspend check flagged, with the identical
protocol (journal_link_ablation.run_config). Appends rows marked rerun=True with the
reason; the original contaminated rows stay in the CSV unchanged. Rerun policy fixed
before any rerun data existed: each flagged cell is rerun exactly once.

Usage: python -u src/journal_link_rerun.py 100:dynamic_stripped 500:dynamic_unstripped
"""
from __future__ import annotations

import sys
import time

from compile import compile_model
from journal_link_ablation import BUILD_ROOT, MODELS_ROOT, OUT_CSV, append_row, run_config
from journal_parallel_timing import wait_until_idle
from model_layout import build_layout
from scaled_models import generate_thermal_chain, swap_room_conductance

REASON = "rerun: original cell overlapped a Windows suspend event (src/journal_suspend_check.py)"

for spec in sys.argv[1:]:
    n_str, config = spec.split(":")
    n = int(n_str)
    name, mid = f"ThermalChain{n}", n // 2
    base = generate_thermal_chain(n, MODELS_ROOT / f"N{n}_base" / f"{name}.mo")
    chg = swap_room_conductance(base, mid, MODELS_ROOT / f"N{n}_chg" / f"{name}.mo")
    b_ir, c_ir = compile_model(str(base), name).ir, compile_model(str(chg), name).ir
    wait_until_idle()
    t0 = time.time()
    print(f"[rerun N={n}] {config} start {time.strftime('%H:%M:%S')}", flush=True)
    rec = run_config(config, BUILD_ROOT / f"N{n}_rerun" / config, b_ir, c_ir, build_layout(b_ir, c_ir),
                     [f"Q{mid}env"], name)
    rec.update(n_rooms=n, n_equations=3 * n - 1, run_order_index=-1, wall_clock_s=time.time() - t0,
               rerun=True, rerun_reason=REASON)
    print(f"  speedup disc={rec['speedup_disc']:.2f}x [{rec['speedup_disc_fieller_low']:.2f},"
          f"{rec['speedup_disc_fieller_high']:.2f}] full={rec['full_disc_mean_s']:.1f}s "
          f"incr={rec['incr_disc_mean_s']:.2f}s identical={rec['outputs_identical']} "
          f"reuse_ok={rec['reused_byte_identical']}", flush=True)
    append_row(rec, OUT_CSV)
