"""Phase 4 (journal-upgrade): preliminary locality figure, regenerated
deterministically from results/journal_upgrade_phase4_locality_ripple.csv.
Same deterministic-SVG/PDF conventions as src/figures_scale.py.
"""
from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

from figures_scale import FIGURES, RESULTS, _savefig

LOCALITY_CSV = RESULTS / "journal_upgrade" / "locality_parallel" / "locality_ripple.csv"

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "recompilation-unit-feasibility-study"

# Series shown: (model, N, edit_type, label). Mixed-model series stay in the CSV.
SERIES = [
    ("signal_chain", 250, "stage_gain", "Algebraic signal chain, stage gain (N=250)"),
    ("signal_chain", 1000, "stage_gain", "Algebraic signal chain, stage gain (N=1000)"),
    ("thermal_chain", 250, "exchange_conductance", "Thermal chain, exchange edit (N=250)"),
    ("thermal_chain", 250, "room_conductance", "Thermal chain, room loss edit (N=250)"),
    ("thermal_chain", 1000, "room_conductance", "Thermal chain, room loss edit (N=1000)"),
]


def fig_locality_ripple():
    df = pd.read_csv(LOCALITY_CSV)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for model, n, edit, label in SERIES:
        s = df[(df.model == model) & (df.N == n) & (df.edit_type == edit)].sort_values("position")
        ax.plot(s.position / n, s.ripple * 100, marker="." if n == 1000 else None,
                linestyle="-" if n == 250 else ":", label=label)
    ax.set_yscale("log")
    ax.set_xlabel("Relative edit position (position / N)")
    ax.set_ylabel("Ripple (% of units affected, log scale)")
    ax.set_title("Ripple vs. edit position: states cut, algebraic chains do not")
    ax.legend(fontsize=7)
    fig.tight_layout()
    out = _savefig(fig, "journal_locality_ripple")
    plt.close(fig)
    return out


if __name__ == "__main__":
    FIGURES.mkdir(parents=True, exist_ok=True)
    print(f"wrote {fig_locality_ripple()}")
