# R8 — Transverse-feasible runway seeding (Fable, 2026-08-15 late)
Evidence: the KAFW bisect (Ortho4XP/tmp/kafwbisect/, STATUS 20260815f).
The runway DEM-follow band `min(10, ½·K·d²)` is per-runway LONGITUDINAL;
parallel runways ride real cross-field fall independently (KAFW: ±0.848/
−1.398 off a 0.087 law spread → 2.333 m across a 136 m connector whose
budget is 2.046 → refusal, 9 nodes, 0.287 m).

THE LAW: a runway station's DEM-follow seed must be ROUTE-FEASIBLE — it
may not leave the reach interval implied by every already-seated station
reachable over the taxi-route graph (the same `spine_value_fields`
metric the final assertion uses).

Mechanism, two stages; stage 1 alone closes KAFW and ships first:
1. INTERIM — WIDEN THE ZERO-BAND SET + MAKE JOIN SEATING SURVIVE:
   extend `grade_law.runway_join_contacts` from centreline ENDPOINTS to
   every taxi-centreline CROSSING of a runway; a join station's law
   seating survives `faa_joint_solve`/redistribute (today it is free and
   the ride returns — the B2 flex lock finding: the ride consumes the
   runway's own 1.5 % slack so flex cannot undo it later).
2. FULL — clamp each DEM-follow station into the route-metric reach
   interval of already-seated stations (order: CIFP pins, then joins,
   then interiors). Implement only if stage 1 leaves any battery/KAFW/
   KDFW runway-pair infeasibility.
Acceptance: KAFW builds rc=0 (no --allow flags) and its census reported;
CYXY+HECA+SPJC+SPLP censuses: runway families (runway_crown,
runway_end_skirt, raoa, within_shape::runway) at-or-better, airside
byte-identical preferred, any delta attributed; twins for (a) a crossing
mints a join contact, (b) join seating survives the joint solve, (c) the
KAFW two-runway fixture solves (synthetic). Build-time: ledger frame.
Materiality 0.01; attempt cap 2 then STOP. Deviations STOP to the lead.
