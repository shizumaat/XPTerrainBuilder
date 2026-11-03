"""A TERRAIN-ADAPTED STRUCTURE WHOSE SUPPORTS WOULD BE BURIED IS RAISED
ONTO THEM — EXPERIMENT (#1726; owner 2026-11-02T23:28Z "Try B so I can
see it"; REMOVE once he rules).

A structure member the terrain adapted to (``rebake_plan.screen_of``'s
``exclude``, the reason ``pack_partition.ADAPTED_SKIP``) keeps its
authored row and is never re-seated.  When that member stands on slender
SUPPORTS (poles, piers: ``geom/foot_planes.is_support``'s reading, in the
object's own frame) whose feet the surface would bury, the owner's rule is
"the bottom of the poles and piers to be at grade, likely lifting the
building up".  With ``[building_pad] support_raise_members`` on:

* the supports' DENSEST foot plane (``geom/foot_planes.support_plane``:
  the elevation that stands the most of their feet at grade, within
  ``PLANE_BAND_M``, at least ``PLANE_MIN_FEET`` of them) is the origin
  elevation ``E`` of the member's ORIGIN FRAME — every DSF row sharing its
  ``(lat, lon, heading, elevation)`` (``msl_feet.origin_of_row``: the
  author's one frame), so the parts of one model stay together;
* when ``E`` stands more than ``tol_m`` above the drape at the origin,
  every row of the frame is written ``OBJECT_MSL`` at ``E`` and none of
  them is split or re-seated (:func:`without_rows` removes their members
  from the plan the split reads).

Off (the default) nothing here runs.  Supports far off the densest plane
(a few deep landside poles) are not brought to grade.  Name-free: the
witnesses are the screen's reason, the geometry and the rows.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import typing as _t

__all__ = ["SUPPORT_RAISE", "raised_rows",
           "without_rows", "raise_seats", "LAST"]

#: the ``MslSeat.why`` this module writes
SUPPORT_RAISE = "support_raise"
#: the last :func:`raised_rows` call's frames, for the report: adapted
#: resource -> (lift m, support feet at grade, support feet read, rows)
LAST: dict[str, tuple[float, int, int, int]] = {}

Surface = _t.Callable[[float, float], "float | None"]


def _support_feet(path: str, max_extent_m: float, min_height_m: float
                 ) -> list[tuple[float, float, float]]:
    """One foot ``(x, y, z)`` per SUPPORT of the OBJ8 at ``path``: a static
    solid component at least ``min_height_m`` tall whose plan box spans at
    most ``max_extent_m`` on both axes of the object's own frame — its
    plan centre at its lowest ``y``.  ``[]`` when unreadable."""
    from . import obj8 as _obj8
    try:
        g = _obj8.parse_obj8(path)
    except (OSError, ValueError):
        return []
    out = []
    for c in _obj8.solid_components(g):
        if c.animated or c.max_y - c.min_y < min_height_m:
            continue
        pts = g.vertices[c.tris.reshape(-1)]
        if (float(pts[:, 0].max() - pts[:, 0].min()) <= max_extent_m
                and float(pts[:, 2].max() - pts[:, 2].min()) <= max_extent_m):
            out.append((c.cx, c.min_y, c.cz))
    return out


def _origin_z(row: _t.Any, surface: Surface) -> "float | None":
    """Where the row's origin renders now: its MSL elevation, or the drape
    at its origin plus an ``OBJECT_AGL`` lift."""
    if row.kind == "OBJECT_MSL":
        return float(row.elevation or 0.0)
    g = surface(float(row.lat), float(row.lon))
    if g is None:
        return None
    return float(g) + (float(row.elevation or 0.0) if row.kind == "OBJECT_AGL" else 0.0)


def raised_rows(dump: _t.Any, rebake_plan: _t.Any, surface: Surface, pack_root: str,
                law: _t.Any, tol_m: float,
                counts: "dict | None" = None) -> dict[int, float]:
    """``row index -> E`` for every row of an origin frame raised onto its
    terrain-adapted member's supports (module docstring); ``{}`` when the
    knob is off."""
    from ..geom.foot_planes import support_lift_on
    if not support_lift_on(law, "support_raise_members"):
        return {}
    from ..geom.foot_planes import PLANE_BAND_M, PLANE_MIN_FEET, support_plane
    from .msl_feet import _foot_needs, origin_of_row
    from .pack_partition import ADAPTED_SKIP
    st = law.tables.structures
    ext = float(getattr(st.building_pad, "support_max_extent_m", 0.0) or 0.0)
    hmin = float(st.placement.chain_min_height_m)
    adapted = {p for p, why in (getattr(rebake_plan, "skipped", ()) or ())
               if str(why).startswith(ADAPTED_SKIP)}
    rows = list(getattr(dump, "placements", ()) or ())
    frames: dict[tuple, list[int]] = {}
    for i, r in enumerate(rows):
        if r.kind in ("OBJECT", "OBJECT_AGL", "OBJECT_MSL"):
            frames.setdefault(origin_of_row(r), []).append(i)
    out: dict[int, float] = {}
    LAST.clear()
    for idx in frames.values():
        mine = [i for i in idx if rows[i].def_path in adapted]
        if not mine or not pack_root:
            continue
        needs: list[float] = []
        for i in mine:
            phys = os.path.join(pack_root, rows[i].def_path)
            feet = _support_feet(phys, ext, hmin) if os.path.isfile(phys) else []
            needs += _foot_needs(rows[i], feet, surface)
        sp = support_plane(needs, PLANE_BAND_M)
        z0 = _origin_z(rows[mine[0]], surface)
        if sp is None or sp[1] < PLANE_MIN_FEET or z0 is None or sp[0] - z0 <= tol_m:
            continue
        for i in idx:
            out[i] = round(float(sp[0]), 3)
        LAST[rows[mine[0]].def_path] = (round(sp[0] - z0, 3), sp[1], len(needs), len(idx))
    if counts is not None and out:
        counts["support_raise_rows"] = len(out)
    return out


def without_rows(rebake_plan: _t.Any, raised: _t.Collection[int]) -> _t.Any:
    """``rebake_plan`` less every member placed by a raised row (its
    ``dsf:obj<row>`` id): the split never cuts, nor seats, them."""
    if not raised:
        return rebake_plan
    gone = {f"dsf:obj{i}" for i in raised}
    units = []
    for u in rebake_plan.units:
        ms = tuple(m for m in u.members if m.id not in gone)
        if ms:
            units.append(u if len(ms) == len(u.members) else _dc.replace(u, members=ms))
    return _dc.replace(rebake_plan, units=tuple(units))


def raise_seats(dump: _t.Any, raised: _t.Mapping[int, float]) -> tuple:
    """The ``MslSeat`` of every raised row, at its frame's ``E``."""
    from ..model.placement import MslSeat
    rows = list(getattr(dump, "placements", ()) or ())
    return tuple(MslSeat(i, str(rows[i].def_path), float(rows[i].lon), float(rows[i].lat),
                         float(rows[i].heading_deg), float(z), SUPPORT_RAISE)
                 for i, z in sorted(raised.items()) if 0 <= i < len(rows))
