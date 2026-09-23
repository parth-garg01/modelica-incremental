"""Journal upgrade, phase 5: controlled ablation of ONE design choice,
"states are not edge sources", at the dependency-graph level only.

`build_ablation_graph(ir, states_as_edge_sources)`:
  False: the shipped definition. Must reproduce matched_graph.build_matched_graph()
         and matched_units.compute_matched_units() exactly (asserted per model).
  True:  the naive reading. A state's own derivative row "writes" the state
         itself (("var", x), not ("der", x)), and every equation that reads the
         state's value gets an ordinary read edge from it. The matching, the
         unit-id convention, the resolver and the soundness check are unchanged.

No C builds, no gcc: Rumoca compiles plus pure-Python graph/codegen only.
Run from the repo root: PYTHONPATH=src python src/journal_state_ablation.py
"""
from __future__ import annotations

import csv
import functools
from pathlib import Path

import networkx as nx
import numpy as np
import rumoca as rm

from graph import _varrefs, build_dependency_graph
from matched_graph import build_matched_graph
from matched_units import compute_matched_units
from matching import compute_matching
from resolver import resolve_impact
from scaled_models import generate_rc_ladder, generate_thermal_chain, swap_room_conductance
from soundness import check_soundness
from units import compute_units

GEN_ROOT = Path("models/journal_ablation_parallel")
OUT_UNITS = Path("results/journal_upgrade/states_ablation_parallel/state_ablation_units.csv")
OUT_RIPPLE = Path("results/journal_upgrade/states_ablation_parallel/state_ablation_ripple.csv")


def build_ablation_graph(ir: dict, states_as_edge_sources: bool) -> nx.DiGraph:
    m = compute_matching(ir)
    states = set(ir["x"].keys())
    g = nx.DiGraph()
    for i, name in m.eq_to_var.items():
        is_state_row = m.eq_kind[i] == "x"
        eq_node = ("eq", name)
        write_node = ("var", name) if (states_as_edge_sources or not is_state_row) else ("der", name)
        g.add_node(eq_node, kind=m.eq_kind[i])
        g.add_node(write_node)
        g.add_edge(eq_node, write_node)
        reads = set(m.eq_involves[i])
        if states_as_edge_sources:
            reads |= _varrefs(ir["f_x"][i]) & states
        for read_name in reads:
            if read_name == name:
                continue
            g.add_node(("var", read_name))
            g.add_edge(("var", read_name), eq_node)
    return g


def builder(toggle: bool):
    return functools.partial(build_ablation_graph, states_as_edge_sources=toggle)


def check_reproduces_shipped(ir: dict) -> bool:
    g = build_ablation_graph(ir, False)
    ref = build_matched_graph(ir)
    assert set(g.nodes) == set(ref.nodes) and set(g.edges) == set(ref.edges), "graph differs from build_matched_graph"
    assert compute_units(g) == compute_matched_units(ir), "units differ from compute_matched_units"
    return True


def load(path, model_name, roots=None, structure=True):
    session = rm.Session(roots=roots) if roots else rm.Session()
    model = session.load(str(path), model=model_name)
    import json
    ir = json.loads(model.to_json(stage="dae"))
    if not structure:  # Rumoca structure() took > 90 s on ThermalChain1000 (diagnosed, not run)
        return ir, "skipped: structure() too slow at this size"
    try:
        n_blocks = model.structure().n_blocks
    except Exception as e:  # noqa: BLE001 - recorded, not hidden
        n_blocks = f"unavailable: {type(e).__name__}"
    return ir, n_blocks


def unit_stats(units: dict) -> dict:
    sizes = [len(v) for v in units.values()]
    return dict(n_units=len(units), largest_unit=max(sizes, default=0), n_coupled_units=sum(s > 1 for s in sizes))


# ---------------------------------------------------------------- models

FIXTURES = [
    ("OneLine", "models/one_line/OneLine.mo"),
    ("DecoupledPair", "models/decoupled_pair/DecoupledPair.mo"),
    ("RLCCircuit", "models/rlc_circuit/RLCCircuit.mo"),
    ("ThermalNetwork", "models/thermal_network/ThermalNetwork.mo"),
    ("Chain", "models/chain/Chain.mo"),
    ("CoupledAlgebraic", "models/coupled_algebraic/CoupledAlgebraic.mo"),
    ("CoupledDynamic", "models/coupled_dynamic/CoupledDynamic.mo"),
]
MSL = [
    ("MslRcCircuit", "models/msl_rc_circuit/MslRcCircuit.mo", ["msl_src", "models/msl_rc_circuit"]),
    ("MslResistorNetwork", "models/msl_resistor_network/MslResistorNetwork.mo", ["msl_src", "models/msl_resistor_network"]),
    ("MslThermalChain", "models/msl_thermal_chain/MslThermalChain.mo", ["msl_src", "models/msl_thermal_chain"]),
]

# (label, baseline path, changed path, model name, seed, baseline roots, changed roots)
FIXTURE_CELLS = [
    ("ThermalNetwork swap", "models/thermal_network/ThermalNetwork.mo", "models/thermal_network_swapped/ThermalNetwork.mo", "ThermalNetwork", ["Q1"], None, None),
    ("ThermalNetwork sensor", "models/thermal_network/ThermalNetwork.mo", "models/thermal_network_sensor/ThermalNetwork.mo", "ThermalNetwork", ["Qtotal"], None, None),
    ("ThermalNetwork removal", "models/thermal_network/ThermalNetwork.mo", "models/thermal_network_removed/ThermalNetwork.mo", "ThermalNetwork", ["T2"], None, None),
    ("RLCCircuit swap", "models/rlc_circuit/RLCCircuit.mo", "models/rlc_circuit_swapped/RLCCircuit.mo", "RLCCircuit", ["i"], None, None),
    ("Chain swap", "models/chain/Chain.mo", "models/chain_swapped/Chain.mo", "Chain", ["y1"], None, None),
]


def msl_cells():
    from measure_msl import CELLS  # import only; run_cell is never called
    labels = ["MslRcCircuit swap", "MslThermalChain swap", "MslRcCircuit sensor", "MslResistorNetwork removal"]
    return [(lab, c["baseline_path"], c["changed_path"], c["model_name"], c["seed"], c["baseline_roots"], c["changed_roots"])
            for lab, c in zip(labels, CELLS)]


def scaled_models():
    out = []
    for n in (10, 50, 250, 1000):
        name = f"ThermalChain{n}"
        base = generate_thermal_chain(n, GEN_ROOT / f"{name}_base" / f"{name}.mo")
        chg = swap_room_conductance(base, n // 2, GEN_ROOT / f"{name}_swap" / f"{name}.mo")
        out.append((name, base, chg, n))
    for n in (10, 50, 250):
        name = f"RcLadder{n}"
        out.append((name, generate_rc_ladder(n, GEN_ROOT / f"{name}_base" / f"{name}.mo"), None, n))
    return out


# ---------------------------------------------------------------- codegen evidence

def codegen_probe(model_name: str, ir: dict, toggle: bool) -> dict:
    """Run the repo's own pure-Python unit codegen and dynamic driver
    generator with toggle-True units swapped in (monkeypatched at runtime in
    the importing modules' namespaces only; no file is modified). Records
    what happens rather than asserting it."""
    import eval_order
    import unit_codegen
    from model_layout import build_layout

    units = compute_units(build_ablation_graph(ir, toggle))
    patched = lambda _ir: units  # noqa: E731
    saved = (unit_codegen.compute_matched_units, eval_order.compute_matched_units)
    unit_codegen.compute_matched_units = eval_order.compute_matched_units = patched
    rec = {"model": model_name, "toggle": toggle}
    try:
        layout = build_layout(ir)
        try:
            files = unit_codegen.generate_all_unit_sources(model_name, ir, layout)
            rec["unit_codegen"] = f"ok ({len(files)} files)"
        except Exception as e:  # noqa: BLE001
            rec["unit_codegen"] = f"{type(e).__name__}: {str(e)[:160]}"
            files = None
        try:
            driver = unit_codegen.generate_unit_driver_dynamic(model_name, ir, layout)
            rec["driver_codegen"] = "ok"
            if files is not None:
                exported = {ln.split("void ")[1].split("(")[0] for src in files.values()
                            for ln in src.splitlines() if "__declspec(dllexport)" in ln}
                requested = {ln.split('", "')[1].split('"')[0] for ln in driver.splitlines() if "_load_unit(\"" in ln}
                missing = sorted(requested - exported)
                rec["driver_symbols_missing"] = missing
        except Exception as e:  # noqa: BLE001
            rec["driver_codegen"] = f"{type(e).__name__}: {str(e)[:160]}"
    finally:
        unit_codegen.compute_matched_units, eval_order.compute_matched_units = saved
    return rec


def _eval(node, env):
    if "VarRef" in node:
        return env(node["VarRef"]["name"]["name"], False)
    if "Literal" in node:
        return float(next(iter(node["Literal"]["value"].values())))
    if "Binary" in node:
        a, b, op = _eval(node["Binary"]["lhs"], env), _eval(node["Binary"]["rhs"], env), node["Binary"]["op"]
        ops = {"Add": lambda: a + b, "Sub": lambda: a - b, "Mul": lambda: a * b, "Div": lambda: a / b,
               "Exp": lambda: a ** b, "Pow": lambda: a ** b}
        if op not in ops:
            raise NotImplementedError(f"Binary {op}")
        return ops[op]()
    if "Unary" in node:
        return -_eval(node["Unary"]["rhs"], env)
    if "BuiltinCall" in node:
        fn, args = node["BuiltinCall"]["function"], node["BuiltinCall"]["args"]
        if fn == "Der":
            return env(args[0]["VarRef"]["name"]["name"], True)
        return {"Sin": np.sin, "Cos": np.cos, "Exp": np.exp}[fn](_eval(args[0], env))
    raise NotImplementedError(list(node.keys()))


def semantic_probe(ir: dict, t: float = 0.3) -> dict | None:
    """Pure-Python numeric check at one time point: solve the full per-step
    system two ways and compare the value that would land in v->dx.
      correct: unknowns = algebraics + der(x); state values are knowns.
      naive:   unknowns = algebraics + x, with der(x) and x read as the SAME
               unknown (what "the der row writes x" means if taken literally,
               and what block_codegen would compute if Der() were accepted).
    States are set to start + (k+1) so the check is not at a trivial point."""
    xs, ys = list(ir["x"]), list(ir["y"]) + list(ir.get("w", {}))
    if not xs:
        return None
    params = {n: _eval(v["start"], lambda *_: 0.0) for n, v in ir["p"].items()}
    xval = {n: _eval(ir["x"][n]["start"], lambda *_: 0.0) + k + 1 for k, n in enumerate(xs)}

    def solve(keys, env_for):
        def resid(z):
            env = env_for(dict(zip(keys, z)))
            return np.array([_eval(e["rhs"], env) for e in ir["f_x"]])
        c = resid(np.zeros(len(keys)))
        A = np.column_stack([resid(np.eye(len(keys))[j]) - c for j in range(len(keys))])
        probe = np.linspace(0.3, 1.7, len(keys))
        linear = bool(np.allclose(resid(probe), A @ probe + c))
        if np.linalg.matrix_rank(A) < len(keys):
            return None, linear
        return dict(zip(keys, np.linalg.solve(A, -c))), linear

    def base_env(zmap, der_key):
        def env(name, is_der):
            if name == "time":
                return t
            if is_der:
                return zmap[der_key(name)]
            if name in zmap:
                return zmap[name]
            return xval[name] if name in xval else params[name]
        return env

    good, lin_g = solve(ys + [("der", x) for x in xs], lambda z: base_env(z, lambda n: ("der", n)))
    naive, lin_n = solve(ys + xs, lambda z: base_env(z, lambda n: n))
    out = {"linear": lin_g and lin_n, "correct_dx": {x: good[("der", x)] for x in xs} if good else "singular"}
    out["naive_dx"] = {x: naive[x] for x in xs} if naive else "singular"
    if good and naive:
        out["max_abs_dx_error"] = max(abs(good[("der", x)] - naive[x]) for x in xs)
    return out


# ---------------------------------------------------------------- main

def main():
    unit_rows, ripple_rows, codegen_rows, semantic_rows = [], [], [], []
    cache: dict = {}

    def get(path, name, roots=None, structure=True):
        key = (str(path), name)
        if key not in cache:
            cache[key] = load(path, name, roots, structure)
        return cache[key]

    def record_model(label, ir, n_blocks, kind):
        assert check_reproduces_shipped(ir)
        for toggle in (False, True):
            units = compute_units(build_ablation_graph(ir, toggle))
            st = unit_stats(units)
            unit_rows.append(dict(model=label, kind=kind, variant=f"states_as_edge_sources={toggle}",
                                  n_equations=len(ir["f_x"]), **st, rumoca_n_blocks=n_blocks,
                                  agrees_with_rumoca=(st["n_units"] == n_blocks) if isinstance(n_blocks, int) else "",
                                  reproduces_shipped=(True if not toggle else "")))
        try:
            st = unit_stats(compute_units(build_dependency_graph(ir)))
            unit_rows.append(dict(model=label, kind=kind, variant="raw_phase1_graph", n_equations=len(ir["f_x"]), **st,
                                  rumoca_n_blocks=n_blocks,
                                  agrees_with_rumoca=(st["n_units"] == n_blocks) if isinstance(n_blocks, int) else "",
                                  reproduces_shipped=""))
        except Exception as e:  # noqa: BLE001 - raw graph cannot parse anonymous residuals
            print(f"  raw graph n/a on {label}: {type(e).__name__}")

    def record_cell(label, base_ir, chg_ir, seed, with_raw):
        variants = [(f"states_as_edge_sources={t}", builder(t)) for t in (False, True)]
        if with_raw:
            variants.append(("raw_phase1_graph", build_dependency_graph))
        for vname, gb in variants:
            impact = resolve_impact(chg_ir, seed, graph_builder=gb)
            sound = check_soundness(base_ir, chg_ir, impact, graph_builder=gb)
            recompiled_eqs = sum(len(impact["units"][u]) for u in impact["affected_units"])
            # equation-level superset check, over equations that exist post-change
            present = {n[1] for n in gb(chg_ir).nodes if n[0] == "eq"}
            eq_superset = (set(sound["actually_changed_equations"]) & present) <= set(impact["affected_equations"])
            ripple_rows.append(dict(
                cell=label, seed=",".join(seed), variant=vname,
                n_equations=len(chg_ir["f_x"]), total_units=impact["total_units"],
                affected_units=len(impact["affected_units"]),
                ripple_units=round(len(impact["affected_units"]) / impact["total_units"], 4),
                equations_recompiled=recompiled_eqs,
                ripple_equations=round(recompiled_eqs / len(chg_ir["f_x"]), 4),
                traversal_equations=len(impact["affected_equations"]),
                actually_changed_equations=len(sound["actually_changed_equations"]),
                sound_units=sound["sound"], missed_units=";".join(sound["missed_units"]),
                sound_equations_superset=eq_superset,
            ))

    for name, path in FIXTURES:
        print(name)
        ir, nb = get(path, name)
        record_model(name, ir, nb, "fixture")
        for t in (False, True):
            codegen_rows.append(codegen_probe(name, ir, t))
        try:
            sp = semantic_probe(ir)
            if sp:
                semantic_rows.append((name, sp))
        except NotImplementedError as e:
            semantic_rows.append((name, f"evaluator unsupported node {e}"))
    for name, path, roots in MSL:
        print(name)
        ir, nb = get(path, name, roots)
        record_model(name, ir, nb, "msl")
        for t in (False, True):
            codegen_rows.append(codegen_probe(name, ir, t))

    for label, bp, cp, name, seed, broots, croots in FIXTURE_CELLS:
        print(label)
        record_cell(label, get(bp, name, broots)[0], get(cp, name, croots)[0], seed, with_raw=True)
    for label, bp, cp, name, seed, broots, croots in msl_cells():
        print(label)
        record_cell(label, get(bp, name, broots)[0], get(cp, name, croots)[0], seed, with_raw=False)

    for name, base, chg, n in scaled_models():
        print(name)
        ir, nb = get(base, name, structure=n <= 250)
        record_model(name, ir, nb, "generated")
        if n <= 50:
            for t in (False, True):
                codegen_rows.append(codegen_probe(name, ir, t))
        if chg is not None:
            record_cell(f"{name} swap_room_conductance(room {n // 2})", ir, get(chg, name, structure=False)[0], [f"Q{n // 2}env"],
                        with_raw=(n <= 250))

    for path, rows in ((OUT_UNITS, unit_rows), (OUT_RIPPLE, ripple_rows)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {path} ({len(rows)} rows)")

    import json
    probes = OUT_UNITS.parent / "state_ablation_probes.json"
    probes.write_text(json.dumps({"codegen": codegen_rows, "semantic": [[n, sp] for n, sp in semantic_rows]},
                                 indent=2, default=str), encoding="utf-8")
    print(f"wrote {probes}")
    print("\nCODEGEN PROBE")
    for r in codegen_rows:
        print(" ", r)
    print("\nSEMANTIC PROBE")
    for name, sp in semantic_rows:
        print(" ", name, sp)


if __name__ == "__main__":
    main()
