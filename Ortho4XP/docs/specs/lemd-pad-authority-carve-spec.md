# LEMD pad-authority carve — the big-pit ramp corridor (owner-sanctioned)

Owner, 1.0.265 sim pass (2026-08-28, item 2): "How can we identify the
ramp coming down into the big pit and ensure we cut away enough so the
terrain is not extending above the object" — this sanctions the carve the
trench-extension round's Amendment 2 left PENDING OWNER. Terrain (the
building8 pad's 600.5 flatten + rim-band ground) still stands above the
authored ramp descending into the basin (owner screenshot 2: a grass slab
hanging over the corridor at the rim).

## Standing findings (lemd-basin-trench-ramp-extension-spec, both arms)

- The ramp corridor ground BELONGS to building8's pad ring (owner probe
  points 9.87 m / 3.88 m INSIDE it, containment-measured);
  `BASIN_PAD_FLOOR_SEAT` yields the pad's flattening authority only
  OUTSIDE the facility. No trench-side lever can take it.
- Retired-kept-gated machinery to REUSE, not refork: the shared ramp-reach
  derivation `_region_ramp_reach_rings` + `_ramp_lobes_of` (batter/ramp
  separation) and the emit plate arm (`O4_BASIN_RAMP_REACH_PLATE`) in
  `object_terrain_features.py`.

## Law

1. IDENTIFY THE RAMP FROM THE OBJECT'S OWN GEOMETRY: the corridor is the
   authored ramp deck's footprint (the descending OBJ8 surface between
   grade and the basin floor), derived from the pack geometry the basin
   machinery already reads ("trench depth authority = the object's own
   geometry") — never hand coordinates, never the DEM.
2. CARVE THE PAD AUTHORITY: building8's flattening authority excludes the
   ramp corridor. Inside the corridor the floor plate (existing emit arm)
   owns the ground at the ramp's underside profile (or facility floor
   where the object gives none); the pad edge along the corridor is a
   declared wall/terrace (the declared-wall exemption class), not a bare
   cliff and not a smoothing ramp.
3. THE PAD STAYS FLAT OUTSIDE THE CORRIDOR at its committed value; the
   facility ring, floor (587.75), rim (600.51) and every founding read
   stay byte-untouched. Any movement outside the corridor is a STOP.
4. G INSTRUMENT — AMENDED (Fable, 2026-08-28, on the lane's STOP: the
   scoped 62-station read is 596.000 vs committed 596.682 on ONE surface,
   so "exclude the corridor" and "reproduce the committed value" cannot
   both hold as one number). RULED:
   a. The pack seats at a FOUNDED DATUM carried in its own provenance
      (`seat_datum_m`), never re-derived from a mesh mean over a carved
      surface. AMENDED after lane measurement: the live datum is
      **600.51** — written by the owner-accepted 1.0.265 build (the rim
      re-seat wave's level-to-level value; owner in-sim: "rim and
      elevation are all perfect now"). The historic 596.682 was the
      2026-08-27 dev-surface value, SUPERSEDED before this round; do not
      re-pin it. The carry law exists so no future rebake moves the
      datum again.
   b. The scoped (corridor-excluded, 62-station) read is the DRIFT
      DETECTOR: acceptance = it is STABLE across the carve (596.000 in
      both arms, tolerance 0.01 m). A moved scoped read means the carve
      touched ambient ground it must not — a STOP, never a re-seat.
   c. If the rebake machinery cannot carry a founded datum for this
      pack, STOP and report — do not let a rebake move the pack.

## Acceptance

- A mesh/patch probe along the ramp deck: no terrain above the authored
  ramp surface anywhere in the corridor (sample the deck line at ~2 m
  spacing; terrain ≤ deck underside everywhere).
- The prior round's two owner probes (40.4923132,-3.5697896 /
  40.4924064,-3.569366) inside emitted floor, containment-measured.
- building8 pad flat at its committed value OUTSIDE the corridor; floor
  587.75; rim 600.51; facility ring byte-identical; G re-read per §4
  reproduces the committed value.
- LEMD census not worsened; the plate-arm artifact classes (within_shape
  +196 airside, worst 12.74 m boundary rows) MUST NOT appear — the carve
  removes the colliding authority, so the plate no longer fights the pad.
- HECA/SPJC/OTHH byte-identical.
