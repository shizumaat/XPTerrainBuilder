# v2 — tunnel wall objects, round 2: ground-referenced ramps inside the walls (spec, 2026-09-04)

Owner sim read of OTHH on app 1.0.285 (RULINGS 2026-09-05n), five items, all
of them law:

1. The ramp's MOUTH is at the FULL DEPTH of the wall object; the other end
   of the ramp reaches GROUND at the END OF THE WALL — or beyond it where
   the ramp law (`[tunnel] ramp_max_grade`) needs more length.
2. The trench never extends beyond the OUTSIDE of the walls, and follows
   the walls' CURVES.
3. A tunnel ramp is still built wherever OSM says there is one, objects or
   not.
4. The TOP of the wall objects is FLUSH with the surrounding terrain,
   never below ground.

Author: session (Fable). Implementer: lane `v2tunnelobj2`. Supersedes the
round-1 spec's §3.2–3.4 (hull rectangle, seat floor, plate/DEM crest);
its §3.1 signature (with the lane's two amendments) stands.

## 1. Measured on 1.0.285 (OTHH_20260904T204014, the round-1 product)

| placement | kind / elev | anchor | mesh under anchor | rendered plate | ground |
|---|---|---|---|---|---|
| six +5 m objects | `OBJECT_AGL −3.0` | inside its own hull, on the trench floor | 0.96 | **2.96** (1.0 m BELOW ground) | 3.96 |
| tunnel1 ×2 (+9.55) | `OBJECT_AGL −7.0` | inside the hull | −3.04 | **−0.49** (4.4 m below) | 3.96 |

An AGL placement is rendered relative to the MESH at its anchor; round 1
cut the trench under the anchor to the seat, so the wall sank by exactly
the cut. The pack's AGL offsets are the author's guess at a mesh that no
longer exists — they are not a datum. The datum is the OBJECT'S OWN
GEOMETRY referenced to the GROUND: plate = ground, floor at the mouth =
ground − plate height (5.0 m; tunnel1 9.5 m), which is the round-1 spec's
depth reading the owner confirmed and v1's `bore_datum_m` 5.1 within
0.1 m. Round 1's hull rectangle (e.g. "135 × 45 m" for a curved 27 m
carriageway) is why the trench overran the walls.

## 2. Law (TOML; every constant a named key)

`structures.toml [tunnel.object]` — replace `floor_datum` / `crest`:

```toml
plate_datum        = "ground"      # the wall's top plate is FLUSH with the ground at the wall (05n-4); the object is re-seated to it
mouth_depth        = "plate"       # floor at the mouth = ground − plate height (05n-1: "full depth of the wall object")
ramp_end           = "wall_end"    # the ramp reaches ground at the far end of the wall, extended beyond it only where ramp_max_grade needs the length (05n-1)
trench             = "inner_walls" # trench = the region between the walls' INNER faces, following their curves; the wall band = each wall's own plan footprint (05n-2); never a hull rectangle
wall_face_max_thickness_m = 2.0    # a wall solid's plan thickness; thicker plan solids are decks/slabs, not walls
wall_sample_m      = 2.0           # station spacing along a wall line
mouth_end          = "bore"        # the deep end = the end whose axis continues into an OSM tunnel way (bore); else the end facing the other placement of the same family; else the closed end
reseat             = true          # the re-bake seats every tunnel-object family so its plate sits at the ground (delta = ground − rendered plate); never excluded
```

Precedence stays `["object", "osm"]` but is applied PER MOUTH (§3.4).

## 3. Mechanism (`airport/tunnel_objects.py`, `planar/structures.py`,
`planar/structure_geometry.py`, `constraints/structures.py`,
`airport/rebake_plan.py` / `emit/rebake.py`)

1. **Wall lines.** From the object's genuine solids (the `ResourceCache`
   geometry), the WALL solids are the components whose plan footprint is
   a thin band (`wall_face_max_thickness_m`) spanning the skirt depth.
   Each wall's plan footprint (heading-rotated, placed) IS its wall band;
   its inner edge (the side facing the other wall) is a polyline sampled
   every `wall_sample_m`. Two walls → the trench = the polygon between the
   two inner lines closed at the ends; the corridor AXIS = the midline.
   One wall (a half object, `[a]`/`[b]`) → its band only, the trench from
   the OSM carriageway width on the wall's inner side. NO rectangle
   anywhere.
2. **Ends.** The deep end (MOUTH) per `mouth_end`; the other end is the
   GROUND end. `tunnel1` (two placements, 700 m apart, headings 23° /
   293°) resolves through the bore each faces.
3. **Profile.** Floor at the mouth = ground(mouth) − plate height. From
   the mouth toward the ground end the floor climbs at
   `min(ramp_max_grade, needed)` where `needed` = depth / wall length
   along the axis; if `needed > ramp_max_grade` the ramp continues beyond
   the wall end at `ramp_max_grade` along the OSM approach way (existing
   `_ramp_top` / `ramp_targets`, `max_ramp_length_m` refusal). Inside the
   walls the floor is the ramp — no flat trench at the seat. The wall
   band's crest = the ground at each station (09-03b), both edges.
4. **Precedence per MOUTH.** An OSM bore mouth inside an object's trench
   or band is the object's (its OSM ramp is not built); a mouth outside
   every object keeps its OSM ramp exactly as before (05n-3). A bore
   covered by an object at one end only therefore ships an object ramp
   at that end and an OSM ramp at the other. Report per bore.
5. **Re-seat (05n-4).** `rebake_plan` no longer excludes tunnel-object
   families; each family's unit is seated so that its rendered plate
   equals the ground at the wall band (`delta = ground − (mesh(anchor) +
   agl + plate_y)`), through the existing coalition / `min_delta_m` gate
   (the plate is a structure datum: exempt from the 1 m threshold like
   deck seats — `deck_seat_threshold_exempt` generalised to
   `structure_seat_threshold_exempt`). Provenance names the delta per
   object.
6. **Log line** per corridor: `floor@mouth <z> ground <z> depth <d> m
   ramp <L> m (inside walls <L_w> m, beyond <L_b> m) grade <g> % ends
   mouth=<bore id|family|closed> ground=<…> walls <n> reseat <delta>`.

Consumer census (owner 30l): the `Tunnel` product keeps its fields; the
trench polygon and wall bands replace the round-1 U-polygon at ONE site
(`structure_geometry`). Every reader (`constraints/structures`,
`ramp_targets`, basins' structure cells, `verify/structures`, emit roles,
publication sidecar, rebake) is listed in the report with its effect
BEFORE the first edit.

## 4. Acceptance (ONE representative airport = OTHH)

- Twins (`test_tunnel_objects.py` extended): a curved two-wall synthetic
  object (walls as arcs) → trench between the inner lines, no vertex of
  the trench outside the walls, wall bands = wall footprints; a wall too
  short for the depth at 4 % → ramp beyond the wall end at exactly
  `ramp_max_grade`; mouth chosen by the bore; a bore covered at one end
  keeps its OSM ramp at the other; re-seat delta = ground − rendered
  plate for an AGL −3.0 placement under a cut floor.
- OTHH `build_airport.py OTHH --engine v2`: per corridor the log line
  above; floor at each mouth = 3.96 − 5.0 = −1.04 (tunnel1 −5.59); the
  trench polygon within the wall footprints (assert in the build: max
  trench-vertex distance outside the inner wall lines 0.0 m); the two
  owner sites 25.2715296,51.6022683 / 25.2556192,51.6080938 quoted as
  floor / band / ground; the OSM-only ramps that stand (05n-3) named;
  re-seat deltas per placement (expected +1.0 m for the six, +4.45 m
  for tunnel1); census 0/0; v2-verify 0.
- LEMD `--base-arm` byte-identical.
- Build-time statement; the wall-line extraction over 10 signatures must
  stay under the 0.6 s line with the signature pass.

## 5. Out of scope

Roofs / covered sections between two object ramps (the OSM bore between
them is covered ground exactly as today), and any change to the deck
reader.
