"""Feature 9: figures for Stage A's real-model results (measured, not
projected -- results/measurements_msl.parquet), from src/measure_msl.py
(Feature 8). Same deterministic-SVG conventions as src/figures.py.
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


def load() -> pd.DataFrame:
    df = pd.read_parquet(RESULTS / "measurements_msl.parquet")
    return df.reset_index(drop=True)


def _labels(df: pd.DataFrame) -> list[str]:
    return [f"{m}\n({s})" for m, s in zip(df["model_name"], df["seed"])]


def fig_measured_speedup(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = _labels(df)
    ax.bar(labels, df["measured_speedup"], color="#55A868")
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1)
    ax.set_ylabel("Measured speedup (full rebuild time / incremental time)")
    ax.set_xlabel("Model (seed equations)")
    ax.set_title("Measured incremental-vs-full-rebuild speedup\n(real gcc builds, real models, not a projection)")
    for i, v in enumerate(df["measured_speedup"]):
        ax.text(i, v + 0.1, f"{v:.2f}x", ha="center")
    fig.tight_layout()
    out = FIGURES / "measured_speedup.svg"
    fig.savefig(out, **SAVE_KWARGS)
    plt.close(fig)
    return out


def fig_real_model_ripple(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = _labels(df)
    ax.bar(labels, df["affected_fraction"] * 100, color="#4C72B0")
    ax.set_ylabel("Affected recompilation units (%)")
    ax.set_xlabel("Model (seed equations)")
    ax.set_title("Ripple on real MSL-component models")
    ax.set_ylim(0, 100)
    for i, v in enumerate(df["affected_fraction"] * 100):
        ax.text(i, v + 2, f"{v:.1f}%", ha="center")
    fig.tight_layout()
    out = FIGURES / "real_model_ripple.svg"
    fig.savefig(out, **SAVE_KWARGS)
    plt.close(fig)
    return out


def fig_time_breakdown(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = _labels(df)
    x = range(len(df))
    width = 0.35
    ax.bar([i - width / 2 for i in x], df["full_rebuild_mean_s"] * 1000, width,
           yerr=df["full_rebuild_stdev_s"] * 1000, label="Full rebuild", color="#C44E52")
    ax.bar([i + width / 2 for i in x], df["incremental_mean_s"] * 1000, width,
           yerr=df["incremental_stdev_s"] * 1000, label="Incremental", color="#55A868")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Wall-clock time (ms)")
    ax.set_title("Full vs. incremental compile+link time\n(real MSL-component models, 5 repeats, error bars = stdev)")
    ax.legend()
    fig.tight_layout()
    out = FIGURES / "time_breakdown_real.svg"
    fig.savefig(out, **SAVE_KWARGS)
    plt.close(fig)
    return out


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    df = load()
    for fn in (fig_measured_speedup, fig_real_model_ripple, fig_time_breakdown):
        print(f"wrote {fn(df)}")


if __name__ == "__main__":
    main()
