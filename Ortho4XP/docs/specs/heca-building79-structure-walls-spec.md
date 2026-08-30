# HECA building79 — footprints from structure walls, not convex hulls
# (owner ruling 2026-08-30e; round-6 Family B law)

Attribution (accepted, measured in round 6b): building79 (way -10079,
shapeID 78, ~100,886 m², flat 97.85) is one pad because
`dsf_reader.read_dsf_object_buildings` emits each OBJ8's CONVEX HULL —
the seven DSF object footprints under it union into ONE 105,094 m²
part BEFORE `_close_building_outline` runs (the close adds +0.3 % and
is refuted as the minter). Three of the seven are hulls of whole
complexes: 60,390 m² (308x338, convexity 1.00), 43,463 m², 22,742 m².
No DSF facade and no OSM terminal way is there.

## Law (round-6 Family B, standing)

A building pad is one building's footprint; five buildings are five
pads with the pavement between them scored as pavement.

## Work

Replace the per-OBJ convex-hull footprint with a footprint derived
from the structure's OWN wall geometry: concave outline(s) of the
OBJ8's vertical structure, one polygon per disjoint structure — an
OBJ whose walls describe five separate buildings yields five
footprint parts, and the ground between them is NOT footprint.
Constraints:
- The vertical-structure evidence gate (R18-2) and the round-6b
  segmented-linear-array demotion are UNCHANGED — this changes the
  GEOMETRY a qualifying object contributes, not who qualifies.
- Degenerate/unclosed wall geometry falls back to the convex hull
  (never zero footprint for a qualifying structure); the fallback is
  logged per object.
- `_OBJECT_FOOTPRINT_CACHE_VERSION` bumps; one-time recompute cost is
  acceptable (round-6b measured ~73 s at LEMD scale), quote it.
- Mind pad seats: pad-count changes move the pad solve (the LEMD rim
  600.48→600.25 precedent, accepted 2026-08-30c) — quote any seat
  movements at building79's neighbours.

## Acceptance (site-first)

building79's site: the single 495x533 m pad is replaced by per-building
pads (the owner counted FIVE buildings) with pavement between them
scored as pavement; each pad flat at its own lawful value. Synthetic
twin: an OBJ8 fixture whose walls describe two disjoint boxes yields
two footprint parts with a gap. Whole-pack control: pad count and
total pad area at HECA quoted control→arm; no qualifying structure
loses its pad entirely (fallback proves out). ONE closing HECA build;
control = round-6b closing arm (ledger, body d1a5a580652d). Census not
worsened beyond attributed pad-population effects (quote them
separately, the item-3 LEMD precedent). Below-bar = STOP with residual
quoted.
