# S1b — first-class chord boundaries in phase A (Opus-executable)

Fable, 2026-07-31, written under the owner's tonight deadline.
Parent: `s1-taut-chord-constructor-spec.md` (fourteen rulings blocks;
"the S1 spec" below).  S1's measurement has landed (`f1b13c3`:
chord model, defects 949 → 0, 113 green, gate-off proved, value
path 73.5 ms).  The gate-ON HECA arm running tonight is the **α
baseline arm** for everything below.

## §0 THE SCOPE LINE (read this before anything)

**THE PRICING RULING: the chord model collapses S1b-core to THREE
SEAM-LEVEL EDITS.**  S1b was ordained against the tube-and-funnel
constructor, where "first-class inside phase A" meant moving a
solver.  A string is now two numbers and a linear evaluation, and
every input it needs (carried substrate, grade graph, decoration,
`node_band`) exists BEFORE the harmonic runs.  So:

* **IN tonight (S1b-core):** (1) compute chord targets
  PRE-harmonic, inside `_solve_spine_profile`, by moving the CALL
  SITE of the existing landed computation — the computation itself
  does not change; (2) supply those targets as DIRICHLET (fixed)
  values to the harmonic through the solver's EXISTING fixed-value
  mechanism, so the harmonic solves only the RESIDUAL (unstrung
  interiors, gaps, plural-claim vertices) with string values as
  boundaries; (3) retire the post-phase-A overwrite application
  and the phase-A-internal taut pass on assembled strings, by the
  measured protocol in §3.
* **OUT (deferred, explicitly NOT tonight):** the DRAW-TOWARD
  re-founding — fabric reference as grade-law projection out from
  the string web (1.5 % along-route / 1 % lateral), R demoted to
  an instance of that projection, layer 6 shrunk to off-web
  fallback.  That is a reference-system redesign, not an evening
  edit.  Service 4b untouched, per ordination.  R2 is BLOCKED
  (§6).

Rationale carried from the ordination: the harmonic owns 67.1 %
of the corridor's departure from DEM and has no altitude
preference — it interpolates toward the network's descent, which
lifts the seam and sags the chord: one mechanism, two signs.
With string boundaries it finally has one.

## §1 The three edits, at seam level (never by line number)

1. **Target computation moves ahead of the harmonic.**  Locate
   the harmonic min-curvature solve inside `_solve_spine_profile`
   by its own comments.  Immediately BEFORE it, under the S1 gate,
   compute the per-vertex chord targets exactly as the landed
   value path does (endpoint band-centre reads per S1 Rulings
   43/49 — direct / interpolated / clamped — and linear
   evaluation at decorated exclusive-claim vertices).  Function-
   local import; gate OFF ⇒ no import, no computation, phase A
   byte-identical (S1 §5 law).
2. **Pins ride the existing fixed-value mechanism.**  The strung
   exclusive-claim vertices join the solve's existing fixed-value
   structure with their chord values — the same mechanism that
   already holds hard/anchor vertices fixed.  NO new solver
   machinery, no new constraint system.  Precedence law
   (unchanged from S1 §4): hard/anchor vertices are NEVER pinned
   by strings — where a strung vertex is also hard, hard wins and
   the conflict is counted; plural-claim vertices are NEVER
   pinned (S1 Ruling 39(ii)/42 — the solve joins the approaching
   chords); the anchor set consulted is the PRE-FREEZE set (the
   §4 `base_hard` silent-no-op hazard applies at this call site
   exactly as at the old one).
   **THE LAW-FILTERED GRIP (ruled 2026-07-31 night, S1 Ruling 52
   — resolves the pins-vs-Ruling-19 conflict; conditions 1 and 2
   both confirmed as measured).**  Pins DO join `anchors`
   (forced — otherwise fairing and the exact cap projection move
   them and G2 fails by construction).  But the pin set is
   FILTERED BEFORE JOINING: **no pair may be left both-pinned
   where the chord grade between the two pinned values exceeds
   that pair's cap budget** (strict >, at the §2-step-4 audit
   epsilon 1e-9 — no new constant).  A both-pinned over-cap pair
   is a string FORCING an unlawful surface — the exact class the
   owner outlawed and Ruling 19 gates at zero; the measured 76
   of 3,223 pairs (excess max 0.584 m) are that class
   materialized, latent under α and surfaced by S1b.  THE LAW:
   **the chord is never bent by law; the GRIP is.**  The chord
   (the preference, and gate (A)'s object) is never modified,
   never clipped to cap; where holding the surface to it would
   break grade law, the string RELEASES ITS GRIP and the cap
   machinery owns the span — the owner's sentence ("grade law
   overrules the string when needed") implemented at the
   transport layer, at the exact stations where "needed" is
   true.  Scope: the filter applies only to pairs with at least
   one STRING PIN member and releases ONLY string pins — a law
   anchor (`base_hard`) is never released, and a
   both-LAW-anchor over-cap pair is the projection's
   pre-existing genuine-step contract, not ours.  Release rule:
   the MINIMAL deterministic release such that no both-pinned
   over-cap pair remains; endpoint-protective (release the
   member farther from its string's nearer endpoint — gate (A)
   reads endpoints; a run of consecutive over-cap pairs
   releases its interior pins first); ties by stable node id;
   the exact algorithm is discretion WITHIN minimality,
   determinism (a test pins same-input-same-output), endpoint
   protection, and never-release-law.  Every release is
   WITNESSED — the GRIP-YIELD WITNESS: pair, cap, chord grade,
   excess, released end, rule fired.  Ruling 44/47(B)'s
   delivery gate then reads released spans as cap-contact
   departures WITH their author named — the loop closes.
   Consistency, recorded: S1 Ruling 43(f) is AMENDED, not
   broken — chord grade vs cap remains telemetry for the CHORD;
   it is no longer only telemetry for the GRIP.  S1 Ruling 21
   is untouched — it governed strings gripping EACH OTHER; a
   pin is a string gripping its OWN pavement, and the
   law-filter is the invariant applied to that grip.  Ruling 19
   STANDS at zero BY CONSTRUCTION: no both-pinned over-cap pair
   can exist, so phase A cannot emit a string-forced over-cap
   segment, and the post-phase-A freeze (`base_hard[i] = True`)
   freezes only lawful grips.  Disposition (4) — let the
   projection move pins — is REJECTED: it launders the yield
   through the solver, destroys pin auditability, and makes the
   solver the author of string values.  PRE-REGISTERED:
   released-pin population ≈ the 76-pair class (excess median
   0.000 / p90 0.026 / max 0.584 m); chord 1 unaffected
   (near-flat chord); a materially larger release population is
   a FINDING to attribute before trusting G1.
3. **The α overwrite retires; the internal taut pass on
   assembled strings retires.**  Per §3 below — measured, in the
   same commit, never silent.

## §2 The law

* ONE application: string values enter phase A once, as
  boundaries.  Nothing overwrites after phase A returns.  The
  single-pass violation α acknowledged (harmonic computes
  interiors the hook discards) is thereby CLOSED, and the
  harmonic's interiors become real outputs everywhere.
* Dirichlet means DIRICHLET: the solver may not move a pinned
  vertex.  G2 asserts it exactly.
* The residual domain is the harmonic's whole remaining job
  [AMENDED by Ruling 53: the harmonic's AND the surviving
  residual spine smoother's — see §3; the over-claim is
  corrected]:
  unstrung vertices, gaps between strings, plural-claim junction
  vertices.  No blending back onto pinned vertices from any
  later phase-A stage (the spine-yield/quarantine-blend class —
  see §5(i)).
* Everything the S1 spec froze stays frozen: the chord model
  (Rulings 42-49), the invariant gate (Ruling 19), exclusions,
  the clip, tenure, carriage, denominator hygiene.

## §3 Retirements (measured, never silent — S1 standing rule)

* **The post-phase-A overwrite application.**  Retired in the
  S1b commit.  Measure, do not trust: at every pinned vertex the
  emitted value must equal the chord evaluation exactly (this is
  G2); the retirement changes values ONLY at unstrung vertices —
  which is the intended effect (the harmonic now respects
  boundaries there), read by G1.
* **The phase-A-internal taut pass on assembled strings** (the
  §1b-named deletion; the spine-yield projection site the S1
  record attributes the quarantine blend to).  MASK FIRST, then
  delete: run the offline replay with the pass masked and pins
  active; if masking changes ANY value outside assembled-string
  vertices, STOP and report the consumers (see §5(i)) — do not
  delete blind.  Mask-clean ⇒ delete in the same commit, with
  its tests retired or converted.
  **[THE MASK FIRED — RULED same night (S1 Ruling 53):
  KEEP-AND-RESCOPE, not delete.**  Measured, one variable, pins
  active, both arms sharing `graph=None` (labelled): pinned
  0 moved of 3,429; other spine 567 moved of 3,697, max
  0.283 m; off-spine 0 of 123,929.  THE FINDING: the pass
  strings ALL `_build_spine_corridors` corridors, not only S1's
  assembled strings — on strung ground it is now PROVABLY INERT
  (the pins hold; it respects `anchors` by construction), and
  its entire remaining effect is unstrung spine: sub-100 m
  runs, geometry-only strings, service-adjacent spine,
  plural-claim junctions.  It has stopped being a competing
  string constructor and become the RESIDUAL SPINE SMOOTHER on
  ground S1 does not claim.  THE ORDINATION IS SATISFIED IN
  SUBSTANCE: "the internal taut pass on assembled strings is
  deleted there" — on assembled strings it is structurally
  dead; what survives is a different-domain mechanism sharing
  the code.  Deleting tonight would hand 567 vertices to
  harmonic+fairing alone with an UNMEASURED 0.28 m-class
  surface change — deleting through a fired STOP, and retiring
  a mechanism because its NAME matches what we replaced when
  its DOMAIN no longer overlaps (the inverse of the lesson that
  produced the chord model).  GUARDS, so it cannot rot back
  into a constructor: (1) inertness-on-strung-ground is G2's
  standing assertion (pins exact through the whole chain, this
  pass included) — the guard is already a gate; (2) its DOMAIN
  is this spec text: unstrung spine only, with fairing-class
  authority, never string authority — the spec name is "the
  residual spine smoother (formerly the internal taut pass)";
  renaming code is a later hygiene commit, never tonight;
  (3) the mask table (567 / 0.283 m) is the recorded
  residual-domain footprint — the BASELINE for any future
  retirement measurement; (4) whether the residual domain
  should eventually be the harmonic's alone is a MEASURED
  question deferred past the flip: an A/B on residual-domain
  quality (law-true counts + departure stats on unstrung
  spine), pre-registered before it runs — not tonight, and
  only sooner if the suite read shows unstrung-spine
  regressions vs α, in which case the pass's changed inputs
  (it now sees pinned boundaries) are the first suspect.]**
* NOT retired tonight: layer 6, R's independence, any reference
  machinery (deferred with DRAW-TOWARD).

## §4 Gates, chord terms, pre-registered against the α baseline

The α baseline is TONIGHT'S gate-ON HECA arm at `f1b13c3` (its
W-CHORD table, defect counts, per-phase times).  S1b's
verification FOLDS INTO the owner's already-planned spends — the
one tile build and the one suite read.  **S1b adds ZERO builds.**

* **G1 (mechanism):** the harmonic-owned departure share (67.1 %
  baseline class) COLLAPSES on strung corridors; both signs of
  the one mechanism move together — seam lift down, chord sag
  down.  Directions pre-registered, magnitudes NOT promised; a
  material move against direction is a FINDING to attribute,
  never to accept.  W-CHORD1(B) (binding-law-witnessed delivery)
  improves or holds vs α; W-CHORD2 moves toward 103-106 or
  holds.
* **G2 (identity, amended by the law-filtered grip):** max
  |emitted − chord| at FILTERED-set pinned vertices = 0 (float
  eps) — any nonzero is a solver-moved-a-pin defect, STOP.  PLUS
  the completeness assertion: NO both-pinned over-cap pair
  exists after the filter (cheap scan, same epsilon).  The
  grip-yield witness count reconciles with the pre-registered
  76-pair class.  [PRODUCTION READING: offline-exact did NOT
  carry — matched-pin median 0.2342 m.  See S1 Ruling 55: the
  JOIN is suspect first (2,210 of 3,790 pins unmatched at the
  1 m proximity join — the wrong-object register); G2 re-reads
  on the canonical-identity join, and the neighbour-drag law
  (no stage manufactures an over-cap pair against a hard node)
  is the ruled fix shape behind it.]
* **G3 (invariants carry):** string-authored defect classes stay
  0 (the 949 → 0 dissolution must survive the reordering);
  `no_datum` stays dissolved; Ruling 19's slice stays 0.
* **G4 (inertness):** gate OFF ⇒ byte-identical phase A (the
  copied-tree three-way on SPLP+CYXY per S1 §5 — the cheap
  identity builds, not a HECA spend).
* **G5 (budget):** value path stays ≤ the landed 73.5 ms class;
  the harmonic on residual-only is cheaper-or-equal; per-phase
  times from the standing build-times ledger, cold-cache
  discipline per the measurement-trap register.
* **Carried-open, pre-registered so S1b is not blamed for it:**
  the 23C endpoint sits +0.61 m vs CIFP (gate (A) ε ≤ 0.50) —
  an OPEN endpoint-provenance number (P3c-relocated, S1 Rulings
  47/48).  S1b does not touch endpoint reads and must not move
  this number; if it moves, that is a G2-class finding.

## §5 EXPECT DIVERGENCE (S1 §10 style; the surgery site is
`_solve_spine_profile`'s interior)

(i) **Consumers between the two sites.**  Anything reading elev
between the harmonic and the old hook point (couple_adj,
spine_floor, §7 z_ref snapshots, the quarantine blend) will now
see STRING values where it saw harmonic values.  ENUMERATE these
consumers FIRST (grep the interior, list them in the commit
message).  Each is either (a) intended to see string values —
that is the point of S1b — or (b) a law input that must see
pre-string state: any (b) is a STOP, report with the consumer
named.  Do not reorder around it silently.
(ii) **Plural-claim junctions:** expected small moves (the
harmonic now joins chords under grade law there).  Report the
distribution; do not clamp it.
(iii) **Pin-set conflicts:** a strung vertex that is also hard —
hard wins, count reported.  If the count is materially nonzero,
report before trusting G1's attribution.
(iv) **Solver behaviour:** many interior pins may change
iteration counts/conditioning.  Record; never tune solver
parameters in this commit.
(v) **If the solver has NO general fixed-value mechanism** (only
special-cased anchors): STOP and report the actual solver
contract.  Building a new constraint system is not tonight's
work.
(vi) **If gate-off byte-identity cannot be held** at the new
call site (import leaks, side effects): STOP — the import-
neutral law outranks the deadline.
(vii) **FIRED AND RULED (post-landing, same night): the
`yield_hard` enumeration.**  Downstream yield stages rebuild
their hard set from `truth_hard` and never inherit the phase-A
spine freeze, so fp#8 and the finals could move pinned vertices
— measured at chord 1's dip as 4.87 m of below-ceiling drag
with no law author.  RULED at S1 Ruling 54: defect for PINNED
vertices, design for the rest; the fix is `yield_hard` gaining
the Ruling-52 KEPT PIN SET — never the wholesale spine freeze.
Diagnostic arm gated, pre-registered there.

## §6 The R2 dependency — RULED: BLOCKED tonight, twice over

R2's spec founds the tube on R1 as its centre.  (1) R1's
precondition is unmet: `O4_REFERENCE_FIELD` default "0", CP2
gates unread.  (2) S1 just changed R1's OWN layer 4 (spine layer
= chord, not rod-implied string), so R1's gates must be RE-READ
against the chord before anything is enforced against R1 —
re-reading runs OFFLINE on tonight's build artifacts, no extra
spend, but not before morning.  (3) "Found the tube on chord
targets directly" is not a shortcut — partial-coverage chords as
a tube centre IS the DRAW-TOWARD re-founding (projection out
from the web), i.e. the deferred (c) design, not an evening
edit.  The coordinator's read to the owner is CONFIRMED.
Sequence: S1b-core tonight → R1 layer-4 re-read on tonight's
artifacts (offline) → R1 CP2 → R2.

## §7 FROZEN / DISCRETION

**FROZEN:** the three-edit scope (anything more is not S1b-core
and waits); the pin precedence law (hard > string; plural-claim
never pinned; pre-freeze anchor set); one-application law; the
gates G1-G5 and the α baseline's identity; the retirement
protocol (mask before delete); zero new builds; the OUT list.
**DISCRETION:** exact code placement within the named seams;
test parametrisation; how the fixed-value mechanism is invoked
(within §5(v)); report formatting.
