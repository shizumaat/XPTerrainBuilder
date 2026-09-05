# v2 — tunnel wall OBJECTS as the tunnel authority (spec, 2026-09-04)

Owner ruling 2026-09-05k-1 (OTHH read on 1.0.284): the pack's tunnel wall
objects define a tunnel's **shape, length and depth**. Reading confirmed by
the owner: **the placement seat is the tunnel floor; the object's top plate
is the wall crest.** Author: session (Fable). Implementer: lane
`v2tunnelobj`. Law: `src/auto_patch_v2/law/structures.toml`.

## 1. The evidence (measured 2026-09-04, OTHH Doha (Aeroscape), DSF dump
`+25+051.dsf.e9df4ffc.text`)

| resource | placements | plan extent (x × z, m) | solids y | crest plate |
|---|---|---|---|---|
| `Objects/tunnels/tunnel west 1.obj` | 1 | 39 × 44 | −15 → +5 | +5.0 (314 m²) |
| `tunnel west 2.obj` / `tunnel west 3.obj` | 1 + 1 | 223 × 44 | −15 → +5 | +5.0 (529 / 523 m²) |
| `tunnel_sw.obj` | 1 | 105 × 33 | −15 → +5 | +5.0 (272 m²) |
| `tunnel middle - east.obj` | 1 | 117 × 80 | −15 → +5 | +5.0 (312 m²) |
| `tunnel middle - west.obj` | 1 | 59 × 190 | −15 → +5 | +5.0 (441 m²) |
| `tunnel1.obj` | 2 | 16 × 250 | −10 → +9.5 | +9.5 (529 m²) |

Plate = near-horizontal solid faces (|n_y| ≥ 0.7) binned at 0.5 m; the
single bin per object IS the crest. No plate below the seat (the basin pass
already refuses them: "genuine solids reach −18 m … NO floor plate — a
skirt, not a pit"). Today v2 derives OTHH's 8 tunnels from OSM bores at
`[tunnel] bore_datum_m = 5.1` (mouth −1.14 under DEM 3.96): correct depth
for the +5 m objects by coincidence, **wrong for `tunnel1` (9.5 m)**, and
the bore's length/half-width are OSM estimates ("top 168 m half 11.2 m")
where the object states them.

## 2. Law (TOML first — no constant in Python)

`structures.toml`:

```toml
[tunnel.object]                     # RULINGS 2026-09-05k-1
source_precedence   = ["object", "osm"]   # an object tunnel REPLACES every OSM bore its footprint covers; OSM bores stand only where no object does
floor_datum         = "seat"        # the placement seat (OBJECT_MSL absolute; OBJECT/OBJECT_AGL = production DEM at the placement + elevation)
crest               = "plate"       # crest = seat + the object's top plate height (NOT the DEM: the object states the wall)
skirt_min_depth_m   = 3.0           # genuine solids must reach this far BELOW the seat for a wall skirt (OTHH: 10–15 m)
plate_normal_y_min  = 0.7           # reuse of deck_plate_normal_y_min: a crest face is near-horizontal
plate_bin_m         = 0.5           # crest plane = the largest-area bin of plate faces at or above the seat
plate_min_area_m2   = 100.0         # below this the object is not a wall (a bollard, a kerb)
plate_min_height_m  = 2.0           # crest must stand this far above the seat (a 0.3 m kerb is not a tunnel wall)
floor_plate_max_m2  = 0.0           # any floor plate below the seat disqualifies (that is a basin — basins.py owns it)
hull_min_length_m   = 10.0          # the plan hull's long side; shorter is a stub, refused loudly
end_cap_open_m      = 2.0           # a hull end with no solid within this of the end line is an OPEN end (a mouth); a closed end is a dead wall
merge_gap_m         = 3.0           # two object hulls whose open ends face within this are ONE corridor (tunnel1 × 2)
```

Every key is read through `law/model.py` (a `TunnelObject` dataclass under
`Structures.tunnel`), validated by `law/tables.py`, and registered in
`tests/auto_patch_v2/test_law_tables.py` (no numeric literal in Python).

## 3. Mechanism

New module `src/auto_patch_v2/airport/tunnel_objects.py` (≤ 400 lines):

1. **Signature.** For each resolved DSF placement (the `ResourceCache`
   already parsed for basins — reuse its `ObjGeometry` / `solid_components`,
   never parse twice), a *wall skirt* is: genuine solids reaching ≤
   −`skirt_min_depth_m` below the seat plane (y = 0 in object space), a
   crest plate (per §2) at ≥ `plate_min_height_m`, area ≥ `plate_min_area_m2`,
   and no floor plate below the seat. Everything else is not a tunnel object
   (buildings, basins, decks keep their own readers).
2. **Footprint.** The plan hull of the object's solid vertices (x, z) →
   rotated by heading, placed at the placement's frame xy (`obj8.placement_
   affine`) → a `Polygon` in the airport frame. Length / width = the rotated
   rectangle's sides (`model.frame.rotated_rectangle`). The corridor AXIS is
   the rectangle's long axis; ends are classified open/closed per
   `end_cap_open_m`. Hulls whose open ends face each other within
   `merge_gap_m` merge into one corridor.
3. **Datums.** `floor = seat elevation` (MSL absolute, or DEM(placement) +
   AGL); `crest = floor + plate height`. Depth = plate height (5.0 / 9.5 m).
4. **Precedence.** An OSM bore (`planar/structures.py::_chains`) whose axis
   intersects an object corridor's footprint is DROPPED (stats: `bores_
   replaced_by_object`); the object corridor takes its place in the SAME
   `Tunnel` product that `build_structures` already emits (trench cells at
   the floor, wall band `wall_band_width_m` at the crest, `wall_gap_m`, ramp
   climbing from each OPEN end at `ramp_max_grade` to the DEM through the
   existing `_ramp_top` / `ramp_targets`, using the OSM approach ways for the
   ramp centreline where they exist, else the corridor axis extended).
   Closed ends get no ramp.
5. **Crest law.** For object corridors `crest = "plate"`: the wall band's
   inner and outer edges carry `floor + plate height`, one value per station
   (the 09-03b "crest = DEM" law stays for OSM bores — two sources, ONE
   `Tunnel` product, the crest a per-tunnel field, never a second emitter).
6. **Re-bake.** A tunnel wall object is a STRUCTURE: its anchor family is
   excluded from the re-seat like a basin family (`[rebake] basin_family_
   excluded` extended to `structure_family_excluded`), and it is listed in
   the plan under `skipped.tunnel_object`.
7. **Log line** (the `[v2] [ICAO] structures:` block): per corridor
   `tunnel-object:<resource>@<n>: floor <z> crest <z> depth <d> m length
   <L> m width <W> m ends open/closed replaced bores [<ids>]`.

Consumer census (owner 30l — every pass that reads tunnel geometry) is in
`planar/structures.py` (cells cut, `ramp_targets`, deck intervals),
`constraints/structures.py`, `verify/structures.py`, `emit` (roles
`tunnel_trench` / `tunnel_ramp` / `retaining_wall`): all read the `Tunnel`
product, none read the source — the table in the report must say so per
consumer before the first edit.

## 4. Acceptance (ONE representative airport = OTHH; build economy)

- Twins (`tests/auto_patch_v2/test_tunnel_objects.py`): a synthetic OBJ8
  text (two parallel wall slabs −12 → +5 with a 400 m² crest plate, no
  floor) is a skirt; a box with a floor plate is refused; a 0.3 m kerb is
  refused; the two-placement merge; an OSM bore under the hull is replaced;
  the seat/plate datums; the law-table register.
- OTHH through `build_airport.py OTHH --engine v2`: the structures line
  reports 7 object corridors (tunnel1 × 2 merged or reported as one 500 m
  corridor — state which), depths 5.0 × 6 / 9.5 × 1, the OSM bores they
  replace named; census 0/0 (oracle); the owner's sites 25.2715296,51.6022683
  / 25.2556192,51.6080938: wall crest = plate height above the floor, ramp
  mouths at the open ends.
- LEMD (no wall objects) byte-identical patch body (`--base-arm`) — the
  one OFF-arm build a shared-structures change earns.
- Build-time statement: the OBJ8 parse is already paid (38 s at OTHH,
  cached by `ResourceCache`); the signature pass must add < 0.6 s or the
  Fable-5 review is owed.

## 5. Out of scope

Objects without a crest plate (open-top skirts), tunnels roofed by decks
(the deck reader stands), and any change to the 09-03b DEM-crest law for
OSM bores.
