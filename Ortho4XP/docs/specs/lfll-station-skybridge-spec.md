# LFLL station: the skybridge group, the trench's lower pad, bridges and tunnels (#1333)

Owner, 2026-10-25 (LFLL), verbatim: "the train station is connected to the
terminal by skybridge and should stay with that group, and receive a second
lower pad so the rail cut stays consistent as it passes the airport. Several
bridges and tunnels are not seated or cut correctly either." Approved for beta 5
on 2026-10-28.

LFLL is where this was seen and is the closing test. The rules below apply to
every airport (RULINGS 2026-10-05e).

## 1. What the issue asks, and what already covers it

| # | Ask | Existing mechanism | State on main (b8c456c9) |
|---|---|---|---|
| 1 | The station joins the terminal's group through its skybridge | §16g footprint chain at `[placement] touch_m`; one zero per connected unit (22o, #1146/#1470); airside wins (23e); one shared frame, own-ground pieces move with what they touch (28p (2)) | **Already the case.** The pack authors every LFLL object in ONE frame (anchor 45.725461, 5.081976). The skybridge pieces `TGV_LY_21` / `TGV_LY_02` / `TGV_LY_32` (deck, y +0.33 to +0.40) run from the station east to lon 5.0790, where `T2_LY_29` / `T2_LY_30` start (5.07874). The partition chains the station, the skybridge, T1 and T2 into one footprint unit (`unit 3`; the owner's 1.0.43x plan of 2026-10-24: one group `fu:3:19` at 238.97 m, 1,989 bodies, 359 of them `TGV_LY_*`). No new rule. The witness the issue asks for (a bridge object whose footprint touches both buildings) is the existing 22o chain. |
| 2 | A second, lower pad at the rail's grade so the cut runs at one depth | Two pads per two-level group (23b/23c), lower level depth from the objects (27h), lower levels `planar/low_level`, `planar/group_low`, `planar/low_extent` (#1306/#1532) | **Missing.** See §2. |
| 3 | Bridges and tunnels not seated or cut correctly | #1298 (roofed pack tunnels), #1331 (LGAV tunnel_ramp), #1138 (pack bridge edges), 28k (cuts and tunnels) | **No site listed by the owner.** §5 lists what the census pass found; nothing is changed. |

## 2. Attribution (measured before any fix)

Capture `LFLL` at b8c456c9 (FRANCE1M lidar inset), stage replay `--from classify --emit`:

- OSM maps the LGV through the station as seven `railway=rail cutting=yes
  covered=yes tunnel=building_passage layer=-1` ways (45.7190 to 45.7231), and
  as `cutting=yes` north and south of it. The lidar sees the trench floor
  continuously: 228.3 to 230.3 m along the line, 229.3 to 229.9 m under the
  station.
- #1183 (#1179) cuts every cutting corridor out of every pad at the pad's one
  derivation site, so the station's pad `building8` is split into strips
  (`building8#1` to `#5`) with no pad over the tracks.
- The pad fills of 19ap (`planar/pad_fill`, minted as landings by
  `planar/landing`) then fill the corridor back up. The station's concourse
  plates ride the held block, and their part over the corridor is "off the
  block", so the corridor becomes 16 landings `building8/landing0` to `15` at
  239.3 to 239.8 m. Along the rail centre line the emitted surface reads the
  base-mesh lidar at 229.3 to 229.9 m north and south of the station and 239.3
  to 239.8 m for the 450 m under it. This is the owner's "steps up to the
  building".
- `planar/low_level` refuses the station block: "ground drop +0.27 < 3 m". The
  low parts' footprint it reads lies on the strips the trim left, not over the
  trench.
- The trench's own objects stand at y −9.12 (156 of 216 walled feet of the
  parts along the tracks, 1 m band) under a station floor at y −0.06 (3,956 of
  5,004 walled feet). With the owner's 1.0.43x zero (238.97 m) that is
  229.85 m: the lidar floor.

## 3. The rules

**R1. A landing never fills a mapped cutting.** This is existing law (#1179)
applied at its second mint. The fills and deck landings of `planar/landing`
take the cutting corridors (`classify/pad_cut_corridor.cutting_corridors`, the
one reading) as already taken, like a pad. No collar is laid over them either.

**R2. A covered cutting under a pad is that pad's lower level (23b two pads,
27h depth from the objects).** A cutting way mapped `covered=yes` or
`tunnel=building_passage` runs under the building the pad carries. It is not a
bore (§26), and the [tunnel] law already says the passage "belongs to the
building's pad".

1. `classify/pad_cut_corridor` no longer trims a covered cutting from the pad.
   It still trims every open one.
2. In `planar/low_level.low_level_split`, a held pad that a covered corridor
   crosses is read by `planar/covered_cut.plan_covered` first:
   - The cut's REACH is the corridor plus one carriageway width either side
     (`cutting_corridors(widen=1.0)`), which takes in the platforms between
     and beside the tracks.
   - The block's TOP level `t` is the densest 1 m plane of the walled feet of
     the unit's share of the pad off the reach: the floor its own buildings
     stand on.
   - Its LOWER PARTS are the unit parts standing at least two plane bands (a
     storey, 23c) under `t` whose footprint meets the reach, each kept to the
     reach. The rest of a 5 km rail object or a ground plate is never taken in.
   - The level is the corridor plus those parts' footprints, cut from the pad
     by `low_level.level_cut` (closed by `pad_frontage_m`, kept that far off
     the airside, a riser's width off the other pads, at least a unit pad's
     worth). It is minted `<block>/p1`, a `low_level` record with
     `witness = covered_cut`, held at the block's datum + (plane − `t`), where
     plane is the densest 1 m plane of the lower parts' walled feet in the
     reach (27h).
3. The level does not extend over its group's lower footprint
   (`planar/low_extent`). RULINGS 2026-10-28r (1).
4. What no level takes is trimmed out of every pad (`covered_cut.trim_uncut`,
   in `planar/overlay` after the platform split), as #1183 trims an open cut.
   This covers a covered cut under a pad whose unit has no lower storey along
   it, and the pieces the level cut keeps off the airside. A pad never fills a
   cut.
5. The object stage sees no second level. `airport/placement_read` publishes
   the level under its block's plane, so the station stays seated with its
   group (row 1).

**R3. The cut's ends grade to the open cut (RULINGS 2026-10-28r (3)).** The
level stays where the objects put it. Beyond each end of the station the
ground grades smoothly to meet it, with no step (`planar/cut_runout`).

An END is where a mapped cutting way crosses the level's ring and runs on
outside every pad for 20 m. Crossings within 60 m of each other are one end.
Its lip is their centre and its direction their mean outward tangent.

Off the lip runs a strip as wide as those tracks' corridors (half a
carriageway either side). It is as long as `geom/ramp_profile.runout_profile`
needs to meet the raw ground:
- designed at `[tunnel] rail_ramp_grade` = 1.25 %;
- never steeper than `rail_ramp_max_grade` = 3.5 % (new law keys, the 28k R5
  rail grades; source: EU TSI INF §4.2.3.6).

It is a LANDING RUN-OUT (#711, `Registries.landing_runouts`). Its region is
minted by `planar/landing.landing_cut`, and its rows are
`constraints/ramp_runout.landing_runout_rows`: never above the level, never
below the design ramp off it, onto its ground by its end, against the solved
datum. This is one row family: a viaduct's landing runs out at road grade, a
cut's level at rail grade.

An end whose ground stands level with the level, or above it (a run-out never
climbs), asks nothing and is counted (`cut_runout_ends`).

Emittability: the level is a flat pad, and its riser is the existing
`<block>/p1#strip` (§2 (3)), the cell `solve/wall_cut` cuts, so the heightfield
carries it.

## 4. Consumer census (RULINGS 2026-08-30l)

Every pass that reads the region (the covered corridor under a pad) or the new
level:

| Pass (module) | Reads | Before | After | Ruling |
|---|---|---|---|---|
| `classify/evidence._pads` → `pad_cut_corridor.trim_cut_corridors` | cutting corridors | trims open + covered | trims open only | R2 (1) |
| `planar/overlay` apron cut, `reach_after_pads`, `pad_terrace_split` | pad polygons | station pad in strips | station pad whole over the tracks (as before #1183) | unchanged rules |
| `planar/platform.platform_split` (held-block plan, datum samples) | pad polygons | strips | one block | unchanged |
| `planar/landing` deck landings + `pad_fill` plate/pier fills + collars | free ground | filled the corridor (16 fills, 239.3–239.8 m) | corridor taken | **R1** |
| `planar/low_level.low_level_split` / `plan_low` / `group_low` | held pads | `plan_low` refused | `plan_covered` first; the others are not run on a pad it levels | **R2 (2)** |
| `planar/low_level._with_roads` (24a: a road over the lower level takes it) | mapped roads | – | **not applied to a covered-cut level**: 28r (2) | 28r (2) |
| `planar/ribbons._ribbons_pass_c` (mapped-road ribbons, 30aa) | ribbon cells over the corridor | a road stub over the westmost track at the station's north end | every ribbon cell is cut out of the covered corridors first | 28r (2) |
| `planar/low_extent.extend_levels` (#1306/#1532) | every `low_level` record | – | skips `witness = covered_cut` | **R2 (3)**, 28r (1) |
| `planar/covered_cut.trim_uncut` (new, `planar/overlay`) | pad regions | – | trims the rest of the covered corridor | **R2 (4)** |
| `planar/cut_runout.cut_runouts` (new, end of `low_level_split`) | the level's ring, cutting ways, DEM | 0.9–1.4 m step to the base mesh at both ends | a run-out record per end in `Registries.landing_runouts` | **R3** |
| `planar/landing.landing_cut` / `_runout_regions` | `landing_runouts` | viaduct run-outs only | also mints the cut's end strips (`service_road`, ref `runout:<level>`) | R3 |
| `constraints/ramp_runout.landing_runout_rows`, `runout_exempt` | `landing_runouts` + faces | viaduct run-outs | the same rows at the record's own `g` / `cap` (the rail grades) | R3 |
| `constraints/platform.landing_rows` | `low_level` records | – | rigid at D + `y_lo` (the `plan_low` row; no `air_xy`, so not `group_level`) | unchanged consumer |
| `constraints/group_level` (23f) | records with `air_xy` | – | not used (28r (3): the block datum) | – |
| `constraints/riser`, `solve/wall_cut` | `#strip` riser cells | – | the level's riser | unchanged consumer |
| `airport/placement_read` / object stage | the level under its block's plane | – | station seated with its group | R2 (5) |
| `planar/structures` (bores), `planar/channel` (§45) | `tunnel=yes` bores, crossings | building_passage is no bore | unchanged | §26 |
| Light-rail tunnel −11339 (Rhônexpress) mouth north of the station, 45.7223, 5.0756 | tunnel_ramp face | 229.27 → 222.31 | unchanged; meets the level's north end | unchanged |
| groundside terrace law, road seating (24a/27f/27s) | roads welded to pads | roads met fills at 239.x | roads meet the station pad (H) at its edge | unchanged rules |
| census (`tools/harness`) | emitted patch | – | the level is a `building` plane pad; its riser is priced by `terrace_actual_step` | – |

## 5. Bridges and tunnels around LFLL (item 3)

No sites were listed by the owner. The structures the planar stage builds at
LFLL, from capture b8c456c9:

- OSM bore `tunnel:-13564` (2 mouths, 45.766, 5.087; mouth 203.2 m): the road
  tunnel 4.6 km north of the terminals, outside the airport.
- OSM bore `tunnel:-11339`: the Rhônexpress light rail leaving the station
  north (45.7223, 5.0756). The tunnel_ramp face runs 229.3 → 222.3 m, and the
  §34 (12) (4) note reads "deck -2864 … DEM cut −3.61 m — SEVERS".
- One wall corridor (`TREES_LY_00`, bay, 45.7249, 5.0771), 32 door ramps, three
  pack basins (two covered pits at 226.9 and 227.1 m under the hotel, one pit at
  233.4 m).
- The pack's ground plates and trench objects are refused as a tunnel
  ("deck footprint 430,816 m² over the 150,000 m² maximum; a tunnel is not an
  island"). That is the tunnel-admission law, not a defect here.

None was changed in this lane. #1298 (roofed pack tunnels) and #1331 (closed)
are not the class here: LFLL's station is a covered rail cut mapped as
`building_passage`, not a pack tunnel object.

## 6. Owner rulings (RULINGS 2026-10-28r, Q257–Q259, 2026-10-28T05:47:49Z)

"257. A 258. A 259. I think if we did B it would require separating the object
group right? If so, I would say A, and then grade terrain to meet either end of
the object rails smoothly".

1. **(Q257 A)** The level is the cut's alone and extends over nothing. This is
   R2 (3).
2. **(Q258 A)** A road crossing over the covered cut inside the building is
   carried by the building's objects (28k 227a). The level takes no road (24a
   is not applied) and no road ribbon stands in a covered cut.
3. **(Q259 A)** The level is held at the block's datum plus the objects' plane.
   Its ends grade to the open cut at the rail grades (R3).

## 7. Acceptance

Synthetic twins: `tests/auto_patch_v2/test_covered_cut1333.py`.

Capture replay (`LFLL` at b8c456c9; `--from classify --emit --verify`; base =
main 28cd9b38, lane = this branch, on the same capture), census A/B:

| | base | lane |
|---|---|---|
| ground along the rail under the station (450 m) | 239.3–239.8 m (16 fills) | 230.38 m, one level `building8/p1` (54,130 m²) |
| north end (lip 45.72304, 5.07606) | 1.4 m step to the base mesh (228.9 m) | `runout:building8/p1`, 230.38 → 228.8 m over about 80 m, then on the lidar |
| south end | 0.9 m step at the covered end | the open cut between the station's south platforms stays at the platform level, then grades down at the station's south end (`runout:building8/p1#1`) |
| hard rows relaxed | 280 (pad 251) | 50 (pad 29) |
| census total / adjudicated | 1,840 / 424 | 1,536 / 176 |
| airside families (airside_no_step, cross_shape, taxi_box, strip_*) | 21 / 3 / 4 / 17 | unchanged |
| DEFECT families | zero | zero |

New census rows:
- **+5 `pavement_over_road_cap`, 9.5 m, 45.7161–45.7183, 5.0754–5.0757.**
  These are the station pad's edge over the south end strip, i.e. the trench
  walls under the station's southern part. The census did not see them before,
  because the cut floor had no face.
- **+1 `pavement_over_road_cap`, 0.54 m.** A road west of the station.
- **+1 `vertex_to_edge_step` and +1 `mid_edge_step`.** Door ramps and roads,
  0.5–0.6 m.

Residual, ruled acceptable by 28r (3): the level stands 0.7–0.9 m over the
lidar floor under the station, where the objects put it.

The closing LFLL build is still pending, and its harness run was REFUSED and
flagged CONTAMINATED (2026-10-28). During the build the engine tried to fetch
the Copernicus GLO-30 and GLO-90 BASE rasters for N45E005 (base-void fill).
The write guard blocked the replace and the remove, but two `.part` files
stayed in the shared `Elevation_data/+40+000/` folder. That scope needs a
`--refresh-data dem` that covers the base rasters. Then comes the owner's
sim read: the station sits with the terminal group, and the rail cut is
continuous past the station.
