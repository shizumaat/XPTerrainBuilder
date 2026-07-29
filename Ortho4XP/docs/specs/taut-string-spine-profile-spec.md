# Taut-String Spine Profile — spec

Status: **APPROVED for implementation** (owner ruling 2026-07-28, this
session).  Supersedes the min-curvature harmonic as the taxi-spine
longitudinal profile objective.  Gate `O4_SPINE_TAUT_STRING`, default ON;
OFF restores the current harmonic path byte-identically.

## 1. Problem (measured, HECA 2026-07-28)

The corridor between (30.1105599, 31.4087103) and (30.1137307, 31.4129164)
emits a ~3.6 m V-dip (bottom 103.14 m) although:

* the reach-band ceiling along the corridor is 109.4–110.5 m mid-segment
  (single witness anchor: the 05L NE join, node value 64.42 m) — the solved
  profile sits **6.3 m below the lawful ceiling** and 5.5 m below the DEM;
* the straight chord between the corridor's end values (107.85 → 105.75)
  fits under the ceiling at every node — the dip is **not law-forced**;
* the dip walls run −1.9 % / +3.2 % on 1.5 %-cap edges.

Stage attribution (instrumented build): the phase-A harmonic drags the
corridor 1.5–4 m below DEM (its min-curvature target interpolates toward
the network-wide 41 m descent to 05L; spine nodes have no altitude
preference); the phase-A cap projection and later joint projections drag
it further in waves (POCS budgets are two-sided, so "uniformly too low"
is a valid fixpoint); interior hard anchors (two `seat_on_spine` pins at
106.48 / 106.08 on this corridor) then turn the sag into a V.  Nothing in
the pipeline ever lifts a spine back toward its lawful maximum.

Root cause class: **objectives with no altitude preference on real-relief
airports**.  The 2026-07-27 verdict "remainder = 05L reach ceiling,
lawful" is overturned by measurement.

## 2. Owner model (ruling 2026-07-28)

> Closest-to-DEM would be fine if DEM were always accurate, but it's not.
> We also need to minimize elevation rising more than needed, just as much
> as sagging.  Like the runway: draw a straight line between the two
> farthest points we can — taxiways generally have long straight sections —
> and stay as close to that as we can within our feasible band.

Formalization: per spine **corridor**, the profile is the **taut string**
(shortest path in (s, z)) through the feasible tube
`[floor(s), ceiling(s)]`, pinned at genuinely-pinned points.  Properties:

* symmetric — no up/down preference; deviates from the chord only where a
  wall or peg forces it, and every bend has a witnessed constraint;
* DEM-robust — DEM steers nothing directly; it enters only through
  deliberate pins (runway joins, seam pins, seats) and the band cones;
* cap-safe — both walls are cap-Lipschitz in the route metric (cones of
  slope ≤ cap from anchors; `building_spine_floor` is cap-Lipschitz by
  construction), so string tangents obey the grade cap wherever the tube
  is feasible and the tangent has a wall contact at both ends; peg-to-peg
  chords between band-feasible values are cap-bounded by the same wall
  Lipschitz argument.  Off-net nodes (band `None`) have unbounded walls;
  the existing exact cap projection remains as the safety net (§5 step 5);
* degrades correctly — where the network genuinely runs at cap (HECA NE
  descent: 2758 m route for a 41.33 m drop = exactly 1.50 % average) the
  tube pinches and the string lies ON the ceiling (max grade because it is
  the only compliant profile); where there is slack, the string is the
  chord.

The K-factor fairing (`_fair_spine_chains`) is retained and becomes what
it was meant to be: vertical-curve rounding at the string's few bend
points, not a rescue pass over a wiggly field.

## 3. Scope

* IN: taxi/service spine corridor interiors + free corridor endpoints
  (junction settle, §6).  Phase-A only (`_solve_spine_profile`), plus the
  hold-hard invariant (§7) on later projections.
* OUT (unchanged): runway profiles, apron/junction body fill (phase B),
  building seats, seam pins, broken-node quarantine + blend, gap-fill
  spines, adjacent-ground machinery, crown machinery (strings solve in the
  uncrowned space like today's solve).
* `SPINE_CHORD_MAX_SAG_M` is subsumed; it stays default-OFF and its
  removal is deferred until after the in-sim review.

## 4. Core algorithm (new module, frozen API)

New file `src/auto_patch/elevation_per_surface/route_profile/taut_string.py`
(pure stdlib + math, no auto_patch imports, deterministic):

```python
def taut_string(stations, floor, ceiling, z_start, z_end):
    """Exact taut string through the tube [floor[i], ceiling[i]] at
    strictly-increasing stations, from (stations[0], z_start) to
    (stations[-1], z_end).  Greedy funnel algorithm, O(k).  Walls may be
    ±inf (unbounded).  Preconditions (asserted): equal lengths >= 2,
    floor[i] <= ceiling[i], endpoint values inside their walls (clamped
    within 1e-9 tolerance).  Returns list[float] (len k)."""

def string_with_pegs(stations, floor, ceiling, pegs):
    """Taut string with interior pegs.  ``pegs``: {index: value}; the
    corridor is split at peg indices and each span strung independently
    (a peg is an exact pass-through point, clamped into its own walls).
    Endpoint handling: if index 0 (resp. last) is not a peg, the free end
    CONTINUES THE TANGENT of the adjacent strung span, clamped into the
    walls (fewest-grade-changes rule).  Fewer than 2 pegs total: returns
    None (caller falls back to the current behavior)."""
```

Peg values that violate their own walls are clamped into the walls for
the string (the raw peg value itself is never changed — pegs are hard
nodes owned elsewhere; the mismatch is the existing both-hard /
quarantine class and stays reported by the cap projection).

## 5. Phase-A integration (`_solve_spine_profile`, route_profile/solve.py)

Order of operations with the gate ON:

1. warm start + harmonic Gauss-Seidel — **unchanged** (now serves as the
   junction-value seed and the fallback for unstrung nodes);
2. **NEW — taut-string network pass** (§6): overwrite corridor interiors
   and settle free corridor endpoints;
3. `_fair_spine_chains` K-factor fairing — unchanged (rounds the string's
   bends; band clamps and anchors still hold);
4. freeze (`base_hard`) — unchanged;
5. exact cap projection on spine edges — unchanged (safety net).

Gate OFF ⇒ step 2 skipped ⇒ byte-identical to today.

## 6. Corridors and the network settle

**Corridor extraction.**  Extract the chain-building + through-weld-splice
logic of `_fair_spine_chains` (maximal degree-2 runs, spliced through
welds within `SPINE_FAIR_WELD_MAX_DEVIATION_DEG` of straight-on) into a
shared helper so fairing and stringing operate on the SAME corridors.
The extraction must be behavior-preserving for fairing (same chains, same
order — the existing fairing tests are the guard).

**Per-corridor data.**  Stations = cumulative chord length.  Walls per
node: `node_band` (floor, ceiling), raised by `spine_floor`
(building-frontage floor); band `None` ⇒ ±inf; band-inverted nodes
(floor > ceiling) split the corridor (they keep their existing value —
quarantine territory).  Pegs = hard nodes on the corridor (`base_hard`
at phase-A entry: runway joins, seam pins, `seat_on_spine`).

**Free endpoints.**  A corridor endpoint that is not hard takes its
post-harmonic value clamped into its walls as the provisional value for
pass 1.

**Deterministic network settle (2 passes).**
Pass 1: process corridors longest-first (tie: smallest first node index).
String each with `string_with_pegs`; after a corridor is strung, its node
values are updated in `elev`, and any node shared with a later corridor
(crossing welds) acts as a peg there ("the crossing taxiway meets the
through-taxiway's surface" — matches the owner's model: longest straight
line first).
Pass 2: re-string every corridor once more with endpoint/crossing values
as settled by pass 1 (Jacobi over the pass-1 state, same order).  Two
passes, fixed — no convergence loop.

**Fallbacks.**  Corridor with < 2 pegs/settled endpoints (isolated loops,
two-free-end fragments): keep harmonic values.  Any exception inside the
string pass must propagate loudly (never silently skip constraints).

**CROSS-CORRIDOR LAW COUPLING (amendment 2026-07-28, measured blocker).**
Two corridors crossing one junction WITHOUT a shared spine node string to
mutually-inconsistent values (KCLT: 0.2–0.4 m disagreements on 3–8 m
within-junction pairs → 1373 minted law-true violations once held; both
hold-boundary pre-legalise variants failed — the joint-graph one re-drags
the corridor through body edges and costs 2.6 s, the strung-pair-scoped
one misses the offenders and mints 4 % longitudinal steps instead).  The
fix belongs AT STRING TIME: while settling, every already-strung (or
hard) node j imposes a MOVING WALL on a later-strung node i wherever a
unified-graph law edge (i, j, budget) exists —
``ceiling_i ← min(ceiling_i, z_j + budget)``, ``floor_i ← max(floor_i,
z_j − budget)`` — so crossing corridors are cap-consistent BY
CONSTRUCTION and the holds have nothing to mint.  The coupling adjacency
comes from ``G.edges`` (the validator's own pair set, materialized — no
lazy machinery), filtered once to pairs with both endpoints on spine
corridors; pass 2 re-strings with the full mutual walls.  Applies at
BOTH string sites (phase A and the pre-yield re-string).

## 7. Hold-hard invariant (later projections) — AMENDED per audit 2026-07-28

Audit (scratchpad `taut_string_audit.md`, two reproducible instrumented
HECA builds) attributed the drag: fp#2–#5 are clean; the movers are the
yield projections at solve.py:988/990 (`yield_hard` snapshotted BEFORE
the freeze; corridor −2.7 m), the movable-pads/free-seats yield at
solve.py:1095 (**the dominant wave, corridor −7.9 m, seat pin freed
106.48 → 98.60 — it runs AFTER the `O4_DUMP_SOLVE_STATE` dump, so §1
understates the emitted dip by ~5 m**), `_fair_ring_edges` (anchors =
`yield_hard`; its sibling `_fair_gap_spine_chains` uses `base_hard` and
moves zero), and `final_grade_projection` (fp#10/#11, REBUILT node space,
no spine concept).  The yield passes free the spine for documented
feasibility reasons (chains freeze ~2.6 m apart; the polytope is feasible
only with movable pads/seats) — re-hardening them would re-mint those
residuals.  Therefore:

* **RE-STRING, don't re-harden**: after the last solve-space yield pass
  (after the `_fair_gap_spine_chains` call, before crown/writeback),
  re-run the corridor string with pegs = still-hard nodes' + settled
  crossing values, then re-legalise with the spine-edges-only projection
  (the `_solve_spine_profile` tail pattern), then re-yield the body once
  so it grades to the lifted spine;
* **FINAL-PROJECTION HOLD** (sub-gate `O4_SPINE_TAUT_STRING_FINAL_HOLD`,
  default ON): export the re-strung spine as canonical-key membership on
  the layout; `final_grade_projection` maps the keys into its rebuilt
  space and adds them to its hard set.  A/B the residual-edge impact —
  this is the acknowledged open risk (the final projection already exits
  with ~24.5 k over-cap edges at HECA; holding ~7 k more hard nodes may
  shift counts);
* new `O4_STEP_DEBUG` line after the re-string:
  `[taut-string] corridors=N strung=M resag worst=X.XXm`
  (worst interior deviation of the live profile from the re-derived
  string) — the invariant's cheap witness.

## 8. Acceptance criteria

1. Unit: `tests/test_taut_string.py` green (chord-in-tube exact; ceiling
   pinch bends at witnessed contact; floor pinch symmetric; ±inf walls;
   pegs pass-through; free-end tangent continuation; single-span and
   dense-station corridors; determinism: same input → same output;
   grades ≤ wall Lipschitz constant on cap-Lipschitz synthetic tubes).
2. HECA corridor regression (`tests/test_spine_taut_string_heca.py`):
   on the diagnosed corridor, no interior node more than **0.5 m below**
   the chord between the corridor end values, and no over-cap edge
   within the corridor (NE-tail at-cap descent excluded — it is lawful
   by construction).  MUST measure the **EMITTED** patch (post
   `final_grade_projection`, via `layout.to_osm` output or the layout's
   emitted per-vertex altitudes) — the audit proved the
   `O4_DUMP_SOLVE_STATE` dump precedes the dominant drag wave, so a
   dump-based test would pass while the emitted surface still dips.
3. Suite parity: full pytest suite gate-ON vs gate-OFF — no NEW failures
   (known reds per STATUS.md stay).
4. `tools/check_grade.py` law-true counts on HECA/SPJC/CYXY/KCLT not
   worse than gate-OFF.
5. Build time: expected cost ≪ 0.6 s (O(spine nodes) × 2 passes; ~7 k
   nodes at HECA).  Verify with `tools/check_build_time.py`; any measured
   cost ≥ 0.6 s triggers the hard-law optimization review before landing.

## 9. Task split (agent plan)

* **A (core)**: `taut_string.py` + `tests/test_taut_string.py` against
  the frozen §4 API.  Pure, no repo deps.
* **C (audit)**: attribute the late drag waves (fp#6/#7) — every
  projection call site during a HECA build: caller line, hard-set
  coverage of frozen spine, whether corridor nodes moved.  Read-only;
  temp instrumentation via external wrappers only.
* **B (integration)**: §5 + §6 in `route_profile/solve.py` (corridor
  extraction shared with fairing, network settle, gate) + §7 fixes per
  C's findings.
* **D (regression)**: §8.2 test.
* Lead reviews all diffs, runs §8.3–8.5.

## 10. STRING-AS-LAW: the interval rod (owner ruling 2026-07-28 late
session — SUPERSEDES §7's hold mechanisms)

The 2026-07-28 implementation round proved the hold model wrong in
practice: value-holds fight the yield passes, mint both-hard violations
wherever the law graph lacks a body↔spine pair (owner in-sim: "taxiway
edges left behind"), and every scoped repair tried is falsified (§7
notes, STATUS round 7).  Owner ruling: **encode the taut string into the
grade law itself, so the solver follows it at solve time.**

### 10.1 Model

After phase A derives and fairs each corridor's string (coupling per §6
included), emit ONE SIGNED INTERVAL EDGE per consecutive spine pair:

    z_i − z_j ∈ [Δstring_ij − ε, Δstring_ij + ε]

using the existing 4-tuple interval-edge form (`one_solve` Stage B0/B3
machinery, already production for adjacent-ground).  Registered in
`shape_constraints` as a dedicated entry, these are ordinary law edges:
every subsequent projection — fp#2..fp#9, ring fairing re-checks, the
FINAL projection — maintains the string's SHAPE automatically.

* Intervals pin DIFFERENCES, not values: a corridor is a quasi-rigid ROD
  that translates vertically as a unit to meet seats, seams, runways and
  the body web.  The yields keep their feasibility freedom (their reason
  to exist) but cannot manufacture dips.
* Bodies follow wherever a body↔spine law edge exists, to wherever the
  rod SETTLED — no stale copies, no ordering hazard.
* DELETED with this model: the pre-yield re-string block, the
  `yield_hard |=` hold, the final-projection hold + canonical-key
  export-for-hold (the key carry is reused to project the INTERVAL EDGES
  into the final projection's rebuilt node space — both endpoints must
  resolve, else the pair is dropped and counted).
* ε: default 0.02 m/edge (quantization-scale; accumulated shape drift
  over a 30-edge corridor ≤ ~0.6 m); tunable `O4_SPINE_ROD_EPSILON_M`.
  Respect `_QUANT_MARGIN_FLOOR_M` semantics (`_margined_interval`).
* Corridor splits (band-inverted / broken nodes) carry over: no interval
  edge across a split.  Genuinely infeasible tubes still ride the
  ceiling at cap (the string is derived there; a cap-grade interval is
  consistent with the symmetric cap edge).
* Phase-A freeze for the phase-B body fill stays as today; the rod
  governs everything AFTER phase B.

### 10.2 Legacy rect machinery removal (same session)

Owner: "we have no rects any more, and no end caps."  Verified: the
emitted HECA patch has ZERO rect roles (global slice — "rects/
junction-emit/spine bypassed").  `_flatten_rect_ends` and
`_restamp_caps_unified` are stale no-op scaffolding that misled this
very session.  Task: verify zero rect-role output across ALL fixtures
(SPJC/SPLP/CYXY/HECA/KCLT/MMOX role census), then remove the two
functions, their call sites, and any rect-plane coupling machinery that
becomes dead — suite must stay green; any fixture that DOES still emit
rect roles halts the removal and gets reported instead.

### 10.3 Acceptance

1. Corridor regression (§8.2) still ≤ 0.5 m sag / no over-cap.
2. Printed within-shape law-true counts, gate ON, not worse than
   gate-OFF baselines on all five fixtures (KCLT 6, SPJC 26, HECA 1864,
   CYXY 106, SPLP 65+0) — the mint class must DIE with the holds.
3. Owner's in-sim step site (30.11211,31.40562 / 30.11195,31.40578)
   stays lawful; no new seam classes (the rod translates, never steps).
4. Cost: rod derivation is the existing string pass; interval
   enforcement rides existing projection machinery.  Total attributable
   < 0.6 s (hard law), measured.
5. Gate OFF byte-identical; rect removal verified by role census +
   full-suite parity.
