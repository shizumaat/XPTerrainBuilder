# auto-patch-v2 — M5e report: taxiway STRETCHES and CAP BY EDGE PORTION (RULINGS 2026-09-04t-2/3)

Lane `lane/v2caps` off main `ede79b2e`. Rulings implemented: **04t-3**
(a taxiway's letter/cap applies per STRETCH from its centreline
intersection with another taxiway onward; junction faces carry the cap of
the stretch they belong to; strictest-of-chains 04q-2 superseded) and
**04t-2** (a junction/road MOUTH keeps its own cap; a LONG EDGE shared with
an apron takes the apron cap on the portion along the apron only; the
oracle follows the same portion rule). Every law value from the TOML
tables (one new key); no env reads; no v1 imports in v2 (the oracle edit is
v1's tool); every file ≤ 1,000 lines; attempt cap two per family respected
(one attempt spent per family, one refuted mechanism deleted).

## 0. Site first — CYXY apron 156 (`pav17`; face 150 → 151 on this tree)

| | z − DEM median | chain (`why CYXY --at 60.708422,-135.072589`) |
|---|---|---|
| before (main `ede79b2e`) | **−1.98 m** (min −2.23) | v2347 apron → v477 junction 100 / parallel 6: **taxi_within_shape 1.50 % × 222.0 m** (+3.33) → v469 runway edge 1.5 % × 199.3 m (+2.99) → runway 02 CIFP pin 694.334 |
| after (this lane) | **−1.87 m** (min −2.12) | the same chain, the same limiter: v2348 → v477 **1.50 % × 222.0 m**; the +0.11 m came from the runway crown hop (v469 694.221 → 694.337, the crown preference yielded 0.115 m) |

The expected further rise did NOT materialise. The G example itself
reproduces exactly (§1: X = v482 ↔ the next G vertex v2352 is a
same-stretch pair at **3.00 % × 38.3 m** in both faces the G stretch
bounds, `taxi_within_shape … per stretch (04t-3)`), but the apron's
limiter is a junction-100 BODY chord between a vertex on stretch 20
(taxi17, A) and a vertex on stretch 27 (E, D) — a cross-letter pair, which
this lane prices at the face's strictest letter (§1, the stated choice).
The v1 oracle does not price that 222 m chord at all (its JUNCTION MESH
RULE prices a junction's spine + triangle-mesh edges only; v2 solves the
all-pairs superset by its own M2 decision). Whether v2 should adopt the
mesh / travel-path reading for junction body chords is open question 1.

## 1. The stretch rule as implemented

* `constraints/stretches.py` (new, 223 lines): a `taxi_centerline`
  breakline is split at every planar vertex it shares with another taxi
  centreline (`build_stretches`, the intersection vertex belongs to both
  stretches); each stretch carries ITS chain's letter — threaded
  `evidence.Chain.letter` → `roles.CutLine.code_letter` →
  `overlay.SourceLine.code_letter` → `model.planar.Breakline.code_letter`
  — and the taxi family's cap for it. CYXY: 57 stretches, 26
  intersections; G = stretch 17 (bl 22, `taxi19`, A, 3 %) from X to the
  taxi17 crossing; E split into stretches 22/23 (D) at X.
* PAIR PRICING (`compose_pairs`, `pair_caps`; `taxi.py:73-105`): a pair
  whose two vertices lie on ONE stretch holds that stretch's cap (the
  looser of several common stretches — the oracle's "looser of the shared
  centerlines", read through the published `axes`, which now carry
  per-stretch caps: `transverse._edge_cap` → `stretches.edge_cap`); every
  other pair of the face holds the FACE's cap = the strictest CROSSING
  letter (`roles._junction_letter:565-593`: strictest of the chains
  running through/along the part, else the NEAREST through-route that
  minted it — a route merely within proximity no longer tightens). It is
  not a chord across letters because a cross-letter pair is never priced
  at the looser letter; the relaxation lives on the stretch whose letter
  it is. **Not chosen and deleted:** the nearest-stretch partition with
  cross-letter composition along the travel path (Σ cap·len through the
  intersection, floored at the face cap, ceiled at the looser plane) —
  measured on the twin fixture 2026-09-04 the v1 oracle read 4 rows at
  1.91–1.99 % / cap 1.5 % on exactly the composed pairs: a one-letter-
  per-way oracle cannot read a body region, and publishing v2's per-pair
  budgets (`pair_caps`) would put the oracle on v2's population (its baked
  path floors every published pair at the way cap, un-tightening the
  frontage reading).
* Centreline chords (`taxi_centerlines`) and the route graph
  (`routes.py`: centreline edges, taxi-face chords) carry the same
  per-stretch prices, tightened by a governed non-taxi face the chord
  bounds (an apron lane is apron, 09-03j). Sidecar key `stretches`
  (`[[ll…], cL, letter, ref]`); `verify/within.py` re-composes per stretch
  from it (`stretch_pair_caps`).
* FRONTAGE ON TAXI-FAMILY FACES (`taxi.py`, `routes.py`, `verify/within.py`):
  a pair with a pad vertex holds the pad's cap (`common.roles.building`).
  This is the mechanism behind the "07-06 vs 04q-2" rows — §3.

## 2. The portion rule as implemented

* v2: `apron.apron_edge_portions` (`apron.py:118-214`, generator
  `apron_edge_portion`, registered after `apron_within_shape`): for every
  governed, non-apron, non-rigid face with cap above the apron's, the
  contiguous runs of its ring whose edges are SHARED with an apron ring
  (same vertex ids) and whose length ≥ `emit.toml
  within_shape.apron_edge_portion_min_width_ratio` (= **1.5**) × the
  face's WIDTH (short side of its minimum rotated rectangle) are LONG
  EDGES: every pair inside one run is a `Diff` at the apron cap. A shorter
  run is a MOUTH — nothing minted; pairs with a vertex off the run keep the
  face's cap. Why 1.5: a square-on mouth shares ≈ 1.0 width, a 45°-skewed
  one ≈ 1.4; a face running ALONG an apron shares a multiple.
* Oracle (`tools/check_grade.py`, separate commit `0a7b019d`):
  `mark_apron_edge_portions` marks every `o4_grade_law='apron'` way's long
  shared-apron runs ONCE per parse (`run_checks`, right after
  `_ll_to_m_factory`); a marked way reads its OWN role cap
  (`_role_grade_limit`, `_soft_grade_shape` no longer sets
  `adopts_apron_grade`), and `iter_shape_grade_constraints` tightens every
  pair inside one long run to the apron cap (a `min`, so frontage / seam /
  cross-section still bind). Value `auto_patch.config.
  APRON_EDGE_PORTION_MIN_WIDTH_RATIO = 1.5`; `tests/test_harness.py` holds
  it equal to the TOML value and exercises long edge vs mouth.
* **Instrument correction on the stored v1 controls: zero deltas.**
  CYXY `c01e77f19e22` 160/74 airside (adjudicated airside 67) before and
  after; SPJC `742516a81572` 687/597/597; HECA `7ea3ca72c47c`
  2836/1072/1074. Not one shipped v1 patch carries the tag (0
  `o4_grade_law` ways in all three) — the lateral-contiguity law retired
  the adoption stamp — so the 07-06 whole-body reading was already inert
  in production; the correction lives in the oracle and its twins.

## 3. Attribution: the SPJC 8 / KCLT 33 / HECA 18 junction rows were FRONTAGE rows, not 07-06

Probed on the m5c patches (`91700133c773`, `3bfaace6a7e6`,
`cee809865b7d`) by joining every within_shape row's endpoints to the ways
holding them: **SPJC 8/8, KCLT 33/33 (+6 service_road), HECA 18/18
`junction|junction cap=1.0` rows have a BUILDING-PAD endpoint** (SPJC:
building16 / building… on junction pav40/pav16; KCLT pav37/pav48). The
oracle's cap came from `grade_law.classify_pair`'s frontage rule (a pair
with a pad endpoint ≤ `BUILDING_FRONTAGE_MAX_GRADE` = 1 %), not from
`_body_cap_unbounded`'s apron branch — v2 emits no `o4_grade_law` tag, so
that branch is unreachable on a v2 patch. m5c §6.1 / 04s "one reader
disagreement (07-06 vs 04q-2)" is refuted; v2 priced pad-endpoint pairs on
junction faces at the letter cap while `apron.py` applied the frontage
chord rule to apron faces only. Fix: the pad's cap on every taxi-family
pair with a pad vertex (one attempt).

## 4. Builds (ledgered, `build_airport.py ICAO --engine v2`, tree after `3faa5224`+`0a7b019d`)

| airport | tag / ledger key | build | v2 verify | oracle census adjudicated / airside | before |
|---|---|---|---|---|---|
| CYXY | `CYXY_20260904T130531` / **a2c00e96782d** (control on main `CYXY_20260904T130653` / 136bf1c9832b, 0/0) | 4.8 s, optimal, crown:469 yielded 0.115 | 0 | **4 / 4** — runway\|runway 1.76–1.97 % over 12–13 m, 0.24 m, at the runway-02 threshold (60.7120, −135.0717) | 0 / 0 |
| SPJC | `SPJC_20260904T130549` / **e8992a9dbdd8** | 59.4 s, optimal, no yield | 2 (adjacent_ground_tear) | **0 / 0** | 8 / 8 |
| KCLT | `KCLT_20260904T130549` / **e5c4db91e012** | 83.2 s, optimal, no yield | 46 | **27 / 0** (all groundside: mid_edge_step 12, cross_shape 4, vertex_to_edge_step 4, within_shape 6, road_cross_section 1 — the first-build lot residual m5c §4) | 70 / 44 |
| OTHH / SPLP / LEMD | stored `9ad5b9c3db45` / `a4a3758be45b` / `4d96b4d41c41` re-censused with the NEW oracle | not rebuilt (the sweep) | — | **0 / 0**, **0 / 0**, **0 / 0** | 0 / 0 |

CYXY's four rows: node −531 (runway ring, 694.57) vs −472 / −471 / −545.
In the control the same pairs sit at 694.54 vs 694.33 = **1.72 %** over
12.2 m — already over the oracle's 1.5 % and inside its quantisation
envelope; this lane's solve moved −531 by +3 cm (the crown preference at
v469 yielded 0.115 m because the per-stretch rows let more of the
junction/apron rise) and the pairs left the envelope. v2 prices those very
chords (`runway_within_shape` rows 530–471 etc.) at **2.0 %**
(`rulesets.runway.longitudinal` for CYXY's runway class) while the oracle
prices runway|runway at **1.5 %**: a pre-existing runway-cap disagreement
between the two readers at CYXY, exposed, not created. Not fixed here
(runway law is not this lane's family; open question 2).

## 5. Twins

`tests/auto_patch_v2/test_stretches.py` (7): the split at X with per-
stretch caps and per-stretch published axes; the CYXY G/E example (X ↔
next G vertex at G's cap in every face, and the same price in the route
graph); a junction across a letter change (on-G pair at A, on-A pair at D,
cross pair and body pairs at J's own D — the row set is exactly {A, D});
two stretches of one letter read as one plane; long shared edge at the
apron cap vs mouth untouched (the run IS the shared edge, `face_width`
geometry stated); oracle equality on the solved fixture (v2 verify 0 rows,
`check_grade` law-true 0 within_shape rows, the 3 % actually USED between
X and the next G vertex); a minted step on the G stretch read at G's cap.
`tests/test_harness.py` (2): the portion rule prices no row on a long
junction's far edge at 1.2 % nor on a 1.2 % mouth, and one junction row at
cap 1.0 on a 1.2 % shared run; the marker's runs and the one ratio (v2 TOML
== v1 config == the oracle's constant). Suites: `tests/auto_patch_v2` 182
passed; `tests/test_harness.py` 302 passed.

## 6. Not done / open questions (≤ 3)

1. **Junction body chords across letters** (CYXY 156's limiter: v2348 ↔
   v477, 222 m at 1.5 % inside junction 100): v2 prices every pair of a
   junction as a plane; the oracle prices spine + mesh edges only. Adopt
   the mesh / travel-path (04o) reading for junction body chords in v2, or
   keep the plane? Owner question; the cross-letter composition was built,
   measured against the oracle, and deleted (§1).
2. **CYXY runway cap disagreement** (v2 2.0 % vs oracle 1.5 % on the
   runway-02 threshold chords; 4 rows at 0.24 m): which runway class /
   cap is law for CYXY 02/20, and which reader is wrong?
3. OTHH / SPLP / LEMD were re-censused on their stored patches only (the
   oracle change is inert on them); their builds change under 04t-3 and
   the frontage cap and will be measured by the sweep. HECA was not
   rebuilt (its 03k hangar row / 04t-1 least-variance is `v2relax`'s).
