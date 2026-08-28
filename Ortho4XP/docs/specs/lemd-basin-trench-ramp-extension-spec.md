# LEMD basin trench extension under the ramp (owner sim read 2026-08-28)

Owner read of app 1.0.264 (LEMD big pit): "rim of the pit and elevation are
all perfect now, just the terrain is poking through the ramp at
40.4923132,-3.5697896 — extend the trench/pit bottom under the ramp to about
40.4924064,-3.569366."

## Current geometry (owner patch `+40-010/+40-004/LEMD_auto.patch.osm`, 07:09)

- `object_basin_trench` floor way -11774 (shapeID 1775), 587.75 m, ends
  ~1.2 m from the first coordinate.
- `object_basin_rim` ways -11776/-11777/-11775/-11783 at 600.51 m.
- The target point sits ~11 m outside the floor polygon; between the floor
  edge and the target the mesh stands at rim/DEM height and pokes through
  the authored ramp object descending into the pit.
- Distance to cover: ~29 m ESE from the current floor edge, under the ramp
  span, through 40.4924064,-3.569366.

## Law

Extend the basin trench FLOOR region (the founding-geometry derivation, not
a hand-edit of the emitted patch) so the floor pan covers the ramp's span
through the target coordinate. The extension keeps floor value 587.75 (or
the ramp's underside profile if the founding machinery already carries one —
do not invent a slope). Rim, walls, and the committed basin arc invariants
(founding c446edba, group seat 690d0568, the ONE G=596.682 relationship at
0.000000 m — see memory lemd-aerosoft-patch-ground-truth) are untouched;
any change to them is a STOP, not a side effect.

## Acceptance

- Rebuilt LEMD patch: floor polygon covers a probe at 40.4924064,-3.569366;
  `osm_site.py --at` shows `object_basin_trench` at 0 m from both owner
  coordinates.
- The basin relationship invariant unchanged (byte-diff the basin sidecar
  rows / re-run the arc's own check).
- LEMD census not worsened; controls (HECA/OTHH arms) untouched.
