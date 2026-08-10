# Round 6 — OTHH residuals (2026-08-10, FROZEN; pre-ship mode)

Author: lead (Fable). Charter: owner in-sim ("OTHH is almost all
fixed") — three residuals, mechanisms measured by recon on the 10:30
rebuild. PRE-SHIP MODE (docs/RULINGS.md): unit tests for changed
behavior only, run once, no builds.

## R6-1 — DSF building pads never span water

building1 (way -10001, 19,466 m²) carries 2,055 m² (10.6 %) of open
water: the CONVEX HULL ring (`object_footprints.py:492
structure_ring`, `DSF_OBJECT_FOOTPRINT_UNION=0`) bridges a lagoon +
shore; close/simplify added nothing. THE LAW: DSF-cluster building
pads are CLIPPED by the OSM water ∪ sea union (coastline-derived)
after the close/simplify loop (`pipeline.py:2890-2900` — load the
tile's water/coastline extracts there; they exist per-tile beside
the airports extract). Remainder rules as §2.3b of the terminal-way
spec: sub-20 m² drops, MultiPolygon parts emit separately, edge-only
touch untouched. OSM-WAY pads are NOT clipped (mapper's authority;
Emiri -77 is 27 m inland and clean). Regression pin: pad area over
water at OTHH → ~0; building87 unchanged.

## R6-2 — Implied-tunnel evidence must ride the same road

The two S1 bores were admitted by `S|-8342` (tunnel=yes, service),
78.8 m from the crossing part but FOUR NETWORK HOPS away through a
class change and a real junction — "network-connected within 100 m"
admits exactly the bore R4 meant to refuse. THE LAW: the evidence
chain walk (`bridges.py:465 _chain_tunnel_evidence`) advances only
through DEGREE-2 endpoint joins of IDENTICAL signature (the existing
`_sig` predicate, `bridges.py:600-613` — same highway/railway/name);
a junction node or class change ends the walk. Census-verified
outcome to pin in tests: OTHH's 8 self-evidenced bores (on -917/-918
secondary tunnel=yes) survive; the 2 S1 bores refuse at hop 1; the
S4 service continuations never enter the implied path at all
(service ∉ _IMPLIED_HW_TYPES).

## R6-3 — Flush-deck bridges over water seat at abutment grade

Bridge_01 (TERRAIN_CARRIED, cosmetic flush deck, deck_top −0.31 m):
its resources are R4-EXCLUDED from the y-bake, its anchor sits over
water (DEM 0.00 at anchor and every deck station), so it drapes
~3.96 m low; the crossing-floor path also declines
(`bridges.py:9845` — deck under BRIDGE_ROAD_CLEARANCE_M). THE LAW: a
TERRAIN_CARRIED bridge whose anchor ground sample sits more than the
reseat threshold (1.0 m) BELOW its certified abutment grade (the
classifier's `abutment_reaches_grade` land witnesses — median ground
along `bridge.abutment_lines`) LEAVES the exclusion set and takes a
Phase-2 seat at that abutment-grade consensus (decision kind
`bridge_abutment_seat`, provenance recorded; measure-only mode
honored). Delta here ≈ +3.96 m — a lawful ≥1 m reseat under the
threshold law. Expected: deck top ≈ 3.65 m (abutment grade + authored
−0.31). Bridges whose anchors sample land within threshold stay
excluded/draped as today (regression pin: Bridge_02/03/06 unchanged).

## Tests (one lane, run once)
R6-1: synthetic pad over water clipped, remainders per rules, OSM-way
pad untouched. R6-2: the census pin above as synthetic twins (same-
signature continuation admitted; junction/class-change hop refused).
R6-3: over-water anchor + certified abutments → seat at abutment
median, kind recorded; land-anchor bridge unchanged; measure-only
writes nothing. Cache/sidecar versions bumped where records change.
One deferred-verification line; owner sims OTHH after the next
rebuild.
