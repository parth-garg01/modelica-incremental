import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codegen_units import generate_all_units
from compile import compile_model
from matched_codegen import generate_all_units_from_matching
from model_layout import build_layout

MODELS = [
    ("models/one_line/OneLine.mo", "OneLine"),
    ("models/decoupled_pair/DecoupledPair.mo", "DecoupledPair"),
    ("models/rlc_circuit/RLCCircuit.mo", "RLCCircuit"),
    ("models/thermal_network/ThermalNetwork.mo", "ThermalNetwork"),
    ("models/chain/Chain.mo", "Chain"),
]


@pytest.mark.parametrize("path,model_name", MODELS)
def test_matched_codegen_is_bit_identical_to_phase_2_codegen(path, model_name):
    """Feature 3's regression check: matching-driven codegen must produce
    EXACTLY the same C source as phase-2's independent natural-target
    codegen, on every fully-assignment-form fixture, not just RLC and
    Thermal (the two the PRD names explicitly)."""
    result = compile_model(path, model_name)
    layout = build_layout(result.ir)

    matched_files = generate_all_units_from_matching(model_name, result.ir, layout)
    original_files = generate_all_units(model_name, result.ir, layout)

    assert matched_files.keys() == original_files.keys()
    for filename in matched_files:
        assert matched_files[filename] == original_files[filename], (
            f"{model_name}/{filename}: matched-driven codegen diverged from phase-2 codegen"
        )


def test_matched_codegen_refuses_a_coupled_block():
    """Feature 3 only handles singleton blocks; a genuine coupled block
    (Feature 4's job) must raise, not silently emit wrong single-equation
    code for one member of the block."""
    result = compile_model("models/coupled_algebraic/CoupledAlgebraic.mo", "CoupledAlgebraic")
    layout = build_layout(result.ir)
    with pytest.raises(NotImplementedError):
        generate_all_units_from_matching("CoupledAlgebraic", result.ir, layout)


def test_unary_minus_translates_correctly():
    """Teeth check for the real pre-existing bug this feature caught:
    expr_c.py's Unary handling read node["Unary"]["arg"], but the actual
    IR key is "rhs" (mirroring Binary's lhs/rhs naming) -- this crashed
    with KeyError on ANY equation using unary minus (e.g. OneLine's
    der(x) = -x), for BOTH the old and new codegen paths, and had never
    been caught because only RLC/ThermalNetwork (neither of which uses a
    bare unary minus) had ever been run through C codegen before."""
    result = compile_model("models/one_line/OneLine.mo", "OneLine")
    layout = build_layout(result.ir)
    files = generate_all_units_from_matching("OneLine", result.ir, layout)
    assert len(files) == 1
    c_source = next(iter(files.values()))
    assert "-(" in c_source or "(-" in c_source
