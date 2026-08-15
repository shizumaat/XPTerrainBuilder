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
