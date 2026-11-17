"""THE GENERATED TAXIWAY DECK, AS AN OBJ8 (spec 2123 §A2, issue #2123).

A pure writer: a deck RING (plan polygon, metres in the object's frame)
and its TOP surface go in, the OBJ8 text comes out.  Nothing here reads a
pack, a DSF or the law; the caller derives the ring, the top, the painted
lines and the lights and decides where the file lands.

The object is three faces and the redrawn paint:

* the TOP, flagged ``ATTR_hard_deck concrete`` -- aircraft roll on it and
  ``airport/obj8.ObjGeometry.hard_deck`` reads it as the deck (it bears
  plan, so the deck kind is the flag, never a plate);
* the 1 m FASCIA round every ring (exterior and holes) and the UNDERSIDE,
  not hard;
* each :class:`DeckLine` as a strip of quads ``width_m`` wide on the top,
  under ``ATTR_poly_os 2`` so it never fights the concrete;
* each :class:`DeckLight` as a ``LIGHT_NAMED`` a few cm above the top.

FRAME.  OBJ8 is x east, y up, z SOUTH before the placement heading turns
it (``airport/obj8.py``).  :class:`DeckFrame` is that frame for a
placement at ``(lon, lat)`` with heading ``h``: a deck placed with ``h`` =
the route's bearing has its route axis along ``-z`` -- so the directional
named lights ``taxi_g`` / ``taxi_g_rev`` (aimed along ``+z`` / ``-z`` in
``lights.txt``) face along the taxiway both ways.

WINDING.  A face is FRONT when its vertices run clockwise seen from the
side it faces (the convention of ``tools/obj8_building_gen``); every face
here is emitted through :func:`_tri`, which orders a triangle so its
right-hand normal points INTO the solid.

Build-time impact: none at solve time; a deck is a few hundred vertices,
written by the object stage.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import shapely
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from . import deck_texture as _tex

__all__ = ["DeckFrame", "DeckLine", "DeckLight", "DECK_MARK", "deck_obj8_text"]

#: the head comment every generated deck carries (the minted-file test)
DECK_MARK = "# o4 generated deck"

XY = tuple[float, float]
_WGS_A = 6378137.0
_WGS_E2 = 6.69437999014e-3


@_dc.dataclass(frozen=True)
class DeckFrame:
    """The placement's local frame: ``to_local(lon, lat) -> (x, z)`` and
    back, on the WGS84 tangent plane at the anchor (mm-exact over a deck's
    100 m), rotated by the heading as X-Plane rotates the object."""

    lon: float
    lat: float
    heading_deg: float = 0.0

    def _radii(self) -> tuple[float, float]:
        s = math.sin(math.radians(self.lat))
        w = math.sqrt(1.0 - _WGS_E2 * s * s)
        m = _WGS_A * (1.0 - _WGS_E2) / (w ** 3)        # meridian
        n = _WGS_A / w                                  # prime vertical
        return m * math.pi / 180.0, n * math.cos(math.radians(self.lat)) * math.pi / 180.0

    def to_local(self, lon: float, lat: float) -> XY:
        m_lat, m_lon = self._radii()
        east, north = (lon - self.lon) * m_lon, (lat - self.lat) * m_lat
        h = math.radians(self.heading_deg)
        return (east * math.cos(h) - north * math.sin(h),
                -(east * math.sin(h) + north * math.cos(h)))

    def to_lonlat(self, x: float, z: float) -> XY:
        h = math.radians(self.heading_deg)
        east = x * math.cos(h) - z * math.sin(h)
        north = -(x * math.sin(h) + z * math.cos(h))
        m_lat, m_lon = self._radii()
        return (self.lon + east / m_lon, self.lat + north / m_lat)


@_dc.dataclass(frozen=True)
class DeckLine:
    """A painted line on the deck: ``points`` ``(x, z)``; ``colour`` is
    ``"yellow"`` or ``"white"``."""

    points: tuple[XY, ...]
    width_m: float
    colour: str = "yellow"


@_dc.dataclass(frozen=True)
class DeckLight:
    """A named light (``lights.txt``) at ``(x, z)`` on the deck."""

    name: str
    x: float
    z: float


class _Mesh:
    def __init__(self) -> None:
        self.vt: list[tuple[float, ...]] = []
        self.idx: list[int] = []

    def vertex(self, p: tuple[float, float, float], n: tuple[float, float, float],
               uv: XY) -> int:
        self.vt.append((*p, *n, *uv))
        return len(self.vt) - 1

    def tri(self, a: int, b: int, c: int, inward: tuple[float, float, float]) -> None:
        """Append ``a b c`` ordered so its right-hand normal points along
        ``inward`` (into the solid): clockwise seen from outside."""
        pa, pb, pc = (self.vt[i][:3] for i in (a, b, c))
        u = [pb[k] - pa[k] for k in range(3)]
        v = [pc[k] - pa[k] for k in range(3)]
        nrm = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        if sum(nrm[k] * inward[k] for k in range(3)) < 0:
            b, c = c, b
        self.idx.extend((a, b, c))


def _region_uv(region, x: float, z: float, box: tuple[float, float, float, float]) -> XY:
    """``(x, z)`` inside ``box`` mapped into a texture region (stretched,
    a hair inside its edges so no neighbour bleeds in)."""
    u0, v0, u1, v1 = region
    x0, z0, x1, z1 = box
    eps = 1.0 / _tex.SIZE
    fu = (x - x0) / max(x1 - x0, 1e-9)
    fv = (z - z0) / max(z1 - z0, 1e-9)
    return (u0 + eps + fu * (u1 - u0 - 2 * eps), v0 + eps + fv * (v1 - v0 - 2 * eps))


def _plates(m: _Mesh, poly: Polygon, top_y: _t.Callable[[float, float], float],
            thickness_m: float) -> tuple[int, int]:
    """Top and underside triangles; returns ``(top index count, all)``."""
    box = poly.bounds
    tris = [t for t in shapely.get_parts(shapely.constrained_delaunay_triangles(poly))
            if t.area > 1e-6]
    n0 = len(m.idx)
    for t in tris:
        ids = [m.vertex((x, top_y(x, z), z), (0.0, 1.0, 0.0),
                        _region_uv(_tex.CONCRETE_UV, x, z, box))
               for x, z in list(t.exterior.coords)[:3]]
        m.tri(*ids, inward=(0.0, -1.0, 0.0))
    n_top = len(m.idx) - n0
    for t in tris:
        ids = [m.vertex((x, top_y(x, z) - thickness_m, z), (0.0, -1.0, 0.0),
                        _region_uv(_tex.FASCIA_UV, x, z, box))
               for x, z in list(t.exterior.coords)[:3]]
        m.tri(*ids, inward=(0.0, 1.0, 0.0))
    return n_top, len(m.idx) - n0


def _fascia(m: _Mesh, poly: Polygon, top_y, thickness_m: float) -> None:
    """One quad per ring edge, facing out of the slab: rings oriented
    counter-clockwise in ``(x, z)`` coordinates, so the solid lies LEFT of
    each edge there and the outward normal is the edge's right normal."""
    poly = orient(poly, 1.0)
    for ring in (poly.exterior, *poly.interiors):
        pts = list(ring.coords)
        per = max(ring.length, 1e-9)
        s = 0.0
        for (xa, za), (xb, zb) in zip(pts[:-1], pts[1:]):
            d = math.hypot(xb - xa, zb - za)
            if d < 1e-6:
                continue
            out = ((zb - za) / d, 0.0, -(xb - xa) / d)
            inward = (-out[0], 0.0, -out[2])
            ua, ub = s / per, (s + d) / per
            s += d
            u0, v0, u1, v1 = _tex.FASCIA_UV
            def uv(f: float, top: bool) -> XY:
                return (u0 + f * (u1 - u0), v1 - 1e-3 if top else v0 + 1e-3)
            ta = m.vertex((xa, top_y(xa, za), za), out, uv(ua, True))
            tb = m.vertex((xb, top_y(xb, zb), zb), out, uv(ub, True))
            ba = m.vertex((xa, top_y(xa, za) - thickness_m, za), out, uv(ua, False))
            bb = m.vertex((xb, top_y(xb, zb) - thickness_m, zb), out, uv(ub, False))
            m.tri(ta, tb, bb, inward)
            m.tri(ta, bb, ba, inward)


def _paint(m: _Mesh, lines: _t.Sequence[DeckLine], top_y) -> None:
    for ln in lines:
        uv = _tex.uv_centre(_tex.YELLOW_UV if ln.colour == "yellow" else _tex.WHITE_UV)
        h = ln.width_m / 2.0
        for (xa, za), (xb, zb) in zip(ln.points[:-1], ln.points[1:]):
            d = math.hypot(xb - xa, zb - za)
            if d < 1e-6:
                continue
            ox, oz = -(zb - za) / d * h, (xb - xa) / d * h
            corners = ((xa + ox, za + oz), (xb + ox, zb + oz),
                       (xb - ox, zb - oz), (xa - ox, za - oz))
            ids = [m.vertex((x, top_y(x, z), z), (0.0, 1.0, 0.0), uv) for x, z in corners]
            m.tri(ids[0], ids[1], ids[2], (0.0, -1.0, 0.0))
            m.tri(ids[0], ids[2], ids[3], (0.0, -1.0, 0.0))


def deck_obj8_text(ring: Polygon, top_y: _t.Callable[[float, float], float], *,
                   thickness_m: float, texture: str,
                   lines: _t.Sequence[DeckLine] = (),
                   lights: _t.Sequence[DeckLight] = (),
                   light_lift_m: float = 0.05,
                   lod_m: tuple[float, float] = (0.0, 6000.0),
                   comments: _t.Sequence[str] = ()) -> str:
    """The OBJ8 text of one deck.  ``ring`` is the plan polygon in the
    object frame ``(x, z)``; ``top_y(x, z)`` the deck top's ``y`` there
    (a plane for a ruled deck); ``texture`` the TEXTURE path relative to
    the object file."""
    if ring.is_empty or not ring.is_valid or ring.area <= 0:
        raise ValueError("deck ring must be a valid, non-empty polygon")
    m = _Mesh()
    n_top, _ = _plates(m, ring, top_y, thickness_m)
    _fascia(m, ring, top_y, thickness_m)
    n_solid = len(m.idx)
    _paint(m, lines, top_y)
    n_paint = len(m.idx) - n_solid
    out = ["I", "800", "OBJ", "", DECK_MARK]
    out += [f"# {c}" for c in comments]
    out += ["", f"TEXTURE {texture}", "",
            f"POINT_COUNTS {len(m.vt)} 0 0 {len(m.idx)}", ""]
    out += ["VT " + " ".join(f"{v:.4f}" if k < 6 else f"{v:.5f}" for k, v in enumerate(vt))
            for vt in m.vt]
    out.append("")
    full = len(m.idx) // 10
    out += ["IDX10 " + " ".join(map(str, m.idx[10 * i:10 * i + 10])) for i in range(full)]
    out += [f"IDX {i}" for i in m.idx[10 * full:]]
    out += ["", f"ATTR_LOD {lod_m[0]:g} {lod_m[1]:g}",
            "ATTR_hard_deck concrete", f"TRIS 0 {n_top}",
            "ATTR_no_hard", f"TRIS {n_top} {n_solid - n_top}"]
    if n_paint:
        out += ["ATTR_poly_os 2", f"TRIS {n_solid} {n_paint}", "ATTR_poly_os 0"]
    out += [f"LIGHT_NAMED {lt.name} {lt.x:.3f} {top_y(lt.x, lt.z) + light_lift_m:.3f} {lt.z:.3f}"
            for lt in lights]
    return "\n".join(out) + "\n"
