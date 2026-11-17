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
* each :class:`DeckLine` as a strip of quads ``width_m`` wide standing
  its ``lift_m`` over the top (never ``ATTR_poly_os``: an OBJ is not
  draped, ``deck_objects._FILM_STEP_M``);
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
from dataclasses import replace as dataclass_replace

import shapely
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from . import deck_texture as _tex

__all__ = ["DeckFrame", "DeckLine", "DeckLight", "DeckSkin", "DeckStrip",
           "DECK_MARK",
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


def _cap(m: _Mesh, poly: Polygon, y, up: bool, uv) -> None:
    """One horizontal face of ``poly`` at ``y(x, z)``, facing up or down;
    ``uv(x, z)`` its texture coordinates."""
    n, inward = ((0.0, 1.0, 0.0), (0.0, -1.0, 0.0)) if up else \
        ((0.0, -1.0, 0.0), (0.0, 1.0, 0.0))
    for t in _tris(poly):
        ids = [m.vertex((x, y(x, z), z), n, uv(x, z)) for x, z in list(t.exterior.coords)[:3]]
        m.tri(*ids, inward=inward)


def _sides(m: _Mesh, poly: Polygon, y_hi, y_lo, uv) -> None:
    """One quad per ring edge from ``y_lo`` up to ``y_hi``, facing out of
    the prism: rings oriented counter-clockwise in ``(x, z)``, so the
    solid lies LEFT of each edge there and the outward normal is the
    edge's right normal.  ``uv(metres along the ring, ring length, top)``."""
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
            ta = m.vertex((xa, y_hi(xa, za), za), out, uv(sa, per, True))
            tb = m.vertex((xb, y_hi(xb, zb), zb), out, uv(sb, per, True))
            ba = m.vertex((xa, y_lo(xa, za), za), out, uv(sa, per, False))
            bb = m.vertex((xb, y_lo(xb, zb), zb), out, uv(sb, per, False))
            m.tri(ta, tb, bb, inward)
            m.tri(ta, bb, ba, inward)


def _uvs(tile: "XY | None", box, depth: float, origin_x: float = 0.0):
    """``(horizontal uv(x, z), side uv(s, per, top))``: a TILED texture in
    metres (u across the route from ``origin_x``, v along it), else the
    atlas regions (``deck_texture``)."""
    if tile:
        return (lambda x, z: ((x - origin_x) / tile[0], -z / tile[1]),
                lambda at, _per, top: (at / tile[0], (depth if top else 0.0) / tile[1]))
    r = _tex.FASCIA_UV

    def side(at: float, per: float, top: bool) -> XY:
        f = at / per
        return (r[0] + f * (r[2] - r[0]), r[3] - 1e-3 if top else r[1] + 1e-3)
    return (lambda x, z: _region_uv(_tex.CONCRETE_UV, x, z, box)), side


def _plates(m: _Mesh, poly: Polygon, top_y: _t.Callable[[float, float], float],
            thickness_m: float, tile: "XY | None" = None, origin_x: float = 0.0
            ) -> tuple[int, int]:
    """Top and underside triangles; returns ``(top index count, all)``.
    ``tile``: the ``(width, height)`` metres one repeat of a TILED texture
    covers (u across the route, v along it), else the atlas regions."""
    box = poly.bounds
    hor, _side = _uvs(tile, box, thickness_m, origin_x)
    n0 = len(m.idx)
    _cap(m, poly, top_y, True, hor)
    n_top = len(m.idx) - n0
    under = hor if tile else (lambda x, z: _region_uv(_tex.FASCIA_UV, x, z, box))
    _cap(m, poly, lambda x, z: top_y(x, z) - thickness_m, False, under)
    return n_top, len(m.idx) - n0


def _fascia(m: _Mesh, poly: Polygon, top_y, thickness_m: float,
            tile: "XY | None" = None) -> None:
    """The slab's edge faces, ``thickness_m`` deep (:func:`_sides`)."""
    _side = _uvs(tile, poly.bounds, thickness_m)[1]
    _sides(m, poly, top_y, lambda x, z: top_y(x, z) - thickness_m, _side)


def _part(m: _Mesh, part, top_y, tile: "XY | None", origin_x: float) -> None:
    """One :class:`deck_structure.Part` as a prism under ``top_y``."""
    def y_hi(x, z):
        return top_y(x, z) + part.top_m

    def y_lo(x, z):
        return part.floor_y if part.floor_y is not None else top_y(x, z) + part.bottom_m
    hor, side = _uvs(tile, part.poly.bounds, part.top_m - part.bottom_m, origin_x)
    if not tile:
        def hor(x, z, _b=part.poly.bounds):
            return _region_uv(_tex.FASCIA_UV, x, z, _b)
    if "top" in part.faces:
        _cap(m, part.poly, y_hi, True, hor)
    if "bottom" in part.faces:
        _cap(m, part.poly, y_lo, False, hor)
    if "sides" in part.faces:
        _sides(m, part.poly, y_hi, y_lo, side)


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
    X-Plane's own pavement page, drawn as the airport's pavement is.  The
    page's material rows the object repeats (spec 2132-design section 4,
    ``""`` for none): ``weather`` (its WEATHER map, relative to the
    object), ``decal_lib`` (verbatim) and ``surface`` (the hard deck's
    surface name).  ``origin_x``: the ``x`` the texture's ``u = 0`` stands
    at (the carried route's centreline, so the slabs run along it)."""

    texture: str
    tile_m: XY
    normal: str = ""
    weather: str = ""
    decal_lib: str = ""
    surface: str = "concrete"
    origin_x: float = 0.0

    def header(self) -> list[str]:
        """The object's material rows, in Laminar's own order
        (``gar5_stairs_5s.obj``): texture, normal, metalness, decal,
        weather, specular."""
        out = [f"TEXTURE {self.texture}"]
        if self.normal:
            out += [f"TEXTURE_NORMAL {self.normal}", "NORMAL_METALNESS"]
        if self.decal_lib:
            out.append(f"DECAL_LIB {self.decal_lib}")
        if self.weather:
            out.append(f"WEATHER {self.weather}")
        return out + ["GLOBAL_specular 1"]


@_dc.dataclass(frozen=True)
class DeckStrip:
    """A textured band along a polyline on the top (#2141): ``points``
    ``(x, z)``; it reaches ``left_m`` / ``right_m`` either side of them
    (left of the direction of travel, as X-Plane draws a line), ``u`` =
    ``(u at the left edge, u at the right edge)``, ``v`` = metres along
    over ``v_scale_m`` -- mirrored every repeat when ``mirror_v`` (a
    texture whose repeat does not meet itself then shows no seam) --
    standing ``lift_m`` over the top."""

    points: tuple[XY, ...]
    left_m: float
    right_m: float
    u: XY
    v_scale_m: float
    lift_m: float = 0.0
    mirror_v: bool = False


def _stations(points: _t.Sequence[XY], v_scale: float, mirror: bool
              ) -> list[tuple[float, float, float]]:
    """``(x, z, s)`` along ``points``, with a station at every repeat
    boundary when the texture is mirrored (so v folds at a vertex)."""
    out = [(points[0][0], points[0][1], 0.0)]
    s = 0.0
    for (xa, za), (xb, zb) in zip(points[:-1], points[1:], strict=True):
        d = math.hypot(xb - xa, zb - za)
        if d < 1e-6:
            continue
        if mirror:
            k = math.floor(s / v_scale) + 1
            while k * v_scale < s + d - 1e-6:
                f = (k * v_scale - s) / d
                out.append((xa + f * (xb - xa), za + f * (zb - za), k * v_scale))
                k += 1
        s += d
        out.append((xb, zb, s))
    return out


def _strip(m: _Mesh, st: DeckStrip, top_y) -> None:
    """One :class:`DeckStrip`: a mitred quad band, facing up."""
    pts = _stations(st.points, st.v_scale_m, st.mirror_v)
    if len(pts) < 2:
        return

    def left_normal(i: int) -> XY:
        """The world-left unit normal at station ``i`` (``(x, z)`` is
        mirrored against east/north: left of travel ``(dx, dz)`` is
        ``(dz, -dx)``), mitred between its two segments."""
        ns = []
        for a, b in ((i - 1, i), (i, i + 1)):
            if 0 <= a and b < len(pts):
                dx, dz = pts[b][0] - pts[a][0], pts[b][1] - pts[a][1]
                d = math.hypot(dx, dz)
                if d > 1e-6:
                    ns.append((dz / d, -dx / d))
        nx, nz = sum(n[0] for n in ns), sum(n[1] for n in ns)
        k = math.hypot(nx, nz)
        if k < 1e-9:
            return ns[0] if ns else (1.0, 0.0)
        nx, nz = nx / k, nz / k
        cos = max(0.5, nx * ns[0][0] + nz * ns[0][1]) if ns else 1.0
        return (nx / cos, nz / cos)

    def v_of(s: float) -> float:
        t = s / st.v_scale_m
        if not st.mirror_v:
            return t
        f = t % 2.0
        return f if f <= 1.0 else 2.0 - f
    prev = None
    for i, (x, z, s) in enumerate(pts):
        nx, nz = left_normal(i)
        v = v_of(s)
        lx, lz = x + nx * st.left_m, z + nz * st.left_m
        rx, rz = x - nx * st.right_m, z - nz * st.right_m
        a = m.vertex((lx, top_y(lx, lz) + st.lift_m, lz), (0.0, 1.0, 0.0), (st.u[0], v))
        b = m.vertex((rx, top_y(rx, rz) + st.lift_m, rz), (0.0, 1.0, 0.0), (st.u[1], v))
        if prev is not None:
            m.tri(prev[0], prev[1], b, (0.0, -1.0, 0.0))
            m.tri(prev[0], b, a, (0.0, -1.0, 0.0))
        prev = (a, b)


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
                   skin: "DeckSkin | None" = None,
                   parts: _t.Sequence = (),
                   near_lod_m: float = 1200.0) -> str:
    """The OBJ8 text of one deck.  ``ring`` is the plan polygon in the
    object frame ``(x, z)``; ``top_y(x, z)`` the deck top's ``y`` there
    (a plane for a ruled deck); ``texture`` the TEXTURE path relative to
    the object file (the atlas of ``deck_texture``).  With ``skin``
    (#2132) the slab is drawn in that tiled texture instead, and the paint
    and lights belong in :func:`overlay_obj8_text` (one texture per OBJ8):
    ``lines`` / ``lights`` must then be empty.

    ``parts`` (``deck_structure.structure_parts``, the slab first): the
    bridge drawn in two LODs -- every part up to ``near_lod_m`` (the slab's
    top the hard deck), then to ``lod_m[1]`` the top, the full-depth
    fascia and the kerbs only, none of it hard.  No ``parts``: today's
    one-LOD slab."""
    if ring.is_empty or not ring.is_valid or ring.area <= 0:
        raise ValueError("deck ring must be a valid, non-empty polygon")
    if skin is not None and (lines or lights):
        raise ValueError("a skinned deck carries no paint: draw it in the overlay object")
    tile = skin.tile_m if skin is not None else None
    ox = skin.origin_x if skin is not None else 0.0
    header = skin.header() if skin is not None else [f"TEXTURE {texture}"]
    hard = f"ATTR_hard_deck {skin.surface if skin is not None and skin.surface else 'concrete'}"
    m = _Mesh()
    if not parts:
        n_top, _ = _plates(m, ring, top_y, thickness_m, tile, ox)
        _fascia(m, ring, top_y, thickness_m, tile)
        n_solid = len(m.idx)
        _paint(m, lines, top_y)
        n_paint = len(m.idx) - n_solid
        body = [f"ATTR_LOD {lod_m[0]:g} {lod_m[1]:g}", hard, f"TRIS 0 {n_top}",
                "ATTR_no_hard", f"TRIS {n_top} {n_solid - n_top}"]
        if n_paint:
            body.append(f"TRIS {n_solid} {n_paint}")
        body += _light_rows(lights, top_y, light_lift_m)
        return _obj_text(m, header, body, comments)
    slab, rest = parts[0], parts[1:]
    hor = _uvs(tile, ring.bounds, thickness_m, ox)[0]
    _cap(m, slab.poly, top_y, True, hor)                      # the hard deck
    n_top = len(m.idx)
    for p in (slab, *rest):
        _part(m, dataclass_replace(p, faces=tuple(f for f in p.faces if f != "top"))
              if p is slab else p, top_y, tile, ox)
    n_near = len(m.idx)
    _plates(m, ring, top_y, thickness_m, tile, ox)            # the far LOD
    _fascia(m, ring, top_y, thickness_m, tile)
    for p in rest:
        if p.name == "kerb":
            _part(m, p, top_y, tile, ox)
    n_far = len(m.idx) - n_near
    _paint(m, lines, top_y)
    n_paint = len(m.idx) - n_near - n_far
    body = [f"ATTR_LOD {lod_m[0]:g} {near_lod_m:g}", hard, f"TRIS 0 {n_top}",
            "ATTR_no_hard", f"TRIS {n_top} {n_near - n_top}"]
    if n_paint:
        body.append(f"TRIS {n_near + n_far} {n_paint}")
    body += _light_rows(lights, top_y, light_lift_m)
    body += [f"ATTR_LOD {near_lod_m:g} {lod_m[1]:g}", "ATTR_no_hard", f"TRIS {n_near} {n_far}"]
    if n_paint:
        body.append(f"TRIS {n_near + n_far} {n_paint}")
    return _obj_text(m, header, body, comments)


def overlay_obj8_text(top_y: _t.Callable[[float, float], float], *, texture: str,
                      lines: _t.Sequence[DeckLine] = (),
                      strips: _t.Sequence[DeckStrip] = (),
                      lights: _t.Sequence[DeckLight] = (),
                      light_lift_m: float = 0.05,
                      lod_m: tuple[float, float] = (0.0, 6000.0),
                      comments: _t.Sequence[str] = (),
                      material: _t.Sequence[str] = ()) -> str:
    """The OBJ8 text of a deck's OVERLAY (#2132): the painted ``lines``
    (``texture`` the ``deck_texture`` atlas) or the ``strips`` (one
    texture's film: the rubber, X-Plane's line art),
    never hard, never casting a shadow, standing each strip's / line's
    lift over the slab (no ``ATTR_poly_os``: an OBJ is not draped) --
    placed at the deck's own anchor, in its frame.  ``material``: the
    header rows after ``TEXTURE`` (the page's normal map)."""
    m = _Mesh()
    for st in strips:
        _strip(m, st, top_y)
    _paint(m, lines, top_y)
    body = [f"ATTR_LOD {lod_m[0]:g} {lod_m[1]:g}", "ATTR_no_hard"]
    if m.idx:
        body.append(f"TRIS 0 {len(m.idx)}")
    body += _light_rows(lights, top_y, light_lift_m)
    return _obj_text(m, [f"TEXTURE {texture}", *material, "GLOBAL_no_shadow"], body, comments)
