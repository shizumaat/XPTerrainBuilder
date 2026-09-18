# Scout `hecachannel` — WHY §45 minted two channels that should not exist
### HECA `channel:2` + LEMD `channel:5`, both from app 1.0.348

Base main `ef8377a0`. Read-only: no edits, no builds, no worktree. Every number is read verbatim
out of a shipped product, a cached feed, a pack DSF dump, an inset raster, or the source.

---

## 0. THE ANSWER IN ONE PAGE

The owner's question is the WHY. There are **two different admitting errors**, both in §45's
witness reading, and neither one touches a real apron channel:

**HECA `channel:2` — an ABOVE-GROUND STRUCTURE READ AS A BELOW-GRADE SOLID.**
Three placements of `Airport/Jetway/EGCC_Jetway_metal_03.obj` — passenger airbridges, 90 m off
the road — supplied §45 (3)(i)'s "pack" depth witness. The floor value is reproducible to 3 mm:

    DEM(30.110831521, 31.402840085) = 101.597 m      <- dsf:obj2786's seat
    EGCC_Jetway_metal_03.obj lowest VT y = -4.2753 m  <- the model's own below-origin geometry
    101.597 - 4.2753 = 97.321                         vs declared/emitted floor 97.324 m

The jetway's rotunda-column stub, modelled below its own origin so the bridge reads flush on any
apron, is read as 4.28 m of "genuine solid under grade" against `object_min_depth_m = 3.0`. That
one reading (a) supplied the floor, (b) set the corridor half-width to **92.0 m** (the jetway's
own off-axis offset) where the road is 7.0 m wide, and (c) — decisively — flipped the datum from
`clearance` to `pack`, which is the **only** thing that let `channel:2` past the guard that
refused its five siblings. The owner's instinct was exactly right about the KIND of error; it is
the jetways, not the elevated railway (which is in neither the OSM feeds nor the pack — §3).

**LEMD `channel:5` — A ZERO-LENGTH DECK COUNTED AS A CROSSING, then a FLOOR THAT CLIMBS WITH NO
CEILING.** Its two "crossings" are `channel_deck:5#0` (way -5828, s 450-470, real) and
`channel_deck:5#1` (way **-5832, s0 = 0.0, s1 = 0.0** — zero length, pinned at the axis origin by
`LineString.project`'s clamp, because way -5832 does not run along the axis at all). That
degenerate deck is what satisfies `min_decks_without_depth = 2`. It then also plants a floor
anchor at s = 0, and §45 (3)(iii)'s implementation — `min` over upward cones at 8 % with **no
upper clamp at the road's own §37 profile** — produces a Λ, peaking **+11.90 m ABOVE the DEM**
at s ≈ 211: the owner's "large hill, the opposite of a trench".

**Neither error is present in a real channel.** LGAV `channel:0` (the Attiki Odos trench) carries
`Trench/Trench_07.obj` + `Trench/Trench_08.obj` — purpose-built 2 km trench-wall models at the
corridor edge — and 4 positive-span decks. VHHH `channel:0` (a real apron channel, the owner's
own example) carries **no pack witness at all** and 3 positive-span decks. Both survive every
refinement in §7.

---

## 1. WAY -13192 (HECA)

**Feed and tags.** `airport_small_roads`, way `-13192`, **`highway=service` and nothing else** —
no `tunnel`, `bridge`, `layer`, `covered`, `cutting`, `name`. 69 nodes, 2,840 m long (the record
reads `axis 2836 m`).

    /Users/noah/XPTerrainBuilderData/OSM_data/+30+030/+30+031/+30+031_airport_small_roads.osm.bz2

Read with `Ortho4XP/tools/osm_site.py … --dump -13192`. Single un-merged way:
`channel_facilities[0].ways == [-13192]`, note `1 way(s) within [channel] merge_m 40 m share the
corridor` (`/Users/noah/XPTerrainBuilderData/Patches/+30+030/+30+031/HECA_auto.patch.osm.axes.json`).

**ID COLLISION.** `id="-13192"` also exists in `+30+031_big_roads.osm.bz2` and
`+30+031_water.osm.bz2`. The channel's way is the `airport_small_roads` one. This is the
collision `channel.way_key` exists for (`Ortho4XP/src/auto_patch_v2/planar/channel.py:106-121`);
the HECA sidecar publishes the **bare** id, so a downstream reader joining on `-13192` can land
on the wrong way. (VHHH's `structures.json` does publish `way_keys`; the patch sidecar does not.)

**Course.** A service-road ring. Node 0 `30.1113717,31.4038703` (between the piers), NW along the
terminal frontage to `30.1161194,31.4022295` (~s 900), back SE past `30.1141308,31.4041615`, east
to `30.1114291,31.4069831` (~s 1500), then S/SW to `30.1084756,31.4032704`. The channel takes
**s = 0…1990 m** (`notes[0]`: `ends 0..1990 m`). Corridor polygon area **366,466 m² (36.6 ha)**,
bbox lat 30.1081313-30.1169416, lon 31.3990226-31.407972.

**Relative to the pavements** (`osm_site.py … --contains` on the emitted patch): it runs through
airside pavement the whole way. Owner site 3 (`30.1153948,31.4011451`) is INSIDE
`tunnel_trench:channel_floor:2` (way -11374); site 2 (`30.1120743,31.4075856`) is INSIDE
`feature:structure_rim:channel_wall:2` (way -11941); site 1 (`30.1118669,31.4078138`) is 0.01 m
outside the wall ring, inside apron `dsf:objpav99`.

**Is the real road mapped `tunnel=yes`, and why is -13192 not among the 12 excluded?** The real
underpass area IS mapped — on OTHER ways:

| way | feed | tags | at |
|---|---|---|---|
| -21860 | small_roads | `highway=service, tunnel=yes` | 30.11253,31.39739 |
| -20638 | small_roads | `highway=tertiary, tunnel=yes` | 30.11277,31.39749 |
| -13108 | small_roads | `highway=tertiary, tunnel=yes` | 30.11275,31.39740 |
| -13189 | small_roads | `highway=service, tunnel=building_passage` | 30.11194,31.40069 |
| -13245 / -13249 / -13252 / -12198 | small_roads | `highway=service, tunnel=building_passage` | 30.1099-30.1106, 31.3957-31.3985 |

§45 (13)(b)'s hard claimed set is built in `planar/channel_claims.crossing_claims`
(`Ortho4XP/src/auto_patch_v2/planar/channel_claims.py:65-67`) from `is_tunnel(w,
tn.admitted_values)`, and `admitted_values = ["yes"]`
(`Ortho4XP/src/auto_patch_v2/law/structures.toml:11`). So the `building_passage` ways — including
**-13189, which runs along -13192's own course at 30.1122,31.4009** — are not in the exclusion
set either. -13192 carries no `tunnel` tag at all and is excluded by nothing.

I reproduced **11** `tunnel=yes` road ways inside `radius_deg = 0.05`
(`Ortho4XP/src/auto_patch_v2/airport/load.py:68`) against the report's `12 way(s) excluded`; the
12th almost certainly comes from a neighbour tile's feed (`load_feed` reads the 3x3
neighbourhood) — see §9.

**A THIRD, INDEPENDENT DEFECT FOUND HERE.** `+30+031_airport_small_roads.osm.bz2` (written
2026-07-27) carries **no `o4_tag_schema` attribute at all**, while `+30+031_big_roads.osm.bz2`
(2026-09-15) carries `o4_tag_schema="2026-09-15"`. In
`Ortho4XP/src/auto_patch_v2/airport/load.py:349-354` a feed with `schema is None` goes to
`untagged` and is only *recorded*; only `schema != ROAD_CACHE_TAG_SCHEMA` **refuses**. The
1.0.348 report confirms:

    load.osm_road_feeds_untagged = [".../+30+031_airport_small_roads.osm.bz2 (airport_small_roads)"]
    load.osm_road_feeds_stale    = []

HECA's small-roads feed was therefore read under the pre-§45 (9) whitelist: `layer`, `cutting`,
`covered`, `embankment` are missing from every small road at this airport, and §45 (1)(d) cannot
fire here. **A strictly older, unstamped feed gets a weaker gate than a stamped one.**

## 2. THE THREE PACK PLACEMENTS (HECA)

Read off the pristine dump
`/Users/noah/XPTerrainBuilderData/Airport_mod_cache/c_EGY - 100_airport - HECA Cairo (Tai Models)/+30+031.dsf.anchor_bak.a636e364.text`
(3,436 placements) through the engine's own `airport/dsf.read_dump`; ids are `dsf:obj{i}` with
`i` the placement index (`Ortho4XP/src/auto_patch_v2/airport/load.py:471`). The sidecar names
them: `channel_facilities[0].walls[*].witness == "dsf:obj2786,dsf:obj2787,dsf:obj2788"`.

| id | resource | lat, lon | heading | kind | DEM (bilinear) | DEM − 4.2753 |
|---|---|---|---|---|---|---|
| dsf:obj2786 | `Airport/Jetway/EGCC_Jetway_metal_03.obj` | 30.110831521, 31.402840085 | 196.674754 | OBJECT | 101.597 | **97.321** |
| dsf:obj2787 | `Airport/Jetway/EGCC_Jetway_metal_03.obj` | 30.110619326, 31.403913939 | 196.674754 | OBJECT | 103.518 | 99.243 |
| dsf:obj2788 | `Airport/Jetway/EGCC_Jetway_metal_03.obj` | 30.111345560, 31.404116598 | 313.098650 | OBJECT | 103.452 | 99.177 |

**What they are: passenger airbridges.** `EGCC_Jetway_metal_03.obj` is the Taimodels Manchester
jetway asset
(`/Users/noah/X-Plane 12/Custom Scenery/c_EGY - 100_airport - HECA Cairo (Tai Models)/Airport/Jetway/EGCC_Jetway_metal_03.obj`,
19,302 VT). Its y range is **-4.2753 … +11.0939 m**; 6,109 vertices below -1 m, 1,681 below -3 m.
These are the only three `.obj` jetways in the whole tile — the pack's other 48 jetways are
`.agp` (`HECA_Jetway_No_glass.agp` x23, `HECA_Jetway_No_glass_green.agp` x25).

**Is 97.32 a genuine below-grade solid? No.** It is the model's own below-origin geometry — the
fixed rotunda column and wheel-bogie stub, sunk under the apron plane so the bridge reads flush
on any surface. Nothing is dug there. `_depth_under_crest`
(`Ortho4XP/src/auto_patch_v2/planar/channel.py:326-347`) takes obj8's `solid_min_depth_m` against
the LOCAL terrain, so the jetway reads **≈4.28 m under grade against `[channel]
object_min_depth_m = 3.0`** (`Ortho4XP/src/auto_patch_v2/law/structures.toml:381`) — it clears
the gate by 1.28 m.

`channel_floor.channel_floor` (`Ortho4XP/src/auto_patch_v2/planar/channel_floor.py:60-72`) then
takes `min(solid_min_z)` over the set and emits a **two-station, dead-flat profile**
(line 68: `profile = tuple((s, floor_pack) for s in (ss[0], ss[-1]))`) across all 1,990 m. The
sidecar: `floor_declared_min_m == floor_declared_max_m == emitted_floor_min_m ==
emitted_floor_max_m == 97.324`, `emitted_floor_count 609`.

**The same three objects set the WIDTH.** `channel_geometry._walls_half`
(`Ortho4XP/src/auto_patch_v2/planar/channel_geometry.py:330-346`) takes the maximum across-axis
offset of the witnesses' below-grade footprints. The axis is a 2.8 km ring and a jetway stands
~92 m off it, so the record reads `corridor half-width 92.0 m from pack walls (10) (i) …
carriageways ⊕ lane_width_m reads 7.0 m here`. **One jetway 92 m off-axis widened a 7 m road into
a 184 m trench.**

## 3. THE NECK AND THE DECK (HECA) — and the owner's elevated railway

**One deck**, `channel_deck:2#0`, way -13192, `datum "design"`, `s0 1870.0 … s1 1930.0` — 60 m
along the axis, i.e. `30.1094792,31.4046543 -> 30.1091331,31.4041767` (midpoint
`30.1093062,31.4044155`; stations computed from the way's own node chain).

**What it really is:** the service road crossing **taxiway `pav65` at grade**. At the deck
midpoint `osm_site.py --contains` reads exactly one covering ring:

    INSIDE  cross_connector:pav65  rings=1  ways=-10173     (aeroway=taxiway, code_letter=E, shapeID 174)

with `pav111` (`secondary_parallel`), `pav1#1` (`junction`) and apron `dsf:objpav97` within 26 m.
The "paved neck across an unpaved corridor" is a **taxiway that a service road crosses** — plain
HECA geometry, not a bridge over anything.

**THE ELEVATED RAILWAY IS NOT THE DECK AND NOT A PACK WITNESS.** Checked at the owner's
coordinate `30.1155738, 31.4000159`:

* **Not the deck.** The deck stands ~700 m SSE of the rail point and its ring is taxiway `pav65`.
  The record carries `witnesses ["neck","pack"]` with **no `bridge` witness**, so the deck cannot
  have come from §45 (1)(a)'s `aeroway_decks` path — a viaduct could not have produced it.
* **Not in OSM.** No railway way exists within 80 m of the rail point in any of the three cached
  feeds. Nearest ways: `highway=tertiary` (-22352, 64 m), `highway=service` (-20624 / -13121,
  29 m), `highway=secondary` (big_roads -1227 / -1223, 35 m).
* **Not in the pack.** The 21 placements within 150 m of the rail point in the pristine dump are
  16 x `lib/street/streetlights/ResidentialLight_01V2.obj`, 2 x `Airport/T23/Apron_Type1.obj`,
  2 x `SAM3_Library/marshaller/marshaller_high.agp`, 1 x `Lib_Making/Passenger/bus.obj`.

**But the owner's DIAGNOSIS is exactly right in kind.** The admitting error IS "an above-ground
structure read as a below-grade solid" — it is a different above-ground structure: three
airbridges 600-700 m south (§2).

**Measured airside cost at the deck.** Way -10173 (`pav65`) is emitted **6.31 … 7.39 m below the
DEM** over its 27 nodes — worst `-7.39 m` at `30.1094084,31.4038713` (z = 97.95, DEM = 105.34).
The taxiway is being pulled into the trench. *Single-arm reading; attributing it to `channel:2`
rather than to HECA's general apron law needs the channel-off replay in §7.*

## 4. LEMD `channel:5` — THE SECOND FALSE POSITIVE

Products: `/Users/noah/XPTerrainBuilderData/Patches/+40-010/+40-004/LEMD_auto.patch.osm(.axes.json)`,
report `/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+40-004/LEMD/LEMD.report.json`.

**Which roads?** Both in `+40-004_airport_small_roads.osm.bz2` (again a bare-id collision: the
`big_roads` feed has its own -5828, a `bridge=yes highway=trunk layer=1` 200 km away at
40.3009,-3.7864, and its own -5832 at 40.5415,-3.6416):

* **-5828 = `highway=track`** (one tag). 18 nodes, from `40.4621513,-3.5551633` SE to
  `40.4572348,-3.5497030`. This is the axis: the channel's `floor_profile[0]` is -5828's node 0.
* **-5832 = `highway=service`** (one tag). 32 nodes, a loop 500 m NORTH,
  `40.4663723,-3.5556535` … ending at `40.4622484,-3.5551844` — **15 m from -5828's node 0**, so
  the two merge under `[channel] merge_m = 40`.

**The two decks — one real, one degenerate.** From the sidecar:

    decks = [{"ref":"channel_deck:5#0","way":-5828,"s0":450.0,"s1":470.0},
             {"ref":"channel_deck:5#1","way":-5832,"s0":  0.0,"s1":  0.0}]

`channel_deck:5#1` has **zero length at station 0**. It is not a real crossing and it is not the
same neck counted twice — it is way -5832's neck, projected onto an axis it does not run along.
The mechanism is at `Ortho4XP/src/auto_patch_v2/planar/channel.py:891-892`:

```
            spans.append((axis_ln.project(Point(a.x, a.y)),
                          axis_ln.project(Point(b.x, b.y)), int(c.way.id)))
```

`shapely.LineString.project` **clamps** to `[0, length]`. A neck standing off the far end of the
axis lands with both endpoints at 0.0 (or both at L), and `_decks`
(`channel.py:928-942`) has no `t1 > t0` test and no "is this neck inside the corridor" test, so
the degenerate span becomes a `Deck`. This is the SAME clamp defect §45 (10) already carries a
law comment about at the width site — `_across`: *"an end-clamped projection is an overhang, not
a width; that is the 404.7 m of round 1"* (`channel.py:604-606`). It was fixed for the width and
not for the stations.

**That zero-length deck is what admits the channel.** With one deck, `channel:5` would have been
refused exactly as its siblings were — the same report refuses `channel:3`, `channel:4` and
`channel:6` for `1 crossing(s) (< [channel] min_decks_without_depth 2)`.

**And it is what builds the hill.** `channel_floor` takes one anchor per deck at the deck MIDPOINT
(`channel_floor.py:91-96`): `(0.0, DEM(axis(0)) - 5.1) = (0, 583.90)` and
`(460.0, DEM(axis(460)) - 5.1) = (460, 580.90)`. Then line 109:

```
        prof.append((float(s), float(min(z + grade * abs(s - sd) for sd, z in anchors))))
```

a **minimum of upward-opening 8 % cones**, with no upper bound of any kind. Solving
`583.90 + 0.08 s = 580.90 + 0.08 (460 - s)` gives `s = 211.25, z = 600.80` — the report's
`600.70` and the sidecar's `emitted_floor_max_m 600.677`. Measured against the 5 m Spain DTM
(`/Users/noah/XPTerrainBuilderData/Elevation_data/+40-010/N40W004_airport_insets/LEMD_spain5m.tif`):

    s~   0.0  40.462151,-3.555163  floor 583.90  DEM 589.00  floor-DEM  -5.10
    s~  49.8  40.461964,-3.554632  floor 587.90  DEM 588.04  floor-DEM  -0.14
    s~  99.8  40.461626,-3.554249  floor 591.90  DEM 588.00  floor-DEM  +3.90
    s~ 149.9  40.461271,-3.553887  floor 595.90  DEM 588.00  floor-DEM  +7.90
    s~ 199.9  40.460925,-3.553510  floor 599.90  DEM 588.00  floor-DEM +11.90   <- the owner's hill
    s~ 250.0  40.460579,-3.553133  floor 597.70  DEM 587.00  floor-DEM +10.70
    s~ 350.0  40.459909,-3.552344  floor 589.70  DEM 586.00  floor-DEM  +3.70
    s~ 450.1  40.459237,-3.551560  floor 581.70  DEM 586.00  floor-DEM  -4.30
    s~ 490.2  40.458949,-3.551277  floor 583.30  DEM 586.00  floor-DEM  -2.70

The owner's point `40.460758,-3.5532228` (DEM 587.0) sits on that peak. The ground along -5828 is
FLAT — 589.0 m at s 0 falling to 585.0 at s 554, on a 5 m DTM. There is no cut and nothing to cut.

**The law text that is not implemented.** §45 (3)(iii): *"under each deck the floor is the deck
top − `bridge.clearance_m` … and between decks **the road's own longitudinal law (§37)** clamped
≤ that datum and ≤ `ramp_max_grade`."* `channel_floor.py:101-115` implements only the
`ramp_max_grade` half. There is no §37 term and no DEM term, so between two decks further apart
than `2 x clearance / ramp_max_grade` = 127.5 m the floor is free to climb 8 % indefinitely. The
docstring at lines 42-46 states the intent correctly and the code does not carry it.

**This is not confined to `channel:5`.** LEMD `channel:1` (decks 750-790 / 1280-1330, 535 m apart)
declares `603.90..625.10` and `channel:2` (860-920 / 1050-1110) declares `588.90..597.10` — the
same Λ. And LEMD's shipped 1.0.348 tile carries **`channel_floor_at_declaration` 230 rows**
(`verify.by_family`), against HECA's 0: the residual the §45 merge left "owed after the reads"
(RULINGS 2026-09-16i) is 230 rows at LEMD.

**Is neck + 2 decks the same clause family as HECA's neck + pack? No — they are the two OPPOSITE
branches of one sentence.** §45 (13)(c): *"a channel needs a pack or lidar witness, **or** a neck
witness with ≥ `min_decks_without_depth` (2) decks"*. HECA takes the first branch (its guard is
skipped entirely because `datum == DATUM_PACK`); LEMD takes the second (its guard runs and passes
because `len(decks) == 2`). One sentence, two independent false positives, two independent fixes.

## 5. THE COMBINED FALSE-POSITIVE TABLE

| | **HECA `channel:2`** FALSE | **LEMD `channel:5`** FALSE | **LGAV `channel:0`** TRUE | **VHHH `channel:0`** TRUE |
|---|---|---|---|---|
| source | 1.0.348 patch sidecar | 1.0.348 patch sidecar | `Patches/+30+020/+37+023/LGAV_auto.patch.osm.axes.json` (2026-09-16 16:55) | `/tmp/harness/v2wallface/base_VHHH/structures.json` (main `31b7ad1b`) |
| ways | -13192 `highway=service` | -5828 `highway=track` + -5832 `highway=service` | -1343 -7021 -2914 -4017 | -6184 |
| **witnesses** | **`neck, pack`** | **`neck`** | **`bridge, pack`** | **`neck`** |
| pack witness objects | **3 x `EGCC_Jetway_metal_03.obj` (AIRBRIDGES), point objects, 92 m off-axis** | none | **`Trench/Trench_07.obj` + `Trench/Trench_08.obj`** (`dsf:obj616/617`, purpose-built trench walls, ~2 km ALONG the axis) | none |
| decks / crossings | **1** (60 m, s 1870-1930) | **2, but one is ZERO length at s 0** | **4**, all positive spans (7.0, 13.6, 13.7, 13.6 m) | **3**, all positive spans (70, 120, 70 m) |
| datum | `pack` | `clearance` | `pack` | `clearance` |
| half-width | **92.0 m** from "pack walls", road reads **7.0 m** (x13.1) | 7.0 m, carriageways ⊕ `lane_width_m` | 62.8 m from pack walls, road reads 33.9 m (x1.85) | 7.0 m, carriageways ⊕ `lane_width_m` |
| declared floor | **97.324 flat over 1,990 m**, up to **12.4 m below the DEM** | **580.90 … 600.70**, Λ peaking **+11.90 m ABOVE the DEM** | 66.467 flat over the trench (the Trench seats) | 2.22 … 22.62, a real longitudinal profile |
| what is really there | undulating airfield, DEM 95.28-109.71 along the axis; **no cut** | flat ground, 5 m DTM 589 -> 585; **no cut** | the Attiki Odos + Proastiakos trench | a real apron channel |

The discriminating columns are **witnesses** and **deck spans** — not "does it cross airside
pavement", which all four do.

## 6. THE ADMITTING CLAUSE, QUOTED

`Ortho4XP/src/auto_patch_v2/planar/channel.py:755-766` — the whole guard:

```
    if (datum == DATUM_CLEARANCE
            and (WITNESS_NECK not in _wits(grp)
                 or len(decks) < ch.min_decks_without_depth)):
        stats.refused.append(
            f"{cid}: witnessed by a paved neck alone and with {len(decks)} crossing(s) "
            f"(< [channel] min_decks_without_depth {ch.min_decks_without_depth}) ...")
        return None
```

Spec §45 (13)(c), and §45 (19) as ratified names the HECA site itself: *"HECA's `channel:2`
(way -13192, neck + pack witness, one deck) is lawful under (13)(c) and stands; it is named for
the owner's HECA read."* (brief 460-461, RULINGS 2026-09-16g).

**HECA: is the pack witness's depth read the ONLY thing separating `channel:2` from the five
refused? YES — literally.** The guard is a single `if` on `datum == DATUM_CLEARANCE`. The five
refused (`channel:0/1/3/4/5`) are each `neck alone, 1 crossing`. `channel:2` is `neck, 1 crossing`
too. It survives only because `channel_floor` returned `DATUM_PACK` at `channel_floor.py:72`
before the guard was reached.

**LEMD: the only thing separating `channel:5` from `channel:3/4/6` is `len(decks) == 2`**, and one
of those two decks is zero-length.

**Would the law as written admit any airport where a pack models an underpass beside a road
crossing? Yes, and far more than that.** The pack-witness predicate is `_pack_witnesses`
(`channel.py:244-313`), called from `_pack_ids` (`channel.py:846-863`) with
`half_m = cap = corridor_max_half_width_m = 120.0`:

1. the placement's `below_grade` footprint has area > `min_area_m2` = 1.0 m²;
2. it intersects `cand.line.buffer(120 m)` — **anywhere within 120 m of the road, not on its
   course**;
3. `_depth_under_crest(o) >= object_min_depth_m` = 3.0 m, against the object's own local terrain.

Nothing requires the solid to be *on* the road, to run *along* it, to be a *wall or floor*, to be
below-grade *in the world* rather than in its own model space, or to be anywhere near the neck.
Any payware pack whose assets carry ≥3 m of below-origin geometry — jetways, GSE canopies, hangar
door wells, fuel-pit lids, any model on a sunk plinth — beside any service road that crosses any
taxiway will mint a channel. HECA is that case; it is not special.

## 7. THE LAW REFINEMENT (described, not implemented)

Blast radius is identical and small for all of these (`Ortho4XP/tools/blast.py`):
`planar/channel.py` is imported by `pipeline/build.py` and `planar/channel_claims.py`, tested
directly by `Ortho4XP/tests/auto_patch_v2/test_v2channel.py` plus 17 conftest-fixture tests.
`planar/channel_floor.py` is imported by `channel.py` alone (no direct twin — covered through
`test_v2channel.py`). `planar/channel_geometry.py` is imported by all three.

**NOT VIABLE: "refuse a channel that crosses airside pavement."** The owner has ruled it out
(EGLL / VHHH have real apron channels), and the data agrees: VHHH `channel:0` crosses airside
pavement at three necks. Dropped.

---

**FIX A — HECA. A PACK WITNESS IS A WALL OR A FLOOR *ALONG* THE CORRIDOR, NOT ANY DEEP OBJECT
NEAR IT.** Amends §45 (1)(c); one derivation site, `_pack_witnesses` (`channel.py:260, 291-311`),
two narrowings:

* (i) test the below-grade footprint against the ROAD'S OWN corridor (`half_base`, which reads
  **7.0 m** at HECA and 33.9 m at LGAV), not the 120 m search cap `half_m`;
* (ii) require the footprint to RUN ALONG the axis — its along-axis extent at least
  `[channel] corridor_min_length_m` (50 m), or simply longer than its across-axis extent.

Effect: HECA's three point jetways (90+ m off-axis, a few m² each) are dropped → the datum falls
to `DATUM_CLEARANCE` → **the EXISTING (13)(c) guard refuses it** for `1 crossing(s) < 2`. No new
refusal clause needed. LGAV's `Trench_07/08` run ~2 km along the axis at the corridor edge →
kept, and (i) also removes the 92 m half-width at source since `_walls_half` reads the same set.
VHHH and LEMD carry no pack witness → byte-identical. **Highest value, smallest surface, one
file.** This is the fix that answers the owner's "above-ground structure read as a below-grade
solid".

**FIX B — LEMD. A DECK IS A CROSSING ONLY IF IT HAS A POSITIVE SPAN ON THE AXIS.** Amends §45
(1)(b)'s deck derivation; one site, `_decks` (`channel.py:928-942`): drop any span with
`t1 - t0 < emit.identity.min_distinct_spacing_m`, and refuse a neck whose own midpoint stands
further than the corridor half-width from the axis (the `project` clamp is silent otherwise).
This is the same defect §45 (10) already names at `_across` — *"an end-clamped projection is an
overhang, not a width"* — carried to the station site. Effect: LEMD `channel:5` has **1** deck →
refused by (13)(c). VHHH's 3 decks, LGAV's 4 and LEMD `channel:1/2`'s 4 all have positive spans →
untouched. **Two-line change, one file.**

**FIX C — the missing half of §45 (3)(iii): THE FLOOR NEVER CLIMBS ABOVE THE ROAD.** Independent
of A and B, and the one that makes the whole clause safe. `channel_floor.py:101-115` computes
`min` over 8 % cones with no upper bound; add the clamp the spec already states — `z(s) =
min(cone(s), the road's own §37 profile at s)`, i.e. the road never rises above where it would run
at grade. At LEMD that pins the floor to 588-586 and the hill is gone even if `channel:5`
survived. It also bounds `channel:1` (declared 625.10) and `channel:2`. **This is a defect on its
own terms — a channel floor 11.9 m above the ground is not a floor — and should land whether or
not A and B do.**

**FIX D — a separate chip, not a §45 clause.** `airport/load.py:349-354` should treat an
**UNTAGGED** road feed at least as strictly as a superseded-schema one. Today an unstamped
2026-07-27 feed passes where a stamped 2026-07-16 feed refuses, which is what makes §45 (1)(d)
structurally unavailable at HECA.

**The fastest measurement.** Every registered HECA capture is `[MISSING]`, so there is no live
solve capture to replay. The fastest arm is the DRY structure replay §45.3 itself names (~25 s,
no build, no emit):

    cd Ortho4XP && venv/bin/python -m auto_patch_v2.planar HECA --stage structures

(`Ortho4XP/src/auto_patch_v2/planar/__main__.py:126-147`), diffed base-vs-branch with
`Ortho4XP/tools/structure_replay_diff.py` (promoted in v2channel round 5 for exactly this). The
identity bar is the same replay at **LEMD, VHHH, LGAV, KPHX, KDFW, KCLT, CYXY, OTHH** — and two
of those already have durable, registered base arms on disk to diff against:

    /tmp/harness/v2wallface/base_LEMD/structures.json    (main 31b7ad1b, 193 s)
    /tmp/harness/v2wallface/base_VHHH/structures.json    (main 31b7ad1b, 399 s, channels 1)

A HECA/LEMD capture for a solve or emit arm would have to be cut fresh
(`v2_solve_replay --capture`; HECA 156-187 s, LEMD 232 s on the registered history).

## 8. HISTORY

* §45 merged **2026-09-16** at `782a50d6` (RULINGS 2026-09-16i, brief 502-546); the merge note
  already records `HECA 1 (channel:2, -13192, neck + pack, one deck — the owner's read)` and
  `LEMD 3`. It shipped ON in **app 1.0.343** (RULINGS 2026-09-16v, brief 548).
* `channel:2` therefore **cannot** have been in the 1.0.340 HECA tile: 1.0.340 predates the merge.
* It is reproducible today and is not a §46 artefact. The two registered HECA frames still on
  disk both carry the identical record:

      /tmp/harness/xq_base_heca.osm.axes.json   (base main 6c8dfe71, lane xplatquantum)
      /tmp/harness/xq_lane_heca4.osm.axes.json  (lane arm, §46 1 mm quantum)

  both -> `channel:2  ways [-13192]  witnesses ['neck','pack']  datum pack  floor 97.324-97.324
  half-width 92.0 m  ends 0..1990 m` — equal to the 1.0.348 shipped sidecar.
* `tools/harness/frames.py list HECA`: **every other registered HECA frame is `[MISSING]`**,
  including the v2padclip `HECA.on2.pkl` capture at base `782a50d6`. I could not replay it or read
  its `channels`.
* The 1.0.344 HECA tile was built on main `ed7cedab`, post-`782a50d6`, so it carried §45 ON and,
  on the evidence above, the same `channel:2`. The brief's claim that 1.0.348 is the first HECA
  tile the owner has *seen* with §45 ON is about the owner's reads, which the repo cannot confirm.

## 9. SOURCES I COULD NOT VERIFY

1. **The 12th excluded way (§45 (13)(b)) at HECA.** I reproduced 11 `tunnel=yes` road ways inside
   `radius_deg = 0.05`; the report says 12. `load_feed` merges a 3x3 tile neighbourhood, so the
   12th is likely from a neighbour tile's feed. Naming it needs the structure replay (§7), which I
   did not run (read-only, no builds).
2. **`solid_min_depth_m` / `below_grade` as the engine computed them.** I could not read the
   engine's `obj8` values for `dsf:obj2786/7/8` without a load; I derived the depth from the OBJ's
   VT y range (-4.2753 m) and the inset DEM, which reproduces the published floor to 3 mm. The
   published `floor_declared_min_m 97.324` and the witness ids are read verbatim from the sidecar;
   the attribution of 97.324 to the jetway's model geometry is arithmetic, not a quoted engine
   value. The same applies to the LEMD anchors (reproduced to 0.1 m by the same arithmetic).
3. **Which feed's -5828 / -5832 the LEMD channel took.** The sidecar publishes bare ids and both
   ids collide across feeds. I identified the `airport_small_roads` copies because their geometry
   matches the published `floor_profile` endpoints exactly; the engine's own `way_key` was not
   published for LEMD (VHHH's `structures.json` does publish `way_keys`; the patch sidecar does
   not).
4. **The DEM frame.** I sampled `HECA_copernicusglo30.tif` and `LEMD_spain5m.tif` directly (GDAL,
   read-only) rather than through `airport/dem_production`, to avoid any chance of a shared-repo
   write. The engine reads a baked working grid with bilinear query
   (`load.dem_provenance.query = "bilinear on the baked working grid"`), so my values can differ
   by the bake. The 3 mm agreement at `dsf:obj2786` says the difference is small there; read the
   axis-profile numbers as ±0.2 m. HECA's only inset is COPERNICUSGLO30 (30 m,
   `load.flat_site.signals.s2_source_class = "coarse"`), so §45 (3)(ii)'s lidar witness can never
   fire at HECA and the DEM can never be asked whether the cut is real.
5. **Attribution of `pav65`'s -6.3…-7.4 m z−DEM to `channel:2`.** Single-arm reading. A
   channel-off replay is needed (memory `mechanism-before-fix`).
6. **EGLL.** No EGLL frame, capture or product exists anywhere I could reach; VHHH is the only
   real apron channel I could read, and it is the owner's own example.
7. **LGAV `channel:0`'s registered frame.** Read off the shipped
   `Patches/+30+020/+37+023/LGAV_auto.patch.osm.axes.json` (2026-09-16 16:55), which is the
   owner's tile build, not a lane arm; its `dsf:obj616/617` resolve to `Trench/Trench_08.obj` and
   `Trench/Trench_07.obj` in `+37+023.dsf.04094557.text` (713 placements) — the OTHER cached dump
   in that pack (`+37+023.dsf.d6b261e0.text`, 1,639 placements) indexes those ids to South
   Buildings objects, so the pairing depends on the build having read the 713-placement dump. I
   did not verify which dump the LGAV build read.
8. **`tools/site_read.py --dsf-dump`** — I read the pristine dumps through the engine's own
   `airport/dsf.read_dump` instead, because I needed the placement INDEX (`dsf:obj{i}`), which
   `site_read`'s point-scoped report does not key on. Same files, same parser.
