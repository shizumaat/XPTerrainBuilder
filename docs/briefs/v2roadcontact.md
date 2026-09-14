# Brief pack — lane `v2roadcontact`

Base: main `93a2a3d2` · generated 2026-09-13 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

§37 (10): taxiways are airside contacts (reach 15 m); route pairs by geometry; every airside ribbon priced

## The brief

Frame: the owner's 1.0.329 HECA products — data repo `Patches/+30+040/+30+031/HECA_auto.patch.osm` (+ `.axes.json` sidecar), `/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+30+031/HECA/` (report.json, graded), the shipped `zOrtho4XP_+30+031` tile — ALL READ-ONLY. `auto_patch_v2 explain --shape N --patch <that patch> HECA` (pass `--patch`; the engine-tree default is a Sep 9 patch with different shapeIDs; `--shape` goes BEFORE the ICAO). Scout `v2heca329`'s numbers are in RULINGS 13cs; its declared reader `heca_probe.py` (xref/samp/line) is in the session scratchpad `/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/` — reuse via `tools/mesh_region_tris.py --z-xref` and `tools/osm_site.py` where they fit. Dry arm on the 1.0.329 products first; ONE HECA build through `tools/harness/build_airport.py HECA` as the closing test; other airports dry from registered frames (`frames.py list`). Lanes running beside you: `v2bankfoot` (O4_Vector_Map / O4_Mesh_Utils / emit/bank.py — do not touch), `v2connector` (airport/footprint_unit.py), `v2gradecache` (planar cost).
Implement §37 (10) in `Ortho4XP/src/auto_patch_v2/constraints/road_ramp.py` / `airport/road_ramp.py` (and `solve/design_report.py` for the census): (1) the airside contact set = apron, pad, lot, every taxi-family role, junction, stub, runway shoulder (§40, landing in lane `v2roles` — read the role names from `classify/roles.py`, do not wait for it); a road ending within `contact_reach_m` (15 m, new law key in `law/emit.toml`) of an airside edge without touching it takes a contact at the nearest edge point at that face's solved level; (2) two routes whose frames place vertices within `pair_lateral_m` (6 m) of each other over ≥ `pair_overlap_m` (10 m) of arc are MERGED into one route before §37 (7)'s pairing; `NOT_A_PAIR` never for two vertices on one ribbon; the census names merged pairs; (3) the cross-section then prices every airside ribbon. Sites: (5) `service_road:route0` end 30.1077666, 31.4031555 at 108.09 vs pav74's edge 106.9 (33 % over 4.4 m); (4) 30.1096746, 31.4048466 (route 5936, t +4.10) vs 30.1096476, 31.4048517 (route 5934, t −2.12): 1.30 m over 3.05 m; (3) `route7` at 109.14–110.17 beside `apron:pav131` 108.43 (11.6 m), `pav115` cross-slope 2.03 % over 28 m. `tools/road_terrain_conformance.py --by-ref`, `v2_solve_replay --why-at` on a fresh HECA capture (register it). Twins for the contact reach and the geometric pair merge.

## Bars

- route0's end within 0.05 m of pav74's edge level; the 33 % step gone (profile every 1 m over 10 m from the end).
- Item-4 pair: priced; step ≤ 2 % over 3.05 m (today 42.6 %); `road_cross_section` rows HECA 4 → every ribbon (count named), none > cap after.
- route7: contact from pav131; `pav115` cross-slope ≤ 1.5 % at 30.1114112, 31.4063353 (today 2.03 % over 28 m); the "hill" at 30.1116052, 31.4066985 lowered to the bench (number).
- `road_ramp` / `transverse` / `road_cross_section` census before → after on HECA (build) and KCLT (dry from its registered frame); no airside vertex moves (airside is king).
- Suite twice.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/constraints/road_ramp.py`, `Ortho4XP/src/auto_patch_v2/airport/road_ramp.py`, `Ortho4XP/src/auto_patch_v2/emit/road_join.py`, `Ortho4XP/src/auto_patch_v2/law/emit.toml`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/classify/`, `Ortho4XP/src/auto_patch_v2/planar/`, `Ortho4XP/src/auto_patch_v2/emit/bank.py`

## Spec (design-surface) §37 (10)

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

## RULINGS

## 2026-09-13cs HECA eight items attributed (scout `v2heca329`): none is the 13cp mesh regression; §40, §41, §37 (10) written; lanes `v2roles`, `v2zonehole`, `v2roadcontact`

Scout on the owner's 1.0.329 +30+031 tile, read-only. Tile-wide node→mesh
cross-reference: PATCH_RING 27,673 vertices 0 off; road ribbons 271,698, 2
off (both ~100 km from HECA); at every owner site mesh = patch to 0.000 m.
The 13cp condition IS present (128 open `bank_foot` ways vs 9 closed;
annulus seeds 252 → 3, valued vertices 84,631 → 0, INTERP_ALT 629,054 →
369,060, harmonic "kept own" 374) but landed on no authored HECA vertex.

| # | class | ruling |
|---|---|---|
| 1 shape 44 | PATCH-ROLE: 585 m along runway 05L/23R, 73 % apron cover, still a corridor (no rung refuses it) | §40 (1) runway shoulder joins the runway body; §40 (2) apron cover refuses the corridor kind |
| 2 dip | PATCH-SOLVE: zone2#7 strip and `cross_connector:pav77` (100 % inside pav73) emitted over the taxiway; 8.6 % climb-out, verify blind | §41: inner face = hole; zones clipped out of pavement; `zone_on_pavement` census; `role_overlap_read.py` repaired |
| 3 hill | PATCH-SOLVE: route7 holds the DEM 1.5 m above the cut ground beside pav131 | §37 (10) (1) contact within reach |
| 4 road step | PATCH-SOLVE: two route frames on one ribbon → `NOT_A_PAIR`, 42.6 % never priced | §37 (10) (2) pairs by geometry |
| 5 cliff | PATCH-SOLVE: taxiway not in the contact set → road targets the DEM, 33 % step | §37 (10) (1) taxiways are airside contacts |
| 6 shape 93/478 | PATCH-ROLE: corridor (width 27.8, apron 13 %); 478 is its zone strip | §40 (2)/(3) |
| 7 floating building | OBJECT, NOT REPRODUCED: pad 88.88–88.98 = mesh 88.955; `T3_60.obj` in `unit:41` (36 members, anchor 1.7 km away, 19.47 m higher) but no seating row > 0.5 m within 70 m | owner asked for the object / a screenshot; standing HECA object debt noted: +19.70 m at 30.120503,31.402651 (`feet:20`, 1,144 m diameter), `Airport/T23` median −4.04 worst −11.71, 83 of 359 over 0.5 m |
| 8 missing apron | MISSING-SOURCE: 0 rings; nearest OSM apron 60.5 m, apt.dat pavement 110.6 m; the pavement seen is the pack's draped `.pol` page; the "feeder" is `apron:pav132` | INTENT QUESTION to the owner: admit the pack's DSF draped-pavement pages as source polygons (`dsf_pavements` admits one today)? |

* Lanes: `v2roles` (§40, `classify/roles.py` + `rules.toml`), `v2zonehole`
  (§41, planar zones + `role_overlap_read.py`), `v2roadcontact` (§37 (10),
  `constraints/road_ramp.py`, `airport/road_ramp.py`). HECA is the closing
  airport for each; dry arms first on the 1.0.329 products.
* Chips: `role_overlap_read.py` `KeyError: 'anchor'`; `auto_patch_v2 explain`
  defaults to the engine-tree patch (Sep 9) — must take `--patch`, and
  `--shape` only before the ICAO.
* Not verified: item 7; the `apron_named=1` token on cells 58/191 (source
  description matches no token — untraced); no registered HECA frame.

## 2026-09-13ba — v2roadramp MERGED (1fffc892, lane 63ef42f9 / merge dc4a8e43 after two rounds): §37 (6) the road ramp (`airport/road_ramp.py` + `constraints/road_ramp.py`; decks out) and §37 (7) ROAD PAIRS ALONG THE ROUTE — `road_ramp.road_route_frame` (every road-family ring vertex → route id, station, signed lateral, off the ways the ramp reads its DEM on; a through-way answers the outer kerbs; 174 KCLT vertices unframed keep the chord law) → `PlanarMap.road_route_frame` → sidecar `road_route_frame` (a LAW INPUT in `check_grade.SIDECAR_LAW_KEYS`); ONE reading `constraints/roads.road_pair_reading` imported by the generator, `verify/within` and `check_grade` (`cap_l·|Δs| + cap_t·|Δt|`, transverse by the angle in route coordinates, `NOT_A_PAIR` on two routes, chord law with no frame; a ring edge always priced; no bound under `cap_t × plan distance`). KCLT (ONE build `v2roadramp2` 5dcfccc142b9 vs a same-tree control at 70646dc8, 1f83c7a053d9): `dsf:pol51` follow 0.294 → 1.007, fill +13.31 → +1.59 m (MET); `dsf:pol82` +6.17 → +0.68 (0.18 over the bar); all-road |z−DEM| median 0.708 → 0.171, p95 3.348 → 1.674; refs over 3 m 8 → 2 (pol51's 5.33 m CUT + the excluded deck); the ten worst pairs: 7 not-a-pair (switchback), 2 route-followable, 1 real cross-section; v2 verify `road_cross_section` 781 → 462; LP rows 95,797 → 84,606, solve 104.6 → 71.5 s, build 311 vs 315 s; LEMD dry (157 vertices framed, the 61 apron lanes 0 targets, 13 decks excluded, governed ≤ 0.02) and CYXY dry (targets ≤ 0.01 off the core clamp) as before. NOT MET: the v1-era census `road_cross_section` 330 → 642 and adjudicated 3,813 → 5,684 — the two instruments DISAGREE IN DIRECTION: both PAIR identically (twinned); what differs is `check_grade`'s pair SELECTION (`shape_constraints(road_path_metric=True)`) and its allowance envelope, and the remaining rows are a road surface that now RIDES ITS TERRAIN, so a section that rolls with the ground breaks the 2 % cross-section; cockpit CRITICAL motion 7 → 12 with NO road row in either arm (the five new rows not yet named — asked of the lane). Suite 1,499/0 twice on main. The lane's question: is the 2 % cross-section a LAW or a §31 (3) target for a landside road?

* FABLE'S RULING (§37 (8)): FOR A GROUNDSIDE ROAD THE CROSS-SECTION IS A §31 (3) VISUAL TARGET, NOT A LAW. The owner's frame (12y): landside is "visual only, natural shapes"; a road that follows a hillside carries the hillside's crossfall, and a 2 % section forced on it is the fill the owner saw. The 2 % cross-section stays LAW on airside roads (a road inside or edge-sharing an apron IS the apron — the free-road ruling) and on a groundside road within its airside contact's reach (the ramp's first `pad_frontage_m` from the mouth, where a vehicle transitions); beyond that reach it is a design target priced under the visual family (0.5 m over the road width) and the census REPORTS it. `check_grade`'s road pair selection is re-pointed onto the same `road_pair_reading` with that reach rule (the next roads lane; a `road_cross_section` row on a groundside road beyond the reach is REPORT, not DEFECT). The five new cockpit motion rows are named by the lane before the owner's read; the app build (1.0.327) proceeds — the owner's read is the acceptance.

## 2026-09-13bf — v2roadramp ROUND 3 MERGED (bb6175b8, lane 33633dc1): §37 (8) + 13be's (ii)/(iii). THE 462-ROW ATTRIBUTION FIRST: over the 2,155 pairs §37 (7) calls a cross-section, the pairs whose own §37 (6) TARGETS already broke their 2 % bound — per VERTEX with the raw-DEM floor (round 2) 145 (worst 3.51 vs 0.60 m over Δs 5.8 m on `dsf:pol51`); per vertex with the clamp floor 129 (worst 3.67 vs 0.19 over Δs 1.2 m); per (ROUTE, STATION) with the clamp floor 0 — the target was read per vertex (its own nearest-way floor, its own graph distance), so two kerbs of one station could differ by 3.67 m and the hard ceiling held the tilt against the 2 %; the raw DEM made it worse (not cap-Lipschitz). FIX: target `max(clamp_r(s), envelope_r(s))` per route station, both cap-Lipschitz, so kerbs differ by at most `cap_l·|Δs|` — always inside §37 (7)'s bound; `road_cross_section (2026-08-25g)` in `[design] hard_rulings`; `road_coverage_join` family (42 coverage exits on 26 routes → 22 pins). KCLT (ONE build `v2roadramp3` 91ab5a7c8e15 vs `ctlkclt70646dc8`): v2 verify `road_cross_section` 781 → 462 → 7; v1 census 330 → 642 → 300 (met by the law itself — its selection still runs `grade_graph.shape_constraints`; the re-point is OWED); `dsf:pol51` follow 0.286 → 1.017, NO survivor row on it; the 7 survivors sit on the WIDE pages (`dsf:pol53` way −10858, pairs 36–48 m apart, up to 2.01 m against a 0.8 m bound — a bench not fully cut, owed); `dsf:pol82` 0.68 (0.18 over, unchanged); `road_coverage_join` 0 on the arm vs up to 7.93 m on the control (5.17 / 5.15 at the owner's site) → arm max 0.004 m; cockpit CRITICAL motion 9 (bar 7 — the `strip_arc` rows of 13bd, the unsettled lag's), visual 1 (`adjacent_ground_step` 0.82 m at 35.2267703, −80.9552263 — v2rampwalk's new family on main, not this lane's; owed with the 0.56 m lip of 13ax); all-road |z−DEM| median 0.198, p95 2.206; hard 28 / 238,729 (max 0.0883), SET NOT SETTLED; `bridge_deck:-14469` (new on main) +11.10 m and out of the ramp population by §37 (6) — its own §33 (4) datum is owed. LEMD / CYXY dry as before. Suite 1,503/0 twice on main. THE OWNER'S QUESTION (13bb/13bc) ANSWERED IN LAW: inside an airport the road banking is v2's — hard cross-section, the core's clamp as the ramp's floor, one value at the coverage edge. APP 1.0.327 BUILDS NOW.

## Tool: road_terrain_conformance

| `Ortho4XP/tools/road_terrain_conformance.py` | The census is GREEN and the owner says the ROADS are wrong — "capped at a visibly low grade, cutting through hills" (docs/POSTMORTEM-20260831.md). This is the TERRAIN-CONFORMANCE INSTRUMENT owner ruling RULINGS 2026-08-31a requires, and the reason it must exist is that NO CENSUS CAN SEE THE DEFECT: a road planed flat through a hill breaks no grade law at all — it is the most lawful surface there is — while the owner's road law says a road FOLLOWS TERRAIN up to `SERVICE_ROAD_MAX_GRADE` (8 %) and is pinned ONLY where it meets airside pavement. Per road CHAIN (a connected run of `service_road` / `service_junction` rings, joined by SHARED NODE IDs and walked along the component's longest path, stationed by ring-centroid arclength — the road's own PATH, never a plan chord, which is the frame `free_road_profile` solves in): `dem_relief_m` (how much hill the chain crosses), `emitted_relief_m`, **`follow_ratio`** (emitted/DEM relief — 1.0 rides the hill, 0.0 is a plane through it, and this is the headline), `cut_max_m` / `fill_max_m`, \|emitted−DEM\| median + p95, emitted vs DEM grade (max and median), and `dem_followable_pct` — the share of steps whose DEM grade is ALREADY within the road cap, which is what turns "flat" into "flat where the law allowed it to climb". **It measures no law and counts no defects**: geometry and altitudes come from `check_grade._parse_osm`, the role from `check_grade.law_role`, the road family from `check_grade._ROAD_FAMILY_ROLES` (which IS `grade_law.ROAD_ROLES`), the metre frame from `check_grade._ll_to_m_factory` about the sidecar's anchor, and the DEM through `apron_drape_read`'s own loaders and `_dem_at` (the engine's own `dem.alt`) — every set, parser and sampler IMPORTED, never re-spelled (the census-wrapper precedent). Every report also carries the COMPOSITION-FREE reading over ALL road-family vertices — |emitted−DEM| median + p95, the count of vertices cutting deeper than 5/10/20 m, and the worst — because chains are arm-dependent (emit decimation drops collinear vertices, so a flattened road fuses differently) while that population is not. **TWO POPULATIONS (2026-08-31, linear-transport Batch 1).** A `PATCH.osm` carries auto_patch's road pavement; **`--levelled-roads <tile>/o4_levelled_roads.json`** carries the CORE-owned roads, which emit as mesh `INTERP_ALT` ring altitudes and leave NO patch rows at all — invisible to the patch mode, to `check_grade` and to every census (RULINGS 2026-08-31b "LEVERAGE THE CORE"; spec `docs/specs/linear-transport-redesign-spec.md` §2 item 4). The sidecar is written by `O4_Vector_Map.include_roads`' longitudinal clamp pass: per OSM WAY, the centerline stations it clamped (<=20 m apart, so the instrument outresolves `emit_decimate`'s 60 m chords), each station's lat/lon, the terrain under it and the altitude the road took. The SAME statistics are computed from those two numbers and the SAME `--rank` / `--site` / `--profile` / `--json` readers print them — no second instrument. Its frame is DECLARED and is NOT the patch frame: one WAY per chain (not a shared-node component), the profile UNBINNED at the clamp's own stations, the DEM as the BUILD sampled it (no `--dem-source` applies), and the cap judged against is the SIDECAR's own `grade_cap`, not this file's constant. A levelled-roads arm compares to another levelled-roads arm and NEVER to a patch arm; the report says so whenever both are printed. It also prints the CLAMP read: ways, stations, how many were clamped beyond the 0.01 m materiality floor, and the max lift and max cut. Three modes: `--rank` DISCOVERS a patch's hill sites (chains over `--min-relief`, longest first, with way ids, end lat/lon and the deepest-cut coordinate), and `--site NAME=LAT,LON` reads ONE PLACE across arms, control first, joined by PLACE and never by way id (`arm_site_read`'s frame rule — ids are arm-dependent); `--profile` prints each arm's station/emitted/DEM table. A site with no chain inside `--site-radius` is reported with its nearest distance, never as zero. `--dem-source airport-inset` (default) is THE SURFACE PRODUCTION GRADES ON; a missing surface REFUSES rather than substituting the other, because two arms on two DEM sources are not comparable. Numbers are comparable ARM TO ARM on identical options and nowhere else. **`--by-ref` (lane `v2roadcap2`, 2026-09-13, RULINGS 2026-09-13ab)**: the same population and the same samplers, grouped by SOURCE REF (`dsf:pol51`, `pav17`) — vertices, worst FILL and worst CUT off the DEM each with its own coordinate, |emitted-DEM| median and p95, worst first. The ref is the unit the owner names a site by and the unit a CLASSIFICATION fix moves; the chain is arm-dependent (emit decimation re-fuses it) and the whole-airport reading hides one road behind 800 lawful vertices. FILL is reported apart from CUT because a road held UP in the air (owner item 5, KCLT `dsf:pol51` +13.28 m) is invisible to a cut-only reading. Scout `v2roadcapkclt` wrote a one-off for exactly this; promoted on its second use (RULINGS `7e90032`). Twin: `Ortho4XP/tests/test_road_terrain_conformance.py` (the DEM is INJECTED, so the law is stated on a surface the twin owns — no corpus, no network; the `--by-ref` grouping, the fill/cut split, the worst-vertex coordinate and this index row). |

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N]` on either a `--replay` arm or a `--why-from PKL`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

## Registered frames: HECA

(none registered)

## Registered frames: KCLT

KCLT  capture  base ec8723e9   lane v2eat            2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2eat/cap  — captures of KCLT/HECA/OTHH/SPJC by lane v2eat; base predates the 13ak pad-law break — valid
KCLT  rebake   base 864e7577   lane v2family         2026-09-13T12:12:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/family/frame/KCLT.rebake.json  — v2familyKCLTframe build (rc 0, 389.3 s, body_sha bb022a77f067) on main 864e7577 — POST 13ak pad-law fix; the build was CONTAMINATED (one Airport_mod_cache dump, chip 13ao) so it carries no ledger key
KCLT  graded   base 864e7577   lane v2family         2026-09-13T12:12:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/family/frame/KCLT.graded.json  — the design surface of the same v2familyKCLTframe build
KCLT  capture  base 70646dc8   lane v2roadramp       2026-09-13T12:44:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/cap/KCLT.pkl
KCLT  rebake   base 0c86fe2c   lane v2clusterpad     2026-09-13T17:03:58  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/laneKCLT/v2clusterpadKCLT2.v2/KCLT.rebake.json  — v2clusterpadKCLT2 build (rc 0, 477.2 s, body_sha 9f056cce3dc3, shared repo UNCHANGED) on claude/v2clusterpad over main 0c86fe2c — the FIRST KCLT frame carrying the §30 (4) CLUSTER PAD and its apron reach; no ledger key (the tree moved between key and store time)
KCLT  graded   base 0c86fe2c   lane v2clusterpad     2026-09-13T17:03:58  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/laneKCLT/v2clusterpadKCLT2.v2/KCLT.graded.json  — the design surface of the same v2clusterpadKCLT2 build: building80+building91 are ONE plane (union spread 4.43 -> 1.46 m) and 38 of 90 apron vertices within 60 m sit at the pad's level
KCLT  patch    base ce203b29   lane v2zonebank       2026-09-13T17:33:35  /tmp/harness/KCLT_20260913T172152.osm  — closing build of claude/v2zonebank cde84e27 (rc 0, 492.4 s, body_sha 9113da337600, ledger 6486660716cc, shared repo UNCHANGED) — §37 (3) as amended: bank 134 rings / 1,311 foot nodes, bank_foot at both owner sites (38.3 m and 10.2 m) and at the 13ax lip; census law-true 13,416
KCLT  graded   base ce203b29   lane v2zonebank       2026-09-13T17:33:35  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/zonebank/KCLT.solved.pkl  — v2_solve_replay --solved-out off cap/KCLT.pkl on BASE ce203b29 — the fixed upstream for 'v2_solve_replay --bank-from PKL --bank-walk' (2.5 s per bank-stage arm)
KCLT  graded   base 880a9293   lane v2clusterpad     2026-09-13T17:50:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/r2/v2cpKCLTr2.v2/KCLT.graded.json  — v2cpKCLTr2 (rc 0, 493.0 s, 5fb560ae50d0) — the CLUSTER arm of the matched pair; its DISARM twin (cluster_pad_min_m2=0, cluster_apron_reach_m=0) is v2cpKCLTdisarm at .../disarmOUT/v2cpKCLTdisarm.v2/
KCLT  rebake   base 880a9293   lane v2clusterpad     2026-09-13T17:50:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/r2/v2cpKCLTr2.v2/KCLT.rebake.json  — the rebake plan of the same v2cpKCLTr2 build
KCLT  graded   base 952924e9   lane v2clusterpad     2026-09-13T18:15:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/c3/v2cpKCLTc3.v2/KCLT.graded.json  — round-3 CLUSTER arm (13cc reach: population minus no-step-coupled apron, priced at apron_trend); its matched DISARM twin is .../d3/v2cpKCLTd3.v2 and the PAD-ONLY attribution arm .../padonly/ is BYTE-IDENTICAL to the disarm
KCLT  patch    base 8fce79cb   lane v2hairline       2026-09-13T17:43:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/kclt_arm.osm  — §39 ARM patch (harness tag v2hairline_kclt_patch): shore weld dropped 2 bank nodes, worst 0.0198 mm at 35.2031709,-80.9454997 (the 723,015-sliver site)
KCLT  graded   base e88ed84b   lane v2clusterpad     2026-09-13T18:41:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/p5/v2cpKCLTp5.v2/KCLT.graded.json  — round-4 PAD-ONLY arm (reach 0, merge EFFECTIVE: building91 221.52, union spread 1.07); its matched DISARM twin is .../d4/v2cpKCLTd4.v2 (bde3f0aff32e). Taxi family 2,406 moved worst 2.07 m between the two — the merge's own, the reach is off in both
KCLT  graded   base 8841c106   lane v2clusterpad     2026-09-13T18:58:24  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/p6/v2cpKCLTp6.v2/KCLT.graded.json  — round-5 PAD-ONLY arm under the §30 (4) (5) GATE — BYTE-IDENTICAL to its DISARM twin .../d4/v2cpKCLTd4.v2 (both bde3f0aff32e): building91 yields (65.81 m from the terminal, a part-box artefact), taxi family 0 moved
KCLT  patch    base 00d8b05c   lane v2hairline       2026-09-13T21:16:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/kclt_r2.osm  — §39 round 2 arm patch: hairline_pair adjudicated 0, emitted sub-spacing segments 799 -> 11 (all the deliberate triangle floor)

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

