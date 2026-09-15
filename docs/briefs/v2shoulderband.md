# Brief pack — lane `v2shoulderband`

Base: main `ff56c8cf` · generated 2026-09-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

The runway shoulder is a band (§40 (5)): the runway role ends at the strip; every runway vertex carries a level; runway_step

## The brief

Founded on v2lemdstruct2 r5 (RULINGS 15az): the moving "runway" vertices at LEMD are on a §40 (1) shoulder cell reaching 914 m off 14R/32L; only the centreline breakline's 1,421 of 4,033 runway-family vertices carry a level. Sites: `classify/roles.py` (§40 (1)/(4) the shoulder kind — the cut at the strip line), `classify/rules.toml` (`runway_shoulder_shared_m`, the strip half-width by code — find the existing strip table: `[runway] strip_half_width_m` or the §29 (7) lateral band key), `constraints/runway_profile.py` (level rows across the band via `runway_crown`), `verify/census.py` + `tools/check_grade.py` (`runway_step`), `law/families.toml`. The runway's OWN law must hold the runway: no runway-family vertex "held by the objective". STANDING ORDERS: NO `--tile` builds (RULINGS 15av); airport-path builds only; never write the shared data repo; never `--refresh-data`; matched pairs on one tree. Other lanes: v2othhdet (object readers), v2vhhhctl (measurement). Do not touch solve/design*.py, planar/structure_deck.py, planar/structures.py.

## Bars

- The consumer census table (§40 (5) (5)) in the MEASURED block BEFORE the first code edit: every reader of the runway role set / the shoulder kind / `runway_*` families / the strip and lateral band / `ramp_in_strip` / `wall_in_runway_strip` / `ramp_cuts_runway_family` / the profile preserve / the CIFP pins / `airside_edge_flip` — one table, one derivation site chosen.
- LEMD: cell 15 (`runway_shoulder`, 111,648 m², face 5 lateral offsets 30.2/58.1/914.3 m) → the runway-family part within the strip half-width named (m²), the remainder re-roled (which roles, m²); NO runway-family vertex beyond the strip; every runway-family vertex carries a level row (count "held by the objective" → 0); the 0.95 m step at 40.4613609,−3.5446852 gone or named as a `runway_step` DEFECT; the owner's item-7 site 40.4611623,−3.5444804 raw pair still ≤ 1.985 %; `ramp_in_strip` 18 → named (the trench vs the strip re-read).
- VHHH: the 84,000 m² shoulder (14s) → its strip part vs remainder named; HECA: shape 44 (pav73) strip part joins 05L/23R, the rest apron (13co's read); CYXY/SPJC/KCLT/OTHH: every shoulder before → after with its extent (a real shoulder must survive whole).
- `runway_step` in `[verify]` + `LAW_FAMILIES` + families.toml with twins; materiality floor 0.10 m (14bx).
- Census by family, matched replay pairs (one tree, one capture, one variable — registers asserted per arm) at LEMD + HECA + VHHH: no family worse by > 5 % unnamed; `runway_transverse`/`runway_crown` rows before → after.
- Suite by FAILED lines (zero); ONE LEMD build (AIRPORT PATH, no --tile) as the closing test; `shared repo UNCHANGED` quoted.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/classify/roles.py`, `Ortho4XP/src/auto_patch_v2/classify/rules.toml`, `Ortho4XP/src/auto_patch_v2/constraints/runway_profile.py`, `Ortho4XP/tools/check_grade.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/solve/design.py`, `Ortho4XP/src/auto_patch_v2/planar/structures.py`

## Spec (design-surface) §40

## §40 A PAVEMENT ALONG A RUNWAY IS THE RUNWAY'S; APRON EVIDENCE REFUSES THE CORRIDOR KIND (owner RULINGS 2026-09-13co items 1/6; Fable 2026-09-13; RULINGS 2026-09-13cs) — lane `v2roles`

**THE DEFECT (scout `v2heca329`, HECA 1.0.329).**  Shape 44 (`primary_parallel:pav73`,
96,426 m², mean width 101.5 m) shares **585.1 m of boundary with runway
05L/23R's ring** and its source page is 73 % covered by OSM `aeroway=apron`;
`_kind` calls the cell a CORRIDOR because `shared_m` and `width_m` say so and
nothing in `classify/rules.toml` lets apron cover refuse the corridor kind
(`[lot] apron_cover_fraction` is a LOT rung; `[lot] apron_name_tokens` reads the
apt.dat description, which for a DSF page is `asphalt_D3/strips.pol`).  Shape 93
(`secondary_parallel:pav74`, 51,563 m², width 27.8 m, apron cover 13 %) is the
same: the owner reads it as apron, and shape 478 is the zone strip the taxi role
manufactures around it (2,185 m², 614 m shared).

1. **THE RUNWAY SHOULDER.**  A pavement cell whose boundary runs ≥
   `runway_shoulder_shared_m` (100 m) along a runway ring, or whose centroid
   lies within the runway's strip, is not a taxiway of any kind: it is the
   runway's SHOULDER — it joins the runway body (the §29 chord surface and the
   runway's lateral law) and is emitted as part of the runway's datum, never as
   a corridor beside it.  The census names every shoulder with its shared
   length.
2. **APRON EVIDENCE REFUSES THE CORRIDOR.**  OSM `aeroway=apron` cover ≥
   `apron_cover_fraction` over a cell REFUSES the corridor kind (the cell is
   APRON, tier by §19), the same rung that today refuses the lot.  Corridor
   evidence (taxi length, shared edge) does not override apron cover; a
   corridor that is truly a corridor has no apron over it.
3. A cell re-kinded by (1) or (2) manufactures no adjacent-ground zone strips
   (zones exist around taxi-family faces only): shape 478 disappears by
   construction.

BARS (HECA, the 1.0.329 frame dry through `auto_patch_v2 explain --patch …`):
shape 44's cell → runway shoulder of 05L/23R, named; shape 93's cell → apron;
no `graded_strip:adjacent_ground:taxi` face inside or along either; the role
census of the five-airport frames before → after (every re-kinded cell named
with its evidence — a runway shoulder at CYXY/SPJC/KCLT/OTHH must be a real
shoulder); `within_shape` rows on pav73/pav74 before → after; suite twice.

## §40 A PAVEMENT ALONG A RUNWAY IS THE RUNWAY'S; APRON EVIDENCE REFUSES THE CORRIDOR KIND (owner RULINGS 2026-09-13co items 1/6; Fable 2026-09-13; RULINGS 2026-09-13cs) — lane `v2roles`

**THE DEFECT (scout `v2heca329`, HECA 1.0.329).**  Shape 44 (`primary_parallel:pav73`,
96,426 m², mean width 101.5 m) shares **585.1 m of boundary with runway
05L/23R's ring** and its source page is 73 % covered by OSM `aeroway=apron`;
`_kind` calls the cell a CORRIDOR because `shared_m` and `width_m` say so and
nothing in `classify/rules.toml` lets apron cover refuse the corridor kind
(`[lot] apron_cover_fraction` is a LOT rung; `[lot] apron_name_tokens` reads the
apt.dat description, which for a DSF page is `asphalt_D3/strips.pol`).  Shape 93
(`secondary_parallel:pav74`, 51,563 m², width 27.8 m, apron cover 13 %) is the
same: the owner reads it as apron, and shape 478 is the zone strip the taxi role
manufactures around it (2,185 m², 614 m shared).

1. **THE RUNWAY SHOULDER.**  A pavement cell whose boundary runs ≥
   `runway_shoulder_shared_m` (100 m) along a runway ring, or whose centroid
   lies within the runway's strip, is not a taxiway of any kind: it is the
   runway's SHOULDER — it joins the runway body (the §29 chord surface and the
   runway's lateral law) and is emitted as part of the runway's datum, never as
   a corridor beside it.  The census names every shoulder with its shared
   length.
2. **APRON EVIDENCE REFUSES THE CORRIDOR.**  OSM `aeroway=apron` cover ≥
   `apron_cover_fraction` over a cell REFUSES the corridor kind (the cell is
   APRON, tier by §19), the same rung that today refuses the lot.  Corridor
   evidence (taxi length, shared edge) does not override apron cover; a
   corridor that is truly a corridor has no apron over it.
3. A cell re-kinded by (1) or (2) manufactures no adjacent-ground zone strips
   (zones exist around taxi-family faces only): shape 478 disappears by
   construction.

BARS (HECA, the 1.0.329 frame dry through `auto_patch_v2 explain --patch …`):
shape 44's cell → runway shoulder of 05L/23R, named; shape 93's cell → apron;
no `graded_strip:adjacent_ground:taxi` face inside or along either; the role
census of the five-airport frames before → after (every re-kinded cell named
with its evidence — a runway shoulder at CYXY/SPJC/KCLT/OTHH must be a real
shoulder); `within_shape` rows on pav73/pav74 before → after; suite twice.

### §40 AMENDED — THE SHOULDER IS A RIBBON, KEEPS THE RUNWAY'S DATUM, AND TAKES THE SHOULDER'S OWN CROSS-SLOPE (Fable 2026-09-13; RULINGS 2026-09-13dd) — lane `v2roles`

MEASURED (round 1): §40 (1) as written (shared edge ≥ 100 m) swallowed the
field — OTHH runway role 619,131 → 3,832,917 m² (6× the slab), KCLT ×3.2,
HECA ×1.7.  The lane's depth floor (`corridor.runway_shoulder_max_depth_m` =
50.0, mean depth = area / shared length) holds the bar "a cell that really
runs along a runway": shape 44's cell reads 39.6 m; HECA's cell at
30.1098157, 31.4343111 (97.6 m) does not.  §40 (1)'s centroid-in-strip clause
is WITHDRAWN (it would make every parallel inside the 150 m strip a shoulder).
§40 (2) reads the CELL's apron cover, never the source page's (on the page
reading 164 of OTHH's 410 cells refused; per cell 2).

1. A SHOULDER is a ribbon: shared edge ≥ `runway_shoulder_shared_m` AND mean
   depth ≤ `runway_shoulder_max_depth_m`.  It carries role `runway` at the
   runway's ref, code and letter (a distinct role needs `precedence.toml` and
   six `RUNWAY_FAMILY` tuples — owed, not this round).
2. THE SHOULDER KEEPS THE RUNWAY'S DATUM — continuous, no step, across the
   shared edge (the runway's chord surface reaches it) — BUT TAKES THE
   SHOULDER'S OWN CROSS-SLOPE: `[runway] shoulder_transverse_max = 0.025`
   (ICAO Annex 14 §3.2.4: shoulder transverse slope ≤ 2.5 %), priced on
   shoulder vertices beyond the runway's own half-width; the runway's
   1.5 % holds inside its width only.  MEASURED: HECA's two
   `runway_transverse` rows at 1.5287 % / 1.5233 % (108.7 / 204.9 m from the
   ridge, 3.1 / 4.8 cm of excess) are shoulder rows and pass under 2.5 %.
3. Zone strips from NEIGHBOURING taxi faces on a re-kinded cell's ground are
   §41 (2)'s `zone_on_pavement` class (3 at HECA shape 93) — the
   arrangement-to-emit mint, chipped; not §40's.

### §40 (4) A SHOULDER IS PAVEMENT OF THE RUNWAY, NOT THE RUNWAY'S STRIP (Fable 2026-09-14; RULINGS 2026-09-14s) — lane `v2roles`

MEASURED (VHHH 1.0.332): three faces beside 07R/25L re-roled `runway` by §40
(84,000 / 8,040 / 6,228 m²) entered `planar/structures.py`'s strip keep-out
(every `RUNWAY_FAMILY` cell ⊕ 75 m) and `planar/zones.py`'s zone-band
derivation; the big road tunnel at 22.30368, 113.92917 was refused ("the
wall would stand inside the runway strip keep-out") and the basin pass cut a
4,057 m² pit with a closed 7.3 m rim in its place; the shoulders minted
587,849 m² of 75 m zone-2 band.  A 30l consumer-census miss: §40 changed a
role literal and two REGION derivations keyed on it were never ruled.

1. A cell of `kind = "runway_shoulder"` carries the runway's datum, crown
   and lateral law (§40 (2)) and MANUFACTURES NO REGION: it is excluded
   where `strip_u` (the runway strip keep-out) and the zone bands are
   derived; it inherits its host runway's band.
2. Every reader of `RUNWAY_FAMILY` is censused in ONE table (surface
   readers keep the shoulder; region derivations exclude it) before either
   site is edited.

BARS: VHHH the 1.0.332 frame dry (`planar --stage structures`): tunnels
27 → 28 (the `tunnel1_done.obj` tunnel admitted, its 62-node ramp and open
wall back), basins 71 → 70 (`basin:5` gone), `graded_strip` area back to the
old arm's within 5 %; HECA shape 44 still a shoulder with the runway datum
(13dg's bars hold); the `RUNWAY_FAMILY` census table in the spec.

MEASURED — THE `RUNWAY_FAMILY` CONSUMER CENSUS (lane `v2roles`, 2026-09-14;
RULINGS 2026-08-30l).  Every reader of the runway-family role set in
`src/auto_patch_v2/`, by grep, ruled in ONE table before either site was
edited.  A SURFACE reader asks "is this pavement the runway's?" and KEEPS
the shoulder (it carries the runway's datum, crown, lateral law and census
partition, §40 (2)).  A REGION derivation buffers or unions runway cells
into a ZONE OF INFLUENCE off the pavement and EXCLUDES it: a shoulder is
pavement of the runway, and the runway's strip and bands are already drawn
around the runway itself, which the shoulder lies inside.  The predicate is
one helper, `classify.roles.is_runway_shoulder(cell)` (`Cell.kind ==
"runway_shoulder"`); only the three REGION sites call it.

| site | what it derives | class | verdict |
|---|---|---|---|
| `planar/structures.py:293-298` `strip` / `strip_u` | runway cells ⊕ `zone2_half_width_m` (75 m) — the strip keep-out a structure wall may not stand in | REGION | **EXCLUDE** — the VHHH defect: 84,000 + 8,040 + 6,228 m² of shoulder ⊕ 75 m refused `tunnel1_done.obj` at 22.30368, 113.92917 |
| `planar/zones.py:96-99` zone-band `groups` | the adjacent-ground band sources, by family and code | REGION | **EXCLUDE** — the shoulders minted 587,849 m² of 75 m zone-2 band at VHHH, against `rules.toml`'s own "a shoulder manufactures no zone strip" |
| `planar/shapes.py:138-150` `strip_keepout` | each runway cell's long axis + end-skirt corridor ⊕ the strip half width — where a joint is never declared | REGION | **EXCLUDE** — same shape of error, found by this census and not by the VHHH read: a 84,000 m² shoulder has a long axis of its own |
| `constraints/strips.py` `runway_groups` | the strip footprint (axis, width, rings) | REGION | already EXCLUDED by construction (§40 (1), round 1): reads `Runway.slab_corners`, the apt.dat ends and width, never the role's rings |
| `planar/structures.py:277-278` `runway_u` | what a structure ramp may NOT cross | surface | KEEP — a ramp crossing a shoulder cuts the runway's own pavement |
| `planar/structures.py:287` `stops` (door ramp) | the governed cells a door ramp stops at, runway family excepted | surface | KEEP |
| `planar/structures.py:290` → `planar/wall_corridor_ramps.py:109-114` `airside_stops` | the airside cells a wall-corridor ramp stops at | surface | KEEP |
| `planar/structures.py:858` | cells the object knife never cuts | surface | KEEP — the runway's pavement is not cut by an object |
| `planar/basins.py:526-527` `runway_u`, `:794` | what a basin never cuts (`cuts_runway_family`) | surface | KEEP |
| `planar/shapes.py:218-226` network roots | the runway-connected face network | surface | KEEP — a shoulder is reachable pavement |
| `constraints/runway_profile.py` `crown_drops`, `runway_crown`, `runway_transverse` | the datum, crown floor and transverse law per vertex | surface | KEEP (§40 (2): the crown stops at the runway edge, the cap becomes the shoulder's) |
| `constraints/runway_chord.py:559` `faces_of_role(RUNWAY_FAMILY)` | the §29 chord target | surface | KEEP — this is §40 (1)'s whole point |
| `constraints/zones.py:198-206` `face_of_edge` | which runway face an edge's band belongs to | surface | KEEP — the shoulder's `ref` IS its host runway's, so it inherits that runway's band |
| `constraints/zones.py:96-99`, `:326-331` | family of a band edge; the tie population's runway exclusion | surface | KEEP |
| `constraints/eat.py:280`, `apron_trend.py:170`, `taxi_trend.py:115`, `flat_site.py:80` | role-set membership for the EAT rects, the trend terms and the flat-site datum | surface | KEEP |
| `solve/project.py:158-161` `runway_family_vertices`, `solve/design.py:188` | the projection's runway vertex set | surface | KEEP |
| `verify/runway.py`, `verify/strips.py`, `verify/structures.py`, `tools/check_grade.py` | the census readings | surface | KEEP (the shoulder is priced at its own cap, §40 (2)) |
| `law/tables.py` `role_family` / `role_words` / `precedence` | the role register | surface | KEEP |

### §40 (1) AMENDED — A SHOULDER DOES NOT ENCLOSE THE RUNWAY (Fable 2026-09-14; RULINGS 2026-09-14bh) — lane `v2roles`

MEASURED (LERM, the +40-004 tile abort): the aerodrome's single open
pavement page (65,655 m², fronting seven hangars) shared 2,135 m of a
2,135 m runway ring — it ENCLOSED the runway — passed the 100 m shared floor
and the 50 m depth cap, took the runway datum while its ground falls 7.5 %,
and minted 43 `runway_transverse` DEFECT rows at the shoulder cap.  New
rung `corridor.runway_shoulder_max_wrap` (0.75): the shared boundary is at
most that fraction of the runway slab's own perimeter — a shoulder runs
ALONG a runway, it does not wrap one.  Separation measured over every
shoulder cell: HECA 0.01–0.54, VHHH 0.01–0.55, LERM's false shoulder 1.00
(runners-up recorded: area ratio ≤ 0.88 vs 1.09; pads touching 0 vs 7).
`shoulder_wrap` and `shoulder_depth_m` ride in the cell evidence.

## §40 (5) A SHOULDER IS A BAND, NOT A CELL — THE RUNWAY ROLE ENDS AT THE STRIP (Fable 2026-09-15; RULINGS 2026-09-15az; lane v2lemdstruct2 r5 measurement) — consumer census first, then the cut

**The reading (LEMD, r5).**  Cell 15, `kind = runway_shoulder`, **111,648
m²**, code 4/F, admitted under §40 (1) with the runway's role, ref and
code: face 5 has 306 nodes with lateral offsets **30.2 / 58.1 / 914.3 m**
(min / median / max) from 14R/32L's centreline — 276 of 306 beyond the
30.5 m half-width — while the runway's own faces 0 and 7 stay ≤ 31.0 m.
`runway_profile` + the threshold pins give a LEVEL to 1,421 of 4,033
"runway-family" vertices (the centreline breakline, perfect: one chain,
365 vertices, moved ≤ 0.059 m); the rest are held by the objective and,
until r4, by two `LEMD69.obj` sign plinths (dual 48,669).  `runway_
crown` / `runway_transverse` are minted over the cell but price a crown
across 30.5 m; 490 m off-axis they bound nothing, so a **0.95 m step
between two faces of one "runway" role** escapes every DEFECT family.
The owner's VHHH read (14s: an 84,000 m² shoulder) is the same class.

**RULED.**  (1) A runway shoulder is a BAND: pavement carrying the
runway's ref is runway-family only within the runway's graded strip
half-width from the centreline (`[runway] strip_half_width_m` by code —
ICAO code 3/4: 75 m in the existing law tables; the shoulder itself
the code's shoulder width beyond the runway edge).  (2) Pavement with
the runway's ref BEYOND the strip is NOT runway family: the classifier
gives it the role its geometry earns (junction / taxiway / apron by the
existing scorer) and the runway's ref is dropped from it — it welds to
the runway family at the strip line like any airside contact (§37
(10)).  (3) Within the band, every runway-family vertex carries a
LEVEL: the profile/threshold rows extend from the centreline breakline
across the band by the crown law (`runway_crown`), so no runway-family
vertex is ever "held by the objective".  (4) A step between two faces
of the runway family of more than the runway's transverse cap over the
edge length is a DEFECT: family `runway_step` in `[verify]`, materiality
per §… the 0.10 m floor.  (5) Consumer census FIRST (owner 2026-08-30l):
every reader of the runway role set, the shoulder kind, `runway_*`
families, the runway strip / lateral band (§29 (7)), `ramp_in_strip`,
`wall_in_runway_strip`, `ramp_cuts_runway_family`, the profile
preserve, the CIFP pins — one table before the cut; the cut at the
single derivation site in `classify/roles` beside §40 (1)/(4).
Expected at LEMD: face 5 shrinks to the band; the ex-shoulder ground
takes junction/apron roles with their own transverse caps (the owner's
item-7 site then reads under the junction law it already meets, 1.542
%); the 0.95 m step is either healed by the level rows or named as a
`runway_step` DEFECT; VHHH's 84,000 m² shoulder shrinks likewise.
(5) bounds (1), it does not reverse it: a cell that shares ≥ 100 m with
the runway ring or has its centroid in the strip is STILL the runway's
— but only the part of it within the strip half-width; the remainder
beyond the strip keeps the role its geometry earns (HECA shape 44, 101.5
m wide: the strip part joins 05L/23R, the rest is the apron the owner
read it as — 13co).  Owner ruling 13co's intent ("a pavement along a
runway is the runway's") is exactly a band beside the runway.

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

## Spec (design-surface) §34 (13)

## §34 (13) A STRUCTURE RAMP IS GRADED ALONG ITS AXIS; THE COVERED EXTENT READS EVERY AIRSIDE STRIP THE CROSSING LIES IN (Fable 2026-09-15; RULINGS 2026-09-15u; answers lane v2lemdstruct2's two questions) — lane `v2lemdstruct2` r2

(1) **`tunnel_ramp` is a ROUTE-family shape.**  Its grade is read along
its AXIS (mouth → top, the §34 (7) stations), as §37 (7) reads the road
family and 09-05aa the taxi family — never across the plan chord.  The
item-5 ramp's worst `within_shape` row today is 8.250 m / 8.31 % over a
99.25 m PLAN CHORD where the axis is 143.5 m (5.75 %); the +63
`within_shape` rows the §33 (5) fix priced are that misreading.  The
ramp's own cap is the ramp grade cap; a chord row on a `tunnel_ramp` is
not minted.

(2) **The covered extent reads EVERY airside strip the crossing lies in.**
§34 (5) (b) clears the strip of the way the bore passes UNDER; at LEMD
item 7 the underpass passes under junction pav157 and the trench then
surfaces inside runway 14R/32L's 75 m strip (8 `ramp_in_strip` rows
against the runway; `strip_transverse [runway|tunnel_ramp]` 13.87 m).
RULED: the mouth opens beyond the OUTERMOST airside strip at that
station — runway strips included (§29 (7) the runway lateral band is
airside ground) — and the ramp descends outside it.  If the ramp that
results exceeds its grade cap within `max_ramp_length_m`, the ramp cap
decides and the residual is named; the strip is never cut.
`wall_in_runway_strip` / §29 (7) keep their own reading of walls.

(3) **The junction's crossfall at a runway contact.**  No `transverse`
row exists at pav157's nodes shared with the runway; the crossfall is
priced only by `taxi_box` / `airside_no_step` junction|runway pairs and
reads 4.957 % over 18.2 m (cap 1.985 / 1.500 %); after the trench move
4.296 / 2.479 %.  A junction touching a runway takes the runway's edge
level at the contact (airside is king) and carries its OWN transverse
cap across its width: the lane names the rows that pull pav157's far
edge down (the trench rim? the zone? the bored road's deck?) with
`--why-at` before the fix — a transverse row set on the junction is the
expected remedy, the measurement decides.

(4) **§34 (11) (a) road admission — the consumer census is the first
deliverable of r2**, then the admission: OSM way −5944 (`highway=
service`, `lanes=2`, 0.14 m from the owner's point) is kept out by
`classify/evidence._osm_roads` (centrelines ∩ `pavement_union`) and
`classify/roles` (faces only from `ev.truck_chains`).  The "pull" as
stated is REFUTED (vertices within 60 m at DEM +0.03 mean, worst +1.41 m
ABOVE); what the owner sees is the DEM's own 611 m × 88.7 m plateau
between two rims solving at 602.16 / 601.69 — an unowned 9 m cut in the
witness.  The road, admitted, grades that ground (§37 (6) its zones);
the 144,429 m² hole ring (cover 0.011) is closed by the road's faces and
zones or excluded per §34 (11) (c).

### §34 (13) **MEASURED — r2** (lane `v2lemdstruct2`, branch `claude/v2lemdstruct2`, base main `9c313551`)

THE FRAME is r1's: the ONE registered LEMD capture (`LEMD capture base
da8e5d7f lane v2lemdstruct2`), matched `v2_solve_replay` arms off it, the
harness census on each `--emit`.  **NO CLOSING BUILD** — the shared repo's
`osm_layers` refresh RULINGS 15u calls for has not been run (the refresh
ledger's last `osm_layers` entry is 2026-09-08T11:33:30, for SPJC), so
this round stops at the replay pair exactly as instructed.

#### (1) A STRUCTURE RAMP IS GRADED ALONG ITS AXIS — MET

ONE derivation, `auto_patch_v2.verify.within.ring_route_m`: the ROUTE
between two vertices of a closed ring is the shorter of the two walks
around it.  A `tunnel_ramp` face is a RIBBON (`planar/structure_geometry.
geometry` walks the axis stations down one side and back up the other),
so for two vertices on the same side that walk IS the run between their
stations, and for two across the ribbon it is the short way round the
nearer end — no sidecar key needed, unlike the taxi route
(`taxi_route_pairs`) and the road frame (`road_route_frame`).  It reads
`max(chord, route)` and a polyline between two of its own points is never
shorter than the chord, so it can only RELAX and never blinds a ramp that
is genuinely over cap along its axis.  Two readers, one function: the v2
verify (`verify/within.within_shape`) and `tools/check_grade`
(`_ring_route_m`, imported, with a literal no-engine fallback the twin
asserts identity against).

| bar | before | §34 (13) (1) |
|---|---|---|
| census `within_shape` rows touching a `tunnel_ramp` | **71** | **27** |
| the item-5 ramp's worst row (way −10852/−10853) | **10.41 m / 10.49 % over a 99.3 m PLAN CHORD** | **3.87 m / 8.29 % over a 46.7 m AXIS run** |
| census `within_shape`, airport-wide | 3,464 | **3,420** |
| the same on the BASE arm | 3,397 | **3,391** |
| §33 (5)'s price, re-read | +67 rows | **+29** |
| census ADJUDICATED | 1,404 | **1,360** |

**RESIDUAL, NAMED.**  27 ramp rows survive, worst **8.29 % against the
8.0 % cap** — the item-5 ramp is 0.29 pp over its own cap along its own
axis over a 46.7 m run, which is a real grade and not an artefact.  The
ruling's own alternative ("or is named") is what this is.

#### (2) THE COVERED EXTENT READS EVERY AIRSIDE STRIP — ATTEMPTED, MOVED BACKWARDS, DELETED

Built as ruled: `airside_strip_union` (every runway- and taxi-family cell
grown by `strip_half_width_m`, the zone law's own number) and, per station
per side, `_strip_exit_m` — the last point along the normal still inside
any airside strip — as the floor under §34 (5) (b)'s kerb+strip offset.
ONE full planar replay arm (`b1`).  **Every bar moved the wrong way:**

| | §34 (5) (b) (r1) | §34 (13) (2) attempt |
|---|---|---|
| `ramp_in_strip` (bar: 8 → **0**) | 8 | **19** |
| `strip_transverse`, worst | 83, 13.872 m | **90, 19.070 m** |
| v2 verify `wall_in_runway_strip` | 6 | **20** |
| cockpit CRITICAL visual CLIFFS | 10 | **24** |
| census ADJUDICATED | 1,360 | 1,372 |
| the trench mouth from the owner's node | 31.06 / 33.43 m | 41.67 / 43.25 m |
| solve | optimal | optimal |

**THE MECHANISM, AND WHY A SECOND ATTEMPT IS NOT WORTH ITS BUILD.**  At
LEMD F-6 the crossing stands 33–43 m from runway 14R/32L, whose code-4
strip is **75 m**.  "The mouth opens beyond the outermost airside strip"
therefore asks for a covered extent of roughly **150 m** and a ramp that
descends from `mouth_z` 564.90 below a taxi surface at 581 over that run —
a different structure, not a longer clip.  What the clip's 10 m of extra
reach actually bought was a DEEPER trench slightly FURTHER into the same
strip, plus a wider ribbon that bored more road and put fresh ramps into
OTHER runway strips (the new worst `ramp_in_strip` row is at
40.4633057,−3.5451343, a site the reading never touched before).  §34 (13)
(2)'s own escape clause is the answer: *"If the ramp that results exceeds
its grade cap within `max_ramp_length_m`, the ramp cap decides and the
residual is named; the strip is never cut."*  `max_ramp_length_m` is 600 m
and `ramp_max_grade` 0.08, so the ramp CAN be built — but the strip is not
being cut by the ramp, it is being cut by the TRENCH the bore needs, and
the bore's length is what the deck cell states.  The code is DELETED per
the standing law (a bar that moves backwards is not kept gated); the
measurement is this table.  **The residual stands: 8 `ramp_in_strip` rows
and `strip_transverse [runway|tunnel_ramp]` 13.872 m over 32.49 m against
runway 14R/32L's strip, at LEMD 40.4605950,−3.5447694.**

#### (3) THE JUNCTION'S CROSSFALL AT A RUNWAY CONTACT — THE ROWS ARE NAMED, AND THE PREMISE INVERTS

`--why-vertex` on the two vertices the census pair is made of (the r1
solved arm), at the owner's own point:

* **v906** (40.4611623,−3.5444804, the owner's point, shared
  `junction#86` + `runway#5`) z **579.08**, DEM 572.03 — **7.05 m of
  fill**.  Binding: `no_step_pairs` 4 (dual 3,197), `junction_mesh` 7
  (2,584), `runway_profile` 1 (585), `taxi_centreline` 1 (585),
  **`transverse` 1 (141), a 4-term row AT ITS BOUND +0.2241**.  Chain:
  v906 → v6621 (**+2.31 m**, `junction_mesh` at **cap 1.50 % × 43.2 m**)
  → v6719 `graded_strip#95` z 577.63, terminal **FREE — "held by its
  ground datum (the DEM under it)"**.
* **v6622** (18.12 m away, `graded_strip#94` + `junction#86`, NOT shared
  with the runway) z **579.86** — the junction's far edge.  Binding:
  **`foot_rows` 14 (dual 42,656 — an order of magnitude above everything
  else)**, `no_step_pairs` 6 (4,565), `junction_mesh` 7 (1,870),
  **`transverse` 6 (900), 4-term rows AT THEIR BOUND −0.2438**,
  `taxi_box` 2, `taxi_chain` 1, `zone_bands` 4.

**THE PREMISE INVERTS.**  The brief and the ruling ask for "the rows that
pull pav157's far edge DOWN".  The far edge is **0.78 m ABOVE** the
runway contact, not below: 579.86 against 579.08.  Nothing pulls it down;
the runway edge is held 7.05 m over its own DEM by the junction mesh
stretched at cap across 43.2 m to a zone-band vertex sitting on the DEM,
and the object **FOOT ROWS** are the heaviest thing in the sheet at the
far edge.

**AND THE `transverse` ROWS EXIST AND ARE AT CAP.**  r1 reported "no
transverse row" from the CENSUS's family view, and that is true of the
census — zero `transverse` rows within 120 m — but the SOLVE has seven of
them there, every one binding at its bound (±0.24 m over 18.1 m =
**1.35 %**, inside the 1.5 % cap).  They are 4-TERM rows: a vertex against
an INTERPOLATED point across the corridor, not the raw pair.  The census
prices the raw pair v906–v6622 at **0.78 m / 18.12 m = 4.30 %**.  So the
two instruments disagree about what "the crossfall" IS, and the remedy the
ruling expects — "a transverse row set on the junction" — is already
there and already satisfied.  **A NEW ROW SET IS NOT THE FIX AND WAS NOT
ATTEMPTED**: what wants Fable's reading is whether a junction's transverse
law is the 4-term cross-corridor row (satisfied) or the pair across its
width (4.30 %, three times the cap).  Measured both ways, above.

#### (4) §34 (11) (a) ROAD ADMISSION — THE CONSUMER CENSUS, AND THE EDIT IT REFUSES

The census (owner RULINGS 2026-08-30l) was completed BEFORE any consumer
was edited, and it is the deliverable: **the admission as specified is not
a bounded change and was NOT landed.**

**THE TABLE** (scout `v2lemdstruct2-census`, read-only, on the registered
capture; `service_road` is `value=true`, `side="groundside"` in
`law/precedence.toml`).  Verdicts: UNAFFECTED / CHANGED-report-only /
NEEDS-A-RULE / HAZARD.

| # | consumer | what it reads | effect of a new `service_road` face population | verdict |
|---|---|---|---|---|
| 1 | `classify/evidence._osm_roads` | centreline ∩ `pavement_union`, `rules.osm_roads` (`highways=["service"]`, `dedup_m` 8, `min_len_m` 10) | the gate itself; widening CHAINS is a different blast radius from minting FACES | NEEDS-A-RULE |
| 2 | `classify/roles` corridor mint | `ev.truck_chains` − pavement/pad/runway, `service.road_width_m` 6.0 | the change site | — |
| 3 | `classify/roles._road_evidence` | `truck_chains + road_chains` vs `scored` | corridor faces are appended AFTER `scored`, so FACES do not reach it; widened CHAINS do → more `parking_lot` demotions and open-default flips | HAZARD if chains widen |
| 4 | `classify/roles` road CUT LINES in strips | `truck_chains + road_chains` ∩ strip sources | widened chains mint breaklines INSIDE senior strips | NEEDS-A-RULE |
| 5 | `classify/sources` | `ev.road_chains` → `osm_road_m` / `aisle_m` | the whole lot ladder (`lot.min_road_fraction`, `narrow_road_width_m`, §37 (5)) — role churn on EXISTING pages | HAZARD if chains widen |
| 6 | `classify/airside_edge.airside_edge_flip` | roles, `lot.road_airside_edge_frac` | every new face is a §27 candidate and can FLIP to `apron`; flips propagate to fixpoint. **9 of 46 candidate faces (5,016 m²) lie mostly inside a 75 m runway strip** | **HAZARD** |
| 7 | `planar/build.build` | `classification.cells` | +46…+207 faces on a 1,024-face / 20,608-vertex map | CHANGED-report-only |
| 8 | `planar/weld.weld_cells` | value, non-rigid roles | `service_road` is a VALUE role → new faces weld into neighbours and MOVE their vertices | NEEDS-A-RULE |
| 9 | `planar/shapes._label_roads` / `network_faces` / `strip_keepout` | road-family faces | each new face is labelled ALONG or CROSSING → new declared `road_ramp`s with their own row law | NEEDS-A-RULE |
| 10 | `planar/zones.zone_regions` | `side == "groundside"` cells ⊕ `groundside_cutback_m` 0.6 + snap 0.354 | **9,229 m² of 3,036,527 m² zone-band area removed = 0.30 %, on 10 of 279 `graded_strip` faces** | CHANGED-report-only |
| 11 | `planar/terrain_edge.road_lines` | `airport.osm_ways` DIRECTLY | already sees every mapped road | UNAFFECTED |
| 12 | `constraints/roads.road_law_caps` / `road_within_shape` | `family("road_cross_section").roles` | the full cross-section pair law on every new face; lateral contiguity hands the 9 strip-interior faces a RUNWAY-grade transverse cap | **HAZARD** |
| 13 | §37 (1) longitudinal (`role_cap("service_road")`) | the role cap | unchanged (8 %); row count grows | CHANGED-report-only |
| 14 | `constraints/road_ramp` §37 (6)/(7)/(9)/(10) | the road frame | new ramp / contact / join rows | CHANGED-report-only |
| 15 | `airport/road_ramp.deck_refs` / `road_ramp_targets` | `pm.structures[*].decks` refs | `deck_refs` excludes only MAPPED BRIDGE DECKS. A face minted over a `tunnel=yes` way has NO structure record, is NOT excluded, and §37 (6) grades it to the surface **OVER A BORE**. Three such ways sit in the owner's void (−15327, −5980, −5931) | **HAZARD** |
| 16 | `airport/road_profile.core_profiles` / `preferred_road_z` | ALL `osm_ways` with `highway` | population already complete — **way −5944 is ALREADY in the core profile**, so §37 (6) answers a face over it with no new plumbing | UNAFFECTED |
| 17 | `emit/osm_adapter` | `precedence.roles[role]`, `ref` | would reuse the 1206 corridors' own `route{i}` namespace — the census could not separate the two populations | NEEDS-A-RULE |
| 18 | `tools/check_grade` `_ROAD_FAMILY_ROLES`, `road_cross_section`, `ramp_in_road`, `road_coverage_join`, `zone_on_pavement` | `law_role(way)` | all four price the new faces automatically; counts rise on every one | CHANGED-report-only |
| 19 | `verify/roads.road_profile_agreement` | faces owning a preferred vertex | whole-population mean/max move | CHANGED-report-only |
| 20 | `verify/steps`, `constraints/proximity`, `constraints/groundside`, `solve/design` §9 | `role_side == "groundside"` | every new corridor rim is a fresh airside/groundside boundary → more step / proximity pairs | CHANGED-report-only |
| 21 | `constraints/zones` `own_law` | `road_family_roles` | new rim vertices leave the zone-band constraint | CHANGED-report-only |
| 22 | `constraints/transverse`, `contiguity`, `verify/contiguity`, `pipeline/shapes` | `road_family_roles` | mechanical, role-keyed | UNAFFECTED |
| 23 | `verify/structures.tunnel_deck_clearance` | the `("service_road","tunnel_ramp")` pair | would catch #15 only where a `tunnel_ramp` exists | NEEDS-A-RULE |
| 24 | `src/auto_patch/*` (v1) | v1 role sets | not on the v2 pipeline | UNAFFECTED |

**THE POPULATION, MEASURED THREE WAYS** (the capture; `airport.osm_ways`
are the whole TILE's road net, which is the trap):

| scope | faces | area |
|---|---|---|
| every off-pavement `highway=service` part, no gate | **618** | **1,857,973 m²** |
| clipped to the apt.dat boundary ⊕ 50 m, `tunnel`/`bridge` refused (57 ways), the runway strip cut | **207** | **944,872 m²** |
| the same without the runway-strip cut | 199 | 977,182 m² |
| (scout's independent count, clipped to the PATCH COVERAGE) | 46 | 21,038 m² |

LEMD's whole patch coverage is 12,189,226 m².  **The narrowest gate I
could derive at classify time still admits 944,872 m² — 7.8 % of the
layout — to fix one 297.9 m road.**  A third scope was tried and measured
too: roads inside the ENCLOSED VOIDS of the airside union (the shape
§34 (11) (c) names) — 52 voids ≥ 10,000 m², but the largest is
**4,816,431 m²** (the airfield's own middle, not a void), and the class
reads **137 road parts / 42,113 m**.  None of the three isolates the
defect.

**THE VOID ITSELF** is not −5944's alone: it is a hole in
`graded_strip:adjacent_ground:taxi:F:zone2#18`, **144,254 m²**,
representative point **40.4946503,−3.5835473** (the owner's, exactly), and
**fourteen** `highway` ways lie in it — ten with no chain today (−5944
297.9 m, −5913 263.9 m, −5958 244.0 m, −5962 126.6 m, −15328/29/30/31/32/33
~30 m each) and three of the remaining four are the **bores themselves**
(−15327, −5980, −5931).  Closing it takes a **10-way, ~1,030 m road
network**, not one way.

**WHAT THIS LANE DID.**  The admission was BUILT to the census's own
scope — faces only (never widening `ev.road_chains`), `tunnel`/`bridge`
ways refused, the runway strip cut, its own `osmroad<n>` ref namespace,
clipped to the apt.dat boundary — and then **REVERTED**: 207 faces /
944,872 m² is two orders of magnitude past the owner's one road, and it
cannot be measured this round at all (a classify-stage change is invisible
to a `--from planar` replay — the capture holds the classification — so it
needs a fresh capture AND a build, and the build is barred until the
`osm_layers` refresh).  This is a STOP-and-report under the attempt cap.

**THE BOUNDED SUCCESSOR, NAMED.**  §34 (11)'s own words are "THE ROAD
BETWEEN TWO MOUTHS", and that predicate is available — at the PLANAR
stage, not at classify: two mouths of the SAME bored road facing each
other across a gap (LEMD `tunnel:-15327@0` at 40.4947815,−3.5829176 and
`tunnel:-5980@0` at 40.4940096,−3.5826576, **88.7 m** apart, the parent
road already walked by `structure_approach.approach_along`).  That mints
ONE face at LEMD instead of 207, needs no boundary heuristic, and cannot
touch a runway strip or a bore because the structures stage already knows
where both are.  It is a new emitted class (classify → planar → emit) and
wants its own round.

**AND THE ROAD-TAG QUESTION IS ANSWERED: NO.**  `+40-004_big_roads.osm.bz2`
(the file r1's build rewrote) does now carry the v2roadtags keys —
`layer` 2,420, `covered` 250, `embankment` 68, `cutting` 16 — but it holds
**zero ways within 600 m of the site**.  All 22 ways there come from
`+40-004_airport_small_roads.osm.bz2`, dated **Aug 31 and NOT rewritten**,
and carry only `highway` / `lanes` / `bridge` / `tunnel` / `width`.  Across
all 6,620 loaded `highway` ways the capture has **no `layer` tag at all**,
and `airport/osm.TAGS_OF_INTEREST` keeps `layer` but DROPS `covered`,
`cutting` and `embankment`, so even a rewritten small-roads feed would
need that frozenset widened first.  The new tags cannot identify −5944's
relationship to the two bores.

#### THE CLOSING ARM — NO BUILD, AND WHY

The shipping arm is `b2`: one `--from planar` replay of the registered
capture on the r2 tree, solve **optimal** 54.5 s.  Its surface is
BYTE-EQUAL to r1's at both owner sites (item 5 rim −10995 602.16 / ramp
−10852 floor **597.09** = **5.07 m**; item 7 rim at **31.06 m**, ramp at
**33.43 m**, floor 564.90), because §34 (13) (1) changes only how the
surface is READ.  The two instruments agree exactly on how many rows the
plan chord was inventing:

| | r1 | r2 (§34 (13) (1)) |
|---|---|---|
| v2 verify `within_shape` | 466 | **422** (−44) |
| census `within_shape` | 3,464 | **3,420** (−44) |
| census LAW-TRUE / ADJUDICATED | 5,756 / 1,404 | **5,712 / 1,360** |
| `ramp_in_strip` / `strip_transverse` worst | 8 / 13.872 m | 8 / 13.872 m (unchanged — (2) deleted) |
| v2 verify `tunnel_mouth_canonical` / `wall_in_runway_strip` | 28 / 6 | 28 / 6 |
| cockpit CRITICAL motion / visual (cliffs) | 4 / 1,433 (10) | 4 / 1,433 (10) |

**NO CLOSING BUILD WAS RUN.**  RULINGS 15u's owner act — `build_airport.py
LEMD --refresh-data osm_layers` — has not happened: the refresh ledger
`/Users/noah/XPTerrainBuilderData/.harness/refresh_ledger.jsonl` ends at
**2026-09-08T11:33:30** (scope `osm_layers`, for SPJC), with nothing from
2026-09-15.  Building LEMD now would measure the same mixed corpus r1's
build contaminated, so this round stops at the replay pair, as instructed.
Suite `tests/auto_patch_v2 tests/test_harness.py`: **1,591 passed / 1
skipped / 0 FAILED**.

## §34 (13) MEASURED AND AMENDED (lane v2lemdstruct2 r2 1846bb15; Fable 2026-09-15; RULINGS 2026-09-15y) — (1) landed; (2) WITHDRAWN; (3) the raw pair IS the junction's transverse law; (4) the road between two mouths is minted at the planar stage

**(1) LANDED.**  `verify/within.ring_route_m` — a ramp ribbon's ring IS
its axis down one side and back; `within_shape` reads `max(chord,
route)`, so it can only relax.  Ramp rows 71 → 27; the item-5 ramp 10.49
% over a 99.3 m chord → 8.29 % over a 46.7 m axis run; verify and
census both lose exactly 44 rows.  Residual: 27 rows, worst 8.29 %
against the 8.0 % cap — named, under the 0.5 pp attempt floor of
interest.

**(2) WITHDRAWN.**  "Beyond the outermost strip" at item 7 asks for a
~150 m covered extent (the crossing stands 33–43 m from 14R/32L, whose
strip is 75 m) — a different structure; the attempt moved backwards
(`ramp_in_strip` 8 → 19, `strip_transverse` 13.87 → 19.07 m, cliffs 10
→ 24) and was deleted.  The residual STANDS and is the owner's to see:
8 `ramp_in_strip` rows, the trench 13.87 m deep over 32.49 m at
40.4605950, −3.5447694, inside the runway's 75 m strip.  Two honest
options for the owner: accept a road ramp 33 m off the runway edge
(the real road IS there), or cover the bore to the strip edge (a ~150
m tunnel the pack did not author).

**(3) THE RAW PAIR IS THE TRANSVERSE LAW.**  `--why-vertex`: the far edge
v6622 is 0.78 m ABOVE the runway contact (579.86 vs 579.08) — nothing
pulls it down; the RUNWAY edge is held 7.05 m over its own DEM by
`junction_mesh` stretched at cap 1.50 % × 43.2 m to a free zone-band
vertex, and the heaviest family at the far edge is `foot_rows` (dual
42,656 — object feet).  `transverse` rows exist and are AT THEIR BOUND
(1.35 % of 1.5 %) — as 4-term cross-corridor rows; the census prices
the raw pair across the junction at 4.30 %, and the raw pair is what
the owner sees from the cockpit ("lateral slope … still not fixed").
RULED: a junction's transverse law is the RAW PAIR across its width at
every station (the census's reading); the 4-term cross-corridor row is
not a transverse cap and does not satisfy it.  r3 sets raw-pair
transverse rows on junctions (≤ the taxiway cap, the runway's edge
level at the contact per airside-is-king) and names the object feet
that then yield or the row that then binds.

**(4) THE ROAD BETWEEN TWO MOUTHS — planar-stage, one face.**  The 24-
reader census (in the MEASURED block) returned HAZARD on five for a
general road-face admission (`airside_edge_flip` turning road into
apron inside a runway strip; §37 (1) contiguity handing a runway cap;
`road_ramp.deck_refs` grading a face to the surface OVER A BORE; the
lot ladder; the `route{i}` namespace) and the gated population is 207
faces / 944,872 m² (7.8 % of LEMD's coverage) to fix one 297.9 m road —
reverted.  RULED: §34 (11) (a) is re-founded on its own words — at the
PLANAR stage, two mouths of the same parent road within `mouth_pair_m`
(the LEMD pair is 88.7 m apart) mint ONE road face between them (the
road's own width, the §37 road rows, its zones), never a general
admission; the void (144,254 m², cover 0.011) then closes by that face
and its zones or is excluded per (11) (c).  v2roadtags' tags do not
reach this site (all 22 ways come from `airport_small_roads`, and
`TAGS_OF_INTEREST` drops `covered`/`cutting`/`embankment`) — noted for
the peer's follow-up, not this lane's.

### §34 (13) **MEASURED — r3** (lane `v2lemdstruct2`, branch `claude/v2lemdstruct2`, base main `539e524e`)

THE FRAME is r1's still: the ONE registered LEMD capture, matched
`v2_solve_replay` arms, the harness census on each `--emit`.  **NO
CLOSING BUILD** — checked once, the refresh ledger's last `osm_layers`
entry is **2026-09-08T11:33:30 (SPJC)**, so RULINGS 15u's owner act has
not run and LEMD would be measured on the corpus r1's build contaminated.
Suite `tests/auto_patch_v2 tests/test_harness.py`: **1,619 passed / 1
skipped / 0 FAILED**.

#### (3) THE RAW PAIR IS THE JUNCTION'S TRANSVERSE LAW — STATED AND MINTED; NOT MET AS A VALUE, AND THE REASON IS MEASURED TWICE

**WHAT LANDED.**  `constraints/transverse.junction_raw_transverse` — a
new generator beside `transverse`, registered in `constraints/__init__`.
It walks the SAME stations (`geometry.walk_transects`, the census's own
walk, never a second one) and, at each, prices the two RING VERTICES the
transect's two hits fall nearest — real emitted columns, which is what
makes it a raw pair — over their own plan distance at the axis's
transverse cap.  Two ruling heads so the halves can be told apart:
`RAW_PAIR_RULING` and, where one end is a vertex the junction SHARES with
a runway, `RAW_PAIR_CONTACT_RULING`; both registered in `[design]
one_way_rulings`, so at a contact the junction's far edge FOLLOWS and no
runway column ever moves for it (airside is king).  Where BOTH ends are
runway-shared the runway owns the pair and no row is minted.

**AT THE OWNER'S POINT the row is exactly right and it does not bind.**
LEMD `pav157` / 40.4611623,−3.5444804: the pair (v906 on the runway edge,
v6622 the junction's far edge 18.12 m away) is priced at **±0.268 m**,
`follows=(v6622,)` — and the solve still reads **4.296 % over 18.2 m**,
unchanged from r2.  1,591 raw-pair rows at LEMD, **62 of them contacts**.

**HARD WAS TRIED TWICE AND IS INFEASIBLE.**

| arm | what | result |
|---|---|---|
| c1 | the row as a TARGET (one-way, at `law`) | solve optimal, verify 1,549; `transverse` 115 → 97, `airside_no_step` 457 → 451; **the site unchanged at 5.01 %** |
| c2 | ALL 1,591 raw pairs in `[design] hard_rulings` | **10,006 of 109,240 hard rows violated, worst 60.48 m** |
| c5 | ONLY the 62 CONTACT rows hard | **8,548 of 106,182 violated, worst 105.29 m**; verify 179,008 rows, `runway_transverse` 625 and `runway_vertical_curve` 243 — the DEFECT families |

So the raw pair stands as the LAW and as a TARGET, and §34 (13) (3)'s own
alternative is what r3 reports.  **THE ROWS THAT BEAT IT, NAMED** (r2's
`--why-vertex`, unchanged): at the far edge v6622 — `foot_rows` **14 rows,
sum |dual| 42,656** (the object feet), `no_step_pairs` 6 (4,565),
`junction_mesh` 7 (1,870), `zone_bands` 4; at the contact v906 —
`no_step_pairs` (3,197), `junction_mesh` **at cap 1.50 % × 43.2 m**
(2,584) whose chain terminates on a zone-band vertex that is FREE, "held
by its ground datum".  A junction's far edge is held by four families at
once; a fifth, however correct, is one voice among them, and hardening it
over-determines the sheet.  **The residual is 4.296 % / 2.479 % against
1.985 % / 1.500 %, and it is the owner's to see beside 15y-1.**

| bar | r2 | r3 |
|---|---|---|
| the raw pair at 40.4611623,−3.5444804 (18.2 m) | 4.296 % | **4.296 %** — NOT MET |
| the same over 16.5 m | 2.479 % | **2.479 %** — NOT MET |
| census `taxi_box` \| `airside_no_step` junction\|runway pairs within 14 m | 5 \| 4 | **0 \| 8** |
| census `transverse` (the 4-term family) | 107 | **98** |
| census `airside_no_step` | 475 | **460** |
| runway vertices moved > 0.02 m by the new rows | — | **0** (every contact row is one-way on the junction end; the registers are twinned) |

#### (4) THE ROAD BETWEEN TWO MOUTHS — LANDED, AND THE PREDICATE THE BRIEF GUESSED IS REFUTED

**THE PREDICATE IS NOT "TWO MOUTHS OF ONE BORE FACING EACH OTHER".**
Measured at the owner's site: `tunnel:-15327@0` and `tunnel:-5980@0` are
88.5 m apart and their ramps climb AWAY from one another — dot of each
outward direction with the line between them **−0.916** and **−0.906**.
They are the two near portals of a DUAL CARRIAGEWAY whose far ends merge
at `tunnel:-15327+-5980@0` (−15327 is 2,234 m long, −5980 2,204 m), and
the 88.5 m between them is the 611 m plateau the bores pass UNDER, not a
road.  What IS the road between two mouths is the way whose OWN TWO ENDS
are mouths: **−5944** runs from `tunnel:-5931@1`'s mouth — sharing its
node exactly, **0.00 m** — to 47.3 m short of `tunnel:-5980@0`.

**WHAT LANDED.**  `planar/structure_road.py` (NEW, its own module because
`planar/structures.py` is at its 1,000-line budget and because lane
`v2vmmcshore` r2 is editing it): `mouth_pair_roads(airport,
classification, law, tunnels)`, called from `planar/build.build`
immediately after `build_structures` — the seam where the cells must
exist before the arrangement is built.  Law key `[tunnel] mouth_pair_m`
(100.0, in `structures.toml`; the model field carries NO default, which
is what the two `no_numeric_literal_in_law_python` twins enforce).
`StructureStats.mouth_roads` carries one named line per face and
`pipeline/build` prints them under the structures line, because the class
is meant to be a handful and a rising count must be visible.

The predicate, each clause answering a HAZARD r2's 24-reader census named:
a mapped `highway=*` way, itself **neither `tunnel` nor `bridge`** (the
census's worst hazard: a face over a bore is graded to the surface over
it); **each end within `mouth_pair_m` of a structure mouth, the two
mouths DIFFERENT**; **at least one end joined to the bore by a shared
NODE** (the canonical identity join) — two node joins reads **0** ways at
LEMD, none reads **27**, one reads **4**; the face is the way's own
carriageway width minus every existing cell; its own `mouth_road:<way>`
ref namespace.

**THE DRY PAIRS — 7 faces across three airports.**

| airport | faces | area | named |
|---|---|---|---|
| **LEMD** | **4** | **3,775 m²** | `mouth_road:-5944` 2,085 m² (the owner's), `-3830` 787, `-12917` 541, `-4044` 361 |
| **OTHH** | **0** | — | the class never fires (39 structures, cells 369 → 369) |
| **KCLT** | **3** | **3,564 m²** | `-11280` 2,613 m², `-11279` 929, `-9694` 22 |

Against 207 faces / 944,872 m² for the general admission r2 refused.

**THE BARS.**

| bar | before | after |
|---|---|---|
| the face exists on way −5944's segment | no road-family way within 60 m | **way −10867 `service_road` / `mouth_road:-5944`, 24 nodes, 605.09–611.00 m**; 4 of the 6 stations along the owner's own line now read it |
| its grade ≤ the road cap | — | worst edge **8.00 % against the 8 % road cap** — MET at cap; it rides its ground, \|z−DEM\| max **1.70 m** |
| the ground at 40.4940268,−3.5826498 within 0.10 m of the road profile | no face | **NOT MET** — −5944's own centreline ENDS 47.3 m short of that point; only the rim and the ramp stand there |
| hole ring −10670 (144,429 m²) closed | cover **0.011** | cover **0.023** — **NOT MET**; rings > 10,000 m² **13 → 13** |
| census by family | ADJ 1,360 | **ADJ 1,344** (airside 1,279 → 1,251); `transverse` 107 → 98, `airside_no_step` 475 → 460, `road_cross_section` 9 → 11, `taxi_box` 167 → 171, `hairline_pair` 1,423 → 1,428; LAW-TRUE 5,712 → **5,692**; CRITICAL motion 4 → 4, visual 1,433 → 1,438 (10 cliffs both) |
| the class's own census cost | — | **16 rows** on the four faces, **11 of them `-4044`'s** (a tertiary on a 12 % hillside, worst 10.79 % over 12.0 m); the owner's −5944 carries **one**, a 7.98 % cross-section over a 2.0 m span |
| solve | optimal | **optimal** |

**WHY THE VOID DOES NOT CLOSE, ARITHMETICALLY.**  One 2,085 m² road in a
144,254 m² hole is 1.4 %; r2 already measured that closing it takes a
**10-way, ~1,030 m network** (−5944, −5913, −5958, −5962 and six ~30 m
stubs), of which −5944 is the only one with a mouth at each end.  §34 (11)
(c)'s other limb — "or excluded from the graded strip" — is untouched by
this lane and is where the remaining 98.6 % belongs.

## §34 (13) (3) RULED ON r3's MEASUREMENT — AN OBJECT'S FOOT NEVER HOLDS AIRSIDE PAVEMENT (Fable 2026-09-15; RULINGS 2026-09-15ad) — lane `v2lemdstruct2` r4

r3 minted the raw-pair row (`constraints/transverse.junction_raw_
transverse`, one-way on the junction end at a runway contact; 1,591
rows at LEMD, 62 contacts; census `transverse` 107 → 98, junction|
runway `taxi_box` within 14 m 5 → 0; 0 runway vertices moved) and the
site still reads 4.296 %.  Hard was infeasible twice (10,006 / 8,548
violated).  The families that hold pav157's far edge v6622 ABOVE the
runway contact: `foot_rows` **14 rows, dual 42,656** (object feet),
`no_step_pairs` 6 (4,565), `junction_mesh` 7 (1,870), `zone_bands` 4;
at the contact v906 `junction_mesh` at cap 1.50 % × 43.2 m to a FREE
zone vertex held by its DEM.  RULED: (a) an object's foot row on an
AIRSIDE vertex is ONE-WAY toward the object — the foot follows the
pavement, never holds it (airside is king; the object stage re-seats
on the design surface anyway).  r4 names the 14 objects behind those
rows (what stands at a taxiway junction's edge 18 m from a runway —
signs, lights, a fence?) and flips their rows' direction at the
derivation site; (b) the `junction_mesh` row from the runway contact
to a free zone vertex terminates on a vertex that carries the
junction's own transverse law, not on a DEM-held zone vertex — the
mesh row's far end at a contact is the raw-pair partner; (c) re-
measure the crossfall; if the raw pair then binds and the site reads
≤ 1.985 %, done; if `no_step_pairs` bind next, name them and stop —
the residual joins 15y-1 for the owner.

### §34 (13) (3) (a) **MEASURED — r4** (lane `v2lemdstruct2`, branch `claude/v2lemdstruct2`, base main `848bf35e`)

Same registered LEMD capture, matched `v2_solve_replay` arms, harness
census on each `--emit`.  **NO BUILD** — the refresh ledger's last
`osm_layers` entry is still **2026-09-08T11:33:30 (SPJC)**.  Suite
**1,638 passed / 1 skipped / 0 FAILED**.

#### (a) THE 14 OBJECTS, NAMED — THEY ARE TWO BODIES OF ONE PLACEMENT

`foot_targets` on the capture: **8 foot targets touch v6622, from exactly
2 bodies** (the 14 the `--why-vertex` dual named are the binding subset of
their 16 one-sided rows).

| body | span | feet | verdict | target z | DEM under it | relief | `y_zero` | anchor |
|---|---|---|---|---|---|---|---|---|
| `LEMD_OBJ-Airport_Munoza-LEMD69#b2` | **2.232 m** | 4 | `bare` | 577.02 | 577.01–577.03 | 0.001 m | −1.198 | 40.4609886,−3.5450515 |
| `LEMD_OBJ-Airport_Munoza-LEMD69#b4` | **2.231 m** | 4 | `bare` | 576.85 | 576.80–576.91 | 0.001 m | −1.200 | 40.4609892,−3.5449556 |

**RESOURCE / CLASS.**  One pack placement, `Airport_Munoza` /
`LEMD69.obj`, cut by §6 into **27 rigid bodies** — b1…b22 and b24/b25 are
all **2.23 m** square with 4 feet, relief 0.001 m and `y_zero` −1.18…−1.21,
strung down the taxiway edge; b0 is the 28.0 m run and b23 the 71.3 m one
with 140 feet.  That signature — a 2.2 m flat square sitting 1.2 m under
its own origin, repeated in a line along a kerb — is the taxiway's own
**edge furniture** (sign boards / guidance panels on their plinths), and
b2 and b4 are two of them.

**ITS OWN GROUND, and why the row reaches AIRSIDE.**  Every one of the 8
feet stands on `graded_strip` — none on pavement — and the bodies sit on
their DEM to the centimetre (`fit_residual` 0.010 / 0.112 m).  The row
reaches the junction because a foot row is stated over the TRIANGLE the
foot stands in, and the graded strip SHARES its kerb vertices with the
junction it borders: **one node, one value** (09-01g).  v6622 carries
`graded_strip#94` AND `junction#86`, so two pieces of taxiway furniture
standing on the verge were holding a taxiway junction's crossfall through
a shared kerb column — the heaviest family on the vertex, `sum |dual|`
**42,656**, an order of magnitude over everything else.

**WHAT LANDED.**  `constraints/foot_rows.foot_rows`: a foot row whose
triangle touches an AIRSIDE VALUE ROLE keeps every term and sets
`follows` to its BARE-GROUND columns — the pavement's are GIVEN.  The
head `structures.placement foot_row` is registered in `[design]
one_way_rulings` beside its existing `foot_row_rulings` price entry.  A
triangle with NO free column stays two-sided (11x (1): all or nothing per
body).  `STATS["foot_rows"]["one_way_at_airside"]` reports the count —
**LEMD 184**, **HECA 3**.

**THE SCOPE IS THE RULING'S, AND THE NARROWING WAS MEASURED AND
REJECTED.**  Excluding the runway family (taxi + apron only) halves the
runway movement but never reaches zero and LOSES the law:

| scope | owner's raw pair | runway vertices moved > 0.02 m | worst |
|---|---|---|---|
| every airside value role (RULED) | **1.160 %** | 394 | 5.086 m |
| taxi family + apron only | **2.585 %** (over the 1.985 % cap) | 196 | 3.277 m |

#### (b) THE `junction_mesh` ROW — DISSOLVED BY (a), NOT EDITED

`--why-vertex 6622` after (a): `junction_mesh` **1 row, sum |dual| 0.07**
— it holds nothing, and its far end is v904/v903, both `junction#86` +
`runway#5`, not a DEM-held zone vertex.  The premise of (b) was r3's
measurement of a sheet the feet were distorting; with the feet one-way it
is gone.  **No change was made to the 04y mesh population**, because
rewriting a triangulation edge to a different pair on the strength of a
dissolved symptom is the opposite of mechanism-before-fix.  What binds
v6622 now: `foot_rows` 8 (26,950, still in the row as GIVEN terms),
`rim_level` 1 (117), `junction_mesh` 1 (**0.07**); the chain runs 6 hops
to the F-6 trench's own pinned ramp top.

#### (c) THE CROSSFALL, RE-MEASURED — BAR MET; THE RUNWAY MOVED, AND IT IS THE PRICE

Read BY COORDINATE on the two closing planar arms (the vertex ids differ:
the mouth-road cells renumber the map).

| | r3 closing (`c6`) | r4 closing (`d5`) |
|---|---|---|
| contact vertex at 40.4611623,−3.5444804 | 579.068 | 582.586 |
| the junction's far edge, 18.12 m out | 579.850 | 582.309 |
| **THE RAW PAIR** | **4.313 %** | **1.529 %** — **MET** (junction cap 1.985 %) |
| census rows within 20 m of the owner's point | 8 | **0** |
| the row that binds | — | none at the site; the pair is inside its cap and the census prices nothing there |

| census family | r3 (`c6`) | r4 (`d5`) |
|---|---|---|
| `transverse` | 98 | **90** |
| `airside_no_step` | 460 | **377** |
| `taxi_box` | 171 | **163** |
| `within_shape` | 3,415 | **3,585** |
| `strip_transverse` (worst) | 81 (13.864 m) | **89 (17.700 m)** |
| `ramp_in_strip` | 8 | **18** |
| LAW-TRUE / ADJUDICATED | 5,692 / 1,344 | 5,791 / **1,357** (airside 1,251 → 1,215) |
| CRITICAL motion | 4 | **6** |
| CRITICAL visual (cliffs) | 1,438 (10) | 1,456 (**20**) |
| v2 verify rows | 1,564 | **1,547**; DEFECT families ALL ZERO, solve optimal |

**THE RUNWAY-IMMOBILITY BAR IS NOT MET AND CANNOT BE BY THIS MECHANISM.**
Joined by identity key over 4,031 shared runway-family vertices,
**354 moved more than 0.02 m, worst 5.687 m**, 8 of them over 2 m — all
at the F-6 crossing.  That is not a one-way leak: the feet WERE holding
the runway, so removing a hold necessarily moves what it wrongly held,
and even the taxi-only narrowing leaves 196 moving.  The knock-on is
named: `ramp_in_strip` 8 → 18, `strip_transverse` worst 13.864 → 17.700 m,
cliffs 10 → 20, and a **new `mid_edge_step` 0.950 m over 1 m between two
RUNWAY faces at 40.4613609,−3.5446852** — a welded step on rolled-on
pavement, the kind of row the pilot feels, at the owner's own site.
Against that: the crossfall is fixed, airside ADJUDICATED falls 1,251 →
1,215, `airside_no_step` 460 → 377 and the site prices nothing.  **The
trade is the owner's to see beside 15y-1.**

#### THE CONTROL — HECA, matched pair, ONE variable

The law toggle alone (`one_way_rulings` entry in / out), one tree, one
capture (`HECA.off3.pkl`).  Only **3 of HECA's 4 foot targets** touch
airside pavement, and the change is nearly inert:

| | flip OFF | flip ON |
|---|---|---|
| v2 verify rows | 30,459 | **30,500** (+41, +0.13 %) |
| `airside_no_step` | 7,794 | 7,823 |
| runway-family vertices moved > 0.02 m | — | **8 of 3,753**, worst **0.064 m** |
| whole surface max \|off − on\| | — | **0.822 m**, 2 vertices over 0.5 m |

LEMD's 5 m is therefore a SITE property — two bodies of edge furniture on
a junction↔runway contact — not the law's general cost.

#### A DEFECT THIS ROUND MADE AND CAUGHT, RECORDED

Disarming the flip for the HECA control by deleting every line matching
the head's prefix deleted the `foot_row_rulings` entry as well, which
silently re-priced **every foot row in the tree** from `pad_flat` (3000)
to `law` (3).  The four §11b twins caught it; the first HECA control arm
was run under it and was DISCARDED and re-run with a single-variable
toggle.  `tests/test_harness.py::test_the_foot_row_head_is_in_both_
registers` now twins the two registers apart — `conforming_rulings` is
their union and so could never have been the guard.

### §34 (13) (3) **MEASURED — r5: WHAT HOLDS 14R/32L THERE, AND THE ANSWER IS THAT IT IS NOT 14R/32L** (lane `v2lemdstruct2`, base main `d803147a`)

#### 0. THE FRAME r4 GOT WRONG, AND THE CORRECTION

r4's runway figures compared `c6` (r3's closing arm) with `d5` (r4's) —
and **main moved between them** (`v2vmmcshore` added
`planar/structure_service.py`, `v2objcut` landed).  That is a cross-tree
comparison and it is not evidence (memory
``cross-tree-comparisons-are-not-evidence``).  r5 rebuilt the pair on ONE
tree, ONE capture, ONE variable — the `emit.toml one_way_rulings` entry
for `structures.placement foot_row`, in and out, registers asserted
before each arm:

| | flip OFF (`e_off`) | flip ON (`e_on`) |
|---|---|---|
| solve | optimal 188.1 s | optimal 174.3 s |
| v2 verify rows | 1,711 | **1,554** |
| census LAW-TRUE / ADJUDICATED | 5,782 / 1,505 | **5,712 / 1,393** (airside 1,370 → **1,258**) |
| CRITICAL motion | **7** | **5** |
| CRITICAL visual (cliffs) | 1,456 (**20**) | 1,456 (**20**) |
| `mid_edge_step` | **2, worst 0.950 m** | **2, worst 0.950 m** |
| `ramp_in_strip` | **18** | **18** |
| `airside_no_step` | 452 | **357** |
| `taxi_box` | 152 | **130** |
| `transverse` | 98 | **90** |
| `strip_arc` | 9 | **4** |
| `within_shape` | 3,497 | 3,559 |
| `strip_transverse` (worst) | 90 (13.864 m) | 89 (**17.700 m**) |
| the owner's raw pair | **4.313 %** | **1.529 %** |

**THE 0.950 m STEP, THE 18 `ramp_in_strip` ROWS AND THE 20 CLIFFS ARE ON
BOTH ARMS.**  r4 reported them as the flip's cost; on a matched pair they
are not.  The flip's real price is `within_shape` +62, `strip_transverse`
worst 13.864 → 17.700 m and `raoa` 1 → 2; its gains are CRITICAL motion
7 → 5, airside ADJUDICATED −112, `airside_no_step` −95, `taxi_box` −22,
`transverse` −8, `strip_arc` −5 and the crossfall.  **Net the flip is
clearly positive**, and the case for holding r4 was built on a frame
error this round corrects.

Runway movement, same matched pair: **319 of 4,042 runway-family
vertices move more than 0.02 m, worst 5.687 m** (r4's 354 / 5.687 m was
the right magnitude by luck).  That number is real and §1 explains it.

#### 1. `--why-vertex` ON THE WORST MOVER — THE SAME ANSWER ON BOTH ARMS

v902 (40.4610273,−3.5449992), the worst mover, 576.631 → 582.319:

    e_off: binding rows on v902 by family — foot_rows 9, sum|dual| 48,669
           chain trace: no terminal reached — the objective holds it
    e_on : binding rows on v902 by family — foot_rows 9, sum|dual| 48,669
           chain trace: no terminal reached — the objective holds it

**On BOTH arms the ONLY family binding it is `foot_rows`, and on both the
chain reaches no terminal.**  No §29 profile row, no CIFP threshold pin,
no lateral-band row, no `runway_crown`, no `runway_transverse`, no
longitudinal cap binds that vertex on either arm.  (On the OFF arm the
pressure solve moves the surface by up to **10.265 m** — the OFF
solution is nowhere near the pressure solution, which is itself the
signature of a sheet held by weights rather than constraints.)

#### 2. WHY — THE VERTEX IS NOT ON THE RUNWAY

Generator coverage of the 4,033 runway-family vertices, counted offline
on the capture:

| generator | vertices covered |
|---|---|
| `runway_crown` / `runway_transverse` | 3,950 |
| `runway_within_shape` | 3,720 |
| **`runway_profile` / `runway_vertical_curve`** | **1,421** |

`runway_profile` and the CIFP threshold pins are the ONLY rows that give
a runway vertex a LEVEL; everything else bounds a DIFFERENCE.  Their
population is `ridge_chains` — the `runway_profile` BREAKLINE, i.e. the
centreline.  And the centreline is perfect: **14R/32L is ONE chain, 365
vertices, carrying its threshold pins, and it moved at most 0.059 m
between the two arms.**  All four LEMD runways are one intact pinned
chain each.

So where is v902?  Measured assumption-free as the distance to the
nearest 14R/32L ridge vertex:

| vertex | distance to the 14R/32L RIDGE | roles |
|---|---|---|
| v902 | **451.6 m** | `graded_strip` + `runway` |
| v903 | 453.9 m | `graded_strip` + `junction` + `runway` |
| v906 (the owner's own point) | **495.8 m** | `junction` + `runway` |
| v940 (a face of the 0.95 m step) | 491.8 m | `runway` |

14R/32L is **61.1 m** wide — a half-width of 30.5 m.  These vertices are
**fifteen times** that off its centreline, and they all sit on ONE face:

| face | ring | area | lateral offset from the ridge (min / median / max) | beyond the 30.5 m half-width |
|---|---|---|---|---|
| 0 | 538 | 133,118 m² | 0.0 / 0.0 / **30.9 m** | 115 of 538 |
| 7 | 555 | 133,106 m² | 0.0 / 0.0 / **31.0 m** | 118 of 555 |
| **5** | 306 | **111,308 m²** | 30.2 / **58.1** / **914.3 m** | **276 of 306** |

Faces 0 and 7 are the runway.  **Face 5 is not**, and the classification
says what it is: **cell 15, `kind = runway_shoulder`, 111,648 m², code
4/F** — a §40 (1) SHOULDER, admitted as a runway cell with the runway's
ref, code number and code letter.

**THE MECHANISM, STATED PLAINLY.**  14R/32L's level at that station is
derived from NEITHER the runway's own law nor honestly from neighbours:
the station is not on the runway.  A 111,648 m² §40 (1) shoulder reaching
**914 m** from the centreline carries the runway's role, ref and code, so
`runway_crown` and `runway_transverse` are minted over it — but those
price a CROWN across a 30.5 m half-width, and over 58–914 m they bound
nothing a five-metre move could violate (which is why the DEFECT families
read ALL ZERO on both arms throughout r3, r4 and r5).  `runway_profile`
never reaches it.  The shoulder's level was therefore held by the
objective, and — until r4 — by two object feet: `LEMD_OBJ-Airport_
Munoza-LEMD69` b2 and b4.

#### 3. WHY TWO "RUNWAY FACES" STEP 0.95 m OVER 1 m WITHOUT A DEFECT

`runway_transverse` IS the DEFECT family that would price it, and it is
the CROWN reading: a pair judged against the runway's own axis and half
width.  A pair 490 m off-axis is not a crown pair, so the family never
sees it, and no other DEFECT family prices a step between two faces of
one role.  The census sees it only as `mid_edge_step` — a geometric
within-face welded step with no axis notion — and the cockpit block
classes it a CLIFF because it is steeper than the design surface's own
bank.  Both rows are REPORT, not DEFECT.

**A `runway_step` DEFECT FAMILY WAS NOT ADDED, and that is deliberate.**
On this geometry it would fire on 111,648 m² that is not a runway, making
the instrument agree with a role it should be disputing.  The family is
worth having — but after the role is right, not instead of it.

#### 4. THE FIX IS NOT AT THE RUNWAY LAW'S DERIVATION SITE

15an asked for it there ("the runway holds itself: its profile/threshold
rows must be present and binding at every runway vertex incl. shared
kerb nodes").  The measurement says the runway already holds itself
perfectly — one pinned chain per runway, ≤ 0.059 m of movement — and that
extending `runway_profile`'s level rows to "every runway vertex" would
spread the runway's own profile law across a **111,648 m²** shoulder
lobe reaching 914 m off the centreline.  That is a §40 question (what a
shoulder is, and whether a shoulder 914 m from its runway is one at all),
it lives in `classify/roles` beside §40 (1)/(4), and it is the shape of
change owner RULINGS 2026-08-30l requires a consumer census for.  This
lane STOPS at the attribution rather than improvising it — which is what
"mechanism before fix" is for.

**What r5 recommends, with its numbers:** (i) MERGE r4 — on a matched
pair the flip costs nothing it was held for and buys airside ADJUDICATED
−112 and CRITICAL motion 7 → 5; (ii) open the §40 shoulder question with
face 5's table above; (iii) add `runway_step` once a shoulder's extent is
ruled.

## §34 (13) (3) MEASURED (lane v2lemdstruct2 r4 96c1208f; Fable 2026-09-15; RULINGS 2026-09-15an) — the feet were `Airport_Munoza/LEMD69.obj`'s 27 plinth bodies on the kerb; one-way at airside meets the crossfall (1.529 %) — and the RUNWAY moves 5.687 m at LEMD (HECA control 0.064 m): what held 14R/32L there was the furniture, not the runway's law → r5 attributes the runway's own rows before the merge

The 14 binding foot rows at v6622 belong to TWO bodies of ONE
placement (`LEMD69#b2`, `#b4`: 2.23 m square, 4 feet, relief 0.001 m,
`y_zero` −1.2 — sign panels on plinths strung along the kerb, 27 bodies
in all); their feet sit on `graded_strip` at their own DEM, and the row
is stated over the TRIANGLE while the strip shares its kerb vertices
with the junction (one node, one value, 09-01g) — so verge furniture
held a junction's crossfall at dual 42,656.  LANDED: `constraints/foot_
rows.foot_rows` — a foot row touching an airside value role keeps its
terms and sets `follows` to its bare-ground columns (head in
`one_way_rulings`; an all-pavement triangle stays two-sided, 11x (1));
LEMD 184 rows one-way, HECA 3.  The `junction_mesh` row dissolved (dual
0.07, far end on junction+runway vertices) — NOT edited.  Crossfall at
the site 4.313 % → **1.529 %** (cap 1.985), census rows within 20 m 8 →
0; `transverse` 98 → 90, `airside_no_step` 460 → 377.  THE PRICE: 354 of
4,031 runway vertices moved > 0.02 m, worst **5.687 m**; the contact
rose 579.07 → 582.59; `ramp_in_strip` 8 → 18, `strip_transverse` worst
13.86 → 17.70 m, cliffs 10 → 20, and a NEW `mid_edge_step` 0.950 m over
1 m between two RUNWAY faces at 40.4613609, −3.5446852.  HECA control
(one variable): 8 of 3,753 runway vertices, worst 0.064 m.  RULED: the
direction is right and stays; the runway movement is a SITE property —
at that station 14R/32L's level was being held by the sign feet, which
means the runway's own rows (§29 the profile preserve / the CIFP
thresholds / the lateral band, the runway crown) were slack or absent
there.  r5 ATTRIBUTES before the merge: `--why-at` on the worst runway
mover and on both faces of the 0.95 m step — which runway-family rows
exist at those vertices, what holds the runway's level there on the r3
arm (with the feet) and on the r4 arm (without), and why two runway
faces can step 0.95 m over 1 m without a structural DEFECT.  The fix
follows the attribution (the runway's own law must hold the runway; a
step between runway faces is a DEFECT family if it is not one).  Also
recorded: a register-deletion defect this round (disarming a head by
prefix also deleted `foot_row_rulings`, re-pricing every foot row 3000
→ 3) was caught by the §11b twins; the two registers are now twinned
apart.

## RULINGS

## 2026-09-15az v2lemdstruct2 r4+r5 MERGED (1da0faeb): r4's 5.687 m "runway movement" was a CROSS-TREE comparison (main moved between the arms); on one tree/one capture/one variable the one-way-feet flip costs `within_shape` +62 and gains airside ADJUDICATED −112, motion 7 → 5, the owner's raw pair 4.313 → 1.529 % (1.542 % in a real build); the moving "runway" vertices sit on a §40 SHOULDER cell of 111,648 m² reaching 914 m off the centreline — RULED §40 (5): a shoulder is a band, the runway role ends at the strip, every runway vertex carries a level, `runway_step` DEFECT

Lane @ 1da0faeb; suite 1,658 passed, 0 FAILED. Matched pair (flip
OFF/ON): verify 1,711 → 1,554, ADJUDICATED 1,505 → 1,393 (airside 1,370
→ 1,258), motion 7 → 5; the 0.95 m `mid_edge_step`, the 18 `ramp_in_
strip` rows and the 20 cliffs are on BOTH arms (r4 charged them to the
flip — withdrawn); the flip's price `within_shape` 3,497 → 3,559,
`strip_transverse` worst 13.86 → 17.70 m. `--why-vertex` v902 (the
worst mover): only `foot_rows` bind (dual 48,669), "no terminal
reached — the objective holds it", on BOTH arms; the pressure solve
moves it 10.265 m. v902/v906/v940 are 452–496 m from 14R/32L's ridge on
face 5 = cell 15 `runway_shoulder` 111,648 m² (276/306 vertices beyond
the 30.5 m half-width). `runway_transverse` is the crown reading and
cannot see a step 490 m off-axis; no `runway_step` was added (it
would endorse the role it should dispute). Closing build (`--tile
40 -4` — a TILE build, run before the 15av order reached this lane;
the LEMD pack's newest dump is 07:23, no pack file newer than 12:00 —
no rebake write observed; the lane asked to confirm): rc 0, 980 s,
`shared repo UNCHANGED`; the owner's raw pair 0.280 m / 18.16 m =
1.542 %; item 5 5.07 m; item 7 rim 31.06 m; 3 mouth roads. RULED §40
(5) (consumer census first, then the classifier cut): the shoulder
band, the runway ref dropped beyond the strip, level rows across the
band, `runway_step`. Memory rule re-founded by this round: cross-tree
comparisons are not evidence (14bk, r4) — a lane's before/after must
be one tree, one capture, one variable, registers asserted per arm.

## 2026-09-15an v2lemdstruct2 r4 HELD (96c1208f): the crossfall bar MET (4.313 → 1.529 %) by making foot rows one-way at airside — the 14 feet were `LEMD69.obj` sign plinths on the kerb — but LEMD's runway moves 354 vertices / 5.687 m and a 0.95 m step appears between two runway faces at the owner's site (HECA control 0.064 m) → r5 attributes what holds 14R/32L there before the merge

Lane @ 96c1208f; suite 1,650 passed, 0 FAILED; no build (the lane
read the ledger before the 11:05–11:35 refreshes; +40-004 needed none).
Details in §34 (13) (3) MEASURED. The direction (a foot never holds
airside) is RIGHT and is not re-litigated; what is wrong is that the
runway's level at that station depended on it — the runway's own rows
must hold the runway. r5: `--why-at` on the worst runway mover and on
the 0.95 m step's two faces on BOTH arms; name the runway-family rows
present/absent; then the fix at the runway law's derivation site, and
a DEFECT family for a step between runway faces if none prices it.
HECA control clean (+41 verify rows, 8 runway vertices ≤ 0.064 m).
Register defect caught by the §11b twins (`foot_row_rulings` deleted
by a prefix match; every foot row re-priced 3000 → 3; the control arm
discarded and re-run) — the two registers twinned apart.

## 2026-09-13co Owner read of 1.0.329 — HECA ("mostly … close to the best we've built so far"), six items — scout `v2heca329`

Owner, verbatim: "HECA is mostly looking close to the best we've built so
far. Some issues: 1. shapeID 44 is a taxiway role, but taxiway cannot run
adjacent to a runway, that portion should have been absorbed into the runway
itself 2. Around here: 30.1312203, 31.3983896 I can't tell if there's a gap
with no coverage, or just a problem, but in the sim their's a bit dip in the
taxiway that aircraft could not drive through. 3. This taxiway has too much
lateral slope: 30.1114112, 31.4063353. Really we just need this area
30.1116052, 31.4066985 to be lowered so we don't have so much of a hill
right there, then the road, taxiway, and apron can all meet more smoothly.
4. This is the edge of a road: 30.1096746, 31.4048466, the center of the
road here: 30.1096476, 31.4048517 is lower creating a sharp lateral slope in
the road 5. Road here: 30.1077666, 31.4031555 is ending in a cliff above the
taxiway, it should join the taxiway edge smoothly with no gap and at the
same elevation. 6. This large area 30.1082777, 31.4022695 is apron, not all
taxiway, and shapeID 478 should be part of it, not adjacent ground"

* Earlier in the same read (LEMD): "There's nothing in the patch, it seems
  like both LEMD and HECA the terrain looks different, did anything change
  with the DEM? … a road that now appears in a deep canyon: 40.465414,
  -3.5531888". Checked: NO DEM refresh since 2026-09-08 (refresh ledger), no
  elevation file newer than the 1.0.329 app. Mesh-path commits since
  1.0.327: b6ad4309 / 0523aec5 / 95579a99 / d1fd6242 (§39 shore weld,
  vector-map weld OFF, pre-flight). Scout `v2lemd329` redirected: coverage
  test at the coordinate, mesh profile vs DEM, diff of every code path
  touching non-patch terrain.
* Scout `v2heca329` dispatched on the six HECA items: (1) shape 44's role
  and its runway adjacency — the §29 (7) lateral band / role scorer; (2)
  coverage at 30.1312203, 31.3983896 and the dip's profile; (3)/(4) the
  cross-slope at the two sites against §37 (8) (road cross-section is LAW)
  and the taxiway lateral cap; (5) the road end vs the taxiway edge — §37
  (9) coverage-edge join; (6) shape 478's role and the apron/taxiway
  partition at 30.1082777, 31.4022695.

## 2026-09-14s VHHH tunnel regression attributed (scout `v2vhhhtunnel`): §40's shoulder re-role grew the RUNWAY strip keep-out and refused the big road tunnel; the basin pass took the vacated ground — a 30l consumer-census miss; §40 (4) written; lanes `v2roles` r3 + `v2othhfix`

Old arm = v2gradecache's VHHH patch (51c4666b, 2026-09-13 22:04) vs
the owner's 1.0.332 patch: every matched tunnel-family ring z-identical
(70 trenches, 30 ramps, 103 rims; only decimation differs). ONE site
changed, 22.30368, 113.92917 (`tunnel/tunnel1_done.obj`): the 62-node
`tunnel_ramp` (6,310 m², 7.31 → 2.22) and its OPEN wall are GONE;
instead `basin:5` — a CLOSED 25-node rim at 7.31 (4,057 m²) and two
floors to −0.13 (2.35 m below the old ramp's bottom); the descent
carried by 4 interior vertices (1.4 / 1,000 m² vs 22 in the pavement);
a 42 % mouth cliff (7.25 → 0.91 in 15 m). Reports: tunnels 28 → 27,
refused 44 → 45, basins 70 → 71 (`basin:5` new). Mechanism: f19e2226
(§40) re-roled three faces beside 07R/25L to `runway` (83,999 + 8,040 +
6,228 m²; VHHH runway area 780 k → 1,273 k m²); `planar/structures.py:
292-298` builds the strip keep-out from every `RUNWAY_FAMILY` cell ⊕
75 m (`zone2_half_width_m`, code 4) — the shoulders stand 60–69 m from
the tunnel footprint (old nearest runway face 221 m) → `:593-597`
"the wall would stand inside the runway strip keep-out"; then
`planar/build.py` runs structures before basins, `basins.py:711-719`'s
"overlaps a tunnel structure" guard no longer fires, region 5 is
admitted as a pit. Collateral: `zones.py:96-99` keys on `RUNWAY_FAMILY`
too → the shoulders mint 75 m zone-2 bands (`graded_strip` +587,849
m²; `junction dsf:pol406` 7.11 → 5.98 beside the tunnel) —
contradicting rules.toml's own "a shoulder manufactures no zone strip".
The 14r "24 ramps > 0.5 m" population dissolves under a per-vertex
envelope reading (100 of 101 rings at 0.00; one −2.00 m ramp byte-
identical across patches). The mesh is innocent.

* RULING §40 (4): a runway shoulder is PAVEMENT OF THE RUNWAY, not the
  runway's STRIP: it carries the runway's datum, crown and lateral law
  and manufactures NO region — it is excluded at the two region
  derivation sites (`structures.py` strip keep-out; `zones.py` zone
  band — it inherits the host runway's band), and every `RUNWAY_FAMILY`
  reader is censused in one table (the 30l miss). Lane `v2roles` r3.
* §24 (8): a basin's ramp corridor is RE-NODED at `ramp_station_m`
  before emission so §24 (5)'s per-station profile has vertices (today
  `constraints/structures.py:779-783` only pins existing planar
  vertices — a 4-triangle fan). Lane `v2othhfix` (basins.py).
* Open: whether an 84,000 m² face beside 07R/25L is a shoulder at all
  (`runway_shoulder_max_depth_m` 50 admitted it) — the owner's eye on
  the 1.0.333 VHHH read.

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N] [--why-hard-stage 1]` on either a `--replay` arm or a `--why-from PKL`; `--why-from PKL --probe-site LAT,LON [--probe-drop M] [--probe-arm TERM=V ...]`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (**and THE CLUSTERS beside the partition and the groups** — lane ``v2padjoin`` 2026-09-14: a capture without ``Airport.clusters`` leaves §30 (4)'s cluster pad, its apron reach and §16g (10)'s derived pads INERT in every replay of it, so a pads-ON arm silently measures the pads-OFF law; a capture predating them has them DERIVED at replay off its own partition, named on stdout) (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently).  **`--why-hard-stage 1`** reads §20b STAGE 1's OWN ASSEMBLY instead of the full problem's (`solve.design.stage_split`'s drop + fixed): the AIRSIDE hard set, in the rows and the metre scaling stage 1 enforced them under. The full read cannot answer "does the AIRSIDE solve settle" — the airside rows are a subset of 325k whose population and scaling the stage's own drop changes — and that is exactly the claim RULINGS 13y (B) / 13ab / 14as make (lane `v2settle`, which used it to split HECA's "42 unsettled rows" into 9 CONSTANT rows the solve can never move, 6 HELD runway rows at the projection's own bar, and 18 real ones).  The shipped surface is read either way: an airside vertex's z IS stage 1's, so the stage-1 read at the shipped z equals the read at stage 1's own surface (measured identical at HECA). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate).  **`--probe-site LAT,LON` IS THE STABILITY PROBE** (lane `v2qp`, spec §20c, promoted from lane `v2settle` r2's `scratchpad/v2settle/probe3.py`/`probe4.py` on its second use): off a `--solved-out` pickle, one extra `Band` ceiling `--probe-drop` (default 0.30) metres under the ARM's OWN base surface at the vertex nearest the point, re-solved, and the moved set (> 0.02 m) binned by distance from it — 0-40 / 40-100 / 100-250 / 250-500 / beyond, with the worst beyond 250 m, each arm's hard set and its exit line.  `--probe-arm TERM=V` repeated makes it a MATCHED PAIR of `[design]` arms on ONE problem (`--probe-arm solver=fixed_point --probe-arm solver=qp` is §20c's own bar); with none it probes the shipped law alone.  This is the instrument RULINGS 2026-09-14bw's headline was taken on (HECA: 959 vertices moved by one 0.30 m row, 953 beyond 500 m, ZERO within 100 m).  `--design-weight TERM=V` also takes a NON-NUMERIC value now (§20c's `solver=qp`); a value that does not parse as a float is passed through as the string.    **`--placement KEY=V` IS THE CAPTURE-TIME LAW ARM** (lane `v2padqp`, spec §16g (10) (11)): the §16g (10) pad keys (`pad_from_cluster`, `pad_airside_clip`) are read in `classify/evidence._pads` and `planar/overlay` — UPSTREAM of the capture — so `--design-weight` (a `[design]` override applied at REPLAY) cannot arm them and a pads-ON replay of a pads-OFF capture silently measures the pads-OFF law; a matched OFF/ON pair is therefore TWO CAPTURES of one tree, never two edits of the shipped toml (the value is coerced to the key's own type, an unknown key refuses by name, and the arm is recorded in the pickle).  `--capture` also arms `harness/build_airport.arm_shared_repo_protection` — the ONE arming composition — and prints `[guard] shared repo UNCHANGED`.  Twin: `tests/auto_patch_v2/test_v2qp.py` (the probe as a fixture pair) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

## Tool: check_grade

| `Ortho4XP/tools/check_grade.py` | You want the grade validator's CLI on one patch, or its library from code. The CLI is a thin front end over the same law reader the census uses. A run with no sidecar is CONTEXT-FREE and overcounts — it is not a defect count. It also prints **THE COCKPIT BLOCK FIRST** (owner RULINGS 2026-09-12x/12y; §31 (6)) — the same `cockpit_block` / `cockpit_block_lines` the harness census and the pytest fixtures call, over the SAME run's `family_out` (the checks' own output is buffered and replayed under the block, never run twice). A `strip_seam_tear` row carries the PAIR MIDPOINT as its lat/lon (spec §32 (3), RULINGS 2026-09-12ag): it used to carry none, and `run_checks` filled it with the offending way's RING CENTROID — at LEMD that sent the cockpit block's first CRITICAL VISUAL find 220 m from the 8.25 m tear. Twinned both sides (`tests/auto_patch_v2/test_v2zoneclamp.py`), the engine's own `verify/strips.strip_seam_tear` alongside. The block's "in view by approach" test is the ONE approach corridor of `auto_patch_v2.law.approach_corridor` (RULINGS 2026-09-12al; twins `tests/auto_patch_v2/test_v2approachcorridor.py`), never a radius around a runway vertex. **`adjacent_ground_step`** (spec §34 (4), lane `v2rampwalk` 2026-09-13) is the WITHIN-FACE welded step on a v2 `adjacent_ground:*` face — the reading no family had: `graded_strip` carries no within-shape cap, `adjacent_ground_tear` fires only under a 1 m edge and `strip_seam_tear` is the CROSS-shape twin, so a band holding its designed level over a mapped road's own ground (LEMD `zone2#2`, 1.73 m over 1.5 m at road −6289) was priced by nothing. Its floor is the cockpit's own `visual_m` AND `cliff_grade` in one step: without the cliff term it counts the lawful hillside drape (measured CYXY 296 rows). Lockstep both sides — `auto_patch_v2.verify.strips.adjacent_ground_step` reads it in the engine; twins `tests/auto_patch_v2/test_v2rampwalk.py` and the v1/v2 census parity test. **`ramp_in_road`** (spec §34 (10), owner RULINGS 2026-09-14bb/14bc/14bd, lane `v2othhramp`) is the CRITICAL presence family the road margin needed: every ramp arriving at a road ends at the road's TRUE edge — the centreline offset by the road's own half-width toward the ramp, ONE derivation `planar/wall_corridor_ramps.road_true_edge` read by every ramp emitter — so a RAMP vertex standing INSIDE a road ribbon is a lane of carriageway cut away, whatever its elevation. No other family sees it: a ramp welded flat into the road it ate breaks no grade law and prices zero rows. A vertex within the census's own weld tolerance of the ribbon's edge is ON the edge, which is what the law asks for. It reads 0 at OTHH before and after — the family is the GUARD on that derivation and never a defect count. Twins: `tests/test_harness.py` §34 (10) (both directions, the weld line both ways, the register and the cockpit class, and the ramp-role set read from the law's own structure roles). **`ramp_in_strip`** (spec §34 (5) (b), Fable 2026-09-15 / RULINGS 2026-09-15h, owner 15e item 7, lane `v2lemdstruct2`) is its AIRSIDE sibling: the covered extent of an underpass beneath a taxiway or runway spans the pavement AND its graded strip, so a RAMP vertex standing inside that strip is a trench in the ground an aircraft leaving the pavement runs out onto — LEMD 40.4611623,-3.5444804, where a code-E strip is 19.0 m and the trench face stood at 15.5 m under a 5.42 m unbanked drop, the airport's worst CRITICAL VISUAL row. The strip region is ONE derivation with `planar/zones.zone_regions` and `planar/structure_underpass.strip_half_width_m` (the zone-2 half width for the cell's class, the zone-1 LIP where the class declares none), read from the LAW with a literal no-engine fallback the twin asserts against. TWO READINGS MEASURED, NOT CHOSEN: the face's sidecar HOLES are applied and the pavement SOLID is subtracted, so the region is the BAND — read ring-blind and disc-shaped the first arm reported 52 LEMD rows, every one inside `cross_connector:pav61`'s own 144,429 m2 void and up to 220 m from any kerb, and `de_m` can now never exceed the class's own half width. Twins: `tests/test_harness.py` §34 (5) (b) (both directions, the class's own half width against the zone law and the planar derivation, the taxiway-loop void, the weld line both ways, the register and the cockpit class). **THE RUNWAY SHOULDER'S OWN CAP** (spec §40 (2) as amended, owner RULINGS 2026-09-13dd, lane `v2roles`): a within-shape pair BOTH of whose nodes lie beyond their runway's own half width is priced at `shoulder_transverse_max` (2.5 %, ICAO Annex 14 §3.2.4), not the runway's 1.5 % — a §40 (1) SHOULDER keeps the runway's DATUM, not its cross-fall. The line is the SOLVE's and is read, never re-derived: the sidecar's `runway_axes` (`[ref, lat_a, lon_a, lat_b, lon_b, half_m]` off the apt.dat ends and width) and `shoulder_transverse_max`, through `shoulder_nids` / `_shoulder_cap`. Fitting the width to the runway RINGS instead would read a shoulder as part of the runway and never find its own line. A patch with no key reads exactly as before. One reading with the generator and the v2 verify (`auto_patch_v2.law.tables.runway_transverse_cap`); twins `tests/auto_patch_v2/test_runway_shoulder.py`. |

## Tool: census

| `Ortho4XP/tools/harness/census.py` | You need DEFECT COUNTS from an emitted patch. Every law family always (the register, never a hand list), law-true frame from the patch's own sidecar, airside/groundside/mixed split, worst-N rows, class table, sidecar evidence, JSON + table, A/B across patches. **The only numbers that may be quoted as defect counts.** `--zone-split` additionally buckets the within-shape rows by FAN-RAMP ZONE membership (on a declared ramp piece / inside a zone / crossing one / unrelated, plus the rows already steeper than the zone cap) — reach for it when a grade law grants relief on declared ground and you need to know whether the relief is where the defects are. It is a flag and not its own tool because it needs the census's law-true frame; a private copy of that frame is the census-wrapper defect above. `--magnitude-bands [EDGES]` buckets EVERY law-true row by severity (|de| / step height; default edges `0.01,0.1,1,10` m, or your own ascending list) with the airside/groundside/mixed and adjudicated/version-deferred splits per band — reach for it when the question is which KIND of population a total is, not how big it is (the frame of record is stated in these terms: "0.1-1 m 13,711 = 45.1 %, 1-10 m 11,143 = 36.7 %, 82 % is in-band airside solver residual"). The bands PARTITION the census's own rows and the band below the first edge is the materiality floor's own. Promoted 2026-08-06 from the two lane copies that hand-rolled it (c6attr, c6tip). `--frame own\|base` selects the AXIS FRAME: `own` (default) is the patch's own sidecar and the only frame whose numbers are defect counts; `base` re-reads the SAME patch bytes with the SERVICE axes removed from its sidecar — the axis population a pre-road-feed sidecar carried — which is what splits "the class moved because the surface moved" from "…because the axis frame moved" (cycle 9/10: HECA 10 000 m read airside 4,610 own-frame and 4,474 base-frame, and the whole gap was ONE instrument defect). A base-frame number is a FRAME claim, never a defect count; the frame is stamped into every report either way (`axis_frame`). Added 2026-08-07 (cycle 10) in place of the hand-built filtered sidecars the cycle-10 probe made and threw away. `--rows-json OUT.json` additionally ITEMISES every law-true row — family, role pair, side, magnitude, grade/cap, site in layout-local metres, lat/lon, way ids — which is what turns a class table into an attribution: a net class delta hides equal churn by construction (a class that gains 200 rows at one site and loses 18 at another reads as "+182"), and only the rows say WHICH rows and WHERE. It is the census's own `all_rows`, the same population every count in the report is taken from, so the dump and the counts beside it can never disagree — `tests/test_harness.py` asserts the dump's class tally IS the report's class table, its side split IS the report's, and the worst-N table is its prefix. With several patches you get one dump per patch (a single file would silently keep the last). Added 2026-08-07 (cycle 10) for the road-pair receiver-only round's +182 decomposition. `--sites` clusters those same rows into DEFECT SITES and reports the other headline: how many DISTINCT defects a patch carries (law-true and adjudicated), ROWS PER SITE — the AMPLIFICATION FACTOR — per-site worst |de| / step and worst grade excess, the families, role pairs and shape ids each site spans, its bbox + centroid lat/lon, and a SIM-VISIBILITY flag. Reach for it whenever a row total is about to be quoted as a defect count to a human: row counts AMPLIFY and site counts do not — one over-cap region on one apron mints hundreds of edge-granularity rows (HECA's way -12407 alone carries ~800; the road-feed round's 180 threshold-flip sites live on 19 shapes, 72 % of them on four aprons), so "thousands of defects" is a count of PAIRS THE LAW PRICED and differs from the number of things wrong with the surface by whatever the amplification happens to be on that patch. THE CLUSTERING RULE, printed with every table so a site count is never read without it: two rows join one site iff SAME LAW FAMILY and (shared way id OR shared canonical node), where a canonical node is the census's own weld tolerance (`LAW_TRUE_KNOBS['proximity_m']` = `check_grade.SHARED_VERTEX_TOL_M`, 0.5 m) applied to the rows' endpoints in layout-local metres — the law's own "these two vertices are one node" predicate, never a proximity semantic invented for a report; sites are the connected components (union-find), and no magnitude, role or geometry test takes part. `--site-visibility M` moves the visibility threshold (default 0.05 m of relief = silhouette-visible candidate); it is a REPORTING threshold and an assumption — nothing has measured it in the sim — never a law, and the law still adjudicates every row regardless. `--sites-json OUT.json` dumps every site with its full membership as row indices into the census's own magnitude-sorted order, so it joins a `--rows-json` dump by position. The sites PARTITION the census's own population — `census_one` REFUSES if they do not, and `tests/test_harness.py` §9 carries the known-answer twin (two hand-built sites, one joined by way id and one by weld, asserting count, membership, amplification and both visibility flags) plus the union-equals-`all_rows` lockstep. Added 2026-08-07 (cycle 10) for the owner's "why does the battery still read thousands of defects" question. **THE HEADLINE the section reports is ACTIONABLE SITES** — the MATERIALITY FLOOR (owner RULINGS 2026-08-07, "we don't need to be grading to less than 0.5m") adjudicated per site, since a site is the unit that sentence is about: 40 one-centimetre rows on one apron are one place owing 0.4 m of grading, not 40 defects. A site is actionable when its ADJUDICATED rows accumulate ≥ **0.5 m** of unlawful excess, OR one of them is a single step ≥ **0.15 m** or sits at ≥ **2× its own cap** (the SHARP GUARD — "we don't want any sharp bumps", the half a bare accumulation floor throws away), OR it touches the **RUNWAY FAMILY** (`runway` / `runway_crossing`), which is never floored because reg-derived precision governs there. Every constant is a named knob in `check_grade` (`MATERIALITY_FLOOR_M`, `MATERIALITY_SHARP_STEP_M`, `MATERIALITY_SHARP_GRADE_CAP_MULTIPLE`, `MATERIALITY_RUNWAY_FAMILY_ROLES`) citing the ruling, and all of them ride in every report beside the counts — the floor is PROVISIONAL and two site tables taken at two floors are not comparable. ACCUMULATION is `check_grade.row_excess_m` summed over the site's adjudicated rows only (a version-deferred or out-of-scope row is not a defect and may not fund one): the EXCESS, not the magnitude — a 3.2 m rise over 200 m of 1.5 %-capped taxiway is a 3.2 m magnitude and a 0.2 m excess. A family that prices a CAP rather than metres (`MATERIALITY_UNMEASURED_FAMILIES`, today `lateral_contiguity`, whose `de_m` is a bare grade difference over no span) funds nothing AND keeps its site actionable — a floor may only relax what it can measure. A site the floor takes out is REPORTED under the **`sub_floor`** label with its rows and worst |de| (counted-never-dropped, the `VERSION_DEFERRED_FAMILIES` / `disconnected_ring` convention), and actionable + sub-floor PARTITIONS the adjudicated sites — `census_one` REFUSES if it does not. Twins: `tests/test_harness.py` §10 (both sides of every constant, each guard half proven to fire ALONE, the runway exemption, the label locked to its register, the production refusal). Alongside it, ROLE-LESS FEATURE WAYS SIDE WITH THEIR HOST (lead ruling 2026-08-07): an `o4_feature` way with no `role` tag — `shape_interior_ring` / `gap_interior_ring` / `gap_drainage_spine` / `crown_spine`, 232 of them at HECA — used to fall through to the caller's default 1.5 % cap and to AIRSIDE whatever its host was; `check_grade.resolve_feature_hosts` (shared-node majority, ties on `layout.AUTHORITY_RANK`) and the drainage law's own parent selection now supply the role and side for REPORTING ONLY — the `role` tag is law input and is never written — and a row whose host's vertex set COVERS it is adjudicated `role_less_host_duplicate` (one geometry, one row set), reported under its own heading and never dropped. §10b twins. `--no-cache` / `--clear-cache` govern the CENSUS CACHE: the full report is memoised under `Ortho4XP/tmp/census_cache` (lane-local, gitignored, `$O4_CENSUS_CACHE_DIR`, REFUSED inside the shared data repo, and off inside pytest unless the root is named) keyed by the patch BODY sha (`build_airport.body_sha256`, the `tail -n +3` the frozen MANIFESTs speak) AND the whole-file sha (the census PRINTS the provenance stamp the body hash excludes), the sidecar BYTES (never an enumeration of its law keys — that is the wrapper defect), the run ledger's own code-tree hash (`run_with_ledger.code_tree_hash`, so a `check_grade.py` edit misses), `LAW_TRUE_KNOBS`, the `O4_*` environment and the option frame. A hit re-prints the stored report and re-writes the stored `--json` / `--rows-json` / `--sites-json` bytes, so it is the fresh output plus exactly ONE line — the `[CENSUS CACHE HIT] …` marker, first, immediately before the `=== CENSUS …` header, printed even under `--quiet`; a miss prints nothing. No number, family or law changes: memoisation, not measurement. Twin: `tests/test_census_cache.py`. The census also prints THE BUILD'S OWN AIRSIDE-SCOPED CERTIFICATE beside its counts (air7, RULINGS 2026-09-01l/r): the solve's law-graph verdict on the zero-airside beta bar, read verbatim from the sidecar's `airside_certificate` EVIDENCE key (readings per certificate site + the last-exit verdict; row-side partition, check_grade's quantization allowance imported) — a DIFFERENT instrument over a DIFFERENT population (law edges at exit vs emitted node pairs): agreement is corroboration, disagreement is a finding, and neither replaces the other. Twins: `tests/test_solve_certificate_instrument.py` TASK 6. **THE COCKPIT BLOCK IS PRINTED FIRST** (owner RULINGS 2026-09-12x/12y; `design-surface-spec.md` §31 (6), lane `v2cockpit`): before any other line the census classifies its OWN rows into CRITICAL MOTION (a `step`-class family over `[cockpit] motion_step_m` 0.05 m BETWEEN WELDED NEIGHBOURS — ends no farther apart than `emit.instrument.step_contact_tol_m`, the law's own weld spacing — where BOTH roles are ROLLED-ON — the runway family, the taxi family and the apron, derived from `precedence.toml`, never a literal list — plus the `grade_break` families the runway/taxi rate laws forbid, which carry no span test because a curve is long by definition), CRITICAL VISUAL (a WELDED `step`-class row over `visual_m` 0.5 m inside the airport boundary or within `approach_km` 5 km of a runway axis) and REPORT (everything else: every slope excess, every keep-out row, everything under a threshold, and everything beyond the view — §31 (4), "centimetres are not a goal"), each with its count, worst magnitude and worst COORDINATE. It is a CLASSIFICATION and never a measurement: no row is created, dropped or re-priced, and `cockpit_block` REFUSES if its three buckets do not add up to the population handed in. **THE SPAN RULE** (owner RULINGS 2026-09-12ad, round 2): a step-family row read SPANNED — ends farther apart than the weld spacing — is a SLOPE, not a discontinuity: it is grade, judged by its own cap, and is REPORT.  Round 1 classed a 2.69 m rise over 81 m of LEMD taxiway as critical motion and the block read 452; every one of those rows was spanned and LEMD now reads 0.  The REPORT line names what the rule moved — how many spanned rows would be over the motion threshold and how many over the visual one if they were welded — so the count is never folded into an anonymous total.  **THE CLIFF ESCAPE** (owner RULINGS 2026-09-12af, round 3) bounds it: a spanned row whose implied grade `|dz| / span` exceeds `[cockpit] cliff_grade` is a CUT or a RISE, not ground, and is judged as though it were welded, under its own reason `cliff` (on rolled-on pavement CRITICAL MOTION — no aircraft rolls a 1:3).  LEMD's `strip_seam_tear`, 8.27 m over 3.01 m = 275 %, is the row that made the rule.  The escape restores the BUCKET, never the threshold: a 0.4 m cliff is still under `visual_m` and still invisible.  `cliff_grade` holds a DOTTED LAW PATH (`emit.design.bank_slope`), never a number: the design surface's own 1:3 bank is already the line between "ground a pilot reads" and a wall, and `tables.cliff_grade` resolves it — change the bank and the cliff line follows, with no second copy to drift.  The loader refuses a path that does not name a grade in (0, 1] over the motion threshold.  **ROUND 4** (owner RULINGS 2026-09-12aj) repaired three READER defects the block's own output exposed, all in `check_grade.py`: the three RATE/ARC readers (`strip_arc`, `raoa`, `airside_no_step`'s §1.2 half) built rows with NO lat/lon, so `run_checks`'s fallback stamped each with the CENTROID OF ITS RING — 36 rows of LEMD apron `pav12` printed one coordinate 560 m from the wall they had found, and a whole round of attribution went to the wrong place; every rate row now carries its own pair midpoint (`_rate_row_site`, off a projection that gained an `inverse`). A rate row's `distance_m` published the HALF span `0.5*(dp+dn)` while its `de_m` spans `dp+dn`, so every implied grade read 2x (LEMD's five apron rows printed 0.37-0.46 and are really 0.20-0.23); it is now the full separation, and the allowance keeps the half span because that is the rate law's own averaging term. And the CLIFF ESCAPE now reaches EVERY family, not only `step` ones — LEMD's two sharpest readings of the same wall, a `within_shape` 81 % and a `cross_shape` 240 %, are class `grade` and could not be cliffs at all — while `row_roles` returns THE FACES ON EACH SIDE of the pair rather than the ring it was walked on: a within-shape pair has one ring for both ways, so the pad rim standing over the apron read `building|building` and the rolled-on test called it landside. `run_checks` indexes every node to the SENIOR face carrying it (`precedence.toml` authority order, an identity join on emitted coordinates at millimetre quantisation — never a proximity match) and stamps `role_a`/`role_b`; `row_roles` prefers them. A patch with no `boundary` role way (v2 emits none today) says so and the approach corridor alone decides view. IN VIEW BY APPROACH IS **THE APPROACH CORRIDOR** (owner RULINGS 2026-09-12al, §31 (2)): per runway END, `[cockpit] approach_km` beyond the threshold along the extended centreline and `approach_half_width_m` to each side, derived ONCE in `src/auto_patch_v2/law/approach_corridor.py` and read by the engine's mouth gate (`planar/structure_approach.FieldRegion`, §29 (1)) through the same class — the harness takes its axes from the emitted runway rings, the engine from the apt.dat thresholds. The first reading, "within `approach_km` of a runway axis", admitted the whole airport (at LEMD 4,318 of 4,408 rows, at HECA 8,122 of 37,364 — the corridor leaves 90 and 29,242 of them respectively behind) and is DELETED, not gated. Every family's class lives in `law/families.toml` (`cockpit = step|grade_break|grade|keepout`, REQUIRED — a new family without one does not load) and the four numbers in `law/emit.toml [cockpit]`. Twins: `tests/test_harness.py` §7. **§38 THE TILE SEAM (owner RULINGS 2026-09-13ah / 13am / 13an; lane `v2seampin`)** adds the two families the census had no instrument for. `seam_residual` prices every tile-seam band-edge vertex against ITS OWN tile's baked DEM sample — the value the solve PINNED, published per pin in the sidecar as `seam_pins` = `[lat, lon, dem_z]` (all of them since 13ah; the M3a sidecar published only the subset a soft preference happened to honour). Class `step`, so the cockpit rule gives it CRITICAL MOTION on the rolled-on roles and VISUAL elsewhere with no second threshold. It is the reader the SPLP berm needed: 106 rows, max 3.433 m, 31 of them CRITICAL MOTION on `runway|runway` (worst 0.629 m) — while `strip_seam_tear` read 0 over the same 3 m ridge. `bank_across_seam` prices any `bank_foot` node inside the band (`seam_half_width_m`, also published), class `keepout`: one node is the whole defect, because 13an measured a chain 0.0237 m off the meridian that Triangle4XP split 16,298 times against the unsplittable tile border. The bank foot is ROLE-LESS, so this family reads the `feature_out` channel of `_parse_osm`, not `ways` — a reader that walked `ways` prices nothing. Both are sidecar-declared like `eat_ceiling`: a patch with no key (v1's output, or a v2 patch predating §38) reports nothing and reads exactly as before. This is where the lane's seam-vertex/DEM probe was PROMOTED to (RULINGS `7e90032` second-use rule) — there is no separate script. Twins: `tests/test_harness.py` §38 (both directions of both families, at SPLP's own worst numbers, plus the cockpit classes read out of `families.toml`). |

| `Ortho4XP/tools/census_matrix.py` | You have MANY census JSONs — a multi-airport, multi-world round's arms — and the question is "did any cell's AIRSIDE count RISE against the arm we promised not to regress" (the Q4 gate) and "where did the change land". Lays the arms out as one table (lawtrue / adjudicated / airside / groundside per cell), applies a stated per-cell airside CEILING (`--gate ARM`, default the first census listed, or `--gate-json FILE` for a recorded frame of record), prints the arm-vs-arm delta and, with `--bands`, the census's magnitude bands. **It measures nothing and derives no number** — every value is read verbatim from a `harness/census.py --json` artifact; a reporter that recomputes a defect count is the census-wrapper defect. Equality PASSES the gate ("may not rise"); a cell with no ceiling is reported as ungated, never as a pass. Promoted 2026-08-06 from `tmp/c8fin/mx.py` on its second use (c9feed) — promote-on-reuse; the lane copy hard-coded one round's frame as a module constant. Twin: `tests/test_census_matrix.py`. |

| `Ortho4XP/tools/census_rows_diff.py` | You have TWO `harness/census.py --rows-json` dumps (a control arm and an arm under test) and the question is WHICH rows moved, not how many. A class delta hides equal churn by construction — 200 new and 182 gone read as "+18" — and the zero-new-adjudicated-airside bar is a claim about ROWS, so it needs a row-level reader. Joins the two dumps in three labelled tiers: EXACT (same family / role pair / side, both endpoints identical to the millimetre in the patch's own layout-local metre frame), MOVED (same class, nearest surviving partner within `--tol`, default 0.50 m, each partner used once — an INFERENCE, labelled one everywhere, and quoting two tolerances is how you show the join is not doing the work), and NEW / GONE (no partner — the rows an attribution owes a mechanism for). **It derives no law and measures nothing**: every row is read verbatim out of a census dump, the census staying the only instrument that produces defect counts. REFUSES a join across different `law_true_knobs` or a different axis frame (two dumps read under different law are not one population), a class-level census JSON, and a truncated dump. `--side` / `--family` filter the REPORT, never the join. Twin: `tests/test_census_rows_diff.py` (the four tiers on a hand-built scene, the tolerance knob both ways, class isolation, endpoint-order invariance, partner-used-once, nearest-wins, exact-beats-near, every refusal). |

| `Ortho4XP/tools/pad_span_census.py` | The question is DOES THIS UNIT'S OWN DATUM FIT ITS BODIES' PADS — *how far apart do the emitted `building` pads one FOOTPRINT UNIT stands on actually stand?* — the single number owner RULINGS 2026-09-14c item 1 is accepted or refused on (spec `object-placement-spec.md` §16g (1)/(7)). No other instrument asks it: `harness/census.py` prices PAIRS OF VALUES, so an object seated 23.70 m above its own pad breaks no grade law and reports ZERO rows; `obj8_split_report.py` prints a body's anchor and its own ground but never asks whether the bodies sharing ONE unit's datum stand on pads that disagree; `role_overlap_read.py` is an AREA sweep and `role_edge_census.py` a boundary-length one. This is the unit-vs-pad reading: per unit, the `building` pads its bodies' FEET fall inside, how many bodies it holds, and the SPAN of those pads' planes, largest first. **It measures no law and counts no defects** — the pads are the emitted design surface's own `building` faces at `median(z)` over the ring, which is the plane `footprint_unit` reads through `anchor_rule.pad_plurality`, and the body→part join is the PART ID, never a proximity match (memory `canonical-identity-join`). `--over` (default 1.0 m) is the listing floor 14g stated its bar in, not a threshold with any standing. It takes either `o4_v2_placement_<ICAO>.json` or an `obj8_split_report --json` dump — both carry the same `splits` body records. Measured basis (scout `v2heca331` on the owner's 1.0.331 HECA): 17 units whose pads span > 1 m over 1,363 bodies, `fu:38:20` alone 978 bodies on 136 pads spanning 34.8 m — the unit chained on PART BOXES, and its DECK member then gave 96.20 to 1,509 bodies. Promoted 2026-09-14 from that scout's scratchpad `padspan.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse) — the 14g attribution, then lane `v2connector` round 3's before/after. Several patches are reported separately; quote it on identical options. Twin: `tests/test_pad_span_census.py` (the span IS the unit's own pads, a non-`building` face is not a pad, a unit on one pad is not a row, a body with no `unit_of` is not counted, the floor both ways, the CLI's JSON IS the library result, and this index row). |

| `Ortho4XP/tools/role_edge_census.py` | The question is WHAT SHARES AN EDGE WITH WHAT — *how many metres of a groundside shape's boundary run along AIRSIDE PAVEMENT in an emitted patch* — the single number owner RULINGS 2026-09-12c is accepted or refused on ("shapeID 81 ... cannot be groundside because it shares a long edge with an apron. Something can only be groundside if it has no connection to airside other than a service road"). No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a lot welded flat along 828 m of apron breaks no grade law and reports ZERO rows; `role_overlap_read.py` asks AREA overlap (what STANDS on what), which is 0 for two faces that merely share a boundary; `osm_site.py` answers one coordinate. This is the BOUNDARY-LENGTH sweep: per groundside shape its area, perimeter, inscribed radius (area / perimeter) and the metres shared with airside pavement / with `service_road`+`service_junction` / with `building`, largest first; `--min-m` (§27's `[lot] airside_edge_min_m`, default 10) and `--min-radius` (its sliver floor, default 1.0 m) split the population into SUBSTANTIVE, SLIVER and LOT-class. **It measures no law and counts no defects** — geometry, roles and the groundside partition come from the harness library (`check_grade._parse_osm`, `effective_role`, `_GROUNDSIDE_ROLES`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. Edges are joined on NODE IDENTITY — a shared edge is two shapes listing the same node pair, exactly what the planar weld produces — never a proximity match (memory `canonical-identity-join`). Measured basis (shipped 1.0.320 LEMD): 175 groundside shapes, 105 sharing >= 10 m with airside pavement, 71 substantive (182,604 m², 34 slivers excluded), of which 13 LOT-class / 145,262 m² — the owner's shapeID 81 (`pav137`) 140.2 m of its 270.9 m perimeter, `pav125` 828.4 m. Promoted 2026-09-12 from the `v2lemd320t` scout's `census_gs.py` on its second use (RULINGS `7e90032`). Several patches are reported separately — the arm-to-arm read; quote it on identical options. **`--pad-frontage`** is the SECOND question on the same geometry and the same joins (added 2026-09-12, lane `v2frontage`, spec §28): *pad -> neighbour -> shared edge m -> STEP m*, the read owner RULINGS 2026-09-11ai-1 -> 2026-09-12r ("grade frontages only") is accepted on. No other instrument answers it either: the harness census FORGIVES a declared terrace across a shape joint (`terrace_joints_ll`), so a car park standing 3 m above the terminal it fronts prices ZERO rows — and at LEMD the owner's +3.03 m is not even a declared joint (the patch carries 4, none of them `building4`'s). Per `building` shape: each groundside neighbour (`groundside_pavement` / `service_road` / `service_junction`, `parking_lot` by its class tag), the metres of edge they SHARE by node identity, the facing-vertex pairs within `--near` (default 2.0 m) and the largest and mean SIGNED step, neighbour minus pad. The proximity read is not a shortcut: the pad-frontage relation is a proximity relation in the engine too (`[design] pad_frontage_m` 3.0, owner RULINGS 2026-09-10ax (1)) and `building4` / `pav124` share not one node while standing 0.71-1.50 m apart. `--min-step` (default 0.05 m) is the listing floor. Measured basis (shipped 1.0.321 LEMD): ONE pad with a groundside step >= 0.10 m — `building4`, `pav124` +3.03 / +2.67 and `route6` +0.38. Twin: `tests/test_role_edge_census.py` (the shared edge IS the node-identity join, the airside-pavement set excludes `building`, service-road metres are reported apart, the sliver split, prices-no-law, the pad-frontage step across a proximity gap and across a welded edge, and this index row). |

| `Ortho4XP/tools/void_census.py` | The question is about ENCLAVE TOPOLOGY on a shipped patch: which regions does airside pavement completely surround, which of them have a tunnel/bridge ESCAPE, and what is sitting inside them. Reads back exactly the geometry the enclave region law computes (`auto_patch/enclaves.py`). `--union` selects WHICH union, because the law has two and they answer different questions: `surround` (default) is airside ∪ BUILDINGS, the set published as `layout.airside_enclaves` and the CLASSIFIER's question ("is this ground airside-interior?"); `pavement` is airside pavement only, which is the GAP LAW's own detection union and therefore the scope of the adjacent-ground BAND KEEP-OUT (`enclaves.enclave_band_keepout_union`). The distinction is load-bearing and was measured: buildings standing in HECA's 3.4 km² infield subdivide it into pocket-width components in the `surround` union while the gap law holds it as ONE wide region and declines it on width, so scoping the keep-out by the wrong union deleted 152,734 m² of Annex 14 §3.4.11-13 graded strip. The union is stamped into every report — two unions are two populations. Reports per void its area, perimeter, minimum-rotated-rect SHORT SIDE and POCKET flag (short side ≤ the gap law's own `GAP_FILL_MAX_WIDTH_M`, the class the ruled gap ring + spine treatment covers; under `--union pavement` that flag IS the band keep-out's membership test), the escapes, whether the gap treatment emitted a face there, the per-role/ref contents, the retaining-wall inventory with way ids, and the BARE GROUND remainder carrying no shape at all — the 87.6 % that made the shape-scoped G-ENCLAVE predicate structurally blind. `--bands` adds the ADJACENT-GROUND inventory beside the topology: band and `adjacent_ground_wall` way counts and areas, split by where each way SITS — inside a POCKET no-escape void (the keep-out's own territory), inside another no-escape void, or outside every void — each way in exactly one column, the columns summing to the total. Reach for it whenever a band-area delta is about to be quoted: the total alone cannot tell a keep-out that removed band inside pocket voids from one that also took ground nothing owns, and that is precisely the failure the ratified scoping fixes. **It measures no law and derives no defect count**: grade defects come from `harness/census.py` and nowhere else, and the role vocabulary plus the escape set are IMPORTED from `auto_patch.enclaves` rather than re-typed (the census-wrapper precedent). Parses with the harness library's own reader (`check_grade._parse_osm`) in the builder's anchor frame from the axes sidecar, so this tool and the census read one geometry; without a sidecar the topology is unchanged and lat/lon are simply not reported. FRAME: emitted geometry is post-decimation and post `_separate_groundside_from_airside`, so a void reads slightly larger than the in-build region and a groundside shape inside it reads pulled back from the rim; a real-DEM patch is never comparable with a constant-DEM one. The in-build predicate also honours the `is_bridge` SHAPE FLAG, which `to_osm` does not emit — so this reader sees the four escape ROLES and no more (stated by the tool itself). Promoted 2026-08-07 from `tmp/enclave_attrib/void_census.py` on its second use (promote-on-reuse); the lane copy carried its own patch reader and a hand-typed role list. Twin: `tests/test_void_census.py`. |

| `Ortho4XP/tools/seat_feet_census.py` | THE DRAPE RESIDUAL AT EVERY PLACEMENT'S FEET (RULINGS 2026-09-09ac (3); the placement reading 11e (3), spec §7/§9) — `--placement-plan o4_v2_placement_<ICAO>.json` with `--mesh` (a built mesh) or `--graded` (the emitted design surface, for a dry run with no tile built): per placement of the plan's own rows, `surface(foot) − (surface(anchor) + y_foot)`, the |Δ| histogram (<0.3 / 0.3-1 / 1-3 / >3 m), the same by class, the worst N with lat/lon, and §13's elevated-body / footless-carrier bars. Feet are read from the AUTHORED pack (`.anchor_bak` when one exists). THE SEAT-RESULT MODE IS DELETED (owner RULINGS 2026-09-12s, spec §8) — the name is kept because the INDEX row, `obj8_split_report` and the twins address it by it. Writes nothing to the pack. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. CRITICAL MOTION is named as an instrument limit rather than printed as a zero HERE: §17's motion reading needs the graded face ROLE under each foot, and this tool hands the block none — `obj8_split_report.py` is the entry that takes it (owner RULINGS 2026-09-12am (2), lane `v2objmotion`). §16e (owner RULINGS 2026-09-13k, lane `v2othhdatums`): `--placement-plan --mesh` WAS BROKEN — it passed its bbox as `(lat, lon)` to `MeshElevationSampler`, which takes `(min_lon, min_lat, max_lon, max_lat)`, so at OTHH it asked for a box at lon 25.2 / lat 51.6 and the sampler raised `no mesh triangles inside ... — wrong tile?`; the one place the two orders meet is now `plan_bounds()` and a twin holds it end to end over the sampler's own mesh fixture. The report also prints `§16e bodies on a DATUM` (a crest plate / a deck top) as its own class and EXCLUDES them from §13's `elevated bodies as own files` bar: a datum body's `y_zero` is +5 … +10 m by construction, and counting it there reported the law as the defect (OTHH 0 -> 10 -> 0 with the class printed apart). §16e (3) (Fable 2026-09-13, RULINGS 2026-09-13v, lane `v2bridgecontact`): the report also prints THE BRIDGE FAMILY block (`airport/bridge_family.census_bridges` / `census_bridges_lines`, re-exported through `placement_census`, the same call `obj8_split_report` makes over the same plan shape) — per `Bridge_NN` the deck's own body's world DECK TOP against the land under that bridge's own written geometry (`|deck top - highest land|`, bar `[cockpit] visual_m` 0.5 m), the PER-PLACEMENT zero spread (`max - min` of `surface_z - y_zero` over one placement's bodies; `Bridge_02_CLUTTER_007` is six piers of ONE solid), the CROSS-BRIDGE carriers (a body whose `merged_into` names a file of another bridge, bar 0) and how many bodies publish `bridge_of` and agree with the resource's own tag. The `Bridge_NN` axis is the CENSUS's, never the law's — §16e (3) exists because the name does not name a bridge — so the agreement count is the instrument's own check on the derived relation. Measured on the app's 1.0.326 OTHH frame: `Bridge_01` deck top 3.23 -> 3.96 and `Bridge_04`/`Bridge_05` KEPT -> 3.96 (all three |deck top - land| 0.00, PASS), cross-bridge carriers 2 (unchanged — the bind and the filter are refuted and deleted, see `bridge_family`'s module doc). |

| `census_lockstep.py` | `harness/census.py` (law-true + bare frames, class table) |

## Tool: site_read

| `Ortho4XP/tools/site_read.py` | You have a coordinate from an owner's sim read and the question is WHAT THE OBJECT STAGE MADE OF IT — not what the OSM patch says there (`osm_site.py`, the emitted ways) and not one law's defect count (`harness/census.py`). Three products of ONE build, read at ONE point in one process: the emitted DESIGN SURFACE's faces containing or near it (role, ref, side, z min/med/max, node count — a CONTAINING face reads 0.0 m, never the distance to its nearest vertex, which is `osm_site --at`'s own trap); the DSF ROWS standing on it (`OBJECT` / `OBJECT_MSL` / `OBJECT_AGL` with the resource and, where it has one, the written elevation — `None` for a plain `OBJECT`, never 0.0); and the PLAN BODIES whose plan box reaches it, each with its §6 class, its FOOTPRINT UNIT, its surface z and zero and the stage's own ANCHOR REASON verbatim, which is the line that says WHY a body is where the owner saw it. `--patch-dir DIR` resolves `<ICAO>.graded.json` and `o4_v2_placement_<ICAO>.json` by glob (an `obj8_split_report --json` dump works as `--plan`: the same `splits` records), `--dsf-dump` takes a DSFTool TEXT dump — pass the PRISTINE `<dsf>.anchor_bak...text` (`dsf_write.pristine_dsf_path`) when you want the pack as INSTALLED rather than as this repo last wrote it. `--show`, `--max`, `--json`. **It measures nothing and derives no law**: every value is read verbatim out of a product and nothing is written. Promoted 2026-09-14 (RULINGS `7e90032`, promote-on-reuse) from the scratchpad reader of the 14g HECA attribution, re-written for the 14bl LEMD one (scouts `v2heca331` / `v2lemd336o`) and used a THIRD time by lane `v2leafframe` — three copies of one question, already drifted in their hard-coded LEMD paths. Twin: `tests/auto_patch_v2/test_v2leafframe.py`. |

| `Ortho4XP/tools/arm_site_read.py` | The question is about a PLACE across two arms — "is the wall at 35.2077303,-80.9290869 still there, and did anything near it get worse?" — which an A/B leaves open: `census.py --rows-json` itemises rows and `census_rows_diff.py` joins two dumps class by class, but neither can be asked about a coordinate, and `osm_site.py` reads geometry without law rows or pad seats. This is the join: per named `--site`, per arm, the law-true rows within `--radius` with their worst grade and |de|; with `--seats`, the BUILDING PAD seats that moved between the arms — the channel this repo's HECA airside attribution ran through (a pad seat welds into the apron ring, so a seat that moves moves airside; measured 2026-08-12b: 92 of 215 pads, median 0.32 m, and building211's +0.88 m carried +203 apron rows). **It measures no law and counts no defects**: rows are read verbatim out of census `--rows-json` dumps and geometry/altitudes through the harness library's own `check_grade._parse_osm`, so this tool and the census read one file one way; a missing input reports SKIPPED, never zero. FRAMES, both printed: rows are located by the census's own row lat/lon, which for a within-shape pair is the PAIR's position (a 400 m apron chord's row sits far from either endpoint's geometry), so a radius selects rows near the PAIR, not shapes touching the site; seats join by the building's `ref` tag, never by way id or shapeID (both arm-dependent). Promoted 2026-08-12b from the service-corridor lane's `measure_arms.py` on its SECOND use — the named-site table and then the airside attribution. `--welds` (added 2026-08-12c, the corridor-joins round's ruling-4(a) instrument) answers the other question a place can be asked — IS THIS SEAM JOINED? Per site, per arm: the node ids SHARED between the road family (`check_grade._ROAD_FAMILY_ROLES`, read from the census library) and the airside ways, the max |Δalt| two ways carry at a shared node (0.00 is the construction — production values sit on the NODE, so a weld is single-valued; the delta is the torn-weld guard for way-valued rings), the NEAREST UNWELDED approach when nothing is shared (0.999 m at both KCLT mouths, against a 0.5 m weld tolerance), and the `retaining_wall` ways standing at the site with their ids. `--profile` / `--line` (added 2026-08-25, the HECA apron round-2 acceptance) answer the THIRD question a place can be asked — WHAT SHAPE IS THE SURFACE HERE? `--profile` walks every ring of `--profile-roles` (default `apron,graded_strip`) reaching a site and reports its worst consecutive EDGE and its RIPPLE AMPLITUDE, the peak-to-peak inside a 50 m run ALONG THE RING — the same window `apron_drape_read` calls `amp50`, so the two tools spell the ripple one way. `--line NAME=LAT,LON:LAT,LON` orders every emitted vertex in a corridor about an owner-named segment by its station along it, with the step between consecutive stations: the reading an acceptance written as "no unlawful step along the owner line" is stated in, AND the reading that shows a NODELESS VOID, because there an EMPTY STATION LIST IS ITSELF THE FINDING (a region with no emitted vertices contributes no census row however wrong its surface is — the blind spot `nodeless_interiors` counts). Neither prices a law; quote them ARM TO ARM on identical options, never as a verdict. Reach for it whenever an acceptance claim is about a join: **row absence cannot answer it** — a census row exists only between PAIRED geometry, so an unwelded road↔taxiway seam is silent in every census, which is exactly how two 1.0.244 acceptance claims passed over a gap no node could bridge. Twin: `tests/test_corridor_axis_coverage.py`.  **`--behind NAME=LAT,LON:LAT,LON` is the WALL scope** (added 2026-08-29, scorer-v2 round, spec `scorer-v2-class-boundary-spec.md`): the owner states a wall as two coordinates and asks that no airside pavement cross it — `--line` answers what the emitted elevation does ALONG it and `osm_site --line` answers what covers each station ON it, but neither answers the quantitative half, the SQUARE METRES of airside-role pavement sitting on the groundside, which is the number a boundary-cut round moves and therefore the number its acceptance is written in. Per crossing ring it reports the area behind, the node split either side and each side's altitude range — the shape of a wall buried inside one apron (HECA apron 584: 48 nodes at 97.22-104.69 m in front, 95 at 90.77-102.71 m behind). TWO FRAME RULES, both load-bearing: the band is the line's OWN SPAN by `--behind-depth-m` (default 150 m) deep, never a half-plane — unbounded, the far side sweeps in the whole airport and reports 634,371 m² where the local answer is 25,900 (measured at HECA); and the GROUNDSIDE side is decided by the patch — the side carrying less airside pavement — so reversing the two coordinates cannot change the answer and a caller cannot pick it. The closed-ring repeat is dropped before the node split (counting it double reports one extra node on whichever side the ring starts). It prices no law and counts no defects. **THE SEAT JOIN IS NOT FREE (2026-08-31, the buildings round).** `building{N}` is an ORDINAL identifier, so an arm that ADDS or DROPS a pad renumbers every later one and the ref join reports the RENUMBERING as seat motion: measured on the buildings-round HECA arms (pad count 175 -> 176) the ref join said 85 of 174 pads moved, median 2.72 m, max 33.65 m, where the population had barely moved. The tool now DETECTS it — a common ref whose pad centroid is more than `--seat-radius` (15 m) away is named as RENUMBERED, with the advice to re-run — and `--seat-join location` pairs pads by centroid instead (closest pair first, each pad used once; a pad with no partner within the radius is reported as added/dropped, NEVER as a move), which on the same arms reads 28 of 174 moved, median 0.07 m, max 2.32 m. Quote a pad-population round's seat movements under the location join. |

## Tool: role_overlap_read

| `Ortho4XP/tools/role_overlap_read.py` | The question is WHAT STANDS ON WHAT — *how many square metres of one emitted role/ref class lie on another class's footprint* — which is the single number a ruling of the form "the gap-fill spine must STOP at groundside pavement" (RULINGS 2026-08-30 ruling 4) is accepted or refused on. No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a face lying flat on a lot breaks no grade law and reports ZERO rows; `osm_site.py` answers one coordinate and `arm_site_read.py` one named place; `void_census.py` asks enclave TOPOLOGY; `lattice_overlap_read.py` asks CONTAINMENT of the two role-less membrane classes by LENGTH. This is the AREA sweep: `--over ROLE[:REF] --on ROLE[:REF],...` reports the populations, how many OVER ways stand on the ON union, the total m², and per stacked way its own area, the area over, the fraction and the ON shapes it stands on, largest first. **It measures no law and counts no defects** — geometry, the metre frame about the sidecar's own anchor and the role-carrying rings come from the harness library (`check_grade._parse_osm` / `_ll_to_m_factory`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. A patch with NO `.axes.json` sidecar is REFUSED (no anchor, no metre frame — an area in the wrong frame looks right and is not). `--min-area` (default 1.0 m²) is emit rounding, not a law threshold. Measured basis (HECA round 6b/6c): on the round-6b closing arm `graded_strip:gap_fill_spine` over `groundside_pavement` = 18 strips / 26,780 m², two faces carrying 24,288 m² of it (3190 over lot 2813 by 13,657 m², 70 %; 3192 over 2814 by 10,631 m², 63 %), while the same read over `service_road,service_junction` — 34 strips / 25,073 m² — said the annulus class was not one ruling's alone. Promoted 2026-08-30 from the HECA round-6b lane's scratchpad on its second use (RULINGS `7e90032`). `--pad M` grows the ON union before the read and `--beyond` reports the COMPLEMENT — the OVER ways that do NOT reach it, totalled and split by ref: the OWNERSHIP read RULINGS 31b is stated in ("within SERVICE_ROAD_PAVEMENT_NEAR_M of aircraft pavement"), which is how Batch 4a priced HECA's far road-family population off the merged-main control (`service_junction` beyond 25 m of the airside roles: 1,526 of 1,777 rings / 473,248 m², of which 1,325 ref-less / 435,882 m²). `--site LAT,LON` (repeatable) answers a named place in the OVER class's own terms — which way covers it, its ref and area, and the distance from both point and ring to the ON class. Several patches are reported separately — the arm-to-arm read; quote it on identical options. **`--contains` is the CONTAINMENT CENSUS and it is a DIFFERENT FRAME** (2026-09-13, lane `v2zonehole`, spec §41 (1)): the overlap sweep above is a SOLID-frame question and reads 0 m² here BY CONSTRUCTION — the arrangement is a partition, so a face enclosed by another sits in its HOLE and never overlaps its solid. `--contains` asks whether a pavement face lies inside another pavement face's EXTERIOR RING (`--min-frac`, default 0.95 = §41 (1)'s own floor, the one spelling of `planar.overlay.ENCLOSED_MIN_FRAC` outside the engine), and reports per row the inner face and its area, the host, the RING fraction, the SOLID fraction beside it (which is what says the two readings are not the same question), the shared-edge length and the distance to the host's solid — a face that TOUCHES its host is a NOTCH cut into a body (absorbed by `planar.overlay.absorb_enclosed_pavement`), one that does not is an ISLAND in the middle of a taxiway loop (left alone). Measured basis (the owner's 1.0.329 HECA patch): 39 of 370 pavement faces contained, 65,772 m², every one at solid fraction 0.000, 33 notches / 6 islands — `cross_connector:pav77` 896 m² in `primary_parallel:pav73` is the owner's dip site (RULINGS 2026-09-13co item 2). **THE ANCHOR REPAIR** (same lane): the read used to do `side["anchor"]` and died `KeyError: 'anchor'` on every v2 patch — v2's `SIDECAR_KEYS` publishes no anchor, deliberately, and the harness library itself falls back to the MEAN OF NODES, which is the frame the census reads the same patch in. The sidecar is still REQUIRED; the anchor is used when the patch carries one; the frame in force is printed on every report and carried in the JSON (`frame`). **`--slivers` and `--hole-rings` are the FOURTH and FIFTH questions, and both are WIDTH questions** (2026-09-14, lane `v2slivers`, spec §41 (4) / RULINGS 2026-09-14g items 4/5): the reads above ask what stands on, or inside, what — neither asks whether a shape is BIG ENOUGH TO CARRY LAW, which is what a zone strip that mints a hump and a hole ring that ships across a service road have in common. `--slivers` reports every `graded_strip` face under `--strip-min-area` (50 m², `emit.terrace.strip_min_m2`) or narrower than `--strip-min-width` (3.0 m, `strip_min_width_m`) with its area, inscribed width, elevation span and the pavement face it borders longest — the HOST `planar.overlay.dissolve_sliver_zones` unions it into. `--hole-rings` reports every emitted `gap_interior_ring` way with the fraction of its area the faces INSIDE it cover (`--cover-eps`, `emit.terrace.hole_cover_eps`), its inscribed width, and a verdict: `covered` (a duplicate ring), `hairline` (narrower than `strip_min_width_m`: it can carry no transition) or `void` (a real hole, which KEEPS its ring). THE WIDTH IS THE MAXIMUM INSCRIBED CIRCLE's DIAMETER, imported from the engine's own `planar.overlay.inscribed_width_m` and never re-spelled: `2 A / P` is a mean-width proxy and over-counted HECA's narrow zone faces 42 → 153 (the ruling's own measurement). Measured basis (the owner's 1.0.331 HECA patch, mean-of-nodes frame): 338 `graded_strip` faces / 2,895,389 m², of which 57 slivers / 1,647 m² (51 under 50 m², 42 under 3 m) — shape 1035 `adjacent_ground:taxi:E:zone1#38`, 15.7 m², 2.16 m, z 105.86–106.01 against a taxiway at 104.4, host `cross_connector:pav115`, the owner's hump (RULINGS 2026-09-14c item 4); and 57 `gap_interior_ring` rings / 926,251 m², 11 covered ≥ 98 %, 5 hairline, 41 real voids — way −10231, 29.5 m², 1.60 m wide, 92.3 % covered, the ring that shipped across `service_road:route4`. Both price no law and count no defects. Twin: `tests/test_role_overlap_read.py` (the area IS the intersection, the ROLE:REF selector is exact, the floor both ways, prices-no-law, the no-sidecar refusal, the `--pad`/`--beyond` complement, the `--site` read, the inscribed width agreeing with the engine's and the proxy disagreeing, the tool's three §41 (4) constants being the law table's, the sliver read naming the host, the hole read's cover fraction / width / three verdicts, the three reads refusing to run two at a time, and this index row) and `tests/auto_patch_v2/test_v2zonehole.py` (the anchor-less sidecar is not a crash, the containment census's ring-vs-solid frames, and that the two spellings of 0.95 agree). |

| `Ortho4XP/tools/role_overlap_read.py` | The question is WHAT STANDS ON WHAT — *how many square metres of one emitted role/ref class lie on another class's footprint* — which is the single number a ruling of the form "the gap-fill spine must STOP at groundside pavement" (RULINGS 2026-08-30 ruling 4) is accepted or refused on. No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a face lying flat on a lot breaks no grade law and reports ZERO rows; `osm_site.py` answers one coordinate and `arm_site_read.py` one named place; `void_census.py` asks enclave TOPOLOGY; `lattice_overlap_read.py` asks CONTAINMENT of the two role-less membrane classes by LENGTH. This is the AREA sweep: `--over ROLE[:REF] --on ROLE[:REF],...` reports the populations, how many OVER ways stand on the ON union, the total m², and per stacked way its own area, the area over, the fraction and the ON shapes it stands on, largest first. **It measures no law and counts no defects** — geometry, the metre frame about the sidecar's own anchor and the role-carrying rings come from the harness library (`check_grade._parse_osm` / `_ll_to_m_factory`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. A patch with NO `.axes.json` sidecar is REFUSED (no anchor, no metre frame — an area in the wrong frame looks right and is not). `--min-area` (default 1.0 m²) is emit rounding, not a law threshold. Measured basis (HECA round 6b/6c): on the round-6b closing arm `graded_strip:gap_fill_spine` over `groundside_pavement` = 18 strips / 26,780 m², two faces carrying 24,288 m² of it (3190 over lot 2813 by 13,657 m², 70 %; 3192 over 2814 by 10,631 m², 63 %), while the same read over `service_road,service_junction` — 34 strips / 25,073 m² — said the annulus class was not one ruling's alone. Promoted 2026-08-30 from the HECA round-6b lane's scratchpad on its second use (RULINGS `7e90032`). Several patches are reported separately — the arm-to-arm read; quote it on identical options. Twin: `tests/test_role_overlap_read.py` (the area IS the intersection, the ROLE:REF selector is exact, the floor both ways, prices-no-law, the no-sidecar refusal, and this index row). |

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
LEMD  capture  base da8e5d7f   lane v2lemdstruct2    2026-09-15T08:29:03  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/cap/LEMD.pkl  — fresh LEMD v2_solve_replay capture on claude/v2lemdstruct2, base main da8e5d7f (20,608 vertices, 1,024 faces, 286 s; clusters 7776, pack partition 115 s) — the 15e items 5/7 round (33 (5), 34 (11), 34 (5) (b))
LEMD  patch    base da8e5d7f   lane v2lemdstruct2    2026-09-15T09:14:50  /Users/noah/XPTerrainBuilder/.claude/worktrees/v2lemdstruct2/Ortho4XP/Patches/+40-010/+40-004/LEMD_auto.patch.osm  — lane v2lemdstruct2 CLOSING LEMD tile build (tag v2lemdstruct2, branch claude/v2lemdstruct2 @ 5ed9b083, base main da8e5d7f): rc 0, 551.8 s (vector 491.5 + mesh 59.5), solve optimal 40.4 s, ledger tree 3e3e13880a2a. WARNING: the harness flagged the run CONTAMINATED — it rewrote OSM_data/+40-010/+40-004/+40-004_big_roads.osm.bz2 (2,197,226 -> 2,199,670 bytes), the v2roadtags ROAD_CACHE_TAG_SCHEMA bump merged into main the same morning; the matched REPLAY pair off the registered capture is unaffected. 33 (5): item-5 mouth floor 599.25 -> 597.09 under a rim at 602.16 = 5.07 m vs bore_datum_m 5.10. 34 (5) (b): item-7 trench mouth 12.77/15.46 m -> 31.06/33.43 m from the owner node, beyond the 19.0 m code-E strip; zone1 intact at 18.15 m. Census: ramp_in_strip 11 -> 8 (all runway-strip), wall_in_runway_strip 10 -> 6, tunnel_mouth_canonical 32 -> 28
LEMD  mesh     base da8e5d7f   lane v2lemdstruct2    2026-09-15T09:14:50  /tmp/harness/tile_v2lemdstruct2/Data+40-004.mesh  — lane v2lemdstruct2 CLOSING LEMD tile build (tag v2lemdstruct2, branch claude/v2lemdstruct2 @ 5ed9b083, base main da8e5d7f): rc 0, 551.8 s (vector 491.5 + mesh 59.5), solve optimal 40.4 s, ledger tree 3e3e13880a2a. WARNING: the harness flagged the run CONTAMINATED — it rewrote OSM_data/+40-010/+40-004/+40-004_big_roads.osm.bz2 (2,197,226 -> 2,199,670 bytes), the v2roadtags ROAD_CACHE_TAG_SCHEMA bump merged into main the same morning; the matched REPLAY pair off the registered capture is unaffected. 33 (5): item-5 mouth floor 599.25 -> 597.09 under a rim at 602.16 = 5.07 m vs bore_datum_m 5.10. 34 (5) (b): item-7 trench mouth 12.77/15.46 m -> 31.06/33.43 m from the owner node, beyond the 19.0 m code-E strip; zone1 intact at 18.15 m. Census: ramp_in_strip 11 -> 8 (all runway-strip), wall_in_runway_strip 10 -> 6, tunnel_mouth_canonical 32 -> 28
LEMD  patch    base da8e5d7f   lane v2lemdstruct2    2026-09-15T09:14:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/base_emit/LEMD_auto.patch.osm  — BASE ARM of the matched replay pair (v2_solve_replay --replay on the registered da8e5d7f capture, base tree, --emit): LAW-TRUE 5688 / ADJUDICATED 1341, ramp_in_strip 11, strip_transverse worst 5.589 m, within_shape 3397, tunnel_mouth_canonical 32; item-5 floor 599.25 under rim 602.16 (2.91 m); item-7 ramp at 15.46 m, 572.02-572.42 under a 577.84 kerb
LEMD  patch    base da8e5d7f   lane v2lemdstruct2    2026-09-15T09:14:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/a4_emit/LEMD_auto.patch.osm  — ARM of the matched replay pair (--from planar, 33 (5) + 34 (5) (b)): LAW-TRUE 5756 / ADJUDICATED 1404, ramp_in_strip 8, strip_transverse worst 13.872 m, within_shape 3464, tunnel_mouth_canonical 28
LEMD  capture  base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/LEMD.on3.pkl  — LEMD PADS-ON capture (v2_solve_replay --capture --placement pad_from_cluster=true --placement pad_airside_clip=true, 219 s, 20,473 vertices / 1,011 faces, guard shared repo UNCHANGED) - the FIRST LEMD capture carrying the derived cluster pads; the T4 cluster unit:25#843 (421,940 m2, 761 walled, PKT4 a member) mints ONE pad containing the owner's garage at 40.4892214,-3.5944287. Its matched OFF arm is cap/LEMD.off3.pkl
LEMD  capture  base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/LEMD.off3.pkl  — LEMD PADS-OFF capture (--placement pad_from_cluster=false pad_airside_clip=false = the shipped law), 226 s, 21,348 vertices / 1,058 faces, guard UNCHANGED - the BASE ARM of the v2padqp LEMD pair; reproduces 15h's garage reading (nearest pad building12 55.3 m away, median 616.35)
LEMD  patch    base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /tmp/harness/v2padqpLEMD2.osm  — CLOSING BUILD v2padqpLEMD2 with BOTH §16g (10) pad keys ARMED (the measurement arm; the branch SHIPS them false): rc 0, 346.3 s, ways 1048, nodes 20304, status optimal, body_sha e5d30cf207a8, artifact ledger 50546224d866, v2-verify 1,633 rows, '[harness] shared repo UNCHANGED by this build (full-surface before/after snapshot)'. The owner's T4 garage at 40.4892214,-3.5944287 is INSIDE pad building45 (93-node face, every face of the ref at median 615.35) and the pad law defeats the spurious basin:1 there
LEMD  patch    base 9c313551   lane v2lemdstruct2    2026-09-15T09:47:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/b2_emit/LEMD_auto.patch.osm  — r2 SHIPPING ARM (v2_solve_replay --from planar on the registered da8e5d7f capture, tree = claude/v2lemdstruct2 r2): solve optimal 54.5 s; v2 verify 1,576 rows (within_shape 466 -> 422 under 34 (13) (1)'s axis reading, tunnel_mouth_canonical 28, wall_in_runway_strip 6); census LAW-TRUE 5,712 / ADJUDICATED 1,360, within_shape 3,420, ramp_in_strip 8, strip_transverse worst 13.872 m. Surface byte-equal to r1 at both owner sites (item 5 floor 597.09 under rim 602.16; item 7 mouth 31.06/33.43 m). NO BUILD: the osm_layers refresh RULINGS 15u calls for has not been run
LEMD  patch    base 9c313551   lane v2lemdstruct2    2026-09-15T09:47:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/b1_emit/LEMD_auto.patch.osm  — 34 (13) (2) REFUTED ARM (outermost airside strip; the code is DELETED): every bar moved backwards - ramp_in_strip 8 -> 19 (bar was 0), strip_transverse 83/13.872 m -> 90/19.070 m, verify wall_in_runway_strip 6 -> 20, cockpit CRITICAL visual cliffs 10 -> 24, ADJUDICATED 1,360 -> 1,372; the trench mouth 31.06/33.43 -> 41.67/43.25 m, still inside 14R/32L's 75 m strip. Kept as the refutation record
LEMD  patch    base 106459fa   lane v2objcut         2026-09-15T09:44:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/r4_LEMD/structures.json/structures.json  — §33 (6) LEMD matched pair (base /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/b4_LEMD/...): the same six arrays BYTE-IDENTICAL (1/50/0/1/3/0), plate_mouths 2->2, crest_from_approach 2->2, underpasses 1->1; +25 named §33 (6) refusals only.
LEMD  patch    base 539e524e   lane v2lemdstruct2    2026-09-15T10:24:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/c6_emit/LEMD_auto.patch.osm  — r3 CLOSING ARM (v2_solve_replay --from planar on the registered da8e5d7f capture, tree = claude/v2lemdstruct2 r3): solve optimal 45.9 s, v2 verify 1,564 rows. 34 (13) (3) junction_raw_transverse ON as a one-way TARGET (1,591 rows, 62 contacts) - the owner's pair at 40.4611623,-3.5444804 still 4.296 % over 18.2 m; hard refuted twice (all 1,591: 10,006/109,240 violated worst 60.48 m; the 62 contacts alone: 8,548/106,182 worst 105.29 m). 34 (13) (4) mouth_pair_roads ON: 4 faces / 3,775 m2 at LEMD incl. mouth_road:-5944 (way -10867, 605.09-611.00 m, worst edge 8.00 % at the road cap), KCLT 3 / 3,564 m2, OTHH 0. Census ADJUDICATED 1,360 -> 1,344, LAW-TRUE 5,712 -> 5,692, transverse 107 -> 98, airside_no_step 475 -> 460. Hole ring -10670 cover 0.011 -> 0.023, rings > 10,000 m2 13 -> 13. NO BUILD: the ledger's last osm_layers refresh is 2026-09-08 (SPJC)
LEMD  patch    base 539e524e   lane v2lemdstruct2    2026-09-15T10:24:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/c1_emit/LEMD_auto.patch.osm  — r3 arm c1 (constraints-stage): junction_raw_transverse as a SOFT one-way target only, no mouth roads - solve optimal, verify 1,549, transverse 115 -> 97, airside_no_step 457 -> 451, the owner's crossfall pair UNCHANGED at 5.01 %. The measurement that says the raw-pair row is correct and does not bind
LEMD  patch    base 848bf35e   lane v2lemdstruct2    2026-09-15T11:36:11  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/d5_emit/LEMD_auto.patch.osm  — r4 CLOSING ARM (v2_solve_replay --from planar on the registered da8e5d7f capture, tree = claude/v2lemdstruct2 r4): solve optimal 226.1 s, v2 verify 1,547 rows, DEFECT families ALL ZERO. 34 (13) (3) (a) the foot-row flip ON (LEMD 184 one-way of 524 targets). THE OWNER'S CROSSFALL, by coordinate: contact 582.586 / far edge 582.309 over 18.12 m = 1.529 %, under the 1.985 % junction cap (r3 read 4.313 %); 0 census rows within 20 m. PRICE: 354 of 4,031 runway-family vertices moved > 0.02 m, worst 5.687 m; ramp_in_strip 8 -> 18, strip_transverse worst 13.864 -> 17.700 m, cliffs 10 -> 20, a NEW mid_edge_step 0.950 m between two runway faces at 40.4613609,-3.5446852. Census LAW-TRUE 5,791 ADJUDICATED 1,357 (airside 1,251 -> 1,215). NO BUILD: the ledger's last osm_layers refresh is 2026-09-08
LEMD  patch    base 106459fa   lane v2objcut         2026-09-15T10:44:12  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/c6_LEMD/structures.json/structures.json  — r2 §33 (6) C lane arm at claude/v2objcut 3b3259dd (base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/b4_LEMD/...)
LEMD  patch    base d803147a   lane v2lemdstruct2    2026-09-15T12:24:50  /Users/noah/XPTerrainBuilder/.claude/worktrees/v2lemdstruct2/Ortho4XP/Patches/+40-010/+40-004/LEMD_auto.patch.osm  — r5 CLOSING BUILD (build_airport.py LEMD --tag v2lemdstruct2r5 --tile 40 -4), rc 0, 980.1 s, ledger tree fddb2fc4a8c6, [harness] shared repo UNCHANGED (full-surface before/after snapshot). THE ACCEPTANCE NUMBER: the owner's raw pair at 40.4611623,-3.5444804 reads 0.280 m over 18.16 m = 1.542 %, under the 1.985 percent junction cap (r3 read 4.313). Item 5 rim 602.16 / ramp floor 597.09 = 5.07 m; item 7 trench rim at 31.06 m; 3 mouth roads. Census LAW-TRUE 6,024 ADJUDICATED 1,934, ramp_in_strip 18, mid_edge_step 2 (0.950 m), strip_transverse 89/17.700, transverse 92, airside_no_step 362, cliffs 20
LEMD  patch    base d803147a   lane v2lemdstruct2    2026-09-15T12:24:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/e_off_emit/LEMD_auto.patch.osm  — r5 MATCHED PAIR, flip OFF arm (the r4 foot-row one-way registration OUT; one tree, one capture, registers asserted before the arm). Verify 1,711 rows; census LAW-TRUE 5,782 ADJUDICATED 1,505 (airside 1,370); CRITICAL motion 7, cliffs 20; mid_edge_step 2 worst 0.950 m; ramp_in_strip 18; the owner's raw pair 4.313 percent. Its ON twin is e_on_emit. THIS PAIR CORRECTS r4, whose runway figures compared arms across a main merge
LEMD  patch    base d803147a   lane v2lemdstruct2    2026-09-15T12:24:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/e_on_emit/LEMD_auto.patch.osm  — r5 MATCHED PAIR, flip ON arm. Verify 1,554 rows; census LAW-TRUE 5,712 ADJUDICATED 1,393 (airside 1,258); CRITICAL motion 5, cliffs 20; mid_edge_step 2 worst 0.950 m (SAME as the OFF arm - it is NOT the flip's doing); ramp_in_strip 18 (same); airside_no_step 452 -> 357, taxi_box 152 -> 130, transverse 98 -> 90, strip_arc 9 -> 4; within_shape +62 and strip_transverse worst 13.864 -> 17.700 m are the flip's real price; the owner's raw pair 4.313 -> 1.529 percent. Runway movement 319 of 4,042 vertices > 0.02 m, worst 5.687 m - attributed to a 111,648 m2 40 (1) runway SHOULDER (cell 15 / face 5) reaching 914 m off the centreline, on which no level row exists
LEMD  patch    base f912ba81   lane v2objcut         2026-09-15T12:02:00  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e1_LEMD/structures.json/structures.json  — r3 lane dry --stage structures at claude/v2objcut edf1e3c0; matched base arm at main f912ba81 in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e0_LEMD (LEMD) / /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e2_LEMD (OTHH, run 2 - run 1 e0_OTHH read 7 corridors against run 2's 9 at the SAME sha: main's object-corridor reader is NONDETERMINISTIC at OTHH, reported).
LEMD  patch    base f912ba81   lane v2objcut         2026-09-15T12:02:00  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/f1_LEMD/structures.json/structures.json  — r3 C3' arm with deck_rings_ll published (base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/f0_LEMD): bridge_deck:-6288 lateral -11.81..+2.29 m -> -10.23..+10.24 m against the Bridge2 pair's inner faces at +-10.185 m (worst |offset|-half 1.62 -> 0.06 m); every other LEMD deck ring BYTE-IDENTICAL.

## Registered frames: HECA

HECA  patch    base 13431931   lane v2zonehole       2026-09-13T22:35:13  /tmp/harness/v2zonehole_heca3.osm  — closing arm of claude/v2zonehole (rc 0, 410.3 s, body_sha 6cc8952ff963, ledger 3b32f2bd74f7, shared repo UNCHANGED) — §41 (1) absorption: containment census 39 -> 4 contained faces (33 notches absorbed, 65,772 -> 245 m2), cross_connector:pav77 absorbed into primary_parallel:pav73 at the owner's site, law-true 40,067 -> 38,151, rows within 100 m of the site 615 -> 551; residual zone_on_pavement 3 / 52.3 m2
HECA  capture  base 1a7a7158   lane v2roadcontact    2026-09-13T22:42:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/roadcontact/cap/HECA.pkl  — the FIRST registered HECA capture (v2_solve_replay --capture, 156 s, 17,408 vertices / 762 faces, 59 shapes) on main 1a7a7158; carries the road_contact_edge channel
HECA  patch    base 1a7a7158   lane v2roadcontact    2026-09-13T22:42:26  /tmp/harness/v2roadcontactHECA2.osm  — closing build of claude/v2roadcontact 9ac0fac2 (rc 0, 337.6 s, body_sha 38465d2dfd2a, ledger 96f569b01af9, shared repo UNCHANGED) — §37 (10): route0 end +0.054 m over pav74 edge, item-4 pair 1.6 % over 3.05 m; census law-true 38,441 adjudicated 12,771
HECA  patch    base 1a7a7158   lane v2roles          2026-09-13T22:45:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build/v2roles_HECA.osm  — closing HECA build of lane v2roles at claude/v2roles f19e2226 (§40): rc 0, 439.8 s, ways 1383, body_sha 8b2ca256f237, artifact ledger 9441f61e86fb, solve feasible, guard UNCHANGED. Shape 44 -> runway shoulder of 05L/23R, shape 93 -> apron, taxi zone strips on shape 44's ground 5 -> 0. RESIDUAL: v2-verify DEFECT runway_transverse 0 -> 2 (1.5287/1.5233 % vs the 1.50 % cap = 3.1/4.8 cm excess at 108.7/204.9 m from the ridge)
HECA  graded   base 1a7a7158   lane v2roles          2026-09-13T22:45:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build/v2roles_HECA.v2/HECA.graded.json  — design surface of the same v2roles_HECA build; HECA.report.json beside it carries verify.rows per family
HECA  patch    base 79d1fc1e   lane v2drapedsrc      2026-09-13T22:48:53  /tmp/harness/v2drapedsrc_heca.osm  — lane v2drapedsrc closing HECA build on claude/v2drapedsrc 588c09fa (base main 79d1fc1e): rc 0, 1941.7 s, body_sha d5643cfde2d4, artifact ledger 302ca060e48e, shared repo UNCHANGED, solve feasible — the FIRST HECA frame carrying §42 object pavement (467 bodies / 5,511,801 m2 from 8 draped resources; the owner's site 30.1235047,31.4160956 now INSIDE apron:pav132 shape 63)
HECA  graded   base 79d1fc1e   lane v2drapedsrc      2026-09-13T22:48:53  /tmp/harness/v2drapedsrc_heca.v2/HECA.graded.json  — lane v2drapedsrc closing HECA build on claude/v2drapedsrc 588c09fa (base main 79d1fc1e): rc 0, 1941.7 s, body_sha d5643cfde2d4, artifact ledger 302ca060e48e, shared repo UNCHANGED, solve feasible — the FIRST HECA frame carrying §42 object pavement (467 bodies / 5,511,801 m2 from 8 draped resources; the owner's site 30.1235047,31.4160956 now INSIDE apron:pav132 shape 63)
HECA  rebake   base 79d1fc1e   lane v2drapedsrc      2026-09-13T22:48:53  /tmp/harness/v2drapedsrc_heca.v2/HECA.rebake.json  — lane v2drapedsrc closing HECA build on claude/v2drapedsrc 588c09fa (base main 79d1fc1e): rc 0, 1941.7 s, body_sha d5643cfde2d4, artifact ledger 302ca060e48e, shared repo UNCHANGED, solve feasible — the FIRST HECA frame carrying §42 object pavement (467 bodies / 5,511,801 m2 from 8 draped resources; the owner's site 30.1235047,31.4160956 now INSIDE apron:pav132 shape 63)
HECA  patch    base a5bb6be3   lane v2roles          2026-09-13T23:17:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build_r2/v2roles_HECA_r2b.osm  — ROUND 2 closing HECA build, claude/v2roles a33197a5 (§40 as amended by RULINGS 2026-09-13dd, main merged at 76108185): rc 0, 352.7 s, ways 1142, nodes 22040, body_sha 907d90dfc271, artifact ledger 09ca36ca6c1a, solve feasible, guard shared repo UNCHANGED. v2-verify runway_transverse 2 -> 0 (the two shoulder rows pass at the 2.5 % shoulder cap); NO DEFECT family. Matched census A/B vs the 1a7a7158 base arm: law-true 38,612 -> 33,265, ADJUDICATED 12,844 -> 14,870 (+2,026; round 1 was +2,511)
HECA  graded   base a5bb6be3   lane v2roles          2026-09-13T23:17:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build_r2/v2roles_HECA_r2b.v2/HECA.graded.json  — design surface of the round-2 v2roles_HECA_r2b build; report.json beside it, and the A/B rows dumps in scratchpad/v2roles/rows_r2.*.json
HECA  patch    base 38dd98be   lane v2roadcontact    2026-09-13T23:36:37  /tmp/harness/v2roadcontactHECA3.osm  — CLOSING build of claude/v2roadcontact 9eaebbf8 (rc 0, 332.5 s, body_sha 8bbae5f33254, artifact ledger 5e3f94ef2db6, shared repo UNCHANGED) on merged main 38dd98be — §37 (10) as ruled 13dh: route0 end +0.023 m over pav74's edge (4.34 m away), item-4 pair 0.05 m over 3.05 m (1.6 %); census law-true 33,242 adjudicated 14,850 (airside 14,506 / gs 300), road_cross_section 27, transverse 1,575, road_coverage_join 0; v2 verify 21,797 rows, verify_defects {}
HECA  patch    base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/l2/v2ds_lane38.osm  — lane v2drapedsrc round 2 (§42 (2) amended, RULINGS 13dc) on claude/v2drapedsrc 8994391f; MATCHED PAIR with the base arm cut at main 38dd98be (both carry §40). rc 0, 540.9 s, ways 1783, body_sha c16719e90795, artifact ledger 3eec5bf2bd6a, shared repo UNCHANGED. The owner's site 30.1235047,31.4160956 is INSIDE its OWN apron face apron:dsf:objpav33 (base: 0 rings); census law-true adjudicated 14,870 -> 24,338
HECA  graded   base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/l2/v2ds_lane38.v2/HECA.graded.json  — lane v2drapedsrc round 2 (§42 (2) amended, RULINGS 13dc) on claude/v2drapedsrc 8994391f; MATCHED PAIR with the base arm cut at main 38dd98be (both carry §40). rc 0, 540.9 s, ways 1783, body_sha c16719e90795, artifact ledger 3eec5bf2bd6a, shared repo UNCHANGED. The owner's site 30.1235047,31.4160956 is INSIDE its OWN apron face apron:dsf:objpav33 (base: 0 rings); census law-true adjudicated 14,870 -> 24,338
HECA  patch    base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/b2/v2ds_base38.osm  — BASE ARM of the v2drapedsrc round-2 pair: main 38dd98be cut with git archive into a ritual worktree (src byte-identical to the archive), rc 0, 342.7 s, ways 1142, body_sha 907d90dfc271, artifact ledger 85edce09e12a, shared repo UNCHANGED
HECA  graded   base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/b2/v2ds_base38.v2/HECA.graded.json  — the design surface of the same v2ds_base38 base arm
HECA  capture  base cf87c942   lane v2unionsweep     2026-09-14T07:40:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2unionsweep/heca.lane.json  — DRY replay dump (NOT a capture: plan_clusters OFF the registered HECA capture 1a7a7158, via cluster_arm.py). MATCHED PAIR: heca.base.json = main cf87c942 (67.52 s, contended; scout read 28.7 s), heca.lane.json = claude/v2unionsweep 99cf52ba (2.24 s). 2 clusters both arms, both areas bit-identical (unit:42#0 404117.7954653089 / unit:43#8 915741.4253155532).
HECA  patch    base fef82b29   lane v2slivers        2026-09-14T09:05:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2slivers/heca/v2sl_heca2.osm  — CLOSING build of claude/v2slivers 88dfed33 (base main fef82b29): rc 0, 549.5 s, ways 1720, nodes 31441, body_sha 1c7f2be7abae, solve feasible, shared repo UNCHANGED (2 EXTERNAL-CANDIDATE VHHH deltas outside this build's input set) - 41(4) zone slivers 57/1647 m2 -> 1/188 m2 (55 dissolved, 0 dropped), owner shape 1035 gone (no vertex within 12 m of 30.1110526,31.4061994; base carried four at 105.86-106.01 against neighbours 104.32-104.71); gap_interior_ring 57 -> 49 (3 covered + 5 hairline gone incl way -10231, 0 minted, all 49 real voids). Census A/B vs v2sl_heca_base: law-true 54018 -> 53806, ADJUDICATED 24305 -> 24375, cockpit CRITICAL motion 14 -> 17, visual 1568 -> 1518
HECA  patch    base fef82b29   lane v2slivers        2026-09-14T09:05:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2slivers/heca_base/v2sl_heca_base.osm  — BASE ARM of the v2slivers matched pair: main fef82b29 (src restored clean in the lane worktree), rc 0, 521.5 s, ways 1783, body_sha c07206902a0b, artifact ledger dc1d00dd83ca, shared repo UNCHANGED. Reproduces the owner's 1.0.331 numbers exactly: 338 graded_strip faces, 57 slivers / 1647 m2, 57 gap_interior_ring rings
HECA  patch    base 2a4abb10   lane v2apronneck      2026-09-14T09:05:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/apronneck/build/v2apronneck_HECA.osm  — lane v2apronneck CLOSING HECA build on claude/v2apronneck 5340dcd7 (base main 2a4abb10) — §43 the neck cut: rc 0, 544.5 s, ways 1822, nodes 31613, body_sha d47263b02287, artifact ledger d53f79789526, solve feasible, guard shared repo UNCHANGED, v2-verify DEFECTS {}. HECA 10 necks; the owner's shape-344 apron (79,658 m2, z span 21.77 m) is gone — the neck A->B is secondary_parallel carrying -2.18 % where the apron carried -1.51 %, the new apron beyond spans 2.51 m. MATCHED PAIR with v2apronneck_HECAbase.
HECA  graded   base 2a4abb10   lane v2apronneck      2026-09-14T09:05:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/apronneck/build/v2apronneck_HECA.v2/HECA.graded.json  — lane v2apronneck CLOSING HECA build on claude/v2apronneck 5340dcd7 (base main 2a4abb10) — §43 the neck cut: rc 0, 544.5 s, ways 1822, nodes 31613, body_sha d47263b02287, artifact ledger d53f79789526, solve feasible, guard shared repo UNCHANGED, v2-verify DEFECTS {}. HECA 10 necks; the owner's shape-344 apron (79,658 m2, z span 21.77 m) is gone — the neck A->B is secondary_parallel carrying -2.18 % where the apron carried -1.51 %, the new apron beyond spans 2.51 m. MATCHED PAIR with v2apronneck_HECAbase.
HECA  patch    base 2a4abb10   lane v2apronneck      2026-09-14T09:05:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/apronneck/base_build/v2apronneck_HECAbase.osm  — BASE ARM of the v2apronneck matched pair: main 2a4abb10 in its own ritual worktree (v2apronneckbase), rc 0, 550.6 s, shared repo UNCHANGED (2 external-candidate deltas named, another lane's VHHH mod-cache), NOT ledger-stored. Census law-true 54,018 adjudicated 24,305
HECA  patch    base 22134e4f   lane zonemint         2026-09-14T09:26:56  /tmp/harness/zonemint_heca.osm  — closing build of claude/zonemint f35d3ee9 (rc 0, 664.5 s, ways 1783, nodes 31514, body_sha c07206902a0b, solve feasible, shared repo UNCHANGED; artifact ledger not stored: an external .DS_Store delta in the window) — sidecar face_holes now derived from the EMITTED surface (546 sub-spacing merges this build): zone_on_pavement 0 (the v2zonehole 13431931 frame: 3 / 52.3 m2; that frame REPLAYED with re-derived holes: 0, no other family moved). Base 22134e4f carries §40/§42, so its 54,012 rows / adjudicated 23,523 are NOT comparable with the 13431931 frame's 38,044 / 12,166
HECA  patch    base 22134e4f   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T083816.osm  — lane v2connector round 3 HECA build on claude/v2connector a191b26e: rc0 507.4s, body_sha c07206902a0b, ledger fd20ddfd334c, solve feasible, guard UNCHANGED — the FIRST HECA frame carrying §16g (7) (1) footprint rings (CONVEX HULL form, Part.ring flat); bodies at 96.20 1,489 -> 0
HECA  graded   base 22134e4f   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T083816.v2/HECA.graded.json  — lane v2connector round 3 HECA build on claude/v2connector a191b26e: rc0 507.4s, body_sha c07206902a0b, ledger fd20ddfd334c, solve feasible, guard UNCHANGED — the FIRST HECA frame carrying §16g (7) (1) footprint rings (CONVEX HULL form, Part.ring flat); bodies at 96.20 1,489 -> 0
HECA  rebake   base 22134e4f   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T083816.v2/HECA.rebake.json  — lane v2connector round 3 HECA build on claude/v2connector a191b26e: rc0 507.4s, body_sha c07206902a0b, ledger fd20ddfd334c, solve feasible, guard UNCHANGED — the FIRST HECA frame carrying §16g (7) (1) footprint rings (CONVEX HULL form, Part.ring flat); bodies at 96.20 1,489 -> 0
HECA  patch    base bc6b0641   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T093118.osm  — lane v2connector round 4 closing HECA build on claude/v2connector 70dc4acf (base main bc6b0641): rc0 597.6s, body_sha see result.json, ledger 9c1ae5a6873e, solve feasible, guard UNCHANGED — the FIRST frame carrying the TRUE OUTLINE (Part.rings, one per blob, simplified OUTWARD): 46,765 of 55,626 parts / 52,724 rings / 264,996 vertices; units 304 -> 324, plan_units_and_connectors 17.2 s, pads-span units 20 -> 17, rail concrete_3 b1 93.45 -> 76.70
HECA  graded   base bc6b0641   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T093118.v2/HECA.graded.json  — lane v2connector round 4 closing HECA build on claude/v2connector 70dc4acf (base main bc6b0641): rc0 597.6s, body_sha see result.json, ledger 9c1ae5a6873e, solve feasible, guard UNCHANGED — the FIRST frame carrying the TRUE OUTLINE (Part.rings, one per blob, simplified OUTWARD): 46,765 of 55,626 parts / 52,724 rings / 264,996 vertices; units 304 -> 324, plan_units_and_connectors 17.2 s, pads-span units 20 -> 17, rail concrete_3 b1 93.45 -> 76.70
HECA  rebake   base bc6b0641   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T093118.v2/HECA.rebake.json  — lane v2connector round 4 closing HECA build on claude/v2connector 70dc4acf (base main bc6b0641): rc0 597.6s, body_sha see result.json, ledger 9c1ae5a6873e, solve feasible, guard UNCHANGED — the FIRST frame carrying the TRUE OUTLINE (Part.rings, one per blob, simplified OUTWARD): 46,765 of 55,626 parts / 52,724 rings / 264,996 vertices; units 304 -> 324, plan_units_and_connectors 17.2 s, pads-span units 20 -> 17, rail concrete_3 b1 93.45 -> 76.70
HECA  patch    base e1014ddd   lane v2connector      2026-09-14T11:15:19  /tmp/harness/HECA_20260914T104957.osm  — lane v2connector round 5 HECA build (the §16g (8) NULL ARM) on claude/v2connector 2e97d822: rc0 578.1s, body_sha 4dd84ed258a0, solve feasible, guard UNCHANGED — §16g (8) derived pads implemented but INERT here: pad_flats.cluster_cross_links 0, so cluster_offsets returns {} and no pad moved; pad-span census byte-equal to round 4 (17 units / 845 bodies, fu:38:23 23 pads / 29.99 m)
HECA  graded   base e1014ddd   lane v2connector      2026-09-14T11:15:19  /tmp/harness/HECA_20260914T104957.v2/HECA.graded.json  — lane v2connector round 5 HECA build (the §16g (8) NULL ARM) on claude/v2connector 2e97d822: rc0 578.1s, body_sha 4dd84ed258a0, solve feasible, guard UNCHANGED — §16g (8) derived pads implemented but INERT here: pad_flats.cluster_cross_links 0, so cluster_offsets returns {} and no pad moved; pad-span census byte-equal to round 4 (17 units / 845 bodies, fu:38:23 23 pads / 29.99 m)
HECA  rebake   base e1014ddd   lane v2connector      2026-09-14T11:15:19  /tmp/harness/HECA_20260914T104957.v2/HECA.rebake.json  — lane v2connector round 5 HECA build (the §16g (8) NULL ARM) on claude/v2connector 2e97d822: rc0 578.1s, body_sha 4dd84ed258a0, solve feasible, guard UNCHANGED — §16g (8) derived pads implemented but INERT here: pad_flats.cluster_cross_links 0, so cluster_offsets returns {} and no pad moved; pad-span census byte-equal to round 4 (17 units / 845 bodies, fu:38:23 23 pads / 29.99 m)
HECA  capture  base 22134e4f   lane rwyholes         2026-09-14T09:25:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder--claude-worktrees-dreamy-maxwell-b04861/a16ebd19-720d-4bda-a609-9334a87ca57c/scratchpad/rwyholes/cap/HECA.pkl  — the FIRST HECA capture carrying §40 (v2_solve_replay --capture from a ritual-mounted control worktree at main 22134e4f, 151 s, guard blocked [], lane-local DSF dump + mod-cache overlays; 25,358 vertices / 1,307 faces): 43 runway-family faces, 4 with holes, 308 hole vertices — the rwyholes dry pair (crown_drops 3419 -> 3727, runway_crown 2441 -> 2749, runway_transverse 2441 -> 2749 rows) was read off it
HECA  patch    base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECA2.osm  — LANE arm of the v2padcluster matched pair (§16g (9)-(10) THE PAD IS THE CLUSTER, branch claude/v2padcluster 1a230c8f, base main 0bc96357): rc 0, 394.8 s, ways 2079, body_sha c83dfe27b38d, artifact ledger beb3e32ab119, solve feasible, guard shared repo UNCHANGED. The FIRST HECA frame whose building pads are DERIVED from the pack's clusters (1,954 clusters; pad area 867,374 -> 1,369,935 m2, 414 -> 652 faces). pad_cluster_mismatch 44; AIRSIDE 13,637 of 21,534 taxi/runway vertices moved > 0.02 m, worst 10.14 m -- the airside bar is MISSED and the branch should not merge on it
HECA  patch    base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECAdisarm.osm  — BASE ARM of the v2padcluster matched pair: the SAME branch with [placement] pad_from_cluster=false, floor_split_m=0, cluster_pad_min_m2=0 (the keys' own disarm clauses), rc 0, 462.1 s, ways 1741, body_sha 97a2267cfc28, guard shared repo UNCHANGED. Reproduces the pre-14x pad derivation: 414 building faces / 867,374 m2
HECA  graded   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECA2.v2/HECA.graded.json  — LANE arm of the v2padcluster matched pair (§16g (9)-(10) THE PAD IS THE CLUSTER, branch claude/v2padcluster 1a230c8f, base main 0bc96357): rc 0, 394.8 s, ways 2079, body_sha c83dfe27b38d, artifact ledger beb3e32ab119, solve feasible, guard shared repo UNCHANGED. The FIRST HECA frame whose building pads are DERIVED from the pack's clusters (1,954 clusters; pad area 867,374 -> 1,369,935 m2, 414 -> 652 faces). pad_cluster_mismatch 44; AIRSIDE 13,637 of 21,534 taxi/runway vertices moved > 0.02 m, worst 10.14 m -- the airside bar is MISSED and the branch should not merge on it
HECA  graded   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECAdisarm.v2/HECA.graded.json  — BASE ARM of the v2padcluster matched pair: the SAME branch with [placement] pad_from_cluster=false, floor_split_m=0, cluster_pad_min_m2=0 (the keys' own disarm clauses), rc 0, 462.1 s, ways 1741, body_sha 97a2267cfc28, guard shared repo UNCHANGED. Reproduces the pre-14x pad derivation: 414 building faces / 867,374 m2
HECA  rebake   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECA2.v2/HECA.rebake.json  — LANE arm of the v2padcluster matched pair (§16g (9)-(10) THE PAD IS THE CLUSTER, branch claude/v2padcluster 1a230c8f, base main 0bc96357): rc 0, 394.8 s, ways 2079, body_sha c83dfe27b38d, artifact ledger beb3e32ab119, solve feasible, guard shared repo UNCHANGED. The FIRST HECA frame whose building pads are DERIVED from the pack's clusters (1,954 clusters; pad area 867,374 -> 1,369,935 m2, 414 -> 652 faces). pad_cluster_mismatch 44; AIRSIDE 13,637 of 21,534 taxi/runway vertices moved > 0.02 m, worst 10.14 m -- the airside bar is MISSED and the branch should not merge on it
HECA  rebake   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECAdisarm.v2/HECA.rebake.json  — BASE ARM of the v2padcluster matched pair: the SAME branch with [placement] pad_from_cluster=false, floor_split_m=0, cluster_pad_min_m2=0 (the keys' own disarm clauses), rc 0, 462.1 s, ways 1741, body_sha 97a2267cfc28, guard shared repo UNCHANGED. Reproduces the pre-14x pad derivation: 414 building faces / 867,374 m2
HECA  patch    base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterHECA4.osm  — LANE arm of the v2padcluster ROUND 3 pair (§16g (10) (4)-(6), branch claude/v2padcluster e75f97b1, base main a1d0edfa): rc 0, 384.4 s, ways 2088, body_sha cbefb8edcacb, artifact ledger 72fb36419b42, solve feasible, guard shared repo UNCHANGED. (4) only a WALLED body chains (Part.height_m + chain_min_height_m 2.5) on BOTH the design cluster and the object unit; (5) the pad is clipped by airside and split at its pieces; (6) pad_airside_weld census. T3 RESOLVED: largest cluster over the pad threshold 541,200 m2 / 9,334 bodies -> 171,086 m2 / 1 body; the terminal body at 30.1279552,31.403143 is +0.15 m off its own ground (was +7.50). MISSED: airside 17,482 of 29,465 vertices moved > 0.02 m (worst 12.15, runway 856/3,426 worst 3.14); pad_cluster_mismatch 27; pad_airside_weld 24 (disarm 16); terminal SURFACE 80.94 vs bar 72.50; constraints +55 %. Design surface byte-identical to v2padclusterHECA3
HECA  graded   base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterHECA4.v2/HECA.graded.json  — LANE arm of the v2padcluster ROUND 3 pair (§16g (10) (4)-(6), branch claude/v2padcluster e75f97b1, base main a1d0edfa): rc 0, 384.4 s, ways 2088, body_sha cbefb8edcacb, artifact ledger 72fb36419b42, solve feasible, guard shared repo UNCHANGED. (4) only a WALLED body chains (Part.height_m + chain_min_height_m 2.5) on BOTH the design cluster and the object unit; (5) the pad is clipped by airside and split at its pieces; (6) pad_airside_weld census. T3 RESOLVED: largest cluster over the pad threshold 541,200 m2 / 9,334 bodies -> 171,086 m2 / 1 body; the terminal body at 30.1279552,31.403143 is +0.15 m off its own ground (was +7.50). MISSED: airside 17,482 of 29,465 vertices moved > 0.02 m (worst 12.15, runway 856/3,426 worst 3.14); pad_cluster_mismatch 27; pad_airside_weld 24 (disarm 16); terminal SURFACE 80.94 vs bar 72.50; constraints +55 %. Design surface byte-identical to v2padclusterHECA3
HECA  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterHECA4.v2/HECA.rebake.json  — LANE arm of the v2padcluster ROUND 3 pair (§16g (10) (4)-(6), branch claude/v2padcluster e75f97b1, base main a1d0edfa): rc 0, 384.4 s, ways 2088, body_sha cbefb8edcacb, artifact ledger 72fb36419b42, solve feasible, guard shared repo UNCHANGED. (4) only a WALLED body chains (Part.height_m + chain_min_height_m 2.5) on BOTH the design cluster and the object unit; (5) the pad is clipped by airside and split at its pieces; (6) pad_airside_weld census. T3 RESOLVED: largest cluster over the pad threshold 541,200 m2 / 9,334 bodies -> 171,086 m2 / 1 body; the terminal body at 30.1279552,31.403143 is +0.15 m off its own ground (was +7.50). MISSED: airside 17,482 of 29,465 vertices moved > 0.02 m (worst 12.15, runway 856/3,426 worst 3.14); pad_cluster_mismatch 27; pad_airside_weld 24 (disarm 16); terminal SURFACE 80.94 vs bar 72.50; constraints +55 %. Design surface byte-identical to v2padclusterHECA3
HECA  patch    base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterHECA5.osm  — LANE arm of the v2padcluster ROUND 4 pair (§16g (10) (7)-(8), branch claude/v2padcluster 9a4bd0e3, base main a1d0edfa): rc 0, 420.6 s, ways 1916, body_sha 1112755a1db9, artifact ledger 85c18b3071e6, solve feasible, guard shared repo UNCHANGED. (7) LEAVES GET NO PAD (39 % of the outline area dropped: 359,152 m2 in 1,518 leaf pads + 175,708 m2 under the threshold); (8) the plate is DROPPED AT AN AIRSIDE RIM (8,967 skirt rows at the pad slope ceiling, 30 pads wholly inside pavement keep a two-sided plate). MET: the terminal at 30.1279552,31.403143 SURFACE 72.60 (bar 72.50, DISARM 72.07) with its body on the WALLED cluster pad building298 at 72.62, own ground +0.08 m (+0.55 m of fill, cluster fu:38:96@cluster_pad). MISSED: airside 14,263 of 29,783 moved > 0.02 m worst 4.55 m (the RUNWAY 1,021 of 3,426 worst 0.41 m, down from 3.14); pad_cluster_mismatch 14 (disarm 33); pad_airside_weld 16 (disarm 3, worst 1.135 m); constraints +15.7 %
HECA  graded   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterHECA5.v2/HECA.graded.json  — LANE arm of the v2padcluster ROUND 4 pair (§16g (10) (7)-(8), branch claude/v2padcluster 9a4bd0e3, base main a1d0edfa): rc 0, 420.6 s, ways 1916, body_sha 1112755a1db9, artifact ledger 85c18b3071e6, solve feasible, guard shared repo UNCHANGED. (7) LEAVES GET NO PAD (39 % of the outline area dropped: 359,152 m2 in 1,518 leaf pads + 175,708 m2 under the threshold); (8) the plate is DROPPED AT AN AIRSIDE RIM (8,967 skirt rows at the pad slope ceiling, 30 pads wholly inside pavement keep a two-sided plate). MET: the terminal at 30.1279552,31.403143 SURFACE 72.60 (bar 72.50, DISARM 72.07) with its body on the WALLED cluster pad building298 at 72.62, own ground +0.08 m (+0.55 m of fill, cluster fu:38:96@cluster_pad). MISSED: airside 14,263 of 29,783 moved > 0.02 m worst 4.55 m (the RUNWAY 1,021 of 3,426 worst 0.41 m, down from 3.14); pad_cluster_mismatch 14 (disarm 33); pad_airside_weld 16 (disarm 3, worst 1.135 m); constraints +15.7 %
HECA  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterHECA5.v2/HECA.rebake.json  — LANE arm of the v2padcluster ROUND 4 pair (§16g (10) (7)-(8), branch claude/v2padcluster 9a4bd0e3, base main a1d0edfa): rc 0, 420.6 s, ways 1916, body_sha 1112755a1db9, artifact ledger 85c18b3071e6, solve feasible, guard shared repo UNCHANGED. (7) LEAVES GET NO PAD (39 % of the outline area dropped: 359,152 m2 in 1,518 leaf pads + 175,708 m2 under the threshold); (8) the plate is DROPPED AT AN AIRSIDE RIM (8,967 skirt rows at the pad slope ceiling, 30 pads wholly inside pavement keep a two-sided plate). MET: the terminal at 30.1279552,31.403143 SURFACE 72.60 (bar 72.50, DISARM 72.07) with its body on the WALLED cluster pad building298 at 72.62, own ground +0.08 m (+0.55 m of fill, cluster fu:38:96@cluster_pad). MISSED: airside 14,263 of 29,783 moved > 0.02 m worst 4.55 m (the RUNWAY 1,021 of 3,426 worst 0.41 m, down from 3.14); pad_cluster_mismatch 14 (disarm 33); pad_airside_weld 16 (disarm 3, worst 1.135 m); constraints +15.7 %
HECA  patch    base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA7.osm  — SHIPPED arm of v2padcluster ROUND 5 (§16g (10) (8) refined, branch claude/v2padcluster 95c48df7, base main 9a8b253b): rc 0, 451.5 s, ways 1916, body_sha 18e51b7d084e, artifact ledger a602bba1b858, solve feasible, guard shared repo UNCHANGED. [placement] pad_skirt_m ships at 0 = the airside-SHARED vertices alone (round 4's scope) PLUS 14al's withdrawal of the two-sided ceiling row over a pair of two shared vertices (4,008 pairs dropped). THE BEST ARM: airside 9,573 of 21,523 moved > 0.02 m (r4 10,048, the 25 m band 10,683), the RUNWAY 885 worst 0.390 m (r4 1,021/0.410, band 1,394/0.570); pad_cluster_mismatch 14; pad_airside_weld 29 worst 1.135; law-true 64,844; the terminal body on building298 at 72.60, own ground +0.07 m. Constraints 109.69 s = +31.4 % (bar +20 %, MISSED — the pad population, not the skirt)
HECA  patch    base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA6.osm  — the 25 m BAND arm of v2padcluster ROUND 5 — MEASURED AND REFUTED (branch claude/v2padcluster b5e29894): rc 0, 433.5 s, body_sha ee7d0f56911c, artifact ledger b63e49fd65b0, guard shared repo UNCHANGED. Worse than round 4's scope on EVERY airside bar: airside 10,048 -> 10,683, the runway 1,021 -> 1,394 and its worst 0.410 -> 0.570 m, pad_airside_weld 16 -> 21 (worst 1.135 -> 2.42), law-true 63,904 -> 66,771 — for the terminal body +0.08 -> +0.00 m. A wider band softens more of the pad and a softer pad moves more of the apron inside the same ceiling. pad_skirt_m keeps 25.0 as its design value and ships at 0
HECA  graded   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA7.v2/HECA.graded.json  — SHIPPED arm of v2padcluster ROUND 5 (§16g (10) (8) refined, branch claude/v2padcluster 95c48df7, base main 9a8b253b): rc 0, 451.5 s, ways 1916, body_sha 18e51b7d084e, artifact ledger a602bba1b858, solve feasible, guard shared repo UNCHANGED. [placement] pad_skirt_m ships at 0 = the airside-SHARED vertices alone (round 4's scope) PLUS 14al's withdrawal of the two-sided ceiling row over a pair of two shared vertices (4,008 pairs dropped). THE BEST ARM: airside 9,573 of 21,523 moved > 0.02 m (r4 10,048, the 25 m band 10,683), the RUNWAY 885 worst 0.390 m (r4 1,021/0.410, band 1,394/0.570); pad_cluster_mismatch 14; pad_airside_weld 29 worst 1.135; law-true 64,844; the terminal body on building298 at 72.60, own ground +0.07 m. Constraints 109.69 s = +31.4 % (bar +20 %, MISSED — the pad population, not the skirt)
HECA  graded   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA6.v2/HECA.graded.json  — the 25 m BAND arm of v2padcluster ROUND 5 — MEASURED AND REFUTED (branch claude/v2padcluster b5e29894): rc 0, 433.5 s, body_sha ee7d0f56911c, artifact ledger b63e49fd65b0, guard shared repo UNCHANGED. Worse than round 4's scope on EVERY airside bar: airside 10,048 -> 10,683, the runway 1,021 -> 1,394 and its worst 0.410 -> 0.570 m, pad_airside_weld 16 -> 21 (worst 1.135 -> 2.42), law-true 63,904 -> 66,771 — for the terminal body +0.08 -> +0.00 m. A wider band softens more of the pad and a softer pad moves more of the apron inside the same ceiling. pad_skirt_m keeps 25.0 as its design value and ships at 0
HECA  rebake   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA7.v2/HECA.rebake.json  — SHIPPED arm of v2padcluster ROUND 5 (§16g (10) (8) refined, branch claude/v2padcluster 95c48df7, base main 9a8b253b): rc 0, 451.5 s, ways 1916, body_sha 18e51b7d084e, artifact ledger a602bba1b858, solve feasible, guard shared repo UNCHANGED. [placement] pad_skirt_m ships at 0 = the airside-SHARED vertices alone (round 4's scope) PLUS 14al's withdrawal of the two-sided ceiling row over a pair of two shared vertices (4,008 pairs dropped). THE BEST ARM: airside 9,573 of 21,523 moved > 0.02 m (r4 10,048, the 25 m band 10,683), the RUNWAY 885 worst 0.390 m (r4 1,021/0.410, band 1,394/0.570); pad_cluster_mismatch 14; pad_airside_weld 29 worst 1.135; law-true 64,844; the terminal body on building298 at 72.60, own ground +0.07 m. Constraints 109.69 s = +31.4 % (bar +20 %, MISSED — the pad population, not the skirt)
HECA  rebake   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA6.v2/HECA.rebake.json  — the 25 m BAND arm of v2padcluster ROUND 5 — MEASURED AND REFUTED (branch claude/v2padcluster b5e29894): rc 0, 433.5 s, body_sha ee7d0f56911c, artifact ledger b63e49fd65b0, guard shared repo UNCHANGED. Worse than round 4's scope on EVERY airside bar: airside 10,048 -> 10,683, the runway 1,021 -> 1,394 and its worst 0.410 -> 0.570 m, pad_airside_weld 16 -> 21 (worst 1.135 -> 2.42), law-true 63,904 -> 66,771 — for the terminal body +0.08 -> +0.00 m. A wider band softens more of the pad and a softer pad moves more of the apron inside the same ceiling. pad_skirt_m keeps 25.0 as its design value and ships at 0
HECA  patch    base 18cc0ecb   lane v2staged         2026-09-14T16:41:01  /tmp/harness/v2stagedHECA3.osm  — §20b THE STAGED SOLVE, FINAL FORM, staged_solve=true arm (branch claude/v2staged): rc 0, 416.0 s, ways 1916, body_sha 266b56b5a358, v2-verify 33955, shared repo UNCHANGED. Stage 1 AIRSIDE 19,034 unknowns / 128,949 rows, 42/161,690 hard violated max 0.1794 NOT SETTLED, 0 one-way rows, runway projection 0.1155 -> 0.020000 m with 0 elastic; stage 2 13,838 unknowns / 180,591 rows in 11.2 s. vs its OFF twin v2stagedHECAoff (= r5 shipped body 18e51b7d084e): airside moved vs DISARM 8,976 -> 10,371 (BAR 0 MISSED; runway 885/0.390 -> 477/1.560), adjudicated 28,413 -> 29,018, airside_no_step 7,919 -> 6,801, taxi_box 3,429 -> 2,854, pad_airside_weld 29 -> 33, pad_cluster_mismatch 14 -> 14, terminal building298 72.60 -> 73.05. SHIPS OFF
HECA  patch    base 18cc0ecb   lane v2staged         2026-09-14T16:41:01  /tmp/harness/v2stagedHECAoff.osm  — §20b's DISARM twin (staged_solve=false) on claude/v2staged: rc 0, 476.3 s, body_sha 18e51b7d084e — BYTE-IDENTICAL to v2padcluster r5's shipped arm (ledger a602bba1b858), which proves everything merged since a3185dbb changes nothing at HECA and makes the r5/DISARM frames lawful controls for this lane. v2-verify 33,397; 1,021/365,395 hard rows violated max 2.984 m
HECA  capture  base b1b7704c   lane v2settle         2026-09-14T17:38:04  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/HECA.pkl  — v2_solve_replay --capture on main b1b7704c (158 s, 31,820 vertices / 1,684 faces, pack partition 101 s: bodies 24,655 groups 22,049 relief 3,938 infeasible 2,546, 63 shapes); guard shared repo UNCHANGED, lane-local DSF + mod-cache overlays. The first HECA capture carrying the merged §20b staged solve (flag OFF by default; arm with --design-weight staged_solve=1). Stage-1 airside hard set read off it with the new --why-hard-stage 1.
HECA  graded   base b1b7704c   lane v2settle         2026-09-14T17:38:04  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/emit_laneB/HECA.graded.json  — LANE arm of the v2settle matched pair (single solve = the shipped configuration), claude/v2settle b1a93a9a off main b1b7704c: dry --emit replay off cap/HECA.pkl. BYTE-IDENTICAL to the base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/base/emit_baseA/ (main b1b7704c) — the constant hard rows never reached the matrix. Hard set READ 281 -> 263 violated, worst 1.2595 m unchanged. Census law-true 64,716 ADJUDICATED 27,695.
HECA  capture  base b1b7704c   lane v2padvert        2026-09-14T18:19:02  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/HECA.pkl  — RE-READ by lane v2padvert (claude/v2padvert 4ec750f9): v2settle's HECA capture replayed under §20b (--design-weight staged_solve=1) with 14au's relaxed skirt ceiling (5 %). Stage 1 AIRSIDE 6/161,638 hard over 0.02 m, worst 0.0445 m — UNCHANGED from v2settle's post-fix reading (the airside did not move). Stage 2 770/163,847 violated, worst 4.4241 m, of which 124 a PROVED INFEASIBLE SET (90.4386 m over 544 free columns) against v2settle's 1,428 of 2,548 / 1,015.6 m: -91 % rows, -91 % shortfall. Pads-ON was NOT measurable off this capture — v2_solve_replay.capture sets no airport.clusters, so pad_from_cluster is inert in any replay of it; a pads-ON HECA reading needs a fresh capture or a build. guard shared repo UNCHANGED.
HECA  patch    base 092b3983   lane v2padjoin        2026-09-14T20:06:08  /tmp/harness/v2padjoinHECAbase.osm  — BASE ARM of the v2padjoin matched HECA pair (branch claude/v2padjoin, base main 092b3983 + the re-landed v2padvert clip): pad_from_cluster=true, pad_airside_clip=true, staged_solve=true, cluster_apron_reach_m=0. rc 0, 457.9 s, ways 1904, nodes 31924, body_sha 3a2d1507c31a, v2-verify 31042, solve feasible, guard shared repo UNCHANGED (1 external-candidate OTHH mod-cache delta named, another lane's; no artifact ledger key for that reason). REPRODUCES v2padvert's registered pads-ON frame EXACTLY: stage 2 1,201/189,405 hard violated, 151 an INFEASIBLE SET (178.7207 m over 705 free columns); stage 1 4/148,256 worst 0.0329 m
HECA  patch    base 092b3983   lane v2padjoin        2026-09-14T20:06:08  /tmp/harness/v2padjoinHECAjoin.osm  — JOIN ARM of the same pair, the ONLY variable cluster_apron_reach_m 0 -> 40 with the §30 (4) apron reach minted as RULINGS 2026-09-14bf's PLANE JOIN (each collar vertex bound into the pad's plate: cap-0 pad_flat + the hard 1 % ceiling). rc 0, 449.9 s, body_sha c76d6b9759f7, guard shared repo UNCHANGED. THE JOIN IS REFUTED: 24,202 join rows take stage 2 from 1,201 to 3,322/204,943 violated and the INFEASIBLE SET from 151/178.7207 m to 1,114/2,312.4274 m over 1,009 columns; stage 1 (the AIRSIDE) 4 -> 8 rows, worst 0.0329 -> 0.1080 m. Mechanism: under §20b the collar is airside, stage 1 fixes it without the pad and substitutes it as a constant, so the plate must equal an already-solved collar (worst join ceiling rows 5.89 m); the all-airside collar pairs leak into stage 1 and move the airside. The join code is DELETED on the branch
HECA  patch    base 0c72919a   lane v2padjoin        2026-09-14T20:49:33  /tmp/harness/v2padjoinHECAr2base.osm  — ROUND 2 BASE ARM (branch claude/v2padjoin 747eaf91, base main 0c72919a): pad_from_cluster + pad_airside_clip + staged_solve ON, cluster_apron_reach_m 0. rc 0, 473.5 s, body_sha 3a2d1507c31a — BYTE-IDENTICAL to round 1's base arm, which proves everything merged into main since 092b3983 changes nothing at HECA in this configuration. Stage 2 1,201/189,405 hard violated, 151 an INFEASIBLE SET (178.7207 m over 705 columns); stage 1 4/148,256 worst 0.0329 m; census pad_airside_weld 42, pad_cluster_mismatch 12, ADJUDICATED 26,708; terminal 30.1279552,31.403143 at 72.62
HECA  patch    base 0c72919a   lane v2padjoin        2026-09-14T20:49:33  /tmp/harness/v2padjoinHECAr2collar2.osm  — ROUND 2 COLLAR ARM, RULINGS 2026-09-14bk's form: the apron within cluster_apron_reach_m (40 m) of a cluster outline is ONE PLANE among itself in §20b STAGE 1 (apron-law heads zones.apron cluster_collar_plane[ ceiling], in no conforming register, no pad vertex in any row) and the pad's plate equals that fixed collar in stage 2; other building pads' welded vertices struck from the collar. rc 0, 368.3 s, body_sha 77e8a3aa20cb, guard shared repo UNCHANGED. STAGE 1 IS FEASIBLE (min shortfall 0.0000 m) — the collar plane is lawful — but THE ACCEPTANCE IS MISSED: airside moved vs the base 11,847 vertices worst 9.45 m (RUNWAY 837, worst 1.23) against a collar of 266 vertices / 12 at the plane, the terminal 72.62 -> 75.92 (bar 72.50), stage-2 infeasible 151 rows / 178.72 m -> 1,318 / 3,074.92 m. The worst stage-2 rows are structures.building_pad airside skirt (7.07 -> 8.58 m) — the skirt law 14ay withdraws and this round did not. Its unstruck twin is v2padjoinHECAr2collar (b6443b925086: 1,626 / 3,644.17 m, stage 1 44 unsettled). Ships DISARMED
HECA  patch    base 7fe1ee9e   lane v2padjoin        2026-09-14T21:30:17  /tmp/harness/v2padjoinHECAr3base.osm  — ROUND 3 BASE ARM (claude/v2padjoin, the SKIRT WITHDRAWN + the low-side datum; pads + clip + staged ON, cluster_apron_reach_m 0): rc 0, 446.1 s, body_sha 43b8ad21d290, v2-verify 28,801, guard shared repo UNCHANGED. THE SKIRT WITHDRAWAL ALONE, against round 2's base 3a2d1507c31a in the same configuration: stage-2 infeasible 151 rows / 178.7207 m -> 92 / 138.7410 m, violated 1,201 -> 555, worst 7.0692 -> 6.4143 m, pad_airside_weld 42 -> 18, pad_cluster_mismatch 12, ADJUDICATED 26,708 -> 24,770; stage 1 5/153,340 worst 0.0329. Terminal surface at 30.1279552,31.403143 72.92, the terminal cluster's plane 72.478
HECA  patch    base 7fe1ee9e   lane v2padjoin        2026-09-14T21:30:17  /tmp/harness/v2padjoinHECAr3collar.osm  — ROUND 3 COLLAR ARM (the only variable cluster_apron_reach_m 0 -> 40): rc 0, 512.4 s, body_sha 8cb776c1d044, guard shared repo UNCHANGED. MISSES: stage-2 infeasible 92 -> 1,511 rows / 138.74 -> 3,148.2532 m, airside moved 11,001 worst 9.27 m (runway 849 worst 1.62), terminal cluster plane 72.478 -> 75.497, surface 72.92 -> 75.90, pad_airside_weld 18 -> 19, ADJUDICATED 24,770 -> 25,983. Stage 1 stays FEASIBLE (11 unsettled rows, min shortfall 0.0000 m) — the collar plane is lawful law. THE RESIDUAL IS NOT LOCAL: of 11,363 moved vertices only 3,202 are within 40 m of a cluster pad, 3,776 within 100 m, 2,211 beyond 500 m — a field-wide shift of an unsettled stage-1 optimum (14as (ii), 13y (B)/13ab). Collar 266 vertices, 8 at the plane. Ships DISARMED
HECA  capture  base 12400580   lane v2settle         2026-09-14T23:01:33  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/HECA.pkl  — RE-READ at main 12400580 (round 2): the same b1b7704c capture replays under the merged tree. THE STABILITY PROBE FRAME — scratchpad/v2settle/probe3.py + probe4.py perturb ONE apron vertex (v9968 at 30.12795521596,31.4031429808) with a ceiling 0.30 m under the base surface and bin the moved set by distance: main moves 959 vertices > 0.02 m, 953 BEYOND 500 m, 0 within 100 m, worst 0.5206 m. Reproduces RULINGS 14br's collar signature with the pad law inert. Stage 1 here: 35/174,500 hard over 0.02 m, worst 0.0828 m, certificate FEASIBLE.
HECA  graded   base 12400580   lane v2settle         2026-09-14T23:01:33  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/r2/emit_final/HECA.graded.json  — lane v2settle ROUND 2 arm (claude/v2settle 16725245) off the b1b7704c HECA capture at main 12400580: BYTE-IDENTICAL to the base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/base2/ equivalents and to the pre-change arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/r2/emit_off/. 39/329,775 hard rows violated, worst 1.2595 m, active-set exits objective_stalled x6 (NONE at same_set).
HECA  patch    base 63258868   lane v2qp             2026-09-15T00:29:54  /tmp/harness/v2qpHECA.osm  — CLOSING build of claude/v2qp 682d1810 with [design] solver="qp" (§20c; the branch SHIPS fixed_point — this is the QP ARM): rc 0, 449.1 s, ways 1741, nodes 31261, body_sha 73b5bdecfd98, artifact ledger 2f4e1c4f8717, status optimal, shared repo UNCHANGED, v2-verify 30592 rows. design line: QP (§20c) 6 exact solves optimal x6, 197 rounds / 358 linear solves, 50.09 s, worst |grad| 537.7; 18/329337 hard rows over 0.02 m (3 a proved INFEASIBLE SET, 3.1661 m) vs the fixed point's 39. Census law-true 61845 ADJUDICATED 26348
HECA  graded   base 63258868   lane v2qp             2026-09-15T00:29:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2qp/emit_heca_qp/HECA.graded.json  — QP ARM of the v2qp matched HECA replay pair off the registered v2settle capture (cap/HECA.pkl, base b1b7704c), --design-weight solver=qp: solve 131.0 s (fixed point 127.4 s = 1.03x), hard rows over 0.02 m 39 -> 18, worst 1.2595 unchanged, infeasible set 4 -> 3. Its BASE ARM (fixed_point, same tree) is /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2qp/emit_heca_fp/HECA.graded.json, which reproduces v2settle r2's registered reading exactly (39/329775, objective_stalled x6). Census A/B ADJUDICATED 26634 -> 26607, no family worse by > 5 %
HECA  capture  base 12400580   lane v2qp             2026-09-15T00:29:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/r2/heca.solved.pkl  — RE-READ by lane v2qp as the §20c STABILITY PROBE frame, through the promoted instrument 'v2_solve_replay --why-from PKL --probe-site 30.1279552,31.403143 --probe-arm solver=fixed_point --probe-arm solver=qp'. fixed_point reproduces 14bw exactly: 959 of 31820 moved > 0.02 m, 959 beyond 250 m, 953 beyond 500 m, ZERO within 100 m, worst 0.5206 m, hard 39 -> 25 under the probe. qp: 0 moved anywhere, max |dz| 0.0043 m field-wide, hard 18 -> 18. Same capture solved twice is BITWISE identical on both arms (sha cef4f5c8a773 / 01c2f08e40b1)
HECA  capture  base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/HECA.on3.pkl  — HECA PADS-ON capture (--placement pad_from_cluster=true pad_airside_clip=true), 170 s, 32,182 vertices / 1,811 faces, guard UNCHANGED. Its solved pickle h2.on.pkl is the §16g (10) (11) probe frame: one 0.30 m ceiling at 30.1279552,31.403143 moves 16 of 32,182 vertices, ALL beyond 500 m, worst 0.1031 m (the same capture with the clip left at the MINT moved 0, max 0.0192 m). Matched OFF arm cap/HECA.off3.pkl
HECA  capture  base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/HECA.off3.pkl  — HECA PADS-OFF capture (the shipped law), 186 s, 31,820 vertices / 1,684 faces, guard UNCHANGED - BASE ARM of the v2padqp HECA pair (census ADJUDICATED 26,608; pad_cluster_mismatch 16)
HECA  capture  base 848bf35e   lane v2lemdstruct2    2026-09-15T11:36:11  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/heca_on.pkl  — r4 CONTROL, flip ON arm (solved pickle off the registered v2padqp HECA.off3 capture): verify 30,500 rows. Its matched OFF arm is heca_off2.pkl beside it - ONE variable, the emit.toml one_way_rulings entry for structures.placement foot_row. Delta: verify 30,459 -> 30,500 (+41), airside_no_step 7,794 -> 7,823, 8 of 3,753 runway-family vertices moved > 0.02 m (worst 0.064 m), whole surface max 0.822 m. Only 3 of HECA's 4 foot targets touch airside pavement - the flip is nearly inert here, so LEMD's 5 m is a SITE property
HECA  capture  base 5144df7d   lane v2padqp          2026-09-15T10:51:20  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/HECA.clip.pkl  — THE CLIP-ONLY ARM (--placement pad_airside_clip=true pad_from_cluster=false), 209 s, 30,980 vertices / 1,665 faces, guard shared repo UNCHANGED. §16g (10) (11) r2's interventional attribution: against the pads-OFF arm this arm ALONE moves 4,474 airside vertices worst 1.39 m (runway 17 / 0.100) of the full pads-ON arm's 5,973 / 3.28 m -- three quarters of the airside movement is the ARRANGEMENT CLIP re-noding the airside faces, not any pad row

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

