# wells551 — no pit at the jetways (#551)

Branch `claude/wells551` from main 4b60e97ed. Reference: `/tmp/harness/basins526_OTHH.*` (45 basins,
35 from `Jetway/OTHH_Jetway_Type*.obj`), replay base = the basins526 lane's `g_planar` replay of
`pads67/OTHH.pkl` (main's code).

## 1. The owner's question — what in the jetway object made the engine cut a pit

Each jetway OBJ carries a SERVICE ROOM under the rotunda, modelled in full (`<scratch>/wells551/
comp_probe.py`): a floor plate at y −4.27…−4.31 (20–39 m² of horizontals at depth, 0.26–0.48 of the
41–76 m² footprint), a staircase from +1.0 down to −4.3 (steps 0.15 m apart), ducts and equipment
(~1,300 welded components), the room's ceiling AT the apron. The DSF row is a plain `OBJECT`.
Rule 1 (`airport/obj8._read_placement`, per component) admits a thick solid whose floor is ≥ 2.5 m
under the ground and under its own datum, with a |n_y| ≥ 0.7 plate, whose shell tops out within the
1 m contact band of the ground (`rim_reaches_grade`); `through_grade` refuses only a COMPONENT rising
through the ground. The room passes exactly like a pit (its ceiling is at grade); the 9 m rotunda
above is other components. The 35 "pits" are 4.8 m cuts to the room floor + 0.5 m.

## 2. The two populations (`pop_table.txt`, `lid_table.txt`)

| population | row | plate y | solid top y | top/depth | pack cover above the band |
|---|---|---|---|---|---|
| Drainage 01–05 | OBJECT_AGL +4.30 (kept, §18) | −3.82 | +0.06 | 0.01 | 0.00 |
| Drainage 06 (incl. walled sump basin:9) | OBJECT | −4.20 | +0.06 | 0.01 | 0.00 |
| Dewatering 01 / 02 | OBJECT_AGL +13.50 / OBJECT | −13.14 | +5.35 | 0.41 | 0.02 |
| Jetway Type4–8, 10 (35) | OBJECT | −4.27…−4.31 | +9.01 / +9.34 | 2.09–2.17 | 0.26–1.00 |

Candidates: (a) own lid — refuted (the Drainage sumps have a grating at +0.06 over 100 % of the
plate; real pits); (b) the author's lift — refuted alone (Drainage 06 / Dewatering 02 plain rows,
real pits); (c) pack cover ≥ 0.5 (the existing diagnostic key) — 34 of 35, basin:75 at 0.26 survives;
(d) DEPTH vs HEIGHT: pits 0.01–0.41, wells 2.09–2.17, a ×5 gap with only 1 in it — chosen, no number.

## 3. What landed

`obj8._read_placement`: after the component loop, a placement with witnesses whose solid top
(`base + max component max_y − anchor ground`) exceeds its deepest plate's depth is STANDING ON THE
GROUND: witnesses dropped, `ObjReport.standing[path] = (n, top, depth)`; `_absorb` merges it;
`planar/basins._no_floor_refusals` prints it. Classify-time membership and the plan's below-grade
skip read the same answer. The 04i basement test stays as the second line (its m4b twin amended:
a building 8 m over a 5 m basement is now refused at the read). Twins: `tests/auto_patch_v2/
test_wells551.py` (open pit cut; building on its own basement refused; pit under another object's
canopy stays). Spec §47 (8); `[basin]` comment in structures.toml.

## 4. OTHH replay (pads67 capture, `--from planar --emit`): 45 → 10 basins (the 35 jetway wells
removed by design, listed in the spec); 15 authored seats identical; node movers vs the main-code
replay: 0 (every common node within 0.01 m); the removed rings' nodes are the only-base nodes.
