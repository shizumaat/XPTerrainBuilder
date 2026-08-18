# RM — Route-metric within-shape budgets, apron family (Fable; OWNER-
# RULED 2026-08-15 late, RULINGS "WITHIN-SHAPE BUDGET IS ROUTE-METRIC")
Scope: within-shape pair budgets for the apron/junction/groundside
families (ROLE_GRADE_LIMITS caps unchanged — the DISTANCE changes:
budget = cap × route_distance(pair) where route_distance = route-graph
distance between the pair's attachments + both off-route legs — the
band's own metric, spine_value_fields). Runway/taxiway laws UNCHANGED.
One metric, both readers: the solver's pair_caps bake AND
check_grade/census read the same route distance (the bake already
carries route credit for 473/1,485 HECA pairs — generalize, don't
fork; the census gets it from the sidecar routes the same way the C1
attribution's proxy did, but through the ONE shared implementation —
add it to check_grade as the law function both import).
Consequences to measure (the C1/SM3/C2/C3 populations): HECA airside
within_shape (1,502-class) collapses by the SM1 share; SM3's
cap_slab-vs-band_ceiling empty intervals (829) dissolve; C2's +82 and
C3's +626 re-pricing re-adjudicate. Expect SM2's long-chord relief
(232 rows) to shrink but possibly survive — report it separately (it
is the terrace question's residue; the owner chose route-metric over
terraces, so survivors are reported, not terraced).
Acceptance: HECA + CYXY censuses with per-family deltas and the
SM1/SM2/SM3 decomposition re-run (the C1 method: pairs vs their own
baked budgets); airside strictly improves; no new family; twins:
(a) solver budget == census budget for a synthetic detour pair
(twin-assert through test_harness's shared path), (b) runway/taxi
pairs byte-unchanged, (c) a genuine long-chord violation still fires
under the route budget. Materiality 0.01; attempt cap 2; STOP to lead.

## OWNER ANSWERS (2026-08-18 interview; RULINGS same date)
(a) TRANSVERSE STAYS EUCLIDEAN — the relocated flatness debt (HECA
transverse +963) is paid by mechanism (C3 aligned partner feet +
junction co-level, airside-frozen rework), never re-priced. (b)
"Airside strictly improves" is PER-AIRPORT — CYXY's +20 BLOCKS the
merge until attributed and paid: `rm-cyxy-plus20-attribution-brief.md`
is the gate. The groundside_pavement/tunnel_ramp no-solver-pair-bake
interpretation flag stays open for the lead when the lane resumes
(census-only pricing would fork the lockstep — do not land it without
a lead ruling).
