# Brief pack — lane `v2bridgename`

Base: main `20606467` · generated 2026-09-13 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

§16e (3) reinstated by NAME: a bridge is its pack's name family riding the deck's datum as one rigid zero (owner OTHH read of 1.0.327, RULINGS 2026-09-13bn).

## The brief

Owner (OTHH on 1.0.327, RULINGS 13bn item 1): the deck is at the right level (13al: §16e (5)–(6)), the piers/clutter are still high — the bridge must be ONE unit. §16e (3) is REINSTATED BY NAME (read the spec block in this pack and RULINGS 13v / 13ae for the three refuted derivations — do not retry row, ring or footprint). `airport/bridge_family.py` already derives and publishes `bridge_of` (contact-based, unbound); replace its derivation with the NAME STEM read off the pack's OBJECT_DEF paths (the rebake plan carries each member's resource path) and BIND: the deck member of a stem is the datum body (its anchor from §16e (2)/(6) stands); every other member of the stem takes the deck's zero as its own — no per-member anchor, no carrier search, no §16a (2) ground test, no §15/§16b float refusal for family members (they are reported under the family, not refused). Pieces: `bridge_family.py` (name_stem, assign_bodies by stem), `placement_plan.py` / `placement_body.py` (the seat: family members after the deck), `placement_carrier.py` (family members out of the carrier candidate pool and out of the rest-on search), `placement_census.py` (per-stem spread, members), the writer untouched. Frames: `tools/harness/frames.py list OTHH` (v2unboxed's OTHH 1.0.326 rebake frame; the 13v/13al arms' paths are in §16e's MEASURED blocks). Base arms cut with `git archive <sha> src`; `anchor_rule._m_per_deg` is a first-touch memo (INDEX trap). The 13al lane's plan-stage figure is 70.87 s — do not regress it by more than 10 %.

## Bars

- OTHH: per-family zero spread 0.00 for every `Bridge_NN` stem (today `Bridge_02_CLUTTER_007` piers 4.97 m; per-placement spread > 0.3 m on 12 of 14); members and spread printed per stem by the census.
- Deck tops Bridge_01 / 04 / 05 still 3.96 / 3.96 / 3.96 (13al); Bridge_02 / 03 / 06 decks unchanged.
- Cross-bridge carriers 0 on the name axis; `bridge_of` = the stem for every member; a stem with no deck member falls back to §16c (name them).
- §16e (1) walls and the 8 drainage basins byte-identical; LEMD 1.0.325 byte-identical (its `Bridge4` is a line-station body — name it); KCLT byte-identical.
- Plan stage `--runs 3` ≤ 78 s (13al: 70.87); torn seams 0; outside-box 0 on the write half (APFS clone, guard armed).
- ONE OTHH build (`build_airport.py OTHH`, foreground, base arm reused from the ledger); suite twice.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/airport/bridge_family.py`, `Ortho4XP/src/auto_patch_v2/airport/placement_plan.py`, `Ortho4XP/src/auto_patch_v2/airport/placement_body.py`, `Ortho4XP/src/auto_patch_v2/airport/placement_carrier.py`, `Ortho4XP/src/auto_patch_v2/airport/placement_census.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/airport/placement_family.py`, `Ortho4XP/src/auto_patch_v2/constraints/pads.py`, `Ortho4XP/src/auto_patch_v2/emit/osm_adapter.py`

## Spec (object-placement) §16e (3)

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

## 2026-09-13bn — OWNER READ OF OTHH ON 1.0.327 (verbatim): "1. Bridges look like the actual deck is at the right level, but other components are still too high so the bridge is still coming apart into different components instead of staying a single unit. 2. This curving tunnel ramp has some bumps instead of descending smoothly for the length of the ramp: 25.253869, 51.603365"

* Item 1 REVERSES 13ae's withdrawal of §16e (3): the deck datum (13al) is right; the owner wants the piers and clutter RIDING IT as one unit. Three geometric derivations of "which bridge" were refuted today — the placement ROW (three bridges on one row), the deck's RING (bbox, clutter of one bridge inside another's ring), the deck's FOOTPRINT by contact (the clutter stands BESIDE the plate; an interchange's decks overlap). RULED (Fable, §16e (3) REINSTATED BY NAME): a bridge's family is the pack's own naming — every member whose resource file name shares the deck's stem (`Bridge_NN`, the text before `_CLUTTER` / `_LOD` / a numbered suffix; the law reads the pack's `OBJECT_DEF` paths, one derivation `bridge_family.name_stem`) — and the whole family takes the DECK'S datum as ONE rigid zero (the deck body is the datum body; every other member's zero = the deck's zero; no per-member cut, no carrier search); 13af's "keep object families together" is the standing principle. Where a pack has no deck member for a stem, the family falls back to §16c. Lane `v2bridgename` (pack). Bars (OTHH 1.0.326/1.0.327 frame, `v2_rebake_replay plan --sampler mesh`): per-family zero spread 0.00 for every `Bridge_NN` (today `Bridge_02_CLUTTER_007` 4.97 m); the deck tops still 3.96 / 3.96 / 3.96 (13al); cross-bridge carriers 0 on the NAME axis; `bridge_of` = the name family; LEMD byte-identical (its one `Bridge4` is a line-station body — say so); KCLT (no bridges) byte-identical; suite twice; ONE OTHH build.
* Item 2: the curving tunnel ramp at 25.253869, 51.603365 has BUMPS instead of a smooth descent — §34 (3)'s monotone profile (13ax) should hold on an emitted ramp; OTHH's ramps may be OBJECT-walled (§33 plates, 13i) with the emitted ramp priced between wall stations, or a §34 (6) cap-riding profile with the DEM crossing it. Scout `v2othh327` attributes (the ramp's records, its profile per station vs the DEM, the rows that hold each bump).

## 2026-09-13ae — v2bridgecontact REPORTED (lane 509dd182; merge pending — the branch conflicts in code with v2unboxed's `geom_boxes` through the same body-constructor signatures, so the LANE merges main into its branch and re-reads its bars before the spawner merges) and RULED (Fable, §16e (3) WITHDRAWN, (6) amended). Landed: §16e (5) partless deck members are bodies (Bridge_04 / Bridge_05 form one body each, 54 / 18 triangles, written and parsed back) and (6) the deck's end-line datum (Bridge_01 / 04 / 05 deck tops 3.23 / KEPT 6.43 / KEPT 6.43 → 3.96 / 3.96 / 3.96, 0.00 from the land); §16e (1)'s nine walls, the 8 drainage basins and LEMD 1.0.325 whole BYTE-IDENTICAL (OTHH-wide byte-diff: exactly 1 changed placement + the 2 new); plan stage 79.64 → 70.87 s mean; closing OTHH build rc 0, 763.9 s, guard UNCHANGED; suite 1,264/0 twice. Two moves under the 1,000-line law: `placement_read.py`, `placement_targets.py` split whole out of `placement_plan.py`. §16e (3) REFUTED a third way and DELETED under the attempt cap (cross-bridge carriers 2 → 9 on both arms; worst placement spread 4.97 → 6.61 → 9.66): measured centroid-to-nearest-footprint, only 51–71 of ~80–102 bridge bodies lie inside a deck footprint or within 0.5 m — OTHH's bridge clutter runs BESIDE the deck plate (0.6 … 45 m outside), so a footprint family is PARTIAL and a partly-bound bridge is worse than an unbound one; and Bridge_02/03/06 are an INTERCHANGE whose decks overlap in plan (`Bridge_03_CLUTTER_000__b1` inside Bridge_02's footprint at 0.1 m). The relation is kept as a published, censused fact (`Body.bridge_of`, `bridge_family.py`, 57 bodies / 34 of 39 split bridge placements) with no bind and no filter on it. Two instrument traps recorded in INDEX: `anchor_rule._m_per_deg` is a FIRST-TOUCH MEMO (a new pre-loop call site moved 94 `authored_offset`s by ~8 µm and broke byte-identity on 101 unrelated placements — use the unmemoised `rebake_plan._mpd`); a `--src` pointing at ANOTHER LIVE CHECKOUT of the same sha is not a control (LEMD 3,646 bodies vs 2,122 from `git archive` of the identical sha) — base arms are cut with `git archive <sha> src`.

* FABLE'S RULING on the three intent questions. (i) §16e (6)'s first limb ("the graded pavement/road face") is UNREADABLE at the site — no graded face within 140 m landward of either Bridge_01 abutment, `roles_many` empty at every station; the lane's second limb IS the law: the walk stops at the first DRY, LEVEL line within `split_tol_m` — that level line is "the design surface's graded ground" (the bank is exactly where the line is not level: end0 spans 1.34 / 1.76 / 0.44 / 0.00 m at 0 / 5 / 10 / 15 m). Spec amended. (ii) A body BESIDE a deck plate is NOT that bridge's by any rule the pack states — §16e (3) "one rigid assembly" is WITHDRAWN: the deck is the only datum body of a bridge; its separate clutter and piers rest on their own ground under §16c and are REPORTED per body (`bridge_of` names the deck they stand nearest, spread and cross-bridge carriers censused). The owner's 13k complaint was the DECK ("seat the top deck to align with the ground and let the feet land where they may"); the piers' per-pier zeros ARE the feet landing where they may. Whether the clutter beside the deck reads wrong in the cockpit is the OWNER'S READ of OTHH in app 1.0.327 — no further bridge law before it (the sim read is the acceptance). (iii) Moot: with no bind, the cross-bridge bar is a census line on the contact axis, not a bar.

## 2026-09-13al — v2bridgecontact MERGED (abfed8cb, lane 8bb694ad = 509dd182 + main 8ce4792a merged by the lane, code conflicts with v2unboxed's `geom_boxes` resolved by the lane keeping both parameters at every signature and call site): §16e (5)–(6) per 13ae — OTHH Bridge_01 / 04 / 05 deck tops 3.96 / 3.96 / 3.96 (0.00 from the land), 5 changed + 2 new placements at OTHH all bridges, every non-bridge placement byte-identical; LEMD byte-identical to main (322 splits, 3,646 bodies — §16d's own number, reproduced on both arms; the lane withdrew its earlier "another live checkout is not a control" note: main had MOVED between its log and its replay — the hazard is a live checkout moving, and `git archive <sha>` stays the base-arm rule); `placement_plan.py` came out of the merge at 1,015 lines — the lane moved §16e (3)'s per-unit assignment into `bridge_family.assign_bodies` / `body_bridge` (985 lines, byte-identical behaviour). `bridge_of` published and censused; no bind, no filter (13ae). Suite 1,368/0 twice on main. `test_v2objsplit.py` is 4,344 lines (a test file; split by section owed when next touched).

## Tool: v2_rebake_replay

| `Ortho4XP/tools/v2_rebake_replay.py` | The auto-patch-v2 OBJECT STAGE replayed OFFLINE — the synthetic-first instrument for the post-mesh half. `plan PLAN.json MESH --graded G.json` replays and TIMES the PLACEMENT stage over the sampler the app calls (RULINGS 2026-09-12g), with `--sampler`, `--no-batch`, `--src`, `--plan-out` and the `--oracle-write` / `--oracle-check` bit-identity pair; `order ICAO` is the partition-order twin (11j / spec §11a (3)); `disk PACK_ROOT` prints a pack's current bake state from its `.anchor_bak` backups and v1 provenance, read-only. The `plan` subcommand was DEAD from 12j/12s until 2026-09-12 (lane `v2objmotion`): it imported `RebakePlan` from `emit.rebake` (it lives in `model.rebake`) and read the deleted `carrier_fill_min` key before its own SIG-DIFF dropper ran — both fixed, and the sampler now carries §17's face ROLES so the timing is of the plan the app builds. THE SEAT SUBCOMMANDS ARE DELETED (owner RULINGS 2026-09-12s, spec §8): `seat`, `bodies` and `pairs` replayed v1's vertex rewrite and its `o4_v2_rebake_result_*` sidecars, a refuted mechanism. Writes no pack and builds no tile. (A), RULINGS 2026-09-12ap (lane `v2pavefeet`): `plan` also passes `bind_ground_m` (`[cockpit] visual_m`) through its SIG-DIFF dropper, so it times the plan the app builds and still runs against a src that predates the key. §16e (lane `v2othhdatums`): the entry now runs inside `harness/shared_repo_guard`'s WRITE GUARD and its before/after audit, the same one `obj8_split_report.py` and `build_airport.py` arm — `plan` calls `dsf_reader.ensure_dsf_text_path`, which GENERATES a DSF text dump into the mod cache when the cache has none, and a lane worktree MOUNTS `Airport_mod_cache` at the shared repo (the class RULINGS 2026-09-12j caught in `obj8_split_report`); every run prints `[guard] shared repo UNCHANGED`. `plan` also BACK-FILLS §16e (2)'s `deck_end_stations` on a plan written before the field, by calling `rebake_plan.ring_ends` / `end_line_stations` — the patch half's own two functions, never a second derivation — and prints the count, so an old artefact can be replayed against the new law. §16e (6) (lane `v2bridgecontact`): `abutment_sample_step_m` / `abutment_walk_max_m` go through the SAME SIG-DIFF dropper, so `plan` times the deck end line's LANDWARD WALK the app builds and still runs against a `--src` that predates the two keys. NOTE (measured, lane `v2bridgecontact`): `--src` pointed at ANOTHER LIVE CHECKOUT is NOT a control, because a live checkout MOVES — the main tree read as clean at one sha gave LEMD 3,646 bodies against 2,122 from a `git archive` of that sha, and the difference was the orchestrator merging §16d into main between the `git log` and the replay (3,646 is §16d's own number, reproduced on both arms once the lane merged it). Cut every base arm with `git archive <sha> src | tar -x -C <scratch>` and point `--src` at that; never at a working tree another session can commit into. |

## Tool: seat_feet_census

| `Ortho4XP/tools/seat_feet_census.py` | THE DRAPE RESIDUAL AT EVERY PLACEMENT'S FEET (RULINGS 2026-09-09ac (3); the placement reading 11e (3), spec §7/§9) — `--placement-plan o4_v2_placement_<ICAO>.json` with `--mesh` (a built mesh) or `--graded` (the emitted design surface, for a dry run with no tile built): per placement of the plan's own rows, `surface(foot) − (surface(anchor) + y_foot)`, the |Δ| histogram (<0.3 / 0.3-1 / 1-3 / >3 m), the same by class, the worst N with lat/lon, and §13's elevated-body / footless-carrier bars. Feet are read from the AUTHORED pack (`.anchor_bak` when one exists). THE SEAT-RESULT MODE IS DELETED (owner RULINGS 2026-09-12s, spec §8) — the name is kept because the INDEX row, `obj8_split_report` and the twins address it by it. Writes nothing to the pack. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. CRITICAL MOTION is named as an instrument limit rather than printed as a zero HERE: §17's motion reading needs the graded face ROLE under each foot, and this tool hands the block none — `obj8_split_report.py` is the entry that takes it (owner RULINGS 2026-09-12am (2), lane `v2objmotion`). §16e (owner RULINGS 2026-09-13k, lane `v2othhdatums`): `--placement-plan --mesh` WAS BROKEN — it passed its bbox as `(lat, lon)` to `MeshElevationSampler`, which takes `(min_lon, min_lat, max_lon, max_lat)`, so at OTHH it asked for a box at lon 25.2 / lat 51.6 and the sampler raised `no mesh triangles inside ... — wrong tile?`; the one place the two orders meet is now `plan_bounds()` and a twin holds it end to end over the sampler's own mesh fixture. The report also prints `§16e bodies on a DATUM` (a crest plate / a deck top) as its own class and EXCLUDES them from §13's `elevated bodies as own files` bar: a datum body's `y_zero` is +5 … +10 m by construction, and counting it there reported the law as the defect (OTHH 0 -> 10 -> 0 with the class printed apart). §16e (3) (Fable 2026-09-13, RULINGS 2026-09-13v, lane `v2bridgecontact`): the report also prints THE BRIDGE FAMILY block (`airport/bridge_family.census_bridges` / `census_bridges_lines`, re-exported through `placement_census`, the same call `obj8_split_report` makes over the same plan shape) — per `Bridge_NN` the deck's own body's world DECK TOP against the land under that bridge's own written geometry (`|deck top - highest land|`, bar `[cockpit] visual_m` 0.5 m), the PER-PLACEMENT zero spread (`max - min` of `surface_z - y_zero` over one placement's bodies; `Bridge_02_CLUTTER_007` is six piers of ONE solid), the CROSS-BRIDGE carriers (a body whose `merged_into` names a file of another bridge, bar 0) and how many bodies publish `bridge_of` and agree with the resource's own tag. The `Bridge_NN` axis is the CENSUS's, never the law's — §16e (3) exists because the name does not name a bridge — so the agreement count is the instrument's own check on the derived relation. Measured on the app's 1.0.326 OTHH frame: `Bridge_01` deck top 3.23 -> 3.96 and `Bridge_04`/`Bridge_05` KEPT -> 3.96 (all three |deck top - land| 0.00, PASS), cross-bridge carriers 2 (unchanged — the bind and the filter are refuted and deleted, see `bridge_family`'s module doc). |

## Registered frames: OTHH

OTHH  rebake   base 05050624   lane v2unboxed        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/unboxed  — KCLT 1.0.324 / LEMD 1.0.325 / OTHH 1.0.326 rebake frames + dry arms

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; files under 1,000 lines.
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

