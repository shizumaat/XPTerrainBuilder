"""WHICH FINAL BODIES TOUCH, AND THE GROUPS THEY FORM (spec 2110-R3 §0–§1;
owner RULINGS 2026-11-16k/u, #2110).

Owner, 21:35:15Z (16u): "Touching means from a top down view there's no
visible gap between them, so a roof overhang, shared roof, or connecting
sky bridge connect them and they stay together, but a fence does not join
them."

Read off the FINAL bodies of a split set (every pass has seated them) —
never decided before bodies exist (the l2110b miss: its join ran on §16g
roots before the unit loop).

* A BUILDING is a footed body (``feet``) holding a non-line part at least
  ``walled_m`` (``[placement] chain_min_height_m``) tall; a CONNECTOR a
  footless body (roof, overhang, sky bridge, carried piece); a GROUND ITEM
  any other footed body (vehicle, kerb, slab): never a node, never a vote,
  in a group only through its unit (§1.3 (d)).
* Two bodies of one FRAME (plan unit: one anchor, one datum) TOUCH where a
  non-line part RING of one comes within ``touch_m`` (``[placement]
  touch_gap_m``) of a non-line part ring of the other — and the two
  parts' authored height spans are no more than :data:`VETO_M` apart (a
  truck under a canopy touches nothing).  A part with NO ring is read by
  its plan box, as §16g reads it: a scatter piece carries no ring (spec
  ``pack-read-once-fast-spec.md`` §B.2 (4), ``contact.part_attrs``) and
  is small, so its box is its footprint — LOWS's ``Terminal_LOWS_46`` b1
  is 76 such pieces (spec 2110-R3 B3; the spec's LOWS control population,
  5,354 pairs, is this reading).  A line part (fence,
  wall, barrier) never touches; ``line_segment`` and ``basin`` bodies are
  not nodes.  A pair of two frames is listed, never judged.
* The group graph (§1.3): building ~ building where they touch; a
  connector with an EVIDENCE carrier (``merged_into``, its reason not a
  ``free_column._FALLBACKS`` answer) belongs to its carrier's group, and
  its touches to buildings are edges; a connector with no evidence carrier
  joins the buildings it touches; the bodies of one §16g unit in one frame
  are one group (22o never torn) — the unit most of a body's parts are
  seated in, the unit its own seat names (a §16c (7) bind seats a body in
  its cluster's unit: LOWS ``domiki_lows_20`` b150 / ``_19`` b93) and the
  22o group its seat was set by (``domiki_lows_37`` b152, fu:1:1493).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from .open_frame_seat import unit_root

__all__ = ["Node", "local_metres", "read_nodes", "footprint_areas", "touch_pairs", "groups_of",
           "VETO_M", "BUILDING", "CONNECTOR", "GROUND"]

#: §1.2 VERTICAL VETO: two parts whose authored height spans lie more than
#: this apart do not touch, however close in plan (spec 2110-R3)
VETO_M = 1.0
BUILDING, CONNECTOR, GROUND = "building", "connector", "ground"
#: bodies that are never nodes (§10 segments drape by ruling; a basin's
#: members are the pit's)
_NOT_NODES = ("line_segment", "basin")


@_dc.dataclass
class Node:
    """One final body as the group graph reads it."""

    key: tuple[int, int]            # (record index, body index)
    frame: str                      # plan unit id
    name: str                       # its file (``new_resource``)
    zero: float                     # anchor.surface_z - anchor.y_zero
    kind: str                       # BUILDING / CONNECTOR / GROUND
    unit: str                       # its majority §16g unit root, or ""
    parts: list                     # its non-line parts
    lift: float = 0.0
    carrier: str = ""               # an EVIDENCE carrier's file, or ""
    fallback: str = ""              # a no-evidence carrier's file, or ""
    fixed: str = ""                 # why it is no node (§1.3 FIXED), or ""
    area: float = 0.0               # plan footprint, m2 (buildings)
    family: str = ""                # the unit its SEAT names (anchor.family root)
    grouped: str = ""               # the 22o group it was seated in (its reason)

    def span(self, p: _t.Any) -> tuple[float, float]:
        """A part's authored height span over the frame's one zero."""
        lo = float(p.base_y) + self.lift
        return lo, lo + float(p.height_m)

    def bottom(self) -> float:
        """The authored bottom of its lowest part over its zero."""
        return min(float(p.base_y) for p in self.parts) + self.lift


def local_metres(la0: float, lo0: float
                 ) -> _t.Callable[[float, float], tuple[float, float]]:
    """``(lat, lon) -> (x, y)`` metres about ``(la0, lo0)``."""
    ml, mo = 111132.0, 111320.0 * math.cos(math.radians(la0))
    return lambda la, lo: ((lo - lo0) * mo, (la - la0) * ml)


def _majority_unit(b: _t.Any, plan_wide: _t.Mapping[int, tuple]) -> str:
    n: dict[str, int] = {}
    for pid in getattr(b, "pids", ()) or ():
        seat = plan_wide.get(pid)
        if seat and seat[0]:
            r = unit_root(seat[0])
            n[r] = n.get(r, 0) + 1
    return max(sorted(n), key=lambda r: n[r]) if n else ""


def _grouped(reason: str) -> str:
    """The 22o connected group a body's standing seat names
    (``open_frame_seat.GROUP_REASON`` ``fu:N:M at``), or ""."""
    from .open_frame_seat import GROUP_REASON
    head = reason.split("; was:", 1)[0]
    if not head.startswith(GROUP_REASON + " fu:"):
        return ""
    return unit_root(head[len(GROUP_REASON) + 1:].split(" ", 1)[0])


def _carriers(b: _t.Any) -> tuple[str, str]:
    """``(evidence carrier, no-evidence carrier)`` of a body."""
    from .free_column import _FALLBACKS
    c = str(getattr(b, "merged_into", "") or "")
    if not c:
        return "", ""
    if any(f in str(b.anchor.reason) for f in _FALLBACKS):
        return "", c
    return c, ""


def read_nodes(splits: _t.Sequence[_t.Any], members: _t.Mapping[str, tuple],
               plan_wide: _t.Mapping[int, tuple], walled_m: float) -> list[Node]:
    """Every final body of ``splits`` that can be a node or a follower
    (``members``: placement id -> ``(unit, member)``)."""
    out = []
    for i, rec in enumerate(splits):
        um = members.get(rec.placement_id)
        if um is None:
            continue
        u, m = um
        parts = {p.comp: p for p in m.parts}
        for j, b in enumerate(rec.bodies):
            a = b.anchor
            if a.surface_z is None or b.body_class in _NOT_NODES:
                continue
            ps = [parts[c] for c in b.components if c in parts and not parts[c].line]
            if not ps:
                continue
            kind = (CONNECTOR if not b.feet else
                    BUILDING if any(float(p.height_m) >= walled_m for p in ps) else GROUND)
            ev, fb = _carriers(b)
            fam = str(getattr(a, "family", "") or "")
            out.append(Node((i, j), str(u.id), str(b.new_resource),
                            float(a.surface_z) - float(a.y_zero), kind,
                            _majority_unit(b, plan_wide), ps,
                            float(getattr(b, "lift_m", 0.0) or 0.0), ev, fb,
                            family=unit_root(fam) if fam.startswith("fu:") else "",
                            grouped=_grouped(str(a.reason))))
    return out


def _rings(nodes: _t.Sequence[Node]) -> tuple[list, list, list]:
    """Every node's part rings in metres about one origin (an airport is
    small enough for one), a ring-less part's plan box in its place:
    ``(geoms, owner node, owner part)``."""
    from shapely.geometry import Polygon
    from shapely.geometry import box as _box
    geoms: list = []
    owner: list[int] = []
    part: list = []
    if not nodes:
        return geoms, owner, part
    p0 = nodes[0].parts[0]
    xy = local_metres(float(p0.lat), float(p0.lon))
    for ni, n in enumerate(nodes):
        for p in n.parts:
            gs = [Polygon([xy(la, lo) for la, lo in rg]) for rg in p.rings or ()
                  if len(rg) >= 3]
            if not gs:
                (x0, y0), (x1, y1) = xy(p.box[0], p.box[1]), xy(p.box[2], p.box[3])
                gs = [_box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))]
            for g in gs:
                g = g if g.is_valid else g.buffer(0.0)
                if not g.is_empty:
                    geoms.append(g)
                    owner.append(ni)
                    part.append(p)
    return geoms, owner, part


def footprint_areas(nodes: _t.Sequence[Node]) -> None:
    """Each BUILDING's plan footprint (the union of its part rings), m2."""
    from shapely.ops import unary_union
    geoms, owner, _p = _rings(nodes)
    by: dict[int, list] = {}
    for g, ni in zip(geoms, owner, strict=True):
        by.setdefault(ni, []).append(g)
    for ni, gs in by.items():
        if nodes[ni].kind == BUILDING:
            nodes[ni].area = float(unary_union(gs).area)


def touch_pairs(nodes: _t.Sequence[Node], touch_m: float
                ) -> tuple[dict[tuple[int, int], float], list]:
    """``{(node a, node b): the step between their zeros}`` for every pair
    of ONE frame that touches (§1.2), and the pairs of TWO frames that
    would (``(step, a name, b name)``, worst first) — listed, never
    judged."""
    from shapely.strtree import STRtree
    geoms, owner, part = _rings(nodes)
    out: dict[tuple[int, int], float] = {}
    cross: dict[tuple[int, int], float] = {}
    if len(geoms) < 2:
        return out, []
    a, c = STRtree(geoms).query(geoms, predicate="dwithin", distance=touch_m)
    for gi, gj in zip(a.tolist(), c.tolist(), strict=True):
        ni, nj = owner[gi], owner[gj]
        if ni >= nj or (ni, nj) in out or (ni, nj) in cross:
            continue
        A, B = nodes[ni], nodes[nj]
        (a0, a1), (b0, b1) = A.span(part[gi]), B.span(part[gj])
        if max(a0, b0) - min(a1, b1) > VETO_M:
            continue
        (out if A.frame == B.frame else cross)[(ni, nj)] = abs(A.zero - B.zero)
    listed = sorted(((d, nodes[i].name, nodes[j].name) for (i, j), d in cross.items()),
                    reverse=True)
    return out, listed


def groups_of(nodes: _t.Sequence[Node], pairs: _t.Iterable[tuple[int, int]],
              by_name: _t.Mapping[tuple[str, str], int]) -> list[list[int]]:
    """The §1.3 groups: node indices, each group of at least two bodies
    and at least one BUILDING; a FIXED node is in none.  ``by_name``:
    ``(frame, file) -> node`` — one file is shared by every placement that
    bakes the same offset, so a carrier is looked up in its rider's frame."""
    up = list(range(len(nodes)))

    def find(i: int) -> int:
        while up[i] != i:
            up[i] = up[up[i]]
            i = up[i]
        return i

    def join(i: int, j: int) -> None:
        if not nodes[i].fixed and not nodes[j].fixed:
            up[find(i)] = find(j)
    for (i, j) in pairs:
        ki, kj = nodes[i].kind, nodes[j].kind
        if GROUND in (ki, kj) or (ki == CONNECTOR and kj == CONNECTOR):
            continue            # (a) / (b) / (c): every edge reaches a building
        join(i, j)
    first: dict[str, int] = {}
    for i, n in enumerate(nodes):
        # (d): one unit, read by its parts or named by its seat (a §16c (7)
        # bind seats a body in the unit of the cluster it joined)
        for unit in {n.unit, n.family, n.grouped} - {""} if not n.fixed else ():
            k = f"{unit}|{n.frame}"
            if k in first:
                join(i, first[k])
            else:
                first[k] = i
    for i, n in enumerate(nodes):
        if n.kind != CONNECTOR or not n.carrier:
            continue
        j = by_name.get((n.frame, n.carrier))                     # (b)
        if j is None:
            # a piece riding a UNIT (``merged_into`` names it, #31)
            j = first.get(f"{unit_root(n.carrier)}|{n.frame}")
        if j is not None:
            join(i, j)
    comp: dict[int, list[int]] = {}
    for i, n in enumerate(nodes):
        if not n.fixed:
            comp.setdefault(find(i), []).append(i)
    return [g for g in comp.values()
            if len(g) >= 2 and any(nodes[i].kind == BUILDING for i in g)]
