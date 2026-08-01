# S1 — the taut-chord string constructor (Opus-executable)

Sub-spec of `taut-string-model-spec.md` §4.3.1 / §5 S1 and
`taut-string-implementation-plan.md`.  Fable-authored 2026-07-30 (spec
authorship rule).  Deviation rule binds: reality diverging from this
text is a STOP-and-report, never an improvisation.

## §1 The defect this step exists for (measured)

The HECA parallel-taxiway chord sags to **−11.07 m** below the owner's
111→113 straight string (envOFF, shipped arm; spec §1.8) while the §10
interval rod faithfully holds the surface to ±2 cm of the phase-A
string — therefore **the phase-A string is itself constructed
sagging**.  S1 replaces string CONSTRUCTION: each spine corridor's
profile becomes the *taut string* — the longest-possible straight
chords between anchors, bending only where grade feasibility forces
it, every bend DECLARED with a witness.  Enforcement (rods, sweeps,
field) is untouched; it inherits the new string.

## §1a P3's attribution — MEASURED (2026-07-30, zero builds), and it
## reshaped this spec

Interventional, one variable per arm, single artifact + code version.
Worst 200 m-bin departure vs the owner's 111→113 string:

| arm | variable | worst bin |
|---|---|---|
| control (live state) | — | −12.17 |
| A0 constructor re-run | nothing masked | −9.97 |
| A1/A1g band CEILING → +inf | chord / global | −9.97 (zero effect) |
| A2 band FLOOR → −inf | | −11.43 (floor was propping) |
| A5 seed = raw DEM | | −6.01 (profile sits BELOW the DEM) |
| A6 anchor set swapped | | −9.97 (anchors exonerated) |
| A8 **59 corridor-endpoint pegs seeded at the string** | | **−5.76** |
| A3 all 721 nodes seeded at the string | | −5.76 (≡ A8 at every bin) |
| A8c pegs + ceiling masked | | **−0.05** |

**Verdicts.**  Classes (a) runway crossings, (b) seats, (c) gs pins:
EXONERATED as direct pullers (zero hard nodes within 100 m of the
whole chord; full anchor swap moves nothing).  (d) DEM seed: not the
source.  (e) band ceiling: **LATENT, not binding** — it sits
0.66-5.94 m below the string over along 1000-2400 yet masking it
alone moves 0.00 m; it becomes the sole binding constraint (worth
5.71 m) only AFTER the pegs are freed; 21/43 dip nodes sit ON their
band floor, 0/43 on their ceiling.  **(f) — the attributed class,
absent from the original list: corridor decomposition + peg
inheritance.**  `_build_spine_corridors` cuts the single 3,980 m
chord into 62 corridors (longest 900 m, ZERO hard anchors on any);
their endpoint pegs carry inherited draped values; 8 % of the nodes
carry 100 % of the movable defect.  §4.3.1's "longest possible
straight chord between its anchors" was structurally never attempted.
The constructor CAN hold the owner's line (−0.05 across all 20 bins).

**Bounds caveat:** all arms ran with `spine_floor` and `couple_adj`
absent from the dump; both only tighten, so every number above is an
UPPER BOUND and A8c's −0.05 may be optimistic.  Both fields are
ordered into P2's instrumented build.

**Open attributions (NOT this spec's to guess):** (i) the live state
sits 2.2 m below what the constructor emits from the same state, with
262/721 chord nodes below their own band floor — some post-phase-A
step moves them down; P2's five `_solve_spine_profile` elev snapshots
own it.  (ii) Whether seats/gs pins depress the band CEILING itself
(they are exonerated only as direct pins) — owned by the offline
ceiling-attribution task (plan P3c) on P2's enriched dump; a build
for it is NOT authorized unless the offline path is shown
insufficient.

**Attribution rule (normative, replaces the early-stop licence that
nearly produced the tenth falsified mechanism):** latent vs binding
is decided ONLY by masking; a constraint's position relative to the
string is NEVER an attribution.

## §1b The drag attribution (P2's five snapshots, 2026-07-31) — and
## the ORDERING RULING

Measured through phase A at the seam (cross-validated: stage 5 =
`elev_entry_A` = 108.454 across two independent builds):

| stage | seam | Δ | share of strung motion |
|---|---|---|---|
| 1 entry / DEM-seeded | 103.620 | — | — |
| 2 after harmonic min-curvature | 107.973 | **+4.353** | **67.1 %** |
| 3 after internal taut-string pass | 108.012 | +0.039 | 11.1 % |
| 4 after fairing | 108.012 | +0.000 | 1.9 % |
| 5 after exact cap projection | 108.454 | +0.442 | 19.9 % |

**The harmonic min-curvature solve owns the corridor's departure from
DEM.**  It has no altitude preference — it interpolates toward the
network's descent, which LIFTS the seam off low DEM (+4.35) and SAGS
chord 1 below the owner's high string: one mechanism, two signs.
P3's class (d) is thereby resolved.  The internal taut pass is an
11 % downstream corrector.

**Ordering ruling (Fable): S1's constructor SUPERSEDES the harmonic
on string interiors — it is not the 11 % corrector.**  The hook
overwrites assembled-string values after phase A returns; the
harmonic's 67 % survives only through (i) string END values, (ii)
fallback pieces, (iii) discarded work.  Therefore:
* **S1 keeps its shape (α)** — external hook, post-phase-A
  supersession — and closes the leak surface NOW via the hardened
  §3 end policy (true terminals solved FREE; phase-A values only on
  fallback pieces, counted in the inventory).
* **S1b is ordained as the end-state (β), designed by Fable AFTER
  S1's measurement:** the constructor runs first-class inside phase
  A on assembled strings; the harmonic demotes to residual
  gap-filler with constructor values as Dirichlet boundaries; the
  internal taut pass on assembled strings is deleted there.
  Rationale to carry: the 67.1/11.1 table; α's temporary
  single-pass violation (harmonic computes interiors the hook
  discards) is acknowledged and priced at S1b, not silently kept.
  **EXPANDED 2026-07-31 (owner model confirmation — spec §4.1
  block): S1b now also carries the DRAW-TOWARD reference
  re-founding** — master strings (authored routes with datums)
  first; fabric reference = the grade-law projection out from the
  string web (1.5 % along / 1 % lateral); R re-founded as the apron
  instance of that projection; layer 6 shrunk to off-web fallback;
  the harmonic's string BCs give it the altitude preference it
  measurably lacks.  The owner's question and S1b describe one
  end-state from two sides; they are designed TOGETHER, after S1's
  numbers land.
* Why not β now: mechanism-before-fix (α+D's W-CHORD1/2 measurement
  prices β), and β's surgery site is `_solve_spine_profile`'s
  interior — where P2 is concurrently landing instrumentation; one
  hot function, one session at a time.

## §2 Normative construction (the contract)

**Stage 0 — maximal-string domain assembly (REVISED per §1a; the
structural fix).  MECHANISM REVISED AGAIN 2026-07-31: the original
heading-based follow-through was FALSIFIED on the real geometry —
§10(vi) fired and stopped it, correctly.**  The string domain is NOT
the corridor pieces: `_build_spine_corridors`' 62-piece decomposition
of chord 1 is the attributed defect vector (class f).  S1 assembles
its OWN domains in `taut_string.py`.

**The falsification record (offline replay, real HECA spine graph,
control validated against §1a's 62 pieces / 722 chord nodes):**
heading follow-through at piece endpoints assembles ZERO chord merges
at 5-30° and 9.3 % coverage at 45°; not a threshold problem — only
23 of the ~46 junctions needed even exist as piece-to-piece meetings
(pieces meet crossers and fillets instead), the 23 that exist offer
median 36° / p90 140° deviations, and piece endpoints sit median
9.1 m (max 49.4) off the chord centerline because terminal segments
peel off perpendicular.  A vertex-level straightest-continuation walk
also fails (best 824 m; ~5.5 m node spacing makes single-segment
headings jitter-dominated).  Meanwhile the owner's string IS
graph-reachable: the 722 chord nodes are one connected component
with a 3,992 m through-path entirely inside the 25 m corridor.  The
data carries the chord; heading inference cannot find it.

**The mechanism (Fable ruling: centerline-identity assembly — the
authored truth, not a geometric proxy):**

* **Level 1 — group by authoring centerline.**
  `grade_graph._build_global_spine` walks each `Centerline`'s on-line
  nodes in arc order, so "which centerline authored this spine pair"
  exists at graph-build time.  AUTHORIZED plumbing (Fable,
  frozen-interface decision): export that authorship from the SAME
  walk (no extra pass) as a graph-side map (pair → centerline id,
  plus each centerline's arc-ordered node run).  This is same-space
  data (built and consumed in one solve space) — a plain attribute
  on the graph object, deliberately NOT a node-space-store artifact
  (the store is for cross-space carries).
  **Gating ruling (2026-07-31, closing my underspecified
  authorization): the export is UNGATED** — data-plus collection in
  an existing walk; a gate would create a second maintained path
  (the U1 anti-pattern) with no diagnostic value once inertness is
  PROVEN.  Conditions, normative: (i) three-way SPLP body-hash
  identity with the `grade_graph.py` change reverted in the pre
  copy — "reasoned inert" is not an accepted status; (ii) a
  build-time statement (item 6 exempts nothing; if the walk costs,
  the remedy is lazier collection, not a gate); (iii) a READER lands
  with it (the authorship census now; the real-geometry fixture
  permanently) — write-only attributes do not ship.  Each centerline's
  arc-ordered run is a string SEGMENT; one taxiway ⇒ one segment
  chain by authorship, not by inference.
* **Level 2 — merge centerline segments end-to-end** by windowed
  heading at CENTERLINE scale (hundreds of metres — where heading is
  meaningful; the jitter that killed the vertex walk was 5.5 m
  segments).  `TAUT_STRING_FOLLOW_THROUGH_DEG` (config.py, 15.0)
  survives with its semantics moved here; S1-CP2 reviews its value
  against the assembled inventory.
  **SEGMENTATION REFINEMENT (owner 2026-07-31 — "strings should be
  only straight trunks, changing if there's a turn"): level 2's
  merge and the TURN CUT are one criterion from two sides — merge
  across a junction iff NOT a turn; a horizontal turn ENDS the
  string (axis separation: straight in PLAN; bends only in
  ELEVATION where grade forces, declared WITHIN a string).  Turn
  detection uses ONLY the surviving primitives: bearing
  discontinuity between adjacent AUTHORED segments at fragment
  scale (the validated window) — never dense-node local bearings
  (measured fillet noise).  A junction is NOT a turn; an authored
  geometry break is NOT a turn.
  **GROUND TRUTH ARRIVED + CALIBRATION RULED (2026-07-31;
  `/Users/noah/heca_strings.osm` — 40 strings, 88 nodes, 37,327 m
  [DENOMINATOR SUPERSEDED same day — the owner extended the map:
  46 ways / 99 nodes / 41,412.7 m; see DENOMINATOR HYGIENE in the
  acceptance-measurement rulings];
  chord 1 = ONE string, 3,974.8 m, max interior bend 0.00° ⇒ NO
  turn at 1652, the 58.5 % was an ASSEMBLY DEFECT definitively;
  S1's 296-string inventory is ~7× over-assembly):**
  * **MEMBERSHIP GOES COLLINEARITY-FIRST.**  The owner drew
    independent straight RUNS (2 shared endpoint pairs across 80
    endpoints): the target object is the straight run; chaining
    serves the DATA's fragmentation (36 authored fragments tile
    chord 1), not the model's connectivity.  Endpoint-identity is
    DEMOTED from chaining criterion to one evidence source — it
    was a proxy for "same straight run", valid at phase-1 density,
    measured failing at build density (the 1652 terminus: nearest
    continuation 0.86 m away under a different canonical ID —
    endpoint-selection CONFIRMED).  Two fragments belong to one
    string iff COLLINEAR within the turn threshold AND
    ALONG-CONTIGUOUS within a RECOGNITION tolerance.
  * **IDENTITY ≠ MEMBERSHIP ≠ BRIDGING (three-way, normative):**
    the registry is UNTOUCHED and CORRECT at 0.86 m (β = 0; the
    gap is a SOURCE-DATA near-miss — in-repo precedent
    `BUILDING_FRONTAGE_NEAR_MISS_M`, a value-side recognition
    radius that "moves no geometry and mints no identity");
    membership may RECOGNIZE a near-miss continuation; BRIDGING
    stays forbidden — no value blends across an unknown, the
    string's own construction spans its domain.  Widening the
    interning radius would be the fifth proxy — refused.
  * **`TAUT_STRING_TURN_DEG = 6.0`** — ONE constant, both uses
    (turn cut ≡ merge admission; supersedes the 15.0, which was
    validated insensitive across 10-20° in exactly this empty
    band).  Derivation recorded: calibrated on the 36 CLEAN
    ground-truth strings (max interior bend ≤ 5.0°, 29,342 m;
    bimodal, median 0.00°); seated in the measured empty interval
    (5.0, 7.54) — NEVER on the four disputed outliers (7.54°,
    67.4°, 90.9°, 119.1° — referred to the owner: "should these
    have been split?"; if 7.54° is blessed in-string the threshold
    recalibrates at S1-CP2).
  * The RECOGNITION tolerance is fitted jointly with the threshold
    so assembly reproduces the owner's inventory (expected count
    40 ± the outlier resolution; wrong-merge vs wrong-split
    decomposed) — calibrated, never invented; both S1-CP2-reviewed.
  Negative controls against the map: terminal-segment heading AND
  dense-node local bearing must both FAIL.  The ASSEMBLY fixture
  re-bases to the MAP directly; the capture-derived fixture remains
  for density/endpoint mechanics — two fixtures, two properties.

**CONSTRUCTION REPLACED BY THE OWNER'S OWN RULE (2026-07-31;
verbatim: "each string only has two nodes, one at either end of the
longest straight run that follows the spine within a small margin…
they all trace centerlines").  MAXIMAL-STRAIGHT-RUN EXTRACTION over
the spine supersedes fragment assembly:**
* **Membership by LATERAL OFFSET to the run's end-to-end chord** —
  grow the chord along the spine polyline network; never chain
  fragments.  Consequences, recorded: the 0.86 m near-miss class
  DISSOLVES BY CONSTRUCTION (endpoint adjacency stops being
  load-bearing; the recognition tolerance is superseded before it
  was valued; the fifth-proxy risk evaporates rather than being
  solved); runs MAY OVERLAP at crossings (multiplicity census
  measured nodes on 2-5 routes) so greedy consumption dies —
  MAXIMALITY + de-duplication of sub-chords replaces it.
* **The bearing family retires from construction, superseded
  honestly:** `TAUT_STRING_TURN_DEG = 6.0` (ruled on interior
  bends) and the window semantics are calibration HISTORY — the
  updated map exhibits the criterion as a DISTANCE (41/46 strings
  ≤ 0.06 m offset over runs to 3,974.6 m), the owner's phrase names
  a distance, and a small offset margin SUBSUMES bearing (a 90°
  crosser departs at full distance/metre; a 6° branch exceeds a
  ~2 m margin within ~19 m).  Rulings update on ground truth,
  visibly.
* **"Follows the spine" is BIDIRECTIONAL + CONTINUOUS:** (a)
  spine-near-run — claimed spine nodes within
  `TAUT_STRING_RUN_MARGIN_M` of the chord; (b) run-near-spine — the
  chord's along-extent TILED by claimed nodes with no along-gap
  over the continuity bound (stops two collinear sections separated
  by a terminal being spanned as one "run" crossing no taxiway).
  **MARGIN CALIBRATED 2026-07-31: `TAUT_STRING_RUN_MARGIN_M =
  20.0`** — derivation: 10 m-interval along-string sampling of
  nearest-spine-node distance, no cutoff; clean set (outliers
  excluded) p50 ≈ 5-12 / p90 ≈ 11-18 / max ≈ 13-21 m; chord-1 p50
  9.02 / p90 14.06 / max 18.43 m.  **The owner drew IDEALISED
  straight runs through a spine that MEANDERS around them — the
  margin is the meander scale (~15-20 m), NOT the map's internal
  straightness (≤ 0.06 m, a different quantity ~250× tighter) and
  NOT spine jitter.**  MEMBERSHIP IS THREE TESTS — margin alone
  would claim crosser junction-approaches: (i) within margin of
  the chord; (ii) authored local direction aligned with the run at
  the census-validated 15° window (a ROUTE filter — expressly NOT
  the retired pairwise join-admission); (iii) path-connected along
  spine edges.  All from measured primitives.
  **EPITAPH CORRECTION (honest record):** the earlier "recognition
  was never load-bearing (flat 0-5 m)" claim is WITHDRAWN as
  UNDER-RANGED — the sweep sat in the bottom quarter of the real
  distribution (0.5 % coverage at 0.5 m → 23.4 % at 5 m).  The
  pairwise design's death rests on the owner's construction rule +
  the 305-vs-40 count, which no tolerance explains.  A 5-20 m
  re-sweep is ruled NOT OWED: it would calibrate a quantity that
  no longer exists in the run-based design.
  **Anomaly batch to the owner — ONE question, 8 ways:** the 5
  offset anomalies (585.6/466.7/217.4/164.3/20.2 m) + 3 p50-level
  strings (-39402 78.3, -39345 68.6, -39338 40.2 — a different
  population, excluded from calibration).  Expected-count gate:
  **46 ± the 8 pending**.  DEAD INSTRUMENTS recorded (register 21):
  emitted polygon nodes (saturate at pavement half-width) and
  nearest-string assignment (admits unmapped taxiways) — spine
  nodes vs owner strings is the only valid population.
* S1's substrate CARRIES (spine polylines, authorship, purity,
  witnesses, defect discipline); the merge/recognition layer drops.
* **THE SELECTION RULE + THE ROUTE TIER (owner 2026-07-31,
  verbatim: "So wherever there's a parallel taxiway to a runway,
  there's a single straight string from one end to the other, same
  for cross connecting taxiways, etc...") — ONE TAXI ROUTE ⇒ ONE
  STRING.**  The aggregation tier already exists:
  `RouteChain` (grade_graph.py:193, "a WHOLE taxi route… parent of
  bend-split `Centerline` pieces") → `Centerline.route_idx` (:157)
  → nodes.  The run construction has been seeding at the PIECE tier
  (645 `centerline_chains`) while the owner's strings live at the
  ROUTE tier — the mechanism that explains, at once, the stub-scale
  excess (~28 m ≈ bend-split piece scale), the 154-vs-811 m mean
  ratio, and the tolerance-insensitivity (no margin merges pieces
  back into routes the assembly was never told exist).
  **RULED CONDITIONALLY — design now, commit on the count:** seed
  from `GradeContext.routes` via `route_idx` IF the HECA RouteChain
  count (phase-1 check, zero HECA, directed) lands in the
  PRE-REGISTERED acceptance class: within ~1-2× of 46 (turning
  routes lawfully yield several straight runs, so above-46 is
  expected; exact-46 is NOT demanded — proxy-gate discipline).
  **THE SELECTION FRAME IS RETIRED — FALSIFIED BY SOURCE (owner
  2026-07-31, verbatim: "I drew almost every straight run, maybe
  skipping a couple that were under 100m"):** the map is
  NEAR-EXHAUSTIVE, so the ~240 excess runs are SPURIOUS
  over-fragmentation — not undrawn selections; readings (a)
  structural and (c) target-field-need die as count-gap
  explanations (the strings-are-targets model stands; it just never
  explained the count).  The **8 in-map anomalies are a SEPARATE
  quality track** (drawn-but-possibly-mis-drawn, inside the 46) —
  never count tolerance.
  **ROUTE-TIER CHECK: FAILED — pivot DEAD (measured, zero HECA):**
  `RouteChain` is 1:1 with `Centerline` at HECA (658 = 658; pieces
  per route max 1; chord-1's 75 pieces → 75 distinct routes) —
  seeding from `GradeContext.routes` would reproduce the identical
  partition.  Seeding STAYS at the piece tier; **the RUN
  CONSTRUCTION IS the aggregator** (it already assembles chord 1 as
  one run across 22+ pieces) — no upstream aggregation is built;
  the splitter-1:1-vs-source-shape question is NOTED, NOT PURSUED
  (moot under the threshold ruling; the tier exists if a future
  airport shows multi-piece routes).
  **THE OWNER'S THRESHOLD (2026-07-31, verbatim: "Agreed, strings
  under 100m are probably not very useful, and we primarily want
  the very high level straight routes, there should not be more
  than 50 at HECA") — RULED A SELECTION RULE, NOT CONSTRUCTION:**
  extraction mints maximal runs UNFILTERED (the inventory is
  MEASUREMENT — drop diagnostics need the runs to exist;
  maximality grows a run before its length is known); STRING DUTY
  (target minting, hook rewrite, rod sourcing, the count gate)
  requires **`TAUT_STRING_MIN_LENGTH_M = 100.0` — OWNER-SUPPLIED;
  never recalibrated by us, only he moves it.**  Sub-threshold
  runs are recorded, not stringed; their nodes are NON-STRING
  SPINE — today unchanged (no hook rewrite, exactly like all
  unclaimed nodes); at S1b they take DRAW-TOWARD targets from the
  string web (the model's standing answer for connector nodes).
  **Count gates: hard ≤ 50 (owner's bound); expected class 46-49
  inside it.**  [Status, the 46-way re-seat, and the pre-registered
  decision rule: see COUNT GATE in the acceptance-measurement
  rulings, 2026-07-31.]  Drop-distribution rider: a smooth continuum
  through 100 m is a finding about OUR runs, never a licence to
  move HIS threshold.
  **FILTER MEASURED (2026-07-31, zero build): 286 → 69 surviving
  (≤ 50: FAIL as stated); dropped 217.  The untargeted result that
  matters: surviving total 37,543 m vs the owner's 37,327 m —
  0.6 % — correct geometry, split too fine.  Chord 1 untouched
  (89.8 %).  The rider is ANSWERED: a GENUINE VALLEY (144 runs at
  25-50 m, then 4/2/2 across 50-125 m — bend-split debris as a
  distinct mass; the threshold is robust anywhere ~60-130 m: the
  ideal state for an owner constant — corroborated, not merely
  applied).**
  **ACCEPTANCE RESTATED (three-part; the count corrected, never
  softened — fragmentation is the PEG MECHANISM: every fragment
  boundary is two endpoint datums, P3's 59-peg class and class D at
  scale; few-and-long is the mechanism of the owner's ≤ 50):**
  (i) LENGTH AGREEMENT — surviving total within ~2 % of the
  owner's; (ii) COVERAGE — chord-1 end-to-end class + per-string
  coverage via the map; (iii) COUNT ≤ 50, compared against the
  CORRECTED owner count (the 5 real-offset anomalies are 2-3
  strings each under his own definition ⇒ ~51-56 expected; the
  anomaly track FEEDS the count gate — the earlier independence
  claim is corrected).  **Directed, one instrument:** the
  SURVIVOR-TO-OWNER-STRING CORRESPONDENCE TABLE (which of the 69
  cover which of his ways; per-internal-boundary stop reason —
  margin / align / continuity / spine end) — delivers the corrected
  comparison, the ~19-excess attribution, wrong-merge/wrong-split,
  and the ~375 m chord-1 gap in context, in one zero-build
  artifact.  The SPLITTER QUESTION IS RE-OPENED, bounded (the
  earlier "moot" was premised on the filter closing the count — it
  did not): a CODE-READING answer only — does the route builder
  emit 1:1 by construction, or is the source 1:1? — blast first,
  no redesign; the near-term fix lives in run stop-conditions
  either way.
  **THE CORRESPONDENCE TABLE (2026-07-31, zero builds) — THE BARE
  COUNT WAS HIDING A CANCELLATION:** matched 37/69 ours, 30/46 his;
  **wrong-merge ZERO** ({1:37} — the construction has never
  over-merged at HECA: that suspicion class is RETIRED);
  wrong-split 7 excess ({1:25, 2:4, 4:1}); dominant classes **32
  unmatched-OURS vs 16 unmatched-HIS — opposite-direction defects
  partially cancelling in the aggregate** (7+32 attributed vs 23
  visible, reconciled by the 16).  Register 23: gates may be
  aggregates; DIAGNOSIS never is.
  **Chord-1's 375 m ATTRIBUTED — a WRONG-SPLIT at along ≈ 368:**
  head = a 179.3 m orphan (178.7→358.0) + a ~20 m break
  (358→378) + the 3,599.6 m body (377.6→3,977.1, complete to the
  far end).  Not a coverage failure.  The margin hypothesis is
  PRE-EMPTIVELY KILLED by the existing sweep (coverage identical
  across margins 15-30 — widening would have closed it); no cycles
  there.  DIRECTED (one line): name the ≈ 368 boundary's stop
  reason from the table's per-boundary instrument.
  **THE GEOMETRY-PARTITION TEST — directed as the PRIORITY
  zero-build item, with MANDATORY STEP 0:** publish the MATCH RULE
  and CROSS-MATCH the 32 against the 16 under a looser
  correspondence FIRST — a too-strict rule manufactures
  same-geometry pairs counted once in each unmatched column
  (register 21 applied to the matching criterion; the cheapest kill
  of the different-geometry inference, run before any
  classification).  STEP 1, only for survivors of step 0: bucket
  OURS by substrate (near-owner-but-unmatched / non-route classes —
  apron-, runway-adjacent, stubs) and HIS by three decisive
  possibilities — spine + runs dropped sub-100 / spine + no run
  minted (membership) / **NO SPINE under his line (a SOURCE-DATA
  coverage finding, not a construction defect)**.  The buckets
  decide the fix locus: match rule vs membership vs
  stop-conditions vs source data.  The splitter code-read queues
  BEHIND this test.
  **STEP 0 RUN (2026-07-31): THE INFERENCE SURVIVES** — loosened on
  all three axes at once (overlap ≥ 0.20 / lateral ≤ 40 / angle
  ≤ 30°), only 3 pairs recovered; ~90 % of both columns stand.
  BASELINE CORRECTED: **31/15, never 32/16** (S1's fifth
  self-catch: step 0's lateral used `min` where the table used
  `max`).  Binding over-strictness = the LATERAL gate (two
  recoveries at 33-34 m, 1.0°/14.3°, excellent overlap) — NOT the
  overlap asymmetry flagged as most suspect (measurement over
  intuition, again).  S1-15 (502 vs 220 m) re-classed to
  WRONG-SPLIT, not "recovered" — bookkeeping: matched 37 → 38,
  wrong-split 7 → 8, columns 28/12.  No rule change (the fourth
  fit-the-rule refusal — endorsed).
  **STEP 1 REFINED (budget ruling): two CHEAP DECISIVE FILTERS run
  NOW; the full substrate bucketing HOLDS for the owner's
  tagged-file verdict** (ground truth for is-it-a-real-route; it
  CANNOT answer why our construction produced a run): (a) the
  **PARALLEL-NEIGHBOUR SCAN** — S1-09's signature (~30-40 m
  lateral, near-zero angle, high overlap; 34 m ≈ a taxiway width)
  over the existing correspondence metrics — a named sub-class
  ("building the neighbour", a membership defect with a findable
  cause) that must not be absorbed into "different geometry"; a
  good-tag does not exclude it, a bad-tag still needs its
  mechanism; (b) the **SPINE-EXISTENCE CHECK** on his 12 —
  no-spine-under-his-line is a SOURCE-DATA coverage finding about
  OUR data, kept strictly distinct from no-run-minted; his verdict
  cannot supersede it.
  **STEP 1 MEASURED (2026-07-31; ALL COUNTS ±2 — sixth self-catch:
  the lateral definition was unspecified by DIRECTION; qualitative
  findings robust, no figure quoted precise; DIRECTED: pin ONE
  canonical lateral definition, record it, re-emit the table
  once):** HIS column — **(c) NO SPINE under his line = 8 of 16**
  (five with ~zero spine along their entire length); (b) spine
  present at 96-100 % coverage, NO RUN MINTED = 6 (genuine
  construction misses, OURS); (a) minted-then-dropped-sub-100 = 2
  (29/18 m fragments of his real strings — the fragmentation
  family).  **CHORD-1's ≈ 368 ATTRIBUTED: ZERO spine edges between
  the orphan and the main run — a CONNECTIVITY HOLE IN THE SPINE
  GRAPH** — the membership line for the 375 m is RETIRED, and the
  hole independently explains every tolerance-insensitive sweep.
  **REFUTED 2026-07-31 (P7 step 0, raw-spine measurement): the raw
  spine under the owner's chord is FULLY covered — one component, a
  19-node path through the 375 m region at max lateral 2.7 m.  The
  "hole" was a property of the RUN-MEMBERSHIP population (~362 of
  652 corridor nodes), not the spine; MEMBERSHIP IS BACK ON THE
  TABLE for the 375 m.**  Instruments directed (zero-build): the
  settling test (shortest-path the two run node-sets through
  `spine_adj`, listing excluded intermediates with the predicate
  each failed — closes the assemble_runs-era attribution) and the
  WALK-CLAIM CENSUS (what does `walk_spine_runs` claim over the
  same corridor — the forward question; a heal closes the miss as
  construction-specific, a stop implicates M-new: the 0.05 m
  interning key vs the 0.86 m endpoint near-miss ⇒ no shared node
  ⇒ no inter-chain edge, per the code-read's 669-intra/0-inter
  measurement).
  Parallel-neighbour: 3 of 33 (real, a tenth); the remaining 30
  await the owner's verdict.  **RULINGS:** the SPINE-COVERAGE
  defect is NAMED and tracked UPSTREAM (plan; grade_graph domain,
  above this spec's brief; step 0 = source-presence under the 8
  lines in OUR inputs before any attribution).  S1's
  constructor-scoped remainder is exactly TWO items — attribute
  (b)'s 6, fold (a)'s 2 into the wrong-split family; constructor
  iteration otherwise HOLDS.
  **(b) ATTRIBUTED AND DISSOLVED (2026-07-31, S1's final
  substantive result): NONE of the six is a build failure** — every
  spine node under them is CLAIMED by minted runs (surv/drop, never
  unclaimed).  Mechanisms: correspondence-rule NEAR-MISSES (two
  ~266 m ways 100 %-claimed by single survivors failing the
  0.5/25 m test), TRANSVERSE claims (long runs crossing his short
  string), SHARED-WITH-DROPS — (b) < 6 and overlaps (a).  The
  FRAGMENTATION family is ~6, not 2.  Seventh refusal endorsed: no
  re-bucketing into an unpinned taxonomy; the owner's
  way-id-plus-reason verdict supersedes exactly this inference.
  **HEADLINE: the constructor has NO CONFIRMED BUILD FAILURES** —
  residual mass = substrate (P7) + whatever the owner rejects from
  the 30 (the "confirmed" boundary marked: transverse cases carry a
  direction-selection question at specific sites, deliberately not
  reopened).  **CANONICAL TABLE PINNED: lateral = max perpendicular
  distance of OUR two endpoints from HIS chord — 32/16 under this
  definition or not at all** (supersedes 31/15 and 33/16; that the
  canonical definition restores the ORIGINAL figures is the lesson:
  the number was never the problem, the unpinned definition was).
  The (c)-density signal routes to P7 (density profiles, not
  binary; the ≈ 368 hole joins the same instrument).  S1 HOLDING as
  directed; 29 tests green.

**THE OWNER'S VERDICT (2026-07-31) — THE SINGLE DEFECT AND THE
SPINE-WALK (the third reframe: pairwise → run-based →
spine-following; S1 UN-HELD for exactly this work):** verbatim —
S1-06 "cuts through open terrain… two straight segments with an
almost 45 degree bend at the middle, needs two strings"; S1-12
"the two end points are on the spine of two different taxi ways…
connecting across unpaved area with no spine… should be two
separate spines connecting to the runway (like my example)"; S1-35
"same pattern… strings must generally be within a few meters of a
spine"; S1-09 "right size and shape, but shifted too far from its
spine"; "pretty much all the others follow the same pattern… they
must follow the spine and stop when the spine turns, leave the
curve with no string, and for segments greater than 100m emit a new
string along the spine."
**THE CONSTRUCTION (ruled — the synthesis, smaller than it looks):
chord-growing CONSTRAINED TO THE WALKED SPINE PATH.**  The
run-based chord core survives; the DOMAIN changes: candidates are
the next nodes along the walk, never spine-within-margin-of-a-chord
in the plane.  Grow the segment's chord along the walk; spine
departing the chord beyond the (re-calibrated) few-metre bound ends
the segment; SUSTAINED departure = curve = NO string; a new segment
starts where the spine straightens; the walk stops at (a) a spine
TURN, (b) a spine GAP (P7's holes — you cannot follow what is not
there), (c) route end.  **Open-terrain crossing is UNREPRESENTABLE
by construction** — the rule's built-in acceptance property.  The
≥ 100 m threshold becomes the walk's EMISSION rule (selection
layering preserved: sub-100 segments recorded as inventory;
string duty at ≥ 100).  **The margin TRANSFORMS: admission radius →
VALIDATION bound** (the emitted string lies within a few metres of
the spine it was walked from).  Identity ≠ membership ≠ bridging
survives — walking never bridges.
**THE 20 m MARGIN IS SUSPECT — CONTAMINATION RE-MEASURE DIRECTED,
OUTCOME PRE-REGISTERED:** recompute owner-string-to-spine distances
EXCLUDING absent/sparse stations (sharing P7's density profiles —
one instrument, two consumers).  If the clean distribution
collapses to a few metres: **20 m is REFUTED with its cause named —
register 21's FIFTH strike, the shipped-constant edition** (the
calibration population contained the very spine holes the sibling
track was investigating; the corollary: a calibration population
must be checked for the defect class under investigation; the
ratification was Fable's).  The walk's bound calibrates from the
CLEAN population against the owner's "few meters"; no constant
re-derives before that.
**SUPERSEDED BY OWNER RULING (2026-07-31): the margin is
OWNER-SUPPLIED at ±5 m** — `TAUT_STRING_SPINE_TOLERANCE_M = 5.0`,
one constant, two jobs (simplification band + string-vs-spine
validation), source verbatim in the model spec, only he moves it.
`TAUT_STRING_RUN_MARGIN_M = 20.0` RETIRES; its epitaph completes
when the contamination re-measure names the CAUSE (the re-measure
DOWNGRADES to explanatory — still run; the fifth strike keeps its
lesson).  `SPINE_PERP_TOL_M = 1.0` sits consistently inside ±5 m.
**`bound_m` remains UNWIRED pending the SUBSTRATE ruling** (model
spec): the walk's MECHANISM survives (chord-growing,
emergent-curve discard, direction-symmetric consensus — validated
33/34); the INPUT TIER conditionally moves to the RAW route
network (apt.dat 1201/1202 + OSM linear per the per-consumer D1
ruling — strings are never clipped, so the May ruling's failure
mode does not apply to them), COMMITTED only when P7's raw-network
characterization shows per-route polylines covering the owner's
string-inventory class.  If committed, the processed-tier artifact
classes dissolve (interning near-miss inter-chain edges; the
density/endpoint saga; plausibly bend-split fragmentation) and the
flagged 0.05-vs-0.5 interning question moots.  Surviving
regardless: ±5 m, ≥100 m, direction symmetry, selection layering,
(ii-b) datums, identity ≠ membership ≠ bridging.

**COMMITTED (2026-07-31; the characterization met the gate beyond
its terms — 161/196 raw pieces are already two-point straights;
the fragmentation is manufactured at `route_arcs.py:556-564`):**
* **Substrate = the S2 snapshot** (196 pieces, `pipeline.py:2253`)
  ∪ OSM linear taxiways per D1, **apt.dat-first dedup** (an OSM way
  within the tolerance corridor of an S2 piece yields; OSM stands
  where apt.dat is absent — the 8 D1 lines, where the tolerance
  governs string-vs-its-own-source-polyline).  [GRANULARITY RULED
  2026-07-31: SUBSEGMENT — "where" is locative, per-location never
  per-way; see THE ACCEPTANCE-MEASUREMENT RULINGS below.]  The walk runs on
  this substrate; **`bound_m` WIRES at the owner's 8.0**
  (`TAUT_STRING_SPINE_TOLERANCE_M = 8.0` — owner ruling
  2026-07-31, superseding 5.0; the union owner-approved verbatim:
  "+/- 8m is acceptable, and the union is fine").
  **ACCEPTANCE RESTATED IN THE OWNER'S TERMS (his goal: "majority
  coverage for long straight sections so we can smooth them to our
  string… We don't need 100% coverage"):** GATE A —
  length-weighted MAJORITY coverage of the map at ±8 m (measured
  state 95.6 % length-weighted; 12/12 of his ≥ 1000 m strings);
  GATE B — chord 1 end-to-end; GATE C — W-CHORD1/W-CHORD2
  (unchanged — smoothing long straights to the string IS the
  elevation goal); ≤ 50 inventory sanity bound.  Count-matching,
  the 69-vs-46 chase, and correspondence equality DEMOTE to
  diagnostics; the 8-anomaly answer demotes to denominator
  hygiene.  **DIRECTED: S1 runs the acceptance measurement ITSELF
  against these gates (zero-build)** — the quoted numbers came
  from P7's characterization instruments, and acceptance is
  measured by the acceptance instrument (register 21).
* **`_collapse_straight_edges` is NOT revived** — the walk IS the
  primitive, validated; reviving dead code with a different
  constant (2.5 m) to do one job twice is the U1 anti-pattern.
  The dead family (`synthesize_spine` and its six helpers, live
  only via an attic tool) is PRIOR ART — corroboration of the
  design direction — with a register-16 obligation: harvest its
  ★/warning comments before any future attic deletion.
* **Closed as superseded:** the walk-claim census and the settling
  test (the mechanism was found at source, below the tier they
  interrogate); the processed-tier fixture concerns re-key — the
  real-geometry fixtures re-freeze from the S2 substrate (the
  competition and density clauses still bind; the map is still the
  answer key).  Stage-1 re-acceptance returns to the FULL map
  (S2 ∪ OSM covers the 8 lines; the spine-reachable scoping was a
  processed-tier accommodation).
**NAMED FIXTURE CASES:** S1-06 (the ~45° two-string turn cut);
S1-09 (the shifted-run validation bound); S1-12 (structural
CONFIRMATION, not new machinery — "two separate strings connecting
to the runway, like my example" is the chord-2 pattern and the
(ii-b) datum-flow reading from the source).  P7 SEQUENCING: holes
are now a HARD constructor blocker under follow-the-spine — P7
step 0 joins the construction fork's critical path; the walk's
design/implementation/synthetic tests proceed IN PARALLEL
(spine-reachable acceptance scoping doubly justified).

**THE CURVE-EXIT RULING (2026-07-31; S1's queued deviation —
`walk_spine_runs` landed with 33/34 green and open-terrain crossing
VERIFIED UNREPRESENTABLE; the failing curve test was a REAL gap in
ruling 2, owned):** "sustained" and "straightens" were written as if
primitives; they are defined nowhere and **they are EMERGENT** —
the owner's own sentence contains the machinery:
* a segment ends at its FIRST bound-departure; the next segment
  starts AT the ending node (walk continuity, no node skipped);
* a spine still curving kills successive segments SHORT, and the
  ≥ 100 m emission rule discards them to the inventory — the curve
  gets no string with NO curve-detection criterion and NO new
  constant; a curve that never leaves the bound IS straight at the
  resolution the owner cares about;
* **DIRECTION SYMMETRY (the actual fix — parameter-free):** an
  emitted (≥ 100 m) string must be reproducible growing from EITHER
  end; implementation = re-grow the chord backward from the far end
  and emit the forward/backward CONSENSUS.  The measured defect
  (curve-tail nodes absorbed into the following long segment) is a
  forward-only-growth artifact: a backward chord anchored deep in
  the straight departs the curve early, so the tail falls out.
  Same bound, same 100 m, zero new constants — maximality was
  always direction-independent.
* Pre-registered on the curve fixture: consensus leaves the curve's
  beyond-bound nodes UNSTRUNG while both flanking straights emit
  full strings.  The failing test IS this ruling's fixture; S1-06
  unblocks as its sharp 45° instance.
* Wiring constants: `min_len_m` DEFAULTS to the owner's
  `TAUT_STRING_MIN_LENGTH_M` (his constant, already landed);
  `bound_m` stays REQUIRED-EXPLICIT with no default until the
  contamination re-measure lands — a default now would repeat the
  shipped-constant trap while its predecessor is under
  investigation.  `assemble_runs` remains present and additive
  until the walk passes acceptance; its retirement is a later
  measured step, never a silent deletion.

**THE FIXTURE-PREMISE RULING (2026-07-31; direction symmetry landed
33/34 parameter-free — the one failure was Fable's own designated
fixture asserting the premise the ruling overturned):**
* **(b) REJECTED BY NAME:** aggressive arc-node exclusion is the
  straightening test resurrected under a new job title.
* **(a) ADOPTED AND MADE RIGOROUS — the fixture asserts the RULED
  criterion, not a geometric intuition:** (i) the fixture
  CONSTRUCTS its "sustained" region decisively beyond bound (apex
  ≥ 2× `bound_m` from any candidate chord) — "sustained" needs no
  detector when the fixture author places it beyond the criterion
  by construction; (ii) assertions are the ruled INVARIANTS: count
  == 2; **every strung node within `bound_m` of its own string's
  chord** (the validation bound asserted directly); the
  constructed beyond-bound region UNSTRUNG.  Nothing asserts about
  "arc nodes" as a class.  (iii) **Sub-bound entry nodes may belong
  to either flanking string, explicitly** — the owner's strings are
  idealized two-node objects; node-level membership at transitions
  is OUR construction detail within his tolerance, and fixtures
  must not legislate it.
* **S1-06 unblocks with the same assertion shape** (two strings per
  the verdict, extents keyed to his map's segments, validation
  bound, beyond-bound neighbourhood unstrung, transition membership
  free); S1-09/S1-12 behind.
* Recorded: the one-directional-adjacency FIXTURE BUG (duplicate-key
  dict comprehension; every backward step read as a spine gap) that
  DIRECTION SYMMETRY EXPOSED — a stricter construction surfacing a
  latent fixture defect the looser one silently tolerated
  (registers 9/13 paying in reverse); the walk was correct
  throughout; ★-noted at the fixed helper because the failure mode
  (empty walk) points nowhere near the cause.  **ACCEPTANCE RE-SCOPED (the
  impossible-gate lesson): stage-1 re-acceptance measures the
  constructor against the SPINE-REACHABLE subset of the map until
  the upstream track lands; the full-map acceptance is the JOINT
  gate of both tracks.**  At route tier: the TURN CUT
  REDUCES to margin failure (offset from the end-to-end chord
  accumulates through any turn); bend-split piece boundaries are
  NEVER re-used as turn information (the owner's multi-node
  dead-straight strings showed authored vertices ≠ turns);
  membership's three tests carry with test (ii) EXPECTED INERT at
  route tier (no crossers within one route) — deleted only on
  MEASURED inertness (the #21 precedent).  The ~375 m chord-1
  extent attribution re-sequences AFTER the seed pivot (one
  attribution against the final construction — single-pass).
* **THE MEASURED EPITAPHS (2026-07-31, the pairwise calibration
  negative — zero builds, nothing tuned; it independently confirms
  the run-based pivot from measurement while the owner's definition
  confirmed it from the source):** with the pairwise 6.0° gate +
  recognition tolerance swept 0 → 5 m: strings 305 → 327 (wrong
  direction, never approaching the map's count) and chord-1
  coverage FLAT at 58.5 % — **the recognition tolerance was never
  load-bearing** (the 0.86 m gap was recognized and the pairwise
  admission then rejected the candidate), and the pairwise gate is
  the over-assembly's author.  Mechanism, now spec text: 36
  authored fragments tile a 0.00°-bend / 0.06 m-offset string ⇒
  FRAGMENT JOINS CARRY NOISE THE RUN DOES NOT — a pairwise gate
  measures fillet noise at authorship scale (the piece-scale
  failure, one level up).  `TAUT_STRING_TURN_DEG` and
  `TAUT_STRING_MEMBER_NEAR_MISS_M` retire with their derivations
  intact; the ★ identity ≠ membership ≠ bridging comment SURVIVES
  (membership changed its TEST, not its place).  CONFIRMING
  MEASUREMENT directed (zero-build, on the capture): chord-1's 36
  pairwise join deviations vs the accumulated run's own-chord
  offset — expected joins > 6° while the run holds ≤ margin; the
  recorded WHY for S1-CP2.
* **Fallback**: spine edges with NO authoring centerline (synthetic
  connectors, discovered taxiways) stay their own pieces; level-2
  continuation may attach them; their count is reported.
* **Interior piece endpoints — the pegs — dissolve into ordinary
  stations** (unchanged intent); clause-1 anchors keep their role.
* `_build_spine_corridors` itself is **NOT modified** (unchanged).

**Mechanism-before-wiring gate — part (i) MEASURED AND RULED PASSED
2026-07-31 (census at `/tmp/s1/heca_authorship.pkl`; phase-1 layout;
S1 stopped at the literal condition and Fable ruled — correctly on
both sides):** chord 1 is authored by 75 chains (best single 678 m /
17 % by metres — the "one or a few" expectation FAILED), but the
**36 chains within 15° of the chord bearing tile it end-to-end:
3,806 of 3,968 m (95.9 %) with median AND max consecutive gap
0.0 m** across 33 junctions; the 39 crossers sit cleanly outside the
window (median 27.8°).  The original condition was a COUNT PROXY for
the real property — bridgeless concatenability — and the proxy
failed while the property held (the same error class as the
piece-level heading proxy, one level up; owned by Fable).

**The gate, restated in the property's own terms (normative):**
level-1+2 assembly proceeds for a trunk when the census shows
(a) authored chains collinear to the trunk within the level-2
window, (b) tiling it at ≥ 95 % METRE coverage, (c) with
ZERO-LENGTH gaps (shared-node junctions) — any positive-length gap
is a STOP for Fable, never a heuristic bridge.
**ZERO-LENGTH DEFINED (ruling 2026-07-31, after register 15's
falsification): two fragment endpoints are THE SAME endpoint iff
they resolve to the same CANONICAL-POINT REGISTRY ID** — the 0.5 m
interning every weld, carry and U1 artifact already keys on; the
pipeline's one identity, not a new tolerance.  This SHARPENS the
gate: the sharing test compares canonical IDs, never per-run
indices or raw coordinates.  **No chaining rule beyond canonical
identity exists.**  Arm-2 instrumentation (approved): per
non-chaining adjacent pair, both endpoints' canonical resolutions +
metric separation, classed (α) canonically identical, compared
wrongly → implementation fix; (β) distinct within 0.5 m →
registry-interning question, report; (γ) real gap > 0.5 m → STOP
for Fable (plausibly the walk dropping junction nodes at build
density — a grade_graph question).  Plus per-string-end stop
reason (no incident fragment vs deviation-rejected, with best
deviation).  The histogram decides; no fix before it exists.
**PART (ii)'s PASS IS DEMOTED to phase-1 scope (third proxy in the
lineage: piece headings → count proxy → phase-1 endpoint sharing
standing in for build-density sharing): bridgeless concatenability
is UNVERIFIED at build density** (build assembled 22 fragments max
vs the fixture's 36).  The §6 gate's evidence basis is arm 2's
build-density measurement + the re-based fixture (endpoint-sharing
structure preserved, terminal-segment negative control
re-established; re-base still AFTER attribution).  **Metre extents are
gate currency; node-count percentages never are** (density-dependent
across phase-1 vs full layouts — S1's caveat, adopted).  Level 2's
heading is the WHOLE-FRAGMENT bearing (capped at a window length),
not a fixed-metre window — the median fragment is 37 m and whole-
fragment bearing is what the census validated at 15°.

**Part (ii) — DEMONSTRATED AND PASSED 2026-07-31 (zero builds):**
chord 1 assembles into ONE string — 36 fragments, 293 nodes,
along-span 1 → 3,966 m = 99.9 % of the chord, **0 of 463 chord spine
nodes orphaned** (both sides of the §6 gate).  Node-level
concatenability confirmed: 38 corridor vertices are shared endpoints
of ≥ 2 fragments.  **The window IS the mechanism, interventionally:**
terminal-segment heading (window 0) reaches 59.8 %; whole-fragment
bearing at the 37 m window reaches 99.9 %; thresholds 10°/15°/20°
produce byte-identical assemblies — the threshold is not doing the
work.  `TAUT_STRING_HEADING_WINDOW_M = 37.0` (config.py, the
measured median fragment extent; S1-CP2 reviews it with the
inventory).
**Gate-currency ruling (the polyline honesty flag, answered):**
COVERAGE reads ALONG-SPAN (the gate protects end-to-end trunk span);
STATIONS AND CAP BUDGETS read POLYLINE arc-length (the law follows
the path an aircraft taxis — a cap over the real 4,281 m path is the
lawful budget, not a bonus).  Two quantities, two jobs; the
polyline-vs-along excess (+316 m / 8 % here — an ASSEMBLY-ERA figure;
walk-era 0.14 %, see the gate-currency correction below — lateral
wiggle inside the corridor) is REPORTED per trunk in the assembly
inventory.
**API ratification (Fable):** `assemble_maximal_strings` gains
keyword-only `window_m: float = 0.0` — the mechanism must be
expressible and the necessity test must vary it; config-reads inside
the pure constructor are rejected.  The 0.0 default exists for
semantics fixtures; PRODUCTION call sites pass
`TAUT_STRING_HEADING_WINDOW_M` explicitly, never the default.  The unauthored-edge fallback STAYS for other
airports; HECA's 0/5,085 unauthored pairs is recorded as a MEASURED
zero.  Build-time for the export: MEASURED 0.080 ms (6,657
incidences; ~75× under the 1 % review line) — condition discharged.

**THE ACCEPTANCE-MEASUREMENT RULINGS (2026-07-31 — S1 ran the directed
zero-build acceptance and STOPPED at two unruled points instead of
improvising; correct on both.  Evidence record: substrate reproduction
VERIFIED (196 pieces / 151 routes / 46,145.1 m, exact match to the
committed figures, 0.07 s); GATE A PASS — 87.1 % dedup-way / 84.4 %
dedup-subseg length-weighted at ±8 m over 46 owner ways / 41,412.7 m /
8,305 stations; ≥1000 m subset 89.8 / 90.2 %, 11 of 12 ways
individually majority-covered; residual 67 % concentrated on P7's 8
known no-spine lines; definition sensitivity ≤ 1.0 pp (chord-vs-node
87.1→88.1; piece-vs-route 87.1→87.9) — not load-bearing.  GATE B FAIL —
best single string 93.0 % (dedup-way) / 18.5 % (dedup-subseg) of owner
way −39330, while the UNION covers 100 % of its stations.  Inventory
FAIL — 194 / 142 strings vs ≤ 50; metres 71,092 / 41,819 vs the
owner's 41,412.7.  Two later instruments arrived mid-ruling and are
part of this record: the unit fixture's delete-not-split (one 110 m
spine: ONE authored chain ⇒ `strings=[110.0]`; TWO chains of 50+60 m
sharing a node ⇒ `strings=[]`, both runs sub-min — deleted, not
fragmented) and the wired production driver's inventory (645
non-service processed-tier chains ⇒ 107 strings, longest 1,412.7 m,
711 sub-100 m runs holding 20,013.5 m = 39 % of walked metres with no
string duty).**

* **RULING 1 — DEDUP GRANULARITY: SUBSEGMENT.**  The committed
  sentence is LOCATIVE — "OSM stands WHERE apt.dat is absent" names
  locations, not way ids.  At HECA 275 of 282 standing ways are
  PARTIALLY inside the corridor, so way-granularity turns the clause
  against itself: OSM would stand where apt.dat is PRESENT for 75 %
  of emitted metres — a dedup leaving 75 % duplication fails the
  purpose named in its own title (apt.dat-FIRST: apt.dat wins
  wherever both exist).  The "8 D1 lines" parenthetical was
  DESCRIPTIVE of an expected clean partition, written before partial
  overlap was measured; the granularity question was never considered
  when the sentence was written — owned, same class as the
  fallback-granularity revision above.  Convergents: dedup-subseg
  inventory metres 41,819 = 101 % of the owner's 41,412.7 (inside the
  ~2 % length diagnostic); dedup-way 71,092 (+72 %); duplication 4 %
  vs 75 %.  The chord-1 regression under subseg (93.0 → 18.5 % best
  single) is NOT evidence for way granularity: it is the chain
  boundary (Ruling 2), attributed interventionally; way granularity
  "wins" chord 1 only by keeping a duplicated OSM way as a SECOND
  AUTHORITY over apt.dat's own pavement — the right number carried by
  the wrong mechanism (register 6).  MECHANICS: membership is
  per-station against the piece corridor at the owner's 8.0 m,
  materialized as maximal runs; a run shorter than the tolerance
  (8.0 m along-way) is ABSORBED into its surrounding state
  (anti-chatter at the corridor boundary — derived from the owner's
  constant, no new number).  Every dedup cut MINTS A SEAM JOINT to
  the covering piece — recorded continuity the source way itself
  asserted; recognition, not bridging (the near-miss precedent:
  moves no geometry, mints no identity).  A joint sits within the
  tolerance of the cut by construction; no second constant.
* **RULING 2 — THE CHAIN DOMAIN: MAXIMAL THROUGH-PATHS.  AUTHORING
  BOUNDARIES ARE NOT CHAIN BOUNDARIES.**  This is RESTORATION of
  committed law at the one named seam, not new law and NOT an owner
  intent question: "a JUNCTION is not a turn — chord 1 runs straight
  through 33; an AUTHORED GEOMETRY BREAK is not a turn", and
  "level-2's merge and the turn cut are ONE criterion from two
  sides: merge across a junction iff NOT a turn" are already
  normative (model spec §segmentation refinement, ratified from the
  owner's own map).  His object crosses chain boundaries by
  construction — no authored chain spans chord 1 (census: best
  single authored chain 678 m / 17 %; route-tier walk caps the best
  string at 1,450.0 m vs his 3,981.4 m way) — so a chain-bounded
  domain contradicts "chord 1 = ONE string" outright, and GATE B is
  satisfiable ONLY by junction-crossing chains.  "Authorship is
  membership" binds nodes to the NETWORK (`on_line`), never strings
  to chain ids.  The fixture agent's reading — "the owner's rule is
  stop when the spine TURNS, not stop at an authored chain
  boundary" — is confirmed as exactly the committed law.  THE LAW,
  all of it at `spine_walk_chains` (the ★ seam; no driver surgery):
  1. Chains handed to the walk are MAXIMAL THROUGH-PATHS in the
     Ruling-1 substrate graph (S2 pieces ∪ standing-OSM
     subsegments).  Chains PARTITION substrate edges — every edge in
     exactly one chain; no duplication, no omission.
  2. NOT chain boundaries: piece ids, route ids, junction degree,
     authored geometry breaks, dedup cut seams (via their joints),
     tier boundaries.  The ONLY string boundaries remain the walk's:
     bound-departure at the owner's 8.0, spine end, and the ≥ 100 m
     selection — unchanged.
  3. COMPOSITION IS PERMISSIVE AND PARAMETER-FREE: at each junction
     node, pair incident edge-ends GLOBALLY by ascending bearing
     discontinuity — best pair first, each end at most once, ties by
     stable id.  No threshold: `TAUT_STRING_TURN_DEG` stays retired;
     a geometrically bad pairing is harmless by construction because
     the walk cuts it (a turn is a turn wherever it sits in a
     chain).  [CORRECTED 2026-07-31 by Ruling 3, second block: TRUE
     in geometry, measured FALSE in tenure — the cut left the
     spent tail unstrung (+2,533 m).  Tenure now follows emission;
     the pairing rule itself is unchanged.]  Seam joints compose
     END-TO-END ONLY (fragment end ↔
     piece end); a fragment ending mid-span of its covering piece
     simply ends — the physical line there is already the covering
     piece's chain, and no mid-edge vertex is ever minted.
  4. `min_len_m` (the owner's 100) applies to WALK OUTPUT on the
     composed domain, never to authored fragments.  The DELETE
     mechanism dissolves; three instruments at three scales measured
     it (the unit fixture; S1's one-variable intervention — 126
     strings / 18.5 % at route-tier chains vs 63 / 99.9 % at
     through-paths, walk byte-identical, stop reasons 88 %
     `route_end`, spine-gap stops inert 0/1,338; the driver's 107 /
     1,412.7 m / 39 % sub-min mass).
  5. THE WALK IS UNCHANGED — measured not-the-limiter.  Dissolving
     chains into a free graph walk is REJECTED: unmeasured new
     machinery for a job the measured construction already does (U1
     anti-pattern), and linear chains are what keep open-terrain
     crossing unrepresentable — composition adds NO geometry; every
     chain metre is a substrate polyline metre, so a string still
     cannot cross unpaved ground.  Independent corroboration of the
     walk, recorded: worst member-node offset from its own string's
     chord 7.97 m (bound 8.0) vs the retired assembly's 695.22 m —
     the open-terrain class quantified; this feeds
     `assemble_maximal_strings`' retirement case, which still waits
     for acceptance (a later measured step, never a silent
     deletion).  Sequencing for the implementer: substrate function
     (Ruling 1) → composition (Ruling 2) → the seam returns composed
     chains; walk and driver untouched.  Note the seam TODAY feeds
     the processed tier (645 chains — the third instrument's
     population), which is NEITHER ruling; both rulings land there
     together.
* **GATE B VERDICT: SUBSTRATE-DOMAIN ARTIFACT, NOT A CONSTRUCTOR
  DEFECT.**  The union covers 100 % of chord-1 stations; the
  one-variable chain-boundary intervention moves best-single
  18.5 → 99.9 % with the walk byte-identical; 88 % of emitted ends
  stop at `route_end`; spine-gap stops are measured inert.  The
  93.0 % under way-dedup was the WRONG mechanism (a standing
  duplicate as second authority); under the ruled construction
  chord 1 is carried by apt.dat through-path chains — the right
  mechanism.  GATE B STANDS as a gate and re-reads after ARM-ACCEPT.
* **COUNT GATE (≤ 50) STATUS.**  Owner's constant; only he moves it.
  Current FAIL (194 / 142) attributes to the same two mechanisms
  (duplication + chain boundary).  The through-path 63 is
  ATTRIBUTION EVIDENCE, not the ruled construction's count
  (apt.dat-only, ad-hoc pairing, pre-dedup).  The gate carries two
  pre-existing tensions, now surfaced together: (1) this spec's own
  corrected expectation (~51-56 under his definition — the anomaly
  track feeding the gate) EXCEEDS the hard 50; (2) the denominator
  moved under it (map 40 → 46 ways; the 46-49 class was seated on
  40).  DECISION RULE, pre-registered: run ARM-ACCEPT first.  Count
  ≤ 50 ⇒ gate PASSES, no owner question.  Count in the ~51-56
  region ⇒ the contradiction is REAL and routes to the OWNER as one
  artifact-backed question (his current 46-way map, the per-way
  correspondence, the anomaly splits: does ≤ 50 stand against the
  current map, or does the bound re-seat on his corrected count?).
  Count well above that band ⇒ OURS to attribute first — a defect
  is never laundered through a constant request.
* **ARM-ACCEPT (named, pre-registered, zero-build; S1's instrument,
  ~30 s):** substrate per Ruling 1 (subsegment dedup at 8.0, sub-8 m
  absorption, seam joints); chains per Ruling 2 (global best-pair
  composition); walk as landed (`bound_m=8.0`, `min_len_m=100.0`).
  Report: the full gate table (GATE A both definitions, GATE B best
  single + union, count, inventory metres, sub-min mass),
  stop-reason distribution over emitted ends, and per-owner-way
  string multiplicity with split locations.  Pre-registered
  expectations: GATE A ≈ today's (coverage is substrate-geometry —
  a material move is a FINDING to attribute, not to celebrate);
  GATE B reaches the end-to-end class on −39330 from apt.dat-tier
  chains; the count reads by the decision rule above.  Acceptance
  re-reads ONLY from this instrument (register 21).
* **WIRING-FIXTURE DISPOSITION (ruled here, not by an implementer):**
  `test_wiring_assembles_from_authorship_and_holds_the_chord` and
  `test_wiring_no_datum_falls_back_and_is_counted` assert the RULED
  law — "two authored fragments sharing a node assemble into one
  string" is the model spec's own sentence — so they are
  PRE-REGISTERED FIXTURES of Ruling 2: red until the seam lands,
  green with it.  The curve-fixture disposition does NOT transfer.
  Assertions keyed to assembly-era summary fields
  (`heading_window_m > 0.0`) may conform to the walk driver's
  summary without a further ruling; the premise assertions (one
  string, chord held, anchors unrewritten, `no_datum` counted) are
  normative.
* **DENOMINATOR HYGIENE (ruled):** the canonical denominator is the
  owner's file AS ON DISK at measurement time, measured by the
  ACCEPTANCE instrument.  Today: `/Users/noah/heca_strings.osm`
  (2026-07-31 10:20) = **46 ways / 99 nodes / 41,412.7 m polyline /
  39,452.5 m end-to-end chord; chord-1 way −39330 = 3,981.4 m**.
  P7 independently 41,413 m; a cross-instrument spot-check sits
  0.4 % low — the INSTRUMENT is named part of the denominator
  because the ~2 % length diagnostic cannot afford mixed
  projections.  "40 strings / 88 nodes / 37,327 m" (and the chord-1
  3,974.8 / 3,979 / 3,990 variants) are the SUPERSEDED morning
  version — historical citations stand as history with this block
  as the pointer; every live gate and diagnostic re-reads against
  the current file, and every acceptance run LOGS the file's mtime,
  way count, and measured total (a cached denominator is exactly
  how 37,327 reached a live diagnostic).  Calibrations seated on
  the 40-way map are not retroactively invalidated; S1-CP2 re-reads
  them against the current map.  The 46-49 expected class re-seats
  only through the count-gate decision rule, never by silent
  renumber.
* **GATE-CURRENCY CORRECTION (recorded):** the "+316 m / 8 %"
  polyline-vs-along excess was an ASSEMBLY-ERA quantity; under the
  walk it is **0.14 %** (31,129.1 m polyline vs 31,085.4 m
  along-span) — a walked segment is bounded to its own chord by
  construction.  The per-trunk excess report stays (it is the
  wiggle telemetry); the 8 % expectation is dead.

**THE ARM-ACCEPT RULINGS — SECOND BLOCK (2026-07-31; the first
block's instrument ran as pre-registered and S1 again STOPPED at
every unruled point instead of improvising — correct each time.
Evidence record: denominator per the hygiene block (mtime 2026-07-31
10:20:06; 46 ways / 99 nodes / 41,412.7 m); instrument mirror =
production across all 289 chains, 0 mismatches.  GATE A 81.8 %
length-weighted at ±8 m vs the pre-registered 87.1 — the register-21
clause fired exactly as written (a material move is a FINDING to
attribute) and the attribution is Ruling 3's; ≥1000 m subset 85.9 %,
11/12 individually.  GATE B PASS — 3,976.8 m = 99.9 % span of
chord 1, 100 % of stations, median 0.95 m / max 2.9 m, node
provenance 100 % apt.dat (38 apt / 0 OSM): the RIGHT mechanism, and
the first block's substrate-domain verdict is CONFIRMED
interventionally — the substrate offers a 4,312.2 m through-path
where the processed tier topped out at 2,391.2 m with no ~4 km path
at all.  Inventory 74 strings / 39,715.4 m = 96 % of owner metres at
4 % duplication; stop reasons `route_end` 60.8 % / `turn` 39.2 % /
spine-gap 0; multiplicity median 2 / max 15; 0/46 ways at zero
coverage (was 1/46).  Attribution arms, single-variable, zero
builds: A0 = Ruling-1 substrate WITHOUT composition → 87.1 % GATE A
/ 18.5 % GATE B / 160 strings (Ruling 1 alone lands ON its
prediction — the whole −5.3 pp is composition-side); A1 = as ruled →
81.8 / 99.9 / 74; AX = composition with edge exclusivity MASKED →
91.8 / 99.9 / 234 (an attribution arm, NOT a construction);
substrate ceiling 94.5 %.  Uncovered decomposition: A0 5,361 m =
2,268 substrate-absent + 3,093 unstrung; A1 7,550 m = 1,924 + 5,626
— +2,533 m of substrate-PRESENT owner pavement whose edges were
SPENT by composed paths that never strung them.  Per-way the
aggregate hides opposite moves (−869 / −337 / −328 / −281 / −280
against +409 / +182 / +134 / +120): composition's gains are real
and must survive any fix.)**

* **RULING 3 — STRING TENURE: EXCLUSIVITY IS AN EMISSION INVARIANT,
  CHARGED AT STRUNG COVERAGE — NEVER A COMPOSITION-TIME SPEND.**
  What STANDS: emitted strings PARTITION the substrate they cover —
  no metre of pavement carries two string authorities.  AX is
  REJECTED as a construction: overlapping strings are two
  authorities over one ground, the exact minting mechanism the
  emit-consensus record already paid for (two authorities over one
  surface mint violations), and nothing downstream has a law for
  arbitrating two rods on one station.  What CHANGES: an edge is
  SPENT only when an emitted string actually covers it.  Composition
  pairs exactly as Ruling 2 item 3 rules (global best-collinear,
  parameter-free, deterministic — GATE B's mechanism, untouched);
  but edges of a composed path whose chains the walk cut off and
  `min_len`/absorption then deleted RETURN to the pool, and the
  constructor re-runs — identical laws, identical composition,
  identical walk, identical `exclude_nodes` — on the residual
  subgraph, iterating until a round emits nothing.  Termination is
  arithmetic (every emitting round consumes ≥ `min_len_m` from a
  finite pool); determinism is inherited (the residual is a set
  difference walked in the substrate's own stable order);
  `min_len_m` is NEVER relaxed — a residual round that re-composes
  the same sub-min domain emits nothing and the fixpoint stops, so
  delete-not-split holds at every round.  Per-round telemetry
  (round count, strings emitted, metres claimed) joins the stats.
  THE SAFETY SENTENCE, CORRECTED (owned; S1's catch, aimed at this
  spec's own text): "a bad pairing is harmless because the walk
  cuts it" was measured TRUE in geometry and FALSE in tenure — the
  cut protected the STRING but left the cut-off tail SPENT, and
  exclusivity then barred every other string from it (+2,533 m,
  isolated single-variable by AX).  Under emission-charged tenure
  the sentence is true in both senses: a bad pairing costs nothing
  anywhere — the walk cuts its geometry AND its tenure lapses.
  Opus conforms the `compose_through_paths` docstring safety
  sentence to this corrected form when implementing (doc edit, no
  semantic drift).  Build-time: each round is the measured 46.5 ms
  machinery on a strictly shrinking subgraph, expected rounds ≤ 3;
  the hard-law 1 % line governs the measured total.
* **ARM-ACCEPT-2 (pre-registered, zero-build, same instrument and
  denominator discipline):** GATE A expected ≈ 87-90 %
  (composition's per-way gains persist; the orphaned A0-walkable
  mass returns).  MECHANISM GATE, the direct property: substrate-
  present-but-unstrung returns to A0's ~3,093 m walkability-floor
  class.  GATE A below A0's 87.1 %, or unstrung materially above
  the A0 class, is a FINDING (the residual re-domains differently
  than A0's route tier — census the still-unstrung mass) and is
  attributed before any gate re-reads.  GATE B unchanged — residual
  rounds cannot touch covered edges by construction.  Count rises
  above 74 by the residual emissions (order +15-25 expected from
  the 2.5-5.6 km orphan mass at A0 yield; per-round log required)
  and reads by the first block's COUNT-GATE DECISION RULE — status
  update below.  The ceiling stays the substrate's 94.5 %; the
  remaining substrate-absent mass is NOT this constructor's job.
* **COUNT-GATE STATUS UPDATE + THE OFF-MAP DEPENDENCY (recorded so
  Ruling 3 cannot be read as pre-empting the owner).**  The
  decision rule EXECUTED as written: 74 sits above the 51-56 band,
  so it was OURS to attribute FIRST — attributed: 47 strings lie ON
  the owner's map (33,888 m; essentially one per way against his 46
  at 4 % duplication) and 27 OFF it (5,827 m, median 164 m; 18
  apt.dat-authored, 9 OSM standing runs) — and only then routed to
  the owner with the per-way correspondence table.  What his answer
  moves, and does not: GATE A and Ruling 3 move NOT AT ALL — his
  map is GATE A's denominator, the orphaned mass is on-map by
  construction, and off-map strings never enter the metric.  Only
  the COUNT accounting moves:
  - KEEP (off-map pavement carries strings): the inventory is the
    full 74 + residual, and ≤ 50 re-seats on the real inventory —
    his constant, only he moves it (first block).  No constructor
    change.
  - DROP (off-map pavement carries none): his acceptance MAP is not
    a pipeline input — production airports have no owner file — so
    the drop law must key on a PIPELINE-NATIVE property matching
    the intent he states, and the table exists to let him name the
    class (the 18 apt.dat-authored off-map, the 9 OSM standing
    runs, or a length class).  Naming the OSM standing runs would
    REVISE committed D1 law ("OSM stands where apt.dat is absent")
    — his to revise, never ours to infer.  Whatever he names lands
    as an EMISSION FILTER: the substrate builds ONCE, unchanged
    (build once, filter per consumer).  On-map inventory becomes
    47 + the residual strings [CORRECTED same day: recovered
    OWNER-metres are on-map by definition, but residual STRINGS
    need not be — ARM-2 measured the split at 57 on-map / 35
    off-map over 92 strings (v3 denominator, production identity;
    the first-read 57/34/91 was at the since-forbidden 0.5 m)];
    if THAT exceeds his re-seated bound, the trade — recovered
    drawn-map metres vs count — RETURNS TO HIM with the per-string
    recovered-metres table.  Eating coverage of ground he drew to
    fit a count is an acceptance trade only he can make.
* **RULING 4 — THE SUBSTRATE CARRIAGE LAW (§10(i) FIRED AND CLOSED;
  S1's STOP was correct — three separately measured gaps, no carry
  improvised).**  The gaps, for the record: (1) `osm_lines` does
  not exist in phase 2 — OSM taxiway linework is materialised once,
  in phase 1, inside the coverage scorer's parse (`osm_load.py`,
  the `ay == "taxiway"` branch) and then discarded; (2) the
  hook-time `layout.apt_taxi_centerlines` is NOT the S2 snapshot —
  `centerline_recognition.py` REASSIGNS the attribute
  post-recognition (merged / resampled / re-split geometry), so any
  hook-time tier equality assertion is a proxy by construction;
  (3) the substrate is coordinate-space while the driver keys
  rewrites by grade-graph node index.  THE LAW:
  **What crosses.**  ONE write-once layout field (name:
  `string_substrate_src`; storage layout is discretion) carrying
  the CAPTURED SUBSTRATE INPUT, both tiers, in the layout's own
  anchor-relative metre frame — ONE projection; the
  denominator-hygiene block's 0.4 % mixed-projection lesson is why
  no second `to_m` may ever touch this data.  (a) The apt tier:
  coordinate tuples + `is_service` flags materialised at the EXACT
  S2-snapshot assignment (`layout.apt_taxi_centerlines =
  list(osm_centerlines)` under the "Preserve the full input
  centerline set" comment — locate by that comment, never by line
  number), deep-copied so recognition's later reassignment cannot
  reach it.  (b) The OSM tier: `(way_id, polyline)` for exactly the
  `aeroway=taxiway` linear ways the phase-1 scorer already
  consumes, captured AT that existing parse via the SAME `to_m` —
  no second read of any OSM file, no re-derivation (single-pass).
  [CORRECTED same day: the branch this named is DEAD CODE — zero
  call sites since 2026-05-21.  The PROPERTIES stand unchanged;
  the site moved to the live single parse and is RATIFIED as
  Ruling 12 (third block).]
  An empty OSM tier (no OSM data present — the known cwd/worktree
  trap) is LAWFUL degradation and is LOGGED, never silent.
  **Carried how.**  Write-once (a second write raises); captured
  only under the construction gate (gate OFF ⇒ no capture, no
  import, no new attribute — inertness stays by construction, not
  by re-proof); immutable thereafter.  The substrate itself is
  BUILT ONCE, at the hook, by the same pure
  `build_string_substrate` every test and instrument calls — the
  phase-1 side captures and fingerprints, it never builds
  (determinism from inputs is already pinned: the reproduction
  record, exact match, 0.07 s).
  **Identity proof — what shows the same object at both ends.**  A
  content fingerprint (hash over the canonically-serialised
  coordinate tuples + per-tier counts + metre totals) computed at
  capture and stored in the field; the hook RECOMPUTES it from the
  carried object, asserts equality, and LOGS the denominator line
  (pieces / ways / metres / fingerprint prefix) exactly as
  ARM-ACCEPT logs its own — drift from the measured arms shows in
  the log, not in a gate three steps later.  Once, after the
  plumbing lands: the instrument-mirror comparison (the 289-chain
  equality) re-runs against the CARRIED object — a control
  reproducing a known value.
  **Space and decoration.**  The substrate stays coordinate-space
  end to end.  The HOOK side — where the grade graph and the
  canonical registry exist — computes the NODE DECORATION: a graph
  vertex lies ON an emitted string iff its canonical coordinate
  sits within the registry's 0.5 m identity of that string's
  polyline; its station is the arc-length projection.  The
  registry's 0.5 m is the pipeline's ONE identity — the substrate's
  1 µm interning is float hygiene BELOW it, never a second
  identity, and the substrate's 8.0 m is membership/corridor law,
  never an identity radius.  DECORATE, NEVER RE-DERIVE: chain
  topology is frozen at construction; decoration never merges,
  splits, or re-orders chains (the 0.86 m near-miss two-chain pin
  extends across decoration unchanged); no node is moved, no string
  is moved, no unmapped station is snapped or bridged.  An UNMAPPED
  station is an OFF-NET station under the EXISTING §10(v) law (band
  None ⇒ unconstrained; > 20 % of a trunk ⇒ report) — no new
  constant.  An undecorated graph vertex keeps its phase-A value
  (the hook rewrites only strung vertices — §4 law unchanged); the
  resulting fabric-vs-string step is R1's to reconcile (§10(vii)).
  A vertex decorated by two strings is the §3 shared-vertex case,
  already ruled (trunk values it, branch anchors on it): canonical
  identity is authoritative, so this is neither a merge nor
  bridging.
  **Audit (gate on the measured property, never the proxy).**
  Per-string decorated fraction + a round-trip check (every
  decorated vertex within registry identity of its string) join the
  S1-CP2 table.  Where `O4_RECOGNIZED_CENTERLINES` swapped straight
  S2 routes for painted curves, S2-chord-vs-graph displacement is
  the EXPECTED depressor of decorated fraction — a material
  trunk-level drop is a FINDING to attribute (recognition
  displacement vs registry gap) BEFORE the default flip, and the
  census runs OFFLINE on P3's HECA dump first (zero builds).
  [FALSIFIED same day for the dominant tier — see THE DECORATION
  CENSUS: structural absence dominates; displacement survives only
  as one of three candidates for the apt tier's 19.7 % residual.]
  **Who may read.**  The hook's substrate input is the carried
  field ONLY.  Reaching for `layout.apt_taxi_centerlines` at the
  hook, or re-reading OSM there, is a spec violation — both are the
  measured proxies (gaps 2 and 1).
  **Build-time.**  Capture is a copy + hash (phase 1, one-shot);
  the hook-side build is the measured 46.5 ms; decoration must
  reuse the substrate's grid-index pattern and lands under the
  hard-law 1 % line with a measured statement in the implementation
  brief.
  **Divergence, pre-named.**  If some build path reaches the
  S2-snapshot assignment without the scorer's OSM parse having run
  (source selection short-circuits), report the actual order — do
  not add a second parse.
* **RULING 5 — `exclude_nodes` RATIFIED (the flagged interface
  addition stands; flagging it instead of assuming it was the
  deviation rule working as written).**  Keyword-only, default `()`
  ⇒ pre-ruling identity.  The law it encodes: EXCLUSION IS A DOMAIN
  RESTRICTION AND PRECEDES COMPOSITION — post-composition exclusion
  is wrong-altitude (one role-service node would delete a whole
  composed trunk instead of one fragment; the implementer's hazard,
  adopted verbatim).  Three conditions, now normative: (1) ONE ROLE
  SOURCE — the set derives from the same service-role authority the
  §2 exclusion clause names (the driver's role scan), never a
  second classification at the walk; (2) EXCLUSION IS A WALL, NOT A
  SKIP — an excluded node splits the domain and composition never
  pairs across it (pairing across excluded ground would compose
  geometry over pavement the law excluded — bridging); if walling
  over-fragments a lawful taxiway, that is a ROLES defect to
  attribute, never a walk-side accommodation; (3) UNIFORM ACROSS
  ROUNDS — Ruling 3's residual rounds receive the identical set.
  Substrate corollary, same law at the tier level: service apt
  pieces COUNT for membership/coverage (apt.dat presence is
  presence — the committed sentence is locative) but are EXCLUDED
  from the strung domain; exclusion restricts what may be STRUNG,
  never what COVERS.  If this membership population differs from
  what the measured arms used, the first ARM-ACCEPT-2 run logs both
  populations and the delta is attributed before gates re-read.
  [ANSWERED SAME DAY, early: NIL AT HECA — 0 of 196 S2 pieces are
  service, measured at capture.  The corollary moves none of the
  measured arms here; it binds at other airports and re-logs on
  every ARM-2 run as already ordered.]

**THE DECORATION CENSUS + THE TWO STOPS (2026-07-31, later the same
day.  Ruling 4's own audit order ran OFFLINE on P3's dump — 21,321
grade-graph nodes, openly named as an earlier build's dump, zero
builds — and FALSIFIED the pre-named depressor.  Census at the
registry's 0.5 m, true nearest-neighbour: all substrate vertices
(3,555) 9.9 % @0.5 m / 19.1 % @8 m, median 16.64 m; apt tier (436)
80.3 % @0.5 m, median 0.00 m — exact hits, residual 19.7 %
(p90 22.9 m); OSM standing tier (3,119) 0.0 % @0.5 m / 0.6 % @2 m,
median 19.91 m; stations @5 m (12,179) 62.8 % within 8 m of any
node.  Per emitted string against §10(v)'s 20 % clause: 44/74 over,
19 fully off-net; by length class — ≥1000 m: median 0.0 % off-net,
1/9 over; 300-1000 m: 11/24; 100-300 m: 32/41, median 50 %;
length-weighted 23.8 % of emitted metres off-net.  The OSM standing
tier is not DISPLACED — it is STRUCTURALLY off-net: standing runs
exist exactly where apt.dat is absent, and the grade graph is built
from the apt.dat-derived layout, so there are no nodes beneath them
BY CONSTRUCTION.  Owned by Fable: the depressor was pre-named
without decomposing by tier when the tier split sat in hand — the
displacement hypothesis was only ever a candidate for the apt
tier's residual.  Concurrently: Rulings 3 and 5 are implemented and
measured (record below), and the implementer STOPPED at two
normative collisions instead of ruling them — correct both times.)**

* **RULING 6 — GATE A STANDS AS MEASURED, AND IS NAMED WHAT IT IS:
  A CONSTRUCTOR-RECOGNITION GATE, NOT A DELIVERY GATE.  EVERY
  ACCEPTANCE TABLE NOW CARRIES ACTIONABLE-A BESIDE IT.**  GATE A's
  definition, arithmetic, the A0/A1/AX record and the ARM-ACCEPT-2
  pre-registrations are UNCHANGED — redefining a metric mid-record
  destroys comparability, and the constructor DID string the ground
  the substrate law names.  But under §4's law the ONLY action
  channel is decorated graph vertices, so a string with none can
  rewrite nothing and smooths nothing — coverage alone may no
  longer be PRESENTED as delivery.  THE COMPANION METRIC,
  mandatory beside GATE A in every table from now on:
  **ACTIONABLE-A** = length-weighted fraction of the owner's map
  where a station is covered by some emitted string (±8 m, GATE A's
  own test) AND that covering string has a DECORATED vertex within
  the same 8 m of the station.  Both factors are existing
  quantities (Ruling-1 membership; Ruling-4 decoration); the
  census's nearest-node form is this metric's UPPER BOUND
  (decoration at 0.5 m ⊆ any-node at 8 m); no new constant.  THE
  PROXY HAZARD, NAMED EXACTLY: before D1 admission, no-graph
  ground read as VISIBLE uncovered residual; D1 moved it into
  INVISIBLE covered-but-inert mass.  D1 is NOT re-litigated — it
  governs recognition and stays committed law; ACTIONABLE-A
  returns the gap to view.  The coordinator's hypothesis is
  CONFIRMED AS STRUCTURE: P7's "8 owner lines with no spine
  beneath" and this census's off-net tier are ONE domain gap (the
  grade graph's domain vs the owner's named ground) seen by two
  instruments — with the MECHANISM split still owed, so ORDERED
  (offline, zero builds): decompose the off-net mass into
  PAVEMENT-PRESENT-BUT-UNGRAPHED (graph-domain work, ours to
  attribute further) vs PAVEMENT-ABSENT-IN-LAYOUT (a source/intent
  question — should strings act on ground the layout does not
  pave?), by containment against the layout pavement union the
  instruments already hold.  NO PASS THRESHOLD is seated on
  ACTIONABLE-A here: the threshold prices the owner's purpose
  sentence and is HIS, and seating one before the attribution
  census would launder a domain defect through the constructor's
  gate.  Its first read (ARM-2) is BASELINE-SETTING, ungated.
  Routing: the census + ACTIONABLE-A artifacts TRAVEL WITH the
  27-string package already in front of the owner, QUEUED BEHIND
  his pending ruling — both are the same question (what is the OSM
  standing tier FOR), and "OSM-tier strings largely cannot act
  today" materially changes what keeping or dropping them means.
  Elevation gates are unaffected and sequencing does NOT reopen:
  the ≥1000 m trunk class is essentially fully on-net (median
  0.0 %), chord 1 is 100 % apt provenance — GATE B/C measure
  strings that act; the owner's "arm 3 waits for the plumbing"
  ruling stands.
* **RULING 7 — DECORATION STANDS AS THE CARRIAGE; EMPTY DECORATION
  IS A CORRECT ANSWER; "HEALING" IT IS FORBIDDEN.**  The apt tier
  validates the mechanism at the ONE identity (median 0.00 m,
  80.3 % exact).  A tier decorating at 0.0 % has a DOMAIN problem,
  not a carriage problem — and the carriage's own telemetry
  surfacing that on day one is the audit clause doing its job.
  HARD LAW: decoration is never healed by radius inflation or
  nearest-node snapping — at median 19.91 m a snap would rewrite
  OTHER pavement's vertices with values solved for a line ~20 m
  away, minted violations by construction (the emit-consensus
  class).  Off-net strings stay carried, measured, and INERT until
  the domain question resolves.  DEPRESSOR TAXONOMY, CORRECTED:
  (1) structural absence (OSM standing tier — dominant, measured);
  (2) the apt tier's 19.7 % residual, UNATTRIBUTED among three
  candidates — centerlines ABSORBED into junction polygons, pieces
  DROPPED during rect decomposition (both named by the pipeline's
  own S2-snapshot comment block), and recognition displacement
  (`O4_RECOGNIZED_CENTERLINES`) — ordered as an offline census;
  p90 22.9 m is far beyond curve-vs-chord for gentle curves, so
  absorption/drop carry the prior.  [MEASURED same day, census 2:
  the prior held — 91 % of non-decorating apt vertices are PIECE
  ENDPOINTS (median miss 34.8 m; endpoint failure rate 19.9 %):
  the residual IS the endpoint-ABSORPTION class.  True
  displacement is the 9 % interior class, median 2.2 m.  Fable's
  depressor was mis-named twice — not recognition-displacement,
  not displacement at all — owned both times.]  DUMP-VS-LIVE, pre-recorded:
  the structural conclusion (a 0.0 % tier) survives any dump
  staleness; the exact percentages do not — the S1-CP2
  decorated-fraction telemetry re-reads them on the live build
  before the flip, as already ordered.
* **RULING 8 — STOP 1 RESOLVED: THE PROCESSED-TIER DOMAIN DIES AT
  THE CARRIAGE SWAP, NOT AT THE GATE FLIP — AND NOT BEFORE.**  The
  implementer's STOP was correct, and the interim state chosen
  (carriage functions landed and tested; the seam still serving
  the processed tier; ONE substrate path) is RATIFIED — it is not
  a second substrate path, it is the pre-substrate domain alive
  until the carriage exists.  Owned by Fable: Ruling 4's
  retirement sentence ordered a deletion without sequencing it —
  it was written as if the capture already existed.  The
  sequencing law: "lands" means ONE commit in which (a) the
  phase-1 capture writes `string_substrate_src`, (b) the seam's
  chain source becomes the carried substrate
  (build-at-hook + decoration, per Ruling 4), (c) the two
  pre-registered wiring fixtures are GREEN ON THE SUBSTRATE PATH
  (they are the swap's definition of done; conforming their
  source plumbing was pre-authorized), and (d) the processed-tier
  DOMAIN construction is DELETED in that same commit.  From that
  commit on there is ONE chain source; a selection flag between
  the two paths is FORBIDDEN at every point in time (two live
  paths is the measured hazard class: masked decimators, split
  measurements, mislabeled arms) — before the swap the processed
  tier is the only source, after it the substrate is.  The WALK
  is untouched throughout (unchanged law), and
  `assemble_maximal_strings`' formal retirement keeps its own
  separate acceptance step (Ruling 2 item 5 — never a silent
  deletion).  Between swap and gate flip, gate-on is opt-in
  instrumentation measuring the SHIP construction — which is
  exactly what the owner's held arm-3 build must measure.  A
  missing or empty carried field at gate-on is LAWFUL NO-OP
  degradation (logged, per Ruling 4), never a reason to keep a
  fallback domain alive.
* **RULING 9 — STOP 2 RESOLVED: `station_m` = 5.0 m, OURS — AN
  IMPLEMENTATION RESOLUTION, NOT OWNER LAW.**  The owner's
  constants price INTENT (8.0 m corridor, ≥100 m string, ≤50
  count); a sampling resolution prices nothing he has an opinion
  about — routing it to him would be the intent-question
  anti-pattern inverted (mechanisms get measured, not asked).
  Value grounds: 5.0 m is the resolution EVERY measured arm and
  every pre-registered expectation is seated on (any other value
  breaks the acceptance record's comparability — the metric-
  identity discipline); it satisfies the module's own bound
  (0 < 5.0 ≤ 8.0) and resolves both law lengths it serves with
  margin (absorption at 8 m: 1.6×; `min_len` at 100 m: 20×).
  Known artifact, stated: run extents quantize at ±`station_m`,
  material only within one station of the 8 m absorption boundary
  — chatter-scale, far below the map's 100 m+ runs.  FORM (the
  register-21 discipline in full): the parameter STAYS
  required-explicit in every API (ratified); the value lives as
  ONE named constant at the single production call site, cited to
  this ruling; it is NOT config-owned, NOT env-tunable — a
  tunable resolution invites per-airport fitting, the exact trap;
  it is LOGGED in every substrate/denominator line (already in
  stats — now permanent); a wiring assertion pins the production
  call site to 5.0.  It moves only by ruling WITH a re-baseline
  of the acceptance record, never by tuning.
* **RULINGS 3 + 5 — MEASURED RECORD (zero builds).**  Ruling 3 at
  the substrate tier: 3 rounds to fixpoint — 74 strings
  (39,793.8 m) → +17 (3,208.4 m) → +1 (142.5 m) → 0; **92 total =
  74 + 18 residual, inside the pre-registered +15-25 band**;
  residual emitted 3,350.9 m (NOTE: emitted string metres, not the
  mechanism gate's quantity — substrate-present-but-unstrung OWNER
  metres reads from ARM-2, still the gate); longest string
  3,976.8 m unchanged, round 1 bit-identical to the pre-ruling arm
  on original edge ids — GATE B's mechanism provably untouched;
  exclusivity 0 edges with two authorities; termination arithmetic
  and asserted; 79 tests green; gate-off re-proved and
  independently re-verified.  Ruling 5: implemented as a WALL (the
  seam SPLITS a chain at an excluded node; composition cannot pair
  across).  BUILD-TIME (item 6): Stage 0 committed baseline
  70.56 ms → 87.41 ms with tenure (+16.85 ms = +2.81 % of the
  0.6 s review line, 0.146 % of the 60 s budget) — under the line,
  no review trigger, zero until the flip.  Rounds are the cost
  driver: the 0.6 s line is the tripwire and rounds are TELEMETRY;
  a round CAP is FORBIDDEN (it would silently change emissions —
  a law change disguised as an optimization).  An airport far
  above HECA's 3 rounds is a re-measure case, by time, under the
  existing line.
* **ARM-ACCEPT-2 STATUS:** running against the pre-registered
  block, which is FROZEN as written (no prediction may move
  mid-run).  Report additions ordered here are REPORT-side only:
  the ACTIONABLE-A split (Ruling 6, baseline-setting), the
  per-tier decoration re-read, the service-population log (Ruling
  5 corollary), `station_m` in the denominator line, and the
  residual strings' on/off-map split (which the owner's 27-string
  package is updated WITH, as a delta to the same open question —
  not a fresh question).  [RAN the same day — results, the
  out-of-band GATE A finding, and the acceptance ruling: third
  block, below.]

**THE THIRD BLOCK — ARM-ACCEPT-2 RESULTS + THE CARRIAGE LANDINGS
(2026-07-31, evening; zero builds throughout; instrument mirror
identical across 289 chains.  ARM-2 against the frozen
pre-registration: GATE A 86.8 % vs predicted 87-90 — OUT OF BAND,
−0.3 pp under A0's 87.1, reported unattributed exactly as the
frozen clause requires; ≥1000 m subset 90.7 %, 11/12; 17/46 ways at
100 %, 0/46 at 0 %.  GATE B CONFIRMED — 3,976.8 m, 99.9 % span,
100 % of stations.  Unstrung 3,531 m from 5,626 — 83 % of the
2,533 m excess recovered, 438 m short of the A0 class: partially
met.  Count MET — 91 = 74 + 17 residual (3,248.5 m recovered);
inventory 42,963.9 m = 104 % of owner metres, 57 on-map / 34
off-map (the owner's package updates by delta, as ordered).
Exclusivity PASS — 0 edges with two authorities; stop reasons
unchanged.  THE FINDING'S RECORD: the headline nets a 2,356 m LOST
/ 2,261 m GAINED two-way redistribution (worst ways: −39349 −385,
−39312 −360, −39328 −337, −39354 −281, −39322 −280).  Two
mechanisms proposed and BOTH FALSIFIED by S1: "A0 was a
non-exclusive baseline, unfair comparison" — REFUTED, A0 holds
exactly 1 double-authority edge / 192 m, like-for-like; "lost
ground buried in sub-min fragments" — REFUTED, 94 of 2,356 m =
4 %.  S1 then STOPPED rather than offer a third guess — ENDORSED;
that is the method law holding under pressure.  ESCALATED PROXY
HAZARD NOT REALIZED: all 17 residual strings are apt-tier, 0
OSM-tier, median off-net 0.0 % — the residual's +5.1 pp
(81.8 → 86.8) is coverage that CAN act.  Caveats recorded, not
dropped: 3/17 fully off-net; 7/17 over §10(v)'s 20 %; residual
length-weighted off-net 25.2 % vs round-0's 23.8 %.  Ruling 6's
census question stands on its own — it is simply not what the
residual did.)**

* **RULING 10 — THE INTERNING PIN: CONSTRUCTION-SIDE NODE IDENTITY
  IS THE PRODUCTION FLOAT-HYGIENE VALUE; THE REGISTRY'S 0.5 m
  BINDS AT DECORATION ONLY; REGISTRY-SCALE INTERNING INSIDE THE
  SUBSTRATE IS FORBIDDEN.**  Measured need: S1's telemetry
  diverged from the implementer's on every round, and the ENTIRE
  divergence is the interning radius — S1 at 0.5 m (the registry
  identity), the implementer at 0.001 m; at 0.001 S1 reproduces
  the implementer bit-for-bit (3,081 edges / 39,793.8 m / 1,242
  spent / 92 strings), at 0.5 m it differs by 11 edges / 78.4 m /
  1 string / 1 residual.  Neither computed wrongly — they used
  different IDENTITY DEFINITIONS, and such numbers are formally
  non-comparable.  The law: identity is the canonical registry's
  business alone, and the registry's domain is PIPELINE NODES —
  decoration (Ruling 4) is where 0.5 m binds.  Construction-side
  interning exists only to cancel float noise; at 0.5 m it MINTS
  identity the registry never granted (a sub-0.5 m near-miss
  between authored coordinates would merge — the near-miss law
  keeps it two).  PIN, exactly as `station_m`: the implementer
  NAMES the production interning value(s) in the telemetry
  contract, logged in every denominator line alongside
  `station_m`; every instrument conforms or labels its numbers
  NON-COMPARABLE; no cross-arm table may mix identity definitions
  unlabelled.
* **RULING 11 — ARM-2 IS NOT ACCEPTED YET; THE FROZEN CLAUSE
  FIRED; CONTROL, THEN MASKS.**  Step 0, the CONTROL (a
  re-tabulation, not a new arm): re-read the FULL ARM-2 table
  under the PRODUCTION identity definition (Ruling 10) — S1
  already reproduces the implementer bit-for-bit there, and the
  acceptance instrument must measure the production object
  (register 21).  The −0.3 pp sits at the same order as the known
  78.4 m identity divergence, so the finding itself may be
  instrument-definition noise: GATE A back in band (≥ 87.1) at
  production identity ⇒ the finding ATTRIBUTES to instrument
  mismatch, ARM-2 is ACCEPTED on the re-read, and the
  redistribution stays as telemetry.  Step 1, only if still out of
  band — the named attribution JOIN (zero builds, existing
  per-station artifacts): cross-tab the lost 2,356 m by
  {substrate-present-but-unstrung} vs {strung-but-chord-far: owner
  station ≤ 8 m from the covering through-path's SUBSTRATE
  polyline yet > 8 m from the emitted CHORD — the lawful
  triangle-inequality class, membership 8 + walk bound 8} vs
  {other}, per way for the five named losers.  NO third mechanism
  is guessed here — the partition is named, the masks decide.
  Pre-named CONSEQUENCES, not predictions: chord-far dominant ⇒
  the loss is structural to long-chain chords (GATE A and GATE B
  trade through chord length); that does NOT reopen composition —
  GATE B is committed law — and routes as a gate-definition note
  beside Ruling 6's ACTIONABLE-A, to the owner only if he wants
  the last coverage points; unstrung dominant ⇒ back to Fable with
  the run-geometry census.  BLOCKING SCOPE: this ruling blocks
  GATE A's acceptance line and final ARM-2 sign-off ONLY — not the
  carriage swap (Ruling 8), not the owner packages, not arm-3
  planning; the control + join are offline and hours-scale.
* **RULING 12 — THE OSM CAPTURE SITE: THE MOVED SITE IS RATIFIED;
  THE NAMED BRANCH WAS DEAD CODE, AND THAT MISS IS OWNED.**
  Measured: `_score_apt_dat_against_osm` (the `ay == "taxiway"`
  branch Ruling 4(b) named) has zero call sites in `src/`,
  `tools/`, `tests/`, `Sources/` — superseded 2026-05-21 by
  `_pick_best_apt_dat_against_osm` ("no pavement / OSM coverage
  analysis is performed").  No build path executes the named site.
  Owned by Fable: the branch was verified to EXIST, never to
  EXECUTE — a semantic anchor must be an anchor on a MEASURED-LIVE
  path; liveness is now part of naming any capture/hook site, and
  the implementer's §10 report-the-actual-order response was the
  correct handling (no second parse added).  THE RATIFIED SITE:
  capture consumes the `nodes`/`ways` of the single existing
  `_load_osm_airports` call (published as
  `layout._osm_airport_features`), filtered in memory under the
  same `to_m`, both capture points in one function scope; the
  population REPLICATES the dead branch exactly —
  `aeroway == "taxiway"` only (no `parking_position`; that is the
  wider processed tier and may not leak in), ≥ 2 resolvable
  nodes, ≥ 1.0 m — every Ruling 4(b) property preserved
  (single-pass, one projection, no second read, exact
  population).  The population filter is PINNED by test (required
  if not already among the landed 22).  Locate by the live
  parse's semantic anchor, never a line number.  The dead scorer's
  DELETION is endorsed and routes to the HYGIENE track as its own
  commit — it is the only thing left that LOOKS like a live OSM
  taxiway parse and it has already misled this spec once; it does
  NOT ride the swap commit (Ruling 8's definition of done stays
  minimal).
* **CARRIAGE CAPTURE — MEASURED RECORD.**  Apt tier as ruled:
  materialised immutable float tuples ARE the deep copy (stronger
  than `copy.deepcopy` of shapely objects); the gap-2 regression
  guard runs the REAL `recognize_curved_centerlines` and pins
  non-vacuity first (recognition fires, rewrites 3 pieces → 2 with
  different geometry; captured tier + fingerprint unchanged).
  SINGLE-FINGERPRINT DISCIPLINE HELD: the implementer deleted its
  own drafted fingerprint and imports the hook's
  `substrate_fingerprint` function-locally AFTER the gate's early
  return — `taut_string` stays unimported at gate-off
  (test-pinned); `layout.py` carries an explicit comment
  forbidding any fingerprint defined there.  Field set ONLY under
  the gate (gate OFF grows NO attribute — 0.33 µs), write-once,
  second write raises.  Build-time (item 6): gate ON 5.48 ms
  (apt 0.74 + OSM 1.10 + fingerprint 3.27; the fingerprint is
  60 % and recomputes once at the hook, ~9 ms/build total) —
  0.0091 % of the 60 s budget, ~66× under the review line.
  22 new tests green driving the real production path, including
  the tamper assertion firing on a modified tier.  UNRELATED RED,
  recorded with evidence: 5 failures in `test_crown_seam_ramp.py`
  (`KeyError: 'axis_len2'`), PROVEN pre-existing interventionally
  (scratch rebuild with only the capture call removed → identical
  5) — a concurrent session's in-flight `crown.py` work; no gate
  in this line (including Ruling 8's fixtures-green) reads against
  it, per the §6 suite-comparator law with this note as the
  evidence.  STATUS: with Rulings 8, 9, and 12 the carriage is
  UNBLOCKED — the swap commit may assemble; arm 3 stays held by
  the owner until it lands (his ruling).

**THE FOURTH BLOCK — OWNER RULINGS + FOUR CLOSURES (2026-07-31,
late.  The swap LANDED: chord 1 end-to-end on the production path
at 3,976.8 m, 101 tests green, gate-off intact, build time flat.
The owner ruled on the off-map package, verbatim: "the onmap ones
are good"; keep the correct off-map ones; "the ones that are not
needed are ones that overlap a runway, and there's a couple that
don't appear to align with a taxiroute: OFF-04 293 m OSM detached /
OFF-07 270 m OSM detached.  So we're very close."  And §2.2b ran on
the swap-landed constructor: `infeasible_station` 55 → 429.)**

* **OWNER RECORD (closes Ruling 6's routed question and the first
  block's count-gate decision rule).**  KEEP — off-map pavement
  DOES carry strings; per the recorded dependency, the ≤ 50 bound
  RE-SEATS on the real inventory (his constant, moved by him; the
  numeric gate is superseded by his review-by-artifact of the
  actual inventory; count stays reported telemetry).  ON-MAP
  ACCEPTANCE, recorded as acceptance and not as an aside: "the
  onmap ones are good" — the 57 on-map strings (v3, production
  identity) are OWNER-ACCEPTED on his own drawn ground, as amended
  by his own runway class below (ON-20 is on-map and running-along;
  the acceptance carries that amendment, not an exemption).  His
  two exclusion classes are the remaining distance to "very
  close": (1) runway overlap — Ruling 16; (2) taxi-route
  misalignment — HELD, below.
* **RULING 14 — ARM-2 ACCEPTED (the Ruling-11 ladder completed).**
  Step 0 halved the finding and proved the identity hypothesis
  right in direction and magnitude (−0.30 → −0.16 pp at production
  identity; every tenure round reconciled bit-for-bit; GATE B and
  exclusivity unchanged).  Step 1 attributed the survivor: lost
  2,336 m = 97 % genuinely UNSTRUNG + 3 % lawful chord-far + 0 %
  other — chord-displacement refuted, on top of the two S1
  falsifications.  ACCEPTED at **GATE A 86.9 % / production
  identity / v3 denominator** — the comparability baseline for
  every future arm; the 87.1 floor RETIRES having done its job (it
  was an attribution tripwire, never an owner constant; the owner
  gate was and remains majority).  The −0.16 pp net / ~2.3 km
  gross churn is RECORDED as the structural price of Rulings 2+3
  (composition-boundary starvation: shoulders spent by emitted
  neighbours leave residual domains that cannot reach `min_len`;
  A0's route-tier packaging hid it by bundling shoulders with
  interiors).  NO FIX IS ORDERED, so no mechanism-narrative debt
  blocks acceptance (mechanism-before-FIX; a priced trade needs
  attribution of the finding, which this is).  Pinned as a RECORD
  item on the next instrumented arm, not a gate: the confirmatory
  cross-tab (lost-unstrung edges ⊆ the never-spent pool at
  fixpoint — 1,839 of 3,081 edges — with their maximal
  residual-domain lengths < `min_len`); a mismatch REOPENS the
  attribution.  ANTI-TUNING CLAUSE: no `min_len` relaxation (the
  owner's 100; only he moves it) and no boundary special-cases
  (U1 anti-pattern) may be proposed against this class without a
  full GATE B + no-new-constant pricing.
* **RULING 15 — THE ACTIONABLE-A INSTRUMENT: NEITHER NUMBER
  TRAVELS AS THE ANSWER; THE RELATION IS RECONCILED AND THE FORM
  IS RE-PINNED TO EDGE-SPANS.**  S1's hazard-surfacing and its
  refusal to pick are ENDORSED — instrument choice is a ruling.
  (a) RELATION RECONCILIATION, ordered first: the baseline's
  population ("126 of 1,295 STRUNG vertices"; 5.9/km) is the
  TRANSPOSE of Ruling 4's ruled relation, which decorates GRAPH
  vertices against the string POLYLINE at the registry 0.5 m.  One
  table reconciles: graph vertices decorated under the ruled
  relation, production strung-vertex counts, and the baseline's
  figures — each with its definition named (Ruling 10's
  mixed-definition law applies to decoration too).  (b) FORM: the
  8 m-window per-station test RETIRES as a proxy of the true
  delivery mechanism — rods are EDGE objects, and a rod is
  string-shaped iff BOTH its endpoint vertices are rewritten.
  **ACTIONABLE-A (final form, constant-free): an owner station is
  actionable iff covered (GATE A's own ±8 m test) AND its
  arc-position on the covering string lies within a span between
  two decorated vertices adjacent in that string's decorated
  sequence and connected by a graph edge.**  (c) The per-string
  quantity is RETAINED as telemetry named ANCHORED-STRINGS
  (existence-not-delivery; 70/92, 86 % of metres, 80.1 %
  owner-map at baseline), always labelled.  (d) The corrected
  re-measure runs on the dump (zero builds) and SUPERSEDES the
  4.8 / 80.1 pair in the owner package — the pair stays labelled
  "being decided" until then.  Pre-registered: corrected
  ACTIONABLE-A lands well above 4.8 on graphed pavement and below
  GATE A, the remainder isolating census 1's extraction class;
  single-digit persistence would be a NAMED FINDING
  (along-centerline node sparsity/offset) to attribute, not
  accept.
* **CENSUS 1 CLOSURE (Ruling 6's ordered decomposition).**  99.2 %
  of off-net strung vertices sit on DRAWN PAVEMENT (137 apt
  polygons + 49 OSM closed aeroway polygons); pavement-absent is
  0.8 %; on-net control 99.5 %, indistinguishable.  The
  pavement-absent intent fork of Ruling 6 COLLAPSES: the off-net
  ground is real pavement the grade graph fails to cover, so the
  fix locus is UPSTREAM EXTRACTION (grade-graph/layout coverage),
  routed as its OWN track with its own spec — not this
  constructor's law, and not an owner intent question beyond
  scope/priority.  The P7 ≡ off-net-tier identification is now
  MEASURED, not inferred.  Interim honesty stands as ruled: inert
  strings carried, ACTIONABLE-A shows the gap, no-heal law binds.
* **RULING 16 — RUNWAY OVERLAP IS A DEFECT AGAINST COMMITTED LAW
  ("Runway profiles are EXCLUDED"), AND THE ENFORCEMENT LOCUS IS
  THE HOOK-SIDE STRUNG DOMAIN, PRE-COMPOSITION.**  [SUPERSEDED IN
  MECHANISM the same day, by the OWNER'S OWN RULE — fifth block,
  Ruling 18.  What STANDS from this ruling: the DEFECT finding
  (committed law unenforced on the substrate tier, mechanism
  located at the late pipeline filter), clause (i)
  capture-unchanged, clause (iv) membership-not-restricted, and
  the measured record.  What is REPLACED: the pre-composition
  domain wall and the angle discriminator — the owner's
  clip-and-floor subsumes both, and two measured blockers killed
  the wall's mechanics first (the shared predicate encodes the
  RECT consumer's failure mode and deletes all 51 lawful
  crossings; 12 of 20 running-along pieces are PARTIAL, so a
  per-piece drop discards 898 m of lawful pavement including 85 %
  of on-map ON-20).  The implementer's STOP at both was correct.]  Measured: 21/92
  strings touch runway pavement — 10 RUNNING-ALONG at 0-29° to
  the runway axis vs 11 CROSSING at 74-90°, an EMPTY 29-74° gap
  (the discriminator validates itself; no fitted threshold
  exists because the classes do not touch).  Running-along =
  1,691 m = 3.9 % of emitted metres, 9 off-map + ON-20 (427 m,
  on-map) — reaching the owner-accepted set, which is why his
  general form of the ruling was right.  Mechanism located: the
  pipeline's own runway filter binds LONG AFTER the S2 snapshot
  the substrate captures, so the substrate inherits pieces the
  pipeline itself later discards (11 apt-tier + 9 OSM-tier
  running-along).  THE LAW: (i) CAPTURE IS UNCHANGED — moving it
  past the filter would trade Ruling 4's ruled snapshot property
  and re-seat the whole measured record; (ii) the exclusion binds
  at the HOOK between substrate build and composition, as a
  DOMAIN WALL on RUNNING-ALONG segments only, BOTH tiers, with
  Ruling 5 semantics exactly (a wall, never a skip; composition
  never pairs across; residual rounds receive the same walls);
  (iii) CROSSING segments stay walkable — transverse runway
  crossing is lawful and is precisely what clause-1
  runway-crossing anchors expect; (iv) MEMBERSHIP IS NOT
  RESTRICTED — runway-running apt presence still covers (OSM may
  not stand over runway ground); exclusion restricts what may be
  STRUNG, never what COVERS (Ruling 5's sentence, third
  application); (v) the geometry authority is the pipeline's own
  runway rects with each runway's own apt.dat width — the same
  objects the late filter uses; the discriminator is pinned AS
  S1 BUILT AND VALIDATED IT (contiguous overlap against the
  runway's own width, angle beside it); (vi) a regression fixture
  pins a running-along piece yielding no string along the runway
  while a crossing survives intact.  PRICED effects, recorded
  before measurement: about −1,691 m emitted; ON-20's
  running-along span dies and its remainder re-forms; any GATE A
  dip is priced to the OWNER'S OWN RULING, reported, and is not a
  defect.  This lands BEFORE arm 3 — it is one of the owner's two
  named finish-line items and touches no ≥2 km trunk.
* **CLASS (2) — HELD OPEN, AND THE STRUCTURAL CONNECTION NAMED.**
  The naive reading is REFUTED with the opposite sign (his two
  rejects are the CLOSEST-aligned: median 14.9 m, 100 % within
  25 m; kept strings run to 140 m).  Candidate C (never within
  8 m of a route, always within 25 m — the OFFSET-SHADOW
  signature: a lane beside the taxiway, not the taxiway) selects
  exactly 2/2 with 0 swept in, reusing only existing constants —
  RECORDED AS LEADING CANDIDATE, NOT LAW: six candidates against
  two positives is the multiple-comparisons shape this line has
  already paid for, S1's refusal is endorsed, and the owner is
  being asked for more examples.  No filter lands on two points.
  THE CONNECTION, named deliberately: both exemplars are
  OSM-sourced from the 0 %-decorated tier, and an offset-shadow
  is exactly the case where D1's "OSM stands where apt.dat is
  ABSENT" is resolution-ambiguous — absent at the 8 m membership
  tolerance, present at corridor scale (25 m).  If his further
  examples confirm the shadow class, the lawful fix is a
  REFINEMENT OF D1's ABSENCE RESOLUTION INSIDE THE SUBSTRATE
  DEDUP — not an emission filter — and it is HIS committed-law
  sentence to refine, with the substrate's membership machinery
  already holding both distances.  No implementer discovers this
  inside a filter.  [LABEL + ROUTE CORRECTION, same day — the
  owner corrected his own labels, verbatim: "CORRECTION! 07 and
  04 ARE correct and on a centerline!  It's 03 and 30 that are
  not!"  Everything above seated on OFF-04/07 as rejects is
  VOID: candidate C's 2/2 selection, and the
  offset-shadow-as-reject reading — which the corrected labels
  INVERT: OFF-04/07 are OSM standing over real taxiways apt.dat
  lacks, D1 working as designed, now owner-affirmed.
  Re-measured on the corrected population, THE REJECT CLASS IS
  TWO CLASSES: (2a) OFF-23 — OSM tier, apt.dat genuinely absent
  at 8 m, ~17 % at corridor scale, verified by CONTENT (it
  matches the owner's own "maybe 25 percent" description where
  the old labels failed content-match) — the ONLY member a D1
  absence-resolution refinement can reach, and ONE point, so no
  predicate is designed on it; (2b) OFF-03 / OFF-30 —
  apt.dat-TIER routes, 100 % on-centerline at every radius,
  100 % OSM-corroborated (median separation 8.7 / 6.1 m),
  admitted apt.dat-FIRST on PRESENCE: STRUCTURALLY UNREACHABLE
  by any refinement of how the dedup resolves ABSENCE, because
  the dedup treats apt.dat as ground truth.  Whatever governs
  2b lives UPSTREAM of the dedup or OUTSIDE our sources — the
  refinement, if the owner's examples confirm 2a, is scoped to
  2a ONLY and is never designed against all three.  Five
  candidates refuted on the corrected population
  (coverage-fraction — a real negative this time; candidate C;
  the buried-centerline predicate; distance-to-centerline in
  any form; apt.dat-over-declaring — killed by the OSM
  corroboration).  CAVEAT recorded with that last kill:
  corroboration is not independence — two databases can share
  one stale upstream — so the elimination does not prove the
  routes exist on the ground; it proves OUR HELD DATA cannot
  separate the classes, which is exactly the routing point.
  Leading candidate by elimination sits OUTSIDE the data:
  HECA's apt.dat carries ZERO row-120 painted-line records; if
  the owner judges against visible paint or imagery, the
  resolution is P7 step 0's SOURCE-ACQUISITION branch (or
  owner-supplied per-route rulings) — never a geometric
  predicate fitted to two points, and NOT a dedup law.  The
  owner has been asked directly what he is looking at;
  candidate-hunting is HELD until he answers (five refutations
  is where the method law says stop), and Fable designs NOTHING
  here before that answer.  REGISTER LINE, adopted from the
  implementer: LABELS ARE A POPULATION — a striking result that
  depends on a small hand-supplied label set is PROVISIONAL
  until the labels are confirmed (the sibling of "a margin is
  only as valid as its population", one level up, about LABELS
  rather than measurements).  Provenance recorded whole: the
  same instrument that surfaced the inconsistency (OFF-07
  maximally on-centerline under a reject label, flagged before
  anyone knew the labels were wrong) also built a confident
  opposite-direction conclusion ON those labels, and the
  implementer declined the credit and volunteered the tempering
  — the tempering is the lesson.  CONTENT-MATCH BEFORE
  LABEL-TRUST is the working mechanism: it is how OFF-23
  verified when 04/07 failed to.]  [SECOND CORRECTION, same day —
  the owner described OFF-03/30: "they're just in the apron
  running parallel to a taxi centerline about 15m offset from
  it.  Based on satellite imagery.  Let me double check what's
  actually in the apt.dat" — the OFFSET-SHADOW SIGNATURE, at the
  APT.DAT TIER, where nobody looked.  And it exposed an
  instrument flaw: the 100 %-on-centerline figures were computed
  against the NEAREST centerline INCLUDING the string's own
  source — an apt.dat-tier string is within 8 m of its own
  authoring centerline BY CONSTRUCTION, so 100 % at every radius
  was a TAUTOLOGY, not a finding.  REGISTER LINE: EXCLUDE SELF
  BEFORE MEASURING PROXIMITY — a reference population that
  contains the measured object's own source can only confirm
  ("name the population", applied to reference sets).  The
  apt-tier refutations are PROVISIONALLY WITHDRAWN — candidate
  C's idea revives as a candidate AT THE APT TIER — and the
  re-measure excludes self and asks the owner's own question: is
  there ANOTHER taxi centerline running parallel at ~15 m, with
  the string sitting on apron pavement.  The 2a/2b SPLIT STANDS
  unchanged (presence-admission vs absence-resolution remain
  different loci; if an offset-shadow predicate emerges at the
  apt tier it is a SOURCE-DATA / upstream question, still never
  a dedup-absence refinement).  The hold stands; the owner is
  checking his own apt.dat and his answer may supersede
  everything here.]  [CLOSED same day — his answer DID
  supersede: the OFF-03/30 class is parallel-duplicate source
  data and the owner DISSOLVED it, no filter, no rule (Ruling
  33, tenth block, with the measurement's self-falsification).
  OFF-23 (2a) stays dormant: one point, no predicate.]
* **RULING 17 — §2.2b CLOSURE: THE MANUFACTURED CLASS IS §3's
  MEASURED PRICE; ARBITRATION IS OPEN LAW WITH ITS CENSUS
  ORDERED; ARM 3 IS VALID FOR ITS TRUNK-SEATED GATES AND
  PROCEEDS.**  The classification record: 429 rows = 86 distinct
  author-pairs — 35 SURFACED (median excess 1.468 m, matching the
  historical 179's 1.515 — same population; band-vs-anchor
  merges with P3c's §6.4 presentation as ruled) + 51 MANUFACTURED
  (median 6.108 m / max 8.102), EVERY one involving an `xstring`;
  mechanism attributed INTERVENTIONALLY by the decoration mask
  (429 → 75; 82.5 % shared-vertex-authored; two instruments
  agree 354 vs 365).  Multi-valued decoration is NOT reverted
  (ruled; the mask costs 474 strung vertices and raises
  `no_datum` 32 → 44).  The defect is §3's: trunk-first freezes
  an earlier string's value — chosen from tube SLACK — into a
  hard equality, and a later string inheriting two such frozen
  choices that nothing ever coupled can invert its own tube.  §3
  HAS NO ARBITRATION RULE FOR TWO INCOMPATIBLE CROSS-ANCHORS;
  the implementer's refusal to invent one is endorsed.  INTERIM
  LAW, affirmed: §2's minimal fallback IS the behaviour (the
  infeasible run keeps phase-A locally, flanks string, the gap
  is surfaced in the witness) — nothing new is improvised for
  builds.  ORDERED (offline, zero builds), the census the
  arbitration ruling will stand on: for each of the 86 pairs,
  each authoring string's post-propagation [lo, hi] WIDTH at the
  shared vertex and where its frozen value sits in that
  interval; and for the 51, whether compatible choices existed
  within both strings' slack plus g·d (|z_A − z_B| ≤ slack_A +
  slack_B + g·d).  PRE-REGISTERED FORK: mostly yes ⇒ the
  contradiction is MINTED BY PREMATURE FREEZING and the
  arbitration law will inherit INTERVALS where slack existed
  (designed by Fable on the census, targeted before the S1-CP2
  flip decision, never before the census); mostly no ⇒ the
  incompatibility is REAL between tubes and routes to the §6.4
  owner pathway with the surfaced class.  ALSO ORDERED: the
  one-line clause-1 provenance labelling at the hook
  (`truth_hard` / `runway_nodes` / `building_seats`) on the next
  instrumented arm — 234 defects carry an anchor-class author
  and the sub-class is currently unrecoverable; recorded OPEN,
  no speculation: the 8.102 m manufactured ceiling
  (reach-band candidate checked and killed).  [CLOSED BY
  AUTHORSHIP in arm 3 — seventh block: `lo=xstring@0` vs
  `hi=cap<-xstring@66`, a string's own value on BOTH sides of
  the infeasibility; the pure form of the Ruling-21 outlawed
  mechanism.  No further mystery; it feeds the slack census.]  ARM-3 VALIDITY,
  ruled: the five ≥2 km trunks (15.2 km, 43 % of strung metres,
  chord 1 included) carry ZERO defects of either class and hold
  ZERO `xstring` anchors under trunk-first — so W-CHORD1,
  W-CHORD2, the assembly gate, and the owner's in-sim read are
  INVARIANT to any future §3 arbitration by construction, and
  arm 3 is a VALID spend for them THROUGH the manufactured
  class.  The build LOGS per-string anchor inventories and the
  trunks' zero-`xstring` status confirms the invariance
  in-build.  The law-true-counts and suite-comparator lines READ
  but are PROVISIONAL-THROUGH-§3 (fallback boundary steps are
  the §10(vii) class): if they regress, the §3 arbitration is
  the named remedy and the FLIP waits on a post-§3 delta
  verification — offline replay first, and if a build is needed
  it is NEW budget, stated now so it surprises no one.
  SEQUENCE to the owner's build: Ruling 16 lands → one offline
  inventory/acceptance re-read on the final construction (the
  runway exclusion moves inventory and GATE A; zero builds) →
  arm 3.  §3 law work runs in parallel and does not gate the
  build.  [Ruling 16's mechanism was superseded by the owner's
  clip rule the same day — the sequence stands with "the clip
  (Ruling 18) lands" as the first step.]

**THE FIFTH BLOCK — THE OWNER'S CLIP RULE (2026-07-31, latest.
Both runway blockers were put to the owner and he ruled directly,
verbatim: "Use the runway outline to clip any strings, discarding
anything inside the runway, and if the remainder is less than 50m
just drop it, the taxiway's grade will be smooth enough without
it."  Q1: the string consumer gets its own owner-supplied rule —
neither the shared predicate nor any threshold of ours.  Q2:
subsegment, sharper than the priced arm B — a CLIP, with no angle
test at all: an along-runway string is mostly interior so its
remainders fall under 50 m and drop; a crossing is mostly exterior
so its remainders survive.  One rule, both classes.)**

* **THE PER-CONSUMER LAW — RECORDED AS SETTLED, NO LONGER OPEN.**
  D1's principle — admission is PER-CONSUMER, keyed to the
  consumer's FAILURE MODE — generalizes from source admission to
  filter predicates and their thresholds, and the owner applied
  the generalization himself without being asked.  Corollary,
  measured the hard way: a threshold inside a shared predicate is
  part of that predicate's consumer contract (the 5.0 m
  runway-drop encodes "no rect belongs on a runway at all" — the
  RECT consumer's failure mode); reuse is lawful only where the
  failure modes match, and a consumer with a different failure
  mode gets its own rule rather than a conformed threshold.
* **RULING 18 — THE CLIP LAW.**  (a) BIND POINT: the clip binds on
  the EMITTED STRING, never the substrate — the coordinator's
  direction is RATIFIED, on deeper grounds than the owner's
  wording: §2 step 1 already places runway-crossing values as
  clause-1 anchors ON THE CHAIN, so committed design REQUIRES the
  chain to span the crossing (the anchor has nowhere to sit on a
  severed chain); substrate-side clipping would split every
  crossing taxiway into two independently-solving strings free to
  diverge at the runway edges where physical continuity is
  hardest law, and would put GATE B itself at the mercy of runway
  adjacency.  Construction spans; EMISSION discards duty inside
  the outline: interior stations carry no rewrite, no decoration
  duty, no witness, and both remainders lie on the one solved
  line, meeting the runway through the crossing anchor.  (b)
  GEOMETRY: "the runway outline" reads as the runway's own PAVED
  outline — the pipeline's runway rect at that runway's apt.dat
  width, the same surface the runway emit covers — NOT strip or
  clearance surfaces, which would eat lawful taxiway pavement
  beyond the paved edge and spuriously shrink remainders.  The
  implementer names the object used and the STOP-if-candidates-
  differ-materially instruction STANDS (a silent pick is the
  shape of a proxy entering); a material delta routes to Fable
  with the comparison table.  [RESOLVED same day, BY THE OWNER —
  the STOP fired, the delta WAS material (3 strings / 0.4 pp
  GATE A / [50,100) band 4 vs 1), and the coordinator routed the
  disambiguation to HIM, correctly: "the runway outline" is his
  own phrase — intent, not mechanism — so the routing clause
  above is CORRECTED to match: an owner-phrase reading
  disambiguates with the OWNER; mechanism deltas route to Fable.
  HIS RULING: the SHOULDER-ABSORBED UNION (75.6 m), shoulders
  included.  The declared-width rect reading is CONSIDERED AND
  SUPERSEDED, not contradicted — the principle was "the runway's
  own PAVED outline, never strip/clearance", and shoulders ARE
  paved and ARE graded by the runway profile, so the widened
  union is where runway elevation authority actually ends;
  strip/clearance remain rightly excluded (not pavement).  Two
  independent supports, recorded so this is never re-opened:
  (1) PROVENANCE — the shoulder widening runs BEFORE the S2
  snapshot, so `layout.runway_union` at capture already IS the
  widened union (verified against the build log:
  75.6 / 75.6 / 75.9); (2) the `pipeline.py:955-958` caution
  governs a width used as a MULTIPLIER (the Annex-14 RESA
  factor), not an outline used as a REGION — the multiplier
  hazard does not reach this use.  Landed arm on the owner's
  outline: 85 strings / 41,285 m / GATE A 86.2 % / 4 dropped /
  [50,100) band = 1.]  (c) THE 50 m FLOOR is an
  OWNER-SUPPLIED CONSTANT, landed with his sentence and his
  reason verbatim at the constant, never recalibrated by us.
  (d) THE 50-vs-100 INTERACTION RESOLVES BY SCOPE, pre-committed
  before the count arrives: `min_len` (100 m) is a
  CONSTRUCTION-EXISTENCE law — walk output on the composed
  domain, pre-clip; the 50 m floor is an EMISSION-REMAINDER law —
  clipped pieces of an already-lawful string, post-clip.  A
  remainder in [50, 100) SURVIVES: reading 100 over it would make
  the owner's "less than 50m" clause dead letter, and his reason
  ("the taxiway's grade will be smooth enough without it") prices
  exactly the remainder question, not string existence.  The
  [50, 100) count is TELEMETRY, labelled remainder-class in the
  inventory, and travels to the owner in the package — if he
  dislikes the population his rule kept, HIS constant moves.
  (e) TENURE AND TERMINATION, no special case: runway-interior
  ground carries no string authority; a dropped sub-50 remainder
  leaves its edges unspent, the residual round regenerates and
  re-drops it, the round therefore emits nothing new and the
  Ruling-3 fixpoint stops — termination arithmetic unchanged, and
  the emitted set of every round is the POST-CLIP set.  (f) THE
  ANGLE DISCRIMINATOR RETIRES from construction; the 0-29° /
  74-90° bimodal record STANDS as measurement history (it is what
  made the classes presentable to the owner).  (g) Regression
  pins: a crossing string survives with both remainders
  collinear and its crossing anchor intact; an along-runway
  string drops entirely via the floor; a partial piece (the
  ON-20 class) keeps its off-runway majority.  Build-time record:
  classification 123 ms / with assembly 169 ms = 0.28 % of the
  budget — under the review line.
* **ARM-3 STATUS RESTATED (Ruling 17 already answers the "one
  remaining blocker"):** §3 arbitration does NOT gate the build —
  the trunk-seated GATE C gates are invariant to any future
  arbitration by construction (trunks hold zero `xstring`
  anchors, confirmed in-build from the logged anchor
  inventories), the §2 minimal fallback is the affirmed interim
  law, and the counts/comparator lines read as
  provisional-through-§3.  The path to the owner's in-sim build
  is: Ruling 18's clip lands → the offline inventory/acceptance
  re-read on the final construction (zero builds) → arm 3.  The
  §3 slack census (Ruling 17) proceeds in parallel and feeds the
  arbitration ruling before the S1-CP2 flip decision.

**THE SIXTH BLOCK — THE OWNER'S STRING INVARIANT (2026-07-31,
verbatim and NORMATIVE: "…they should never CAUSE a grade law
violation, they are just there to give everything a target when
they have the freedom to move, a preference, but the grade law
overrules the string when needed."  This is the model sentence §2
implements — and it TIGHTENS one measured thing: under §2.2b the
51 manufactured contradictions were "ours to fix under the normal
loop"; under this sentence a string that inverts a tube has done
what strings must NEVER do.  Three consequences ruled, not
assumed.)**

* **RULING 19 — THE INVARIANT GATE AT S1-CP2: the flip requires
  ZERO grade-law violations in the emitted surface ATTRIBUTABLE
  TO STRING AUTHORSHIP — the string-attributed SLICE at zero,
  never the aggregate promoted.**  Measured LAW-TRUE (the
  law-true frame is mandatory; the bare-check_grade overcount is
  a paid-for register), attribution by the existing
  witness/author machinery (bend witnesses, defect authors, the
  §2.2b classes) — that machinery is what makes "CAUSE"
  decidable rather than rhetorical.  The aggregate law-true line
  stays exactly as §6 wrote it ("not worse than the
  24F-baseline", already priced there as the four-airport
  ~710 s run) — promoting the raw aggregate would hold strings
  hostage to pre-existing defects they did not author, the
  defect-laundering hazard in reverse.  No new runtime: the
  invariant gate is an ATTRIBUTION SLICE of a run §6 already
  budgets; the coordinator's pricing confirmation to the owner
  is endorsed all the same.
* **RULING 20 — THE §10(vii) BOUNDARY, stated so it is never
  read as licence.**  §10(vii) is a statement about WHEN TO
  JUDGE — transient over-cap during development; only the §6
  gates judge — never about what may SHIP.  With Ruling 19 in
  the gate table the licence expires AT the table: a shipped
  string-attributed violation fails the flip, full stop.  ARM 3
  reads exactly as already ruled (trunk gates valid; aggregate
  lines provisional-through-§3) PLUS one required report: the
  string-attributed slice of its law-true counts, law-true
  framed.  Arm 3 remains a valid READ and was never the flip.
  The INTERIM LAW (§2 minimal fallback) is CONSISTENT with the
  invariant — falling back IS the string yielding to law — so
  nothing changes mid-arm; fallback boundary steps that survive
  the sweeps into the emitted surface land in Ruling 19's slice,
  and clearing them is the §3-arbitration/R1 remedy's job before
  any flip.
* **RULING 21 — THE §3 ARBITRATION'S REQUIRED OUTCOME: THE FORK
  SURVIVES AS TAXONOMY; BOTH BRANCHES NOW SERVE ONE INVARIANT —
  ONLY LAW MAY BIND.  A slack-chosen string value may never bind
  another string's feasibility.**  Operative consequences: (a)
  `xstring` values are PREFERENCES, never degenerate law
  intervals — the entire family of designs that promote a
  string-minted value to hard law is EXCLUDED by owner ruling;
  (b) a LAW-FORCED value (the authoring string's own tube
  pinched to ~zero slack at that vertex) is law passing THROUGH
  a string and may stand hard — which is exactly what the
  ordered slack census measures per shared vertex, so the census
  now feeds the arbitration directly: slack ≈ 0 ⇒ law-forced,
  may bind; slack > 0 ⇒ preference, must yield; (c) where no
  choice within both strings' LAW tubes (plus g·d) can meet, the
  contradiction is LAW-vs-LAW — surfaced, not manufactured — and
  routes to the §6.4 owner pathway as before.  The MECHANISM
  (who re-values whom; ordering; determinism at the shared
  vertex) remains open and is designed on the census as ruled;
  the OUTCOME is no longer open: zero string-authored infeasible
  stations, by construction, in whatever design lands.
  [DESIGNED same day, on the census AND on the owner's own
  proposal — the STRING NETWORK SOLVE, eleventh block: agreement
  as constraint, not inheritance; trunk-first arbitration
  retired; the outlawed mechanism structurally absent.  AND HELD
  the same day — the owner withdrew the agreement premise
  itself; the twelfth block rules what survives, and under soft
  targets the arbitration may not need to exist at all.]

**THE SEVENTH BLOCK — ARM 3's S1-CP2 PACKAGE (2026-07-31.  The
construction is VALIDATED and one policy gated the entire payoff.
Chain 0 (chord 1): 3,976.8 m / 355 vertices / ONE run / ZERO
bends / ZERO off-net / ZERO band inversions — the assembly gate
PASSES in production outright.  Then ONE defect: `no_datum` @
station 0.0 — "span has fewer than two absolute datums; no
post-harmonic inheritance is permitted" — and the span fell back
WHOLESALE to phase-A: W-CHORD1 FAILED with 18 of 20 bins
bit-identical to envOFF because the string was never allowed to
speak.  Not sag, not blockage, not a construction bug, not a grip
bug: DATUM SUPPLY.  34 spans across the build share the class.
Collateral corrections, production-authoritative: length-weighted
off-net 0.0 %, 0 of 64 domains over §10(v) — the relayed 23.8 %
was a prior build's graph and is WITHDRAWN (Ruling 7's
dump-vs-live caveat vindicated verbatim); and chain 0 is the
OPPOSITE of the Ruling-21 outlawed mechanism — no `xstring`
appears anywhere on it; it had too FEW real datums, not a fake
one blocking it.  RULING 19's FIRST READING: 831 defects =
295 MANUFACTURED / 536 SURFACED by recorded authorship; the
invariant's target class is 275 (`infeasible_station` with an
`xstring` binding author) on 7 chains, 102-629 m, all
priority 3; the five ≥2 km trunks carry NONE — the
trunk-invariance argument held in-build, and promoting the
aggregate 831 would have charged strings with 536 law conflicts
they merely revealed: the slice-not-aggregate ruling is
vindicated by its first use.  The 8.10 m worst case
(`lo=xstring@0` vs `hi=cap<-xstring@66`) CLOSES the fourth
block's open ceiling BY AUTHORSHIP: a string's own value on BOTH
sides — the pure form of the outlawed mechanism.  Clean lines:
the clip control reproduced the coordinator's pre-registered
prediction on ALL FIVE values (22 clipped / 4 dropped /
132.51 m / 2 split / 1 in band) — wiring confirmed by
prediction, not inspection; tenure matches every load-bearing
figure; decoration 3,556 of 18,033 eligible, max offset
0.4996 m — never exceeding the registry radius; 14 bends;
1,155 nodes rewritten.  STILL OPEN, unattributed: the 7-way OSM
population gap between offline and production.)**

* **RULING 22 — THE (ii-b) DATUM-SUPPLY POLICY IS THE GATING
  DESIGN QUESTION OF THE LINE, AND ITS RESOLUTION NEEDS THE
  OWNER'S MODEL INTENT — the question is SHAPED here with the
  design space priced, not dumped raw.**  The owner's premise
  was explicitly provisional ("we can try using the anchor
  governed fabric already there" — a directive to measure);
  measured: at the one corridor the line exists to fix, the
  anchor-governed fabric supplied ZERO datums.  The design
  space, priced: (A) FREE-END TAUT SOLVE — where a span has a
  law tube but fewer than two absolute datums, solve the taut
  string with free ends THROUGH the tube (minimal-bend lawful
  line; ends pinned only where datums exist; today's behaviour
  is the degenerate case of two pins).  The tube is fully
  present on chain 0 TODAY (0 off-net / 0 inverted), so this
  works now; it mints no new authority; law still binds first
  (the owner's invariant holds under it by construction).  What
  it leaves open is the ONE model question: where law leaves the
  string's overall height free inside the tube, WHAT CHOOSES THE
  HEIGHT — and that is the owner's call, not a mechanism.  (B)
  law-derived END datums (band value at the end, then solve
  pinned) — REJECTED as design lead's recommendation: the same
  underdetermination hidden inside a formula, and a bad end
  choice bends the whole string, where (A) lets the full span's
  geometry choose the level globally.  (C) one-datum relaxation
  — a sub-case of (A).  (D) `xstring` junction values as end
  datums — EXCLUDED by Ruling 21 except under its law-forced
  test (a slack-chosen crosser value pinning a trunk's level is
  the preference-cascading-as-authority pattern; and chain 0 is
  the TRUNK — crossers anchor on it, never the reverse).  (E)
  owner-supplied per-corridor datums — last resort, not a
  pipeline law.  RECOMMENDATION: (A), with the height rule as
  THE OWNER QUESTION, relay-ready: "Chord 1's string was perfect
  — straight, lawful, zero bends — but the rule for what its
  ends may use found fewer than two absolute reference values on
  the whole 4 km, and 'try the anchor-governed fabric' measured
  out as supplying none there.  The law tube is present the
  whole way, so the string can still be the straightest lawful
  line — but the law leaves its overall height free inside the
  tube, and something must choose it.  All options are lawful
  and differ by at most the tube's width: (i) least TOTAL
  displacement from the existing terrain profile — moves the
  least dirt, and cannot re-import a dip because straightness
  binds first; (ii) the centre of the law band — maximum margin
  both ways; (iii) the DEM's span-scale trend; (iv) a rule you
  specify.  Your 'never cause a violation' sentence is preserved
  under all of them — the tube binds first."  LAW PRESERVED
  under every option: "no post-harmonic inheritance is
  permitted" stands — option (i) uses phase-A as an OBJECTIVE,
  never as a boundary AUTHORITY (no end inherits any value;
  straightness and the tube bind before the objective; a local
  dip cannot transfer through a global least-displacement
  level choice on a straight line).  ORDERED with the remedy:
  the per-span band-presence census over the 34-span class
  (chain 0 is 100 %; how many of the 34 the free-end solve
  rescues is a number, not a guess).  BUDGET, stated plainly:
  the flip CANNOT proceed on arm 3's W-CHORD1 — the string
  never spoke, so the gate never read the construction.  Remedy
  lands → offline replay first (§1a bounds caveat: replay is an
  upper bound) → ONE build for the W-CHORD re-read = NEW
  budget, priced to the owner together with the height
  question.  Arm 3 itself is NOT wasted: it validated assembly,
  clip, tenure, decoration, and Ruling 19's instrument
  in-build.
* **RULING 23 — THE STRING-DISPOSITION LEDGER: IN SCOPE BEFORE
  THE FLIP.**  92 clipped strings → 64 domains with 21 strings
  producing no domain is an INVENTORY-INTEGRITY gap: authority
  that vanishes between emission and the hook is unaccounted,
  and unaccounted is the one thing the identity discipline
  exists to forbid.  The hook's own accounting gains a
  DISPOSITION RECORD per emitted string — `domain` /
  `clip-dropped` / `no-domain + reason` — in the sidecar, on
  the next instrumented run.  NO interpretation of the 21
  before the ledger lands (they may be lawful `no_datum`
  fallbacks; the ledger will say).  The flip is blocked on the
  ledger EXISTING and the 21 being ATTRIBUTED — not on any
  particular disposition being absent.
* **RULING 24 — THE SLACK CENSUS RUNS AS ORDERED, POPULATION
  SHARPENED.**  The 275's chains and authors are now named:
  the census LEADS with the 7 named chains' shared vertices
  (the binding population, the 8.10 both-sides case among
  them), and RETAINS the full 86-pair sweep for the taxonomy —
  a census re-scoped to only the guilty would re-import the
  labels-are-a-population hazard.  Ruling 15's corrected
  ACTIONABLE-A reconciliation RE-BASES onto arm 3's production
  artifacts (decoration 3,556/18,033, max offset 0.4996 m) —
  the dump is superseded for every decoration quantity, per
  Ruling 7's own caveat.

**THE EIGHTH BLOCK — THE OWNER'S TWO ANSWERS AND THE SINGLE-BUILD
CONSOLIDATION (2026-07-31.  He answered both Ruling-22 questions:
the HEIGHT RULE is the CENTRE OF THE LAWFUL BAND — chosen over
least-displacement and DEM-trend with the consequences priced to
him explicitly (least-displacement pulls toward the existing
sagging profile and most likely leaves W-CHORD1 failing; the DEM
at chord 1 runs ~103 against the 111→113 he identified from the
real airport) — the option NEUTRAL to the existing surface,
making no claim about the real airport, maximum headroom both
ways for grade law.  And SEQUENCING: he declined the single-build
datum-only path and chose the stricter one — "hold everything
until §3 lands"; no build until the 275 string-authored
violations are fixed as well; then ONE build reads the datum
remedy AND the invariant gate together.)**

* **RULING 25 — THE HEIGHT LAW: FREE-END TAUT SOLVE WITH
  BAND-CENTRE HEIGHT SELECTION (owner-ruled).**  Precise object,
  so "band centre" is never mis-read: the owner chose a HEIGHT
  RULE for the string, not a shape.  The per-station band-centre
  POLYLINE is explicitly NOT the rule — it is not straight and
  would mint bends law does not require, contradicting
  minimal-bend.  THE LAW: the free-end taut solve yields the
  minimal-bend lawful family; each residual FREE HEIGHT
  PARAMETER (the whole-span translation when no tube contact
  pins it; the end-segment freedoms when contacts exist) is set
  to the CENTRE OF ITS FEASIBLE LAWFUL INTERVAL — maximum
  symmetric margin to floor and ceiling.  Degenerate cases
  confirm the law: two datums ⇒ today's pinned solve unchanged;
  a contact ⇒ the profile is pinned there and the freedom
  shrinks as law dictates.  Deterministic; ties cannot exist (an
  interval has one midpoint).  Formalization of the
  multi-contact case is implementation discretion WITHIN: every
  free parameter centres in its own lawful interval, determinism
  holds, and no bend is added beyond tube contacts.  "No
  post-harmonic inheritance" STANDS untouched — this rule
  consults only the tube (law), never phase-A, never the DEM,
  never another string.  [Height-rule status note, same day: the
  owner's band-centre answer was given under the CONFINED-string
  model; his soft-target reconsideration re-opens the height
  question as the band-vs-ideal fork — twelfth block, Ruling 40.
  This ruling's selection law stands wherever the confined model
  stands.]
* **RULING 26 — THE SINGLE-BUILD INSTRUMENT MANIFEST (complete,
  ruled; anything not on it does not get measured this cycle).**
  RIDES THE BUILD, no additional authorization: (1) W-CHORD1 +
  W-CHORD2 with the string speaking — the build's purpose; the
  20-bin table and the assembly-gate re-confirmation; (2) the
  SOLVER-SIDE invariant read: the §2.2b classification on the
  build's own witnesses — the 275 must read ZERO
  string-authored infeasible stations (Ruling 21's outcome);
  (3) Ruling 23's DISPOSITION LEDGER (this is "the next
  instrumented run"); (4) the clause-1 PROVENANCE labelling
  (crossing / seam / CIFP-derived — the one-line hook change;
  3,741 ids currently unlabelled); (5) the BAND-PRESENCE
  rescue table: predicted-vs-measured stringing of the 34-span
  `no_datum` class under Ruling 25; (6) Ruling 15's corrected
  ACTIONABLE-A + ANCHORED-STRINGS from the build's production
  artifacts; (7) the OSM POPULATION GAP instrumentation: the
  capture's population + fingerprint logged against the
  instrument's — with the attribution ATTEMPTED OFFLINE FIRST
  (it may close before the build; it must close before the
  flip either way — denominator integrity); (8) the standard
  denominator lines (owner file v3, `station_m`, interning,
  substrate fingerprint, decoration max-offset ≤ registry
  radius).  SEPARATE AUTHORIZATION, put to the owner as its own
  ask, never silently spent: the FOUR-AIRPORT law-true battery
  (~710 s; `O4_TEST_AIRPORTS` does not scope the parametrized
  suite) — required because Ruling 19's EMITTED-SURFACE
  attributed slice and the §6 aggregate comparator both read
  from it, and the law-true frame is mandatory (bare
  check_grade overcounts — paid register).  THE FLIP READS
  BOTH: the single build's manifest AND the battery; the build
  alone cannot flip.  PRE-REGISTRATION, frozen before the
  build: the arbitration's predicted reclassification of the
  275 (which resolve by preference-yield vs surface as
  law-vs-law, from the slack census), the band-presence rescue
  prediction, and W-CHORD1's expected direction.
* **RULING 27 — ORDER OF WORK, confirmed with one correction:**
  the two censuses (slack; band-presence) run NOW in parallel —
  dispatched; the §3 arbitration is designed ON the slack
  census (Fable, per Rulings 17/21/24); the FREE-END SOLVE
  (Ruling 25) does NOT wait for the census — it lands in
  parallel (disjoint law region: end policy vs shared-vertex
  arbitration), and BOTH must be in the tree before the offline
  replay so the replay reads the composed system; then offline
  replay (§1a: an upper bound, never the truth) with the
  pre-registration table frozen; then the ONE build with the
  full manifest; then the four-airport battery under its own
  authorization; then the S1-CP2 flip decision on the complete
  table.

**THE NINTH BLOCK — BOTH CENSUSES IN; THE MANIFEST CLOSES
(2026-07-31.  Band-presence: ALL 34 `no_datum` spans carry a full
lawful tube — 0 off-net, 0 band-inverted, 15,454 m, chord 1
included.  Slack: 61 shared vertices, 12 with defects, 49 clean;
on the measurable 12: 3 law-forced (|slack| ≤ 0.05 m), 2
slack-chosen, 7 already-infeasible on their tightest side.
Vertex 20105 — the 8.102 m case — chain 55 held 27.3 m of free
choice and the value it took left chain 10 NO lawful interval:
the ceiling closure by authorship is now confirmed by slack,
independently.  THE FULL-SWEEP DISCIPLINE, measured load-bearing:
guilty-chain vertices lead the population (median min-slack
−3.454 m, 6/6 negative, vs −0.898 m, 4/6) WITHOUT defining it —
vertices 14459 and 20010 are infeasible with NO guilty chain
involved; a census scoped to the accused would have missed them.
Limitation recorded, not buried: the sidecar carries `lo`/`hi`
on defects only, so slack is measured on 12 of 61.)**

* **RULING 28 — OPTION (A) IS A COMPLETE REMEDY FOR THE
  `no_datum` CLASS, NO HEDGE.**  34 of 34 spans have a lawful
  band for the centre-of-band height to sit in.  The
  band-presence rescue prediction SHARPENS accordingly and is
  pre-registered: under Rulings 22/25 ALL 34 spans string in the
  single build; any span that does not is a FINDING against the
  implementation, not the class.
* **RULING 29 — THE ARBITRATION POPULATION IS THE 61 SHARED
  VERTICES, NEVER THE 7 CHAINS.**  Measured proof: two
  infeasible shared vertices carry no guilty chain at all.  The
  design proceeds now on the measurable 12 plus the census
  structure, and the 12-of-61 gap closes in TWO reads: the
  per-vertex tube dump rides the OFFLINE REPLAY first (the full
  population's SHAPE before the arbitration lands — §1a caveat
  attached: replay tubes are upper bounds, never truth), then
  the BUILD (the truth read, against pre-registered
  predictions).  The owner's sequencing is preserved: design on
  census → land → replay → build.
* **RULING 30 — THE SINGLE-BUILD MANIFEST CLOSES AT ELEVEN
  RIDERS.  The list is now law: after the spend, anything
  absent waits for a budget the owner has closed.**  Ruling
  26's eight, merged and extended: (1) W-CHORD1/W-CHORD2 with
  the string speaking, 20-bin table, assembly re-confirmation;
  (2) the solver-side invariant read (§2.2b on build witnesses;
  the 275 must read ZERO string-authored); (3) the disposition
  ledger; (4) clause-1 provenance labels (3,741 ids); (5) the
  34/34 rescue table (Ruling 28); (6) corrected ACTIONABLE-A +
  ANCHORED-STRINGS; (7) the OSM population predicate, logged at
  capture (the 7-way / 1,205 m divergence attempts OFFLINE
  attribution first and must close before the flip); (8) the
  standard denominator lines.  Added, each justified: (9) the
  PER-VERTEX TUBE DUMP for ALL strung vertices — closes the
  12-of-61 gap; its derived report is the 61-vertex
  shared-vertex join (vertex → crossing strings → per-string
  intervals → values); (10) the HOOK REWRITE MAP (node, prior
  value, written value) — "rewritten but unmoved" vs "never
  rewritten" stops being an inference; (11) BUILDING199's WELD
  — a named §6 gate that simply did not reach arm 3's log
  (recorded as an arm-3 package gap; it rides).  PLUS two
  witnesses Fable adds for the new law's first outing: the
  ARBITRATION DECISION WITNESS (per shared vertex: which branch
  fired — law-forced-bind / preference-yield /
  law-vs-law-surfaced — with values) and the HEIGHT-SELECTION
  WITNESS (per free-end span: datum count, feasible height
  interval, selected offset; audit `selected = interval
  midpoint` to float tolerance).  Separate, restated so the
  flip table is not surprised: the four-airport law-true
  battery under its OWN authorization (Ruling 26), and the §5
  gate-off identity three-way on SPLP+CYXY — cheap, not a HECA
  spend, still required before the flip because the remedy and
  arbitration add gate-on code.
* **LEDGER — THE OFFSET-CENTERLINE FINDING (numbers pending;
  no inference).**  The owner confirms HECA's apt.dat 1201/1202
  network carries centerlines offset ~15 m from the real
  taxiway centerline on SOME routes; OFF-03/30 are strings
  faithfully built on those wrong lines; chord 1 is
  demonstrably NOT offset (99.9 % within ±8 m of his way) — so
  the defect is PER-ROUTE, not global, and it reaches PAST
  strings: the spine and grade corridor are built from the same
  lines.  If confirmed, class (2b) resolves as a SOURCE-DATA
  defect — upstream of the dedup, exactly where the second
  correction placed it — and OFF-30's 62 %@1° OSM
  "corroboration" becomes suspect under the shared-stale-
  upstream caveat already recorded.  The running measurement
  (which routes; how much of an offset route's spine sits off
  its own pavement) reports numbers before anyone reasons
  further.  NOTHING about this finding is improvised into the
  single build — its remedy, if any, is upstream source law
  with its own track.  [NUMBERS IN same day — tenth block: the
  feared spine consequence is REFUTED at HECA with a named
  bound; the tie-back instrument SELF-FALSIFIED; the owner
  DISSOLVED the OFF-03/30 class.]

**THE TENTH BLOCK — THE OFFSET MEASUREMENT: REFUTED FEAR, A
SELF-FALSIFYING INSTRUMENT, AND A DISSOLVED CLASS (2026-07-31.
Spine-on-own-pavement median 100.0 % for BOTH aligned and offset
groups; zero pieces fully off pavement, zero below 50 %; the
worst cases — 40 m offset, and 1,420 m at a constant 29.4 m —
sit entirely on apt.dat row-110 pavement.  The offsets displace
centerlines sideways WITHIN wide pavement, never off it: "a 15 m
offset puts the grade corridor off a 23 m taxiway" is REFUTED at
HECA, and the owner's own prediction — bogus data, probably no
bad effects — holds on the measurable part.)**

* **RULING 31 — WHAT THE RECORD KEEPS: THE BOUND AND THE FLOOR,
  NEVER THE PERCENTAGE ALONE.**  The implementer's bound is
  adopted as spec text: the measurement rules out the corridor
  GRADING EMPTY GROUND; it does NOT establish that the corridor
  grades the CORRECT surface — a line 15 m off the taxiway
  centerline can be fully on apron pavement and still grade the
  wrong thing.  PRESENCE IS NOT CENTRALITY.  The tie-back's
  count — 11 offset pieces / 2,235 m / 4.8 %, scattered — is a
  FLOOR, not a count, and is recorded ONLY with its flaw
  attached: the instrument classified the owner's own exemplars
  as ALIGNED (OFF-03's piece at 0.0 m, OFF-30's at 2.0 m, with
  OFF-04/07 sitting 14.9 m from those same pieces), which
  resolves one way only — two OSM ways run ~15 m apart there
  and the instrument matched each piece to whichever was
  nearer, then declared alignment.  Independently confirmed by
  the dedup (OFF-04/07 stand ONLY because no apt piece lies
  within 8 m).  OSM CANNOT ARBITRATE AGAINST ITSELF.
* **RULING 32 — THE REGISTER LINE GENERALIZES (fourth instance
  today of ONE failure class):** self-matching → the 25 m
  parallel-way match → labels-as-a-population → and now a
  nearest-reference that is itself the wrong object.  The
  general form supersedes the special case: **VERIFY THE
  REFERENCE, NOT JUST THE DISTANCE — a reference population
  must be verified to CONTAIN THE RIGHT OBJECT, not merely a
  nearby one; proximity to SOMETHING is not evidence about the
  thing you meant.**  Recorded with the uncomfortable half kept
  in: each instance cost a confident wrong conclusion a later
  correction had to unwind, and three of the four were caught
  by the OWNER, not by us.
* **RULING 33 — THE OFF-03/30 CLASS IS DISSOLVED (owner ruling:
  no filter, no rule), AND CLASS (2) CLOSES.**  His mechanism,
  corroborated by our data: parallel duplicates have
  near-identical endpoints and therefore near-identical
  profiles (length pairs 299/293 m, 274/270 m), and the spine
  attaches to whichever is closest; and the pipeline's own law
  makes them harmless — decoration binds at the registry's
  0.5 m, so two strings 15 m apart can NEVER share a vertex,
  hence a parallel duplicate cannot author a §3 contradiction.
  Candidate C and its four successors are all CORRECTLY dead:
  none described anything real.  Class 2a (OFF-23) stays
  exactly where it was — one point, no predicate, DORMANT
  unless the owner brings examples.  Nothing about duplicates
  is filtered, deduped, or "fixed" anywhere in this line.
* **RULING 34 — MANIFEST AMENDMENT, ADMITTED BEFORE THE SPEND:
  RIDER (12), THE CENTERLINE REALITY REFERENCE — defined
  narrowly so the closed list stays closed.**  Amending the
  ruled list is lawful only BEFORE the spend, which this is.
  The reference is the OWNER'S MAP (the v3 denominator file) —
  the only in-hand reference independent of both OSM and the
  picked pack's 1201/1202 network, verified by the strongest
  authority we have (him), and NAMED in every output (per
  Ruling 32, no unlabelled "reality").  Content: per apt.dat
  taxi piece and per string, membership/distance against his
  map, with aligned/offset classification carrying the
  reference's name and its SCOPE limit — his map reaches only
  the acceptance domain, so outside it the offset population
  stays a floor, recorded as such.  The presence-vs-centrality
  attribution (WHICH surface each corridor grades) attempts
  OFFLINE FIRST on arm-3 artifacts; the build rider is the
  fallback instrumentation only if those artifacts lack
  corridor identity.  The Global-pack row-120 delta (0 vs
  1,044) stays a SOURCE-TRACK note (P7 step 0), never this
  build's problem.

**THE ELEVENTH BLOCK — THE STRING NETWORK SOLVE (2026-07-31.
[STATUS: HELD the same day — the owner reconsidered his own
proposal's premise before any design was implemented; twelfth
block rules what survives.  This block is PRESERVED as the
priced formulation IF intersection-agreement ever returns;
Rulings 35-37 are NOT frozen and NOT implemented.]
The owner, verbatim: "If we're not already we would, I guess
need some sort of string network solve, there's not many nodes,
but the places where they meet or cross have to agree, so the
strings have to be adjusted within their feasible band so they
all intersections agree, that should then allow the actual
taxiway solving to join smoothly right?"  His scale intuition is
measured correct: 64 string domains, 61 shared vertices — tens
of unknowns.  Fable's answer to his closing question, for
relay: YES — agreement at intersections is exactly what buys
smooth joins downstream; the taxiway solve inherits consistent
targets by construction.)**

* **RULING 35 — THE NETWORK SOLVE IS ADOPTED, AND IT UNIFIES
  THE TWO OPEN PROBLEMS.  THE FORMULATION:** the UNKNOWNS are
  ONE VALUE PER SHARED VERTEX (y_v, ~61) — agreement is
  DEFINITIONAL, not an inheritance: both strings take the same
  y_v, so there is no earlier string, no later string, no
  `xstring` authority, and Ruling 21's outlawed mechanism is
  STRUCTURALLY ABSENT rather than policed.  (The
  per-string-offset formulation — rigid shapes plus one
  translation each — is REJECTED: cycles in the crossing graph
  make rigid translation generically infeasible even when a
  lawful assignment exists; per-vertex unknowns have no cycle
  problem.)  CONSTRAINTS, all existing law and nothing else:
  per string, the y-values at its shared vertices plus its own
  absolute datums must survive the §2 tube-and-cap propagation
  without inversion — linear inequalities; the feasible region
  is a small polytope.  Absolute datums enter as fixed values;
  pinched vertices (census: |slack| ≤ 0.05 m) are effectively
  fixed; slack vertices are the degrees of freedom — the slack
  census maps onto the formulation exactly.  GIVEN the solved
  y-vector, each string solves by the EXISTING per-string taut
  machinery with its shared vertices as interior anchors —
  single-string funnel code unchanged, bends only at tube
  contacts and anchors.  SELECTION where the polytope leaves
  freedom: the owner's band-centre ruling GENERALIZES —
  maximum symmetric margin (the single-interval midpoint is
  its one-dimensional case), with uniqueness REQUIRED and
  obtained by construction (a strictly convex tie-break), so
  determinism is a theorem of the objective, not a hope of the
  ordering.  DEGENERACY CHAIN, which is the design's proof of
  shape: network solve ⊃ free-end band-centre solve (a
  component with zero absolute datums — Ruling 25 is RETAINED
  as exactly this case, subsumed, not superseded) ⊃ today's
  two-pin solve (a lone string with two datums).  DATUM
  PROPAGATION closes Ruling 22's class without any end-datum
  policy: chord 1 crosses datum-bearing strings, so its height
  arrives through its intersections; a component holding no
  datum anywhere takes band-centre.  §3's trunk-first
  ARBITRATION IS RETIRED — its ordering survives only as
  deterministic enumeration order of solver input, never as
  value authority; §2's per-string machinery, the hardened end
  policy, and "no post-harmonic inheritance" all stand
  untouched.  SCALE/BUDGET: tens of unknowns, hundreds of
  linear constraints — build-time statement required at
  landing, expected far under the 0.6 s line; solver internals
  are implementation discretion WITHIN determinism, the
  stated selection law, and the declaration law below.
* **RULING 36 — THE INFEASIBLE COMPONENT: DECLARED WITH ITS
  BINDING CONSTRAINTS, AND BOTH STRINGS YIELD — NEVER ONE,
  NEVER SILENTLY.**  A component with no consistent assignment
  is a GENUINE law-vs-law defect (feasibility-is-guaranteed:
  attribute the metric, anchor value, cap, or false topology —
  never accept as a resting state).  The solve DECLARES the
  minimal conflicting constraint set with authors and gap
  magnitude (the §2.2b arithmetic generalized from pairs to
  subsystems) and routes it to the §6.4 owner pathway.
  Emission interim, because one node carries one elevation:
  the CONTESTED vertices revert to phase-A — NEITHER string
  speaks there (symmetric yield, declared in the witness), and
  each string treats the contested vertex as a §2
  minimal-fallback boundary.  A silent single-string yield —
  any mechanism where one string quietly absorbs the
  contradiction — is FORBIDDEN; that would be the sequential
  arbitration's defect reborn inside the network solve.
  PRE-REGISTERED for the build (sharpened after the replay's
  tube dump): the 275 manufactured read ZERO; the predicted
  declared set is drawn from the 7 tightest-side-infeasible
  vertices plus 14459/20010 (the non-guilty infeasibles),
  exact membership frozen before the build.
* **RULING 37 — THE TWO PRINCIPLE READINGS, owned:**
  SINGLE-PASS — the principle forbids doing the SAME work
  twice (re-derivation, transport), not solving one system
  once; the network solve computes each unknown once, jointly,
  and RETIRES the double work the sequential design carried
  (arbitrate, then reconcile the arbitration's own
  contradictions).  Numerical iteration inside a solver is not
  task repetition; the artifact is built once.  DETERMINISM —
  previously an ordering property, now an objective property:
  same input ⇒ same unique optimum ⇒ identical output, with
  the enumeration order pinned for bit-reproducibility of the
  solver input.  INSTRUMENT LIST: NO NEW RIDERS.  Rider 9
  (per-vertex tube dump) is the solver's own input record;
  the ARBITRATION DECISION WITNESS reshapes to the network
  form (per shared vertex: solved y, feasible interval,
  margin, status — fixed-by-datum / pinched / free-centred /
  contested-declared); the HEIGHT-SELECTION WITNESS extends
  per component (datum count, residual freedom, selection).
  The manifest stays at twelve riders; the pre-registration
  table re-states in network terms before the build.

**THE TWELFTH BLOCK — THE OWNER RECONSIDERS: SOFT TARGETS AND
THE BAND-VS-IDEAL FORK (2026-07-31, verbatim: "Hmm, actually, I
think that may be wrong, because this all started trying to
eliminate a dip.  The long string (chord1?) parallel to 05C/23C
is nearly flat, but the terrain and taxiway does need to descend
below the string near the middle, the string itself can't bend,
so maybe we don't want or need string ends to match they are
just providing the 'ideal' straight path for that particular
taxiway, the taxiway will be solved according to grade law, and
having the string high above the dip, pulls the solve to
minimize the dip right?"  Not a retraction of the sixth-block
invariant — its COMPLETION: strings are INDEPENDENT ideal
targets per taxiway; reconciliation is the SOLVE's job under
grade law, never the string layer's.  The coordinator's fork
question to the owner — band-capped string vs ideal-held string
with the band suspect — is ENDORSED as the right question, with
Ruling 40's addition so his answer is implementable either way
without violating his own invariant.)**

* **RULING 38 — THE NETWORK SOLVE IS HELD, NOT ADOPTED; THE
  ELEVENTH BLOCK IS PRESERVED AS PRICED FORMULATION.**  Its
  premise — intersections must agree — is the sentence its own
  proposer has withdrawn.  Owned by Fable, kept in the record:
  Rulings 35-37 were adopted on the owner's proposal the same
  day he reconsidered it; the spec keeps both, dated, because
  deleting the formulation would delete the pricing his next
  answer needs.  Nothing of 35-37 is frozen; nothing was
  implemented.
* **RULING 39 — UNDER SOFT TARGETS THE SHARED-VERTEX PROBLEM
  DISSOLVES STRUCTURALLY (conditional on his confirmation,
  which rides the fork question).**  The mechanics, both
  required, both small: (i) `xstring` values EXIT every tube —
  no cross-anchor, hard or soft, ever again: Ruling 21 taken to
  completion (not only may a string value not BIND, strings
  need not AGREE); each string's taut solve sees only LAW —
  band, caps, clause-1 datums.  (ii) The §4 hook rewrites ONLY
  vertices claimed by exactly ONE string; a plural-claimed
  vertex is NOT rewritten — symmetric, like hard vertices,
  which the hook already never touches — and the downstream
  solve reconciles the approaching preferences under grade law,
  exactly where the owner just placed reconciliation.  Under
  these two rules the 275 manufactured contradictions become
  STRUCTURALLY IMPOSSIBLE (no `xstring` author exists to write
  them); §3's one-value policy and its hard-anchor promotion
  are RETIRED AS THE DEFECT ITSELF; and the arbitration this
  line spent the day designing — sequential AND network — need
  not exist.  Scale of the concession: 61 of 3,556 decorated
  vertices go unrewritten; every string keeps its full profile
  as target.
* **RULING 40 — RULING 22 RESHAPES: CHORD 1 NEEDS A HEIGHT, NOT
  DATUMS — AND THE HEIGHT IS THE FORK, priced so either answer
  lands lawfully.**  (a) BAND-CAPPED STRING: lawful by
  construction, but MEASURED unable to hold his ideal at the
  exact defect this line exists to fix — the band ceiling sits
  0.66-5.94 m BELOW his 111→113 line over along 1000-2400
  (§1a/§6.6), so the string would sag because its CEILING sags,
  and band-centre (his earlier answer, given under the confined
  model) sits lower still.  Under (a) the ceiling's correctness
  is load-bearing and P3c gates everything.  (b) IDEAL-HELD
  STRING, band treated as suspect: the INVARIANT PERMITS an
  out-of-band TARGET — the sixth block binds the SURFACE, never
  the preference, and a target above the ceiling pulls the
  solve to the lawful boundary nearest the ideal, which is
  precisely "minimize the dip subject to law."  BUT the CURRENT
  transport is OVERWRITE (the hook writes string values into
  `elev`; rods mint from them), under which string values
  BECOME surface values — so (b) requires EITHER the P3c
  attribution concluding the ceiling is wrong (fix the band;
  then even a confined string holds the ideal) OR a TRANSPORT
  redesign (strings as solve references, never overwrites — a
  §4-level change, priced as such, never improvised).  Under
  (b) "what defines the ideal's height" re-opens (his 111→113
  came from real-airport knowledge; the pipeline analogue is
  endpoint ground truth — the datum question in new clothes —
  or max-lawful-straight, or owner-supplied values): NAMED for
  his answer, not guessed.  Tube-confinement of the string is
  an artifact of the overwrite TRANSPORT, not of his invariant
  — that sentence rides to him with the fork.
* **RULING 41 — P3c IS PROMOTED: THE BAND-CEILING PROVENANCE
  (along 1000-2400; the 146 band-vs-anchor merge; §6.6) STOPS
  BEING DEFERRABLE ON EVERY BRANCH.**  Branch (a) needs the
  ceiling FIXED for the string to hold the ideal; branch (b)
  needs the ceiling ATTRIBUTED before the band may be called
  suspect — mechanism before fix; "treat the band as wrong"
  without provenance would be the tenth falsified mechanism's
  shape.  The standing record already points one way — the dip
  region's phase-A drag toward the 05L descent, and §2.2b's 146
  pre-existing band-vs-anchor defects "plausibly the same
  band-input defect" — a PRIOR to check, never a conclusion.
  Runs OFFLINE on existing dumps and the rider-9 tube-data
  class; the instrument manifest is UNCHANGED (rider 9 already
  carries what P3c needs).  This is now the critical path of
  the line regardless of the owner's answer.  [CONDITIONED same
  day by the chord model — thirteenth block, Ruling 45 step 0:
  P3c stays the critical path IF the band binds the SURFACE
  solve; if the band only ever bound the retired tube, the
  chord model frees the surface to ride its caps and P3c
  demotes to telemetry.  One attribution decides.]

**THE THIRTEENTH BLOCK — THE CHORD MODEL: THE OWNER RESOLVES THE
FORK AND THE CONSTRUCTION COLLAPSES TO HIS ORIGINAL SENTENCE
(2026-07-31, verbatim: "Ahh, yes, sorry for the confusion, I
meant the string's two END POINTS sit in the middle of their
band, the actual string between them is a straight line that
certainly could be above or below the feasible band, which would
just cause the solver to pull the taxiway to it's cap where
needed...  The string is always a straight chord through space,
only the end points sit in the middle of the band."  This is his
ORIGINAL sentence — "each string only has two nodes, one at
either end of the longest straight run" — which the spec has
quoted all along.  Two nodes is a chord.  The tube-following
machinery was OUR accretion on top of his model, and the
register line this earns is recorded with the rulings: RE-READ
THE OWNER'S ORIGINAL SENTENCE BEFORE BUILDING MACHINERY — when
the model sentence and the machinery disagree, the sentence was
the spec.)**

* **RULING 42 — THE CHORD MODEL, adopted whole.**  A string is
  a STRAIGHT CHORD: two endpoints, z linear in arc length
  between them, never bending, free to run above or below the
  feasible band between its ends; the SOLVER pulls the taxiway
  surface to its cap toward the chord where the chord is
  unreachable — reconciliation is entirely solve-side.
  RETAINED (the geometry side is untouched): the substrate,
  membership/dedup, composition and tenure, the walk and its
  8.0 m plan bound, `min_len`, the runway clip, decoration,
  the carriage, the disposition ledger — everything that
  decides WHERE a string is and WHAT it spans.  RETIRED (the
  elevation-construction side, by the protocol of Ruling 45,
  never silently): §2 steps 1-4 as string construction — tube
  assembly, cap-consistency propagation, the taut/funnel
  algorithm, the slope audit — `taut_chain_profile`,
  `BendWitness`, `StringDefect`'s infeasible classes, the
  (ii-b) end-datum machinery and its constant, the `no_datum`
  / `datum_infeasible` fallback classes (34 and 458 predicted
  to dissolve), §3's value machinery wholesale (one-value
  policy, hard-anchor promotion, trunk-first ordering, the
  hardened end policy — trivially satisfied and absorbed),
  and both arbitration designs (sequential AND network — the
  eleventh block stays a priced record).  The 275
  string-authored `infeasible_station` defects DISSOLVE BY
  CONSTRUCTION: no tube exists to invert and no `xstring`
  author exists to write them.  FEASIBILITY-IS-GUARANTEED
  RELOCATES: a chord is always constructible, so infeasibility
  can never again be a string-construction defect — it is a
  solve-side law question, where it belongs.  Ruling 39's
  mechanic (ii) becomes UNCONDITIONAL: the hook rewrites only
  vertices claimed by exactly ONE string; plural-claimed
  vertices are never rewritten and the solve joins the
  approaching chords under grade law.
* **RULING 43 — THE ENDPOINT LAW (the whole elevation content
  of a string is now two numbers, so their law is stated
  exactly).**  (a) Each endpoint takes the CENTRE of the band
  AT ITS END VERTEX — the owner's band-centre answer, now in
  its true scope.  (b) Where the end vertex carries no band
  (undecorated or band-None), the read WALKS INWARD along the
  string to the first banded station, distance LOGGED — a
  law-read at the nearest point where law exists on the
  string's own path: recognition, never bridging, no geometry
  moved, no value from any other string.  (c) A string with NO
  banded station anywhere emits GEOMETRY ONLY (inert,
  declared, the census-1 extraction class) — never a guessed
  height.  (d) Clause-1 anchors need no special case: where an
  anchor pins the band, the band's centre IS the anchor value
  — the law arrives through the band, not through a policy.
  (e) Clip remainders inherit THE one chord (defined by the
  pre-clip endpoints) — Ruling 18's collinearity, now true by
  definition.  (f) Chord grade vs cap is TELEMETRY, not law —
  a steeper-than-cap chord is a lawful preference; the surface
  rides its cap (the invariant covers it).  [AMENDED by Ruling
  52 (fifteenth block): TRUE for the CHORD, which is never bent
  by law — but under S1b's Dirichlet transport a both-pinned
  over-cap pair CANNOT ride its cap, so the GRIP is
  law-filtered: telemetry for the chord, law for the grip.]
* **RULING 44 — GATES RESTATED FOR A CHORD THAT CANNOT BEND.**
  W-CHORD1 becomes: worst-bin departure strictly improves from
  −11.07 (unchanged), AND every remaining surface-vs-chord
  departure bin carries a BINDING-LAW WITNESS — cap contact,
  runway conformance, clip span, or a declared solve-side
  defect; an unexplained slack departure fails the gate.  Bend
  witnesses RETIRE with the bends; the witness that replaces
  them is solve-side (per-bin departure + the binding author).
  [REFINED same day by Ruling 47 — the gate separates cleanly
  into the endpoint-identity pair and the delivery witness.]
  W-CHORD2 and building199 stand unchanged.  Ruling 19's
  invariant gate stands unchanged — now expected ZERO BY
  CONSTRUCTION, and the build still VERIFIES it (a
  by-construction claim is measured once before it is
  trusted).
* **RULING 45 — THE RETIREMENT PROTOCOL (retirement is a
  measured step; at this scale, four measured steps — nothing
  is deleted before its step passes).**  STEP 0, the one
  load-bearing mechanical unknown, attributed FIRST: WHERE
  DOES THE BAND BIND?  If `node_band` constrains ONLY the
  retired tube, the chord model frees the surface to ride its
  caps toward the chord — the owner's "pull to cap" works
  as he describes, and the sagging ceiling (0.66-5.94 m below
  his ideal) constrained only our accretion: P3c DEMOTES to
  telemetry.  If the band ALSO binds the surface solve, the
  surface stops at the sagging ceiling short of his chord, the
  dip persists, and P3c REMAINS the critical path (Ruling 41).
  Code-level attribution plus a replay mask, offline, before
  anything else.  [ANSWERED same day — fourteenth block: the
  band binds BOTH consumers; the surface solve clamps every
  node into `node_band`.  P3c is the critical path; the
  dip-headroom question (~6 m under the ceiling, pre-arm-3,
  not current) goes to the BAND dump.]  STEP 1, the
  PULL-MECHANISM VERIFICATION,
  offline replay (§1a: an upper bound): chord targets through
  the EXISTING transport; measure — surface departs the chord
  only where a binding law explains it; the 275 read zero; the
  34 `no_datum` spans SPEAK; W-CHORD1's direction.  STEP 2,
  removal: only after step 1 confirms — each retired module
  goes with its tests retired or converted;
  `assemble_maximal_strings`' long-pending retirement folds
  into the same wave; §5 gate-off byte-identity re-proof
  (SPLP+CYXY three-way) AFTER the removal.  STEP 3, the ONE
  build per the reshaped manifest.  The owner's budget ruling
  is unchanged by all of this: nothing builds until steps 0-2
  are done and the pre-registration table is restated in chord
  terms.
* **RULING 46 — THE MANIFEST, RESHAPED ITEM BY ITEM (count
  unchanged; nothing added, nothing silently dropped).**
  Rider 9 (per-vertex TUBE dump) reshapes to the per-vertex
  BAND dump — still load-bearing (step 0, P3c, endpoint
  reads).  The 61-shared-vertex join reshapes to the
  DISSOLUTION VERIFICATION: the plural-claim skip ledger
  (exactly which vertices the hook skipped) plus the 275
  reading zero.  The ARBITRATION DECISION WITNESS retires with
  the arbitration; the HEIGHT-SELECTION WITNESS reshapes to
  the ENDPOINT WITNESS (per string: end vertices, band
  [lo, hi] at each, centre taken, inward-walk distance, chord
  grade).  Bend-witness consumers reshape per Ruling 44.
  Everything else stands as ruled: disposition ledger,
  clause-1 provenance (still serves Ruling 19 attribution and
  P3c), W-CHORD1/2, the invariant slice, OSM population
  predicate, denominators, the reality reference, building199,
  the rewrite map (now trivially auditable: linear values),
  ACTIONABLE-A + ANCHORED-STRINGS.
* **RULING 47 — THE PROJECTION RECORDED (with its substitution
  attached, as delivered — a projection, never a gate reading),
  AND THE GATE SHARPENS INTO A PAIR.**  Chord 1 under the chord
  model, with band-centre STOOD IN by each end bin's emitted
  median (exact for shape; only as good as that substitution
  for level): worst bin moves from −11.07 m at along 1800 to
  −1.07 m at along 3800; at the dip the chord sits 10.32 m
  ABOVE the emitted surface.  THE STRUCTURAL SENTENCE, adopted
  as spec law because it is the design's proof of shape: a
  straight line measured against a straight line differs
  LINEARLY, so its extremum sits at an END, never mid-span —
  THE MID-SPAN SAG IS UNREPRESENTABLE under the chord model,
  exactly as open-terrain crossing is unrepresentable under
  the walk.  The simplification does not improve the defect;
  it removes the defect's CLASS from the output space.
  W-CHORD1 THEREFORE SEPARATES INTO TWO GATES, both required:
  (A) STRING IDENTITY — the chord's two endpoint values
  against the owner's line, ε ≤ 0.50 m each (R3's ε; the
  linear-difference maximum is an endpoint, so two numbers ARE
  the whole comparison).  Projected today: north 0.46 m —
  clears, but by 0.04 m ON THE SUBSTITUTION, so it is an OPEN
  number, not a pass; south 1.08 m — the single thing between
  this construction and gate (A), pre-registered as the first
  question the REAL band read answers: either band-centre at
  the south vertex differs from his value (the relocated-P3c
  question in its first concrete instance) or the substitution
  erred.  Neither endpoint number is settled until rider 9's
  band dump replaces the stand-in.  (B) SURFACE DELIVERY —
  Ruling 44's binding-law witness over every surface-vs-chord
  departure bin, with strict improvement from −11.07 as the
  headline.  (A) without (B) is a beautiful target never
  delivered — arm 3's lesson; (B) without (A) is faithful
  delivery of the wrong line.
* **RULING 48 — P3c RELOCATES TO THE ENDPOINTS, AND STEP 1
  WIDENS TO THE WHOLE INVENTORY.**  The band stops mattering
  across the span and starts mattering ACUTELY at exactly two
  stations per string (~128 stations): a band centre inherited
  from a sagging neighbourhood would re-import the dip THROUGH
  THE ENDPOINT rather than through the span.  Accordingly:
  the ENDPOINT WITNESS (Ruling 46) gains the band's
  PROVENANCE at each endpoint — which anchors reached it via
  the route metric (the §2.2b authorship unwrapping already
  proved this recoverable) — value AND author, per endpoint.
  Ruling 45 STEP 0 is unchanged (where does the band bind);
  its P3c consequence now reads at the endpoints.  Ruling 45
  STEP 1's scope WIDENS explicitly: the pull-mechanism
  verification covers ALL 64 chords, BOTH signs — the owner
  has licensed chords to leave the band, so below-band and
  above-band behaviour at scale, with departures binding-law
  explained per string, is a stated open question the replay
  answers, never an assumption.  The projection's own caveats
  ride with it in the record: endpoints assumed where the walk
  put them (holds — the geometry side is untouched), nothing
  claimed about the other 63 strings, nothing about solver
  behaviour at scale.  It answers exactly one question —
  chord 1's defect is closable by this construction — and
  that answer is now on the record with its conditions.

**THE FOURTEENTH BLOCK — STEP 0 ANSWERED, AND THE ENDPOINT READ
LAW (2026-07-31.  Ruling 45 STEP 0 is ATTRIBUTED from code, two
structurally independent band consumers: the retired tube
(`taut_string._band_walls`) AND the surface solve —
`one_solve.one_profile_solve` reads `node_band` directly and
clamps EVERY node ("the per-node (floor, ceiling) the solve
clamps into"; "applied to EVERY node, the apron body included").
THE BAND SURVIVES THE TUBE'S RETIREMENT: a chord above a sagging
ceiling cannot pull the surface past that ceiling — "pull to
cap" operates INSIDE the band, never through it.  Ruling 41's
conditional RESOLVES: P3c IS THE CRITICAL PATH.  The tension,
flagged not resolved, rides with it: the prior finding recorded
HECA's dip profile ~6 m UNDER the ceiling — the band can bind in
MECHANISM while being non-binding at that dip; if that headroom
still holds, chord 1 closes under the chord model; the figure
predates arm 3 and is NOT current — the BAND dump resolves it,
doubly justified.  Also kept, the coordinator's own correction:
the two-numbers-give-every-node-a-target description is the
TARGET state, not present behaviour — today's hook has no
interpolation anywhere; THE RETIREMENT IS NOT A SIMPLIFICATION
OF THE VALUE PATH, IT *IS* THE VALUE PATH.  And the endpoint
measurement, proxy-graph labelled: 108/170 endpoints (63.5 %)
coincide with a graph node at the 0.5 m identity; 62 (36.5 %) do
not — sharply bimodal (p50 0.00, p75 2.85, p90 48.64 m;
firing-case median 14.2 m, max 97.9); Ruling 43(b) fires on 44
of 85 strings — A MAIN PATH on the input that supplies 100 % of
a string's elevation content.  The owner's expectation that
endpoints ARE centerline nodes holds only where the graph
exists; the flagged-unclaimed mechanism — OSM standing runs are
5 m RESAMPLE STATIONS, synthetic points with no reason to land
on a node — awaits its measurement below.)**

* **RULING 49 — THE ENDPOINT READ LAW: NO SNAP; READ THE LAW AT
  THE TRUE LOCATION BY INTERPOLATION; CLAMP ONLY BEYOND THE
  GRAPH — AND THE OFFSET IS A FIRST-ORDER QUALITY METRIC.**
  SNAPPING ENDPOINT SELECTION TO GRAPH NODES IS REJECTED: it
  moves geometry the chord model froze as retained; it needs a
  radius constant (the shipped-constant trap); the small
  bimodal mode is solved exactly without it; and for the large
  mode a snap IS the walk-inward clamp wearing a different
  name, while also mutating plan geometry and multiplicity
  mid-acceptance.  THE LAW, by mode: (1) DIRECT — the end
  vertex is a node: read its band (63.5 % today).  (2)
  BETWEEN-NODE — the endpoint lies inside graph coverage
  between two bracketing nodes on its route: the band [lo, hi]
  is INTERPOLATED to the endpoint's along-station.  A READ of
  a law field at a point, not bridging: nothing crosses a gap,
  no identity is minted, no geometry moves — and it makes the
  p75 ≈ 2.85 m mode EXACT with zero new constants.  (3)
  BEYOND-GRAPH — the endpoint lies past the outermost banded
  station (the OSM-tail mode): the read CLAMPS to that
  outermost station (Ruling 43(b) as written), the chord
  EXTENDS over the tail by its own linearity (two points
  define it everywhere; extension adds no information), and
  the tail is DELIVERY-MOOT BY CONSTRUCTION — no nodes exist
  there, so the hook rewrites nothing regardless; the tail
  matters only to gate (A), where the clamp-to-end offset ×
  chord grade is REPORTED as that endpoint's uncertainty term,
  never hidden.  INSTRUMENTATION: the ENDPOINT WITNESS gains
  read MODE (direct / interpolated / clamped), the offset, the
  bracketing nodes, and the tier; ORDERED offline (zero
  builds): the 62 decomposed by mode and tier — the
  5 m-resample mechanism gets its measurement instead of its
  plausibility.  The beyond-graph population is the
  graph-coverage gap measured a THIRD way and feeds the
  census-1 extraction track.  RELAY for the owner: his
  expectation is TRUE where the centerline graph exists, and
  no selection rule can conjure law where it does not — that
  remainder is the known extraction gap, not an endpoint
  policy choice.

**THE FIFTEENTH BLOCK — S1b SPECCED, PRICED, AND SCOPED FOR THE
OWNER'S TONIGHT DEADLINE (2026-07-31, late.  S1's measurement
landed: `f1b13c3` — chord model in production, defects 949 → 0
by construction, 113 tests green, gate-off proved, value path
73.5 ms = 43 ms cheaper than the funnel; endpoint band centres
vs the owner's CIFP data +0.07 m at 05C / +0.61 m at 23C — the
23C number is the carried-open Ruling 47/48 endpoint-provenance
question, now concrete.  The gate-ON HECA arm running tonight is
the α BASELINE ARM.)**

* **RULING 50 — S1b IS PRICED AND SPECCED:
  `docs/specs/s1b-first-class-chord-boundaries-spec.md` (its own
  Opus-executable document; this block is the pointer, that file
  is the law).**  THE PRICING: the chord model collapses
  S1b-core to THREE SEAM-LEVEL EDITS — (1) the chord-target
  computation moves ahead of the harmonic inside
  `_solve_spine_profile` (call-site move of landed code, gated,
  function-local import); (2) the targets enter the harmonic as
  DIRICHLET pins through the solver's EXISTING fixed-value
  mechanism (hard > string; plural-claim never pinned;
  pre-freeze anchor set — all S1 law carried); (3) the
  post-phase-A overwrite and the phase-A-internal taut pass on
  assembled strings RETIRE, mask-before-delete.  The harmonic
  demotes to residual gap-filler with string boundaries — the
  ordained S1b, at a fraction of its ordained size, because a
  string is now two numbers and a linear evaluation whose every
  input exists before the harmonic runs.  DEFERRED OUT,
  explicitly: the DRAW-TOWARD re-founding (projection out from
  the string web, R as instance, layer 6 shrink) — a
  reference-system redesign, not an evening edit; service 4b
  untouched.  GATES G1-G5 pre-registered in chord terms against
  the α arm; S1b adds ZERO builds (verification folds into the
  owner's planned tile build + suite read; SPLP+CYXY identity
  three-way stays the cheap non-HECA proof).  EXPECT-DIVERGENCE
  clauses name the one real hazard class: consumers reading
  elev between the harmonic and the old hook point (couple_adj,
  spine_floor, §7 z_ref snapshots, the quarantine blend) —
  enumerated first, any must-see-pre-string consumer is a STOP.
* **RULING 51 — R2 IS BLOCKED TONIGHT, twice over (the
  coordinator's read CONFIRMED):** R1's precondition is unmet
  (`O4_REFERENCE_FIELD` default "0", CP2 unread) AND S1 just
  changed R1's own layer 4 (spine layer = chord), so R1's gates
  re-read BEFORE anything enforces against them — offline, on
  tonight's build artifacts, no extra spend, but not by
  morning.  "Found the tube on chord targets directly" is not a
  shortcut: partial-coverage chords as a tube centre IS the
  deferred DRAW-TOWARD design.  Sequence: S1b-core tonight →
  R1 layer-4 re-read (offline) → R1 CP2 → R2.
* **RULING 52 — THE LAW-FILTERED GRIP (S1b step 0 surfaced the
  pins-vs-Ruling-19 conflict; ruled the same night; full law in
  the S1b spec §1 edit 2).**  S1b's step 0 was CLEAN — no
  §5(i) class-(b) consumer exists (`couple_adj` reads no elev;
  `spine_floor` is a pre-phase-A input; §7 `z_ref` snapshots
  already sit downstream of the old hook), §5(v) is satisfied
  by the existing `anchors` mechanism, pin/hard conflicts 0.
  But pins-in-anchors makes 3,223 spine pairs both-anchored,
  and 76 of them (2.36 %; excess max 0.584 m) carry chord
  grades over their cap budget — the exact cap projection
  leaves both-anchor pairs alone, so those 76 would be
  STRING-FORCED over-cap pairs: Ruling 19's required-zero
  class, latent under α, surfaced by S1b, frozen by
  `base_hard` after phase A.  THE RULING: pins join `anchors`
  (forced), AND the pin set is LAW-FILTERED first — no pair
  may remain both-pinned where the chord grade between the
  pinned values exceeds that pair's cap (strict >, the
  existing 1e-9 audit epsilon).  THE CHORD IS NEVER BENT BY
  LAW; THE GRIP IS.  Releases are minimal, deterministic,
  endpoint-protective, never touch a law anchor, and are
  WITNESSED (the grip-yield witness — Ruling 44/47(B)'s
  delivery gate reads released spans as cap-contact departures
  with their author named).  Ruling 43(f) amended (telemetry
  for the chord, law for the grip); Ruling 21 untouched (it
  governed strings gripping EACH OTHER; a pin grips the
  string's OWN pavement); Ruling 19 back to zero BY
  CONSTRUCTION.  Accepting the 76 was rejected (fails Ruling
  19 outright); solver-moved pins were rejected (launders the
  yield, destroys attribution).  Pre-registered: the release
  population ≈ the 76-pair class; chord 1 unaffected
  (near-flat); materially more releases is a FINDING before
  G1 is trusted.  [LANDED same night, pre-registration HELD on
  both counts: 3,470 offered → 3,429 kept / 41 released over 79
  over-cap pairs (1.18 % of pins); excess median 0.000 /
  p90 0.081 / max 0.584 m; ZERO releases on chord 1.  G2
  amended form on the delivered arm: max |emitted − chord| at
  kept pins = 0.000e+00 exact through harmonic, fairing AND the
  cap projection; completeness zero; witness reconciles 79 → 41
  minimal.  Implementation notes adopted into the record: strict
  > at the existing 1e-9 epsilon; both-law-anchor pairs never
  touched; endpoint-protective ordering; and a RE-ADMISSION PASS
  so minimality is VERIFIED rather than assumed by a greedy
  stop.  The owner's invariant is now STRUCTURAL at the pin
  layer.]
* **RULING 53 — THE PHASE-A TAUT PASS: KEEP-AND-RESCOPE.  The
  §3 mask FIRED as designed (567 of 3,697 unstrung spine
  vertices move, max 0.283 m; pinned 0 of 3,429; off-spine 0 of
  123,929; both arms `graph=None`, labelled) and the finding
  re-frames the deletion: the pass strings ALL spine corridors,
  and with pins in `anchors` it is PROVABLY INERT on strung
  ground — its whole remaining effect is unstrung spine.  It
  has stopped being a competing string constructor and become
  the RESIDUAL SPINE SMOOTHER on ground S1 does not claim.**
  The §1b ordination ("the internal taut pass on assembled
  strings is deleted there") is SATISFIED IN SUBSTANCE — on
  assembled strings it is structurally dead; the surviving code
  is a different-domain mechanism.  Deleting tonight would hand
  567 vertices to harmonic+fairing alone with an unmeasured
  0.28 m-class surface change — deleting through a fired STOP,
  and retiring by NAME where the DOMAIN no longer overlaps: the
  inverse of the lesson that produced the chord model.  Four
  guards in the S1b spec §3: G2 is the standing inertness gate;
  the domain is spec-named (unstrung spine, fairing-class
  authority, never string authority; spec name "the residual
  spine smoother", code rename deferred to hygiene); the mask
  table is the recorded footprint and the baseline for any
  future retirement measurement; harmonic-alone-vs-smoother on
  the residual domain is a deferred MEASURED question,
  pre-registered before it runs, pulled earlier only if the
  suite read shows unstrung-spine regressions (first suspect:
  the pass's changed inputs — it now sees pinned boundaries).
  Endorsed alongside: G4's SPLP+CYXY three-way identity builds
  (authorized by the coordinator; code-level proof — gate
  unset, module never imported, ungated AST refs [] — is
  necessary, the byte identity remains the standard); §5(iv)
  iteration-count read folds into the tile build, recorded
  never tuned.
* **RULING 54 — THE `yield_hard` ENUMERATION: A DEFECT FOR
  PINNED VERTICES, DESIGN FOR THE REST — AND THE FIX IS THE
  GRIP, NOT THE FREEZE.**  The finding (candidate correctly
  labelled, masking arm authorized as a gated DIAGNOSTIC, not
  landed): at chord 1's dip, target 112.64 / ceiling 105.99 /
  hook-time 107.20 / delivered 101.12 — 6.64 m is the lawful
  band clamp (owner-ruled: the 05L/23R cross-connectors), and
  **4.87 m is the surface below its own ceiling with nothing
  holding it there**; the same-string control at along 2403
  tracks within 0.5 m where the band admits the chord.  The
  construction site: `yield_hard` (solve.py:1351) is REBUILT
  from `truth_hard | runway_nodes | building_seats | _gs_hard`
  and never inherits the phase-A spine freeze, so fp#8
  (:1392) and the finals (:1892, :1988) may move every
  phase-A-frozen spine node — the standing quarantine-blend
  prior, now with a construction site in THIS tree.  THE
  VERDICT, forced by this line's own law: a blend is NOT grade
  law, so a blend dragging a lawful strung value below its own
  ceiling is the string overruled by a non-law — the owner's
  invariant violated in the emitted surface; equivalently, the
  4.87 m class is a Ruling 47(B) departure bin with NO
  POSSIBLE binding-law witness (no cap contact, no clamp, no
  runway, no clip) — "an unexplained slack departure fails the
  gate" already convicts it.  The blend's own retained purpose
  ("keep only for genuine band inversions") does not cover a
  station with 4.87 m of admitted headroom.  DEFECT.  But the
  case-for-design is answered IN THE FIX, not dismissed: the
  yield step exists to free nodes, and wholesale inheritance
  of the ~3,700-node spine freeze would over-freeze the
  unstrung residual domain (the smoother's ground, junctions,
  sub-min runs) that has no string authority and MUST yield —
  the freeze was never the right object; THE KEPT PIN SET is.
  THE FIX'S SHAPE: `yield_hard` GAINS THE LAW-FILTERED KEPT
  PINS (the Ruling-52 set, 3,429-class) — and nothing else.
  Unstrung spine stays yieldable (design ratified there).
  Wholesale freeze inheritance REJECTED (over-freezing);
  excluding pins from the blend alone REJECTED (under-scoped —
  :1892/:1988 also take `yield_hard`, and hard membership is
  the EXISTING protection idiom; no new mechanism).
  Consistency: a pinned node behaves during yield exactly as a
  truth anchor already does — neighbours reconcile against a
  lawful fixed value or DECLARE, and a neighbour-vs-pin
  conflict is the surfaced class with authors, never silently
  absorbed.  Ruling 52's precedence carries: law is never
  released; where a genuine LAW demand reaches a pinned vertex
  at yield time, that is a declared conflict for attribution,
  not a silent un-pin.  PRE-REGISTERED for the diagnostic arm
  (so it cannot be read backwards): at the dip, delivered
  rises from 101.12 to the ceiling-clamped chord ≈ 105.99 at
  pinned stations — the owner's stated ~106; the 6.64 m clamp
  REMAINS and now carries its band-clamp witness; the 4.87 m
  closes to ~0 at pinned vertices; clamp-boundary transitions
  emerge as cap-lawful ramps (pin-to-free pairs are the cap
  machinery's), not steps; unstrung spine and off-spine
  unchanged by construction.  The arm CANNOT show
  breaks-elsewhere (adopted): that needs the gate set —
  law-true counts and declared-defect deltas vs tonight's arm;
  pre-registered there: zero new law-true violations
  attributable to pin-holding, and any neighbour-vs-pin
  declarations small-with-authors.  ANOMALY, resolved before
  the arm is read: hook-time 107.20 ABOVE ceiling 105.99 at
  the cited station — either a station-alignment artifact in
  the report or a real hook-time band violation; the arm
  reports (target, ceiling, hook, delivered) aligned on ONE
  station definition before any number is quoted.
  [CONFIRMED IN PRODUCTION same night: delivered at the dip
  106.40 / 106.90 vs the owner's stated ~106 — +5.18 m from
  S1b; worst bin −11.07 → −10.74 → −5.83 and MOVED off 1800
  (the owner's dip is GONE; the residual is a different,
  shallower station); pre-registration ≈ 105.99 MET;
  `n_defects` 0, rc 0.  And the wholesale freeze recovered the
  SAME ~5.2 m — the narrow object was SUFFICIENT, so the
  over-freeze rejection is vindicated by measurement, not only
  principle.]
* **RULING 55 — PINS AND THEIR CAP-COUPLED NEIGHBOURS: THE
  NEIGHBOUR INHERITS NO FREEZE AND NO NEW MECHANISM — IT
  ALREADY OWES THE PIN EXACTLY ONE THING UNDER LAW, THE CAP;
  THE DEFECT IS ANY STAGE THAT MANUFACTURES AN OVER-CAP PAIR
  AGAINST A HARD NODE.**  The evidence naming one shape: G2
  fails in production (offline 0.000e+00; build median 0.2342 /
  p90 1.1407 / max 6.9008 over 1,580 of 3,790 pins MATCHED —
  population caveat below) and `n_pin_yield_conflicts` = 874 =
  786 `free` + 88 `law_anchor`, excess median 1.616 / max
  14.682; chord 1's 1400-1800 bin holds 7 `free`-class
  conflicts (max 7.92) and W-CHORD1's residual worst bin moved
  to 1600 — THE CONFLICTS AND THE RESIDUAL SHARE A STATION.
  The shape: the pin cannot move directly (`yield_hard`), the
  blend moves its UN-pinned neighbour, the pair goes over-cap,
  and something later drags the pin — Ruling 54's defect ONE
  HOP REMOVED: the string overruled by a blend TRANSITIVELY
  through the cap.  THE LAW: no stage may MANUFACTURE an
  over-cap pair against a hard node — stated for ALL hard
  nodes, pins AND truth anchors alike (the 88 `law_anchor`
  conflicts show the same violation against anchors, so this
  was never pin-special; the "behaves exactly as a truth
  anchor" sentence holds — and now indicts the machinery
  around BOTH).  Mechanically: a yield/blend candidate
  adjacent to hard nodes moves within the §2-step-2 interval
  [hard ± cap·d] intersected with its own law — BOUNDING,
  never freezing.  The named trap is avoided because cap·d is
  the LAW's own freedom, not ours: corridors still descend
  away from pins at cap rate — the owner's model, enforced at
  yield time instead of repaired after.  Freezing the free
  neighbours REJECTED (the wholesale freeze by another name);
  doing nothing REJECTED (leaves pins overruled by blends
  transitively).  MECHANISM BEFORE FIX — candidates are
  unseparated and the fix lands only after this decomposition:
  (i) THE JOIN FIRST — 2,210 of 3,790 pins unmatched at 1 m
  proximity is the VERIFY-THE-REFERENCE register live in our
  own instrument (nearest-within-1 m is the wrong-object
  join); the pin→delivered join re-states on CANONICAL
  identity, and G2 re-reads on the identity-joined population
  before ANY departure number is trusted; (ii) the MOVER
  LEDGER — per conflict, which stage last moved the free
  member (stamp if cheap, report if not); (iii) the
  `law_anchor` 88 against the α arm — pre-existing or new, one
  artifact comparison; pre-existing ⇒ its own track, not this
  line's.  PRE-REGISTERED for the fix arm: identity-joined G2
  at pins returns to the 0-class where neighbourhoods are
  lawful; manufactured conflicts 874 → ~0; the 1600 residual
  closes toward band/cap-explained; hard-adjacent yield
  infeasibilities surface as DECLARED conflicts
  small-with-authors — a LARGE declared population is a
  finding (the pin web over-constraining the yield network)
  that returns here.  ALSO CLOSED on this run's evidence:
  fragmentation is OURS, decisively (chord 1's 239 corridor
  boundaries: turn 2 / tenure 113 / route_end 63 / consensus
  61; the 24.94 m was a filter artifact, real 8.64 m; the
  owner's morning intent question WITHDRAWN) — a future work
  item, not tonight's.  STILL UNGATED, endorsed: the
  string-attributed law-true slice — `n_defects` = 0 does not
  speak for it.

Service corridors are EXCLUDED (their reference is the DEM-follow
shape — spec §4.1 layer 4 exception).  Runway profiles are EXCLUDED
(FAA profile machinery owns them).

Per assembled string, in this exact order:

1. **Tube assembly.**  Per vertex i: interval `[lo_i, hi_i]` =
   intersection of (a) the reach band at i (`node_band`; off-net ⇒
   unconstrained at that vertex), (b) any hard local law box already
   recorded for i.  Clause-1 anchors on the chain (runway-crossing
   values, tile-seam pins, CIFP-derived values) become degenerate
   intervals `[z_a, z_a]`.  Chain ENDS take their end policy from §3.
2. **Cap-consistency propagation.**  Two sweeps (forward, backward)
   with the per-segment longitudinal cap `g_k` (the corridor's law cap
   from `config.taxi_grade_cap_for_letter` via the segment's route —
   1.5 % default class):
   `hi_i ← min(hi_i, hi_{i-1} + g_k·Δs)`, `lo_i ← max(lo_i,
   lo_{i-1} − g_k·Δs)`, then mirrored right-to-left.  If any
   `lo_i > hi_i` after propagation: **infeasible station — declared
   defect** carrying both binding authors (which anchor/band value
   propagated each side) and the gap magnitude (clause 8: attribute,
   never drape-tune).
   **FALLBACK GRANULARITY — REVISED 2026-07-31 (arm 1 measured the
   original whole-chain policy turning ~179 clustered stations into
   an 81 % fallback rate, chord 1 included; the granularity question
   was never considered when this clause was written — owned):
   MINIMAL FALLBACK.**  The fallback extent is the INFEASIBLE RUN
   only (contiguous empty-tube stations, which keep their phase-A
   values locally); the feasible spans on either side become
   sub-strings, each strung by its own taut chord (steps 3-5).  The
   facing span-ends do NOT blend across the defect — the value gap
   between them IS the surfaced contradiction, reported in the
   witness (authors, gap, fallback extent), never smoothed.
   Whole-chain fallback is RETIRED.  Feasibility-is-guaranteed
   governs the defect list: every `infeasible_station` is classified
   by the §2.2b arithmetic and routed to attribution, never accepted
   as a resting state.

   **§2.2b — surfaces-vs-creates arithmetic (directed 2026-07-31;
   ZERO builds; precedes arm 2):** for each defect's author pair
   (z_A, z_B; along-string distance d; cap g): |z_A − z_B| > g·d ⇒
   the anchors are lawfully incompatible along the route INDEPENDENT
   of Stage 0 — pre-existing law defect, SURFACED not created;
   |z_A − z_B| ≤ g·d with the tube still inverted ⇒ MANUFACTURED by
   tube assembly/propagation — constructor-side, ours.  Classify all
   defects (+ `no_datum` separately) and name each author's clause-1
   class (crossing / seam / CIFP-derived).  Pre-existing entries
   feed the §6.4 owner pathway; manufactured entries are S1 bugs to
   fix under the normal loop.
   **MEASURED (2026-07-31, arm-1 data; the recorded `lo−hi` excess
   IS the required quantity — S1's correct recognition, no
   re-derivation): ≥ 146/179 SURFACED.**  The 146 band-vs-anchor
   cases carry a provably pre-existing author (`node_band` is built
   at solve.py:683, before the hook, never written by S1); excess
   median 1.515 m / max 1.618 m; 2/179 numerical (≤ 5 cm), 129/179
   material (> 0.5 m).  These MERGE with P3c's band-provenance
   question into ONE §6.4 owner presentation (plausibly the same
   band-input defect).  The 33 anchor-vs-anchor cases are
   UNDECIDABLE until arm 2's `anchor`/`xstring` relabel (installed
   at the call site; frozen signature untouched) distinguishes
   clause-1 anchors from S1-minted earlier-string values — claimed
   neither way, per the §1a rule.
3. **Taut string.**  The classic taut-string/funnel algorithm through
   the propagated tube from the chain's start value to its end value:
   piecewise-linear, bends ONLY at tube contacts, O(m).  This IS the
   owner's sentence as an algorithm: the straight chord when it fits;
   otherwise the minimal-bend lawful path.
4. **Slope audit (safety net, not a tuner).**  Assert every output
   segment |slope| ≤ g_k + 1e-9.  A violating segment is a **declared
   defect** (report with the segment and its flanking contacts) and
   the chain falls back as in step 2.  Never silently clip.
5. **Bend witnesses.**  Every bend: station, side (floor/ceiling),
   the constraint author (band-from-anchor via route metric / local
   box / anchor value), chain id.  Stored compactly in the node-space
   store (keyset+payload artifact `string_bends`) and dumped as CSV
   when `O4_STRING_WITNESS_DUMP=<path>` is set.  W-CHORD1's "declared
   bend" gate reads THESE witnesses.

## §3 Junctions between strings (the one ordering rule)

A vertex shared by 2+ assembled strings takes ONE value.  Frozen
policy — **trunk-first, deterministic**: strings sorted by (priority
class, length descending, stable id); priority classes: (1) runway-
parallel trunk strings, (2) cross/connector strings, (3) the rest.
A vertex already valued by an earlier string becomes a hard anchor
(degenerate interval) for every later string that shares it.  One
pass, no iteration (single-pass principle).  This reproduces the
owner's picture at HECA by construction: chord 1 (the trunk, ONE
maximal string after Stage 0) gets its straight ~111→113 string
first; chord 2 then anchors on it at the junction and runs its own
taut string outward toward 05L — descending lawfully, which is
exactly the seam's W-CHORD2 target.
**End policy (HARDENED by the §1b ordering ruling — this is where
the harmonic's 67 % could leak into S1's output):** a string end is
one of exactly three classes: (i) a clause-1 anchor — its value;
(ii) shared with an earlier string — that string's value (§3 order);
(iii) a TRUE TERMINAL — solved FREE by the constructor (the taut
string with a free boundary; the tube decides where it rests).  No
assembled-string end inherits a phase-A (post-harmonic) value.
**CLASS (ii-b) — TRUNK END DATUMS.  OWNER-CONFIRMED 2026-07-31
(verbatim: "ii-b We can try using the anchor governed fabric
already there").**  The chord corridors carry ZERO interior hard
anchors (measured §1a; arm 2's `no_datum` 21→32 is the signature),
and the owner's hierarchy read carefully is a DATUM FLOW — "strings
between anchors" means the string's BOUNDARY data comes from the
anchor-bearing network it welds into, not that anchors sit on its
interior.  Corroboration at the adopted extremities: chord 1's ends
measure 110.54/111.92 against the owner's own 111/113.

*Operationalization (normative):* a trunk end takes as its datum the
LIVE (hook-moment) value of the canonically-adjacent junction-complex
fabric node at the end — **implemented and review-accepted 2026-07-31
as: the nearest NON-SPINE neighbour, deterministic tie-break, no band
read** — ACCEPTED iff a clause-1 anchor lies within
`TAUT_STRING_END_DATUM_ANCHOR_RADIUS_M` (config.py, initial 250.0 —
measured cover for the ~107 m nearest-anchor distance at chord 1;
measured-not-sacred, do-not-widen recorded at the constant, S1-CP2
reviews it) of the end through the spine graph (bounded Dijkstra).  No anchor within radius ⇒ the end STAYS class (iii) free and
is counted — the anchor-proximity gate is what keeps the harmonic-
contamination door shut (§1b): only anchor-governed fabric may hand
values in.  ENDS ONLY, per the owner: mid-trunk split spans stay
datum-poor BY DESIGN pending the §6.4 rulings — counted
consequences of the surfaced contradictions, never engineered
around.  The §3 trunk-first ordering STANDS.

*"We can try" is a DIRECTIVE TO MEASURE, not a premise to build on*
(the owner's framing is explicitly provisional): if the route graph
cannot solve within grade against adopted trunk-end datums, that is
a LAW DEFECT TO ATTRIBUTE per feasibility-is-guaranteed — declared
as `datum_infeasible` naming the adopted value and the binding
constraint, routed to the §6.4 filing — NEVER a softened datum,
NEVER a silent band-seat retreat.  Acceptance measurement:
(offline, first) construction re-run on the arm-2 graph with
adopted end datums — chord 1 strings end-to-end modulo the
§6.4-pending defect splits, with ZERO new defects AUTHORED BY the
adopted datums; (arm 3, one held HECA) W-CHORD1 strictly improves
from −11.07 with residual departures witness-covered.

*Why adopted fabric and not a band-derived seat (rationale recorded
so no future reader "improves" this back):* a band seat would
INHERIT the very contradictions already routed to §6.4 — 137 of the
≥159 surfaced are band-vs-anchor, and seating the string on a band
read would anchor it on values in active contradiction with the
bands constraining it.  Adopted fabric carries NO band read: the
lower-coupling option, not merely the cheaper one.

*STAGE-1 MEASURED OUTCOME (2026-07-31, on the state capture —
chord-1-scoped acceptance FAILED as declared, the gate working):*
137 datums adopted / 281 ends free-and-counted; fallbacks 231→197;
**45 `datum_infeasible` against the required zero** — routed to
§6.4 as **CLASS D, the first defects in this line authored by an
owner-ruled mechanism** (presented as the "we can try" report-back
the owner asked for), AFTER the §2.2b-style classification of all
45 on the capture (adopted value vs the other binding author over
d at cap; author classes named).  HYPOTHESIS framed per §1a, not
acted on: the radius gate is a PROXY for governance — proximity to
an anchor does not guarantee the adopted neighbour's value is
anchor-governed rather than drape-contaminated.  NO radius tuning
in either direction pending the classification (do-not-widen AND
do-not-narrow).  Chord-1 assembly reached 58.5 % along-span
(orphans 0); the north-end shortfall is provisionally an ASSEMBLY
question (dead-parallel segments measured inside the uncovered
region), settled by the owner's map; the 1652 stop attribution
runs offline on the capture (Stage 0 is pure — per-end stop
reasons + candidate inventory at the terminus).
Phase-A values survive ONLY on fallback pieces (§2), and the
assembly inventory reports that count for S1-CP2.  Chord 2 is
thereby fully harmonic-free by construction: top end anchors on the
trunk, bottom end on the 05L-side crossings — the lawful descent
into the owner's 103-106 band is the constructor's own product.
The end inventory is reviewed at S1-CP2 with the bend witnesses; a
drifted end class found there is a checkpoint ruling, never an
implementer decision.

## §4 Where S1 writes (integration)

**CORRECTION 2026-07-31: `taut_string.py` is an EXISTING committed
module — S1 rightly EXTENDED it rather than duplicating (do not
rebuild what exists); this spec's "new module" was wrong.**  The
constructor code is PURE (no layout mutation), plus one gated hook in
`solve.py` immediately BEFORE the §10 rod-slab mint (locate by the
mint block's comments, never by line number): under the gate, the
hook rewrites `elev[i]` for strung non-hard vertices to the
constructed values, so the rods are MINTED FROM the taut string and
every downstream consumer (sweeps, R1 field layer 4, R) inherits.
Hard/anchor vertices are never rewritten.  Gate OFF ⇒ hook inert
(function-local import; gate-off never imports the module) ⇒
byte-identical.
**Hook contract (measured hazard, found by S1's own replay):** the
hook receives the PRE-FREEZE anchor set (clause-1 anchors only) as
its `hard` — at the hook point `base_hard` has ALREADY absorbed the
phase-A spine freeze, so passing `base_hard` anchors every strung
vertex and makes the hook a silent no-op.  A unit test pins this
(the hook must move at least one vertex on a fixture where the taut
string differs from phase-A).

Frozen public API (REVISED 2026-07-30 by Fable for Stage 0 — a spec
change, made before any implementation exists; implementers still may
not alter it):

```python
@dataclass(frozen=True)
class StringDomain:
    vertices: List[int]               # ordered vertex indices
    stations: List[float]             # arc-length stations
    pieces: List[int]                 # corridor-piece ids consumed
    priority_class: int               # §3 classes 1/2/3

@dataclass(frozen=True)
class TautChainResult:
    values: Dict[int, float]          # vertex idx -> taut z (uncrowned)
    bends: List[BendWitness]          # declared bends, §2.5 fields
    defects: List[StringDefect]       # infeasible stations / slope audit
    fell_back: bool                   # string kept phase-A profile

def assemble_maximal_strings(centerline_runs, pair_author, node_xy, *,
                             continuation_deg) -> List[StringDomain]
    # Stage 0, pure, REVISED for centerline-identity assembly (§2):
    # centerline_runs: {centerline_id: [ordered node idx]} (arc order,
    #   from the _build_global_spine walk); pair_author: {(i, j):
    #   centerline_id}; node_xy for level-2 windowed headings.
    # Level 1 groups by authorship; level 2 merges segments
    # end-to-end at centerline scale under continuation_deg.
    # Deterministic (stable tie-breaks); each segment consumed once.

def taut_chain_profile(stations, lo, hi, caps, *, z_start, z_end,
                       anchors) -> TautChainResult
    # pure per-string solver: §2 steps 2-4 on plain sequences.

def construct_taut_strings(layout, G, *, elev, bucket_to_idx, n,
                           node_band, hard, centerline_runs,
                           pair_author, cap_of_segment)
        -> Dict[int, float]
    # Stage 0 + §3 ordering + per-string calls; mints `string_bends`
    # AND the assembly inventory (`string_domains`) into the
    # node-space store; returns the full rewrite map (empty ⇒ nothing
    # to apply).  NO mutation of elev or layout geometry.
    # `hard` here is the PRE-FREEZE clause-1 anchor set — never
    # `base_hard` (the measured silent-no-op hazard, §4).
```

`BendWitness` / `StringDefect` are small frozen dataclasses in the
same module (fields exactly as §2.5 / §2.2 name them).

## §5 Gate, default, and flip protocol

Gate **`O4_TAUT_STRING_CONSTRUCTION`**, default **"0"** at landing.
Byte-identity at "0" proven by the copied-tree three-way protocol on
SPLP + CYXY (the U1 method; sequential, never suite-context — P0b
rule).  Default flips to "1" only after checkpoint S1-CP2.

## §6 Acceptance (as tests)

Unit (new `tests/test_taut_string.py`, headless, synthetic):
1. wide tube, equal end values ⇒ single chord, zero bends;
2. tube pinch below the chord ⇒ contact run with bend witnesses,
   all slopes ≤ cap, values hug the pinch exactly;
3. anchor-vs-anchor infeasibility after propagation ⇒ `fell_back`
   True, defect carries BOTH authors, no NaN anywhere;
4. slope audit: a hand-built tube violating the §2 invariant trips
   the declared defect (or the test documents why it is unreachable);
5. junction policy: shared vertex valued by the trunk, branch string
   anchors on it (order stability: same input ⇒ identical output);
6. service-corridor and runway exclusion;
7. gate OFF ⇒ `construct_taut_strings` never called (import-neutral);
8. **Stage 0**: (i) two segments of ONE authoring centerline crossing
   a piece boundary group into one string (level 1); (ii) two
   centerline segments meeting end-to-end under the continuation
   threshold merge (level 2), a sharp branch does NOT; (iii)
   **REPLACED 2026-07-31 — the synthetic 62-piece chain PASSED under
   the falsified heading mechanism (a false-confidence fixture);
   assembly acceptance now runs on a REAL-GEOMETRY fixture**
   (landed: `tests/fixtures/heca_chord1_authorship.json`), gated by
   the two-sided §6 assembly gate.  The synthetic chain SURVIVES as
   a unit test of merge/dissolution SEMANTICS only.
   **THE COMPETITION CLAUSE (2026-07-31, from S1's self-catch —
   adopted verbatim): a real-geometry fixture must preserve the
   COMPETITION, not just the geometry.**  S1's first fixture froze
   only the 77 chord-touching fragments — and window 0 reached
   99.9 % on it: subsetting had removed the competing candidates at
   each junction, so real geometry tested INTENT again.  The landed
   fixture freezes all 647 non-service authored fragments and
   reproduces full-graph behaviour.  **A mechanism fixture carries
   its own NEGATIVE CONTROL:** the window-necessity test (window 0
   must FAIL — 59.8 % vs 99.9 %) doubles as the fixture's validity
   proof; a fixture on which a falsified mechanism passes is
   invalid, however real its geometry.
   **DENSITY SIBLING (2026-07-31, arm 1 — taxonomy entry five): the
   phase-1 fixture (22.7k nodes) predicted 99.9 % assembly; the
   131k-node build assembled 2,366 m max — the fixture preserved
   the COMPETITION but not the DENSITY.**  Re-base order (ruled — no
   blind re-freeze): (1) census the assembly shortfall at build
   density OFFLINE (admission failure — bearings at denser
   fragmentation — vs tiling failure — gaps that exist only at
   density); (2) re-base the fixture from build-density data;
   (3) re-establish the negative control at the new density.  A
   re-based fixture without the shortfall attribution is entry five
   committed twice;
   (iv) determinism: same input ⇒ identical assembly;
   (v) unauthored-edge fallback: an unauthored piece stays separate
   and is counted.
9. **Peg-dissolution semantics**: an interior peg's inherited value
   has ZERO influence on the string result (assert by perturbing it).
10. **Hook liveness** (the `base_hard` hazard, §4): on a fixture
   where the taut string differs from phase-A, the gated hook moves
   at least one vertex.

HECA (checkpoint S1-CP2, ≤ 4 builds total):
* **Assembly gate (disambiguated 2026-07-31 — the string is the
  THROUGH-PATH, not the corridor point-cloud)**: chord 1 assembles
  as ONE string whose ordered node path spans the through-path class
  (~3,992 m north→south, every node inside the 25 m corridor;
  measured reference: 360-node path exists in the graph).  Corridor
  spine nodes NOT on that string must belong to OTHER assembled
  strings (the crossers) — none may remain orphaned pieces;
* **W-CHORD1**: worst-bin departure strictly improves from −11.07 m
  (`owner_chord_probe.py` gate line); expected DIRECTION per §1a:
  the peg class closes (A8-class recovery, upper-bound −5.76) and
  every remaining departure is covered by a declared bend witness —
  at HECA specifically, band-ceiling bends over along 1000-2400
  feeding the §6.6 owner ruling;
* **W-CHORD2**: seam pair stays ≤ 1.5 % AND moves toward 103-106;
* building199 weld not worse than 0.49 m;
* law-true HECA counts (`O4_TEST_AIRPORTS=HECA test_pavement_grade`;
  CAUTION plan register 14: the variable does not scope every
  parametrized test — budget this as a FOUR-airport run, ~710 s)
  not worse than the 24F-baseline values;
* suite comparator: zero failures outside the 24F set (spec §5.0).
* NOTE the §1a bounds caveat: replay numbers are upper bounds
  (spine_floor/couple_adj absent there); the build measures truth.

## §7 Checkpoints (Fable resumed; do not proceed past them)

* **S1-CP1 — SATISFIED 2026-07-30 by P3's table + the Fable ruling
  recorded in §1a/§2.**  Rulings made: Stage 0 is in scope (the
  structural fix; pegs dissolve, they are not targeted); the band
  stays in the tube as-is and its bends are DECLARED (the ceiling is
  latent today, binding after Stage 0 — its provenance is P3c's
  offline attribution, and §6.6 is where the owner rules on the
  bends); `_build_spine_corridors` is not modified.  Implementation
  may start once P2 (R1) lands; the remaining pre-build gate is the
  unit-test set incl. the Stage-0 cases.
* **S1-CP2** — after the first gated HECA arm: the §6 gate table +
  the full bend-witness list + the `string_domains` assembly
  inventory (piece counts, follow-through threshold hits) + the §3
  end inventory.  Fable rules on the default flip and reviews the
  threshold value.

## §8 Build-time statement

Propagation + funnel are O(total strung vertices) (~10⁴-10⁵) with
trivial constants — expected well under 0.6 s; the hook is one dict
application.  Measure `check_build_time --run --runs 3 CYXY` after
landing; ≥ 0.6 s ⇒ stop, optimization review (hard law).

## §9 Ladder + budget

(a) P3's dumps/table → (c) unit tests → identity builds (SPLP+CYXY
three-way, ~3 min) → (d) HECA ≤ 4 builds (~25-30 min) at S1-CP2.
No flats beyond the comparator; no battery (R3's).

**Sequencing advice (2026-07-31, Fable — the owner decides):** 1 of
the ≤ 4 HECA builds remains.  Spend it ONCE, on the construction we
intend to ship: land Ruling 3 + the Ruling-4 plumbing, re-run
ARM-ACCEPT-2 and the decoration census OFFLINE (zero builds),
re-state the W-CHORD predictions, THEN build.  An arm-3 build today
measures the processed-tier construction (tops out ~2.0 km where
the substrate carries chord 1 at 3,976.8 m end-to-end) — a GATE C
read on a superseded constructor is a PROXY and cannot ratify the
flip; S1-CP2 judges the ship construction.  If the owner orders the
build first anyway, its results are labelled processed-tier and the
flip still waits for the ship-construction build.  When the build
runs: check the DEM inset-cache and sidecar STALE lines before
quoting any W-CHORD number, and a session's first build is
cold-cache — never a baseline.

## §10 EXPECT DIVERGENCE

(i) **FIRED AND CLOSED 2026-07-31** — the assumption was measured
FALSE three separate ways (no `osm_lines` exists in phase 2; the
hook-time apt tier is post-recognition, not the S2 snapshot; the
substrate is coordinate-space against a node-indexed driver).  S1
STOPPED as designed, and the carry is now LAW: Ruling 4 in the
second rulings block (capture-at-snapshot, write-once +
fingerprint, hook reads only the carried field, registry-identity
decoration).  The original license to rebuild piece geometry from
the spine graph at the hook is RETIRED — that path reconstructs
exactly the processed-tier proxy this ruling exists to escape.
(ii) Per-segment cap source: if a string's route/letter is ambiguous
at some segment (mixed corridors after follow-through), report the
ambiguity class and count — do not guess a cap.
(iii) **REWORKED after P3 (the original clause here licensed an
early stop on the correlational ceiling reading that intervention
falsified — it would have been the tenth falsified mechanism).**
The binding-vs-latent status of ANY tube constraint is decided only
by masking (the §1a attribution rule).  No stop-early on
correlation; a constraint "obviously" authoring a departure is
exactly the claim that needs the mask arm.  If a masking arm cannot
be run offline for a constraint class, report the gap — do not
substitute the correlational reading.
(iv) The hook point: if rod minting has moved or slabs are minted
before any viable hook, report with the actual order.
(v) Off-net (band None) runs: unconstrained stations are expected in
small runs; if > 20 % of a trunk string is off-net, report before
trusting the tube.
(vi) **FIRED AND RESOLVED 2026-07-31** — the original heading
mechanism could not assemble chord 1 at ANY threshold (the §2
falsification record); the STOP worked exactly as designed and the
mechanism was replaced by centerline-identity assembly, ruled by
Fable.  The threshold concern survives at level-2 (centerline-scale
merges): too much (two genuinely distinct taxiways merged through a
shallow kink) vs too little (an authored-in-pieces taxiway left
unchained).  The chord-1 acceptance test catches too-little;
S1-CP2's inventory review catches too-much.  If no value passes
both at HECA, STOP — design question, not a tuning loop.
(ix) Authorship availability: if centerline identity is NOT in
scope at `_build_global_spine`'s pair-emission point (the §2
plumbing assumes it is), STOP before touching grade_graph further.
(x) **ANSWERED 2026-07-31**: the census DID show many short authored
centerlines (75; median fragment 37 m) — and ALSO showed level 2 can
chain them (36 collinear fragments, zero-length gaps, 95.9 % metre
tiling), so the STOP's second conjunct is refuted and the gate is
ruled PASSED with its condition restated in property terms (§2).
S1's stop-at-the-literal-gate was correct; the count proxy was the
defect.  Residual divergence: OTHER airports may show positive-
length gaps or ambiguous admissions — those remain STOPs for Fable.
(vii) Large rewrites (the dip is 11-12 m) will mint big
fabric-vs-string steps for the sweeps to reconcile under R1's
references — transient over-cap counts DURING development are
expected; only the §6 gates judge.
(viii) §1a's open attributions may land during implementation (P2's
snapshots naming the post-phase-A 2.2 m drag; P3c's ceiling
provenance) — fold them in at the next checkpoint, do not redesign
mid-step.

## §11 FROZEN / DISCRETION

**FROZEN:** module path and API (§4, incl. `assemble_maximal_strings`
and `StringDomain`); Stage 0's semantics (centerline-identity level 1
+ centerline-scale windowed continuation level 2 + unauthored
fallback; pegs dissolve; `_build_spine_corridors` untouched; the
authorship export from the SAME graph-build walk); the §1b ordering
ruling (α now, S1b ordained — no implementer reorders phase A); the
§2 step order and defect semantics (fall back + declare, never
tune); the §3 ordering policy and HARDENED end policy (no assembled
end inherits phase-A values); the hook contract (pre-freeze anchors,
never `base_hard`); the gate name/default/flip protocol; §6 gates
(incl. the through-path assembly gate and the real-geometry
fixture); the checkpoints; witness fields; exclusions (service,
runway); the §1a attribution rule; Ruling 3's tenure law
(emission-charged exclusivity; the residual fixpoint; `min_len_m`
never relaxed; AX-style overlap forbidden); Ruling 4's carriage law
(capture-at-snapshot, write-once + fingerprint, ONE projection,
hook reads only the carried field, decorate-never-re-derive,
unmapped = off-net); Ruling 5's exclusion semantics
(pre-composition wall, one role source, uniform across rounds);
Ruling 6's ACTIONABLE-A companion (reported beside GATE A in every
acceptance table; its threshold is the owner's alone); Ruling 7's
no-heal law (no radius inflation, no nearest-node snapping; empty
decoration is a correct answer); Ruling 8's swap sequencing (one
chain source at every point in time; selection flags between paths
forbidden; the processed-tier domain deleted in the swap commit
with the wiring fixtures green on the substrate path); Ruling 9's
`station_m` = 5.0 discipline (required-explicit everywhere, one
named constant at the one production call site, logged in every
denominator, moves only by ruling with a re-baseline); Ruling 10's
identity discipline (registry 0.5 m at decoration only;
construction-side interning at the pinned production hygiene
value, logged; mixed-definition tables forbidden unlabelled);
Ruling 12's liveness rule (a spec-named capture/hook site must sit
on a measured-live path) and ratified OSM capture site; Ruling 14's
accepted baseline (GATE A 86.9 % at production identity on the v3
denominator; the retired 87.1 tripwire; the anti-tuning clause);
Ruling 15's ACTIONABLE-A form (edge-span, constant-free; the ruled
decoration relation; ANCHORED-STRINGS always labelled); Ruling 16
as amended (defect finding, capture-unchanged, membership-not-
restricted); Ruling 17's interim law (§2 minimal fallback; no
improvised arbitration) and arm-3 validity conditions (trunk
invariance confirmed from logged anchor inventories;
counts/comparator provisional-through-§3); Ruling 18's clip law
(emitted-string bind point; the OWNER-RULED shoulder-absorbed
outline, declared-width considered-and-superseded; the owner's
50 m floor verbatim and never recalibrated; the 50-vs-100 scope
resolution; post-clip emitted sets); the per-consumer law
(admission AND filter predicates keyed to the consumer's failure
mode; thresholds are part of a predicate's consumer contract);
THE OWNER'S STRING INVARIANT verbatim (sixth block: strings are a
preference, grade law overrules, a string never causes a
violation) with Ruling 19 (flip gate = the string-attributed
law-true slice at ZERO; aggregate line unchanged), Ruling 20
(§10(vii) is judge-time law, never ship licence), and Ruling 21
(ONLY LAW MAY BIND: `xstring` values are preferences;
law-forced-vs-slack-chosen decided by the slack census; zero
string-authored infeasible stations in whatever arbitration
design lands); Ruling 22's datum-supply frame (free-end taut
solve recommended; the height rule is the OWNER's; "no
post-harmonic inheritance" stands — objective, never authority;
`xstring` end datums excluded per Ruling 21; the flip never reads
W-CHORD1 from an arm where the string did not speak); Ruling 23's
disposition ledger (every emitted string carries a recorded
disposition; the flip blocks on the ledger existing and the gap
attributed); Ruling 24's census scope (lead with the named
chains, keep the full sweep — a census scoped to the guilty
re-imports the labels hazard); Ruling 28's complete-remedy claim
(34/34; a non-stringing span is an implementation finding);
Ruling 29's population law (the 61 shared vertices, never the 7
chains; tube dumps ride replay then build); Ruling 30's closed
manifest (twelve riders after Ruling 34; amendments only before
the spend); Rulings 31-32 (floor-with-flaw recording; VERIFY THE
REFERENCE — a reference population must contain the right
object, not merely a nearby one); Ruling 33's dissolution
(parallel duplicates are harmless source data; no filter
anywhere in this line); Rulings 35-37 explicitly NOT FROZEN
(network solve HELD — twelfth block); Ruling 39's soft-target
mechanics, conditional on the owner's fork answer (no `xstring`
in any tube; plural-claimed vertices unrewritten; reconciliation
belongs to the solve); Ruling 40's branch pricing (out-of-band
TARGETS do not violate the invariant — the SURFACE does;
tube-confinement is an artifact of the overwrite transport);
Ruling 41's P3c promotion (band-ceiling provenance is the
line's critical path on every branch); THE CHORD MODEL
(thirteenth block, Rulings 42-48: retained-vs-retired ledger;
the endpoint law; the W-CHORD1 pair — endpoint identity at
ε ≤ 0.50 plus binding-law-witnessed delivery; the four-step
measured retirement protocol; the reshaped manifest;
mid-span-sag unrepresentability as spec law; RE-READ THE
OWNER'S ORIGINAL SENTENCE); Ruling 49's endpoint read law
(no snap — rejected with grounds; direct / interpolated /
clamped read modes; band interpolation is a READ, not
bridging; beyond-graph tails delivery-moot with the chord
extending by its own linearity; the clamp offset reported as
gate-(A) uncertainty, a first-order quality metric); and the
fourteenth block's step-0 record (the band binds the surface
solve — P3c critical path; the dip-headroom question goes to
the BAND dump).
**DISCRETION:** funnel implementation details; piece-
geometry/adjacency recovery mechanics (within (i), now closed —
historical); the greedy assembly's internal data structures;
dataclass layout beyond the named fields; test parametrisation;
CSV dump formatting; the capture plumbing and the carried field's
exact storage layout (within Ruling 4); decoration data structures
and residual-round bookkeeping (within Rulings 3-4).  The
follow-through threshold VALUE is config-owned and reviewed at
S1-CP2 (not implementer-tuned silently).
