# drape229 — base slabs drape over sloping ground (owner RULINGS 2026-10-14d, #229)

Lane notes: the consumer census (RULINGS 2026-08-30l) for the three new
readings, written before the consumers were edited, and the law values.

## The readings

| reading | where | law value (existing unless marked) |
|---|---|---|
| PLATE witness: side-face share of the slab component | `geom/base_slab` rule 5, faces from `airport/slab_faces` | `[placement] base_slab_max_side_share` 0.5 — **NEW, proposed** (a majority); plate face = `[bridge] deck_plate_normal_y_min` 0.7 |
| DRAPE SIDE: level plate with no wall | `geom/base_slab` rule 6 | level = top relief <= `[placement] split_tol_m` 0.3 m (the foot tolerance); "clearly a lot or road" = holds a disc of `emit.road_profile.lane_width_m` 4 m (the gap mint's own floor) |
| PROPORTIONS: road vs lot | `geom/proportions.road_proportioned`, `classify/gap_mint.slab_role` | typical width <= `classify/rules.toml [service] free_max_width_m` 25 m and run >= `[apron] arm_min_aspect` 3.0 widths |
| DRAPE decision: over sloping ground | `airport/slab_drape.drape_plan` | ground relief over the open part > 2 x `[placement] split_tol_m` (no level plate fits within the foot tolerance at every point) |
| up faces that drape | `airport/slab_faces`, `airport/obj8_drape.up_keys` | `n_y >= [bridge] deck_plate_normal_y_min` under the OBJ8 clockwise winding (checked against the authored VT normals: 99.7-100 % agree on six slab files) |

Typical width = 4 x the median interior distance to the boundary: the
inscribed circle (the widest place) reads HECA's `T3_road` 30.6 m at a
junction; the typical width reads it 13.5-14.9 m.

## Consumer census

| # | consumer | reads | with this change | ruling |
|---|---|---|---|---|
| 1 | `classify/gap_mint` | `slab_polygons` | witness with faces: −door c9 (HECA), +20 OB-asphalt + concrete_3 plates (HECA); KCLT, OTHH (pads67 capture), KASE unchanged | the mint stays the single derivation; slab pieces after the pack's (unchanged) |
| 2 | `classify/gap_mint` role | slab pieces | `parking_lot` for lot proportions, `groundside_pavement` for road | late cells: absent from stage 1 by construction (`is_late_ref`) — airside cannot see the role |
| 3 | `classify/evidence` pad mint shades + `CLUSTER_PADS.base_slab_m2` | `pad_shades`, `slab_polygons` | same witness object passed (`witness_faces`); `leaves_pads` false so pads unchanged | none |
| 4 | `constraints/cluster_pad` census shades | `pad_shades` | same witness | none |
| 5 | `pipeline/late_stage`, `gap_terrace`, `gap_follow` | gap piece role caps | a `parking_lot` piece's cap is 5 % (was 10 % soft under the 5 % hard ceiling) | lot law, as ruled |
| 6 | placement `build_splits` -> `_cut_and_file` -> `split_obj8` | member drape set | a member with a draped slab is always WRITTEN (one body included); slab up faces under `ATTR_draped`, kerbs / undersides dropped | bodies, anchors, seats unchanged |
| 7 | `placement_seams`, `placement_census` | written body files | draped tris parse as `draped` (not solid) — no foot, no seam read | none |
| 8 | DSF rows (`dsf_write`) | bodies | no new row: the draped tris ride their body's own file and row | none |
| 9 | harness airport builds | patch + rebake plan | grading changes only; the drape is a TILE-build placement product, proved offline by `obj8_split_report --drape --write-into` | needs-sim-read |

## Not done / open

- Road-proportioned slab pieces keep `groundside_pavement`: the 5 %
  universal pavement ceiling (09-09b (4)) still binds them; "cap 10 %"
  would need them in the road family (`service_road`), whose cross-section
  axis is the minimum rotated rectangle — wrong for a curved road sheet.
- `base_slab_leaves_pads` stays false: slab ground under a pad stays pad.
- Riders on a slab and the road/ramp-foot hold: not changed here (the
  rigid rest keeps its own seat).
