# End-around taxiway (EAT) surface law — ANCHOR-RECT revision

Owner rulings 2026-07-27.  Supersedes the constraint-edge mechanism of
the first implementation (which ships in this tree GATED OFF —
`EAT_SURFACE_CEILING_ENABLED`, `config.py`) as the ACTIVE mechanism;
the first implementation's law functions, region helper, scoping
constants, verification reader and tests all carry over.

## The rulings (verbatim intent)

1. Mechanism: "identify them and create a runway-width rectangle in the
   EAT that's taxiway width by runway width, along the runway extended
   centerline (just the segment of the EAT that would be covered if the
   runway extended over it), and add that as a HARD ANCHOR, since we
   know exactly how much lower than the runway threshold it has to be.
   Then the solver just grades to it like it does to crossing runways,
   tile seams and the other CIFP threshold."
2. Value: "anchoring it at the regulation is the right course, even if
   it has to fill DEM" — pin at the regulation elevation
   UNCONDITIONALLY.  No min-with-terrain refinement.
3. Region: FAA for North America (ICAO first letter K/C/P/M), EASA
   everywhere else — already in `config.eat_surface_slope_and_setback`.

## Why anchor-rect instead of ceiling edges

The one-sided ceiling edges (`solver_primitives._build_eat_ceiling_
constraints`) inject NEGATIVE pavement-to-pavement weights into
`ceil_radj`; the lazy Dijkstra in `one_solve._reach` assumes monotone
weights and blows up (measured: KCLT killed at 15 min CPU / 20.3 GB;
`heappop` storm).  A HARD ANCHOR is a pinned node value — reach bands
propagate `E_anchor ± cap·d` outward through the EXISTING
positive-weight machinery (the same mechanism by which a low runway's
ceiling binds distant pavement).  No solver change, no envelope-leaf
work needed; that chip becomes optional.

## Build plan

1. **Rect**: per runway end passing the scoping guard, corridor =
   extended centerline, half-width = the runway's DECLARED half-width
   (see the declared-width chip — apt.dat row-100 width, shoulders
   EXCLUDED), from `EAT_MIN_CROSSING_DIST_M` (300 m) outward to the
   corridor's far scoping bound.  Rect = corridor ∩ taxi/junction/apron
   pavement; keep each connected crossing segment (one per EAT).
2. **Value**: `end_elev + eat_pavement_ceiling(D_mid, slope, setback,
   tail)` where `end_elev` is the SOLVED runway-end value (profiles
   freeze before the field solve, so this is a constant), D measured
   from the DER along the outward vector, slope/setback from
   `eat_surface_slope_and_setback(icao)`, tail from
   `TAIL_HEIGHT_BY_CODE_LETTER` via the end's code letter (declared
   width — NOT shoulder-widened).  Pin every pavement node inside the
   rect at that value (flat across the rect; the rect is short along
   the direction of EAT travel).  Where two ends' corridors overlap one
   EAT, the LOWER value wins.
3. **Anchoring**: register the rect nodes in the same hard-anchor store
   the tile-seam pins use (`layout._seam_anchor_keys` family /
   crossing-runway anchor pattern) so the route-profile solve holds
   them and grades the ramps at taxi caps + K-factor.  The ramps need
   ~700 m per side at KCLT (−8.6 m pin, network near DEM at +2 vs
   threshold); a loop too short to ramp lawfully escalates and reports
   — never silently breaks grade.
4. **Audit**: keep `verification.check_eat_ceiling` exactly as landed —
   it checks EVERY corridor vertex against the surface, covering the
   loop parts the anchor only governs via the caps.
5. **Gate**: reuse `EAT_SURFACE_CEILING_ENABLED`, flip default ON once
   the anchor-rect path replaces the edge builder (delete or
   permanently gate-off `_build_eat_ceiling_constraints`' negative-edge
   emission; its scoping helpers `eat_end_projection` /
   `eat_scoping_bounds` are reused by the rect construction).
6. **Tests**: tests/test_eat_ceiling.py (53) carries over — formula,
   region, scoping tests unchanged; replace the one-sided-edge tests
   with anchor-pin tests (rect nodes pinned at the value; gate-off
   byte-identical).  KCLT smoke: the EAT rect should solve to
   `end − 8.6 m` (FAA 40:1, code E via declared width) with ~1.5 %
   ramps; shipped-truth reference: pre-law the EAT is FLAT at end
   +0.9 m (sim-confirmed).

## Traps recorded this round (do not re-trip)

* Standalone KCLT elevation builds are GARBAGE unless the base raster
  exists: the checkout lacks `Elevation_data/+30-090/N35W081.hgt` (the
  app root has it); the loader now REFUSES an all-zero DEM loudly.
  Copy/symlink the .hgt before measuring, never git-add it.
* Two probes reported the zero-DEM artifact as real EAT geometry
  ("16-20 m below the end"); the shipped patch and the sim are the
  ground truth.
* `Runway.declared_width_m` currently returns the shoulder-widened
  rect width (62 m for a 45 m runway) — mis-codes E as F.  The
  declared-width chip fixes it; the EAT tail-class lookup must use the
  fixed accessor.
