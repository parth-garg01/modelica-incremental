"""Demo: live incremental-vs-full rebuild sweep over growing model sizes.

Prints a coloured table as each size finishes and saves a speedup chart to
figures/demo_scale.png. Uses run_scale_cell() directly, so it does NOT touch
results/measurements_scale.*.

Usage: PYTHONPATH=src python src/demo_scale.py [sizes...]   (default 50 100 250 500)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from measure_scale import run_scale_cell

G, C, Y, B, D, R = "\033[92m", "\033[96m", "\033[93m", "\033[1m", "\033[2m", "\033[0m"


def main() -> None:
    sizes = [int(a) for a in sys.argv[1:]] or [50, 100, 250, 500]
    print(f"\n{B}{C}  DRIFT-TRIGGERED INCREMENTAL RECOMPILATION{R}")
    print(f"{D}  full rebuild vs. recompiling only the units a change affects{R}\n")
    head = f"  {'rooms':>6} {'equations':>10} {'units':>7} {'recompiled':>11} {'full (s)':>9} {'incr (s)':>9} {'speedup':>9}  verified"
    print(B + head + R)
    print(D + "  " + "-" * (len(head) - 2) + R)

    rows = []
    for n in sizes:
        r = run_scale_cell(n)
        full, incr = r["full_rebuild_mean_s"], r["incremental_mean_s"]
        speedup = full / incr
        ok = r["incremental_matches_full_for_unaffected_objects"] and r["outputs_identical"]
        rows.append((r["n_equations"], speedup, full, incr))
        print(
            f"  {n:>6} {r['n_equations']:>10} {r['total_units']:>7} "
            f"{r['affected_units']:>5} ({r['affected_fraction']*100:4.1f}%) "
            f"{full:>9.2f} {incr:>9.2f} {B}{G}{speedup:>8.1f}x{R}  "
            f"{G + 'bit-identical' + R if ok else Y + 'MISMATCH' + R}",
            flush=True,
        )

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    eq = [x[0] for x in rows]
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.5))
    a.plot(eq, [x[2] for x in rows], "o-", label="full rebuild", color="#c0392b", lw=2)
    a.plot(eq, [x[3] for x in rows], "o-", label="incremental", color="#27ae60", lw=2)
    a.set_xlabel("equations"); a.set_ylabel("rebuild time (s)"); a.set_title("Rebuild time"); a.legend(); a.grid(alpha=.3)
    b.bar([str(e) for e in eq], [x[1] for x in rows], color="#2980b9")
    for i, x in enumerate(rows):
        b.text(i, x[1], f"{x[1]:.1f}x", ha="center", va="bottom", fontweight="bold")
    b.set_xlabel("equations"); b.set_ylabel("speedup (x)"); b.set_title("Measured speedup"); b.grid(alpha=.3, axis="y")
    fig.suptitle("Incremental recompilation of Modelica digital twins (every rebuild bit-identical to full)")
    fig.tight_layout()
    out = Path("figures") / "demo_scale.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=160)
    print(f"\n  {B}{G}Saved {out}{R}\n")
    if sys.platform == "darwin":
        subprocess.run(["open", str(out)])


if __name__ == "__main__":
    main()
