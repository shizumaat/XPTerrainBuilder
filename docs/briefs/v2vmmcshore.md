# Brief pack — lane `v2vmmcshore`

Base: main `6fecb62b` · generated 2026-09-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

VMMC: a tunnel serves the field or is not built; the shore trims the zones; the sea wall (§34 (12), §37 (11))

## The brief

Owner 15f (VMMC 1.0.340). Two region trims at their single derivation sites — never per-consumer vetoes (RULINGS 2026-08-30l). Sites: `planar/structure_approach.py` (`mouths()` the §29 (1) gate → add the serves-the-field predicate: the bore's covered stretch passes under airside pavement / a pad or unit footprint / an authored deck), `airport/deck_signature.py` (`is_tunnel_way`), `planar/structures.py` (the airside-cut exemption list: `ramp_cuts_runway_family` → airside role set; the water clip), `planar/structure_deck.py` (a bridge severs only when it CROSSES the bore), `planar/zones.py` (the water clip; the quay; the sea wall breakline pair), the water source: the flat-site pass's water mask (grep "is WATER and is CUT OUT" in `pipeline/` / `classify/`) and the coastline ways in the OSM feeds (`OSM_data/+20+110/+22+113/*coastline*`), and the tile's sea source `O4_Vector_Map include_sea` for the water level. Census: `tools/check_grade.py` (`sea_wall` family; exempt sea-wall edges from `strip_seam_tear` / `adjacent_ground_step`), `verify/census.py`. Tools: `tools/osm_site.py`, `tools/role_overlap_read.py`, `tools/mesh_region_tris.py --z-xref`, `v2_solve_replay --capture` (make and register a VMMC capture; none exists). Sea-wall geometry: a breakline pair — the quay/pavement edge vertex at Z and a coincident (or ε-offset seaward) shore vertex at the water level; measure that the mesh emits it as a vertical face (the tile's `.poly` breaklines; `O4_Vector_Map` breaklines from 14-series work). Bank stays OFF. Do not touch solve/design*.py, constraints/cluster_pad.py (lane v2padqp), structure_underpass.py beyond the airside-deck rule (lane v2lemdstruct2 owns §34 (5) (b) — coordinate through the report, not the code: if you need the underpass path, say so and stop).

## Bars

- Owner site 22.1618794, 113.579745: NO tunnel face, rim or ramp within 300 m; every VMMC corridor (three groups today: shore 6 ramps/11 rims; 578–782 m; 1,132–1,182 m) either NAMED with the cover element it passes under (§34 (12) (1)) or gone; count 11 → N with each survivor's covered element quoted.
- Taxiway pav5 (code E, junction) whole again: one face set at the design surface (6.10 ± its own law), no vertex below 5.9 m; `ramp_cuts_runway_family` generalised to the airside role set (taxiway/junction/apron/stub/parallel) with its twin.
- Zero patch vertices seaward of the coastline (ways −687/−913); zero zone faces crossing the coastline (13 today); the doubled water plane gone — confirmed with `mesh_region_tris.py --z-xref` on the closing build (name the triangles at z = 0 seaward, before → after).
- At the taxiway-by-the-sea (the screenshot; worst tear today 22.16232, 113.58138): the pavement edge to the water is a `sea_wall` (vertical, drop ~6.1 m, no slope), quay/zone per §37 (11) (2)–(3); `strip_seam_tear` 61 → 0 with sea-wall edges excluded by the NEW family, `adjacent_ground_step` 6 → 0 or named; `sea_wall` in `LAW_FAMILIES` with its twin; the census's verdict FAIL → PASS or each survivor named.
- The consumer census tables (§34 (12) and §37 (11)) written in the MEASURED blocks BEFORE the first edit — one table each, every reader of the corridor region / the water mask / the zone region / `beyond_zone2`.
- Census by family, matched replay pair at VMMC (before → after; no family worse by > 5 % unnamed); LEMD and OTHH replay pairs to prove no regression where tunnels DO serve the field (LEMD 50 tunnels / 7 decks / 1 underpass, OTHH's terminal corridors 14ab — counts unchanged or each change named).
- Suite by FAILED lines (zero); ONE VMMC build (`build_airport.py VMMC`, ~16 s) as the closing test; `shared repo UNCHANGED`.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/planar/zones.py`, `Ortho4XP/src/auto_patch_v2/planar/structure_approach.py`, `Ortho4XP/src/auto_patch_v2/planar/structures.py`, `Ortho4XP/src/auto_patch_v2/airport/deck_signature.py`, `Ortho4XP/src/auto_patch_v2/law/structures.toml`, `Ortho4XP/src/auto_patch_v2/law/zones.toml`, `Ortho4XP/tools/check_grade.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/solve/design.py`, `Ortho4XP/src/auto_patch_v2/constraints/cluster_pad.py`, `Ortho4XP/src/auto_patch_v2/planar/structure_underpass.py`

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

## Spec (design-surface) §37

## §37 A ROAD KEEPS ITS OWN LONGITUDINAL LAW; A ROAD FLIPS BY SHARE; THE BANK IS EMITTED WHERE IT IS LOAD-BEARING (Fable 2026-09-13; RULINGS 2026-09-13q, KCLT items 5, 7, 8; CYXY item 2) — lane `v2roadcap`

Scout `v2kclt1t`: (5) the service road down to KCLT's east access road falls 1.4 %
where its DEM falls 9 % and ends +14.22 m in the air — `constraints/roads.py:38-70`
`road_law_caps` gives a road the STRICTEST longitudinal cap of any governed face it
touches (lateral contiguity, 2026-08-02 cl. 2) — 0.015 on 42 of KCLT's 121 groundside
faces; the 1:3 bank then walks 34 m to daylight it (lawful on that ray; airport-wide
17.6 % of foot stations are steeper than 1:3, max 1:0.4). (7) shapeID 791 (`dsf:pol82`,
8.4 m wide, 1,203 m perimeter, 575 m of road centreline inside, no taxi centreline —
a STRIP by evidence) was flipped to `apron` by §27 on 15.3 + 10.5 m of lateral apron
contact (2 % of its perimeter) and, under the apron's 1.5 %, climbs +12.3 m off its
ground; 60 ribbon aprons (< 12 m wide) carry 108,744 m². (8) the `bank_foot` ring is
the 1:3 transition from the patch COVERAGE (the union of every planar face — not an
aerodrome boundary; KCLT has none in OSM) to the DEM, emitted at every station: KCLT
34.2 km (42 % of stations carry < 0.5 m; 5.8 % over 5 m, max 19.2 m, stand-off to
89 m; 451 chords over 30 m up to 5.6 m off the DEM mid-chord), CYXY 14.8 km (51 %
under 0.5 m, max 2.4 m, none over 5 m).

1. **LATERAL CONTIGUITY BINDS THE TRANSVERSE CAP ONLY.** A road-family face takes
   the strictest cap of its contiguous faces for its TRANSVERSE law (it must not
   tear against the surface beside it); its LONGITUDINAL cap stays its own
   (`service_road` 8 %). Consumer census first (§28 frontages, §20 pad levels,
   `road_cross_section`, the lateral-contiguity family). KCLT's east road descends
   to its DEM.
2. **A ROAD FLIPS BY SHARE, A LOT BY EDGE.** §27's lateral test stays as ruled for
   lot-class faces (≥ 10 m); a STRIP-class face (a road by evidence) flips only when
   its lateral airside contact is at least `[lot] road_airside_edge_frac` (0.2) of
   its perimeter — LEMD's 61 apron-side lanes (edges to 828 m) stay apron; a
   through-road touching an apron for 2 % of its length stays a road (owner 13j
   item 7). Consumer: `airside_edge_flip` only.
3. **THE BANK IS EMITTED WHERE IT IS LOAD-BEARING.** A foot station is emitted only
   where |z_ring − DEM(foot)| exceeds `[design] bank_materiality_m` = `bank_min_width_m
   × bank_slope` (1.65 m); elsewhere the ring carries no foot and the mesh's own
   interpolation blends the sub-metre difference. Long foot chords are split at
   `bank_chord_max_m` (30 m) so no chord stands more than `split_tol_m` off the DEM
   mid-chord. The bank's own law is unchanged: it still daylights at 1:3 where it is
   emitted; the real reduction comes from (1) and (2), which remove the fill the
   bank was covering. The owner's question ("do we need it at all?") is answered
   with the numbers: CYXY's ring vanishes; KCLT's shrinks to its load-bearing
   stations, re-quoted after (1)/(2).
4. **BARS**: KCLT `dsf:pol51` within 2 m of its DEM at its east end (today +14.22),
   `service_road` off-DEM max 14.2 → < 3 m; shapeID 791 a `service_road` (its fill
   +12.3 → on its ground); ribbon aprons 60 → quoted; LEMD's §27 flips unchanged (dry
   replay); bank foot stations KCLT 1,855 → N (load-bearing only), CYXY 649 → 0 (dry
   replay), stations steeper than 1:3 quoted; chords over 30 m 451 → 0; ONE
   `--engine v2` KCLT build with the cockpit block first (critical motion 16 → quoted,
   the three item-5 cliffs gone); census; twins; suite. The census's 215 m apron
   step at 35.2138431, −80.9480288 is the z = 0 crater (lane `v2zerocrater`), excluded.
### §37.1 CONSUMER CENSUS (owner RULINGS 2026-08-30l), completed BEFORE any consumer was edited — lane `v2roadcap`

**A. THE LATERAL-CONTIGUITY CAP** (`constraints/roads.road_law_caps`; §37 (1)).

| # | consumer | reads | RULE |
|---|---|---|---|
| L1 | `constraints/roads.road_within_shape` | `road_law_caps` | **EDITED**: `cap_l` is the ROLE'S OWN longitudinal (`service_road` 8 %); `cap_t = min(role transverse, contiguity cap)`. |
| L2 | `constraints/taxi.triangle_planes` (`plane_gradient`) | `road_law_caps` | **EDITED — the contiguity min is DROPPED.** `|∇z| ≤ cap` is ISOTROPIC: a plane row has no transverse component to bind on its own, so it prices at the face's own longitudinal cap. Before §37 this branch flattened a road triangle in every direction. |
| L3 | `pipeline/publication.face_tags` | `road_law_caps` | **EDITED**: stamps `o4_grade_law_cap_t`, never the bare `o4_grade_law_cap` (which binds a way's WHOLE within-shape reading in the v1 census). |
| L4 | `pipeline/publication.publication` `station_caps` | `road_station_caps` | UNCHANGED. The per-station vector is the WALK, not a cap assignment; v1's fourth reader still reads it and, with it present, mints no row BY CONSTRUCTION (`_built = min(eff, published) ≤ _law_here`). |
| L5 | `constraints/contiguity.{station_caps,road_station_caps,cap_at,face_station_cap}` | the probe walk | UNCHANGED — the walk is the same; only what the cap BINDS changed. |
| L6 | `verify/contiguity.lateral_contiguity` | `p.cap(sh)` + published stations | **EDITED**: prices `p.cap_t(sh)` — the transverse binding — against the re-walked cross-section's strictest longitudinal law. |
| L7 | `verify/frame.Patch.cap` / `Shape.law_cap` | `law_caps` mapping | **EDITED**: `cap()` is now the role's longitudinal alone; new `cap_t()` folds the binding in. `Shape.law_cap` MEANS the transverse binding; every `census(surf, law, pub, road_law_caps(...))` call site is unchanged. |
| L8 | `verify/within.within_shape` / `road_cross_section` | `p.cap`, `rc.transverse` | **EDITED**: `cap_t = p.cap_t(sh)`; the longitudinal cap is the role's. |
| L9 | `verify/within.plane_gradient` | `p.cap` | follows L7 — the role's own longitudinal. Mirrors L2, so generator and reader move together. |
| L10 | `check_grade._role_grade_limit` / `_lateral_cap_tag` (`o4_grade_law_cap`) | the way tag | UNCHANGED IN MEANING. v2 no longer stamps it for contiguity, so a v2 road reads its role cap; **every v1 patch reads exactly as before** (08-02 clause 2 is untouched in `auto_patch/`). |
| L11 | `check_grade._xsec_allowance` (the `road_cross_section` family) | `cap_l` | **EDITED**: `min(road_cross_section_cap(cap_l), o4_grade_law_cap_t)` — the ONE site at which the contiguity cap reaches the v1 census. |
| L12 | `check_grade._check_lateral_contiguity` (the fourth reader) | published `station_caps` | UNCHANGED — vacuous by construction on a v2 sidecar (L4). |
| L13 | `emit/osm_adapter` oracle alias (`extra["o4_grade_law_cap"]` `prior`) | the face tags | UNCHANGED CODE. `prior` is now absent for road-family aliases, which is the intent: an alias's LONGITUDINAL cap must not be tightened by a transverse law. |
| L14 | §28 GROUNDSIDE FRONTAGES (`constraints/pad_frontage_gs.py`, `verify/frontage`) | pad ↔ frontage rows | UNAFFECTED — neither imports `road_law_caps`; a frontage row's cap is the pad law's. |
| L15 | §20 PAD LEVELS (`constraints/pads`, `[design] pad_level_rulings`) | pad rim / pavement edge | UNAFFECTED — same; and the relaxation FREES the road, it never pulls a pad (the one-way rulings). |
| L16 | `solve/why.family_of` (`road_within_shape` / `road_cross_section`) | the row's source | UNAFFECTED — labels unchanged. |
| L17 | `auto_patch/` v1 (`lateral_contiguity.py`, `grade_graph._body_cap`, `layout.py:3120`) | v1's own stamping | UNTOUCHED — §37 is v2 law. |

**B. `airside_edge_flip`'s callers** (§37 (2)).

| # | consumer | reads | RULE |
|---|---|---|---|
| B1 | `classify/roles.classify` | the ONE call | UNCHANGED signature and return; the share test lives inside the one derivation site (§27 (2)). |
| B2 | every downstream consumer of `role` | `law.tables.role_side` | UNAFFECTED BY CONSTRUCTION — `side` stays a pure function of `role`. |
| B3 | `tools/role_edge_census.py` | the emitted patch | UNAFFECTED — it reads the product, and reports the share it now measures against. |

**C. THE BANK's readers** (§37 (3)). A foot ring may now be one OPEN chain per load-bearing run.

| # | consumer | reads | RULE |
|---|---|---|---|
| C1 | `emit/osm_adapter` bank branch | `closed = vertices[0] == vertices[-1]`, `len ≥ 3` | UNCHANGED — it ALREADY emits an open chain (the tile-piece case, §9.4 deviation 2). Runs are padded so no chain is under 3 nodes. |
| C2 | `emit/osm_adapter.write_tile_pieces` | breakline runs | UNCHANGED — a chain splits at a seam exactly as a ring did. |
| C3 | `O4_Vector_Map.include_patches` | every CLOSED way | An OPEN `bank_foot` way is a constrained LINE carrying altitudes: it seeds no INTERP_ALT face and blocks no water flood. CORRECT — where no foot is emitted there is no bank to seed. |
| C4 | `O4_Mesh_Utils._bank_rings_from_patches` / `bank_annulus_polygon` | CLOSED `bank_foot` ways only | **EDITED**: an open chain is closed into its RIBBON — the chain and its own nearest-point projection onto the design coverage — and REFUSED when the swept area is implausible for a bank of that length. Without this, one immaterial station would have taken the whole ring's annulus out of the linear blend. A refusal leaves those vertices to the harmonic extension, which is this module's standing rule. |
| C5 | `O4_Mesh_Utils.bank_annulus_blend_values` / `_bank_foot_along_normal` / `BANK_BLEND_STATS` | the annulus + the feet | UNCHANGED via C4. Where a run carries no foot, `interpolate_free_interior_altitudes`' harmonic extension carries the sub-materiality difference — §37 (3)'s own words. |
| C6 | `O4_Mesh_Utils.bank_annulus_region_areas` (Triangle's region sizing) | `bank_annulus_polygon` | follows C4. |
| C7 | `check_grade._parse_osm` / `ROLE_LESS_FEATURE_CLASSES` | `o4_feature=bank_foot` | UNCHANGED — routed to `feature_out` open or closed; it mints no row (§9 A10/A11). |
| C8 | `verify/frame.Patch.of` | `runway_profile` / `structure_rim` kinds | UNAFFECTED (§9 A8). |
| C9 | `emit/surface.GradedSurface.to_json` / `SCHEMA` | breaklines as vertex tuples | UNAFFECTED. |
| C10 | `emit/rebake.deck_datum_from_surface`, `airport/rebake_plan` | the PRE-bank surface | UNAFFECTED (§9 A7). |
| C11 | `emit/terrain_edge.no_bank_region` | the banked region cut | UNCHANGED — the region is cut before any station is emitted. |

### §37 **MEASURED** (lane `v2roadcap`, 2026-09-13, branch `claude/v2roadcap`, base `ec8723e9`)

**THE CLOSING TEST MOVED FROM KCLT TO LEMD — KCLT CANNOT BE BUILT ON THIS
CORPUS, AND THE LANE DID NOT MAKE IT BUILDABLE.**  `build_airport.py KCLT
--engine v2` refuses at the loader, before classify:

> `KCLT: the pack DSF …/+35-081.dsf.anchor_bak is newer than every cached
> text dump under …/Airport_mod_cache/Nimbus Simulation - KCLT V1.4 …`

The refusal is `airport/load.py:289` and it is CORRECT.  The PRISTINE read
frame (RULINGS 2026-09-11m) reads `+35-081.dsf.anchor_bak`, and
`dsf.find_text_dump` keys the candidate dumps on *that* basename: the
shared mod cache holds `+35-081.dsf.{1334c2dd,7bf41307,b698274b}.text` —
dumps of the WRITTEN DSF — and **no `+35-081.dsf.anchor_bak.*.text` at
all** (LEMD, OTHH, NZQN and NZVL each have one; KCLT has never had one).
The cure is `--refresh-data airport_mod_cache`, which this lane's brief
forbids and which changes every lane's corpus stamp.  **It is the
orchestrator's call, not the lane's.**  The same guard is what refused the
scout's `explain KCLT` (13q).  Consequences, stated rather than papered
over: every KCLT bar of §37 (4) — `dsf:pol51`, shapeID 791, the ribbon
aprons, the cockpit block, the KCLT census — is **NOT MEASURED**.  What is
measured below is LEMD (the closing build) and CYXY (the control), both
`--engine v2`, both against a `--base-arm` at the same base `ec8723e9`,
plus the KCLT BASE numbers read offline from the 1.0.324 products.

#### KCLT, BASE ONLY (the 1.0.324 products, read with the emitter's own instruments)

Reproduced exactly, so the sites are not in doubt — only the fix is
unmeasured:

| site | 1.0.324 |
|---|---|
| `dsf:pol51` shapeID 946 | `o4_grade_law_cap=0.015`, worst **+14.22 m** at 35.2074982, −80.9296586, east end +8.09 |
| `dsf:pol51` shapeID 945 | `o4_grade_law_cap=0.015`, worst +14.07 m, east end +8.02 |
| `service_road` (whole airport) | 864 vertices, **max +14.22 / −4.14 m** off the DEM |
| shapeID 791 (`dsf:pol82`) | role **`apron`**, 81 vertices, **+12.33 m** at 35.2209280, −80.9275739 |
| bank | 49 closed rings, **1,855 stations**, 34,212 m, **451 chords over 30 m**, max chord 130.1 m |
| bank materiality (§37 (3), read with `_inner`'s own rule) | **526 of 1,855 stations (28.4 %) load-bearing** at 1.65 m; 57.8 % carry over 0.5 m, 7.1 % over 5 m |
| ribbon aprons (< 12 m min-rect width, emitted apron ways) | **43 / 5,010 m²** — NOT the spec's 60 / 108,744 m², a different instrument; quoted here on the one used for both arms |

#### LEMD — the closing build

ONE `--engine v2 --patch-only` build per arm, one tree, one corpus
(`e512b4ea8cca`), both at base `ec8723e9`, both rc 0, shared repo
UNCHANGED:

* BASE — tag `v2roadcapLEMDbase`, 523.6 s engine, artifact ledger
  **`11c63567bce3`**;
* §37 — tag `v2roadcapLEMD2`, 510.5 s engine, artifact ledger
  **`648c9198fba3`** (the first §37 arm, `v2roadcapLEMD`, 400.0 s, is the
  same patch outside the bank: it carried the padded-run overlap the
  twin now forbids).

**§37 (2) — LEMD's flips STAND, PROVEN BY IDENTITY.**  The two arms'
patches carry **1,075 role-carrying faces with byte-identical roles: 0
changed**.  `tools/role_edge_census.py` reads the same figure on both:
124 groundside shapes, 28 sharing ≥ 10 m with airside pavement, **0
substantive (all 28 slivers, 789 m²), 0 LOT-class**.  A lane that runs
828 m ALONGSIDE its apron is a share, not a graze; none came back.

**§37 (3) — the bank.**

| | BASE | §37 |
|---|---|---|
| foot nodes | **2,594** in 48 closed rings | **836** in 78 chains, 76 open |
| foot length | 60,986 m | **11,544 m** |
| chords over 30 m | **820** (max 131.7 m) | **0** (max 30.0 m) |
| duplicate foot coordinates | **5** (pre-existing) | **0** |
| load-bearing stations | — | **489 of 2,596** (2,107 under the 1.65 m floor; 11 rings carry no bank at all); 153 split stations |
| bank slope p95 / max |  0.433 / 1.255 | **0.580** / 1.260 |

The slope p95 rises because it is the pre-existing `slope to the nearest
DESIGN vertex` statistic now read over LOAD-BEARING stations only — the
minimum-width feet that held it down are exactly the ones §37 (3)
removes.  It is the §9.5 residual, reported and not fixed.

**§37 (1) — THE CENSUS MOVED THE WRONG WAY AT LEMD, AND THE LANE DOES NOT
PAPER OVER IT.**

| harness census | BASE | §37 |
|---|---|---|
| LAW-TRUE | 3,573 (within 3,570 / cross 3 / steps 0) | 3,798 (3,795 / 3 / 0) |
| **ADJUDICATED** | **1,143** — airside 1,127 / gs 15 / mixed 1 | **1,379** — airside **1,345** / gs 33 / mixed 1 |
| `within_shape` | 2,792 | 2,821 |
| `taxi_box` | 204 | **326** |
| `airside_no_step` | 419 | **481** |
| `road_cross_section` | 0 | 2 |
| `strip_transverse` / `strip_longitudinal` | 43 / 15 | 49 / 20 |

**+236 adjudicated, +218 of it airside — and the roads are groundside.**
Attribution, in the order the rulings require:

1. **It is not §37 (2)**: the classification is byte-identical (above).
2. **It is not §37 (3)**: the bank is built AFTER the solve and is
   census-skipped; the pre-fix and post-fix §37 arms — which differ ONLY
   in the bank — census **identically** (3,798 / 1,379, family for
   family).  The same holds at CYXY (1,049 / 345 in both).
3. **§37 (1) is a STRICT RELAXATION of the road family, proven by
   construction.**  The transverse cap is arithmetically unchanged —
   `min(rc.transverse, cap_l)` with `cap_l = min(long, law_cap)` equals
   `min(rc.transverse, long, law_cap)` — and the longitudinal cap only
   ever rises (0.015 → 0.080 on a contiguous road).  The generator row
   COUNTS are identical in both arms, line for line, all 62 of them.  So
   no row was tightened and none was added.
4. **What is left is the LP landing on a different optimum of an
   UNSETTLED system.**  Both arms report `HARD SET NOT SETTLED` (2 and
   25 of 126,696 rows violated) and `LAG NOT SETTLED`; the assembled
   design system moves 64,902 → 66,830 rows (the one-sided split, not
   the generators); and the same mechanism at CYXY moves the census the
   OTHER WAY, −61 adjudicated / −75 airside.  Non-monotone across two
   airports from one strictly-relaxing change is the signature RULINGS
   2026-09-12i named for §27's tunnel ramp: an LP re-solve of a free
   interior, not a mechanism.  **The census is not the objective.**
5. **What this lane did NOT do**: it did not tune the objective, gate the
   change, or iterate a third time.  The regression is REPORTED with its
   site numbers for the owner's adjudication.  Nothing here says the
   +218 rows are lawful — only that they are not a groundside pull the
   code can be shown to make.

#### CYXY — the control, both arms at `ec8723e9`, one tree, one corpus

| | BASE (`163c4e7f50dc`) | §37 (`cc9c86490555`) |
|---|---|---|
| harness census LAW-TRUE | 1,047 | 1,049 |
| harness census **ADJUDICATED** | **406** (airside 381 / gs 25) | **345** (airside **306** / gs 39) |
| `within_shape` | 915 | 968 — the whole rise is `withdrawn_law_05aa` taxi chords, 625 → 688, never adjudicated |
| `road_cross_section` | 12 | 17 |
| `taxi_box` | 34 | **17** |
| `airside_no_step` | 74 | **40** |
| `plane_gradient` | 1 | **0** — §37 (1)'s L2: the isotropic plane row is no longer bound to a contiguous class |
| `transverse` | 9 | 5 |
| bank foot nodes | **649** in 20 closed rings | **153** in 19 chains, all open |
| bank foot length | 14,835 m | **2,346 m** |
| bank chords over 30 m | **218** (max 82.3 m) | **0** (max 29.8 m) |
| bank load-bearing stations | — | **79 of 648** |
| duplicate foot coordinates | 0 | 0 |
| groundside shapes ≥ 10 m airside edge, substantive | 3 (10,295 m²) | 4 (11,546 m²) — one road came back, exactly §37 (2) |
| `service_road` off-DEM > 0.5 m | 83 / 292 (max 2.99 m) | 93 / 314 (max 3.14 m) |

**−61 adjudicated at CYXY, −75 of them airside**, the gain in
`airside_no_step` (74 → 40) and `taxi_box` (34 → 17).

**CYXY's ring does NOT vanish.**  §37 (3) predicted 649 → 0 from the
scout's headline ("max 2.4 m").  Read with the emitter's OWN inner-end
rule — the nearest point of the coverage with its z interpolated ALONG
the boundary edge, which is `emit/bank.py::_inner`, not the nearest
design VERTEX — CYXY carries 115 stations over 1.65 m and 27 over 5 m.
The measured answer to the owner's question "do we need it at all" is
therefore: **yes, but only for a sixth of it** — 79 load-bearing
stations, 2,346 m of foot instead of 14,835 m, 84 % of the ring gone.
At LEMD the same reading leaves 489 of 2,596 and 81 % of the foot gone;
the KCLT products read 526 of 1,855 (28.4 %).

#### A DEFECT §37 (3) INTRODUCED AND THE TWIN NOW FORBIDS

Padding each load-bearing run separately makes two runs one station
apart OVERLAP, and two chains over the same ground re-emit the same edge
on two sets of nodes — the duplicate constrained segments RULINGS
2026-09-09t measured Triangle's recovery spinning on.  Measured on the
first arms: **3 duplicate foot coordinates at CYXY, 14 at LEMD**.  The
padding is now part of the MEMBERSHIP (`keep[i] = flags[i-1] or flags[i]
or flags[i+1]`, then maximal cyclic runs of `keep`), twinned, and both
arms read 0 — the LEMD base's own 5 duplicates are gone with them.

#### THE CLOSING BUILD OF THE ARM AS RULED (RULINGS 2026-09-13dh)

ONE HECA build of `claude/v2roadcontact` **`9eaebbf8`** on merged main
`38dd98be`, tag **`v2roadcontactHECA3`**: **rc 0**, 332.5 s,
`status feasible`, `body_sha 8bbae5f33254`, artifact ledger
**`5e3f94ef2db6`**, **`[guard] shared repo UNCHANGED`** (full-surface
before/after snapshot), lock churn 18 operations (coordination state).
v2 verify 21,797 rows and **`verify_defects {}` — the DEFECT families the
app's driver gates on are EMPTY**.

| the built patch | value |
|---|---|
| ADJUDICATED | 14,850 — **airside 14,506 / groundside 300** / mixed 44 |
| LAW-TRUE | 33,242 |
| `road_cross_section` | **27** (all groundside) |
| `transverse` | 1,575 (airside 1,409 / groundside 166) |
| `road_coverage_join` | 0 |
| `route0`'s end vs the nearest airside edge (`pav74`, 4.34 m away, level 106.627) | **106.65 — +0.023 m** (shipped 1.0.329: +1.474 m) |
| the item-4 pair over 3.05 m | **0.05 m — 1.6 %** (shipped 1.0.329: 1.30 m, 42.6 %) |

The build's ABSOLUTE census is not comparable to the round-1 build
(`v2roadcontactHECA2`, 12,771 adjudicated): main moved three merges in
between — §40's runway shoulder alone takes `transverse` 790 → 1,575 and
`runway_crown` 40 → 183 on both sides of any road arm. The before → after
attribution is the MATCHED REPLAY PAIR above, both arms cut from the same
base.

#### Build-time impact statement

Bank pass: CYXY 0.14 s both arms, LEMD 0.54 → 0.51 s.  §37 (1) removes a
`min`; §37 (2) adds one comparison per candidate; §37 (3) reads `_inner`
for every region station instead of only for emitted ones and re-reads it
for the kept ones, which the bank pass absorbs.  Whole-build wall is a
re-solve of a changed system on a machine running four lanes
concurrently, so no A/B is quoted (standing law: never one run per side).
Nothing here is within 1 % of either budget.

#### What this lane did NOT do

KCLT (blocked — the pristine-DSF dump, above); the five-airport sweep
(the orchestrator's, once per merged batch); any `--refresh-data`; any
new tool (nothing here needed one — the bank's own census is
`BankReport.line()`, the share census is `tools/role_edge_census.py`,
the defect counts are `tools/harness/census.py`), so no `tools/INDEX.md`
row; any merge.

### §37 (5) THE SECOND MECHANISM UNDER THE EAST ROAD (Fable 2026-09-13; RULINGS 2026-09-13ab) — lane `v2roadcap2`

Scout `v2roadcapkclt` on main 064e244e: §37 (1) moved `dsf:pol51` 0.94 m
(+14.22 → +13.28 m) — the DEM grade along its chain is 6.8 %, under the 8 %
road cap, so the longitudinal cap was never what held it (follow ratio
0.287 over 179 m). `dsf:pol82` (owner's shapeID 791) is STILL `apron` at
+11.52 m though §37 (2)'s share rule should have left a face with 2 % of its
perimeter on airside a road. Both attributions were incomplete. The lane
first makes `explain KCLT` run (the `planar.__main__.default_inputs` half of
the 13q chip: honour `O4_AIRPORT_MOD_CACHE_DIR` / the harness redirect as
`build_airport.py` now does — one resolution, not two), then NAMES the rows
holding `dsf:pol51` up (transverse rows to an apron edge? a bank or zone
band? a pad frontage? the `taxi_trend` of a neighbour?) and the PASS that
classes `dsf:pol82` apron (scorer role before §27, or a share read on the
wrong perimeter), and fixes what it names.

BARS (KCLT, ONE build): `dsf:pol51` within 2 m of the DEM over its chain
(follow ratio ≥ 0.8), no service road over 3 m off the DEM airport-wide
(today max +13.28 / −4.25); `dsf:pol82` classed `service_road` on its own
ground; the 1:3 bank at the east edge shrinks with the fill it daylighted;
cockpit CRITICAL motion ≤ 9 (13ab's block) with no new row on the east road;
LEMD role census byte-identical (§37 (2) holds: the 61 apron-side lanes stay
apron); suite twice.

### §37 (5) **MEASURED** (lane `v2roadcap2`, 2026-09-13, branch `claude/v2roadcap2`, base `2002c7dc` + main `05050624`)

ONE `--engine v2` KCLT build, tag **`v2roadcap2`**, 371.1 s engine / 418.5 s
wall, rc 0, `status optimal`, `body_sha a7651dd35206`, artifact ledger
**`0e50c1a921f1`**, `[guard] shared repo UNCHANGED`.  The BASE it is quoted
against is scout `v2roadcapkclt`'s build on main `064e244e` (RULINGS
2026-09-13ab, ledger `2951cfc994bd`) — a DIFFERENT sha, stated because this
lane did not spend a second 7-minute build on a control the ledger already
holds.

#### THE INSTRUMENT

`explain KCLT` and `v2_solve_replay --capture KCLT` RUN in a lane worktree,
under `O4_AIRPORT_MOD_CACHE_DIR` pointed at a copy-on-write overlay, with the
shared repo untouched.  Three halves, of which the lane wrote two:

* the mod-cache resolution — **the owner's own `modcacheguard` chip, main
  `05050624`**, merged into this branch; the lane's parallel implementation
  was dropped in its favour;
* `tools/v2_solve_replay.py --capture` now makes its own PRISTINE pack dump
  through the build entry's own `auto_patch.engine_v2.fresh_pack_dump` (one
  implementation, three callers).  v2 never runs DSFTool itself and KCLT has
  never had a `+35-081.dsf.anchor_bak.*.text`, so without this every capture
  of KCLT refused at `airport/load.py:289` whatever root it resolved;
* `capture_has_groups` read `bool(groups.groups)` and so refused every
  COMPLETE capture of an airport that HAS no groups — **KCLT partitions
  7,163 bodies into 0 groups**.  The predicate is now "the derivation ran";
  `partition is None` is what actually catches a pre-12u capture.

#### (b) `dsf:pol82` — ATTRIBUTED, FIXED, MEASURED

13ab offered two hypotheses ("the scorer's role before §27, or §37 (2)'s
share read on the wrong perimeter").  `explain KCLT --at
35.2208425,-80.9278375` names a third, and it is neither:

> `cell 226: role=apron ... ref=dsf:pol82` — `source_class=lot`,
> `source_reason=5 road(s) reach it (04u), no taxi centreline, no startup,
> width 8.4 m`, `airside_edge_m=20.8`, `airside_edge_flip=1`,
> `airside_edge_round=2`, `airside_edge_was=parking_lot`.

§27's flip is READ CORRECTLY on the right perimeter, and the scorer never
touched the face.  The face was born **`parking_lot`**, so
`airside_edge.airside_edge_flip`'s `was_road[i]` is False and §37 (2)'s share
test — which asks whether a face was born `service_road` / `service_junction`
— never applied; the LOT rule (20.8 m ≥ `airside_edge_min_m` 10 m) flipped it.

Why it was born a lot is `classify/sources.py:_record`.  `narrow_road_width_m`
(12 m) says in its own words "a source polygon at most this wide that carries
ANY road centreline IS the road", but its branch is gated on `carries` =
`road_m ≥ min_road_fraction × HALF-PERIMETER`.  On a ribbon the half-perimeter
is a LENGTH, not a width: `dsf:pol82` is 8.44 m × 601 m, so `carries` demanded
**120.3 m** of mapped centreline and OSM maps **70.5 m** inside it (the
centreline wanders in and out of an 8.4 m page; five roads reach it).  The
strip branch never fired, and the face fell through to the LOT ladder's
weakest rung — `reach > 0`, RULINGS 2026-09-04u.  **Twelve KCLT pages
6.7–10.3 m wide read the same way.**

THE LAW (`[lot] min_lot_width_m` = 11.0 m): a 90-degree car park's minimum
module is one 5.0 m stall row plus one 6.0 m one-way aisle.  In the band
`[service.road_width_m, min_lot_width_m]` = [6.0, 11.0] m a page never reaches
the two WEAKEST lot rungs (`carries_osm`, the 04u `reach` rung), and it is the
ROAD where it carries a road centreline that is not noise
(`osm_roads.min_len_m` 10 m).  MAPPED evidence still outranks the width in
both directions: `amenity=parking` cover, an OSM parking aisle, `aeroway=apron`
cover, an apron name and a 1300 startup all keep their verdicts.  BELOW 6.0 m
the page is an EMIT SLIVER and §27's own sliver class owns it — the first arm
of this rule took 26 LEMD slivers (`dsf:pol255#2` and family, 0.1–0.3 m across)
out of the lot class and moved LEMD's cell count 597 → 578 for no reason
connected to §37 (5); the floor is why the rule is a band.

| KCLT | BASE (13ab, main 064e244e) | §37 (5) (`0e50c1a921f1`) |
|---|---|---|
| `dsf:pol82` role | **`apron`** | **`service_road`** (emitted shapeID 783) |
| `dsf:pol82` off-DEM max | +11.52 m (13ab) / +12.33 m (1.0.324) | **+6.13 m** at 35.2206623,−80.9287108 |
| source classes | lot 60 / open 193 / strip 30 | lot 48 / open 197 / strip 38 (12 moved) |
| cockpit CRITICAL motion | 9 (worst 0.790 m `strip_arc`) | **5** (worst 0.610 m `mid_edge_step [apron\|apron]` at 35.2082082,−80.9412547, a 13ab row) |
| cockpit CRITICAL visual | 2 (pre-§35) | **0** |
| census LAW-TRUE | 11,504 | 11,541 |
| census ADJUDICATED | 3,959 (airside 3,592) | **3,739 (airside 3,357)** |
| road ramps (08r-2) | — | `dsf:pol82` now appears as a ROAD ramp: 0.73 m over 62 m = 1.18 % |

No new row stands on the east road: the census's worst ten are all
`cross_connector` at 35.230,−80.952 (the west side).

CONTROLS, dry (`explain --sources`, classify only, no build):

| | BASE | §37 (5) |
|---|---|---|
| **CYXY** | 120 cells; lot 16 / open 48 / strip 7 | **BYTE-IDENTICAL** — 0 source classes changed. `pav4` (11.5 m, 41 m of road on a 464 m half-perimeter — the case `min_road_fraction` was written for, 09-04j) is ABOVE the floor and unmoved |
| **LEMD** | 597 cells; lot 37 / open 260 / strip 11 | 597 cells; lot 36 / open 260 / strip 12 — **ONE source changed**, `pav119` (8.9 m, 130 m of OSM road) lot → strip |

**§37 (2) HOLDS at LEMD and the bar is quoted honestly**: the 61 apron-side
lanes are `service_road`-born faces and this rule does not touch them; but the
role census is NOT byte-identical — `pav119` moves from `parking_lot` to
`service_road` (both groundside), which is §37 (5) doing exactly what it says
on the one LEMD page in its class.

#### (a) `dsf:pol51` — ATTRIBUTED, EVERY NAMED CANDIDATE REFUTED, NOT FIXED

`dsf:pol51` classifies CORRECTLY: `explain KCLT --at 35.2074982,-80.9296586`
reads `role=service_road side=groundside kind=strip`, `source_class=strip`,
`source_reason=width 11.1 m <= narrow 12, road 385 m` (through 385 m, 4
pieces).  Nothing in the classification holds it up.

The binding read is `tools/v2_solve_replay.py --why-from … --why-at
35.2074982,-80.9296586 --site-radius 25` — `solve.why`'s duals on a pressure
solve of the SAME LP (`|z_pressure − z| max 0.000 m`), off a capture of this
tree:

> `ridge vertex v19369  z 213.15  DEM 199.91 (z-DEM +13.24)`
> `binding rows on v19369 by family: (none: no row binds the vertex — the
> objective holds it)`
> `chain trace: no terminal reached — the objective holds it`

**ZERO rows bind the owner's site.**  Every mechanism §37 (5) named as a
candidate is REFUTED at this vertex: no transverse row to an apron edge, no
zone band, no pad frontage, no neighbour's `taxi_trend`, no bank row.  There
is no cap to relax and no generator to fix.

What holds it is the OBJECTIVE, and the road's own fit target is not where the
road is.  Read off the solved set at the same vertex:

| v19369 | m |
|---|---|
| DEM | 199.91 |
| `PlanarMap.preferred_z` (the core-clamp adapter, `airport/road_profile.preferred_road_z`) | **203.44 (+3.53 over the DEM)** |
| solved z | **213.15 (+13.24 over the DEM, +9.71 over its own target)** |

So the second mechanism is TWO terms, neither of them a constraint:

1. the road's fit TARGET is already +3.53 m up — `cap_lipschitz_profile`'s
   mid-envelope over the whole OSM way, not the terrain under the page (the
   build's own reading: `roads vs core profile: 3096 vertices, mean
   |z−profile| 0.789 m, max 9.890 m, 2710 off beyond materiality in 202 of
   223 faces`);
2. the solve then sits **+9.71 m above that target** with nothing binding it,
   because the smoothing / coupling terms that tie the road to the airside
   FILL beside it outweigh the road's fit weight.  The site read shows the
   region is one smooth surface at the fill's level — 74 vertices within 60 m,
   `z−DEM` mean 6.92 / min 0.94 / max 13.24, roles `building`,
   `graded_strip`, `junction`, `service_road`, **max step over a short edge
   0.02 m**; airport-wide `graded_strip` 12.48 m, `building` 12.61 m,
   `junction` 11.18 m off the DEM.

THE LANE STOPPED HERE AND DID NOT FIX IT.  The fix is an OBJECTIVE-WEIGHT law
— which term wins where a groundside road meets an airside fill — and RULINGS
2026-09-13y already ruled that class a STOP-and-report for a lane ("the
census is not the objective"; the lane did not tune the objective).  Owner law
1a puts a new weight law behind a Fable spec.  The measurement it needs is
already cheap and reproducible: the capture is 76 s and `--why-at` is 93 s.

BARS, stated as measured:

| bar | before | after |
|---|---|---|
| `dsf:pol51` within 2 m of the DEM, follow ratio ≥ 0.8 | 0.287, +13.28 m | **0.283, +13.29 m — NOT MET** (attributed above) |
| no `service_road` over 3 m off the DEM airport-wide | max +13.28 / −4.25 | **max +13.29 / −4.17 — NOT MET** (same mechanism; 5 refs over 3 m, next worst `dsf:pol70` +8.16) |
| `dsf:pol82` classed `service_road` on its own ground | `apron`, +11.52 m | **`service_road`, +6.13 m — ROLE MET, GROUND NOT** (the (a) mechanism) |
| the 1:3 bank at the east edge shrinks with the fill | 401/1,876 load-bearing, 732 foot nodes | **421/2,408 load-bearing, 754 foot nodes — NOT MET**: (a) removed no fill, so the bank has none to give back |
| cockpit CRITICAL motion ≤ 9, no new row on the east road | 9 | **5, none on the east road — MET** |
| LEMD role census byte-identical | — | **ONE source moved (`pav119`) — see above** |
| CYXY control | — | **byte-identical** |

#### CONSUMER CENSUS (owner RULINGS 2026-08-30l) — the source-class change

The change moves faces between two GROUNDSIDE roles (`parking_lot` →
`service_road`) at their single derivation site (`classify/sources.py:_record`,
the source classifier), so `side` stays a pure function of `role` and no
consumer is edited.

| # | consumer | reads | RULE |
|---|---|---|---|
| S1 | `classify/roles.classify` source branch | `src.cls` | THE ONE derivation site — `strip` → `service_road`, `lot` → `parking_lot`, unchanged code. |
| S2 | `classify/airside_edge.airside_edge_flip` | the BORN role (`_ROAD_ROLES`) | UNCHANGED CODE, and this is the point: a face born a road now takes §37 (2)'s SHARE test. `dsf:pol82` 20.8 m of a 1,203 m perimeter = 1.7 % < 0.2 → no flip. |
| S3 | `law.tables.role_side` | the role | UNAFFECTED — both roles are groundside. |
| S4 | `constraints/roads.road_family_roles` (`families.road_cross_section.roles`) | the role | The face GAINS the `road_cross_section` family and the 8 % / 2 % road caps, and LOSES the lot's 5 % cap. This is the intent (§37 (1)); measured: `road_cross_section` 733 verify rows, `lateral_contiguity` 20, no new census family. |
| S5 | `airport/road_profile.road_family_vertices` / `axis_roles` | the role | The face gains a core-clamp fit target (`road_fit_vertices` 1,748 → 2,585). Intended: a road is fitted to the core's profile, a lot is not. |
| S6 | §20 pad levels (`constraints/pads`) / §28 frontages (`constraints/pad_frontage_gs`) | `parking_lot` by class tag | A frontage neighbour changes CLASS but not side; `groundside_frontage` 164 → 148 design-target rows, max miss 1.384 → 0.717 m. |
| S7 | `tools/role_edge_census.py` `_GROUNDSIDE_ROLES` | the emitted patch | UNAFFECTED — both roles are in the set; the LOT-class split moves, which is what it is there to report. |
| S8 | `tools/road_terrain_conformance.py` `_ROAD_FAMILY_ROLES` (= `grade_law.ROAD_ROLES`) | the emitted patch | The face ENTERS the road population: KCLT road vertices 2,533, and `dsf:pol82` is now readable as a road (`--by-ref`). |
| S9 | `check_grade.law_role` / `LAW_FAMILIES` | the way tag | UNCHANGED — no family added, no key added; the harness census reads it as a road. |
| S10 | `emit/osm_adapter` oracle aliases | the role | UNCHANGED — `service_road` already has its alias. |
| S11 | §27 `_LOT_SLIVER_RADIUS_M` | the face | UNTOUCHED, deliberately: the 6.0 m floor keeps every emit sliver on the old path (the 26-LEMD-sliver arm above). |
| S12 | v1 `auto_patch/` | its own classifier | UNTOUCHED — §37 is v2 law. |

#### Build-time impact statement

`_record` gains two comparisons per source polygon (596 at KCLT); the classify
stage is unmeasurable against it.  The road population grows
(`road_fit_vertices` 1,748 → 2,585), which is rows the solve already prices for
every other road.  KCLT engine wall 373.3 s (13ab, main) → 371.1 s here, on a
machine running other lanes — no A/B is quoted (standing law).  Nothing is
within 1 % of either budget.

#### What this lane did NOT do

The (a) fix (attributed to the objective; a weight law needs a Fable spec — see
above); any `--refresh-data`; the five-airport sweep; any LEMD or CYXY BUILD
(the LEMD and CYXY arms above are DRY classify reads, as the brief required);
a fresh KCLT BASE build (13ab's ledger `2951cfc994bd` is quoted instead, and
its sha is stated); `constraints/eat.py` or the EAT loop (lane `v2eatramp`);
any merge; any RULINGS entry.

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

### §37 (6)/(7) **MEASURED — ROUND 2** (lane `v2roadramp`, 2026-09-13, branch `claude/v2roadramp`, base `70646dc8`)

ONE `--engine v2 --patch-only` KCLT build, tag **`v2roadramp2`**, 311.0 s,
rc 0, `status feasible`, `body_sha 3db860e1d3c7`, artifact ledger
**`5dcfccc142b9`**, `[guard] shared repo UNCHANGED`.  The BASE is a
control built for this round at the SAME base — tag `ctlkclt70646dc8`,
ledger **`1f83c7a053d9`**, 315.2 s, tree `70646dc8` — because the shared
`ctl-KCLT` stands at `864e7577` and main has since taken v2seampin,
v2eatramp and v2settle; every number below is against the SAME-TREE
control, and the round-1 column (`497728ff051c`, §37 (6) alone on
`864e7577`) is quoted beside it so §37 (7)'s own movement is visible.

#### WHAT LANDED

* §37 (6) AMENDED: the deck exclusion (round 1's finding) is ratified law.
* §37 (7): `airport/road_ramp.road_route_frame` derives, for EVERY
  road-family ring vertex, `(route id, station s, signed lateral t)` off
  the SAME ways the ramp reads its DEM on; `PlanarMap.road_route_frame`
  carries it, `pipeline/publication` publishes it (sidecar
  `road_route_frame`, LAW INPUT in `check_grade.SIDECAR_LAW_KEYS`), and
  ONE reading — `constraints/roads.road_pair_reading` — is imported by
  the generator, by `verify/within` and by `check_grade`, so the three
  cannot drift (the census-wrapper precedent).
* THE READING: `bound = cap_l·|Δs| + cap_t·|Δt|` (the taxi family's box,
  06q/06s) with Δs the ROUTE distance and Δt the offset across it;
  TRANSVERSE — and so `road_cross_section` — iff the pair's direction in
  ROUTE coordinates is at least `road_transverse_axis_min_deg` off the
  centreline; **NOT A PAIR** on two different routes; the chord law where
  no route answers.  Two floors keep it a RELAXATION: a RING EDGE is
  always priced (an adjacent pair keeps the chord reading across a route
  boundary, so a way boundary mid-road cannot leave a step unpriced), and
  no bound is under `cap_t × the pair's plan distance` (a projection can
  collapse on a bend).
* THE FRAME COVERS EVERY ROAD VERTEX: a way running THROUGH a face
  answers its outer kerbs too (the ramp TARGET keeps the face's answer
  radius).  Without that, 174 of KCLT's 2,026 road vertices were unframed
  — the wide pages' outer kerbs — and their pairs fell back to the chord
  law that held the switchback (measured: `dsf:pol51` cut 6.75 m).

Generator population at KCLT: `road_within_shape` 76,261 rows — **routed
24,741, chord 51,520** (the parking lots and groundside pavement, which
are not roads and keep the chord law), **not_a_pair 47,965**, ring_edge
578.  Published frame: 2,177 vertices.

#### THE OWNER'S SITE — `dsf:pol51` (`--site`, radius 60 m)

| | `ctl-KCLT` (864e7577) | §37 (6) | §37 (6)+(7) |
|---|---|---|---|
| FOLLOW RATIO | 0.294 | 0.857 | **1.007** |
| highest FILL | +13.31 m | +1.62 | **+1.59** |
| deepest CUT | 0.86 m | 5.58 | **5.33** |
| \|emitted−DEM\| median / p95 | 0.43 / 10.54 | 2.33 / 4.11 | **0.61 / 3.78** |

#### AIRPORT-WIDE ROADS (`--by-ref`, same options)

All 2,533 road vertices: \|emitted−DEM\| median **0.708 → 0.171 m**, p95
**3.348 → 1.674 m**, worst 4.17 → 5.33 m.  **Refs over 3 m off the DEM:
8 → 2** — `dsf:pol51` (5.33 m of CUT at 35.2068764,−80.9301639) and
`bridge_deck:-3595` (+4.08 m, the face §37 (6) excludes, unchanged from
its 4.09 m).  `dsf:pol70` 8.17 → **1.65**, `dsf:pol50` 6.53 → **1.25**,
`dsf:pol82` (owner item 7) 6.17 → **0.68 m** (bar ≤ 0.5: 0.18 m over,
reported under §31 (4) as a residual).  `dsf:pol39` 3.64 → 2.22,
`dsf:pol86` 3.46 → 1.67, `dsf:pol63` 3.84 → under 1.7.

#### THE TEN WORST PAIRS, NAMED (the round-1 attribution, re-read under (7))

| face | ref | plan chord | §37 (7) verdict |
|---|---|---|---|
| 827 | `dsf:pol51` (the switchback) | 45.6 m | **not a pair** (two routes) |
| 777 | `dsf:pol50` | 161.4 m | **not a pair** |
| 792 | `dsf:pol70` | 64.0 m | **not a pair** |
| 600 | `dsf:pol39` | 93.7 m | **not a pair** |
| 729 | `dsf:pol62` | 41.9 m | **not a pair** |
| 737 | `dsf:pol82` | 81.7 m | **not a pair** |
| 764 | `dsf:pol53` | 22.3 m | **not a pair** |
| 828 | `dsf:pol51` | 77.6 m | route-followable, bound 6.97 m |
| 597 | `dsf:pol39` | 84.2 m | route-followable, bound 8.07 m (target Δ 6.74 — met) |
| 595 | `dsf:pol66` | 7.0 m | TRANSVERSE, bound 0.47 m (a real cross-section) |

Seven of the ten are the switchback class the ruling frees; two are
route-followable; one is a genuine cross-section.

#### THE CENSUS AND THE VERIFY

| | BASE `1f83c7a053d9` | §37 (6) (r1) | §37 (6)+(7) |
|---|---|---|---|
| harness LAW-TRUE | 11,274 | 17,030 | 13,128 |
| harness **ADJUDICATED** | **3,813** (airside 3,379 / gs 434) | 7,622 | **5,684** (airside **3,801** / gs 1,883) |
| `road_cross_section` | 330 | 1,691 | **642** |
| `within_shape` | 8,500 | 11,541 | 9,743 |
| `airside_no_step` | 612 | 1,374 | **657** |
| `transverse` | 109 | 470 | 348 |
| v2 VERIFY rows | 3,908 | 12,264 | **4,439** |
| v2 VERIFY `road_cross_section` | **781** | 5,263 | **462** |
| cockpit CRITICAL motion / visual | 7 / 0 | 8 / 0 | **12 / 0** |

**THE TWO BARS ARE NOT MET AND THE LANE SAYS SO**: `road_cross_section`
642 against ≤ 310 (the base at this tree is 330), adjudicated 5,684
against ≤ 3,900, cockpit motion 12 against ≤ 8 (NO road row in either
arm — the rolled-on set is airside by definition; the 12 are runway
`strip_arc` grade breaks and two apron `mid_edge_step` rows, the same
families as the base's 7).  What IS measured:

1. §37 (7) removed two thirds of what §37 (6) cost: adjudicated 7,622 →
   5,684, `road_cross_section` 1,691 → 642, `airside_no_step` 1,374 → 657
   (below the base), v2 verify rows 12,264 → 4,439.
2. **The two instruments now disagree in DIRECTION on the road family**:
   the v2 VERIFY — which prices exactly the generator's rows, under the
   same imported reading — reads `road_cross_section` **781 → 462**, an
   improvement on the base; the v1 census reads 330 → 642.  Both now
   PAIR the same way (the twin asserts the census imports the
   generator's function); what still differs is the pair SELECTION
   (`grade_graph.shape_constraints(road_path_metric=True)`, v1's own) and
   the allowance envelope.  The residual is not a pairing artefact.
3. The rows that remain are a road surface that now RIDES ITS TERRAIN
   (median off-DEM 0.708 → 0.171 m): a section that rolls with the ground
   breaks the 2 % cross-section, and the census counts it.  Whether a
   groundside road's cross-section is a LAW or a target under §31 (3)
   ("landside is visual only, grade laws there are TARGETS") is the
   question this residual asks; it is not one this lane may answer.

#### Build-time impact statement

The frame is one extra answer per road vertex over the profiles
`preferred_road_z` already built (KCLT: 2,177 vertices, inside the road
stage's own 1.4 s); the pair law itself is arithmetic on two 3-tuples and
DROPS 47,965 of 76,261 rows, so the solve got smaller (LP rows 95,797 →
84,606) and faster (solve 104.6 → 71.5 s; whole build 426.5 → 311.0 s
against the control's 315.2 s).  Nothing here is within 1 % of either
budget on the wrong side.

#### What round 2 did NOT do

Merge into main; write RULINGS; touch §37 (1)'s caps, the bank, §27's
flip, `solve/`, `constraints/eat.py` or the other lanes' files; a third
KCLT build (the attempt cap: the route pairing, then the collapse floor,
which moved the census 646 → 642 and was kept as a safety floor, not
re-built for); a LEMD or CYXY BUILD (both re-read DRY on their captures:
LEMD 157 road vertices all framed, 486 routed pairs / 184 not-a-pair, the
61 apron-side lanes still carrying 0 ramp targets, the 13 decks excluded,
6 governed vertices within 0.02 m of the DEM; CYXY 348 framed, 3,347
routed / 2,902 not-a-pair, targets within 0.01 m of the core clamp); a
new tool (no `tools/INDEX.md` row).

### §37 (8) THE CROSS-SECTION IS LAW ON A GROUNDSIDE ROAD; THE RAMP BINDS THE CENTRELINE (owner 2026-09-13; RULINGS 2026-09-13bb) — lane `v2roadramp` round 3

Owner: "The base engine should be correcting road banking, confirm that is
running before we try to grade it or test it." Confirmed: the rows run
(`road_cross_section`, 2 %, weight 300, not hard) and lose — KCLT verify 781
violated pairs on the control, 462 with the ramp. A hillside road keeps its
crossfall on a BENCH, not by tilting.

8. **LAW, NOT TARGET.** The 2 % cross-section is law on every road-family
   face, groundside included; `road_cross_section (2026-08-25g)` joins
   `[design] hard_rulings` and the polish certifies it. The ramp target
   (§37 (6)) is the road's CENTRELINE profile per station; the kerbs follow
   the centreline through the cross-section rows, so the hard ramp ceiling
   binds one value per station and never a kerb against another station;
   the adjacent ground takes the bench (§19; §37 (3)'s bank where
   load-bearing).

BARS (round 3; attribution of the 462 rows FIRST, `--why-at`): v2 verify
`road_cross_section` 462 → ≤ 20, survivors named; v1 census 642 → ≤ 330
once its selection reads `road_route_frame`; `dsf:pol51` follow ≥ 0.85 and
section ≤ 2 % at every station; `dsf:pol82` ≤ 0.5 m; cockpit motion ≤ 7;
LEMD / CYXY dry as before; ONE KCLT build against `ctlkclt70646dc8`.

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

### §37 (8)/(9) + §37 (6) amended **MEASURED — ROUND 3** (lane `v2roadramp`, 2026-09-13, branch `claude/v2roadramp`, base `661cb2e7`)

ONE KCLT build, tag **`v2roadramp3`**, 326.6 s, rc 0, `status feasible`,
`body_sha 5f3a70d28599`, artifact ledger **`91ab5a7c8e15`**, `[guard]
shared repo UNCHANGED`.  The control is round 2's same-corpus
`ctlkclt70646dc8` (ledger `1f83c7a053d9`) at main `70646dc8`; main has
since taken `661cb2e7` (v2rampwalk's bridges and adjacent-ground steps,
the v1 retirement — `build_airport.py` no longer has `--engine`), so the
NON-ROAD families below carry that movement too and are marked.

#### THE ATTRIBUTION FIRST — why 462 `road_cross_section` rows survived §37 (7)

Measured on the KCLT capture, over the 2,155 pairs §37 (7) calls a
CROSS-SECTION, by comparing each pair's own §37 (6) TARGETS against its
2 % bound (`cap_t·|Δt| + cap_l·|Δs|`):

| the target's reading | pairs whose TARGETS already break their own 2 % bound | worst |
|---|---|---|
| per VERTEX, floor = the raw DEM along the route (round 2) | **145** of 2,155 | 3.51 m against a 0.60 m bound, Δs 5.8 m, `dsf:pol51` |
| per VERTEX, floor = the core clamp | **129** | 3.67 m against 0.19 m, Δs **1.2 m** |
| per (ROUTE, STATION), floor = the core clamp (this round) | **0** | — |

The suspicion in the brief is confirmed and made precise: the target was
read PER VERTEX — its own nearest-way answer for the floor and its own
graph distance for the descent — so two kerbs of ONE station could take
values 3.67 m apart over 1.2 m of station, and the hard ramp ceiling then
held that tilt against the 2 % cross-section.  The raw DEM made it worse
(it is not cap-Lipschitz), which is why (2) and (8) are one fix:

* the FLOOR is the core's clamp on THE ROUTE THE FRAME NAMES
  (`cap_lipschitz_profile`, already carried by `RoadProfiles`), and
* the target is `max(clamp_r(s), envelope_r(s))` — the descent lifted onto
  the route as a cap-Lipschitz upper envelope — so it is a function of
  (route, station) alone.

Both terms are cap-Lipschitz, so a section's two kerbs differ by at most
`cap_l·|Δs|`, always inside the pair bound: **the ceiling cannot tilt a
section, by construction**.

#### THE THREE RULES AS BUILT

* §37 (8): `road_cross_section (2026-08-25g)` is in `[design]
  hard_rulings` — the 2 % is a CONSTRAINT of the active set on every
  road-family face.
* §37 (6) amended: `airport/road_ramp._floor_along_route` reads the clamp
  (`_dem_twin` keeps the terrain reading for the report only).
* §37 (9): `emit/road_join.py` (the coverage is `emit/bank.coverage_polygon`,
  one implementation) walks each route's stations against the coverage and
  pins the last station inside at the CORE ribbon's altitude at the first
  station outside; published as `PlanarMap.road_coverage_join` and sidecar
  `road_coverage_join`, minted as `Pin` rows by
  `constraints/road_ramp.road_join_rows`, priced by the new census family
  **`road_coverage_join`** (`check_grade.LAW_FAMILIES` + `families.toml`
  `cockpit = "step"`, `solver = "pin"`, four twins in `test_harness.py`).

#### PER BAR

| bar | control `1f83c7a053d9` | round 2 `5dcfccc142b9` | **round 3 `91ab5a7c8e15`** |
|---|---|---|---|
| v2 verify `road_cross_section` ≤ 20 | 781 | 462 | **7** ✅ |
| v1 census `road_cross_section` ≤ 330 | 330 | 642 | **300** ✅ |
| `dsf:pol51` follow ≥ 0.85 | 0.286 | 1.007 | **1.017** ✅ |
| `dsf:pol82` ≤ 0.5 m | 6.17 | 0.68 | **0.68** ❌ (0.18 m over) |
| `road_coverage_join` 0 on the arm, > 0 on the control | — | — | **0 rows**; the same 22 coordinates on the control stand up to **7.93 m** off the ribbon (`dsf:pol70`), 5.17 / 5.15 m at the owner's site 35.2077280 / 35.2077325, −80.929 → **arm 0.004 m max** ✅ |
| cockpit CRITICAL motion ≤ 7 | 7 | 12 | **9** ❌ (visual 0 → **1**, an `adjacent_ground_step [apron\|graded_strip]` cliff 0.820 m over 2.01 m at 35.2267703,−80.9552263 — `adjacent_ground_step` is `661cb2e7`'s new family, not this lane's) |
| all-road \|z−DEM\| | median 0.708 / p95 3.348 | 0.171 / 1.674 | **0.198 / 2.206**, worst 4.40 m |
| adjudicated | 3,813 | 5,684 | 5,864 (airside 4,228 / gs 1,636) — the airside rise is `661cb2e7`'s |

THE 7 SURVIVORS (the v2 verify's own count; the build prints counts, so
they are named through the v1 census's reading of the same law on the same
patch — 300 rows, p50 0.34 m, p95 1.40 m, max 2.01 m): they concentrate on
**`dsf:pol53` way −10858** (55 rows, every one of the worst eight, at
35.21603,−80.92880–80.92890, pairs 36–48 m apart on a page 170 vertices
long) and on `−10862` (40), `−10879` (39), `−10507` (23).  These are the
WIDE pages whose section spans tens of metres: at Δt ≈ 40 m the 2 % bound
is 0.8 m and the built section carries up to 2.01 m.  They are a bench the
solve did not fully cut, not a tilt the law admits.

Other readings: `road_ramp` 1,955 targets from **244** contacts (137 on
the ramp, up to 1.80 m over 596 m of route), clamp over the DEM up to
3.67 m, core fit withdrawn on 1,760; `road_within_shape` 76,393 rows
(routed 24,871 / chord 51,522 / not-a-pair 47,988 / ring-edge 580);
`road_coverage_join` 22 rows from 42 exits on 26 routes; hard rows
28/238,729 violated (max 0.0883 m), `SET NOT SETTLED` 645 flips worst
0.024 m — KCLT's standing 13y (B) condition.  `bridge_deck:-14469`
(`661cb2e7`'s new deck) reads +11.10 m off the DEM and is OUTSIDE the ramp
population by §37 (6) as amended.

LEMD / CYXY dry, on their captures: LEMD 6 governed vertices (13 decks
excluded), targets within 0.01 m of the core clamp, 0 apron-face targets
of 159; CYXY 314 targets, 10 on the ramp, clamp over the DEM up to 1.08 m,
targets within 0.22 m of the clamp.  Suite **1,332 / 0 twice**.

#### What round 3 did NOT do

A second KCLT build or a new control at `661cb2e7` (the bar named
`ctlkclt70646dc8`); the `check_grade` SELECTION re-point (the bar's ≤ 330
was met by the law itself — the census's selection still reads
`grade_graph.shape_constraints`, and its 300 rows are the same population
the verify reads 7 of, the difference being v1's allowance envelope);
chasing the `strip_arc` rows (13ba: the unsettled lag's, and this build's
cockpit block carries one of them at 0.090 m); `dsf:pol82`'s last 0.18 m;
any merge, RULINGS entry, or new tool.

### §37 (3) AMENDED — THE COVERAGE CLOSES AT THE EMITTER; AN OPEN LOAD-BEARING RUN IS A BREAKLINE (owner RULINGS 2026-09-13cp) — lane `v2bankfoot`

§37 (3) emitted ONE OPEN CHAIN PER LOAD-BEARING RUN and nothing over the
immaterial stretches, so the banked region stopped having a CLOSED
boundary in the patch at all — LEMD 1.0.329: **105 open `bank_foot` ways,
0 closed**.  The mesh step's whole bank machinery is a REGION reading, so
that is not a smaller bank, it is no bank:

* `O4_Vector_Map.include_patches:3007/3040` gives `PATCH_RING_MARKER`
  only to a CLOSED way and inserts every open one as `DUMMY` (attr 0) —
  the foot stops being the INTERP_ALT flood barrier and R18-1b's
  Dirichlet datum and drops out of `patches_area`;
* `patch_coverage_polygon` polygonizes marker-15 segments, so the annulus
  leaves the R18-1c domain and its triangles are dropped;
* `bank_annulus_blend_values` was fed a ribbon `_close_open_foot`
  reconstructed by `nearest_points`: **15 valued vertices against
  33,377** the run before;
* the R18-1b harmonic extension then interpolated the vacated corridor
  from remote data — road ribbons authored at 588–590 m emitted at 568
  (a 20.7 m canyon at 40.465414,−3.5531888; 1,400 INTERP_ALT nodes off by
  > 2 m tile-wide, worst −24.3 m).

**THE AMENDMENT.** (a) The boundary ring of the banked region is emitted
WHOLE and CLOSED; the load-bearing test governs which stretches are
RESOLVED (chord-split at `bank_chord_max_m`, mid-chord within
`split_tol_m` of the DEM) and NEVER whether the coverage closes.  Every
station carries the DEM either way — which is what an immaterial station
means.  (b) An OPEN load-bearing run (a ring a tile seam split, §9.4)
wears `PATCH_RING_MARKER`, never `DUMMY`.  (c) The mesh step never closes
a foot itself: `_close_open_foot` is DELETED and an open chain is foot
LINEWORK.  (d) A collapsed annulus REFUSES.  (e) Interim belt: a
bare-INTERP_ALT input node is Dirichlet data.

#### THE CONSUMER CENSUS (owner RULINGS 2026-08-30l) — every reader of `PATCH_RING_MARKER` and of the foot geometry, ruled in ONE table

| # | consumer | reads | RULE |
|---|---|---|---|
| B1 | `O4_Vector_Map.include_patches` closed branch (`:3007`) | closed ways | **UNCHANGED.** The emitter's ring is closed again, so it takes this branch exactly as before §37 (3). |
| B2 | `O4_Vector_Map.include_patches` open branch (`:3040`) | open ways | **EDITED**, the one new site: `o4_feature` in `OPEN_BREAKLINE_FEATURES` (`bank_foot`, `structure_rim` — the two the emitter may SPLIT, `osm_adapter`) takes `PATCH_RING_MARKER`; everything else still `DUMMY`. `crown_spine` / `terrain_edge` are ALWAYS open and never wore the marker: widening to them would be a new law, separately measured. |
| B3 | `patches_area` (the LAND cutter, R4) | closed ring polygons | **RESTORED, not widened.** The banked region is back in it because the ring is closed again — the pre-§37 (3) state. No new polygon source; an open chain still contributes no area (it bounds nothing). |
| B4 | `seawall_admission_area` / `graded_area` (R17-3) | `GRADED_COVERAGE_ROLES` rings | **UNAFFECTED.** A `bank_foot` way is role-less, so it was never in the admission set and is not now. |
| B5 | `include_sea` / `include_water` floods | the WATER/SEA/SEA_EQUIV bits of the marker | **RESTORED to the pre-§37 (3) state** for the same reason as B3. An OPEN chain wearing the marker is a new barrier SEGMENT, but an open chain closes no region, so a flood goes round it — no water is fenced out. |
| B6 | `interp_alt_patch_polygons` → the per-FACE INTERP_ALT seeding | closed ring polygons | **RESTORED.** This is the load-bearing one: with no closed foot the annulus was not a face, got no seed, and its triangles were not INTERP_ALT at all (tile INTERP_ALT triangles 1,670,705 → 371,965). |
| B7 | `O4_Mesh_Utils.patch_coverage_polygon` (R18-1c domain) | marker-15 `.poly` segments, polygonized | **UNCHANGED CODE, restored meaning.** Dangling open chains are ignored by `polygonize`, so B2 cannot widen the coverage; the closed ring is what closes the annulus faces. |
| B8 | `patch_valued_vertex_indices` / `_patch_ring_edges` (the Dirichlet set) | marker-15 edge endpoints | **UNCHANGED CODE.** B2 puts an open run's nodes back in it — which is the ruling's "the Dirichlet datum its closed predecessor was". |
| B9 | `patch_segment_split_values` (R18-1b amendment) | the same edges | **UNCHANGED.** A mesher-inserted vertex on an open run's segment now takes the run's own value there, as on any ring. |
| B10 | `bank_annulus_polygon` / `_bank_rings_from_patches` | the patch `.osm` rings | **EDITED**: returns `(feet, design, open_foot_lines)`; open chains are LINEWORK and never enter the region. `_close_open_foot` and `BANK_OPEN_CHAIN_AREA_WIDTHS` are DELETED. |
| B11 | `bank_annulus_blend_values`' `on_foot` classification | `boundary(feet)` | **EDITED, additive**: the open foot LINES join the foot linework, so a `.poly` edge on a seam-split run is an OUTER segment carrying the foot's own z. |
| B12 | `bank_annulus_regions` (09x triangle sizing) | `_bank_rings_from_patches` | **UNCHANGED** but for the tuple unpack. |
| B13 | `interpolate_free_interior_altitudes` | the Dirichlet set | **UNCHANGED CODE**; its free set shrinks by the ribbon belt (e) and by B8. Its report now names the isolated COMPONENTS (371 at LEMD on 1.0.329) and not only the vertex count. |
| B14 | `hairline_preflight` / `hairline_findings` (`on_boundary`) — lane `v2hairline`'s file region, NOT edited here | every constrained segment, marker-blind | **UNAFFECTED BY DESIGN.** It prices segments, not rings, and never asks whether a way is closed. The node COUNT it sees changes (the ring is whole again), which is a measurement, not a law interaction. |
| B15 | `tools/mesh_region_tris.py` (`PATCH_RING_MARKER = 15`) | the same segments | **UNAFFECTED**; `tests/test_r18c_interp_alt_domain.py` still twin-asserts the three spellings agree. |
| B16 | `tools/patch_seed_seal.py` | inserts marker-15 rings | **UNAFFECTED** (an independent reproduction of the seeding). |
| B17 | `check_grade` `bank_foot` register (`:391`, `:1501`, `bank_across_seam`, `:10427` open features) | the patch's `bank_foot` channel | **UNAFFECTED CODE**; the OPEN-feature branch simply finds nothing at a single-tile airport now. The bank stays role-less and censused as articulation geometry (§9.2). |
| B18 | `verify/frame.Patch.of`, `tools/undulation` | the skip register | **UNAFFECTED.** |

The one region trimmed at its single derivation site (the ruling's
preference over per-consumer vetoes) is the EMITTER's `banked` polygon:
it is where closure happens, and every consumer above reads the closed
ring rather than reconstructing one.

### §37 (10) THE AIRSIDE CONTACT SET INCLUDES TAXIWAYS; A ROUTE PAIR IS FOUND BY GEOMETRY (owner RULINGS 2026-09-13co items 3/4/5; Fable 2026-09-13; RULINGS 2026-09-13cs) — lane `v2roadcontact`

**THE DEFECTS (scout `v2heca329`, HECA 1.0.329).**  (5) `service_road:route0`
ends at 108.09 on the DEM 4.4 m from the `graded_strip` at 106.62 and
`secondary_parallel:pav74` at 106.9 — a 33 % cliff — because §37 (6)'s airside
contact names "apron, pad or lot" and a TAXIWAY is not in the set, so the road
has no contact and targets the DEM.  (3) `service_road:route7` holds the DEM at
109.14–110.17 beside `apron:pav131` at 108.43 (11.6 m away) and ground cut 1.5 m
below the DEM, so the three-way meeting is a hill and `pav115`'s cross-slope
runs 2.03 % over 28 m.  (4) at 30.1096746, 31.4048466 a 3 m ribbon carries two
route frames — route 5936 (a 40 m stub, t = +4.10) and route 5934 (t = −2.12) —
so §37 (7) returns `NOT_A_PAIR`, the section is never priced, and the road
steps 1.30 m over 3.05 m (42.6 %) against a declared 1.5 % cap.

1. The AIRSIDE CONTACT of §37 (6) is any airside face: apron, pad, lot,
   TAXIWAY (every taxi-family role), junction, stub, and the runway shoulder
   of §40.  A road that ends within `contact_reach_m` (15 m) of an airside
   face's edge without touching it has a contact at the nearest edge point,
   at that face's solved level (route7 → pav131).
2. TWO ROUTES ARE ONE CARRIAGEWAY when their corridors interpenetrate: any
   pair of routes whose frames place vertices within `pair_lateral_m` (6 m)
   of each other over ≥ `pair_overlap_m` (10 m) of arc are MERGED into one
   route before the cross-section reading; `NOT_A_PAIR` is never returned for
   two vertices on one ribbon.  The census names every merged pair.
3. The cross-section (§37 (8)) is then priced on every airside road, and
   `road_cross_section` at HECA goes from 4 rows to every ribbon.

BARS (HECA 1.0.329 frame, dry arm then ONE HECA build): route0's end within
0.05 m of pav74's edge level, the 33 % step gone; the item-4 pair priced (step
≤ 2 % over 3 m); route7 contact from pav131, `pav115` cross-slope ≤ 1.5 %; the
`road_cross_section` / `transverse` / `road_ramp` census before → after on
HECA and KCLT (KCLT from its registered frame, dry); suite twice.

#### §37 (10) CONSUMER CENSUS (owner RULINGS 2026-08-30l), completed BEFORE any consumer was edited — lane `v2roadcontact`

The change adds ONE region (the reach contact's airside EDGE) and changes ONE
existing reading (the route frame's route ids, through the merge). Both are
derived at ONE site — `airport/road_ramp.py` — and published as channels.

**A. EVERY READER OF `PlanarMap.road_route_frame` (the merge changes route ids).**

| # | consumer | RULE |
|---|---|---|
| F1 | `constraints/roads.road_within_shape` (the generator) | UNCHANGED CODE beyond passing the new `one_ribbon` argument. Route ids are OPAQUE to it: it only asks whether two frames name the SAME route. A merge can only turn `NOT_A_PAIR` into a priced pair — never the reverse. |
| F2 | `verify/within.road_frames` | UNCHANGED — reads the published frame by identity key; ids are opaque. Passes `one_ribbon_m()`. |
| F3 | `tools/check_grade._road_frame_by_nid` (sidecar `road_route_frame`, a LAW INPUT) | UNCHANGED — ids opaque; the ONE reading `road_pair_reading` is imported, and the ONE-RIBBON width with it (`one_ribbon_m()`), so generator / verify / census keep pricing one law. Twinned (`test_v2roadcontact.py`). |
| F4 | `emit/road_join.road_coverage_joins` (§37 (9)) | UNCHANGED — reads `(route, station)` to find a way's coverage exit. A merged route re-stations onto the SURVIVOR's centreline, so the exit is found on the survivor's line; MEASURED: `road_coverage_join` 0 on both HECA arms and both KCLT arms. |
| F5 | `airport/road_ramp.road_ramp_targets` (the ramp's own floor + envelope) | READS THE MERGED FRAME, which is the point: the clamp is read at `ways[route].at(s)` — the survivor's own profile — so a merged ribbon has ONE floor per station instead of two. |
| F6 | `pipeline/publication` / `emit/osm_adapter` (the sidecar key) | UNCHANGED — it publishes whatever the channel holds. |

**B. THE CONTACT ROW, AND WHY IT IS NOT A TARGET.**

| # | consumer | RULE |
|---|---|---|
| C1 | the §37 (6) ramp target (`road_ramp_z`) | **WITHDRAWN over the end group** (route distance ≤ one lane width). At the mouth the level is the airside's, and only the airside's. MEASURED: with both authorities at `[design] law` HECA `route0`'s end split the difference and stood 0.70 m over its contact (arm 3); with the target withdrawn, 0.054 m. |
| C2 | `[design] hard_rulings` | **NOT REGISTERED, and the reason is measured**: `solve/design` carries ONE `shift` vector, and the augmented Lagrangian's `shift[hard_i] = mu / rho` OVERWRITES the one-way lag of a row in both registers — the leaders vanish from the row. Registered hard, this row drove HECA's roads to `z − DEM = −108 m` and minted 63,170 within-shape rows (arm 2). The §37 (6) ramp ceiling above it stays the hard one. **This is a solver limitation, not a law: hard + one-way is not expressible today.** |
| C3 | `[design] one_way_rulings` | **REGISTERED** — `follows=(v,)`, so the road vertex keeps its column and the two AIRSIDE columns enter the right-hand side lagged. No contact row can move an airside vertex (airside is king). |
| C4 | `classify/roles` / §27's flip | UNAFFECTED — the contact SET is read off `precedence.toml` (`side = "airside"` and `value = true`) plus `[road_contact] extra_roles`, so §40's runway shoulder joins by being DECLARED, not by being typed. A role with no level of its own (`graded_strip`, `boundary`, a clearance) is not a contact. |
| C5 | `emit/bank.py`, `road_terrain_conformance`, the census families | UNAFFECTED — all read the SOLVED surface / the emitted patch. |
| C6 | a capture pickled before the channel | `tools/v2_solve_replay.py` BACKFILLS a missing `PlanarMap` field at its dataclass default and NAMES it (the publisher derives the channel in the replay anyway). Without it a registered frame another lane shares becomes unreplayable. |

### §37 (10) **MEASURED** (lane `v2roadcontact`, 2026-09-13, branch `claude/v2roadcontact`, base `1a7a7158`)

Frame: ONE HECA capture (`v2_solve_replay --capture`, 156 s, 17,408 vertices /
762 faces, registered), replayed on the BASE tree and on this branch — a
matched pair on one capture. KCLT: the registered `v2roadramp` capture
(base `70646dc8`), the same matched-pair method, the base arm cut with
`git archive 1a7a7158 src/auto_patch_v2`.

#### THE OWNER'S SITES

| site | BASE | §37 (10) |
|---|---|---|
| (5) `route0` end 30.1077666, 31.4031555 vs `pav74`'s edge | 108.09 against a contact level of **106.630** — **+1.460 m** | **106.67 against 106.616 — +0.054 m** (bar 0.05 m: 0.004 m over, one materiality floor) |
| (5) the step over the 4.4 m gap | 33 % | **1.2 %** |
| (4) the pair 30.1096746,31.4048466 / 30.1096476,31.4048517 (3.05 m apart, route frames 5936 / 5934) | 105.25 vs 103.95 = **1.30 m, 42.6 %** | **104.00 vs 103.96 = 0.04 m, 1.3 %** (bar ≤ 2 %: MET) |
| (3) `route7` / `pav115` 30.1114112,31.4063353 | 107.72 | 107.72 — **UNCHANGED, and the ruling's premise is REFUTED below** |

**ITEM 3'S MECHANISM IS REFUTED.** §37 (10) (1) says `route7` "holds the DEM
beside `apron:pav131`" for want of a contact. MEASURED on the capture:
`route7` is 15 vertices in two faces and **8 of them ARE airside mouths** —
v7150/7151/7152/7167 on `pav115`, v7161/7162/7163/7164/7170 on `pav131`,
every one at 0.00 m. It has contacts at both ends already, and its 6 owned
vertices stand 0.6–1.0 m over those mouths across Δs ≈ 18 m — **inside its
own 8 % longitudinal cap (allowance 1.44 m)**, so neither a contact nor a
climb ceiling can move it. The "hill" is a lawful road between two mouths
that are themselves on their terrain (mouth DEM 109.6–110.1, solved
109.16–109.54). `pav115`'s cross-slope is an AIRSIDE (taxi-family) question,
not a road-contact one. Attempt spent; no code was written for item 3.

#### HECA CENSUS (harness `census.py`, the two replay-emitted patches)

| | BASE | §37 (10) |
|---|---|---|
| LAW-TRUE | 38,437 | **38,289** |
| ADJUDICATED | 12,312 (airside 11,960 / gs 299) | **12,268** (airside 11,941 / **gs 274**) |
| `road_cross_section` | 21 | **28** |
| `transverse` | 771 | **742** |
| `road_coverage_join` | 0 | 0 |
| v2 verify `road_cross_section` / `within_shape` / `transverse` | 4 / 8,986 / 771 | 9 / 8,989 / 742 |

#### KCLT (matched replay pair on the registered `v2roadramp` capture)

| | BASE | §37 (10) |
|---|---|---|
| LAW-TRUE | 13,577 | 13,666 |
| ADJUDICATED | 5,075 (airside 3,524 / gs 1,549) | 5,101 (airside **3,656** / gs **1,443**) |
| `road_cross_section` | **373** | **280** |
| `transverse` | 271 | 288 |
| v2 verify `road_cross_section` | 2 | 8 |

Dry derivation at KCLT: **132 reach ends** governing 978 of 1,796 road
vertices, **6 merged route pairs** (named: `route585#377`→`osm:-10026`,
`osm:-10627`→`osm:-10628`, `route437#341`→`osm:-12916`,
`route459#346`→`osm:-12039`, `osm:-13773`→`osm:-10617`,
`route717#399`→`osm:-9748`), 268 mouth targets withdrawn.

#### §37 (10) (3) IS ALREADY TRUE, AND THE "4 ROWS" WAS A VIOLATION COUNT

The clause reads "`road_cross_section` at HECA goes from 4 rows to every
ribbon". MEASURED on the generator: cross-section rows are PRICED on **15 of
HECA's 18 road / groundside refs in BOTH arms** (`route8` 108→115, `route0`
63→67, `route2` 61→62, `pav55` 48→54…). The 4 was the VERIFY VIOLATION
count, not a priced-row count. What the ruling actually buys is the pairs
the switchback rule was freeing wrongly: `road_within_shape` `routed`
9,932 → **9,973**, `not_a_pair` 9,092 → **9,065** at HECA, and
`not_a_pair` 41,820 with 24,164 routed at KCLT.

#### AIRSIDE IS KING — ROUND 2 (coordinator 2026-09-13), THE AIRSIDE ROW FIRST

Round 1 moved 115 HECA airside vertices over 0.1 m and lifted KCLT's airside
census +132. THE REMEDY, and what it measured (matched replay pairs on the
two registered captures, BOTH arms on merged main `a621b491`, the base arm
cut with `git archive`):

**(a) EVERY ROW THIS LANE MINTS THAT TOUCHES A MOUTH IS ONE-WAY.** A road
RING's vertices include the mouth it shares with its apron or taxiway, so a
pair this lane newly prices can bind an AIRSIDE column. Measured at HECA: of
the 24 pairs the ribbon rule and the merge newly price, **8 touch an airside
vertex** — and `ribbon_follower` read 0, because those 8 came from the MERGE
(same route after fusing), not from the cross-route rule. Both are now
recognised (`PlanarMap.road_route_merged` publishes the routes that absorbed
another) and minted under `RIBBON_RULING`, `follows=(road_v,)`, registered in
`[design] one_way_rulings` and NOT in `hard_rulings`. HECA: **44 follower
rows**; the 5 cross-ribbon pairs whose BOTH vertices are airside are not
minted at all (before §37 (10) they read `NOT_A_PAIR`). A pair on a MERGED
route is never dropped, only made one-way — a row that already existed must
not be deleted.

**(b) THE WITHDRAWAL RELEASES NO AIRSIDE VERTEX.** The §37 (6) target governs
road-OWNED vertices (`_owned`: senior role in the road family), so an airside
vertex never carried one. MEASURED at HECA: **544 targets, 0 airside; 66
withdrawn at the mouth, 0 airside; `preferred_z` airside entries 0 → 0.**
Twinned (`test_no_airside_vertex_carries_a_ramp_target_or_loses_one`).

**(c) THE BYTE READING, AIRSIDE FIRST.**

| HECA, matched pair on the registered capture | BASE `38dd98be` | §37 (10) round 2 |
|---|---|---|
| **ADJUDICATED AIRSIDE** | **12,052** | **12,088 (+36)** |
| airside `within_shape` / `taxi_box` / `airside_no_step` | 30,908 / 2,036 / 3,788 | 30,854 / 2,068 / 3,811 |
| airside value vertices moved > 0.1 m | — | **123 of 9,255, 4 over 0.5 m, worst 0.550 m** |
| ADJUDICATED total / groundside / mixed | 12,429 / 322 / 55 | 12,418 / **280** / 50 |
| `road_cross_section` | 40 | **30** |
| `transverse` (airside) | 777 (611) | **744** (609) |
| `route0` end vs `pav74`'s edge | +1.460 m | **+0.054 m** |
| item-4 pair over 3.05 m | 1.30 m (42.6 %) | **0.04 m (1.3 %)** |

The SAME code delta read against the PREVIOUS base is +1 airside row, not +36
— which is itself the reading below: the groundside gain (−42 / −49) and the
two site fixes are stable across bases, the airside row count is not.

| HECA, the same pair one merge earlier | BASE `a621b491` | §37 (10) round 2 |
|---|---|---|
| **ADJUDICATED AIRSIDE** | **11,960** | **11,961 (+1)** |
| airside `within_shape` / `taxi_box` / `airside_no_step` | 31,002 / 2,040 / 3,691 | 31,001 / 2,039 / 3,691 |
| airside value vertices moved > 0.1 m | — | **121 of 9,255 (round 1: 296 under the same base), 2 over 0.5 m, worst 0.610 m** |
| ADJUDICATED total / groundside | 12,331 / 318 | 12,282 / **269** |
| `road_cross_section` | 40 | **28** |
| `transverse` | 771 | **740** |
| `route0` end vs `pav74`'s edge | +1.460 m | **+0.054 m** |
| item-4 pair over 3.05 m | 1.30 m (42.6 %) | **0.05 m (1.6 %)** |

| KCLT, matched pair on the registered `v2roadramp` capture | BASE `a621b491` | §37 (10) round 2 |
|---|---|---|
| ADJUDICATED airside | 3,599 | 3,670 (+71; round 1 was +132) |
| ADJUDICATED total / groundside | 5,150 / 1,549 | 5,142 / **1,470** |
| `road_cross_section` | **373** | **304** |
| airside value vertices moved > 0.1 m | — | 994 of 9,991, worst 1.360 m |

**THE 0.1 m BAR IS NOT MET, AND THE RESIDUAL IS THE OBJECTIVE'S, NOT A ROW'S
— MEASURED TWICE.**

1. **THE DISARM ARM IS BYTE-IDENTICAL.** With `contact_reach_m = 0` and
   `pair_lateral_m = 0` the branch emits the same patch as the base arm to
   the byte (`md5 210dfeb0d55081a474f95b05f5ed80ed` both). The tree is
   otherwise neutral: every difference below is the two law keys'.
2. **THE WORST AIRSIDE MOVER IS HELD BY NO ROW.** `--why-from … --why-at
   30.1014237, 31.3933314` (the apron vertex that moves 0.610 m), a duals
   solve of the arm's own LP: *"binding rows on v5920 by family: (none: no
   row binds the vertex — the objective holds it); chain trace: no terminal
   reached"*. It is the 13aj mechanism read from the other side — the
   least-squares objective re-balancing a coupled sheet after 66 road
   targets are withdrawn and 24 road pairs are priced.
3. Each key moves airside ON ITS OWN and in DIFFERENT places (contact only:
   95 vertices > 0.1 m; ribbon/merge only: 104 — and the second arm only
   DROPS 5 rows and re-stations one route), which is the signature of a
   sensitive solve rather than of a pull whose size tracks its rows.
4. At KCLT both arms report `SET NOT SETTLED` (922 / 416 rows flipped),
   `HARD SET NOT SETTLED` and `LAG NOT SETTLED after 3 of 3 rounds` with
   ~4,000 one-way rows still moving and the **worst leader move 0.317 /
   0.242 m** — the solve's own unconverged lag is three times the 0.1 m
   bar, so a per-vertex byte comparison at that resolution is below the
   instrument's resolution there (the standing KCLT instance of RULINGS
   2026-09-13y (B) / 13ab).

**WHAT WOULD MEET IT** is not a row change: it is the standing "airside
solves first, groundside conforms" ordering — fixing the airside columns
before the groundside pass — which is an architecture question for the
owner, not this lane's. INTENT QUESTION: does "airside is king" mean NO ROW
of a groundside law may bind an airside column (met, and twinned), or that
the airside SURFACE must be invariant under a groundside change (not met,
and not meetable while both are one least-squares solve)?

#### Build-time impact statement

Bank pass: CYXY 0.14 s both arms, LEMD 0.54 → 0.51 s.  §37 (1) removes a
`min`; §37 (2) adds one comparison per candidate; §37 (3) reads `_inner`
for every region station instead of only for emitted ones and re-reads it
for the kept ones, which the bank pass absorbs.  Whole-build wall is a
re-solve of a changed system on a machine running four lanes
concurrently, so no A/B is quoted (standing law: never one run per side).
Nothing here is within 1 % of either budget.

#### What this lane did NOT do

KCLT (blocked — the pristine-DSF dump, above); the five-airport sweep
(the orchestrator's, once per merged batch); any `--refresh-data`; any
new tool (nothing here needed one — the bank's own census is
`BankReport.line()`, the share census is `tools/role_edge_census.py`,
the defect counts are `tools/harness/census.py`), so no `tools/INDEX.md`
row; any merge.

### §37 (5) THE SECOND MECHANISM UNDER THE EAST ROAD (Fable 2026-09-13; RULINGS 2026-09-13ab) — lane `v2roadcap2`

Scout `v2roadcapkclt` on main 064e244e: §37 (1) moved `dsf:pol51` 0.94 m
(+14.22 → +13.28 m) — the DEM grade along its chain is 6.8 %, under the 8 %
road cap, so the longitudinal cap was never what held it (follow ratio
0.287 over 179 m). `dsf:pol82` (owner's shapeID 791) is STILL `apron` at
+11.52 m though §37 (2)'s share rule should have left a face with 2 % of its
perimeter on airside a road. Both attributions were incomplete. The lane
first makes `explain KCLT` run (the `planar.__main__.default_inputs` half of
the 13q chip: honour `O4_AIRPORT_MOD_CACHE_DIR` / the harness redirect as
`build_airport.py` now does — one resolution, not two), then NAMES the rows
holding `dsf:pol51` up (transverse rows to an apron edge? a bank or zone
band? a pad frontage? the `taxi_trend` of a neighbour?) and the PASS that
classes `dsf:pol82` apron (scorer role before §27, or a share read on the
wrong perimeter), and fixes what it names.

BARS (KCLT, ONE build): `dsf:pol51` within 2 m of the DEM over its chain
(follow ratio ≥ 0.8), no service road over 3 m off the DEM airport-wide
(today max +13.28 / −4.25); `dsf:pol82` classed `service_road` on its own
ground; the 1:3 bank at the east edge shrinks with the fill it daylighted;
cockpit CRITICAL motion ≤ 9 (13ab's block) with no new row on the east road;
LEMD role census byte-identical (§37 (2) holds: the 61 apron-side lanes stay
apron); suite twice.

### §37 (5) **MEASURED** (lane `v2roadcap2`, 2026-09-13, branch `claude/v2roadcap2`, base `2002c7dc` + main `05050624`)

ONE `--engine v2` KCLT build, tag **`v2roadcap2`**, 371.1 s engine / 418.5 s
wall, rc 0, `status optimal`, `body_sha a7651dd35206`, artifact ledger
**`0e50c1a921f1`**, `[guard] shared repo UNCHANGED`.  The BASE it is quoted
against is scout `v2roadcapkclt`'s build on main `064e244e` (RULINGS
2026-09-13ab, ledger `2951cfc994bd`) — a DIFFERENT sha, stated because this
lane did not spend a second 7-minute build on a control the ledger already
holds.

#### THE INSTRUMENT

`explain KCLT` and `v2_solve_replay --capture KCLT` RUN in a lane worktree,
under `O4_AIRPORT_MOD_CACHE_DIR` pointed at a copy-on-write overlay, with the
shared repo untouched.  Three halves, of which the lane wrote two:

* the mod-cache resolution — **the owner's own `modcacheguard` chip, main
  `05050624`**, merged into this branch; the lane's parallel implementation
  was dropped in its favour;
* `tools/v2_solve_replay.py --capture` now makes its own PRISTINE pack dump
  through the build entry's own `auto_patch.engine_v2.fresh_pack_dump` (one
  implementation, three callers).  v2 never runs DSFTool itself and KCLT has
  never had a `+35-081.dsf.anchor_bak.*.text`, so without this every capture
  of KCLT refused at `airport/load.py:289` whatever root it resolved;
* `capture_has_groups` read `bool(groups.groups)` and so refused every
  COMPLETE capture of an airport that HAS no groups — **KCLT partitions
  7,163 bodies into 0 groups**.  The predicate is now "the derivation ran";
  `partition is None` is what actually catches a pre-12u capture.

#### (b) `dsf:pol82` — ATTRIBUTED, FIXED, MEASURED

13ab offered two hypotheses ("the scorer's role before §27, or §37 (2)'s
share read on the wrong perimeter").  `explain KCLT --at
35.2208425,-80.9278375` names a third, and it is neither:

> `cell 226: role=apron ... ref=dsf:pol82` — `source_class=lot`,
> `source_reason=5 road(s) reach it (04u), no taxi centreline, no startup,
> width 8.4 m`, `airside_edge_m=20.8`, `airside_edge_flip=1`,
> `airside_edge_round=2`, `airside_edge_was=parking_lot`.

§27's flip is READ CORRECTLY on the right perimeter, and the scorer never
touched the face.  The face was born **`parking_lot`**, so
`airside_edge.airside_edge_flip`'s `was_road[i]` is False and §37 (2)'s share
test — which asks whether a face was born `service_road` / `service_junction`
— never applied; the LOT rule (20.8 m ≥ `airside_edge_min_m` 10 m) flipped it.

Why it was born a lot is `classify/sources.py:_record`.  `narrow_road_width_m`
(12 m) says in its own words "a source polygon at most this wide that carries
ANY road centreline IS the road", but its branch is gated on `carries` =
`road_m ≥ min_road_fraction × HALF-PERIMETER`.  On a ribbon the half-perimeter
is a LENGTH, not a width: `dsf:pol82` is 8.44 m × 601 m, so `carries` demanded
**120.3 m** of mapped centreline and OSM maps **70.5 m** inside it (the
centreline wanders in and out of an 8.4 m page; five roads reach it).  The
strip branch never fired, and the face fell through to the LOT ladder's
weakest rung — `reach > 0`, RULINGS 2026-09-04u.  **Twelve KCLT pages
6.7–10.3 m wide read the same way.**

THE LAW (`[lot] min_lot_width_m` = 11.0 m): a 90-degree car park's minimum
module is one 5.0 m stall row plus one 6.0 m one-way aisle.  In the band
`[service.road_width_m, min_lot_width_m]` = [6.0, 11.0] m a page never reaches
the two WEAKEST lot rungs (`carries_osm`, the 04u `reach` rung), and it is the
ROAD where it carries a road centreline that is not noise
(`osm_roads.min_len_m` 10 m).  MAPPED evidence still outranks the width in
both directions: `amenity=parking` cover, an OSM parking aisle, `aeroway=apron`
cover, an apron name and a 1300 startup all keep their verdicts.  BELOW 6.0 m
the page is an EMIT SLIVER and §27's own sliver class owns it — the first arm
of this rule took 26 LEMD slivers (`dsf:pol255#2` and family, 0.1–0.3 m across)
out of the lot class and moved LEMD's cell count 597 → 578 for no reason
connected to §37 (5); the floor is why the rule is a band.

| KCLT | BASE (13ab, main 064e244e) | §37 (5) (`0e50c1a921f1`) |
|---|---|---|
| `dsf:pol82` role | **`apron`** | **`service_road`** (emitted shapeID 783) |
| `dsf:pol82` off-DEM max | +11.52 m (13ab) / +12.33 m (1.0.324) | **+6.13 m** at 35.2206623,−80.9287108 |
| source classes | lot 60 / open 193 / strip 30 | lot 48 / open 197 / strip 38 (12 moved) |
| cockpit CRITICAL motion | 9 (worst 0.790 m `strip_arc`) | **5** (worst 0.610 m `mid_edge_step [apron\|apron]` at 35.2082082,−80.9412547, a 13ab row) |
| cockpit CRITICAL visual | 2 (pre-§35) | **0** |
| census LAW-TRUE | 11,504 | 11,541 |
| census ADJUDICATED | 3,959 (airside 3,592) | **3,739 (airside 3,357)** |
| road ramps (08r-2) | — | `dsf:pol82` now appears as a ROAD ramp: 0.73 m over 62 m = 1.18 % |

No new row stands on the east road: the census's worst ten are all
`cross_connector` at 35.230,−80.952 (the west side).

CONTROLS, dry (`explain --sources`, classify only, no build):

| | BASE | §37 (5) |
|---|---|---|
| **CYXY** | 120 cells; lot 16 / open 48 / strip 7 | **BYTE-IDENTICAL** — 0 source classes changed. `pav4` (11.5 m, 41 m of road on a 464 m half-perimeter — the case `min_road_fraction` was written for, 09-04j) is ABOVE the floor and unmoved |
| **LEMD** | 597 cells; lot 37 / open 260 / strip 11 | 597 cells; lot 36 / open 260 / strip 12 — **ONE source changed**, `pav119` (8.9 m, 130 m of OSM road) lot → strip |

**§37 (2) HOLDS at LEMD and the bar is quoted honestly**: the 61 apron-side
lanes are `service_road`-born faces and this rule does not touch them; but the
role census is NOT byte-identical — `pav119` moves from `parking_lot` to
`service_road` (both groundside), which is §37 (5) doing exactly what it says
on the one LEMD page in its class.

#### (a) `dsf:pol51` — ATTRIBUTED, EVERY NAMED CANDIDATE REFUTED, NOT FIXED

`dsf:pol51` classifies CORRECTLY: `explain KCLT --at 35.2074982,-80.9296586`
reads `role=service_road side=groundside kind=strip`, `source_class=strip`,
`source_reason=width 11.1 m <= narrow 12, road 385 m` (through 385 m, 4
pieces).  Nothing in the classification holds it up.

The binding read is `tools/v2_solve_replay.py --why-from … --why-at
35.2074982,-80.9296586 --site-radius 25` — `solve.why`'s duals on a pressure
solve of the SAME LP (`|z_pressure − z| max 0.000 m`), off a capture of this
tree:

> `ridge vertex v19369  z 213.15  DEM 199.91 (z-DEM +13.24)`
> `binding rows on v19369 by family: (none: no row binds the vertex — the
> objective holds it)`
> `chain trace: no terminal reached — the objective holds it`

**ZERO rows bind the owner's site.**  Every mechanism §37 (5) named as a
candidate is REFUTED at this vertex: no transverse row to an apron edge, no
zone band, no pad frontage, no neighbour's `taxi_trend`, no bank row.  There
is no cap to relax and no generator to fix.

What holds it is the OBJECTIVE, and the road's own fit target is not where the
road is.  Read off the solved set at the same vertex:

| v19369 | m |
|---|---|
| DEM | 199.91 |
| `PlanarMap.preferred_z` (the core-clamp adapter, `airport/road_profile.preferred_road_z`) | **203.44 (+3.53 over the DEM)** |
| solved z | **213.15 (+13.24 over the DEM, +9.71 over its own target)** |

So the second mechanism is TWO terms, neither of them a constraint:

1. the road's fit TARGET is already +3.53 m up — `cap_lipschitz_profile`'s
   mid-envelope over the whole OSM way, not the terrain under the page (the
   build's own reading: `roads vs core profile: 3096 vertices, mean
   |z−profile| 0.789 m, max 9.890 m, 2710 off beyond materiality in 202 of
   223 faces`);
2. the solve then sits **+9.71 m above that target** with nothing binding it,
   because the smoothing / coupling terms that tie the road to the airside
   FILL beside it outweigh the road's fit weight.  The site read shows the
   region is one smooth surface at the fill's level — 74 vertices within 60 m,
   `z−DEM` mean 6.92 / min 0.94 / max 13.24, roles `building`,
   `graded_strip`, `junction`, `service_road`, **max step over a short edge
   0.02 m**; airport-wide `graded_strip` 12.48 m, `building` 12.61 m,
   `junction` 11.18 m off the DEM.

THE LANE STOPPED HERE AND DID NOT FIX IT.  The fix is an OBJECTIVE-WEIGHT law
— which term wins where a groundside road meets an airside fill — and RULINGS
2026-09-13y already ruled that class a STOP-and-report for a lane ("the
census is not the objective"; the lane did not tune the objective).  Owner law
1a puts a new weight law behind a Fable spec.  The measurement it needs is
already cheap and reproducible: the capture is 76 s and `--why-at` is 93 s.

BARS, stated as measured:

| bar | before | after |
|---|---|---|
| `dsf:pol51` within 2 m of the DEM, follow ratio ≥ 0.8 | 0.287, +13.28 m | **0.283, +13.29 m — NOT MET** (attributed above) |
| no `service_road` over 3 m off the DEM airport-wide | max +13.28 / −4.25 | **max +13.29 / −4.17 — NOT MET** (same mechanism; 5 refs over 3 m, next worst `dsf:pol70` +8.16) |
| `dsf:pol82` classed `service_road` on its own ground | `apron`, +11.52 m | **`service_road`, +6.13 m — ROLE MET, GROUND NOT** (the (a) mechanism) |
| the 1:3 bank at the east edge shrinks with the fill | 401/1,876 load-bearing, 732 foot nodes | **421/2,408 load-bearing, 754 foot nodes — NOT MET**: (a) removed no fill, so the bank has none to give back |
| cockpit CRITICAL motion ≤ 9, no new row on the east road | 9 | **5, none on the east road — MET** |
| LEMD role census byte-identical | — | **ONE source moved (`pav119`) — see above** |
| CYXY control | — | **byte-identical** |

#### CONSUMER CENSUS (owner RULINGS 2026-08-30l) — the source-class change

The change moves faces between two GROUNDSIDE roles (`parking_lot` →
`service_road`) at their single derivation site (`classify/sources.py:_record`,
the source classifier), so `side` stays a pure function of `role` and no
consumer is edited.

| # | consumer | reads | RULE |
|---|---|---|---|
| S1 | `classify/roles.classify` source branch | `src.cls` | THE ONE derivation site — `strip` → `service_road`, `lot` → `parking_lot`, unchanged code. |
| S2 | `classify/airside_edge.airside_edge_flip` | the BORN role (`_ROAD_ROLES`) | UNCHANGED CODE, and this is the point: a face born a road now takes §37 (2)'s SHARE test. `dsf:pol82` 20.8 m of a 1,203 m perimeter = 1.7 % < 0.2 → no flip. |
| S3 | `law.tables.role_side` | the role | UNAFFECTED — both roles are groundside. |
| S4 | `constraints/roads.road_family_roles` (`families.road_cross_section.roles`) | the role | The face GAINS the `road_cross_section` family and the 8 % / 2 % road caps, and LOSES the lot's 5 % cap. This is the intent (§37 (1)); measured: `road_cross_section` 733 verify rows, `lateral_contiguity` 20, no new census family. |
| S5 | `airport/road_profile.road_family_vertices` / `axis_roles` | the role | The face gains a core-clamp fit target (`road_fit_vertices` 1,748 → 2,585). Intended: a road is fitted to the core's profile, a lot is not. |
| S6 | §20 pad levels (`constraints/pads`) / §28 frontages (`constraints/pad_frontage_gs`) | `parking_lot` by class tag | A frontage neighbour changes CLASS but not side; `groundside_frontage` 164 → 148 design-target rows, max miss 1.384 → 0.717 m. |
| S7 | `tools/role_edge_census.py` `_GROUNDSIDE_ROLES` | the emitted patch | UNAFFECTED — both roles are in the set; the LOT-class split moves, which is what it is there to report. |
| S8 | `tools/road_terrain_conformance.py` `_ROAD_FAMILY_ROLES` (= `grade_law.ROAD_ROLES`) | the emitted patch | The face ENTERS the road population: KCLT road vertices 2,533, and `dsf:pol82` is now readable as a road (`--by-ref`). |
| S9 | `check_grade.law_role` / `LAW_FAMILIES` | the way tag | UNCHANGED — no family added, no key added; the harness census reads it as a road. |
| S10 | `emit/osm_adapter` oracle aliases | the role | UNCHANGED — `service_road` already has its alias. |
| S11 | §27 `_LOT_SLIVER_RADIUS_M` | the face | UNTOUCHED, deliberately: the 6.0 m floor keeps every emit sliver on the old path (the 26-LEMD-sliver arm above). |
| S12 | v1 `auto_patch/` | its own classifier | UNTOUCHED — §37 is v2 law. |

#### Build-time impact statement

`_record` gains two comparisons per source polygon (596 at KCLT); the classify
stage is unmeasurable against it.  The road population grows
(`road_fit_vertices` 1,748 → 2,585), which is rows the solve already prices for
every other road.  KCLT engine wall 373.3 s (13ab, main) → 371.1 s here, on a
machine running other lanes — no A/B is quoted (standing law).  Nothing is
within 1 % of either budget.

#### What this lane did NOT do

The (a) fix (attributed to the objective; a weight law needs a Fable spec — see
above); any `--refresh-data`; the five-airport sweep; any LEMD or CYXY BUILD
(the LEMD and CYXY arms above are DRY classify reads, as the brief required);
a fresh KCLT BASE build (13ab's ledger `2951cfc994bd` is quoted instead, and
its sha is stated); `constraints/eat.py` or the EAT loop (lane `v2eatramp`);
any merge; any RULINGS entry.

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

### §37 (6)/(7) **MEASURED — ROUND 2** (lane `v2roadramp`, 2026-09-13, branch `claude/v2roadramp`, base `70646dc8`)

ONE `--engine v2 --patch-only` KCLT build, tag **`v2roadramp2`**, 311.0 s,
rc 0, `status feasible`, `body_sha 3db860e1d3c7`, artifact ledger
**`5dcfccc142b9`**, `[guard] shared repo UNCHANGED`.  The BASE is a
control built for this round at the SAME base — tag `ctlkclt70646dc8`,
ledger **`1f83c7a053d9`**, 315.2 s, tree `70646dc8` — because the shared
`ctl-KCLT` stands at `864e7577` and main has since taken v2seampin,
v2eatramp and v2settle; every number below is against the SAME-TREE
control, and the round-1 column (`497728ff051c`, §37 (6) alone on
`864e7577`) is quoted beside it so §37 (7)'s own movement is visible.

#### WHAT LANDED

* §37 (6) AMENDED: the deck exclusion (round 1's finding) is ratified law.
* §37 (7): `airport/road_ramp.road_route_frame` derives, for EVERY
  road-family ring vertex, `(route id, station s, signed lateral t)` off
  the SAME ways the ramp reads its DEM on; `PlanarMap.road_route_frame`
  carries it, `pipeline/publication` publishes it (sidecar
  `road_route_frame`, LAW INPUT in `check_grade.SIDECAR_LAW_KEYS`), and
  ONE reading — `constraints/roads.road_pair_reading` — is imported by
  the generator, by `verify/within` and by `check_grade`, so the three
  cannot drift (the census-wrapper precedent).
* THE READING: `bound = cap_l·|Δs| + cap_t·|Δt|` (the taxi family's box,
  06q/06s) with Δs the ROUTE distance and Δt the offset across it;
  TRANSVERSE — and so `road_cross_section` — iff the pair's direction in
  ROUTE coordinates is at least `road_transverse_axis_min_deg` off the
  centreline; **NOT A PAIR** on two different routes; the chord law where
  no route answers.  Two floors keep it a RELAXATION: a RING EDGE is
  always priced (an adjacent pair keeps the chord reading across a route
  boundary, so a way boundary mid-road cannot leave a step unpriced), and
  no bound is under `cap_t × the pair's plan distance` (a projection can
  collapse on a bend).
* THE FRAME COVERS EVERY ROAD VERTEX: a way running THROUGH a face
  answers its outer kerbs too (the ramp TARGET keeps the face's answer
  radius).  Without that, 174 of KCLT's 2,026 road vertices were unframed
  — the wide pages' outer kerbs — and their pairs fell back to the chord
  law that held the switchback (measured: `dsf:pol51` cut 6.75 m).

Generator population at KCLT: `road_within_shape` 76,261 rows — **routed
24,741, chord 51,520** (the parking lots and groundside pavement, which
are not roads and keep the chord law), **not_a_pair 47,965**, ring_edge
578.  Published frame: 2,177 vertices.

#### THE OWNER'S SITE — `dsf:pol51` (`--site`, radius 60 m)

| | `ctl-KCLT` (864e7577) | §37 (6) | §37 (6)+(7) |
|---|---|---|---|
| FOLLOW RATIO | 0.294 | 0.857 | **1.007** |
| highest FILL | +13.31 m | +1.62 | **+1.59** |
| deepest CUT | 0.86 m | 5.58 | **5.33** |
| \|emitted−DEM\| median / p95 | 0.43 / 10.54 | 2.33 / 4.11 | **0.61 / 3.78** |

#### AIRPORT-WIDE ROADS (`--by-ref`, same options)

All 2,533 road vertices: \|emitted−DEM\| median **0.708 → 0.171 m**, p95
**3.348 → 1.674 m**, worst 4.17 → 5.33 m.  **Refs over 3 m off the DEM:
8 → 2** — `dsf:pol51` (5.33 m of CUT at 35.2068764,−80.9301639) and
`bridge_deck:-3595` (+4.08 m, the face §37 (6) excludes, unchanged from
its 4.09 m).  `dsf:pol70` 8.17 → **1.65**, `dsf:pol50` 6.53 → **1.25**,
`dsf:pol82` (owner item 7) 6.17 → **0.68 m** (bar ≤ 0.5: 0.18 m over,
reported under §31 (4) as a residual).  `dsf:pol39` 3.64 → 2.22,
`dsf:pol86` 3.46 → 1.67, `dsf:pol63` 3.84 → under 1.7.

#### THE TEN WORST PAIRS, NAMED (the round-1 attribution, re-read under (7))

| face | ref | plan chord | §37 (7) verdict |
|---|---|---|---|
| 827 | `dsf:pol51` (the switchback) | 45.6 m | **not a pair** (two routes) |
| 777 | `dsf:pol50` | 161.4 m | **not a pair** |
| 792 | `dsf:pol70` | 64.0 m | **not a pair** |
| 600 | `dsf:pol39` | 93.7 m | **not a pair** |
| 729 | `dsf:pol62` | 41.9 m | **not a pair** |
| 737 | `dsf:pol82` | 81.7 m | **not a pair** |
| 764 | `dsf:pol53` | 22.3 m | **not a pair** |
| 828 | `dsf:pol51` | 77.6 m | route-followable, bound 6.97 m |
| 597 | `dsf:pol39` | 84.2 m | route-followable, bound 8.07 m (target Δ 6.74 — met) |
| 595 | `dsf:pol66` | 7.0 m | TRANSVERSE, bound 0.47 m (a real cross-section) |

Seven of the ten are the switchback class the ruling frees; two are
route-followable; one is a genuine cross-section.

#### THE CENSUS AND THE VERIFY

| | BASE `1f83c7a053d9` | §37 (6) (r1) | §37 (6)+(7) |
|---|---|---|---|
| harness LAW-TRUE | 11,274 | 17,030 | 13,128 |
| harness **ADJUDICATED** | **3,813** (airside 3,379 / gs 434) | 7,622 | **5,684** (airside **3,801** / gs 1,883) |
| `road_cross_section` | 330 | 1,691 | **642** |
| `within_shape` | 8,500 | 11,541 | 9,743 |
| `airside_no_step` | 612 | 1,374 | **657** |
| `transverse` | 109 | 470 | 348 |
| v2 VERIFY rows | 3,908 | 12,264 | **4,439** |
| v2 VERIFY `road_cross_section` | **781** | 5,263 | **462** |
| cockpit CRITICAL motion / visual | 7 / 0 | 8 / 0 | **12 / 0** |

**THE TWO BARS ARE NOT MET AND THE LANE SAYS SO**: `road_cross_section`
642 against ≤ 310 (the base at this tree is 330), adjudicated 5,684
against ≤ 3,900, cockpit motion 12 against ≤ 8 (NO road row in either
arm — the rolled-on set is airside by definition; the 12 are runway
`strip_arc` grade breaks and two apron `mid_edge_step` rows, the same
families as the base's 7).  What IS measured:

1. §37 (7) removed two thirds of what §37 (6) cost: adjudicated 7,622 →
   5,684, `road_cross_section` 1,691 → 642, `airside_no_step` 1,374 → 657
   (below the base), v2 verify rows 12,264 → 4,439.
2. **The two instruments now disagree in DIRECTION on the road family**:
   the v2 VERIFY — which prices exactly the generator's rows, under the
   same imported reading — reads `road_cross_section` **781 → 462**, an
   improvement on the base; the v1 census reads 330 → 642.  Both now
   PAIR the same way (the twin asserts the census imports the
   generator's function); what still differs is the pair SELECTION
   (`grade_graph.shape_constraints(road_path_metric=True)`, v1's own) and
   the allowance envelope.  The residual is not a pairing artefact.
3. The rows that remain are a road surface that now RIDES ITS TERRAIN
   (median off-DEM 0.708 → 0.171 m): a section that rolls with the ground
   breaks the 2 % cross-section, and the census counts it.  Whether a
   groundside road's cross-section is a LAW or a target under §31 (3)
   ("landside is visual only, grade laws there are TARGETS") is the
   question this residual asks; it is not one this lane may answer.

#### Build-time impact statement

The frame is one extra answer per road vertex over the profiles
`preferred_road_z` already built (KCLT: 2,177 vertices, inside the road
stage's own 1.4 s); the pair law itself is arithmetic on two 3-tuples and
DROPS 47,965 of 76,261 rows, so the solve got smaller (LP rows 95,797 →
84,606) and faster (solve 104.6 → 71.5 s; whole build 426.5 → 311.0 s
against the control's 315.2 s).  Nothing here is within 1 % of either
budget on the wrong side.

#### What round 2 did NOT do

Merge into main; write RULINGS; touch §37 (1)'s caps, the bank, §27's
flip, `solve/`, `constraints/eat.py` or the other lanes' files; a third
KCLT build (the attempt cap: the route pairing, then the collapse floor,
which moved the census 646 → 642 and was kept as a safety floor, not
re-built for); a LEMD or CYXY BUILD (both re-read DRY on their captures:
LEMD 157 road vertices all framed, 486 routed pairs / 184 not-a-pair, the
61 apron-side lanes still carrying 0 ramp targets, the 13 decks excluded,
6 governed vertices within 0.02 m of the DEM; CYXY 348 framed, 3,347
routed / 2,902 not-a-pair, targets within 0.01 m of the core clamp); a
new tool (no `tools/INDEX.md` row).

### §37 (8) THE CROSS-SECTION IS LAW ON A GROUNDSIDE ROAD; THE RAMP BINDS THE CENTRELINE (owner 2026-09-13; RULINGS 2026-09-13bb) — lane `v2roadramp` round 3

Owner: "The base engine should be correcting road banking, confirm that is
running before we try to grade it or test it." Confirmed: the rows run
(`road_cross_section`, 2 %, weight 300, not hard) and lose — KCLT verify 781
violated pairs on the control, 462 with the ramp. A hillside road keeps its
crossfall on a BENCH, not by tilting.

8. **LAW, NOT TARGET.** The 2 % cross-section is law on every road-family
   face, groundside included; `road_cross_section (2026-08-25g)` joins
   `[design] hard_rulings` and the polish certifies it. The ramp target
   (§37 (6)) is the road's CENTRELINE profile per station; the kerbs follow
   the centreline through the cross-section rows, so the hard ramp ceiling
   binds one value per station and never a kerb against another station;
   the adjacent ground takes the bench (§19; §37 (3)'s bank where
   load-bearing).

BARS (round 3; attribution of the 462 rows FIRST, `--why-at`): v2 verify
`road_cross_section` 462 → ≤ 20, survivors named; v1 census 642 → ≤ 330
once its selection reads `road_route_frame`; `dsf:pol51` follow ≥ 0.85 and
section ≤ 2 % at every station; `dsf:pol82` ≤ 0.5 m; cockpit motion ≤ 7;
LEMD / CYXY dry as before; ONE KCLT build against `ctlkclt70646dc8`.

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

### §37 (8)/(9) + §37 (6) amended **MEASURED — ROUND 3** (lane `v2roadramp`, 2026-09-13, branch `claude/v2roadramp`, base `661cb2e7`)

ONE KCLT build, tag **`v2roadramp3`**, 326.6 s, rc 0, `status feasible`,
`body_sha 5f3a70d28599`, artifact ledger **`91ab5a7c8e15`**, `[guard]
shared repo UNCHANGED`.  The control is round 2's same-corpus
`ctlkclt70646dc8` (ledger `1f83c7a053d9`) at main `70646dc8`; main has
since taken `661cb2e7` (v2rampwalk's bridges and adjacent-ground steps,
the v1 retirement — `build_airport.py` no longer has `--engine`), so the
NON-ROAD families below carry that movement too and are marked.

#### THE ATTRIBUTION FIRST — why 462 `road_cross_section` rows survived §37 (7)

Measured on the KCLT capture, over the 2,155 pairs §37 (7) calls a
CROSS-SECTION, by comparing each pair's own §37 (6) TARGETS against its
2 % bound (`cap_t·|Δt| + cap_l·|Δs|`):

| the target's reading | pairs whose TARGETS already break their own 2 % bound | worst |
|---|---|---|
| per VERTEX, floor = the raw DEM along the route (round 2) | **145** of 2,155 | 3.51 m against a 0.60 m bound, Δs 5.8 m, `dsf:pol51` |
| per VERTEX, floor = the core clamp | **129** | 3.67 m against 0.19 m, Δs **1.2 m** |
| per (ROUTE, STATION), floor = the core clamp (this round) | **0** | — |

The suspicion in the brief is confirmed and made precise: the target was
read PER VERTEX — its own nearest-way answer for the floor and its own
graph distance for the descent — so two kerbs of ONE station could take
values 3.67 m apart over 1.2 m of station, and the hard ramp ceiling then
held that tilt against the 2 % cross-section.  The raw DEM made it worse
(it is not cap-Lipschitz), which is why (2) and (8) are one fix:

* the FLOOR is the core's clamp on THE ROUTE THE FRAME NAMES
  (`cap_lipschitz_profile`, already carried by `RoadProfiles`), and
* the target is `max(clamp_r(s), envelope_r(s))` — the descent lifted onto
  the route as a cap-Lipschitz upper envelope — so it is a function of
  (route, station) alone.

Both terms are cap-Lipschitz, so a section's two kerbs differ by at most
`cap_l·|Δs|`, always inside the pair bound: **the ceiling cannot tilt a
section, by construction**.

#### THE THREE RULES AS BUILT

* §37 (8): `road_cross_section (2026-08-25g)` is in `[design]
  hard_rulings` — the 2 % is a CONSTRAINT of the active set on every
  road-family face.
* §37 (6) amended: `airport/road_ramp._floor_along_route` reads the clamp
  (`_dem_twin` keeps the terrain reading for the report only).
* §37 (9): `emit/road_join.py` (the coverage is `emit/bank.coverage_polygon`,
  one implementation) walks each route's stations against the coverage and
  pins the last station inside at the CORE ribbon's altitude at the first
  station outside; published as `PlanarMap.road_coverage_join` and sidecar
  `road_coverage_join`, minted as `Pin` rows by
  `constraints/road_ramp.road_join_rows`, priced by the new census family
  **`road_coverage_join`** (`check_grade.LAW_FAMILIES` + `families.toml`
  `cockpit = "step"`, `solver = "pin"`, four twins in `test_harness.py`).

#### PER BAR

| bar | control `1f83c7a053d9` | round 2 `5dcfccc142b9` | **round 3 `91ab5a7c8e15`** |
|---|---|---|---|
| v2 verify `road_cross_section` ≤ 20 | 781 | 462 | **7** ✅ |
| v1 census `road_cross_section` ≤ 330 | 330 | 642 | **300** ✅ |
| `dsf:pol51` follow ≥ 0.85 | 0.286 | 1.007 | **1.017** ✅ |
| `dsf:pol82` ≤ 0.5 m | 6.17 | 0.68 | **0.68** ❌ (0.18 m over) |
| `road_coverage_join` 0 on the arm, > 0 on the control | — | — | **0 rows**; the same 22 coordinates on the control stand up to **7.93 m** off the ribbon (`dsf:pol70`), 5.17 / 5.15 m at the owner's site 35.2077280 / 35.2077325, −80.929 → **arm 0.004 m max** ✅ |
| cockpit CRITICAL motion ≤ 7 | 7 | 12 | **9** ❌ (visual 0 → **1**, an `adjacent_ground_step [apron\|graded_strip]` cliff 0.820 m over 2.01 m at 35.2267703,−80.9552263 — `adjacent_ground_step` is `661cb2e7`'s new family, not this lane's) |
| all-road \|z−DEM\| | median 0.708 / p95 3.348 | 0.171 / 1.674 | **0.198 / 2.206**, worst 4.40 m |
| adjudicated | 3,813 | 5,684 | 5,864 (airside 4,228 / gs 1,636) — the airside rise is `661cb2e7`'s |

THE 7 SURVIVORS (the v2 verify's own count; the build prints counts, so
they are named through the v1 census's reading of the same law on the same
patch — 300 rows, p50 0.34 m, p95 1.40 m, max 2.01 m): they concentrate on
**`dsf:pol53` way −10858** (55 rows, every one of the worst eight, at
35.21603,−80.92880–80.92890, pairs 36–48 m apart on a page 170 vertices
long) and on `−10862` (40), `−10879` (39), `−10507` (23).  These are the
WIDE pages whose section spans tens of metres: at Δt ≈ 40 m the 2 % bound
is 0.8 m and the built section carries up to 2.01 m.  They are a bench the
solve did not fully cut, not a tilt the law admits.

Other readings: `road_ramp` 1,955 targets from **244** contacts (137 on
the ramp, up to 1.80 m over 596 m of route), clamp over the DEM up to
3.67 m, core fit withdrawn on 1,760; `road_within_shape` 76,393 rows
(routed 24,871 / chord 51,522 / not-a-pair 47,988 / ring-edge 580);
`road_coverage_join` 22 rows from 42 exits on 26 routes; hard rows
28/238,729 violated (max 0.0883 m), `SET NOT SETTLED` 645 flips worst
0.024 m — KCLT's standing 13y (B) condition.  `bridge_deck:-14469`
(`661cb2e7`'s new deck) reads +11.10 m off the DEM and is OUTSIDE the ramp
population by §37 (6) as amended.

LEMD / CYXY dry, on their captures: LEMD 6 governed vertices (13 decks
excluded), targets within 0.01 m of the core clamp, 0 apron-face targets
of 159; CYXY 314 targets, 10 on the ramp, clamp over the DEM up to 1.08 m,
targets within 0.22 m of the clamp.  Suite **1,332 / 0 twice**.

#### What round 3 did NOT do

A second KCLT build or a new control at `661cb2e7` (the bar named
`ctlkclt70646dc8`); the `check_grade` SELECTION re-point (the bar's ≤ 330
was met by the law itself — the census's selection still reads
`grade_graph.shape_constraints`, and its 300 rows are the same population
the verify reads 7 of, the difference being v1's allowance envelope);
chasing the `strip_arc` rows (13ba: the unsettled lag's, and this build's
cockpit block carries one of them at 0.090 m); `dsf:pol82`'s last 0.18 m;
any merge, RULINGS entry, or new tool.

### §37 (3) AMENDED — THE COVERAGE CLOSES AT THE EMITTER; AN OPEN LOAD-BEARING RUN IS A BREAKLINE (owner RULINGS 2026-09-13cp) — lane `v2bankfoot`

§37 (3) emitted ONE OPEN CHAIN PER LOAD-BEARING RUN and nothing over the
immaterial stretches, so the banked region stopped having a CLOSED
boundary in the patch at all — LEMD 1.0.329: **105 open `bank_foot` ways,
0 closed**.  The mesh step's whole bank machinery is a REGION reading, so
that is not a smaller bank, it is no bank:

* `O4_Vector_Map.include_patches:3007/3040` gives `PATCH_RING_MARKER`
  only to a CLOSED way and inserts every open one as `DUMMY` (attr 0) —
  the foot stops being the INTERP_ALT flood barrier and R18-1b's
  Dirichlet datum and drops out of `patches_area`;
* `patch_coverage_polygon` polygonizes marker-15 segments, so the annulus
  leaves the R18-1c domain and its triangles are dropped;
* `bank_annulus_blend_values` was fed a ribbon `_close_open_foot`
  reconstructed by `nearest_points`: **15 valued vertices against
  33,377** the run before;
* the R18-1b harmonic extension then interpolated the vacated corridor
  from remote data — road ribbons authored at 588–590 m emitted at 568
  (a 20.7 m canyon at 40.465414,−3.5531888; 1,400 INTERP_ALT nodes off by
  > 2 m tile-wide, worst −24.3 m).

**THE AMENDMENT.** (a) The boundary ring of the banked region is emitted
WHOLE and CLOSED; the load-bearing test governs which stretches are
RESOLVED (chord-split at `bank_chord_max_m`, mid-chord within
`split_tol_m` of the DEM) and NEVER whether the coverage closes.  Every
station carries the DEM either way — which is what an immaterial station
means.  (b) An OPEN load-bearing run (a ring a tile seam split, §9.4)
wears `PATCH_RING_MARKER`, never `DUMMY`.  (c) The mesh step never closes
a foot itself: `_close_open_foot` is DELETED and an open chain is foot
LINEWORK.  (d) A collapsed annulus REFUSES.  (e) Interim belt: a
bare-INTERP_ALT input node is Dirichlet data.

#### THE CONSUMER CENSUS (owner RULINGS 2026-08-30l) — every reader of `PATCH_RING_MARKER` and of the foot geometry, ruled in ONE table

| # | consumer | reads | RULE |
|---|---|---|---|
| B1 | `O4_Vector_Map.include_patches` closed branch (`:3007`) | closed ways | **UNCHANGED.** The emitter's ring is closed again, so it takes this branch exactly as before §37 (3). |
| B2 | `O4_Vector_Map.include_patches` open branch (`:3040`) | open ways | **EDITED**, the one new site: `o4_feature` in `OPEN_BREAKLINE_FEATURES` (`bank_foot`, `structure_rim` — the two the emitter may SPLIT, `osm_adapter`) takes `PATCH_RING_MARKER`; everything else still `DUMMY`. `crown_spine` / `terrain_edge` are ALWAYS open and never wore the marker: widening to them would be a new law, separately measured. |
| B3 | `patches_area` (the LAND cutter, R4) | closed ring polygons | **RESTORED, not widened.** The banked region is back in it because the ring is closed again — the pre-§37 (3) state. No new polygon source; an open chain still contributes no area (it bounds nothing). |
| B4 | `seawall_admission_area` / `graded_area` (R17-3) | `GRADED_COVERAGE_ROLES` rings | **UNAFFECTED.** A `bank_foot` way is role-less, so it was never in the admission set and is not now. |
| B5 | `include_sea` / `include_water` floods | the WATER/SEA/SEA_EQUIV bits of the marker | **RESTORED to the pre-§37 (3) state** for the same reason as B3. An OPEN chain wearing the marker is a new barrier SEGMENT, but an open chain closes no region, so a flood goes round it — no water is fenced out. |
| B6 | `interp_alt_patch_polygons` → the per-FACE INTERP_ALT seeding | closed ring polygons | **RESTORED.** This is the load-bearing one: with no closed foot the annulus was not a face, got no seed, and its triangles were not INTERP_ALT at all (tile INTERP_ALT triangles 1,670,705 → 371,965). |
| B7 | `O4_Mesh_Utils.patch_coverage_polygon` (R18-1c domain) | marker-15 `.poly` segments, polygonized | **UNCHANGED CODE, restored meaning.** Dangling open chains are ignored by `polygonize`, so B2 cannot widen the coverage; the closed ring is what closes the annulus faces. |
| B8 | `patch_valued_vertex_indices` / `_patch_ring_edges` (the Dirichlet set) | marker-15 edge endpoints | **UNCHANGED CODE.** B2 puts an open run's nodes back in it — which is the ruling's "the Dirichlet datum its closed predecessor was". |
| B9 | `patch_segment_split_values` (R18-1b amendment) | the same edges | **UNCHANGED.** A mesher-inserted vertex on an open run's segment now takes the run's own value there, as on any ring. |
| B10 | `bank_annulus_polygon` / `_bank_rings_from_patches` | the patch `.osm` rings | **EDITED**: returns `(feet, design, open_foot_lines)`; open chains are LINEWORK and never enter the region. `_close_open_foot` and `BANK_OPEN_CHAIN_AREA_WIDTHS` are DELETED. |
| B11 | `bank_annulus_blend_values`' `on_foot` classification | `boundary(feet)` | **EDITED, additive**: the open foot LINES join the foot linework, so a `.poly` edge on a seam-split run is an OUTER segment carrying the foot's own z. |
| B12 | `bank_annulus_regions` (09x triangle sizing) | `_bank_rings_from_patches` | **UNCHANGED** but for the tuple unpack. |
| B13 | `interpolate_free_interior_altitudes` | the Dirichlet set | **UNCHANGED CODE**; its free set shrinks by the ribbon belt (e) and by B8. Its report now names the isolated COMPONENTS (371 at LEMD on 1.0.329) and not only the vertex count. |
| B14 | `hairline_preflight` / `hairline_findings` (`on_boundary`) — lane `v2hairline`'s file region, NOT edited here | every constrained segment, marker-blind | **UNAFFECTED BY DESIGN.** It prices segments, not rings, and never asks whether a way is closed. The node COUNT it sees changes (the ring is whole again), which is a measurement, not a law interaction. |
| B15 | `tools/mesh_region_tris.py` (`PATCH_RING_MARKER = 15`) | the same segments | **UNAFFECTED**; `tests/test_r18c_interp_alt_domain.py` still twin-asserts the three spellings agree. |
| B16 | `tools/patch_seed_seal.py` | inserts marker-15 rings | **UNAFFECTED** (an independent reproduction of the seeding). |
| B17 | `check_grade` `bank_foot` register (`:391`, `:1501`, `bank_across_seam`, `:10427` open features) | the patch's `bank_foot` channel | **UNAFFECTED CODE**; the OPEN-feature branch simply finds nothing at a single-tile airport now. The bank stays role-less and censused as articulation geometry (§9.2). |
| B18 | `verify/frame.Patch.of`, `tools/undulation` | the skip register | **UNAFFECTED.** |

The one region trimmed at its single derivation site (the ruling's
preference over per-consumer vetoes) is the EMITTER's `banked` polygon:
it is where closure happens, and every consumer above reads the closed
ring rather than reconstructing one.

### §37 (10) THE AIRSIDE CONTACT SET INCLUDES TAXIWAYS; A ROUTE PAIR IS FOUND BY GEOMETRY (owner RULINGS 2026-09-13co items 3/4/5; Fable 2026-09-13; RULINGS 2026-09-13cs) — lane `v2roadcontact`

**THE DEFECTS (scout `v2heca329`, HECA 1.0.329).**  (5) `service_road:route0`
ends at 108.09 on the DEM 4.4 m from the `graded_strip` at 106.62 and
`secondary_parallel:pav74` at 106.9 — a 33 % cliff — because §37 (6)'s airside
contact names "apron, pad or lot" and a TAXIWAY is not in the set, so the road
has no contact and targets the DEM.  (3) `service_road:route7` holds the DEM at
109.14–110.17 beside `apron:pav131` at 108.43 (11.6 m away) and ground cut 1.5 m
below the DEM, so the three-way meeting is a hill and `pav115`'s cross-slope
runs 2.03 % over 28 m.  (4) at 30.1096746, 31.4048466 a 3 m ribbon carries two
route frames — route 5936 (a 40 m stub, t = +4.10) and route 5934 (t = −2.12) —
so §37 (7) returns `NOT_A_PAIR`, the section is never priced, and the road
steps 1.30 m over 3.05 m (42.6 %) against a declared 1.5 % cap.

1. The AIRSIDE CONTACT of §37 (6) is any airside face: apron, pad, lot,
   TAXIWAY (every taxi-family role), junction, stub, and the runway shoulder
   of §40.  A road that ends within `contact_reach_m` (15 m) of an airside
   face's edge without touching it has a contact at the nearest edge point,
   at that face's solved level (route7 → pav131).
2. TWO ROUTES ARE ONE CARRIAGEWAY when their corridors interpenetrate: any
   pair of routes whose frames place vertices within `pair_lateral_m` (6 m)
   of each other over ≥ `pair_overlap_m` (10 m) of arc are MERGED into one
   route before the cross-section reading; `NOT_A_PAIR` is never returned for
   two vertices on one ribbon.  The census names every merged pair.
3. The cross-section (§37 (8)) is then priced on every airside road, and
   `road_cross_section` at HECA goes from 4 rows to every ribbon.

BARS (HECA 1.0.329 frame, dry arm then ONE HECA build): route0's end within
0.05 m of pav74's edge level, the 33 % step gone; the item-4 pair priced (step
≤ 2 % over 3 m); route7 contact from pav131, `pav115` cross-slope ≤ 1.5 %; the
`road_cross_section` / `transverse` / `road_ramp` census before → after on
HECA and KCLT (KCLT from its registered frame, dry); suite twice.

#### §37 (10) CONSUMER CENSUS (owner RULINGS 2026-08-30l), completed BEFORE any consumer was edited — lane `v2roadcontact`

The change adds ONE region (the reach contact's airside EDGE) and changes ONE
existing reading (the route frame's route ids, through the merge). Both are
derived at ONE site — `airport/road_ramp.py` — and published as channels.

**A. EVERY READER OF `PlanarMap.road_route_frame` (the merge changes route ids).**

| # | consumer | RULE |
|---|---|---|
| F1 | `constraints/roads.road_within_shape` (the generator) | UNCHANGED CODE beyond passing the new `one_ribbon` argument. Route ids are OPAQUE to it: it only asks whether two frames name the SAME route. A merge can only turn `NOT_A_PAIR` into a priced pair — never the reverse. |
| F2 | `verify/within.road_frames` | UNCHANGED — reads the published frame by identity key; ids are opaque. Passes `one_ribbon_m()`. |
| F3 | `tools/check_grade._road_frame_by_nid` (sidecar `road_route_frame`, a LAW INPUT) | UNCHANGED — ids opaque; the ONE reading `road_pair_reading` is imported, and the ONE-RIBBON width with it (`one_ribbon_m()`), so generator / verify / census keep pricing one law. Twinned (`test_v2roadcontact.py`). |
| F4 | `emit/road_join.road_coverage_joins` (§37 (9)) | UNCHANGED — reads `(route, station)` to find a way's coverage exit. A merged route re-stations onto the SURVIVOR's centreline, so the exit is found on the survivor's line; MEASURED: `road_coverage_join` 0 on both HECA arms and both KCLT arms. |
| F5 | `airport/road_ramp.road_ramp_targets` (the ramp's own floor + envelope) | READS THE MERGED FRAME, which is the point: the clamp is read at `ways[route].at(s)` — the survivor's own profile — so a merged ribbon has ONE floor per station instead of two. |
| F6 | `pipeline/publication` / `emit/osm_adapter` (the sidecar key) | UNCHANGED — it publishes whatever the channel holds. |

**B. THE CONTACT ROW, AND WHY IT IS NOT A TARGET.**

| # | consumer | RULE |
|---|---|---|
| C1 | the §37 (6) ramp target (`road_ramp_z`) | **WITHDRAWN over the end group** (route distance ≤ one lane width). At the mouth the level is the airside's, and only the airside's. MEASURED: with both authorities at `[design] law` HECA `route0`'s end split the difference and stood 0.70 m over its contact (arm 3); with the target withdrawn, 0.054 m. |
| C2 | `[design] hard_rulings` | **NOT REGISTERED, and the reason is measured**: `solve/design` carries ONE `shift` vector, and the augmented Lagrangian's `shift[hard_i] = mu / rho` OVERWRITES the one-way lag of a row in both registers — the leaders vanish from the row. Registered hard, this row drove HECA's roads to `z − DEM = −108 m` and minted 63,170 within-shape rows (arm 2). The §37 (6) ramp ceiling above it stays the hard one. **This is a solver limitation, not a law: hard + one-way is not expressible today.** |
| C3 | `[design] one_way_rulings` | **REGISTERED** — `follows=(v,)`, so the road vertex keeps its column and the two AIRSIDE columns enter the right-hand side lagged. No contact row can move an airside vertex (airside is king). |
| C4 | `classify/roles` / §27's flip | UNAFFECTED — the contact SET is read off `precedence.toml` (`side = "airside"` and `value = true`) plus `[road_contact] extra_roles`, so §40's runway shoulder joins by being DECLARED, not by being typed. A role with no level of its own (`graded_strip`, `boundary`, a clearance) is not a contact. |
| C5 | `emit/bank.py`, `road_terrain_conformance`, the census families | UNAFFECTED — all read the SOLVED surface / the emitted patch. |
| C6 | a capture pickled before the channel | `tools/v2_solve_replay.py` BACKFILLS a missing `PlanarMap` field at its dataclass default and NAMES it (the publisher derives the channel in the replay anyway). Without it a registered frame another lane shares becomes unreplayable. |

### §37 (10) **MEASURED** (lane `v2roadcontact`, 2026-09-13, branch `claude/v2roadcontact`, base `1a7a7158`)

Frame: ONE HECA capture (`v2_solve_replay --capture`, 156 s, 17,408 vertices /
762 faces, registered), replayed on the BASE tree and on this branch — a
matched pair on one capture. KCLT: the registered `v2roadramp` capture
(base `70646dc8`), the same matched-pair method, the base arm cut with
`git archive 1a7a7158 src/auto_patch_v2`.

#### THE OWNER'S SITES

| site | BASE | §37 (10) |
|---|---|---|
| (5) `route0` end 30.1077666, 31.4031555 vs `pav74`'s edge | 108.09 against a contact level of **106.630** — **+1.460 m** | **106.67 against 106.616 — +0.054 m** (bar 0.05 m: 0.004 m over, one materiality floor) |
| (5) the step over the 4.4 m gap | 33 % | **1.2 %** |
| (4) the pair 30.1096746,31.4048466 / 30.1096476,31.4048517 (3.05 m apart, route frames 5936 / 5934) | 105.25 vs 103.95 = **1.30 m, 42.6 %** | **104.00 vs 103.96 = 0.04 m, 1.3 %** (bar ≤ 2 %: MET) |
| (3) `route7` / `pav115` 30.1114112,31.4063353 | 107.72 | 107.72 — **UNCHANGED, and the ruling's premise is REFUTED below** |

**ITEM 3'S MECHANISM IS REFUTED.** §37 (10) (1) says `route7` "holds the DEM
beside `apron:pav131`" for want of a contact. MEASURED on the capture:
`route7` is 15 vertices in two faces and **8 of them ARE airside mouths** —
v7150/7151/7152/7167 on `pav115`, v7161/7162/7163/7164/7170 on `pav131`,
every one at 0.00 m. It has contacts at both ends already, and its 6 owned
vertices stand 0.6–1.0 m over those mouths across Δs ≈ 18 m — **inside its
own 8 % longitudinal cap (allowance 1.44 m)**, so neither a contact nor a
climb ceiling can move it. The "hill" is a lawful road between two mouths
that are themselves on their terrain (mouth DEM 109.6–110.1, solved
109.16–109.54). `pav115`'s cross-slope is an AIRSIDE (taxi-family) question,
not a road-contact one. Attempt spent; no code was written for item 3.

#### HECA CENSUS (harness `census.py`, the two replay-emitted patches)

| | BASE | §37 (10) |
|---|---|---|
| LAW-TRUE | 38,437 | **38,289** |
| ADJUDICATED | 12,312 (airside 11,960 / gs 299) | **12,268** (airside 11,941 / **gs 274**) |
| `road_cross_section` | 21 | **28** |
| `transverse` | 771 | **742** |
| `road_coverage_join` | 0 | 0 |
| v2 verify `road_cross_section` / `within_shape` / `transverse` | 4 / 8,986 / 771 | 9 / 8,989 / 742 |

#### KCLT (matched replay pair on the registered `v2roadramp` capture)

| | BASE | §37 (10) |
|---|---|---|
| LAW-TRUE | 13,577 | 13,666 |
| ADJUDICATED | 5,075 (airside 3,524 / gs 1,549) | 5,101 (airside **3,656** / gs **1,443**) |
| `road_cross_section` | **373** | **280** |
| `transverse` | 271 | 288 |
| v2 verify `road_cross_section` | 2 | 8 |

Dry derivation at KCLT: **132 reach ends** governing 978 of 1,796 road
vertices, **6 merged route pairs** (named: `route585#377`→`osm:-10026`,
`osm:-10627`→`osm:-10628`, `route437#341`→`osm:-12916`,
`route459#346`→`osm:-12039`, `osm:-13773`→`osm:-10617`,
`route717#399`→`osm:-9748`), 268 mouth targets withdrawn.

#### §37 (10) (3) IS ALREADY TRUE, AND THE "4 ROWS" WAS A VIOLATION COUNT

The clause reads "`road_cross_section` at HECA goes from 4 rows to every
ribbon". MEASURED on the generator: cross-section rows are PRICED on **15 of
HECA's 18 road / groundside refs in BOTH arms** (`route8` 108→115, `route0`
63→67, `route2` 61→62, `pav55` 48→54…). The 4 was the VERIFY VIOLATION
count, not a priced-row count. What the ruling actually buys is the pairs
the switchback rule was freeing wrongly: `road_within_shape` `routed`
9,932 → **9,973**, `not_a_pair` 9,092 → **9,065** at HECA, and
`not_a_pair` 41,820 with 24,164 routed at KCLT.

#### AIRSIDE MOTION — REPORTED, NOT CLAIMED CLEAN

No CONTACT row can move an airside vertex (one-way, C3). But the one-ribbon
pair rule prices pairs on road RINGS, whose vertices include the mouths a
road shares with its apron, and withdrawing 66 mouth targets re-solves the
whole LP. MEASURED HECA base → arm over 9,255 airside value vertices:
**115 move more than 0.1 m (1.2 %), 2 more than 0.5 m, worst 0.770 m**
(an apron at 30.1014237, 31.3933314); runway worst 0.080 m. The bar "no
airside vertex moves for a road" is NOT met as a byte reading; no row
minted by this lane pulls airside.

#### Build-time impact statement

One extra STRtree over the airside faces' ring edges and one nearest-edge
query per route END, plus the merge's one `dwithin` query over the framed
road vertices. MEASURED standalone on the HECA capture with the road
profiles WARM (as the build shares them, P9), three runs each:
`with_road_ramp` **0.23 / 0.23 / 0.26 s on this branch against 0.26 / 0.27 /
0.27 s on the base** — inside the run-to-run spread, no new pass and no
second `core_profiles`. Whole HECA build 337.6 s (tag `v2roadcontactHECA2`);
no A/B is claimed (standing law: never one run per side). The solve carries
301 extra one-way rows at HECA and 978 at KCLT.

#### THE CLOSING BUILD (the acceptance arm)

ONE HECA build through the harness, tag **`v2roadcontactHECA2`**, rc 0,
**337.6 s**, `status feasible`, `body_sha 38465d2dfd2a`, artifact ledger
**`96f569b01af9`**, `[guard] shared repo UNCHANGED`. Read against the
OWNER'S SHIPPED 1.0.329 patch at the two sites:

| site | shipped 1.0.329 | build `v2roadcontactHECA2` |
|---|---|---|
| `route0` end vs `pav74`'s edge (106.616 / 106.606) | 108.09 — **+1.474 m** | 106.66 — **+0.054 m** |
| item-4 pair over 3.05 m | 105.25 / 103.95 = **1.30 m, 42.6 %** | 103.83 / 103.88 = **0.05 m, 1.6 %** |

Build census (harness): LAW-TRUE 38,441, ADJUDICATED 12,771 (airside 12,446
/ groundside **273**), `road_cross_section` 23, `transverse` 790,
`road_coverage_join` 0; v2 verify 16,589 rows, DEFECT families ALL ZERO.
The build's frame is not the replay pair's, so the before → after reading
is the REPLAY PAIR above; the build is the acceptance arm.

### §37 (3) AMENDED — THE COVERAGE CLOSES; LOAD-BEARING GOVERNS RESOLUTION ONLY (Fable 2026-09-13; RULINGS 2026-09-13cw) — lane `v2bankfoot`

The banked region's boundary ring is emitted WHOLE and CLOSED. §37 (3)'s
load-bearing test decides which stretches of it are chord-RESOLVED
(`split_chain(..., mask)`, `BankReport.load_bearing`), never whether the
coverage closes: the mesh's bank machinery is a REGION reading
(`patches_area`, `patch_coverage_polygon`, the INTERP_ALT seed needs a marker
segment all the way round — 61,604 INTERP_ALT triangles in coverage with no
ring vs 283,247 closed), and an open way in the vector map is a `DUMMY`
edge (13cp).  An OPEN way of a class whose closed form wears the marker
(`OPEN_BREAKLINE_FEATURES = ("bank_foot", "structure_rim")`) wears
`PATCH_RING_MARKER`; `crown_spine` / `terrain_edge` stay `DUMMY`.
`audit_bank_annulus` refuses a patch with a bank foot that values under 10 %
of its annulus candidates.  Bare INTERP_ALT input nodes are Dirichlet, never
free.  `[design] bank_omit` (default false) is the owner's OMIT arm (13cq).

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

## Spec (design-surface) §29

## §29 A MOUTH IS BUILT ONLY ON THE FIELD (owner RULINGS 2026-09-12r; Fable 2026-09-12t) — lane `v2mouthgate`

Owner: "we should never emit anything for actual tunnels, only the tunnel mouths and
entrance/exit ramps … This applies to both rail and highway. The one exception is …
shallow tunnels with object based roofs that need an open trench." Scout
`v2tunnelmouths` on the 1.0.321 LEMD products: the bore already emits NOTHING
(`planar/structures.py:12-15`, cells cut 0); the exception is already the law twice
(`[cutout.sunken_road]` Law B requires a roof, `[cutout.wall_corridor]` Law C
requires headroom; `[tunnel.object]` REFUSES a roof) and never keyed on OSM. The
violation is the MOUTH: a bore is admitted by ≥ 1 m of cover under ANY cell
(`structures.py:238`) and then BOTH mapped ends become mouths with no containment
test (`structure_approach.py:282-294`). LEMD's two rail bores (4.9 km each) are
admitted by 125–162 m under the `building12` pad, their north mouths (on the field,
under T4) are refused against that pad, and their SOUTH-WEST mouths — 2.4 km outside
the OSM load box, 4.0 km west of every other patch feature, 95 m above the field —
are built: ramps 960/962, rims 691/692, banks 694/695 (149 vertices) that set the
patch's whole western bbox edge. They carry zero grade rows; the census cannot see it.

1. **A MOUTH IS BUILT WHERE A PILOT WOULD SEE IT** (owner 12ab, 12al): a `Mouth`
   whose point (and whose ramp reach) lies outside the governed region — the
   classified cover ⊕ `[tunnel] mouth_standoff_m` (150 m; 12aa/12ac) ∪ the APPROACH
   CORRIDOR of §31 (2) — is dropped at `mouths()`, named in the structures line
   (`mouths off-field N`); outside both it is raw DEM. A bore with no such mouth
   emits nothing. The corridor is ONE derivation shared with the cockpit block.
2. **ADMISSION FOLLOWS THE MOUTH, NOT THE BORE**: the cover test moves from "≥ 1 m of
   the bore under any cell" to "a mouth on the field" — a bore 5 km long admitted by
   one cell far from its only surviving mouth is the defect generator.
3. **DEAD KEY DELETED**: `[tunnel] bore_cut_clearance_m` (`structures.toml:12`,
   `model.py:297`) has no reader in v2 — removed with its schema line.
4. **BARS**: LEMD faces 960/962, rims 691/692, banks 694/695 gone; the patch bbox's
   west edge back at the airside extent (−3.594, was −3.641); every other LEMD
   structure byte-identical (15 highway corridors, Bridge4's cutting, the 2 decks);
   SPJC's two mouths and OTHH's object/wall-corridor set unchanged by dry read (their
   structures lines); ONE `--engine v2` LEMD build against the ledger base; the
   harness census unchanged (4,408 law-true on 1.0.321 — no tunnel rows exist);
   twins (an off-field mouth is dropped; an on-field one stays; a roofed corridor
   is untouched); suite.

**MEASURED** (lane `v2mouthgate`, branch `claude/v2mouthgate` off main `c1bcb73b`;
ONE tree, three arms, the shared corpus.  Rounds: the lane stopped on two misses,
RULINGS `2026-09-12aa` ruled `mouth_standoff_m` 100 m, and owner `2026-09-12ab`
answered 12aa-1 "Build them" — admission is BY THE MOUTH, the cover test deleted.)

Arms — BASE `c1bcb73b` (`v2mouthgate_base`, artifact `aafb8a0b4800`, body
`d3829dcb10c6`, 484 s) and the ruled tree (`v2mouthgate_r2`, artifact
`4a2a66a539fc`, body `b758bc344c3b`, 383 s).  The base reproduces the shipped
1.0.321 line and census exactly: `bores 68 (uncovered 47) mouths 41 duals merged 7
tunnels 17 decks 2 cells cut 0 refused 118`, 4,408 law-true / 1,859 adjudicated.

Ruled tree: `structures: bores 68 (no on-field mouth 36, mouth-only built 11,
replaced by objects 2)  mouths 48 (off-field 83)  duals merged 7  object corridors 1
door ramps 0  sunken roads 0  wall corridors 0  tunnels 26  decks 6  cells cut 2
refused 118`.

* **THE SITE IS GONE.**  The two rail mouths at 40.4805, −3.6395 build nothing:
  ramps 960/962, rims 691/692, banks 694/695 (149 vertices) absent, the 149 patch
  nodes west of −3.60 are 0, and the bbox west edge comes back 3.5 km — lon min
  −3.64071 → −3.59918 (the westernmost feature is now one of the newly built
  on-field portals at 40.48619, −3.59878; the airside extent is −3.59384).
* **ROUND 3, THE STANDOFF AT 150 m** (`v2mouthgate_r3`, artifact `d27130a304b3`,
  body `4d66e96d21b7`, 387 s; the 100 m arm `v2mouthgate_r2` / `4a2a66a539fc` /
  `b758bc344c3b` is the previous step).  Of the five on-field highway corridors the
  50 m standoff dropped, 100 m returned three (40.48701,−3.55443 / 40.48974,−3.54980
  / 40.49455,−3.55410) and 150 m returns a FOURTH byte-identically (40.48995,−3.55896,
  the same 16-vertex ramp, 0.3 m of centroid).  **40.51063,−3.56311 is still not
  built**: its mouth (bore `-6028`) stands **208 m** off the field — outside 150.
  The "natural gap" the value was chosen in (146 → 208) is exactly that corridor's
  own drop; keeping it needs ≥ 210 m, after which the next drops are 228, 267, 277,
  361, 383, 393, 429 m (the widest gap left is 208 → 228).  Unruled, so 150 stands
  and the corridor is OWED a decision.
  Line: `bores 68 (no on-field mouth 35, mouth-only built 12, replaced by objects 2)
  mouths 55 (off-field 76)  duals merged 9  object corridors 1  tunnels 29  decks 6
  cells cut 2  refused 118`; ramps 18 → 33.
  Census 4,408 → **4,576** law-true (+168), adjudicated 1,859 → **1,928** (+69):
  `within_shape` +132, `taxi_box` +65, `strip_transverse` +6; against
  `airside_no_step` −22, `strip_longitudinal` −6, `transverse` −4,
  `resa_transverse` −2, `frontage_near_miss` −1.  (At 100 m the same ruling read
  +104 / −87; the extra corridors admitted between 100 and 150 m carry the +64
  law-true and turn the adjudicated delta positive — the portals are real, so the
  rows are their surfaces meeting the field, not the rail defect.)
* **THE MOUTH-ONLY PORTALS ARE BUILT** (owner 12ab): at 150 m, **12** bores admitted
  on an on-field mouth alone, named in the build line — `-16684, -16683, -15336,
  -12795, -7847, -5284, -4054, -4043, -3829, -6339, -1581, -1568` — mostly 2–4 km
  south (40.4587…40.4798, −3.570…−3.583).  `tunnels` 17 → 29, `decks` 2 → 6,
  `mouths` 41 → 55 (76 ends dropped off-field).
* **CENSUS BY STANDOFF** (harness, one tree, against the same base): 50 m with the
  cover test deleted read 4,737 / 1,910 (+329 / +51); 100 m read 4,512 / 1,772
  (+104 / −87); **150 m, the ruled value, reads 4,576 / 1,928 (+168 / +69)**.
* **DEAD KEY** `bore_cut_clearance_m` deleted (toml + `model.py`; the law loader is
  strict, so a stale key refuses).
* **DRY READ (no build).**  OTHH's tunnel set is corridor-driven — object and
  kerb-wall corridors are built from the pack's own geometry through
  `object_groups` / `extra_groups`, which never pass through `mouths()`, and the
  corridors' footprints are inside the governed region — so its shipped line
  (`bores 22 (uncovered 13, replaced by objects 6) mouths 4 object corridors 8
  tunnels 9`) keeps its object-replaced mouths.  Its four remaining OSM mouths are
  NOT proven unchanged (LEMD drops that class beyond 100 m and no OTHH product on
  disk carries the distances), and under 12ab OTHH's 13 uncovered bores may now be
  ADMITTED wherever a mouth stands on the field — unmeasured.  SPJC's two on-field
  mouths are the scout's reading (`2026-09-12t`); no SPJC v2 product is in the tree.
* Twins: `tests/auto_patch_v2/test_v2mouthgate.py` (6) — an on-field mouth built,
  an off-field one dropped and counted, a bore under cover with no on-field mouth
  emits nothing, the standoff read from the law (both sides of the boundary), a
  mouth outside every standoff whose RAMP REACH runs onto a cell beyond it kept,
  and a mouth on the field whose bore covers nothing BUILT and named — plus
  `test_v2wallcorridor.py::test_the_mouth_gate_leaves_the_roofed_corridor_untouched`.
  Suite 1,176 passed / 1 skipped; targeted v1 tunnel set 151 passed with 12p's
  pre-existing `test_tunnel_portal_fidelity::TestClearanceAnnulus` red.
* A concurrent process wrote 11 New Zealand paths into the shared repo during the
  DISCARDED first arm (CONTAMINATED flag worked, artifact not stored); the base and
  both kept arms report the shared repo UNCHANGED.
### 29.1 **MEASURED, ROUND 2 — THE APPROACH CORRIDOR** (lane `v2approachcorridor`, branch `claude/v2approachcorridor` off main `19af2772`; owner RULINGS 2026-09-12al answering 12ae-1: "if it would be visible from an arriving or departing aircraft it should be cut, if not we can leave it raw DEM")

**THE CORRIDOR, ONE DERIVATION.**  `src/auto_patch_v2/law/approach_corridor.py`
(`ApproachCorridor`): per runway END, `[cockpit] approach_km` (5) beyond the
threshold along the extended centreline, `[cockpit] approach_half_width_m`
(2,000 m, the new key) to each side.  The ENGINE reaches it through
`planar/structure_approach.approach_corridor_of` (axes = `airport.runways`'
apt.dat thresholds) and `FieldRegion(polys, mouth_standoff_m, corridor)`; the
HARNESS through `check_grade.cockpit_geometry` (axes = the emitted runway
rings' principal axis, `grade_law.runway_axis_and_width`, joined by ref).  Same
class, same two law numbers, one rectangle — twinned on one fixture.  The 5 km
runway-axis DISC is deleted, and with it the `approach_m` argument of
`cockpit_in_view`, so no caller can pass a radius in.

**(1) THE SHIPPED LEMD PRODUCTS** (`Patches/+40-010/+40-004/`, the owner's
1.0.323 rebuild, `LEMD_auto.patch.osm` mtime 2026-09-12 12:11; copied before
reading).  4 runway axes -> **8 corridors**, 0 boundary rings (so at LEMD the
corridor is the WHOLE in-view test):

| corridor | threshold | outward | tip (5 km) |
|---|---|---|---|
| 14L/32R:0 | 40.49705,-3.55999 | 322.3° | 40.53258,-3.59611 |
| 14L/32R:1 | 40.46790,-3.53037 | 142.3° | 40.43237,-3.49426 |
| 14R/32L:0 | 40.48619,-3.57737 | 322.2° | 40.52170,-3.61352 |
| 14R/32L:1 | 40.45522,-3.54583 | 142.2° | 40.41970,-3.50967 |
| 18L/36R:0 | 40.53545,-3.55935 | 359.8° | 40.58036,-3.55954 |
| 18L/36R:1 | 40.49990,-3.55921 | 179.8° | 40.45499,-3.55903 |
| 18R/36L:0 | 40.53320,-3.57484 | 359.8° | 40.57812,-3.57509 |
| 18R/36L:1 | 40.49200,-3.57461 | 179.8° | 40.44708,-3.57437 |

(each corridor's four corners are in the lane's read; 14R/32L:0's ring is
40.49719,-3.55869 / 40.53270,-3.59485 / 40.51070,-3.63220 / 40.47519,-3.59604.)

* **`-6028`'s mouth at 40.51063,-3.56311 is IN** — corridor 14L/32R:0,
  **1,358 m along** its 5,000 and **716 m lateral** of its ±2,000; distance to
  the nearest corridor edge **0.0 m**.  12ae's open question is answered by the
  law: a portal 208 m off the classified surfaces, on the 32R approach, is what
  an arriving aircraft looks at.
* **The two rail mouths at 40.4805,-3.6395 are OUT** — nearest corridor
  14R/32L:0 (the 14R approach side the owner named), 2,720 m along it but
  **4,547 m lateral** of ±2,000: **2,547 m outside the nearest corridor edge**.
  They stay raw DEM, and the §29 round-1 result stands.
* **THE COCKPIT BLOCK'S VIEW TEST, before -> after, on the shipped products**
  (one tree, one parse, the retired disc rebuilt beside the corridor):
  rows that LEAVE "in view" — LEMD **90** of 4,408 (4,318 stay), HECA
  **29,242** of 37,364 (8,122 stay), SPJC **1,450** of 2,180 (730 stay), CYXY
  **0** of 972, OTHH **1** of 1.  Nothing ENTERS view anywhere: the corridor is
  strictly inside the disc.  The buckets barely move, because what the disc
  admitted was mostly under threshold or spanned: the ONLY bucket change on the
  five airports is **HECA CRITICAL VISUAL 1 -> 0** (the 0.531 m
  `vertex_to_edge_step [apron|building]` at 30.1213393,31.4072652, now REPORT
  `beyond_view`); LEMD 22 motion / 5 visual, SPJC 2 / 2, CYXY 0 / 0 and OTHH
  0 / 0 are identical on both readings, and every census TOTAL is unchanged.

**(2) THE BUILD.**  ONE `--engine v2` LEMD build of the change
(`v2approachcorridor`, **362.3 s** wall, rc 0, `status optimal`, body
`b27faf5ce243`, artifact ledger **`cf95ca6d8341`**) against a base arm built at
main `19af2772` (`v2approachcorridor_base`, 350.7 s, body `803760c824e4`,
ledger **`9f6558283155`**).  The named base `3510458499f8` (the §32 clamped
arm) is a DIFFERENT code tree (`57bca3fe…` against main's `ca0ff868…`), so it
was not quoted as the control — but the base built here reproduces its patch
body EXACTLY (`803760c824e4` both), so the two arms are the same surface the
ledger arm carried.  `shared repo UNCHANGED` on both (full before/after
snapshot; 18 lock-churn operations on the base, the allowed class).

* **The structures line**, base -> change:
  `bores 68 (no on-field mouth 35, mouth-only built 12, replaced by objects 2)
  mouths 55 (off-field 76) duals merged 9 object corridors 1 tunnels 29 decks 6
  cells cut 2 refused 118`
  ->
  `bores 68 (no on-field mouth 20, mouth-only built 27, replaced by objects 2)
  mouths 87 (off-field 44, on approach 37 of 8 corridors) duals merged 16
  object corridors 1 tunnels 50 decks 13 cells cut 2 refused 122`.
* **EVERY MOUTH THE CORRIDOR ADDED IS NAMED** (the report's first 12 of 37,
  each with its true distance off the field): `-15327` at 162 m and 171 m,
  **`-6028` at 208 m**, `-5388` at 1,535 / 1,550 m, `-5383` at 1,550 / 1,530 m,
  `-5377` at 1,420 / 1,429 m, `-4928` at 2,237 m, `-4439` at 2,802 / 2,803 m.
  Mouth-only bores BUILT: `-16684, -16683, -15336, -12795, -7847, -5284,
  -4054, -4043, -3829, -6339, -1581, -1568` -> `-16684, -16683, -15336,
  -12795, -7847, -5388, -5383, -5377, -5284, -4928, -4439, -4054` (12 -> 27,
  the first 12 named).  The nearest drops are now 67 / 135 / 141 / 192 / 198 /
  210 / 214 / 220 m off the field AND outside every corridor.
* **THE RAIL MOUTHS DO NOT RETURN.**  Patch bbox lat **40.44976..40.53638 ->
  40.42891..40.53638**, lon **-3.59918..-3.52877 -> -3.60536..-3.50982**; 191
  nodes now stand west of -3.60 (the `-4928` portal at -3,769,-2,518 m), and
  none anywhere near -3.6395.  The patch grows south and east where the new
  portals are: ways **1,144 -> 1,230**, nodes **23,989 -> 25,697**.
* **THE CENSUS, cockpit block first** (harness, both arms, one tree):
  CRITICAL motion **4 -> 2** (the worst goes 0.940 m over 61.71 m `strip_arc
  [primary_parallel|primary_parallel]` at 40.5006629,-3.5740136 -> 0.670 m over
  58.03 m `strip_arc [junction|junction]` at 40.4625636,-3.5525152 — two
  grade-break rows gone with the surfaces the new portals rebuilt), CRITICAL
  visual **0 -> 0**, REPORT **3,605 -> 3,571**.
  LAW-TRUE **3,609 -> 3,573** (-36), ADJUDICATED **1,183 -> 1,143** (-40), and
  the whole delta is GROUNDSIDE: airside 3,557 both, groundside **51 -> 15**.
  By family: `within_shape` 2,832 -> 2,792, `airside_no_step` 428 -> 419,
  `strip_arc` 9 -> 8, `resa_transverse` 2 -> 1, `cross_shape` 1 -> **0**;
  against `taxi_box` 198 -> 204, `transverse` 80 -> 87, `strip_longitudinal`
  13 -> 15, `strip_transverse` 42 -> 43.  Engine verify rows 1,369 -> 1,354,
  with `tunnel_mouth_canonical` 16 -> 26 and `tunnel_deck_clearance` 2 -> 7 —
  the new portals' own rows.

**(3) TWINS** — `tests/auto_patch_v2/test_v2approachcorridor.py` (8): the
corridor is the law beyond each threshold and never back over the runway; an
airport with no runway holds NOTHING (the empty region is empty, not vacuously
true); the schema refuses a zero half-width and one at or over the corridor's
length (the retired disc wearing a corridor's name); a mouth in the corridor
far from the cover is BUILT and counted `mouths_on_approach`; one outside both
is DROPPED and named "outside every approach corridor"; a bore with neither
kind of mouth emits nothing; the engine and the harness read ONE corridor (same
class object, and the apt.dat-threshold rectangle equals the emitted-ring
rectangle within 1 m); and THE RETIRED BUFFER IS GONE (`cockpit_in_view` takes
no radius, no `runway_pts` cloud survives, and a row 4 km ABEAM a runway —
inside the old disc — is `beyond`).  `test_v2mouthgate.py`'s fixture was
amended in the same commit: its off-region ends now run SOUTH, across the
fixture runway's axis instead of along it, because "far from the cover" is no
longer off the region when it stands on an extended centreline — the ruling
working, visible in the twins.  **Suite** `tests/auto_patch_v2 tests/test_harness.py
tests/test_role_edge_census.py tests/test_mesh_sampler*.py tests/test_post_mesh.py
tests/test_object_rebake.py`: **1,214 passed / 1 skipped**, run TWICE (main
`19af2772` collects 1,206 / 1; +8 new).

**NOT DONE, named:** no OTHH / SPJC / HECA / CYXY BUILD under the new gate
(their mouths are read only on the shipped products, where the corridor changes
no bucket but OTHH's 4 OSM mouths and 13 uncovered bores stay unmeasured under
12ab+12al — still owed from 12ae).  No app build, no five-airport sweep, no
merge.  The two arms above were built BEFORE the line-budget extraction that
moved `_under_cover` / the region assembly / the mouth report into
`structure_approach.py` (`structures.py` stood at 999 lines and the additions
crossed the 1,000-line file law); the extraction is textual — the same
expressions, the same `unary_union` — and the CONFIRMING REBUILD on the
committed tree (`v2approachcorridor_x`, 364.2 s, ledger `93c615b05a58`) comes
back **body `b27faf5ce243`, byte-identical** to the arm quoted above, with the
same structures line.

## Spec (design-surface) §39

## §39 THE HAIRLINE LAW (Fable 2026-09-13; RULINGS 2026-09-13an / 13bk; owner reads SPLP 13ag, LEMD 13bi, KCLT 13bj) — lane `v2hairline`

Three sightings in one day of one class: a constrained edge laid within
millimetres of, and parallel to, another — the SPLP bank chain 2.37 cm from
the meridian (16,298 Triangle4XP nodes in 1.92 m), LEMD's two patch pavement
rings 0.06–0.26 mm from the retention basins' water edges (2.30 M sub-0.1 m²
triangles, 73 % of the tile, X-Plane stalled), and (pending the scout) KCLT's
tearing. Triangle4XP must recover both segments and fills the wedge with a
Steiner cascade; GEOS's OverlayNG falls back to its snapping noder on the
same inputs (13bi's 35 GB union is the suspect twin).

1. **NO EDGE BESIDE ANOTHER.** An emitted ring vertex or edge may not lie
   within `identity.min_distinct_spacing_m` (0.5 m) of a FOREIGN constrained
   edge — an OSM water edge, a tile border, a core road ribbon, another
   face's ring — unless it SHARES that edge's vertices exactly (the 11-dp
   identity join). A ring edge within the spacing of a water edge is
   SNAPPED onto the water edge's own vertices (the shore weld: water is a
   datum and already carries the vertex), never laid beside it. Applied at
   ONE site: the emitter's ring writer, after every face is final.
2. **THE CENSUS FAMILY `hairline_pair`** prices every emitted ring edge
   against every foreign constrained edge of the tile's vector map within
   the spacing and within 5° of parallel — CRITICAL unconditionally (a
   load-time and texture defect, not a height).
3. **THE MESH PRE-FLIGHT.** `O4_Mesh_Utils` audits the assembled `.poly`
   before Triangle4XP: any non-adjacent constrained pair within the spacing
   and within 5° of parallel is REFUSED by name (pair, markers, coordinates)
   — the tile fails in seconds, never after a 40-minute Triangle run.
   `mesh_region_tris.py --hairline-audit` is the instrument (promoted from
   the scouts' `nearpar.py`).
4. **THE LEMD CAUSE IS NAMED AT ITS SITE.** Bisect the 1773 batch on the
   LEMD capture for the pass that moved the pavement ring onto the water
   edge (the shore weld count fell 403,636 → 145,257): the seam-band and
   bank-coverage changes (13as), the level belt (13w), the bank cut (§37
   (3)), the basin footprint (§24 (4)) are the suspects, in that order.

BARS: LEMD (`Data+40-004.mesh` from ONE harness tile build or the app's):
sub-0.1 m² triangles 2,301,676 → low hundreds, aspect p50 7,549 → < 5, DSF
≤ 23 MB, triangles ≈ 2.93 M; `hairline_pair` 0 at LEMD, KCLT, SPLP, CYXY
and > 0 on the LEMD control; the pre-flight refuses a synthetic hairline
`.poly` and passes the four tiles; F-6, the basin, the ramps byte-identical
where they are not the cause; suite twice.

### §39 AMENDED — THE SUBJECT IS THE VERTEX; THE BANK IS WELDED TO THE MESH'S WATER (Fable 2026-09-13; RULINGS 2026-09-13bt, owner VMMC read 13br) — lane `v2hairline`

VMMC: both cliffs are `bank_foot` vertices 0.012–0.05 mm OFF the OSM sea chord,
as bent triples (bank legs sharing both endpoints with the chord) that an
edge-pair census skips as adjacent; the bank clipped its feet against the
DEM's water witness while the mesh constrains the OSM SEA edges.

- **(1') THE VERTEX.** Any emitted patch vertex — ring, breakline, `bank_foot`
  chain, any `.poly` marker — within `min_distinct_spacing_m` of a foreign
  constrained edge it does not lie ON is a `hairline_pair` row; segment
  adjacency is irrelevant.
- **(3') THE DEGENERATE TRIPLE.** The mesh pre-flight also rejects a path
  a→m→b laid beside a chord a→b (zero area by construction).
- **(5') ONE WATER WITNESS.** At `emit/bank.py`, after the DEM-water clip,
  every foot station is snapped to the nearest vector-map water / coastline
  vertex within the spacing; where only an edge is within the spacing the
  station is projected onto it and adopted as a shared vertex, or DROPPED
  (stations stopped at water or under the materiality floor carry no
  earthwork); no station may sit astride the 0.5 m bar.
- Instrument: `bentchord.py` promoted beside `--hairline-audit`.

BARS (VMMC, added to §39's): bent-chord triples under 0.5 m at the bank
chains 369 → 0; foot nodes within 0.5 mm of a SEA edge 15 → 0; sub-0.1 m²
triangles in the two 60 m boxes 376,041 → CYXY's class; the latent `bank:4`
site (22.147882733, 113.589822933) clean; `hairline_pair` > 0 on the VMMC
control, 0 on the arm.

### §39 AMENDED AGAIN — ANGLE-FREE, AND THE VECTOR MAP WELDS; §37 (3) AMENDED — ZONE EDGES ARE IN THE BANK (Fable 2026-09-13; RULINGS 2026-09-13bu, owner KCLT read 13bj) — lanes `v2hairline`, `v2zonebank`

KCLT: a `bank_foot` node 2.79 mm (and another 0.24 mm) from an OSM water edge
made `Vector_Map.insert_edge` split the water edge and mint a node — a
2.79 mm constrained WATER segment, 481,602 slivers; the pairs are at 29° and
89°, so a parallel gate misses them. Items 5 and the new coordinate are the
adjacent-ground zone-2 outer edge 4.6 m / 2.5 m in a cut with NO bank foot.

- **§39, angle-free:** `hairline_pair` and the pre-flight price (a) two distinct
  constrained NODES within `min_distinct_spacing_m` and (b) any constrained
  SEGMENT shorter than it; the 5° gate is deleted; 13bt's vertex-to-edge and
  degenerate-triple tests stand.
- **§39 (6) THE VECTOR MAP WELDS.** `insert_edge`'s split test is METRIC (a
  crossing within the spacing of an endpoint takes that endpoint; no node is
  minted), and after `snap_to_grid` every constrained node pair within the
  spacing is welded onto the senior node (water, tile border, coastline
  first) with the degenerate segment dropped. The stale 1e-7° comment at
  `O4_Mesh_Utils.py:645` is corrected.
- **§37 (3) amended:** every graded ring is in the bank's coverage, the
  adjacent-ground zone-2 outer rings included; a zone edge ≥
  `bank_materiality_m` off the DEM is load-bearing and gets its foot; census
  family `zone_edge_cliff` — a zone-band outer edge whose mesh slope exceeds
  1:1 where the DEM's is under half of it.

BARS: KCLT constrained segments under 10 mm 28 → 0, the three sliver
cascades 1,230,453 → CYXY's class, `hairline_pair` > 0 control / 0 arm (lane
`v2hairline`); KCLT item 5 (35.2007757, −80.9455609) and 35.2056385,
−80.9478669 banked at 1:3 — `zone_edge_cliff` 0 on the arm, > 0 on the
control; the 13ax lips re-read (lane `v2zonebank`).

## §39 THE HAIRLINE LAW (Fable 2026-09-13; RULINGS 2026-09-13an / 13bk; owner reads SPLP 13ag, LEMD 13bi, KCLT 13bj) — lane `v2hairline`

Three sightings in one day of one class: a constrained edge laid within
millimetres of, and parallel to, another — the SPLP bank chain 2.37 cm from
the meridian (16,298 Triangle4XP nodes in 1.92 m), LEMD's two patch pavement
rings 0.06–0.26 mm from the retention basins' water edges (2.30 M sub-0.1 m²
triangles, 73 % of the tile, X-Plane stalled), and (pending the scout) KCLT's
tearing. Triangle4XP must recover both segments and fills the wedge with a
Steiner cascade; GEOS's OverlayNG falls back to its snapping noder on the
same inputs (13bi's 35 GB union is the suspect twin).

1. **NO EDGE BESIDE ANOTHER.** An emitted ring vertex or edge may not lie
   within `identity.min_distinct_spacing_m` (0.5 m) of a FOREIGN constrained
   edge — an OSM water edge, a tile border, a core road ribbon, another
   face's ring — unless it SHARES that edge's vertices exactly (the 11-dp
   identity join). A ring edge within the spacing of a water edge is
   SNAPPED onto the water edge's own vertices (the shore weld: water is a
   datum and already carries the vertex), never laid beside it. Applied at
   ONE site: the emitter's ring writer, after every face is final.
2. **THE CENSUS FAMILY `hairline_pair`** prices every emitted ring edge
   against every foreign constrained edge of the tile's vector map within
   the spacing and within 5° of parallel — CRITICAL unconditionally (a
   load-time and texture defect, not a height).
3. **THE MESH PRE-FLIGHT.** `O4_Mesh_Utils` audits the assembled `.poly`
   before Triangle4XP: any non-adjacent constrained pair within the spacing
   and within 5° of parallel is REFUSED by name (pair, markers, coordinates)
   — the tile fails in seconds, never after a 40-minute Triangle run.
   `mesh_region_tris.py --hairline-audit` is the instrument (promoted from
   the scouts' `nearpar.py`).
4. **THE LEMD CAUSE IS NAMED AT ITS SITE.** Bisect the 1773 batch on the
   LEMD capture for the pass that moved the pavement ring onto the water
   edge (the shore weld count fell 403,636 → 145,257): the seam-band and
   bank-coverage changes (13as), the level belt (13w), the bank cut (§37
   (3)), the basin footprint (§24 (4)) are the suspects, in that order.

BARS: LEMD (`Data+40-004.mesh` from ONE harness tile build or the app's):
sub-0.1 m² triangles 2,301,676 → low hundreds, aspect p50 7,549 → < 5, DSF
≤ 23 MB, triangles ≈ 2.93 M; `hairline_pair` 0 at LEMD, KCLT, SPLP, CYXY
and > 0 on the LEMD control; the pre-flight refuses a synthetic hairline
`.poly` and passes the four tiles; F-6, the basin, the ramps byte-identical
where they are not the cause; suite twice.

### §39 AMENDED — THE SUBJECT IS THE VERTEX; THE BANK IS WELDED TO THE MESH'S WATER (Fable 2026-09-13; RULINGS 2026-09-13bt, owner VMMC read 13br) — lane `v2hairline`

VMMC: both cliffs are `bank_foot` vertices 0.012–0.05 mm OFF the OSM sea chord,
as bent triples (bank legs sharing both endpoints with the chord) that an
edge-pair census skips as adjacent; the bank clipped its feet against the
DEM's water witness while the mesh constrains the OSM SEA edges.

- **(1') THE VERTEX.** Any emitted patch vertex — ring, breakline, `bank_foot`
  chain, any `.poly` marker — within `min_distinct_spacing_m` of a foreign
  constrained edge it does not lie ON is a `hairline_pair` row; segment
  adjacency is irrelevant.
- **(3') THE DEGENERATE TRIPLE.** The mesh pre-flight also rejects a path
  a→m→b laid beside a chord a→b (zero area by construction).
- **(5') ONE WATER WITNESS.** At `emit/bank.py`, after the DEM-water clip,
  every foot station is snapped to the nearest vector-map water / coastline
  vertex within the spacing; where only an edge is within the spacing the
  station is projected onto it and adopted as a shared vertex, or DROPPED
  (stations stopped at water or under the materiality floor carry no
  earthwork); no station may sit astride the 0.5 m bar.
- Instrument: `bentchord.py` promoted beside `--hairline-audit`.

BARS (VMMC, added to §39's): bent-chord triples under 0.5 m at the bank
chains 369 → 0; foot nodes within 0.5 mm of a SEA edge 15 → 0; sub-0.1 m²
triangles in the two 60 m boxes 376,041 → CYXY's class; the latent `bank:4`
site (22.147882733, 113.589822933) clean; `hairline_pair` > 0 on the VMMC
control, 0 on the arm.

### §39 AMENDED AGAIN — ANGLE-FREE, AND THE VECTOR MAP WELDS; §37 (3) AMENDED — ZONE EDGES ARE IN THE BANK (Fable 2026-09-13; RULINGS 2026-09-13bu, owner KCLT read 13bj) — lanes `v2hairline`, `v2zonebank`

KCLT: a `bank_foot` node 2.79 mm (and another 0.24 mm) from an OSM water edge
made `Vector_Map.insert_edge` split the water edge and mint a node — a
2.79 mm constrained WATER segment, 481,602 slivers; the pairs are at 29° and
89°, so a parallel gate misses them. Items 5 and the new coordinate are the
adjacent-ground zone-2 outer edge 4.6 m / 2.5 m in a cut with NO bank foot.

- **§39, angle-free:** `hairline_pair` and the pre-flight price (a) two distinct
  constrained NODES within `min_distinct_spacing_m` and (b) any constrained
  SEGMENT shorter than it; the 5° gate is deleted; 13bt's vertex-to-edge and
  degenerate-triple tests stand.
- **§39 (6) THE VECTOR MAP WELDS.** `insert_edge`'s split test is METRIC (a
  crossing within the spacing of an endpoint takes that endpoint; no node is
  minted), and after `snap_to_grid` every constrained node pair within the
  spacing is welded onto the senior node (water, tile border, coastline
  first) with the degenerate segment dropped. The stale 1e-7° comment at
  `O4_Mesh_Utils.py:645` is corrected.
- **§37 (3) amended:** every graded ring is in the bank's coverage, the
  adjacent-ground zone-2 outer rings included; a zone edge ≥
  `bank_materiality_m` off the DEM is load-bearing and gets its foot; census
  family `zone_edge_cliff` — a zone-band outer edge whose mesh slope exceeds
  1:1 where the DEM's is under half of it.

BARS: KCLT constrained segments under 10 mm 28 → 0, the three sliver
cascades 1,230,453 → CYXY's class, `hairline_pair` > 0 control / 0 arm (lane
`v2hairline`); KCLT item 5 (35.2007757, −80.9455609) and 35.2056385,
−80.9478669 banked at 1:3 — `zone_edge_cliff` 0 on the arm, > 0 on the
control; the 13ax lips re-read (lane `v2zonebank`).

## RULINGS

## 2026-09-15i VMMC 15f ATTRIBUTED (scout, 1.0.340): the seafront tunnel is an OSM car-park bore admitted by the 150 m standoff and carried 600 m by six mapped bridges, cutting taxiway pav5; the zone band is emitted over the sea — RULED §34 (12) + §37 (11), lane v2vmmcshore

Item 1: probe 22.1618794,113.579745 is 0.00 m inside `tunnel_ramp`
−10098 (contains 35.9 m of coastline −687); one 492.9 m corridor of 6
ramps / 11 rims from OSM `highway=service tunnel=yes` −5508/−5507 (no
layer, no bridge; `tunnel_objects []`); admitted by
`deck_signature.is_tunnel_way` + the §29 (1) gate (cover ⊕
`mouth_standoff_m` 150, pav5 36 m away); floor 1.06 = 6.16 − 5.1 flat for
six faces because `bridge_deck` −3636/−3446/−3444/−1798/−2898/−5188 each
sever the climb; approach walk to `max_ramp_length_m` 600; taxiway pav5
(code E, junction) split into six faces at 3.58/4.28/4.50 m — the
corridor cuts every pavement bar runway family + pads (08-07 ruling 4).
VMMC totals: 11 ramps, 19 rims, three corridor groups (shore; 578–782
m; 1,132–1,182 m from the coast). Item 2: no WATER role, no bank; zone
1 lip 3 m + zone 2 code-E 19 m, `beyond_zone2 = dem` = 0.00 (GLO30
ocean): the 6.10 m drop as 26–32 % (zone 2) and 100–1,124 % (lip); 13
zone faces cross the coastline (3–195 m), rings at 0.00 up to 42 m
seaward — the second water plane; `strip_seam_tear` 61 (6.110 m, 238 %),
`adjudicated 225 FAIL`. Z0 6.10 is CIFP thresholds (apt.dat 5.79). The
flat-site pass already reads the water mask ("47.0 % … WATER … the
mask edge is the sea wall") — the zone derivation does not. RULED §34
(12) (serves the field; clipped by water; never cuts airside; a bridge
severs only when it crosses the bore) and §37 (11) (the shore trims
the zones; quay + sea wall; `sea_wall` family; tears exempt). Not
verified: the doubled plane needs `mesh_region_tris` on a build; VMMC
has no structures.json / no placement json (stock pack, 1,925
placements; no pack object implicated).

## 2026-09-15f OWNER VMMC READ (app 1.0.340): no tunnels into the water; a taxiway in the water drops straight to it — verbatim

1. "Should not be any tunnel here: 22.1618794, 113.579745, this whole
   long line of tunnels going out into the water and cutting the
   taxiway is an error and shouldn't be there."
2. Screenshot: a taxiway running along the sea, its edge falling as a
   long dark bank onto a pale sloped strip that then meets the water,
   with a second, translucent water plane offset from the shore. "With
   a taxiway in the water, I don't think we want any adjacent ground
   at all, the pavement should drop straight to the water with no
   slope."
Scout dispatched (attribution of the tunnel line's minting evidence;
the zone/bank emission at the sea edge) before the law.

## 2026-09-13cd — v2hairline MERGED (bd5e6952, lane 6bf8ecfb): §39 — THE LEMD CAUSE NAMED: `emit/bank.py:838-840` cuts the banked region by the water so the bank foot ring's vertices ARE the water polygon's, and the ring is then chord-split at `bank_chord_max_m` in the tmerc METRES frame while the mesh constrains the water edge as a straight segment in tile-relative DEGREES — a straight line in one frame is not straight in the other: at 40.4762773, −3.5456742 interpolating the water edge A→B at t = 1/3 in metres reproduces the emitted node BYTE-IDENTICALLY (gap 0.0676 mm, 0.000°, both endpoints shared); NOT a merge-sha regression of the 1773 batch — a frame mismatch present wherever the bank follows a water edge (the batch changed which rings do); the `pyproj` round trip refuted (0.0000 mm over ±0.05°). SHIPPED: (1) `emit/osm_adapter.weld_to_shore` (+ `shore_edges_of`, `WeldReport`) called ONCE from `pipeline/build.py` after `with_terrain_edges` — a vertex within `min_distinct_spacing_m` of a foreign water VERTEX snaps onto it; one in the INTERIOR of a water edge with both neighbours on the shore is DROPPED; the rest counted `stranded` (LEMD 95 candidates, 24 dropped, 0 stranded; KCLT 2 bank nodes dropped at the 723,015-sliver site, worst 0.0198 mm); sidecar key `shore_edges`; it covers the bank chains, so 13bt (5') is satisfied at §39 (1)'s one site and `emit/bank.py` is untouched; (2) `hairline_pair` — angle-free, vertex-subject, three readings (`shore` / `ring` / `short`), cockpit class `unmeshable` = CRITICAL; (3) `O4_Mesh_Utils.hairline_preflight` before every Triangle4XP call (`O4_HAIRLINE_PREFLIGHT=refuse|report|off`) and `mesh_region_tris.py --hairline-audit` (`nearpar.py` + `bentchord.py` promoted) — self-proved on the shipped `.poly`s: LEMD 118 unmeshable (the nine 15/1 pairs at 0.0595–0.2649 mm), VMMC bent chords 369 (13bt's number to the row), KCLT short segments 2,246 / 28 under 10 mm / 6 under 1 mm (13bu's numbers); (4) `Vector_Map.insert_edge` METRIC split test (`O4_VECTOR_SPLIT_M` 10 mm) — a crossing within the radius of any endpoint IS that endpoint, no node minted (KCLT's 2.79 mm water sliver cannot be born; verified safe on the LEMD tile). LEMD TILE (a lane `--tile` build): sub-0.1 m² triangles in the bbox 2,301,676 → 1,641; aspect p50 7,549 → 1.61; needles 1,625,081 → 2,792; tile triangles 3,149,290 → 2,734,780 (1770: 2,930,290); interior boundary edges 1.60 M → 574,723; `hairline_pair` adjudicated 29 → 5 (all at exactly 0.000 — a vertex ON the edge, which Triangle splits cleanly); CYXY 0 adjudicated (264 above the floor); KCLT patch 2 (`short`, 5.6 µm and 5.5 mm). DSF size not measurable in a lane tile build (imagery stands down). Suite 1,341/0 twice on main. RULED on the deviations: (i) the POST-SNAP VECTOR-MAP WELD is REFUTED AS IMPLEMENTED and ships OFF (`O4_VECTOR_WELD_M` 0.0): welding one node at 10 mm made Triangle4XP refuse the `.poly` ("Topological inconsistency after splitting a segment") — moving a node re-nodes nothing; it needs a re-noding pass (owed; code + 6 twins kept); (ii) the 0.5 m refusal bar as written would refuse every real tile (LEMD 684 pairs, KCLT 2,246 short segments) — the DEGENERATE FLOOR is 10 mm (13bu's own bar) with slenderness 1e4 and a 0.1 m outer-boundary clause; rows above the floor are stamped `out_of_scope = above_degenerate_floor` (CYXY 264 / 0) — ACCEPTED as the law's numbers; §39 amended in place; (iii) THE EMITTER'S OWN SHORT SEGMENTS: LEMD 932 and KCLT 1,635 constrained segments shorter than `min_distinct_spacing_m` (shortest 5.6 µm at 35.2153165, −80.9285365) — §39's law violated at emit time, independent of water — lane `v2shortseg` owed (the identity join must merge, never write, a sub-spacing edge). NOT MEASURED: VMMC's bars (its tile build was still running — 65+ min in the vector step, the 13bp VHHH cost, `v2gradecache` pending) and KCLT's tile (refused for a missing `N35W081_bathymetry_band` — needs `--refresh-data dem`, the OWNER's act; asked). Contamination note: the LEMD control build reported 6 `osm_layers` clip writes under `OSM_data/_regional_extracts/clips/clip_+021+0112_*` — tile +21+112, another lane's concurrent VHHH work (the 12j / 13ao class; the dumpguard chip's scope).

## 2026-09-13cg — v2hairline's VMMC MEASUREMENT (branch 8e566c17, merged 8c58e1a7 — frames only; the code was 13cd's) and RULED (Fable, §39 (6) restated): the VMMC tile built in the lane (3,845 s — the VHHH cost) reads bent chords 369 → 166 with NO sea/bank triple left (the 2 under 0.5 mm are water-vs-water), unmeshable pairs 419 → 119, the two 60 m boxes' slivers 677,820 → 406,393, the latent `bank:4` site CLEAN — PARTIAL, and the residual is the finding: a `bank_foot`-vs-`SEA` vertex at 0.0025 mm survives at 22.155210945, 113.576646308 (slenderness 4,004,066) and box A got WORSE (137,718 → 296,037) because the emit-side weld reads `TileWater` (`sea_area_from_coastline`) while the mesh constrains `include_sea`'s OWN sea edges — the two differ by micrometres: 13bt's two-witness shore lives in the MESH's own inputs, and the emitter cannot close it; only the vector map can. Six VMMC stations stay 481–501 mm from a SEAWALL breakline (a mesh-side construct absent from `shore_edges`). The VMMC arm is not single-variable (it carries the day's main incl. v2zonebank's `_foot_piece`). RULED: (i) ONE WITNESS — the emitter's `shore_edges` are built from the SAME sea polygons the mesh will constrain (the vector map's `include_sea` product, not a second derivation from the coastline), so the emit weld and the mesh agree to the 11-dp identity; the `SEAWALL` breakline (`O4_Vector_Map.py:157`, the 0.5 m inland limb) joins `shore_edges` so no station can sit astride the bar; (ii) THE VECTOR-MAP WELD WITH A RE-NODING PASS — the refuted post-snap weld (13cd) is re-armed only as weld + re-node: after moving a junior node onto its senior, every edge that passed within the radius of the junior is re-noded against the senior's edges (the `insert_edge` split machinery, now metric), so Triangle4XP's "topological inconsistency" cannot arise; the twin is LEMD's arm-2 `.poly` (the one that refused) meshing clean; (iii) `v2shortseg` folded in: the identity join must MERGE, never write, a sub-spacing constrained segment (LEMD 932, KCLT 1,635, VMMC 1,631; shortest 5.6 µm). Round 2 on the SAME lane (resumed). Bars: VMMC bent chords 166 → 0 sea/bank and box slivers → CYXY's class, the 0.0025 mm pair gone, the 6 seawall stations resolved; LEMD held at 1,641; the LEMD arm-2 `.poly` meshes; emitted sub-spacing segments 0 at LEMD / KCLT / VMMC; KCLT tile still needs the owner's `--refresh-data dem`.

## Tool: osm_site

| `Ortho4XP/tools/osm_site.py` | You have a coordinate and the question is WHAT IS THERE — which ways carry that spot, how they are tagged and roled, how many nodes they have, what altitudes those nodes carry — or you want one way's node chain dumped in order. Reads BOTH OSM dialects this repo produces (the emitted patch's single-quoted attributes with per-node `alt_abs`, and the Ortho4XP road feeds' double-quoted ones, plain or `.bz2`), so a patch and the feed it was built from can be read side by side in one process, at one probe point, in one projection. Several files are reported separately — that is the arm-vs-arm read (an owner artifact against a lane build) an attribution starts from. `--role` scopes to one emitted role, `--dump WAY` prints the chain with per-node altitude and distance, `--json` writes what the report printed. **It measures nothing and derives no law**: every value is read verbatim out of the file, and defect counts come from `harness/census.py` and nowhere else — a private re-count is the census-wrapper defect. A node with no `alt_abs` reports `None`, never 0.0 (no authority claimed it is a real state), and a dangling `nd` ref is reported, never dropped. Promoted 2026-08-12 from the round-20 lane's `kclt_site.py` (patches) and `osmfeed.py` (bz2 feeds) on their SECOND use (RULINGS `7e90032`, promote-on-reuse): two copies of one question asked of two formats, already drifted — one could read `alt_abs`, the other could read bz2, neither could read the other's quoting. **`--contains` is the SECOND question, and it is not the first one** (added 2026-08-28, spec `docs/specs/lemd-pad-authority-carve-spec.md` Acceptance): `--at` reports the distance to a way's nearest NODE, so a point deep inside a large ring reads tens of metres away and NEVER 0.00 m — a lane quoted "1.20 m / 11.60 m outside" off exactly that and a containment read then put both owner probes 9.87 m and 3.88 m INSIDE the pad (`lemd-basin-trench-ramp-extension` Amendment 2). `--contains` asks WHICH RINGS COVER THIS POINT: geometry comes from the harness library's own parser (`check_grade._parse_osm`), imported and never re-spelled, and rings are grouped by `(role, ref)` and decided EVEN-ODD inside each group — a point in a hole ring is OUTSIDE its own pad, not inside two ways. **`--line LAT,LON:LAT,LON [--step M]` is that same containment answered along a SEGMENT, station by station** — the reading a "the plate covers the whole ramp" acceptance is stated in (the carve spec samples the deck line at ~2 m); both ends are always stations, and a run of stations INSIDE NOTHING is itself the finding. Neither prices a law nor counts a defect. **THE THIRD ROAD SOURCE (2026-08-28, LEMD ramp/road fidelity round):** a `.cache` file is the X-Plane DSF VECTOR ROAD NETWORK sidecar (`Airport_mod_cache/<pack>/o4_dsf_road_network_<tile>.cache`), unpickled through the engine's OWN record types (`auto_patch.dsf_road_network`) — never a second DSF parser — and presented as ways so `--at` / `--dump` / `--json` work on it unchanged. Reach for it where the OSM sources are EMPTY and the corridors still come from somewhere: at LEMD the tile carries no small-roads extract and `big_roads` is empty at both tunnel sites, so this sidecar is the only thing that can say how many chains cross a portal, what subtype each carries and whether it drapes (level 0) or flies (level 1+). A node reports NO altitude: the network's third column is a draping LEVEL FLAG, not metres, and it is reported as the `level` / `draped` tags it is. TWO SELECTION FRAMES, and the one in force is printed on every report and carried in the JSON (`selection_frame`): the nearest NODE (the default, the frame every pre-2026-08-28 caller reads in) or the closest approach to the POLYLINE (`--by-line`, the default for a `.cache`, because a DSF segment's shape points stand tens of metres apart while the road passes right over the probe — measured at LEMD item 1: nearest node 34.54 m, line 0.66 m). Both distances are always reported, so the two frames can never be mixed unnoticed. **`--relate` is the FOURTH question, and it is the DUPLICATION one** (added 2026-08-30, spec `docs/specs/othh-tunnel-mouth-canonical-spec.md`): `--at` says WHICH shapes are at a coordinate, `--contains` says which COVER it — neither says HOW THEY SIT AGAINST ONE ANOTHER, which is the whole of a "is this one corridor emitted twice?" question. It reports, per touching pair among the ways `--at` selected, the two areas, the OVERLAP AREA, the SHARED-BOUNDARY LENGTH and the containment verdict — same rings, same metre frame and the same harness-library parser (`check_grade._parse_osm`) as `--contains`, imported and never re-spelled. The shared-edge column is the discriminator the other modes cannot give: two surfaces that TILE (0 m² overlap, a long shared edge) are one surface emitted as two, which reads identically to two neighbours under `--at`. Measured basis (OTHH item 1, owner patch 2026-08-29): service_road -10051 vs tunnel_road -12306 — overlap 0.0 m², shared edge 211.22 m, union area == sum of parts, i.e. one road corridor cut into three shapes. It prices no law and counts no defects. Twin: `tests/test_osm_site.py` (both dialects, both containers, absent-altitude-is-None, radius/role selection, nearest-first order, dump order, dangling refs, the CLI's JSON IS the library's result, the refusals, the nearest-node-is-not-containment trap, the hole ring, the role filter, both-ends stations, the DSF cache source with its two selection frames, `--relate` reporting a tiling pair as 0 m² overlap with a long shared edge and an overlapping pair as overlap, and this index row). **`--relate` reads the FEATURE rings too and the rim's stand-off** (2026-09-08a, lane `v2trenchgap`): the role-less `o4_feature` ways the census skips (`structure_rim`, `gap_interior_ring`) join the ring set as role `feature:<name>`, and each pair carries `boundary_gap_m` (the smallest vertex-to-other-exterior distance over the vertices not on it) with `a_off_b_median_m` / `b_off_a_median_m` (each direction's median) — `gap_m` reads 0 for a rim around its ramp, and the question there is how far the rim's vertices stand off the ramp edge (the mesh wall band's width: OTHH tunnel sites read 1.77 / 1.12 m under 06b's `rim_gap_m`). Quote the median for the side stand-off; the minimum is a corner's. |

## Tool: role_overlap_read

| `Ortho4XP/tools/role_overlap_read.py` | The question is WHAT STANDS ON WHAT — *how many square metres of one emitted role/ref class lie on another class's footprint* — which is the single number a ruling of the form "the gap-fill spine must STOP at groundside pavement" (RULINGS 2026-08-30 ruling 4) is accepted or refused on. No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a face lying flat on a lot breaks no grade law and reports ZERO rows; `osm_site.py` answers one coordinate and `arm_site_read.py` one named place; `void_census.py` asks enclave TOPOLOGY; `lattice_overlap_read.py` asks CONTAINMENT of the two role-less membrane classes by LENGTH. This is the AREA sweep: `--over ROLE[:REF] --on ROLE[:REF],...` reports the populations, how many OVER ways stand on the ON union, the total m², and per stacked way its own area, the area over, the fraction and the ON shapes it stands on, largest first. **It measures no law and counts no defects** — geometry, the metre frame about the sidecar's own anchor and the role-carrying rings come from the harness library (`check_grade._parse_osm` / `_ll_to_m_factory`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. A patch with NO `.axes.json` sidecar is REFUSED (no anchor, no metre frame — an area in the wrong frame looks right and is not). `--min-area` (default 1.0 m²) is emit rounding, not a law threshold. Measured basis (HECA round 6b/6c): on the round-6b closing arm `graded_strip:gap_fill_spine` over `groundside_pavement` = 18 strips / 26,780 m², two faces carrying 24,288 m² of it (3190 over lot 2813 by 13,657 m², 70 %; 3192 over 2814 by 10,631 m², 63 %), while the same read over `service_road,service_junction` — 34 strips / 25,073 m² — said the annulus class was not one ruling's alone. Promoted 2026-08-30 from the HECA round-6b lane's scratchpad on its second use (RULINGS `7e90032`). `--pad M` grows the ON union before the read and `--beyond` reports the COMPLEMENT — the OVER ways that do NOT reach it, totalled and split by ref: the OWNERSHIP read RULINGS 31b is stated in ("within SERVICE_ROAD_PAVEMENT_NEAR_M of aircraft pavement"), which is how Batch 4a priced HECA's far road-family population off the merged-main control (`service_junction` beyond 25 m of the airside roles: 1,526 of 1,777 rings / 473,248 m², of which 1,325 ref-less / 435,882 m²). `--site LAT,LON` (repeatable) answers a named place in the OVER class's own terms — which way covers it, its ref and area, and the distance from both point and ring to the ON class. Several patches are reported separately — the arm-to-arm read; quote it on identical options. **`--contains` is the CONTAINMENT CENSUS and it is a DIFFERENT FRAME** (2026-09-13, lane `v2zonehole`, spec §41 (1)): the overlap sweep above is a SOLID-frame question and reads 0 m² here BY CONSTRUCTION — the arrangement is a partition, so a face enclosed by another sits in its HOLE and never overlaps its solid. `--contains` asks whether a pavement face lies inside another pavement face's EXTERIOR RING (`--min-frac`, default 0.95 = §41 (1)'s own floor, the one spelling of `planar.overlay.ENCLOSED_MIN_FRAC` outside the engine), and reports per row the inner face and its area, the host, the RING fraction, the SOLID fraction beside it (which is what says the two readings are not the same question), the shared-edge length and the distance to the host's solid — a face that TOUCHES its host is a NOTCH cut into a body (absorbed by `planar.overlay.absorb_enclosed_pavement`), one that does not is an ISLAND in the middle of a taxiway loop (left alone). Measured basis (the owner's 1.0.329 HECA patch): 39 of 370 pavement faces contained, 65,772 m², every one at solid fraction 0.000, 33 notches / 6 islands — `cross_connector:pav77` 896 m² in `primary_parallel:pav73` is the owner's dip site (RULINGS 2026-09-13co item 2). **THE ANCHOR REPAIR** (same lane): the read used to do `side["anchor"]` and died `KeyError: 'anchor'` on every v2 patch — v2's `SIDECAR_KEYS` publishes no anchor, deliberately, and the harness library itself falls back to the MEAN OF NODES, which is the frame the census reads the same patch in. The sidecar is still REQUIRED; the anchor is used when the patch carries one; the frame in force is printed on every report and carried in the JSON (`frame`). **`--slivers` and `--hole-rings` are the FOURTH and FIFTH questions, and both are WIDTH questions** (2026-09-14, lane `v2slivers`, spec §41 (4) / RULINGS 2026-09-14g items 4/5): the reads above ask what stands on, or inside, what — neither asks whether a shape is BIG ENOUGH TO CARRY LAW, which is what a zone strip that mints a hump and a hole ring that ships across a service road have in common. `--slivers` reports every `graded_strip` face under `--strip-min-area` (50 m², `emit.terrace.strip_min_m2`) or narrower than `--strip-min-width` (3.0 m, `strip_min_width_m`) with its area, inscribed width, elevation span and the pavement face it borders longest — the HOST `planar.overlay.dissolve_sliver_zones` unions it into. `--hole-rings` reports every emitted `gap_interior_ring` way with the fraction of its area the faces INSIDE it cover (`--cover-eps`, `emit.terrace.hole_cover_eps`), its inscribed width, and a verdict: `covered` (a duplicate ring), `hairline` (narrower than `strip_min_width_m`: it can carry no transition) or `void` (a real hole, which KEEPS its ring). THE WIDTH IS THE MAXIMUM INSCRIBED CIRCLE's DIAMETER, imported from the engine's own `planar.overlay.inscribed_width_m` and never re-spelled: `2 A / P` is a mean-width proxy and over-counted HECA's narrow zone faces 42 → 153 (the ruling's own measurement). Measured basis (the owner's 1.0.331 HECA patch, mean-of-nodes frame): 338 `graded_strip` faces / 2,895,389 m², of which 57 slivers / 1,647 m² (51 under 50 m², 42 under 3 m) — shape 1035 `adjacent_ground:taxi:E:zone1#38`, 15.7 m², 2.16 m, z 105.86–106.01 against a taxiway at 104.4, host `cross_connector:pav115`, the owner's hump (RULINGS 2026-09-14c item 4); and 57 `gap_interior_ring` rings / 926,251 m², 11 covered ≥ 98 %, 5 hairline, 41 real voids — way −10231, 29.5 m², 1.60 m wide, 92.3 % covered, the ring that shipped across `service_road:route4`. Both price no law and count no defects. Twin: `tests/test_role_overlap_read.py` (the area IS the intersection, the ROLE:REF selector is exact, the floor both ways, prices-no-law, the no-sidecar refusal, the `--pad`/`--beyond` complement, the `--site` read, the inscribed width agreeing with the engine's and the proxy disagreeing, the tool's three §41 (4) constants being the law table's, the sliver read naming the host, the hole read's cover fraction / width / three verdicts, the three reads refusing to run two at a time, and this index row) and `tests/auto_patch_v2/test_v2zonehole.py` (the anchor-less sidecar is not a crash, the containment census's ring-vs-solid frames, and that the two spellings of 0.95 agree). |

| `Ortho4XP/tools/role_overlap_read.py` | The question is WHAT STANDS ON WHAT — *how many square metres of one emitted role/ref class lie on another class's footprint* — which is the single number a ruling of the form "the gap-fill spine must STOP at groundside pavement" (RULINGS 2026-08-30 ruling 4) is accepted or refused on. No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a face lying flat on a lot breaks no grade law and reports ZERO rows; `osm_site.py` answers one coordinate and `arm_site_read.py` one named place; `void_census.py` asks enclave TOPOLOGY; `lattice_overlap_read.py` asks CONTAINMENT of the two role-less membrane classes by LENGTH. This is the AREA sweep: `--over ROLE[:REF] --on ROLE[:REF],...` reports the populations, how many OVER ways stand on the ON union, the total m², and per stacked way its own area, the area over, the fraction and the ON shapes it stands on, largest first. **It measures no law and counts no defects** — geometry, the metre frame about the sidecar's own anchor and the role-carrying rings come from the harness library (`check_grade._parse_osm` / `_ll_to_m_factory`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. A patch with NO `.axes.json` sidecar is REFUSED (no anchor, no metre frame — an area in the wrong frame looks right and is not). `--min-area` (default 1.0 m²) is emit rounding, not a law threshold. Measured basis (HECA round 6b/6c): on the round-6b closing arm `graded_strip:gap_fill_spine` over `groundside_pavement` = 18 strips / 26,780 m², two faces carrying 24,288 m² of it (3190 over lot 2813 by 13,657 m², 70 %; 3192 over 2814 by 10,631 m², 63 %), while the same read over `service_road,service_junction` — 34 strips / 25,073 m² — said the annulus class was not one ruling's alone. Promoted 2026-08-30 from the HECA round-6b lane's scratchpad on its second use (RULINGS `7e90032`). Several patches are reported separately — the arm-to-arm read; quote it on identical options. Twin: `tests/test_role_overlap_read.py` (the area IS the intersection, the ROLE:REF selector is exact, the floor both ways, prices-no-law, the no-sidecar refusal, and this index row). |

## Tool: mesh_region_tris

| `Ortho4XP/tools/mesh_region_tris.py` | Built-mesh triangle count inside the airport bbox — the number load time tracks — and, with `--area-bands`, the triangle SIZE distribution beside it: the near-degenerate SLIVER class (< 0.1 m^2, which carries no visible ground and costs load time outright), the sub-texel classes, and the visible class, each with its ground cover, in and out of the box. The band edges default to `0.1,1,TEXEL` and the literal `TEXEL` resolves to one orthophoto texel^2 at the bbox's mid latitude (ZL16 = 2.0662 m / 4.269 m^2 at HECA), because a triangle finer than a texel cannot be resolved by the imagery at all — that is the honest floor for "invisible geometry". `--json` stamps the bbox, the ZL and the edges beside the counts. Absorbed 2026-08-07 from `tmp/density_audit/meshtexel.py` on its second use (the sliver spec's phase-B interventional read) — promote-on-reuse, the near-fit extended rather than forked. **A/B WARNING, stated by the tool itself:** derive the bbox with `--bbox`, never `--patch-osm` — two arms' patches give two different boxes, which is two populations. `--aspect` adds the SHAPE half beside the size half: the ratio `longest edge / (2*sqrt(3) * inradius)` (1.0 = equilateral, rising without bound as a triangle degenerates) as p50/p90/p99/max over the in-bbox triangles, plus the NEEDLE count at `--aspect-flag` (default 20.0, a REPORTING threshold and an assumption, never a law — two runs quoted at two thresholds are not comparable). Reach for it whenever the question is "did this change mint a LONG-TRIANGLE artifact class", which the area bands structurally cannot answer: a 40 m x 0.5 m needle and a 4.5 m equilateral have the same area and land in the same band. Added 2026-08-08 (fabricA, THE FABRIC MODEL Phase A) because that round's acceptance is stated in exactly those terms; measured HECA in-bbox control p50 2.04 / p99 23.35 / max 975.53, sparse arm 2.02 / 22.76 / 975.53. Twin: `tests/test_mesh_region_tris.py` (a hand-built MEDIT mesh of deliberate areas; the published texel constants; every band-spec refusal; the aspect normalisation proven on a known equilateral and a known needle, and proven to SEPARATE two same-area triangles the bands cannot). **`--interp-alt-audit` (2026-08-28, the CYXY INTERP_ALT round) answers "who owns this mesh's altitudes" in the THREE artifacts it actually lives in, from the one MEDIT parse this tool already owns** (`--inputs PREFIX` for the build's `.node`/`.poly`, tile origin parsed from the mesh name or `--tile LAT LON`): the SEAL — is every INTERP_ALT seed in a BOUNDED face of the arrangement of the INTERP_ALT-marked segments, which is exactly Triangle4XP's own containment condition (regionplague crosses any segment sharing no bit with the flood); the PLAGUE — did every attr-8 triangle of the built mesh land inside that same envelope, i.e. did the marks survive the CDT; and the DOMAIN — how far does the CONNECTED attr==8 sub-mesh that `O4_Mesh_Utils` harmonic-extends the patch ring altitudes over (R18-1b) reach beyond the patch coverage, component by component, with each component's patch-valued anchor count and span. Reach for it whenever a mesh contradicts its own `.alt`: reading only one of the three is how +60-136 was first attributed to a plague leak that this audit refuted in 1 s — seal 0 of 578 seeds unsealed, plague 0 of 22,923 triangles outside the envelope, domain ONE 10.2 km component carrying all 6,677 patch-valued vertices against a 1.94 km^2 patch coverage (the town's levelled road network, welded to the airport wherever a road touches it). `--json` stamps every count. | **`--water-audit` (2026-09-09, lane `v2water`, owner RULINGS 09m) answers "is the water flat, and at its datum" from the mesh alone**: over every triangle carrying a water bit (WATER|SEA|SEA_EQUIV — the mask is twin-asserted against `O4_Vector_Utils.Vector_Map.dico_attributes`, never a second spelling), how many water VERTICES stand at 0.000 and how many do not with the commonest values named, how many water TRIANGLES span more than `--water-step-flag` metres corner to corner (a one-triangle step in open water is a sawtooth, not terrain), and the ATTRIBUTE HISTOGRAM beside them — which is the attribution: `SEA|INTERP_ALT` (10) means a patch seed reached that water and exempted it from sea levelling, bare `SEA` (2) means it did not. `--near LAT LON RADIUS_M` repeats the read at a site. Measured at OTHH on the owner's 1.0.297 build: 2,180 of 2,197 water triangles attr 10, every water vertex exactly 0.000 (699) or 3.962 (782), 1,692 stepped. Extended here rather than forked: the MEDIT parse, the tile-origin resolution and the JSON stamping are this tool's already. Twin: `tests/test_mesh_water_audit.py` (a hand-built mesh of one flat sea triangle, one 3.962 m stepped one, one inland body and one attr-8 land triangle that must not be counted). **`--hairline-audit` (2026-09-13, lane `v2hairline`, spec §39 (3), owner RULINGS 2026-09-13an/13bk/13bt/13bu) answers "can Triangle4XP even build this `.poly`" BEFORE it is run**, ANGLE-FREE, in the FOUR topologies the four measured sightings hid in: `node_pairs` (two distinct constrained nodes inside `--hairline-spacing`, 0.5 m = `emit.identity.min_distinct_spacing_m`), `short_segments` (a constrained segment shorter than it — KCLT's 2.7913 mm water sliver, 481,602 triangles under 0.1 m^2), `bent_chords` (VMMC's degenerate triple `a->m->b` beside the chord `a->b`, which SHARES both endpoints and is invisible to every non-adjacent pair test) and `vertex_edges` (LEMD's ring vertex 0.0595 mm from a water edge, and SPLP's bank foot 23.7 mm from the tile border). There is NO parallel gate: KCLT's two cascades stand at 29.08 and 89.20 deg. Each row carries its gap, markers, coordinates and SLENDERNESS (the neighbouring feature's length over the gap = the Steiner cascade Triangle must build). The UNMESHABLE subset the mesh pre-flight refuses on is anything under `--hairline-degenerate` (0.010 m, KCLT 13bu's own bar), over `--hairline-slenderness` (1e4), or beside the OUTER boundary under `--hairline-boundary-gap` (0.1 m; `-Y` forbids Steiner points there, so the wedge can only be relieved by splitting the OTHER segment) — all three ASSUMPTIONS and REPORTING thresholds, never laws. Reach for it whenever a tile's triangle count jumps, a texture tears at a seam, or X-Plane will not load a tile. Measured on the shipped 1.0.327 tiles: LEMD `Data+40-004.poly` 57 / 957 / 157 / 2,562 with 118 unmeshable (the bank foot 0.0595–0.2649 mm from the retention basins' water edges, slenderness 417,901 down to 95,714); VMMC 321 / 2,271 / **369** / 7,448 (the bent-chord count 13bt reports to the row); KCLT 102 / **2,246** / 293 / 5,794, 28 short segments under 10 mm and 6 under 1 mm (13bu's own numbers). Takes the `.poly`/`.node` alone (`--inputs PREFIX`, no `--mesh`), so it runs before a build finishes; omit `--tile` on a negative-longitude tile (argparse cannot take `-81`) and the origin is parsed from the file name. THE ONE IMPLEMENTATION is the engine's own (`O4_Mesh_Utils.hairline_findings` / `hairline_refusals`, which `hairline_preflight` calls before every Triangle4XP invocation; `O4_HAIRLINE_PREFLIGHT=report|off` downgrades or skips the refusal): promoted from the scouts' `nearpar.py` and `bentchord.py` on their second use, never forked, so the instrument and the refusal can never disagree. Twin: `tests/test_mesh_hairline_preflight.py` (all four sightings at their own numbers, the 0.30 m neighbouring ring and the 0.444 m land segment that must NOT be refused, the shared-vertex chain that is not a pair, and every knob). **`--z-xref` (2026-09-13, lane `v2hairline`, owner RULINGS 2026-09-13cp) answers "who owns this node's altitude" between the vector map and the built mesh**: every `.node` z against the altitude the `.mesh` carries at the SAME coordinate, counted per `.poly` ATTRIBUTE with the worst offender named, over `--z-flag` (2 m); needs `--mesh`, `--inputs` (or a `.mesh` its inputs sit beside) and a `--bbox`. Reach for it whenever a pass makes two ways SHARE a node — sharing a node is sharing an altitude, and picking the wrong one silently re-levels the crossed chain. Promoted from scout `v2lemd329`'s `xref.py` on its second use (13cp's attribution, then this lane's before/after), extended not forked: the disc became this tool's own `--bbox`, and the MEDIT parse, the tile-origin resolution and the JSON stamping were already here. Measured at LEMD +40-004: attr 1 (WATER) 56,830 matched, 10,337 over 2 m before the 13cp z carry and 10,338 after — which is how that carry's premise was REFUTED (the branch fires twice on the whole tile, so the water z error is a different, still unattributed mechanism). **`--patch-edge-step` (2026-09-13, lane `v2bankfoot`, owner request via the round's coordinator — the bank_foot OMIT arm) is the other half of `--z-xref`**: for every `PATCH_RING_MARKER` mesh vertex, the altitude STEP to a triangulation neighbour that is NOT on a ring and stands OUTSIDE the patch coverage (median / p95 / max with its coordinate, counts over 1 m and 3 m). §8.4's measured defect is that Ortho4XP's mesh does not blend from the patch boundary to the DEM — it drapes the raw DEM right outside the constrained ring, so a ring standing 16.6 m off the terrain builds a 16.8 m cliff ONE TRIANGLE wide — and the BANK is the owner's answer to it. So `--z-xref` says whether the ribbons carry their own altitude and THIS says whether the patch edge is a bank or a wall; an arm that omits the bank_foot class altogether is judged on both. Same three artifacts this tool already parses (`--inputs PREFIX` + `--mesh`), writes nothing. Twin: `tests/test_mesh_region_tris.py` (a hand-built ring at 600 m beside an outside vertex at 588 = a 12 m step over two pairs, the graded edge that reads 0, and the `.poly` with no ring segment that says so instead of printing a number). |

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N] [--why-hard-stage 1]` on either a `--replay` arm or a `--why-from PKL`; `--why-from PKL --probe-site LAT,LON [--probe-drop M] [--probe-arm TERM=V ...]`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (**and THE CLUSTERS beside the partition and the groups** — lane ``v2padjoin`` 2026-09-14: a capture without ``Airport.clusters`` leaves §30 (4)'s cluster pad, its apron reach and §16g (10)'s derived pads INERT in every replay of it, so a pads-ON arm silently measures the pads-OFF law; a capture predating them has them DERIVED at replay off its own partition, named on stdout) (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently).  **`--why-hard-stage 1`** reads §20b STAGE 1's OWN ASSEMBLY instead of the full problem's (`solve.design.stage_split`'s drop + fixed): the AIRSIDE hard set, in the rows and the metre scaling stage 1 enforced them under. The full read cannot answer "does the AIRSIDE solve settle" — the airside rows are a subset of 325k whose population and scaling the stage's own drop changes — and that is exactly the claim RULINGS 13y (B) / 13ab / 14as make (lane `v2settle`, which used it to split HECA's "42 unsettled rows" into 9 CONSTANT rows the solve can never move, 6 HELD runway rows at the projection's own bar, and 18 real ones).  The shipped surface is read either way: an airside vertex's z IS stage 1's, so the stage-1 read at the shipped z equals the read at stage 1's own surface (measured identical at HECA). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate).  **`--probe-site LAT,LON` IS THE STABILITY PROBE** (lane `v2qp`, spec §20c, promoted from lane `v2settle` r2's `scratchpad/v2settle/probe3.py`/`probe4.py` on its second use): off a `--solved-out` pickle, one extra `Band` ceiling `--probe-drop` (default 0.30) metres under the ARM's OWN base surface at the vertex nearest the point, re-solved, and the moved set (> 0.02 m) binned by distance from it — 0-40 / 40-100 / 100-250 / 250-500 / beyond, with the worst beyond 250 m, each arm's hard set and its exit line.  `--probe-arm TERM=V` repeated makes it a MATCHED PAIR of `[design]` arms on ONE problem (`--probe-arm solver=fixed_point --probe-arm solver=qp` is §20c's own bar); with none it probes the shipped law alone.  This is the instrument RULINGS 2026-09-14bw's headline was taken on (HECA: 959 vertices moved by one 0.30 m row, 953 beyond 500 m, ZERO within 100 m).  `--design-weight TERM=V` also takes a NON-NUMERIC value now (§20c's `solver=qp`); a value that does not parse as a float is passed through as the string.  Twin: `tests/auto_patch_v2/test_v2qp.py` (the probe as a fixture pair) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

## Tool: check_grade

| `Ortho4XP/tools/check_grade.py` | You want the grade validator's CLI on one patch, or its library from code. The CLI is a thin front end over the same law reader the census uses. A run with no sidecar is CONTEXT-FREE and overcounts — it is not a defect count. It also prints **THE COCKPIT BLOCK FIRST** (owner RULINGS 2026-09-12x/12y; §31 (6)) — the same `cockpit_block` / `cockpit_block_lines` the harness census and the pytest fixtures call, over the SAME run's `family_out` (the checks' own output is buffered and replayed under the block, never run twice). A `strip_seam_tear` row carries the PAIR MIDPOINT as its lat/lon (spec §32 (3), RULINGS 2026-09-12ag): it used to carry none, and `run_checks` filled it with the offending way's RING CENTROID — at LEMD that sent the cockpit block's first CRITICAL VISUAL find 220 m from the 8.25 m tear. Twinned both sides (`tests/auto_patch_v2/test_v2zoneclamp.py`), the engine's own `verify/strips.strip_seam_tear` alongside. The block's "in view by approach" test is the ONE approach corridor of `auto_patch_v2.law.approach_corridor` (RULINGS 2026-09-12al; twins `tests/auto_patch_v2/test_v2approachcorridor.py`), never a radius around a runway vertex. **`adjacent_ground_step`** (spec §34 (4), lane `v2rampwalk` 2026-09-13) is the WITHIN-FACE welded step on a v2 `adjacent_ground:*` face — the reading no family had: `graded_strip` carries no within-shape cap, `adjacent_ground_tear` fires only under a 1 m edge and `strip_seam_tear` is the CROSS-shape twin, so a band holding its designed level over a mapped road's own ground (LEMD `zone2#2`, 1.73 m over 1.5 m at road −6289) was priced by nothing. Its floor is the cockpit's own `visual_m` AND `cliff_grade` in one step: without the cliff term it counts the lawful hillside drape (measured CYXY 296 rows). Lockstep both sides — `auto_patch_v2.verify.strips.adjacent_ground_step` reads it in the engine; twins `tests/auto_patch_v2/test_v2rampwalk.py` and the v1/v2 census parity test. **`ramp_in_road`** (spec §34 (10), owner RULINGS 2026-09-14bb/14bc/14bd, lane `v2othhramp`) is the CRITICAL presence family the road margin needed: every ramp arriving at a road ends at the road's TRUE edge — the centreline offset by the road's own half-width toward the ramp, ONE derivation `planar/wall_corridor_ramps.road_true_edge` read by every ramp emitter — so a RAMP vertex standing INSIDE a road ribbon is a lane of carriageway cut away, whatever its elevation. No other family sees it: a ramp welded flat into the road it ate breaks no grade law and prices zero rows. A vertex within the census's own weld tolerance of the ribbon's edge is ON the edge, which is what the law asks for. It reads 0 at OTHH before and after — the family is the GUARD on that derivation and never a defect count. Twins: `tests/test_harness.py` §34 (10) (both directions, the weld line both ways, the register and the cockpit class, and the ramp-role set read from the law's own structure roles). **THE RUNWAY SHOULDER'S OWN CAP** (spec §40 (2) as amended, owner RULINGS 2026-09-13dd, lane `v2roles`): a within-shape pair BOTH of whose nodes lie beyond their runway's own half width is priced at `shoulder_transverse_max` (2.5 %, ICAO Annex 14 §3.2.4), not the runway's 1.5 % — a §40 (1) SHOULDER keeps the runway's DATUM, not its cross-fall. The line is the SOLVE's and is read, never re-derived: the sidecar's `runway_axes` (`[ref, lat_a, lon_a, lat_b, lon_b, half_m]` off the apt.dat ends and width) and `shoulder_transverse_max`, through `shoulder_nids` / `_shoulder_cap`. Fitting the width to the runway RINGS instead would read a shoulder as part of the runway and never find its own line. A patch with no key reads exactly as before. One reading with the generator and the v2 verify (`auto_patch_v2.law.tables.runway_transverse_cap`); twins `tests/auto_patch_v2/test_runway_shoulder.py`. |

## Tool: census

| `Ortho4XP/tools/harness/census.py` | You need DEFECT COUNTS from an emitted patch. Every law family always (the register, never a hand list), law-true frame from the patch's own sidecar, airside/groundside/mixed split, worst-N rows, class table, sidecar evidence, JSON + table, A/B across patches. **The only numbers that may be quoted as defect counts.** `--zone-split` additionally buckets the within-shape rows by FAN-RAMP ZONE membership (on a declared ramp piece / inside a zone / crossing one / unrelated, plus the rows already steeper than the zone cap) — reach for it when a grade law grants relief on declared ground and you need to know whether the relief is where the defects are. It is a flag and not its own tool because it needs the census's law-true frame; a private copy of that frame is the census-wrapper defect above. `--magnitude-bands [EDGES]` buckets EVERY law-true row by severity (|de| / step height; default edges `0.01,0.1,1,10` m, or your own ascending list) with the airside/groundside/mixed and adjudicated/version-deferred splits per band — reach for it when the question is which KIND of population a total is, not how big it is (the frame of record is stated in these terms: "0.1-1 m 13,711 = 45.1 %, 1-10 m 11,143 = 36.7 %, 82 % is in-band airside solver residual"). The bands PARTITION the census's own rows and the band below the first edge is the materiality floor's own. Promoted 2026-08-06 from the two lane copies that hand-rolled it (c6attr, c6tip). `--frame own\|base` selects the AXIS FRAME: `own` (default) is the patch's own sidecar and the only frame whose numbers are defect counts; `base` re-reads the SAME patch bytes with the SERVICE axes removed from its sidecar — the axis population a pre-road-feed sidecar carried — which is what splits "the class moved because the surface moved" from "…because the axis frame moved" (cycle 9/10: HECA 10 000 m read airside 4,610 own-frame and 4,474 base-frame, and the whole gap was ONE instrument defect). A base-frame number is a FRAME claim, never a defect count; the frame is stamped into every report either way (`axis_frame`). Added 2026-08-07 (cycle 10) in place of the hand-built filtered sidecars the cycle-10 probe made and threw away. `--rows-json OUT.json` additionally ITEMISES every law-true row — family, role pair, side, magnitude, grade/cap, site in layout-local metres, lat/lon, way ids — which is what turns a class table into an attribution: a net class delta hides equal churn by construction (a class that gains 200 rows at one site and loses 18 at another reads as "+182"), and only the rows say WHICH rows and WHERE. It is the census's own `all_rows`, the same population every count in the report is taken from, so the dump and the counts beside it can never disagree — `tests/test_harness.py` asserts the dump's class tally IS the report's class table, its side split IS the report's, and the worst-N table is its prefix. With several patches you get one dump per patch (a single file would silently keep the last). Added 2026-08-07 (cycle 10) for the road-pair receiver-only round's +182 decomposition. `--sites` clusters those same rows into DEFECT SITES and reports the other headline: how many DISTINCT defects a patch carries (law-true and adjudicated), ROWS PER SITE — the AMPLIFICATION FACTOR — per-site worst |de| / step and worst grade excess, the families, role pairs and shape ids each site spans, its bbox + centroid lat/lon, and a SIM-VISIBILITY flag. Reach for it whenever a row total is about to be quoted as a defect count to a human: row counts AMPLIFY and site counts do not — one over-cap region on one apron mints hundreds of edge-granularity rows (HECA's way -12407 alone carries ~800; the road-feed round's 180 threshold-flip sites live on 19 shapes, 72 % of them on four aprons), so "thousands of defects" is a count of PAIRS THE LAW PRICED and differs from the number of things wrong with the surface by whatever the amplification happens to be on that patch. THE CLUSTERING RULE, printed with every table so a site count is never read without it: two rows join one site iff SAME LAW FAMILY and (shared way id OR shared canonical node), where a canonical node is the census's own weld tolerance (`LAW_TRUE_KNOBS['proximity_m']` = `check_grade.SHARED_VERTEX_TOL_M`, 0.5 m) applied to the rows' endpoints in layout-local metres — the law's own "these two vertices are one node" predicate, never a proximity semantic invented for a report; sites are the connected components (union-find), and no magnitude, role or geometry test takes part. `--site-visibility M` moves the visibility threshold (default 0.05 m of relief = silhouette-visible candidate); it is a REPORTING threshold and an assumption — nothing has measured it in the sim — never a law, and the law still adjudicates every row regardless. `--sites-json OUT.json` dumps every site with its full membership as row indices into the census's own magnitude-sorted order, so it joins a `--rows-json` dump by position. The sites PARTITION the census's own population — `census_one` REFUSES if they do not, and `tests/test_harness.py` §9 carries the known-answer twin (two hand-built sites, one joined by way id and one by weld, asserting count, membership, amplification and both visibility flags) plus the union-equals-`all_rows` lockstep. Added 2026-08-07 (cycle 10) for the owner's "why does the battery still read thousands of defects" question. **THE HEADLINE the section reports is ACTIONABLE SITES** — the MATERIALITY FLOOR (owner RULINGS 2026-08-07, "we don't need to be grading to less than 0.5m") adjudicated per site, since a site is the unit that sentence is about: 40 one-centimetre rows on one apron are one place owing 0.4 m of grading, not 40 defects. A site is actionable when its ADJUDICATED rows accumulate ≥ **0.5 m** of unlawful excess, OR one of them is a single step ≥ **0.15 m** or sits at ≥ **2× its own cap** (the SHARP GUARD — "we don't want any sharp bumps", the half a bare accumulation floor throws away), OR it touches the **RUNWAY FAMILY** (`runway` / `runway_crossing`), which is never floored because reg-derived precision governs there. Every constant is a named knob in `check_grade` (`MATERIALITY_FLOOR_M`, `MATERIALITY_SHARP_STEP_M`, `MATERIALITY_SHARP_GRADE_CAP_MULTIPLE`, `MATERIALITY_RUNWAY_FAMILY_ROLES`) citing the ruling, and all of them ride in every report beside the counts — the floor is PROVISIONAL and two site tables taken at two floors are not comparable. ACCUMULATION is `check_grade.row_excess_m` summed over the site's adjudicated rows only (a version-deferred or out-of-scope row is not a defect and may not fund one): the EXCESS, not the magnitude — a 3.2 m rise over 200 m of 1.5 %-capped taxiway is a 3.2 m magnitude and a 0.2 m excess. A family that prices a CAP rather than metres (`MATERIALITY_UNMEASURED_FAMILIES`, today `lateral_contiguity`, whose `de_m` is a bare grade difference over no span) funds nothing AND keeps its site actionable — a floor may only relax what it can measure. A site the floor takes out is REPORTED under the **`sub_floor`** label with its rows and worst |de| (counted-never-dropped, the `VERSION_DEFERRED_FAMILIES` / `disconnected_ring` convention), and actionable + sub-floor PARTITIONS the adjudicated sites — `census_one` REFUSES if it does not. Twins: `tests/test_harness.py` §10 (both sides of every constant, each guard half proven to fire ALONE, the runway exemption, the label locked to its register, the production refusal). Alongside it, ROLE-LESS FEATURE WAYS SIDE WITH THEIR HOST (lead ruling 2026-08-07): an `o4_feature` way with no `role` tag — `shape_interior_ring` / `gap_interior_ring` / `gap_drainage_spine` / `crown_spine`, 232 of them at HECA — used to fall through to the caller's default 1.5 % cap and to AIRSIDE whatever its host was; `check_grade.resolve_feature_hosts` (shared-node majority, ties on `layout.AUTHORITY_RANK`) and the drainage law's own parent selection now supply the role and side for REPORTING ONLY — the `role` tag is law input and is never written — and a row whose host's vertex set COVERS it is adjudicated `role_less_host_duplicate` (one geometry, one row set), reported under its own heading and never dropped. §10b twins. `--no-cache` / `--clear-cache` govern the CENSUS CACHE: the full report is memoised under `Ortho4XP/tmp/census_cache` (lane-local, gitignored, `$O4_CENSUS_CACHE_DIR`, REFUSED inside the shared data repo, and off inside pytest unless the root is named) keyed by the patch BODY sha (`build_airport.body_sha256`, the `tail -n +3` the frozen MANIFESTs speak) AND the whole-file sha (the census PRINTS the provenance stamp the body hash excludes), the sidecar BYTES (never an enumeration of its law keys — that is the wrapper defect), the run ledger's own code-tree hash (`run_with_ledger.code_tree_hash`, so a `check_grade.py` edit misses), `LAW_TRUE_KNOBS`, the `O4_*` environment and the option frame. A hit re-prints the stored report and re-writes the stored `--json` / `--rows-json` / `--sites-json` bytes, so it is the fresh output plus exactly ONE line — the `[CENSUS CACHE HIT] …` marker, first, immediately before the `=== CENSUS …` header, printed even under `--quiet`; a miss prints nothing. No number, family or law changes: memoisation, not measurement. Twin: `tests/test_census_cache.py`. The census also prints THE BUILD'S OWN AIRSIDE-SCOPED CERTIFICATE beside its counts (air7, RULINGS 2026-09-01l/r): the solve's law-graph verdict on the zero-airside beta bar, read verbatim from the sidecar's `airside_certificate` EVIDENCE key (readings per certificate site + the last-exit verdict; row-side partition, check_grade's quantization allowance imported) — a DIFFERENT instrument over a DIFFERENT population (law edges at exit vs emitted node pairs): agreement is corroboration, disagreement is a finding, and neither replaces the other. Twins: `tests/test_solve_certificate_instrument.py` TASK 6. **THE COCKPIT BLOCK IS PRINTED FIRST** (owner RULINGS 2026-09-12x/12y; `design-surface-spec.md` §31 (6), lane `v2cockpit`): before any other line the census classifies its OWN rows into CRITICAL MOTION (a `step`-class family over `[cockpit] motion_step_m` 0.05 m BETWEEN WELDED NEIGHBOURS — ends no farther apart than `emit.instrument.step_contact_tol_m`, the law's own weld spacing — where BOTH roles are ROLLED-ON — the runway family, the taxi family and the apron, derived from `precedence.toml`, never a literal list — plus the `grade_break` families the runway/taxi rate laws forbid, which carry no span test because a curve is long by definition), CRITICAL VISUAL (a WELDED `step`-class row over `visual_m` 0.5 m inside the airport boundary or within `approach_km` 5 km of a runway axis) and REPORT (everything else: every slope excess, every keep-out row, everything under a threshold, and everything beyond the view — §31 (4), "centimetres are not a goal"), each with its count, worst magnitude and worst COORDINATE. It is a CLASSIFICATION and never a measurement: no row is created, dropped or re-priced, and `cockpit_block` REFUSES if its three buckets do not add up to the population handed in. **THE SPAN RULE** (owner RULINGS 2026-09-12ad, round 2): a step-family row read SPANNED — ends farther apart than the weld spacing — is a SLOPE, not a discontinuity: it is grade, judged by its own cap, and is REPORT.  Round 1 classed a 2.69 m rise over 81 m of LEMD taxiway as critical motion and the block read 452; every one of those rows was spanned and LEMD now reads 0.  The REPORT line names what the rule moved — how many spanned rows would be over the motion threshold and how many over the visual one if they were welded — so the count is never folded into an anonymous total.  **THE CLIFF ESCAPE** (owner RULINGS 2026-09-12af, round 3) bounds it: a spanned row whose implied grade `|dz| / span` exceeds `[cockpit] cliff_grade` is a CUT or a RISE, not ground, and is judged as though it were welded, under its own reason `cliff` (on rolled-on pavement CRITICAL MOTION — no aircraft rolls a 1:3).  LEMD's `strip_seam_tear`, 8.27 m over 3.01 m = 275 %, is the row that made the rule.  The escape restores the BUCKET, never the threshold: a 0.4 m cliff is still under `visual_m` and still invisible.  `cliff_grade` holds a DOTTED LAW PATH (`emit.design.bank_slope`), never a number: the design surface's own 1:3 bank is already the line between "ground a pilot reads" and a wall, and `tables.cliff_grade` resolves it — change the bank and the cliff line follows, with no second copy to drift.  The loader refuses a path that does not name a grade in (0, 1] over the motion threshold.  **ROUND 4** (owner RULINGS 2026-09-12aj) repaired three READER defects the block's own output exposed, all in `check_grade.py`: the three RATE/ARC readers (`strip_arc`, `raoa`, `airside_no_step`'s §1.2 half) built rows with NO lat/lon, so `run_checks`'s fallback stamped each with the CENTROID OF ITS RING — 36 rows of LEMD apron `pav12` printed one coordinate 560 m from the wall they had found, and a whole round of attribution went to the wrong place; every rate row now carries its own pair midpoint (`_rate_row_site`, off a projection that gained an `inverse`). A rate row's `distance_m` published the HALF span `0.5*(dp+dn)` while its `de_m` spans `dp+dn`, so every implied grade read 2x (LEMD's five apron rows printed 0.37-0.46 and are really 0.20-0.23); it is now the full separation, and the allowance keeps the half span because that is the rate law's own averaging term. And the CLIFF ESCAPE now reaches EVERY family, not only `step` ones — LEMD's two sharpest readings of the same wall, a `within_shape` 81 % and a `cross_shape` 240 %, are class `grade` and could not be cliffs at all — while `row_roles` returns THE FACES ON EACH SIDE of the pair rather than the ring it was walked on: a within-shape pair has one ring for both ways, so the pad rim standing over the apron read `building|building` and the rolled-on test called it landside. `run_checks` indexes every node to the SENIOR face carrying it (`precedence.toml` authority order, an identity join on emitted coordinates at millimetre quantisation — never a proximity match) and stamps `role_a`/`role_b`; `row_roles` prefers them. A patch with no `boundary` role way (v2 emits none today) says so and the approach corridor alone decides view. IN VIEW BY APPROACH IS **THE APPROACH CORRIDOR** (owner RULINGS 2026-09-12al, §31 (2)): per runway END, `[cockpit] approach_km` beyond the threshold along the extended centreline and `approach_half_width_m` to each side, derived ONCE in `src/auto_patch_v2/law/approach_corridor.py` and read by the engine's mouth gate (`planar/structure_approach.FieldRegion`, §29 (1)) through the same class — the harness takes its axes from the emitted runway rings, the engine from the apt.dat thresholds. The first reading, "within `approach_km` of a runway axis", admitted the whole airport (at LEMD 4,318 of 4,408 rows, at HECA 8,122 of 37,364 — the corridor leaves 90 and 29,242 of them respectively behind) and is DELETED, not gated. Every family's class lives in `law/families.toml` (`cockpit = step|grade_break|grade|keepout`, REQUIRED — a new family without one does not load) and the four numbers in `law/emit.toml [cockpit]`. Twins: `tests/test_harness.py` §7. **§38 THE TILE SEAM (owner RULINGS 2026-09-13ah / 13am / 13an; lane `v2seampin`)** adds the two families the census had no instrument for. `seam_residual` prices every tile-seam band-edge vertex against ITS OWN tile's baked DEM sample — the value the solve PINNED, published per pin in the sidecar as `seam_pins` = `[lat, lon, dem_z]` (all of them since 13ah; the M3a sidecar published only the subset a soft preference happened to honour). Class `step`, so the cockpit rule gives it CRITICAL MOTION on the rolled-on roles and VISUAL elsewhere with no second threshold. It is the reader the SPLP berm needed: 106 rows, max 3.433 m, 31 of them CRITICAL MOTION on `runway|runway` (worst 0.629 m) — while `strip_seam_tear` read 0 over the same 3 m ridge. `bank_across_seam` prices any `bank_foot` node inside the band (`seam_half_width_m`, also published), class `keepout`: one node is the whole defect, because 13an measured a chain 0.0237 m off the meridian that Triangle4XP split 16,298 times against the unsplittable tile border. The bank foot is ROLE-LESS, so this family reads the `feature_out` channel of `_parse_osm`, not `ways` — a reader that walked `ways` prices nothing. Both are sidecar-declared like `eat_ceiling`: a patch with no key (v1's output, or a v2 patch predating §38) reports nothing and reads exactly as before. This is where the lane's seam-vertex/DEM probe was PROMOTED to (RULINGS `7e90032` second-use rule) — there is no separate script. Twins: `tests/test_harness.py` §38 (both directions of both families, at SPLP's own worst numbers, plus the cockpit classes read out of `families.toml`). |

| `Ortho4XP/tools/census_matrix.py` | You have MANY census JSONs — a multi-airport, multi-world round's arms — and the question is "did any cell's AIRSIDE count RISE against the arm we promised not to regress" (the Q4 gate) and "where did the change land". Lays the arms out as one table (lawtrue / adjudicated / airside / groundside per cell), applies a stated per-cell airside CEILING (`--gate ARM`, default the first census listed, or `--gate-json FILE` for a recorded frame of record), prints the arm-vs-arm delta and, with `--bands`, the census's magnitude bands. **It measures nothing and derives no number** — every value is read verbatim from a `harness/census.py --json` artifact; a reporter that recomputes a defect count is the census-wrapper defect. Equality PASSES the gate ("may not rise"); a cell with no ceiling is reported as ungated, never as a pass. Promoted 2026-08-06 from `tmp/c8fin/mx.py` on its second use (c9feed) — promote-on-reuse; the lane copy hard-coded one round's frame as a module constant. Twin: `tests/test_census_matrix.py`. |

| `Ortho4XP/tools/census_rows_diff.py` | You have TWO `harness/census.py --rows-json` dumps (a control arm and an arm under test) and the question is WHICH rows moved, not how many. A class delta hides equal churn by construction — 200 new and 182 gone read as "+18" — and the zero-new-adjudicated-airside bar is a claim about ROWS, so it needs a row-level reader. Joins the two dumps in three labelled tiers: EXACT (same family / role pair / side, both endpoints identical to the millimetre in the patch's own layout-local metre frame), MOVED (same class, nearest surviving partner within `--tol`, default 0.50 m, each partner used once — an INFERENCE, labelled one everywhere, and quoting two tolerances is how you show the join is not doing the work), and NEW / GONE (no partner — the rows an attribution owes a mechanism for). **It derives no law and measures nothing**: every row is read verbatim out of a census dump, the census staying the only instrument that produces defect counts. REFUSES a join across different `law_true_knobs` or a different axis frame (two dumps read under different law are not one population), a class-level census JSON, and a truncated dump. `--side` / `--family` filter the REPORT, never the join. Twin: `tests/test_census_rows_diff.py` (the four tiers on a hand-built scene, the tolerance knob both ways, class isolation, endpoint-order invariance, partner-used-once, nearest-wins, exact-beats-near, every refusal). |

| `Ortho4XP/tools/pad_span_census.py` | The question is DOES THIS UNIT'S OWN DATUM FIT ITS BODIES' PADS — *how far apart do the emitted `building` pads one FOOTPRINT UNIT stands on actually stand?* — the single number owner RULINGS 2026-09-14c item 1 is accepted or refused on (spec `object-placement-spec.md` §16g (1)/(7)). No other instrument asks it: `harness/census.py` prices PAIRS OF VALUES, so an object seated 23.70 m above its own pad breaks no grade law and reports ZERO rows; `obj8_split_report.py` prints a body's anchor and its own ground but never asks whether the bodies sharing ONE unit's datum stand on pads that disagree; `role_overlap_read.py` is an AREA sweep and `role_edge_census.py` a boundary-length one. This is the unit-vs-pad reading: per unit, the `building` pads its bodies' FEET fall inside, how many bodies it holds, and the SPAN of those pads' planes, largest first. **It measures no law and counts no defects** — the pads are the emitted design surface's own `building` faces at `median(z)` over the ring, which is the plane `footprint_unit` reads through `anchor_rule.pad_plurality`, and the body→part join is the PART ID, never a proximity match (memory `canonical-identity-join`). `--over` (default 1.0 m) is the listing floor 14g stated its bar in, not a threshold with any standing. It takes either `o4_v2_placement_<ICAO>.json` or an `obj8_split_report --json` dump — both carry the same `splits` body records. Measured basis (scout `v2heca331` on the owner's 1.0.331 HECA): 17 units whose pads span > 1 m over 1,363 bodies, `fu:38:20` alone 978 bodies on 136 pads spanning 34.8 m — the unit chained on PART BOXES, and its DECK member then gave 96.20 to 1,509 bodies. Promoted 2026-09-14 from that scout's scratchpad `padspan.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse) — the 14g attribution, then lane `v2connector` round 3's before/after. Several patches are reported separately; quote it on identical options. Twin: `tests/test_pad_span_census.py` (the span IS the unit's own pads, a non-`building` face is not a pad, a unit on one pad is not a row, a body with no `unit_of` is not counted, the floor both ways, the CLI's JSON IS the library result, and this index row). |

| `Ortho4XP/tools/role_edge_census.py` | The question is WHAT SHARES AN EDGE WITH WHAT — *how many metres of a groundside shape's boundary run along AIRSIDE PAVEMENT in an emitted patch* — the single number owner RULINGS 2026-09-12c is accepted or refused on ("shapeID 81 ... cannot be groundside because it shares a long edge with an apron. Something can only be groundside if it has no connection to airside other than a service road"). No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a lot welded flat along 828 m of apron breaks no grade law and reports ZERO rows; `role_overlap_read.py` asks AREA overlap (what STANDS on what), which is 0 for two faces that merely share a boundary; `osm_site.py` answers one coordinate. This is the BOUNDARY-LENGTH sweep: per groundside shape its area, perimeter, inscribed radius (area / perimeter) and the metres shared with airside pavement / with `service_road`+`service_junction` / with `building`, largest first; `--min-m` (§27's `[lot] airside_edge_min_m`, default 10) and `--min-radius` (its sliver floor, default 1.0 m) split the population into SUBSTANTIVE, SLIVER and LOT-class. **It measures no law and counts no defects** — geometry, roles and the groundside partition come from the harness library (`check_grade._parse_osm`, `effective_role`, `_GROUNDSIDE_ROLES`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. Edges are joined on NODE IDENTITY — a shared edge is two shapes listing the same node pair, exactly what the planar weld produces — never a proximity match (memory `canonical-identity-join`). Measured basis (shipped 1.0.320 LEMD): 175 groundside shapes, 105 sharing >= 10 m with airside pavement, 71 substantive (182,604 m², 34 slivers excluded), of which 13 LOT-class / 145,262 m² — the owner's shapeID 81 (`pav137`) 140.2 m of its 270.9 m perimeter, `pav125` 828.4 m. Promoted 2026-09-12 from the `v2lemd320t` scout's `census_gs.py` on its second use (RULINGS `7e90032`). Several patches are reported separately — the arm-to-arm read; quote it on identical options. **`--pad-frontage`** is the SECOND question on the same geometry and the same joins (added 2026-09-12, lane `v2frontage`, spec §28): *pad -> neighbour -> shared edge m -> STEP m*, the read owner RULINGS 2026-09-11ai-1 -> 2026-09-12r ("grade frontages only") is accepted on. No other instrument answers it either: the harness census FORGIVES a declared terrace across a shape joint (`terrace_joints_ll`), so a car park standing 3 m above the terminal it fronts prices ZERO rows — and at LEMD the owner's +3.03 m is not even a declared joint (the patch carries 4, none of them `building4`'s). Per `building` shape: each groundside neighbour (`groundside_pavement` / `service_road` / `service_junction`, `parking_lot` by its class tag), the metres of edge they SHARE by node identity, the facing-vertex pairs within `--near` (default 2.0 m) and the largest and mean SIGNED step, neighbour minus pad. The proximity read is not a shortcut: the pad-frontage relation is a proximity relation in the engine too (`[design] pad_frontage_m` 3.0, owner RULINGS 2026-09-10ax (1)) and `building4` / `pav124` share not one node while standing 0.71-1.50 m apart. `--min-step` (default 0.05 m) is the listing floor. Measured basis (shipped 1.0.321 LEMD): ONE pad with a groundside step >= 0.10 m — `building4`, `pav124` +3.03 / +2.67 and `route6` +0.38. Twin: `tests/test_role_edge_census.py` (the shared edge IS the node-identity join, the airside-pavement set excludes `building`, service-road metres are reported apart, the sliver split, prices-no-law, the pad-frontage step across a proximity gap and across a welded edge, and this index row). |

| `Ortho4XP/tools/void_census.py` | The question is about ENCLAVE TOPOLOGY on a shipped patch: which regions does airside pavement completely surround, which of them have a tunnel/bridge ESCAPE, and what is sitting inside them. Reads back exactly the geometry the enclave region law computes (`auto_patch/enclaves.py`). `--union` selects WHICH union, because the law has two and they answer different questions: `surround` (default) is airside ∪ BUILDINGS, the set published as `layout.airside_enclaves` and the CLASSIFIER's question ("is this ground airside-interior?"); `pavement` is airside pavement only, which is the GAP LAW's own detection union and therefore the scope of the adjacent-ground BAND KEEP-OUT (`enclaves.enclave_band_keepout_union`). The distinction is load-bearing and was measured: buildings standing in HECA's 3.4 km² infield subdivide it into pocket-width components in the `surround` union while the gap law holds it as ONE wide region and declines it on width, so scoping the keep-out by the wrong union deleted 152,734 m² of Annex 14 §3.4.11-13 graded strip. The union is stamped into every report — two unions are two populations. Reports per void its area, perimeter, minimum-rotated-rect SHORT SIDE and POCKET flag (short side ≤ the gap law's own `GAP_FILL_MAX_WIDTH_M`, the class the ruled gap ring + spine treatment covers; under `--union pavement` that flag IS the band keep-out's membership test), the escapes, whether the gap treatment emitted a face there, the per-role/ref contents, the retaining-wall inventory with way ids, and the BARE GROUND remainder carrying no shape at all — the 87.6 % that made the shape-scoped G-ENCLAVE predicate structurally blind. `--bands` adds the ADJACENT-GROUND inventory beside the topology: band and `adjacent_ground_wall` way counts and areas, split by where each way SITS — inside a POCKET no-escape void (the keep-out's own territory), inside another no-escape void, or outside every void — each way in exactly one column, the columns summing to the total. Reach for it whenever a band-area delta is about to be quoted: the total alone cannot tell a keep-out that removed band inside pocket voids from one that also took ground nothing owns, and that is precisely the failure the ratified scoping fixes. **It measures no law and derives no defect count**: grade defects come from `harness/census.py` and nowhere else, and the role vocabulary plus the escape set are IMPORTED from `auto_patch.enclaves` rather than re-typed (the census-wrapper precedent). Parses with the harness library's own reader (`check_grade._parse_osm`) in the builder's anchor frame from the axes sidecar, so this tool and the census read one geometry; without a sidecar the topology is unchanged and lat/lon are simply not reported. FRAME: emitted geometry is post-decimation and post `_separate_groundside_from_airside`, so a void reads slightly larger than the in-build region and a groundside shape inside it reads pulled back from the rim; a real-DEM patch is never comparable with a constant-DEM one. The in-build predicate also honours the `is_bridge` SHAPE FLAG, which `to_osm` does not emit — so this reader sees the four escape ROLES and no more (stated by the tool itself). Promoted 2026-08-07 from `tmp/enclave_attrib/void_census.py` on its second use (promote-on-reuse); the lane copy carried its own patch reader and a hand-typed role list. Twin: `tests/test_void_census.py`. |

| `Ortho4XP/tools/seat_feet_census.py` | THE DRAPE RESIDUAL AT EVERY PLACEMENT'S FEET (RULINGS 2026-09-09ac (3); the placement reading 11e (3), spec §7/§9) — `--placement-plan o4_v2_placement_<ICAO>.json` with `--mesh` (a built mesh) or `--graded` (the emitted design surface, for a dry run with no tile built): per placement of the plan's own rows, `surface(foot) − (surface(anchor) + y_foot)`, the |Δ| histogram (<0.3 / 0.3-1 / 1-3 / >3 m), the same by class, the worst N with lat/lon, and §13's elevated-body / footless-carrier bars. Feet are read from the AUTHORED pack (`.anchor_bak` when one exists). THE SEAT-RESULT MODE IS DELETED (owner RULINGS 2026-09-12s, spec §8) — the name is kept because the INDEX row, `obj8_split_report` and the twins address it by it. Writes nothing to the pack. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. CRITICAL MOTION is named as an instrument limit rather than printed as a zero HERE: §17's motion reading needs the graded face ROLE under each foot, and this tool hands the block none — `obj8_split_report.py` is the entry that takes it (owner RULINGS 2026-09-12am (2), lane `v2objmotion`). §16e (owner RULINGS 2026-09-13k, lane `v2othhdatums`): `--placement-plan --mesh` WAS BROKEN — it passed its bbox as `(lat, lon)` to `MeshElevationSampler`, which takes `(min_lon, min_lat, max_lon, max_lat)`, so at OTHH it asked for a box at lon 25.2 / lat 51.6 and the sampler raised `no mesh triangles inside ... — wrong tile?`; the one place the two orders meet is now `plan_bounds()` and a twin holds it end to end over the sampler's own mesh fixture. The report also prints `§16e bodies on a DATUM` (a crest plate / a deck top) as its own class and EXCLUDES them from §13's `elevated bodies as own files` bar: a datum body's `y_zero` is +5 … +10 m by construction, and counting it there reported the law as the defect (OTHH 0 -> 10 -> 0 with the class printed apart). §16e (3) (Fable 2026-09-13, RULINGS 2026-09-13v, lane `v2bridgecontact`): the report also prints THE BRIDGE FAMILY block (`airport/bridge_family.census_bridges` / `census_bridges_lines`, re-exported through `placement_census`, the same call `obj8_split_report` makes over the same plan shape) — per `Bridge_NN` the deck's own body's world DECK TOP against the land under that bridge's own written geometry (`|deck top - highest land|`, bar `[cockpit] visual_m` 0.5 m), the PER-PLACEMENT zero spread (`max - min` of `surface_z - y_zero` over one placement's bodies; `Bridge_02_CLUTTER_007` is six piers of ONE solid), the CROSS-BRIDGE carriers (a body whose `merged_into` names a file of another bridge, bar 0) and how many bodies publish `bridge_of` and agree with the resource's own tag. The `Bridge_NN` axis is the CENSUS's, never the law's — §16e (3) exists because the name does not name a bridge — so the agreement count is the instrument's own check on the derived relation. Measured on the app's 1.0.326 OTHH frame: `Bridge_01` deck top 3.23 -> 3.96 and `Bridge_04`/`Bridge_05` KEPT -> 3.96 (all three |deck top - land| 0.00, PASS), cross-bridge carriers 2 (unchanged — the bind and the filter are refuted and deleted, see `bridge_family`'s module doc). |

| `census_lockstep.py` | `harness/census.py` (law-true + bare frames, class table) |

## Registered frames: VMMC

VMMC  mesh     base 6bf8ecfb   lane v2hairline       2026-09-13T18:27:49  /tmp/harness/tile_v2hairline_vmmc2/Data+22+113.mesh  — §39 ARM (shore weld ON, vector weld OFF): bank-chain bent chords 8 -> 2 under 0.5 mm (the 2 are water-vs-water), unmeshable 419 -> 119, latent bank:4 CLEAN; residual 0.0025 mm bank/SEA vertex_edge at 22.155210945,113.576646308 (two-witness shore)
VMMC  mesh     base 00d8b05c   lane v2hairline       2026-09-13T21:16:09  /tmp/harness/tile_v2hairline_r2vmmc_iv/Data+22+113.mesh  — §39 round 2 arm: unmeshable 419 -> 50, bent chords 369 -> 164 (worst 0.0124 -> 0.1276 mm, no sea/bank triple), sub-spacing segments 2,271 -> 900; boxes UNCHANGED at 406,393 — the 0.0025 mm bank_foot(0)/SEA(2) pair at 22.155210945,113.576646308 survives the .poly's 9-decimal write

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

