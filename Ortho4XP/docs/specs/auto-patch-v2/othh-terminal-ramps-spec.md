# v2 — OTHH terminal: door ramps and the sunken road under the building (spec, 2026-09-08)

Owner (RULINGS 2026-09-08b): "spots where the object extends below
ground, at least one slightly depressed tunnel under the building, and
several basement access doors that need a small ramp going down to
them." Measured by scout `othhterminal` on `OTHH_20260907T125006`
(flat site Z0 3.962, every plate depth = metres under ground). Author:
session (Fable). Implementer: lane `v2doorramp`, AFTER `v2trenchgap`
merges (same files).

## 1. Measured (the scout's read; KML sent to the owner)

* SIX basement access wells whose floor plate reaches the car parks'
  exterior face: sills −1.57 … −1.70 m, wells 3.7 × 1.5 m (Parking-
  Left/Right ×4), 3.8 × 2.4 (VCN_003), 5.2 × 4.8 (Terminal_Parking_006);
  nearest at-grade OSM road 22.8–41.4 m. v2 emits NOTHING: they are
  under `basin.admission_depth_m` 2.5 (obj8.py:648-650) and never a
  witness.
* TWO sunken road ramps (`TerminalRoads_03_000` / `02_000`): floor
  plates 2,368 / 2,288 m², 183 × 22 m, from the mouth at grade down
  3.09 / 3.18 m (1.7 %), then the underground road to −11.5 m; roofed by
  the viaduct decks (`03_002` / `02_002`). Refused by the tunnel-object
  pass as "roofed along its axis" (tunnel_objects.py:305-316) and by the
  basin pass (`through_grade` / `no_floor`, obj8.py:662-673, 742-756);
  no OSM tunnel way runs along them; v2 emits nothing — flat terrain
  3.96 over a floor 0.56–3.65 m under it.
* Two genuine BASEMENTS under Bridge_01 (basins 8/10, own cover 1.00):
  correctly refused (basins.py:337-345) — unchanged.
* The terminal proper's "spots": four −0.17 m slivers of Terminal_Base_2_1
  (6.7 / 2.2 / 2.2 / 1.6 m²) — below every gate; unchanged.

## 2. Law A — DOOR RAMP (`structures.toml [cutout.door]`)

Where a below-grade floor plate of an object REACHES ITS EXTERIOR FACE
(the plate boundary leaves the object's own at-grade geometry,
obj8.py:801-833 — a door, not a basement), cut a trench of the sill's
width from the sill up to grade at the ramp grade, OUTSIDE the building
only, along the outward normal of that face. Keys: `sill_min_depth_m =
0.5` (its own gate, separate from the 2.5 m basin gate), `sill_min_width_m
= 1.0`, `ramp_grade = 0.08` (a 1.70 m sill → 21 m; the pack's own
geometry implies ≥ 7.5 % — the nearest road is 22.8 m away — the
owner's "small ramp"), `max_length_m = 25` (a ramp that would cross an
at-grade road or pavement STOPS at it and steps — report the case).
The trench floor = the sill plate ⊕ `floor_overlap_m`; the rim = 08a's
`rim_inset_m` inside the well's walls; the ramp is a `tunnel_ramp`-class
structure face (precedence.toml) with `seat = "none"` — the door groups
NEVER re-seat the anchor family (basins.py:392-400 `seat =
"floor_plate"` would move all 35 members of unit:22): members standing
> `contact_band_m` under the mesh are facility members and keep their
authored y (structures.toml:169, emit/rebake.py:382-391).

## 3. Law B — SUNKEN ROAD under the building (`[cutout.sunken_road]`)

A floor plate below the seat that is ROOFED (today's refusal) whose
plate reaches within `contact_band_m` of the ground at one end is a
sunken road: the mouth is that end; the trench = the plate ⊕
`floor_overlap_m` along the axis, the floor = the plate's own y per
station (the 1.7 % descent), cut only to `max_depth_m = 4.0` (deeper is
the underground road — the terrain stays); rim inside the wall (08a);
the building/deck above untouched (the roof is the object). A third
signature class in `airport/tunnel_objects.signature` beside full/edge
wall; `planar/object_corridor.object_groups` (:119-162) takes the depth
per station from the plate, `climbs = False` at the deep end;
`basins.py`: a plate whose depth VARIES and reaches grade is a ramp,
never a basement (`basement_cover_min` applies to level, closed plates
only). `seat = "none"` likewise (unit:26's 399 members stay).

## 4. Consumer census (owner 30l) — the lane writes the table before
editing: `obj8._witness` / `at_grade_geometry`, `basins.py` (the
basement branch exempts door reaches and varying plates),
`structure_geometry.py` ramp rings, `structures.py` group builder
(`_pad_hit` :445 must not refuse a door ramp against its own pad — it
starts at the face by construction), `object_corridor.py`,
`precedence.toml`, `emit/rebake.py` facility rule, `verify/structures.py`
and the oracle's structure readings, `flat_site.py` (structure faces are
already excluded from the flat datum), the census.

## 5. Twins and acceptance

Twins: a box with a 1.7 m well reaching its face → one door ramp of the
sill width, 21 m at 8 %, rim inside the well walls, the anchor unmoved;
the same well under the roof → basement, nothing; a roofed descending
plate reaching grade → sunken-road trench to 4 m, floor along the plate,
anchor unmoved; a level roofed plate → basement. ONE build: `OTHH
--engine v2 --tile 25 51` (the seat is post-mesh): the six wells and
the two ramps emitted (quote each: floor z, rim, length), verify 0,
census 0/0, `objects moved: 0` for units 22 and 26 (the owner: no object
modifications), LEMD/CYXY `--base-arm` unchanged.
