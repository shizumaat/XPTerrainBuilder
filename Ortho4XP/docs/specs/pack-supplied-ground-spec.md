# Pack-supplied ground (issue #1362) — witness, consumers, owner question

Status: DRAFT for ratification (RULINGS 2026-08-30l consumer census). No consumer edited.

## 1. Measured (PAKT, the installed pack, its `.anchor_bak` DSF)
- 20 pack-local objects in `terrain/` share ONE authored anchor (one `OBJECT` lon/lat/heading,
  AGL, no MSL): a rigid set. `terrain.obj` is 4,884 triangles, ALL `ATTR_hard`, transparent
  texture: the invisible collision ground. Its plan union is 1.227 km2 and covers 100.0 % of the
  apt.dat runway rectangle (104,500 m2); its y runs -1.8..37.8 m (sea level to the field).
  `base_01..06` are the visible textured ground on the same footprint; `_runway_*`/`_asphalt*`
  are `ATTR_poly_os` decals on it; `stones_*` the shoreline riprap.
- Our rebake split the set into 27 placements on 10 anchors (`obj8_split`, object-placement
  §4/§6). Each body is AGL, so each drapes on our ground under its OWN anchor: the set is no
  longer rigid.
- The owner's point (55.353885, -131.701416) is 103 m OUTSIDE the hard ground (offshore of the
  riprap). The patch's way -10024 there is `runout:1` (classify/ramp_runout): a 9,248 m2
  road-grade strip at 22.5-23.3 m over water, 0 % inside the pack ground.
  Attribution (INFERRED, not replay-confirmed: the PAKT capture ran >30 min and was stopped): `ramp_feet` reads the hard ground's shoreline
  embankment as an object ramp coming down to its own zero, and the run-out leaves it to sea.
- The companion HD mesh the manual names is not installed; nothing machine-readable in the
  airport pack declares it (only the manual's text).

## 2. The witness (geometry only, no names)
A pack-local object, or the set of pack-local objects that share one authored anchor, IS THE
PACK'S GROUND when its plan-bearing `ATTR_hard` triangles (`obj8.ObjGeometry.hardness == HARD`,
`_plan_bearing`) cover at least `[pack_ground] runway_cover_min` (proposed 0.5) of the airport's
apt.dat runway area. Rationale: X-Plane rolls aircraft only on the terrain mesh or on hard
object surfaces; a hard surface under the runway is the ground the pack flies on. A taxiway
bridge plate or a helipad never covers half a runway. The SET is everything on that anchor.
"Companion mesh present": `terrain_mesh_witness.read` finds one (coverage, never a name).
"Companion missing": pack ground witnessed AND no companion found. Not witnessable: whether the
pack *requires* a mesh (the manual is prose) — the engine can only say it found none.

## 3. Consumer census (each consumer's rule, ONE table)
| consumer | today | rule under pack ground |
|---|---|---|
| `airport/rebake_plan` + `obj8_split` | splits into bodies, re-anchors each | never split; the set keeps its one anchor, seated rigid (MSL = the anchor height at which the set's hard runway meets apt.dat elevation) |
| `airport/ramp_feet`, `classify/ramp_runout`, `planar/landing_runout` | reads the hard ground as a deck ramp | the pack ground is no ramp: no feet, no run-outs from it (fixes the owner's site) |
| deck readers (`obj8.hard_deck` callers: `deck_bridge`, `overpass_deck`, `structures`) | hard plate may read as a deck | the pack ground is no deck/bridge — for the deck-redesign lanes (files off limits here) |
| design solve (sheet, pavement) | grades to DEM/OSM pavement | inside the ground footprint the mesh stands `[pack_ground] under_m` below the hard surface (no z-fight, no gap); pavement there follows it |
| `constraints/water` + mesh water masks | water vertices pinned to water | inside the footprint water is land (as patch pavement over water is a deck) |
| road / runout emit | emits OSM and minted roads | no minted road over the footprint; mapped roads ride the hard surface |
| `companion` / `terrain_mesh_witness` | companion found by coverage | present: its mesh is the ground under the set, our patch defers to it there |
| engine events + Mac/Qt build box (#1244) | — | "companion missing" notice (new event: wire-protocol pair) |

## 4. Owner question
With the witness above and no companion mesh installed, should the engine (A) grade its own
mesh to stand just under the pack's hard ground (water under it becomes land; our mesh plays
the missing mesh's part) and only show a notice that no companion mesh was found, or (B) warn
before the build and offer "build anyway / skip this airport's patch"?
Recommendation: A, with the notice. The witness lets us build what the mesh supplied; a
blocking choice gives the user nothing to act on except installing a pack we cannot name.
