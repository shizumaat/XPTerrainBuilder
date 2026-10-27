"""ONE ZERO PER CONNECTED GROUP (owner RULINGS 2026-10-22c/f, 2026-10-22o;
#1214 round 3, R5).

Owner, 2026-10-23T01:10:51Z (22o): "connected objects stay as one group,
even if parts end up under ground ... we only split and seat separately,
objects that are clearly at least a couple meters apart with no above
ground connecting shape, so bridges, road decks, etc. that touch or even
come within a meter of a building must always move together with that
building."

Two passes, both applied to one placement's record after its bodies are
formed and before the lift and the cut:

* :func:`rigid_open` — an OPEN frame (every member a deck or a deck
  candidate: a bridge, a canopy) takes ONE zero per placement: the deck
  datum where a body carries it, else the lowest (10-22c: no support
  floats).  Moved out of ``placement_plan``.
* :func:`group_zero` — every body whose parts belong to one CONNECTED SET
  (a §16g footprint unit's ROOT: the pad-level and block passes cut one
  connected unit into pieces, ``fu:16:6938/p2/b1``, and 22o puts the
  pieces back together) takes that set's one zero — basin rims, line
  segments, viaduct spans, decks, garage connectors alike; no per-pass
  datum for a group member.  The set's zero is the median of its pieces'
  zeros over its parts (:func:`root_zeros`).  The §16g chain is the
  "touch or within a metre" relation (``[placement] touch_m``); a body
  none of whose parts is chained keeps its own seat.

Each re-anchored body's file is renamed for what it now bakes (R1,
``placement_file.named_body``).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["OPEN_KINDS", "rigid_open", "open_zero", "frame_zero", "unit_root",
           "group_key", "root_zeros", "body_root",
           "frame_root_boxes", "merge_frame_roots", "unchained_links", "group_zero",
           "GROUP_REASON",
           "TOUCH_M"]

#: the deck verdicts that make a member an OPEN structure — a deck
#: (``flag`` / ``signature``) or a plate the signature pass could not prove
#: spans anything (``candidate``: a bridge with no mapped way, a canopy)
OPEN_KINDS = frozenset({"flag", "signature", "candidate"})

#: the reason prefix :func:`group_zero` writes
GROUP_REASON = "one connected group"


def rigid_open(record: _t.Any, m: _t.Any, open_frame: bool) -> _t.Any:
    """Owner RULINGS 2026-10-22c (#1214): "prioritize the canopy or bridge
    deck, and that the pillars or supports stay attached, then seating the
    whole unit so no pillars are floating" — and 10-22f: "they should
    always move as a group".  Every body of a placement in an OPEN frame
    takes ONE zero: the deck's datum where a body carries it, else the
    LOWEST of the bodies' own zeros, so no support floats.  A body whose
    seat tilt is baked into its vertices leaves the placement as it was."""
    bodies = record.bodies
    if not open_frame or len(bodies) < 2:
        return record
    if any(getattr(b.seat, "applied", False) for b in bodies if b.seat is not None):
        return record
    zs = [float(b.anchor.surface_z) - float(b.anchor.y_zero) for b in bodies
          if b.anchor.surface_z is not None]
    if len(zs) < 2 or max(zs) - min(zs) <= 0.05:
        return record
    target = open_zero(bodies)
    return _at_zero(record, m, target, lambda b: True,
                    f"one rigid open structure at {target:.2f} (RULINGS 2026-10-22c)")


def open_zero(bodies: _t.Sequence[_t.Any]) -> "float | None":
    """10-22c's one zero of an open structure's bodies: the deck's datum
    where a body carries it, else the LOWEST of their own zeros (no support
    floats); ``None`` with no seated body."""
    zs = [(float(b.anchor.surface_z) - float(b.anchor.y_zero), b) for b in bodies
          if b.anchor.surface_z is not None]
    if not zs:
        return None
    dat = [z for z, b in zs if b.anchor.datum]
    return dat[0] if dat else min(z for z, _b in zs)


def frame_zero(record: _t.Any, m: _t.Any, target: float, why: str) -> _t.Any:
    """Every seated body of ``record`` not already at ``target`` re-anchored
    to it (10-22c/f: a bridge's frame moves as one), its file renamed."""
    return _at_zero(record, m, target,
                    lambda b: abs(float(b.anchor.surface_z) - float(b.anchor.y_zero)
                                  - target) > 1e-6, why)


def _at_zero(record: _t.Any, m: _t.Any, target: float,
             take: _t.Callable[[_t.Any], bool], why: str) -> _t.Any:
    from .placement_file import named_body
    out = []
    for b in record.bodies:
        a = b.anchor
        if a.surface_z is None or not take(b):
            out.append(b)
            continue
        y0 = float(a.surface_z) - target
        off = tuple(a.offset)
        a2 = _dc.replace(a, y_zero=y0, offset=(off[0], y0, off[2]),
                         reason=f"{why}; was: {a.reason}")
        out.append(named_body(m, b, anchor=a2))
    return _dc.replace(record, bodies=tuple(out))


def unit_root(uid: str) -> str:
    """The id of the connected unit a pad-level or block piece was cut
    from (``fu:16:6938/p2/b1`` -> ``fu:16:6938``; a seat's family spelling
    ``fu:16:6938/p2/b1@viaduct`` reads the same)."""
    return str(uid).split("/", 1)[0].split("@", 1)[0]


def group_key(root: str, frame: str) -> str:
    """The key of ONE frame's share of a connected unit (#1214 round 4):
    a connected unit chains several frames — separate authored objects,
    each placed by its author on HIS ground — and each frame takes its own
    zero in it; the terminal's pieces move as one, the tower beside it
    keeps its own ground (KMCI 1.0.418: the tower stood 3.5-4.4 m up on
    the terminal's plane)."""
    return f"{root}|{frame}"


def root_zeros(plan_wide: _t.Mapping[int, tuple], plan: _t.Any = None,
               surface: _t.Any = None, counts: "dict | None" = None,
               airside_out: "dict[str, tuple[float, int]] | None" = None
               ) -> dict[str, tuple[float, float]]:
    """:func:`group_key` ``-> (zero, the frame's lift)`` for every frame's
    share of every connected unit (``frame`` is the plan unit id; "" with
    no ``plan``), the zero being:

    * where the share TOUCHES AIRSIDE PAVEMENT (owner RULINGS 2026-10-22q),
      the airside floor — ``airside_group_seat.airside_zeros`` (needs
      ``plan`` and a ``surface`` carrying ``roles``);
    * else, for a frame chained into another frame's unit, its OWN GROUND
      (the low-side plane of ``ground - y`` over its feet,
      ``airside_group_seat.ground_plane``: the plan-wide datum is
      spelled in the unit's dominant frame, and put a tower beside KMCI's
      terminal 3.5-4.4 m up);
    * else the median of the plan-wide unit zeros
      (``footprint_seats.plan_wide_seats``: part id -> (unit, zero, ...))
      over its parts — round 3's reading, which for a unit touching
      airside let a central block over a road trench outvote the halls on
      the apron (LFPG T2, 1.0.418)."""
    frame_of: dict[int, tuple[str, float]] = {}
    if plan is not None:
        frame_of = {p.pid: (str(u.id), float(getattr(u, "agl_m", 0.0) or 0.0))
                    for u in plan.units for m in u.members for p in m.parts}
    acc: dict[str, list[float]] = {}
    lift: dict[str, float] = {}
    size: dict[str, dict[str, int]] = {}
    for pid, seat in plan_wide.items():
        if not seat or seat[1] is None or not seat[0]:
            continue
        fid, lf = frame_of.get(pid, ("", 0.0))
        r = unit_root(seat[0])
        k = group_key(r, fid)
        acc.setdefault(k, []).append(float(seat[1]))
        lift[k] = lf
        size.setdefault(r, {})[fid] = size.setdefault(r, {}).get(fid, 0) + 1
    # the unit's DOMINANT frame (most parts): the plan-wide datum is
    # spelled in it; another frame chained in is another authored object
    dominant = {r: max(sorted(n), key=lambda f: n[f]) for r, n in size.items()}
    out = {}
    for k, zs in acc.items():
        zs.sort()
        out[k] = (zs[len(zs) // 2], lift[k])
    if plan is not None and surface is not None:
        from .airside_group_seat import airside_zeros
        own: dict[str, float] = {}
        az = airside_zeros(plan, plan_wide, surface,
                           lambda unit, fid: group_key(unit_root(unit), fid), own)
        for k in list(out):
            r, fid = k.rsplit("|", 1)
            if k in az:
                out[k] = (az[k][0], out[k][1])
            elif fid != dominant.get(r) and k in own:
                # a chained frame touching no airside stands on its own
                # ground (KMCI's tower beside the terminal)
                out[k] = (own[k], out[k][1])
        if counts is not None:
            counts["groups_on_airside"] = len(az)
        if airside_out is not None:
            # the keys seated on the airside floor with their stand-side
            # feet (``unchained_links``' precedence, owner RULINGS
            # 2026-10-23e: airside wins)
            airside_out.update(az)
    return out


#: 22o: "bridges, road decks, etc. that touch or even come within a meter of
#: a building must always move together with that building"
TOUCH_M = 1.0


def frame_root_boxes(u: _t.Any, plan_wide: _t.Mapping[int, tuple]
                     ) -> dict[str, list[tuple]]:
    """``root -> the plan boxes of its parts`` in ONE frame (plan unit
    ``u``) — what an unchained body of the frame is measured against."""
    out: dict[str, list[tuple]] = {}
    for m in getattr(u, "members", ()) or ():
        for p in getattr(m, "parts", ()) or ():
            seat = plan_wide.get(p.pid)
            if seat and seat[0] and getattr(p, "box", None):
                out.setdefault(unit_root(seat[0]), []).append(tuple(p.box))
    return out


def merge_frame_roots(root_boxes: _t.Mapping[str, _t.Sequence[tuple]],
                      parts: "_t.Mapping[str, int] | None" = None
                      ) -> dict[str, str]:
    """``root -> the root it moves with`` inside ONE frame: connected units
    whose parts touch or come within :data:`TOUCH_M` of each other are one
    group (22o: a thin deck or a viaduct links two halls even where the
    §16g chain, which never links through a thin body, keeps them apart);
    each group moves with its largest unit (``parts``: parts per root, else
    the box count)."""
    roots = sorted(root_boxes)
    size = {r: (parts or {}).get(r, len(root_boxes[r])) for r in roots}
    up = {r: r for r in roots}

    def find(r: str) -> str:
        while up[r] != r:
            up[r] = up[up[r]]
            r = up[r]
        return r
    hull = {r: _hull(root_boxes[r]) for r in roots}
    for i, a in enumerate(roots):
        for b in roots[i + 1:]:
            if find(a) == find(b) or _gap_m(hull[a], [hull[b]]) > TOUCH_M:
                continue
            small, big = sorted((a, b), key=lambda r: len(root_boxes[r]))
            if any(_gap_m(q, root_boxes[big]) <= TOUCH_M for q in root_boxes[small]):
                ra, rb = find(a), find(b)
                keep, drop = sorted((ra, rb), key=lambda r: (-size[r], r))
                up[drop] = keep
    return {r: find(r) for r in roots}


def unchained_links(u: _t.Any, plan_wide: _t.Mapping[int, tuple],
                    merged: "_t.Mapping[str, str] | None" = None,
                    airside: "_t.Mapping[str, tuple] | _t.AbstractSet[str]" = frozenset(),
                    counts: "dict | None" = None) -> dict[str, str]:
    """``root -> the root it moves with`` inside ONE frame (plan unit
    ``u``), read THROUGH ITS UNCHAINED PARTS (#1214 round 6; 22o: pieces
    that "touch or even come within a meter of a building must always move
    together with that building"): the frame's parts are a graph, two parts
    joined where their footprint RINGS come within :data:`TOUCH_M` and one
    of them is UNCHAINED (a thin deck, a railing, a road surface: no §16g
    unit holds it); the units a component holds are one group.  Rings,
    never plan boxes: the boxes of an unlifted shared-datum frame overlap
    neighbours 20 m away.

    AIRSIDE WINS (owner RULINGS 2026-10-23e): the group moves with its
    AIRSIDE-SEATED unit (``airside``: the :func:`group_key` s
    ``airside_group_seat.airside_zeros`` seated, with their ``(zero, feet
    read)``) and the groundside units take its zero; with none, with its
    largest unit.  A component holding SEVERAL airside-seated units moves
    with the one whose floor the MOST stand-side feet read, and every other
    share, airside and groundside alike, takes its zero (counted,
    ``unchained_airside_joined``): LFPG T2 (1.0.424) kept its halls and its
    trench block apart as six roots, the group floating where the trench
    block's floor won.  ``merged`` (``merge_frame_roots``' answer) is
    composed in."""
    import math

    from shapely.geometry import Polygon
    from shapely.strtree import STRtree
    la0, lo0 = (float(q) for q in u.anchor)
    ml, mo = 111132.0, 111320.0 * math.cos(math.radians(la0))
    fid = str(getattr(u, "id", ""))
    base = dict(merged or {})
    geoms, owner = [], []
    size: dict[str, int] = {}
    for m in getattr(u, "members", ()) or ():
        for p in getattr(m, "parts", ()) or ():
            seat = plan_wide.get(p.pid)
            r = unit_root(seat[0]) if seat and seat[0] else None
            if r is not None:
                r = base.get(r, r)
                size[r] = size.get(r, 0) + 1
            for rg in getattr(p, "rings", ()) or ():
                if len(rg) < 3:
                    continue
                g = Polygon([((lo - lo0) * mo, (la - la0) * ml) for la, lo in rg])
                if not g.is_valid:
                    g = g.buffer(0.0)
                if not g.is_empty:
                    geoms.append(g)
                    owner.append(r)
    if len(size) < 2 or not geoms:
        return base
    up = list(range(len(geoms)))

    def find(i: int) -> int:
        while up[i] != i:
            up[i] = up[up[i]]
            i = up[i]
        return i
    a, b = STRtree(geoms).query(geoms, predicate="dwithin", distance=TOUCH_M)
    for i, j in zip(a.tolist(), b.tolist(), strict=True):
        if i < j and (owner[i] is None or owner[j] is None):
            ri, rj = find(i), find(j)
            if ri != rj:
                up[ri] = rj
    comp: dict[int, set[str]] = {}
    for i, r in enumerate(owner):
        if r is not None:
            comp.setdefault(find(i), set()).add(r)
    out = dict(base)
    n_joined = 0
    for rs in comp.values():
        if len(rs) < 2:
            continue
        air = sorted(r for r in rs if group_key(r, fid) in airside)
        n_joined += len(air) > 1
        keep = (max(air, key=lambda r: _feet_read(airside, group_key(r, fid))) if air
                else max(sorted(rs), key=lambda r: size.get(r, 0)))
        for r in rs:
            if r != keep:
                out[r] = keep
    for r in list(out):
        t, seen = out[r], {r}
        while t in out and t not in seen:
            seen.add(t)
            t = out[t]
        out[r] = t
    if counts is not None and n_joined:
        k = "unchained_airside_joined"
        counts[k] = counts.get(k, 0) + n_joined
    return out


def _feet_read(airside: _t.Any, key: str) -> int:
    """The stand-side feet ``airside_zeros`` read for ``key`` (0 for a
    bare key set): the witness that picks a group's one airside zero."""
    v = airside.get(key) if hasattr(airside, "get") else None
    return int(v[1]) if isinstance(v, tuple) and len(v) > 1 else 0


def _hull(boxes: _t.Sequence[tuple]) -> tuple:
    return (min(q[0] for q in boxes), min(q[1] for q in boxes),
            max(q[2] for q in boxes), max(q[3] for q in boxes))


def body_root(b: _t.Any, plan_wide: _t.Mapping[int, tuple],
              file_root: "_t.Mapping[str, str] | None" = None,
              root_boxes: "_t.Mapping[str, _t.Sequence[tuple]] | None" = None
              ) -> "str | None":
    """The connected unit the body's seat already names (its anchor's
    ``family``, a §16g unit — its own, or its carrier's), else the one most
    of its parts belong to; for a body none of whose parts is chained,
    its CARRIER's (``merged_into``, through
    ``file_root``: the written file -> its unit, filled as the carriers are
    written), else the unit of its own frame whose parts its plan box
    touches or comes within :data:`TOUCH_M` of (``root_boxes``,
    :func:`frame_root_boxes`; the nearest)."""
    fam = str(getattr(getattr(b, "anchor", None), "family", "") or "")
    if fam.startswith("fu:"):
        # seated by a unit already (its own, or its carrier's): that unit
        return unit_root(fam)
    n: dict[str, int] = {}
    for pid in getattr(b, "pids", ()) or ():
        seat = plan_wide.get(pid)
        if seat and seat[0]:
            r = unit_root(seat[0])
            n[r] = n.get(r, 0) + 1
    if n:
        return max(sorted(n), key=lambda r: n[r])
    carrier = getattr(b, "merged_into", "") or ""
    if carrier and file_root and carrier in file_root:
        return file_root[carrier]
    box = getattr(b, "plan_box", None) or getattr(b, "geom_box", None)
    if box and root_boxes:
        best = None
        for r in sorted(root_boxes):
            g = _gap_m(tuple(box), root_boxes[r])
            if g is not None and g <= TOUCH_M and (best is None or g < best[0]):
                best = (g, r)
        if best is not None:
            return best[1]
    return None


def _gap_m(box: tuple, boxes: _t.Any) -> "float | None":
    """The least plan gap in metres between ``box`` and any of ``boxes``
    (``placement_boxes.box_gap_m``'s reading, over an array at once)."""
    import numpy as np

    from . import anchor_rule as _ar
    q = np.asarray(boxes, dtype=float).reshape(-1, 4)
    if not len(q):
        return None
    ml, mo = _ar._m_per_deg(0.5 * (box[0] + box[2]))
    dla = np.maximum(0.0, np.maximum(box[0] - q[:, 2], q[:, 0] - box[2])) * ml
    dlo = np.maximum(0.0, np.maximum(box[1] - q[:, 3], q[:, 1] - box[3])) * mo
    return float(np.sqrt(dla * dla + dlo * dlo).min())


def group_zero(record: _t.Any, m: _t.Any, plan_wide: _t.Mapping[int, tuple],
               zeros: _t.Mapping[str, tuple[float, float]], counts: dict,
               frame: str = "", tol_m: float = 0.05,
               file_root: "_t.Mapping[str, str] | None" = None,
               root_boxes: "_t.Mapping[str, _t.Sequence[tuple]] | None" = None,
               merged: "_t.Mapping[str, str] | None" = None) -> _t.Any:
    """R5 / 22o: every body of ``record`` (a placement of frame ``frame``,
    the plan unit id) whose parts belong to a connected unit takes the ONE
    zero of that frame's share of it (:func:`root_zeros`), whatever pass
    seated it.  A body carried by one of the unit's files takes it too
    (:func:`body_root`).  A body already within ``tol_m`` of its target is
    left as it is."""
    if not plan_wide or not zeros:
        return record
    roots = {id(b): body_root(b, plan_wide, file_root, root_boxes)
             for b in record.bodies}
    if merged:
        roots = {k: (merged.get(r, r) if r else r) for k, r in roots.items()}

    def target(r: str) -> "float | None":
        z = zeros.get(group_key(r, frame))
        return None if z is None else z[0]

    def off(b: _t.Any) -> bool:
        r = roots.get(id(b))
        if r is None or b.anchor.surface_z is None:
            return False
        t = target(r)
        if t is None:
            return False
        z = float(b.anchor.surface_z) - float(b.anchor.y_zero)
        return abs(z - t) > tol_m

    moved = [b for b in record.bodies if off(b)]
    if not moved:
        return record
    counts["group_zero_bodies"] = counts.get("group_zero_bodies", 0) + len(moved)
    out = record
    for r in sorted({roots[id(b)] for b in moved}):
        t = target(r)
        out = _at_zero(out, m, t,
                       lambda b, _r=r: roots.get(id(b)) == _r and off(b),
                       f"{GROUP_REASON} {r} at {t:.2f} (RULINGS 2026-10-22o/q)")
    return out
