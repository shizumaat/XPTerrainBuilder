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
