# Brief pack — lane `deckseat`

Base: main `6ca948ad` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Scout deckseat: consumer census for §49 — a parapet takes the emitted deck face as its datum and follows the deck's slope

## The brief

# Scout `deckseat` — consumer census for spec §49: a bridge parapet takes the emitted DECK face as its datum and follows the deck's slope (owner RULINGS 2026-09-17u-2 / 17w (2))

Owner: "Since the deck must slope to meet terrain (and it does in reality), unless you can change the bridge parapets to match the slope angle, we would have to seat them at the low end and let them disappear into the deck, better than leaving an end floating."

Read `docs/briefs/lemdobjects-report.md` §Q4/Q5/Q7 (D)/(E): `Bridge2.obj` (LEMD, one authored row, no elevation) → 5 bodies from 3 components; north wall b0 (50 feet, "line segment 1/2: mid-foot", 611.52) + b2 (footless remainder, 605.96); south wall b3/b4 footless at 599.3 (median ground over boxes straddling deck 605.6–609.5 and the `tunnel_ramp` floor 599.30). The emitted deck face `service_road bridge_deck:-6288` is READ BY NOTHING in `airport/` (`placement_read.py:51-52` publishes only `building` faces and `structure_rim` breaklines); `datum_of` (`anchor_rule.py:324`) returns None (`deck_kind ""`, `plate_y None`); `_own_ground_file` (`placement_plan.py:299`) and `segment_anchor` (`placement_cut.py:727`) never reach `anchor_of`. 13r ruled Bridge2/LEMD50 DRAPED plates — the session reads it as the deck PLATE, not the parapets (17w).

This is a NEW REGION entering the object stage (owner RULINGS 2026-08-30l): the spec starts with a census of EVERY pass that reads graded geometry in the object stage, ruled in ONE table, before any consumer is edited. Questions (cite file:line; no edits, no builds):
1. THE REGION CENSUS: every reader of `graded.json` faces / regions / breaklines in `src/auto_patch_v2/airport/` and `pipeline/` (grep `pads_rims_from_graded_doc`, `PAD_FACE_ROLE`, `RIM_BREAKLINE_KIND`, `graded`, `surface(`, `ground_under`, `foot_boxes`): for each, what it reads, what a third region "DECK faces (`bridge_deck:*`, and any other deck-family ref: `object_decks`, `pavement_decks`, viaducts)" would do to it if published beside pads and rims — inert / must consult / must ignore — one table.
2. THE DATUM PATH: where a per-station deck z would enter — `datum_of` (`anchor_rule.py:324-372`, the plate/deck branches keyed on `plate_y`/`deck_top_y`), `segment_anchor` (`placement_cut.py:727`), `_own_ground_file` (`placement_plan.py:299`) — and the ORDER the seat rules run in (which reading would pre-empt the deck if the deck were only added to `anchor_of`). Name the single derivation site you would choose.
3. THE SLOPE: the rebake writer bakes each body's seat into its `.obj` (`authored_offset`/`y_zero`): where is that transform applied (file:line), is it a pure translation today, and would a SHEAR (y += grade × along-axis distance, the deck's grade between stations) or a small pitch rotation be a one-site change there? What does the line-station cut (§16d) give for free — station spacing on `Bridge2` (b0 "1/2"), so the step between adjacent station seats on a deck rising 3.9 m over ~100 m — and is that step visible (name it)? Is `LEMDzaun.obj` (60 feet, 3 stations) the same class?
4. THE POPULATION: every body on the corpus (LEMD, HECA, OTHH old-pack dumps if reachable, VHHH, LGAV, KCLT, CYXY) whose plan box touches an emitted deck-family face — resource, class, seat reason, z vs deck z at its station — the parapets and everything else the rule would catch (light poles on decks, road furniture, the OTHH bridge decks memory `othh-bridge-deck-datum-r12`, `Bridge4.obj`'s plate). Which of those must be EXCLUDED by construction (a deck object itself, a pier, a body already on a plate datum)?
5. 13r: quote it (`tools/docq.py ruling 13r`) and say exactly what it ruled for `Bridge2`/`LEMD50` and whether "no object re-seat" bound the parapets or the plate.
6. The fallback: if the shear is refused, "seat at the LOW end and disappear into the deck" — which station and which reading delivers that with the existing rules.
7. Every source you could not verify.
Report as a cited markdown file in your scratchpad AND in full in your final message.

## Spec (object-placement) §16e

## §16e THE DECK TOP AND THE CREST PLATE ARE DATUMS (owner RULINGS 2026-09-13k; Fable 2026-09-13n) — lane `v2othhdatums`

Owner: "With single layer bridges over water we should be seating the top deck to
align with the ground and let the feet land where they may. The tunnel walls are now
seating above ground, where before, and as they should, be creating the tunnel ramp
walls, with their tops flush with terrain." Scout `v2othh1o` on OTHH 1.0.326: no bridge
is torn (1 seam airport-wide, not a bridge); the bridges come apart because (a) half
of a bridge stands over the canal (water is a datum at 0.00) and half on land (3.96),
so pieces anchored at their own feet sit 2.8 m apart (Bridge_01: 12 bodies at 1.946,
one at 4.763); (b) piers of one solid get per-pier zeros (`Bridge_02_CLUTTER_007`: six
piers, 3.2 m spread); (c) §16c (4)'s rest-on ranking inside a unit of four bridges
picks carriers on OTHER bridges 250 m away. The seat era had NOT seated these at all
(no seat: "anchor on water and no site datum") — rigid at authored y was what "not
coming apart" looked like; R12's `deck_top` lived in v1's post-mesh seat. The tunnel
walls: §14 (2)'s rim anchor sets `y_zero = 0` (its docstring assumes the floor plate
authored −depth and the parapet +2.99 — LEMD's pits, OTHH's 8 drainage basins with
`plate_y` < 0) — OTHH's nine `tunnels/*` walls carry `plate_y` **+5.00 / +9.55 / +10.00**
(the CREST plate), so their crests stand +5 … +10 m over the rim; `tunnel middle -
west` classifies as no basin and takes a low-side foot: +20 m. §5's MSL→AGL
conversion removed the author's sink (−3 … −8 m) that the seat used to correct.
`Member.deck_datum_z`, `deck_ends`, `plate_stations`, `plate_y` are stamped by the plan
and READ BY NOTHING in the placement path; `reseat_expect_m` (05n-4) is computed and
published with no executor. §8's byte-identity proof was taken at LEMD, where no
tunnel wall object is admitted — OTHH is the only corpus airport with them.

1. **THE CREST PLATE IS THE DATUM.** A body whose member carries `plate_y` anchors at a
   wall-band station (`plate_stations`) with `y_zero = plate_y`: the crest plate at
   the ground there. For `plate_y ≤ 0` (a floor-plate basin) this is byte-identical
   to §14 (2); for `plate_y > 0` (a crest-plate wall) it restores `DATUM_PLATE`. The
   rule keys on `plate_y`, never on the basin classification. `reseat_expect_m` is
   the residual the census prints.
2. **THE DECK TOP IS THE DATUM OF A SINGLE-LAYER SPAN OVER WATER.** A deck member
   whose ring stands over no graded face (`deck_datum_z` None) and whose components
   reach no ground within the ring anchors so that `zero = ground at its END LINES −
   deck_top_y` (R12's abutment reading; `deck_ends` derived for flag decks from the
   ring's ends on land); the feet land where they may. A flyover with land under its
   ring (`deck_datum_z` set, `deck_top_y` 8–10 m) is untouched.
3. **A BRIDGE IS ONE RIGID ASSEMBLY.** The bodies of one deck member (deck, piers,
   clutter of that `Bridge_NN` family) ride the deck's datum as one cluster — never
   per-pier zeros, never a carrier on another bridge: within a unit, a body of a deck
   family may rest only on its own family. The feet are reported, not seated.
4. **BARS (OTHH 1.0.326 frame, matched arms; no build)**: the nine walls' crests
   within 0.3 m of the corridor rim (today +5 … +20 m; `worst feet` 15.00/10.00 rows
   gone; the 8 drainage basins byte-identical); Bridge_01/04/05 deck tops at the land
   (3.96 ± 0.3; today 5.52 / 6.43 / 6.43), Bridge_02/06 unchanged; per-placement zero
   spread for every bridge ≤ 0.3 (`Bridge_02_CLUTTER_007` 3.2 → 0); cross-bridge
   carriers 0; §14 footless-at-datum 4 → ≤ 1; seams unchanged (1, not a bridge);
   the LEMD sites held; plan stage; suite. Instrument: `seat_feet_census.py
   --placement-plan --mesh` passes its bbox as (lat, lon) to a sampler that takes
   (lon, lat) — broken since the switch; fixed with a twin.

**MEASURED (lane `v2othhdatums`, 2026-09-13).** Implemented in
`airport/anchor_rule.py` (`Datum`, `datum_of`, `_datum_anchor`, `keep_off_row`,
`Anchor.datum`), `airport/rebake_plan.py` (`ring_ends` / `end_line_stations`,
stamped into the new `Member.deck_end_stations`), `model/rebake.py` +
`model/placement.py` (the two published fields), `airport/placement_body.py`
(the two `anchor_for` call sites pass `datum=`), `airport/placement_carrier.py`
(`is_elevated`), `airport/placement_plan.py` (the keep test), and
`auto_patch/engine_v2.py` (`surface.water`). Matched arms on the app's 1.0.326
OTHH frame (`o4_v2_rebake_OTHH.json` + `OTHH.graded.json` + the built
`Data+25+051.mesh`) replayed through `v2_rebake_replay.py plan --sampler mesh`,
and the LEMD 1.0.325 frame the same way.

* **WHY THE MESH AND NOT THE GRADED SAMPLER.** `obj8_split_report`'s graded
  sampler reads the canal as OFF-SHEET, and the whole of §16e (2) turns on
  water being a DATUM AT 0.00 — which only the mesh states. `v2_rebake_replay
  plan --sampler mesh` is also the sampler the APP calls (12g) and the entry the
  plan-stage time is read on, so one instrument gives both. No `--mesh` option
  was added to `obj8_split_report`: a second sampler in a second entry is the
  census-wrapper defect.
* **§16e (1), THE NINE WALLS (bar: crest within 0.3 m of the corridor rim).**
  Before / after, crest − ground at the wall band: `tunnel middle - west`
  **+19.54 → 0.00**, `tunnel1` (two placements) **+10.78 / +9.13 → +0.02 /
  +0.21**, `tunnel south west 2` **+10.30 → 0.00**, `tunnel_sw` **+5.29 →
  0.00**, `tunnel west 1` **+5.01 → 0.00**, `tunnel west 3` **+4.47 → 0.00**,
  `tunnel west 2` **+3.98 → +0.02**, `tunnel middle - east` **+6.02 → 0.00**.
  **Walls over 0.3 m from the band: 9 → 0.** Four of the nine were KEPT on
  their authored row before (the crest then stands `plate_y` over the ground by
  construction) and are WRITTEN now: the keep test asked whether the row and
  the anchor read the same SURFACE, which for a datum body says nothing
  (`anchor_rule.keep_off_row`).
* **The 8 drainage basins (`plate_y` ≤ 0) are BYTE-IDENTICAL** — every anchor
  point, `y_zero`, surface and reason unchanged, all still `basin rim (...)` at
  zero 3.959/3.960. **LEMD IS BYTE-IDENTICAL WHOLE**: 2,109 body rows and 4
  keeps, ZERO changed, including the T4S pit and every named site
  (green-TEJ3 20 rows, T4 47, HANG3 2, LEMD47 1, TABOX 2, Bridge4 2 — all 0).
* **§16e (2), THE DECK TOP.** `Bridge_01`'s deck takes the datum: deck top
  **5.52 → 3.23 m** against land at 3.96 — the bar (3.96 ± 0.3) is **MISSED by
  0.43 m**, and the mechanism is measured, not guessed: its end lines stand on
  the CANAL BANK, which the mesh reads 2.52 (start end median) and 3.60 (far
  end) with one station on water; 3.96 is the graded road further landward.
  R12's landward walk is not armed here — it walks on too few LAND samples and
  this end line has eleven. Reported, not iterated (materiality/attempt cap).
* **NOT DONE — `Bridge_04` / `Bridge_05` deck tops (6.43 / 6.43, bar 3.96).**
  Their deck members carry NO PART AT ALL in the plan (`parts 0`: the partition
  found no genuine solid in them), so the placement path forms no body for them
  and there is nothing to anchor; both stay KEPT on their row. Giving a
  partless datum member a body is a BODY-FORMATION change in
  `placement_body._raw_bodies` (every downstream reader indexes the body's
  parts) and belongs with §16 (1)'s population rule — reported for ruling.
* **NOT DONE — §16e (3), and the two attempts are the attribution.** The rule
  needs "the Bridge_NN family", and the pack states no such thing: OTHH's
  unit:6 puts Bridge_02, Bridge_03 and Bridge_06 — three bridges 250 m apart —
  on ONE row at ONE AGL, so `deck_signature.family_key` (the anchor spelling)
  calls all thirty members one family, and at LEMD a shared-datum row would
  call 171 resources one. The lane tried the DECK'S RING as the family (a body
  standing inside `deck_ring` is that bridge's: the placement bound rigid, its
  cuts exempt, and the rest-on candidate set — `placement_carrier.carriers_for`,
  the `ranked` list built under `if box is not None` — cut to its own family).
  Read on the member's LOWEST part the cross-bridge carries went **2 → 3**;
  read on ALL its parts (attempt 2) **2 → 5**, and Bridge_02's per-placement
  spreads went the wrong way too. Both attempts moved the section's own bar
  backwards and the code is DELETED, not kept: the ring does not partition the
  clutter (OTHH's `Bridge_02_CLUTTER_000` stands inside Bridge_06's ring) and a
  family-less body is not filtered at all. What §16e (3) needs ruled is what
  names a bridge when the row does not and the ring does not either.
  `Bridge_02_CLUTTER_007`'s six piers therefore still span **4.97 m**, the
  per-placement spreads are unchanged, and cross-bridge carriers stay **2**.
* **The rest of OTHH** (matched arms, mesh census): feet histogram IDENTICAL
  (437 / 164 / 44 / 3; rows with a foot > 0.3 m 211, > 3 m 3); files 1,334 →
  **1,338** (the four written walls); §13 `elevated bodies as own files` **0**
  with the 10 datum bodies counted apart; §14 `footless at datum` **3 → 3**
  (§16e (4) asked 4 → ≤ 1; on the MESH frame the baseline is 3, and the datum
  law does not touch that class — the graded frame's 4 is a sampler
  difference); §14 basin-RING spread 0.00 → **0.20 m** (bar 0.3: the walls now
  anchor on a band station rather than on the rim ring, and the bar reads them
  there); §15 stands-over float 72 → 74 with CARRIED **7 → 7**; §16b carried
  float 118 → **117**, wide 170 → **170**; cockpit CRITICAL visual 281 → 289.
  Torn seams were not re-read (the written-pack census; no pack was written).
* **Plan stage** (`--runs 3`, mesh sampler, foreground): **72.23 → 79.64 s**
  mean (min 70.71 → 74.45). The ≤ 60 s bar is MISSED ON BOTH ARMS — it was
  already missed on main — and the +7.4 s is the datum's own stations plus the
  four newly-written walls; `surface` calls 568,468 → 569,216 (+748, 0.13 %),
  so the wall time is not the datum reading and the two arms are within the
  ±25 % single-run swing the law names. Reported, not optimised.
* **THE INSTRUMENT (§16e (4)), fixed and twinned.** `seat_feet_census.py
  --placement-plan --mesh` passed `(min lat, min lon, max lat, max lon)` to a
  sampler taking `(min_lon, min_lat, max_lon, max_lat)`: at OTHH it raised
  `no mesh triangles inside (25.24, 51.59, 25.28, 51.62) — wrong tile?` and the
  mode had never run. `plan_bounds()` is the one place the two orders meet.
* **THE REPLAY NOW ARMS THE SHARED-REPO GUARD** (`v2_rebake_replay.py`, the
  same `harness/shared_repo_guard` implementation): `plan` calls
  `ensure_dsf_text_path`, which generates a DSF dump into a mod cache the lane
  worktree MOUNTS at the shared repo. Every run of this lane printed
  `[guard] shared repo UNCHANGED`.
* **Suite**: `tests/auto_patch_v2 tests/test_harness.py
  tests/test_role_edge_census.py tests/test_mesh_sampler*.py
  tests/test_post_mesh.py tests/test_object_rebake.py` — **1,237 passed, 1
  skipped**, twice. Six new twins in `tests/auto_patch_v2/test_v2objsplit.py`.

### §16e (3) AMENDED, (5)–(6) ADDED (Fable 2026-09-13; RULINGS 2026-09-13v) — lane `v2bridgecontact`

The lane's two attempts are the attribution: the ROW does not name a bridge
(OTHH unit:6 puts three bridges 250 m apart on one row at one AGL; LEMD's
shared-datum row would call 171 resources one family) and the RING does not
either (it is a bbox; `Bridge_02_CLUTTER_000` stands inside Bridge_06's ring).

3. **A BRIDGE IS NAMED BY CONTACT WITH THE DECK'S OWN MODEL FOOTPRINT.** The
   deck member's mesh projected to plan is the deck's FOOTPRINT POLYGON (the
   ring is its bbox and is too coarse where decks overlap in plan). A pier or
   clutter body BELONGS to the deck whose footprint polygon contains its plan
   centroid, or lies within 0.5 m of it; where two decks' footprints both
   contain it, the deck whose underside is nearest ABOVE the body's top wins
   (absolute vertical distance — §16c (4)). A body no deck footprint contains
   has NO bridge family: it takes the ordinary §16c rest-on ground, is never
   filtered and never carried by a deck. `family_key` is untouched for every
   other class; the bridge family is a derived relation computed once per
   plan and published per body (`bridge_of`). The bodies of one bridge ride
   the deck's datum as ONE rigid cluster (per-placement zero spread ≤ 0.3 m);
   within that cluster a body may rest only on its own deck or its own piers.
5. **A PARTLESS DECK MEMBER IS A BODY.** A deck member whose partition found no
   genuine solid (`parts 0`: Bridge_04, Bridge_05) is admitted in
   `placement_body._raw_bodies` as one body whose footprint is the model's
   declared bounds and whose deck top is its plate — the §16 (1) population
   class, not a skip. It anchors under (2) like any other deck.
6. **THE DECK'S END-LINE DATUM IS THE GRADED FACE THE DECK CONNECTS TO, NOT
   THE BANK UNDER THE END LINE.** Bridge_01's end lines stand on the canal
   bank (mesh 2.52 / 3.60) and the deck seated to 3.23, 0.73 m below the road
   at 3.96 that drives onto it — a step at the abutment an aircraft or vehicle
   would feel. The datum walks LANDWARD from the end line (R12's walk, armed
   regardless of sample count) until it meets a graded pavement/road face or
   the design surface's graded ground; bank and water samples are excluded.
   The owner's rule ("seat the top deck to align with the ground and let the
   feet land where they may") is judged there: |deck top − datum| ≤ 0.5 m
   (§31 visual) at EACH abutment; feet unconstrained and reported.

BARS (OTHH 1.0.326 frame, `v2_rebake_replay.py plan --sampler mesh`, matched
arms): Bridge_01/04/05 deck tops within 0.5 m of the graded road at each
abutment (today 3.23 / 6.43 / 6.43 vs 3.96); `Bridge_02_CLUTTER_007` pier
spread 4.97 → ≤ 0.3; per-placement zero spread ≤ 0.3 for every bridge;
cross-bridge carriers 2 → 0; `bridge_of` published for all 30 members;
walls (§16e (1)) and the 8 drainage basins byte-identical; LEMD 1.0.325
byte-identical; plan stage not worse than 80 s (`--runs 3`); suite twice.

**MEASURED — §16e (3)(5)(6) (lane `v2bridgecontact`, 2026-09-13).** Arms
on the app's 1.0.326 OTHH frame (`o4_v2_rebake_OTHH.json` +
`OTHH.graded.json` + the built `Data+25+051.mesh`) and the 1.0.325 LEMD
frame, replayed through `v2_rebake_replay.py plan --sampler mesh` and
censused with `seat_feet_census.py --placement-plan --mesh`. Implemented
in `airport/anchor_rule.py` (`Datum.ends` / `step_m` / `walk_max_m` /
`level_tol_m`, `_walked_stations`, `_line_reading`),
`airport/placement_body.py` (`_declared_parts` / `_declared_box` and the
§16e (5) admission), the new `airport/bridge_family.py` (the whole
relation, its census and its bars), `model/placement.py` +
`airport/placement_record.py` (`Body.bridge_of`, `Staged.bridge`),
`airport/placement_plan.py` (the once-per-plan footprint pass over
shared cutters), `airport/placement_write.py` + `auto_patch/engine_v2.py`
+ `tools/v2_rebake_replay.py` (the two `[bridge]` keys), and
`tools/seat_feet_census.py` (the block). Two modules were MOVED WHOLE
for the 1,000-line law, no line changed and both re-exported from
`placement_plan`: `airport/placement_read.py` (`read_plan`,
`pads_rims_from_graded*`) and `airport/placement_targets.py`
(`_footless_targets`, `_carrier_pieces`).

| bar | before | after |
| --- | --- | --- |
| `Bridge_01` deck top vs the graded road 3.96 | 3.23 (0.73 off) | **3.96 (0.00) PASS** |
| `Bridge_04` deck top | KEPT on its row, 6.43 | **3.96 (0.00) PASS** |
| `Bridge_05` deck top | KEPT on its row, 6.43 | **3.96 (0.00) PASS** |
| `Bridge_02_CLUTTER_007` pier spread | 4.97 m | 4.97 m — **MISSED** |
| per-placement zero spread > 0.3 m | 12 of 14 | 12 of 14 — **MISSED** |
| cross-bridge carriers (resource-name axis) | 2 | 2 — **MISSED** |
| `bridge_of` published | – | 57 bodies / 34 of 39 split bridge placements |
| §16e (1) nine walls + 8 drainage basins | – | **BYTE-IDENTICAL** |
| LEMD 1.0.325 whole | – | **BYTE-IDENTICAL** (322 splits, 2,122 bodies, 0 changed) |
| plan stage (`--runs 3`, mesh, foreground) | 79.64 s mean (13v) | **70.87 s mean, min 67.92** |
| suite | – | 1,264 passed, 1 skipped, twice |

(The three §16e (3) rows read MISSED against the bars as they stood when
this lane ran; RULINGS 2026-09-13ae WITHDREW (3) on this measurement and
made all three CENSUS LINES rather than bars — the section below.)

* **§16e (6), THE LANDWARD WALK, AND THE ONE LIMB THAT IS NOT THE
  SPEC'S.** The spec stops the walk at "a graded pavement/road face or
  the design surface's graded ground". THE FIRST LIMB IS UNREADABLE AT
  THIS SITE AND THAT IS MEASURED, NOT ASSUMED: `graded_roles_from_doc`
  builds 894 faces from `OTHH.graded.json` and `roles_many` is EMPTY at
  every station of every 5 m offset out to 140 m landward of BOTH of
  `Bridge_01`'s end lines — there is no graded face at the abutments at
  all, which is the same fact `deck_datum_z = None` states. The second
  limb is implemented as the reading the mesh does give: the walk stops
  at the first offset where no station is on water or off-sheet AND the
  line is LEVEL within `[placement] split_tol_m`. The bank is exactly
  the stretch where it is not — `end0` spans 1.34 m at the end line,
  1.76 at 5 m, 0.44 at 10 m and 0.00 (all 3.96) from 15 m; `end1` spans
  1.41 / 0.28 / 0.24 / 0.12 and 0.00 from 20 m; and 3.96 is the level
  the other three bridges carry as their own `deck_datum_z`. The
  role limb is kept and asked first wherever a sampler carries roles.
  **INTENT QUESTION for the spec's author:** is "the design surface's
  graded ground" the level line the walk finds, or is a deck whose
  abutments touch no graded face outside §16e (6) altogether?
* **§16e (5) IS THE WHOLE OF Bridge_04/05.** Their deck members carry
  ONE solid component each (54 and 18 `ATTR_hard_deck` triangles, y
  4.51–4.65 and 4.55–4.61 — a 0.14 m plate the thickness gate refused),
  so `_declared_parts` reads the components the cutter already has open
  and the member becomes one body with negative pids the contact graph
  can never match. Both end lines already read 3.96 with zero spread, so
  the walk does not move them: the datum alone puts them on the road.
  Files 1,338 → 1,340, placements kept 376 → 374.
* **§16e (3) IS DERIVED, PUBLISHED AND CENSUSED — AND WIRED TO NOTHING.**
  The relation (the deck's mesh projected to plan, exact
  point-in-triangle plus the 0.5 m reach, ties to the underside nearest
  the body's top) is in `bridge_family.py` and published as
  `Body.bridge_of`. Its other two halves — one bridge is one rigid
  cluster, and a body rests only on its own deck or piers — were built
  on it and BOTH ARMS MOVED THE SECTION'S OWN BARS BACKWARDS, so the
  code is DELETED under the attempt cap:
  * arm 1 (family cluster + pool cut to the family): cross-bridge
    carriers 2 → **9**, per-placement spreads over 0.3 m 12 of 14 → **17
    of 19**, `Bridge_02_CLUTTER_007` 4.97 → **6.61 m**.
  * arm 2 (the family actually UNIONED — §16c (7) deliberately never
    unions two footed bodies of one member, so arm 1's cluster never
    formed at all — and only the DECKS cut out of a family-LESS body's
    pool, which is §16e (3)'s own "never filtered"): cross 2 → **9**,
    spreads 12 of 16, worst 4.97 → **9.66 m**.
  THE MECHANISM (the distance from every bridge body's plan centroid to
  the nearest deck footprint): (a) THE FAMILY IS PARTIAL — 51 to 71 of
  ~80–102 bridge bodies fall inside a footprint or within 0.5 m and the
  rest stand 0.6 … 45 m outside it, because OTHH's bridge clutter runs
  BESIDE the deck plate (parapets, kerbs, lamp masts); a partly-bound
  bridge is worse than an unbound one, its named half on one zero and
  its unnamed half on its own ground, and the per-placement bar reads
  across both. (b) THE DECKS OVERLAP EACH OTHER — Bridge_02/03/06 are an
  INTERCHANGE: `Bridge_03_CLUTTER_000__b1` stands INSIDE Bridge_02's
  footprint (0.1 m), `Bridge_02_CLUTTER_001__b3` and `_002__b0` inside
  Bridge_06's. By CONTACT those bodies are that deck's, which is the
  law; the bar is stated over the pack's `Bridge_NN` SPELLING, which the
  law deliberately does not read. 66 of 71 published values agreed with
  the name and the five that did not are the interchange.
  **TWO INTENT QUESTIONS:** is a body BESIDE a deck plate that bridge's
  (the 0.5 m reach is the spec's own number and this lane did not change
  it), and on which axis is the cross-bridge bar read when contact and
  name disagree?
* **THE BYTE-IDENTITY WAS NEARLY LOST TO A MEMO, AND THE FIX IS THE
  RULE.** `anchor_rule._m_per_deg` memoises per 1e-4 deg of latitude and
  keeps whichever exact latitude touched a key FIRST. Reading it from a
  NEW call site before the unit loop handed every later caller in the
  same 11 m band a value it did not compute: 94 `authored_offset`s moved
  by ~8 microns and **101 OTHH placements this law does not touch** —
  four drainage/dewatering resources among them — stopped being
  byte-identical while every anchor point, zero and reason was
  unchanged. The footprint pass, `_declared_parts` and the landward walk
  all read the UNMEMOISED `rebake_plan._mpd` instead (`bridge_family._latlon`
  is `placement_cut.authored_latlon`'s own two lines over it), and the
  changed set went 101 → 59 → 58 → **1** (`Bridge_01`'s deck, which is
  §16e (6)) plus the two decks §16e (5) adds.
* **THE RESIDUE OTHH CARRIES.** §15 stands-over float 74 → 78 with
  CARRIED **7 → 9** and §16b wide 170 → 172: `Bridge_04`'s two clutter
  bodies now ride the deck body §16e (5) created (+2.47 m each), which
  did not exist to ride before. §14 footless-at-datum 3 → 3, §13
  elevated-own-files 0 → 0, §16b carried-own-ground 117 → 117.
* **A CONTROL TRAP, RECORDED — AND ITS CAUSE CORRECTED AT THE MERGE.**
  `v2_rebake_replay plan --src` pointed at ANOTHER LIVE CHECKOUT is not a
  control: `/Users/noah/XPTerrainBuilder/Ortho4XP/src` gave LEMD **3,646**
  bodies where a `git archive` of the sha this lane read on that tree gave
  **2,122**. The reason is not `--src` and not the same sha — it is that a
  LIVE CHECKOUT MOVES: the orchestrator merged §16d (`v2unboxed`, 748be853)
  into main between the `git log` that read the sha and the replay that
  used the tree, and 3,646 is §16d's own LEMD number, which BOTH arms give
  once this lane merges main `8ce4792a`. Every base arm here is cut with
  `git archive <sha> src | tar -x -C <scratch>`, which is the only spelling
  another session cannot change underneath a measurement.

### §16e (3) WITHDRAWN; (6) AMENDED (Fable 2026-09-13; RULINGS 2026-09-13ae)

Lane `v2bridgecontact` refuted (3) a third way (its MEASURED block above):
OTHH's bridge clutter runs BESIDE the deck plate (only 51–71 of ~80–102
bridge bodies inside a deck footprint or within 0.5 m; the rest 0.6 … 45 m
outside) and Bridge_02/03/06 are an interchange whose decks overlap in plan.
A footprint family is partial, and a partly-bound bridge is worse than an
unbound one (cross-bridge carriers 2 → 9 on both arms).

3. **WITHDRAWN.** The deck is the only datum body of a bridge. Its separate
   clutter and piers rest on their own ground under §16c and are REPORTED
   per body: `Body.bridge_of` (the deck whose model footprint contains the
   body, or ""), the per-placement zero spread and the cross-bridge carrier
   count are census lines, not bars. No bind and no carrier filter reads
   `bridge_of`. The owner's read of OTHH in app 1.0.327 decides whether any
   further bridge law is wanted.
6. **AMENDED — the walk stops at the first dry, level line.** The first
   limb (a graded pavement/road face) is unreadable where the mesh carries
   no roles (no graded face within 140 m landward of either Bridge_01
   abutment). The end-line datum walks landward from the end line in 5 m
   steps and stops at the first line that is DRY (no water sample) and
   LEVEL within `split_tol_m` across its span — that line is the design
   surface's graded ground there; the bank is exactly where the line is not
   level. Measured: Bridge_01 / 04 / 05 deck tops 3.96 / 3.96 / 3.96 against
   the land at 3.96.

**RE-MEASURED ON MERGED MAIN `8ce4792a` (lane `v2bridgecontact`).** The
lane merged main — §16d's `geom_boxes` parameter and
`PlacementState.geom_boxes` run through the same body constructors as
§16e (3)'s `bridge`, and both survive in every signature and call site —
and re-read the two bars against a base arm cut with
`git archive 8ce4792a src`:

* **Bridge_01 / 04 / 05 deck tops 3.96 / 3.96 / 3.96**, each 0.00 m from
  the land at 3.96 (§31 visual 0.5 m, PASS).
* **LEMD 1.0.325 BYTE-IDENTICAL** to main: 322 splits, 3,646 bodies (the
  §16d number, on both arms), ZERO changed rows.
* OTHH: **5** changed placements and 2 new, every one of them
  `Bridge_01` / `Bridge_04` / `Bridge_05` — the two datum decks §16e (5)
  admits and the sibling members that now find one. Every non-bridge
  placement in the airport is byte-identical.
* Suite `tests/auto_patch_v2 tests/test_harness.py
  tests/test_object_rebake.py`: **1,227 passed, 1 skipped, twice**
  (124 twins in `test_v2objsplit.py` — main's 118 and this lane's 6).
* §16e (3) stays WITHDRAWN per RULINGS 2026-09-13ae: `bridge_of` is
  published and censused, and nothing binds or filters on it.

### §16e (3) REINSTATED BY NAME — A BRIDGE IS ITS PACK'S NAME FAMILY (owner RULINGS 2026-09-13bn; Fable 2026-09-13) — lane `v2bridgename`

Owner (OTHH 1.0.327): "the actual deck is at the right level, but other
components are still too high so the bridge is still coming apart into
different components instead of staying a single unit." Row, ring and
footprint families were each refuted (13v, 13ae); the pack's NAMING is what
its author meant.

3. **THE NAME FAMILY.** A bridge's members are every placement whose
   resource file name shares the deck's stem — the text before `_CLUTTER`,
   `_LOD`, or a trailing numbered suffix (`Bridge_01`, `Bridge_02`, …), read
   off the pack's `OBJECT_DEF` paths by ONE derivation
   (`bridge_family.name_stem`). The deck member (§16e (2)'s datum body) is
   the family's datum; every other member — piers, clutter, railings —
   takes the deck's zero as ONE rigid zero: no per-member cut, no carrier
   search, no ground test (the feet land where they may — on, above or
   below the ground the deck spans). A stem with no deck member falls back
   to §16c. `bridge_of` publishes the stem; the census prints each family's
   spread and members.

BARS (OTHH frame, `v2_rebake_replay plan --sampler mesh`, matched arms):
per-family zero spread 0.00 for every `Bridge_NN` (today `Bridge_02_CLUTTER_007`
4.97 m); deck tops 3.96 / 3.96 / 3.96 held; cross-bridge carriers 0 on the
name axis; LEMD and KCLT byte-identical (LEMD's `Bridge4` is a line-station
body — name it); ONE OTHH build; suite twice.

## Spec (object-placement) §16d

## §16d THE PLAN BOXES WHAT THE WRITER WRITES (Fable 2026-09-13; RULINGS 2026-09-13h) — lane `v2unboxed`

Owner (13d items 3, 4): a dark plate ~15 m over the T4 apron; roofs still floating at
the cargo hangars. Scout `v2lemd325o` on the 1.0.325 written frame: the DSF has no
polygon with an elevation (every one of its 1,609 `.pol`/`.lin` is draped) — the
plate is an OBJECT: the FS2XPlane 10 × 10 m shadow quad every source object carries
at its origin, y = −5, normal down (`North_FSX-LEMD80.obj` is nothing else). Aerosoft
LEMD is a shared-datum pack — 2,035 of 2,109 bodies sit on two placement rows 18 m
from the owner's point — so seven such quads stack at that spot, and four ride zeros
chosen kilometres away: `Terminal4_green-T4BJO__b0` +16.37 m, `Terminal4_yellow-
LEMD16__b0` +15.90 (its box is the T4 terminal 2.27 km west), `Cargo-LEMD63__b6`
+7.13, `OldTerminal_FSX-LEMD43__b0` +2.22. At the cargo hangars `Cargo-TEJ1__b0`'s
roof plate stands +3.71 m over `NEWCO__b9`'s roof (76 of its 105 vertices lie 694 m
outside its own `geom_box`; on `NEWCO__b9`'s zero it lands 0.03 m from the roof top);
`Cargo-TEJ3__b1` the same. THE MECHANISM: `geom_box` is the hull of the ADMITTED
parts (`placement_plan.py:230`, `:298`) while the writer emits the source object's
triangles regardless — a zero-thickness one-sided quad is not admitted (`no_solid_
admitted 25`), a roof plate over another hangar was never boxed — so the geometry
rides a zero the body chose elsewhere and NO instrument reads it (§15, §16a, §16b
read the box; §7 reads feet; the quad has neither). Class: 397 of 2,109 bodies carry
geometry > 1 m outside their own box (202 > 10 m, 65 > 100 m, 8 > 1 km; 91 of them
carried/bound). Two instrument defects beside it: the cockpit block's worst
coordinate for §15/§16a/§16b rows is the PLACEMENT ROW (`placement_cockpit.py:42-60`)
— at a shared-datum pack that is one of two points for 96.5 % of bodies (12ak's
"LEMD03__b33 at 40.4928202" was that artefact); and the `nearest footed body of the
unit` fallback (`placement_carrier.py:833-843`) has no distance cap (35 binds, 19 over
100 m, one 3,323 m).

1. **EVERY WRITTEN TRIANGLE BELONGS TO A BODY WHOSE BOX CONTAINS IT.** At the split,
   a connected component — admitted as a part or not — whose plan distance from
   the body's part hull exceeds `coarsen_reach_m` (100 m) is not that body's: it is
   its own body, footless, anchored on its own ground at its authored offset
   (§16 (3)). The FS2XPlane origin plate (a one-sided, zero-thickness quad at the
   object origin below y = 0) is such a body: written on its own ground at −5 m, it
   is buried as the pack authored it. `geom_box` is the hull of what the file will
   contain, and §16b's span bar reads it.
2. **THE NEAREST-FOOTED FALLBACK IS CAPPED** at `coarsen_reach_m`; beyond it a
   footless body takes its own ground (§16 (3)).
3. **THE COCKPIT COORDINATE IS THE BODY'S**: the worst row's coordinate is the
   centre of the body's written geometry (or its worst foot), never the placement
   row.
4. **BARS (1.0.325 written frame, matched arms)**: the four plates gone from the sky
   (each on its own ground at −5 m); `Cargo-TEJ1__b0` on `NEWCO__b9` (roof base within
   0.3 m of 605.04); `TEJ3__b1` likewise; bodies with geometry > 1 m outside their
   box 397 → 0 (twin); the nearest-footed fallback beyond 100 m 19 → 0; the 11at/12h/
   12o/12z/12aq/12ar sites held; torn seams 0; §15 carried float 0; files quoted;
   plan stage LEMD ≤ 10.3 s; OTHH the same under the guard; the cockpit block's
   worst coordinates verified against the bodies' geometry (twin); suite. No build;
   the app after.

### §16d (1)–(3) MEASURED (lane `v2unboxed`, 2026-09-13; branch `claude/v2unboxed`)

Implemented in `airport/placement_orphan.py` (NEW: §16d (1)'s whole law — the
components the plan's bodies do not own, placed), `airport/placement_cut.py`
(`_LineCutter.written_components` / `plan_box_of_tris` / `_draped_components`),
`airport/placement_plan.py` (the pass between §15's candidates and §15's search;
`_geom_hull`, `Staged.geom_boxes`), `airport/placement_carrier.py` (§16d (2)'s
cap), `airport/placement_cockpit.py` (§16d (3)) and `airport/placement_seams.py`
(`census_outside_box`, §16d (1)'s bar instrument, printed by `--write-pack` and
`--torn-seams`).  Two files moved for the 1,000-line law: `_footless_targets` /
`_carrier_pieces` into `placement_body.py`, `group_at_zero` into
`placement_boxes.py`; both re-exported where every caller reads them.

* **ATTRIBUTION FIRST — the dry arm is NOT the app's arm.**  `obj8_split_report`
  on the 1.0.325 rebake plan does not reproduce the app's written carriers, and
  the cause is THE SURFACE, not the population: the app hands `build_splits`
  the built MESH sampler (`engine_v2._placement_surface(mesh_sample)`) while the
  tool hands it a `LinearNDInterpolator` over `LEMD.graded.json`'s emitted
  vertices (`surface_from_graded`).  Everything else matches — identical
  `bodies_uncoarsened` 11,135 and `line_segments` 849, identical law keys, the
  same `--admit-skipped` population — while the SURFACE-driven readings do not:
  `anchor_off_surface` 0 (app) vs 6 (dry), `carrier_refused_zero_off_ground`
  105 vs 221, `carrier_refused_far_from_carried_ground` 179 vs 274,
  `unit_clusters` 206 vs 202.  Those refusals are exactly what pushes a search
  down to the fallback rules, which is where `Terminal4-LEMD01__b0` sits
  (`elect__b0 (838 m)` written, `SENRG__b233 (512 m)` dry).  **Every bar below
  is therefore read on MATCHED DRY ARMS** — main `59790e5f` into pack copy A,
  this branch into pack copy B, the same rebake plan, the same graded surface,
  APFS clones of the live pack, the guard armed (both runs print `shared repo
  UNCHANGED`).  The app's own figures are quoted beside them where they exist.

* **THE INSTRUMENT (§16d (1)'s bar).** `census_outside_box` opens the WRITTEN
  files and asks whether every `VT` row lies inside the `geom_box` the plan
  published for that body.  On the app's live 1.0.325 pack it reads **378** of
  2,109 bodies over 1 m (the scout's 397 under its own fixed metres-per-degree;
  same population, same 8 over a kilometre, worst `Munoza-LEMD80__b0` 3,682 m).

  | bar (matched dry arms) | A (main) | B (branch) |
  |---|---|---|
  | §16d bodies with geometry > 1 m outside their box | 390 | **0** (0 even over 1 cm) |
  | nearest-footed fallback binds / over 100 m | 49 / 29 | **21 / 0** |
  | §16c torn seams outside line/arc pieces | 0 | **0** |
  | §16c single-component resources in ≥ 2 files | 0 | **0** |
  | §15 carried body floating over its carrier | 0 | **0** |
  | duplicate rows of a split placement surviving | 0 | **0** |
  | DSF round trip / new `OBJECT_DEF`s read back | OK 2,141 | **OK 2,279** |
  | files | 2,141 | **2,279** |

* **THE FOUR PLATES (§16d (4)).**  Each is now its own footless body on its own
  ground with its authored y kept, so it renders 5 m UNDER the ground the pack
  put it over — buried, as authored:

  | plate | A: render − ground | B |
  |---|---|---|
  | `Terminal4_green-T4BJO` | **+15.94** | −5.00 (ground 595.81) |
  | `Terminal4_yellow-LEMD16` | **+15.73** | −5.00 |
  | `Cargo-LEMD63` | **+5.77** | −5.00 |
  | `OldTerminal_FSX-LEMD43` | **+1.72** | −5.00 (ground 595.82) |

  (the app's own frame read +16.37 / +15.90 / +7.13 / +2.22 — the same four
  plates, the surface difference above.)

* **THE CARGO ROOFS.**  `Cargo-TEJ1`'s roof plates are no longer one carried
  body riding a zero chosen elsewhere: each component finds the hangar it stands
  over.  The piece over `NEWCO__b9` has its roof base at **604.95** — 0.09 m
  from the hangar's authored roof top 605.04, inside the 0.3 m bar; the piece
  over `NEWCO__b10` reads 604.72 on its own hangar.  `Cargo-TEJ3` likewise
  (ten pieces on `CNTRL`, `FBRIK__b0/b1`, `NEWCO__b0/b3/b5/b8/b11/b12`, `TNT__b3`).

* **THE NAMED SITES HELD** (11at/12h/12o/12z/12aq/12ar; base planes per
  resource, arm A → arm B): `Terminal4_green-TEJ3` 610.41–617.17 → identical;
  `Terminal4SAT_green-TEJ3` 589.47–597.26 → identical; `HANG3` 605.73–606.06 →
  identical; `LEMD47` one body 603.53 → identical; `Bridge2` 598.73–607.03 →
  identical; `TABOX` spread 0.01 → identical; `T2NBG` 602.81–607.24 → identical;
  `green-PKT4` and `Terminal4_green-TEJ1` identical; `Terminal4_48` one body,
  spread 0.00 → identical.  `green-STRT4` gains 5 files (19 → 24) at the SAME
  base range 597.54–617.71: the orphan components now have files of their own
  inside the range, not outside it.

* **A LATENT WRITER DEFECT FOUND AND FIXED.**  `obj8_split` named a body's file
  by its index in the LIVE list (`body_resource_name(rel, k)`) while the plan
  spells it `body_resource_name(resource, body_id)` and the DSF row is written
  on the plan's name.  A body the cut leaves with NO triangle (its geometry
  inside an ANIM block another body owns) therefore shifted every later body's
  file one name down — the row carried the NEXT body's geometry at this body's
  zero.  Measured at LEMD: `OldTerminal_FSX-DCNEUN`'s `__b0` row held `b1`'s
  object, 254 m from `b0`'s own box.  The file is now named by its body, and a
  body with no file is dropped from the plan's rows (`bodies_without_a_file`) so
  no `OBJECT_DEF` points at a file nothing wrote.

* **THE COST, REPORTED NOT HIDDEN.**  LEMD plan stage **13.6 → 17.8 s** (wall
  16.81 → 21.08 s, medians of 3 foreground runs each; the branch's own
  `plan stage` line is new and reads 17.6–18.2 s, the baseline's inferred from
  the same fixed 3.2 s of tool overhead).  §16d (4)'s `LEMD ≤ 10.3 s` is
  **MISSED on BOTH arms in this frame** — the 10.3 s figure was read without
  `--admit-skipped`, which this replay needs.  OTHH plan stage **≈ 83 → 86.1 s**
  (wall 86.99 → 89.89, +3 %), the ≤ 60 s bar missed on both arms as it was at
  12ap.  The cost is the POPULATION: LEMD now places 27,737 components the plan
  never saw (19,905 joined to a body within the reach, 7,832 their own bodies),
  OTHH 143,950 (98,776 / 45,174), and 7,786 more carrier searches run at LEMD.
  Three optimisations already took most of it back and are part of the change:
  `written_components` hands back numpy arrays and the caller builds Python
  triples only for what it places; the joined components of one group are ONE
  append, not one per component; `group_at_zero` memoises each group's zero and
  ground range on its length (29.6 M inner steps, 9 s of the profiled stage).
  A further reduction is a new question, not this lane's.

* **MOVING THE WRONG WAY, NAMED.**  §16b's two counts rise because the
  population they read grew: `carried piece float over its OWN ground > 0.5 m`
  120 → 151 and `body wider than its terrain group` 1,037 → 1,116 (both already
  over their bar 0 on main).  The rise is the components that previously stood
  in some other body's file where NO instrument read them; they are now bodies
  with their own ground reading.  `§16 CARRIED bodies whose carrier's zero is
  over 1 m from the ground under their own geometry` 62 → 81 (information only),
  and COCKPIT CRITICAL visual 459 → 494 for the same reason.

* **SUITE** `tests/auto_patch_v2 tests/test_harness.py
  tests/test_role_edge_census.py tests/test_mesh_sampler*.py
  tests/test_post_mesh.py tests/test_object_rebake.py`: **1,234 passed, 1
  skipped**, twice.  Twins: `test_16d_1_a_component_beyond_the_reach_is_its_own_body`,
  `test_16d_1_every_written_triangle_lies_inside_its_body_box` (the bar as a
  property), `test_16d_2_the_nearest_footed_fallback_is_capped`,
  `test_16d_3_the_cockpit_coordinate_is_the_bodys_not_the_row`.
  `coarsen_reach_m <= 0` DISARMS the reach (the convention every other
  plan-contiguity key takes): the component then joins the nearest body.


### §16d (4)–(6) Carried components group by carrier; the ground bound is member-agnostic; a body anchors on the pad it stands on (Fable 2026-09-13; RULINGS 2026-09-13m)

Scout `v2kclt1o` on KCLT (Nimbus, native XP12: master models per material — `paredes_N`
walls, `techos_N` roofs, `vidrios` glazing — each on ONE placement row; 34 rows carry 71
split placements, bodies up to 1,628 m from their row): (a) hangar wall `005_ALB__b9`
5.04 m into its pad — a SAME-MEMBER §16c (7)/(8) bind to a body 500 m away on the
apron; 12ap's 0.5 m ground bound tests only `member != top.member`, so it was skipped
(the cluster spans 714 m at one zero; the airport's worst §17 row +5.96 m); (b) roof
plates `001_ALB__b5/b6/b11/b18/b28/b29` float +2.5 … +7.4 m — elevated bodies of 3–12
components spanning 154–1,774 m carried at ONE zero (`carried_bodies_uncut` 5,295 vs
3 cut by carrier), the walls under them correctly seated; (c) the terminal: one pad
`building80` (1.19 m of relief); 213 bodies overlap it, zeros 210.5–223.7 — the 80
whose ANCHOR POINT lands on the pad agree with it to 1.13 m, the 133 whose anchor
point lands on apron/adjacent ground (213.8–224.6) do not; clusters by contact are 272
separate things at one zero each; 12 rest-on carriers with authored gaps to −9.9 m;
a wall carried by GLAZING; a 20-vertex z = 0.00 crater in apron face 661 (`dsf:pol31`)
— design surface, not object law (RULINGS 13m, lane `v2zerocrater`).

4. **A CARRIED BODY'S COMPONENTS GROUP BY CARRIER.** Each connected component of a
   carried (elevated / footless) body finds the footed body IT stands over (§15's
   overlap at the component); components over different carriers are different
   pieces, each at its carrier's zero; a component over none anchors on its own
   ground (§16 (3)). §16a (1)'s "cut where the carrier is cut" and (1)'s reach are
   read per component. A roof resource of twelve plates over twelve buildings is
   twelve pieces.
5. **THE GROUND BOUND IS MEMBER-AGNOSTIC**: §16c (7)'s bind holds only while the
   bound body's own-ground zero is within `visual_m` 0.5 of the senior's, same
   member or not (12ap (A) applied everywhere); a cluster's zero-plane span obeys it.
6. **A BODY ANCHORS ON THE PAD IT STANDS ON.** Where a footed body's written
   geometry lies mostly on a `building` pad, its anchor point is chosen on that pad
   (the low-side foot that lies on the pad, else the pad's level under the body's
   centroid) — never on the apron or ground it happens to spill onto. The pad's own
   relief (§20: 1.19 m over 900 m at KCLT's terminal) is a §20/§28 reading, reported.
7. **BARS (KCLT 1.0.324 frame + LEMD 1.0.325 frame, matched arms)**: `005_ALB__b9` on
   its pad (−5.04 → within 0.5); the six `001_ALB` roof bodies on their walls (each
   piece within 0.5 m of the wall top beneath it); terminal bodies anchoring off
   every pad 133 → 0, the complex's zero spread 13.2 m → the pad's relief; the
   glazing carrier named and, if glazing is footless by authoring, excluded by the
   existing solid test (report, do not name-match); the LEMD sites held; seams 0;
   §16b carried-own-ground bar at KCLT 32 → quoted; files; plan stage; suite.

### §16d (4)–(6) MEASURED (lane `v2unboxed`, 2026-09-13; branch `claude/v2unboxed`)

Implemented in `airport/placement_body.py` (§16d (4): `_atom_targets`, one carried
target per ATOM, and `CARRIED_ATOMS_MAX`), `airport/placement_plan.py` (the split
before §15's search, carrying the SOURCE group so §16c (7)'s cluster membership
survives it), `airport/placement_atom.py` (§16d (5): the `member != top.member`
clause deleted) and `airport/anchor_rule.py` (§16d (6): `pad_majority`, and the
`pads` argument WIRED at last).  `placement_geom.py` took `written_components` /
`part_tris` / `plan_box_of_tris` for the 1,000-line law.

* **THE ATOM, NOT THE BARE COMPONENT.**  §16d (4) says "each connected component";
  the division here is by §16c (1)'s ATOM (`_comp_blocks`) — the component, or the
  CLUSTER §16c (6)/(7) bound it into.  Dividing a rigid cluster would undo that law,
  and the two readings are the same wherever no cluster exists.  **Reported as a
  deviation from the sentence, held to be its intent.**

* **BARS (KCLT 1.0.324 frame, matched dry arms; the write half into an APFS clone,
  guard armed, `shared repo UNCHANGED` on every run).**

  | bar | before (this branch after §16d (1)–(3)) | after |
  |---|---|---|
  | `005_ALB__b9` vs its `building` pad | **−5.04** (12ap's frame) / −5.85 here (zero 210.46, pad 216.31) | **+0.02** (zero 215.51, pad `building26` 215.49–215.51) |
  | widest RETAINED cluster zero-plane span | 5.69 m | **0.64 m** |
  | binds refused for ground | 14 | **22** |
  | carried bodies divided by ATOM | 0 | **473** |
  | footed bodies anchored ON their pad (§16d (6)) | 0 | **61** |
  | §15 carried body floating over its carrier | 0 | **0** (bar 0) |
  | §16d written geometry outside its own box | — | **0** (bar 0) |
  | §16c torn seams outside line/arc pieces | 0 | **1**, step **+0.16 m**, `paredes_9_charlotte` b1↔b6, ONE shared vertex — under the 0.3 m census tolerance and under `visual_m`; NAMED, bar missed |
  | files | 473 | **477** |
  | DSF round trip / defs read back | — | **OK, 477/477** |
  | plan stage (dry, 3 runs) | 8.65 s | **8.3–8.5 s** |

  The `001_ALB` roof bodies the owner's read names are now cut per atom and each
  rides the wall body IT stands over (`b5` → `006_ALB__b0` 219.56 vs 219.94 ground,
  `b6` → `008_ALB__b1` 221.39 vs pad `building59` 221.38–221.41, `b11` →
  `004_ALB__b0` 217.51 vs pad 217.59, `b29` → `004_ALB__b25` 216.93 vs pad
  216.93–216.96) where before they were ONE carried body per resource at one zero
  (217.51 under 223.75 m of ground, 208.81 under 221.89).  §15's own carried bar —
  `zero − zero_beneath`, which IS "within 0.5 m of the wall beneath" — is **0 on
  both arms**.

* **THE TERMINAL, REPORTED NOT CLOSED.**  Over `building80` (1.19 m of relief,
  865-node ring) the ON-PAD set's zero spread is **1.03 m** on both arms — the pad's
  own relief, as §16d (6) predicts.  The count of bodies whose anchor lands OFF the
  pad moves only 71 → 65 (footed 26 → 24) in this frame, NOT 133 → 0: the 133 was
  read on the app's 1.0.324 WRITTEN frame, and the residue here is bodies whose
  ground contacts are MOSTLY off the pad (the rule's own majority test declines
  them) plus carried bodies, which take their carrier's anchor by §15 and not their
  own.  Named, not closed.

* **A DEFECT §16d (4) EXPOSED AND FIXED.**  A target group holding BOTH a cut piece
  (its own `tris`) and a raw the cut never touched (its parts' whole components) was
  read for its `tris` alone, so the rest of the group's triangles were claimed by no
  body and `obj8_split` handed them to the nearest one: measured at KCLT, 9
  placements left 990–3,280 triangles unclaimed and `001_ALB__b32`'s file reached
  207 m outside its own box.  The audit (every placement's solid triangles against
  the union of its bodies' `tris` and `cut_components`) reads **0 of 103** after.

* **THE COST — OVER BUDGET, AND NAMED.**  Plan stage, dry, this machine: LEMD
  13.6 (main) → 17.8 (§16d (1)–(3)) → **25.0 / 28.6 / 46.0 s** over three runs;
  OTHH ≈83 → 86.1 → **136.5 s**; KCLT 8.65 → **8.3–8.5 s**.  The LEMD run-to-run
  swing is the standing ±25 % and worse; the OTHH figure is one run.  §16d (4) asks
  a carrier search PER ATOM, and OTHH's clutter members publish thousands of them.
  Three narrowings are already in: a body narrower than `coarsen_reach_m` is not
  divided (§16a (1) already cuts those against the carriers the search returns),
  `CARRIED_ATOMS_MAX` 64 bounds a body's pieces, each piece carries only ITS OWN
  parts (so §15's contact fallback reads its own neighbours, not the whole body's),
  and that fallback now counts by set intersection instead of scanning the unit's
  neighbour list once per candidate.  **This takes an airport that was already over
  the 60 s per-airport budget further over it: it needs the owner's approval and a
  Fable-5 whole-pipeline optimisation review before it ships** (`Ortho4XP/CLAUDE.md`
  HARD LAW).  No further reduction was attempted in this lane.

* **THE LEMD SITES HELD** on the same 1.0.325 frame, written arm: the four shadow
  plates still −5.00 on their own ground; `Cargo-TEJ1` on `NEWCO__b9` at 604.95;
  §16d outside-box 0; seams 0; §15 carried float 0; round trip OK 2,435/2,435;
  every named site's base range identical to §16d (1)–(3)'s except
  `Terminal4_green-TEJ1` (spread 4.01 → **1.28**) and `T2NBG` (4.44 → **4.28**).
  §16b's carried-piece own-ground count rises again with the population it reads
  (LEMD 151 → 154, KCLT 41 → 41), already over its bar 0 on every arm.

* **SUITE**: **1,237 passed, 1 skipped**.  Twins:
  `test_16d_4_each_atom_of_a_carried_body_finds_its_own_carrier`,
  `test_16d_5_the_ground_bound_holds_inside_one_member_too`,
  `test_16d_6_a_body_anchors_on_the_pad_it_stands_on`.  Four existing twins were
  re-read against the new law and are marked with the ruling that changed them: the
  two §16a (1) roof twins now assert the OUTCOME and the atom count, §14 (1)'s
  footless twin reads two atoms as two own-ground bodies, and 12ap's bind twin
  asserts the refusal INSIDE one member.

* **NOT DONE.** The KCLT z = 0 crater in apron face 661 (`dsf:pol31`) is lane
  `v2zerocrater`'s and no bar here excludes or names its bodies — the terminal
  figures above are quoted whole.  The glazing carrier is not separately attributed.
  No airport was built.

## Spec (object-placement) §16c

## §16c THE CONNECTED COMPONENT IS THE ATOM (Fable, 2026-09-12; RULINGS 2026-09-12b/12d)

The owner's read of 1.0.320 (12b) found hangar vaults sliced, a canopy building in
seven pieces over 11 m, the T4 approach deck in 39 pieces (worst seam 16.29 m), and
the old terminal's roofs 0.57–0.70 m below their walls. Scout `v2lemd320`: §16b (1)'s
cut has the authored TRIANGLE as its atom (`obj8_split.BodyCut`, `tri_owner` senior
to the vertex vote, unowned triangles to the nearest body), so a terrain-group
boundary falls INSIDE a connected solid and the halves are written at two zeros.
Written-frame census: 2,554 seams where two sibling files share an authored vertex,
1,994 with a step > 0.30 m, 2,275 of 3,561 bodies (63.9 %) on a torn seam; 19
single-component resources written as ≥ 2 files. §16b's own MEASURED block refuted
the finer footed triangle cut for "tearing rigid solids" and kept the same atom.

1. **NO CUT CROSSES A CONNECTED COMPONENT.** Every group §9, §16 (2), §16a (1) and
   §16b (1) form — terrain, foot, carrier — is formed over COMPONENTS
   (`obj8.solid_components`), never over triangles: a component is keyed by the
   design surface under its OWN geometry and joins ONE group whole. A component
   wider than its terrain stays whole (a vault, a deck slab, a canopy) — one file,
   one zero. The only station cuts are §10's line segments and §14a's basin arcs
   (drape-class by ruling), and those pieces are the only sibling files allowed to
   share an authored vertex. `split_obj8` never assigns a triangle to a body that
   does not own its component.
2. **THE CARRIER QUESTION IS ASKED ONCE PER COMPONENT** (§16b (2) read on
   components), and the bounded fallback §16b (3) reads the ground under the
   component's CONTACT — its feet, or where it stands over the candidate — never
   the median of its footprint (the deck slab's median ground was the underpass
   floor 15 m below its pier feet).
3. **A FOOT OVER A STRUCTURE CUT IS NOT A GROUND FOOT.** §9's low-side rule and
   §16a (2)'s carrier ground test ignore feet whose surface sample lands on a
   `tunnel_ramp` / tunnel floor / basin-interior face: the body spans the cut. The
   lane MEASURES this first — whether `PKT4__b0`'s zero 611 is a trench foot — and
   implements it only if so; otherwise reports the refutation.
4. **THE CARRIER IS WHAT THE BODY RESTS ON** (§15 (1)(a) amended; amended again
   2026-09-12n): among the candidates a body plan-overlaps, the carrier is the one
   whose TOP surface under the overlap lies NEAREST the body's base plane in
   absolute distance — above or below: a roof let into a parapet rests on walls
   whose top stands above its base, and "nearest below" (the first wording) sent
   the T2 roofs to bodies 6 m off. Largest overlap breaks ties only. A 158 m² wall whose top meets the roof beats a 129,113 m² floor slab
   17 m below it. (`LEMD41__b1` on `LEMD52__b0` reads 0.01 m today; every other T2
   roof rode `LEMD38`'s floor pieces.)
5. **THE BAR INSTRUMENT IS THE WRITTEN FRAME**: `obj8_split_report` (and the
   `--write-pack` census) print the TORN-SEAM census — sibling files of one
   placement sharing an authored vertex, the base step per seam, by class — from
   the written files (the scout's `tear.py`, promoted on this second use). Bars,
   LEMD 1.0.320 frame + OTHH: torn seams outside line/arc pieces **0**; single-
   component resources in ≥ 2 files **0**; the four sites — `HANG3` vault one file
   per component, seams 0; `green-LEMD50` ≤ 2 files; `green-STRT4` deck components
   c0/c2/c3/c41/c42 one file each, no piece more than `split_tol_m` below its pier
   feet; T2 roofs `TEJ3/tej2_teilb/LEMD58/LEMD50/T2CSG` within 0.3 m of the wall
   tops (`LEMD52/53/59/T2BCK/LEMD54`, today 0.57–0.70 m low), skylight strips in
   ONE file; §15 carried float 0; the 11at sites held (green-TEJ3 0.02/0.04, gate-5
   sign −0.15, T4 deck −0.05); files ≈ 900–1,400 (counterfactual estimate 899);
   plan stage on the GRADED sampler ≤ main's and the `_surface` call count quoted
   (the mesh-sampler cost is 12a's, measured separately); round trip OK; suite.

**MEASURED (lane `v2atom`, 2026-09-12; branch `claude/v2atom`).**
Implemented in `airport/obj8_split.py` (§16c (1)'s writer half: the
triangle goes to the body owning ITS COMPONENT, an unowned component
goes WHOLE to the nearest body, and the vertex vote and per-triangle
nearest fallback are DELETED), `airport/placement_cut.py` (§16c (1)'s
cut half: `_LineCutter.comp_of` / `_comp_blocks` — the vectorised
triangle→component map every cut now groups by; `terrain_groups`,
`foot_groups` and `carrier_groups` place WHOLE components;
`carrier_groups` takes the piece's own written triangles; `part_tops`),
`airport/placement_body.py` (the footed triangle cut reads the same
`own_tris` its pre-test measured), `airport/placement_boxes.py`
(§16c (2)'s `contact_ground`, `foot_box_index`, `CONTACT_PTS_MAX`),
`airport/placement_carrier.py` (§16c (4)'s rest-on ranking and
`Candidate.top_y` / `part_tops`), `airport/placement_plan.py` (the
wiring) and `airport/placement_seams.py` (NEW: §16c (5)'s torn-seam
census, the scout `v2lemd320`'s `tear.py` promoted).

* **THE FOUR SITES AND THE CLASS REPRODUCED** on the live 1.0.320
  written pack, read-only, by the promoted census: `HANG3` 10 files /
  **14 torn seams** worst 3.05 m; `green-LEMD50` 7 files / spread
  11.12 m; `Bridge2` 8 files / 11.72 m; `green-STRT4` **53 files**,
  `__b44` seams up to **16.29 m**; whole plan **2,554 seams, 1,994 over
  0.30 m** (974 + 1,580 line/arc, 790 + 1,204 over) — the scout's
  figures to the unit.
* **§16c (3) IS REFUTED AND IS NOT IMPLEMENTED.**  `PKT4__b0`'s zero is
  611.00 on the 1.0.320 frame (611.23 was 1.0.319's) and its anchor
  reason is its own: `low-side foot (no point within 0.3 m of the body's
  zero plane: authored relief 0.95 m)`.  NOTHING of it stands on a
  structure cut: all 8 of its foot boxes and all 32 of its written
  geometry samples lie on NO graded face at all (`tunnel_ramp` ×17 and
  `tunnel_trench` ×1 are the only structure roles `LEMD.graded.json`
  carries; the nearest is 65 m away in latitude), and 0 of 32 samples
  and 0 of 8 foot boxes fall inside any of the 19 structure RIM rings.
  "A foot over a structure cut is not a ground foot" has no instance
  here; the deck slab's real mechanism is §16c (2)'s, which is
  implemented.
* **THE BARS**, matched replay arms on the 1.0.320 LEMD rebake plan +
  `LEMD.graded.json`, `--admit-skipped` on the live pack, the write half
  into APFS clones (BEFORE is this lane's instrument commit `3dff7879`
  on main's law, so both arms are read by one instrument):

  | bar | 1.0.320 written | before | after |
  |---|---|---|---|
  | torn seams outside line/arc pieces (bar 0) | 974 (790 > 0.3 m) | 723 (575 > 0.3 m) | **0 — MET** |
  | single-component resources in >= 2 files (bar 0) | 131 | 128 | **0 — MET** |
  | bodies on a torn seam | 1,011 | 816 | **0** |
  | line/arc station seams (lawful, apart) | 1,580 | 1,446 | 891 |
  | §15 carried `stands-over float > 0.5 m` (bar 0) | — | 0 | **0 — MET** |
  | §14 `footless at datum` / `on ground` / `basin split` | — | 0 / 0 / 0 | **0 / 0 / 0** |
  | §16 `rows on the datum outside the plan` | — | 0 | **0** |
  | §14a basin ring bar (<= 0.3 m) | — | 0.18 m, 0 over | **0.18 m, 0 over** |
  | §16b carried piece float > 0.5 m (bar 0) | — | 120 | 124 |
  | §16b body wider than its terrain group (bar 0) | — | 1,532 | **1,417** |
  | files | 3,561 | 3,253 | **2,804** |
  | round trip (write half into a pack COPY) | — | OK | **OK**, 2,804 files, 2,804/2,804 new `OBJECT_DEF`s, 0 rows carrying an elevation, duplicate rows surviving 0 |
  | plan stage, graded sampler, 3 runs | — | 13.53 / 13.52 / 13.53 s | **9.84 / 10.48 / 10.32 s — MET (<= main's)** |
  | `_surface` calls | — | 194,853 (+104,091 vectorised points) | **186,263 (+104,619)** |

  OTHH, same arms: torn seams **639 (342 > 0.3 m) -> 1**, single-
  component resources in >= 2 files **165 -> 1**, §15 carried float
  **0 -> 0**, `footless at datum` 0, files 1,897 -> 1,898, §16b carried
  piece float **200 -> 172** and wide **144 -> 85**, round trip **OK**
  (1,897/1,897 new `OBJECT_DEF`s, 0 rows carrying an elevation), the
  §16a (2) refusal set 21 -> 57.  The ONE
  residue is `Buildings/Fire Fuel/OTHH_Fuel_02_LOD0_007.obj`
  b0<->b1, step +2.70 m: two components `obj8.solid_components`
  reports as SEPARATE share an authored vertex POSITION to the
  millimetre (vertex ids 378/399 and 379/411).  Named, not closed.
* **THE FOUR SITES AFTER** (files / written base spread; live 1.0.320 ->
  before -> after): `HANG3` **10 / 3.51 m -> 6 / 1.90 -> 6 / 1.37**, and
  every file is now a whole number of components (seams 14 -> 0);
  `green-LEMD50` **7 / 11.12 -> 4 / 2.73 -> 1 / 0.00 (bar <= 2 files
  MET)**; `green-STRT4` **53 / 16.29 -> 31 / 10.13 -> 24 / 8.90**;
  `Bridge2` **8 / 11.72 -> 6 / 1.66 -> 5 / 1.73**.
* **THE 11at SITES HELD, AND TWO MOVED THE WRONG WAY** (zero minus the
  design surface under the body's own written geometry, before ->
  after): item 3 `green-TEJ3` **+0.44 -> +0.18**, item 5 **-0.40 ->
  -0.29**, the gate-5 sign **-0.02 -> -0.02**; but the T4 landside deck
  `green-STRT4` **+0.90 -> +1.11** and the T4 roof `Terminal4_48`
  **+1.81 -> +3.26**.  Both are the atom's own cost: those pieces were
  carried bodies the old cut divided THROUGH a welded slab, and a slab
  that stays whole takes one zero over ground that moves under it.
  §16c (5)'s "no piece more than `split_tol_m` below its pier feet" is
  therefore **MISSED** and named.
* **§16c (4) IMPROVED THE WORST CASE AND MISSED THE BAR.**  T2 roofs
  (`TEJ3`/`tej2`/`tej2_teilb`/`LEMD58`/`LEMD50`/`T2CSG`) against the top
  of the named wall geometry directly under them, read in WORLD
  coordinates from the written files: live 1.0.320 **7 of 9 over 0.3 m,
  worst 2.80 m**; before **5 of 7, worst 6.56 m**; after **5 of 7, worst
  0.97 m**.  148 bodies take the new `rests on it` reason.  The bar
  ("within 0.3 m") is MISSED.
* **THE COST OF THE ATOM, NAMED.**  §16a (2)'s refusal set at LEMD goes
  **37 -> 157** footed bodies (20 carried bodies stand over one, was 0),
  because 11ak (2)'s FOOT cut can no longer divide a body authored as
  ONE welded component: such a body's feet genuinely disagree and it is
  honestly mis-anchored.  11ak's twin is AMENDED to read both halves —
  three treads in three components are still cut by their feet, the same
  ribbon welded is written whole and refused.  HANG3's four vault arcs
  are four separate components written at four zeros 1.37 m apart: no
  seam, but adjacent rigid pieces of one resource at different zeros are
  a class §16c does not reach (they do not overlap in plan, so §14 (3)
  never binds them).  Reported for the owner.
* **TWO READINGS CORRECTED IN PASSING** (both §16b (1)'s own sentence,
  both forced by the twins): the FOOTED triangle cut and the CARRIER cut
  now read the same `own_tris` their pre-test measures — a member the
  plan records as ONE part is WRITTEN as the whole object, so a cut over
  the parts' components measured a span it could not act on.
* **SPEED.**  §16c (2)'s first form was two thirds of the plan stage
  (154 M box comparisons in `contact_ground`); bounded to the piece's
  `foot_boxes`, candidates whose hull box it meets, and
  `CONTACT_PTS_MAX` samples, the whole stage came out FASTER than main's
  (13.5 -> 10.2 s).  `comp_of` is a packed-key `searchsorted`, not a
  Python dict.
* **Twins:** `test_no_cut_crosses_a_connected_component`,
  `test_split_obj8_never_assigns_a_triangle_across_a_component`,
  `test_the_carrier_is_what_the_body_rests_on`,
  `test_the_bounded_fallback_reads_the_contact_ground_not_the_median`,
  `test_the_torn_seam_census_reads_the_written_files`; four twins
  AMENDED where §16c supersedes them (the scattered roof, the carried
  roof over two buildings, the carried roof re-cut by its walls, and
  11ak (2)'s foot re-cut — each now authored in SEPARATE components,
  with the welded case asserting the new law).  Suite **1,127 passed /
  1 skipped** (main 1,122 / 1).  `_Staged` moved to
  `airport/placement_record.py` for the 1,000-line law.
* **NOT DONE:** no airport build (§16c needs none); §16c (3) refuted and
  left out; the `--write-pack` arms are pack COPIES and the live pack was
  read-only throughout.

### §16c (6) COMPONENTS IN CONTACT BIND (owner RULINGS 2026-09-12h)

§16c (1) made the connected COMPONENT the atom of every group.  An
exporter's "one solid" is often several components that TOUCH, and
written at two zeros they read as a break: OTHH's
`OTHH_Fuel_02_LOD0_007` carries two components **0.4 mm** apart — under
the millimetre key `obj8.solid_components` welds on (`np.round(v, 3)`)
they are two — and round 1 wrote them 2.70 m apart, the airport's last
seam.

Components of ONE resource bind into ONE RIGID BODY for anchoring —
one zero, the senior component's carrier — when they share a vertex
position within `[placement] contact_eps_m` (2 mm), OR when the REBAKE
PLAN's own ε-contact graph already links their parts.  A bound cluster
is the atom every §16c (1) group is formed over.

**MEASURED (lane `v2atom` round 2, 2026-09-12; branch `claude/v2atom`).**
`_LineCutter.comp_cluster` (union-find over the plan's intra-member
contact pairs and a box-rejected KD-tree pair count), `_comp_blocks`
grouping by cluster, `[placement] contact_eps_m` in
`law/structures.toml` + `law/rebake_schema.py`, wired through
`placement_plan.build_splits` / `placement_write` / `engine_v2` and
`obj8_split_report --contact-eps`.

* **THE BAR, LEMD** (same matched frame; round 1 -> round 2): torn seams
  outside line/arc **0 -> 0**, single-component resources in >= 2 files
  **0 -> 0**, files **2,804 -> 2,776**, §15 carried float **0**, round
  trip **OK** (2,776 files, 2,776/2,776 new `OBJECT_DEF`s, 0 rows
  carrying an elevation, duplicate rows surviving 0), plan stage on the
  graded sampler **8.86 / 9.28 / 9.37 s** (main 13.53), `_surface` calls
  186,263 -> **184,219**, §16b carried piece float 124 -> **122** and
  wide 1,417 -> **1,405**, §16a (2) refusal set 157 -> **169**.  Suite
  **1,129 / 1 skipped**.  The distance test is ONE labelled radius pair
  query over the member's vertices: the first form (a KD-tree per
  component and an n^2 pair loop) was quadratic in a clutter object's
  thousands of components and did not finish OTHH's plan stage in ten
  minutes.
* **THE BAR, OTHH** (round 1 -> round 2): torn seams outside line/arc
  **1 -> 0 — MET**, single-component resources in >= 2 files **1 -> 0 —
  MET**, files 1,898 -> **1,891**, §16b carried piece float 172 -> 175
  and wide 85 -> **76**, §15 carried float **0**, round trip **OK**
  (1,890/1,890 new `OBJECT_DEF`s, 0 rows carrying an elevation).  The
  airport's LAST seam — `OTHH_Fuel_02_LOD0_007` b0<->b1, +2.70 m — is
  exactly the two components 0.4 mm apart, and it is closed.
* **`Terminal4_48` FIXED BY IT.**  Its zero spread **3.58 -> 0.69 m**
  and the owner-site reading `zero - ground under its own geometry`
  **+3.26 -> +0.04 m** (1.0.319 read +1.81): the piece that rode
  `green-STRT4__b11` at a top 3.38 m below it is now bound to its own
  neighbours and takes their zero.  The other 11at sites are byte-equal
  (item 3 +0.18, item 5 -0.29, gate-5 sign -0.02).
* **`HANG3`'s FOUR VAULT ARCS ARE NOT REACHED, AND THE BAR IS REFUTED AS
  WRITTEN.**  Measured pairwise minimum vertex distance between its 7
  components: the arcs stand **1.507-1.853 m** from the two spine
  components and 9.65-65.31 m from each other; and the rebake plan
  records **ZERO** intra-member ε-contacts for this resource (the
  airport has 37,324 contacts in all).  Neither half of §16c (6)
  can bind them: a 2 mm contact tolerance does not reach 1.5 m, and the
  plan's graph has no edge.  Binding them needs `contact_eps_m` >= 1.86
  m, which is a REACH and not a contact — it would weld anything
  standing within two metres across every resource of the pack.  The
  vault stays 6 files at 6 zeros spanning 1.37 m.  NOT FIXED; the
  question is the owner's (a "one resource, one rigid object" rule is a
  different law from contact).
* **THE T2 ROOFS ARE NOT §16c (4)'s TO FIX.**  Attribution: the named
  wall bodies DO plan-overlap every roof and are NOT refused by
  §16a (2) (`ground_off` 0.00-0.08) — they are removed by §16 (3)'s
  FILL gate before the rest-on ranking ever sees them.  `LEMD54`'s
  bodies under the roofs carry `fill` **0.005 / 0.010 / 0.031** and
  `LEMD59`'s **0.031**, against `[placement] carrier_fill_min` **0.2**:
  a terminal's wall RING is a thin loop, and its parts-hull over its
  plan box is one to three per cent.  What the rest-on rule is then left
  to choose between are bodies whose top under the overlap is +2.46,
  +7.93, +8.39, +14.63 m below the roof's base — it picks the nearest
  below, which is what it is for.  Raising or qualifying the fill gate
  is a RULING (it exists so a fence's box cannot carry a zero); not
  changed here.
* **THE `green-STRT4` DECK IS AN INSTRUMENT ARTEFACT, NOT A FLOAT.**  The
  +1.11 m body is FOOTED (6 feet, fill 1.000, not carried, not
  elevated), and its `y_zero` is **-1.668**: its anchor vertex is a
  SKIRT 1.67 m below the object's zero plane.  `zero - ground under the
  geometry` therefore reads the skirt depth, not a float — the body's
  own lowest vertex lands on the design surface at its anchor
  (616.449).  Its real residual is §7's, `ground_off` **0.397 m** over
  0.43 m of authored foot relief: 11ak (2)'s class, which §16c (1) can
  no longer foot-cut because the deck is one welded component.  Not a
  defect to fix here; the §16b `carried piece float` bar should not
  count a footed skirted body at all, which is a census question.
* **THE §16a (2) REFUSAL SET, NAMED** (LEMD round 2, 169 candidate
  bodies; over WRITTEN files with `ground_off > 0.3 m`, basins exempt,
  524 files of which 353 are line segments that §16 (3) bars from
  carrying anyway): **other 97, skirted 69, building 5**.  Worst-off:
  `green-STRT4__b0` 7.16 m (building, 4 feet), `LEMDblast__b1` 7.14
  (line), `Munoza-LEMD50__b2` 5.96 (line), `Terminal4sBlue-STRT4__b1`
  5.08, `green-PKT4__b0` 4.50 (skirted), `Munoza-TWY__b1` 4.16,
  `Cargo-NEWCO__b0` 3.35, `P2CNX__b4` 3.19.  Every one is the same
  class: a body whose FEET are authored over metres of relief on ground
  that barely moves, which 11ak (2)'s foot cut used to divide and §16c
  (1) forbids dividing.
* **THE FILE COUNT, EXPLAINED.**  2,776 files by §6 class: **line_segment
  1,141**, other 1,232, skirted 246, building 166, basin 19.  By
  resource the top two are `grass_FSX-LEMDgrass` **894 files** and
  `Taxisigns-SENRG` **310** — 1,204 files, 43 % of the airport, from two
  line/clutter resources cut by §10's 100 m station law.  The 899
  counterfactual counted SOLID bodies only; the solid half here is
  **1,663**.  Nothing in §16c makes line files: round 1 took them 1,446
  -> 891 seams and the count is §10's, not the atom's.
* **Twins:** `test_components_in_contact_are_one_rigid_body`,
  `test_the_plans_contact_graph_binds_components_whatever_the_distance`.

### §16c (7)-(9) THE FILL GATE GOES, THE RIGID REACH CHAINS, A SKIRT IS NOT A FLOAT (owner RULINGS 2026-09-12j)

**(7) THE FILL FRACTION LEAVES CARRIER CANDIDACY.** §16 (3)'s "a carrier
is a SOLID" stays as a CLASS rule — a line segment, a grass strip, a sign
never carry — and `[placement] carrier_fill_min` is DELETED, not gated.
It was the wrong instrument for that rule: a terminal's wall RING is a
thin loop, and `LEMD54` / `LEMD59` — the walls the T2 roofs rest on,
which overlap every roof and pass §16a (2)'s ground test — fill
0.005-0.031 of their boxes and were struck as carriers before §16c (4)
ranked anything.

**(8) THE RIGID REACH** (`[placement] rigid_reach_m` 2.0).  SOLID
components of one resource whose geometry comes within the reach CHAIN
into one rigid cluster; the cluster is the atom of every group and of the
BODY.  Line objects are excluded (§10 cuts a fence into stations on
purpose).

**(9) A SKIRT IS NOT A FLOAT.** §16b's carried-float bar reads only a
carried body WITH NO FEET OF ITS OWN; a footed body's number is
`ground_off`.

**MEASURED (lane `v2atom` round 3, 2026-09-12; branch `claude/v2atom`).**
Implemented in `law/structures.toml` + `law/rebake_schema.py`
(`carrier_fill_min` deleted, `rigid_reach_m` added),
`airport/placement_carrier.py` (the fill test gone from `carriers_for`),
`airport/placement_census.py` (the fill test gone from the §15 census
population; the §16b float bar skips a footed body),
`airport/placement_cut.py` (`comp_cluster` at the reach, line objects
excluded), `airport/placement_body.py` (THE CLUSTER IS ONE BODY: the
`_bodies_of` groups are unioned by cluster and the PART cut may not
divide one) and `airport/placement_plan.py` / `placement_write.py` /
`auto_patch/engine_v2.py` / `tools/obj8_split_report.py --rigid-reach`.

* **THE SHARED-REPO WRITE, CLOSED FIRST.**  `obj8_split_report.py` armed
  nothing, and round 2's OTHH `--admit-skipped` run created
  `Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text` (3.25 MB)
  and rewrote `o4_dsf_object_positions_+25+051.cache` in the shared repo
  with both lane-local cache env vars exported.  The entry now runs
  inside `harness/shared_repo_guard`'s guard and its before/after audit —
  the ONE implementation `build_airport.py` arms — and every round-3 run
  prints `[guard] shared repo UNCHANGED by this build (full-surface
  before/after snapshot)`.  Proven independently: a file list of
  `/Users/noah/XPTerrainBuilderData/Airport_mod_cache/` (1,523 files,
  name+size+mtime) taken before and after a full guarded OTHH
  `--admit-skipped --write-pack` run is **byte-identical**.  The env
  redirect itself was measured and HOLDS (`airport_mod_cache_root()`
  returns the lane-local dir before and after every engine import); what
  failed was that nothing refused or reported the write, which is what
  the guard now does.  Twin:
  `test_the_report_tool_arms_the_shared_repo_write_guard`.
* **THE BARS, LEMD** (matched frame, round 2 -> round 3):

  | bar | round 2 | round 3 |
  |---|---|---|
  | torn seams outside line/arc (0) | 0 | **0 — MET** |
  | single-component resources in >= 2 files (0) | 0 | **0 — MET** |
  | `HANG3` — the (8) bar | 6 files, zeros spanning **1.37 m** | **3 files, 1.12 m** (the vault arcs and the spines bind; the bar "one zero" is NOT met) |
  | nothing new rides a fence | 0 | **0 — MET** |
  | 11at item 3 / item 5 / gate-5 sign | +0.18 / -0.29 / -0.02 | **+0.06 / -0.29 / -0.02 — HELD** |
  | 12h `Terminal4_48` | +0.04 | **+0.49** (spread 0.69 -> 0.86) |
  | `green-STRT4` deck | +1.11 (23 files) | **+0.14 (19 files, spread 8.90 -> 6.09)** |
  | §15 carried float > 0.5 m (0) | 0 | **0 — MET** |
  | §16b carried piece float (0) | 122 | **107** |
  | §16b wider than its terrain group (0) | 1,405 | **979** |
  | files | 2,776 | **2,174** |
  | round trip | OK | **OK**, 2,174/2,174 new `OBJECT_DEF`s, 0 rows carrying an elevation |
  | §16a (2) refusal set | 169 | **244** |
  | plan stage, graded, 3 runs | 9.3 s | **9.92 / 9.96 / 9.85 s** (main 13.53) |

* **THE RIGID CLUSTERS DO NOT RUN AWAY.**  Five largest cluster plan
  extents at LEMD: **5,157 m / 2,890 m / 2,514 m / 2,271 m / 2,234 m —
  every one of them a SINGLE component** (`Munoza-LEMDzaun`,
  `North_FSX-LEMDzaun`, three `AESlite-LEMD-VOR` markers), i.e. authored
  that way and not chained by the reach.  129 of 7,816 clusters exceed
  300 m, all of that class.  `Terminal4SAT_green-TEJ3`: **9 components ->
  9 clusters** — its panels do NOT chain, which is the bar.
* **THE COST, NAMED.**  `grass_FSX-LEMDgrass` goes 894 -> 458 files: the
  reach chains grass tufts within 2 m into rigid mats.  Reported, not
  judged — the resource reads as a line object per component in places
  and not in others.
* **(9) IS A NO-OP AT LEMD AND IS STILL RIGHT.**  `footed_carried_excluded`
  is **0**: no carried body at LEMD publishes feet, so the bar never
  counted one.  The `green-STRT4` +1.11 m round 2 reported was never in
  the §16b census at all — it was this lane's own site probe reading
  `zero - ground` on a FOOTED body with `y_zero` -1.668.  The census now
  cannot make that mistake, and the probe's number for that body is
  +0.14 m after (8).
* **THE BARS, OTHH** (matched frame, round 2 -> round 3): torn seams
  outside line/arc **1 -> 0 — MET**, single-component resources in >= 2
  files **1 -> 0 — MET**, files 1,891 -> **1,362**, §16b carried piece
  float 172 -> 177, wide 85 -> **74**, §16a (2) refusal set 57 -> 99,
  round trip **OK** (1,361/1,361 new `OBJECT_DEF`s, 0 rows carrying an
  elevation), `[guard] shared repo UNCHANGED`.  The arm is SLOW — the
  three refuted forms did not finish it at all (45 min and counting) and
  the shipped one takes tens of minutes against round 2's ~10; the reach
  costs OTHH more than it costs LEMD, and that cost is not measured as a
  stage time this round.  Owed.
* **THE T2 ROOFS ARE STILL MISSED, AND THE ATTRIBUTION HAS MOVED.**  5 of
  7 over 0.3 m, worst 6.12 m (round 2: 5 of 7, worst 0.97; live 1.0.320:
  7 of 9, worst 2.80) — and it MOVES with every change to the carrier
  set, which is itself the finding: the choice is not pinned by the law.  With the fill gate gone the `LEMD54` bodies ARE
  candidates (`ground_off` 0.08-0.11, overlapping every roof) — and
  §16c (4) still does not pick them, because their top under the overlap
  stands ABOVE the roof's own base plane and "nearest BELOW the base" is
  category 1 for anything above it.  These walls are parapets and upper
  storeys: the roof is let INTO them, not laid on top.  The §16c (5) bar
  (roof base within 0.3 m of the wall TOP) and the §16c (4) rule
  (carrier top nearest below the roof base) are asking for two different
  geometries.  Not guessed at: it is a ruling.
* **THE REACH'S COST, MEASURED AND THEN BOUNDED.**  A radius pair query
  over every vertex of a member returns MILLIONS of pairs at 2 m: the
  LEMD plan stage went **9.3 -> 108-126 s** over 3 runs.  A KD-tree per
  component with an n^2 loop is quadratic in a clutter object's
  thousands of components (it did not finish OTHH in ten minutes).  What
  ships is a SWEEP: the components sorted by the low corner of their
  box, the pairs whose boxes come within the reach walked once, anything
  already unioned skipped, and the trees asked only then
  (`airport/placement_atom.py`, NEW — the §16c atom law lifted out of
  `placement_cut` for the 1,000-line law), and the pair TEST is a
  nearest-neighbour query with an upper bound, not `count_neighbors`:
  counting EVERY pair within 2 m between two dense clouds is billions,
  and it is what left OTHH's plan stage unfinished after 45 minutes and
  LEMD's at 26.3 s.  FOUR forms measured — all-pairs `query_pairs`
  (**108-126 s**), the same vectorised (**~117 s**), a box SWEEP with
  `count_neighbors` (**26.3 s**, OTHH unfinished at 45 min), and the
  sweep with a bounded nearest-neighbour query: **9.92 / 9.96 / 9.85 s**
  over 3 runs against main's 13.53 — the "plan stage <= main's" bar
  **MET**.  `_surface` calls 184,219 -> **141,466**.  A member with more
  than `placement_atom.RIGID_REACH_COMPONENTS_MAX` (64) components keeps
  §16c (6)'s contact binding only — an affordability bound, named.
* **Twins:** `test_the_rigid_reach_chains_solids_and_never_a_line_object`,
  `test_the_16b_float_bar_excludes_a_footed_body`,
  `test_the_report_tool_arms_the_shared_repo_write_guard`; the fence
  twin AMENDED (the fill fraction gone, the CLASS rule kept), and two
  cut twins amended where §16c (6)/(8) supersede them — a contact-bound
  ribbon is ONE rigid body and 11ak (2)'s foot cut can no longer divide
  it, which the twin now reads from both sides.

**MEASURED (lane `v2atom` round 4, 2026-09-12; branch `claude/v2atom`; RULINGS 2026-09-12n).**

* **§16c (4) IS NOW ABSOLUTE DISTANCE** (`placement_carrier._rest_key`):
  the overlapping candidate whose top under the overlap is nearest the
  body's base plane, above or below.  Five of the nine T2 roof bodies
  now rest within 0.36 m of their chosen carrier's top (−0.03, −0.18,
  −0.24, −0.36); four still take one 2.5–14.6 m away.
* **THE T2 BAR IS STILL MISSED: 7 of 8 over 0.3 m, worst 6.12 m**
  (round 3: 6 of 7, worst 6.12; live 1.0.320: 7 of 9, worst 2.80).  The
  rule is satisfied — each roof rests on the nearest-top candidate it
  overlaps — so the residue is the CANDIDATE SET, not the ranking: the
  wall body the eye reads as "under" those four roofs is not one they
  plan-overlap in `stands_over_rank`.
* **ONE MECHANISM TESTED AND REFUTED, REVERTED:** that the wall rings
  were outside the stands-over set because only a body's eight largest
  part boxes are published (`FOOT_BOXES_MAX`).  Raised to 32 the bar
  moved 7 of 8 → 6 of 7 with the worst unchanged at 6.12 m, for a
  larger plan; not kept.
* **THE 11at / 12h SITES ALL HOLD:** item 3 **+0.06**, item 5 **−0.29**,
  gate-5 sign **−0.02**, `green-STRT4` deck **+0.14**, `Terminal4_48`
  **+0.49**; `HANG3` **3 files / 1.12 m**, `green-LEMD50` 1 file,
  `Bridge2` 5 files, nothing rides a fence (**0**).
* **§16c (8) IS BOUNDED BY A CLUSTER SPAN CAP**
  (`placement_atom.RIGID_CLUSTER_SPAN_MAX_M` 1,200 m): a cluster is one
  rigid body no cut may divide, so a chain of 2 m hops that walks a
  terminal makes a body wider than any terrain it can stand on —
  unbounded, the reach chains `OTHH_Terminal_Base_*` into clusters
  spanning 1,042–1,175 m over 3–15 components.  A 100 m cap was measured
  and REJECTED: it broke the sites the reach exists for (`Terminal4_48`
  +0.49 → +3.26, `HANG3` 3 → 5 files).
* **THE REACH IS NOT WHAT COSTS OTHH, MEASURED ON MATCHED ARMS.**  OTHH
  plan stage, same code, graded sampler: **64.33 s** at the 1,200 m cap,
  **64.45 s** at 100 m, **63.46 s with the reach DISARMED**.  The reach
  accounts for **0.9 s**; deleting it would not bring OTHH under the
  45 s bar, so it is KEPT.  The **≤ 45 s bar is MISSED at 64 s** and the
  cost is elsewhere in the stage (344,838 `_surface` calls at OTHH
  against LEMD's 141,306).
* **LEMD plan stage 10.31 s** against main's 13.53 — MET.
* **OTHH, MEASURED TO COMPLETION UNDER THE GUARD** (round 3 -> round 4):
  torn seams outside line/arc **0 — MET**, single-component resources in
  >= 2 files **0 — MET**, §15 carried float **0 — MET**, files 1,362 ->
  **1,376**, §16b carried piece float 177 -> 183, wide 74 -> **70**,
  round trip **OK** (1,375/1,375 new `OBJECT_DEF`s, 0 rows carrying an
  elevation), `[guard] shared repo UNCHANGED`.
* **LEMD, ROUND 4**: files **2,171**, seams **0**, single-component
  **0**, §15 carried float **0**, round trip **OK** (2,171/2,171),
  guard **UNCHANGED**.
* **THE §16a (2) REFUSAL SET (244), BY CLASS**, read over the written
  files (`ground_off` > 0.3 m, basins exempt; 358 files, of which 114
  are line segments §16 (3) bars from carrying anyway): **other 158,
  skirted 76, building 10**.  Worst-off: `LEMDblast__b1` 7.14 m (line),
  `Terminal4sBlue-STRT4__b1` 5.08, `LEMD03__b6` 4.98, `Munoza-LEMD50__b1`
  4.92 (line), `green-PKT4__b0` 4.50, `Munoza-TWY__b1` 4.16,
  `Munoza-LEMD69__b12` 3.95 (140 feet), `Cargo-NEWCO__b0` 3.35,
  `Munoza-LEMD03__b5` 3.32, `P2CNX__b3` 3.19 — every one the same class:
  feet authored over metres of relief on ground that barely moves, which
  §16c (1) forbids foot-cutting.
* **Merged main `30a61c9f`** (§27, the mesh-sampler grid, `v2_rebake_replay
  plan`); `tools/INDEX.md` resolved keeping BOTH rows.  Full twin set
  **1,169 passed / 1 skipped**.

### §16c (7)–(8) The unit binds by contact; the rest-on carrier is not refused for its own ground (Fable, 2026-09-12; RULINGS 2026-09-12q)

Scout `v2t2roofs` on main `fe5d7a87`: the four T2 roofs that miss are NOT a plan-overlap
predicate (widening it — "inside the hull box" 72 carriers changed, "any hull-box
overlap" 121 — fixes none of them). Three causes: `tej2__b0/b1` rest on `P2PK__b0`
(|Δ| 1.45 m against 14.64 for the runner-up, only two candidates overlap) and §16a
(2) REFUSES it for its own `ground_off` 0.42 > 0.30 — the ranking runs before the
refusal, so the body it rests on is dropped and the next one taken; `LEMD48__b0` /
`LEMD47__b1` have NO candidate at their height because `LEMD47`/`LEMD48` are one
thing (114 ε-contacts between them in the rebake plan) and §16c (6) binds only
within one member, with elevated bodies excluded from their member's coarsening;
and the block's separation is the SPREAD — the T2 walls are separate footed bodies
each at its own low-side ground (building bodies 602.89 … 603.35, `LEMD47` alone at
three zeros 1.19 m apart), and every roof inherits whichever the ranking hands it.
The plan records 175 cross-member ε-contacts among the T2 resources.

7. **THE UNIT BINDS BY CONTACT.** §16c (6)'s contact binding is unit-wide: bodies
   of one UNIT in ε-contact (the rebake plan's cross-member contact pairs, and the
   rigid reach within `rigid_reach_m`) form ONE rigid cluster, and an elevated body
   joins its own member's footed cluster. The cluster's zero is its senior FOOTED
   body's anchor (largest footprint; §9 low side); every member rides it at the
   authored offset. `RIGID_CLUSTER_SPAN_MAX_M` (1,200) bounds the chain. A terminal
   authored as walls + roofs + skylights in contact is one building.
8. **THE REST-ON CARRIER IS NOT REFUSED FOR ITS OWN GROUND.** §16a (2)'s refusal
   yields when the candidate's top under the overlap meets the carried body's base
   within `split_tol_m`: it is what the body rests on, and its mis-anchoring is its
   own residual (reported under the refusal set), not a reason to hand the body to
   something 14 m away. Refusal stays for every other candidate.
9. **BARS (lane `v2unitbind`)**: T2 building bodies within 150 m of 40.4660017,
   −3.5694045 at ONE zero (spread ≤ 0.3, today 0.46; `LEMD47` one zero, today 1.19
   apart); every T2 roof within 0.3 m of the wall it rests on (today 4 of 9 at
   2.85–20.6 m); `tej2` on `P2PK`; the 11at / 12h / 12o sites held (green-TEJ3,
   gate-5, `Terminal4_48`, the deck, `HANG3`); torn seams 0; §15 carried float 0;
   OTHH seams 0 and its plan stage not worse than 64 s; collateral quoted airport-
   wide (carriers changed, zeros moved, largest move, cluster count and the five
   largest spans); files; round trip; suite.

**MEASURED (lane `v2unitbind`, 2026-09-12; branch `claude/v2unitbind` from main
`be882755`).**  Implemented in `airport/placement_atom.py` (`RigidNode`,
`unit_clusters`, `unit_rigid`, `bind_unit` and `UNIT_CLUSTER_SPAN_MAX_M`),
`airport/placement_carrier.py` (§16c (8)'s `_rests_on` / `_admit` inside
`carriers_for`) and `airport/placement_plan.py` (the unit's own ε-contact pairs;
pass 3 takes the cluster's senior INSTEAD of the carrier search for a bound
body).  Matched arms on the 1.0.320 rebake plan + `LEMD.graded.json`,
`--admit-skipped` on the live pack read-only, the write half into APFS clones,
`[guard] shared repo UNCHANGED` on every run.

* **§16c (8) ALONE FIXES NOTHING AT `tej2`, AND IS KEPT.**  `P2PK__b0`'s top
  stands **1.45 m** from `tej2`'s base, not within `split_tol_m` 0.3, so the
  yield never reaches it; what carries `tej2` onto `P2PK` is (7).  The rule
  still fires **129 searches** at LEMD on its own (106 in the shipped
  combination, 88 at OTHH) and takes files 2,171 → 2,160; the yield is counted
  as `carrier_refused_zero_off_ground_yielded_rest_on` beside the refusal it
  relieves.
* **THE SITE, REPRODUCED** (main `be882755`, this instrument): `tej2__b0`
  **+2.85** on `LEMD03__b0`, `tej2__b1` **+14.64** on `LEMD38__b27` (both with
  `P2PK__b0` refused at `ground_off` **0.42**), `LEMD48__b0` **−3.90**,
  `LEMD47__b1` **+20.57**; `LEMD47` at three zeros **1.19 m** apart; the T2
  named block within 150 m of 40.4660017, −3.5694045 spread **1.365 m** over 12
  bodies (building class 0.325 over 8); `LEMD47`/`LEMD48` **228** cross-member
  ε-contacts, **164** among the named T2 resources, 12,408 cross-member in the
  plan.
* **THE BARS, LEMD** (before → after): torn seams outside line/arc **0 → 0 —
  MET**; single-component resources in ≥ 2 files **0 → 0 — MET**; §15 carried
  float **0 → 0 — MET**; §14 footless at datum / on ground / basin split
  **0/0/0 → 0/0/0**; §16 rows on the datum **0 → 0**; round trip **OK**
  (2,148/2,148 new `OBJECT_DEF`s, 0 rows carrying an elevation); files
  **2,171 → 2,148**; §16b carried piece float **108 → 117** (worse, named),
  wider than its terrain group **982 → 973**; plan stage on the graded sampler
  **9.70 / 9.75 / 9.93 s** against main's **10.09 / 11.12 / 24.63 — MET**.
* **THE T2 BLOCK, AND WHAT IS STILL MISSED.**  Named-block spread
  **1.365 → 0.537 m** (bar ≤ 0.3, **MISSED**); building class 0.325 → **0.312**;
  `LEMD48` **one zero — MET**; `LEMD47` three zeros → **two, 0.804 m apart**
  (**MISSED**); `tej2`'s contacting piece rides **`P2PK__b0`** — the bar's own
  sentence — while its two other terrain pieces, which the plan records no
  contact for, keep `LEMD03` (+2.86) and `LEMD38` (+14.64).  Roof bodies whose
  reason is still `rests on it` and whose authored gap exceeds 0.3 m: **7 of 12
  → 5 of 7** (worst 20.57 → 15.96).  NAMED FOR THE OWNER: the "within 0.3 m of
  the wall it rests on" reading is an AUTHORED number for `LEMD47`/`LEMD48` —
  their roofs are authored 5–9 m above the top of the only wall geometry under
  them (`LEMD47__b0` top 4.66 against a roof base of 9.62), so no carrier
  choice can make it 0.3; what (7) can do, and does, is put the roof and the
  walls at ONE zero.
* **THE 11at / 12h / 12o SITES HELD**: item 3 **+0.06 → +0.05**, item 5
  **−0.29 → −0.27**, gate-5 sign **−0.02**, the T4 deck **+0.14**, `HANG3`
  **−0.81** (7 → 6 files), and `Terminal4_48` **+0.49 → −0.11** — improved by
  the senior rule below.
* **THE CLUSTERS, AND THEIR BOUNDS.**  LEMD **136** clusters of more than one
  body, five largest plan spans **298.9 / 295.7 / 293.0 / 292.0 / 289.4 m**
  (28 / 22 / 8 / 176 / 14 bodies); non-senior bodies bound: **168 footed, 733
  elevated**.  OTHH **187** clusters, largest spans **299.7 / 299.7 / 299.5 /
  299.4 / 299.0 m**; **386 footed, 10,119 elevated**.  `UNIT_CLUSTER_SPAN_MAX_M`
  is **300 m** and is a measured constant, not a ruled key: at
  `RIGID_CLUSTER_SPAN_MAX_M` (1,200) the unit graph made clusters **1,190 m**
  wide that collapsed **10.46 m** of honest terrain reading onto one zero
  (`LEMDzaun` stations, `LEMDgrass` mats), and at **100 m** the whole T2 fix is
  lost (`LEMD47__b1` back to +20.57, `tej2__b1` to +14.64) exactly as 12o's
  100 m cap broke `Terminal4_48`.
* **THE SENIOR IS §9's, THEN THE FOOTPRINT.**  Three rules measured: the hull
  BOX area gave the T2 block 0.568 m and `Terminal4_48` **+0.75** (a KIOSK whose
  parts are scattered over the terminal took the cluster); the true FOOTPRINT
  (part-box area) gave `Terminal4_48` −0.11 and the block **1.200**; the most
  GROUND-CONTACT VERTICES then footprint — which is `senior_of`'s own seniority
  — gives the block **0.537** and every named site held.  That is what ships.
* **THREE MECHANISMS REFUTED AND DELETED.**  (i) Restricting an elevated body's
  candidate set to the candidates it TOUCHES: `tej2_teilb` −0.24 → **−11.46**,
  `LEMD58` −0.18 → **−11.79** — a body touches things it does not rest on.
  (ii) A contact TIER ahead of §16c (4)'s rest-on ranking: the same class of
  regression.  (iii) Ranking a body's own member's candidates first inside
  `carriers_for`: superseded by the cluster, which answers "what is it part
  of" instead of "what does it stand over".  All three are gone from the tree.
* **TWO GUARDS THE MEASUREMENT FORCED.**  A cluster senior must READ A SURFACE
  (an off-sheet anchor put `Cargo-EAT` 599 m down onto its authored row), and
  a LINE object or a BASIN body never binds (§10's stations each read their own
  ground; §14 (2) makes a pit's zero its rim — bound, LEMD03/36/85 split into
  **8 torn seams and 3 basin splits**).  Two FOOTED bodies of one member are
  never unioned by the member rule either: they were cut apart because the
  ground under them differs, and unioning them moved `Terminal4-LEMD01`'s two
  bodies **20.5 m** onto one zero.
* **THE COLLATERAL, AIRPORT-WIDE** (keyed by part ids, never by file name — a
  file's index is reassigned when the body count moves): **175 carriers
  changed, 187 zeros moved**, largest real move **7.93 m**
  (`Terminal4_green-PKT4`'s elevated body from `LEMD02__b6` to `STRT4__b8`),
  then 4.28 / 3.88 / 2.09 m; two bodies moved **+565 m** OFF their authored
  datum onto real ground (`Munoza-LEMD78` / `-LEMD76`, an improvement).
* **THE BARS, OTHH** (matched before/after arms, both under the guard): torn
  seams **0 → 0 — MET**, single-component resources in ≥ 2 files **0 → 0 —
  MET**, §15 carried float **0 → 0 — MET**, files **1,376 → 1,337**, §14
  footless at datum **5 → 4** and basin split **1 → 1** (both PRE-EXISTING,
  neither made worse), §16b carried piece float **183 → 163**, wider **70 →
  65**, round trip **OK** (1,336/1,336 new `OBJECT_DEF`s), `[guard] shared repo
  UNCHANGED`.  Plan stage on the graded sampler, matched arms on this machine:
  **73.2 / 83.4 / 84.2 s** against main's **68.6 / 77.2 / 82.4** — the cluster
  pass costs OTHH a few seconds inside the noise, and BOTH arms are over 12o's
  64 s figure today, so the ≤ 64 s bar is **MISSED on both sides** and the
  regression is not this round's.  The unit pass was bounded once for cost: a
  member with ONE footed body unions its elevated bodies without the
  plan-overlap loop (OTHH publishes 49,793 elevated bodies), which took it from
  87–93 s to 73–84 with the plan byte-identical.
* **Twins:** `test_the_unit_binds_by_contact`,
  `test_a_cluster_never_grows_wider_than_a_building`,
  `test_a_line_object_and_a_basin_never_join_a_unit_cluster`,
  `test_the_rest_on_carrier_is_not_refused_for_its_own_ground`; the footless-deck
  twin AMENDED (the deck and the terminal are in ε-contact, so the reason is now
  §16c (7)'s binding onto the same carrier at the same zero).  Suite **1,173
  passed / 1 skipped** (main 1,169 / 1).
* **NOT DONE:** no airport build (§16c needs none); the ≤ 0.3 m block-spread and
  `LEMD47`-one-zero bars are MISSED and named above; `tej2`'s non-contacting
  pieces are unchanged; the rigid REACH is NOT extended across members (only the
  plan's ε-contact graph and the member rule bind a unit — the cross-member
  reach was not measured and is owed); no `tools/INDEX.md` row changed (no tool
  gained or lost a flag).

**MEASURED (lane `v2reach`, 2026-09-12; branch `claude/v2reach` from main
`5a7b325d`; owner RULINGS 2026-09-12am (1)).**  Matched arms on the 1.0.320
rebake plan + `LEMD.graded.json`, `--admit-skipped` on the live pack read-only,
the write half into APFS clones, `[guard] shared repo UNCHANGED` on every run.

* **THE SITE, ATTRIBUTED — AND IT IS NOT THE REACH.**  `LEMD47` is written at
  two zeros because §16c (7)'s rule (a) — an ELEVATED body joins its own
  member's footed cluster — **never fired at all**.  `bind_unit` built every
  `RigidNode` POSITIONALLY and the dataclass declares `footprint_m2` BEFORE
  `footed`, so every node read `footprint_m2` **True** and `footed` its own
  area: a member's `feet_i` held all 114 of `LEMD47`'s bodies, not one was
  "not footed", and no union was ever made by (a).  Only the ε-contact graph
  bound anything, and `LEMD47`'s footed walls (parts 929/931/961/964, 16 feet)
  carry **ZERO** recorded contacts — all 114 with `LEMD48` are on its ELEVATED
  parts.  Measured plan distance from those walls to the nearest other body of
  the unit: **0.000 m** (its own elevated parts, `LEMD48`, `LEMD49`,
  `LEMD38__b27` all overlap it in plan), so no reach length was ever the
  question.  The seniority tie-break was inert for the same reason
  (`_area` returned 1.0 for every footed candidate): what shipped at 12z was
  "most feet, then the low side", not "then the footprint".
* **THE FIX IS THE FIELD ORDER PLUS THE RULE'S OWN DISTANCE TEST, AND IT
  MEETS THE OWNER'S BAR.**  Every field is named at both construction sites,
  and rule (a) picks the footed body of the member the elevated body STANDS
  OVER (largest plan overlap), else the NEAREST within `coarsen_reach_m`
  (100 m).  Both halves of that are measured: 12z's one-footed FAST PATH
  unioned with no test at all — dead while the field order was wrong, and the
  moment (a) lived it broke §15 (1)'s own twin
  (`test_a_roof_resource_rides_the_walls_of_ANOTHER_resource`: a member's
  ground body 250 m from its roof, LEMD's `LEMD38` +6.11 m) — while a strict
  OVERLAP test left `LEMD47` at **two zeros 0.491 m apart**, because its roof
  pieces stand BESIDE its walls (0-12 m), not over them.
* **THE BARS, LEMD** (main `5a7b325d` → this branch): `LEMD47`
  **two zeros 0.804 m apart → ONE (603.619) — MET**; `LEMD48` one zero, now
  the SAME one; T2 named-block spread **0.537 → 0.474 m — MET** (bar ≤ 0.5),
  building-class spread 0.474 → **0.385**; the 11at / 12h / 12o / 12z sites
  HELD (item 3 **+0.05**, item 5 **−0.27**, gate-5 sign −0.02 → **+0.04**,
  T4 deck **+0.14**, `Terminal4_48` **−0.11**, `HANG3` **−0.81** / 2 files,
  `Bridge2` 6 files, `green-LEMD50` 1 file, and
  `Terminal4SAT_green-TEJ3` **5 files / 5 zeros, byte-equal — its panels do
  not chain**); torn seams outside line/arc **0 → 0 — MET**;
  single-component resources in ≥ 2 files **0 → 0 — MET**; §15 carried float
  **0 → 0 — MET**; §14 footless at datum / on ground / basin split
  **0/0/0 → 0/0/0**; §16 rows on the datum **0 → 0**; §16b carried piece
  float **117 → 101**, wider than its terrain group **973 → 980** (worse by
  7, named); files **2,148 → 2,114**; round trip **OK** (2,114/2,114 new
  `OBJECT_DEF`s, 0 rows carrying an elevation); plan stage on the graded
  sampler **9.22 / 9.29 / 9.30 s** against main's **9.81 / 9.86 / 9.85 —
  MET** (bar ≤ 10.3).  `[guard] shared repo UNCHANGED` on every run.
* **THE CLUSTERS.**  LEMD **211** clusters of more than one body (12z: 136),
  five largest plan spans **299.3 / 298.9 / 298.4 / 297.8 / 297.3 m** — every
  one inside `UNIT_CLUSTER_SPAN_MAX_M`; non-senior bodies bound **192 footed,
  1,329 elevated** (12z: 168 / 733 — the difference is rule (a) working).
  OTHH **215** clusters, five largest **300.0 m** ×5 (164 / 221 / 1,541 /
  1,161 / 111 bodies), **403 footed, 22,932 elevated**.
* **THE COLLATERAL, AIRPORT-WIDE** (keyed by part ids, never file name):
  **93 carriers changed, 91 zeros moved**, largest real move **1.367 m**
  (`OldTerminal_FSX-TECH`, 601.308 → 602.676), then 1.148 / 1.148 / 1.137 ×3
  / 1.124 / 1.074; one body moved **+602 m** off its authored datum onto real
  ground (`Cargo-LEMD64`, an improvement).
* **THE BARS, OTHH** (matched arms under the guard, main → this branch): torn
  seams **0 → 0 — MET**, single-component **0 → 0 — MET**, §15 carried float
  **0 → 0 — MET**, files **1,337 → 1,252**, §16b carried piece float
  **163 → 126**, wider **65 → 75** (worse by 10, named), §14 basin split
  **1 → 1**, §14 footless at datum **4 → 5** — one WORSE on a bar already
  violated, named: an elevated body that used to take a carrier now takes
  neither a cluster nor one.  Round trip **OK** (1,251/1,251 new
  `OBJECT_DEF`s), `[guard] shared repo UNCHANGED`.  Plan stage on the graded
  sampler, this machine, same hour: **57.6 / 58.0 / 58.3 s** against main's
  **61.5 / 59.9 / 60.0** — MET.
* **THE CROSS-MEMBER RIGID REACH IS REFUTED AND DELETED** (the code is in
  `claude/v2reach` `70776af7` and its revert; the record is here).  Solid
  bodies of different members chaining within `rigid_reach_m` was implemented
  twice and measured three ways on the same frame:

  | arm | T2 block spread | carriers changed | LEMD plan stage |
  |---|---|---|---|
  | main `5a7b325d` | 0.537 | — | 9.8-9.9 s |
  | field order + (a)'s distance test (SHIPPED) | **0.474** | 93 | **9.2-9.3 s** |
  | field order + reach, PART BOXES | 1.548 | 254 | — |
  | field order + reach, AUTHORED VERTICES | 1.949 | 137 | — |
  | ... and no footed↔footed union | 0.875 | 100 | **67.1-67.9 s** |

  (the three reach arms were measured against the FAST-PATH form of rule (a),
  whose own numbers are `LEMD47` one zero, block 0.537, 66 carriers — the
  arm the twin above then refuted)

  The mechanism, named: a 2 m chain walks a terminal's APRON.  At LEMD it put
  `AES_SAFE09__b16/17/19/20`, `PLANK__b3`, `TECH__b9/10/11`, `YETWY__b9/10`,
  `TWY__b3`, `LEMD60__b15` and the terminal bodies beside them onto ONE zero
  **1.24 m below the block** — eleven FOOTED bodies, each of which had read
  its own ground, collapsed onto the one with the most feet.  Forbidding
  footed↔footed unions (12z's within-member veto, extended) halves the damage
  and does not remove it, and the reach still costs the LEMD plan stage
  **6.8x** (67 s against 9.9, bar 10.3).  Both halves of the bar — "T2 block
  spread ≤ 0.5" and "nothing else worse than 0.5 m that was under it" — are
  MISSED by every arm of the reach and MET without it (0.474).  A
  cross-member reach therefore needs a rule that is not distance: what §16c
  (7) is FOR is a body with no ground of its own, and the ε-contact graph plus
  rule (a) already reach that class.  The owner's call.
* **Twins:** `test_an_elevated_body_joins_its_own_members_footed_cluster`
  (both halves: `unit_rigid` directly, and one member with a footed part and
  an elevated part over it through `build_splits` — it FAILS on main
  `5a7b325d` and passes here); the four §16c (7)/(8) twins AMENDED to name
  every `RigidNode` field, since building them positionally is what let the
  defect through; and §15 (1)'s
  `test_a_roof_resource_rides_the_walls_of_ANOTHER_resource` is what caught
  the fast path — it is the distance test's own witness and is unchanged.
  Suite **1,207 passed / 1 skipped**, twice (main 1,206 / 1).
* **NOT DONE:** no airport build (§16c needs none);
  `tej2`'s non-contacting pieces are unchanged; the T2 roofs' authored 5-9 m
  gap is unchanged (12z's reading stands); no `tools/INDEX.md` row changed (no
  tool gained or lost a flag).

## RULINGS

## 2026-09-13r — v2wallplate MERGED (a16431b9, lane 35db07fc): §33 — every screened resource named (182 → 184 named refusals + 1 plate refusal; the four suppressed prefixes gone); the THIN-PLATE WALL class (`airport/thin_plates.py`, `law/tunnel_object_schema.py`; two gates the measurement forced — a span CEILING at `least_skirt` (else a 1,035 × 557 m cargo terminal is a "plate") and an ALONG-AXIS run test (else a 750 × 89 m slab claims seven bores it merely crosses) — recorded in the law file, accepted); item 5's mouth at the object's north end 40.4987906, −3.5849926 (moved 83.9 m), 25.1 m wide, axis on the object's centre (0.0 m); item 6's mouth ground 610.23 → 607.01, the ramp 36 → 144 m climbing monotonically to the DEM (rim 0.24 m ≤ 0.3); 46 of 50 LEMD tunnels byte-identical; OTHH 0 plate mouths, 0 crest caps (its 9 object + 73 wall corridors untouched); one LEMD build (355 s, ledger 024bfdf4297b, optimal; census 3,573 / 1,143 → 3,588 / 1,178, cockpit motion 2 → 1, visual 0). §33 (3) implemented as a CAP `crest = min(DEM(mouth), approach ground + bore_datum_m)` — the literal trigger fired on every ordinary portal (accepted, the spec text yields to the measurement). ITEM 9 MISSED: the decks went from 2.77 m BELOW the apron to 2.0–2.1 m ABOVE it — the deck face is clipped 19.2 m short of the mapped way's east end and the end reads the DEM (606.10) there, not the apron's solved value (606.60); a profile over the face's extent made it worse because THE DECK RING'S VERTICES ARE THE CORRIDOR RIM'S (one node carries both ways); two refinements owed to `v2rampwalk`: read the end's ground by walking the mapped road to the first governed cell (§34 (1)'s route reading) and rule the rim/deck vertex coupling. `Bridge2.obj` / `LEMD50.obj` are DRAPED object plates (their top an offset over the solved ground, not a datum) — RULED: a draped deck plate rides the terrain deck the mesh gives it; the terrain deck is what must be right (item 9), no object re-seat. Suite 1,167 / 1 twice. Three pre-existing v1 reds unchanged (`test_tunnel_portal_fidelity::TestClearanceAnnulus`, `test_object_anchor::test_kclt_eight_bake_pool_end_to_end`, `test_tunnel_ramp_run_merge::TestItIsNotAPostPass` — owed).

## 2026-09-13k — OWNER READ OF OTHH (verbatim): "Most of the bridges are coming apart and seated wrong, With single layer bridges over water we should be seating the top deck to align with the ground and let the feet land where they may. The tunnel walls are now seating above ground, where before, and as they should, be creating the tunnel ramp walls, with their tops flush with terrain."

* Two REGRESSIONS against the seat era, both in classes the seat had special datums for: (a) object BRIDGES — the seat's `deck_top` datum (RULINGS R12, memory `othh-bridge-deck-datum-r12`: the deck top at the ground, the feet where they land) — the owner restates it as law: a single-layer bridge over water seats its TOP DECK to the ground; the feet land where they may; (b) TUNNEL WALL OBJECTS — the seat's `DATUM_PLATE` (`[tunnel.object] plate_datum`: the crest plate = ground at the band; RULINGS 2026-09-05n) — the walls' tops flush with the terrain, forming the ramp walls; today they stand above ground. §8 retired the seat (12v) and the placement path anchors these bodies like any other (low-side foot / carrier) — the two datums did not cross over. Scout `v2othh1o` attributes (which bodies, their anchors now vs the surviving `deck_datum_z` / plate datum, the class counts at OTHH) before the law; the products are the owner's latest OTHH build (check provenance).

## 2026-09-13n — ATTRIBUTED (scout `v2othh1o`) and RULED (Fable, spec §16e): OTHH's bridges are NOT torn (1 seam airport-wide) — they come apart because half of each stands over the canal (water datum 0.00) and half on land (3.96), piers of one solid take per-pier zeros (3.2 m spread in `Bridge_02_CLUTTER_007`), and the rest-on ranking inside a four-bridge unit picks carriers on OTHER bridges; the seat era had never seated them (rigid at authored y). The tunnel walls: §14 (2)'s rim anchor assumes the authored zero IS the rim (`plate_y` < 0, floor-plate basins) — OTHH's nine walls carry the CREST plate `plate_y` +5/+9.55/+10 → crests +5 … +20 m over the rim; `Member.deck_datum_z` / `deck_ends` / `plate_stations` / `plate_y` and `reseat_expect_m` are stamped and READ BY NOTHING — §8 deleted the executor and its byte-identity proof ran at LEMD, where no wall object is admitted. LAW §16e: the crest plate is the datum (`y_zero = plate_y` at a wall-band station; byte-identical for basins); the deck top is the datum of a single-layer span over water (`zero = ground at the end lines − deck_top_y`, feet free); a bridge is one rigid assembly (its family rides the deck, never another bridge). Lane `v2othhdatums` (Opus). Instrument: `seat_feet_census --mesh` bbox axis order broken (lat/lon swapped) — fixed in the lane.

## 2026-09-15ax APP 1.0.341 BUILT (f4bac3d4, engine 1.50.1788, main 7341372b) on the owner's word ("Build 341 for me to test") — bundled: solver qp, defect floor 0.10, bank OFF, pads OFF, mouth_pair_m 100, parapet_max_width_m 3.0; NOT in it: v2vmmcshore r6/r7 (the deck rule §34 (12) (4), merged to main right after at 347c4552), v2channel. v2vmmcshore r7 MERGED: both behaviours kept in structure_deck (`deck_intervals(..., bores, witness, plates)`), structures.py at 1,000 lines, suite 1,696 green twice on the branch; dry pairs VMMC 13 / 1, LEMD 56 / 5, OTHH 44 / 1; `-6288` centred on Bridge2's pair (span 20.6 vs inner 20.37 m, 0.23 ≤ 0.3)

WHAT THE OWNER READS IN 1.0.341 — LEMD: item 5 mouth 5.07 m deep; the
road between the mouths (−5944) graded at the cap; item 7 trench 31–33
m from the taxiway kerb (beyond the code-E strip; the runway-strip
residual stands — 15y-1); ramps graded along their axis; items 3/4
inside Bridge3's wall pairs (item 4's top 7 m short of the pair's
outer end); item 1 the deck centred on the parapets (from v2objcut r3);
item 2 the garage STILL floats (pads OFF — the airside re-noding
question). VMMC (r1–r3 only): the sea wall / quays, no zone band over
the sea, no taxiway cut; the seafront corridor STILL carries decks in
1.0.341 (the witnessed-below-grade rule is in the next build) — read
the shore, not the tunnel line. VHHH: all five shells cut to their
authored floors and outlines (tunnel5 the owner's site); the VHHH pack
in the mod cache carries a lane rebake (15av) — the owner's app tile
build rebakes from .anchor_bak. Also: LGAV no longer crashes the
object stage; schema-stale road layers refuse by name; the road-layer
refreshes done today. The two LEMD decks lost by the deck rule
(`-5305`, `-15293`) are NOT in 1.0.341 (they still hold their
trenches there) — a 1.0.342 item.
15ax addendum: suite ON MAIN after the v2vmmcshore r7 merge (347c4552): 1652 passed, 1 skipped, 42 warnings in 66.05s (0:01:06).

## 2026-09-17u scout `lemdobjects` REPORTED (report `docs/briefs/lemdobjects-report.md`): LEMD T4 — the unit FORMED and seats 64 bodies at 614.77, the single lowest vertex of pad `building45` 590 m away (§16g (10) (9) (2) low side over the WHOLE pad ring; `pad_plurality` keeps the LAST face of a five-face ref), 1.0–1.9 m under apron `pav12`, while `Terminal4_05` b5 / `_56` sit OUTSIDE the unit at 616.96 — 2.37 m inside one building; Bridge2 parapets — NO law reads an emitted `bridge_deck:*` face in the object stage; two owner intent questions

* Item 4: every body at zero plane 614.77 = the 45 members of `fu:25:983@cluster_pad` + 19 carried (`family_of` 64); the reasons already print the error ("own ground +0.42…+2.24 m", all positive, median +1.26). `plan_unit_datums` takes `min(p.z)` over the entire ring of ONE `PadRing` (`footprint_unit.py:589`, `pad_between_aprons`); `building45` is FIVE faces (25,928 m² face 162 min 614.77 / median 615.17; face 1035 72,620 m² min 615.18) spanning 40.4883–40.4943 — the T4 main block, 250–600 m from the owner's points — and `pad_plurality` (`placement_family.py:543`, twin `anchor_rule.py:266`) stores the LAST face matched per ref, so the datum is decided by iteration order (0.41 m swing). The unit is 1,216 × 516 m; the pad is welded to `pav3` (614.77 is a shared vertex) and agrees with its own aprons — the pad is not losing to the apron; the ONE plane is carried 600 m to a different apron 1–1.9 m higher. The pack: every T4 resource on ONE row (−3.564788376, 40.492764363), no elevation, 0 MSL/AGL — the LSGG shared-datum class. `footless_own_ground` bodies (AESlite VOR) are 0.3 m ABOVE the apron, not the submerged ones. Related to HECA T3 (17s) but the other half: at HECA the unit never formed; at LEMD it formed with the wrong plane AND part of the terminal stayed outside it.
* Item 5: `Bridge2.obj` (one authored row, no elevation) → 5 bodies from 3 components; north wall = component 0 split into a FOOTED piece b0 (50 feet, "line segment 1/2: mid-foot", 611.52, its 125 m box running west onto the `tunnel_ramp` face that climbs to 611) and an ELEVATED footless remainder b2 ("footless_own_ground", 605.96) — 5.56 m apart; south wall = component 1 → b3/b4, footless, boxes straddling deck and trench, the MEDIAN ground under them lands on the `tunnel_ramp` floor 599.30. The deck face `service_road bridge_deck:-6288` (605.60..609.47; both owner points are its ring vertices at 606.98 / 606.19) is READ BY NOTHING in `airport/` (`placement_read.py:51-52` publishes only `building` faces and `structure_rim` breaklines); `deck_kind ""`, `plate_y None` → §16e's datum branch (`anchor_rule.py:324/658`) returns None; `footless_own_ground` (`placement_plan.py:299`) and `segment_anchor` (`placement_cut.py:727`) never reach `anchor_of` at all. History: the five-body split and the N/S pairing are unchanged since 1.0.340 (15h); RULINGS 13r ruled Bridge2/LEMD50 DRAPED plates ("no object re-seat" — the deck plate, not the parapets); 15ax moved the DECK onto the parapets' span — the deck was fixed, the walls never re-seated, which is why the gap shows now.
* FIX SHAPES (not implemented): item 4 — **(A)** read the low side LOCALLY (pad vertices within reach of the body's own contacts, or the shared-edge subset the `:577-587` comment proposes), amends §16g (10) (9) (2); **(B)** a unit member never seats below the graded AIRSIDE surface under its own footprint (`max(unit_datum, own_ground − ε)`, `footprint_unit.py:705-707`) — BREAKS §16g rigidity → OWNER INTENT; **(C)** `pad_plurality` folds every face of a ref before min/median — a pure defect, `anchor_rule.py` blast 21 importers, touch last. Item 5 — **(D)** a body whose footprint touches an emitted `bridge_deck:*` face takes that face's z at its own station BEFORE any foot/own-ground/line-station reading: a NEW REGION entering the object stage → consumer census at spec time (30l), amends §16e, and needs the owner to say 13r covered the plate not the parapets → OWNER INTENT; **(E)** narrow/partial: an elevated footless remainder takes its footed sibling's zero (fixes b2, not b3/b4). Replay: `tools/obj8_split_report.py` on the shipped `o4_v2_rebake_LEMD.json` + `LEMD.graded.json` (no mesh); the only LEMD mesh on disk is 2026-08-27 (unmatched — say so if used). Instruction mismatch reported: `tools/INDEX.md` absent at the repo root the CLAUDE.md names; the index is `Ortho4XP/tools/README.md` + `tools/docq.py index`.
* OWNER INTENT QUESTIONS (17u-1) T4: with the pad datum now MEDIAN (17t) T4 still sits 0.8–1.4 m under `pav12` at the owner's points — does a 1,216 m footprint unit stay ONE rigid plane when its members' ground differs by 2 m (then fix A: the datum read where the body stands, the unit partitioned by reach), or is the graded airside surface a FLOOR under every member (fix B, rigidity yields to the apron)? (17u-2) Bridge parapets: may a parapet wall take the emitted deck face's z at its station (fix D, §16e amended, 13r read as the PLATE only), or stay draped (13r as written, the gap stands)?

## 2026-09-17w v2doorwellperf MERGED: the OTHH structures stage on the new pack COMPLETES (1,386 s, 29.18 GB max RSS; LEMD 4.77 GB / 378 s, VHHH 6.69 / 386, HECA 2.65 / 154) — the production memory bar is MISSED (6.1 × LEMD, above the owner's 25 GB line); the THIRD path is the basin at-grade intersection with 500k-triangle INTERIOR components — §48 (lane `v2interiors`) is its fix; a dry planar replay arms NO shared-repo guard (docket)

* Lane `v2doorwellperf` @ 86d4ab6e (suite 1,961 passed / 2 skipped / 1 xpassed after merging main, no FAILED lines; twin 5/5 red on base). Fix 1 `obj8.above_grade_footprint` / `at_grade_geometry(within=)`: the memoised whole-object union intersected with the window, bound at COMPONENT granularity (the literal whole-object variant measured and rejected: LEMD structures 107 → 337 s; component-bound 121.6 s, byte-identical on every non-timing key). Fix 2 `planar/basins` cover read `within=ring`, LRU keyed (placement, ring). The old windowed branch was also WRONG: it kept whole triangles whose plan bbox overlapped and never intersected — LEMD's two `door_refused` reasons change for that reason (wells 0 → 0). Pairs: HECA byte-identical; VHHH 69/70 `covered_fraction` at 1e-14 (union order); LEMD as above.
* THIRD PATH (attributed, not fixed): `basins.build_basins:563 → obj8.at_grade_geometry → _in_window → shapely intersection` (GEOS KdTree), 2,051 s / 31.42 GB — ONE 500k-triangle component (`OTHH_Terminal_Interior_Clutter_3_1`, 536,802 tris / 141 MB) clips to a multipolygon whose intersection with a ring is minutes and gigabytes; `[basin] rim_read_vertex_budget` 40 M never trips (the whole read charges 7.18 M = 18 %). Every one of the ten heaviest resources is a §48 interior → lane `v2interiors` dispatched NOW with the OTHH ON-vs-OFF peak RSS and wall as its headline bar. PROPOSED production bar (owner's number): the structures stage's peak RSS ≤ 2 × LEMD's (≈ 9.5 GB) on the new OTHH pack.
* Shared-repo write DISCLOSED: the lane's base VHHH arm refreshed `Airport_mod_cache/c_HKG …/o4_dsf_object_positions_+22+113.cache` (124,908 B, 18:29:45) THROUGH a symlink-seeded overlay (`dsf_reader.py:2331` fingerprint refresh); overlays are now real copies. DOCKET: a dry `auto_patch_v2.planar` replay arms no `SharedRepoWriteGuard` — the harness guard must wrap the dry replay entry (one implementation, `tools/harness/shared_repo_guard.py`), refusing a write through a symlink into the shared repo; until then every lane COPIES its dumps. The 19:30–19:39 LEMD/HECA cache and `Patches/HECA*`/`HEAZ*` writes are the peer session's.

## Tool: site_read

| `Ortho4XP/tools/site_read.py` | You have a coordinate from an owner's sim read and the question is WHAT THE OBJECT STAGE MADE OF IT — not what the OSM patch says there (`osm_site.py`, the emitted ways) and not one law's defect count (`harness/census.py`). Three products of ONE build, read at ONE point in one process: the emitted DESIGN SURFACE's faces containing or near it (role, ref, side, z min/med/max, node count — a CONTAINING face reads 0.0 m, never the distance to its nearest vertex, which is `osm_site --at`'s own trap); the DSF ROWS standing on it (`OBJECT` / `OBJECT_MSL` / `OBJECT_AGL` with the resource and, where it has one, the written elevation — `None` for a plain `OBJECT`, never 0.0); and the PLAN BODIES whose plan box reaches it, each with its §6 class, its FOOTPRINT UNIT, its surface z and zero and the stage's own ANCHOR REASON verbatim, which is the line that says WHY a body is where the owner saw it. `--patch-dir DIR` resolves `<ICAO>.graded.json` and `o4_v2_placement_<ICAO>.json` by glob (an `obj8_split_report --json` dump works as `--plan`: the same `splits` records), `--dsf-dump` takes a DSFTool TEXT dump — pass the PRISTINE `<dsf>.anchor_bak...text` (`dsf_write.pristine_dsf_path`) when you want the pack as INSTALLED rather than as this repo last wrote it. `--show`, `--max`, `--json`. **It measures nothing and derives no law**: every value is read verbatim out of a product and nothing is written. Promoted 2026-09-14 (RULINGS `7e90032`, promote-on-reuse) from the scratchpad reader of the 14g HECA attribution, re-written for the 14bl LEMD one (scouts `v2heca331` / `v2lemd336o`) and used a THIRD time by lane `v2leafframe` — three copies of one question, already drifted in their hard-coded LEMD paths. Twin: `tests/auto_patch_v2/test_v2leafframe.py`. |

| `Ortho4XP/tools/arm_site_read.py` | The question is about a PLACE across two arms — "is the wall at 35.2077303,-80.9290869 still there, and did anything near it get worse?" — which an A/B leaves open: `census.py --rows-json` itemises rows and `census_rows_diff.py` joins two dumps class by class, but neither can be asked about a coordinate, and `osm_site.py` reads geometry without law rows or pad seats. This is the join: per named `--site`, per arm, the law-true rows within `--radius` with their worst grade and |de|; with `--seats`, the BUILDING PAD seats that moved between the arms — the channel this repo's HECA airside attribution ran through (a pad seat welds into the apron ring, so a seat that moves moves airside; measured 2026-08-12b: 92 of 215 pads, median 0.32 m, and building211's +0.88 m carried +203 apron rows). **It measures no law and counts no defects**: rows are read verbatim out of census `--rows-json` dumps and geometry/altitudes through the harness library's own `check_grade._parse_osm`, so this tool and the census read one file one way; a missing input reports SKIPPED, never zero. FRAMES, both printed: rows are located by the census's own row lat/lon, which for a within-shape pair is the PAIR's position (a 400 m apron chord's row sits far from either endpoint's geometry), so a radius selects rows near the PAIR, not shapes touching the site; seats join by the building's `ref` tag, never by way id or shapeID (both arm-dependent). Promoted 2026-08-12b from the service-corridor lane's `measure_arms.py` on its SECOND use — the named-site table and then the airside attribution. `--welds` (added 2026-08-12c, the corridor-joins round's ruling-4(a) instrument) answers the other question a place can be asked — IS THIS SEAM JOINED? Per site, per arm: the node ids SHARED between the road family (`check_grade._ROAD_FAMILY_ROLES`, read from the census library) and the airside ways, the max |Δalt| two ways carry at a shared node (0.00 is the construction — production values sit on the NODE, so a weld is single-valued; the delta is the torn-weld guard for way-valued rings), the NEAREST UNWELDED approach when nothing is shared (0.999 m at both KCLT mouths, against a 0.5 m weld tolerance), and the `retaining_wall` ways standing at the site with their ids. `--profile` / `--line` (added 2026-08-25, the HECA apron round-2 acceptance) answer the THIRD question a place can be asked — WHAT SHAPE IS THE SURFACE HERE? `--profile` walks every ring of `--profile-roles` (default `apron,graded_strip`) reaching a site and reports its worst consecutive EDGE and its RIPPLE AMPLITUDE, the peak-to-peak inside a 50 m run ALONG THE RING — the same window `apron_drape_read` calls `amp50`, so the two tools spell the ripple one way. `--line NAME=LAT,LON:LAT,LON` orders every emitted vertex in a corridor about an owner-named segment by its station along it, with the step between consecutive stations: the reading an acceptance written as "no unlawful step along the owner line" is stated in, AND the reading that shows a NODELESS VOID, because there an EMPTY STATION LIST IS ITSELF THE FINDING (a region with no emitted vertices contributes no census row however wrong its surface is — the blind spot `nodeless_interiors` counts). Neither prices a law; quote them ARM TO ARM on identical options, never as a verdict. Reach for it whenever an acceptance claim is about a join: **row absence cannot answer it** — a census row exists only between PAIRED geometry, so an unwelded road↔taxiway seam is silent in every census, which is exactly how two 1.0.244 acceptance claims passed over a gap no node could bridge. Twin: `tests/test_corridor_axis_coverage.py`.  **`--behind NAME=LAT,LON:LAT,LON` is the WALL scope** (added 2026-08-29, scorer-v2 round, spec `scorer-v2-class-boundary-spec.md`): the owner states a wall as two coordinates and asks that no airside pavement cross it — `--line` answers what the emitted elevation does ALONG it and `osm_site --line` answers what covers each station ON it, but neither answers the quantitative half, the SQUARE METRES of airside-role pavement sitting on the groundside, which is the number a boundary-cut round moves and therefore the number its acceptance is written in. Per crossing ring it reports the area behind, the node split either side and each side's altitude range — the shape of a wall buried inside one apron (HECA apron 584: 48 nodes at 97.22-104.69 m in front, 95 at 90.77-102.71 m behind). TWO FRAME RULES, both load-bearing: the band is the line's OWN SPAN by `--behind-depth-m` (default 150 m) deep, never a half-plane — unbounded, the far side sweeps in the whole airport and reports 634,371 m² where the local answer is 25,900 (measured at HECA); and the GROUNDSIDE side is decided by the patch — the side carrying less airside pavement — so reversing the two coordinates cannot change the answer and a caller cannot pick it. The closed-ring repeat is dropped before the node split (counting it double reports one extra node on whichever side the ring starts). It prices no law and counts no defects. **THE SEAT JOIN IS NOT FREE (2026-08-31, the buildings round).** `building{N}` is an ORDINAL identifier, so an arm that ADDS or DROPS a pad renumbers every later one and the ref join reports the RENUMBERING as seat motion: measured on the buildings-round HECA arms (pad count 175 -> 176) the ref join said 85 of 174 pads moved, median 2.72 m, max 33.65 m, where the population had barely moved. The tool now DETECTS it — a common ref whose pad centroid is more than `--seat-radius` (15 m) away is named as RENUMBERED, with the advice to re-run — and `--seat-join location` pairs pads by centroid instead (closest pair first, each pad used once; a pad with no partner within the radius is reported as added/dropped, NEVER as a move), which on the same arms reads 28 of 174 moved, median 0.07 m, max 2.32 m. Quote a pad-population round's seat movements under the location join.  **`--airside-near-cuts M` (2026-09-15, lane `v2shellwall`)** answers the question spec §33 (6) B AMENDED is written in — *did airside beside the pack's structure-object cuts move?* (owner RULINGS 2026-09-15bh: "airside beside a shell never moves", bar 0.02 m).  The region is the SIDECAR'S OWN `object_cuts` `outline_ll` (the arm's, else the control's — a cut that did not exist in the control is precisely the case asked about), never a radius the caller typed, so this read and the `object_cut_offset` family are priced against one geometry; the join is the canonical 11-dp lat/lon identity join, never proximity; a vertex present in one arm only is reported as UNJOINED and named, never as zero motion. Reports the joined population, the movers over `--airside-move-floor-m` (0.02 m, §16g (10) (5)'s own bar), the worst mover with its coordinate, both altitudes and its ways' roles, and the movers by role.  Measured on the registered VHHH pair (`VHHH_20260915T120714` → `VHHH_20260915T122604`): joined 1,079, MOVED 633, unjoined 223, worst −6.460 m at 22.30772370921,113.92337437951 (7.31 → 0.85, junction/primary_parallel).  It measures no law and counts no defects. |

## Tool: obj8_split_report

| `Ortho4XP/tools/obj8_split_report.py` | THE OBJ8 SPLIT, DRY-RUN (spec `object-placement-spec.md` §4 / §6 / §7; owner RULINGS 2026-09-11b) — what a pack's object stage becomes once placements are AGL, objects are cut into their RIGID BODIES and each body carries its own anchor. Reads only a build's own two products — the re-seat plan (`<ICAO>.rebake.json`: the pack read once, its welded parts and the ε-contact graph) and the emitted DESIGN SURFACE (`<ICAO>.graded.json`, whose `building` faces are the object pads and `structure_rim` breaklines the basin walls) — and NEVER opens the pack for writing, never reads the DSF and never builds anything. Prints per placement the bodies, their §6 class, each body's anchor point / reason / authored offset, the files that would be written and the placements KEPT WHOLE with the reason (`one_body`, `anim`, `unparsable`); `--write-into DIR` writes every cut file into a scratch dir and parses each back through `airport/obj8.parse_obj8` (LEMD 13,924 files, OTHH 65,360, all parsing back with the written triangle count, 2026-09-11); and prints §7's CENSUS — the design surface at a body's ANCHOR against the surface under each of its ground-contact FEET, the |Δ| histogram `seat_feet_census.py` prints from a mesh and a seat result, read instead from the plan and the design surface so the two are comparable. A foot or anchor outside every graded face reads `off-surface` and is never guessed at (the DEM governs there and this tool does not open the DEM). `--no-cut` for body counts only, `--filter`, `--json`, `--split-tol` to override `[placement] split_tol_m`. ROUND 2 (owner RULINGS 2026-09-11e, spec §9): the bodies are COARSENED (bodies of one placement whose intended-zero terrain heights agree within `split_tol_m` are one file, the senior body's anchor; an elevated body joins the nearest ground group) and each anchor is the GENERIC one (the footprint point where the design surface equals the body's zero; a body with authored relief beyond its skirt takes its low-side foot and is reported with the residual) — LEMD 302 placements -> 985 files (3.26x), OTHH 954 -> 1,172 (1.23x). §13 (owner RULINGS 2026-09-11r/s): an ELEVATED body — one whose lowest authored vertex, or the `y_zero` of the anchor the generic rule gives it, stands above `[rebake] elevated_base_m` — NEVER has a file of its own; it joins its CARRIER (the same placement's ground body with the largest plan overlap, else the nearest) at its authored offset, and a placement with NO ground body is KEPT WHOLE with reason `footless`. The report prints the two classes by name — `elevated bodies as own files` (BAR 0) and `footless placements kept whole` — because the FEET histogram cannot see this defect: the writer shifts an elevated body so its own lowest vertex lands on the terrain and every foot then reads perfect (LEMD's 218 roofs/decks/tower parts censused green while the sim was broken). Measured on matched pack copies: LEMD own-files 278 -> 0, files 1,099 -> 828, feet > 3 m 1,060 -> 151, worst 34.06 -> 13.75 m; OTHH 1,203 -> 333 files, feet > 3 m 952 -> 6. ROUND 3 (owner RULINGS 2026-09-11f, spec §10): the write half RESTORES every `<obj>.anchor_bak` in the pack before any file is written (counts in the plan's provenance), and a LINE OBJECT authored as one component is cut into SEGMENTS by triangle station (`--line-segment M` overrides `[placement] line_segment_m`; 0 disarms it) — LEMD 897 segments from 271 one-line bodies, 985 -> 1,086 files, census `> 3 m` 30 -> 25; OTHH 1,187 files, `> 3 m` 0. `--write-pack PACK_COPY` runs THE WHOLE WRITE HALF into a pack COPY through `airport/placement_write.apply_plan` (cut files, DSF + backup + provenance, dump-cache refresh, `o4_v2_placement_<ICAO>.json`) and reads the written DSF back; it REFUSES a live X-Plane install. The census also splits the feet over 0.3 m into BURIED (lawful) and FLOATING (the defect the eye reads). `--rows-near LAT,LON[,R]` (lane `v2padcluster`, 2026-09-14) is that SAME projection selected BY PLACE — every body whose ANCHOR is within R metres (default 40) of the coordinate, nearest first, each row carrying its `site_m` — because the owner names a defect by coordinate and the shapeIDs in a report go stale between builds while a coordinate does not; `osm_site --at/--contains` answers the other half of a site question (which emitted FACES cover the point) and is not re-spelled here. Promoted from the scout `v2heca331`'s scratchpad `site.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse): the 14g attribution, then §16g (10)'s per-site bars; its graded-face half was already `osm_site`'s and was NOT copied. Twin: `tests/auto_patch_v2/test_v2objsplit.py::test_rows_near_selects_the_same_rows_BY_PLACE`. `--rows SUBSTR,SUBSTR` (lane `v2canopy4`) prints the PER-BODY rows of the placements named — the body's anchor (point, surface z, `y_zero`, reason), its ground-contact feet, its worst foot signed with |Δ|, and the 0.3 m verdict — for the owner's named sites (`OldTerminal_FSX-LEMD38,-LEMD84,-LEMD60`); it is a PROJECTION of the one census pass, never a second instrument (the bins, feet and worst list are identical with and without it, twinned). §14 (owner RULINGS 2026-09-11u/v, lane `v2carrier`): a FOOTLESS placement is CARRIED — written as a body file at its CARRIER's anchor with the carrier's `y_zero` (the footed body of its UNIT it abuts with the largest contact, else the nearest, else the largest) — a BASIN resource is never split and anchors at a RIM point where the design surface equals its zero (`rims` wired at last), and bodies of one resource that OVERLAP IN PLAN bind whatever the contact graph says. The report prints the four §14 bars (`footless at datum` 0, `footless on ground` 0, `basin bodies split` 0, `spread`) beside §13's, from `airport/placement_carrier.census_v14` — the same call `seat_feet_census --placement-plan` makes over the same plan shape, so the two instruments are one code path. Measured on the app's 1.0.315 LEMD frame: the four footbridge resources at the terminal's zero 616.65 (deck bottom road + 4.4-5.0 m, was ON the road), `Terminal4SAT_pink-LEMD01` at its terminal's 597.43, the basin's three resources one file each on ONE rim vertex (zero spread 7.0 m -> 0.00, parapet +2.99 above the rim), files 828 -> 855, round trip OK, row census `> 3 m` 17. Twin: `tests/auto_patch_v2/test_v2objsplit.py`. §15 (owner RULINGS 2026-09-11ae, lane `v2roofcarrier`): the CARRIER IS WHAT THE BODY STANDS OVER — chosen across the whole UNIT, every resource alike, by largest PLAN OVERLAP beneath, else largest contact, else nearest (§13's same-placement scope and §14's contact-first order are superseded; the pack names its roofs as their own resources, so the walls a roof rides are almost never its own file); the plan-overlap BOND is RE-CUT where a bound group's intended zeros span more than `split_tol_m` (a rigid body is never wider than the terrain it can stand on; BASIN exempt); DUPLICATE ROWS of one resource identical in lon/lat/heading are ONE placement, all of them replaced (`--write-pack` reports `duplicate rows of a SPLIT placement ... surviving after the write`, bar 0); an anchor or foot on no graded face is marked OFF-SHEET and excluded from every comparison and bar; and the report prints §15 (3)'s `stands-over float > 0.5 m` from `airport/placement_carrier.census_v15` — `float = zero - zero_beneath`, the class NEITHER the feet histogram nor §14's bars can see (a carried body has no feet at all), barred at 0 for CARRIED bodies and reported for footed ones. §16 (owner RULINGS 2026-09-11ai, lane `v2skipped`): the report adds the POPULATION census (`placement_carrier.census_population`: `rows on the datum outside the plan` — the resources the SEAT-era thickness gate dropped, which keep the pack's shared-datum row and render where the datum is, bar 0 — beside the lawful skips and the multi-anchor class, reported not barred) and `census_v16`'s `float = zero - ground_under_geometry`: the ground read under the body's OWN parts (`geom_box` / `foot_boxes`, the median of the part-box centres) and never under its carrier's box — `CARRIED bodies whose carrier's zero is over 1 m from the ground under their own geometry` (bar 0; LEMD 39 -> 0 on matched arms) and `files whose own-geometry ground departs over 3 m from the ground at their row` (26, reported). `--admit-skipped PACK_ROOT` puts the thickness-gated resources of a PRE-§16 plan back into the population by reading their rows from the pack's own DSF (one part per component, no contact graph, the member id IS the DSF row index) — what a build's own plan now carries, for replaying a plan written before the switch; LEMD 25 resources / 25 rows, OTHH 99. §16a (owner RULINGS 2026-09-11aj, lane `v2skipped2`): a CARRIED body is cut where its CARRIER is cut (one piece per carrier terrain group its own triangles stand over, each riding that group's zero; never by the ground under itself), the ground check moved to the carrier's OWN feet (`Candidate.ground_off`, `surface(foot) - y_foot` against the body's zero), and `census_v16`'s carried number demoted to INFORMATION — the bar for a carried body is §15 (3)'s `zero - zero_beneath`. The report prints `carried bodies left uncut by the ground` / `cut by their CARRIER into N piece(s)` and, beside the §15 bar, how many of the carried floats stand over a body the law REFUSES as a carrier. LEMD carried float 58 → 4, files 1,591 → 1,328, plan stage 9.9 → 6.3 s; OTHH 7 → 39, 46.4 → 60.2 s (both OTHH bars missed and reported). 11ak (lane `v2skipped3`): the CARRIED bar's `beneath` is the carrier THE LAW CHOSE (`merged_into`, resolved by identity over every row that reads a zero — a carrier written WHOLE names its MEMBER RESOURCE, which is the whole of OTHH's residual), and a body the law REFUSES as a carrier is counted and named as its own class, `carried over a refused body`, with how far its own feet stand off; §16 (2) also cuts BY FOOT (`placement_cut._LineCutter.foot_groups`: the feet grouped by the zero each says the body has, `surface(foot) - y_foot`, each triangle joining the group of the foot nearest it in plan) — the class no ground cut can see, a body whose FEET are authored over metres of relief on terrain that barely moves, which is exactly what §16a (2) refuses. The re-cut line prints the three cuts (terrain / triangle / foot). LEMD carried float 4 → 0, refused carriers 117 → 21 (13 of the residue are rim-anchored BASIN bodies the foot cut is exempt from), files 1,328 → 1,371, plan stage 6.2 → 5.66 s; OTHH carried 42 → 0, refused 55 → 19, files 1,679 → 1,622, plan stage 59 → 31 s (`solid_components` read in one sort instead of a mask per component; `bind_plan_overlaps` swept by the hull's south edge). 11al (lane `v2basincarry`): a BASIN body is EXEMPT from §16a (2)'s ground test — its zero is the RIM (§14 (2)) and its floor feet are authored below it by construction — so it may carry, and the report prints `§16a (2) basin carriers` (how many basins, how many the feet test would have refused) beside the refusal set: LEMD refused carriers 21 → 8, OTHH 19 → 4, carried float 0/0 unchanged. §14a (owner RULINGS 2026-09-11ap item 6, lane `v2basinring`): a BASIN body follows its RING. §24 (1) puts the rim vertices at the APRON's level, so the ring is not level (LEMD's T4 pit 597.68 … 599.52 over 59 nodes) while §14 (2) wrote every basin body at ONE rim point — the owner's "gap between wall and apron", +0.71 / −1.13 m, while the §14 `spread` bar read 0.01 because it measures the pit's bodies against EACH OTHER. `airport/basin_ring.py` (NEW: the whole law — `arcs_of`, `ring_arcs`, `member_kind`, `ring_bar`) cuts the ring into ARCS whose z agrees within `split_tol_m` and cuts each basin body's WALL BAND by them, one piece per arc anchored at that arc's rim point (the interior remainder keeps §14 (2)'s single point: the trench floor is one level); and a member authored AT THE RIM PLANE but standing inside the ring is a FLOOR body that takes §16 (3)'s ground under its own footprint, never the rim, never a carrier. The report prints the RE-DEFINED bar — `§14a spread of a BASIN RING = max |wall base − ring z| over its nodes` (bar ≤ `split_tol_m`), with the nodes on an arc the pit has NO WALL on reported beside it — and the `§14a basin FLOOR members` / `basin bodies cut by the ring's ARCS` counts. It needs the rings WITH their heights (`census_v14(rims=..., arc_cap=..., counts=...)`; `RimRing.z`, and the `basin_arc_wall:<ref>#<k>` counts keys the cut writes are how the bar tells "no wall here" from "the wall is written in the interior piece"). Matched arms on the app's 1.0.319 LEMD frame: the ring bar 1.12 m / 9 nodes over → **0.18 m / 0 over**, `LEMD13__b0` off the rim and onto its own ground, files 1,371 → 1,394, feet > 3 m 518 → 412, floating 9,509 → 9,014; OTHH's 21 basin carriers and its whole foot census byte-identical. §16b (owner RULINGS 2026-09-11ap, lane `v2owncut`): the TERRAIN CUT IS PRIOR AND UNIVERSAL and is read on the body's OWN WRITTEN TRIANGLES — including everything the writer will put in the file (`placement_cut._LineCutter.all_tris`: a placement the plan reads as ONE body is written as the WHOLE object, which is why `green-TEJ3`'s 4-triangle part read 0.22 m of ground while its 2,342 m file stood +16.22 m over it) — so a CARRIED body is divided by the ground under itself first and §16a (1)'s carrier cut runs inside each piece; §9's coarsening additionally requires PLAN CONTIGUITY (`[placement] coarsen_reach_m`, 30 m) and acts WITHIN a terrain group (the pieces carry the ground they stand on, or the very next pass welds them back); each PIECE finds its own carrier, and a FALLBACK candidate (contact / nearest / largest, no plan overlap) is refused unless its zero is within `split_tol_m` of the ground under the piece (`carrier_refused_far_from_carried_ground`). The report prints `census_v16b`'s two bars over the WRITTEN geometry the plan now publishes per body (`geom_pts`, one sample per 10 m cell, thinned to 32 by the farthest-point walk): `carried piece float over its own ground > 0.5 m` and `body wider than its terrain group`, both bar 0, with the BASIN exemptions (§14 (2) / 11al) counted apart and the wide residue split by class. `--coarsen-reach M` overrides the contiguity reach. Measured on the app's 1.0.319 LEMD frame: the owner's item 3 +10.74 → the plate ON the roof beneath it (618.58 vs the group's 618.60), item 5 +16.22 → 620.38 vs 620.27, `Terminal4_48` zero-vs-ground −4.02 → median −0.01, `Taxisigns-SENRG` 38 of 80 bodies over 0.3 m → 12 of 419; files 1,371 → 3,272 at the amended 100 m reach (4,633 at the refuted 30 m), plan stage 5.6 → 10.1 s (bar ≤ 8 s MISSED, reported). §16c (owner RULINGS 2026-09-12b/12d, lane `v2atom`): THE CONNECTED COMPONENT IS THE ATOM — `--torn-seams PACK_ROOT` prints the TORN-SEAM CENSUS over a WRITTEN pack (the plan argument is then the WRITTEN `o4_v2_placement_<ICAO>.json` and `--graded` is not read), and the same census prints automatically after `--write-pack`: sibling files of ONE placement that share an AUTHORED VERTEX (the key `obj8.solid_components` welds on, `round(x, 3)`) are two halves of one connected solid written at two zeros, with the base step per seam, the step histogram, the worst list and the per-class breakdown, and §10's line segments / §14a's basin arcs — the only lawful station cuts — counted APART.  Two bars, both 0: `torn seams outside line/arc pieces` and `single-component resources in >= 2 files`.  The instrument is the scout `v2lemd320`'s `tear.py`, promoted on its second use, and lives in `airport/placement_seams.py` (`census_torn_seams` / `census_torn_seams_lines`, re-exported through `placement_census`).  Measured on the live 1.0.320 LEMD pack it reproduces the owner's four sites exactly (`HANG3` 10 files / 14 seams worst 3.05 m; `green-LEMD50` 7 / 11.12 m; `Bridge2` 8 / 11.72 m; `green-STRT4` 53 files, `__b44` 16.29 m) and the class (2,554 seams, 1,994 over 0.30 m).  On matched replay arms the law takes LEMD 723 -> **0** seams and 128 -> **0** single-component splits (files 3,253 -> 2,804, plan stage 13.5 -> 10.2 s over 3 runs, round trip OK), OTHH 639 -> **1** and 165 -> **1** (files 1,897 -> 1,898). §16c (6) (RULINGS 2026-09-12h, round 2): `--contact-eps M` overrides `[placement] contact_eps_m` (2 mm) — components of ONE resource whose geometry comes within it, or whose parts the rebake plan's ε-contact graph already links, BIND into one rigid body for anchoring (one zero, the senior component's carrier): OTHH's `OTHH_Fuel_02_LOD0_007` carries two components 0.4 mm apart that the millimetre weld key reads as separate.  LEMD files 2,804 -> 2,776, seams stay 0, `Terminal4_48` zero spread 3.58 -> 0.69 m, plan stage 9.6 s (main 13.5). ROUND 3 (RULINGS 2026-09-12j): the entry now runs inside `harness/shared_repo_guard`'s WRITE GUARD and its before/after audit (a round-2 OTHH `--admit-skipped` run had created `Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text` in the SHARED repo with both lane-local cache env vars exported and nothing refused it); every run prints `[guard] shared repo UNCHANGED`.  `--rigid-reach M` overrides `[placement] rigid_reach_m` (2.0) — §16c (8): SOLID components of one resource within it chain into ONE rigid cluster, which is the atom of the BODY as well as of the cut (LINE objects excluded).  `carrier_fill_min` is DELETED from carrier candidacy (§16c (7)); the CLASS exclusion stays.  LEMD: `HANG3` 6 files / 1.37 m -> 2 / 0.45, `green-STRT4` 23 -> 15 files (spread 8.90 -> 3.73), files 2,776 -> 2,121, §16b wide 1,405 -> 967, seams 0, round trip OK; five largest rigid clusters are all SINGLE components (5,157 / 2,890 / 2,514 m — fences and VOR markers, not chained) and `green-TEJ3` stays 9 components / 9 clusters. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. **§17 CRITICAL MOTION IS READ** (owner RULINGS 2026-09-12am (2), lane `v2objmotion`): the graded surface's FACE ROLE under every foot (`airport/placement_boxes.GradedRoles` / `graded_roles_from_doc`, built from the SAME parsed `<ICAO>.graded.json` the sampler and the pads are, senior face by `precedence.toml`'s authority order, a 55 m grid over the faces' boxes) joined to §7's own float there (`airport/placement_motion.census_motion`, re-exported through `placement_census`): a body with a foot on a ROLLED-ON face (`law.tables.rolled_on_roles`) is ON PAVEMENT and every such foot is judged at `[cockpit] motion_step_m` 0.05 m, named with resource, foot coordinate, face role and SIGN. The block prints the count of bodies on pavement, the feet over the threshold, the worst ten, and the breakdowns by resource / face role / body class / anchor rule / size band, plus what the EYE reads at those feet (floating vs buried over `visual_m`) and the MEDIAN-anchor arm. BASIN bodies are counted APART (§14 (2) / 11al: a pit's zero is its rim and its floor feet are authored below it — they were LEMD's whole worst ten). Measured on the 1.0.320 LEMD frame: 493 of 2,153 bodies stand on pavement, 7,124 feet on 399 over 0.05 m; after the §17 anchor rule 6,635 on 407 (OTHH 6,234 → 3,877 on 113 → 103). RULINGS 2026-09-12ap (lane `v2pavefeet`): `--motion-rows OUT.json` writes §17's PER-BODY projection — one row per written body with its anchor, class, anchor reason and every ground-contact foot (lat/lon, authored y, surface z, face role, on-pavement, float) — the rows `census_motion` itself reads, never a second census (the scout's scratchpad projection, promoted on its second use). (E) THE SAMPLER HONOURS GRADED HOLES: a Delaunay over the emitted VERTICES spans a hole ring with triangles reaching from an apron vertex to a trench vertex, and LEMD read **592.22 m at a point whose ROLE is apron** six metres outside the hole — 12ap's two worst pavement feet (`LEMDblast__b1` +7.18, `Terminal4sBlue-STRT4__b1` −5.08) were that fabricated ramp, and the anchor correction is 6.91 m. A simplex CROSSING a hole ring with a step over `split_tol_m` is struck and a point inside one reads the nearest vertex of that simplex ON ITS OWN SIDE of the ring; measured narrowings: "centroid on no face" struck 8,689 of 47,287 simplices and cost 421 files / 435 off-sheet bodies, and a strike with no side-aware read cost 160. (B) §17 is judged at the GROUND-CONTACT feet — the in-band feet within `split_tol_m` of the lowest (`placement_motion.ground_contact_feet`); `contact_band_m` is shared law and unchanged, BOTH sets are sampled and the wider reading prints beside the judged one so the report states its own attribution. (A) `bind_ground_m` (`[cockpit] visual_m`) bounds §16c (7): a FOOTED body of ANOTHER member keeps the cluster only while its own zero is within it of the senior's, else it keeps its own anchor and is counted — the report prints `bound refused for ground N` with the worst refused disagreement and the widest RETAINED cluster zero-plane span. Matched arms, LEMD main → branch: CRITICAL MOTION 6,640 → 5,400 feet on 407 → 356 bodies, over 0.5 m FLOATING 663 → 128 and BURIED 1,109 → 808 (of which (B) alone 581 → 128 / 816 → 808), worst pavement foot +7.18 → +2.41 m, 74 binds refused (worst 2.38 m), files 2,107 → 2,149, seams 0/0, round trip OK, plan stage 10.19 → 10.03 s; OTHH 3,891 → 2,822 feet on 103 → 74, floating 332 → 12, §14 footless at datum 5 → 4, files 1,252 → 1,269, plan stage 60.8 → 61.4 s (the ≤ 60 s bar missed on BOTH arms). §16b's carried-piece float and wide counts move the WRONG way at both airports (LEMD 111 → 119 / 967 → 983, OTHH 126 → 135 / 75 → 78) and are named. §16d (owner RULINGS 2026-09-13h, lane `v2unboxed`): THE PLAN BOXES WHAT THE WRITER WRITES — a WRITTEN-FRAME bar beside the torn seams, `§16d bodies with written geometry > 1 m outside their geom_box` (`airport/placement_seams.census_outside_box`, printed after `--write-pack` and by `--torn-seams`, bar 0): `geom_box` was the hull of the ADMITTED PARTS while the writer emitted the source object's triangles regardless, so a component no part named (the FS2XPlane origin plate, an exporter's ground paint, a roof plate over the next hangar) rode a zero the body chose elsewhere and NO instrument read it — LEMD 1.0.325 live pack 378 of 2,109 bodies, 8 over a kilometre. Every connected component the writer will emit — draped ones included — is now PLACED: within `coarsen_reach_m` of a ground group's part hull it joins that group and `geom_box` grows to the hull of what the file will contain; beyond it, it is a FOOTLESS BODY §15's search places, or §16 (3)'s own ground (`--coarsen-reach 0` disarms the reach and the component joins the nearest body, the pre-§16d reading). The nearest-footed fallback is CAPPED at the same reach (`carrier_refused_nearest_beyond_reach`), and the COCKPIT block names the worst row by the centre of the BODY'S OWN written geometry, never the placement row (a shared-datum pack puts 96.5 % of its bodies on two points). `plan stage: N.NN s` is printed after the split — the number a round's budget is quoted in, timed exactly where the shipped engine's own `build_splits` call is, without the graded parse or the census. Matched dry arms on the 1.0.325 LEMD frame (the app's own arm reads a MESH sampler where the tool reads a Delaunay over the graded vertices — the two disagree on every surface-driven refusal and the bars are read dry-to-dry): outside-box 390 → **0**, nearest-footed over 100 m 29 → **0**, the four shadow plates +15.94/+15.73/+5.77/+1.72 → **−5.00 on their own ground**, `Cargo-TEJ1` on `NEWCO__b9` roof base 604.95 (bar 0.3 of 605.04), seams 0/0, §15 carried float 0/0, round trip OK, files 2,141 → 2,279, LEMD plan stage 13.6 → 17.8 s and OTHH ≈83 → 86.1 s (both bars missed on BOTH arms, named). It also fixed a latent WRITER defect: the cut file was named by its index in the LIVE body list while the DSF row is written on the plan's `body_id` name, so a body the cut left with no triangle shifted every later body's file one name down (`OldTerminal_FSX-DCNEUN`'s `__b0` row held `b1`'s object). §16d (4)-(6) (owner RULINGS 2026-09-13m, same lane, second frame KCLT 1.0.324): a CARRIED body's components group BY CARRIER — each ATOM (§16c (1)'s, so a rigid cluster is never divided) asks its own carrier question BEFORE the search, counted as `carried bodies cut by ATOM`, where §16a (1)'s after-the-fact cut could only divide the answer the whole body got (KCLT 5,295 carried bodies left uncut against 3 cut; a native pack's master roof model spans 1,774 m); §16c (7)'s 0.5 m ground bound is MEMBER-AGNOSTIC (12ap tested `member != top.member`, and a native pack's one-model-per-material member spans the airport: KCLT's `005_ALB__b9` sank 5.04 m into its pad on a same-member bind to an apron body 500 m away); and a FOOTED body whose ground contacts lie mostly inside one emitted `building` pad reads only the contacts ON it (`anchor_rule.pad_majority`; the anchor reason then says `on pad <ref>`). Matched dry arms at KCLT: `005_ALB__b9` -5.85 -> **+0.02** against its pad, widest retained cluster zero span 5.69 -> **0.64 m**, 473 carried bodies divided by atom, 61 bodies anchored on their pad, `building80`'s on-pad zero spread 1.03 m (the pad's own relief 1.19), §16d outside-box **0**, §15 carried float **0**, round trip OK 477/477, one new torn seam (+0.16 m, one shared vertex, named), files 473 -> 477, plan stage 8.65 -> 8.3-8.5 s. It also exposed a defect the atom cut made visible: a target group holding BOTH a cut piece and an untouched raw was read for its `tris` alone, leaving 990-3,280 triangles per placement claimed by no body (9 of KCLT's 103) for `obj8_split` to hand to the nearest one — the audit reads 0 of 103 after. **COST: plan stage LEMD 17.8 -> 25-46 s and OTHH 86 -> 136 s** (KCLT flat) — the per-atom carrier search, narrowed by a `coarsen_reach_m` span gate, a 64-atom cap, per-atom pids and a set-intersection contact count, and still needing the owner's approval and a Fable-5 review before it ships. **§16g (5)'s PER-PLACEMENT ROW CENSUS, DRY (`--dsf-dump DUMP.text`, owner RULINGS 2026-09-14bo, lane `v2leafframe`).** The dry path reads no DSF by design; given an EXISTING DSFTool text dump it also prints the `OBJECT_MSL` seats the writer would emit, from the SAME `footprint_unit.msl_seats_for_dump` call `placement_write.build_plan` makes — the per-row base (`msl_base_unit_pad` / `msl_base_own_feet` / `msl_base_deck` / `msl_left_to_the_drape` / `msl_off_sheet_left_draped`), the multi-anchor census beside it, and `|elevation - the design surface at the row's own feet|` over 0.5 m with the worst named. PASS THE PRISTINE DUMP (`<dsf>.anchor_bak...text`, `dsf_write.pristine_dsf_path`): a dump of an ALREADY-WRITTEN pack reads the app's own absolute elevations back as authored offsets and reported 1,055 rows 22 m off their feet that do not exist. Measured at LEMD on the pristine dump: `OBJECT_MSL` rows **1,481 -> 0** (1,466 left to the drape, 196 standing on their unit's pad at offset 0, 5 off-sheet) — every LEMD multi-anchor row is a plain `OBJECT` with no authored offset, so the drape at its own feet IS the law's answer. Nothing is written and no DSF is decoded. Twin: `tests/auto_patch_v2/test_v2leafframe.py`. |

## Tool: v2_rebake_replay

| `Ortho4XP/tools/v2_rebake_replay.py` | The auto-patch-v2 OBJECT STAGE replayed OFFLINE — the synthetic-first instrument for the post-mesh half. `plan PLAN.json MESH --graded G.json` replays and TIMES the PLACEMENT stage over the sampler the app calls (RULINGS 2026-09-12g), with `--sampler`, `--no-batch`, `--src`, `--plan-out` and the `--oracle-write` / `--oracle-check` bit-identity pair; `order ICAO` is the partition-order twin (11j / spec §11a (3)); `disk PACK_ROOT` prints a pack's current bake state from its `.anchor_bak` backups and v1 provenance, read-only. The `plan` subcommand was DEAD from 12j/12s until 2026-09-12 (lane `v2objmotion`): it imported `RebakePlan` from `emit.rebake` (it lives in `model.rebake`) and read the deleted `carrier_fill_min` key before its own SIG-DIFF dropper ran — both fixed, and the sampler now carries §17's face ROLES so the timing is of the plan the app builds. THE SEAT SUBCOMMANDS ARE DELETED (owner RULINGS 2026-09-12s, spec §8): `seat`, `bodies` and `pairs` replayed v1's vertex rewrite and its `o4_v2_rebake_result_*` sidecars, a refuted mechanism. Writes no pack and builds no tile. (A), RULINGS 2026-09-12ap (lane `v2pavefeet`): `plan` also passes `bind_ground_m` (`[cockpit] visual_m`) through its SIG-DIFF dropper, so it times the plan the app builds and still runs against a src that predates the key. §16e (lane `v2othhdatums`): the entry now runs inside `harness/shared_repo_guard`'s WRITE GUARD and its before/after audit, the same one `obj8_split_report.py` and `build_airport.py` arm — `plan` calls `dsf_reader.ensure_dsf_text_path`, which GENERATES a DSF text dump into the mod cache when the cache has none, and a lane worktree MOUNTS `Airport_mod_cache` at the shared repo (the class RULINGS 2026-09-12j caught in `obj8_split_report`); every run prints `[guard] shared repo UNCHANGED`. `plan` also BACK-FILLS §16e (2)'s `deck_end_stations` on a plan written before the field, by calling `rebake_plan.ring_ends` / `end_line_stations` — the patch half's own two functions, never a second derivation — and prints the count, so an old artefact can be replayed against the new law. §16e (6) (lane `v2bridgecontact`): `abutment_sample_step_m` / `abutment_walk_max_m` go through the SAME SIG-DIFF dropper, so `plan` times the deck end line's LANDWARD WALK the app builds and still runs against a `--src` that predates the two keys. NOTE (measured, lane `v2bridgecontact`): `--src` pointed at ANOTHER LIVE CHECKOUT is NOT a control, because a live checkout MOVES — the main tree read as clean at one sha gave LEMD 3,646 bodies against 2,122 from a `git archive` of that sha, and the difference was the orchestrator merging §16d into main between the `git log` and the replay (3,646 is §16d's own number, reproduced on both arms once the lane merged it). Cut every base arm with `git archive <sha> src | tar -x -C <scratch>` and point `--src` at that; never at a working tree another session can commit into. |

## Tool: frames

| `tools/harness/frames.py` | THE FRAMES REGISTRY (owner 2026-09-13): `register --icao KCLT --kind capture|rebake|patch|graded|mesh --path P --base SHA --lane L [--note]`, `list [ICAO] [--kind K]`, `latest ICAO --kind K` (newest EXISTING entry; a vanished path prints `[MISSING]` and is never served). Append-only JSONL at `docs/frames.jsonl` (merge-friendly across lane branches). A lane registers its capture / rebake plan / closing products at the end so the next lane does not hunt scratchpads. Twin in `Ortho4XP/tests/test_docq.py`. |

## Tool: blast

| `tools/blast.py` | **Before editing anything under `Ortho4XP/src/` or `Sources/`.** Direct importers, tests to run, role-literal / env-flag / wire-protocol hazards, co-change neighbours. `--audit` checks its own recall. **`--tests-for FILE [FILE...]` (2026-08-12, BS1) is the SWEEP SELECTOR:** it reads the diff (`--since REF`, default HEAD), works out which top-level symbols actually moved (AST before/after, so a reformat or a comment edit selects nothing) and prints the test files whose recorded symbol USE intersects them — measured on `auto_patch/layout.py` with a one-symbol change: **6 test files against the 113-file full direct-importer sweep**. With no FILE it selects for every `.py` the diff touched. The law is a UNION of four clauses and RECALL OVER PRECISION: symbol-attributed tests, ∪ ALL direct-importer tests of a changed file with at most `--cheap-ceiling` (15) of them, ∪ ALL of them for any symbol the index cannot attribute (dynamic use, a re-export, `__all__`, a module-level edit — the fallback is named on stderr, never a silent narrowing), ∪ changed test files. STDOUT is the pipeable list (`| xargs venv/bin/python -m pytest`), the stamped header and every fallback go to STDERR. `--audit --mutations N` is the twin that keeps it honest: it deletes one hot symbol per run AT RUNTIME (a pytest plugin — no source file is ever rewritten, because lanes build against this same tree), runs the sample's FULL sweep, discounts the unmutated baseline and requires every failing file to be IN the selection; recall 100 % is the acceptance and precision is printed beside it, plus what clause 1 alone would have caught. A mutation set with NO failing test is a FAIL, not a pass. Index shards are v3: v2 added `symbol_tests` / `symbols_attributed`; **v3 (2026-08-21) adds `tests_via_fixture` — FIXTURE-MEDIATED reach.** pytest wires tests to conftest by NAME, not import: `conftest.cached_airport_layout` imports `auto_patch.pipeline` inside its body, and a test that says `from conftest import cached_airport_layout` (or takes a fixture parameter, or `getfixturevalue`s it) never appears as an importer of anything pipeline transitively imports. On 2026-08-20 a lane editing `runway_segments.py` + `gap_fill.py` ran the listed sweep (472 passed) and skipped `test_pavement_grade.py` / `test_single_graph_acceptance.py` that way. The card now carries a separate `TESTS VIA CONFTEST FIXTURE` line (grouped by helper, not truncated), `--tests-for` adds a 5th union clause (`via-fixture=N`, the files named on stderr), and `--audit` carries two via-fixture canaries (`FIXTURE_CANARIES`). Src->src edges only (a tool importing a module is not a fixture path); helper->helper calls and fixture->fixture params are closed over. Rebuild stays ~2.1 s. An older index on disk rebuilds itself. |

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
LEMD  rebake   base 31b7ad1b   lane v2doorwellperf   2026-09-17T20:21:59  /tmp/harness/v2doorwellperf/lane_LEMD/structures.json  — LEMD dry 'planar --stage structures' LANE arm on claude/v2doorwellperf 8c6e73e9 (RULINGS 17k (a)): rc 0, 378.00 s real, max RSS 4,770,856,960 B (4.77 GB), lane-local O4_DSF_CACHE_DIR/O4_AIRPORT_MOD_CACHE_DIR. vs the main-31b7ad1b base arm (/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/68719ad8-48b0-4348-b2fb-5068aec73ed8/scratchpad/dwp/base_LEMD): every array byte-identical bar door_refused (2 refusal REASONS at the same 2 sites, wells 0 -> 0) and basins[0].covered_fraction 0.22750614688902682 -> 0.227506146889027 (1 ulp-class, union order). wall_s structures 107.264 -> 220.822 CONTENDED (an uncontended lane run of the same code read 121.559).

## Registered frames: OTHH

OTHH  rebake   base 05050624   lane v2unboxed        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/unboxed  [MISSING]  — KCLT 1.0.324 / LEMD 1.0.325 / OTHH 1.0.326 rebake frames + dry arms
OTHH  capture  base 7949757a   lane v2othh327        2026-09-13T16:30:07  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othh327/OTHH.pkl  [MISSING]  — v2_solve_replay --capture OTHH on main 7949757a (402 s); solved arms beside it: OTHH.solved.pkl (base) and OTHH.nofeet.pkl (--drop-generator foot_rows)
OTHH  patch    base a0f65165   lane v2cutfeet        2026-09-13T17:37:22  /tmp/harness/OTHH_20260913T171324.osm  [MISSING]  — closing build of lane v2cutfeet (§11b (7) cut foot verdicts), rc 0, 968.0 s, ways 1097, body_sha 0ff85d1a7bff, artifact ledger 86493fdab68b; matched replay arms on the v2othh327 capture live in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cutfeet/out (OTHH.base.pkl / OTHH.cut.pkl / othh.base.json / othh.cut.json / *.log), KCLT arms beside them
OTHH  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/fin_OTHH/structures.json  [MISSING]  — OTHH planar --stage structures on claude/v2gradecache vs the 0c86fe2c base arm in scratchpad/base_OTHH: basins array BYTE-IDENTICAL; only one sunken_refused message rounds 50%->49% roofed, same verdict
OTHH  capture  base cf87c942   lane v2unionsweep     2026-09-14T07:40:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2unionsweep/othh.lane.json  [MISSING]  — DRY replay dump (NOT a capture: the plan_clusters reading OFF the registered OTHH capture 7949757a, via scratchpad/v2unionsweep/cluster_arm.py). MATCHED PAIR: othh.base.json = main cf87c942 (666.07 s, machine contended; scout v2partcost read 299.8 s uncontended at 628cca80), othh.lane.json = claude/v2unionsweep 99cf52ba (16.60 s). 44 clusters both arms, all 44 area_m2 BIT-IDENTICAL (struct.pack '<d' hex).
OTHH  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/base/OTHH_base.osm/v2cost2base.osm  [MISSING]  — BASE ARM of the v2cost2 matched triple (own ritual worktree v2cost2base at main 4c6f467c): rc 0, harness wall 631.7 s, staged total 592.86, body_sha 72d4ec0e08f2, ways 1000 nodes 25387, guard UNCHANGED. wall_s load 7.63 / partition 313.57 / classify 7.87 / planar 67.13 / constraints 94.43 / solve 23.34 / emit 9.00 / rebake_plan 5.49 / verify 63.50 (the second Patch.of + road_law_caps + apron_over_preference ran OUTSIDE this clock). obj8_split_report on its own products: plan stage 223.13 s
OTHH  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_cold.osm/v2cost2cold.osm  [MISSING]  — LANE COLD arm (claude/v2cost2 3eeccf13, partition cache EMPTY -> WROTE 1.05 GB): rc 0, wall 615.1 s, body_sha 72d4ec0e08f2 — BYTE-IDENTICAL to the base arm (patch, OTHH.rebake.json and OTHH.graded.json all sha-equal). wall_s partition 288.87 (313.57 base: the per-axis contact screens), constraints 85.32 (94.43), verify 121.85 (63.50 + the 45.6 s that used to run unclocked), total 612.71, unclocked 1.24
OTHH  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_warm.osm/v2cost2warm.osm  [MISSING]  — LANE WARM arm (claude/v2cost2 12b29e6c, partition cache HIT): rc 0, harness wall 328.1 s vs the base arm's 631.7; body_sha 72d4ec0e08f2 BYTE-IDENTICAL, guard shared repo UNCHANGED. wall_s partition 313.57 -> 8.40, classify 7.87 -> 75.79 (the ResourceCache is cold on a hit, so the pack parse moves here: partition+classify 321.5 -> 84.2), constraints 94.43 -> 73.48, verify 63.50+45.6-unclocked -> 62.43, total 592.86 -> 325.17. verify.wall_s per family published (within_shape 50.94, taxi_box 8.72)
OTHH  patch    base 55cf0fe3   lane v2cost2          2026-09-14T11:31:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_r2c2.osm/v2c2r2c2.osm  [MISSING]  — ROUND 2 COLD arm (claude/v2cost2 7bc09ea7, RULINGS 14v; cache EMPTY -> WROTE 31.3 MB, was 1,047 MB): rc 0, body_sha 72d4ec0e08f2, patch/rebake/graded sha-equal to the 4c6f467c base arm, guard UNCHANGED. wall_s partition 283.70 classify 8.90 planar 63.17 constraints 80.17 verify 67.25 total 547.67 unclocked 1.28
OTHH  patch    base 55cf0fe3   lane v2cost2          2026-09-14T11:31:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_r2w2.osm/v2c2r2w2.osm  [MISSING]  — ROUND 2 WARM arm (claude/v2cost2 7bc09ea7): cache HIT, 2,259 resource readings restored; rc 0 harness wall 298.6 s (base arm 631.7), body_sha 72d4ec0e08f2 BYTE-IDENTICAL (patch, rebake plan and graded surface), guard UNCHANGED. wall_s partition 8.07 classify 10.21 (partition+classify 321.5 -> 18.3 on the base arm's frame; bar <= 40 MET) planar 84.43 (55 cold: the pack parse the cache no longer pre-pays lands here) constraints 78.67 verify 69.06 total 296.22 unclocked 1.28
OTHH  patch    base 8e92e26a   lane v2othhfix        2026-09-14T11:37:09  /tmp/harness/v2othhfix2.osm  [MISSING]  — closing OTHH patch build of lane v2othhfix on claude/v2othhfix (§24 (7)/(8), §34 (7)/(8) as amended by 14u): rc 0, 614.3 s, ways 1012, nodes 23724, body_sha 44208e4fdd65, artifact ledger 20d817adcf38, shared repo UNCHANGED; report /tmp/harness/v2othhfix2.v2/OTHH.report.json; census A/B vs the owner's 1.0.332 patch ADJUDICATED 1764 -> 1766 (+2)
OTHH  rebake   base 908895cd   lane v2othhfix        2026-09-14T11:37:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix  [MISSING]  — dry planar --stage structures arms on the lane-local overlay: base_OTHH (main 908895cd), a5_OTHH (the branch, final law); bars.py / inner.py / prof.py read floor-per-region, floor vs rim-minus-standoff and the §34 (7) profile identity; dry.sh / dry2.sh are the arm runners
OTHH  patch    base ed971ccd   lane v2othhfix        2026-09-14T14:56:25  /tmp/harness/v2othhfix_r2.osm  [MISSING]  — ROUND 2 closing OTHH build (§34 (9) the pinched ramp, RULINGS 2026-09-14ak) on claude/v2othhfix: rc 0, 511.5 s, ways 1010, nodes 23607, body_sha ba3354ce693f, artifact ledger 3060701734b4, shared repo UNCHANGED; verify DEFECT families EMPTY (rows 2190 -> 2214, the +24 all within_shape on the two pinched ramps); census vs the owner's 1.0.333 patch ADJUDICATED 3206 -> 3223, road_cross_section 6 -> 6, transverse/airside_no_step/zone_on_pavement unchanged; shared AIRSIDE vertices moved > 0.1 m = 0 of 16,810
OTHH  rebake   base ed971ccd   lane v2othhfix        2026-09-14T14:56:25  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix  [MISSING]  — ROUND 2 dry --stage structures matched pair: r2_base (main 9a8b253b = the 1.0.333 code) vs r2_fix (§34 (9)); corridors 40 -> 40, refusals 50 -> 50, 2 pinched_ramps (Terminal_Base_2_1@2 vs route9 12.6 m at 11.05 %; Terminal_Base_2_5@0/a vs route7 5.1 m at 36.98 %)
OTHH  patch    base 298b6ac8   lane v2liftedcap      2026-09-14T15:43:25  /tmp/harness/v2liftedcap.osm  [MISSING]  — §34 (9) the census takes the LIFTED pinched-ramp cap (RULINGS 14am): rc 0, 494.9 s, ways 1010, nodes 23607, body_sha bdd053b93bbf, artifact ledger 5c0c2ded14c5, shared repo UNCHANGED. MATCHED PAIR: the same patch with the two o4_grade_law_cap_lifted tags stripped is /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2liftedcap/arms/nolift.osm (ADJUDICATED 3223 / law-true 4526 = the v2othhfix_r2 numbers exactly); as built 3204 / 4507. census_rows_diff EXACT 4507 MOVED 0 NEW 0 GONE 19 (all within_shape tunnel_ramp|tunnel_ramp on shapes 828/831). Census json/rows arms in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2liftedcap
OTHH  patch    base a4b7801d   lane v2othhfix        2026-09-14T17:31:46  /tmp/harness/v2othhfix_r3b.osm  [MISSING]  — ROUND 3 closing OTHH build (§34 (9) (4)-(5), RULINGS 2026-09-14aq) on claude/v2othhfix: rc 0, 262.3 s (warm), ways 1010, nodes 23615, body_sha a3c64e4a261c, artifact ledger 4afb62b3f6a1, shared repo UNCHANGED; verify DEFECT families EMPTY, rows 2189 -> 2146; census vs the owner's 1.0.334 patch ADJUDICATED 3204 -> 3174 (within_shape -35, road_cross_section +8 away from both pinched roads); route7 road levels byte-identical, route9 within 0.02 m, 0 of 118 service-road vertices moved > 0.1 m, 2 of 16,810 airside (0.10/0.12 m, apron|building corners)
OTHH  rebake   base a4b7801d   lane v2othhfix        2026-09-14T17:31:46  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix/r3_base2/structures.json  [MISSING]  — ROUND 3 dry --stage structures (§34 (9) (4)-(5)) vs the lane's round-2 arm r2_fix: corridors 40 -> 40, refusals 50 -> 50; Terminal_Base_2_5@0/a climb_from 38.89 -> 36.50 (+2.4 m), pinched grade 36.98 % -> 25.18 %; Terminal_Base_2_1@2 6.30 -> 6.00, 11.05 % -> 10.80 %; mouth_z unchanged both; both pinched ramps report 'the road face edge (the pack paints no line here)' — OTHH carries NO road-edge marking (marks.py/marks2.py/marks3.py/pol.py beside it)
OTHH  rebake   base 9a49f136   lane v2splitname      2026-09-14T18:03:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2splitname/out/othh.lane.json  [MISSING]  — 14at THE SPLIT FILE IS KEYED ON THE OFFSET IT BAKES — MATCHED PAIR of v2_rebake_replay plan --sampler mesh --runs 3 on the 1.0.334 OTHH products (o4_v2_rebake_OTHH.json + OTHH.graded.json + the installed Data+25+051.mesh, --dsf-dump the shared mod cache's +25+051.dsf.55d38455.text). othh.base.json = main 9a49f136 cut with git archive (145.99 s mean); othh.lane.json = claude/v2splitname 4b13e977 (140.26 s mean). Collisions (one file written by >1 placement with distinct offsets) 1 -> 0; distinct body files 1856 -> 1857; splits 705 bodies 1857 both arms; every row byte-identical bar the name (and the 531 anchor_reason/merged_into strings that quote a carrier's file name) — 0 differences beyond the tag. tunnel1 b0: idx 14052 -> __b0_8b16464a baking its own [9.0486,9.5497,-50.1039], idx 14051 -> __b0_c057eb1e baking [-8.8848,9.5497,-84.4220]. guard shared repo UNCHANGED both arms.
OTHH  rebake   base fe0a5b33   lane v2othhfix        2026-09-14T19:34:56  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix/r4b/structures.json  [MISSING]  — ROUND 4 dry --stage structures (§34 (9) (6) the half-width margin) vs r3_base2: corridors 40 -> 40, none lost; Terminal_Base_2_5@0/a top_s 44.0 -> 40.0 (IN 4.00 m) grade 25.18 -> 53.95 %; Terminal_Base_2_1@2 top_s 18.9 -> 14.0 (IN 4.89 m) grade 10.80 -> 17.39 %; route7 half-width 3.32 m / route9 3.00 m; mouth_z unchanged. NO BUILD — the 54 % east ramp needs 14be's plate-edge full-depth point (not landed) to give the run back; ramp_in_road measured 0 in BOTH the owner's 1.0.335 patch and the lane's r3b build
OTHH  patch    base 88de7fec   lane v2othhramp       2026-09-14T20:43:50  /tmp/harness/v2othhramp.osm  [MISSING]  — CLOSING OTHH build of lane v2othhramp (claude/v2othhramp caf7b9cc; the three coupled items of RULINGS 14bi): rc 0, 649.9 s, ways 1015, nodes 23714, body_sha 87ba777c8a94, shared repo UNCHANGED, verify defects {} (rows 7877). MATCHED CONTROL at the same tree = /tmp/harness/v2othhrampBASE.osm (worktree v2othhrampbase at bdd28759 = main 88de7fec + the v2othhfix half-width merge, rc 0, 511.9 s, body_sha b60c2dd4502b, artifact ledger cc0ead55f1f2 — a later --base-arm at that tree is served from it). A/B: law-true 8939 -> 8957, airside 8854 -> 8851, ADJUDICATED 7623 -> 7620; ramp_in_road 0 -> 0; hairline_pair 1316 -> 1337; airside vertices 22 of 20,001 moved > 0.02 m worst 0.060 m and 0 over 0.1 m; service-road vertices 0 of 116 moved > 0.02 m worst 0.010 m. Pinched grades east route7 53.95 -> 17.17 %, west route9 17.39 -> 18.06 %
OTHH  patch    base bdd28759   lane v2othhramp       2026-09-14T20:44:05  /tmp/harness/v2othhrampBASE.osm  [MISSING]  — MATCHED CONTROL for lane v2othhramp: main 88de7fec + the claude/v2othhfix half-width merge, NONE of the three 14bi items. rc 0, 511.9 s, ways 1010, nodes 23605, body_sha b60c2dd4502b, artifact ledger cc0ead55f1f2, shared repo UNCHANGED, verify defects {} (rows 7881). Built in ritual worktree v2othhrampbase
OTHH  rebake   base bdd28759   lane v2othhramp       2026-09-14T20:44:06  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhramp  [MISSING]  — MATCHED dry --stage structures TRIPLE for RULINGS 14bi: r0_base (bdd28759 = the half-width margin alone), r1_plate (the plate edge alone), r2_all (all three). tunnels 40 -> 42, wall corridors 25 -> 27, refusals 26 -> 26. EAST MOUTH Terminal_Base_2_5@0/a along the axis: wall-band end 38.89, PAD edge 36.50 (14at's reading), COVERING-PLATE edge 29.00, ramp top 40.00 with the half-width margin (44.00 without) — 9.9 m of uncovered corridor is ramp, grade 53.95 -> 17.17 %. WEST Terminal_Base_2_1@2: the plate covers the whole corridor so climb_from stands at the wall end 6.30 (the pad read 6.00), 17.39 -> 18.06 %. r1 and r2 are BYTE-IDENTICAL: §34 (10)'s generalisation changes nothing at OTHH beyond the §34 (9) pinch. dry.sh is the arm runner; basetree/ is the git-archive base tree
OTHH  patch    base 106459fa   lane v2objcut         2026-09-15T09:44:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/r4_OTHH/structures.json/structures.json  [MISSING]  — §33 (6) OTHH matched pair (base /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/b4_OTHH/...): corridors/tunnels/wall_corridors/basins/plates/door_wells ALL BYTE-IDENTICAL (9/44/73/10/2/4); +51 named §33 (6) refusals only.
OTHH  patch    base f32fb08c   lane v2channel        2026-09-15T10:23:51  /tmp/v2channel/r3/br_OTHH/structures.json  [MISSING]  — v2channel round-3 DRY structure replay (branch), paired with base OTHH at main 46b219d8 in /tmp/v2channel/r3/base_OTHH
OTHH  patch    base 106459fa   lane v2objcut         2026-09-15T10:44:12  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/c6_OTHH/structures.json/structures.json  [MISSING]  — r2 §33 (6) C lane arm at claude/v2objcut 3b3259dd (base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/b4_OTHH/...)
OTHH  patch    base 395bd09a   lane v2channel        2026-09-15T10:52:05  /tmp/v2channel/r4/br_OTHH/structures.json  [MISSING]  — v2channel round-4 DRY structure replay (branch, §45 (13)); base arm at main in /tmp/v2channel/r4/base_OTHH
OTHH  patch    base f912ba81   lane v2objcut         2026-09-15T12:02:00  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e1_OTHH/structures.json/structures.json  [MISSING]  — r3 lane dry --stage structures at claude/v2objcut edf1e3c0; matched base arm at main f912ba81 in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e0_OTHH (LEMD) / /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e2_OTHH (OTHH, run 2 - run 1 e0_OTHH read 7 corridors against run 2's 9 at the SAME sha: main's object-corridor reader is NONDETERMINISTIC at OTHH, reported).
OTHH  patch    base 9306c56d   lane v2othhdet        2026-09-15T13:10:23  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhdet/runs/g1/structures.json  [MISSING]  — v2othhdet CLOSING dry --stage structures arm on claude/v2othhdet 9306c56d (lane-local mod-cache overlay, shared corpus). N=6 runs (g1-g4,h1,h2) SEMANTICALLY IDENTICAL, sha 1cafb197257c96cd over every non-timing key. Base arm = git archive 118d2c40 into scratchpad/v2othhdet/basesrc, run othh_base2. BASE vs LANE: corridors 9 / tunnels 44 / wall_corridors 73 / basins 10 / plates 2 / door_wells 4 all byte-identical IGNORING id; corridor_refused 120 the same SET, now sorted; the ONLY change is tunnel-object:tunnel1.obj@0 <-> @1 swapping placements dsf:obj14051/14052 (the 14av tunnel-wall pair) because @k is no longer the input index. structures.json embeds wall clocks (wall_s, *_stats, grade_read, basin_unions) so a raw file sha is NEVER a determinism instrument - compare the non-timing keys. Pre-fix arms r1-r4 beside it; the 7/42 of 15ar is NOT reproducible on the refreshed corpus.
OTHH  patch    base 0f0c1b6c   lane v2shellwall      2026-09-15T14:17:03  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2shellwall/lane_OTHH/structures.json  [MISSING]  — OTHH dry 'planar --stage structures' on claude/v2shellwall: corridors 9 (object cuts 0 B), tunnels 44, basins 10, door wells 4 - OTHH reads ZERO signature-B cuts, so no OTHH corridor reaches structure_geometry.geometry_from_trench at all and every OTHH retaining_wall/tunnel_wall corridor comes out of geometry(), which this lane does not edit by one line. The matched BASE arm was set up (git archive 0f0c1b6c into scratchpad/v2shellwall/basesrc with the worktree's mounts symlinked) and NOT completed.
OTHH  capture  base 7f80dc71   lane v2shoulderband   2026-09-16T09:10:47  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/sb/r2/cap/OTHH.pkl  [MISSING]  — OTHH capture carrying §40 (5) (421 s, 20,966 vertices / 874 faces, guard UNCHANGED). §40 (1) shoulder 6 cells / 107,118 m2, 20 vertices beyond the strip (worst 134.7 m) -> band 93,762 m2 / 0 beyond, remainder 13,357 m2. THE END CAP IS WORTH +16,602 m2 HERE (77,160 -> 93,762): the largest end-corridor gain of the five
OTHH  patch    base 7f80dc71   lane v2shoulderband   2026-09-16T09:10:47  /tmp/harness/v2sb_OTHH.osm  [MISSING]  — closing OTHH build of v2shoulderband r2: rc 0, 531.8 s, ways 1045, nodes 23677, body_sha 99929f132a03, artifact ledger ae7a9e70a91f, optimal, v2-verify 208 rows, every §40 DEFECT family ZERO, shared repo UNCHANGED. Census law-true 2,057 adjudicated 653
OTHH  mesh     base d0de7c8a   lane shorewater       2026-09-17T19:03:32  /tmp/harness/tile_shorewater-after/Data+25+051.mesh  — tile +25+051 built in default_xplane mode on claude/shorewater d0de7c8a (tag shorewater-dx, wall 3945.6s, shared repo UNCHANGED); its DSF is /tmp/harness/tile_shorewater-after/Earth nav data/+20+050/+25+051.dsf. Water-datum audit: water-terrain triangles on the default-landclass LAND band 4806 -> 0, raised water on mesh-land 2162 (3.51 km2) -> 16 (3 m2); mesh SEA 95966 tris all 62914 vertices at 0.000. NOTE the auto_patch OTHH stage took ~55 min in 'Classifying & building the planar map' in this tree, twice.
OTHH  rebake   base 31b7ad1b   lane v2doorwellperf   2026-09-17T20:46:36  /tmp/harness/v2doorwellperf/lane_OTHH/structures.json  — THE FIRST OTHH dry 'planar --stage structures' replay that COMPLETES on the NEW pack (Aeroscape OTHH Hamad Intl, DSF sha 7adb2cb0), claude/v2doorwellperf 8c6e73e9 (RULINGS 17k (a)): rc 0, 1385.99 s real, max RSS 29,183,950,848 B (29.18 GB), wall_s load 22.292 classify 119.842 structures 1243.324, grade_read 125.89 s / 14,161 calls / 2,187 unions / 7,181,361 vertices, door read_s 611.66 (11,513 placements, 7,017 sill witnesses, 140 families, 489 regions). STRUCTURES LINE: corridors 5 (object cuts 0 B, basin placements claimed 0), door wells 4 (refused 485), sunken roads 1 (refused 18), tunnels 42, basins 20, corridor refusals 137, tunnel refusals 45, basin refusals 131; wall_corridors 73, plates 2, channels 1, pinched_ramps 2, buried_skipped 1449. Before the fix the same replay ran 56:40 / 25.8 GB (scout wallfit) and 2418.58 s / 28.60 GB and 2051.48 s / 31.42 GB on the two intermediate arms, all three killed without output. Lane-local O4_DSF_CACHE_DIR + O4_AIRPORT_MOD_CACHE_DIR (mod-cache overlay under scratchpad/dwp/mc, the five packs read are real copies). NO base arm exists: main does not terminate on this pack.

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

