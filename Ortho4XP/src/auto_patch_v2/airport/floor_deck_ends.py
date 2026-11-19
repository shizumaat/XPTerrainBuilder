"""A DECK OF AN OBJECT FLOOR'S FRAME SEATED BY ITS OWN END LINES (owner
RULINGS 2026-11-18c, an exception to 2026-10-22o).

THE RULE.  A placement of an object floor's frame (``airport/object_floor.
seat_records``: written whole at the frame's zero, 22o's "connected objects
stay one group") that is a DECK — its dominant near-horizontal plate
(``deck_signature.dominant_plate``'s bin rule) standing ``[bridge]
deck_min_elevation_m`` or more over the frame's floor and running
``deck_min_span_m`` or more along its axis — is seated by its OWN END LINES
when

* BOTH ends land on MAPPED ROADS standing more than the seat tolerance
  (``[placement] split_tol_m``) over its seated deck top there.  An end is
  the deck's own end EDGE (a skew deck's follows the skew), read across
  its width every touch distance; its APPROACH BAND runs from the edge one
  ``[bridge] abutment_sample_step_m`` outward along the span; the end lands
  on a road when a station of the band stands on a road face of the design
  surface (``surface.roles``, ``model.planar.ROAD_ROLES``), and the road is
  the median ground of the band's road stations.  A road meeting the end
  beside a bank the frame's own cut graded is still the road the deck
  carries: the 22p majority reading AT the line (``bridge_approach.
  end_ground``) reads the bank there; and
* its ONLY contact with the frame is a BEARING contact under its deck:
  every part of a frame mate within the touch distance of it stands more
  than the seat tolerance below its deck top (it rests on the mate — a
  wall running on beyond it included; nothing of the frame rises beside
  or over it).

It is then seated FLUSH at the LOWER road end (22m / 22p: the deck meets
its road at an end line); the higher end's remaining step is the terrain's
to grade (#1138), listed by :func:`log_line` and never chased.  The rest of
the frame stays at the floor; a gap over the frame bodies the deck rested
on is accepted (owner 2026-11-18T02:33Z, "b").

Geometry only: nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np

__all__ = ["EndLift", "EndSeat", "law_of", "faces_of", "place", "read_seat", "end_lifts",
           "lifted", "log_line"]


#: how far inside the deck an end line's stations read its top (m): past
#: the end's chamfer, short of the next span
HAIR_M = 0.5


@_dc.dataclass(frozen=True)
class _Law:
    normal_y_min: float
    bin_m: float
    area_tie: float
    min_elevation_m: float
    min_span_m: float
    step_m: float
    tol_m: float
    touch_m: float


@_dc.dataclass(frozen=True)
class EndLift:
    """One deck seated by its end lines: its record ``id`` and resource,
    the frame ``zero`` it stood at, the ``lift`` onto the lower road end;
    per end (end order) the road ``ground`` and the deck ``top`` at the
    frame's zero; the ``flush`` end's index and the ``step`` the other end
    keeps (its road over the lifted deck top: #1138's)."""

    id: str
    resource: str
    zero: float
    lift: float
    ground: tuple[float, float]
    top: tuple[float, float]
    flush: int
    step: float


def law_of(structures: _t.Any) -> "_Law | None":
    """The rule's law from ``law.tables.structures``; ``None`` (disarmed)
    where a key predates it."""
    from .open_frame_seat import TOUCH_M
    try:
        br, pl = structures.bridge, structures.placement
        return _Law(float(br.deck_plate_normal_y_min), float(br.deck_plane_bin_m),
                    float(br.deck_plane_area_tie), float(br.deck_min_elevation_m),
                    float(br.deck_min_span_m), float(br.abutment_sample_step_m),
                    float(pl.split_tol_m), float(TOUCH_M))
    except AttributeError:
        return None


# ── the placed geometry ─────────────────────────────────────────────────

def faces_of(path: str, memo: dict) -> "np.ndarray | None":
    """The STATIC solid triangles ``(n, 3, 3)`` of authored ``(x, y, z)``
    corners of a resource, read once."""
    if path not in memo:
        from . import obj8 as _obj8
        got = None
        try:
            g = _obj8.parse_obj8(path)
            t = np.asarray(g.solid, int).reshape(-1, 3)
            if len(g.animated) == len(t):
                t = t[~np.asarray(g.animated, bool)]
            if len(t):
                got = np.asarray(g.vertices, float)[:, :3][t]
        except (OSError, ValueError):
            got = None
        memo[path] = got
    return memo[path]


def place(f: np.ndarray, e0: float, n0: float, heading_deg: float, zero: float) -> np.ndarray:
    """``(n, 3, 3)`` of ``(east, north, z)``: the authored faces ``f`` set
    at ``(e0, n0)`` at ``heading_deg`` (``obj8.placement_affine``'s
    convention), z the world height at the frame's ``zero``."""
    h = math.radians(float(heading_deg or 0.0))
    c, s = math.cos(h), math.sin(h)
    x, y, z = f[..., 0], f[..., 1], f[..., 2]
    return np.stack([e0 + x * c - z * s, n0 - (x * s + z * c), zero + y], axis=-1)


def _placed(f: np.ndarray, row: _t.Any, origin: tuple[float, float], zero: float
            ) -> np.ndarray:
    """:func:`place` at a dump row: metres about ``origin``."""
    from .rebake_plan import _mpd
    ml, mo = _mpd(float(origin[0]))
    return place(f, (float(row.lon) - origin[1]) * mo, (float(row.lat) - origin[0]) * ml,
                 float(getattr(row, "heading_deg", 0.0) or 0.0), zero)


def _plate(f: np.ndarray, law: _Law) -> "tuple[float, np.ndarray] | None":
    """``(y, mask)`` of the DOMINANT plate (``deck_signature.dominant_plate``'s
    bin rule over every solid face): its bin height and its faces."""
    p0, p1, p2 = f[:, 0], f[:, 1], f[:, 2]
    nrm = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(nrm, axis=1)
    ny = np.where(ln > 1e-12, np.abs(nrm[:, 1]) / np.maximum(ln, 1e-12), 0.0)
    area = 0.5 * np.abs((p1[:, 0] - p0[:, 0]) * (p2[:, 2] - p0[:, 2])
                        - (p2[:, 0] - p0[:, 0]) * (p1[:, 2] - p0[:, 2]))
    flat = ny >= law.normal_y_min
    if not flat.any():
        return None
    k = np.round(f[:, :, 1].mean(axis=1) / law.bin_m).astype(int)
    bins: dict[int, float] = {}
    for b, a in zip(k[flat].tolist(), area[flat].tolist(), strict=True):
        bins[b] = bins.get(b, 0.0) + a
    top = max(bins.values())
    dom = max(b for b, a in bins.items() if a >= law.area_tie * top)
    return dom * law.bin_m, flat & (k == dom)


# ── the reading ─────────────────────────────────────────────────────────

def _deck(pf: np.ndarray, f: np.ndarray, law: _Law):
    """``(plan, axis, near-horizontal faces placed)`` of a deck placement,
    or ``None`` where it is no deck (module doc): ``plan`` the union of its
    near-horizontal faces, ``axis`` ``(u, v, t0, t1)`` its span direction,
    the cross direction and the plan's extent across it (the minimum
    rectangle's long side is the span)."""
    import shapely
    got = _plate(f, law)
    if got is None:
        return None
    y, _m = got
    if y - min(0.0, float(f[:, :, 1].min())) < law.min_elevation_m:
        return None
    flat = pf[_flat(f, law)]
    if not len(flat):
        return None
    tri = shapely.polygons(flat[..., :2])
    plan = shapely.union_all(shapely.buffer(tri[shapely.area(tri) > 0.0], 0.05))
    axis = _axis(np.asarray(plan.convex_hull.exterior.coords), law.min_span_m)
    return None if axis is None else (plan, axis, flat)


def _axis(h: np.ndarray, min_span_m: float):
    """``(u, v, t0, t1)`` of the minimum-area rectangle around the hull
    ``h`` (one hull edge per side tried): ``u`` along its long side, ``v``
    across, ``t0..t1`` the extent across; ``None`` under ``min_span_m``."""
    best = None
    for a, b in zip(h[:-1], h[1:], strict=True):
        d = b - a
        ln = float(np.hypot(*d))
        if ln < 1e-9:
            continue
        u = d / ln
        v = np.array([-u[1], u[0]])
        s, t = h @ u, h @ v
        area = (s.max() - s.min()) * (t.max() - t.min())
        if best is None or area < best[0]:
            best = (area, u, v, float(s.max() - s.min()), float(t.min()), float(t.max()))
    if best is None:
        return None
    _a, u, v, ls, t0, t1 = best
    if ls < t1 - t0:                  # the edge tried runs across the span
        ls, u, v = t1 - t0, v, -u
        t0, t1 = float((h @ v).min()), float((h @ v).max())
    return (u, v, t0, t1) if ls >= min_span_m else None


def _flat(f: np.ndarray, law: _Law) -> np.ndarray:
    """The near-horizontal faces (``deck_plate_normal_y_min``) of ``f``."""
    nrm = np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0])
    ln = np.linalg.norm(nrm, axis=1)
    return (ln > 1e-12) & (np.abs(nrm[:, 1]) >= law.normal_y_min * np.maximum(ln, 1e-12))


def _end_edges(plan, axis, step_m: float, hair_m: float
               ) -> "tuple[tuple[np.ndarray, np.ndarray], ...] | None":
    """The deck's two END EDGES read across its width: per cross station
    (every ``step_m``) the plan's first and last point along the span —
    a SKEW deck's end follows its own edge, never the rectangle's —
    as ``(outside, inside)`` station arrays ``hair_m`` beyond and within
    it, end order low ``s`` first; ``None`` where no station crosses."""
    import shapely
    u, v, t0, t1 = axis
    n = max(2, int(math.ceil((t1 - t0) / step_m)))
    reach = float(np.abs(np.asarray(plan.envelope.exterior.coords) @ u).max()) + 1.0
    lo_out, lo_in, hi_out, hi_in = [], [], [], []
    for t in np.linspace(t0, t1, n + 1)[1:-1]:
        ray = shapely.LineString([v * t - u * reach, v * t + u * reach])
        hit = plan.intersection(ray)
        if hit.is_empty:
            continue
        s = np.asarray(shapely.get_coordinates(hit)) @ u
        for s_end, sign, out_, in_ in ((s.min(), -1.0, lo_out, lo_in),
                                       (s.max(), 1.0, hi_out, hi_in)):
            out_.append(v * t + u * (s_end + sign * hair_m))
            in_.append(v * t + u * (s_end - sign * hair_m))
    if not lo_out:
        return None
    return ((np.asarray(lo_out), np.asarray(lo_in)), (np.asarray(hi_out), np.asarray(hi_in)))


def _top_at(flat: np.ndarray, q: np.ndarray) -> "float | None":
    """The deck top over the stations ``q``: the median of the highest
    near-horizontal face over each (the driven surface; a parapet is a
    station or two of many); ``None`` where no face stands over any."""
    import shapely
    tree = shapely.STRtree(shapely.polygons(flat[..., :2]))
    pt, face = tree.query(shapely.points(q[:, 0], q[:, 1]), predicate="intersects")
    if not len(pt):
        return None
    best = np.full(len(q), -np.inf)
    np.maximum.at(best, pt, flat[..., 2].max(axis=1)[face])
    return float(np.median(best[np.isfinite(best)]))


def _samples(t: np.ndarray, step_m: float) -> np.ndarray:
    """Points over one triangle every ~``step_m`` (a barycentric grid)."""
    edge = max(math.dist(t[0], t[1]), math.dist(t[1], t[2]), math.dist(t[2], t[0]))
    n = int(min(60, max(1, math.ceil(edge / step_m))))
    i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
    k = (i + j) <= n
    a, b = i[k] / n, j[k] / n
    return t[0] + a[:, None] * (t[1] - t[0]) + b[:, None] * (t[2] - t[0])


def _bearing_only(deck_pf: np.ndarray, plan, top_z: float, mates: _t.Sequence[np.ndarray],
                  law: _Law) -> bool:
    """Every part of a frame mate within ``touch_m`` of the deck stands
    below its deck top by more than the seat tolerance: it bears the deck
    from under it (a wall it rests on, running on beyond it), and nothing
    of the frame rises beside or over it (module doc)."""
    from shapely import contains_xy
    lo = float(deck_pf[..., 2].min()) - law.touch_m
    hi = float(deck_pf[..., 2].max()) + law.touch_m
    near = plan.buffer(law.touch_m)
    x0, y0, x1, y1 = near.bounds
    for mf in mates:
        box = ((mf[..., 0].max(axis=1) >= x0) & (mf[..., 0].min(axis=1) <= x1)
               & (mf[..., 1].max(axis=1) >= y0) & (mf[..., 1].min(axis=1) <= y1)
               & (mf[..., 2].max(axis=1) >= lo) & (mf[..., 2].min(axis=1) <= hi))
        for t in mf[box]:
            p = _samples(t, 0.5)
            p = p[(p[:, 2] >= lo) & (p[:, 2] <= hi)]
            q = p[contains_xy(near, p[:, 0], p[:, 1])] if len(p) else p
            if not len(q):
                continue
            if (q[:, 2] > top_z - law.tol_m).any():
                return False          # rises to the deck: no bearing under it
    return True


def _end_road(edge: np.ndarray, out_dir: np.ndarray, law: _Law, surface: _t.Callable,
              to_ll: _t.Callable) -> "float | None":
    """The road an end lands on (module doc): the median ground of the
    road stations of its approach band — the ``edge`` stations walked
    ``out_dir`` every touch distance up to one abutment step — or ``None``
    where none stands on a road face."""
    from ..model.planar import ROAD_ROLES
    roles = getattr(surface, "roles", None)
    if roles is None or not len(edge):
        return None
    walk = np.arange(0.0, law.step_m + 1e-9, law.touch_m)
    q = (edge[None, :, :] + walk[:, None, None] * out_dir[None, None, :]).reshape(-1, 2)
    st = [to_ll(e, n) for e, n in q]
    got = roles.roles_many([a[0] for a in st], [a[1] for a in st])
    zs = sorted(float(z) for z in (surface(la, lo) for (la, lo), r
                                   in zip(st, got, strict=True) if r in ROAD_ROLES)
                if z is not None)
    return zs[len(zs) // 2] if zs else None


@_dc.dataclass(frozen=True)
class EndSeat:
    """One placed deck read by its own end lines (module doc): its
    ``plan``, its two END EDGES as stations ON the edge (end order, low
    ``s`` first), per end the road ``ground`` and the deck ``top`` at the
    zero it was placed at, the ``flush`` end's index and the ``lift`` onto
    it."""

    plan: _t.Any
    edges: tuple[np.ndarray, np.ndarray]
    ground: tuple[float, float]
    top: tuple[float, float]
    flush: int
    lift: float


def read_seat(pf: np.ndarray, f: np.ndarray, mates: _t.Sequence[np.ndarray], law: _Law,
              end_ground: _t.Callable[[np.ndarray, np.ndarray], "float | None"]
              ) -> "EndSeat | None":
    """THE RULE on one placement (module doc), wherever its ground is read:
    ``pf`` its faces placed (``(east, north, z)``), ``f`` as authored,
    ``mates`` its frame mates placed, ``end_ground(edge stations, outward
    direction)`` the road an end lands on (``None``: no road).  The object
    stage reads the drawn surface's road faces (:func:`end_lifts`); the
    pack stage predicts it (``airport/stack_end_seat``).  ``None`` where the
    rule does not seat it."""
    deck = _deck(pf, f, law)
    if deck is None:
        return None
    plan, axis, flat = deck
    edges = _end_edges(plan, axis, law.touch_m, HAIR_M)
    if edges is None:
        return None
    roads = [end_ground(out_, sign * axis[0])
             for (out_, _in), sign in zip(edges, (-1.0, 1.0), strict=True)]
    tops = [_top_at(flat, in_) for _out, in_ in edges]
    if any(g is None for g in roads) or any(t is None for t in tops):
        return None
    grounds = (float(roads[0]), float(roads[1]))
    tops_ = (float(tops[0]), float(tops[1]))
    if any(g - t <= law.tol_m for g, t in zip(grounds, tops_, strict=True)):
        return None
    if not _bearing_only(pf, plan, min(tops_), mates, law):
        return None
    low = 0 if grounds[0] <= grounds[1] else 1
    on_edge = tuple(0.5 * (o + i) for o, i in edges)
    return EndSeat(plan, (on_edge[0], on_edge[1]), grounds, tops_, low,
                   grounds[low] - tops_[low])


def _frame(dump: _t.Any, records) -> list:
    """``(record, row)`` of every object-floor record naming a dump row."""
    from . import dsf as _dsf
    from .terrain_shaped import OBJECT_FLOOR_SEAT
    rows = list(getattr(dump, "placements", ()) or ())
    out = []
    for r in records or ():
        if not hasattr(r, "get") or r.get("seat") != OBJECT_FLOOR_SEAT:
            continue
        tile, i = _dsf.row_of(str(r.get("id", "")))
        if tile is None and i is not None and 0 <= i < len(rows) \
                and str(rows[i].def_path) == str(r.get("resource")):
            out.append((r, rows[i]))
    return out


def end_lifts(dump: _t.Any, records: _t.Sequence[_t.Mapping[str, _t.Any]],
              surface: _t.Callable, pack_root: str, law: "_Law | None"
              ) -> tuple[EndLift, ...]:
    """Every object-floor frame deck the rule seats by its end lines
    (module doc), in record order; ``()`` with no law."""
    from .rebake_plan import _mpd
    frame = _frame(dump, records) if law is not None else []
    if len(frame) < 2:
        return ()
    memo: dict = {}
    origin = (float(frame[0][1].lat), float(frame[0][1].lon))
    ml, mo = _mpd(origin[0])

    def to_ll(e: float, n: float) -> tuple[float, float]:
        return origin[0] + n / ml, origin[1] + e / mo

    placed = []
    for r, row in frame:
        f = faces_of(os.path.join(pack_root, *str(row.def_path).replace("\\", "/").split("/")),
                   memo)
        placed.append(None if f is None else (f, _placed(f, row, origin, float(r["elevation"]))))
    out = []
    for k, (r, _row) in enumerate(frame):
        if placed[k] is None:
            continue
        mates = [p[1] for j, p in enumerate(placed) if j != k and p is not None]
        got = read_seat(placed[k][1], placed[k][0], mates, law,
                        lambda edge, d: _end_road(edge, d, law, surface, to_ll))
        if got is None:
            continue
        g, t, low = got.ground, got.top, got.flush
        out.append(EndLift(str(r["id"]), str(r.get("resource")), float(r["elevation"]),
                           round(got.lift, 3), g, t, low,
                           round(g[1 - low] - (t[1 - low] + got.lift), 3)))
    return tuple(out)


def lifted(records: _t.Sequence[_t.Mapping[str, _t.Any]], lifts: _t.Sequence[EndLift]
           ) -> tuple:
    """``records`` with each lifted deck's elevation raised by its lift and
    its seat ``terrain_shaped.DECK_ENDS_SEAT``; every other record as given."""
    from .terrain_shaped import DECK_ENDS_SEAT
    by = {d.id: d for d in lifts}
    out = []
    for r in records or ():
        d = by.get(str(r.get("id", ""))) if hasattr(r, "get") else None
        out.append(r if d is None else
                   {**r, "seat": DECK_ENDS_SEAT,
                    "elevation": round(float(r["elevation"]) + d.lift, 3)})
    return tuple(out)


def log_line(d: EndLift) -> str:
    """One line per lifted deck: its flush end and the other end's step."""
    return (f"floor deck ends (RULINGS 2026-11-18c): {d.resource} {d.id} lifted "
            f"{d.lift:+.2f} from the frame zero {d.zero:.3f}; end {d.flush + 1} flush with "
            f"its road {d.ground[d.flush]:.2f}; end {2 - d.flush}'s road "
            f"{d.ground[1 - d.flush]:.2f} stands {d.step:+.2f} over the deck (#1138)")
