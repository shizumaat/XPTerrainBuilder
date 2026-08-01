# Route-metric envelope: feasibility travels taxi routes, never apron chords

Fable spec, 2026-08-01. Implements the owner's directive verbatim: "we
need to fix the route graph, it has to be via actual routes, not cutting
across the edge of aprons." Sized by the megaanchor counterfactual
(scratchpad `megaanchor/`, static re-scoring — read it before
implementing; its table is the pre-registration source). Line numbers
against `fa5aad0`. Owner rulings in force: reach follows taxi
centerlines (2026-07-30, escalated 2026-08-01); zero breaks in paved
areas is the end state; all counts full-census.

**Sequencing:** implement AFTER the break-blend continuity fix lands
(same files; that spec is in flight). Rebase mechanically on its commit.

## 1. The envelope rides the band (the one-line asymmetry)

The solve's projections already run their reach envelope on the
route-metric band; the FINAL projection does not (`solve.py:5330`
default "0" vs `one_solve.py:1805` default "1" — and the final passes
do not pass `env_band`). Fix: the final projection builds/receives the
SAME band the solve used (`reach_band_unified` — THE one engine; carry
it across on the layout like `_taut_rod_key_edges`, or rebuild from the
same inputs if carriage is unsound — say which and why) and passes it
as `env_band` to its `feasibility_project` calls. Resolve the
env-flag default drift while there: one default, defined once,
documented; the historical "0"/"1" split dies.

## 2. Seed admission (the bigger half, measured)

New witness-admission law, mirroring the existing groundside clause: a
hard anchor whose node carries NO route-pavement role (its patch roles
are only within `{graded_strip, retaining_wall, runway_clearance,
taxiway_clearance, ols_cut, groundside_pavement, boundary}` — the
`ROLE_GRADE_LIMITS is None` family, plus groundside) may not seed the
airside feasibility envelope in ANY pass. It still anchors its own
vertex value (this spec changes witnessing, not values). Role
membership comes from the layout's own shape registry at solve time —
never fresh string literals (blast.py role-literal hazard).
**The 889 role-unmatched anchors from the counterfactual must be
CLASSIFIED by the implementation** (they exist in the solver, so the
solver knows their provenance) — report their split; excluding them
blind is forbidden (the counterfactual's air+unk bracket shows they
carry up to 146 of the ≥20 m deficits).

## 3. The off-route leg

A query node or admitted anchor off the centerline graph attaches via
its LOCAL leg: priced at the local cap, bounded by the band's existing
attachment radius (the raster lookup's own bound — reuse it, no new
constant). No chain may traverse shape-adjacency chords: the band
engine already guarantees this; the guarantee must now hold at every
pass.

## 4. Acceptance (pre-registered from the counterfactual table)

Gate: `O4_ROUTE_METRIC_ENVELOPE`, default "0" this round.

1. Unit tests: a synthetic two-runway tension absorbable via a long
   route but not via a short apron chord is FEASIBLE under the gate;
   a non-route anchor (graded_strip trace) cannot witness; the
   off-route leg is priced and bounded.
2. Gate-off byte identity: CYXY `dcebb6ff…`, SPLP `c2316222…`, HECA α
   `4be7fb4b…`.
3. Gate-on HECA α arm vs the counterfactual's `route/air` row
   (first-order expectations — this is a re-SOLVE, the counterfactual
   was a re-scoring, deviations are findings not failures):
   * deficits ≥20 m: 5,278 → ~0;
   * broken population toward ~5,200 (±sensitivity bracket 6,700);
   * deficit p50 toward ~5 m;
   * owner's example site: deficit ~0.67 m class, the 9.08 m wall GONE
     (with the blend fix also on, the site reads smooth);
   * the 282 runway×runway control class SURVIVES (it is real);
   * full-severity census: cliffs materially down (pre-register your
     number from the Δt×drain composition before building);
   * no groundside regression; no runway vertex moves.
4. SPJC gate-on arm (the airport where strings doubled breaks): break
   population before/after — the topology fix should shrink the
   string-era amplification surface too.
5. Battery (`O4_TEST_AIRPORTS` scoped runs acceptable for iteration;
   full battery before commit) + build-time delta from the phase
   ledger (the band already exists per solve — expected ~neutral; the
   hard law's 1% trigger applies).

## 5. Out of scope

The residue (route-local value conflicts, strip-weld values on route
pavement, the 282-class) — next attribution; quarantine retirement
(after the drain); the blend beyond what its own spec landed; strings.
