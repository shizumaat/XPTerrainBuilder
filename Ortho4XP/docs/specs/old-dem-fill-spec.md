# Old-DEM fill: the graded ground is built up to the runway as an embankment

Owner RULINGS 2026-11-06a (2), #1915 (15:34Z, "Yes to both"): when the DEM
is older than the airport (it sits well below CIFP-stood runway ends or the
field elevation), the graded surface is built up to the runway as FILL (an
embankment), never pulled down to the DEM. Spec first; it meets the runway
cap yield and the adjacent-ground law. With 2026-11-06a (1) (the CIFP pair
stands when it agrees with the field, landed on `claude/fhshfill` 701c1b2a9).

FHSH is where the defect was found and the closing test; the rule reads
every airport (RULINGS 2026-10-05e). Lane `fhshfill`, 2026-11-06.

**Status: IMPLEMENTED on `claude/fhshfill2` (lane `fhshfill2`) after the
owner's answers, RULINGS 2026-11-06b (3)-(5); §8 records what was built and
where it departs from §2.** §0-§7 are the spec as stopped.

## 0. What the build shows now (site numbers first)

Build `fhshfill_r1` (rule (1) in, this branch at 701c1b2a9; body
`e40494375ba7`, artifact ledger `ac93195c2928`); capture registered
(`tools/harness/frames.py list FHSH`, lane `fhshfill`, base 701c1b2a9).

| reading | before (1.0.472, scout) | after rule (1) |
|---|---|---|
| 01 (02) threshold vs CIFP 303.89 m | 251.01 m (DEM pin) | 303.93 m |
| 19 (20) threshold vs CIFP 308.76 m | DEM | 308.82 m |
| runway ends, apt.dat | 247.3 / 319.9 m | 302.68 / 310.49 m |
| runway mid / peak | 3.7 % ramp | 316.41 m / 317.08 m at s 1042 m (field 311.20 m) |
| centreline grade | 3.7 % (cap yielded) | 1.39 % over the first quarter, 1.53 % over 30 m at s 115 m; cap 1.25 % not yielded; stage 1 reports the hard set INFEASIBLE (185 rows, 2.48 m shortfall, `rulesets.runway.end_zone`) |
| apron vs field 311.2 m | 268-271 m | 309.5-317.4 m |
| runway z - DEM | | +90.1 m at the 01 end, -8.7 m at mid |
| census | | CRITICAL motion 0; CRITICAL visual 28 (16 cliffs, worst 91.88 m over 51.5 m, adjacent_ground_step in the 01-end strip at -15.9667297, -5.6464522); law-true 1,001; adjudicated 954 (airside 914) |

The runway now stands on CIFP. Its strip does not: at the 01 end the
adjacent ground falls from the runway (302 m) to the pre-fill Dry Gut floor
(200-210 m) inside 50 m. The strip vertices there carry no law row (replay
`--why-at -15.96696244534,-5.64644520959`: "no row binds the vertex — the
objective holds it"), so the ground datum (`[design] ground_datum`, a weak
`z = DEM` row, §23) puts them on the 2010-2014 valley floor. This is the
lawful 08t reading ("cut and fill are unbounded, the blend happens INSIDE
the zone, beyond it the terrain") on a DEM that is no longer the ground.

## 1. The witness: FILL

A station of an adjacent-ground region's PAVEMENT SIDE (the `seed` that
`planar/zones.zone_regions` already hands `clip_to_terrain_edge`: the
pavement union for zone 1, its lip for zone 2) is a FILL station when the
pavement there stands more than `runway_ends.grade_disagree_m[class]` above
the DEM (lidar 1.5, fine 4, coarse 12 m): further than the DEM's own class
can be wrong. The pavement level at planar time is the runway's stood pin
line (the `RunwayEnd.threshold_elev_m` / `pin_along_m` the load resolved;
2026-11-06a (1)); the DEM is the airport's sampler.

The FILL FOOTPRINT is the part of the adjacent ground whose nearest
pavement-side station is a fill station.

Measured FHSH (coarse class, 12 m), strip ring 75 m off the axis, 60 m past
each end:

* 01 end and the first ~190 m of both sides: pavement-side depth 12-90 m,
  strip-ring depth up to 101.9 m (s -60 m, 19 m west of the axis). FILL.
* 19 end: pavement-side depth -3 to +3 m (the runway sits on the DEM there;
  CIFP 308.76, DEM 311.66). NOT fill, although the strip ring 60 m past
  the end stands 30-69 m over the DEM: that is the natural fall toward the
  sea cliff, and §19's crest stays the edge there. The witness is the
  pavement side, never the ring, exactly so this case is not filled.

## 2. The rule

(1) **No crest inside the fill.** `clip_to_terrain_edge` takes the fill
footprint in `not_crest` (the parameter #1201 added for walled plates): the
crest the DEM shows there is buried ground. Single site: `planar/zones.py`
at the existing call (the union with `plate_near`).

(2) **No DEM datum inside the fill.** `solve/design_ground.ground_datum_vertices`
leaves out every vertex inside the fill footprint: the DEM there is no
witness of the ground (09g (1)'s interior-pocket rule, "the DEM is
overridden there", extended to old ground). The zone's own law rows and the
bending term hold it at the law level off its pavement; nothing pulls it
down. Pavement is unchanged (no DEM pull, 08t (1)).

(3) **The FILL BANK.** Beyond the adjacent ground's kept outer ring, at
every fill station, a bank face at `[design] bank_slope` (1:3, the ruled
embankment slope, 09-09e) runs outward along the ring's normal to its
DAYLIGHT point: the first station `t >= bank_min_width_m` where
`z_ring - bank_slope * t <= DEM(t)` (the 09-09 daylight line; RULINGS
2026-09-09 (2)). The face is a new planar region of role `fill_bank`
(family `none`, side `airside`, bend class `strip`), split into radial
quads one ring station wide (station spacing = the ring's own vertices,
at most `fill_bank.station_m`, default 10 m) so the emitted faces carry
the fall line as constrained edges (§3). Its rows: per bank vertex v, the
one-way bank row `z_v >= z_p - bank_slope * |v - p|` led by its ring vertex
p (`follows = v`: the bank follows the strip and never pulls it, the
collar precedent `constraints/platform._bank_rows`); its TOE vertices carry
the ground datum (`z = DEM`, the toe is on current ground). Width: no cap
of its own up to `fill_bank.max_width_m` (default 400 m, a safety bound; a
toe that never daylights stops there and is reported by name, as 09-09 (2)
did at its 200 m). Measured FHSH at 1:3: toe 94-214 m out at the 01 end,
152-192 m along the first 190 m of the west side.

(4) **What the bank never crosses.** Pavement or another adjacent-ground
region (it ends where they begin); water (the shore cut `zones.py` already
applies); a tile-seam band (seams stay locked to the DEM, 2026-11-03e
(22); family `bank_across_seam`); and a ROAD — see §7 Q1. Where it is
stopped short of daylight, the stop is the patch edge and the step is
reported (as 09-09 (2)).

(5) **The runway cap yield and the adjacent-ground law.** Unchanged
consumers: the runway profile keeps its pins and no DEM pull; `runway_yield`
(§50) reads the pins, which now agree with each other (0.31 % over
1,550 m), so nothing yields (report: `cap_yield.yielded False`, cap 1.25 %).
The zone law (zone 1 / zone 2 transverse, the end corridors' longitudinal
rows, `strips.py`) is not re-fit: it simply has no DEM to blend to inside
the fill, and its outer ring becomes the bank's crest.

## 3. Emittable in a heightfield mesh

Yes. Every face is single-valued in plan; the steepest face is the bank at
1:3 (18.4 deg). The toe ring is the patch's open edge and lies ON the DEM,
so the patch meets the mesh with no step (the 2026-11-03e (16) 0.5 m bar is
met by construction). The interior: the mesh values a patch face's free
vertices harmonically, which squeezes a wide bank against its shorter ring
(measured HECA 2026-09-09: 111 % against an authored 33 %); the bank is
therefore emitted as radial quads (§2 (3)), each bounded by two fall-line
edges whose altitudes are linear, so the harmonic field across a quad is
the ruled bank. The mesh-side bank annulus (`O4_Bank_Annulus`,
`bank_foot` rings) is NOT used: it needs a closed foot ring offset from the
whole coverage (a 5 m bank round every patch, the 13cw costs: 337 ring
nodes moved up to 9.22 m) and its shared-segment hazard is the 09t hang.

## 4. Consumer census (RULINGS 2026-08-30l)

Static reading of every reader of `graded_strip` / `zone_regions` /
`ground_datum_vertices` / `ground_roles` (36 engine files) and the census
law support. A NEW role keeps the bank out of every `graded_strip` reader
that must not see it; only the rows below read the fill footprint or the
new role.

| # | reader | reads | rule |
|---|---|---|---|
| C1 | `planar/zones.zone_regions` -> `planar/terrain_edge.clip_to_terrain_edge` | crest cells | `not_crest` gains the fill footprint (§2 (1)); the ONE derivation site of the footprint is a new `planar/fill_footprint.py` |
| C2 | `solve/design_ground.ground_datum_vertices` | ground vertices reaching the outer boundary | minus the fill footprint's vertices (§2 (2)); `why` reads the same function |
| C3 | `solve/design_assemble` step 7 | datum rows | unchanged code; fewer rows |
| C4 | `planar/overlay.py`, `planar/build.py` | regions -> faces | the `fill_bank` region enters like a zone region (after the zones, before the overlay's noding) |
| C5 | `constraints/zones.zone_bands`, `constraints/strips.py`, `constraints/end_lip.py`, `constraints/runway_chord.py` | `graded_strip` faces | unchanged (the bank is not `graded_strip`) |
| C6 | `constraints/` new `fill_bank.py` | `fill_bank` faces | the one-way bank rows of §2 (3), the `_bank_rows` pattern (a new family member, not an append to `platform.py`) |
| C7 | `law/precedence.toml [roles]`, `law/families.toml` | role vocabulary | `fill_bank = { family = "none", side = "airside", value = false }`; ROLE-LITERAL hazard (blast) — one new literal, registered in both |
| C8 | `solve/design.py` `_bend_class`, `solve/rows._zone_weights` | bend class | `strip` (so `ground_roles` includes the toe for its datum) — C2 then excludes the footprint, not the bank |
| C9 | `constraints/water.py` GROUND_ROLES, `planar/shore.py` | ground rings at the coast | the bank is clipped at water before it is a region (§2 (4)); `fill_bank` added to GROUND_ROLES so a bank that reaches the shore is decided by the shore verdict like a zone |
| C10 | `planar/road_yield.py`, `airport/road_ramp.py`, `constraints/road_ramp.py`, `emit/road_join.py` | ground a road meets | §7 Q1 decides; until then the bank stops at the road edge (11-04a (8)) |
| C11 | `constraints/runway_profile`, `constraints/runway_yield` | pins, the ridge | unchanged (§2 (5)) |
| C12 | `emit/osm_adapter` | faces -> ways | `fill_bank` faces are ways with `role=fill_bank`, `aeroway=apron` like every ground role (the precedence `aeroway`); the toe ring is the patch's outer ring |
| C13 | `tools/check_grade.py`, `tools/harness/law_support/grade_law.py`, `strip_seam.py`, `verify/strips.py` | `graded_strip` shapes | unchanged for `graded_strip`; a new census family `fill_bank_slope` (the bank steeper than `bank_slope` + materiality) registered in `LAW_FAMILIES` and `families.toml` (the `test_harness` twin fails otherwise); the census's §31 (7) CLIFF test already treats 1:3 as the design surface's own bank |
| C14 | `verify/cutback.py`, `pipeline/late_stage.py`, `pipeline/band_road_wall.py` | `graded_strip` | unchanged |
| C15 | `planar/wall_slope.py`, `planar/deck_bridge.py`, `planar/structure_underpass.py`, `planar/lidar_road.py` | `graded_strip` near structures | unchanged; a bank never enters a structure corridor (it ends at any region, §2 (4)) |
| C16 | the sidecar | records | `fill_bank` per region: stations, toe width min/median/max, stops (seam / water / road / max width) |

Build time: the footprint is one DEM read per pavement-side station and
the daylight walk one per bank station (FHSH: 148 fill stations x <= 200
samples); well under 1 % of the 60 s budget. An airport with no fill
station builds byte-identically (C1/C2 no-ops, no bank region).

## 5. Law keys (no number in code)

* `runway_ends.grade_disagree_m` — reused as the fill witness (§1).
* `[design] bank_slope`, `bank_min_width_m` — reused (§2 (3)).
* new `[fill_bank] station_m = 10.0`, `max_width_m = 400.0`.

## 6. Twins and the closing test

Synthetic (the `test_runway_end_pins` one-runway fixture): a runway 60 m
over a plane at one end and on it at the other -> (a) the footprint covers
the high end only; (b) no crest cut there, the crest kept at the other end
over a synthetic cliff; (c) no datum row in the footprint; (d) the bank
toe on the plane at `depth / bank_slope` (+- one station); (e) an airport
with no fill builds byte-identically. Closing build: FHSH, reported as §0
plus bank width at the 01 end and the census `fill_bank_slope` rows.

## 7. Questions for the owner

**Q1 (blocks §2 (4)): a road under the fill.** Two OSM service roads (ways
-32, -33) run across Dry Gut 110-300 m beyond the 01 (02) end, on the
2010-2014 valley floor at 212-261 m. The 1:3 fill under the runway end
reaches 94-214 m out, so the roads lie inside it, up to ~60-90 m under its
surface. RULINGS 2026-11-04a (8) says a bank stops at a road edge and
slopes down beside it, never across it; here that stands a 60-90 m wall at
the road. (a) A road inside an old-DEM fill footprint is under the fill:
the bank runs over it and the road is graded only where it leaves the
footprint (it is pre-construction ground the OSM still maps) —
recommended; (b) 04a (8) holds: the bank stops at the road, the wall
stands; (c) the road rides on the bank's surface at its own grade law.

**Q2 (sibling defect, not in 06a (2)): the runway climbs over the old
hill.** With CIFP standing, the runway still rises to 317.08 m at mid
(s 1,042 m), 5.9 m over the field elevation 311.20 m. The airside it meets
is levelled off the DEM's pre-construction hill (DEM 325 m at mid; the
runway trend target is off by up to 46.5 m; aprons 309.5-317.4 m), so the
runway climbs 1.39 % over its first quarter (cap 1.25 %; the hard set is
reported INFEASIBLE, 185 rows) to reach it. The cut is 06a (2)'s mirror:
the real airport was cut through that hill. An aerodrome's elevation is by
definition the highest point of its landing area. (a) Where the DEM
predates the airport (§1's witness), no runway or airside level may stand
above the field elevation plus the DEM class's tolerance: the trends yield
to it — recommended; (b) leave the trends as they are.

## 8. As built (lane `fhshfill2`, RULINGS 2026-11-06b (3)-(5))

ONE derivation site, `airport/old_dem_fill.attach`, called by the loader
right after `end_pins.verify`.  It wraps the airport's DEM sampler
(`FillDem`): every reader of the ground — the end area (`model/end_area`),
the terrain edge, the zones' datum (`dem_z`), the road profiles, the pack's
object reads, the workers (`dem_shared`) — reads the ground AS BUILT.  An
airport with no fill station is returned unchanged.

* **Witness** (§1): the stood pin line more than `grade_disagree_m[class]`
  over the DEM on the centreline; the run extends, per half of the band,
  while the pin line stands over the DEM on the centreline or that half's
  edge.  A sampler of no stated class is no witness (end_pins' rule).
* **Crest**: each run's half-band, `zone2_half_width_m` + half the runway
  width from the centreline (the zone is measured off the runway CELL's
  edge, which a pack may draw off the apt.dat centreline; under-covered,
  the zone ring hung over the embankment), run out over the end area at a
  fill end, at the pin line's level.
* **Fill surface** `F = max(DEM, C)` inside the footprint; `C` the highest
  of the crest's cone and every terrace's cone at
  `zones.adjacent_ground.old_dem_fill_slope` (0.667, 1V:1.5H, PROPOSED).
  The crest's cone is shadowed past a terrace road and steepens to land on
  a terrace closer than the slope allows (the straight face from the
  crest's edge to the kerb): the strip keeps its width, the road its level.
* **Terraces** (2026-11-06b (4), Q2): a mapped road with a dip inside the
  crest's cone holds its LOWER RIM over that dip — the lower of the highest
  ground along the road behind and ahead (where it meets undisturbed ground
  on its lower side), flat while it wraps the fill; a road ending on another
  road's terrace takes that level as its rim (junction).  This replaces
  "exits of the cone", which moved with the slope and the RSA (FHSH: road
  -33 at 255/244 m with 1:2, 238 m with 1:1.5).
* **End area**: a terrace station ahead of a fill end sets the end area
  back to where the embankment from the end's level reaches it (+ half-width
  + stand-off).  Read by `model/end_area` off `F` (the drop is the
  embankment's top) — no change to that module.
* **Bank** (§2 (3)): `planar/fill_bank` — the footprint less the zones
  (welded), the cells / ribbons / keep-outs (stood off) and the water, as
  `graded_strip` pieces with ref `fill_bank:<k>` (DEVIATION from §2 (3)'s
  new role `fill_bank`: the wall-slope precedent, no new role literal; the
  zone law binds nothing to it, the census's `adjacent_ground_step` does not
  read it).  NOT split into radial quads (§3): the drawn faces are ruled
  between crest ring and toe ring (FHSH 1:1.9-1:2 drawn).
* **Toe**: `constraints/fill_bank.fill_toe_pins` pins every bank-only
  vertex on the patch's open edge at `F` (the DEM at the toe, the terrace
  beside a road) — the weak datum alone left the toe 3.2 m off the DEM.
* **Ceiling** (2026-11-06b (5), Q3): with a fill, `F` inside the airside
  envelope (every runway band + end areas, every pavement) is cut to field +
  tolerance, falling back to the DEM at the fill slope.  No hard row: at
  FHSH the ceiling is 323.2 m and the runway peaks at 317.0 m, so it binds
  nothing there.
* **Q1** (2026-11-06b (3)): `_field_vouches` already requires rule (b)
  (701c1b2a9); twin `test_a_flat_airports_equal_pair_is_untouched`.

Not built: the radial quads (§3), a census `fill_bank_slope` family (§4
C13), the tile-seam stop (§2 (4)), the per-region sidecar record (C16; the
load report carries `old_dem_fill`).
