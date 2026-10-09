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
