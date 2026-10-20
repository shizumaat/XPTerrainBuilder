# THE LOWER LEVEL OF A STEPPED UNIT'S PAD (#809)

Owner RULINGS 2026-10-19ai (amends the 2026-09-30r flat-pad cut; follows
2026-10-19y). "Where an object carries its own one-storey step, its rigid
pad gets a second, lower level along that step, tied to the airside level,
and landside roads meet the lower level."

A narrow first implementation of the base-profile spec's §2 (1) plane pads
(`building-base-profile-spec.md`; that spec's census C1–C25 is the
superset). It reuses the `<ref>/p<k>` grammar, the block strip, and the
landing registry and rows. It adds no column class and no generator.

## §1 Measured (KATL east terminal, 33.641271, −84.416453)

- **The pad.** Held block `building31/b0` (79,176 m²) sits flat at 300.76 m.
- **The ground under it.** The DEM under it spans 288.2–302.4 m. Over the
  71,302 m² footprint of the unit's low parts the median is 289.5 m; over
  the remaining 6,164 m² by the apron it is 301.2 m.
- **The object.** The unit `terminal_F` (cluster `unit:23#2`, base
  STEPPED) has its frontage parts at authored y 0 and its landside parts
  at y −13.
- **The anchor.** It is right (19y): the zero is the pad's median, 300.76,
  and the lowest feet land at 287.7, against the lowest ground under the
  terminal of 288.2.
- **The defect.** The landside roads share the block's rim and rode up
  4–11 m.

## §2 The rule (`planar/low_level.py`, called last in `platform_split`)

1. **Which pads.** A held, non-conforming pad is read only when its unit's
   composed base is STEPPED (`pad_blocks.unit_base`). The unit is the one
   pack unit holding the most part centres inside the pad.
2. **The top level.** `t` is the most common rounded base y among the
   unit's parts that touch the frontage band (airside within
   `pad_frontage_m`). A canopy trim above that floor or a sill below it
   does not count.
3. **The low region.** Take the unit's parts whose base y is at most
   `t − [building_pad] low_level_min_step_m` (3.0 m, one storey). Union
   their footprints inside the pad and close the union by
   `pad_frontage_m`. Then remove:
   - the airside, buffered by `pad_frontage_m` (the frontage stays high);
   - every other pad, buffered by the riser width (two pads keep two
     floors, so no vertex is shared).

   Pieces under `min_area_m2` are dropped. A total under `[placement]
   cluster_pad_min_m2` (5,000 m², the unit-pad bar) mints nothing.
4. **The mint.**
   - The high block keeps its ref.
   - The low region becomes `<block>/p1`.
   - Between them runs a riser strip `<block>/p1#strip`, of width
     `max(identity spacing, 2 × grid)`.
   - `<block>/p1` is registered in `Registries.landings` with
     `kind = "low_level"`, `y_lo` = the lowest low part − `t`, and
     `y_hi = −low_level_min_step_m`.
5. **The level.** The lower level is a flat pad on its own ground:
   - `ground_z` is the DEM median over the region's AREA, read at the
     mint. The ring mean would read the slope up to the block.
   - `landing_rows` states one soft own-ground row on the pad's mean, at
     the `frontage_level` head's `pad_flat` price, and a hard band against
     the block's datum column, `D + y_lo ≤ z ≤ D + y_hi`.
   - The lower level is a stage-2 pad, so it is left out of
     `stage_air_vertices`.
   - It fronts nothing: `pad_frontage_level`, `pad_fronting` and
     `pad_datum_withdrawn` skip it, and the cluster plane group keeps it
     out of its block's group.
6. **The riser** is the object's own storey: the steepest cell and no 1:3
   rows (base-profile §8a Q2). `block_strip_rows` skips a lower level's
   strip, and the design's bending skips every edge across it
   (`solve/wall_cut._riser_edges`, beside the declared wall's cut).

   Measured on the gap-free base map (the build's first map, where no
   road holds the lower level):
   - without the bending cut, the lower level stood at 291.4 m;
   - without its own ground, at 294.9 m;
   - folded into the block's plane group, at 297.7 m (the band's top);
   - with all of them in place, at 289.6 m.

## §3 Consumer census (RULINGS 2026-08-30l)

| # | consumer | ruling |
|---|---|---|
| 1 | `planar/platform.platform_split` | EDITED: calls `low_level_split` after `landing_regions` (which clears the registry) |
| 2 | `planar/pad_blocks.plan_blocks` / `bisect_blocks` | UNCHANGED: the frontage cut runs first; the low split runs inside a held block |
| 3 | `planar/landing.landing_regions`, `landing_cut` | UNCHANGED: `landing_cut` cuts a lot under the lower level as under a landing (no lot under KATL's) |
| 4 | `model/planar` grammar | EDITED: `plane_origin_ref` (a `/p<k>` with k ≥ 1, and its strip, fold to the pad before `/p`); `plane_of` / `unit_ref_of` unchanged |
| 5 | `model/registries`, `pipeline/capture_state` | UNCHANGED: the record rides in `landings` (`kind`) |
| 6 | `constraints/platform.landing_rows` | EDITED: a `low_level` record states the band, a landing its equality |
| 7 | `constraints/platform.block_strip_rows` | EDITED: a lower level's strip carries no 1:3 rows |
| 8 | `constraints/platform` hold / contacts / datum (`unit_pad_faces`, `_contact_sets`, `hold_sets`, `datum_vertices`) | UNCHANGED: keyed on held refs; the lower level is not held |
| 9 | `constraints/pads` (`pad_flats`, slope ceiling, `pad_datum_withdrawn`, `pad_frontage_level`) | EDITED: `is_lower_level`; the lower level fronts nothing and is never withdrawn; flat and slope rows apply as to any pad |
| 10 | `constraints/no_step` | UNCHANGED: airside pairs only |
| 10a | `constraints/cluster_pad._base_ref` (plane groups) | EDITED: a lower level is its own plane group, never its block's |
| 10b | `constraints/pad_fronting` (facing across bare ground) | EDITED: a lower level faces nothing |
| 10c | `model/platform.stage_air_vertices` (§20b stage 1) | EDITED: a lower level and its strip are stage 2 (base-profile C14) |
| 10d | `solve/wall_cut.wall_cut_edges` (the bending) | EDITED: `_riser_edges`, the bending skips the riser |
| 11 | roads (`road_ramp`, road terrace, `pad_frontage_gs`) | UNCHANGED: a road sharing the lower level's rim takes its level, as it took the block's |
| 12 | `airport/placement_read.pads_rims_from_graded_doc`, `_banks_as_platform` | EDITED: the lower level and its strip are published under the BLOCK's ref at the block's plane, so the unit is seated as one body at the airside datum (the 19y anchor). `pad_plurality`, `plan_unit_datums`, `pad_block_seat` are then unchanged |
| 13 | `pipeline/publication._landings` | UNCHANGED: the sidecar lists the lower level (`deck` None) |
| 14 | `classify/ramp_runout._landing_faces` | UNCHANGED: reads the `/landing` spelling only |
| 15 | census (`check_grade` bank ways `#strip`, `pad_flat`, `within_shape`, `platform_rim_relief`) | UNCHANGED readers; measured on the closing build |
| 16 | `pipeline/stage_code`, `O4_Step_Code` closures | EDITED: `planar.low_level` keyed |

## §4 Emittability

The strip's two rims stand 1 m apart (the riser width), the wall-gap form
(RULINGS 2026-09-01c); the object's facade covers it.
