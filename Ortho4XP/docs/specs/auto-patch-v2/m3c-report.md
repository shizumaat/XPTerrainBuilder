# auto-patch-v2 — M3c report: the core smooths first (roads)

Lane `v2roads` (Fable, RULINGS 2026-09-04t-4; 03h), branch `lane/v2roads`
off main `ede79b2e`. Every file ≤ 1,000 lines (largest touched
`pipeline/build.py` 368; new `airport/road_profile.py` 512; `law/model.py` 900); no environment
reads; every constant from the TOML tables (one new section `emit.toml
[road_profile]`); no v1 `auto_patch` import — the ONE core import
(`O4_Vector_Utils.cap_lipschitz_profile`) is made in the adapter only.
Twins `tests/auto_patch_v2/test_m3c_roads.py` (6); the whole v2 directory
181 passed. Commits on the branch, not merged.

## 1. FACTS: what the core smooths, and what only v2 emits

Read in `O4_Vector_Map.build_poly_file` / `include_roads` /
`include_airports` and `O4_Vector_Utils.clamp_road_network`:

* ORDER. `include_airports` (auto_patch build → `include_patches` encodes
  the patch) runs FIRST; `include_roads` runs AFTER the patch is in the
  vector map. The core's road pass therefore never re-smooths a patch
  vertex: there are no shared vertices by construction — the road ribbon
  is cut back `lane_width + 2` (= 6 m) from `apt_area`
  (`treated_area` = the patch pavement union ∪ the apt.dat
  runway/taxiway/apron area) before it is buffered and encoded.
* POPULATION. OSM ways only: `big_roads` (road_level ≥ 1), `small_roads`
  (≥ 2), and — unconditionally whenever auto_patch runs — every
  level-5 highway class + airport rail classes inside each airport's
  inset bbox (`airport_small_roads`). Asserted `bridge` / `tunnel` spans
  are excluded (auto_patch owns spans; `bridge=no` is a road). A way is
  levelled when an endpoint lies in the airport array or any station's
  |DEM(centre) − DEM(shifted `lane_width`)| ≥ `road_banking_limit`
  (0.5 m); `max_levelled_segs` 200,000.
* THE CORE NEVER SEES apt.dat 1206 ground routes, DSF `.pol` road pages,
  or apt.dat 110 pavements: those surfaces exist in the mesh only through
  v2's patch.
* ALGORITHM. Per way, on the centreline, BEFORE the buffer:
  `refine_way` at ≤ `DEFAULT_ROAD_STATION_M` = 20 m stations (original
  vertices kept, `int(L // 20)` inserted per segment); terrain sampled on
  `tile.dem.alt_vec` (the production raster); `cap_lipschitz_profile` =
  the cap-Lipschitz mid-envelope `(floor + ceil) / 2` with
  `floor = max_j(z_j − cap·|s − s_j|)`, `ceil = min_j(z_j + cap·|s − s_j|)`
  — the terrain itself wherever the terrain is cap-lawful, the minimum
  sup-norm lift/cut elsewhere; cap = `tile.road_grade_limit` (default
  `SERVICE_ROAD_MAX_GRADE` = 0.08, the same constant as the law's
  `common.roles.service_road.longitudinal`); bridge-deck pins from
  auto_patch's confirmed decks. LATERAL: the buffered ribbon (±
  `lane_width` = 4 m) is encoded `INTERP_ALT` with `alt_vec_shift`: a ring
  vertex reads the nearest clamped station within `2 × lane_width` = 8 m
  (`Levelled_Roads.answer`, cKDTree), else the DEM shifted one lane width
  inward — both kerbs carry the centreline value (laterally level).
  `refine=100` m along the ring.

| surface | core smooths it? | v2 emits it? |
|---|---|---|
| OSM `highway=*` way outside `apt_area` + 6 m | yes (clamp + lateral levelling, if levelled) | no |
| OSM `highway=*` way inside / within 6 m of the patch pavement | clamp computed, ribbon NOT encoded (`apt_area` subtraction) | yes, where pavement lies under it (v2 face; the way is a `road_centerline` breakline / evidence) |
| apt.dat 1206 route | never seen | yes (`route` breakline, service_road faces) |
| DSF `.pol` road page / apt.dat 110 groundside pavement | never seen | yes (v2 face: strip / lot / open) |
| OSM `bridge=*` / `tunnel=*` asserted span | excluded | structures (v2 M4) |

## 2. THE ADAPTER — `airport/road_profile.py`

Contract: every vertex a road-family face OWNS (`senior_role` over
`roles_at` ∈ {service_road, service_junction, groundside_pavement,
parking_lot}; a kerb shared with the ground beside it is the road's, a
vertex shared with an apron/taxiway is the airside surface's and keeps the
DEM) gets THE VALUE THE CORE WOULD GIVE IT as its fit target
(`PlanarMap.preferred_z`, additive; `solve/assemble.py` reads
`preferred_z.get(i, dem_z)` — two lines; `Vertex.dem_z` stays the DEM for
seams, reports and readers):

* three sources, each clamped with the core's own
  `cap_lipschitz_profile` on v2's DEM (the production tile raster the
  core's `tile.dem` IS; OSM ways clipped to the WARM tiles —
  `ProductionDem.warm_tiles` / `tile_of_many` — so a road never composes a
  cold neighbour): `osm` (every levelled OSM way, whole way, as the core
  clamps it), `route` (every `road_centerline` breakline — a 1206 route or
  an OSM road's on-pavement part — as its own way), `axis` (a road face —
  service_road / service_junction / groundside_pavement; a lot has no axis
  in law, 04m — that NO way runs through: the ring's mid-line swept along
  its minimum-rectangle long axis every 10 m, `face_axis`);
* the answer is the PROJECTION onto a way, the profile interpolated at
  the projection (the continuous form of the nearest-station rule, exact
  at a station): the ways running THROUGH a road face answer that face's
  vertices within the face's own radius (`answer_radius_lane_widths` ×
  the face's half-width, width = area / half-perimeter, never below the
  core's 8 m); any other way within the core's 8 m answers a vertex as
  the core would (lots, slivers); nearest wins, an OSM way within 8 m
  outranks a route; no source → the vertex keeps the DEM and is COUNTED
  (`report.road_profile.by_role[role].dem`);
* the cap rows stay unchanged (`constraints/roads.py`: 8 % / 2 %
  cross-section / lot 5 % / lateral contiguity); v2 moves a vertex off
  the profile ONLY where a row binds — measured: the L1 roughness term
  (λ 0.5 vs 0) changes the whole-airport mean |z − profile| at CYXY by
  0.0004 m, so no station exclusion was added.

Law: `emit.toml [road_profile]` `station_m 20`, `lane_width_m 4`,
`answer_radius_lane_widths 2` — twin-held equal to
`DEFAULT_ROAD_STATION_M`, `O4_Cfg_Vars` `lane_width` / `road_grade_limit`
defaults and `Levelled_Roads.radius_m`. The tile's own `road_grade_limit`
/ `lane_width` reach the adapter (`Inputs.road_grade_limit` /
`lane_width_m`: the driver's task dict from `tile`, the CLI from the
global cfg); `None` = the law defaults.

Verify: `verify/roads.py::road_profile_agreement` — per road face the
mean/max |z − profile| and the count off beyond materiality (a report
figure, not a census family: the profile is a preference, never a cap).
Pipeline prints `road profile …` and `roads vs core profile …` lines and
records both in `<ICAO>.report.json` (`road_profile`,
`road_profile_agreement`).

## 3. CYXY shape 153 before → after

The owner's shipped shapeID 153 is planar face **147** (`dsf:pol120`,
service_road, 33 vertices, 11.7 m wide, 247 m long). It carries NO
centreline — no OSM way (nearest 36 m median), no 1206 route: the core
never sees it. Its profile is therefore the core's ALGORITHM on the
page's own axis (kind `axis`, 27 stations):

* the axis DEM rises 697.27 → 703.54 m over 247.1 m = **2.54 % mean**
  (station grades 0.2–5.6 %) — cap-lawful everywhere, so the clamped
  profile IS the terrain at every station (max |clamped − DEM| = 0.000):
  the ruling's "the core's smoothed profile" and "follows the terrain"
  coincide here by construction;
* BEFORE (base `ede79b2e`): each kerb pulled to its own DEM sample —
  mean |z − DEM| 0.108 m, max 0.661 m (at the far junction end);
* AFTER: 27/33 vertices answered by the axis (6 at the wide mouth,
  13.1–16.9 m off the axis, keep the DEM — counted); the road is
  LATERALLY LEVELLED onto its axis — both kerbs of every station carry the
  axis value (z − profile = **+0.000** at 15 of 27 vertices, every vertex
  from s = 0 to s = 129 m), mean |z − profile| 0.130 m, max 0.744 m; mean
  |z − DEM| 0.182 m. The residual is the last 25 m (s ≥ 222 m) where 147
  meets three other service-road faces and the lot/apron deficit the
  `why` report attributed (04q) propagates through the road rows —
  unchanged from before (max 0.661 → 0.672 there).

Whole CYXY (harness closing build): 639 road-family vertices, 446
preferred (osm 335, route 55, axis 56), 193 DEM fallback (127 of them
parking-lot vertices beside no road, 40 service_road, 26 groundside);
the preference itself moves 382 vertices off their own DEM sample (max
0.96 m — lateral levelling of cross-sloped pages and one OSM clamp);
mean |z − profile| 0.409 m, max 3.95 m, 228 off in 40 of 49 faces. The
large deviations are the SAME faces as before (route6 3.82 → 3.95,
dsf:pol23 3.43 → 3.42, lot pav4 2.13 → 2.10 m off their DEM): roads
dragged by the apron/lot rows they touch (the 03k / 04s class), not by
this adapter — 22 faces read |z − profile| ≤ 0.05 m.

## 4. Agreement with the core at the shared boundary

There is no shared vertex: the core's ribbon stops 6 m outside
`apt_area`. Where a v2 road face and a core ribbon are the same OSM way,
both read ONE profile — the same `cap_lipschitz_profile` on the same
raster (`ProductionDem` = `tile.dem`; twin: adapter vs
`clamp_road_network` + `Levelled_Roads.answer` identical to 1e-6 where
the terrain is lawful, ≤ 0.05 m at clamped stations — the arclength
metrics differ by 0.3 %). The 6 m band between them is raw-DEM
triangulation; with both sides on one profile it ramps ≤ the cap.

## 5. Census

| airport | build | oracle (`census.py`) before → after | v2 verify |
|---|---|---|---|
| CYXY | harness `build_airport.py CYXY --engine v2`, tag `CYXY_20260904T125727`, artifact-ledger key `1a01cc4112f2`, body `dd4787779be3`, 5.9 s | ADJUDICATED **0 / 0** PASS | 0 |
| SPLP | standalone CLI (8.6 s) | **0 → 0** | 3 within_shape (pre-existing, same on base) |
| SPJC | standalone CLI (54 s) | **8 → 8** (junction\|junction at the apron cap — lane `v2caps`'s rows, unchanged) | 2 adjacent_ground_tear (pre-existing, same on base) |

SPLP: 94 road vertices, 17 preferred (11,999 OSM ways clamped, 0.57 s),
mean |z − profile| 0.194 m. SPJC: 424 vertices, 367 preferred (osm/route/
axis 13), mean 0.566 m, max 4.86 m (the pad-frontage class).

## 6. Not done / open

* `pipeline/why.py` / `solve/why.py` print z vs DEM, not vs the preferred
  profile (lane `v2relax` owns `why`) — a `why` reading of a road should
  show the profile column.
* The axis mid-line is a minimum-rectangle sweep: fine for strips
  (CYXY 147), crude for L-shaped pages (their far vertices fall outside
  the face radius and keep the DEM — counted, never invented).
* No build-time review: road profile stage 0.10–0.57 s (CYXY / SPJC);
  below the 0.6 s budget line.
