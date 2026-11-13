"""THE VISIBLE CUT OF A HIDDEN SHELL (#1918; owner RULINGS 2026-11-06d (1)
and (6), 21:40Z: "trench depth should be based on other objects like bridges
and structures that extend below the surrounding grade").

A concave cut shell the written DSF hides owns no ground and pins nothing
(:func:`airport.object_floor.owns_ground`).  The cut it stood for is read from
the VISIBLE members of its frame — the co-placed placements, less the shell
itself and the deck pieces its pavement drives across (``FloorDeck``) — that
stand below the surrounding grade.  The shell is a WITNESS only, of which
member lies ON the cut:

* a member COMPONENT whose bottom stands ``shell_floor_min_m`` or more over
  the shell's surface under it is a COVER — a deck plate, a soffit, the
  girders under a deck — and states nothing about the ground;
* one whose bottom stands that far UNDER it is BURIED — a catenary mast's
  or a pier's foundation — and states nothing either;
* every other component reaching ``object_min_depth_m`` under the shell's
  rim (the surrounding grade the pack states) LIES ON THE CUT — a wall or
  pier foot, a kerb footing, a lamp column, a bank liner — and its surface
  standing that far under the rim, sampled every quarter ``[channel]
  station_m`` (a long liner's vertices can stand a station apart), gives the
  cut's witness points (:attr:`VisibleCut.points`, each tagged with its
  component).

The shell's own FLOOR PLATES (its near-horizontal faces standing
``object_min_depth_m`` or more under its rim, sampled the same way) are
:attr:`VisibleCut.extent`: where the floor lies, never how deep the cut is
(spec ``object-gate-member-floors-20261113.md`` §4.1) — the channel reads it
to tell a member standing on the floor from one on a ledge of the bank.

The channel reads them along its axis (``planar/channel_depth``): a member's
lowest point at a station is its foot there, the feet are the floor profile
and the floor's edge, the rest of its plan the bank up to the crest.

Every number is a law-table value; nothing here names a pack or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

from ..geom.lowest_face import floor_z_at
from . import obj8 as _obj8
from .object_floor import ObjectFloor, _placed_all

__all__ = ["visible_cuts"]


@_dc.dataclass(frozen=True)
class VisibleCut:
    """What a hidden shell's visible frame states about its cut: ``points``
    ``(n, 4)`` — ``x, y, z`` and the member component's index — of the
    members lying on it (module doc), ``covers`` / ``buried`` how many
    components stood over it / under it, ``bound`` the shell's footprint
    (the most the cut may reach, 2026-11-06d (1)), ``extent`` ``(m, 3)``
    points on the shell's own floor plates (module doc) and ``members``
    each member index's ``(placement id, authored zero)``."""

    shell_id: str
    points: np.ndarray = _dc.field(repr=False, compare=False)
    covers: int = 0
    buried: int = 0
    notes: tuple[str, ...] = ()
    bound: object = _dc.field(default=None, repr=False, compare=False)
    extent: np.ndarray = _dc.field(default_factory=lambda: np.zeros((0, 3)), repr=False,
                                   compare=False)
    members: tuple[tuple[str, float], ...] = ()


def _read_visible_cut(f: ObjectFloor, objects: _t.Mapping[str, _obj8.PlacedObject],
                     cache: _obj8.ResourceCache, law,
                     scale: tuple[float, float] = (1.0, 1.0)) -> VisibleCut:
    """The :class:`VisibleCut` of the hidden shell ``f`` (module doc);
    ``objects`` the placements by id, ``scale`` the frame's metres per OBJ
    metre."""
    ob = law.tables.structures.tunnel.object
    span, flat = float(ob.shell_floor_min_m), float(ob.shell_flat_m)
    deep = float(f.rim_z if f.rim_z is not None else f.zero_z) \
        - float(law.tables.structures.channel.object_min_depth_m)
    decked = {d.object_id for d in f.decks}
    step = float(law.tables.structures.channel.station_m) / 4.0
    got: list[np.ndarray] = []
    members: list[tuple[str, float]] = []
    count = {"cover": 0, "buried": 0}
    for pid, _res, zero in f.seats:
        o = objects.get(pid)
        if pid == f.object_id or pid in decked or o is None or o.resolved is None:
            continue
        g = cache.geometry(o.resolved)
        if g is None or not len(g.solid):
            continue
        faces = _placed_all(o, g, float(zero), scale)
        for c in cache.genuine(o.resolved):
            if c.idx is None or not len(c.idx):
                continue
            fc = faces[c.idx]
            kind = _member(fc, f, span, deep, flat)
            if kind in count:
                count[kind] += 1
            if kind != "cut":
                continue
            pts = _dense(fc, step)
            pts = pts[pts[:, 2] <= deep]
            got.append(np.column_stack([pts, np.full(len(pts), float(len(got)))]))
            members.append((str(pid), float(zero)))
    pts = np.concatenate(got) if got else np.zeros((0, 4))
    note = (f"{f.id}: visible cut (2026-11-06d (6)) — {len(got)} member component(s) "
            f"on the cut, lowest {pts[:, 2].min():.2f}; {count['cover']} cover(s), "
            f"{count['buried']} buried" if len(pts)
            else f"{f.id}: visible cut — no visible member lies on the cut")
    return VisibleCut(f.id, pts, count["cover"], count["buried"], (note,), f.footprint,
                      _floor_plates(f, deep, step, law), tuple(members))


def _floor_plates(f: ObjectFloor, deep: float, step: float, law) -> np.ndarray:
    """``(m, 3)`` points on the hidden shell's own near-horizontal faces
    standing at or under ``deep`` (its rim less ``object_min_depth_m``):
    where its floor plates lie (:attr:`VisibleCut.extent`)."""
    fc = np.asarray(f.faces, float).reshape(-1, 3, 3)
    if not len(fc):
        return np.zeros((0, 3))
    n = np.cross(fc[:, 1] - fc[:, 0], fc[:, 2] - fc[:, 0])
    ln = np.linalg.norm(n, axis=1)
    flat = np.abs(n[:, 2]) >= float(law.tables.structures.tunnel.object.plate_normal_y_min) \
        * np.where(ln > 0, ln, np.inf)
    low = fc[:, :, 2].max(axis=1) <= deep
    keep = fc[flat & low]
    if not len(keep):
        return np.zeros((0, 3))
    pts = _dense(keep, step)
    return pts[pts[:, 2] <= deep]


def _dense(fc: np.ndarray, step: float) -> np.ndarray:
    """Points on the faces ``fc`` no farther than about ``step`` apart:
    each triangle subdivided evenly by its longest edge."""
    out = [fc.reshape(-1, 3)]
    edge = np.max(np.linalg.norm(fc - np.roll(fc, 1, axis=1), axis=2), axis=1)
    for n in np.unique(np.ceil(edge / max(step, 1e-6)).astype(int)):
        if n < 2:
            continue
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
        keep = (i + j) <= n
        a, b = (i[keep] / n)[:, None], (j[keep] / n)[:, None]
        for t in fc[np.ceil(edge / max(step, 1e-6)).astype(int) == n]:
            out.append(t[0] + a * (t[1] - t[0]) + b * (t[2] - t[0]))
    return np.concatenate(out)


def _member(fc: np.ndarray, f: ObjectFloor, span: float, deep: float,
            flat: float) -> "str | None":
    """``"cover"``, ``"buried"``, ``"cut"`` or ``None`` (off the cut, or
    above the surrounding grade) for one member component's placed faces
    ``fc``."""
    pts = fc.reshape(-1, 3)
    zmin = float(pts[:, 2].min())
    if zmin > deep:
        return None
    low = pts[pts[:, 2] <= zmin + flat]
    # the bottom's corners AND its faces' centres: a deck plate's corners
    # stand over the banks it spans, its faces over the cut
    bot = fc[(fc[:, :, 2] <= zmin + flat).all(axis=1)].mean(axis=1)
    xy = np.concatenate([low[:, :2], bot[:, :2]]) if len(bot) else low[:, :2]
    under = floor_z_at(f.faces, xy[:, 0], xy[:, 1])
    if not np.isfinite(under).any():
        return None
    gap = zmin - float(np.nanmin(under))
    return "cover" if gap >= span else ("buried" if gap <= -span else "cut")


def visible_cuts(floors: _t.Sequence[ObjectFloor], objects, cache, law,
                 scale: tuple[float, float] = (1.0, 1.0)) -> list[VisibleCut]:
    """Each HIDDEN shell's :class:`VisibleCut` — the channels' depth, width
    and reach witness (``planar/channel_depth``)."""
    by_id = {str(o.id): o for o in objects or ()}
    return [_read_visible_cut(f, by_id, cache, law, scale) for f in floors
            if f.hidden and f.footprint is not None and not f.footprint.is_empty]
