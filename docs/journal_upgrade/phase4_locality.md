# Phase 4: change locality versus edit position (graph level)

Question: does the paper method's recompilation scope stay local as the SAME edit
moves through a model, and what structural property governs it? Timing at sampled
positions is reported separately (Section 6).

Scripts: `src/journal_locality.py` (sweep; every position is a real text edit plus a
real Rumoca recompile, then `resolve_impact` and the independent `check_soundness`),
`src/journal_locality_sourcediff.py` (Phase 2 source diff per position),
`src/journal_figures_locality.py` (figure). Data:
`results/journal_upgrade/locality_parallel/locality_ripple.csv` (1,070 positions),
`locality_sourcediff.csv`. Figure: `figures/journal_locality_ripple.{svg,pdf}`
(regenerates byte-identically). Run 2026-09-23 12:13-12:34 IST.

Provenance: the sweep was first drafted by a stopped analysis agent; the rerun agrees
with its partial output on all 513 overlapping positions (affected units and
soundness); that draft CSV and draft note were then retired, and the draft's
predictions are preserved verbatim below.

## 1. Predictions (recorded before any sweep ran, from the draft note)

1. Thermal chain, room-loss edit at room i (seed `Q{i}env`): exactly 2 affected units
   at every position (`Q{i}env`, `T{i}`), for N=250 and N=1000.
2. Thermal chain, exchange edit (seed `Q{i}_{i+1}`): exactly 3 at every position.
3. Algebraic signal chain (one state x, `y1 = a1*x`, `yk = ak*y{k-1}`), edit at stage
   k: affected = N-k+1 of N+1 units; strongly position dependent; k=1 is essentially a
   full rebuild.
4. Every position sound; post-change graph structurally identical to the baseline for
   every coefficient edit.
5. Mixed model (thermal chain, each room temperature feeding an L-stage sensor chain):
   a stage-j sensor edit affects L-j+1 units regardless of room; a room-loss edit still
   affects 2 (sensors read the state T{i}, not der(T{i})).
6. Governing property: the size of the seed's forward algebraic cone, bounded by the
   nearest state boundaries downstream, not model size or source position.

## 2. Results

| Model, edit | Positions | Affected units | Sound | Structure unchanged |
|---|---|---|---|---|
| ThermalChain250, room loss | all 250 | 2 at every position (of 749) | all | all |
| ThermalChain1000, room loss | 103 sampled (1, 2, every 10th, N-1, N) | 2 at every position (of 2,999) | all | all |
| ThermalChain250, exchange | all 249 | 3 at every position | all | all |
| SignalChain250, stage gain | all 250 | exactly 251-k (250 at k=1 ... 1 at k=250) | all | all |
| SignalChain1000, stage gain | 103 sampled | exactly 1001-k (1,000 ... 1) | all | all |
| ThermalSensorChain100 (L=5), stage-1 edit | all 100 rooms | 5 at every room (of 799) | all | all |
| ThermalSensorChain100, room 50 stage j | j=1..5 | 5, 4, 3, 2, 1 | all | all |
| ThermalSensorChain100, room loss | 10 rooms | 2 at every room | all | all |

All six predictions confirmed exactly, with no exception across 1,070 positions.

## 3. Interpretation

The reachability scope equals the edited equation's forward algebraic cone, cut at the
nearest downstream state. It does not depend on model size or on where the edit sits in
the source, except through the cone:
- where states cut the model into short algebraic segments (thermal chain, RC ladder,
  BridgedStar, sensors behind a state), scope is constant and tiny at any size;
- where a long algebraic pipeline has no state inside it (signal chain), scope is
  position dependent and an edit near the head is effectively a full rebuild.
This is a boundary of the paper's locality claim, stated structurally rather than
as "changes are local".

## 4. Locality versus the Phase 2 source diff

Per position, the paper's reachability set vs the matching-free baseline vs the
generated-source diff (`locality_sourcediff.csv`):

| Cell | Paper | Baseline | Source diff |
|---|---|---|---|
| SignalChain250 stage 1 / 2 / 63 / 125 / 188 / 249 / 250 | 250 / 249 / 188 / 126 / 63 / 2 / 1 | 250 at every stage | 1 at every stage |
| ThermalSensorChain100 room1/50/100 stage 1 | 5 | 5 | 1 |
| ThermalSensorChain100 room 50 stage 3 | 3 | 5 | 1 |

Two findings:
- **The matching's dependency direction matters on long algebraic chains, not only on
  connect-generated MSL models.** The direction-agnostic baseline must follow the chain
  both ways and selects the whole chain (250) at every stage; the paper method selects
  only the downstream part. This corrects the earlier Phase 2 phrasing (advantage seen
  "only on MSL"): the relevant property is long algebraic dependency chains, which
  connect-generated acausal equations and algebraic pipelines both produce.
- **The recompile scope from the source diff is 1 unit at every position.** The long
  forward cone is semantic impact (values change) but not code impact. So the
  position-dependent cost appears only if reachability drives recompilation; this is
  measured in Section 6.

## 5. Decision

Thermal-chain positions are not timed further: scope is constant (2 units) at every
position and equals the configuration already timed in Phase 2 and the scale sweep, so
timing more positions would only measure noise. The signal chain is timed at a few
positions with all three strategies, because there the strategies differ by up to
250x in units recompiled and it directly tests whether build time follows the
recompile set.

## 6. Timing at sampled positions

Pending (runs after the link ablation, serially, on AC power).
