# Brief pack — lane `v2shellwall`

Base: main `8b02d0c0` · generated 2026-09-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

A shell's trench is walled — rim at the surface, vertical walls, floor inside; airside never pulled (§33 (6) B AMENDED); VHHH TUNNEL2/tunnel5

## The brief

Founded on v2vhhhctl (RULINGS 15bh): v2objcut r3's `structure_geometry.geometry_from_trench` / `ring_for` emits a signature-B trench whose ring vertices are the airside's own vertices with the floor's rows on them — the trench has no wall, so the airside network is pulled down 6.5 m around TUNNEL2_DONE/tunnel5. Sites: `planar/structure_geometry.py` (the ring: split into RIM ring = the surrounding surface's vertices, no floor row; FLOOR ring inset by the wall thickness at the authored plate level along the cover's profile; the WALL band between as a breakline pair — reuse the emission OTHH's `retaining_wall`/`tunnel_wall` cells use in `planar/structures.py` (`new_cells.append(("retaining_wall","tunnel_wall",…))`) and the sea wall's breakline pair (§37 (11), `constraints/water.py` / `planar/zones.py`)), `planar/structures.py` `build_structures` (the `_ring` closure, cells), `airport/object_cut.py` (`shell_reading`: publish the inner-face line and wall thickness), `constraints/structures.py` (the floor rows must bind the FLOOR ring only; the rim carries the neighbours' law), `emit/*` (the wall cells' faces). Consumer census first (08-30l): every reader of the trench ring / `tunnel_ramp` faces / `structure_rim` / `retaining_wall` cells / `object_cut_*` families / `ramp_in_strip`. Artifacts: control/arm patches at /tmp/harness/VHHH_20260915T120714.osm and VHHH_20260915T122604.osm (+ .axes.json); census dumps under scratchpad/v2vhhhctl/. Other lanes: v2othhdet (object readers — do not touch tunnel_objects.py/wall_corridors.py beyond publishing fields), v2shoulderband (classify/roles, runway_profile, check_grade `runway_step`). Do not touch solve/design*.py.

## Bars

- VHHH, matched against the registered CONTROL frame (VHHH_20260915T120714 @ f912ba81, body 8c8ef471eaab) and the ARM (VHHH_20260915T122604 @ 118d2c40, body 38e3a2678b5c): airside vertices (junction/apron/taxi family) within 200 m of the five shells moved vs the CONTROL ≤ 0.02 m — count of movers named (today: up to 6.5 m).
- Off-DEM > 0.5 m maxima by role back to the control's: junction ≤ 1.45 m, primary_parallel ≤ 1.55, cross_connector ≤ 0.96, apron ≤ 2.57, graded_strip ≤ 1.90 (today 6.2–6.5); apron bodies' own-plane worst back to ≥ −0.3 m (today −5.23).
- Census (harness/census.py, one invocation, control → arm → fix): LAW-TRUE 4,845 → ≤ 1,531 + the trenches' own rows (named by family); ADJUDICATED 1,472 → ≤ 121 + named; `within_shape` 2,482 → ≈ 168 + named; `airside_no_step` 625 → ≈ 8 + named; cockpit CRITICAL motion 1 → 0.
- The shells still cut: `object_cut_depth` 0 rows on all five; `object_cut_offset` ≤ r3's (TUNNEL2's four named or gone); the owner's site tunnel5 ring vertices outside the wall line 0; the walls emitted as vertical bands (breakline pairs) — the wall count and total length per shell named; the ramp inside the walls at the cover's stations.
- OTHH: `tunnel_wall`/`retaining_wall` corridors byte-identical (same emission path) — dry pair + the OTHH replay pair census unchanged; LEMD dry pair byte-identical bar Bridge4's corridor if it shares the path (name it).
- Suite by FAILED lines (zero); ONE VHHH airport-path build as the closing test (tile builds allowed on main ≥ 6f6c28ed but not needed); `shared repo UNCHANGED` quoted.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/planar/structure_geometry.py`, `Ortho4XP/src/auto_patch_v2/planar/structures.py`, `Ortho4XP/src/auto_patch_v2/airport/object_cut.py`, `Ortho4XP/src/auto_patch_v2/constraints/structures.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/solve/design.py`, `Ortho4XP/src/auto_patch_v2/classify/roles.py`, `Ortho4XP/src/auto_patch_v2/airport/tunnel_objects.py`

## Spec (design-surface) §33 (6)

## §33 (6) THE PACK'S STRUCTURE OBJECTS ARE THE CUT GEOMETRY — THREE SIGNATURES, ONE READER (owner RULINGS 2026-09-15e items 1/3/4/6, 15g; 14av; Fable 2026-09-15j) — lane `v2objcut`

**The intent (owner, three airports).**  "The tunnels have object based
interior walls and hard covers where needed (like EGLL does), so we need
to cut our trenches based on those … align with the provided ramp and
walls" (VHHH); "use the provided surface wall objects as a precise guide
for where to cut the mouth, ramp should stay within the wall boundaries
… the terrain grades under the wall object and the wall sits on top of
the tunnel edges" (LEMD); "the two edge wall objects … should be used
as guides for where the author wants the bridge … grade the bridge so
those sit smoothly on either edge of it" (LEMD).  THE PACK'S STRUCTURAL
OBJECTS ARE THE AUTHOR'S GEOMETRY; the mapped way is the ROUTE (the
seed, and the connection to the network beyond the object's ends) and
nothing more.  Where an object of any signature below covers a bore or
a crossing, the cut's PLAN, DEPTH, COVERED EXTENT and STATIONS derive
from the object.

**The three signatures (measured 15h/15j; detected by GEOMETRY, never by
name, never by ICAO).**

* **A — crested walls (OTHH, 14av):** solids descending below the
  object's zero with a crest plate ≥ `plate_min_height_m` above it
  (−15 … +5, −10 … +9.55).  Already LAW C (`airport/wall_corridors.py`);
  the wall's inner faces are the trench walls, the crest is the rim.
  The per-airport affordance `kerb_wall_corridors` (`law/airports.toml`,
  OTHH only) is RETIRED: the signature admits, not the ICAO.
* **B — shell + flush hard cover (VHHH, EGLL):** a SHELL object whose
  largest horizontal plate lies ≥ 2 m below its zero (the FLOOR: −6.01
  / −6.54 / −8.95 / −9.01 at VHHH, 733–16,759 m²; EGLL −4 … −7) and, at
  the same placement (position within 1 m, same heading) or inside the
  same object, a COVER whose `HARD_DECK` plate at |y| ≤ 1 m covers part
  of the shell's plan (VHHH `_TN`: 427–11,254 m²; EGLL `N.obj` /
  `Na.obj`).  Today this class falls through every reader:
  `tunnel_objects.py:717` (a floor witness ⇒ basins), the §2 crest-
  plate rule (no plate above zero), `thin_plates` (1.0–1.5 m), LAW C
  (OTHH only).  RULED: the shell's per-band wall line (NOT the convex
  hull — the shells are L-shaped) is the trench outline; the FLOOR
  PLATE's level in the seated frame is the floor (the depth is AUTHORED
  — it overrides `bore_datum_m`, which is the law for UNAUTHORED bores
  only); the cover's flat plate is the covered extent; the cover's
  descending plate profile (tunnel5: 0.00 → −0.91 → −1.71 → −6.01 over
  25 m bins) gives the ramp STATIONS; `HARD_DECK` is the machine-
  readable marker of the cover.  The shell is never a basin.
* **C — thin surface walls and parapets (LEMD):** solids < 1.5 m tall,
  long (length ≥ 20 × height), narrow (≤ 2 m), sitting on the surface
  (y_min ≥ −0.1).  (C1) A parallel PAIR along a bore (Bridge3: 354 × 25.1
  m, 1.03 m; spacing 5–40 m, overlap ≥ 50 %) is the trench's TOP EDGES:
  the trench lies between the pair's inner faces, runs the pair's FULL
  length, its mouths at the pair's ends, its open ramps beyond them
  (item 4: from the wall's south end toward 40.4951833); the wall's
  foot line is the rim at grade — the terrain grades under the wall and
  the wall sits on the trench edge; the depth is `bore_datum_m` (no
  authored floor).  (C2) A single thin wall in a U (Bridge4, 2.01 m,
  admitted today): the ring follows the wall's INNER-FACE polyline with
  chord error ≤ half the band (0.75 m) — never a 9-station chord cut of
  a curved U — and runs to the wall's END (17 m short today).  (C3) A
  parapet PAIR flanking a mapped bridge way (Bridge2: 0.92 m, 25.6 m
  apart) is the DECK's lateral extent: the deck is centred on the pair
  and as wide as their inner spacing, so both parapets sit on the deck
  edges; the OSM carriageway pair gives the route only (today: 8–9 m
  south of the parapets).  The §33 (2) plate reading of these objects
  (a width and a mouth station) and the 1.5 m skirt pre-screen are
  SUPERSEDED for signature C; §33 (2) (a)'s clamp to the bore way's end
  is superseded by C1 (the object's end IS the mouth) — the 14bl item
  7/8 runaway it fixed was the plate's overhang beyond a bore with no
  wall pair, which C1's pairing test excludes.

**One reader.**  `airport/tunnel_objects.py` (or a successor
`airport/object_cut.py`) screens every placed object ONCE for A/B/C and
publishes ONE record class (`ObjectCut`: outline polyline per band,
floor level or None, covered extent, stations, ends, signature) that
`planar/structures.py` / `structure_approach.py` / `structure_deck.py` /
`wall_corridor_ramps.py` consume; `basins.py` sees none of them.
Consumer census at spec time (RULINGS 2026-08-30l): every reader of
tunnel objects, plates, basins with object carriers, wall corridors and
deck groups — one table before the first edit.  Where an OSM bore and an
object disagree, the OBJECT wins inside its extent; the mapped way
carries the corridor beyond it (§34 (12) still gates whether the tunnel
serves the field at all).  `[verify]` gains `object_cut_offset`: the
worst distance of an emitted ring vertex outside its object's wall line
(bar 0.5 m) and `object_cut_depth`: floor vs the authored floor plate
(bar 0.10 m).

**MEASURED** (lane `v2objcut`, branch `claude/v2objcut` off main `bf518d0c`;
ONE tree, the shared corpus.  Synthetic-first: dry `planar --stage structures`
replays at VHHH / LEMD / OTHH and a direct OBJ8 inventory of the VHHH tunnel
pair before the one VHHH build.)

**§33 (6) CONSUMER CENSUS (RULINGS 2026-08-30l), one table, written BEFORE the
first code edit.**  Every reader of the pack's tunnel objects, thin plates,
floor-witness basins, wall corridors and deck groups, and what §33 (6) does to
it.  The column "Ruled" is the decision this lane implements at that site; a
row marked UNCHANGED is a site the lane does not edit and the measurement must
prove untouched.

| # | Reader (file · symbol) | What it reads | Ruled |
|---|---|---|---|
| 1 | `airport/obj8.read_placed_objects` · `_witness` | every placement → `PlacedObject.witnesses` (the FLOOR PLATE `admission_depth_m` under the local ground) | UNCHANGED as a reading. The signature screen runs AFTER it and SUBTRACTS its own placements from the witnessed set; the witness itself is still what signature B's floor plate is found through (one parse, never a second). |
| 2 | `airport/basin_witness.read_objects` | the pack, memoised on `ResourceCache` | UNCHANGED — one parse for the whole build. |
| 3 | `airport/basin_witness.basin_member_ids` | `o.witnesses` → the placements exempt from the skirt reader and the re-seat below-grade skip (10ax (2)) | **CHANGED**: a placement the object-cut screen claims (A/B/C) is NOT a basin member. It is still exempt at both sites — it is a trench, not a foundation — so the exemption set is `witnesses ∪ object_cut`, one derivation (`airport/object_cut.cut_placement_ids`). |
| 4 | `planar/basins.build_basins` · `witnessed = [o for o in objects if o.witnesses]` | the basin REGION, rim, floor, cut | **CHANGED, one derivation site**: the intake filters out every placement the object-cut screen claims. "The shell is never a basin" (§33 (6) B). Bar: signature-A/B/C objects reaching `build_basins` = 0, count named per airport. |
| 5 | `planar/basins.object_decks` | `o.hard_deck` / `deck_top_z` → object bridges | UNCHANGED in code. A signature-B COVER is a `HARD_DECK` plate at `|y| ≤ 1 m`; it is the tunnel's covered extent, not a bridge deck over open ground — it is excluded with its shell (row 4's same set), and the count is named. |
| 6 | `airport/tunnel_objects.read_corridors` | OBJ8 → `Corridor` (crest plate + skirt, LAW A/B) | **CHANGED**: the `o.witnesses` hand-off at `:726` no longer sends a floor-witness placement straight to basins — it is screened for signature B first (shell + flush hard cover). Signature A/C readings are unchanged; every refusal still named (§33 (1)). |
| 7 | `airport/tunnel_walls.read_wall_lines` / `midline` / `stations_along` | a crest plate → inner faces, axis, stations | **CHANGED for C2 only**: the station spacing along a CURVED inner face is bounded so the emitted chord error stays ≤ half the band (0.75 m); a straight corridor's stations are unmoved (bit-identical at OTHH). |
| 8 | `airport/wall_corridors.read_wall_corridors` (LAW C bands/pairs) | vertical-only bands → kerb corridors + garage ramps | **CHANGED**: the per-airport affordance `kerb_wall_corridors` is RETIRED; the admission is signature A read on the pair's OWN resource (solids descending `min_wall_depth_m` below the object's zero WITH a crest plate `plate_min_height_m` above it). Bar: OTHH's corridor set identical OFF→ON, every difference named. |
| 9 | `law/airports.toml` · `airports_schema.Affordances.kerb_wall_corridors` | the ICAO switch | **DELETED** (key and field). `group_span_max_m` stays. |
| 10 | `airport/thin_plates.read_plates` | 1.0–1.5 m solids over a mapped way → `WallPlate` (a width + an axis) | **CHANGED**: signature C. A plate whose own solids read as a parallel PAIR of thin bands publishes the pair's INNER faces (C1 axis + inner spacing), not the authored box; a parapet pair flanking a mapped bridge way publishes the DECK extent (C3). The 1.5 m skirt pre-screen is superseded for C, so a C object is admitted whether or not `read_corridors` refused it for a skirt. |
| 11 | `planar/structure_approach.apply_plates` | `Mouth` ← `WallPlate` (§33 (2)) | **CHANGED**: for a C1 pair the §33 (2) (a) clamp is SUPERSEDED — the object's end IS the mouth and the ramp runs open beyond it; the mouth takes the pair's INNER spacing as its width and the pair's midline as its axis. For a plate with no pair (the 14bl item 7/8 runaway) the clamp stands exactly as it is. |
| 12 | `planar/structure_approach.mouths()` / `merge_duals` | bore ends → `Mouth` | UNCHANGED (lane `v2vmmcshore` owns `mouths()`; `apply_plates` runs after it and rewrites `xy` / `inward` / `width_m` / `approach` only). |
| 13 | `planar/structure_approach.field_region_for` (§29 gate) | cover ∪ corridors ⊕ standoff | UNCHANGED and runs FIRST — the gate judges the MAPPED end, never the moved one. §34 (12) (lane `v2vmmcshore`) still decides whether a tunnel is built at all. |
| 14 | `planar/object_corridor.mouth_covered_by` | mouth xy vs corridor footprints (05n-3 precedence) | UNCHANGED in code; a signature-B shell now HAS a footprint here, so its OSM mouths are replaced by the object's — that is §33 (6)'s "the OBJECT wins inside its extent", measured as `mouths_replaced_by_object`. |
| 15 | `planar/object_corridor.object_groups` / `climb_path` / `_interp` | `Corridor` → `Group` (half-width and rim per station) | UNCHANGED — a signature-B corridor is a `Corridor` like any other; its stations come from the shell's own wall line. |
| 16 | `planar/object_corridor.trench_outside_m` | emitted ramp rings vs the corridor's trench | UNCHANGED; it is the existing instrument the new `object_cut_offset` family generalises (ring vertex vs the object's WALL LINE, every signature). |
| 17 | `planar/structures.build_structures` | `corridors`, `plates`, `objects`, cells | UNCHANGED (another lane's file this round): every §33 (6) reading reaches it through the existing `corridors=` / `plates=` / `objects=` arguments. No new argument, no re-ordering. |
| 18 | `planar/structures` ramp geometry (`geometry`, `_pad_hit`, `beyond_strip`) | the mouth's width / inward | UNCHANGED; it reads the width `apply_plates` hands it, so a C1 ramp is the pair's inner spacing by construction. |
| 19 | `planar/structure_deck.deck_intervals` / `deck_groups` / `deck_items` | mapped bridge ways crossing a corridor → `Deck` | **CHANGED (C3 only)**: where a parapet PAIR flanks the deck's mapped way, the deck face is centred on the pair and as wide as their inner spacing; with no pair the carriageway width stands exactly as today. |
| 20 | `planar/structure_deck.deck_ends` (§33 (4)) | the way's two ends → the deck's end levels | UNCHANGED — C3 changes the deck's LATERAL extent only, never its profile. |
| 21 | `planar/structure_deck.object_deck_intervals` | `object_decks` (hard-deck objects) over a corridor | UNCHANGED in code; row 5's exclusion keeps a signature-B cover out of it (it is the tunnel's own roof, not a deck over it). |
| 22 | `planar/wall_corridor_ramps.wall_corridor_groups` / `wall_corridor_profile` / `stop_and_steepen` | LAW C records → ramp groups and profiles | UNCHANGED in code; row 8's admission change is the only thing that can alter what reaches it. Bar: OTHH ramps identical. |
| 23 | `planar/wall_corridor_ramps.road_true_edge` / `airside_stops` / `locked_road_stops` | where a ramp stops (§34 (9)/(10)) | UNCHANGED. |
| 24 | `airport/skirt.skirted_placements` (10ag) | basin members exempt from the skirt drop | **CHANGED through row 3's one derivation** — the exemption set grows by the object-cut placements; no second spelling. |
| 25 | `airport/rebake_plan` below-grade skip (09w (1)) | basin members exempt | **CHANGED through row 3's one derivation**; a tunnel shell's below-zero geometry is not a foundation. |
| 26 | `airport/rebake_plan` / `emit/rebake` `ATTR_hard_deck` re-seat | hard-deck objects | UNCHANGED — the shell and its cover keep the seats the object stage gives them; this lane re-seats nothing (13r's "a draped deck plate rides the terrain deck the mesh gives it"). |
| 27 | `airport/deck_signature.classify` / `is_bridge_way` / `is_tunnel_way` | the deck families and the two way predicates | REUSED UNCHANGED by every signature — one predicate, never a second (the 13r rule). |
| 28 | `pipeline/publication.tunnel_objects` | `tn.source != "osm"` | UNCHANGED: a C1/C3 mouth stays `source = "osm"` (it IS an OSM bore, the object only placed and sized its portal); a B shell is an object corridor and reads `object` as every corridor does today. |
| 29 | `pipeline/build` / `planar/__main__ --stage structures` structures line + KML | the stats | **CHANGED, reporting only**: `object cuts N (A n / B n / C n)`, `basin placements claimed by a cut N`, and one named line per refusal — every screened resource still named (§33 (1)). |
| 30 | `verify/structures.tunnel_mouth_canonical` | cap crest − ramp mouth = `bore_datum_m` | **READ, NOT CHANGED**: signature B's floor is AUTHORED and overrides `bore_datum_m`, so a B mouth is legitimately deeper; the family is quoted before → after and every new row named. §33 (5) (lane `v2lemdstruct2`) owns the shallow case. |
| 31 | `verify/structures.tunnel_deck_clearance` | min(deck) − max(ramp) ≥ `clearance_m` | UNCHANGED. |
| 32 | `verify/*` + `tools/check_grade.LAW_FAMILIES` | the emitted roles | **NEW families** `object_cut_offset` (worst emitted ring vertex outside its object's wall line, bar 0.5 m) and `object_cut_depth` (emitted floor vs the authored floor plate, bar 0.10 m), registered in `LAW_FAMILIES` with twins in `tests/test_harness.py` — the census cannot omit a family (the twin fails). |
| 33 | `emit/osm_adapter` sidecar `road_bridge_decks` | always empty in v2 | UNCHANGED. |
| 34 | `planar/zones.py`, `planar/structure_underpass.py`, `constraints/cluster_pad.py`, `solve/design*.py` | other lanes' files this round | NOT TOUCHED. |

**THE TWO FAMILIES SELECT BY OVERLAP, NOT BY REF.**  An emitted ramp face's
`ref` is its ROLE (`tunnel_ramp`), the same string for every corridor in the
patch (`planar/structures.py:713`), so a ref join would price every ramp of the
airport against every object.  A face with at least one vertex INSIDE the wall
line is that object's cut; a face wholly outside is another corridor's and is
not read.  The published `outline_ll` is the walls ∪ trench EXTERIOR ring, so
for a hairpin shell (VHHH `tunnel5`) the region is slightly LOOSER than the
trench — the family can under-report, never over-report.

**CENSUS ROWS THE MEASUREMENT CORRECTED.**  Rows 3 / 24 / 25 ruled that the
skirt and re-seat exemption set would grow to `witnesses ∪ object_cut`.  It
does not need to: a signature-B shell already carries a floor witness, so it
is already in `basin_member_ids`, and §33 (6) removes it from the basin
**intake** only (row 4).  `airport/skirt.py` and `airport/rebake_plan.py` are
therefore UNCHANGED, and `cut_placement_ids` has exactly one consumer.  Row 8
/ 9 (the affordance's retirement) is REFUTED — see (A) below.  Rows 10 / 11 /
19 (signature C) are NOT DONE this round — see (C).

**(B) THE SHELL + FLUSH HARD COVER — DONE.**  `airport/object_cut.py` (NEW,
440 lines) screens every placement once and publishes `ObjectCut`;
`tunnel_objects.shell_corridor` turns one into the SAME `Corridor` every other
object corridor is, so `planar/structures.py` is not edited at all and the
05n-3 per-mouth precedence, `object_groups` and `trench_outside_m` read it
unchanged.  Three readings are the object's and not the law's:

* **The trench outline is the plan union of the shell's NON-VERTICAL faces**
  (floor plates and ramps alike), never a hull: VHHH `tunnel5_done.obj` is a
  U-turn ramp whose 9,290 m² trench sits in a 245.9 × 73.2 m box.
* **The wall line is the plan segments of its VERTICAL faces**, and a run of
  the trench ring with no wall face standing on it is a PORTAL.  `tunnel5`
  reads exactly two open runs of its 29 ring edges (22.2 m and 17.0 m) and 27
  walled ones; `tunnel3` reads one portal spanning TWO ring edges (44.4 m +
  2.5 m), which is why the open edges are joined into RUNS before they are
  counted; `tunnel2` reads FIVE portals (a 28,525 m² multi-portal shell) and
  takes its two longest as its ends, the others standing inside a wall chain.
* **The floor is the DEEPEST plate-worthy bin, not the largest-area one.**  A
  shell's RAMPS are near-horizontal too (`tunnel5`'s read |n_y| = 0.998 over
  100 m), so the largest bin of horizontal faces is a ramp's mid-height:
  measured `tunnel1` a 1,514 m² ramp bin at −2.50 against the 733 m² floor at
  −6.95, `tunnel4` 2,672 m² at −5.25 against 454 m² at −9.01.

**TWO DEVIATIONS from §33 (6) B's text, both forced by measurement** (the 13r
precedent — the spec text yields to the measurement):

1. **The cover is a SECOND PLACEMENT, never the shell itself.**  §33 (6) B
   allows "or inside the same object"; that form admitted VHHH's `sea_X.obj`
   — a sea barrier whose own flush hard deck covers its own −28.20 m plate —
   as a 104.9 m wide, 22.88 m deep "tunnel".
2. **The object must COVER A BORE OR A CROSSING**, which is §33 (6)'s own
   opening clause read as a GATE: a mapped tunnel way ending at a portal
   (`bore_end_tolerance_m`) or running through the trench.  Without it
   `sea_X.obj` + `sea.obj` (a 112,376 m² flush hard deck — the SEA SURFACE)
   still read as a corridor 177 m off the north shore.

**THE MATCHED DRY REPLAY PAIRS** (`planar --stage structures`, ONE tree per
arm, one machine, the shared corpus, the lane-local mod-cache overlay; base =
main `106459fa` in its own ritual worktree, lane = `claude/v2objcut`).

* **OTHH — NOTHING MOVES.**  `corridors`, `tunnels`, `wall_corridors`,
  `basins`, `plates` and `door_wells` all **BYTE-IDENTICAL** (9 / 44 / 73 / 10
  / 2 / 4); the only difference is **+51 named §33 (6) refusals** (28 "no
  near-horizontal solid face stands 2.0 m under the object's zero", 9 "not a
  tunnel floor", 6 "the trench ring has 0 open ends", 3 shells with no flush
  cover, each by resource).  The §33 (1) discipline holds for the new reader.
* **LEMD — NOTHING MOVES.**  The same six arrays BYTE-IDENTICAL (1 / 50 / 0 /
  1 / 3 / 0), **+25 named refusals**.  `plate_mouths` 2 → 2,
  `crest_from_approach` 2 → 2, `underpasses` 1 → 1.
* **VHHH — five object cuts read, three built.**  `corridors` **0 → 5** with
  the AUTHORED floors: `TUNNEL2_DONE` **0.78**, `tunnel1_done` **0.37**,
  `tunnel3_done` **−1.63**, `tunnel4_done` **−1.69**, `tunnel5_done`
  **1.30** — against the bar's 0.77 / 0.36 / −1.63 / −1.69 / 1.31, every one
  inside the 0.10 m bar.  `wall_corridors` **0 → 0** (the affordance stands),
  `basins` **70 → 70 and the population IDENTICAL** by (objects, area) — the
  five shells and their five covers were never separate pits, and the claim
  (`shell_claimed`: 10 placements) keeps it that way.  `tunnels` 28 → 23: nine
  OSM bore tunnels at those sites are replaced by the objects (05n-3), which
  read **mouth_z 2.22 = DEM − `bore_datum_m`** on the base arm against the
  objects' own 0.37 / −1.63 / −1.69.

**THE VHHH MISS, NAMED.**  Two of the five cuts — `tunnel5_done` (THE OWNER'S
SITE 22.3038632, 113.9088362) and `TUNNEL2_DONE` — are refused DOWNSTREAM by
`planar/structures.py`'s ramp-ring builder: *"the approach bends tighter than
the corridor (ramp or wall ring self-intersects)"*.  Both are HAIRPINS —
`tunnel5` is a U-turn ramp whose 413 m axis reverses on itself, `TUNNEL2` a
1,110 m multi-portal corridor — and a ring built by OFFSETTING such an axis by
its half widths folds.  The reading is right (floor 1.30 against the authored
1.31, trench 9,290 m², two portals) and the corridor is refused for a reason
that has nothing to do with §33 (6): the emitter must follow the OBJECT'S OWN
trench polygon rather than offset an axis.  That is a `planar/structures.py`
change, which this lane's brief reserves to another lane, so it is REPORTED,
not attempted.

**THE BEFORE READING ON THE OWNER'S OWN 1.0.340 VHHH PRODUCTS** (the shipped
patch under `Patches/+20+110/+22+113/`, read against each object's published
wall line — no build, nothing written).  Per shell: emitted `tunnel_ramp` /
`structure_rim` vertices standing outside the object's wall line, and the
emitted floor against the authored one:

| object | vertices | outside (> 0.5 m) | worst | emitted floor | authored | miss |
|---|---|---|---|---|---|---|
| `tunnel5_done` | 147 | **85** | 75.80 m | 2.21 | 1.31 | **0.90 m** |
| `tunnel1_done` | 25 | **19** | 81.48 m | 2.22 | 0.37 | **1.85 m** |
| `TUNNEL2_DONE` | 171 | **111** | 83.74 m | 2.22 | 0.78 | **1.44 m** |
| `tunnel3_done` | 46 | **27** | 86.12 m | 2.22 | −1.63 | **3.85 m** |
| `tunnel4_done` | 40 | **26** | 79.67 m | 2.22 | −1.69 | **3.91 m** |

That is `object_cut_offset` 268 rows / worst 86.12 m and `object_cut_depth`
0.90–3.91 m on the shipped build, and it reproduces the 15j scout's
"0.92–3.91 m too shallow" exactly.  The AFTER numbers are the closing VHHH
build's, which this lane could not run (see below).

**(A) THE AFFORDANCE'S RETIREMENT IS REFUTED — one dry VHHH replay.**  The
crested-wall predicate (solids under the object's own zero WITH a crest plate
`plate_min_area_m2` standing `plate_min_height_m` above it) admits an ordinary
BUILDING, because a building has a roof.  Measured at VHHH: wall corridors
**0 → 116** (bay 28, level 88), **every one of them inside `CITY2.obj`** — a
city-block object off the field whose foundation walls descend 6.4–8.5 m under
their ground — plus 75 narrow-cut candidates and three `CITY1.obj` families.
No depth threshold repairs it: OTHH's own admitted bays are 1.35 m deep.  This
is RULINGS 2026-09-10ap's seven rounds at a THIRD airport.  The predicate is
DELETED (not kept gated); `kerb_wall_corridors` STANDS in `law/airports.toml`
with the refutation recorded beside the gate, and §33 (6) A is an INTENT
QUESTION for the owner, not a mechanism.

**NO CLOSING BUILD.**  RULINGS 2026-09-15u: `+22+113`'s cached road layers
predate the `ROAD_CACHE_TAG_SCHEMA` bump, so the first harness build on that
tile REWRITES the shared repo's road layer (the LEMD `+40-004` build was
flagged CONTAMINATED) and, since `v2schemarefuse`, REFUSES by name.  The
refresh ledger carries NO `osm_layers` refresh for `+22+113` at all.  The
build AWAITS the owner's `--refresh-data osm_layers` on that tile; the lane
ran no build and no `--refresh-data`.

**(C) SIGNATURE C IS NOT DONE, and the measurement that stopped it.**  The
BAND READING landed (`object_cut.thin_bands` / `band_pair`, over LAW C's own
`wall_geometry` machinery — a band is a STRAIGHT RUN of vertical faces, never
a component: LEMD `Bridge3.obj`'s two components read 73 × 16 m and 58 × 15 m
convex hulls and are not walls by any gate, while comp 0's vertical faces
split into the PAIR, two 73.0 / 73.1 m runs 1.00 m thick 14.02 m apart).  It
is NOT wired into `apply_plates` or `structure_deck` because the reading
contradicts C1's premise: **`Bridge3.obj` carries 280 triangles in two
components at its two ENDS (z −354.2…−281.0 and z −57.6…0); 224 m of its
354.2 m box carry no solid at all.**  So "a parallel PAIR along a bore …
[whose] trench … runs the pair's FULL length" does not describe this object —
its walls are two short MOUTH pieces, and 25.1 m is its authored BOX, not its
wall spacing (the pair's inner faces are 14.02 m apart).  `Bridge2.obj` reads
two 42.0 / 39.5 m bands at 157.5° and 67.1° — perpendicular, no pair;
`Bridge4.obj` reads no band at all under the surface gates (2.016 m tall).
Rather than guess the owner's geometry a third time, the reading is published
and measured and the INTENT goes to the owner (the standing "mechanisms get
measured, INTENT gets asked" law).

## §33 (6) MEASURED AND RE-FOUNDED (lane v2objcut r1 e178702f; Fable 2026-09-15; RULINGS 2026-09-15x) — B reads; A refuted by geometry alone; C re-founded on the objects as they are

**B — READS.**  All five VHHH shells admitted with their AUTHORED floors
(1.30 / 0.37 / 0.78 / −1.63 / −1.69 against bars 1.31 / 0.36 / 0.77 /
−1.63 / −1.69; the OSM arm 2.22 for all), corridors 0 → 5, tunnels 28 →
23 (nine OSM bores replaced), basins identical by (object, area) — 10
placements claimed.  OTHH and LEMD byte-identical on six populations.
MISS: `tunnel5_done` (the owner's site, a 413 m U-turn) and `TUNNEL2_
DONE` are refused by the RING BUILDER (`planar/structures.py`: "the
approach bends tighter than the corridor — ramp or wall ring self-
intersects") — a ring built by OFFSETTING AN AXIS folds on a hairpin.
RULED (r2): for a signature-B corridor the emitter takes the object's
OWN trench polygon (the shell's per-band wall line, closed by the
cover's ends) as the ring — no axis offset; the stations from the
cover's profile.  `object_cut_offset` / `object_cut_depth` families
land (select by overlap, not by ref).

**A — REFUTED by geometry alone.**  Retiring `kerb_wall_corridors` for
the crested signature admitted 116 corridors at VHHH, every one inside
`CITY2.obj` (a city-block object: a building has a roof) — RULINGS 10ap
at a third airport; no depth threshold separates them (OTHH's admitted
bays are 1.35 m deep).  RULED: the predicate is deleted; the per-airport
affordance STANDS as the gate for A until a discriminator is MEASURED
(candidates for a later scout: a roof plate spanning the walls; the
object's footprint on airside vs off-field; the pack's placement on a
pad).  Not an owner question.

**C — RE-FOUNDED on the measured objects.**  `Bridge3.obj` is NOT a
354 m wall pair: its 280 triangles sit in two components at its two
ENDS (z −354.2…−281.0 and −57.6…0), each a pair of 73.0 / 73.1 m walls
**14.02 m** apart; 224 m of the box carries no solid.  The author marked
the two MOUTHS; the bore between them is COVERED.  `Bridge2.obj` reads
two perpendicular bands (no pair); `Bridge4.obj` no straight band (a
curved U).  RULED: (C1′) a thin-wall PAIR (parallel straight bands,
spacing 5–40 m, overlap ≥ 50 %) marks a MOUTH RAMP: the ramp lies
between the pair's inner faces, runs the pair's length, its mouth at
the end nearer the bore's covered stretch and its top at the outer end;
the bore between two such pairs (or between a pair and an authored
deck) is covered; the walls sit on the ramp's top edges (the foot line
is the rim at grade).  Item 3's ramp lies inside the north pair; item
4's inside the south pair, its top at the pair's outer end (toward
40.4951833).  (C2′) a band is a POLYLINE of contiguous vertical faces,
straight or curved (Bridge4's U): the ring follows its inner face with
chord error ≤ 0.75 m and runs to its end.  (C3′) parapets: the lane
reports Bridge2's two bands with coordinates and headings against the
deck before any rule — if they flank the deck (parallel, each side)
the deck is centred on them; if perpendicular they are abutment walls
at the deck's ENDS and mark its span.  Every C rule is measured on the
three LEMD objects by dry pair before it is wired.

## §33 (6) B AMENDED — A SHELL'S TRENCH IS WALLED: THE RIM STAYS AT THE SURROUNDING SURFACE, THE OBJECT'S WALLS ARE VERTICAL, AIRSIDE IS NEVER PULLED (Fable 2026-09-15; RULINGS 2026-09-15bh; lane v2vhhhctl measurement) — lane `v2shellwall`

**The measurement (VHHH, matched pair f912ba81 → d94db789, one
source merge, both builds clean).**  Cutting `TUNNEL2_DONE` (1,109.9 m,
21.1 m wide, floor 0.777, depth 6.54 m) and `tunnel5_done` (413.2 m,
22.8 m, floor 1.304, depth 6.01 m — the owner's site) to their authored
floors was RIGHT at the shells (`object_cut_depth` 0 rows; offsets 0
bar TUNNEL2's four) and WRONG around them: the solve's active set
4,177 → 11,253, objective 19,143 → 375,231; off-DEM > 0.5 m maxima
junction 1.45 → 6.22 m, primary_parallel 1.55 → 6.46, cross_connector
0.96 → 6.47, apron 2.57 → 6.48; apron bodies' own planes −0.27 → −5.23
m; design targets missed apron max 1.70 m, taxi 1.35 m; LAW-TRUE 1,531
→ 4,845, ADJUDICATED 121 → 1,472, 87 % of the new rows within 500 m of
TUNNEL2 (taxiway-network grade rows: `within_shape` cross_connector /
primary_parallel, `airside_no_step`).  The trench ring's vertices are
shared with the airside faces and the floor's rows pull them down —
the trench has no wall.  §37 (11)'s sea wall contributed nothing (4 →
4, identical coordinates); the r3 report's "1,713 → 4,845" understated
the rise (the shipped 1.0.340 patch was worse than the control).

**RULED.**  A signature-B trench is a WALLED cut, emitted as OTHH's
`retaining_wall` / `tunnel_wall` cells are (§33 (1), 14av): (1) the RIM
ring is the surrounding design surface — its vertices are the
airside/ground vertices they already are and carry NO floor row;
airside beside a shell never moves (§16g (10) (5)'s bar, 0 > 0.02 m
against the control); (2) the FLOOR ring is a separate ring inside the
rim by the wall's thickness (the object's inner-face line), at the
authored floor plate's level along the object's own profile (the
cover's stations); (3) between them the WALL: a vertical band (the
breakline pair the sea wall and the OTHH walls already use) — the
object's interior walls are the retaining walls, the terrain does not
grade between rim and floor; (4) the ramp portion (the cover's
descending profile) grades from the mouth station to the floor INSIDE
the walls; where the object's walls end (the open ramp beyond the
shell) the ramp's own edges take the §34 (7) ramp law.  Bars at VHHH
(the control pair's frames): airside vertices within 200 m of the five
shells moved vs the f912ba81 control ≤ 0.02 m (count named); off-DEM
maxima by role back to the control's (junction 1.45, apron 2.57);
ADJUDICATED back to ≤ 121 + the trenches' own rows (named);
`object_cut_depth` 0 and `object_cut_offset` ≤ r3's (TUNNEL2's four
named); the cockpit CRITICAL motion 0; OTHH's walled corridors
byte-identical (the same emission path).

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

## §33 (5) THE MOUTH'S FLOOR IS THE BORE DATUM, HOWEVER ITS STATION WAS TAKEN (Fable 2026-09-15; RULINGS 2026-09-15h) — lane `v2lemdstruct2`

LEMD 1.0.340, owner 15e item 5: the mouth at 40.4947697, −3.5829037
(ramp way −10892 / shape 886, floor 599.25) sits **2.91 m** under its own
rim (−11034 at 602.16) where the law's `bore_datum_m` is 5.10 — the depth
Bridge4's admitted corridor got.  The floor came from the approach, not
the datum.  RULED: whether a mouth's station comes from the bore way, a
plate takeover (§33 (2)), the clamp ((2) (a)) or the approach, its floor
is `rim − bore_datum_m` unless the pack AUTHORED a depth (deep walls,
§33 (1) / 14av); a shallower mouth is a `tunnel_mouth_canonical` row at
that mouth, named.

### §33 (5) **MEASURED** (lane `v2lemdstruct2`, branch `claude/v2lemdstruct2`, base main `da8e5d7f`)

**THE FRAME.**  ONE fresh LEMD capture, registered
(`docs/frames.jsonl`, `LEMD capture base da8e5d7f lane v2lemdstruct2`,
20,608 vertices / 1,024 faces, 286 s), and matched `v2_solve_replay`
arms off it — the base arm reproduces the shipped read EXACTLY: mouth
floor **599.25** under a rim at **602.16** at 40.4947697, −3.5829037
(the ruling's own numbers), `tunnel_mouth_canonical` **32**.

**THE MECHANISM, MEASURED BEFORE THE FIX — THE DATUM WAS NEVER A LAW,
IT WAS A WEIGHT.**  The PLANAR record was already right:
`tunnel:-15327@0` carries `mouth_dem_z` **602.175** and `mouth_z`
**597.075** — exactly `rim − bore_datum_m`.  `--why-at
40.4947697,−3.5829037 --site-radius 6` on the base solved arm names the
whole chain in one line:

    ridge vertex v18710  z 599.25  DEM 597.08 (z−DEM +2.17)
    binding rows: structures 3, sum|dual| 1295.49
    chain: terminal v18748[retaining_wall#848] z 602.19
           [PIN: tunnel.crest = dem ...]; 1 hop; sum dz −2.94
      v18710 -> v18748  dz −2.94  structures Linear tunnel.bore_datum_m

The row EXISTS, it names the right two vertices, and it is **2.16 m out**
while the solve reports `0/103840 hard rows violated, HARD SET SETTLED`.
The reason is `solve/rows._law_sides`: a `Linear` with `lo == hi` is
routed into the **`eqs`** bucket, and `solve/design` adds those with
`rows.add(terms, hi, d.law, ...)` — the LAW TARGET WEIGHT.  Only the
one-sided bucket is filtered through `is_hard(hard_rulings(law), row)`.
So the mouth datum was a soft least-squares row in a contest it could
lose, and at this mouth it lost by 2.17 m.

**ARM 1 (a no-op, and it is the proof).**  Registering the head
`tunnel.bore_datum_m` in `[design] hard_rulings` ALONE changed **nothing**
— hard rows 103,840 → 103,840, every emitted altitude byte-identical,
`tunnel_mouth_canonical` 32 → 32.  An equality never reaches the test.

**THE FIX.**  `constraints/structures.py` states the datum as TWO
ONE-SIDED `Linear` rows (`z_m − z_cap ≤ −bore_datum_m` and
`z_cap − z_m ≤ +bore_datum_m`) instead of one `lo == hi` equality — the
same value, in the bucket where the register is read — and
`law/emit.toml [design] hard_rulings` names the head.

**ARM 2 (matched, same capture, constraints-stage replay).**

| bar | base | §33 (5) |
|---|---|---|
| mouth 40.4947697,−3.5829037 floor | **599.25** | **597.09** |
| its rim | 602.16 | 602.16 |
| **depth vs `bore_datum_m` 5.10** | **2.91 m** | **5.07 m** — MET (bar ± 0.05) |
| hard rows / violated | 103,840 / 0 | **103,946** / 0, HARD SET SETTLED |
| status | optimal | optimal |
| v2 verify rows | 1,562 | 1,626 |
| `tunnel_mouth_canonical` | **32** | **28** |
| `within_shape` (v2 verify) | 406 | **469** |
| DEFECT families | ALL ZERO | ALL ZERO |

**THE PRICE, NAMED.**  +106 hard rows (two per OSM-bore mouth, 53 of
them) and **+63 `within_shape` verify rows**: a mouth 2.17 m deeper is a
ramp 2.17 m steeper over the same route, and at this mouth the ramp was
already the airport's worst within-shape row — `8.250 m / 8.31 % over a
99.25 m PLAN CHORD` on way −10853, whose own axis is **143.5 m** long
(`top_s` 144).  The ramp is inside its 8 % cap ALONG ITS ROUTE and over
cap ACROSS ITS CHORD; §37 (7) states the route reading for the ROAD
family and 09-05aa for the TAXI family, and neither covers the STRUCTURE
RAMP family.  That is the intent question this lane leaves with its
numbers, not a mechanism it refuted.

## §33 (6) THE PACK'S STRUCTURE OBJECTS ARE THE CUT GEOMETRY — THREE SIGNATURES, ONE READER (owner RULINGS 2026-09-15e items 1/3/4/6, 15g; 14av; Fable 2026-09-15j) — lane `v2objcut`

**The intent (owner, three airports).**  "The tunnels have object based
interior walls and hard covers where needed (like EGLL does), so we need
to cut our trenches based on those … align with the provided ramp and
walls" (VHHH); "use the provided surface wall objects as a precise guide
for where to cut the mouth, ramp should stay within the wall boundaries
… the terrain grades under the wall object and the wall sits on top of
the tunnel edges" (LEMD); "the two edge wall objects … should be used
as guides for where the author wants the bridge … grade the bridge so
those sit smoothly on either edge of it" (LEMD).  THE PACK'S STRUCTURAL
OBJECTS ARE THE AUTHOR'S GEOMETRY; the mapped way is the ROUTE (the
seed, and the connection to the network beyond the object's ends) and
nothing more.  Where an object of any signature below covers a bore or
a crossing, the cut's PLAN, DEPTH, COVERED EXTENT and STATIONS derive
from the object.

**The three signatures (measured 15h/15j; detected by GEOMETRY, never by
name, never by ICAO).**

* **A — crested walls (OTHH, 14av):** solids descending below the
  object's zero with a crest plate ≥ `plate_min_height_m` above it
  (−15 … +5, −10 … +9.55).  Already LAW C (`airport/wall_corridors.py`);
  the wall's inner faces are the trench walls, the crest is the rim.
  The per-airport affordance `kerb_wall_corridors` (`law/airports.toml`,
  OTHH only) is RETIRED: the signature admits, not the ICAO.
* **B — shell + flush hard cover (VHHH, EGLL):** a SHELL object whose
  largest horizontal plate lies ≥ 2 m below its zero (the FLOOR: −6.01
  / −6.54 / −8.95 / −9.01 at VHHH, 733–16,759 m²; EGLL −4 … −7) and, at
  the same placement (position within 1 m, same heading) or inside the
  same object, a COVER whose `HARD_DECK` plate at |y| ≤ 1 m covers part
  of the shell's plan (VHHH `_TN`: 427–11,254 m²; EGLL `N.obj` /
  `Na.obj`).  Today this class falls through every reader:
  `tunnel_objects.py:717` (a floor witness ⇒ basins), the §2 crest-
  plate rule (no plate above zero), `thin_plates` (1.0–1.5 m), LAW C
  (OTHH only).  RULED: the shell's per-band wall line (NOT the convex
  hull — the shells are L-shaped) is the trench outline; the FLOOR
  PLATE's level in the seated frame is the floor (the depth is AUTHORED
  — it overrides `bore_datum_m`, which is the law for UNAUTHORED bores
  only); the cover's flat plate is the covered extent; the cover's
  descending plate profile (tunnel5: 0.00 → −0.91 → −1.71 → −6.01 over
  25 m bins) gives the ramp STATIONS; `HARD_DECK` is the machine-
  readable marker of the cover.  The shell is never a basin.
* **C — thin surface walls and parapets (LEMD):** solids < 1.5 m tall,
  long (length ≥ 20 × height), narrow (≤ 2 m), sitting on the surface
  (y_min ≥ −0.1).  (C1) A parallel PAIR along a bore (Bridge3: 354 × 25.1
  m, 1.03 m; spacing 5–40 m, overlap ≥ 50 %) is the trench's TOP EDGES:
  the trench lies between the pair's inner faces, runs the pair's FULL
  length, its mouths at the pair's ends, its open ramps beyond them
  (item 4: from the wall's south end toward 40.4951833); the wall's
  foot line is the rim at grade — the terrain grades under the wall and
  the wall sits on the trench edge; the depth is `bore_datum_m` (no
  authored floor).  (C2) A single thin wall in a U (Bridge4, 2.01 m,
  admitted today): the ring follows the wall's INNER-FACE polyline with
  chord error ≤ half the band (0.75 m) — never a 9-station chord cut of
  a curved U — and runs to the wall's END (17 m short today).  (C3) A
  parapet PAIR flanking a mapped bridge way (Bridge2: 0.92 m, 25.6 m
  apart) is the DECK's lateral extent: the deck is centred on the pair
  and as wide as their inner spacing, so both parapets sit on the deck
  edges; the OSM carriageway pair gives the route only (today: 8–9 m
  south of the parapets).  The §33 (2) plate reading of these objects
  (a width and a mouth station) and the 1.5 m skirt pre-screen are
  SUPERSEDED for signature C; §33 (2) (a)'s clamp to the bore way's end
  is superseded by C1 (the object's end IS the mouth) — the 14bl item
  7/8 runaway it fixed was the plate's overhang beyond a bore with no
  wall pair, which C1's pairing test excludes.

**One reader.**  `airport/tunnel_objects.py` (or a successor
`airport/object_cut.py`) screens every placed object ONCE for A/B/C and
publishes ONE record class (`ObjectCut`: outline polyline per band,
floor level or None, covered extent, stations, ends, signature) that
`planar/structures.py` / `structure_approach.py` / `structure_deck.py` /
`wall_corridor_ramps.py` consume; `basins.py` sees none of them.
Consumer census at spec time (RULINGS 2026-08-30l): every reader of
tunnel objects, plates, basins with object carriers, wall corridors and
deck groups — one table before the first edit.  Where an OSM bore and an
object disagree, the OBJECT wins inside its extent; the mapped way
carries the corridor beyond it (§34 (12) still gates whether the tunnel
serves the field at all).  `[verify]` gains `object_cut_offset`: the
worst distance of an emitted ring vertex outside its object's wall line
(bar 0.5 m) and `object_cut_depth`: floor vs the authored floor plate
(bar 0.10 m).

**MEASURED** (lane `v2objcut`, branch `claude/v2objcut` off main `bf518d0c`;
ONE tree, the shared corpus.  Synthetic-first: dry `planar --stage structures`
replays at VHHH / LEMD / OTHH and a direct OBJ8 inventory of the VHHH tunnel
pair before the one VHHH build.)

**§33 (6) CONSUMER CENSUS (RULINGS 2026-08-30l), one table, written BEFORE the
first code edit.**  Every reader of the pack's tunnel objects, thin plates,
floor-witness basins, wall corridors and deck groups, and what §33 (6) does to
it.  The column "Ruled" is the decision this lane implements at that site; a
row marked UNCHANGED is a site the lane does not edit and the measurement must
prove untouched.

| # | Reader (file · symbol) | What it reads | Ruled |
|---|---|---|---|
| 1 | `airport/obj8.read_placed_objects` · `_witness` | every placement → `PlacedObject.witnesses` (the FLOOR PLATE `admission_depth_m` under the local ground) | UNCHANGED as a reading. The signature screen runs AFTER it and SUBTRACTS its own placements from the witnessed set; the witness itself is still what signature B's floor plate is found through (one parse, never a second). |
| 2 | `airport/basin_witness.read_objects` | the pack, memoised on `ResourceCache` | UNCHANGED — one parse for the whole build. |
| 3 | `airport/basin_witness.basin_member_ids` | `o.witnesses` → the placements exempt from the skirt reader and the re-seat below-grade skip (10ax (2)) | **CHANGED**: a placement the object-cut screen claims (A/B/C) is NOT a basin member. It is still exempt at both sites — it is a trench, not a foundation — so the exemption set is `witnesses ∪ object_cut`, one derivation (`airport/object_cut.cut_placement_ids`). |
| 4 | `planar/basins.build_basins` · `witnessed = [o for o in objects if o.witnesses]` | the basin REGION, rim, floor, cut | **CHANGED, one derivation site**: the intake filters out every placement the object-cut screen claims. "The shell is never a basin" (§33 (6) B). Bar: signature-A/B/C objects reaching `build_basins` = 0, count named per airport. |
| 5 | `planar/basins.object_decks` | `o.hard_deck` / `deck_top_z` → object bridges | UNCHANGED in code. A signature-B COVER is a `HARD_DECK` plate at `|y| ≤ 1 m`; it is the tunnel's covered extent, not a bridge deck over open ground — it is excluded with its shell (row 4's same set), and the count is named. |
| 6 | `airport/tunnel_objects.read_corridors` | OBJ8 → `Corridor` (crest plate + skirt, LAW A/B) | **CHANGED**: the `o.witnesses` hand-off at `:726` no longer sends a floor-witness placement straight to basins — it is screened for signature B first (shell + flush hard cover). Signature A/C readings are unchanged; every refusal still named (§33 (1)). |
| 7 | `airport/tunnel_walls.read_wall_lines` / `midline` / `stations_along` | a crest plate → inner faces, axis, stations | **CHANGED for C2 only**: the station spacing along a CURVED inner face is bounded so the emitted chord error stays ≤ half the band (0.75 m); a straight corridor's stations are unmoved (bit-identical at OTHH). |
| 8 | `airport/wall_corridors.read_wall_corridors` (LAW C bands/pairs) | vertical-only bands → kerb corridors + garage ramps | **CHANGED**: the per-airport affordance `kerb_wall_corridors` is RETIRED; the admission is signature A read on the pair's OWN resource (solids descending `min_wall_depth_m` below the object's zero WITH a crest plate `plate_min_height_m` above it). Bar: OTHH's corridor set identical OFF→ON, every difference named. |
| 9 | `law/airports.toml` · `airports_schema.Affordances.kerb_wall_corridors` | the ICAO switch | **DELETED** (key and field). `group_span_max_m` stays. |
| 10 | `airport/thin_plates.read_plates` | 1.0–1.5 m solids over a mapped way → `WallPlate` (a width + an axis) | **CHANGED**: signature C. A plate whose own solids read as a parallel PAIR of thin bands publishes the pair's INNER faces (C1 axis + inner spacing), not the authored box; a parapet pair flanking a mapped bridge way publishes the DECK extent (C3). The 1.5 m skirt pre-screen is superseded for C, so a C object is admitted whether or not `read_corridors` refused it for a skirt. |
| 11 | `planar/structure_approach.apply_plates` | `Mouth` ← `WallPlate` (§33 (2)) | **CHANGED**: for a C1 pair the §33 (2) (a) clamp is SUPERSEDED — the object's end IS the mouth and the ramp runs open beyond it; the mouth takes the pair's INNER spacing as its width and the pair's midline as its axis. For a plate with no pair (the 14bl item 7/8 runaway) the clamp stands exactly as it is. |
| 12 | `planar/structure_approach.mouths()` / `merge_duals` | bore ends → `Mouth` | UNCHANGED (lane `v2vmmcshore` owns `mouths()`; `apply_plates` runs after it and rewrites `xy` / `inward` / `width_m` / `approach` only). |
| 13 | `planar/structure_approach.field_region_for` (§29 gate) | cover ∪ corridors ⊕ standoff | UNCHANGED and runs FIRST — the gate judges the MAPPED end, never the moved one. §34 (12) (lane `v2vmmcshore`) still decides whether a tunnel is built at all. |
| 14 | `planar/object_corridor.mouth_covered_by` | mouth xy vs corridor footprints (05n-3 precedence) | UNCHANGED in code; a signature-B shell now HAS a footprint here, so its OSM mouths are replaced by the object's — that is §33 (6)'s "the OBJECT wins inside its extent", measured as `mouths_replaced_by_object`. |
| 15 | `planar/object_corridor.object_groups` / `climb_path` / `_interp` | `Corridor` → `Group` (half-width and rim per station) | UNCHANGED — a signature-B corridor is a `Corridor` like any other; its stations come from the shell's own wall line. |
| 16 | `planar/object_corridor.trench_outside_m` | emitted ramp rings vs the corridor's trench | UNCHANGED; it is the existing instrument the new `object_cut_offset` family generalises (ring vertex vs the object's WALL LINE, every signature). |
| 17 | `planar/structures.build_structures` | `corridors`, `plates`, `objects`, cells | UNCHANGED (another lane's file this round): every §33 (6) reading reaches it through the existing `corridors=` / `plates=` / `objects=` arguments. No new argument, no re-ordering. |
| 18 | `planar/structures` ramp geometry (`geometry`, `_pad_hit`, `beyond_strip`) | the mouth's width / inward | UNCHANGED; it reads the width `apply_plates` hands it, so a C1 ramp is the pair's inner spacing by construction. |
| 19 | `planar/structure_deck.deck_intervals` / `deck_groups` / `deck_items` | mapped bridge ways crossing a corridor → `Deck` | **CHANGED (C3 only)**: where a parapet PAIR flanks the deck's mapped way, the deck face is centred on the pair and as wide as their inner spacing; with no pair the carriageway width stands exactly as today. |
| 20 | `planar/structure_deck.deck_ends` (§33 (4)) | the way's two ends → the deck's end levels | UNCHANGED — C3 changes the deck's LATERAL extent only, never its profile. |
| 21 | `planar/structure_deck.object_deck_intervals` | `object_decks` (hard-deck objects) over a corridor | UNCHANGED in code; row 5's exclusion keeps a signature-B cover out of it (it is the tunnel's own roof, not a deck over it). |
| 22 | `planar/wall_corridor_ramps.wall_corridor_groups` / `wall_corridor_profile` / `stop_and_steepen` | LAW C records → ramp groups and profiles | UNCHANGED in code; row 8's admission change is the only thing that can alter what reaches it. Bar: OTHH ramps identical. |
| 23 | `planar/wall_corridor_ramps.road_true_edge` / `airside_stops` / `locked_road_stops` | where a ramp stops (§34 (9)/(10)) | UNCHANGED. |
| 24 | `airport/skirt.skirted_placements` (10ag) | basin members exempt from the skirt drop | **CHANGED through row 3's one derivation** — the exemption set grows by the object-cut placements; no second spelling. |
| 25 | `airport/rebake_plan` below-grade skip (09w (1)) | basin members exempt | **CHANGED through row 3's one derivation**; a tunnel shell's below-zero geometry is not a foundation. |
| 26 | `airport/rebake_plan` / `emit/rebake` `ATTR_hard_deck` re-seat | hard-deck objects | UNCHANGED — the shell and its cover keep the seats the object stage gives them; this lane re-seats nothing (13r's "a draped deck plate rides the terrain deck the mesh gives it"). |
| 27 | `airport/deck_signature.classify` / `is_bridge_way` / `is_tunnel_way` | the deck families and the two way predicates | REUSED UNCHANGED by every signature — one predicate, never a second (the 13r rule). |
| 28 | `pipeline/publication.tunnel_objects` | `tn.source != "osm"` | UNCHANGED: a C1/C3 mouth stays `source = "osm"` (it IS an OSM bore, the object only placed and sized its portal); a B shell is an object corridor and reads `object` as every corridor does today. |
| 29 | `pipeline/build` / `planar/__main__ --stage structures` structures line + KML | the stats | **CHANGED, reporting only**: `object cuts N (A n / B n / C n)`, `basin placements claimed by a cut N`, and one named line per refusal — every screened resource still named (§33 (1)). |
| 30 | `verify/structures.tunnel_mouth_canonical` | cap crest − ramp mouth = `bore_datum_m` | **READ, NOT CHANGED**: signature B's floor is AUTHORED and overrides `bore_datum_m`, so a B mouth is legitimately deeper; the family is quoted before → after and every new row named. §33 (5) (lane `v2lemdstruct2`) owns the shallow case. |
| 31 | `verify/structures.tunnel_deck_clearance` | min(deck) − max(ramp) ≥ `clearance_m` | UNCHANGED. |
| 32 | `verify/*` + `tools/check_grade.LAW_FAMILIES` | the emitted roles | **NEW families** `object_cut_offset` (worst emitted ring vertex outside its object's wall line, bar 0.5 m) and `object_cut_depth` (emitted floor vs the authored floor plate, bar 0.10 m), registered in `LAW_FAMILIES` with twins in `tests/test_harness.py` — the census cannot omit a family (the twin fails). |
| 33 | `emit/osm_adapter` sidecar `road_bridge_decks` | always empty in v2 | UNCHANGED. |
| 34 | `planar/zones.py`, `planar/structure_underpass.py`, `constraints/cluster_pad.py`, `solve/design*.py` | other lanes' files this round | NOT TOUCHED. |

**THE TWO FAMILIES SELECT BY OVERLAP, NOT BY REF.**  An emitted ramp face's
`ref` is its ROLE (`tunnel_ramp`), the same string for every corridor in the
patch (`planar/structures.py:713`), so a ref join would price every ramp of the
airport against every object.  A face with at least one vertex INSIDE the wall
line is that object's cut; a face wholly outside is another corridor's and is
not read.  The published `outline_ll` is the walls ∪ trench EXTERIOR ring, so
for a hairpin shell (VHHH `tunnel5`) the region is slightly LOOSER than the
trench — the family can under-report, never over-report.

**CENSUS ROWS THE MEASUREMENT CORRECTED.**  Rows 3 / 24 / 25 ruled that the
skirt and re-seat exemption set would grow to `witnesses ∪ object_cut`.  It
does not need to: a signature-B shell already carries a floor witness, so it
is already in `basin_member_ids`, and §33 (6) removes it from the basin
**intake** only (row 4).  `airport/skirt.py` and `airport/rebake_plan.py` are
therefore UNCHANGED, and `cut_placement_ids` has exactly one consumer.  Row 8
/ 9 (the affordance's retirement) is REFUTED — see (A) below.  Rows 10 / 11 /
19 (signature C) are NOT DONE this round — see (C).

**(B) THE SHELL + FLUSH HARD COVER — DONE.**  `airport/object_cut.py` (NEW,
440 lines) screens every placement once and publishes `ObjectCut`;
`tunnel_objects.shell_corridor` turns one into the SAME `Corridor` every other
object corridor is, so `planar/structures.py` is not edited at all and the
05n-3 per-mouth precedence, `object_groups` and `trench_outside_m` read it
unchanged.  Three readings are the object's and not the law's:

* **The trench outline is the plan union of the shell's NON-VERTICAL faces**
  (floor plates and ramps alike), never a hull: VHHH `tunnel5_done.obj` is a
  U-turn ramp whose 9,290 m² trench sits in a 245.9 × 73.2 m box.
* **The wall line is the plan segments of its VERTICAL faces**, and a run of
  the trench ring with no wall face standing on it is a PORTAL.  `tunnel5`
  reads exactly two open runs of its 29 ring edges (22.2 m and 17.0 m) and 27
  walled ones; `tunnel3` reads one portal spanning TWO ring edges (44.4 m +
  2.5 m), which is why the open edges are joined into RUNS before they are
  counted; `tunnel2` reads FIVE portals (a 28,525 m² multi-portal shell) and
  takes its two longest as its ends, the others standing inside a wall chain.
* **The floor is the DEEPEST plate-worthy bin, not the largest-area one.**  A
  shell's RAMPS are near-horizontal too (`tunnel5`'s read |n_y| = 0.998 over
  100 m), so the largest bin of horizontal faces is a ramp's mid-height:
  measured `tunnel1` a 1,514 m² ramp bin at −2.50 against the 733 m² floor at
  −6.95, `tunnel4` 2,672 m² at −5.25 against 454 m² at −9.01.

**TWO DEVIATIONS from §33 (6) B's text, both forced by measurement** (the 13r
precedent — the spec text yields to the measurement):

1. **The cover is a SECOND PLACEMENT, never the shell itself.**  §33 (6) B
   allows "or inside the same object"; that form admitted VHHH's `sea_X.obj`
   — a sea barrier whose own flush hard deck covers its own −28.20 m plate —
   as a 104.9 m wide, 22.88 m deep "tunnel".
2. **The object must COVER A BORE OR A CROSSING**, which is §33 (6)'s own
   opening clause read as a GATE: a mapped tunnel way ending at a portal
   (`bore_end_tolerance_m`) or running through the trench.  Without it
   `sea_X.obj` + `sea.obj` (a 112,376 m² flush hard deck — the SEA SURFACE)
   still read as a corridor 177 m off the north shore.

**THE MATCHED DRY REPLAY PAIRS** (`planar --stage structures`, ONE tree per
arm, one machine, the shared corpus, the lane-local mod-cache overlay; base =
main `106459fa` in its own ritual worktree, lane = `claude/v2objcut`).

* **OTHH — NOTHING MOVES.**  `corridors`, `tunnels`, `wall_corridors`,
  `basins`, `plates` and `door_wells` all **BYTE-IDENTICAL** (9 / 44 / 73 / 10
  / 2 / 4); the only difference is **+51 named §33 (6) refusals** (28 "no
  near-horizontal solid face stands 2.0 m under the object's zero", 9 "not a
  tunnel floor", 6 "the trench ring has 0 open ends", 3 shells with no flush
  cover, each by resource).  The §33 (1) discipline holds for the new reader.
* **LEMD — NOTHING MOVES.**  The same six arrays BYTE-IDENTICAL (1 / 50 / 0 /
  1 / 3 / 0), **+25 named refusals**.  `plate_mouths` 2 → 2,
  `crest_from_approach` 2 → 2, `underpasses` 1 → 1.
* **VHHH — five object cuts read, three built.**  `corridors` **0 → 5** with
  the AUTHORED floors: `TUNNEL2_DONE` **0.78**, `tunnel1_done` **0.37**,
  `tunnel3_done` **−1.63**, `tunnel4_done` **−1.69**, `tunnel5_done`
  **1.30** — against the bar's 0.77 / 0.36 / −1.63 / −1.69 / 1.31, every one
  inside the 0.10 m bar.  `wall_corridors` **0 → 0** (the affordance stands),
  `basins` **70 → 70 and the population IDENTICAL** by (objects, area) — the
  five shells and their five covers were never separate pits, and the claim
  (`shell_claimed`: 10 placements) keeps it that way.  `tunnels` 28 → 23: nine
  OSM bore tunnels at those sites are replaced by the objects (05n-3), which
  read **mouth_z 2.22 = DEM − `bore_datum_m`** on the base arm against the
  objects' own 0.37 / −1.63 / −1.69.

**THE VHHH MISS, NAMED.**  Two of the five cuts — `tunnel5_done` (THE OWNER'S
SITE 22.3038632, 113.9088362) and `TUNNEL2_DONE` — are refused DOWNSTREAM by
`planar/structures.py`'s ramp-ring builder: *"the approach bends tighter than
the corridor (ramp or wall ring self-intersects)"*.  Both are HAIRPINS —
`tunnel5` is a U-turn ramp whose 413 m axis reverses on itself, `TUNNEL2` a
1,110 m multi-portal corridor — and a ring built by OFFSETTING such an axis by
its half widths folds.  The reading is right (floor 1.30 against the authored
1.31, trench 9,290 m², two portals) and the corridor is refused for a reason
that has nothing to do with §33 (6): the emitter must follow the OBJECT'S OWN
trench polygon rather than offset an axis.  That is a `planar/structures.py`
change, which this lane's brief reserves to another lane, so it is REPORTED,
not attempted.

**THE BEFORE READING ON THE OWNER'S OWN 1.0.340 VHHH PRODUCTS** (the shipped
patch under `Patches/+20+110/+22+113/`, read against each object's published
wall line — no build, nothing written).  Per shell: emitted `tunnel_ramp` /
`structure_rim` vertices standing outside the object's wall line, and the
emitted floor against the authored one:

| object | vertices | outside (> 0.5 m) | worst | emitted floor | authored | miss |
|---|---|---|---|---|---|---|
| `tunnel5_done` | 147 | **85** | 75.80 m | 2.21 | 1.31 | **0.90 m** |
| `tunnel1_done` | 25 | **19** | 81.48 m | 2.22 | 0.37 | **1.85 m** |
| `TUNNEL2_DONE` | 171 | **111** | 83.74 m | 2.22 | 0.78 | **1.44 m** |
| `tunnel3_done` | 46 | **27** | 86.12 m | 2.22 | −1.63 | **3.85 m** |
| `tunnel4_done` | 40 | **26** | 79.67 m | 2.22 | −1.69 | **3.91 m** |

That is `object_cut_offset` 268 rows / worst 86.12 m and `object_cut_depth`
0.90–3.91 m on the shipped build, and it reproduces the 15j scout's
"0.92–3.91 m too shallow" exactly.  The AFTER numbers are the closing VHHH
build's, which this lane could not run (see below).

**(A) THE AFFORDANCE'S RETIREMENT IS REFUTED — one dry VHHH replay.**  The
crested-wall predicate (solids under the object's own zero WITH a crest plate
`plate_min_area_m2` standing `plate_min_height_m` above it) admits an ordinary
BUILDING, because a building has a roof.  Measured at VHHH: wall corridors
**0 → 116** (bay 28, level 88), **every one of them inside `CITY2.obj`** — a
city-block object off the field whose foundation walls descend 6.4–8.5 m under
their ground — plus 75 narrow-cut candidates and three `CITY1.obj` families.
No depth threshold repairs it: OTHH's own admitted bays are 1.35 m deep.  This
is RULINGS 2026-09-10ap's seven rounds at a THIRD airport.  The predicate is
DELETED (not kept gated); `kerb_wall_corridors` STANDS in `law/airports.toml`
with the refutation recorded beside the gate, and §33 (6) A is an INTENT
QUESTION for the owner, not a mechanism.

**NO CLOSING BUILD.**  RULINGS 2026-09-15u: `+22+113`'s cached road layers
predate the `ROAD_CACHE_TAG_SCHEMA` bump, so the first harness build on that
tile REWRITES the shared repo's road layer (the LEMD `+40-004` build was
flagged CONTAMINATED) and, since `v2schemarefuse`, REFUSES by name.  The
refresh ledger carries NO `osm_layers` refresh for `+22+113` at all.  The
build AWAITS the owner's `--refresh-data osm_layers` on that tile; the lane
ran no build and no `--refresh-data`.

**(C) SIGNATURE C IS NOT DONE, and the measurement that stopped it.**  The
BAND READING landed (`object_cut.thin_bands` / `band_pair`, over LAW C's own
`wall_geometry` machinery — a band is a STRAIGHT RUN of vertical faces, never
a component: LEMD `Bridge3.obj`'s two components read 73 × 16 m and 58 × 15 m
convex hulls and are not walls by any gate, while comp 0's vertical faces
split into the PAIR, two 73.0 / 73.1 m runs 1.00 m thick 14.02 m apart).  It
is NOT wired into `apply_plates` or `structure_deck` because the reading
contradicts C1's premise: **`Bridge3.obj` carries 280 triangles in two
components at its two ENDS (z −354.2…−281.0 and z −57.6…0); 224 m of its
354.2 m box carry no solid at all.**  So "a parallel PAIR along a bore …
[whose] trench … runs the pair's FULL length" does not describe this object —
its walls are two short MOUTH pieces, and 25.1 m is its authored BOX, not its
wall spacing (the pair's inner faces are 14.02 m apart).  `Bridge2.obj` reads
two 42.0 / 39.5 m bands at 157.5° and 67.1° — perpendicular, no pair;
`Bridge4.obj` reads no band at all under the surface gates (2.016 m tall).
Rather than guess the owner's geometry a third time, the reading is published
and measured and the INTENT goes to the owner (the standing "mechanisms get
measured, INTENT gets asked" law).

## §33 (6) MEASURED AND RE-FOUNDED (lane v2objcut r1 e178702f; Fable 2026-09-15; RULINGS 2026-09-15x) — B reads; A refuted by geometry alone; C re-founded on the objects as they are

**B — READS.**  All five VHHH shells admitted with their AUTHORED floors
(1.30 / 0.37 / 0.78 / −1.63 / −1.69 against bars 1.31 / 0.36 / 0.77 /
−1.63 / −1.69; the OSM arm 2.22 for all), corridors 0 → 5, tunnels 28 →
23 (nine OSM bores replaced), basins identical by (object, area) — 10
placements claimed.  OTHH and LEMD byte-identical on six populations.
MISS: `tunnel5_done` (the owner's site, a 413 m U-turn) and `TUNNEL2_
DONE` are refused by the RING BUILDER (`planar/structures.py`: "the
approach bends tighter than the corridor — ramp or wall ring self-
intersects") — a ring built by OFFSETTING AN AXIS folds on a hairpin.
RULED (r2): for a signature-B corridor the emitter takes the object's
OWN trench polygon (the shell's per-band wall line, closed by the
cover's ends) as the ring — no axis offset; the stations from the
cover's profile.  `object_cut_offset` / `object_cut_depth` families
land (select by overlap, not by ref).

**A — REFUTED by geometry alone.**  Retiring `kerb_wall_corridors` for
the crested signature admitted 116 corridors at VHHH, every one inside
`CITY2.obj` (a city-block object: a building has a roof) — RULINGS 10ap
at a third airport; no depth threshold separates them (OTHH's admitted
bays are 1.35 m deep).  RULED: the predicate is deleted; the per-airport
affordance STANDS as the gate for A until a discriminator is MEASURED
(candidates for a later scout: a roof plate spanning the walls; the
object's footprint on airside vs off-field; the pack's placement on a
pad).  Not an owner question.

**C — RE-FOUNDED on the measured objects.**  `Bridge3.obj` is NOT a
354 m wall pair: its 280 triangles sit in two components at its two
ENDS (z −354.2…−281.0 and −57.6…0), each a pair of 73.0 / 73.1 m walls
**14.02 m** apart; 224 m of the box carries no solid.  The author marked
the two MOUTHS; the bore between them is COVERED.  `Bridge2.obj` reads
two perpendicular bands (no pair); `Bridge4.obj` no straight band (a
curved U).  RULED: (C1′) a thin-wall PAIR (parallel straight bands,
spacing 5–40 m, overlap ≥ 50 %) marks a MOUTH RAMP: the ramp lies
between the pair's inner faces, runs the pair's length, its mouth at
the end nearer the bore's covered stretch and its top at the outer end;
the bore between two such pairs (or between a pair and an authored
deck) is covered; the walls sit on the ramp's top edges (the foot line
is the rim at grade).  Item 3's ramp lies inside the north pair; item
4's inside the south pair, its top at the pair's outer end (toward
40.4951833).  (C2′) a band is a POLYLINE of contiguous vertical faces,
straight or curved (Bridge4's U): the ring follows its inner face with
chord error ≤ 0.75 m and runs to its end.  (C3′) parapets: the lane
reports Bridge2's two bands with coordinates and headings against the
deck before any rule — if they flank the deck (parallel, each side)
the deck is centred on them; if perpendicular they are abutment walls
at the deck's ENDS and mark its span.  Every C rule is measured on the
three LEMD objects by dry pair before it is wired.

## §33 (6) B AMENDED — A SHELL'S TRENCH IS WALLED: THE RIM STAYS AT THE SURROUNDING SURFACE, THE OBJECT'S WALLS ARE VERTICAL, AIRSIDE IS NEVER PULLED (Fable 2026-09-15; RULINGS 2026-09-15bh; lane v2vhhhctl measurement) — lane `v2shellwall`

**The measurement (VHHH, matched pair f912ba81 → d94db789, one
source merge, both builds clean).**  Cutting `TUNNEL2_DONE` (1,109.9 m,
21.1 m wide, floor 0.777, depth 6.54 m) and `tunnel5_done` (413.2 m,
22.8 m, floor 1.304, depth 6.01 m — the owner's site) to their authored
floors was RIGHT at the shells (`object_cut_depth` 0 rows; offsets 0
bar TUNNEL2's four) and WRONG around them: the solve's active set
4,177 → 11,253, objective 19,143 → 375,231; off-DEM > 0.5 m maxima
junction 1.45 → 6.22 m, primary_parallel 1.55 → 6.46, cross_connector
0.96 → 6.47, apron 2.57 → 6.48; apron bodies' own planes −0.27 → −5.23
m; design targets missed apron max 1.70 m, taxi 1.35 m; LAW-TRUE 1,531
→ 4,845, ADJUDICATED 121 → 1,472, 87 % of the new rows within 500 m of
TUNNEL2 (taxiway-network grade rows: `within_shape` cross_connector /
primary_parallel, `airside_no_step`).  The trench ring's vertices are
shared with the airside faces and the floor's rows pull them down —
the trench has no wall.  §37 (11)'s sea wall contributed nothing (4 →
4, identical coordinates); the r3 report's "1,713 → 4,845" understated
the rise (the shipped 1.0.340 patch was worse than the control).

**RULED.**  A signature-B trench is a WALLED cut, emitted as OTHH's
`retaining_wall` / `tunnel_wall` cells are (§33 (1), 14av): (1) the RIM
ring is the surrounding design surface — its vertices are the
airside/ground vertices they already are and carry NO floor row;
airside beside a shell never moves (§16g (10) (5)'s bar, 0 > 0.02 m
against the control); (2) the FLOOR ring is a separate ring inside the
rim by the wall's thickness (the object's inner-face line), at the
authored floor plate's level along the object's own profile (the
cover's stations); (3) between them the WALL: a vertical band (the
breakline pair the sea wall and the OTHH walls already use) — the
object's interior walls are the retaining walls, the terrain does not
grade between rim and floor; (4) the ramp portion (the cover's
descending profile) grades from the mouth station to the floor INSIDE
the walls; where the object's walls end (the open ramp beyond the
shell) the ramp's own edges take the §34 (7) ramp law.  Bars at VHHH
(the control pair's frames): airside vertices within 200 m of the five
shells moved vs the f912ba81 control ≤ 0.02 m (count named); off-DEM
maxima by role back to the control's (junction 1.45, apron 2.57);
ADJUDICATED back to ≤ 121 + the trenches' own rows (named);
`object_cut_depth` 0 and `object_cut_offset` ≤ r3's (TUNNEL2's four
named); the cockpit CRITICAL motion 0; OTHH's walled corridors
byte-identical (the same emission path).

## Spec (design-surface) §37 (11)

## §37 (11) THE SHORE TRIMS THE ZONES; A PAVEMENT AT THE WATER IS A SEA WALL (owner RULINGS 2026-09-15f item 2; Fable 2026-09-15i) — lane `v2vmmcshore`

**The reading.**  There is no WATER role in the patch and no bank (bank
OFF).  Between the taxiway edge (6.10) and the sea (DEM 0.00, GLO30
ocean) the engine emits the ordinary adjacent-ground band — a 3 m lip
(zone 1) and the code-E 19 m band (zone 2), `beyond_zone2 = "dem"` — so
the 6.10 m fall is taken as 26–32 % across zone 2 and 100–1,124 % across
the lip: the pale sloped strip and the dark face in the screenshot are
that band.  Thirteen zone faces cross the coastline by 3–195 m; the
rings stand at exactly 0.00 up to 42 m seaward of it — the second,
translucent water plane is the patch's own terrain at sea level beside
the tile's water.  Census: `strip_seam_tear` 61 (worst 6.110 m, 238 %),
`adjacent_ground_step` 6.  "With a taxiway in the water, I don't think we
want any adjacent ground at all, the pavement should drop straight to
the water with no slope."

**RULED — one region trim at the zone derivation site (`planar/zones.py`),
never per-consumer vetoes.**  (1) The zone region is CLIPPED by the WATER
region: the coastline/water polygons (OSM `natural=coastline` / water
ways, the flat-site water mask) — no zone ring, lip or band is emitted
seaward of the coastline, and no patch vertex stands on the water.
(2) Where the land between a pavement edge and the coastline is
NARROWER than zone 1 + zone 2 (lip + half-width), that land is a QUAY:
one plane at the pavement edge's level (the pavement's own edge rows
carry it), ending at the coastline in a SEA WALL — a vertical drop from
the quay level to the water level, emitted as a breakline pair (the
quay edge at Z, the coincident shore vertex at the water level); where
the pavement edge IS the coastline (within the lip width) the sea wall
is the pavement edge itself, no slope, no strip.  (3) Where the land is
wider, the zones apply in full, bounded by the coastline, and the sea
wall stands at the coastline at whatever level zone 2 reaches there
(zones never drop to the DEM's ocean zero).  (4) The DEM's one-post
ocean bleed (GLO30 0.00 up to a post inland of the mapped coastline) is
NEVER the ground: on the quay the level is the pavement's; in the
zones the DEM witness is the nearest on-land post.  (5) The census
names sea-wall edges as their own family (`sea_wall`: the drop, the
level, the length) and `strip_seam_tear` / `adjacent_ground_step` EXCLUDE
them — the tear IS the wall.  (6) The weld to shore (§39, `weld_to_
shore`) stays a hairline fix on the vertices that remain; it is not the
trim.  Consumer census first: every reader of the zone region and of
`beyond_zone2` (zones.py, cluster/pad clips, road ribbons §34 (4), the
bank emitter even while OFF, `verify/within.py`, `check_grade`'s strip
families, `mesh_region_tris`), one table.  Water level: the tile's own
sea (the coastline mesh at the X-Plane water level), read from the
same source the tile uses (`O4_Vector_Map include_sea`).

### §37 (11) CONSUMER CENSUS (owner RULINGS 2026-08-30l), completed BEFORE any consumer was edited — lane `v2vmmcshore`

The zone region has ONE production derivation (`planar/zones.zone_regions`,
called once from `planar/overlay.build_arrangement:254`) and `beyond_zone2`
has ONE reader (`law/model.py`'s datum enum — it is a DECLARATION that zone
3 is the DEM, not a geometry channel).  The trim (1) is taken there.  The
QUAY (2) and the SEA WALL (5) are the two NEW classes, and they are what
this table is for.

| # | consumer | reads | RULE |
|---|---|---|---|
| Z1 | `planar/zones.zone_regions` | the cells, the law | **EDITED — THE ONE DERIVATION SITE.** `z1`/`z2` are differenced by the WATER region before they are split into parts, so no ring, lip or band exists seaward of the coastline. The QUAY is derived here too, from the same water geometry, so there is one region producer and not two. |
| Z2 | `planar/overlay.build_arrangement` | `ZoneRegion.polygon` / `.ref` / `.zone` | UNAFFECTED CODE for the trim (a smaller polygon); the QUAY enters as a `ZoneRegion` of its own zone class so no new `Region` kind is invented. |
| Z3 | `constraints/zones.zone_bands` / `zone_bounds` | the zone number + the class | **UNAFFECTED for zones 1 and 2.** A QUAY region is EXEMPT from the band ladder — its level is the pavement edge's, stated by the pavement's own edge rows — so it mints no band row rather than a relaxed one (a relaxed band is still a fall). |
| Z4 | `constraints/water.water_pins` | `graded_strip` ring vertices on water | UNAFFECTED CODE. Its count is the trim's proof (W3). |
| Z5 | `constraints/strips.py`, `constraints/structures.py`, `constraints/runway_chord.py` | `graded_strip` faces | UNAFFECTED — role and ref vocabulary unchanged. |
| Z6 | `constraints/cluster_pad.py` / `constraints/pads.py` (the pad clips) | pad geometry, never the zone region | UNAFFECTED — a pad clip is taken against pavement and pad footprints; no pad reads a zone ring. (Lane `v2padqp` owns that file; nothing here touches it.) |
| Z7 | `airport/road_ramp.py` (road ribbons, §34 (4)) | road-family faces | UNAFFECTED — a road ribbon is priced on its own route frame; the zone band is not in its population. |
| Z8 | `emit/bank.py` (the bank emitter, bank OFF) | the graded rings as coverage | UNAFFECTED BY CONSTRUCTION — a trimmed ring is a smaller coverage. §37 (3) as amended (13cw) closes the coverage at the emitter whatever the ring's extent; the SEA WALL edge is a breakline, never a bank foot, so the two never compete for the same station. |
| Z9 | `verify/within.py` / `verify/strips.py` | the emitted faces | UNAFFECTED — the sea-wall pair is not a within-shape pair (the two vertices are one breakline, not two stations of one face). |
| Z10 | `check_grade` `strip_seam_tear` / `adjacent_ground_step` | emitted `graded_strip` rings | **EDITED per (5):** an edge whose two vertices are a declared sea-wall pair is EXCLUDED from both families — the tear IS the wall. The exclusion is keyed on the sidecar's own `sea_wall` declaration, never on a height guess. |
| Z11 | `check_grade.LAW_FAMILIES` + `law/families.toml` | the register | **EDITED, additive:** the new family `sea_wall` (the drop, the level, the length) with its twins in `tests/test_harness.py`. Registering it in the same commit as the check is what `test_harness.py` twin-asserts. |
| Z12 | `tools/mesh_region_tris.py --z-xref` | the `.poly` markers and the mesh | UNAFFECTED — it reads the built tile; the sea wall is an ordinary constrained pair to it, which is the point of emitting it as a breakline. |
| Z13 | `emit/osm_adapter` breaklines / `OPEN_BREAKLINE_FEATURES` | the feature name | **EDITED, additive:** `sea_wall` is an OPEN breakline feature so the vector map gives it `PATCH_RING_MARKER` rather than `DUMMY` (13cp's B2 rule, and for its reason: a wall that is a `DUMMY` edge is not a wall). |
| Z14 | `law/model.py` `beyond_zone2` | the datum enum | UNCHANGED — zone 3 is still the DEM. (4) does not change what zone 3 IS; it changes which DEM POST is the witness where the sea has bled one post inland. |
| Z15 | v1 `auto_patch/` | its own zone law | UNTOUCHED — §37 is v2 law. |

## Spec (design-surface) §34 (7)

### §34 (7) A RAMP CORRIDOR CARRIES A CROSS-CHORD ONLY WHERE THE ROUTE BENDS OR THE PROFILE BREAKS (owner RULINGS 2026-09-14n item 2; Fable 2026-09-14; RULINGS 2026-09-14p) — lane `v2othhfix`

Stations at `station_m` are the SAMPLING of the profile, not the emitted
shape.  After the profile is solved, consecutive stations whose axis stays
within `min_distinct_spacing_m` (0.5) of the chord between the surviving ends
AND whose design z stays within the materiality floor (0.01 m) of the linear
interpolation between them are COLLAPSED; a straight constant-grade run emits
its two end chords and nothing between; a landing-to-climb transition keeps
its chord.  The 0.5 m identity `snap_out` then has nothing between the ends to
stagger.  BARS: OTHH ways −10854 (40 nodes) / −10859 (29) → 8 nodes each
(landing / climb / landing), max lateral offset from the chord ≤ 0.05 m
(today 0.27–0.49); the ramp profile unchanged within 0.01 m at every former
station; every `tunnel_ramp` at OTHH before → after node counts.

## RULINGS

## 2026-09-15bh v2vhhhctl (measurement, two clean airport-path builds, frames registered): the VHHH census rise is ONE mechanism — v2objcut r3's two hairpin trenches (TUNNEL2_DONE 1,110 m, tunnel5 413 m) pull the connected airside down up to 6.5 m (LAW-TRUE 1,531 → 4,845, ADJUDICATED 121 → 1,472; the sea wall 4 → 4 identical) — a 1.0.341 REGRESSION at VHHH → RULED §33 (6) B AMENDED: a shell's trench is WALLED (rim at the surface, vertical walls, floor inside); lane v2shellwall; owner notified

Control f912ba81 (VHHH_20260915T120714, 1,108.6 s, body 8c8ef471eaab)
→ arm 118d2c40 (VHHH_20260915T122604, 1,182.9 s, body 38e3a2678b5c =
r3's closing build bit for bit), both `shared repo UNCHANGED`, both in
the artifact ledger; `git log --first-parent` between them = ONE
source merge (d94db789). Numbers in §33 (6) B AMENDED. Row join: EXACT
1,287 / MOVED 0 / GONE 244 / NEW 3,558; 3,084 of the NEW within 500 m
of TUNNEL2. The brief's premise (the sea wall would dominate) REFUTED
by the numbers. Cockpit: CRITICAL motion 0 → 1 (the 0.670 m
`object_cut_offset` cliff at 22.3080218,113.9225398), visual +67 (all
unmeshable hairline). The shells themselves: `object_cut_depth` 0
rows; offsets 0 bar TUNNEL2's four (0.897/0.842/0.812/0.670). The
lane's worktree taken down; frames committed. The owner (testing
1.0.341) push-notified: VHHH near the tunnels is a known regression;
LEMD/VMMC reads valid.

## 2026-09-15ar v2objcut r3 MERGED (5cc3e7bc → d94db789): VHHH tunnel5 MET (ring vertices outside the wall line 85 → 0, floor 1.30 = authored; all five shells 0 outside bar TUNNEL2_DONE 4 / 0.90 m; `object_cut_depth` 0 rows), LEMD item 1 MET (both parapets on the deck edges within 0.06 m; six other decks byte-identical), item 6 stations 9 → 13 (`trench_outside_max_m` 0.139); TWO MAIN-TREE FINDINGS: the OTHH object-corridor reader is NONDETERMINISTIC (7/42 vs 9/44 on one tree, `tunnel west 1/3.obj` flipping) — lane v2othhdet; the VHHH closing build CONTAMINATED the mod cache (a new-hash DSF dump of the owner's rebaked pack past the lane-local redirect) — the peer's guard; the VHHH census vs the 1.0.340 patch (law-true 1,713 → 4,845, ADJUDICATED 272 → 1,472) is UNATTRIBUTED — a control pair at f912ba81 is owed (lane v2vhhhctl)

Lane @ 5cc3e7bc (main f912ba81 merged); suite 1,649 passed, 0 FAILED;
22 twins. Closing VHHH build rc 0, 672.4 s, optimal, body_sha
38e3a2678b5c, 1,970 verify rows, `object corridors 5 (0 refused)`,
`tunnels 26 cells cut 17` — the hairpins no longer fold (B's ring =
the object's trench polygon, `structure_geometry.geometry_from_trench`
/ `ring_for` / `seed_wall_stations` — only stations whose inner-face
point stands > 0.5 m off the chord are seeded; seeding EVERY station
moved nine straight OTHH corridors and was withdrawn). Per shell,
1.0.340 → build: tunnel5 85/147 (worst 75.8 m) → 0/107, floor miss
0.90 → 0.00; tunnel1 19/25 → 0/62; TUNNEL2 111/171 → 4/389 (0.90 m —
the 1,110 m five-portal shell, named, over the 0.5 m bar); tunnel3
27/46 → 0/45; tunnel4 26/40 → 0/37. C3′: `structure_deck.flanking_pair`
/ `_centred_on_pair` — `-6288`'s lateral extent −11.81…+2.29 →
−10.23…+10.24 m against inner faces ±10.185 (worst excess +1.62 →
+0.06 m); `mouth_z` unchanged, only `climb_from_s`. C2′: Bridge4
stations 12 → 17, collapsed 9 → 13; per-vertex numbers await a LEMD
build. LEMD 49/51 tunnels identical (the two named); OTHH six
populations identical — BUT two base runs at f912ba81 differ (7/42 vs
9/44; arms e0_OTHH / e2_OTHH), `tunnel_objects.py` byte-identical
between branch and main: a main-tree nondeterminism that invalidates
any single-run "byte-identical" claim at OTHH and may vary the
CUSTOMER'S OTHH build run to run. CONTAMINATION (quoted): "SHARED-REPO
SIDE EFFECT: this build wrote 2 path(s) NOBODY authorised … [airport_
mod_cache] … added Airport_mod_cache/c_HKG - 100_airport - VHHH_…/
+22+113.dsf.d18b5903.text … Re-run with --refresh-data
airport_mod_cache … artifact ledger: NOT stored"; the harness also
named `+60-136_big_roads.osm.bz2` as an external candidate (my CYXY
refresh at 11:46, ledgered). OWNER: `--refresh-data airport_mod_cache`
for the VHHH pack's new-hash dump is yours to authorise (not covered
by the road-layer word). `planar/structures.py` at exactly 1,000
lines.

## 2026-09-15x v2objcut r1 MERGED (e178702f → main): signature B reads every VHHH shell at its authored floor (five for five); the hairpins wait on the ring builder (r2); signature A REFUTED by geometry (CITY2.obj roofs, 116 false corridors — the affordance stands); signature C RE-FOUNDED — Bridge3 is two mouth-marking wall pairs, not a 354 m pair

Lane @ e178702f (main merged through 106459fa); suite 1,607 passed
twice, 0 FAILED; suite ON MAIN after the merge reported below. VHHH dry
pair: floors 1.30/0.37/0.78/−1.63/−1.69 (bars met ±0.01), corridors
0 → 5, tunnels 28 → 23, basins identical (10 placements claimed);
`tunnel5_done` (owner site) + `TUNNEL2_DONE` refused by the ring
builder's axis offset on hairpins — the reading is right (floor 1.30,
trench 9,290 m², two portals), the emitter must take the object's
trench polygon (r2, `planar/structures.py` — after v2vmmcshore r2 lands
there). OTHH/LEMD six populations BYTE-IDENTICAL (+51/+25 named
refusals). Before-reading on the owner's 1.0.340 VHHH patch: vertices
outside the wall line 85/19/111/27/26 (worst 75.8–86.1 m), floor misses
0.90/1.85/1.44/3.85/3.91 m. A: retiring `kerb_wall_corridors` → VHHH
wall corridors 0 → 116, all inside `CITY2.obj` (10ap at a third
airport); predicate deleted, affordance stands. C: the scout's 354.2 ×
25.1 m box was the OBJECT BOX, not the solids — Bridge3 = two 73 m wall
pairs 14.02 m apart at its two ends, 224 m empty between (the author
marks the mouths; the bore is covered); Bridge2 two perpendicular
bands; Bridge4 no straight band. RULED §33 (6) MEASURED AND RE-FOUNDED
(C1′ pair = mouth ramp; C2′ band = polyline incl. curved; C3′ measured
before ruled). New `airport/object_cut.py`; `object_cuts` sidecar key;
families `object_cut_offset`/`object_cut_depth`; 18 twins. No VHHH
build (+22+113 road layers stale — the owner's refresh). Lesson (for
the scout protocol): a bounding box is not the solid — quote the
components' extents, not the box.
15x addendum: suite ON MAIN after the v2objcut merge (3b35df96): 1,607 passed, 1 skipped, 0 FAILED lines (40.7 s). After v2lemdstruct2 (287f9b5b): 1,587 passed, 0 FAILED.

## 2026-09-14av v2splitname MERGED (f960f53e): split files are named per distinct baked offset — the OTHH tunnel wall at 25.2697569, 51.6055534 gets its own file; VHHH 6 collisions → 0

Lane `v2splitname` @ 4b13e977. `body_resource_name(resource, k,
offset)` → `<stem>__b<k>_<tag>.obj`, tag = 8 hex of blake2s over the
offset triple (a HASH, not an index among the resource's offsets — an
index renames other placements' files when the population changes);
threaded through the three file-naming sites + `SplitFile`; the
carrier `Candidate` keeps the untagged slot id and `merged_into`
resolves through `file_of[(member, group)]` to the real file. OTHH
rebake replay, matched pair on the 1.0.334 products: 705 splits /
1,857 bodies both arms; names 1,856 → 1,857; collisions 1 → 0;
every row byte-identical but the tag; placement 14052 (the owner's
wall) → `tunnel1__b0_8b16464a.obj` baking its own [9.05, 9.55,
−50.10], 14051 → `__b0_c057eb1e`. VHHH 6 → 0 (two jetway frames,
`seabarier3__b0..b3`, +48 files); HECA/KCLT/LEMD/SPJC 0. Plan stage
unchanged. Suite 1,518 twice. Not done: a `--write-pack` round trip
at OTHH (the DSF re-encode on the new names end to end) — the app
build is that round trip.

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N] [--why-hard-stage 1]` on either a `--replay` arm or a `--why-from PKL`; `--why-from PKL --probe-site LAT,LON [--probe-drop M] [--probe-arm TERM=V ...]`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (**and THE CLUSTERS beside the partition and the groups** — lane ``v2padjoin`` 2026-09-14: a capture without ``Airport.clusters`` leaves §30 (4)'s cluster pad, its apron reach and §16g (10)'s derived pads INERT in every replay of it, so a pads-ON arm silently measures the pads-OFF law; a capture predating them has them DERIVED at replay off its own partition, named on stdout) (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently).  **`--why-hard-stage 1`** reads §20b STAGE 1's OWN ASSEMBLY instead of the full problem's (`solve.design.stage_split`'s drop + fixed): the AIRSIDE hard set, in the rows and the metre scaling stage 1 enforced them under. The full read cannot answer "does the AIRSIDE solve settle" — the airside rows are a subset of 325k whose population and scaling the stage's own drop changes — and that is exactly the claim RULINGS 13y (B) / 13ab / 14as make (lane `v2settle`, which used it to split HECA's "42 unsettled rows" into 9 CONSTANT rows the solve can never move, 6 HELD runway rows at the projection's own bar, and 18 real ones).  The shipped surface is read either way: an airside vertex's z IS stage 1's, so the stage-1 read at the shipped z equals the read at stage 1's own surface (measured identical at HECA). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate).  **`--probe-site LAT,LON` IS THE STABILITY PROBE** (lane `v2qp`, spec §20c, promoted from lane `v2settle` r2's `scratchpad/v2settle/probe3.py`/`probe4.py` on its second use): off a `--solved-out` pickle, one extra `Band` ceiling `--probe-drop` (default 0.30) metres under the ARM's OWN base surface at the vertex nearest the point, re-solved, and the moved set (> 0.02 m) binned by distance from it — 0-40 / 40-100 / 100-250 / 250-500 / beyond, with the worst beyond 250 m, each arm's hard set and its exit line.  `--probe-arm TERM=V` repeated makes it a MATCHED PAIR of `[design]` arms on ONE problem (`--probe-arm solver=fixed_point --probe-arm solver=qp` is §20c's own bar); with none it probes the shipped law alone.  This is the instrument RULINGS 2026-09-14bw's headline was taken on (HECA: 959 vertices moved by one 0.30 m row, 953 beyond 500 m, ZERO within 100 m).  `--design-weight TERM=V` also takes a NON-NUMERIC value now (§20c's `solver=qp`); a value that does not parse as a float is passed through as the string.    **`--placement KEY=V` IS THE CAPTURE-TIME LAW ARM** (lane `v2padqp`, spec §16g (10) (11)): the §16g (10) pad keys (`pad_from_cluster`, `pad_airside_clip`) are read in `classify/evidence._pads` and `planar/overlay` — UPSTREAM of the capture — so `--design-weight` (a `[design]` override applied at REPLAY) cannot arm them and a pads-ON replay of a pads-OFF capture silently measures the pads-OFF law; a matched OFF/ON pair is therefore TWO CAPTURES of one tree, never two edits of the shipped toml (the value is coerced to the key's own type, an unknown key refuses by name, and the arm is recorded in the pickle).  `--capture` also arms `harness/build_airport.arm_shared_repo_protection` — the ONE arming composition — and prints `[guard] shared repo UNCHANGED`.  Twin: `tests/auto_patch_v2/test_v2qp.py` (the probe as a fixture pair) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

## Tool: census

| `Ortho4XP/tools/harness/census.py` | You need DEFECT COUNTS from an emitted patch. Every law family always (the register, never a hand list), law-true frame from the patch's own sidecar, airside/groundside/mixed split, worst-N rows, class table, sidecar evidence, JSON + table, A/B across patches. **The only numbers that may be quoted as defect counts.** `--zone-split` additionally buckets the within-shape rows by FAN-RAMP ZONE membership (on a declared ramp piece / inside a zone / crossing one / unrelated, plus the rows already steeper than the zone cap) — reach for it when a grade law grants relief on declared ground and you need to know whether the relief is where the defects are. It is a flag and not its own tool because it needs the census's law-true frame; a private copy of that frame is the census-wrapper defect above. `--magnitude-bands [EDGES]` buckets EVERY law-true row by severity (|de| / step height; default edges `0.01,0.1,1,10` m, or your own ascending list) with the airside/groundside/mixed and adjudicated/version-deferred splits per band — reach for it when the question is which KIND of population a total is, not how big it is (the frame of record is stated in these terms: "0.1-1 m 13,711 = 45.1 %, 1-10 m 11,143 = 36.7 %, 82 % is in-band airside solver residual"). The bands PARTITION the census's own rows and the band below the first edge is the materiality floor's own. Promoted 2026-08-06 from the two lane copies that hand-rolled it (c6attr, c6tip). `--frame own\|base` selects the AXIS FRAME: `own` (default) is the patch's own sidecar and the only frame whose numbers are defect counts; `base` re-reads the SAME patch bytes with the SERVICE axes removed from its sidecar — the axis population a pre-road-feed sidecar carried — which is what splits "the class moved because the surface moved" from "…because the axis frame moved" (cycle 9/10: HECA 10 000 m read airside 4,610 own-frame and 4,474 base-frame, and the whole gap was ONE instrument defect). A base-frame number is a FRAME claim, never a defect count; the frame is stamped into every report either way (`axis_frame`). Added 2026-08-07 (cycle 10) in place of the hand-built filtered sidecars the cycle-10 probe made and threw away. `--rows-json OUT.json` additionally ITEMISES every law-true row — family, role pair, side, magnitude, grade/cap, site in layout-local metres, lat/lon, way ids — which is what turns a class table into an attribution: a net class delta hides equal churn by construction (a class that gains 200 rows at one site and loses 18 at another reads as "+182"), and only the rows say WHICH rows and WHERE. It is the census's own `all_rows`, the same population every count in the report is taken from, so the dump and the counts beside it can never disagree — `tests/test_harness.py` asserts the dump's class tally IS the report's class table, its side split IS the report's, and the worst-N table is its prefix. With several patches you get one dump per patch (a single file would silently keep the last). Added 2026-08-07 (cycle 10) for the road-pair receiver-only round's +182 decomposition. `--sites` clusters those same rows into DEFECT SITES and reports the other headline: how many DISTINCT defects a patch carries (law-true and adjudicated), ROWS PER SITE — the AMPLIFICATION FACTOR — per-site worst |de| / step and worst grade excess, the families, role pairs and shape ids each site spans, its bbox + centroid lat/lon, and a SIM-VISIBILITY flag. Reach for it whenever a row total is about to be quoted as a defect count to a human: row counts AMPLIFY and site counts do not — one over-cap region on one apron mints hundreds of edge-granularity rows (HECA's way -12407 alone carries ~800; the road-feed round's 180 threshold-flip sites live on 19 shapes, 72 % of them on four aprons), so "thousands of defects" is a count of PAIRS THE LAW PRICED and differs from the number of things wrong with the surface by whatever the amplification happens to be on that patch. THE CLUSTERING RULE, printed with every table so a site count is never read without it: two rows join one site iff SAME LAW FAMILY and (shared way id OR shared canonical node), where a canonical node is the census's own weld tolerance (`LAW_TRUE_KNOBS['proximity_m']` = `check_grade.SHARED_VERTEX_TOL_M`, 0.5 m) applied to the rows' endpoints in layout-local metres — the law's own "these two vertices are one node" predicate, never a proximity semantic invented for a report; sites are the connected components (union-find), and no magnitude, role or geometry test takes part. `--site-visibility M` moves the visibility threshold (default 0.05 m of relief = silhouette-visible candidate); it is a REPORTING threshold and an assumption — nothing has measured it in the sim — never a law, and the law still adjudicates every row regardless. `--sites-json OUT.json` dumps every site with its full membership as row indices into the census's own magnitude-sorted order, so it joins a `--rows-json` dump by position. The sites PARTITION the census's own population — `census_one` REFUSES if they do not, and `tests/test_harness.py` §9 carries the known-answer twin (two hand-built sites, one joined by way id and one by weld, asserting count, membership, amplification and both visibility flags) plus the union-equals-`all_rows` lockstep. Added 2026-08-07 (cycle 10) for the owner's "why does the battery still read thousands of defects" question. **THE HEADLINE the section reports is ACTIONABLE SITES** — the MATERIALITY FLOOR (owner RULINGS 2026-08-07, "we don't need to be grading to less than 0.5m") adjudicated per site, since a site is the unit that sentence is about: 40 one-centimetre rows on one apron are one place owing 0.4 m of grading, not 40 defects. A site is actionable when its ADJUDICATED rows accumulate ≥ **0.5 m** of unlawful excess, OR one of them is a single step ≥ **0.15 m** or sits at ≥ **2× its own cap** (the SHARP GUARD — "we don't want any sharp bumps", the half a bare accumulation floor throws away), OR it touches the **RUNWAY FAMILY** (`runway` / `runway_crossing`), which is never floored because reg-derived precision governs there. Every constant is a named knob in `check_grade` (`MATERIALITY_FLOOR_M`, `MATERIALITY_SHARP_STEP_M`, `MATERIALITY_SHARP_GRADE_CAP_MULTIPLE`, `MATERIALITY_RUNWAY_FAMILY_ROLES`) citing the ruling, and all of them ride in every report beside the counts — the floor is PROVISIONAL and two site tables taken at two floors are not comparable. ACCUMULATION is `check_grade.row_excess_m` summed over the site's adjudicated rows only (a version-deferred or out-of-scope row is not a defect and may not fund one): the EXCESS, not the magnitude — a 3.2 m rise over 200 m of 1.5 %-capped taxiway is a 3.2 m magnitude and a 0.2 m excess. A family that prices a CAP rather than metres (`MATERIALITY_UNMEASURED_FAMILIES`, today `lateral_contiguity`, whose `de_m` is a bare grade difference over no span) funds nothing AND keeps its site actionable — a floor may only relax what it can measure. A site the floor takes out is REPORTED under the **`sub_floor`** label with its rows and worst |de| (counted-never-dropped, the `VERSION_DEFERRED_FAMILIES` / `disconnected_ring` convention), and actionable + sub-floor PARTITIONS the adjudicated sites — `census_one` REFUSES if it does not. Twins: `tests/test_harness.py` §10 (both sides of every constant, each guard half proven to fire ALONE, the runway exemption, the label locked to its register, the production refusal). Alongside it, ROLE-LESS FEATURE WAYS SIDE WITH THEIR HOST (lead ruling 2026-08-07): an `o4_feature` way with no `role` tag — `shape_interior_ring` / `gap_interior_ring` / `gap_drainage_spine` / `crown_spine`, 232 of them at HECA — used to fall through to the caller's default 1.5 % cap and to AIRSIDE whatever its host was; `check_grade.resolve_feature_hosts` (shared-node majority, ties on `layout.AUTHORITY_RANK`) and the drainage law's own parent selection now supply the role and side for REPORTING ONLY — the `role` tag is law input and is never written — and a row whose host's vertex set COVERS it is adjudicated `role_less_host_duplicate` (one geometry, one row set), reported under its own heading and never dropped. §10b twins. `--no-cache` / `--clear-cache` govern the CENSUS CACHE: the full report is memoised under `Ortho4XP/tmp/census_cache` (lane-local, gitignored, `$O4_CENSUS_CACHE_DIR`, REFUSED inside the shared data repo, and off inside pytest unless the root is named) keyed by the patch BODY sha (`build_airport.body_sha256`, the `tail -n +3` the frozen MANIFESTs speak) AND the whole-file sha (the census PRINTS the provenance stamp the body hash excludes), the sidecar BYTES (never an enumeration of its law keys — that is the wrapper defect), the run ledger's own code-tree hash (`run_with_ledger.code_tree_hash`, so a `check_grade.py` edit misses), `LAW_TRUE_KNOBS`, the `O4_*` environment and the option frame. A hit re-prints the stored report and re-writes the stored `--json` / `--rows-json` / `--sites-json` bytes, so it is the fresh output plus exactly ONE line — the `[CENSUS CACHE HIT] …` marker, first, immediately before the `=== CENSUS …` header, printed even under `--quiet`; a miss prints nothing. No number, family or law changes: memoisation, not measurement. Twin: `tests/test_census_cache.py`. The census also prints THE BUILD'S OWN AIRSIDE-SCOPED CERTIFICATE beside its counts (air7, RULINGS 2026-09-01l/r): the solve's law-graph verdict on the zero-airside beta bar, read verbatim from the sidecar's `airside_certificate` EVIDENCE key (readings per certificate site + the last-exit verdict; row-side partition, check_grade's quantization allowance imported) — a DIFFERENT instrument over a DIFFERENT population (law edges at exit vs emitted node pairs): agreement is corroboration, disagreement is a finding, and neither replaces the other. Twins: `tests/test_solve_certificate_instrument.py` TASK 6. **THE COCKPIT BLOCK IS PRINTED FIRST** (owner RULINGS 2026-09-12x/12y; `design-surface-spec.md` §31 (6), lane `v2cockpit`): before any other line the census classifies its OWN rows into CRITICAL MOTION (a `step`-class family over `[cockpit] motion_step_m` 0.05 m BETWEEN WELDED NEIGHBOURS — ends no farther apart than `emit.instrument.step_contact_tol_m`, the law's own weld spacing — where BOTH roles are ROLLED-ON — the runway family, the taxi family and the apron, derived from `precedence.toml`, never a literal list — plus the `grade_break` families the runway/taxi rate laws forbid, which carry no span test because a curve is long by definition), CRITICAL VISUAL (a WELDED `step`-class row over `visual_m` 0.5 m inside the airport boundary or within `approach_km` 5 km of a runway axis) and REPORT (everything else: every slope excess, every keep-out row, everything under a threshold, and everything beyond the view — §31 (4), "centimetres are not a goal"), each with its count, worst magnitude and worst COORDINATE. It is a CLASSIFICATION and never a measurement: no row is created, dropped or re-priced, and `cockpit_block` REFUSES if its three buckets do not add up to the population handed in. **THE SPAN RULE** (owner RULINGS 2026-09-12ad, round 2): a step-family row read SPANNED — ends farther apart than the weld spacing — is a SLOPE, not a discontinuity: it is grade, judged by its own cap, and is REPORT.  Round 1 classed a 2.69 m rise over 81 m of LEMD taxiway as critical motion and the block read 452; every one of those rows was spanned and LEMD now reads 0.  The REPORT line names what the rule moved — how many spanned rows would be over the motion threshold and how many over the visual one if they were welded — so the count is never folded into an anonymous total.  **THE CLIFF ESCAPE** (owner RULINGS 2026-09-12af, round 3) bounds it: a spanned row whose implied grade `|dz| / span` exceeds `[cockpit] cliff_grade` is a CUT or a RISE, not ground, and is judged as though it were welded, under its own reason `cliff` (on rolled-on pavement CRITICAL MOTION — no aircraft rolls a 1:3).  LEMD's `strip_seam_tear`, 8.27 m over 3.01 m = 275 %, is the row that made the rule.  The escape restores the BUCKET, never the threshold: a 0.4 m cliff is still under `visual_m` and still invisible.  `cliff_grade` holds a DOTTED LAW PATH (`emit.design.bank_slope`), never a number: the design surface's own 1:3 bank is already the line between "ground a pilot reads" and a wall, and `tables.cliff_grade` resolves it — change the bank and the cliff line follows, with no second copy to drift.  The loader refuses a path that does not name a grade in (0, 1] over the motion threshold.  **ROUND 4** (owner RULINGS 2026-09-12aj) repaired three READER defects the block's own output exposed, all in `check_grade.py`: the three RATE/ARC readers (`strip_arc`, `raoa`, `airside_no_step`'s §1.2 half) built rows with NO lat/lon, so `run_checks`'s fallback stamped each with the CENTROID OF ITS RING — 36 rows of LEMD apron `pav12` printed one coordinate 560 m from the wall they had found, and a whole round of attribution went to the wrong place; every rate row now carries its own pair midpoint (`_rate_row_site`, off a projection that gained an `inverse`). A rate row's `distance_m` published the HALF span `0.5*(dp+dn)` while its `de_m` spans `dp+dn`, so every implied grade read 2x (LEMD's five apron rows printed 0.37-0.46 and are really 0.20-0.23); it is now the full separation, and the allowance keeps the half span because that is the rate law's own averaging term. And the CLIFF ESCAPE now reaches EVERY family, not only `step` ones — LEMD's two sharpest readings of the same wall, a `within_shape` 81 % and a `cross_shape` 240 %, are class `grade` and could not be cliffs at all — while `row_roles` returns THE FACES ON EACH SIDE of the pair rather than the ring it was walked on: a within-shape pair has one ring for both ways, so the pad rim standing over the apron read `building|building` and the rolled-on test called it landside. `run_checks` indexes every node to the SENIOR face carrying it (`precedence.toml` authority order, an identity join on emitted coordinates at millimetre quantisation — never a proximity match) and stamps `role_a`/`role_b`; `row_roles` prefers them. A patch with no `boundary` role way (v2 emits none today) says so and the approach corridor alone decides view. IN VIEW BY APPROACH IS **THE APPROACH CORRIDOR** (owner RULINGS 2026-09-12al, §31 (2)): per runway END, `[cockpit] approach_km` beyond the threshold along the extended centreline and `approach_half_width_m` to each side, derived ONCE in `src/auto_patch_v2/law/approach_corridor.py` and read by the engine's mouth gate (`planar/structure_approach.FieldRegion`, §29 (1)) through the same class — the harness takes its axes from the emitted runway rings, the engine from the apt.dat thresholds. The first reading, "within `approach_km` of a runway axis", admitted the whole airport (at LEMD 4,318 of 4,408 rows, at HECA 8,122 of 37,364 — the corridor leaves 90 and 29,242 of them respectively behind) and is DELETED, not gated. Every family's class lives in `law/families.toml` (`cockpit = step|grade_break|grade|keepout`, REQUIRED — a new family without one does not load) and the four numbers in `law/emit.toml [cockpit]`. Twins: `tests/test_harness.py` §7. **§38 THE TILE SEAM (owner RULINGS 2026-09-13ah / 13am / 13an; lane `v2seampin`)** adds the two families the census had no instrument for. `seam_residual` prices every tile-seam band-edge vertex against ITS OWN tile's baked DEM sample — the value the solve PINNED, published per pin in the sidecar as `seam_pins` = `[lat, lon, dem_z]` (all of them since 13ah; the M3a sidecar published only the subset a soft preference happened to honour). Class `step`, so the cockpit rule gives it CRITICAL MOTION on the rolled-on roles and VISUAL elsewhere with no second threshold. It is the reader the SPLP berm needed: 106 rows, max 3.433 m, 31 of them CRITICAL MOTION on `runway|runway` (worst 0.629 m) — while `strip_seam_tear` read 0 over the same 3 m ridge. `bank_across_seam` prices any `bank_foot` node inside the band (`seam_half_width_m`, also published), class `keepout`: one node is the whole defect, because 13an measured a chain 0.0237 m off the meridian that Triangle4XP split 16,298 times against the unsplittable tile border. The bank foot is ROLE-LESS, so this family reads the `feature_out` channel of `_parse_osm`, not `ways` — a reader that walked `ways` prices nothing. Both are sidecar-declared like `eat_ceiling`: a patch with no key (v1's output, or a v2 patch predating §38) reports nothing and reads exactly as before. This is where the lane's seam-vertex/DEM probe was PROMOTED to (RULINGS `7e90032` second-use rule) — there is no separate script. Twins: `tests/test_harness.py` §38 (both directions of both families, at SPLP's own worst numbers, plus the cockpit classes read out of `families.toml`). |

| `Ortho4XP/tools/census_matrix.py` | You have MANY census JSONs — a multi-airport, multi-world round's arms — and the question is "did any cell's AIRSIDE count RISE against the arm we promised not to regress" (the Q4 gate) and "where did the change land". Lays the arms out as one table (lawtrue / adjudicated / airside / groundside per cell), applies a stated per-cell airside CEILING (`--gate ARM`, default the first census listed, or `--gate-json FILE` for a recorded frame of record), prints the arm-vs-arm delta and, with `--bands`, the census's magnitude bands. **It measures nothing and derives no number** — every value is read verbatim from a `harness/census.py --json` artifact; a reporter that recomputes a defect count is the census-wrapper defect. Equality PASSES the gate ("may not rise"); a cell with no ceiling is reported as ungated, never as a pass. Promoted 2026-08-06 from `tmp/c8fin/mx.py` on its second use (c9feed) — promote-on-reuse; the lane copy hard-coded one round's frame as a module constant. Twin: `tests/test_census_matrix.py`. |

| `Ortho4XP/tools/census_rows_diff.py` | You have TWO `harness/census.py --rows-json` dumps (a control arm and an arm under test) and the question is WHICH rows moved, not how many. A class delta hides equal churn by construction — 200 new and 182 gone read as "+18" — and the zero-new-adjudicated-airside bar is a claim about ROWS, so it needs a row-level reader. Joins the two dumps in three labelled tiers: EXACT (same family / role pair / side, both endpoints identical to the millimetre in the patch's own layout-local metre frame), MOVED (same class, nearest surviving partner within `--tol`, default 0.50 m, each partner used once — an INFERENCE, labelled one everywhere, and quoting two tolerances is how you show the join is not doing the work), and NEW / GONE (no partner — the rows an attribution owes a mechanism for). **It derives no law and measures nothing**: every row is read verbatim out of a census dump, the census staying the only instrument that produces defect counts. REFUSES a join across different `law_true_knobs` or a different axis frame (two dumps read under different law are not one population), a class-level census JSON, and a truncated dump. `--side` / `--family` filter the REPORT, never the join. Twin: `tests/test_census_rows_diff.py` (the four tiers on a hand-built scene, the tolerance knob both ways, class isolation, endpoint-order invariance, partner-used-once, nearest-wins, exact-beats-near, every refusal). |

| `Ortho4XP/tools/pad_span_census.py` | The question is DOES THIS UNIT'S OWN DATUM FIT ITS BODIES' PADS — *how far apart do the emitted `building` pads one FOOTPRINT UNIT stands on actually stand?* — the single number owner RULINGS 2026-09-14c item 1 is accepted or refused on (spec `object-placement-spec.md` §16g (1)/(7)). No other instrument asks it: `harness/census.py` prices PAIRS OF VALUES, so an object seated 23.70 m above its own pad breaks no grade law and reports ZERO rows; `obj8_split_report.py` prints a body's anchor and its own ground but never asks whether the bodies sharing ONE unit's datum stand on pads that disagree; `role_overlap_read.py` is an AREA sweep and `role_edge_census.py` a boundary-length one. This is the unit-vs-pad reading: per unit, the `building` pads its bodies' FEET fall inside, how many bodies it holds, and the SPAN of those pads' planes, largest first. **It measures no law and counts no defects** — the pads are the emitted design surface's own `building` faces at `median(z)` over the ring, which is the plane `footprint_unit` reads through `anchor_rule.pad_plurality`, and the body→part join is the PART ID, never a proximity match (memory `canonical-identity-join`). `--over` (default 1.0 m) is the listing floor 14g stated its bar in, not a threshold with any standing. It takes either `o4_v2_placement_<ICAO>.json` or an `obj8_split_report --json` dump — both carry the same `splits` body records. Measured basis (scout `v2heca331` on the owner's 1.0.331 HECA): 17 units whose pads span > 1 m over 1,363 bodies, `fu:38:20` alone 978 bodies on 136 pads spanning 34.8 m — the unit chained on PART BOXES, and its DECK member then gave 96.20 to 1,509 bodies. Promoted 2026-09-14 from that scout's scratchpad `padspan.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse) — the 14g attribution, then lane `v2connector` round 3's before/after. Several patches are reported separately; quote it on identical options. Twin: `tests/test_pad_span_census.py` (the span IS the unit's own pads, a non-`building` face is not a pad, a unit on one pad is not a row, a body with no `unit_of` is not counted, the floor both ways, the CLI's JSON IS the library result, and this index row). |

| `Ortho4XP/tools/role_edge_census.py` | The question is WHAT SHARES AN EDGE WITH WHAT — *how many metres of a groundside shape's boundary run along AIRSIDE PAVEMENT in an emitted patch* — the single number owner RULINGS 2026-09-12c is accepted or refused on ("shapeID 81 ... cannot be groundside because it shares a long edge with an apron. Something can only be groundside if it has no connection to airside other than a service road"). No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a lot welded flat along 828 m of apron breaks no grade law and reports ZERO rows; `role_overlap_read.py` asks AREA overlap (what STANDS on what), which is 0 for two faces that merely share a boundary; `osm_site.py` answers one coordinate. This is the BOUNDARY-LENGTH sweep: per groundside shape its area, perimeter, inscribed radius (area / perimeter) and the metres shared with airside pavement / with `service_road`+`service_junction` / with `building`, largest first; `--min-m` (§27's `[lot] airside_edge_min_m`, default 10) and `--min-radius` (its sliver floor, default 1.0 m) split the population into SUBSTANTIVE, SLIVER and LOT-class. **It measures no law and counts no defects** — geometry, roles and the groundside partition come from the harness library (`check_grade._parse_osm`, `effective_role`, `_GROUNDSIDE_ROLES`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. Edges are joined on NODE IDENTITY — a shared edge is two shapes listing the same node pair, exactly what the planar weld produces — never a proximity match (memory `canonical-identity-join`). Measured basis (shipped 1.0.320 LEMD): 175 groundside shapes, 105 sharing >= 10 m with airside pavement, 71 substantive (182,604 m², 34 slivers excluded), of which 13 LOT-class / 145,262 m² — the owner's shapeID 81 (`pav137`) 140.2 m of its 270.9 m perimeter, `pav125` 828.4 m. Promoted 2026-09-12 from the `v2lemd320t` scout's `census_gs.py` on its second use (RULINGS `7e90032`). Several patches are reported separately — the arm-to-arm read; quote it on identical options. **`--pad-frontage`** is the SECOND question on the same geometry and the same joins (added 2026-09-12, lane `v2frontage`, spec §28): *pad -> neighbour -> shared edge m -> STEP m*, the read owner RULINGS 2026-09-11ai-1 -> 2026-09-12r ("grade frontages only") is accepted on. No other instrument answers it either: the harness census FORGIVES a declared terrace across a shape joint (`terrace_joints_ll`), so a car park standing 3 m above the terminal it fronts prices ZERO rows — and at LEMD the owner's +3.03 m is not even a declared joint (the patch carries 4, none of them `building4`'s). Per `building` shape: each groundside neighbour (`groundside_pavement` / `service_road` / `service_junction`, `parking_lot` by its class tag), the metres of edge they SHARE by node identity, the facing-vertex pairs within `--near` (default 2.0 m) and the largest and mean SIGNED step, neighbour minus pad. The proximity read is not a shortcut: the pad-frontage relation is a proximity relation in the engine too (`[design] pad_frontage_m` 3.0, owner RULINGS 2026-09-10ax (1)) and `building4` / `pav124` share not one node while standing 0.71-1.50 m apart. `--min-step` (default 0.05 m) is the listing floor. Measured basis (shipped 1.0.321 LEMD): ONE pad with a groundside step >= 0.10 m — `building4`, `pav124` +3.03 / +2.67 and `route6` +0.38. Twin: `tests/test_role_edge_census.py` (the shared edge IS the node-identity join, the airside-pavement set excludes `building`, service-road metres are reported apart, the sliver split, prices-no-law, the pad-frontage step across a proximity gap and across a welded edge, and this index row). |

| `Ortho4XP/tools/void_census.py` | The question is about ENCLAVE TOPOLOGY on a shipped patch: which regions does airside pavement completely surround, which of them have a tunnel/bridge ESCAPE, and what is sitting inside them. Reads back exactly the geometry the enclave region law computes (`auto_patch/enclaves.py`). `--union` selects WHICH union, because the law has two and they answer different questions: `surround` (default) is airside ∪ BUILDINGS, the set published as `layout.airside_enclaves` and the CLASSIFIER's question ("is this ground airside-interior?"); `pavement` is airside pavement only, which is the GAP LAW's own detection union and therefore the scope of the adjacent-ground BAND KEEP-OUT (`enclaves.enclave_band_keepout_union`). The distinction is load-bearing and was measured: buildings standing in HECA's 3.4 km² infield subdivide it into pocket-width components in the `surround` union while the gap law holds it as ONE wide region and declines it on width, so scoping the keep-out by the wrong union deleted 152,734 m² of Annex 14 §3.4.11-13 graded strip. The union is stamped into every report — two unions are two populations. Reports per void its area, perimeter, minimum-rotated-rect SHORT SIDE and POCKET flag (short side ≤ the gap law's own `GAP_FILL_MAX_WIDTH_M`, the class the ruled gap ring + spine treatment covers; under `--union pavement` that flag IS the band keep-out's membership test), the escapes, whether the gap treatment emitted a face there, the per-role/ref contents, the retaining-wall inventory with way ids, and the BARE GROUND remainder carrying no shape at all — the 87.6 % that made the shape-scoped G-ENCLAVE predicate structurally blind. `--bands` adds the ADJACENT-GROUND inventory beside the topology: band and `adjacent_ground_wall` way counts and areas, split by where each way SITS — inside a POCKET no-escape void (the keep-out's own territory), inside another no-escape void, or outside every void — each way in exactly one column, the columns summing to the total. Reach for it whenever a band-area delta is about to be quoted: the total alone cannot tell a keep-out that removed band inside pocket voids from one that also took ground nothing owns, and that is precisely the failure the ratified scoping fixes. **It measures no law and derives no defect count**: grade defects come from `harness/census.py` and nowhere else, and the role vocabulary plus the escape set are IMPORTED from `auto_patch.enclaves` rather than re-typed (the census-wrapper precedent). Parses with the harness library's own reader (`check_grade._parse_osm`) in the builder's anchor frame from the axes sidecar, so this tool and the census read one geometry; without a sidecar the topology is unchanged and lat/lon are simply not reported. FRAME: emitted geometry is post-decimation and post `_separate_groundside_from_airside`, so a void reads slightly larger than the in-build region and a groundside shape inside it reads pulled back from the rim; a real-DEM patch is never comparable with a constant-DEM one. The in-build predicate also honours the `is_bridge` SHAPE FLAG, which `to_osm` does not emit — so this reader sees the four escape ROLES and no more (stated by the tool itself). Promoted 2026-08-07 from `tmp/enclave_attrib/void_census.py` on its second use (promote-on-reuse); the lane copy carried its own patch reader and a hand-typed role list. Twin: `tests/test_void_census.py`. |

| `Ortho4XP/tools/seat_feet_census.py` | THE DRAPE RESIDUAL AT EVERY PLACEMENT'S FEET (RULINGS 2026-09-09ac (3); the placement reading 11e (3), spec §7/§9) — `--placement-plan o4_v2_placement_<ICAO>.json` with `--mesh` (a built mesh) or `--graded` (the emitted design surface, for a dry run with no tile built): per placement of the plan's own rows, `surface(foot) − (surface(anchor) + y_foot)`, the |Δ| histogram (<0.3 / 0.3-1 / 1-3 / >3 m), the same by class, the worst N with lat/lon, and §13's elevated-body / footless-carrier bars. Feet are read from the AUTHORED pack (`.anchor_bak` when one exists). THE SEAT-RESULT MODE IS DELETED (owner RULINGS 2026-09-12s, spec §8) — the name is kept because the INDEX row, `obj8_split_report` and the twins address it by it. Writes nothing to the pack. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. CRITICAL MOTION is named as an instrument limit rather than printed as a zero HERE: §17's motion reading needs the graded face ROLE under each foot, and this tool hands the block none — `obj8_split_report.py` is the entry that takes it (owner RULINGS 2026-09-12am (2), lane `v2objmotion`). §16e (owner RULINGS 2026-09-13k, lane `v2othhdatums`): `--placement-plan --mesh` WAS BROKEN — it passed its bbox as `(lat, lon)` to `MeshElevationSampler`, which takes `(min_lon, min_lat, max_lon, max_lat)`, so at OTHH it asked for a box at lon 25.2 / lat 51.6 and the sampler raised `no mesh triangles inside ... — wrong tile?`; the one place the two orders meet is now `plan_bounds()` and a twin holds it end to end over the sampler's own mesh fixture. The report also prints `§16e bodies on a DATUM` (a crest plate / a deck top) as its own class and EXCLUDES them from §13's `elevated bodies as own files` bar: a datum body's `y_zero` is +5 … +10 m by construction, and counting it there reported the law as the defect (OTHH 0 -> 10 -> 0 with the class printed apart). §16e (3) (Fable 2026-09-13, RULINGS 2026-09-13v, lane `v2bridgecontact`): the report also prints THE BRIDGE FAMILY block (`airport/bridge_family.census_bridges` / `census_bridges_lines`, re-exported through `placement_census`, the same call `obj8_split_report` makes over the same plan shape) — per `Bridge_NN` the deck's own body's world DECK TOP against the land under that bridge's own written geometry (`|deck top - highest land|`, bar `[cockpit] visual_m` 0.5 m), the PER-PLACEMENT zero spread (`max - min` of `surface_z - y_zero` over one placement's bodies; `Bridge_02_CLUTTER_007` is six piers of ONE solid), the CROSS-BRIDGE carriers (a body whose `merged_into` names a file of another bridge, bar 0) and how many bodies publish `bridge_of` and agree with the resource's own tag. The `Bridge_NN` axis is the CENSUS's, never the law's — §16e (3) exists because the name does not name a bridge — so the agreement count is the instrument's own check on the derived relation. Measured on the app's 1.0.326 OTHH frame: `Bridge_01` deck top 3.23 -> 3.96 and `Bridge_04`/`Bridge_05` KEPT -> 3.96 (all three |deck top - land| 0.00, PASS), cross-bridge carriers 2 (unchanged — the bind and the filter are refuted and deleted, see `bridge_family`'s module doc). |

| `census_lockstep.py` | `harness/census.py` (law-true + bare frames, class table) |

## Tool: census_rows_diff

| `Ortho4XP/tools/census_rows_diff.py` | You have TWO `harness/census.py --rows-json` dumps (a control arm and an arm under test) and the question is WHICH rows moved, not how many. A class delta hides equal churn by construction — 200 new and 182 gone read as "+18" — and the zero-new-adjudicated-airside bar is a claim about ROWS, so it needs a row-level reader. Joins the two dumps in three labelled tiers: EXACT (same family / role pair / side, both endpoints identical to the millimetre in the patch's own layout-local metre frame), MOVED (same class, nearest surviving partner within `--tol`, default 0.50 m, each partner used once — an INFERENCE, labelled one everywhere, and quoting two tolerances is how you show the join is not doing the work), and NEW / GONE (no partner — the rows an attribution owes a mechanism for). **It derives no law and measures nothing**: every row is read verbatim out of a census dump, the census staying the only instrument that produces defect counts. REFUSES a join across different `law_true_knobs` or a different axis frame (two dumps read under different law are not one population), a class-level census JSON, and a truncated dump. `--side` / `--family` filter the REPORT, never the join. Twin: `tests/test_census_rows_diff.py` (the four tiers on a hand-built scene, the tolerance knob both ways, class isolation, endpoint-order invariance, partner-used-once, nearest-wins, exact-beats-near, every refusal). |

## Tool: check_grade

| `Ortho4XP/tools/check_grade.py` | You want the grade validator's CLI on one patch, or its library from code. The CLI is a thin front end over the same law reader the census uses. A run with no sidecar is CONTEXT-FREE and overcounts — it is not a defect count. It also prints **THE COCKPIT BLOCK FIRST** (owner RULINGS 2026-09-12x/12y; §31 (6)) — the same `cockpit_block` / `cockpit_block_lines` the harness census and the pytest fixtures call, over the SAME run's `family_out` (the checks' own output is buffered and replayed under the block, never run twice). A `strip_seam_tear` row carries the PAIR MIDPOINT as its lat/lon (spec §32 (3), RULINGS 2026-09-12ag): it used to carry none, and `run_checks` filled it with the offending way's RING CENTROID — at LEMD that sent the cockpit block's first CRITICAL VISUAL find 220 m from the 8.25 m tear. Twinned both sides (`tests/auto_patch_v2/test_v2zoneclamp.py`), the engine's own `verify/strips.strip_seam_tear` alongside. The block's "in view by approach" test is the ONE approach corridor of `auto_patch_v2.law.approach_corridor` (RULINGS 2026-09-12al; twins `tests/auto_patch_v2/test_v2approachcorridor.py`), never a radius around a runway vertex. **`adjacent_ground_step`** (spec §34 (4), lane `v2rampwalk` 2026-09-13) is the WITHIN-FACE welded step on a v2 `adjacent_ground:*` face — the reading no family had: `graded_strip` carries no within-shape cap, `adjacent_ground_tear` fires only under a 1 m edge and `strip_seam_tear` is the CROSS-shape twin, so a band holding its designed level over a mapped road's own ground (LEMD `zone2#2`, 1.73 m over 1.5 m at road −6289) was priced by nothing. Its floor is the cockpit's own `visual_m` AND `cliff_grade` in one step: without the cliff term it counts the lawful hillside drape (measured CYXY 296 rows). Lockstep both sides — `auto_patch_v2.verify.strips.adjacent_ground_step` reads it in the engine; twins `tests/auto_patch_v2/test_v2rampwalk.py` and the v1/v2 census parity test. **`ramp_in_road`** (spec §34 (10), owner RULINGS 2026-09-14bb/14bc/14bd, lane `v2othhramp`) is the CRITICAL presence family the road margin needed: every ramp arriving at a road ends at the road's TRUE edge — the centreline offset by the road's own half-width toward the ramp, ONE derivation `planar/wall_corridor_ramps.road_true_edge` read by every ramp emitter — so a RAMP vertex standing INSIDE a road ribbon is a lane of carriageway cut away, whatever its elevation. No other family sees it: a ramp welded flat into the road it ate breaks no grade law and prices zero rows. A vertex within the census's own weld tolerance of the ribbon's edge is ON the edge, which is what the law asks for. It reads 0 at OTHH before and after — the family is the GUARD on that derivation and never a defect count. Twins: `tests/test_harness.py` §34 (10) (both directions, the weld line both ways, the register and the cockpit class, and the ramp-role set read from the law's own structure roles). **`ramp_in_strip`** (spec §34 (5) (b), Fable 2026-09-15 / RULINGS 2026-09-15h, owner 15e item 7, lane `v2lemdstruct2`) is its AIRSIDE sibling: the covered extent of an underpass beneath a taxiway or runway spans the pavement AND its graded strip, so a RAMP vertex standing inside that strip is a trench in the ground an aircraft leaving the pavement runs out onto — LEMD 40.4611623,-3.5444804, where a code-E strip is 19.0 m and the trench face stood at 15.5 m under a 5.42 m unbanked drop, the airport's worst CRITICAL VISUAL row. The strip region is ONE derivation with `planar/zones.zone_regions` and `planar/structure_underpass.strip_half_width_m` (the zone-2 half width for the cell's class, the zone-1 LIP where the class declares none), read from the LAW with a literal no-engine fallback the twin asserts against. TWO READINGS MEASURED, NOT CHOSEN: the face's sidecar HOLES are applied and the pavement SOLID is subtracted, so the region is the BAND — read ring-blind and disc-shaped the first arm reported 52 LEMD rows, every one inside `cross_connector:pav61`'s own 144,429 m2 void and up to 220 m from any kerb, and `de_m` can now never exceed the class's own half width. Twins: `tests/test_harness.py` §34 (5) (b) (both directions, the class's own half width against the zone law and the planar derivation, the taxiway-loop void, the weld line both ways, the register and the cockpit class). **THE RUNWAY SHOULDER'S OWN CAP** (spec §40 (2) as amended, owner RULINGS 2026-09-13dd, lane `v2roles`): a within-shape pair BOTH of whose nodes lie beyond their runway's own half width is priced at `shoulder_transverse_max` (2.5 %, ICAO Annex 14 §3.2.4), not the runway's 1.5 % — a §40 (1) SHOULDER keeps the runway's DATUM, not its cross-fall. The line is the SOLVE's and is read, never re-derived: the sidecar's `runway_axes` (`[ref, lat_a, lon_a, lat_b, lon_b, half_m]` off the apt.dat ends and width) and `shoulder_transverse_max`, through `shoulder_nids` / `_shoulder_cap`. Fitting the width to the runway RINGS instead would read a shoulder as part of the runway and never find its own line. A patch with no key reads exactly as before. One reading with the generator and the v2 verify (`auto_patch_v2.law.tables.runway_transverse_cap`); twins `tests/auto_patch_v2/test_runway_shoulder.py`. |

## Tool: site_read

| `Ortho4XP/tools/site_read.py` | You have a coordinate from an owner's sim read and the question is WHAT THE OBJECT STAGE MADE OF IT — not what the OSM patch says there (`osm_site.py`, the emitted ways) and not one law's defect count (`harness/census.py`). Three products of ONE build, read at ONE point in one process: the emitted DESIGN SURFACE's faces containing or near it (role, ref, side, z min/med/max, node count — a CONTAINING face reads 0.0 m, never the distance to its nearest vertex, which is `osm_site --at`'s own trap); the DSF ROWS standing on it (`OBJECT` / `OBJECT_MSL` / `OBJECT_AGL` with the resource and, where it has one, the written elevation — `None` for a plain `OBJECT`, never 0.0); and the PLAN BODIES whose plan box reaches it, each with its §6 class, its FOOTPRINT UNIT, its surface z and zero and the stage's own ANCHOR REASON verbatim, which is the line that says WHY a body is where the owner saw it. `--patch-dir DIR` resolves `<ICAO>.graded.json` and `o4_v2_placement_<ICAO>.json` by glob (an `obj8_split_report --json` dump works as `--plan`: the same `splits` records), `--dsf-dump` takes a DSFTool TEXT dump — pass the PRISTINE `<dsf>.anchor_bak...text` (`dsf_write.pristine_dsf_path`) when you want the pack as INSTALLED rather than as this repo last wrote it. `--show`, `--max`, `--json`. **It measures nothing and derives no law**: every value is read verbatim out of a product and nothing is written. Promoted 2026-09-14 (RULINGS `7e90032`, promote-on-reuse) from the scratchpad reader of the 14g HECA attribution, re-written for the 14bl LEMD one (scouts `v2heca331` / `v2lemd336o`) and used a THIRD time by lane `v2leafframe` — three copies of one question, already drifted in their hard-coded LEMD paths. Twin: `tests/auto_patch_v2/test_v2leafframe.py`. |

| `Ortho4XP/tools/arm_site_read.py` | The question is about a PLACE across two arms — "is the wall at 35.2077303,-80.9290869 still there, and did anything near it get worse?" — which an A/B leaves open: `census.py --rows-json` itemises rows and `census_rows_diff.py` joins two dumps class by class, but neither can be asked about a coordinate, and `osm_site.py` reads geometry without law rows or pad seats. This is the join: per named `--site`, per arm, the law-true rows within `--radius` with their worst grade and |de|; with `--seats`, the BUILDING PAD seats that moved between the arms — the channel this repo's HECA airside attribution ran through (a pad seat welds into the apron ring, so a seat that moves moves airside; measured 2026-08-12b: 92 of 215 pads, median 0.32 m, and building211's +0.88 m carried +203 apron rows). **It measures no law and counts no defects**: rows are read verbatim out of census `--rows-json` dumps and geometry/altitudes through the harness library's own `check_grade._parse_osm`, so this tool and the census read one file one way; a missing input reports SKIPPED, never zero. FRAMES, both printed: rows are located by the census's own row lat/lon, which for a within-shape pair is the PAIR's position (a 400 m apron chord's row sits far from either endpoint's geometry), so a radius selects rows near the PAIR, not shapes touching the site; seats join by the building's `ref` tag, never by way id or shapeID (both arm-dependent). Promoted 2026-08-12b from the service-corridor lane's `measure_arms.py` on its SECOND use — the named-site table and then the airside attribution. `--welds` (added 2026-08-12c, the corridor-joins round's ruling-4(a) instrument) answers the other question a place can be asked — IS THIS SEAM JOINED? Per site, per arm: the node ids SHARED between the road family (`check_grade._ROAD_FAMILY_ROLES`, read from the census library) and the airside ways, the max |Δalt| two ways carry at a shared node (0.00 is the construction — production values sit on the NODE, so a weld is single-valued; the delta is the torn-weld guard for way-valued rings), the NEAREST UNWELDED approach when nothing is shared (0.999 m at both KCLT mouths, against a 0.5 m weld tolerance), and the `retaining_wall` ways standing at the site with their ids. `--profile` / `--line` (added 2026-08-25, the HECA apron round-2 acceptance) answer the THIRD question a place can be asked — WHAT SHAPE IS THE SURFACE HERE? `--profile` walks every ring of `--profile-roles` (default `apron,graded_strip`) reaching a site and reports its worst consecutive EDGE and its RIPPLE AMPLITUDE, the peak-to-peak inside a 50 m run ALONG THE RING — the same window `apron_drape_read` calls `amp50`, so the two tools spell the ripple one way. `--line NAME=LAT,LON:LAT,LON` orders every emitted vertex in a corridor about an owner-named segment by its station along it, with the step between consecutive stations: the reading an acceptance written as "no unlawful step along the owner line" is stated in, AND the reading that shows a NODELESS VOID, because there an EMPTY STATION LIST IS ITSELF THE FINDING (a region with no emitted vertices contributes no census row however wrong its surface is — the blind spot `nodeless_interiors` counts). Neither prices a law; quote them ARM TO ARM on identical options, never as a verdict. Reach for it whenever an acceptance claim is about a join: **row absence cannot answer it** — a census row exists only between PAIRED geometry, so an unwelded road↔taxiway seam is silent in every census, which is exactly how two 1.0.244 acceptance claims passed over a gap no node could bridge. Twin: `tests/test_corridor_axis_coverage.py`.  **`--behind NAME=LAT,LON:LAT,LON` is the WALL scope** (added 2026-08-29, scorer-v2 round, spec `scorer-v2-class-boundary-spec.md`): the owner states a wall as two coordinates and asks that no airside pavement cross it — `--line` answers what the emitted elevation does ALONG it and `osm_site --line` answers what covers each station ON it, but neither answers the quantitative half, the SQUARE METRES of airside-role pavement sitting on the groundside, which is the number a boundary-cut round moves and therefore the number its acceptance is written in. Per crossing ring it reports the area behind, the node split either side and each side's altitude range — the shape of a wall buried inside one apron (HECA apron 584: 48 nodes at 97.22-104.69 m in front, 95 at 90.77-102.71 m behind). TWO FRAME RULES, both load-bearing: the band is the line's OWN SPAN by `--behind-depth-m` (default 150 m) deep, never a half-plane — unbounded, the far side sweeps in the whole airport and reports 634,371 m² where the local answer is 25,900 (measured at HECA); and the GROUNDSIDE side is decided by the patch — the side carrying less airside pavement — so reversing the two coordinates cannot change the answer and a caller cannot pick it. The closed-ring repeat is dropped before the node split (counting it double reports one extra node on whichever side the ring starts). It prices no law and counts no defects. **THE SEAT JOIN IS NOT FREE (2026-08-31, the buildings round).** `building{N}` is an ORDINAL identifier, so an arm that ADDS or DROPS a pad renumbers every later one and the ref join reports the RENUMBERING as seat motion: measured on the buildings-round HECA arms (pad count 175 -> 176) the ref join said 85 of 174 pads moved, median 2.72 m, max 33.65 m, where the population had barely moved. The tool now DETECTS it — a common ref whose pad centroid is more than `--seat-radius` (15 m) away is named as RENUMBERED, with the advice to re-run — and `--seat-join location` pairs pads by centroid instead (closest pair first, each pad used once; a pad with no partner within the radius is reported as added/dropped, NEVER as a move), which on the same arms reads 28 of 174 moved, median 0.07 m, max 2.32 m. Quote a pad-population round's seat movements under the location join. |

## Tool: obj8_split_report

| `Ortho4XP/tools/obj8_split_report.py` | THE OBJ8 SPLIT, DRY-RUN (spec `object-placement-spec.md` §4 / §6 / §7; owner RULINGS 2026-09-11b) — what a pack's object stage becomes once placements are AGL, objects are cut into their RIGID BODIES and each body carries its own anchor. Reads only a build's own two products — the re-seat plan (`<ICAO>.rebake.json`: the pack read once, its welded parts and the ε-contact graph) and the emitted DESIGN SURFACE (`<ICAO>.graded.json`, whose `building` faces are the object pads and `structure_rim` breaklines the basin walls) — and NEVER opens the pack for writing, never reads the DSF and never builds anything. Prints per placement the bodies, their §6 class, each body's anchor point / reason / authored offset, the files that would be written and the placements KEPT WHOLE with the reason (`one_body`, `anim`, `unparsable`); `--write-into DIR` writes every cut file into a scratch dir and parses each back through `airport/obj8.parse_obj8` (LEMD 13,924 files, OTHH 65,360, all parsing back with the written triangle count, 2026-09-11); and prints §7's CENSUS — the design surface at a body's ANCHOR against the surface under each of its ground-contact FEET, the |Δ| histogram `seat_feet_census.py` prints from a mesh and a seat result, read instead from the plan and the design surface so the two are comparable. A foot or anchor outside every graded face reads `off-surface` and is never guessed at (the DEM governs there and this tool does not open the DEM). `--no-cut` for body counts only, `--filter`, `--json`, `--split-tol` to override `[placement] split_tol_m`. ROUND 2 (owner RULINGS 2026-09-11e, spec §9): the bodies are COARSENED (bodies of one placement whose intended-zero terrain heights agree within `split_tol_m` are one file, the senior body's anchor; an elevated body joins the nearest ground group) and each anchor is the GENERIC one (the footprint point where the design surface equals the body's zero; a body with authored relief beyond its skirt takes its low-side foot and is reported with the residual) — LEMD 302 placements -> 985 files (3.26x), OTHH 954 -> 1,172 (1.23x). §13 (owner RULINGS 2026-09-11r/s): an ELEVATED body — one whose lowest authored vertex, or the `y_zero` of the anchor the generic rule gives it, stands above `[rebake] elevated_base_m` — NEVER has a file of its own; it joins its CARRIER (the same placement's ground body with the largest plan overlap, else the nearest) at its authored offset, and a placement with NO ground body is KEPT WHOLE with reason `footless`. The report prints the two classes by name — `elevated bodies as own files` (BAR 0) and `footless placements kept whole` — because the FEET histogram cannot see this defect: the writer shifts an elevated body so its own lowest vertex lands on the terrain and every foot then reads perfect (LEMD's 218 roofs/decks/tower parts censused green while the sim was broken). Measured on matched pack copies: LEMD own-files 278 -> 0, files 1,099 -> 828, feet > 3 m 1,060 -> 151, worst 34.06 -> 13.75 m; OTHH 1,203 -> 333 files, feet > 3 m 952 -> 6. ROUND 3 (owner RULINGS 2026-09-11f, spec §10): the write half RESTORES every `<obj>.anchor_bak` in the pack before any file is written (counts in the plan's provenance), and a LINE OBJECT authored as one component is cut into SEGMENTS by triangle station (`--line-segment M` overrides `[placement] line_segment_m`; 0 disarms it) — LEMD 897 segments from 271 one-line bodies, 985 -> 1,086 files, census `> 3 m` 30 -> 25; OTHH 1,187 files, `> 3 m` 0. `--write-pack PACK_COPY` runs THE WHOLE WRITE HALF into a pack COPY through `airport/placement_write.apply_plan` (cut files, DSF + backup + provenance, dump-cache refresh, `o4_v2_placement_<ICAO>.json`) and reads the written DSF back; it REFUSES a live X-Plane install. The census also splits the feet over 0.3 m into BURIED (lawful) and FLOATING (the defect the eye reads). `--rows-near LAT,LON[,R]` (lane `v2padcluster`, 2026-09-14) is that SAME projection selected BY PLACE — every body whose ANCHOR is within R metres (default 40) of the coordinate, nearest first, each row carrying its `site_m` — because the owner names a defect by coordinate and the shapeIDs in a report go stale between builds while a coordinate does not; `osm_site --at/--contains` answers the other half of a site question (which emitted FACES cover the point) and is not re-spelled here. Promoted from the scout `v2heca331`'s scratchpad `site.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse): the 14g attribution, then §16g (10)'s per-site bars; its graded-face half was already `osm_site`'s and was NOT copied. Twin: `tests/auto_patch_v2/test_v2objsplit.py::test_rows_near_selects_the_same_rows_BY_PLACE`. `--rows SUBSTR,SUBSTR` (lane `v2canopy4`) prints the PER-BODY rows of the placements named — the body's anchor (point, surface z, `y_zero`, reason), its ground-contact feet, its worst foot signed with |Δ|, and the 0.3 m verdict — for the owner's named sites (`OldTerminal_FSX-LEMD38,-LEMD84,-LEMD60`); it is a PROJECTION of the one census pass, never a second instrument (the bins, feet and worst list are identical with and without it, twinned). §14 (owner RULINGS 2026-09-11u/v, lane `v2carrier`): a FOOTLESS placement is CARRIED — written as a body file at its CARRIER's anchor with the carrier's `y_zero` (the footed body of its UNIT it abuts with the largest contact, else the nearest, else the largest) — a BASIN resource is never split and anchors at a RIM point where the design surface equals its zero (`rims` wired at last), and bodies of one resource that OVERLAP IN PLAN bind whatever the contact graph says. The report prints the four §14 bars (`footless at datum` 0, `footless on ground` 0, `basin bodies split` 0, `spread`) beside §13's, from `airport/placement_carrier.census_v14` — the same call `seat_feet_census --placement-plan` makes over the same plan shape, so the two instruments are one code path. Measured on the app's 1.0.315 LEMD frame: the four footbridge resources at the terminal's zero 616.65 (deck bottom road + 4.4-5.0 m, was ON the road), `Terminal4SAT_pink-LEMD01` at its terminal's 597.43, the basin's three resources one file each on ONE rim vertex (zero spread 7.0 m -> 0.00, parapet +2.99 above the rim), files 828 -> 855, round trip OK, row census `> 3 m` 17. Twin: `tests/auto_patch_v2/test_v2objsplit.py`. §15 (owner RULINGS 2026-09-11ae, lane `v2roofcarrier`): the CARRIER IS WHAT THE BODY STANDS OVER — chosen across the whole UNIT, every resource alike, by largest PLAN OVERLAP beneath, else largest contact, else nearest (§13's same-placement scope and §14's contact-first order are superseded; the pack names its roofs as their own resources, so the walls a roof rides are almost never its own file); the plan-overlap BOND is RE-CUT where a bound group's intended zeros span more than `split_tol_m` (a rigid body is never wider than the terrain it can stand on; BASIN exempt); DUPLICATE ROWS of one resource identical in lon/lat/heading are ONE placement, all of them replaced (`--write-pack` reports `duplicate rows of a SPLIT placement ... surviving after the write`, bar 0); an anchor or foot on no graded face is marked OFF-SHEET and excluded from every comparison and bar; and the report prints §15 (3)'s `stands-over float > 0.5 m` from `airport/placement_carrier.census_v15` — `float = zero - zero_beneath`, the class NEITHER the feet histogram nor §14's bars can see (a carried body has no feet at all), barred at 0 for CARRIED bodies and reported for footed ones. §16 (owner RULINGS 2026-09-11ai, lane `v2skipped`): the report adds the POPULATION census (`placement_carrier.census_population`: `rows on the datum outside the plan` — the resources the SEAT-era thickness gate dropped, which keep the pack's shared-datum row and render where the datum is, bar 0 — beside the lawful skips and the multi-anchor class, reported not barred) and `census_v16`'s `float = zero - ground_under_geometry`: the ground read under the body's OWN parts (`geom_box` / `foot_boxes`, the median of the part-box centres) and never under its carrier's box — `CARRIED bodies whose carrier's zero is over 1 m from the ground under their own geometry` (bar 0; LEMD 39 -> 0 on matched arms) and `files whose own-geometry ground departs over 3 m from the ground at their row` (26, reported). `--admit-skipped PACK_ROOT` puts the thickness-gated resources of a PRE-§16 plan back into the population by reading their rows from the pack's own DSF (one part per component, no contact graph, the member id IS the DSF row index) — what a build's own plan now carries, for replaying a plan written before the switch; LEMD 25 resources / 25 rows, OTHH 99. §16a (owner RULINGS 2026-09-11aj, lane `v2skipped2`): a CARRIED body is cut where its CARRIER is cut (one piece per carrier terrain group its own triangles stand over, each riding that group's zero; never by the ground under itself), the ground check moved to the carrier's OWN feet (`Candidate.ground_off`, `surface(foot) - y_foot` against the body's zero), and `census_v16`'s carried number demoted to INFORMATION — the bar for a carried body is §15 (3)'s `zero - zero_beneath`. The report prints `carried bodies left uncut by the ground` / `cut by their CARRIER into N piece(s)` and, beside the §15 bar, how many of the carried floats stand over a body the law REFUSES as a carrier. LEMD carried float 58 → 4, files 1,591 → 1,328, plan stage 9.9 → 6.3 s; OTHH 7 → 39, 46.4 → 60.2 s (both OTHH bars missed and reported). 11ak (lane `v2skipped3`): the CARRIED bar's `beneath` is the carrier THE LAW CHOSE (`merged_into`, resolved by identity over every row that reads a zero — a carrier written WHOLE names its MEMBER RESOURCE, which is the whole of OTHH's residual), and a body the law REFUSES as a carrier is counted and named as its own class, `carried over a refused body`, with how far its own feet stand off; §16 (2) also cuts BY FOOT (`placement_cut._LineCutter.foot_groups`: the feet grouped by the zero each says the body has, `surface(foot) - y_foot`, each triangle joining the group of the foot nearest it in plan) — the class no ground cut can see, a body whose FEET are authored over metres of relief on terrain that barely moves, which is exactly what §16a (2) refuses. The re-cut line prints the three cuts (terrain / triangle / foot). LEMD carried float 4 → 0, refused carriers 117 → 21 (13 of the residue are rim-anchored BASIN bodies the foot cut is exempt from), files 1,328 → 1,371, plan stage 6.2 → 5.66 s; OTHH carried 42 → 0, refused 55 → 19, files 1,679 → 1,622, plan stage 59 → 31 s (`solid_components` read in one sort instead of a mask per component; `bind_plan_overlaps` swept by the hull's south edge). 11al (lane `v2basincarry`): a BASIN body is EXEMPT from §16a (2)'s ground test — its zero is the RIM (§14 (2)) and its floor feet are authored below it by construction — so it may carry, and the report prints `§16a (2) basin carriers` (how many basins, how many the feet test would have refused) beside the refusal set: LEMD refused carriers 21 → 8, OTHH 19 → 4, carried float 0/0 unchanged. §14a (owner RULINGS 2026-09-11ap item 6, lane `v2basinring`): a BASIN body follows its RING. §24 (1) puts the rim vertices at the APRON's level, so the ring is not level (LEMD's T4 pit 597.68 … 599.52 over 59 nodes) while §14 (2) wrote every basin body at ONE rim point — the owner's "gap between wall and apron", +0.71 / −1.13 m, while the §14 `spread` bar read 0.01 because it measures the pit's bodies against EACH OTHER. `airport/basin_ring.py` (NEW: the whole law — `arcs_of`, `ring_arcs`, `member_kind`, `ring_bar`) cuts the ring into ARCS whose z agrees within `split_tol_m` and cuts each basin body's WALL BAND by them, one piece per arc anchored at that arc's rim point (the interior remainder keeps §14 (2)'s single point: the trench floor is one level); and a member authored AT THE RIM PLANE but standing inside the ring is a FLOOR body that takes §16 (3)'s ground under its own footprint, never the rim, never a carrier. The report prints the RE-DEFINED bar — `§14a spread of a BASIN RING = max |wall base − ring z| over its nodes` (bar ≤ `split_tol_m`), with the nodes on an arc the pit has NO WALL on reported beside it — and the `§14a basin FLOOR members` / `basin bodies cut by the ring's ARCS` counts. It needs the rings WITH their heights (`census_v14(rims=..., arc_cap=..., counts=...)`; `RimRing.z`, and the `basin_arc_wall:<ref>#<k>` counts keys the cut writes are how the bar tells "no wall here" from "the wall is written in the interior piece"). Matched arms on the app's 1.0.319 LEMD frame: the ring bar 1.12 m / 9 nodes over → **0.18 m / 0 over**, `LEMD13__b0` off the rim and onto its own ground, files 1,371 → 1,394, feet > 3 m 518 → 412, floating 9,509 → 9,014; OTHH's 21 basin carriers and its whole foot census byte-identical. §16b (owner RULINGS 2026-09-11ap, lane `v2owncut`): the TERRAIN CUT IS PRIOR AND UNIVERSAL and is read on the body's OWN WRITTEN TRIANGLES — including everything the writer will put in the file (`placement_cut._LineCutter.all_tris`: a placement the plan reads as ONE body is written as the WHOLE object, which is why `green-TEJ3`'s 4-triangle part read 0.22 m of ground while its 2,342 m file stood +16.22 m over it) — so a CARRIED body is divided by the ground under itself first and §16a (1)'s carrier cut runs inside each piece; §9's coarsening additionally requires PLAN CONTIGUITY (`[placement] coarsen_reach_m`, 30 m) and acts WITHIN a terrain group (the pieces carry the ground they stand on, or the very next pass welds them back); each PIECE finds its own carrier, and a FALLBACK candidate (contact / nearest / largest, no plan overlap) is refused unless its zero is within `split_tol_m` of the ground under the piece (`carrier_refused_far_from_carried_ground`). The report prints `census_v16b`'s two bars over the WRITTEN geometry the plan now publishes per body (`geom_pts`, one sample per 10 m cell, thinned to 32 by the farthest-point walk): `carried piece float over its own ground > 0.5 m` and `body wider than its terrain group`, both bar 0, with the BASIN exemptions (§14 (2) / 11al) counted apart and the wide residue split by class. `--coarsen-reach M` overrides the contiguity reach. Measured on the app's 1.0.319 LEMD frame: the owner's item 3 +10.74 → the plate ON the roof beneath it (618.58 vs the group's 618.60), item 5 +16.22 → 620.38 vs 620.27, `Terminal4_48` zero-vs-ground −4.02 → median −0.01, `Taxisigns-SENRG` 38 of 80 bodies over 0.3 m → 12 of 419; files 1,371 → 3,272 at the amended 100 m reach (4,633 at the refuted 30 m), plan stage 5.6 → 10.1 s (bar ≤ 8 s MISSED, reported). §16c (owner RULINGS 2026-09-12b/12d, lane `v2atom`): THE CONNECTED COMPONENT IS THE ATOM — `--torn-seams PACK_ROOT` prints the TORN-SEAM CENSUS over a WRITTEN pack (the plan argument is then the WRITTEN `o4_v2_placement_<ICAO>.json` and `--graded` is not read), and the same census prints automatically after `--write-pack`: sibling files of ONE placement that share an AUTHORED VERTEX (the key `obj8.solid_components` welds on, `round(x, 3)`) are two halves of one connected solid written at two zeros, with the base step per seam, the step histogram, the worst list and the per-class breakdown, and §10's line segments / §14a's basin arcs — the only lawful station cuts — counted APART.  Two bars, both 0: `torn seams outside line/arc pieces` and `single-component resources in >= 2 files`.  The instrument is the scout `v2lemd320`'s `tear.py`, promoted on its second use, and lives in `airport/placement_seams.py` (`census_torn_seams` / `census_torn_seams_lines`, re-exported through `placement_census`).  Measured on the live 1.0.320 LEMD pack it reproduces the owner's four sites exactly (`HANG3` 10 files / 14 seams worst 3.05 m; `green-LEMD50` 7 / 11.12 m; `Bridge2` 8 / 11.72 m; `green-STRT4` 53 files, `__b44` 16.29 m) and the class (2,554 seams, 1,994 over 0.30 m).  On matched replay arms the law takes LEMD 723 -> **0** seams and 128 -> **0** single-component splits (files 3,253 -> 2,804, plan stage 13.5 -> 10.2 s over 3 runs, round trip OK), OTHH 639 -> **1** and 165 -> **1** (files 1,897 -> 1,898). §16c (6) (RULINGS 2026-09-12h, round 2): `--contact-eps M` overrides `[placement] contact_eps_m` (2 mm) — components of ONE resource whose geometry comes within it, or whose parts the rebake plan's ε-contact graph already links, BIND into one rigid body for anchoring (one zero, the senior component's carrier): OTHH's `OTHH_Fuel_02_LOD0_007` carries two components 0.4 mm apart that the millimetre weld key reads as separate.  LEMD files 2,804 -> 2,776, seams stay 0, `Terminal4_48` zero spread 3.58 -> 0.69 m, plan stage 9.6 s (main 13.5). ROUND 3 (RULINGS 2026-09-12j): the entry now runs inside `harness/shared_repo_guard`'s WRITE GUARD and its before/after audit (a round-2 OTHH `--admit-skipped` run had created `Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text` in the SHARED repo with both lane-local cache env vars exported and nothing refused it); every run prints `[guard] shared repo UNCHANGED`.  `--rigid-reach M` overrides `[placement] rigid_reach_m` (2.0) — §16c (8): SOLID components of one resource within it chain into ONE rigid cluster, which is the atom of the BODY as well as of the cut (LINE objects excluded).  `carrier_fill_min` is DELETED from carrier candidacy (§16c (7)); the CLASS exclusion stays.  LEMD: `HANG3` 6 files / 1.37 m -> 2 / 0.45, `green-STRT4` 23 -> 15 files (spread 8.90 -> 3.73), files 2,776 -> 2,121, §16b wide 1,405 -> 967, seams 0, round trip OK; five largest rigid clusters are all SINGLE components (5,157 / 2,890 / 2,514 m — fences and VOR markers, not chained) and `green-TEJ3` stays 9 components / 9 clusters. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. **§17 CRITICAL MOTION IS READ** (owner RULINGS 2026-09-12am (2), lane `v2objmotion`): the graded surface's FACE ROLE under every foot (`airport/placement_boxes.GradedRoles` / `graded_roles_from_doc`, built from the SAME parsed `<ICAO>.graded.json` the sampler and the pads are, senior face by `precedence.toml`'s authority order, a 55 m grid over the faces' boxes) joined to §7's own float there (`airport/placement_motion.census_motion`, re-exported through `placement_census`): a body with a foot on a ROLLED-ON face (`law.tables.rolled_on_roles`) is ON PAVEMENT and every such foot is judged at `[cockpit] motion_step_m` 0.05 m, named with resource, foot coordinate, face role and SIGN. The block prints the count of bodies on pavement, the feet over the threshold, the worst ten, and the breakdowns by resource / face role / body class / anchor rule / size band, plus what the EYE reads at those feet (floating vs buried over `visual_m`) and the MEDIAN-anchor arm. BASIN bodies are counted APART (§14 (2) / 11al: a pit's zero is its rim and its floor feet are authored below it — they were LEMD's whole worst ten). Measured on the 1.0.320 LEMD frame: 493 of 2,153 bodies stand on pavement, 7,124 feet on 399 over 0.05 m; after the §17 anchor rule 6,635 on 407 (OTHH 6,234 → 3,877 on 113 → 103). RULINGS 2026-09-12ap (lane `v2pavefeet`): `--motion-rows OUT.json` writes §17's PER-BODY projection — one row per written body with its anchor, class, anchor reason and every ground-contact foot (lat/lon, authored y, surface z, face role, on-pavement, float) — the rows `census_motion` itself reads, never a second census (the scout's scratchpad projection, promoted on its second use). (E) THE SAMPLER HONOURS GRADED HOLES: a Delaunay over the emitted VERTICES spans a hole ring with triangles reaching from an apron vertex to a trench vertex, and LEMD read **592.22 m at a point whose ROLE is apron** six metres outside the hole — 12ap's two worst pavement feet (`LEMDblast__b1` +7.18, `Terminal4sBlue-STRT4__b1` −5.08) were that fabricated ramp, and the anchor correction is 6.91 m. A simplex CROSSING a hole ring with a step over `split_tol_m` is struck and a point inside one reads the nearest vertex of that simplex ON ITS OWN SIDE of the ring; measured narrowings: "centroid on no face" struck 8,689 of 47,287 simplices and cost 421 files / 435 off-sheet bodies, and a strike with no side-aware read cost 160. (B) §17 is judged at the GROUND-CONTACT feet — the in-band feet within `split_tol_m` of the lowest (`placement_motion.ground_contact_feet`); `contact_band_m` is shared law and unchanged, BOTH sets are sampled and the wider reading prints beside the judged one so the report states its own attribution. (A) `bind_ground_m` (`[cockpit] visual_m`) bounds §16c (7): a FOOTED body of ANOTHER member keeps the cluster only while its own zero is within it of the senior's, else it keeps its own anchor and is counted — the report prints `bound refused for ground N` with the worst refused disagreement and the widest RETAINED cluster zero-plane span. Matched arms, LEMD main → branch: CRITICAL MOTION 6,640 → 5,400 feet on 407 → 356 bodies, over 0.5 m FLOATING 663 → 128 and BURIED 1,109 → 808 (of which (B) alone 581 → 128 / 816 → 808), worst pavement foot +7.18 → +2.41 m, 74 binds refused (worst 2.38 m), files 2,107 → 2,149, seams 0/0, round trip OK, plan stage 10.19 → 10.03 s; OTHH 3,891 → 2,822 feet on 103 → 74, floating 332 → 12, §14 footless at datum 5 → 4, files 1,252 → 1,269, plan stage 60.8 → 61.4 s (the ≤ 60 s bar missed on BOTH arms). §16b's carried-piece float and wide counts move the WRONG way at both airports (LEMD 111 → 119 / 967 → 983, OTHH 126 → 135 / 75 → 78) and are named. §16d (owner RULINGS 2026-09-13h, lane `v2unboxed`): THE PLAN BOXES WHAT THE WRITER WRITES — a WRITTEN-FRAME bar beside the torn seams, `§16d bodies with written geometry > 1 m outside their geom_box` (`airport/placement_seams.census_outside_box`, printed after `--write-pack` and by `--torn-seams`, bar 0): `geom_box` was the hull of the ADMITTED PARTS while the writer emitted the source object's triangles regardless, so a component no part named (the FS2XPlane origin plate, an exporter's ground paint, a roof plate over the next hangar) rode a zero the body chose elsewhere and NO instrument read it — LEMD 1.0.325 live pack 378 of 2,109 bodies, 8 over a kilometre. Every connected component the writer will emit — draped ones included — is now PLACED: within `coarsen_reach_m` of a ground group's part hull it joins that group and `geom_box` grows to the hull of what the file will contain; beyond it, it is a FOOTLESS BODY §15's search places, or §16 (3)'s own ground (`--coarsen-reach 0` disarms the reach and the component joins the nearest body, the pre-§16d reading). The nearest-footed fallback is CAPPED at the same reach (`carrier_refused_nearest_beyond_reach`), and the COCKPIT block names the worst row by the centre of the BODY'S OWN written geometry, never the placement row (a shared-datum pack puts 96.5 % of its bodies on two points). `plan stage: N.NN s` is printed after the split — the number a round's budget is quoted in, timed exactly where the shipped engine's own `build_splits` call is, without the graded parse or the census. Matched dry arms on the 1.0.325 LEMD frame (the app's own arm reads a MESH sampler where the tool reads a Delaunay over the graded vertices — the two disagree on every surface-driven refusal and the bars are read dry-to-dry): outside-box 390 → **0**, nearest-footed over 100 m 29 → **0**, the four shadow plates +15.94/+15.73/+5.77/+1.72 → **−5.00 on their own ground**, `Cargo-TEJ1` on `NEWCO__b9` roof base 604.95 (bar 0.3 of 605.04), seams 0/0, §15 carried float 0/0, round trip OK, files 2,141 → 2,279, LEMD plan stage 13.6 → 17.8 s and OTHH ≈83 → 86.1 s (both bars missed on BOTH arms, named). It also fixed a latent WRITER defect: the cut file was named by its index in the LIVE body list while the DSF row is written on the plan's `body_id` name, so a body the cut left with no triangle shifted every later body's file one name down (`OldTerminal_FSX-DCNEUN`'s `__b0` row held `b1`'s object). §16d (4)-(6) (owner RULINGS 2026-09-13m, same lane, second frame KCLT 1.0.324): a CARRIED body's components group BY CARRIER — each ATOM (§16c (1)'s, so a rigid cluster is never divided) asks its own carrier question BEFORE the search, counted as `carried bodies cut by ATOM`, where §16a (1)'s after-the-fact cut could only divide the answer the whole body got (KCLT 5,295 carried bodies left uncut against 3 cut; a native pack's master roof model spans 1,774 m); §16c (7)'s 0.5 m ground bound is MEMBER-AGNOSTIC (12ap tested `member != top.member`, and a native pack's one-model-per-material member spans the airport: KCLT's `005_ALB__b9` sank 5.04 m into its pad on a same-member bind to an apron body 500 m away); and a FOOTED body whose ground contacts lie mostly inside one emitted `building` pad reads only the contacts ON it (`anchor_rule.pad_majority`; the anchor reason then says `on pad <ref>`). Matched dry arms at KCLT: `005_ALB__b9` -5.85 -> **+0.02** against its pad, widest retained cluster zero span 5.69 -> **0.64 m**, 473 carried bodies divided by atom, 61 bodies anchored on their pad, `building80`'s on-pad zero spread 1.03 m (the pad's own relief 1.19), §16d outside-box **0**, §15 carried float **0**, round trip OK 477/477, one new torn seam (+0.16 m, one shared vertex, named), files 473 -> 477, plan stage 8.65 -> 8.3-8.5 s. It also exposed a defect the atom cut made visible: a target group holding BOTH a cut piece and an untouched raw was read for its `tris` alone, leaving 990-3,280 triangles per placement claimed by no body (9 of KCLT's 103) for `obj8_split` to hand to the nearest one — the audit reads 0 of 103 after. **COST: plan stage LEMD 17.8 -> 25-46 s and OTHH 86 -> 136 s** (KCLT flat) — the per-atom carrier search, narrowed by a `coarsen_reach_m` span gate, a 64-atom cap, per-atom pids and a set-intersection contact count, and still needing the owner's approval and a Fable-5 review before it ships. **§16g (5)'s PER-PLACEMENT ROW CENSUS, DRY (`--dsf-dump DUMP.text`, owner RULINGS 2026-09-14bo, lane `v2leafframe`).** The dry path reads no DSF by design; given an EXISTING DSFTool text dump it also prints the `OBJECT_MSL` seats the writer would emit, from the SAME `footprint_unit.msl_seats_for_dump` call `placement_write.build_plan` makes — the per-row base (`msl_base_unit_pad` / `msl_base_own_feet` / `msl_base_deck` / `msl_left_to_the_drape` / `msl_off_sheet_left_draped`), the multi-anchor census beside it, and `|elevation - the design surface at the row's own feet|` over 0.5 m with the worst named. PASS THE PRISTINE DUMP (`<dsf>.anchor_bak...text`, `dsf_write.pristine_dsf_path`): a dump of an ALREADY-WRITTEN pack reads the app's own absolute elevations back as authored offsets and reported 1,055 rows 22 m off their feet that do not exist. Measured at LEMD on the pristine dump: `OBJECT_MSL` rows **1,481 -> 0** (1,466 left to the drape, 196 standing on their unit's pad at offset 0, 5 off-sheet) — every LEMD multi-anchor row is a plain `OBJECT` with no authored offset, so the drape at its own feet IS the law's answer. Nothing is written and no DSF is decoded. Twin: `tests/auto_patch_v2/test_v2leafframe.py`. |

## Tool: mesh_region_tris

| `Ortho4XP/tools/mesh_region_tris.py` | Built-mesh triangle count inside the airport bbox — the number load time tracks — and, with `--area-bands`, the triangle SIZE distribution beside it: the near-degenerate SLIVER class (< 0.1 m^2, which carries no visible ground and costs load time outright), the sub-texel classes, and the visible class, each with its ground cover, in and out of the box. The band edges default to `0.1,1,TEXEL` and the literal `TEXEL` resolves to one orthophoto texel^2 at the bbox's mid latitude (ZL16 = 2.0662 m / 4.269 m^2 at HECA), because a triangle finer than a texel cannot be resolved by the imagery at all — that is the honest floor for "invisible geometry". `--json` stamps the bbox, the ZL and the edges beside the counts. Absorbed 2026-08-07 from `tmp/density_audit/meshtexel.py` on its second use (the sliver spec's phase-B interventional read) — promote-on-reuse, the near-fit extended rather than forked. **A/B WARNING, stated by the tool itself:** derive the bbox with `--bbox`, never `--patch-osm` — two arms' patches give two different boxes, which is two populations. `--aspect` adds the SHAPE half beside the size half: the ratio `longest edge / (2*sqrt(3) * inradius)` (1.0 = equilateral, rising without bound as a triangle degenerates) as p50/p90/p99/max over the in-bbox triangles, plus the NEEDLE count at `--aspect-flag` (default 20.0, a REPORTING threshold and an assumption, never a law — two runs quoted at two thresholds are not comparable). Reach for it whenever the question is "did this change mint a LONG-TRIANGLE artifact class", which the area bands structurally cannot answer: a 40 m x 0.5 m needle and a 4.5 m equilateral have the same area and land in the same band. Added 2026-08-08 (fabricA, THE FABRIC MODEL Phase A) because that round's acceptance is stated in exactly those terms; measured HECA in-bbox control p50 2.04 / p99 23.35 / max 975.53, sparse arm 2.02 / 22.76 / 975.53. Twin: `tests/test_mesh_region_tris.py` (a hand-built MEDIT mesh of deliberate areas; the published texel constants; every band-spec refusal; the aspect normalisation proven on a known equilateral and a known needle, and proven to SEPARATE two same-area triangles the bands cannot). **`--interp-alt-audit` (2026-08-28, the CYXY INTERP_ALT round) answers "who owns this mesh's altitudes" in the THREE artifacts it actually lives in, from the one MEDIT parse this tool already owns** (`--inputs PREFIX` for the build's `.node`/`.poly`, tile origin parsed from the mesh name or `--tile LAT LON`): the SEAL — is every INTERP_ALT seed in a BOUNDED face of the arrangement of the INTERP_ALT-marked segments, which is exactly Triangle4XP's own containment condition (regionplague crosses any segment sharing no bit with the flood); the PLAGUE — did every attr-8 triangle of the built mesh land inside that same envelope, i.e. did the marks survive the CDT; and the DOMAIN — how far does the CONNECTED attr==8 sub-mesh that `O4_Mesh_Utils` harmonic-extends the patch ring altitudes over (R18-1b) reach beyond the patch coverage, component by component, with each component's patch-valued anchor count and span. Reach for it whenever a mesh contradicts its own `.alt`: reading only one of the three is how +60-136 was first attributed to a plague leak that this audit refuted in 1 s — seal 0 of 578 seeds unsealed, plague 0 of 22,923 triangles outside the envelope, domain ONE 10.2 km component carrying all 6,677 patch-valued vertices against a 1.94 km^2 patch coverage (the town's levelled road network, welded to the airport wherever a road touches it). `--json` stamps every count. | **`--water-audit` (2026-09-09, lane `v2water`, owner RULINGS 09m) answers "is the water flat, and at its datum" from the mesh alone**: over every triangle carrying a water bit (WATER|SEA|SEA_EQUIV — the mask is twin-asserted against `O4_Vector_Utils.Vector_Map.dico_attributes`, never a second spelling), how many water VERTICES stand at 0.000 and how many do not with the commonest values named, how many water TRIANGLES span more than `--water-step-flag` metres corner to corner (a one-triangle step in open water is a sawtooth, not terrain), and the ATTRIBUTE HISTOGRAM beside them — which is the attribution: `SEA|INTERP_ALT` (10) means a patch seed reached that water and exempted it from sea levelling, bare `SEA` (2) means it did not. `--near LAT LON RADIUS_M` repeats the read at a site. Measured at OTHH on the owner's 1.0.297 build: 2,180 of 2,197 water triangles attr 10, every water vertex exactly 0.000 (699) or 3.962 (782), 1,692 stepped. Extended here rather than forked: the MEDIT parse, the tile-origin resolution and the JSON stamping are this tool's already. Twin: `tests/test_mesh_water_audit.py` (a hand-built mesh of one flat sea triangle, one 3.962 m stepped one, one inland body and one attr-8 land triangle that must not be counted). **`--hairline-audit` (2026-09-13, lane `v2hairline`, spec §39 (3), owner RULINGS 2026-09-13an/13bk/13bt/13bu) answers "can Triangle4XP even build this `.poly`" BEFORE it is run**, ANGLE-FREE, in the FOUR topologies the four measured sightings hid in: `node_pairs` (two distinct constrained nodes inside `--hairline-spacing`, 0.5 m = `emit.identity.min_distinct_spacing_m`), `short_segments` (a constrained segment shorter than it — KCLT's 2.7913 mm water sliver, 481,602 triangles under 0.1 m^2), `bent_chords` (VMMC's degenerate triple `a->m->b` beside the chord `a->b`, which SHARES both endpoints and is invisible to every non-adjacent pair test) and `vertex_edges` (LEMD's ring vertex 0.0595 mm from a water edge, and SPLP's bank foot 23.7 mm from the tile border). There is NO parallel gate: KCLT's two cascades stand at 29.08 and 89.20 deg. Each row carries its gap, markers, coordinates and SLENDERNESS (the neighbouring feature's length over the gap = the Steiner cascade Triangle must build). The UNMESHABLE subset the mesh pre-flight refuses on is anything under `--hairline-degenerate` (0.010 m, KCLT 13bu's own bar), over `--hairline-slenderness` (1e4), or beside the OUTER boundary under `--hairline-boundary-gap` (0.1 m; `-Y` forbids Steiner points there, so the wedge can only be relieved by splitting the OTHER segment) — all three ASSUMPTIONS and REPORTING thresholds, never laws. Reach for it whenever a tile's triangle count jumps, a texture tears at a seam, or X-Plane will not load a tile. Measured on the shipped 1.0.327 tiles: LEMD `Data+40-004.poly` 57 / 957 / 157 / 2,562 with 118 unmeshable (the bank foot 0.0595–0.2649 mm from the retention basins' water edges, slenderness 417,901 down to 95,714); VMMC 321 / 2,271 / **369** / 7,448 (the bent-chord count 13bt reports to the row); KCLT 102 / **2,246** / 293 / 5,794, 28 short segments under 10 mm and 6 under 1 mm (13bu's own numbers). Takes the `.poly`/`.node` alone (`--inputs PREFIX`, no `--mesh`), so it runs before a build finishes; omit `--tile` on a negative-longitude tile (argparse cannot take `-81`) and the origin is parsed from the file name. THE ONE IMPLEMENTATION is the engine's own (`O4_Mesh_Utils.hairline_findings` / `hairline_refusals`, which `hairline_preflight` calls before every Triangle4XP invocation; `O4_HAIRLINE_PREFLIGHT=report|off` downgrades or skips the refusal): promoted from the scouts' `nearpar.py` and `bentchord.py` on their second use, never forked, so the instrument and the refusal can never disagree. Twin: `tests/test_mesh_hairline_preflight.py` (all four sightings at their own numbers, the 0.30 m neighbouring ring and the 0.444 m land segment that must NOT be refused, the shared-vertex chain that is not a pair, and every knob). **`--z-xref` (2026-09-13, lane `v2hairline`, owner RULINGS 2026-09-13cp) answers "who owns this node's altitude" between the vector map and the built mesh**: every `.node` z against the altitude the `.mesh` carries at the SAME coordinate, counted per `.poly` ATTRIBUTE with the worst offender named, over `--z-flag` (2 m); needs `--mesh`, `--inputs` (or a `.mesh` its inputs sit beside) and a `--bbox`. Reach for it whenever a pass makes two ways SHARE a node — sharing a node is sharing an altitude, and picking the wrong one silently re-levels the crossed chain. Promoted from scout `v2lemd329`'s `xref.py` on its second use (13cp's attribution, then this lane's before/after), extended not forked: the disc became this tool's own `--bbox`, and the MEDIT parse, the tile-origin resolution and the JSON stamping were already here. Measured at LEMD +40-004: attr 1 (WATER) 56,830 matched, 10,337 over 2 m before the 13cp z carry and 10,338 after — which is how that carry's premise was REFUTED (the branch fires twice on the whole tile, so the water z error is a different, still unattributed mechanism). **`--patch-edge-step` (2026-09-13, lane `v2bankfoot`, owner request via the round's coordinator — the bank_foot OMIT arm) is the other half of `--z-xref`**: for every `PATCH_RING_MARKER` mesh vertex, the altitude STEP to a triangulation neighbour that is NOT on a ring and stands OUTSIDE the patch coverage (median / p95 / max with its coordinate, counts over 1 m and 3 m). §8.4's measured defect is that Ortho4XP's mesh does not blend from the patch boundary to the DEM — it drapes the raw DEM right outside the constrained ring, so a ring standing 16.6 m off the terrain builds a 16.8 m cliff ONE TRIANGLE wide — and the BANK is the owner's answer to it. So `--z-xref` says whether the ribbons carry their own altitude and THIS says whether the patch edge is a bank or a wall; an arm that omits the bank_foot class altogether is judged on both. Same three artifacts this tool already parses (`--inputs PREFIX` + `--mesh`), writes nothing. Twin: `tests/test_mesh_region_tris.py` (a hand-built ring at 600 m beside an outside vertex at 588 = a 12 m step over two pairs, the graded edge that reads 0, and the `.poly` with no ring segment that says so instead of printing a number). |

## Registered frames: VHHH

VHHH  capture  base dc5517c0c156603c7b3339b2a9d80b21ccbc0caa lane v2zgszunion      2026-09-13T16:07:22  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/vhhh.35993.log  — shapely union_all tracer log; VHHH build aborted at 10 GB RSS inside planar/build build_basins -> obj8.at_grade_geometry; 311 unions / 270.5 s in 11 min
VHHH  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /tmp/harness/VHHH_20260913T170144.osm  — VHHH harness build on claude/v2gradecache (--no-ledger, /usr/bin/time -l): rc=0 wall 3580.5 s; at-grade read 2626 s -> 11.88 s / 811 unions over 6752 placements; wall_s.planar STILL 2845 s (the remaining ~2625 s is NOT the at-grade read); peak RSS 77.8 GB (load/partition); report /tmp/harness/VHHH_20260913T170144.v2/VHHH.report.json
VHHH  patch    base a4a953f0   lane v2gradecache     2026-09-13T19:55:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/armB_VHHH/structures.json  — VHHH planar --stage structures A/B on ONE instrument/machine/corpus (scratchpad/prof tree on the lane-local mod-cache overlay): armA f4e9b436 (at-grade memo only) 2418.1 s / 62.5 GB peak RSS -> armB a4a953f0 (+ _rim_open STRtree) 1217.8 s / 73.4 GB; structures.json BYTE-IDENTICAL bar wall_s (70 basins, 43 refusals). cProfile of armA: build_basins 2016 s of 2360 s, _rim_open 1195.9 s over 96 calls (549,207 point-to-MULTILINESTRING distances), at_grade_geometry 106.5 s. Residual after armB ~1133 s = the ring loops other unions (~714 s), door_wells 117 s, wall_corridors 66 s.
VHHH  patch    base 51c4666b   lane v2gradecache     2026-09-13T22:20:49  /tmp/harness/VHHH_20260913T220441.osm  — VHHH closing harness build round 2 (--no-ledger, /usr/bin/time -l, machine clear): rc=0 wall 3580.5 -> 921.1 s; wall_s.planar 2845.2 -> 483.4 s; peak RSS 77.8 -> 8.62 GB; shared repo UNCHANGED; 96 regions / 70 basins / 43 refusals unchanged. at-grade read 12.9 s / 811 unions / 6752 placements; basin unions cover 10.4s/96, own_cover 0.4, wits.plate 0.2, rest 0.0 (the rim_geom union is GONE — was 979.5 s / 96). Residual inside planar: _rim_open ~150 s, door_wells read_s 123.8, wall_corridors read_s 53.1, sunken_roads 24.7, read_placed_objects ~61 — per-candidate geometry work, not repeated work. Report /tmp/harness/VHHH_20260913T220441.v2/VHHH.report.json
VHHH  mesh     base 333ee02e   lane v2bankfoot       2026-09-14T08:00:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2bankfoot/vhhh/Data+22+113.mesh  — VHHH +22+113 UNBLOCKED: seed clearance = the encoding quantum (0.5 m, pole-of-inaccessibility fallback). seal all 4030 enclosed (was 1 of 4095 unsealed, build died); face seeds 4094->4022, 132 degenerate skipped; rc 0, guard UNCHANGED. z-xref vs the owner's shipped 1.0.330 tile: attr8 worst -29.79->+9.87 m, attr9 203->29, attr10 138->45, attr15 worst -7.320 unchanged (09ad b), WATER attr1/2 unmoved
VHHH  mesh     base 345cf11b   lane v2bankfoot       2026-09-14T09:59:05  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2bankfoot/vhhh_r4d/Data+22+113.mesh  — ROUND 4: narrow is not degenerate — only the 10 mm hairline floor drops a face. seal all 4057 enclosed, skipped 132->4 (survivors 4.9/9.4/9.7 mm inradius at 22.29193,113.8971), face seeds 4022->4049, rc 0, guard UNCHANGED. TUNNELS UNCHANGED vs the owner's shipped 1.0.332: 62/62 ramps + 72/72 trenches 100% attr-8, same 4 of 72 trenches over 0.5 m — the seed floor is REFUTED as the tunnel regression's cause
VHHH  patch    base 6196113c   lane v2gradecache     2026-09-14T10:28:08  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/r3B_VHHH/structures.json  — VHHH round 3 matched arms, ONE tree/machine/corpus, planar --stage structures on the lane-local overlay: armA main 4c6f467c 400.7 s / 6.78 GB -> armB 306.7 s / 6.56 GB (-94.0 s, -23%). structures.json BYTE-IDENTICAL on EVERY key (71 basins, basin_refused, tunnels, corridors, door_wells, sunken_roads, plates, wall_corridors, underpasses, cells_cut); LEMD likewise. The fix: shapely.is_empty/is_valid/area/get_type_id over the arrays instead of per-object property reads, in basins._rim_index and obj8_clip._union_rings/_polygon_parts. REFUTED third site: vectorising wall_geometry._plan_segments_indexed measured 334.1 s vs 306.7 s (worse) — reverted, _bands_of's residual is NOT this class.
VHHH  patch    base 949378fd   lane v2roles          2026-09-14T10:58:55  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/vhhh/build/v2roles_VHHH.osm  — §40 (4) closing VHHH build, claude/v2roles e69c0d31: rc 0, 795.8 s, ways 1330, nodes 24758, solve OPTIMAL, body_sha ad7b49746745, guard shared repo UNCHANGED (1 EXTERNAL-CANDIDATE delta named: an OTHH mod-cache file outside this build's input set, write_guard_blocked empty — another lane's write; ledger store declined for that reason only). The owner's tunnel at 22.30368,113.92917 is BACK: tunnel_ramp way -10488 n=62 alt 2.22-7.31 m, tunnel_wall rim -11230 n=69, no pit. structures tunnels 28 / cells cut 40 / refused 154. graded_strip 2,439,489 (old arm VHHH_20260913T220441, pre-§40) -> 2,390,657 m2 = -2.00 percent, inside the 5 percent bar; runway faces 6 -> 35, runway area 780,628 -> 1,273,536 m2 (the shoulders are runway body)
VHHH  graded   base 949378fd   lane v2roles          2026-09-14T10:58:56  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/vhhh/lane/structures.json  — VHHH planar --stage structures LANE arm (§40 (4)); its MATCHED BASE arm on main 949378fd is beside it at ../base/structures.json. tunnels 27 -> 28 (tunnel:-3365+-532@0 admitted), basins 71 -> 70 (basin:5 gone: 3,476 m2 pit, 7.315 m rim, tunnel/tunnel1_done.obj, at 22.30367635,113.92917437), tunnel_refused 45 -> 44, basin_refused 42 -> 43, cells_cut 39 -> 40
VHHH  rebake   base 8e92e26a   lane v2othhfix        2026-09-14T11:37:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix/a4_VHHH/structures.json  — VHHH dry --stage structures on the branch (§24 (7)/(8)): 71 basins / 42 refusals, floor/region 0.225 (armB base a4a953f0) -> 0.564; basin:5's 2,761 m2 ramp corridor re-noded 9 -> 205 ring vertices at ramp_station_m 2.0 m
VHHH  patch    base 106459fa   lane v2objcut         2026-09-15T09:44:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/r4_VHHH/structures.json/structures.json  — §33 (6) LANE arm: dry 'planar --stage structures' on claude/v2objcut; its MATCHED BASE arm on main 106459fa is /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/b4_VHHH/structures.json/structures.json. corridors 0 -> 5 object cuts with the AUTHORED floors (TUNNEL2_DONE 0.78 / tunnel1 0.37 / tunnel3 -1.63 / tunnel4 -1.69 / tunnel5 1.30 vs the bar 0.77/0.36/-1.63/-1.69/1.31); wall corridors 0 -> 0 (the affordance stands, §33 (6) A refuted); basins 70 -> 70 population IDENTICAL, 10 placements claimed; tunnels 28 -> 23. tunnel5 (the owner's site) and TUNNEL2 refused DOWNSTREAM by planar/structures.py's ring builder: a hairpin corridor's offset ring self-intersects.
VHHH  patch    base 106459fa   lane v2objcut         2026-09-15T10:44:12  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/c7_VHHH/structures.json/structures.json  — r2 §33 (6) lane arm at claude/v2objcut 3b3259dd: corridors 0->5 (floors 0.78/0.37/-1.63/-1.69/1.30), wall corridors 0->0, basins 70->71 (one extra 0.2 m2 JETWAY FRAME pit; population identical by (objects, area)), tunnels 28->24
VHHH  patch    base f912ba81   lane v2objcut         2026-09-15T12:02:00  /tmp/harness/v2objcutVHHHr3.osm  — r3 CLOSING VHHH BUILD (claude/v2objcut edf1e3c0): rc 0, 672.4 s, ways 1460, nodes 25910, status optimal, body_sha 38e3a2678b5c, v2-verify rows 1970. object corridors 5 (object cuts 5 B, basin placements claimed 10), tunnels 26, cells cut 17. AFTER on the five shells: ring vertices outside the wall line 85/19/111/27/26 -> 0/0/4/0/0 (worst 75.8-86.1 m -> 0.90 m), emitted floor vs authored |de| 0.90/1.85/1.44/3.85/3.91 -> 0.00/0.00/0.00/0.01/0.00 m. object_cut_offset 4 rows (worst 0.897, all TUNNEL2_DONE), object_cut_depth 0. RUN FLAGGED CONTAMINATED: 2 unauthorised Airport_mod_cache paths (a fresh +22+113 DSFTool dump) - artifact ledger NOT stored.
VHHH  patch    base f912ba81   lane v2vhhhctl        2026-09-15T13:02:22  /tmp/harness/VHHH_20260915T120714.osm  — MATCHED CONTROL for the v2objcut r3 delta: harness build_airport.py VHHH at main f912ba81 (own ritual worktree v2vhhhctlbase, lane-local DSF/mod-cache redirects). rc 0, wall 1108.6 s, ways 1405, nodes 25328, optimal, body_sha 8c8ef471eaab, v2-verify rows 160. 'shared repo UNCHANGED by this build'; artifact ledger STORED bfbfeb3e3a64 (44.1 MB) - a later --base-arm at this tree/env/corpus serves it. Census law-true 1531, ADJUDICATED 121, out-of-scope 1410. object_cuts 3 of 5 (tunnel1/3/4); TUNNEL2_DONE + tunnel5_done still refused by the ring builder. No --tile.
VHHH  patch    base 118d2c40   lane v2vhhhctl        2026-09-15T13:02:32  /tmp/harness/VHHH_20260915T122604.osm  — ARM of the matched pair: harness build_airport.py VHHH at merged main 118d2c40 (v2objcut r3 d94db789 is the ONLY source merge over the control f912ba81). rc 0, wall 1182.9 s, ways 1460, nodes 25910, optimal, body_sha 38e3a2678b5c = v2objcut r3's closing build EXACTLY; v2-verify rows 1970. 'shared repo UNCHANGED by this build' - the r3 mod-cache contamination did NOT recur; artifact ledger STORED fed2cfb7b219 (45.6 MB). Census law-true 4845 (control 1531), ADJUDICATED 1472 (control 121). object_cuts 5 of 5: TUNNEL2_DONE (1109.9 m, 203-vertex ring) and tunnel5_done (413.2 m, the owner's site) newly built. 3084 of 3558 NEW census rows stand within 500 m of TUNNEL2_DONE. No --tile.

## Registered frames: OTHH

OTHH  rebake   base 05050624   lane v2unboxed        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/unboxed  — KCLT 1.0.324 / LEMD 1.0.325 / OTHH 1.0.326 rebake frames + dry arms
OTHH  capture  base 7949757a   lane v2othh327        2026-09-13T16:30:07  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othh327/OTHH.pkl  — v2_solve_replay --capture OTHH on main 7949757a (402 s); solved arms beside it: OTHH.solved.pkl (base) and OTHH.nofeet.pkl (--drop-generator foot_rows)
OTHH  patch    base a0f65165   lane v2cutfeet        2026-09-13T17:37:22  /tmp/harness/OTHH_20260913T171324.osm  — closing build of lane v2cutfeet (§11b (7) cut foot verdicts), rc 0, 968.0 s, ways 1097, body_sha 0ff85d1a7bff, artifact ledger 86493fdab68b; matched replay arms on the v2othh327 capture live in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cutfeet/out (OTHH.base.pkl / OTHH.cut.pkl / othh.base.json / othh.cut.json / *.log), KCLT arms beside them
OTHH  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/fin_OTHH/structures.json  — OTHH planar --stage structures on claude/v2gradecache vs the 0c86fe2c base arm in scratchpad/base_OTHH: basins array BYTE-IDENTICAL; only one sunken_refused message rounds 50%->49% roofed, same verdict
OTHH  capture  base cf87c942   lane v2unionsweep     2026-09-14T07:40:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2unionsweep/othh.lane.json  — DRY replay dump (NOT a capture: the plan_clusters reading OFF the registered OTHH capture 7949757a, via scratchpad/v2unionsweep/cluster_arm.py). MATCHED PAIR: othh.base.json = main cf87c942 (666.07 s, machine contended; scout v2partcost read 299.8 s uncontended at 628cca80), othh.lane.json = claude/v2unionsweep 99cf52ba (16.60 s). 44 clusters both arms, all 44 area_m2 BIT-IDENTICAL (struct.pack '<d' hex).
OTHH  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/base/OTHH_base.osm/v2cost2base.osm  — BASE ARM of the v2cost2 matched triple (own ritual worktree v2cost2base at main 4c6f467c): rc 0, harness wall 631.7 s, staged total 592.86, body_sha 72d4ec0e08f2, ways 1000 nodes 25387, guard UNCHANGED. wall_s load 7.63 / partition 313.57 / classify 7.87 / planar 67.13 / constraints 94.43 / solve 23.34 / emit 9.00 / rebake_plan 5.49 / verify 63.50 (the second Patch.of + road_law_caps + apron_over_preference ran OUTSIDE this clock). obj8_split_report on its own products: plan stage 223.13 s
OTHH  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_cold.osm/v2cost2cold.osm  — LANE COLD arm (claude/v2cost2 3eeccf13, partition cache EMPTY -> WROTE 1.05 GB): rc 0, wall 615.1 s, body_sha 72d4ec0e08f2 — BYTE-IDENTICAL to the base arm (patch, OTHH.rebake.json and OTHH.graded.json all sha-equal). wall_s partition 288.87 (313.57 base: the per-axis contact screens), constraints 85.32 (94.43), verify 121.85 (63.50 + the 45.6 s that used to run unclocked), total 612.71, unclocked 1.24
OTHH  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_warm.osm/v2cost2warm.osm  — LANE WARM arm (claude/v2cost2 12b29e6c, partition cache HIT): rc 0, harness wall 328.1 s vs the base arm's 631.7; body_sha 72d4ec0e08f2 BYTE-IDENTICAL, guard shared repo UNCHANGED. wall_s partition 313.57 -> 8.40, classify 7.87 -> 75.79 (the ResourceCache is cold on a hit, so the pack parse moves here: partition+classify 321.5 -> 84.2), constraints 94.43 -> 73.48, verify 63.50+45.6-unclocked -> 62.43, total 592.86 -> 325.17. verify.wall_s per family published (within_shape 50.94, taxi_box 8.72)
OTHH  patch    base 55cf0fe3   lane v2cost2          2026-09-14T11:31:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_r2c2.osm/v2c2r2c2.osm  — ROUND 2 COLD arm (claude/v2cost2 7bc09ea7, RULINGS 14v; cache EMPTY -> WROTE 31.3 MB, was 1,047 MB): rc 0, body_sha 72d4ec0e08f2, patch/rebake/graded sha-equal to the 4c6f467c base arm, guard UNCHANGED. wall_s partition 283.70 classify 8.90 planar 63.17 constraints 80.17 verify 67.25 total 547.67 unclocked 1.28
OTHH  patch    base 55cf0fe3   lane v2cost2          2026-09-14T11:31:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_r2w2.osm/v2c2r2w2.osm  — ROUND 2 WARM arm (claude/v2cost2 7bc09ea7): cache HIT, 2,259 resource readings restored; rc 0 harness wall 298.6 s (base arm 631.7), body_sha 72d4ec0e08f2 BYTE-IDENTICAL (patch, rebake plan and graded surface), guard UNCHANGED. wall_s partition 8.07 classify 10.21 (partition+classify 321.5 -> 18.3 on the base arm's frame; bar <= 40 MET) planar 84.43 (55 cold: the pack parse the cache no longer pre-pays lands here) constraints 78.67 verify 69.06 total 296.22 unclocked 1.28
OTHH  patch    base 8e92e26a   lane v2othhfix        2026-09-14T11:37:09  /tmp/harness/v2othhfix2.osm  — closing OTHH patch build of lane v2othhfix on claude/v2othhfix (§24 (7)/(8), §34 (7)/(8) as amended by 14u): rc 0, 614.3 s, ways 1012, nodes 23724, body_sha 44208e4fdd65, artifact ledger 20d817adcf38, shared repo UNCHANGED; report /tmp/harness/v2othhfix2.v2/OTHH.report.json; census A/B vs the owner's 1.0.332 patch ADJUDICATED 1764 -> 1766 (+2)
OTHH  rebake   base 908895cd   lane v2othhfix        2026-09-14T11:37:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix  — dry planar --stage structures arms on the lane-local overlay: base_OTHH (main 908895cd), a5_OTHH (the branch, final law); bars.py / inner.py / prof.py read floor-per-region, floor vs rim-minus-standoff and the §34 (7) profile identity; dry.sh / dry2.sh are the arm runners
OTHH  patch    base ed971ccd   lane v2othhfix        2026-09-14T14:56:25  /tmp/harness/v2othhfix_r2.osm  — ROUND 2 closing OTHH build (§34 (9) the pinched ramp, RULINGS 2026-09-14ak) on claude/v2othhfix: rc 0, 511.5 s, ways 1010, nodes 23607, body_sha ba3354ce693f, artifact ledger 3060701734b4, shared repo UNCHANGED; verify DEFECT families EMPTY (rows 2190 -> 2214, the +24 all within_shape on the two pinched ramps); census vs the owner's 1.0.333 patch ADJUDICATED 3206 -> 3223, road_cross_section 6 -> 6, transverse/airside_no_step/zone_on_pavement unchanged; shared AIRSIDE vertices moved > 0.1 m = 0 of 16,810
OTHH  rebake   base ed971ccd   lane v2othhfix        2026-09-14T14:56:25  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix  — ROUND 2 dry --stage structures matched pair: r2_base (main 9a8b253b = the 1.0.333 code) vs r2_fix (§34 (9)); corridors 40 -> 40, refusals 50 -> 50, 2 pinched_ramps (Terminal_Base_2_1@2 vs route9 12.6 m at 11.05 %; Terminal_Base_2_5@0/a vs route7 5.1 m at 36.98 %)
OTHH  patch    base 298b6ac8   lane v2liftedcap      2026-09-14T15:43:25  /tmp/harness/v2liftedcap.osm  — §34 (9) the census takes the LIFTED pinched-ramp cap (RULINGS 14am): rc 0, 494.9 s, ways 1010, nodes 23607, body_sha bdd053b93bbf, artifact ledger 5c0c2ded14c5, shared repo UNCHANGED. MATCHED PAIR: the same patch with the two o4_grade_law_cap_lifted tags stripped is /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2liftedcap/arms/nolift.osm (ADJUDICATED 3223 / law-true 4526 = the v2othhfix_r2 numbers exactly); as built 3204 / 4507. census_rows_diff EXACT 4507 MOVED 0 NEW 0 GONE 19 (all within_shape tunnel_ramp|tunnel_ramp on shapes 828/831). Census json/rows arms in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2liftedcap
OTHH  patch    base a4b7801d   lane v2othhfix        2026-09-14T17:31:46  /tmp/harness/v2othhfix_r3b.osm  — ROUND 3 closing OTHH build (§34 (9) (4)-(5), RULINGS 2026-09-14aq) on claude/v2othhfix: rc 0, 262.3 s (warm), ways 1010, nodes 23615, body_sha a3c64e4a261c, artifact ledger 4afb62b3f6a1, shared repo UNCHANGED; verify DEFECT families EMPTY, rows 2189 -> 2146; census vs the owner's 1.0.334 patch ADJUDICATED 3204 -> 3174 (within_shape -35, road_cross_section +8 away from both pinched roads); route7 road levels byte-identical, route9 within 0.02 m, 0 of 118 service-road vertices moved > 0.1 m, 2 of 16,810 airside (0.10/0.12 m, apron|building corners)
OTHH  rebake   base a4b7801d   lane v2othhfix        2026-09-14T17:31:46  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix/r3_base2/structures.json  — ROUND 3 dry --stage structures (§34 (9) (4)-(5)) vs the lane's round-2 arm r2_fix: corridors 40 -> 40, refusals 50 -> 50; Terminal_Base_2_5@0/a climb_from 38.89 -> 36.50 (+2.4 m), pinched grade 36.98 % -> 25.18 %; Terminal_Base_2_1@2 6.30 -> 6.00, 11.05 % -> 10.80 %; mouth_z unchanged both; both pinched ramps report 'the road face edge (the pack paints no line here)' — OTHH carries NO road-edge marking (marks.py/marks2.py/marks3.py/pol.py beside it)
OTHH  rebake   base 9a49f136   lane v2splitname      2026-09-14T18:03:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2splitname/out/othh.lane.json  — 14at THE SPLIT FILE IS KEYED ON THE OFFSET IT BAKES — MATCHED PAIR of v2_rebake_replay plan --sampler mesh --runs 3 on the 1.0.334 OTHH products (o4_v2_rebake_OTHH.json + OTHH.graded.json + the installed Data+25+051.mesh, --dsf-dump the shared mod cache's +25+051.dsf.55d38455.text). othh.base.json = main 9a49f136 cut with git archive (145.99 s mean); othh.lane.json = claude/v2splitname 4b13e977 (140.26 s mean). Collisions (one file written by >1 placement with distinct offsets) 1 -> 0; distinct body files 1856 -> 1857; splits 705 bodies 1857 both arms; every row byte-identical bar the name (and the 531 anchor_reason/merged_into strings that quote a carrier's file name) — 0 differences beyond the tag. tunnel1 b0: idx 14052 -> __b0_8b16464a baking its own [9.0486,9.5497,-50.1039], idx 14051 -> __b0_c057eb1e baking [-8.8848,9.5497,-84.4220]. guard shared repo UNCHANGED both arms.
OTHH  rebake   base fe0a5b33   lane v2othhfix        2026-09-14T19:34:56  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix/r4b/structures.json  — ROUND 4 dry --stage structures (§34 (9) (6) the half-width margin) vs r3_base2: corridors 40 -> 40, none lost; Terminal_Base_2_5@0/a top_s 44.0 -> 40.0 (IN 4.00 m) grade 25.18 -> 53.95 %; Terminal_Base_2_1@2 top_s 18.9 -> 14.0 (IN 4.89 m) grade 10.80 -> 17.39 %; route7 half-width 3.32 m / route9 3.00 m; mouth_z unchanged. NO BUILD — the 54 % east ramp needs 14be's plate-edge full-depth point (not landed) to give the run back; ramp_in_road measured 0 in BOTH the owner's 1.0.335 patch and the lane's r3b build
OTHH  patch    base 88de7fec   lane v2othhramp       2026-09-14T20:43:50  /tmp/harness/v2othhramp.osm  — CLOSING OTHH build of lane v2othhramp (claude/v2othhramp caf7b9cc; the three coupled items of RULINGS 14bi): rc 0, 649.9 s, ways 1015, nodes 23714, body_sha 87ba777c8a94, shared repo UNCHANGED, verify defects {} (rows 7877). MATCHED CONTROL at the same tree = /tmp/harness/v2othhrampBASE.osm (worktree v2othhrampbase at bdd28759 = main 88de7fec + the v2othhfix half-width merge, rc 0, 511.9 s, body_sha b60c2dd4502b, artifact ledger cc0ead55f1f2 — a later --base-arm at that tree is served from it). A/B: law-true 8939 -> 8957, airside 8854 -> 8851, ADJUDICATED 7623 -> 7620; ramp_in_road 0 -> 0; hairline_pair 1316 -> 1337; airside vertices 22 of 20,001 moved > 0.02 m worst 0.060 m and 0 over 0.1 m; service-road vertices 0 of 116 moved > 0.02 m worst 0.010 m. Pinched grades east route7 53.95 -> 17.17 %, west route9 17.39 -> 18.06 %
OTHH  patch    base bdd28759   lane v2othhramp       2026-09-14T20:44:05  /tmp/harness/v2othhrampBASE.osm  — MATCHED CONTROL for lane v2othhramp: main 88de7fec + the claude/v2othhfix half-width merge, NONE of the three 14bi items. rc 0, 511.9 s, ways 1010, nodes 23605, body_sha b60c2dd4502b, artifact ledger cc0ead55f1f2, shared repo UNCHANGED, verify defects {} (rows 7881). Built in ritual worktree v2othhrampbase
OTHH  rebake   base bdd28759   lane v2othhramp       2026-09-14T20:44:06  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhramp  — MATCHED dry --stage structures TRIPLE for RULINGS 14bi: r0_base (bdd28759 = the half-width margin alone), r1_plate (the plate edge alone), r2_all (all three). tunnels 40 -> 42, wall corridors 25 -> 27, refusals 26 -> 26. EAST MOUTH Terminal_Base_2_5@0/a along the axis: wall-band end 38.89, PAD edge 36.50 (14at's reading), COVERING-PLATE edge 29.00, ramp top 40.00 with the half-width margin (44.00 without) — 9.9 m of uncovered corridor is ramp, grade 53.95 -> 17.17 %. WEST Terminal_Base_2_1@2: the plate covers the whole corridor so climb_from stands at the wall end 6.30 (the pad read 6.00), 17.39 -> 18.06 %. r1 and r2 are BYTE-IDENTICAL: §34 (10)'s generalisation changes nothing at OTHH beyond the §34 (9) pinch. dry.sh is the arm runner; basetree/ is the git-archive base tree
OTHH  patch    base 106459fa   lane v2objcut         2026-09-15T09:44:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/r4_OTHH/structures.json/structures.json  — §33 (6) OTHH matched pair (base /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/b4_OTHH/...): corridors/tunnels/wall_corridors/basins/plates/door_wells ALL BYTE-IDENTICAL (9/44/73/10/2/4); +51 named §33 (6) refusals only.
OTHH  patch    base 106459fa   lane v2objcut         2026-09-15T10:44:12  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/c6_OTHH/structures.json/structures.json  — r2 §33 (6) C lane arm at claude/v2objcut 3b3259dd (base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/b4_OTHH/...)
OTHH  patch    base f912ba81   lane v2objcut         2026-09-15T12:02:00  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e1_OTHH/structures.json/structures.json  — r3 lane dry --stage structures at claude/v2objcut edf1e3c0; matched base arm at main f912ba81 in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e0_OTHH (LEMD) / /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e2_OTHH (OTHH, run 2 - run 1 e0_OTHH read 7 corridors against run 2's 9 at the SAME sha: main's object-corridor reader is NONDETERMINISTIC at OTHH, reported).

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

