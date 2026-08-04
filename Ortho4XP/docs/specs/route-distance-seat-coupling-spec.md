# Route-distance seat coupling: one metric for the coupler and the law

> **RECONCILIATION (2026-08-04, with DRAFT-seed-fix-round-spec):** the
> seed-fix round's §3 shares this spec's mechanism family (polytopes
> priced on a metric the projection does not enforce). Ruling: UNIFY
> THE METRIC, FENCE THE ROUNDS — the seed-fix round builds the
> law-graph budget oracle ONCE (route-metric distance/budget priced
> exactly as phase A projects); §1 below CONSUMES that oracle instead
> of building its own pricing. This round stays a separate dispatch
> (own arms, own bands) and lands AFTER the oracle exists.

Fable spec DRAFT, 2026-08-04, assignment 5. SCOPE ASSUMPTION (flagged):
the assignment-5 brief did not reach this agent; scope is reconstructed
from carrier_attrib/DOSSIER.md §2's own fix shape ("derive the
coupled-pair set from the same graph the projection enforces") plus the
route-metric rulings. If the lead's brief differs, re-scope before
dispatch. Per the coordinator (2026-08-04): this lane is UNAFFECTED by
the held spine-seed/band attribution — the budgets below consume the
law graph's edge caps, never `reach_band_unified`. Lines against
86e7310 + the uncommitted seat-flip edits (see Baseline note). BINDING:
docs/RULINGS.md (single-pass; band-lawful displacement — route-metric
frame; feasibility-is-guaranteed; convergence guards).

## Mechanism (two instruments, one population — the coupler's metric
## is not the law's)

The seat coupler admits and prices pairs in a STRAIGHT-CHORD frame:
polygon distance ≤ the 200 m corridor cutoff, limit |L_i − L_j| ≤
`APRON_MAX_GRADE`·gap with gap = straight-line distance
(`build_building_seats`, anchors.py:192ff). The projection enforces the
cap along the WITHIN-SHAPE LAW GRAPH. Measured (DOSSIER §2, HEAZ):
pads building4↔building5 are 17.6 m apart by chord (limit 0.176 m) but
bound by the 2-hop chain 35 —0.0578 (7 m)— 1295 —0.1015 (11.2 m)— 37:
the REAL budget is 0.1593 m, and the pair stalled 8 000 sweeps (28.8 %
of HEAZ's budget). After the spine yield, (37,1295) is the NAMED NEXT
carrier (spine_freeze/RESULTS.md #2) with HEAZ's worst remaining gap
(2.754 m) — this spec's fix population. The shared-surface predicate
(dossier-fixes §3, `O4_SEAT_COUPLE_SHARED_SURFACE`) repaired ADMISSION
for ring-sharing pads, but the LIMIT and the corridor cutoff remain
chord-priced: at HECA it admits 126→152 pairs and 105→130 ship
violating their own limit — more admission under the wrong metric just
finds more empty polytopes. The chord cutoff also rejects 2 613 HECA
pairs as `gap>corridor` — chord-far and route-unreachable are different
populations. Route-metric is the ruled frame (band-lawful displacement;
`ROUTE_LEG_EXACT`/`BAND_SEED_EXACT` flipped default-on in the kill
half; the raster band's 8.7 m service-over-apron feasibility leak is
the documented cost of not using it).

## The design

1. **One metric.** Pair admission AND budgets derive from the same
   within-shape law graph the projection enforces (reuse the existing
   constraint graph — single-pass; never a re-derived proximity or
   visibility instrument). Pair budget = the per-edge budget sum along
   the minimum-budget path, priced exactly as the projection prices its
   edges (for 35↔37 that is 0.1593 m — the number that actually binds).
2. **Admission.** Pairs route-reachable within
   `ROUTE_COUPLING_MAX_DIST_M` (owner dial; provisional 200 m to
   preserve today's reach intent) couple; route-unreachable pads do not
   (no law binds them — coupling them was never meaningful). The
   shared-surface predicate is SUBSUMED (ring-sharing pads have a
   through-surface path); the chord corridor cutoff and any remaining
   visibility-fraction pathway die inside the gate.
3. **Polytope.** Per-pair route budgets feed the existing polytope;
   the empty-polytope report (c5d39f8 §4) is unchanged and stays loud.
   Budgets can TIGHTEN where the chord overestimated (0.1593 < 0.176
   above): MORE empty polytopes is honest measurement feeding the
   split-level trigger, not a regression — pre-registered below, with
   the split quoted.
4. **Identity check (the point of the round).** For every coupled
   pair, the coupler's budget equals the projection's binding-path
   budget within 1 % — asserted in-round; a larger disagreement means
   two instruments again and is the STOP, not a tolerance to widen.

Gate: `O4_SEAT_COUPLE_ROUTE_METRIC`, default "0". With it on,
`O4_SEAT_COUPLE_SHARED_SURFACE` (now default ON per the seat-flip
battery) becomes redundant and is bypassed, never fought.

## Baseline note (concurrent seat-flip round)

At writing, the main tree carries UNCOMMITTED default flips of
`O4_SEAT_BAND_CONSISTENT` and `O4_SEAT_COUPLE_SHARED_SURFACE` to "1"
(the seats-both battery: HECA 9 952 → 9 649 within, HEAZ 118 → 117).
All arms and bands below are quoted against the NEW defaults (152
pairs / 130 shipping at HECA), and the gate-off identity anchors are
the seat-flip round's NEW body hashes — the lead pins them at
dispatch. The pre-flip anchors (SPLP 1531e6d0 / CYXY 5b7a1912 / HEAZ
5854d6e7 / HECA 2a28d01b / KCLT 74c4731f) apply ONLY if dispatch
precedes the flip landing.

## Pre-registered outcomes (bands)

1. HEAZ: (35,37) couples at the projection's own budget; the carrier
   (37,1295) is ABSENT from the stall-carrier list (hard); stalled
   calls 10 → ≤8 success / ≤9 partial; the HEAZ worst-gap 2.754 class
   clears or moves to a named next carrier (quoted).
2. HECA at new defaults: shipping-in-violation 130 → −40 % success /
   −15 % partial; any rise is acceptable ONLY as fully accounted
   tightened-honest-budget pairs (the split quoted pair-by-pair);
   empty-polytope pad count re-quoted as split-level trigger data.
3. Rejection census: `gap>corridor` (HECA 2 613) re-quoted under route
   admission; `not_visible` = 0 (the predicate is gone inside the
   gate).
4. Locality: every pad whose pair set is unchanged seats
   byte-identically (asserted in the A/B).
5. Census both frames at HEAZ + HECA quoted OFF→ON; no new over-cap
   class; severity does not rise.

## Acceptance

Gate-off byte identity (body hashes, 2×) on the current default
anchors per the Baseline note. Suite: same 23 reds; new tests
(route-vs-chord budget divergence twin — the 35/1295/37 geometry;
admission supersession of the shared-surface case; the budget-identity
property test; route-unreachable non-admission; loud polytope
unchanged). Runway vertices byte-identical. Only `check_build_time
--run` timings quotable; no timing claim; ≥1 %-budget measured cost ⇒
Fable-5 optimization review per hard law. Build budget: identity 2×5 +
HEAZ arm + HECA arm ≈ 1.5 h honest wall total, foreground, WORKTREE
(venv/OSM_data symlinked; the main tree hosts the seat-flip round's
live edits — do not build from the dirty main tree). No commit.
Convergence guards: 0.01 m materiality, 2 attempts, `.progress`.

## STOP rules

Budget-identity disagreement >1 % on any coupled pair (report the
pair, do not widen the tolerance); shipping-in-violation rises beyond
the tightened-budget accounting; pair-set blowup (>5× the new-default
baseline); band-1 carrier still present after one fix attempt; second
miss on any target.

## Out of scope

Seat VALUE law (`O4_SEAT_BAND_CONSISTENT` — flipped by its own round);
sectioning (split-level spec); the spine-seed/band attribution (HELD
lane — nothing here validates seeds against bands); spine-yield
default; the terrace and consensus rounds.
