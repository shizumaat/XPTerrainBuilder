# Beta 2 — OTHH-2 / OTHH-4 / OTHH-6 diagnosis (artefact-only, no builds)

Lane: DIAGNOSE-ONLY, 2026-09-18. No code edits, no builds, no git ops.
Evidence: existing OTHH/HECA/LEMD patch files, recorded phase times, code reading.

Status: IN PROGRESS (appended as discovered).

## Artefacts used

- `/Users/noah/XPTerrainBuilder/Ortho4XP/Patches/+20+050/+25+051/OTHH_auto.patch.osm`
  (5,715,311 B, mtime 2026-08-14 15:11 — the newest OTHH patch on disk; it is
  NOT a build-350 emission, so counts are indicative, not build-350 exact).
- HECA `Patches/+30+030/+30+031/HECA_auto.patch.osm` (2026-09-09),
  LEMD `Patches/+40-010/+40-004/LEMD_auto.patch.osm` (2026-09-15),
  CYXY `Patches/+60-140/+60-136/CYXY_auto.patch.osm` (2026-09-15).
- `~/.ortho4xp/tile_build_times/+25+051.json` (OTHH tile) and `+30+031.json` (HECA tile).
- `~/.ortho4xp/auto_patch_build_times/OTHH.json`.

## OTHH-2 — where the line is printed and what runs next

The console line is printed at
`/Users/noah/XPTerrainBuilder/Ortho4XP/src/auto_patch/engine_v2.py:693-697`:

    UI.vprint(1, f"  [v2 placement] {plan_.icao}: design surface "
                 f"{len(pads)} object pad(s), {len(rims)} structure "
                 f"rim(s), {len(_surface.roles.faces)} graded face(s) "
                 f"for the §17 motion rule")

It sits inside the v2 OBJECT PLACEMENT stage, immediately after the graded
surface doc is parsed (`pads_rims_from_graded_doc` / `decks_from_graded_doc`,
`engine_v2.py:678-681`) and immediately BEFORE the big call
`_pw.build_plan(...)` (`engine_v2.py:704-750`). So the line is the last thing
printed before object placement's own solve, and after that auto_patch is done
and the TILE build continues into the mesh step (Triangle4XP), which is what
the UI shows as "triangulating".

### Recorded timings (no build run; ledger only)

`~/.ortho4xp/tile_build_times/+25+051.json` — the owner's OTHH tile, last two
runs are **2026-09-18 11:43** and **2026-09-18 12:11** (build 350 day):

| step | OTHH +25+051 | HECA +30+031 (2026-09-17) |
|---|---|---|
| mesh (Triangle4XP) | **448.61 s** (11:43) and **272.08 s** (12:11) | 76.69 s and 110.31 s |
| vector (incl. auto_patch) | 62.15 s, `airports: 0`, `autopatch_seconds: 0.0` | 486.37 s / 589.51 s, `airports: 2`, `autopatch_seconds: 469.4 / 554.0` |
| masks | 6.13 / 4.10 s | 1.45 / 1.84 s |

So the mesh step at OTHH is **2.5x–5.8x HECA's**, and it is the dominant
recorded step of that tile. Note the 12:11 OTHH run recorded
`airports: 0, autopatch_seconds: 0.0` in its vector step — auto_patch did not
re-run in that pass; the mesh nevertheless consumed 272 s, because
`include_patches` reads the patch file already on disk. i.e. the cost is in
the PATCH GEOMETRY the mesher ingests, not in the time auto_patch spends.

`~/.ortho4xp/auto_patch_build_times/OTHH.json` last entry (2026-09-09 17:50)
also shows auto_patch itself is heavy at OTHH: total 1,575.33 s, of which
"Solving elevations (FAA grade compliance)" 821.82 s and "Assembling pavement
& runway shoulders" 536.71 s (previous runs: 449–453 s total) — a 3.5x
regression in auto_patch between 2026-09-03 and 2026-09-09 that is a separate
finding worth its own row.

### Patch size comparison (exact counts, `<node id='…'` / `<way ` / `<nd `)

| airport | nodes | ways | nd-refs | file bytes |
|---|---|---|---|---|
| **OTHH** | **33,109** | **2,535** | **56,439** | 5,715,311 |
| HECA | 23,336 | 1,191 | 38,760 | 4,387,770 |
| LEMD | 21,154 | 1,088 | 38,417 | 4,069,783 |
| CYXY | 4,430 | 274 | 8,492 | 877,410 |

OTHH is 1.42x HECA in nodes but **2.13x in ways** — the way count, not the
node count, is the outlier. Triangulation cost is driven by CONSTRAINED
SEGMENTS (each `<nd>` pair is a constraint edge) and by the number of
near-degenerate constraints, not by node count alone.

### Constraint DENSITY, not node count, is the OTHH outlier

Segment = every consecutive `<nd>` pair in a way, i.e. one constrained edge
handed to Triangle4XP.

| airport | constrained segments | min len | median len | segments < 0.5 m | near-duplicate nodes (<0.5 m apart) |
|---|---|---|---|---|---|
| **OTHH** | **53,904** | 0.500 m | **5.35 m** | 0 | 42 (42 pairs, max cluster 2) |
| HECA | 37,569 | 0.500 m | 11.73 m | 570 (1.5%) | 0 |
| LEMD | 37,329 | 0.499 m | 13.53 m | 5 | 0 |

There are **no zero-length segments and no sub-0.1 m duplicates** anywhere —
the 0.5 m floor is being honoured. So OTHH's triangulation cost is **not**
degenerate geometry; it is that OTHH hands the mesher **1.43x the constrained
edges of HECA at 2.2x the linear density** (median edge 5.35 m vs 11.73 m).
At a fixed `min_angle=10` quality constraint (below) the Steiner-point count
Triangle grows roughly with the square of constraint density in the
constrained region.

### The role census — the outlier is JUNCTION MESHES

Ways by `o4_role` (exact counts):

| role | OTHH ways | OTHH nd-refs | HECA ways | HECA nd-refs |
|---|---|---|---|---|
| **service_junction** | **854** | **9,625** | 1 | 29 |
| **junction** | **667** | **19,725** | 69 | 2,828 |
| graded_strip | 193 | 6,778 | 297 | 12,155 |
| gap_drainage_spine | 191 | 2,060 | 0 | 0 |
| object_pad | 139 | 1,075 | 0 | 0 |
| gap_interior_ring | 97 | 6,385 | 41 | 1,326 |
| groundside_pavement | 85 | 2,424 | 14 | 663 |
| tunnel_trench | 76 | 2,225 | 0 | 0 |
| building | 67 | 934 | 413 | 7,138 |
| apron | 64 | 3,008 | 32 | 2,156 |
| tunnel_ramp | 23 | 121 | 0 | 0 |
| runway | 2 | 451 | 6 | 2,934 |

`junction` + `service_junction` = **1,521 of OTHH's 2,535 ways (60%)** and
**29,350 of its 56,439 nd-refs (52%)**. At HECA the same two roles are
**70 ways (5.9%)** and 2,857 nd-refs (7.4%). This is THE structural
difference between the two patches.

`Ortho4XP/scratch/build_OTHH.log:224-225` (a 2026-09-07 OTHH run) independently
prices the stage: `junction_mesh 11800 14.797 s`, `junction_mesh.box_pairs 2588`
— 11,800 junction-mesh items built.

### The mesh command and the retry ladder (the "insanely slow" amplifier)

`Ortho4XP/src/O4_Mesh_Utils.py:2833-2836`:

    Tri_option = ("-pq" + "{:.9g}".format(tile.min_angle) + do_refine +
                  regional_areas + "uYB" + tri_verbosity + output_poly + limit_tris)

`Ortho4XP/src/O4_Mesh_Utils.py:2891-2917`: if Triangle4XP returns non-zero
(quality unachievable), the WHOLE triangulation is re-run at
`min_angles = [8, 6, 4, 2, 0]` — up to **five additional full triangulations
of the same tile**, in sequence, with no intermediate progress output
(`O4_Mesh_Utils.py:2633` notes "Triangle4XP goes quiet for minutes between
phase lines"). That is the mechanism by which "triangulating" can run many
times the 272–449 s the ledger recorded for a SUCCESSFUL first pass; a build
that trips the ladder pays 2x–6x.

OTHH's tile config (`Ortho4XP/Tiles/zOrtho4XP_+25+051/Ortho4XP_+25+051.cfg`)
is at the defaults for all of these: `min_angle=10.0`, `mesh_zl=19`,
`curvature_tol=2.0`, `apt_curv_tol=0.5`, `limit_tris=3.0`. `apt_curv_tol=0.5`
(vs `curvature_tol=2.0`) means the airport footprint is meshed at **4x the
curvature resolution** of the rest of the tile
(`O4_Mesh_Utils.py:463-491`, `build_curv_tol_weight_map`), so the dense
junction-mesh constraint field lands exactly where the posting is finest.
OTHH is also coastal (`elevation_level=coastline`,
`bathymetry_band_km=5.0`, `coast_curv_tol=1.0`), adding a second refined
region; HECA's tile cfg carries only `default_website` / `default_zl`.

**OTHH-2 conclusion (mechanism, not yet interventionally proved):** the
triangulation is slow because the airport hands Triangle4XP ~30k constrained
nd-refs of `junction` / `service_junction` polygons — 52% of the patch —
packed at a 5.35 m median edge inside the `apt_curv_tol=0.5` refined region,
and any quality failure re-runs the whole triangulation up to five more
times. The stated fix direction is to reduce junction-mesh emission at OTHH
(see OTHH-6), not to loosen `min_angle`.

## OTHH-4 — the "clouds of detached nodes"

### What is NOT the cause (measured, all four patches)

- **No detached nodes in the patch.** Every one of OTHH's 33,109 nodes is
  referenced by at least one way (FREE = 0). LEMD has 52 free nodes (0.2%),
  CYXY 28 (0.6%), HECA 0. The owner's "detached" is a SIM appearance, not a
  free-floating OSM node.
- **No degenerate geometry.** Zero zero-length segments, zero sub-0.1 m
  near-duplicates; only 42 node pairs anywhere in OTHH sit within 0.5 m.

### At the owner's coordinate 25.2546269, 51.6204583

Exactly **one** patch way contains the point: way `-10196`,
`aeroway=apron role=apron shapeID=195`, 14 nodes, node elevations
`alt_abs` 3.98 → 4.15 m.

Within a 120 m radius there are **50 patch nodes**, elevations 3.70 → 4.22 m
(a 0.52 m spread), belonging to ways of roles: `junction` (23 node-slots),
`building` (22), `graded_strip` (16), `apron` (14), `service_junction` (5),
`object_pad` (3). Closest samples:

    12.1m id=-791   25.2545337,51.6205210  alt_abs 3.98
    13.9m id=-2876  25.2547208,51.6203672  alt_abs 3.99
    17.4m id=-2881  25.2545222,51.6203300  alt_abs 4.11
    23.9m id=-27799 25.2545313,51.6206709  alt_abs 3.70
    34.6m id=-2927  25.2544234,51.6207180  alt_abs 4.22

So: many small adjacent shapes, each pinned at its own slightly different
height — 0.5 m of spread within 120 m on an airport the owner calls truly
flat.

### THE FINDING: half of OTHH's patch nodes carry NO elevation at all

`alt_abs` tag census (a node without `alt_abs` is NOT pinned — the mesh
takes the raw DEM there):

| airport (patch mtime) | nodes | pinned (`alt_abs`) | **UNPINNED** |
|---|---|---|---|
| **OTHH (2026-08-14)** | 33,109 | 17,334 (52.4%) | **15,775 (47.6%)** |
| HECA (2026-09-09) | 23,336 | 23,336 (100.0%) | 0 |
| LEMD (2026-09-15) | 21,154 | 21,154 (100.0%) | 0 |
| KCLT (2026-08-12) | 29,700 | 29,039 (97.8%) | 661 (2.2%) |
| OTBD (2026-08-14) | 9,468 | 9,062 (95.7%) | 406 (4.3%) |
| OTBH (2026-08-14) | 3,131 | 2,877 (91.9%) | 254 (8.1%) |
| ZGSZ (2026-08-12) | 19,701 | 8,644 (43.9%) | 11,057 (56.1%) |

The same-vintage controls (KCLT/OTBD/OTBH, all 92–98% pinned) rule out patch
AGE as the explanation. The two outliers, OTHH (47.6% unpinned) and ZGSZ
(56.1% unpinned), are the two large custom packs — and at OTHH the unpinned
nodes belong overwhelmingly to exactly the two roles that blow up the way
count:

    OTHH UNPINNED node-slots by owning role:
      junction 13,040 | service_junction 7,777 | graded_strip 4,377
      apron 2,266 | groundside_pavement 1,737 | building 653
      object_pad 394 | service_road 270 | runway 131
    OTHH PINNED node-slots by owning role:
      (no role tag) 9,227 | junction 6,018 | graded_strip 2,207
      tunnel_trench 2,149 | service_junction 991 | apron 678

`junction` nodes are 13,040 unpinned vs 6,018 pinned; `service_junction`
7,777 unpinned vs 991 pinned (≈89% unpinned). **The junction / service
junction meshes that dominate OTHH's patch are emitted as rings whose
vertices largely carry no elevation.** In the mesh each such vertex takes
the DEM/inset height while its pinned neighbours in the same or adjacent
ring take the solved height — which is exactly "nodes at slightly different
elevations from their surroundings", in clouds, wherever a junction mesh
sits.

### Does OTHH-4 feed OTHH-2?

**Partly — same root, different symptom.** The unpinned-ness itself costs
Triangle4XP nothing: the constrained EDGES are handed over either way, so
the triangulation cost comes from the 29,350 junction/service-junction
nd-refs (OTHH-2), not from whether those nodes carry `alt_abs`. But BOTH
symptoms are produced by the same upstream fact: OTHH's partition emits
**1,521 junction / service_junction faces (60% of all ways)** against HECA's
70. Cut that population and OTHH-2 and OTHH-4 both shrink. Treat them as one
mechanism with two readings, and attribute the junction-face explosion (why
854 `service_junction` faces at OTHH — `src/auto_patch_v2/classify/roles.py:434-437`
assigns `service_junction` where a face is apron-kind with TRUCK routes and
no taxi route) before proposing a fix. The 2026-09-07 log line
`junction_mesh 11800 14.797 s` / `junction_mesh.box_pairs 2588`
(`Ortho4XP/scratch/build_OTHH.log:224-225`) is the stage to instrument.

**Caveat, stated plainly:** the OTHH patch read here is 2026-08-14, five
weeks before build 350. Everything above should be re-read on a build-350
OTHH patch before any fix is designed. No build was run in this lane.

## OTHH-6 — "on a truly flat airport the inset pre-flattens everything, can the patch be skipped?"

### First: the premise needs correcting (two citations)

1. **The elevation inset is not a flattener — it is a SHARPENER.**
   `Ortho4XP/src/O4_Cfg_Vars.py:310-313` (`airport_elevation_insets`):
   meter-class elevation is *"fetched for the neighbourhood of every airport
   on the tile and overlaid on the base elevation raster before the mesh is
   built"*. `airport_elevation_level` (`O4_Cfg_Vars.py:325-337`) is a ground
   RESOLUTION (0.5–30 m), not a level surface. The inset replaces a coarse
   DEM with a fine one; it imposes no plane.
2. **What blurs an airport is `apt_smoothing_pix`, and the inset REDUCES
   it.** `O4_Cfg_Vars.py:300-303`: `apt_smoothing_pix=8` is *"gaussian blur
   … applied to the elevation raster"*. `O4_Cfg_Vars.py:305-308`
   (`apt_smoothing_auto`, default True, set in OTHH's tile cfg): airports
   *"covered by high resolution elevation insets are blurred less or not at
   all."* So at OTHH — insets on, `apt_smoothing_auto=True` — the airport is
   deliberately blurred LESS than a no-inset airport, not flattened.

OTHH *looks* flat because Doha's ground there genuinely is: every patch node
within 120 m of the owner's OTHH-4 coordinate sits between 3.70 m and 4.22 m.
Flatness is the TERRAIN's, not the inset's.

That matters for the plan: "skip the patch because the inset already
flattened it" would be skipping the patch in favour of an UNFLATTENED,
now-high-resolution DEM — the opposite of the intent.

### What the patch supplies that no flat (or sharp) DEM can

Counted in OTHH's own patch, with the code that consumes each:

1. **Constrained mesh edges along every pavement boundary.** Every patch way
   becomes a segment in the `.poly` that Triangle4XP is forbidden to cross
   (`O4_Mesh_Utils.py:2849-2871`, `poly_file` is the last mesh argument;
   the `-p` flag is PSLG mode). This is what makes a triangle edge lie ON the
   runway edge instead of cutting diagonally across it. OTHH's patch carries
   **53,904 such segments**. A flat DEM supplies zero. Without them the mesh
   posting (`mesh_zl=19`) decides where pavement ends, and the ortho texture
   tears at the boundary — which is exactly the shape of blocker NLWF-2
   ("texture tearing at one runway end").
2. **Object seating — pads, rims and decks.** `engine_v2.py:672-697` reads
   the graded-surface doc the patch emits and derives
   `pads, rims = placement_plan.pads_rims_from_graded_doc(_gd)` and
   `decks_from_graded_doc(_gd)`. The comment there is explicit
   (`engine_v2.py:661-667`): *"without the pads and rims `classify_body` can
   never answer `building` or `basin` … every shipped body fell through to
   `other`"*. OTHH's patch carries **139 `object_pad` ways** and
   **84 structure rims** (the owner's own console line). Skip the patch and
   every building, jetway and hangar at OTHH loses its datum and floats or
   sinks — the SPJC-1/SPJC-2/HECA-4 failure mode.
3. **The §17 motion rule's face roles.** `engine_v2.py:680-692` builds
   `_surface.roles` from the same doc so a body standing on rolled-on
   pavement takes the MEDIAN of its feet instead of its low side. The owner's
   console line reports **866 graded faces** feeding exactly this. No DEM
   carries a role.
4. **Runway crown.** OTHH's patch has **2 `crown_spine` ways / 864 nd-refs**.
   A runway is not flat across its width; a flat inset makes it flat, and the
   crown is a drainage-law requirement, not an aesthetic.
5. **Retaining walls and wall/road level separation.** **16 `retaining_wall`
   ways**. HECA-3 in this same blocker list is precisely the owner asking for
   a retaining wall's two-level behaviour — road level at the wall top,
   ground beyond at the bottom. That is a patch product.
6. **Graded strips and the airside/groundside terrace boundary.**
   **193 `graded_strip` ways / 6,778 nd-refs** and **85
   `groundside_pavement` ways**. Under the adjacent-ground zone law the step
   from graded pavement to raw DEM is a LAWFUL terrace that must be built,
   not left to a blur.
7. **The classes the owner already proposes keeping**: `tunnel_trench` 76,
   `tunnel_ramp` 23, `bridge_trench` 1, `bridge_causeway` 2,
   `gap_drainage_spine` 191, `gap_interior_ring` 97.

### Honest answer: **PARTLY — and the part that can go is the part causing OTHH-2 and OTHH-4.**

- **No**, the patch cannot be reduced to "below-grade + drainage". Items 1–5
  above (constrained edges, pads/rims, face roles, crown, walls) have no DEM
  substitute at any resolution, and dropping them reproduces four other rows
  already on this beta-2 list (SPJC-1, SPJC-2, HECA-3, NLWF-2).
- **Yes**, there is a large, identifiable skippable population, and it is the
  one the owner's other two OTHH rows are complaining about: the **1,521
  `junction` / `service_junction` faces (60% of OTHH's ways, 52% of its
  nd-refs, 29,350 nd-refs)**, of which ~89% of `service_junction` vertices
  carry NO elevation at all. These faces are re-stating, at a 5.35 m median
  edge, ground that the high-resolution inset already describes at 0.5–1 m
  posting. On a flat airport a junction mesh whose vertices are unpinned
  contributes a constrained edge and a DEM lookup — i.e. cost without a
  datum.
- The right shape of a plan is therefore **not** "skip the patch on flat
  airports" but **"do not emit a graded face where the face is already at
  the inset's own height, and never emit an UNPINNED constrained ring"** —
  one rule, at the single emission site, which is the consumer-census
  discipline this repo requires (CLAUDE.md, RULINGS 2026-08-30l).
- The premise correction above (inset ≠ flattener) should go to the owner
  with this, because his proposed plan is built on it.

**Owner question this raises (intent, not mechanism):** should a graded face
whose solved height equals the inset height everywhere within tolerance be
emitted at all? That is a design ruling, not something a measurement settles.

## What this lane did NOT do

- No build, no replay capture, no `check_grade`, no census — no budget.
- Did not read a build-350 OTHH patch: none exists on disk. Every OTHH number
  here is from the **2026-08-14** patch and must be re-measured before a fix.
- Did not attribute WHY the partition produces 854 `service_junction` faces
  at OTHH (`src/auto_patch_v2/classify/roles.py:434-437` is the assignment
  site; the truck-route input is unexamined).
- Did not attribute the auto_patch regression visible in
  `~/.ortho4xp/auto_patch_build_times/OTHH.json`: total 449.8 s (2026-09-03)
  → 1,575.3 s (2026-09-09), driven by "Assembling pavement & runway
  shoulders" 1.5 s → 536.7 s and "Solving elevations" 265 s → 822 s. This
  looks like a separate beta-2 blocker row and is NOT explained by anything
  above.
- Did not edit code, did not touch `docs/BETA2-BLOCKERS.md`, ran no git
  operation.
