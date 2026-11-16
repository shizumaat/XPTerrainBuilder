"""A HUNG WEDGE WALL IS SEATED ON THE AIRSIDE AT ITS TOP (#2099 F2 P5,
spec ``docs/specs/2099-F2.md`` §6; owner RULINGS 2026-10-27r "the top of the
objects flush with the airside surface").

A pack wall hung from its zero whose top is LEVEL while its foot runs from
the zero down to a deep apex (a wedge: the face of a ramp or a trench
mouth's flank) is no retaining wall of record — the wall class refuses it
by its margins — yet its top edge is the airside's edge.  Seated at the DEM
under its anchor it stands at whatever the old ground said (measured CYYZ:
the two flanks beside a mouth drew at skirt level, 2–3 m over the apron).

THE WITNESS (all of, :func:`_witness`): gate G (``wall_sheets.hung_wall``);
at least ``[service] retaining_wall_min_length_m`` long, every piece thinner
than ``wall_face_max_thickness_m``; its top level within ``plate_bin_m`` and
its foot changing by ``shell_floor_min_m`` or more (``wall_top``'s
profiles); one face (its UPPER face, as the pack-sheet wall's side witness
names it, ``wall_sides._upper_index``) with stage-1 airside under at least
half its ``wall_sample_m`` stations ``entrance_airside_reach_m`` out, the
other face under less than half; not a retaining wall of record; no other
rule seats the row.

THE SEAT: ONE plate entry (``pipeline/rebake_inputs._plate_seats``' tuple):
``(top y, the airside stations, 0.0)`` — ``emit/rebake._plate_reading``
lands the top flush on the mean drawn airside behind the upper face.
Geometry only; no airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import math
import types
import typing as _t

import numpy as np
import shapely
from shapely.geometry import Polygon

__all__ = ["HungWedge", "WALL_TOP_PLATE", "hung_wedge_plates"]

#: the plate kind of a hung wedge wall's TOP (#2099 P5b): its §16e datum
#: (``anchor_rule.datum_of``) stands at any sign of top y, and the wall is
#: never a §16g unit member (``footprint_unit``): a unit's datum, read off a
#: pad the wall merely touches, would float the wall's top off its airside
WALL_TOP_PLATE = "wall_top"


class HungWedge(_t.NamedTuple):
    """One seated wedge wall, for the log and the twins."""

    oid: str
    top_y: float
    stations: list          # frame xy, on the stage-1 airside
    share: float            # upper face's airside share
    other: float            # the other face's
    foot_range: float


def _airside_tree(airside):
    """``(STRtree, polygons)`` of the stage-1 airside face polygons
    ``airside``; ``None`` without one."""
    polys = [g if g.is_valid else g.buffer(0.0) for g in airside or ()]
    return (shapely.STRtree(polys), polys) if polys else None


def _on_airside(tree, pts: np.ndarray) -> np.ndarray:
    """Per point of ``pts`` (``(n, 2)``): stands on a stage-1 airside face."""
    st, polys = tree
    out = np.zeros(len(pts), bool)
    if not len(pts):
        return out
    pi, fi = st.query(shapely.points(pts), predicate="intersects")
    out[np.unique(pi)] = True
    return out


def _face_stations(face, step: float, reach: float) -> np.ndarray:
    """Points ``reach`` out on the RIGHT of ``face`` (the footprint lies on
    its left, ``wall_sides._wall_faces``), every ``step`` along it."""
    out = []
    for t in np.arange(0.5 * step, face.length, step):
        a = face.interpolate(float(t))
        b = face.interpolate(min(face.length, float(t) + 0.5))
        if b.distance(a) <= 1e-9:
            b, a = a, face.interpolate(max(0.0, float(t) - 0.5))
        dx, dy = b.x - a.x, b.y - a.y
        ln = math.hypot(dx, dy)
        if ln <= 1e-9:
            continue
        p = face.interpolate(float(t))
        out.append((p.x + dy / ln * reach, p.y - dx / ln * reach))
    return np.asarray(out, float).reshape(-1, 2)


def _pieces(part, to_xy) -> list:
    polys = []
    for rg in getattr(part, "rings", None) or ():
        if len(rg) < 3:
            continue
        g = Polygon([to_xy(lon, lat) for lat, lon in rg])
        g = g if g.is_valid else g.buffer(0.0)
        if not g.is_empty and g.geom_type == "Polygon":
            polys.append(g)
    return polys


def _witness(airport, unit, member, tree, walls, law, cfg, cache, to_xy) -> HungWedge | None:
    """The module doc's witness on one member; ``None`` where it fails."""
    from .wall_class import _origin, _seat_z
    from .wall_sheets import hung_wall
    from .wall_sides import _wall_faces
    from .wall_top import foot_profile, top_profile
    ob = law.tables.structures.tunnel.object
    if len(member.parts) != 1:
        return None
    p = member.parts[0]
    by = getattr(p, "base_y", None)
    if by is None or getattr(p, "line", False) \
            or float(p.height_m) < float(cfg.retaining_wall_min_height_m):
        return None
    pieces = _pieces(p, to_xy)
    if not pieces or sum(g.length for g in pieces) / 2.0 < float(cfg.retaining_wall_min_length_m) \
            or any(2.0 * g.area / g.length >= float(ob.wall_face_max_thickness_m) for g in pieces):
        return None
    top_y = float(by) + float(p.height_m)
    if not hung_wall(p, True, top_y, _seat_z(airport, unit, member, to_xy), cfg):
        return None
    if any(g.intersection(w).area > 1e-6 for g in pieces for w in walls):
        return None             # a retaining wall of record seats itself
    comp = types.SimpleNamespace(seat_z=0.0, member=member, origin=_origin(unit, member),
                                 retained_top_y=None, top_y=top_y, retained_m=0.0,
                                 height_m=float(p.height_m))
    step, reach = float(ob.wall_sample_m), float(ob.entrance_airside_reach_m)
    tops, feet, pts, hits = [], [], [], [0, 0, 0, 0]
    for g in pieces:
        faces = _wall_faces(g)
        if faces is None:
            return None
        st = [_face_stations(f, step, reach) for f in faces]
        on = [_on_airside(tree, s) for s in st]
        k = 0 if on[0].sum() * len(on[1]) >= on[1].sum() * len(on[0]) else 1
        tp = top_profile(comp, g, faces[k], to_xy, cache)
        fp = foot_profile(comp, g, faces[1 - k], to_xy, cache)
        if not tp or not fp:
            return None
        tops += [z for _s, z in tp]
        feet += [z for _s, z in fp]
        pts += [tuple(q) for q in st[k][on[k]]]
        hits = [hits[0] + int(on[k].sum()), hits[1] + len(on[k]),
                hits[2] + int(on[1 - k].sum()), hits[3] + len(on[1 - k])]
    share, other = hits[0] / max(hits[1], 1), hits[2] / max(hits[3], 1)
    if share < 0.5 or other >= 0.5 or not pts \
            or max(tops) - min(tops) > float(ob.plate_bin_m) \
            or max(feet) - min(feet) < float(ob.shell_floor_min_m):
        return None
    return HungWedge(str(member.id), top_y, pts, share, other, max(feet) - min(feet))


def hung_wedge_plates(airport, airside, law, cfg, cache, taken) -> list[HungWedge]:
    """Every hung wedge wall of ``airport``'s pack partition no other rule
    seats (``taken``: placement ids already seated or excluded);
    ``airside`` the stage-1 airside face polygons (frame metres), ``cfg``
    the classifier's ``[service]`` rules."""
    part = getattr(airport, "partition", None)
    tree = _airside_tree(airside) if part is not None else None
    if tree is None:
        return []
    to_xy = airport.frame.entry()
    walls = [w.poly for w in (getattr(airport, "retaining_walls", ()) or ())
             if getattr(w, "poly", None) is not None]
    out = []
    for u in part.units:
        for m in u.members:
            if str(m.id) in taken:
                continue
            got = _witness(airport, u, m, tree, walls, law, cfg, cache, to_xy)
            if got is not None:
                out.append(got)
    return out
