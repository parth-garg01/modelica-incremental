# Results summary (generated from results/measurements.parquet)

- **RLCCircuit** (component_swap, seed=i): 1/2 units affected (50% ripple), projected speedup ceiling **2.00x**, compile time 3.83 ms (± 0.99 ms, 7 repeats).
- **ThermalNetwork** (component_swap, seed=Q1): 1/1 units affected (100% ripple), projected speedup ceiling **1.00x**, compile time 5.20 ms (± 1.14 ms, 7 repeats).

The speedup ceiling is a **projection** (1 / affected_fraction), an optimistic upper bound that ignores relink and re-matching overhead -- not a measured incremental compile time. No incremental compiler was built this week; see prd.md Section 2 and Section 12 for the full limitations.
