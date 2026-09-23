"""Phase 4 (journal-upgrade): change-locality sweep. Does the resolver's
ripple stay local as the SAME edit type moves through a model?

Graph-level only: every position is a real text edit + real Rumoca
recompile, then resolve_impact()/check_soundness() over the matched graph.
No gcc, no builds. Also checks, per position, that the post-change matched
graph and unit partition are identical to the baseline's (the
"coefficient edit is structurally invisible" claim).

Writes results/journal_upgrade_phase4_locality_ripple.csv (new file).
Models go under models/journal_locality/<model>/{baseline,changed}/, one
directory per variant (Rumoca rejects two same-named classes in one dir).
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

from compile import compile_model
from matched_graph import build_matched_graph
from matched_units import compute_matched_units
from resolver import resolve_impact
from scaled_models import generate_thermal_chain, swap_room_conductance
from soundness import check_soundness

# Kuhn's augmenting-path DFS recurses along the signal chain (depth ~N).
sys.setrecursionlimit(20000)

MODELS_ROOT = Path("models") / "journal_locality_parallel"
OUT_CSV = Path("results") / "journal_upgrade" / "locality_parallel" / "locality_ripple.csv"
FIELDS = ["model", "N", "edit_type", "position", "method", "total_units",
          "affected_units", "ripple", "sound", "seed", "structure_identical",
          "actually_changed_units", "compile_s"]


def _write(lines: list[str], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def generate_signal_chain(n: int, out_path: str | Path) -> Path:
    """One state x (der(x) = -x) feeding an N-stage purely algebraic,
    index-1, linear, assignment-form pipeline: y1 = a1*x, yk = ak*y{k-1}."""
    lines = [f"model SignalChain{n}"]
    lines += [f"  parameter Real a{k} = 0.999;" for k in range(1, n + 1)]
    lines.append("  Real x(start=1.0);")
    lines += [f"  Real y{k};" for k in range(1, n + 1)]
    lines.append("equation")
    lines.append("  der(x) = -x;")
    lines.append("  y1 = a1*x;")
    lines += [f"  y{k} = a{k}*y{k-1};" for k in range(2, n + 1)]
    lines.append(f"end SignalChain{n};")
    return _write(lines, Path(out_path))


def generate_thermal_sensor_chain(n_rooms: int, n_stages: int, out_path: str | Path) -> Path:
    """generate_thermal_chain's topology, plus an n_stages algebraic sensor
    pipeline per room reading that room's temperature state."""
    base = Path(out_path).with_suffix(".tmp")
    generate_thermal_chain(n_rooms, base)
    text = base.read_text(encoding="utf-8")
    base.unlink()
    old_name, new_name = f"ThermalChain{n_rooms}", f"ThermalSensorChain{n_rooms}"
    decls = ["  parameter Real ks = 0.9;"] + [
        f"  Real S{i}_{j};" for i in range(1, n_rooms + 1) for j in range(1, n_stages + 1)]
    eqs = []
    for i in range(1, n_rooms + 1):
        eqs.append(f"  S{i}_1 = ks*T{i};")
        eqs += [f"  S{i}_{j} = ks*S{i}_{j-1};" for j in range(2, n_stages + 1)]
    text = text.replace(old_name, new_name)
    text = text.replace("equation\n", "\n".join(decls) + "\nequation\n", 1)
    text = text.replace(f"end {new_name};", "\n".join(eqs) + f"\nend {new_name};")
    out_path = Path(out_path)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def _replace_line(source_path: Path, old: str, new: str, out_path: Path) -> Path:
    text = source_path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"expected exactly one {old!r}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text.replace(old, new), encoding="utf-8")
    return out_path


def swap_exchange_conductance(source_path, i: int, out_path) -> Path:
    """Double the inter-room exchange coefficient of Q{i}_{i+1} (a formula
    edit, like swap_room_conductance). Seed: Q{i}_{i+1}."""
    return _replace_line(Path(source_path), f"  Q{i}_{i+1} = Gadj*(T{i} - T{i+1});\n",
                         f"  Q{i}_{i+1} = 2*Gadj*(T{i} - T{i+1});\n", Path(out_path))


def swap_signal_gain(source_path, k: int, out_path) -> Path:
    """Double stage k's gain. Seed: y{k}."""
    rhs = "x" if k == 1 else f"y{k-1}"
    return _replace_line(Path(source_path), f"  y{k} = a{k}*{rhs};\n",
                         f"  y{k} = 2*a{k}*{rhs};\n", Path(out_path))


def swap_sensor_gain(source_path, room: int, stage: int, out_path) -> Path:
    """Double room `room`'s sensor stage `stage` gain. Seed: S{room}_{stage}."""
    rhs = f"T{room}" if stage == 1 else f"S{room}_{stage-1}"
    return _replace_line(Path(source_path), f"  S{room}_{stage} = ks*{rhs};\n",
                         f"  S{room}_{stage} = 2*ks*{rhs};\n", Path(out_path))


def _structure(ir: dict) -> tuple[frozenset, dict]:
    return frozenset(build_matched_graph(ir).edges()), compute_matched_units(ir)


def sweep(model: str, n: int, model_name: str, generate, edit_type: str,
          positions: list, inject, seed_of, writer) -> None:
    root = MODELS_ROOT / f"{model}_N{n}"
    base_path = generate(root / "baseline" / f"{model_name}.mo")
    baseline = compile_model(base_path, model_name)
    base_structure = _structure(baseline.ir)
    changed_path = root / f"changed_{edit_type}" / f"{model_name}.mo"
    t0 = time.perf_counter()
    for pos in positions:
        inject(base_path, pos, changed_path)
        changed = compile_model(changed_path, model_name)
        seed = seed_of(pos)
        impact = resolve_impact(changed.ir, [seed], graph_builder=build_matched_graph)
        sound = check_soundness(baseline.ir, changed.ir, impact, graph_builder=build_matched_graph)
        total, affected = impact["total_units"], len(impact["affected_units"])
        writer.writerow({
            "model": model, "N": n, "edit_type": edit_type,
            "position": pos,
            "method": "real_recompile", "total_units": total,
            "affected_units": affected, "ripple": f"{affected / total:.6g}",
            "sound": sound["sound"], "seed": seed,
            "structure_identical": _structure(changed.ir) == base_structure,
            "actually_changed_units": len(sound["actually_changed_units"]),
            "compile_s": f"{changed.compile_seconds:.4f}",
        })
    print(f"{model} N={n} {edit_type}: {len(positions)} positions in "
          f"{time.perf_counter() - t0:.1f}s", flush=True)


def sampled(n: int) -> list[int]:
    return sorted({1, 2, n - 1, n} | set(range(10, n + 1, 10)))


def main() -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()

        def run(*args):
            sweep(*args, writer=w)
            f.flush()

        for n, positions in ((250, list(range(1, 251))), (1000, sampled(1000))):
            run("thermal_chain", n, f"ThermalChain{n}", lambda p, n=n: generate_thermal_chain(n, p),
                "room_conductance", positions, swap_room_conductance, lambda i: f"Q{i}env")
        run("thermal_chain", 250, "ThermalChain250", lambda p: generate_thermal_chain(250, p),
            "exchange_conductance", list(range(1, 250)), swap_exchange_conductance,
            lambda i: f"Q{i}_{i+1}")
        for n, positions in ((250, list(range(1, 251))), (1000, sampled(1000))):
            run("signal_chain", n, f"SignalChain{n}", lambda p, n=n: generate_signal_chain(n, p),
                "stage_gain", positions, swap_signal_gain, lambda k: f"y{k}")
        # Mixed: L=5 sensor stages per room, 100 rooms. Stage-1 edit at every
        # room, then every stage of the middle room.
        mixed = ("thermal_sensor_chain", 100, "ThermalSensorChain100",
                 lambda p: generate_thermal_sensor_chain(100, 5, p))
        run(*mixed, "sensor_stage1", list(range(1, 101)),
            lambda s, r, o: swap_sensor_gain(s, r, 1, o), lambda r: f"S{r}_1")
        run(*mixed, "sensor_stage_in_room50", list(range(1, 6)),
            lambda s, j, o: swap_sensor_gain(s, 50, j, o), lambda j: f"S50_{j}")
        run(*mixed, "room_conductance", sorted({*range(1, 101, 11), 100}),
            swap_room_conductance, lambda i: f"Q{i}env")
    print(f"wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
