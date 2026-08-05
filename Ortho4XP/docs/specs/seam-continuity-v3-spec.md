# Seam continuity v3: adjudicate the step, then bind where values are born

Fable spec, 2026-08-04, assignment 6 V3 (designer-authored,
lead-approved) — after v2's §0
pre-flight caught the value-authority miss before any build
(seamv2/RESULTS.md: the zone writeback at solve.py:4055-4084 re-derives
every edge-owning band node from raw DEM + corridor clamp AFTER any
projection; no projection writes graded_strip at all; §3-v2's box was
vacuous by construction). The owner's endgame authorization stands.
Lines against the tip (main 9324cad; kill inventory at fb85f5a per
seamv2 §3 — re-verify by blast.py at dispatch). BINDING:
docs/RULINGS.md (law compliance, not instrument-zero; single-solve;
airside-is-king; intent questions route to the owner; convergence
guards). **DISPATCH GATE: §3 branch selection waits on the owner
question below. §1, §2's loudness, and §4's kill-control measurement
are owner-independent and may dispatch immediately.**

## §0 Population pre-flight — PERMANENT, now three-part

The v1/v2 lesson institutionalized as a checklist every arm must pass
offline BEFORE building: (1) POPULATION — the law-bound nodes intersect
the census population (v1's miss); (2) AUTHORITY — the binding site is
the one that WRITES the emitted value (v2's miss); (3) ORDERING —
nothing downstream overwrites it (v2's third fact). v3's own
pre-flight: prove, from the resampler formula + patch data offline,
that the chosen branch changes the 8 sites' EMITTED values (Branch D)
or that the declaration predicate fires on exactly the 34 rows
(Branch T).

## The adjudication (measured, then ruled — seamv3/ scratch)

The strip-footprint join ran on the HASH-VERIFIED tip anchors
(refpull_interim/tip/patches/HECA_anchor1.osm = 122708ac…, CYXY =
d89b73a8…; sites and runway geometry from the SAME patch and frame;
seamv3/stripjoin.py):

| site | rows | worst \|de\| | nearest strip | lateral (half-width) |
|---|---:|---:|---|---|
| HECA (−102, 30) | 1 | 4.260 | 05C/23C | 715.5 m (75) |
| HECA (−156, −33) | 6 | 3.340 | 05C/23C | 404.2 m (75) |
| HECA (−100, 31) | 1 | 3.340 | 05C/23C | 696.5 m (75) |
| HECA (−156, −34) | 1 | 3.330 | 05C/23C | 384.2 m (75) |
| HECA (−135, 88) | 10 | 2.840 | 05L/23R | 458.9 m (75) |
| HECA (−103, 30) | 4 | 2.790 | 05C/23C | 728.2 m (75) |
| HECA (−120, 87) | 5 | 1.980 | 05L/23R | 715.5 m (75) |
| CYXY (−16, 15) | 6 | 1.800 | 02/20 | 190.4 m (30) |

1. **Strip precedence: RULED OUT by measurement.** Every site is
   5–10× the half-width outside every strip footprint (end corridors
   included). v3 does NOT compose with the RSA machinery; the
   runway-edge wall prohibition does not reach these sites either.
2. **The adjacent-ground zone-law terrace clause does not cover the
   class.** Both sides are emitted GRADED band fabric (one
   pavement-welded row, one floor-free DEM-draping cut row —
   seamv2's structural reading, 6 of 8 sites); the clause exempts the
   graded/DEM boundary only. It is not stretched by fiat here.
3. **The healer's declined rule is correct non-authority behavior; its
   SILENCE is the defect.** `blend_cross_strip_seam_steps`'
   every-node-anchored⇒genuine-step rule is the single-authority
   doctrine working (a healer must never silently regrade anchored
   fabric). But "left alone" without declaration violates loud
   attribution: OWNER-INDEPENDENT change — a declined cluster emits a
   named report (site, height, anchored sides) through the forensics
   channel, unconditionally.
4. **The class disposition has NO standing ruling** — both remaining
   dispositions are owner intent. Per "intent questions route to the
   owner", the question ships with artifacts, below.

## THE OWNER QUESTION (gates §3 only; KML at
## scratchpad seamv3/seam_sites_v3.kml, 8 placemarks)

At 8 sites (7 HECA, 1 CYXY; table above) the graded-strip band fabric
steps 1.8–4.3 m where a floor-free CUT row (lawfully draping raw DEM
under its own ceiling) meets a PAVEMENT-WELDED row holding the
pavement edge. All sites are far outside every runway-strip footprint
(measured); both sides are graded fabric, so neither the terrace
exemption nor strip precedence decides. The cross-strip healer sees
exactly these pairs and declines them as genuine steps. **Is such a
step (A) a lawful terrace to DECLARE — retaining-wall face + census
exemption; if so, with what height bound, if any — or (B) a defect —
the cut row must be floored/blended to its welded neighbour where the
rows meet?** Context: this class GROWS when the ref-pull dies (the s7
12→93 signature); (A) accepts more/taller declared terraces at the
kill, (B) bounds the step at value-minting regardless of the kill.

## §3 The two branches (dispatch ONE, after the answer; both gated)

- **Branch T — declared terrace** (`O4_STRIP_STEP_DECLARED`, "0"): on
  decline, the healer emits the declaration (retaining-wall face via
  the retreat machinery, or the declaration tag) + the census exempts
  DECLARED joints via a shared-module predicate reading the SAME
  declaration (lockstep); height bound if the owner sets one; count
  and heights censused per airport. No surface movement.
- **Branch D — continuity at minting** (`O4_BAND_ROW_CONTINUITY`,
  "0"): a cross-row constraint where adjacent rows of different
  regimes meet — the cut row's boundary values adopt the welded
  neighbour's within the cut row's own ceiling (direction: weld gives,
  cut conforms; PAVEMENT UNTOUCHED — airside-is-king intact). Binding
  site is the band-value minting (the zone writeback / resampler),
  i.e. where the emitted value is actually born — passing §0's
  authority + ordering checks by construction. The healer's population
  empties; the validator needs no new exemption.

## §1 Module + third copy (owner-independent)

The strip_seam_law.py module is LANDED (ac1c689 — identity CYXY 2x +
HECA 1x exact, census row-for-row; the seamv2 close-out). v3's §1
work is ONLY the third-copy absorption: it absorbs the THIRD constants copy:
`SEAM_STEP_RADIUS_M`/`SEAM_STEP_MIN_DELTA_M` in
`blend_cross_strip_seam_steps` (adjacent_ground.py:1662, run at
pipeline.py:6262) become imports of the module's
`STRIP_SEAM_TEAR_RADIUS_M`/`STRIP_SEAM_TEAR_MIN_STEP_M`;
identity-not-equality twins extended. seamv2's flagged deviation is
resolved as taken: the module lives in src, tools imports src,
grade_graph_validate keeps only the TILE_SEAM rename (no strip import
until a strip consumer exists).

## §4 Sequencing and the kill

ORDER IS LAW: (1) kill-control arm (`O4_YIELD_REF_WEIGHT=0`) at
HECA + CYXY FIRST — the 0.02→0 exposure is still UNMEASURED and
nothing is banded before it is quoted; a NEW casualty class outside
the strip family at this arm is a STOP (v2 Ruling B carried: that
class gets its own law before the kill proceeds). (2) The chosen
branch arm at tip defaults. (3) Branch + w0 — the law must hold the
class through the kill. Kill inventory per seamv2 §3 (fb85f5a
line numbers; blast re-verify — it has drifted at every anchor so
far; `solve.py` carries 42 env flags, the kill must not take a
neighbour). The kill remains the next ANCHOR-MINTING event; landing
it is the lead/owner's deliberate decision, not this round's.

## Pre-registered outcomes (bands)

0. §0 three-part pre-flight per branch (offline, hard gate).
1. Kill-control QUOTED, not banded (the exposure measurement): HECA
   seam 28 → X, CYXY 6 → Y, full class table; second-casualty scan.
2. Branch arm, tip defaults: the 6 cut-beside-weld sites resolve —
   Branch D: HECA `seam::seam` 28 → ≤8 success / ≤16 partial, CYXY
   6 → 0; Branch T: same residual counts UNDER the exemption, with
   declared-terrace count ≈ the exempted rows, quoted. The 2
   non-conforming sites (the (−156,−33/−34) raised pattern,
   +4.24/+0.90 ABOVE host) are pre-registered as OUT of the branch's
   fix population — attributed separately, never forced.
3. Branch + w0: the class stays within band 2's level (+small); the
   s7 93-row signature does NOT reappear; the branch's law is thereby
   proven to be the load-bearer the pull was.
4. Pavement byte-identity in branch arms (the law binds band fabric
   only — hard); runway vertices byte-identical everywhere.
5. Healer-decline loudness: report rows == declined clusters (34
   today), zero silent declines (hard).

## Acceptance

Gate-off byte identity 2× on the tip campaign anchors (cited from
refpull_interim/RESULTS.md's anchor table; re-pin at dispatch PRE_REG
if any lane has minted since). Suite: same reds vs a matched pristine
control, identical selection; new twins (§1 identity twins extended to
the third copy; decline-loudness; branch predicate membership on the 8
sites; Branch D direction test: weld value unmoved, cut adopts;
Branch T declaration↔exemption lockstep). Timing: gates SUSPENDED
(RULINGS defer+tripwire) — ledger tripwire only, no timing claim. Build budget: kill-control
HECA+CYXY, branch arm ×2, branch+w0 ×2, identity 2×5 ≈ 2–2.5 h honest
wall; foreground; WORKTREE; no commit; phase-C (the kill) excluded
from this budget and this round's authority. Convergence guards:
0.01 m materiality, 2 attempts, `.progress`.

## STOP rules

Owner question unanswered ⇒ §3 does not dispatch (§1 + loudness +
kill-control still deliver); §0 pre-flight miss on any part; a second
casualty class at kill-control; band-2 miss after one fix attempt;
any pavement movement in a branch arm; second miss on any target.

## Out of scope

The kill's landing (anchor-minting, lead/owner); the full band-writer
single-solve ingestion (Branch D is minting-local continuity, not the
ingestion — the ingestion round inherits both branches' constraints);
strip precedence / RSA machinery (measured out); the 2 non-conforming
sites beyond attribution; consensus retirement; emit decimation.

## LEAD ADJUDICATION (2026-08-04 late; owner-independent parts landed
## bd1c8a7; evidence scratchpad seamv3lane/)

1. §2's premise FALSIFIED by the loudness work itself: the
   all-anchored decline population is EMPTY at both airports. Every
   census row traces to the healer's NON-WORSENING GUARD exiting
   silently — BLOCKED (bounds inverted, lo > hi: CYXY's site has
   bounds [695.960, 695.750]) or CLAMPED (moved to a bound, residual
   4.26 m = the census row); 2 of 8 sites are not healer pairs at all.
   The guard-exit loudness extension is RATIFIED (band 5's intent was
   zero silent leave-alones; the guard exits ARE the silent channel).
2. **THE OWNER QUESTION IS SUSPENDED** — its framing ("declined
   genuine steps") is materially wrong: 6 of 8 sites are steps the
   healer WANTS to close and cannot. The BLOCKED case is an inverted
   interval — the empty-polytope shape feasibility-is-guaranteed
   forbids — so MECHANISM-BEFORE-FIX applies: attribute WHERE the
   inverted bounds come from (which law supplies lo, which hi, and
   whether the inversion is a defect or genuine law tension) BEFORE
   any intent question. If the bounds are defective, the healer closes
   the steps and both §3 branches die unbuilt; only if the inversion
   is genuine law tension does the terrace-vs-floor question return to
   the owner, reframed.
3. Kill-control adjudication (v2 Ruling B): NO new casualty class
   under the strict reading — no STOP. The substantive +74 rows across
   four existing classes at HECA (junction +48, building +26,
   transverse +5, step_mid +2) against net −672 is recorded as a
   KILL-GATING ATTRIBUTION ITEM: those rows are adjudicated, never
   netted, before the kill lands.
4. The FOURTH constants copy (SEAM_STEP_MIN_GRADE ==
   STRIP_SEAM_TEAR_MIN_GRADE) is QUEUED for absorption WITH the
   bounds-attribution round's verdict (coupling the emitter's cliff
   test to the census is a design decision that belongs with the
   healer's law, not a mechanical move).

## BOUNDS-ATTRIBUTION VERDICT (lead, 2026-08-04 night; evidence
## scratchpad bounds/; the suspended owner question is WITHDRAWN)

The probe closed every bound arithmetically against the hash-verified
tip patches. THE INVERTED BOUNDS HAVE NO TWO-LAW TENSION: both sides
are the SAME constant (STRIP_SEAM_TEAR_MIN_STEP_M − 0.05) quoted
against two different excluded neighbours — inverted iff two outside
neighbours differ by >1.90 m. Defect class, three mechanisms:
1. The guard OMITS the MIN_GRADE conjunct its own pairing test and
   the census apply (over-strict up to 3x at the measured 2.2-6.0 m
   distances); the inversion-creating neighbours are drapes the
   healer's own cliff test declared lawful. A lawful assignment is
   computable at every inverted site — feasibility-is-guaranteed
   holds; the empty polytope is the guard's, not the law's. The guard
   also actively MINTED rows (dragged a lawful node 1.9 m down onto a
   tear). Fix: the guard's allowance becomes identical to the census
   predicate (max(MIN_STEP, MIN_GRADE·planar) − 0.05), absorbing the
   FOURTH constants copy. Static: CYXY 6→0, HECA 28→~11.
2. TARGET defect: the healer AVERAGES disagreeing weld authorities
   (benches 5.58 m apart in level → an unlawful middle; the CLAMPED
   nodes were the lawful ones) — the emit-consensus minting pattern
   reproduced inside the healer. RULED BY STANDING LAW, no owner
   question: single-authority doctrine + emit-consensus precedent +
   the owner's 2026-07-19 ruling (a genuine level change is
   horizontal WALL geometry, and the wall machinery exists). The
   healer must never average across disagreeing anchors or a stacked
   wall; those joints belong to the wall passes. Wall-pass ordering
   vs wall-aware healer is a DESIGN decision (v4).
3. Residuals: the hard 6.0 m radius splits clusters (a 4.26 m cliff
   between mates 1.5 m apart); two sites are minted post-healer (wall
   emitters + late writers run after with no reconciliation).
V4 (final seam design): grade-aware guard + authority-split clusters
+ radius fix + post-healer ordering/declaration + the kill sequencing;
both v3 §3 branches DIE UNBUILT. Static predictions must be verified
for second-order effects before landing.
