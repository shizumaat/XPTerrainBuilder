"""THE CROSSING GROUPS AND THEIR SEAT WITNESS, read ONCE at load (owner
RULINGS 2026-11-20g / 20k / 20s; spec ``docs/specs/elevated-clearance-20g-
round3-spec.md`` §B.2-§B.4).

20g: an elevated pack structure crossing a mapped road or rail keeps the
class minimum clearance over it -- first by seating its buildings high
enough, then by lowering the road or rail in an open trench under it.  20k:
"a group is lifted no higher than its own highest ground vote".  20s (O1):
the lift is capped so no member on airside-held or pavement ground floats
more than the ground bar; the roads go deeper instead.

:func:`crossing_records` reads, per pack frame (plan unit) of the partition,
on the authored geometry placed in the airport frame:

* its CROSSINGS: every component of a member whose soffit spans a mapped
  road's or rail's carriageway over the frame's ``[rebake] elevated_base_m``
  (``airport/elevated_crossing``, the one read; rails included).  A soffit
  under ``[road_gen] witness_share`` x ``[bridge] clearance_minimum_m`` over
  the frame zero is no passage (class ``low_soffit``: listed, never acted
  on -- O5);
* the CROSSING GROUP: the frame's parts touching the crossing components,
  transitively (``[placement] touch_gap_m``, ``touch_graph.VETO_M``), each
  footed part with its GROUND VOTE (the median ``DEM - y`` over its feet);
* its ANCHOR: the highest-vote BUILDING part (a footed part
  ``chain_min_height_m`` tall) within the votes' area-weighted p90 (a DEM
  reading over it is a roof the survey saw), its feet the group's SEAT
  WITNESS; a group
  whose building votes spread (area-weighted p10..p90) more than
  ``touch_seat.SEAT_MAX_M`` has no one seat (class ``no_seat``, 16v).

No seat is PREDICTED here.  :func:`seat_plan` decides, on whatever ground
reading its caller has (the cells at plan time, the planar map at rows and
emit time), the group's ``dz <= 0`` under its anchor and whether it is
lifted at all; the trench floor is tied to the SOLVED surface under the
witness (``constraints/soffit_floor``) and the patch publishes that solved
seat (``soffit_floor.publication``, at emit), which the object stage obeys
(``touch_seat``).  Nothing names an airport, a pack or a resource.
"""
from __future__ import annotations

import math
import statistics as _st
import typing as _t

import numpy as np

from . import elevated_crossing as _ec

__all__ = ["crossing_records", "seat_plan", "short_crossings", "ground_reader",
           "margin_m", "VERDICTS", "PUBLISHED", "SHORT_M"]

#: a crossing acts only where it falls short by more than this (m)
SHORT_M = 0.05
#: the low quantile a group's control seat and its unraisable floor read
#: (area-weighted): the survey's pits and roofs are no ground (MEASURED KMCO
#: unit:6, building votes 23.94 min, p02 26.57, p95 27.54, max 32.63 over a
#: complex the drawn mesh seats at 26.35 .. 27.19)
LOW_Q = 0.05
#: R4: an anchor on a held pad is preferred within this of the highest vote (m)
PREFER_M = 0.05
#: a pad this close to airside pavement is welded to it (read as held), m
WELD_M = 0.5

#: ``(unit, member, comp, way) -> class`` of every crossing the last trench
#: plan read (``planar/soffit_road`` fills it; ``constraints/soffit_floor.
#: publication`` publishes it): ``trench``, ``airside_held``, ``level_seed``,
#: ``depth_cap``, ``no_route``, ``no_seat``, ``low_soffit``
VERDICTS: dict[tuple, str] = {}


def margin_m(law) -> float:
    """``[elevated] clearance_margin_m``: the trench floor stands this far
    under the class minimum (the solve's hard tolerance, the mesh)."""
    return float(law.tables.structures.elevated.clearance_margin_m)

#: the keys of a crossing the graded surface publishes for the object stage
PUBLISHED = ("unit", "member", "comp", "way", "kind", "need", "zero", "soffit_y",
             "anchor", "dz", "lift", "class")


def _placed(g, comp, o, heading_deg: float) -> np.ndarray:
    """One component's static solid faces ``(n, 3, 3)`` in the airport
    frame: x, y the plan (``obj8.placement_affine``), z the AUTHORED ``y``."""
    from .obj8 import placement_affine
    a, b, d, e, xo, yo = placement_affine(o, heading_deg)
    T = np.asarray(g.solid)[np.asarray(comp.idx)]
    V = np.asarray(g.vertices, dtype=np.float64)[T]
    x, y, z = V[:, :, 0], V[:, :, 1], V[:, :, 2]
    return np.stack([a * x + b * z + xo, d * x + e * z + yo, y], axis=-1)


def _owners(u, cache, to_xy, elev: float) -> list:
    """``((member id, comp), faces, floor)`` of every component of the unit
    that rises over ``elev`` (the bridge law's members left out)."""
    from .placement_family import member_is_deck
    out = []
    for m in u.members:
        if getattr(m, "scatter", False) or getattr(m, "free_bridge", "") or member_is_deck(m):
            continue
        path = m.authored_path or m.live_path
        g = cache.geometry(path) if path else None
        if g is None or not g.solid.shape[0]:
            continue
        la, lo = (m.origin or u.anchor)
        o = to_xy(float(lo), float(la))
        for ci, c in enumerate(cache.components(path)):
            if c.animated or c.max_y <= elev or c.idx is None:
                continue
            out.append(((m.id, ci), _placed(g, c, o, float(m.heading_deg)), elev))
    return out


def _part_polys(u, to_xy) -> list:
    """``(member id, part, frame polygon)`` of every non-line part ring."""
    from shapely.geometry import Polygon
    out = []
    for m in u.members:
        for p in m.parts:
            if p.line:
                continue
            for r in p.rings or ():
                if len(r) >= 3:
                    g = Polygon([to_xy(lo, la) for la, lo in r])
                    g = g if g.is_valid else g.buffer(0.0)
                    if not g.is_empty:
                        out.append((m.id, p, g))
    return out


def _group(polys: list, seeds: set, touch_m: float, veto_m: float) -> list:
    """The parts touching the ``seeds`` ``(member, comp)`` transitively."""
    from shapely.strtree import STRtree
    if not polys:
        return []
    tree = STRtree([g for _m, _p, g in polys])
    a, b = tree.query([g for _m, _p, g in polys], predicate="dwithin", distance=touch_m)
    adj: dict[int, list[int]] = {}
    for i, j in zip(a.tolist(), b.tolist(), strict=True):
        pi, pj = polys[i][1], polys[j][1]
        lo = max(float(pi.base_y), float(pj.base_y))
        hi = min(float(pi.base_y) + float(pi.height_m), float(pj.base_y) + float(pj.height_m))
        if i != j and lo - hi <= veto_m:
            adj.setdefault(i, []).append(j)
    todo = [k for k, (m, p, _g) in enumerate(polys) if (m, p.comp) in seeds]
    seen = set(todo)
    while todo:
        k = todo.pop()
        for j in adj.get(k, ()):
            if j not in seen:
                seen.add(j)
                todo.append(j)
    return [polys[k] for k in sorted(seen)]


def _vote(p, to_xy, dem) -> "float | None":
    """A part's ground vote: the median of ``DEM - y`` over its feet."""
    vs = []
    for la, lo, y in p.feet or ():
        try:
            z = float(dem.z(*to_xy(lo, la)))
        except Exception:  # noqa: BLE001 -- off the raster
            continue
        if math.isfinite(z):
            vs.append(z - float(y))
    return _st.median(vs) if vs else None


def _weighted(vs: list[tuple[float, float]], q: float) -> float:
    """The area-weighted ``q`` quantile of sorted ``(vote, area)``."""
    total = sum(max(w, 1e-6) for _v, w in vs)
    acc = 0.0
    for v, w in vs:
        acc += max(w, 1e-6)
        if acc >= q * total:
            return v
    return vs[-1][0]


def _parts(group: list, to_xy, dem, wall_m: float) -> list[dict]:
    """Every footed part of the group once, with its vote, plan and feet."""
    from shapely.ops import unary_union
    polys: dict[tuple, list] = {}
    rec: dict[tuple, _t.Any] = {}
    for mid, p, g in group:
        polys.setdefault((mid, p.comp), []).append(g)
        rec[(mid, p.comp)] = p
    out = []
    for (mid, comp), p in rec.items():
        if not p.feet:
            continue
        v = _vote(p, to_xy, dem)
        if v is None:
            continue
        out.append({"member": str(mid), "comp": int(comp), "vote": float(v),
                    "area": float(p.area_m2), "building": float(p.height_m) >= wall_m,
                    "feet": [(float(a), float(b), float(y)) for a, b, y in p.feet],
                    "fxy": [(*to_xy(float(b), float(a)), float(y)) for a, b, y in p.feet],
                    "plan": unary_union(polys[(mid, comp)])})
    return out


def _anchor(parts: list[dict], top: float) -> dict:
    """The highest-vote BUILDING part (any footed part where none is one)
    whose vote stands within the group's area-weighted p90 ``top``: a DEM
    reading over the p90 is the survey's roof or bridge, not the ground the
    group stands on (MEASURED KMCO unit:6: building votes p10..p90 26.69 ..
    27.63, the highest 35.37 m)."""
    pool = [p for p in parts if p["building"]] or parts
    return max((p for p in pool if p["vote"] <= top + 1e-9), key=lambda p: p["vote"],
               default=max(pool, key=lambda p: p["vote"]))


def _crossing(c, share: float) -> dict:
    """One crossing as a plain record (``cells``: frame x, y, soffit y)."""
    mid, comp = c.owner
    xs, ys, zs = c.grid
    soffit = float(np.min(zs))
    return {"member": str(mid), "comp": int(comp), "way": c.way, "kind": c.kind,
            "need": float(c.need_m), "soffit_y": round(soffit, 3),
            "least_m": float(c.least_m), "at": (round(c.at[0], 3), round(c.at[1], 3)),
            "cells": np.stack([xs, ys, zs], axis=1),
            "class": "low_soffit" if soffit < share else ""}


def crossing_records(airport, law, cache) -> tuple[tuple[dict, ...], list[str]]:
    """``(groups, notes)``: every crossing group of the partition (module
    doc), one plain record each."""
    from shapely.ops import unary_union
    part = getattr(airport, "partition", None)
    dem = getattr(airport, "dem", None)
    if part is None or dem is None or cache is None:
        return (), []
    st = law.tables.structures
    base = float(st.rebake.elevated_base_m)
    share = float(st.road_gen.witness_share) * float(st.bridge.clearance_minimum_m)
    touch_m = float(getattr(st.placement, "touch_gap_m", 0.0) or 0.0)
    wall_m = float(st.placement.chain_min_height_m)
    to_xy = airport.frame.entry()
    cways = _ec.carriageways(getattr(airport, "osm_ways", ()) or (),
                             lambda w: list(w.points), law)
    if not cways or touch_m <= 0.0:
        return (), []
    from .touch_graph import VETO_M
    from .touch_seat import SEAT_MAX_M

    def ground(xs, ys):
        return np.array([float(dem.z(float(x), float(y))) for x, y in zip(xs, ys, strict=True)])
    out: list[dict] = []
    notes: list[str] = []
    for u in part.units:
        owners = _owners(u, cache, to_xy, base)
        crossed = _ec.read_crossings(owners, cways, ground) if owners else []
        if not crossed:
            continue
        # the group hangs from its PASSAGES: a soffit under the share is no
        # passage (O5) and joins nothing to it
        seeds = {c.owner for c in crossed if float(np.min(c.grid[2])) >= share} or \
            {c.owner for c in crossed}
        group = _group(_part_polys(u, to_xy), seeds, touch_m, VETO_M)
        parts = _parts(group, to_xy, dem, wall_m)
        blds = sorted((p["vote"], p["area"]) for p in parts if p["building"]) or \
            sorted((p["vote"], p["area"]) for p in parts)
        if not blds:
            notes.append(f"{u.id}: {len(crossed)} crossing(s), no ground vote: no seat")
            continue
        spread = _weighted(blds, 0.9) - _weighted(blds, 0.1)
        anchor = _anchor(parts, _weighted(blds, 0.9))
        rec = {"unit": str(u.id), "parts": parts, "spread": round(spread, 3),
               "anchor": (anchor["member"], anchor["comp"]), "vote_anchor": anchor["vote"],
               "plan": unary_union([g for _m, _p, g in group]),
               "crossings": [_crossing(c, share) for c in crossed],
               "class": "no_seat" if spread > SEAT_MAX_M else ""}
        out.append(rec)
        notes.append(f"{u.id}: {len(crossed)} crossing(s), anchor {anchor['member']}#"
                     f"{anchor['comp']} vote {anchor['vote']:.2f}, spread {spread:.2f} over "
                     f"{len(parts)} footed part(s)" + (" -- no one seat (16v), listed"
                                                      if rec["class"] else ""))
    return tuple(out), notes


# ── the seat plan ────────────────────────────────────────────────────────

#: the ground at a frame point ``(x, y) -> (kind, z)``: ``kind`` ``"airside"`` (a
#: pavement role), ``"held"`` (a pad welded to airside pavement),
#: ``"raisable"`` (anything the solve may grade) or ``None`` (off the map);
#: ``z`` the ground the seat stands on there -- a pad's LEVEL
#: (:func:`pad_level`: a pad is one plane, whatever the survey reads under
#: it), else the DEM
Ground = _t.Callable[[float, float], "tuple[str | None, float]"]


def pad_level(poly, dem, step: float = 4.0, out_m: float = 1.0) -> float:
    """A pad's predicted level: the median DEM along its outline grown by
    ``out_m``, every ``step`` -- the ground the pad meets at its edge (the
    survey over a building's own footprint reads its roof: MEASURED KMCO
    unit:6, part votes 23.9 .. 35.4 m over a complex the drawn mesh seats
    at 26.35 .. 27.19)."""
    ring = poly.buffer(out_m).exterior if poly.geom_type == "Polygon" else \
        max(getattr(poly.buffer(out_m), "geoms", [poly.buffer(out_m)]),
            key=lambda g: g.area).exterior
    n = max(4, min(1024, int(ring.length // step)))
    zs = []
    for k in range(n):
        q = ring.interpolate(ring.length * k / n)
        z = float(dem.z(q.x, q.y))
        if math.isfinite(z):
            zs.append(z)
    return float(np.median(zs)) if zs else float("nan")


def ground_reader(items: _t.Sequence[tuple], law, dem) -> tuple:
    """``(ground, airside_near)`` over ``(polygon, role, pad key)`` items
    (the cells at plan time, the planar faces at rows and emit time -- one
    reading for both): a point on airside value pavement (never a pad) is
    ``("airside", DEM)``; on a pad ``("held" | "raisable", its level)`` --
    held where any piece of the pad stands within the weld reach
    (:data:`WELD_M`) of airside pavement; on anything else, or nothing,
    ``("raisable" | None, DEM)``.  ``airside_near(poly)``: within
    ``airside_group_seat.TOUCH_M`` of airside pavement."""
    import shapely
    from shapely.ops import unary_union
    from shapely.strtree import STRtree

    from ..law.tables import is_value_role, role_side
    from .airside_group_seat import TOUCH_M

    def pavement(role: str) -> bool:
        return role != "building" and is_value_role(law, role) \
            and role_side(law, role) == "airside"
    rank = [0 if pavement(r) else 1 if r == "building" else 2 for _p, r, _k in items]
    pave = [p for (p, _r, _k), k in zip(items, rank, strict=True) if k == 0]
    pave_tree = STRtree(pave) if pave else None
    tree = STRtree([p for p, _r, _k in items]) if items else None
    pads: dict = {}
    for (p, _r, k), q in zip(items, rank, strict=True):
        if q == 1:
            pads.setdefault(k, []).append(p)

    def near_d(poly, d: float) -> bool:
        return pave_tree is not None and len(pave_tree.query(
            poly, predicate="dwithin", distance=d)) > 0
    held = {k for k, ps in pads.items() if any(near_d(p, WELD_M) for p in ps)}
    level: dict = {}

    def ground(x: float, y: float) -> "tuple[str | None, float]":
        hits = [] if tree is None else tree.query(shapely.points(x, y), predicate="intersects")
        if not len(hits):
            return None, float(dem.z(x, y))
        j = min((int(h) for h in hits), key=lambda h: rank[h])
        _p, role, key = items[j]
        if rank[j] == 0:
            return "airside", float(dem.z(x, y))
        if rank[j] == 1:
            if key not in level:
                level[key] = pad_level(unary_union(pads[key]), dem)
            return ("held" if key in held else "raisable"), level[key]
        return "raisable", float(dem.z(x, y))

    def near(poly) -> bool:
        return near_d(poly, TOUCH_M)
    return ground, near


def _ground_vote(p: _t.Mapping, ground: Ground) -> "tuple[float, set]":
    """``(vote, kinds)``: a part's vote on its predicted ground (the median
    ``z - y`` over its feet; its DEM vote where none reads) and the kinds
    of ground its feet stand on."""
    vs, kinds = [], set()
    for x, y_, y in p["fxy"]:
        k, z = ground(x, y_)
        kinds.add(k)
        if z is not None and math.isfinite(z):
            vs.append(z - float(y))
    return (_st.median(vs) if vs else p["vote"]), kinds


def seat_plan(rec: _t.Mapping, law, ground: Ground,
              airside_near: _t.Callable[[_t.Any], bool]) -> dict:
    """THE GROUP'S SEAT (spec §B.4 (2)-(3), RULINGS 2026-11-20s O1/O3):
    ``{"anchor", "witness", "dz", "lift", "seat", "control", "ties",
    "prior_float", "dz_by"}``.

    * the CONTROL seat is the group's area-weighted :data:`LOW_Q` building
      vote (the touch pass seats a group at its lowest vote; the quantile is
      that vote without the survey's pits);
    * the ANCHOR is the record's (the highest vote within the p90), or
      within :data:`PREFER_M` of it a part standing on a held pad (R4);
    * ``dz = min(0, low (vote_i) + split_bar_m - vote_anchor)`` over the
      members on UNRAISABLE ground -- a foot on airside pavement or a held
      pad (``ground``), or a building within ``airside_group_seat.TOUCH_M``
      of an airside-role cell (``airside_near``) -- whose float at the
      control seat is within ``[placement] split_bar_m`` (O1: no such member
      floats past the ground bar), ``low`` their area-weighted
      :data:`LOW_Q` vote (the survey's pits are no ground).  Where that leaves no lift over the
      control the group is NOT lifted (``lift`` false) and ``dz`` brings the
      seat to the control: the trench is graded for the seat the touch pass
      gives it;
    * ``ties``: the members on raisable ground of a lifted group within the
      bar at control -- the ground under their feet is tied to the witness
      (§B.7); ``prior_float``: members past the bar already at the control
      (listed, O3: they never zero the lift).

    ``seat`` is the PLANNED seat on the DEM votes (geometry only: the rows
    tie the floor to the solved witness); ``slack`` the ground bar it may
    solve under (``short_crossings`` plans for it)."""
    bar = float(law.tables.structures.placement.split_bar_m) or 0.5
    read = {(p["member"], p["comp"]): _ground_vote(p, ground) for p in rec["parts"]}
    parts = [dict(p, vote=read[(p["member"], p["comp"])][0]) for p in rec["parts"]]
    kinds_of = {(p["member"], p["comp"]): read[(p["member"], p["comp"])][1] for p in parts}
    by = {(p["member"], p["comp"]): p for p in parts}
    blds = [p for p in parts if p["building"]] or parts
    ranked = sorted((p["vote"], p["area"]) for p in blds)
    ctl, top = _weighted(ranked, LOW_Q), _weighted(ranked, 0.9)
    a = _anchor(parts, top)
    # R4: within PREFER_M of its vote, an anchor whose feet stand on a held
    # pad (stage 1 solves its witness: the floor follows it, never pulls it)
    a = next((p for p in sorted(blds, key=lambda p: -p["vote"])
              if a["vote"] - PREFER_M <= p["vote"] <= a["vote"]
              and kinds_of[(p["member"], p["comp"])] == {"held"}), a)
    ties, prior, held = [], [], []
    for p in parts:
        float0 = ctl - p["vote"]
        if float0 > bar:
            prior.append((p["member"], p["comp"], round(float0, 3)))
            continue
        kinds = kinds_of[(p["member"], p["comp"])]
        if kinds & {"airside", "held"} or (p["building"] and airside_near(p["plan"])):
            held.append((p["vote"], p["area"]))
        elif p is not a and kinds <= {"raisable"}:
            ties.append((p["member"], p["comp"]))
    floor = _weighted(sorted(held), LOW_Q) if held else None
    dz = 0.0 if floor is None else min(0.0, floor + bar - a["vote"])
    dz_by = "" if floor is None else f"p{round(100 * LOW_Q):02d} {floor:.2f} of {len(held)}"
    lift = a["vote"] + dz > ctl + SHORT_M
    if not lift:
        dz, ties = min(0.0, ctl - a["vote"]), []
    return {"anchor": (a["member"], a["comp"]), "witness": a["feet"], "dz": round(dz, 3),
            "lift": lift, "seat": a["vote"] + dz, "control": ctl, "ties": ties,
            "prior_float": prior, "dz_by": dz_by, "by": by, "slack": bar}


def short_crossings(rec: _t.Mapping, plan: _t.Mapping, margin: float,
                    ground: Ground) -> list[dict]:
    """The crossings of ``rec`` short by more than :data:`SHORT_M` at the
    planned seat less its ``slack`` (the seat the solve may give it: the
    plan reads the DEM, the object stage the solved surface) over the ground
    ``ground`` reads under their cells (a pad's level on a pad),
    ``low_soffit`` ones left out (no passage), each with its ``short`` at the
    planned seat and its planned floor (at the slackened seat: the trench
    is laid out deep enough, the floor rows hold the real one)."""
    out = []
    for c in rec["crossings"]:
        if c["class"]:
            continue
        cells = np.asarray(c["cells"])
        gz = np.array([ground(float(x), float(y))[1] for x, y, _z in cells])
        ok = np.isfinite(gz)
        least = float(np.min(cells[ok, 2] - gz[ok])) if ok.any() else c["least_m"]
        seat = plan["seat"] - float(plan.get("slack", 0.0))
        if c["need"] - (seat + least) > SHORT_M:
            out.append(dict(c, short=round(c["need"] - (plan["seat"] + least), 3),
                            floor=seat + c["soffit_y"] - c["need"] - margin))
    return out
