"""Feature 17: figures for Stage B's scaling and break-even results,
regenerated deterministically from results/measurements_scale.parquet
(Feature 13), results/measurements_overhead.parquet (Feature 14), and
results/measurements_break_even.parquet (Feature 16). Same
deterministic-SVG conventions as src/figures.py and src/figures_msl.py.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "recompilation-unit-feasibility-study"

RESULTS = Path("results")
FIGURES = Path("figures")
SAVE_KWARGS = {"metadata": {"Date": None}}


def fig_speedup_vs_size() -> Path:
    df = pd.read_parquet(RESULTS / "measurements_scale.parquet").sort_values("n_equations")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.errorbar(
        df["n_equations"], df["measured_speedup"], fmt="o-", color="#55A868",
        label="Measured speedup",
    )
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1)
    ax.set_xlabel("Model size (equations)")
    ax.set_ylabel("Measured speedup (full rebuild / incremental)")
    ax.set_title(f"Incremental speedup vs. model size\n({int(df['repeats'].iloc[0])} repeats per point, real gcc/ld builds)")
    fig.tight_layout()
    out = FIGURES / "speedup_vs_size.svg"
    fig.savefig(out, **SAVE_KWARGS)
    plt.close(fig)
    return out


def fig_overhead_vs_size() -> Path:
    df = pd.read_parquet(RESULTS / "measurements_overhead.parquet").sort_values("n_equations")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(df["n_equations"], df["graph_and_partition_s"], "o-", color="#4C72B0", label="Graph + partition setup")
    if "full_rebuild_mean_s" in df.columns:
        ax.plot(df["n_equations"], df["full_rebuild_mean_s"], "s--", color="#C44E52", label="Full rebuild")
    ax.set_xlabel("Model size (equations)")
    ax.set_ylabel("Wall-clock time (s)")
    ax.set_title("One-time setup overhead vs. model size")
    ax.legend()
    fig.tight_layout()
    out = FIGURES / "overhead_vs_size.svg"
    fig.savefig(out, **SAVE_KWARGS)
    plt.close(fig)
    return out


def fig_break_even_crossing() -> Path:
    df = pd.read_parquet(RESULTS / "measurements_break_even.parquet").sort_values("batch_size")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(df["batch_size"], df["batched_full_total_s_mean"], "o-", color="#C44E52", label="Batched full rebuild (cumulative)")
    ax.fill_between(df["batch_size"], df["batched_full_total_s_low"], df["batched_full_total_s_high"], color="#C44E52", alpha=0.2)
    ax.axhline(df["streaming_incremental_total_s"].iloc[0], color="#55A868", linestyle="--", label="Streaming incremental (cumulative)")
    crossing = df["break_even_batch_size"].iloc[0]
    if pd.notna(crossing):
        ax.axvline(crossing, color="gray", linestyle=":", label=f"Break-even (batch size = {int(crossing)})")
    ax.set_xlabel("Batch size (changes accumulated per rebuild)")
    ax.set_ylabel("Cumulative wall-clock time (s)")
    ax.set_title(f"Streaming incremental vs. batched full rebuild\n(N={int(df['n_rooms'].iloc[0])} rooms, {int(df['n_changes'].iloc[0])} changes)")
    ax.legend()
    fig.tight_layout()
    out = FIGURES / "break_even_crossing.svg"
    fig.savefig(out, **SAVE_KWARGS)
    plt.close(fig)
    return out


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    for fn in (fig_speedup_vs_size, fig_overhead_vs_size, fig_break_even_crossing):
        print(f"wrote {fn()}")


if __name__ == "__main__":
    main()
