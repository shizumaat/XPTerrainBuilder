"""The Qt 3D preview (issue #46, spec patch-editor-20261015 §5, §6): the
surface assembly and triangulation on the L2 fixture face, the terrain
cut-out rule, the building seat transform, a change re-meshing only the
touched shapes and re-seating only their buildings, the drape tile plan,
the "Last build" state, the shared ``pack_objects`` request and the window's
words.

Headless (offscreen Qt).  Offscreen Qt Quick has no RHI, so Qt Quick 3D
DRAWS NOTHING here: the scene graph is loaded and fed, and the model layer
is what is asserted.  No engine process, no network, no X-Plane."""

import base64
import json
import math
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")
pytest.importorskip("PySide6.QtQuick3D")

import numpy as np  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_Qt_Preview3D_Buildings as BLD  # noqa: E402
import O4_Qt_Preview3D_Drape as DRP  # noqa: E402
import O4_Qt_Preview3D_Shapes as SHP  # noqa: E402
import O4_Qt_Preview3D_Terrain as TER  # noqa: E402
from O4_Qt_Patch_Engine import PatchEngine  # noqa: E402
from O4_Qt_Patch_Model import LoadedPatch, PatchEditModel  # noqa: E402
from O4_Qt_Preview3D_Model import PreviewModel  # noqa: E402
from o4_engine import patch_edit as PE  # noqa: E402

#: The Mac tests' real face with its gap ring (L2's fixture, one file for both apps).
FACE = os.path.join(os.path.dirname(__file__), "..", "..", "Tests", "SceneryKitTests",
                    "Fixtures", "PatchEditor", "patch_face_with_hole.json")


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _signed(xy, tri):
    (ax, ay), (bx, by), (cx, cy) = (xy[v] for v in tri)
    return ((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) / 2


def _ring_area(pts):
    x, y = np.array(pts).T
    return abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2


def _nested(gap_shape_id):
    """The Mac test's document: a 0.01° square face (-101), a gap ring
    inside it (-102) and a face inside the square but outside the gap (-103)."""
    nodes = [(-1, 45.00, -123.00), (-2, 45.00, -122.99), (-3, 45.01, -122.99), (-4, 45.01, -123.00),
             (-5, 45.002, -122.998), (-6, 45.002, -122.996), (-7, 45.004, -122.996),
             (-8, 45.004, -122.998), (-9, 45.006, -122.994), (-10, 45.006, -122.992),
             (-11, 45.008, -122.992)]
    gap = {"o4_feature": "gap_interior_ring"}
    if gap_shape_id is not None:
        gap["shapeID"] = gap_shape_id
    return PE.PatchDoc.from_wire(
        [[i, la, lo, 100.0] for i, la, lo in nodes],
        [{"id": -101, "refs": [-1, -2, -3, -4, -1], "tags": {"role": "apron", "shapeID": "7"}},
         {"id": -102, "refs": [-5, -6, -7, -8, -5], "tags": gap},
         {"id": -103, "refs": [-9, -10, -11, -9], "tags": {"role": "building"}}])


# ─── surfaces and triangles ────────────────────────────────────────────────

def test_the_l2_face_triangulates_to_its_area_with_its_hole():
    with open(FACE, encoding="utf-8") as f:
        reply = json.load(f)
    doc = PE.PatchDoc.from_wire(reply["nodes"], reply["ways"])
    frame = SHP.LocalFrame.of(doc)
    shapes = SHP.assemble(doc, frame)
    assert len(shapes) == 1 and len(shapes[0].holes) == 1      # the gap ring is no surface
    shape = shapes[0]
    x, y = frame.metres([n[1] for n in doc.nodes.values()], [n[2] for n in doc.nodes.values()])
    xy = dict(zip(doc.nodes, zip(x, y)))
    mesh = SHP.ShapeMesh.of(shape, doc, frame)
    tris = [tuple(mesh.vertex_ids[i] for i in t) for t in mesh.indices.reshape(-1, 3)]
    areas = [_signed(xy, t) for t in tris]
    assert min(areas) >= 0                                       # counter-clockwise from above
    want = _ring_area([xy[i] for i in shape.outer]) - _ring_area([xy[i] for i in shape.holes[0]])
    assert sum(areas) == pytest.approx(want, rel=1e-6)
    assert set(mesh.vertex_ids) <= shape.node_ids               # corners are the shape's nodes


@pytest.mark.parametrize("shape_id", ["7", None])
def test_a_gap_ring_and_a_nested_face_are_holes_of_the_face_that_holds_them(shape_id):
    shapes = SHP.assemble(_nested(shape_id))
    assert [s.way_id for s in shapes] == [-101, -103]
    assert shapes[0].holes == ((-5, -6, -7, -8), (-9, -10, -11))
    assert shapes[1].holes == ()


def test_a_face_inside_its_parents_gap_is_not_a_second_hole():
    doc = _nested("7")
    # move the building face (-103) inside the gap ring (-102)
    for nid, (la, lo) in {-9: (45.0025, -122.9975), -10: (45.0025, -122.9965),
                          -11: (45.0035, -122.9965)}.items():
        doc = PE.set_position(doc, nid, la, lo)
    assert SHP.assemble(doc)[0].holes == ((-5, -6, -7, -8),)


def test_a_concave_face_is_covered_exactly():
    # a comb (three teeth north): the retired centroid-kept Delaunay would
    # bridge the gaps between the teeth (issue #752)
    comb = [(0, 0), (50, 0), (50, 30), (40, 30), (40, 10), (30, 10), (30, 30), (20, 30),
            (20, 10), (10, 10), (10, 30), (0, 30)]
    xy = {i + 1: p for i, p in enumerate(comb)}
    tris = SHP.triangulate(xy, list(xy))
    assert len(tris) == len(comb) - 2
    assert sum(abs(_signed(xy, t)) for t in tris) == pytest.approx(_ring_area(comb))


# ─── the terrain cut-out ───────────────────────────────────────────────────

def _even_odd(pts, p):
    inside = False
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        if (ay > p[1]) != (by > p[1]) and p[0] < (bx - ax) * (p[1] - ay) / (by - ay) + ax:
            inside = not inside
    return inside


def test_the_cut_out_drops_exactly_the_triangles_whose_centroid_is_in_a_face():
    doc = _nested("7")
    shapes = SHP.assemble(doc)
    grid = TER.TerrainGrid(60, 70, 44.999, -123.001, 0.0002, 0.0002)
    covered = TER.covered_triangles(grid, shapes, doc.nodes)
    assert covered.size == grid.triangle_count
    dropped = in_gap = 0
    for t in range(grid.triangle_count):
        lat, lon = grid.centroid(t)
        inside = any(sum(_even_odd([(doc.nodes[i][2], doc.nodes[i][1]) for i in ring], (lon, lat))
                         for ring in (s.outer, *s.holes)) % 2 for s in shapes)
        assert covered[t] == inside, t
        dropped += inside
        if _even_odd([(doc.nodes[i][2], doc.nodes[i][1]) for i in (-5, -6, -7, -8)], (lon, lat)):
            in_gap += 1
            assert not covered[t]
    assert dropped and in_gap
    assert len(TER.kept_indices(grid, covered)) == 3 * (grid.triangle_count - dropped)


def test_grid_triangles_are_counter_clockwise():
    grid = TER.TerrainGrid(3, 4, 0, 0, 1, 1)
    xy = {v: (v % 4, v // 4) for v in range(12)}
    tris = grid.triangles()
    assert len(tris) == grid.triangle_count == 12
    assert all(_signed(xy, t) == 0.5 for t in tris)


# ─── the seat transform ────────────────────────────────────────────────────

def test_a_building_sits_on_the_surface_turned_by_its_heading():
    frame = SHP.LocalFrame(30.0, 31.0)
    space = TER.PreviewSpace(frame, base=90.0)
    pose = BLD.Pose.seat(30.0, 31.0, 90.0, 2.0, 100.0, space)
    assert (pose.x, pose.y, pose.z) == pytest.approx((0, 12, 0), abs=1e-4)   # 100 + 2 − 90
    # heading 90: the model's nose (authored −z, north) points east
    assert pose.place((0, 0, -10)) == pytest.approx((10, 12, 0), abs=1e-6)
    # the exaggeration lifts the seat only: the roof stays 5 m above it
    assert pose.place((0, 5, 0), exaggeration=3.0)[1] == pytest.approx(12 * 3 + 5)
    row = BLD.instance_table([pose], 3.0)[0]
    m = np.array([row[0:4], row[4:8], row[8:12]])
    assert m @ np.array([3.0, 5.0, -10.0, 1.0]) == pytest.approx(pose.place((3, 5, -10), 3.0), abs=1e-4)


# ─── live: a change re-meshes only the touched shapes ─────────────────────

class _SyncEngine:
    """The engine door, run in-line: terrain, pack objects and work."""

    def __init__(self, sample, objects):
        self.sample, self.objects = sample, objects
        self.calls = []

    def has(self, name):
        return True

    def call(self, name, callback, **kw):
        self.calls.append(name)
        if name == "terrain_sample":
            callback(self.sample, None)
        else:
            callback(None, "no %s here" % name)

    def run(self, work, callback):
        try:
            result, error = work(), None
        except Exception as exc:          # pragma: no cover — shown in the assert
            result, error = None, repr(exc)
        assert error is None, error
        callback(result, error)

    def pack_objects(self, tile, icao, bbox, callback):
        self.calls.append("pack_objects")
        callback(self.objects, None)


class _RecordingScene:
    """Records what the model sends; draws nothing."""

    def __init__(self):
        self.shape_sets, self.table_sets, self.extent = [], [], None
        self.terrain = None

    def __getattr__(self, name):              # every other setter: accepted
        return lambda *a, **k: None

    def set_shape(self, way, positions, normals, texcoords, indices):
        self.shape_sets.append((way, positions.copy()))

    def set_terrain(self, *args, extent):
        self.terrain = args

    def set_buildings(self, models, facades):
        self.tables = [t.copy() for _p, _n, t in models]

    def set_building_tables(self, tables):
        self.table_sets.append(dict(tables))


def _box_model():
    v = np.array([[0, 0, 0], [4, 0, 0], [4, 0, 4], [0, 0, 4], [0, 6, 0], [4, 6, 0]], dtype="<f4")
    t = np.array([[0, 1, 2], [0, 2, 3], [0, 1, 5], [0, 5, 4]], dtype="<u4")
    return {"key": "box", "vertices_f32_b64": base64.b64encode(v.tobytes()).decode(),
            "triangles_u32_b64": base64.b64encode(t.tobytes()).decode()}


def _two_faces():
    """Two separate 0.001° square faces west (-201) and east (-202), alt 100."""
    nodes, n = [], 0
    for k, lon0 in enumerate((31.400, 31.403)):
        for la, lo in ((30.1, lon0), (30.1, lon0 + 0.001), (30.101, lon0 + 0.001), (30.101, lon0)):
            n -= 1
            nodes.append([n, la, lo, 100.0])
    ways = [{"id": -201, "refs": [-1, -2, -3, -4, -1], "tags": {"role": "apron"}},
            {"id": -202, "refs": [-5, -6, -7, -8, -5], "tags": {"role": "apron"}}]
    return PE.PatchDoc.from_wire(nodes, ways)


def _sample(box):
    rows, cols = 8, 8
    z = np.full(rows * cols, 95.0, dtype="<f4")
    return {"bbox": box, "rows": rows, "cols": cols, "spacing_m": 5.0,
            "dlat": (box[2] - box[0]) / (rows - 1), "dlon": (box[3] - box[1]) / (cols - 1),
            "elev_f32_b64": base64.b64encode(z.tobytes()).decode(),
            "sources": {"base": "x.hgt", "inset": None}}


def test_an_edit_remeshes_and_reseats_only_the_touched_shape(qapp):
    doc = _two_faces()
    box, _spacing = TER.terrain_request(doc.nodes.values())
    objects = {"models": [_box_model()], "facades": [], "missing": [],
               "placements": [{"model": "box", "lat": 30.1005, "lon": 31.4005, "heading_deg": 0,
                               "agl_m": 0},
                              {"model": "box", "lat": 30.1002, "lon": 31.4038, "heading_deg": 0,
                               "agl_m": 0}]}
    engine, scene, patch = _SyncEngine(_sample(box), objects), _RecordingScene(), PatchEditModel()
    preview = PreviewModel(engine, patch, scene)
    preview.set_active(True)
    patch.load(LoadedPatch(tile="+30+031", icao="ZZZZ", source="auto", path="/x", header={}), doc)
    assert preview.status == "ready" and preview.icao == "ZZZZ"
    assert {w for w, _p in scene.shape_sets} == {-201, -202}
    assert preview.buildings_status == "ready" and preview.buildings_count == 2
    seat_east = scene.tables[0][1][7]                            # y of the east building
    assert seat_east == pytest.approx((100.0 - 95.0) * 3)       # on the patch (base = DEM min), ×3
    assert preview.chip == "Preview · 1.4 km × 1.1 km · DEM base only · 5 m grid"

    scene.shape_sets.clear()
    patch.set_selection([-6])
    patch.offset_selection_alt(-3.0)                             # a node of the EAST face only
    assert [w for w, _p in scene.shape_sets] == [-202]
    assert scene.table_sets and all(set(t) == {0} for t in scene.table_sets)
    assert preview._seats.poses[0].y == pytest.approx(5.0)      # the west building did not move
    assert preview._seats.poses[1].y < 5.0                      # the east one followed its ground
    assert "mesh_crop" not in engine.calls                       # Last build is never live

    scene.shape_sets.clear()
    patch.set_selection([-5])
    patch.delete_selection()                                     # topology: east face re-triangulated
    assert [w for w, _p in scene.shape_sets] == [-202]


# ─── the drape and "Last build" ────────────────────────────────────────────

def test_the_drape_plan_fits_4096_px_and_covers_the_box(tmp_path, qapp):
    box = (30.08, 31.37, 30.14, 31.45)                           # ~7.7 × 6.7 km
    plan = DRP.DrapePlan.plan(box, max_zoom=19)
    assert plan.width <= 4096 and plan.height <= 4096
    assert DRP.DrapePlan.plan(box, max_zoom=plan.zoom + 1).zoom == plan.zoom + 1 or \
        max(DRP.DrapePlan._pixels(box, plan.zoom + 1)) > 4096
    x0, y0, _w, _h = plan.rect(*plan.tiles[0])
    assert -256 < x0 <= 0 and -256 < y0 <= 0                     # the NW tile overhangs the box
    xr, yb, w, h = plan.rect(*plan.tiles[-1])
    assert xr + w >= plan.width and yb + h >= plan.height        # the SE tile reaches the corner
    corners = DRP.uv([box[2], box[0]], [box[1], box[3]], box)
    assert corners == pytest.approx(np.array([[0, 0], [1, 1]]), abs=1e-9)
    folder = tmp_path / "OSM" / str(plan.zoom)
    folder.mkdir(parents=True)
    tile = QImage(256, 256, QImage.Format_RGB32)
    tile.fill(QColor("red"))
    tx, ty = plan.tiles[len(plan.tiles) // 2]
    tile.save(str(folder / ("%d_%d.jpg" % (tx, ty))))
    image, found = DRP.compose_drape(plan, str(tmp_path), "OSM", QColor("green"))
    assert found == 1 and (image.width(), image.height()) == (plan.width, plan.height)
    x, y, _w, _h = plan.rect(tx, ty)
    assert image.pixelColor(int(x) + 128, int(y) + 128).red() > 200   # the cached tile
    assert image.pixelColor(2, 2).green() > 100                      # a missing one: terrain colour


def test_last_build_is_fetched_once_per_build_and_never_live():
    s = DRP.LastBuildState()
    assert s.select(DRP.LAST_BUILD, build=1.0)                   # first showing: fetch
    s.fetching(1.0)
    assert not s.select(DRP.LAST_BUILD, build=1.0)               # already loading
    s.fetched(True)
    assert s.showing_mesh and not s.select(DRP.LAST_BUILD, build=1.0)
    assert not s.select(DRP.PREVIEW, build=1.0) and not s.showing_mesh
    assert not s.tile_built(2.0)                                 # rebuilt while in Preview: later
    assert s.select(DRP.LAST_BUILD, build=2.0)                   # … on the next showing
    s.fetching(2.0)
    s.fetched(False, "Set the cleanup level to 2 or lower")
    assert s.mode == DRP.PREVIEW and not s.can_show_last_build
    assert not s.select(DRP.LAST_BUILD, build=2.0) and s.mode == DRP.PREVIEW


# ─── one pack_objects request per box ──────────────────────────────────────

def test_the_outlines_and_the_preview_share_one_pack_objects_request(qapp):
    from o4_engine import events as EV
    engine = PatchEngine(object(), run_async=False)
    asked = []
    engine._handlers = {"pack_objects": lambda **kw: asked.append(kw) or {"status": "started"}}
    got = []
    box = [30.0, 31.0, 30.1, 31.1]
    engine.pack_objects("+30+031", "ZZZZ", box, lambda r, e: got.append(("outlines", r, e)))
    engine.pack_objects("+30+031", "ZZZZ", box, lambda r, e: got.append(("preview", r, e)))
    assert len(asked) == 1
    engine.on_pack_objects_ready(EV.PackObjectsReady(request=asked[0]["request"], result={"m": 1}))
    assert got == [("outlines", {"m": 1}, None), ("preview", {"m": 1}, None)]
    engine.pack_objects("+30+031", "ZZZZ", box, lambda r, e: got.append(("again", r, e)))
    assert len(asked) == 1 and got[-1] == ("again", {"m": 1}, None)


# ─── the window ────────────────────────────────────────────────────────────

def test_the_window_speaks_the_mac_words(qapp):
    from O4_Qt_Preview3D_Window import LEGEND, PreviewWindow
    doc = _two_faces()
    box, _spacing = TER.terrain_request(doc.nodes.values())
    engine = _SyncEngine(_sample(box), {"models": [], "placements": [], "facades": [],
                                        "missing": []})
    patch = PatchEditModel()
    window = PreviewWindow(engine, patch)
    assert window.qml_errors == [] and window.view.rootObject() is not None
    window.show()
    assert window.windowTitle() == "3D Preview"
    assert window.status_label.text() == ("Zoom the map in on a built airport to preview its "
                                          "patch in 3D.")
    patch.load(LoadedPatch(tile="+30+031", icao="ZZZZ", source="auto", path="/x", header={}), doc)
    assert window.windowTitle() == "3D Preview · ZZZZ"
    assert window.chip_text().startswith("Preview · 1.4 km × 1.1 km · DEM base only · 5 m grid")
    assert [t for _c, t in LEGEND] == ["DEM terrain", "patch surface", "pack buildings",
                                       "selected node"]
    assert [b.text() for b in window.mode_buttons.values()] == ["Preview", "Last build"]
    window.exaggeration_slider.setValue(55)
    assert window.model.exaggeration == 5.5 and window.exaggeration_label.text() == "5.5"
    window.model.select_mode(DRP.LAST_BUILD)                     # this engine has no mesh
    assert not window.mode_buttons[DRP.LAST_BUILD].isEnabled()
    window.close()
    assert not math.isnan(window.scene.orbit.distance)
