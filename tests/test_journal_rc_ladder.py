"""Journal upgrade, phase 3: RC ladder and BridgedStar at graph level and
generated-C-text level only. No gcc, no build, no simulation run."""
import json
import sys
from pathlib import Path

import pytest
import rumoca as rm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codegen_units import generate_header
from journal_generators import generate_bridged_star, swap_branch_bridge
from journal_rc_changes import add_segment_probe, swap_segment_resistance
from matched_graph import build_matched_graph
from matched_units import compute_matched_units
from matching import compute_matching
from model_layout import build_layout
from resolver import resolve_impact
from scaled_models import generate_rc_ladder
from soundness import check_soundness
from unit_codegen import generate_all_unit_sources, generate_unit_driver_dynamic


def _load(path, name):
    model = rm.Session().load(str(path), model=name)
    return json.loads(model.to_json(stage="dae")), model.structure()


def _impact(base_ir, chg_ir, seed):
    impact = resolve_impact(chg_ir, seed, graph_builder=build_matched_graph)
    sound = check_soundness(base_ir, chg_ir, impact, graph_builder=build_matched_graph)
    return impact, sound


@pytest.mark.parametrize("n", [3, 20])
def test_rc_ladder_graph(tmp_path, n):
    name = f"RcLadder{n}"
    ir, st = _load(generate_rc_ladder(n, tmp_path / name / f"{name}.mo"), name)
    m = compute_matching(ir)
    units = compute_matched_units(ir)
    assert len(ir["f_x"]) == 2 * n + 1
    assert m.is_matched and m.agrees_with_natural_targets()
    assert all(len(v) == 1 for v in units.values())  # states cut every loop
    assert len(units) == st.n_blocks == 2 * n + 1 and st.n_algebraic_loops == 0
    g = build_matched_graph(ir)
    for s in ir["x"]:
        # src/matching.py drops states from eq_involves entirely, so a
        # state never even appears as a read node: it cannot be an edge source.
        assert ("var", s) not in g and g.out_degree(("der", s)) == 0


def test_rc_ladder_codegen_translates_sin_and_time(tmp_path):
    name = "RcLadder4"
    ir, _ = _load(generate_rc_ladder(4, tmp_path / name / f"{name}.mo"), name)
    layout = build_layout(ir)
    files = generate_all_unit_sources(name, ir, layout)
    driver = generate_unit_driver_dynamic(name, ir, layout)
    assert len(files) == 9
    vs = files[f"{name}_unit_Vs.c"]
    assert "sin(" in vs and "v->time" in vs
    assert "v.time = 0.0;" in driver and "v.time += dt;" in driver
    assert "real_t time;" in generate_header(name, layout)


@pytest.mark.parametrize("i", [1, 5, 10])
def test_rc_injectors_ripple_and_soundness(tmp_path, i):
    n, name = 10, "RcLadder10"
    base = generate_rc_ladder(n, tmp_path / "base" / f"{name}.mo")
    base_ir, _ = _load(base, name)

    swap_ir, _ = _load(swap_segment_resistance(base, i, tmp_path / "swap" / f"{name}.mo"), name)
    impact, sound = _impact(base_ir, swap_ir, [f"I{i}"])
    assert impact["affected_units"] == sorted([f"I{i}", f"V{i}"])
    assert sound["actually_changed_units"] == [f"I{i}"] and sound["sound"]

    probe_ir, _ = _load(add_segment_probe(base, i, tmp_path / "probe" / f"{name}.mo"), name)
    impact, sound = _impact(base_ir, probe_ir, [f"P{i}"])
    assert impact["affected_units"] == [f"P{i}"] and impact["total_units"] == 2 * n + 2
    assert sound["actually_changed_units"] == [f"P{i}"] and sound["sound"]
    assert f"{name}_unit_P{i}.c" in generate_all_unit_sources(name, probe_ir, build_layout(base_ir, probe_ir))


def test_bridged_star_has_coupled_blocks_and_hub_fan_in(tmp_path):
    n, name, k = 6, "BridgedStar6", 3
    base = generate_bridged_star(n, tmp_path / "base" / f"{name}.mo")
    ir, st = _load(base, name)
    m = compute_matching(ir)
    units = compute_matched_units(ir)
    sizes = sorted(len(v) for v in units.values())
    assert len(ir["f_x"]) == 6 * n + 1 and m.is_matched
    assert sizes == [1] * (n + 1) + [5] * n
    assert len(units) == st.n_blocks and st.n_algebraic_loops == n

    files = generate_all_unit_sources(name, ir, build_layout(ir))
    assert sum("rumoca_solve_linear_nxn(5," in src for src in files.values()) == n

    chg_ir, _ = _load(swap_branch_bridge(base, k, tmp_path / "swap" / f"{name}.mo"), name)
    impact, sound = _impact(ir, chg_ir, [f"J{k}"])
    block = next(u for u, mem in units.items() if f"J{k}" in mem)
    assert impact["affected_units"] == sorted([block, f"V{k}", "Vh"])
    assert sound["sound"]
