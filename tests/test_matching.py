import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from matching import blt_blocks, compute_matching, _kuhn_max_bipartite_matching

FIXTURES = Path(__file__).resolve().parent.parent / "results" / "fixtures"

ASSIGNMENT_FORM_MODELS = ["OneLine", "DecoupledPair", "RLCCircuit", "ThermalNetwork", "Chain"]


def load_ir(model_name: str) -> dict:
    return json.loads((FIXTURES / f"{model_name}.json").read_text())


@pytest.mark.parametrize("model_name", ASSIGNMENT_FORM_MODELS)
def test_fully_assignment_form_models_match_completely_and_agree(model_name):
    """On every model with no anonymous residuals, the matcher must find
    a perfect matching that agrees exactly with the known-correct
    assignment-form target for every equation -- this is the Feature 1
    regression check."""
    ir = load_ir(model_name)
    m = compute_matching(ir)
    assert m.is_matched is True
    assert m.unmatched_equations == []
    assert m.agrees_with_natural_targets() is True


@pytest.mark.parametrize("model_name,expected_blocks", [
    ("OneLine", 1), ("DecoupledPair", 2), ("RLCCircuit", 3), ("ThermalNetwork", 9),
])
def test_block_count_matches_rumocas_own_structural_info(model_name, expected_blocks):
    """Cross-check against Model.structure().n_blocks, captured when the
    fixture was generated (these are the values printed in each commit's
    evidence, not re-queried live here to keep this test IR-file-only)."""
    ir = load_ir(model_name)
    m = compute_matching(ir)
    blocks = blt_blocks(ir, m)
    assert len(blocks) == expected_blocks


def test_kuhn_matching_is_deterministic_across_repeated_calls():
    """Teeth check for the reproducibility bug this module's docstring
    describes: run the same real-world (partial-conflict) matching input
    many times and confirm the result never changes. Before switching
    from networkx's hopcroft_karp_matching to this hand-rolled Kuhn's
    algorithm, this exact scenario produced a DIFFERENT unmatched pair on
    almost every run."""
    left = [0, 11, 56, 57, 58, 62, 63]
    adjacency = {
        0: ["G.p.v"],
        11: ["C3.n.v", "C3.p.v"],
        56: ["C1.n.v", "G.p.v"],
        57: ["C3.n.v", "G.p.v"],
        58: ["C3.n.v", "C5.n.v"],
        62: ["C2.n.v", "C3.p.v"],
        63: ["C3.p.v", "C4.p.v"],
    }
    results = [_kuhn_max_bipartite_matching(left, adjacency) for _ in range(20)]
    assert all(r == results[0] for r in results)
    assert len(results[0]) == 7  # a perfect matching exists and must be found every time


def test_kuhn_matching_finds_maximum_not_first_greedy_result():
    """A left node whose only candidate is already taken must trigger a
    correct augmenting-path re-assignment, not fail outright. u0 and u1
    both only want v0; a correct matcher must give v0 to one of them and
    reroute the other to v1."""
    left = ["u0", "u1"]
    adjacency = {"u0": ["v0"], "u1": ["v0", "v1"]}
    result = _kuhn_max_bipartite_matching(left, adjacency)
    assert len(result) == 2
    assert result["u0"] == "v0"
    assert result["u1"] == "v1"


def test_states_are_never_reassigned_by_a_reader():
    """Teeth check for the states-exclusion fix: without it, an equation
    that merely reads a state's current value could get matched to the
    state itself, stealing it from the state's own differential row.
    Confirmed to actually happen on ThermalNetwork before the fix (Q1env
    <-> T1 got swapped); this checks it doesn't regress."""
    ir = load_ir("ThermalNetwork")
    m = compute_matching(ir)
    for i, kind in m.eq_kind.items():
        if kind == "x":
            state_name = m.eq_natural_target[i]
            assert m.eq_to_var[i] == state_name, (
                f"state equation {i} was matched away from its own state {state_name!r}"
            )
