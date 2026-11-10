"""THE BELOW-GRADE WITNESS: a cut, ramp, trench or pit stands only where
something stands BELOW THE AUTHOR'S GROUND (owner RULINGS 2026-11-07b (1):
"a pack's below-grade intent ... is judged against the pack's OWN ground
plates — the author's ground — never against our terrain or the placement
zero, for every airport"; #1950 #1961 #1966 #1972).

The author's ground is ``geom/author_ground``: the near-horizontal faces of
the pack's plate objects standing at ground level, read as the LOWEST face
at a point, and the design ground (the DEM) only where the author laid no
plates.  This module gathers it from the placed objects ONCE per pack read
(:func:`ground_of`, kept beside the ``ResourceCache`` that parsed them) and
asks the one question every cut reader asks of a pack object:

* :func:`depth_under` — how far does a placement's lowest solid stand under
  the author's ground around its footprint?  A portal over a bore's end and
  a hard-deck bridge's frame each state the road under them — at the
  portal's zero, at the frame's bottom — and the cut is admitted only where
  that road stands ``floor_sunken_min_m`` or more under the author's
  ground; less is a structure standing ON the ground over a road at grade
  (a toll booth, a garage), and nothing is cut for it.

Every number is a ``[tunnel.object]`` law value; nothing here names a pack
or an airport.
"""
from __future__ import annotations

import typing as _t
import weakref

import numpy as np

from ..geom import author_ground as _ag
from . import obj8 as _obj8
from .object_cut import _face_normals_y

__all__ = ["author_ground", "around", "ground_of", "depth_under", "row_depth_under",
           "zero_of", "floor_share", "placed_all", "xp"]


class _Below(_t.NamedTuple):
    """One below-grade reading: ``depth`` (metres the bottom stands under
    the author's ground; negative = above it, NaN = no ground read), and
    ``why`` — the line every refusal and admission quotes."""

    depth: float
    why: str


def _msl_of(airport) -> dict[str, float]:
    """``{placement id: MSL elevation}`` of the airport's ``OBJECT_MSL`` rows."""
    return {o.id: o.y_offset_m for o in getattr(airport, "dsf_objects", ()) or ()
            if o.kind == "OBJECT_MSL"}


def zero_of(o, msl: _t.Mapping[str, float]) -> float:
    """The placement's zero as read: its MSL elevation, or the ground under
    its anchor plus its AGL."""
    return float(msl[o.id]) if o.kind == "OBJECT_MSL" else float(o.anchor_z + o.agl_m)


def floor_share(g: "_obj8.ObjGeometry | None", law) -> float:
    """The share of the solid's SURFACE (3D area) its near-horizontal faces
    carry — a wall has no plan area, so plan area cannot tell a cover from
    a floor."""
    ob = law.tables.structures.tunnel.object
    if g is None or not len(g.solid):
        return 0.0
    v, t = g.vertices, g.solid
    p0, p1, p2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)
    tot = float(area.sum())
    if tot <= 0.0:
        return 0.0
    return float(area[_face_normals_y(v, t) >= ob.plate_normal_y_min].sum()) / tot


def xp(px: np.ndarray, py: np.ndarray, o, scale) -> tuple:
    """Frame positions of an OBJ's metres laid out as X-Plane lays them
    (``model.frame.xplane_metre_scale``: its sphere, the frame's WGS84)."""
    return (o.xy[0] + (px - o.xy[0]) * scale[0], o.xy[1] + (py - o.xy[1]) * scale[1])


def placed_all(o, g, zero: float, scale=(1.0, 1.0)) -> np.ndarray:
    """Every solid face of ``o`` in the frame, absolute z (A2)."""
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    F = g.vertices[g.solid]
    px, py = xp(a * F[:, :, 0] + b * F[:, :, 2] + xo, d * F[:, :, 0] + e * F[:, :, 2] + yo,
                o, scale)
    return np.stack([px, py, zero + F[:, :, 1]], axis=2)


def author_ground(placed, cache, law, msl, scale=(1.0, 1.0), shares=None,
                  ground=None) -> "_ag.AuthorGround":
    """The pack's own ground (``geom/author_ground``): the near-horizontal
    faces of every placement whose solid is a plate (near-horizontal faces
    carry ``floor_object_min_share`` of its surface), seated at its zero —
    those standing at GROUND LEVEL, within ``author_ground_band_m`` of the
    design ground under them (a roof, a deck, a departures level stands
    over it; a sunken floor under it).  ``shares`` memoises each resource's
    plate share for the caller."""
    ob = law.tables.structures.tunnel.object
    shares = {} if shares is None else shares
    faces, owners = [], []
    for p in placed:
        g = cache.geometry(p.resolved) if p.resolved else None
        if g is None or not len(g.solid):
            continue
        if p.resolved not in shares:
            shares[p.resolved] = floor_share(g, law)
        if shares[p.resolved] < ob.floor_object_min_share:
            continue
        hz = _face_normals_y(g.vertices, g.solid) >= ob.plate_normal_y_min
        if hz.any():
            f = placed_all(p, g, zero_of(p, msl), scale)[hz]
            if ground is not None:
                c = f.mean(axis=1)
                gz = np.asarray(ground(c[:, 0], c[:, 1]), float).ravel()
                f = f[np.abs(c[:, 2] - gz) <= ob.author_ground_band_m]
            faces.append(f)
            owners.extend([p.id] * len(f))
    return _ag.AuthorGround(np.concatenate(faces) if faces else np.zeros((0, 3, 3)), owners)


class _Ground(_t.NamedTuple):
    ag: "_ag.AuthorGround"
    dem: _t.Callable
    msl: dict


_MEMO: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def ground_of(airport, objects, cache, law) -> _Ground:
    """The author's ground of the pack ``objects`` (read through ``cache``),
    the DEM and the MSL rows — gathered ONCE per cache and pack read, and
    handed to every reader that asks :func:`depth_under`."""
    key = (id(airport), len(objects))
    got = _MEMO.get(cache)
    if got is not None and got[0] == key:
        return got[1]
    from ..model.frame import xplane_metre_scale
    from .dem import dem_z_many
    msl = _msl_of(airport)

    def dem(xs, ys):
        return dem_z_many(airport.dem, xs, ys)
    placed = [o for o in objects if o.resolved is not None
              and not _obj8.is_stock_library_resource(o.path)]
    ag = author_ground(placed, cache, law, msl,
                       xplane_metre_scale(airport.frame.origin[0]), None, dem)
    out = _Ground(ag, dem, msl)
    _MEMO[cache] = (key, out)
    return out


def around(foot, exclude: _t.AbstractSet[str], ag: "_ag.AuthorGround", dem, law):
    """The author's ground around ``foot`` (``author_ground_inner_m`` ..
    ``author_ground_outer_m`` outside it, the ``exclude``-d placements'
    own faces left out), else the design ground there."""
    ob = law.tables.structures.tunnel.object
    return ag.around(foot, (ob.author_ground_inner_m, ob.author_ground_outer_m),
                     ob.author_ground_step_m, ob.author_ground_min_share,
                     exclude=frozenset(exclude), dem=dem)


def depth_under(bottom_z: float, foot, exclude: _t.AbstractSet[str], g: _Ground,
                law, what: str = "its bottom") -> _Below:
    """How far ``bottom_z`` (``what``: a placement's lowest solid, a deck's
    top — absolute) stands under the author's ground around ``foot``
    (frame plan), the ``exclude``-d placements' own faces left out."""
    r = around(foot, exclude, g.ag, g.dem, law)
    if r.source == "none":
        return _Below(float("nan"), "no ground reads around it")
    depth = r.z - float(bottom_z)
    return _Below(depth, f"{what} {bottom_z:.2f} stands {depth:.2f} m under the author's "
                        f"ground around it (" + ("its plates" if r.source == "plates"
                                                 else "NO PLATES: the DEM")
                 + f" {r.z:.2f}, plates over {100 * r.share:.0f} % of the ring)")


def row_depth_under(o, low_y: float, foot, exclude: _t.AbstractSet[str], g: _Ground, law,
                    what: str = "its bottom") -> _Below:
    """:func:`depth_under` of placement ``o``'s solid ``low_y`` metres over
    its zero.  A row drawn on the ground (``OBJECT`` / ``OBJECT_AGL``) STATES
    its own depth under the author's ground: ``-(agl + low_y)``.  The deeper
    of that and the anchor-sample reading counts (#1949 OMDB
    ``tunner_5_1``, AGL -4.8: the DEM at its anchor reads 8.43 over a
    4.21 ground around it — a surface model seeing a structure — and put
    its floor 0.48 m under the ground; a DEM that sees a real trench under
    an AGL-0 row still reads it).  An ``OBJECT_MSL`` row states no ground."""
    b = depth_under(zero_of(o, g.msl) + low_y, foot, exclude, g, law, what)
    if o.kind == "OBJECT_MSL" or b.depth != b.depth:
        return b
    stated = -(float(o.agl_m) + float(low_y))
    if not stated > b.depth:
        return b
    return _Below(stated, f"{what} stands {stated:.2f} m under the ground its AGL "
                          f"{float(o.agl_m):.2f} is drawn on (the row's own statement; "
                          f"the anchor reading: {b.why})")
