# Round 7 — SEAWALL at the pavement/water edge (2026-08-10, FROZEN; pre-ship)

Author: lead (Fable). Charter: owner in-sim at VMMC — "taxiways at
the right level, however... we need a vertical wall drop to water
level, otherwise the water itself is sloping up to the taxiway."
Mechanism: the R6/pavement-is-land ring blocks the sea flood
(patch-pavement-is-land-spec.md), but the mesh outside the ring
still TRANSITIONS from deck elevation to sea level over the
triangulation's horizontal run — a ramp where reality has a wall.
PRE-SHIP MODE (docs/RULINGS.md): unit tests once, no builds.

## The law

Where a patch pavement ring borders WATER (the segments of the ring
seaward of / intersecting the OSM water ∪ sea union — the same union
and orientation law `osm_load._load_osm_water_sea_union` built for
R6-1), the vector map emits a SEAWALL: a companion breakline offset
OUTWARD by `SEAWALL_OFFSET_M` (0.5 m, env-overridable) along exactly
those segments, carrying elevation = the water level (sea: 0.0;
inland water: that polygon's level if the vector map knows one, else
0.0), marked so it constrains mesh z (the INTERP_ALT idiom) but
carries NO water-blocking bits (the sea may own it). The mesh then
drops deck→water over 0.5 m — reads vertical, the near-vertical-wall
class the carve rulings already bless. Land-bordering ring segments
emit nothing (normal blends unchanged).

Implementation home: O4_Vector_Map at the patch-ring insertion site
(the ring's water intersection is computable there — `patches_area`
and the sea polygon are both in scope in `include_sea`/
`include_patches`; thread minimally, follow the r4water lane's
plumbing). Constants beside `PATCH_RING_MARKER`.

## Tests (run once)
Synthetic: ring crossing a sea polygon → seawall breakline on the
seaward segments only, at 0.0, offset 0.5, no water bits; fully-
inland ring → no seawall; the R6-1 regression pins still green
(attr-9 bridges keep water; flood still blocked). VMMC-shaped twin:
a corridor ring through sea gets seawalls both sides.

## Acceptance
Unit tests once; owner sims VMMC after the next +22+113 rebuild
(expected: vertical drop from taxiway deck to flat water). One
deferred-verification line.
