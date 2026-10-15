# Patch editor and 3D preview (#46) — spec 2026-10-15

Status: APPROVED by the owner 2026-10-15 ("Plan is approved"). Branch
`claude/patch-editor`. Mockup: `docs/mockups/patch-editor-20261015.html`
(also published as the design page the owner reviewed).

The app draws the patch the engine will build for an airport when the map is
zoomed in on it, and lets the user edit it JOSM-style: select, multi-select,
drag, delete and insert nodes, set or offset elevation, undo. Saving writes a
MANUAL patch, which the engine already prefers over the auto patch. A
separate 3D window shows the terrain with the patch applied and the pack's
buildings, live while editing. Mac first, then Qt parity.

## 0. Owner answers (2026-10-15, interview)

| # | Question | Answer |
|---|---|---|
| A1 | How saved edits relate to future auto patches | Full manual patch (the existing override). No delta overlay. |
| A2 | Airport with no patch on disk | Built patches only ("Build this tile first"). No patch-only generate. |
| A3 | Grade-law checking of edits | None. What the user edits is what gets built. |
| A4 | v1 extras | Multi-select + offset; pack reference outlines; Qt parity. |
| A5 | Zero-violation acceptance for an edited airport | "yes": violations are reported, never fail the build, result labelled "user-edited". |
| A6 | File name | "yes": `<ICAO>_edited.patch.osm`. |
| A7 | Object re-seating with an edited patch | "Yes" (stays off) — plus: show the pack's buildings in the 3D view. |
| A8 | 3D placement | "3D view only as a separate window." |
| A9 | 3D extent | "Yes": patch bbox + 500 m, 5 m spacing. |
| A10 | Near-coincident nodes | "I only meant in the editor, that when the user is moving nodes, within 0.5m they snap together" — and: the pointer snaps the dragged node to a node within 0.5 m, dragging away releases it, and it merges only on release while snapped (§3.3). Snap radius: "8 pt on screen" (owner, 2026-10-15 — at airport zoom 0.5 m of ground is under 0.1 pt). No merge pass at save. |

Relevant law: RULINGS 2026-09-13cg (iii) (sub-spacing merge), 05e (no
airport-specific code), 30l (consumer census — §1.3 below).

## 1. Files and the override (existing engine behaviour — reuse, do not re-implement)

1.1 Layout: `Patches/<10° dir>/<1° tile>/` (`O4_File_Names.patch_dir`). Auto
patch `<ICAO>_auto.patch.osm`; any other `*.patch.osm` whose prefix before
the first `_` is the ICAO is a MANUAL patch and replaces the auto patch
(`O4_Vector_Map.include_patches`, `driver.py` manual detection,
`auto_patch_not_applied` turns object re-seating off).

1.2 Save target: `<ICAO>_edited.patch.osm`, written atomically (temp file +
`os.replace`). Header (root `<osm>` attributes): every `o4_*` freshness stamp
of the patch the edit started from, re-keyed without their `o4_` prefix as `o4_edited_from_<name>` (e.g.
`o4_cfg` → `o4_edited_from_cfg`; the stamp readers are unanchored, so
`o4_edited_from_o4_cfg` would read as a live stamp), plus
`o4_user_edited="1"`. Revert renames it to `<ICAO>_edited.patch.osm.disabled`
(never deletes). If a DIFFERENT manual patch already exists for the ICAO (a
JOSM file), the editor loads that one and saves back to IT (same path); A6
names only the editor's own new files. Such a file has no "Revert to auto"
(the pane says it was made outside the editor; undo still works within the
session); `patch_revert` refuses it. "Hand-made" is decided by FILE NAME: any manual
patch other than `<ICAO>_edited.patch.osm` (saving stamps
`o4_user_edited` on both, since both are the user's edits).

1.3 Consumer census (30l) of the saved file — every reader of a manual patch:
`include_patches` (geometry; `alt_abs` per node is taken as-is),
`auto_patch_not_applied` (re-seating off), `driver.py` manual detection (skips
the auto-patch stage), the build census / acceptance (A5 — L1 reads how a
manual patch is treated today and makes it report-not-fail with the label),
the app's "modified airports" / reanchor status (unchanged). L1 confirms this
list by grep and reports any reader it adds.

1.4 Staleness: `patch_load` compares the recorded `o4_edited_from_*` stamps
with the stamps the current inputs would produce, through
`driver.auto_patch_stale_inputs` (extracted by L1 from
`_auto_patch_is_current`, which now calls it).
Different → `stale: true` + the names of the inputs that moved.

## 2. Wire protocol 1.12 (frozen interface)

`PROTOCOL_VERSION` "1.11" → "1.12". Commands only, replies only — NO new
event classes, so the event-name wire hazard (`events.py` ↔
`OrthoEngineClient.swift`) is untouched. Errors reply `ok: false` with an
`error` sentence naming the cause and the fix. Binary arrays are base64 of
little-endian packed values. `tile` is the `+45-123` key. Lat/lon are
degrees, elevations metres MSL.

```
patch_list   {tile}
  -> {airports: [{icao, source: "auto"|"manual", path,
                  bbox: [min_lat, min_lon, max_lat, max_lon], nodes, ways}]}
patch_load   {tile, icao}
  -> {icao, source, path, stale, stale_inputs: [str],
      min_distinct_spacing_m, identity_dp, header: {k: v},
      nodes: [[id, lat, lon, alt_or_null], ...],
      ways:  [{id, refs: [id, ...], tags: {k: v}}, ...]}
patch_save   {tile, icao, base_path, nodes, ways}
  -> {path, nodes: <count>, ways: <count>}
patch_revert {tile, icao} -> {disabled_path}
pack_outlines {tile, icao}
  -> {pavement: [{kind: "pavement"|"boundary", rings: [[[lat, lon], ...], ...]}],
      footprints: [{role, rings}], missing: [reason]}
terrain_sample {tile, icao, bbox, spacing_m}
  -> {bbox, rows, cols, spacing_m, dlat, dlon, elev_f32_b64,
      sources: {base, inset}}          # row-major, row 0 = south edge
mesh_crop    {tile, bbox}
  -> {mesh_path, vertices_f64_b64 /* lon, lat, elev triples */,
      triangles_u32_b64}
pack_objects {tile, icao, bbox}
  -> {models: [{key, vertices_f32_b64 /* authored x, y, z m */,
                triangles_u32_b64}],
      placements: [{model, lat, lon, heading_deg, agl_m}],
      facades: [{ring: [[lat, lon], ...], height_m}],
      missing: [reason]}
```

Clarified 2026-10-15 (after L2): `terrain_sample.sources` is
`{base: <path>, inset: <path or null>}`; `pack_objects.models[].key` is a
string. The DOCUMENT ORIGIN (§3.3) is the centre of the document's bbox at
load time (mean of min/max lat and of min/max lon), fixed for the document's
life.

Amended 2026-10-15 before L4/6c (additive or narrowing, by the spec
author): (a) `pack_outlines` returns `pavement` (rows 110 pavement and 130
boundary, beziers flattened by `auto_patch_v2/airport/apt_dat.py`) and
`missing`; `footprints` is DROPPED — the map draws building footprints from
the `pack_objects` result (the plan outline of each placed model's hulls),
so buildings are read once, by one command. (b) `terrain_sample` and
`mesh_crop` take an optional `build_dir` (the tile's build folder as the app
knows it); absent → the default `Tiles/` folder.

Node ids are the file's (negative) ids. The client allocates new node ids
below the document's minimum id; way ids are kept. `patch_save` writes ways
and nodes in the order given; tags are written back unchanged.

`terrain_sample` reuses `auto_patch_v2/airport/dem.load_dem` (base + insets,
the airport solve's own DEM). `mesh_crop` reuses the `.mesh` parser in
`auto_patch/mesh_sampler.py`; a mesh removed by `cleaning_level` > 2 is an
error saying so. `pack_objects` reuses `auto_patch_v2/airport/dsf.py`
placements and `airport/obj8.py` (`parse_obj8`, `ResourceCache`): solid,
non-animated triangles only, each model once. All three read caches only — a
missing DEM, DSF dump or library index is reported, never downloaded or
regenerated (data-repo law: refreshes are explicit events).

## 3. Edit operations (one spec, two implementations, one twin)

Python `o4_engine/patch_edit.py` (Qt imports it directly); Swift
`SceneryKit/PatchDocument.swift`. A shared fixture
`Ortho4XP/tests/fixtures/patch_edit_ops.json` — op sequences with the
expected document after each — runs in pytest AND `swift test`; the two
implementations cannot drift.

3.1 Operations: `move(ids, dlat, dlon)`, `set_position(id, lat, lon)`,
`set_alt(ids, alt)`, `offset_alt(ids, d)`, `delete_nodes(ids)`,
`insert_on_edge(a, b)`, `merge_nodes(source, target)` (§3.3).

3.2 Topology rules. Delete removes the node from every way. After any op,
consecutive duplicate refs collapse; a closed way (first == last) left with
fewer than 3 distinct nodes, or an open way with fewer than 2, is removed in
the same step. `insert_on_edge` places the node at the midpoint, alt = mean of
the two endpoints (null if either is null), into EVERY way in which `a`, `b`
are consecutive in either direction (shared edges stay welded).

3.3 Snap while dragging (A10, owner clarification 2026-10-15: "when dragging
a node the mouse comes within 0.5m of another node it should try and snap to
that node, if the user does not release the mouse button and drags away it
moves away, only merging if the user releases the mouse button over the
snapped nodes"). This is drag-time UI plus ONE explicit operation:
- During a drag, when the POINTER comes within the snap radius of another
  (non-dragged) node, the grabbed node is drawn AT that node (snap
  highlight); the rest of a multi-selection keeps following the pointer
  delta. Dragging back out of the radius releases the snap and the node
  follows the pointer again. Nothing is merged while the button is down.
- On release while snapped: one undo step = `move` of the selection to the
  release position + `merge_nodes(grabbed, target)`. On release while not
  snapped: `move` only.
- `merge_nodes(source, target)` (added to §3.1): the TARGET survives with
  its position and elevation; every ref to `source` becomes `target`; 3.2
  applies (consecutive duplicates collapse, degenerate ways go). It checks
  no distance — the UI decided.
- Snap radius (owner, 2026-10-15): 8 pt ON SCREEN from the pointer to the
  node, at any zoom — the same radius as clicking a node. Several
  candidates: nearest on screen wins, ties by the engine's `survivor_key`
  (the fixture's `ui_snap_reference` documents it). `min_distinct_spacing_m`
  is still served by `patch_load` (for display and future checks); the snap
  does not use it.
Nothing else merges: `move`, inserts, elevation edits, deletes and
`patch_save` never merge, and untouched geometry is never changed —
twin-tested: `patch_load` → `patch_save` with no edits rewrites the same nodes
and ways (real patches carry node pairs at 0.499–0.500 m — 125 in the data-repo
HECA patch of 2026-10-15 — that must stay as they are).

## 4. Mac app

Files (new unless noted): `SceneryKit/PatchDocument.swift` (model, §3 ops,
spatial grid for hit-testing), `SceneryKit/PatchTriangulator.swift`
(ear-clipping with holes, per shape), `XPTerrainBuilder/PatchEditModel.swift`
(document, selection, mode, undo registration),
`XPTerrainBuilder/PatchOverlay.swift` (drawing + gestures; `MapCanvasView`
gains a few lines only), `XPTerrainBuilder/PatchInspector.swift` (the
"Patch · ICAO" box in `BuildPane`, below Activity),
`XPTerrainBuilder/TerrainPreviewWindow.swift` (3D), `OrthoEngineClient.swift`
(edit: eight wrappers).

Display: when the view is narrower than ~0.08° and a built tile in view has
a patch (`patch_list`) whose bbox intersects the viewport, the airport whose
bbox is nearest the viewport centre is loaded (one at a time). Nodes are drawn
when ≥ 6 pt apart on screen; drawing is viewport-culled; a drag rebuilds only
the moved nodes' shapes, in a layer separate from the base map.

Interaction (View / Edit segmented control on the map): Edit-mode click
selects (8 pt hit radius), ⇧-click toggles, ⇧-drag box-selects, drag on a node
moves the selection (drag on empty map pans), "+" handles at the midpoints of
the selected nodes' shapes' edges (and on hover) insert, ⌫/⌦ delete, ⌘Z/⇧⌘Z
through the window's `UndoManager` (a drag coalesces to one step; history
survives a save), ⌘S save, Esc clears. Inspector: lat/lon, elevation field
(m, with ft and the original value), "used by" roles, delete; multi-selection:
range, "Set to", "Offset", delete. Save bar: unsaved-edit count, "Revert to
auto…" (confirmation inside the pane), Save; after save "Rebuild tile" and the
re-seating note; a stale edited patch shows the stale note. Unsaved edits
prompt on airport switch and quit. Hand-made patches whose nodes carry no
`alt_abs` show "elevation from the mesh".

## 5. 3D preview (separate window, A8)

`WindowGroup(id: "terrain-preview")`, ⌘3 / toolbar "3D". SceneKit; orbit
(drag), zoom (scroll), pan (⌥-drag), vertical exaggeration ×1–×10, Imagery /
Buildings / Wireframe toggles, "Preview | Last build". Extent (A9): patch
bbox + 500 m, 5 m spacing. PREVIEW: `terrain_sample` grid with the patch
faces cut out, patch shapes triangulated at their node elevations, one
geometry per shape (an edit rebuilds one buffer); selection highlighted in
sync with the map. BUILDINGS: `pack_objects` models as shared geometry
(clones), each placement at `preview_surface(anchor) + agl + y` — X-Plane's
own drape at the anchor — so lowering ground under a building shows it
floating, as it would in the sim (re-seating is off for an edited patch).
LAST BUILD: `mesh_crop`, refreshed after a rebuild only. Read-only: no
picking or editing in 3D.

Ruled after L6a (2026-10-15): (1) a closed patch way nested inside another
surface is a HOLE of its direct parent unless it lies inside one of the
parent's `gap_interior_ring`s (the emitter writes no hole that inner faces
cover — HECA 179, LEMD 213, KUAO 137 nested faces). (2) Above the 4 M-sample
cap the client coarsens the spacing in 0.5 m steps and the chip shows the
spacing used. (3) The terrain should be the one the mesh drapes on: use the
tile's composed production DEM (`dem_frame="production"`) when it is
readable from cache, else the authored base + inset (`load_dem`), with the
inset feather from the tile's cfg; the chip names which (6b). (4)
`terrain_sample` runs on the engine's read loop (~0.25 s for HECA's 1.95 M
samples).

Ruled after 6b's size stop (2026-10-15): full pack meshes are too heavy for
the preview (HECA: 460 models, 3,118 placements, 2.75 M solid triangles,
176 MB reply, ~5 s). BUILDINGS ARE GREY MASSING, as the mockup says: each
model is sent as the CONVEX HULL of each of its solid connected components
(`airport/obj8.solid_components`, already position-welded to 1 mm),
components under 2 m in every dimension dropped. Bar: HECA reply ≤ 10 MB. If
the command still takes more than 1 s, it replies `{status: "started"}` and
completes through ONE new event, `PackObjectsReady {request: <cmd id>,
result | error}`, from a worker thread — the `airport_index` /
`AirportIndexReady` pattern; the event class name is the wire name on both
sides (`events.py` ↔ `OrthoEngineClient.swift`). The pristine DSF is right:
with an edited patch, re-seating is off and the pack's authored placements
are what X-Plane draws. Custom build folders get the authored DEM until
`terrain_sample` learns the tile's build folder (6c).

Ruled after the massing measurement (2026-10-15; HECA 413 models, 3,071
placements, 745 k hull triangles, 19.5 MB, 13–17 s): the 10 MB bar was a
guess and is replaced. The component hulls stay as built (no snapping, no
cluster merge). Limit: a reply over 50 MB drops the smallest remaining
components first until it fits, and says how many in `missing`. The command
is ASYNCHRONOUS (`{status: "started"}` + `PackObjectsReady`), and the engine
keeps the result in memory for the session keyed by pack DSF path and mtime,
so reopening the window is instant. The 3D window shows the terrain and patch
at once and adds the buildings when they arrive ("Loading buildings…").
## 6. Qt (L5, L7)

The same overlay, inspector and 3D window in `O4_Qt_Map.py` (+ new modules,
not appends), `QUndoStack`, calling `patch_edit.py` directly; 3D via
pyqtgraph's OpenGL widget.

## 7. Not in v1

Grade checking (A3); patch-only generation (A2); delta overlay (A1); new
shapes, tag editing, way split/join; elevation colour ramp; editing in 3D;
live exact remesh.

## 8. Lanes (Opus, moderate; the spawner owns the merge into `claude/patch-editor`)

| Lane | Scope | Order |
|---|---|---|
| L1 | Engine: protocol 1.12, `patch_list/load/save/revert`, `patch_edit.py`, the §3.3 shared merge helper, the twin fixture, A5 label, tests | first |
| L2 | Mac read-only render: wrappers, `PatchDocument`, overlay, View-mode inspector | parallel with L1 against §2 |
| L3 | Mac Edit mode (§4 interaction, undo, save/revert) | after L1 + L2 |
| L4 | `pack_outlines` + drawing (Mac; Qt in L5) | after L1 |
| L5 | Qt parity of L2–L4 | after L3 |
| L6 | 3D (Mac): 6a `terrain_sample` + triangulator + window + live preview; 6b `pack_objects` + buildings; 6c imagery drape + `mesh_crop` / Last build | 6a after L2, alongside L3 |
| L7 | 3D (Qt) | after L5 + 6a |

Closing test (once, at the end): on one built airport, edit a few nodes, save,
rebuild the tile; the build log says "using the MANUAL patch" and the mesh
reads the new elevations at those points. No sweep: auto patches are
unchanged unless an edited file exists.

Build-time impact: none on the build path (commands run on demand; the A5
label is a header read). No airport-specific code anywhere (05e).
