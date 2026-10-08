# pads58 notes — hand-back at the 4B boundary (Opus implementer, 2026-10-08)

Branch `claude/pads56` (PR #463). Spec `tools/docq.py spec '§56'`. Done: step 4B's machinery, built and
twinned, levels byte-identical. STOPPED on 4B's acceptance: the fixed copy's `{why}` slots do not exist
on the real record (below). 4C, 4D, 4E and the closing builds are NOT started.

Frames: `<scratch>/pads58/heca_4a/` (the 4A arm, `b5647897`), `<scratch>/pads58/heca_4b/` (4B);
registered `HECA patch lane pads58` (`/Users/noah/XPTerrainBuilderData/.harness/frames/pads58/`, patch +
sidecar). Read script: `<scratch>/pads58/plat.py SIDECAR…` (released set, warned, tiers, datum vs median).
Both arms: `tools/v2_solve_replay.py --replay gaps3/HECA.pkl --from classify --emit DIR --verify
--workers 6` (15 min each beside three other lanes' replays; solve 235 s).

## STOP (BLOCKING for 4B's acceptance) — `reach_isect` carries no number on any pad

Spec §56 (3): "every slot is a field the record carries today (… `reach_isect`, `reach_isect_empty` …)".
MEASURED on the HECA gaps3 replay and on every sweep sidecar (`/tmp/harness/sw1045_*`, `swg_*`, seven
airports each): `reach_isect` is `null` and `datum_median` is `null` in EVERY `platforms[]` record.
Two causes, one after the other:

1. THE RECORD WAS LOST (found and FIXED here, a general repair). `no_step.hold_interval` writes the
   per-block report into `model.platform.HELD` during stage 1 — which since #100 round 8 (c) runs on the
   ribbon-free map under ITS OWN registries (`pipeline/stage_one_map.StageOne.scope`: "stage 1's own
   mutations stay its own"), and the §55 last stage re-mints `HELD` again. So `reach_band`, `reach_isect`,
   `datum_chosen`, `reach_lo/hi_binding` never reached the publication. Fix: `model.platform.
   HOLD_REPORT_KEYS` / `hold_report` / `install_hold_report` (the report's scalar and lat/lon keys — no
   vertex id), carried at the scope's exit and over `run_late_stage` in `pipeline/build`. After it the
   HECA record reads `datum_median` on 42 of 42 held pads, `reach_band` with both bounds on 37, and
   `reach_lo_binding` / `reach_hi_binding` (contact, anchor lat/lon, runway, hops) on the unit pads —
   padspec4's "in no sidecar record today" was this same loss.
2. `reach_isect` IS UNBOUNDED BY CONSTRUCTION (NOT fixed — the spec author's). `hold_interval` intersects
   the contacts' `REACH_GENERATOR` Bands read off pass 1a's `cs`; the 08k shape stage withdraws those
   Bands (`pipeline/shapes.py:129`; HECA "reach bands to withdraw 17180"), so no contact carries one and
   every block reads `reach_isect [None, None]`, `reach_isect_empty false` (42 of 42). Neither `{why}`
   sentence can be said: both need `r_lo` and `r_hi`. (By reading the code + the 42 records; no
   intervention arm was run.)

So on the HECA replay `building101` (0.328 m over 3 of 16 contacts, the one pad over the 0.3 m bar) is
NOT warned: the record reads `warned: false, warning: null, warning_unsaid: ["reach_isect"]`, the census
row reads `reading: "unsaid"`. I did not invent a sentence (the copy is fixed and the owner reads it).

What the record DOES carry now, for the author to choose from — the pair-graph interval (the REPORT):

| pad | released / welded | `released_max_m` | datum | `datum_median` | `reach_band` (pair graph) | `reach_empty` |
|---|---|---|---|---|---|---|
| `building101` (conforming) | 3 / 13 | 0.328 | 82.583 | 84.227 | [83.477, 86.413] | false |
| `building141` (14.6 m collar) | 6 / 33 | 0.260 | 70.812 | 70.403 | [71.800, 70.239] | **true** (gap 1.562) |
| `building132` | 2 / 35 | 0.043 | 87.368 | 90.254 | [84.508, 89.757] | false |
| `building158` | 3 / 4 | 0.043 | 76.702 | 77.307 | [73.853, 77.670] | false |
| `building150` | 3 / 21 | 0.042 | 78.546 | 79.216 | [77.134, 80.747] | false |
| `building186` (conforming) | 1 / 32 | 0.021 | 70.792 | 71.001 | [66.685, 70.511] | false |

QUESTION 1 (yes / no) for the spec author: may `{why}` read the pair-graph interval — `reach_band` /
`reach_empty` — in place of `reach_isect` / `reach_isect_empty`, the two sentences otherwise verbatim?
RECOMMEND YES: its semantics are the copy's own ("the lowest contact can be reached only up to {hi} and
the highest only down to {lo}" is exactly `lo > hi`), and it is the one interval with numbers. It is a
one-line change in `constraints/pad_warning.py` (`SLOTS`, `frontage_warning`) and the twin's records.
CAVEAT the author must weigh: `building101`'s datum 82.583 lies OUTSIDE its non-empty band
[83.477, 86.413], so the line would say "seated flat at 82.58 m, the apron's own level there … a common
level within reach exists (83.48–86.41 m)" — and see Question 2 on whether the two numbers share a frame.

QUESTION 2 (yes / no): is "the apron's own level there" still the right clause, and is bar 3 (d)
(`datum == datum_median`, "02ah's own acceptance") still a bar? It could not be read before the carry,
and on the 4A arm it does NOT hold: `|datum − datum_median|` is over 0.02 m on **39 of 42** held pads,
over 0.3 m on 33, over 1 m on 21, worst 4.65 m (`building85` 94.226 vs 98.875, `91` 94.292 vs 98.523,
`51` 85.818 vs 89.653, `138` 88.289 vs 91.530; T3 `building3` 101.878 vs 100.565) — and the sign is one
way: the solved datum is LOWER than the median on 35 of the 39 (median of the differences −0.67 m).
**NOT ATTRIBUTED** (no arm run): either the pass-1a contact values `hold_interval` takes the median of
are not in the emitted surface's vertical frame, or the ribbon-free pass 1a really stands that far from
the solved apron at the frontages. Until that is read, NEITHER `datum_median` NOR `reach_band` should be
printed beside `datum` in a line the owner reads — Question 1's YES is conditional on it. The datum
stands inside its pair-graph band on 33 of the 37 pads that carry both bounds (outside: `building141`
(empty band), `101`, `186`, `90`). RECOMMEND for (d): "per pad `|datum(4C) − datum(4A)| ≤ 0.05 m`", which
needs no median.

## DONE — step 4B (one commit), levels byte-identical

- `constraints/pad_warning.py` (new, 102 lines): `COPY`, `WHY_NO_LEVEL`, `WHY_NO_BLEND`, `ONE_LEVEL` — the
  spec's words verbatim; `frontage_warning(rec, margin)`, `stamp_warning`, `warnings_of`, `missing_slots`.
- `constraints/platform.py`: both `_datum_record` read sites stamp `pad_m2` (the faces' area — the spec
  named the slot, the record did not carry it), `warned`, `warning`, and `warning_unsaid` for a block over
  the bar whose record lacks a slot.
- The wire: `pipeline/build` → `report["warnings"]`; `auto_patch/engine_v2` result `"warnings"`;
  `auto_patch/driver` says each through `UI.loud_warning` in the PARENT (the build runs in a worker;
  `auto_patch_v2` prints nothing and imports no UI). No new event class; Swift untouched.
  `tools/v2_solve_replay.py --emit` prints `WARNED:` lines.
- Census: `check_grade._check_pad_frontage(held=False)` = the blocks with `released > 0` (it read
  `unheld_contacts`, which 02ah left always 0 — the family read 0 rows everywhere), `de` =
  `released_max_m`, site = the worst released contact, `reading` = `warned` / `not_warned` / `unsaid`;
  `families.toml` text re-worded as the spec gives it.
- Twins `tests/auto_patch_v2/test_pad_warning.py` (8): the copy byte-asserted in both `{why}` variants and
  with the one-block suffix; 0.25 silent; a missing slot names itself; the report carry by ref; the census
  rows.

PROOF (HECA gaps3, 4A arm vs 4B arm): `HECA.graded.json` sha256 `7164cd6a1acafc7c…` both; patch body
(less the header line) `6a4a44a76a4e1241…` both; the released set, counts and `hard_conflict` tiers
(pad 14 / groundside 168 / taxi 70) identical. `tools/harness/census.py` on the 4B arm:
`pad_frontage_infeasible` **6** rows (`101` 0.328, `141` 0.260, `132` 0.043, `158` 0.043, `150` 0.042,
`186` 0.021), each with `reading` — bar met; WARNED = **0**, bar NOT met (`building101` unsaid).
`platform_rim_relief` 45, `platform_refused` 3 (the collars are still minted).

Doubts noted, not blocking: (i) the spec puts the rows in `report.json verify.by_family`; the family is
a CENSUS family (`verify/census.NOT_IMPLEMENTED`), so the count is `harness/census.py`'s, not the
report's. (ii) `{n_contacts}` = `released + welded` of the record (held contacts; a ramp contact is not
counted). (iii) OTHH and KASE were not replayed: OTHH's sweep sidecar has 0 released (0 warnings by
construction); KASE `building1` (0.629) will read `unsaid` until Question 1 is ruled.

## For 4C — reading done, nothing edited (the next lane starts here)

The 4A arm on final code (the baseline bar 3 reads): 48 records, 12 collared + 33 conforming + 3
refused (`building96` eroded_away, `100` / `162` under_min_area); released as in the table above.

What I would build (unverified design, from the code):
- `planar/platform.platform_split`: no erosion. Unit pad (≥ `cluster_pad_min_m2`, ≥ 3 welded samples, not
  draped) → `plan_blocks`; > 1 block → `_mint_blocks` with `plats = [P]` (`col = Q − keep` becomes
  `ref + STRIP_SUFFIX`); else `HELD[ref]` with the plan's record and the region left WHOLE. The two
  rename passes (`:461-474`) go: a 23a rim sliver keeps the pad's ref (a cut unit's: its nearest block's
  ref). `merge_platform_faces` keys = held refs ∪ their `#strip`. The erosion-refused pads are ALREADY
  conforming-held today (the `:481` loop registers any refused pad) plus `refused_plates`' soft plane —
  the change for them is the unit path's hard flat rows, not a new hold.
- `model/platform.datum_vertices`: one rule for every held ref — an OWN (non-airside) vertex farthest
  from the weld, the conforming branch's. A pad whose every vertex is airside has no datum column and is
  not held (today's conforming behaviour): COUNT these on the replay — in 4A a unit pad always had an
  interior platform ring.
- `constraints/platform`: `platform_contacts` = (ref, the pad face's vertices, those that are airside)
  per held non-conforming ref, plus the landing pairs `collar_faces` still yields; `platform_plane_rows`'
  held branch over `own − airside` (the generator runs on the FULL map; the conforming own-vertex rows
  live in `hold_interval` and are remapped from the ribbon-free map — a ribbon T-vertex on a pad rim gets
  none). A contact then has ONE row (its hold), as on a conforming pad — the "post-4C case already
  running". Exclude a vertex shared with another pad of a different base ref (the collar's and
  `refused_plates`' own exemption; HECA `building281` | `building68` stand 16.4 m apart).
  `refused_plates` STAYS — it serves the `draped_facade` refusal.
- The §20 plate (`constraints/pads`) then prices the unit pad's whole rim, contacts included: the hard 1 %
  ceiling between a RELEASED or RAMP contact and an own vertex at D is a new hard pair on unit pads
  (conforming pads have it today). This is where bar 3 (a)/(b) will be decided.

READERS THE CENSUS (§56 (5)) DOES NOT RULE — each a "STOP: add the row" under the spec's own rule:
1. `planar/landing.landing_regions(…, cap, …)` takes `platform_collar_max_m` as the LANDING bank's width
   (`planar/platform.py:513`). Row 9 says landings are unchanged and the §56 (3) table deletes the key:
   both cannot hold. The key must survive 4D (or the landing gets its own).
2. `solve/design_ground.coverage_edge_collar_vertices` is not dead with the unit collar: a landing collar
   (`<unit>/landing<k>#collar`) is a `#collar` face and can stand on the coverage edge. HECA / OTHH carry
   0 landings on these frames, so 4D's byte-identity there proves nothing about it.
3. `airport/pad_block_seat._platform_polys` drops each block's LARGEST published ring as "the collar's
   outer ring". After 4C the largest ring is the block face itself — it must read every ring of the block.
4. `airport/placement_read._collars_as_platform` also folds LANDING collars under the landing ref; the
   spec deletes it and, two rows on, says the strip is folded "exactly as `_collars_as_platform` folded
   the collar". 4C's minimum is `is_collar_ref` → `is_bank_ref` there, keeping the fold.
5. `constraints/pads.py:605` `platformed` and `:970` are true for a landing's faces too.
6. `check_grade._check_platform_rim_relief` emits one row PER platform record (45 on the 4B arm, `de` 0):
   "reads 0 after 4C" needs the reader to skip a record with no `rim_relief_max_m`.

Tests naming the collar (to rewrite with 4C / 4D): `test_unitplatform_platform` (24 tests, 82 hits),
`test_v2padlevel` (12, 28), `test_collarlag302` (4, 22), `test_pad_blocks` (24, 15), `test_v2staged` (10,
11), `test_flatpad150`, `test_facade_mint`, `test_v2frontage`, `_plate.py`, and one to three hits in
twelve more.

## Not done
4C, 4D, 4E; the OTHH and HECA closing builds; the site bars; the remaining-faces table; the blocker-site
reads (#96 / #111 / #112 / #10); the walls3 merge and the `test_gap_terrace` re-record (the master had
not said walls3 is on main); an OTHH replay of 4B; KASE.
