# Pack-read profile — TNCM / TFFG, one shared pack (lane `packreadprofile`, 2026-09-18)

MEASUREMENT ONLY. No fix, no design. Every number below was taken on branch
`claude/packreadprofile`, base main `b12fe86a`, worktree
`/Users/noah/XPTerrainBuilder/.claude/worktrees/packreadprofile/Ortho4XP`,
on the SHARED corpus mounted by `lane_worktree.sh up packreadprofile`, with
`arm_shared_repo_protection` armed on every run (`[guard] shared repo
UNCHANGED` on all four). Nothing was written into
`/Users/noah/X-Plane 12/…` (verified by `find -newermt`).

THE SITE: app 1.0.351, tile `+18-064`. TNCM and TFFG both resolve their
apt.dat to ONE pack,
`/Users/noah/X-Plane 12/Custom Scenery/c_NLD - 100_airport - TNCM_1_Apt`.

CONTENTION DISCLOSURE: the owner's app was building `+18-064` (and later
`+46+006`) throughout. Absolute walls are inflated; ratios, call counts and
COUNTS are not. Never quote these as timing baselines.

---

## 0. HEADLINE

1. **Parsing the pack is not the cost.** TNCM parses 1.72 GB of `.obj`
   (5.71 M solid triangles, 17.3 M `VT` rows) in **9.3–9.4 s**. The whole
   pack read + partition + groups is **301 s** and the capture to its crash
   point is **870 s**.
2. **The cost is COMPONENTS, not placements, resources, bytes or triangles.**
   TNCM's 315 in-window resources carry **118,485 solid connected components**;
   the partition places **101,922 parts**. `Objects/Flora/HillBush.obj`
   alone is **41,220 components** (39 MB), `Objects/Autogen/AG2_palms.obj`
   **24,089**. These are scatter objects — bushes, palms, people, fences,
   baggage carts — that no structure law can ever admit.
3. **Cutting the placement window by 87 % changes nothing** (measured
   what-if §5.1): placements 10,024 → 1,353, parts 101,922 → **101,935**,
   partition 231.2 → **233.3 s**. A distance/bbox prefilter on PLACEMENTS is
   refuted as a lever.
4. **The `math.hypot` hot loop is `model/ground_fit.py:85 neighbour_pairs`** —
   pure-Python O(n²) Prim MST — **444,096,901 of the run's 445,211,151 hypot
   calls (99.75 %)**, and **84.4 % of its work is ONE call with n = 27,376
   feet**. A throwaway numpy Prim on that exact real input is **12.9× faster
   with byte-equal output** (§5.2). **At TFFG the same loop is 646.5 s of a
   652.3 s stage (99.1 %), max n = 86,592, Σ n² = 14.2 G** (§1.6) — TFFG's
   pack read + partition + groups is **1,126.7 s at 18.50 GB max RSS**
   against TNCM's 301.6 s at 7.08 GB, on a THIRD fewer placements.
5. **The partition cache never hits when two airports share one pack**, and
   worse, they overwrite each other: the fingerprint includes the ICAO and
   the radius, the FILE PATH does not (§2, row P).
6. **The sibling child in `sem_wait` is not blocked on useful work** — it is
   an IDLE `ProcessPoolExecutor` worker that finished its airport and is
   parked in `call_queue.get()`, still holding its peak RSS (§1.4).
7. **TNCM CANNOT COMPLETE TODAY.** Both my capture and (by the same code
   path) the app die in
   `airport/wall_corridors.py:289 unary_union(caps)` with
   `GEOSException: TopologyException: side location conflict at
   -557.63537947169073 254.3627994326352` (§1.5). GEML failed the same class
   in the owner's log today.

---

## 1. WHERE THE TIME AND MEMORY GO

### 1.1 TNCM stage table

Un-profiled arm (`instr_groups.py`, the engine's own functions, no cProfile):

| stage | wall (s) | note |
|---|---|---|
| `airport/load.load_with_report` | **4.1** | 10,066 `DsfObject` |
| `planar/basins.read_objects` (= `basin_witness.read_objects`) | **23.5** | 10,024 placements, 10,024 resolved, 463 resources parsed, 3,169 stock |
| &nbsp;&nbsp;of which `obj8.parse_obj8` | 9.4 | 494 files, 1.72 GB |
| &nbsp;&nbsp;of which `obj8.solid_components` | 7.3 | 315 resources |
| `airport/pack_partition.partition_pack` | **231.2** | see counts below |
| `planar/group.derive` | **42.8** | of which `neighbour_pairs` **39.6 (92.5 %)** |
| max RSS (this arm) | **7.08 GB** | |

`partition_pack` counts: units 9, **members 246**, **parts 101,922**,
contacts 761,153, pools 89, structures 3,900, **pairs_tested 2,261,597**,
pairs_unproved 920, abutments 33,909, multi_anchor 68, stock 3,169,
line_objects 13, elevated_decks 23.

`group.derive` counts: bodies 6,558, groups 5,945, relief 2,258,
infeasible 1,838, abutment_pairs 33,909, refused_building 28,013.

Profiled arm (cProfile, `prof_capture.py`, whole `v2_solve_replay.capture`):
**870.2 s wall, 13.71 GB max RSS, 1,394,016,582 function calls**, ending in
the GEOS crash. Profiler overhead ≈ 1.2× on partition, ≈ 2.2× on
`read_objects`. Stage cumulative time from the profile:

| stage | cum (s) | % of 870 |
|---|---|---|
| `airport/pack_partition.py:435 partition_pack` | 339.3 | 39.0 |
| &nbsp;&nbsp;`airport/contact.py:673 partition` | 254.4 | 29.2 |
| &nbsp;&nbsp;&nbsp;&nbsp;`contact.py:555 _narrow_pass` | 168.6 | 19.4 |
| &nbsp;&nbsp;&nbsp;&nbsp;`contact.py:309 placed_parts` | 66.2 | 7.6 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`contact.py:215 plan_hull` | 57.1 | 6.6 |
| &nbsp;&nbsp;`airport/skirt.py:150 reading` (10,262 calls / 462 real) | 79.1 | 9.1 |
| `planar/build.py:160 build` (PARTIAL — crashed) | 298.5 | 34.3 |
| &nbsp;&nbsp;`airport/door_wells.py:286 read_door_wells` | 134.5 | 15.5 |
| &nbsp;&nbsp;`airport/tunnel_objects.py:825 read_corridors` | 83.1 | 9.5 |
| &nbsp;&nbsp;`airport/object_cut.py:445 read_shells` | 75.0 | 8.6 |
| &nbsp;&nbsp;`airport/wall_corridors.py:554 read_wall_corridors` | 69.2 | 8.0 |
| &nbsp;&nbsp;`airport/sunken_roads.py:273 read_sunken_roads` | 11.6 | 1.3 |
| `planar/group.py:355 derive` | 121.8 | 14.0 |
| &nbsp;&nbsp;`model/ground_fit.py:132 ground_fit` | 119.4 | 13.7 |
| &nbsp;&nbsp;&nbsp;&nbsp;`model/ground_fit.py:85 neighbour_pairs` | 113.4 | 13.0 |
| `airport/basin_witness.py:60 read_objects` (2 calls, 2nd memoised) | 51.9 | 6.0 |
| &nbsp;&nbsp;`airport/obj8.py:598 read_placed_objects` | 47.3 | 5.4 |
| &nbsp;&nbsp;&nbsp;&nbsp;`airport/obj8.py:92 parse_obj8` | 21.7 | 2.5 |
| `classify/roles.py:182 classify` | 32.0 | 3.7 |
| `planar/cluster.py:109 clusters` | 9.8 | 1.1 |
| `airport/load.py:211 load_with_report` | 10.9 | 1.3 |

### 1.2 Top functions inside the dominant stage (cProfile, by tottime)

| tottime (s) | ncalls | function |
|---|---|---|
| 180.2 | 297,130 | `shapely/set_operations.py:463 union_all` |
| 77.1 | 3,152 | `v2/model/ground_fit.py:85 neighbour_pairs` ← the hypot loop |
| 60.9 | 2,034,231 | `shapely/measurement.py:53 distance` |
| 51.8 | 4,465,496 | `v2/airport/contact.py:509 _narrow_rows` |
| 39.6 | 4,465,496 | `v2/airport/contact.py:456 _inside` |
| **36.4** | **445,211,151** | `math.hypot` |
| 34.0 | 650,434 | `shapely/constructive.py:136 buffer` |
| 32.2 | 48,396,109 | `shapely/decorators.py:73 wrapped` (shapely's own Python wrapper) |
| 25.2 | 9,806,760 | `numpy.ufunc.reduce` |
| 21.3 | 96,388 | `shapely/set_operations.py:112 intersection` |
| 19.4 | 1 | `v2/airport/contact.py:555 _narrow_pass` (own frame) |
| 17.9 | 29,199,009 | `shapely/predicates.py:844 intersects` |
| 15.5 | 4,593 | `v2/airport/contact.py:477 _point_tri_dist2_rows` |
| 11.2 | 103,420 | `numpy.ndarray.argsort` |
| 10.6 | 863,711 | `v2/airport/dem_production.py:180 sample` |
| 9.2 | 982 | `numpy.fromstring` (inside `parse_obj8`) |
| 7.2 | 10,991 | `numpy.ndarray.sort` |
| 6.5 | 494 | `v2/airport/obj8.py:92 parse_obj8` (own frame) |
| 6.2 | 129,830,571 | `builtins.isinstance` |
| 5.5 | 554,821 | `shapely/predicates.py:429 is_valid` |
| 5.4 | 2,594,082 | `shapely/creation.py:332 polygons` |
| 5.3 | 29,199,009 | `shapely/geometry/base.py:817 intersects` (wrapper) |
| 5.1 | 31,392,968 | `numpy.generic.item` |
| 5.0 | 2,594,803 | `shapely/creation.py:234 linearrings` |
| 4.1 | 863,711 | `v2/airport/dem_production.py:540 z_many` |

Cumulative-time view adds the shapely wrapper chain: `decorators.py:73
wrapped` **48,396,109 calls / 393.4 s cumulative (45 % of the run)** — i.e.
**48.4 million individual shapely (GEOS) calls**.

### 1.3 The hot loop, exactly

```
src/auto_patch_v2/model/ground_fit.py:85  neighbour_pairs(pts)
```
* **What it is**: the Euclidean MINIMUM SPANNING TREE over one body's ground
  FEET, computed with **pure-Python O(n²) Prim** — the docstring says so and
  says why (`model` may import neither scipy nor numpy, M0 §1). The inner
  loop is `d = math.hypot(ux - vx, uy - vy)` at line 124.
* **What it iterates**: `pts` = one GROUP's feet in plan (metres), built in
  `ground_fit` (`:158`) from `Foot(lat, lon, y)` rows; each part contributes
  at most `[rebake] foot_samples_max` = 4 feet, and a LINE OBJECT up to
  `line_object_stations_max` = 64 stations.
* **Complexity**: Θ(n²) per call in feet-of-one-group, Σ n² over the airport.
* **The n it ran on (measured, TNCM)**: **3,152 calls, 137,547 feet total,
  Σ n² = 888,331,349, max n = 27,376.** The single n = 27,376 call is
  749.4 M of that Σ n² = **84.4 % of all the work**, and takes **32.4 s** of
  the 39.6 s the whole stage spends here. Next largest: 7,956 / 6,192 /
  2,052 / 2,028 / 2,005 / 1,309 / 1,127 / 1,052 / 1,013.
* **Why n is 27,376**: the contact graph welds the scatter objects' 101,922
  parts into a few bodies; one body carries ~7,000 parts × up to 4 feet.
* Called from `planar/group.py:411 _verdict` → `model/ground_fit.py:132
  ground_fit` (5,945 groups, 3,152 with ≥ 2 sampled feet).

The brief's second name, `vector_norm`, is
`contact.py:330 areas = 0.5 * np.linalg.norm(np.cross(b - a, d - a), axis=1)`
inside `placed_parts` (66.2 s cum), one numpy call per placed component.

### 1.4 The `sem_wait` sibling — attributed

Live specimens sampled while the owner's app was stuck (`/usr/bin/sample`,
outputs at `/Users/noah/XPTerrainBuilder/.lanes/packreadprofile/live_*.txt`):

* pid **97736**, 98 % CPU, 7.1 GB → 100 % of samples in a numpy ufunc →
  `GEOSUnaryUnion_r` → `CascadedPolygonUnion::binaryUnion` →
  `OverlayNG`/`MCIndexNoder`. That is `shapely.union_all`; in this code path
  it is `contact.plan_hull` / the structure readers.
* pid **97738**, 0 % CPU, 12.8 → 7.5 GB, **4,445 of 4,445 samples in
  `sem_wait` from `_PyEval_EvalFrameDefault`** for > 20 minutes.

There is **no lock in the v2 airport build path** (`grep Lock()/RLock()/
Semaphore(/acquire(` over `src/auto_patch_v2` returns nothing;
`partition_cache.py` takes no lock at all). The dispatcher is
`src/auto_patch/driver.py:987 _cf.ProcessPoolExecutor(max_workers=n,
mp_context=spawn, initializer=_init_worker, initargs=(dem, pq))`, one
`submit` per airport (`:1001`). An idle CF worker blocks in its call
queue's `_rlock.acquire()`, which is exactly `sem_wait`. TQPF had already
reached `[95/100]` in the log. **The lock serialises nothing and duplicates
nothing — it is an idle worker whose freed arenas Python has not returned
to the OS.** `max_tasks_per_child` is not set. Note also that the tile DEM
is pickled into `initargs` and therefore exists once per worker (production
frame `11017×11017`, float32 ≈ 485 MB per copy before compositing).

### 1.5 The crash (blocking, reproduced)

```
planar/build.py:198  read_wall_corridors
  airport/wall_corridors.py:613  _bands_of
  airport/wall_corridors.py:289  cap_u = unary_union(caps)
shapely.errors.GEOSException: TopologyException: side location conflict
  at -557.63537947169073 254.3627994326352
```
Un-guarded `unary_union` over placement-transformed triangle polygons
(`_plan_polys(v, comp.tris[~vert], mat)`), no `make_valid`, no try/except.
Reproduced twice (901.8 s / 12.40 GB, and 870.2 s / 13.71 GB under
cProfile). The owner's log shows the same GEOS class already killing GEML
today (`[+35-003] Auto-patch: FAILED GEML (build): [v2] TopologyException:
unable to assign free hole to a shell`). TNCM sat at `[40/100]` for 45+
minutes in the app and has the same call ahead of it.

### 1.6 TFFG — WORSE THAN TNCM

Same instrument, same tree
(`/Users/noah/XPTerrainBuilder/.lanes/packreadprofile/instr_TFFG.log`):

| stage | TNCM | **TFFG** |
|---|---|---|
| `load_with_report` | 4.1 s | 4.2 s |
| `read_objects` | 23.5 s | **11.3 s** |
| &nbsp;&nbsp;placements / resolved / resources parsed / stock | 10,024 / 10,024 / 463 / 3,169 | 6,750 / 6,750 / 243 / 2,470 |
| `partition_pack` | 231.2 s | **458.9 s** |
| &nbsp;&nbsp;members / parts | 246 / 101,922 | **72 / 76,930** |
| &nbsp;&nbsp;contacts / pairs_tested / pools / structures / abutments | 761,153 / 2,261,597 / 89 / 3,900 / 33,909 | 507,738 / 1,619,419 / 8 / 368 / **2** |
| `group.derive` | 42.8 s | **652.3 s** |
| &nbsp;&nbsp;of which `neighbour_pairs` | 39.6 s (92.5 %) | **646.5 s (99.1 %)** |
| &nbsp;&nbsp;bodies / groups / infeasible | 6,558 / 5,945 / 1,838 | 1,149 / 1,134 / 956 |
| `neighbour_pairs` calls / Σ n² / **max n** | 3,152 / 888,331,349 / **27,376** | **1,095 / 14,153,408,902 / 86,592** |
| feet total | 137,547 | **298,372** |
| **pack read + partition + groups** | **301.6 s** | **1,126.7 s** |
| **max RSS** | 7.08 GB | **18.50 GB** |

TFFG's n histogram: 86,592 / 62,744 / 40,628 / 26,452 / 15,172 / 8,444 /
4,268 / 2,072 / 2,046 / 1,970 ×2 / 1,428 / 1,340. **Σ n² is 16× TNCM's from
a THIRD as many calls.** The top four calls alone are 13.0 G of the 14.2 G.

The reading: **the two airports' costs are independent, neither is driven
by its placement count, and the SMALLER airport is the expensive one.**
TFFG has 33 % fewer placements, 71 % fewer members and 75 % as many parts —
and a 2× partition wall, a 15× groups wall and 2.6× the memory.

### 1.7 Pack facts

| fact | value |
|---|---|
| pack size on disk | 8.8 GB |
| `.obj` files in the pack | 543 (3.74 GB) |
| `OBJECT_DEF` in `+18-064.dsf` | 611 (431 resolve to a pack `.obj`; 180 are `lib/` virtual paths) |
| `OBJECT*` placements in `+18-064.dsf` | **16,282** |
| referenced `.obj` bytes / `VT` rows / solid tris / draped tris | 2.04 GB / 20,617,376 / **6,808,862** / 79,007 |
| DSFTool text dump | 2,074,994 B, `+18-064.dsf.10aa9ce7.text` |
| TNCM window (±0.05° box, `load.py:467`) | **10,075 placements**, 315 in-pack resources, **1,717 MB**, 17,259,393 VT, **5,710,451 solid tris**, **118,485 components** |
| TFFG window (±0.05° box) | **6,832 placements**, 163 in-pack resources, **336 MB**, 3,492,278 VT, **1,143,176 solid tris** |
| resources read by BOTH | **130** — **12.3 MB**, 44,765 tris (heaviest shared is a 1.0 MB sailboat) |
| placements standing in BOTH windows | **2,867** |

**Duplicate READ between the two airports is small: 12.3 MB of 2.05 GB
(0.6 %).** Duplicate DOWNSTREAM work is not: 2,867 placements are partitioned,
witnessed, footprinted and contact-tested twice, once per pool child.

Heaviest resources by COMPONENT count (the thing that costs), TNCM window:

| components | tris | verts | MB | placements | resource |
|---|---|---|---|---|---|
| **41,220** | 123,660 | 370,980 | 39.1 | 1 | `Objects/Flora/HillBush.obj` |
| **24,089** | 487,448 | 1,462,344 | 153.5 | 1 | `Objects/Autogen/AG2_palms.obj` |
| 7,614 | 98,992 | 296,976 | 27.1 | 1 | `Objects/Ground/Roads/ParkingBushes.obj` |
| 4,020 | 117,840 | 353,520 | 34.5 | 1 | `Objects/Vehicles/BaggageCarts.obj` |
| 3,534 | 34,379 | 103,137 | 9.1 | 1 | `Objects/Autogen/AG1_Palms2.obj` |
| 2,745 | 355,465 | 1,066,395 | 112.5 | 1 | `Objects/Autogen/Docks.obj` |
| 2,428 | 237,950 | 713,850 | 71.1 | 1 | `Objects/People/Maho_Girl3.obj` |
| 2,345 | 193,852 | 581,556 | 56.4 | 1 | `Objects/Airport/AirportFenceBig.obj` |
| 2,138 | 93,569 | 280,707 | 24.5 | 1 | `Objects/Airport/TerminalInterior.obj` |
| 1,955 | 314,494 | 943,482 | 91.5 | 1 | `Objects/Autogen/Autogen1.obj` |
| 1,890 | 331,332 | 993,996 | 99.6 | 1 | `Objects/Airport/AirportFence.obj` |

Note the shape difference from OTHH (RULINGS 17o/17w): OTHH's driver is
1,247 heavy resources × 14,218 placements. TNCM's is **one placement each of
a few scatter files whose single `.obj` contains tens of thousands of
disconnected components.** Both end at the same place — component count.

---

## 2. THE READ-ONCE MAP

One row per path that reads pack data. "Two airports, one pack, one tile"
= do the two POOL CHILDREN share it?

| # | read | site (file:line) | what is cached | KEY | scope / root | shared TNCM↔TFFG? | reused on a 2nd build? |
|---|---|---|---|---|---|---|---|
| A | DSFTool text dump of the pack DSF | `auto_patch_v2/airport/dsf.py:104 find_text_dump`, tag `dsf.py:82 text_dump_tag`; produced by `auto_patch.engine_v2.fresh_pack_dump` | `<tile>.dsf.<tag>.text` | **path + sha256(DSF bytes)[:8]**, content-hashed | on disk, `Airport_mod_cache/<pack>/` (shared repo, or `O4_AIRPORT_MOD_CACHE_DIR` overlay) | **YES** — per pack+DSF, no ICAO | **YES** |
| B | dump parse → defs / placements / polygons | `airport/dsf.py:145 read_dump` (pure-Python per line) | **nothing** | — | in-process only | **NO** — each child re-parses the 2.07 MB dump | NO |
| C | v1 object footprints (buildings) | `auto_patch/dsf_reader.py:1560 read_dsf_buildings`, sidecar `dsf_reader.py:1296` | `o4_object_footprints_<tile>.cache` | **DSF + every pack `.obj` + 2 partition constants** — no ICAO | on disk, mod-cache root; plus in-process memo `_OBJECT_READER_MEMO` and per-DSF `threading.Lock` (`dsf_reader.py:1452-1466`) | **YES** on disk; the in-process memo/lock is per PROCESS so the two children each read the sidecar (cheap) | **YES** |
| D | v1 object placement positions | `auto_patch/dsf_reader.py:2334 read_dsf_object_placement_positions` | `o4_dsf_object_positions_<tile>.cache` | DSF **size + mtime** (not content) | on disk, mod-cache root | **YES** | YES (it is the file whose fingerprint refresh caused the 17w disclosed write) |
| E | X-Plane library index (`lib/…` → physical) | `airport/obj8.py:261 library_index_path`, `:267 read_library_index` — READ-ONLY, never rebuilt here | `o4_library_index_<sha1(xplane_root)[:16]>.cache` | X-Plane root | on disk, mod-cache root | **YES** | YES |
| F | placement resolution + `DsfObject` mint | `airport/load.py:463-492` (window `:467`, `radius_deg` 0.05 default at `load.py:68`) | nothing | — | in-process | **NO** — 2,867 placements resolved twice | NO |
| G | **OBJ8 text parse** | `airport/obj8.py:92 parse_obj8`, memo `obj8.py:378 ResourceCache.geometry` | `ResourceCache._geom` | **resolved path** | **in-process only, per pool child** | **NO** — the 130 shared resources (12.3 MB) parsed twice | **NO** — never on disk |
| H | solid connected components | `airport/obj8.py:210 solid_components`, memo `obj8.py:386 ResourceCache.components` | `ResourceCache._comps` | resolved path | in-process, per child | **NO** | NO |
| I | per-resource y/plan range, bounds | `ResourceCache._range`, `._bounds` | yes | resolved path | in-process **+ carried in the partition cache** (`obj8.py:356 derived_state`) | via row P only | via row P only |
| J | skirt reading | `airport/skirt.py:150 reading`, memo `ResourceCache.skirt` | yes (a plan `union_all` per resource) | resolved path | in-process + `derived_state` | via row P only | via row P only |
| K | placed objects / floor witnesses | `airport/basin_witness.py:60 read_objects` → `obj8.py:598 read_placed_objects`; memo `ResourceCache.placed["objects"]` (`basin_witness.py:68,96`) | yes | the literal key `"objects"` | in-process, per child; **restored by row P** | **NO** | via row P only |
| L | at-grade / above-grade clip + union | `obj8.py:987 at_grade_geometry`, `obj8.py:~960 above_grade_footprint`; memos `ResourceCache.grade_memo` / `cover_memo` / `clip_memo` (`obj8.py:328-331`), `obj8_grade.py:117 memo_union` | yes | **`(resource, component, plane)`** — frame-independent by construction (RULINGS 13bp, fixed by `v2doorwellperf` 17w) | in-process, per child | **NO** | NO |
| M | **component plan footprint (`plan_hull`)** | `airport/contact.py:215 plan_hull`, called from `contact.py:349 placed_parts` | **NOTHING** | — | — | **NO** | **NO** — 101,922 GEOS `union_all`s per airport per build |
| N | contact graph / narrow pass | `contact.py:673 partition`, `:555 _narrow_pass`, `:400 _broad_pairs` | nothing | — | in-process | **NO** — 2.26 M pair tests redone per airport | via row P only |
| O | ground feet + MST | `contact.py:142 _feet`; `model/ground_fit.py:85 neighbour_pairs` | **nothing** | — | — | **NO** | **NO** (groups are never cached — see below) |
| P | **THE PACK PARTITION CACHE** | `airport/partition_cache.py`, driven at `pipeline/build.py:392-424` | `(pack_objects, pack_report, partition, clusters, ocache.derived_state())` | `v2 \| code_digest \| law sha \| ruleset \| dump(name,size,mtime) \| every pack .obj pristine (relpath,size,mtime) \| frame crs/lat0/lon0 \| **icao** \| **radius_deg** \| pack root \| borrowed apt block` (`partition_cache.py:130-161`) | on disk, `Airport_mod_cache/<pack>/o4_v2_partition_<tile>.cache` — **PATH carries the TILE ONLY** (`cache_path`, `:195-215`) | **NO, AND WORSE: they collide.** One path, two fingerprints → each airport misses, rebuilds, and OVERWRITES the other's payload. No lock. | **NO** in a two-airport tile: the second airport's write leaves the first permanently stale |
| Q | groups (`planar/group.derive`) | `pipeline/build.py:440` | **deliberately NOT cached** (module doc: it reads `dem_at`) | — | — | NO | NO |
| R | door wells / tunnels / plates / sunken roads / wall corridors / basins | `planar/build.py:186-227` | only through the `ResourceCache` memos of row L | — | in-process | NO | NO |
| S | rebake plan | `airport/rebake_plan.py` (filters row P's partition) | — | — | — | — | — |

**Evidence for row P's collision.** `fingerprint()` hashes
`f"icao:{airport.icao}|radius:{radius_deg}|"` (`partition_cache.py:153`);
`cache_path()` builds the name from the DUMP's tile token only
(`:207-215`). Both airports of `+18-064` therefore write and read
`Airport_mod_cache/c_NLD - 100_airport - TNCM_1_Apt/o4_v2_partition_+18-064.cache`.
Observed: that file was **21,712,447 B** at 19:21 and **18,306,851 B** at
19:34:44 during the app's `+18-064` run — two different payloads at one
path inside one tile build. No `[partition] cache HIT` or `cache WROTE`
line appears anywhere in `engine-stderr.log`.

Also note: `_pristine_entries` (`partition_cache.py:163`) walks the whole
8.8 GB pack tree and `os.stat`s all 543 `.obj` on every fingerprint — once
per airport, twice per tile.

---

## 3. PER-AIRPORT vs PER-PACK (what is frame-independent)

| work | frame-independent (cacheable ONCE per pack/resource) | why / where the airport frame enters |
|---|---|---|
| `parse_obj8` (vertices, tri indices, hardness, draped) | **YES, fully** — authored object space | — |
| `solid_components` (welding, labels, min/max y, centroid, hard-deck flag) | **YES, fully** — authored object space (`obj8.py:210-247`) | — |
| per-resource `y_range` / `bounds` | **YES** (already carried in row P's `derived_state`) | — |
| skirt reading | **YES** (already carried) | — |
| **component plan footprint** (`plan_hull`'s `union_all`) | **YES in shape** — the union of the projected triangles is invariant under the placement's rotation+translation; today it is computed on PLACED points (`contact.py:349 plan_hull(pts, lt)` where `pts = _place(...)`) so nothing is reused. **This is the single biggest frame-independent item: 101,922 unions, 57.1 s cum, ZERO cache.** | only the final rigid transform of the ring |
| `_feet` selection (which vertices are feet, thinned by farthest-point over the plan) | **YES** — the choice is over authored (x, z) and authored y (`contact.py:142-172`); only the *coordinates* need placing | the returned (x, y) are placed |
| component triangle areas / area-weighted centroid (`contact.py:330`) | **YES** — rigid transforms preserve area; the centroid transforms | — |
| anchor_z, agl, rendered y = `DEM(anchor) + agl + y` | **NO** | the DEM sample is the airport's |
| at-grade / above-grade CLIP at a plane | **already memoised frame-independently** at `(resource, component, plane)` — but the PLANE is a DEM reading, so the key is per-airport in practice | `obj8_clip`, `obj8.py:328-331` |
| contact graph / narrow pass / pools / abutments | **NO in general** — pairs are across placements, which only exist in the airport frame. **BUT**: pairs WITHIN one placement (`_narrow_pass` explicitly tests and records them, `contact.py:585-590`) are frame-independent, and with 101,922 parts from 246 members most pairs are intra-member. | — |
| `ground_fit` / `neighbour_pairs` | **NO** — feet are placed and the verdict prices the DEM's fall | — |
| basins / door wells / tunnels / wall corridors | **NO** — every rule reads the local ground | — |

**The GEML interaction the brief names.** `obj8._witness` (`obj8.py:855`,
24,280 calls / 45.5 s cum here) rotates the component's geometry into the
airport frame and that rotation mints invalid rings (GEML: 126 of 449).
A frame-independent cache makes this *better or worse depending on where
the rotation lands*: if the cached artefact is the ring in OBJECT space and
the rotation is applied to the finished ring, the ring is rotated once
(N vertices) instead of the triangles being rotated and re-unioned
(N triangles), so there are strictly fewer chances to mint an invalid
ring — but the *validity* of the rotated ring must then be asserted at the
cache boundary, not inside the union. The same crash class is live in
`wall_corridors.py:289` (§1.5), which unions placement-transformed
triangles with no `make_valid`. This is a correctness fact the spec author
must rule on, not a design I am proposing.

---

## 4/5. MEASURED WHAT-IFS (labelled; NOT designs)

### 5.1 Prefilter the placement window — REFUTED

Arm: the identical instrumented run with `Inputs.radius_deg` 0.05 → 0.015
(a ±1.6 km box instead of ±5.5 km). One variable, one tree.

| | radius 0.05 | radius 0.015 | Δ |
|---|---|---|---|
| placements resolved | 10,024 | **1,353** (−86.5 %) | |
| resources parsed | 463 | 338 | |
| `read_objects` | 23.5 s | 18.0 s | −23 % |
| **parts** | 101,922 | **101,935** | **+13** |
| **`partition_pack`** | **231.2 s** | **233.3 s** | **+0.9 %** |
| `group.derive` | 42.8 s | 43.5 s | +1.6 % |
| `neighbour_pairs` calls / Σn² / max n | 3,152 / 888,331,349 / 27,376 | 3,159 / 888,331,631 / **27,376** | unchanged |
| max RSS | 7.08 GB | 7.04 GB | −0.6 % |

**Throwing away 87 % of the placements removes 0 % of the cost.** The cost
lives in ~250 MEMBERS near the airport whose resources carry 100 k+
components. A bbox/STRtree prefilter over PLACEMENTS is not the lever; a
budget or a filter over COMPONENTS is where the mass is.

### 5.2 Vectorise the hottest pure-Python loop — 12.9× on the real input

Throwaway `whatif_prim.py` (scratch only, `src` untouched): the shipped
`model/ground_fit.neighbour_pairs` vs a numpy Prim (`np.hypot` over the
whole candidate array per step), run on the **largest real TNCM input
captured by the instrumented run** (pickled, n = 27,376):

```
largest real input n = 27376
shipped pure-Python Prim : 32.446 s   edges 27375
numpy-vectorised Prim    :  2.510 s   edges 27375   speedup 12.9x
outputs identical (indices equal, distance |d| <= 1e-9): True
```

On **TFFG's** largest real input (n = 86,592, the same script, same tree):

```
largest real input n = 86592
shipped pure-Python Prim : 345.207 s   edges 86591
numpy-vectorised Prim    :  23.820 s   edges 86591   speedup 14.5x
outputs identical (indices equal, distance |d| <= 1e-9): True
```

That single TFFG call is **345.2 s of the stage's 646.5 s**; the TNCM call
is 32.4 s of 39.6 s. Note the constraint the
docstring states: `model` may import neither numpy nor scipy (M0 §1) — so
this is a measurement of the ceiling, not a patch. (An O(n log n) EMST via
a Delaunay triangulation would be a different order again; not measured.)

### 5.3 Where a native/vectorised path would and would not help

Purely from the measured split (§1.2): 180.2 s of `union_all` +
2.03 M `distance` + 29.2 M `intersects` + 0.65 M `buffer` = **GEOS is
already C++**; what is Python there is the **48.4 M wrapper crossings**
(`decorators.py:73`, 32.2 s of pure overhead) and the fact that the calls
are MILLIONS OF TINY ONES rather than a few bulk ones.

---

## 6. INPUTS FOR THE OPTIMISATION QUESTION

### 6 (a) The pack-processing wall by KIND of work — TNCM

Percentages of the 870.2 s cProfile run (whose absolute walls carry ≈ 1.2–2.2×
profiler overhead; the un-profiled totals in §1.1 are the honest walls).

| kind of work | seconds | % of 870 | basis |
|---|---|---|---|
| DSFTool text dump | **0 (cache hit)** | 0 | dump already on disk; the tool never runs DSFTool itself |
| parsing that dump text | ~1 | 0.1 | `dsf.read_dump` over 2.07 MB, 16,282 placements |
| **OBJ8 text parse** | **21.7** (9.4 un-profiled) | **2.5** | `parse_obj8` 494 calls, incl. `numpy.fromstring` 9.2 s |
| **shapely/GEOS calls** | **≥ 393.4** | **≥ 45** | `decorators.py:73 wrapped` cum; of which `union_all` 180.2 tottime / 297,130 calls, `distance` 60.9 / 2,034,231, `buffer` 34.0 / 650,434, `intersection` 21.3 / 96,388, `intersects` 17.9 / 29,199,009, `is_valid` 5.5 / 554,821 — **48,396,109 GEOS calls in total: many tiny, not few big** |
| shapely PYTHON-wrapper overhead alone | **32.2** | 3.7 | `decorators.py:73` own frame |
| **pure-Python per-vertex/per-pair arithmetic** | **≈ 210** | **≈ 24** | `neighbour_pairs` 77.1 + `math.hypot` 36.4 + `_narrow_rows` 51.8 + `_inside` 39.6 + `_point_tri_dist2_rows` 15.5 (partly numpy) |
| numpy (non-GEOS) | **≈ 60** | ≈ 7 | `ufunc.reduce` 25.2, `argsort` 11.2, `sort` 7.2, `generic.item` 5.1, `asarray` 2.4, `numeric.full` 2.4, misc |
| DEM sampling | 14.7 | 1.7 | `dem_production.sample` 10.6 / 863,711 + `z_many` 4.1 |
| interpreter overhead visible as such | ≥ 6.2 | 0.7 | `isinstance` 129,830,571 calls |
| pickling / IPC between pool children | **not on this path** | 0 | the capture is single-process. In the APP: the tile DEM is pickled once per worker via `ProcessPoolExecutor(initargs=(dem, pq))` (`driver.py:987`); per-airport results are small dicts; the progress `Manager().Queue()` carries 5-tuples |
| **lock waits** | **0 useful** | 0 | no lock exists in the v2 path; the app's `sem_wait` is an idle worker (§1.4) |
| disk cache read/write | ~0.5 | <0.1 | dump read 2.07 MB; `o4_object_footprints` 261 kB; partition cache 18–22 MB write when it is written |
| **total accounted** | ~870 | | |

OTHH comparison (RULINGS 17w, not re-measured here): structures stage
1,386 s / 29.18 GB; LEMD 378 s / 4.77 GB; VHHH 386 s / 6.69; HECA 154 s /
2.65. Same family of cost, a different driver (heavy resources × many
placements rather than one file × 41,220 components).

### 6 (b) Top 5 hot functions — parallelism and array-shape

| rank | function | data-parallel over independent units? | expressible as array ops? | array sizes |
|---|---|---|---|---|
| 1 | `shapely.union_all` (297,130 calls, 180.2 s) — from `contact.plan_hull` (101,922), `obj8_clip._union_rings` (65,473), `skirt._plan_union` (724), `obj8_grade.memo_union` (6,268), `wall_corridors._bands_of` (385), `object_cut.shell_reading` (52) | **YES — one call per COMPONENT, fully independent.** | Partly: shapely 2 exposes `shapely.union_all(..., axis=)` for a *grouped* bulk union, and `shapely.polygons()` already builds the input array in C (2,594,082 calls today, one per union). The per-component union itself is a GEOS cascade; a bulk form would need `axis=1` over a ragged set. **The real lever measured here is that the SAME component's union is recomputed per placement and never memoised.** | per call ≤ `OUTLINE_TRIS_MAX` = 4,000 triangles (`contact.py:190`), typically 3–40; 101,922 calls |
| 2 | `ground_fit.neighbour_pairs` (3,152 calls, 77.1 s + 36.4 s of `math.hypot`) | **YES — one MST per GROUP**, 5,945 groups, no shared state | **YES, completely** — measured 12.9× (§5.2) with identical output; the inner step is one `np.hypot` over an (n,) array | n up to **27,376**; Σ n² = 888 M; total feet 137,547 |
| 3 | `contact._narrow_rows` + `_inside` (4,465,496 calls each, 91.4 s) inside `_narrow_pass` | **YES — one candidate pair at a time**, already batched into stacked numpy rows (`_point_tri_dist2_rows`, 4,593 flushes over 4.47 M pair-sides) | Already partly vectorised; the remaining 91.4 s is **Python-per-pair row assembly**, 4.47 M dict/attr lookups. Expressible as one CSR-style stacked build over all pairs. | 2,261,597 pairs tested; `contact_batch_rows` chunking |
| 4 | `shapely.measurement.distance` (2,034,231 calls, 60.9 s) + `intersects` (29,199,009 calls, 17.9 s) | **YES** | **YES — these are exactly what `shapely.STRtree` bulk queries and the vectorised `shapely.distance(arrA, arrB)` are for.** 29.2 M scalar `intersects` calls is the clearest "many tiny calls" signature in the profile. | 29.2 M scalar predicate calls |
| 5 | `contact.placed_parts` (66.2 s cum) — `_place`, `np.linalg.norm(np.cross(...))`, `_feet`, `plan_hull` | **YES — one placed component at a time**, 101,922 iterations | Mostly: the affine `_place` (`contact.py:124`) and the areas/centroid are trivially bulk over ALL triangles of ALL components of one resource at once; today they are per component | per component: (m,3) triangles, (k,3) vertices; totals 5.71 M tris / 17.3 M verts |

`obj8.parse_obj8` is deliberately NOT in this list: 9.4 s for 1.72 GB
(≈ 180 MB/s), already numpy-in-C for `VT`/`IDX`; only the ordered `TRIS`/
`ATTR_*` walk is Python and it does not appear in the top 25.

### 6 (c) The calibration micro-benchmark

Done — §5.2. **12.9× from plain numpy, on the real input, byte-equal
output.** Read that as: the hottest pure-Python loop in the profile is a
"just vectorise it" case, and the remaining pure-Python mass
(`_narrow_rows`/`_inside`, 91.4 s) is the same shape. No native code is
required to reach it. What numpy does NOT reach is the 180 s of GEOS
`union_all` — that is already C++ and its lever is *calling it fewer times*
(memoising `plan_hull` per `(resource, component)`), not calling it faster.

### 6 (d) Delivery constraints any native option must meet (facts, no opinion)

* **Platforms shipped**: macOS arm64 (`macos-15`, frozen engine inside a
  signed+notarised `.app`), Windows x64 (`windows-latest`, frozen Qt app),
  Linux x64 (`ubuntu-22.04`, frozen Qt app) — `.github/workflows/release.yml`
  jobs at lines 18 / 245 / 374. CI is `.github/workflows/ci.yml`.
* **Native binaries ship today, per OS, as DATA**: `Ortho4XP/Utils/{mac,win,
  lin}` — `DSFTool`, `Triangle4XP`, `triangle`, `nvcompress`/`libnvtt`,
  `7zz`/`7z.exe`, `DDSTool`, and `osmium` (built by
  `.github/workflows/build-osmium.yml`; `Utils/lin` carries both x86-64 and
  `osmium-aarch64`). They are copied wholesale by
  `Ortho4XP.spec:96 ('./Utils', './Ortho4XP_Data/Utils')`. There is a
  `Utils/CMakeLists.txt` and `Utils/toolchains/` — an existing C/C++ build
  path for these tools.
* **Compiled Python wheels already frozen**: numpy 2.4.4, shapely 2.1.2
  (GEOS 3.13.1), scipy 1.17.1, GDAL 3.12.3, pyproj 3.7.2, highspy 1.15.1,
  osqp 1.1.3, rtree 1.4.1 (libspatialindex), osmium 4.3.1 (the Python
  binding, in ADDITION to the CLI), scikit-fmm, imagecodecs, tifffile,
  Pillow, PySide6. `Ortho4XP.spec` uses `collect_all('highspy')`,
  `collect_all('tifffile')`, `collect_all('imagecodecs')` and
  `collect_submodules('auto_patch_v2')`.
  **numba is NOT present. Cython is NOT present.** No compiler toolchain is
  invoked at app-build time for Python code.
* **Some wheels are VENDORED as `.whl` under `Utils/`** for install time
  (`Utils/mac/numpy-2.4.4-cp313-cp313-macosx_11_0_arm64.whl`,
  `Utils/win/gdal-…win_amd64.whl`, `Utils/win/scikit_fmm-…whl`) and are
  **stripped from the bundle** by `Ortho4XP.spec:128`
  (`a.datas = [d for d in a.datas if not d[0].lower().endswith('.whl')]`).
* **macOS signing/notarisation is the hard constraint** (`scripts/sign_app.sh`):
  every Mach-O is discovered with `find` + `file` and signed inner-first
  (never `codesign --deep`, lines 6-14); the script REFUSES if any
  discovered Mach-O is uncovered (line 187); and **Apple's notary unpacks
  archives and rejects any unsigned Mach-O inside one** — which is exactly
  why the vendored `.whl` files are removed (line 87-101, submission
  `0e71fbdf` Invalid). Any new native artefact must be a plain, signable
  Mach-O inside the bundle, not inside an archive, and must be built for
  arm64 with the hardened runtime.
* **The cross-platform identity gate**: spec §46 (owner 2026-09-17, Q 17d-1).
  Inputs entering an airport's frame are quantised at
  `emit.identity.input_quantum_m = 0.001 m`; with that in force the LP came
  out `17289×1918, 181 rounds, identical` on mac/Linux/Windows and **the
  emitted patch BODY was byte-identical on all three**. §46 (3) records the
  mechanism: "GEOS, numpy and scipy are deterministic across these platforms
  once they are fed the same doubles." **Outputs that feed identity**: the
  emitted `*_auto.patch.osm` body, the LP problem shape, every stage digest
  in `pipeline/xplat.py`. So a vectorised or native replacement must be
  bit-reproducible, not merely close — e.g. a change of summation order in
  an area or centroid reduction is visible. (`neighbour_pairs`' vectorised
  form in §5.2 returned byte-equal edges and distances on this input; that
  is one input, not a proof.)
* **An existing native OBJ8/DSF parser?** In this repo: **DSF yes, OBJ8 no.**
  `Utils/*/DSFTool` (Laminar's, 3 platforms) is the only native DSF reader
  and is already used, via a text dump behind a content-hashed cache.
  OBJ8 has no native reader here; `src/auto_patch_v2/airport/obj8.py` and
  v1's `obj8_reader` are the only parsers, and `tools/msfs_to_obj8`,
  `tools/obj8_building_gen`, `tools/obj8_preview`, `tools/obj8_geometry.py`
  are all Python. No third-party OBJ8 library is vendored.

---

## 7. ARTEFACTS AND WHAT I DID NOT DO

Durable lane directory (outlives this session):
`/Users/noah/XPTerrainBuilder/.lanes/packreadprofile/`

* `cap/TNCM.prof` — the cProfile stats of the whole capture (870.2 s run)
* `prof_TNCM.log` — that run's stdout + the top-45 tables + the traceback
* `capture_TNCM.log` — the first, un-profiled capture (901.8 s, 12.40 GB)
* `instr.log`, `instr_r015.log`, `instr_TFFG.log` — the un-profiled
  instrumented arms (radius 0.05, radius 0.015, TFFG)
* `TNCMnpairs.pkl` — the real n = 27,376 `neighbour_pairs` input + the
  n histogram
* `live_97736.txt`, `live_97738.txt`, `live2_97738.txt` — `sample` of the
  owner's stuck app children
* `packfacts.py`, `comps.py`, `instr_groups.py`, `prof_capture.py`,
  `whatif_prim.py` — throwaway instrumentation, scratch only, `src`
  untouched

**NO CAPTURE PICKLE EXISTS**: `--capture TNCM` cannot complete on this tree
(§1.5), so no `cap/TNCM.pkl` was registered and no `--replay` arm was
possible. The frames registry entry points at the profile and the
instrumented logs instead.

Not done:
* no `build_airport.py` run, no tile build, no five-airport sweep
* no fix of any kind, no spec, no source edit on the branch beyond this
  document
* TFFG's `group.derive` had not returned when this was written; its
  `neighbour_pairs` histogram and max RSS are missing
* `union_all`'s 297,130 calls are attributed to call sites by cumulative
  time, not by a per-site counter (shapely's decorator hides the caller in
  `print_callers`)
* the 12.9× what-if is one input on one machine, not a `--runs N` timing
* the GEML `obj8._witness` ring-validity interaction (§3) is described from
  the existing record, not re-measured here
