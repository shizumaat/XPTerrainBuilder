"""ONE GENERATED DECK'S OBJECTS (spec 2123 A2; #2132, #2141): the slab
and its overlays, as OBJ8 texts at the deck's one anchor.

``generated_pack.recipe`` hands each published deck record here.  The
deck's FRAME runs its carried route along ``-z`` (the route's own chord
across the ring, so X-Plane's slabs, the tire marks and the directional
lights all run along the taxiway, #2141 (1)); then:

* the SLAB (``deck_obj8``) in X-Plane's page for the pavement it carries
  (``deck_pavement``: the apt.dat surface under the ring, runway or
  taxiway page) with the page's normal and weather map (``deck_skin``;
  never the page's ``DECAL_LIB``: see :data:`_FILM_STEP_M`), and the bridge under it (``deck_structure``: slab,
  edge beam, beams, kerbs, piers; two LODs);
* the PAINT overlay: each dropped apt.dat line in X-Plane's own line art
  (``deck_line_art``), the expansion joints across the ends, and the
  named lights (``deck_paint.light_names``);
* the RUBBER overlay: the rubber page's centre band, a strip along the
  route.

Where the install resolves nothing, one object on the generated atlas
(``deck_texture``) as before.  Nothing here names an airport.

Build-time impact: the object stage only -- shapely on a handful of
rings, a few thousand vertices per deck.
"""
from __future__ import annotations

import math
import os
import typing as _t

from shapely.geometry import LineString, MultiPoint, Polygon
from shapely.ops import transform

from . import deck_paint as _paint
from .deck_line_art import LinePage
from .deck_obj8 import (
    DeckFrame,
    DeckLight,
    DeckLine,
    DeckSkin,
    DeckStrip,
    deck_obj8_text,
    overlay_obj8_text,
)
from .deck_structure import Part

__all__ = ["install_art", "deck_objects", "ring_polygon"]

GENERATED_DIR = "objects/o4_generated"
TEXTURE = "o4_deck_concrete.png"


#: apt.dat ``120`` taxiway CENTRELINE types (plain, ``_b``, wide) and lights
_CENTRE_TYPES = frozenset((1, 51, 10, 60))
_CENTRE_LIGHTS = frozenset((101, 107))

#: THE FILMS ARE SOLID GEOMETRY (owner sim read 2026-11-17, app 1.0.555:
#: the deck's paint did not draw, "the texture moves and changes as the
#: view changes").  An OBJ is not draped: X-Plane draws ``ATTR_poly_os``
#: geometry in its own pass, and Laminar puts ``DECAL_LIB`` (an airport
#: pavement / marking decal) and ``WEATHER_TRANSPARENT`` only on DRAPED
#: geometry (``ATTR_draped``; no non-draped default-scenery OBJ carries
#: either).  So the overlays carry none of the three: each film stands
#: ``[deck_gen] rubber_lift_m`` / ``paint_lift_m`` over the top, and a
#: line's layers (a ``_b`` line's black border, then its colour) this far
#: apart, so nothing coplanar fights at distance.
_FILM_STEP_M = 0.01


def ring_polygon(ring) -> Polygon:
    """A record's ``[[lon, lat], ...]`` ring as a valid polygon."""
    p = Polygon([tuple(q) for q in ring])
    return p if p.is_valid else p.buffer(0.0)


def _mean(pts) -> tuple[float, float]:
    """The centroid of the points ``pts`` (an end line's stations)."""
    c = MultiPoint([tuple(p) for p in pts]).centroid
    return (c.x, c.y)


def _chord(lines: _t.Sequence[_t.Sequence], R0: Polygon) -> "tuple[float, float] | None":
    """The direction of the longest piece of ``lines`` inside ``R0``,
    first point to last."""
    pieces = []
    for pts in lines:
        if len(pts) >= 2:
            g = LineString(pts).intersection(R0)
            pieces += [q for q in getattr(g, "geoms", [g])
                       if q.geom_type == "LineString" and q.length > 1.0]
    if not pieces:
        return None
    c = list(max(pieces, key=lambda q: q.length).coords)
    return (c[-1][0] - c[0][0], c[-1][1] - c[0][1])


def _deck_frame(rec: _t.Mapping, dropped=()) -> DeckFrame:
    """The placement frame: anchored at the ring's centroid, heading along
    the taxiway it carries -- the longest dropped CENTRELINE across the
    ring (``dropped``: the deck's dropped apt.dat lines), else the carried
    route's chord, else end A's centroid to end B's -- signed end A to
    end B, so the taxiway runs along ``-z`` (#2141 (1): X-Plane's slabs
    and the tire marks then run along it)."""
    c = ring_polygon(rec["ring"]).centroid
    f0 = DeckFrame(c.x, c.y, 0.0)
    (ax, az), (bx, bz) = (f0.to_local(*_mean(rec["seats_a"])),
                          f0.to_local(*_mean(rec["seats_b"])))
    R0 = transform(lambda x, y, _z=None: f0.to_local(x, y), ring_polygon(rec["ring"]))
    centre = [[f0.to_local(lo, la) for lo, la in d.points] for d in dropped
              if int(d.line or 0) in _CENTRE_TYPES or int(d.light or 0) in _CENTRE_LIGHTS]
    route = [[f0.to_local(lo, la) for lo, la in rec.get("route") or ()]]
    d = _chord(centre, R0) or _chord(route, R0)
    if d is not None and d[0] * (bx - ax) + d[1] * (bz - az) < 0.0:
        d = (-d[0], -d[1])
    dx, dz = d if d is not None else (bx - ax, bz - az)
    hdg = math.degrees(math.atan2(dx, -dz)) % 360.0
    return DeckFrame(c.x, c.y, hdg)


def _top_fn(rec: _t.Mapping, frame: DeckFrame):
    """``top_y(x, z)``: the deck's one plane in the object frame -- level
    across the A->B line, ``top_a`` at end A rising to ``top_b`` at end
    B, plus ``top_lift_m`` (the object's zero is the deck's zero)."""
    a = frame.to_local(*_mean(rec["seats_a"]))
    b = frame.to_local(*_mean(rec["seats_b"]))
    dx, dz = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dz * dz or 1.0
    ta, tb, lift = float(rec["top_a"]), float(rec["top_b"]), float(rec.get("top_lift_m", 0.02))

    def top_y(x: float, z: float) -> float:
        t = ((x - a[0]) * dx + (z - a[1]) * dz) / n2
        return ta + t * (tb - ta) + lift
    return top_y


class _Art(_t.NamedTuple):
    """What the install draws decks with: ``slab(page) -> PageArt | None``
    (cached), the ``lines`` pages by apt.dat type, the ``rubber`` page,
    and ``links`` (pack path -> install file) filled as art is used."""

    slab: _t.Callable[[str], _t.Any]
    lines: dict
    rubber: _t.Any
    links: dict


def install_art(g, root: "str | None", resolve) -> _Art:
    """The install's art for decks (``deck_skin``, ``deck_line_art``);
    nothing resolves when ``root`` is falsy."""
    from . import deck_line_art as _lines
    from . import deck_skin as _skin
    resolve = _skin.laminar_first(resolve) if root else resolve
    cache: dict = {}

    def slab(page: str):
        if page not in cache:
            cache[page] = _skin.page_art(page, root, resolve) if root else None
        return cache[page]
    return _Art(slab, _lines.line_pages(str(g.line_lib), root, resolve) if root else {},
               _skin.page_art(str(g.rubber_pol), root, resolve) if root else None, {})


def _link(art: _Art, path: str) -> str:
    """The pack name of an install file, recorded in ``art.links``."""
    from .deck_skin import link_name
    if not path:
        return ""
    name = link_name(path)
    art.links[f"{GENERATED_DIR}/{name}"] = path
    return name


class _Piece(_t.NamedTuple):
    line: LineString          # in the deck frame
    line_type: int
    light: int


def _pieces(dropped, R: Polygon, frame: DeckFrame) -> list[_Piece]:
    """The dropped apt.dat ``120`` pieces inside the deck, in its frame."""
    inner = R.buffer(-0.05)
    out = []
    for d in dropped:
        g = LineString([frame.to_local(lo, la) for lo, la in d.points]).intersection(inner)
        for piece in getattr(g, "geoms", [g]):
            if not piece.is_empty and piece.geom_type == "LineString" and piece.length >= 0.2:
                out.append(_Piece(piece, int(d.line or 0), int(d.light or 0)))
    return out


def _lights(pieces: _t.Sequence[_Piece], step: float) -> list[DeckLight]:
    out = []
    for p in pieces:
        names = _paint.light_names(p.light) if p.light else ()
        s = step / 2.0
        while names and s < p.line.length:
            q = p.line.interpolate(s)
            out += [DeckLight(n, q.x, q.y) for n in names]
            s += step
    return out


def _atlas_lines(pieces: _t.Sequence[_Piece], lift: float, stats: dict) -> list[DeckLine]:
    """The pieces as the generated atlas's stripes (``deck_paint``),
    ``lift`` over the top (the colours a layer step over the black)."""
    lines: list[DeckLine] = []
    for p in pieces:
        stripes = _paint.stripes_of(p.line_type) if p.line_type else ()
        if p.line_type and not stripes:
            stats["unpainted"] += 1
        for k, (off, w, colour, dash) in enumerate(stripes):
            ln = p.line.parallel_offset(off, "left") if abs(off) > 1e-6 else p.line
            for gg in getattr(ln, "geoms", [ln]):
                if gg.is_empty or gg.length < 0.05:
                    continue
                for seg in _paint.dashed_pieces(gg, dash):
                    lines.append(DeckLine(tuple(seg.coords), w, colour,
                                          lift + (0.0 if colour == "black"
                                                  else _FILM_STEP_M * (k + 1))))
            stats["lines"] += 1
    return lines


def _art_strips(pieces: _t.Sequence[_Piece], pages: "dict[int, LinePage]", lift: float,
                stats: dict) -> list[DeckStrip]:
    """The pieces in X-Plane's own line art: one strip per layer."""
    out: list[DeckStrip] = []
    for p in pieces:
        page = pages.get(p.line_type) if p.line_type else None
        if p.line_type and page is None:
            stats["unpainted"] += 1
        if page is None:
            continue
        for k, lay in enumerate(page.layers):
            left, right = page.span_m(lay)
            out.append(DeckStrip(tuple(p.line.coords), left, right,
                                 (lay[0] / page.tex_width, lay[2] / page.tex_width),
                                 page.scale_m[1], lift + _FILM_STEP_M * k))
        stats["lines"] += 1
    return out


def _joints(R: Polygon, ends, g) -> list[tuple[tuple[float, float], ...]]:
    """The expansion joints: each end edge, ``joint_inset_m`` inside the ring."""
    from .deck_structure import end_edges
    out = []
    for a, b in end_edges(R, ends, float(g.end_tol_m), float(g.end_angle_deg)):
        edge = LineString([a, b])
        for side in ("left", "right"):
            ln = edge.parallel_offset(float(g.joint_inset_m), side)
            if not ln.is_empty and R.contains(ln.interpolate(0.5, normalized=True)):
                ln = ln.intersection(R.buffer(-0.05))
                out += [tuple(q.coords) for q in getattr(ln, "geoms", [ln])
                        if q.geom_type == "LineString" and q.length > 0.2]
                break
    return out


def _centreline(pieces: _t.Sequence[_Piece]) -> list:
    """The longest dropped taxiway centreline on the deck (``(x, z)``
    points), ``[]`` for none: the wheels run there, so the tire marks do."""
    cl = [p.line for p in pieces if p.line_type in _CENTRE_TYPES or p.light in _CENTRE_LIGHTS]
    return list(max(cl, key=lambda q: q.length).coords) if cl else []


def _rubber(R: Polygon, route: _t.Sequence, page, g) -> list[DeckStrip]:
    """#2141 (2): the rubber page's centre band (``rubber_u0``-``u1``), a
    strip along ``route`` (the painted centreline, else the carried
    route) inside the deck, mirrored every repeat."""
    w, h = page.scale_m
    u0, u1 = float(g.rubber_u0), float(g.rubber_u1)
    half = (u1 - u0) * w / 2.0
    inner = R.buffer(-0.05)
    line = LineString(route).intersection(inner) if len(route) >= 2 else None
    if line is None or line.is_empty:
        _x0, z0, _x1, z1 = R.bounds
        line = LineString([(R.centroid.x, z1 + 1.0),
                           (R.centroid.x, z0 - 1.0)]).intersection(inner)
    return [DeckStrip(tuple(q.coords), half, half, (u0, u1), h, float(g.rubber_lift_m), True)
            for q in getattr(line, "geoms", [line])
            if q.geom_type == "LineString" and q.length > 1.0]


def _structure(R: Polygon, rec: _t.Mapping, frame: DeckFrame, ends, g) -> "list[Part]":
    from .deck_structure import Road, structure_parts
    roads = [Road(tuple(frame.to_local(lo, la) for lo, la in r["line"]), float(r["half_m"]))
             for r in rec.get("roads") or () if len(r.get("line") or ()) >= 2]
    floor = rec.get("floor_m")
    floor_y = (min(float(rec["top_a"]), float(rec["top_b"])) - float(floor)
               if floor is not None else None)
    return structure_parts(R, ends, g, roads=roads, floor_y=floor_y)


def _slab_skin(rec: _t.Mapping, R: Polygon, route, art: _Art, g, surface_code
               ) -> "DeckSkin | None":
    """The slab's skin: X-Plane's page for the carried pavement's surface
    (``deck_pavement``), else ``[deck_gen] concrete_pol``; ``None`` when
    the install resolves neither."""
    from .deck_pavement import surface_page
    page = surface_page(surface_code, str(rec.get("family") or "")) \
        if surface_code is not None else None
    pa = (art.slab(page) if page else None) or art.slab(str(g.concrete_pol))
    if pa is None:
        return None
    xs = [p[0] for p in route] or [R.centroid.x]
    return DeckSkin(_link(art, pa.albedo), pa.scale_m, _link(art, pa.normal),
                    _link(art, pa.weather), "", pa.surface or "concrete",
                    sum(xs) / len(xs))


def _film_material(art: _Art, page, metalness: bool) -> list[str]:
    """A film's material rows: its normal map only (:data:`_FILM_STEP_M`)."""
    out = []
    if page.normal:
        out.append(f"TEXTURE_NORMAL {_link(art, page.normal)}")
        if metalness:
            out.append("NORMAL_METALNESS")
    return out + ["GLOBAL_specular 1"]


def deck_objects(rec: _t.Mapping, dropped, art: _Art, g, *, surface_code: "int | None" = None
                 ) -> tuple[list[tuple[str, str]], dict]:
    """``([(pack path, OBJ8 text)], stats)`` of one deck (module doc):
    ``dropped`` its dropped apt.dat lines (``apt_flatten``), ``art`` the
    install's (:func:`install_art`), ``g`` the ``[deck_gen]`` law,
    ``surface_code`` the apt.dat surface it carries."""
    frame = _deck_frame(rec, dropped)
    R = transform(lambda x, y, _z=None: frame.to_local(x, y), ring_polygon(rec["ring"]))
    top_y = _top_fn(rec, frame)
    rel = str(rec["resource"])
    thick, lod = float(rec.get("thickness_m", 1.0)), (0.0, float(g.lod_m))
    comments = [f"{rec['object_id']} spec 2123 A2: zero {float(rec['zero_m']):.3f} m heading "
                f"{frame.heading_deg:.3f}"]
    route = [frame.to_local(lo, la) for lo, la in rec.get("route") or ()]
    route_in = LineString(route).intersection(R) if len(route) >= 2 else None
    route_xy = list(getattr(route_in, "coords", ())) if route_in is not None and \
        route_in.geom_type == "LineString" else []
    ends = [[frame.to_local(lo, la) for lo, la in rec[k]] for k in ("seats_a", "seats_b")]
    stats = {"lines": 0, "unpainted": 0, "lights": 0, "parts": 0, "frame": frame}
    pieces = _pieces(dropped, R, frame)
    lights = _lights(pieces, float(g.light_spacing_m))
    stats["lights"] = len(lights)
    parts = _structure(R, rec, frame, ends, g)
    stats["parts"] = len(parts)
    stats["piers"] = sum(1 for p in parts if p.name == "column")
    skin = _slab_skin(rec, R, route_xy, art, g, surface_code)
    joints = _joints(R, ends, g)
    near = float(g.near_lod_m)
    if skin is None:
        lift = float(g.paint_lift_m)
        lines = _atlas_lines(pieces, lift, stats) + \
            [DeckLine(j, float(g.joint_m), "black", lift) for j in joints]
        return [(rel, deck_obj8_text(R, top_y, thickness_m=thick, texture=TEXTURE, lines=lines,
                                     lights=lights, lod_m=lod, comments=comments, parts=parts,
                                     near_lod_m=near))], stats
    stats["slab"] = os.path.basename(art.links.get(f"{GENERATED_DIR}/{skin.texture}", ""))
    out = [(rel, deck_obj8_text(R, top_y, thickness_m=thick, texture=TEXTURE, lod_m=lod,
                                comments=comments, skin=skin, parts=parts, near_lod_m=near))]
    paint = _paint_overlay(pieces, joints, lights, top_y, art, g, lod, comments, stats)
    if paint:
        out.append((rel[:-4] + "_paint.obj", paint))
    strips = _rubber(R, _centreline(pieces) or route_xy, art.rubber, g) \
        if art.rubber is not None else []
    if strips:
        out.append((rel[:-4] + "_rubber.obj",
                    overlay_obj8_text(top_y, texture=_link(art, art.rubber.albedo), strips=strips,
                                      lod_m=lod, comments=comments,
                                      material=_film_material(art, art.rubber, True))))
    return out, stats


def _paint_overlay(pieces, joints, lights, top_y, art: _Art, g, lod, comments, stats) -> str:
    """The paint + lights overlay: X-Plane's line art where the install
    has it (the joints in a ``_b`` line's black border), else the atlas."""
    lift = float(g.paint_lift_m)
    if art.lines:
        strips = _art_strips(pieces, art.lines, lift, stats)
        black = next((p for t, p in sorted(art.lines.items()) if t > 50 and len(p.layers) > 1),
                     None)
        if black is not None:
            lay = black.layers[0]
            u = (lay[0] / black.tex_width, lay[2] / black.tex_width)
            strips += [DeckStrip(j, float(g.joint_m) / 2, float(g.joint_m) / 2, u,
                                 black.scale_m[1], lift) for j in joints]
        if not strips and not lights:
            return ""
        page = art.lines[min(art.lines)]
        return overlay_obj8_text(top_y, texture=_link(art, page.texture), strips=strips,
                                 lights=lights, lod_m=lod, comments=comments,
                                 material=_film_material(art, page, False))
    lines = _atlas_lines(pieces, lift, stats) + [DeckLine(j, float(g.joint_m), "black", lift)
                                                 for j in joints]
    if not lines and not lights:
        return ""
    return overlay_obj8_text(top_y, texture=TEXTURE, lines=lines, lights=lights, lod_m=lod,
                             comments=comments)
