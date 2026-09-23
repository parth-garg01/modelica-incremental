"""Locality x Phase 2: per edit position, compare the paper's reachability set with the
generated-source diff on the models where reachability scope varies with position.
Reuses journal_phase2_verify_oracle.verify (independent source diff). Pure Python, no builds.
Output: results/journal_upgrade/locality_parallel/locality_sourcediff.csv"""
from pathlib import Path

import pandas as pd

from journal_locality import generate_signal_chain, generate_thermal_sensor_chain, swap_sensor_gain, swap_signal_gain
from journal_phase2_verify_oracle import verify

ROOT = Path("models/journal_locality_sourcediff")
cells = []
base = generate_signal_chain(250, ROOT / "sig_base" / "SignalChain250.mo")
for k in (1, 2, 63, 125, 188, 249, 250):
    chg = swap_signal_gain(base, k, ROOT / f"sig_{k}" / "SignalChain250.mo")
    cells.append(dict(label=f"SignalChain250/stage{k}", baseline_path=str(base), changed_path=str(chg),
                      model_name="SignalChain250", seed=[f"y{k}"]))
sbase = generate_thermal_sensor_chain(100, 5, ROOT / "sens_base" / "ThermalSensorChain100.mo")
for room, stage in ((1, 1), (50, 1), (50, 3), (100, 1)):
    chg = swap_sensor_gain(sbase, room, stage, ROOT / f"sens_{room}_{stage}" / "ThermalSensorChain100.mo")
    cells.append(dict(label=f"ThermalSensorChain100/room{room}_stage{stage}", baseline_path=str(sbase),
                      changed_path=str(chg), model_name="ThermalSensorChain100", seed=[f"S{room}_{stage}"]))

rows = []
for c in cells:
    r = verify(c)
    rows.append({k: v for k, v in r.items() if k != "sets"})
    print(f"{r['cell']:40s} paper={r['n_paper']:4d} baseline={r['n_baseline']:4d} source_diff={r['n_oracle']:3d} "
          f"oracle<=paper={r['oracle_subset_of_paper']}", flush=True)
out = Path("results/journal_upgrade/locality_parallel/locality_sourcediff.csv")
pd.DataFrame(rows).to_csv(out, index=False)
print("wrote", out)
