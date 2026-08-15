# Constructive solve — the sub-minute lawful patch (Fable, 2026-08-14)

Owner charter: produce a HECA-class auto-patch in under one minute by
CONSTRUCTING a lawful surface instead of optimizing toward one, ship
it BESIDE the iterative model behind a mode switch, and let the in-sim
A/B decide whether the expensive model earns its time. This round
absorbs the chartered publish/pair perf round (the two output-moving
candidates dissolve into the constructor's territory).

## Premises (all verified this session, cited to the record)

- The law is BINARY and thin (owner rulings 2026-08-14): caps, welds,
  runway crowns, enclosed-area drainage spines, adjacent-ground
  slopes, seam continuity. DEM deviation is not reported or
  considered; FLAT is lawful; taxi/road surfaces get no drainage
  curvature; terraces between features are free; gaps drape.
- The machinery exists and is fast: the taut-string profile solver
  (corridor_profile — 1-D cap-constrained construction), the
  cap-Lipschitz envelope (reach band — any selection INSIDE it is
  cap-lawful by construction), the flatness-certified lazy tier
  (certified shapes skip pair generation), value-preserving carry
  (proven, twinned), the stage architecture and single projection.
- The iterative solve's cost is its objective, not its law: ~250 s at
  HECA balancing DEM fidelity nobody is owed.

## The model (mode `constructive`)

C1 RUNWAY SPINES FIRST: taut-string profile per runway under its
   longitudinal cap + crown (existing constants); ends/seams take
   their existing law ties. These values are immutable anchors.
C2 ONE PROPAGATION: multi-source cap-bounded envelope over the one
   published graph from all anchors (runway values, seam pins, hard
   ties). Every node takes the DETERMINISTIC SELECTION: the feasible
   interval's midpoint, followed by at most one smoothing pass that
   provably moves only WITHIN intervals (interval-constrained — still
   lawful by construction). An empty interval is a REPORTED
   feasibility finding (feasibility-is-guaranteed), never a clamp.
C3 PLANAR INTERIORS: large interior regions (apron panels, yards)
   fill with low-order surfaces within caps and weld to their rims;
   surfaces lawful by construction take the CERTIFIED tier — pair-law
   generation skipped for them (the existing lazy machinery, not a
   new gate).
C4 REQUIRED LAW OBJECTS unchanged: crowns (runways only), enclosed
   drainage spines, adjacent-ground slopes beside runways/taxiways,
   RSA/skirts, seam continuity — same emitters, values read from the
   constructed field.
C5 CONSUMERS unchanged: pads (emission-time relative), corridors
   (already taut-string), pockets (grade to rims), y-bake, censuses,
   sidecars — the field is the only thing that changed.

## Mode plumbing

One cfg key `solve_model` (global + per-tile, values `iterative` |
`constructive`), DEFAULT `iterative` until the owner rules after the
A/B. Engine reads it at solve dispatch; harness passes/records it in
frame.json and the artifact-ledger variant key (two models = two
artifacts, never served for each other); the Qt and Swift UIs expose
it as a simple selector (engine-owns-features law). Censuses and
sidecars identical in both modes.

## Acceptance

1. CENSUS: at the five battery airports the constructive patch fires
   no adjudicated family WORSE than the iterative model's current
   counts, aspiring to zero (by-construction shapes should approach
   it); every row attributed. Each mode is self-deterministic
   (build-twice byte-identical per mode); there is deliberately NO
   byte gate BETWEEN modes.
2. TIME: one exclusive `--runs 2` pair per mode at HECA + CYXY.
   Target HECA total < 60 s constructive. If missed but < 120 s,
   report the decomposition and continue — the owner judges value.
3. THE IN-SIM A/B (the owner's verdict, the round's real gate): same
   tiles built in both modes (HECA, OTHH, KCLT, VHHH), flown
   side-by-side; the owner picks the default (or keeps both modes —
   fast drafts vs final quality is a legitimate end state).
4. Guards/discipline as always: shared repo untouched, tests once
   through the ledger, twins (selection determinism, interval
   containment of the smoothing pass, certified-tier equivalence,
   mode isolation — flipping the key changes ONLY the solve),
   DEFERRED lines.

## Pre-delegated decisions

- Selection rule is FIXED (interval midpoint + one in-interval
  smooth); alternatives are measured only if acceptance 1 fails.
- Phase 4 (global slice, ~35 s) is IN SCOPE for coarsening only if
  the <60 s target demands it after the solve collapses; correctness
  identical.
- A required law object whose constructive value conflicts at a weld
  → weld-or-gap, precedence rules as today.
- Objects moving MORE to y-bake at relief airports under the flatter
  field is EXPECTED and lawful (HECA already ~all); quote the counts.
- STOPs: an empty feasibility interval at a real airport; any census
  family the constructor fires that the iterative model does not.

## Lanes

K1 (Fable-class, authorized): C1-C3 constructor + certification
wiring. K2 (Opus): mode plumbing (cfg/harness/ledger-variant/UI
selector), measurement support, tile builds for the A/B. Lead:
consolidated censuses, the exclusive timing pairs, and the A/B
handoff package for the owner.

## AMENDMENT 1 — THE LIVING BAND (owner correction, 2026-08-14; supersedes C1/C2's anchor model)

K1's attempt 2 (lane/k1construct) proved the selection/certification
tail and the mode gates, and FAILED census acceptance at HECA/CYXY by
over-anchoring: C1 froze whole runway profiles, and derived minters
(certified pins et al.) were admitted as hard without mutual
validation — 14,104 crossed intervals at HECA in one 19.846 m
pair-class. The owner's correction, now the model:

A1 TRUE ANCHORS ONLY: the CIFP runway thresholds and the tile seam
   boundaries. Nothing else is hard before the band exists. True
   anchors are physically real and mutually consistent by reality; a
   contradiction WITHIN this set is a data defect (CIFP vs seam) —
   reported, never absorbed.
A2 THE BAND RUNS FIRST AND LIVES: the one published graph computes
   the cap-Lipschitz band from the true anchors alone. Thereafter
   every value that wants to be fixed is minted IN PRIORITY ORDER,
   validated against the CURRENT band, and — when accepted — joins
   the anchor set and locally refines the band before the next mint.
   Consistency holds by induction; every interval is non-empty by
   construction. Order (stable canonical ids within each class):
     P0 true anchors → P1 runway interiors — 1-D taut strings
     threaded through the band tube (string_with_pegs; thresholds are
     the ONLY pegs; flex emerges where the band narrows, which is the
     flex law's own definition) → P2 seam/DEM ties, seats, EAT pins,
     corridor free ends → P3 certified region fits → P4 remainder.
A3 REFUSAL SEMANTICS (anchor-placement law, executable): a mint
   outside the current band is REFUSED and recorded with minter id,
   value, band [lo,hi], deficit, and the two bounding anchors — the
   refused feature falls back to its non-anchored path (seat →
   yield-hard, pad → y-bake, plane fit → smaller region). No law
   value is ever silently clamped. These named refusals ARE the
   anchor-defect findings the round has been missing.
A4 SOURCE TRACKING: the band propagation carries provenance — every
   node knows its floor-minter and ceiling-minter — so any residual
   finding names its pair. (This is also the instrument the iterative
   model's absorbed-contradiction attribution needs; it ships in both
   modes' shared band code.)
A5 SINGLE PASS: after minting, K1's landed selection stands (interval
   midpoint + one in-interval smooth). No yielding projections exist
   in this mode.

## Amended acceptance

Original acceptance 1-4 stands, plus: ZERO empty intervals at all
battery airports (by construction — any would-be contradiction
surfaces as an A3 named refusal instead); census parity-or-better at
HECA and CYXY specifically (K1's failure set); K1's gates stay green
(mode isolation byte-for-byte, per-mode determinism); the owner's
time bar — LESS THAN HALF the iterative exclusive wall at HECA
(sub-minute remains aspirational; K1's broken-anchor version already
measured 267-277 vs 581 direction, and this removes work).

## Deployment (confirmed)

PARALLEL PATH: solve_model default stays iterative; the constructive
mode is reachable via env/per-tile/global cfg and both app selectors
(merged K2 plumbing, one-reader precedence, ledger variant
separation). The A/B compares performance and output quality across
the same tiles in both modes; the owner's in-sim verdict picks the
default or keeps both.

## Implementation base (K1b — a bounded revision, not a rewrite)

Build on lane/k1construct: KEEP the mode dispatch (O4_Solve_Model),
selection, certification tier, twins, and gate infrastructure;
REPLACE the anchor assembly (demote all but A1) and the propagation
(living band, ordered minting, source tracking, A3 refusals). The
K1 arms' logs (worktree k1construct tmp/k1_*.log) and the recorded
empty-interval rows are the regression fixtures: HECA's 19.846 m
pair-class and CYXY's 0.195 m chain must become named A3 refusals.

## K1b IMPLEMENTATION RECORD (2026-08-15, Fable lead — owner ratification pending on the three starred items)

AMENDMENT 1 is implemented on lane/k1construct: ``one_solve.LivingBand``
(A2 band-first + incremental refinement + A4 floor/ceiling-minter
provenance, module-level in the shared band code),
``constructive.constructive_core`` rewritten to ordered minting
(P0 true anchors = ``cifp_pins`` verbatim + tile-seam pins; P1 runway
interiors via ``corridor_profile.solve_run_profile`` — thresholds the
only pegs, a crossing runway's pinch arrives through the band; P2 the
demoted base_hard populations; P3 certified fits per node; P4
remainder), A3 named refusals with fallbacks
(``layout._constructive_refusals``), A1 data-defect channel
(``_constructive_p0_defects``).  Zero empty intervals at HECA and CYXY
by construction (the K1 fixtures now surface as named refusals:
HECA's 19.846 m pair-class as ``floor by rwy:05C/23C / ceiling by
cifp:05L/23R`` rows, CYXY's 0.195 m chain as ``cert:264 vs
cifp:02/20`` rows).

Deviations taken under the pre-delegated clause ("alternatives are
measured only if acceptance 1 fails" — the as-written selection failed
CYXY census parity), each measured at CYXY, census family tables in
the session record:

*  ★ SELECTION = THE CARRIER, not the bare interval midpoint: the DEM
   seed field regularized to cap-Lipschitz over the law adjacency
   (midpoint of its lower/upper Lipschitz regularizations), clamped
   into the living band per node.  Median of three cap-Lipschitz
   fields — pair-lawfulness by construction is UNCHANGED.  Midpoint
   arm remains measurable (``O4_CONSTRUCTIVE_SELECT=mid``).  Measured:
   every worst-row magnitude improved, tears/steps/arc families went
   to zero, groundside within-shape −16.
*  ★ SMOOTHING = up to 8 in-interval sweeps (fixed count, zero-move
   early exit; ``O4_CONSTRUCTIVE_SWEEPS``), not exactly one.  The
   per-sweep containment/lawfulness invariant is the twin's own proof;
   iteration converges toward the in-band harmonic.  Measured: CYXY
   adjudicated 374 → 361, within_shape reached iterative parity.
*  ★ STAGE-B RECEIVER VALUATION: before the groundside law passes, the
   receivers take a band-from-the-mouths + carrier valuation (the
   population the iterative model's partitioned projection values;
   holding it at raw seed measured +22 within_shape::service_junction
   at CYXY).  Airside-is-king preserved: mouths are read-only
   authority.
*  C4 consequence (not a deviation): the CONSTRUCTED profile is
   persisted onto ``layout._runway_redistributed_profiles[ref]``
   (fractions/elevs/anchored; ``cifp_pins``/``seam_t``/law fields
   verbatim), so the crown-spine ridge, tile-cut rewrite and seam
   clamp floor read the same surface the ring emits.  Measured:
   HECA-class runway_crown shortfall at CYXY 113 → 6 (better than
   iterative's 10).
*  A per-surface planar seed fill (C3 spelled as pre-regularization
   median) was built and MEASURED WORSE (CYXY 380 vs 373) — removed;
   the certified tier remains the planar-interior mechanism.

Census standing at CYXY (adjudicated, constructive vs iterative
3-family view): total 361 vs 313; within_shape 71 vs 71 (parity, worst
2.25 vs 4.09), transverse 275 vs 227 (worst equal at 1.637, the
excess spread across corpus-shared apron/service classes whose spans
the visibility-windowed graph does not bind), runway_crown/raoa/
strip_longitudinal/strip_arc/tears/steps all at-or-better.  Residual
family-parity gap is transverse-shaped and lives in spans no
projection binds in either mode; the owner's in-sim A/B remains the
round's real gate.
