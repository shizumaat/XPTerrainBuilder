# Brief pack — lane `v2lemdstruct2`

Base: main `c689104d` · generated 2026-09-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

LEMD 15e items 5 + 7: mouth = bore datum, the road between mouths, the underpass covers the strip (§33 (5), §34 (11), §34 (5) (b))

## The brief

Owner 15e items 5 and 7 (LEMD 1.0.340). Sites: `planar/structure_approach.py` (`apply_plates`, the mouth floor), `planar/structure_underpass.py` (`underpass_bores`, the deck-cell clip §34 (5) (a) → extend to the strip), `planar/structures.py`, `constraints/roads.py` / `constraints/road_ramp.py` (§37 road rows), `classify/sources.py` + `emit/osm_adapter.py` (road admission; the pack's draped road net per 14bi), `planar/zones.py`, `tools/check_grade.py` (`ramp_in_strip`), `tools/role_overlap_read.py --hole-rings`. No capture exists for this build — make one (`v2_solve_replay --capture` on the harness LEMD build) and register it; the scout's numbers are in RULINGS 15h. Items 1/3/4/6 (walls as cut geometry) are NOT yours — a separate law is coming; do not touch `airport/wall_corridors.py` or `planar/wall_corridor_ramps.py` beyond what item 7 needs. Do not touch `solve/design*.py`.

## Bars

- Item 5 mouth 40.4947697, −3.5829037: floor = rim − `bore_datum_m` (5.10) ± 0.05 m (today 2.91 m under the rim).
- Item 5 road 40.494628, −3.5832911 → 40.4943869, −3.5823239: identified (way id or pack draped road named) and admitted as a road-family way; grade along it ≤ the road cap, profile smooth between the two mouths' ground levels; the ground at 40.4940268, −3.5826498 no longer pulled — the design surface there within 0.10 m of the road profile; the rows that lowered it today NAMED by `--why-at` on a fresh capture BEFORE the fix.
- Hole ring −10689 (144,429 m², cover 0.011): covered (cover ≥ 0.5) or excluded from the graded strip; count of `gap_interior_ring` rings > 10,000 m² at LEMD before → after.
- Item 7 taxiway 40.4611623, −3.5444804: no `tunnel_ramp` face vertex inside or touching the taxiway's strip (the `strip_transverse` band or zone 1); the trench mouth beyond the strip; the 5.38 m drop between the kerb node (577.80) and 15.5 m out → the strip's own surface (≤ the strip transverse cap); `ramp_in_strip` check registered in `LAW_FAMILIES` with its twin.
- Item 7 lateral slope: the transverse row (or its absence) at junction pav157's shared runway nodes named; the taxiway's transverse across the site ≤ 1.5 % after the fix, or the residual quoted with the owner's decision needed.
- Census by family matched replay pair at LEMD: no family worse by > 5 %; `tunnel_mouth_canonical` 31 → named; suite by FAILED lines (zero); ONE LEMD build as the closing test; `shared repo UNCHANGED`.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/planar/structure_approach.py`, `Ortho4XP/src/auto_patch_v2/planar/structure_underpass.py`, `Ortho4XP/src/auto_patch_v2/constraints/roads.py`, `Ortho4XP/tools/check_grade.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/airport/wall_corridors.py`, `Ortho4XP/src/auto_patch_v2/planar/wall_corridor_ramps.py`, `Ortho4XP/src/auto_patch_v2/solve/design.py`

## Spec (design-surface) §33 (5)

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

## Spec (design-surface) §34 (11)

## §34 (11) THE ROAD BETWEEN TWO MOUTHS IS A ROAD; A RIM NEVER PULLS THE GROUND BESIDE IT (Fable 2026-09-15; RULINGS 2026-09-15h) — lane `v2lemdstruct2`

Same site: between mouth 886 (599.25) and ramp 898 (603.32 at
40.4940268, −3.5826498) the owner names a road (40.494628, −3.5832911 →
40.4943869, −3.5823239) whose ground "is getting pulled down".  In the
patch that line is NOT a road: every station reads `cross_connector:
pav61` + `gap_interior_ring` + `graded_strip:adjacent_ground:taxi:F:
zone2`, no road-family way within 60 m, and the two ramps meet across
hole ring −10689 — **144,429 m², cover 0.011**, VOID at 40.4946503,
−3.5835473 — where no family owns a vertex.  RULED: (a) the lane
IDENTIFIES the road (an OSM `highway=*` way, or the pack's draped road
net — the source 14bi named for road width) and admits it as a road-
family way with §37 road rows: a smooth profile between the two mouths'
ground levels within the road cap, its zones per §37 (6); (b) a
`structure_rim` is a one-way CEILING on the ground it borders (the
ground may not rise above the rim's crest), never a pull — the ground
between two structures across an unowned void keeps the design surface;
(c) a `gap_interior_ring` of that size (> 10 × the largest lawful sliver,
§41) with cover < 0.5 is itself the defect at its VOID point: the layout
either covers it with faces of the owning roles or excludes it from the
graded strip.  The lane measures the pull first (`--why-at` on a fresh
capture) and names the rows that lowered the ground.

## Spec (design-surface) §34 (5)

### §34 (5) NARROWED — NO UNDERPASS UNDER A JETWAY; §29 (7) THE RUNWAY LATERAL BAND (Fable 2026-09-13; RULINGS 2026-09-13bm) — lane `v2spjc`

SPJC (owner 1.0.327, 13bi): `is_aeroway_bridge` admitted 63 `aeroway=jet_bridge`
footways and bored 86 apron roads under 49–127 m "decks" read off the apron
cell; the −641/−2525 trunk tunnel's south mouths were dropped 168 / 191 m off
the field while 192 m beside runway 16R/34L at mid-length.

- **§34 (5):** an underpass is bored only under an aeroway a taxiing aircraft
  uses (`aeroway in {taxiway, runway}`, `apron` where mapped as a bridge);
  never `jet_bridge` / `parking_position`, never `highway=footway`.
  `_deck_half_width` refuses a cell wider than 4× the way's carriageway and
  falls back to the carriageway; `is_bridge_way` excludes `jet_bridge` so no
  jetway mints a terrain deck.
7. **THE RUNWAY LATERAL BAND (§29).** The field region is the cover ⊕
   `mouth_standoff_m` ∪ the approach corridors ∪ each runway's axis ⊕
   `runway_view_half_width_m` (design: 250 m) — one derivation shared with
   the cockpit block. A bore with one mouth built has its sibling admitted
   under the same test. `mouth_standoff_m` stays 150.

BARS: SPJC underpasses 19 → taxiway-only (named); tunnels at the owner's four
points 0; the four jetway `bridge_deck:` faces gone; −641/−2525 south mouths
built at −12.0202431, −77.129278; LEMD −6028's mouth by the same rule (dry);
LEMD F-6 and KCLT taxiway U unchanged; ONE SPJC build; suite twice.

**WHAT LANDED.**  `planar/cluster.py` (NEW) derives the clusters from the
pack partition at LOAD, beside the groups (`pipeline/build.py`), and they
travel on `Airport.clusters` because `constraints` may not import `planar`
(the layering twin).  `constraints/cluster_pad.py` (NEW, beside
`pad_frontage_gs.py` and for the same 1,000-line reason) holds both rows:
`plane_groups` — the groups a pad PLANE is priced over, a cluster's faces
as ONE entry, read by `pads._pad_rows` (`pad_flats` + the hard 1 % ceiling)
and by `pads.pad_frontage_level` — and `cluster_apron_level`, the reach.
The derivation itself is `airport.placement_family.plan_clusters`, the same
`_clusters` law §16g binds the objects with, at the same
`[placement] footprint_touch_m`.

**THE FRAME.**  ONE KCLT build through the harness, tag
`v2clusterpadKCLT2`, rc 0, **477.2 s**, status feasible, `body_sha
9f056cce3dc3`, `[harness] shared repo UNCHANGED`.  It earned NO ledger
entry: the code tree moved between key time and store time (the §16g (4)
edit), so the artifact ledger refused the store — correctly.  The "before"
column is the registered `v2familyKCLTframe` graded document (base
`864e7577`), which is NOT a matched arm: the base moved a full day of main
between them.  **A matched design base arm was NOT built** and every design
number below carries that confound.

| bar | before (`v2familyKCLTframe` graded) | after (`v2clusterpadKCLT2`) |
|---|---|---|
| the cluster, named | — | `unit:31#0`, 19 members (`paredes_*`, `techos_*`, `suelos_interiores_charlotte`, `vidrios_*`), footprint union **378,982 m²**, on `building80` + `building91`; and `unit:30#0`, 17 members, 15,334 m² |
| the CLUSTER PAD's plane | `building80` 221.15 … 222.32 (spread 1.17), `building91` **217.89** — 4.43 m below it | `building80` 221.68 … 223.14, `building91` **222.27 … 222.28**; union spread **4.43 → 1.46 m** — MET in kind: the pad inside the terminal no longer sits 3.6 m under the terminal |
| `building80`'s own flatness | spread 1.17 m | **1.46 m** — WORSE by 0.29 m, and named: the plate now carries `building91`'s frontage and the reach beside its own |
| the apron within `cluster_apron_reach_m` (60 m) | 70 vertices, median \|apron − pad\| **0.26 m**, max 1.16, **0** within 0.05 m | 90 vertices, median **0.16 m**, max 1.77, **38 of 90 within 0.05 m** — the bar (≤ 0.05 m inside the reach) is MET for 38 and NOT for the rest; the residue is the feasibility clause and the taxi-catchment exclusion |
| the taxiway family | — | NOT measurable without a matched base build; what IS exact is that no taxi- or runway-family vertex is ever a FOLLOWER of a reach row, and no apron vertex nearer such a face than the pad is in the population at all (both twinned) |
| solve | — | feasible, 593 active-set rounds, 93/238,729 hard rows violated (max 0.0877 m), `pad_flat` verify rows 47, total 420.13 s |

**THE TAXI-CATCHMENT CLAUSE, AND WHAT MEASURED IT.**  On the twin fixture
the reach lifted an apron and the taxiway welded to it followed by **2.20 m**
through the apron's own no-step law — the reach's rows never touched a taxi
vertex.  Striking the band's own vertices is therefore not enough, and an
apron vertex nearer a taxi- or runway-family face than the cluster pad is
now excluded outright.  On the fixture that arm read **3.51 m** instead of
2.20 — WORSE — but the fixture's taxi face carries no datum of its own and
swings metres between arms, so it measures the fixture and not the law.  The
clause is KEPT because it can only ever SHRINK what the reach touches, and
it is named here as UNMEASURED at an airport.

### §34 (5) NARROWED — NO UNDERPASS UNDER A JETWAY; §29 (7) THE RUNWAY LATERAL BAND (Fable 2026-09-13; RULINGS 2026-09-13bm) — lane `v2spjc`

SPJC (owner 1.0.327, 13bi): `is_aeroway_bridge` admitted 63 `aeroway=jet_bridge`
footways and bored 86 apron roads under 49–127 m "decks" read off the apron
cell; the −641/−2525 trunk tunnel's south mouths were dropped 168 / 191 m off
the field while 192 m beside runway 16R/34L at mid-length.

- **§34 (5):** an underpass is bored only under an aeroway a taxiing aircraft
  uses (`aeroway in {taxiway, runway}`, `apron` where mapped as a bridge);
  never `jet_bridge` / `parking_position`, never `highway=footway`.
  `_deck_half_width` refuses a cell wider than 4× the way's carriageway and
  falls back to the carriageway; `is_bridge_way` excludes `jet_bridge` so no
  jetway mints a terrain deck.
7. **THE RUNWAY LATERAL BAND (§29).** The field region is the cover ⊕
   `mouth_standoff_m` ∪ the approach corridors ∪ each runway's axis ⊕
   `runway_view_half_width_m` (design: 250 m) — one derivation shared with
   the cockpit block. A bore with one mouth built has its sibling admitted
   under the same test. `mouth_standoff_m` stays 150.

BARS: SPJC underpasses 19 → taxiway-only (named); tunnels at the owner's four
points 0; the four jetway `bridge_deck:` faces gone; −641/−2525 south mouths
built at −12.0202431, −77.129278; LEMD −6028's mouth by the same rule (dry);
LEMD F-6 and KCLT taxiway U unchanged; ONE SPJC build; suite twice.

**WHAT LANDED.**  `planar/cluster.py` (NEW) derives the clusters from the
pack partition at LOAD, beside the groups (`pipeline/build.py`), and they
travel on `Airport.clusters` because `constraints` may not import `planar`
(the layering twin).  `constraints/cluster_pad.py` (NEW, beside
`pad_frontage_gs.py` and for the same 1,000-line reason) holds both rows:
`plane_groups` — the groups a pad PLANE is priced over, a cluster's faces
as ONE entry, read by `pads._pad_rows` (`pad_flats` + the hard 1 % ceiling)
and by `pads.pad_frontage_level` — and `cluster_apron_level`, the reach.
The derivation itself is `airport.placement_family.plan_clusters`, the same
`_clusters` law §16g binds the objects with, at the same
`[placement] footprint_touch_m`.

**THE FRAME.**  ONE KCLT build through the harness, tag
`v2clusterpadKCLT2`, rc 0, **477.2 s**, status feasible, `body_sha
9f056cce3dc3`, `[harness] shared repo UNCHANGED`.  It earned NO ledger
entry: the code tree moved between key time and store time (the §16g (4)
edit), so the artifact ledger refused the store — correctly.  The "before"
column is the registered `v2familyKCLTframe` graded document (base
`864e7577`), which is NOT a matched arm: the base moved a full day of main
between them.  **A matched design base arm was NOT built** and every design
number below carries that confound.

| bar | before (`v2familyKCLTframe` graded) | after (`v2clusterpadKCLT2`) |
|---|---|---|
| the cluster, named | — | `unit:31#0`, 19 members (`paredes_*`, `techos_*`, `suelos_interiores_charlotte`, `vidrios_*`), footprint union **378,982 m²**, on `building80` + `building91`; and `unit:30#0`, 17 members, 15,334 m² |
| the CLUSTER PAD's plane | `building80` 221.15 … 222.32 (spread 1.17), `building91` **217.89** — 4.43 m below it | `building80` 221.68 … 223.14, `building91` **222.27 … 222.28**; union spread **4.43 → 1.46 m** — MET in kind: the pad inside the terminal no longer sits 3.6 m under the terminal |
| `building80`'s own flatness | spread 1.17 m | **1.46 m** — WORSE by 0.29 m, and named: the plate now carries `building91`'s frontage and the reach beside its own |
| the apron within `cluster_apron_reach_m` (60 m) | 70 vertices, median \|apron − pad\| **0.26 m**, max 1.16, **0** within 0.05 m | 90 vertices, median **0.16 m**, max 1.77, **38 of 90 within 0.05 m** — the bar (≤ 0.05 m inside the reach) is MET for 38 and NOT for the rest; the residue is the feasibility clause and the taxi-catchment exclusion |
| the taxiway family | — | NOT measurable without a matched base build; what IS exact is that no taxi- or runway-family vertex is ever a FOLLOWER of a reach row, and no apron vertex nearer such a face than the pad is in the population at all (both twinned) |
| solve | — | feasible, 593 active-set rounds, 93/238,729 hard rows violated (max 0.0877 m), `pad_flat` verify rows 47, total 420.13 s |

**THE TAXI-CATCHMENT CLAUSE, AND WHAT MEASURED IT.**  On the twin fixture
the reach lifted an apron and the taxiway welded to it followed by **2.20 m**
through the apron's own no-step law — the reach's rows never touched a taxi
vertex.  Striking the band's own vertices is therefore not enough, and an
apron vertex nearer a taxi- or runway-family face than the cluster pad is
now excluded outright.  On the fixture that arm read **3.51 m** instead of
2.20 — WORSE — but the fixture's taxi face carries no datum of its own and
swings metres between arms, so it measures the fixture and not the law.  The
clause is KEPT because it can only ever SHRINK what the reach touches, and
it is named here as UNMEASURED at an airport.

### §34 (5) (a), §24 (1) (a), §33 (2) (a), §33 (4)/§34.5 (6) AMENDED — FOUR DERIVATIONS FROM THE LEMD 1.0.336 READ (Fable 2026-09-14; RULINGS 2026-09-14bp) — lane `v2lemdstruct`

1. §34 (5) (a) THE UNDERPASS CLIP IS THE DECK CELL'S: the bored road is
   clipped to the deck cell's own footprint eroded by `wall_gap_m +
   wall_band_width_m + grid`; the centreline-symmetric ribbon only where no
   cell states the deck; `_deck_half_width` reads the same derivation.
2. §24 (1) (a) THE RIM IS THE WALL: a rim station with at-grade shell
   geometry within `footprint_close_m` snaps onto the shell's outer face;
   the region boundary stands only where no wall exists; `_rim_open`'s
   count becomes the derivation's own report (stations off the shell).
3. §33 (2) (a) THE PLATE MOUTH IS CLAMPED TO THE COVERED EXTENT: the mouth
   moves to the plate end or the bore way's end, whichever is nearer the
   mapped mouth along the axis; width takeover and the approach walk as
   before.
4. §33 (4) / §34.5 (6) AMENDED: a mapped bridge way's deck spans THE WAY
   (`ln.buffer(wd/2)` over its full length), the end equality at each
   mapped end (the governed cell within `deck_end_reach_m`); decks of
   parallel bridge ways sharing a crossing are one group — one transverse
   plane, no rim sliver.  §34.5 (6)'s refusal is withdrawn.
BARS (LEMD, ONE build): F-6 mouth within 3 m of 40.4609913,−3.5445335,
`pav157` uncut north of it; basin:0 stations beyond 2 m of the shell 58 →
≤ 11; the 40.4988 mouths within 3 m of 40.4980461,−3.5850118 and of the
segment 40.4960195,−3.585058 → 40.4960167,−3.5849289; the deck ends within
3 m of 40.4835967,−3.580923 / 40.4835412,−3.5799114, one plane across both
carriageways, the profile past the east end monotone (no notch), no rim
sliver; `road_cross_section` / `within_shape` on the approaches before →
after; airside 0; verify defects {}; five-frame dry: tunnels / basins /
plate mouths / decks before → after named.

## §34 (5) (b) THE COVERED EXTENT OF AN UNDERPASS INCLUDES THE TAXIWAY'S STRIP (Fable 2026-09-15; RULINGS 2026-09-15h; 14bl item 1 residual) — lane `v2lemdstruct2`

LEMD taxiway 40.4611623, −3.5444804 (owner 15e item 7, screenshot 2):
§34 (5) (a) IS in force (the deck CELL's footprint, eroded 2.1 m, 772 m²
over 50 stations), and the trench now opens **12.8–15.5 m from the
pavement node**: ramp face 993 (`tunnel_ramp`, floor 572.42) against the
kerb at 577.80 — a **5.38 m** face inside `adjacent_ground:taxi:E:zone1`
with no bank (bank OFF) — the "hole".  The deck cell covers the
PAVEMENT only.  RULED: (a) the covered extent of an underpass beneath a
taxiway or runway spans the pavement AND its graded strip (the
`strip_transverse` band the law already prices, 165 rows at LEMD; the
zone-1 width where no strip is declared) — the mouth opens beyond the
strip, the ramp descends outside it, and the rim between is the strip's
own surface; (b) no `tunnel_ramp` face may share a vertex with, or lie
inside, the strip of the way it passes under (a `zone_on_pavement`-class
check, named `ramp_in_strip`).  The LATERAL slope is separate: junction
`pav157` (173 vertices, 566.31…580.14) shares its nodes with runway
face 5 at the site and reads 1.9 % over 18.2 m against the 1.5 %
taxiway cap; the lane names the transverse row (or its absence) that
permits it and whether the runway's cross-section is carrying the
junction's crown — the fix follows the measurement (§29 (7) lateral
band / §37 (10) taxiway contacts).

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

## Spec (design-surface) §37 (6)

### §37 (6) A GROUNDSIDE ROAD IS A RAMP FROM ITS AIRSIDE CONTACT TO THE DEM (Fable 2026-09-13; RULINGS 2026-09-13aj) — lane `v2roadramp`

Lane `v2roadcap2`: KCLT `dsf:pol51` (owner item 5) is held +13.24 m over the
DEM by NO row — `--why-at` on a pressure solve names zero binding rows; the
objective holds it, +9.71 m above its own `preferred_road_z` target (203.44),
welded by smoothness to the airside fill beside it (`graded_strip` 12.48 /
`building` 12.61 m off the DEM). A weight contest is not a law.

6. **THE ROAD'S PROFILE IS DERIVED ALONG ITS ROUTE.** From each AIRSIDE
   CONTACT of a groundside road (the mouth where it meets an apron, pad or
   lot; that level is the airside's — airside is king), the road target along
   route distance s is `max(DEM(s), z_contact − road_cap × s)`: it descends at
   the road cap until it meets the DEM and follows the DEM from there (and
   climbs at the cap where the DEM rises above the contact); between two
   contacts the two ramps meet at their higher envelope; a road with no
   airside contact targets the DEM. The target is a DESIGN TARGET (§31 (3)
   class, design-target weight — not the `preferred_road_z` soft fit, which
   this supersedes for groundside roads) with a HARD ceiling
   `z ≤ target + visual_m`, so smoothness can never lift the road back onto
   the fill. The road's own longitudinal cap (§37 (1)) and cross-section
   stand; the bank (§37 (3)) then daylights only the short fill at the
   contact. §34 (1) and §36 (5) are the same law for tunnel and EAT ramps.

Consumer census first (owner 2026-08-30l): every reader of `preferred_road_z`,
the road envelope / core clamp, `road_law_caps`, the mouth (§27), the bank's
load-bearing test, `road_terrain_conformance`.

BARS (KCLT, ONE build, base = 3e7dd382 with `--base-arm`): `dsf:pol51` follow
ratio 0.283 → ≥ 0.8 and within 2 m of the DEM over its chain (`--by-ref`);
no service road > 3 m off the DEM airport-wide (today 5 refs, worst +13.29);
`dsf:pol82` on its ground (+6.13 → ≤ 0.5); the east-edge bank shrinks with
the fill (`BankReport.line()`, load-bearing stations 421 → fewer, named);
cockpit CRITICAL motion ≤ 5 with no new east-road row; LEMD dry replay: the
61 apron-side lanes untouched (apron), every groundside road whose worst
off-DEM changes by > 0.5 m NAMED with its contact; CYXY control byte-identical
or named; solve settled lines quoted; suite twice.



#### §37 (6) CONSUMER CENSUS (owner RULINGS 2026-08-30l), completed BEFORE any consumer was edited — lane `v2roadramp`

**A. EVERY READER OF `preferred_road_z` / `PlanarMap.preferred_z`.**

| # | consumer | reads | RULE |
|---|---|---|---|
| P1 | `pipeline/build.py:499` (the only production caller) | `preferred_road_z` | **EDITED**: `with_road_ramp` runs LAST of the target channels (after the runway chord, the taxi trend, the apron trend), because a MOUTH's level is read from the airside's own published target where it carries one. It is the ONE superseding site. |
| P2 | `solve/design.py:295` — `road_fit` rows at `[design] road` (3) | `pm.preferred_z` | UNCHANGED CODE. A ramp-governed vertex is simply ABSENT, so it carries one target, not two in a weight contest (KCLT: `road_fit_vertices` 2,314 → 825). |
| P3 | `solve/why.py:362` — the "what holds this vertex" narrative | `pm.preferred_z.get(v)` | UNCHANGED. The ramp is ROWS (`Linear` + `Band`), so `why` names them as binding rows under the `road_ramp` generator instead of the "its design target" prose branch. |
| P4 | `constraints/taxi_trend.py:303` | `preferred_z` at a chain's RUNWAY pins | UNAFFECTED — only runway-contact vertices, never a road vertex; and it runs BEFORE the withdrawal. |
| P5 | `constraints/runway_chord.py:567-575` (merges the chord into `preferred_z`) | the mapping | UNAFFECTED — runway vertices are never road-owned, and it runs BEFORE the withdrawal. |
| P6 | `verify/roads.road_profile_agreement` ("roads vs core profile") | `pm.preferred_z` | **CHANGED IN MEANING, a report figure**: it now measures the roads the ramp does NOT govern (KCLT arm: 1,336 vertices, mean 0.310 m, max 3.940 m). The agreement with the core clamp is no longer the road's contract where §37 (6) supersedes it. |
| P7 | `model/planar.PlanarMap` | the target channels | **ADDED** `road_ramp_z`, beside `taxi_trend_z` / `apron_trend_z` (own channel, own weight). A capture pickled before it cannot be replayed — re-capture (the 12u rule). |
| P8 | `tools/v2_solve_replay.py::_targets` | the build's channel order | **EDITED** — publishes the ramp last, so a replay arm solves the build's problem. |
| P9 | `airport/road_profile.core_profiles` | the ways + the answer index | **EDITED, additive**: `RoadProfiles.per_face` now carries `core_profiles`' second return, so §37 (6) reads the SAME profiles `preferred_road_z` built (one construction per build, not two). |
| P10 | `tests/test_m3c_roads.py`, `test_v2smooth.py`, `test_v2padceiling.py` | `preferred_z` | UNAFFECTED — they do not run the publisher; all green. |

**B. THE ROAD ENVELOPE / THE CORE CLAMP, `road_law_caps`, THE MOUTH, THE BANK, THE INSTRUMENT.**

| # | consumer | RULE |
|---|---|---|
| C1 | the core clamp (`clamp_profile` = `O4_Vector_Utils.cap_lipschitz_profile`) | UNCHANGED. §37 (6) reads the ways' `dem`, not their clamped `z`: the RAMP is the profile, and the clamp stays the core's own answer for every road the ramp does not govern (P6) and for the core-levelled roads outside the patch. |
| C2 | `constraints/roads.road_law_caps` and every one of §37.1 A's L1–L17 | UNAFFECTED — §37 (6) neither reads nor writes the contiguity cap; §37 (1)'s longitudinal cap and the cross-section still shape the face. |
| C3 | §27 `airside_edge_flip` / `classify/roles` (THE MOUTH) | UNAFFECTED — the ramp reads its contacts from the planar weld (`roles_at`, an airside `role_side`), never from the flip. A face the flip makes an apron leaves the road population by role; `dsf:pol82`, which §37 (5) returned to `service_road`, is governed (fill +6.17 → +0.80 m). MEASURED: 0 apron-face vertices carry a ramp target at KCLT (78 apron faces), LEMD (159) or CYXY (16). |
| C4 | `emit/bank.py` `_inner` / `material_runs` (the load-bearing test) | UNCHANGED CODE — the bank is derived from the SOLVED surface, so it shrinks with the fill it daylighted (measured below). |
| C5 | `tools/road_terrain_conformance.py` (`--by-ref`, `--site`) | UNAFFECTED — it reads the emitted patch. It is the instrument both arms are read with. |
| C6 | `solve/design.is_hard` / `[design] hard_rulings` / `solve/project.py` | **EDITED, additive**: the ceiling's ruling head `roads.groundside_road ramp ceiling` is registered, so the ceiling is a CONSTRAINT of the active set (KCLT: hard rows 133,148 → 134,953 on the replay = +1,805, one per governed vertex). The runway and zone projections are untouched (they select their own families). |
| C7 | `planar/structures.py` decks (`bridge_deck:<way>`, role `service_road`) | **EXCLUDED FROM THE POPULATION** (`airport/road_ramp.deck_refs`, read off `pm.structures`, never off the ref string). A deck's level is STATED by the structure (§33 (4): tied to its two mapped ends, over the ramp's clearance). Without the exclusion the ramp pulled LEMD's decks to the terrain under the crossing: `bridge_deck:-3923` −4.72 m, `-3731` −4.20 m, KCLT `-3595` −2.84 m from their own profile — a hard ceiling against a structure's own datum. MEASURED after: every LEMD deck moves ≤ 0.02 m. **This scoping is not in §37 (6)'s text: it is the census's finding and wants Fable's ruling.** |

### §37 (6) **MEASURED** (lane `v2roadramp`, 2026-09-13, branch `claude/v2roadramp`, base `864e7577`)

ONE `--engine v2 --patch-only` KCLT build, tag **`v2roadramp`**, 426.5 s,
rc 0, `status feasible`, `body_sha 589f23c23ba1`, artifact ledger
**`497728ff051c`**, `[guard] shared repo UNCHANGED`.  The BASE is the
SHARED control `ctl-KCLT` (lane `v2seampinctl`, tree `c29238cd3fa8` =
main `864e7577`, ledger **`8e6288563291`**, `body_sha bb022a77f067`),
SERVED from the artifact ledger — no control was rebuilt.  Same corpus
`99f8ad879c83` on both arms.  Synthetic-first: two solve replays off one
KCLT capture (89 s) before the build, plus LEMD and CYXY replay pairs.

#### THE OWNER'S SITE — item 5, `dsf:pol51` (`road_terrain_conformance --site`, radius 60 m)

| | BASE `8e6288563291` | §37 (6) `497728ff051c` |
|---|---|---|
| chain span / DEM relief | 179.3 m / 12.15 m | (same chain) |
| emitted relief | 3.57 m | **10.41 m** |
| **FOLLOW RATIO** | **0.294** | **0.857** (bar ≥ 0.8 **MET**) |
| highest FILL | **+13.31 m** at 35.2074982,−80.9296586 | **+1.62 m** |
| deepest CUT | 0.86 m | **5.58 m** |
| \|emitted−DEM\| median / p95 | 0.43 / 10.54 m | 2.33 / 4.11 m |

The road no longer flies: the owner's coordinate reads **+13.31 → +1.62 m**
of fill and the chain rides the hill.  "Within 2 m of the DEM over its
chain" is **NOT met** — the residual is a CUT, attributed below.

#### AIRPORT-WIDE ROADS (`--by-ref`, both arms, same options)

| ref | BASE fill / cut | §37 (6) fill / cut |
|---|---|---|
| `dsf:pol51` | **+13.31** / 1.64 | +1.62 / **6.78** |
| `dsf:pol70` | +8.17 / −1.24 | +0.51 / 3.88 |
| `dsf:pol50` | +6.53 / 1.32 | +0.62 / 6.07 |
| `dsf:pol82` (item 7) | +6.17 / 1.41 | **+0.80** / 3.66 |
| `dsf:pol63` | +3.84 / 0.09 | under 2 m |
| `dsf:pol39` | +3.64 / 3.36 | +0.96 / 3.26 |
| `dsf:pol86` / `route19` / `route18` / `dsf:pol62` | +3.46 / +3.46 / +3.16 / +3.25 | all under 2 m |
| `bridge_deck:-3595` (EXCLUDED, C7) | +4.09 / 0.26 | +4.11 / 0.19 |

Whole population, 2,533 road vertices: \|emitted−DEM\| median **0.708 →
0.352 m**, p95 3.348 → 3.510, worst 4.17 → 6.78.  **Refs over 3 m of FILL:
9 → 1, and the one is the bridge deck the law excludes.**  Refs over 3 m
of CUT: 3 → 8.  The bar as written ("no service road > 3 m off the DEM";
base "5 refs, worst +13.29") is **NOT met on the |off-DEM| reading**: the
worst halves (13.31 → 6.78) and the FILL class is gone, the CUT class
grows.  `dsf:pol82` **+6.13/+6.17 → +0.80 m: MET.**

#### THE COCKPIT BLOCK (harness census, both patches)

| | BASE | §37 (6) |
|---|---|---|
| CRITICAL **motion** | **12** — worst 0.920 m over 59.87 m `strip_arc [runway|runway]` at 35.2239471,−80.9530979 | **8** — worst 0.620 m over 0.90 m `mid_edge_step [apron|apron]` at 35.2082082,−80.9412547 |
| CRITICAL **visual** | 0 | **0** |
| new row on the east road | — | **none** (every critical row is an apron/runway row, none within 500 m of the east access road) |

Motion 12 → 8 with the worst row 0.920 → 0.620 m; the bar (≤ 5) is NOT
met, and no critical row is a road row in either arm.

#### THE BANK (§37 (3)) — it shrinks with the fill

Arm build's `BankReport.line()`: 69 rings, 7,764 boundary vertices → **665
foot nodes**, LOAD-BEARING **342 / 2,430** stations (2,088 under the 1.65 m
floor; 27 rings carry no bank at all), 63 open chains, longest chord 30.0 m.
Read on the two PATCHES (the same geometry count on both arms): bank_foot
ways 72 → 69, foot nodes **776 → 671**; **within 300 m of the owner's
bank_foot coordinate 35.2077804,−80.928713: 89 → 61 nodes** (−31 %), now
in 12 short chains instead of 5 long ones.

#### THE CENSUS MOVED THE WRONG WAY, AND THE MECHANISM IS §37 (1)'s CHORD

| harness census | BASE | §37 (6) |
|---|---|---|
| LAW-TRUE | 11,809 | 17,030 |
| **ADJUDICATED** | **3,900** (airside 3,496 / gs 404) | **7,622** (airside 5,517 / gs 2,105) |
| `within_shape` | 8,934 | 11,540 |
| `road_cross_section` | 310 | **1,691** |
| `airside_no_step` | 718 | 1,374 |
| `transverse` | 114 | 470 |
| v2 verify `road_cross_section` | 763 | **5,263** |

ATTRIBUTION, measured on the capture before the build and not inferred:
**§37 (1) prices a road ring's pairs by their PLAN CHORD, and a road page
is not a plan chord.**  For every face carrying vertices over 3 m from
their ramp target, the face's own worst pair is one the within-shape /
cross-section law forbids the target to reach — and **7 of the 10 worst
are followable ALONG THE ROUTE at the road's own 8 % cap**:

| face | ref | worst pair | \|Δtarget\| | plan chord (cap) | ROUTE distance (8 % bound) |
|---|---|---|---|---|---|
| 827 | `dsf:pol51` | v16797–v16836 | 13.55 m | 45.6 m (long. 3.65 m) | **279.9 m (22.39 m) — followable** |
| 777 | `dsf:pol50` | v15699–v15740 | 10.07 m | 161.4 m (transv. 3.23 m) | **440.4 m (35.23 m) — followable** |
| 792 | `dsf:pol70` | v15484–v15955 | 7.66 m | 64.0 m (transv. 1.28 m) | **263.4 m — followable** |
| 764 | `dsf:pol53` | v15415–v15474 | 3.40 m | 22.3 m (transv. 0.45 m) | **575.8 m — followable** |
| 828 | `dsf:pol51` | v16797–v16791 | 13.30 m | 77.6 m (6.21 m) | 87.0 m (6.96 m) — steeper than the cap along the route too |

`dsf:pol51` is a HAIRPIN: two branches of one page 45 m apart in plan and
280 m apart along the road, with 13.6 m of terrain between them.  Before
§37 (6) both branches floated together on the airside fill and every pair
was satisfied; with the lower branch on its ground (a HARD ceiling) the
pair rows drag the upper branch down — `--why-at 35.2073045,−80.9301802`
on a pressure solve of the same LP names exactly two families holding it:
`road_within_shape` (4 rows, cap 8 % × 45.6 m = 3.65 m, chain terminal
v16797 at the §37 (6) ceiling) and `road_cross_section` (9 rows, cap 2 % ×
44.2 m).  **This is the withdrawn-chord law (owner 2026-09-05aa) stated
for the taxi family and NOT for the road family**, and it is why the cut
class grows and why `road_cross_section` reports 5,263 rows.  §37 (6)'s
brief says §37 (1) and the cross-section STAND, so this lane did not touch
them: it is the intent question below, with its numbers.

#### LEMD — dry read + a replay pair on one capture (239 s), base tree `864e7577` vs this branch

* **The 61 apron-side lanes are UNTOUCHED**: 0 of 159 apron faces carry a
  ramp target (the population is road-family faces by role; §27's flip is
  read, never re-derived — C3).
* LEMD's road faces are almost entirely BRIDGE DECKS: 13 decks, and after
  C7's exclusion only **6 groundside-road vertices** are governed, each
  within **0.02 m** of the DEM and of its core fit.
* Solved arms (`--solved-out`, same capture, base tree vs branch): whole
  surface max |arm − base| **1.231 m**, 44 vertices over 0.5 m; **no
  groundside road's worst off-DEM moves by more than 0.5 m** — the two that
  move at all are `route3` (worst 1.67 → 1.47 m, move 0.23 m) and `route6`
  (1.63 → 1.41, 0.22 m), both toward the DEM, both contacting the T4
  apron; every `bridge_deck:*` moves ≤ 0.02 m.  `service_road` max off-DEM
  9.31 m in BOTH arms (a deck).  The solve went `feasible` → `optimal`.

#### CYXY — the control, NOT byte-identical, named

Dry: 314 governed vertices, 34 mouths, and the target is within **0.01 m**
of the core clamp everywhere (one vertex, `route6`).  Replay pair on one
capture: whole surface max |arm − base| **1.378 m**, 63 vertices over
0.5 m; `service_road` max off-DEM **2.43 → 2.06 m** and vertices over
0.5 m **65 → 30**; apron 4.09 → 3.99; `graded_strip` 5.11 both.  Every
road ref moves TOWARD its ground: `dsf:pol120` 1.38 → 0.52, `pav29` 1.30 →
0.29, `pav0` 1.36 → 0.38, `pav30` 1.01 → 0.34, `dsf:pol121` 1.90 → 1.30,
`route13` 1.81 → 1.10.  The solve went `feasible` → `optimal`.

#### THE SOLVE'S SETTLED LINES

| | BASE (replay) | §37 (6) (replay) | §37 (6) (the build) |
|---|---|---|---|
| status | optimal | feasible | feasible |
| hard rows violated | 1 / 133,148 (max 0.0215 m) | **0 / 134,953 (max 0.0200 m, HARD SET SETTLED)** | 7 / 243,511 (max 0.0458 m, NOT SETTLED) |
| lag | NOT SETTLED, worst leader move 0.365 m | NOT SETTLED, 0.359 m | NOT SETTLED, 0.649 m |
| active-set | 717 rounds, settled | 567 rounds, SET NOT SETTLED (229 flips, worst 0.467 m) | 495 rounds, SET NOT SETTLED (403 flips, worst 0.048 m) |
| road ramp targets | — | — | 1,876 of 3,910 unmet, max 6.648 m |

The build's unsettled counters are KCLT's own standing instance of
RULINGS 2026-09-13y (B) / 13ab; the ramp adds 1,955 hard ceilings to it.

#### Build-time impact statement

The derivation is one Dijkstra over the road vertices plus one answer per
governed vertex, reading the road profiles `preferred_road_z` ALREADY
built (P9, so no second `core_profiles`): **1.4 s measured standalone at
KCLT including a cold `core_profiles`, and the profiles are shared in the
build**.  The solve carries 1,955 extra targets and 1,955 hard ceilings
(rows 62,804 → 73,115 on the replay, wall 85 → 68 s there; the build's
solve is 104.6 s).  Whole-build wall 426.5 s against the control's 463.3 s,
measured on a machine running other lanes — no A/B is claimed (standing
law: never one run per side).

#### The intent question (measured, for the owner / Fable)

**A ROAD PAGE IS PRICED BY ITS PLAN CHORD; A ROAD IS WALKED.**  Owner
2026-09-05aa withdrew the chord reading for the TAXI family ("the route
graph follows every curve; never a chord across open pavement"); the road
family still prices ALL PAIRS of a ring by plan distance, and the
cross-section cap (2 %) by plan DIRECTION against the ring's long axis.
On a hairpin or a page that follows a hillside, that forbids the road to
stand on the ground §37 (6) sends it to: 7 of the 10 worst pairs are
followable along the route at the road's own 8 % cap (table above), and
the price of holding them is `dsf:pol51` cut 6.78 m into its hill and
`road_cross_section` 763 → 5,263 verify rows.  Does the withdrawn-chord
law extend to the road family (a road pair priced over the ROUTE between
its stations, as §37 (6) prices the target), or does the road page keep
its plan-chord law and §37 (6) yield where the two disagree?

#### What this lane did NOT do

The five-airport sweep (the orchestrator's); any `--refresh-data`; any
merge into main; any RULINGS entry; any change to §37 (1)'s caps, the
cross-section, `road_law_caps`, the bank, §27's flip or anything in
`solve/`, `constraints/eat.py`, `planar/structures*.py`, `planar/zones.py`
or `constraints/structures.py` (the parallel lanes' files); a second KCLT
build (the attempt cap: two replay arms, then one build); a LEMD or CYXY
BUILD (both were read as replay pairs on one capture each, which is the
dry frame the brief asked for); a new tool, so no `tools/INDEX.md` row.

### §37 (6) AMENDED (decks out), §37 (7) A ROAD PAIR IS PRICED ALONG THE ROUTE (Fable 2026-09-13; RULINGS 2026-09-13av) — lane `v2roadramp` round 2

Lane v2roadramp (4172e698): the ramp works (KCLT `dsf:pol51` follow 0.29 →
0.86) but the census regressed 3,900 → 7,622: `road_within_shape` (8 % × a
45.6 m PLAN chord) and `road_cross_section` (2 % × 44.2 m) hold a hairpin's
upper branch to the lower branch's ceiling — the two branches are 280 m apart
along the road.

- **§37 (6) amended:** a `bridge_deck:*` face is OUT of the ramp population —
  its datum is §33 (4) (the deck end equals the pavement it connects to).
7. **A ROAD PAIR IS PRICED ALONG THE ROUTE.** The road's longitudinal rows
   (the 8 % cap, `road_within_shape`) pair vertices by ROUTE distance along
   the road's own centreline, never by plan chord (09-05aa's withdrawn chord;
   §34 (1)'s route-priced ramp). A cross-section pair is a pair ACROSS the
   road's width at ONE station; `road_cross_section` prices only those. Two
   branches of one road within a road width in plan (a switchback) are not a
   pair; the ground between them is adjacent ground (§19 / §31, terraced,
   visual only).

BARS (round 2, ONE KCLT build against the shared control `ctl-KCLT`):
`road_cross_section` 1,691 → ≤ 310; adjudicated ≤ 3,900; the ten worst pairs
named route-followable or transverse; `dsf:pol51` follow ≥ 0.85 holds;
`dsf:pol82` ≤ 0.5 m (today 0.80); cockpit CRITICAL motion ≤ 8, no road row;
LEMD / CYXY dry re-read; suite twice.

### §37 (6) AMENDED (the ramp's floor is the core clamp), §37 (9) THE COVERAGE-EDGE JOIN (Fable 2026-09-13; RULINGS 2026-09-13be) — lane `v2roadramp` round 3

Scout `roadlevel`: the core's `include_roads` levelling runs for every
airport-area way and is then REMOVED inside the patch coverage + 6 m
(`O4_Vector_Map.py:1749-1757`); inside the coverage the patch is the sole
road authority and v2 computes the core's clamp itself
(`airport/road_profile.py` → `cap_lipschitz_profile`). At KCLT's east road
the mesh shows the patch (214.24) over the core (203.48) and the DEM
(200.31); at the coverage edge the patch's kerb meets the core ribbon with a
2.36 m drop over 7.9 m.

- **§37 (6) amended — THE FLOOR IS THE CLAMP.** The ramp target is
  `max(clamp(s), z_contact − cap × s)` along the route, `clamp(s)` the
  in-process `cap_lipschitz_profile` value (`preferred_road_z`'s own
  profile): the road descends at the cap to the core's answer and follows
  it. Where the DEM is within the cap the two coincide; where it is not,
  the road takes the lift/cut the core would have given it.
9. **THE COVERAGE-EDGE JOIN.** A road-family face whose way leaves the
   coverage takes, at its last station inside, the core ribbon's altitude
   at the first station outside (the clamp value) as an EQUALITY; census
   family `road_coverage_join` prices the step (twin: a road exiting the
   coverage, step 0). Bar at KCLT way 10826 station 0: 2.36 m → ≤ 0.05 m in
   the patch.

BARS (round 3, with §37 (8)'s): as 13bb, plus `road_coverage_join` 0 on the
lane arm and > 0 on the control; the mesh confirmation of the join is the
app build's tile.

### §37 (6) A GROUNDSIDE ROAD IS A RAMP FROM ITS AIRSIDE CONTACT TO THE DEM (Fable 2026-09-13; RULINGS 2026-09-13aj) — lane `v2roadramp`

Lane `v2roadcap2`: KCLT `dsf:pol51` (owner item 5) is held +13.24 m over the
DEM by NO row — `--why-at` on a pressure solve names zero binding rows; the
objective holds it, +9.71 m above its own `preferred_road_z` target (203.44),
welded by smoothness to the airside fill beside it (`graded_strip` 12.48 /
`building` 12.61 m off the DEM). A weight contest is not a law.

6. **THE ROAD'S PROFILE IS DERIVED ALONG ITS ROUTE.** From each AIRSIDE
   CONTACT of a groundside road (the mouth where it meets an apron, pad or
   lot; that level is the airside's — airside is king), the road target along
   route distance s is `max(DEM(s), z_contact − road_cap × s)`: it descends at
   the road cap until it meets the DEM and follows the DEM from there (and
   climbs at the cap where the DEM rises above the contact); between two
   contacts the two ramps meet at their higher envelope; a road with no
   airside contact targets the DEM. The target is a DESIGN TARGET (§31 (3)
   class, design-target weight — not the `preferred_road_z` soft fit, which
   this supersedes for groundside roads) with a HARD ceiling
   `z ≤ target + visual_m`, so smoothness can never lift the road back onto
   the fill. The road's own longitudinal cap (§37 (1)) and cross-section
   stand; the bank (§37 (3)) then daylights only the short fill at the
   contact. §34 (1) and §36 (5) are the same law for tunnel and EAT ramps.

Consumer census first (owner 2026-08-30l): every reader of `preferred_road_z`,
the road envelope / core clamp, `road_law_caps`, the mouth (§27), the bank's
load-bearing test, `road_terrain_conformance`.

BARS (KCLT, ONE build, base = 3e7dd382 with `--base-arm`): `dsf:pol51` follow
ratio 0.283 → ≥ 0.8 and within 2 m of the DEM over its chain (`--by-ref`);
no service road > 3 m off the DEM airport-wide (today 5 refs, worst +13.29);
`dsf:pol82` on its ground (+6.13 → ≤ 0.5); the east-edge bank shrinks with
the fill (`BankReport.line()`, load-bearing stations 421 → fewer, named);
cockpit CRITICAL motion ≤ 5 with no new east-road row; LEMD dry replay: the
61 apron-side lanes untouched (apron), every groundside road whose worst
off-DEM changes by > 0.5 m NAMED with its contact; CYXY control byte-identical
or named; solve settled lines quoted; suite twice.



#### §37 (6) CONSUMER CENSUS (owner RULINGS 2026-08-30l), completed BEFORE any consumer was edited — lane `v2roadramp`

**A. EVERY READER OF `preferred_road_z` / `PlanarMap.preferred_z`.**

| # | consumer | reads | RULE |
|---|---|---|---|
| P1 | `pipeline/build.py:499` (the only production caller) | `preferred_road_z` | **EDITED**: `with_road_ramp` runs LAST of the target channels (after the runway chord, the taxi trend, the apron trend), because a MOUTH's level is read from the airside's own published target where it carries one. It is the ONE superseding site. |
| P2 | `solve/design.py:295` — `road_fit` rows at `[design] road` (3) | `pm.preferred_z` | UNCHANGED CODE. A ramp-governed vertex is simply ABSENT, so it carries one target, not two in a weight contest (KCLT: `road_fit_vertices` 2,314 → 825). |
| P3 | `solve/why.py:362` — the "what holds this vertex" narrative | `pm.preferred_z.get(v)` | UNCHANGED. The ramp is ROWS (`Linear` + `Band`), so `why` names them as binding rows under the `road_ramp` generator instead of the "its design target" prose branch. |
| P4 | `constraints/taxi_trend.py:303` | `preferred_z` at a chain's RUNWAY pins | UNAFFECTED — only runway-contact vertices, never a road vertex; and it runs BEFORE the withdrawal. |
| P5 | `constraints/runway_chord.py:567-575` (merges the chord into `preferred_z`) | the mapping | UNAFFECTED — runway vertices are never road-owned, and it runs BEFORE the withdrawal. |
| P6 | `verify/roads.road_profile_agreement` ("roads vs core profile") | `pm.preferred_z` | **CHANGED IN MEANING, a report figure**: it now measures the roads the ramp does NOT govern (KCLT arm: 1,336 vertices, mean 0.310 m, max 3.940 m). The agreement with the core clamp is no longer the road's contract where §37 (6) supersedes it. |
| P7 | `model/planar.PlanarMap` | the target channels | **ADDED** `road_ramp_z`, beside `taxi_trend_z` / `apron_trend_z` (own channel, own weight). A capture pickled before it cannot be replayed — re-capture (the 12u rule). |
| P8 | `tools/v2_solve_replay.py::_targets` | the build's channel order | **EDITED** — publishes the ramp last, so a replay arm solves the build's problem. |
| P9 | `airport/road_profile.core_profiles` | the ways + the answer index | **EDITED, additive**: `RoadProfiles.per_face` now carries `core_profiles`' second return, so §37 (6) reads the SAME profiles `preferred_road_z` built (one construction per build, not two). |
| P10 | `tests/test_m3c_roads.py`, `test_v2smooth.py`, `test_v2padceiling.py` | `preferred_z` | UNAFFECTED — they do not run the publisher; all green. |

**B. THE ROAD ENVELOPE / THE CORE CLAMP, `road_law_caps`, THE MOUTH, THE BANK, THE INSTRUMENT.**

| # | consumer | RULE |
|---|---|---|
| C1 | the core clamp (`clamp_profile` = `O4_Vector_Utils.cap_lipschitz_profile`) | UNCHANGED. §37 (6) reads the ways' `dem`, not their clamped `z`: the RAMP is the profile, and the clamp stays the core's own answer for every road the ramp does not govern (P6) and for the core-levelled roads outside the patch. |
| C2 | `constraints/roads.road_law_caps` and every one of §37.1 A's L1–L17 | UNAFFECTED — §37 (6) neither reads nor writes the contiguity cap; §37 (1)'s longitudinal cap and the cross-section still shape the face. |
| C3 | §27 `airside_edge_flip` / `classify/roles` (THE MOUTH) | UNAFFECTED — the ramp reads its contacts from the planar weld (`roles_at`, an airside `role_side`), never from the flip. A face the flip makes an apron leaves the road population by role; `dsf:pol82`, which §37 (5) returned to `service_road`, is governed (fill +6.17 → +0.80 m). MEASURED: 0 apron-face vertices carry a ramp target at KCLT (78 apron faces), LEMD (159) or CYXY (16). |
| C4 | `emit/bank.py` `_inner` / `material_runs` (the load-bearing test) | UNCHANGED CODE — the bank is derived from the SOLVED surface, so it shrinks with the fill it daylighted (measured below). |
| C5 | `tools/road_terrain_conformance.py` (`--by-ref`, `--site`) | UNAFFECTED — it reads the emitted patch. It is the instrument both arms are read with. |
| C6 | `solve/design.is_hard` / `[design] hard_rulings` / `solve/project.py` | **EDITED, additive**: the ceiling's ruling head `roads.groundside_road ramp ceiling` is registered, so the ceiling is a CONSTRAINT of the active set (KCLT: hard rows 133,148 → 134,953 on the replay = +1,805, one per governed vertex). The runway and zone projections are untouched (they select their own families). |
| C7 | `planar/structures.py` decks (`bridge_deck:<way>`, role `service_road`) | **EXCLUDED FROM THE POPULATION** (`airport/road_ramp.deck_refs`, read off `pm.structures`, never off the ref string). A deck's level is STATED by the structure (§33 (4): tied to its two mapped ends, over the ramp's clearance). Without the exclusion the ramp pulled LEMD's decks to the terrain under the crossing: `bridge_deck:-3923` −4.72 m, `-3731` −4.20 m, KCLT `-3595` −2.84 m from their own profile — a hard ceiling against a structure's own datum. MEASURED after: every LEMD deck moves ≤ 0.02 m. **This scoping is not in §37 (6)'s text: it is the census's finding and wants Fable's ruling.** |

### §37 (6) **MEASURED** (lane `v2roadramp`, 2026-09-13, branch `claude/v2roadramp`, base `864e7577`)

ONE `--engine v2 --patch-only` KCLT build, tag **`v2roadramp`**, 426.5 s,
rc 0, `status feasible`, `body_sha 589f23c23ba1`, artifact ledger
**`497728ff051c`**, `[guard] shared repo UNCHANGED`.  The BASE is the
SHARED control `ctl-KCLT` (lane `v2seampinctl`, tree `c29238cd3fa8` =
main `864e7577`, ledger **`8e6288563291`**, `body_sha bb022a77f067`),
SERVED from the artifact ledger — no control was rebuilt.  Same corpus
`99f8ad879c83` on both arms.  Synthetic-first: two solve replays off one
KCLT capture (89 s) before the build, plus LEMD and CYXY replay pairs.

#### THE OWNER'S SITE — item 5, `dsf:pol51` (`road_terrain_conformance --site`, radius 60 m)

| | BASE `8e6288563291` | §37 (6) `497728ff051c` |
|---|---|---|
| chain span / DEM relief | 179.3 m / 12.15 m | (same chain) |
| emitted relief | 3.57 m | **10.41 m** |
| **FOLLOW RATIO** | **0.294** | **0.857** (bar ≥ 0.8 **MET**) |
| highest FILL | **+13.31 m** at 35.2074982,−80.9296586 | **+1.62 m** |
| deepest CUT | 0.86 m | **5.58 m** |
| \|emitted−DEM\| median / p95 | 0.43 / 10.54 m | 2.33 / 4.11 m |

The road no longer flies: the owner's coordinate reads **+13.31 → +1.62 m**
of fill and the chain rides the hill.  "Within 2 m of the DEM over its
chain" is **NOT met** — the residual is a CUT, attributed below.

#### AIRPORT-WIDE ROADS (`--by-ref`, both arms, same options)

| ref | BASE fill / cut | §37 (6) fill / cut |
|---|---|---|
| `dsf:pol51` | **+13.31** / 1.64 | +1.62 / **6.78** |
| `dsf:pol70` | +8.17 / −1.24 | +0.51 / 3.88 |
| `dsf:pol50` | +6.53 / 1.32 | +0.62 / 6.07 |
| `dsf:pol82` (item 7) | +6.17 / 1.41 | **+0.80** / 3.66 |
| `dsf:pol63` | +3.84 / 0.09 | under 2 m |
| `dsf:pol39` | +3.64 / 3.36 | +0.96 / 3.26 |
| `dsf:pol86` / `route19` / `route18` / `dsf:pol62` | +3.46 / +3.46 / +3.16 / +3.25 | all under 2 m |
| `bridge_deck:-3595` (EXCLUDED, C7) | +4.09 / 0.26 | +4.11 / 0.19 |

Whole population, 2,533 road vertices: \|emitted−DEM\| median **0.708 →
0.352 m**, p95 3.348 → 3.510, worst 4.17 → 6.78.  **Refs over 3 m of FILL:
9 → 1, and the one is the bridge deck the law excludes.**  Refs over 3 m
of CUT: 3 → 8.  The bar as written ("no service road > 3 m off the DEM";
base "5 refs, worst +13.29") is **NOT met on the |off-DEM| reading**: the
worst halves (13.31 → 6.78) and the FILL class is gone, the CUT class
grows.  `dsf:pol82` **+6.13/+6.17 → +0.80 m: MET.**

#### THE COCKPIT BLOCK (harness census, both patches)

| | BASE | §37 (6) |
|---|---|---|
| CRITICAL **motion** | **12** — worst 0.920 m over 59.87 m `strip_arc [runway|runway]` at 35.2239471,−80.9530979 | **8** — worst 0.620 m over 0.90 m `mid_edge_step [apron|apron]` at 35.2082082,−80.9412547 |
| CRITICAL **visual** | 0 | **0** |
| new row on the east road | — | **none** (every critical row is an apron/runway row, none within 500 m of the east access road) |

Motion 12 → 8 with the worst row 0.920 → 0.620 m; the bar (≤ 5) is NOT
met, and no critical row is a road row in either arm.

#### THE BANK (§37 (3)) — it shrinks with the fill

Arm build's `BankReport.line()`: 69 rings, 7,764 boundary vertices → **665
foot nodes**, LOAD-BEARING **342 / 2,430** stations (2,088 under the 1.65 m
floor; 27 rings carry no bank at all), 63 open chains, longest chord 30.0 m.
Read on the two PATCHES (the same geometry count on both arms): bank_foot
ways 72 → 69, foot nodes **776 → 671**; **within 300 m of the owner's
bank_foot coordinate 35.2077804,−80.928713: 89 → 61 nodes** (−31 %), now
in 12 short chains instead of 5 long ones.

#### THE CENSUS MOVED THE WRONG WAY, AND THE MECHANISM IS §37 (1)'s CHORD

| harness census | BASE | §37 (6) |
|---|---|---|
| LAW-TRUE | 11,809 | 17,030 |
| **ADJUDICATED** | **3,900** (airside 3,496 / gs 404) | **7,622** (airside 5,517 / gs 2,105) |
| `within_shape` | 8,934 | 11,540 |
| `road_cross_section` | 310 | **1,691** |
| `airside_no_step` | 718 | 1,374 |
| `transverse` | 114 | 470 |
| v2 verify `road_cross_section` | 763 | **5,263** |

ATTRIBUTION, measured on the capture before the build and not inferred:
**§37 (1) prices a road ring's pairs by their PLAN CHORD, and a road page
is not a plan chord.**  For every face carrying vertices over 3 m from
their ramp target, the face's own worst pair is one the within-shape /
cross-section law forbids the target to reach — and **7 of the 10 worst
are followable ALONG THE ROUTE at the road's own 8 % cap**:

| face | ref | worst pair | \|Δtarget\| | plan chord (cap) | ROUTE distance (8 % bound) |
|---|---|---|---|---|---|
| 827 | `dsf:pol51` | v16797–v16836 | 13.55 m | 45.6 m (long. 3.65 m) | **279.9 m (22.39 m) — followable** |
| 777 | `dsf:pol50` | v15699–v15740 | 10.07 m | 161.4 m (transv. 3.23 m) | **440.4 m (35.23 m) — followable** |
| 792 | `dsf:pol70` | v15484–v15955 | 7.66 m | 64.0 m (transv. 1.28 m) | **263.4 m — followable** |
| 764 | `dsf:pol53` | v15415–v15474 | 3.40 m | 22.3 m (transv. 0.45 m) | **575.8 m — followable** |
| 828 | `dsf:pol51` | v16797–v16791 | 13.30 m | 77.6 m (6.21 m) | 87.0 m (6.96 m) — steeper than the cap along the route too |

`dsf:pol51` is a HAIRPIN: two branches of one page 45 m apart in plan and
280 m apart along the road, with 13.6 m of terrain between them.  Before
§37 (6) both branches floated together on the airside fill and every pair
was satisfied; with the lower branch on its ground (a HARD ceiling) the
pair rows drag the upper branch down — `--why-at 35.2073045,−80.9301802`
on a pressure solve of the same LP names exactly two families holding it:
`road_within_shape` (4 rows, cap 8 % × 45.6 m = 3.65 m, chain terminal
v16797 at the §37 (6) ceiling) and `road_cross_section` (9 rows, cap 2 % ×
44.2 m).  **This is the withdrawn-chord law (owner 2026-09-05aa) stated
for the taxi family and NOT for the road family**, and it is why the cut
class grows and why `road_cross_section` reports 5,263 rows.  §37 (6)'s
brief says §37 (1) and the cross-section STAND, so this lane did not touch
them: it is the intent question below, with its numbers.

#### LEMD — dry read + a replay pair on one capture (239 s), base tree `864e7577` vs this branch

* **The 61 apron-side lanes are UNTOUCHED**: 0 of 159 apron faces carry a
  ramp target (the population is road-family faces by role; §27's flip is
  read, never re-derived — C3).
* LEMD's road faces are almost entirely BRIDGE DECKS: 13 decks, and after
  C7's exclusion only **6 groundside-road vertices** are governed, each
  within **0.02 m** of the DEM and of its core fit.
* Solved arms (`--solved-out`, same capture, base tree vs branch): whole
  surface max |arm − base| **1.231 m**, 44 vertices over 0.5 m; **no
  groundside road's worst off-DEM moves by more than 0.5 m** — the two that
  move at all are `route3` (worst 1.67 → 1.47 m, move 0.23 m) and `route6`
  (1.63 → 1.41, 0.22 m), both toward the DEM, both contacting the T4
  apron; every `bridge_deck:*` moves ≤ 0.02 m.  `service_road` max off-DEM
  9.31 m in BOTH arms (a deck).  The solve went `feasible` → `optimal`.

#### CYXY — the control, NOT byte-identical, named

Dry: 314 governed vertices, 34 mouths, and the target is within **0.01 m**
of the core clamp everywhere (one vertex, `route6`).  Replay pair on one
capture: whole surface max |arm − base| **1.378 m**, 63 vertices over
0.5 m; `service_road` max off-DEM **2.43 → 2.06 m** and vertices over
0.5 m **65 → 30**; apron 4.09 → 3.99; `graded_strip` 5.11 both.  Every
road ref moves TOWARD its ground: `dsf:pol120` 1.38 → 0.52, `pav29` 1.30 →
0.29, `pav0` 1.36 → 0.38, `pav30` 1.01 → 0.34, `dsf:pol121` 1.90 → 1.30,
`route13` 1.81 → 1.10.  The solve went `feasible` → `optimal`.

#### THE SOLVE'S SETTLED LINES

| | BASE (replay) | §37 (6) (replay) | §37 (6) (the build) |
|---|---|---|---|
| status | optimal | feasible | feasible |
| hard rows violated | 1 / 133,148 (max 0.0215 m) | **0 / 134,953 (max 0.0200 m, HARD SET SETTLED)** | 7 / 243,511 (max 0.0458 m, NOT SETTLED) |
| lag | NOT SETTLED, worst leader move 0.365 m | NOT SETTLED, 0.359 m | NOT SETTLED, 0.649 m |
| active-set | 717 rounds, settled | 567 rounds, SET NOT SETTLED (229 flips, worst 0.467 m) | 495 rounds, SET NOT SETTLED (403 flips, worst 0.048 m) |
| road ramp targets | — | — | 1,876 of 3,910 unmet, max 6.648 m |

The build's unsettled counters are KCLT's own standing instance of
RULINGS 2026-09-13y (B) / 13ab; the ramp adds 1,955 hard ceilings to it.

#### Build-time impact statement

The derivation is one Dijkstra over the road vertices plus one answer per
governed vertex, reading the road profiles `preferred_road_z` ALREADY
built (P9, so no second `core_profiles`): **1.4 s measured standalone at
KCLT including a cold `core_profiles`, and the profiles are shared in the
build**.  The solve carries 1,955 extra targets and 1,955 hard ceilings
(rows 62,804 → 73,115 on the replay, wall 85 → 68 s there; the build's
solve is 104.6 s).  Whole-build wall 426.5 s against the control's 463.3 s,
measured on a machine running other lanes — no A/B is claimed (standing
law: never one run per side).

#### The intent question (measured, for the owner / Fable)

**A ROAD PAGE IS PRICED BY ITS PLAN CHORD; A ROAD IS WALKED.**  Owner
2026-09-05aa withdrew the chord reading for the TAXI family ("the route
graph follows every curve; never a chord across open pavement"); the road
family still prices ALL PAIRS of a ring by plan distance, and the
cross-section cap (2 %) by plan DIRECTION against the ring's long axis.
On a hairpin or a page that follows a hillside, that forbids the road to
stand on the ground §37 (6) sends it to: 7 of the 10 worst pairs are
followable along the route at the road's own 8 % cap (table above), and
the price of holding them is `dsf:pol51` cut 6.78 m into its hill and
`road_cross_section` 763 → 5,263 verify rows.  Does the withdrawn-chord
law extend to the road family (a road pair priced over the ROUTE between
its stations, as §37 (6) prices the target), or does the road page keep
its plan-chord law and §37 (6) yield where the two disagree?

#### What this lane did NOT do

The five-airport sweep (the orchestrator's); any `--refresh-data`; any
merge into main; any RULINGS entry; any change to §37 (1)'s caps, the
cross-section, `road_law_caps`, the bank, §27's flip or anything in
`solve/`, `constraints/eat.py`, `planar/structures*.py`, `planar/zones.py`
or `constraints/structures.py` (the parallel lanes' files); a second KCLT
build (the attempt cap: two replay arms, then one build); a LEMD or CYXY
BUILD (both were read as replay pairs on one capture each, which is the
dry frame the brief asked for); a new tool, so no `tools/INDEX.md` row.

### §37 (6) AMENDED (decks out), §37 (7) A ROAD PAIR IS PRICED ALONG THE ROUTE (Fable 2026-09-13; RULINGS 2026-09-13av) — lane `v2roadramp` round 2

Lane v2roadramp (4172e698): the ramp works (KCLT `dsf:pol51` follow 0.29 →
0.86) but the census regressed 3,900 → 7,622: `road_within_shape` (8 % × a
45.6 m PLAN chord) and `road_cross_section` (2 % × 44.2 m) hold a hairpin's
upper branch to the lower branch's ceiling — the two branches are 280 m apart
along the road.

- **§37 (6) amended:** a `bridge_deck:*` face is OUT of the ramp population —
  its datum is §33 (4) (the deck end equals the pavement it connects to).
7. **A ROAD PAIR IS PRICED ALONG THE ROUTE.** The road's longitudinal rows
   (the 8 % cap, `road_within_shape`) pair vertices by ROUTE distance along
   the road's own centreline, never by plan chord (09-05aa's withdrawn chord;
   §34 (1)'s route-priced ramp). A cross-section pair is a pair ACROSS the
   road's width at ONE station; `road_cross_section` prices only those. Two
   branches of one road within a road width in plan (a switchback) are not a
   pair; the ground between them is adjacent ground (§19 / §31, terraced,
   visual only).

BARS (round 2, ONE KCLT build against the shared control `ctl-KCLT`):
`road_cross_section` 1,691 → ≤ 310; adjudicated ≤ 3,900; the ten worst pairs
named route-followable or transverse; `dsf:pol51` follow ≥ 0.85 holds;
`dsf:pol82` ≤ 0.5 m (today 0.80); cockpit CRITICAL motion ≤ 8, no road row;
LEMD / CYXY dry re-read; suite twice.

### §37 (6) AMENDED (the ramp's floor is the core clamp), §37 (9) THE COVERAGE-EDGE JOIN (Fable 2026-09-13; RULINGS 2026-09-13be) — lane `v2roadramp` round 3

Scout `roadlevel`: the core's `include_roads` levelling runs for every
airport-area way and is then REMOVED inside the patch coverage + 6 m
(`O4_Vector_Map.py:1749-1757`); inside the coverage the patch is the sole
road authority and v2 computes the core's clamp itself
(`airport/road_profile.py` → `cap_lipschitz_profile`). At KCLT's east road
the mesh shows the patch (214.24) over the core (203.48) and the DEM
(200.31); at the coverage edge the patch's kerb meets the core ribbon with a
2.36 m drop over 7.9 m.

- **§37 (6) amended — THE FLOOR IS THE CLAMP.** The ramp target is
  `max(clamp(s), z_contact − cap × s)` along the route, `clamp(s)` the
  in-process `cap_lipschitz_profile` value (`preferred_road_z`'s own
  profile): the road descends at the cap to the core's answer and follows
  it. Where the DEM is within the cap the two coincide; where it is not,
  the road takes the lift/cut the core would have given it.
9. **THE COVERAGE-EDGE JOIN.** A road-family face whose way leaves the
   coverage takes, at its last station inside, the core ribbon's altitude
   at the first station outside (the clamp value) as an EQUALITY; census
   family `road_coverage_join` prices the step (twin: a road exiting the
   coverage, step 0). Bar at KCLT way 10826 station 0: 2.36 m → ≤ 0.05 m in
   the patch.

BARS (round 3, with §37 (8)'s): as 13bb, plus `road_coverage_join` 0 on the
lane arm and > 0 on the control; the mesh confirmation of the join is the
app build's tile.

## RULINGS

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

## 2026-09-14bt v2lemdstruct MERGED (2bbd3206): the 40.4988 tunnel's mouths on the owner's points (0.00 m), the bridge one deck to the way's ends, the F-6 mouth back 7.5 m; the basin rim-on-the-wall REFUTED as ruled (a wall-face reference is needed); §33 (3)'s crest at the clamped portal re-opened

Lane `v2lemdstruct` @ d630ffa3 (LEMD tile build `v2lemdstruct1`, rc 0,
verify defects {}, suite 1,540 twice; 1,560 on main). Landed: §34 (5)
(a) `_deck_cell` one derivation, the clip asymmetric across the axis;
§33 (2) (a) `_covered_end` clamps the plate move (both 40.4988
mouths 0.00 m from the owner's points; width 25.1 m; approach walk
verbatim); §33 (4)/§34.5 (6) `planar/structure_deck.py` (new):
`deck_intervals` over the way's full length, parallel ways sharing a
crossing one face (`[bridge] deck_group_gap_max_m` 12) — the bridge
ends 3.29 / 0.00 m from the owner's points, one face, east levels
within 0.02 m of the apron, rim `-11036` gone, no ≥ 0.5 m step past
the east end; decks 11 → 7 (four pairs merged, none lost). Census
ADJUDICATED 2,094 → 1,924, `road_cross_section` 14 → 8. F-6: the
ramp's north extent back 7.5 m (rim 40.4611264 → 40.4610588), the
taxiway `pav157` never cut in either arm, the profile monotone — but
the owner's stop point stays 7.6 m south of the rim and 11.9 m WEST
of the corridor axis (the bore is a merged dual carriageway, the
reported mouth is the pair's centre; the OSM centreline sits 0.25 m
from the north kerb so the eroded cell still reaches ~14 m south).
§24 (1) (a) REFUTED as ruled: `obj8.at_grade_geometry` clips each
component at ONE plane (a CONTOUR over the 28,345 m² pit — median
19.2 m / worst 51 m from the region ring); snapping would drag the
cut 20 m inward; the region ring passes 1.41 m from the owner's point
— the canyon is not a ring metres off the wall. `rim_wall_report`
(per-station) stands; the rule needs the pack's near-vertical solid
faces' plan trace (13g's open item, `obj8`'s to build). §33 (3): with
the mouth clamped back, `tunnel:-5931@1` returns to crest 610.23 /
floor 605.13 / ramp 36 m — the crest cap did not fire; open.

* OWNER (item 1, F-6): the mouth is 7.5 m further back; your point
  is off the axis by 12 m (the dual carriageway's centre is reported)
  — say whether the west carriageway's mouth should go further back
  still, or whether this reads right in the sim.
* OWNER (item 5, the basin canyon): the ring is 1.4 m from your point
  and the mesh has a clean 7.7 m wall; what you see is between the
  pack's wall object and our cut — a coordinate ON the visible gap and
  its width would let a wall-face read be targeted.
* App 1.0.338 (LEMD: 14bs + 14bt) next.

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N] [--why-hard-stage 1]` on either a `--replay` arm or a `--why-from PKL`; `--why-from PKL --probe-site LAT,LON [--probe-drop M] [--probe-arm TERM=V ...]`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (**and THE CLUSTERS beside the partition and the groups** — lane ``v2padjoin`` 2026-09-14: a capture without ``Airport.clusters`` leaves §30 (4)'s cluster pad, its apron reach and §16g (10)'s derived pads INERT in every replay of it, so a pads-ON arm silently measures the pads-OFF law; a capture predating them has them DERIVED at replay off its own partition, named on stdout) (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently).  **`--why-hard-stage 1`** reads §20b STAGE 1's OWN ASSEMBLY instead of the full problem's (`solve.design.stage_split`'s drop + fixed): the AIRSIDE hard set, in the rows and the metre scaling stage 1 enforced them under. The full read cannot answer "does the AIRSIDE solve settle" — the airside rows are a subset of 325k whose population and scaling the stage's own drop changes — and that is exactly the claim RULINGS 13y (B) / 13ab / 14as make (lane `v2settle`, which used it to split HECA's "42 unsettled rows" into 9 CONSTANT rows the solve can never move, 6 HELD runway rows at the projection's own bar, and 18 real ones).  The shipped surface is read either way: an airside vertex's z IS stage 1's, so the stage-1 read at the shipped z equals the read at stage 1's own surface (measured identical at HECA). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate).  **`--probe-site LAT,LON` IS THE STABILITY PROBE** (lane `v2qp`, spec §20c, promoted from lane `v2settle` r2's `scratchpad/v2settle/probe3.py`/`probe4.py` on its second use): off a `--solved-out` pickle, one extra `Band` ceiling `--probe-drop` (default 0.30) metres under the ARM's OWN base surface at the vertex nearest the point, re-solved, and the moved set (> 0.02 m) binned by distance from it — 0-40 / 40-100 / 100-250 / 250-500 / beyond, with the worst beyond 250 m, each arm's hard set and its exit line.  `--probe-arm TERM=V` repeated makes it a MATCHED PAIR of `[design]` arms on ONE problem (`--probe-arm solver=fixed_point --probe-arm solver=qp` is §20c's own bar); with none it probes the shipped law alone.  This is the instrument RULINGS 2026-09-14bw's headline was taken on (HECA: 959 vertices moved by one 0.30 m row, 953 beyond 500 m, ZERO within 100 m).  `--design-weight TERM=V` also takes a NON-NUMERIC value now (§20c's `solver=qp`); a value that does not parse as a float is passed through as the string.  Twin: `tests/auto_patch_v2/test_v2qp.py` (the probe as a fixture pair) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

## Tool: role_overlap_read

| `Ortho4XP/tools/role_overlap_read.py` | The question is WHAT STANDS ON WHAT — *how many square metres of one emitted role/ref class lie on another class's footprint* — which is the single number a ruling of the form "the gap-fill spine must STOP at groundside pavement" (RULINGS 2026-08-30 ruling 4) is accepted or refused on. No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a face lying flat on a lot breaks no grade law and reports ZERO rows; `osm_site.py` answers one coordinate and `arm_site_read.py` one named place; `void_census.py` asks enclave TOPOLOGY; `lattice_overlap_read.py` asks CONTAINMENT of the two role-less membrane classes by LENGTH. This is the AREA sweep: `--over ROLE[:REF] --on ROLE[:REF],...` reports the populations, how many OVER ways stand on the ON union, the total m², and per stacked way its own area, the area over, the fraction and the ON shapes it stands on, largest first. **It measures no law and counts no defects** — geometry, the metre frame about the sidecar's own anchor and the role-carrying rings come from the harness library (`check_grade._parse_osm` / `_ll_to_m_factory`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. A patch with NO `.axes.json` sidecar is REFUSED (no anchor, no metre frame — an area in the wrong frame looks right and is not). `--min-area` (default 1.0 m²) is emit rounding, not a law threshold. Measured basis (HECA round 6b/6c): on the round-6b closing arm `graded_strip:gap_fill_spine` over `groundside_pavement` = 18 strips / 26,780 m², two faces carrying 24,288 m² of it (3190 over lot 2813 by 13,657 m², 70 %; 3192 over 2814 by 10,631 m², 63 %), while the same read over `service_road,service_junction` — 34 strips / 25,073 m² — said the annulus class was not one ruling's alone. Promoted 2026-08-30 from the HECA round-6b lane's scratchpad on its second use (RULINGS `7e90032`). `--pad M` grows the ON union before the read and `--beyond` reports the COMPLEMENT — the OVER ways that do NOT reach it, totalled and split by ref: the OWNERSHIP read RULINGS 31b is stated in ("within SERVICE_ROAD_PAVEMENT_NEAR_M of aircraft pavement"), which is how Batch 4a priced HECA's far road-family population off the merged-main control (`service_junction` beyond 25 m of the airside roles: 1,526 of 1,777 rings / 473,248 m², of which 1,325 ref-less / 435,882 m²). `--site LAT,LON` (repeatable) answers a named place in the OVER class's own terms — which way covers it, its ref and area, and the distance from both point and ring to the ON class. Several patches are reported separately — the arm-to-arm read; quote it on identical options. **`--contains` is the CONTAINMENT CENSUS and it is a DIFFERENT FRAME** (2026-09-13, lane `v2zonehole`, spec §41 (1)): the overlap sweep above is a SOLID-frame question and reads 0 m² here BY CONSTRUCTION — the arrangement is a partition, so a face enclosed by another sits in its HOLE and never overlaps its solid. `--contains` asks whether a pavement face lies inside another pavement face's EXTERIOR RING (`--min-frac`, default 0.95 = §41 (1)'s own floor, the one spelling of `planar.overlay.ENCLOSED_MIN_FRAC` outside the engine), and reports per row the inner face and its area, the host, the RING fraction, the SOLID fraction beside it (which is what says the two readings are not the same question), the shared-edge length and the distance to the host's solid — a face that TOUCHES its host is a NOTCH cut into a body (absorbed by `planar.overlay.absorb_enclosed_pavement`), one that does not is an ISLAND in the middle of a taxiway loop (left alone). Measured basis (the owner's 1.0.329 HECA patch): 39 of 370 pavement faces contained, 65,772 m², every one at solid fraction 0.000, 33 notches / 6 islands — `cross_connector:pav77` 896 m² in `primary_parallel:pav73` is the owner's dip site (RULINGS 2026-09-13co item 2). **THE ANCHOR REPAIR** (same lane): the read used to do `side["anchor"]` and died `KeyError: 'anchor'` on every v2 patch — v2's `SIDECAR_KEYS` publishes no anchor, deliberately, and the harness library itself falls back to the MEAN OF NODES, which is the frame the census reads the same patch in. The sidecar is still REQUIRED; the anchor is used when the patch carries one; the frame in force is printed on every report and carried in the JSON (`frame`). **`--slivers` and `--hole-rings` are the FOURTH and FIFTH questions, and both are WIDTH questions** (2026-09-14, lane `v2slivers`, spec §41 (4) / RULINGS 2026-09-14g items 4/5): the reads above ask what stands on, or inside, what — neither asks whether a shape is BIG ENOUGH TO CARRY LAW, which is what a zone strip that mints a hump and a hole ring that ships across a service road have in common. `--slivers` reports every `graded_strip` face under `--strip-min-area` (50 m², `emit.terrace.strip_min_m2`) or narrower than `--strip-min-width` (3.0 m, `strip_min_width_m`) with its area, inscribed width, elevation span and the pavement face it borders longest — the HOST `planar.overlay.dissolve_sliver_zones` unions it into. `--hole-rings` reports every emitted `gap_interior_ring` way with the fraction of its area the faces INSIDE it cover (`--cover-eps`, `emit.terrace.hole_cover_eps`), its inscribed width, and a verdict: `covered` (a duplicate ring), `hairline` (narrower than `strip_min_width_m`: it can carry no transition) or `void` (a real hole, which KEEPS its ring). THE WIDTH IS THE MAXIMUM INSCRIBED CIRCLE's DIAMETER, imported from the engine's own `planar.overlay.inscribed_width_m` and never re-spelled: `2 A / P` is a mean-width proxy and over-counted HECA's narrow zone faces 42 → 153 (the ruling's own measurement). Measured basis (the owner's 1.0.331 HECA patch, mean-of-nodes frame): 338 `graded_strip` faces / 2,895,389 m², of which 57 slivers / 1,647 m² (51 under 50 m², 42 under 3 m) — shape 1035 `adjacent_ground:taxi:E:zone1#38`, 15.7 m², 2.16 m, z 105.86–106.01 against a taxiway at 104.4, host `cross_connector:pav115`, the owner's hump (RULINGS 2026-09-14c item 4); and 57 `gap_interior_ring` rings / 926,251 m², 11 covered ≥ 98 %, 5 hairline, 41 real voids — way −10231, 29.5 m², 1.60 m wide, 92.3 % covered, the ring that shipped across `service_road:route4`. Both price no law and count no defects. Twin: `tests/test_role_overlap_read.py` (the area IS the intersection, the ROLE:REF selector is exact, the floor both ways, prices-no-law, the no-sidecar refusal, the `--pad`/`--beyond` complement, the `--site` read, the inscribed width agreeing with the engine's and the proxy disagreeing, the tool's three §41 (4) constants being the law table's, the sliver read naming the host, the hole read's cover fraction / width / three verdicts, the three reads refusing to run two at a time, and this index row) and `tests/auto_patch_v2/test_v2zonehole.py` (the anchor-less sidecar is not a crash, the containment census's ring-vs-solid frames, and that the two spellings of 0.95 agree). |

| `Ortho4XP/tools/role_overlap_read.py` | The question is WHAT STANDS ON WHAT — *how many square metres of one emitted role/ref class lie on another class's footprint* — which is the single number a ruling of the form "the gap-fill spine must STOP at groundside pavement" (RULINGS 2026-08-30 ruling 4) is accepted or refused on. No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a face lying flat on a lot breaks no grade law and reports ZERO rows; `osm_site.py` answers one coordinate and `arm_site_read.py` one named place; `void_census.py` asks enclave TOPOLOGY; `lattice_overlap_read.py` asks CONTAINMENT of the two role-less membrane classes by LENGTH. This is the AREA sweep: `--over ROLE[:REF] --on ROLE[:REF],...` reports the populations, how many OVER ways stand on the ON union, the total m², and per stacked way its own area, the area over, the fraction and the ON shapes it stands on, largest first. **It measures no law and counts no defects** — geometry, the metre frame about the sidecar's own anchor and the role-carrying rings come from the harness library (`check_grade._parse_osm` / `_ll_to_m_factory`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. A patch with NO `.axes.json` sidecar is REFUSED (no anchor, no metre frame — an area in the wrong frame looks right and is not). `--min-area` (default 1.0 m²) is emit rounding, not a law threshold. Measured basis (HECA round 6b/6c): on the round-6b closing arm `graded_strip:gap_fill_spine` over `groundside_pavement` = 18 strips / 26,780 m², two faces carrying 24,288 m² of it (3190 over lot 2813 by 13,657 m², 70 %; 3192 over 2814 by 10,631 m², 63 %), while the same read over `service_road,service_junction` — 34 strips / 25,073 m² — said the annulus class was not one ruling's alone. Promoted 2026-08-30 from the HECA round-6b lane's scratchpad on its second use (RULINGS `7e90032`). Several patches are reported separately — the arm-to-arm read; quote it on identical options. Twin: `tests/test_role_overlap_read.py` (the area IS the intersection, the ROLE:REF selector is exact, the floor both ways, prices-no-law, the no-sidecar refusal, and this index row). |

## Tool: check_grade

| `Ortho4XP/tools/check_grade.py` | You want the grade validator's CLI on one patch, or its library from code. The CLI is a thin front end over the same law reader the census uses. A run with no sidecar is CONTEXT-FREE and overcounts — it is not a defect count. It also prints **THE COCKPIT BLOCK FIRST** (owner RULINGS 2026-09-12x/12y; §31 (6)) — the same `cockpit_block` / `cockpit_block_lines` the harness census and the pytest fixtures call, over the SAME run's `family_out` (the checks' own output is buffered and replayed under the block, never run twice). A `strip_seam_tear` row carries the PAIR MIDPOINT as its lat/lon (spec §32 (3), RULINGS 2026-09-12ag): it used to carry none, and `run_checks` filled it with the offending way's RING CENTROID — at LEMD that sent the cockpit block's first CRITICAL VISUAL find 220 m from the 8.25 m tear. Twinned both sides (`tests/auto_patch_v2/test_v2zoneclamp.py`), the engine's own `verify/strips.strip_seam_tear` alongside. The block's "in view by approach" test is the ONE approach corridor of `auto_patch_v2.law.approach_corridor` (RULINGS 2026-09-12al; twins `tests/auto_patch_v2/test_v2approachcorridor.py`), never a radius around a runway vertex. **`adjacent_ground_step`** (spec §34 (4), lane `v2rampwalk` 2026-09-13) is the WITHIN-FACE welded step on a v2 `adjacent_ground:*` face — the reading no family had: `graded_strip` carries no within-shape cap, `adjacent_ground_tear` fires only under a 1 m edge and `strip_seam_tear` is the CROSS-shape twin, so a band holding its designed level over a mapped road's own ground (LEMD `zone2#2`, 1.73 m over 1.5 m at road −6289) was priced by nothing. Its floor is the cockpit's own `visual_m` AND `cliff_grade` in one step: without the cliff term it counts the lawful hillside drape (measured CYXY 296 rows). Lockstep both sides — `auto_patch_v2.verify.strips.adjacent_ground_step` reads it in the engine; twins `tests/auto_patch_v2/test_v2rampwalk.py` and the v1/v2 census parity test. **`ramp_in_road`** (spec §34 (10), owner RULINGS 2026-09-14bb/14bc/14bd, lane `v2othhramp`) is the CRITICAL presence family the road margin needed: every ramp arriving at a road ends at the road's TRUE edge — the centreline offset by the road's own half-width toward the ramp, ONE derivation `planar/wall_corridor_ramps.road_true_edge` read by every ramp emitter — so a RAMP vertex standing INSIDE a road ribbon is a lane of carriageway cut away, whatever its elevation. No other family sees it: a ramp welded flat into the road it ate breaks no grade law and prices zero rows. A vertex within the census's own weld tolerance of the ribbon's edge is ON the edge, which is what the law asks for. It reads 0 at OTHH before and after — the family is the GUARD on that derivation and never a defect count. Twins: `tests/test_harness.py` §34 (10) (both directions, the weld line both ways, the register and the cockpit class, and the ramp-role set read from the law's own structure roles). **THE RUNWAY SHOULDER'S OWN CAP** (spec §40 (2) as amended, owner RULINGS 2026-09-13dd, lane `v2roles`): a within-shape pair BOTH of whose nodes lie beyond their runway's own half width is priced at `shoulder_transverse_max` (2.5 %, ICAO Annex 14 §3.2.4), not the runway's 1.5 % — a §40 (1) SHOULDER keeps the runway's DATUM, not its cross-fall. The line is the SOLVE's and is read, never re-derived: the sidecar's `runway_axes` (`[ref, lat_a, lon_a, lat_b, lon_b, half_m]` off the apt.dat ends and width) and `shoulder_transverse_max`, through `shoulder_nids` / `_shoulder_cap`. Fitting the width to the runway RINGS instead would read a shoulder as part of the runway and never find its own line. A patch with no key reads exactly as before. One reading with the generator and the v2 verify (`auto_patch_v2.law.tables.runway_transverse_cap`); twins `tests/auto_patch_v2/test_runway_shoulder.py`. |

## Tool: site_read

| `Ortho4XP/tools/site_read.py` | You have a coordinate from an owner's sim read and the question is WHAT THE OBJECT STAGE MADE OF IT — not what the OSM patch says there (`osm_site.py`, the emitted ways) and not one law's defect count (`harness/census.py`). Three products of ONE build, read at ONE point in one process: the emitted DESIGN SURFACE's faces containing or near it (role, ref, side, z min/med/max, node count — a CONTAINING face reads 0.0 m, never the distance to its nearest vertex, which is `osm_site --at`'s own trap); the DSF ROWS standing on it (`OBJECT` / `OBJECT_MSL` / `OBJECT_AGL` with the resource and, where it has one, the written elevation — `None` for a plain `OBJECT`, never 0.0); and the PLAN BODIES whose plan box reaches it, each with its §6 class, its FOOTPRINT UNIT, its surface z and zero and the stage's own ANCHOR REASON verbatim, which is the line that says WHY a body is where the owner saw it. `--patch-dir DIR` resolves `<ICAO>.graded.json` and `o4_v2_placement_<ICAO>.json` by glob (an `obj8_split_report --json` dump works as `--plan`: the same `splits` records), `--dsf-dump` takes a DSFTool TEXT dump — pass the PRISTINE `<dsf>.anchor_bak...text` (`dsf_write.pristine_dsf_path`) when you want the pack as INSTALLED rather than as this repo last wrote it. `--show`, `--max`, `--json`. **It measures nothing and derives no law**: every value is read verbatim out of a product and nothing is written. Promoted 2026-09-14 (RULINGS `7e90032`, promote-on-reuse) from the scratchpad reader of the 14g HECA attribution, re-written for the 14bl LEMD one (scouts `v2heca331` / `v2lemd336o`) and used a THIRD time by lane `v2leafframe` — three copies of one question, already drifted in their hard-coded LEMD paths. Twin: `tests/auto_patch_v2/test_v2leafframe.py`. |

| `Ortho4XP/tools/arm_site_read.py` | The question is about a PLACE across two arms — "is the wall at 35.2077303,-80.9290869 still there, and did anything near it get worse?" — which an A/B leaves open: `census.py --rows-json` itemises rows and `census_rows_diff.py` joins two dumps class by class, but neither can be asked about a coordinate, and `osm_site.py` reads geometry without law rows or pad seats. This is the join: per named `--site`, per arm, the law-true rows within `--radius` with their worst grade and |de|; with `--seats`, the BUILDING PAD seats that moved between the arms — the channel this repo's HECA airside attribution ran through (a pad seat welds into the apron ring, so a seat that moves moves airside; measured 2026-08-12b: 92 of 215 pads, median 0.32 m, and building211's +0.88 m carried +203 apron rows). **It measures no law and counts no defects**: rows are read verbatim out of census `--rows-json` dumps and geometry/altitudes through the harness library's own `check_grade._parse_osm`, so this tool and the census read one file one way; a missing input reports SKIPPED, never zero. FRAMES, both printed: rows are located by the census's own row lat/lon, which for a within-shape pair is the PAIR's position (a 400 m apron chord's row sits far from either endpoint's geometry), so a radius selects rows near the PAIR, not shapes touching the site; seats join by the building's `ref` tag, never by way id or shapeID (both arm-dependent). Promoted 2026-08-12b from the service-corridor lane's `measure_arms.py` on its SECOND use — the named-site table and then the airside attribution. `--welds` (added 2026-08-12c, the corridor-joins round's ruling-4(a) instrument) answers the other question a place can be asked — IS THIS SEAM JOINED? Per site, per arm: the node ids SHARED between the road family (`check_grade._ROAD_FAMILY_ROLES`, read from the census library) and the airside ways, the max |Δalt| two ways carry at a shared node (0.00 is the construction — production values sit on the NODE, so a weld is single-valued; the delta is the torn-weld guard for way-valued rings), the NEAREST UNWELDED approach when nothing is shared (0.999 m at both KCLT mouths, against a 0.5 m weld tolerance), and the `retaining_wall` ways standing at the site with their ids. `--profile` / `--line` (added 2026-08-25, the HECA apron round-2 acceptance) answer the THIRD question a place can be asked — WHAT SHAPE IS THE SURFACE HERE? `--profile` walks every ring of `--profile-roles` (default `apron,graded_strip`) reaching a site and reports its worst consecutive EDGE and its RIPPLE AMPLITUDE, the peak-to-peak inside a 50 m run ALONG THE RING — the same window `apron_drape_read` calls `amp50`, so the two tools spell the ripple one way. `--line NAME=LAT,LON:LAT,LON` orders every emitted vertex in a corridor about an owner-named segment by its station along it, with the step between consecutive stations: the reading an acceptance written as "no unlawful step along the owner line" is stated in, AND the reading that shows a NODELESS VOID, because there an EMPTY STATION LIST IS ITSELF THE FINDING (a region with no emitted vertices contributes no census row however wrong its surface is — the blind spot `nodeless_interiors` counts). Neither prices a law; quote them ARM TO ARM on identical options, never as a verdict. Reach for it whenever an acceptance claim is about a join: **row absence cannot answer it** — a census row exists only between PAIRED geometry, so an unwelded road↔taxiway seam is silent in every census, which is exactly how two 1.0.244 acceptance claims passed over a gap no node could bridge. Twin: `tests/test_corridor_axis_coverage.py`.  **`--behind NAME=LAT,LON:LAT,LON` is the WALL scope** (added 2026-08-29, scorer-v2 round, spec `scorer-v2-class-boundary-spec.md`): the owner states a wall as two coordinates and asks that no airside pavement cross it — `--line` answers what the emitted elevation does ALONG it and `osm_site --line` answers what covers each station ON it, but neither answers the quantitative half, the SQUARE METRES of airside-role pavement sitting on the groundside, which is the number a boundary-cut round moves and therefore the number its acceptance is written in. Per crossing ring it reports the area behind, the node split either side and each side's altitude range — the shape of a wall buried inside one apron (HECA apron 584: 48 nodes at 97.22-104.69 m in front, 95 at 90.77-102.71 m behind). TWO FRAME RULES, both load-bearing: the band is the line's OWN SPAN by `--behind-depth-m` (default 150 m) deep, never a half-plane — unbounded, the far side sweeps in the whole airport and reports 634,371 m² where the local answer is 25,900 (measured at HECA); and the GROUNDSIDE side is decided by the patch — the side carrying less airside pavement — so reversing the two coordinates cannot change the answer and a caller cannot pick it. The closed-ring repeat is dropped before the node split (counting it double reports one extra node on whichever side the ring starts). It prices no law and counts no defects. **THE SEAT JOIN IS NOT FREE (2026-08-31, the buildings round).** `building{N}` is an ORDINAL identifier, so an arm that ADDS or DROPS a pad renumbers every later one and the ref join reports the RENUMBERING as seat motion: measured on the buildings-round HECA arms (pad count 175 -> 176) the ref join said 85 of 174 pads moved, median 2.72 m, max 33.65 m, where the population had barely moved. The tool now DETECTS it — a common ref whose pad centroid is more than `--seat-radius` (15 m) away is named as RENUMBERED, with the advice to re-run — and `--seat-join location` pairs pads by centroid instead (closest pair first, each pad used once; a pad with no partner within the radius is reported as added/dropped, NEVER as a move), which on the same arms reads 28 of 174 moved, median 0.07 m, max 2.32 m. Quote a pad-population round's seat movements under the location join. |

## Tool: obj8_split_report

| `Ortho4XP/tools/obj8_split_report.py` | THE OBJ8 SPLIT, DRY-RUN (spec `object-placement-spec.md` §4 / §6 / §7; owner RULINGS 2026-09-11b) — what a pack's object stage becomes once placements are AGL, objects are cut into their RIGID BODIES and each body carries its own anchor. Reads only a build's own two products — the re-seat plan (`<ICAO>.rebake.json`: the pack read once, its welded parts and the ε-contact graph) and the emitted DESIGN SURFACE (`<ICAO>.graded.json`, whose `building` faces are the object pads and `structure_rim` breaklines the basin walls) — and NEVER opens the pack for writing, never reads the DSF and never builds anything. Prints per placement the bodies, their §6 class, each body's anchor point / reason / authored offset, the files that would be written and the placements KEPT WHOLE with the reason (`one_body`, `anim`, `unparsable`); `--write-into DIR` writes every cut file into a scratch dir and parses each back through `airport/obj8.parse_obj8` (LEMD 13,924 files, OTHH 65,360, all parsing back with the written triangle count, 2026-09-11); and prints §7's CENSUS — the design surface at a body's ANCHOR against the surface under each of its ground-contact FEET, the |Δ| histogram `seat_feet_census.py` prints from a mesh and a seat result, read instead from the plan and the design surface so the two are comparable. A foot or anchor outside every graded face reads `off-surface` and is never guessed at (the DEM governs there and this tool does not open the DEM). `--no-cut` for body counts only, `--filter`, `--json`, `--split-tol` to override `[placement] split_tol_m`. ROUND 2 (owner RULINGS 2026-09-11e, spec §9): the bodies are COARSENED (bodies of one placement whose intended-zero terrain heights agree within `split_tol_m` are one file, the senior body's anchor; an elevated body joins the nearest ground group) and each anchor is the GENERIC one (the footprint point where the design surface equals the body's zero; a body with authored relief beyond its skirt takes its low-side foot and is reported with the residual) — LEMD 302 placements -> 985 files (3.26x), OTHH 954 -> 1,172 (1.23x). §13 (owner RULINGS 2026-09-11r/s): an ELEVATED body — one whose lowest authored vertex, or the `y_zero` of the anchor the generic rule gives it, stands above `[rebake] elevated_base_m` — NEVER has a file of its own; it joins its CARRIER (the same placement's ground body with the largest plan overlap, else the nearest) at its authored offset, and a placement with NO ground body is KEPT WHOLE with reason `footless`. The report prints the two classes by name — `elevated bodies as own files` (BAR 0) and `footless placements kept whole` — because the FEET histogram cannot see this defect: the writer shifts an elevated body so its own lowest vertex lands on the terrain and every foot then reads perfect (LEMD's 218 roofs/decks/tower parts censused green while the sim was broken). Measured on matched pack copies: LEMD own-files 278 -> 0, files 1,099 -> 828, feet > 3 m 1,060 -> 151, worst 34.06 -> 13.75 m; OTHH 1,203 -> 333 files, feet > 3 m 952 -> 6. ROUND 3 (owner RULINGS 2026-09-11f, spec §10): the write half RESTORES every `<obj>.anchor_bak` in the pack before any file is written (counts in the plan's provenance), and a LINE OBJECT authored as one component is cut into SEGMENTS by triangle station (`--line-segment M` overrides `[placement] line_segment_m`; 0 disarms it) — LEMD 897 segments from 271 one-line bodies, 985 -> 1,086 files, census `> 3 m` 30 -> 25; OTHH 1,187 files, `> 3 m` 0. `--write-pack PACK_COPY` runs THE WHOLE WRITE HALF into a pack COPY through `airport/placement_write.apply_plan` (cut files, DSF + backup + provenance, dump-cache refresh, `o4_v2_placement_<ICAO>.json`) and reads the written DSF back; it REFUSES a live X-Plane install. The census also splits the feet over 0.3 m into BURIED (lawful) and FLOATING (the defect the eye reads). `--rows-near LAT,LON[,R]` (lane `v2padcluster`, 2026-09-14) is that SAME projection selected BY PLACE — every body whose ANCHOR is within R metres (default 40) of the coordinate, nearest first, each row carrying its `site_m` — because the owner names a defect by coordinate and the shapeIDs in a report go stale between builds while a coordinate does not; `osm_site --at/--contains` answers the other half of a site question (which emitted FACES cover the point) and is not re-spelled here. Promoted from the scout `v2heca331`'s scratchpad `site.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse): the 14g attribution, then §16g (10)'s per-site bars; its graded-face half was already `osm_site`'s and was NOT copied. Twin: `tests/auto_patch_v2/test_v2objsplit.py::test_rows_near_selects_the_same_rows_BY_PLACE`. `--rows SUBSTR,SUBSTR` (lane `v2canopy4`) prints the PER-BODY rows of the placements named — the body's anchor (point, surface z, `y_zero`, reason), its ground-contact feet, its worst foot signed with |Δ|, and the 0.3 m verdict — for the owner's named sites (`OldTerminal_FSX-LEMD38,-LEMD84,-LEMD60`); it is a PROJECTION of the one census pass, never a second instrument (the bins, feet and worst list are identical with and without it, twinned). §14 (owner RULINGS 2026-09-11u/v, lane `v2carrier`): a FOOTLESS placement is CARRIED — written as a body file at its CARRIER's anchor with the carrier's `y_zero` (the footed body of its UNIT it abuts with the largest contact, else the nearest, else the largest) — a BASIN resource is never split and anchors at a RIM point where the design surface equals its zero (`rims` wired at last), and bodies of one resource that OVERLAP IN PLAN bind whatever the contact graph says. The report prints the four §14 bars (`footless at datum` 0, `footless on ground` 0, `basin bodies split` 0, `spread`) beside §13's, from `airport/placement_carrier.census_v14` — the same call `seat_feet_census --placement-plan` makes over the same plan shape, so the two instruments are one code path. Measured on the app's 1.0.315 LEMD frame: the four footbridge resources at the terminal's zero 616.65 (deck bottom road + 4.4-5.0 m, was ON the road), `Terminal4SAT_pink-LEMD01` at its terminal's 597.43, the basin's three resources one file each on ONE rim vertex (zero spread 7.0 m -> 0.00, parapet +2.99 above the rim), files 828 -> 855, round trip OK, row census `> 3 m` 17. Twin: `tests/auto_patch_v2/test_v2objsplit.py`. §15 (owner RULINGS 2026-09-11ae, lane `v2roofcarrier`): the CARRIER IS WHAT THE BODY STANDS OVER — chosen across the whole UNIT, every resource alike, by largest PLAN OVERLAP beneath, else largest contact, else nearest (§13's same-placement scope and §14's contact-first order are superseded; the pack names its roofs as their own resources, so the walls a roof rides are almost never its own file); the plan-overlap BOND is RE-CUT where a bound group's intended zeros span more than `split_tol_m` (a rigid body is never wider than the terrain it can stand on; BASIN exempt); DUPLICATE ROWS of one resource identical in lon/lat/heading are ONE placement, all of them replaced (`--write-pack` reports `duplicate rows of a SPLIT placement ... surviving after the write`, bar 0); an anchor or foot on no graded face is marked OFF-SHEET and excluded from every comparison and bar; and the report prints §15 (3)'s `stands-over float > 0.5 m` from `airport/placement_carrier.census_v15` — `float = zero - zero_beneath`, the class NEITHER the feet histogram nor §14's bars can see (a carried body has no feet at all), barred at 0 for CARRIED bodies and reported for footed ones. §16 (owner RULINGS 2026-09-11ai, lane `v2skipped`): the report adds the POPULATION census (`placement_carrier.census_population`: `rows on the datum outside the plan` — the resources the SEAT-era thickness gate dropped, which keep the pack's shared-datum row and render where the datum is, bar 0 — beside the lawful skips and the multi-anchor class, reported not barred) and `census_v16`'s `float = zero - ground_under_geometry`: the ground read under the body's OWN parts (`geom_box` / `foot_boxes`, the median of the part-box centres) and never under its carrier's box — `CARRIED bodies whose carrier's zero is over 1 m from the ground under their own geometry` (bar 0; LEMD 39 -> 0 on matched arms) and `files whose own-geometry ground departs over 3 m from the ground at their row` (26, reported). `--admit-skipped PACK_ROOT` puts the thickness-gated resources of a PRE-§16 plan back into the population by reading their rows from the pack's own DSF (one part per component, no contact graph, the member id IS the DSF row index) — what a build's own plan now carries, for replaying a plan written before the switch; LEMD 25 resources / 25 rows, OTHH 99. §16a (owner RULINGS 2026-09-11aj, lane `v2skipped2`): a CARRIED body is cut where its CARRIER is cut (one piece per carrier terrain group its own triangles stand over, each riding that group's zero; never by the ground under itself), the ground check moved to the carrier's OWN feet (`Candidate.ground_off`, `surface(foot) - y_foot` against the body's zero), and `census_v16`'s carried number demoted to INFORMATION — the bar for a carried body is §15 (3)'s `zero - zero_beneath`. The report prints `carried bodies left uncut by the ground` / `cut by their CARRIER into N piece(s)` and, beside the §15 bar, how many of the carried floats stand over a body the law REFUSES as a carrier. LEMD carried float 58 → 4, files 1,591 → 1,328, plan stage 9.9 → 6.3 s; OTHH 7 → 39, 46.4 → 60.2 s (both OTHH bars missed and reported). 11ak (lane `v2skipped3`): the CARRIED bar's `beneath` is the carrier THE LAW CHOSE (`merged_into`, resolved by identity over every row that reads a zero — a carrier written WHOLE names its MEMBER RESOURCE, which is the whole of OTHH's residual), and a body the law REFUSES as a carrier is counted and named as its own class, `carried over a refused body`, with how far its own feet stand off; §16 (2) also cuts BY FOOT (`placement_cut._LineCutter.foot_groups`: the feet grouped by the zero each says the body has, `surface(foot) - y_foot`, each triangle joining the group of the foot nearest it in plan) — the class no ground cut can see, a body whose FEET are authored over metres of relief on terrain that barely moves, which is exactly what §16a (2) refuses. The re-cut line prints the three cuts (terrain / triangle / foot). LEMD carried float 4 → 0, refused carriers 117 → 21 (13 of the residue are rim-anchored BASIN bodies the foot cut is exempt from), files 1,328 → 1,371, plan stage 6.2 → 5.66 s; OTHH carried 42 → 0, refused 55 → 19, files 1,679 → 1,622, plan stage 59 → 31 s (`solid_components` read in one sort instead of a mask per component; `bind_plan_overlaps` swept by the hull's south edge). 11al (lane `v2basincarry`): a BASIN body is EXEMPT from §16a (2)'s ground test — its zero is the RIM (§14 (2)) and its floor feet are authored below it by construction — so it may carry, and the report prints `§16a (2) basin carriers` (how many basins, how many the feet test would have refused) beside the refusal set: LEMD refused carriers 21 → 8, OTHH 19 → 4, carried float 0/0 unchanged. §14a (owner RULINGS 2026-09-11ap item 6, lane `v2basinring`): a BASIN body follows its RING. §24 (1) puts the rim vertices at the APRON's level, so the ring is not level (LEMD's T4 pit 597.68 … 599.52 over 59 nodes) while §14 (2) wrote every basin body at ONE rim point — the owner's "gap between wall and apron", +0.71 / −1.13 m, while the §14 `spread` bar read 0.01 because it measures the pit's bodies against EACH OTHER. `airport/basin_ring.py` (NEW: the whole law — `arcs_of`, `ring_arcs`, `member_kind`, `ring_bar`) cuts the ring into ARCS whose z agrees within `split_tol_m` and cuts each basin body's WALL BAND by them, one piece per arc anchored at that arc's rim point (the interior remainder keeps §14 (2)'s single point: the trench floor is one level); and a member authored AT THE RIM PLANE but standing inside the ring is a FLOOR body that takes §16 (3)'s ground under its own footprint, never the rim, never a carrier. The report prints the RE-DEFINED bar — `§14a spread of a BASIN RING = max |wall base − ring z| over its nodes` (bar ≤ `split_tol_m`), with the nodes on an arc the pit has NO WALL on reported beside it — and the `§14a basin FLOOR members` / `basin bodies cut by the ring's ARCS` counts. It needs the rings WITH their heights (`census_v14(rims=..., arc_cap=..., counts=...)`; `RimRing.z`, and the `basin_arc_wall:<ref>#<k>` counts keys the cut writes are how the bar tells "no wall here" from "the wall is written in the interior piece"). Matched arms on the app's 1.0.319 LEMD frame: the ring bar 1.12 m / 9 nodes over → **0.18 m / 0 over**, `LEMD13__b0` off the rim and onto its own ground, files 1,371 → 1,394, feet > 3 m 518 → 412, floating 9,509 → 9,014; OTHH's 21 basin carriers and its whole foot census byte-identical. §16b (owner RULINGS 2026-09-11ap, lane `v2owncut`): the TERRAIN CUT IS PRIOR AND UNIVERSAL and is read on the body's OWN WRITTEN TRIANGLES — including everything the writer will put in the file (`placement_cut._LineCutter.all_tris`: a placement the plan reads as ONE body is written as the WHOLE object, which is why `green-TEJ3`'s 4-triangle part read 0.22 m of ground while its 2,342 m file stood +16.22 m over it) — so a CARRIED body is divided by the ground under itself first and §16a (1)'s carrier cut runs inside each piece; §9's coarsening additionally requires PLAN CONTIGUITY (`[placement] coarsen_reach_m`, 30 m) and acts WITHIN a terrain group (the pieces carry the ground they stand on, or the very next pass welds them back); each PIECE finds its own carrier, and a FALLBACK candidate (contact / nearest / largest, no plan overlap) is refused unless its zero is within `split_tol_m` of the ground under the piece (`carrier_refused_far_from_carried_ground`). The report prints `census_v16b`'s two bars over the WRITTEN geometry the plan now publishes per body (`geom_pts`, one sample per 10 m cell, thinned to 32 by the farthest-point walk): `carried piece float over its own ground > 0.5 m` and `body wider than its terrain group`, both bar 0, with the BASIN exemptions (§14 (2) / 11al) counted apart and the wide residue split by class. `--coarsen-reach M` overrides the contiguity reach. Measured on the app's 1.0.319 LEMD frame: the owner's item 3 +10.74 → the plate ON the roof beneath it (618.58 vs the group's 618.60), item 5 +16.22 → 620.38 vs 620.27, `Terminal4_48` zero-vs-ground −4.02 → median −0.01, `Taxisigns-SENRG` 38 of 80 bodies over 0.3 m → 12 of 419; files 1,371 → 3,272 at the amended 100 m reach (4,633 at the refuted 30 m), plan stage 5.6 → 10.1 s (bar ≤ 8 s MISSED, reported). §16c (owner RULINGS 2026-09-12b/12d, lane `v2atom`): THE CONNECTED COMPONENT IS THE ATOM — `--torn-seams PACK_ROOT` prints the TORN-SEAM CENSUS over a WRITTEN pack (the plan argument is then the WRITTEN `o4_v2_placement_<ICAO>.json` and `--graded` is not read), and the same census prints automatically after `--write-pack`: sibling files of ONE placement that share an AUTHORED VERTEX (the key `obj8.solid_components` welds on, `round(x, 3)`) are two halves of one connected solid written at two zeros, with the base step per seam, the step histogram, the worst list and the per-class breakdown, and §10's line segments / §14a's basin arcs — the only lawful station cuts — counted APART.  Two bars, both 0: `torn seams outside line/arc pieces` and `single-component resources in >= 2 files`.  The instrument is the scout `v2lemd320`'s `tear.py`, promoted on its second use, and lives in `airport/placement_seams.py` (`census_torn_seams` / `census_torn_seams_lines`, re-exported through `placement_census`).  Measured on the live 1.0.320 LEMD pack it reproduces the owner's four sites exactly (`HANG3` 10 files / 14 seams worst 3.05 m; `green-LEMD50` 7 / 11.12 m; `Bridge2` 8 / 11.72 m; `green-STRT4` 53 files, `__b44` 16.29 m) and the class (2,554 seams, 1,994 over 0.30 m).  On matched replay arms the law takes LEMD 723 -> **0** seams and 128 -> **0** single-component splits (files 3,253 -> 2,804, plan stage 13.5 -> 10.2 s over 3 runs, round trip OK), OTHH 639 -> **1** and 165 -> **1** (files 1,897 -> 1,898). §16c (6) (RULINGS 2026-09-12h, round 2): `--contact-eps M` overrides `[placement] contact_eps_m` (2 mm) — components of ONE resource whose geometry comes within it, or whose parts the rebake plan's ε-contact graph already links, BIND into one rigid body for anchoring (one zero, the senior component's carrier): OTHH's `OTHH_Fuel_02_LOD0_007` carries two components 0.4 mm apart that the millimetre weld key reads as separate.  LEMD files 2,804 -> 2,776, seams stay 0, `Terminal4_48` zero spread 3.58 -> 0.69 m, plan stage 9.6 s (main 13.5). ROUND 3 (RULINGS 2026-09-12j): the entry now runs inside `harness/shared_repo_guard`'s WRITE GUARD and its before/after audit (a round-2 OTHH `--admit-skipped` run had created `Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text` in the SHARED repo with both lane-local cache env vars exported and nothing refused it); every run prints `[guard] shared repo UNCHANGED`.  `--rigid-reach M` overrides `[placement] rigid_reach_m` (2.0) — §16c (8): SOLID components of one resource within it chain into ONE rigid cluster, which is the atom of the BODY as well as of the cut (LINE objects excluded).  `carrier_fill_min` is DELETED from carrier candidacy (§16c (7)); the CLASS exclusion stays.  LEMD: `HANG3` 6 files / 1.37 m -> 2 / 0.45, `green-STRT4` 23 -> 15 files (spread 8.90 -> 3.73), files 2,776 -> 2,121, §16b wide 1,405 -> 967, seams 0, round trip OK; five largest rigid clusters are all SINGLE components (5,157 / 2,890 / 2,514 m — fences and VOR markers, not chained) and `green-TEJ3` stays 9 components / 9 clusters. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. **§17 CRITICAL MOTION IS READ** (owner RULINGS 2026-09-12am (2), lane `v2objmotion`): the graded surface's FACE ROLE under every foot (`airport/placement_boxes.GradedRoles` / `graded_roles_from_doc`, built from the SAME parsed `<ICAO>.graded.json` the sampler and the pads are, senior face by `precedence.toml`'s authority order, a 55 m grid over the faces' boxes) joined to §7's own float there (`airport/placement_motion.census_motion`, re-exported through `placement_census`): a body with a foot on a ROLLED-ON face (`law.tables.rolled_on_roles`) is ON PAVEMENT and every such foot is judged at `[cockpit] motion_step_m` 0.05 m, named with resource, foot coordinate, face role and SIGN. The block prints the count of bodies on pavement, the feet over the threshold, the worst ten, and the breakdowns by resource / face role / body class / anchor rule / size band, plus what the EYE reads at those feet (floating vs buried over `visual_m`) and the MEDIAN-anchor arm. BASIN bodies are counted APART (§14 (2) / 11al: a pit's zero is its rim and its floor feet are authored below it — they were LEMD's whole worst ten). Measured on the 1.0.320 LEMD frame: 493 of 2,153 bodies stand on pavement, 7,124 feet on 399 over 0.05 m; after the §17 anchor rule 6,635 on 407 (OTHH 6,234 → 3,877 on 113 → 103). RULINGS 2026-09-12ap (lane `v2pavefeet`): `--motion-rows OUT.json` writes §17's PER-BODY projection — one row per written body with its anchor, class, anchor reason and every ground-contact foot (lat/lon, authored y, surface z, face role, on-pavement, float) — the rows `census_motion` itself reads, never a second census (the scout's scratchpad projection, promoted on its second use). (E) THE SAMPLER HONOURS GRADED HOLES: a Delaunay over the emitted VERTICES spans a hole ring with triangles reaching from an apron vertex to a trench vertex, and LEMD read **592.22 m at a point whose ROLE is apron** six metres outside the hole — 12ap's two worst pavement feet (`LEMDblast__b1` +7.18, `Terminal4sBlue-STRT4__b1` −5.08) were that fabricated ramp, and the anchor correction is 6.91 m. A simplex CROSSING a hole ring with a step over `split_tol_m` is struck and a point inside one reads the nearest vertex of that simplex ON ITS OWN SIDE of the ring; measured narrowings: "centroid on no face" struck 8,689 of 47,287 simplices and cost 421 files / 435 off-sheet bodies, and a strike with no side-aware read cost 160. (B) §17 is judged at the GROUND-CONTACT feet — the in-band feet within `split_tol_m` of the lowest (`placement_motion.ground_contact_feet`); `contact_band_m` is shared law and unchanged, BOTH sets are sampled and the wider reading prints beside the judged one so the report states its own attribution. (A) `bind_ground_m` (`[cockpit] visual_m`) bounds §16c (7): a FOOTED body of ANOTHER member keeps the cluster only while its own zero is within it of the senior's, else it keeps its own anchor and is counted — the report prints `bound refused for ground N` with the worst refused disagreement and the widest RETAINED cluster zero-plane span. Matched arms, LEMD main → branch: CRITICAL MOTION 6,640 → 5,400 feet on 407 → 356 bodies, over 0.5 m FLOATING 663 → 128 and BURIED 1,109 → 808 (of which (B) alone 581 → 128 / 816 → 808), worst pavement foot +7.18 → +2.41 m, 74 binds refused (worst 2.38 m), files 2,107 → 2,149, seams 0/0, round trip OK, plan stage 10.19 → 10.03 s; OTHH 3,891 → 2,822 feet on 103 → 74, floating 332 → 12, §14 footless at datum 5 → 4, files 1,252 → 1,269, plan stage 60.8 → 61.4 s (the ≤ 60 s bar missed on BOTH arms). §16b's carried-piece float and wide counts move the WRONG way at both airports (LEMD 111 → 119 / 967 → 983, OTHH 126 → 135 / 75 → 78) and are named. §16d (owner RULINGS 2026-09-13h, lane `v2unboxed`): THE PLAN BOXES WHAT THE WRITER WRITES — a WRITTEN-FRAME bar beside the torn seams, `§16d bodies with written geometry > 1 m outside their geom_box` (`airport/placement_seams.census_outside_box`, printed after `--write-pack` and by `--torn-seams`, bar 0): `geom_box` was the hull of the ADMITTED PARTS while the writer emitted the source object's triangles regardless, so a component no part named (the FS2XPlane origin plate, an exporter's ground paint, a roof plate over the next hangar) rode a zero the body chose elsewhere and NO instrument read it — LEMD 1.0.325 live pack 378 of 2,109 bodies, 8 over a kilometre. Every connected component the writer will emit — draped ones included — is now PLACED: within `coarsen_reach_m` of a ground group's part hull it joins that group and `geom_box` grows to the hull of what the file will contain; beyond it, it is a FOOTLESS BODY §15's search places, or §16 (3)'s own ground (`--coarsen-reach 0` disarms the reach and the component joins the nearest body, the pre-§16d reading). The nearest-footed fallback is CAPPED at the same reach (`carrier_refused_nearest_beyond_reach`), and the COCKPIT block names the worst row by the centre of the BODY'S OWN written geometry, never the placement row (a shared-datum pack puts 96.5 % of its bodies on two points). `plan stage: N.NN s` is printed after the split — the number a round's budget is quoted in, timed exactly where the shipped engine's own `build_splits` call is, without the graded parse or the census. Matched dry arms on the 1.0.325 LEMD frame (the app's own arm reads a MESH sampler where the tool reads a Delaunay over the graded vertices — the two disagree on every surface-driven refusal and the bars are read dry-to-dry): outside-box 390 → **0**, nearest-footed over 100 m 29 → **0**, the four shadow plates +15.94/+15.73/+5.77/+1.72 → **−5.00 on their own ground**, `Cargo-TEJ1` on `NEWCO__b9` roof base 604.95 (bar 0.3 of 605.04), seams 0/0, §15 carried float 0/0, round trip OK, files 2,141 → 2,279, LEMD plan stage 13.6 → 17.8 s and OTHH ≈83 → 86.1 s (both bars missed on BOTH arms, named). It also fixed a latent WRITER defect: the cut file was named by its index in the LIVE body list while the DSF row is written on the plan's `body_id` name, so a body the cut left with no triangle shifted every later body's file one name down (`OldTerminal_FSX-DCNEUN`'s `__b0` row held `b1`'s object). §16d (4)-(6) (owner RULINGS 2026-09-13m, same lane, second frame KCLT 1.0.324): a CARRIED body's components group BY CARRIER — each ATOM (§16c (1)'s, so a rigid cluster is never divided) asks its own carrier question BEFORE the search, counted as `carried bodies cut by ATOM`, where §16a (1)'s after-the-fact cut could only divide the answer the whole body got (KCLT 5,295 carried bodies left uncut against 3 cut; a native pack's master roof model spans 1,774 m); §16c (7)'s 0.5 m ground bound is MEMBER-AGNOSTIC (12ap tested `member != top.member`, and a native pack's one-model-per-material member spans the airport: KCLT's `005_ALB__b9` sank 5.04 m into its pad on a same-member bind to an apron body 500 m away); and a FOOTED body whose ground contacts lie mostly inside one emitted `building` pad reads only the contacts ON it (`anchor_rule.pad_majority`; the anchor reason then says `on pad <ref>`). Matched dry arms at KCLT: `005_ALB__b9` -5.85 -> **+0.02** against its pad, widest retained cluster zero span 5.69 -> **0.64 m**, 473 carried bodies divided by atom, 61 bodies anchored on their pad, `building80`'s on-pad zero spread 1.03 m (the pad's own relief 1.19), §16d outside-box **0**, §15 carried float **0**, round trip OK 477/477, one new torn seam (+0.16 m, one shared vertex, named), files 473 -> 477, plan stage 8.65 -> 8.3-8.5 s. It also exposed a defect the atom cut made visible: a target group holding BOTH a cut piece and an untouched raw was read for its `tris` alone, leaving 990-3,280 triangles per placement claimed by no body (9 of KCLT's 103) for `obj8_split` to hand to the nearest one — the audit reads 0 of 103 after. **COST: plan stage LEMD 17.8 -> 25-46 s and OTHH 86 -> 136 s** (KCLT flat) — the per-atom carrier search, narrowed by a `coarsen_reach_m` span gate, a 64-atom cap, per-atom pids and a set-intersection contact count, and still needing the owner's approval and a Fable-5 review before it ships. **§16g (5)'s PER-PLACEMENT ROW CENSUS, DRY (`--dsf-dump DUMP.text`, owner RULINGS 2026-09-14bo, lane `v2leafframe`).** The dry path reads no DSF by design; given an EXISTING DSFTool text dump it also prints the `OBJECT_MSL` seats the writer would emit, from the SAME `footprint_unit.msl_seats_for_dump` call `placement_write.build_plan` makes — the per-row base (`msl_base_unit_pad` / `msl_base_own_feet` / `msl_base_deck` / `msl_left_to_the_drape` / `msl_off_sheet_left_draped`), the multi-anchor census beside it, and `|elevation - the design surface at the row's own feet|` over 0.5 m with the worst named. PASS THE PRISTINE DUMP (`<dsf>.anchor_bak...text`, `dsf_write.pristine_dsf_path`): a dump of an ALREADY-WRITTEN pack reads the app's own absolute elevations back as authored offsets and reported 1,055 rows 22 m off their feet that do not exist. Measured at LEMD on the pristine dump: `OBJECT_MSL` rows **1,481 -> 0** (1,466 left to the drape, 196 standing on their unit's pad at offset 0, 5 off-sheet) — every LEMD multi-anchor row is a plain `OBJECT` with no authored offset, so the drape at its own feet IS the law's answer. Nothing is written and no DSF is decoded. Twin: `tests/auto_patch_v2/test_v2leafframe.py`. |

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

