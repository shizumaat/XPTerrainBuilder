# Brief pack — lane `roads315`

Base: main `a43fc86a` · generated 2026-10-03 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

CYXY service road hill and cut (#315 #316)

## The brief

Issues #315 and #316. Owner read of app 1.0.372 at CYXY: (a) a service road has a hill at 60.7090573, -135.0740232 — owner does not think the DEM carries it; expects a smooth profile along the road's long axis. (b) a service road is cut below grade at 60.704929, -135.0724751.
Step 1 (measure, no edit): for each site report the road element (role/ref), its emitted longitudinal profile +-150 m, the DEM profile under it, the neighbours' levels (pads, lots, apron, terraces), and the hard/soft rows that bind there (v2_solve_replay --probe-site / --why-hard / --why-vertex on a sw1023_CYXY capture). Name the mechanism with an INTERVENTIONAL replay (drop/relax the suspected row, see the profile move) before any fix.
Known neighbours: #264 (cc325354) made the pavement road cap skip a held hillside-terrace pad|lot pair; #282 minted road ribbons carry stage-2 slope conflicts at joins to pinned corridors; #110 unclassified groundside pavement defaults to the parking-lot role. Check whether either site is one of these classes before proposing anything new.
Step 2: fix at the mechanism if it is a defect inside existing law. If the fix needs a new rule or an owner intent call (e.g. which neighbour the road should follow), STOP and report options.

## Bars

- Both sites: emitted road profile monotone/smooth along the long axis within the road cap, no crest at (a), road at grade with its neighbours at (b); numbers before/after at the two coordinates first.
- Airside unchanged vs sw1023_CYXY (tools/airside_value_delta.py --tol 0.02, runway bar 0); census CRITICAL motion reported.
- Twin test for the mechanism (synthetic). ONE closing CYXY build via tools/harness/build_airport.py. No sweep, no merge, no issue comments.

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

## Spec (design-surface) §37 (8)

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

## RULINGS

## 2026-10-02af CYXY READS MERGED (cc325354, lane cyxy262 e1a70c5c; Fixes #262 #263 #264) + SWEEP sw1014 vs sw1013 + REFERENCES RE-CUT. #262: a cell holding a 1300 startup refuses the corridor kind (§40 (2) rung, boolean) — CYXY pav5 cross_connector -> apron (16,221 m²), the only other re-kind is CYXY cell 41 pav3 (South ramp); SPJC/HECA/KCLT 0. #263: stock `.agp` hangars (lib/airport/common_elements/hangars/) are buildings again (v1's AGP source ported; `dsf:agp:hangar`) — CYXY pads 10 -> 14, SPJC +19 hangar pads (GA area −12.028, −77.104). #264: the pavement road cap skips a held hillside-terrace pad|lot pair — the access road is level at 698.4–698.7 m along the terminal wall (the 13o/13p second-storey level, not the pad's 694.96). SWEEP: CYXY 433 movers (runway 6 / 0.24 m at 02/20's SE end — the flex envelope re-settled when pav3 became apron, 0.022 of 0.117 m used, caps held), adjudicated 332 -> 409 (the apron's new rows), CRITICAL motion 0 -> 1 = `raoa [apron|apron]` 0.24 m over 24.1 m @60.7106099, −135.0735336 — the engine's raoa family is SOFT while the census calls it CRITICAL (instrument weight gap, filed); SPJC 1,439 movers (the 19 hangar pads + their aprons, worst 5.44 m @−12.02792899, −77.10387967; runway 12 / 0.06), CRITICAL 0, adjudicated 931 -> 1,000; KCLT 19 / 0.03; KASE 0; HECA 0. OWNER LOOKS OWED: CYXY terminal apron cell 81 pav28 (60.7138298, −135.0619616) stays a corridor (no startup inside); the SPJC hangar pads; #264's level (second storey, not pad). References `sw1014_*`, base cc325354.

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N] [--why-hard-stage 1]` on either a `--replay` arm or a `--why-from PKL`; `--why-from PKL --probe-site LAT,LON [--probe-drop M] [--probe-arm TERM=V ...]`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (**and THE CLUSTERS beside the partition and the groups** — lane ``v2padjoin`` 2026-09-14: a capture without ``Airport.clusters`` leaves §30 (4)'s cluster pad, its apron reach and §16g (10)'s derived pads INERT in every replay of it, so a pads-ON arm silently measures the pads-OFF law; a capture predating them has them DERIVED at replay off its own partition, named on stdout) (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently).  **`--why-hard-stage 1`** reads §20b STAGE 1's OWN ASSEMBLY instead of the full problem's (`solve.design.stage_split`'s drop + fixed): the AIRSIDE hard set, in the rows and the metre scaling stage 1 enforced them under. The full read cannot answer "does the AIRSIDE solve settle" — the airside rows are a subset of 325k whose population and scaling the stage's own drop changes — and that is exactly the claim RULINGS 13y (B) / 13ab / 14as make (lane `v2settle`, which used it to split HECA's "42 unsettled rows" into 9 CONSTANT rows the solve can never move, 6 HELD runway rows at the projection's own bar, and 18 real ones).  The shipped surface is read either way: an airside vertex's z IS stage 1's, so the stage-1 read at the shipped z equals the read at stage 1's own surface (measured identical at HECA). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate).  **`--probe-site LAT,LON` IS THE STABILITY PROBE** (lane `v2qp`, spec §20c, promoted from lane `v2settle` r2's `scratchpad/v2settle/probe3.py`/`probe4.py` on its second use): off a `--solved-out` pickle, one extra `Band` ceiling `--probe-drop` (default 0.30) metres under the ARM's OWN base surface at the vertex nearest the point, re-solved, and the moved set (> 0.02 m) binned by distance from it — 0-40 / 40-100 / 100-250 / 250-500 / beyond, with the worst beyond 250 m, each arm's hard set and its exit line.  `--probe-arm TERM=V` repeated makes it a MATCHED PAIR of `[design]` arms on ONE problem (`--probe-arm solver=fixed_point --probe-arm solver=qp` is §20c's own bar); with none it probes the shipped law alone.  This is the instrument RULINGS 2026-09-14bw's headline was taken on (HECA: 959 vertices moved by one 0.30 m row, 953 beyond 500 m, ZERO within 100 m).  `--design-weight TERM=V` also takes a NON-NUMERIC value now (§20c's `solver=qp`); a value that does not parse as a float is passed through as the string.    **`--placement KEY=V` IS THE CAPTURE-TIME LAW ARM** (lane `v2padqp`, spec §16g (10) (11)): the §16g (10) pad keys (`pad_from_cluster`, `pad_airside_clip`) are read in `classify/evidence._pads` and `planar/overlay` — UPSTREAM of the capture — so `--design-weight` (a `[design]` override applied at REPLAY) cannot arm them and a pads-ON replay of a pads-OFF capture silently measures the pads-OFF law; a matched OFF/ON pair is therefore TWO CAPTURES of one tree, never two edits of the shipped toml (the value is coerced to the key's own type, an unknown key refuses by name, and the arm is recorded in the pickle).  `--capture` also arms `harness/build_airport.arm_shared_repo_protection` — the ONE arming composition — and prints `[guard] shared repo UNCHANGED`.  **`--rule SECTION.KEY=V` IS THE CAPTURE-TIME CLASSIFY ARM** (lane `v2shoulderband`, spec §40 (5)): the same thing for `classify/rules.toml` that `--placement` is for `[placement]` — a CLASSIFY key is read upstream of the capture (the capture HOLDS the classification, so `--from planar` cannot see a classify change at all), which makes a matched pair on one TWO CAPTURES; doing that by editing the shipped toml between the arms is the defect RULINGS 2026-09-15az records (disarming a head by prefix also deleted `foot_row_rulings` and silently re-priced every foot row), so the arm is ONE COMMAND-LINE VARIABLE on one unedited tree instead. `SECTION.KEY=VALUE`, coerced to the key's own type, an unknown section or key refuses BY NAME, and the arm is printed on stdout — e.g. `--rule corridor.runway_shoulder_band=false`.  **`--reclassify PKL` IS THE DRY §40 BAND READ** (lane `v2shoulderband` r2, promoted on its SECOND use per RULINGS `7e90032` — r1 hand-rolled it in a scratchpad for the HECA control and r2 needed it at five airports): a CLASSIFY key cannot be armed at replay, but the capture also carries the `Airport` the classifier ran on, so the CLASSIFY STAGE ALONE is re-run over it on the CURRENT tree with `--rule` as the only variable — seconds against a capture's minutes (LEMD 74-79 s). It prints §40 (5)'s own table: the `runway_shoulder` population (cells, m², each named with its host runway and its worst lateral offset), the runway BODY beside it, what the remainder earned BY ROLE, the worst lateral offset of a shoulder vertex off its own runway's apt.dat axis and how many stand beyond the band (§40 (5) (1)'s own bar, "→ 0"), and the classifier's own `shoulder_band_*` stats; `--json` dumps it with the arm recorded, so no reading is frame-less. It is a DRY read and says so — no planar build, no solve, no emit — so it PRICES NO LAW AND COUNTS NO DEFECTS (defect counts come from `harness/census.py` and nowhere else) and it cannot answer anything downstream of classify: a `runway_step` row or a census family needs a built patch. The axis and the half width are the derivation's own (`classify/roles.shoulder_band`), imported and never re-spelled. Control: re-read on the registered `LEMD capture base e856ce64` it reproduces r1's ON arm EXACTLY (271,086 m² / 19 cells / remainder 273,949 m² in 28 faces). Twin: `tests/auto_patch_v2/test_runway_shoulder.py` (the table IS the classifier's verdict on both arms, band + remainder PARTITION the cell, the arm is recorded).  **A CAPTURE CARRIES THE ARRANGEMENT'S RE-NODE READING** (lane `v2padclip`, spec §16g (10) (12) (2)): `pipeline/publication` publishes the sidecar's `pad_airside_renode` out of a module global `planar/overlay.PAD_AIRSIDE` that only a BUILD fills, so every replay arm published an EMPTY list and read a perfect family — the silent-degradation class. `--capture` now pickles that dict and `--replay` restores it and prints `pad/airside re-node from the capture: deleted N minted M`; a capture written before 2026-09-16 carries none and the sidecar key is then OMITTED, which every reader reads as NOT MEASURED rather than zero.   Twin: `tests/auto_patch_v2/test_v2qp.py` (the probe as a fixture pair) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. **`--stage1-dump OUT.json.gz` / `--stage1-diff A B [--movers AVD.json]` IS THE §20b (3) STAGE-1 POPULATION READER** (lane `v2stagepop`, spec §20b (3) (4), RULINGS 2026-09-16v): off a `--solved-out` pickle (`--why-from`) or off a CAPTURE (`--replay`, the generators re-run under the current tree), it runs `solve/design.stage_split` + `solve/design.assemble` — the assembly the stage actually solves, never a re-derivation — and writes every ROW (least-squares, per-body datum and one-sided, each keyed by its owner/ruling, its terms and its right-hand side), every COLUMN (the reduction's own merged vertex set), every SHEET FACE with its area and every TRIANGLE, all keyed by the canonical 11-dp lat/lon so two arms diff BY IDENTITY (memory `canonical-identity-join`); it REFUSES if its own sheet re-read does not reproduce `DesignReport.triangles`. `--stage1-diff` prints the decomposition §20b (3) (4) asks for — counts, then rows REMOVED / ADDED / **RETARGETED** (the same row over the same vertices at a different right-hand side: a target the groundside moved, never a row of the pad law), the columns, the sheet faces by role and m², the triangles — and with `--movers` (an `airside_value_delta --json`) attributes each moved airside vertex to the class of stage-1 change it stands on, with the far field's distance profile to the nearest change. It SOLVES NOTHING, prices no law and counts no defects (defect counts come from `harness/census.py`). Measured basis (HECA, the v2padclip r2 staged arms, every pad generator dropped): columns 18,495 → 18,499, one-sided rows 1,317,645 → 1,322,265 (`apron` frontage-chord / preferred-tier 4,712 removed / 9,178 added), `apron_trend` 1,107 RETARGETED, sheet faces 892 vs 890 → 859 = 859 once the stage's own roles decide the sheet. `--from classify` (lane `spjcpads`, issues #3/#4) RE-DERIVES the clusters off the captured partition and RE-RUNS CLASSIFY under the current tree before the planar map — the only resume that sees a change to `plan_clusters` / `member_is_deck` / the derived-pad mint (`geom.cluster_outlines`), which are minted at classify time off captured clusters (`--from planar` moved 0 pads). With `--from classify|planar`, `--placement KEY=V` is a REPLAY-TIME `[placement]` arm (one tree, one variable — e.g. `pad_keeps_footprint=false`, the pre-RULINGS-23a clip), refused before the capture is read for any later resume; `--pad-read` prints the PAD READ of the re-run arrangement (the pad/airside publication: 23a apron cut / pre-23a clip counters and the §16g (10) (12) re-node census; building vs airside face area; the weld population by node identity; `pad_cluster_mismatch`; the pad REF under each `--site`, all its faces and m²; and THE NESTED-PAD CENSUS (lane `nestedpads`, issue #6 HECA-1 "a building shape must never be nested inside another"): every `building` face inside the shell of another pad's face — two refs counted as the defect, a ref's own face in its own hole counted apart — rows largest first with both refs and lat/lon; HECA capture be2dfd43: 4 / 3,922 m² on main → 1 / 1.2 m² with the weld-closed merge) and stops before the solve (`--json` writes it). Measured basis (SPJC, the spjcpads capture): 23a arm `building32` 99,234 m² in ONE face vs 13,323 m² in 8 pre-23a; re-node minted 20 vs 25. Twin: `Ortho4XP/tests/auto_patch_v2/test_spjcpads.py`. MERGED 2026-09-25 (lane nlwf): shapes|planar] [--drop-generator G] [--weight ROLE=W] [--site LAT,LON] [--site-radius M] [--chord-fill ROLE ...] [--emit DIR] [--verify] [--design-weight TERM=W] [--solved-out PKL] [--json OUT] [--z-out Z.npy]`; **`--rule` takes LIST keys** (lane `nlwf`, 2026-09-25): comma-separated, each element typed like the shipped first one (`--rule surfaces.graded_codes=1,2,3,4,5,12,14,15`, the NLWF transparent-apron arm); and `--json` now carries `verify.rows` — every family's rows (capped 200), not only the gate's, so an arm is read by site without a second census. MERGED 2026-09-28 (lane nestedpads): the pad REF under each `--site`, all its faces and m²) and stops before the solve (`--json` writes it). A capture REFUSES unless `Airport_mod_cache` and the DSF dump cache resolve outside the shared repo (`require_capture_isolation`, the guard's own `redirected_scopes`; #64) — the CLI `--capture` arms both; a direct call of `capture()` does not. `O4_FRAME_ENTRY_DUMP=<dir>` arms §51's offender dump (v2 reads no env; #59). MERGED 2026-09-28 (lane clustertrim): **`--stage1-dump` CARRIES `--placement`** (lane `clustertrim`, issue #67): the dump's capture path called the replay prelude WITHOUT the arm, so `--placement pad_keeps_footprint=false --stage1-dump` silently dumped the shipped law and printed no arm line; the prelude now receives it (and prints `REPLAY ARM [placement]`), and `--placement` with `--why-from` refuses (a solved pickle's arrangement cannot see the key). Twin: `tests/auto_patch_v2/test_clustertrim.py`. MERGED-PENDING 2026-09-28 (lane unitplatform2): **`--placement SECTION.KEY=V`** arms another `structures.toml` table at replay (`--placement building_pad.platform_collar=false`, the unit-platform matched base arm on one capture). **SHORE DECISION (issue #72, RULINGS 2026-09-29a/h):** every `--from classify|planar` replay prints one `[planar] shore <kind> by <witness> [height] <zone ref> at LAT, LON` line per zone part reaching the sea (witness declared / pack_wall / pavement / profile / default; `shore_undeclared` for default) — the read of `planar/shore.shore_verdict` on the capture, no build needed. **`--pad-read` PRINTS THE FLAT-PAD BLOCK PARTITION** (lanes `flatpad111` / `flatpad111b`, flat-pad spec §2 as ruled 2026-09-30r — Q-111b option (1), the terminal cut into flat blocks at its necks; issue #111): `[building_pad] frontage_hold` ships TRUE, so every `--from classify|planar` replay prints one `PAD BLOCKS <ref>: <one_block|split|residual|stop_cap> contacts N q N blocks N bay B m steps [b<i>|b<j> ±ΔD, ...] necks [m of footed pack parts each cut crosses] | b<k> <m2> front <m> contacts N [zmin..zmax] D <predicted datum> held N ramp N residual N (max M)` line per minted platform, off `planar/pad_blocks.BLOCK_PLANS`, and `--json` carries `pad_blocks` (with the cut chords); the SOLVED per-block datum and the hold's miss are in the emitted sidecar's `platforms[]` (`datum`, `hold_residual_p50_m` / `_max_m`, `hold_within_m`). `--placement building_pad.frontage_hold=false` is the 29s contact-led control. Twin: `tests/auto_patch_v2/test_pad_blocks.py`. MERGED-PENDING 2026-09-30 (lane aptdatum129): **`--cifp-dir DIR`** is a CAPTURE ARM — the load reads CIFP from DIR instead of the cfg's `cifp_data_path` (an EMPTY dir = the no-CIFP airport, issue #129's KCLT-without-CIFP arm) without touching the real X-Plane install. MERGED-PENDING 2026-09-30 (lane `flatpad128v3`): **`--drop-generator` also takes a RULING HEAD** (`design_roles.ruling_head`, the key `[design] hard_rulings` names a law by) — the frontage hold's rows are minted by `platform_collar` beside the collar's own, so `--drop-generator frontage_hold` dropped NOTHING and a "hold-OFF" arm silently kept the hard hold (measured HECA: runway 191 movers, worst 1.16 m); `--drop-generator "structures.building_pad frontage_hold"` is the flat-pad v2 §1 pass-1a arm. **A LANE-LOCAL DATA OVERLAY IS DECLARED AND RECORDED, NEVER A HAND-SWAPPED SYMLINK** (issue #156): `--data-overlay DIR` (env `O4_DATA_OVERLAY`) reads the corpus directories that `DIR` carries (`Elevation_data`, `OSM_data`) from it and leaves every other input on the shared corpus — the provider-inset case two lanes (`las130`, `cwcb154`) took by temporarily replacing the worktree's `Elevation_data` symlink, which left the capture indistinguishable from a shared-corpus one. The overlay frame (`{dir, provides}`) is pickled WITH the capture under `data_overlay`, re-announced at every replay off it and carried into the `--solved-out` pickle and the `--json` result, so an overlay capture can never be mistaken for a shared one. It is a READ-side declaration: the shared-repo write guard stays armed and the flag authorises NO write (as `--allow-degraded-dem` does not). It is NOT `build_airport.py --corpus snapshot:DIR`, which is a hash-stamped, manifest-VERIFIED snapshot REPLACING the whole corpus (`corpus_snapshot.verify` refuses one carrying no complete read set for the airport); an unverified partial provider tree is a different act and keeps a different name. Twin: `tests/test_v2_solve_replay_overlay.py`. FIXED 2026-10-02 (lane `sweep1005attr`): **an `--emit` arm of `--from classify|planar` is now BODY-IDENTICAL to its own build** (measured KCLT + SPJC against `sw1005_*` at 219fbccd) — the emit half was missing the §39 shore weld + `merge_sub_spacing` (SPJC 108 extra vertices), and the replay let `build_planar` read the pack through its own DEFAULT `ResourceCache`, which carries §51 (6)'s input quantum while the build's does not (KCLT lost a tunnel_ramp + wall, 2,381 row-side values off the build, worst 1.12 m); it now reads the pack once through a cache built as `pipeline/build.pack_stage` builds it and hands it to classify and the planar build. FIXED 2026-10-02 (lane `replay224`): **the CAPTURE STATE travels with the capture** (issues #224 / #208) — four of the build's planar-stage products are MODULE GLOBALS rather than values handed stage to stage (`model.platform.HELD` / `PLATEAUS` / `PLATFORMS`, `model.pad_terrace.TERRACES`; `planar.overlay.PAD_AIRSIDE` was the first of the class to travel, RULINGS 2026-09-16b) and the constraint generators read them, so `--from shapes|constraints` — which do not re-run `planar/build.build` — read every one EMPTY and assembled a different LP from the build's (KCLT 65,212 rows vs 49,981 on an IDENTICAL 22,263-vertex set; HECA §5a relaxed 822 rows vs 108; CYXY/KASE armed two jetway strips the build held disarmed, since `jetway_strip` disarms on a HELD block). The capture now records them in ONE versioned record (`src/auto_patch_v2/pipeline/capture_state.py`, which also carries the CONSUMER CENSUS of every module registry and why each is or is not carried), the replay installs it and prints `capture state v1 installed: ...`, and a capture that does NOT carry a field REFUSES the late resume BY FIELD NAME — naming the stage that fills it and every pass that reads it — rather than silently solving a different problem (the 12u groups rule applied to the whole class). The `--solved-out` pickle carries the same record, because `--bank-from`'s emit half reads `PLATFORMS` / `TERRACES` through `pipeline/publication` and `--probe-site` / `--stage1-dump` re-solve under `hold_pass`, which reads `HELD`. Twin: `tests/test_v2_capture_state.py`. **`--pad-read --shape-dump OUT.json`** (lane `roadmint100e`, #100 round 4) writes the 08k SHAPE READ of the re-run arrangement — every labelled vertex's shape by canonical 11-dp lat/lon and the joints — so two arms diff the labelling BY IDENTITY before any solve (seconds against the 6-min replay; it found the ribbon-as-separator and ribbon-edge-as-witness doors at HECA: 58 shapes / 22 joints for main's 52 / 0). |

## Tool: road_terrain_conformance

| `Ortho4XP/tools/road_terrain_conformance.py` | The census is GREEN and the owner says the ROADS are wrong — "capped at a visibly low grade, cutting through hills" (docs/POSTMORTEM-20260831.md). This is the TERRAIN-CONFORMANCE INSTRUMENT owner ruling RULINGS 2026-08-31a requires, and the reason it must exist is that NO CENSUS CAN SEE THE DEFECT: a road planed flat through a hill breaks no grade law at all — it is the most lawful surface there is — while the owner's road law says a road FOLLOWS TERRAIN up to `SERVICE_ROAD_MAX_GRADE` (8 %) and is pinned ONLY where it meets airside pavement. Per road CHAIN (a connected run of `service_road` / `service_junction` rings, joined by SHARED NODE IDs and walked along the component's longest path, stationed by ring-centroid arclength — the road's own PATH, never a plan chord, which is the frame `free_road_profile` solves in): `dem_relief_m` (how much hill the chain crosses), `emitted_relief_m`, **`follow_ratio`** (emitted/DEM relief — 1.0 rides the hill, 0.0 is a plane through it, and this is the headline), `cut_max_m` / `fill_max_m`, \|emitted−DEM\| median + p95, emitted vs DEM grade (max and median), and `dem_followable_pct` — the share of steps whose DEM grade is ALREADY within the road cap, which is what turns "flat" into "flat where the law allowed it to climb". **It measures no law and counts no defects**: geometry and altitudes come from `check_grade._parse_osm`, the role from `check_grade.law_role`, the road family from `check_grade._ROAD_FAMILY_ROLES` (which IS `grade_law.ROAD_ROLES`), the metre frame from `check_grade._ll_to_m_factory` about the sidecar's anchor, and the DEM through `apron_drape_read`'s own loaders and `_dem_at` (the engine's own `dem.alt`) — every set, parser and sampler IMPORTED, never re-spelled (the census-wrapper precedent). Every report also carries the COMPOSITION-FREE reading over ALL road-family vertices — |emitted−DEM| median + p95, the count of vertices cutting deeper than 5/10/20 m, and the worst — because chains are arm-dependent (emit decimation drops collinear vertices, so a flattened road fuses differently) while that population is not. **TWO POPULATIONS (2026-08-31, linear-transport Batch 1).** A `PATCH.osm` carries auto_patch's road pavement; **`--levelled-roads <tile>/o4_levelled_roads.json`** carries the CORE-owned roads, which emit as mesh `INTERP_ALT` ring altitudes and leave NO patch rows at all — invisible to the patch mode, to `check_grade` and to every census (RULINGS 2026-08-31b "LEVERAGE THE CORE"; spec `docs/specs/linear-transport-redesign-spec.md` §2 item 4). The sidecar is written by `O4_Vector_Map.include_roads`' longitudinal clamp pass: per OSM WAY, the centerline stations it clamped (<=20 m apart, so the instrument outresolves `emit_decimate`'s 60 m chords), each station's lat/lon, the terrain under it and the altitude the road took. The SAME statistics are computed from those two numbers and the SAME `--rank` / `--site` / `--profile` / `--json` readers print them — no second instrument. Its frame is DECLARED and is NOT the patch frame: one WAY per chain (not a shared-node component), the profile UNBINNED at the clamp's own stations, the DEM as the BUILD sampled it (no `--dem-source` applies), and the cap judged against is the SIDECAR's own `grade_cap`, not this file's constant. A levelled-roads arm compares to another levelled-roads arm and NEVER to a patch arm; the report says so whenever both are printed. It also prints the CLAMP read: ways, stations, how many were clamped beyond the 0.01 m materiality floor, and the max lift and max cut. Three modes: `--rank` DISCOVERS a patch's hill sites (chains over `--min-relief`, longest first, with way ids, end lat/lon and the deepest-cut coordinate), and `--site NAME=LAT,LON` reads ONE PLACE across arms, control first, joined by PLACE and never by way id (`arm_site_read`'s frame rule — ids are arm-dependent); `--profile` prints each arm's station/emitted/DEM table. A site with no chain inside `--site-radius` is reported with its nearest distance, never as zero. `--dem-source airport-inset` (default) is THE SURFACE PRODUCTION GRADES ON; a missing surface REFUSES rather than substituting the other, because two arms on two DEM sources are not comparable. Numbers are comparable ARM TO ARM on identical options and nowhere else. **`--by-ref` (lane `v2roadcap2`, 2026-09-13, RULINGS 2026-09-13ab)**: the same population and the same samplers, grouped by SOURCE REF (`dsf:pol51`, `pav17`) — vertices, worst FILL and worst CUT off the DEM each with its own coordinate, |emitted-DEM| median and p95, worst first. The ref is the unit the owner names a site by and the unit a CLASSIFICATION fix moves; the chain is arm-dependent (emit decimation re-fuses it) and the whole-airport reading hides one road behind 800 lawful vertices. FILL is reported apart from CUT because a road held UP in the air (owner item 5, KCLT `dsf:pol51` +13.28 m) is invisible to a cut-only reading. Scout `v2roadcapkclt` wrote a one-off for exactly this; promoted on its second use (RULINGS `7e90032`). **SIDECAR v2 (lane `roadclampscope`, 2026-09-18, RULINGS 2026-09-18n; spec `linear-transport-redesign-spec.md` §2-SUPPLEMENT S.4 row 10)**: the clamp is now scoped to the PATCH NEIGHBOURHOOD, so each way is priced against ITS OWN cap — the run's yielded `cap_eff` outside the band, `cap_inside` within it — and a `scope="terrain"` way (the base engine's road on the terrain, no longitudinal law) is COUNTED and NOT PRICED; the clamp read adds `sidecar_version`, `cap_inside`, `runout_m`, `budget_m`, `cap_ceiling`, `neighbourhood_ways`, `terrain_ways`/`terrain_stations` and the run counts. A v1 sidecar reads exactly as before. Twin: `Ortho4XP/tests/test_road_terrain_conformance.py` (the DEM is INJECTED, so the law is stated on a surface the twin owns — no corpus, no network; the `--by-ref` grouping, the fill/cut split, the worst-vertex coordinate and this index row). |

## Registered frames: CYXY

CYXY  patch    base 8dac3c6b   lane v1settings       2026-09-13T12:56:32  /tmp/harness/v1settings_base.osm  [MISSING]  — base arm: CYXY --engine v2 at main 8dac3c6b, body_sha fc59980475f5 (v1-retirement stage A control)
CYXY  patch    base 9ae9e5a9   lane v1settings       2026-09-13T12:56:32  /tmp/harness/v1settings_lane.osm  [MISSING]  — lane arm: CYXY, no --engine flag, body_sha fc59980475f5 — byte-identical to the base arm
CYXY  patch    base dc5517c0   lane solvemodel       2026-09-13T15:55:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/base_CYXY/CYXY_20260913T155123.osm  [MISSING]  — BASE arm, solve_model retirement closing test; body_sha ca2c7bbaa57e, 314 ways / 4690 nodes / 344 verify rows
CYXY  patch    base dc5517c0   lane solvemodel       2026-09-13T15:55:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/lane_CYXY/CYXY_20260913T155153.osm  [MISSING]  — LANE arm (claude/solvemodel fdd291e9); body_sha ca2c7bbaa57e — byte-identical to the base arm, patch cmp-clean
CYXY  patch    base ce203b29   lane v2zonebank       2026-09-13T17:33:35  /tmp/harness/CYXY_20260913T173248.osm  [MISSING]  — CYXY control on claude/v2zonebank cde84e27 (rc 0, 16.4 s, body_sha b38fbb12b262) — census law-true 1,087, bank_across_seam 0, stacked_nodes 0 (the RULINGS 10g plateau-tearing class clean)
CYXY  patch    base fef82b29   lane v2slivers        2026-09-14T09:05:36  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2slivers/cyxy/v2sl_cyxy2.osm  [MISSING]  — CYXY control, lane arm (claude/v2slivers 88dfed33): rc 0, 13.6 s, ways 268, body_sha 018092d831df. NOT byte-identical to the base arm and lawfully so: CYXY carries 12 zone slivers / 339 m2 and 4 hairline hole rings at base, all dissolved/suppressed. Base arm v2sl_cyxy_base (main fef82b29): 284 ways, body_sha 673393ea5af0, 121 graded_strip faces / 12 slivers, 13 rings / 4 hairline
CYXY  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/CYXY.osm/cyxylane.osm  [MISSING]  — CYXY control, LANE arm (claude/v2cost2 12b29e6c): rc 0, 12.9 s, body_sha 018092d831df — cmp-IDENTICAL to the base arm at main 4c6f467c in scratchpad/v2cost2/base/CYXY.osm/cyxybase.osm (13.2 s, same sha)
CYXY  patch    base 55cf0fe3   lane v2cost2          2026-09-14T11:31:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/CYXY_r2.osm/cyxyr2.osm  [MISSING]  — CYXY control, round 2 lane arm (claude/v2cost2 7bc09ea7): rc 0, 14.2 s, body_sha 018092d831df, cmp-IDENTICAL to the base arm scratchpad/v2cost2/base/CYXY.osm/cyxybase.osm
CYXY  capture  base 12400580   lane v2settle         2026-09-14T23:01:33  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/CYXY.pkl  [MISSING]  — v2_solve_replay --capture CYXY on main 12400580 (8 s, 4,503 vertices / 261 faces); guard shared repo UNCHANGED. The cheap control: single solve 17/32,327 hard rows violated, active-set exits line_search_stalled x1 (never the set's own fixed point). Lane v2settle r2's byte-identity arm.
CYXY  graded   base 63258868   lane v2qp             2026-09-15T00:29:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2qp/emit_cyxy_qp/CYXY.graded.json  [MISSING]  — QP ARM of the v2qp matched CYXY replay pair off cap/CYXY.pkl (base 12400580): solve 3.2 -> 4.2 s (1.31x), status feasible -> optimal, hard rows over 0.02 m 17 -> 12, runway projection worst hard row 0.0044 -> 0.0002 m, lag worst leader move 0.319 -> 0.162 m. BASE ARM at emit_cyxy_fp/. Census A/B ADJUDICATED 427 -> 379 (-11.2 %), NO family worse. The FISTA cross-check and the HiGHS refutation were measured on this capture (scratchpad/v2qp/*.log)
CYXY  patch    base f32fb08c   lane v2channel        2026-09-15T10:23:52  /tmp/v2channel/r3/br_CYXY/structures.json  [MISSING]  — v2channel round-3 DRY structure replay (branch), paired with base CYXY at main 46b219d8 in /tmp/v2channel/r3/base_CYXY
CYXY  patch    base 395bd09a   lane v2channel        2026-09-15T10:52:05  /tmp/v2channel/r4/br_CYXY/structures.json  [MISSING]  — v2channel round-4 DRY structure replay (branch, §45 (13)); base arm at main in /tmp/v2channel/r4/base_CYXY
CYXY  capture  base 3e15a18d   lane v2shoulderband   2026-09-16T09:10:47  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/sb/r2/cap/CYXY.pkl  [MISSING]  — CYXY capture carrying §40 (5), taken AFTER merging the peer's v2usgsbox (main bc7f16a2) which un-refused CYXY's two version-stale USGS3DEP negatives (4 s, 4,474 vertices / 257 faces, guard UNCHANGED). One §40 (1) shoulder, 14,399 m2 on 14L/32R reaching 172.3 m -> band 12,778 m2 (88.7 %) + 1,621 m2 stub. The end cap changes NOTHING here
CYXY  patch    base 3e15a18d   lane v2shoulderband   2026-09-16T09:10:47  /tmp/harness/v2sb_CYXY2.osm  [MISSING]  — closing CYXY build of v2shoulderband r2 (post-v2usgsbox merge): rc 0, 15.5 s, ways 276, nodes 4423, body_sha 98fb821518ab, artifact ledger c23bbd629ce5, optimal, v2-verify 339 rows, every §40 DEFECT family ZERO, shared repo UNCHANGED. Census law-true 1,102 adjudicated 375
CYXY  patch    base f1313f75   lane xplatcrlf        2026-09-17T15:58:33  /tmp/harness/crlffix.osm  [MISSING]  — LANE arm, newline pinning (claude/xplatcrlf a5d24ed5): CYXY rc 0, 12.4 s, ways 268, nodes 4335, body_sha e1b9e0e9cc19 - byte-IDENTICAL to the pre-fix base arm /tmp/harness/crlfbase.osm at f1313f75 (same body_sha, same file sha256 6994aa0e2eff); CYXY.graded.json and CYXY.rebake.json also sha256-identical. Proves the CRLF pinning is a no-op on POSIX. Shared repo UNCHANGED both arms.
CYXY  patch    base 2fb0799f   lane xplatspread      2026-09-17T16:12:39  /tmp/harness/xplatspread  [MISSING]  — NOT a harness build: the CROSS-PLATFORM PROJECTION frames, Release run 35285038635 (r2) on branch claude/xplatspread, all three runners GREEN (r1 = 35283889554). Re-fetch: gh run download 35285038635 -p 'frozen-tile-logs-*'. Each of mac/linux/windows carries CYXY.xproj.json (exact float.hex of every load-stage to_xy, N=2847; a 289-point lattice probe forward+inverse to 14 km; solved z per vertex), CYXY.xplat.json (stage digests), the emitted patch, and quantised/ = the same with the load projection snapped to 1 mm plus 73,528 exact constraint rows. Read with scripts/check_frozen_tile.py --compare-projection / --compare. MEASURED: to_xy spread 4e-10 m mean / 2.1e-9 m max (17d's (5e-7,5e-5) bracket over-read a dp6 digest), ZERO straddles at 1e-4/1e-3/1e-2/0.5 m, Linux != Windows (84 of 2847); in the 1 mm arm LP 17289x1918 / 181 rounds on all three and the emitted patch BODY byte-identical (header excluded, CRLF normalised).
CYXY  patch    base 6c8dfe71   lane xplatquantum     2026-09-17T17:19:12  /tmp/harness/xq_base.osm  [MISSING]  — BASE arm at main 6c8dfe71 (§46 price): rc 0, 13.2 s, ways 268, nodes 4335, optimal, body_sha e1b9e0e9cc19 (= the xplatcrlf frame), v2-verify 311 rows; census law-true 1,101 ADJUDICATED 368. Shared repo UNCHANGED. Artifact ledger 95812416b348.
CYXY  patch    base 6c8dfe71   lane xplatquantum     2026-09-17T17:19:12  /tmp/harness/xq_lane3.osm  [MISSING]  — LANE arm, claude/xplatquantum 0992d747 (§46 1 mm input quantum): rc 0, 13.0 s, ways 268, nodes 4330 (-5), optimal, body_sha ad542d0955b3, v2-verify 335 rows; census law-true 1,104 (+3) ADJUDICATED 384 (+16, +4.3 %). No object-stage refusal at CYXY (80 objects skipped, rebake units 0), so RULINGS 17g residual (3) did not bite. The junction-buffer repair is INERT here (same body_sha before and after it). Shared repo UNCHANGED.
CYXY  patch    base e2ca979a   lane xplatquantum     2026-09-17T17:43:30  /tmp/harness/xq_r2_cyxy.osm  [MISSING]  — ROUND 2 lane arm (claude/xplatquantum 9cd71efa, §46 (9) census row 16: the tile water-mask polygons switched to Frame.entry()): rc 0, 12.9 s, ways 268, nodes 4330, optimal, body_sha ad542d0955b3 — BYTE-IDENTICAL to the round-1 lane arm /tmp/harness/xq_lane3.osm, so row 16 is inert at CYXY. Shared repo UNCHANGED. Release 35291801734 gate GREEN (patch body 301280a0e02e byte-identical on all three); the gate's first run on MAIN, 35291627055, is GREEN with the same verdict.
CYXY  capture  base 0bac9241   lane b2frontagedatum  2026-09-18T17:15:38  /tmp/b2fd/CYXY.pkl  [MISSING]  — CYXY capture at main 0bac9241 (7 s, 4,412 vertices / 261 faces, guard UNCHANGED) — the §28 (6) option-C population arm: tools/pad_frontage_step.py reads 4 pairs, building9->pav4 +4.192 / building10->dsf:pol129 +3.283 TERRACE, building1->pav29 +0.047/+0.082 ARMED
CYXY  patch    base 0bac9241   lane b2frontagedatum  2026-09-18T17:15:38  /tmp/harness/CYXY_20260918T171219.osm  [MISSING]  — CLOSING BUILD of the option-C change (claude/b2frontagedatum): rc 0, 12.9 s, ways 273, nodes 4340, optimal, body_sha 74a61fd896b3, ledger ffa50922f000, shared repo UNCHANGED. groundside_frontage_level.pairs_held_as_terrace 2 (was 0). Census law-true 1,378 adjudicated 373 — NOT a matched A/B, no base arm was built
CYXY  capture  base 1280cc3e   lane insetpatchset1   2026-09-18T17:39:15  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/80ca8b90-a6be-4952-b61f-ace3ff9007d9/scratchpad/cap/CYXY.pkl  [MISSING]  — R_patch control capture (7 s, 4,412 vertices / 261 faces) on main 1280cc3e; guard UNCHANGED. Emitted nodes reach 1110.1 m beyond _own_extent(margin 0); z_many reads reach 5,090.4 m over 2,276 batches. Also the first capture taken with airport_elevation_insets as the None/ICAO/All enum (log: 'Legacy config value True for airport_elevation_insets read as ICAO').
CYXY  patch    base 1280cc3e   lane insetpatchset1   2026-09-18T17:41:01  /tmp/harness/CYXY_20260918T173959.osm  [MISSING]  — CLOSING control build of claude/insetpatchset1 76ca638f (spec insets-follow-patch-set §E): rc 0, 12.7 s, ways 273, nodes 4340, status optimal, body_sha 09e38e9576d8, artifact ledger 002b7cf90da9, v2-verify 362 rows, shared repo UNCHANGED. Proves the enum relabel + the patch selector + the ONE inset trim leave the no-boundary path building normally; the emit/solve path is untouched by this branch so no OFF-arm byte-identity pair was run (BUILD ECONOMY).
CYXY  patch    base df2881d4   lane insetpatchset1   2026-09-18T18:26:20  /tmp/harness/CYXY_20260918T182549.osm  [MISSING]  — BASE ARM at clean main df2881d4 (ritual worktree insetbase): rc 0, 13.3 s, ways 273, nodes 4340, optimal, body_sha bd4a5d6c6bf4, v2-verify 349 rows. Pays RULINGS 18h's owed 'new CYXY control' after §50 (the cap yields): the pre-§50 control at 1280cc3e was body_sha 09e38e9576d8 / 362 verify rows, so the move is §50's, not any later lane's.
CYXY  patch    base df2881d4   lane insetpatchset1   2026-09-18T18:26:20  /tmp/harness/CYXY_20260918T182442.osm  [MISSING]  — CLOSING control of claude/insetpatchset1 29c085fb (slice 1d complete): rc 0, 12.8 s, ways 273, nodes 4340, optimal, body_sha bd4a5d6c6bf4, ledger 1bfcbe78639c, v2-verify 349 rows, shared repo UNCHANGED. BYTE-IDENTICAL to the base arm at main df2881d4 — slice 1d (airside claim, class S/M, _warm_tile deletion, context-only far side, protocol 1.8) touches NO geometry path at a single-tile class-M airport. frame.json inset_selection {mode ICAO, admitted true}.
CYXY  patch    base c0912e54   lane packmst          2026-09-18T21:20:51  /tmp/harness/CYXY_20260918T211647.osm  [MISSING]  — BASE ARM at clean main c0912e54 (ritual worktree packmstbase): rc 0, 14.3 s, ways 273, nodes 4340, optimal, body_sha c0010b201f35, v2-verify 349 rows, ledger 0adbe94f66a0, shared repo UNCHANGED. Main's c0912e54 moved CYXY off the df2881d4 control (bd4a5d6c6bf4 -> c0010b201f35), so a fresh base arm was required.
CYXY  patch    base c0912e54   lane packmst          2026-09-18T21:20:51  /tmp/harness/CYXY_20260918T211716.osm  [MISSING]  — CLOSING build of claude/packmst 9b59fb55 (S1: Delaunay-candidate heap Prim for the feet MST): rc 0, 13.3 s, ways 273, nodes 4340, optimal, body_sha c0010b201f35, ledger 8a5099773c42, v2-verify 349 rows, shared repo UNCHANGED. BYTE-IDENTICAL to the base arm /tmp/harness/CYXY_20260918T211647.osm (cmp-clean over the WHOLE file, not just the body). NOTE CYXY has rebake units 0 / 80 objects skipped, so it exercises the emit/solve path, not ground_fit; the MST identity proof is the twins + the two real pickled inputs (TNCM 27,376 pts 34.63 s -> 0.12 s, TFFG 86,592 pts 421.72 s -> 0.46 s, ordered edge list == on both, 4,106 / 52,833 tied lengths, 0 fallbacks).
CYXY  capture  base 8224729d   lane cyxyflip         2026-09-25T21:37:55  /Users/noah/XPTerrainBuilderData/.harness/frames/cyxyflip/CYXY.pkl  — CYXY capture (issue #2 CYXY-1). Dry reclassify at main 4cd4025f reproduces its own cl exactly (0 ref/role keys differ). Base (no centreline mouth) flips 7 faces, fix flips 4: dsf:pol123/pol20/pol17 apron -> parking_lot, NO other ref changes
CYXY  patch    base 4cd4025f   lane cyxyflip         2026-09-25T21:37:55  /Users/noah/XPTerrainBuilderData/.harness/frames/cyxyflip/CYXY_20260925T213619.osm  — BASE ARM at clean main 4cd4025f (worktree cyxybase): rc 0, 20.9 s, ways 273, nodes 4340, optimal, body_sha c0010b201f35 (= packmst control, main has not moved CYXY), v2-verify 349, ledger 8f8a5965d5e4, shared repo UNCHANGED. Census LAW-TRUE 1,378 ADJUDICATED 373 (airside 294 / groundside 79)
CYXY  patch    base 4cd4025f   lane cyxyflip         2026-09-25T21:37:55  /Users/noah/XPTerrainBuilderData/.harness/frames/cyxyflip/CYXY_20260925T213651.osm  — LANE ARM claude/cyxyflip 8c32b520 (§27 centreline mouth, #2): rc 0, 20.1 s, ways 272, nodes 4337, optimal, body_sha cc4c865614d6, v2-verify 318, ledger 32d14c7fed44, shared repo UNCHANGED. Census LAW-TRUE 1,311 (-67) ADJUDICATED 322 (-51; airside 240 -54 / groundside 82 +3). pol123/pol20/pol17 parking_lot (parking_lot tags 19 -> 22)
CYXY  capture  base 4cd4025f   lane surfacesettle    2026-09-25T22:07:49  /Users/noah/XPTerrainBuilderData/.harness/frames/surfacesettle/CYXY.pkl  — CYXY capture at main 4cd4025f (11 s). Control: lane solved z array-identical to base (both fixes); report 15 / 0.7278 m -> 14 / 0.3639 m (instrument only).
CYXY  capture  base be2dfd43   lane surfacesettle2   2026-09-27T23:42:31  /Users/noah/XPTerrainBuilderData/.harness/frames/surfacesettle2/CYXY.pkl  — capture at main be2dfd43 + lane PlanarMap fields road_reach_seed/road_join_yield (tree e26d68d9); replay --from constraints
CYXY  patch    base de25a131   lane sw0930           2026-09-29T16:55:01  /Users/noah/XPTerrainBuilderData/.harness/frames/sw0930/sw0930_CYXY.osm  — sweep round 8 sw0930 on main de25a131 (#11 terrace floor 1.0, #115); KCLT runway moved 0.85 m -> #117; HECA runway 0 vs reference; app 1.0.362
CYXY  capture  base 3b3e4ed1   lane hardhold128      2026-09-30T08:48:12  /Users/noah/XPTerrainBuilderData/.harness/frames/hardhold128/CYXY.pkl  — v2_solve_replay --capture CYXY on main 3b3e4ed1 (15 s, 4,460 vertices; no platforms)
CYXY  patch    base f3b19a20   lane hardhold128      2026-09-30T08:48:13  /Users/noah/XPTerrainBuilderData/.harness/frames/hardhold128/hardhold128_CYXY.osm  — CLOSING CYXY build hardhold128_CYXY, claude/hardhold128 f3b19a20 (#128 hard frontage hold): rc 0, 20.8 s, body_sha 60dc4be74f0a, ledger a6b14a175390, shared repo UNCHANGED. CYXY mints NO platform, so the hold never fires: airside 0 movers vs sw0930, census identical (adjudicated 254, motion 0, visual 25)
CYXY  patch    base fbf0d57c   lane flatpad128v2     2026-09-30T09:25:47  /Users/noah/XPTerrainBuilderData/.harness/frames/flatpad128v2/g0_CYXY.osm  — G0 replay (flat-pad v2 §8 step 2): stage 0 runway-alone, hold OFF (--from constraints on frames/hardhold128/CYXY.pkl @3b3e4ed1), claude/flatpad128v2 fbf0d57c. G0 FAILS: 32 runway movers vs sw0930, worst 0.227 m 60.71104978086,-135.06435298322 (no_step_rate binds in the ref). Base replay (no stage 0) = reference runway 0 at 0.02.
CYXY  patch    base 8d014dc1   lane reference        2026-09-30T12:29:55  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1002_CYXY.osm  — airside REFERENCE re-cut at sw1002 / app 1.0.366 per RULINGS 2026-09-30ak/30am (continuous transverse bound, yield envelope, taxi yield): HECA runway 173 movers worst 0.29 m vs sw0929c (bound 0.30), KCLT 14 worst 0.10 vs cifp119, SPJC 20 worst 0.22, SPLP 228 worst 0.50 (yielded runway to its pin line), CYXY/NLWF identical
CYXY  patch    base a63577d8   lane flatpad128v3     2026-09-30T17:42:44  /Users/noah/XPTerrainBuilderData/.harness/frames/flatpad128v3/pass1a_CYXY.osm  — PASS 1a CONTROL (flat-pad v2 A1 (a)): replay --from planar on frames/hardhold128/CYXY.pkl with --drop-generator 'structures.building_pad frontage_hold'; runway vs sw1002 = 0 movers at 0.02
CYXY  patch    base 82cadcb2   lane flatpad128v3     2026-09-30T17:42:44  /Users/noah/XPTerrainBuilderData/.harness/frames/flatpad128v3/replay_CYXY.osm  — flat-pad v2 full-mechanism replay --from planar on frames/hardhold128/CYXY.pkl
CYXY  patch    base 2f32dddc   lane flatpad128v3     2026-09-30T18:19:03  /Users/noah/XPTerrainBuilderData/.harness/frames/flatpad128v3/fix_CYXY.osm  — RULINGS 30bb fix arm replay --from planar on frames/hardhold128/CYXY.pkl
CYXY  patch    base 8364d7cd   lane reference        2026-10-01T01:08:12  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1003_CYXY.osm  — airside REFERENCE re-cut at sw1003 / app 1.0.367 per RULINGS 2026-10-01a (apronhard batch: hard apron cap, runway flex Bands, road joins on airside faces unpinned) + 30bu/30bw ladder: CRITICAL motion HECA 18->2, KCLT 3->4 (new worst 2.59 m pavement_over_road_cap apron|apron at 35.2068281,-80.9422880, the #143 class), SPJC 0->0, CYXY 0->0, KASE 3->1; adjudicated HECA 18005->13380, KCLT 6954->5640, SPJC 1215->1279, CYXY 343->333, KASE 3280->2780
CYXY  capture  base 96665331   lane holefill154      2026-10-01T08:12:09  /Users/noah/XPTerrainBuilderData/.harness/frames/holefill154/CYXY.pkl  — control capture at claude/holefill154 (shared corpus): replay --from constraints --emit byte-identical to the same capture+replay at main 0cfa2fb1 (patch 9ca5938c8f2f whole-file, axes 80b59969cfd2, graded de426e4535ab)
CYXY  capture  base 5c26ff0c   lane ringsq1          2026-10-01T21:50:47  /Users/noah/XPTerrainBuilderData/.harness/frames/ringsq1/CYXY.pkl  — control capture at main 5c26ff0c (12 s, 4,460 vertices); claude/ringsq1 dfa30a62 capture + replay --from constraints --emit byte-identical (patch 8d3be4b9/c16fc763/d9df535e md5 of graded/osm/axes). Pickles differ only at one trailing byte (capture metadata; two same-tree captures differ there too).
CYXY  patch    base 219fbccd   lane reference        2026-10-02T03:23:09  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1005_CYXY.osm  — airside REFERENCE re-cut at sw1005 / app 1.0.368 (main 219fbccd; RULINGS 2026-10-02o/p/q): vs sw1003 — CYXY identical; KASE 27 movers 0.15 m (the §12 inset re-cut); HECA 3,103 movers 0.82 m = flatpad150's restored b3 plateau, runway 0; KCLT 4,867 / 1.64 m and SPJC 2,899 / 6.42 m = flatpad150's restored plateaus (KCLT 77,000 -> 196,933 m2, SPJC 47,040 -> 173,048 m2) + roadrows143's road releases (apron#475 1.15 m, apron#155 5.07 m), attributed on one capture per airport (arm D with both reverted = 0 movers); defects carried: #150 sliver mints (KCLT ~40 pav14 faces 0-6 m2, SPJC ~21 pav49), #223 SPJC building14#collar spike 46.26 m (pre-existing 39.84 in sw1003), #199 merge-survivor flips; CRITICAL under today's census: CYXY 0, SPJC 0, KCLT 7 (= reference), KASE 2, HECA 2 (one #215 artefact each)
CYXY  capture  base 0b073dd2   lane basepads4read    2026-10-02T04:56:49  /Users/noah/XPTerrainBuilderData/.harness/frames/basepads4read/CYXY.pkl  — v2_solve_replay --capture CYXY on claude/basepads4read 0b073dd2 (main 8f00ab04 + PR #220 ee04df5d); carries the #208 planar registries; --from planar and --from constraints emit BODY-IDENTICAL patches at all 5
CYXY  patch    base 41543772   lane reference        2026-10-02T12:24:24  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1010_CYXY.osm  — sweep sw1010 reference (RULINGS 2026-10-02aa)
CYXY  patch    base 66caa624   lane roadmint100      2026-10-02T17:55:16  /Users/noah/XPTerrainBuilderData/.harness/frames/roadmint100/roadmint100b_CYXY.osm  — roadmint100b CYXY control arm: vs main (ledger a2c619bc3535) 231 solve-owned movers worst 0.80 m cross_connector|graded_strip at 60.70706486692,-135.07487441567, apron 0.49, taxi 26/0.38, runway 2/0.02, 174/170 airside nodes re-noded — the rule moves CYXY's airside (BAR MISSED)
CYXY  patch    base e3776af9   lane roadmint100      2026-10-02T18:12:44  /Users/noah/XPTerrainBuilderData/.harness/frames/roadmint100/roadmint100d_CYXY.osm  — roadmint100b arm 3 CYXY control arm vs sw1012_CYXY: 30 solve-owned movers worst 0.22 m graded_strip|primary_parallel|service_road at 60.70167119403,-135.06383213825 (zone_bands row), apron 12 <= 0.03, taxi 1 0.02, strip 16; airside nodes 1 A-only / 1 B-only (arm 2: 231 / 0.80 m / 174+170) — bar 30z (1) NOT met
CYXY  patch    base 632eaaaa   lane reference        2026-10-02T17:52:48  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1012_CYXY.osm  — sweep sw1012 reference (RULINGS 2026-10-02ac)
CYXY  patch    base af902d07   lane reference        2026-10-02T18:07:59  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1013_CYXY.osm  — sweep sw1013 reference (RULINGS 2026-10-02ae)
CYXY  patch    base f3d34b7b   lane roadmint100      2026-10-02T18:48:00  /Users/noah/XPTerrainBuilderData/.harness/frames/roadmint100/rm3a_CYXY.osm  — roadmint100b round 3 CYXY control arm vs sw1013_CYXY (== sw1012): 30 solve-owned movers worst 0.22 m at 60.70167119403,-135.06383213825, 1 A-only / 1 B-only; stage 1 2377/4844 vs main 2377/4845 — bar 30z (1) NOT met; the zone band rows are already one-way (follows=v), the one missing stage-1 row not yet named
CYXY  patch    base e59448e4   lane cyxy262          2026-10-02T18:34:26  /Users/noah/XPTerrainBuilderData/.harness/frames/cyxy262/cyxy262_CYXY.osm  — CLOSING CYXY build cyxy262_CYXY, claude/cyxy262 e59448e4 (#262 startup refuses corridor, #263 .agp hangar pads, #264 held terrace pair never welded by the fallback cap): rc 0, 20.5 s, body_sha 7248cafa727b, ledger 6bb3b1c53a90, shared repo UNCHANGED. vs sw1010_CYXY: solve-owned 289 movers worst 2.29 m (apron pav5 re-kinded: taxi 54 / apron 36 / strip 187), runway 6 worst 0.24 m at 02/20's SE end (flex envelope, pulling block building2, caps held); census CRITICAL motion 0 -> 1 (raoa apron|apron grade break 0.24 m / 24.1 m at 60.7106099,-135.0735336 — engine raoa family is SOFT, census CRITICAL; exposed by the pav5 re-kind), visual 25 -> 19, adjudicated 332 -> 409; pads 10 -> 14 (building8 = the owner's hangar, 2,066 m2); pav4 site 695.32 -> 698.55 m
CYXY  capture  base e59448e4   lane cyxy262          2026-10-02T18:34:26  /Users/noah/XPTerrainBuilderData/.harness/frames/cyxy262/CYXY_b.pkl  — v2_solve_replay --capture CYXY on claude/cyxy262 e59448e4 (13 s, 4,349 vertices; carries the 6 dsf:agp hangar footprints); --from planar --emit == the closing build cyxy262_CYXY body
CYXY  patch    base cc325354   lane reference        2026-10-02T18:45:57  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1014_CYXY.osm  — sweep sw1014 reference (RULINGS 2026-10-02af)
CYXY  patch    base HEAD       lane roadmint100      2026-10-02T19:23:18  /Users/noah/XPTerrainBuilderData/.harness/frames/roadmint100/rm3f_CYXY.osm  — roadmint100b round 3 CYXY arm vs sw1014_CYXY: 86 solve-owned movers worst 0.57 m graded_strip|primary_parallel at 60.69697726693,-135.06033596269, apron 41 <= 0.17, taxi 2 <= 0.09, 1/1 A-/B-only; census 1245/433 vs ref 1187/409, hairlines 53 vs 19 — bar NOT met
CYXY  patch    base 5fafe6d0   lane roadmint100e     2026-10-02T21:36:34  /Users/noah/XPTerrainBuilderData/.harness/frames/roadmint100e/rm100e_CYXY.osm  — CLOSING build rm100e_CYXY at claude/roadmint100e 5fafe6d0 (#100 round 5): vs sw1014: solve-owned 159 movers (sw1015 80), strip 98/0.29, apron 40/0.15, taxi 14/0.09; nodes A-only 1 B-only 1; CRIT motion 1 = 1; adjudicated airside 336 -> 335
CYXY  patch    base 2e5cce16   lane reference        2026-10-02T21:43:35  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1017_CYXY.osm  — sweep sw1017 reference (RULINGS 2026-10-02ai)
CYXY  patch    base e9019e0d   lane roadmint100h     2026-10-03T01:09:53  /Users/noah/XPTerrainBuilderData/.harness/frames/roadmint100h/rm100h_CYXY.osm  — closing build #100 r8 option (c)
CYXY  patch    base 7bb800f5   lane reference        2026-10-03T01:46:26  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1018_CYXY.osm  — sweep sw1018 reference (RULINGS 2026-10-03a)
CYXY  patch    base e6b3d06d   lane reference        2026-10-03T08:59:11  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1019_CYXY.osm  — sweep sw1019 reference (RULINGS 2026-10-03d)
CYXY  patch    base b6d5369f   lane reference        2026-10-03T09:53:54  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1020_CYXY.osm  — sweep sw1020 reference (RULINGS 2026-10-03f)
CYXY  patch    base 82bf8000   lane reference        2026-10-03T11:21:01  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1021_CYXY.osm  — sweep sw1021 reference (RULINGS 2026-10-03g)
CYXY  patch    base e7b9dc08   lane reference        2026-10-03T12:35:22  /Users/noah/XPTerrainBuilderData/.harness/frames/reference/sw1022_CYXY.osm  — sweep sw1022 reference (RULINGS 2026-10-03h)

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

