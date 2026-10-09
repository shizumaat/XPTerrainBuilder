# pads65 notes — continues `claude/pads63` (PR #480) after the master's sweep and the seat review, 2026-10-08/09

Scratch `<scratch>/pads65/` (`.progress`, `arm.sh` = one replay in the FROZEN tree `pads63j1` at `ARM_SHA`, `chain*.sh`,
`site.py` / `onring.py` / `padedge.py` graded-JSON probes, `t3probe.py`). Arms: `f1` (R1 attempt 1), `f2` (R1 attempt 2),
`g1` / `g1L` (everything through T3 + main `2c13d578`).

## R1 — OTHH wall-top rims (28 `structure_rim:tunnel_wall` vertices down, 31 stage-2 `hard_conflict`)

MECHANISM (read in the planar map, proved by two replay arms):

* On main the face between the pad and a wall-corridor ramp was `building6#collar` — a BANK ref. `constraints/pads._pad_rows`
  drops bank faces (`per_face … if not is_bank_ref`), `constraints/pavement_cap` drops every pair touching a collar vertex
  (`collar_v`), and `constraints/ceiling` twins only rows that exist. So no pad ceiling, no pavement fallback and no 5 % twin
  was ever stated between the wall's top rim and the ramp's vertex 0.5–1.1 m away. The exemption WAS the collar.
* 4C (`055e08f1`) deleted the collar: rim vertex and ramp vertex are now two vertices of the ONE pad face `building6`, so the
  1 % `pad_slope_max ceiling`, its `pavement_max_grade ceiling` twin and the `road_max_grade pavement fallback` ring edge are
  all stated across the wall chord against the ramp's pin (1.35 m in 0.7 m).
* The 4C fix `596e62c2` took "a vertex a STRUCTURE face carries" out of the flat set by ROLE `structure` — and a wall's top
  rim IS the exterior ring of a `retaining_wall` VOID face (structure = true, value = false). So the rims left the flat set
  with the ramp tops, and the pad-tier flat hold was the row the LP gave: rim 3.92 → 2.61.
* Arm `f1` (attempt 1: every structure-carried vertex out of the plate rows and the fallback as well): hard_conflict 31 → 0,
  but rims still down (the worst still 2.61, its neighbours 3.63) and `building9` fell 0.84 m (its door-ramp wall rims left
  its plate). Refuted as stated; kept the derivation, narrowed the set.
* Arm `f2` (attempt 2, `c35bed63`): `model.platform.structure_vertices` = vertices of structure faces that carry a VALUE
  (the ramps). A void wall face's ring stays a point of the pad (10an: the rim is flush with the surface it sits in).
  OTHH replay vs `sw6_OTHH`: hard_conflict 0; structure frame 1 mover — 25.26473779693, 51.61171830177 main 3.92 → 3.96
  (the pad's own level; on main that rim vertex sat 0.04 under it in the collar's bank); solve-owned movers 0; held-pad
  level changes 0; body 96d1b4d6cfbc.

## The instrument — `airside_value_delta` STRUCTURE frame (`0609b968`)

Law structure roles + `structure_rim` breaklines by the kind their `ref` names. Re-read of the branch's existing builds vs
`sw6` at 0.02 m: KCLT 3 (tunnel_ramp 2 @ 0.04 at 35.20105481483, -80.94033935031 / 35.20105482035, -80.94041621906;
structure_rim:tunnel_wall 1 @ 0.02 at 35.22181305165, -80.94187489425); KASE 0; HECA 0; CYXY 0; NLWF 0 (no structure);
SPJC 19 `structure_rim:channel_wall` (worst 0.24 at -12.00892759215, -77.11794847041; 0.21 at -12.00884623373,
-77.11798979198; 0.14; 0.12 × 3; 0.11 × 2; 0.10; ≤ 0.08 × 10 — one channel's rim along -12.0085…-12.0100, -77.1181…-77.1174).
SPJC's 19 are NOT the R1 class: the rim vertices are vertices of junction `pav6` (the channel's rim is flush with the pavement it
sits in, 10an) and it is `pav6` that moved (sw6 15.59 → swp 15.35 at the worst; channel floor 14.75 = 14.75) — solve-owned taxi
movers seen through the rim. KCLT's 3 are at the 0.02–0.04 m noise floor.

## R2 — SPJC -12.02473811380, -77.11902772614 (3 CRITICAL `frontage_near_miss apron|apron`, 0.060 m)

MECHANISM (`--why-from g1/SPJC.solved.pkl --why-at`, `nm_probe.py` on the solved map): v4284 is a vertex of three plateau
apron faces (`pav49#plateau:building5`, `pav46#plateau:building5` × 2), 0.980 m from the pad's ring. On main it was the
collar's outer rim → a weld of `platform_contacts` → held at the datum. With the collar gone it is plateau-only:
`platform.hold_sets` lists it as a plateau `extra`, `_with_near_miss` finds it is a near-miss endpoint (`frontage_contacts`
fires 5 pairs on it, nearest pad vertex v3949 at 0.980 m, budget 1.5 % → 0.0147 m) but skips it as already `taken`, and
`no_step.hold_interval` mints no hold row for a plateau vertex (02ag). The only rows binding it: `pad_frontage_level` (it is
a LEADER of the pad's level row) and one `plane_gradient`; the near-miss row is a priced target, not a hard row. It settled at
19.03 under datum 19.089. FIX (`ec5ff680`): a plateau vertex that is a near-miss endpoint inside the sliver
(`d <= frontage_near_miss_m`, bound to a vertex on the datum) is a frontage contact — it leaves `plateau_vertices` and is held.

## The seat review's tasks (T4, T2, T1, T3 — commits `…T4`, `95699191`, `…T1`, `1061f5fc`)

* T4: the datum's reach Band stated only where the reach intersection cuts the pair-graph interval; `stats.datum_reach_bands`.
* T2: `[design] seal_max_m = 0.05`; `weld_floor.welds_off` + `HoldPass.rewiden` + ONE pass-1b re-solve in `flex.stage_one`
  (`stage1a.weld_rewidened`) for a weld off by more and under the floor; such a weld gives PER CONTACT (`widen_weld_rows`, the
  depth-1 statement kept for this branch only — the review's "(ii-b) with the LP's relaxation as the give" has no face Δ to
  bisect because the pair graph called the level reachable). DEVIATION to rule.
* T1: `weld_floor.least_allowance` (bisection, 1 + 8 reads, upper bound `pavement_fallback_cap` = the road cap, so the answer is
  within cap/256 ≈ 0.04 pp of the least), `widen_face_rows`, `pair_graph(bump=)`; faces = the non-rigid pavement faces incident
  to a closing contact; rows = pavement-tier heads with EVERY vertex in those faces; `Linear` rows only of the point-vs-foot
  form (`ceiling._span`). Record `weld_widened.{delta_pct, faces, closing_contacts, fixed_level_m, rows, runway_rows_kept}`.
  Census: `weld_widened_nodes(nodes, platforms, ways)` → `.faces {node: delta}` joined by the way's `ref`; `_weld_give(…, d)`
  adds `delta·d` when both nodes lie on a listed face — in the three families that already read the record
  (`pavement_over_road_cap`, `within_shape`, `cross_shape`); `airside_no_step` does NOT read it (not added: report).
  DEVIATION: the census joins by REF (every face of that ref), the engine widens the touching faces only.
* T3 (owner 2026-10-09c (2a)): a fixed closing contact dictates D; the non-fixed closing contacts' faces take the allowance, the
  bisection's test is "D inside the non-fixed contacts' admissible interval"; two fixed contacts that disagree by more than
  `hard_tol_m` stand the block down (warning); `weld_widened.fixed_level_m`.

KASE arm `g1` (960dd241, `sweepwalls/base/KASE.pkl --from classify`): `building1` misfit 0.543, **Δ_b 1.25 pp** on
`pav7#plateau:building1`, 449 rows, runway rows 0, datum 2367.947 → 2367.930, released 0, WARNED 0; steepest ring edge on the
face **2.76 %** over 14.1 m at 39.22010294331, -106.86487635609 (p64: 4.61 %), next 2.74 % / 19.0 m, 2.74 % / 13.5 m. Body 718538f4d2e2.
