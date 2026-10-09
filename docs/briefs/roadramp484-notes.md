# roadramp484 — lane notes (issue #484; RULINGS 2026-10-08c (1), 2026-10-09c (2b))

Branch `claude/roadramp484`, base main `e2eec15c`. Scratch:
`<scratchpad>/roadramp484/` (captures `cap/ICAO.pkl`, arms `A/` main-tree replay, `B/` this tree).

## S1 — the read (what states a road at the cap)

`airport/road_ramp.road_ramp_targets` (spec §37 (6)): per governed road vertex a
DESIGN-TARGET EQUALITY (`Linear lo = hi = target`, law weight) plus a hard ceiling
`target + visual_m`; `target(route, station) = max(floor, envelope)`, floor = the core
clamp of the route at that station, envelope = max over the mouths (every road-face
vertex whose senior role is airside, at `max(published airside target, DEM)`) of
`z_mouth − cap × graph distance`, lifted onto the route (one value per station).
`cap` = the smallest longitudinal cap of the road family. Nothing ENDS the ramp: the
cone runs over the whole connected road graph and is simply under the floor where the
floor is higher. So the cap was the grade the road was built at wherever the cone
stood over the floor.

Every reader of "cap × distance" in the road-ramp family, ruled by reading:

| site | what it states | ruling |
|---|---|---|
| `road_ramp_targets` envelope | target equality at the cap | THE DEFECT — changed |
| `constraints/road_ramp._reach_seed` (27a (11)) | stage 2: target and ceiling raised to `z_edge − cap × s` for the vertices a reach contact within a lane width governs | same ramp, same defect — changed |
| `constraints/road_ramp.terrace_profile` bare run (03b) | stage 2: `clip(target, L ± cap × d)` beyond the last bordered station of a terraced ribbon — an equality AT the cap wherever the road's own target is outside the cone | same defect (the road leaving the pavement it borders) — changed |
| `terrace_profile` anchors (`clip(out, z_join ± cap × d)`) | keeps a profile within cap reach of a hard join pin | a feasibility clip against a pin — NOT changed |
| `road_contact_rows` (§37 (10) (1)) | one-way CEILING `z ≤ z_edge + cap × s` | a ceiling — NOT changed |
| `gate_merged` (`2h / cap`) | two wall witnesses closer than the there-and-back ramp are one gate | feasibility test — NOT changed |
| `_lift` (cap-Lipschitz upper envelope onto the route) | one value per station | geometry of the frame, keeps the cap — NOT changed |
| the floor (`cap_lipschitz_profile`, 13be) | the core clamp: the terrain where it is cap-lawful, the mid-envelope at the cap where it is not | built at the cap where the TERRAIN is over the cap — NOT changed, reported (found-not-fixed 1) |
| `classify/gap_terrace.consistent` / `level_groups` (§55) | two stations are one level when the piece's cap joins them | feasibility test — NOT changed |
| `classify/gap_terrace._lot_cut` (§55, 06d) | `ramp = (L − A) > cap × d_apron`: the lot is every point from which the road's level is still reachable from the apron at the CAP; the rest is the ramp strip | SAME CLASS (the ramp strip is sized at exactly the cap: width = rise / cap) but NOT the same change: it mints faces at classify/late time, the piece's cap is the 10 % groundside-pavement cap, and it re-cuts the HECA gap pieces the owner has not yet read (#430 #292 #358). Reported, not changed (found-not-fixed 2) |

The `road_ramp ramp to the DEM` relaxed rows of the gap lanes are this generator's
target equality (`constraints/road_ramp.RULING`), i.e. the same code.

## S2 — the rule as built

* Law: `emit.toml [road_contact] ramp_grade = 0.05`, checked at load in `(0, road cap]`.
  Its own key, not shared with `[tunnel] ramp_grade`: each stands under its own cap in its
  own table and was ruled on its own evidence.
* `geom/ramp_grade.py` — `least_grade`, `built_grade`: the one arithmetic; `planar/unframed_ramp.
  unframed_top` now calls it (tunnel twins unchanged, 7 pass).
* `airport/road_descent.py` — `descend`: each contact's ramp at its built grade. Run ends:
  the road's own end (route-end group the graph does not continue past) and the next contact;
  need = max over ends of (z_contact − level at end) / graph distance; ends inside one lane
  width ask nothing; over the cap → the cap (today's outcome). One screening pass (ends'
  levels carried UP the road at the design grade) names the contacts that may need more;
  only those are walked. The envelope is made gentlest-first so the max stays exact.
* Stage 2: `_reach_seed` and the terrace bare exit read `_run_grade` (same arithmetic, the
  run they have).

## S3 — twins
`tests/auto_patch_v2/test_road_descent.py` (8), `test_v2roadramp.py` (design / 7.3 % / over cap /
design = cap control), `test_unframed_ramp.py` unchanged.

## S2 addendum — the two cones of a terraced ribbon
After the first replay NLWF read byte-identical: its road is governed by the terrace
profile's COVERAGE-JOIN cone (`clip(out, z_join ± cap × d)`), the fourth site that builds
at the cap. It now reads the built grade too (ends = every bordered level of the route);
a join's pin is the bare run's end level. NLWF's own road still needs more than the cap
(max cut 13.11 m) and so stays at the cap = main: 1 node moved 0.03 m.

## S4 — measured (captures at main e2eec15c on this tree; arm A = the SAME capture replayed
from the main tree e2eec15c, arm B = this tree a0955988; `--from constraints --emit --verify`,
`--workers 3`)

Replay == build on main: arm A bodies equal `/tmp/harness/sw6_*` / `swga_*` at CYXY, NLWF,
KASE, SPJC, KCLT, OTHH (HECA's plain replay has no late gap stage: b8bc5a808fbe).

| airport | body A -> B | §37 (6) ramps >= a lane width, main (10 %) -> now | ramp length main -> now | road refs / nodes moved > 0.02 m, worst | solve-owned airside movers | runway | structure nodes > 0.02 m |
|---|---|---|---|---|---|---|---|
| CYXY | cf8e9e89ec62 = | 1 -> 1 (at the cap: road end 5 m away) | 13 -> 13 m | 0 | 0 | 0 | 0 |
| NLWF | 45ec40e74dcb -> ccd78331ad19 | 1 -> 3 (2 at 5 %, 1 at the cap: next contact 8 m away) | 23 -> 43 m | 1 / 1, 0.03 m | 0 | 0 | 0 |
| KASE | f9b157158a39 -> 5804715b557c | 0 -> 1 (5 %) | 0 -> 6 m | 2 / 2, 0.07 m | 0 | 0 | 0 |
| SPJC | 61f66f149737 -> c6b95f6e06da | 1 -> 1 (cap: next contact 4 m) | 8 -> 8 m | 5 / 8, 0.12 m | 0 | 0 | 0 |
| KCLT | 0b1566de77d5 -> 048297c0e4ef | 24 -> 55 (35 at 5 %, 6 steepened, 14 at the cap) | 231 -> 1,264 m, longest 24 -> 148 m | 55 / 306, 1.04 m (23 refs > 0.3 m, 2 > 1 m) | 0 | 0 | tunnel_ramp 7 (worst 0.13 m, 2 nodes; 5 at 0.02-0.03) |
| HECA | b8bc5a808fbe -> c8cf75281fc6 | 25 -> 44 (37 at 5 %, 2 steepened, 5 at the cap) | 201 -> 753 m, longest 27 -> 57 m | 12 / 66, 0.60 m (4 refs > 0.3 m) | 0 | 0 | tunnel_ramp 13 at 0.03 m |
| OTHH | 73676fda6914 = | 0 -> 0 (flat) | 0 | 0 | 0 | 0 | 0 |

Stage-2 ramps (now): reach-seed runs steeper than design KCLT 7, HECA 5; terrace bare exits
steeper than design CYXY 1 of 1, NLWF 2 of 5, KASE 1 of 2, SPJC 10 of 25, KCLT 18 of 39, HECA 5
of 14, OTHH 0 of 35. Pre-solve targets only ever RISE (KCLT 212 > 0.02 m, max 1.22 m; HECA 118,
max 0.61 m); roads that come DOWN in the patch do so through the join cone (tighter at 5 %).

Census (each arm under its own tree's tool): adjudicated airside identical everywhere;
CRITICAL motion KASE 1 = 1, KCLT 5 = 5, HECA 2 = 2, others 0; `hard_conflict` KCLT 346 -> 335
(airside 55 = 55), HECA build 294 -> 291 (airside 90 = 90); `road_cross_section` CYXY 18 = 18,
NLWF 24 = 24, KASE 14 = 14, SPJC 52 -> 51, **KCLT 767 -> 800 (worst 2.23 -> 2.29 m)**, HECA
replay 487 -> 492, OTHH 3 = 3; `pavement_over_road_cap` KCLT 18 -> 17 (worst 4.47 -> 3.18 m).
Row-side (soft receivers): KCLT 40 nodes worst 0.45 m (graded strips welded to roads), HECA
replay 38 nodes at 0.05 m (pad building10 / building22), SPJC 2, KASE 1, NLWF 1.

## S5 — closing build: HECA `rr484_HECA` (harness, a0955988, 530 s single run; main swga 525 s)
body ad4ef9685c5f -> 7429a5823317. Row-side movers 0, solve-owned 0, runway 0. Roads 14 refs /
67 nodes, worst 0.60 m (dsf:objpav104). tunnel_ramp 13 nodes at 0.03 m. Gap piece
`gap:8/s0/lot` 7 nodes: +2.37 m at two (30.11535802, 31.41080197 and 30.11510995, 31.41089018),
-1.47 m at one (30.11414469, 31.40954132), four <= 0.08 m. These are single nodes standing
off their own piece in ONE of the two arms (main: 101.80 beside route3 at 104.22, and 106.38
among 104.7-105.2; this arm: 100.29 among 98.0-98.2) — an isolated-vertex defect of the gap
piece that both arms carry, at different nodes. Not attributed by an intervention.
Owner sites: #430 (30.1154841, 31.4105884) gap:7/lot alt 96.89..101.49 in both arms; #292
(30.1159784, 31.4106264) gap:7/lot + gap:7/ramp0 92.41..99.73 in both; #358 (30.1193169,
31.4085087) inside gap:0/s4/lot, not a mover. No gap:7 / gap:0 node moved > 0.02 m.
