"""AGPs JOINED BY AN AUTHORED CONNECTOR SEAT AS ONE GROUP (#2090; owner
2026-11-14T20:49Z, KDEN: "The terminal is connected via the skybridge to
concourse A, so must stay with concourse A as part of the object group").

HOW X-PLANE SEATS AN ``.agp``: rigidly, on the drawn ground under ONE
point, its ``GROUND_PT`` (``agp_pieces``).  Two ``.agp`` placements of one
pack that the author joined by a floor — KDEN's Concourse A sky bridge,
whose two decks run into the Jeppesen terminal's two bridge ramps — each
read their own point: Concourse A on its graded building pad (1638.49),
the terminal on the lidar plaza under its great hall (1625.97), and the
bridge decks land 3.50 m above the ramps they were drawn to meet.

THE RULE, general to every pair of pack-local on-ground ``.agp`` rows:

* a CONNECTOR FLOOR is a solid face of a piece facing up (X-Plane's
  clockwise front face; ``|n_y|`` at least :data:`FLAT` of its area
  normal; ``[agp] flat``) standing ``[agp] connector_floor_m`` or more
  over its group's ground line — headroom over a road or an apron, so two buildings
  whose ground slabs merely touch never join;
* two placements JOIN where a connector-floor vertex of one stands
  within ``[agp] contact_m`` (plan) of a connector-floor vertex of the
  other; each such pair votes the datum step ``delta = y_a - y_b`` that
  makes the two floors meet (``datum_b = datum_a + delta``), one vote
  per distinct pair of floor heights.  THE JOIN'S CERTAINTY (spec 2090
  C1 V2, RULINGS 2026-11-13r): the winning step stands when it has two
  or more votes and more than any rival, or when it is within ``[agp]
  flat_step_tol_m`` of zero (one pair is enough); a single pair with a
  non-zero step, or a tie, is no join (listed with its step).  KDEN: the
  lower deck 11.48 meets the lower ramp 20.50 and the upper deck 15.98
  the upper ramp 25.00 — two votes for -9.02; every other pairing gets
  one;
* THE PUBLISHED GROUP (spec 2090 A1-A6): the pack stage derives each
  group ONCE (``airport/agp_group``), the stage-2 rewrite reads its datum
  on the design surface (``constraints/agp_level``) and the graded
  surface publishes it (``agp_groups``); :func:`plan_lifts` given that
  record lifts every follower to its PUBLISHED datum.  Without the key
  (a surface graded before it) the fallback below stands;
* FALLBACK: in each joined group the GOVERNOR is the member whose ground point
  stands on a face of the airport's graded surface (``surface.roles``;
  the rolled-on roles first, then the lowest row) — its datum is the
  design surface's (airside is king); a member that reads ungraded
  ground FOLLOWS; a member on graded ground never moves (it stands on
  the design surface), so two such members' floors are never read.  A
  group with no member on a graded face is left as authored.  A floor
  under an animation (a jetway's tunnel) joins nothing: KEWR's jetways
  and their fixed extensions vote steps of 5 m at rest;
* each follower's datum becomes the governor's plus the joins' steps
  along the group (breadth first, row order), and its pieces are lifted
  by ``need - drawn ground`` in a COPY of its file
  (``<stem>__g_<hash>.agp`` beside it, every ``OBJ_DELTA`` height moved;
  ``agp_pieces.lifted_text``), the DSF row pointed at the copy and kept
  ON THE GROUND (RULINGS 2026-09-28a (4) Q-31: an ``.agp`` row is never
  written ``OBJECT_MSL``).  A lift under ``[agp] lift_tol_m`` writes
  nothing: the authored file and row are kept byte for byte.

What it does NOT do: grade the ground to the lifted group (the design
surface's business: the garage bridges and lots at KDEN must come up to
it); move a library ``.agp`` (its pieces resolve beside the library);
lift an ``.agp`` holding a placement a height cannot move
(``agp_pieces._OTHER``).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np

from ..law.agp_schema import AgpLaw
from ..model.placement import CUT_MARK, AgpSeat
from . import agp_pieces as _ap

__all__ = ["candidates", "joins", "plan_lifts", "ground_box", "RELIEF_M"]

#: V4: the drawn relief is read within this of the ground point (m)
RELIEF_M = 2.0
_LAW = AgpLaw()


@_dc.dataclass(frozen=True)
class _Member:
    """One pack-local on-ground ``.agp`` row."""

    index: int
    resource: str
    text: str
    agp: _ap.AgpFile
    lon: float
    lat: float
    heading_deg: float
    #: the pack stage's object id (``dsf:obj<index>``); ``""`` at the
    #: object stage, which reads the dump
    row: str = ""


@_dc.dataclass(frozen=True)
class _Join:
    """Two members whose connector floors meet: ``step`` is the datum of
    the second minus the first's that makes them meet; ``(lon, lat)`` the
    middle of the floors' contact; ``votes`` the distinct level pairs of
    the winning step and ``rival`` the runner-up's; ``stands`` V2's
    verdict (a refused join is listed, never lifted)."""

    step: float
    lon: float
    lat: float
    votes: int = 0
    rival: int = 0
    stands: bool = True


@_dc.dataclass(frozen=True)
class _AgpFileOut:
    """A lifted copy: pack-relative ``resource`` and its whole ``text``
    (the shape ``placement_write.write_files`` writes)."""

    resource: str
    text: str


def candidates(dump: _t.Any, pack_root: str) -> list[_Member]:
    """Every on-ground (``OBJECT``, or ``OBJECT_MSL``, which converts)
    row of ``dump`` whose definition is a PACK-LOCAL ``.agp``."""
    out: list[_Member] = []
    read: dict[str, tuple[str, _ap.AgpFile] | None] = {}
    for i, p in enumerate(getattr(dump, "placements", ()) or ()):
        d = p.def_path
        if not d.lower().endswith(".agp") or p.kind not in ("OBJECT", "OBJECT_MSL"):
            continue
        if d not in read:
            path = os.path.join(pack_root, *d.lstrip("/").replace("\\", "/").split("/"))
            agp = _ap.read_agp(path) if os.path.isfile(path) else None
            text = ""
            if agp is not None:
                with open(path, "r", encoding="latin-1", errors="replace") as fh:
                    text = fh.read()
            read[d] = None if agp is None else (text, agp)
        if read[d] is not None:
            out.append(_Member(i, d, read[d][0], read[d][1], p.lon, p.lat,
                               p.heading_deg))
    return out


def ground_box(members: _t.Sequence[_Member]) -> tuple[float, float, float, float] | None:
    """``(min_lon, min_lat, max_lon, max_lat)`` over the members' ground
    points, or ``None`` with none — what the mesh reading must hold."""
    pts = [_ap.ground_point(m.agp, m.lon, m.lat, m.heading_deg) for m in members]
    if not pts:
        return None
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts))


# ── connector floors ─────────────────────────────────────────────────────

def _piece_floors(path: str, memo: dict, flat: float = _LAW.flat) -> np.ndarray:
    """``(k, 3, 3)`` — every up-facing static floor triangle of the OBJ8
    at ``path`` as its three ``(x, y, z)`` corners (authored frame),
    memoised (``agp_floors``: through the pack's floor cache)."""
    if path in memo:
        return memo[path]
    from .agp_floors import floors_of
    memo[path] = floors_of(path, flat).astype(np.float64)
    return memo[path]


def _connector_floors(m: _Member, lat0: float, lon0: float, memo: dict,
                      law: AgpLaw = _LAW, band: "float | None" = None) -> np.ndarray:
    """``(k, 3, 3)`` — the member's connector-floor triangles, corners
    ``(east, north, y)`` in the frame at ``(lat0, lon0)``, ``y`` over the
    member's datum.  Given ``band`` (#2090 C1) its GROUND floors instead:
    every corner within ``band`` of the datum."""
    def keep(y: np.ndarray) -> np.ndarray:
        return (y.min(axis=1) >= float(law.connector_floor_m) if band is None
                else np.abs(y).max(axis=1) <= float(band))
    return _placed(m, lat0, lon0, lambda obj: _piece_floors(obj, memo, float(law.flat)), keep, 3)


def _placed(m: _Member, lat0: float, lon0: float, read, keep, corners: int) -> np.ndarray:
    """``(k, corners, 3)`` — every piece's ``read(obj)`` shapes (authored
    frame) that ``keep(y over the datum)`` keeps, placed as X-Plane places
    the piece: ``(east, north, y)`` in the frame at ``(lat0, lon0)``."""
    from .anchor_rule import _m_per_deg
    ml, mo = _m_per_deg(lat0)
    rows = []
    for pc in _ap.placed_pieces(m.agp, m.lon, m.lat, m.heading_deg):
        f = read(pc.obj)
        if not f.shape[0]:
            continue
        y = f[:, :, 1] + pc.height
        ok = keep(y)
        if not ok.any():
            continue
        h = math.radians(pc.heading_deg)
        s, c = math.sin(h), math.cos(h)
        x, z = f[ok, :, 0], f[ok, :, 2]
        e0, n0 = (pc.lon - lon0) * mo, (pc.lat - lat0) * ml
        rows.append(np.stack([e0 + x * c - z * s, n0 - (x * s + z * c), y[ok]], axis=2))
    return np.concatenate(rows) if rows else np.zeros((0, corners, 3))


def member_feet(m: _Member, lat0: float, lon0: float, memo: dict, band: float) -> np.ndarray:
    """``(k, 1, 3)`` — member ``m``'s FEET (``agp_floors.feet_of``: the
    bottoms of its pieces' solids) standing within ``band`` of its datum,
    corners ``(east, north, y)`` in the frame at ``(lat0, lon0)`` (#2116 R2
    C1b)."""
    from .agp_floors import feet_of

    def read(obj: str) -> np.ndarray:
        if ("feet", obj) not in memo:
            memo[("feet", obj)] = feet_of(obj, float(_LAW.flat)).astype(np.float64)
        return memo[("feet", obj)]
    return _placed(m, lat0, lon0, read,
                   lambda y: np.abs(y).max(axis=1) <= float(band), 1)


#: a floor triangle this small (circumradius about its centroid, m) is
#: found through the centroid tree; a larger one is read against every point
_SMALL_M = 4.0


def _over(pts: np.ndarray, tris: np.ndarray, contact_m: float = _LAW.contact_m
          ) -> list[tuple[float, float, float, float]]:
    """``(y of the point, y of the floor under it, east, north)`` for every point of
    ``pts`` ``(n, 3)`` standing over (or within ``contact_m`` in plan
    of) a triangle of ``tris`` ``(k, 3, 3)``.  Vectorised over (point,
    triangle) candidate pairs: the small triangles through a centroid tree
    at their own largest radius, the few large ones against every point
    (D: one huge triangle no longer widens every point's query)."""
    if not pts.shape[0] or not tris.shape[0]:
        return []
    from scipy.spatial import cKDTree
    xy = tris[:, :, :2]
    cen = xy.mean(axis=1)
    rad = np.linalg.norm(xy - cen[:, None, :], axis=2).max(axis=1)
    small = rad <= _SMALL_M
    pi: list[np.ndarray] = []
    ti: list[np.ndarray] = []
    if small.any():
        idx = np.flatnonzero(small)
        lists = cKDTree(cen[idx]).query_ball_point(pts[:, :2], float(rad[idx].max()) + contact_m)
        lens = np.fromiter((len(c) for c in lists), int, len(lists))
        if lens.sum():
            pi.append(np.repeat(np.arange(len(lists)), lens))
            ti.append(idx[np.fromiter((k for c in lists for k in c), int, int(lens.sum()))])
    for t in np.flatnonzero(~small).tolist():
        near = np.flatnonzero(np.hypot(*(pts[:, :2] - cen[t]).T) <= rad[t] + contact_m)
        pi.append(near)
        ti.append(np.full(near.size, t))
    if not pi:
        return []
    P, T = np.concatenate(pi), np.concatenate(ti)
    if not P.size:
        return []
    t3 = tris[T]
    a, b, c = t3[:, 0, :2], t3[:, 1, :2], t3[:, 2, :2]
    p2 = pts[P, :2]
    v0, v1, v2 = b - a, c - a, p2 - a
    den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
    ok = np.abs(den) > 1e-9
    P, t3, v0, v1, v2, den, p2 = P[ok], t3[ok], v0[ok], v1[ok], v2[ok], den[ok], p2[ok]
    u = (v2[:, 0] * v1[:, 1] - v1[:, 0] * v2[:, 1]) / den
    w = (v0[:, 0] * v2[:, 1] - v2[:, 0] * v0[:, 1]) / den
    bc = np.clip(np.stack([1.0 - u - w, u, w], axis=1), 0.0, None)
    bc /= bc.sum(axis=1, keepdims=True)
    q = (bc[:, :, None] * t3[:, :, :2]).sum(axis=1)
    near = np.hypot(*(q - p2).T) <= contact_m
    yf = (bc[near] * t3[near][:, :, 2]).sum(axis=1)
    pp = pts[P[near]]
    return list(zip(pp[:, 2].tolist(), yf.tolist(), pp[:, 0].tolist(), pp[:, 1].tolist(),
                    strict=True))


def _region(fa: np.ndarray, fb: np.ndarray, contact_m: float = _LAW.contact_m
            ) -> np.ndarray | None:
    """The plan box both floor sets reach (widened by ``contact_m``), or
    ``None`` when they do not overlap."""
    if not fa.shape[0] or not fb.shape[0]:
        return None
    lo = np.maximum(fa[:, :, :2].min(axis=(0, 1)), fb[:, :, :2].min(axis=(0, 1)))
    hi = np.minimum(fa[:, :, :2].max(axis=(0, 1)), fb[:, :, :2].max(axis=(0, 1)))
    lo, hi = lo - contact_m, hi + contact_m
    return None if np.any(lo > hi) else np.stack([lo, hi])


def _in(tris: np.ndarray, box: np.ndarray) -> np.ndarray:
    """The triangles of ``tris`` with a corner inside ``box``."""
    xy = tris[:, :, :2]
    inside = np.all((xy >= box[0]) & (xy <= box[1]), axis=2).any(axis=1)
    return tris[inside]


def _step(fa: np.ndarray, fb: np.ndarray, law: AgpLaw = _LAW
          ) -> tuple[float, np.ndarray, int, int, bool] | None:
    """``(step, contact, votes, rival, stands)``: the voted datum step
    ``datum_b - datum_a`` that makes the floors meet (``y_a - y_b`` over
    each other), the middle of their contact ``(east, north)``, the
    winning step's distinct level pairs, the runner-up's, and V2's
    verdict (module doc) — or ``None`` with no contact."""
    contact = float(law.contact_m)
    box = _region(fa, fb, contact)
    if box is None:
        return None
    ta, tb = _in(fa, box), _in(fb, box)
    va = np.unique(ta.reshape(-1, 3), axis=0) if ta.shape[0] else np.zeros((0, 3))
    vb = np.unique(tb.reshape(-1, 3), axis=0) if tb.shape[0] else np.zeros((0, 3))
    over_a, over_b = _over(va, tb, contact), _over(vb, ta, contact)
    pairs = {(round(ya, 2), round(yb, 2)) for ya, yb, _e, _n in over_a}
    pairs |= {(round(ya, 2), round(yb, 2)) for yb, ya, _e, _n in over_b}
    if not pairs:
        return None
    step, n, rival, stands = _vote(pairs, law)
    mid = np.array([[e, n_] for _a, _b, e, n_ in over_a + over_b]).mean(axis=0)
    return step, mid, n, rival, stands


def _vote(pairs: _t.Iterable[tuple[float, float]], law: AgpLaw = _LAW
          ) -> tuple[float, int, int, bool]:
    """``(step, votes, rival, stands)`` of the distinct level pairs
    ``pairs`` (``(y_a, y_b)``): V2 (module doc)."""
    votes: dict[int, list[float]] = {}
    for ya, yb in sorted(pairs):
        d = ya - yb
        votes.setdefault(int(round(d / float(law.step_bin_m))), []).append(d)
    ranked = sorted(votes.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    step = float(np.median(ranked[0][1]))
    n, rival = len(ranked[0][1]), (len(ranked[1][1]) if len(ranked) > 1 else 0)
    stands = n > rival and (n >= 2 or abs(step) <= float(law.flat_step_tol_m))
    return step, n, rival, stands


def joins(members: _t.Sequence[_Member],
          pairs: _t.Callable[[int, int], bool] | None = None,
          law: AgpLaw = _LAW, refused: "dict | None" = None
          ) -> dict[tuple[int, int], _Join]:
    """``{(i, j): _Join}`` — member list positions ``i < j`` that JOIN, the
    datum step ``datum_j - datum_i`` that makes their floors meet and
    where they meet.
    Only members with ``OBJ_DELTA`` pieces whose tiles come within
    ``[agp] contact_m`` of each other are read (a piece file is parsed only
    for such a pair), and only the pairs ``pairs(i, j)`` admits.  A pair
    whose floors meet but V2 refuses goes to ``refused`` (when given)."""
    from .anchor_rule import _m_per_deg
    from .riders import agp_footprint_xy
    if len(members) < 2:
        return {}
    lat0, lon0 = members[0].lat, members[0].lon
    ml, mo = _m_per_deg(lat0)
    contact = float(law.contact_m)
    boxes: list[tuple[float, float, float, float] | None] = []
    for m in members:
        ring = agp_footprint_xy(m.agp.path, ((m.lon - lon0) * mo, (m.lat - lat0) * ml),
                                m.heading_deg) if m.agp.deltas else None
        boxes.append(None if not ring else (min(p[0] for p in ring), min(p[1] for p in ring),
                                            max(p[0] for p in ring), max(p[1] for p in ring)))
    memo: dict = {}
    floors: dict[int, np.ndarray] = {}
    out: dict[tuple[int, int], _Join] = {}
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            a, b = boxes[i], boxes[j]
            if pairs is not None and not pairs(i, j):
                continue
            if a is None or b is None or a[0] > b[2] + contact or b[0] > a[2] + contact \
                    or a[1] > b[3] + contact or b[1] > a[3] + contact:
                continue
            for k in (i, j):
                if k not in floors:
                    floors[k] = _connector_floors(members[k], lat0, lon0, memo, law)
            got = _step(floors[i], floors[j], law)
            if got is None:
                continue
            lon, lat = lon0 + got[1][0] / mo, lat0 + got[1][1] / ml
            jn = _Join(got[0], float(lon), float(lat), got[2], got[3], got[4])
            if jn.stands:
                out[(i, j)] = jn
            elif refused is not None:
                refused[(i, j)] = jn
    return out


# ── the seat ─────────────────────────────────────────────────────────────

def _governor(group: _t.Sequence[int], members: _t.Sequence[_Member],
              surface: _t.Any) -> int | None:
    """The group member whose ground point stands on a graded face —
    a rolled-on role first, then the lowest row — or ``None``."""
    roles = getattr(surface, "roles", None)
    if roles is None:
        return None
    gps = [_ap.ground_point(members[k].agp, members[k].lon, members[k].lat,
                            members[k].heading_deg) for k in group]
    got = roles.roles_many([p[1] for p in gps], [p[0] for p in gps])
    rolled = getattr(surface, "rolled_on", None) or frozenset()
    ranked = sorted((0 if r in rolled else 1, members[k].index, k)
                    for k, r in zip(group, got, strict=True) if r)
    return ranked[0][2] if ranked else None


def _graded(members: _t.Sequence[_Member], surface: _t.Any) -> list[bool]:
    """Per member: does its ground point stand on a face of the graded
    surface (``surface.roles``)?  All ``False`` without roles."""
    roles = getattr(surface, "roles", None)
    if roles is None or not members:
        return [False] * len(members)
    gps = [_ap.ground_point(m.agp, m.lon, m.lat, m.heading_deg) for m in members]
    return [bool(r) for r in roles.roles_many([p[1] for p in gps], [p[0] for p in gps])]


def _groups(n: int, steps: _t.Mapping[tuple[int, int], _Join]) -> list[list[int]]:
    adj: dict[int, list[int]] = {}
    for i, j in steps:
        adj.setdefault(i, []).append(j)
        adj.setdefault(j, []).append(i)
    seen: set[int] = set()
    out = []
    for k in sorted(adj):
        if k in seen:
            continue
        comp, todo = [], [k]
        seen.add(k)
        while todo:
            x = todo.pop()
            comp.append(x)
            for y in sorted(adj[x]):
                if y not in seen:
                    seen.add(y)
                    todo.append(y)
        out.append(sorted(comp))
    return out


def _needs(gov: int, steps: _t.Mapping[tuple[int, int], _Join], datum0: float
           ) -> dict[int, float]:
    """Each group member's datum, breadth first from the governor."""
    need = {gov: datum0}
    frontier = [gov]
    while frontier:
        nxt = []
        for x in frontier:
            for (i, j), jn in sorted(steps.items()):
                if i == x and j not in need:
                    need[j] = need[x] + jn.step
                    nxt.append(j)
                elif j == x and i not in need:
                    need[i] = need[x] - jn.step
                    nxt.append(i)
        frontier = nxt
    return need


def _variant_resource(resource: str, text: str, lift_m: float) -> str:
    """``<dir>/<stem>__g_<hash>.agp`` beside the original: one name per
    (file, lift) — ``facade_seat._variant_resource``'s naming."""
    from .facade_seat import _variant_resource as _named
    return _named(resource, text, lift_m, ".agp")


def _relief(surface: _t.Callable, lon: float, lat: float) -> float:
    """V4: the drawn relief (max - min) at the ground point and four
    points :data:`RELIEF_M` from it; 0 where the mesh reads nothing."""
    dl = RELIEF_M / 111_320.0
    do = dl / max(1e-6, math.cos(math.radians(lat)))
    zs = [surface(lat + a, lon + b) for a, b in
          ((0.0, 0.0), (dl, 0.0), (-dl, 0.0), (0.0, do), (0.0, -do))]
    zs = [float(z) for z in zs if z is not None and not math.isnan(float(z))]
    return round(max(zs) - min(zs), 3) if zs else 0.0


class _Lifts:
    """The seats and lifted files :func:`plan_lifts` collects."""

    def __init__(self, law: AgpLaw) -> None:
        self.law = law
        self.seats: list[AgpSeat] = []
        self.files: dict[str, _AgpFileOut] = {}

    def lift(self, m: _Member, gm: _Member, need: float, surface: _t.Callable) -> None:
        """Lift ``m`` (governed by ``gm``) so its datum reads ``need`` on
        the drawn ground at its ground point."""
        if m.agp.other:
            return
        p = _ap.ground_point(m.agp, m.lon, m.lat, m.heading_deg)
        z = surface(p[1], p[0])
        if z is None:
            return
        lift = round(need - float(z), 2)
        if abs(lift) < float(self.law.lift_tol_m):
            return
        res = _variant_resource(m.resource, m.text, lift)
        if res not in self.files:
            note = (f"{CUT_MARK}{m.resource}: lifted {lift:+.2f} m to meet "
                    f"{gm.resource} at its connector floor (#2090)")
            self.files[res] = _AgpFileOut(res, _ap.lifted_text(m.text, lift, note))
        self.seats.append(AgpSeat(m.index, m.resource, res, lift, gm.index,
                                  p[0], p[1], round(float(z), 3), round(need, 3),
                                  _relief(surface, p[0], p[1])))


def _published_lifts(members: _t.Sequence[_Member], published: _t.Sequence[_t.Mapping],
                     surface: _t.Callable, riders: _t.Container[int], out: _Lifts
                     ) -> dict[str, _t.Any]:
    """SPEC 2090 A6: every follower of a governed published group lifted
    to its PUBLISHED datum; the governor, a member on a face stage 1
    solved, a jetway-strip rider and anything airside never move (A7).
    An unpredicted group keeps the fallback's governor (a member on a
    graded face) and its published steps.  Returns the counts."""
    by_index = {m.index: k for k, m in enumerate(members)}

    def _member(rec) -> "_Member | None":
        k = by_index.get(int(rec.get("index", -1)))
        if k is None or members[k].resource != rec.get("resource"):
            return None
        return members[k]
    off: list[float] = []
    for g in published:
        recs = list(g.get("members") or ())
        gov = next((r for r in recs if r.get("row") == g.get("governor")), None)
        if gov is None:
            _unpredicted(recs, g, surface, _member, riders, out)
            continue
        gm = _member(gov)
        if gm is None:
            continue
        gp = _ap.ground_point(gm.agp, gm.lon, gm.lat, gm.heading_deg)
        zg = surface(gp[1], gp[0])
        if zg is not None and g.get("z_gov") is not None:
            off.append(float(zg) - float(g["z_gov"]))
        for r in recs:
            if r is gov or r.get("airside") or r.get("stage1") or r.get("datum") is None:
                continue
            m = _member(r)
            if m is not None and m.index not in riders:
                out.lift(m, gm, float(r["datum"]), surface)
    worst = max(off, key=abs, default=0.0)
    return {"agp_governor_drawn_off_m": round(worst, 3),
            "agp_governor_drawn_off_listed": int(sum(abs(o) > 0.05 for o in off))}


def _unpredicted(recs, g, surface, member_of, riders, out: _Lifts) -> None:
    """An unpredicted published group (A2 named no governor): [A]'s rule
    on its published joins — the member on a graded face governs."""
    ms = [member_of(r) for r in recs]
    if any(m is None for m in ms):
        return
    pos = {r.get("row"): k for k, r in enumerate(recs)}
    steps = {}
    for j in g.get("joins") or ():
        a, b = pos.get(j.get("a")), pos.get(j.get("b"))
        if a is not None and b is not None:
            key = (min(a, b), max(a, b))
            st = float(j["step"]) if a < b else -float(j["step"])
            steps[key] = _Join(st, 0.0, 0.0)
    graded = _graded(ms, surface)
    gov = _governor(list(range(len(ms))), ms, surface)
    if gov is None:
        return
    gm = ms[gov]
    gp = _ap.ground_point(gm.agp, gm.lon, gm.lat, gm.heading_deg)
    d0 = surface(gp[1], gp[0])
    if d0 is None:
        return
    for k, nd in _needs(gov, steps, float(d0)).items():
        if k != gov and not graded[k] and not recs[k].get("airside") \
                and ms[k].index not in riders:
            out.lift(ms[k], gm, nd, surface)


def plan_lifts(dump: _t.Any, pack_root: str, surface: _t.Callable,
               members: _t.Sequence[_Member] | None = None, *,
               published: "_t.Sequence[_t.Mapping] | None" = None,
               riders: _t.Container[int] = (), law: AgpLaw = _LAW
               ) -> tuple[tuple[AgpSeat, ...], tuple[_AgpFileOut, ...], dict[str, _t.Any]]:
    """``(seats, lifted files, counts)`` for the pack's joined on-ground
    ``.agp`` rows standing on ``surface`` (the built mesh; ``surface.roles``
    names the graded faces).  ``published`` is the graded surface's
    ``agp_groups`` (spec 2090 A5/A6): given, every follower is lifted to
    its published datum and nothing is re-derived; ``None`` (a surface
    graded before the key) re-derives the groups by the fallback (module
    doc).  ``riders`` are the jetway-strip riders' row indices (A7)."""
    members = candidates(dump, pack_root) if members is None else list(members)
    out = _Lifts(law)
    if published is not None:
        counts = _published_lifts(members, published, surface, riders, out)
        counts.update({"agp_rows": len(members), "agp_groups": len(published),
                       "agp_joins": sum(len(g.get("joins") or ()) for g in published)})
    else:
        counts = _fallback_lifts(members, surface, riders, out)
        from .agp_floors import flush
        flush()                                 # the floor cache (D1)
    counts.update({"agp_lifted": len(out.seats),
                   "agp_lift_max_m": max((abs(s.lift_m) for s in out.seats), default=0.0),
                   "agp_relief_max_m": max((s.gp_relief_m for s in out.seats), default=0.0)})
    return tuple(out.seats), tuple(out.files.values()), counts


def _fallback_lifts(members: _t.Sequence[_Member], surface: _t.Callable,
                    riders: _t.Container[int], out: _Lifts) -> dict[str, _t.Any]:
    """[A]'s rule (module doc FALLBACK): the governor stands on a graded
    face; a pair of members that both stand on graded ground moves nothing
    (its floors are never read)."""
    graded = _graded(members, surface)
    steps = joins(members, lambda i, j: not (graded[i] and graded[j]), out.law)
    groups = _groups(len(members), steps)
    for group in groups:
        gov = _governor(group, members, surface)
        if gov is None:
            continue
        gm = members[gov]
        gp = _ap.ground_point(gm.agp, gm.lon, gm.lat, gm.heading_deg)
        d0 = surface(gp[1], gp[0])
        if d0 is None:
            continue
        need = _needs(gov, steps, float(d0))
        for k in group:
            if k != gov and not graded[k] and members[k].index not in riders:
                out.lift(members[k], gm, need[k], surface)
    return {"agp_rows": len(members), "agp_joins": len(steps), "agp_groups": len(groups)}
