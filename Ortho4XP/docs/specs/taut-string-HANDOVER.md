# Taut-string line — session handover, 2026-08-01

## 0-CAMPAIGN STATE — 2026-08-04, POST KILL-HALF (supersedes everything
## below; RULINGS.md is owner-law canon; memory/campaign-goal.md is the goal)

**THE GOAL** (owner, unchanged): five-airport LAW COMPLIANCE
(SPJC/SPLP/CYXY/HECA/KCLT): zero ADJUDICATED violations (the law includes
its exemptions and floors — instruments report, the law adjudicates),
quarantine machinery GONE, every reg generation-binding with test twins.

**CAMPAIGN ANCHORS as of the 2026-08-04 TIP (commit c48ce36; new
defaults w=0.02 + corridor-ref retired + seat-band ON; minted 2x):**
SPJC `7cc21d87` SPLP `0d967737` CYXY `d89b73a8` HECA `122708ac`
KCLT `4c331a46` HEAZ(fixture) `9679dd1e`. Tip census (law-true,
pre-flip -> new default): SPJC 1698->1366, SPLP 50->27, CYXY 171->155,
HECA 9649->9125, KCLT 2908->2643; BATTERY 14,476->13,316 (-1,160),
seam +15 (ruled accepted). Every prior anchor list below is HISTORY.

**MORNING DECISIONS (owner interview, 2026-08-07 AM; the four
2026-08-07 RULINGS entries are canon): (1) BAR SUPERSEDED — Mac TEST
APP builds NOW from the green tip; RELEASE_NOTES name the four
structures + honest numbers; Mac only, no tag/CI. AMENDED: NO TILES
ON RELEASE (owner: "I'll build tiles myself") — the recipe's tile
step is gone for good. (2) Item-4 = EVIDENCE FIRST —
coupling-classified KML + dossier of the 140 on-DEM vertices, then
the (a)-vs-(d) sentence. (3) Round order RATIFIED: pad-frontage →
relief+drainage → hardening; c9feed cycle-10 probe re-runs on
b6936ed in parallel. (4) Approvals: 529 junk DSF dirs DELETE
(lead-executed, ledgered); O4_SVC_CURVED_JUNCTION RETIRED (lane/
svcret 410735e, byte-identical CYXY, census Δ+0 — closes STATUS
20260731d's open call); baseline re-record stays deferred to the
final profiling round. SHIPPED THIS MORNING: XPTerrainBuilder.app
1.0.221 (engine 1.50.1666 frozen, self-contained) — launch smoke
green; toolchain note: CLT on macOS 27 beta lost the SwiftUIMacros
plugin, build with DEVELOPER_DIR=/Applications/Xcode-beta.app; main
tree's 4 unmounted data dirs now symlink the shared repo; write
guard gained the no-op ensure-dir allowance (twin in
test_harness.py).**

**WALLS RETIRE TO CARVES (owner ruling 08-07 ~12:30, RULINGS entry
"Retaining walls emit ONLY at carve structures"): walls lawful only
at tunnel/bridge carve structures; FEATHER (graded transitions under
caps, no explicit relief feature) replaces them everywhere incl. the
adjacent-ground DEM boundary (step class dies by construction →
wall_foot_ll population → ~0 → machinery retires). Executes IN the
relief-generation round (structure #2) — which this REDEFINES:
generate feathered transitions + fan zones, not walls/terraces.
Pad-frontage (structure #1) simplifies: single relief form per
chord, no per-frontage STEP/WALL decision. Enclave-wall attribution
lane (running) now doubles as the wall-emitter inventory the relief
round consumes.**

**SLIVER ATTRIBUTION (08-07 ~10:30; 46-point vintage series, pinned
cda instrument anchored to the density dossier's A5 row): REAL-frame
divergence flat 08-01→08-05, DOUBLES by 08-07. Four families:
interior-ring emit `8c6e047` 08-05 (+11tv/+14x, HIGH —
layout.py:2570's "already-interned" assertion measured FALSE: 65.9%
of interior-ring vertices belong to no other way; specimen ring
-13507 shares ZERO nids with ways it crosses at 18.5 mm); c5nodeid
merge Fix P coincident mints (+10, HIGH); the 08-05 terrace/wall
block (MED; 28% wall vertices private vs 0 in A5); graded_strip~
graded_strip creep (NOT PINNED, LOW; relief-coupled,
oracle-invisible). All = the shared-boundary-spelled-twice class
cycle5-node-identity-spec FORBIDS — a REGRESSION REPAIR under
existing law, spec sliver-node-identity-repair-spec.md.
be2009f3→HEAD mints ≈nothing (twice-confirmed). The tv/x→mesh-sliver
linkage is STILL correlational — Phase B of the repair spec supplies
the missing interventional arm. NEW HARNESS HOLE (fix lane
dispatched): guard-blocked DEM prep DEGRADES with exit 0
(dem_inset_provenance null, 18.5k vs 34-36k nodes) — provider .lock
write at HEAD, makedirs at old vintages; real-DEM harness
measurement builds impossible until fixed. 2/4 patch-only builds
spent (degraded; kept as matched code-delta control, arms in
tmp/sliver_attrib/arms/).**

**ITEM-4 CLOSED PROVISIONAL (08-07 ~10:00): ruling (d) landed in
lane/item4d (final sha 4fe19e0, READY-TO-MERGE; control item4dctl
standing) — the one-sided wall-foot exemption as a `wall_foot_ll`
out-of-scope stamp (disconnected_ring convention; law-true counts
never move). 48/48 at HECA_lo including the ratified stacked-twin
weld (11-dp spelling + value both exact; the weld acted ONLY on the
measured case). Battery −500: 86 airside rows released (HECA 48 /
KCLT 21 / SPJC 14 / HEAZ 3); 10k world zero everywhere; law-true
identical to control at all 8 patches; +6 twins, FAILED-diff empty.
Spec deviations ratified in-spec (dem threading / weld membership /
battery-wide firing). CHORED: census frame-sidecar auto-read with
--dem contradiction refusal; 5e-3 on-DEM tolerance deduplication
(who_wrote vs check_grade). Retrospective structure #4 of four:
RESOLVED (provisional — revisit at sim pass). MERGES PENDING OWNER:
lane/svcret 410735e, lane/item4d 4fe19e0, lane/demfix 225fad3 (the
guard-degrade hole: two refusal detectors + scoped .lock allowance +
12 twins; full-frame HECA patch-only evidence 36,404 nodes,
provenance non-null, corpus UNCHANGED — unblocks nidrepair's
real-frame check and Phase B on merge).**

**CYCLE-10 EXECUTED (08-07 ~11:30; lane/c9feed tip b3cfa55, STILL
PARKED — merging c9feed remains the road-feed gate decision): fix 1
— the instrument hole was TUPLE TRUNCATION (`run_checks`' axis
conversion kept 4 slots, dropping sidecar `is_service`; the
truck-route rule never fired ONCE) — fixed as the named `_axes_to_m`;
555 removed rows across 4 arms, 100% service-axis-traceable, exactly
one class moved per cell, post-fix own-frame == base-frame airside
(4,474==4,474: the instrument half of the +604 is zero BY
CONSTRUCTION). Fix 2 — three probe gates committed default-OFF with
identity+sentinel inertness twins (NO_SERVICE_EDGES / NO_MOUTHS /
NO_ROAD_PAIR_LAW). M1 knife — PAIR LAW IS A CARRIER, THE LARGEST
SINGLE, NOT THE CARRIER: −262 of the +444 within_shape::apron|apron
at 10k (59%), +22 at −500 (control already 81 BELOW base there);
~182 rows UNATTRIBUTED; world-asymmetric like the edge knife. Lane's
census `--frame own|base` extension RATIFIED (lead:
extend-don't-fork, default byte-verified, twinned). c10ctl+c10knife
worktrees mounted with arms. MERGE QUEUE CLEARED (owner, ~11:00):
svcret, item4d, demfix ALL MERGED — nidrepair's real-frame check +
Phase B unblocked on report. Chip session task_c09c1bdd duplicates
merged demfix — flagged to owner for stop.**

**CYCLE-10 PROBE VERDICT (08-07 ~09:30, clean-tree re-run; c10ctl
left mounted with arm-A artifacts): the c9feed +604 attribution
STANDS — 136 instrument + 468 surface, reproduced exactly (4/4 body
shas, 7/7 census cells; the lane's dirty flag was cosmetic). The
original probe was confounded THREE ways: dirty-tree-only hooks
(O4_PROBE_NO_SERVICE_EDGES/NO_MOUTHS in no commit, no stash),
treatment PRE-APPLIED (probe2's knife ran on the tree already
carrying the cure — inert by construction), three arms on three
trees. Mechanism verdict: NOT airside riding graph edges (the edge
knife reads +137 at 10k / −431 at −500 — same knife, opposite
signs), NOT mouths; the remaining carrier is the roads' PAIR LAW
inside the airside solve. Instrument half = (d) with an exact
address: service axes stamp transverse::apron|apron (69→205 @10k /
54→197 @−500) though _axis_is_svc + _GROUNDSIDE_ROLES forbids it —
those rows should not exist. −500 own-frame: arm B 4,150, base-frame
4,007 = −122 BELOW baseline. Next (spec
cycle10-roadfeed-verdict-spec.md): (1) instrument fix, zero builds;
(2) probe hooks land as committed default-OFF gates; (3)
pre-registered pair-law knife (edges stay, pair law withheld from
the airside partitioned projection) — surface fix remains a design
decision, not auto-landed. NOTE: two arm builds flagged CONTAMINATED
by concurrent shared-repo writes (OTHH +25+051; Masks/+30+031 = the
owner's own in-app tile build writing masks) — snapshot-level only,
identity proven by reproduced shas.**

**TRAIN STOPPED PER OWNER GATE (00:30 08-07): HECA airside <100
proven unreachable (3,734 after the one safe fix, −395; ladder:
convergence 2%, the remainder = FOUR structures — pad-frontage
chords ~1,870 / relief generation (b) 1,368-at-blanket-5% /
feature-weld hardening 2,045 both-hard / on-DEM stranding (a)-vs-(d)
OWNER ADJUDICATION PENDING). NO APP BUILT. Retrospective:
docs/retrospective-2026-08-07.md (delivered). c9air MERGED. **c9feed PARKED**
(works-but-gate-failed, the fix3b playbook): D′ 3,898→2,714 with the
lane's law addition (ONE AIRSIDE VIEW of the one graph — airside
never rides service edges; roads/mouths live everywhere, HEAZ's
first 36 mouths) but HECA 10k +604 airside (136 instrument + 468
surface; mouths excluded interventionally; the decisive graph-edge
probe was CONFOUNDED — cycle 10's FIRST measurement re-runs it on
b6936ed). census_matrix.py cherry-picked to main. NEW NAMED CLASSES:
cross-shape welded neighbours carry NO LAW PAIR (the D′ tear
specimen, 46.05 m over 3.58 m at a mouth); airside VALUES move
(8-18 cm median, worst 3.7 m) where counts are flat — receiver-only
residual coupling. 3 re-minted DSF leak dirs cleaned under the
owner's class approval (ledgered). Next rounds ranked in
the retrospective: owner item-4 sentence → pad-frontage round →
relief generation (scope WITH deferred drainage) → hardening round.**

**RELEASE TRAIN (owner 2026-08-06 22:48 PDT, superseded above): fresh Mac app for
testing by 06:00 PDT 08-07. HARD FREEZE 03:30** (a lane not
merge-ready PARKS) → serial merge + flat tip battery 03:45 → release
build 04:30 (make_engine freeze-freshness check; make_app TCC/
LaunchServices traps, direct-exec smoke; tiles +30+031 then +35-081,
.hgt check; RELEASE_NOTES honest known-remaining) → deliver 06:00.
**RELEASE GATE (owner 2026-08-06 ~23:00): HECA adjudicated AIRSIDE
< 100 at 04:00 PDT ⇒ proceed with the app build; ≥ 100 ⇒ STOP, no
app — conduct a retrospective and deliver an owner report on what
the remaining defects are and why they resist elimination. Current:
4,129 (−500) / 4,006 (canyon) — lead applies the gate to BOTH worlds
(conservative reading, flagged to owner). Groundside ships named
either way.** IN FLIGHT: c9feed (road feed joins the graph,
cycle9-road-feed-spec) + c9air (airside-residual attribution+bounded
fixes). Owner decisions landed: DSF cleanup DONE+ledgered (535 dirs);
point-4 scoped; partition RATIFIED (in RULINGS); NO joints across
any road (terrace-r2 Q closed).

**SESSION CHECKPOINT — 2026-08-06, HEAD 34088fe (+ the fix3b merge in
flight). FRESH SESSION BOOTS HERE; the ~17:30 block below is HISTORY.**
Read: RULINGS.md end-to-end, tools/INDEX.md, BASELINES.md (scratchpad
rebaseline/), memory/.

CYCLE-4 VERDICTS (all three targets closed this session):
- Targets 2+3 LANDED (merge `7786ff0`, lane/c4law): flex budget DELETED
  per owner ruling (clamp = min(pull, slack)); ride never enters an
  anchor via ZERO-BAND-BUT-FREE join stations (anchored-set mechanism
  measured re-minting the self-anchor lock — deviation ratified,
  spec cycle4-anchor-law). Law/ride instrument's law line = anchored ∪
  flex-applied (`033c3d5`). HECA canyon: 3,169 nodes @ constant
  12.8394 m → **382 nodes worst 1.6421 m, ALL LAW-half** (ride ≤0.019 m);
  three anchor pairs (6995/7326/3666/7595), law spreads 26.29/26.30/
  27.56 m over budgets 24.658/25.793/27.084 m ⇒ +1.6358/+0.5083/
  +0.4729 m. HECA plateau −771 law-true vs matched control.
- Target 1 LANDED IN MODIFIED FORM, **PREMISE FALSIFIED** (merge
  `389af44`, lane/c4proj): final_grade_projection ABSORBS the plateau
  row mass (hold arms 48,432/38,681 vs 24,258 control) — THE ONE SOLVE
  ITSELF EXITS UNCERTIFIED on HECA plateau (63,898 active violating
  edges, worst residual 96.79 m, "the polytope is EMPTY"). Landed and
  standing: carried law context (solved_values/building_seats/
  gs_witness by canonical identity), near-miss frontage law (exposed a
  LOCKSTEP GAP — generation-binding, NO census family, reads as HECA
  +498), counted terrace/fan appliers (fan rail verified: handed 5%
  cap reaches both edge sets), who_wrote --author, ENTRY/EXIT law
  certificate. Idempotence hold is REPORT-ONLY.

CYCLE-5 STATE: attribution DONE (dossier c4tip tmp/c5attr_dossier.md):
ALL SEVEN battery builds exit UNCERTIFIED; every dominant family is
**(a) BUG** — stale foot boxes (solve.py:1384 vs the one authority
solver_primitives.py:2416; 65.6% stale-box rows, datum p90 24.9 m),
one-shot band floor clamp (one_solve.py:2566; 11,144 below-floor vs
112 above, 99.5:1), gs_pin hard raw-DEM anchors (70/70 out-of-band
hard nodes, worst 85.7 m below own floor); certificate (d) on family
axis only (arithmetic verified). Honest post-fix residual: 3.9% of
edges, worst 5.620 m. Adjacent-ground "binds→0" claim FALSIFIED (boxes
bound; stale datum mints it; plateau worse than canyon — KCLT dem1
225.34 m). **c5solve LANDED AND MERGED** (all four fixes first-attempt;
spec cycle5-solve-certification carries the full outcome table): HECA
plateau adjudicated 21,404 → **6,442 (−69.9%, airside −72.1%)**; KCLT
7,477 → 3,404, its raw-law envelope INFEASIBLE **0 of 22,298**; the
below-band and HARD:gs_pin classes are EMPTY; dominant class is now
in-band↔in-band (82.66%, worst 15.950 m). NOT met (quantified, tasked):
no CERTIFIED exit yet — HECA worst residual STUCK at 89.431 m across
all three fixes (carrier (1013,7022) now free/free) and who_wrote
--author still shows 1,634 untouched-node moves worst 87.930 m (likely
ONE mechanism, 89.4≈87.9); HECA envelope 13,259/17,955 @ 16.856 m;
canyon unchanged (flex territory). NOTE: c5solve censuses are in the
PRE-c5inst frame — the merged tip unifies both; the reconciliation
battery re-reads the matrix there.

**RECONCILED TIP MATRIX (frame of record, tip d6fa96a, c5tip
tmp/c5tip_report.md):** ADJUDICATED/airside — HEAZ 1,100/423 ·
212/203 · SPJC 2,127/2,051 · 3,801/3,701 · KCLT 3,421/2,249 ·
3,638/2,049 · HECA 6,517/5,811 · canyon FAILS (see below). c5inst
PROVEN surface-neutral (five cells, five exact fnm-only deltas).
SPJC SPLITS: plateau −30.9% (gentle prior holds), canyon +1.9% and
band excess flips CEILING-side worst 1.5007 m (named, not chased).
SOLVE EXIT still UNCERTIFIED all 8; who_wrote untouched class
UNCHANGED (HECA 1,634 @ 87.930 m — target #14).

**CANYON VERDICT REVERSED (c5tip Job 2): (a)+(d), NOT law.** Budgets
are exactly cap×length (1.5000% — not under-priced; no unpriced
relief on a spine); PLATEAU achieves pair 2's spread at 22.66 m with
3.13 m slack on IDENTICAL CIFP pins; canyon anchor values are
DEM-driven (+5.31/+6.24 m vs plateau); the flex retired 8 bins
carrying 168.62 m after 'apply refused 1.898 m 2x' and hit round cap
12 (same runway demands 0.05 m in plateau); `_anchor_law_values`'
"CIFP cannot reach" sentence is FALSE all three pairs (reports ride
0.04 m for a 5.31 m DEM-driven value). **c5flex LANDED AND MERGED — HECA
CANYON BUILDS** (the last flat-world hard-fail is gone; ALL EIGHT flat
builds now succeed). Mechanism: the self-anchor lock class a THIRD
time, on the APPLY side — apply_runway_flex re-anchored flex-minted
stations that flex_slack_at lawfully withdraws; 178/178 main-cap
refusals bound by self-minted anchors (asked 1.789 m, relax 0.000,
unminted 18.406); FALSE refusals minted retirement. Fixed instrument:
CIFP-forced spreads 4.81/4.82/3.02 m vs budgets 24.7-27.1 — all three
verdicts reverse to (a); world-invariance twinned byte-identical.
Canyon adjudicated 10,463 (first-ever number; band residual 110 @
2.76 m). Spec deviation RATIFIED: plateau moves BY CONSTRUCTION
(604+661 m suppressed demand on the other runways) — 6,517 → 6,597;
runway families improve, within_shape +110 (network-absorption
question, tasked); HEAZ plateau +90 (groundside +88). Named, open:
both worlds stop on the 12-round flex cap, not convergence. My
earlier "metric/cap/topology" framing above is SUPERSEDED.

**NEAR-ZERO CANYON NODES (c5tip Job 3): (a).** SPJC 55 / KCLT 186
(+259 partial lerps) / HEAZ 7 vertices stranded AT raw DEM by FIVE
geometry-time ring writers seeding new vertices from DEM —
groundside separate/merge, bridges portals, adjacent-ground walls
(all already scheduled for ingestion, RULINGS 2026-08-03) + solve
seats landing on constant DEM. Folds into the single-solve ingestion
program (with target #14's second-author class).

**NODE-IDENTITY ROUND (from the §12 STOP): premise falsified**
(0.0012 m² overlap) — the 193 CYXY budget mismatches are ONE-NODE-
TWO-COORDINATES defects (pre-solve fan cut mints near-twins after the
settle, 99; planarize inserts within the 0.5 m weld tol vs 0.05 m
dedup, 94). RULED: cycle5-node-identity-spec (cut on the settled
lattice; planarize snaps, never twins; weld-after-cut FORBIDDEN —
tears 0.1384 m²). **c5nodeid LANDED AND MERGED** (superset-cover
ruling): budget mismatches 193 → 2 (residual = a different inter-shape
class, node 830, 0.438 m apart, ratio ~1.04 — named); divergence
instrument reads 0 on minted pieces and final rings; keep-out
zero-tolerance with runtime-verified superset; SPJC's fan-signature
self-overlap pair GONE (1.5289 → 0.5812 m², survivor is a junction
mechanism); zone area −1.5% (ruled accepted).
INSTRUMENT ROUND MERGED (lane/c5inst): radius law-derived (F2 exempt),
grid-residual excuse deleted (SPJC honest 48 — population now FLOOR
side at this tree, the ceil quartet was be2009f-era), CYXY fixture red
gone, trace_reach_route REVIVED on the live band (canyon attribution
unblocked), deferred adjudication mechanical (d48bc0a cited),
frontage_near_miss family registered (HECA 85/KCLT 17-29/SPJC 3-7/
HEAZ 0), sub-inversion band excess reported+sidecar'd.

**CYCLE-6 STATE (c5auth dossier; targets #14+#15 = ONE picture):**
The stuck 89 m residual + ALL >10 m second-author moves = a fix-2/
fix-3 interaction — at a disjoint gs-pin-box/band conflict the merge
KEEPS THE PIN BOX AND DISCARDS THE BAND (one_solve.py:2616-2629;
14 declared conflicts ≡ the 14 below-floor nodes; groundside pulls
airside down 87 m; fgp's lifts back are the "second author").
Hypothesis C falsified for the extremes (6.9% overlap, max 2.63 m)
but the DEM ring writers own the census mass: SEVENTEEN sites (top:
pavement_scoring._enact_verdict 7,653 — absent from the earlier five;
emit_terrain_transition_features is ALSO a live second author 89/
94.52 m), cluster D = 2,166 adjudicated rows ≥10 m (17.2%; HEAZ
57.1%/KCLT 41.4% of own totals). Ownership: 47.2% in-band 0.1-1 m ·
32.2% 1-10 m · 17.2% D · P <0.1% of rows but the architecture
violation. FRAME NOTE: the dossier tree lacked c5flex; its baselines
(HECA 7,036 etc.) supersede c5tip's but the tip has BOTH — lanes
establish their own baselines. SPEC cycle6-band-wins-and-ingestion:
Part P **LANDED AND MERGED** (lane/c6band):
14/14 conflicts BAND WINS, 0 below floor; fp#8 worst 91.15 → 60.77 m
(next class: apron carrier (962,5037), different population); HECA
adjudicated 7,165 → 6,481 (airside −691, gs +8 — the lot conforms);
who_wrote untouched worst 89.65 → 14.73 m (>10 m: 14 → 2, survivors
pre-existing); frontage_near_miss worst 90.89 → 2.95; HEAZ
byte-identical (inert without conflicts); non-pin conflicts stay
UNRESOLVED-and-loud. Part D **LANDED AND MERGED**
(lane/c6ingest): the groundside half was ONE mechanism — millimetre-key
weld identity vs the emitter's 0.5 m rule — fixed as one value ladder
(weld anchor → prior field → law interp → counted LAW ISLAND) with
provenance; canyon stranded SPJC 55→8 / KCLT 186→134 / HEAZ 7→7;
exemptions cited (wall feet + bands under zone law; solve seats under
the constant-DEM invariant); dossier misattributions corrected (walls
NOT DEM writers; finalize:294 not a defect). Cluster D 2,252→2,066
only (−8.3%) — residual RE-ATTRIBUTED: service-junction flat-world
seating spread (HEAZ 630 rows, 12 svc ways flat at 1.00 m, two
disagreeing LAW values left standing — solve/band floor-seating,
tasked #18 with the KCLT canyon +180 trade, ~281 non-exempt HECA
attributions, and the pipeline:5721 chord limiter). Battery
adjudicated 12,753→12,265; matched controls: zero introduced reds.
who_wrote --author-dump landed on the tip (c5auth instrument work).

**FRAME OF RECORD — POST-CYCLE-6 (c6tip tmp/c6tip_record.md; a fresh
session boots on THIS matrix).** ALL EIGHT flat builds succeed.
ADJUDICATED/airside: HEAZ 1,103/460 · 202/199 · SPJC 2,289/2,268 ·
3,814/3,780 · KCLT 1,818/878 · 3,384/1,824 · HECA 6,700/6,093 ·
11,092/8,026. BATTERY 30,402 (plateau 11,910 · canyon 18,492) +
12,250 deferred (all drainage_minimum). Solve UNCERTIFIED all eight.
TRUE cycle-6 delta (matched control 4e9008c — both lane dossiers were
cross-tree; the control reproduces HECA 7,165 / fp#8 91.150942
exactly): battery −653; KCLT canyon +180; P∘D interaction +219 (not
additive). Suite FAILED-diff EMPTY (+18 passing twins; 11 standing
reds). RANKED OWNERSHIP: **82% is in-band airside solver residual** —
C-BAND 0.1-1 m 13,711 (45.1%) + C-DECAMETRE 1-10 m 11,143 (36.7%),
one authority (POCS settles apron/junction interiors just over cap);
D′ DEM-stranded groundside rings 4,276 (14.1% — the ladder's LAW
ISLAND branch keeps the DEM seed; fix = lot law enters the solve);
X-STEP 474; C-EPS 792; P′ 21 rows. NEW second author:
_post_projection_conformance_passes moves untouched building seats up
to 9,902 m (HECA canyon). CORRECTIONS: task-18 premise was an
instrument mislabel (flat_ways counts way-level tags) — HEAZ 630 rows
are D′; the real svc-junction spread is KCLT canyon 131 rows (two
disagreeing LAW values, no vertex on DEM). Debts: census
--magnitude-bands promotion owed; who-json by-writer silently empty;
tools/INDEX.md UNREACHABLE from lane worktrees (lane_worktree.sh
doesn't mount repo-root tools/).

**CYCLE-7 IN FLIGHT (lane c7cert; spec cycle7-certified-exit).** The
82% attributed (c6attr dossier, c6tip tmp/): CONVERGENCE ~33-57% —
derive_sweep_budget prices a diffusive process with a linear bound,
~100x short; pure symmetric law CERTIFIES when allowed to converge
(HEAZ x100 = 0; HECA x400 = 0 rows >=0.01); the "NOT budget
exhaustion" exit line is FALSIFIED — verdict (a). STRUCTURE: boxes+
pins own 25.5% and 100% of the 60.77 m headline — a 2-CYCLE between a
zero-width seat box (detached pad building172 at its groundside datum
1.66, band WITHHELD, 343-pad class) and an apron at band floor 62.50
— verdict (c); seed_rwy_seam depth 610 pins, 51.19 m |dz| vs 33.38 m
budget — (b) attribute-first; the INTERVAL/SLAB layer is the largest
structural owner, UNATTRIBUTED — the lane's first measurement;
certificate blind to flat-group edges (1,184 UNATTRIBUTED) — (d);
conformance-pass suspect FALSIFIED (corrective); fgp raises its own
certificate +8,234 — same underpricing suspected. Q4 (P∘D +219)
unresolved, chored. Tool debt: interval_reach_replay unfaithful to
fp#8 (missing dump keys) — extension chored.

**THE PLAN (owner-reviewed 2026-08-06; rulings of the day: instrument
truth · low world −500 m · frontage ⇒ band seating · ONE graph):**
(1) land+merge c7cert (in flight: convergence exit, band seating,
honest certificate, slab attribution); (2) OWNER KML review of the
seam-pin route (phantom coupling vs real — his verdict); (3) cycle
7.5 consolidation: synthetic −500 path (+0.66 m provenance),
standing-instrument sweep (#21), harness hygiene (#20/#23), ONE
battery re-minting the frame of record at −500 (dual purpose);
(4) CYCLE 8 = the one-graph round (spec lead-owed): groundside joins
the route graph, D′ + KCLT svc dissolve by construction — the last
architecture item; (5) endgame: per-row (a)-(d) on the −500/10,000
pair to zero-plus-declared; (6) flat-green ⇒ the real-DEM
reintroduction event (deliberate, harness); (7) sim pass →
compare-target re-cut → final-design profiling round. RISK REGISTER:
fix-4 slab attribution (last unnamed mass), below-sea-level handling
at −500 (never exercised). SEAM-PIN VERDICT RULED (owner, from the
KML): the route was INVALID — certificate routes follow the reach law
(no pad-interior traversal, no zero-budget hops); class = (d), pins
are law, the 610-pin population re-adjudicates after the certificate
reprices (ruling relayed to c7cert for fix 3). Sweep riders: the
seed_rwy_seam label is a misnomer 607/610; 444/1,077 hardened with no
seeder record (unattributed channel).

**CYCLE 7 LANDED AND MERGED (lane/c7cert).** Fix 1 evidence-based
exit (95.8% of the 100x gain at 12% of sweeps; wall +19.2% HECA /
+52.6% HEAZ — under tripwire, flagged for the final profiling round);
fix 2 in the ruled frontage⇒band form (worst 60.77 → 53.71, 4
underivable pads LOUD); fix 3 per the certificate-route ruling
(witnesses 13,370 → 1,226, max gap 19.20 → 1.11 m; carrier feasible);
fix 5 family axis complete. HECA dem1 6,700 → **5,969** (airside
5,376); HEAZ 1,064 / canyon 185. Suite: FAILED lists identical to
control. **FIX-4 STOP → proposed ruling pending owner:** rod slabs
tighter than law on 91.1% of pairs (max 2,305×) = smoothing as
surface authority; proposed: slab budgets FLOOR at the pair's
grade-law budget (soft beyond law, never hard) — repriced with the
seam-continuity design, seam families as the counter-read (6,300
edges, 31.5% of converged residual). **Q4 DEBT → cycle-8 acceptance:**
Part D's ladder trades +301 airside for −62 groundside
(airside-negative, forbidden trade) — the one-graph round must clear
it (acceptance: airside ≤ the P-only 5,792 frame). Worktrees c7q4 +
c7ctl left mounted for teardown.

**CYCLE 7.5 (three of four lanes MERGED):** hygiene (index
ref-dependence fixed — 30/58 worktrees predated it; census
--magnitude-bands promoted; the shared-repo leak was
test_dsf_texture_modes path-keyed caching, 529/530 dirs — redirected
+ session guard twin; down-teardown restores tracked paths; HEAZ
anchor 9679dd1e noted STALE). The ruled −500 world LANDED (first
new-frame censuses HEAZ 1,062 / HECA 6,097 adjudicated; worst |de|
560-603 m = D′ amplified as intended; envelope now DERIVED — 161
HEAZ nodes lawfully at full 10,500 m span; nodata sentinel guarded;
0.66 m writer = seat_detached_pads_by_law zero-width box, march
horizon 2.5 m < the 6.46 m law edge; building172 now floor-seats
62.43 under cycle-7 fix 2 — live confirmation; building173 at
−500.00 = the unhosted D′ variant). SLAB FLOOR LANDED as CONTAINMENT
at ONE pricing site (certificate −6,233 = the pre-registered class;
HECA dem1 adjudicated 5,969 → **5,033**, dem10k 9,629 → **7,388**;
HEAZ 1,033/165; seam counter-read FLAT-OR-BETTER all four worlds).
SWEEP MERGED (6f59c5e; two-implementation
−500 conflicts resolved as unions, c75dem library authoritative;
285 twins green + one fix-forward). **CYCLE 7.5 COMPLETE.** Sweep
highlights: reach-band zero-of-zero → NOT MEASURED with discriminated
cause (HEAZ real cause: G.runway_anchor EMPTY); flex honest line was
arithmetically FALSE → true 4-term partition; certificates stamp
node+crown space, CERTIFIED word removed (world-dependent) →
over_cap=N; 15 FIXED / 1 RETIRED. Follow-ups tasked (#25): _hard_cat
decouple (instrument AND law input — 092af7f flipped crown at 22
nodes), phase-A freeze classless hardening (solve.py:2816 — the real
remaining unattributed channel; the blanket's own residual is
structurally 0), gs_pin no-op in the crown-freeze tuple, tree-sha
stamp wiring, band_excess dual-instrument owner Q. OPEN OWNER AUTH:
delete the 529 junk DSF-cache dirs. **FRAME OF RECORD MINTED
(c8base tmp/c8base_record.md, tip 6f59c5e, worlds −500/10,000):**
BATTERY both worlds **18,933 adjudicated** (−500: 8,193 / 10k:
10,740) + 12,320 deferred. Per −500/10k ADJ (airside): HEAZ
1,032/165 (390/162) · SPJC 442/746 (428/706) · KCLT 1,426/2,441
(502/886) · HECA 5,293/7,388 (4,707/4,228). **AIRSIDE IS
WORLD-INVARIANT to 0.8%** (6,027 vs 5,982) — the whole world swing
is groundside D′. Ranked: 74.5% = converged-but-uncertified solve
residual (93.7% of airside rows in 0.1–10 m); **D′ 4,607 rows
(24.3%) = the ENTIRE groundside mass**, mechanism in one line
([groundside-law-seat]: HECA 2,646/2,725 rings reach the ladder with
no law source, keep the seed); ≥10 m band 96% groundside, worst
KCLT 719.91 / canyon 9,935. 100% of on-DEM emitted nodes STRANDED.
Suite: 11 standing + 1 NEW = cycle 7.5's OWN DSF guard firing on its
unfinished redirect (chored into cycle 8). TWO cycle-8 pre-findings:
the analytic band is NOT world-invariant (HECA 12,657 width
disagreements, max 71 m, zero coverage mismatch — attribute BEFORE
extending it groundside; spec pre-requirement) and env_band carry
30–38% short everywhere (world-invariant, named). **CYCLE 8 MERGED (partial;
lane/c8graph):** both worlds 18,933 → **16,567** (HECA 10k −1,595;
HEAZ −500 D′ 633→3). Band-invariance verdict (d): THE LAYOUT is a
different object per world (cut vs fill; canyon +33.6% nodes) —
instrument corrected. Mouths + groundside band landed+twinned but
FIRE 0x — service stringing is the limiter (SPJC 4/389 segments;
sliced-road nodes at edges vs the 1.0 m perp tol). Real D′ carrier:
unreached service junctions at seed → seat_service_pavement_on_law.
Disconnected rings: ONE predicate solve+census (HECA 968; out-of-
scope 2,892 reported). Suite 12th red CLOSED ((a) test_data_root
reload). Q4 GATE 6/8, 2 FAIL +11 airside total — carrier:
final_grade_projection CO-PROJECTS groundside with airside; cure
RULED in the spec ADDENDUM (lead, from receiver-only — owner
ratification flagged): THE PROJECTION PARTITIONS (airside first,
groundside pairs excluded; groundside after vs frozen airside).
**c8fin MERGED:** the partition landed
at EVERY projection — Q4 7/8, BOTH original debts cured (SPJC −77 /
HECA −802 airside), battery airside 12,005 → **10,718 (−1,287)**,
ADJ → **15,530**; residual FAIL = KCLT 10k +1 strip_seam_tear on a
terrain strip (capped, named) — gate adjudicated SUBSTANTIVELY MET.
Mouths FIRE first time (SPJC 23 / KCLT 50). **STOP → CYCLE 9 (spec
lead-owed, task #26): the graph carries only apt.dat row-1206 routes
(HECA 5) while the ROAD FEED (705 lines / 97.9 km) carves the slice
and never enters** — mechanism: _slice_service_subsegments into
build_context + sidecar + census reader in ONE lockstep landing;
seats the honest +244 groundside. Groundside +244 = roads/lots
showing their OWN shortfall instead of dragging aprons (correct
direction). Named: HEAZ canyon gs 3→131 @ 1-10 m =
the class-universal lateral-contiguity absorption item (standing);
anchor seeds world-dependent ≤0.17 m (rider); KCLT slab carrier
re-read owed.

NEXT TARGETS (ranked):
1. **The solve's UNCERTIFIED exit is the real plateau author** —
   attribute the empty polytope per family (ENTRY/EXIT certificate +
   hold ledger + who_wrote --author are the instruments), then spec
   the fix. Feasibility-is-guaranteed: empty polytope = (a)-(d) defect.
2. HECA canyon 382-node LAW-half residual (the three pairs above) —
   metric/cap/topology attribution.
3. Instrument-fix round (post-battery, spec owed): _RWD_RADIUS_M=15
   misses lawful 1.24% at 19.45 m; RASTER_REACH_BAND_GRID_RESIDUAL_M
   =0.25 calibration stale (~50-row continuum excused); CYXY
   anti-gaming fixture asserts a gone defect; trace_reach_route.py
   replays the RETIRED reach engine (INDEX row false); harness oracle
   counts version-deferred drainage_minimum rows (no deferred
   adjudication instrument); near-miss frontage census family (the
   lockstep gap); production band law is inversion-only — sub-inversion
   band excess ships silent.
4. env_band carry: a new ring node inherits no band (13,937/17,862
   keys resolve; shortfall = decimated vertices, not disagreement).

DEBTS CLEARED THIS SESSION: apron-terrace-law-spec r2 (`d7c3072`,
landed-vs-pending table; owner Q carried: may service-road routes relax
out of the joint no-cross set?); SPJC-verdicts-at-pristine-HEAD
attributed (the checkpoint's "all three" = the ORACLE's three verdicts
— standing flat targets, byte-identical to fix-3A control, e5c8443
value-neutral; pytest reds: F1 = fgp tail of target 1 (a); F2/F3 =
(d) instrument/fixture). **CORRECTION: the backlog line
"route_band_zero pinned-dominated (SPJC 1,227/CYXY 501/SPLP 289)" DOES
NOT REPRODUCE at HEAD** (SPJC 55 raw/0 filtered, CYXY 2) — same
instrument name, different population; re-derive before acting.

TIP RECORD — fix3b MERGED at `97838ce`, battery run (worktree c4tip,
artifacts tmp/battery/). Zero textual conflicts; composition verified
semantically (ramp priced 5% in solve AND projection via the shape path
— the median-10.24% recurrence is structurally closed). Suite vs
matched control (FAILED-list diff): fixed none, NEW exactly one —
`test_solver_validator_same_edge_budgets@CYXY`, 193/12,706 edges at
ratio exactly 5.0 = the PARKED §12 split-overlap defect now visible;
validator is the PERMISSIVE side (census under-reports there). FLAT
MATRIX (adjudicated excl. deferred / airside): HEAZ 1160/486 ·
268-52=216/211 · SPJC 3075/3004 · 3723/3640 · KCLT 7477/6236 ·
3807/2230 · HECA plateau 21404/20629 · canyon FAIL (384/7618, three
pairs ALL LAW-half, +1.9921/+0.8521/+0.3564 m, budgets byte-identical
to pre-merge, ride ≤0.045). Counts ROSE vs frames on SPJC/KCLT/HECA:
attributed to DENOMINATOR GROWTH (fan cut mints ring vertices = new
censusable pairs; HECA 26 aprons → 39 ramp pieces, 10,064 pairs bound
at 5%; SPJC 7,301; KCLT 6,828) — "more law bound" and "fewer rows" are
different quantities; only the first moved. HEAZ fell on both frames.
Near-miss frontage lockstep gap CONFIRMED structurally (cross_shape=0
everywhere while frontage_near_miss binds 4/12-38/78-86/118-138
edges). Adjacent-ground ingestion residual at HECA canyon: 54,063
band vertices outside their law box, worst 20.77 m (self-declared
"goes to 0 when the solve binds the supplied boxes" — folds into the
solve-uncertified attribution). SPJC/KCLT canyon worst rows ≈9,970 m
in a 10,000 m world = nodes the constant DEM never reached
(instrument/seed question, tasked). Owner-started side sessions:
apron_terrace docstring fix, lane_worktree.sh down fix.

**SESSION CHECKPOINT — 2026-08-05 ~17:30, HEAD 7ea3e6e (+ docs
6e7e0ea). HISTORY — superseded above.** Read: RULINGS.md end-to-end
(the law, incl. flat-first e56d40c, real-DEM gated, drainage scope
d48bc0a, fan-ramp 21f0980, no-lawful-infeasible 5578b6a, closed
verdicts), tools/INDEX.md (the harness is THE way), BASELINES.md
(scratchpad rebaseline/), memory/.

CYCLE-4 TARGETS, converged from both fix-3 lanes:
1. **final_grade_projection is THE author** — overwrites the route
   solve ±22 m (fix-3A who_wrote evidence, 12 vertices) and overrides
   handed 5% fan budgets into median-10.24% surfaces (fix-3B's clean
   flat-world specimen). Owns HECA plateau's ~10k rows AND the fan
   acceptance failure. Fix its constraint set to BE the solve's law
   (the ingestion pattern).
2. **DEM-follow ride enters anchors** — runway profile stations ride
   the world (+20 m canyon) and are republished as hard band anchors
   at taxi joins (fix-3A, interventionally proven; flex EXONERATED).
   Fix: ride never enters an anchor; the law/ride split instrument
   (landed, 7ea3e6e) is the acceptance reader.
3. **+7.011 m law shortfall — RULED**: the flex displacement budget
   is ELIMINATED (owner: the law is the only bound; minimize via
   minimum-move design, never an arbitrary cap — RULINGS tail).
   Implement in cycle 4: delete RUNWAY_FLEX_MAX_DISPLACEMENT_M +
   budget_left from the clamp chain; flat oracle is acceptance;
   expected to close the +7.011 within lawful profile room.
4. **lane/fix3b PARKED UNMERGED** (fan activation, works but
   acceptance-failed on #1; + its own split-overlap downstream defect
   at attempt-cap; control worktree fix3bctl is the matched baseline
   — do not tear down). Merge after #1 lands.
5. Debts: Fable spec revision (terrace: 4cbed92 + 21f0980 +
   pre-solve fan panelization); SPJC verdicts fail at pristine HEAD
   (all three, fix-3A control); suite deadlock under xdist observed
   once (control, 35 min) — watch.
FLAT TARGETS stand (HEAZ 1250/892 · HECA 17,557/FAIL · SPJC
2762/6722); real DEM stays gated on flat-green.

**FRAME OF RECORD (2026-08-05 ~14:30, HISTORY, re-baseline @ be84766, one
harness + one corpus; BASELINES.md in scratchpad rebaseline/).**
FLAT-WORLD TARGETS (drive to zero, version-deferred excluded): HEAZ
1,258/894 · SPJC 2,644/6,719 · KCLT 5,362/3,109 · HECA 17,806 /
CANYON HARD-FAILS (BandInversionError, 3,169 nodes @ constant
12.8394 m — the anchor-relief class, terraces dead by DEM-keyed
trigger). REAL-DEM REFERENCE (recorded, not ranked): SPJC 783 · SPLP
59 · CYXY 127 · HECA 6,544 · KCLT 2,487(faa, +1,042 deferred) · HEAZ
260. Flex nondeterminism NOT manifest (byte-identical builds). Fix
cycle 2 (ranked): fast-path deletion; trigger re-keying to
anchor-envelope (owns HECA canyon + the 16k plateau within_shape);
groundside raw-DEM authority completion; assertion-2 saturation
reader; inset frame keys + harness side-effect BLOCKING; drainage_min
role literals; crown-minimum BINDING (the scoped work — generation
exists); compare-target matched control. Owner Q pending: the CIFP
threshold datum-lift (keep as alignment vs delete).

**THE COMPLETE SYSTEM (2026-08-05 ~08:00, HISTORY; MODE: build-complete-then-
debug, RULINGS 12320bd — gates dead, testing = composed builds).**
Landed: KILL 954d6e8, SEATS b0c7df5, INGEST 01006a6, LAW 894aebf,
sweep 0c2c768, test fixes 5743885. First composed build SUCCEEDED all
three: HEAZ 177 (airside 89), HECA 7,129 (airside 4,975 — was 8,268),
KCLT 2,670 (airside 425 — was 2,297; strip_arc 985 + strip_abeam 847
are NEW laws binding for the first time). Hard zeros hold. DEBUG
BACKLOG (ranked): KCLT tunnel_ramp 12.02 m/80.5% single row;
route_band_zero pinned-dominated (SPJC 1,227/CYXY 501/SPLP 289); SPJC
runway 1.50% vs ICAO 1.25% (flex should drain); HECA worst apron pair
9.84 m; CYXY spine 3 rows (§7-kill residue); SPLP self-overlap 8.48
m²; 11 composed-law test reds recorded in integrate/ evidence.
HYGIENE BACKLOG deferred: 3,786-line dead code, O4_DEBUG
consolidation, 110 move-to-config, provenance stamp, ~200 Tier-4
gates. Owner Qs pending: the 5 rulesets provisionals + split-level
pair question + strings verdict (parked feature).

**KCLT RE-BASELINE (04:20, HISTORY): the P4 tile build refreshed the road
feed — KCLT law-true 2,643→2,514 / steps 54→24 at current data
(control 1cc33da3; release anchor 307c3fcc is STALE). Dead-zone fix
flip-gated (O4_FLEX_DEMAND_TOL_FINE — HECA default moves
census-neutrally, 675fc645); its ladder runs gated.**

**RELEASE DELIVERED 2026-08-05 01:40 PDT — 4h20m early.** App
dist.nosync/XPTerrainBuilder.app 1.0.219 (engine 1.50.1665, JSONL
smoke-tested; DEVELOPER_DIR=Xcode-beta workaround — xcode-select had
reset to CLT). Tiles sim_review/release_0605/: HECA +30+031 embeds
release anchor a1ade8bd BYTE-IDENTICAL; KCLT +35-081 = ebf7b107
(production insets 100%/1m vs the lab frame 0%/31m the census
measured — instrument fix queued). RELEASE_NOTES.md in the same dir
is the owner's brief. Release anchors: SPJC f50f488d SPLP 0d967737
CYXY fd43f616 HECA a1ade8bd KCLT 307c3fcc HEAZ 9679dd1e @ 9863a7e.
NEXT TRAIN queue: DEM-follow HEAZ 47-node abort fix (unlocks the
composed world: HECA airside 8540→6402, KCLT 2297→1167), terrace
in-strip joint + over-fire, SPJC +16 attribution, consensus wall-half
integration, seam wall-site redesign, kill re-attribution, reg
families + rulesets B (drafts committed), lab-instrument inset fix,
compare_target re-cut (owner-signed), 5 owner questions pending,
**emit-amplification corner class (SPJC node 10625, 4x at a free
triple-shape corner, 50.67% spike — attributed, fix OWED BEFORE the
next flip round; release notes corrected)**.

**RELEASE TRAIN (owner 2026-08-04 22:30 PDT): Mac app built and ready
for in-sim testing at 06:00 PDT Aug 5. HARD DEADLINE.** Agile phases,
review + re-prioritize at each boundary; a lane not merge-ready at its
cut line PARKS for the next train (never rushed in):
- P1 now→01:00 — seven lanes land (seam v4, flip-adjudication,
  coupling, consensus, flex-convergence, test-maint, designer);
  serial merge as each reports.
- P2 01:00→03:00 — flip batch lands; stragglers merge; FEATURE
  FREEZE 03:00 (hard — after it only test/doc/verdict commits).
- P3 03:00→04:30 — THE TIP: identity + census battery mints release
  anchors, one full suite vs control; merge-to-main decision.
- P4 04:30→06:00 — release build: make_engine (verify freeze
  freshness — the iCloud silent-death trap), make_app (expect TCC
  re-prompt + LaunchServices first-open; direct-exec smoke test),
  fresh test tiles at release defaults (priority: +30+031 HECA/HEAZ,
  then KCLT +35-081; symlink pack textures, never reconvert; check
  .hgt present — the zero-DEM trap), RELEASE NOTES with the honest
  known-remaining list. Deliver 06:00.
Phase clock: agent notifications + the 20-min heartbeat cron; at
every wake, check this schedule and enforce cut lines.

**BOARD AS OF 2026-08-04 NIGHT (HEAD `ebe34c1`+).** Post-tip landings:
flex completion `9324cad` (self-anchor unlock/DEM-follow/honest B2/§2a,
all gated; composed 12-round STOP recorded — hook-vs-apply divergence
is the flex-convergence round's mechanism); one-seam-vocabulary
`ac1c689` (strip_seam_law.py, −276 dup lines); seam v3
owner-independent `bd1c8a7` (third-copy absorption, guard-exit
loudness, kill-control MEASURED: 34→109 battery-2, no new class, +74
four-class kill-gating item). Seam premise chain v1→v4 (each falsified
by pre-flight, all in the v2/v3 spec tails + bounds/ scratchpad):
final verdict = FOUR HEALER DEFECTS, owner question dissolved; v4
(`ebe34c1`, O4_STRIP_HEAL_LAW) IN FLIGHT. Also in flight: nothing
else. QUEUED: flip adjudication (band-seed-complete + DEM-follow +
strip-heal + terrace default-ON), coupling round (oracle landed),
consensus retirement, flex-convergence attribution, the kill
(anchor-minting, owner/lead), apply-minted end-zone round,
ring-asymmetry, baseline re-record → final-design profiling round.

**BOARD AS OF 2026-08-04 EVENING (HEAD `9d7eea0`, HISTORY).** Landed today:
seat-gates variant A (`58e2f99` — SEAT_BAND_CONSISTENT ON, coupler HELD,
new HECA anchor `a785f170`, others unchanged); the APRON TERRACE LAW
gated default "0" (`5eaf1e2`, adjudication `768cded` — gate-on at HECA:
apron.slope −52.9%, law-true within −25.5%, joint∩route ≡ 0 structural);
KCLT baseline nesting fix (`6a8f4bf`); licensing docs (`98e7805`); specs
approved: seam-continuity (`6a69d4f`), ref-pull interim (`57f033b`),
seed-fix + coupling reconciliation (`a5e96a9`), rsa amendments
(`9d7eea0`).  SPLIT-LEVEL SEATS: round HELD (verdict in its spec §ROUND
VERDICT, `4c6f449`; worktree seats-lane parked).  SEED ATTRIBUTION
VERDICT: owner's axiom confirmed — HEAZ infeasibility was 100% minted by
the per-edge quant margin compounding per path (raw law 0/2032); HECA
was ONE minted seat (band floor above own hard value + uncapped apron
polytope); every margined-envelope number battery-wide changes meaning
when seed-fix §1 lands.  IN FLIGHT: rsa-law (rebasing + ruling (b)
re-grade), ref-pull interim (worktree refpull-lane), seed-fix (worktree
seedfix-lane).  QUEUE: coupling round (after the oracle), consensus
retirement, adjacent_ground pre-flex band probe, open/closed ring
asymmetry fix, baseline re-record (machine reads 13-32% fast),
one-solve groundside, remaining reg families, SPLP tile-cut class,
test-maintenance (23 reds), scorer re-key, strings verdict LAST.

**THE KILL HALF** (`docs/specs/kill-half-spec.md`, owner-approved in
`b56b37a`).  Three things changed at once, and they are what a user now
gets:

1. **§1 THE DEFAULTS FLIP.** Eleven gates ship ON:
   `ROUTE_METRIC_ENVELOPE` (`019d0bb`), `RETIRE_TERRAIN_PIN_QUARANTINE`
   (`ceef13f`), `LATERAL_CONTIGUITY_LAW` + `NEEDLE_SOURCE_GUARD`
   (`1e5a781`), `SERVICE_LOT_ABSORPTION` + `TRIANGLE_PLANE_REPORTS` +
   `BAND_SEED_EXACT` (`495660a`/`5a94c57`), `SOURCE_COVERAGE_CHECK` +
   `RUNWAY_STRIP_WALL_LAW` + `DRAINAGE_SPINE_LAW` + `ROUTE_LEG_EXACT`
   (`0b9efaf`); `PROJECTION_STALL_REPORT` follows by implication.  Every
   gate keeps its env override, so `O4_<GATE>=0` restores the old path.
   **+1 SINCE THE SEAT-FLIP BATTERY (2026-08-04, lead ruling variant A):
   `SEAT_BAND_CONSISTENT` ships ON** — a full-frontage building seat
   clamps into the intersection of its selection interval and the NODE
   band at its own contact nodes (the band the projection enforces).
   Measured ALONE: HECA −303 law-true within (`building|building` 440→393
   AND the surrounding `apron` 6822→6665 / `junction` 1856→1781 follow it
   down), every other battery airport BYTE-IDENTICAL, no new over-cap
   class, no sweep cost (HECA 31 676, byte-equal to the pre-flip default),
   no build-time cost resolvable above the noise floor.
   EXCLUDED and still "0": `SCORER_SERVICE_ADJ` (re-key queued), the
   string gates (owner pause), `BREAK_BLEND_CONTINUOUS` (died with §2),
   and `SEAT_COUPLE_SHARED_SURFACE` — **HELD, and SEQUENCED not
   rejected**: measured ALONE it is HEAZ −1 / CYXY −4 / SPJC −7 but KCLT
   **+145** law-true within, migrating defects out of buildings
   (`building|building` 46→28) into AIRSIDE pavement (`apron` +75,
   `junction` +49) with a new `adj_edge::graded_strip` over-cap class at
   1.15 m — the airside-is-king failure mode.  Root cause is the
   CHORD-priced metric (at HECA it admits 152 coupled pairs with NO
   jointly-feasible seat set; 130 ship violating their own coupling
   limit), which is what `docs/specs/route-distance-seat-coupling-spec.md`
   (`a5e96a9`) exists to fix.  It re-arms after the seed-fix round lands
   the law-graph budget oracle and the coupling round re-prices
   admission/limits on it.  Separability is MEASURED, not assumed:
   `KCLT_sb1` / `SPJC_sb1` (this gate off, seat-band on) are byte-
   identical to their old defaults.

2. **§2 THE QUARANTINE MACHINERY IS DELETED** — not gated, deleted: the
   break blend and its continuity gate, the freeze (`broken` → immovable,
   and the `_final_projection_broken_keys` carry), all three
   `_break_node_ll` sinks (solve, projection, weld-relimit), the sidecar's
   `break_nodes` key, `check_grade`'s three splits (pairs, planes, steps)
   and `grade_graph_validate`'s break scoping.  Counts are FULL-CENSUS.
   The A2/A3/A4/B3 minters keep their REPORT halves only.

3. **§3 THE LOUD ERROR** (ungated, it IS the law):
   `building_feasibility.assert_no_final_band_inversion` fails the build
   when the FINAL reach band is inverted by > 0.01 m at any node, naming
   nodes, floor/ceiling and route distances.  MEASURED: fires ZERO times
   across SPLP/CYXY/HEAZ/SPJC/HECA (HEAZ carries 2 sub-materiality
   inversions ≤ 0.01 m, reported PASS-with-residual).

**NEW DEFAULT-ARM PATCH BASELINES** (body sha256, `tail -n +3`, built with
NO `O4_` var set).  The `8eab3acd`/`f460a8f7`/`b7d02779` gate-off anchors
below are RETIRED — gate-off is no longer what ships:

| airport | body sha256 (default arm) | vs the pre-kill CAND arm |
|---|---|---|
| SPLP | `1531e6d0`49bb1c6a7865fb9f6141a4cc565d18a58e942d2e47708b8b750f3853 | BYTE-IDENTICAL |
| CYXY | `5b7a1912`b5c1ce1641e66d4ebaf9d0271a4db24be1c2630ab41a00098fe259dc | BYTE-IDENTICAL |
| HEAZ | `5854d6e7`73126bd1c39954723e4cf305101a3e8d385647b75ecb88759b087859 | differs (see below) |
| SPJC | `b3875f84`b5bfbbefb1b99697703c84ee2e0427238ffd80ef1249180c49a76851 | no CAND dump exists |
| HECA | `2a28d01b`becaad3dc0c1686d1239e425904620b33499bf079ae8b3a9c37a808d | no CAND dump exists |

**SPJC ROW CORRECTED 2026-08-04** (seat-flip battery): the value recorded
here was 63 hex characters — a dropped character in `...84b5fbbefb1b...`.
The true 64-char digest, reproduced 3× that session (a gates-off arm, a
seat-band-only arm, and the dossier-round arm), is `...84b5bfbbefb1b...`
as now shown.  No surface changed; only the transcription was wrong.

**SEAT-FLIP BATTERY BASELINES (2026-08-04, lead ruling variant A —
`SEAT_BAND_CONSISTENT` ON, `SEAT_COUPLE_SHARED_SURFACE` held OFF).**
Default arm, no `O4_` var set, each reproduced 2× on this tree.  ONLY HECA
moves; the other five are byte-identical to the rows above, which is the
whole point of the variant-A ruling:

| airport | body sha256 (default arm) | vs the pre-seat-flip arm |
|---|---|---|
| SPLP | `1531e6d0`49bb1c6a7865fb9f6141a4cc565d18a58e942d2e47708b8b750f3853 | BYTE-IDENTICAL |
| CYXY | `5b7a1912`b5c1ce1641e66d4ebaf9d0271a4db24be1c2630ab41a00098fe259dc | BYTE-IDENTICAL |
| HEAZ | `5854d6e7`73126bd1c39954723e4cf305101a3e8d385647b75ecb88759b087859 | BYTE-IDENTICAL |
| SPJC | `b3875f84`b5bfbbefb1b99697703c84ee2e0427238ffd80ef1249180c49a76851 | BYTE-IDENTICAL (`sb1` arm) |
| KCLT | `74c4731f`2b8954b3d06a18c40c3539b694653e60728feed801b1245ea0d8477f | BYTE-IDENTICAL (`sb1` arm) |
| HECA | `a785f170`3d600fe2cd57da103978f95c96a8dd41da9da01b2f166c6e7578ac9d | **−303 law-true within** (9 952 → 9 649) |

The split-level-seats spec's band 1 needs NO re-base under variant A: the
126/105 frame remains the default frame.  The 152/130 empty-polytope frame
only exists with `SEAT_COUPLE_SHARED_SURFACE` ON, which does not ship.

HEAZ is the only airport whose band is inverted at all, so it is the only
one §2 can move: 796 of 6,204 shared vertices differ (p50 0.01 m, max
0.12 m — one to two emit quanta), 200 of 6,404 geometry vertices are
re-placed in junction and gap-interior rings, and NO runway vertex moves.
Every airport's `.axes.json` sidecar is exactly one key smaller
(`break_nodes` removed, `[]` at SPLP); no other sidecar key changed.

**SUITE**: 23 failed / 4,204 passed / 18 skipped / 13 xfailed — the reds
are EXACTLY the standing 23, name for name.  New xfail(strict) rows: the
2 CYXY drain-ledger tests (the exposed 1.9 % apron pair) and 5
exposed-consumer tests (below).

**BUILD TIME** (2 cold-equivalent runs each, foreground, exclusive,
default arm): SPLP 12.25 / CYXY 35.56 / HEAZ 54.73 / SPJC 174.99 / HECA
351.93 s, written to `tools/build_time_baselines.json`.  The owner's
approved ceilings (SPJC 153.2, HECA 315.4) are in
`tools/build_time_approvals.json`.  TODAY'S NUMBERS ARE ABOVE THOSE
CEILINGS AND THE ROUND IS NOT WHY: a same-session pre-kill control
(worktree at `4d20c7c`, CAND arm, warm caches) measured CYXY 35.8 /
SPJC 177.15 / HECA 336.5 s, i.e. the machine itself is 5-15 % slower than
during the overnight approval battery — visible on phases this round
cannot touch (HECA emit 79.7-80.1 s overnight vs 81.2-90.2 s in every arm
measured today).  Post-kill vs same-session pre-kill: CYXY −0.24 s, SPJC
−2.16 s, HECA +15.4 s, all inside the arms' own spread.

**THE SIM TILE**: `sim_review/zOrtho4XP_+30+031_DEFAULT/` (+
`DEFAULT_NOTE.md`), built with `O4_ vars in this process: []` — this is
what every user build now produces.  Textures symlink to the strings-on
pack as before.

**STOP-AND-REPORT items** (§2's exposed-consumer clause; nothing was
deleted on the implementer's authority, all are xfail(strict) with the
exposure named): `SVC_SPINE_EDGE_COUPLE` / `edge_couple_nodes`,
`O4_CHAIN_RIGID_BLEND` / `O4_BRANCH_RIGID_BLEND`, and fix-arm SITE 2 of
`O4_HARD_NEIGHBOUR_BOUND` — all three had their ONLY effect site inside
the deleted blend.

**QUEUE after review**: rulesets A/B with KCLT (the FAA fixture) →
missing-reg law rounds (strip precedence, abeam-longitudinal, RESA
transverse, ROFA back-slope per the approved exemption, shoulder crown,
runway-profile arc, RAOA, transverse solver-binding, groundside drainage
minimum) → KML-v3 class drain → strings verdict LAST.  Small items still
queued: spine-keyed scorer re-key, late-mint binding point, memo-key bug,
`service_junction` 8 % coupling (owner may split).

---

## 0-CAMPAIGN STATE — 2026-08-03 (SUPERSEDED by the 2026-08-04 block
## above; kept for the attribution chain)

**THE GOAL** (owner): iterate to five-airport LAW COMPLIANCE
(SPJC/SPLP/CYXY/HECA/KCLT — KCLT joins with the ruleset round as the FAA
fixture): zero ADJUDICATED violations (law includes its exemptions/
floors — instruments report, the law adjudicates), quarantine machinery
GONE, every reg generation-binding with test twins. Heartbeat cron
(session-local) re-anchors every 20 min.

**Committed through `495660a` + rulings `47455c1`** (read the commit
messages 0b9efaf..495660a for per-round numbers): the four field-report
fixes (strip walls / drainage law / lateral pricing+transect / coverage
guard + H1 source discriminator); the classification round
(lateral-contiguity law with the owner's ring-road tests, service-
adjacency scorer, drainage lockstep); quarantine rounds 1-2 (terrain-pin
export retired BOTH effects; sole-cause decomposition: ZERO of 287
genuine terrain-vs-law; HEAZ "inversions" = raster seed-cell bug, fixed
in kill-prep §3 to sub-materiality); kill-prep (absorption machinery
portion-only/spine-remains, triangle demotion, band seed fix).

**COMMITTED: the constants+absorption round** — owner
constants GROUNDSIDE 4→5% + SERVICE_ROAD 5→8% (cited in `config.py` and
`docs/STANDARDS.md` rows 25/27, ungated).  **NEW GATE-OFF BASELINES,
each reproduced 2×** — the old CYXY `dcebb6ff` / SPLP `c2316222` / HECA
`9a49cbce` anchors are RETIRED:

| airport | frame | baseline (body sha256, `tail -n +3`) |
|---|---|---|
| CYXY | bare | `8eab3acd`b470b7c285d61c609d9b3d7c4833974d607d71a765523c3008bac3f1 |
| SPLP | bare | `f460a8f7`178d7873c46051170c2488d2d96ae189d608d6e1a39ea3f5eac8955c |
| HECA | repaired | `b7d02779`be109710692558a4bcea0214861f236c1aebe2b9bc8ffd798295396b |

Both constants are GENERATION-binding (the new surface judged by the old
law is 2.2-2.5× worse); every runway vertex is byte-identical across the
change at CYXY/SPLP/HECA.  `service_junction` rides
`SERVICE_ROAD_MAX_GRADE` — flagged for the owner, not split.

Of the two kill-prep §1 STOP fixes: the merged-surface one-law regrade
LANDED (attempt 2 of 2, gated, big improvement but its pre-registration
missed — see the round report); the 21-runway-vertex airside violation
was **attributed and STOPPED, not fixed** — the suspected emit consensus
is FALSIFIED (staged snapshots: the runway field is identical up to
`AA_pre_solve` and diverges at `AB_post_solve_immediate`), the mover is
the SOLVE, because `service_road`/`service_junction` are
`PAVEMENT_ROLES` and `groundside_pavement` is not, so absorbing a road
into a lot changes solver MEMBERSHIP.

**QUEUE after it:** flip-and-kill (defaults flip + exclusive timing
battery + whole-pipeline review + machinery deletion + the loud
final-field error >0.01 m — measured to fire ZERO times today) →
rulesets A/B with KCLT → missing-reg law rounds (strip precedence,
abeam-longitudinal, RESA transverse, ROFA back-slope per approved
exemption, shoulder crown, runway-profile arc, RAOA, transverse
solver-binding, groundside drainage minimum) → KML-v3 class drain →
strings verdict LAST. Also queued small: spine-keyed scorer re-key,
late-mint binding point, memo-key bug, service_junction 8% coupling
(owner may split).

---

## 0-EVENING PIVOT — 2026-08-01 late (superseded by 0-CAMPAIGN STATE;
## kept for the attribution chain)

The owner flew both arms. VERDICTS: strings-on is "a massive mess"
(cliffs/canyons/tears); strings-off "still has many of the same type,
lower magnitude". STRING WORK IS PAUSED (his purpose statement: strings
are an anti-hills-and-valleys refinement for lawful taxiways, possibly
not aprons — memory `string-purpose-statement`). The QUARANTINE IS
UNAUTHORIZED (zero breaks in paved areas; ALL counts full-census —
memory `feasibility-is-guaranteed`, escalated). ATTRIBUTED CHAIN: the
visible mess = break regions (HECA α full census 19,591 rows/1,023
cliffs, 21.5k quarantined) × a DISCONTINUOUS blend weight
(value-Dijkstra dist by-product as geometric t — one_solve.py:1884; 80%
of ≥2 m close-pair steps carry |Δt|≥0.1) painting pockets manufactured
by FALSE TOPOLOGY: the final projection's envelope walks the pavement
PAIR graph (apron chords, zero-budget pad teleports, 45-hop/4.8 km
chains) instead of taxi routes, letting the two REAL 05L/23R↔05C/23C
tensions ceiling/floor 67%/53% of all break nodes at 3.3 km reach.
Owner directive: FIX THE ROUTE GRAPH ("via actual routes, not cutting
across the edge of aprons"). Counterfactual (megaanchor/): route metric
+ withdrawing non-route-role witnesses (47% of hard anchors —
graded_strip traces etc.) kills every ≥20 m deficit; residue ~17%/p50
5 m incl. the real 282 runway×runway class. IN FLIGHT: break-blend
continuity fix (spec `break-blend-continuity-spec.md`, implementing);
NEXT: `route-metric-envelope-spec.md` (written, implement AFTER blend
fix lands — same files); then residue attribution → quarantine retires
into loud errors → full-census validator → string refit LAST against
the repaired α surface. SPLP baseline is now `c2316222…` (corrected
CIFP; owner fixed a known-bad RW02 253 ft→158 ft). Probe purity fixed
(`b87a1dc`). Sim-review packs + KMLs in `sim_review/` (gitignored).

## 0. CURRENT STATE — 2026-08-01 EOD (this block supersedes §§3-8 below;
## §§1-2 — the delegation model and the owner's model — remain law)

**Branch `taut-string-chord-model`. Commits this session:** `50a12ea`
(probes: mover ledger + hook-time attribution), `b4ff1cd` (fix arm round 1),
`676f8da` (round 2). **Round 4 in flight** (spec
`taut-string-fix-arm-round4-spec.md`); round 3 was measurement-only.
Specs this session: `taut-string-probe-spec.md`,
`taut-string-fix-arm-spec.md`, `-round2-spec.md`, `-round4-spec.md`.

**Owner rulings added today:**
* Band-lawful displacement TRUMPS the DEM — metres moved is not a defect
  metric; conditions: endpoints in band, law-true spines, edge-follow
  (owner wants a simulator look before final say).
* There is ONE band (`reach_band_unified`); seats and string endpoints
  both consume it. Never describe its runway seeding as a second band.

**Old open defects, closed:** #1 G2 pin drag (final passes minted it;
fix-3 hold ⇒ HECA median 0.0020, 100% ≤1 cm; SPJC's residual tail was the
OFF-SPINE class below). #2 conflicts (mover ledger: 94% proj_u.blend,
zero sweeps; Ruling 55 bounding ⇒ 35 undeclared max 0.24 m; the 88
law_anchor class was STATIC — grip pin-vs-hard extension ⇒ 0). #4
hook-time band violations (no hard stamp guilty; plain P0 DEM seeds =
terrain above the runway-anchored ceiling). #5 flip gate READ:
854 → 837 (r1) → 747 (r2), decomposed 362 adjacent_ground-clamp (side
task, running separately) + 244 SPJC apron (⅔ = off-spine pin class,
round-4 fix) + 141 (37 release-induced junctions, 12 CYXY pin-vs-free,
92 post-solve-minted unattributed).

**Key mechanisms proven (do not re-derive):**
* Grip completeness: round 1 added pin-vs-hard pairs; round 2 made the
  grip's pair graph the LAW's graph (ring edges from the solve's own
  shape-constraints object streamed once + two-hop through-free family,
  tightest-budget min-merge). Chords never bent; ~29% of pins release.
* OFF-SPINE PINS (round 3, exact): S1b writes every pin but the phase-A
  freeze covers only `u_spine_adj` keys ⇒ off-graph pins get overwritten
  by phase B then held wrong. 32/32 movers off-spine vs 1,620/1,620
  on-spine at 0.000000 m. Fable ruling: a pin the solve cannot hold is
  not a pin (round-4 fix: applied vs `off_graph` ledger + `pin_frozen`).
* DECLARED WEB = LAWFUL BOOKKEEPING (round 3): 0/176 HECA declared
  both-pin nodes at any created defect, 100% law-true; escalation to a
  route-metric grip is RULED DOWN to a monitoring ledger (alarms:
  unquarantined residual >single digits, or defect-coincidence > random
  control). Rod chains are the cheapest subclass, not the priciest.
* Canonical identity join: the .osm 11-decimal spelling IS the canonical
  key (0 collisions); never proximity-join (11.6% wrong-object). ~63% of
  pin vertices are emit-decimated (survivorship bias in any per-pin
  emitted stat).

**Gates:** `O4_TAUT_STRING_CONSTRUCTION` still default "0";
`O4_STRING_MOVER_LEDGER`, `O4_HARD_NEIGHBOUR_BOUND`,
`O4_STRING_PINS_FINAL_HOLD` default "0". Gate-off byte identity: CYXY
`dcebb6ff…` unchanged; **SPLP BASELINE = `c2316222…` (2026-08-01, final).**
*(Both hashes RETIRED 2026-08-03 by the owner-constants round — current
baselines are in §0 above: CYXY `8eab3acd…`, SPLP `f460a8f7…`, HECA
repaired `b7d02779…`.  The story below is still the reason SPLP's
anchor is what it is.)* Full story, all
attributed: SPLP RW02's true elevation is **158 ft** (owner-confirmed;
DEM was right). The owner's mid-day CIFP update had introduced OLD
INCORRECT data (253 ft) — that WAS the "unattributed" hash flip
(`d8d0f065…` → `1d7f6fc7…`; Custom Data dir mtimes moved 12:21-12:22,
file mtimes preserved, which is why the bisect could not see it). Round
7's "old baseline buried the threshold" verdict INVERTS: the keep-CIFP
rule was faithfully applying garbage. Owner fixed the CIFP; the
corrected build hashes `c2316222…` (3× reproduced) with RW02 anchoring
low and only a ~2 m tiered-budget deficit (was 14.6 m under the bad
value). `1d7f6fc7…` is retired. The specced instrument stands and is
now proven necessary: env-gated threshold-reconciliation print +
composed-DEM (and CIFP) fingerprint in patch provenance — a data update
must announce itself, not surface as a hash flip. Probe purity: `O4_STRING_MOVER_LEDGER` proven
byte-inert at SPJC + HECA after round 7's read-only registry query +
published-attribute fence (before that fix, probe-on arms were NOT
production at SPJC). Flip
decisions after round 4; the `O4_HARD_NEIGHBOUR_BOUND` flip changes
α output (75/88 anchor conflicts pre-exist gate-off) and goes to the
owner with battery evidence.

**Next after round 4:** rule on the round-4 reads (off-graph tenure
scope, release-induced junctions, CYXY blind spot, post-solve emitter
probe) → gate flips → suite read → R1 re-read → R1 CP2 → R2 → battery →
owner's simulator look → tile/app. Session scratchpad artifact sets:
`ruling55/ flipgate/ fixarm/ round2/ round3/ round4/` (ephemeral — key
numbers are in the specs and commit messages).

---

(Below: the 2026-08-01 morning handover. §§1-2 remain law; §§3-8 are
superseded by §0.)

Supersedes the 2026-07-31 handover (that one describes the tube-and-funnel
constructor, which is **retired**). Written for a new session to finish the
work. **Do not re-derive §2 or §4** — they cost builds and rounds.

---

## 1. Delegation model (owner standing rules — do not violate)

* **Fable = design and review ONLY.** It writes ALL specs and rules EVERY
  mid-implementation deviation. It never implements.
* **Opus = implementation and investigation.** Every `Agent` launch passes an
  explicit `model`.
* Canonical text: `Ortho4XP/CLAUDE.md` §"Working style" item 1a.
* **Report IN-TURN.** Never end a turn holding a completed measurement, and
  never rely on a completion notification to wake the coordinator. That
  pattern cost **eight hours** on 2026-07-31: a finished build sat unread
  from 22:45 to 06:37. Poll builds inside your own turn.

## 2. The owner's model — all rulings, do not re-litigate

**What a string IS (2026-07-31, verbatim):**
> "The string is always a straight chord through space, only the end points
> sit in the middle of the band."

* A string is a **straight chord between two points**. Its two ENDPOINTS take
  **band centre**; between them the chord **may run above or below the band
  freely** — the solver pulls the taxiway to its cap where it does.
* **The string never bends.** It is an idealized elevation target, never
  emitted.
* **Strings are PREFERENCES. Grade law overrules them. A string must NEVER
  CAUSE a grade-law violation.** (Owner, verbatim: *"they should never CAUSE
  a grade law violation… the grade law overrules the string when needed."*)
* Corollary, Fable Ruling 52: **the chord is never bent by law — the GRIP
  is.** Where two pinned ends would force an over-cap pair, the *pin*
  releases; the chord is never modified or clipped.
* A string's whole elevation content is **two numbers**. The hook evaluates
  the chord per vertex by **linear interpolation on the chord station**.

**Owner constants — ONLY HE MOVES THESE:**

| constant | value | job |
|---|---|---|
| `TAUT_STRING_SPINE_TOLERANCE_M` | **8.0** | membership + string-vs-spine validation |
| `TAUT_STRING_MIN_STRING_M` | **100.0** | string duty (sub-100 stays inventory) |
| `TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M` | **50.0** | clip remainder floor |
| string count | **≤ 50** | sanity bound |

Ours, not his: `SUBSTRATE_STATION_M` 5.0, `SUBSTRATE_INTERN_M` 1e-6.

**Other owner rulings:**
* **Runway clip:** clip strings by the **runway outline**, discard anything
  inside, drop remainders < 50 m. Outline = the **shoulder-absorbed union**
  (75.6 m at HECA), not the declared rect — his ruling, because shoulders are
  paved and the runway profile grades them.
* **Substrate** = apt.dat S2 snapshot (`pipeline.py:2253`) ∪ OSM linear
  taxiways, **apt.dat-first, per-LOCATION dedup** (the clause is locative).
* **CIFP is the source of truth for thresholds.** HECA: 05C = 116 m (south
  end), 23C = 114 m (north end). Band centre at chord 1's endpoints matches
  these to +0.07 / +0.61 m — the endpoint law is sound.
* **Chord 1 legitimately descends to 106-107** between along 1462 and 1865
  (his coords 30.116015,31.416090 → 30.113677,31.412894) because of the
  cross-connectors to the much lower 05L/23R, then rises near-straight to
  along 2403 (30.110475,31.408709). **His earlier "111→113" is the IDEAL
  string, not the expected surface.**
* Ground truth: `/Users/noah/heca_strings.osm` — 46 ways, 99 nodes,
  41,412.7 m polyline (the specs' older "40 / 37,327 m" is superseded).

## 3. Where the work stands

**Branch `taut-string-chord-model`, HEAD `d424c9d`, tree clean.**

| commit | content |
|---|---|
| `f1b13c3` | chord model, substrate, clip, tenure, specs |
| `53e1156` | the S1 hook + S1b Dirichlet pins in `solve.py` |
| `d371e68` | working-tree snapshot (other lines' work — recovery point, do not merge wholesale) |
| `b9bd57d` | the pin ledger |
| `d424c9d` | **Ruling 54** + stop-reason and departure ledgers |

**Gate `O4_TAUT_STRING_CONSTRUCTION` default `"0"`. Gate-off byte identity
proven three-way and re-proved after every change: SPLP `d8d0f065…`,
CYXY `dcebb6ff…`** (body hash past the provenance stamp).
*(Historical — both superseded; see §0 for the live baselines.)*

**Landed:** substrate assembly + per-location dedup + seam joints; runway clip
at the owner's outline and floor; through-path composition (authoring
boundaries are NOT chain boundaries); string tenure (an edge is spent only
when an emitted string covers it); the chord model with the three endpoint
read modes; the grip filter; **Ruling 54** (`yield_hard` gains the
law-filtered kept pin set); three ledgers (`pin_ledger`, `walk_boundaries`,
`departures`).

**Retired** (measured, with per-test disposition): the tube, cap propagation,
the funnel, the slope audit, `taut_chain_profile`, `BendWitness`, the
infeasible `StringDefect` classes, the (ii-b) end-datum machinery, §3's value
machinery, the fragment-assembly family.
**KEPT and RESCOPED** (Ruling 53): the phase-A taut pass — provably inert on
strung ground (0 of 3,429 pinned vertices move), retained as the **residual
spine smoother** on unstrung spine. Its footprint (567 vertices moved, max
0.283 m) is the baseline for any future retirement.

### 3a. Implementation map (`route_profile/taut_string.py` unless noted)

| symbol | role |
|---|---|
| `read_endpoint_band_centre` / `EndpointRead` | Ruling 49's read law: `direct` / `interpolated` / `clamped`. HECA 101/0/27 — mode 2 empty **there**, not in general. No snap, no radius constant. |
| `chord_station`, `chord_targets` | z linear in along-station **on the chord** — two numbers give every node a target |
| `compass_ends` | N/S labels from coordinates. **Endpoint order is WALK order and carries no geography** — this caused a transposition that cost a round |
| `filter_pins_by_grade_law` | Ruling 52 grip filter: strict `>` at 1e-9, minimal via a **re-admission pass** (not a greedy stop), endpoint-protective, never releases a law-anchor pair |
| `spine_walk_chains` → `compose_through_paths` → `through_path_chains` | the seam. Global best-collinear pairing, parameter-free; **paths stay LINEAR — that is what keeps open-terrain crossing unrepresentable** |
| `strings_with_tenure` | an edge is spent only by an emitted string; cut/`min_len` edges return; fixpoint, termination arithmetic and asserted |
| `substrate_fingerprint` / `substrate_from_carriage` / `decorate_nodes_onto_strings` | carriage hook side. **Decoration is multi-valued on purpose** (§3 shared-vertex); its index walks segments cell-by-cell — a bbox fill would allocate ~64 M cells for a 4 km diagonal |
| `write_string_sidecar` | idempotent, **called LAST** (see trap 3) |
| `construct_taut_strings` | carriage → service exclusion → chaining → tenure → clip (per-string, so remainders keep the pre-clip chord) → decoration → targets |
| `solve.py` | targets computed at the phase-A call site, grip-filtered, passed as `string_pins=`; merged into the **existing `anchors` set**; post-phase-A overwrite gone; **Ruling 54: `yield_hard |= kept pins`** |

**Ledgers in the `string_domains` sidecar:** `pins`, `walk_boundaries`
(with `is_emitted_end`), `departures`, `pins_in_yield_hard`,
`pin_yield_conflicts`, plus the four counts.

**Retained deliberately:** `taut_string` / `string_with_pegs` are the **§10
rod sweep's**, not string construction's — do not retire them with the
constructor family.

## 4. Measured results — do not re-derive

| | |
|---|---|
| chord 1 delivered at the dip | **106.40 / 106.90** vs the owner's ~106 |
| W-CHORD1 worst bin | −11.07 (baseline) → −10.74 (S1b) → **−5.83**, and it **moved off 1800 to 1600** |
| string-authored defects | **949 → 0** (dissolved by construction) |
| seam pair (W-CHORD2) | 107.83 → 107.83 = **0.00 %** grade, law passes with margin |
| GATE A (length-weighted coverage @ ±8 m) | **86.2 %** |
| GATE B (chord 1 end-to-end) | **FAILS as one string** — corridor fully covered by 3, zero gaps |
| Stage 0 + value path | **73.5 ms**, cheaper than the funnel it replaced |

**The drag mechanism, attributed:** `fp#8` rebuilt `yield_hard` from
`truth_hard` and never inherited the spine freeze, so every vertex phase A
froze went free again and the blend moved it. Ruling 54 fixes it by adding
the kept pins. **Wholesale freeze inheritance was measured to recover the
same ~5.2 m and was rejected** — it over-freezes the unstrung residual that
must yield.

## 5. OPEN DEFECTS — with evidence

1. **G2 FAILS IN PRODUCTION.** `max |emitted − chord|` at kept pins: median
   **0.2342 m**, p90 1.1407, **max 6.9008**; only **28.5 %** within 0.05 m.
   Offline it was 0.000e+00. *Population caveat: 1,580 of 3,790 kept pins
   matched a delivered node within 1 m; the rest are probably spine nodes
   with no nearby emitted vertex — unconfirmed.*
2. **Free-neighbour cap coupling — RULED (Fable Ruling 55), fix not yet
   implemented.** `n_pin_yield_conflicts = 874`: **`free` 786 /
   `law_anchor` 88**, excess median 1.616 m, max 14.682. On chord 1: 36, with
   the **1400-1800 bin holding 7, all `free`, max excess 7.92 m — the same
   station the worst bin moved to.** A pin cannot be moved directly, but its
   un-pinned neighbour can, and cap coupling drags the pin: **the string
   overruled by a blend TRANSITIVELY through the cap.**
   **THE RULING: the neighbour inherits NO freeze and NO new mechanism — it
   already owes the pin exactly one thing under law, the cap.** A yield/blend
   candidate adjacent to a hard node moves within `[hard ± cap·d]`
   intersected with its own law. **BOUNDING, never freezing** — `cap·d` is
   the law's own freedom, so corridors still descend away from pins at cap
   rate. Freezing the neighbours is the wholesale freeze by another name and
   stays rejected. **The law is stated for ALL hard nodes, pins and truth
   anchors alike** — the 88 `law_anchor` conflicts show the same violation
   against anchors, so this was never pin-special; the defect is **any stage
   that MANUFACTURES an over-cap pair against a hard node.**
   **THREE SEPARATIONS BEFORE THE FIX, IN ORDER** (mechanism before fix):
   **(i) THE JOIN FIRST** — 2,210 of 3,790 pins unmatched at a 1 m proximity
   join is the verify-the-reference failure live in our own instrument.
   Re-state the pin→delivered join on **CANONICAL identity** and re-read G2
   on the identity-joined population. **The 0.2342 m median may be partly a
   wrong-object artifact and must NOT be quoted as pin drag until then.**
   **(ii) THE MOVER LEDGER** — per conflict, which stage last moved the free
   member (stamp if cheap, report if not). **(iii)** the 88 `law_anchor`
   conflicts against the α arm: pre-existing or new, one artifact comparison;
   pre-existing routes to its own track.
   **Pre-registered for the fix arm:** identity-joined G2 at pins returns to
   the 0-class where neighbourhoods are lawful; manufactured conflicts
   874 → ~0; the 1600 residual closes toward band/cap-explained;
   hard-adjacent yield infeasibilities surface as **declared** conflicts,
   small and author-carrying — **a large declared population is a finding**
   (the pin web over-constraining the yield network) and returns to Fable.
3. **Chord 1 fragments into 3 strings.** Boundaries at along 398 (turn /
   consensus / route_end, mixed) and 728 (**both ends `consensus`**).
   Corridor census over 239 boundaries: **turn 2**, tenure 113, route_end 63,
   consensus 61. **This is OURS — direction-symmetry and tenure — not the
   owner's tolerance.**
4. **49 hook-time band violations** in the dip window (90 of 966 banded
   corridor nodes above their own ceiling at hook time, worst +2.11 m). The
   corridor arrives at the hook already outside its feasibility band.
   **Upstream of everything else, unattributed.**
5. **The string-attributed law-true slice is UNMEASURED** — that is the flip
   gate (Ruling 19: it must be **zero**). `n_defects = 0` is NOT that gate.
   Needs `O4_TEST_AIRPORTS=HECA test_pavement_grade`, which does **not**
   scope to one airport — price it as four airports / ~710 s.
6. **Offline-vs-production substrate divergence, 3 instances, unattributed**:
   22 apt pieces, 7 OSM ways, 18 strings. **The offline walk is no longer a
   production stand-in.** Make production emit what it did.

## 6. NOT STARTED

* **R1's layer-4 re-read** (offline, on the artifacts) → **R1 CP2** → **R2**.
  R2 is blocked twice over: `O4_REFERENCE_FIELD` is default `"0"` with its CP2
  gates unread, AND S1 changed R1's layer 4 (the spine layer is now the chord).
* **The battery**, then **the tile and the Mac app**. The owner cancelled the
  tile deliberately — he will build his own once the known issues are resolved.
* **A suite read** before anything ships (the live comparator is 24 stable
  failures across 9 files; there were also 5 unrelated `test_crown_seam_ramp`
  reds from a concurrent session).
* **The §6.4 owner filing.**

## 7. Method lessons paid for in this session

**THE DOMINANT FAILURE MODE: two instruments describing different
populations while assumed to describe one.** Seven instances in one night,
**every one caught by an implausible NUMBER, none by code review**:

* distance-to-centerline over a set containing the string's **own source** →
  every apt-tier string read 100 %;
* "corroboration" at 25 m matching the **parallel taxiway 15 m away**;
* a conclusion built on **transposed labels**;
* a pin verdict sampled along the **chord line in the plane** while pins
  follow the walked path — 5 matches against a 311-vertex string;
* a decomposition mixing **two coordinate projections**;
* **the max of a FILTERED set reported as the max** — vertices filtered to
  ≤ 25 m, max quoted as 24.94 m (the filter edge). Real value: **8.64 m**.
  This nearly reached the owner as a structural impossibility that did not
  exist;
* an inventory keyed by `first_vertex`, silently losing **8 of 64 strings**
  while the summary still said 64.

**Defences that work:** predict the magnitude before computing; treat a
too-clean or too-extreme result as a reason to audit the instrument;
exclude the measured object's own source from any reference set; pin ONE
frame/axis/projection and state it beside every number; **make production
emit what it did** rather than reconstructing offline.

**Also standing:** mechanism before fix (interventional evidence, or say
"the data cannot attribute this"); intent questions route to the OWNER, not
to a build — he has ruled correctly from his own data repeatedly, and he
supplies artifacts; a gate-off identity arm is not ceremony (it caught a
shadowed-import `UnboundLocalError` that broke the ungated path for every
airport, which the AST and import probes could not see).

## 8. What the next session should do

1. **Get Fable's ruling on the free-neighbour question** (open defect 2) — it
   is the last named thing between here and closing the residual.
2. **Measure the string-attributed law-true slice** (open defect 5) — it is
   the flip gate and it has never been read.
3. **Attribute the hook-time band violations** (open defect 4) — upstream,
   and it may explain why the clamp bites so hard at that station.
4. Then **R1 re-read → R1 CP2 → R2 → the battery**, per the owner's own
   sequence, and only then a tile and the app.
