# auto-patch-v2 M1b — classification round from the owner's CYXY sim read (RULINGS 2026-09-04j)

Lane `v2class`, branch `lane/v2class` off main `2821a0db`. The owner's
first sim read of v2 (app 1.0.279, CYXY) found four CLASSIFICATION items;
this report is the attribution, the law, the mechanism and the recipe for
reading any shapeID's verdict.

## 1. Attribution — what the classifier had read, per shapeID

The owner's patch: `Patches/+60-140/+60-136/CYXY_auto.patch.osm` (shared
repo, read-only). Evidence printed with `python -m auto_patch_v2 explain
CYXY --shape N --patch <that file>` (section 5).

| shapeID | shipped role (cap) | what the classifier had read | owner | after (this branch) |
|---|---|---|---|---|
| 69 | `service_junction`, `o4_grade_law_cap=0.01` | ONE 45,248 m² cell: fifteen DSF pavement pages (`asphalt_5L`, `asphalt_L/plain`) + apt.dat `pav0` dissolved into one pavement union; `n_taxi=0`, kind `apron`, then "touched by free ground-route parts only → service" (user 2026-07-02); OSM `highway=service` (2,054 m of roads and aisles inside) was NOT read by v2; the 1 % came from lateral contiguity with the apron | roads ≤ 8 %, lots ≤ 5 %, cut at the mouths | 13 `parking_lot` faces (pol116/117/118/124/125/128/131/132/133 + small pages), 2 `service_road` strips (`pav0`, `dsf:pol23`) |
| 161 | `service_junction`, cap 0.01 | 1,097 m² of `dsf:pol120` (an 11.7 m-wide page carrying 224 m of 1206 route to a turnaround): the free-road centreline cut split the page along its axis; the half became "service" | same class as 69 | `service_road` (the whole page is one strip face) |
| 127 | `apron` | ONE 37,557 m² cell: `pav17` "Apron off E at G" + `pav29` "New Taxiway 41" (15,191 m², 621 m of 1206 ring road) + `pav30` "New Taxiway 40" (335 m of route) + `pav1/2/10` + `dsf:pol130` (a lot page, 145 m of OSM road, no taxi centreline) + `pol120` half, `pol8`; the union dissolved every source boundary and the blob's width > 50 m read apron; the free-road cut only carved the OUTER half-strips of the ring road | apron never merged with groundside | `apron` (`pav17`, 10,434 m² + its 50 m proximity band as `junction`), `service_road` strips `pav29`/`pav30`/`pol120`, `parking_lot` `pol130`, `apron` `pav1`/`pav10` (a stand) |
| 227 | `groundside_pavement` | `dsf:pol19` (20,136 m², `lib/airport/ground/pavement/asphalt_L/plain.pol`): kind `apron`, 3 taxi chains (44/45/46) touching, then DEMOTED — no pavement touch-chain to a runway (the page is 20 m clear of `pav29`, across a pad) | taxiway | `junction` (the proximity band of the through lane; taxi family caps) |
| 229 | `groundside_pavement` | same page, corridor kind (width 13.8 m on chains 44/46), demoted | taxiway | `cross_connector` |
| 230 | `groundside_pavement` | same page, proximity band, demoted | apron | `junction` — residual: it lies within 50 m of a through taxi route (user 2026-07-06 "< 50 m from a centreline is NOT apron"); reported, not overridden |
| 231 | `groundside_pavement` | same page, apron kind beyond the band, demoted | apron | `apron` |

Root causes (three), each with its fix:

1. **The pavement union dissolved source boundaries.** apt.dat 110
   polygons and DSF pages were unioned before slicing; only taxi centrelines
   and free-route centrelines cut. A road page beside an apron, a lot page
   beside a road, all became one face. Fix: `classify/sources.py` reads
   every source polygon once and names it a road STRIP, a parking LOT or
   OPEN pavement; strips and lots are cut at their own boundary (the mouth
   is where the road's corridor crosses the lot's boundary), the apron
   never absorbs them.
2. **OSM roads were not evidence.** v2 M1 carried the 1206 routes only.
   Fix: `evidence.py` `_osm_roads` — OSM `highway=service` ways on pavement,
   deduped against the 1206 routes (`rules.osm_roads`), with
   `service=parking_aisle` as lot evidence and `amenity=parking` polygons as
   lot cover (`airport/osm.py` now keeps `amenity`/`parking`). On THIS corpus
   the airport feeds carry no `amenity=parking` and no `service=*` subtags
   (grepped all six CYXY feeds): the lot verdict at CYXY rests on the
   geometric fallback — an OSM road grid (≥ 3 merged pieces per 100 m of
   half-perimeter) in a polygon no taxi centreline or startup touches.
3. **The runway touch-chain ignored the taxi network.** A page a NETWORK
   taxiway runs onto, clear of every other pavement, was demoted landside.
   Fix: `Chain.runway_network` (BFS over the 1202 network from the runway
   nodes) seeds the chain walk.

Two more verdict rules fell out of the measurement and are stated in
`rules.toml` (all thresholds there; none in code):

* `lot.min_road_fraction = 0.2` — a road clipping a polygon's corner names
  nothing (CYXY `pav4`: 41 m of OSM road on a 5,338 m² hangar-side strip
  read as a road strip and the v1 building-frontage 1 % clamp then minted
  24 oracle rows on it).
* `lot.apron_name_tokens = ["apron"]` — an apt.dat description naming an
  apron (or OSM `aeroway=apron` cover) makes its unnamed lanes apron
  evidence for nothing (RULINGS 2026-09-03j: stand lanes inside an apron
  are apron); only a NAMED taxiway running ON the pavement (≥ half its
  length inside it) keeps taxi law there — `pav9` "Apron 1 and E" keeps
  taxiway E as a corridor; `pav17` is apron although E/F/G run along its
  edge.

## 2. The `parking_lot` role

* `law/precedence.toml` `[roles]`: `parking_lot = { family = "common",
  side = "groundside", value = true, aeroway = "apron", oracle_role =
  "groundside_pavement" }`, last in `authority.order` (junior-most governed:
  the road owns the mouth value, the lot conforms — 03i).
* `law/rulesets.toml` `[common.roles]`: `parking_lot = { longitudinal =
  0.050, transverse = 0.020 }`. **Transverse is the road law's lateral 2 %
  until the owner states otherwise** — and it is a recorded number only: a
  lot has no cross-section axis, so no generator prices it (open question 2).
* Solve: `constraints/roads.py` `road_within_shape` prices every lot ring
  pair at 5 % (one literal added beside `groundside_pavement`; v2law2 lane
  territory, minimal edit).
* **Oracle.** `check_grade._GROUNDSIDE_ROLES` has no `parking_lot`; an
  unknown role is judged AIRSIDE at the CLI default cap — rows mispriced,
  not dropped. The emitter therefore writes the alias: `role=
  groundside_pavement class=parking_lot o4_grade_law_cap=0.05`; the census
  composes the way-level cap as a MINIMUM with the role's 8 %, so it prices
  exactly 5 % on the groundside partition. The `role` register field
  `oracle_role` is validated by the loader (must name a registered,
  un-aliased role of the same side). The law twin
  (`tests/auto_patch_v2/test_law_tables.py`) carries two RULED-DEVIATION
  entries (`precedence.order`, `groundside partition`, "owner 2026-09-04j").
  v2's own verify reads `parking_lot` directly.

## 3. Cut at the mouths — the mechanism

`classify/sources.py` `classify_sources` → one `SourceRecord` per source
polygon (width = area / half-perimeter, road/OSM/aisle/through lengths,
merged road pieces, taxi length, startups, parking and apron cover, class,
reason). Classes:

* **strip** — carries a road (1206 or OSM, not an aisle), touches no taxi
  centreline, and is ≤ `narrow_road_width_m` (12 m) wide, or ≤
  `service.free_max_width_m` (25 m) with ≥ 60 % of its half-perimeter
  covered by THROUGH road (each end on the boundary or at an interior
  junction) and ≤ 2 merged road pieces per 100 m (measured CYXY: strips
  0.2–1.5, lots 2.9–4.6).
* **lot** — not a strip, no taxi, no startup, not apron-named/covered, and
  an OSM road or aisle grid inside (or `amenity=parking` cover ≥ 50 %).
* **open** — everything else (the M1 slice model unchanged).

`roles.py`: strip and lot boundaries join the slice lines (`_cut_lines`);
a free-route centreline inside a strip does not cut again; a face lying
≥ half in a strip is `service_road`, in a lot `parking_lot`, with the
source record in its evidence. Demoted (landside) apron/taxi faces become
`parking_lot` when a road reaches them or a road/lot face touches them,
else stay `groundside_pavement` (an island nobody drives to). A stand
(1300) inside a face keeps it apron even when only routes touch it.
`planar/zones.py`: airside zone bands are cut back `groundside_cutback_m`
(0.6 m, `zones.toml`) from groundside pavement so a road's DEM climb never
shares a vertex with a taxi strip (measured: one shared corner vertex tore
a taxi:B zone band 3.03 m in 5.6 m; the stand-off terraces — groundside
terrace law, the mixed-pad precedent 09-01i). Faces stay a partition,
T-vertices 0 (twin asserts it).

## 4. Measurements

CYXY, this branch, offline replay vs main `161f4dda` (both
`python -m auto_patch_v2 build`), then the harness closing build
(`build_airport.py CYXY --engine v2`, ledgered — tags in the lane report):

| role | main m² | v2class m² | delta |
|---|---:|---:|---:|
| groundside_pavement | 73,849 | 8,858 | −64,991 |
| parking_lot | 0 | 63,672 | +63,672 |
| service_junction | 52,470 | 85 | −52,385 |
| junction | 78,687 | 110,277 | +31,590 |
| service_road | 2,660 | 33,184 | +30,524 |
| cross_connector | 23,567 | 50,591 | +27,024 |
| primary_parallel | 157,898 | 140,987 | −16,911 |
| stub | 37,929 | 26,247 | −11,681 |
| apron | 140,891 | 132,914 | −7,977 |

Oracle census CYXY 0/0 (was 0/0); v2 verify 0 rows; solve optimal
(harness tag `CYXY_v2class2`, artifact-ledger key `10437fdf6f7d`, 7.5 s).
v1 role agreement (`test_role_agreement.py`): exact 48.1 % → 53.6 %,
family 71.4 % → 70.8 % (the lots are a new class v1 does not have; every
new disagreeing pair carries its reason).

SPLP (`SPLP_v2class2`, key `ad9a377ad56f`): oracle 0/0 (was 0/0); v2
verify 3 `within_shape` rows on `pav0` cross-connectors — IDENTICAL on
main's control replay (pre-existing v2-verify/oracle disagreement, M4c
residual), not this round's. `dsf:pol13` (39,382 m², 2,353 m of OSM road
in 12 pieces, no taxi centreline, no startup) → `parking_lot`:

| role | main m² | v2class m² | delta |
|---|---:|---:|---:|
| parking_lot | 0 | 48,563 | +48,563 |
| apron | 57,816 | 9,284 | −48,532 |
| (every other role) | | | ±0 (runway +15) |

SPJC (`SPJC_v2class2`, key `e6877264f22f`): oracle 0/0 (was 0/0); v2
verify 0. Lots: `pav46` "New terminal" (99,924 m², no startup among the
airport's 193, no taxi centreline, 435 m of OSM road in 7 pieces — the
landside terminal forecourt v1's dossier called "landside terminal-frontage
parking"), `dsf:pol69`/`pol70` (road grids of 17/10 pieces), `pol34`,
`pol65`; strips `pol71`/`pol32`/`pol33`:

| role | main m² | v2class m² | delta |
|---|---:|---:|---:|
| parking_lot | 0 | 156,963 | +156,963 |
| apron | 804,253 | 676,609 | −127,644 |
| junction | 564,014 | 649,502 | +85,488 |
| cross_connector | 113,568 | 61,457 | −52,112 |
| stub | 258,501 | 221,326 | −37,175 |
| groundside_pavement | 47,891 | 17,796 | −30,095 |
| service_road | 12,706 | 27,969 | +15,263 |
| service_junction | 13,540 | 0 | −13,540 |

The SPJC taxi-family reshuffle (junction ↑, stub/cross_connector ↓) is the
apron-name rule: apron-described pavements carrying only unnamed lanes now
read apron/junction instead of corridors (03j) — same taxi caps, the
`plane_gradient` family differs. Not sim-read by the owner yet.

## 5. How to read the evidence for a shapeID (the owner's recipe)

    cd Ortho4XP
    PYTHONPATH=src venv/bin/python -m auto_patch_v2 explain CYXY --shape 127
    PYTHONPATH=src venv/bin/python -m auto_patch_v2 explain CYXY --shape 69 --patch /path/to/CYXY_auto.patch.osm
    PYTHONPATH=src venv/bin/python -m auto_patch_v2 explain CYXY --at 60.70385,-135.06947

`--shape N` reads way `shapeID=N` (the role-carrying ring) from the shipped
patch — default `Patches/<block>/<tile>/<ICAO>_auto.patch.osm` in the
engine tree — and prints every v2 cell overlapping it (≥ 25 m²): role,
side, kind, ref, the evidence record the verdict used (`kind`, `n_taxi`,
`shared_m`, `width_m`, `near_route`, `apron_named`, `source_class`,
`source_reason`, `demoted`, `road_evidence`, …), each source polygon under
it with its own record and the one-line reason for its class, and the
centrelines that touch it (taxi chains with `(network)` when they reach a
runway through the 1202 graph, 1206 routes, OSM roads with `(aisle)`).
`--at LAT,LON` does the same for the cell containing the point. The
classification runs fresh from the loaders (read-only; a cold DEM frame is
accepted — no elevation is read), ~4 s at CYXY.

Reading a verdict: `source_class=strip` → the face is a road because its
source polygon is; `source_class=lot` → a lot; `kind=corridor` with
`width_m` → a taxi sub-role from the corridor test; `near_route=1`
→ the 50 m proximity band (junction); `demoted=1, road_evidence=1` → a
landside face a road reaches (lot); `apron_named=1` → the author called it
an apron and only a named taxiway on it could have made it a corridor.

## 6. Open questions for the owner

1. **Lot evidence on this corpus is geometric.** The airport OSM feeds
   carry neither `amenity=parking` nor `service=parking_aisle`; the reader
   for both is in and idle. Widening the feed query is a data refresh
   (`--refresh-data`), not a lane act — wanted?
2. **Lot transverse 2 %** is recorded in `rulesets.toml` but unpriced (no
   axis on a lot). Keep as a recorded number, or price all lot pairs at 2 %
   (a flatter lot than the 5 % along-slope the owner stated)?
3. **shapeID 230** reads `junction` (taxi caps) under the 50 m proximity
   ruling; the owner called it apron. A page-by-page override is not law —
   does the proximity band stop at an apron page a taxiway merely ends on?

## 7. Not done

* No five-airport sweep (orchestrator's).
* `constraints/roads.py` one-literal edit reported to lane v2law2 for
  co-ordination; no other constraints/solve/structures file touched.
* v1 (`src/auto_patch/`) untouched — `parking_lot` exists in v2 only.
