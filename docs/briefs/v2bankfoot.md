# Brief pack — lane `v2bankfoot`

Base: main `20a53b11` · generated 2026-09-13 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Open bank feet are breaklines: PATCH_RING_MARKER + emitter-closed coverage; annulus loud bar; ribbons never free (RULINGS 13cp)

## The brief

THE DEFECT (RULINGS 13cp, scout v2lemd329 on the owner's 1.0.329 +40-004 tile): since c632622d (§37 (3)) the LEMD patch carries 105 OPEN `bank_foot` ways and 0 closed. `Ortho4XP/src/O4_Vector_Map.py:3007` gives `PATCH_RING_MARKER` only to closed ways; `:3040-3043` inserts every open way as `DUMMY` (attr 0). The foot stops being the INTERP_ALT flood barrier and the Dirichlet datum, drops out of `patches_area`; `O4_Mesh_Utils.py:1109-1155` (`open_feet`, `_close_open_foot` :430-453) then hands `bank_annulus_blend_values` 15 vertices where the run before had 33,377, and R18-1b's harmonic extension (`interpolate_free_interior_altitudes`) interpolates the vacated corridor from remote data: road ribbons authored at 588–590 in `.node` are emitted at 568 (a 20.7 m canyon at 40.465414,-3.5531888; tile-wide 1,400 INTERP_ALT nodes off by >2 m, worst −24.3 m at 40.4727134,-3.5610941; PATCH_RING nodes 0 off). Engine log counters (`~/Library/Logs/XPTerrainBuilder/engine-stderr.log`, +40-004 runs): annulus valued 33,377/43,665 → 2/15; harmonic moved 414–511 → 95,151/2,729 with 371 components "kept own" (no authored vertex). Same mechanism presumed at HECA.

DO (in this order, synthetic-first):
1. At the vector-map site: an OPEN `bank_foot` way (and any open load-bearing run) wears `PATCH_RING_MARKER`, never `DUMMY` — it is a breakline: INTERP_ALT barrier + Dirichlet datum. Check `blast.py` for every reader of the marker that assumes a closed ring (`patches_area`, `patch_coverage_polygon`, the ring writer / `weld_to_shore`, the pre-flight's `on_boundary`) and rule each in the spec MEASURED table BEFORE editing (RULINGS 2026-08-30l).
2. Coverage for `patches_area` / `patch_coverage_polygon` is closed AT THE EMITTER (`src/auto_patch_v2/emit/bank.py` and the coverage the design already holds) — the emitter writes the closed coverage polygon (a `bank_coverage` or the existing coverage ring, closed) beside the open load-bearing feet; delete `_close_open_foot`'s `nearest_points` projection or reduce it to reading that polygon.
3. A LOUD bar in `O4_Mesh_Utils`: when an airport has any bank foot and `bank_annulus_blend_values` values < 10 % of the annulus vertices, the mesh step REFUSES with the counts (no silent `return None`); the harmonic report line names components with no authored vertex.
4. Interim belt: bare INTERP_ALT (attr 8) input nodes are never in the free set of `interpolate_free_interior_altitudes` (its docstring already promises road ribbons byte-unchanged) — twin it.
5. Do NOT touch `weld_hairlines`, `hairline_preflight` or `insert_edge` (lane `v2hairline` owns them; the `insert_edge` split z is routed there).

MEASURE: synthetic twin first (an open foot chain + a road ribbon across it: ribbon z unchanged after the mesh step). Then ONE LEMD tile-mesh run through the harness (`build_airport.py LEMD --tile 40 -4` or `run_tile_mesh_only.py` per INDEX; the guard armed, `[guard] shared repo UNCHANGED`) and the cross-reference the scout used (node z vs mesh z per attr — promote its `xref.py` reading into `tools/` with an INDEX row and a twin if no near-fit exists; check `tools/INDEX.md` for `mesh_node_xref`-like tools first). HECA: the counters dry from the registered HECA frame if a mesh run is not needed; otherwise ONE HECA mesh run is allowed as the second airport because the owner reported it too.
Fresh LEMD capture: `frames.py list LEMD` (base 32c78eaf, lane v2lemd329).

## §37 (3) text (from the §37 body; docq `spec §37` for the whole)

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

## Bars

- LEMD site 40.465414,-3.5531888: mesh z within 0.5 m of the `.node` ribbon z (588–590); today 568.3.
- LEMD tile-wide node→mesh cross-reference: INTERP_ALT nodes off by > 2 m 1,400 → ≤ 10 (name any survivor); PATCH_RING stays 0; DUMMY 110 → named.
- `bank_annulus_blend_values` valued vertices at LEMD back in the 3–4 × 10⁴ range (today 15); harmonic "moved" back to the ~400–500 range (today 2,729), components with no authored vertex 0 (today 371).
- HECA: the same three counters before → after (dry from the registered frame or one mesh run).
- The loud bar fires on the 1.0.329 numbers (a twin with 15/33,377 refuses) and not on the fixed ones.
- Suite twice; `tests/test_mesh_hairline_preflight.py` and `tests/test_post_mesh.py` still green.

## Files

Yours: `Ortho4XP/src/O4_Vector_Map.py`, `Ortho4XP/src/O4_Mesh_Utils.py`, `Ortho4XP/src/auto_patch_v2/emit/bank.py`
Other lanes' (do not touch): `Ortho4XP/src/O4_Vector_Utils.py`, `O4_Mesh_Utils.py hairline_preflight/weld functions (lane v2hairline)`, `Ortho4XP/src/auto_patch_v2/airport/footprint_unit.py`

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

## 2026-09-13cp LEMD "canyon roads" attributed: §37 (3)'s OPEN bank feet enter the vector map as DUMMY edges — the bank annulus collapsed (33,377 → 15 valued vertices), the harmonic extension took the ground (414 → 2,729 moved) — lane `v2bankfoot`

Scout `v2lemd329`, read-only on the owner's 1.0.329 +40-004 tile. At
40.465414, −3.5531888 the `.node` file carries the road ribbon at 588–590 m
(the core's clamped, correct altitude); the built mesh emits it at 568.3 —
a 20.7 m trench, a smooth 568 plane over 600 m. Tile-wide, every input
node cross-referenced to its own mesh vertex: PATCH_RING_MARKER 0 of 29,186
off; runway/taxiway/hangar 0; **INTERP_ALT road ribbons 1,400 of 278,177
off by > 2 m, worst −24.3 m at 40.4727134, −3.5610941**; DUMMY 110; WATER
10,438 (worst −25.1 m — a second population, see below). Both sites lie
INSIDE `patch_coverage_polygon` (24.4 km²), so the domain filter admits
them and no audit fires. The engine log's per-run counters for +40-004
across every historical run: bank annulus valued vertices 12,961 → 32,325
→ 33,377 → 46,338 → 43,665 → **2 → 15**; harmonic "patch/road interiors
moved" 448 → 426 → 414 → 450 → 511 → **95,151 → 2,729** with, for the
first time, components with no authored vertex (371 "kept own"); total
INTERP_ALT triangles 1,670,705 → 371,965. NOT the DEM (13co); NOT the
patch (`road_cross_section` 2 rows worst 0.16 m, `road_coverage_join` 0;
the 19 road refs' deepest cuts are `bridge_deck:` refs §37 (6) excludes).

* THE CAUSE: `c632622d` §37 (3) "the bank is emitted where it is
  load-bearing" — LEMD's patch now carries **105 OPEN `bank_foot` ways and
  0 closed**. `O4_Vector_Map.py:3007` gives `PATCH_RING_MARKER` only to a
  closed way; `:3040-3043` inserts every open way as **`DUMMY` (attr 0)**:
  the foot is no longer a Dirichlet datum, no longer an INTERP_ALT flood
  barrier, no longer in `patches_area`. `O4_Mesh_Utils.py:1109-1155`'s new
  `open_feet` / `_close_open_foot` projection then feeds
  `bank_annulus_blend_values` 15 vertices where it fed 33,377, and the
  R18-1b harmonic extension interpolates the vacated corridor from remote
  data — the 568 plane under a 589 hillside. The same mechanism explains
  the owner's "HECA looks different" and is presumed under HECA items 2–5
  (13co) until measured.
* SECOND SUSPECT, unquantified: `0523aec5`'s metric split test in
  `O4_Vector_Utils.insert_edge` (`:279-315`, ON by default,
  `split_spacing_m = 0.010`) re-creates a crossed old edge THROUGH THE NEW
  WAY'S NODE, so the new way's altitude enters the old chain — against the
  comment at `:314` "rely on the old id2 id3 for the z value". Candidate
  for the 10,438 WATER nodes off by > 2 m. Routed to lane `v2hairline`
  (its code): carry the old edge's interpolated z; measure the WATER
  population before → after.
* RULING: an open bank foot is a BREAKLINE, not a dummy edge. It wears
  the marker its closed predecessor wore (attr `PATCH_RING_MARKER`: the
  INTERP_ALT barrier and the Dirichlet datum), and coverage for
  `patches_area` / `patch_coverage_polygon` is closed AT THE EMITTER from
  the load-bearing runs and the design coverage, never by `nearest_points`
  projection inside the mesh step. `_close_open_foot`'s silent `None` and
  the annulus split get a report line and a LOUD bar: the mesh step
  refuses when `bank_annulus_blend_values` values < 10 % of the annulus
  vertices at an airport with any bank foot. Interim belt: bare INTERP_ALT
  road-ribbon input nodes leave the free set of
  `interpolate_free_interior_altitudes` (R18-1b's own docstring promises
  ribbons byte-unchanged).
* Lane `v2bankfoot` (Opus, brief pack; the bank lane's code) implements
  it; closing test ONE LEMD tile-mesh run (the site profile 588–590, annulus
  back to the 3–4 × 10⁴ range, harmonic moved back to the ~400–500 range,
  INTERP_ALT off-by-> 2 m 1,400 → ~0) plus the HECA counters dry from the
  registered frame. Fresh LEMD capture registered by the scout (base
  32c78eaf).
* Instrumentation carried: §37 (6) governs 6 of 108 service-road vertices
  at LEMD; §37 (9) 10 exits → 0 pins (the `road_join.py:87` station match
  never fires there; KCLT 42 → 22) — owed, not this round.
* Not verified: no 1.0.327 tile/patch survives (the `.dsf.bak` was not
  decoded); the log carries no version marker; the split branch's firing
  count.

## 2026-09-13ba — v2roadramp MERGED (1fffc892, lane 63ef42f9 / merge dc4a8e43 after two rounds): §37 (6) the road ramp (`airport/road_ramp.py` + `constraints/road_ramp.py`; decks out) and §37 (7) ROAD PAIRS ALONG THE ROUTE — `road_ramp.road_route_frame` (every road-family ring vertex → route id, station, signed lateral, off the ways the ramp reads its DEM on; a through-way answers the outer kerbs; 174 KCLT vertices unframed keep the chord law) → `PlanarMap.road_route_frame` → sidecar `road_route_frame` (a LAW INPUT in `check_grade.SIDECAR_LAW_KEYS`); ONE reading `constraints/roads.road_pair_reading` imported by the generator, `verify/within` and `check_grade` (`cap_l·|Δs| + cap_t·|Δt|`, transverse by the angle in route coordinates, `NOT_A_PAIR` on two routes, chord law with no frame; a ring edge always priced; no bound under `cap_t × plan distance`). KCLT (ONE build `v2roadramp2` 5dcfccc142b9 vs a same-tree control at 70646dc8, 1f83c7a053d9): `dsf:pol51` follow 0.294 → 1.007, fill +13.31 → +1.59 m (MET); `dsf:pol82` +6.17 → +0.68 (0.18 over the bar); all-road |z−DEM| median 0.708 → 0.171, p95 3.348 → 1.674; refs over 3 m 8 → 2 (pol51's 5.33 m CUT + the excluded deck); the ten worst pairs: 7 not-a-pair (switchback), 2 route-followable, 1 real cross-section; v2 verify `road_cross_section` 781 → 462; LP rows 95,797 → 84,606, solve 104.6 → 71.5 s, build 311 vs 315 s; LEMD dry (157 vertices framed, the 61 apron lanes 0 targets, 13 decks excluded, governed ≤ 0.02) and CYXY dry (targets ≤ 0.01 off the core clamp) as before. NOT MET: the v1-era census `road_cross_section` 330 → 642 and adjudicated 3,813 → 5,684 — the two instruments DISAGREE IN DIRECTION: both PAIR identically (twinned); what differs is `check_grade`'s pair SELECTION (`shape_constraints(road_path_metric=True)`) and its allowance envelope, and the remaining rows are a road surface that now RIDES ITS TERRAIN, so a section that rolls with the ground breaks the 2 % cross-section; cockpit CRITICAL motion 7 → 12 with NO road row in either arm (the five new rows not yet named — asked of the lane). Suite 1,499/0 twice on main. The lane's question: is the 2 % cross-section a LAW or a §31 (3) target for a landside road?

* FABLE'S RULING (§37 (8)): FOR A GROUNDSIDE ROAD THE CROSS-SECTION IS A §31 (3) VISUAL TARGET, NOT A LAW. The owner's frame (12y): landside is "visual only, natural shapes"; a road that follows a hillside carries the hillside's crossfall, and a 2 % section forced on it is the fill the owner saw. The 2 % cross-section stays LAW on airside roads (a road inside or edge-sharing an apron IS the apron — the free-road ruling) and on a groundside road within its airside contact's reach (the ramp's first `pad_frontage_m` from the mouth, where a vehicle transitions); beyond that reach it is a design target priced under the visual family (0.5 m over the road width) and the census REPORTS it. `check_grade`'s road pair selection is re-pointed onto the same `road_pair_reading` with that reach rule (the next roads lane; a `road_cross_section` row on a groundside road beyond the reach is REPORT, not DEFECT). The five new cockpit motion rows are named by the lane before the owner's read; the app build (1.0.327) proceeds — the owner's read is the acceptance.

## 2026-09-13bu — ATTRIBUTED (scout `v2kclt327`, the shipped +35-081 tile and the KCLT patch, read-only) and RULED (Fable: §39 amended again, §37 (3) amended, §16g (4)). KCLT's tile: 1,232,247 triangles under 0.1 m² (39 %), 99.85 % of them in THREE ~15 × 20 m spots — two inside `bank_foot` chains (`bank:51` 481,602; `bank:50` 723,015) and one off-airport pond (25,836, unattributed). ITEM 2 + the apron pull-down — §39's CLASS, a THIRD TOPOLOGY: patch node −23317 of `bank:51` (35.218153000, −80.930207800) enters the vector map as n11592; the tile's OSM WATER edge passes 2.7913 mm away; `Vector_Map.insert_edge` (`O4_Vector_Utils.py:253-257`) SPLIT the water edge there and minted n849288 (an interpolated z — the split's signature), so the `.poly` carries a constrained WATER segment 2.7913 mm long → 481,602 slivers, shortest edge 2.11 µm; `bank:50`'s node −23307 the same at 0.2401 mm → 723,015. The sites: `insert_node` (`O4_Vector_Utils.py:157`) dedupes on EXACT float equality; `are_encroached` (`:399`) uses a DIMENSIONLESS `eps = 1e-8`, so a crossing 1 µm from a 20 m edge's endpoint is "interior"; `snap_to_grid(9)` (`O4_Vector_Map.py:1193`) is a 1e-9° = 0.11 mm grid — finer than the mismatch (a stale comment at `O4_Mesh_Utils.py:645-647` still claims 1e-7°). The pairs are at 29.08° and 89.20° — §39 (2)/(3)'s "within 5° of parallel" gate MISSES them; the catching predicate is angle-free: two distinct constrained NODES inside the spacing, or a constrained SEGMENT shorter than it (tile-wide 2,245 under 0.5 m, 28 under 10 mm, 6 under 1 mm — the two cascades are #1 and #10). The owner's item-2 coordinates themselves are clean (the cascade is 195 m east; the apron node reads mesh 221.48 vs DEM 222.23). NOT NEW: both bank vertices are present, byte-equal, in v2family's registered frame (base 864e7577) — the geometry predates the app build; only the tile side (no `.poly` registered) could not be A/B'd. ITEM 5 + the new coordinate — NOT §39: the ADJACENT-GROUND ZONE-2 OUTER EDGE in a CUT against raw DEM with NO BANK EMITTED — item 5: a 5.1 m wall triangle (213.02 / 207.90 / 208.02; plan slope 1.70 where the DEM's is 0.06), the low corner a node of `adjacent_ground:taxi:F:zone2#46`, the strip 4.6 m in a cut for ≥ 30 m closing to the DEM in 7.5 m (1:1.6), `osm_site --radius 40` finds no `bank_foot`; the new coordinate: a 2.77 m step at `zone2#50`, no bank. §37 (3)'s materiality (1.65 m) should have emitted a foot at 4.6 and 2.5 m: the zone-2 outer rings are either not in the bank's coverage union or their stations were dropped at chord-splitting. ITEM 4 — the four floating roof planes are ONE resource, `Terminals/Hangar/Charlotte_Airport_001_ALB.obj`: a PURE ROOF (4,700 vertices, y 2.10 … 33.64, nothing at y ≤ 0) spread over the whole 1.7 km hangar district, split into 28 FOOTLESS bodies (16 with a `geom_box` wider than 200 m, the widest 1,747 m), zeros 202.02 … 223.01; `placement_plan.py:786-793`'s §16c (7) short-circuit hands a body in a rigid cluster a carrier from ANYWHERE in the cluster (`carriers_for`'s rest-on ranking and §16a (2)'s ground test never asked): `__b16` rides `007_ALB__b11` at 221.20 over a hangar at 216.03 (+4.76 at the owner's first site; +4.05, +3.99 / −5.86, −6.42 at the others); the census already prints it as the worst §15 carried-over-refused-carrier row (5.17 m) and 212 §16b wide-body rows; `census_outside_box` reads clean because `geom_box` is the hull of the written triangles (a 1.7 km body gets a 1.7 km box); `RIGID_CLUSTER_SPAN_MAX_M` 1,200 caps the cluster of bodies, not one body's components.

* FABLE'S RULINGS. (i) §39 AMENDED AGAIN — ANGLE-FREE: the `hairline_pair` family and the mesh pre-flight price (a) two distinct constrained NODES within `min_distinct_spacing_m` and (b) any constrained SEGMENT shorter than it, with no parallel gate (the 5° gate is deleted; 13bt's vertex-to-edge and degenerate-triple tests stand); the cure at ONE MORE site, the vector map: `insert_edge`'s split test becomes METRIC (a crossing within the spacing of an endpoint returns that endpoint's id, never minting a node) and, after `snap_to_grid`, every constrained node pair within the spacing is WELDED onto the senior node (water / tile border / coastline first — "water is a datum"), the degenerate segment dropped; `O4_Mesh_Utils.py:645-647`'s stale 1e-7° comment corrected. Folded into lane `v2hairline` (told), bars at KCLT: constrained segments under 10 mm 28 → 0, the three cascades' slivers 1,230,453 → CYXY's class, `hairline_pair` > 0 on the control and 0 on the arm; the off-airport pond named or refuted. (ii) §37 (3) AMENDED — every graded ring is in the bank's coverage, the adjacent-ground zone-2 outer rings included; a zone-2 edge standing ≥ `bank_materiality_m` above or below the DEM is LOAD-BEARING and gets its foot; the census family `zone_edge_cliff` prices a zone-band outer edge whose mesh slope exceeds 1:1 where the DEM's is under half of it. Lane `v2zonebank` (pack): item 5's 5.1 m and the new coordinate's 2.77 m → banked at 1:3 (walls 0), the 13ax lips re-read. (iii) §16g (4) — COMPONENTS APART ARE SEPARATE BODIES: the footprint unit applies at the COMPONENT level — a body whose own connected components do not touch each other in plan (beyond the 0.5 m spacing) is split into one body per plan cluster BEFORE the unit derivation, each seated by the unit it touches (the hangar roof piece over hangar A joins hangar A's unit); a footless body never inherits a cluster zero chosen more than `coarsen_reach_m` away (the §16c (7) short-circuit is gone for footless members). Folded into lane `v2clusterpad` (§16g's owner; told): bar `001_ALB` 28 bodies → one per hangar, zero spread 20.99 → ≤ 0.3 m per building, the four sites' roof base within 0.3 m of the wall tops beneath, `§15 carried over a refused carrier` 8 → 0.

## Tool: run_tile_mesh_only

| `Ortho4XP/tools/run_tile_mesh_only.py` | Consumer-side mesh work: steps 1–2 only, no imagery. Arms THE shared-repo write guard (`harness/shared_repo_guard.py` — the same single implementation `harness/build_airport.py` uses): an unauthorised write into the shared data repo refuses at the call, the run audits a full before/after snapshot, joins the bathymetry prefetch before disarming, and a refusal the engine swallowed fails the run. Measured precedent 2026-08-08: two unguarded mesh-only runs silently rewrote five inset/bathymetry manifests in the shared repo. It has NO refresh mechanism of its own — warm a cold tile with `harness/build_airport.py --refresh-data <scope>`. **`--patches-as-is` (2026-09-04, v2 M2 mesh A/B):** step 1 does NOT resolve the X-Plane install paths, so auto_patch generation is skipped and the `Patches/` files ALREADY ON DISK are meshed as they are — the deliberate measurement of a given patch's mesh-apply cost (Triangle input segments / constrained edges, step 1 and step 2 wall), printed as such; a run without the flag still refuses when no install resolves. Measured 2026-09-04 on +60-136, one run per arm: v1 CYXY patch (09-02 sweep arm) 108,708 input segments / 247,315 constrained edges, step 1 39.4 s, step 2 9.3 s; v2 M2 patch 105,420 / 243,088, step 1 34.8 s, step 2 8.8 s (both arms flagged by the guard for the same blocked `N60W136_airport_insets/index.json` warm-pass rewrite — identical frame both sides, not a patch effect). A third argument `first_step` (2026-08-11, round 15) selects the MESH REPLAY: `2` runs step 2 alone on the `.node` / `.poly` / `.weight` / `.alt` already in the build directory, which is the acceptance loop for a change in the mesh CONSUMER — re-running step 1 rewrites the very inputs under test, and in a checkout that resolves no X-Plane root it skips auto_patch entirely and still exits 0 (measured +25+051: 191,764 input vertices and 696,507 triangles against the 224,818 / 3,149,297 of the build being reproduced, and the patch-dependent degeneracy simply absent). Copy a build's four input files beside its `Ortho4XP_+XX+YYY.cfg` into a lane-local build directory and the replay meshes exactly the geometry that build meshed. |

## Tool: build_airport.py

| `Ortho4XP/tools/harness/build_airport.py` | You need to BUILD anything for measurement: one airport patch, a constant-DEM oracle world, or a whole tile. Enforces the build cwd, refuses a cold DEM/inset frame, a drifted config frame, a PRIVATE data corpus and any implicit download into the shared repo; guarantees the axes sidecar; wraps the run in the ledger; audits the shared repo before/after; and records the env, DEM-frame and data-mount snapshots every later claim depends on. It also refuses a DEGRADATION THE ENGINE SWALLOWED (2026-08-07): `auto_patch.elevation._load_airport_dem` runs production's whole DEM prep inside one `except Exception`, so a write the shared-repo guard blocked became a WARN line, `dem_inset_provenance: null` and a build that exited 0 on 18.5 k nodes against production's 34-36 k (measured at HECA, `tmp/sliver_attrib`). Two independent detectors close it — a write the guard blocked during a build that nevertheless returned, and a laylane carrying no DEM provenance at all — and either refuses BEFORE the patch is written, so a DEM-less `.osm` never lands where a census would find it. The guard's one allowance is the lane's cross-process `.lock` file (`is_lock_artifact`): coordination state, never corpus data, and only for the exclusive-create and removal that `O4_File_Lock.hold_file_lock` performs — a `builtins.open` of a `.lock` path, a rename onto one, or any real data write beside it still refuses, and the churn is recorded in `tmp/engine_cache_root`, `O4_LANE_CACHE_ROOT` overrides; one per WORKTREE, reused across runs, still lane-local and still COW-seeded — perf P2 Lane A 2026-08-13: the per-run root threw away everything a build derived, so HECA re-ran `_compute_dsf_object_buildings` (66.6 s) every lane build and OTHH ~455 s, and seeding from the shared corpus could not save it because the pack's own `.obj` files are IN the footprint fingerprint and the Phase-2 y-bake rewrites them AFTER that run's sidecar is written — HECA sidecar 07:03, 376 of 568 `.obj` rewritten 07:14; staleness is safe because every artifact under the root is content-keyed, so a stale clone recomputes rather than answering wrong) (`build_airport.frame.json`. `--dem CONST_M` substitutes a synthetic constant surface (an explicit DEM SOURCE substitution, never a law gate) and takes NEGATIVES — `--dem -500` is the ruled low world; the world is stamped into `<tag>.result.json` / `<tag>.frame.json` under `synthetic_dem`, because a −500 m census row is not comparable with a real-DEM one. The guard and its allowances live in `harness/shared_repo_guard.py` (one implementation, shared with `run_tile_mesh_only.py`). Engine derived-cache writes never touch the corpus at all (2026-08-11): every build re-points the two writable cache roots the engine derives into — the DSFTool dump cache (`O4_DSF_CACHE_DIR`) and the per-pack `Airport_mod_cache` root (`O4_AIRPORT_MOD_CACHE_DIR`, a COPY-ON-WRITE read-through overlay: APFS `clonefile` seeding — warm reads, and a write lands lane-local even when the writer TRUNCATES IN PLACE) — at the LANE-PERSISTENT root `<out>/<tag>.engine_caches/`, the same env-overridden mechanism the pytest suite runs under; the measured hole it closes is the DSFTool SUBPROCESS dump no Python-level guard can intercept (KCLT 2026-08-11, `Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text`, run flagged CONTAMINATED). The MASKS root joined them 2026-08-12b (owner ruling: lane mask writes land lane-local): `O4_MASKS_DIR` (`O4_File_Names.masks_root`, read at CALL time) points the engine at `<out>/<tag>.engine_caches/Masks`, a copy-on-write overlay seeded from the shared `Masks/` subtree of the TILE(S) IN SCOPE — so the masks step's reads stay warm and its legacy cleanup deletes lane-local clones instead of everyone's rasters (the measured refusal: a HECA `--tile 30 31` arm rc=1 on 16 blocked `os.remove`s of `Masks/+30+030/+30+031/*.png`, every one swallowed by a bare `except: pass` now narrowed to `FileNotFoundError`). A scope the run is AUTHORISED to refresh (`--refresh-data airport_mod_cache` / `dsf_cache` / `masks`) is deliberately NOT redirected — the refresh must land in the shared repo — and the redirect record rides in `<tag>.result.json` / `<tag>.frame.json` under `engine_cache_redirects`. Corollary: a cold derived cache no longer forces `--allow-degraded-dem` (the rewrite lands lane-local instead of being guard-blocked); warming the SHARED cache stays an explicit `--refresh-data` act. `--warm-insets ICAO[,ICAO...]` (2026-08-11, round-13 spec amendment) fetches/refreshes the airport ELEVATION INSETS of exactly the airports named, before the build's DEM prep and inside the lock, snapshot, guard and ledger record (which names them) — valid ONLY with `--refresh-data dem`, re-querying rather than consulting the cache (negatives included — a transient TNM 504 cached a durable `no-coverage` for KMCI on 2026-08-11), and it is the only lawful instrument for a one-airport inset need: an airport build never reaches `ensure_airport_insets` (its DEM prep is pure disk state), a `--tile` build would refresh every void inset on the tile against a one-airport authorisation, and the standalone fetch tool writes the corpus outside the lock and the ledger. It also bypasses the `is_cached` size>0 gate for the named airports, under which a non-empty but INVALID raster makes a tile pass skip the fetch entirely. **The BASE-ARM ARTIFACT LEDGER (2026-08-12, BS2) means a reference arm is built once, ever:** every successful patch build stores its patch + sidecar + frame + env + result in `~/.ortho4xp/artifact_ledger` (outside the shared repo, gitignored, size-capped LRU, `O4_ARTIFACT_LEDGER_DIR` / `_MAX_MB`), content-addressed by (code-tree hash, ICAO, the `O4_*` env the run ledger keys on, CORPUS STAMP, build variant); `--base-arm` (or `--from-ledger`) serves that artifact instead of rebuilding — measured at CYXY: **0.3 s against a 63.3 s build, patch, sidecar and frame byte-identical**, behind a provenance line naming the original build, its timestamp and its duration, with a `<tag>.served.json` record beside it. A miss NAMES the component that moved, and a corpus-stamp mismatch is ALWAYS a miss (a changed corpus is a different measurement — the KCLT road-feed precedent). Refused: `--no-ledger` (a timing run has no time to replay), `--tile`, `--refresh-data`, and `--no-artifact-ledger` (a flag that silently does nothing). A refresh-authorised or CONTAMINATED run is never stored, and the key's tree hash + dirty flag are RE-CHECKED at store time (the key is cut at START; a worker-pool child that outlives its parent can finish after source edits land — the 2026-08-28 LEMD poisoned-key precedent): a mismatch refuses the store loudly, stamps `contaminated_key` into `<tag>.frame.json`, and never re-keys. **LANE INPUTS ARE PROVISIONED, NEVER HAND-SEEDED (owner ruling 2026-08-12b):** a `--tile` build whose build dir lacks `Ortho4XP_+XX+YYY.cfg` gets it as a BYTE COPY from the ritual's own canonical source (`$O4_MAIN_REPO/Ortho4XP/Tiles/zOrtho4XP_+XX+YYY/`, the tree `lane_worktree.sh` clones `Ortho4XP.cfg` and `Patches/` from), recorded with its sha256 in `<tag>.frame.json` under `tile_cfg_provenance`; an EXISTING lane cfg is never overwritten (recorded as `present`, hashed) and a MISSING canonical source REFUSES — synthesized defaults would build a tile at a provider and ZL nobody chose and exit 0. Closes the 'EMPTY default_website' wall two lanes each improvised past with a different cfg source on 2026-08-12. **`--solve-capture DIR` (2026-08-13, P2 instrument item 1)** additionally writes a SOLVE-STAGE CAPTURE into `DIR/<ICAO>/` — the phases 1-4 product at the solve boundary, replayable by `tools/solve_cut.py --replay` without rebuilding phases 1-4. It is armed inside `build_patch`, AFTER `arm_shared_repo_protection` (the env key is the engine module's own constant, and importing the engine before the redirect composition is the ordering that composition exists to prevent), and it is refused with `--tile` rather than silently doing nothing (`build_tile` runs the engine through another entry; arm `O4_SOLVE_CAPTURE` in that build's environment knowingly instead, and every airport the tile builds writes its own capture). Capture is a pure reader at the boundary: measured at CYXY the build's body sha was `61efa43c3aeb`, the frozen 1.0.245 baseline, capture armed.  **`--geometry-only` (2026-08-14, owner request):** plan geometry only (`compute_elevations=False`, the pipeline's own documented mode) for visual inspection — refused with `--tile` and `--solve-capture` (silent no-ops), stamped into `result.json` and the artifact-ledger variant key so a solved arm can never be served from a geometry-only one, and NEVER censused (there is no solved surface to count). **THE WINDOW IS NOT THE AUTHOR (2026-09-01, beta hardening H6 item 6 — flagged independently by three lanes):** the before/after audit diffs the WHOLE shared repo across the build's wall-clock window and used to attribute EVERY delta in it to that build — but builds run concurrently by ruling, an authorised `--refresh-data` in lane B lands inside lane A's window, and the library-index allowance was this same cross-attribution solved once for one file (the nidrepair 2026-08-07 frames each reported `write_guard_blocked: []` and each named the same modified sidecar neither of them wrote). Every delta is still NAMED — nothing is dropped — but one is labelled **EXTERNAL-CANDIDATE** instead of CONTAMINATED when BOTH hold: this build's own `write_guard_blocked` is EMPTY (a guard-blocked write is a whole-run veto — that build's code did reach for the corpus), AND the path is provably OUTSIDE the build's INPUT SET (`BuildInputScope`: the tiles it reads plus their eight neighbours, in BOTH corpus spellings — `+30+031` and `N30E031` — plus the per-airport road feed by ICAO). A path naming neither a tile nor an airport is UNSCOPABLE and therefore IN scope: "not provably external" is the whole predicate, and the instrument downgrades only what it can positively exclude. CONTAMINATED is unchanged for in-scope or guard-blocked deltas, and an entry passing no scope (or an empty one) gets the pre-2026-09-01 behaviour to the letter. The verdict is re-derivable: `build_input_scope`, `unauthorised_writes` (every delta) and `external_candidate_writes` all ride in `<tag>.frame.json`. The ARTIFACT-LEDGER STORE gate is deliberately the stricter of the two and still refuses on ANY delta — contamination is about whether this build's numbers are trustworthy, the store gate about whether its corpus stamp still describes the corpus a later hit would read. `contaminating_writes` is the ONE reading of the label. Twins: `tests/test_harness.py` (external-vs-in-scope, the guard-blocked veto, the unchanged default, the unscopable path, both tile spellings + neighbours, the ICAO rule, the refusal reading the one helper, the frame stamps). **There is no other sanctioned way to build.** **THE V2 ENGINE (2026-09-04, lane v2resid; THE ONLY ENGINE since the owner retired v1, RULINGS 2026-09-13au — there is no `--engine` flag and no `auto_patch_engine` cfg key):** the SAME entry builds the auto-patch-v2 patch (`src/auto_patch_v2/pipeline/build.py`, RULINGS 2026-09-03d) under the same cwd/DEM-frame/corpus refusals, the same shared-repo guard and swallowed-refusal detectors, the same sidecar guarantee, run ledger and artifact ledger; `frame.json` records `engine` and the v2 law-table digest (`law_tables`: sha256 over `src/auto_patch_v2/law/*.toml`) plus a `v2` block (solve status, LP size, stage walls, v2-verify counts, tile pieces), and the artifact-ledger variant key carries both (v1 keys unchanged — a v2 patch is never served for a v1 arm). The v2 products land in `<tag>.v2/` (`<ICAO>.report.json` with the IIS on infeasibility, `<ICAO>.graded.json`, tile pieces); the patch and sidecar are MOVED to `<tag>.osm` / `<tag>.osm.axes.json` so `census.py` reads it like any patch. Refused by name (not wired for v2): `--dem`, `--geometry-only`, `--solve-capture` (not wired; a silently-inert flag is the precedent). A non-optimal solve refuses to report (no patch is written). **`--tile LAT LON` (2026-09-04, lane v2app)** builds the WHOLE TILE with the app's own dispatch: `auto_patch.driver` runs `auto_patch.engine_v2.build_write_verify_one_v2` per airport — `auto_patch_v2.pipeline.build` on the tile's OWN production DEM (`tile.dem` seeded into the v2 loader, never re-composed), the current tile's patch + sidecar placed at `Patches/<block>/<tile>/<ICAO>_auto.patch.osm`, the v2 verify census in `auto_patch_verify_debug.log`, one `[provenance] ICAO patch: engine=v2 sha=… law=<digest> ruleset=… solve=… dem=…` line per airport, and a non-optimal solve / v2 refusal a NAMED per-airport build failure (`AutoPatchFailed` on the JSONL protocol, IIS in the verify log). Every patch carries `o4_ap_engine` in its freshness block (schema `2`), so a patch the retired engine left behind never reads as current. Measured +25+051 2026-09-04: OTBD 13.7 s / OTBH 7.0 s / OTHH 37.8 s, all optimal; oracle census on the placed OTHH patch 0/0. The mod-cache redirect is also handed to v2's own loader (`inputs.mod_cache_root`), which `planar.__main__.default_inputs` cannot do for itself — it reads no environment by design, so before 2026-09-13 the pack-dump FRESHNESS guard (`airport/load.py:289`) judged the SHARED root and refused every KCLT / HECA v2 build and `explain` (RULINGS 2026-09-13q, "chip"); the build now reads and derives its DSF text dumps in the same lane-local overlay every other derived cache lands in. The guard's one allowance is the lane's cross-process `.lock` file (`is_lock_artifact`): coordination state, never corpus data, and only for the exclusive-create and removal that `O4_File_Lock.hold_file_lock` performs — a `builtins.open` of a `.lock` path, a rename onto one, or any real data write beside it still refuses, and the churn is recorded in `tmp/engine_cache_root`, `O4_LANE_CACHE_ROOT` overrides; one per WORKTREE, reused across runs, still lane-local and still COW-seeded — perf P2 Lane A 2026-08-13: the per-run root threw away everything a build derived, so HECA re-ran `_compute_dsf_object_buildings` (66.6 s) every lane build and OTHH ~455 s, and seeding from the shared corpus could not save it because the pack's own `.obj` files are IN the footprint fingerprint and the Phase-2 y-bake rewrites them AFTER that run's sidecar is written — HECA sidecar 07:03, 376 of 568 `.obj` rewritten 07:14; staleness is safe because every artifact under the root is content-keyed, so a stale clone recomputes rather than answering wrong) (`build_airport.frame.json`. `--dem CONST_M` substitutes a synthetic constant surface (an explicit DEM SOURCE substitution, never a law gate) and takes NEGATIVES — `--dem -500` is the ruled low world; the world is stamped into `<tag>.result.json` / `<tag>.frame.json` under `synthetic_dem`, because a −500 m census row is not comparable with a real-DEM one. The guard and its allowances live in `harness/shared_repo_guard.py` (one implementation, shared with `run_tile_mesh_only.py`). Engine derived-cache writes never touch the corpus at all (2026-08-11): every build re-points the two writable cache roots the engine derives into — the DSFTool dump cache (`O4_DSF_CACHE_DIR`) and the per-pack `Airport_mod_cache` root (`O4_AIRPORT_MOD_CACHE_DIR`, a COPY-ON-WRITE read-through overlay: APFS `clonefile` seeding — warm reads, and a write lands lane-local even when the writer TRUNCATES IN PLACE) — at the LANE-PERSISTENT root `<out>/<tag>.engine_caches/`, the same env-overridden mechanism the pytest suite runs under; the measured hole it closes is the DSFTool SUBPROCESS dump no Python-level guard can intercept (KCLT 2026-08-11, `Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text`, run flagged CONTAMINATED). The MASKS root joined them 2026-08-12b (owner ruling: lane mask writes land lane-local): `O4_MASKS_DIR` (`O4_File_Names.masks_root`, read at CALL time) points the engine at `<out>/<tag>.engine_caches/Masks`, a copy-on-write overlay seeded from the shared `Masks/` subtree of the TILE(S) IN SCOPE — so the masks step's reads stay warm and its legacy cleanup deletes lane-local clones instead of everyone's rasters (the measured refusal: a HECA `--tile 30 31` arm rc=1 on 16 blocked `os.remove`s of `Masks/+30+030/+30+031/*.png`, every one swallowed by a bare `except: pass` now narrowed to `FileNotFoundError`). A scope the run is AUTHORISED to refresh (`--refresh-data airport_mod_cache` / `dsf_cache` / `masks`) is deliberately NOT redirected — the refresh must land in the shared repo — and the redirect record rides in `<tag>.result.json` / `<tag>.frame.json` under `engine_cache_redirects`. Corollary: a cold derived cache no longer forces `--allow-degraded-dem` (the rewrite lands lane-local instead of being guard-blocked); warming the SHARED cache stays an explicit `--refresh-data` act. `--warm-insets ICAO[,ICAO...]` (2026-08-11, round-13 spec amendment) fetches/refreshes the airport ELEVATION INSETS of exactly the airports named, before the build's DEM prep and inside the lock, snapshot, guard and ledger record (which names them) — valid ONLY with `--refresh-data dem`, re-querying rather than consulting the cache (negatives included — a transient TNM 504 cached a durable `no-coverage` for KMCI on 2026-08-11), and it is the only lawful instrument for a one-airport inset need: an airport build never reaches `ensure_airport_insets` (its DEM prep is pure disk state), a `--tile` build would refresh every void inset on the tile against a one-airport authorisation, and the standalone fetch tool writes the corpus outside the lock and the ledger. It also bypasses the `is_cached` size>0 gate for the named airports, under which a non-empty but INVALID raster makes a tile pass skip the fetch entirely. **The BASE-ARM ARTIFACT LEDGER (2026-08-12, BS2) means a reference arm is built once, ever:** every successful patch build stores its patch + sidecar + frame + env + result in `~/.ortho4xp/artifact_ledger` (outside the shared repo, gitignored, size-capped LRU, `O4_ARTIFACT_LEDGER_DIR` / `_MAX_MB`), content-addressed by (code-tree hash, ICAO, the `O4_*` env the run ledger keys on, CORPUS STAMP, build variant); `--base-arm` (or `--from-ledger`) serves that artifact instead of rebuilding — measured at CYXY: **0.3 s against a 63.3 s build, patch, sidecar and frame byte-identical**, behind a provenance line naming the original build, its timestamp and its duration, with a `<tag>.served.json` record beside it. A miss NAMES the component that moved, and a corpus-stamp mismatch is ALWAYS a miss (a changed corpus is a different measurement — the KCLT road-feed precedent). Refused: `--no-ledger` (a timing run has no time to replay), `--tile`, `--refresh-data`, and `--no-artifact-ledger` (a flag that silently does nothing). A refresh-authorised or CONTAMINATED run is never stored, and the key's tree hash + dirty flag are RE-CHECKED at store time (the key is cut at START; a worker-pool child that outlives its parent can finish after source edits land — the 2026-08-28 LEMD poisoned-key precedent): a mismatch refuses the store loudly, stamps `contaminated_key` into `<tag>.frame.json`, and never re-keys. **LANE INPUTS ARE PROVISIONED, NEVER HAND-SEEDED (owner ruling 2026-08-12b):** a `--tile` build whose build dir lacks `Ortho4XP_+XX+YYY.cfg` gets it as a BYTE COPY from the ritual's own canonical source (`$O4_MAIN_REPO/Ortho4XP/Tiles/zOrtho4XP_+XX+YYY/`, the tree `lane_worktree.sh` clones `Ortho4XP.cfg` and `Patches/` from), recorded with its sha256 in `<tag>.frame.json` under `tile_cfg_provenance`; an EXISTING lane cfg is never overwritten (recorded as `present`, hashed) and a MISSING canonical source REFUSES — synthesized defaults would build a tile at a provider and ZL nobody chose and exit 0. Closes the 'EMPTY default_website' wall two lanes each improvised past with a different cfg source on 2026-08-12. **`--solve-capture DIR` (2026-08-13, P2 instrument item 1)** additionally writes a SOLVE-STAGE CAPTURE into `DIR/<ICAO>/` — the phases 1-4 product at the solve boundary, replayable by `tools/solve_cut.py --replay` without rebuilding phases 1-4. It is armed inside `build_patch`, AFTER `arm_shared_repo_protection` (the env key is the engine module's own constant, and importing the engine before the redirect composition is the ordering that composition exists to prevent), and it is refused with `--tile` rather than silently doing nothing (`build_tile` runs the engine through another entry; arm `O4_SOLVE_CAPTURE` in that build's environment knowingly instead, and every airport the tile builds writes its own capture). Capture is a pure reader at the boundary: measured at CYXY the build's body sha was `61efa43c3aeb`, the frozen 1.0.245 baseline, capture armed.  **`--geometry-only` (2026-08-14, owner request):** plan geometry only (`compute_elevations=False`, the pipeline's own documented mode) for visual inspection — refused with `--tile` and `--solve-capture` (silent no-ops), stamped into `result.json` and the artifact-ledger variant key so a solved arm can never be served from a geometry-only one, and NEVER censused (there is no solved surface to count). **THE WINDOW IS NOT THE AUTHOR (2026-09-01, beta hardening H6 item 6 — flagged independently by three lanes):** the before/after audit diffs the WHOLE shared repo across the build's wall-clock window and used to attribute EVERY delta in it to that build — but builds run concurrently by ruling, an authorised `--refresh-data` in lane B lands inside lane A's window, and the library-index allowance was this same cross-attribution solved once for one file (the nidrepair 2026-08-07 frames each reported `write_guard_blocked: []` and each named the same modified sidecar neither of them wrote). Every delta is still NAMED — nothing is dropped — but one is labelled **EXTERNAL-CANDIDATE** instead of CONTAMINATED when BOTH hold: this build's own `write_guard_blocked` is EMPTY (a guard-blocked write is a whole-run veto — that build's code did reach for the corpus), AND the path is provably OUTSIDE the build's INPUT SET (`BuildInputScope`: the tiles it reads plus their eight neighbours, in BOTH corpus spellings — `+30+031` and `N30E031` — plus the per-airport road feed by ICAO). A path naming neither a tile nor an airport is UNSCOPABLE and therefore IN scope: "not provably external" is the whole predicate, and the instrument downgrades only what it can positively exclude. CONTAMINATED is unchanged for in-scope or guard-blocked deltas, and an entry passing no scope (or an empty one) gets the pre-2026-09-01 behaviour to the letter. The verdict is re-derivable: `build_input_scope`, `unauthorised_writes` (every delta) and `external_candidate_writes` all ride in `<tag>.frame.json`. The ARTIFACT-LEDGER STORE gate is deliberately the stricter of the two and still refuses on ANY delta — contamination is about whether this build's numbers are trustworthy, the store gate about whether its corpus stamp still describes the corpus a later hit would read. `contaminating_writes` is the ONE reading of the label. Twins: `tests/test_harness.py` (external-vs-in-scope, the guard-blocked veto, the unchanged default, the unscopable path, both tile spellings + neighbours, the ICAO rule, the refusal reading the one helper, the frame stamps). **There is no other sanctioned way to build.** **THE V2 ENGINE (2026-09-04, lane v2resid; THE ONLY ENGINE since the owner retired v1, RULINGS 2026-09-13au — there is no `--engine` flag and no `auto_patch_engine` cfg key):** the SAME entry builds the auto-patch-v2 patch (`src/auto_patch_v2/pipeline/build.py`, RULINGS 2026-09-03d) under the same cwd/DEM-frame/corpus refusals, the same shared-repo guard and swallowed-refusal detectors, the same sidecar guarantee, run ledger and artifact ledger; `frame.json` records `engine` and the v2 law-table digest (`law_tables`: sha256 over `src/auto_patch_v2/law/*.toml`) plus a `v2` block (solve status, LP size, stage walls, v2-verify counts, tile pieces), and the artifact-ledger variant key carries both (v1 keys unchanged — a v2 patch is never served for a v1 arm). The v2 products land in `<tag>.v2/` (`<ICAO>.report.json` with the IIS on infeasibility, `<ICAO>.graded.json`, tile pieces); the patch and sidecar are MOVED to `<tag>.osm` / `<tag>.osm.axes.json` so `census.py` reads it like any patch. Refused by name (not wired for v2): `--dem`, `--geometry-only`, `--solve-capture` (not wired; a silently-inert flag is the precedent). A non-optimal solve refuses to report (no patch is written). **`--tile LAT LON` (2026-09-04, lane v2app)** builds the WHOLE TILE with the app's own dispatch: `auto_patch.driver` runs `auto_patch.engine_v2.build_write_verify_one_v2` per airport — `auto_patch_v2.pipeline.build` on the tile's OWN production DEM (`tile.dem` seeded into the v2 loader, never re-composed), the current tile's patch + sidecar placed at `Patches/<block>/<tile>/<ICAO>_auto.patch.osm`, the v2 verify census in `auto_patch_verify_debug.log`, one `[provenance] ICAO patch: engine=v2 sha=… law=<digest> ruleset=… solve=… dem=…` line per airport, and a non-optimal solve / v2 refusal a NAMED per-airport build failure (`AutoPatchFailed` on the JSONL protocol, IIS in the verify log). Every patch carries `o4_ap_engine` in its freshness block (schema `2`), so a patch the retired engine left behind never reads as current. Measured +25+051 2026-09-04: OTBD 13.7 s / OTBH 7.0 s / OTHH 37.8 s, all optimal; oracle census on the placed OTHH patch 0/0. |

| `Ortho4XP/tools/harness/build_airport.py` | **Default.** See above. |

## Tool: road_terrain_conformance

| `Ortho4XP/tools/road_terrain_conformance.py` | The census is GREEN and the owner says the ROADS are wrong — "capped at a visibly low grade, cutting through hills" (docs/POSTMORTEM-20260831.md). This is the TERRAIN-CONFORMANCE INSTRUMENT owner ruling RULINGS 2026-08-31a requires, and the reason it must exist is that NO CENSUS CAN SEE THE DEFECT: a road planed flat through a hill breaks no grade law at all — it is the most lawful surface there is — while the owner's road law says a road FOLLOWS TERRAIN up to `SERVICE_ROAD_MAX_GRADE` (8 %) and is pinned ONLY where it meets airside pavement. Per road CHAIN (a connected run of `service_road` / `service_junction` rings, joined by SHARED NODE IDs and walked along the component's longest path, stationed by ring-centroid arclength — the road's own PATH, never a plan chord, which is the frame `free_road_profile` solves in): `dem_relief_m` (how much hill the chain crosses), `emitted_relief_m`, **`follow_ratio`** (emitted/DEM relief — 1.0 rides the hill, 0.0 is a plane through it, and this is the headline), `cut_max_m` / `fill_max_m`, \|emitted−DEM\| median + p95, emitted vs DEM grade (max and median), and `dem_followable_pct` — the share of steps whose DEM grade is ALREADY within the road cap, which is what turns "flat" into "flat where the law allowed it to climb". **It measures no law and counts no defects**: geometry and altitudes come from `check_grade._parse_osm`, the role from `check_grade.law_role`, the road family from `check_grade._ROAD_FAMILY_ROLES` (which IS `grade_law.ROAD_ROLES`), the metre frame from `check_grade._ll_to_m_factory` about the sidecar's anchor, and the DEM through `apron_drape_read`'s own loaders and `_dem_at` (the engine's own `dem.alt`) — every set, parser and sampler IMPORTED, never re-spelled (the census-wrapper precedent). Every report also carries the COMPOSITION-FREE reading over ALL road-family vertices — |emitted−DEM| median + p95, the count of vertices cutting deeper than 5/10/20 m, and the worst — because chains are arm-dependent (emit decimation drops collinear vertices, so a flattened road fuses differently) while that population is not. **TWO POPULATIONS (2026-08-31, linear-transport Batch 1).** A `PATCH.osm` carries auto_patch's road pavement; **`--levelled-roads <tile>/o4_levelled_roads.json`** carries the CORE-owned roads, which emit as mesh `INTERP_ALT` ring altitudes and leave NO patch rows at all — invisible to the patch mode, to `check_grade` and to every census (RULINGS 2026-08-31b "LEVERAGE THE CORE"; spec `docs/specs/linear-transport-redesign-spec.md` §2 item 4). The sidecar is written by `O4_Vector_Map.include_roads`' longitudinal clamp pass: per OSM WAY, the centerline stations it clamped (<=20 m apart, so the instrument outresolves `emit_decimate`'s 60 m chords), each station's lat/lon, the terrain under it and the altitude the road took. The SAME statistics are computed from those two numbers and the SAME `--rank` / `--site` / `--profile` / `--json` readers print them — no second instrument. Its frame is DECLARED and is NOT the patch frame: one WAY per chain (not a shared-node component), the profile UNBINNED at the clamp's own stations, the DEM as the BUILD sampled it (no `--dem-source` applies), and the cap judged against is the SIDECAR's own `grade_cap`, not this file's constant. A levelled-roads arm compares to another levelled-roads arm and NEVER to a patch arm; the report says so whenever both are printed. It also prints the CLAMP read: ways, stations, how many were clamped beyond the 0.01 m materiality floor, and the max lift and max cut. Three modes: `--rank` DISCOVERS a patch's hill sites (chains over `--min-relief`, longest first, with way ids, end lat/lon and the deepest-cut coordinate), and `--site NAME=LAT,LON` reads ONE PLACE across arms, control first, joined by PLACE and never by way id (`arm_site_read`'s frame rule — ids are arm-dependent); `--profile` prints each arm's station/emitted/DEM table. A site with no chain inside `--site-radius` is reported with its nearest distance, never as zero. `--dem-source airport-inset` (default) is THE SURFACE PRODUCTION GRADES ON; a missing surface REFUSES rather than substituting the other, because two arms on two DEM sources are not comparable. Numbers are comparable ARM TO ARM on identical options and nowhere else. **`--by-ref` (lane `v2roadcap2`, 2026-09-13, RULINGS 2026-09-13ab)**: the same population and the same samplers, grouped by SOURCE REF (`dsf:pol51`, `pav17`) — vertices, worst FILL and worst CUT off the DEM each with its own coordinate, |emitted-DEM| median and p95, worst first. The ref is the unit the owner names a site by and the unit a CLASSIFICATION fix moves; the chain is arm-dependent (emit decimation re-fuses it) and the whole-airport reading hides one road behind 800 lawful vertices. FILL is reported apart from CUT because a road held UP in the air (owner item 5, KCLT `dsf:pol51` +13.28 m) is invisible to a cut-only reading. Scout `v2roadcapkclt` wrote a one-off for exactly this; promoted on its second use (RULINGS `7e90032`). Twin: `Ortho4XP/tests/test_road_terrain_conformance.py` (the DEM is INJECTED, so the law is stated on a surface the twin owns — no corpus, no network; the `--by-ref` grouping, the fill/cut split, the worst-vertex coordinate and this index row). |

## Registered frames: LEMD

LEMD  capture  base ec8723e9   lane v2roadcap        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/rw/cap/LEMD.pkl  — the v2roadcap-era LEMD capture used by scout v2unsettled2
LEMD  capture  base 864e7577   lane v2settle         2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle  — fresh main capture + per-law arms + logs (13ak)
LEMD  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/fin_LEMD/structures.json  — LEMD planar --stage structures on claude/v2gradecache vs the 0c86fe2c base arm in scratchpad/base_LEMD: every basin rim_ll/region_ll/floor_z/ramp_rings_ll/area/notes and every basin refusal BYTE-IDENTICAL; only covered_fraction moves 0.22750697->0.22750614 at the 1 cm plane quantum
LEMD  mesh     base 8fce79cb   lane v2hairline       2026-09-13T17:43:19  /tmp/harness/tile_v2hairline_arm3/Data+40-004.mesh  — §39 ARM: shore weld ON, metric split ON, vector weld OFF — sub-0.1 m2 in bbox 1,641, aspect p50 1.61, 2,734,780 tris
LEMD  patch    base df67b414   lane v2hairline       2026-09-13T17:43:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/control.osm  — §39 CONTROL patch (harness tag v2hairline_control) with shore_edges injected from the same TileWater witness — hairline_pair 29 adjudicated
LEMD  capture  base 32c78eaf   lane v2lemd329        2026-09-13T20:49:45  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/cap/LEMD.pkl  — fresh LEMD v2_solve_replay capture on main 32c78eaf (22158 vertices, 1119 faces, 353 s) — for the sunken-road round

## Registered frames: HECA

(none registered)

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

