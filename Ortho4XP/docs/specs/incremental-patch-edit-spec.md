# Incremental patch edit: apply a small patch edit to a built mesh — spec (2026-10-26)

Status: PROPOSAL, spec only; no code changes. Issue #1323 (owner
2026-10-25: "if nothing else has changed, everything is cached, and the user
moves a few nodes in the patch, can we somehow just apply that tiny change
to the mesh very fast without having to rebuild the whole thing?"). Related:
#412 (airport patch build time), #615 / #836 / #837 / #838 (step reuse),
`patch-editor-20261015.md` (A3: an edit is not grade-checked; A7: object
re-seating stays off for an edited airport), `step-reuse-content-keys-spec.md`.
Law: RULINGS 2026-08-30l (consumer census, §6 below), 05e (no
airport-specific code: everything here is per tile, read from the tile's own
files). Read on main `c95b84f`; every `file:line` below is on that commit.

## 0. The answer in short

1. **Feasible, in two tiers.**
   - **Tier 1, height-only edit** (nodes keep their place, only `alt_abs`
     changes). Triangle4XP is skipped. The result can be **byte-identical**
     to a full rebuild, and the check for that is a fixture twin (§9 E2).
   - **Tier 2, geometric edit** (moved nodes, added or removed ways). Only a
     bounded cavity around the change is re-meshed. The result is
     **lawful but not identical** to a full rebuild: the triangles inside
     the cavity differ. Whether that is acceptable is owner question Q1.
2. **What the fast path saves:** the whole-tile Triangle4XP run (and its
   weight map) and, when no water triangle moved, the masks step.
3. **What it does not save:**
   - the vector step: it reruns, because it is the only complete authority
     on what a patch change does (§3, §6);
   - the altitude post-process;
   - the object stage;
   - the DSF encode.

   So its value is set by Triangle4XP's and the masks step's share of the
   rebuild. The repo holds no current per-step times for the owner's tile
   (+51-001, 21 min 25 s on 2026-10-24), so **Phase 0 is a measurement**
   (§10), and Tier 1 starts only if it shows a worthwhile saving.
4. **Cost:**
   - Tier 1 is one C change to Triangle4XP (record how each inserted vertex
     got its altitude, and replay that record), about 400 lines of Python,
     and four twins. About two lane rounds.
   - Tier 2 adds cavity extraction, a seam check, stitching and a
     lawfulness audit. About three to four rounds, architecture-class.

## 1. What happens today (verified)

1. The patch editor saves `<ICAO>_edited.patch.osm`, a manual patch that
   replaces the auto patch (patch-editor §1.2; `include_patches`,
   `src/O4_Vector_Map.py:3828`).
2. Patch files are **outputs** of the vector step in its reuse record
   (`_output_files`, `src/O4_Step_Reuse.py:290`, through `_patch_files`
   `:167`). An edited or new patch file makes the vector step stale ("its
   output files changed", `stale_reason` `:345`). The vector step reruns:
   - `include_airports` → `generate_auto_patches`, whose per-airport
     freshness gate reuses every other airport's patch;
   - `include_patches`, roads, sea, water, the ortho grid, the gluing edges,
     the noding, the weld and the seed audit;
   - it writes `.node`, `.poly`, `.alt` and `.apt`
     (`build_poly_file`, `src/O4_Vector_Map.py:1253`).
3. The mesh step's `previous` key changes, so the mesh step reruns
   (`build_mesh`, `src/O4_Mesh_Utils.py:2562`):
   - the weight map (`:2746`);
   - **Triangle4XP on the whole tile** (`:2773`, retries at a lower angle
     at `:2794`);
   - `post_process_nodes_altitudes` (`:2823`, body `:2035`);
   - `write_mesh_file` (`:2829`);
   - the object stage (`_auto_patch_post_mesh_rebake`, `:2858`).
4. The masks step's `previous` key changes, so the masks step reruns.
5. The DSF step is never reusable (`REUSABLE_STEPS`,
   `src/O4_Step_Reuse.py:97`); `build_dsf` (`src/O4_DSF_Utils.py:814`)
   re-encodes the whole tile.

## 2. Mechanism facts the design stands on

| # | Fact | Where |
|---|---|---|
| F1 | **Triangle4XP's refinement does not read node altitudes.** `testtriangle` decides from x, y, the triangle's region attribute (INTERP_ALT triangles are never refined), the area bound and the raster curvature. A node's z is a vertex ATTRIBUTE ("extra"), carried to output column 5. | `Utils/src/Triangle4XP.c:7221-7370` (`attribute >= 8` return at `:7279`), extras out at `:14995` |
| F2 | **An inserted (Steiner) vertex's attribute is a linear interpolation of the vertices it was inserted between, at insertion time.** There are five sites. | segment split `Triangle4XP.c:12343`, midpoint `:12533`, circumcentre `:14368`, others `:14182`, `:14623` |
| F3 | Output column 2 is the raster altitude at the vertex's (clamped) x, y. It is unchanged when the positions and the `.alt` are unchanged. | `Triangle4XP.c:14977-14994` |
| F4 | Every input vertex is written at its own index. The post-process maps `.poly` node ids to mesh vertices by that index. | `_input_order_check`, `src/O4_Mesh_Utils.py:946` |
| F5 | The post-process reads the Triangle output, the `.poly`, the patch `.osm` files and the levelled-roads sidecar, then **overwrites `.1.node` with its result** (`:2359-2368`). With `cleaning_level ≥ 1`, `.1.node`, `.1.ele` and the weight file are deleted (`:2831-2843`). So **the raw Triangle output does not survive a build today.** | `src/O4_Mesh_Utils.py` |
| F6 | **The masks step reads only the water-bit triangles (x, y, type)** of this tile's mesh and its eight neighbours' meshes. | `select_neighbor_meshes` `src/O4_Mask_Utils.py:516`; loop `:1154-1200` |
| F7 | **The DSF step reads the `.mesh`.** Its pools come from a quadtree on vertex positions, and each pool's altitude range is set by its vertices. | `src/O4_DSF_Utils.py:874`, pools `:909-980` |
| F8 | The object stage runs inside the mesh step. It is off for an airport whose patch is manual or edited. | `src/auto_patch/object_stage.py:865` → `selection.auto_patch_not_applied` `src/auto_patch/selection.py:386` |
| F9 | **The levelled-roads sidecar is outside the reuse record (a pre-existing gap).** The mesh step reads `o4_levelled_roads.json` (`src/O4_Mesh_Utils.py:1276`), which the vector step writes (`src/O4_Vector_Map.py:2312`), but the vector step's recorded outputs do not list it (`src/O4_Step_Reuse.py:290-296`). Today a changed sidecar under an unchanged `.node`/`.poly` would not stale the mesh step. Tier 1 adds it (§8). **For the master: this is a bug to file.** | as cited |

F1 to F3 together mean the following. If the rerun vector step writes the
same `.node` x, y values, the same `.poly` segments, holes and regions, the
same `.alt` and the same `.apt`, and only some node z values differ, then a
full Triangle4XP run would produce **the same triangles and the same vertex
positions**. Only column 5 would differ, and the raw column 5 of every
vertex can be recomputed exactly from the input z values and a record of
how each Steiner vertex was inserted.

## 3. The diff: what changed, and what it touches

**The authority is what Triangle4XP and the post-process read, not the
patch file.** The census (§6) finds about twenty passes in the vector step
that react to patch geometry:

- the apt.dat runway/apron encoding is skipped under a patch;
- roads graded within the patch band;
- sea seeds blocked by pavement;
- sea walls admitted along graded coverage;
- helipads, hangars, OBJ8 objects, bank-annulus regions and INTERP_ALT
  sub-cell seeds.

Re-implementing "which of those a moved node affects" would be a second
implementation of the vector step. Instead the fast path **reruns the
vector step unchanged** and diffs its products.

1. Before the vector step runs, the fast path moves the products the mesh
   was built from into `<build_dir>/fast_path/prev/`:
   - `.node`, `.poly`, `.alt`, `.apt` and the sidecar;
   - the patch files, kept to name the edit in the log.

   Their content digests must equal the vector record's `outputs` rows,
   which proves they are what the current mesh was built from (the mesh
   record's `previous` is the vector record's hand-on digest,
   `_handed_on` `src/O4_Step_Reuse.py:322`).
2. The vector step runs as today and records as today.
3. The products are compared in canonical form. The parse is shared with
   `hairline_findings`' `.poly` reader (`_hairline_read_poly`,
   `src/O4_Mesh_Utils.py:145`), never re-spelled.

| Class | Condition | Path |
|---|---|---|
| D0 | `.node`, `.poly`, `.alt`, `.apt` and sidecar byte-identical. Only patch `.osm` content changed, for example a tag the vector step ignores, which the post-process may still read through `bank_pavement_lines`. | Tier 1 with an empty z change |
| D1 | **Height-only.** Same node count; every node's x, y bytes equal at the same index; z differs for a set of nodes; `.poly` segments, markers, holes and region records (seed x, y, attribute, area) identical; `.alt` and `.apt` byte-identical. The sidecar may differ in levels only. | **Tier 1** |
| D2 | Anything else: a node added, removed or moved, a segment or marker changed, a seed moved. | **Tier 2** candidate (§5), else full |
| — | `.alt` or `.apt` differ | full mesh step (the DEM or the airport weight boxes moved) |

**What it touches.**

- **Tier 1:** the changed-z input vertices; their Steiner descendants
  (read from the provenance record, §4); the triangles incident to them;
  and, after the post-process, the set of vertices whose final z differs
  from the old `.mesh`. That set is measured, never assumed. The
  post-process includes graph-wide passes, so a z change can spread
  through a whole connected patch interior:
  - the free-interior Laplace solve (`interpolate_free_interior_altitudes`,
    `:711`);
  - the bank blend (`:1440`);
  - water smoothing (`:2132-2162`).
- **Tier 2:** the cavity (§5.1).

The patch-level diff (moved nodes, alt-only nodes, ways added or removed,
by node and way id between `prev/<patch>.osm` and the saved file) is for the
log line only ("3 nodes changed height, 1 way moved").

## 4. Tier 1: the height-only fast path

### 4.1 Steps (inside the mesh step, before `forget_from`)

1. **Admit.** `O4_Step_Reuse.stale_reason(tile, "mesh")` may differ from
   the recorded inputs ONLY in `previous`: same mesh settings, code digest,
   engine and auto-patch configuration. The kept raw artefacts (§8) are
   present and their digests equal the mesh record's rows. The Triangle4XP
   binary digest equals the one recorded with them. The diff class is D0
   or D1.
2. **Re-attribute.** Run Triangle4XP in its new RE-ATTRIBUTE mode with:
   - the kept raw `.1.node`;
   - the provenance record `.1.prov`;
   - the new `.node`.

   It writes a raw `.1.node` in which:
   - each input vertex's column 5 is the new z;
   - each Steiner vertex's column 5 is recomputed in insertion order by
     the same C expression that made it (F2);
   - columns 0 to 4 are byte-copied (F3).

   Doing the replay in the same binary keeps the floating-point contraction
   identical; a Python replay could differ in the last bit (#875: FMA
   contraction differs by platform compiler). The kept `.1.ele` is used as
   is.
3. **Post-process, unchanged.** Put the re-attributed raw `.1.node` and the
   kept `.1.ele` where `post_process_nodes_altitudes` reads them, then call
   it, `write_mesh_file` and `_auto_patch_post_mesh_rebake(tile)` exactly
   as `build_mesh` does (`:2823-2858`). There is no second post-process
   and no second object stage.
4. **Record the mesh** (`REUSE.record(tile, "mesh")`). Its outputs now
   include the new raw artefacts (§8).
5. **Masks witness.** If the water-triangle digest (§8) of the new `.mesh`
   equals the old one, the masks step's outputs are what a rerun would
   write (F6: the neighbours' meshes did not change, and the mask settings
   are in its record). The fast path re-records masks
   (`REUSE.record(tile, "masks")`) without running it: that re-keys
   `previous` to the new mesh and digests the unchanged mask files.
   Otherwise the masks step runs.
6. **DSF and activation** run as today.

### 4.2 Why it equals a full rebuild

- A full rebuild runs the same vector step (identical products, D1).
- Its Triangle4XP produces the same triangles and positions (F1, F3) and
  the same column 5 (F2; the replay is the same expression in the same
  binary).
- From there the two paths run the same post-process, `.mesh` writer,
  object stage, masks (or the witness that it would write the same files)
  and DSF encoder, on the same bytes.

The claim is proven on the fixture by E2 (§9), not argued.

### 4.3 Triangle4XP changes (C, `Ortho4XP/Utils/src/Triangle4XP.c`)

1. **A provenance switch**, proposed letter `K` (unused in the switch
   parser `:3140-3335`). For each Steiner vertex, in insertion order, it
   writes:
   - its output index;
   - the site kind (F2);
   - the output indices of its two or three parents;
   - the coefficients (`split`, or `xi`, `eta`).

   Two subtleties:
   - **A vertex freed before output** (a deleted Steiner, or a duplicate
     that `vertexdealloc` drops) is recorded as dead.
   - **Pool reuse:** the parents' output indices are known only at output
     time, because the vertex pool reuses freed slots. So the C keeps
     pointers and resolves them to output numbers in the write pass, where
     `setvertexmark(vertexloop, vertexnumber)` already numbers them
     (`:15004`).

   The record is binary, beside the `b` exchange files (mesh-io-spec §4).
2. **A RE-ATTRIBUTE mode** (the lane picks the switch and argument
   layout), as described in §4.1 step 2. It does no meshing.
3. **Feature-detected** like `TRI_BIN.use_binary_io`: a binary without the
   switch means no fast path, never a failure. The CI job that builds
   Triangle4XP from source (`.github/workflows/ci.yml:312-330`) gains the
   twins E1 and E2. `Utils/Triangle4XP-CHANGES.md` gets its entry.

Build-time impact on every build: the provenance write, about 30 bytes per
Steiner vertex. Keeping the raw `.1.node` and `.1.ele` replaces their
deletion with a rename. The lane measures both
(`tools/check_build_time.py --runs 3` on one tile); the law's 1 % of the
300 s tile budget is 3 s.

## 5. Tier 2: local re-mesh (only if owner Q1 is yes)

### 5.1 The cavity

1. Collect the D2 change set: the new and removed `.poly` segments and
   nodes, and the moved seeds.
2. Take the old triangles whose bounding box meets the change set's
   bounding box grown by a margin R. R is a parameter (proposal: three
   local mean triangle edges, at least 25 m). It is not tuned per site.
3. Close that set so that its boundary crosses no constrained segment's
   interior: a boundary may run along a segment, never cut through one.
4. The cavity boundary edges are old mesh edges, kept fixed.

### 5.2 The sub-run

1. Write a cavity `.poly` from three parts:
   - the boundary edges as boundary segments (`-Y`, already in
     `triangle_switches` `src/O4_Mesh_Utils.py:2507`, forbids Steiner
     points on them);
   - the new `.poly`'s segments inside the cavity;
   - the new seeds inside the cavity.
2. Boundary vertices keep their old raw column 5.
3. Run Triangle4XP with the build's own argument builder
   (`triangle4xp_command` `:2528`) on the same `.alt` and weight file.
   - Open question for the lane, to measure: the curvature map `hme` is
     computed over the whole raster (allocated at `Triangle4XP.c:17115`). A
     window option may be needed on densified tiles.

### 5.3 Region attributes: the seam check

Triangle4XP's region "plague" floods each seed's bits until a segment
carrying the same bit blocks it. A flood from a seed outside the cavity can
reach into it, and a change inside the cavity can open or close a path
**out of** it. So:

1. Cavity triangles take their bits from a flood seeded by the new seeds
   inside the cavity, plus, across each non-blocking boundary edge, the
   outside neighbour triangle's bits.
2. **The seam condition:** after the flood, for every boundary edge that a
   bit does not block, the inside and outside triangles carry the same
   value of that bit.
3. A mismatch means the change altered a region outside the cavity:
   **refuse, and run the full mesh step.**

### 5.4 Stitch, post-process, audit

1. **Stitch** the kept raw outside triangles with the sub-run's
   triangles. Renumber so that the NEW `.node`'s input vertices sit at
   their input index (F4), the outside Steiner vertices follow, and the
   cavity's Steiner vertices come last.
2. **Run the unchanged post-process, `.mesh` writer and object stage** on
   the stitched raw mesh, as in §4.1 step 3.
3. **Lawfulness audit**, which refuses (full mesh step) on any failure:
   - (a) a conforming seam: every boundary edge appears exactly once on
     each side, with no T-junction;
   - (b) every constrained segment of the new `.poly` is present as mesh
     edges;
   - (c) every patch-valued vertex carries its authored altitude
     (`patch_valued_vertex_indices` `:893`);
   - (d) the existing post-process audits pass unchanged
     (`audit_bank_annulus` `:1349`, `audit_interp_alt_extent` `:1988`);
   - (e) the minimum angle reached inside the cavity is at least the run's
     `min_angle`, or it is reported (`-Y` can block a split near the seam).
4. **Masks:** Tier 2 refuses a cavity that holds a water-bit triangle
   before or after the edit. Masks then stay reusable (F6), and a
   neighbour tile's masks never read a changed water triangle.

### 5.5 Why it is not identical to a full rebuild

A full rebuild refines the whole tile from scratch. Its Steiner points near
the change follow a different insertion history, and encroachment can
spread beyond any fixed cavity. Inside the cavity the triangles therefore
differ, while the constraints, the authored altitudes and the region
attributes are the same. The terrain between authored vertices differs
within Triangle4XP's own curvature criterion. That is the "prove itself
lawful" branch the issue names. It is the owner's choice (Q1), because it
gives up "same bytes as a full rebuild" for an edited tile.

## 6. Consumer census (RULINGS 2026-08-30l): every pass that reads patch geometry

"Fast path" says how each reader is handled. **Rerun** means it runs
unchanged inside the rerun vector step or the unchanged post-process; its
effect reaches the mesh only through the products the diff compares (§3).

| Pass | file:line | What it reads | Fast path |
|---|---|---|---|
| `generate_auto_patches`: manual detection | `src/auto_patch/driver.py:1566`, `:1661` | which ICAOs have a manual patch | rerun (vector) |
| `include_patches`: rings, alt tags, seeds | `src/O4_Vector_Map.py:3828-4278` | every way, `alt_abs`/`alt_rel`, roles | rerun → `.node`/`.poly` |
| OBJ8 patch objects | `src/O4_Vector_Map.py:4251`, `keep_obj8` `:4282` | `Patches/<tile>/<dir>/` | rerun |
| `encode_runways_taxiways_and_aprons` | `src/O4_Airport_Utils.py:1185` (`_airport_subsumed_by_patches` `:1156`) | `patches_list`, `patches_area` | rerun |
| `encode_hangars` | `src/O4_Airport_Utils.py:1502` | `patches_list`, `patches_area` | rerun |
| `flatten_helipads` | `src/O4_Airport_Utils.py:1533` | `treated_area` (patch union) | rerun |
| `include_roads`: the grading band | `src/O4_Vector_Map.py:2366`, band `:2553-2560`; `src/O4_Vector_Utils.py:2391-2476` | `patches_area` | rerun → `.node` z and sidecar |
| `road_bridge_deck_pins`, `road_join_yield_pins` | `src/O4_Vector_Map.py:2208`, `:2265` | patch `.osm` files | rerun |
| levelled-roads sidecar | written `src/O4_Vector_Map.py:2312` | levelled ways | rerun; **joins the vector record (F9)** |
| `include_sea`: sea seeds, wall admission | `src/O4_Vector_Map.py:3019`, `:3094-3129`; `sea_seed_areas` `:664`; `seawall_admission_area` `:258`; `insert_seawalls` `:588` | `patches_area`, `graded_area` | rerun |
| `include_water` | `src/O4_Vector_Map.py:3150`, `:3303` | `patches_area`, `graded_area` | rerun |
| `seed_interp_alt_subcells` | `src/O4_Vector_Map.py:3641`, `:3679-3695` | patch polygons, union | rerun → region records |
| `size_bank_annulus_regions` | `src/O4_Vector_Map.py:3597` → `_bank_rings_from_patches` `src/O4_Bank_Annulus.py:46` (reads files `:64-75`) | patch `.osm` bank rings | rerun → region areas |
| `audit_interp_alt_seed_sealing` | `src/O4_Vector_Map.py:3758` | the arrangement | rerun (a refusal stays a refusal) |
| Triangle4XP region plague | `Utils/src/Triangle4XP.c:13573` (`regionplague`) | seeds, segment marks | Tier 1: unchanged (D1 proves the same seeds and marks). Tier 2: seam check §5.3 |
| `build_curv_tol_weight_map` | `src/O4_Mesh_Utils.py:537` | `.apt` boundaries (not the patch) | Tier 1 and 2: `.apt` must be byte-identical |
| `patch_valued_vertex_indices` / `_patch_ring_edges` | `src/O4_Mesh_Utils.py:893`, `:996` | `.poly` PATCH_RING_MARKER edges | unchanged post-process |
| `patch_segment_split_values` | `src/O4_Mesh_Utils.py:1013` | ring edges, Steiner vertices on them | unchanged post-process |
| `bank_pavement_lines`, `_levelled_road_lines` | `src/O4_Mesh_Utils.py:1192` (files `:1220-1241`), `:1267` (`:1276`) | patch `.osm`, sidecar | unchanged post-process (why D0 still runs it) |
| `pavement_shore_vertices` | `src/O4_Mesh_Utils.py:1302` | pavement lines, water bits | unchanged post-process |
| `interp_alt_ribbon_vertex_indices` | `src/O4_Mesh_Utils.py:1420` | `.poly` INTERP_ALT edges | unchanged post-process |
| `bank_annulus_blend_values` / `audit_bank_annulus` | `src/O4_Mesh_Utils.py:1440`, `:1349` | bank rings, `.poly` | unchanged post-process |
| `patch_coverage_polygon` / `triangles_inside_coverage` / `audit_interp_alt_extent` | `src/O4_Mesh_Utils.py:1912`, `:1957`, `:1988` | `.poly` ring marker | unchanged post-process |
| `interpolate_free_interior_altitudes` | `src/O4_Mesh_Utils.py:711` | the patch-valued set, INTERP_ALT triangles | unchanged post-process (graph-wide: why §3 measures the change set) |
| object stage | `src/auto_patch/object_stage.py:865`, worklist `src/auto_patch/post_mesh.py:205-215` | manual or edited ICAOs (off), the mesh | unchanged (`_auto_patch_post_mesh_rebake`) |
| `O4_Step_Reuse`: patch outputs and inputs | `src/O4_Step_Reuse.py:167`, `:182` | file content; apt/CIFP/pack stamps | §8 |
| unmounted packs, unpatched record | `src/O4_Unmounted_Links.py:196`; `src/O4_Unpatched_Airports.py:79` | patch file names | rerun (vector) |
| patch editor | `src/o4_engine/patch_commands.py`, `patch_file.py` | the file | the writer; not a build pass |
| masks | `src/O4_Mask_Utils.py:1154-1200` | the mesh's water triangles only, never a patch | water-triangle witness §8 |
| DSF, airport fade masks | `src/O4_DSF_Utils.py:874`; `src/O4_Airport_Fade_Masks.py:266` | the `.mesh`; the `.apt` pickle | runs (Tier 1b lever, §10) |

`auto_patch_v2` reads no other patch file: the grep finds only
`airport/object_plan.py`'s own plan files. An edit therefore never changes
another airport's patch, and the driver's freshness gate keeps reusing them.

## 7. What forces a full rebuild (the mesh step runs as today)

1. **An input changed.** Any vector, mesh or masks reuse input other than
   patch content differs:
   - settings, engine or code digest, auto-patch configuration;
   - OSM, insets, `scenery_packs.ini`;
   - a patch's apt.dat, CIFP or pack stamp.

   That is any `stale_reason` key other than the outputs or `previous`
   (`src/O4_Step_Reuse.py:345-369`). The DSF step reruns in every case.
2. **The DEM or the airport boxes moved:** `.alt` or `.apt` differ (§3).
3. **The tile edge.** The change set, or the cavity, comes within R of the
   tile edge or touches a gluing edge (`src/O4_Vector_Map.py:1438-1459`).
   The outer boundary is `-Y`-fixed and is the seam to the neighbours,
   whose masks read this mesh (F6).
4. **The outline topology changed beyond the cavity:** the seam condition
   fails (§5.3). That covers a ring opened or closed, or a region merged
   or split, whose effect leaves the cavity.
5. **What the edit claims changes elsewhere.** Inside the vector step this
   needs no rule of its own: whatever the edit makes the roads, sea, water,
   walls or OBJ8 objects do shows up as a D2 change. It is then either
   inside the cavity, or rule 3 or 4 refuses it. In the object stage it
   always reruns, unchanged.
6. **Size.** The cavity holds more than a fraction of the tile's triangles
   (proposal 10 %); there is no gain left.
7. **Missing evidence:**
   - the kept raw artefacts are missing, or their digests do not match the
     mesh record;
   - the Triangle4XP binary is not the one that made them, or it lacks the
     switch;
   - `O4_STEP_REUSE=0`.
8. **A step fails.** The sub-run, the re-attribute run or the
   post-process audit fails, or the Tier 2 lawfulness audit fails.
9. **Owner Q1 answered no:** every D2 edit.

Each refusal is logged in a few words, the way `_reuse_step` words a stale
step (`src/o4_engine/session.py:1494-1518`). For example: "Mesh: full
rebuild (the edit reaches the tile edge)".

## 8. Cache needs and stamps (#615)

| Artefact | Written by | Kept today? | Stamped by | Needed for |
|---|---|---|---|---|
| `.node`, `.poly`, `.alt`, `.apt`, patch `.osm` | vector | yes (`cleaning_level ≤ 2`) | vector outputs, content (`src/O4_Step_Reuse.py:290`) | the diff (§3) |
| `o4_levelled_roads.json` | vector | yes | **not stamped (F9)**: add to the vector outputs | Tier 1, and the reuse law itself |
| raw `.1.node` (before the post-process) | Triangle4XP | **no** (overwritten `:2359`, deleted `:2831`) | **new**: mesh outputs, content | Tier 1 and 2 |
| `.1.ele` | Triangle4XP | **no** (deleted `:2831`) | **new**: mesh outputs | Tier 1 and 2 |
| `.1.prov` provenance | Triangle4XP `K` | **new** | **new**: mesh outputs | Tier 1 (and Tier 2, for outside Steiner vertices) |
| Triangle4XP binary digest | — | — | **new** field in the mesh record | Tier 1 admission |
| water-triangle digest of the `.mesh` | mesh | — | **new** field in the mesh record: sha256 over the water-bit triangles' (x, y, type), in file order | the masks witness |
| `.mesh` | mesh | yes | mesh outputs | the old/new change set; DSF input |
| `fast_path/prev/` | fast path | **new**, deleted after the step | content equal to the vector record's rows | the diff only |

Changes to `src/O4_Step_Reuse.py`:

1. Bump `SCHEMA`: every record then reads as none once, as the module's
   own history notes.
2. Vector outputs gain the sidecar. Mesh outputs gain the three raw files.
   The mesh record gains the binary digest and the water-triangle digest.
3. **New `edit_only_changes(tile)`:** the patch files whose content changed
   when every vector input key and every non-patch output row is as
   recorded; otherwise `None`. This is the cheap pre-check that says "the
   fast path may apply" before the vector step runs, and it feeds the plan
   prediction (`predicted_reuse`, `session.py:258`).
4. After a fast path, `record()` writes mesh, and masks when the witness
   held, exactly as after a run (#838 commits per step).
5. `forget_from` is unchanged: a Stop inside the fast path leaves no mesh
   record, and the next build runs the full mesh step.

Disk: the raw node file is 48 bytes per vertex (six doubles), the `.ele`
about 16 bytes per triangle, and the provenance about 30 bytes per Steiner
vertex. For a 2 M-vertex tile that is roughly 100 + 65 + 40 MB. This is
owner question Q2.

Registration, because CI failed four PRs on it this month:

- a new module (proposal `src/O4_Patch_Fast_Path.py`, entered from the mesh
  step) joins `O4_Step_Code` `ENTRY_MODULES["mesh"]` and `_SHARED` /
  `_BEYOND_SHARED`, and `src/auto_patch/provenance_code.py`
  `PATCH_CODE_MODULES`;
- `tests/test_step_code_closure.py` and `tests/test_patch_code_closure.py`
  must pass;
- any new exception class gets an `O4_Tile_Failures.EXCEPTION_CODES` code;
- every `open()` takes an `encoding=` for text files.

## 9. The equivalence and lawfulness checks

All are synthetic-first, on the frozen fixture (`tools/fixtures/make_mesh_dsf_fixture.py`,
`tests/test_mesh_dsf_oracle.py`). Its window already holds a flat PATCH RING
square at 112.5 m with a free DUMMY run inside, beside a WATER square.

- **E1: Triangle4XP ignores z (F1).** Run the fixture with the ring at
  112.5 m and at 113.25 m. The `.1.ele` is byte-identical, and `.1.node`
  columns 0 to 4 are byte-identical. In CI per platform, beside the text ==
  binary twin.
- **E2: Tier 1 equals a full rebuild.** Build the fixture, then
  re-altitude the ring.
  - **Arm A:** the full recipe.
  - **Arm B:** the fast path from Arm 0's kept artefacts.
  - **Pass:** `.mesh` sha256 equal, and both `.dsf` sha256 equal (the
    MD5 footer included), for `full_ortho` and `default_xplane`; the masks
    witness holds; every `stale_reason` afterwards is `None`.

  Run it on every platform with its own pinned Triangle4XP.
- **E3: refusals.** Each must take the full mesh step, with its words in
  the log:
  - a moved ring node gives D2 (and full when Q1 is no);
  - a ring vertex within R of the tile edge;
  - a changed mesh setting;
  - a missing `.1.prov`;
  - a binary without `K`.
- **E4: Tier 2 lawfulness (only if Q1 is yes).** Move one ring node by
  3 m.
  - The §5.4 audit passes.
  - Outside the cavity, every triangle and every vertex z equals the full
    rebuild's, except vertices in the graph-wide post-process sets, which
    are listed and compared within the 0.01 m materiality floor.
  - Inside the cavity, the authored vertices equal the rebuild's exactly.
  - Every point sample's region bits equal the rebuild's.
  - The max |z| difference of free terrain is reported, never iterated on.
- **E5: the closing test.** One representative airport, once (BUILD
  ECONOMY):
  1. `tools/harness/build_airport.py ICAO --tile LAT LON`;
  2. one height edit through the engine's `patch_save`;
  3. the rebuild through the fast path;
  4. a full rebuild of the same edit into a second build dir.

  Pass: equal `.mesh` and `.dsf` sha256 (Tier 1). Then the owner's sim
  read.

## 10. Expected time for a few-node edit

**Phase 0 must measure the current numbers.** The repo holds no current
per-step times for a tile: `build_time_baselines.json` `tiles` is empty,
and the per-tile history lives on the Mac (`~/.ortho4xp/tile_build_times`).
The recorded figures are below, with their dates. They are not a
prediction for current main.

| Phase | Recorded | Source |
|---|---|---|
| vector step without auto-patch generation | ~4 s (Cairo +30+031, 2026-07-25); KCLT +35-081 vector 68.7 s of a 107.4 s tile profile (2026-08-13) | `docs/whole_tile_5min_feasibility.md` §1.1; `docs/specs/perf-p3-wave2-sinks-spec.md` lane T |
| mesh step (Triangle4XP + post-process) | +51-001: 82-208 s; Cairo: 906 s on the ×3 grid, est. ~35 s after the bake fix (2.6 s Triangle4XP + 25-35 s Python post-process) (2026-07-25) | `whole_tile_5min_feasibility.md` §1.3, §2 |
| masks | 8.1 s (Cairo); 300-900 s (fjord coasts) (2026-07-25) | same §1.1, §1.3 |
| `build_dsf` | 84.6 s (HK +22+113, 266 MB mesh, masks warm, shared machine, 2026-10-19) | `docs/specs/dsf-and-masks-measure-first-spec.md` table |

Model:

- **Tier 1** = T_vector + T_reattribute (expected under 1 s) + T_post +
  T_objects + T_dsf.
- **Full rebuild** = T_vector + T_weights + T_triangle + T_post +
  T_objects + T_masks + T_dsf.
- **The saving is T_weights + T_triangle + T_masks.**

On the recorded figures the remaining Tier 1 wall is about 1.5-4 minutes on
a metro tile (vector 4-70 s, post-process 25-35 s, DSF ~85 s, object stage
not recorded). Whether that is a large or a small cut of the owner's
21 min 25 s depends on how that build split between steps, and the repo
does not record that.

**Phase 0 (the master, low effort, once):**

1. Run the owner's case:
   - `Ortho4XP/venv/bin/python tools/harness/build_airport.py <ICAO> --tile 51 -1 --no-ledger`,
     warm, for the airport the owner edited on +51-001;
   - then one `alt_abs` change in its `<ICAO>_edited.patch.osm`;
   - then the same command again.
2. Read the per-step seconds of the second build.
3. Run `tools/profile_tile_build.py 51 -1 --steps mesh,imagery` on that
   build dir, to split the mesh step into Triangle4XP, post-process and
   object stage, and the imagery step into `build_dsf` and the imagery
   check.
4. Report the table: T_vector, T_triangle, T_post, T_objects, T_masks,
   T_dsf, T_imagery.

Decision rule: start Tier 1 if T_weights + T_triangle + T_masks is at least
a third of the rebuild. Otherwise the cost is elsewhere, and the levers
below come first:

- **Tier 1b: z-only DSF re-encode.** Under D1 the positions, so the pool
  quadtree and every terrain-patch command, are unchanged. Only the
  altitudes and each pool's altitude range change. Re-encode only the pools
  that hold a changed vertex, and prove it on E2's `.dsf` sha256.
- **The vector step's per-airport freshness checks** ("the reuse checks
  for every airport" the issue names). They cannot simply be skipped: an
  auto patch's OSM witness covers the neighbour tiles' feeds
  (`auto_patch_stale_inputs`, `src/auto_patch/driver.py:370-457`), which
  the vector step's `osm` key does not. A shortcut needs a census table
  of freshness key → covering vector input first.

## 11. Cost to build, and phases

| Phase | Work | Effort (2026-10-20a) | Size |
|---|---|---|---|
| P0 | measurement (§10) | low, master | one warm build + one edited rebuild + one profile |
| P1 | Tier 1: Triangle4XP `K` + re-attribute (C, ~150 lines); `O4_Patch_Fast_Path.py` (~300 lines: admit, snapshot, diff, call, witness); `O4_Step_Reuse` (§8, ~60 lines); session hook; E1-E3 twins; F9 fix | medium (spec'd), one lane | ~2 rounds |
| P1b | z-only DSF re-encode, if P0 says DSF dominates | high | ~1-2 rounds |
| P2 | Tier 2 (§5), only if Q1 is yes | xhigh (architecture) | ~3-4 rounds |

No new UI control is needed if Q3 answers "automatic". A control would land
in both apps (two UIs, one layout, `tests/test_qt_layout_parity.py`).

## 12. Open owner questions

- **Q1.** For an edit that moves nodes or adds or removes ways: may the
  fast path give a mesh that is lawful but not byte-identical to a full
  rebuild? Lawful means the same constraints, the exact authored heights,
  the same water and land regions, and terrain within the mesher's own
  tolerance. Inside a small area around the edit the triangles differ.
  **Or must every geometric edit keep the full rebuild,** with only
  height-only edits taking the fast path? *Recommendation: height-only
  first (Tier 1); decide Tier 2 after Phase 0 and Tier 1 have measured
  what it would add.*
- **Q2.** The fast path needs the mesher's raw output kept after every
  build, roughly 100-200 MB on a big tile and much less on a rural one.
  Keep it for every tile, or only once a tile has an edited patch? With
  the second choice, the first edit after a build still takes one full
  rebuild. *Recommendation: every tile.*
- **Q3.** Should "Rebuild tile" pick the fast path by itself when it
  applies, with a log line ("height-only edit: mesh updated without
  re-meshing"), or should there be a separate "Apply edit" action?
  *Recommendation: automatic, with no new control.*
- **Q4.** Approve P0 (one measurement) now, and P1 only if P0 shows the
  saving is at least a third of the rebuild?
