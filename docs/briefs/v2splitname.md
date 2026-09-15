# Brief pack — lane `v2splitname`

Base: main `381004d7` · generated 2026-09-14 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Split files are keyed per distinct offset: the OTHH tunnel wall collision (RULINGS 14at)

## The brief

THE SPLIT-FILE NAME COLLISION (RULINGS 14at; the owner's missing tunnel wall at OTHH 25.2697569, 51.6055534). `Ortho4XP/src/auto_patch_v2/airport/obj8_split.py::body_resource_name(resource, body_id)` names the written split file on resource + body id ONLY (`Objects/tunnels/tunnel1__b0.obj`), while `authored_offset` is per PLACEMENT (the re-seated anchor): OTHH's `tunnel1.obj` is placed twice (placement plan idx 14051 anchor 25.272571,51.612887 offset [-8.885, 9.55, -84.422]; idx 14052 anchor 25.269719,51.605679 offset [9.049, 9.55, -50.104]) — both write the same file, the file bakes 14051's offset, and 14052's wall renders 38.7 m from its DSF row. Same class as the LEMD note at `obj8_split.py:649`. FIX: the split file is keyed on resource + body id + the OFFSET (a distinct file per distinct baked offset: `__b<k>_<n>.obj`, n = the index of that offset among the resource's distinct offsets, or a short hash of the offset triple — choose the one that is STABLE across builds and say why), threaded through every `body_resource_name` call site: `airport/placement_plan.py`, `airport/obj8_split.py`, the writer (`airport/placement_write.py`), and `dsf_write.py`'s row rewrite (`src/auto_patch/` — check `blast.py`); placements sharing an identical offset still share ONE file (no file explosion: count files before → after at OTHH — 1,849 body files today). Twins: two placements of one resource with different offsets → two files, each baking its own offset, each DSF row pointing at its own file; two placements with the same offset → one file. Consumer census: every reader of the split file name (`.anchor_bak` restore, `obj8_split_report`, the rebake replay `tools/v2_rebake_replay.py`, the seat census `seat_feet_census.py`). Measure: the 1.0.334 OTHH products (`Patches/+20+050/+25+051/o4_v2_placement_OTHH.json`, READ-ONLY) — list every (resource, body) written by > 1 placement with distinct offsets at OTHH (and dry at LEMD/HECA/KCLT/SPJC from registered plans): the collision population before; after: 0 collisions; the OTHH wall at the coordinate rendered at its own row (the split file's baked offset = 14052's). ONE OTHH build (patch + object stage — the tile's object stage runs after the mesh: use `build_airport.py OTHH --tile 25 51` or the rebake replay on the 1.0.334 products, lane-local `O4_AIRPORT_MOD_CACHE_DIR` overlay so the pack rewrite lands lane-local — say which). Files: `airport/obj8_split.py`, `airport/placement_plan.py`, `airport/placement_write.py`, `src/auto_patch/dsf_write.py` (if that is where the rows are rewritten), tests. NOT yours: `planar/`, `solve/`, `classify/`, `constraints/`.

## Bars

- OTHH: (resource, body) pairs written by > 1 placement with distinct offsets: N → 0; `tunnel1__b0`'s two placements → two files, each baking its own offset; the wall at 25.2697569, 51.6055534 rendered at its DSF row (the baked offset = placement 14052's).
- Body files at OTHH 1,849 → 1,849 + (collisions resolved) only; identical-offset placements still share one file.
- LEMD/HECA/KCLT/SPJC dry from registered plans: collision counts before → after (0), names.
- The `.anchor_bak` restore and `obj8_split_report` read the new names (twins); suite twice.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/airport/obj8_split.py`, `Ortho4XP/src/auto_patch_v2/airport/placement_plan.py`, `Ortho4XP/src/auto_patch_v2/airport/placement_write.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/planar/`, `Ortho4XP/src/auto_patch_v2/solve/`, `Ortho4XP/src/auto_patch_v2/classify/`

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

## RULINGS

## 2026-09-14at v2othhfix round 3 MERGED (76518d99): full depth at the building wall (25 % from 37 %); the pack paints NO road-edge line as geometry at OTHH; the missing tunnel wall is a split-file NAME COLLISION — lane `v2splitname`

Lane `v2othhfix` @ a4b7801d (OTHH build `v2othhfix_r3b`, ledger
4afb62b3f6a1, verify defects {}, ADJUDICATED 3,204 → 3,174; suite
1,495 on main). §34 (9) (5) `covered_start`: the climb-from moves back
to where the axis leaves the building pad — `@0/a` +2.4 m of run
(the pad edge measures 2.4 m, not the owner's ~4), grade 36.98 →
25.18 %; `@2` 11.05 → 10.80 %; mouth_z unchanged. §34 (9) (4)
`road_edge_witness` landed (lazy read of the pack's `markings` draped
objects; keys `road_edge_line_reach_m` 6 / `_parallel_deg` 15) — and
OTHH HAS NO WITNESS: no `markings` object within 60 m of the east
mouth and no thin pavement source within 40 m; the only markings near
the other two are `StopLine1_*` bars 32–54 m away across the taxiway.
The white edge line the owner sees is baked into the road texture or
the orthophoto, not geometry. Road edges unchanged (route7
byte-identical); airside 2 of 16,810 moved > 0.1 m (pad-edge corner
joints, +0.10/+0.12); corridors 40 → 40; `road_cross_section` 6 → 14
(+8 rows 500 m away at 25.268, 51.606–51.610 — not the pinch, owed a
look). A publication crash (the pinched record's arity) caught by the
build, guarded by a twin.

* THE MISSING TUNNEL WALL (25.2697569, 51.6055534): `tunnel1.obj` is
  the only OTHH tunnel resource placed TWICE (idx 14051 and 14052,
  anchors 38.7 m apart in plan); `obj8_split.body_resource_name`
  keys the split file on resource + body id only, so both placements
  write `Objects/tunnels/tunnel1__b0.obj` and the file bakes 14051's
  offset — placement 14052 renders its wall 38.7 m from its DSF row.
  The layout is innocent (`tunnel_wall` −10948 and a ramp are at the
  coordinate). Same class as the LEMD `__b0` note at
  `obj8_split.py:649`. Lane `v2splitname` BEFORE app 1.0.335.
* OWNER (intent, the painted line): the engine reads no white line at
  OTHH's east mouth. Options: (a) a per-airport `road_edge_inset_m`
  (the line's offset inside the road face edge — the owner measures
  it once); (b) a coordinate on the line from the owner → we derive
  the inset; (c) accept the face edge. The east ramp ends at the face
  edge today.

## 2026-09-13cn SPJC viaduct attributed: §16g (3) EXPELS the body it should bind — §16g (6) written, lane `v2connector`

Scout `v2spjcramp` on the owner's 1.0.329 SPJC products (no build; read-only).
The access-road viaduct `SPJC_LIMANUEVA_xp11_007__b0` (span 549 m, 16
components, one body) has `unit_of = None`: §16g (3)'s connector test (span
≥ 200 m AND end-ground spread ≥ 0.5 m; here 11.58 m) names it a connector and
`_bind_plan_wide` drops it from the terminal unit `fu:0:0@cluster_pad`
(datum `building6` 19.5604) WITHOUT writing the promised station cut, so it
falls to §16c's low-side foot: the −8.308 m footing bottom is pinned to the
mesh (19.058), authored zero lands at 27.366 — **7.81 m above the unit
datum**, the deck 18.3–19.7 m over the apron, the south abutment slab +8.96 m
in the air; the only contact with the mesh is the footing bottom at s 0–50 m
(−0.02 … +0.15). `xp11_010__b0` (span 1,030 m) is expelled the same way,
0.99 m LOW. All eleven LIMANUEVA placements share ONE DSF origin/heading in
the source pack (a shared-datum pack); nine chain into the terminal unit, the
two longest are thrown out. The terminal did not move 1.0.327 → 1.0.329
(`SPJC.rebake.json` byte-identical across three frames; `building6`
[18.84, 20.13] in all). Second, smaller class: no road face reaches the
viaduct's low end (nearest road chain 655.7 m; OSM `highway=service`
−10092/−10616 within 25 m are absorbed into `pav49`/`pav46` under the
free-road ruling), so §37 (6)/§34 grade nothing there — at the correct datum
the south abutment still wants +1.56 m of fill, NE columns up to 2.4 m of
cut. `--why-at` not run (no capture; no solved vertex within 52.6 m).

* RULING (the owner's words 13ce: cutting is allowed ONLY for "very long
  connecting pieces like the elevated rail at HECA"): a connector CONNECTS
  two units. §16g (6) written: (1) connector = span ≥ 200 m AND spread ≥
  0.5 m AND its two ends touch two DIFFERENT units (or one unit and open
  ground); a body whose every contact chains into one unit is that unit's
  member however long; (2) an identified connector is seated on its
  high-end unit's datum until the station cut is written — it never falls
  to the low-side foot; (3) the shared-DSF-origin pack row is recorded as
  `authored_unit`, and a partition separating siblings raises
  `unit_split_authored` (WARN).
* Lane `v2connector` (Opus, brief pack) implements §16g (6) in
  `airport/footprint_unit.py`; closing test SPJC through the harness (the
  two bodies at the datum, `unit_connectors_cut` 0 there, HECA rail still a
  connector).
* The residual (+1.56 m fill at the abutment, no road under the viaduct)
  stays open under §37 (6)/§34 — the absorbed service ways are the next
  read once the datum is right.
* Not verified: the 1.0.327 placement plan (overwritten; app builds are not
  in the artifact ledger); `artifact_ledger.py --history` does not exist as
  a CLI — the brief was wrong to name it.

## Tool: obj8_split_report

| `Ortho4XP/tools/obj8_split_report.py` | THE OBJ8 SPLIT, DRY-RUN (spec `object-placement-spec.md` §4 / §6 / §7; owner RULINGS 2026-09-11b) — what a pack's object stage becomes once placements are AGL, objects are cut into their RIGID BODIES and each body carries its own anchor. Reads only a build's own two products — the re-seat plan (`<ICAO>.rebake.json`: the pack read once, its welded parts and the ε-contact graph) and the emitted DESIGN SURFACE (`<ICAO>.graded.json`, whose `building` faces are the object pads and `structure_rim` breaklines the basin walls) — and NEVER opens the pack for writing, never reads the DSF and never builds anything. Prints per placement the bodies, their §6 class, each body's anchor point / reason / authored offset, the files that would be written and the placements KEPT WHOLE with the reason (`one_body`, `anim`, `unparsable`); `--write-into DIR` writes every cut file into a scratch dir and parses each back through `airport/obj8.parse_obj8` (LEMD 13,924 files, OTHH 65,360, all parsing back with the written triangle count, 2026-09-11); and prints §7's CENSUS — the design surface at a body's ANCHOR against the surface under each of its ground-contact FEET, the |Δ| histogram `seat_feet_census.py` prints from a mesh and a seat result, read instead from the plan and the design surface so the two are comparable. A foot or anchor outside every graded face reads `off-surface` and is never guessed at (the DEM governs there and this tool does not open the DEM). `--no-cut` for body counts only, `--filter`, `--json`, `--split-tol` to override `[placement] split_tol_m`. ROUND 2 (owner RULINGS 2026-09-11e, spec §9): the bodies are COARSENED (bodies of one placement whose intended-zero terrain heights agree within `split_tol_m` are one file, the senior body's anchor; an elevated body joins the nearest ground group) and each anchor is the GENERIC one (the footprint point where the design surface equals the body's zero; a body with authored relief beyond its skirt takes its low-side foot and is reported with the residual) — LEMD 302 placements -> 985 files (3.26x), OTHH 954 -> 1,172 (1.23x). §13 (owner RULINGS 2026-09-11r/s): an ELEVATED body — one whose lowest authored vertex, or the `y_zero` of the anchor the generic rule gives it, stands above `[rebake] elevated_base_m` — NEVER has a file of its own; it joins its CARRIER (the same placement's ground body with the largest plan overlap, else the nearest) at its authored offset, and a placement with NO ground body is KEPT WHOLE with reason `footless`. The report prints the two classes by name — `elevated bodies as own files` (BAR 0) and `footless placements kept whole` — because the FEET histogram cannot see this defect: the writer shifts an elevated body so its own lowest vertex lands on the terrain and every foot then reads perfect (LEMD's 218 roofs/decks/tower parts censused green while the sim was broken). Measured on matched pack copies: LEMD own-files 278 -> 0, files 1,099 -> 828, feet > 3 m 1,060 -> 151, worst 34.06 -> 13.75 m; OTHH 1,203 -> 333 files, feet > 3 m 952 -> 6. ROUND 3 (owner RULINGS 2026-09-11f, spec §10): the write half RESTORES every `<obj>.anchor_bak` in the pack before any file is written (counts in the plan's provenance), and a LINE OBJECT authored as one component is cut into SEGMENTS by triangle station (`--line-segment M` overrides `[placement] line_segment_m`; 0 disarms it) — LEMD 897 segments from 271 one-line bodies, 985 -> 1,086 files, census `> 3 m` 30 -> 25; OTHH 1,187 files, `> 3 m` 0. `--write-pack PACK_COPY` runs THE WHOLE WRITE HALF into a pack COPY through `airport/placement_write.apply_plan` (cut files, DSF + backup + provenance, dump-cache refresh, `o4_v2_placement_<ICAO>.json`) and reads the written DSF back; it REFUSES a live X-Plane install. The census also splits the feet over 0.3 m into BURIED (lawful) and FLOATING (the defect the eye reads). `--rows-near LAT,LON[,R]` (lane `v2padcluster`, 2026-09-14) is that SAME projection selected BY PLACE — every body whose ANCHOR is within R metres (default 40) of the coordinate, nearest first, each row carrying its `site_m` — because the owner names a defect by coordinate and the shapeIDs in a report go stale between builds while a coordinate does not; `osm_site --at/--contains` answers the other half of a site question (which emitted FACES cover the point) and is not re-spelled here. Promoted from the scout `v2heca331`'s scratchpad `site.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse): the 14g attribution, then §16g (10)'s per-site bars; its graded-face half was already `osm_site`'s and was NOT copied. Twin: `tests/auto_patch_v2/test_v2objsplit.py::test_rows_near_selects_the_same_rows_BY_PLACE`. `--rows SUBSTR,SUBSTR` (lane `v2canopy4`) prints the PER-BODY rows of the placements named — the body's anchor (point, surface z, `y_zero`, reason), its ground-contact feet, its worst foot signed with |Δ|, and the 0.3 m verdict — for the owner's named sites (`OldTerminal_FSX-LEMD38,-LEMD84,-LEMD60`); it is a PROJECTION of the one census pass, never a second instrument (the bins, feet and worst list are identical with and without it, twinned). §14 (owner RULINGS 2026-09-11u/v, lane `v2carrier`): a FOOTLESS placement is CARRIED — written as a body file at its CARRIER's anchor with the carrier's `y_zero` (the footed body of its UNIT it abuts with the largest contact, else the nearest, else the largest) — a BASIN resource is never split and anchors at a RIM point where the design surface equals its zero (`rims` wired at last), and bodies of one resource that OVERLAP IN PLAN bind whatever the contact graph says. The report prints the four §14 bars (`footless at datum` 0, `footless on ground` 0, `basin bodies split` 0, `spread`) beside §13's, from `airport/placement_carrier.census_v14` — the same call `seat_feet_census --placement-plan` makes over the same plan shape, so the two instruments are one code path. Measured on the app's 1.0.315 LEMD frame: the four footbridge resources at the terminal's zero 616.65 (deck bottom road + 4.4-5.0 m, was ON the road), `Terminal4SAT_pink-LEMD01` at its terminal's 597.43, the basin's three resources one file each on ONE rim vertex (zero spread 7.0 m -> 0.00, parapet +2.99 above the rim), files 828 -> 855, round trip OK, row census `> 3 m` 17. Twin: `tests/auto_patch_v2/test_v2objsplit.py`. §15 (owner RULINGS 2026-09-11ae, lane `v2roofcarrier`): the CARRIER IS WHAT THE BODY STANDS OVER — chosen across the whole UNIT, every resource alike, by largest PLAN OVERLAP beneath, else largest contact, else nearest (§13's same-placement scope and §14's contact-first order are superseded; the pack names its roofs as their own resources, so the walls a roof rides are almost never its own file); the plan-overlap BOND is RE-CUT where a bound group's intended zeros span more than `split_tol_m` (a rigid body is never wider than the terrain it can stand on; BASIN exempt); DUPLICATE ROWS of one resource identical in lon/lat/heading are ONE placement, all of them replaced (`--write-pack` reports `duplicate rows of a SPLIT placement ... surviving after the write`, bar 0); an anchor or foot on no graded face is marked OFF-SHEET and excluded from every comparison and bar; and the report prints §15 (3)'s `stands-over float > 0.5 m` from `airport/placement_carrier.census_v15` — `float = zero - zero_beneath`, the class NEITHER the feet histogram nor §14's bars can see (a carried body has no feet at all), barred at 0 for CARRIED bodies and reported for footed ones. §16 (owner RULINGS 2026-09-11ai, lane `v2skipped`): the report adds the POPULATION census (`placement_carrier.census_population`: `rows on the datum outside the plan` — the resources the SEAT-era thickness gate dropped, which keep the pack's shared-datum row and render where the datum is, bar 0 — beside the lawful skips and the multi-anchor class, reported not barred) and `census_v16`'s `float = zero - ground_under_geometry`: the ground read under the body's OWN parts (`geom_box` / `foot_boxes`, the median of the part-box centres) and never under its carrier's box — `CARRIED bodies whose carrier's zero is over 1 m from the ground under their own geometry` (bar 0; LEMD 39 -> 0 on matched arms) and `files whose own-geometry ground departs over 3 m from the ground at their row` (26, reported). `--admit-skipped PACK_ROOT` puts the thickness-gated resources of a PRE-§16 plan back into the population by reading their rows from the pack's own DSF (one part per component, no contact graph, the member id IS the DSF row index) — what a build's own plan now carries, for replaying a plan written before the switch; LEMD 25 resources / 25 rows, OTHH 99. §16a (owner RULINGS 2026-09-11aj, lane `v2skipped2`): a CARRIED body is cut where its CARRIER is cut (one piece per carrier terrain group its own triangles stand over, each riding that group's zero; never by the ground under itself), the ground check moved to the carrier's OWN feet (`Candidate.ground_off`, `surface(foot) - y_foot` against the body's zero), and `census_v16`'s carried number demoted to INFORMATION — the bar for a carried body is §15 (3)'s `zero - zero_beneath`. The report prints `carried bodies left uncut by the ground` / `cut by their CARRIER into N piece(s)` and, beside the §15 bar, how many of the carried floats stand over a body the law REFUSES as a carrier. LEMD carried float 58 → 4, files 1,591 → 1,328, plan stage 9.9 → 6.3 s; OTHH 7 → 39, 46.4 → 60.2 s (both OTHH bars missed and reported). 11ak (lane `v2skipped3`): the CARRIED bar's `beneath` is the carrier THE LAW CHOSE (`merged_into`, resolved by identity over every row that reads a zero — a carrier written WHOLE names its MEMBER RESOURCE, which is the whole of OTHH's residual), and a body the law REFUSES as a carrier is counted and named as its own class, `carried over a refused body`, with how far its own feet stand off; §16 (2) also cuts BY FOOT (`placement_cut._LineCutter.foot_groups`: the feet grouped by the zero each says the body has, `surface(foot) - y_foot`, each triangle joining the group of the foot nearest it in plan) — the class no ground cut can see, a body whose FEET are authored over metres of relief on terrain that barely moves, which is exactly what §16a (2) refuses. The re-cut line prints the three cuts (terrain / triangle / foot). LEMD carried float 4 → 0, refused carriers 117 → 21 (13 of the residue are rim-anchored BASIN bodies the foot cut is exempt from), files 1,328 → 1,371, plan stage 6.2 → 5.66 s; OTHH carried 42 → 0, refused 55 → 19, files 1,679 → 1,622, plan stage 59 → 31 s (`solid_components` read in one sort instead of a mask per component; `bind_plan_overlaps` swept by the hull's south edge). 11al (lane `v2basincarry`): a BASIN body is EXEMPT from §16a (2)'s ground test — its zero is the RIM (§14 (2)) and its floor feet are authored below it by construction — so it may carry, and the report prints `§16a (2) basin carriers` (how many basins, how many the feet test would have refused) beside the refusal set: LEMD refused carriers 21 → 8, OTHH 19 → 4, carried float 0/0 unchanged. §14a (owner RULINGS 2026-09-11ap item 6, lane `v2basinring`): a BASIN body follows its RING. §24 (1) puts the rim vertices at the APRON's level, so the ring is not level (LEMD's T4 pit 597.68 … 599.52 over 59 nodes) while §14 (2) wrote every basin body at ONE rim point — the owner's "gap between wall and apron", +0.71 / −1.13 m, while the §14 `spread` bar read 0.01 because it measures the pit's bodies against EACH OTHER. `airport/basin_ring.py` (NEW: the whole law — `arcs_of`, `ring_arcs`, `member_kind`, `ring_bar`) cuts the ring into ARCS whose z agrees within `split_tol_m` and cuts each basin body's WALL BAND by them, one piece per arc anchored at that arc's rim point (the interior remainder keeps §14 (2)'s single point: the trench floor is one level); and a member authored AT THE RIM PLANE but standing inside the ring is a FLOOR body that takes §16 (3)'s ground under its own footprint, never the rim, never a carrier. The report prints the RE-DEFINED bar — `§14a spread of a BASIN RING = max |wall base − ring z| over its nodes` (bar ≤ `split_tol_m`), with the nodes on an arc the pit has NO WALL on reported beside it — and the `§14a basin FLOOR members` / `basin bodies cut by the ring's ARCS` counts. It needs the rings WITH their heights (`census_v14(rims=..., arc_cap=..., counts=...)`; `RimRing.z`, and the `basin_arc_wall:<ref>#<k>` counts keys the cut writes are how the bar tells "no wall here" from "the wall is written in the interior piece"). Matched arms on the app's 1.0.319 LEMD frame: the ring bar 1.12 m / 9 nodes over → **0.18 m / 0 over**, `LEMD13__b0` off the rim and onto its own ground, files 1,371 → 1,394, feet > 3 m 518 → 412, floating 9,509 → 9,014; OTHH's 21 basin carriers and its whole foot census byte-identical. §16b (owner RULINGS 2026-09-11ap, lane `v2owncut`): the TERRAIN CUT IS PRIOR AND UNIVERSAL and is read on the body's OWN WRITTEN TRIANGLES — including everything the writer will put in the file (`placement_cut._LineCutter.all_tris`: a placement the plan reads as ONE body is written as the WHOLE object, which is why `green-TEJ3`'s 4-triangle part read 0.22 m of ground while its 2,342 m file stood +16.22 m over it) — so a CARRIED body is divided by the ground under itself first and §16a (1)'s carrier cut runs inside each piece; §9's coarsening additionally requires PLAN CONTIGUITY (`[placement] coarsen_reach_m`, 30 m) and acts WITHIN a terrain group (the pieces carry the ground they stand on, or the very next pass welds them back); each PIECE finds its own carrier, and a FALLBACK candidate (contact / nearest / largest, no plan overlap) is refused unless its zero is within `split_tol_m` of the ground under the piece (`carrier_refused_far_from_carried_ground`). The report prints `census_v16b`'s two bars over the WRITTEN geometry the plan now publishes per body (`geom_pts`, one sample per 10 m cell, thinned to 32 by the farthest-point walk): `carried piece float over its own ground > 0.5 m` and `body wider than its terrain group`, both bar 0, with the BASIN exemptions (§14 (2) / 11al) counted apart and the wide residue split by class. `--coarsen-reach M` overrides the contiguity reach. Measured on the app's 1.0.319 LEMD frame: the owner's item 3 +10.74 → the plate ON the roof beneath it (618.58 vs the group's 618.60), item 5 +16.22 → 620.38 vs 620.27, `Terminal4_48` zero-vs-ground −4.02 → median −0.01, `Taxisigns-SENRG` 38 of 80 bodies over 0.3 m → 12 of 419; files 1,371 → 3,272 at the amended 100 m reach (4,633 at the refuted 30 m), plan stage 5.6 → 10.1 s (bar ≤ 8 s MISSED, reported). §16c (owner RULINGS 2026-09-12b/12d, lane `v2atom`): THE CONNECTED COMPONENT IS THE ATOM — `--torn-seams PACK_ROOT` prints the TORN-SEAM CENSUS over a WRITTEN pack (the plan argument is then the WRITTEN `o4_v2_placement_<ICAO>.json` and `--graded` is not read), and the same census prints automatically after `--write-pack`: sibling files of ONE placement that share an AUTHORED VERTEX (the key `obj8.solid_components` welds on, `round(x, 3)`) are two halves of one connected solid written at two zeros, with the base step per seam, the step histogram, the worst list and the per-class breakdown, and §10's line segments / §14a's basin arcs — the only lawful station cuts — counted APART.  Two bars, both 0: `torn seams outside line/arc pieces` and `single-component resources in >= 2 files`.  The instrument is the scout `v2lemd320`'s `tear.py`, promoted on its second use, and lives in `airport/placement_seams.py` (`census_torn_seams` / `census_torn_seams_lines`, re-exported through `placement_census`).  Measured on the live 1.0.320 LEMD pack it reproduces the owner's four sites exactly (`HANG3` 10 files / 14 seams worst 3.05 m; `green-LEMD50` 7 / 11.12 m; `Bridge2` 8 / 11.72 m; `green-STRT4` 53 files, `__b44` 16.29 m) and the class (2,554 seams, 1,994 over 0.30 m).  On matched replay arms the law takes LEMD 723 -> **0** seams and 128 -> **0** single-component splits (files 3,253 -> 2,804, plan stage 13.5 -> 10.2 s over 3 runs, round trip OK), OTHH 639 -> **1** and 165 -> **1** (files 1,897 -> 1,898). §16c (6) (RULINGS 2026-09-12h, round 2): `--contact-eps M` overrides `[placement] contact_eps_m` (2 mm) — components of ONE resource whose geometry comes within it, or whose parts the rebake plan's ε-contact graph already links, BIND into one rigid body for anchoring (one zero, the senior component's carrier): OTHH's `OTHH_Fuel_02_LOD0_007` carries two components 0.4 mm apart that the millimetre weld key reads as separate.  LEMD files 2,804 -> 2,776, seams stay 0, `Terminal4_48` zero spread 3.58 -> 0.69 m, plan stage 9.6 s (main 13.5). ROUND 3 (RULINGS 2026-09-12j): the entry now runs inside `harness/shared_repo_guard`'s WRITE GUARD and its before/after audit (a round-2 OTHH `--admit-skipped` run had created `Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text` in the SHARED repo with both lane-local cache env vars exported and nothing refused it); every run prints `[guard] shared repo UNCHANGED`.  `--rigid-reach M` overrides `[placement] rigid_reach_m` (2.0) — §16c (8): SOLID components of one resource within it chain into ONE rigid cluster, which is the atom of the BODY as well as of the cut (LINE objects excluded).  `carrier_fill_min` is DELETED from carrier candidacy (§16c (7)); the CLASS exclusion stays.  LEMD: `HANG3` 6 files / 1.37 m -> 2 / 0.45, `green-STRT4` 23 -> 15 files (spread 8.90 -> 3.73), files 2,776 -> 2,121, §16b wide 1,405 -> 967, seams 0, round trip OK; five largest rigid clusters are all SINGLE components (5,157 / 2,890 / 2,514 m — fences and VOR markers, not chained) and `green-TEJ3` stays 9 components / 9 clusters. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. **§17 CRITICAL MOTION IS READ** (owner RULINGS 2026-09-12am (2), lane `v2objmotion`): the graded surface's FACE ROLE under every foot (`airport/placement_boxes.GradedRoles` / `graded_roles_from_doc`, built from the SAME parsed `<ICAO>.graded.json` the sampler and the pads are, senior face by `precedence.toml`'s authority order, a 55 m grid over the faces' boxes) joined to §7's own float there (`airport/placement_motion.census_motion`, re-exported through `placement_census`): a body with a foot on a ROLLED-ON face (`law.tables.rolled_on_roles`) is ON PAVEMENT and every such foot is judged at `[cockpit] motion_step_m` 0.05 m, named with resource, foot coordinate, face role and SIGN. The block prints the count of bodies on pavement, the feet over the threshold, the worst ten, and the breakdowns by resource / face role / body class / anchor rule / size band, plus what the EYE reads at those feet (floating vs buried over `visual_m`) and the MEDIAN-anchor arm. BASIN bodies are counted APART (§14 (2) / 11al: a pit's zero is its rim and its floor feet are authored below it — they were LEMD's whole worst ten). Measured on the 1.0.320 LEMD frame: 493 of 2,153 bodies stand on pavement, 7,124 feet on 399 over 0.05 m; after the §17 anchor rule 6,635 on 407 (OTHH 6,234 → 3,877 on 113 → 103). RULINGS 2026-09-12ap (lane `v2pavefeet`): `--motion-rows OUT.json` writes §17's PER-BODY projection — one row per written body with its anchor, class, anchor reason and every ground-contact foot (lat/lon, authored y, surface z, face role, on-pavement, float) — the rows `census_motion` itself reads, never a second census (the scout's scratchpad projection, promoted on its second use). (E) THE SAMPLER HONOURS GRADED HOLES: a Delaunay over the emitted VERTICES spans a hole ring with triangles reaching from an apron vertex to a trench vertex, and LEMD read **592.22 m at a point whose ROLE is apron** six metres outside the hole — 12ap's two worst pavement feet (`LEMDblast__b1` +7.18, `Terminal4sBlue-STRT4__b1` −5.08) were that fabricated ramp, and the anchor correction is 6.91 m. A simplex CROSSING a hole ring with a step over `split_tol_m` is struck and a point inside one reads the nearest vertex of that simplex ON ITS OWN SIDE of the ring; measured narrowings: "centroid on no face" struck 8,689 of 47,287 simplices and cost 421 files / 435 off-sheet bodies, and a strike with no side-aware read cost 160. (B) §17 is judged at the GROUND-CONTACT feet — the in-band feet within `split_tol_m` of the lowest (`placement_motion.ground_contact_feet`); `contact_band_m` is shared law and unchanged, BOTH sets are sampled and the wider reading prints beside the judged one so the report states its own attribution. (A) `bind_ground_m` (`[cockpit] visual_m`) bounds §16c (7): a FOOTED body of ANOTHER member keeps the cluster only while its own zero is within it of the senior's, else it keeps its own anchor and is counted — the report prints `bound refused for ground N` with the worst refused disagreement and the widest RETAINED cluster zero-plane span. Matched arms, LEMD main → branch: CRITICAL MOTION 6,640 → 5,400 feet on 407 → 356 bodies, over 0.5 m FLOATING 663 → 128 and BURIED 1,109 → 808 (of which (B) alone 581 → 128 / 816 → 808), worst pavement foot +7.18 → +2.41 m, 74 binds refused (worst 2.38 m), files 2,107 → 2,149, seams 0/0, round trip OK, plan stage 10.19 → 10.03 s; OTHH 3,891 → 2,822 feet on 103 → 74, floating 332 → 12, §14 footless at datum 5 → 4, files 1,252 → 1,269, plan stage 60.8 → 61.4 s (the ≤ 60 s bar missed on BOTH arms). §16b's carried-piece float and wide counts move the WRONG way at both airports (LEMD 111 → 119 / 967 → 983, OTHH 126 → 135 / 75 → 78) and are named. §16d (owner RULINGS 2026-09-13h, lane `v2unboxed`): THE PLAN BOXES WHAT THE WRITER WRITES — a WRITTEN-FRAME bar beside the torn seams, `§16d bodies with written geometry > 1 m outside their geom_box` (`airport/placement_seams.census_outside_box`, printed after `--write-pack` and by `--torn-seams`, bar 0): `geom_box` was the hull of the ADMITTED PARTS while the writer emitted the source object's triangles regardless, so a component no part named (the FS2XPlane origin plate, an exporter's ground paint, a roof plate over the next hangar) rode a zero the body chose elsewhere and NO instrument read it — LEMD 1.0.325 live pack 378 of 2,109 bodies, 8 over a kilometre. Every connected component the writer will emit — draped ones included — is now PLACED: within `coarsen_reach_m` of a ground group's part hull it joins that group and `geom_box` grows to the hull of what the file will contain; beyond it, it is a FOOTLESS BODY §15's search places, or §16 (3)'s own ground (`--coarsen-reach 0` disarms the reach and the component joins the nearest body, the pre-§16d reading). The nearest-footed fallback is CAPPED at the same reach (`carrier_refused_nearest_beyond_reach`), and the COCKPIT block names the worst row by the centre of the BODY'S OWN written geometry, never the placement row (a shared-datum pack puts 96.5 % of its bodies on two points). `plan stage: N.NN s` is printed after the split — the number a round's budget is quoted in, timed exactly where the shipped engine's own `build_splits` call is, without the graded parse or the census. Matched dry arms on the 1.0.325 LEMD frame (the app's own arm reads a MESH sampler where the tool reads a Delaunay over the graded vertices — the two disagree on every surface-driven refusal and the bars are read dry-to-dry): outside-box 390 → **0**, nearest-footed over 100 m 29 → **0**, the four shadow plates +15.94/+15.73/+5.77/+1.72 → **−5.00 on their own ground**, `Cargo-TEJ1` on `NEWCO__b9` roof base 604.95 (bar 0.3 of 605.04), seams 0/0, §15 carried float 0/0, round trip OK, files 2,141 → 2,279, LEMD plan stage 13.6 → 17.8 s and OTHH ≈83 → 86.1 s (both bars missed on BOTH arms, named). It also fixed a latent WRITER defect: the cut file was named by its index in the LIVE body list while the DSF row is written on the plan's `body_id` name, so a body the cut left with no triangle shifted every later body's file one name down (`OldTerminal_FSX-DCNEUN`'s `__b0` row held `b1`'s object). §16d (4)-(6) (owner RULINGS 2026-09-13m, same lane, second frame KCLT 1.0.324): a CARRIED body's components group BY CARRIER — each ATOM (§16c (1)'s, so a rigid cluster is never divided) asks its own carrier question BEFORE the search, counted as `carried bodies cut by ATOM`, where §16a (1)'s after-the-fact cut could only divide the answer the whole body got (KCLT 5,295 carried bodies left uncut against 3 cut; a native pack's master roof model spans 1,774 m); §16c (7)'s 0.5 m ground bound is MEMBER-AGNOSTIC (12ap tested `member != top.member`, and a native pack's one-model-per-material member spans the airport: KCLT's `005_ALB__b9` sank 5.04 m into its pad on a same-member bind to an apron body 500 m away); and a FOOTED body whose ground contacts lie mostly inside one emitted `building` pad reads only the contacts ON it (`anchor_rule.pad_majority`; the anchor reason then says `on pad <ref>`). Matched dry arms at KCLT: `005_ALB__b9` -5.85 -> **+0.02** against its pad, widest retained cluster zero span 5.69 -> **0.64 m**, 473 carried bodies divided by atom, 61 bodies anchored on their pad, `building80`'s on-pad zero spread 1.03 m (the pad's own relief 1.19), §16d outside-box **0**, §15 carried float **0**, round trip OK 477/477, one new torn seam (+0.16 m, one shared vertex, named), files 473 -> 477, plan stage 8.65 -> 8.3-8.5 s. It also exposed a defect the atom cut made visible: a target group holding BOTH a cut piece and an untouched raw was read for its `tris` alone, leaving 990-3,280 triangles per placement claimed by no body (9 of KCLT's 103) for `obj8_split` to hand to the nearest one — the audit reads 0 of 103 after. **COST: plan stage LEMD 17.8 -> 25-46 s and OTHH 86 -> 136 s** (KCLT flat) — the per-atom carrier search, narrowed by a `coarsen_reach_m` span gate, a 64-atom cap, per-atom pids and a set-intersection contact count, and still needing the owner's approval and a Fable-5 review before it ships. |

## Tool: seat_feet_census

| `Ortho4XP/tools/seat_feet_census.py` | THE DRAPE RESIDUAL AT EVERY PLACEMENT'S FEET (RULINGS 2026-09-09ac (3); the placement reading 11e (3), spec §7/§9) — `--placement-plan o4_v2_placement_<ICAO>.json` with `--mesh` (a built mesh) or `--graded` (the emitted design surface, for a dry run with no tile built): per placement of the plan's own rows, `surface(foot) − (surface(anchor) + y_foot)`, the |Δ| histogram (<0.3 / 0.3-1 / 1-3 / >3 m), the same by class, the worst N with lat/lon, and §13's elevated-body / footless-carrier bars. Feet are read from the AUTHORED pack (`.anchor_bak` when one exists). THE SEAT-RESULT MODE IS DELETED (owner RULINGS 2026-09-12s, spec §8) — the name is kept because the INDEX row, `obj8_split_report` and the twins address it by it. Writes nothing to the pack. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. CRITICAL MOTION is named as an instrument limit rather than printed as a zero HERE: §17's motion reading needs the graded face ROLE under each foot, and this tool hands the block none — `obj8_split_report.py` is the entry that takes it (owner RULINGS 2026-09-12am (2), lane `v2objmotion`). §16e (owner RULINGS 2026-09-13k, lane `v2othhdatums`): `--placement-plan --mesh` WAS BROKEN — it passed its bbox as `(lat, lon)` to `MeshElevationSampler`, which takes `(min_lon, min_lat, max_lon, max_lat)`, so at OTHH it asked for a box at lon 25.2 / lat 51.6 and the sampler raised `no mesh triangles inside ... — wrong tile?`; the one place the two orders meet is now `plan_bounds()` and a twin holds it end to end over the sampler's own mesh fixture. The report also prints `§16e bodies on a DATUM` (a crest plate / a deck top) as its own class and EXCLUDES them from §13's `elevated bodies as own files` bar: a datum body's `y_zero` is +5 … +10 m by construction, and counting it there reported the law as the defect (OTHH 0 -> 10 -> 0 with the class printed apart). §16e (3) (Fable 2026-09-13, RULINGS 2026-09-13v, lane `v2bridgecontact`): the report also prints THE BRIDGE FAMILY block (`airport/bridge_family.census_bridges` / `census_bridges_lines`, re-exported through `placement_census`, the same call `obj8_split_report` makes over the same plan shape) — per `Bridge_NN` the deck's own body's world DECK TOP against the land under that bridge's own written geometry (`|deck top - highest land|`, bar `[cockpit] visual_m` 0.5 m), the PER-PLACEMENT zero spread (`max - min` of `surface_z - y_zero` over one placement's bodies; `Bridge_02_CLUTTER_007` is six piers of ONE solid), the CROSS-BRIDGE carriers (a body whose `merged_into` names a file of another bridge, bar 0) and how many bodies publish `bridge_of` and agree with the resource's own tag. The `Bridge_NN` axis is the CENSUS's, never the law's — §16e (3) exists because the name does not name a bridge — so the agreement count is the instrument's own check on the derived relation. Measured on the app's 1.0.326 OTHH frame: `Bridge_01` deck top 3.23 -> 3.96 and `Bridge_04`/`Bridge_05` KEPT -> 3.96 (all three |deck top - land| 0.00, PASS), cross-bridge carriers 2 (unchanged — the bind and the filter are refuted and deleted, see `bridge_family`'s module doc). |

## Tool: v2_rebake_replay

| `Ortho4XP/tools/v2_rebake_replay.py` | The auto-patch-v2 OBJECT STAGE replayed OFFLINE — the synthetic-first instrument for the post-mesh half. `plan PLAN.json MESH --graded G.json` replays and TIMES the PLACEMENT stage over the sampler the app calls (RULINGS 2026-09-12g), with `--sampler`, `--no-batch`, `--src`, `--plan-out` and the `--oracle-write` / `--oracle-check` bit-identity pair; `order ICAO` is the partition-order twin (11j / spec §11a (3)); `disk PACK_ROOT` prints a pack's current bake state from its `.anchor_bak` backups and v1 provenance, read-only. The `plan` subcommand was DEAD from 12j/12s until 2026-09-12 (lane `v2objmotion`): it imported `RebakePlan` from `emit.rebake` (it lives in `model.rebake`) and read the deleted `carrier_fill_min` key before its own SIG-DIFF dropper ran — both fixed, and the sampler now carries §17's face ROLES so the timing is of the plan the app builds. THE SEAT SUBCOMMANDS ARE DELETED (owner RULINGS 2026-09-12s, spec §8): `seat`, `bodies` and `pairs` replayed v1's vertex rewrite and its `o4_v2_rebake_result_*` sidecars, a refuted mechanism. Writes no pack and builds no tile. (A), RULINGS 2026-09-12ap (lane `v2pavefeet`): `plan` also passes `bind_ground_m` (`[cockpit] visual_m`) through its SIG-DIFF dropper, so it times the plan the app builds and still runs against a src that predates the key. §16e (lane `v2othhdatums`): the entry now runs inside `harness/shared_repo_guard`'s WRITE GUARD and its before/after audit, the same one `obj8_split_report.py` and `build_airport.py` arm — `plan` calls `dsf_reader.ensure_dsf_text_path`, which GENERATES a DSF text dump into the mod cache when the cache has none, and a lane worktree MOUNTS `Airport_mod_cache` at the shared repo (the class RULINGS 2026-09-12j caught in `obj8_split_report`); every run prints `[guard] shared repo UNCHANGED`. `plan` also BACK-FILLS §16e (2)'s `deck_end_stations` on a plan written before the field, by calling `rebake_plan.ring_ends` / `end_line_stations` — the patch half's own two functions, never a second derivation — and prints the count, so an old artefact can be replayed against the new law. §16e (6) (lane `v2bridgecontact`): `abutment_sample_step_m` / `abutment_walk_max_m` go through the SAME SIG-DIFF dropper, so `plan` times the deck end line's LANDWARD WALK the app builds and still runs against a `--src` that predates the two keys. NOTE (measured, lane `v2bridgecontact`): `--src` pointed at ANOTHER LIVE CHECKOUT is NOT a control, because a live checkout MOVES — the main tree read as clean at one sha gave LEMD 3,646 bodies against 2,122 from a `git archive` of that sha, and the difference was the orchestrator merging §16d into main between the `git log` and the replay (3,646 is §16d's own number, reproduced on both arms once the lane merged it). Cut every base arm with `git archive <sha> src | tar -x -C <scratch>` and point `--src` at that; never at a working tree another session can commit into. |

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

