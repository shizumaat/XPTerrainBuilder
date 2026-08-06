# Cycle 4 — Ride never enters an anchor (the anchor-law spec)

**Status: LANDED** (lane/c4law `516e8bc` + `033c3d5`, merged 2026-08-05).
Cycle-4 target #2, checkpoint ab00777; fix-3A interventionally attributed.
Mode: BUILD-COMPLETE-THEN-DEBUG — no gates; decide-and-note deviations
toward the target architecture.

**Deviation RATIFIED (spec author, 2026-08-05):** the preferred mechanism
below (§Mechanism, joins in the ANCHORED set) was measured to re-mint the
self-anchor lock — anchored joins bound `flex_slack_at`, HEAZ went
green→BandInversionError. The landed mechanism is ZERO-BAND-BUT-FREE:
joins are zero-band stations of the DEM-follow blend (they seat exactly
on the law line, ride tapers to zero into them) but carry NO authority —
they do not bound the flex and follow the law line through later lawful
moves. Every frozen requirement holds. Companion instrument ruling: the
law/ride reader's law line is anchored ∪ flex-applied stations (owner
flex ruling: anything within the law is legal); the e5c8443 flex_minted
exclusion was a (d) instrument defect, fixed in `033c3d5`.

**Acceptance read (post-landing):** HECA canyon 3,169 nodes @ constant
12.8394 m → 382 nodes worst 1.6421 m; ride at anchors ≤0.019 m (five of
six readings <0.01 m floor); the whole residual is LAW-half — three
anchor pairs, law spreads 26.29/26.30/27.56 m over route budgets
24.658/25.793/27.084 m (shortfalls +1.6358/+0.5083/+0.4729 m). That
residual is the next cycle's metric/cap/topology attribution target
under the (a)-(d) vocabulary.

## The defect (attributed, fix-3A)

A runway profile's interior stations are a DEM-FOLLOW SEED:
`runway_segments.generate_patch_osm` sets every non-anchored station to
`clamp(DEM, law_baseline ± min(RUNWAY_DEM_FOLLOW_LAW_BAND_M, ½·K·d²))`
([runway_segments.py:1517-1542]). That is lawful SEATING — DEM choosing
where in the band the profile sits (RULINGS: DEM is a seed).

The defect: taxi-join anchors are VALUE-SAMPLED off that emitted surface
(`grade_graph._runway_anchors`, `_sample_runway_segment_elev` at
[grade_graph.py:2270] and the on-edge section below it) and published as
HARD band anchors (`G.runway_anchor` → `spine_value_fields` seeds). The
ride — up to ±10 m of world-dependent seating — thereby becomes LAW for
every band seeded from the join. Measured (fix-3A, HECA constant-DEM
pair): +20.000 m world-to-world on 71/75 stations of 05C/23C; HECA canyon
`BandInversionError`, 3,169 nodes at a constant 12.8394 m, of which
~6.0 m is pure ride ("LAW ALONE IS FEASIBLE here" rows in the law/ride
split report). Flex is EXONERATED (no-flex arm reproduces it).

## The law

An anchor carries LAW authority only. Seating freedom must remain visible
to the band as freedom — never republished as a hard value. Standing
citations: DEM's role (constant-DEM invariant), anchor placement law,
single-authority (single-solve architecture), band-lawful displacement.

## The requirement (frozen)

1. **The emitted runway surface at every taxi-join station equals the
   law-line value** — the anchored-station interpolation (CIFP
   thresholds, seams, cross-runway/crossing anchors, and flex-applied
   targets, which are lawful hard moves). The DEM-follow ride tapers to
   ZERO into every join station, inside the existing ½·K·d² envelope
   (smooth by construction — no new kink class).
2. Consequence, by construction: `_runway_anchors`' emitted-surface
   sample publishes the law value — ride never enters `G.runway_anchor`.
   Do NOT fork the sampling site into a second value authority; the ONE
   emitted surface stays the thing sampled (single-pass principle).
3. In the two constant-DEM worlds the SAME join station reads the SAME
   anchor value (the band-width field's anchor rows become
   world-invariant).

## Mechanism (preferred; decide-and-note if blocked)

Insert each runway's taxi-join stations into the profile's ANCHORED set,
valued at the law-line interpolation, BEFORE the DEM blend consumes
`anchored` — either:
- (i) in `generate_patch_osm` at the seeding site, if taxi centerlines
  are resolvable there; or
- (ii) at redistribute time (`runway_redistribute` /
  `_runway_redistributed_profiles`), where the layout and
  `apt_taxi_centerlines` are certainly available, followed by the
  existing `faa_joint_solve` re-run so every cap re-verifies.

Join-station derivation must reuse the SAME contact law the graph uses
(`grade_law.runway_join_contact` + the `_runway_anchors` candidate
logic) — one authority for "where a join is"; extract a shared helper
rather than duplicating (consult-before-create). A law-line-collinear
inserted station changes the law baseline by ZERO (the baseline is
already linear between flanking anchors) — assert that in a twin.

## Acceptance

- **The law/ride split instrument** (landed `7ea3e6e`,
  `building_feasibility._anchor_law_values` + the classified
  `assert_no_final_band_inversion` report) is the acceptance reader:
  after the fix, every surviving shortfall classifies as LAW-half only;
  ride contributions at anchors read ≈0 (≤ materiality 0.01 m).
- HECA constant-DEM canyon build (harness): the 12.8394 m constant class
  must lose its ride half. Combined with the flex-budget spec landing in
  the same lane, HECA canyon is expected to BUILD (the remaining
  law-half is the +7.011 m family that ruling closes). If a law-half
  residual remains, report it classified — it is (a)-(d) vocabulary
  work, never a re-ride.
- Twins: `tests/test_final_band_inversion.py` stays green; add a twin
  asserting a join-station anchor value is identical across the two
  constant-DEM worlds (per-airport synthetic geometry is fine).
- Real-DEM builds are GATED (RULINGS flat-green ruling) — do not run
  them for this lane.

Build budget: HECA oracle pair + HEAZ sentinel (~40 s) + unit twins.
Materiality 0.01 m; attempt cap 2; `.progress` heartbeat.
