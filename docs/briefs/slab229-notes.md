# slab229 — notes (issue #229 / #519: a flat plane at the base of objects is pavement; RULINGS 2026-10-10o (B), 02v (3b), 12k (2), 13b (3))

## RESUME HERE
* Branch `claude/slab229` (worktree `.claude/worktrees/slab229`) off main bd950d682.
* Scratch `<scratchpad 466e18b3…>/slab229/`: `witness_g2.py PLAN GRADED` (the witness over a rebake plan, with the
  graded face roles under each open part), `capslab.py CAP.pkl` (the engine witness on a capture's partition),
  `cap/{KCLT,HECA}.pkl` (captures at this branch with `--placement base_slab_min_m2=0`), `two.sh TREE OUT ICAO`
  (the build's two stages on one capture: `--gap-free` base then `--late-from`), `rp/<ICAO>_{main,slab}/`.

## The code (one derivation site, two readers)
* `geom/base_slab.py` — THE WITNESS, per component of the load-time partition (`Airport.partition` Parts):
  ground feet; |lowest authored y| <= `base_slab_base_y_max_m` 0.5; solid height <= `base_slab_max_height_m` 2.0;
  OPEN part = outline minus every other part ring of the partition (any unit: walls, roofs, upper floors, booths);
  open >= `base_slab_min_m2` 300 and >= `base_slab_open_min_share` 0.25 of the outline; TOUCHES a walled part
  (`chain_min_height_m` 2.5, within `footprint_touch_m` 0.5) of any unit — the plane at the base of objects.
  `pad_shades` = deck shades + slab open parts; `slab_polygons` = the slab sheets.
* Pad side (10o (B) "never a reason to fuse into one pad"): `classify/evidence._cluster_pads` (mint), the fallback
  footprint trim (`evidence` :670), `constraints/cluster_pad.cluster_polys` (census) all read `pad_shades`.
* Pavement side: `classify/gap_mint.mint_gap_pieces` appends `slab_polygons` to the gap sheets — graded groundside
  pavement (apron where it touches an apron without road evidence, 08c (6)/08g), following the standing levels
  across the stand-off (`constraints/gap_follow`).
* Law: `structures.toml [placement] base_slab_*` + `law/rebake_schema.py`; `law.tables.base_slab_law`.

## Consumer census (scout, main bd950d682; every pass that reads object-pavement / slab / pad geometry)
| # | reader | reads | what it does with an admitted slab (this branch) |
|---|---|---|---|
| 1 | v1 `auto_patch/object_footprints.structure_footprint_parts` -> footprint cache | union of a contact structure's triangles | UNCHANGED (cache is v1; one ring per structure, no component identity) — trimmed downstream by #9 |
| 2 | `airport/load.py:604-618` `dsf:object*` Buildings | cache rings | unchanged |
| 3 | `load.py:631-640` pad_union -> `object_pavement.read_object_pavements` | cache pads clip draped bodies | unchanged (slabs are SOLID; never draped bodies) |
| 4 | `object_pavement` draped / hard-plane / gap-sheet gates | per resource | unchanged — a solid slab fails every gate there; admitted downstream instead |
| 5 | `load.py:643-663` gap-sheet naming | `Airport.gap_sheets` | unchanged; slabs join at the mint (#23) |
| 6 | `classify/evidence._dsf_pavements` | `dsf:` pages | unchanged (slabs are not sources) |
| 7 | `classify/sources` object-body cuts | `dsf:objpav*` | unchanged |
| 8 | `classify/evidence._cluster_pads` -> `geom.cluster_outlines(shades=)` | cluster rings | slab open part SUBTRACTED (as a deck shade is) |
| 9 | `evidence._pads` fallback trim | cache rings | slab open part SUBTRACTED before the cover test (so a cache ring cannot re-admit it) |
| 10-12 | `pack_partition._build_member`, `contact.placed_parts`, `rebake.Part` | per-component parts | unchanged — the slab stays a seated part of its body (its riders keep their carrier) |
| 13-16 | `placement_family.bodies_of_plan/plan_clusters`, `sheet_chain`, `footprint_unit` | bodies / units | unchanged; the outline is trimmed at #8 (the deck-shade site), not per consumer |
| 17-18 | `planar/cluster.clusters`, `constraints/cluster_pad.cluster_polys` | clusters | census reads the SAME `pad_shades` (no `pad_cluster_mismatch` from it) |
| 19-22 | `placement_read.pads_rims_from_graded_doc`, `pad_block_seat`, `footprint_seats`, `anchor_rule.anchor_for`, `placement_carrier` | graded doc, unit datums | unchanged code; a body on the slab reads the graded surface under its feet; a body bound into a pad unit keeps the unit datum |
| 23 | `classify/gap_mint.mint_gap_pieces` | gap sheets | slab open parts APPENDED as sheets |
| 24 | `classify/pad_touch`, `roles._cut_back_groundside`, `planar/weld.weld_cells` | source cells vs pads | not applied: a gap piece stands off a pad and follows its level (deviation from 10o's "weld as to any pavement", see below) |
| 25 | `constraints/pads.*`, `pad_frontage_gs`, `pad_ramp` | shared rims | unchanged |
| 26 | `constraints/gap_follow`, `pavement_cap`, `pipeline/late_stage` | gap faces | grade the slab pieces |
| 27 | `pipeline/build.py` say-lines, `verify/pads.pad_flat` | counts | `cluster pads` dict carries `base_slab_m2`; gap mint stats `base_slab_sheets/_m2` |

DEVIATION (for the master): 10o says buildings beside the slab weld to it "as to any pavement (09j)". Through the
gap-sheet path (09a, the path 10o names) a piece stands off a pad by the set-back and is bound to the pad's level
within cap x distance from it (`gap_follow`), which is the gap path's weld; it is not a shared-rim weld.

## The witness at the seven sweep airports (r5b plans: KCLT HECA OTHH SPJC KASE; sw23: CYXY NLWF)
`witness_g2.py` (plan) and `capslab.py` (the engine function on the captures) — admitted open parts:
| airport | admitted | open m2 | what | refused by the touch rule (no walled part within 0.5 m) |
|---|---|---|---|---|
| KCLT | 3 components / 8 pieces | 26,643 | `techos_1` comp 8 (the forecourt, 23,110 m2 outline), comp 10, `suelos_interiores` comp 45 (36,295 m2, open part mostly already apron) | — |
| HECA | 17 components / 24 pieces | 39,458 | `T23/T3_road` comp 0, `T23/side_walk` 0/1, `T23/door` 9 (on apron), `Hangar_Tower/concrete_1` 16, twelve `ground/OB-asphalt_2/_3` planes | 21 `OB-asphalt` planes, `Private_hall/concrete_3` 49 |
| OTHH | 4 | 4,821 | Emiri Terminal 17 / 17_03 plates (already groundside pavement), MedicalCenter_3 comp 6 (on apron/strip), 16L ILS dock 358 m2 (no face) | two Emiri 16 plates |
| KASE | 0 | 0 | — | `Aspen_Rockwall` (509 m2, 29 % on apron), `Aspen_Hexagons_1` plaza |
| SPJC, CYXY, NLWF | 0 | 0 | no candidate (CYXY has no pack units) | — |
FALSE POSITIVES / NEGATIVES read by hand: suelos comp 45 is named "interior floors" but its open part (not under any
roof ring) lies 93 % on the apron already — inert. The OTHH ILS dock (358 m2 on no face) is a slab under a walled part
of its own object (a dock, not a road) — admitted, a candidate false positive (it mints nothing if the strip band
knife takes it). Real building pads: a floor under its own roof is never admitted (the cover rule; twin).

## Arm ON (slab leaves the pads too) — MEASURED, then put behind `base_slab_leaves_pads` (OWNER-PENDING, off)
Replays on captures `cap/{KCLT,HECA}.pkl`, main bd950d682 vs branch, two-stage (`two.sh`):
* KCLT: pads 331,712 -> 331,706 m2; 14 solve-owned airside vertices moved (apron pav14 near building84, worst
  0.12 m) — a slab piece minted as `gapapron` (fixed since: slab pieces are never apron-judged).
* HECA: building15 (hangar-tower pad, 30,332 m2, 97.74 m) splits in three (2,259 + 4,165 + 20,865 m2) at -0.07 m;
  building10 (2,046 m2, 102.91 m) GONE; building11 1,580 -> 249 m2 and +1.17 m; building22 -3.40 m; building8
  +0.28 m; the T3 pad building4 -0.07 m; 1,951 solve-owned airside vertices worst 0.20 m (strip 321, taxi 704, apron
  926). Bar "airside 0 movers" missed -> the pad side waits for the owner.

## Arm shipped (pads untouched; slab = groundside gap pavement) — replays vs main
* KCLT: airside 0, structures 0, pads 0 (100 = 100); +4 groundside pieces; pad roads `-11471` / `-8197` move
  1.73 m (they follow the new pieces). Ground under the forecourt slab `techos_1` comp 8 (slab rendered ~222.6 m):
  median 221.19 -> 222.51 (3,501 m2 piece) and 221.33 -> 222.40 (4,256 m2); the 311 m2 piece 220.53 -> 222.69;
  comp 10 220.47 -> 222.60. Object feet within 200 m of 35.2216,-80.9440: floating feet 134 -> 84, floating
  bodies 15 -> 9; worst +3.15 m unchanged at 35.2221531,-80.9425076 — a pad road (`-8197`) ramping 222.68 -> 219.88
  off building75 under the slab's edge (the ramp leaves the PAD's rim, not the slab's: see NOT DONE).
* HECA: airside 0, structures 0, pads 0 (one collar `building4/landing4#collar` +4 m2 of ring, no vertex > 0.02 m);
  groundside: 10 gap refs (196 nodes, worst 3.59 m `gap:5/s0`), 58 service-road refs (301 nodes, worst 4.43 m
  `small_roads:-18868` 3 nodes). Ground under the slabs: T3_road comp 0 median 96.88 -> 98.18 and 96.91 -> 100.06,
  side_walk 98.20 -> 99.99 and 98.65 -> 100.12, OB-asphalt_2 c5 96.73 -> 99.31, OB-asphalt_3 c100 98.32 -> 100.65;
  slabs on pads/apron/lots unchanged.

## CLOSING (harness builds at 9cd2b852b, tags `slab229_<ICAO>`, vs `/tmp/harness/sw24_<ICAO>` = main bd950d682)
* Movers > 0.02 m: row-side, solve-owned airside and structures 0 at KCLT, HECA, OTHH. Rebake plans byte-IDENTICAL
  (the plan carries parts, not the graded levels; the seat is read at the object stage). Groundside: KCLT +4 gap
  pieces, 5 service-road refs / 32 nodes worst 1.73 m (`small_roads:-11471`, `-8197`, pad roads beside the
  forecourt); HECA 10 gap refs / 196 nodes worst 3.59 m (`gap:5/s0`), 58 service-road refs / 301 nodes worst 4.43 m
  (`small_roads:-18868`, 3 nodes), 6 road refs only in sw24 (re-cut by the new pieces); OTHH +1 piece (`gap:131`,
  ~290 m2 at the Emiri terminal, 3.96 m flat), `gap:2/s6#1` -> `gap:2/s7/#1` (re-cut), 0 moved values.
* Object zeros (obj8_split_report on each build's own plan + graded; body matched by placement + components; > 0.05 m):
  KCLT 1 (`Paredes_7` b at 35.222027,-80.945939 +0.77 m, now carried by the forecourt slab body); HECA 31 (worst
  OB-asphalt_2 body +3.49 m at 30.113214,31.396678, door/metal_strip/titles +2.42 m at 30.115389,31.406660,
  OB-asphalt_2 +1.47 at 30.115029,31.406040, OB-asphalt_3 +1.21 at 30.113009,31.395105, the rest <= 0.73 m);
  OTHH 2 (`OTHH_TerminalRoads_03_003` dsf:obj8721 b0 -1.62 m and its CLUTTER rider -0.90 m at 25.257546,51.612392
  — the surface under it is unchanged (3.96 m both), its low-side-foot y0 -3.169 -> -1.552: NOT ATTRIBUTED; the
  object-stage report is deterministic on one surface, and main's code on this branch's surface gives the same move,
  so the 290 m2 Emiri piece ~900 m away re-orders the object stage's reading).
* §7 feet census: KCLT floating 1816 -> 1767, buried 917 -> 916, >3 m 22 = 22; HECA floating 8535 -> 8475, buried
  14032 -> 14052, >3 m 493 -> 517; OTHH floating 5171 -> 5131, buried 5366 -> 5377.
* Law-true census totals: KCLT 17857 -> 17872 (road_cross_section 950 -> 941, hard_conflict 321 -> 335 (groundside
  288 -> 302), hairline_pair 2063 -> 2073); HECA 58599 -> 58533 (within_shape 46061 -> 46034, road_cross_section
  1363 -> 1331, terrace_actual_step 23 -> 29, mid_edge_step 72 -> 60, hard_conflict 701 -> 706, plane_gradient 10 ->
  11, pavement_over_road_cap 35 -> 36); OTHH 2448 -> 2430. Airside columns unchanged at all three.
* #519 TOLL PLAZA (35.2235078, -80.9427104): on main (sw24 / r5b) its bodies `paredes_11` b28 / b30 are their own
  host unit seated "on its median ground at 219.27 (own ground -0.03 / +0.00 m)" on pad road `small_roads:-28429`
  — no longer floating; unchanged here. The +3.86 m connect549 read was the FORECOURT SLAB's foot (`techos_1` b0),
  which this round grades under (ground under the slab median 221.2 -> 222.5 m against the slab at ~222.6 m).
* Frames registered (`frames.py list KCLT|HECA|OTHH`, lane slab229): captures KCLT/HECA, the three patches.

## NOT DONE
* The pad side (slab leaves the pads it lies under): built, MEASURED, OFF (`base_slab_leaves_pads`), owner question.
* Pad roads that cross a slab ramp from the PAD's rim (KCLT `-8197` 222.68 -> 219.88 under the forecourt slab's
  edge, foot +3.15 m at 35.2221531,-80.9425076): under 13a (2) the slab is the plateau the ramp leaves from. The
  ramp is `constraints/pad_ramp.py` / `classify/pad_road_exit.py` (lane crossfall609's files) — not touched.
* A slab welded into a walled body keeps that body's seat (the terminal unit's datum); a slab not under a pad is
  graded toward the slab's level only where the gap follow allows (the piece follows its fixed neighbours across
  the stand-off). No per-body cut of a slab from its building.
* The gap piece stands off a pad by the set-back and follows its level (`gap_follow`) — the gap path's weld, not a
  shared-rim weld (10o "weld as to any pavement").
* OTHH object move above: not attributed.
