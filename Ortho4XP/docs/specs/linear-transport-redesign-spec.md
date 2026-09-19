# Linear-transport redesign — roads, bridges, tunnels, airside connections
# (RULINGS 31a/31b mandate; consumer census: linear-transport-consumer-
# census.md, 118 rows — every interaction below is ruled against it.
# Author: Fable lead, 2026-08-31. ONE owner ratification covers this
# whole spec; per-batch sim checkpoints adjudicate, per 31a.)

## §1 The model

ONE law for a road's vertical profile everywhere: follow terrain;
where terrain exceeds `SERVICE_ROAD_MAX_GRADE` (8 %), LIFT or CUT the
minimum needed to hold the cap (the bounded-envelope clamp — census #5,
free_road_profile's envelope branch, which is KEPT as the algorithm);
laterally level (no banking). Pins exist ONLY at airside pavement
contact (29c contact-is-value) and at bridge decks (30c §5,
re-expressed below). OWNERSHIP: the core's `include_roads` owns
general roads; auto_patch owns (a) contact transitions, (b) bridges,
(c) tunnels as mouths/ramps/retaining walls. The `tunnel_road` claim
class (R14-1) and the chord/self-pin profile model retire.

## §2 Core roads (census §5)

1. LONGITUDINAL CLAMP, per-way on centerlines (census #111 option i —
   NEVER on the merged buffered ring): for each way in
   `road_network_banked`, sample the shifted-DEM profile at ≤20 m
   stations, run the envelope clamp (lift-or-cut, cap-Lipschitz —
   the same algorithm as free_road_profile's envelope branch, ported),
   and store per-way clamped stations. `alt_vec_shift` answers from
   the nearest clamped station within lane_width×2 (cKDTree), falling
   back to shifted DEM beyond. Grade constant: new cfg var
   `road_grade_limit` (O4_Cfg_Vars beside `road_banking_limit`,
   census #116), default = `auto_patch.config.SERVICE_ROAD_MAX_GRADE`
   (one constant, import direction already exists — census #115).
   REFINED 2026-09-18n — see §2-SUPPLEMENT at the end of this file: the
   clamp runs only in the PATCH NEIGHBOURHOOD, at per-class caps that
   yield to a 1 m deviation budget; elsewhere roads are upstream's.
2. PATCH-AREA MAX DETAIL UNCONDITIONAL (owner 2026-08-31): the
   airport-inset level-5 + rail leveling runs whenever auto_patch
   runs, regardless of a numeric user `road_level`; the user knob
   governs tile-wide only.
3. FIX the key-presence exclusion (census #106): exclude a way only
   when `bridge`/`tunnel` has a truthy value (not `no`), so
   `bridge=no` ways level normally. The exclusion set is the seam
   with auto_patch's (b)/(c): approaches level with the core, the
   tagged span belongs to auto_patch.
4. MEASURABILITY (census #91, the blindness the post-mortem names):
   the clamp pass WRITES a levelled-roads sidecar
   (`<tile>/o4_levelled_roads.json`: per-way station lat/lon +
   clamped alt + DEM alt) beside the tile. `tools/
   road_terrain_conformance.py` gains `--levelled-roads` to price
   core-owned roads from it; census/check_grade stay patch-only
   (their law populations shrink per census #83-90, accepted).
   Granularity: clamp stations ≤20 m so the instrument outresolves
   emit_decimate's 60 m (census #112).

## §3 auto_patch roads — the contact model (census §1, §4)

1. RETIRE: both `solve_free_road_profiles` call sites, the chord
   branch, self-pins, `cap_distance_prefix` (if unused after the
   port), PROFILE_KEYS/binding-refusal registers, O4_FRP_* flags
   (census #1-4, #6-7, #10-12).
2. KEEP AND REWIRE into the transition profiler: LAW 1 freeze-weld
   (#8), LAW 2 end-on binding (#9), `_road_vertex_graph` (#13),
   `_airside_value_at` (#14), `adopt_road_airside_crossing_values`
   (#61), the envelope clamp (#5). A transition chain runs from the
   airside contact pin outward at most `SERVICE_ROAD_PAVEMENT_NEAR_M`
   (25 m; seam-probe 5 measures whether that set IS the contact set)
   and its OUTER END takes the value of the SAME shared clamp
   function the core uses (one function ⇒ the handoff welds by
   construction).
3. OWNERSHIP SHRINK: `build_service_road_network` mints only contact
   stubs (within the transition scope of airside pavement or a
   bridge/tunnel feature); general road courses stop emitting as
   patch pavement (#53). `SERVICE_ROAD_CARVE` (#54) keeps — airside
   by construction. The ~15 spec-must-rule writers in census §4a rule
   as: passes that exist to manage road-vs-lot ownership at scale
   (#68 route corridors, #96 lot sever, #97 road_zone sever, #98
   road-only lots, #99 absorption, #101 full-width merge) go DORMANT
   with their domain (retire only after a full-battery zero-fire
   measurement, 29f); value-writers that remain in the contact scope
   (#56 dem_follow, #57 reach, #59 lateral contiguity + cap vector,
   #60/#63 seats, #64 chord limiter, #66/#67) KEEP, now operating on
   the small contact population. `svc_free_ends` (#17/#58): a
   transition's outer end is no longer "free" — the free-end DEM tie
   retires with general roads; corridor_axis_coverage's --free-ends
   mode re-reads from the levelled-roads sidecar.
4. CENSUS MIGRATION GUARD MIRROR (#90): add the outbound twin — the
   road-family population leaving the patch is DECLARED (a
   `road_ownership` sidecar count), so census shrinkage is provably
   the shrink, not a silent drop.
5. CONVERGENCE-POINT DISCIPLINE (census §4a SUPPLEMENT): the road
   family has ~40 altitude writers in 19 modules, converging at TWO
   points — the solver writeback (`solver_primitives._writeback`,
   both call sites) and `to_osm`'s authority resolution. The shrink
   is a POPULATION change (general road shapes stop existing in the
   patch), not 40 code edits: writers act on whatever road shapes
   remain, which is the contact set. Batch 2 verifies by seam-probe
   (`who_wrote.py --at`) at one airport, not by editing writers. The
   `_cut_back_road_frontage` gate conflict (census supplement) is
   seam-probed in Batch 2 before any assumption. The mint has NO
   pre-solve value authority (census correction) — the transition
   profiler is therefore installed at the writeback/`reseat_service_
   mouths` seam, the census-named "natural home" of the pinned-
   transition law.

## §4 Bridges (census #75, #44; 30c/30d/30f re-expressed)

Detection (`road_bridge_deck` §1/§2) KEEPS: bridge-tagged feed way ×
emitted below-grade structure = terrain deck; object-governed spans
keep the object law. The deck is core-owned road ground WITH a pin:
30c §5's "pin in the free-road profile solve" re-expresses as a pin
in the CORE clamp (a clamped-station override at deck stations: deck
level = max(clamped value, structure-beneath + 5.1 m... per 30d the
structure holds bore datum so this is the road solve's own level —
the pin's function is §6 refusal detection and the approach grade
check, both priced in the clamp pass). Cuts on either side hold
`BRIDGE_ROAD_CLEARANCE_M` (5.1) under the span (30d full-depth
geometry unchanged). OSM-level classifier: shared node ⇒ same level;
crossing without shared node orders by layer/bridge/tunnel — built
on the existing G-TUNNEL-ROAD tag machinery (#42), which KEEPS.

## §5 Tunnels — mouths, ramps, retaining walls (census §2, §3)

1. RETIRE: `TUNNEL_ROAD_REF` and its minters (#22-26), the stand-down
   (#31), claim audits (#32), claim publisher + `tunnel_open_cut_
   claim_polys` (#48), the 30i clip membership (#30), solver claim
   pins (#37), claim env flags. RULINGS superseded: R14-1, 25e-claim
   lineage, 30i — named in the ratification.
2. REWIRE BY ROLE/GEOMETRY, not ref: walls key on ramp/mouth geometry
   (#27, #28); `claimed_tunnel_corridor` readers become tunnel_ramp
   checks (#33, #34); BELOW_GRADE_REFS drops "tunnel_road" (#35);
   node-book exclusion re-keys to `tunnel_open_cut_polys` (#51 —
   seam-probe 4 verifies ring coverage BEFORE the closing build);
   region publication re-homes out of the claim pass (#47, #49);
   claim-edge seniority reads the cut half only (#50).
3. The canonical mouth (30 ruling) stands: one ramp to the mouth
   line, one wall band per side, one end cap. Where mapped road
   pavement lies over the cut, it is now CORE road ground above a
   covered stretch (the deck model, §4) or severed by the open cut —
   never re-profiled in place.
4. `tunnel_portal_acceptance` re-keys its bore-cover check to
   ramp/mouth geometry (#40) — updated in the SAME batch so the OTHH
   battery cannot silently SKIP.

## §6 Implementation batches (sim-checkpoint gate: ONE batch between
## owner sim reads; each batch ONE lane, ONE closing build)

- Batch 0 (enabler, no geometry change): merge lane/phase0roads
  (instrument + off-arms); this spec + census ratified.
- Batch 1 — CORE: §2 items 1-4 (clamp, sidecar, unconditional patch-
  area leveling, exclusion fix, instrument extension). Closing:
  one tile build (LEMD), conformance read on the sidecar. auto_patch
  untouched.
- Batch 2 — ROADS: §3 (FRP retirement, contact model, ownership
  shrink, guard mirror). Closing: HECA + the SPJC owner site
  (follow_ratio at way 702's chain ≥0.95, no cutting >2 m) + the
  HECA missing-road site (owner 31c): the road between
  30.1123618,31.4059543 and 30.1118258,31.4065064 EMITS (its OSM
  service way exists; ruled needed for a smooth transition) — under
  the new ownership it is either a core-levelled road reaching the
  patch or a contact transition; the seam ruling decides, the site
  closes either way.
- Batch 3 — TUNNELS+BRIDGES: §4+§5. Closing: OTHH (three canonical
  mouths, wall count per side = 1) + LEMD (bridge span per 30d/30n).
- Batch 4 — CLEANUP: retired tests rewritten/deleted (census test
  list), env flags removed, dormant passes measured zero-fire then
  deleted, RULINGS supersessions recorded, PERF re-measured against
  tools/build_time_baselines.json (the 31a anchor) — the retirements
  should claw back part of the 5-6x accretion; quote the delta.

## §7 Emitability + heightfield check (30l requirement)

Everything here emits in a heightfield: core roads are INTERP_ALT
ring altitudes (existing machinery); transitions are patch pavement;
decks are terrain at road level over severed cuts (30d, proven at
LEMD); tunnels are open cuts + walls (pre-claim model, proven).
No floating geometry anywhere in the model.

## Acceptance (whole redesign)

Owner sites: SPJC 702 terrain-following ≤8 %; LEMD 40.4834432,
-3.5805328 bridge per policy; OTHH mouths canonical. Census not
worsened beyond the DECLARED ownership migration; conformance
instrument green on both patch and levelled-roads populations;
basin/ramp invariants held; perf delta vs committed baselines quoted.
Below-bar = STOP with residual. Sim read between every batch.

## §5-SUPPLEMENT (Batch 3b, spec author 2026-08-31 — closes the two
## gaps Batch 3's measurement exposed; census #31 is REFUTED as scoped)

1. ONE RAMP SURFACE PER CORRIDOR, AT THE SOURCE. The retired
   stand-down was doing double duty as the SYNTHETIC ramp
   de-duplicator (measured: ramps 22 → 95 without it). The law
   "one ramp surface descending the corridor centre" is enforced AT
   THE EMITTER: consecutive ramp strips along one corridor chain
   merge into ONE surface per descending run before emission — never
   a post-pass re-creating the stand-down.
2. WALLS FOLLOW THEIR RAMP, PRODUCTIVELY. Census #27/#28 said REWIRE
   and the lane retired instead (owned deviation): the claim-waller's
   population (17/39 walls, 20/48 feet at the OTHH control) must be
   REPLACED, not deleted — every merged ramp corridor side gets
   exactly one wall band derived from the ramp's own geometry through
   the existing wall-band machinery. The canonical-mouth bar (one
   wall band per side) is the acceptance.
3. NODE-BOOK EXCLUSION SCOPE. The seam-probe-4 area clause fires
   wherever a cut is published (LEMD: 467 airside nodes moved with a
   byte-identical tunnel population). Membership narrows to:
   BELOW-GRADE ROLE (tunnel_ramp / tunnel_trench / basin families)
   AND (node-in-cut OR area-in-cut ≥ 2 m²) — the exclusion's purpose
   is bore-depth values not travelling outward, which roles capture
   without geometric spillover onto at-grade ground. The off-arm in
   flight adjudicates the clause attribution first.

## §5-SUPPLEMENT-2 (Batch 3f, spec author 2026-08-31 — fork walls)

A TRUE fork (31h divergence test: separation growth > TUNNEL_FORK_MIN
_GROWTH_M) is walled PER ARM: downstream of the divergence point each
arm is its own corridor for the wall machinery — the existing band
emitter runs on the arm's own body, yielding inner AND outer faces
per arm naturally (no special inner-face path). Where the two arms'
INNER bands overlap near the throat (the V's pinch, the 31g class),
they collapse to ONE SHARED wall along the bisector — a shared
structure is the physical answer in a gap narrower than two bands.
The throat plate caps the V as today. Acceptance: the confirmed fork
at 25.2537652,51.6032373 reads wall/foot ≥0.9 per side on BOTH arms'
inner and outer faces (or the shared-bisector wall where pinched);
no band collisions; the canonical bar per mouth site becomes, for a
fork site: one ramp per arm + per-arm walls with the shared-pinch
rule + one throat cap.
Also Batch 3f: ATTRIBUTE the 21% foot shortfall at the merged site
25.2761183,51.6134359 (154.0/193.8 m², gap not wall-occupied) before
fixing — measured mechanism, then the fix, per standing law.

## §2-SUPPLEMENT (owner RULINGS 2026-09-18n; Fable 2026-09-18) — THE CLAMP
## IS SCOPED TO THE PATCH NEIGHBOURHOOD, ITS CAP IS THE ROAD'S CLASS, AND
## THE CAP YIELDS TO A DEVIATION BUDGET — lane `roadclampscope`

REFINES §2 item 1 and RULINGS 2026-08-31b / 2026-09-13be (ii)(iii). Founded on
`docs/findings/roads-off-patch-20260918.md` (measured; not re-derived). Every
number below marked TFFJ is an offline re-run on the shipped sidecar
(`zOrtho4XP_+17-063/o4_levelled_roads.json`, app 1.0.351) against the union
of the closed rings of the corpus `TFFJ_auto.patch.osm`; way classes joined
from the tile's `airport_small_roads` / `big_roads` caches (4,429 / 4,429
matched by end nodes).

Owner, verbatim: "how would we by applying any road grade clamping outside
the airport patch? Shouldn't that be handled by the normal engine road
processing and we only deal with stuff in the patch area?" … caps "must find
plausible real world specs, it can't be steeper than the intended vehicle
traffic can actually handle."

### S.0 A PREMISE OF THE FINDINGS, CORRECTED (verified in git)

`road_is_too_much_banked` (`O4_Vector_Map.py:2024-2043`) is UPSTREAM'S
FUNCTION, BYTE FOR BYTE — the earliest tree in history (`38b3eaf5`, which
pre-dates `e80ebd97`) carries the identical body, including the two
`apt_array` clauses, and `alt_vec_shift` there is the bare shifted DEM.
`apt_array` (`O4_Airport_Utils.py:911`) is upstream's too: each airport's
boundary BBOX grown 1,500 m, on a 1001² grid — NOT the 2 km inset box. So
"the unconditional admission" the findings name is upstream's admission to
LATERAL levelling (it bypasses the 0.5 m banking threshold and
`max_levelled_segs`; it cannot move a centreline off the DEM). What
`e80ebd97` added is that EVERY admitted way — tile-wide, 4,429 at TFFJ —
enters the LONGITUDINAL clamp. The inset box is the FEED (S.4 row 7), not
the admission. 18n is therefore implemented as: **admission to lateral
levelling = upstream, unchanged; admission to the CLAMP = the patch
neighbourhood, decided by geometry at one site.** (Owner Q2 confirms.)

### S.1 THE NEIGHBOURHOOD — ONE DERIVATION SITE

Site: `O4_Vector_Utils.clamp_road_network` (it gains `coverage=` and
`way_classes=`). Nothing else decides who is clamped.

(1) **THE BAND.** `band = improved_buffer(patches_area ∪ deck polygons,
lane_width + 2)` — `patches_area` (`O4_Vector_Map.py:1236`, the union of
every closed patch ring, 13be) NOT `apt_area`/`treated_area` (which also
carries apt.dat pavement of airports no patch was built for — those get
upstream processing only), and NOT a bbox. It is the same `lane_width + 2`
offset the ribbon is already differenced by at `:2224`, so "in the band" =
"where the core has no ribbon and the patch is the authority" (13be (i)).
The road bridge decks of `road_bridge_deck_pins` join the band: a deck is
auto_patch's object wherever it stands (31b (b)). `include_roads` receives
`patches_area` as a new fifth positional-or-keyword argument from `:1265`
(it is already in scope at `:1236`); when no patch was built the band is
empty and NO way is clamped (pure upstream + nothing).

(2) **OURS.** A way is OURS iff at least one of its stations lies in the
band. (TFFJ: 40 ways / 586 stations of 4,429 / 60,594 — service 29,
unclassified 5, secondary 3, residential 3.) Purpose, not proximity: only
a way that enters the band has a JOIN (13be (iii)); a way 10 m beside the
patch that never enters it has no contract with the patch and is terrain.
An OSM way split just outside the band hands over to an un-clamped way at
a station where (3)'s pin has already returned the profile to the DEM — so
way identity never creates a step.

(3) **THE RUN AND ITS RULE.** For an OURS way, the RUN is every station
within `runout_m = 100 m` of ARCLENGTH ALONG THE WAY from its nearest
in-band station (in-band stations included); maximal contiguous runs are
solved independently. Over a run the profile is the existing mid-envelope
clamp under a PER-SEGMENT cap, PINNED TO THE DEM at each run extremity that
is outside the band (the run-out end, or the way's own end if it comes
first) — `cap_lipschitz_pin_envelope`'s existing corridor, so the run
re-meets terrain EXACTLY, by construction, not "within ε". Stations outside
every run: `alt = dem`, identically, and they are NOT in the answering
KD-tree — `alt_vec_shift` falls through to the shifted DEM there, which is
upstream's `alt_vec_shift` verbatim. Why 100 m and not longer: with S.3's
budget the deviation is ≤ 1 m, which dissipates inside 17 m even at 6 %;
100 m (≥ 5 stations) is the length over which a DEM/lidar bump at the mouth
is smoothed, and TFFJ is insensitive to it (R 100 → 250: displaced
stations 7 → 12, max unchanged at the budget). Why not zero: a zero
run-out pins the FIRST outside station to raw DEM, and v2's join (13be
(iii)) would then inherit one raster cell's noise as an equality.

(4) **THE PER-SEGMENT CAP.** `cap_lipschitz_profile` /
`cap_lipschitz_pin_envelope` accept `cap` as a scalar (today's behaviour,
bit-identical — `road_transition.py:392` and every existing twin keep
passing) OR a per-SEGMENT array (length n−1); internally `cs = cap·s`
becomes `K = concat(0, cumsum(cap_seg · ds))`. The four sweeps are
unchanged; the result is Lipschitz in the weighted metric, i.e. each
segment holds ITS cap. Segment caps: both ends in the band →
`road_grade_limit` (the patch's cap, 8 % — v2's `service_road` law,
untouched; this is what the cfg knob now MEANS); otherwise the way's class
cap (S.3), after the yield.

(5) **EVERYTHING ELSE** — `road_is_too_much_banked`, the three layer
passes, `improved_buffer`, the `apt_area` difference, `encode_MultiPolygon
(…, "INTERP_ALT", refine=100)`: UNCHANGED. Outside the neighbourhood the
road pipeline is upstream's, value for value.

### S.2 THE JOINS

(a) **Clamped run ↔ unclamped continuation of the same way:** equality at
the pin (step 0.000 by construction); inside the run every segment is
≤ its cap; beyond it the grade is the terrain's, as upstream draws it. "No
kink beyond the class cap" is met on the clamped side; the terrain side is
not ours to cap (18n). Twin: S.6 T3.

(b) **Core ribbon ↔ patch (13be (ii)/(iii)) — v2 MUST CALL THE SAME
FUNCTION.** v2's `airport/road_profile.clamp_way` replaces
`clamp_profile(s, dem, cap)` with the shared
`VECT.neighbourhood_road_profile` (S.5) for `OSM`-kind ways, passing
`in_band` from `emit.bank.coverage_polygon(pm)` buffered by
`lane_width + 2`, the way's class from `w.tags`, and `cap_inside = cap_`.
`ROUTE` and `AXIS` ways lie wholly in the coverage → all segments
`cap_inside` → numerically today's values. Without this the patch would
still clamp a way that climbs a 20 % hillside out of the airport over its
WHOLE length at 8 % and carry the 5–30 m cut/fill INTO the coverage while
the ribbon outside sits on terrain — the defect re-created at the patch
edge. 13be (ii)'s "ramp floor = the core's clamped profile" and (iii)'s
equality are unchanged IN WORDS; the profile they name is now this one.

(c) **The join value is read AT THE CROSSING, not at the first outside
station.** `emit/road_join.py:80` takes `w.z[first_out]` — up to one 20 m
station from the edge; at 8 % that hid ≤ 1.6 m, at a 20 % class cap it is
≤ 4 m. It becomes the linear interpolation of `w.z` at the arclength where
the way crosses the coverage boundary. Same for the core's answer:
`Levelled_Roads.answer` interpolates between the two stations bracketing
the query's projection on the nearest station's way, instead of returning
the nearest station's value (the tree now holds ~600 stations at TFFJ, not
60,594 — the cost falls).

(d) **The missing road↔terrain LATERAL feather (findings item 4): OUT OF
SCOPE, with numbers.** Under S.1–S.3 the largest road-vs-terrain offset
anywhere on the TFFJ tile is the budget, 1.00 m, at 7 stations (shipped:
45.44 m, 19,531 stations). The two worst near-patch ways:

| sidecar way | class | length | terrain grade med / p90 / max | shipped max offset (st > 0.5 m) | this spec, outside the band |
|---|---|---|---|---|---|
| 9 | secondary (through the patch, 32 of 47 st in band) | 587 m | 3.7 / 15.3 / 19.9 % | 5.43 m (33) | 1.00 m (4), cap yields 12 → 16.2 % |
| 782 | service | 207 m | 4.6 / 34.8 / 34.9 % | 6.13 m (17) | 0.55 m (1), no yield |
| 1054 | service | 72 m | 11.9 / 28.1 / 30.1 % | 3.65 m (6) | 1.00 m (2), yields 20 → 25.3 % |
| 435 (owner site) | residential | 652 m | 15.2 / 31.0 / 57.6 % | 33.86 m (59) | 0.00 — not OURS, terrain |

A ≤ 1 m kerb offset over an 8 m ribbon is inside what upstream's own
lateral levelling already produces on a 25 % cross-slope (4 m × 0.25 =
1.0 m). A feather is a new region with its own consumer census; it is not
opened here. If the owner's read of the mouth still shows a wall, the lever
is `budget_m`, not a feather.

### S.3 PER-CLASS CAPS — SOURCED — AND THE YIELD

Principle for choosing among sources: the cap is the steepest grade a
PUBLISHED DESIGN STANDARD permits for that class in MOUNTAINOUS terrain at
low design speed — i.e. the steepest the class's intended traffic is
designed to handle. Flat-terrain "desirable" values are not caps (a road
that exists on a hill was not built to them); vehicle gradeability is the
sanity ceiling, not the cap. Where standards disagree the table takes the
value a second standard corroborates, not the single steepest outlier.

| OSM tag | cap | sources | why |
|---|---|---|---|
| `highway=motorway` | 6 % | AASHTO Green Book freeways, mountainous 5–6 % [KYTC]; DMRB CD 109 Table 5.1 motorway 3 % desirable / 4 % relaxation [CD109]; RAL EKL 1 4.5 % [RAL] | AASHTO mountainous is the permissive end; nothing published exceeds it |
| `highway=motorway_link`, `trunk_link` | 8 % | AASHTO ramp grades to 8 % at low ramp speeds (Green Book ch. 10, from memory — not re-fetched); DMRB all-purpose relaxation 8 % [CD109] | ramps run steeper than mainline |
| `highway=trunk` | 8 % | DMRB all-purpose dual 4 % / relaxation 8 % [CD109]; RAL EKL 4 max 8.0 % [RAL]; AASHTO rural arterial mountainous up to 8 % at 40 mph [KYTC range 5–10 %] | three standards meet at 8 % |
| `highway=primary`, `primary_link` | 10 % | AASHTO arterials mountainous 5–10 % [KYTC]; TxDOT urban arterial rolling 8–9 % at 15–30 mph [TxDOT] | top of the arterial range |
| `highway=secondary`, `secondary_link` | 12 % | AASHTO collectors mountainous 8–12 % [KYTC]; TxDOT urban collector rolling 12 % [TxDOT]; Queensland RPDM 10–12 % at 40 km/h mountainous [search excerpt] | top of the collector range, corroborated |
| `highway=tertiary`, `tertiary_link` | 12 % | same collector rows | a minor collector is still a collector; 14 % (AASHTO urban collector, 20 mph, from memory) uncorroborated → not used |
| `highway=unclassified`, `residential`, `living_street`, `road` | 15 % | AASHTO local residential streets "15 percent maximum" [CED]; Vancouver (WA) VMC local service streets 15 % [search excerpt]; AASHTO local roads mountainous 10–17 % [KYTC] | 15 % is stated by two sources; 17 % only at 15 mph |
| `highway=service` (groundside: driveways, parking aisles, alleys) | 20 % | San Bernardino County Fire driveway ≤ 20 %; San Miguel Fire access road ≤ 20 % with concrete above 15 % [search excerpts]; IFC D103.2 10 % without approval [IFC]; 2WD cars start on ~16 %, hold ~20 % moving [search excerpt] | the steepest published limit for a vehicle access way, and the 2WD limit |
| `highway=track` | 18 % | USFS FSH 7709.56 ch. 40: 12 % passenger cars, 18 % high-clearance / 4WD [FSH] | a track's intended traffic IS high-clearance |
| `railway=rail`, `narrow_gauge`, `siding`, `spur`, `yard` | 4 % | adhesion mainline practice; Saluda Grade 4.7 % was the steepest US mainline (Wikipedia, title seen, not fetched) | LOW-CONFIDENCE ROW — one weak source; rail was 8 % until now, so 4 % only tightens inside a ≤ 100 m run under a 1 m budget |
| `railway=tram`, `light_rail` | 8 % | unchanged from today (no source sought) | unchanged |
| any other / untagged | `road_grade_limit` (8 %) | — | today's behaviour; loud count in the report line |
| INSIDE the band, every class | `road_grade_limit` (8 %) | v2 law `common.roles.service_road.longitudinal` | the patch's law — UNTOUCHED (brief) |

Gradeability check on the ceiling: transit buses are tested to hold
≥ 10 mph on a 10 % grade with a parking brake holding 20 % (49 CFR 665 bus
testing [search excerpt]); loaded log trucks stall around 10 % from rest
without traction aids. So nothing above `cap_ceiling = 30 %` is a road any
class drives; it bounds the yield below.

Sources: [KYTC] kp.uky.edu/knowledge-portal/articles/roadway-grade/ (KYTC
HDGM Table 2 after AASHTO Green Book) · [TxDOT] txdot.gov Roadway Design
Manual §4.8.1 Table 4-11 · [CD109] DMRB CD 109 Table 5.1
(standardsforhighways.co.uk; Leicestershire TG4 summary) · [RAL]
bauformeln.de/strassenbau/grenz-und-richtwerte/landstrassen (RAL 2012 Tab.
14: EKL 1–4 = 4.5 / 5.5 / 6.5 / 8.0 %) · [CED] cedengineering.com C06-017
(Green Book local streets) · [FSH] fs.usda.gov FSH 7709.56 ch. 40 · [IFC]
codes.iccsafe.org IFC 2021 Appendix D. NOT OBTAINED (searched, tables not
reachable): Swiss VSS 40 110, Austroads AGRD Part 3 Table 8.3 verbatim,
RASt 06. None would raise a row above its present value.

**THE YIELD (the §50 analogue: "the cap yields, uniformly").** Real terrain
under a real road may exceed the class cap inside the neighbourhood (St
Barth's public roads run 15–25 %; way 1054 reaches 30 %). Then the road is
NOT driven off the terrain to hold the cap. For each run:

    dev(c)  = max over the run's OUT-OF-BAND, UNPINNED stations of |profile_c − dem|
    cap_eff = the smallest c in [cap_class, cap_ceiling] with dev(c) ≤ budget_m

found by bisection (24 halvings; `dev` is non-increasing in `c`). ONE
uniform `cap_eff` per run replaces `cap_class` on its out-of-band segments —
never a per-station exception. In-band segments keep `road_grade_limit`
always (inside the patch the cap is law and v2 owns the earthwork). If
`dev(cap_ceiling) > budget_m` — only possible when in-band 8 % segments push
the mouth off terrain — the run ships at `cap_ceiling` and is named in the
report. `budget_m = 1.0` (S.2 (d)'s numbers; = upstream's own lateral
offset on a 25 % cross-slope; 2× `visual_m`). Deck pins are equalities and
outrank the budget (§6's refusal unchanged). ONE LOUD LINE per build, no
gate, no verify family (§50's choice): `N ways in the patch neighbourhood,
M runs, Y yielded (worst cap_eff P % on way W, class C), Z at the ceiling,
max offset D m`; the same per-way in the sidecar.

18n does not state the budget's VALUE (the owner redirected the budget
question to scope; inside the neighbourhood the class still occurs: way 9
would stand 4.34 m off terrain at its 12 % class cap). → Owner Q1; the lane
ships 1.0 m.

### S.4 CONSUMER CENSUS (RULINGS 2026-08-30l) — every row ruled

| # | consumer (file:line) | reads | ruling |
|---|---|---|---|
| 1 | `clamp_road_network` `O4_Vector_Utils.py:1942` | every banked way | THE DERIVATION SITE. Gains `coverage` (band polygon, tile frame, or None) and `way_classes` (parallel to geoms, or None → default cap). bbox-prefilters ways against the band; OURS → `neighbourhood_road_profile`; others → `add_way(stations, dem, dem, s)` with `scope="terrain"` |
| 2 | `cap_lipschitz_profile` `:1664`, `cap_lipschitz_pin_envelope` `:1620` | scalar cap | EXTENDED: `cap` scalar OR per-segment array (S.1 (4)). Scalar path bit-identical (twin T1). Callers `road_transition.py:392`, `road_profile.py:233`, tools: untouched |
| 3 | `Levelled_Roads.answer` `:1843` / `alt_vec_shift` `O4_Vector_Map.py:2050` | KD-tree of all stations | tree holds RUN stations only; answer interpolates (S.2 (c)); miss → shifted DEM = upstream. `alt_vec_shift` body unchanged |
| 4 | `road_is_too_much_banked` `O4_Vector_Map.py:2024` | `apt_array` | UNCHANGED — upstream verbatim (S.0). Owner Q2 |
| 5 | `OSM_to_MultiLineString` `O4_OSM_Utils.py:1255` | drops way id/tags | gains `accepted_ids=None`: a list appended with `wayid` immediately after each successful `multiline.append`. `include_roads` maps ids → `layer.dicosmtags["w"][id]` (`highway` else `railway:`-prefixed) for each of the three layers, concatenated in the geoms' order; a length mismatch → all-default caps + a WARNING (never a crash). `filter`'s upstream signature untouched |
| 6 | `apt_area` difference `:2223` | `treated_area + lane_width + 2` | UNCHANGED. The band uses the same offset on `patches_area`, so in-band ⊂ removed ribbon |
| 7 | `_airport_auto_roads_layer_at` `:744` (feed box = inset boxes) → cache `airport_small_roads` | — | THE FEED DOES NOT SHRINK. Its other readers need the whole box: v2 `airport/osm.load_feed` (3×3, `ROAD_FEEDS`), the 15ar structure/bore readers, `ensure_auto_patch_road_feeds` / `_v2_road_feed_paths` `:868`, harness `superseded_road_feeds`. It is a shared-corpus artefact (a change is a locked `--refresh-data` event) and `ROAD_CACHE_TAG_SCHEMA` does not move (`highway`/`railway` are already kept as query tags — verified, 4,429/4,429 classed). What the box still does island-wide is upstream LATERAL levelling of level-5 ways under the 2026-07-27 auto-mode ruling → Owner Q3 |
| 8 | `o4_levelled_roads.json` writer `:1884`, `write_levelled_roads_sidecar` | — | `version: 2`. Still lists EVERY levelled way (row 9 needs them). Top level adds `runout_m`, `budget_m`, `cap_inside`, `cap_ceiling`, `class_caps`; `grade_cap` stays (= `cap_inside`). Per way adds `layer_way_id`, `class`, `scope` (`neighbourhood`/`terrain`), `cap_class`, `runs: [{i0, i1, cap_eff, yielded, at_ceiling, max_offset_m}]`. `summary` adds `neighbourhood_ways`, `runs`, `yielded_runs`, `ceiling_runs` |
| 9 | `bank_pavement_lines` `O4_Mesh_Utils.py:1282` | sidecar `lat`/`lon`/`lane_width_m` | UNAFFECTED (geometry only) — the reason row 8 keeps terrain-scope ways |
| 10 | `tools/road_terrain_conformance.py:532 read_levelled_roads` | `grade_cap`, per-way arrays | reads v2 sidecar: prices each run against ITS `cap_eff`/in-band cap; `scope=terrain` ways are counted and NOT priced (no law applies); v1 sidecars read as today. INDEX row updated same commit |
| 11 | v2 `core_profiles` / `clamp_way` `airport/road_profile.py:454/:240` | whole OSM way at `cap_` | S.2 (b): OSM-kind ways call the shared function. `preferred_road_z`, `road_ramp` (`:424`, `:555`), `v2_solve_replay.py:1585` read the result through `RoadProfiles` — no edit |
| 12 | v2 `road_coverage_joins` `emit/road_join.py:80`; family `road_coverage_join`; `constraints/road_ramp.road_join_rows` | `w.z[first_out]` | S.2 (c): crossing-interpolated value. Family definition, bar (≤ 0.05 m) and rows unchanged. 13cp's owed item (`road_join.py:87` station match never fires at LEMD) is NOT taken here |
| 13 | `road_bridge_deck_pins` `:1928` → `deck_pins` | sidecar decks | decks join the band (S.1 (1)); pins act only inside runs — a deck is in the band so its stations always are. §6 refusal + report unchanged; pins outrank the budget |
| 14 | 13cp Dirichlet `O4_Mesh_Utils.py:2381` + `interp_alt_ribbon_vertex_indices :1413` | ribbon authored z | UNCHANGED and now benign: it renders whatever the ribbon carries, which outside the neighbourhood is the DEM |
| 15 | `road_grade_limit` `O4_Cfg_Vars.py:403`, list `:806`; Qt + Swift rows; `o4_schema_snapshot.json:928/:1367` | — | KEPT, same name/type/default; MEANING narrows to "cap inside the patch band + default for unclassed ways". HINT rewritten (Fable copy, S.5) → snapshot regenerated (`tests/test_schema_snapshot.py`); no new cfg var, no Swift code change, no wire change |
| 16 | law table | — | `auto_patch_v2/law/emit.toml [road_profile]` gains `runout_m`, `budget_m`, `cap_ceiling` and `[road_profile.class_caps]`; `law/model.py:574 RoadProfile` gains the fields; the core reads them through ONE new reader beside `_road_grade_cap_from_law` (`O4_Cfg_Vars.py:23`). One definition, both engines |
| 17 | freshness stamps `driver.py:223`, `provenance.py:691 config_digest` | — | PATCHES RESTALE EXACTLY ONCE, through `o4_engine` (the engine version moves with the app build that ships this) — no `FRESHNESS_SCHEMA_VERSION` bump, no digest edit. Pre-existing gap, REPORTED not fixed: `road_grade_limit` / `lane_width` reach v2 (`driver.py:1536`) but are in no stamp |
| 18 | `driver.py:1536` → `engine_v2.py:323` → `load.py:98` | knob plumb | unchanged |
| 19 | `road_transition.py:285-392` (v1 remnant) | scalar clamp | unchanged (row 2) |

### S.5 FROZEN INTERFACE (the implementer does not alter it)

    O4_Vector_Utils.neighbourhood_road_profile(
        stations_s, values, in_band, cap_class, *, cap_inside, runout_m,
        budget_m, cap_ceiling, pin_idx=None, pin_val=None
    ) -> (altitudes, report)
    # report = {"scope": "neighbourhood"|"terrain",
    #           "runs": [{"i0","i1","cap_eff","yielded","at_ceiling","max_offset_m"}],
    #           + the existing deck-pin keys when pins were offered}

Pure numpy, geometry-free (the caller supplies `in_band`), no shapely, no
law import — so v2 and a twin can call it directly. `in_band` all-False →
`(values.copy(), scope="terrain")`.

`road_grade_limit` hint (final copy): "Longitudinal grade cap, as a
fraction (0.08 = 8 %), for roads INSIDE an auto-patched airport's patch
area, where the airport builder grades them. Outside the patch area roads
follow the terrain exactly as the base engine levels them; within about
100 m of the patch a road is eased onto the patch using a grade limit for
its road class (motorway 6 % … service road 20 %) and is never moved more
than about 1 m off the terrain to do it."

### S.6 EXPECTED EFFECT, EMITTABILITY, COST, TESTS

TFFJ tile (+17-063), from the sidecar: ways clamped 4,429 → 40; stations
off terrain by > 0.5 m 19,531 → 7; > 5 m 6,074 → 0; > 20 m 547 → 0; worst
45.44 m → 1.00 m; owner site (way 435 st 46–47) +30.88 m → 0.00. Near-patch
ways (the 40): > 0.5 m 204 → 7, worst 6.68 → 1.00 m. +17-097 (196.8 m),
+16-097, −13-077, +46+006: not re-run; the rule is scale-free (no OURS way
→ no clamp), so every off-neighbourhood station there goes to 0 by
construction.

EMITTABLE: the change only alters per-vertex altitudes of the existing
`INTERP_ALT` ribbon — single-valued heightfield, no new geometry, no new
marker.

BUILD-TIME IMPACT: expected REDUCTION, unmeasured (pre-ship: no timing
run). The clamp and its KD-tree fall from 60,594 to ~600 stations at TFFJ;
added: one prepared-polygon `covers` over the stations of bbox-prefiltered
ways, and ≤ 25 O(n) clamp evaluations per yielded run (2 runs at TFFJ) —
well under the 1 % floor (3 s tile / 0.6 s airport). v2: one prepared
`covers` per OSM way already clamped.

TESTS (headless; run once, only these files): extend
`tests/test_road_grade_clamp.py`, `tests/auto_patch_v2/test_m3c_roads.py`,
`tests/test_road_terrain_conformance.py`; fixture
`tests/fixtures/roadclampscope/tffj_ways.json` (committed with this spec:
ways 9 / 782 / 1054 / 435 — `s_m`, `dem_alt`, shipped `alt`, the in-band
mask, and the expected numbers).
T1 scalar-cap bit-identity: `cap_lipschitz_profile(s, dem, 0.08)` on the
four fixture ways == `shipped_alt_cap008` (≤ 1e-6) and == the per-segment
call with a constant array. T2 synthetic per-segment cap: a 30 % ramp, caps
[8 %, 20 %] → every segment ≤ its own cap. T3 the join: fixture way 9 — pin
station offset 0.000; way 435 → output `is` terrain, scope `terrain`, zero
tree stations. T4 the yield: fixture expecteds (`cap_eff` 0.1623 / 0.2000 /
0.2531 ± 1e-3; max offset 1.000 / 0.554 / 1.000 ± 0.005; no-budget 4.343 /
0.554 / 2.934); monotonicity of `dev(c)`; a synthetic in-band 8 % cliff →
`at_ceiling`. T5 deck pin inside a run still exact; refusal report intact.
T6 `OSM_to_MultiLineString(accepted_ids=…)` parallel to geoms incl. a
rejected and a degenerate way; mismatch → default caps + warning. T7
`answer` interpolation: a query midway between two stations reads the
mean; outside the radius reads the DEM argument. T8 sidecar v2 keys +
`bank_pavement_lines` reads it; conformance tool prices a v2 and a v1
sidecar. T9 v2: an OSM way leaving a synthetic coverage → `clamp_way` equals
the core function on the same arrays; `ROUTE`/`AXIS` values unchanged;
`road_coverage_joins` returns the crossing-interpolated value (a 10 %
outside slope, crossing mid-segment: old value off by 1.0 m, new exact).
T10 law mirror: `emit.toml` class caps == the core reader's. Schema
snapshot regenerated.

CONVERGENCE GUARDS: materiality 0.01 m / 0.01 pp; at most 2 fix iterations
per pre-registered target (T4 numbers, closing-test bars), then STOP and
report; `.progress` heartbeat. Any deviation from S.1–S.5 → stop, resume
this spec's author.

FILES (ONE Opus implementer, one coupled change-set):
`src/O4_Vector_Utils.py`, `src/O4_Vector_Map.py`, `src/O4_OSM_Utils.py`,
`src/O4_Cfg_Vars.py`, `src/auto_patch_v2/law/emit.toml`,
`src/auto_patch_v2/law/model.py`, `src/auto_patch_v2/airport/road_profile.py`,
`src/auto_patch_v2/emit/road_join.py`, `tools/road_terrain_conformance.py`,
`../tools/INDEX.md`, `../Sources/SceneryKit/Resources/o4_schema_snapshot.json`
(regenerated), the three test files; plus one pointer line under
design-surface-spec §37 (9) naming this supplement.

`tools/blast.py` hazards (index dc16fc9): `O4_Vector_Utils.py` — 29
importers, env flags `O4_VECTOR_SPLIT_M` / `O4_VECTOR_WELD_M` read here
(untouched), co-change `O4_Vector_Map.py` 58 %; `O4_Vector_Map.py` — 48
importers, 16 ROLE LITERALS ("renaming a ROLE_* VALUE in
auto_patch/layout.py breaks this file silently" — none renamed), reads the
patch artefact; `O4_OSM_Utils.py` — 36 importers (the new kwarg is
optional, default None); `O4_Cfg_Vars.py` — co-change
`SettingsLayout.swift` 75 %, `O4_Settings_Model.py` 50 % (hint only: no
Swift edit, snapshot regenerated); `road_profile.py` — hot symbol
`preferred_road_z` (3 users; signature unchanged); `road_join.py` — NO
direct test importer (T9 adds one). No wire-protocol (`events.py`) drift.

CLOSING TEST — ONE build: `venv/bin/python tools/harness/build_airport.py
TFFJ --tile 17 -63 --boundary skip` (harness rules). Bars, read from the new
sidecar + the loud line: `neighbourhood_ways` ≈ 40 (35–50); terrain-scope
stations with `|alt − dem| > 0.01` = 0; max offset ≤ 1.00 m; way through
17.8985499, −62.838825 `scope = terrain`, offset 0.00 (was +30.88);
`road_coverage_join` family 0 rows; tile rc 0. Register the frame.

NOT DONE BY THIS SPEC: no re-run of the four other tiles; the engine log's
admitted-by-`apt_array` vs admitted-by-banking split is unmeasured; VSS /
Austroads / RASt tables not obtained; the rail row is low-confidence; the
stamp gap in row 17 is reported only.

### S.7 OWNER QUESTIONS (only what 18n leaves open)

Q1. "Inside the patch neighbourhood a real road can still be steeper than
its class allows (at TFFJ the public road through the patch would stand
4.3 m off the ground at its 12 % class cap). I have the cap yield —
uniformly along that stretch, as you ruled for the TFFJ runway — so the road
is never more than 1.0 m off the terrain. Is 1.0 m the number you want, or
another?"

Q2. "The base engine (upstream Ortho4XP, unchanged since before our clamp)
levels every road that starts or ends within 1.5 km of an airport's bounding
box side-to-side without applying its 0.5 m banking test. I read your
'normal engine road processing' as keeping that exactly as upstream has it,
and scoped only our longitudinal clamp to the patch neighbourhood. Keep
upstream's rule, or should roads beyond the patch neighbourhood also have to
pass the banking test?"

Q3. "Your 2026-07-27 'auto' road mode still fetches every road class
(down to tracks) inside each airport's 2 km elevation-inset box and levels
them side-to-side — at St Barth that is the whole island, 4,342 ways. The
longitudinal clamp no longer touches them, but the side-to-side levelling
does (a flat 8 m ribbon across a hillside: about 1 m of kerb step on a 25 %
cross-slope, exactly what upstream does at road level 5). Keep it, or should
the level-5 detail also shrink to the patch neighbourhood? (The road DATA
stays as it is either way — the airport builder reads it.)"
