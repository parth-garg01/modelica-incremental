"""Feature 15 (Stage B): a change-frequency harness. Applies a SEQUENCE
of real, cumulative structural changes to one model (each edit built on
top of the previous one's already-edited source, the way a real codebase
accumulates edits over time) and drives that same sequence through two
real, independently timed strategies:

  STREAMING INCREMENTAL: after every single change, immediately
  recompile only the affected unit(s) and relink -- src/c_build.py's
  incremental_rebuild(), chained so each step's cache is the PREVIOUS
  step's own incremental build output, never a fresh full rebuild.

  BATCHED FULL: accumulate changes without rebuilding, then do ONE full
  rebuild (src/c_build.py's full_rebuild()) reflecting all changes in
  the batch so far, once every `batch_size` changes.

Every number here is a real gcc/ld wall-clock measurement -- there is no
step where a cost is assumed rather than timed for the batch size(s)
actually run. Feature 16 (src/break_even.py) extends this to a sweep
over batch sizes and finds the crossing point, reusing the SAME
streaming measurement (it does not depend on batch size) and combining
it with directly-measured, repeated full-rebuild timings.
"""
from __future__ import annotations

import time
from pathlib import Path

from c_build import full_rebuild, incremental_rebuild, write_sources
from compile import compile_model
from matched_graph import build_matched_graph
from measure_msl import _affected_c_filenames, _as_build_sources
from model_layout import build_layout
from resolver import resolve_impact
from scaled_models import generate_thermal_chain, swap_room_conductance

BUILD_ROOT = Path("build_cache_freq")
MODELS_ROOT = Path("models") / "scaled"


def _build_chain(model_name: str, n_rooms: int, changed_rooms: list[int]) -> tuple[list[Path], list[str]]:
    """K+1 real .mo files: step 0 is the unmodified generator output; step
    i (i>=1) is step i-1's file with room `changed_rooms[i-1]`'s heat-loss
    coefficient doubled -- a genuine cumulative edit sequence, each step
    building on the actual previous step's source text, not independent
    edits to the same original."""
    chain_dir = MODELS_ROOT / f"{model_name}_chain"
    paths = [generate_thermal_chain(n_rooms, chain_dir / "step_00" / f"{model_name}.mo")]
    seeds = []
    for i, room in enumerate(changed_rooms, start=1):
        prev = paths[-1]
        nxt = swap_room_conductance(prev, room, chain_dir / f"step_{i:02d}" / f"{model_name}.mo")
        paths.append(nxt)
        seeds.append(f"Q{room}env")
    return paths, seeds


def run_change_sequence(n_rooms: int, changed_rooms: list[int]) -> dict:
    model_name = f"ThermalChain{n_rooms}"
    paths, seeds = _build_chain(model_name, n_rooms, changed_rooms)
    irs = [compile_model(str(p), model_name).ir for p in paths]
    layout = build_layout(*irs)
    sources = [_as_build_sources(model_name, ir, layout) for ir in irs]

    base_dir = BUILD_ROOT / model_name
    for i, src in enumerate(sources):
        write_sources(src, base_dir / f"step_{i:02d}" / "src")

    # Step 0: seed the cache. Shared "cold start" cost, identical for
    # both strategies (both begin from the same initial state) -- not
    # counted in either total, only in the returned record for context.
    cache = full_rebuild(sources[0], base_dir / "step_00" / "src", base_dir / "step_00" / "build")

    steps = []
    prev_objects = cache.object_paths
    for i in range(1, len(sources)):
        impact = resolve_impact(irs[i], [seeds[i - 1]], graph_builder=build_matched_graph)
        affected = _affected_c_filenames(model_name, irs[i], impact)
        t0 = time.perf_counter()
        result = incremental_rebuild(
            sources[i], base_dir / f"step_{i:02d}" / "src", base_dir / f"step_{i:02d}" / "build",
            affected, prev_objects,
        )
        elapsed = time.perf_counter() - t0
        steps.append({
            "step": i,
            "changed_room": changed_rooms[i - 1],
            "seed": seeds[i - 1],
            "affected_units": len(affected),
            "total_units": impact["total_units"],
            "incremental_s": elapsed,
        })
        prev_objects = result.object_paths

    return {
        "model_name": model_name,
        "n_rooms": n_rooms,
        "n_changes": len(changed_rooms),
        "steps": steps,
        "total_streaming_incremental_s": sum(s["incremental_s"] for s in steps),
        "sources": sources,  # kept for run_batched_full to reuse without recompiling models
        "base_dir": base_dir,
    }


def run_batched_full(seq: dict, batch_size: int) -> dict:
    """Real full rebuilds at the end of every `batch_size`-change batch,
    reusing the already-compiled BuildSources from run_change_sequence
    (no re-parsing) but timing gcc/ld freshly for each batch boundary."""
    sources = seq["sources"]
    base_dir = seq["base_dir"]
    n_changes = seq["n_changes"]

    batch_ends = list(range(batch_size, n_changes + 1, batch_size))
    if not batch_ends or batch_ends[-1] != n_changes:
        batch_ends.append(n_changes)

    batches = []
    for end in batch_ends:
        t0 = time.perf_counter()
        full_rebuild(sources[end], base_dir / f"step_{end:02d}" / "src", base_dir / f"batched_b{batch_size}_end{end:02d}" / "build")
        elapsed = time.perf_counter() - t0
        batches.append({"batch_end_step": end, "full_rebuild_s": elapsed})

    return {
        "batch_size": batch_size,
        "batches": batches,
        "total_batched_full_s": sum(b["full_rebuild_s"] for b in batches),
    }


if __name__ == "__main__":
    n_rooms = 300
    changed_rooms = [30, 60, 90, 120, 150, 180, 210, 240, 270, 295]  # 10 evenly-spaced changes

    seq = run_change_sequence(n_rooms, changed_rooms)
    print(f"model={seq['model_name']} n_changes={seq['n_changes']}")
    for s in seq["steps"]:
        print(f"  step {s['step']}: changed room {s['changed_room']} "
              f"affected={s['affected_units']}/{s['total_units']} units, "
              f"incremental={s['incremental_s']:.3f}s")
    print(f"total_streaming_incremental_s={seq['total_streaming_incremental_s']:.3f}s")

    batched = run_batched_full(seq, batch_size=5)
    for b in batched["batches"]:
        print(f"  batch ending at step {b['batch_end_step']}: full_rebuild={b['full_rebuild_s']:.3f}s")
    print(f"total_batched_full_s (batch_size=5)={batched['total_batched_full_s']:.3f}s")
