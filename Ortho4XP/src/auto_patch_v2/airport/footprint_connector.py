"""§16g (6) A CONNECTOR JOINS TWO UNITS (owner RULINGS 2026-09-13cn;
spec ``object-placement-spec.md`` §16g (6); the owner's own words at 13ce:
cutting is allowed only for "very long connecting pieces like the elevated
rail at HECA").

The §16g footprint unit's ONE exception, lifted out of ``footprint_unit``
for the 1,000-line law.  Three rules and their witness:

1. A CONNECTOR is a body that CONNECTS — span, end-ground step AND a
   TOPOLOGY.  The topology is read by REMOVING the body from its own unit
   and looking at what falls apart (:func:`_connector_ends`): a body that
   chains two groups makes them one unit by existing, so the partition
   WITH it in can never witness the split.  Every contact into ONE
   component means MEMBER, however long the body is — SPJC's 549 m
   access-road viaduct is the terminal's.
2. An identified connector is SEATED on its HIGH end's datum by the
   caller, ``footprint_unit.plan_wide_seats``, which is where the datums
   are; it never falls to §16c's low-side foot.
3. PROVENANCE IS A WITNESS: the shared-datum pack's own DSF row groups the
   placements it authored together (:func:`authored_units`), and a
   partition separating two siblings raises ``unit_split_authored``.

Nothing here reads a design surface or mutates a candidate: it answers
"what is this body, and between what" and hands the answer back.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from . import anchor_rule as _ar
from . import placement_boxes as _pb
from .placement_family import _clusters

__all__ = ["PlanConnector", "CONNECTOR_BOXES_MAX", "_span_m",
           "_is_connector", "_connector_ends", "authored_units",
           "authored_unit_census"]


def _span_m(boxes: _t.Sequence[tuple[float, float, float, float]]) -> float:
    """The plan DIAGONAL of a body's footprint, metres (§16g (3))."""
    h = _pb.hull_of(boxes)
    if h is None:
        return 0.0
    ml, mo = _ar._m_per_deg(0.5 * (h[0] + h[2]))
    return (((h[2] - h[0]) * ml) ** 2 + ((h[3] - h[1]) * mo) ** 2) ** 0.5


def _is_connector(c: _t.Any, cc: _t.Sequence[tuple[float, float, float, float]],
                  span_m: float, visual_m: float,
                  ends: "tuple[str, str] | None" = None) -> bool:
    """§16g (6) A CONNECTOR JOINS TWO UNITS (owner RULINGS 2026-09-13cn,
    on the owner's 13ce words: cutting is allowed only for "very long
    connecting pieces like the elevated rail at HECA").

    THREE tests, all of them: a footprint span of at least ``span_m``, two
    ends whose GROUND differs by at least ``visual_m``, AND — the test
    13cn adds — a TOPOLOGY: the body's two ends touch two DIFFERENT
    plan-wide footprint units, or one unit and open ground beyond
    ``span_m`` of it.  ``ends`` is that verdict, read off the plan-wide
    partition by :func:`_connector_ends` (``("", "")`` where the partition
    says nothing); ``None`` means no partition was available and the
    topology cannot be asserted, which is NOT a connector.

    "Long and sloping" alone identifies nothing.  A body whose every
    contact chains into ONE unit is a MEMBER of that unit however long it
    is and however much the ground under it varies — the SPJC access-road
    viaduct ``SPJC_LIMANUEVA_xp11_007__b0`` (span 549 m, end-ground spread
    11.58 m) is the terminal's, and the rule that exists for a kilometre
    of elevated rail threw it out to §16c's low-side foot 7.81 m above the
    unit datum (13cn).

    The ends are the two contacts furthest apart in plan, read on the
    hull's long axis — the cheap reading of "its two ends", and the one
    the span itself is measured on."""
    if span_m <= 0.0 or visual_m <= 0.0 or len(cc) < 2:
        return False
    if ends is None or ends[0] == ends[1]:
        return False
    boxes = list(c.part_boxes) or ([c.box] if c.box else [])
    if _span_m(boxes) < span_m:
        return False
    h = _pb.hull_of(boxes)
    if h is None:
        return False
    along_lat = (h[2] - h[0]) >= (h[3] - h[1])
    key = (lambda q: q[0]) if along_lat else (lambda q: q[1])
    lo = min(cc, key=key)
    hi = max(cc, key=key)
    return abs((lo[3] - lo[2]) - (hi[3] - hi[2])) >= visual_m

@_dc.dataclass(frozen=True)
class PlanConnector:
    """§16g (6): a body that CONNECTS two footprint units.

    ``end_a`` / ``end_b`` are the two ends' UNITS in plan order along the
    hull's long axis — the components its own unit ``unit`` would fall
    into without it, named ``<unit>/cN``; an empty side is OPEN GROUND (no
    body of the unit within ``connector_span_m`` of that end).  ``boxes_a``
    / ``boxes_b`` are those components' plan boxes, which is what the two
    ends' DATUMS are read on.  Which end the piece is SEATED on is the
    HIGH one, and that is a datum reading — made in
    :func:`plan_wide_seats`, where the datums exist."""

    id: str
    key: tuple[int, int, int]
    pids: frozenset[int]
    resource: str
    span_m: float
    unit: str
    end_a: str
    end_b: str
    boxes_a: tuple[tuple[float, float, float, float], ...] = ()
    boxes_b: tuple[tuple[float, float, float, float], ...] = ()
    #: the ``(unit, member, body)`` keys of each end component — what the
    #: DECK branch of :func:`plan_unit_datums` reads the datum off
    keys_a: tuple[tuple[int, int, int], ...] = ()
    keys_b: tuple[tuple[int, int, int], ...] = ()


#: §16g (6): how many of a body's part boxes the end-topology test reads.
#: A clutter member carries thousands, and the question — "does this END
#: touch that unit" — is answered by a sample of the extremes.
CONNECTOR_BOXES_MAX = 256


def _thin(boxes: _t.Sequence[_t.Any], cap: int) -> list:
    step = max(1, len(boxes) // cap)
    return list(boxes[::step])


def _axis_of(h: tuple[float, float, float, float]):
    """The hull's LONG axis as a box -> position function (§16g (6): "its
    two ends", read on the axis the span is measured on)."""
    if (h[2] - h[0]) >= (h[3] - h[1]):
        return lambda b: 0.5 * (b[0] + b[2])
    return lambda b: 0.5 * (b[1] + b[3])


def _components(idxs: _t.Sequence[int], shims: _t.Sequence[_PShim],
                touch_m: float) -> list[list[int]]:
    """``idxs`` split into CONNECTED COMPONENTS at ``touch_m`` — the same
    :func:`_clusters` derivation, with the singletons it drops put back
    (a component of one body is still a component)."""
    if not idxs:
        return []
    sub = [shims[j] for j in idxs]
    cl, _adj = ([], {}) if len(sub) < 2 else _clusters(sub, touch_m,
                                                       min_members=1)
    out = [[idxs[k] for k in c] for c in cl]
    seen = {j for g in out for j in g}
    out.extend([j] for j in idxs if j not in seen)
    return out


def _touches(i: int, group: _t.Sequence[int], shims: _t.Sequence[_PShim],
             touch_m: float, pos) -> "tuple[float, float] | None":
    """Where along ``i``'s long axis does it touch ``group``?  ``(lowest,
    highest)`` axis position of ITS OWN boxes that meet the group, or
    ``None``."""
    mine = _thin(shims[i].part_boxes, CONNECTOR_BOXES_MAX)
    lo = hi = None
    for j in group:
        s = shims[j]
        if s.box is None or _pb.box_gap_m(shims[i].box, s.box) > touch_m:
            continue
        theirs = _thin(s.part_boxes, CONNECTOR_BOXES_MAX)
        for b in mine:
            if any(_pb.box_gap_m(b, y) <= touch_m for y in theirs):
                p = pos(b)
                lo = p if lo is None or p < lo else lo
                hi = p if hi is None or p > hi else hi
    return None if lo is None else (lo, hi)


def _connector_ends(i: int, cl: _t.Sequence[int], uid: str,
                    shims: _t.Sequence[_PShim], touch_m: float,
                    span_m: float, in_a_unit: _t.Sequence[int]
                    ) -> "PlanConnector | None":
    """§16g (6) (1): is body ``i`` of unit ``cl`` a CONNECTOR, and between
    what?  See :func:`plan_units_and_connectors` for the three cases."""
    h = shims[i].box
    if h is None:
        return None
    pos = _axis_of(h)
    rest = [j for j in cl if j != i]
    comps = _components(rest, shims, touch_m)
    hit = []
    for k, g in enumerate(comps):
        t = _touches(i, g, shims, touch_m, pos)
        if t is not None:
            hit.append((t[0], t[1], k, g))
    if not hit:
        return None
    def _made(a: str, b: str) -> PlanConnector:
        return PlanConnector(
            id=f"cn:{shims[i].key[0]}:{i}", key=shims[i].key,
            pids=shims[i].pids, resource=shims[i].resource,
            span_m=_span_m(shims[i].part_boxes), unit=uid,
            end_a=a, end_b=b,
            boxes_a=(() if not a else
                     tuple(x for j in _by[a] for x in shims[j].part_boxes)),
            boxes_b=(() if not b else
                     tuple(x for j in _by[b] for x in shims[j].part_boxes)),
            keys_a=(() if not a else tuple(shims[j].key for j in _by[a])),
            keys_b=(() if not b else tuple(shims[j].key for j in _by[b])))
    _by = {f"{uid}/c{k}": g for _lo, _hi, k, g in hit}
    if len(hit) >= 2:
        a = min(hit, key=lambda q: q[0])
        b = max((q for q in hit if q[2] != a[2]), key=lambda q: q[1])
        ia, ib = f"{uid}/c{a[2]}", f"{uid}/c{b[2]}"
        return _made(ia, ib) if a[0] <= b[1] else _made(ib, ia)
    # ONE component: is the other end free, and free of every unit body?
    lo, hi, k, _g = hit[0]
    mine = _thin(shims[i].part_boxes, CONNECTOR_BOXES_MAX)
    a0 = min(pos(b) for b in mine)
    a1 = max(pos(b) for b in mine)
    free_low = (lo - a0) >= (a1 - hi)
    end = min(mine, key=pos) if free_low else max(mine, key=pos)
    near = min((_pb.box_gap_m(end, shims[j].box) for j in in_a_unit
                if j != i and shims[j].box is not None),
               default=float("inf"))
    if near <= span_m:
        return None
    u = f"{uid}/c{k}"
    return _made("", u) if free_low else _made(u, "")

# ── §16g (6) (3) PROVENANCE IS A WITNESS ─────────────────────────────────

def authored_units(plan: _t.Any) -> dict[tuple[int, int], str]:
    """§16g (6) (3): the SHARED-DATUM PACK groups — ``(unit index, member
    index) -> authored unit id``.

    The pack's own row is the witness: placements written at ONE DSF
    origin (lat, lon to 1e-7) and ONE heading are one authored unit, which
    is how a shared-datum pack says "these eleven pieces are one
    building".  SPJC's eleven ``LIMANUEVA`` rows are one such group and
    §16g (3) threw two of them out of the unit the other nine formed
    (13cn) — this is the measurement that would have named that at plan
    time.

    It is a WITNESS, never a rule: nothing here moves a body."""
    key_of: dict[tuple[float, float, float], str] = {}
    out: dict[tuple[int, int], str] = {}
    rows: list[tuple[tuple[float, float, float], tuple[int, int]]] = []
    for ui, u in enumerate(getattr(plan, "units", ()) or ()):
        ll = getattr(u, "anchor", None) or (0.0, 0.0)
        la, lo = (float(ll[0]), float(ll[1]))
        for mi, m in enumerate(u.members):
            rows.append(((round(la, 7), round(lo, 7),
                          round(float(getattr(m, "heading_deg", 0.0)),
                                4)), (ui, mi)))
    for i, k in enumerate(sorted({k for k, _v in rows})):
        key_of[k] = f"au:{i}"
    for k, v in rows:
        out[v] = key_of[k]
    return out


def authored_unit_census(plan: _t.Any, pid_units: _t.Mapping[int, tuple]
                         ) -> dict[str, int]:
    """§16g (6) (3): does the footprint partition SEPARATE two siblings of
    one authored unit?  ``unit_split_authored`` is the cockpit's WARN —
    the count of shared-datum-pack groups whose bodies landed in more than
    one plan-wide footprint unit."""
    au = authored_units(plan)
    seen: dict[str, set[str]] = {}
    for ui, u in enumerate(getattr(plan, "units", ()) or ()):
        for mi, m in enumerate(u.members):
            a = au.get((ui, mi))
            if a is None:
                continue
            for p in m.parts:
                row = pid_units.get(p.pid)
                if row is not None:
                    seen.setdefault(a, set()).add(str(row[0]))
    return {"authored_units": len(set(au.values())),
            "authored_units_in_a_unit": len(seen),
            "unit_split_authored": sum(1 for v in seen.values()
                                       if len(v) > 1)}

