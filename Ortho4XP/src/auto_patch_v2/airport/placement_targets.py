"""A BODY THE CARRIER SEARCH LEFT BARE RIDES WHAT IT IS WELDED TO (issue
#127; spec ``object-placement-spec.md`` flat-pad §7).

:func:`welded_carriers` reads the weld off the plan's PART contacts;
:func:`weld_own_ground` reads it off the AUTHORED GEOMETRY of one
placement's pieces, for the pieces that hold no part (#1146, lane lseat,
``docs/findings/seating-lseat.md`` §2).  The carrier question itself
(``_footless_targets``) and what its answer cuts (``_carrier_pieces``) are
``placement_body``'s — ONE implementation; the second copy that lived here
was unreachable and is deleted (lane ``v2trim``, RULINGS 2026-10-04c (2)).

NO LAW CONSTANT LIVES HERE.
"""
from __future__ import annotations

import typing as _t

from . import placement_carrier as _pc

__all__ = ["welded_carriers", "weld_own_ground", "pieces_touch"]


def welded_carriers(targets: _t.Sequence[_t.AbstractSet[int]],
                    carrier_of: _t.Mapping[int, _pc.Candidate],
                    contacts: _t.Iterable[tuple[int, int]],
                    ) -> dict[int, tuple[_pc.Candidate, str]]:
    """Issue #127 (flat-pad spec §7): A BODY THE SEARCH LEFT ON ITS OWN
    GROUND RIDES WHAT IT IS WELDED TO.

    §15's search offers only FOOTED candidates, so a footless facade
    whose one weld is to a body that is itself CARRIED (HECA T3: the
    ``glass_blue_2`` panes welded to ``T2_Brick`` b4, which rests on
    ``door`` b27) found nothing it may stand on and fell to §16 (3)'s
    own ground — the design surface under its own footprint, 1.1-1.4 m
    over the zero its wall was written at, a seam the eye reads across a
    2 mm weld.  The weld is the stronger evidence: the pack authored the
    two parts touching, so they share ONE carrier.

    ``targets`` are the part-id sets of the bodies with no carrier;
    ``carrier_of`` maps every part id already placed to the candidate its
    body is written on (a footed body's own pids to itself, a carried
    body's to its carrier); ``contacts`` is the unit's ε-contact graph
    (welds only, never abutments).  A target takes the carrier holding
    the MOST of its welds (ties: the carrier with the most feet, then
    member, then group).  The walk is breadth-first in ROUNDS read from
    a snapshot, so two facades welded to each other share the carrier of
    whichever reaches a placed body first, and the answer never depends
    on the order the targets are listed.  Targets welded to nothing
    placed are absent from the result and keep their own ground.

    ``{target index: (carrier, why)}``."""
    adj: dict[int, set[int]] = {}
    for a, b in contacts:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    placed = dict(carrier_of)
    out: dict[int, tuple[_pc.Candidate, str]] = {}
    hops = 0
    while True:
        hops += 1
        new: dict[int, tuple[_pc.Candidate, str]] = {}
        for ti, pids in enumerate(targets):
            if ti in out:
                continue
            votes: dict[int, list] = {}
            for p in pids:
                for q in adj.get(p, ()):
                    if q in pids:
                        continue
                    c = placed.get(q)
                    if c is None:
                        continue
                    v = votes.setdefault(id(c), [0, c])
                    v[0] += 1
            if not votes:
                continue
            n, c = min(votes.values(),
                       key=lambda v: (-v[0], -v[1].feet, v[1].member,
                                      v[1].group))
            new[ti] = (c, f"welded ({n} part contact(s), hop {hops}) to a "
                          f"body written on it")
        if not new:
            return out
        for ti, (c, _w) in new.items():
            for p in targets[ti]:
                placed.setdefault(p, c)
        out.update(new)


def _body_tris(b: _t.Any, cutter: _t.Any) -> "_t.Any":
    """The piece's authored triangles as an ``(n, 3, 3)`` array — its own
    cut triangles, else its whole components' — or ``None``."""
    import numpy as np
    if cutter is None or not cutter._read():
        return None
    rows = list(b.tris or ())
    if not rows:
        comps = cutter._comps
        tl = [comps[c].tris for c in (b.components or ()) if 0 <= c < len(comps)]
        if not tl:
            return None
        rows = np.concatenate(tl)
    ix = np.asarray(rows, dtype=np.int64).reshape(-1, 3)
    return cutter._geom.vertices[ix][:, :, :3].astype(float)


def _near(pts: "_t.Any", tris: "_t.Any", eps: float, chunk: int = 256) -> bool:
    """Does any point of ``pts`` come within ``eps`` of any of ``tris``
    (exact point-to-triangle distance, ``contact``'s row test)?"""
    import numpy as np

    from .contact import _point_tri_dist2_rows
    lo, hi = tris.reshape(-1, 3).min(axis=0) - eps, tris.reshape(-1, 3).max(axis=0) + eps
    pts = pts[((pts >= lo) & (pts <= hi)).all(axis=1)]
    if not len(pts):
        return False
    tlo, thi = tris.min(axis=1), tris.max(axis=1)
    pts = pts[np.argsort(pts[:, 0])]
    for s in range(0, len(pts), chunk):
        p = pts[s:s + chunk]
        keep = ((tlo <= p.max(axis=0) + eps) & (thi >= p.min(axis=0) - eps)).all(axis=1)
        t = tris[keep]
        if not len(t):
            continue
        pi = np.repeat(np.arange(len(p)), len(t))
        ti = np.tile(np.arange(len(t)), len(p))
        d2 = _point_tri_dist2_rows(p[pi], t[ti, 0], t[ti, 1], t[ti, 2])
        if (d2 <= eps * eps).any():
            return True
    return False


def pieces_touch(ta: "_t.Any", tb: "_t.Any", eps: float) -> bool:
    """Two pieces' authored triangles ``(n, 3, 3)`` TOUCH: a vertex of
    either comes within ``eps`` of a triangle of the other (owner RULINGS
    2026-10-22o: "touch or even come within a meter")."""
    import numpy as np
    a0, a1 = ta.reshape(-1, 3).min(axis=0), ta.reshape(-1, 3).max(axis=0)
    b0, b1 = tb.reshape(-1, 3).min(axis=0), tb.reshape(-1, 3).max(axis=0)
    if (a0 > b1 + eps).any() or (b0 > a1 + eps).any():
        return False
    return (_near(np.unique(ta.reshape(-1, 3), axis=0), tb, eps)
            or _near(np.unique(tb.reshape(-1, 3), axis=0), ta, eps))


def _zero(b: _t.Any) -> "float | None":
    a = b.anchor
    return None if a.surface_z is None else float(a.surface_z) - float(a.y_zero)


def weld_own_ground(record: _t.Any, m: _t.Any, cutter: _t.Any, counts: dict,
                    tol_m: float = 0.05) -> _t.Any:
    """#1146 (owner RULINGS 2026-10-22o on the pieces of ONE placement): an
    OWN-GROUND piece (§16 (3), ``footless_own_ground``) moves with the
    pieces its authored geometry touches within ``open_frame_seat.TOUCH_M``.

    KLAX's elevated rail is one placement whose atoms (§16d (4)) touch face
    to face with no shared vertex — §16c (6) binds by VERTEX — and hold no
    part, so no part weld (:func:`welded_carriers`) or unit chain sees them;
    each asked its own carrier, fell to its own ground, and the rail stood
    in pieces up to 2.5 m apart.  Here the touching own-ground pieces form
    components (transitively); each component takes the zero of the piece
    it touches that the law DID seat (carried, unit-carried, deck, footed —
    the one with the most triangles), else of its own largest piece.  Only
    own-ground pieces move: a carried piece keeps its carrier's zero (a
    material file's pieces on two buildings stay on their buildings)."""
    from .open_frame_seat import TOUCH_M, at_zero
    from .placement_file import OWN_GROUND
    bodies = record.bodies
    own = [i for i, b in enumerate(bodies)
           if str(b.anchor.reason).startswith(OWN_GROUND) and _zero(b) is not None]
    zs = [z for z in (_zero(b) for b in bodies) if z is not None]
    if not own or len(zs) < 2 or max(zs) - min(zs) <= tol_m:
        return record
    tri = {i: _body_tris(b, cutter) for i, b in enumerate(bodies) if _zero(b) is not None}
    tri = {i: t for i, t in tri.items() if t is not None and len(t)}
    own = [i for i in own if i in tri]
    up = {i: i for i in tri}

    def find(i: int) -> int:
        while up[i] != i:
            up[i] = up[up[i]]
            i = up[i]
        return i
    seated: dict[int, list[int]] = {}
    for i in own:
        for j in tri:
            if j == i or (j in own and j < i):
                continue
            if j in own and find(i) == find(j):
                continue
            if not pieces_touch(tri[i], tri[j], TOUCH_M):
                continue
            if j in own:
                up[find(i)] = find(j)
            else:
                seated.setdefault(i, []).append(j)
    comp: dict[int, list[int]] = {}
    for i in own:
        comp.setdefault(find(i), []).append(i)
    target: dict[int, float] = {}
    for mem in comp.values():
        anchors = sorted({j for i in mem for j in seated.get(i, ())})
        pick = max(anchors or mem, key=lambda k: (len(tri[k]), -k))
        if len(mem) < 2 and not anchors:
            continue
        z = _zero(bodies[pick])
        for i in mem:
            if abs(_zero(bodies[i]) - z) > tol_m:
                target[id(bodies[i])] = z
    if not target:
        return record
    counts["own_ground_welded_bodies"] = counts.get("own_ground_welded_bodies", 0) + len(target)
    counts["own_ground_weld_groups"] = counts.get("own_ground_weld_groups", 0) + len(
        {round(z, 3) for z in target.values()})
    out = record
    for z in sorted(set(target.values())):
        out = at_zero(out, m, z, lambda b, _z=z: target.get(id(b)) == _z,
                       f"welded to the pieces it touches at {z:.2f} (#1146, RULINGS 2026-10-22o)")
    return out
