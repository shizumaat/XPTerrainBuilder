"""WHERE A PACK'S TERRAIN OBJECTS STAND, FOR THE INSET BOX (issue #2272).

Owner (2026-11-24T15:19Z): "if we have high enough quality elevation
data ... compare to the shell objects and if we are close we do not need
the shell".  The hide offer (``terrain_model.quality``) needs quality
elevation UNDER each terrain object, but the airport inset box
(``O4_Airport_Elevation_Insets._airport_bounding_boxes``) reaches only the
aerodrome boundary plus the graded reach: a pack's rocks, cliffs and
islets past it are read on the 30-90 m base DEM and never offered.

THE RULE: the inset box of an airport is the union of its aerodrome box
and the PLAN BOX of every terrain object a pack places near it -- each
object that passes one of the family's DEM-free candidate tests
(``terrain_model.shape_of`` with its small shells, ``ground_shell.shape_of``,
``relief_skin.shape_of``), its covered plan cells turned by the
placement's heading (``terrain_model._world``), grown by the inset
feather and the fetch pad.

THE NEAR ROWS (:func:`nearby`, before any OBJ8 is read): a placement
whose origin stands ON an aerodrome box is not asked -- the inset box
already reaches the fetch margin (graded reach + feather + pad, about
465 m) past it, so only an object over twice that across could poke out,
and a pack's hill-scale terrain stands off its aerodrome; nor is one whose
origin stands more than :data:`MAX_GAP_M` from every aerodrome box.  It
keeps the fetch step from parsing a large pack's every building (ORBX
KATL: 2,985 definitions, ~30 s cold).  What is asked is kept between
builds by the caller, per file version, as :func:`outline`'s plain list
under :func:`gates_key` (a 200 MB grandstand beside KHMP costs 13 s to
ask once, nothing after).

THE CAP (:func:`admit`): an object is left out, and named, when it
stands more than :data:`MAX_GAP_M` from the aerodrome box, when its plan
box is larger than :data:`MAX_PLAN_AREA_M2` (a whole-island model is the
base DEM's job, not an airport inset's), or when it lies wholly off the
tile; an admitted box is clipped to the tile.  No object admitted: the
box comes back unchanged, so the request is byte-identical.

DEM-free and network-free: the placements and the files are the caller's
(the pack's pristine tile DSF, pack-local resources only).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

__all__ = ["MAX_PLAN_AREA_M2", "MAX_GAP_M", "ModelBox", "nearby", "outline",
           "gates_key", "plan_boxes", "nearest", "admit"]

#: the largest plan box an airport inset grows for (10 km^2)
MAX_PLAN_AREA_M2 = 10.0e6
#: the farthest an admitted object may stand from the aerodrome box (m)
MAX_GAP_M = 5000.0

_M_PER_DEG_LAT = 111_320.0
#: bumped when :func:`outline` changes what it returns
_SCHEMA = 1


@_dc.dataclass(frozen=True)
class ModelBox:
    """One placement of a terrain object: its resource, origin and plan
    box ``(west, south, east, north)`` in degrees, and the box's area."""

    resource: str
    lon: float
    lat: float
    box: tuple[float, float, float, float]
    area_m2: float


def nearby(placements: _t.Iterable[tuple], aerodromes: _t.Iterable[tuple]) -> list[tuple]:
    """THE NEAR ROWS (module doc) among ``(def path, lon, lat, heading)``
    placements, for aerodrome boxes ``(west, south, east, north)``."""
    boxes = list(aerodromes)
    out = []
    for row in placements:
        pt = (float(row[1]), float(row[2])) * 2
        gaps = [_gap_m(pt, b, pt[1]) for b in boxes]
        if gaps and 0.0 < min(gaps) <= MAX_GAP_M:
            out.append(row)
    return out


def nearest(model: ModelBox, aerodromes: _t.Mapping[str, tuple]) -> "str | None":
    """The airport whose aerodrome box stands nearest ``model``'s plan."""
    if not aerodromes:
        return None
    return min(aerodromes, key=lambda k: (_gap_m(model.box, aerodromes[k], model.lat), k))


def _shape(path: str) -> _t.Any:
    """The family's candidate shape of an OBJ8 file, or ``None`` (one
    parse, every test reads it)."""
    from . import ground_shell as _gs
    from . import relief_skin as _rs
    from . import terrain_model as _tm
    from .obj8 import parse_obj8
    try:
        g = parse_obj8(path)
    except (OSError, ValueError):
        return None
    for test in (_tm.shape_of, _gs.shape_of, _rs.shape_of):
        shape = test(path, g)
        if shape is not None:
            return shape
    return None


def outline(path: str) -> "list[list[float]] | None":
    """The plan OUTLINE of an OBJ8 file when it is a terrain object: the
    convex hull of its covered plan cells in its own frame (``x``, ``z``
    in metres; ``terrain_model._world`` turns it), else ``None``.  A
    plain list, so the caller can keep it between builds
    (:func:`gates_key`)."""
    shape = _shape(path)
    if shape is None or not shape.grid.covered.any():
        return None
    from ..geom.terrain_deck import CELL_M
    ii, jj = np.nonzero(shape.grid.covered)
    pts = np.column_stack([shape.grid.x0 + CELL_M * ii, shape.grid.z0 + CELL_M * jj])
    pts = np.unique(pts, axis=0)
    if len(pts) >= 3:
        from scipy.spatial import ConvexHull, QhullError
        try:
            pts = pts[ConvexHull(pts).vertices]
        except QhullError:                  # collinear cells: keep them all
            pass
    return [[round(float(x), 3), round(float(z), 3)] for x, z in pts]


def gates_key() -> str:
    """The digest of every numeric gate of the family's candidate tests:
    a kept :func:`outline` is read again only under the same gates."""
    import hashlib

    from . import (
        ground_shell,
        relief_skin,
        rock_witness,
        terrain_model,
        terrain_rock,
        terrain_shell,
    )
    rows = sorted((m.__name__.rsplit(".", 1)[-1], k, repr(v))
                  for m in (terrain_model, terrain_shell, terrain_rock, rock_witness,
                            ground_shell, relief_skin)
                  for k, v in vars(m).items()
                  if k.isupper() and isinstance(v, (int, float)) and not isinstance(v, bool))
    return hashlib.sha1(repr((_SCHEMA, rows)).encode()).hexdigest()[:16]


def _plan_box(points: _t.Sequence, lon: float, lat: float, heading: float
              ) -> tuple[tuple[float, float, float, float], float]:
    """A placement's plan box in degrees and its area in m^2 (``points``:
    an :func:`outline`, turned as ``terrain_model._world`` turns a cell)."""
    from ..geom.terrain_deck import CELL_M
    p = np.asarray(points, dtype=float)
    h = math.radians(heading)
    sn, c = math.sin(h), math.cos(h)
    xs, ys = p[:, 0] * c - p[:, 1] * sn, -(p[:, 0] * sn + p[:, 1] * c)
    w, e = float(xs.min()) - CELL_M, float(xs.max()) + CELL_M
    s, n = float(ys.min()) - CELL_M, float(ys.max()) + CELL_M
    m_lon = _M_PER_DEG_LAT * math.cos(math.radians(lat))
    return ((lon + w / m_lon, lat + s / _M_PER_DEG_LAT,
             lon + e / m_lon, lat + n / _M_PER_DEG_LAT), (e - w) * (n - s))


def plan_boxes(placements: _t.Iterable[tuple[str, float, float, float]],
               path_of: _t.Callable[[str], "str | None"],
               outline_of: "_t.Callable[[str], _t.Any] | None" = None) -> list[ModelBox]:
    """The terrain objects among ``placements`` -- ``(def path, lon, lat,
    heading)`` rows (``dsf_reader._read_dsf_object_placements``) -- each
    with its plan box.  ``path_of(def path)`` is the pack-local file or
    ``None`` (a library object is never a pack's terrain);
    ``outline_of(file)`` is :func:`outline` or the caller's kept copy."""
    from .obj8 import is_stock_library_resource
    outline_of = outline_of or outline
    outlines: dict[str, _t.Any] = {}
    out = []
    for dpath, lon, lat, heading in placements:
        if dpath not in outlines:
            phys = None if is_stock_library_resource(dpath) else path_of(dpath)
            outlines[dpath] = None if phys is None else outline_of(phys)
        points = outlines[dpath]
        if not points:
            continue
        box, area = _plan_box(points, float(lon), float(lat), float(heading))
        out.append(ModelBox(str(dpath), float(lon), float(lat), box, area))
    return out


def _gap_m(a: tuple, b: tuple, lat: float) -> float:
    """The distance between two degree boxes, in metres."""
    m_lon = _M_PER_DEG_LAT * math.cos(math.radians(lat))
    dx = max(a[0] - b[2], b[0] - a[2], 0.0) * m_lon
    dy = max(a[1] - b[3], b[1] - a[3], 0.0) * _M_PER_DEG_LAT
    return math.hypot(dx, dy)


def admit(models: _t.Iterable[ModelBox], aerodrome: tuple, box: tuple, tile: tuple,
          pad_m: float) -> tuple[tuple, list[ModelBox], list[tuple[ModelBox, str]]]:
    """THE CAP (module doc).  ``aerodrome``: the aerodrome boundary's box,
    ``box``: the airport's inset box, ``tile``: the tile's box (all in
    degrees, ``(west, south, east, north)``), ``pad_m``: the margin each
    admitted plan box grows by.  Returns ``(box, admitted, [(left out,
    why)])``; ``box`` is the argument itself when nothing is admitted."""
    lat = 0.5 * (aerodrome[1] + aerodrome[3])
    m_lon = _M_PER_DEG_LAT * math.cos(math.radians(lat))
    pad = (pad_m / m_lon, pad_m / _M_PER_DEG_LAT)
    out, admitted, left = box, [], []
    for m in models:
        gap = _gap_m(m.box, aerodrome, lat)
        if gap > MAX_GAP_M:
            left.append((m, "%.0f m from the aerodrome" % gap))
            continue
        if m.area_m2 > MAX_PLAN_AREA_M2:
            left.append((m, "plan box %.1f km2" % (m.area_m2 / 1e6)))
            continue
        grown = (max(m.box[0] - pad[0], tile[0]), max(m.box[1] - pad[1], tile[1]),
                 min(m.box[2] + pad[0], tile[2]), min(m.box[3] + pad[1], tile[3]))
        if grown[0] >= grown[2] or grown[1] >= grown[3]:
            left.append((m, "off the tile"))
            continue
        admitted.append(m)
        out = (min(out[0], grown[0]), min(out[1], grown[1]),
               max(out[2], grown[2]), max(out[3], grown[3]))
    return out, admitted, left
