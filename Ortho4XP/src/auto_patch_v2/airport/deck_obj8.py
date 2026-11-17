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

__all__ = ["DeckFrame", "DeckLine", "DeckLight", "DeckSkin", "DeckSheet", "DECK_MARK",
           "deck_obj8_text", "overlay_obj8_text"]

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
    ``"yellow"``, ``"white"`` or ``"black"`` (``airport/deck_paint``)."""

    points: tuple[XY, ...]
    width_m: float
    colour: str = "yellow"
    #: the stripe stands this far over the top (a ``_b`` line's black
    #: under-stripe at 0, its colour over it), so two never z-fight
    lift_m: float = 0.0


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


def _tris(poly: Polygon) -> list[Polygon]:
    return [t for t in shapely.get_parts(shapely.constrained_delaunay_triangles(poly))
            if t.area > 1e-6]


def _plates(m: _Mesh, poly: Polygon, top_y: _t.Callable[[float, float], float],
            thickness_m: float, tile: "XY | None" = None) -> tuple[int, int]:
    """Top and underside triangles; returns ``(top index count, all)``.
    ``tile``: the ``(width, height)`` metres one repeat of a TILED texture
    covers (u across the route, v along it), else the atlas regions."""
    box = poly.bounds
    tris = _tris(poly)

    def uv(region, x: float, z: float) -> XY:
        return (x / tile[0], -z / tile[1]) if tile else _region_uv(region, x, z, box)
    n0 = len(m.idx)
    for t in tris:
        ids = [m.vertex((x, top_y(x, z), z), (0.0, 1.0, 0.0), uv(_tex.CONCRETE_UV, x, z))
               for x, z in list(t.exterior.coords)[:3]]
        m.tri(*ids, inward=(0.0, -1.0, 0.0))
    n_top = len(m.idx) - n0
    for t in tris:
        ids = [m.vertex((x, top_y(x, z) - thickness_m, z), (0.0, -1.0, 0.0),
                        uv(_tex.FASCIA_UV, x, z))
               for x, z in list(t.exterior.coords)[:3]]
        m.tri(*ids, inward=(0.0, 1.0, 0.0))
    return n_top, len(m.idx) - n0


def _fascia(m: _Mesh, poly: Polygon, top_y, thickness_m: float,
            tile: "XY | None" = None) -> None:
    """One quad per ring edge, facing out of the slab: rings oriented
    counter-clockwise in ``(x, z)`` coordinates, so the solid lies LEFT of
    each edge there and the outward normal is the edge's right normal."""
    poly = orient(poly, 1.0)
    for ring in (poly.exterior, *poly.interiors):
        pts = list(ring.coords)
        per = max(ring.length, 1e-9)
        s = 0.0
        for (xa, za), (xb, zb) in zip(pts[:-1], pts[1:], strict=True):
            d = math.hypot(xb - xa, zb - za)
            if d < 1e-6:
                continue
            out = ((zb - za) / d, 0.0, -(xb - xa) / d)
            inward = (-out[0], 0.0, -out[2])
            sa, sb = s, s + d          # metres along the ring
            s += d

            def uv(at: float, top: bool, r=_tex.FASCIA_UV, per=per) -> XY:
                if tile:                   # the slab's edge in tiled metres
                    return (at / tile[0], (thickness_m if top else 0.0) / tile[1])
                f = at / per
                return (r[0] + f * (r[2] - r[0]), r[3] - 1e-3 if top else r[1] + 1e-3)
            ta = m.vertex((xa, top_y(xa, za), za), out, uv(sa, True))
            tb = m.vertex((xb, top_y(xb, zb), zb), out, uv(sb, True))
            ba = m.vertex((xa, top_y(xa, za) - thickness_m, za), out, uv(sa, False))
            bb = m.vertex((xb, top_y(xb, zb) - thickness_m, zb), out, uv(sb, False))
            m.tri(ta, tb, bb, inward)
            m.tri(ta, bb, ba, inward)


def _paint(m: _Mesh, lines: _t.Sequence[DeckLine], top_y) -> None:
    for ln in lines:
        uv = _tex.uv_centre({"yellow": _tex.YELLOW_UV, "black": _tex.BLACK_UV}
                            .get(ln.colour, _tex.WHITE_UV))
        h = ln.width_m / 2.0
        for (xa, za), (xb, zb) in zip(ln.points[:-1], ln.points[1:], strict=True):
            d = math.hypot(xb - xa, zb - za)
            if d < 1e-6:
                continue
            ox, oz = -(zb - za) / d * h, (xb - xa) / d * h
            corners = ((xa + ox, za + oz), (xb + ox, zb + oz),
                       (xb - ox, zb - oz), (xa - ox, za - oz))
            ids = [m.vertex((x, top_y(x, z) + ln.lift_m, z), (0.0, 1.0, 0.0), uv)
                   for x, z in corners]
            m.tri(ids[0], ids[1], ids[2], (0.0, -1.0, 0.0))
            m.tri(ids[0], ids[2], ids[3], (0.0, -1.0, 0.0))


@_dc.dataclass(frozen=True)
class DeckSkin:
    """A TILED texture for the slab (#2132; ``airport/deck_skin``):
    ``texture`` (and ``normal``, ``""`` for none) relative to the object
    file, one repeat covering ``tile_m`` = ``(across, along)`` metres --
    X-Plane's own pavement page, drawn as the airport's pavement is."""

    texture: str
    tile_m: XY
    normal: str = ""


@_dc.dataclass(frozen=True)
class DeckSheet:
    """A textured film on the top (``airport/deck_skin``'s rubber):
    ``poly`` in ``(x, z)``, ``uv(x, z)`` its texture coordinates, standing
    ``lift_m`` over the top."""

    poly: Polygon
    uv: _t.Callable[[float, float], XY]
    lift_m: float = 0.0


def _obj_text(m: _Mesh, header: _t.Sequence[str], body: _t.Sequence[str],
              comments: _t.Sequence[str]) -> str:
    out = ["I", "800", "OBJ", "", DECK_MARK]
    out += [f"# {c}" for c in comments]
    out += ["", *header, "", f"POINT_COUNTS {len(m.vt)} 0 0 {len(m.idx)}", ""]
    out += ["VT " + " ".join(f"{v:.4f}" if k < 6 else f"{v:.5f}" for k, v in enumerate(vt))
            for vt in m.vt]
    out.append("")
    full = len(m.idx) // 10
    out += ["IDX10 " + " ".join(map(str, m.idx[10 * i:10 * i + 10])) for i in range(full)]
    out += [f"IDX {i}" for i in m.idx[10 * full:]]
    out += ["", *body]
    return "\n".join(out) + "\n"


def _light_rows(lights, top_y, lift: float) -> list[str]:
    return [f"LIGHT_NAMED {lt.name} {lt.x:.3f} {top_y(lt.x, lt.z) + lift:.3f} {lt.z:.3f}"
            for lt in lights]


def deck_obj8_text(ring: Polygon, top_y: _t.Callable[[float, float], float], *,
                   thickness_m: float, texture: str,
                   lines: _t.Sequence[DeckLine] = (),
                   lights: _t.Sequence[DeckLight] = (),
                   light_lift_m: float = 0.05,
                   lod_m: tuple[float, float] = (0.0, 6000.0),
                   comments: _t.Sequence[str] = (),
                   skin: "DeckSkin | None" = None) -> str:
    """The OBJ8 text of one deck.  ``ring`` is the plan polygon in the
    object frame ``(x, z)``; ``top_y(x, z)`` the deck top's ``y`` there
    (a plane for a ruled deck); ``texture`` the TEXTURE path relative to
    the object file (the atlas of ``deck_texture``).  With ``skin``
    (#2132) the slab is drawn in that tiled texture instead, and the paint
    and lights belong in :func:`overlay_obj8_text` (one texture per OBJ8):
    ``lines`` / ``lights`` must then be empty."""
    if ring.is_empty or not ring.is_valid or ring.area <= 0:
        raise ValueError("deck ring must be a valid, non-empty polygon")
    if skin is not None and (lines or lights):
        raise ValueError("a skinned deck carries no paint: draw it in the overlay object")
    tile = skin.tile_m if skin is not None else None
    m = _Mesh()
    n_top, _ = _plates(m, ring, top_y, thickness_m, tile)
    _fascia(m, ring, top_y, thickness_m, tile)
    n_solid = len(m.idx)
    _paint(m, lines, top_y)
    n_paint = len(m.idx) - n_solid
    header = [f"TEXTURE {texture if skin is None else skin.texture}"]
    if skin is not None and skin.normal:
        # the page's own normal map, read as the page reads it
        header += [f"TEXTURE_NORMAL {skin.normal}", "NORMAL_METALNESS"]
    body = [f"ATTR_LOD {lod_m[0]:g} {lod_m[1]:g}",
            "ATTR_hard_deck concrete", f"TRIS 0 {n_top}",
            "ATTR_no_hard", f"TRIS {n_top} {n_solid - n_top}"]
    if n_paint:
        body += ["ATTR_poly_os 2", f"TRIS {n_solid} {n_paint}", "ATTR_poly_os 0"]
    body += _light_rows(lights, top_y, light_lift_m)
    return _obj_text(m, header, body, comments)


def overlay_obj8_text(top_y: _t.Callable[[float, float], float], *, texture: str,
                      lines: _t.Sequence[DeckLine] = (),
                      sheets: _t.Sequence[DeckSheet] = (),
                      lights: _t.Sequence[DeckLight] = (),
                      light_lift_m: float = 0.05,
                      lod_m: tuple[float, float] = (0.0, 6000.0),
                      comments: _t.Sequence[str] = ()) -> str:
    """The OBJ8 text of a deck's OVERLAY (#2132): the painted ``lines``
    (``texture`` the ``deck_texture`` atlas) or the ``sheets`` (one
    texture's film, the rubber), never hard, drawn over the slab under
    ``ATTR_poly_os`` -- placed at the deck's own anchor, in its frame."""
    m = _Mesh()
    for sh in sheets:
        for t in _tris(sh.poly):
            ids = [m.vertex((x, top_y(x, z) + sh.lift_m, z), (0.0, 1.0, 0.0), sh.uv(x, z))
                   for x, z in list(t.exterior.coords)[:3]]
            m.tri(*ids, inward=(0.0, -1.0, 0.0))
    _paint(m, lines, top_y)
    body = [f"ATTR_LOD {lod_m[0]:g} {lod_m[1]:g}", "ATTR_no_hard"]
    if m.idx:
        body += ["ATTR_poly_os 2", f"TRIS 0 {len(m.idx)}", "ATTR_poly_os 0"]
    body += _light_rows(lights, top_y, light_lift_m)
    return _obj_text(m, [f"TEXTURE {texture}"], body, comments)
