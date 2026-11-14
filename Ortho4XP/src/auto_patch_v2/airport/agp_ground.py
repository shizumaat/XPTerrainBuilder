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
  normal) standing :data:`CONNECTOR_FLOOR_M` or more over its group's
  ground line — headroom over a road or an apron, so two buildings
  whose ground slabs merely touch never join;
* two placements JOIN where a connector-floor vertex of one stands
  within :data:`CONTACT_M` (plan) of a connector-floor vertex of the
  other; each such pair votes the datum step ``delta = y_a - y_b`` that
  makes the two floors meet (``datum_b = datum_a + delta``), one vote
  per distinct pair of floor heights; the step with the most votes is
  the join, and a tie is no join (the floors do not say which meets
  which).  KDEN: the lower deck 11.48 meets the lower ramp 20.50 and the
  upper deck 15.98 the upper ramp 25.00 — two votes for -9.02; every
  other pairing gets one;
* in each joined group the GOVERNOR is the member whose ground point
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
  by ``need - datum`` in a COPY of its file
  (``<stem>__g_<hash>.agp`` beside it, every ``OBJ_DELTA`` height moved;
  ``agp_pieces.lifted_text``), the DSF row pointed at the copy and kept
  ON THE GROUND (RULINGS 2026-09-28a (4) Q-31: an ``.agp`` row is never
  written ``OBJECT_MSL``).  A lift under :data:`LIFT_TOL_M` writes
  nothing: the authored file and row are kept byte for byte.

What it does NOT do: grade the ground to the lifted group (the design
surface's business: the garage bridges and lots at KDEN must come up to
it); move a library ``.agp`` (its pieces resolve beside the library);
lift an ``.agp`` holding a placement a height cannot move
(``agp_pieces._OTHER``).
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import math
import os
import typing as _t

import numpy as np

from ..model.placement import CUT_MARK, AgpSeat
from . import agp_pieces as _ap

__all__ = ["CONNECTOR_FLOOR_M", "CONTACT_M", "LIFT_TOL_M", "candidates",
           "joins", "plan_lifts", "ground_box"]

#: a floor this high over its group's ground line is a connector floor
CONNECTOR_FLOOR_M = 2.5
#: two connector-floor vertices this close in plan meet (metres)
CONTACT_M = 1.5
#: a lift smaller than this writes nothing (the pavement visibility bar)
LIFT_TOL_M = 0.05
#: a face is a floor when its normal's vertical share is at least this
FLAT = 0.9
#: the vote bins the datum step at this resolution (metres)
STEP_BIN_M = 0.05


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


@_dc.dataclass(frozen=True)
class _Join:
    """Two members whose connector floors meet: ``step`` is the datum of
    the second minus the first's that makes them meet; ``(lon, lat)`` the
    middle of the floors' contact."""

    step: float
    lon: float
    lat: float


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

def _piece_floors(path: str, memo: dict) -> np.ndarray:
    """``(k, 3, 3)`` — every up-facing floor triangle of the OBJ8 at
    ``path`` as its three ``(x, y, z)`` corners (authored frame),
    memoised."""
    if path in memo:
        return memo[path]
    from . import obj8 as _obj8
    try:
        g = _obj8.parse_obj8(path, at_rest=True)
    except (OSError, ValueError):
        g = None
    out = np.zeros((0, 3, 3))
    if g is not None and g.solid.shape[0]:
        v, t = g.vertices, g.solid
        a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
        n = np.cross(b - a, c - a)
        norm = np.linalg.norm(n, axis=1)
        # X-Plane's front face is clockwise seen from the front: an up-
        # facing floor's (b - a) x (c - a) points DOWN in the OBJ frame
        up = (norm > 1e-9) & (-n[:, 1] >= FLAT * norm)
        if g.animated.shape[0] == up.shape[0]:
            up &= ~g.animated          # a moving floor (a jetway) joins nothing
        if up.any():
            out = np.stack([a[up], b[up], c[up]], axis=1)
    memo[path] = out
    return out


def _connector_floors(m: _Member, lat0: float, lon0: float, memo: dict
                      ) -> np.ndarray:
    """``(k, 3, 3)`` — the member's connector-floor triangles, corners
    ``(east, north, y)`` in the frame at ``(lat0, lon0)``, ``y`` over the
    member's datum."""
    from .anchor_rule import _m_per_deg
    ml, mo = _m_per_deg(lat0)
    rows = []
    for pc in _ap.placed_pieces(m.agp, m.lon, m.lat, m.heading_deg):
        f = _piece_floors(pc.obj, memo)
        if not f.shape[0]:
            continue
        y = f[:, :, 1] + pc.height
        keep = y.min(axis=1) >= CONNECTOR_FLOOR_M
        if not keep.any():
            continue
        h = math.radians(pc.heading_deg)
        s, c = math.sin(h), math.cos(h)
        x, z = f[keep, :, 0], f[keep, :, 2]
        e0, n0 = (pc.lon - lon0) * mo, (pc.lat - lat0) * ml
        rows.append(np.stack([e0 + x * c - z * s, n0 - (x * s + z * c), y[keep]],
                             axis=2))
    return np.concatenate(rows) if rows else np.zeros((0, 3, 3))


def _over(pts: np.ndarray, tris: np.ndarray
          ) -> list[tuple[float, float, float, float]]:
    """``(y of the point, y of the floor under it, east, north)`` for every point of
    ``pts`` ``(n, 3)`` standing over (or within :data:`CONTACT_M` in plan
    of) a triangle of ``tris`` ``(k, 3, 3)``."""
    if not pts.shape[0] or not tris.shape[0]:
        return []
    from scipy.spatial import cKDTree
    cen = tris[:, :, :2].mean(axis=1)
    reach = float(np.linalg.norm(tris[:, :, :2] - cen[:, None, :], axis=2).max())
    tree = cKDTree(cen)
    out: list[tuple[float, float, float, float]] = []
    for p, cand in zip(pts, tree.query_ball_point(pts[:, :2], reach + CONTACT_M),
                       strict=True):
        if not cand:
            continue
        t = tris[cand]
        a, b, c = t[:, 0, :2], t[:, 1, :2], t[:, 2, :2]
        v0, v1, v2 = b - a, c - a, p[:2] - a
        den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
        ok = np.abs(den) > 1e-9
        if not ok.any():
            continue
        t, a, v0, v1, v2, den = t[ok], a[ok], v0[ok], v1[ok], v2[ok], den[ok]
        u = (v2[:, 0] * v1[:, 1] - v1[:, 0] * v2[:, 1]) / den
        w = (v0[:, 0] * v2[:, 1] - v2[:, 0] * v0[:, 1]) / den
        bc = np.clip(np.stack([1.0 - u - w, u, w], axis=1), 0.0, None)
        bc /= bc.sum(axis=1, keepdims=True)
        q = (bc[:, :, None] * t[:, :, :2]).sum(axis=1)
        near = np.hypot(*(q - p[:2]).T) <= CONTACT_M
        out.extend((float(p[2]), float(yf), float(p[0]), float(p[1])) for yf in
                   (bc[near] * t[near][:, :, 2]).sum(axis=1))
    return out


def _region(fa: np.ndarray, fb: np.ndarray) -> np.ndarray | None:
    """The plan box both floor sets reach (widened by :data:`CONTACT_M`),
    or ``None`` when they do not overlap."""
    if not fa.shape[0] or not fb.shape[0]:
        return None
    lo = np.maximum(fa[:, :, :2].min(axis=(0, 1)), fb[:, :, :2].min(axis=(0, 1)))
    hi = np.minimum(fa[:, :, :2].max(axis=(0, 1)), fb[:, :, :2].max(axis=(0, 1)))
    lo, hi = lo - CONTACT_M, hi + CONTACT_M
    return None if np.any(lo > hi) else np.stack([lo, hi])


def _in(tris: np.ndarray, box: np.ndarray) -> np.ndarray:
    """The triangles of ``tris`` with a corner inside ``box``."""
    xy = tris[:, :, :2]
    inside = np.all((xy >= box[0]) & (xy <= box[1]), axis=2).any(axis=1)
    return tris[inside]


def _step(fa: np.ndarray, fb: np.ndarray) -> tuple[float, np.ndarray] | None:
    """The voted datum step ``datum_b - datum_a`` that makes the floors
    meet (``y_a - y_b`` over each other) and the middle of their contact
    ``(east, north)``, or ``None`` (no contact, or a tie between
    steps)."""
    box = _region(fa, fb)
    if box is None:
        return None
    ta, tb = _in(fa, box), _in(fb, box)
    va = np.unique(ta.reshape(-1, 3), axis=0) if ta.shape[0] else np.zeros((0, 3))
    vb = np.unique(tb.reshape(-1, 3), axis=0) if tb.shape[0] else np.zeros((0, 3))
    over_a, over_b = _over(va, tb), _over(vb, ta)
    pairs = {(round(ya, 2), round(yb, 2)) for ya, yb, _e, _n in over_a}
    pairs |= {(round(ya, 2), round(yb, 2)) for yb, ya, _e, _n in over_b}
    if not pairs:
        return None
    votes: dict[int, list[float]] = {}
    for ya, yb in sorted(pairs):
        d = ya - yb
        votes.setdefault(int(round(d / STEP_BIN_M)), []).append(d)
    ranked = sorted(votes.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    if len(ranked) > 1 and len(ranked[0][1]) == len(ranked[1][1]):
        return None
    mid = np.array([[e, n] for _a, _b, e, n in over_a + over_b]).mean(axis=0)
    return float(np.median(ranked[0][1])), mid


def joins(members: _t.Sequence[_Member],
          pairs: _t.Callable[[int, int], bool] | None = None
          ) -> dict[tuple[int, int], _Join]:
    """``{(i, j): _Join}`` — member list positions ``i < j`` that JOIN, the
    datum step ``datum_j - datum_i`` that makes their floors meet and
    where they meet.
    Only members with ``OBJ_DELTA`` pieces whose tiles come within
    :data:`CONTACT_M` of each other are read (a piece file is parsed only
    for such a pair), and only the pairs ``pairs(i, j)`` admits."""
    from .anchor_rule import _m_per_deg
    from .riders import agp_footprint_xy
    if len(members) < 2:
        return {}
    lat0, lon0 = members[0].lat, members[0].lon
    ml, mo = _m_per_deg(lat0)
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
            if a is None or b is None or a[0] > b[2] + CONTACT_M or b[0] > a[2] + CONTACT_M \
                    or a[1] > b[3] + CONTACT_M or b[1] > a[3] + CONTACT_M:
                continue
            for k in (i, j):
                if k not in floors:
                    floors[k] = _connector_floors(members[k], lat0, lon0, memo)
            got = _step(floors[i], floors[j])
            if got is not None:
                lon, lat = lon0 + got[1][0] / mo, lat0 + got[1][1] / ml
                out[(i, j)] = _Join(got[0], float(lon), float(lat))
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
    stem, _ext = os.path.splitext(resource.replace("\\", "/"))
    h = hashlib.sha256(f"{text}\0{lift_m:.2f}".encode("utf-8", "surrogateescape"))
    return f"{stem}__g_{h.hexdigest()[:8]}.agp"


def plan_lifts(dump: _t.Any, pack_root: str, surface: _t.Callable,
               members: _t.Sequence[_Member] | None = None
               ) -> tuple[tuple[AgpSeat, ...], tuple[_AgpFileOut, ...], dict[str, _t.Any]]:
    """``(seats, lifted files, counts)`` for the pack's joined on-ground
    ``.agp`` rows standing on ``surface`` (the built mesh; ``surface.roles``
    names the graded faces)."""
    members = candidates(dump, pack_root) if members is None else list(members)
    graded = _graded(members, surface)
    # a pair of members that both stand on graded ground moves nothing:
    # its floors are never read
    steps = joins(members, lambda i, j: not (graded[i] and graded[j]))
    seats: list[AgpSeat] = []
    files: dict[str, _AgpFileOut] = {}
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
            m = members[k]
            if k == gov or m.agp.other or graded[k]:
                continue
            p = _ap.ground_point(m.agp, m.lon, m.lat, m.heading_deg)
            z = surface(p[1], p[0])
            if z is None:
                continue
            lift = round(need[k] - float(z), 2)
            if abs(lift) < LIFT_TOL_M:
                continue
            res = _variant_resource(m.resource, m.text, lift)
            if res not in files:
                note = (f"{CUT_MARK}{m.resource}: lifted {lift:+.2f} m to meet "
                        f"{gm.resource} at its connector floor (#2090)")
                files[res] = _AgpFileOut(res, _ap.lifted_text(m.text, lift, note))
            seats.append(AgpSeat(m.index, m.resource, res, lift, gm.index,
                                 p[0], p[1], round(float(z), 3), round(need[k], 3)))
    counts = {"agp_rows": len(members), "agp_joins": len(steps),
              "agp_groups": len(groups), "agp_lifted": len(seats),
              "agp_lift_max_m": max((abs(s.lift_m) for s in seats), default=0.0)}
    return tuple(seats), tuple(files.values()), counts
