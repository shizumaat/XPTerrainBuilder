# Brief pack — lane `shorewater`

Base: main `840d65da` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

OTHH: water climbs the vertical faces of the land (default_xplane tile +25+051)

## The brief

## Lane shorewater — OTHH: WATER CLIMBS THE VERTICAL FACES OF THE LAND (owner sim read, 2026-09-17)

OWNER, with a screenshot from the sim at OTHH (tile +25+051): "When building a tile with
X-Plane default textures and no orthos (and maybe then too), our coastline data has a
problem that is allowing water to go up on to vertical parts of the land. We either need
to ensure the water follows the terrain edge, or ensure we don't assign non-zero
elevations to ocean coastline areas." Open a lane to ROOT CAUSE and ADDRESS it.

THE SCREENSHOT: a road bridge on piers over a sea channel, palms, light poles, a sandy
island bank at lower left. The WATER SHADER is drawn on sloping, faceted triangles that
climb the bank: up the embankment under both bridge abutments, up the island's edge at
lower left, and along the far shore — several metres of "water" standing on near-vertical
faces, then sand above it. The open water itself is flat and correct. So water-rendered
triangles have at least one vertex well above the water level.

BUILD IDENTITY (measured): the tile in the sim is
`/Users/noah/X-Plane 12/Custom Scenery/zOrtho4XP_+25+051/` built 2026-09-16 16:52–16:57
by app 1.0.344 (engine 1.50.1791), `texture_mode=default_xplane` (its
`Ortho4XP_+25+051.cfg:52` and `Ortho4XP_+25+051_imagery.json`), provider Arc ZL16,
`textures_total: 0`. On disk, READ-ONLY for you: `Data+25+051.mesh` (44.6 MB), `.node`,
`.poly`, `.alt`, `.apt`, and the DSF under `Earth nav data/+20+050/`. Recorded step times
for this tile: vector 63 s, mesh 213 s, masks 9 s, imagery+DSF 14 s — a whole rebuild is
about FIVE MINUTES, so a real closing build is affordable. OTHH is a flat-site airport
(engine log: "SYNTHETIC CONSTANT INSET at Z0 3.96 m … 34.6 % of the synthetic extent is
WATER and is CUT OUT of the Z0 raster (the base DEM stands there; the mask edge is the sea
wall)"; "Water is a datum: 186 shore vertex(es) shared with a patch/road INTERP_ALT
triangle kept their levelled water altitude").

THE LAW THAT ALREADY EXISTS (read these, do not re-derive — and note the defect means
something ESCAPES them or sits DOWNSTREAM of them):
- RULINGS 2026-09-09m / 09o (3): WATER IS A DATUM per TRIANGLE — a triangle carrying ANY
  water bit takes sea/water levelling regardless of an INTERP_ALT seed (measured then: 2,180
  SEA|INTERP_ALT triangles over 13.7 km2 at OTHH, 1,692 carrying a 3.962 m step).
  Code: `Ortho4XP/src/O4_Mesh_Utils.py` ~:2195-2215.
- RULINGS 2026-09-09z (3): the same law per VERTEX — `water_valued` = every corner of a
  water or sea triangle (~:2236-2246); the INTERP_ALT column-5 copy skips them (~:2450-2475).
- RULINGS 2026-09-09aj (v2shore, 0bcd37f2): "the shore has no bank; OTHH water sits at
  0.000 everywhere". Spec §39 (the hairline law) and `emit/osm_adapter.weld_to_shore`:
  patch vertices are welded EXACTLY onto foreign water vertices.
- "Smoothing inland water" / "Smoothing of sea water" (`O4_Mesh_Utils.py` ~:2276): INLAND
  water bodies keep their OWN level — a fix must NEVER zero a lake or a river at altitude;
  the datum is each water body's level, the sea's is 0.
Use `Ortho4XP/venv/bin/python tools/docq.py ruling 2026-09-09z` etc.; if docq returns
empty (it did for a 17a key today) read `Ortho4XP/docs/RULINGS.md` by grep for the heading.

HYPOTHESES — each is a GUESS until measured; REFUTED ones are deleted from your report's
conclusions, per the project's attribution-before-fix law (memory `mechanism-before-fix`:
an attribution read is not causal; require an INTERVENTION):
 H1 THE PAINT, NOT THE MESH: in `default_xplane` mode the terrain type of each triangle
    comes from `src/O4_Default_Terrain_Map.py` (X-Plane default terrains baked from a
    landclass source; its header says "Water terrains are kept like any other terrain
    (callers filter if needed)"). If a LAND triangle on the bank is assigned a WATER
    terrain because the landclass source is coarser than the mesh coastline, the mesh
    law above is satisfied (no water-BIT triangle is raised) and the sim still draws water
    up the bank. This would also explain why it shows in default-textures mode. With
    orthos the equivalent is the water MASK draped over a sloping land triangle ("and
    maybe then too").
 H2 A LATER PASS RAISES A WATER VERTEX after the levelling: road ribbons ("Road ribbons:
    N bare-INTERP_ALT input node(s) keep their authored altitude and join the Dirichlet
    set", RULINGS 13cp), patch rings ("mesher-inserted vertex(es) lie on a patch ring
    segment and take the ring's value", R18-1b), bridge decks/abutments, the sea wall,
    `bank_foot` chains, or the post-mesh object stage.
 H3 THE FLAT-SITE RASTER'S WATER CUT-OUT AND THE VECTOR COASTLINE DISAGREE: the Z0 3.96 m
    synthetic inset is cut by a raster water mask; shore vertices from the OSM coastline
    that fall on the raised side sample 3.96 m. (Under the per-vertex datum law they should
    still be levelled if they are corners of a water triangle — so H3 alone cannot do it;
    it matters combined with H1.)
 H4 TWO WATER SOURCES: OSM `coastline` vs `water` layers (both cached for this tile) overlap
    or gap at the channel, leaving slivers classed one way in the mesh and the other in
    the DSF.

MEASURE FIRST, READ-ONLY, ON THE BUILT TILE (no build yet):
 1. A WATER-DATUM AUDIT of the shipped tile. CONSULT `tools/INDEX.md` FIRST — near-fits
    exist: `tools/mesh_region_tris.py` (built-mesh triangles in a bbox), `tools/seawall_admission.py`
    (where a sea wall is admitted), `tools/patch_seed_seal.py`, and the DSFTool text dump
    (`auto_patch/dsf_reader.ensure_dsf_text_path`, lane-local cache via `O4_DSF_CACHE_DIR`).
    EXTEND a near-fit (a subcommand/flag) rather than forking; only if none fits, add
    `tools/water_datum_audit.py` with its INDEX row and a twin in the same commit. It reports,
    for a tile: (a) MESH SIDE — triangles whose attribute carries a water/sea bit with any
    vertex above that water body's level by > 0.05 m: count, area, max height, top sites
    (lat/lon); (b) DSF SIDE — triangles whose TERRAIN TYPE is a water terrain (`terrain_Water`
    and whichever default-terrain water names the map uses) with any vertex above 0.05 m (sea)
    — count, area, max height, top sites; (c) the JOIN: DSF-water triangles that are NOT
    water-bit triangles in the mesh (that population IS H1), and the reverse.
 2. LOCATE the owner's site from the audit: the largest raised-water cluster near a road
    bridge over a channel at OTHH (the airport reference is ~25.273 N, 51.608 E). Give
    lat/lon for the bridge abutments and the lower-left island bank; say which population
    each raised triangle belongs to.
 3. Name the hypothesis the numbers support, then INTERVENE on a synthetic fixture before
    touching production code paths blindly: a small synthetic tile world (sea + a raised
    bank + a bridge/road crossing, flat-site-style raised raster) driven through the SAME
    functions (the altitude post-processing in `O4_Mesh_Utils`, the default-terrain
    assignment, the DSF terrain-type writer). Tests build their own tmp corpus; the conftest
    write guard fails any test that writes the shared repo.

THE FIX — the owner named two acceptable outcomes and the existing law already chooses
between them: WATER IS A DATUM and THE SHORE HAS NO BANK ⇒ every water-RENDERED triangle
lies flat at its water body's level, and the rise from the waterline to the land happens
on LAND-rendered triangles. So: (i) if H1, a triangle is drawn as water IFF the mesh says
it is water (the terrain/mask assignment follows the mesh's water bits, never a coarser
raster), and it must hold in BOTH texture modes — check the ortho/mask path for the same
class and report what you find even if you only fix default_xplane first; (ii) if H2/H4,
fix the pass that raises the vertex at its ONE derivation site (no per-consumer veto;
consumer census first if the change touches a shared region — CLAUDE.md RULINGS
2026-08-30l). Do not flatten the LAND (that is the other remedy and the law did not pick
it), never zero inland water, and do not move the waterline.

CLOSING TEST (one tile, ~5 min): rebuild +25+051 in `default_xplane` mode through the
harness (`tools/harness/build_airport.py OTHH --tile 25 51 …` — read its help for the tile
and texture-mode options; it refuses an empty cifp, a cold DEM frame or a private corpus,
and an implicit download is a refusal, not yours to override; if it refuses, report the
named scope instead of working around it). Lane products stay lane-local. Run your audit
on the result: DSF-side and mesh-side raised-water counts BEFORE (the shipped tile) vs
AFTER, tile-wide, expected → 0 for the sea; plus `mesh_region_tris` for OTHH unchanged
within noise, and the engine's own "Water is a datum" / "shore" log lines quoted. Quote
`[harness] shared repo UNCHANGED`. Then `tools/blast.py` for each edited src file and what
it names, tests/test_post_mesh.py, the mesh/DSF/default-terrain tests, the standing suite
once with FAILED lines verbatim.

FILES: yours — `src/O4_Mesh_Utils.py`, `src/O4_Default_Terrain_Map.py`, the DSF terrain
writer (`src/O4_DSF_Utils.py` or wherever terrain types are chosen), the masks step if the
ortho path needs it, your tool + tests. NOT yours this round (other lanes are in them):
`src/O4_Airport_Elevation_Insets.py`, `src/auto_patch_v2/airport/dem_production.py`,
`tools/harness/build_airport.py` (lane insetbounds); `scripts/check_frozen_tile.*`,
`src/auto_patch_v2/pipeline/xplat.py` (lane xplatspread). If you need a harness option that
does not exist, STOP and report rather than editing build_airport.py.

Rules: worktree from Ortho4XP/ `tools/harness/lane_worktree.sh up shorewater`; merge main
first. The bash guard refuses engine build/test commands whose effective cwd is not an
Ortho4XP/ with venv and OSM_data (run them from your worktree's Ortho4XP/ in their own call,
never ending a compound command with a `cd` elsewhere), pattern-matches test-runner words
inside heredocs (write files with the Write tool) and refuses `git stash`. The X-Plane
install and the shipped tile are READ-ONLY. Release Xcode only; never quit the owner's app;
never run make_app/make_engine; no push; commit early; do not merge; no RULINGS entry.
Report: the audit numbers before/after, the site coordinates, which hypothesis the
measurement supported and which it REFUTED, the interventional proof, the fix and its one
site, whether ortho mode has the same class, branch + sha, and everything not done.

## RULINGS

## 2026-09-09z — OWNER INTERVIEW (four rulings): crossing runways grade to the NEAREST-THRESHOLD runway's crossing node (v1's logic); library objects are left to X-Plane's draping; the shore has NO bank — pavement nodes only, the DEM/bathymetry grades into the water; planes always follow their walls, held or not

* (1) RUNWAY × RUNWAY CROSSINGS (supersedes 09r (2)'s "primary governs"): "All crossing runways must stay within the runway grade laws. V1 takes the closest threshold to the crossing, solves that runway, then sets the crossing node as an anchor for the other runway(s) to grade to, same logic as a tile seam boundary or the CIFP threshold." RULED: the runway whose THRESHOLD is nearest the crossing solves the crossing node under its own laws; that node's z becomes a PIN for every other runway through the crossing (as a seam/threshold pin), and every runway stays inside its grade and curvature laws. At CYXY 02/20's thresholds are nearest both crossings (15 m and 166 m) → 02/20 governs both nodes; 14R/32L and 14L/32R grade to them (the 1.07 m "dip" is then the law, spread as a vertical curve by the exact projection). `crossing_primary` / `runway_crossing_release` are replaced by the nearest-threshold pin. Lane `v2crossing` after `v2settle` (same files).
* (2) LIBRARY OBJECTS: no DSF placement rewrite — X-Plane drapes them at their anchor; 09q's owed (2) for library stock is CLOSED as "not wanted"; multi-anchor per-placement copies stay owed (low priority).
* (3) THE SHORE: "Only set pavement node elevations, then the DEM should automatically grade into the water and blend with bathymetry data" — RULED: NO bank at water — where the daylight walk meets water within `bank_min_width_m`, no foot is emitted at all (the ring's outer edge is the patch boundary); the mesh drapes the DEM (with the bathymetry band) and levels the water (09u), so a quay at OTHH is the DEM's own step and a beach is the bathymetry's slope. 09m (2)/09o (4)'s shore bank is WITHDRAWN. Lane `v2shore` after `v2bankblend` round 2 (same `emit/bank.py`).
* (4) PLANES FOLLOW THEIR WALLS, HELD OR NOT: a plane's carrier is the component its geometry TOUCHES (shared vertices / footprint contact within the identity spacing), nearest-distance only as the fallback; if the carrier is held the plane is held with it, if the carrier moves the plane moves — never a panel at a different height from the walls that carry it (HECA's Private Hall block, 143 after 09x). Lane `v2planes` after `v2lemdseats` round 3 (same `airport/rigid.py`).

## 2026-09-09aj — v2shore MERGED (0bcd37f2): the shore has no bank; OTHH water sits at 0.000 everywhere

* `emit/bank.py`: the annulus region is CUT by the tile's water multipolygon (17 of OTHH's 44 rings are water-cut holes; banked region 11.43 km², over water 0.0 m²); the daylight walk stops at the water line; foot nodes on the water line carry 0.000. `O4_Mesh_Utils`: a vertex carrying the water bit keeps its levelled water altitude over any patch value (186 shore vertices at OTHH). Spec §18; `tools/patch_water_audit.py` new, `mesh_region_tris.py --water-audit` extended; 4 twin files, 344 with the harness.
* OTHH SITE-FIRST (matched step-2 replay, only `O4_Mesh_Utils` differing): SEA vertices off 0.000 28 → **0**; SEA triangles with a step > 1 m 21 → **0** (max step 2.712 → 0.000 m); within 2 km of 25.2558, 51.6079: 3 → 0. The owner's "sharp cliff at the land/water border" was a 3.96 m plateau step INSIDE the water — the land-side shore transect was already a ramp (max grade 0.077, unchanged). Inland bodies (30,147 vertices) hold their own levels, lawful. Verify 16 rows, no DEFECT family, hard set settled. Shared repo unchanged.
* Deviation ACCEPTED (spawner): the foot ring stays CLOSED along the water line (shore vertices at the DEM's own value — a no-op in elevation, a fence in topology), because an open `bank_foot` way is a dummy in `include_patches` and the dry three-quarters of the annulus would lose its INTERP_ALT seed (§10.5's 306 % transect). Unexercised at OTHH: the walk's own water branch (the canal lies outside every daylight ray; the region cut did the work) — proven by twins only.

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; a file past 1,000 lines is a warning to reconsider its architecture (split by
  responsibility when it no longer fits; past 1,500 split before merging — owner 13bz).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py tests/test_auto_patch_freshness.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

