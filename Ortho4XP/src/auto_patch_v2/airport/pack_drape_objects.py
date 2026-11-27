"""DRAPED PHOTOS LAID AS OBJECTS (issue #2250): the photo layers of a
pack that lays its orthophotos as draped OBJ8 objects, not ``.pol``s.

FlyTampa's LGKR lays its airport photo as thirteen ``OBJECT_MSL`` rows of
``Corfu_objects/ground/x-obj_groundpoly_<a1..f1>.obj``: each a
``TEXTURE_DRAPED`` image (``lgkr_<a1..f1>.dds``, 1024 px, a photo of the
town and the field) mapped north-up on quads of a 471 m grid, every
triangle under ``ATTR_draped``.  ``pack_drapes`` read ``POLYGON_DEF``
``.pol`` files only, so the photo was never offered for hiding.

THE WITNESS for an ``OBJECT_DEF`` is ``pack_drapes``'s, read from the
OBJ8 (:func:`photo_object`):

1. the PACK'S OWN file (resolved under the pack folder);
2. ALL its geometry DRAPED: a ``TEXTURE_DRAPED`` image, no 3-D
   ``TEXTURE``, and every ``TRIS`` inside ``ATTR_draped`` (a building
   with a draped apron is no photo); no ``ATTR_hard`` (pavement the
   aircraft rolls on, drawn on purpose);
3. image-mapped NORTH-UP: the image's ``u`` axis, placed by the row's
   heading, along the parallels within ``pack_drapes.NORTH_UP_DEG``;
4. over an airport and PHOTO-SIZED (its placed extent at least
   ``pack_drapes.MIN_SPAN_M``) with an image that is not see-through
   (``pack_drapes.MIN_OPAQUE``).

A passing definition is a ``pack_drape_grid.Layer`` like a ``.pol``'s,
keyed :func:`layer_index` (negative: object definitions count apart from
polygon ones), one box per row placing it; the grid rule then decides
(RULINGS 2026-11-07a (3)) and the omission takes ``MissingDef("object",
…)`` (``pack_art.OMITTABLE``).
"""
from __future__ import annotations

import math
import os
import typing as _t

import numpy as np

__all__ = ["ObjPhoto", "photo_object", "layer_index", "def_index", "object_layers"]

Box = tuple[float, float, float, float]          # lon0, lat0, lon1, lat1
_M_PER_DEG_LAT = 110_540.0
_M_PER_DEG_LON = 111_320.0
#: the rows that place an object (token 1 its definition)
_ROWS = ("OBJECT", "OBJECT_AGL", "OBJECT_MSL")


class ObjPhoto(_t.NamedTuple):
    """One draped-photo OBJ8: its image, its vertices ``(x, z, u)`` and
    its draw order (``deck_author_art.layer_order``)."""
    texture: str
    xzu: np.ndarray
    layer: float


def layer_index(i: int) -> int:
    """The ``Layer.index`` of object definition ``i`` (negative)."""
    return -(i + 1)


def def_index(index: int) -> int:
    """The object definition of a negative ``Layer.index``."""
    return -index - 1


def photo_object(path: str) -> ObjPhoto | None:
    """Witness (2) on the OBJ8 at ``path``: its draped image and vertices,
    or ``None`` when it is not a wholly draped, unpaved image."""
    from .deck_author_art import layer_order
    texture, group, draped, flat = "", "", False, True
    xzu: list[tuple[float, float, float]] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                toks = raw.split()
                if not toks:
                    continue
                kw = toks[0]
                if kw == "VT" and len(toks) >= 9:
                    xzu.append((float(toks[1]), float(toks[3]), float(toks[7])))
                elif kw == "TEXTURE_DRAPED" and len(toks) > 1:
                    texture = toks[1]
                elif kw in ("TEXTURE", "ATTR_hard", "ATTR_hard_deck"):
                    return None
                elif kw == "ATTR_layer_group_draped":
                    group = " ".join(toks[1:])
                elif kw == "ATTR_draped":
                    draped = True
                elif kw == "ATTR_no_draped":
                    draped = False
                elif kw == "TRIS":
                    flat = flat and draped
    except (OSError, ValueError):
        return None
    if not (texture and flat and xzu):
        return None
    return ObjPhoto(texture, np.asarray(xzu, float),
                    layer_order({"LAYER_GROUP": group} if group else {}))


def _placed(ph: ObjPhoto, lon: float, lat: float, heading: float
            ) -> tuple[Box, float]:
    """The lon/lat box of the photo placed at a row, and how far its
    image's ``u`` axis turns off the parallels (``pack_drapes._turn_deg``)."""
    from .pack_drapes import _turn_deg
    h = math.radians(heading)
    x, z, u = ph.xzu[:, 0], ph.xzu[:, 1], ph.xzu[:, 2]
    east = x * math.cos(h) - z * math.sin(h)
    north = -(x * math.sin(h) + z * math.cos(h))
    lons = lon + east / (_M_PER_DEG_LON * math.cos(math.radians(lat)))
    lats = lat + north / _M_PER_DEG_LAT
    box = (float(lons.min()), float(lats.min()), float(lons.max()), float(lats.max()))
    return box, _turn_deg(list(zip(lons.tolist(), lats.tolist(), u.tolist(), strict=True)))


def object_layers(pack_root: str, lines: _t.Sequence[str],
                  areas: _t.Sequence[Box]) -> tuple[list, dict[int, int], list[str]]:
    """``(layers, uses, defs)`` of one dump: every object definition
    passing witness (1)-(3) as a ``pack_drape_grid.Layer`` (``witness``
    (4) over ``areas``), the rows placing each (by ``Layer.index``) and
    every ``OBJECT_DEF`` path."""
    from .dsf_rows import placement_rows
    from .image_opacity import image_file, opaque_fraction
    from .obj8 import resolve_resource
    from .pack_drape_grid import Layer
    from .pack_drapes import MIN_OPAQUE, MIN_SPAN_M, NORTH_UP_DEG, _overlaps, _span_m
    defs = [ln.partition(" ")[2].strip() for ln in lines if ln.startswith("OBJECT_DEF ")]
    rows: dict[int, list[tuple[float, float, float]]] = {}
    for _o, _li, toks in placement_rows(lines):
        if toks[0] in _ROWS:
            head = float(toks[4] if toks[0] == "OBJECT" else toks[5])
            rows.setdefault(int(toks[1]), []).append((float(toks[2]), float(toks[3]), head))
    layers, uses = [], {}
    for i, placed in sorted(rows.items()):
        path = defs[i] if 0 <= i < len(defs) else ""
        if not path.lower().endswith(".obj"):
            continue
        local = resolve_resource(path.replace("\\", "/"), pack_root, {})
        ph = photo_object(local) if local else None          # (1), (2)
        if ph is None:
            continue
        got = [_placed(ph, *p) for p in placed]
        turns = sorted(t for _b, t in got)
        if turns[len(turns) // 2] > NORTH_UP_DEG:
            continue                                         # (3)
        boxes = tuple(b for b, _t in got)
        over = any(_span_m(b) >= MIN_SPAN_M and any(_overlaps(b, a) for a in areas)
                   for b in boxes)
        if over:
            img = image_file(os.path.dirname(local), ph.texture)
            frac = opaque_fraction(img) if img else None
            over = frac is None or frac >= MIN_OPAQUE        # (4)
        layers.append(Layer(layer_index(i), path, ph.texture, boxes, over, ph.layer))
        uses[layer_index(i)] = len(placed)
    return layers, uses, defs
