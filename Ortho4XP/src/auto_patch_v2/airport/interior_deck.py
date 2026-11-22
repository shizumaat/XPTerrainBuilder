"""EVERYTHING INSIDE A BUILDING MOVES WITH THE BUILDING (owner RULINGS
2026-11-19f, issue #2177): a flagged deck INSIDE a building is no deck.

Owner 2026-11-19T01:12Z: "everything inside a building just moves with
the building."  A pack's interior floors carry ``ATTR_hard_deck`` (the
sim lets one walk on them), so the read takes them for decks
(``obj8.read_placement``: ``deck_kind == "flag"``) and every deck law then
reads them — the viaduct footprints (RJTT's ``T3INTER.obj``, 1.95 M
triangles of stacked floors, stalled the placement plan 11+ min at
39 GB), the deck seats, the bridge family.  An interior rides the
building it sits in at its authored offset; it is a plain member of the
building's frame, and nothing reads it as a deck.

THE WITNESS (geometry only, RULINGS 05e): a flagged member of a frame
family (``deck_signature.family_key``: one anchor, one AGL — the pack row
set the building is authored in) whose deck plate lies INSIDE another
member of the family, the BUILDING:

- ROOFED: at least ``[basin] basement_cover_min`` of the plate's plan
  area (the plate's plan-bearing triangles, weighted by area) lies under
  the building's solids standing more than ``[basin]
  min_solid_thickness_m`` above that plate triangle's top — the same
  share that makes a roofed floor a room, never a pit (RULINGS
  2026-09-06c (1));
- FLOORED: the building's lowest solid stands at or under the plate's
  lowest point — the plate lies between the building's floor and roof
  (a bridge's lower deck roofed by its upper one, whose own piers stand
  above it, is not inside it: OTHH ``Bridge_01`` reads 0.905 roofed with
  its "building" 5.5 m over the plate's foot).

A triangle of the plate is under the building where its plan centroid
lies in a building triangle whose own centroid stands above it.  Only the
DECK VERDICT is withdrawn (``hard_deck`` / ``deck_top_z`` / ``deck_kind``
/ ``deck_plate``); the member keeps every other reading, and its frame
keeps seating it with the rest of its unit.  It runs on the read
(``basin_witness.read_objects``) BEFORE the deck signature, so a family
whose only flags were interiors is read by the signature as the unflagged
family it is; a signature deck (a family's plane, not a member's own
flag) is never asked.

MEASURED (#2177, the shared rebake plans' members on their pack geometry):
RJTT ``T3INTER.obj`` (inside ``T3MIN2.obj``) and ``T2EXTinter.obj``
(inside ``T2EXT.obj``), both 100 % roofed, leave the deck set; RJTT's 24
other decks and every deck of KBNA, KDEN, HECA, KJFK, ESSA and OTHH stay
(OTHH ``Bridge_01_LOD0_003`` 0.905 roofed, no floor under it).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from . import obj8 as _obj8
from .deck_signature import family_key

__all__ = ["mark"]


def mark(objects: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
         law) -> list[_obj8.PlacedObject]:
    """``objects`` with every flagged deck inside a building of its own
    frame family out of the deck verdict (module docstring)."""
    bl = law.tables.structures.basin
    th, cover = float(bl.min_solid_thickness_m), float(bl.basement_cover_min)
    fams: dict[tuple, list[int]] = {}
    for i, o in enumerate(objects):
        if (o.resolved is None or o.kind == "OBJECT_MSL"
                or _obj8.is_stock_library_resource(o.path)):
            continue
        fams.setdefault(family_key(o), []).append(i)
    out = list(objects)
    memo: dict = {}
    reads: dict = {}
    for idx in fams.values():
        if len(idx) < 2:
            continue
        for i in idx:
            o = objects[i]
            if o.deck_kind != "flag":
                continue
            for j in idx:
                b = objects[j]
                if j == i:
                    continue
                k = (o.resolved, round(o.heading_deg, 6), b.resolved,
                     round(b.heading_deg, 6), round(_z0(b) - _z0(o), 3))
                if k not in memo:
                    memo[k] = _inside_share(o, b, cache, th, cover, reads)
                if memo[k] >= cover:
                    out[i] = _dc.replace(
                        o, hard_deck=None, deck_top_z=None, deck_kind="",
                        deck_plate=None,
                        deck_evidence=(f"inside {b.path} ({memo[k]:.0%} of its deck "
                                       "roofed, floored under it): no deck "
                                       "(RULINGS 2026-11-19f)",))
                    break
    return out


def _inside_share(o: _obj8.PlacedObject, b: _obj8.PlacedObject,
                 cache: _obj8.ResourceCache, thickness_m: float,
                 need: float = 0.0, reads: "dict | None" = None) -> float:
    """The share of ``o``'s deck plate (plan area) under ``b``'s solids
    standing ``thickness_m`` over it — 0 where ``b`` does not reach down
    to the plate's lowest point (it is no floor under it), where nothing
    of ``o`` is a plan-bearing deck, or where the share cannot reach
    ``need`` (the plate's area within ``b``'s plan box falls short of it).
    ``reads`` holds each building's reading between calls."""
    go = cache.geometry(o.resolved)
    bld = _building(b, cache, {} if reads is None else reads)
    if go is None or bld is None or not go.hard_deck.shape[0]:
        return 0.0
    plate = go.hard_deck
    p_xy = _plan(go.vertices, o)[plate]
    p_z = go.vertices[plate][..., 1] + _z0(o)
    area = _area(p_xy)
    total = float(area.sum())
    top = p_z.max(axis=1) + thickness_m
    if (total <= 0.0 or bld["zmin"] > float(p_z.min())     # no floor under it
            or bld["zmax"] <= float(top.min())):            # nothing over it
        return 0.0
    cen = p_xy.mean(axis=1)
    reach = ((cen >= bld["lo"]) & (cen <= bld["hi"])).all(axis=1)
    if not reach.any() or float(area[reach].sum()) < need * total:
        return 0.0
    tree, b_cz = _tree(bld)
    import shapely
    pi, ti = tree.query(shapely.points(cen[reach]), predicate="intersects")
    rows = np.nonzero(reach)[0][pi]
    ok = b_cz[ti] > top[rows]
    under = np.zeros(cen.shape[0], dtype=bool)
    under[rows[ok]] = True
    return float(area[under].sum()) / total


def _building(b: _obj8.PlacedObject, cache: _obj8.ResourceCache,
              reads: dict) -> "dict | None":
    """``b``'s still solids as a building is read — their lowest
    elevation and plan box (the tree over them is built on first use,
    :func:`_tree`) — or ``None`` with none."""
    k = (b.resolved, round(b.heading_deg, 6), round(b.xy[0], 3),
         round(b.xy[1], 3), round(_z0(b), 3))
    if k in reads:
        return reads[k]
    gb = cache.geometry(b.resolved)
    hit = None
    if gb is not None and gb.solid.shape[0]:
        solid = gb.solid
        if gb.animated.shape[0] == solid.shape[0]:
            solid = solid[~gb.animated]
        if solid.shape[0]:
            y = gb.vertices[:, 1][solid]
            # the plan box over EVERY vertex: a superset, read only to
            # rule a building out
            xy = _plan(gb.vertices, b)
            hit = {"b": b, "g": gb, "solid": solid,
                   "zmin": float(y.min()) + _z0(b),
                   "zmax": float(y.max()) + _z0(b),
                   "lo": xy.min(axis=0), "hi": xy.max(axis=0), "tree": None}
    reads[k] = hit
    return hit


def _tree(bld: dict) -> tuple:
    """The building's plan triangles as a tree, with each triangle's
    centroid elevation (built once per building)."""
    if bld["tree"] is None:
        import shapely
        b, gb, solid = bld["b"], bld["g"], bld["solid"]
        t = _plan(gb.vertices, b)[solid]
        cz = gb.vertices[solid][..., 1].mean(axis=1) + _z0(b)
        bld["tree"] = (shapely.STRtree(shapely.polygons(
            np.concatenate([t, t[:, :1]], axis=1))), cz)
    return bld["tree"]


def _z0(o: _obj8.PlacedObject) -> float:
    """The rendered elevation of the object's authored ``y = 0``."""
    return float(o.anchor_z) + float(o.agl_m)


def _plan(v: np.ndarray, o: _obj8.PlacedObject) -> np.ndarray:
    """Every vertex of ``v`` in the frame plan, metres ``(n, 2)``
    (``obj8.placement_affine``)."""
    h = math.radians(o.heading_deg)
    s, c = math.sin(h), math.cos(h)
    x, z = v[:, 0], v[:, 2]
    return np.stack([o.xy[0] + x * c - z * s, o.xy[1] - (x * s + z * c)], axis=1)


def _area(t: np.ndarray) -> np.ndarray:
    """The plan area of each triangle of ``t`` ``(n, 3, 2)``."""
    return 0.5 * np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1])
                        - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1]))
