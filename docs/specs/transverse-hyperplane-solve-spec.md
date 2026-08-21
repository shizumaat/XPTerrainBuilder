# Transverse in the solve — weighted transect constraints (Fable spec,
# 2026-08-21; owner ruling RULINGS 2026-08-21 "RM's relocated airside
# debt is paid by the solver pricing transverse" — option 2)

Basis: two reads on lane/routemetric fec3b34 (2026-08-21). The census's
`transverse` family is a TRANSECT reader (`check_grade._check_transverse_grade`
:3572): stations every 10 m along the sidecar taxi axes, a perpendicular to
±80 m, the nearest inside span across ring EDGES, endpoint heights
edge-INTERPOLATED, budget `cap_t × width` (`transverse_cap_for_longitudinal_cap`),
direct distance — never a route. The solver already computes the same budget
(`lateral_spine_nodes.lateral_xsection_law_edges` :271) and binds it into
`u_edges` (solve.py:3949) default-ON, but (a) it can only bind NODE PAIRS, and
66 of 75 CYXY airside transverse rows have no ring vertex near either
endpoint; (b) it selects spans on the PRE-SOLVE ring (44/45 stations
vertex-hit on apron 115 → 0 spans bound) while the census reads the EMITTED
ring. Binding the four corner nodes pairwise is REFUTED (median 7.6×
over-constraint; 88 % of corner pairs > 1.2× the span width).

## The law (ONE function, both readers)

1. `grade_law.transverse_span_budget_m(cap_l, width_m) -> float` =
   `transverse_cap_for_longitudinal_cap(cap_l) * width_m`, no quantization;
   each reader adds its own envelope (`_pair_quant_noise_m` census-side, as
   `pair_grade_budget_m` does). `check_grade:3715` and
   `lateral_xsection_law_edges` both call it; neither keeps an inline copy.

2. A transect is a WEIGHTED 4-NODE constraint: near z = (1−t)·z_a + t·z_b,
   far z = (1−s)·z_c + s·z_d, `|near − far| ≤ budget`. Two half-space rows
   (w, −w) per transect, weights from the edge parameters t, s.

## The solve

3. Record: `entry["hyper"] = [(idx4, w4, b, station_id)]` — a SEPARATE list,
   never a 5-tuple in `edges` (the `len(edge) >= 4` decoders at
   one_solve.py:470/531/3432 would read it as an interval slab).
4. Flat build (one_solve.py:2118-2152): `H_idx (m,4) int`, `H_w (m,4)`,
   `H_b (m,)`, `H_free (m,4)` from `hard` (only FREE nodes absorb; a hard
   node's weight is masked, never moved).
5. Kernel (one_solve.py:966-1010), inside the same sweep after the interval
   block: `r = (H_w·z[H_idx]).sum(1) − H_b; act = r > tol;
   wf = H_w·H_free; nrm = (wf²).sum(1); step = r/nrm where act & nrm>0;
   acc −= scatter(step·wf); cnt += scatter(act)`. This is the half-space
   projection; it composes with the existing Jacobi averaging unchanged.
6. Stage: transects on airside shapes are stage A (`solve_stage.stage_of_role`
   of the owning shape, as `record_lateral_xsection_pairs` stamps today);
   groundside transects (service_road/service_junction — the same gap, 71 of
   189 CYXY rows unbound) are IN SCOPE for the mechanism but measured
   separately, stage B, and may be disabled by flag if they destabilise.
7. Every meter learns the type: `_material_over_cap` (:1633),
   `_exit_residual_by_family` (:1700), `_stall_guard_report` carrier
   (:1591-1629), `projection_law_certificate` (solve.py:6806-6829), and
   `derive_sweep_budget` (the rows join its basis, or `max_iters` is derived
   from a smaller graph than the one being solved). A hyper row that is
   over cap at exit appears in `over_cap=N` with family `transverse`.

## Coverage — the spans the census will read

8. Spans are selected against the ring the census will see. Mechanism: after
   the projection settles and vertex inserts/welds are known (the point
   where `_write_axes_sidecar` has the emitted ring), re-run the transect
   walk on THAT ring using the census's own station function (extract it
   from `check_grade._check_transverse_grade` into `grade_law` / a shared
   module so both readers call one walker — the twin asserts identical
   station sets), bind, and run the FINAL projection with the hyper rows
   present. If the final projection is not where the emitted ring is known,
   report exactly where the ring is last mutated and STOP — do not bind on a
   ring the census will not read.
9. No new vertices. `O4_XSECTION_VERTEX_HITS` stays parked.

## The band (known blind spot — measured, not wished away)

10. `reach_band_unified` is a route-edge Dijkstra and cannot carry a
    hyperplane. The writeback clamp (building_feasibility.py:1909-1912) may
    therefore re-violate a transect after the projection. Instrument it:
    after the clamp, re-evaluate every bound transect and print
    `[transverse-bind] bound=M priced=N unbound=K clamp_reviolated=R worst=…`.
    `R > 0` on any airport is a STOP-and-report (the follow-on is a
    transect-aware clamp floor/ceiling — a separate spec), never an
    improvised clamp edit in this lane.

## Lockstep artifact

11. Sidecar: `xsection_spans` beside `pair_caps` in `.axes.json` —
    `[[lat,lon],[lat,lon], width_m, budget_m, station_id]` per bound span —
    written by `layout._write_axes_sidecar`, covered by the existing
    `pair_caps_body_sha256` bake hash.
12. Census: `_check_transverse_grade` joins its priced stations to
    `xsection_spans` by station_id and reports `priced N / bound M /
    unbound N−M`; an unbound priced station is DECLARED on its own line
    (the `[bake] UNVERIFIED` shape). Refusal is not required in this round;
    the number is.

## Acceptance (lane/routemetric continuation; composed censuses via the harness)

13. Twins: (a) kernel — a 4-node synthetic transect over cap is projected
    onto the half-space, hard nodes unmoved, free nodes moved in weight
    proportion; (b) two-row symmetry gives |near−far| ≤ b from either side;
    (c) station walker identical between census and solver on a synthetic
    ring with inserts; (d) meters count a hyper row; (e) sidecar round-trip
    + bake hash still verifies; (f) zero transects → byte-identical to
    today (the flag-off arm and the no-span arm both).
14. CYXY first (≈60 s): transverse airside 75 → target ≤ the 2026-08-16
    control's 63 on the RM base, i.e. RM + this ≤ 75a per-airport (the
    merge bar); within_shape airside stays 0; `over_cap` at exit reported;
    `clamp_reviolated` reported; `airside_value_delta` vs the RM arm.
15. HECA one arm (≈17 min): per-airport airside ≤ 1,487 (the 2026-08-21
    battery) AND ≤ the RM arm's own; transverse airside from 1,046 toward
    the pre-RM 1,069 or better; certificate `over_cap`/both-hard not worse
    than the RM arm; `clamp_reviolated` = 0 or STOP.
16. Never a timing claim (ledger tripwire only); no shared-repo writes;
    kill switch `O4_TRANSVERSE_HYPER` default ON in the lane, with the
    flag-off arm as the attribution instrument.

Pre-delegated: materiality 0.01 m; attempt cap 2 then STOP; any airside
increase on any airport is a STOP; band re-violation > 0 is a STOP; a
station-set mismatch between readers is a STOP (fix the walker, not the
count).
