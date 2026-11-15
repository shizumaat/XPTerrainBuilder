"""A TUNNEL MOUTH MADE OF TOUCHING PIECES IS ONE OBJECT GROUP (#2099; owner
ruling 2026-11-15T16:07Z: "Like other areas, tunnel mouths made of multiple
touching pieces need to be treated as an object group"; spec
``docs/specs/2099-mouth-groups.md``).

A pack may author a mouth as a box over the bore (a deck, a portal, an
entrance) and its WING WALLS as separate placements at their own anchors,
touching the box.  Read one by one, each wing stood on the ground at its own
anchor -- on top of the cut instead of down in it (MEASURED CYYZ, the GlobalArt
pack: three mouths, seven wings, 2.4-94 m from their box's anchor).

THE GROUP is the load partition's ε-contact graph (``PackPartition.contacts``,
the grouping every other seat reads) across anchor families
(:func:`mouth_groups`); :func:`_wing_refusal` is the witness that a touching
piece is a wing, not a fence, a lamp or a building.  THE SEAT is the mouth's:
a wing's zero is the mouth's zero plus the mouth's FLOOR y (``Mouth.floor_y``,
the road under the mouth in the mouth's own frame), carried by whichever seat
the mouth itself has -- its plate (:func:`wing_plates`) or its whole-row record
(:func:`wing_records`).

Every number is a law-table value; nothing here names a pack, a resource or an
airport.
"""
from __future__ import annotations

import collections
import dataclasses as _dc
import typing as _t

import numpy as np
import shapely

from . import frame_entry as _fe
from . import obj8 as _obj8
from .obj8_clip import _bulk_polys

__all__ = ["Mouth", "MouthGroup", "mouths_of", "mouth_groups", "wing_plates",
           "wing_records", "log_lines", "MOUTH_DATUM"]

#: the ``datum`` of a wing's whole-row seat record (:func:`wing_records`)
MOUTH_DATUM = "mouth group"


@_dc.dataclass(frozen=True)
class Mouth:
    """One MOUTH placement a reader took (spec §1 M1-M3): ``floor_y`` the
    road under it in its own frame (under its zero), ``reader`` the reader's
    name (for the log)."""

    object_id: str
    floor_y: float
    reader: str


@_dc.dataclass(frozen=True)
class MouthGroup:
    """A mouth and its wings, ``(placement id, resource)`` each."""

    mouth: Mouth
    wings: tuple[tuple[str, str], ...]


def _solids(o: _obj8.PlacedObject, cache: _obj8.ResourceCache, law):
    """``(placed plan, top y, hard-deck triangles)`` of ``o``'s genuine solids
    (frame metres), or ``None`` with none."""
    g = None if o.resolved is None else cache.geometry(o.resolved)
    comps = [] if g is None else cache.genuine(o.resolved)
    if g is None or not comps:
        return None
    tris = np.concatenate([c.tris for c in comps])
    plan = _fe.union(_bulk_polys(g.vertices, tris), "mouth_group._solids")
    plan = _fe.enter([plan], _obj8.placement_affine(o.xy, o.heading_deg), _fe.quantum(law))[0]
    if plan is None or plan.is_empty:
        return None
    return plan, float(g.vertices[np.unique(tris), 1].max()), int(len(g.hard_deck))


def _farthest(plan, other) -> float:
    """How far ``plan``'s outline runs from ``other`` at most (metres)."""
    return max(other.distance(shapely.Point(c))
               for q in getattr(plan, "geoms", [plan]) for c in q.exterior.coords)


def _wing_refusal(read, mouth_top_over_floor: float, mouth_plan, law) -> "str | None":
    """Why the piece read ``read`` (:func:`_solids`) is NO wing of a mouth
    whose top stands ``mouth_top_over_floor`` over its floor, plan
    ``mouth_plan`` -- or ``None`` (spec §1 W1-W3):

    W1 A WALL: no hard deck, and no part of its solids' plan as thick as
    ``[tunnel.object] wall_face_max_thickness_m`` (thicker solids are decks
    and slabs).
    W2 A WALL'S HEIGHT, NO TALLER THAN THE MOUTH: its top stands
    ``shell_floor_min_m`` or more over its zero (its foot), and no more than
    ``plate_bin_m`` over the mouth's top over its floor.
    W3 IT RUNS OUT OF THE MOUTH: it reaches ``entrance_skirt_m`` or more
    beyond the mouth's plan, and nowhere farther than ``wing_reach_max_m``."""
    ob = law.tables.structures.tunnel.object
    if read is None:
        return "no genuine solid"
    plan, top, hard = read
    if hard:
        return "it carries a hard deck"
    if not plan.buffer(-0.5 * float(ob.wall_face_max_thickness_m)).is_empty:
        return f"no wall: its plan is {ob.wall_face_max_thickness_m:g} m thick somewhere"
    if top < float(ob.shell_floor_min_m):
        return f"no wall's height: its top {top:+.2f} under shell_floor_min_m"
    if top > mouth_top_over_floor + float(ob.plate_bin_m):
        return (f"taller than the mouth: its top {top:+.2f} over the mouth's "
                f"{mouth_top_over_floor:.2f} over its floor")
    far = _farthest(plan, mouth_plan)
    if far < float(ob.entrance_skirt_m):
        return f"it runs {far:.1f} m out of the mouth, under entrance_skirt_m"
    if far > float(ob.wing_reach_max_m):
        return f"it runs {far:.1f} m out of the mouth, over wing_reach_max_m"
    return None


def _contact_roots(partition) -> tuple[dict[str, str], dict[str, str]]:
    """``(placement id -> its root, placement id -> resource)``: the load
    partition's ε-contact components over PLACEMENTS (a part of one touching a
    part of another), a LINE object's parts (a fence, a kerb) joining none."""
    owner: dict[int, str] = {}
    path: dict[str, str] = {}
    for ui, u in enumerate(partition.units):
        for mi, m in enumerate(u.members):
            oid, res = partition.member_object.get((ui, mi), (m.id, m.resource))
            path[str(oid)] = str(res)
            owner.update((p.pid, str(oid)) for p in m.parts if not getattr(p, "line", False))
    par: dict[str, str] = {}

    def find(x: str) -> str:
        par.setdefault(x, x)
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for a, b in partition.contacts:
        oa, ob = owner.get(a), owner.get(b)
        if oa is not None and ob is not None and oa != ob:
            par[find(oa)] = find(ob)
    return {o: find(o) for o in path}, path


def mouth_groups(partition, objects: _t.Sequence[_obj8.PlacedObject],
                 mouths: _t.Sequence[Mouth], cache: _obj8.ResourceCache, law,
                 taken: _t.AbstractSet[str] = frozenset()
                 ) -> tuple[list[MouthGroup], list[str]]:
    """THE MOUTH GROUPS (spec §1) and one note per touching piece refused.

    A candidate stands in its mouth's ε-contact component of the load
    partition, is no mouth and is not ``taken`` (seated by another rule: one
    authority per row).  It is a WING when :func:`_wing_refusal` passes it and
    its plan comes within ``[rebake] contact_epsilon_m`` of the mouth's plan or
    of a wing already joined (ONE HOP: a chain runs only through wings).  A
    wing joins one mouth, the first by id."""
    if partition is None or not mouths:
        return [], []
    eps = float(law.tables.structures.rebake.contact_epsilon_m)
    root, path = _contact_roots(partition)
    by_id = {str(o.id): o for o in objects}
    comp: dict[str, list[str]] = collections.defaultdict(list)
    for oid, r in root.items():
        comp[r].append(oid)
    mouth_ids = {m.object_id for m in mouths}
    out: list[MouthGroup] = []
    notes: list[str] = []
    used: set[str] = set()
    for m in sorted(mouths, key=lambda q: q.object_id):
        mo = by_id.get(m.object_id)
        mread = None if mo is None or m.object_id not in root else _solids(mo, cache, law)
        if mread is None:
            continue
        cand: dict[str, _t.Any] = {}
        for oid in sorted(comp[root[m.object_id]]):
            if oid in mouth_ids or oid in taken or oid in used or oid not in by_id:
                continue
            read = _solids(by_id[oid], cache, law)
            why = _wing_refusal(read, mread[1] - m.floor_y, mread[0], law)
            if why is None:
                cand[oid] = read[0]
            else:
                notes.append(f"{oid} {path[oid]}: touches mouth {m.object_id}, no wing ({why})")
        reach, wings = [mread[0]], []
        grew = True
        while grew:
            grew = False
            for oid in sorted(set(cand) - set(wings)):
                if any(cand[oid].distance(r) <= eps for r in reach):
                    wings.append(oid)
                    reach.append(cand[oid])
                    grew = True
        notes.extend(f"{oid} {path[oid]}: a wall of mouth {m.object_id}'s group that "
                     f"reaches it through no wing" for oid in sorted(set(cand) - set(wings)))
        used.update(wings)
        if wings:
            out.append(MouthGroup(m, tuple((w, path[w]) for w in sorted(wings))))
    return out, notes


def wing_plates(groups: _t.Sequence[MouthGroup], plates: _t.Mapping[str, tuple]
                ) -> dict[str, tuple]:
    """The PLATE seat of each wing whose mouth is plate-seated
    (``pipeline/rebake_inputs._plate_seats``: ``(y, stations, clearance,
    kind[, anchor zero])``, zero = the surface at the stations less ``y``): the
    mouth's plate with its zero lowered by nothing but the mouth's floor --
    ``y - floor_y`` and an anchor zero ``+ floor_y`` (spec §2 S1)."""
    out: dict[str, tuple] = {}
    for g in groups:
        p = plates.get(g.mouth.object_id)
        if p is None:
            continue
        y, st, *rest = p
        if len(rest) > 2 and rest[2] is not None:
            rest = [*rest[:2], float(rest[2]) + g.mouth.floor_y, *rest[3:]]
        for wid, _res in g.wings:
            out[wid] = (float(y) - g.mouth.floor_y, st, *rest)
    return out


def wing_records(groups: _t.Sequence[MouthGroup],
                 records: _t.Sequence[_t.Mapping[str, _t.Any]], seat: str
                 ) -> list[dict[str, _t.Any]]:
    """A whole-row seat record (``seat``, written as ``OBJECT_MSL`` by
    ``terrain_shaped.row_seats``) for each wing whose mouth's ROW is seated by
    one (spec §2 S2): ``elevation`` the mouth's own record's plus its floor y,
    ``led_by`` the mouth.  A mouth seated at several ends (an entrance)
    leads at its lowest."""
    zero: dict[str, float] = {}
    for r in records:
        oid = str(r.get("id", ""))
        if "elevation" in r and r.get("elevation") is not None and not r.get("led_by"):
            zero[oid] = min(zero.get(oid, float(r["elevation"])), float(r["elevation"]))
    out = []
    for g in groups:
        z = zero.get(g.mouth.object_id)
        if z is None:
            continue
        for wid, res in g.wings:
            out.append({"id": wid, "resource": res, "datum": MOUTH_DATUM, "seat": seat,
                        "elevation": round(z + g.mouth.floor_y, 3),
                        "led_by": g.mouth.object_id})
    return out


def log_lines(icao: str, groups: _t.Sequence[MouthGroup], notes: _t.Sequence[str]
              ) -> list[str]:
    """The build log's lines on the mouth groups."""
    out = [f"[{icao}] mouth groups (#2099): {len(groups)} group(s), "
           f"{sum(len(g.wings) for g in groups)} wing(s)"]
    out += [f"[{icao}]   {g.mouth.reader} {g.mouth.object_id} floor y {g.mouth.floor_y:+.2f}: "
            + ", ".join(w for w, _r in g.wings) for g in groups]
    out += [f"[{icao}]   {n}" for n in notes]
    return out


def mouths_of(pm) -> list[Mouth]:
    """THE MOUTHS the planar readers took (spec §1 M1-M3): every hard-deck
    bridge (``PlanarMap.decks``; its floor the frame's bottom, the road the
    cut is made to), every roofed portal seated at its pinned floor (its zero
    IS the floor) and every entrance face (its floor the mouth's pinned
    floor, ``Tunnel.mouth_z``, under the zero its seat states)."""
    out: dict[str, Mouth] = {}
    for db in getattr(pm, "decks", ()) or ():
        out.setdefault(str(db.object_id), Mouth(str(db.object_id), float(db.bottom_y),
                                                "hard-deck bridge"))
    for tn in getattr(pm, "structures", ()) or ():
        ps = getattr(tn, "portal_seat", ()) or ()
        if not ps or not getattr(tn, "portal", ""):
            continue
        floor_y = float(tn.mouth_z) - float(ps[1])
        out.setdefault(str(tn.portal), Mouth(str(tn.portal), floor_y,
                                             "entrance face" if len(ps) > 2 else "roofed portal"))
    return [out[k] for k in sorted(out)]
