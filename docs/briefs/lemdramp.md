# Brief pack — lane `lemdramp`

Base: main `4c7da255` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Scout lemdramp: LEMD ramp must stop short of the taxiway; pav188 is a taxiway (owner 1.0.348 read)

## The brief

# Scout `lemdramp` — LEMD 1.0.348 read, items 2–3: the tunnel ramp must stop short of the taxiway; pav188 is a taxiway, not apron

## The owner's read (2026-09-17, app 1.0.348, LEMD tile +40-004 built 19:35; "great progress, almost done")
> 2. "The tunnel ramp here: 40.461311, -3.544781 must stop short of the taxiway, so should end here: 40.4613855, -3.5447716"
> 3. "40.4614416, -3.5452585 is a wide taxiway, not apron."

## What the session measured (read-only; products `/Users/noah/XPTerrainBuilderData/Patches/+40-010/+40-004/`, report `/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+40-004/LEMD/LEMD.report.json`)
- 40.461311,-3.544781 is node −18617 of way −10863 `{"ref": "tunnel_ramp", "role": "tunnel_ramp"}` (11 nodes, alt 571.52 → 570.0), INSIDE `feature:structure_rim:tunnel_wall` (−11018, alt 570.0..576.98). The ramp ring: south end 40.461311 (571.52), 40.461635 (571.0), 40.461959 (570.5), north end 40.462072 (570.0); width ≈ 18 m (lon −3.544569 … −3.544787). Apron `pav188` (−10300, 163 nodes, alt 570.01..585.49, tags `aeroway=apron ref=pav188 shapeID=294`) is 2.0 m from the ramp's south-end node.
- The owner's desired end 40.4613855,-3.5447716 is 8.3 m NORTH of the current south-end node (0.80 m off the ramp's own line), 2.79 m from pav188's line, and INSIDE both the ramp ring and the rim.
- 40.4614416,-3.5452585 is a node of pav188 itself (INSIDE `apron:pav188`). The owner says the shape is a WIDE TAXIWAY.

## Questions (cite file:line and exact numbers; no edits, no builds)
1. WHICH CORRIDOR is −10863: a §34 object corridor (`planar/structures` `object_corridors` / `tunnel_objects`), a door ramp, an OSM bore's mouth ramp, or a §45 channel? Name its record in `LEMD.report.json` (`/planar/structures/*`, `/emit/published/*`), the object or way that states it, its axis and stations, `ramp_grade`, and the mouth rule that placed the south end at 40.461311.
2. THE TAXIWAY: what does apt.dat say shape 294 is (`110` pavement row: name, surface; is it a taxiway by name/`120` centreline coverage) and what did `classify/roles` make it (`apron` — by which rule: area, no centreline, the pavement-classification overhaul scorer v2 …)? Does a taxi centreline (`120`/`taxi_route`) run through pav188 at 40.4614416,-3.5452585? Cite the classifier site that chose `apron` and the rule that would choose `taxiway`.
3. THE RAMP'S END vs THE PAVEMENT: does the ramp/mouth currently lie INSIDE pav188 (overlap area in m², `tools/osm_site.py --relate`), and by how much would ending it at the owner's point shorten it (metres, and the grade the ramp would then need to reach 570.0 from the surface at the new mouth)? Which law places a mouth relative to airside pavement — §34 (8) "A CLIMB STOPPED BY AIRSIDE ENDS AT THE PAVEMENT" / (8) AMENDED "moves its mouth away from airside" (`tools/docq.py spec '§34 (8)'`), §34 (9) the pinched ramp — and is pav188's `apron` role what let the mouth sit 2 m from it (an apron is not "airside" for the mouth rule? cite)? If pav188 were classified `taxiway`, would the existing law already move the mouth to (about) the owner's point? Measure with the classify capture if one exists, otherwise say what replay would.
4. HISTORY: was this ramp identical in the tile the owner last read (1.0.336/1.0.341 LEMD reads, RULINGS 2026-09-14/15 — grep `40.4613`)? Cite any earlier ruling on this ramp/pavement.
5. THE SMALLEST FIX SHAPE(S) (describe, do NOT implement; blast radius via `tools/blast.py`): (a) classification — pav188 → taxiway (which rule, what else at LEMD/other airports flips with it: count shapes affected on the LEMD classify capture); (b) the mouth rule — end the climb N m short of ANY airside pavement incl. apron; (c) an owner-authored override. Name the spec clause each amends and the fastest replay (`v2_solve_replay`, planar `--stage`, INDEX rows) to measure it.
6. Every source you could not verify.

Report as a cited markdown file in your scratchpad AND in full in your final message.

## Spec (design-surface) §34

## §34 RAMPS FOLLOW THEIR ROUTE; ZONES YIELD TO ROADS; A BRIDGE STATES THE CROSSING (Fable 2026-09-13i) — lane `v2rampwalk`, after `v2wallplate`

Scout `v2lemd325t`, items 1, 7, 8: (7a) `_ramp_top` prices a curved approach by the
straight CHORD from the mouth (`planar/structures.py:225-226`), so a ramp whose DEM
condition is met at 271 m runs 420 m of axis (12 of 59 LEMD ramps have axis/chord >
1.3; worst 3.85); and `approach()` tests direction only on the first hop and then
takes the first candidate way at each node (`structure_approach.py:225-233`) — 7a's
second hop turned 90° onto an unrelated road. (7b) the mapped 180° hairpin `-5958`
exists; the ramp stops at 36 m because the DEM there is only 1.9 m above the floor,
then sawtooths (`constraints/structures.py:10-16` bounds consecutive stations by a
`Diff` only). (8) `planar/zones.py:74-78` subtracts CELLS from the zone band; an OSM
road with no cell is never subtracted, and §19's road rule is gated on a crest
(`terrain_edge.py:180-181`) — a 1.73 m step over 1.5 m inside `zone2#2` that no family
prices (`graded_strip` cap None; `adjacent_ground_tear` empty on v2). (1) no bore: the
roads under taxiway bridge F-6 (`aeroway=taxiway bridge=yes layer=1`, OSM −1230) carry
no `tunnel` tag; the DEM's 7.5 m cutting is unmodelled; the taxi surface bathtubs
2.66 m at 5.3 % across it.

1. **A RAMP IS PRICED ALONG ITS ROUTE.** `_ramp_top`'s reach and climb tests read the
   axis length walked, never the chord; the ramp ends at the first station where
   the DEM condition holds ALONG the route.
2. **THE APPROACH WALK KEEPS ITS HEADING.** After the first hop, the walk prefers the
   continuation with the smallest turn and refuses a turn over `[tunnel]
   approach_turn_max_deg` (60) unless the mapped way itself turns (a hairpin's own
   nodes turn gradually); the route stays on the way it entered until that way ends.
3. **A RAMP CLIMBS MONOTONICALLY** from the mouth to its top: the design profile is
   monotone (a one-way `Diff` ≥ 0 per station toward the top) at ≤ the cap.
4. **ZONES YIELD TO ROADS.** The zone band subtracts mapped road ribbons (OSM highway
   ways ⊕ `groundside_cutback_m`) at the single zone derivation site whether or not
   a cell exists; §19's rule 2 runs without a crest. `adjacent_ground:*` faces get a
   within-face step reading in the cockpit block (a welded step > 0.5 m is critical
   visual).
5. **A BRIDGE STATES THE CROSSING.** A road passing under an `aeroway=*` way tagged
   `bridge=yes` (`layer ≥ 1`) seeds an UNDERPASS: the aeroway is a terrain deck at the
   taxi surface (level across the cutting under taxi law), the road a bore with
   mouths and ramps where it leaves the deck's footprint (§29's gate applies).
6. **BARS**: 7a ends at 40.4947925, −3.5817713 ± 15 m at the DEM; 7b runs the hairpin
   and ends near 40.4938154, −3.5817946 at the DEM; item 8's zone face ends at the
   road ribbon (the 1.73 m step gone); item 1's taxiway level across F-6 (the 2.66 m
   bathtub gone) with mouths and ramps either side; axis/chord > 1.3 ramps 12 → 0;
   the other ramps quoted; ONE `--engine v2` LEMD build; census; twins; suite.

### 34.5 **MEASURED** (lane `v2rampwalk`, branch `claude/v2rampwalk` off main `c55141cf`)

ONE tree, one corpus.  Arms, both `--engine v2` LEMD through
`tools/harness/build_airport.py`: **BASE** = main `c55141cf`
(`--base-arm`, artifact `bdeaf64f86bb`, body `4e2c8b856dbe`, 400.0 s,
`status optimal`, verify 1,372) and the **LANE** tree (artifact
`e87162aa889b`, body `fefe03c84963`, 432.8 s, `status feasible`, verify
1,180).  A third, intermediate arm with §34 (5) ARMED is quoted under (5)
(`f4cf494dab92`, body `5e1f083560ab`, 443.8 s).  Dry planar replays
throughout (`planar --stage structures`, `tools/v2_solve_replay.py`
capture 279 s + ~50 s per arm).

**(1) A RAMP IS PRICED ALONG ITS ROUTE — LANDED.**  `ramp_top`'s chord
term is deleted; the reach is the axis walked.  LEMD dry replay: 38 of
49 ramps shorten, total ramp axis **6,158 → 4,658 m (−24 %)**; **axis/chord
> 1.3: 2 → 1** (my instrument counts 2 at base over the 50 tunnel
records, where the scout counted 12 of 59 over the emitted ramp FACES —
two populations, both quoted).  **7a `tunnel:-15327@0`: 420 → 144 m of
axis** (mouth 40.4947815, −3.5829176; top 40.4955757, −3.5823827, at the
DEM 607.50).  **BAR MISSED, and the bar is the thing that moved**: §34 (6)
puts 7a's end at 40.4947925, −3.5817713 ± 15 m, which is the far end of
way −5913 at s = 264 — the ruled mechanism ends the ramp at s = 144,
101 m short of it, because that is the first station where the 8 % climb
from 596.92 meets the DEM ALONG THE ROUTE (607.19 at s = 132 against a
reach of 10.56).  The bar's coordinate was where the DEFECT NODE stood
under the over-long ramp; under (1) no ramp vertex exists there at all.
Ruled tighter than the bar, not looser.

**(2) THE APPROACH WALK KEEPS ITS HEADING — LANDED.**  `[tunnel]
approach_turn_max_deg = 60`, schema'd.  ATTRIBUTION CORRECTION: 7a's
"90° second hop onto −5913's continuation" is not a hop — the walk takes
way −5913 whole (263.9 m, turn 0.4° at the mouth) and the 90° is INSIDE
−5913's own nodes, which §34 (2) exempts by construction.  The clause
DOES bite at 7b: at −5958's far end the old walk took the first candidate
in load order, −15331 at 33.3°, with −15328 at 2.3° beside it.  Corridor
churn from the shorter ramps: 3 bores lost, 2 gained (31h overlap pairs
swapping which side is refused); LEMD tunnels 50 → 49.

**(3) A RAMP CLIMBS MONOTONICALLY — LANDED, WITH A PRICE.**  One one-way
`Offset(hi, lo, 0)` per consecutive station of the climb, sense taken
from the ramp's own ends so a mouth topping BELOW its datum stays
feasible.  LEMD offsets 296 → 690.  THE PRICE, measured on the replay
(one variable, `RW_NO_MONO`): the design solve goes `optimal` →
`feasible` — the active set does not settle inside its round cap (175
rounds, 69 rows flipped, worst 0.010 m); with the monotone rows off, the
same tree solves `optimal`.  And with the profile pressed onto the cap
the emitter has no rounding headroom (12p's flagged class): `within_shape`
2,769 → 3,616, +847 rows, ALL `tunnel_ramp|tunnel_ramp` groundside pairs
at 8.02–8.03 % against the 8.00 % cap, worst |de| 19.02 m at
40.47968, −3.58206.  They are out of scope (groundside, priced at the
cap's own noise), and the ADJUDICATED count still falls — see the census
— but the instrument moves a long way and the solve status is worse.

**(4) ZONES YIELD TO ROADS — LANDED.**  `road_lines` now returns AT-GRADE
centrelines only (a bored or bridged road is not the surface — one
derivation, both consumers); `road_ribbons` grows them by
`road_profile.lane_width_m + groundside_cutback_m` ⊕ the snap; the ribbon
enters `clip_to_terrain_edge` as a BARRIER beside the crest, so the band
ends at it and does not resume beyond it; §19 rule 2 runs with an empty
crest.  RECORDED DEVIATION: §19.2 (2)'s "flush at the road's OUTER edge"
is amended to the INNER edge for a cell-less road — the outer-edge
reading was written for a road that HAS a cell, whose ⊕ cut-back is
subtracted anyway; read literally it leaves the band standing on the
road.  §19's own twin carries the amendment and its reason.  The new
census family `adjacent_ground_step` (§34 (4)'s cockpit reading) is
registered in `LAW_FAMILIES`, in `law/families.toml` (`cockpit = "step"`)
and in the engine's own `verify/strips.adjacent_ground_step`, so the
v1/v2 lockstep twin passes; its floor is `visual_m` AND `cliff_grade` in
ONE step — without the cliff term it counts the lawful hillside drape
(measured CYXY 296 rows).  RESULT: `adjacent_ground_step` **3 → 1** at
LEMD; the base's 1.63 m at 40.4856895, −3.5884014 and its 0.82 m at
40.4609353, −3.5409609 are gone.

**(5) A BRIDGE STATES THE CROSSING — IMPLEMENTED, NOT ARMED; A RULING IS
OWED.**  `planar/structure_underpass.py` (`is_aeroway_bridge`,
`underpass_bores`, `approach_along`) plus `[tunnel] underpass_min_layer`
/ `underpass_min_span_m`.  The predicate had to be LOCAL: the shared
`is_bridge_way` requires `highway` or `railway`, so an aeroway bridge is
invisible to every deck pass — which is exactly why nothing was seeded.
The deck's half-width is read off the taxi CELL the aeroway stands in
(`pavement_half_widths` cannot answer it: its ±2 m centre test asks
whether a pavement TRACES a road, and a junction blob's across-axis
centre is metres off the centreline it contains) — LEMD F-6 reads 7.6 m
where the lanes fallback reads 3.5.  MEASURED with it armed
(`f4cf494dab92`): `underpasses 1`, way −1230's two service roads bored,
31h-merged into ONE ramp, mouths at 40.4610903, −3.5446736 and
40.4612284, −3.5446741, ramps 96 / 84 m, floor 564.90 = DEM(mouth) 570.00
− `bore_datum_m`.  AND THE COCKPIT GOT WORSE: **CRITICAL VISUAL 3 → 10**,
seven of the ten at 40.46100, −3.54455, `strip_seam_tear` **0 → 4** — the
portal RIM takes `DEM(mouth)` = 570.0, the road's ground down in the
cutting, against a taxi surface solving ~573.5 above it, so the abutment
reads as a 3.52 m cliff.  §34 (5)'s other half — "the aeroway is a
terrain deck at the taxi surface, level across the cutting under taxi
law" — has NO DEM source (the DEM carries no bridge): the abutment rim
would have to take the TAXI CELL's own SOLVED value, a new relational
law.  That is an owner/Fable ruling, so the lane stopped at its attempt
cap, unwired the call, and left the module and its twins standing with
the measurement.  KCLT taxiway U (13q item 3) is UNMEASURED: every KCLT
load in a lane worktree is refused by the pack-dump freshness guard
(`airport/load.py:289`, 13q's own chip — the `.dsf.anchor_bak` is newer
than the cached dumps), and `--refresh-data` is not a lane's to run.

**(6) ITEM 9'S DECK END — HALF LANDED, THE RESIDUAL ATTRIBUTED.**
`deck_ends` now takes the nearest governed cell within `[bridge]
deck_end_reach_m` (25 m) when no cell stands under the mapped end, so
LEMD way −6288's east end reads `pav92` (13.3 m away, solved 606.60)
instead of nothing.  IT DOES NOT MOVE THE DECK, and the replay says why:
§33 (4)'s tie is a ONE-WAY lower bound (`Offset(deck, apron, 0)`) and the
deck already stands 2 m ABOVE the apron.  THE RIM/DECK VERTEX COUPLING,
ruled: six of the ten `bridge_deck:-6288` vertices carry the corridor
RIM as well, but the rim's DEM pin is already skipped there — a deck face
is `service_road`, a governed role, so `shared_with_ground` holds and the
DECK's law governs the shared node.  The coupling is therefore NOT what
holds the deck up.  What holds it up is its own end profile: the face
spans t 0.157…0.787 of the way (13.3…66.3 m of 84.3 — it is the CORRIDOR
crossing, and "the deck face reaches the way's end" is REFUSED as
geometry: beyond the trench the road is ordinary ground), and the
interpolated `Band` lo runs 609.29 at the west edge down to 606.93 at the
east, from a WEST end whose DEM is 609.99 — a real embankment the road
really comes off.  The solve leaves the deck at 608.26…609.31, i.e.
1.3–1.7 m ABOVE its own east lo, because nothing pulls it down: the lo is
one-way and the apron tie is one-way.  BAR MISSED (0.3 m of the apron at
the east end): the deck ends 1.66 m above it.  The lever that would meet
it is a two-sided materiality window on the end profile instead of a
lower bound — which §33 (4) ruled out ("a bound, never a pin") and 13r
measured as a regression in its face-extent form; it needs a ruling.

**CENSUS** (harness, law-true, both arms in this tree): TOTAL 3,591 →
4,278; **ADJUDICATED 1,181 → 1,055 (−126)**; out of scope 2,410 → 3,223.
By family: `airside_no_step` 417 → 338, `transverse` 79 → 48, `taxi_box`
235 → 178, `road_cross_section` 22 → 18, `strip_transverse` 39 → 37,
`adjacent_ground_step` 3 → 1, against `within_shape` 2,769 → 3,616 (the
(3) ramp-cap pairs above), `resa_transverse` 1 → 5, `strip_longitudinal`
14 → 19, `plane_gradient` 0 → 3, `mid_edge_step` 0 → 1.

**THE COCKPIT BLOCK.**  CRITICAL MOTION 1 → 2 (both `strip_arc` grade
breaks; worst 0.610 → 0.520 m, the new one 0.400 m over 25.76 m at
40.4597648, −3.5495209).  CRITICAL VISUAL 3 → 2 — but the WORST row is
worse: 1.630 m over 1.5 m → **8.500 m over 12.03 m** at
40.5331907, −3.5748496, and it is (4)'s.  Attributed: at 18R/36L's north
end the ribbon barrier trims `adjacent_ground:runway:4:zone2#21`
(155 nodes, 597.88…609.25) to `#23` (37 nodes, 599.45…607.95,
`o4_edge = "road"`), and the trimmed boundary runs straight down the
slope at the arrangement's own chord cap — one 12.03 m ring edge carrying
8.50 m where the untrimmed face spread the same drop over many.  The
trim's boundary needs densifying below the chord cap on a slope; owed.

**SUITE** `tests/auto_patch_v2` + `tests/test_harness.py`: 1,125 passed,
1 skipped, twice.  The v1 tunnel / bridge / ramp / portal set: 904
passed, the SAME three pre-existing reds 13r named
(`test_tunnel_portal_fidelity::TestClearanceAnnulus`,
`test_object_anchor::test_kclt_eight_bake_pool_end_to_end`,
`test_tunnel_ramp_run_merge::TestItIsNotAPostPass`).  One behaviour-
neutral move to stay under the 1,000-line budget: `StructureStats` out of
`planar/structures.py` into `planar/structure_stats.py`, proved by two
`--stage structures` LEMD replays whose `structures.json` differ only in
their timing fields.

### 34.6 **MEASURED, ROUND 2** (lane `v2rampwalk`, `claude/v2rampwalk` merged onto main `864e7577`)

Arms, both `--engine v2` LEMD, ONE tree, one corpus, the shared-repo guard
clean on both.  **BASE** = main `864e7577` (`--base-arm`, artifact
`439c6493b02c`, body `667e8c2761ed`, 430.5 s, `status optimal`, verify
1,431).  **LANE** = this tree (artifact `6afd79da37d2`, body
`c482e5366f6c`, 449.1 s, **`status optimal`**, verify 1,290).  An
intermediate lane arm — before the round-2 attempt 2 on §33 (4) / §34 (5)
and with the densifier still in — is `1498afa25daa` (body `2411176dea57`,
428.2 s, `feasible`) and is quoted where it isolates a mechanism.

**CENSUS**: TOTAL 3,698 → 4,363; **ADJUDICATED 1,215 → 1,154 (−61)**; out
of scope 2,483 → 3,209.  `taxi_box` 240 → 193, `transverse` 80 → 49,
`airside_no_step` 433 → 408, `strip_transverse` 44 → 37, against
`within_shape` 2,848 → 3,574 and `road_cross_section` 23 → 58.

**COCKPIT, both arms.**  BASE: CRITICAL motion 2 (worst 0.430 m over
58.03 m, `strip_arc` at 40.4625636, −3.5525152), CRITICAL visual 3 (worst
1.720 m over 1.5 m, `adjacent_ground_step` at 40.4856895, −3.5884014).
LANE: CRITICAL **motion 2 → 1** (worst 0.230 m over 66.18 m at
40.4928034, −3.5741300), CRITICAL **visual 3 → 11** (worst 8.490 m over
12.03 m at 40.5331907, −3.5748496; then 5.29 m at 40.4609964, −3.5416344
and 40.4610048, −3.5445453).  The visual regression is (3)'s and (5)'s,
attributed below.

**§34 (6) THE RAMP PROFILE SITS UNDER THE CAP — LANDED, BAR MET.**  Each
ramp pair is priced `cap − hard_tol_m / d`.  `within_shape`
`tunnel_ramp|tunnel_ramp` **20 (base) → 28 (lane)**: round 1's +847 rows
at 8.02–8.03 % against the 8.00 % cap are GONE (the +8 is the two extra
underpass ramps).  And the design solve is back to **`optimal`** — round
1's `optimal → feasible` was the monotone profile pressed onto the cap;
one `hard_tol_m` of headroom settles the active set (208 rounds, no
"SET NOT SETTLED" line).

**§33 (4) A DECK END IS AN EQUALITY — LANDED, BAR MET.**  The end group
takes a two-sided `Offset(deck, pavement, ±split_tol_m)` to the governed
cell `deck_ends` found, and the cell's nearest vertex is now measured
FROM THE WAY'S OWN END, not from the deck polygon (the face is the
corridor crossing and stops 18 m short, so the polygon's nearest apron
vertex stood 33.8 m away on a 470-node apron).  LEMD `bridge_deck:-6288`
east-most vertex **608.25 → 607.65** against the `pav92` vertex 13.4 m
from the way's east end at **607.47**: a gap of **0.18 m**, inside
`split_tol_m` 0.3 (round 1: 1.66 m).  NOTE FOR THE RECORD: the equality
is two-sided, so BOTH ends moved — that apron vertex went 606.60 → 607.47
while the deck came down 0.60 m.  West end 609.28 → 608.84 against its
DEM chord window 609.38 ± 0.3 (0.54 m under it; the west end runs onto an
unclassified road and has no governed cell to tie to).

**§34 (5) THE PORTAL RIM UNDER A DECK — PARTLY LANDED, BAR MISSED.**
`structure_underpass.py` is ARMED; LEMD reports `underpasses 1`, taxiway
F-6 way −1230 (deck half-width 7.6 m read off its own taxi cell, clip
5.5 m), both service roads bored and 31h-merged, `tunnel:-5821+-5820@0/@1`
mouths at the abutments, ramps 96 / 84 m, floor 564.90, and both records
carry the mark `underpass under aeroway -1230`.  TWO cures were built:
(a) the clip is shrunk by the rim stand-off so the corridor's end cap
lands ON the taxi cell, and (b) an underpass rim vertex standing inside a
governed pavement cell takes a two-sided `Offset` (offset 0) to that
cell's nearest vertex instead of `_rim_rows`' DEM pin.  MEASURED: the rim
way at the mouth now runs **570.0…576.07** where the taxi cell `pav157`
is at 576.45 — the shared half took the deck.  THE BAR IS STILL MISSED:
CRITICAL visual at the site is not 0 and `strip_seam_tear` is 2, not 0.
The residual is a DIFFERENT face: the 5.29 m row is
`graded_strip|junction` between `adjacent_ground:taxi:E:zone1#75`
(568.66…575.52), the ADJACENT-GROUND band the corridor cut, and the
taxiway at 576.45 — the zone band beside the trench follows the trench
down.  That is the zone law beside a structure, not the rim's datum, and
it is outside both this clause's text and this lane's attempt cap.

**KCLT ITEM 3 — MEASURED BY REPLAY (no build).**  Main's load cure works:
with `auto_patch.engine_v2.fresh_pack_dump` in the inputs KCLT loads in a
lane worktree.  KCLT carries **124** `aeroway` + `bridge` ways, of which
**3** reach `underpass_min_layer` — the 121 others are JET BRIDGES
(`aeroway=jet_bridge bridge=yes highway=footway`, no `layer`), which the
layer gate excludes by construction.  **Taxiway U, way −1560** (deck
half-width 18.0 m, clip 15.9 m): **2 roads bored**, one of them the
untagged tertiary −13664, mouths at **35.2015761, −80.9403453** and
**35.2018654, −80.9403264** — 21.4 m and 40.2 m inside 13ai's bar
coordinates (35.2013838 / 35.2022266, −80.94041), which mark the bridge's
own ends rather than the abutments the clip puts the mouths at.  Two more
underpasses at KCLT: taxiways −71 and −70 (deck half-widths 6.4 / 5.6 m,
one road each, 8.6 / 6.9 m of bore — just over `underpass_min_span_m`).
No KCLT BUILD was run: the LEMD build is the round's one closing build.

**§34 (4) A TRIMMED BOUNDARY IS DENSIFIED ON A SLOPE — REFUTED AND
DELETED.**  Built as ruled (`visual_m` of DEM change per ring edge, on the
trim's own new edges only): it inserted 402 stations and the 8.50 m row
DID NOT MOVE (8.500 → 8.490).  Attributed on the arm that removed it: the
edge carrying the row is **A 40.5332464, −3.5760707 z 599.45 → B
40.5331383, −3.5760707 z 607.94, 12.03 m apart** on
`adjacent_ground:runway:4:zone2#24`'s ORIGINAL outer ring — the trim
removed the material beside it, it did not create it, and the densifier
deliberately does not insert into a region's own welded edges.  The
`graded_strip|graded_strip` `within_shape` count is **671 without the
densifier and 704 with it** against **0** in the base, so the 671 are the
TRIM's price and only 33 were the densification's.  The builder is
deleted (the comment at the call site and git are its record); the open
question — a trim that follows the contour instead of cutting across it —
is named there and is not this lane's to rule.

**SUITE** `tests/auto_patch_v2` + `tests/test_harness.py`: **1,214 passed,
1 skipped, twice**, after the merge and again at the end.  The v1 tunnel /
bridge / ramp / portal set: 904 passed, the SAME three pre-existing reds
13r named.  Files under the 1,000-line budget throughout
(`structures.py` 953, `structure_approach.py` 898,
`constraints/structures.py` 961, `structure_underpass.py` 261).

### 34.7 **MEASURED, ROUND 3** (lane `v2rampwalk`, `claude/v2rampwalk` merged onto main `f866e8bb`)

§34 (4) NARROWED as ruled: the general road trim is WITHDRAWN (the ribbon
barrier, `road_ribbons`, and §19 rule 2's crest un-gating are deleted;
§19.2 (2) reads at the road's OUTER edge again, as originally ruled), and a
zone band now yields ONLY to a TUNNEL CORRIDOR — `Classification.keepouts`,
the mouth/ramp/trench/underpass outer rings the structure pass publishes —
subtracted with the SAME `groundside_cutback_m ⊕ snap` stand-off a
groundside cell gets, so the band never shares a vertex with the corridor's
rim and the gap terraces against the ramp walls.  §34 (5), §34 (6) and
§33 (4) stand exactly as round 2 landed them.  One derivation site, so
§19.3's consumer table still holds verbatim.

Arms, both `--engine v2` LEMD, one tree, one corpus, shared repo unchanged.
**BASE** = main `f866e8bb` (`--base-arm`, artifact `00ddff5c133a`, body
`667e8c2761ed` — byte-identical to round 2's base, which confirms
`f866e8bb` is docs-only over `864e7577` for LEMD — 418.0 s, `optimal`,
verify 1,431).  **LANE** artifact `0f6002e1aaf2`, body `bf66853f153a`,
444.2 s, **`optimal`**, verify 1,322.

**CENSUS**: TOTAL 3,698 → **3,572 (−126)**; **ADJUDICATED 1,215 → 1,156
(−59)**; out of scope 2,483 → 2,416.  `transverse` 80 → 51, `taxi_box`
240 → 210, `airside_no_step` 433 → 410, `strip_transverse` 44 → 36,
`within_shape` 2,848 → **2,785 (−63)**, `adjacent_ground_step` 3 → 1,
`raoa` 1 → 0, `cross_shape` 1 → 0, against `road_cross_section` 23 → 50.

**THE COCKPIT BLOCK, both arms.**  BASE: CRITICAL motion **2** (worst
0.430 m over 58.03 m, `strip_arc` at 40.4625636, −3.5525152), CRITICAL
visual **3** (worst 1.720 m over 1.5 m at 40.4856895, −3.5884014).
LANE: CRITICAL motion **2** (worst 0.430 → **0.070 m** at the same
`strip_arc`; the second is a NEW 0.060 m welded `frontage_near_miss` step
at 40.4668804, −3.5698264), CRITICAL visual **3 → 1**, worst
**0.560 m over 0.5 m**, `adjacent_ground_step [apron|graded_strip]` at
40.4609843, −3.5450536.

**BARS.**
* CRITICAL visual ≤ 3 — **1** ✅; NO row at 40.5331907, −3.5748496 ✅
  (the 8.49 m edge is back inside `zone2`'s interior, spread as before);
  none at F-6's 40.4609964 / 40.4610048 ✅ — the 5.29 m rows and both
  `strip_seam_tear` rows are GONE (`strip_seam_tear` 0 on both arms).  The
  ONE surviving visual row stands 33 m east of them at 40.4609843,
  −3.5450536 and is 0.560 m over 0.50 m — an apron↔band lip in the
  approach corridor, an order of magnitude under what it replaced.
* `graded_strip|graded_strip` `within_shape` ≤ base + 20 — **0**, against
  0 in the base (round 2: 671) ✅.
* item 8's 1.63 / 1.72 m row at 40.4856895, −3.5884014 — **absent** ✅
  (`adjacent_ground_step` 3 → 1): the road there is AT A TUNNEL, so the
  corridor subtraction is what removes it, which is the ruling's point.
* item 9's deck end ≤ 0.3 — `bridge_deck:-6288` east 608.25 → **607.67**
  against the `pav92` vertex 13.4 m from the way's east end 606.60 →
  607.49: gap 1.65 → **0.18 m** ✅.
* `optimal` — **held** ✅ (both arms).
* 7a / 7b — **held**: `tunnel:-15327@0` top **144 m** (was 420),
  `tunnel:-5980@0` top 36 m; `tunnel_ramp|tunnel_ramp` `within_shape`
  20 → **26**, no cap-riding population ✅.
* KCLT item 3 — **unchanged by replay**: 124 aeroway+bridge ways, 3 at
  `underpass_min_layer` (121 jet bridges), taxiway U −1560 bores 2 roads,
  mouths 35.2015761 / 35.2018654, −80.94034; taxiways −71 and −70 one road
  each.  No KCLT build.
* SUITE `tests/auto_patch_v2` + `tests/test_harness.py`: **1,220 passed, 1
  skipped, twice**.  The v1 tunnel / bridge / ramp / portal set: 860
  passed, the two pre-existing reds 13r named that live in it
  (`test_tunnel_portal_fidelity::TestClearanceAnnulus`,
  `test_tunnel_ramp_run_merge::TestItIsNotAPostPass`).

**WHAT ROUND 3 DID NOT SETTLE.**  `road_cross_section` 23 → 50 (+27) —
groundside road faces re-priced by the corridor stand-off; all out of
scope, none critical.  The new 0.060 m welded motion row at
40.4668804, −3.5698264.  The 0.560 m visual row above.  `road_lines`
keeps round 1's AT-GRADE filter (a `tunnel` / `bridge` way's centreline is
not the surface): it only NARROWS §19 rule 2 and creates no trim.

### §34 (4) NARROWED — A ZONE BAND YIELDS ONLY TO A TUNNEL CORRIDOR (Fable 2026-09-13; RULINGS 2026-09-13ar) — lane `v2rampwalk` round 3

Round 2 (8e101597): the general "zones yield to roads" trim exposed
`zone2#24`'s original outer ring (8.49 m over 12.03 m at 40.5331907,
−3.5748496 — the band used to spread that terrain across its interior) and
cost 671 `graded_strip|graded_strip` rows; the densifier cannot insert into a
region's own welded edges (refuted). At F-6 the zone-1 band followed the
underpass trench down (5.29 m rows).

4. **THE CORRIDOR, NOT THE ROAD.** A zone band yields only to a TUNNEL
   CORRIDOR — the mouth, the ramp, the trench and the underpass corridor as
   §34 (1)–(3) and (5) price them — which is SUBTRACTED from the band; the
   band's boundary there is the corridor's own edge (terraced by the ramp
   walls). A road elsewhere inside adjacent ground grades WITH the zone (the
   standing law). Owner item 8 (a road at a tunnel) is the corridor case.

BARS (round 3, ONE LEMD build with `--base-arm`): CRITICAL visual ≤ 3 with
no row at 40.5331907, −3.5748496 and none at F-6 (40.4609964 …
40.4610048); `graded_strip|graded_strip` `within_shape` ≤ base + 20 (round
2: 671); item 8's 1.63 m row absent; item 9's deck end ≤ 0.3 (round 2:
0.18); `optimal`; 7a / 7b ramp bars hold; KCLT item 3 by replay unchanged;
suite twice.

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

### §34 (4) NARROWED — A ZONE BAND YIELDS ONLY TO A TUNNEL CORRIDOR (Fable 2026-09-13; RULINGS 2026-09-13ar) — lane `v2rampwalk` round 3

Round 2 (8e101597): the general "zones yield to roads" trim exposed
`zone2#24`'s original outer ring (8.49 m over 12.03 m at 40.5331907,
−3.5748496 — the band used to spread that terrain across its interior) and
cost 671 `graded_strip|graded_strip` rows; the densifier cannot insert into a
region's own welded edges (refuted). At F-6 the zone-1 band followed the
underpass trench down (5.29 m rows).

4. **THE CORRIDOR, NOT THE ROAD.** A zone band yields only to a TUNNEL
   CORRIDOR — the mouth, the ramp, the trench and the underpass corridor as
   §34 (1)–(3) and (5) price them — which is SUBTRACTED from the band; the
   band's boundary there is the corridor's own edge (terraced by the ramp
   walls). A road elsewhere inside adjacent ground grades WITH the zone (the
   standing law). Owner item 8 (a road at a tunnel) is the corridor case.

BARS (round 3, ONE LEMD build with `--base-arm`): CRITICAL visual ≤ 3 with
no row at 40.5331907, −3.5748496 and none at F-6 (40.4609964 …
40.4610048); `graded_strip|graded_strip` `within_shape` ≤ base + 20 (round
2: 671); item 8's 1.63 m row absent; item 9's deck end ≤ 0.3 (round 2:
0.18); `optimal`; 7a / 7b ramp bars hold; KCLT item 3 by replay unchanged;
suite twice.

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

### §34 (8) A CLIMB STOPPED BY AIRSIDE ENDS AT THE PAVEMENT; THE REFUSAL IS THE RAMP'S, NEVER THE CORRIDOR'S (owner RULINGS 2026-09-14n item 2; Fable 2026-09-14; RULINGS 2026-09-14p) — lane `v2othhfix`

When `stop_and_steepen` cannot reach the ground inside `max_ramp_grade`
before the axis enters airside pavement, the ramp ENDS at the pavement edge
at the grade it has, and the residual step is taken by a PORTAL / RIM FACE at
the pavement boundary (a retaining wall — what the pack authors there); the
airside cell is never pulled (airside is king).  A corridor whose trench is
otherwise lawful is CUT with its mouths (§33 (2)); the report names the ramp
refusal and the portal height.  Measure first: the stopped station is snapped
one `grid` short of the cell boundary (`wall_corridor_ramps.py:133`) — at
OTHH `Terminal_Base_2_5.obj@0` the miss is 1.0 pp over 17.1 m (1.88 m of
rise); if recovering that half-metre makes it lawful, say so, and still land
the portal rule for the next one.  BARS: the corridor under the terminal at
25.26621, 51.61134 CUT (trench + both mouths), the portal faces named with
their heights; the five `Terminal_Base_2_1` corridors unchanged; no airside
vertex moves.

### §34 (8) AMENDED — A CLIMB THAT CANNOT REACH AIRSIDE MOVES ITS MOUTH AWAY FROM AIRSIDE (owner RULINGS 2026-09-14u; supersedes the portal of 14p) — lane `v2othhfix`

When `stop_and_steepen` cannot reach the ground inside `max_ramp_grade`
before the axis enters airside pavement, the corridor's MOUTH is moved away
from the airside edge — toward and if need be under the building — by the
run the cap needs (rise / `max_ramp_grade` − the run available); the trench
lengthens by that amount, the ramp runs at the cap from the moved mouth to
the ground, and the corridor reaches full depth under the building.  No
portal step; the airside cell is never pulled; the report names the moved
mouth and the metres it moved.  BAR: `OTHH_Terminal_Base_2_5.obj@0` cut with
both mouths, each mouth's move named (the /a side needs ≥ 1.7 m more run at
10 %); the five `Terminal_Base_2_1` corridors unchanged.

### §34 (9) THE PINCHED RAMP (owner RULINGS 2026-09-14ak; Fable 2026-09-14) — lane `v2othhfix`

"All the ramps leading down into/under the terminal are coming out too far
and pulling down the service road edge."  When a corridor's climb-out would
reach a SERVICE ROAD LOCKED TO AIRSIDE (a road edge-sharing or absorbed into
airside pavement, or whose level is an airside contact under §37 (10))
before it reaches the ground:
1. the ramp ENDS at the road edge; the road edge keeps its airside-locked
   level and is never pulled;
2. the ramp runs from that road edge down to the ramp bottom at the
   BUILDING EDGE (the corridor mouth), and the grade cap is LIFTED for that
   pinched run — whatever grade the span requires is lawful;
3. the report names each pinched ramp (`pinched_ramp`: corridor, road,
   span, grade); §34 (8)'s mouth move applies only where no such road
   pinches the climb.
BARS (OTHH, ONE build): every terminal ramp that today extends into a
service road ends at the road edge (list them: corridor, road way, the
road edge's level before → after — unchanged); the ramp bottom at the
building edge unchanged; the pinched grades named; the road-family census
(`road_cross_section`, `road_ramp`, airside vertices moved 0) before →
after; no ramp under the terminal shortened or lost.

### §34 (9) (4)–(5) THE PAINTED ROAD EDGE; FULL DEPTH AT THE BUILDING WALL (owner RULINGS 2026-09-14aq) — lane `v2othhfix`

4. Where the pack carries a road-edge MARKING — a draped `markings` object
   (the class §42 refuses as pavement) whose line runs along the road within
   `road_edge_line_reach_m` (6 m) of the road face's edge and within
   `road_edge_line_parallel_deg` (15°) of it — the pinched ramp ends at the
   PAINTED LINE; the marking witnesses where the road really is.  Without
   one, the face edge stands.  The report names which witness each pinched
   ramp used.
5. The ramp's full-depth point is the corridor's COVERED START — the
   building wall — never the outer end of the retaining-wall bands that
   protrude from it; the protruding stretch is ramp.  BARS (OTHH, ONE
   build): the two pinched ramps end at the painted line east and west
   (named with the marking object and the offset from the face edge);
   `Terminal_Base_2_5@0/a` full depth at the building wall (the ~4 m of
   protruding wall added to the run — the pinched grade before → after);
   airside 0; road edges unchanged.

### §34 (10) THE ROAD MARGIN IS GENERAL (owner RULINGS 2026-09-14bb/bc/bd) — lane `v2othhfix`

Every ramp arriving at a road — a pinched corridor climb (§34 (9)), a §34
(8) climb-out, a basin ramp (§24 (8)), a structure approach, a
tunnel-object ramp — ends at the road's TRUE EDGE: the centreline offset by
the road's half-width toward the ramp; the road ribbon is never cut by a
ramp.  One derivation, `road_true_edge(road, side)`, reading the road's own
width (the emitted ribbon / route-frame extent / `road_width_m`), used by
every ramp emitter; no per-airport key.  Census `ramp_in_road` (CRITICAL): a
ramp vertex inside a road ribbon.  BARS: OTHH's two pinched ramps' tops move
in by the road's half-width (named); `ramp_in_road` 0 on the five registered
frames (each airport's count before → after); road ribbons uncut; airside 0.

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

### §34 (11) **MEASURED — THE ROAD IS NAMED, THE "PULL" IS REFUTED AS STATED, AND THE VOID IS THE 9 m CUT** (lane `v2lemdstruct2`, base main `da8e5d7f`)

Same registered capture and the same matched replay arms as §33 (5).
The base arm REPRODUCES the scout's read station for station: along the
owner's own segment 40.494628,−3.5832911 → 40.4943869,−3.5823239, all
twelve stations read `cross_connector:pav61` + `feature:
gap_interior_ring:` + `graded_strip:adjacent_ground:taxi:F:zone2#18` and
nothing else; the hole-ring census (`role_overlap_read --hole-rings`)
reports the ring as **way −10671, 144,429.5 m², cover 0.011, inscribed
width 362.39 m, VOID at 40.4946503,−3.5835473** — the ruling's own
figures, in this tree's own ids.  LEMD carries **25** `gap_interior_ring`
rings (1,310,382 m²), **13 of them over 10,000 m²**.

**(a) THE ROAD IS OSM WAY −5944** — `highway=service`, `lanes=2`, 11
nodes, in `OSM_data/+40-010/+40-004/+40-004_airport_small_roads.osm.bz2`.
Its polyline passes **0.14 m** from the owner's first point and its long
segment runs 40.4948064,−3.5838872 → 40.4944780,−3.5827984, the owner's
own line; the second point is 1.13 m from `−15332` (`highway=service`)
and 5.41 m from `−5980` (`highway=service tunnel=yes`), the south bore.
**It is in the feed and it is not in the patch, and the two gates are
named:**

1. `classify/evidence._osm_roads` intersects every OSM road centreline
   with `ev.pavement_union` before it becomes a `Chain` — an OSM road is
   admitted as EVIDENCE for a page's class (strip / lot), never as
   geometry of its own.  −5944 runs through pav61's 144,429 m² HOLE, so
   the intersection is empty and no chain exists.
2. `classify/roles` mints road-family FACES from `ev.truck_chains` alone
   — the authored 1206 routes — differenced against the pavement, pad and
   runway unions.  There is no 1206 route here, so no face, so no §37
   row of any kind.

**(b) NO RIM PULLS ANYTHING HERE — THERE IS NOTHING TO PULL.**
`--why-at 40.4940268,−3.5826498 --site-radius 60` on the base solved arm:
16 vertices within 60 m, roles `['retaining_wall', 'tunnel_ramp']` ONLY,
z−DEM mean **+0.03**, min −1.41, **max +1.41**.  The worst vertex is
v18924 at **z 603.32, DEM 601.91 — 1.41 m ABOVE its own ground**, held by
one `structures` FLAT row and, in the tool's own words, "no terminal
reached — the objective holds it".  Nothing lowers the ground at the
owner's point; the rim is pinned at its own DEM by station
(`tunnel.crest = dem`).  Read on the emitted patch, the nearest emitted
way to the VOID point 40.4946503,−3.5835473 is **48.45 m** away.

**WHAT THE OWNER IS SEEING, MEASURED ON THE DEM.**  The ground between
the two mouths is a **611 m plateau**, and the two mouths stand at the
bottom of a real cutting:

| along mouth −15327@0 → mouth −5980@0 (88.7 m) | DEM |
|---|---|
| 40.4947815,−3.5829176 (the north mouth) | **602.02** |
| 7.4 m | 602.64 |
| 14.8 m | **607.61** |
| 22.2 m | 610.30 |
| 29.6 – 66.5 m | **611.00** (the plateau) |
| 81.2 m | 610.32 |
| 40.4940096,−3.5826576 (the south mouth) | 607.79 |

and the owner's road line reads **610.98 … 611.06 … 610.09** over its
whole 86 m.  So: the patch owns the two corridor rings (rims at 602.16
and 601.69) and **NOTHING** in the 88.7 m between them, where the ground
rises to 611 — an unowned 9 m cut, 144,429 m² of it, with no zone band
(the corridor keepout subtracts it at `zones.groundside_cutback_m`) and
no bank (this arm reports `0 rings banked`).  That is "the ground is
getting pulled down": not a row pulling a vertex, but a **plateau with no
owner between two 9 m-deep cuts**, which is exactly the shape clause (c)
names and exactly what the owner's own remedy — "provide a smooth sloping
road grade for the road here" — would give it, since way −5944 stands ON
the plateau at 610–611.

**WHAT THIS LANE DID NOT DO, AND WHY.**  Clause (a) is a NEW SHAPE CLASS
in the layout — a road-family face population that does not exist today —
and owner RULINGS 2026-08-30l requires the consumer census of every pass
that reads road-family geometry (§37 (1) caps, the cross-section, §37 (6)
the ramp, §37 (7) the route pricing, §27's flip, `road_law_caps`, the
bank, `zone_regions`' groundside cutback, `emit/osm_adapter`) in ONE table
BEFORE any consumer is edited.  That census is the next round's first
work, and it now starts from a named way, two named gates and the DEM
profile above rather than from a coordinate.  Clause (b) is REFUTED AS
STATED at this site (no pull row exists) and clause (c)'s remedy is
clause (a)'s: the void is covered by giving the plateau its road.

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

### §34 (5) (b) **MEASURED** (lane `v2lemdstruct2`, branch `claude/v2lemdstruct2`, base main `da8e5d7f`)

Same registered capture and the same matched `v2_solve_replay` arms as
§33 (5); §34 (5) (b) needs the PLANAR stage, so its arms are
`--from planar`.  The base arm reproduces the ruling's read exactly:
`tunnel:-5821+-5820@0` (note `underpass under aeroway -1230`), rim way
−10987 at **577.84** against ramp way −10911 at **572.02…572.42**,
**12.77 m / 15.46 m** from the owner's node — a **5.42 m** face inside
`adjacent_ground:taxi:E:zone1#69`, which begins at 16.2 m.  Read on the
planar map, ramp face 961 carried **2 of its 12** ring vertices inside
the code-E strip and rim face 356 **9 of 25**, its nearest vertex 0.00 m
from the pavement.  In the harness census that face is the airport's
**worst CRITICAL VISUAL row**: `strip_transverse [runway|tunnel_ramp]
5.589 m over 13.72 m at 40.4605077,−3.5446406`.

**THE FIX — ONE DERIVATION, NO NEW CONSTANT.**
`planar/structure_underpass.strip_half_width_m(law, cell)` is the zone
law's own `zone2_half_width_m` for the cell's class (code NUMBER for the
runway family, code LETTER for the taxi family), falling back to
`zones.adjacent_ground.lip_width_m` where the class declares no strip —
the ruling's own words.  `_deck_cell` adds it to each station's two kerb
offsets, so `_cell_ribbon` (§34 (5) (a)'s asymmetric clip) erodes from
pavement-edge **plus strip**.  The DECK's own half width is untouched:
`_deck_half_width` passes no `law`, so a 19 m strip never becomes 19 m of
deck.  The census family `ramp_in_strip` reads the same derivation from
the other side.

| bar | BASE | §34 (5) (b) |
|---|---|---|
| trench mouth from the owner's node 40.4611623,−3.5444804 | **12.77 m** (rim) / **15.46 m** (ramp) | **31.06 m** / **33.43 m** — BEYOND the 19.0 m code-E strip |
| the ramp's floor there | 572.02…572.42 | **564.90**…572.70 (its own `mouth_z`) |
| the kerb above it | 577.84 | 581.12 |
| `adjacent_ground:taxi:E:zone1#69` | reaches 16.2 m, cut by the corridor | **intact, 18.15 m** |
| `adjacent_ground:taxi:E:zone2#59` | 19.2 m | **20.93 m** |
| `ramp_in_strip` (new family) | **11** | **8** — every TAXI-family row gone; the 8 are RUNWAY-strip rows |
| `wall_in_runway_strip` (v2 verify) | 10 | **6** |
| lateral pair `junction\|runway` over 18.2 m at the site | **4.957 %** (\|de\| 0.900 m) | **4.296 %** (0.780 m) |
| the same over 16.5 m | **4.957 %** (0.820 m) | **2.479 %** (0.410 m) |
| `taxi_box` rows within 120 m of the site | **8** | **0** |
| solve | optimal | optimal |

**THE RESIDUAL, NAMED.**  The 8 surviving `ramp_in_strip` rows are
against **runway 14R/32L's own 75 m strip** (code 4), not the taxiway's,
and with them `strip_transverse [runway|tunnel_ramp]` moves **5.589 m
over 13.72 m → 13.872 m over 32.49 m** (40.7 % → 42.7 %): the trench is
now deeper AND further out, so the face it presents to the RUNWAY strip
is bigger even though the face it presents to the TAXIWAY is gone.  This
is NOT a gap in the implementation, and the alternative was BUILT AND
MEASURED rather than argued: a "widest strip standing at this station"
reading (arm 4, a second full planar replay) is **byte-identical** to
this one at LEMD — the classification's cells are a PARTITION, so exactly
one cell contains each station, and along way −1230 that is
`junction/pav157` for 36 of its 48 m with the last station in a
`runway_shoulder` cell the `DECK_CELL_MAX_RATIO` gate refuses outright.
That reading is therefore DELETED, not parked.  The runway-strip
residual is a different law — a structure surfacing inside a runway
strip, §29 (7)'s lateral band / `wall_in_runway_strip` — and it wants
the owner's reading.

**THE LATERAL SLOPE (the separate half of the bar), MEASURED AND
NAMED.**  There is **NO `transverse` family row at `pav157`'s shared
runway nodes** — zero `transverse` rows within 120 m of the owner's
point, on either arm.  What prices the crossfall there is `taxi_box`
and `airside_no_step`, both `junction|runway` between way −10006
(runway 14R/32L) and way −10094 (`pav157`):

| span | BASE grade | cap | BASE \|de\| | after |
|---|---|---|---|---|
| 18.2 m | **4.957 %** | 1.985 % | 0.900 m | 4.296 % / 0.780 m |
| 16.5 m | **4.957 %** | 1.500 % | 0.820 m | 2.479 % / 0.410 m |

So the junction's crossfall at the site is **4.96 %**, not the 1.9 % the
attribution read (1.9851 is the CAP, not the grade), and **the runway IS
carrying the junction's crown**: every one of those pairs has one foot on
the runway ring and one on the junction ring, which share their nodes
there.  §34 (5) (b) improves it (4.957 → 4.296 % / 2.479 %) as a side
effect of taking the trench out of the strip, and it does NOT reach the
1.5 % taxiway cap.  The residual is quoted and the fix is not this
lane's: it is §29 (7) / §37 (10), a taxi-family cap over a pair whose
other foot is a runway vertex.

### THE CLOSING TEST — ONE LEMD TILE BUILD (lane `v2lemdstruct2`)

`tools/harness/build_airport.py LEMD --tag v2lemdstruct2 --tile 40 -4`,
branch `claude/v2lemdstruct2` @ `5ed9b083` (base main `da8e5d7f`),
**rc 0, 551.8 s** (vector 491.5 + mesh 59.5), solve **optimal** 40.4 s,
ledger tree `3e3e13880a2a`.  Structures line:

    underpass taxiway -1230 (layer 1, deck half-width 7.7 m, clip the deck
    CELL's footprint across the axis PLUS its graded strip (§34 (5) (b))
    eroded by 2.1 m (3316 m2 over 50 station(s), §34 (5) (a)), cell 50 read
    / 0 refused over 4x carriageway): 2 road(s) bored

— the clip area **772 m² → 3,316 m²** with the SAME 2 roads bored and the
same 50 stations read, 0 refused.

**THE OWNER'S SITES IN THE BUILT PATCH** (`Patches/+40-010/+40-004/
LEMD_auto.patch.osm`), which reproduce the replay arm exactly:

| site | built |
|---|---|
| 40.4947697,−3.5829037 | rim −11032 **602.16**, ramp −10891 floor **597.09** — **5.07 m** |
| 40.4611623,−3.5444804 | rim −11085 at **31.06 m** (570.00–573.77), ramp −10945 at **33.43 m** (564.90–572.70); `zone1#69` **18.15 m**, `zone2#59` **20.93 m** |

Harness census of the built patch: LAW-TRUE 5,498, ADJUDICATED 1,428
(airside 1,303 / gs 113 / mixed 12), CRITICAL motion 5, CRITICAL visual
1,183 (10 cliffs); `ramp_in_strip` **8**, `strip_transverse` 82 (worst
13.872), `within_shape` 3,453, `transverse` 107, `taxi_box` 169,
`hairline_pair` 1,173.  It is NOT a matched pair — no base BUILD exists
at this sha — and it is not quoted as one; the matched numbers are the
replay pair above.  Suite `tests/auto_patch_v2 tests/test_harness.py`
**1,587 passed / 1 skipped / 0 FAILED**, run twice.

**`[harness] !! SHARED-REPO SIDE EFFECT` — THE RUN IS FLAGGED
CONTAMINATED, AND THE AUTHOR IS NAMED.**  The build rewrote
`OSM_data/+40-010/+40-004/+40-004_big_roads.osm.bz2` (2,197,226 →
2,199,670 bytes, mtime 09:03 = this build's start) under scope
`osm_layers`.  This lane changed nothing in the road feed: `v2roadtags`
(`d4729dfc`, merged into main the same morning) bumps
`ROAD_CACHE_TAG_SCHEMA` so that the first build after it REWRITES every
cached road layer.  It is the KCLT 2026-08-05 precedent's exact shape and
it wants `--refresh-data osm_layers` run once, deliberately, before the
next LEMD or KCLT measurement.  Every number in the matched REPLAY PAIR
above is unaffected: both arms ran off the ONE registered capture, before
the build, with no shared-repo write.

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

### §34 (12) CONSUMER CENSUS (owner RULINGS 2026-08-30l), completed BEFORE any consumer was edited — lane `v2vmmcshore`

Every clause of §34 (12) is a REGION SHRINK at a SINGLE derivation site —
fewer bores admitted (1), fewer corridors built (3), a corridor clipped at
the shore (2), fewer decks severing a climb (4).  No consumer gains a new
shape class, so the table's job is to prove that each reader is
COUNT-SENSITIVE ONLY: it reads the same kinds of record, fewer of them.

**A. THE CORRIDOR REGION (the bore admission, the cut, `Classification.keepouts`).**

| # | consumer | reads | RULE |
|---|---|---|---|
| T1 | `planar/structures.build_structures` — the admission line (`mouth_only = …`) | `under_cover(b.line, polys, cell_tree)` over EVERY cell | **EDITED, the ONE derivation site of (1).** The retired cover test's count becomes the GATE, and its cover set is NARROWED to the §34 (12) (1) classes (airside pavement by `role_side`, `building` pads/unit footprints, the pack's authored corridor footprints and plates). A bore with an on-field mouth and no such cover is not built and is NAMED (`bores_no_service`). Mapped `bridge=yes` roads are not in the set and never were — a bridge deck is minted BY a corridor, so it can never be that corridor's own admission evidence. |
| T2 | `planar/structure_approach.mouths()` — the §29 (1) gate | `FieldRegion.holds` | **UNCHANGED CODE.** §29 (1) stays a NECESSARY condition; (1) adds a second, independent one at T1. Keeping them apart keeps the two reports apart (`mouths off-field N` vs `bores no service N`) — 12al's corridor and 13bm's band were once read as one region for exactly the opposite reason. |
| T3 | `planar/structures` the airside-cut refusal (`runway_u`) | cells whose `role in RUNWAY_FAMILY` | **EDITED, the ONE site of (3):** the union is the AIRSIDE ROLE SET — every role with `side = "airside"` in `precedence.toml` that carries a surface of its own (taxiway, junction, apron, stub, parallel, runway, runway_crossing) — so `ramp_cuts_runway_family = false` generalises and the exception list is empty. The key keeps its name and its `false`; what widened is the population it protects. |
| T4 | `planar/structure_deck.deck_intervals` (the bridge severance) | mapped `bridge=*` ways crossing the RAMP AXIS at ≥ 30° | **EDITED, the ONE site of (4):** the crossing must be of the BORE (the mapped `tunnel=yes` chain), inside the corridor's own width, not of the approach axis the ramp walks. A seafront bridge running parallel to the shore crosses a 600 m approach walk six times and the bore never. |
| T5 | `planar/zones.zone_regions` `keepouts` | the corridors' outer rings | UNAFFECTED CODE. Fewer corridors ⇒ fewer keepouts ⇒ the band spreads where a corridor is no longer built, which is the pre-corridor state and is what (1) intends. |
| T6 | `planar/basins.py:788` `classification.keepouts` | the same tuple | UNAFFECTED — same shape, fewer entries. |
| T7 | `planar/overlay.build_arrangement` | `Classification.cells` | UNAFFECTED — a structure cell that is not built is simply absent; no role, ref or ordering changes. |
| T8 | `constraints/structures.py`, `constraints/foot_rows.py`, `constraints/groundside.py` | `model.structures` (`Tunnel` / `Deck` records) | UNAFFECTED — they iterate the records; the list is shorter. |
| T9 | `verify/structures.py` (`tunnel_mouth_canonical`, `tunnel_deck_clearance`) | the same records | UNAFFECTED — a withdrawn corridor withdraws its own rows with it. |
| T10 | `emit/osm_adapter` (`tunnel_ramp`, `structure_rim`, `bridge_deck:*`) | the cells / records | UNAFFECTED — nothing new is emitted; 11 ramps and 19 rims become N. |
| T11 | `check_grade` (`tunnel_ramp` role, `ramp_in_road`, `ramp_in_strip`, `LAW_FAMILIES`) | the emitted patch | UNAFFECTED — no family added, no sidecar key added by §34 (12). |
| T12 | `pipeline/publication`, `classify/airside_edge`, `solve/project` | roles / channels | UNAFFECTED — `side` stays a pure function of `role`; no role moves. |
| T13 | `airport/deck_signature.is_tunnel_way` | the OSM tags | **UNCHANGED, deliberately.** WHICH ways are bores is not what the owner's site is about: `−5508/−5507` really is `tunnel=yes`. What (1) refuses is BUILDING it. Narrowing the tag reading instead would have moved every airport's bore set for one VMMC car park. |

**B. THE WATER REGION (clause (2)).**

| # | consumer | reads | RULE |
|---|---|---|---|
| W1 | `airport/dem_production.ProductionDem.water_geometry` | the tile's cached coastline/water layers (`O4_Vector_Map.cached_tile_water`) | **THE ONE WITNESS, UNCHANGED CODE** — the same object `airport/flat_site._cut_water` already cuts the datum region with (owner 2026-09-09m (3)) and §39 (i) (13cg) named as the emitter's shore witness. §34 (12) (2) and §37 (11) (1) both ask THIS function and neither re-derives a coastline. |
| W2 | `planar/structures` — the corridor's `outer` / `ramp` / `wall` | the cells | **EDITED, one site:** the corridor footprint is clipped by the water region before the void and the refusals are taken; a corridor whose ramp would reach the sea ends at the shore, and one left with no dry ramp is refused and named. |
| W3 | `constraints/water.water_pins` | `airport.dem.water_many` over `graded_strip` rings | UNAFFECTED CODE, and it is the INSTRUMENT of both clauses: with the regions trimmed, the count of ground vertices standing on water falls to zero (VMMC base: 193). It is kept armed precisely so the trim is provable rather than asserted. |
| W4 | `emit/bank.py` (the water clip at `:838`) / `emit/osm_adapter.weld_to_shore` (§39) | the same witness | UNAFFECTED — the bank is OFF at VMMC and the weld is a hairline fix on the vertices that REMAIN (§37 (11) (6)); it is not the trim. |

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

### §34 (12) / §37 (11) **MEASURED** (lane `v2vmmcshore`, 2026-09-15, branch `claude/v2vmmcshore`, base main `6fecb62b` + the day's merges)

**THE CLOSING BUILD REFUSES, BY NAME, AND THE LANE DID NOT WORK AROUND IT.**
On the final merged tree `build_airport.py VMMC` exits 1 at the shared-repo
guard (v2schemarefuse, RULINGS 2026-09-15u):

> `[osm_layers] OSM_data/+20+110/+22+113/+22+113_big_roads.osm.bz2 — the
> cached big_roads layer is SCHEMA-STALE — written under 2026-07-16, the
> engine expects 2026-09-15` … `--refresh-data osm_layers`

The refresh is the OWNER's act.  The MATCHED PAIR below is therefore the
BASE control `v2vmmcshoreBASE` (artifact ledger `b3a8d4c01325`, body
`f328f77e1639`) against arm `v2vmmcA5` (body `9c240e89bccc`) — one tree,
one corpus, both `[harness] shared repo UNCHANGED` with an EMPTY
`write_guard_blocked` and only `.lock` churn, both registered.  The arm
stands ONE MERGE BEFORE the final tree; what moved after it is named at
the end, and the final tree's own dry read reproduces every shore number.

| bar | BASE `b3a8d4c01325` | arm `9c240e89bccc` |
|---|---|---|
| owner site 22.1618794, 113.579745 | **0.00 m INSIDE `tunnel_ramp` way −10098** | **no face, rim or ramp within 300 m — none exists at all** |
| `tunnel_ramp` faces / `structure_rim` | **11 / 19** | **0 / 0** |
| the corridor count, NAMED | 12 bores admitted, 5 tunnels | **`bores no service 12 (§34 (12) (1))`** — every one named in the structures line; **no survivor, so no covered element to quote** |
| `pav5` (code E, junction) | 4 faces, **3.58 / 4.28 / 4.50 … 6.16 m** | 4 faces, **5.09 … 6.12 m** — bar (no vertex below 5.9) **NOT MET by 0.81 m**, attributed below |
| patch vertices at or under 0.5 m (the doubled water plane) | the rings stand at 0.00 up to 42 m seaward | **0 of 2,318 nodes** |
| `water_pins` wet (ground vertices standing on water) | **193** | **0** |
| `strip_seam_tear` | **61** (worst 6.110 m, 238 %) | **0** |
| `adjacent_ground_step` | **6** | **0** |
| `strip_transverse` / `transverse` | 0 / 11 | **0 / 0** |
| `airside_no_step` | 78 (worst 1.640 m) | **32** (worst 0.310 m) |
| `within_shape` / `taxi_box` | 76 / 61 | **2 / 22** |
| `hairline_pair` | 68 (45 above the degenerate floor) | 76 — **WORSE by 8, all out of scope**, named below |
| census **LAW-TRUE / ADJUDICATED** | **366 / 225** (airside 212, verdict FAIL) | **133 / 55** (airside 55, verdict FAIL) |
| the shore trim | — | `THE SHORE (§37 (11) (1)) cut 98,575 m² off 3 region(s), 6,567 m of sea wall`; 44 zone regions, **19 QUAYS** |

**THE TEAR AT 22.16232, 113.58138 IS GONE**: the base's worst row
(`strip_seam_tear graded_strip|junction`, 6.110 m at 238 %) has no
successor in any family on the arm.

**WHY `pav5` STILL READS 5.09 AND NOT 6.10.**  It is not the corridor and
it never was: with the tunnel withdrawn the junction came back whole and
sat at **1.95 m**, because `airport/flat_site._cut_water` cut the DATUM
REGION by the raw coastline partition, which calls **110,826 m² — 24.5 %
— of VMMC's runway/taxi union SEA** (the field is reclaimed land OSM's
coastline does not follow; the build's own line reads "47.0 % of the
synthetic extent is WATER and is CUT OUT of the Z0 raster", and the DEM
under those vertices reads 1.38–2.50 m).  §37 (11) (4)'s land
declaration — the airport's own classified surfaces are LAND — restores
the datum rows (1,083 → 1,240) and takes `pav5` to 5.09 … 6.12.  The
residual 0.81 m is the flat-site PREFERENCE losing to its neighbours
(`flat_site 826/1240 unmet, max 0.692 m`), not a row: **reported, not
fixed**, under the attempt cap.

**`hairline_pair` 68 → 76, and it is named rather than papered over.**
Every row is out of scope (45 `above_degenerate_floor`, 31
`on_the_edge`); none is adjudicated on either arm.  The rise is the
zone rings now ENDING at the coastline instead of crossing it, so more
of the patch boundary lies on the shore linework — which is what §37
(11) (1) asks for and what §39 (1)'s weld is for.  It is not measured in
the MESH (no tile build: see the refusal above).

#### LEMD AND OTHH — MATCHED DRY `planar --stage structures` PAIRS (no build)

Base arm cut in its own ritual worktree at `079197eb`; lane arm on this
branch; same corpus, same mod cache.

| | LEMD base | LEMD arm | OTHH base | OTHH arm |
|---|---|---|---|---|
| tunnels | **54** | **16** | **44** | **41** |
| decks (over all tunnels) | 7 | **1** | — | — |
| underpasses (§34 (5)) | **1** | **1** | 0 | 0 |
| corridors / door wells / sunken roads | 1 / 0 / 0 | 1 / 0 / 0 | 9 / 4 / 0 | 9 / 4 / 0 |
| basins | 0 | **1** | 10 | 10 |

* **LEMD loses 38 tunnels, and every one is the SAME CLASS**: a bore with
  an on-field mouth that passes under NO cover — owner 2026-09-12ab's
  "Build them" population, which §34 (12) (1) narrows in as many words
  ("a necessary condition, never a sufficient one").  Named:
  `-12795, -12918, -1293, -1321, -1341+-1339, -15336, -1581+-1568, -3231,
  -3829, -3958, -4043(+-3922), -4054+-4052, -4439, -473, -4928, -5284,
  -5388+-5383, -5821+-5820, -5970, -6339, -7847` (both ends where both
  were built).  **The 16 that remain are the ones that serve the field**,
  including `Bridge4`, `-6028` (12al's approach portal) and the
  `-5938+-26709+-8677+-26708+-22223` chain.
* **The 6 lost decks are those tunnels' own** — attributed row by row: of
  the base's five deck-bearing tunnels, four are in the no-service set and
  the one that survives (`-17265+-5946+-6640+-1359@1`) **keeps its deck**.
  **§34 (12) (4) removed ZERO decks at LEMD and ZERO at OTHH** — it is a
  no-op on both, and its only measured effect is at VMMC, where the
  corridor it would have applied to is not built at all.
* **The §34 (5) UNDERPASS IS UNTOUCHED** (1 → 1): its bore is the road
  centreline clipped to the aeroway's own deck ribbon, so it runs under
  airside pavement by construction and the deck states the crossing.
* **LEMD GAINS `basin:0`** — the 14bp bar.  Its base refusal reads
  `28345 m² overlaps a tunnel structure (a bore ramp; structures are never
  cut) at 40.491741, −3.569263`; the bore ramp is a no-service one, and
  with it gone the basin is built.
* **OTHH loses 4 tunnels** (`-11191@0/@1`, `-8342@0/@1`, all no-service)
  and **gains `wall-corridor:OTHH_Terminal_Parking_VCN_004.obj@1`**, which
  the base refused for overlapping `tunnel:-11191@0`.  Its 9 object
  corridors, 4 door wells and 10 basins are unchanged.

#### TWO SCOPINGS THE CENSUS FOUND, BOTH MEASURED, NEITHER IN THE RULING'S TEXT

1. **§34 (12) (3) APPLIES TO AN OSM BORE'S CORRIDOR, NOT TO ONE THE PACK
   STATES.**  Applied to object and wall corridors the widened union
   refused three OTHH terminal tunnels — `tunnel middle - east`,
   `tunnel middle - west`, `tunnel south west 2` — against aprons
   `pav32` / `pav30`.  An object corridor's own plate IS the deck over
   the pavement, which is (3)'s first limb, and there is no terrain deck
   cell to find.  The runway family alone binds there, as before.
2. **THE PAVEMENT A CORRIDOR'S OWN MOUTH STANDS ON IS NOT "CUT".**  (3)
   speaks of a bore that CROSSES a pavement; a corridor whose mouth
   stands on an apron does not cross it, it ENDS in it — that is what a
   portal is, and 08-07 ruling 4's cut is how the portal is opened.
   Without the exemption the twin's own baseline (a bore under an apron
   with both mouths on it) was refused.  VMMC's bore reached `pav5`
   **36 m from its mouth**, which is the defect the clause is for.

   Both want Fable's ruling; both are named in `structure_service.py`.

#### §34 (12) (1) ADMITS THE MOUTH, IT WITHHOLDS THE BUILD

`stats.mouths` / `mouths_off_field` / `mouths_on_approach` stay what §29
(1) found; `bores_no_service` / `no_service_bores` are (12) (1)'s own
report, and the structures line carries both.  The §29 twins were amended
accordingly (`test_v2mouthgate.py`, `test_v2approachcorridor.py`): where
they measure the MOUTH gate their fixture bores now run under the apron so
the second gate is satisfied, and
`test_a_mouth_on_the_field_is_built_though_its_bore_covers_nothing` is
RESTATED — the mouth is still admitted and counted, the build is withheld,
and 12ab's supersession is written into it.

#### THE SHORE WITNESS IS THE SEA, NOT EVERY WET POLYGON

`shore_region` reads `ProductionDem.sea_geometry` — the coastline
partition's SEA polygons alone (VMMC: 6 sea, 14,678 inland).  Trimming at
an inland body would delete the 09-09m WATER DATUM's whole population
(measured: `tests/auto_patch_v2/test_water_datum`'s canal went from a
pinned strip to no strip at all) and would cut the band at LEMD's
retention basins, which are §24's region.  A sampler with no
`sea_geometry` claims NO shore: no witness, no trim.

#### WHAT IS NOT DONE, NAMED

* **The closing VMMC build** (refused above) and therefore `mesh_region_
  tris.py --z-xref` on a built tile: the doubled water plane is proven
  GONE in the PATCH (0 nodes at or under 0.5 m, `water_pins` wet 0) and
  NOT in the mesh.
* **The sea wall's own geometry is the MESH's, and this lane did not
  re-author it.**  `O4_Vector_Map`'s Round 7 / R17-3 seawall breaklines
  (authored FOR VMMC on 2026-08-10) already offset every
  graded-coverage ring segment bordering water outward by
  `SEAWALL_OFFSET_M` at `SEAWALL_SEA_LEVEL_M` — which IS §37 (11) (2)'s
  breakline pair.  The patch's job is to END at the coastline, and the
  `sea_wall` census family is how the census sees that it did.  A second
  emit-side pair would be a second authority and a §39 hairline.
* **`sea_wall` reports 0 rows at VMMC** — the quay rings end ON the shore
  and the ADJACENT-GROUND families they used to tear against report 0, so
  there is nothing left for the exclusion to take.  The family and the
  exclusion are proved by TWINS, not by the airport, and that is stated
  rather than hidden.
* `pav5`'s last 0.81 m (the flat-site preference, above); any
  `--refresh-data`; the five-airport sweep; any LEMD / OTHH / CYXY BUILD;
  any merge into main; any RULINGS entry; any new tool (no `tools/INDEX.md`
  row — the readings are `osm_site.py`, `harness/census.py`,
  `planar --stage structures` and `frames.py`).

#### Build-time impact statement

`serves_the_field` is one STRtree query per admitted bore (VMMC 12, LEMD
54, OTHH 44); `airside_cut_roles` is one pass over `precedence.toml`;
`shore_region` is one `sea_geometry` call plus one `difference` per
build, and the per-region clip is one `intersection` on the regions that
touch the sea (VMMC: 3 of 44).  Measured whole-build wall at VMMC: base
21.6 s, arm 18.8 s — the arm builds LESS (no corridors, smaller zone
region, 2,854 → 2,321 unknowns, 10,406 → 6,845 rows).  Nothing here is
within 1 % of either budget on the wrong side.
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

## §34 (12) AMENDED — (1) WITHDRAWN (owner 12ab STANDS: admission is by the mouth); (3) scoped to OSM bores; a mouth's own pavement is not a cut (Fable 2026-09-15; RULINGS 2026-09-15w) — lane `v2vmmcshore` r2

Lane r1 (a57abc47) met every VMMC bar (0 ramps / 0 rims, the tear gone,
0 of 2,318 nodes at or under 0.5 m, 98,575 m² trimmed off three
regions, 6,567 m of sea wall, 19 quays, ADJUDICATED 225 → 55) and then
measured (1) at LEMD by dry pair: **54 → 16 tunnels** — the 38 lost are
owner 12ab's population ("Build them": a mapped tunnel whose mouth
stands on the field is built, mouth and ramp, whether or not its bore
passes under an airport surface; visible on approach).  (1) as written
REVERSED an owner ruling by the side door.  RULED:

(1) is WITHDRAWN.  Admission stays BY THE MOUTH (12ab, `mouth_standoff_m`).
What stops the VMMC seafront line is (2)–(4): no structure face over the
water (the corridor ends at the shore); a corridor never CUTS airside
pavement (it becomes an underpass where the pavement is authored as a
deck or a pack corridor covers it, otherwise it STOPS SHORT of the
pavement — at VMMC the OSM car-park bore stops at pav5); a mapped bridge
severs the climb only where it crosses the bore.  (3) is SCOPED to OSM-
derived corridors: a PACK-STATED corridor (§33 (6) signatures A/B/C, the
OTHH terminal tunnels under pav32/pav30) is authored geometry and its
crossing of airside IS an underpass by authorship — never refused.  The
pavement a corridor's own MOUTH stands on is not "cut": a portal ends in
it.  What remains at VMMC under this reading — a short mouth + ramp at
the car-park entrance beside the seafront, if the mouth is on the field
— is an OWNER QUESTION (15w): the owner objected to "the whole long line
… going out into the water and cutting the taxiway"; whether the stub
that survives is wanted is theirs to say, with its geometry named by r2.
The lane's r2 re-measures VMMC, LEMD (54 → 54 expected) and OTHH
(44 → 44 + the returned wall corridor) under the amendment.  The pav5
residual 0.81 m (the flat-site preference losing to its neighbours,
`flat_site 826/1240 unmet, max 0.692 m`) is accepted and named.

### §34 (12) AMENDED / §37 (11) **MEASURED — ROUND 2** (lane `v2vmmcshore`, 2026-09-15, branch `claude/v2vmmcshore`, base main `847fa1a1`)

**(1) IS DELETED, NOT GATED** (`serves_the_field` / `no_service_bores` and
their stats fields are gone; `structures.py`'s docstring says the mouth
admits again).  The §29 twins r1 amended are RESTORED to their own
assertions, and `test_v2mouthgate.py::test_a_mouth_on_the_field_is_built_
though_its_bore_covers_nothing` carries the supersession's own history so
the reversal cannot come back unnoticed.

**THE CLOSING BUILD STILL REFUSES** (checked once, on the merged tree):

> `REFUSING: … [osm_layers] OSM_data/+20+110/+22+113/+22+113_big_roads.osm.bz2`
> `— the cached big_roads layer is SCHEMA-STALE — written under 2026-07-16,`
> `the engine expects 2026-09-15 … --refresh-data osm_layers`

and the refresh ledger holds NO `osm_layers` entry covering `+22+113`.
The arm is therefore a **MATCHED REPLAY PAIR**, one corpus, two trees,
one instrument: a `v2_solve_replay --capture` (14 s) per tree and its
`--emit` patch, censused by `harness/census.py`.  BASE = the ritual
worktree at `079197eb`; ARM = this branch.

| bar | BASE (replay-emitted) | ARM (replay-emitted) |
|---|---|---|
| owner site 22.1618794, 113.579745 | **INSIDE `tunnel_ramp` way −10098** | **covered by NOTHING** (`osm_site --contains`: 0 ring groups) |
| `tunnel_ramp` faces / `structure_rim` | 11 / 19 | **8 / 13** |
| ramp + rim standing ON THE SEA | **1,543.8 m²** | **1.7 m²** — §34 (12) (2) (unclipped, once (1) was withdrawn, it read 905.7 m²) |
| `pav5` | 4 faces **3.58 / 4.28 / 5.43 … 6.16 m** | 4 faces **5.09 … 6.12 m**; lowest airside face 3.58 → **5.09** — bar (≥ 5.9) **NOT MET by 0.81 m**, the accepted flat-site residual |
| patch nodes at or under 0.5 m | **284** | **0** |
| `strip_seam_tear` / `adjacent_ground_step` | **63 / 6** | **0 / 0** |
| `transverse` / `strip_transverse` / `road_cross_section` | 11 / 0 / 6 | **0 / 0 / 0** |
| `ramp_in_strip` | **18** (worst 9.103 m) | **0** |
| `airside_no_step` / `within_shape` / `taxi_box` | 76 / 76 / 62 | **32 / 2 / 22** |
| `hairline_pair` | 138 (worst 0.331 m) | **108** (worst 0.186 m) |
| census **LAW-TRUE / ADJUDICATED** | **456 / 245** (airside 213, gs 9, mixed 23) | **165 / 55** (airside 55, gs 0, mixed 0) |
| the shore trim (dry, same tree) | — | `THE SHORE (§37 (11) (1)) cut 98,575 m² off 3 region(s), 6,567 m of sea wall`; 44 zone regions, **19 QUAYS** — unchanged from r1 |

**A DEFECT THE REPLAY PAIR FOUND, AND THE FIX.**  `tools/v2_solve_replay.py`
called `flat_site.detect` WITHOUT §37 (11) (4)'s land declaration, so a
replay solved a different problem from a build: `pav5` 1.95 m against the
build's 5.09, `within_shape` 327 against 2.  The replay now reads
`pipeline/build._classified_land` — ONE derivation, two callers — and the
arm above reproduces the r1 harness build exactly (ADJUDICATED 55,
`within_shape` 2, `airside_no_step` 32).

#### LEMD AND OTHH — MATCHED DRY `planar --stage structures` PAIRS

| | LEMD base | LEMD arm | OTHH base | OTHH arm |
|---|---|---|---|---|
| tunnels | 54 | **55** | 44 | **44** |
| decks / basins / underpasses | 7 / 0 / 1 | **7 / 0 / 1** | 1 / 10 / 0 | **1 / 10 / 0** |
| corridors / door wells / sunken roads | 1 / 0 / 0 | 1 / 0 / 0 | 9 / 4 / 0 | 9 / 4 / 0 |

**OTHH IS IDENTICAL, tunnel for tunnel** — the three terminal tunnels (3)
refused in r1 are back (the scoping), and the `VCN_004` wall corridor does
NOT "return" because the bore it overlapped (`tunnel:-11191@0`) is itself
back under (1)'s withdrawal.

**LEMD IS 54 → 55, AND THE ONE DIFFERENCE IS NAMED**: `tunnel:-5821+-5820@1`.
The base REFUSED it — `the ramp would cross a runway-family face before
reaching the DEM (ramp_cuts_runway_family = false)` — and under (3) as
amended it STOPS SHORT and is built instead.  That is the ruling's own
words ("otherwise it STOPS SHORT of the pavement") turning a refusal into
a shorter portal; it is the F-6 underpass's own bore pair, and the
underpass count is unchanged at 1.  Nine refusal MESSAGES change wording
(a pad hit that is now also an airside hit names the pavement:
`-17028@0` `pav70`, `-17037@0` `pav54`, `-17037@1` `pav12`); the verdicts
are the same.

#### THE VMMC STUB — OWNER QUESTION 15w-1, WITH ITS GEOMETRY

**The bore the owner named builds nothing**: `−5508+−5507+−2489` is
refused at BOTH ends (`its corridor overlaps tunnel:-4787@1 (not a dual
under 31h's separation test)`).  What stands on the seafront is a
DIFFERENT bore, `tunnel:-2488@0` — mouth **22.1629135, 113.5752813**,
floor **0.996 m**, design grade 8 %, approach walk `top_s` **468 m** —
emitting three ramp faces, 381 m of frontage in all:

| face | area | length | floor | centroid | → owner's probe | → `pav5` | → the shore |
|---|---|---|---|---|---|---|---|
| `−10085` | 1,522 m² | 207 m | 1.00 m | 22.1626813, 113.5762528 | 263 m | **38.8 m** | 127.2 m |
| `−10086` | 568 m² | 87 m | 1.00 m | 22.1623307, 113.5777243 | 169 m | **38.9 m** | 63.3 m |
| `−10087` | 454 m² | 87 m | 1.00 m | 22.1621281, 113.5785729 | **74 m** | **38.9 m** | **0.0 m** (it ENDS at the coastline — (2)) |

The line no longer reaches the owner's probe, never touches `pav5`
(38.8 m clear at its nearest) and no longer goes out into the water.
KML for the owner's read:
`<scratchpad>/vs/VMMC_r2.kml` (`planar --stage structures --kml`).
The 1.7 m² residual on the sea is one rim sliver at the clip line, under
the identity spacing.

#### What round 2 did NOT do

The closing VMMC build (refused above — the owner's `--refresh-data
osm_layers`) and therefore `mesh_region_tris --z-xref`; `pav5`'s last
0.81 m (accepted by 15w); any `--refresh-data`; the five-airport sweep;
any LEMD / OTHH BUILD; any merge; any RULINGS entry; any new tool.

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

### §34 (12) (4) **MEASURED — ROUND 3** (lane `v2vmmcshore`, 2026-09-15, branch `claude/v2vmmcshore`, base main `14031e00`)

**(a) WHAT (4) IS IMPLEMENTED WITH, AND WHAT IT IS NOT — r2 did not say.**
The shipped test is ONE limb of the ruling: a bridge way whose run INSIDE
THE CORRIDOR exceeds `_DECK_ALONGSIDE_MAX` (6) × its own carriageway width
is not an over-crossing and does not sever.  The ruling's other limb —
"it CROSSES the bore (an over-crossing within the corridor's own width)"
— was **NOT implemented**: `bores` was read as a flag arming the alongside
limb and the bore's geometry was never tested.

Measured on `tunnel:-2488@0` (bore way **−2488**, length **36.6 m**,
carriageway 7.0 m; approach walk **604.2 m**; corridor half-width
3.5 + 2.1 m):

| deck | own length | run INSIDE the ramp corridor | alongside bar | shipped verdict | CROSSES the bore? | distance to the bore | crossing station |
|---|---|---|---|---|---|---|---|
| `bridge_deck:-1798` | 239.1 m | **11.8 m** | 42.0 m | SEVERS | **NO** | **137.2 m** | s = 214.8 m |
| `bridge_deck:-3636` | 462.2 m | **19.3 m** | 42.0 m | SEVERS | **NO** | **46.7 m** | s = 308.7 m |

Both are genuine steep crossings of the 604 m APPROACH WALK — the
alongside limb correctly passes them — and NEITHER comes within 46 m of a
36.6 m bore.  They set `climb_from_s = 559.2 m` on a ramp that ends at
`top_s = 468.0` (the §34 (12) (3) stop at `pav5`), so the climb never
starts and the floor stays **flat at 1.00 m for 381 m of frontage**
against a rise of 6.096 − 0.996 = **5.10 m**, which at the 8 % design
grade needs **63.8 m**.

**(b) THE CORRIDOR WITH (4) APPLIED AS RULED** (`ln.intersects(bore ⊕
half_outer)`), dry `--stage structures` and a matched VMMC replay pair
against a base arm at the same main:

| | BASE (main `14031e00`) | (4) as ruled |
|---|---|---|
| `tunnel:-2488@0` decks | `bridge_deck:-1798` + `-3636` | **none** |
| `tunnel:-2488@0` `climb_from_s` / `top_s` | 559.2 / 468.0 m | **0.0 / 84.0 m** |
| `tunnel:-2488@0` `clipped_by` | `pav5` | **none** — it no longer reaches the pavement at all |
| every VMMC corridor's `top_s` | 36 … 576 m | **24 … 108 m** (one deck survives anywhere: `bridge_deck:-2088` on `-4787@1`, climb from 9.7 m) |
| VMMC tunnels / tunnel refusals | 5 / 10 | **13 / 2** — short ramps stop overlapping, so the 31h refusals fall away and MORE corridors are built |
| emitted ramp faces / area | 8 / 8,975 m² | **14 / 8,485 m²** |
| ramp + rim standing on the sea | 1.7 m² | **0.0 m²** |
| nearest ramp to the owner's probe | 74 m | **188 m** |
| nearest ramp to `pav5` | 38.8 m | 39.0 m |
| census LAW-TRUE / ADJUDICATED | 163 / **53** | 157 / **57** (`airside_no_step` 30 → 35) |

**(c) AND IT IS REFUTED AT LEMD.**  Same instrument, same main:

| | LEMD base | LEMD with (4) as ruled | OTHH base | OTHH with (4) as ruled |
|---|---|---|---|---|
| tunnels | 55 | 56 | 44 | **44** |
| **decks** | **7** | **0** | 1 | **1** |
| basins / underpasses | 0 / 1 | 0 / 1 | 10 / 0 | 10 / 0 |

Every LEMD deck is dropped, with the ramp length that changes named:

| tunnel | `top_s` | `climb_from_s` | decks lost |
|---|---|---|---|
| `-1341+-1339@1` | 180.0 → **24.0** | 153.8 → 0.0 | `bridge_deck:-15293` |
| `-1581+-1568@1` | 552.0 → **60.0** | 287.1 → 0.0 | `-5305`, `-1378` |
| `-17265+-5946+-6640+-1359@1` | 96.0 → **24.0** | 71.0 → 0.0 | **`-6288`** |
| `-4928@0` | 252.0 → **84.0** | 169.9 → 0.0 | `-14230`, `-516` |
| `-5284@0` | 72.0 → 72.0 | 22.4 → 0.0 | `-11828` |

`bridge_deck:-6288` is the §33 (4) deck RULINGS 2026-09-14bp item 10 was
written for and lane `v2lemdstruct` measured to 3 m.  **A LEMD deck
crosses the TRENCH the ramp digs, not the short mapped bore**, so the
literal limb reverses §33 (4) by exactly the side door §34 (12) (1)
reversed 12ab.  It is DELETED, not gated; the alongside limb — the one
VMMC's parallel seafront needs — stands, and the dry arms at VMMC (5 /
10), LEMD (55, 7 decks) and OTHH (44, 1 deck) are identical to the base
at main.  Twin: `test_a_bridge_running_ALONGSIDE_the_corridor_does_not_
sever_the_climb`, whose last assertion pins the refuted limb's ABSENCE.

**THE INTENT QUESTION (attempt cap reached on (4)).**  A distance-to-bore
test does not separate the two cases: VMMC's decks are 46.7 / 137.2 m out,
LEMD's cross at stations 22.4–287.1 m of a ramp whose bore is also short.
What DOES separate them, measured: **VMMC's corridor needs 63.8 m and its
decks stand at s = 214.8 / 308.7 m — beyond the station at which the climb
would already have reached grade, so there is no trench there for a bridge
to span.**  A deck that severs a climb which has already daylighted is
what holds a flat floor for 381 m.  Whether (4) should read "a bridge
severs only where the corridor is still BELOW GRADE at that station" is a
law number this lane may not author; it is offered with its numbers.
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

## §34 (12) (4) AMENDED — A BRIDGE SEVERS THE CLIMB ONLY WHERE THE CORRIDOR IS STILL BELOW GRADE (Fable 2026-09-15; RULINGS 2026-09-15aj; lane v2vmmcshore r3 measurement) — lane `v2vmmcshore` r4

r3 measured the two limbs of (4).  The ALONGSIDE limb (a `bridge=yes`
way whose run inside the corridor exceeds `_DECK_ALONGSIDE_MAX` × its
carriageway width is not an over-crossing) stands.  The CROSSES-THE-BORE
limb is REFUTED and deleted: a LEMD deck crosses the TRENCH the ramp
digs, not the short mapped bore (`bridge_deck:-6288` — the §33 (4) deck
of 14bp item 10 — is 137 m from a 36.6 m bore), so the literal limb
dropped all seven LEMD decks (7 → 0); it reversed §33 (4) by the side
door.  What separates VMMC from LEMD, measured: VMMC's `tunnel:-2488@0`
needs 63.8 m to reach grade (5.10 m at 8 %) and its two "severing" decks
stand at s = 214.8 / 308.7 m — beyond the station where the climb would
already have reached grade, where there is no trench for a bridge to
span; they set `climb_from_s` = 559.2 m on a ramp whose stop is 468 m,
so the floor stayed at 1.00 m for 381 m.  RULED: **a deck severs the
climb only where the corridor is still BELOW GRADE at the deck's
station**.  Decks are taken in station order from the mouth: the climb
runs from the last covered end at the ramp cap; a deck whose near edge
lies at or before the station where that climb reaches grade extends
the covered run (the climb restarts beyond its far edge); a deck beyond
that station is not a crossing of this corridor and is ignored.  The
number is the ramp cap itself (`ramp_max_grade`), no new key.  Expected
(r3's arm): VMMC `-2488@0` decks none, `top_s` 84 m, the corridor no
longer reaching pav5, ramp+rim on the sea 0.0 m², nearest ramp 188 m
from the owner's probe; LEMD keeps its 7 decks (each deck's station vs
its ramp's climb-to-grade station named); OTHH 44 / 1 deck unchanged.

### §34 (12) (4) AS AMENDED **MEASURED — ROUND 4** (lane `v2vmmcshore`, 2026-09-15, branch `claude/v2vmmcshore`, base main `dec0481e`)

Implemented at `structure_deck._below_grade`, fed by `structure_service.
grade_reach_for` — which is `structure_approach.ramp_top`, the RAMP's own
derivation, so the deck reading and the ramp it feeds cannot disagree
about where the trench ends.  No new key (the number is `ramp_max_grade`).
Every verdict is written into the tunnel's `notes`
(`structure_deck.below_grade_notes`), so the two stations it compares are
readable without a rebuild — the tables below are that output.

#### VMMC — THE CLOSING BUILD

`build_airport.py VMMC --tag v2vmmcshore4`: **rc 0, 21.3 s**, `status
optimal`, `body_sha 2f53c8d2cbb1`, artifact ledger **`14508d4b2d53`**, and
verbatim:

> `[harness] shared repo UNCHANGED by this build (full-surface before/after snapshot) — no side-effect mutation`

| bar | r1 BASE (`b3a8d4c01325`) | CLOSING BUILD (`14508d4b2d53`) |
|---|---|---|
| owner probe 22.1618794, 113.579745 | inside `tunnel_ramp` −10098 | **covered by nothing**; nearest ramp **268 m** away |
| ramp + rim standing on the sea | 1,543.8 m² | **0.00 m²** |
| patch nodes at or under 0.5 m | 284 | **0** |
| `pav5` | 3.58 / 4.28 / 5.43 … 6.16 | **5.09 … 6.12**; nearest ramp 39.0 m clear |
| lowest airside face | 3.58 m (`pav5#1`) | **5.09 m** |
| `strip_seam_tear` / `adjacent_ground_step` / `transverse` | 61 / 6 / 11 | **0 / 0 / 1** |
| `sea_wall` | — | **27 rows**, worst drop 6.100 m (reported, never adjudicated) |
| census LAW-TRUE / ADJUDICATED | 366 / **225** | 178 / **61** |
| structures | 11 ramps / 19 rims, tunnels 5 | tunnels **13**, decks **4**, refusals **2**, ramps 16 / rims 19 |
| the shore trim | — | 98,575 m² off 3 regions, **6,154 m of sea wall** |

`tunnel:-2488@0`, the seafront corridor, reads:

| deck | station s0..s1 | climb runs from | reaches grade at | verdict |
|---|---|---|---|---|
| `-1798` | 211.0 … 218.7 | 0.0 | **84.0** | BEYOND GRADE, not a crossing |
| `-3636` | 302.1 … 315.3 | 0.0 | never | BEYOND GRADE |
| `-3446` | 489.4 … 502.1 | 0.0 | never | BEYOND GRADE |
| `-3444` | 545.9 … 558.6 | 0.0 | never | BEYOND GRADE |

— so `climb_from_s` 559.2 → **0.0**, `top_s` 468.0 → **84.0 m** (63.8 m of
climb plus one station of slack), `clipped_by` `pav5` → **none**: the
corridor no longer reaches the pavement at all.  **The chained case is
the owner's own bore** `-5508+-5507+-2489@0`: `-2088` at s 12.2 severs
(grade at 84.0), the climb RESTARTS at its far edge 19.2, and `-1798` at
s 69.2 severs again because the restarted climb reaches grade only at
96.0 — two decks kept, exactly the ruling's chaining.

#### LEMD — THE RULING'S EXPECTATION IS NOT MET, AND HERE IS WHY

Expected: 7 decks kept.  **Measured: 1.**  Every reading, from the
build's own notes:

| tunnel | deck | station s0..s1 | climb from | reaches grade at | verdict |
|---|---|---|---|---|---|
| `-5284@0` | `-11828` | 14.6 … 21.8 | 0.0 | 108.0 | **severs** |
| `-17265+-5946+-6640+-1359@1` | **`-6288`** | 56.3 … 70.4 | 0.0 | **24.0** | beyond grade |
| `-1341+-1339@1` | `-15293` | 146.2 … 153.2 | 0.0 | **24.0** | beyond grade |
| `-1581+-1568@1` | `-5305` | 103.3 … 110.5 | 0.0 | **60.0** | beyond grade |
| `-1581+-1568@1` | `-1378` / `-1379` | 270.0 / 279.2 | 0.0 | never | beyond grade |
| `-4928@0` | `-14230` | 107.0 … 124.5 | 0.0 | **84.0** | beyond grade |
| `-4928@0` | `-374` / `-516` / `-15311` | 125.3 / 158.0 / 162.3 | 0.0 | never | beyond grade |
| `-1341+-1339@0` | `-639` | 523.4 … 530.4 | 0.0 | **180.0** | beyond grade |

LEMD tunnels **55 → 56** (`tunnel:-1341+-1339@0` returns), decks **7 → 1**,
basins 0 → 0, underpasses **1 → 1**; the ramp lengths that change:
`-1341+-1339@1` 180 → 24 m, `-1581+-1568@1` 552 → 60 m,
`-17265+-5946+-6640+-1359@1` 96 → 24 m, `-4928@0` 252 → 84 m,
`-5931@0` 96 → 120 m and `-5931@1` 36 → 48 m (no decks either side —
the §34 (12) (3) stop, not (4)).

**THE RESULT IS INTERNALLY CONSISTENT WITH §34.5 (6)** ("beyond the trench
the road is ordinary ground"): each of LEMD's six dropped decks stands
past the station at which its own ramp's climb reaches the DEM, so there
is no trench under it for a bridge to span — the decks were themselves
what held those trenches open (their base `climb_from_s` were 71.0 /
153.8 / 287.1 / 169.9 m, all beyond the 24–180 m at which the ramp
daylights on its own).  It is the same shape as VMMC's defect, smaller.

**BUT `bridge_deck:-6288` IS RULINGS 2026-09-14bp ITEM 10's OWN BAR**
(lane `v2lemdstruct` measured its ends to 3 m of 40.4835967,−3.580923),
and this lane will not delete a ratified §33 (4) deck on its own reading.
The law is implemented EXACTLY as 15aj states it and the consequence is
reported rather than tuned: **whether (4) as amended is meant to stand
where it takes `-6288`, or whether a deck that is a §33 (4) MAPPED-END
deck is senior to the below-grade test, is the owner's / Fable's call.**
Nothing here is gated; the attempt cap on (4) is spent (r3's
crosses-the-bore limb, r4's below-grade limb).

#### OTHH — UNCHANGED

44 tunnels, **1 deck**, 10 basins, 9 object corridors, 4 door wells, 0
underpasses — identical to the base at main, deck for deck.

#### Twin

`test_a_deck_severs_only_where_the_corridor_is_still_below_grade`: VMMC's
own numbers (grade at 84.0, decks at 211.0 / 302.1 → none), the chained
case (12.2 severs, the climb restarts at 19.2, 69.2 severs), the first
beyond-grade deck stopping the run, and the two null readings (a climb
that never reaches grade, and no `grade_reach` at all) keeping every deck.
## §34 (12) (4) MEASURED AT LEMD — THE BELOW-GRADE LIMB HOLDS AT VMMC AND FAILS AT LEMD; THE DISCRIMINATOR IS A WITNESSED CUTTING (Fable 2026-09-15; RULINGS 2026-09-15al) — lane `v2vmmcshore` r5 (measurement first)

r4 (5b30cf9d) implemented (4) AMENDED exactly (`structure_deck._below_
grade` fed by `structure_service.grade_reach_for` = `ramp_top`, the
ramp's own derivation).  VMMC on a real build: `-2488@0` decks at s 211 /
302 / 489 / 546 against grade at 84.0 — none severs; the owner's bore
`-5508+…` keeps two chained decks (12.2 → 19.2 → 69.2 against 84 / 96)
— the rule as ruled.  LEMD: decks 7 → **1**.  Every dropped deck stands
past where its ramp daylights UNAIDED (grade at 24–180 m; decks at 56–
530 m) — and those decks were what held the trench open (base
`climb_from_s` 71 / 154 / 287 / 170 m).  `bridge_deck:-6288` (14bp item
10, the owner's screenshot-1 bridge, "much better") is among them.  The
two limbs tried (crosses-the-bore, below-grade) are both refuted as
DISCRIMINATORS between VMMC and LEMD; the attempt cap on blind limbs is
spent.  RULED: the next round MEASURES before any rule — for each of
the 11 decks (LEMD 7, VMMC 4): the crossed road's own tags in the road
feed (`layer`, `cutting`, `covered`, `tunnel`, `embankment` — the
witnesses v2roadtags now keeps, §45 (9)), the DEM profile along the
road under the deck (the road's DEM beneath the deck vs the deck way's
DEM at its abutments — a real cutting reads lower), the deck's own
`layer`/`bridge` tags and length, and the distance from the mouth.  The
expected discriminator: a deck severs the climb where the road beneath
it is WITNESSED as a cutting (a negative `layer`, `cutting=yes`, or a
DEM depression under the deck of ≥ 1 m relative to its abutments)
regardless of station; a deck over a road at grade beyond the ramp's
daylight station is not a crossing.  The rule is written after the
table, by the session.

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

## §34 (12) (4) RULED FROM THE TABLE — A DECK SEVERS THE CLIMB WHERE THE GROUND BENEATH IT IS WITNESSED BELOW GRADE (Fable 2026-09-15; RULINGS 2026-09-15ap) — lane `v2vmmcshore` r6

The 16-deck table (r5, `osm_site --deck-witness`): at LEMD the DEM under
the span reads a CUTTING at 8 of 11 decks (+0.81 … +2.35 m below the
mean of the abutments) and the bore beneath every approved deck whose
feed is schema-current carries `layer −1/−2, tunnel=yes`; at VMMC every
deck on the field reads 0.00 m (two at sea level +0.15/+0.17, one
embankment −1.77) and the ways beneath the decks are the untagged
seafront approach.  The station limbs (crosses-the-bore, below-grade)
disagree with the cut on 5 of 11 and are WITHDRAWN.  RULED:

A mapped `bridge=yes` way crossing a corridor SEVERS the climb (extends
the covered run; the climb restarts beyond its far edge; chaining as
r4) where the ground beneath its span is WITNESSED below grade, by
either witness:
  (i) the corridor's way beneath the deck's span carries `tunnel=yes`
      or `layer ≤ −1` in a SCHEMA-CURRENT road feed (a stale feed
      reports `schema`, which is neither yes nor no — the deck is then
      judged by (ii) alone);
  (ii) the DEM under the span reads at least `deck_cut_witness_m`
      (0.5 m; VMMC's maximum on the field is +0.17, LEMD's minimum
      positive +0.81) below the mean of the DEM at the deck's two
      abutments (`abutment_m` 40, or the deck end when shorter).
Otherwise the deck stands over ordinary ground beyond the trench
(§34.5 (6)) and does not sever.  The alongside limb (r3) stays as a
pre-filter.  Expected: LEMD keeps its 7 approved decks (`-6288` by (i)
layer −2; `-11828`, `-14230`, `-516` by (ii); `-5305`, `-1378`, `-15293`
by (i) layer −1 — note `-5305` −0.57 and `-15293` −1.46 read NEGATIVE
under (ii) and are kept by (i) alone); VMMC keeps none (`-2088`'s 0.00
included); OTHH 44 / 1 unchanged; the Macau LRT viaducts (`bridge=
viaduct railway=light_rail`, cut 0.00) never sever.  Law keys
`[bridge] deck_cut_witness_m`, `abutment_m` — no Python defaults.
The negative-id collision the round found (the road layers and the
airports layer each mint negative ids; 8 of 11 deck ids carry two
ways, five with an `aeroway=taxiway` first copy) is a reader hazard
for every tool that joins on a way id — chip.

### §34 (12) (4) AS RULED **MEASURED — ROUND 6** (lane `v2vmmcshore`, 2026-09-15, branch `claude/v2vmmcshore`, base main `2c8a34a1`)

Implemented at `structure_service.deck_witness_for` (the two witnesses)
and `structure_deck._witnessed` (the chaining), keyed on `[bridge]
deck_cut_witness_m` = 0.5 and `deck_abutment_m` = 40.0 — **no Python
defaults**.  BOTH station limbs are DELETED: r3's crosses-the-bore and
r4's below-grade are gone with their helper (`grade_reach_for`), and
every verdict is written into the tunnel's own `notes`
(`deck_witness_notes`), which is the table below.

#### THE CLOSING VMMC BUILD

`build_airport.py VMMC --tag v2vmmcshore6`: **rc 0, 16.8 s**, `status
optimal`, `body_sha ecc616c4bba5`, artifact ledger **`3cd89005e24c`**,
and verbatim:

> `[harness] shared repo UNCHANGED by this build (full-surface before/after snapshot) — no side-effect mutation`

| bar | r4 closing build | r6 closing build |
|---|---|---|
| owner probe 22.1618794, 113.579745 | covered by nothing, nearest ramp 268 m | **covered by nothing**, nearest ramp **188 m** |
| ramp + rim on the sea | 0.00 m² | **0.00 m²** |
| patch nodes at or under 0.5 m | 0 | **0** |
| `pav5` | 5.09 … 6.12, ramp 39.0 m clear | **5.09 … 6.12**, ramp **39.0 m** clear |
| structures | tunnels 13 / decks 4 / refused 2 | tunnels 13 / **decks 1** / refused 2 |
| `sea_wall` / `strip_seam_tear` / `adjacent_ground_step` | 27 / 0 / 0 | **27 / 0 / 0** |
| census LAW-TRUE / ADJUDICATED | 178 / 61 | 172 / **55** |

**VMMC's bars are MET**: `-2488@0` and `-5508+-5507+-2489@0` build **0
decks**.  The ONE deck left anywhere at VMMC is `-2088` on `-4787@1` at
**s 0.0–9.1**, kept by witness (i) — `tunnel=yes` on the bore it actually
stands over, at the mouth.  Every other candidate reads `tag witness
none; DEM cut 0.00 m` (the field is flat at Z0 6.10) and does not sever,
**including all five Macau LRT viaduct crossings** (`-5188`, `-4244`,
`-2898`, `-2736`) and the two 0.15–0.17 m sea-level readings.  The
+22+113 feed refreshed at 11:05 does NOT make (i) fire for them: the
decks stand over the untagged seafront approach, not over the tagged
bore, which is the distinction the ruling drew.

#### OTHH — UNCHANGED

44 tunnels, **1 deck** (`object_deck:dsf:obj269`), 10 basins, 9 object
corridors, 4 door wells — identical to the base at main.

#### LEMD — 5 OF THE 7 APPROVED DECKS, AND THE TWO LOST ARE NAMED

| deck | tag witness | DEM cut | verdict | approved 7? |
|---|---|---|---|---|
| `-6288` | none | **+2.03 m** | SEVERS by (ii) | yes |
| `-11828` | none | **+1.34 m** | SEVERS by (ii) | yes |
| `-14230` | none | **+0.81 m** | SEVERS by (ii) | yes |
| `-516` | none | **+2.33 m** | SEVERS by (ii) | yes |
| `-1378` | none | **+1.79 m** | SEVERS by (ii) | yes |
| `-374` | none | +0.92 m | SEVERS by (ii) | no — grouped into its partner |
| `-15311` | none | +2.35 m | SEVERS by (ii) | no — grouped |
| `-1379` | none | +1.60 m | SEVERS by (ii) | no — grouped |
| **`-5305`** | **none** | **−0.57 m** | **does not sever** | **YES — LOST** |
| **`-15293`** | **none** | **−1.46 m** | **does not sever** | **YES — LOST** |
| `-639` | none | −1.01 m | does not sever | no (its tunnel is unbuilt at base) |

LEMD emits **5 decks** (`-6288`, `-11828`, `-14230`, `-516`, `-1378`)
against the approved 7; tunnels 55 → 56, basins 0 → 0, underpasses
1 → 1.  The ramp lengths that change: `-1341+-1339@1` `top_s` 180 → 24 m
(`-15293` lost), `-1581+-1568@1` keeps `top_s` 552 m and `climb_from_s`
287.1 (it still has `-1378`), `-5931@0` 96 → 120 m and `-5931@1`
36 → 48 m (deckless — §34 (12) (3)'s stop, not (4)).

**WHY THE TWO ARE LOST, AND IT IS THE RULING'S OWN WORDS.**  The ruling
expected `-5305`, `-1378` and `-15293` to be kept by (i) `layer −1`.
Their bores DO carry `layer=-1 tunnel=yes` — but (i) as ruled is "the
corridor's way beneath the deck's SPAN", and **neither span stands over
its bore**: `-5305` crosses at s 103.3 m and `-15293` at s 146.2 m of the
approach walk, while the bore chains `-1581+-1568` and `-1341+-1339` end
far short of them.  `-1378` is kept only because its DEM cut is +1.79 m.
Reading (i) as "any way of the corridor carries the tag" would keep both
— and would also sever **every** VMMC deck, since VMMC's bores are
`tunnel=yes` too; that is the defect the whole section exists to remove.
So the two readings cannot both hold, and this lane implemented the one
the ruling states.  **`-5305` and `-15293` are REPORTED as lost, not
tuned around.**

#### Twins and fixtures

`test_a_deck_severs_only_where_a_CUTTING_is_witnessed` pins all four
cases the ruling names — a cut deck (+1.34), a tag-only deck (cut −1.46
with `layer −1`), a VMMC 0.00 deck, a stale-feed deck judged by (ii)
alone — plus the one the LEMD loss turns on: **a tagged bore the span
does not reach witnesses nothing**.  Two pre-existing fixtures asserted
"the deck severs" over FLAT synthetic ground, which is the VMMC defect
rather than a deck; both now carry a 1 m cutting under the span, bounded
across the corridor so the abutments stand on the ordinary ground the
comparison is against (`test_m4._PlaneDem`, `test_v2wallplate`'s
`_Cutting`).

## §34 (12) (5) A BORE THAT ENTERS A BUILDING IS THE BUILDING'S RAMP, NOT A TERRAIN TUNNEL; THE SIM'S ELEVATED ROADS CARRY BRIDGES (owner RULINGS 2026-09-16d; Fable 2026-09-16) — lane `v2vmmcbore`

Owner 2026-09-16: "There should be no tunnels cut at VMMC because all
of the roads are above ground, all the bridges/overpasses/ramps are
handled by elevated roads provided by the sim, they don't need any
trenches cut."  VMMC after r6 still built `tunnel:-2488@0` (an 84 m
ramp at an OSM `highway=service tunnel=yes` bore 188 m from the owner's
probe) and `-2088` on `-4787@1` — car-park ramps under Taipa's
buildings, admitted by the mouth (12ab).  RULED (OSM-derived bores
only; pack-stated corridors are authored geometry and untouched):
(a) a bore whose covered end enters a BUILDING footprint, an
underground parking (`amenity=parking` + `parking=underground` /
`multi-storey`, `building=parking`) or a `covered=yes` structure is
the building's own ramp — the object or the sim carries it; it is NOT
built as a terrain tunnel; (b) a mapped bridge / overpass / ramp
(`bridge=yes`, `layer ≥ 1`) over ordinary ground is the sim's elevated
road; the terrain neither severs nor trenches for it (§34 (12) (4)
already: no witnessed cutting → no deck); (c) a terrain tunnel is an
OSM bore that passes UNDER something at grade — pavement, a pad, a
road, a railway, ground witnessed as a cutting (the deck witnesses of
(4)) — with a mouth on the field (12ab).  At VMMC every bore fails (c):
expected 0 tunnels, 0 ramps, 0 rims; the sea wall and quays of §37 (11)
unchanged.  LEMD (55/56 tunnels — real road tunnels under the field,
`layer −1/−2`) and OTHH (44, pack corridors) unchanged tunnel for
tunnel; SPJC/KCLT/CYXY named if any bore changes.  The building/parking
witness comes from the OSM feeds already cached (the airports layer
carries `building=*`; the small-roads layer the `amenity=parking`
polygons — say if it does not).

## §34 (12) (4) AMENDED (2) — WITNESS (i) READS THE CORRIDOR, NOT THE SPAN (owner RULINGS 2026-09-16f: shapes 981 and 988 span real cuts; conditional on (5)) — lane `v2vmmcbore`

The owner checked the two decks §34 (12) (4) dropped (shape 981 =
`bridge_deck:-5305` at 40.4788711, −3.5787587; shape 988 =
`bridge_deck:-15293` at 40.4659974, −3.5811339): "both span real
cuts."  The DEM witness (ii) read −0.57 / −1.46 m there (a coarse
reading against sloping abutments) and witness (i) as written asked
the way beneath the SPAN, which is the untagged approach.  The
narrowness of (i) existed only to keep VMMC's seafront decks out; with
(5) no OSM bore is built at VMMC at all.  RULED: (i) reads the
CORRIDOR — a deck severs the climb where ANY way of the bore chain it
crosses carries `tunnel=yes` or `layer ≤ −1` in a schema-current feed;
(ii) the DEM cut stays as the second witness.  Expected: LEMD returns
to exactly the seven approved decks (`-6288 -11828 -14230 -516 -5305
-1378 -15293`; the grouped partners `-374/-15311/-1379` follow their
groups); OTHH 44 / 1 unchanged; VMMC 0 (by (5)); SPJC/KCLT/CYXY any
deck that changes named.  Twins: the two LEMD decks (tag-only via the
chain), a VMMC-shaped case (a bore that enters a building → no
corridor → no deck), a chain with no tag and no cut (no sever).

### §34 (12) (5) CONSUMER CENSUS (owner RULINGS 2026-08-30l), written BEFORE the first consumer was edited — lane `v2vmmcbore`

§34 (12) (5) is a REGION SHRINK at a SINGLE derivation site: fewer bores
admitted.  It mints no shape class, no role, no ref and no sidecar key, so
the table's job is the same as (12)'s own — prove each reader is
COUNT-SENSITIVE ONLY.  The gate stands in `planar/structure_approach.
mouths()`, which is where admission has stood since owner 12ab, so no
consumer downstream of it can tell a refused bore from one that never had
an on-field mouth.

**A. THE ADMISSION.**

| # | consumer | reads | RULE |
|---|---|---|---|
| B1 | `planar/structure_approach.mouths()` | `bores`, `osm`, `law`, `FieldRegion` | **EDITED, the ONE derivation site of (5).** A bore that fails the (5) reading yields NO mouths. §29 (1)'s own gate is UNCHANGED and runs first, so `mouths_off_field` keeps counting exactly what it counted. |
| B2 | `planar/structure_approach.field_region_for()` | `airport`, `law`, `polys` | **EDITED, reporting only**: the `FieldRegion` now carries the `airport` it was built from, so `mouths()` can reach the DEM and the cover WITHOUT a new argument at `structures.build_structures`'s call site (another lane's file this round). No test of the region changes. |
| B3 | `planar/structure_service.terrain_tunnel_witness()` (NEW) | the law, the cover tree, the OSM ways, the DEM | **NEW, the reading itself** — a pure function, one call site (B1), beside (12) (3)'s and (4)'s readings for the same reason they live there. |
| B4 | `airport/deck_signature.is_enclosure_way()` (NEW) | the OSM tags | **NEW predicate beside `is_tunnel_way` / `is_bridge_way`** — (5) (a)'s building / underground-parking / covered class, ONE spelling (row 27 of §33 (6)'s census: one predicate, never a second). `is_tunnel_way` itself is UNCHANGED: WHICH ways are bores is not what (5) is about. |
| B5 | `airport/osm.TAGS_OF_INTEREST` | the feeds | **EDITED: `covered` added.** (5) (a) names `covered=yes` and the v2 reader's whitelist dropped the tag, so the witness could not be read at all. `O4_Vector_Map.ROADS_TAGS_OF_INTEREST` already keeps it (§45 (9), schema 2026-09-15). Additive: every consumer reads tags BY KEY, so one more key changes no existing reading. |
| B6 | `planar/structures.build_structures` — `with_mouth` / `covered` / `bores_no_mouth` | the mouths `mouths()` returned | **NOT TOUCHED** (another lane's file). A (5)-refused bore is absorbed into `stats.bores_no_mouth`, whose label then covers two populations. THE ONE LINE (5) WOULD OWE `structures.py` is its own counter; it is NOT taken, and the conflation is named in the MEASURED block and in the lane report instead. The refusals themselves are NAMED, one line each, through `mouth_reports`. |
| B7 | `planar/structure_approach.mouth_reports()` | `FieldRegion`, mouths, dropped | **EDITED, reporting only**: emits one `bore not a terrain tunnel …` line per (5) refusal with its evidence, kept apart from the `mouth off-field …` lines — the r1 discipline (two reports are never one region). |
| B8 | `planar/structure_approach.merge_duals` / `apply_plates` / `object_corridor.mouth_covered_by` | the mouth list | UNAFFECTED — the list is shorter; no mouth changes. |
| B9 | `planar/structures` ramp / void / deck / stop machinery, `planar/zones.keepouts`, `planar/basins`, `planar/overlay`, `constraints/*`, `verify/structures`, `emit/osm_adapter`, `tools/check_grade` | the corridors and the records | UNAFFECTED, exactly as §34 (12)'s own census T5–T12 ruled: a corridor that is not built withdraws its own cells, records and rows with it. No family, role or sidecar key is added by (5). |
| B10 | `planar/structure_deck.deck_intervals` + `structure_service.deck_witness_for` | the corridor's decks | **EDITED for §34 (12) (4) AMENDED (2)** (16f), and ONLY safely because (5) runs first: witness (i) now reads the CORRIDOR's whole bore chain instead of the way under the span. |

**B. THE (5) (a) WITNESS — WHICH FEED CARRIES IT, PER TILE (the brief's own bar).**

Measured by reading the CACHED feeds directly (`scratchpad/vb/feedtags.py`,
raw XML, before the v2 whitelist):

| tile | feed | closed `building*` rings | `amenity=parking` / `parking=*` | `covered=*` ways |
|---|---|---|---|---|
| `+22+113` (VMMC) | `airports` | **37** (5 within 4 km of the owner probe, all `hangar` / `transportation`, nearest **377 m**) | **0** | 163 |
| `+22+113` | `airport_small_roads` — **the feed the VMMC bores are in** | **0** | **0** | 0 |
| `+22+113` | `big_roads` | 0 | 0 | 258 |
| `+22+113` | `small_roads` (v1 tile layer, not a v2 feed) | **0** of 110,279 ways | 0 | — |
| `+40-004` (LEMD) | all three | 13 rings total | 0 | — |
| `+25+051` (OTHH) | all three | 25 rings total | 0 | — |

**NO CACHED FEED CARRIES THE BUILDING/PARKING WITNESS AT THE VMMC SITE.**
Ortho4XP's general building layer is commented out (`O4_Vector_Map.
include_buildings`), the `airports` feed's buildings are the aerodrome's
own, and `amenity=parking` polygons are mapped in NO feed at any of the
three tiles.  So (5) (a) can NEVER fire at the owner's site: the Taipa
car-park buildings the bores enter are not in the data.  **Reported, and
the round does NOT stop on it** — because (5) (c) is a POSITIVE test over
data that IS present, and the measurement below shows it separates the
owner's site cleanly.  (a) is implemented anyway (it costs one predicate
and fires at LEMD, where two bores DO end inside a mapped
`building=transportation`); a feed change is what it would take to make it
bite at VMMC, and that is the owner's call, not this lane's.

### §34 (12) (5) + §34 (12) (4) AMENDED (2) **MEASURED** (lane `v2vmmcbore`, 2026-09-16, branch `claude/v2vmmcbore`, base main `ae0f956f`)

**THE FRAME.**  One tree per arm, one corpus, the lane-local mod-cache
overlay.  BASE = the ritual worktree `v2vmmcborebase` at main `ae0f956f`;
ARM = this branch.  The base VMMC build reproduces lane `v2vmmcshore`
r6's shipped closing build EXACTLY — **`body_sha ecc616c4bba5`**, the
same hash 15ap's r6 block records — so the pair is anchored to the
patch the owner read.

#### THE CLOSING VMMC BUILD

`build_airport.py VMMC --tag v2vmmcbore1`: **rc 0, 16.5 s**, `status
optimal`, `body_sha 420018b72b91`, artifact ledger **`dc9747f8d707`**,
and verbatim:

> `[harness] shared repo UNCHANGED by this build (full-surface before/after snapshot) — no side-effect mutation`

| bar | BASE = r6 (`ecc616c4bba5`) | ARM (`420018b72b91`) |
|---|---|---|
| owner probe 22.1618794, 113.579745 | covered by nothing; **nearest structure vertex 188 m** | covered by nothing; **nearest structure vertex 1,816 m** |
| `tunnel_ramp` + `structure_rim` faces | **14** | **2** |
| tunnels (dry `--stage structures`) | **13**, decks **1** (`bridge_deck:-2088` on `-4787@1`) | **2**, decks **0** |
| `-2488@0`, `-5508+-5507+-2489@1`, `-4787@1` (the owner's own bores) | built | **NOT BUILT**, each named with its evidence |
| ramp + rim standing on the sea | 0.00 m² | **0.00 m²** (both survivors are inland, 1.8 / 4.7 km from the shore probe) |
| patch nodes at or under 0.5 m | 0 | **0** |
| `pav5` | 5.09 … 6.12 | **5.09 … 6.12** — unchanged |
| `sea_wall` | **27 rows**, worst 6.100 m | **27 rows**, worst 6.100 m — unchanged |
| cockpit CRITICAL motion / visual | 11 / 93 | **11 / 81** |
| census LAW-TRUE / ADJUDICATED | 172 / **55** | 169 / **59** |
| ways / nodes | 117 / 2,657 | 91 / 2,360 |

**THE BAR IS `tunnels 13 → 0` AND IT IS MISSED BY 2 — HERE IS WHAT THE
TWO ARE.**  Nine of VMMC's twelve admitted bores are the car-park ramps
the owner's site is about and all nine are refused.  The other three
(two records after the dual merge) are REAL MACAU ROAD TUNNELS, and the
measurement separates them without a single tuned number:

| bore | length | cover | at-grade over it | ground over it | `layer` | verdict |
|---|---|---|---|---|---|---|
| `-2488` | 36.6 m | 0.0 m | none | **+0.00 m** | none | NOT BUILT |
| `-5508+-5507+-2489` | 37.0 m | 0.0 m | none | **+0.00 m** | none | NOT BUILT |
| `-4787` | 25.2 m | 0.0 m | none | **+0.00 m** | none | NOT BUILT |
| `-6965+-2516` / `-6914` / `-5049` / `-3313` / `-2849` | 22–37 m | 0.0 m | none | **+0.00 m** | none | NOT BUILT |
| `-2388` | 26.7 m | 0.0 m | none | **+0.33 m** | none | NOT BUILT |
| **`-5994+-5993`** | 214 / 224 m | 0.0 m | **`-14967`, `-14962` (`primary`)** | **+1.10 / +1.36 m** | **−2** | **BUILT** — mouth 22.1517293, 113.5646767, **1,816 m** from the owner's probe |
| **`-2577`** | 264.3 m | 0.0 m | **`-3762`, `-3763` (`primary`)** | **+10.53 m** | **−1** | **BUILT** — mouth 22.194078, 113.5500071, **4,709 m** from the probe |

Both survivors are bored through hills on the Macau peninsula, carry
OSM's own `layer −1 / −2`, and are admitted to the airport at all only
by §31 (2)'s 5 km APPROACH CORRIDOR.  **OWNER QUESTION 16d-1**: the
ruling's expectation is 0 tunnels at VMMC, and the two that stand are
not the class the owner objected to — they are exactly what (5) (c)
calls a terrain tunnel.  Removing them needs a rule this lane may not
author (a distance from the field, or a narrowing of §31 (2)'s corridor
for structures); it is offered with its geometry, not tuned away.

**THE +4 ADJUDICATED, ATTRIBUTED** (`census_rows_diff`: EXACT 103,
MOVED 0, GONE 69, NEW 66).  Every new row stands on stub `-10016` and
junction `-10017` between 22.1621 and 22.1630 — the pavement the eleven
withdrawn corridors used to CUT, which comes back WHOLE and is now
priced across its restored extent (the same mechanism r1 recorded for
`pav5`: "with the tunnel withdrawn the junction came back whole").  The
seven biggest are `within_shape` rows that the census does not
adjudicate (`withdrawn_law_05aa`); the adjudicated move is `taxi_box`
+5 and `airside_no_step` −1, worst 0.490 m at 2.14 % against a 1.52 %
box cap.  Twelve `hairline_pair` rows on `tunnel_ramp` / `service_road`
go with the corridors.  No new family, no new role, no new step.

#### THE MATCHED DRY `--stage structures` PAIRS

| | VMMC base | VMMC arm | LEMD base | LEMD arm | OTHH base | OTHH arm | KCLT base | KCLT arm | CYXY base | CYXY arm |
|---|---|---|---|---|---|---|---|---|---|---|
| tunnels | 13 | **2** | 52 | **47** | 44 | **43** | 23 | **17** | 2 | **2** |
| decks | 1 | **0** | 5 | **7** | 1 | **0** | 1 | **1** | 0 | 0 |
| corridors / wall corridors / basins / door wells / plates | 0/0/0/0/0 | 0/0/0/0/0 | 1/0/1/0/3 | **1/0/1/0/3** | 9/73/10/4/2 | **9/73/10/4/2** | — | unchanged | — | unchanged |

* **LEMD KEEPS EXACTLY THE SEVEN APPROVED DECKS.**  §34 (12) (4)
  AMENDED (2) (16f) restores `-5305` and `-15293` — the two the owner
  checked in the sim and confirmed span real cuts — so the arm emits
  `-6288, -11828, -14230, -516, -5305, -1378, -15293`.  **Bar MET.**
* **LEMD loses 5 tunnel records, and each is named.**  Four are (5)'s:
  `tunnel:-15336@0/@1` (37 m, cover 0, no crossing, ground +0.11 m, no
  layer), `tunnel:-3958@0/@1` (30 m, +0.10 m, standing under two
  `primary` BRIDGES and nothing else — clause (b) exactly) and
  `tunnel:-4054+-4052@*`, whose `-4052` side is refused (+0.17 m) while
  `-4054` (+0.71 m) survives alone.  The fifth is (4)'s:
  **`tunnel:-1341+-1339@0` is refused loudly** — with `-639` now
  severing by (i′), the climb starts at s 531 and "the 8 % climb from
  622.58 at s 531 does not reach the DEM (627.13..641.16) within 600 m".
  `-639` is NOT one of the approved seven (15ap's table: "no — its
  tunnel is unbuilt at base").  **Reported, not tuned.**
* **(5) (a) FIRES AT LEMD AND COSTS NOTHING**: `-15347`, `-15349` and
  `-9263` end inside `building=transportation` rings `-48` / `-79` and
  are refused — none of them had a built tunnel at base, so the built
  population is unmoved.  (a) is a no-op on every built tunnel at every
  airport measured.
* **OTHH: one bore out, one PACK CORRIDOR BACK.**  `tunnel:-11191@0/@1`
  (23 m, cover 0, no crossing, +0.00 m, no layer) is a terminal parking
  ramp and is not built; its own `object_deck:dsf:obj269` withdraws with
  it (decks 1 → 0), and **`wall-corridor:OTHH_Terminal_Parking_VCN_004.
  obj@1` RETURNS** — the base refused it for overlapping that bore.
  That is (5) (a)'s intent measured as a positive: the object carries
  the ramp.  The 9 object corridors, 73 wall corridors, 10 basins and 4
  door wells are byte-identical.
* **KCLT loses 3 bores / 6 records**, all one class: `-11281` (10 m,
  +0.04 m), `-11277` (10 m, +0.25 m), `-11251` (9 m, +0.09 m) — cover 0,
  no crossing, no layer.  Its one deck `bridge_deck:-14164` is unchanged.
* **CYXY IS BYTE-IDENTICAL** — 2 tunnels, 0 decks, nothing moved.
* **SPJC COULD NOT BE MEASURED** and no workaround was taken: its road
  feeds `-13-077_big_roads` / `-13-078_big_roads` are SCHEMA-STALE
  (`o4_tag_schema 2026-07-16`) and the loader refuses by name (RULINGS
  2026-09-15u).  `--refresh-data` is the owner's act; the 15ap addendum
  refreshed six tiles and SPJC's two were not among them.

#### THE (5) (a) WITNESS IS NOT IN THE DATA AT VMMC, AND THAT IS WHY (c) CARRIES THE SITE

The census table above measures it: the feed the VMMC bores live in
(`airport_small_roads`) carries **zero** closed building or parking
rings, the `airports` feed's nearest building ring is **377 m** from the
owner's probe, and `amenity=parking` polygons are mapped in NO feed at
any of the five tiles.  Ortho4XP's general building layer is commented
out.  So the Taipa car parks the bores enter are simply absent, (5) (a)
can never bite there, and every VMMC refusal above is (5) (c)'s.
**A feed change is what (a) at VMMC would take**, and that is the
owner's call.

#### WHAT THIS ROUND DID NOT DO, NAMED

* **`stats.bores_not_terrain` — the ONE line `planar/structures.py`
  would owe (5)** — is NOT taken: that file is lane `v2shellwall` r3's
  and the peer's `v2channel`'s this round.  The refusals are all NAMED
  (one line each, with their evidence, under the structures block) but
  their COUNT is absorbed into `stats.bores_no_mouth`, whose label then
  covers two populations.  Named here so the conflation is not
  discovered later as a defect.
* The two VMMC survivors (owner question 16d-1 above); SPJC (the
  owner's `--refresh-data osm_layers`); any `--refresh-data`; the
  five-airport sweep; any LEMD / OTHH / KCLT / CYXY BUILD; any tile
  build and therefore any mesh reading; any merge into main; any
  RULINGS entry; any new tool (the readings are `harness/
  build_airport.py`, `harness/census.py`, `census_rows_diff.py`,
  `osm_site.py`, `planar --stage structures` and `frames.py`).

#### Build-time impact statement

`terrain_tunnel_witness` builds two STRtrees once per build (VMMC 3,306
road/rail ways and 5 rings; LEMD 6,679 / 13; OTHH 7,199 / 25) and asks
at most four questions per ADMITTED bore (VMMC 12, LEMD 47, OTHH 10);
the DEM read is one sample per 5 m of bore.  Measured whole-build wall
at VMMC: base **17.4 s**, arm **16.5 s** — the arm builds LESS (117 → 91
ways, 2,657 → 2,360 nodes).  Nothing here is within 1 % of either budget
on the wrong side.

#### §34 (12) (5) RE-MEASURED AFTER THE MAIN MERGE (lane `v2vmmcbore`, branch `claude/v2vmmcbore` `b2ead29a`, base main `c4efff90` — v2shellwall r3 and v2shoulderband r2 in)

The merge conflicted in `planar/structure_service.py` (v2shellwall r3
moved `decked_exclusion` / `SURFACE_LINE_KINDS` / `owner_kept` / `parts`
in from `structures.py`); BOTH SIDES ARE KEPT — the conflict was the
`__all__` line alone and every symbol of both lanes resolves.
`docs/frames.jsonl` was unioned, no markers anywhere.

**NOTHING MOVED.**  Matched pairs re-run on the merged trees:

| | base (main `c4efff90`) | arm (merged) | arm (pre-merge `9f4e504a`) |
|---|---|---|---|
| VMMC tunnels / decks | 13 / 1 | **2 / 0** | 2 / 0 — IDENTICAL |
| LEMD tunnels / decks | 52 / 5 | **47 / 7** | 47 / 7 — IDENTICAL |
| LEMD deck set | `-6288 -11828 -14230 -516 -1378` | **the approved SEVEN** (`+ -5305 -15293`) | the same seven |
| VMMC closing build | `ecc616c4bba5`, rc 0, 16.8 s, ledger `07c3f4fcd06e` | **`420018b72b91`**, rc 0, 17.0 s, ledger `b1cb3707f003` | `420018b72b91` — BYTE-IDENTICAL |

Both builds print `[harness] shared repo UNCHANGED by this build`.  The
base control's `body_sha ecc616c4bba5` is the SAME hash it carried at
`ae0f956f` and at v2vmmcshore r6, so neither merged lane moves VMMC's
surface and the pair's frame is unchanged.  Suite on the merged tree:
**1,749 passed, 1 skipped, 1 xpassed, 0 FAILED**.

## Spec (design-surface) §34 (8)

### §34 (8) A CLIMB STOPPED BY AIRSIDE ENDS AT THE PAVEMENT; THE REFUSAL IS THE RAMP'S, NEVER THE CORRIDOR'S (owner RULINGS 2026-09-14n item 2; Fable 2026-09-14; RULINGS 2026-09-14p) — lane `v2othhfix`

When `stop_and_steepen` cannot reach the ground inside `max_ramp_grade`
before the axis enters airside pavement, the ramp ENDS at the pavement edge
at the grade it has, and the residual step is taken by a PORTAL / RIM FACE at
the pavement boundary (a retaining wall — what the pack authors there); the
airside cell is never pulled (airside is king).  A corridor whose trench is
otherwise lawful is CUT with its mouths (§33 (2)); the report names the ramp
refusal and the portal height.  Measure first: the stopped station is snapped
one `grid` short of the cell boundary (`wall_corridor_ramps.py:133`) — at
OTHH `Terminal_Base_2_5.obj@0` the miss is 1.0 pp over 17.1 m (1.88 m of
rise); if recovering that half-metre makes it lawful, say so, and still land
the portal rule for the next one.  BARS: the corridor under the terminal at
25.26621, 51.61134 CUT (trench + both mouths), the portal faces named with
their heights; the five `Terminal_Base_2_1` corridors unchanged; no airside
vertex moves.

### §34 (8) AMENDED — A CLIMB THAT CANNOT REACH AIRSIDE MOVES ITS MOUTH AWAY FROM AIRSIDE (owner RULINGS 2026-09-14u; supersedes the portal of 14p) — lane `v2othhfix`

When `stop_and_steepen` cannot reach the ground inside `max_ramp_grade`
before the axis enters airside pavement, the corridor's MOUTH is moved away
from the airside edge — toward and if need be under the building — by the
run the cap needs (rise / `max_ramp_grade` − the run available); the trench
lengthens by that amount, the ramp runs at the cap from the moved mouth to
the ground, and the corridor reaches full depth under the building.  No
portal step; the airside cell is never pulled; the report names the moved
mouth and the metres it moved.  BAR: `OTHH_Terminal_Base_2_5.obj@0` cut with
both mouths, each mouth's move named (the /a side needs ≥ 1.7 m more run at
10 %); the five `Terminal_Base_2_1` corridors unchanged.

## Spec (design-surface) §34 (9)

### §34 (9) THE PINCHED RAMP (owner RULINGS 2026-09-14ak; Fable 2026-09-14) — lane `v2othhfix`

"All the ramps leading down into/under the terminal are coming out too far
and pulling down the service road edge."  When a corridor's climb-out would
reach a SERVICE ROAD LOCKED TO AIRSIDE (a road edge-sharing or absorbed into
airside pavement, or whose level is an airside contact under §37 (10))
before it reaches the ground:
1. the ramp ENDS at the road edge; the road edge keeps its airside-locked
   level and is never pulled;
2. the ramp runs from that road edge down to the ramp bottom at the
   BUILDING EDGE (the corridor mouth), and the grade cap is LIFTED for that
   pinched run — whatever grade the span requires is lawful;
3. the report names each pinched ramp (`pinched_ramp`: corridor, road,
   span, grade); §34 (8)'s mouth move applies only where no such road
   pinches the climb.
BARS (OTHH, ONE build): every terminal ramp that today extends into a
service road ends at the road edge (list them: corridor, road way, the
road edge's level before → after — unchanged); the ramp bottom at the
building edge unchanged; the pinched grades named; the road-family census
(`road_cross_section`, `road_ramp`, airside vertices moved 0) before →
after; no ramp under the terminal shortened or lost.

### §34 (9) (4)–(5) THE PAINTED ROAD EDGE; FULL DEPTH AT THE BUILDING WALL (owner RULINGS 2026-09-14aq) — lane `v2othhfix`

4. Where the pack carries a road-edge MARKING — a draped `markings` object
   (the class §42 refuses as pavement) whose line runs along the road within
   `road_edge_line_reach_m` (6 m) of the road face's edge and within
   `road_edge_line_parallel_deg` (15°) of it — the pinched ramp ends at the
   PAINTED LINE; the marking witnesses where the road really is.  Without
   one, the face edge stands.  The report names which witness each pinched
   ramp used.
5. The ramp's full-depth point is the corridor's COVERED START — the
   building wall — never the outer end of the retaining-wall bands that
   protrude from it; the protruding stretch is ramp.  BARS (OTHH, ONE
   build): the two pinched ramps end at the painted line east and west
   (named with the marking object and the offset from the face edge);
   `Terminal_Base_2_5@0/a` full depth at the building wall (the ~4 m of
   protruding wall added to the run — the pinched grade before → after);
   airside 0; road edges unchanged.

## RULINGS

## 2026-09-14ak Owner on 1.0.333 OTHH: "looks great" — one item: ramps into/under the terminal come out too far and pull the service road edge down — §34 (9) THE PINCHED RAMP

Owner, verbatim: "OK, OTHH looks great, only little problem left is all
the ramps leading down into/under the terminal are coming out too far
and pulling down the service road edge, so they must, when pinched
between a perpendicular service road that is required to stay locked
with airside, and a building, the grade cap is lifted, and whatever
grade is needed to ramp from the road edge to the bottom of the ramp at
the building edge is allowed."

* RULING §34 (9): when a corridor's climb-out would reach a service
  road that is LOCKED to airside (a road that edge-shares or is
  absorbed into airside pavement — the free-road ruling — or any road
  whose level is an airside contact) before reaching the ground, the
  ramp ENDS AT THE ROAD EDGE: the road edge keeps its airside-locked
  level (never pulled), the ramp runs from that edge down to the ramp
  bottom at the BUILDING EDGE, and the grade cap is LIFTED for that
  pinched run — whatever grade the span requires is lawful, reported
  by name (`pinched_ramp`, grade, span). §34 (8)'s mouth move applies
  only when there is no such road; the ramp never extends into the
  road. Lane `v2othhfix` r2 (same code: `wall_corridor_ramps.
  stop_and_steepen`). The OTHH read otherwise stands as the acceptance
  of 14ac.

## 2026-09-14aq Owner on 1.0.334 OTHH: the pinched ramps still cross the road edge on the EAST side and could go further WEST; use the pack's white edge-line marking as the road edge; full depth at the BUILDING WALL, not the outer end of the protruding retaining walls — §34 (9) (4)–(5)

Owner, verbatim: "OTHH with build 334, the tunnels are still crossing
the road edge line on the East side of the building, but could go a
bit further on the west side. Can you detect the white line marking
from the scenery package that marks the road edge? Also, the ramp is
reaching full depth at the outer edge of the retaining walls which
protrude from the building, probably about 4m, the ramp does not need
to reach full depth until the actual building wall so we can make the
ramp less steep. Make those refinements and build a new app so I can
test."

* RULING §34 (9) (4) THE ROAD EDGE IS THE PAINTED LINE: where the pack
  carries a road-edge marking (the draped `markings` layer-group
  objects §42 refuses as pavement — e.g. `asphalt_white.obj` — a white
  line running along the road within `road_edge_line_reach_m` (6 m)
  of the road face's edge and roughly parallel to it) the pinched
  ramp ENDS AT THAT LINE, not at the OSM/patch road-face edge; the
  marking is the witness of where the road really is. Where no
  marking exists the face edge stands.
* RULING §34 (9) (5) FULL DEPTH AT THE BUILDING WALL: the ramp bottom
  (mouth, full depth) is the corridor's COVERED start — the building
  wall — not the outer end of the retaining-wall bands that protrude
  from it (~4 m at OTHH); the protruding stretch is RAMP, so the
  pinched run gains its length and the grade drops. Lane `v2othhfix`
  r3; then app 1.0.335-candidate (OTHH-only change) for the owner's
  test.

## 2026-09-16i v2channel MERGED (782a50d6) — §45 THE OPEN CHANNEL ships ON: nine rounds, (10)–(20) measured; LGAV one channel on four ways, KPHX one bounded channel, KDFW three on the lidar; six airports byte-identical; the floor family's residual 59 rows / 0.854 m is NAMED for the sim read

Round 9 (25e5e197, main 74090011 merged): §45 (19) `_bank_toe_half`
returns (toe, top) — the toe the first confirmed rise (`toe_rise_m`
0.5 / `toe_confirm_m` 10), the crest ring at the top, the cap a logged
backstop never a width; (19)(a)–(c) carry their law comments; §45 (20)
`crossing_claims` splits hard claims (mapped bores, object corridors)
from §34 (5) synthesised ones — a channel that states the depth takes
the synthesised bore's ways and the bore is not built, reported by name.
LGAV: `channel:0` on −1343/−7021/−2914/−4017, 4 decks, pack datum,
half-width 62.8, "the §34 (5) SYNTHESISED bore(s) over −2914+−4017
YIELD"; KCLT 0 channels, its four taxiway-U bores kept. Replays vs main
74090011: OTHH 43/10, LEMD 47/1, HECA 9/0, KCLT 17/0, CYXY 2/0
IDENTICAL; LGAV tunnels 9 = base, one field (`object-cut:Trench_01.obj@0
replaced_ways` → [], the channel owns the ways) + the lane's two named
refusals; SPJC refuses on both arms (stale neighbours). Channels: OTHH/
KCLT/CYXY 0, LEMD 3, KPHX 1, LGAV 1, HECA 1 (`channel:2`, −13192, neck +
pack, one deck — the owner's read). KDFW ONE build `KDFW_20260916T102720`
rc 0, 301 s, UNCHANGED, ledger 4baf0953372f: three channels ALL on the
(3)(ii) lidar datum, half-widths 43.5 / 43.2 / 13.1 m from the toes
(round 8: the 120 m cap), floors 172.87–173.72 / 172.77–174.85 /
170.11–171.81, `channel_crest_at_edge` 0, hard set 55/147,548 over
0.02 m all `runway_profile` (0 in the channel families),
`channel_floor_at_declaration` 59 rows / worst 0.854 m (r7 378 / 12.626
→ r8 149 / 1.886 → r9 59 / 0.854; `channel:3` 40 rows ≤ 0.508,
`channel:1` 19 rows ≤ 0.854 — its floor emits flat at 173.721 against
a declared 172.866–173.721; `channel:2` 0). Also fixed: `tools/
check_grade.py::_channel_declared_at` carried the superseded two-station
reading (census 85 → 59 vs verify 55 — one law, two instruments).
Suite ON MAIN after the merge: `1781 passed, 1 skipped, 1 xpassed`, 0
failed (`docs/frames.jsonl` append conflict resolved both sides; the
peer's v2padclip registrations were committed by this session in
cf578baa under a v2channel message — a registry append, nothing else).
DECISION (this session, under owner 15aq (6)): the KDFW and KPHX
REPLAYS are clean and the KDFW build's residual is attributed and
bounded (≤ 0.85 m on two channels' floors), so §45 ships ON for app
1.0.343 and the owner's sim reads adjudicate: LGAV's trench (one
channel, four decks), KDFW's three channels (channel:1's 13.1 m width and
flat floor), KPHX's bounded corridor (the road cut 5.1 m under the decks
— the lidar reads no cut there), HECA's channel:2. OWED after the reads:
the floor family to 0 (channel:1's flat floor; the 2-D floor vs 1-D
profile reading), C9 (§19 structure edge), `Corridor.bore_ways` (the
object-corridor half of (13)(b) is inert), the reorder of
`identify_channels` ahead of the corridor/sunken-road/door readers,
SPJC's neighbour refresh, the Chatham box question (16e).

## Tool: osm_site

| `Ortho4XP/tools/osm_site.py` | You have a coordinate and the question is WHAT IS THERE — which ways carry that spot, how they are tagged and roled, how many nodes they have, what altitudes those nodes carry — or you want one way's node chain dumped in order. Reads BOTH OSM dialects this repo produces (the emitted patch's single-quoted attributes with per-node `alt_abs`, and the Ortho4XP road feeds' double-quoted ones, plain or `.bz2`), so a patch and the feed it was built from can be read side by side in one process, at one probe point, in one projection. Several files are reported separately — that is the arm-vs-arm read (an owner artifact against a lane build) an attribution starts from. `--role` scopes to one emitted role, `--dump WAY` prints the chain with per-node altitude and distance, `--json` writes what the report printed. **It measures nothing and derives no law**: every value is read verbatim out of the file, and defect counts come from `harness/census.py` and nowhere else — a private re-count is the census-wrapper defect. A node with no `alt_abs` reports `None`, never 0.0 (no authority claimed it is a real state), and a dangling `nd` ref is reported, never dropped. Promoted 2026-08-12 from the round-20 lane's `kclt_site.py` (patches) and `osmfeed.py` (bz2 feeds) on their SECOND use (RULINGS `7e90032`, promote-on-reuse): two copies of one question asked of two formats, already drifted — one could read `alt_abs`, the other could read bz2, neither could read the other's quoting. **`--contains` is the SECOND question, and it is not the first one** (added 2026-08-28, spec `docs/specs/lemd-pad-authority-carve-spec.md` Acceptance): `--at` reports the distance to a way's nearest NODE, so a point deep inside a large ring reads tens of metres away and NEVER 0.00 m — a lane quoted "1.20 m / 11.60 m outside" off exactly that and a containment read then put both owner probes 9.87 m and 3.88 m INSIDE the pad (`lemd-basin-trench-ramp-extension` Amendment 2). `--contains` asks WHICH RINGS COVER THIS POINT: geometry comes from the harness library's own parser (`check_grade._parse_osm`), imported and never re-spelled, and rings are grouped by `(role, ref)` and decided EVEN-ODD inside each group — a point in a hole ring is OUTSIDE its own pad, not inside two ways. **`--line LAT,LON:LAT,LON [--step M]` is that same containment answered along a SEGMENT, station by station** — the reading a "the plate covers the whole ramp" acceptance is stated in (the carve spec samples the deck line at ~2 m); both ends are always stations, and a run of stations INSIDE NOTHING is itself the finding. Neither prices a law nor counts a defect. **THE THIRD ROAD SOURCE (2026-08-28, LEMD ramp/road fidelity round):** a `.cache` file is the X-Plane DSF VECTOR ROAD NETWORK sidecar (`Airport_mod_cache/<pack>/o4_dsf_road_network_<tile>.cache`), unpickled through the engine's OWN record types (`auto_patch.dsf_road_network`) — never a second DSF parser — and presented as ways so `--at` / `--dump` / `--json` work on it unchanged. Reach for it where the OSM sources are EMPTY and the corridors still come from somewhere: at LEMD the tile carries no small-roads extract and `big_roads` is empty at both tunnel sites, so this sidecar is the only thing that can say how many chains cross a portal, what subtype each carries and whether it drapes (level 0) or flies (level 1+). A node reports NO altitude: the network's third column is a draping LEVEL FLAG, not metres, and it is reported as the `level` / `draped` tags it is. TWO SELECTION FRAMES, and the one in force is printed on every report and carried in the JSON (`selection_frame`): the nearest NODE (the default, the frame every pre-2026-08-28 caller reads in) or the closest approach to the POLYLINE (`--by-line`, the default for a `.cache`, because a DSF segment's shape points stand tens of metres apart while the road passes right over the probe — measured at LEMD item 1: nearest node 34.54 m, line 0.66 m). Both distances are always reported, so the two frames can never be mixed unnoticed. **`--relate` is the FOURTH question, and it is the DUPLICATION one** (added 2026-08-30, spec `docs/specs/othh-tunnel-mouth-canonical-spec.md`): `--at` says WHICH shapes are at a coordinate, `--contains` says which COVER it — neither says HOW THEY SIT AGAINST ONE ANOTHER, which is the whole of a "is this one corridor emitted twice?" question. It reports, per touching pair among the ways `--at` selected, the two areas, the OVERLAP AREA, the SHARED-BOUNDARY LENGTH and the containment verdict — same rings, same metre frame and the same harness-library parser (`check_grade._parse_osm`) as `--contains`, imported and never re-spelled. The shared-edge column is the discriminator the other modes cannot give: two surfaces that TILE (0 m² overlap, a long shared edge) are one surface emitted as two, which reads identically to two neighbours under `--at`. Measured basis (OTHH item 1, owner patch 2026-08-29): service_road -10051 vs tunnel_road -12306 — overlap 0.0 m², shared edge 211.22 m, union area == sum of parts, i.e. one road corridor cut into three shapes. It prices no law and counts no defects. Twin: `tests/test_osm_site.py` (both dialects, both containers, absent-altitude-is-None, radius/role selection, nearest-first order, dump order, dangling refs, the CLI's JSON IS the library's result, the refusals, the nearest-node-is-not-containment trap, the hole ring, the role filter, both-ends stations, the DSF cache source with its two selection frames, `--relate` reporting a tiling pair as 0 m² overlap with a long shared edge and an overlapping pair as overlap, and this index row). **`--relate` reads the FEATURE rings too and the rim's stand-off** (2026-09-08a, lane `v2trenchgap`): the role-less `o4_feature` ways the census skips (`structure_rim`, `gap_interior_ring`) join the ring set as role `feature:<name>`, and each pair carries `boundary_gap_m` (the smallest vertex-to-other-exterior distance over the vertices not on it) with `a_off_b_median_m` / `b_off_a_median_m` (each direction's median) — `gap_m` reads 0 for a rim around its ramp, and the question there is how far the rim's vertices stand off the ramp edge (the mesh wall band's width: OTHH tunnel sites read 1.77 / 1.12 m under 06b's `rim_gap_m`). Quote the median for the side stand-off; the minimum is a corner's. **`--deck-witness STRUCTURES.json` is the FIFTH question, and it is §34 (12) (4)'s** (2026-09-15, lane `v2vmmcshore` r5, RULINGS 2026-09-15al): *does a real CUTTING run under this mapped bridge, or is it a bridge over flat ground the corridor has no business severing?* One row per deck a `planar --stage structures` run read, joined to the road FEEDS the build read: the deck way's own tags and mapped length, the corridor's bore ways with their `layer`/`cutting`/`covered`/`tunnel`/`embankment` witnesses (`CUTTING_WITNESS_TAGS`, kept by `O4_Vector_Map.ROADS_TAGS_OF_INTEREST` since the 2026-09-15 schema), and the structures run's own §34 (12) (4) reading (station, the unaided grade-reach, the verdict) taken VERBATIM from the tunnel's `notes` — the tool decides no verdict of its own. **THE NEGATIVE-ID COLLISION is what it exists to survive**: the road layers and the airports layer each mint their own negative ids, so at LEMD eight of the eleven deck ids carry TWO ways and for five of them the first copy is an `aeroway=taxiway` — a first-copy read presented a motorway bridge as a taxiway and five `bridge=yes` decks as tagless at-grade roads. The copy the STRUCTURE PASS read is selected (`is_bridge`'s tag for a deck, `is_tunnel`'s for a bore) and the copy count is printed. A witness a feed CANNOT carry reports `"schema"`, never `None`: a cache written before the tag schema says nothing about cuttings, and reading that as "no cutting mapped" is the same class of error as a census that drops a law family. **`--dem ICAO` adds the CUTTING PROFILE** — the production DEM (`airport/dem_production`, the same witness the structures run read) where the deck passes closest to the bore, and at `--abutment-m` (40 m) each way along the deck: `cut_m = mean(abutments) − under`, positive for a real cutting. The offsets ACTUALLY used are reported, because a deck shorter than twice the abutment cannot give a symmetric pair and a table that hid that would read one abutment as the ground under the span. It prices no law and counts no defects. Measured basis (r5): LEMD `-6288` +2.03 m, `-15311` +2.35, `-516` +2.33 against VMMC's seafront decks at 0.00 m on the flat field. Twin: `tests/test_osm_site.py` (the bridge copy of a colliding id, `"schema"` vs absent, the bores named from the tunnel id, prices-no-law). |

## Tool: site_read

| `Ortho4XP/tools/site_read.py` | You have a coordinate from an owner's sim read and the question is WHAT THE OBJECT STAGE MADE OF IT — not what the OSM patch says there (`osm_site.py`, the emitted ways) and not one law's defect count (`harness/census.py`). Three products of ONE build, read at ONE point in one process: the emitted DESIGN SURFACE's faces containing or near it (role, ref, side, z min/med/max, node count — a CONTAINING face reads 0.0 m, never the distance to its nearest vertex, which is `osm_site --at`'s own trap); the DSF ROWS standing on it (`OBJECT` / `OBJECT_MSL` / `OBJECT_AGL` with the resource and, where it has one, the written elevation — `None` for a plain `OBJECT`, never 0.0); and the PLAN BODIES whose plan box reaches it, each with its §6 class, its FOOTPRINT UNIT, its surface z and zero and the stage's own ANCHOR REASON verbatim, which is the line that says WHY a body is where the owner saw it. `--patch-dir DIR` resolves `<ICAO>.graded.json` and `o4_v2_placement_<ICAO>.json` by glob (an `obj8_split_report --json` dump works as `--plan`: the same `splits` records), `--dsf-dump` takes a DSFTool TEXT dump — pass the PRISTINE `<dsf>.anchor_bak...text` (`dsf_write.pristine_dsf_path`) when you want the pack as INSTALLED rather than as this repo last wrote it. `--show`, `--max`, `--json`. **It measures nothing and derives no law**: every value is read verbatim out of a product and nothing is written. Promoted 2026-09-14 (RULINGS `7e90032`, promote-on-reuse) from the scratchpad reader of the 14g HECA attribution, re-written for the 14bl LEMD one (scouts `v2heca331` / `v2lemd336o`) and used a THIRD time by lane `v2leafframe` — three copies of one question, already drifted in their hard-coded LEMD paths. Twin: `tests/auto_patch_v2/test_v2leafframe.py`. |

| `Ortho4XP/tools/arm_site_read.py` | The question is about a PLACE across two arms — "is the wall at 35.2077303,-80.9290869 still there, and did anything near it get worse?" — which an A/B leaves open: `census.py --rows-json` itemises rows and `census_rows_diff.py` joins two dumps class by class, but neither can be asked about a coordinate, and `osm_site.py` reads geometry without law rows or pad seats. This is the join: per named `--site`, per arm, the law-true rows within `--radius` with their worst grade and |de|; with `--seats`, the BUILDING PAD seats that moved between the arms — the channel this repo's HECA airside attribution ran through (a pad seat welds into the apron ring, so a seat that moves moves airside; measured 2026-08-12b: 92 of 215 pads, median 0.32 m, and building211's +0.88 m carried +203 apron rows). **It measures no law and counts no defects**: rows are read verbatim out of census `--rows-json` dumps and geometry/altitudes through the harness library's own `check_grade._parse_osm`, so this tool and the census read one file one way; a missing input reports SKIPPED, never zero. FRAMES, both printed: rows are located by the census's own row lat/lon, which for a within-shape pair is the PAIR's position (a 400 m apron chord's row sits far from either endpoint's geometry), so a radius selects rows near the PAIR, not shapes touching the site; seats join by the building's `ref` tag, never by way id or shapeID (both arm-dependent). Promoted 2026-08-12b from the service-corridor lane's `measure_arms.py` on its SECOND use — the named-site table and then the airside attribution. `--welds` (added 2026-08-12c, the corridor-joins round's ruling-4(a) instrument) answers the other question a place can be asked — IS THIS SEAM JOINED? Per site, per arm: the node ids SHARED between the road family (`check_grade._ROAD_FAMILY_ROLES`, read from the census library) and the airside ways, the max |Δalt| two ways carry at a shared node (0.00 is the construction — production values sit on the NODE, so a weld is single-valued; the delta is the torn-weld guard for way-valued rings), the NEAREST UNWELDED approach when nothing is shared (0.999 m at both KCLT mouths, against a 0.5 m weld tolerance), and the `retaining_wall` ways standing at the site with their ids. `--profile` / `--line` (added 2026-08-25, the HECA apron round-2 acceptance) answer the THIRD question a place can be asked — WHAT SHAPE IS THE SURFACE HERE? `--profile` walks every ring of `--profile-roles` (default `apron,graded_strip`) reaching a site and reports its worst consecutive EDGE and its RIPPLE AMPLITUDE, the peak-to-peak inside a 50 m run ALONG THE RING — the same window `apron_drape_read` calls `amp50`, so the two tools spell the ripple one way. `--line NAME=LAT,LON:LAT,LON` orders every emitted vertex in a corridor about an owner-named segment by its station along it, with the step between consecutive stations: the reading an acceptance written as "no unlawful step along the owner line" is stated in, AND the reading that shows a NODELESS VOID, because there an EMPTY STATION LIST IS ITSELF THE FINDING (a region with no emitted vertices contributes no census row however wrong its surface is — the blind spot `nodeless_interiors` counts). Neither prices a law; quote them ARM TO ARM on identical options, never as a verdict. Reach for it whenever an acceptance claim is about a join: **row absence cannot answer it** — a census row exists only between PAIRED geometry, so an unwelded road↔taxiway seam is silent in every census, which is exactly how two 1.0.244 acceptance claims passed over a gap no node could bridge. Twin: `tests/test_corridor_axis_coverage.py`.  **`--behind NAME=LAT,LON:LAT,LON` is the WALL scope** (added 2026-08-29, scorer-v2 round, spec `scorer-v2-class-boundary-spec.md`): the owner states a wall as two coordinates and asks that no airside pavement cross it — `--line` answers what the emitted elevation does ALONG it and `osm_site --line` answers what covers each station ON it, but neither answers the quantitative half, the SQUARE METRES of airside-role pavement sitting on the groundside, which is the number a boundary-cut round moves and therefore the number its acceptance is written in. Per crossing ring it reports the area behind, the node split either side and each side's altitude range — the shape of a wall buried inside one apron (HECA apron 584: 48 nodes at 97.22-104.69 m in front, 95 at 90.77-102.71 m behind). TWO FRAME RULES, both load-bearing: the band is the line's OWN SPAN by `--behind-depth-m` (default 150 m) deep, never a half-plane — unbounded, the far side sweeps in the whole airport and reports 634,371 m² where the local answer is 25,900 (measured at HECA); and the GROUNDSIDE side is decided by the patch — the side carrying less airside pavement — so reversing the two coordinates cannot change the answer and a caller cannot pick it. The closed-ring repeat is dropped before the node split (counting it double reports one extra node on whichever side the ring starts). It prices no law and counts no defects. **THE SEAT JOIN IS NOT FREE (2026-08-31, the buildings round).** `building{N}` is an ORDINAL identifier, so an arm that ADDS or DROPS a pad renumbers every later one and the ref join reports the RENUMBERING as seat motion: measured on the buildings-round HECA arms (pad count 175 -> 176) the ref join said 85 of 174 pads moved, median 2.72 m, max 33.65 m, where the population had barely moved. The tool now DETECTS it — a common ref whose pad centroid is more than `--seat-radius` (15 m) away is named as RENUMBERED, with the advice to re-run — and `--seat-join location` pairs pads by centroid instead (closest pair first, each pad used once; a pad with no partner within the radius is reported as added/dropped, NEVER as a move), which on the same arms reads 28 of 174 moved, median 0.07 m, max 2.32 m. Quote a pad-population round's seat movements under the location join.  **`--airside-near-cuts M` (2026-09-15, lane `v2shellwall`)** answers the question spec §33 (6) B AMENDED is written in — *did airside beside the pack's structure-object cuts move?* (owner RULINGS 2026-09-15bh: "airside beside a shell never moves", bar 0.02 m).  The region is the SIDECAR'S OWN `object_cuts` `outline_ll` (the arm's, else the control's — a cut that did not exist in the control is precisely the case asked about), never a radius the caller typed, so this read and the `object_cut_offset` family are priced against one geometry; the join is the canonical 11-dp lat/lon identity join, never proximity; a vertex present in one arm only is reported as UNJOINED and named, never as zero motion. Reports the joined population, the movers over `--airside-move-floor-m` (0.02 m, §16g (10) (5)'s own bar), the worst mover with its coordinate, both altitudes and its ways' roles, and the movers by role.  Measured on the registered VHHH pair (`VHHH_20260915T120714` → `VHHH_20260915T122604`): joined 1,079, MOVED 633, unjoined 223, worst −6.460 m at 22.30772370921,113.92337437951 (7.31 → 0.85, junction/primary_parallel).  It measures no law and counts no defects. |

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N] [--why-hard-stage 1]` on either a `--replay` arm or a `--why-from PKL`; `--why-from PKL --probe-site LAT,LON [--probe-drop M] [--probe-arm TERM=V ...]`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (**and THE CLUSTERS beside the partition and the groups** — lane ``v2padjoin`` 2026-09-14: a capture without ``Airport.clusters`` leaves §30 (4)'s cluster pad, its apron reach and §16g (10)'s derived pads INERT in every replay of it, so a pads-ON arm silently measures the pads-OFF law; a capture predating them has them DERIVED at replay off its own partition, named on stdout) (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently).  **`--why-hard-stage 1`** reads §20b STAGE 1's OWN ASSEMBLY instead of the full problem's (`solve.design.stage_split`'s drop + fixed): the AIRSIDE hard set, in the rows and the metre scaling stage 1 enforced them under. The full read cannot answer "does the AIRSIDE solve settle" — the airside rows are a subset of 325k whose population and scaling the stage's own drop changes — and that is exactly the claim RULINGS 13y (B) / 13ab / 14as make (lane `v2settle`, which used it to split HECA's "42 unsettled rows" into 9 CONSTANT rows the solve can never move, 6 HELD runway rows at the projection's own bar, and 18 real ones).  The shipped surface is read either way: an airside vertex's z IS stage 1's, so the stage-1 read at the shipped z equals the read at stage 1's own surface (measured identical at HECA). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate).  **`--probe-site LAT,LON` IS THE STABILITY PROBE** (lane `v2qp`, spec §20c, promoted from lane `v2settle` r2's `scratchpad/v2settle/probe3.py`/`probe4.py` on its second use): off a `--solved-out` pickle, one extra `Band` ceiling `--probe-drop` (default 0.30) metres under the ARM's OWN base surface at the vertex nearest the point, re-solved, and the moved set (> 0.02 m) binned by distance from it — 0-40 / 40-100 / 100-250 / 250-500 / beyond, with the worst beyond 250 m, each arm's hard set and its exit line.  `--probe-arm TERM=V` repeated makes it a MATCHED PAIR of `[design]` arms on ONE problem (`--probe-arm solver=fixed_point --probe-arm solver=qp` is §20c's own bar); with none it probes the shipped law alone.  This is the instrument RULINGS 2026-09-14bw's headline was taken on (HECA: 959 vertices moved by one 0.30 m row, 953 beyond 500 m, ZERO within 100 m).  `--design-weight TERM=V` also takes a NON-NUMERIC value now (§20c's `solver=qp`); a value that does not parse as a float is passed through as the string.    **`--placement KEY=V` IS THE CAPTURE-TIME LAW ARM** (lane `v2padqp`, spec §16g (10) (11)): the §16g (10) pad keys (`pad_from_cluster`, `pad_airside_clip`) are read in `classify/evidence._pads` and `planar/overlay` — UPSTREAM of the capture — so `--design-weight` (a `[design]` override applied at REPLAY) cannot arm them and a pads-ON replay of a pads-OFF capture silently measures the pads-OFF law; a matched OFF/ON pair is therefore TWO CAPTURES of one tree, never two edits of the shipped toml (the value is coerced to the key's own type, an unknown key refuses by name, and the arm is recorded in the pickle).  `--capture` also arms `harness/build_airport.arm_shared_repo_protection` — the ONE arming composition — and prints `[guard] shared repo UNCHANGED`.  **`--rule SECTION.KEY=V` IS THE CAPTURE-TIME CLASSIFY ARM** (lane `v2shoulderband`, spec §40 (5)): the same thing for `classify/rules.toml` that `--placement` is for `[placement]` — a CLASSIFY key is read upstream of the capture (the capture HOLDS the classification, so `--from planar` cannot see a classify change at all), which makes a matched pair on one TWO CAPTURES; doing that by editing the shipped toml between the arms is the defect RULINGS 2026-09-15az records (disarming a head by prefix also deleted `foot_row_rulings` and silently re-priced every foot row), so the arm is ONE COMMAND-LINE VARIABLE on one unedited tree instead. `SECTION.KEY=VALUE`, coerced to the key's own type, an unknown section or key refuses BY NAME, and the arm is printed on stdout — e.g. `--rule corridor.runway_shoulder_band=false`.  **`--reclassify PKL` IS THE DRY §40 BAND READ** (lane `v2shoulderband` r2, promoted on its SECOND use per RULINGS `7e90032` — r1 hand-rolled it in a scratchpad for the HECA control and r2 needed it at five airports): a CLASSIFY key cannot be armed at replay, but the capture also carries the `Airport` the classifier ran on, so the CLASSIFY STAGE ALONE is re-run over it on the CURRENT tree with `--rule` as the only variable — seconds against a capture's minutes (LEMD 74-79 s). It prints §40 (5)'s own table: the `runway_shoulder` population (cells, m², each named with its host runway and its worst lateral offset), the runway BODY beside it, what the remainder earned BY ROLE, the worst lateral offset of a shoulder vertex off its own runway's apt.dat axis and how many stand beyond the band (§40 (5) (1)'s own bar, "→ 0"), and the classifier's own `shoulder_band_*` stats; `--json` dumps it with the arm recorded, so no reading is frame-less. It is a DRY read and says so — no planar build, no solve, no emit — so it PRICES NO LAW AND COUNTS NO DEFECTS (defect counts come from `harness/census.py` and nowhere else) and it cannot answer anything downstream of classify: a `runway_step` row or a census family needs a built patch. The axis and the half width are the derivation's own (`classify/roles.shoulder_band`), imported and never re-spelled. Control: re-read on the registered `LEMD capture base e856ce64` it reproduces r1's ON arm EXACTLY (271,086 m² / 19 cells / remainder 273,949 m² in 28 faces). Twin: `tests/auto_patch_v2/test_runway_shoulder.py` (the table IS the classifier's verdict on both arms, band + remainder PARTITION the cell, the arm is recorded).  **A CAPTURE CARRIES THE ARRANGEMENT'S RE-NODE READING** (lane `v2padclip`, spec §16g (10) (12) (2)): `pipeline/publication` publishes the sidecar's `pad_airside_renode` out of a module global `planar/overlay.PAD_AIRSIDE` that only a BUILD fills, so every replay arm published an EMPTY list and read a perfect family — the silent-degradation class. `--capture` now pickles that dict and `--replay` restores it and prints `pad/airside re-node from the capture: deleted N minted M`; a capture written before 2026-09-16 carries none and the sidecar key is then OMITTED, which every reader reads as NOT MEASURED rather than zero.   Twin: `tests/auto_patch_v2/test_v2qp.py` (the probe as a fixture pair) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. **`--stage1-dump OUT.json.gz` / `--stage1-diff A B [--movers AVD.json]` IS THE §20b (3) STAGE-1 POPULATION READER** (lane `v2stagepop`, spec §20b (3) (4), RULINGS 2026-09-16v): off a `--solved-out` pickle (`--why-from`) or off a CAPTURE (`--replay`, the generators re-run under the current tree), it runs `solve/design.stage_split` + `solve/design.assemble` — the assembly the stage actually solves, never a re-derivation — and writes every ROW (least-squares, per-body datum and one-sided, each keyed by its owner/ruling, its terms and its right-hand side), every COLUMN (the reduction's own merged vertex set), every SHEET FACE with its area and every TRIANGLE, all keyed by the canonical 11-dp lat/lon so two arms diff BY IDENTITY (memory `canonical-identity-join`); it REFUSES if its own sheet re-read does not reproduce `DesignReport.triangles`. `--stage1-diff` prints the decomposition §20b (3) (4) asks for — counts, then rows REMOVED / ADDED / **RETARGETED** (the same row over the same vertices at a different right-hand side: a target the groundside moved, never a row of the pad law), the columns, the sheet faces by role and m², the triangles — and with `--movers` (an `airside_value_delta --json`) attributes each moved airside vertex to the class of stage-1 change it stands on, with the far field's distance profile to the nearest change. It SOLVES NOTHING, prices no law and counts no defects (defect counts come from `harness/census.py`). Measured basis (HECA, the v2padclip r2 staged arms, every pad generator dropped): columns 18,495 → 18,499, one-sided rows 1,317,645 → 1,322,265 (`apron` frontage-chord / preferred-tier 4,712 removed / 9,178 added), `apron_trend` 1,107 RETARGETED, sheet faces 892 vs 890 → 859 = 859 once the stage's own roles decide the sheet. |

## Tool: classify

| `Ortho4XP/tools/classify_report.py` | The question is what ROLE a shape was given — the legacy-vs-scorer pavement classification (`pavement_score_decisions`) as a confusion matrix plus a per-shape drill-down with centroid lat/lon to fly to in-sim. Builds the airport (60–90 s) or renders a previous `--json` dump instantly with `--from-json` (no install, no build, no network). `--geometry-only` stops the build at the end of phase 1 — where every classification decision is already made, the scorer being a phase-1 shadow pass — so a role question about an airport whose SOLVE costs half an hour (HECA 1,923 s against ~60 s of geometry) does not cost a whole build; the dump records which frame it was read in. Reads production's own shadow-pass decisions off the layout; it classifies nothing itself. Indexed 2026-08-11 (round 11) — it existed and was absent from this file, so a recon lawfully treated it as absent and answered a role question without it. **The BUILD path is GUARDED (2026-08-11): it arms the build entry's own composition, `build_airport.arm_shared_repo_protection` — the engine derived-cache redirects (`O4_DSF_CACHE_DIR`, `O4_AIRPORT_MOD_CACHE_DIR`, lane-local under `Ortho4XP/tmp/classify_report/classify_<ICAO>.engine_caches`, reported as `engine_cache_redirects` on the report) plus a refuse-mode `SharedRepoWriteGuard`, and a refusal the engine SWALLOWED refuses the run. It armed NEITHER before, and two adjudication runs wrote ten files into the shared corpus (mod-cache sidecars and DSFTool dumps under `+35-081`/`+39-095`) — and the redirect alone would not have saved it: the mod-cache overlay was symlink-seeded and an unguarded writer wrote THROUGH the symlinks (both halves fixed 2026-08-12: copy-on-write seeding + a guard that resolves). `--from-json` renders only, so it builds nothing and arms nothing. Twins: `tests/test_harness.py` §6d.** |

| `Ortho4XP/tools/classify_report.py` | The question is what ROLE a shape was given — the legacy-vs-scorer pavement classification (`pavement_score_decisions`) as a confusion matrix plus a per-shape drill-down with centroid lat/lon to fly to in-sim. Builds the airport (60–90 s) or renders a previous `--json` dump instantly with `--from-json` (no install, no build, no network). Reads production's own shadow-pass decisions off the layout; it classifies nothing itself. Indexed 2026-08-11 (round 11) — it existed and was absent from this file, so a recon lawfully treated it as absent and answered a role question without it. **The BUILD path is GUARDED (2026-08-11): it arms the build entry's own composition, `build_airport.arm_shared_repo_protection` — the engine derived-cache redirects (`O4_DSF_CACHE_DIR`, `O4_AIRPORT_MOD_CACHE_DIR`, lane-local under `Ortho4XP/tmp/classify_report/classify_<ICAO>.engine_caches`, reported as `engine_cache_redirects` on the report) plus a refuse-mode `SharedRepoWriteGuard`, and a refusal the engine SWALLOWED refuses the run. It armed NEITHER before, and two adjudication runs wrote ten files into the shared corpus (mod-cache sidecars and DSFTool dumps under `+35-081`/`+39-095`) — and the redirect alone would not have saved it: the mod-cache overlay was symlink-seeded and an unguarded writer wrote THROUGH the symlinks (both halves fixed 2026-08-12: copy-on-write seeding + a guard that resolves). `--from-json` renders only, so it builds nothing and arms nothing. Twins: `tests/test_harness.py` §6d.** |

## Registered frames: LEMD

LEMD  capture  base ec8723e9   lane v2roadcap        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/rw/cap/LEMD.pkl  [MISSING]  — the v2roadcap-era LEMD capture used by scout v2unsettled2
LEMD  capture  base 864e7577   lane v2settle         2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle  [MISSING]  — fresh main capture + per-law arms + logs (13ak)
LEMD  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/fin_LEMD/structures.json  [MISSING]  — LEMD planar --stage structures on claude/v2gradecache vs the 0c86fe2c base arm in scratchpad/base_LEMD: every basin rim_ll/region_ll/floor_z/ramp_rings_ll/area/notes and every basin refusal BYTE-IDENTICAL; only covered_fraction moves 0.22750697->0.22750614 at the 1 cm plane quantum
LEMD  mesh     base 8fce79cb   lane v2hairline       2026-09-13T17:43:19  /tmp/harness/tile_v2hairline_arm3/Data+40-004.mesh  [MISSING]  — §39 ARM: shore weld ON, metric split ON, vector weld OFF — sub-0.1 m2 in bbox 1,641, aspect p50 1.61, 2,734,780 tris
LEMD  patch    base df67b414   lane v2hairline       2026-09-13T17:43:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/control.osm  [MISSING]  — §39 CONTROL patch (harness tag v2hairline_control) with shore_edges injected from the same TileWater witness — hairline_pair 29 adjudicated
LEMD  capture  base 32c78eaf   lane v2lemd329        2026-09-13T20:49:45  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/cap/LEMD.pkl  [MISSING]  — fresh LEMD v2_solve_replay capture on main 32c78eaf (22158 vertices, 1119 faces, 353 s) — for the sunken-road round
LEMD  mesh     base 00d8b05c   lane v2hairline       2026-09-13T21:16:09  /tmp/harness/tile_v2hairline_r2cp/Data+40-004.mesh  [MISSING]  — §39 round 2 FINAL arm: one witness + project + merge + crossing dedupe + 13cp z carry — 1,617 sub-0.1 m2 in bbox, aspect p50 1.65, 2,745,864 tris, pre-flight 7 UNMESHABLE (all non-patch markers)
LEMD  mesh     base 6b3a57cb   lane v2bankfoot       2026-09-13T21:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2bankfoot/fix/Data+40-004.mesh  [MISSING]  — FIX ARM (13cp): bank rings CLOSED again, open runs wear PATCH_RING_MARKER, ribbon belt — annulus 39,105 of 58,555 valued, harmonic moved 491, isolated components 0, 111 closed bank_foot ways / 0 open; owner site 40.465414,-3.5531888 median 589.00 (1.0.329: 568.3); attr-8 nodes over 2 m = 3 of 275,861
LEMD  mesh     base 6b3a57cb   lane v2bankfoot       2026-09-13T21:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2bankfoot/omit/Data+40-004.mesh  [MISSING]  — OMIT ARM (owner request): [design] bank_omit=true, NO bank_foot emitted — ribbons restored too (attr-8 over 2 m = 4), but patch edge step median 0.740 / p95 5.680 / >3 m 2,584 vs the fix arm's 0.415 / 4.944 / 1,924
LEMD  patch    base 05cf9282   lane v2leafframe      2026-09-14T21:43:48  /tmp/harness/v2leafframeLEMD.osm  [MISSING]  — lane v2leafframe CLOSING LEMD patch build (claude/v2leafframe 443b5c0f, base main 05cf9282): rc 0, 786.0 s, body_sha c917d457d4c6, solve feasible, guard shared repo UNCHANGED (38 external-candidate Masks/OTHH deltas named, another lane's; no artifact-ledger key stored for that reason). THE FIRST frame carrying Part.height_m in ONE frame (RULINGS 2026-09-14bo): 29,684 parts 580-646 m -> 0.000-50.001 m, walled 29,684 -> 12,325. Unit census 22 units / 536 bodies-in-a-unit / largest 236 members spanning 2,855 m -> 20 / 206 / 84 members spanning 1,670 m. Items 2/4/6/9 all OUT of the giant units and on their own ground. Sec17 FLOATING 1305 -> 185, BURIED 2054 -> 1725, feet > 1 m 2427 -> 918. NEW: Sec15 carried float 0 -> 2.
LEMD  rebake   base 05cf9282   lane v2leafframe      2026-09-14T21:43:48  /tmp/harness/v2leafframeLEMD.v2/LEMD.rebake.json  [MISSING]  — lane v2leafframe CLOSING LEMD patch build (claude/v2leafframe 443b5c0f, base main 05cf9282): rc 0, 786.0 s, body_sha c917d457d4c6, solve feasible, guard shared repo UNCHANGED (38 external-candidate Masks/OTHH deltas named, another lane's; no artifact-ledger key stored for that reason). THE FIRST frame carrying Part.height_m in ONE frame (RULINGS 2026-09-14bo): 29,684 parts 580-646 m -> 0.000-50.001 m, walled 29,684 -> 12,325. Unit census 22 units / 536 bodies-in-a-unit / largest 236 members spanning 2,855 m -> 20 / 206 / 84 members spanning 1,670 m. Items 2/4/6/9 all OUT of the giant units and on their own ground. Sec17 FLOATING 1305 -> 185, BURIED 2054 -> 1725, feet > 1 m 2427 -> 918. NEW: Sec15 carried float 0 -> 2.
LEMD  graded   base 05cf9282   lane v2leafframe      2026-09-14T21:43:48  /tmp/harness/v2leafframeLEMD.v2/LEMD.graded.json  [MISSING]  — lane v2leafframe CLOSING LEMD patch build (claude/v2leafframe 443b5c0f, base main 05cf9282): rc 0, 786.0 s, body_sha c917d457d4c6, solve feasible, guard shared repo UNCHANGED (38 external-candidate Masks/OTHH deltas named, another lane's; no artifact-ledger key stored for that reason). THE FIRST frame carrying Part.height_m in ONE frame (RULINGS 2026-09-14bo): 29,684 parts 580-646 m -> 0.000-50.001 m, walled 29,684 -> 12,325. Unit census 22 units / 536 bodies-in-a-unit / largest 236 members spanning 2,855 m -> 20 / 206 / 84 members spanning 1,670 m. Items 2/4/6/9 all OUT of the giant units and on their own ground. Sec17 FLOATING 1305 -> 185, BURIED 2054 -> 1725, feet > 1 m 2427 -> 918. NEW: Sec15 carried float 0 -> 2.
LEMD  capture  base 05cf9282   lane v2leafframe      2026-09-14T21:43:49  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/leafframe  [MISSING]  — DRY one-frame counterfactual arms for LEMD/HECA/KCLT/OTHH/SPJC: oneframe.py rewrites a registered rebake plan's Part.height_m to the authored component extent (the fix's own output, VERIFIED byte-equal to the built LEMD plan), obj8_split_report --json before/after beside each, unitcensus.py + sites.py readers, and the pristine-dump OBJECT_MSL censuses (mslp_b336.txt / mslp_built.txt: LEMD MSL rows 1,481 -> 0).
LEMD  patch    base 87bb9f38   lane v2lemdstruct     2026-09-14T21:49:27  /tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls/base/structures.json  [MISSING]  — BASE dry 'planar --stage structures' at main 87bb9f38: bores 70 / mouths 90 / tunnels 50 / decks 11 / cells cut 3 / plate mouths 2 / basins 1; underpass -1230 clip 5.6 m centreline ribbon, 2 roads bored; basin:0 rim stations beyond 2.0 m = 58 of 69
LEMD  patch    base e5078016   lane v2lemdstruct     2026-09-14T21:49:27  /tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls/r3/structures.json  [MISSING]  — AFTER dry 'planar --stage structures' on claude/v2lemdstruct e5078016 (RULINGS 14bp derivations 1/2/3/4): every count identical to the base bar decks 11 -> 7 (parallel carriageways grouped); underpass clip = the deck CELL across the axis, 772 m2, 2 roads bored; plate mouths CLAMPED (moved 0.9 / 0.1 m, -5931 mouths back at 40.4980351,-3.5850028 and 40.4960205,-3.5849927); basin rim-snap REFUTED (median 19.24 m to the at-grade contour, 11 of 68 within 2 m)
LEMD  patch    base e5078016   lane v2lemdstruct     2026-09-14T22:11:40  /Users/noah/XPTerrainBuilder/.claude/worktrees/v2lemdstruct/Ortho4XP/Patches/+40-010/+40-004/LEMD_auto.patch.osm  [MISSING]  — CLOSING BUILD v2lemdstruct1 (build_airport.py LEMD --tile 40 -4), rc 0, 946.7 s (vector 874.3 + mesh 71.7), shared repo UNCHANGED, verify defects {}, solve feasible 146 rounds 395.5 s. Census vs the 1.0.336 tile patch: ADJUDICATED 2094 -> 1924, road_cross_section 14 -> 8, within_shape 3963 -> 3918, taxi_box 241 -> 178; COCKPIT motion 6 -> 4, visual 1184 -> 1181. Mesh at /tmp/harness/tile_v2lemdstruct1/Data+40-004.mesh
LEMD  mesh     base e5078016   lane v2lemdstruct     2026-09-14T22:11:40  /tmp/harness/tile_v2lemdstruct1/Data+40-004.mesh  [MISSING]  — v2lemdstruct1 tile mesh: the bridge transect at lat 40.4835412 over lon -3.5812..-3.5788 reads 610.88 -> 606.15 -> 607.13 with NO station-to-station step over 0.5 m; the residual dip past the owner's east end 40.4835412,-3.5799114 is 0.73 m peak-to-trough (the 1.0.336 read was a 2.2 m notch)
LEMD  capture  base da8e5d7f   lane v2lemdstruct2    2026-09-15T08:29:03  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/cap/LEMD.pkl  [MISSING]  — fresh LEMD v2_solve_replay capture on claude/v2lemdstruct2, base main da8e5d7f (20,608 vertices, 1,024 faces, 286 s; clusters 7776, pack partition 115 s) — the 15e items 5/7 round (33 (5), 34 (11), 34 (5) (b))
LEMD  patch    base da8e5d7f   lane v2lemdstruct2    2026-09-15T09:14:50  /Users/noah/XPTerrainBuilder/.claude/worktrees/v2lemdstruct2/Ortho4XP/Patches/+40-010/+40-004/LEMD_auto.patch.osm  [MISSING]  — lane v2lemdstruct2 CLOSING LEMD tile build (tag v2lemdstruct2, branch claude/v2lemdstruct2 @ 5ed9b083, base main da8e5d7f): rc 0, 551.8 s (vector 491.5 + mesh 59.5), solve optimal 40.4 s, ledger tree 3e3e13880a2a. WARNING: the harness flagged the run CONTAMINATED — it rewrote OSM_data/+40-010/+40-004/+40-004_big_roads.osm.bz2 (2,197,226 -> 2,199,670 bytes), the v2roadtags ROAD_CACHE_TAG_SCHEMA bump merged into main the same morning; the matched REPLAY pair off the registered capture is unaffected. 33 (5): item-5 mouth floor 599.25 -> 597.09 under a rim at 602.16 = 5.07 m vs bore_datum_m 5.10. 34 (5) (b): item-7 trench mouth 12.77/15.46 m -> 31.06/33.43 m from the owner node, beyond the 19.0 m code-E strip; zone1 intact at 18.15 m. Census: ramp_in_strip 11 -> 8 (all runway-strip), wall_in_runway_strip 10 -> 6, tunnel_mouth_canonical 32 -> 28
LEMD  mesh     base da8e5d7f   lane v2lemdstruct2    2026-09-15T09:14:50  /tmp/harness/tile_v2lemdstruct2/Data+40-004.mesh  [MISSING]  — lane v2lemdstruct2 CLOSING LEMD tile build (tag v2lemdstruct2, branch claude/v2lemdstruct2 @ 5ed9b083, base main da8e5d7f): rc 0, 551.8 s (vector 491.5 + mesh 59.5), solve optimal 40.4 s, ledger tree 3e3e13880a2a. WARNING: the harness flagged the run CONTAMINATED — it rewrote OSM_data/+40-010/+40-004/+40-004_big_roads.osm.bz2 (2,197,226 -> 2,199,670 bytes), the v2roadtags ROAD_CACHE_TAG_SCHEMA bump merged into main the same morning; the matched REPLAY pair off the registered capture is unaffected. 33 (5): item-5 mouth floor 599.25 -> 597.09 under a rim at 602.16 = 5.07 m vs bore_datum_m 5.10. 34 (5) (b): item-7 trench mouth 12.77/15.46 m -> 31.06/33.43 m from the owner node, beyond the 19.0 m code-E strip; zone1 intact at 18.15 m. Census: ramp_in_strip 11 -> 8 (all runway-strip), wall_in_runway_strip 10 -> 6, tunnel_mouth_canonical 32 -> 28
LEMD  patch    base da8e5d7f   lane v2lemdstruct2    2026-09-15T09:14:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/base_emit/LEMD_auto.patch.osm  [MISSING]  — BASE ARM of the matched replay pair (v2_solve_replay --replay on the registered da8e5d7f capture, base tree, --emit): LAW-TRUE 5688 / ADJUDICATED 1341, ramp_in_strip 11, strip_transverse worst 5.589 m, within_shape 3397, tunnel_mouth_canonical 32; item-5 floor 599.25 under rim 602.16 (2.91 m); item-7 ramp at 15.46 m, 572.02-572.42 under a 577.84 kerb
LEMD  patch    base da8e5d7f   lane v2lemdstruct2    2026-09-15T09:14:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/a4_emit/LEMD_auto.patch.osm  [MISSING]  — ARM of the matched replay pair (--from planar, 33 (5) + 34 (5) (b)): LAW-TRUE 5756 / ADJUDICATED 1404, ramp_in_strip 8, strip_transverse worst 13.872 m, within_shape 3464, tunnel_mouth_canonical 28
LEMD  capture  base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/LEMD.on3.pkl  [MISSING]  — LEMD PADS-ON capture (v2_solve_replay --capture --placement pad_from_cluster=true --placement pad_airside_clip=true, 219 s, 20,473 vertices / 1,011 faces, guard shared repo UNCHANGED) - the FIRST LEMD capture carrying the derived cluster pads; the T4 cluster unit:25#843 (421,940 m2, 761 walled, PKT4 a member) mints ONE pad containing the owner's garage at 40.4892214,-3.5944287. Its matched OFF arm is cap/LEMD.off3.pkl
LEMD  capture  base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/LEMD.off3.pkl  [MISSING]  — LEMD PADS-OFF capture (--placement pad_from_cluster=false pad_airside_clip=false = the shipped law), 226 s, 21,348 vertices / 1,058 faces, guard UNCHANGED - the BASE ARM of the v2padqp LEMD pair; reproduces 15h's garage reading (nearest pad building12 55.3 m away, median 616.35)
LEMD  patch    base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /tmp/harness/v2padqpLEMD2.osm  [MISSING]  — CLOSING BUILD v2padqpLEMD2 with BOTH §16g (10) pad keys ARMED (the measurement arm; the branch SHIPS them false): rc 0, 346.3 s, ways 1048, nodes 20304, status optimal, body_sha e5d30cf207a8, artifact ledger 50546224d866, v2-verify 1,633 rows, '[harness] shared repo UNCHANGED by this build (full-surface before/after snapshot)'. The owner's T4 garage at 40.4892214,-3.5944287 is INSIDE pad building45 (93-node face, every face of the ref at median 615.35) and the pad law defeats the spurious basin:1 there
LEMD  patch    base 9c313551   lane v2lemdstruct2    2026-09-15T09:47:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/b2_emit/LEMD_auto.patch.osm  [MISSING]  — r2 SHIPPING ARM (v2_solve_replay --from planar on the registered da8e5d7f capture, tree = claude/v2lemdstruct2 r2): solve optimal 54.5 s; v2 verify 1,576 rows (within_shape 466 -> 422 under 34 (13) (1)'s axis reading, tunnel_mouth_canonical 28, wall_in_runway_strip 6); census LAW-TRUE 5,712 / ADJUDICATED 1,360, within_shape 3,420, ramp_in_strip 8, strip_transverse worst 13.872 m. Surface byte-equal to r1 at both owner sites (item 5 floor 597.09 under rim 602.16; item 7 mouth 31.06/33.43 m). NO BUILD: the osm_layers refresh RULINGS 15u calls for has not been run
LEMD  patch    base 9c313551   lane v2lemdstruct2    2026-09-15T09:47:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/b1_emit/LEMD_auto.patch.osm  [MISSING]  — 34 (13) (2) REFUTED ARM (outermost airside strip; the code is DELETED): every bar moved backwards - ramp_in_strip 8 -> 19 (bar was 0), strip_transverse 83/13.872 m -> 90/19.070 m, verify wall_in_runway_strip 6 -> 20, cockpit CRITICAL visual cliffs 10 -> 24, ADJUDICATED 1,360 -> 1,372; the trench mouth 31.06/33.43 -> 41.67/43.25 m, still inside 14R/32L's 75 m strip. Kept as the refutation record
LEMD  patch    base 106459fa   lane v2objcut         2026-09-15T09:44:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/r4_LEMD/structures.json/structures.json  [MISSING]  — §33 (6) LEMD matched pair (base /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/b4_LEMD/...): the same six arrays BYTE-IDENTICAL (1/50/0/1/3/0), plate_mouths 2->2, crest_from_approach 2->2, underpasses 1->1; +25 named §33 (6) refusals only.
LEMD  patch    base f32fb08c   lane v2channel        2026-09-15T10:23:51  /tmp/v2channel/r3/br_LEMD/structures.json  [MISSING]  — v2channel round-3 DRY structure replay (branch), paired with base LEMD at main 46b219d8 in /tmp/v2channel/r3/base_LEMD
LEMD  patch    base 539e524e   lane v2lemdstruct2    2026-09-15T10:24:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/c6_emit/LEMD_auto.patch.osm  [MISSING]  — r3 CLOSING ARM (v2_solve_replay --from planar on the registered da8e5d7f capture, tree = claude/v2lemdstruct2 r3): solve optimal 45.9 s, v2 verify 1,564 rows. 34 (13) (3) junction_raw_transverse ON as a one-way TARGET (1,591 rows, 62 contacts) - the owner's pair at 40.4611623,-3.5444804 still 4.296 % over 18.2 m; hard refuted twice (all 1,591: 10,006/109,240 violated worst 60.48 m; the 62 contacts alone: 8,548/106,182 worst 105.29 m). 34 (13) (4) mouth_pair_roads ON: 4 faces / 3,775 m2 at LEMD incl. mouth_road:-5944 (way -10867, 605.09-611.00 m, worst edge 8.00 % at the road cap), KCLT 3 / 3,564 m2, OTHH 0. Census ADJUDICATED 1,360 -> 1,344, LAW-TRUE 5,712 -> 5,692, transverse 107 -> 98, airside_no_step 475 -> 460. Hole ring -10670 cover 0.011 -> 0.023, rings > 10,000 m2 13 -> 13. NO BUILD: the ledger's last osm_layers refresh is 2026-09-08 (SPJC)
LEMD  patch    base 539e524e   lane v2lemdstruct2    2026-09-15T10:24:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/c1_emit/LEMD_auto.patch.osm  [MISSING]  — r3 arm c1 (constraints-stage): junction_raw_transverse as a SOFT one-way target only, no mouth roads - solve optimal, verify 1,549, transverse 115 -> 97, airside_no_step 457 -> 451, the owner's crossfall pair UNCHANGED at 5.01 %. The measurement that says the raw-pair row is correct and does not bind
LEMD  patch    base 848bf35e   lane v2lemdstruct2    2026-09-15T11:36:11  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/d5_emit/LEMD_auto.patch.osm  [MISSING]  — r4 CLOSING ARM (v2_solve_replay --from planar on the registered da8e5d7f capture, tree = claude/v2lemdstruct2 r4): solve optimal 226.1 s, v2 verify 1,547 rows, DEFECT families ALL ZERO. 34 (13) (3) (a) the foot-row flip ON (LEMD 184 one-way of 524 targets). THE OWNER'S CROSSFALL, by coordinate: contact 582.586 / far edge 582.309 over 18.12 m = 1.529 %, under the 1.985 % junction cap (r3 read 4.313 %); 0 census rows within 20 m. PRICE: 354 of 4,031 runway-family vertices moved > 0.02 m, worst 5.687 m; ramp_in_strip 8 -> 18, strip_transverse worst 13.864 -> 17.700 m, cliffs 10 -> 20, a NEW mid_edge_step 0.950 m between two runway faces at 40.4613609,-3.5446852. Census LAW-TRUE 5,791 ADJUDICATED 1,357 (airside 1,251 -> 1,215). NO BUILD: the ledger's last osm_layers refresh is 2026-09-08
LEMD  patch    base 106459fa   lane v2objcut         2026-09-15T10:44:12  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/c6_LEMD/structures.json/structures.json  [MISSING]  — r2 §33 (6) C lane arm at claude/v2objcut 3b3259dd (base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/b4_LEMD/...)
LEMD  patch    base 395bd09a   lane v2channel        2026-09-15T10:52:05  /tmp/v2channel/r4/br_LEMD/structures.json  [MISSING]  — v2channel round-4 DRY structure replay (branch, §45 (13)); base arm at main in /tmp/v2channel/r4/base_LEMD
LEMD  patch    base e78c9728   lane v2channel        2026-09-15T11:14:01  /tmp/v2channel/r5/br_LEMD/structures.json  [MISSING]  — v2channel round-5 §45 (13)(d): LEMD channel:5's three pack witnesses (dsf:obj7/obj8/obj10 = LEMD37/LEMD85/LEMD36) ARE built basin:0's members, floor 588.952 both — channel:5 refused as ruled; channels 3 (channel:1/:2/:4, all neck+clearance); tunnels 51->51 IDENTICAL, basins 1->1 IDENTICAL vs /tmp/v2channel/r5/base_LEMD.
LEMD  patch    base d803147a   lane v2lemdstruct2    2026-09-15T12:24:50  /Users/noah/XPTerrainBuilder/.claude/worktrees/v2lemdstruct2/Ortho4XP/Patches/+40-010/+40-004/LEMD_auto.patch.osm  [MISSING]  — r5 CLOSING BUILD (build_airport.py LEMD --tag v2lemdstruct2r5 --tile 40 -4), rc 0, 980.1 s, ledger tree fddb2fc4a8c6, [harness] shared repo UNCHANGED (full-surface before/after snapshot). THE ACCEPTANCE NUMBER: the owner's raw pair at 40.4611623,-3.5444804 reads 0.280 m over 18.16 m = 1.542 %, under the 1.985 percent junction cap (r3 read 4.313). Item 5 rim 602.16 / ramp floor 597.09 = 5.07 m; item 7 trench rim at 31.06 m; 3 mouth roads. Census LAW-TRUE 6,024 ADJUDICATED 1,934, ramp_in_strip 18, mid_edge_step 2 (0.950 m), strip_transverse 89/17.700, transverse 92, airside_no_step 362, cliffs 20
LEMD  patch    base d803147a   lane v2lemdstruct2    2026-09-15T12:24:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/e_off_emit/LEMD_auto.patch.osm  [MISSING]  — r5 MATCHED PAIR, flip OFF arm (the r4 foot-row one-way registration OUT; one tree, one capture, registers asserted before the arm). Verify 1,711 rows; census LAW-TRUE 5,782 ADJUDICATED 1,505 (airside 1,370); CRITICAL motion 7, cliffs 20; mid_edge_step 2 worst 0.950 m; ramp_in_strip 18; the owner's raw pair 4.313 percent. Its ON twin is e_on_emit. THIS PAIR CORRECTS r4, whose runway figures compared arms across a main merge
LEMD  patch    base d803147a   lane v2lemdstruct2    2026-09-15T12:24:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/e_on_emit/LEMD_auto.patch.osm  [MISSING]  — r5 MATCHED PAIR, flip ON arm. Verify 1,554 rows; census LAW-TRUE 5,712 ADJUDICATED 1,393 (airside 1,258); CRITICAL motion 5, cliffs 20; mid_edge_step 2 worst 0.950 m (SAME as the OFF arm - it is NOT the flip's doing); ramp_in_strip 18 (same); airside_no_step 452 -> 357, taxi_box 152 -> 130, transverse 98 -> 90, strip_arc 9 -> 4; within_shape +62 and strip_transverse worst 13.864 -> 17.700 m are the flip's real price; the owner's raw pair 4.313 -> 1.529 percent. Runway movement 319 of 4,042 vertices > 0.02 m, worst 5.687 m - attributed to a 111,648 m2 40 (1) runway SHOULDER (cell 15 / face 5) reaching 914 m off the centreline, on which no level row exists
LEMD  patch    base f912ba81   lane v2objcut         2026-09-15T12:02:00  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e1_LEMD/structures.json/structures.json  [MISSING]  — r3 lane dry --stage structures at claude/v2objcut edf1e3c0; matched base arm at main f912ba81 in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e0_LEMD (LEMD) / /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e2_LEMD (OTHH, run 2 - run 1 e0_OTHH read 7 corridors against run 2's 9 at the SAME sha: main's object-corridor reader is NONDETERMINISTIC at OTHH, reported).
LEMD  patch    base f912ba81   lane v2objcut         2026-09-15T12:02:00  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/f1_LEMD/structures.json/structures.json  [MISSING]  — r3 C3' arm with deck_rings_ll published (base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/f0_LEMD): bridge_deck:-6288 lateral -11.81..+2.29 m -> -10.23..+10.24 m against the Bridge2 pair's inner faces at +-10.185 m (worst |offset|-half 1.62 -> 0.06 m); every other LEMD deck ring BYTE-IDENTICAL.
LEMD  patch    base 9306c56d   lane v2othhdet        2026-09-15T13:10:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhdet/runs/lemd_lane/structures.json  [MISSING]  — v2othhdet LEMD dry --stage structures PAIR: lane arm (claude/v2othhdet 9306c56d) vs base arm scratchpad/v2othhdet/runs/lemd_base (git archive 118d2c40 in basesrc). corridors 1 / tunnels 51 / basins 1 / wall_corridors / plates / door_wells ALL byte-identical; the only difference is corridor_refused 209, the same SET now in sorted order.
LEMD  patch    base 1d6bc71a   lane v2channel        2026-09-15T13:27:32  /tmp/v2channel/r7/br_LEMD/structures.json  [MISSING]  — v2channel round-5/6 dry replay (branch): tunnels 52->52 IDENTICAL, basins 1->1 IDENTICAL vs /tmp/v2channel/r7/base_LEMD; channels 3 (channel:1/:2/:4, neck+clearance, 2 decks each); channel:5 refused — its 3 pack witnesses dsf:obj7/obj8/obj10 ARE built basin:0's members (LEMD36/37/85, floor 588.952), exactly §45 (13)(d).
LEMD  capture  base e856ce64   lane v2shoulderband   2026-09-15T13:25:05  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/sb/cap_off/LEMD.pkl  [MISSING]  — §40 (5) MATCHED PAIR, band OFF arm (--rule corridor.runway_shoulder_band=false, the §40 (1) law). v2_solve_replay --capture on claude/v2shoulderband, 236 s, 21,376 vertices / 1,059 faces, guard shared repo UNCHANGED. runway_shoulder 545,036 m2 in 17 cells, worst lateral 914.3 m; solve optimal 169.9 s; the 09y runway projection FAILS (Solve error rc kError); runway_step 3 rows at 40.4613609,-3.5446852 (0.950/0.633/0.317 m); census LAW-TRUE 6,807 ADJUDICATED 2,011.
LEMD  capture  base e856ce64   lane v2shoulderband   2026-09-15T13:25:05  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/sb/cap_on/LEMD.pkl  [MISSING]  — §40 (5) MATCHED PAIR, band ON arm (--rule corridor.runway_shoulder_band=true, the RULED law). Same tree, same airport, ONE variable, arm line printed per capture. 351 s, 21,883 vertices / 1,099 faces, guard UNCHANGED. runway_shoulder 271,086 m2 in 19 band pieces, worst lateral 75.5 m, remainder 273,949 m2 in 28 faces; solve optimal 70.9 s; runway projection 'held by the solve (nothing to settle)', worst hard row 2.3 mm; runway_step 0; census LAW-TRUE 6,185 ADJUDICATED 1,709.
LEMD  patch    base e856ce64   lane v2shoulderband   2026-09-15T13:25:05  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/sb/emit_off/LEMD_auto.patch.osm  [MISSING]  — §40 (5) band OFF arm EMIT (v2_solve_replay --replay --emit --verify off cap_off). The BASE of the matched pair.
LEMD  patch    base e856ce64   lane v2shoulderband   2026-09-15T13:25:05  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/sb/emit_on/LEMD_auto.patch.osm  [MISSING]  — §40 (5) band ON arm EMIT. ramp_in_strip 18 -> 9, strip_transverse 93 -> 34, transverse 92 -> 34, CRITICAL motion 12 -> 6, cliffs 20 -> 10; the ONE riser adjacent_ground_step 0 -> 2 (0.580 m).
LEMD  patch    base e856ce64   lane v2shoulderband   2026-09-15T13:25:05  /tmp/harness/v2shoulderband.osm  [MISSING]  — CLOSING LEMD AIRPORT-PATH build of claude/v2shoulderband a8138464 (build_airport.py LEMD --tag v2shoulderband, NO --tile per RULINGS 2026-09-15av): rc 0, 351.4 s, status optimal, ways 1123, nodes 21660, body_sha 42241995fdaf, artifact ledger 874c7aee6b0d, v2-verify 1797 rows with every DEFECT family ZERO (runway_transverse / runway_vertical_curve / runway_step), shared repo UNCHANGED (18 lock-churn ops, the allowed class).
LEMD  capture  base 7f80dc71   lane v2padclip        2026-09-16T09:49:15  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/cap/LEMD.off.pkl  [MISSING]  — LEMD PADS-OFF capture (the shipped law) on claude/v2padclip, 219 s, 21,841 vertices / 1,099 faces, guard shared repo UNCHANGED - BASE ARM of the v2padclip LEMD pair; census ADJUDICATED 2,121, law-true 6,479, pad_airside_weld 2. The owner's T4 garage 40.4892214,-3.5944287 is covered by NO ring group on this arm (15h's 'the pad polygon ends 55.28 m short').
LEMD  capture  base 7f80dc71   lane v2padclip        2026-09-16T09:49:15  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/cap/LEMD.on.pkl  [MISSING]  — LEMD PADS-ON capture (--placement pad_from_cluster=true pad_airside_clip=true), 216 s, 20,953 vertices / 1,042 faces, guard UNCHANGED. Under §16g (10) (12): re-node deleted 0 / minted 32 (the shipped-law arm reads 150). The owner's T4 garage is INSIDE building45, a 93-node face (way -10991) at 615.05..615.11 - ONE LEVEL, spread 0.06 m, no short-edge step. Census vs the OFF arm: ADJUDICATED 2,121 -> 1,004 (-53%), within_shape 4,253 -> 3,025, hairline_pair 1,642 -> 1,287; worse: pad_cluster_mismatch 0 -> 1, pad_airside_weld 2 -> 3.
LEMD  capture  base 782a50d6   lane v2padclip        2026-09-16T10:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/r2/cap/LEMD.lane2.pkl  [MISSING]  — r2 LEMD PADS-OFF (shipped law) capture with (12) (1) (c): 200 s, 20,403 vertices / 985 faces. Against main 1bc93833 (cap/LEMD.base.pkl) the shipped arm IMPROVES: ADJUDICATED 1,749 -> 986 (-44%), law-true 6,257 -> 4,850, frontage_near_miss 8 -> 0, pad_airside_weld 2 -> 1. apron faces 106 on BOTH pad arms (was 180 vs 106); OFF-arm renode_minted 150 -> 12.
LEMD  patch    base 8fe85a0f   lane v2stagepop       2026-09-16T11:42:11  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2stagepop/emit_lemd_on/LEMD_auto.patch.osm  [MISSING]  — §20b (3) r1 OWNER-SITE READ: LEMD staged (staged_solve=1) PADS-ON replay emit off the registered v2padclip r2 capture cap/LEMD.on2.pkl, on claude/v2stagepop 2b430ab4 (stage 1 triangulates only its own roles). The T4 garage 40.4892214,-3.5944287 is INSIDE building45, a 93-node face (way -10986) at 615.19..615.34 — ONE LEVEL, spread 0.15 m, z-DEM +4.26 m of fill, no step over a short edge (r2: 615.05..615.11, +4.06 m).
LEMD  patch    base 8fe85a0f   lane v2stagepop       2026-09-16T12:17:33  /tmp/harness/v2stagepopLEMD2.osm  [MISSING]  — §20b (3) AMENDED r2 CLOSING BUILD, the three keys ON (pad_from_cluster, pad_airside_clip, staged_solve): rc 0, 301.0 s, ways 1092, nodes 21336, status optimal, body_sha edeebd0de1ff, artifact ledger 39336a1007c1, v2-verify 1262 rows, 'shared repo UNCHANGED by this build (full-surface before/after snapshot)'. The owner's T4 garage 40.4892214,-3.5944287 is INSIDE building45 (93-node face, way -11001, 615.22..615.45 — ONE LEVEL, spread 0.23 m); census law-true 4,952 ADJUDICATED 1,316, cockpit CRITICAL motion 0.
LEMD  patch    base 31b7ad1b   lane v2wallface       2026-09-17T19:20:13  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/68719ad8-48b0-4348-b2fb-5068aec73ed8/scratchpad/wallface/out/base_LEMD/structures.json  — §47 dry pair BASE arm (git archive of main 31b7ad1b into scratchpad/wallface/base, worktree mounts symlinked; lane-local O4_DSF_CACHE_DIR/O4_AIRPORT_MOD_CACHE_DIR, shared repo never written). 193 s. tunnels 47, corridors 1, plates 3, basins 1.
LEMD  patch    base 31b7ad1b   lane v2wallface       2026-09-17T19:20:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/68719ad8-48b0-4348-b2fb-5068aec73ed8/scratchpad/wallface/out/lane_LEMD/structures.json  — §47 dry pair LANE arm (claude/v2wallface bcc3d0b1). 183 s. vs base_LEMD: tunnels 47->47 with ONE differing row (tunnel-object:Bridge4.obj@0 on rim_ll + trench_outside_max_m 0.139->0.000); all 46 OSM bores BYTE-IDENTICAL; corridors/door_wells/wall_corridors/sunken_roads/plates byte-identical; basin:0 rim on the outer face, area 27630->28052 m2.
LEMD  patch    base 31b7ad1b   lane v2wallface       2026-09-17T19:20:49  /tmp/harness/v2wallface/base_LEMD/structures.json  — DURABLE COPY of the §47 LEMD dry-pair BASE arm (git archive of main 31b7ad1b; lane-local caches, shared repo never written). 193 s. tunnels 47, corridors 1, plates 3, basins 1. Its LANE twin is $D/lane_LEMD; the arm runners dry.sh / mkbase.sh / seed_cache.sh and the F-measurement f_measure.py sit beside them.
LEMD  patch    base 31b7ad1b   lane v2wallface       2026-09-17T19:20:49  /tmp/harness/v2wallface/lane_LEMD/structures.json  — DURABLE COPY, §47 LEMD dry-pair LANE arm (claude/v2wallface). 183 s. tunnels 47->47, ONE differing row (tunnel-object:Bridge4.obj@0: rim_ll + trench_outside_max_m 0.139->0.000); all 46 OSM bores BYTE-IDENTICAL; corridors/door_wells/wall_corridors/sunken_roads/plates byte-identical; basin:0 area 27630->28052 m2.

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
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py tests/test_auto_patch_freshness.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

