# Brief pack — lane `channelscout`

Base: main `98c94f86` · generated 2026-09-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Evidence for the OPEN CHANNEL class: KDFW, KPHX beside LGAV

## The brief

# THE QUESTION — the OPEN CHANNEL pattern class (owner 2026-09-15)

A below-grade ROAD/RAIL CHANNEL cut through the centre of an airfield, open to the sky, crossed by taxiway (and
runway) BRIDGES: LGAV (Attiki Odos motorway + Proastiakos rail between the two runways; the FlyTampa pack models
it as `Trench/Trench_0x.obj` walls, floors, a 4,077 x 149 m plate roofed 6 % = the bridge decks), KPHX (Sky
Harbor Blvd under the terminal taxiway bridges) and KDFW (International Parkway between the terminal
horseshoes, taxiway bridges over it). The owner wants ONE model that identifies and grades this class. The
session (Fable) writes the spec; YOUR job is the EVIDENCE it must be founded on, read-only, cited by path and line.

# WHAT IS ALREADY KNOWN AT LGAV (do not repeat; use as the comparison column)
- 30 m COPERNICUS DEM: BLIND to the trench (transect across at 37.93656,23.94063: 77–79 m flat; the trench is
  ~12 m deep by the pack's walls, `Trench_03.obj` VT y −12.67…+5.73).
- OSM big_roads feed: motorway (lanes 2–3) and railway=rail ways cross the field with NO tunnel/bridge/layer/
  cutting/covered tags — OSM offers no evidence of the depth at LGAV.
- Every v2 structure pass refuses the Trench objects for a different reason (report
  `/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+37+023/LGAV/LGAV.report.json`): basins → "shell rises
  4.46 m above the ground (> contact_band_m) … a shell through the ground"; sunken roads → "roofed over 6 % (<
  roof_min_fraction 50 %) — an open ramp"; tunnel objects → "roofed along its axis / roof, not a crest / skirt
  under 0 %"; wall corridors (LAW C) → "law off for LGAV" (`law/airports.toml`, OTHH only). Planar minted only 5
  `tunnel_trench` faces (3,885 m²) + 6 `retaining_wall` + 2 `tunnel_ramp`, and one basin (`Trench_08.obj`,
  floor 69.66) — against a channel of roughly 4 km x 100 m.

# WHAT TO MEASURE (KDFW first — warm; KPHX second — the owner is building it NOW with app 1.0.340, its mod
# cache is empty at brief time: read what exists when you get there, NEVER trigger a fetch or a dump)

For each airport, a table with the same rows so the session can set LGAV / KDFW / KPHX side by side:
1. THE CHANNEL IN OSM: the ways of the road/rail through the field (tile feeds under
   `/Users/noah/XPTerrainBuilderData/OSM_data/+30-100/+32-098/` for KDFW, `+30-120/+33-113/` for KPHX): highway/
   railway class, and EVERY depth witness tag present or absent — tunnel, bridge, layer, cutting, covered,
   embankment — on the channel ways AND on the taxiways crossing them (the `airports` feed: aeroway=taxiway with
   bridge=yes?). Quote way ids and tags.
2. THE CHANNEL IN THE DEM: KDFW has a 1 m 3DEP inset (`Elevation_data/+30-100/N32W098_airport_insets/
   KDFW_usgs3dep.tif`; read with `osgeo.gdal` from `Ortho4XP/venv/bin/python`, read-only). Transects ACROSS
   the channel at three stations and ALONG its axis: depth below the adjacent apron/taxiway, wall-to-wall width,
   floor grade, and — critically — whether the taxiway BRIDGE DECKS appear in the lidar as ridges over the
   channel (a DSM/DTM question: state which the tile is, from the inset's `.json`). KPHX: whatever inset exists
   when you look; if none, say so and give the channel's geometry from OSM + the pack only.
3. THE CHANNEL IN THE PACK: from the cached DSF text dump (`Airport_mod_cache/<pack>/+32-098.dsf.*.text`,
   `OBJECT_DEF` list + placements) and the pack's `.obj` headers/vertices: are there WALL objects, FLOOR/road
   plates, DECK objects along the channel? Depth of the deepest vertex under the placement datum; the roofed
   fraction. Use `tools/docq.py index obj8_split_report` / `object_pad_evidence_report` if a row fits; write no
   new tool.
4. THE CROSSINGS IN apt.dat: which pavements (Global Airports block, and the custom pack's block if it carries
   row-110 pavement — quote the count) cross the channel axis; their width at the crossing; whether the runway
   crosses it. Use `auto_patch_v2.airport.apt_dat.read_airport_block/parse_airport_block` from
   `PYTHONPATH=src`.
5. THE ENGINE'S CURRENT READ: `cd Ortho4XP && PYTHONPATH=src venv/bin/python -m auto_patch_v2.planar KDFW --out
   <scratch> --stage structures` (INDEX row: ~25 s, read-only on the corpus; it REFUSES cold data — if it refuses,
   quote the refusal and stop, do not warm anything). Report which pass touched the channel and every refusal
   string naming its objects, exactly as done for LGAV above. If the harness/shared-repo guard names a write, that
   is a finding — quote it.
6. WHAT THE SIM SHOWS TODAY (if a built tile exists under `/Users/noah/X-Plane 12/Custom Scenery/zOrtho4XP_+32-098`
   or the Patches dir): the last KDFW `*.report.json` / `.graded.json` under `XPTerrainBuilderData/tmp/
   auto_patch_v2/+32-098/KDFW/` if any — its `planar.faces_by_role`, `structures`, `basins`, `sunken_roads` blocks.

# OUTPUT
A report file in your scratchpad (path in your final message) + the three-column table in the final message
(LGAV column from the facts above). Every number carries its source path. No edits, no builds, no downloads.

## Spec (design-surface) §24

## §24 THE BASIN'S EDGE AND FLOOR (owner RULINGS 2026-09-11t) — lane `v2basinedge`

Owner, LEMD 1.0.315: "still a gap between the outer edge and the apron … the apron
elevation shape needs to be closer with less of a gap between the floor cutting
shape. The object also provides a floor … that should be visible instead of seeing
the terrain at the bottom of the basin."

1. **THE CUT HUGS THE WALL.** The basin's cut ring is the object's OUTER wall face at
   its top (the `basin_wall` ring of the floor witness's shell, read from the pack —
   not the OSM footprint, not a snap-out widening, not a buffer). The apron's rim
   vertices lie ON that ring at the rim level (§ rim_level: the rim IS the adjacent
   apron edge), so the pavement meets the wall top with no shelf outside it and no
   step down to it. Measured: horizontal distance from each rim vertex to the wall
   face ≤ `emit.weld_spacing_m` (1.0 m, the identity spacing); vertical step between
   the rim ring and the apron vertices it joins 0.00 m (materiality 0.01).
2. **THE FLOOR SITS UNDER THE OBJECT'S FLOOR.** The trench floor level = the object's
   floor-plate elevation (its authored y at the rim's zero, the 10bd depth) MINUS
   `[basin] floor_clearance_m` (new, default 0.5 m): the plate renders; the terrain
   is never seen through it. The basin's inner floor ring and every floor vertex
   take that level; the walls' bank between rim and floor is the object's wall
   (vertical in the object; the terrain bank is hidden behind it).
3. **Consumers**: the rim ring's derivation site (`planar/structures.py` basin /
   `basin_witness`), constraints `structures.rim_level` + the floor row, verify's
   basin family, `pad_level_report` leaders (a pad fronting the basin reads the rim),
   the placement anchor for a basin body (§6: a RIM point on the emitted ring). One
   table in the lane's report before any edit (08-30l).
4. **Measured first on the app's products** — `<Patches>/+40-010/+40-004/LEMD.graded.json`
   (T4S basin: rim ring vs the object's wall face, rim vs apron edge, floor vs plate) —
   then fixed, then LEMD once. Bars: (1) and (2) as stated; OTHH's Dewatering /
   tunnel basins unchanged by dry run; `> 3 m` unchanged.

**Measured** (lane `v2basinedge`, branch `claude/v2basinedge`; before = the app's
1.0.315 products, after = `LEMD_20260911T142115` `body_sha=0a6181fed68f`, rc 0,
360 s). T4S = `basin:0` (40.491701, −3.569256; members `Ground-FSX-LEMD36/37/85`),
the only basin LEMD admits:

| bar | before | after |
|---|---|---|
| (a) rim vertex → the object's outer wall face (≤ 1.0 m) | **+1.749 / +2.064 / +4.120 m, 56 of 56 OUTSIDE and over the bar** | **−0.251 / +0.010 / +0.264 m, 0 of 49 over** |
| rim ring area vs the shells' region | 28,971 m² over 27,557 m² (perimeter 705 vs 682 m) | 27,586 m² over 27,557 m² (682 vs 682 m) |
| (b) rim → apron vertical step (0.00, materiality 0.01) | 0.000 — all 71 rim vertices share their id with a ground face (23 apron, 51 pad) | 0.000 — all 59 do (14 apron, 47 pad) |
| (c) trench floor − the object's floor plate (−0.50 ± 0.01) | **+0.000 / +0.000 / +0.000 m** | **−0.510 / −0.500 / −0.500 m** |

Mechanism of (a): `planar/basins._rim` widened the region by whole grid steps until
it contained the floor (the plate ⊕ `floor_overlap_m`) and cleared it by the
stand-off; the T4S shell measures 0.00 m thick, so the loop ran to k = 4 = +2.0 m.
That is the owed `rim snap_out widening` item of RULINGS 08e deviation (2), now
closed: the rim is the region, and the stand-off comes out of the FLOOR
(`_floors_inside`, 1,066 m² trimmed at T4S).

OTHH dry run (planar replay of the new tree, no build): all **10** basins still
admitted, none refused; every rim vertex on its wall face (worst |0.494| m, 0 of
263 over the 1.0 m bar); the Dewatering pits' depths unchanged (13.142 m, the
04i/08d reading) and the drainage bowls' 3.816 / 4.201 m likewise, each now
+ 0.500 m of clearance. Basin verify families on the LEMD arm:
`basin_floor_declaration` 0, `basin_floor_at_declaration` 0, `structure_rim_gap` 0,
`wall_in_runway_strip` 0.

**DEVIATION REPORTED (§24 (1)), never decided by the lane.** A ZERO-THICKNESS
shell — LEMD's T4S, OTHH's drainage shells, and every synthetic box fixture —
cannot both keep the rim ON the wall face and give the floor its
`floor_overlap_m` outward past the plate: there is no wall thickness to spend.
The floor is therefore the plate TRIMMED to stand `rim_standoff` (0.5 m, the
identity spacing) inside the rim, which leaves a ≤ 0.5 m band of terrain inside
the wall line rising from the floor to the rim, its top standing up to the
clearance ABOVE the plate. The alternative is the shelf (1) exists to remove.

**NOT MEASURED by the lane**: `> 3 m` (the seat-feet census reads the object
stage, which needs the app's mesh) and a matched defect-gate control (the
1.0.315 products are a four-airport TILE build; a single-airport arm is a
different population, and a control build is a second build).

**MEASURED (lane `v2basinfoot`, 2026-09-13; branch `claude/v2basinfoot`, base
main `e5e04660`).** Before = the owner's 1.0.325 products (the four-airport TILE
build in the data repo: `Patches/+40-010/+40-004/LEMD.graded.json` +
`o4_v2_rebake_LEMD.json` + the copied patch); after = `LEMD --engine v2`
(`v2basinfoot3`, rc 0, 408 s, ledger `1c11f6fad3a2`, `body_sha 58a9ce7d3170`).

**(6) THE CONSUMER CENSUS, before any edit** — every pass that reads the basin
region / rim / floor, and what §24 (4)–(5) does to it:

| consumer | reads | ruling |
|---|---|---|
| `planar/basins.build_basins` | the region, the rim, the floors, the cut knife, the keep-outs | THE SINGLE DERIVATION SITE — both laws land here and nowhere else |
| `airport/obj8._witness` | the component's below-DEM clip (`FloorWitness.below`) | KEPT as rule 1's ADMISSION evidence; `outer` added beside it for the region |
| `constraints/structures.basins` | `faces_by_ref[floor_ref]` vertices, `wall_path`, `floor_below_rim_m` | EDITED: a floor vertex under a ramp corridor takes `deck − floor_clearance_m` (a senior pin); every other vertex keeps the 10ba relative row unchanged |
| `constraints/structures._rim_rows` / `rim_level` | the rim ring's vertices | UNCHANGED in form; the ring is a different (larger) ring, `rim_level` 11 design-target rows before and after |
| `planar/structures.py` `contact_band_m` reader (l. 352) | the LAW KNOB only, for tunnel-object wall bands | NO INTERACTION — it never reads the basin region |
| the pad cut (`cuts_pads`) | the knife vs `building` cells | UNCHANGED in form, and this is where the `building15` notch goes: the pad is now cut there (see below) |
| `building_pad.in_basin_sits_at_floor` | — | DEAD KNOB: declared in `law/structures.toml` + `law/model.py`, read by NO code (grepped). The pad is CUT, not lowered. Left alone, reported |
| `pipeline/build._plate_seats` | `Basin.ring` (the largest PLATE floor face) + `plate_y_m` | UNCHANGED: the ramp is a SEPARATE floor face (`basin_floor:0#1`), `ring` stays the plate's, so the witness's seat stations do not move onto the ramp |
| `pipeline/build._basin_polygon` | `b.region` (deck-signature evidence) | follows the larger region; LEMD deck families 0 before and after |
| `pipeline/publication.basin_facilities` | the record | EDITED: publishes `ramp_corridors` / `ramp_rings_ll` / `ramp_faces_ll` |
| `verify/structures.basin_floor_at_declaration` | the published depth vs every floor vertex | EDITED: under a corridor it expects `deck − clearance` (the SAME call, `model.structures.deck_z_on_faces`). Without this the law's own 42 pinned vertices report as violations — measured: 53 rows on the first arm |
| `verify/structures.basin_floor_declaration` / `structure_rim_gap` / `wall_in_runway_strip` | `solid_minimum_y_m` vs `body_depth_m`; rim-to-floor spacing; the strip | NO CHANGE: 0 / 0 / 0 before and after (the ramp floor is trimmed by the same `rim_standoff`) |
| `airport/basin_ring.py` (§14a arcs) | the EMITTED `basin_wall:0@k` ring from the graded doc | FOLLOWS AUTOMATICALLY, no edit: 6 arcs → 7, ring bar 0.19 → 0.18 m |
| `airport/placement_census` basin exemption | the plan's basin bodies | unchanged in form: basin carriers 24 → 25, exempt 20 → 20 |
| `tools/pad_level_report.py` | pads / refs in a solved pickle | no basin geometry of its own; reads whatever the pads became |
| harness `terrace_joints_ll` / `pad_relief` / `basin_floor_declaration` | the sidecar keys | `terrace_joints` 4 before and after, `basin_facilities` 1, `basin_floor_declaration` 0 |

**(4) THE RING IS THE SHELL'S OUTER FOOTPRINT.** Cause, reproduced on the
1.0.325 frame: `below` is `_clip_component` at ONE plane per component — the DEM
under the component's CENTROID, 593.00 for `Ground-FSX-LEMD85`, while the real
ground over the ramp runs 594.6 … 599.2. The road ramp is never above the DEM at
all (it lies 1.5 … 6.6 m under it its whole length); it leaves the REGION where it
climbs through 593.00, at **40.492259, −3.569411** — the exact closing point of
the below-clip, ~50 m short of the ramp's top.

| bar | before (1.0.325) | after |
|---|---|---|
| LEMD `basin:0` region | 27,557 m² | **28,345 m²** (+788: the notch) |
| rim ring | 59 nodes | **58 nodes**, Hausdorff **11.57 m** from the old ring |
| the notch at 40.4922455, −3.5695503 | `building/building15` z 598.36 … 598.48 | **`tunnel_trench/basin_floor:0` z 589.83 … 595.94** — the pad is cut, the ramp corridor is trench floor |
| §14a ring bar (`obj8_split_report --no-cut`, matched arms) | 0.19 m, 0 of 59 over 0.30 | **0.18 m, 0 of 58 over** |
| ring nodes the pit has NO WALL on (same instrument) | 3 (worst 1.11 m) | **3** (worst 1.31 m) |
| T4S tower cluster | `LEMDzaun`/`SWbaume` basin bodies on the rim, own-ground 7.59/7.57/7.55 m | **unchanged in kind** (7.71 m worst; the cluster stays on the rim) |
| OTHH, planar dry run, all 10 basins | — | **10 admitted, 41 refusals, rims moved (Hausdorff) 0.00 / 0.12 / 0.14 / 0.32 / 0.32 / 0.35 / 0.45 / 0.47 / 0.48 m — sub-grid, none over 0.48**; floor areas identical bar −15/−22 m² on the two Dewatering pits (rim re-snap) |

**(5) THE FLOOR FOLLOWS A RAMP.** The corridor is read off the shell's own
witness components: up-facing faces (`floor_plate_normal_y_min`) between the
floor and `R_est + contact_band_m`, joined in plan, admitted when the part SPANS
the pit (its own vertices reach within the band of both floor and rim) **and its
surface grade is drivable** — the area-weighted mean face slope, new law
`[basin] ramp_max_grade = 0.15`.

The grade test is not decoration: spanning alone admitted **three of OTHH
Drainage_01's banks (2,118 m², the pit's floor area 735 → 2,853 m²)**, because a
bowl's ring of banks climbs floor-to-rim like a ramp. Rise-over-plan-run does not
separate them either (that bank reads 3.61 m over 133.5 m = 0.03, a bowl
diameter apart); the SURFACE grade does: LEMD's ramp **0.09**, every OTHH bank
**0.20 … 0.29**. At 0.15 the LEMD ramp is the only deck either pack admits.

| bar | before | after |
|---|---|---|
| ramp corridors at LEMD `basin:0` | — | **1** (932 m² of floor, 36 deck faces; candidates refused: 2 m² × 2 "does not span", 101 m² "does not span", 2,043 m² `LEMD36` slab "does not span") |
| floor vertices on the ramp's profile | 0 | **42** (`basins.floor_ramp_vertices`) |
| emitted floor z vs `deck − floor_clearance_m` at every corridor vertex | — | **43 of 43 within 0.005 m** |
| the ramp deck vs the design surface under it | **−2.92 m worst over ~51 m (buried)** | **+0.50 m at every corridor floor vertex**; median +0.48 m over a 1 m grid inside the corridor |
| `basin_floor_at_declaration` | **5** | **4** |
| OTHH ramp corridors | — | **0 on all 10 basins** |

**Harness census (before = the 1.0.325 four-airport tile patch, after =
`v2basinfoot3`).** COCKPIT first: CRITICAL motion **2 → 3** (all three grade
BREAKS, worst 0.670 → 0.600 m, the same `strip_arc` site at 40.4625636,
−3.5525152 — nowhere near the basin), CRITICAL visual **0 → 0**. LAW-TRUE total
3,573 → 3,621; ADJUDICATED 1,143 → 1,172 (airside-for-acceptance 1,128 → 1,151);
`basin_floor_declaration` 0 → 0, `wall_in_runway_strip` 0 → 0.

**That census delta is NOT attributable to this change, and the lane says so.**
Two arms of THIS tree differing only in which deck faces the corridor publishes
(48 vs 42 pinned vertices) censused **1,089** and **1,172** adjudicated rows —
the LP's active set (`feasible`/"SET NOT SETTLED" vs `optimal`) moves more than
the basin does. The 1.0.325 arm is also a four-airport TILE build, a different
population from a single-airport arm (the same caveat §24 (1) recorded).

**NOT MET, with its cause named.** `_rim_open` read **57 of 69** open stations
before and **58 of 69** after (bar ≤ 5). The diagnostic's reference is
`at_grade_geometry`, whose linework is the shell clipped at ONE plane per
component — the very defect §24 (4) removed from the region. With LEMD's ground
running 593 … 599 across the pit and the plane at 592.00, the "at-grade line" is
a contour in the middle of the plate, not the wall top, so no ring can be close
to it. Fixing the rim diagnostic is a separate item and is OWED, not done here.

**NOT MEASURED by the lane.** The scout's `probe2.py` reading (11 of 59 ring
nodes 6.1–15.0 m from the nearest WRITTEN basin piece) needs
`o4_v2_placement_LEMD.json`, which only the app's write half produces; the
harness build entry stops at the patch, the graded doc and the rebake plan. The
engine's own §14a instrument (above, matched arms through `obj8_split_report`)
is what the lane could run, and it reads 3 → 3. A pack-geometry probe over the
nine basin resources' WALL faces reads the ring on the wall everywhere except
the new ramp stretch (nodes 15–20, 4.3 … 9.3 m), where the pack models a bare
deck and the mesh makes the trench's sides — which is the cut the owner asked
for. Also not measured: `> 3 m` seat feet against a matched control, and any
OTHH build (dry run only, as §24 (6) requires).

### §24 (4)–(6) The ring is the shell's OUTER footprint; the floor follows a ramp (Fable 2026-09-13; RULINGS 2026-09-13g) — lane `v2basinfoot`

Owner (13d item 2): the SE corner still gaps; the NW corner's cut must reach the
midpoint of the north edge so the modeled road ramp is visible rising to apron level.
Scout `v2lemd325b` on the 1.0.325 frame (ring `basin_wall:0@849`, 59 nodes): the gap
is HORIZONTAL — 11 of 59 ring nodes have no wall within 6–15 m (the engine's own
`_rim_open` reports "57 of 69 rim stations beyond 2.0 m of the shells' at-grade
geometry", diagnostic only); at node 1 the design drops 6.7 m one metre inside the ring
and the nearest pit wall tops out 4 m BELOW the apron edge; five `basin_floor_at_
declaration` rows. Cause: `planar/basins.py:356` builds the region from each solid
component's footprint clipped BELOW the local DEM (`obj8.py:765`), exterior only,
rim inset 0.00 (the shell reads 0.00 m thick) — not §24 (1)'s "OUTER wall face at its
top". The same clip drops the road ramp (`Ground-FSX-LEMD85__b2`: 100.5 m, 591.4 →
597.5, 6.1 % mean, reaching apron level at −3.56946 — 11 m from the owner's midpoint)
out of the region as it rises: a 51.9 × 11.0 m notch that the pad `building15` fills at
598.4, burying ~51 m of the ramp, worst 2.92 m; the floor is one depth below the
nearest rim vertex (`constraints/structures.py:588`), never a ramp profile.

4. **THE RING IS THE SHELL'S OUTER FOOTPRINT AT THE TOP OF ITS WALLS** — every
   component of the basin resource(s) incl. its ramp — never the below-DEM clip.
   Trims the SE overhang and keeps the ramp corridor inside the cut in one edit at
   the single derivation site (`basins.py` region + `_rim`).
5. **THE FLOOR FOLLOWS A RAMP**: floor vertices under a ramp corridor (a deck of the
   basin resource climbing from the floor to the rim) take the deck's authored
   elevation minus `floor_clearance_m` per station; elsewhere the one depth stands.
   Bar: deck − design ≥ 0 over the ramp's whole run (today −2.92 m worst); the 5
   declaration rows → 0.
6. **CONSUMER CENSUS at spec time (08-30l)** — one table before editing: the basin
   rows in `constraints/structures.py`, `planar/structures.py`'s `contact_band_m`
   reader, the pad cut (`cuts_pads`, `building_pad.in_basin_sits_at_floor` — the
   `building15` notch), verify's basin families, `pad_level_report`, `airport/
   basin_ring.py`'s arcs (§14a — the SE node-3 straddle resolves once nodes 0/1/4/5
   have wall within the band), the placement census's basin exemption. OTHH: its 10
   basins / 21 carriers have shells with real thickness (0.75–2.5 m) — the planar
   replay is dry-run BEFORE the edit and re-quoted after (rims moved, m); no OTHH
   build. Bars: SE corner wall base within 0.3 m of the ring at every walled node
   and unwalled nodes 11 → 0; the ramp visible (bar in (5)); harness census; ONE
   `--engine v2` LEMD build against the 1.0.325 base; twins; suite.

### §24 (7) THE FLOOR IS THE WHOLE ADMITTED REGION (owner RULINGS 2026-09-14n item 1; Fable 2026-09-14; RULINGS 2026-09-14p) — lane `v2othhfix`

Once a region is admitted as a pit, the trench floor covers the region minus
the rim stand-off; the witnessed plate DELIMITS NOTHING — it witnesses depth.
(a) The floor witness is read over the whole ADMITTED FAMILY: a sibling
placement whose deep horizontal plate lies inside an admitted region
contributes it even when its own shell never reaches grade (the
`buried_components` skip in `obj8.py` is a pit-SEED test and never
suppresses a plate inside another placement's pit); every skipped buried
component is NAMED in the report with its area and depth.  (b) Where no
plate lies under part of the region the floor still takes `floor_z`: a
rim-level island inside a pit is terrain standing inside the object's walls.
BARS (OTHH 1.0.332 frame): floor/region ≥ 0.95 on all ten basins (today
0.10–0.56; basin:6 879/4,330 m²); mesh stations inside basin:6's rim above
`solid_min_z` (−9.18) 270 of 393 → 0; LEMD basin:0 unchanged (97.4 %, the
control); ONE OTHH build.

### §24 (8) A BASIN'S RAMP CORRIDOR IS RE-NODED AT ITS STATIONS (Fable 2026-09-14; RULINGS 2026-09-14s) — lane `v2othhfix`

§24 (5)'s "the floor under a ramp corridor follows the deck per station"
has no vertices to land on: `constraints/structures.py` pins EXISTING
planar vertices only, so VHHH's `basin_floor:5#1` (2,794 m², 6.9 m of drop)
carried 4 interior vertices and a 42 % mouth step.  The basin pass re-nodes
the ramp corridor at `ramp_station_m` before emission (the structures pass's
stationed ramp is the model).  BAR: any basin ramp corridor ≥ 1 vertex per
`ramp_station_m` along its axis; the mouth grade within the ramp cap.

## Spec (design-surface) §33

## §33 THE PACK'S WALL OBJECTS GOVERN THE MOUTH (owner RULINGS 2026-09-13d item 5; Fable 2026-09-13i) — lane `v2wallplate`

Owner: "remember to use object based wall objects provided by the scenery package
when present as a guide for where the tunnel mouth is and what size it is." Scout
`v2lemd325t`: LEMD's pack models its bridges and tunnel walls as THIN PLATES —
`Bridges/Bridge3.obj` 354 × 25 m spanning the whole `-5931` bore, solids 1.03 m tall;
`Bridge2.obj` 168 × 90 m over the two `-6291/-6288` decks, 1.31 m; `Bridge1.obj`
1.50 m — and `[tunnel.object]`'s pre-screen refuses anything under `least_skirt` =
min(`skirt_min_depth_m` 3.0, `edge_wall_min_skirt_m` 1.5) (`tunnel_objects.py:702,
737-742`) and then SUPPRESSES the refusal from every report (`:772-776`, four
prefixes). So the OSM corridor stood alone: item 5's mouth 7.0 m wide (`lanes × 3.5`)
against the object's 25.1 m, 1.08 m off its centre, 83 m inside the object's end;
item 6's mouth floor set from the DEM over the overbridge EMBANKMENT (610.5 vs 605.8
twelve metres away) — a 5.0–5.8 m rim wall and a ramp that descends; item 9's decks
at trench floor + `clearance_m` 5.10 = 603.85 while the apron they must meet is at
606.5 and the road at 605.7+ — nothing ties a terrain deck to its ends.

1. **EVERY REFUSED RESOURCE IS NAMED.** The four suppressed prefixes are gone; the
   structures line and the inventory KML carry every screened resource and its
   verdict.
2. **THE THIN-PLATE WALL CLASS.** A pack object whose plan footprint lies over a
   mapped bore (`tunnel=yes`) or deck (`bridge=yes`) and whose solids span at least
   `[tunnel.object] thin_plate_min_m` (1.0 m) is an AUTHORED CORRIDOR: its plan ring
   gives the corridor's axis, width and portal positions (the object's ends); the
   depth stays `bore_datum_m` for a bore and, for a deck, the deck's top is the
   object's authored top. `source_precedence = ["object", "osm"]` then does what it
   says. Item 5's mouth: 25.1 m wide at the object's north end; item 6's: at its
   south end.
3. **THE MOUTH CREST IS THE ROAD'S GROUND, NOT THE OVERBRIDGE'S.** `crest = "dem"`
   samples the DEM at the mouth node; where that sample stands on an overbridge
   embankment (the DEM within `bore_datum_m` of the mouth rises more than
   `split_tol_m` above the DEM along the approach's first stations), the mouth crest
   reads the approach's ground; the top cap follows the ground per corner.
4. **A TERRAIN DECK IS TIED TO ITS ENDS.** Its datum is the higher of (trench floor +
   `clearance_m`) and the graded surface at its two ends (the apron on one side,
   the road on the other), the ramp beneath yielding downward; an object deck (2)
   hands its authored top directly.
5. **BARS**: item 5's mouth at the object's end, 25.1 m, axis on the object's centre
   (≤ 0.3 m); item 6's mouth wall ≤ `split_tol_m` above the road's ground, the ramp
   climbing monotonically to the DEM; item 9's decks meeting the apron (606.5) and
   the road within 0.3 m at their ends; every refused resource named (182 screened
   → N named); the other 15 LEMD corridors quoted before/after; OTHH's 9 object
   corridors and 43 wall corridors byte-identical (dry planar replay); consumer
   census of the corridor readers first (08-30l); ONE `--engine v2` LEMD build;
   harness census with the cockpit block; twins; suite.

**MEASURED** (lane `v2wallplate`, branch `claude/v2wallplate` off main `1d124ac2`;
ONE tree, the shared corpus.  Synthetic-first: four dry `--stage structures` planar
replays at LEMD and one at OTHH before the single `--engine v2` LEMD build.)

**BASE.**  The dry replay at `1d124ac2` reproduces the shipped 1.0.325 structures
line and the scout's read EXACTLY — `bores 68 (no on-field mouth 20, mouth-only
built 27, replaced by objects 2)  mouths 87 (off-field 44, on approach 37 of 8
corridors)  duals merged 16  object corridors 1 (signatures 28 of 182 resources)
tunnels 50  decks 13  cells cut 2`, 105 named object refusals.

**§33 CONSUMER CENSUS (08-30l), one table, before any consumer was edited.**

| # | Reader | What it reads | Ruled |
|---|---|---|---|
| 1 | `airport/tunnel_objects.read_corridors` | OBJ8 signatures → `Corridor` | **(1)** the four-prefix suppression DELETED; every SCREENED resource named, the never-screened counted (`not_screened`).  The corridor list itself is untouched. |
| 2 | `airport/thin_plates.read_plates` (NEW) | the same placements / cache | **(2)** reads exactly the class `read_corridors` refuses; `taken` = the resources already admitted as corridors, so an object is read ONCE. |
| 3 | `planar/structures.build_structures` | `corridors`, cells | `plates=` is a NEW additive keyword; nothing existing re-ordered. |
| 4 | `planar/structure_approach.mouths()` | bore ends → `Mouth` | unchanged; `apply_plates` runs after it and rewrites `xy` / `inward` / `width_m` / `approach` only. |
| 5 | `field_region_for` (§29 mouth gate) | cover ∪ corridors ⊕ standoff | UNCHANGED and runs FIRST — the gate judges the MAPPED end, never the moved one.  Measured: `mouths_off_field` 44 → 44. |
| 6 | `object_corridor.mouth_covered_by` (05n-3) | mouth xy vs corridor footprints | runs after the move; measured `mouths_replaced_by_object` 5 → 5, `bores_replaced_by_object` 2 → 2 (Bridge4 unaffected). |
| 7 | `object_corridor.object_groups` | corridors → `Group` | untouched: a plate never becomes an object corridor, it governs the OSM mouth. |
| 8 | `planar/structures` ramp geometry (`geometry`, `_pad_hit`, `beyond_strip`) | the mouth's width / inward | reads the plate's width, so ramp, void and cap are the object's 25.1 m. |
| 9 | `planar/structures._ramp_top` | mouth_z, axis | MOVED VERBATIM to `structure_approach.ramp_top` (both files' budget); no behaviour moved — 46 of 50 tunnels byte-identical proves it. |
| 10 | `model/structures.Deck` | `ref/way/s0/s1/ring/datum/z` | **(4)** three NEW optional fields (`end_z`, `end_ref`, `end_xy`), default `()`; every existing constructor and reader unaffected. |
| 11 | `constraints/structures` deck rows | `deck_top` → `Band`; else `Offset(clearance_m)` | **(4)** adds a per-vertex lower `Band` on the ends' profile and an `Offset` to the governed cell at each end.  The object-deck branch untouched. |
| 12 | `constraints/structures` mouth / rim rows | `tn.mouth_z`, `tn.mouth_dem_z`, `wall_path` | **(3)** changes the VALUE only; crest and floor move together, so the rows are unchanged. |
| 13 | `verify/structures.tunnel_mouth_canonical` | cap crest − ramp mouth = `bore_datum_m` | invariant preserved by construction (the cap moves the floor with it). |
| 14 | `verify/structures.tunnel_deck_clearance` | min(deck) − max(ramp) ≥ `clearance_m` | a LIFTED deck can only increase clearance — never a new row. |
| 15 | `emit/osm_adapter` sidecar `road_bridge_decks` | always empty in v2 | unchanged. |
| 16 | `pipeline/publication.tunnel_objects` | `tn.source != "osm"` | unchanged — a plate mouth stays `source = "osm"` (it IS an OSM bore; the object only placed its mouth). |
| 17 | `pipeline/build` structures line | stats | **(1)/(2)/(3)** `N not screened`, `thin plates N`, `plate mouths N`, `crest from approach N`, one named line each. |
| 18 | `planar/__main__ --stage structures` + `--kml` | the records | **(1)/(2)** `plates`, `plate_refused`, `plate_stats`, `plate_mouths`, `crest_from_approach`; a KML folder for each, plus `tunnel objects refused`. |
| 19 | `airport/rebake_plan` / `emit/rebake` | `ATTR_hard_deck` objects | untouched: a thin plate is not a hard deck and is not in `pm.structures`, so nothing re-seats it (see the OWED note below). |
| 20 | `planar/basins.object_decks` | `o.hard_deck` / `o.deck_top_z` | untouched. |
| 21 | `airport/deck_signature` | `is_bridge_way` / `is_tunnel_way` | reused UNCHANGED by the plate reader — one predicate, never a second. |
| 22 | `planar/zones`, `constraints/{zones,strips}` | `retaining_wall` faces | no new role, no new ref. |
| 23 | `tools/check_grade` `LAW_FAMILIES` | the emitted roles | no new role and no new ref ⇒ no family change. |

**(1) EVERY SCREENED RESOURCE IS NAMED.**  LEMD: **105 → 184** named object refusals
over the **182** screened resources (79 verdicts that no report had ever printed —
`no wall skirt` 40, `no genuine solid` / `no crest plate` / `a stub` the rest), plus
1 named thin-plate refusal.  `Bridge3.obj` and `Bridge2.obj` are among them: they had
been refused SILENTLY for having no skirt.

**(2) THE THIN-PLATE WALL CLASS.**  The class is the GAP the wall pre-screen leaves —
solids spanning `thin_plate_min_m` (1.0) up to `least_skirt` (1.5) — over a mapped
way, with the bore run measured ALONG the plate's own axis.  Both gates were found by
measurement: without the ceiling the class read **112 "plates" at LEMD**, a
1,035 × 557 m cargo terminal spanning 37 m among them; without the along-axis test a
750 × 89 m ground slab (`STRT4.obj`) claimed seven bores that merely CROSS its 89 m
width, and took bore `-9263`'s mouths to an 88.6 m wide ramp.  With both: **4 screened,
3 plates (1 bore, 2 deck), 1 refused by name**, 4 ms.

* `wall-plate:Bridge3.obj@0` — **354.2 × 25.1 m**, solids 1.03 m, over **223.7 m of
  bore `-5931` along its axis**.  Ends 40.4987906,−3.5849926 (north) and
  40.4956006,−3.5849914 (south).
* `wall-plate:Bridge2.obj@0` — 167.9 × 89.6 m, 1.31 m, over 84.3 m of bridge way
  `-6288`; and `LEMD50.obj@0` 155.3 × 33.7 m over `-6291` + `-6288`.
* refused: `Bridge1.obj` — its longest bore run along its axis is under
  `hull_min_length_m` (it clips `-15327` for 8.2 m of 2,234); named.

**The axis is the OBJECT'S OWN BOX, not the plan hull's rectangle.**  `minimum_
rotated_rectangle` minimises AREA, so Bridge3's tapered hull read **354.2 × 20.2 m**
on an axis off the object's centre; the authored box reads **354.2 × 25.1 m** — the
owner's number.

**BAR 5 — item 5's mouth.**  `tunnel:-5931@0`: mouth 40.4980351,−3.5850028 →
**40.4987906,−3.5849926** (the object's north end, moved **83.9 m**), width
**7.0 → 25.1 m**, axis on the object's box centre (0.0 m), ramp top 96 → 204 m,
mouth floor 598.73 → 599.18.  `tunnel:-5931@1` moved 46.6 m to the object's south end.

**(3) THE MOUTH CREST IS THE ROAD'S GROUND.**  Read as a CAP rather than a switch —
`crest = min(DEM(mouth), approach_ground + bore_datum_m)`, biting only past
`split_tol_m`, where `approach_ground` is the median DEM over the approach's stations
from `bore_datum_m` out to 4 × it.  **DEVIATION, flagged for Fable review**: the
clause's literal form ("the DEM within `bore_datum_m` of the mouth rises more than
`split_tol_m` above the DEM along the approach's first stations") fires on EVERY
ordinary portal — a portal's cover stands above the road it lets out onto by
construction (measured LEMD `-5931`'s NORTH mouth: 603.83 at the cap against 602.51 on
the approach, +1.32 m, and nothing wrong with it).  The cap form fires only where the
sample cannot be the portal's cover.  **Two mouths at LEMD**:
`tunnel:-15327+-5980@0` 582.68 → 580.74 (7.05 m over its approach's 575.64) and
`tunnel:-6028@1` 584.91 → 584.32 (5.69 m over 579.22).

**BAR 6 — item 6's mouth.**  `tunnel:-5931@1`, the DEM sample that stood on the
overbridge embankment: mouth ground **610.23 → 607.01**, floor **605.13 → 601.91**,
ramp **36 → 144 m**.  The site is fixed by clause (2) (the mouth moved off the
embankment to the object's end), not by clause (3) — the cap did not need to fire
there once the mouth stood where the object says.

**(4) A TERRAIN DECK IS TIED TO ITS ENDS.**  The record now carries the ground and the
governed cell at the mapped way's two ends; the generator bounds every deck vertex
below at the higher of (trench floor + `clearance_m`) and the ENDS' PROFILE
interpolated over the way's chord, and ties each end to the governed cell's own solved
value where one stands there.  A single flat datum at "the higher of" the two ends was
MEASURED and rejected: LEMD `-6288`'s ends read 609.99 (west road) and 606.10 (east,
beside the apron), so one datum would stand 3.5 m over the apron the owner asked it to
meet.  Trench floor + clearance at that site is 604.12 and the shipped decks emitted at
**603.81–603.85**.

**DRY PLANAR REPLAY, LEMD, base vs ruled (one tree).**  `bores 68 / no on-field mouth
20 / mouth-only 27 / mouths 87 / off-field 44 / on approach 37 / duals 16 / object
corridors 1 / tunnels 50 / decks 13 / cells cut 2 / bores replaced 2 / mouths replaced
5` — **every count identical**.  Per tunnel: **46 of 50 byte-identical**; the four that
move are `-5931@0`, `-5931@1` (clause 2) and `-15327+-5980@0`, `-6028@1` (clause 3).


**OTHH, DRY PLANAR REPLAY (no build).**  `corridors 9  wall corridors 73  tunnels
37  object corridors 9  bores replaced by object 8  mouths replaced 16  decks 0
object decks 1`, and **`plate mouths 0`, `crest from approach 0`** — the two code
paths that can move OTHH geometry never fire there.  Its only plates are two 78.7 ×
18.7 m bridge decks (`OTHH_Bridge_04/05_LOD0_004.obj`, 1.06 m), both DRAPED, so they
state no datum and change nothing; `not_screened` counts 1,103 library resources the
06f gate skips before reading.  `read_corridors` builds the same corridor list it
always did (only its refusal REPORTING changed) and `read_wall_corridors` is
untouched, so the 9 object corridors and the wall-corridor set are unchanged by
construction and by measurement alike.

**THE CLOSING TEST — ONE `--engine v2` LEMD BUILD** (`LEMD_20260913T085100`, artifact
ledger `024bfdf4297b`, body `4e2c8b856dbe`, **355 s, status optimal**, ways 1,229 /
nodes 25,776, v2-verify rows 1,372; shared repo UNCHANGED).  Base = the owner's
1.0.325 products.  Harness census, cockpit block first:

* **CRITICAL motion 2 → 1** (the survivor a forbidden grade break, `strip_arc` 0.610 m
  over 58 m at 40.4625636,−3.5525152); **CRITICAL visual 0 → 0**.
* law-true **3,573 → 3,588** (+15), adjudicated **1,143 → 1,178** (+35, verdict FAIL
  both sides).  The rise is groundside: `groundside 15 → 34`.
* structures line: `... object corridors 1 (signatures 28 of 182 resources screened,
  213 not screened, thin plates 3, merged 0)  plate mouths 2  crest from approach 2
  ... tunnels 50  decks 13  cells cut 2  refused 201`.

**BARS (5).**

* **item 5 — MET.**  The mouth stands at the object's north end
  **40.4987906,−3.5849926** (moved **83.9 m**), **25.1 m** wide, axis on the object's
  own box centre (**0.0 m**, against the OSM mouth's 1.08 m).  Emitted: ramp way
  −10962 (39 nodes) at 599.19 under a rim at 604.28 — exactly `bore_datum_m` 5.10.
  Nothing is emitted within 19 m of the owner's coordinate any more: the portal moved
  to where the object says it is.
* **item 6 — MET.**  `tunnel:-5931@1`: mouth ground **610.23 → 607.01**, floor
  **605.13 → 601.91**, ramp **36 → 144 m**.  The emitted ramp climbs MONOTONICALLY
  601.05 → 609.76 and reaches the DEM at its top (z − DEM −0.99 … +0.01 over the last
  three stations) instead of being clipped into a cliff; the mouth rim stands 603.91
  against the DEM 604.15 at the mouth — **0.24 m ≤ `split_tol_m` 0.3**.
* **item 9 — MISSED, and the residual is quoted.**  The decks are no longer too low:
  `bridge_deck:-6291` **603.81 → 608.74** and `bridge_deck:-6288` **603.83 → 608.63**
  against the apron `pav92` at **606.60** — from **2.77 m BELOW** the apron to
  **2.03–2.14 m ABOVE** it.  The WEST end is met (the decks reach 609.28 / 609.31
  against the emitted ground 608.16 there, 1.1 m); the EAST end is not.
  **ATTRIBUTED**: (a) the deck FACE is clipped to the corridor, so its east edge
  stands **19.2 m short** of the mapped way's east end, where the profile between the
  ends still reads 608.3; (b) the end value is the **DEM at the way's end** (606.10),
  and the apron's own SOLVED value is 606.60 — the `end_ref` cell lookup finds no
  governed cell AT the end point (the nearest apron node is 13.4 m away), so the
  relational tie never arms.  **ROUND 2 REFUTED** (a second LEMD build,
  `LEMD_20260913T090145`, ledger `66cd3ef96192`): making the profile span the deck
  FACE's extent moved the east edge the WRONG way (608.26 → **608.81**), cost 149
  verify rows (1,372 → 1,521, `road_cross_section` 22 → 72) and dropped the solve from
  **optimal to feasible** — the deck ring's vertices ARE the corridor RIM's (one node
  carries both ways), so the deck cannot move without the rim.  Reverted and recorded
  beside the law.  **OWED**: the rim/deck vertex coupling, and whether the end's
  ground should be read by walking the mapped road to the first governed cell
  (§34 (1)'s route reading) rather than at the way's own end.
* **every refused resource named — MET.**  182 screened → **184** named object
  refusals plus 1 named plate refusal; 213 never-screened resources counted.
* **the other LEMD corridors — MET.**  46 of 50 tunnels byte-identical; the 4 that
  move are the two the owner named and the two the crest cap corrects.
* **OTHH byte-identical — MET** (dry read above).
* Twins `tests/auto_patch_v2/test_v2wallplate.py` (9, one per clause plus the class's
  two gates).  Suite `tests/auto_patch_v2 tests/test_harness.py` **1,116 passed / 1
  skipped**, run TWICE.  Targeted v1 tunnel / bridge / portal / object set: 1,333
  passed, 11 skipped, **3 pre-existing reds** (`test_tunnel_portal_fidelity::
  TestClearanceAnnulus` — 12p's standing red — plus `test_object_anchor::
  test_kclt_eight_bake_pool_end_to_end` and `test_tunnel_ramp_run_merge::
  TestItIsNotAPostPass`; this lane touches no v1 file).

**OWED / NOT DONE.**  (i) `Bridge2.obj` and `LEMD50.obj` are DECK plates over the
item-9 bridge ways, and §33 (2)'s deck clause ("the deck's top is the object's
authored top") could not be applied: both are plain `OBJECT` placements DRAPED on the
solved surface, so their authored top (Bridge2: +1.310 m over an `anchor_z` of 608.36,
the DEM at the placement) is an OFFSET, not a datum — an absolute top exists only for
an `OBJECT_MSL` placement or a hard deck.  They are read, recorded and named with that
verdict, and the owner OWES a reading of whether a draped plate should instead be
RE-SEATED onto the deck the ends give it.  (ii) §33 (3) is implemented as a CAP rather
than the clause's literal trigger — flagged above for Fable review.  (iii) item 9's
bar is missed; the two candidate refinements are named above and neither was attempted
a third time (the attempt cap).

### §33 (4) TWO-SIDED, §34 (4)–(6) AMENDED, §19.2 (2) AMENDED (Fable 2026-09-13; RULINGS 2026-09-13ai) — lane `v2rampwalk` round 2

- **§33 (4) A DECK END IS AN EQUALITY.** The deck end takes the level of the
  pavement it connects to (`deck_ends`'s face — LEMD `bridge_deck:-6288` →
  `pav92` east, the road west) within `split_tol_m` as an EQUALITY, not a
  lower bound; the deck's own profile runs between its two end levels under
  the road cap. Bar: item 9's deck within 0.3 m of the apron at its east end
  (today 1.66 m) and of the road at its west end.
- **§34 (4) A TRIMMED BOUNDARY IS DENSIFIED ON A SLOPE.** Where the ribbon
  trim's boundary runs across DEM relief, its stations are spaced so that no
  ring edge carries more than `visual_m` of DEM change (below the chord cap).
  Bar: the 8.50 m edge at 40.5331907, −3.5748496 (`zone2#23`, 18R/36L north)
  → ≤ 0.5 m; cockpit CRITICAL visual worst back under round 1's 1.63 m.
- **§34 (5) THE PORTAL RIM UNDER A DECK TAKES THE TAXI CELL'S SOLVED SURFACE.**
  The DEM carries no bridge, so `DEM(mouth)` is the road in the cutting; the
  abutment rim vertex takes an equality row to the deck cell's surface at the
  same plan point (offset 0 — the `frontage_level` Linear's mechanism) and the
  mouth's ramp floor descends from that rim. `structure_underpass.py` is
  ARMED. Bar: LEMD F-6 (40.4610903 / 40.4612284, −3.54467): mouths and ramps
  both sides, CRITICAL visual at the site 0 (armed today: 3 → 10),
  `strip_seam_tear` 0; KCLT item 3 (35.2022266, −80.9404106 /
  35.2013838, −80.9404162) mouths and ramps both sides.
- **§34 (6) THE RAMP PROFILE SITS UNDER THE CAP.** The monotone profile
  targets `ramp_max_grade − hard_tol_m / L` per edge so the emitted rows read
  under the cap after 2-dp rounding. Bar: the +847 `within_shape` rows at
  8.02 % → 0 (round 1: 2,769 → 3,616).
- **§19.2 (2)** "flush at the road's OUTER edge" reads INNER edge for a
  cell-less road (§34 (4) subtracts the ribbon whether or not a cell exists).

### §33 (4) TWO-SIDED, §34 (4)–(6) AMENDED, §19.2 (2) AMENDED (Fable 2026-09-13; RULINGS 2026-09-13ai) — lane `v2rampwalk` round 2

- **§33 (4) A DECK END IS AN EQUALITY.** The deck end takes the level of the
  pavement it connects to (`deck_ends`'s face — LEMD `bridge_deck:-6288` →
  `pav92` east, the road west) within `split_tol_m` as an EQUALITY, not a
  lower bound; the deck's own profile runs between its two end levels under
  the road cap. Bar: item 9's deck within 0.3 m of the apron at its east end
  (today 1.66 m) and of the road at its west end.
- **§34 (4) A TRIMMED BOUNDARY IS DENSIFIED ON A SLOPE.** Where the ribbon
  trim's boundary runs across DEM relief, its stations are spaced so that no
  ring edge carries more than `visual_m` of DEM change (below the chord cap).
  Bar: the 8.50 m edge at 40.5331907, −3.5748496 (`zone2#23`, 18R/36L north)
  → ≤ 0.5 m; cockpit CRITICAL visual worst back under round 1's 1.63 m.
- **§34 (5) THE PORTAL RIM UNDER A DECK TAKES THE TAXI CELL'S SOLVED SURFACE.**
  The DEM carries no bridge, so `DEM(mouth)` is the road in the cutting; the
  abutment rim vertex takes an equality row to the deck cell's surface at the
  same plan point (offset 0 — the `frontage_level` Linear's mechanism) and the
  mouth's ramp floor descends from that rim. `structure_underpass.py` is
  ARMED. Bar: LEMD F-6 (40.4610903 / 40.4612284, −3.54467): mouths and ramps
  both sides, CRITICAL visual at the site 0 (armed today: 3 → 10),
  `strip_seam_tear` 0; KCLT item 3 (35.2022266, −80.9404106 /
  35.2013838, −80.9404162) mouths and ramps both sides.
- **§34 (6) THE RAMP PROFILE SITS UNDER THE CAP.** The monotone profile
  targets `ramp_max_grade − hard_tol_m / L` per edge so the emitted rows read
  under the cap after 2-dp rounding. Bar: the +847 `within_shape` rows at
  8.02 % → 0 (round 1: 2,769 → 3,616).
- **§19.2 (2)** "flush at the road's OUTER edge" reads INNER edge for a
  cell-less road (§34 (4) subtracts the ribbon whether or not a cell exists).

## Tool: object_pad_evidence_report

| `Ortho4XP/tools/object_pad_evidence_report.py` | The question is whether a pack's OBJ8 structure rings have any EVIDENCE that a BUILDING stands there — the R18-2 building-evidence ruling's measurement surface (owner 2026-08-11b). Per structure: the vertical-structure reading (its members' own ABOVE-GRADE extents, and the fraction of its hull those building-tall members cover), the OSM half (`--icao` joins the airport's mapped building footprints; without it the OSM column reads `-` and NO absence is claimed), the library-path vouching, and the full refusal ledger of every gate upstream. **It measures nothing itself**: the structures come from `dsf_reader.read_dsf_object_building_evidence`, which runs production's own pooling, partition and `object_footprints.structure_ring` (an `evidence_out` out-parameter, so refused structures are measured too), and the coverage is `object_footprints.tall_member_coverage`, the same function the gate calls — a private re-derivation of "how tall is it over its own footprint" would be the census-wrapper defect. It also prices the two pending default-OFF defences on the pack in front of you: for each candidate `--span-sweep` value it separates the rings the EVIDENCE gate already refuses from the marginal ones, which are the gate's actual COST, and `O4_DSF_OBJECT_CONNECTOR_PREFILTER=1` re-runs it for the prefilter's. That is how round 18 ruled both OFF at HECA (span: 6 rings caught at 300 m, 3 already refused, and all 3 marginal ones real buildings including a 60,392 m² shell with a 113 m member; prefilter: 192 of 336 evidence-vouched rings dropped — the documented EGGW/EGLL failure reproduced, because in a material-split pack every texture page spans the field). It is also what caught the NAME-VOUCHING trap: HECA's Tai Models pack files its whole airport under `Airport/Hangar_Tower/`, so a path-anywhere match vouched 667 of 817 rings, phantom pads included. **GUARDED** — it resolves and parses pack objects and (with `--icao`) loads OSM in process, so it arms `build_airport.arm_shared_repo_protection` (redirects + refuse-mode guard) and refuses a swallowed block, exactly as `classify_report.py` does; `--from-json` re-renders a dump build-free and guard-free. Twins: `tests/test_dsf_object_buildings.py` (`TestVerticalStructureEvidence`, `TestEvidenceNameVouching`, `TestPendingDefencesStayOffByMeasurement`). **It is also THE OBJECT-PARTITION SINK'S REPLAY (2026-08-13, perf P3 lane G):** the reader it drives (`read_dsf_object_building_evidence`) is deliberately UNCACHED, so it runs production's whole pooling / weld / contact-graph / narrow phase on one pack in ~70 s instead of a ~570 s build — the partition is not reachable from `solve_cut --replay` (it runs before step 1, not in phases 5-6). `--count MODULE:ATTR` (repeatable) reports each named callable's call count and INCLUSIVE seconds using `profile_airport_build.CallCounter` — IMPORTED, never re-spelled — clocked on `time.process_time`, because five optimisation lanes share one machine and a WALL total there reports their load as this function's cost (measured 2026-08-13: load average 32 moved a `contact_graph` total by 65 % between two identical arms). Every run prints `rings_sha256` / `rows_sha256`, the emitted ring set and the per-structure evidence rows hashed: that pair IS the semantic gate an optimisation of the partition machinery must hold fixed, checkable per iteration instead of per build. |

| `Ortho4XP/tools/object_pad_evidence_report.py` | The question is whether a pack's OBJ8 structure rings have any EVIDENCE that a BUILDING stands there — the R18-2 building-evidence ruling's measurement surface (owner 2026-08-11b). Per structure: the vertical-structure reading (its members' own ABOVE-GRADE extents, and the fraction of its hull those building-tall members cover), the OSM half (`--icao` joins the airport's mapped building footprints; without it the OSM column reads `-` and NO absence is claimed), the library-path vouching, and the full refusal ledger of every gate upstream. **It measures nothing itself**: the structures come from `dsf_reader.read_dsf_object_building_evidence`, which runs production's own pooling, partition and `object_footprints.structure_ring` (an `evidence_out` out-parameter, so refused structures are measured too), and the coverage is `object_footprints.tall_member_coverage`, the same function the gate calls — a private re-derivation of "how tall is it over its own footprint" would be the census-wrapper defect. It also prices the two pending default-OFF defences on the pack in front of you: for each candidate `--span-sweep` value it separates the rings the EVIDENCE gate already refuses from the marginal ones, which are the gate's actual COST, and `O4_DSF_OBJECT_CONNECTOR_PREFILTER=1` re-runs it for the prefilter's. That is how round 18 ruled both OFF at HECA (span: 6 rings caught at 300 m, 3 already refused, and all 3 marginal ones real buildings including a 60,392 m² shell with a 113 m member; prefilter: 192 of 336 evidence-vouched rings dropped — the documented EGGW/EGLL failure reproduced, because in a material-split pack every texture page spans the field). It is also what caught the NAME-VOUCHING trap: HECA's Tai Models pack files its whole airport under `Airport/Hangar_Tower/`, so a path-anywhere match vouched 667 of 817 rings, phantom pads included. **GUARDED** — it resolves and parses pack objects and (with `--icao`) loads OSM in process, so it arms `build_airport.arm_shared_repo_protection` (redirects + refuse-mode guard) and refuses a swallowed block, exactly as `classify_report.py` does; `--from-json` re-renders a dump build-free and guard-free. Twins: `tests/test_dsf_object_buildings.py` (`TestVerticalStructureEvidence`, `TestEvidenceNameVouching`, `TestPendingDefencesStayOffByMeasurement`). **Since the STRUCTURE-WALLS ruling (owner 2026-08-30e) one admitted structure emits one ring PER DISJOINT FOOTPRINT PART**, so `rings emitted` is no longer the admitted-structure count: the run prints a `footprint parts` line (admitted structures → rings, how many split, how many fell back to the convex hull on degenerate geometry), each row carries `parts` / `parts_source`, and the OSM join walks `parts` slots per row and vouches a row when ANY of its parts is vouched. **It is also THE OBJECT-PARTITION SINK'S REPLAY (2026-08-13, perf P3 lane G):** the reader it drives (`read_dsf_object_building_evidence`) is deliberately UNCACHED, so it runs production's whole pooling / weld / contact-graph / narrow phase on one pack in ~70 s instead of a ~570 s build — the partition is not reachable from `solve_cut --replay` (it runs before step 1, not in phases 5-6). `--count MODULE:ATTR` (repeatable) reports each named callable's call count and INCLUSIVE seconds using `profile_airport_build.CallCounter` — IMPORTED, never re-spelled — clocked on `time.process_time`, because five optimisation lanes share one machine and a WALL total there reports their load as this function's cost (measured 2026-08-13: load average 32 moved a `contact_graph` total by 65 % between two identical arms). Every run prints `rings_sha256` / `rows_sha256`, the emitted ring set and the per-structure evidence rows hashed: that pair IS the semantic gate an optimisation of the partition machinery must hold fixed, checkable per iteration instead of per build. |

## Registered frames: KDFW

(none registered)

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; a file past 1,000 lines is a warning to reconsider its architecture (split by
  responsibility when it no longer fits; past 1,500 split before merging — owner 13bz).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

