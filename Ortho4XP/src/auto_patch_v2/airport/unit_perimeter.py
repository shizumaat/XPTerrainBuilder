"""EVERY SEATED GROUP'S PERIMETER INTERVAL AND THE GRADE FIELD (owner RULINGS
2026-11-25m (2)/(3), 25n (1)/(2)/(4)/(6); spec
``docs/specs/underside-height-map-20261125.md`` §3, step 3).

THE POPULATION (:func:`perimeters`): every footprint unit with an underside
map (``airport/unit_underside``) whose zero the build KNOWS before the mesh
--

* ``written whole`` -- S3 admits it (``underside_admission.admit``: a
  composite welded to airside, or mis-zeroed with the ground confirming):
  ``z0`` is the zero ``airport/underside_seat`` writes it at;
* ``coherent`` -- its ``t`` agrees with today's base: today's zero
  ``D - base`` is its underside zero (S3 (a), identity);
* ``today's zero`` -- S3 doubts it, or the seat refused to write it whole
  (13r: today's seat stands), and its ``t`` agrees with today's base within
  ``underside_admission.MIS_ZEROED_M``: on a pad, today's unit zero ``D -
  base`` is its zero to within the grade's own tolerance (MEASURED ELLX
  ``Terminal-A`` + SkyPark, refused: ``t`` +0.14 against base +0.06).  A
  doubted unit whose two zeros are farther apart is not graded (ELLX
  ``pool_5``: ``t`` -6.0 read off its feet; ``cargolux_hq``: -4.8, its
  floor a storey under its walls' feet; neither zero is known);
* ``no pad`` (25n (1), owner Q1) -- off every pad: the zero its stations'
  contact heights read on our DEM (the median of ``g - h``), graded only
  where a station stands more than :data:`GAP_M` off (problem spots only).

A footless map, a unit S3 calls an exception, a unit the seat refused and
a unit a row of which another rule seats (``taken``) are not graded.  ``D``
is read as the seat reads it (``underside_seat._unit_pad`` over the solved
pads).

THE INTERVAL (spec §3).  Each perimeter station ``k`` carries ``[z0 + lo_k,
z0 + hi_k - UNDER_M]``: our ground stands no lower than the edge's lowest
surface (you never see under it) and no higher than the floor behind it.
A station whose lowest surface stands over its floor less ``UNDER_M`` (a
sheet) reads ``hi`` alone: the ground meets the sheet's top.  A station
our ground stands a storey or more off is FAR (25f, 25n (6)): left as
authored, reported, never a target.

THE FIELD (:func:`field`): at a point ``p`` with ground ``g(p)`` and its
nearest target station ``k`` at plan distance ``d`` (within ``REACH_M``):
``G'(p) = g(p) + w(d) (clamp(g(p), lo_k, hi_k) - g(p))``, ``w`` 1 within
the shoulder ``W`` and linear to 0 at ``REACH_M`` (Q3: a wall-like step
becomes a bank).  Inside a group's plan only the shoulder of its own
stations moves (the object covers the rest); a point inside ANOTHER
group's plan never moves for this one's stations.

THE CUT-OUTS (:func:`cut_ceiling`, 25m (3), spec G5): every below-grade
interior's cells (``geom/underside_map.interior_cells``) bound our ground
at ``z0 + floor - UNDER_M`` -- cut only, never raised.

Pure: no shapely, no engine type beyond the map; nothing names a pack, an
object or an airport."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

from ..geom.terrain_deck import UNDER_M
from ..geom.underside_map import interior_cells

__all__ = ["GAP_M", "REACH_M", "Perimeter", "perimeters", "field",
           "cut_ceiling", "off_interval", "from_dict", "Index", "projector"]

#: a station this far off its interval is a gap (m; 25n (1))
GAP_M = 0.5
#: the feather's reach from a station (m; ``terrain_fill.REACH_M``)
REACH_M = 60.0


@_dc.dataclass(frozen=True, eq=False)
class Perimeter:
    """One group's perimeter in a metric frame: ``z0`` its zero and why
    (``written whole`` / ``coherent`` / ``no pad``); per station ``e``/``n``
    frame metres, ``lo``/``hi`` the interval (MSL), ``airside``, ``far``;
    ``plan_e``/``plan_n`` the ground-contact plan's cell centres and
    ``step`` their size; ``cut_*`` the interiors' cells (frame metres,
    ceiling MSL, open or not)."""

    unit: str
    row: str
    z0: float
    why: str
    e: np.ndarray
    n: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    airside: np.ndarray
    far: np.ndarray
    plan_e: np.ndarray
    plan_n: np.ndarray
    step: float
    cut_e: np.ndarray
    cut_n: np.ndarray
    cut_z: np.ndarray
    cut_open: np.ndarray

    def to_dict(self, to_ll: _t.Callable) -> dict[str, _t.Any]:
        """The JSON record (``lat``/``lon`` 7 dp, heights 3 dp) the tile
        build's raster grade reads (``auto_patch/terrain_cut_stage``);
        ``to_ll`` :func:`projector`'s."""
        def ll(e, n):
            if not len(e):
                return [], []
            lo, la = to_ll(np.asarray(e, float), np.asarray(n, float))
            return (np.round(np.asarray(la, float), 7).tolist(),
                    np.round(np.asarray(lo, float), 7).tolist())
        sla, slo = ll(self.e, self.n)
        pla, plo = ll(self.plan_e, self.plan_n)
        cla, clo = ll(self.cut_e, self.cut_n)
        return {"unit": self.unit[:120], "row": self.row, "z0": round(self.z0, 3),
                "why": self.why, "step": round(self.step, 3),
                "stations": {"lat": sla, "lon": slo,
                             "lo": np.round(self.lo, 3).tolist(),
                             "hi": np.round(self.hi, 3).tolist(),
                             "airside": np.asarray(self.airside, bool).astype(int).tolist(),
                             "far": np.asarray(self.far, bool).astype(int).tolist()},
                "plan": {"lat": pla, "lon": plo},
                "cut": {"lat": cla, "lon": clo, "z": np.round(self.cut_z, 3).tolist(),
                        "open": np.asarray(self.cut_open, bool).astype(int).tolist()}}


def from_dict(d: _t.Mapping[str, _t.Any], to_xy: _t.Callable) -> Perimeter:
    """A :meth:`Perimeter.to_dict` record back in the frame of ``to_xy``
    (``(lon, lat) -> (x, y)``)."""
    def xy(blk):
        la, lo = np.asarray(blk["lat"], float), np.asarray(blk["lon"], float)
        if not len(la):
            return np.zeros(0), np.zeros(0)
        x, y = to_xy(lo, la)
        return np.asarray(x, float), np.asarray(y, float)
    st, pl, ct = d["stations"], d["plan"], d["cut"]
    e, n = xy(st)
    pe, pn = xy(pl)
    ce, cn = xy(ct)
    return Perimeter(str(d["unit"]), str(d["row"]), float(d["z0"]), str(d["why"]), e, n,
                     np.asarray(st["lo"], float), np.asarray(st["hi"], float),
                     np.asarray(st.get("airside", [0] * len(e)), bool),
                     np.asarray(st["far"], bool), pe, pn, float(d["step"]), ce, cn,
                     np.asarray(ct["z"], float), np.asarray(ct["open"], bool))


def projector(frame: _t.Any) -> tuple[_t.Callable, _t.Callable]:
    """``(to_xy(lons, lats), to_ll(xs, ys) -> (lons, lats))`` over arrays in
    ``frame``'s own CRS (``terrain_cut.projector``'s convention; the
    frame's ``transformers`` are per point)."""
    from pyproj import Transformer
    fwd = Transformer.from_crs("EPSG:4326", frame.crs, always_xy=True)
    inv = Transformer.from_crs(frame.crs, "EPSG:4326", always_xy=True)

    def to_xy(lons, lats):
        x, y = fwd.transform(np.asarray(lons, float), np.asarray(lats, float))
        return np.asarray(x, float), np.asarray(y, float)

    def to_ll(xs, ys):
        lo, la = inv.transform(np.asarray(xs, float), np.asarray(ys, float))
        return np.asarray(lo, float), np.asarray(la, float)
    return to_xy, to_ll


def _interval(m: _t.Any, z0: float) -> tuple[np.ndarray, np.ndarray]:
    """``(lo, hi)`` MSL per station of map ``m`` at zero ``z0`` (module doc,
    THE INTERVAL): a sheet's ``lo`` is its ``hi``."""
    hi = z0 + np.asarray(m.hi, float) - UNDER_M
    lo = np.minimum(z0 + np.asarray(m.lo, float), hi)
    return lo, hi


def off_interval(z: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """How far each ``z`` stands outside ``[lo, hi]`` (0 inside; negative
    under ``lo``, positive over ``hi``)."""
    z = np.asarray(z, float)
    return np.where(z < lo, z - lo, np.where(z > hi, z - hi, 0.0))


def _no_pad_zero(m: _t.Any, g: np.ndarray) -> "float | None":
    """A no-pad group's zero on our ground (25n (1)): the median of ``g -
    h`` over its stations our DEM reads."""
    ok = np.isfinite(g)
    if not ok.any():
        return None
    return float(np.median(g[ok] - np.asarray(m.h, float)[ok]))


def _near_base(m: _t.Any) -> bool:
    """``t`` within ``underside_admission.MIS_ZEROED_M`` of today's base."""
    from .underside_admission import MIS_ZEROED_M
    return abs(float(m.t) - float(m.base or 0.0)) < MIS_ZEROED_M


def _zero(m: _t.Any, D: "float | None", g: np.ndarray, storey_m: float = 3.0
          ) -> "tuple[float, str] | None":
    """``(z0, why)`` of map ``m`` (module doc, THE POPULATION), or ``None``."""
    from .underside_admission import admit
    from .underside_seat import ADMITTED, _unit_zero
    verdict, det = admit(m, D, g, storey_m)
    if verdict in ADMITTED and D is not None:
        return _unit_zero(m, verdict, D), "written whole"
    if verdict == "coherent":
        return float(det["z_base"]), "coherent"
    if verdict == "doubt" and D is not None and _near_base(m):
        return float(det["z_base"]), "today's zero"
    if verdict == "exception" and det.get("why") == "no pad":
        z0 = _no_pad_zero(m, g)
        if z0 is None:
            return None
        lo, hi = _interval(m, z0)
        if not np.any(np.abs(off_interval(g, lo, hi)) > GAP_M):
            return None             # problem spots only (Q1)
        return z0, "no pad"
    return None


def perimeters(airport: _t.Any, pads: _t.Sequence[_t.Any],
               zeros: "_t.Mapping[str, float] | None" = None,
               storey_m: float = 3.0, no_pad: bool = True,
               taken: _t.AbstractSet[str] = frozenset()) -> list[Perimeter]:
    """THE POPULATION (module doc) on the solved surface's object ``pads``
    (``placement_read.pads_rims_from_graded_doc``).  ``zeros``: the units
    the seat wrote whole and at what (``underside_seat.seat_records``'
    report, ``unit -> z0``) -- when given, an admitted unit the seat
    REFUSED is not graded and the written zero is the one read.
    ``no_pad`` False leaves the no-pad groups out; ``taken``: the rows
    another rule seats (their groups keep that seat, ungraded)."""
    from .underside_composite import dem_many
    from .underside_seat import _unit_pad
    from .unit_underside import AIRSIDE_NEAR_M
    maps = [m for m in (getattr(airport, "undersides", None) or {}).values()
            if not m.footless and m.t is not None]
    if not maps:
        return []
    to_xy, to_ll = airport.frame.transformers()
    many = dem_many(airport.dem)
    out = []
    for m in sorted(maps, key=lambda q: q.key):
        if taken and any(str(r) in taken for r in m.key):
            continue
        g = np.asarray(many(m.e, m.n), dtype=float)
        _pad, D = _unit_pad(m, pads, to_ll, to_xy, AIRSIDE_NEAR_M)
        got = _zero(m, D, g, storey_m)
        if got is None or (got[1] == "no pad" and not no_pad):
            continue
        z0, why = got
        if why == "written whole" and zeros is not None:
            uid = str(m.unit)[:120]     # the seat record's own unit key
            if uid in zeros:
                z0 = float(zeros[uid])
            elif _near_base(m):         # the seat refused it: today's seat stands
                z0, why = float(D) - float(m.base or 0.0), "today's zero"
            else:
                continue
        out.append(_perimeter(m, float(z0), why, g, storey_m))
    return out


def _perimeter(m: _t.Any, z0: float, why: str, g: np.ndarray, storey_m: float) -> Perimeter:
    lo, hi = _interval(m, z0)
    far = np.isfinite(g) & (np.abs(off_interval(g, lo, hi)) >= storey_m)
    gl = m.layers
    pi, pj = np.nonzero(m.plan)
    pe, pn = gl.centres(pi, pj)
    ce, cn, cz, co = [], [], [], []
    for kind, e, n, fy in interior_cells(m):
        ok = np.isfinite(fy)
        ce.append(e[ok])
        cn.append(n[ok])
        cz.append(z0 + fy[ok] - UNDER_M)
        co.append(np.full(int(ok.sum()), kind == "open"))

    def cat(a, dt=float):
        return np.concatenate(a).astype(dt) if a else np.zeros(0, dt)
    return Perimeter(str(m.unit), str(m.key[0]), z0, why, np.asarray(m.e, float),
                     np.asarray(m.n, float), lo, hi, np.asarray(m.airside, bool), far,
                     np.asarray(pe, float), np.asarray(pn, float), float(gl.step),
                     cat(ce), cat(cn), cat(cz), cat(co, bool))


class Index:
    """The target stations of a perimeter set (FAR ones left out) and the
    plans' cells, read once for :func:`field`."""

    def __init__(self, pers: _t.Sequence[Perimeter]) -> None:
        from scipy.spatial import cKDTree
        ok = [~p.far for p in pers]
        self.owner = np.concatenate([np.full(int(k.sum()), i) for i, k in enumerate(ok)]
                                    + [np.zeros(0, int)]).astype(int)
        self.xy = np.concatenate([np.c_[p.e[k], p.n[k]] for p, k in zip(pers, ok, strict=True)]
                                 + [np.zeros((0, 2))])
        self.lo = np.concatenate([p.lo[k] for p, k in zip(pers, ok, strict=True)]
                                 + [np.zeros(0)])
        self.hi = np.concatenate([p.hi[k] for p, k in zip(pers, ok, strict=True)]
                                 + [np.zeros(0)])
        self.tree = cKDTree(self.xy) if len(self.xy) else None
        pe = [np.c_[p.plan_e, p.plan_n] for p in pers]
        self.plan_owner = np.concatenate([np.full(len(a), i) for i, a in enumerate(pe)]
                                         + [np.zeros(0, int)]).astype(int)
        allp = np.concatenate(pe + [np.zeros((0, 2))])
        self.plan_tree = cKDTree(allp) if len(allp) else None
        self.plan_half = np.concatenate([np.full(len(a), 0.5 * p.step * np.sqrt(2.0))
                                         for a, p in zip(pe, pers, strict=True)]
                                        + [np.zeros(0)])

    def plan_of(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """The perimeter whose plan covers each point (``-1``: none)."""
        out = np.full(len(x), -1)
        if self.plan_tree is None or not len(x):
            return out
        d, k = self.plan_tree.query(np.c_[x, y])
        inside = d <= self.plan_half[k]
        out[inside] = self.plan_owner[k[inside]]
        return out


def field(pers: _t.Sequence[Perimeter], x: np.ndarray, y: np.ndarray, g: np.ndarray,
          shoulder_m: float, reach_m: float = REACH_M,
          index: "Index | None" = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(G', station, d)``: THE FIELD (module doc) at frame points ``(x, y)``
    with ground ``g``, the index into the :class:`Index` stations each point
    read (``-1``: none within reach, or held by a plan) and its distance."""
    x, y, g = (np.asarray(a, float) for a in (x, y, g))
    out, which = g.copy(), np.full(len(x), -1)
    ix = index if index is not None else Index(pers)
    if ix.tree is None or not len(x):
        return out, which, np.full(len(x), np.inf)
    d, k = ix.tree.query(np.c_[x, y], distance_upper_bound=reach_m)
    near = np.isfinite(d) & np.isfinite(g)
    kk = np.minimum(k, len(ix.lo) - 1)
    plan = ix.plan_of(x, y)
    # inside a plan: only its own stations' shoulder; another's plan never
    held = (plan >= 0) & ((plan != ix.owner[kk]) | (d > shoulder_m))
    use = near & ~held
    w = np.clip(1.0 - (d - shoulder_m) / max(reach_m - shoulder_m, 1e-6), 0.0, 1.0)
    t = np.minimum(np.maximum(g, ix.lo[kk]), ix.hi[kk])
    out[use] = g[use] + w[use] * (t[use] - g[use])
    which[use] = kk[use]
    return out, which, d


def cut_ceiling(pers: _t.Sequence[Perimeter], x: np.ndarray, y: np.ndarray
                ) -> np.ndarray:
    """THE CUT-OUTS (module doc): per frame point the lowest ceiling of an
    interior cell covering it (``inf``: none)."""
    from scipy.spatial import cKDTree
    x, y = np.asarray(x, float), np.asarray(y, float)
    out = np.full(len(x), np.inf)
    for p in pers:
        if not len(p.cut_z) or not len(x):
            continue
        d, k = cKDTree(np.c_[p.cut_e, p.cut_n]).query(np.c_[x, y])
        hit = d <= 0.5 * p.step * np.sqrt(2.0)
        out[hit] = np.minimum(out[hit], p.cut_z[k[hit]])
    return out
