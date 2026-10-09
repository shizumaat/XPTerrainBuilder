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
