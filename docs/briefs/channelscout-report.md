# Scout `channelscout` — evidence for the OPEN CHANNEL class
LGAV / KDFW / KPHX, read-only, 2026-09-15. Base main `c2c96419`.
Brief: `/Users/noah/XPTerrainBuilder/docs/briefs/channelscout.md`.

Every number below carries its source path. Nothing was built, downloaded or
dumped. Two things are NOT measured and are named in §7.

---

## 0. THE HEADLINE

The three sites are NOT one geometry. They are three different
*witness profiles* over the same idea:

| | LGAV | KDFW | KPHX |
|---|---|---|---|
| channel is BELOW GRADE | yes (~12 m, pack only) | **yes, MEASURED 8.6–9.9 m in 1 m lidar** | **not measurable; DEM flat to 0.1 m** |
| DEM sees it | no (30 m Copernicus) | **yes (1 m 3DEP)** | no (30 m Copernicus) |
| pack models walls/floor | **yes (Trench_0x.obj)** | no (nothing) | no (nothing) |
| OSM road carries a depth tag | no | no (1 stray `tunnel` 40 m away) | **yes — `tunnel=building_passage` ×6** |
| OSM crossing carries `bridge`+`layer` | yes (1 taxiway) | **yes (6 taxiway ways, refs A/B/Y/Z)** | **yes (2 taxiway ways, layer 3)** |
| apt.dat cuts the corridor out of the pavement | — (not read) | **yes — a 2,518 m hole, 4 paved necks** | **yes — an unpaved corridor, 2 paved decks** |
| the engine cuts anything there today | 5 `tunnel_trench` faces / 1 basin | not run (see §5) | **NOTHING: flat apron 342.2–342.9 m** |

The one thing all three share, and the only thing: **the CROSSING is
witnessed and the CHANNEL is not.** The aeroway feed keeps every tag; the
road feed keeps four. See §1a — that is a feed-schema fact, not a mapping fact.

---

## 1. THE CHANNEL IN OSM

Feeds: `/Users/noah/XPTerrainBuilderData/OSM_data/+30-100/+32-098/` (KDFW),
`+30-120/+33-113/` (KPHX), `+30+020/+37+023/` (LGAV).

### 1a. THE FEED CANNOT CARRY THE WITNESSES (new finding)

`Ortho4XP/src/O4_Vector_Map.py:48`

    ROADS_TAGS_OF_INTEREST = ["bridge", "tunnel", "width", "lanes"]

`layer`, `cutting`, `covered`, `embankment` are **dropped at download**
from `big_roads` / `small_roads` / `airport_small_roads` for EVERY tile.
The airports feed is the opposite — `("airports", AIRPORTS_QUERIES, ["all"], [], "")`
at `Ortho4XP/src/O4_Vector_Map.py:853` keeps everything, which is why
`aeroway=taxiway bridge=yes layer=1` survives and a road `cutting=yes`
could not.

Measured tag census over the corridor ways (key: value counts, ABSENT
means not on a single way):

| tag | LGAV (29 ways) | KDFW (225 ways) | KPHX (15 ways) |
|---|---|---|---|
| class | rail 18, motorway 11 | motorway 105, secondary 105, rail 15 | primary 15 |
| `tunnel` | ABSENT | `yes` 1, `building_passage` 1 | **`building_passage` 6** |
| `bridge` | ABSENT | `yes` 62 | ABSENT |
| `layer` | ABSENT | ABSENT | ABSENT |
| `cutting` | ABSENT | ABSENT | ABSENT |
| `covered` | ABSENT | ABSENT | ABSENT |
| `embankment` | ABSENT | ABSENT | ABSENT |
| `lanes` | 2–4 | 2–19 | 2–5 |

Whether OSM upstream tags `cutting=yes` on International Parkway is
UNVERIFIABLE here: it would need `ROAD_CACHE_TAG_SCHEMA`
(`O4_Vector_Map.py:59`) bumped and a re-download. Reported, not assumed.

### 1b. KDFW — International Parkway

Two carriageways, two frontage roads, all N-S, lat 32.880…32.929:
frontage `lon ≈ -97.0414` (secondary, 2–3 lanes) · SB motorway
`lon ≈ -97.04095` (3 lanes) · **median ~121 m** · NB motorway
`lon ≈ -97.03975` (3 lanes) · frontage `lon ≈ -97.0392`.

At the four taxiway crossings the road ways carry NO witness:
way `-3436` (`highway=motorway lanes=3`, lat 32.88446…32.88647) is the
SB carriageway under taxiways A and B; way `-959` is the NB one; way
`-1486` (lat 32.90865…32.91410) and `-1553`/`-16033` are the pair under
Z and Y. Plain `highway`+`lanes`, nothing else.

The 62 `bridge=yes` road ways in the band are the parkway's own ramps and
flyovers elsewhere in the corridor, not the crossings. The single
`tunnel=yes` way is `-27411` (`motorway lanes=3`, 32.89969…32.89983,
lon -97.03979 — 15 m long) and `-10735` is `tunnel=building_passage`
(32.89946…32.89958, lon -97.04099): both are under Terminal C/D
buildings, ~800 m from the nearest taxiway bridge.

**The crossings** (`+32-098_airports.osm.bz2`) — six ways, all
`aeroway=taxiway bridge=yes`:

| way | ref | layer | lat | lon span | span m |
|---|---|---|---|---|---|
| `-276` | A | 1 | 32.88502 | -97.04171…-97.04081 | 84.3 |
| `-280` | B | 2 | 32.88605 | -97.04170…-97.04080 | 84.6 |
| `-21` | Z | 1 | 32.90907 | -97.04170…-97.04057 | 105.7 |
| `-1595` | Z | 1 | 32.90908 | -97.04014…-97.03901 | 105.7 |
| `-23` | Y | 1 | 32.91010 | -97.04169…-97.04056 | 105.8 |
| `-1593` | Y | 1 | 32.91011 | -97.04014…-97.03901 | 105.5 |

Note the pairing: Y and Z each bridge the WEST cut and the EAST cut as
**two separate spans**, with the 121 m median between them carried on
solid fill. A and B are single spans over the west cut only; their east
halves are ways `-31`/`-28` (same refs, NO bridge tag) at lon -97.0392…-97.0386
which are already east of the east frontage road. **KDFW is two parallel
channels, not one.**

### 1c. KPHX — E Sky Harbor Blvd

Two E-W carriageways at **lat 33.43498** (south) and **lat 33.43591**
(north), 103 m apart.

Six segments carry **`tunnel=building_passage`** exactly where the
taxiway bridges stand: `-4248` (lanes 4, lon -112.00418…-112.00347),
`-15974` (5, -112.00481…-112.00435), `-23949` (3, -112.00505…-112.00481)
on the south carriageway; `-3936` (5, -112.00418…-112.00368), `-3937`
(5, -112.00505…-112.00435), `-23804` (4, -112.00368…-112.00348) on the
north. Combined lon extent **-112.00505…-112.00347 = 147 m**.
(A seventh, `-21840`, is a separate building passage at lon -112.0089…-112.0081.)

**The crossings**: exactly two ways, `aeroway=taxiway bridge=yes layer=3
surface=concrete` — `-111` (ref **T**, lon -112.00470, lat 33.43467…33.43600)
and `-206` (unnamed, lon -112.00383, same lat span). Span **148 m** each,
**87 m apart**. The other 24 `layer`-tagged aeroways at KPHX are jet
bridges (`aeroway=jet_bridge`), excluded by §34 (5)'s `TAXIED_AEROWAYS`
narrowing (`Ortho4XP/src/auto_patch_v2/planar/structure_underpass.py:58`).

### 1d. LGAV (comparison column, re-measured for the crossing half)

29 motorway/rail ways through the field, **no depth tag of any kind**
(table above) — the brief's fact, confirmed. But the crossing half is
NOT blind: `aeroway=taxiway bridge=yes layer=1` on way **`-379` (TWY H,
lat 37.93099…37.93149, lon 23.93909…23.93993)** and way **`-6` (TWY K,
lat 37.94364…37.94402)**. Only **1** aeroway (TWY H) actually crosses the
mapped Attiki Odos / rail axis in plan.

---

## 2. THE CHANNEL IN THE DEM

### 2a. KDFW — 1 m 3DEP, and it is a **DTM: the bridge decks are GONE**

`/Users/noah/XPTerrainBuilderData/Elevation_data/+30-100/N32W098_airport_insets/KDFW_usgs3dep.tif`
(227 MB, 12665×10134, reprojected to WGS84 geographic ≈1.19×0.99 m/px,
nodata -32768) with `..._usgs3dep.json`: provider `USGS3DEP`,
`resolution_m 1.0`, `vertical_datum NAVD88`, `valid_fraction 1.0`,
projects `TX_Pecos_Dallas_2018_D19` (4 tiles), published 2021-11-18,
fetched 2026-08-15. **USGS 1-Meter products are bare-earth DEMs (DTM).**

Transects ALONG each taxiway-bridge centreline, 5 m steps, extended 60 m
past each end (s = metres from the bridge's first node):

| bridge | span | rim at s=0 / s=span | floor min | **depth** | floor at s |
|---|---|---|---|---|---|
| `-276` A | 84.3 m | 176.98 / 176.88 (abutment mean 178.65 / 179.01) | **170.87** | **8.64 m** | 35 |
| `-280` B | 84.6 m | 176.78 / 176.16 (179.18 / 179.39) | **170.20** | **9.68 m** | 25 |
| `-21` Z west | 105.7 m | 181.72 / 182.22 (181.32 / 181.85) | **172.80** | **9.94 m** | 45 |
| `-1595` Z east | 105.7 m | 182.68 / 180.69 (181.90 / 181.21) | **173.16** | **9.58 m** | 70 |
| `-23` Y west | 105.8 m | 181.84 / 181.61 (181.45 / 182.06) | **173.27** | **9.55 m** | 50 |
| `-1593` Y east | 105.5 m | 182.76 / 180.53 (181.79 / 181.25) | **174.15** | **8.67 m** | 60 |

Two readings from the same table:

* **NO BRIDGE DECK APPEARS.** Along every one of the six spans the
  surface descends monotonically from the abutment into the cut and
  climbs out; there is no rim-level plateau anywhere over the span. The
  lidar reads the ROAD, ~9 m under the taxiway it should be carrying.
  Example, `-21` (Z west), z at s = 0,10,20,30,40,50,60,70,80,90,100:
  181.72, 179.71, 176.87, 174.03, 172.81, 174.37, 175.14, 175.32, 177.03, 179.63, 182.22.
* **THE MEDIAN IS REAL FILL.** Between `-21` and `-1595` (lon -97.04057…-97.04014)
  the DEM reads a flat **182.68–182.73** plateau over ~120 m at the Z
  latitude, but only **175.3–175.6** at lat 32.900 where no bridge stands.
  The taxiway crosses the median on an embankment that the DTM keeps.

Wall geometry: **sloped banks, not vertical walls** — ~9 m of drop over
~35–45 m of plan run (≈1:4), e.g. `-276` 178.90 @ s=-10 → 170.87 @ s=35.
Floor grade along the channel: 170.87 (A) → 170.20 (B) → 172.80 (Z) →
173.27 (Y) over 2,790 m = **+2.4 m, 0.09 % mean**, essentially level.
Wall-to-wall width = the bridge span, **84.3–105.8 m**.

Caveat recorded: a naive min/max window scan along the whole corridor is
NOT clean (drainage ditches, ramps and the terminal garages enter the
window). The six bridge transects are the defensible measurement; between
the bridge pairs the corridor is not a uniform trench.

### 2b. KPHX — Copernicus GLO-30 only, and it is **BLIND**

`/Users/noah/XPTerrainBuilderData/Elevation_data/+30-120/N33W113_airport_insets/KPHX_copernicusglo30.tif`
(244 KB, **300×216**, 30 m) + `.json`: provider `COPERNICUSGLO30`,
`native_resolution_m 30.0`, `vertical_datum EGM2008`, fetched **2026-09-15**
(today — the owner's build). A duplicate tif sits in `N33W112_airport_insets/`.
**There is no lidar inset for KPHX.**

It is a DSM with masking: `surface_model_building_masking` reports
`footprint_count 12098`, `masked_fraction 0.5635` (36,512 px), filled by
`distance_transform` — over half the inset is interpolated.

N-S transect at lon -112.00427 (between the two T bridges), lat
33.4330→33.4375, 15 m steps: **341.50, 341.50, …, 341.40, 341.49, 341.37,
341.04, 340.54, 340.21, 340.01, 339.94, 339.51, 339.50, …** — a monotone
2.0 m fall over 500 m. Zero signature of a 100 m-wide crossing or any cut.
Same class of blindness as LGAV's 77–79 m flat transect.

The engine's own read agrees: `KPHX.report.json` `load.flat_site`
`s2 {relief_m 6.46, slope 0.001954, residual_std_m 0.777, dsm_trimmed_frac 0.156}`,
`s2_source_class "coarse"`, `s2_source_pixel_m 30.0`.

**KPHX's channel geometry therefore comes from OSM + apt.dat only** (§1c, §4).

### 2c. LGAV (given)

30 m Copernicus, blind; the pack's `Trench_03.obj` VT y −12.67…+5.73 is
the only depth statement.

---

## 3. THE CHANNEL IN THE PACK

### 3a. KDFW — the pack states **nothing** about the channel

`/Users/noah/XPTerrainBuilderData/Airport_mod_cache/c_USA - 100_airport - KDFW_4_Roads (Aerosoft)/+32-098.dsf.6b192ddc.text`
(32 KB) is a **network-only** DSF: `NETWORK_DEF lib/g10/roads.net`,
149 `BEGIN_SEGMENT`/`END_SEGMENT` pairs, 280 `SHAPE_POINT`,
**0 `OBJECT_DEF`**. Every vertex elevation is **0.0 or 1.0** (two distinct
values over 578 points) — draped road vectors, no datum, no depth.
Extent lat 32.85231…32.93157, lon -97.09441…-97.00000; 10 road subtypes.

`.../KDFW_5_Scenery (Aerosoft)/+32-098.dsf.c8f5c313.text` (390 KB): 232
`OBJECT_DEF`, 2,093 placements (113 `OBJECT_MSL`), 13 `POLYGON_DEF`, 720
polygons. Inside the channel band (lon -97.0425…-97.0380, lat 32.878…32.932)
the placements are **82 jetway / dock-guidance / floodlight / small-shed
objects and 107 polygons** (89 `lib/g8/fruit_hot_wet.for` tree rows, 10
`Fence.fac`, 8 `Jet_Blast_Shield.fac`, 6 warehouse/cargo facades).
Grep of all 232 object defs for `bridge|tunnel|wall|road|ramp|viaduct|underpass`
returns **7 hits, all `lib/airport/Ramp_Equipment/*` ground vehicles**.

**There is no wall object, no floor plate, no deck object and no
retaining structure anywhere in the KDFW pack's channel band.** Depth of
the deepest vertex under the placement datum: **not applicable — there is
no candidate resource.** Roofed fraction: **not applicable.**

### 3b. KPHX — likewise nothing

`.../c_USA - 100_airport - KPHX - Phoenix Sky Harbor Intl (MisterX+Kurt)/+33-113.dsf.fcc44ad2.text`
(479 KB): 285 `OBJECT_DEF`, 4,604 placements, 75 `POLYGON_DEF`, 489
polygons. Inside the T-bridge band (lon -112.0060…-112.0025, lat
33.4340…33.4365): **28 placements** (air-conditioner units, floodlights,
gate-number signs, GSE vehicles, a fire station, the tower, two
`lib/airport/markings/roads/stop_*_bg.agp`) and **31 polygons**
(taxiway crack/seam `.lin`s, 5 `lib/airport/ground/roads/asphalt_D2/6m_center.lin`,
5 `DP_Library/.../Flat_New_Uniform.pol`, 3 `Asphalt_2_Base.pol`, one
jet-blast deflector facade, one `Barriers_white.str`). All draped ground
decoration. **No wall, floor or deck object.**

The engine confirms it independently — `KPHX.report.json`
`planar.tunnel_objects`: `resources 1, signatures 0, corridors 0,
plates 0, not_screened 211`, and the ONE refusal is

    Garage3.obj x1: roofed along its axis (125303 m2 of near-horizontal faces
    run along the corridor axis, a plate's worth: >= plate_min_area_m2 100):
    a building or a deck, not a wall skirt

— a parking garage, nowhere near the crossing.

### 3c. LGAV (given, the only pack that models it)

`Trench/Trench_0x.obj` walls + floors, a 4,077 × 149 m plate, roofed 6 %.
**LGAV is the outlier, not the archetype.** A model founded on "read the
pack's trench objects" covers one of the three sites.

---

## 4. THE CROSSINGS IN apt.dat

`auto_patch_v2.airport.apt_dat.find_apt_dat` picks the CUSTOM PACK at both
airports (both carry row-110):

| | chosen apt.dat | row-110 | rings (outer) | Global Airports block |
|---|---|---|---|---|
| KDFW | `Custom Scenery/c_USA - 100_airport - KDFW_5_Scenery (Aerosoft)/Earth nav data/apt.dat` (8,549 rows) | **1** | 1 pavement, 339-node outer + 80 holes | **57** pavements, 7 runways |
| KPHX | `Custom Scenery/c_USA - 100_airport - KPHX - … (MisterX+Kurt)/Earth nav data/apt.dat` (7,225 rows) | **7** | pav#2 "Taxiway B/C", 552-node outer | **35** pavements, 3 runways |

### 4a. KDFW — the corridor IS a hole, the decks ARE the necks

Global `pav#54` (156 rings) and pack `pav#0` (81 rings) agree. Rings that
touch the channel band:

| ring (GLOBAL / PACK) | lat | lon | nodes | what it is |
|---|---|---|---|---|
| `ring0` | 32.87149…32.92313 | -97.08297…-97.00023 | 1280 | the field |
| `ring69` / `ring80` | 32.88616…32.90893 | -97.04750…-97.03520 | 198 / 211 | **the corridor: 2,518 m × ~1,150 m** |
| `ring70` / `ring78` | 32.88513…32.88592 | -97.04577…-97.03511 | 38 / 10 | the 87 m gap **between decks A and B** |
| `ring68` / `ring79` | 32.90917…32.90997 | -97.04564…-97.03499 | 38 / 10 | the 88 m gap **between decks Z and Y** |

Ray-cast of the union pavement along the channel axis (constant lon,
lat 32.878…32.932) gives exactly **four paved necks** — the bridge decks:

| deck | GLOBAL width @ lon -97.04115 / -97.03960 | PACK width |
|---|---|---|
| A (lat 32.88488…32.88514) | **29.1 / 29.1 m** | 29.9 / 29.9 m |
| B (32.88590…32.88617) | **29.9 / 29.9 m** | 29.6 / 29.7 m |
| Z (32.90892…32.90919) | **30.3 / 30.3 m** | 30.1 / 30.1 m |
| Y (32.90995…32.91027) | **35.0 / 36.5 m** | 29.7 / 29.7 m |

**No runway crosses.** All seven KDFW runways lie east or west of the
corridor (17C/35C lon -97.026, 17R/35L -97.030, 18L/36R -97.051,
18R/36L -97.055, 13L/31R -97.021…-97.001, 13R/31L -97.083…-97.063,
17L/35R -97.010).

This is the strongest structural witness at KDFW and it costs nothing:
**the channel is the hole in the airfield pavement, and the crossings are
the necks.** It is available at every airport with an apt.dat and does
not depend on OSM, on the DEM or on a pack.

### 4b. KPHX — an unpaved corridor with two decks

Ray-cast along constant lon: at the two bridge longitudes the pavement is
CONTINUOUS across the road corridor — `-112.00470` paved lat
33.43353…33.44000 (**715 m**, pack) and `-112.00383` paved 33.43320…33.43997
(**750 m**) — while BETWEEN them (`-112.00427`) there is no pavement at all
between lat 33.4310 and 33.4387.

Ray-cast across (constant lat), pack:

| lat | deck 1 | deck 2 | gap |
|---|---|---|---|
| 33.43450 | -112.00482…-112.00457 (**23.0 m**) | -112.00394…-112.00370 (**22.4 m**) | 58 m |
| 33.43498 (S carriageway) | 23.0 m | 22.0 m | 58 m |
| 33.43545 | 22.9 m | 22.1 m | 58 m |
| 33.43591 (N carriageway) | 22.8 m | 22.2 m | 58 m |

Global Airports reads the same two decks **wider** — 42.2–42.5 m and
64.3–64.7 m — a 2–3× disagreement with the pack on deck width at the same
site. Total structure width **112 m** (pack) vs **133 m** (global).
**No runway crosses** (8/26 at lat 33.4409, 7L/25R 33.4311, 7R/25L 33.4289;
the corridor is at 33.4350–33.4359, between 7L/25R and 8/26).

---

## 5. THE ENGINE'S CURRENT READ

### 5a. KPHX — **read from the owner's OWN 1.0.340 products, not re-run**

`/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+33-113/KPHX/KPHX.report.json`
(written today, ruleset `faa`, solve **optimal**, 178 active-set rounds,
10,289 unknowns, 30,516 rows, total 73.3 s).

`planar.structures`:

    bores 5  bores_mouth_only 1  mouths 10  mouths_off_field 0
    mouths_on_approach 2  approach_corridors 6  runway_bands 3
    tunnels 2  decks 0  object_decks 0  pavement_decks 0  cells_cut 0
    object_corridors 0  door_ramps 0  sunken_roads 0  wall_corridors 0
    plate_mouths []  crest_from_approach []

**All eight mouths of the four crossing bores are REFUSED, by one rule:**

    tunnel:-4248@0 / @1  : the mouth stands against building pad building16
    tunnel:-3936@0 / @1  : the mouth stands against building pad building16
    tunnel:-15974@0 / @1 : the mouth stands against building pad building16
    tunnel:-3937@0 / @1  : the mouth stands against building pad building16

Those are exactly the four `tunnel=building_passage` ways of §1c under the
taxiway bridges. `building16` is Terminal 4's pad.

§34 (5) DID fire — `structures.underpasses`:

    underpass taxiway -206 (layer 3, deck half-width 15.0 m, clip the centreline
      ribbon 12.9 m (no cell states the deck, §34 (5) (a)),
      cell 1 read / 140 refused over 4x carriageway): 2 road(s) bored
    underpass taxiway -111 (layer 3, deck half-width 12.5 m, clip 10.4 m
      (no cell states the deck), cell 1 read / 149 refused): 2 road(s) bored
    underpass taxiway -1259 (layer 1, half-width 3.5 m, 0 cells): 0 road(s) bored
    underpass taxiway  -96  (layer 1, half-width 3.5 m, 0 cells): 0 road(s) bored

so the bores were seeded — and then every mouth was thrown away by the
building-pad test. Net effect on the surface, read out of
`KPHX.graded.json` (frame `+proj=tmerc lat_0=33.433583243 lon_0=-112.011839153`):

**every face overlapping the crossing band (lat 33.4345…33.4362,
lon -112.0052…-112.0032) is airside pavement at z 342.23…342.87 m.**
17 faces: 5 `junction`, 4 `apron`, 4 `graded_strip`, 3 `cross_connector`,
1 `building` (`building16`, 342.63…342.71). **Zero `tunnel_ramp`, zero
`retaining_wall`, zero `basin`.** The two `tunnel_ramp` faces that exist
airport-wide are 5 km away at lat 33.44798…33.44809, lon -111.98956…-111.98813
(z 346.02…349.63). Role areas: `tunnel_ramp` 1,259.9 m², `retaining_wall`
539.4 m², against `apron` 1,314,394 m². `basins` is `[]`.
`emit.published.tunnel_objects 0`, `basin_facilities 0`.

Verify families non-zero: `within_shape` 617, `taxi_box` 237,
`strip_transverse` 171, `airside_no_step` 206, `transverse` 44,
`runway_crown` 45, `pad_flat` 5, `resa_transverse` 2,
`frontage_near_miss` 2, `strip_longitudinal` 1, `strip_arc` 1,
**`tunnel_mouth_canonical` 2 (magnitude 2.00 m each, one
`retaining_wall|retaining_wall` airside, one `tunnel_ramp|tunnel_ramp`
groundside)**.

**So KPHX today: the airfield is paved flat straight over a 147 m-wide
road crossing, and the pass that should have cut it was disarmed by a
building pad.** LAW C is off for KPHX by construction
(`Ortho4XP/src/auto_patch_v2/law/airports.toml` names OTHH only —
`kerb_wall_corridors = true`, every other airport false).

Also read: `load.object_pavements` admitted **0 of 271** pack resources
(`no draped layer group` 262, `layer group markings` 6, `decorative name` 3),
`dsf_pavements 47`, `dsf_dump_stale false`.

### 5b. KDFW — **NOT RUN. Reported as owed.**

    cd /Users/noah/XPTerrainBuilder/Ortho4XP && PYTHONPATH=src \
      venv/bin/python -m auto_patch_v2.planar KDFW --out <scratch> --stage structures

Three attempts. Two were refused by the session's permission classifier
(`[Modify Shared Resources]`, triggered by the `>` redirect / background
form). The one attempt that was allowed ran to the DEM composition line

    [dem] production frame N32W098: composed: grid 11017x11017, baked_query=True,
      airports_smoothed=58, insets=… KDFW:USGS3DEP …

and was then cut by the foreground window before writing any output
(`<scratch>/kdfw_struct/` does not exist). **The engine did not refuse and
no data was cold** — the corpus resolved correctly
(`Ortho4XP/OSM_data` → `/Users/noah/XPTerrainBuilderData/OSM_data`,
`Ortho4XP/Elevation_data` → `…Data/Elevation_data`, both symlinks).

Two observations from that partial run:

* **A write attempt inside a documented read-only tool.** The run printed
  `WARNING: Could not save airport info to file
  /Users/noah/XPTerrainBuilder/Ortho4XP/Tiles/zOrtho4XP_+32-098/Data+32-098.apt`.
  The target is ENGINE-TREE-local (`Ortho4XP/Tiles`, a real directory,
  not the shared repo), so no corpus write was attempted and no guard was
  blocked — but `--stage structures` is advertised as "all READ-ONLY on
  the shared corpus" and it does try to write a tile artefact. Worth a
  line; not a contamination.
* Statically, §34 (5) WILL fire at KDFW: `is_aeroway_bridge`
  (`Ortho4XP/src/auto_patch_v2/planar/structure_underpass.py:58`,
  `TAXIED_AEROWAYS = {"taxiway","runway","apron"}`) matches all six
  `aeroway=taxiway bridge=yes` ways of §1b. What the building-pad mouth
  test then does at DFW (Terminals A–E flank the corridor on both sides,
  exactly as Terminal 4 does at KPHX) is the open question.

### 5c. LGAV (given)

Every pass refuses the Trench objects: basins "a shell through the ground"
(4.46 m above ground > `contact_band_m`); sunken roads "roofed over 6 %
(< `roof_min_fraction` 50 %) — an open ramp"; tunnel objects "roofed along
its axis / roof, not a crest / skirt under 0 %"; wall corridors "law off
for LGAV". Planar minted 5 `tunnel_trench` faces (3,885 m²) + 6
`retaining_wall` + 2 `tunnel_ramp` + 1 basin (`Trench_08.obj`, floor 69.66)
against ~4 km × 100 m.
Source: `/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+37+023/LGAV/LGAV.report.json`.

---

## 6. WHAT THE SIM SHOWS TODAY

**KDFW: there is no KDFW patch, and the last recorded build FAILED.**
`/Users/noah/XPTerrainBuilderData/Patches/+30-100/+32-098/` holds patches
for KCPT, KFWS, KGDJ, KGKY, KGPM, KINJ, KNFW, KWEA — **KDFW is absent**.
`…/auto_patch_verify_debug.log` (246 lines) records:

    === KDFW build FAILED (build) ===
    auto_patch.elevation_per_surface.building_feasibility.BandInversionError:
    KDFW: the FINAL reach band is INVERTED at 650 node(s) of 19818
    band-covered node(s) (floor − ceiling > 0.01 m).

(KAFW failed in the same run.) The tile `+32-098.dsf` in
`/Users/noah/X-Plane 12/Custom Scenery/zOrtho4XP_+32-098/Earth nav data/`
is dated **2026-08-15 20:18** — i.e. **the KDFW the owner can fly today
has NO auto-patch at all**: the channel there is whatever the raw 1 m
3DEP mesh gives, which per §2a is a 9 m open cut with no decks.
There is no `tmp/auto_patch_v2/+32-098/` directory.

**KPHX: mid-build.** `/Users/noah/X-Plane 12/Custom Scenery/zOrtho4XP_+33-113/`
has `Data+33-113.mesh` (174 MB, 07:49), `.alt`, `.node`, `.poly`,
`o4_levelled_roads.json` (46 MB, 07:46) written today, and
`Earth nav data/` with no `.dsf` yet. The v2 products quoted in §5a are
in place for both tile halves (`+33-113` and `+33-112`).
`o4_levelled_roads.json` header: `grade_cap 0.08`, `ways 44988`,
`stations 628260`, `clamped_stations 33957`, **`deck_pinned_ways 0`,
`deck_pinned_stations 0`, `deck_pins_refused 0`** — the v1 road leveller
pinned nothing to any deck in the whole tile.

---

## 7. WHAT I COULD NOT VERIFY

1. **KDFW §34 (5) / structures replay** — §5b. The command is quoted; it
   needs ~5–10 min of foreground budget and a Bash permission that the
   classifier will not refuse.
2. **Whether OSM upstream carries `cutting` / `layer` / `covered` /
   `embankment` on these roads** — impossible from the cached feeds
   (§1a); would need `ROAD_CACHE_TAG_SCHEMA` bumped and a re-download,
   which is an explicit `--refresh-data` event, not a scout's act.
3. **Whether KPHX's road is actually below grade.** The 30 m DEM says
   flat to 0.1 m and there is no lidar inset; `tunnel=building_passage`
   asserts a structure overhead, NOT a cutting. On the evidence in hand
   the KPHX channel may be an AT-GRADE road under an elevated deck, which
   is a materially different member of the class than LGAV and KDFW. This
   is the intent question for the owner (§8).
4. **The KDFW pack's `.obj` geometry** was not opened: there is no
   candidate resource to open (§3a), so no vertex depths are quoted.
5. **KPHX's own `+33-112` half** was listed but not read in detail; the
   crossing lies wholly inside `+33-113`.
6. The `dsf:polNN` refs in `KPHX.graded.json` were NOT resolved back to
   the pack's `POLYGON_DEF` indices — the statement "the crossing is
   paved apron" rests on the graded faces' roles and z, not on which
   pack polygon minted them.

---

## 8. THE ONE INTENT QUESTION

**Is the class "a road in a CUTTING under a deck" or "a road UNDER a
deck, cutting or not"?** LGAV and KDFW are cuttings (12 m / 9 m). KPHX
has the best OSM witness of the three (`tunnel=building_passage` ×6) and
no measurable cutting at all. If the model requires depth evidence, KPHX
is out of the class and the two decks should simply be taxi pavement over
an at-grade road. If the model is "a deck states a crossing", KPHX is in
and the depth is a free parameter the crossing's own geometry supplies.
The measurement that would settle it is a 1 m lidar inset for KPHX
(3DEP covers Maricopa County) — an explicit `--refresh-data dem` event,
not a build side effect.

Secondary, and cheaper: **the apt.dat hole is the channel footprint**
(§4a/§4b), available at all three sites without OSM, DEM or pack. Neither
the tunnel pass nor the underpass pass reads it today.
