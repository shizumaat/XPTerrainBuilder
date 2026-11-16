# #2099 R2: the ground beside a grouped mouth's wings is cut to their feet

Lane lwing2099 (Opus), 2026-11-15. Master brief (owner sim read, app 1.0.536): at CYYZ the
ground buries the lower part of a tunnel mouth's wing walls for ~20 m out from the box
(tops still visible). Law: RULINGS 2026-10-22o (connected objects are one group),
2026-11-15 #2099 (mouth groups, spec `2099-mouth-groups.md`), 2026-10-30a (2) (a hard
deck's floor is its frame's bottom), 2026-08-30l (consumer census), 2026-10-05e (no
airport-specific code), 2026-11-13g (drawn gate). Paths under `Ortho4XP/src/auto_patch_v2/`.

## 0. Measured (capture lwing2099/CYYZ.pkl at 36b12e83e; corpus with the 10:28Z small-roads layer)

* The lmouth2099 capture (09:07Z) predates the `+43-080_airport_small_roads` layer
  (refresh ledger 10:28:29Z): it bores no road under T or M (`pm.structures` 2, both
  sunken roads). The new capture reads the tile build's roads: T = an object cut through
  the box (`object-cut:..._T.obj@0`, floor 159.34, no ramp beyond the box: the roads out of
  it are `service_road` ribbons at the DEM), M = a walled deck trench `tunnel:-900@0/@1`
  (floor pre-solve 155.50, ramp level to s 36.8 m then 5 %).
* Feet (lowest solid y of each wing's cross-section, over its zero = the mouth's floor):
  T `_T_b` -0.5 to 40 m, +3.3 at 85, +4.9 at 145, +7.1 at 165 m; `_T` -1.1 to 15 m, +1.4 at
  45, +3.7 at 80, +6.2 at 120, +7.2 at 130 m; `_T_c` -1.3 over its 25 m; M `_M_b` -1.6 over
  23 m, `_M_d` 0.0..0.2 over 15 m. Tops 7.0-7.2 (the taxiway's level).
* Ground at the inner foot, base replay (patch where a face covers it, else DEM; floor =
  the settled deck anchors less their top over bottom): T `_T_b` +7.4 near the box to +1.9
  at 206 m, `_T` +1.7/+5.6 near the box to -2.8 at 141 m, `_T_c` +5.0; M `_M_b` +9.0..+9.9,
  `_M_d` +0.5..+8.6. 6 of 89 samples within 0.5 m.

## 1. The rule (W1-W3)

W1 THE FEET (`planar/wing_cut._feet`): per wing of a mouth group (`airport/mouth_group.
mouth_groups` over the load partition; the planar readers' mouths; every hard deck's
co-placed members `taken` -- they are the deck's own frame, FA's), every `[tunnel.object]
wall_sample_m` along its long axis from the end nearest the mouth: the foot = the
cross-section's lowest solid y (an exact triangle cut), never under the mouth's floor (0:
a footing under the road is buried by design, 20am); the point = its INNER face (the one
nearer the opening axis).

W2 THE REGION (`_ribbon`): from each foot point straight across the opening -- the axis
along the deck's end lines (`_end_line_dir`; a portal's bore), its half-width the deck
ring's (a portal's plan) -- to the far edge. One wall lining a road cuts the road beside
it; a splayed wing cuts the fan between it and the axis. Less the deck ring and the
mouth's plan grown by `[tunnel] wall_gap_m` + the identity spacing (the deck's ground and
end lines keep their law). Its FREE ground (no cell owns it, as `deck_ground`) becomes
`graded_strip` cells `wing_cut:<mouth>[#k]`. Record: `model/wing_cut.WingCut`, published as
`PlanarMap.wing_cuts`.

W3 THE LEVEL (`constraints/wing_cut`): every vertex of the cut's cells and of a groundside
road (value role, `service_road` / lot / pavement) inside the region is held, as the
two-sided pair of the mouth-depth idiom (head `tunnel.mouth_depth_m`, hard), at the
mouth's floor plus the foot under it (`wing_floor_y`: per wing the foot at its nearest
sample, the wings weighted 1/d^2): a hard deck in its own seat -- the end lines' seat set
(`constraints/edge_floor`), `z = 1/2(mean A + mean B) - (1/2(top_A + top_B) - floor_y -
foot)`, the zero the object stage plates the deck (and the wings) at; a row-seated portal
at `floor_z + foot`. Never held: a vertex an airside pavement face or a ramp floor
(value + structure role) carries. A held vertex sheds its DEM pin and road ramp
(`edge_deck.release_governed`, now per generator).

## 2. Consumer census (RULINGS 2026-08-30l)

| # | consumer | reads | ruling |
|---|---|---|---|
| 1 | `planar/structures` (trench ramp / void / rim, knives, skirts) | its own cells | UNCHANGED: runs first; the cut mints free ground only |
| 2 | `planar/deck_bridge.deck_ground` | deck reach | UNCHANGED: runs first; the region keeps off the ring by `wall_gap_m` |
| 3 | `constraints/structures._rim_rows` (rim at the DEM by station) | rim vertices | CHANGED by the post pass: a rim vertex the cut holds sheds its DEM pin |
| 4 | `constraints/road_ramp` (design target, hard ceiling a visual_m above) | road vertices | CHANGED by the post pass: shed on a held vertex (the cut is under the DEM: the ceiling never binds) |
| 5 | `constraints/roads.road_within_shape` (pair caps) | road ring pairs | UNCHANGED: kept; at the region's edge a held vertex meets an unheld one (counted in the relaxed set) |
| 6 | `constraints/edge_deck` span rows (ring + 0.5 m), `_bridge_ground` | deck vertices | UNCHANGED: no cut vertex within the ring's reach; cut cells are not `deck_ground` |
| 7 | `edge_deck.deck_floor` release across the floor | floor vertices | UNCHANGED: no floor vertex is held; the rows name seat and ground vertices |
| 8 | `solve/design_ground` ground datum (soft) | ground vertices | UNCHANGED: the hard pair wins |
| 9 | `constraints/zones.zone_bands` (class by ref), `constraints/strips` | graded_strip | UNCHANGED: no zone class (as deck_ground) |
| 10 | object stage `mouth_group.wing_plates` / `wing_records` | the wings' seat | UNCHANGED: the cut is read in the same seat |
| 11 | emit, census (`check_grade`), `drawn_gate` | patch ways | READ: new `graded_strip` ways `wing_cut:*` |

Emittable: one surface per point (the wall stands at the region's edge; beyond it the
mesh runs to the native ground).

## 3. Not this round

* Portal-led groups (W3 floor_z path) have no witness at CYYZ: twin only.
* A mouth whose box floor and its trench's floor disagree (T: drawn box floor 158.26 vs
  object-cut floor 159.34; M: deck solved 4.7 m under its pre-solve estimate) -- the cut
  follows the BOX's seat (the wings ride it); the trench floor is its own law (#1138 class).

## 4. Result (replays only: ONE-MISS stop, no closing tile build)

Capture `frames/lwing2099/CYYZ.pkl` (36b12e83e, small-roads corpus); base replay = 36b12e83e
code, arm 1 = W1-W3 with a two-way `tunnel.mouth_depth_m` pair, arm 2 (the one fix
iteration) = one-way hard head `structures.wing_cut floor`, every non-airside vertex in the
region held, the ribbon as one quad per station pair, mouth-co-placed pieces `taken`.

Ground at the inner foot vs the floor line (patch where a face covers it, else DEM;
within 0.5 m of the clamped foot / samples):

| wing | base | arm 2 |
|---|---|---|
| T `_T_b` (195 m) | 0/42 (+6.1 near the box .. +1.9 at 206 m) | 31/42 (+0.0..+0.5 from 6 m out; +6.2 at 1 m) |
| T `_T` (131 m) | 5/29 | 17/29 (+1.1..+1.8 within 30 m of the box; -1.2 at 131-141 m: the DEM beyond the wing's end) |
| T `_T_c` (25 m) | 0/8 | 0/8 (+1.2..+6.8: zone and road faces kept) |
| M `_M_b` | 0/6 (+9.0..+9.9) | 0/6 (+8.6..+9.7) |
| M `_M_d` | 1/4 | 0/4 (+6.3..+12.3) |

Airside: the T and M decks solved 0.07 / 0.14 m LOWER in both arms (end lines 166.30 ->
166.22, 159.44 -> 159.30); 359 airside vertices over 0.05 m, worst 0.24 m (43.66892,
-79.61997) -- NOT the cut's pair (the one-way head left the move unchanged); unattributed.
KBNA (`frames/lkbna2`), ENTC, KEGE, KSUN, KBTV captures: no cut forms (BIKF, LICJ, EGNS: no
capture). Bars missed: M's wings (the zone strips and DEM between the splayed wings stay
8-12 m over the box's floor), T near the box (+1.1..+1.8, the footing clamp and the
object-cut floor 1.1 m over the box's bottom), airside unmoved.
