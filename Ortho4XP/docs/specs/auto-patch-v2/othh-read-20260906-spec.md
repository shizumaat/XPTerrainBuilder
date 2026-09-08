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

## 1a. Amendment 2026-09-08 (RULINGS 2026-09-08a; lane `v2trenchgap`): the rim moves INSIDE the wall

Owner: "the trenches gap between wall and ramp are too large so it
leaves a visible hole around the object based walls where the terrain
drops down, we need our tunnel_wall shapes to be closer to the ramp,
creating a steeper drop that's hidden inside the airport's wall
objects." Under §1 the rim stood `rim_gap_m` = 0.3 m OUTSIDE the outer
face, so the mesh wall (rim → floor ring) was the wall's full plan
thickness wide (OTHH side walls 1.00 m: rim 1.00 m off the ramp edge)
and its top edge lay 0.3 m outside the object — the drop began in the
open.

**Law.** `[cutout] rim_gap_m` is retired; `[cutout] rim_inset_fraction
= 0.5`: the at-grade rim stands `rim_inset_fraction × t` INSIDE the
wall's outer face, `t` the wall's MEASURED plan thickness at that
station (a corridor's `Station.thick_l/thick_r`, its end walls'
`mouth_thickness_m` / `far_thickness_m`; a basin shell's thinnest wall —
the smallest plate-edge → footprint-edge distance sampled every grid
step, capped at `wall_face_max_thickness_m` 2.0: an area ratio is not a
thickness, LEMD basin:3's 366 m² plate in a 452 m² footprint read 29 m
by one and was refused).
`floor_overlap_m` is unchanged (the floor ring stays 0.3 m outside the
inner face). One helper states it for tunnel walls AND basins (06b one
law): `planar/structure_geometry.rim_standoff(t, co, spacing)` →
`(inset_m, standoff_m)`,

    inset_m    = rim_inset_fraction × t
    standoff_m = max(t − floor_overlap_m − inset_m, spacing)

`standoff_m` being the plan distance from the floor ring to the rim
(= the mesh wall band's width), `spacing` =
`emit.identity.min_distinct_spacing_m` (0.5): a rim vertex is never
closer to the floor ring than the identity spacing, because two
distinct vertices never are (the census's proximity knob). THIN
SHELLS: when `t − floor_overlap_m − inset_m` is under the spacing the
spacing binds and the rim stands `floor_overlap_m + spacing` = 0.8 m
outside the inner face wherever the wall is thinner than that — at
the outer face for a 0.8 m wall, outside it for thinner ones (a 0.75 m
drainage shell: 0.05 m outside; a 0.4 m shell: 0.4 m outside). Per
family at OTHH (law inset / emitted stand-off): side walls 1.00 m →
0.50 / 0.50 (rim 0.20 m inside the outer face; was 1.00 m off the
ramp, 0.30 m outside the face); end walls 2.0–2.5 m → 1.0–1.25 /
0.70–0.95 (rim at half the thickness); drainage shells 0.75 m → 0.375
/ 0.50. The floor `floor_overlap_m + spacing` is the identity grid's
own: a wall thinner than 0.8 m cannot hide the drop under this law
without moving `floor_overlap_m`, which this amendment does not.

**Consumer table (owner 30l; reader → today → after).**

| reader | today (§1) | after (§1a) |
|---|---|---|
| `law/structures.toml [cutout]`, `law/model.Cutout` | `rim_gap_m = 0.3` | `rim_inset_fraction = 0.5`; `rim_gap_m` gone (loader refuses the old key) |
| `planar/structure_geometry.py` | doc: rim = outer face ⊕ gap; `geometry()` pushes the rim out by grid steps until it clears the ramp by `rim_fn(s)` | `rim_standoff()` added; `geometry()` unchanged — `rim_fn` now returns the (smaller) stand-off |
| `planar/object_corridor.py` `rim_fn` / `cap_off` / `far_off` | `max(t − overlap, 0) + gap` per station and end wall | `rim_standoff(t)[1]` per station and end wall; beyond the walls the OSM bore stand-off as before |
| `planar/structures.py` mouth-cover tolerance (:223) | `rim_gap_m + end_cap_open_m` | `end_cap_open_m` (the rim no longer stands outside the footprint) |
| `planar/structures.py` open-mouth strip (:459) | mouth line ⊕ `rim_gap_m + grid` | mouth line ⊕ `grid` (the spacing: the mouth edge shares no vertex with the covering ground) |
| `planar/structures.py` pad-clip portal (:598) | OSM bore `rim_off` | unchanged (OSM bore law, `wall_gap_m + wall_band_width_m`) |
| `planar/basins.py` `_rim` | footprint ⊕ `rim_gap_m` (+ grid steps) until every floor clears it by the gap | footprint ⊖ `inset_m` (widened by grid steps) until it contains every floor and every floor clears it by `standoff_m`; the refusal names the stand-off |
| `airport/tunnel_walls.py` / `tunnel_objects.py` | measure `thick_l/thick_r`, end thicknesses, floor the station thickness at the grid | unchanged — the measured thickness is now the rim's input |
| `emit/graded.py` `RIM_KIND`, `emit/osm_adapter.py` `structure_rim` | the void's exterior ring emitted as a role-less constrained ring | unchanged (the ring is wherever the planar rim is) |
| `verify/structures.py` `structure_rim_gap` | rim vertex shares no id with a floor vertex and stands ≥ `rim_gap_m` off every floor vertex | ≥ the identity spacing off every floor vertex (the stand-off's floor; the per-wall value is planar's, not the patch's) |
| `verify/frame.py`, `verify/strips.py` | read `structure_rim` features | unchanged |
| `tools/check_grade.py` / `harness/census.py` | `structure_rim` on the feature skip-list | unchanged |
| `tools/harness/oracle.py` | no rim reading | unchanged |
| `tools/osm_site.py --relate` | pairs among ROLE rings only (feature ways absent), `gap_m` = polygon distance (0 for a rim around its ramp) | feature rings join as role `feature:<name>`; `boundary_gap_m` (exterior-to-exterior) added — the rim-to-ramp reading at a site |
| twins | `test_tunnel_objects` (rim ⊆ walls ⊕ gap + 4 grid, ≥ gap off the ramp; both keys ≤ half the thinnest wall), `test_m4b` (basin rim ≥ gap off the floor) | restated on the stand-off; `test_v2trenchgap.py`: 1 m wall → inset 0.5 / stand-off 0.5; 0.4 m shell → the spacing binds (rim at the outer face + 0.4); floor ring untouched; band width before/after quoted |

**Acceptance.** OTHH `--tile 25 51` once: verify 0, census 0/0, the
tunnel rows unchanged; at the two tunnel sites the rim-to-ramp plan
distance 1.00 m → 0.50 m (`osm_site.py --relate` `boundary_gap_m`).
LEMD `--base-arm` verify quoted against `LEMD_20260907T132044` (16).

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
