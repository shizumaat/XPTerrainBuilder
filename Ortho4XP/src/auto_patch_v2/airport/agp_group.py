"""THE AGP GROUP, DERIVED ONCE AT THE PACK STAGE (#2090; spec
``2090-agp-group-groundside-spec.md`` A1-A3; owner 2026-11-14T20:49Z: "The
terminal is connected via the skybridge to concourse A, so must stay with
concourse A as part of the object group").

``planar/free_bridge.attach_free_bridges`` calls :func:`attach_agp_groups`
FIRST, so every reader after it (the bridge stacks' deck joins, the ground
plates, the stage-2 datum, the object stage) reads the one record
``Airport.agp_groups`` (``model/agp_group``):

* MEMBERS: every on-ground (``OBJECT`` / ``OBJECT_MSL``) row whose
  definition is a pack-local ``.agp`` (``agp_ground._Member``);
* JOINS: ``agp_ground.joins`` with V2's certainty; a pair of two members
  that both read as airside (ground point within ``[agp] airside_reach_m``
  of the apt.dat pavement) is never read — the airside is king and two
  airside members never move each other (D2);
* A2 THE PROVISIONAL GOVERNOR: the member whose ground point is nearest the
  apt.dat airside pavement (``deck_stack._Airside``), when that distance is
  within ``airside_reach_m`` and every other member is at least twice as
  far.  None: the group is ``agp_group_unpredicted`` (nothing graded for
  it; the object stage seats it by the fallback rule);
* A3 ``zero_pred``: the DEM at the governor's ground point plus the chain
  step (``AgpGroup.zero_pred``).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..model.agp_group import AGP_GROUP_PREFIX, AgpGroup, AgpJoin, AgpMember
from . import agp_ground as _ag
from . import agp_pieces as _ap

__all__ = ["members_of", "read_groups", "attach_agp_groups", "log_line"]


def members_of(airport) -> list:
    """``agp_ground._Member`` per on-ground pack-local ``.agp`` row of the
    airport's DSF objects (lon / lat through the frame), in row order."""
    import os
    frame = getattr(airport, "frame", None)
    pack = getattr(airport, "pack", None)
    root = os.path.realpath(getattr(pack, "pack_root", "") or "") if pack is not None else ""
    if frame is None:
        return []
    to_ll = frame.transformers()[1]
    read: dict[str, "_ap.AgpFile | None"] = {}
    out = []
    for o in getattr(airport, "dsf_objects", ()) or ():
        path = getattr(o, "resolved_path", None)
        if not path or not str(o.path).lower().endswith(".agp") \
                or o.kind not in ("OBJECT", "OBJECT_MSL"):
            continue
        if root and not os.path.realpath(path).startswith(root + os.sep):
            continue                                  # a library .agp: never moved
        if path not in read:
            read[path] = _ap.read_agp(path) if os.path.isfile(path) else None
        agp = read[path]
        if agp is None:
            continue
        lat, lon = to_ll(*o.xy)
        out.append(_ag._Member(_index(o.id), str(o.path), "", agp, float(lon), float(lat),
                               float(o.heading_deg), str(o.id)))
    return out


def _index(oid: str) -> int:
    """The DSF placement ordinal of ``dsf:obj<i>`` (``-1`` otherwise)."""
    from .dsf import TILE_MARK
    t = str(oid).split(TILE_MARK, 1)[0]
    return int(t[7:]) if t.startswith("dsf:obj") and t[7:].isdigit() else -1


def _airside_m(airport, xys) -> list[float]:
    """Each point's plan distance to the apt.dat airside (``inf`` with none)."""
    from shapely.geometry import Point

    from .deck_stack import _Airside
    air = _Airside(airport)
    if air._tree is None:
        return [math.inf] * len(xys)
    out = []
    for x, y in xys:
        p = Point(x, y)
        i = air._tree.nearest(p)
        out.append(float(air._polys[int(i)].distance(p)))
    return out


def _governor(group: _t.Sequence[int], dist: _t.Sequence[float], reach: float) -> int | None:
    """A2 (module doc): the member nearest the airside, within ``reach``,
    every other member at least twice as far (and further)."""
    k = min(group, key=lambda i: (dist[i], i))
    d = dist[k]
    if not d <= reach:
        return None
    if any(i != k and not (dist[i] >= 2.0 * d and dist[i] > d) for i in group):
        return None
    return k


def read_groups(airport, law) -> tuple[tuple[AgpGroup, ...], tuple[AgpJoin, ...], list[str]]:
    """``(groups, refused joins, notes)`` — module doc."""
    from .dem import dem_z_many
    agp = law.tables.structures.agp
    members = members_of(airport)
    if len(members) < 2:
        return (), (), []
    to_xy = airport.frame.transformers()[0]
    gps = [_ap.ground_point(m.agp, m.lon, m.lat, m.heading_deg) for m in members]
    xys = [to_xy(lon, lat) for lon, lat in gps]
    dist = _airside_m(airport, xys)
    reach = float(agp.airside_reach_m)
    side = [d <= reach for d in dist]
    refused: dict = {}
    steps = _ag.joins(members, lambda i, j: not (side[i] and side[j]), agp, refused)
    from .agp_floors import flush
    flush()                                     # the floor cache (D1)

    def _jn(i: int, j: int, jn) -> AgpJoin:
        return AgpJoin(members[i].row, members[j].row, round(float(jn.step), 3), jn.votes,
                       jn.rival, (round(jn.lat, 8), round(jn.lon, 8)), jn.stands)
    groups, notes = [], []
    dem = getattr(airport, "dem", None)
    for comp in _ag._groups(len(members), steps):
        gov = _governor(comp, dist, reach)
        need = _ag._needs(gov, steps, 0.0) if gov is not None else {}
        dem_gov = None
        if gov is not None and dem is not None:
            z = float(dem_z_many(dem, [xys[gov][0]], [xys[gov][1]])[0])
            dem_gov = z if math.isfinite(z) else None
        why = "" if gov is not None else (
            "agp_group_unpredicted: no member within "
            f"{reach:.0f} m of the airside with every other twice as far")
        ms = tuple(AgpMember(members[k].row, members[k].index, members[k].resource,
                             (round(xys[k][0], 3), round(xys[k][1], 3)),
                             (round(gps[k][1], 9), round(gps[k][0], 9)),
                             round(dist[k], 2) if math.isfinite(dist[k]) else math.inf,
                             None if k not in need else round(need[k], 3)) for k in comp)
        g = AgpGroup(f"{AGP_GROUP_PREFIX}{members[min(comp, key=lambda k: members[k].index)].row}",
                     ms, tuple(_jn(i, j, jn) for (i, j), jn in sorted(steps.items())
                               if i in comp and j in comp),
                     None if gov is None else members[gov].row, dem_gov, why,
                     frozenset(members[k].row for k in comp if side[k]))
        groups.append(g)
        notes.append(_note(g))
    rej = tuple(_jn(i, j, jn) for (i, j), jn in sorted(refused.items()))
    for j in rej:
        notes.append(f"join refused (V2): {j.a} + {j.b} step {j.step:+.2f} on "
                     f"{j.votes} pair(s) against {j.rival}")
    return tuple(groups), rej, notes


def _note(g: AgpGroup) -> str:
    gov = g.member(g.governor) if g.governor else None
    head = (f"{g.id}: {len(g.members)} members, governor "
            + (f"{gov.resource.rsplit('/', 1)[-1]} ({gov.row}, {gov.airside_m:.1f} m from the "
               f"airside, DEM {g.dem_gov if g.dem_gov is not None else float('nan'):.2f})"
               if gov else g.why))
    rows = [f"{m.resource.rsplit('/', 1)[-1]} {m.row} step "
            + ("-" if m.step is None else f"{m.step:+.2f}")
            + ("" if g.zero_pred(m.row) is None else f" zero_pred {g.zero_pred(m.row):.2f}")
            for m in g.members if m.row != g.governor]
    return head + "; " + "; ".join(rows)


def attach_agp_groups(airport, law, notes_out: "list | None" = None):
    """``airport`` with ``agp_groups`` read (:func:`read_groups`)."""
    groups, _rej, notes = read_groups(airport, law)
    if notes_out is not None:
        notes_out.extend(notes)
    return _dc.replace(airport, agp_groups=groups)


def log_line(icao: str, groups: _t.Sequence[AgpGroup], seconds: "float | None" = None) -> str:
    """The build log's one line on the AGP groups read."""
    took = "" if seconds is None else f" in {seconds:.2f} s"
    gov = sum(1 for g in groups if g.governor is not None)
    return (f"[{icao}] agp groups (#2090): {len(groups)} group(s), {gov} governed{took}")
