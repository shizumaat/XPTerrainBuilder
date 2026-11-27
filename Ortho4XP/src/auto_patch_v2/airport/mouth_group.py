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

from ..model.deck_ends import end_mid
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
    #: a hard deck's end lines: ``(the end's middle, its top over the zero)``
    #: each -- the mouth's top where a lining wall meets it (#2099 R3 E3)
    ends: tuple = ()
    #: the road through the mouth (a polyline, frame metres): a hard deck's
    #: (``DeckBridge.road``), a portal's bore line (its axis) -- the line a
    #: wall LINES (#2099 R3 E2); ``()`` where none is read
    road: tuple = ()


@_dc.dataclass(frozen=True)
class MouthGroup:
    """A mouth and its wings, ``(placement id, resource)`` each; ``offsets``
    the RAMP WINGS among them (``airport/ramp_wing``, #2099 G4 S), ``(id,
    Δ)`` each: a ramp wing's zero stands Δ over a wing's."""

    mouth: Mouth
    wings: tuple[tuple[str, str], ...]
    offsets: tuple[tuple[str, float], ...] = ()

    def offset(self, wid: str) -> float:
        """Wing ``wid``'s zero over the group's wing zero (0 but a ramp wing)."""
        return dict(self.offsets).get(wid, 0.0)

    @property
    def ramps(self) -> frozenset[str]:
        """The ramp wings' ids."""
        return frozenset(w for w, _d in self.offsets)


def _solids(o: _obj8.PlacedObject, cache: _obj8.ResourceCache, law):
    """``(placed plan, top y, hard-deck triangles)`` of ``o``'s genuine solids
    (frame metres), or ``None`` with none.  The union is the RESOURCE's
    (:func:`_resource_solids`); only the placement is applied per call."""
    local = None if o.resolved is None else _resource_solids(o.resolved, cache)
    if local is None:
        return None
    plan = _fe.enter([local[0]], _obj8.placement_affine(o.xy, o.heading_deg),
                     _fe.quantum(law))[0]
    if plan is None or plan.is_empty:
        return None
    return plan, local[1], local[2]


def _resource_solids(path: str, cache: _obj8.ResourceCache):
    """``(plan union in the object's own frame, top y, hard-deck triangles)``
    of resource ``path``'s genuine solids, or ``None`` with none -- read once
    per resource on ``cache`` (#2176: the mouth groups are asked once per
    mouth, per pass and per stage, of the same pieces)."""
    memo = getattr(cache, "solids_memo", None)
    if memo is not None and path in memo:
        return memo[path]
    g = cache.geometry(path)
    comps = [] if g is None else cache.genuine(path)
    got = None
    if g is not None and comps:
        tris = np.concatenate([c.tris for c in comps])
        got = (_fe.union(_bulk_polys(g.vertices, tris), "mouth_group._solids"),
               float(g.vertices[np.unique(tris), 1].max()), int(len(g.hard_deck)))
    if memo is not None:
        memo[path] = got
    return got


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
    why = _wall_refusal(read, law)
    if why is not None:
        return why
    plan, top, _hard = read
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


def _wall_refusal(read, law) -> "str | None":
    """W1 (:func:`_wing_refusal`): why the piece read ``read`` is not all
    walls -- no solid, a hard deck, or a plan ``[tunnel.object]
    wall_face_max_thickness_m`` thick somewhere -- or ``None``."""
    ob = law.tables.structures.tunnel.object
    if read is None:
        return "no genuine solid"
    plan, _top, hard = read
    if hard:
        return "it carries a hard deck"
    if not plan.buffer(-0.5 * float(ob.wall_face_max_thickness_m)).is_empty:
        return f"no wall: its plan is {ob.wall_face_max_thickness_m:g} m thick somewhere"
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
                 taken: _t.AbstractSet[str] = frozenset(),
                 roads: _t.Sequence[_t.Sequence[tuple[float, float]]] = ()
                 ) -> tuple[list[MouthGroup], list[str]]:
    """THE MOUTH GROUPS (spec §1) and one note per touching piece refused.

    A candidate stands in its mouth's ε-contact component of the load
    partition, is no mouth and is not ``taken`` (seated by another rule: one
    authority per row).  It is a WING when :func:`_wing_refusal` passes it and
    its plan comes within ``[rebake] contact_epsilon_m`` of the mouth's plan or
    of a wing already joined (ONE HOP: a chain runs only through wings).  A
    wing joins one mouth, the first by id.

    A WALL LINING THE MOUTH'S ROAD (``Mouth.road``) joins too (#2099 R3 E,
    :func:`_lining`), and a RAMP WING butting a wing's end, its zero offset
    (``airport/ramp_wing``, #2099 G4 S; ``roads`` the mapped roads)."""
    if partition is None or not mouths:
        return [], []
    eps = float(law.tables.structures.rebake.contact_epsilon_m)
    root, path = _contact_roots(partition)
    by_id = {str(o.id): o for o in objects}
    comp: dict[str, list[str]] = collections.defaultdict(list)
    for oid, r in root.items():
        comp[r].append(oid)
    mouth_ids = {m.object_id for m in mouths}
    notes: list[str] = []
    used: set[str] = set()
    found: list[tuple[Mouth, tuple, list[str]]] = []
    for m in sorted(mouths, key=lambda q: q.object_id):
        mo = by_id.get(m.object_id)
        mread = None if mo is None else _solids(mo, cache, law)
        if mread is None:
            continue
        wings: list[str] = []
        found.append((m, mread, wings))
        if m.object_id not in root:
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
        reach = [mread[0]]
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
    notes.extend(_lining(found, objects, by_id, cache, law, mouth_ids | set(taken) | used))
    from .ramp_wing import ramp_wings
    ramps, rnotes = ramp_wings(found, objects, cache, law,
                               mouth_ids | set(taken) | {w for _m, _r, ws in found for w in ws},
                               roads)
    notes.extend(rnotes)
    path.update({str(o.id): str(o.path) for o in objects if str(o.id) not in path})
    out = []
    for m, _r, wings in found:
        mine = sorted((rid, j.offset) for rid, j in ramps.items() if j.mouth == m.object_id)
        if wings:
            ids = sorted(wings + [r for r, _d in mine])
            out.append(MouthGroup(m, tuple((w, path[w]) for w in ids), tuple(mine)))
    return out, notes


def _lining(found, objects, by_id, cache, law, closed: _t.AbstractSet[str]) -> list[str]:
    """THE WALLS LINING A MOUTH'S ROAD (#2099 R3 E): a piece that passes
    :func:`_wing_refusal` against a mouth, is in no group (``closed``) and
    within ``[tunnel] dual_carriageway_max_separation_m`` of its plan (E1)
    joins the NEAREST such mouth's wings (``found``, in place) when it lines
    the road through it (E2, :func:`_lines_road`) and stands at the mouth's
    seat (E3, :func:`_seat_refusal`).  One hop: never through a lining wall.
    One note per join and per refusal."""
    from .wall_lines import wall_line_feet
    sep = float(law.tables.structures.tunnel.dual_carriageway_max_separation_m)
    reads = [(m, mr, wings, shapely.LineString(m.road)) for m, mr, wings in found
             if len(m.road) >= 2]
    if not reads:
        return []
    boxes = [(str(o.id), o.plan_bbox) for o in objects
             if str(o.id) not in closed and getattr(o, "plan_bbox", None) is not None
             and not o.plan_bbox.is_empty]
    tree = shapely.STRtree([b for _i, b in boxes]) if boxes else None
    near = set()
    for _m, mr, _w, _r in reads:
        if tree is not None:
            near.update(boxes[int(k)][0] for k in tree.query(mr[0], predicate="dwithin",
                                                             distance=sep))
    joined_tops = {m.object_id: [_solids(by_id[w], cache, law)[1] for w in wings]
                   for m, _mr, wings, _r in reads}

    def top_there(m: Mouth, mr, lines) -> float:
        """The mouth's top over its floor where the wall meets it: a hard
        deck's nearer end line's top, else its solids' top."""
        if not m.ends or not lines or not lines[0][1]:
            return mr[1] - m.floor_y
        x, y = lines[0][1][0][:2]
        return min(m.ends, key=lambda e: (e[0][0] - x) ** 2 + (e[0][1] - y) ** 2)[1] - m.floor_y
    notes: list[str] = []
    for oid in sorted(near):
        o = by_id[oid]
        read = _solids(o, cache, law)
        best = None
        for m, mr, wings, road in reads:
            if read is None or read[0].distance(mr[0]) > sep:
                continue
            why = _wing_refusal(read, mr[1] - m.floor_y, mr[0], law)
            lines = wall_line_feet(o, cache, law, mr[0]) if why is None else []
            why = why or _lines_road(lines, read[0], road, sep) \
                or _seat_refusal(lines, top_there(m, mr, lines), joined_tops[m.object_id], law)
            if why is not None:
                notes.append(f"{oid} {o.path}: within {sep:g} m of mouth {m.object_id}, "
                             f"no lining wall ({why})")
                continue
            d = read[0].distance(mr[0])
            if best is None or d < best[0]:
                best = (d, m, wings)
        if best is not None:
            best[2].append(oid)
            notes.append(f"{oid} {o.path}: lines mouth {best[1].object_id}'s road "
                         f"{best[0]:.1f} m from it -- a wall of its group (#2099 R3 E)")
    return notes


def _side(road, p) -> float:
    """The signed side of point ``p`` against the polyline ``road``."""
    s = road.project(p)
    a, b = road.interpolate(max(0.0, s - 0.5)), road.interpolate(min(road.length, s + 0.5))
    return (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x)


def _lines_road(lines, plan, road, sep: float) -> "str | None":
    """E2: why the wall lines ``lines`` (plan ``plan``) do NOT line ``road``
    -- at least half their length within ``sep`` of it and all of the plan on
    one side of it -- or ``None``."""
    pts = [shapely.Point(x, y) for _ln, st in lines for x, y, *_r in st]
    if not pts:
        return "no wall line"
    share = sum(road.distance(p) <= sep for p in pts) / len(pts)
    if share < 0.5:
        return f"{100.0 * share:.0f} % of its length within {sep:g} m of the mouth's road"
    sides = [_side(road, shapely.Point(c)) for q in getattr(plan, "geoms", [plan])
             for c in q.exterior.coords]
    if min(sides) < -1e-6 and max(sides) > 1e-6:
        return "it stands on both sides of the mouth's road"
    return None


def _seat_refusal(lines, mouth_top: float, wing_tops: _t.Sequence[float], law
                  ) -> "str | None":
    """E3: at its end nearest the mouth (the first station of its nearest
    line) a lining wall's foot stands no more than ``plate_bin_m`` over its
    zero and its top within ``plate_bin_m`` of the mouth's top over its
    floor or of a joined wing's top -- or why not."""
    bin_m = float(law.tables.structures.tunnel.object.plate_bin_m)
    if not lines or not lines[0][1]:
        return "no wall line"
    *_xy, foot, top = lines[0][1][0]
    if foot > bin_m:
        return f"its foot {foot:+.2f} over its zero at the mouth's end"
    if not any(abs(top - t) <= bin_m for t in (mouth_top, *wing_tops)):
        return (f"its top {top:+.2f} at the mouth's end, neither the mouth's "
                f"{mouth_top:.2f} nor a wing's")
    return None


def wing_plates(groups: _t.Sequence[MouthGroup], plates: _t.Mapping[str, tuple]
                ) -> dict[str, tuple]:
    """The PLATE seat of each wing whose mouth is plate-seated
    (``pipeline/rebake_inputs._plate_seats``: ``(y, stations, clearance,
    kind[, anchor zero])``, zero = the surface at the stations less ``y``): the
    mouth's plate with its zero lowered by nothing but the mouth's floor --
    ``y - floor_y`` and an anchor zero ``+ floor_y`` (spec §2 S1); a ramp
    wing's by its offset too (``MouthGroup.offset``, #2099 G4 S)."""
    out: dict[str, tuple] = {}
    for g in groups:
        p = plates.get(g.mouth.object_id)
        if p is None:
            continue
        y, st, *rest = p
        for wid, _res in g.wings:
            lift = g.mouth.floor_y + g.offset(wid)
            more = [*rest[:2], float(rest[2]) + lift, *rest[3:]] \
                if len(rest) > 2 and rest[2] is not None else rest
            out[wid] = (float(y) - lift, st, *more)
    return out


def wing_records(groups: _t.Sequence[MouthGroup],
                 records: _t.Sequence[_t.Mapping[str, _t.Any]], seat: str
                 ) -> list[dict[str, _t.Any]]:
    """A whole-row seat record (``seat``, written as ``OBJECT_MSL`` by
    ``terrain_shaped.row_seats``) for each wing whose mouth's ROW is seated by
    one (spec §2 S2): ``elevation`` the mouth's own record's plus its floor y
    (and a ramp wing's offset, #2099 G4 S), ``led_by`` the mouth.  A mouth
    seated at several ends (an entrance) leads at its lowest."""
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
                        "elevation": round(z + g.mouth.floor_y + g.offset(wid), 3),
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
        ends = tuple((end_mid(st), float(top)) for st, top in
                     ((getattr(db, "seats_a", ()), getattr(db, "top_a", 0.0)),
                      (getattr(db, "seats_b", ()), getattr(db, "top_b", 0.0))) if st)
        out.setdefault(str(db.object_id), Mouth(str(db.object_id), float(db.bottom_y),
                                                "hard-deck bridge", ends,
                                                tuple(getattr(db, "road", ()) or ())))
    for tn in getattr(pm, "structures", ()) or ():
        ps = getattr(tn, "portal_seat", ()) or ()
        if not ps or not getattr(tn, "portal", ""):
            continue
        floor_y = float(tn.mouth_z) - float(ps[1])
        out.setdefault(str(tn.portal), Mouth(str(tn.portal), floor_y,
                                             "entrance face" if len(ps) > 2 else "roofed portal",
                                             road=tuple(tuple(p) for p in
                                                        getattr(tn, "axis", ()) or ())))
    return [out[k] for k in sorted(out)]
