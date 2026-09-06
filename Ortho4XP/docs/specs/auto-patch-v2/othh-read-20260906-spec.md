# v2 — OTHH read on 1.0.288: below-grade trench geometry, ramp width from pavement, basin handles (spec, 2026-09-06)

Owner (RULINGS 2026-09-06b): OTHH "looks quite good", three adjustments.
Author: session (Fable). Implementer: lane `v2othh3`.

## 1. Trench geometry for every below-grade object (tunnels, drainage)

Owner's law: the trench we cut must exactly match or slightly OVERLAP
the object's exterior side so no gap shows; on the interior the object
is completely exposed — the trench FLOOR slightly overlaps the object's
perimeter (walls have width), then a very small gap, and the
surrounding at-grade terrain follows the same perimeter at its outside
edge. No wall face is emitted: floor + at-grade rim with the right gap,
and the mesh engine makes the near-vertical wall between them.

Law (`structures.toml`): `[cutout] floor_overlap_m = 0.3` (the floor
extends this far OUTWARD past the object's inner perimeter — into the
wall's own footprint), `[cutout] rim_gap_m = 0.3` (the at-grade rim
stands this far OUTSIDE the object's outer perimeter), `[cutout]
emit_wall_band = false`. The owner's numbers are "slightly" and "very
small": the lane measures OTHH's wall thicknesses (tunnel walls 2.0 m,
drainage walls) and states the values; both keys ≤ half the thinnest
wall. Applies to tunnel objects (`planar/object_corridor.py`, the
`retaining_wall` band → no band, the trench = inner perimeter ⊕
floor_overlap_m, the rim = outer perimeter ⊕ rim_gap_m, the ground
between them free to the mesh) and to basins (`planar/basins.py`: the
floor = the object's floor plate ⊕ floor_overlap_m, the rim outside the
shell ⊕ rim_gap_m). The 09-01c/e `wall_gap_m` (0.6 m ramp-edge →
wall-inner-edge gap) is superseded for object corridors. Consumer
census (owner 30l) before editing: every reader of `retaining_wall` /
`tunnel_trench` faces and of the basin rim (constraints/structures,
verify/structures, emit roles, rebake, the census oracle's wall rows).

## 2. Ramp width from the pavement tracing the road

Where an apt.dat/DSF pavement follows the road through a tunnel ramp
(the pack traced the road), that pavement's width IS the ramp width —
wider or narrower than `[tunnel] lane_width_m × lanes`. Law: `[tunnel]
ramp_width_source = ["pavement", "lanes"]`; the lane detects a pavement
cell whose centreline runs along the ramp axis within
`ramp_pavement_max_offset_m` (state it) and takes its width per
station; else the lane/width default. Twin with a traced pavement 12 m
wide vs the 7 m default.

## 3. Basins shapeID 879 and 873 vs 877 (correct)

At 879/873 the object sits BELOW the trench floor instead of flush with
the terrain; 877 is right. Owner's read: object handle (anchor)
placement — the seat/floor derivation uses the object's origin where
the floor plate is elsewhere. The lane measures the three: anchor
position vs floor plate, the floor plate's authored y, the placement's
AGL/MSL, the emitted floor z, and the rendered floor; then fixes the
derivation so the floor = the rendered floor plate (anchor + agl +
plate y), never the anchor's ground, and the seat of a basin family
puts its floor plate ON the trench floor. Quote all three before/after.

## 4. Acceptance (OTHH, `--tile 25 51` once for the seat)

Owner sites: the two tunnel sites 25.2715296,51.6022683 /
25.2556192,51.6080938 (floor, rim, gap, no wall band); basins 873/877/879
floor vs object plate; census 0/0, v2-verify 0 (walls' rows retired with
the band); LEMD byte-identity is NOT expected (its OSM-bore walls change
too) — quote LEMD's verify before/after instead; CYXY unchanged.
