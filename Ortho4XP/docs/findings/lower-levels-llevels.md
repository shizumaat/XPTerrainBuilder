# Lower levels end too early (#1306 KATL, #1302 LFPG) — lane `llevels`

Attribution only. The fix needs an owner ruling, so no engine code was changed.
The question is at the end.

Captures were taken on main `275514532`: `KATL.pkl` and `LFPG.pkl`, registered
under lane `llevels`. Each was replayed `--from constraints` on the same tree,
and the numbers below are read off the solved surface (`--solved-out`). The
group zero is approximated by the block plane, `building47` at 300.81 m.

## Site numbers (current configuration)

**KATL east terminal (#1306).** The lower level is `building47/p1`. It covers
71,064 m² and is held flat at 287.78 m (y −13.03, the lower storey's floor:
504 of its walled feet stand at −13). It spans x 770–1574 m in the airport
frame and ends at the terminal's west tip.
- **Apron wall `muro_concreto.obj` (unit 19, south of the terminal).** It runs
  376 m south from the pad. Its foot is at y −11.51, which puts it at 289.30 m,
  1.5 m above the pad floor. Past its lower face the ground is raw DEM at
  290.0–290.7 m, and the service road along it is at 290.9–292.7 m.
- **Apron wall `muro_concreto5.obj` (unit 25, west).** It runs 170 m on to its
  end at the taxiway E strip. Its foot is at y −9.70, which puts it at 291.11 m,
  3.3 m above the pad floor. The pocket north of it is raw DEM at 290.1–292.3 m.
- **Owner site at the control tower (33.641763, −84.421885).** The tower's pad
  `building57` is at 293.06 m (DEM +0.77). The service road beside it is at
  293.18 m. The brick wall `muro_ladrillo.obj` (unit 27) stands there.
- **Group membership.** Both apron walls are in the terminal's group: their
  footprints touch it, so under 22o they are one group. The tower's unit 26
  stands 16.7 m away and `muro_ladrillo` 152.6 m away, so neither is in the
  group.

**LFPG T2 (#1302).** The four lower pads, `building34/35/49/62` `/p1`, are held
at 97.79–97.81 m (y −7.42/−7.44 on the group zero 105.19). Between them, the
central corridor under the roads is APRON (`dsf:pol459`, airside). It is
solved at 103.2–104.1 m (DEM 105.2–105.8), which is 6.3 m above the pads on
either side.
- **Parts standing in the corridor** (x 1900–2350, y −660…−550). All are in
  T2's unit 2:
  - `2A_6.obj`: 36 parts at y −6.5 … −7.7, the trench storey.
  - `2A_26.obj`: 27 parts at y −5.44, the road columns, 2.0 m above the trench
    floor.
  - `2A_23.obj`: the road deck, at y +3.64.

## Attribution: the one rule

**A lower level never crosses the edge of the held pad it was cut from.**
`planar/low_level.level_cut` builds both kinds of lower level (`plan_low` and
`planar/group_low.plan_group_low`) as follows:
- it takes the low footprint, closed by `pad_frontage_m` (and joined by
  `_with_roads`);
- it intersects that with the one held pad `P`
  (`L = valid_area(L.intersection(P)) − air ⊕ near`);
- it then cuts `P` into the high block, the level and the riser.

No ground outside `P` can join a lower level. That includes groundside ground,
pavement, another of the group's pads, and a wall's lower face.

- **KATL.** The walls and the tower pocket lie outside `building47` (they are
  raw mesh or groundside faces), so the level stops at the pad's ring.
- **LFPG.** Each trench pad is its own `P`, so four separate levels are minted.
  The corridor between them is in no pad: it is apron. A second, upstream
  reading puts it there. The §27/19ag reach read
  (`classify/reachability.unreachable_aprons`) judges the 507,378 m² `pol459`
  face whole at classify time, before the pads are cut. The face holds one
  connected room, which is reachable, so the face stays apron.
- **The same read on the planar map, once the pads are cut, gives the opposite
  verdict.** The corridor component (43,482 m², x 1856–2362) has NO reachable
  room: pieces 37 and 38 are beyond the halls. Under 19ag's own words (a
  building divides when aircraft cannot get around it), it is groundside.

## The generalised rule (proposed; elevation needs the owner)

A two-level group's lower level spans the group's whole LOWER FOOTPRINT,
across pads and whatever face kind lies there. The footprint is:
- the closed footprint of the group's lower-storey parts: buildings, road
  columns, and the lower faces of its retaining walls, to their ends;
- the mapped roads over it (24a);
- any pavement within it that aircraft cannot reach once the buildings stand
  (19ag, read after the pad cut).

It never takes airside that aircraft can reach (airside is king, 23e). The
group is the 22o/23e connected group. The tower and `muro_ladrillo` at the
KATL site are NOT in it, so reaching "under the buildings and retaining wall
here" needs either the group, or the level, to take in neighbours within the
closed footprint.

**What is open is the level's height where the group's own objects disagree.**
At KATL the two apron walls' feet stand 1.5 m and 3.3 m above the storey floor
the pad is held at. At LFPG the road columns stand 2.0 m above the trench
floor. 20ai says the ground past a wall foot is the REAL ground (≈ the wall
foot at KATL: 289.3 vs DEM 290.0–290.7; 291.1 vs 290.1–292.3). 22c/23c (2)
say nothing floats, though parts may be partly submerged.

## Question for the owner (one line)

**Q (#1306/#1302):** When the lower level extends over the group's whole
lower footprint (KATL along both apron walls to their ends and into the
control-tower pocket; LFPG across the T2 central corridor), should it
**(a)** stay ONE flat level at the lower storey's floor (KATL 287.8 m, which
leaves the walls' feet floating 1.5 m and 3.3 m above it and cuts the tower
pocket 2.3–4.5 m into the ground; LFPG 97.8 m, which floats the road columns
2.0 m), or **(b)** stand at the foot of whatever object of the group is on
each part (the storey's floor under the terminal and trench buildings; each
wall's own foot along it, 289.3 / 291.1 m at KATL, the 20ai real ground; the
columns' feet, 99.8 m, across the LFPG corridor), with a riser between?
**Recommended: (b)**, so nothing floats (22c) and 20ai stands. The level
still reaches the walls' ends and spans the corridor.

## Acceptance bar, once ruled

- KATL: the lower level is continuous from `building47/p1` along both apron
  walls to their ends and under the tower pocket. Walls' feet within 0.5 m of
  the ground on their lower face (12y ground bar), no airside vertex moved by
  more than 1 m (23d), and the verify DEFECT families stay zero.
- LFPG: the T2E–2F central corridor is groundside and at the lower level
  (0.5 m bar) under the roads and columns, and the four trench pads join it
  without a riser where they stand at one floor.
- Replays `--from classify` on both captures (the 19ag read moves upstream),
  then ONE closing build. Measured after the first replay: the build-time cost
  of the reach read on the planar map (one more room read).

## RULED (RULINGS 2026-10-27h, option (b)) — the design implemented

1. **The reach read sees the buildings** (`classify/reachability`, 19ag).
   The room an aircraft has is the airside pavement LESS the building pads
   standing on it (`Evidence.pad_union`); "joined to the taxi network" is
   still read on the pavement with them (a corridor under the halls is
   pavement, not an island). An apron face whose room is reachable in part
   is SPLIT: each piece of it outside the buildings whose room is all
   beyond (and that is a lot, the existing half-room test, with no startup
   on it) is cut off as `<ref>#beyond<k>` and takes the groundside role.
   LFPG T2's central corridor is such a piece.
2. **The lower level extends over the group's lower footprint**
   (`planar/low_extent`, called by `low_level_split` after the levels are
   minted). For each lower level: the group is its unit plus the units
   whose footprints come within `[placement] touch_m` of it (22o, one hop);
   its LOWER parts are the walled parts whose foot plane stands at least two
   plane bands under the level's top floor. The extension is the closed
   footprint of those parts (a retaining wall's piece widened by its own
   reach, `max(4 h, 20 m)`, the wall-zone reading) plus the roads over it,
   less every pad region and a riser's width, less the airside (cells and
   zones) and `pad_frontage_m`, less any piece whose ground does not lie
   below the block's (the #1115 witness). Each connected piece is minted
   `<block>/p<k>` (kind `low_level`, the level's witness) at the densest
   walled-foot plane of the group's lower parts on it: the objects'
   bottoms (27h). Its riser strip `#strip` separates it from every pad.
3. **Risers between levels.** `constraints/riser` withdraws a row spanning
   two lower levels held at different floors, as it does one spanning a
   level and its block.
4. The KATL tower (unit 26) and brick wall (unit 27) are not in the group
   and are not taken in.

Acceptance (bars 12y: ground 0.5 m): KATL, the ground along the south and
west apron walls' lower faces within 0.5 m of each wall's foot to the
wall's end; LFPG, the T2 central corridor within 0.5 m of the lower
central buildings' bottoms; airside movement < 1 m (23d) with no new
airside grade row; verify DEFECT families zero; the closing build KATL.

## Measured (captures on main 275514532, replays on this branch; closing build KATL)

Two corrections to the design above, both measured:
- the reach read runs in PLANAR, after `pad_cut.apron_cut_to_pads`
  (`planar/reach_after_pads`), not in classify: given the pads as
  obstacles at classify time, the split pieces under the halls fed
  `pad_touch`'s cut-back and LFPG lost hall bays (`building24/57/16`); and
  only a page the pads cut into reached and unreached pieces is split -- a
  page wholly beyond stays classify's (five synthetic fixtures have one);
- wall pieces keep off the adjacent-ground ZONES too (a piece cut into a
  zone tore it 5-9 m at the walls' ends) and off every STRUCTURE (a piece
  over an LFPG tunnel ramp lifted its walls 2.75 m).
- a group level reaching its pad's own ring took 461 pass-1b hold rows
  carried by the join onto that ring and was lifted, rigid, to the pad's
  datum (`building34/p1` 104.17 m against its 97.99 m pin): a group
  level's vertices are stage 2's (`group_level.stage_two_vertices`).

**KATL east terminal** (replay `--from planar`; build `llevels_KATL`,
artifact ledger 805c8913110a, body 1efc102dee91, DEFECT families zero):
- south apron wall (`muro_concreto`): the lower level runs its whole
  length on the lower side, `building47/p4` 11,114 m2 held at 289.30 m =
  the wall's foot (y -11.51); before: raw DEM 290.0-290.7 m;
- west apron wall (`muro_concreto5`): the pocket north of it,
  `building47/p6` 7,299 m2 at 291.11 m = the wall's foot (y -9.70), to the
  brick wall by the tower; before: raw DEM 290.1-292.3 m;
- the terminal's lower storey stays `building47/p1` at 287.78 m; risers
  1.52 m and 3.33 m between;
- airside pavement: 1 vertex moved over 0.01 m (0.044 m); verify 2,135 ->
  2,214 rows: road_cross_section 15 -> 69 (roads crossing the new risers:
  3.2 m at the pocket's east end by the terminal's west tip, 1.7 m at the
  south wall's north end -- the #1138 class), strip_seam_tear 69 -> 73
  (8.4 m where the south strip ends at the taxiway strip south of the
  wall's end), groundside_cutback 123 -> 121.
- NOT taken in (27h): the control tower (unit 26, 16.7 m off the
  terminal's unit) and the brick wall (unit 27, 152.6 m off): the tower
  pad stays at 293.06 m beside the pocket level's 291.11 m.

**LFPG T2** (replay `--from planar`; no build -- the IGN WFS tile index
answers HTTP 400):
- the central corridor (`dsf:pol459#beyond1`, 43,482 m2 unreachable once
  the halls stand) is groundside, and the lower level spans it:
  `building34/p2` at 98.39 m (y -7.07, the lower central buildings'
  area-weighted bottom); before: apron at 102.5-104.7 m;
- the four trench levels stay at 97.98-97.99 m (0.4 m riser to the
  corridor); further extensions along the road trench east
  (`building62/p2..p4`, 98.39-99.09 m);
- airside pavement: 205 vertices over 0.01 m, 34 over 0.1 m, max 0.51 m
  (the apron beside the corridor's west end, 49.00475, 2.57392; 23d);
  verify 3,635 -> 2,705 rows (within_shape 1,791 -> 847, airside_no_step
  227 -> 221, road_cross_section 167 -> 182), DEFECT families zero.
