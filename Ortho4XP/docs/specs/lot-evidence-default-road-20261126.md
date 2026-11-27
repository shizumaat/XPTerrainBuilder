# A lot only on evidence; groundside pavement defaults to road (#2283, 2026-11-26)

Owner 2026-11-26T23:48Z: "We should identify a narrow 'neck' where a road leaves a lot, and classify it
as road, so the roads can grade and ramp correctly. Probably we should default to road, and only go to
the more strict lot grading when we have more evidence to be sure an area is a lot." 23:49Z: "Approved
airports will likely change, but hopefully for the better." Extends RULINGS 2026-11-25e; replaces the
§110 lot default (2026-09-30b remark) and the 04u "a road reaches it" lot rung.

**L1. Lot evidence (the only way to `parking_lot`).** E1 OSM `amenity=parking` over
`[lot] parking_cover_fraction` of the page; E2 an OSM `service=parking_aisle` inside the page; E3 at least
`[car_lots] min_cars` of the pack's parked-car objects seated on the ground on the page (or on the face, for a
face with no page; owner 2026-11-16p "use cars to identify lots"). Minted lots keep their own evidence
(`carlot:` cars, `faclot:` facades, §53 slab lots, the blast-pad lot, a user override). NOT evidence: a road
reaching the page (04u), road centreline inside it, a compact shape, or nothing at all (§110). Shape is
refused as a witness on purpose: EKVG `dsf:pol23` is a compact-looking ring road (rectangle aspect 1.9).

**L2. The default road.** Groundside pavement with no lot witness is a road: the road-law plate
`groundside_pavement` (10 % along, 2 % across, the road cap of 2026-10-07d); a non-page face (11ac demotion,
04u open default) with ribbon proportions stays `service_road` as §110 had it. A source page is never
re-kinded by shape here: `sources`' strip rungs already answered strip-or-lot for it. One derivation: `classify/open_default.unclassified_groundside_role`
(`lot_evidence=`), called by the page branch, the 11ac demotion, the 04u open default, the reachability
demotion and the planar beyond-pieces. The face carries `default_road` (`Face.default_road`, groundside only).

**L3. The neck.** Where an evidenced lot narrows to road width (§43 at the road width,
`classify/neck.road_necks`), the pavement from the neck on is graded as road (25e (2): road cap rising with the
ground to the steep cap 20 %, 2 % lateral) — `pipeline/lot_neck`, unchanged, now over evidenced lots only. A
default-road plate needs no neck: it is road law already.

**L4. Grade, not structure.** The default road follows its ground (25e (2)) like a lot (25e (1)): the
weak `z = DEM` datum (`model/lot_ground._follows_ground`) within its own cap. In the planar ARRANGEMENT it
stands as the lot it was (`planar/overlay.cell_region` gives its region `parking_lot`): landing and collar
cuts, fills, low levels, foot kerbs, pad rims and every other planar pass read it unchanged, and the map face
alone takes the road role (`planar/build`). MEASURED: read as a road in the arrangement, EKVG's landings went
uncut (pad `building5` 2.46 m) and BIKF's pads were re-cut (45 new vertices).

## Consumer census (every pass reading the lot class / region; derivation site = `open_default` + `roles`)

| pass | reads | default road (was `parking_lot`) | change |
|---|---|---|---|
| `law/rulesets.toml` caps; `verify/within`, census | role cap | 10 % / 2 % (road) | **intended** (L2) |
| `emit.toml` §37 (6) ramp contacts `extra_roles = parking_lot` | lot as ramp foot | not a contact: a road leaving it does not ramp at 5 % | **intended** (EKVG v2331-2336 bound here) |
| `airport/road_profile` (road family minus `parking_lot`; reads faces) | prefers the core profile | prefers it (road) | **intended** |
| `model/lot_ground` datum, `pipeline/lot_follow`, `solve/design_assemble` | lot follows ground | follows (`_follows_ground`) | extended (L4) |
| `pipeline/lot_neck` (`is_datum_lot`) | necks of lots | evidenced lots only | trimmed (L3) |
| every planar region reader (`landing_cut`, `platform` fills/low levels, `foot_kerb`, pad cut, rim snap) | region role | `parking_lot` (`cell_region`) | kept: map vertex-for-vertex identical (EKVG, KEGE, BIKF) |
| `planar/structure_mouth` host edge (reads cells) | lot host | still the plate (`default_road` mark) | kept |
| `classify/airside_edge` §27 flip | lot vs born road | groundside_pavement / `road_by_proportions`: the lot's rule | unchanged |
| `law.tables.LOT_ROLES` (lot roads 14a (2), car lots, verify lot chord) | both roles | both roles | unchanged |
| `constraints/agp_plate` P3, `model.planar.ROAD_ROLES` | lot vertex / road roles | road (excluded as roads are) | follows L2 |
| `roles._road_evidence`, `taxi_shoulder`, `pad_relief`, `pad_frontage_gs`, `groundside`, `bridge_span`, `road_ramp` | any groundside plate | same reading | unchanged |
| user role editor (`airport/user_roles`) | user override | wins over both | unchanged |

**Residual (lane llotroad replays).** BIKF: 9 apron vertices ≤ 0.19 m beside pads `building12/13/23`
(≤ 0.25 m): stage 1 solves the same rows; the pads' stage-0 prefix solve reads the plate's hard rows at the
road cap. Refuted there (no effect, deleted): the lot cap on stage-1 pairs of a default road; no profile axis
for a default road.
