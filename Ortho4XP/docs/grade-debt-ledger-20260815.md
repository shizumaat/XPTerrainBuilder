# Grade Debt Ledger

## 2026-08-21 battery refresh (composed main after wave-3 steps 1–6)

Merged since the 2026-08-16 battery: **F3c graded handoff** `47e83ed`
(crater-floor → dam-ceiling monotone descent, owner ruling 2026-08-18),
the **crown-declaration fix** `e55f98d` (an undeclared crown endpoint is
UNKNOWN, not on the ridge — the phantom offset was the READER's), the
**road chord limiter** `1590f75` (`service_road` + `service_junction`
join the finalize Lipschitz clamp; stricter cap at shared nodes; airside
pinned as data), and the **EAT rect-level value refusal** `4540c29` (a
contradiction priced on ANY pin of a flat rect condemns the value on the
whole rect). Six-airport battery on composed main, **all rc=0**.

| airport | adjudicated | airside-for-acceptance |
|---|---|---|
| CYXY | 206 | 75 |
| SPLP | 36 | 34 |
| SPJC | 397 | 189 |
| KAFW | 259 | 64 |
| HECA | 4,812 | 1,487 |
| KDFW | 411 | 150 |
| **total** | **6,121** | **1,999** |

Against 2026-08-16 (9,350 / 2,211): **−3,229 adjudicated, −212 airside.**

**ACCEPTANCE — PASS on all six** under the 2026-08-18 per-airport ruling
(no airport's airside-for-acceptance may exceed its 2026-08-16 value):
CYXY 75 ≤ 75, SPLP 34 ≤ 35, SPJC 189 ≤ 199, KAFW 64 ≤ 89,
HECA 1,487 ≤ 1,522, KDFW 150 ≤ 291. No STOP.

**Frame.** Builds through `tools/harness/build_airport.py` from
`Ortho4XP/`, censuses through `tools/harness/census.py`, row-level A/Bs
through `tools/census_rows_diff.py`, value reads through
`tools/airside_value_delta.py`. The A side of every A/B is the
2026-08-16 battery patch itself, served from the artifact ledger
(`CYXY_20260816T083025`, `SPLP_20260816T083118`, `SPJC_20260816T083126`,
`KAFW_20260816T083441`, `HECA_20260816T083641`, `KDFW_20260816T085141`,
all tree `f575f9bd`) and **re-censused under this tree's law**, so the
join never crosses two law frames. SPLP's patch carries provenance
`4540c299` and the other five `1872e16c`: main gained one commit
mid-battery whose diff is **docs-only** (`docs/RULINGS.md`, +19 lines),
so the battery is ONE code frame. Every build reported `shared repo
UNCHANGED` (full-surface before/after snapshot); the only recorded churn
is the `.lock` coordination family. No timing claim is made or implied
anywhere below — these are correctness builds.

### The census law moved too, and it is separated out here

The same **unchanged** 2026-08-16 patches, censused at `575aea1` and
again on this tree:

| airport | 2026-08-16 ledger | re-censused now | census-law delta |
|---|---|---|---|
| CYXY | 336 / 75 | 336 / 75 | 0 / 0 |
| SPLP | 43 / 35 | 42 / 34 | −1 / −1 |
| SPJC | 482 / 199 | 482 / 199 | 0 / 0 |
| KAFW | 365 / 89 | 363 / 89 | −2 / 0 |
| HECA | 7,548 / 1,522 | 7,545 / 1,519 | −3 / −3 |
| KDFW | 576 / 291 | 576 / 291 | 0 / 0 |

Only two halves of code touch the census in that span: F3c's
`check_grade` half, which the KAFW/KDFW triage dossier proved a **census
no-op** at both fixtures, and the crown-declaration fix. So the −6
adjudicated / −4 airside above is the crown fix's validator half. The
acceptance bars in the table above are the **2026-08-16 ledger** values,
not these — the ruling names those numbers.

### THE HECA −29, RESOLVED

The `lane/eatseed` lane measured HECA **7,516 / 1,490a** at `e55f98d`
with its own code path provably inert at HECA, against a battery figure
of **7,545 / 1,519a** — a −29 with no mechanism. It is now attributed,
by construction rather than by inference:

* Both patches were censused **on this one tree**, so the law frame is
  identical and every difference is in the emitted geometry. The lane's
  patch reproduces 7,516 / 1,490a to the row; the battery patch
  reproduces 7,545 / 1,519a to the row.
* `census_rows_diff` between them: **EXACT 7,522, MOVED 0, GONE 36,
  NEW 7.** Every one of the 43 moved rows is `drainage_spine`
  (GONE 34 `runway|runway` + 1 `apron|apron` + 1 `junction|junction`;
  NEW 7 `apron|apron`), and all 43 are airside — which is why
  adjudicated and airside both fall by exactly 29.

**The −29 is F3c's emitter-side graded handoff (`47e83ed`), nothing
else.** It is the same mechanism, in the same family, that the triage
dossier measured as −24 at KAFW and −7 at KDFW, and that this battery
measures again as −10 at SPJC. It is NOT the crown fix (whose validator
half is the separate −3 on an unchanged patch — 7,548 → 7,545, exactly
what the lane reported) and NOT a build-frame difference (the DEM frame,
corpus and config frame are recorded identical in both `frame.json`s).

### Per-airport: airside EXACT / GONE / NEW, and the family movers

Airside row join is over the law-true airside population (out-of-scope
and version-deferred rows included, so the arithmetic is visible);
adjudicated airside is quoted beside it.

| airport | airside EXACT | GONE | NEW | adjudicated airside |
|---|---:|---:|---:|---|
| CYXY | 86 | 0 | 0 | 75 → 75 |
| SPLP | 34 | 0 | 0 | 34 → 34 |
| SPJC | 189 | 10 | 0 | 199 → 189 |
| KAFW | 467 | 27 | 2 | 89 → 64 |
| HECA | 1,476 | 43 | 11 | 1,519 → 1,487 |
| KDFW | 2,119 | 141 | 0 | 291 → 150 |

**CYXY 336 → 206.** Airside byte-identical: 86 EXACT, 0 gone, 0 new, and
`airside_value_delta` reports **0 solve-owned nodes moved**. The whole
−130 is the chord limiter on the landside: `within_shape
groundside_pavement` **110 → 1**, `within_shape service_road` 13 → 3,
`within_shape service_junction` 12 → 2. Against it, `transverse
service_road` 71 → 76 — the relocation this ledger has now seen at every
airport.

**SPLP 43 → 36.** The only movement is `within_shape service_junction`
8 → 2 (6 GONE, worst 0.86 m at 18–19 %). Airside 0/0; both value frames
report 0 nodes moved.

**SPJC 482 → 397.** Airside −10, every row `drainage_spine::runway`
(F3c). Groundside: `within_shape service_junction` 66 → 26,
`within_shape service_road` 38 → 5, `within_shape groundside_pavement`
12 → 0; against +11 `mid_edge_step` and +4 `vertex_to_edge_step`, both
`service_junction|service_junction` and both at one site
(−12.019792,−77.108244 / −12.019799,−77.108445, worst 0.838 m) — the
limiter flattens two junction rings to different levels and the step
between them becomes legible. Solve-owned airside: 2 nodes @ 0.01 m.

**KAFW 365 → 259.** Airside −25 = 24 `drainage_spine::runway` (F3c) +
3 `strip_arc` gone − 2 `strip_arc` new, all at the one graded-strip site
`-10633`. Groundside: `within_shape groundside_pavement` **72 → 2** —
the lot family that inherits its road welds, exactly the corollary
clause 3 of the limiter spec was written for. Solve-owned airside:
0 nodes moved.

**HECA 7,548 → 4,812.** Airside −32 = the −29 `drainage_spine` above,
−1 `strip_seam_tear` (5 gone / 4 new; the site moves from ways
`-13322|-13452` to `-13322|-13323`) and −2 `within_shape::building`.
Groundside −2,701: `within_shape groundside_pavement` **2,006 → 45**,
`within_shape service_junction` 1,533 → 597, `within_shape service_road`
169 → 61; against `transverse service_junction` **+218** (1,379 →
1,597), `transverse service_road` +64 and `mid_edge_step
service_junction` +52. The build's own limiter certificate:
`chord-grade-limited 1233 polygon(s): 170 groundside_pavement @5%,
1002 service_junction @8%, 61 service_road @8%; shared nodes road/lot
3939, rect/junction 4966, stricter-cap 3939, road near-miss 2896
(of 44981 node(s))`.

**KDFW 576 → 411.** Airside −141, **0 new**: 109 `within_shape::junction`
+ 21 `transverse::junction` + 2 `strip_seam_tear` + 2 `mid_edge_step
junction|runway` — the whole 18L/36R EAT contradiction site, worst
21.74 m — plus 7 `drainage_spine::runway` (F3c). The 11 solve-owned
airside nodes that moved (worst 21.35 m at 32.87925473,−97.05157894) are
that site's junction ways coming DOWN off the refused 196.824 pin onto
the runway datum: the repair itself, not a pull.

### New docket lines

1. **HECA chord-limiter airside residual.** The limiter pins airside as
   data and one solve-owned node still moves: **`30.12927761885,
   31.41320440005`, 0.12 m** (`apron` + `service_junction`, welded to
   the road). Measured on this composed build, not inferred. CYXY 0
   nodes, SPLP 0, KAFW 0, SPJC 2 @ 0.01 m.
2. **The pre-existing final-projection airside channel.** The build's own
   `[airside-value-audit]` line on this battery: `HECA final#1: 6085 of
   107356 AIRSIDE node(s) moved across this projection by > 0.01 m
   (worst 16.881 m) — STOP`. Unchanged from the control, so this wave
   did not widen it. Freezing airside INSIDE the final projection is NOT
   the remedy — that was built and refused (HECA plateau airside
   16.8k → 40.9k; that pass is what makes airside lawful today).
3. **CROWN DECLARATION GAP** (reported, never adjudicated; a rising count
   is an emitter DECLARATION gap, never a surface defect) —
   CYXY 29 (junction 29), SPLP 27 (runway 27), SPJC 162 (junction 148,
   runway 11, service_road 3), KAFW 88 (junction 76, service_junction 9,
   service_road 3), HECA 215 (junction 106, runway 100, apron 9),
   KDFW 578 (junction 560, service_junction 15, runway 3).
4. **KAFW's new classes** (dossier
   `docs/triage/KAFW-KDFW-20260820.md`), with N-1 now **verified on the
   composed build**:
   * **N-1 — road transverse/within_shape at 2–8 %.** Over the
     `SERVICE_ROAD_MAX_TRANSVERSE` 2 % cross-section cap, UNDER the
     limiter's 8 % chord cap. The dossier predicted the limiter would not
     book them. Measured, road-role rows by grade bucket, 2026-08-16 →
     now: **≥ 8 %: 34 → 4** (the limiter's whole road payment);
     **2–8 %: 148 → 170** (transverse) and 16 → 16 (within_shape) — not
     only unbought but **larger**, because flattening the over-cap chords
     deposits their debt inside the band the cross-section cap still
     fails. `transverse service_road` is unmoved at 49. This is owner
     question 6: is the cross-section limit or the chord cap the law?
   * **N-2 — the crown-realisation wobble.** `runway_crown` 34 rows,
     realised − declared median +0.013 m, sd 0.034 m; emit decimation
     REFUTED as the author. Row-stable this wave, 34 → 34.
   * **N-3 — the solver exit**: 326 law edges over cap at the final
     projection, **195 BOTH-HARD** (a hard-anchor contradiction the
     projection cannot move), plus 121 empty-polytope midpoints.
   * **N-4 — four infeasible tile-seam DEM pin pairs** (worst 14.65 %
     over 36.4 m against a 1.5 % cap).
   * **N-5 — closed** by the EAT rect-level ruling.
5. **EAT after the rect-level refusal.** The ruling was deliberately NOT
   transferred to the **deck-pin guard**, which shares the same
   unpriceable hole (per-object; bridgeguard's call). **KSTJ's rect now
   refuses whole** (5 of 18 pins priced) at an airport that is not built.
   And **~70 % of KDFW's EAT pins carry no envelope box** — a rect with
   no priceable node is still unjudged.

### Held lanes (implemented, measured, NOT merged)

* **RM route-metric** — `lane/routemetric` `c009239` + `e5744c3` +
  `4ad22a0` (bake-priced pairs + the one `ring_adjacent_pair`
  predicate). **Blocked on the owner's C3 / taxi-pass question**
  (RULINGS 2026-08-20/21, owner question 1): the airside transverse rows
  RM relocates sit on `apron|apron` / `junction|junction` pairs priced
  from AIRCRAFT axes — the TAXI pass — whose aligned-partner completion
  was previously REFUSED. Merge condition already ruled: the sidecar must
  carry a bake hash keyed to the patch body, and a mismatch REFUSES the
  census.
* **C3 rework** — `lane/c3rework` `ae4a6d5`, airside-frozen on the
  service pass (worst airside pull 58.5 m → 1.11 m, HECA groundside
  −703, 26 twins). **STOP**: it still leaves CYXY at 93a against the 75a
  bar and HECA +13 (all mixed `frontage_near_miss`). C3 cannot pay RM's
  relocated airside debt.
* **Adaptive `join_snap_t`** — `lane/resid` `31909dc`. **HELD**: it meets
  the per-airport letter (HECA airside net −62, no airport up, zero new
  test failures) but re-prices HECA's airside population wholesale —
  **415 gone / 353 new** — to buy ONE runway row (the 2.24 m sliver), now
  that the crown fix retired the other two. Merge-or-drop is the owner's
  call (owner question 3).
* **A2 frontage cutback** — stays **default-OFF**. The limiter has landed
  so the spec's re-arm condition is met, and A2 still fails per-airport:
  it is a **PRE-SOLVE geometry change** (SPJC apron `-10113` gains a
  vertex, re-solves 0.03 m lower, +15 airside) that no post-solve pin
  reaches. A spec-revision question (owner question 4).
* **C2 law pairs** (`lane/lawpair`, seam tears 45 → 8) and **SM3**
  (`lane/sm3solve` `e1fadad`, the 204-node pre-existing contradiction) —
  **not re-measured this wave.** Both were queued behind the RM base, and
  the RM base is what owner question 1 blocks.

### What is NOT zero, and why

1,999 airside and 6,121 adjudicated remain. HECA carries 1,487 of the
airside (the C1 mega-apron relief residual, untouched by this wave —
`within_shape::apron` is row-identical) and 3,325 of the groundside.
The groundside bulk is now one shape everywhere: **`transverse` on the
road family**, which the chord limiter does not and cannot buy, and which
GREW as the limiter paid the chord debt (HECA +218/+64, CYXY +5,
KAFW +22). That is the same class as KAFW N-1, and it is one open law
question — the 2 % road cross-section cap versus the 8 % chord cap —
not a solver defect. The next honest movements on this ledger are that
ruling, and the RM/C3 pair the owner's first question gates.

## 2026-08-16 battery refresh (composed main after the zero-debt round's merges)

Merged this round: F3+F3b gap conformance, R8 runway seeding (both
attempts), the KDFW/implausible-deck bridge guard, R6/R7 frontage
(A1 landside term + R7c cut-and-fill + pad-channel closure; the A2
cutback is default-off pending the road chord limiter). Six-airport
battery, all rc=0 — KAFW and KDFW build for the first time ever.

| airport | adjudicated | airside-for-acceptance |
|---|---|---|
| CYXY | 336 | 75 |
| SPLP | 43 | 35 |
| SPJC | 482 | 199 |
| KAFW (new fixture) | 365 | 89 |
| HECA | 7,548 | 1,522 |
| KDFW (new fixture) | 576 | 291 |
| **total** | **9,350** | **2,211** |

HECA airside is down ~300 from the evening's frame; groundside is UP
(+892) — the frontage round's honest exposure: area moved from
chord-limited lots into road faces that have NO chord limiter yet
(the named wave-3 fix under the standing roads-like-taxiways ruling).
HELD lanes (implemented, measured, unmerged): RM route-metric
(SM1/SM2 collapse proven; relocates debt into transverse — two owner
questions pending), C3 alignment (transverse −549 but pulls airside),
SM3 certified exit (204-node pre-existing contradiction surfaced),
C2 law pairs (seam tears 45→8). The original 2026-08-15 category
analysis below remains the mechanism reference.


**Frame:** composed main after the R5+R5c merge (engine 1.50.1696), censuses
`CYXY_20260815T214510` / `HECA_20260815T214605`, 2026-08-15 late.
"Adjudicated" = law-true census rows after registered exemptions (declared
terraces), out-of-scope, and version-deferred families — the pass/fail
population. Airside has been **byte-identical through every arm tonight**:
nothing below is a regression from today's rounds; it is the standing debt,
now fully attributed.

## Headline

| airport | adjudicated | airside | groundside | mixed |
|---|---|---|---|---|
| CYXY | **333** | 74 | 259 | 0 |
| HECA | **6,955** | 1,733 | 5,134 | 88 |

Airside is not zero. The airside mass decomposes into three categories
(C1–C3 below); none is unattributed.

## Root-cause categories

### C1 — The mega-apron relief residual (largest airside block)
**Rows:** HECA airside `within_shape` 1,502 (worst 11.36 m, p50 0.82);
CYXY `raoa` 8 (worst 6.15) is kin.
**Cause:** HECA's real ~85 m relief against apron/taxi caps. The production
law (spine-frame + §7 reference rods + route-metric band) is the ruled
answer; these rows are its residual — the solve does not fully reach the
lawful surface feasibility-is-guaranteed says exists.
**Proposed:** its own round, fed by the two OPEN owner rulings from K1b
(the string-bend class and the rwy-flexed class). No new law proposed here
until those are ruled.

### C2 — Strip conformance seams
**Rows:** airside `strip_seam_tear` 45 (worst 8.55 — two pre-existing
sites + the docketed B2 site), `strip_arc` 55, `strip_longitudinal` 3,
`adjacent_ground_tear` 4.
**Cause:** strips conform to two authorities at a seam and disagree — the
node-vs-edge class.
**Proposed law (already docketed, refined by R5b's refutation):** shared
boundaries are LAW-PAIRED in the one graph — never a frozen side, never
two independent conformances. One spec covers this and the R5c weld-site
dossier (C6).

### C3 — Station misalignment expressed as transverse tilt
**Rows:** groundside `transverse` 1,684 HECA / 82 CYXY (ALL same-shape;
p50 grade 5.1 % at p50 width 7.5 m; junctions carry 1,154 of 1,684),
airside `transverse` 104 / 63.
**Cause (corrected 2026-08-15 late, after the owner's 0 %-by-construction
question):** the cap and the instrument are both right — each paired
cross-section IS 0 % by the station-shared value rule, and the census
casts true perpendiculars. The rows live BETWEEN stations: where opposite
edges carry vertices at misaligned arclengths, edge interpolation samples
two different effective stations and the road's lawful LONGITUDINAL grade
appears as lateral tilt (8 % × ~4 m misalignment ≈ 4–5 % across 7.5 m —
the measured p50). A flat chord had zero longitudinal grade, so the class
was invisible until R5 made roads track terrain. The mesh interpolates
the same way, so these are real small diagonal warps, honestly priced.
Junction rings dominate because they have no cross-section pairing at
all; the 350 % worst cases are genuine junction cliffs (co-level
residue).
**Fix (no ruling needed):** plant aligned partner feet on BOTH edges at
every road station, and extend the R5c co-level so junction ring
vertices join the through-chain's stations. The family then collapses
to the real cliffs.

### C4 — Landside lots, frontage welds, and the lot-over-road class
**Rows:** groundside `within_shape` 3,176 HECA / 174 CYXY, plus most of
`mid_edge_step` 231 / `vertex_to_edge_step` 47.
**Cause (three rulings, all made tonight):** the free-road width test has
no landside term (car parks absorb public roads — 142/160 HECA groundside
shapes contain mapped roads); building-pad datums weld into frontage road
networks; lots were cut-only (`min(terrain, 8 % cone)` — the 40,000 m³
CYXY hollow).
**Fixes (ruled, spec next):** R6 — roads carry OSM-sourced spines that
pass THROUGH pavement (crossed pavement consumes spine stations);
R7 — mouths-only welds (never buildings; parallel frontage cuts back to
DEM at its real level) + two-sided cut-and-fill lots + the landside term
in the free-road knife. The sink dossier's model (r = 0.96) says this
category collapses when the illegitimate low welds go.

### C5 — Gap fill and drainage
**Rows:** airside `drainage_spine` 8 (the gapstop single-spine residual);
the photographed plateau walls are mostly census-invisible (no law pair
spans pavement→gap→pavement at range).
**State:** F3/F3b implemented on `lane/gapconform` and HELD at the
attempt cap — the staged spine law is in (conformance band pinned,
interior dam + descent cones, MIN_FALL still provisional), but a
1,323-row emitter population (spines riding terrain above pavement at
median 76 m range, worst 25.6 m) is not yet located to its emitting path.
**Next:** one attribution pass (sample rows → way ids → emitter), then F3
merges and this category plus much of the in-sim flats class closes.

### C6 — Marginalia (small, named, bounded)
`frontage_near_miss` 94 (88 mixed, worst 11.53 — rides C1's relief),
`runway_crown` 9 (all ≤ 0.07 m), `runway_end_skirt` 3, `plane_gradient` 7,
`lateral_contiguity` 3, and the R5c weld site (2 step rows + 1 sliver,
dossiered — joins C2's law-pair spec).

### C7 — Withheld patches (invisible to any census)
**KAFW:** +32 arm refuses (0.287 m transverse seeding deficit between
parallel runways) — R8 specced: the DEM-follow band becomes route-feasible
transversely (or interim: join contacts at every taxi crossing, seated
through `faa_joint_solve`).
**KDFW:** refuses on a different family — a hard-seed plateau at
183.286 m against a runway station at 176.470 (6.8 m law spread,
650 nodes). Unattributed; the larger +32-098 blocker.
A refused patch is a whole airport absent from the tile — these outrank
any row category for in-sim impact.

### C8 — What no census can see
Seed-character and DEM-deviation-at-range classes are census-invisible by
ruling (the warm-start lesson). In-sim remains the only detector; the
mixed-version tile-seam hazard (tiles built on 1.0.249–251 carry flattened
edges) persists until affected tiles are rebuilt on the current app.

## Priority reading

1. **C7** (whole airports missing) — R8 + the KDFW attribution.
2. **C4** (the groundside bulk, ~3,400 rows, all three laws already ruled) — R6/R7 spec + lane.
3. **C5** (F3's last attribution pass) — closes the photographed classes.
4. **C3** is a station-alignment fix (no ruling needed) — ~1,700 rows collapse to the real junction cliffs.
5. **C1/C2** are the airside end-game — the two open K1b rulings gate them.
