# Round 8 — VHHH close-out (2026-08-10, FROZEN; pre-ship mode)

Author: lead (Fable). Charter: owner in-sim on 1.0.232 ("VHHH mostly
fixed", three items + screenshots). Mechanisms measured by recon;
two hypotheses refuted there (no DEM path feeds the canyons; the
object transform is exact to 0.000 m). PRE-SHIP MODE: unit tests
once; no builds by the implementer.

## R8-1 — The flat extent covers the airport's claimed objects

The HZMB reclamation (121+ pack placements, no apt.dat/OSM claim)
sits 894 m outside the substitution bbox → a 7.32 m step at its
edge. THE LAW: the flat-site substitution ALSO covers the claimed
object placements — at `flat_site_mode.py:324`, cluster the claimed
placements (all 5,708 fall to VHHH via
`post_mesh.worklist_claim_assigner`; positions already cached via
`dsf_reader.read_dsf_object_placement_positions`) and emit ONE
`_ConstantInset` PER CLUSTER (hull ⊕ the flat margin), never one
grown bbox — the measured 450 m open-channel gap (lon
113.945–113.948) between airport and island must stay sea.
Clustering: simple distance join (placements within ~300 m merge);
clusters with < 5 placements ignored (streetlight strays).

## R8-2 — No solved value leaves its reach band (the canyon law)

At every runway end, `graded_strip` bands carry solved edge
altitudes of −10…−13 m against reach bands of [4.6, 9.4] — the
sidecar's own `band_excess` recorded 199 floor-side escapes to
17.15 m. The band emitter and every DEM path are exonerated; the
escape happens in solver writeback. THE LAW (this is the standing
band doctrine, enforced): the writeback CLAMPS every solved value to
its unified reach band before any consumer reads it
(`adjacent_ground` consumes `edge_alts` at `adjacent_ground.py:1154`
— the clamp lives upstream at the writeback, not per-consumer); each
clamp increments a counted, logged finding (site, delta) — a clamp
is evidence of a solver defect to chase at the ship gate, never
silent. ACCEPTANCE METRIC: VHHH `band_excess` floor-side material
rows → 0. (Root-causing WHICH stage wrote −12.5 needs an
interventional arm — ledgered for the hardening round, not this
lane.)

## R8-3 — One authority per tunnel: objects own, OSM yields

The emitted object trenches and the OSM-derived ramps/walls disagree
by 2–7.6 m per structure (58 % of OSM ramp area outside every pack
body; 61 overlapping quads with −1…+5.4 m altitude conflicts — the
jagged seams in the owner's screenshots). THE LAW: where a CLASSIFIED
object tunnel owns ground (the body-footprint union
`object_terrain_assembly._tunnel_footprint_longitude_latitude_parts`
already builds), the OSM tunnel chain YIELDS — `bridges.py`
(`_load_tunnel_road_network` consumers at :2823/:2884/:2891/:3041)
drops/clips ramp+wall pieces inside those bodies ⊕ a small margin
(2 m); the object trench is the rendered truth. OSM-only tunnels
(no classified object) emit exactly as today. Note for tests: the
uncovered `tunnel4_done` body (no trench emitted today) must not
lose its OSM ramps — the yield applies only where an object trench
EXISTS.

## Tests (one lane, run once)
R8-1: cluster fixture — two placement clusters + gap ⇒ two insets,
channel untouched; sub-5 strays ignored. R8-2: synthetic solve with
a forced band escape ⇒ clamped + finding; in-band values untouched
(equivalence pin). R8-3: ramp inside a classified body ⇒
dropped/clipped; OSM-only tunnel unchanged; tunnel4-class (body, no
trench) keeps ramps. Cache/record version bumps where record shapes
change. One deferred-verification line (the interventional
band-escape attribution is explicitly ledgered).
