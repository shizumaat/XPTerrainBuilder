"""The Qt 3D preview's state (spec patch-editor-20261015 §5, A7–A9; the Mac
app's ``TerrainPreviewModel``, ``TerrainPreviewBuildings`` and
``TerrainPreviewLastBuild``): follows the patch model LIVE and never writes
to it.

On a new document it asks the engine for the terrain (``terrain_sample``,
patch bbox + 500 m at 5 m) and triangulates every surface; on an edit it
rebuilds the buffers of the shapes that use a changed node, re-triangulates
only the shapes whose rings a topology change altered, and re-seats only
the buildings on those shapes.  The terrain cut-out follows moves after a
short pause.  Buildings (``pack_objects``, the box the map's pack outlines
ask for — one request for both) arrive after the ground ("Loading
buildings…").  "Last build" (``mesh_crop``) is fetched when first shown and
again only after the tile is rebuilt — never live.

Heavy work runs through ``PatchEngine.run`` off the GUI thread; the scene
(``O4_Qt_Preview3D_Scene.PreviewScene``) only receives arrays.
"""
from __future__ import annotations

import base64
import typing as _t

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from o4_engine import patch_edit as PE

from O4_Qt_Pack_Outlines import MARGIN_M
import O4_Qt_Preview3D_Buildings as BLD
import O4_Qt_Preview3D_Drape as DRP
import O4_Qt_Preview3D_Shapes as SHP
import O4_Qt_Preview3D_Terrain as TER

__all__ = ["PreviewModel", "NO_PATCH", "LOADING", "READY", "NO_PATCH_TEXT"]

NO_PATCH, LOADING, READY = "no_patch", "loading", "ready"
NO_PATCH_TEXT = "Zoom the map in on a built airport to preview its patch in 3D."
#: Edits pause this long before the terrain cut-out is recomputed.
CUT_DELAY_MS = 150


class PreviewModel(QObject):
    """What the 3D window shows; ``changed`` after any of its texts or
    states moved."""

    changed = Signal()

    def __init__(self, engine, patch_model, scene, built: _t.Callable[[], dict] = dict,
                 imagery: _t.Callable[[], tuple] | None = None, parent=None):
        """``built()`` → {(lat, lon): tile info with ``build_dir`` and
        ``mesh_date``}; ``imagery()`` → ``(cache_dir, source code, max
        zoom)`` of the map's display cache, or None."""
        super().__init__(parent)
        self.engine, self.patch, self.scene = engine, patch_model, scene
        self._built, self._imagery = built, imagery
        self.active = False
        self.status, self.icao, self.chip, self.terrain_error = NO_PATCH, None, "", None
        self.buildings_status, self.buildings_count = "none", 0
        self.buildings_missing: list[str] = []
        self.buildings_error = ""
        self.last_build = DRP.LastBuildState()
        self.last_build_triangles = 0
        self.drape_plan: DRP.DrapePlan | None = None
        self.exaggeration, self.wireframe = 3.0, False
        self.show_buildings, self.show_imagery = True, False
        self._gen = 0
        self._key = None
        self._doc: PE.PatchDoc | None = None
        self._frame: SHP.LocalFrame | None = None
        self.space: TER.PreviewSpace | None = None
        self.box: list[float] | None = None
        self.meshes: dict[int, SHP.ShapeMesh] = {}
        self.index = SHP.ShapeIndex({})
        self._topology_gen = 0
        self._seats: BLD.BuildingSeats | None = None
        self._groups: list[list[int]] = []          # model slot → placement indices
        self._facades: list[tuple[np.ndarray, float, float]] = []   # ring xz, height, base y
        self._mesh_locator: BLD.SurfaceLocator | None = None
        self._cut_timer = QTimer(self)
        self._cut_timer.setSingleShot(True)
        self._cut_timer.setInterval(CUT_DELAY_MS)
        self._cut_timer.timeout.connect(self._cut)
        patch_model.document_changed.connect(self._document_changed)
        patch_model.selection_changed.connect(self._update_markers)

    # ─── window lifecycle ──────────────────────────────────────────────
    def set_active(self, on: bool) -> None:
        """The window opened (follow the patch) or closed (stop)."""
        self.active = bool(on)
        if self.active:
            self._document_changed()

    def _doc_key(self):
        p = self.patch.patch
        return None if p is None else (self.patch.generation, p.tile, p.icao)

    def _document_changed(self) -> None:
        if not self.active:
            return
        doc = self.patch.doc
        if doc is None:
            if self._key is not None:
                self.clear()
            return
        if self._doc_key() != self._key:
            self.reload()
            return
        if self.space is None:                    # still loading: the load reads the latest doc
            return
        before, self._doc = self._doc, doc
        if before is doc:
            return
        change = SHP.diff_documents(before, doc)
        if change.topology:
            self._retriangulate(doc, change.nodes)
        elif change.nodes:
            ways = self.index.shapes_using(change.nodes)
            self._rebuild_buffers(ways, doc)
            self._reseat(ways, doc)
            self._cut_timer.start()
        self._update_markers()

    def clear(self) -> None:
        self._gen += 1
        self._key = self._doc = self._frame = self.space = self.box = None
        self.meshes, self.index = {}, SHP.ShapeIndex({})
        self._seats, self._groups, self._facades, self._mesh_locator = None, [], [], None
        self._cut_timer.stop()
        self.scene.remove_all()
        self.scene.set_imagery(None)
        self.drape_plan = None
        self.last_build, self.last_build_triangles = DRP.LastBuildState(), 0
        self.status, self.icao, self.chip, self.terrain_error = NO_PATCH, None, "", None
        self.buildings_status, self.buildings_count = "none", 0
        self.buildings_missing, self.buildings_error = [], ""
        self.changed.emit()

    # ─── full load ─────────────────────────────────────────────────────
    def reload(self) -> None:
        self.clear()
        self._gen += 1
        gen = self._gen
        doc = self.patch.doc
        p = self.patch.patch
        self._key = self._doc_key()
        self.icao = p.icao
        self.status = LOADING
        self.changed.emit()
        request = TER.terrain_request(doc.nodes.values())
        if request is None:
            self._ground(gen, None, "The patch has no nodes.")
            return
        self.box, spacing = request
        info = self._tile_info()

        def sampled(sample, error):
            if gen == self._gen:
                self._ground(gen, sample, error)
        if not self.engine.has("terrain_sample"):
            sampled(None, "This engine has no terrain_sample command; update the app.")
            return
        self.engine.call("terrain_sample", sampled, tile=p.tile, icao=p.icao, bbox=self.box,
                         spacing_m=spacing, build_dir=getattr(info, "build_dir", None) or None)

    def _ground(self, gen: int, sample, error) -> None:
        """The terrain arrived (or did not): build everything from the
        document as it is NOW (edits may have landed meanwhile)."""
        doc = self.patch.doc
        box = self.box

        def work():
            return _build_ground(doc, sample, box)

        def done(built, crash):
            if gen != self._gen:
                return
            if crash is not None:
                self.terrain_error = crash
                self.status = READY
                self.changed.emit()
                return
            self._install(doc, built, error)
        self.engine.run(work, done)

    def _install(self, doc: PE.PatchDoc, built: dict, terrain_error) -> None:
        self._doc, self._frame, self.space = doc, built["frame"], built["space"]
        if built.get("terrain") is not None:
            self.scene.set_terrain(*built["terrain"], extent=built["extent"])
        else:
            self.scene.extent = built["extent"]
        self.meshes = built["meshes"]
        self.index = SHP.ShapeIndex(self.meshes)
        self._rebuild_buffers(set(self.meshes), doc)
        self.scene.set_exaggeration(self.exaggeration)
        self.scene.set_wireframe(self.wireframe)
        self.scene.set_buildings_visible(self.show_buildings)
        self.chip = built["chip"]
        self.terrain_error = terrain_error
        self.status = READY
        self._update_markers()
        self._load_buildings()
        if self.show_imagery:
            self._start_drape()
        self.tile_built()
        self.scene.reset_view()
        self.changed.emit()

    # ─── incremental ───────────────────────────────────────────────────
    def _rebuild_buffers(self, ways: _t.Iterable[int], doc: PE.PatchDoc) -> None:
        """These shapes' vertex buffers from the current document."""
        if self.space is None:
            return
        self.scene.begin_shapes()
        try:
            self._set_buffers(ways, doc)
        finally:
            self.scene.end_shapes()

    def _set_buffers(self, ways: _t.Iterable[int], doc: PE.PatchDoc) -> None:
        for way in ways:
            mesh = self.meshes.get(way)
            if mesh is None or any(i not in doc.nodes for i in mesh.vertex_ids):
                self.scene.remove_shape(way)
                continue
            rows = [doc.nodes[i] for i in mesh.vertex_ids]
            positions = self.space.node_positions(rows)
            texcoords = DRP.uv([n[1] for n in rows], [n[2] for n in rows], self.box) if rows \
                else np.zeros((0, 2), np.float32)
            self.scene.set_shape(way, positions, TER.vertex_normals(positions, mesh.indices),
                                 texcoords, mesh.indices)

    def _retriangulate(self, doc: PE.PatchDoc, changed_nodes: frozenset) -> None:
        """A topology change: re-assemble the surfaces (holes follow
        nesting), then re-triangulate only the shapes whose rings differ."""
        self._topology_gen += 1
        gen, topo, frame = self._gen, self._topology_gen, self._frame
        previous = {w: m.shape for w, m in self.meshes.items()}

        def work():
            shapes = SHP.assemble(doc, frame)
            out = {s.way_id: SHP.ShapeMesh.of(s, doc, frame)
                   for s in shapes if previous.get(s.way_id) != s}
            present = {s.way_id for s in shapes}
            out.update({w: None for w in previous if w not in present})
            return out

        def done(changed, error):
            if error is not None or gen != self._gen or topo != self._topology_gen:
                return
            current = self.patch.doc or doc
            for way, mesh in changed.items():
                if mesh is None:
                    self.meshes.pop(way, None)
                else:
                    self.meshes[way] = mesh
            self.index = SHP.ShapeIndex(self.meshes)
            moved = self.index.shapes_using(changed_nodes) - set(changed)
            self._rebuild_buffers(set(changed) | moved, current)
            self._reseat(moved | set(changed), current)
            self._cut_timer.start()
            self._update_markers()
        self.engine.run(work, done)

    def _cut(self) -> None:
        """Recompute the terrain cut-out once edits pause."""
        terrain = self.space.terrain if self.space is not None else None
        if terrain is None:
            return
        gen, doc, shapes = self._gen, self._doc, [m.shape for m in self.meshes.values()]

        def work():
            return TER.kept_indices(terrain.grid, TER.covered_triangles(terrain.grid, shapes,
                                                                         doc.nodes))

        def done(indices, error):
            if error is None and gen == self._gen:
                self.scene.set_terrain_indices(indices)
        self.engine.run(work, done)

    def _update_markers(self) -> None:
        doc = self.patch.doc
        if self.space is None or doc is None:
            self.scene.set_markers(np.zeros((0, 3), np.float32))
            return
        rows = [doc.nodes[i] for i in sorted(self.patch.marked_nodes) if i in doc.nodes]
        self.scene.set_markers(self.space.node_positions(rows))

    # ─── buildings ─────────────────────────────────────────────────────
    def _load_buildings(self) -> None:
        p = self.patch.patch
        if p is None or self.box is None or not self.engine.has("pack_objects"):
            return
        gen, doc, space = self._gen, self._doc, self.space
        meshes, frame = dict(self.meshes), self._frame
        self.buildings_status = "loading"

        def arrived(result, error):
            if gen != self._gen:
                return
            if error is not None:
                self.buildings_status, self.buildings_error = "failed", error
                self.changed.emit()
                return
            locator = BLD.SurfaceLocator.of_shapes(meshes, doc.nodes, frame)
            self.engine.run(lambda: _build_buildings(result, locator, space),
                            lambda built, crash: self._buildings_built(gen, result, built, crash))
        self.engine.pack_objects(p.tile, p.icao, self.box, arrived)

    def _buildings_built(self, gen: int, result, built, crash) -> None:
        if gen != self._gen:
            return
        if crash is not None:
            self.buildings_status, self.buildings_error = "failed", crash
            self.changed.emit()
            return
        self._seats, self._groups, self._facades = built["seats"], built["groups"], built["facades"]
        self.scene.set_buildings(
            [(pos, nrm, BLD.instance_table([self._seats.poses[i] for i in group], self.exaggeration))
             for (pos, nrm), group in zip(built["models"], self._groups)],
            self._facade_positions())
        self.buildings_status = "ready"
        self.buildings_count = len(self._seats.placements) + len(self._facades)
        self.buildings_missing = list(result.get("missing") or [])
        if self.last_build.showing_mesh and self._mesh_locator is not None:
            self._seat_all(self._mesh_locator)
        self.changed.emit()

    def _facade_positions(self) -> np.ndarray:
        parts = [BLD.facade_mesh(ring, height, base * self.exaggeration)
                 for ring, height, base in self._facades]
        return np.vstack(parts) if parts else np.zeros((0, 3), np.float32)

    def _push_tables(self, moved: _t.Iterable[int]) -> None:
        """New instance rows for the models whose placements moved."""
        moved = set(moved)
        if not moved or self._seats is None:
            return
        tables = {slot: BLD.instance_table([self._seats.poses[i] for i in group], self.exaggeration)
                  for slot, group in enumerate(self._groups) if moved.intersection(group)}
        self.scene.set_building_tables(tables)

    def _reseat(self, ways: _t.Collection[int], doc: PE.PatchDoc) -> None:
        """After an edit: re-seat the placements on these shapes (Preview only)."""
        if self._seats is None or not ways or self.last_build.mode != DRP.PREVIEW:
            return
        locator = BLD.SurfaceLocator.of_shapes(self.meshes, doc.nodes, self._frame)
        self._push_tables(self._seats.reseat(set(ways), locator, self.space))

    def _seat_all(self, locator: BLD.SurfaceLocator) -> None:
        if self._seats is not None:
            self._push_tables(self._seats.reseat_all(locator, self.space))

    # ─── toggles ───────────────────────────────────────────────────────
    def set_exaggeration(self, value: float) -> None:
        self.exaggeration = min(10.0, max(1.0, float(value)))
        self.scene.set_exaggeration(self.exaggeration)
        if self._seats is not None:
            self._push_tables(range(len(self._seats.placements)))
            self.scene.set_facades(self._facade_positions())
        self.changed.emit()

    def set_wireframe(self, on: bool) -> None:
        self.wireframe = bool(on)
        self.scene.set_wireframe(self.wireframe)
        self.changed.emit()

    def set_show_buildings(self, on: bool) -> None:
        self.show_buildings = bool(on)
        self.scene.set_buildings_visible(self.show_buildings)
        self.changed.emit()

    def set_show_imagery(self, on: bool) -> None:
        self.show_imagery = bool(on)
        if self.show_imagery:
            self._start_drape()
        else:
            self.drape_plan = None
            self.scene.set_imagery(None)
        self.changed.emit()

    def _start_drape(self) -> None:
        source = self._imagery() if self._imagery is not None else None
        if self.box is None or source is None:
            self.scene.set_imagery(None)
            return
        cache_dir, code, max_zoom = source
        plan = DRP.DrapePlan.plan(self.box, max_zoom)
        self.drape_plan = plan
        if plan is None:
            return
        from O4_Qt_Preview3D_Scene import TERRAIN_COLOR
        gen = self._gen

        def done(reply, error):
            if gen == self._gen and self.show_imagery and self.drape_plan is plan and error is None:
                self.scene.set_imagery(reply[0])
                self.changed.emit()
        self.engine.run(lambda: DRP.compose_drape(plan, cache_dir, code, TERRAIN_COLOR), done)

    @property
    def drape_chip(self) -> str:
        """The drape texture's size, for the chip ("" when off)."""
        p = self.drape_plan
        return " · imagery %d × %d px (ZL %d)" % (p.width, p.height, p.zoom) \
            if self.show_imagery and p is not None else ""

    @property
    def buildings_chip(self) -> str:
        if self.buildings_status == "loading":
            return " · Loading buildings…"
        if self.buildings_status == "ready":
            return " · {:,} pack objects".format(self.buildings_count)
        return ""

    @property
    def last_build_chip(self) -> str:
        return (" · last build mesh {:,} triangles".format(self.last_build_triangles)
                if self.last_build.showing_mesh else "")

    # ─── Last build ────────────────────────────────────────────────────
    def _tile_info(self):
        p = self.patch.patch
        if p is None:
            return None
        from O4_File_Names import parse_tile_key
        tile = parse_tile_key(p.tile)
        return (self._built() or {}).get(tuple(tile)) if tile else None

    def select_mode(self, mode: str) -> None:
        info = self._tile_info()
        was = self.last_build.showing_mesh
        fetch = self.last_build.select(mode, getattr(info, "mesh_date", None))
        self._mode_shown(was)
        if fetch:
            self._fetch_mesh()
        self.changed.emit()

    def tile_built(self) -> None:
        """The scan reported the tile again: a new mesh date refetches
        when Last build is showing, else on its next showing."""
        if self.space is None:
            return
        info = self._tile_info()
        if self.last_build.tile_built(getattr(info, "mesh_date", None)):
            self._fetch_mesh()
        self.changed.emit()

    def _mode_shown(self, was_showing: bool) -> None:
        now = self.last_build.showing_mesh
        self.scene.show_last_build(now)
        if was_showing == now or self.space is None or self._doc is None:
            return
        if now and self._mesh_locator is not None:
            self._seat_all(self._mesh_locator)
        elif not now:
            self._seat_all(BLD.SurfaceLocator.of_shapes(self.meshes, self._doc.nodes, self._frame))

    def _fetch_mesh(self) -> None:
        p, info = self.patch.patch, self._tile_info()
        if p is None or self.box is None or self.space is None:
            return
        gen, space, box = self._gen, self.space, self.box
        self.last_build.fetching(getattr(info, "mesh_date", None))
        self.changed.emit()

        def decoded(built, error):
            if gen != self._gen:
                return
            was = self.last_build.showing_mesh
            if error is not None:
                self.last_build.fetched(False, error)
            else:
                positions, normals, texcoords, indices, locator = built
                self._mesh_locator = locator
                self.last_build_triangles = len(indices) // 3
                self.scene.set_last_build(positions, normals, texcoords, indices)
                self.last_build.fetched(True)
            self._mode_shown(was)
            self.changed.emit()

        def cropped(crop, error):
            if gen != self._gen:
                return
            if error is not None:
                decoded(None, error)
                return
            self.engine.run(lambda: _decode_mesh(crop, space, box), decoded)
        self.engine.call("mesh_crop", cropped, tile=p.tile, bbox=box,
                         build_dir=getattr(info, "build_dir", None) or None)


# ─── off-thread work (pure) ───────────────────────────────────────────────

def _build_ground(doc: PE.PatchDoc, sample, box) -> dict:
    """Shapes, triangles, the terrain mesh and its cut-out, the chip."""
    frame = SHP.LocalFrame.of(doc)
    meshes = SHP.mesh_shapes(SHP.assemble(doc, frame), doc, frame)
    surface = TER.TerrainSurface(sample) if sample is not None else None
    alts = [n[3] for n in doc.nodes.values() if n[3] is not None]
    base = surface.min_elevation if surface is not None else (min(alts) if alts else 0.0)
    space = TER.PreviewSpace(frame, base, surface)
    lats = [n[1] for n in doc.nodes.values()]
    lons = [n[2] for n in doc.nodes.values()]
    lo = space.position(min(lats), min(lons), base)[0]
    hi = space.position(max(lats), max(lons), base)[0]
    centre = tuple(float(v) for v in (lo + hi) / 2)
    extent = (centre, float(max(abs(hi[0] - lo[0]), abs(hi[2] - lo[2])) / 2 + MARGIN_M / 2))
    out = {"frame": frame, "space": space, "meshes": meshes, "extent": extent,
           "terrain": None, "chip": "Preview · no terrain"}
    if surface is not None:
        positions, normals = TER.terrain_vertices(surface, space)
        lat, lon = surface.grid.lat_lon()
        covered = TER.covered_triangles(surface.grid, [m.shape for m in meshes.values()], doc.nodes)
        out["terrain"] = (positions, normals, DRP.uv(lat, lon, box),
                          TER.kept_indices(surface.grid, covered))
        out["chip"] = TER.chip_text(sample)
    return out




def _build_buildings(result: _t.Mapping, locator: BLD.SurfaceLocator,
                     space: TER.PreviewSpace) -> dict:
    """Models (shared massing), seats, instance groups and facades."""
    models, slots = [], {}
    for m in result.get("models") or ():
        positions, normals = BLD.model_mesh(m)
        if len(positions):
            slots[m["key"]] = len(models)
            models.append((positions, normals))
    drawn = [p for p in result.get("placements") or () if p.get("model") in slots]
    seats = BLD.BuildingSeats(drawn, locator, space)
    groups: list[list[int]] = [[] for _ in models]
    for i, p in enumerate(drawn):
        groups[slots[p["model"]]].append(i)
    facades = []
    for f in result.get("facades") or ():
        ring = f.get("ring") or []
        if len(ring) < 3:
            continue
        lat = sum(float(p[0]) for p in ring) / len(ring)
        lon = sum(float(p[1]) for p in ring) / len(ring)
        _way, ground = locator.surface(lat, lon, space)
        xyz = space.position([p[0] for p in ring], [p[1] for p in ring], space.base)
        facades.append((xyz[:, [0, 2]], float(f.get("height_m") or 0.0), ground - space.base))
    return {"models": models, "seats": seats, "groups": groups, "facades": facades}


def _decode_mesh(crop: _t.Mapping, space: TER.PreviewSpace, box) -> tuple:
    """``mesh_crop`` → preview positions, upward normals, drape UVs,
    indices and the surface buildings stand on in Last build."""
    v = np.frombuffer(base64.b64decode(crop["vertices_f64_b64"]), dtype="<f8").reshape(-1, 3)
    t = np.frombuffer(base64.b64decode(crop["triangles_u32_b64"]), dtype="<u4")
    positions = space.position(v[:, 1], v[:, 0], v[:, 2]) if len(v) else np.zeros((0, 3), np.float32)
    normals = TER.vertex_normals(positions, t)
    normals[normals[:, 1] < 0] *= -1          # the mesh's winding is Triangle's: shade up
    texcoords = DRP.uv(v[:, 1], v[:, 0], box) if len(v) else np.zeros((0, 2), np.float32)
    locator = BLD.SurfaceLocator.of_mesh(v, t.reshape(-1, 3), space.frame)
    return positions, normals, texcoords, np.ascontiguousarray(t, dtype=np.uint32), locator
