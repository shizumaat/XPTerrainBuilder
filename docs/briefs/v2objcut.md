# Brief pack — lane `v2objcut`

Base: main `bf518d0c` · generated 2026-09-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

The pack's structure objects are the cut geometry — three signatures, one reader (§33 (6)); VHHH tunnel5 + LEMD items 1/3/4/6

## The brief

Owner 15e items 1/3/4/6 (LEMD) + 15g (VHHH); OTHH 14av is the reference for signature A. Sites: `airport/tunnel_objects.py` (`read_corridors`, line ~717 the floor-witness hand-off; the §2 crest-plate rule), `airport/wall_corridors.py` (LAW C; the affordance gate ~670; "kerb walls with no floor" docstring), `airport/thin_plates.py` (§33 (2)), `airport/obj8.py` (plates, `HARD_DECK` hardness, floor witnesses), `airport/wall_geometry.py` (`_plan_segments_indexed` — the per-band wall line; NOT the convex hull), `planar/basins.py` (must stop taking these objects), `planar/structures.py` / `structure_approach.py` (`apply_plates`, §33 (2) (a) clamp — superseded for signature C only), `planar/structure_deck.py` (C3 parapet pair → deck extent), `planar/wall_corridor_ramps.py`, `law/airports.toml` + `law/airports_schema.py` (`kerb_wall_corridors` retired), `law/structures.toml`, `docs/specs/auto-patch-v2/tunnel-wall-objects-spec.md` (§2 signature; amend on your branch). Pairing for B: same placement within 1 m + same heading, or one object. Depth precedence: authored floor plate > `bore_datum_m`. §34 (12) (lane v2vmmcshore) still decides whether a tunnel is built at all — you decide its geometry once it is. Artefacts: VHHH patch/graded/placement/rebake at /Users/noah/XPTerrainBuilderData/Patches/+20+110/+22+113/, LEMD at Patches/+40-010/+40-004/; the VHHH DSF anchor_bak dump in the mod cache (`+22+113.dsf.anchor_bak.7fbeaa79.text`, OBJECT_DEF 954/955 tunnel5). Nine VHHH frames are registered; make a fresh VHHH capture and register it. Other lanes: v2vmmcshore (structure_approach `mouths()` gate, structures.py airside cut, zones.py, deck_signature.py), v2lemdstruct2 (structure_approach mouth floor §33 (5), structure_underpass.py, roads), v2padqp (cluster_pad) — keep your structure_approach edits inside `apply_plates` and name every function you change so the merges compose. Do not touch solve/design*.py.

## Bars

- VHHH owner site 22.3038632, 113.9088362 (`tunnel5_done` + `_TN`): the trench outline = the shell's per-band wall line — emitted ring vertices outside the wall line 18 → 0 (`object_cut_offset` ≤ 0.5 m); floor = the floor plate's seated level 1.31 m ± 0.10 (today 2.23); covered extent = the `_TN` flat plate (x 120 → 270 m of the object); ramp stations from the cover's profile (0.00 → −0.91 → −1.71 → −6.01), named. The same table for tunnels 1–4 (floors 0.36 / 0.77 / −1.63 / −1.69; vertices outside 19/25, …, 13/18 → 0).
- LEMD items 3/4 (Bridge3 pair 354.2 × 25.1 m): the cut INSIDE the pair — ramp-edge offsets W +1.4…+2.4 / E −7.6…−8.6 (outside) → both edges ≥ 0.3 m inside the inner faces; the trench runs the pair's full 354 m with mouths at its ends (40.4987906 N, 40.4956006 S) and open ramps beyond (the south ramp toward 40.4951833, −3.5846052); the wall's §7 float 7.13 m → ≤ 0.10 m; the wall foot line = the rim at grade.
- LEMD item 6 (Bridge4 U): ring vertices outside the inner-face polyline 8/24 + 6/23 → 0; chord error ≤ 0.75 m; the ramp reaches the wall's north end (17 m short → ≤ 1 m).
- LEMD item 1 (Bridge2 parapets, 25.6 m apart, deck 24.5 m): the deck centred on the pair — each parapet on a deck edge within 0.3 m (today S walls 6.8 m inside, N wall 8.6–10.6 m outside); the ramps 874/876 unchanged in level.
- OTHH (14av crested walls, signature A): matched replay pair OFF → ON at OTHH — corridor count, mouths, floors and the tunnel-wall offsets IDENTICAL (or each difference named); `kerb_wall_corridors` per-airport key gone from `law/airports.toml` with the signature admitting OTHH's walls by geometry.
- `object_cut_offset` and `object_cut_depth` in `[verify]` + `LAW_FAMILIES` with twins; basins.py receives no signature-A/B/C object (count named).
- Census by family, matched replay pairs at VHHH, LEMD, OTHH: no family worse by > 5 % unnamed; `tunnel_mouth_canonical` before → after.
- The consumer census table (§33 (6)) in the MEASURED block BEFORE the first edit.
- Suite by FAILED lines (zero); ONE VHHH build (`build_airport.py VHHH`) as the closing test; LEMD/OTHH by replay only; `shared repo UNCHANGED`.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/airport/tunnel_objects.py`, `Ortho4XP/src/auto_patch_v2/airport/wall_corridors.py`, `Ortho4XP/src/auto_patch_v2/airport/thin_plates.py`, `Ortho4XP/src/auto_patch_v2/planar/structure_deck.py`, `Ortho4XP/src/auto_patch_v2/planar/wall_corridor_ramps.py`, `Ortho4XP/src/auto_patch_v2/law/airports.toml`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/solve/design.py`, `Ortho4XP/src/auto_patch_v2/planar/zones.py`, `Ortho4XP/src/auto_patch_v2/planar/structure_underpass.py`, `Ortho4XP/src/auto_patch_v2/constraints/cluster_pad.py`

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

## Spec (design-surface) §34 (12)

## §34 (12) A TUNNEL SERVES THE FIELD OR IS NOT BUILT; NO STRUCTURE CROSSES THE WATER; A CORRIDOR NEVER CUTS AIRSIDE PAVEMENT (owner RULINGS 2026-09-15f item 1; Fable 2026-09-15i) — lane `v2vmmcshore`

**The reading (VMMC 1.0.340).**  Eleven `tunnel_ramp` faces and 19 rims
run 600 m along the Taipa seafront from an OSM `highway=service,
tunnel=yes` bore (ways −5508/−5507, no layer, no bridge) — a car-park
ramp under a building that has nothing to do with the aerodrome.  It was
admitted because its mouth stands inside cover ⊕ `mouth_standoff_m` 150
(§29 (1); pav5 is 36 m away); its floor is 6.16 − 5.1 = 1.06 m flat for
six faces because six mapped `bridge=yes` seafront road ways each sever
the climb (§33 (4)/§34.5 (6)) and the approach walk runs to
`max_ramp_length_m` 600; face −10098 contains 35.9 m of coastline −687;
and the corridor knifes code-E taxiway pav5 into six faces at 3.58–4.50
m against the 6.10 field, because only the runway family and pads are
exempt from a corridor cut (08-07 ruling 4).  "Should not be any tunnel
here … cutting the taxiway is an error."

**RULED.**  (1) **A tunnel is built only where it SERVES THE FIELD**: its
bore way, or the covered stretch it derives, passes UNDER a classified
cover element — airside pavement, a pad or unit footprint, a deck the
pack authored (a plate or wall corridor, §33) — inside the classified
cover.  A mouth within `mouth_standoff_m` of the cover is a necessary
condition, never a sufficient one; a bore whose only covers are mapped
`bridge=yes` roads is not an airport tunnel and is NOT built.  (2) **No
structure face, rim or ramp crosses the water**: tunnels, decks and
basins are clipped by the WATER region (the flat-site pass's water mask
— "47.0 % of the synthetic extent is WATER … the mask edge is the sea
wall" — and the coastline ways); a corridor reaching the water ends at
the shore.  (3) **A corridor never cuts airside pavement.**  Where a bore
crosses a taxiway, junction, apron, stub or parallel, the pavement is
the DECK of an underpass (§34 (5), the covered extent incl. the strip
per (5) (b)) or the corridor stops short of it; the pavement's surface
is never lowered by the trench.  `ramp_cuts_runway_family = false`
generalises to the airside role set; the exception list is empty.
(4) A mapped bridge severs the climb only when its way CROSSES the bore
(an over-crossing within the corridor's own width); parallel or
oblique seafront bridges do not extend the covered extent.  Consumer
census at spec time (RULINGS 2026-08-30l): the lane tables every reader
of the corridor region, the water mask and the airside-cut exemption
before editing (`planar/structures.py`, `structure_approach.py`,
`deck_signature.py`, `structure_deck.py`, `zones.py`, `emit/osm_adapter`,
`verify/*`), one table, one derivation site each.

## RULINGS

## 2026-09-15j VHHH 15g + LEMD 15e items 1/3/4/6 ATTRIBUTED (scouts, 1.0.340): three authoring signatures for one intent, none read as geometry — RULED §33 (6) THE PACK'S STRUCTURE OBJECTS ARE THE CUT GEOMETRY, lane v2objcut

VHHH (scout): five tunnel placements, each a SHELL (`tunnelN_done.obj`,
y −6.01/−6.54/−8.95/−9.01 … 0, largest plate = the FLOOR, 733–16,759
m²) + a COVER (`_TN`, `HARD_DECK` plate at y 0, 427–11,254 m², with a
descending ramp profile 0.00 → −0.91 → −1.71 → −6.01 at tunnel5); the
engine builds OSM-bore mouth-and-ramp only: floor DEM − 5.1 (2.21–3.27)
against the authored 1.31 / 0.77 / −1.63 / −1.69 (0.92–3.91 m too
shallow), 62–83 % of each ramp inside the shell's hull but 10–19 ring
vertices per tunnel OUTSIDE it (median 6.6–68 m). Owner site
22.3038632,113.9088362 = face 1108 inside `tunnel5_done` (245.9 × 73.2
m). EGLL (the owner's reference): the same author convention (`N.obj`
cover + `Na.obj` shell, HARD_DECK covers, floors −4 … −7); no EGLL
capture exists. Why unread: `tunnel_objects.py:717` sends any floor
witness to basins.py; the crest-plate rule needs a plate ≥ 2 m ABOVE
zero; `thin_plates` takes 1.0–1.5 m only; LAW C (`wall_corridors`) is
gated by `kerb_wall_corridors = true` under `[OTHH]` alone
(`law/airports.toml:15-18`) and refuses walls with floors. OTHH's walls
(−15 … +5, −10 … +9.55) are the crested class. LEMD (15h): parapets
0.91–1.03 m refused at the skirt gate; Bridge3's pair read as a plate
width; Bridge4's ring a 9-station chord cut. RULED §33 (6): signatures
A (crested), B (shell + flush hard cover: floor plate = depth, cover =
covered extent + stations), C (thin surface walls: pair = trench top
edges, full length, mouths at the ends; single U = inner-face polyline
to the wall's end; parapet pair = the deck's extent) → ONE reader, ONE
record class, basins see none; the per-airport affordance retired;
§33 (2)'s plate reading and (2) (a)'s clamp superseded for C; two new
verify families. Lane v2objcut (owner sites: VHHH tunnel5; LEMD items
1/3/4/6; OTHH 14av unchanged by replay pair).

## 2026-09-15h LEMD 15e ATTRIBUTED (scout, one build 1.0.340): items 2/5/7 RULED (§16g (10) (11), §33 (5), §34 (11), §34 (5) (b)); items 1/3/4/6 are ONE law with 15g/14av — held for the VHHH inventory

Scout (read-only, engine 1.50.1787 products under Patches/+40-010/
+40-004, the pack's 3,186 split bodies, the DSF dump): NO DEFECT and no
floor line — the verify census (1,592 rows) has no `runway_transverse`
family at all under the converged solver. Item 1: the deck is centred
on OSM bridge ways −6288/−6291 (§33 (4)); the pack's parapets Bridge2
b3/b4 (S, 0.92 m) and b0/b2 (N, 0.93 m), 25.6 m apart, are REFUSED as
walls at the 1.5 m skirt gate (13r: draped plates) — the 24.5 m deck
sits ~8–9 m south of the parapet pair (S walls 6.8 m INSIDE the deck, N
wall 8.6–10.6 m OUTSIDE). Item 2: garage PKT4 b0 seated on pad
building12 (616.10) by unit membership; the pad polygon ends 55.28 m
short; 3.63 m of air over raw DEM; crest plate + basin both refused on
the flat render datum → RULED §16g (10) (11): re-arm `pad_from_cluster`
under qp (lane v2padqp). Items 3/4: ONE wall pair Bridge3 b0 (354.2 ×
25.1 m, H 1.03 m, class basin) consumed by §33 (2) as a WIDTH and a
mouth station only — the cut lies 1.4–2.4 m outside the W wall and
7.6–8.6 m outside the E wall; the §33 (2) (a) clamp ends the corridor at
bore way −5931 (83.9 m / 46.6 m inside the wall's ends), leaving 220 m
of wall with no trench and the wall floating 7.13 m at item 4; "like it
used to" = 14bl items 7/8 pre-clamp (mouth at the plate end); the
owner's 40.4951833 is 46.5 m beyond the wall's S end = the open ramp.
Item 6: Bridge4 (2.01 m) IS the edge-wall corridor, but the emitted
ring is a 9-station chord polyline cutting the curved U's corners 0.5–
2.0 m OUTSIDE the wall line at 8/24 stations and stopping 17 m short of
the wall's N end. Item 5: the "road" is not a road in the patch (every
station `cross_connector:pav61` + `gap_interior_ring` + zone2; no road
way within 60 m); hole ring −10689 144,429 m² cover 0.011; mouth floor
2.91 m under its rim vs `bore_datum_m` 5.10 → RULED §33 (5) + §34 (11).
Item 7: §34 (5) (a) IS applied; the trench (face 993, 572.42) opens
12.8–15.5 m from the kerb (577.80) inside zone 1 — a 5.38 m unbanked
face; junction pav157 shares the runway's nodes, 1.9 % over 18.2 m →
RULED §34 (5) (b). THE WALL THEME: LEMD walls 0.91–2.01 m (sit on the
surface) vs OTHH 19.6–20 m (descend 10–15 m below their zero) — the
1.5 m skirt gate is what makes LEMD's walls plates; the law for walls
as the author's cut geometry (15e 1/3/4/6 + 15g VHHH + 14av) is written
ONCE after the VHHH inventory. Lanes: v2padqp (item 2 + HECA's 14
mismatches), v2lemdstruct2 (items 5, 7).

## 2026-09-15g OWNER VHHH READ (app 1.0.340): the tunnels have object-based interior walls, ramps and hard covers — cut the trenches to THOSE — verbatim

1. "The tunnels have object based interior walls and hard covers where
   needed (like EGLL does), so we need to cut our trenches based on
   those. The tunnel here: 22.3038632, 113.9088362 needs to align with
   the provided ramp and walls from the airport package. This applies
   to most of the other tunnels as well."
Third airport in one theme with 15e items 1/3/4/6 (LEMD short surface
walls) and 14av (OTHH deep walls): THE PACK'S STRUCTURAL OBJECTS —
walls, ramps, covers — ARE THE AUTHOR'S CUT GEOMETRY. Scout dispatched
for the VHHH inventory before one law is written for all three.

## 2026-09-15e OWNER LEMD READ of app 1.0.340 (§20c solver ON): "Excellent work, most issues resolved … nearly ready for a beta release" — seven polish items, verbatim

1. Terrain bridge at 40.483644, -3.580382 (screenshot 1): "much better,
   but can you identify the proximity of the two edge wall objects in
   the scenery package to the bridge edges as indicating they should
   be used as guides for where the author wants the bridge? Ideally we
   should grade the bridge so those sit smoothly on either edge of it."
2. "Why is there no pad emitted for the large parking garage here:
   40.4892214, -3.5944287? It has to stay anchored to the terminal, so
   now it's floating and we should be raising the terrain under it so
   it can blend smoothly with the rest of the area."
3. Tunnels, e.g. 40.4980338, -3.585152: "we should identify when
   there's walls very close to it, they provide a guide for where the
   author expects the tunnel. When they're deep like at OTHH then the
   walls descend into the tunnel, when they're short like this one at
   LEMD they are intended to just sit on the surface so the tunnel
   ramp needs to be inside them so the terrain grades under the wall
   object and the wall sits on top of the tunnel edges."
4. Tunnel 40.4957014, -3.5849565 "should be curving and extending out
   closer to 40.4951833, -3.5846052 like it used to. Again there's
   surface walls to mark the shape."
5. Tunnel mouth 40.4947697, -3.5829037 "doesn't seem to be providing
   the right depth, and the ground is getting pulled down between
   there and 40.4940268, -3.5826498. We may need to provide a smooth
   sloping road grade for the road here: 40.494628, -3.5832911 to
   40.4943869, -3.5823239 to keep the ground from being pulled down."
6. Tunnel 40.4861895, -3.5663473 "should also use the provided surface
   wall objects as a precise guide for where to cut the mouth, ramp
   should stay within the wall boundaries."
7. Screenshot 2: "the lateral slope and hole in the taxiway here:
   40.4611623, -3.5444804. It's better, but still not fixed." (14bl
   item 1 residual.)

"Everything else at LEMD looks great." Screenshot 1: the bridge deck
with a white edge-wall object floating beside its left edge, a second
one lying on the far side; the deck's near ramp drapes over dark
cut terrain. Screenshot 2: a taxiway crowned across its width with a
dark hole at its left edge and red/white barriers along both edges.
THEME (items 1/3/4/6): the pack's SURFACE WALL objects are the
author's footprint guide for bridges and tunnels — a new law class;
scout first (consumer census + object inventory at each site), then
the spec.

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

## 2026-09-14bl Owner read of 1.0.336 LEMD ("very close, good work") — ten items; scouts `v2lemd336s` (structures) and `v2lemd336o` (objects)

Owner, verbatim: "LEMD is looking very close, good work. Bug reports:
1. There's a tunnel mouth here: 40.4614416, -3.5447633 that we are
not emitting, but looks correct because the DEM is already low there
and we are correctly setting the taxiway elevation on this side.
However the otherside where we do create a tunnel ramp it's cutting
deep into the taxiway and also distorting it. The mouth should stop
back about here: 40.4609913, -3.5445335 2. The buildings and various
cargo objects are floating here: 40.4552413, -3.5687453. They should
be separate buildings each seating on the ground. 3. In this area:
40.461514, -3.5732897 there's some object submerged about 1m
underground. 4. Barriers and small buildings around these two runway
ends are floating: 40.4981624, -3.5595534 5. The basin edge here:
40.4910254, -3.5681642 is allow a small gap between the outside wall
and the apron leaving a narrow visible canyon 6. The blast shield
object here 40.4980571, -3.5829243 is floating 7. The tunnel here is
placed way short of the mouth for some reason: 40.4987722, -3.584993.
The mouth should be here: 40.4980461, -3.5850118 8. The other side of
that tunnel's mouth should be between 40.4960195, -3.585058 and
40.4960167, -3.5849289 9. Building over here 40.4841856, -3.5854064 is
floating again 10. The bridge deck here: 40.4835044, -3.5801638 should
be a single smooth bridge, no small gap here, and it's two end points
are: 40.4835967, -3.580923 and 40.4835412, -3.5799114, that's bridge
extent to cover the terrain cutting down to the road running under it."

* Scout `v2lemd336s`: items 1, 5, 7, 8, 10 (the tunnel at 40.4614 —
  its ramp cutting into the taxiway, the mouth station vs the owner's
  40.4609913; the basin edge gap at 40.4910; the tunnel at 40.4988
  placed short of its mouth and the far mouth between the owner's two
  points; the bridge deck at 40.4835 — the gap, the two end points as
  the deck extent). Scout `v2lemd336o`: items 2, 3, 4, 6, 9 (units /
  pads / seats at each coordinate — separate buildings each on the
  ground = §16g (10)'s line; the submerged object; the barriers and
  small buildings at the runway ends; the blast shield; the building
  at 40.4842 "floating again" — 11ah's site).

## 2026-09-13r — v2wallplate MERGED (a16431b9, lane 35db07fc): §33 — every screened resource named (182 → 184 named refusals + 1 plate refusal; the four suppressed prefixes gone); the THIN-PLATE WALL class (`airport/thin_plates.py`, `law/tunnel_object_schema.py`; two gates the measurement forced — a span CEILING at `least_skirt` (else a 1,035 × 557 m cargo terminal is a "plate") and an ALONG-AXIS run test (else a 750 × 89 m slab claims seven bores it merely crosses) — recorded in the law file, accepted); item 5's mouth at the object's north end 40.4987906, −3.5849926 (moved 83.9 m), 25.1 m wide, axis on the object's centre (0.0 m); item 6's mouth ground 610.23 → 607.01, the ramp 36 → 144 m climbing monotonically to the DEM (rim 0.24 m ≤ 0.3); 46 of 50 LEMD tunnels byte-identical; OTHH 0 plate mouths, 0 crest caps (its 9 object + 73 wall corridors untouched); one LEMD build (355 s, ledger 024bfdf4297b, optimal; census 3,573 / 1,143 → 3,588 / 1,178, cockpit motion 2 → 1, visual 0). §33 (3) implemented as a CAP `crest = min(DEM(mouth), approach ground + bore_datum_m)` — the literal trigger fired on every ordinary portal (accepted, the spec text yields to the measurement). ITEM 9 MISSED: the decks went from 2.77 m BELOW the apron to 2.0–2.1 m ABOVE it — the deck face is clipped 19.2 m short of the mapped way's east end and the end reads the DEM (606.10) there, not the apron's solved value (606.60); a profile over the face's extent made it worse because THE DECK RING'S VERTICES ARE THE CORRIDOR RIM'S (one node carries both ways); two refinements owed to `v2rampwalk`: read the end's ground by walking the mapped road to the first governed cell (§34 (1)'s route reading) and rule the rim/deck vertex coupling. `Bridge2.obj` / `LEMD50.obj` are DRAPED object plates (their top an offset over the solved ground, not a datum) — RULED: a draped deck plate rides the terrain deck the mesh gives it; the terrain deck is what must be right (item 9), no object re-seat. Suite 1,167 / 1 twice. Three pre-existing v1 reds unchanged (`test_tunnel_portal_fidelity::TestClearanceAnnulus`, `test_object_anchor::test_kclt_eight_bake_pool_end_to_end`, `test_tunnel_ramp_run_merge::TestItIsNotAPostPass` — owed).

## Tool: obj8_split_report

| `Ortho4XP/tools/obj8_split_report.py` | THE OBJ8 SPLIT, DRY-RUN (spec `object-placement-spec.md` §4 / §6 / §7; owner RULINGS 2026-09-11b) — what a pack's object stage becomes once placements are AGL, objects are cut into their RIGID BODIES and each body carries its own anchor. Reads only a build's own two products — the re-seat plan (`<ICAO>.rebake.json`: the pack read once, its welded parts and the ε-contact graph) and the emitted DESIGN SURFACE (`<ICAO>.graded.json`, whose `building` faces are the object pads and `structure_rim` breaklines the basin walls) — and NEVER opens the pack for writing, never reads the DSF and never builds anything. Prints per placement the bodies, their §6 class, each body's anchor point / reason / authored offset, the files that would be written and the placements KEPT WHOLE with the reason (`one_body`, `anim`, `unparsable`); `--write-into DIR` writes every cut file into a scratch dir and parses each back through `airport/obj8.parse_obj8` (LEMD 13,924 files, OTHH 65,360, all parsing back with the written triangle count, 2026-09-11); and prints §7's CENSUS — the design surface at a body's ANCHOR against the surface under each of its ground-contact FEET, the |Δ| histogram `seat_feet_census.py` prints from a mesh and a seat result, read instead from the plan and the design surface so the two are comparable. A foot or anchor outside every graded face reads `off-surface` and is never guessed at (the DEM governs there and this tool does not open the DEM). `--no-cut` for body counts only, `--filter`, `--json`, `--split-tol` to override `[placement] split_tol_m`. ROUND 2 (owner RULINGS 2026-09-11e, spec §9): the bodies are COARSENED (bodies of one placement whose intended-zero terrain heights agree within `split_tol_m` are one file, the senior body's anchor; an elevated body joins the nearest ground group) and each anchor is the GENERIC one (the footprint point where the design surface equals the body's zero; a body with authored relief beyond its skirt takes its low-side foot and is reported with the residual) — LEMD 302 placements -> 985 files (3.26x), OTHH 954 -> 1,172 (1.23x). §13 (owner RULINGS 2026-09-11r/s): an ELEVATED body — one whose lowest authored vertex, or the `y_zero` of the anchor the generic rule gives it, stands above `[rebake] elevated_base_m` — NEVER has a file of its own; it joins its CARRIER (the same placement's ground body with the largest plan overlap, else the nearest) at its authored offset, and a placement with NO ground body is KEPT WHOLE with reason `footless`. The report prints the two classes by name — `elevated bodies as own files` (BAR 0) and `footless placements kept whole` — because the FEET histogram cannot see this defect: the writer shifts an elevated body so its own lowest vertex lands on the terrain and every foot then reads perfect (LEMD's 218 roofs/decks/tower parts censused green while the sim was broken). Measured on matched pack copies: LEMD own-files 278 -> 0, files 1,099 -> 828, feet > 3 m 1,060 -> 151, worst 34.06 -> 13.75 m; OTHH 1,203 -> 333 files, feet > 3 m 952 -> 6. ROUND 3 (owner RULINGS 2026-09-11f, spec §10): the write half RESTORES every `<obj>.anchor_bak` in the pack before any file is written (counts in the plan's provenance), and a LINE OBJECT authored as one component is cut into SEGMENTS by triangle station (`--line-segment M` overrides `[placement] line_segment_m`; 0 disarms it) — LEMD 897 segments from 271 one-line bodies, 985 -> 1,086 files, census `> 3 m` 30 -> 25; OTHH 1,187 files, `> 3 m` 0. `--write-pack PACK_COPY` runs THE WHOLE WRITE HALF into a pack COPY through `airport/placement_write.apply_plan` (cut files, DSF + backup + provenance, dump-cache refresh, `o4_v2_placement_<ICAO>.json`) and reads the written DSF back; it REFUSES a live X-Plane install. The census also splits the feet over 0.3 m into BURIED (lawful) and FLOATING (the defect the eye reads). `--rows-near LAT,LON[,R]` (lane `v2padcluster`, 2026-09-14) is that SAME projection selected BY PLACE — every body whose ANCHOR is within R metres (default 40) of the coordinate, nearest first, each row carrying its `site_m` — because the owner names a defect by coordinate and the shapeIDs in a report go stale between builds while a coordinate does not; `osm_site --at/--contains` answers the other half of a site question (which emitted FACES cover the point) and is not re-spelled here. Promoted from the scout `v2heca331`'s scratchpad `site.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse): the 14g attribution, then §16g (10)'s per-site bars; its graded-face half was already `osm_site`'s and was NOT copied. Twin: `tests/auto_patch_v2/test_v2objsplit.py::test_rows_near_selects_the_same_rows_BY_PLACE`. `--rows SUBSTR,SUBSTR` (lane `v2canopy4`) prints the PER-BODY rows of the placements named — the body's anchor (point, surface z, `y_zero`, reason), its ground-contact feet, its worst foot signed with |Δ|, and the 0.3 m verdict — for the owner's named sites (`OldTerminal_FSX-LEMD38,-LEMD84,-LEMD60`); it is a PROJECTION of the one census pass, never a second instrument (the bins, feet and worst list are identical with and without it, twinned). §14 (owner RULINGS 2026-09-11u/v, lane `v2carrier`): a FOOTLESS placement is CARRIED — written as a body file at its CARRIER's anchor with the carrier's `y_zero` (the footed body of its UNIT it abuts with the largest contact, else the nearest, else the largest) — a BASIN resource is never split and anchors at a RIM point where the design surface equals its zero (`rims` wired at last), and bodies of one resource that OVERLAP IN PLAN bind whatever the contact graph says. The report prints the four §14 bars (`footless at datum` 0, `footless on ground` 0, `basin bodies split` 0, `spread`) beside §13's, from `airport/placement_carrier.census_v14` — the same call `seat_feet_census --placement-plan` makes over the same plan shape, so the two instruments are one code path. Measured on the app's 1.0.315 LEMD frame: the four footbridge resources at the terminal's zero 616.65 (deck bottom road + 4.4-5.0 m, was ON the road), `Terminal4SAT_pink-LEMD01` at its terminal's 597.43, the basin's three resources one file each on ONE rim vertex (zero spread 7.0 m -> 0.00, parapet +2.99 above the rim), files 828 -> 855, round trip OK, row census `> 3 m` 17. Twin: `tests/auto_patch_v2/test_v2objsplit.py`. §15 (owner RULINGS 2026-09-11ae, lane `v2roofcarrier`): the CARRIER IS WHAT THE BODY STANDS OVER — chosen across the whole UNIT, every resource alike, by largest PLAN OVERLAP beneath, else largest contact, else nearest (§13's same-placement scope and §14's contact-first order are superseded; the pack names its roofs as their own resources, so the walls a roof rides are almost never its own file); the plan-overlap BOND is RE-CUT where a bound group's intended zeros span more than `split_tol_m` (a rigid body is never wider than the terrain it can stand on; BASIN exempt); DUPLICATE ROWS of one resource identical in lon/lat/heading are ONE placement, all of them replaced (`--write-pack` reports `duplicate rows of a SPLIT placement ... surviving after the write`, bar 0); an anchor or foot on no graded face is marked OFF-SHEET and excluded from every comparison and bar; and the report prints §15 (3)'s `stands-over float > 0.5 m` from `airport/placement_carrier.census_v15` — `float = zero - zero_beneath`, the class NEITHER the feet histogram nor §14's bars can see (a carried body has no feet at all), barred at 0 for CARRIED bodies and reported for footed ones. §16 (owner RULINGS 2026-09-11ai, lane `v2skipped`): the report adds the POPULATION census (`placement_carrier.census_population`: `rows on the datum outside the plan` — the resources the SEAT-era thickness gate dropped, which keep the pack's shared-datum row and render where the datum is, bar 0 — beside the lawful skips and the multi-anchor class, reported not barred) and `census_v16`'s `float = zero - ground_under_geometry`: the ground read under the body's OWN parts (`geom_box` / `foot_boxes`, the median of the part-box centres) and never under its carrier's box — `CARRIED bodies whose carrier's zero is over 1 m from the ground under their own geometry` (bar 0; LEMD 39 -> 0 on matched arms) and `files whose own-geometry ground departs over 3 m from the ground at their row` (26, reported). `--admit-skipped PACK_ROOT` puts the thickness-gated resources of a PRE-§16 plan back into the population by reading their rows from the pack's own DSF (one part per component, no contact graph, the member id IS the DSF row index) — what a build's own plan now carries, for replaying a plan written before the switch; LEMD 25 resources / 25 rows, OTHH 99. §16a (owner RULINGS 2026-09-11aj, lane `v2skipped2`): a CARRIED body is cut where its CARRIER is cut (one piece per carrier terrain group its own triangles stand over, each riding that group's zero; never by the ground under itself), the ground check moved to the carrier's OWN feet (`Candidate.ground_off`, `surface(foot) - y_foot` against the body's zero), and `census_v16`'s carried number demoted to INFORMATION — the bar for a carried body is §15 (3)'s `zero - zero_beneath`. The report prints `carried bodies left uncut by the ground` / `cut by their CARRIER into N piece(s)` and, beside the §15 bar, how many of the carried floats stand over a body the law REFUSES as a carrier. LEMD carried float 58 → 4, files 1,591 → 1,328, plan stage 9.9 → 6.3 s; OTHH 7 → 39, 46.4 → 60.2 s (both OTHH bars missed and reported). 11ak (lane `v2skipped3`): the CARRIED bar's `beneath` is the carrier THE LAW CHOSE (`merged_into`, resolved by identity over every row that reads a zero — a carrier written WHOLE names its MEMBER RESOURCE, which is the whole of OTHH's residual), and a body the law REFUSES as a carrier is counted and named as its own class, `carried over a refused body`, with how far its own feet stand off; §16 (2) also cuts BY FOOT (`placement_cut._LineCutter.foot_groups`: the feet grouped by the zero each says the body has, `surface(foot) - y_foot`, each triangle joining the group of the foot nearest it in plan) — the class no ground cut can see, a body whose FEET are authored over metres of relief on terrain that barely moves, which is exactly what §16a (2) refuses. The re-cut line prints the three cuts (terrain / triangle / foot). LEMD carried float 4 → 0, refused carriers 117 → 21 (13 of the residue are rim-anchored BASIN bodies the foot cut is exempt from), files 1,328 → 1,371, plan stage 6.2 → 5.66 s; OTHH carried 42 → 0, refused 55 → 19, files 1,679 → 1,622, plan stage 59 → 31 s (`solid_components` read in one sort instead of a mask per component; `bind_plan_overlaps` swept by the hull's south edge). 11al (lane `v2basincarry`): a BASIN body is EXEMPT from §16a (2)'s ground test — its zero is the RIM (§14 (2)) and its floor feet are authored below it by construction — so it may carry, and the report prints `§16a (2) basin carriers` (how many basins, how many the feet test would have refused) beside the refusal set: LEMD refused carriers 21 → 8, OTHH 19 → 4, carried float 0/0 unchanged. §14a (owner RULINGS 2026-09-11ap item 6, lane `v2basinring`): a BASIN body follows its RING. §24 (1) puts the rim vertices at the APRON's level, so the ring is not level (LEMD's T4 pit 597.68 … 599.52 over 59 nodes) while §14 (2) wrote every basin body at ONE rim point — the owner's "gap between wall and apron", +0.71 / −1.13 m, while the §14 `spread` bar read 0.01 because it measures the pit's bodies against EACH OTHER. `airport/basin_ring.py` (NEW: the whole law — `arcs_of`, `ring_arcs`, `member_kind`, `ring_bar`) cuts the ring into ARCS whose z agrees within `split_tol_m` and cuts each basin body's WALL BAND by them, one piece per arc anchored at that arc's rim point (the interior remainder keeps §14 (2)'s single point: the trench floor is one level); and a member authored AT THE RIM PLANE but standing inside the ring is a FLOOR body that takes §16 (3)'s ground under its own footprint, never the rim, never a carrier. The report prints the RE-DEFINED bar — `§14a spread of a BASIN RING = max |wall base − ring z| over its nodes` (bar ≤ `split_tol_m`), with the nodes on an arc the pit has NO WALL on reported beside it — and the `§14a basin FLOOR members` / `basin bodies cut by the ring's ARCS` counts. It needs the rings WITH their heights (`census_v14(rims=..., arc_cap=..., counts=...)`; `RimRing.z`, and the `basin_arc_wall:<ref>#<k>` counts keys the cut writes are how the bar tells "no wall here" from "the wall is written in the interior piece"). Matched arms on the app's 1.0.319 LEMD frame: the ring bar 1.12 m / 9 nodes over → **0.18 m / 0 over**, `LEMD13__b0` off the rim and onto its own ground, files 1,371 → 1,394, feet > 3 m 518 → 412, floating 9,509 → 9,014; OTHH's 21 basin carriers and its whole foot census byte-identical. §16b (owner RULINGS 2026-09-11ap, lane `v2owncut`): the TERRAIN CUT IS PRIOR AND UNIVERSAL and is read on the body's OWN WRITTEN TRIANGLES — including everything the writer will put in the file (`placement_cut._LineCutter.all_tris`: a placement the plan reads as ONE body is written as the WHOLE object, which is why `green-TEJ3`'s 4-triangle part read 0.22 m of ground while its 2,342 m file stood +16.22 m over it) — so a CARRIED body is divided by the ground under itself first and §16a (1)'s carrier cut runs inside each piece; §9's coarsening additionally requires PLAN CONTIGUITY (`[placement] coarsen_reach_m`, 30 m) and acts WITHIN a terrain group (the pieces carry the ground they stand on, or the very next pass welds them back); each PIECE finds its own carrier, and a FALLBACK candidate (contact / nearest / largest, no plan overlap) is refused unless its zero is within `split_tol_m` of the ground under the piece (`carrier_refused_far_from_carried_ground`). The report prints `census_v16b`'s two bars over the WRITTEN geometry the plan now publishes per body (`geom_pts`, one sample per 10 m cell, thinned to 32 by the farthest-point walk): `carried piece float over its own ground > 0.5 m` and `body wider than its terrain group`, both bar 0, with the BASIN exemptions (§14 (2) / 11al) counted apart and the wide residue split by class. `--coarsen-reach M` overrides the contiguity reach. Measured on the app's 1.0.319 LEMD frame: the owner's item 3 +10.74 → the plate ON the roof beneath it (618.58 vs the group's 618.60), item 5 +16.22 → 620.38 vs 620.27, `Terminal4_48` zero-vs-ground −4.02 → median −0.01, `Taxisigns-SENRG` 38 of 80 bodies over 0.3 m → 12 of 419; files 1,371 → 3,272 at the amended 100 m reach (4,633 at the refuted 30 m), plan stage 5.6 → 10.1 s (bar ≤ 8 s MISSED, reported). §16c (owner RULINGS 2026-09-12b/12d, lane `v2atom`): THE CONNECTED COMPONENT IS THE ATOM — `--torn-seams PACK_ROOT` prints the TORN-SEAM CENSUS over a WRITTEN pack (the plan argument is then the WRITTEN `o4_v2_placement_<ICAO>.json` and `--graded` is not read), and the same census prints automatically after `--write-pack`: sibling files of ONE placement that share an AUTHORED VERTEX (the key `obj8.solid_components` welds on, `round(x, 3)`) are two halves of one connected solid written at two zeros, with the base step per seam, the step histogram, the worst list and the per-class breakdown, and §10's line segments / §14a's basin arcs — the only lawful station cuts — counted APART.  Two bars, both 0: `torn seams outside line/arc pieces` and `single-component resources in >= 2 files`.  The instrument is the scout `v2lemd320`'s `tear.py`, promoted on its second use, and lives in `airport/placement_seams.py` (`census_torn_seams` / `census_torn_seams_lines`, re-exported through `placement_census`).  Measured on the live 1.0.320 LEMD pack it reproduces the owner's four sites exactly (`HANG3` 10 files / 14 seams worst 3.05 m; `green-LEMD50` 7 / 11.12 m; `Bridge2` 8 / 11.72 m; `green-STRT4` 53 files, `__b44` 16.29 m) and the class (2,554 seams, 1,994 over 0.30 m).  On matched replay arms the law takes LEMD 723 -> **0** seams and 128 -> **0** single-component splits (files 3,253 -> 2,804, plan stage 13.5 -> 10.2 s over 3 runs, round trip OK), OTHH 639 -> **1** and 165 -> **1** (files 1,897 -> 1,898). §16c (6) (RULINGS 2026-09-12h, round 2): `--contact-eps M` overrides `[placement] contact_eps_m` (2 mm) — components of ONE resource whose geometry comes within it, or whose parts the rebake plan's ε-contact graph already links, BIND into one rigid body for anchoring (one zero, the senior component's carrier): OTHH's `OTHH_Fuel_02_LOD0_007` carries two components 0.4 mm apart that the millimetre weld key reads as separate.  LEMD files 2,804 -> 2,776, seams stay 0, `Terminal4_48` zero spread 3.58 -> 0.69 m, plan stage 9.6 s (main 13.5). ROUND 3 (RULINGS 2026-09-12j): the entry now runs inside `harness/shared_repo_guard`'s WRITE GUARD and its before/after audit (a round-2 OTHH `--admit-skipped` run had created `Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text` in the SHARED repo with both lane-local cache env vars exported and nothing refused it); every run prints `[guard] shared repo UNCHANGED`.  `--rigid-reach M` overrides `[placement] rigid_reach_m` (2.0) — §16c (8): SOLID components of one resource within it chain into ONE rigid cluster, which is the atom of the BODY as well as of the cut (LINE objects excluded).  `carrier_fill_min` is DELETED from carrier candidacy (§16c (7)); the CLASS exclusion stays.  LEMD: `HANG3` 6 files / 1.37 m -> 2 / 0.45, `green-STRT4` 23 -> 15 files (spread 8.90 -> 3.73), files 2,776 -> 2,121, §16b wide 1,405 -> 967, seams 0, round trip OK; five largest rigid clusters are all SINGLE components (5,157 / 2,890 / 2,514 m — fences and VOR markers, not chained) and `green-TEJ3` stays 9 components / 9 clusters. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. **§17 CRITICAL MOTION IS READ** (owner RULINGS 2026-09-12am (2), lane `v2objmotion`): the graded surface's FACE ROLE under every foot (`airport/placement_boxes.GradedRoles` / `graded_roles_from_doc`, built from the SAME parsed `<ICAO>.graded.json` the sampler and the pads are, senior face by `precedence.toml`'s authority order, a 55 m grid over the faces' boxes) joined to §7's own float there (`airport/placement_motion.census_motion`, re-exported through `placement_census`): a body with a foot on a ROLLED-ON face (`law.tables.rolled_on_roles`) is ON PAVEMENT and every such foot is judged at `[cockpit] motion_step_m` 0.05 m, named with resource, foot coordinate, face role and SIGN. The block prints the count of bodies on pavement, the feet over the threshold, the worst ten, and the breakdowns by resource / face role / body class / anchor rule / size band, plus what the EYE reads at those feet (floating vs buried over `visual_m`) and the MEDIAN-anchor arm. BASIN bodies are counted APART (§14 (2) / 11al: a pit's zero is its rim and its floor feet are authored below it — they were LEMD's whole worst ten). Measured on the 1.0.320 LEMD frame: 493 of 2,153 bodies stand on pavement, 7,124 feet on 399 over 0.05 m; after the §17 anchor rule 6,635 on 407 (OTHH 6,234 → 3,877 on 113 → 103). RULINGS 2026-09-12ap (lane `v2pavefeet`): `--motion-rows OUT.json` writes §17's PER-BODY projection — one row per written body with its anchor, class, anchor reason and every ground-contact foot (lat/lon, authored y, surface z, face role, on-pavement, float) — the rows `census_motion` itself reads, never a second census (the scout's scratchpad projection, promoted on its second use). (E) THE SAMPLER HONOURS GRADED HOLES: a Delaunay over the emitted VERTICES spans a hole ring with triangles reaching from an apron vertex to a trench vertex, and LEMD read **592.22 m at a point whose ROLE is apron** six metres outside the hole — 12ap's two worst pavement feet (`LEMDblast__b1` +7.18, `Terminal4sBlue-STRT4__b1` −5.08) were that fabricated ramp, and the anchor correction is 6.91 m. A simplex CROSSING a hole ring with a step over `split_tol_m` is struck and a point inside one reads the nearest vertex of that simplex ON ITS OWN SIDE of the ring; measured narrowings: "centroid on no face" struck 8,689 of 47,287 simplices and cost 421 files / 435 off-sheet bodies, and a strike with no side-aware read cost 160. (B) §17 is judged at the GROUND-CONTACT feet — the in-band feet within `split_tol_m` of the lowest (`placement_motion.ground_contact_feet`); `contact_band_m` is shared law and unchanged, BOTH sets are sampled and the wider reading prints beside the judged one so the report states its own attribution. (A) `bind_ground_m` (`[cockpit] visual_m`) bounds §16c (7): a FOOTED body of ANOTHER member keeps the cluster only while its own zero is within it of the senior's, else it keeps its own anchor and is counted — the report prints `bound refused for ground N` with the worst refused disagreement and the widest RETAINED cluster zero-plane span. Matched arms, LEMD main → branch: CRITICAL MOTION 6,640 → 5,400 feet on 407 → 356 bodies, over 0.5 m FLOATING 663 → 128 and BURIED 1,109 → 808 (of which (B) alone 581 → 128 / 816 → 808), worst pavement foot +7.18 → +2.41 m, 74 binds refused (worst 2.38 m), files 2,107 → 2,149, seams 0/0, round trip OK, plan stage 10.19 → 10.03 s; OTHH 3,891 → 2,822 feet on 103 → 74, floating 332 → 12, §14 footless at datum 5 → 4, files 1,252 → 1,269, plan stage 60.8 → 61.4 s (the ≤ 60 s bar missed on BOTH arms). §16b's carried-piece float and wide counts move the WRONG way at both airports (LEMD 111 → 119 / 967 → 983, OTHH 126 → 135 / 75 → 78) and are named. §16d (owner RULINGS 2026-09-13h, lane `v2unboxed`): THE PLAN BOXES WHAT THE WRITER WRITES — a WRITTEN-FRAME bar beside the torn seams, `§16d bodies with written geometry > 1 m outside their geom_box` (`airport/placement_seams.census_outside_box`, printed after `--write-pack` and by `--torn-seams`, bar 0): `geom_box` was the hull of the ADMITTED PARTS while the writer emitted the source object's triangles regardless, so a component no part named (the FS2XPlane origin plate, an exporter's ground paint, a roof plate over the next hangar) rode a zero the body chose elsewhere and NO instrument read it — LEMD 1.0.325 live pack 378 of 2,109 bodies, 8 over a kilometre. Every connected component the writer will emit — draped ones included — is now PLACED: within `coarsen_reach_m` of a ground group's part hull it joins that group and `geom_box` grows to the hull of what the file will contain; beyond it, it is a FOOTLESS BODY §15's search places, or §16 (3)'s own ground (`--coarsen-reach 0` disarms the reach and the component joins the nearest body, the pre-§16d reading). The nearest-footed fallback is CAPPED at the same reach (`carrier_refused_nearest_beyond_reach`), and the COCKPIT block names the worst row by the centre of the BODY'S OWN written geometry, never the placement row (a shared-datum pack puts 96.5 % of its bodies on two points). `plan stage: N.NN s` is printed after the split — the number a round's budget is quoted in, timed exactly where the shipped engine's own `build_splits` call is, without the graded parse or the census. Matched dry arms on the 1.0.325 LEMD frame (the app's own arm reads a MESH sampler where the tool reads a Delaunay over the graded vertices — the two disagree on every surface-driven refusal and the bars are read dry-to-dry): outside-box 390 → **0**, nearest-footed over 100 m 29 → **0**, the four shadow plates +15.94/+15.73/+5.77/+1.72 → **−5.00 on their own ground**, `Cargo-TEJ1` on `NEWCO__b9` roof base 604.95 (bar 0.3 of 605.04), seams 0/0, §15 carried float 0/0, round trip OK, files 2,141 → 2,279, LEMD plan stage 13.6 → 17.8 s and OTHH ≈83 → 86.1 s (both bars missed on BOTH arms, named). It also fixed a latent WRITER defect: the cut file was named by its index in the LIVE body list while the DSF row is written on the plan's `body_id` name, so a body the cut left with no triangle shifted every later body's file one name down (`OldTerminal_FSX-DCNEUN`'s `__b0` row held `b1`'s object). §16d (4)-(6) (owner RULINGS 2026-09-13m, same lane, second frame KCLT 1.0.324): a CARRIED body's components group BY CARRIER — each ATOM (§16c (1)'s, so a rigid cluster is never divided) asks its own carrier question BEFORE the search, counted as `carried bodies cut by ATOM`, where §16a (1)'s after-the-fact cut could only divide the answer the whole body got (KCLT 5,295 carried bodies left uncut against 3 cut; a native pack's master roof model spans 1,774 m); §16c (7)'s 0.5 m ground bound is MEMBER-AGNOSTIC (12ap tested `member != top.member`, and a native pack's one-model-per-material member spans the airport: KCLT's `005_ALB__b9` sank 5.04 m into its pad on a same-member bind to an apron body 500 m away); and a FOOTED body whose ground contacts lie mostly inside one emitted `building` pad reads only the contacts ON it (`anchor_rule.pad_majority`; the anchor reason then says `on pad <ref>`). Matched dry arms at KCLT: `005_ALB__b9` -5.85 -> **+0.02** against its pad, widest retained cluster zero span 5.69 -> **0.64 m**, 473 carried bodies divided by atom, 61 bodies anchored on their pad, `building80`'s on-pad zero spread 1.03 m (the pad's own relief 1.19), §16d outside-box **0**, §15 carried float **0**, round trip OK 477/477, one new torn seam (+0.16 m, one shared vertex, named), files 473 -> 477, plan stage 8.65 -> 8.3-8.5 s. It also exposed a defect the atom cut made visible: a target group holding BOTH a cut piece and an untouched raw was read for its `tris` alone, leaving 990-3,280 triangles per placement claimed by no body (9 of KCLT's 103) for `obj8_split` to hand to the nearest one — the audit reads 0 of 103 after. **COST: plan stage LEMD 17.8 -> 25-46 s and OTHH 86 -> 136 s** (KCLT flat) — the per-atom carrier search, narrowed by a `coarsen_reach_m` span gate, a 64-atom cap, per-atom pids and a set-intersection contact count, and still needing the owner's approval and a Fable-5 review before it ships. **§16g (5)'s PER-PLACEMENT ROW CENSUS, DRY (`--dsf-dump DUMP.text`, owner RULINGS 2026-09-14bo, lane `v2leafframe`).** The dry path reads no DSF by design; given an EXISTING DSFTool text dump it also prints the `OBJECT_MSL` seats the writer would emit, from the SAME `footprint_unit.msl_seats_for_dump` call `placement_write.build_plan` makes — the per-row base (`msl_base_unit_pad` / `msl_base_own_feet` / `msl_base_deck` / `msl_left_to_the_drape` / `msl_off_sheet_left_draped`), the multi-anchor census beside it, and `|elevation - the design surface at the row's own feet|` over 0.5 m with the worst named. PASS THE PRISTINE DUMP (`<dsf>.anchor_bak...text`, `dsf_write.pristine_dsf_path`): a dump of an ALREADY-WRITTEN pack reads the app's own absolute elevations back as authored offsets and reported 1,055 rows 22 m off their feet that do not exist. Measured at LEMD on the pristine dump: `OBJECT_MSL` rows **1,481 -> 0** (1,466 left to the drape, 196 standing on their unit's pad at offset 0, 5 off-sheet) — every LEMD multi-anchor row is a plain `OBJECT` with no authored offset, so the drape at its own feet IS the law's answer. Nothing is written and no DSF is decoded. Twin: `tests/auto_patch_v2/test_v2leafframe.py`. |

## Tool: site_read

| `Ortho4XP/tools/site_read.py` | You have a coordinate from an owner's sim read and the question is WHAT THE OBJECT STAGE MADE OF IT — not what the OSM patch says there (`osm_site.py`, the emitted ways) and not one law's defect count (`harness/census.py`). Three products of ONE build, read at ONE point in one process: the emitted DESIGN SURFACE's faces containing or near it (role, ref, side, z min/med/max, node count — a CONTAINING face reads 0.0 m, never the distance to its nearest vertex, which is `osm_site --at`'s own trap); the DSF ROWS standing on it (`OBJECT` / `OBJECT_MSL` / `OBJECT_AGL` with the resource and, where it has one, the written elevation — `None` for a plain `OBJECT`, never 0.0); and the PLAN BODIES whose plan box reaches it, each with its §6 class, its FOOTPRINT UNIT, its surface z and zero and the stage's own ANCHOR REASON verbatim, which is the line that says WHY a body is where the owner saw it. `--patch-dir DIR` resolves `<ICAO>.graded.json` and `o4_v2_placement_<ICAO>.json` by glob (an `obj8_split_report --json` dump works as `--plan`: the same `splits` records), `--dsf-dump` takes a DSFTool TEXT dump — pass the PRISTINE `<dsf>.anchor_bak...text` (`dsf_write.pristine_dsf_path`) when you want the pack as INSTALLED rather than as this repo last wrote it. `--show`, `--max`, `--json`. **It measures nothing and derives no law**: every value is read verbatim out of a product and nothing is written. Promoted 2026-09-14 (RULINGS `7e90032`, promote-on-reuse) from the scratchpad reader of the 14g HECA attribution, re-written for the 14bl LEMD one (scouts `v2heca331` / `v2lemd336o`) and used a THIRD time by lane `v2leafframe` — three copies of one question, already drifted in their hard-coded LEMD paths. Twin: `tests/auto_patch_v2/test_v2leafframe.py`. |

| `Ortho4XP/tools/arm_site_read.py` | The question is about a PLACE across two arms — "is the wall at 35.2077303,-80.9290869 still there, and did anything near it get worse?" — which an A/B leaves open: `census.py --rows-json` itemises rows and `census_rows_diff.py` joins two dumps class by class, but neither can be asked about a coordinate, and `osm_site.py` reads geometry without law rows or pad seats. This is the join: per named `--site`, per arm, the law-true rows within `--radius` with their worst grade and |de|; with `--seats`, the BUILDING PAD seats that moved between the arms — the channel this repo's HECA airside attribution ran through (a pad seat welds into the apron ring, so a seat that moves moves airside; measured 2026-08-12b: 92 of 215 pads, median 0.32 m, and building211's +0.88 m carried +203 apron rows). **It measures no law and counts no defects**: rows are read verbatim out of census `--rows-json` dumps and geometry/altitudes through the harness library's own `check_grade._parse_osm`, so this tool and the census read one file one way; a missing input reports SKIPPED, never zero. FRAMES, both printed: rows are located by the census's own row lat/lon, which for a within-shape pair is the PAIR's position (a 400 m apron chord's row sits far from either endpoint's geometry), so a radius selects rows near the PAIR, not shapes touching the site; seats join by the building's `ref` tag, never by way id or shapeID (both arm-dependent). Promoted 2026-08-12b from the service-corridor lane's `measure_arms.py` on its SECOND use — the named-site table and then the airside attribution. `--welds` (added 2026-08-12c, the corridor-joins round's ruling-4(a) instrument) answers the other question a place can be asked — IS THIS SEAM JOINED? Per site, per arm: the node ids SHARED between the road family (`check_grade._ROAD_FAMILY_ROLES`, read from the census library) and the airside ways, the max |Δalt| two ways carry at a shared node (0.00 is the construction — production values sit on the NODE, so a weld is single-valued; the delta is the torn-weld guard for way-valued rings), the NEAREST UNWELDED approach when nothing is shared (0.999 m at both KCLT mouths, against a 0.5 m weld tolerance), and the `retaining_wall` ways standing at the site with their ids. `--profile` / `--line` (added 2026-08-25, the HECA apron round-2 acceptance) answer the THIRD question a place can be asked — WHAT SHAPE IS THE SURFACE HERE? `--profile` walks every ring of `--profile-roles` (default `apron,graded_strip`) reaching a site and reports its worst consecutive EDGE and its RIPPLE AMPLITUDE, the peak-to-peak inside a 50 m run ALONG THE RING — the same window `apron_drape_read` calls `amp50`, so the two tools spell the ripple one way. `--line NAME=LAT,LON:LAT,LON` orders every emitted vertex in a corridor about an owner-named segment by its station along it, with the step between consecutive stations: the reading an acceptance written as "no unlawful step along the owner line" is stated in, AND the reading that shows a NODELESS VOID, because there an EMPTY STATION LIST IS ITSELF THE FINDING (a region with no emitted vertices contributes no census row however wrong its surface is — the blind spot `nodeless_interiors` counts). Neither prices a law; quote them ARM TO ARM on identical options, never as a verdict. Reach for it whenever an acceptance claim is about a join: **row absence cannot answer it** — a census row exists only between PAIRED geometry, so an unwelded road↔taxiway seam is silent in every census, which is exactly how two 1.0.244 acceptance claims passed over a gap no node could bridge. Twin: `tests/test_corridor_axis_coverage.py`.  **`--behind NAME=LAT,LON:LAT,LON` is the WALL scope** (added 2026-08-29, scorer-v2 round, spec `scorer-v2-class-boundary-spec.md`): the owner states a wall as two coordinates and asks that no airside pavement cross it — `--line` answers what the emitted elevation does ALONG it and `osm_site --line` answers what covers each station ON it, but neither answers the quantitative half, the SQUARE METRES of airside-role pavement sitting on the groundside, which is the number a boundary-cut round moves and therefore the number its acceptance is written in. Per crossing ring it reports the area behind, the node split either side and each side's altitude range — the shape of a wall buried inside one apron (HECA apron 584: 48 nodes at 97.22-104.69 m in front, 95 at 90.77-102.71 m behind). TWO FRAME RULES, both load-bearing: the band is the line's OWN SPAN by `--behind-depth-m` (default 150 m) deep, never a half-plane — unbounded, the far side sweeps in the whole airport and reports 634,371 m² where the local answer is 25,900 (measured at HECA); and the GROUNDSIDE side is decided by the patch — the side carrying less airside pavement — so reversing the two coordinates cannot change the answer and a caller cannot pick it. The closed-ring repeat is dropped before the node split (counting it double reports one extra node on whichever side the ring starts). It prices no law and counts no defects. **THE SEAT JOIN IS NOT FREE (2026-08-31, the buildings round).** `building{N}` is an ORDINAL identifier, so an arm that ADDS or DROPS a pad renumbers every later one and the ref join reports the RENUMBERING as seat motion: measured on the buildings-round HECA arms (pad count 175 -> 176) the ref join said 85 of 174 pads moved, median 2.72 m, max 33.65 m, where the population had barely moved. The tool now DETECTS it — a common ref whose pad centroid is more than `--seat-radius` (15 m) away is named as RENUMBERED, with the advice to re-run — and `--seat-join location` pairs pads by centroid instead (closest pair first, each pad used once; a pad with no partner within the radius is reported as added/dropped, NEVER as a move), which on the same arms reads 28 of 174 moved, median 0.07 m, max 2.32 m. Quote a pad-population round's seat movements under the location join. |

## Tool: role_overlap_read

| `Ortho4XP/tools/role_overlap_read.py` | The question is WHAT STANDS ON WHAT — *how many square metres of one emitted role/ref class lie on another class's footprint* — which is the single number a ruling of the form "the gap-fill spine must STOP at groundside pavement" (RULINGS 2026-08-30 ruling 4) is accepted or refused on. No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a face lying flat on a lot breaks no grade law and reports ZERO rows; `osm_site.py` answers one coordinate and `arm_site_read.py` one named place; `void_census.py` asks enclave TOPOLOGY; `lattice_overlap_read.py` asks CONTAINMENT of the two role-less membrane classes by LENGTH. This is the AREA sweep: `--over ROLE[:REF] --on ROLE[:REF],...` reports the populations, how many OVER ways stand on the ON union, the total m², and per stacked way its own area, the area over, the fraction and the ON shapes it stands on, largest first. **It measures no law and counts no defects** — geometry, the metre frame about the sidecar's own anchor and the role-carrying rings come from the harness library (`check_grade._parse_osm` / `_ll_to_m_factory`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. A patch with NO `.axes.json` sidecar is REFUSED (no anchor, no metre frame — an area in the wrong frame looks right and is not). `--min-area` (default 1.0 m²) is emit rounding, not a law threshold. Measured basis (HECA round 6b/6c): on the round-6b closing arm `graded_strip:gap_fill_spine` over `groundside_pavement` = 18 strips / 26,780 m², two faces carrying 24,288 m² of it (3190 over lot 2813 by 13,657 m², 70 %; 3192 over 2814 by 10,631 m², 63 %), while the same read over `service_road,service_junction` — 34 strips / 25,073 m² — said the annulus class was not one ruling's alone. Promoted 2026-08-30 from the HECA round-6b lane's scratchpad on its second use (RULINGS `7e90032`). `--pad M` grows the ON union before the read and `--beyond` reports the COMPLEMENT — the OVER ways that do NOT reach it, totalled and split by ref: the OWNERSHIP read RULINGS 31b is stated in ("within SERVICE_ROAD_PAVEMENT_NEAR_M of aircraft pavement"), which is how Batch 4a priced HECA's far road-family population off the merged-main control (`service_junction` beyond 25 m of the airside roles: 1,526 of 1,777 rings / 473,248 m², of which 1,325 ref-less / 435,882 m²). `--site LAT,LON` (repeatable) answers a named place in the OVER class's own terms — which way covers it, its ref and area, and the distance from both point and ring to the ON class. Several patches are reported separately — the arm-to-arm read; quote it on identical options. **`--contains` is the CONTAINMENT CENSUS and it is a DIFFERENT FRAME** (2026-09-13, lane `v2zonehole`, spec §41 (1)): the overlap sweep above is a SOLID-frame question and reads 0 m² here BY CONSTRUCTION — the arrangement is a partition, so a face enclosed by another sits in its HOLE and never overlaps its solid. `--contains` asks whether a pavement face lies inside another pavement face's EXTERIOR RING (`--min-frac`, default 0.95 = §41 (1)'s own floor, the one spelling of `planar.overlay.ENCLOSED_MIN_FRAC` outside the engine), and reports per row the inner face and its area, the host, the RING fraction, the SOLID fraction beside it (which is what says the two readings are not the same question), the shared-edge length and the distance to the host's solid — a face that TOUCHES its host is a NOTCH cut into a body (absorbed by `planar.overlay.absorb_enclosed_pavement`), one that does not is an ISLAND in the middle of a taxiway loop (left alone). Measured basis (the owner's 1.0.329 HECA patch): 39 of 370 pavement faces contained, 65,772 m², every one at solid fraction 0.000, 33 notches / 6 islands — `cross_connector:pav77` 896 m² in `primary_parallel:pav73` is the owner's dip site (RULINGS 2026-09-13co item 2). **THE ANCHOR REPAIR** (same lane): the read used to do `side["anchor"]` and died `KeyError: 'anchor'` on every v2 patch — v2's `SIDECAR_KEYS` publishes no anchor, deliberately, and the harness library itself falls back to the MEAN OF NODES, which is the frame the census reads the same patch in. The sidecar is still REQUIRED; the anchor is used when the patch carries one; the frame in force is printed on every report and carried in the JSON (`frame`). **`--slivers` and `--hole-rings` are the FOURTH and FIFTH questions, and both are WIDTH questions** (2026-09-14, lane `v2slivers`, spec §41 (4) / RULINGS 2026-09-14g items 4/5): the reads above ask what stands on, or inside, what — neither asks whether a shape is BIG ENOUGH TO CARRY LAW, which is what a zone strip that mints a hump and a hole ring that ships across a service road have in common. `--slivers` reports every `graded_strip` face under `--strip-min-area` (50 m², `emit.terrace.strip_min_m2`) or narrower than `--strip-min-width` (3.0 m, `strip_min_width_m`) with its area, inscribed width, elevation span and the pavement face it borders longest — the HOST `planar.overlay.dissolve_sliver_zones` unions it into. `--hole-rings` reports every emitted `gap_interior_ring` way with the fraction of its area the faces INSIDE it cover (`--cover-eps`, `emit.terrace.hole_cover_eps`), its inscribed width, and a verdict: `covered` (a duplicate ring), `hairline` (narrower than `strip_min_width_m`: it can carry no transition) or `void` (a real hole, which KEEPS its ring). THE WIDTH IS THE MAXIMUM INSCRIBED CIRCLE's DIAMETER, imported from the engine's own `planar.overlay.inscribed_width_m` and never re-spelled: `2 A / P` is a mean-width proxy and over-counted HECA's narrow zone faces 42 → 153 (the ruling's own measurement). Measured basis (the owner's 1.0.331 HECA patch, mean-of-nodes frame): 338 `graded_strip` faces / 2,895,389 m², of which 57 slivers / 1,647 m² (51 under 50 m², 42 under 3 m) — shape 1035 `adjacent_ground:taxi:E:zone1#38`, 15.7 m², 2.16 m, z 105.86–106.01 against a taxiway at 104.4, host `cross_connector:pav115`, the owner's hump (RULINGS 2026-09-14c item 4); and 57 `gap_interior_ring` rings / 926,251 m², 11 covered ≥ 98 %, 5 hairline, 41 real voids — way −10231, 29.5 m², 1.60 m wide, 92.3 % covered, the ring that shipped across `service_road:route4`. Both price no law and count no defects. Twin: `tests/test_role_overlap_read.py` (the area IS the intersection, the ROLE:REF selector is exact, the floor both ways, prices-no-law, the no-sidecar refusal, the `--pad`/`--beyond` complement, the `--site` read, the inscribed width agreeing with the engine's and the proxy disagreeing, the tool's three §41 (4) constants being the law table's, the sliver read naming the host, the hole read's cover fraction / width / three verdicts, the three reads refusing to run two at a time, and this index row) and `tests/auto_patch_v2/test_v2zonehole.py` (the anchor-less sidecar is not a crash, the containment census's ring-vs-solid frames, and that the two spellings of 0.95 agree). |

| `Ortho4XP/tools/role_overlap_read.py` | The question is WHAT STANDS ON WHAT — *how many square metres of one emitted role/ref class lie on another class's footprint* — which is the single number a ruling of the form "the gap-fill spine must STOP at groundside pavement" (RULINGS 2026-08-30 ruling 4) is accepted or refused on. No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a face lying flat on a lot breaks no grade law and reports ZERO rows; `osm_site.py` answers one coordinate and `arm_site_read.py` one named place; `void_census.py` asks enclave TOPOLOGY; `lattice_overlap_read.py` asks CONTAINMENT of the two role-less membrane classes by LENGTH. This is the AREA sweep: `--over ROLE[:REF] --on ROLE[:REF],...` reports the populations, how many OVER ways stand on the ON union, the total m², and per stacked way its own area, the area over, the fraction and the ON shapes it stands on, largest first. **It measures no law and counts no defects** — geometry, the metre frame about the sidecar's own anchor and the role-carrying rings come from the harness library (`check_grade._parse_osm` / `_ll_to_m_factory`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. A patch with NO `.axes.json` sidecar is REFUSED (no anchor, no metre frame — an area in the wrong frame looks right and is not). `--min-area` (default 1.0 m²) is emit rounding, not a law threshold. Measured basis (HECA round 6b/6c): on the round-6b closing arm `graded_strip:gap_fill_spine` over `groundside_pavement` = 18 strips / 26,780 m², two faces carrying 24,288 m² of it (3190 over lot 2813 by 13,657 m², 70 %; 3192 over 2814 by 10,631 m², 63 %), while the same read over `service_road,service_junction` — 34 strips / 25,073 m² — said the annulus class was not one ruling's alone. Promoted 2026-08-30 from the HECA round-6b lane's scratchpad on its second use (RULINGS `7e90032`). Several patches are reported separately — the arm-to-arm read; quote it on identical options. Twin: `tests/test_role_overlap_read.py` (the area IS the intersection, the ROLE:REF selector is exact, the floor both ways, prices-no-law, the no-sidecar refusal, and this index row). |

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N] [--why-hard-stage 1]` on either a `--replay` arm or a `--why-from PKL`; `--why-from PKL --probe-site LAT,LON [--probe-drop M] [--probe-arm TERM=V ...]`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (**and THE CLUSTERS beside the partition and the groups** — lane ``v2padjoin`` 2026-09-14: a capture without ``Airport.clusters`` leaves §30 (4)'s cluster pad, its apron reach and §16g (10)'s derived pads INERT in every replay of it, so a pads-ON arm silently measures the pads-OFF law; a capture predating them has them DERIVED at replay off its own partition, named on stdout) (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently).  **`--why-hard-stage 1`** reads §20b STAGE 1's OWN ASSEMBLY instead of the full problem's (`solve.design.stage_split`'s drop + fixed): the AIRSIDE hard set, in the rows and the metre scaling stage 1 enforced them under. The full read cannot answer "does the AIRSIDE solve settle" — the airside rows are a subset of 325k whose population and scaling the stage's own drop changes — and that is exactly the claim RULINGS 13y (B) / 13ab / 14as make (lane `v2settle`, which used it to split HECA's "42 unsettled rows" into 9 CONSTANT rows the solve can never move, 6 HELD runway rows at the projection's own bar, and 18 real ones).  The shipped surface is read either way: an airside vertex's z IS stage 1's, so the stage-1 read at the shipped z equals the read at stage 1's own surface (measured identical at HECA). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate).  **`--probe-site LAT,LON` IS THE STABILITY PROBE** (lane `v2qp`, spec §20c, promoted from lane `v2settle` r2's `scratchpad/v2settle/probe3.py`/`probe4.py` on its second use): off a `--solved-out` pickle, one extra `Band` ceiling `--probe-drop` (default 0.30) metres under the ARM's OWN base surface at the vertex nearest the point, re-solved, and the moved set (> 0.02 m) binned by distance from it — 0-40 / 40-100 / 100-250 / 250-500 / beyond, with the worst beyond 250 m, each arm's hard set and its exit line.  `--probe-arm TERM=V` repeated makes it a MATCHED PAIR of `[design]` arms on ONE problem (`--probe-arm solver=fixed_point --probe-arm solver=qp` is §20c's own bar); with none it probes the shipped law alone.  This is the instrument RULINGS 2026-09-14bw's headline was taken on (HECA: 959 vertices moved by one 0.30 m row, 953 beyond 500 m, ZERO within 100 m).  `--design-weight TERM=V` also takes a NON-NUMERIC value now (§20c's `solver=qp`); a value that does not parse as a float is passed through as the string.  Twin: `tests/auto_patch_v2/test_v2qp.py` (the probe as a fixture pair) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

## Tool: check_grade

| `Ortho4XP/tools/check_grade.py` | You want the grade validator's CLI on one patch, or its library from code. The CLI is a thin front end over the same law reader the census uses. A run with no sidecar is CONTEXT-FREE and overcounts — it is not a defect count. It also prints **THE COCKPIT BLOCK FIRST** (owner RULINGS 2026-09-12x/12y; §31 (6)) — the same `cockpit_block` / `cockpit_block_lines` the harness census and the pytest fixtures call, over the SAME run's `family_out` (the checks' own output is buffered and replayed under the block, never run twice). A `strip_seam_tear` row carries the PAIR MIDPOINT as its lat/lon (spec §32 (3), RULINGS 2026-09-12ag): it used to carry none, and `run_checks` filled it with the offending way's RING CENTROID — at LEMD that sent the cockpit block's first CRITICAL VISUAL find 220 m from the 8.25 m tear. Twinned both sides (`tests/auto_patch_v2/test_v2zoneclamp.py`), the engine's own `verify/strips.strip_seam_tear` alongside. The block's "in view by approach" test is the ONE approach corridor of `auto_patch_v2.law.approach_corridor` (RULINGS 2026-09-12al; twins `tests/auto_patch_v2/test_v2approachcorridor.py`), never a radius around a runway vertex. **`adjacent_ground_step`** (spec §34 (4), lane `v2rampwalk` 2026-09-13) is the WITHIN-FACE welded step on a v2 `adjacent_ground:*` face — the reading no family had: `graded_strip` carries no within-shape cap, `adjacent_ground_tear` fires only under a 1 m edge and `strip_seam_tear` is the CROSS-shape twin, so a band holding its designed level over a mapped road's own ground (LEMD `zone2#2`, 1.73 m over 1.5 m at road −6289) was priced by nothing. Its floor is the cockpit's own `visual_m` AND `cliff_grade` in one step: without the cliff term it counts the lawful hillside drape (measured CYXY 296 rows). Lockstep both sides — `auto_patch_v2.verify.strips.adjacent_ground_step` reads it in the engine; twins `tests/auto_patch_v2/test_v2rampwalk.py` and the v1/v2 census parity test. **`ramp_in_road`** (spec §34 (10), owner RULINGS 2026-09-14bb/14bc/14bd, lane `v2othhramp`) is the CRITICAL presence family the road margin needed: every ramp arriving at a road ends at the road's TRUE edge — the centreline offset by the road's own half-width toward the ramp, ONE derivation `planar/wall_corridor_ramps.road_true_edge` read by every ramp emitter — so a RAMP vertex standing INSIDE a road ribbon is a lane of carriageway cut away, whatever its elevation. No other family sees it: a ramp welded flat into the road it ate breaks no grade law and prices zero rows. A vertex within the census's own weld tolerance of the ribbon's edge is ON the edge, which is what the law asks for. It reads 0 at OTHH before and after — the family is the GUARD on that derivation and never a defect count. Twins: `tests/test_harness.py` §34 (10) (both directions, the weld line both ways, the register and the cockpit class, and the ramp-role set read from the law's own structure roles). **THE RUNWAY SHOULDER'S OWN CAP** (spec §40 (2) as amended, owner RULINGS 2026-09-13dd, lane `v2roles`): a within-shape pair BOTH of whose nodes lie beyond their runway's own half width is priced at `shoulder_transverse_max` (2.5 %, ICAO Annex 14 §3.2.4), not the runway's 1.5 % — a §40 (1) SHOULDER keeps the runway's DATUM, not its cross-fall. The line is the SOLVE's and is read, never re-derived: the sidecar's `runway_axes` (`[ref, lat_a, lon_a, lat_b, lon_b, half_m]` off the apt.dat ends and width) and `shoulder_transverse_max`, through `shoulder_nids` / `_shoulder_cap`. Fitting the width to the runway RINGS instead would read a shoulder as part of the runway and never find its own line. A patch with no key reads exactly as before. One reading with the generator and the v2 verify (`auto_patch_v2.law.tables.runway_transverse_cap`); twins `tests/auto_patch_v2/test_runway_shoulder.py`. |

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

## Registered frames: LEMD

LEMD  capture  base ec8723e9   lane v2roadcap        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/rw/cap/LEMD.pkl  — the v2roadcap-era LEMD capture used by scout v2unsettled2
LEMD  capture  base 864e7577   lane v2settle         2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle  — fresh main capture + per-law arms + logs (13ak)
LEMD  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/fin_LEMD/structures.json  — LEMD planar --stage structures on claude/v2gradecache vs the 0c86fe2c base arm in scratchpad/base_LEMD: every basin rim_ll/region_ll/floor_z/ramp_rings_ll/area/notes and every basin refusal BYTE-IDENTICAL; only covered_fraction moves 0.22750697->0.22750614 at the 1 cm plane quantum
LEMD  mesh     base 8fce79cb   lane v2hairline       2026-09-13T17:43:19  /tmp/harness/tile_v2hairline_arm3/Data+40-004.mesh  — §39 ARM: shore weld ON, metric split ON, vector weld OFF — sub-0.1 m2 in bbox 1,641, aspect p50 1.61, 2,734,780 tris
LEMD  patch    base df67b414   lane v2hairline       2026-09-13T17:43:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/control.osm  — §39 CONTROL patch (harness tag v2hairline_control) with shore_edges injected from the same TileWater witness — hairline_pair 29 adjudicated
LEMD  capture  base 32c78eaf   lane v2lemd329        2026-09-13T20:49:45  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/cap/LEMD.pkl  — fresh LEMD v2_solve_replay capture on main 32c78eaf (22158 vertices, 1119 faces, 353 s) — for the sunken-road round
LEMD  mesh     base 00d8b05c   lane v2hairline       2026-09-13T21:16:09  /tmp/harness/tile_v2hairline_r2cp/Data+40-004.mesh  — §39 round 2 FINAL arm: one witness + project + merge + crossing dedupe + 13cp z carry — 1,617 sub-0.1 m2 in bbox, aspect p50 1.65, 2,745,864 tris, pre-flight 7 UNMESHABLE (all non-patch markers)
LEMD  mesh     base 6b3a57cb   lane v2bankfoot       2026-09-13T21:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2bankfoot/fix/Data+40-004.mesh  — FIX ARM (13cp): bank rings CLOSED again, open runs wear PATCH_RING_MARKER, ribbon belt — annulus 39,105 of 58,555 valued, harmonic moved 491, isolated components 0, 111 closed bank_foot ways / 0 open; owner site 40.465414,-3.5531888 median 589.00 (1.0.329: 568.3); attr-8 nodes over 2 m = 3 of 275,861
LEMD  mesh     base 6b3a57cb   lane v2bankfoot       2026-09-13T21:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2bankfoot/omit/Data+40-004.mesh  — OMIT ARM (owner request): [design] bank_omit=true, NO bank_foot emitted — ribbons restored too (attr-8 over 2 m = 4), but patch edge step median 0.740 / p95 5.680 / >3 m 2,584 vs the fix arm's 0.415 / 4.944 / 1,924
LEMD  patch    base 05cf9282   lane v2leafframe      2026-09-14T21:43:48  /tmp/harness/v2leafframeLEMD.osm  — lane v2leafframe CLOSING LEMD patch build (claude/v2leafframe 443b5c0f, base main 05cf9282): rc 0, 786.0 s, body_sha c917d457d4c6, solve feasible, guard shared repo UNCHANGED (38 external-candidate Masks/OTHH deltas named, another lane's; no artifact-ledger key stored for that reason). THE FIRST frame carrying Part.height_m in ONE frame (RULINGS 2026-09-14bo): 29,684 parts 580-646 m -> 0.000-50.001 m, walled 29,684 -> 12,325. Unit census 22 units / 536 bodies-in-a-unit / largest 236 members spanning 2,855 m -> 20 / 206 / 84 members spanning 1,670 m. Items 2/4/6/9 all OUT of the giant units and on their own ground. Sec17 FLOATING 1305 -> 185, BURIED 2054 -> 1725, feet > 1 m 2427 -> 918. NEW: Sec15 carried float 0 -> 2.
LEMD  rebake   base 05cf9282   lane v2leafframe      2026-09-14T21:43:48  /tmp/harness/v2leafframeLEMD.v2/LEMD.rebake.json  — lane v2leafframe CLOSING LEMD patch build (claude/v2leafframe 443b5c0f, base main 05cf9282): rc 0, 786.0 s, body_sha c917d457d4c6, solve feasible, guard shared repo UNCHANGED (38 external-candidate Masks/OTHH deltas named, another lane's; no artifact-ledger key stored for that reason). THE FIRST frame carrying Part.height_m in ONE frame (RULINGS 2026-09-14bo): 29,684 parts 580-646 m -> 0.000-50.001 m, walled 29,684 -> 12,325. Unit census 22 units / 536 bodies-in-a-unit / largest 236 members spanning 2,855 m -> 20 / 206 / 84 members spanning 1,670 m. Items 2/4/6/9 all OUT of the giant units and on their own ground. Sec17 FLOATING 1305 -> 185, BURIED 2054 -> 1725, feet > 1 m 2427 -> 918. NEW: Sec15 carried float 0 -> 2.
LEMD  graded   base 05cf9282   lane v2leafframe      2026-09-14T21:43:48  /tmp/harness/v2leafframeLEMD.v2/LEMD.graded.json  — lane v2leafframe CLOSING LEMD patch build (claude/v2leafframe 443b5c0f, base main 05cf9282): rc 0, 786.0 s, body_sha c917d457d4c6, solve feasible, guard shared repo UNCHANGED (38 external-candidate Masks/OTHH deltas named, another lane's; no artifact-ledger key stored for that reason). THE FIRST frame carrying Part.height_m in ONE frame (RULINGS 2026-09-14bo): 29,684 parts 580-646 m -> 0.000-50.001 m, walled 29,684 -> 12,325. Unit census 22 units / 536 bodies-in-a-unit / largest 236 members spanning 2,855 m -> 20 / 206 / 84 members spanning 1,670 m. Items 2/4/6/9 all OUT of the giant units and on their own ground. Sec17 FLOATING 1305 -> 185, BURIED 2054 -> 1725, feet > 1 m 2427 -> 918. NEW: Sec15 carried float 0 -> 2.
LEMD  capture  base 05cf9282   lane v2leafframe      2026-09-14T21:43:49  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/leafframe  — DRY one-frame counterfactual arms for LEMD/HECA/KCLT/OTHH/SPJC: oneframe.py rewrites a registered rebake plan's Part.height_m to the authored component extent (the fix's own output, VERIFIED byte-equal to the built LEMD plan), obj8_split_report --json before/after beside each, unitcensus.py + sites.py readers, and the pristine-dump OBJECT_MSL censuses (mslp_b336.txt / mslp_built.txt: LEMD MSL rows 1,481 -> 0).
LEMD  patch    base 87bb9f38   lane v2lemdstruct     2026-09-14T21:49:27  /tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls/base/structures.json  — BASE dry 'planar --stage structures' at main 87bb9f38: bores 70 / mouths 90 / tunnels 50 / decks 11 / cells cut 3 / plate mouths 2 / basins 1; underpass -1230 clip 5.6 m centreline ribbon, 2 roads bored; basin:0 rim stations beyond 2.0 m = 58 of 69
LEMD  patch    base e5078016   lane v2lemdstruct     2026-09-14T21:49:27  /tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls/r3/structures.json  — AFTER dry 'planar --stage structures' on claude/v2lemdstruct e5078016 (RULINGS 14bp derivations 1/2/3/4): every count identical to the base bar decks 11 -> 7 (parallel carriageways grouped); underpass clip = the deck CELL across the axis, 772 m2, 2 roads bored; plate mouths CLAMPED (moved 0.9 / 0.1 m, -5931 mouths back at 40.4980351,-3.5850028 and 40.4960205,-3.5849927); basin rim-snap REFUTED (median 19.24 m to the at-grade contour, 11 of 68 within 2 m)
LEMD  patch    base e5078016   lane v2lemdstruct     2026-09-14T22:11:40  /Users/noah/XPTerrainBuilder/.claude/worktrees/v2lemdstruct/Ortho4XP/Patches/+40-010/+40-004/LEMD_auto.patch.osm  — CLOSING BUILD v2lemdstruct1 (build_airport.py LEMD --tile 40 -4), rc 0, 946.7 s (vector 874.3 + mesh 71.7), shared repo UNCHANGED, verify defects {}, solve feasible 146 rounds 395.5 s. Census vs the 1.0.336 tile patch: ADJUDICATED 2094 -> 1924, road_cross_section 14 -> 8, within_shape 3963 -> 3918, taxi_box 241 -> 178; COCKPIT motion 6 -> 4, visual 1184 -> 1181. Mesh at /tmp/harness/tile_v2lemdstruct1/Data+40-004.mesh
LEMD  mesh     base e5078016   lane v2lemdstruct     2026-09-14T22:11:40  /tmp/harness/tile_v2lemdstruct1/Data+40-004.mesh  — v2lemdstruct1 tile mesh: the bridge transect at lat 40.4835412 over lon -3.5812..-3.5788 reads 610.88 -> 606.15 -> 607.13 with NO station-to-station step over 0.5 m; the residual dip past the owner's east end 40.4835412,-3.5799114 is 0.73 m peak-to-trough (the 1.0.336 read was a 2.2 m notch)

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

