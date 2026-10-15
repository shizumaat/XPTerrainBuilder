"""The 3D preview's Qt Quick 3D scene (spec patch-editor-20261015 §5, §6
amended before L7; the Mac app's ``TerrainPreviewScene``).

PySide6's own Qt Quick 3D, no new dependency: procedural
``QQuick3DGeometry`` buffers fed from numpy, one ``QQuick3DInstancing``
table per pack model (one shared geometry, one instance per placement), a
``QQuick3DTextureData`` drape.  The QML scene is a fixed graph whose
properties bind to :class:`PreviewScene`; it holds no document state —
``O4_Qt_Preview3D_Model`` feeds it.

Vertical exaggeration is the y scale of the ``world`` node (terrain, patch
and last-build mesh), so changing it rebuilds nothing there; buildings live
outside it — their instance rows lift the seat only — and so do the
selection markers, so they stay round.

The camera is an orbit (:class:`Orbit`, pure maths): drag orbits, the wheel
zooms, Alt-drag (or the right / middle button) pans; "Reset view" frames
the extent again from the south.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from PySide6.QtCore import Property, QByteArray, QObject, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QVector3D
from PySide6.QtQuick3D import QQuick3DGeometry, QQuick3DInstancing, QQuick3DTextureData

__all__ = ["TERRAIN_COLOR", "PATCH_COLOR", "BUILDING_COLOR", "MARKER_COLOR", "BACKGROUND",
           "MeshGeometry", "PoseInstancing", "Orbit", "KEYS", "SPEED", "PreviewScene", "SCENE_QML"]

TERRAIN_COLOR = QColor(0x7a, 0x8a, 0x6a)
PATCH_COLOR = QColor(0xd6, 0xda, 0xe2)
BUILDING_COLOR = QColor(0xb9, 0xbe, 0xc8)
MARKER_COLOR = QColor(0xff, 0xd6, 0x0a)          # #FFD60A
BACKGROUND = QColor(0x0b, 0x0d, 0x12)
#: The marker sphere's radius in metres (the built-in #Sphere is 100 across).
MARKER_RADIUS_M = 1.8

_ATTR = QQuick3DGeometry.Attribute


class MeshGeometry(QQuick3DGeometry):
    """One indexed triangle buffer: positions, normals and (optionally)
    drape texture coordinates, interleaved."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Triangles)
        self.vertex_count = 0
        self.index_count = 0

    def set_mesh(self, positions: np.ndarray, normals: np.ndarray,
                 texcoords: np.ndarray | None = None, indices: np.ndarray | None = None) -> None:
        """Replace the buffers; ``indices`` None draws the vertices in order."""
        n = len(positions)
        uv = texcoords if texcoords is not None and len(texcoords) == n else np.zeros((n, 2))
        data = np.empty((n, 8), dtype="<f4")
        data[:, 0:3], data[:, 3:6], data[:, 6:8] = positions, normals, uv
        self.clear()
        self.setStride(32)
        self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Triangles)
        self.addAttribute(_ATTR.Semantic.PositionSemantic, 0, _ATTR.ComponentType.F32Type)
        self.addAttribute(_ATTR.Semantic.NormalSemantic, 12, _ATTR.ComponentType.F32Type)
        self.addAttribute(_ATTR.Semantic.TexCoord0Semantic, 24, _ATTR.ComponentType.F32Type)
        self.setVertexData(QByteArray(data.tobytes()))
        self.vertex_count = n
        if indices is not None:
            idx = np.ascontiguousarray(indices, dtype="<u4")
            self.addAttribute(_ATTR.Semantic.IndexSemantic, 0, _ATTR.ComponentType.U32Type)
            self.setIndexData(QByteArray(idx.tobytes()))
            self.index_count = len(idx)
        else:
            self.index_count = 0
        if n:
            lo, hi = positions.min(axis=0), positions.max(axis=0)
            self.setBounds(QVector3D(*map(float, lo)), QVector3D(*map(float, hi)))
        self.update()

    def set_indices(self, indices: np.ndarray) -> None:
        """The terrain's cut-out changed: swap the index buffer only."""
        idx = np.ascontiguousarray(indices, dtype="<u4")
        self.setIndexData(QByteArray(idx.tobytes()))
        self.index_count = len(idx)
        self.update()


class PoseInstancing(QQuick3DInstancing):
    """An instance table held as numpy rows (20 float32 each)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._table = np.zeros((0, 20), dtype="<f4")

    def set_table(self, table: np.ndarray) -> None:
        self._table = np.ascontiguousarray(table, dtype="<f4")
        self.markDirty()

    @property
    def count(self) -> int:
        return len(self._table)

    def getInstanceBuffer(self, *_args):          # noqa: N802 (Qt override)
        return QByteArray(self._table.tobytes()), len(self._table)


#: X-Plane's view commands as its default ``X-Plane Keys.prf`` binds them
#: (the Mac's ``OrbitCamera.Key``): ← → sideways, ↑ ↓ up/down, ``.`` ``,``
#: forward/back, ``=`` ``-`` zoom, Q E rotate, R F tilt.
KEYS = ("left", "right", "up", "down", "forward", "backward",
        "zoom_in", "zoom_out", "rotate_left", "rotate_right", "tilt_up", "tilt_down")
#: Plain is slow, Shift fast, Control slower (X-Plane's _fast / _slow).
SPEED = {"slow": 0.25, "normal": 1.0, "fast": 4.0}


@_dc.dataclass
class Orbit:
    """The orbit camera: a target on the ground, a distance, a yaw (0 =
    looking north from the south) and a pitch above the horizon.

    Input moves these GOAL values; :meth:`step` eases the SHOWN camera
    toward them, so neither a jerky mouse nor a held key makes the view
    jump (owner 2026-10-15: "too jumpy with the mouse"). Same rates as the
    Mac's ``OrbitCamera``."""

    target: tuple[float, float, float] = (0.0, 0.0, 0.0)
    distance: float = 2000.0
    yaw_deg: float = 0.0
    pitch_deg: float = 35.0
    shown: tuple | None = None          # (target, distance, yaw, pitch) on screen

    MIN_PITCH: _t.ClassVar[float] = 3.0
    MAX_PITCH: _t.ClassVar[float] = 89.0
    DRAG_DEG_PER_PX: _t.ClassVar[float] = 0.17       # ≈ 0.003 rad, the Mac's
    ZOOM_PER_NOTCH: _t.ClassVar[float] = 0.96
    PAN_PER_PX: _t.ClassVar[float] = 1.2              # × distance / view height
    KEY_ROTATE_DEG: _t.ClassVar[float] = 20.0         # per second, normal speed
    KEY_TILT_DEG: _t.ClassVar[float] = 15.0
    KEY_MOVE_FRACTION: _t.ClassVar[float] = 0.25      # of the distance per second
    KEY_ZOOM_PER_S: _t.ClassVar[float] = 1.6
    EASING: _t.ClassVar[float] = 0.25                 # of the way per 1/60 s

    def _goal(self) -> tuple:
        return (tuple(self.target), self.distance, self.yaw_deg, self.pitch_deg)

    def _view(self) -> tuple:
        return self.shown if self.shown is not None else self._goal()

    def frame(self, centre: _t.Sequence[float], radius: float) -> None:
        """Frame the extent from the south ("Reset view"), at once."""
        self.target = tuple(float(v) for v in centre)
        self.distance = max(radius, 50.0) * 2.2
        self.yaw_deg, self.pitch_deg = 0.0, 35.0
        self.shown = self._goal()

    def position(self) -> tuple[float, float, float]:
        (tx, ty, tz), d, yaw, pitch = self._view()
        p, y = math.radians(pitch), math.radians(yaw)
        return (tx + d * math.cos(p) * math.sin(y), ty + d * math.sin(p),
                tz + d * math.cos(p) * math.cos(y))

    def rotation(self) -> tuple[float, float, float]:
        """Euler degrees: the camera (looking down −z) turned to the target."""
        _t3, _d, yaw, pitch = self._view()
        return (-pitch, yaw, 0.0)

    def view_distance(self) -> float:
        return self._view()[1]

    # ─── input (moves the goal) ─────────────────────────────────────────
    def orbit(self, dx_px: float, dy_px: float) -> None:
        self.yaw_deg -= dx_px * self.DRAG_DEG_PER_PX      # unbounded: easing never spins
        self.pitch_deg = min(self.MAX_PITCH, max(self.MIN_PITCH,
                                                 self.pitch_deg + dy_px * self.DRAG_DEG_PER_PX))

    def zoom(self, steps: float) -> None:
        self.distance = min(200_000.0, max(20.0, self.distance * self.ZOOM_PER_NOTCH ** steps))

    def pan(self, dx_px: float, dy_px: float, view_height_px: float) -> None:
        """Move the target in the ground plane, by screen pixels."""
        k = self.distance * self.PAN_PER_PX / max(view_height_px, 1.0)
        self._slide(-dx_px * k, dy_px * k)

    def _slide(self, right_m: float, ahead_m: float, up_m: float = 0.0) -> None:
        y = math.radians(self.yaw_deg)
        right = (math.cos(y), -math.sin(y))
        ahead = (-math.sin(y), -math.cos(y))
        tx, ty, tz = self.target
        self.target = (tx + right_m * right[0] + ahead_m * ahead[0], ty + up_m,
                       tz + right_m * right[1] + ahead_m * ahead[1])

    def hold(self, keys: _t.Collection[str], speed: str, dt: float) -> None:
        """Advance the goal by ``dt`` seconds of the held X-Plane keys."""
        if not keys or dt <= 0:
            return
        m = SPEED[speed] * dt

        def axis(plus: str, minus: str) -> float:
            return float(plus in keys) - float(minus in keys)

        self.yaw_deg += axis("rotate_left", "rotate_right") * self.KEY_ROTATE_DEG * m
        self.pitch_deg = min(self.MAX_PITCH, max(self.MIN_PITCH, self.pitch_deg
                             + axis("tilt_up", "tilt_down") * self.KEY_TILT_DEG * m))
        step = self.distance * self.KEY_MOVE_FRACTION * m
        self._slide(axis("right", "left") * step, axis("forward", "backward") * step,
                    axis("up", "down") * step)
        z = axis("zoom_in", "zoom_out")
        if z:
            self.distance = min(200_000.0, max(20.0, self.distance * self.KEY_ZOOM_PER_S ** (-z * m)))

    # ─── easing ─────────────────────────────────────────────────────────
    def step(self, dt: float) -> bool:
        """Ease the shown camera toward the goal; whether it still moves."""
        goal = self._goal()
        if self.shown is None:
            self.shown = goal
            return False
        a = 1.0 - (1.0 - self.EASING) ** (max(dt, 0.0) * 60.0)
        (sx, sy, sz), sd, syaw, spitch = self.shown
        (gx, gy, gz), gd, gyaw, gpitch = goal
        nd = sd + (gd - sd) * a
        self.shown = ((sx + (gx - sx) * a, sy + (gy - sy) * a, sz + (gz - sz) * a),
                      nd, syaw + (gyaw - syaw) * a, spitch + (gpitch - spitch) * a)
        tol = max(0.001 * nd, 0.01)
        settled = (math.dist(self.shown[0], goal[0]) < tol and abs(gd - nd) < tol
                   and abs(gyaw - self.shown[2]) < 0.005 and abs(gpitch - self.shown[3]) < 0.005)
        if settled:
            self.shown = goal
        return not settled


class PreviewScene(QObject):
    """The QML scene's model: geometries, instance tables, toggles and the
    camera, as notifying properties."""

    changed = Signal()
    shapes_changed = Signal()
    buildings_changed = Signal()
    camera_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.terrain = MeshGeometry()
        self.last_build = MeshGeometry()
        self.facades = MeshGeometry()
        self.markers = PoseInstancing()
        self.drape = QQuick3DTextureData()
        self._shapes: dict[int, MeshGeometry] = {}
        self._shape_list: list = []
        self._batch = 0
        self._shapes_dirty = False
        self._buildings: list = []           # [{"geometry", "instancing"}]
        self._exaggeration = 3.0
        self._wireframe = False
        self._buildings_visible = True
        self._last_build_shown = False
        self._imagery = False
        self.orbit = Orbit()
        self.extent: tuple[tuple[float, float, float], float] = ((0.0, 0.0, 0.0), 1000.0)

    # ─── properties the QML binds to ───────────────────────────────────
    def _get_shapes(self):
        return self._shape_list

    def _get_buildings(self):
        return self._buildings

    terrainGeometry = Property(QObject, lambda self: self.terrain, constant=True)
    lastBuildGeometry = Property(QObject, lambda self: self.last_build, constant=True)
    facadeGeometry = Property(QObject, lambda self: self.facades, constant=True)
    markerInstancing = Property(QObject, lambda self: self.markers, constant=True)
    drapeTexture = Property(QObject, lambda self: self.drape, constant=True)
    shapeGeometries = Property("QVariantList", _get_shapes, notify=shapes_changed)
    buildingModels = Property("QVariantList", _get_buildings, notify=buildings_changed)
    exaggeration = Property(float, lambda self: self._exaggeration, notify=changed)
    wireframe = Property(bool, lambda self: self._wireframe, notify=changed)
    buildingsVisible = Property(bool, lambda self: self._buildings_visible, notify=changed)
    lastBuildShown = Property(bool, lambda self: self._last_build_shown, notify=changed)
    imagery = Property(bool, lambda self: self._imagery, notify=changed)
    cameraPosition = Property(QVector3D, lambda self: QVector3D(*self.orbit.position()),
                              notify=camera_changed)
    cameraRotation = Property(QVector3D, lambda self: QVector3D(*self.orbit.rotation()),
                              notify=camera_changed)
    cameraFar = Property(float, lambda self: max(10_000.0, self.orbit.view_distance() * 6 + self.extent[1] * 4),
                         notify=camera_changed)

    # ─── terrain, patch, last build ────────────────────────────────────
    def set_terrain(self, positions, normals, texcoords, indices,
                    extent: tuple[tuple[float, float, float], float]) -> None:
        self.terrain.set_mesh(positions, normals, texcoords, indices)
        self.extent = extent

    def set_terrain_indices(self, indices) -> None:
        self.terrain.set_indices(indices)

    def begin_shapes(self) -> None:
        """Hold the shape list's announcement (a Repeater3D rebuilds every
        delegate per announcement) until :meth:`end_shapes`."""
        self._batch += 1

    def end_shapes(self) -> None:
        self._batch -= 1
        if self._batch == 0 and self._shapes_dirty:
            self._shapes_dirty = False
            self._shape_list = list(self._shapes.values())
            self.shapes_changed.emit()

    def _shapes_moved(self) -> None:
        self._shapes_dirty = True
        if self._batch == 0:
            self.begin_shapes()
            self.end_shapes()

    def set_shape(self, way: int, positions, normals, texcoords, indices) -> None:
        """One shape's buffer (its triangles re-sent each time: the shape's
        own small index list)."""
        geometry = self._shapes.get(way)
        if geometry is None:
            geometry = self._shapes[way] = MeshGeometry()
            self._shapes_moved()
        geometry.set_mesh(positions, normals, texcoords, indices)

    def remove_shape(self, way: int) -> None:
        geometry = self._shapes.pop(way, None)
        if geometry is not None:
            self._shapes_moved()
            geometry.deleteLater()

    def shape_ids(self) -> set[int]:
        return set(self._shapes)

    def set_last_build(self, positions, normals, texcoords, indices) -> None:
        self.last_build.set_mesh(positions, normals, texcoords, indices)

    def show_last_build(self, on: bool) -> None:
        self._set("_last_build_shown", bool(on))

    def remove_all(self) -> None:
        empty3 = np.zeros((0, 3), np.float32)
        self.terrain.set_mesh(empty3, empty3, None, np.zeros(0, np.uint32))
        self.last_build.set_mesh(empty3, empty3, None, np.zeros(0, np.uint32))
        self.begin_shapes()
        for way in list(self._shapes):
            self.remove_shape(way)
        self.end_shapes()
        self.set_markers(np.zeros((0, 3), np.float32))
        self.set_buildings([], np.zeros((0, 3), np.float32))
        self.show_last_build(False)

    # ─── buildings, markers ────────────────────────────────────────────
    def set_buildings(self, models: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
                      facades: np.ndarray) -> None:
        """``models``: ``(positions, normals, instance table)`` per model."""
        for item in self._buildings:
            item["geometry"].deleteLater()
            item["instancing"].deleteLater()
        self._buildings = []
        for positions, normals, table in models:
            geometry = MeshGeometry()
            geometry.set_mesh(positions, normals)
            instancing = PoseInstancing()
            instancing.set_table(table)
            self._buildings.append({"geometry": geometry, "instancing": instancing})
        self.buildings_changed.emit()
        self.set_facades(facades)

    def set_building_tables(self, tables: _t.Mapping[int, np.ndarray]) -> None:
        """New instance rows for some models (an edit moved their ground)."""
        for i, table in tables.items():
            self._buildings[i]["instancing"].set_table(table)

    def set_facades(self, positions: np.ndarray) -> None:
        from O4_Qt_Preview3D_Terrain import vertex_normals
        self.facades.set_mesh(positions, vertex_normals(positions, np.arange(len(positions))))

    def set_markers(self, points: np.ndarray, exaggeration: float | None = None) -> None:
        """Selected nodes (unexaggerated preview space)."""
        self._marker_points = np.asarray(points, dtype=np.float32).reshape(-1, 3)
        e = self._exaggeration if exaggeration is None else exaggeration
        t = np.zeros((len(self._marker_points), 20), dtype=np.float32)
        s = MARKER_RADIUS_M / 50.0
        t[:, 0], t[:, 5], t[:, 10] = s, s, s
        t[:, 3] = self._marker_points[:, 0]
        t[:, 7] = self._marker_points[:, 1] * e
        t[:, 11] = self._marker_points[:, 2]
        t[:, 12:16] = 1.0
        self.markers.set_table(t)

    # ─── toggles ───────────────────────────────────────────────────────
    def _set(self, attr: str, value) -> None:
        if getattr(self, attr) != value:
            setattr(self, attr, value)
            self.changed.emit()

    def set_exaggeration(self, value: float) -> None:
        self._set("_exaggeration", float(value))
        if hasattr(self, "_marker_points"):
            self.set_markers(self._marker_points)

    def set_wireframe(self, on: bool) -> None:
        self._set("_wireframe", bool(on))

    def set_buildings_visible(self, on: bool) -> None:
        self._set("_buildings_visible", bool(on))

    def set_imagery(self, image) -> None:
        """Drape ``image`` (a QImage, top = north) or nil = own colours."""
        if image is not None and not image.isNull():
            from PySide6.QtGui import QImage
            rgba = image.convertToFormat(QImage.Format_RGBA8888)
            self.drape.setSize(rgba.size())
            self.drape.setFormat(QQuick3DTextureData.Format.RGBA8)
            self.drape.setTextureData(QByteArray(bytes(rgba.constBits())))
            self.drape.update()
        self._set("_imagery", image is not None and not image.isNull())

    # ─── camera ────────────────────────────────────────────────────────
    def reset_view(self) -> None:
        centre, radius = self.extent
        self.orbit.frame(centre, radius)
        self.camera_changed.emit()

    def _wake(self) -> None:
        """Run the 60 Hz ease while a key is held or the camera has not
        reached its goal."""
        from PySide6.QtCore import QElapsedTimer, QTimer
        if getattr(self, "_ticker", None) is None:
            self._ticker = QTimer(self)
            self._ticker.setInterval(16)
            self._ticker.timeout.connect(self._tick)
            self._clock = QElapsedTimer()
        if not self._ticker.isActive():
            self._clock.start()
            self._ticker.start()

    def _tick(self) -> None:
        dt = min(self._clock.restart() / 1000.0, 0.1)
        held = getattr(self, "_held", set())
        self.orbit.hold(held, getattr(self, "_speed", "normal"), dt)
        moving = self.orbit.step(dt)
        self.camera_changed.emit()
        if not moving and not held:
            self._ticker.stop()

    def orbit_by(self, dx: float, dy: float) -> None:
        self.orbit.orbit(dx, dy)
        self._wake()

    def zoom_by(self, steps: float) -> None:
        self.orbit.zoom(steps)
        self._wake()

    def pan_by(self, dx: float, dy: float, height: float) -> None:
        self.orbit.pan(dx, dy, height)
        self._wake()

    def key(self, name: str, down: bool, speed: str) -> None:
        """An X-Plane view key (``KEYS``) pressed or released."""
        held = self.__dict__.setdefault("_held", set())
        self._speed = speed
        if down:
            held.add(name)
            self._wake()
        else:
            held.discard(name)

    def set_speed(self, speed: str) -> None:
        self._speed = speed

    def release_keys(self) -> None:
        self.__dict__.setdefault("_held", set()).clear()

    def handle_mouse(self, kind: str, pos: QPointF, buttons, modifiers, height: float,
                     wheel_degrees: float = 0.0) -> bool:
        """The view's mouse: ``kind`` is "press", "move" or "wheel"."""
        if kind == "wheel":
            self.zoom_by(wheel_degrees / 15.0)
            return True
        if kind == "press":
            self._last = pos
            return True
        last = getattr(self, "_last", None)
        if kind != "move" or last is None or not buttons:
            return False
        dx, dy = pos.x() - last.x(), pos.y() - last.y()
        self._last = pos
        pan = (buttons & (Qt.RightButton | Qt.MiddleButton)) or (modifiers & Qt.AltModifier)
        if pan:
            self.pan_by(dx, dy, height)
        else:
            self.orbit_by(dx, dy)
        return True


#: The fixed scene graph; every live value binds to ``scene3d``.
SCENE_QML = """
import QtQuick
import QtQuick3D

Item {
    View3D {
        anchors.fill: parent
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Color
            clearColor: "%(background)s"
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
            tonemapMode: SceneEnvironment.TonemapModeNone
            debugSettings: DebugSettings { wireframeEnabled: scene3d.wireframe }
        }
        PerspectiveCamera {
            position: scene3d.cameraPosition
            eulerRotation: scene3d.cameraRotation
            clipNear: 2
            clipFar: scene3d.cameraFar
        }
        DirectionalLight {
            eulerRotation: Qt.vector3d(-60, 36, 0)
            brightness: 0.9
            ambientColor: Qt.rgba(0.35, 0.35, 0.35, 1.0)
        }
        Texture { id: drape; textureData: scene3d.drapeTexture }
        DefaultMaterial {
            id: terrainMaterial; cullMode: Material.NoCulling
            diffuseColor: scene3d.imagery ? "white" : "%(terrain)s"
            diffuseMap: scene3d.imagery ? drape : null
        }
        DefaultMaterial {
            id: patchMaterial; cullMode: Material.NoCulling
            diffuseColor: scene3d.imagery ? "white" : "%(patch)s"
            diffuseMap: scene3d.imagery ? drape : null
        }
        DefaultMaterial { id: buildingMaterial; cullMode: Material.NoCulling; diffuseColor: "%(building)s" }
        DefaultMaterial { id: markerMaterial; lighting: DefaultMaterial.NoLighting; diffuseColor: "%(marker)s" }

        Node {
            scale: Qt.vector3d(1, scene3d.exaggeration, 1)
            Node {
                visible: !scene3d.lastBuildShown
                Model { geometry: scene3d.terrainGeometry; materials: [terrainMaterial] }
                Repeater3D {
                    model: scene3d.shapeGeometries
                    Model { geometry: modelData; materials: [patchMaterial] }
                }
            }
            Model {
                visible: scene3d.lastBuildShown
                geometry: scene3d.lastBuildGeometry
                materials: [terrainMaterial]
            }
        }
        Node {
            visible: scene3d.buildingsVisible
            Repeater3D {
                model: scene3d.buildingModels
                Model {
                    geometry: modelData.geometry
                    instancing: modelData.instancing
                    materials: [buildingMaterial]
                }
            }
            Model { geometry: scene3d.facadeGeometry; materials: [buildingMaterial] }
        }
        Model { source: "#Sphere"; instancing: scene3d.markerInstancing; materials: [markerMaterial] }
    }
}
""" % {"background": BACKGROUND.name(), "terrain": TERRAIN_COLOR.name(),
       "patch": PATCH_COLOR.name(), "building": BUILDING_COLOR.name(),
       "marker": MARKER_COLOR.name()}
