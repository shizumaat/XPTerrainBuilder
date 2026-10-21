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
5. **The level.** The lower level is a flat pad held RIGID at the
   object's own lower floor (#1141, owner 2026-10-20: "the bottom road deck
   sits at ground level"; amends the own-ground placement below):
   - `landing_rows` holds every vertex at `z = D + y_lo` against the
     block's datum column — a landing's two-sided row.
   - `ground_z` (the DEM median over the region's AREA, read at the mint)
     stays the #1115 witness only. Measured KATL: on its own ground the
     level stood at 289.45 m, 1.64 m over the object's floor (287.78), and
     the roadway's towers were buried by that much.
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

## §5 THE UPPER LEVEL — the mirror (#1101 / #1099)

Owner answer 47 (2026-10-20 15:46Z, "yes to both"): the pad gets a second,
UPPER rigid level, a storey above the airside level and tied to it, and
landside lots and roads meet it; a lot that touches the apron only across
that object-witnessed storey stays groundside under §27.

### §5.1 Measured (LPHR terminal, 38.521557, −28.716632)

- **The object.** The terminal unit (`lphr_tps_01…06`) stands with its
  grounded parts at y 0 on the apron. Its forecourt parapet (`tps_06`, a
  68 m × 1 m part) runs at y +6.0 exactly along the forecourt `pav2`'s
  68 m contact with the apron (`dsf:objpav0`); the landside columns and
  hall stand at +6.0 too.
- **The pad.** `building1` (1,662 m², held CONFORMING; the cluster reads
  FEET, not STEPPED — so §2's gate never reads it).
- **The defect.** With the apron restored (#1100), §27 flipped `pav2` to
  apron across that contact: 8.96 m under its ground. As a lot it was
  held off `building1` as a §28 (6) hillside and sat at the pad's level
  where it met the apron.
- **The DEM** rises 26.8 → 34 m from the apron to the forecourt but
  smoothly (~2 m across the parapet line, +2.0 m between the pad's two
  rims): it does not witness the storey. The object does.

### §5.2 The rule

1. **The storey** (`airport/unit_storey.py`, one reader for classify and
   planar). A unit's airside FLOOR `t` is the base most of its GROUNDED
   parts (`Part.feet`) within `pad_frontage_m` of airside pavement stand
   at; its UPPER STOREY is its parts authored at least `[building_pad]
   low_level_min_step_m` above `t`, read by their plan footprints.
2. **§27 across the storey** (`classify/storey_edge.py`, called by
   `roles.classify` around `airside_edge_flip`). A contact's run inside
   the weld-widened storey footprint is no apron contact. A lot that run
   alone keeps groundside (≥ `airside_edge_min_m` of it) carries
   `airside_edge_storey_m` and `airside_edge_storey_y` (the most common
   authored rise of the upper parts along the run), and is CUT BACK from
   the airside along its whole airside contact by the pad set-back
   (`groundside_cutback_m` + snap margin): the storey is a riser.
3. **The weld.** `roles._cut_back_groundside` welds such a lot to the pad
   it touches instead of holding it off as a §28 (6) hillside — it meets
   the upper level, not the floor.
4. **The mint** (`planar/low_level.plan_up`, after the lower levels, for
   any HELD pad — conforming too — no lower level split). The pad's strip
   within `pad_frontage_m` of the storey lots it touches, kept
   `pad_frontage_m` + the riser width off the airside and off every other
   pad, is `<pad>/p1` (`kind = "upper_level"`), the riser `<pad>/p1#strip`
   between it and the pad (§2 (4)'s width). A piece narrower than the
   riser can stand beside is dropped; the pad must keep `min_area_m2`.
5. **The level** is the LANDING's rigid row: `landing_rows` holds every
   vertex at `z = D + y` (`y` = the storey's rise) against the pad's datum
   column — "a storey above the airside level and tied to it". No own-
   ground row (a landing's datum is its deck; the DEM does not witness the
   storey). Withdrawn from the pad datum like a landing.

### §5.3 Consumer census (RULINGS 2026-08-30l)

| # | consumer | ruling |
|---|---|---|
| U1 | `classify/airside_edge.airside_edge_flip` / `_lateral_airside_m` | EDITED: `storey=` drops the run across the storey; `storey_cuts=` collects it |
| U2 | `classify/roles.classify` | EDITED: the band, the flip, `knife_storeys` (stat `storey_lots`) |
| U3 | `classify/roles._cut_back_groundside` | EDITED: a storey lot is welded, never §28 (6)-held |
| U4 | `classify/gap_apron` (second §27 caller) | UNCHANGED: no storey (gap pieces are no lots beside a unit) |
| U5 | `planar/overlay.build_arrangement` → `platform_split` → `low_level_split` | EDITED: the storey lots' `(polygon, rise)` ride in |
| U6 | `constraints/platform.landing_rows` | UNCHANGED: an `upper_level` record is a landing (equality at `y`) |
| U7 | `constraints/pads.pad_datum_withdrawn` | UNCHANGED: withdrawn as a landing |
| U8 | `constraints/cluster_pad._split_blocks` (plane groups) | EDITED: a level `/p<k>` is its own plane for a whole-unit pad too (MEASURED LPHR: in `building1`'s cluster group its 46 rigid rows were relaxed and it sat at the floor) |
| U9 | `pad_frontage_level`, `pad_fronting`, `stage_air_vertices`, `block_strip_rows`, `wall_cut._riser_edges`, `placement_read` | UNCHANGED: keyed on the `/p<k>` spelling (§3 rows 7–12) |
| U10 | `pipeline/stage_code`, `O4_Step_Code`, `provenance_code` | EDITED: `airport.unit_storey`, `classify.storey_edge` keyed |

### §5.4 Emittability

As §4: the strip's two rims stand one riser width apart; inside the pad
the terminal's own facade covers it, and along the forecourt's apron
contact the knifed stand-off is the parapet's retaining wall.
