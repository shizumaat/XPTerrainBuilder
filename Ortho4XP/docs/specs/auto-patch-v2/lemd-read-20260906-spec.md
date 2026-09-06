# v2 — LEMD read on 1.0.288: basin at shapeID 970; curved edge-wall tunnel at 1088 (spec, 2026-09-06)

Owner (RULINGS 2026-09-06c): LEMD "looks quite good" (object seating right —
the Aerosoft pack anchors per object; HECA's pack shares one anchor across
85 m of relief); two items. Author: session (Fable). Implementer: lane
`v2lemd3`, sequenced after `v2othh3` on its branch (same files).

## 1. shapeID 970 = building16's pad (flat at 597.40) must be a LARGE basin

Measured (offline build): the region under building16 was refused by the
04i rule-4 BASEMENT test — "38 % under its own objects' solids at or above
the ground" (basins 26/27), the pad law then flattened the footprint; a
2,025 m² "covered pit" (basin:0, floor 587.47, 10 m under the pad) was cut
beside it. Owner: the whole shape is a basin. RULED: the basement test
means WHOLLY covered — a region whose floor plate lies under the SAME
object's above-grade solids for at least `[basin] basement_cover_min`
(0.9) is a basement; anything less covered is a PIT (covered or open) and
is cut to its floor plate, the cover being the object. `max_covered_
fraction` (0.5, diagnostic) stays diagnostic. The lane measures
building16's objects (LEMD36/37: floor plates, cover fraction, the 04i
rule-4 reading) and quotes the pit's area and floor before/after; the
pad law yields inside the pit (`cuts_pads = true`).

## 2. shapeID 1088: the tunnel ramp must follow the pack's short edge walls

The pack provides edge walls (LEMD85: crest 1.18 m above the seat, 4.03 m
of skirt) around the ramp; the tunnel-object signature refused them
(`plate_min_height_m` 2.0) and the OSM bore drew a straight ramp into a
taxiway. RULED: an EDGE-WALL object — skirt below the seat ≥
`skirt_min_depth_m`, crest plate < `bore_datum_m` above the seat, no floor
plate — gives the ramp its PLAN (the curve, the width between the walls)
with the crest FLUSH at grade (05n-4); the DEPTH comes from the tunnel
law — the OSM bore's `bore_datum_m` at the mouth — since the wall does not
state it. New key `[tunnel.object] edge_wall_max_plate_m = 2.0` (below it
the object is an edge wall, above it a full tunnel wall); `plate_min_
height_m` keeps its meaning for full walls. Precedence per mouth (05n-3)
unchanged: the bore mouth inside the edge walls is the object's.

## 3. Acceptance (LEMD once, `--tile 40 -4` for the seat is NOT needed)

`build_airport.py LEMD --engine v2` once: basin 970 area/floor, the 1088
ramp's axis following LEMD85's walls (no straight chord into the taxiway;
quote the axis length inside the walls), census 0/0 or the residual named,
v2-verify by family (the 62 `tunnel_wall_top_flat` rows retire with the
band per the OTHH spec §1). OTHH `--base-arm`: unchanged basins (873/877/
879 per the OTHH spec). CYXY unchanged.
