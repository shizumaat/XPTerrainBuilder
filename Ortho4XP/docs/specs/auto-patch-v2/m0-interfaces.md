# auto-patch-v2 — M0: frozen interfaces, the law as data, the M1 brief

Lane `v2m0` (Fable, design deliverable per RULINGS 2026-09-03d; owner
amendment 2026-09-03: law values in human-editable TOML). Package:
`Ortho4XP/src/auto_patch_v2/`. Nothing in it imports v1 (`auto_patch`);
v1 is the reference and the census oracle only.

## 1. Packages and the dependency direction

```
law  ->  model  ->  solve  ->  emit          (M0: these four exist)
         ^  ^         ^
airport  |  |    constraints  ->  verify      (M1/M2 producers; import model + law)
classify |  |                     pipeline    (M2; the only reader of the environment)
planar  -+--+
```

A package imports only those to its left. `law` imports nothing from v2.
`model` holds DATA ONLY (plain dataclasses/tuples; no shapely, no numpy —
`tests/auto_patch_v2/test_model.py::test_no_v1_import_no_env_gate_no_geometry_in_model`
enforces it, along with "no `os.environ`", "no `auto_patch` import", and
"every file ≤ 1,000 lines").

| package | files (M0) | line budget (total, incl. M1/M2 growth) |
|---|---|---|
| `law/` | `model.py` (schema+loader, 720), `tables.py` (accessors, 190), six `*.toml` | 1,200 py + tables |
| `model/` | `frame.py`, `airport.py`, `planar.py`, `constraints.py` | 1,200 |
| `airport/` (M1) | `apt_dat.py`, `cifp.py`, `osm.py`, `dem.py`, `dsf.py`, `pack.py`, `load.py` | 4,000 |
| `classify/` (M1) | `roles.py`, `evidence.py` | 2,000 |
| `planar/` (M1) | `build.py`, `overlay.py`, `chords.py`, `zones.py`, `index.py` | 3,000 |
| `constraints/` (M2) | one module per generator family | 5,000 |
| `solve/` | `api.py` (M0), `assemble.py`, `highs.py`, `osqp.py`, `iis.py` (M2) | 1,500 |
| `emit/` | `surface.py`, `osm_adapter.py`, `s2_adapter.py` (M0); writers (M2) | 1,500 |
| `verify/` (M2) | pure functions over `GradedSurface` + `Law` | 1,500 |
| `pipeline/` (M2) | orchestration, CLI, progress, stage cache, config schema | 800 |

Every file ≤ 1,000 lines (a larger file needs a written reason, 2026-09-03d).

## 2. The law files (the amendment)

Six TOML files under `src/auto_patch_v2/law/`, read by `tomllib` (stdlib):

| file | holds |
|---|---|
| `rulesets.toml` | `[resolution]` (FAA/ICAO selection), `[common]` + `[common.roles]` (authority-independent role caps), `[icao.*]`, `[faa.*]` — runway / taxi / strip / end_skirt / resa / raoa / drainage |
| `zones.toml` | adjacent-ground zones 1–2 (lip, band, half-widths per class), `beyond_zone2 = "dem"`, pockets |
| `structures.toml` | tunnel (bore datum 5.1, wall gap 0.6, crest = "dem"), bridge (clearance 5.1 / minimum 4.2, deck datum), building pad (weld, no footprint outside, cut-back 0.6), basin, retaining wall |
| `emit.toml` | chords (60 m pavement, 50 m apron interior, 12 m stations), identity (11 dp, 0.5 m distinct spacing), materiality (0.01 m, 0.01 pp, 0.5 m step), no-step window/K |
| `precedence.toml` | `[authority] order` (the total order), `[roles]` register (family / side / value / aeroway), `[taxi_family]`, `[runway_family]` |
| `families.toml` | one table per law family: `measures`, `parameter` (dotted path into the tables — the loader refuses one that does not resolve), `roles`, `pairs`, `ruling`, `solver` |

Value grammar: a grade is a FRACTION (`0.015`); a key ending `_m` is
metres; a class table is `{ by_code = { "1" = …, "4" = … }, default = … }`
(ICAO code number) or `{ by_letter = { "A" = …, "F" = … }, default = … }`
(code letter / FAA width proxy) or a bare number (one value for all
classes); an absent class = "the authority states no number" (a no-op); a
rate is `{ grade = 0.02, per_m = 30.5 }`. Each key carries a one-line
comment with meaning, unit and ruling id.

The loader (`law/model.py`, `load_tables(dir)`) refuses: an unknown key,
a missing required key, a non-numeric cap, a grade outside [0, 0.2], a
negative length, a datum string outside its enumeration, a role in
`order` not in `[roles]`, a duplicate in `order`, a `common` role without
a cap, a family whose `parameter` does not resolve, a family naming an
unknown role. The twin `tests/auto_patch_v2/test_law_tables.py` checks
every numeric value against v1's constants (v1 imported in the test only;
239 constants at M0), that every `check_grade.LAW_FAMILIES` key is a v2
family with the same bucket, that the schema round-trips through a copy,
and that each refusal above fires.

### Adding a cap — worked example

Suppose the owner rules a helipad (FATO) longitudinal cap of 2 %:

1. `precedence.toml`: add the role and its place in the order —
   `helipad = { family = "common", side = "airside", value = true, aeroway = "helipad" }`
   and insert `"helipad"` into `[authority] order` after `"runway_crossing"`.
2. `rulesets.toml` `[common.roles]`:
   `helipad = { longitudinal = 0.020, transverse = 0.020 }  # FATO (RULINGS 2026-xx-yy)`.
3. `families.toml`: nothing, if `within_shape` (`roles = ["all"]`) is the
   family that measures it; otherwise add a `[helipad_grade]` table with
   `parameter = "common.roles.helipad.longitudinal"`.
4. Run `venv/bin/python -m pytest -n0 tests/auto_patch_v2/test_law_tables.py`:
   the loader accepts it (or names the key it refuses). If v1 has no
   matching constant the twin needs no change; if v1 does, add one
   `c.eq(...)` line so drift stays impossible.

No Python changes. `Law.for_airport(icao)` picks it up on the next load.

## 3. Frozen public API (signatures)

### `auto_patch_v2.law`
```python
load_tables(law_dir) -> LawTables                      # validates; raises LawError
Law.load(law_dir=None, *, ruleset=None) -> Law
Law.for_airport(icao, ruleset=None, law_dir=None) -> Law   # FAA/ICAO as v1 resolve_ruleset
Law.tables: LawTables; Law.ruleset_key: str; Law.ruleset: Ruleset
resolve_ruleset(resolution, icao) -> str
# tables.py accessors (all pure over Law):
role_cap(law, role, code_number=None, code_letter=None) -> RoleCap | None
role_family(law, role) -> str; role_side(law, role) -> str; is_value_role(law, role) -> bool
authority_rank(law, role) -> int; senior_role(law, roles) -> str
zone_class(law, role) -> ZoneClass | None
zone2_half_width_m(law, role, code_number=None, code_letter=None) -> float | None
zone_bounds(law, role, d_m, code_number=None, code_letter=None) -> (floor|None, ceiling|None)
runway_end_zone_length_m(law, runway_length_m) -> float
family(law, key) -> Family; families_for_role(law, role) -> tuple[Family, ...]
chord_cap_m(law, role) -> float; identity_dp(law) -> int; materiality_m(law) -> float
```

### `auto_patch_v2.model`
```python
frame.Frame(icao, origin=(lat, lon), identity_dp, crs="")   # .transformers() -> (to_xy(lon, lat), to_ll(x, y)); .key(lat, lon)
frame.identity_key(lat, lon, dp) -> (lat, lon)
airport.Airport(icao, name, frame, elevation_m, runways, pavements, linear_features,
                taxi_nodes, taxi_edges, ground_routes, boundaries, startups, osm_ways,
                buildings, dsf_objects, pack, dem, ruleset_key)
airport.Runway(id, width_m, surface, ends=(RunwayEnd, RunwayEnd), code_number, code_letter)
airport.RunwayEnd(name, xy, ll, displaced_m, overrun_m, threshold_elev_m|None, cifp_source)
airport.Pavement(id, surface, outer: Ring, holes, description)
airport.LinearFeature(id, line_type, points, closed)
airport.TaxiNode(id, xy, usage); TaxiEdge(a, b, name, one_way, is_runway, width_class)
airport.GroundRoute(a, b, name, one_way); Boundary(id, outer, holes); Startup(name, xy, heading_deg, kind)
airport.OsmWay(id, kind, points, closed, tags); Building(id, outer, holes, source, height_m, levels, dsf_object)
airport.DemSample (Protocol): z(x, y) -> float; bounds() -> (xmin, ymin, xmax, ymax); provenance
airport.DsfObject(id, path, xy, heading_deg, footprint, hard_deck, deck_top_m, y_offset_m)
airport.SceneryPack(name, apt_dat_path, apt_dat_sha256, dsf_paths, dsf_sha256)
planar.PlanarMap(icao, vertices, edges, faces, breaklines)   # .edges_of_vertex(), .faces_of_edge(eid)
planar.Vertex(id, xy, key, dem_z, incident_faces); Edge(id, a, b, left_face, right_face, kind)
planar.Face(id, role, ref, ring, holes, code_number, code_letter, side); Breakline(id, kind, ref, edges)
planar.validate(pm) -> None                                # raises PlanarError naming I1..I7
constraints.Source(generator, ruling, inputs)
constraints.Pin(v, z, source); Diff(a, b, cap, d, source); Flat(group, source)
constraints.Band(v, lo, hi, source); Offset(a, b, min_delta, source)
constraints.ConstraintSet(pins, diffs, flats, bands, offsets)   # .counts(), .rows(), .vertices(), .by_generator(), .merged(), .to_sparse() [M2]
```

### `auto_patch_v2.solve`
```python
solve(planar, constraints, weights: Weights, options: Options | None) -> Solution   # M2
Weights(by_role, zone3, smoothness, default); Options(backend=HIGHS, feasibility_tol_m, max_iterations, time_limit_s, diagnose_iis, verbose)
Solution(z: tuple[float, ...], status: Status, residual: Residual | None, iis: tuple[(Row, Source), ...], backend, iterations, wall_s, message)
```

### `auto_patch_v2.emit`
```python
surface.GradedSurface(icao, ruleset, origin, crs, identity_dp, vertices, faces, breaklines, provenance)
    .to_dict(z_dp=2) / .to_json(z_dp=2) / .from_dict(d) / .from_json(text);  surface.SCHEMA (JSON schema)
osm_adapter.write_patch(surface, law, out_dir, sidecar=None) -> PatchPaths   # M2; sidecar keys ⊆ SIDECAR_KEYS
s2_adapter.rasterise(surface, cells, step_deg) -> tuple[RasterPatch, ...]     # M6 (format unpublished)
```

Planar-map invariants I1–I7 are in `model/planar.py`'s docstring; the
`to_sparse()` contract in `model/constraints.py`'s `ConstraintSet`.

## 4. M1 brief skeleton — the planar map for CYXY

Implementation lane (Opus). Deliver `airport/`, `classify/`, `planar/`
against the frozen `model` types; no judgement calls — every question
below has its answer here or in the law tables.

**Inputs (all read-only; the shared data repo, RULINGS `e9daef5`):**

| input | path |
|---|---|
| apt.dat (CYXY, Global Airports) | `/Users/noah/X-Plane 12/Global Scenery/Global Airports/Earth nav data/apt.dat` (the scenery signature: this file + the DSF; custom packs excluded by name exactly as v1 `driver.py:404-425`) |
| CIFP | `/Users/noah/X-Plane 12/Custom Data/CIFP/CYXY.dat` (`cifp_data_path` in `/Users/noah/XPTerrainBuilderData/Ortho4XP.cfg`; the worktree cfg ships it EMPTY — the loader takes the path as an argument, never from a cfg) |
| OSM | `/Users/noah/XPTerrainBuilderData/OSM_data/+60-140/+60-136/+60-136_airports.osm.bz2`, `…_airport_small_roads.osm.bz2`, `…_big_roads.osm.bz2` |
| DEM | `/Users/noah/XPTerrainBuilderData/Elevation_data/+60-140/N60W136.hgt` + inset `N60W136_airport_insets/CYXY_hrdem.tif` (+ `CYXY_hrdem.json`, `index.json`) |
| DSF objects | `/Users/noah/XPTerrainBuilderData/Airport_mod_cache/CYXY Whitehorse/+60-136.dsf.f1f00050.text` (DSFTool dump; `o4_object_*_+60-136.cache`) |
| v1 patch (the oracle's subject) | `/Users/noah/XPTerrainBuilderData/Patches/+60-140/+60-136/CYXY_auto.patch.osm` (+ `.axes.json`) |

**Frame:** `Frame("CYXY", origin=(apt.dat row-1 lat/lon of the airport
reference point), identity_dp=law.emit.identity.coordinate_dp)`.

**Steps (each a pure function, each with a twin):**
1. `airport.load(icao, apt_dat, cifp_dir, osm_dir, dem, dsf_dump) -> Airport`:
   rows 1/100/110(+111-116)/120/130/1201/1202/1206/1300 (v1
   `apt_dat_reader.py:106-121, 531-610` is the reference for the record
   grammar; 102 helipads are parsed and reported, not graded); CIFP
   threshold elevations joined to runway ends by designator; OSM ways
   with the tags of interest; buildings from OSM + DSF footprints;
   `DemSample` over the .hgt with the inset applied (bilinear).
2. `classify.roles(airport) -> Mapping[pavement id, Role evidence]`: one
   scorer, one output; roles are the `precedence.toml` register.
3. `planar.build(airport, roles, law) -> PlanarMap`: overlay every
   pavement/pad/zone polygon into ONE planar subdivision (shapely
   `unary_union` of boundaries then polygonize; the shapely import lives
   in `planar/` only), snap by 11-dp identity (never proximity), densify
   chords to `chord_cap_m(law, role)`, insert breaklines (runway
   centrelines at `station_spacing_m`, taxi centrelines from 1202, road
   centrelines from 1206/OSM), zone rings at `lip_width_m` and
   `zone2_half_width_m`, sample DEM per vertex, then `validate()`.

**Acceptance (the M1 bar, plan §3):**
- `validate(pm)` passes; zero T-vertices by I5 (the twin injects one and
  expects `PlanarError`).
- Roles match v1's on ≥ 95 % of pavement AREA: the twin reads v1's patch
  ways (`aeroway` + `role` + ring), intersects each v2 face with the v1
  ring of the same `ref`, and reports agreement by area; differences
  listed per face in the report.
- No vertex without a DEM sample; vertex count reported (CYXY v1: 6,660
  nodes; v2 target ≤ that).
- `pytest -n0 tests/auto_patch_v2` green; build of the map < 5 s.

**The v1 census oracle** (M2 reads it; M1 records the baseline):
```
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/<lane>/Ortho4XP
venv/bin/python tools/harness/census.py /Users/noah/XPTerrainBuilderData/Patches/+60-140/+60-136/CYXY_auto.patch.osm
```
(Appendix B §3 baseline: 160 law-true rows, 67 airside.) The v2 patch,
once `emit/osm_adapter.write_patch` exists, is censused with the same
command — the sidecar it writes carries exactly `SIDECAR_KEYS`.

## 5. Open questions for the owner

1. ICAO code 1/2 runways: the tables say 2.0 % but the v1 census prices
   every runway ring pair at a flat 1.5 % (`LAW_TRUE_KNOBS.max_grade_pct`)
   — v2 solving to the tables would read red on the oracle for a code 1/2
   airport (none of the three milestone airports; CYXY is code 4).
2. Tunnel wall band WIDTH: no named constant exists in v1 (only the
   0.6 m gap, RULINGS 2026-09-01c/e); `structures.toml` has no
   `wall_width_m` until the owner states one.
3. The apron chord rule: encoded as "apron interior vertex spacing ≤
   50 m" (the lattice spacing) — is that the intended reading of "the
   apron rule", or the 60 m ring chord plus a separate interior lattice?
4. `road_cross_section` transverse cap for `tunnel_ramp` (0.020, the
   road value) is an M0 choice by analogy (the ramp carries vehicles); v1
   states no transverse cap for the ramp.
5. Runway `transverse_min` 1.0 % and taxi `transverse_min` are RECORDED
   in v1 and not bound; v2 keeps them recorded — bind them (a crown
   minimum as an `Offset` row) or leave diagnostic?
