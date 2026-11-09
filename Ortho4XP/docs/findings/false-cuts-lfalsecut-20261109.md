# False below-grade cuts — attribution and the below-grade witness (lane lfalsecut, 2026-11-09)

Issues #1966 (KEYW), #1972 (KDEN), #1950 (KMCI), #1961 part 1 (LFMN).  Law: owner
RULINGS 2026-11-07b (1) — a pack's below-grade intent is judged against the
AUTHOR'S ground (`geom/author_ground.py`: the pack's plate faces within
`author_ground_band_m` of the DEM, the DEM where none), never our terrain or a
placement zero.  Base origin/main 25cd0ff1b.  Every number is a planar-stage
replay of a fresh capture at that base (`tools/v2_solve_replay.py --capture ICAO`,
then the build's own `planar.build.build` with its report lines), or a read of the
pack through the build's own readers.

## Attribution

| Site (issue) | Reader that minted the cut | What it rested on | Witness it used | Why it passed | Author's-ground reading |
|---|---|---|---|---|---|
| KEYW 24.552945, -81.755451 — `tunnel_ramp` −11.49 m, 1,978 m² (#1966) | `planar/deck_bridge.deck_bridges` → `planar/deck_bores` (a hard deck bores the road under it, RULINGS 2026-10-30a (2)) → `planar/structures` tunnels `tunnel:-1834@0`, `tunnel:-1834+-1269@0` | `dsf:obj983 KEYW_07_01.obj` (the elevated road / two-level garage, `ATTR_hard_deck` roof 12.28 m over its zero, walls down to −0.12) over service roads −1834 / −1269 (no `tunnel` tag) | the airport's pavement (lot cells) facing two sides of the deck (27c) | the deck reader assumes the deck is the ground the pavement drives across, so the road under it is "deck top − frame bottom" = 12.40 m down: floor 0.91 − 12.40 = −11.48 (`deck_pin`, reported as "pinned by the pack portal") | the frame's bottom (the road it stands on) 0.70 vs the author's ground around the deck 0.81 (DEM; no plates): **0.11 m under** — the garage stands on the ground |
| KDEN 39.844361, -104.670983 — `tunnel_ramp` 6,879 m², 12.6 m fall (#1972) | `planar/structure_service.terrain_tunnel_witness` admitted bore −18906; `airport/portal_objects.read_portals` pinned its mouth | OSM −18906 `highway=unclassified lanes=6 tunnel=yes layer=-1`, 14 m long, under the toll-plaza canopy; `dsf:obj31274 Booths_Small.obj` (roof 4.99 m) over its end | §34 (12) (5) (c) "the bore carries layer −1"; the booth read as a roofed portal (#1343) | a roof between `bridge.clearance_minimum_m` 4.2 and `mouth_depth_m` 7.5 over a bore end is a portal with no ground test; floor 1631.18 − 4.99 = 1626.19, and the run-through to `@0` | the booth's bottom 1631.30 vs the author's ground around its roof 1631.43 (DEM): **0.13 m under** — a building over the road at grade |
| KMCI 39.29995, -94.71874 — 39 m² `tunnel_trench` 13 m deep (#1950) | `planar/basins.build_basins` — `basin:1` (floor 290.58, `R_est` 301.02, "covered pit; covered 95 % (own 0 %)", 2,274 m² trimmed by the wall band, 39 m² left) | `dsf:obj9756 Airport/Border/KCMO-Trimsheet-16.obj` (OBJECT_AGL 1.80; every vertex y −13.98 .. −0.93; 868 m² of near-horizontal faces at the bottom) | rule 1 floor witness: plate 10.4 m under the LOCAL ground (DEM) | rule 4: a region covered by OTHER objects' solids (95 %) is a "covered pit" and is cut | the floor 290.58 is **10.8 m under** the author's ground around it (plates over 1 % of the ring → the DEM 301.39) and ~20 m under the pack's own ground plates there (≈ 310: `concreteroad`, `darkconcretetile`, `KCMO-Trimsheet-4`, all 7–8 m over the DEM and so outside the 3 m band) — **the witness holds**: the defect is that a floor BURIED under the author's ground (95 % covered by it) is cut as an open pit |
| LFMN 43.665230, 7.209759 — `channel_floor:0#1` `tunnel_trench` 0.36 m, 14 ha (#1961 part 1) | `planar/channel.identify_channels` → `channel:0` (§45), floor datum (i) "pack" | tram ways −446 / −532 (`railway=tram`, 1,284 m) with witnesses `neck`, `pack`; pack witnesses `dsf:obj1617 terminal-1-park-01.009-O4XP.obj` and `dsf:obj1875 terminal-1-park-01.008.obj` (T1 car park, a level at y −4.29, solid 0.36) | §45 (1) (c) pack wall/floor along the corridor (deepest genuine solid 0.36 against a crest of 5.47) | both stand on the corridor (6.6 m off the way) and run along it (stations 1..83 m), so they pass (1) (c) AMENDED; the floor (3) (i) then holds 0.36 m over the whole 864 m channel, and the width is taken from the pack | the car-park level stands **4.4 m under** the author's ground (plates 4.64–4.84) — **the witness holds**, but only along the first 80 m of the 1,284 m tram way (6 %); the credible lidar (FRANCE1M) reads no cut along the rest |

## The rule (this lane): a cut stands only on a below-grade witness

`airport/below_grade_witness.py` (new; the author's-ground gathering moved out of
`airport/object_floor.py`, which imports it) builds the author's ground ONCE per
pack read and answers `depth_under(z, foot, exclude)`: how far `z` stands under the
author's ground around `foot`.  Two readers whose cut rests on an object STATING
the road under it now ask it, with `[tunnel.object] floor_sunken_min_m` (2.0) as the
threshold:

* **Hard-deck bridge** (`planar/deck_bridge._elevated`): a deck carrying a ROAD (no
  runway or taxiway across it — `deck_route.carried_route` / `_taxi_at_both_ends`)
  whose frame states the road under it (reaches `tunnel.clearance_m` under its top,
  the test `_road_floor` uses) must stand that road `floor_sunken_min_m` under the
  author's ground around the deck piece; otherwise it is an ELEVATED deck and no
  bridge.  A runway or taxiway across a deck is its own witness (an aircraft never
  climbs onto an elevated deck), and a frame stopping short of the road states no
  level (the ladder governs) — neither is asked.  Measured why: LFPG's `H*` frames
  stand their road only 2.5–9.9 m under the DEM ring and EDDF's `Bridge_2_hard_asph`
  1.66 m (a DEM that blurs the cut), while their decks carry taxiways.
* **Roofed portal** (`airport/portal_objects._at_grade`, roofs up to
  `mouth_depth_m`; taller ones keep their surveyed-cover test): its bottom must
  stand under the author's ground around its roof; otherwise it is a building over
  the road at grade, recorded as a `GradeEnd`, and §34 (12) (5) (a) refuses the bore
  that ends in it ("ENTERS A PACK BUILDING AT GRADE").

## Consumer census (CLAUDE.md, RULINGS 2026-08-30l)

| Reader | Reads | Ruling |
|---|---|---|
| `deck_bridges` (planar build, `channels`'s decision pass does not call it) | decks → `deck_bores`, the edge-deck rows, the object stage's plate, `deck_ground`, `road_overpasses` (`decks` excluded as bridges) | refused at the one derivation site: no consumer sees an elevated deck |
| `read_portals` → `TunnelObjectStats.portals` | `field_region_for` (portal ends), `end_witness`, `structure_mouth` pins, `object_floor.floor_portals`, `trench_objects` (`taken`) | an at-grade object is no portal anywhere; `grade_ends` is a new channel read only by `terrain_tunnel_witness` (a) |
| `terrain_tunnel_witness` (a) | `mouths()` only | the bore is refused before any witness of (c)/(d) |
| `basins`, `channel` pack witnesses, `sunken_roads`, `door_wells` | per-object depth against the DEM (`obj8.solid_min_depth_m`) | NOT changed this lane: KMCI and LFMN carry real below-grade witnesses (table above) |

## What moved, measured (witness OFF = origin/main's readers, ON = this branch)

Planar replays of the fresh captures (the build's own `planar.build.build`):

* **KEYW** (`/private` capture at 25cd0ff1b): `bores 2 → 0`, `object-decked trenches
  2 → 0`, `tunnels 2 → 0`.  CLOSING BUILD `build_airport.py KEYW --tile 24 -82 --tag
  lfalsecut_KEYW` (HEAD e5e226fad + the deck rule's final form, which does not change
  KEYW's road-carrying deck): rc 0, 478 s; `[KEYW] structures: bores 0`; verify rows
  17 (the app build 1.0.478 read 39, two of them `tunnel_mouth_canonical` at the
  ramp); `KEYW_auto.patch.osm` carries 0 `tunnel_ramp` / `tunnel_trench` ways (8
  before); within 40 m of 24.552945, -81.755451 the surface is 0.61..1.17 m (apron,
  service road, building pads), where the 1.0.478 patch had −11.49..0.91.
* **KDEN** (fresh capture): `tunnels 2 → 0`, `cells cut 10 → 0`:
  `tunnel:-18906@1` (the owner site, booth `Booths_Small.obj` 0.13 m under the
  ground) and `tunnel:-14318@0` (service road −14318, 39 m, `tunnel=yes layer=-1`,
  under the Peña Blvd bridges at 39.847392, -104.674056; `Train_Hider.obj`, roof
  6.0 m, bottom 0.01 m under the DEM ring; the DEM is flat 1625.8 along the road, in
  the valley the bridges cross, and the old ramp floor stood 6 m under it).  The
  booth / canopy bores −18916/−18917/−18919/−14337 were already refused and now
  carry the new reason.
* **OTHH** (frames/m12 capture, current code): bore −1355 (admitted under the
  classified cover 37.3 m) built `tunnel:-1355@1`, mouth −2.21 = DEM 3.96 − the
  roof of `OTHH_Emiri_Terminal_17.obj` 6.17, half-width 50.3 m, at the Emiri
  terminal (25.254262, 51.621295).  Both terminal parts over its ends stand on the
  author's ground (bottoms 0.60 / −0.37 m under it): the bore is now refused (a) at
  grade and that ramp is gone.  **Needs the owner's sim read** — the same class as
  KDEN (a building over a mapped `tunnel` at grade), on a case airport.
* Pack reads, decks / portals kept, OFF → ON: KEYW decks 1 → 0; KDEN portals 9 → 0;
  KBNA decks 2 → 2, portals 8 → 8; KIAH decks 5 → 5; LFPG decks 25 → 25, portals
  40 → 36 (`2A_23.obj` / `2A_25.obj` over bores −40021 / −16019 at 49.004869,
  2.577495, bottoms 0.49 / 1.03 m under the ground; the bore is already refused at
  main as entering `2A_25.obj` — no geometry change); EDDF decks 1 → 1, portals 70 → 70; KLAX decks 0 → 0,
  portals 4 → 4 (`Underpass_1/2`); HECA portals 2 → 2, decks 0 → 0; KCLT portals
  1 → 0 (`Paredes_7_charlotte.obj` over −32111, a bore the current main already
  refuses as a passage under `paredes_8_charlotte.obj` — no geometry change), decks
  0 → 0.

## Not fixed here (findings for the owner / a spec)

* **KMCI #1950**: the witness is real by every ground reading.  The cut is wrong
  because the floor is BURIED: the pack's own ground plates cover 95 % of the
  region (`basins` rule 4 counts that as a covered pit and cuts it).  The rule that
  would end it is "a floor the author's ground covers is buried, not a pit" — but
  KMCI's ground plates stand 7–8 m over the DEM (a shared-datum pack), outside the
  3 m `author_ground_band_m`, so the stand-in reading cannot see them.  That is the
  band refinement RULINGS 2026-11-07b (1) names as Beta 8 work; it needs a ruling on
  what the author's ground IS for a shared-datum pack before a reader can use it.
* **LFMN #1961 part 1**: the witness is real (a car-park level 4.4 m under the
  author's plates) but covers 80 m of a 1,284 m corridor; §45 carries its floor
  (3) (i) and its width over the whole channel.  Proposed rule (spec-level, §45):
  a pack witness witnesses only the stations its below-grade footprint stands
  along; beyond them, with a credible lidar reading no cut, the channel ends (or is
  refused when the witnessed run is under `corridor_min_length_m`).  Part 2
  (terminal pads) is a different mechanism and was not taken.
