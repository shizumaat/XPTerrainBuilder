# Round 4 — OTHH in-sim fixes (2026-08-10, FROZEN; pre-ship mode)

Author: lead (Fable). Charter: owner 2026-08-09/10 in-sim reports on
1.0.229. Mechanisms measured by two recon passes over the owner's
build artifacts (numbers cited inline are theirs). PRE-SHIP MODE
(docs/RULINGS.md): unit tests for changed behavior only, run once;
no builds by implementers; owner sims the result.

## R1 — Pad requests: the plan-box fallback is retired

Measured: 61 fallback plan-box rings are 83 % of pad area; the worst
(TerminalRoads mega-part) is a 564.8 × 534.3 m box → a 224,146 m²
pad; the offenders are pier-supported viaducts whose decks have ZERO
triangles in the 0.5 m contact band, so `object_anchor.py:1990-1992`
falls back to the WELDED MEGA-PART's plan box (`:1389-1397`).

THE LAW: a part with NO contact-band triangles raises NO pad request
— an elevated deck does not want terrain raised to it; its piers
belong to parts that do touch ground. The fallback survives ONLY for
parts whose base sits within the contact band of ground (degenerate
mesh case) AND whose plan box is ≤ 2,000 m²; anything larger drops
with a verbosity-1 log naming the resource. Sidecar version bumps
(4 → 5) so the 30-hectare requests on disk are discarded. Pads: 44 %
of the patch's ways today; expect the population to collapse (the
flat surface already made 94 % of requests sub-0.05 m).

## R2 — Objects claim their CONTAINING airport

Measured: OTBD owns the whole Aeroscape pack tile-wide because it
sorts first and ONE object in its bbox+3 km claims the pack
(`driver.py:489-500`, `:447-456`; 6,740 of 8,913 objects are outside
even that margin; requests filed under `icao: OTBD`;
`object_pads._footprint_claim` already rescues pad attribution but
the REBAKE runs pack-wide under OTBD's label).

THE LAW: worklist entries are per-airport by CONTAINMENT — an object
belongs to the airport whose boundary/pavement hull (250 m dilated,
the `_footprint_claim` geometry) contains it; unclaimed objects go
to the nearest airport's entry. The pack appears once per airport
WITH the airport's own object subset recorded; post_mesh consumes
per-airport subsets; the request `icao` is computed from the
request's own coordinates, never inherited from a loop label.
Rebake decisions and provenance carry the claiming airport.

## R3 — Classification hard gates (owner rulings, verbatim in RULINGS)

1. "Pavement touching a runway cannot be apron": scorer-v2 hard gate
   `runway_contact` (`pavement_scoring.py:1821-1930` block) fed from
   `layout.runway_union` — a candidate whose ring touches the runway
   ring (≥ 1 m shared perimeter or ≥ 10 % of own perimeter within
   0.5 m) is never APRON (falls to junction/taxiway per existing
   enactment). The legacy rule exists but is dead under v2
   (`pipeline.py:4297-4298`) — the gate is the v2 rebirth. Measured
   specimen: sid102, 376 m², 51 % of perimeter on the runway.
2. "Narrower than a taxiway cannot be apron": hard gate — a
   candidate that vanishes under 2.0 m erosion (the existing
   `_is_tail`/erosion primitive) is never APRON. Specimens sid105
   (4.1 m OBB width), sid104 (2.4 m).
3. Tunneled roads are not surface roads: ways with `tunnel=yes` (or
   `layer` < 0) are EXCLUDED from the surface road feed
   (`pavement_classification.py:427-429`) and G-FREE-ROAD gains a
   tunnel veto (`pavement_scoring.py:1824-1829`). Specimen sid103 —
   a 2.5 m "service road" ribbon painted over the mapped tunnel pair
   -9169/-9170.

## R4 — Implied tunnels require tag evidence

Measured: the S1 ramps (25.2531, 51.6209) are engine-FABRICATED —
`_synthesize_implied_crossing_bores` (`bridges.py:998-999`) invents
`tunnel=yes` for untagged tertiary ways crossing our pavement
(`bridges.py:664-849`, gate `IMPLIED_CROSSING_TUNNELS` default ON);
no OSM tunnel exists within 73 m. THE LAW: synthesis requires TAG
EVIDENCE — the crossing way, or a way its chain connects to within
100 m, carries `tunnel=yes` or `layer` < 0. A purely geometric
crossing is never a tunnel. (S4's pair — untagged continuations of a
mapped tunnel — still qualifies; S1's do not.)

## R5 — Flat-site profile collapse (the S5/S7 regression)

Measured: under flat mode, surfaces that sampled the DEM for their
per-vertex profiles collapsed to constant Z0 while ramps keep their
dive: the S5 retaining wall went from a 2.90–5.00 m graded crest to
a flat 4.00 against a ramp at −4.02; S7's groundside lost its 79
per-node 1.30–3.97 m profile (bare nodes, way-level 3.96) and meets
the ramp with a 5.62 m step at 2.6 m spacing — the invalid-triangle
source. Neither site is near the synthetic-extent edge; this is
internal.

THE LAW: transition surfaces adjoining BELOW-GRADE geometry (tunnel
walls' crest bands, groundside/service plates within the ramp's
transition reach) take their profile from the TRANSITION LAW —
grade from the ramp/portal profile up to the surrounding surface
(Z0 under flat mode) at the lawful groundside cap over the available
run — never from a raw DEM sample (constant or not). Wall band:
`bridges.py:3290-3412`; groundside altitude assignment:
`groundside.py`'s writer for the affected plates. This must hold on
real-DEM sites too (the DEM sample was always the wrong witness
beside a law-cut ramp; flat mode only exposed it).

## R6 — gap_fill is tunnel-aware

Measured: the S6 spine runs THROUGH ramps because gap detection sees
only `_AIRSIDE_PAVEMENT_ROLES` and the enclave blocker path exempts
tunnel roles (`gap_fill.py:2271-2275` via `_enclave_exempt`;
regression window: `efdeae6` 2026-08-07 removed the interior ring
that used to hold the ramps out). THE LAW: tunnel roles
(`tunnel_ramp`, `tunnel_wall`, `tunnel_trench`) are BLOCKERS in the
enclave gap path — a gap face is cut against them and a spine never
enters their footprint. Verifier already flags the overlaps; after
the fix those verifier lines are the regression test's assertion.

## Tests (per lane, run once)

R1: no-contact elevated part → no request; degenerate small fallback
kept; >2,000 m² fallback dropped+logged; v5 gate. R2: two-airport
fixture — containment partitions objects, request icao from
coordinates, rebake label. R3: the three gates on the measured
specimens' geometry (synthetic twins). R4: untagged crossing → no
bore; tagged-chain crossing → bore. R5: wall/groundside profile
grades ramp→Z0 (fixture with a constant DEM — the flat case IS the
fixture); no bare-node plates beside ramps. R6: ramp inside a gap
face → spine clipped out.

## Lanes

Lane A (`r4class`): R3, R4, R6 — pavement_scoring/classification,
bridges synthesizer block, gap_fill/enclaves. Lane B (`r4pads`):
R1, R2, R5 — object_anchor/post_mesh/driver, bridges wall band,
groundside. bridges.py regions are disjoint; lead merges. No builds;
the lead integrates, builds once, ships the app; owner sims.
