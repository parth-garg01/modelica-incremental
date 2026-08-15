"""Generate the paper figures and a short results summary from logged
data only -- no hand-editing, no values not present in results/measurements.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")
# Fixed hash salt makes SVG element ids deterministic across runs; savefig's
# metadata={"Date": None} below strips the embedded render timestamp. Both
# are needed for "regenerating from the same logs produces identical
# figures" to hold at the byte level, not just visually.
matplotlib.rcParams["svg.hashsalt"] = "recompilation-unit-feasibility-study"

RESULTS = Path("results")
FIGURES = Path("figures")
SAVE_KWARGS = {"metadata": {"Date": None}}


def load() -> pd.DataFrame:
    df = pd.read_parquet(RESULTS / "measurements.parquet")
    return df.sort_values("model_name").reset_index(drop=True)


def fig_ripple_distribution(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = [f"{m}\n({c})" for m, c in zip(df["model_name"], df["change_type"])]
    ax.bar(labels, df["affected_fraction"] * 100, color="#4C72B0")
    ax.set_ylabel("Affected recompilation units (%)")
    ax.set_xlabel("Model (change type)")
    ax.set_title("Ripple: fraction of recompilation units affected per change")
    ax.set_ylim(0, 100)
    for i, v in enumerate(df["affected_fraction"] * 100):
        ax.text(i, v + 2, f"{v:.0f}%", ha="center")
    fig.tight_layout()
    out = FIGURES / "ripple_distribution.svg"
    fig.savefig(out, **SAVE_KWARGS)
    plt.close(fig)
    return out


def fig_speedup_ceiling(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = [f"{m}\n({c})" for m, c in zip(df["model_name"], df["change_type"])]
    ax.bar(labels, df["projected_speedup_ceiling"], color="#DD8452")
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1)
    ax.set_ylabel("Projected speedup ceiling (1 / affected fraction)")
    ax.set_xlabel("Model (change type)")
    ax.set_title("Projected upper-bound speedup\n(projection only -- ignores relink/re-matching overhead)")
    for i, v in enumerate(df["projected_speedup_ceiling"]):
        ax.text(i, v + 0.03, f"{v:.2f}x", ha="center")
    fig.tight_layout()
    out = FIGURES / "speedup_ceiling.svg"
    fig.savefig(out, **SAVE_KWARGS)
    plt.close(fig)
    return out


def fig_unit_size_distribution(df: pd.DataFrame) -> Path:
    """Equations-per-unit histogram, read from each cell's changed model's
    own unit partition (recomputed here from the fixture + resolver code,
    since unit-size membership isn't itself logged per-unit in the parquet)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from compile import compile_model
    from graph import build_dependency_graph
    from units import compute_units

    sizes = []
    seen = set()
    for _, row in df.iterrows():
        path = row["changed_path"]
        if path in seen:
            continue
        seen.add(path)
        result = compile_model(path, row["model_name"])
        g = build_dependency_graph(result.ir)
        units = compute_units(g)
        sizes.extend(len(members) for members in units.values())

    fig, ax = plt.subplots(figsize=(6, 4))
    max_size = max(sizes)
    ax.hist(sizes, bins=range(1, max_size + 2), align="left", rwidth=0.8, color="#55A868")
    ax.set_xlabel("Equations per recompilation unit")
    ax.set_ylabel("Number of units")
    ax.set_title("Recompilation-unit-size distribution\n(across both changed-model fixtures)")
    ax.set_xticks(range(1, max_size + 1))
    fig.tight_layout()
    out = FIGURES / "unit_size_distribution.svg"
    fig.savefig(out, **SAVE_KWARGS)
    plt.close(fig)
    return out


def write_summary(df: pd.DataFrame) -> Path:
    lines = ["# Results summary (generated from results/measurements.parquet)\n"]
    for _, row in df.iterrows():
        lines.append(
            f"- **{row['model_name']}** ({row['change_type']}, seed={row['seed_equations']}): "
            f"{row['affected_units']}/{row['total_units']} units affected "
            f"({row['affected_fraction']*100:.0f}% ripple), "
            f"projected speedup ceiling **{row['projected_speedup_ceiling']:.2f}x**, "
            f"compile time {row['compile_time_mean_s']*1000:.2f} ms "
            f"(± {row['compile_time_stdev_s']*1000:.2f} ms, {row['compile_repeats']} repeats)."
        )
    lines.append(
        "\nThe speedup ceiling is a **projection** (1 / affected_fraction), an optimistic "
        "upper bound that ignores relink and re-matching overhead -- not a measured "
        "incremental compile time. No incremental compiler was built this week; see "
        "prd.md Section 2 and Section 12 for the full limitations."
    )
    out = RESULTS / "summary.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    df = load()

    paths = [
        fig_ripple_distribution(df),
        fig_speedup_ceiling(df),
        fig_unit_size_distribution(df),
    ]
    summary_path = write_summary(df)

    for p in paths:
        print(f"wrote {p}")
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
