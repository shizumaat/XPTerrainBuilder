"""The 3D preview's imagery drape and its "Preview | Last build" state
(spec patch-editor-20261015 §5; the Mac app's ``PatchDrapePlan``,
``TerrainPreviewDrape`` and ``PatchLastBuildState``).

DRAPE: the Qt map's cached imagery tiles — the files its display cache
already holds (``O4_Qt_Map.livemap_cache_dir``), never a download —
composed into ONE texture covering the preview extent, at the finest zoom
whose texture stays within 4,096 px a side.  The texture covers EXACTLY
the extent box in web mercator, so a vertex's texture coordinate depends on
the box alone (:func:`uv`), never on the zoom.  A tile the cache does not
hold is left in the terrain colour.

LAST BUILD: which surface the window shows, and whether the last build's
mesh can be shown; the mesh is fetched once per build (the tile's mesh
date), never live.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np

from O4_Qt_Patch_Geometry import scene_xy

__all__ = ["TILE_SIZE", "MAX_PIXELS", "DrapePlan", "uv", "compose_drape",
           "LastBuildState", "PREVIEW", "LAST_BUILD"]

TILE_SIZE = 256
#: 4,096 px a side keeps the drape near 64 MB of RGBA (a HECA extent: ZL 16).
MAX_PIXELS = 4096


def _tile_xy(lat, lon, z: int):
    """Fractional slippy-tile coordinates at zoom z."""
    x, y = scene_xy(lat, lon, z)
    return x / TILE_SIZE, y / TILE_SIZE


@_dc.dataclass(frozen=True)
class DrapePlan:
    """The texture for ``box`` = ``[min_lat, min_lon, max_lat, max_lon]``."""

    box: tuple[float, float, float, float]
    zoom: int
    width: int
    height: int
    tiles: tuple[tuple[int, int], ...]

    @staticmethod
    def _pixels(box, z: int) -> tuple[float, float]:
        s, w, n, e = box
        x0, y0 = _tile_xy(n, w, z)
        x1, y1 = _tile_xy(s, e, z)
        return float((x1 - x0) * TILE_SIZE), float((y1 - y0) * TILE_SIZE)

    @classmethod
    def plan(cls, box: _t.Sequence[float], max_zoom: int,
             max_pixels: int = MAX_PIXELS) -> "DrapePlan | None":
        """The finest zoom ≤ ``max_zoom`` whose texture fits ``max_pixels``."""
        box = tuple(float(v) for v in box)
        for z in range(min(int(max_zoom), 22), -1, -1):
            w, h = cls._pixels(box, z)
            if w <= max_pixels and h <= max_pixels:
                break
        else:
            return None
        s, wl, n, e = box
        x0, y0 = _tile_xy(n, wl, z)
        x1, y1 = _tile_xy(s, e, z)
        xs = range(int(math.floor(x0)), max(int(math.floor(x0)), int(math.floor(x1 - 1e-9))) + 1)
        ys = range(int(math.floor(y0)), max(int(math.floor(y0)), int(math.floor(y1 - 1e-9))) + 1)
        return cls(box, z, max(1, math.ceil(w)), max(1, math.ceil(h)),
                   tuple((x, y) for y in ys for x in xs))

    def rect(self, x: int, y: int) -> tuple[float, float, float, float]:
        """Where tile (x, y) lands in the texture: ``(left, top, w, h)``
        pixels, origin TOP-LEFT (north-west)."""
        ox, oy = _tile_xy(self.box[2], self.box[1], self.zoom)
        return ((x - float(ox)) * TILE_SIZE, (y - float(oy)) * TILE_SIZE, TILE_SIZE, TILE_SIZE)


def uv(lat, lon, box: _t.Sequence[float]) -> np.ndarray:
    """``(N, 2)`` float32 texture coordinates: u east 0…1, v SOUTH 0…1
    (v = 0 is the box's north edge, the texture's top row)."""
    s, w, n, e = box
    x0, y0 = _tile_xy(n, w, 0)
    x1, y1 = _tile_xy(s, e, 0)
    x, y = _tile_xy(np.atleast_1d(lat), np.atleast_1d(lon), 0)
    return np.column_stack([(x - x0) / (x1 - x0), (y - y0) / (y1 - y0)]).astype(np.float32)


def compose_drape(plan: DrapePlan, cache_dir: str, code: str, fill) -> tuple[_t.Any, int]:
    """The texture (a ``QImage``, RGBA8888) from the map's cached tiles
    ``<cache_dir>/<code>/<z>/<x>_<y>.jpg``, and how many tiles it found.
    Safe off the GUI thread (QImage, QPainter on an image)."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    image = QImage(plan.width, plan.height, QImage.Format_RGBA8888)
    image.fill(fill)
    found = 0
    painter = QPainter(image)
    try:
        for x, y in plan.tiles:
            path = os.path.join(cache_dir, code, str(plan.zoom), "%d_%d.jpg" % (x, y))
            tile = QImage(path) if os.path.isfile(path) else QImage()
            if tile.isNull():
                continue
            painter.drawImage(QRectF(*plan.rect(x, y)), tile)
            found += 1
    finally:
        painter.end()
    return image, found


PREVIEW, LAST_BUILD = "Preview", "Last build"


class LastBuildState:
    """"Preview | Last build": the mode, and what is known of the mesh —
    ``"unknown"``, ``"loading"``, ``"available"`` or ``"unavailable"`` (with
    the engine's sentence)."""

    def __init__(self):
        self.mode = PREVIEW
        self.mesh = "unknown"
        self.reason = ""
        #: The build whose mesh ``mesh`` describes (the tile's mesh date).
        self.mesh_build: float | None = None

    @property
    def can_show_last_build(self) -> bool:
        return self.mesh != "unavailable"

    @property
    def showing_mesh(self) -> bool:
        return self.mode == LAST_BUILD and self.mesh == "available"

    def select(self, mode: str, build: float | None) -> bool:
        """Pick a mode; True when the mesh must be fetched now."""
        if mode != PREVIEW and not self.can_show_last_build:
            return False
        self.mode = mode
        return (mode == LAST_BUILD and (self.mesh == "unknown" or build != self.mesh_build)
                and self.mesh != "loading")

    def tile_built(self, build: float | None) -> bool:
        """The tile was (re)built: a new mesh date forgets the old answer;
        True when Last build is showing and must refetch."""
        if build == self.mesh_build:
            return False
        self.mesh = "unknown"
        return self.mode == LAST_BUILD

    def fetching(self, build: float | None) -> None:
        self.mesh, self.mesh_build = "loading", build

    def fetched(self, ok: bool, reason: str = "") -> None:
        self.mesh, self.reason = ("available", "") if ok else ("unavailable", reason)
        if not ok:
            self.mode = PREVIEW
