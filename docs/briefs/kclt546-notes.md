# kclt546 — lane notes (KCLT owner sim read of 1.0.387: #546, #547, #548)

Branch `claude/kclt546` off main 66bc72f92. Read build: `tunnel522_KCLT` (body f1b26887fcc3).
Replays: capture `frames/pads67/KCLT.pkl`.

## Finding 1 (#546) — tiny apron shapes nested in apron shapes: ATTRIBUTED

Site 35.2202043, -80.946664 (`osm_site --at … --relate` on `tunnel522_KCLT.osm`): three ways
`-10231` (1.50 m2, 5 nodes), `-10232` (3.01 m2), `-10233` (0.38 m2), role `apron`, ref
`pav14#plateau:building81` (shapeID 223/224/225), every one wholly inside way `-10201`
(same role, SAME ref, 42,419 m2). Levels 221.51–221.62 m against the host's 220.86–221.75:
the apron's own surface, no level of its own.

- What they are: SURPLUS PAD SCRAPS. The stand-zone plateau cut leaves thin pieces of the
  building pad standing in holes of the plateau apron face; `planar/pad_sliver.
  rerole_plateau_scraps` (spec §56 (10) R-F) re-roles each as the plateau it borders but
  keeps it a FACE OF ITS OWN ("LAST, so no merge above reads the new region and no vertex
  leaves the arrangement", `planar/ribbons.py:200`). Emitted, each is a ring inside its host.
- Measured on a planar re-run of the capture (scratch `planar_dump.py` / `pl3.py`):
  `plateau_cut` returns 56 plateau pieces, 1 nested; the finished arrangement has 93
  plateau faces, 35 nested, every one with 0 % of its area inside a cut plateau piece and
  100 % of its perimeter along ONE face of its own ref. `pad_scraps_reroled` = 36 / 203.4 m2.
- Census (apron ways <= 60 m2 wholly inside a larger way; scratch `nested.py`):
  KCLT sw10 14 (1 same-ref) -> sw11 49 (34 same-ref + 1 same-base) = tunnel522 49;
  HECA sw12 6 (3 same-ref plateau); OTHH basins526 8 (2 same-ref plateau);
  KASE 1 (a gap ring, other class); CYXY / NLWF / SPJC 0.
- Purpose: none as faces of their own. They add ring vertices inside the plateau (levels
  the plateau's own), nothing else.
- FIX (branch): `rerole_plateau_scraps` unions a scrap whose WHOLE boundary runs along ONE
  plateau face into that face (the hole closes); a scrap a structure also borders, or two
  plateau faces share, keeps its face as before. Counter `pad_scraps_merged`. Twin
  `tests/auto_patch_v2/test_pad_scrap_rerole.py` (6). DEVIATION from spec §56 (10) R-F's
  "zero geometry change / no vertex leaves the arrangement": needs the spec author's
  ratification (the vertices of an enclosed scrap's ring DO leave).

## Finding 2 (#547) — "a large section of terminal is floating": ATTRIBUTED; scout mechanism REFUTED at these two sites, CONFIRMED at the #519 toll plaza

Both sites stand on / beside pad `building81` (Concourse; 12,388 m2), 36.6 m of apron
`pav14` away from pad `building75` (main terminal). Owner's mesh (his tile, written
2026-10-10 12:27; pack DSF 2530c826, same body file names as the `tunnel522_KCLT` plan):
site A 35.2224352,-80.9472186 = 221.75 m; site B 35.2203395,-80.9466805 = 221.75 m
(plateau 221.60 at the nearest body anchor); file anchor 35.2212296,-80.9433723 = 222.44 m.

- Objects (plan `tunnel522_KCLT.v2/KCLT.rebake.json`, `obj8_split_report --rows-near`):
  site A `Terminals/paredes_5_charlotte.obj` body b0 [building] (19 feet), `paredes_4` b0
  (232 feet), `paredes_2` b0 (87 feet); site B `paredes_1` b1 (20 feet, worst foot 1.14 m),
  `paredes_2` b0. All are members of ONE object unit `fu:6:960@cluster_pad` (42 members,
  116 bodies). Each is RE-SEATED (cut into its own body file, written as an `OBJECT` row at
  its own anchor) with `y_zero -0.69` (site B -0.84): "§16g unit … on pad building75 at
  222.44 (own ground -0.69 m)". Authored base y = 0.00 at every one.
- Mechanism: `footprint_unit.plan_unit_datums` gives a unit ONE zero — the level of the
  pad most of its footprint stands on (building75, 222.44). The terrain gives each pad of
  that unit the level of the apron it stands in (09i): building75 222.44, building81
  221.75, building84 222.70. So every body of the unit standing on building81 is written
  0.69 m above its own pad: 4 bodies / 354 feet at +0.69, 2 / 28 at +0.84; 3 bodies / 242
  feet 0.46 m LOW on the other side.
- Before the pads merge (`sw10_KCLT`): building75 221.02, building81 220.62 -> +0.40 m at
  the same bodies (under the 0.5 m visual bar). `sw11_KCLT` = `tunnel522_KCLT`: +0.69.
- INTERVENTION (scratch `planarm.py`: the build's own screen through
  `rebake_screen.build_plan`; base arm byte-identical to the build's plan; arm = `excluded`
  emptied, so `paredes_11` / `paredes_6` are planned like any member): the bodies at sites
  A and B are UNCHANGED (`y_zero -0.69`, same unit, same zero). The whole-file skip is not
  what floats these two sites. Within 60 m of either site the two skipped files have no
  ground-contact component at all (only roof parts at y >= 12 m).
- The skipped files (`dsf:obj6216 paredes_11`, `dsf:obj6209 paredes_6`, both authored
  `OBJECT` rows at the file anchor): `paredes_11` has 387 ground-contact components riding
  222.44 — over the owner's mesh 200 float > 1 m, 81 are sunk > 1 m, 48 within 0.3 m.
  Toll plaza 35.2235078,-80.9427104: mesh 217.92, components +4.46 .. +4.90 m (confirmed).
  In the no-exclusion arm the plaza's components become bodies of their own on their own
  ground (b14 / b32 / b33 / b34 / b35). So the scout's mechanism IS the toll plaza's (#519).
- NOT FIXED. (1) Sites A / B: an intent question (below). (2) Per-component exclusion for
  the toll plaza: not a one-site change — a component dropped from the plan is an ORPHAN
  the writer hands to the nearest body or seats on its own ground
  (`placement_orphan`), i.e. it would be re-seated; keeping only the well's frame on the
  authored row needs a body class "kept at the authored row's seat" in the plan and the
  writer (object-placement spec §18 territory).

## Finding 3 (#548) — "tunnel ramp" at 35.2214617,-80.9460653 and the "tiny arm": ATTRIBUTED

- Patch (`tunnel522_KCLT.osm`): way `-10904` role `tunnel_ramp` (18 nodes, 216.46 -> 220.84 m,
  about 7 m wide, 120 m long) inside `structure_rim` `tunnel_wall` way `-11717`
  (220.82..225.51). Owner's mesh at the site 217.80 m; the pad beside it 222.44 m: a
  trench up to 5.1 m deep.
- Structure record (dry `--stage structures`): `tunnel:-32111+-27411@0`, source `osm`,
  mouth 35.2212937,-80.9458207, mouth DEM 221.60, mouth_z 216.50, 5 % for 120 m along the
  approach road `-27509` (`highway=service lanes=2`). The other mouth `@1` is refused
  ("the mouth stands against building pad building75").
- Bore: OSM ways `-27411` (293 m straight, `highway=service tunnel=yes`, no layer) +
  `-32111`, 312.9 m, running east under the terminal. ADMISSION WITNESS (scratch
  `bore_witness.py` around `structure_service.terrain_tunnel_witness`): §34 (12) (5) (c)
  "under the classified cover for 273.0 m". Neither end is inside a pack building. The
  cover is pad `building75` — the terminal's own footprint. The engine's own 10i (1)
  reading, asked of this bore, ALREADY answers "an elevated pack part
  (`Terminals/paredes_8_charlotte.obj`, base 3.03 m) stands over the carriageway and no
  pack part at grade covers its line" — it is never asked, because the cover witness runs
  first.
- The pack (authored files, read-only): over the bore `Terminals/techos_1_charlotte.obj`
  component 8 (360 x 133 m, y -0.10 .. 6.07) is a road deck 6.02 m over the terminal's
  zero (mesh under it 222.44 = the pad): the lower roadway runs AT GRADE under the
  departures deck. The same component is the up-ramp: its surface stands +1.77 m at the
  owner's site, +4.99 m at the "arm" point and +6.02 m at the bore's mouth. It rises above
  grade all the way; nothing in the pack is below grade here.
- WHY THE ENGINE CUT DOWN: a mapped `tunnel=yes` bore "under cover", where the cover is the
  pad of the elevated deck itself.
- THE "TINY ARM" 35.2215158,-80.9458896: not a structure. It is an arm of pad
  `building75` (way `-11019`, 222.44 m): within 40 m of the point the pad is a strip of
  mean width 1.15 m (109 m2 along ~95 m) — the outline of the ramp's at-grade edge, held at
  the pad level. The ramp object over it is elevated, so only its ground-contact edge
  founds a pad. It does not go with the bore fix (it is the pad outline's thin-piece
  question).
- TWO FIX ITERATIONS, BOTH MISSED, CODE REMOVED (attempt cap 2):
  (1) where the pack reports the passage (10i (1)'s own `_PackBuildings.passage`), the
  PADS' share of the bore's cover is not counted: cover 273.0 -> under 1.0 m, and the bore
  is then admitted by the NEXT witness, "the ground over it stands +0.82 m above its mouth
  chord" (law 0.5). (2) the DEM under those pads discounted too: "+0.55 m above its mouth
  chord" on the ~40 m of line outside the pads — still admitted, by 0.05 m. Verdicts at
  KCLT / HECA / SPJC / KASE / CYXY / NLWF on that code: 0 bores changed (OTHH not finished).
  So no rule that only re-reads the cover or the rise refuses this bore; what refuses it is
  the pack's passage reading OUTRANKING the cover and rise witnesses — a question of
  precedence between the pack and the DEM, the owner's (below). HECA witness for the
  bound: three bores (-20899, -19181, -3949) report a pack passage too
  (`Airport/T23/concrete_2.obj`, base 2.63 m) and are real tunnels admitted by
  `layer -1` — a passage rule must stay under the layer witness.

## Replay pair (finding 1 fix only) — `frames/pads67/KCLT.pkl --from planar`, base = main 66bc72f92 (worktree `kclt546base`), fix = this branch

- `pad_scraps_reroled` 36 / 203.4 m2, `pad_scraps_merged` 33 (3 keep a face: not enclosed
  by ONE plateau face). Nested apron ways: same-ref 34 -> 1, all classes 49 -> 16 (the 13
  "plateau in a building way" + 1 "plain in a building way" are the pre-existing other
  class: apron pieces standing in holes of a PAD, sw10 already had 12).
- Owner site 35.2202043,-80.946664: 3 ways at 0.00 / 0.00 / 2.00 m -> no way within 15 m.
- `airside_value_delta` base -> fix: 109 row-side vertices REMOVED (all plateau-ring
  vertices), 0 added. Movers > 0.01 m: 60, worst 0.03 m — RUNWAY 0; taxi family 28 (worst
  0.03 m at 35.22115978578,-80.94870148143; three at 0.03, the rest <= 0.02); apron 23
  (worst 0.02 m); strip 7 (0.01 m). Structure frame: 299 nodes both arms, 0 moved, 0
  added / removed.
- Other airports, dry planar read of the registered captures (`--from planar --pad-read`):
  HECA re-roled 3 / merged 3 (0.4 m2); OTHH re-roled 7 / merged 3; SPJC re-roled 1 /
  merged 0; KASE, CYXY, NLWF 0 / 0. So the bodies of KCLT, HECA and OTHH change; SPJC,
  KASE, CYXY, NLWF do not. No object plan changes (no object-stage code touched).
