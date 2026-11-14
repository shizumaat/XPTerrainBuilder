"""THE FREE BRIDGE'S READ (#2065; spec ``2065-bridge-class-A1.md`` §A4
S1 / S2 / S4): the thin ``planar`` caller of the positive witness
(``airport/bridge_witness``), like ``planar/deck_stack_attach``.

* PACK STAGE (:func:`attach_free_bridges`, after ``attach_deck_stacks``):
  every frame (``deck_bridge._frames``: one anchor, one heading) holding a
  ``flag`` / ``signature`` deck is read W1-W7 + W4b; a deck of a deck stack,
  a plate with apt.dat pavement or a runway on it (``deck_stack._Airside``:
  class A's witness) and an all-deck frame (22d / 22p keep it,
  ``placement_family.frame_is_bridge``) are not read.  W1 reads ``highway`` /
  ``railway`` routes only.  The decks the classifier calls ``free_bridge``
  (``airport/bridge_class``) become ``Airport.free_bridges``, one
  :class:`~..model.free_bridge.FreeBridge` per group of touching decks.
* PLANAR STAGE (:func:`admitted`): the readers ahead of a free bridge in the
  class order that only the planar stage holds take theirs first — a frame
  holding a pack object cut (10-26d), a frame of a hard-deck bridge
  (``PlanarMap.decks``, class A) — and a frame with a body beside a
  building is refused (22n, ``deck_bridge._beside_a_building``, W6's
  building half, which reads the classification): ONE test per bridge
  against the UNION of the rings of every free deck of its frame (A2).
  R3 mints free stacks from ``PlanarMap.free_bridges`` (admitted), never
  ``Airport.free_bridges``.  ``planar/overpass_deck``
  then takes the kept decks as ``taken`` (S4).
* PUBLICATION (``model/free_bridge.published``): each kept deck's route
  ends in ``(lat, lon)`` for the rebake plan (``pipeline/rebake_inputs``).

One note per deck read or refused, with the witness that decided it.
Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..airport import bridge_frame as _bf
from ..airport import bridge_witness as _bw
from ..model.free_bridge import FREE_PREFIX, FreeBridge, FreeDeck, FreeEnd

__all__ = ["attach_free_bridges", "read_bridges", "bridges_of", "admitted", "plated",
           "planar_stacks", "log_line"]


def _ring(o) -> Polygon:
    from ..airport.rebake_plan import _deck_ring_xy
    p = Polygon(_deck_ring_xy(o))
    if not p.is_valid:
        p = p.buffer(0)
    if p.geom_type != "Polygon":
        p = max(getattr(p, "geoms", [p]), key=lambda g: g.area)
    return p


def _name(o) -> str:
    return f"{o.id} {str(o.path).rsplit('/', 1)[-1]}"


def _routes(ways: _t.Sequence) -> list:
    """W1's ways: ``highway`` / ``railway`` (a taxiway route is class A's)."""
    return [w for w in ways if len(w.points) >= 2
            and ("highway" in (w.tags or {}) or "railway" in (w.tags or {}))]


class _Read:
    """The airport's ways, ground, water and W4b reader, once per read."""

    def __init__(self, airport, objects, cache, law) -> None:
        from ..airport.dem import dem_z_many
        self.law, self.cache = law, cache
        self.ways = _routes(getattr(airport, "osm_ways_mapped", None) or airport.osm_ways)
        dem = getattr(airport, "dem", None)
        self.dem = dem
        self.ground = None if dem is None else (
            lambda xs, ys: dem_z_many(dem, np.asarray(xs, float), np.asarray(ys, float)))
        normal = float(law.tables.structures.bridge.deck_plate_normal_y_min)
        self.by_id = {str(o.id): o for o in objects}
        placed = [(str(o.id), self.geometry(o), o.xy, float(o.heading_deg or 0.0),
                   getattr(getattr(o, "plan_bbox", None), "bounds", None))
                  for o in objects if o.resolved]
        self.under = _bf.Under(placed, self._datum, normal)

    def geometry(self, o):
        return self.cache.geometry(o.resolved) if o.resolved else None

    def _datum(self, oid: str) -> tuple[float, bool]:
        o = self.by_id[oid]
        g = 0.0 if self.ground is None else float(self.ground([o.xy[0]], [o.xy[1]])[0])
        ok = self.ground is not None and math.isfinite(g)
        return (g if ok else 0.0) + float(o.agl_m or 0.0), ok

    def water(self, box: tuple) -> list:
        fn = getattr(self.dem, "water_geometry", None)
        w = fn(box) if fn is not None else None
        return [] if w is None or w.is_empty else [w]


def _frame_witness(decks: list, frame: list, rd: _Read) -> dict:
    """W1-W7 + W4b over one frame (``bridge_witness.frame_witness``)."""
    law = rd.law
    normal = float(law.tables.structures.bridge.deck_plate_normal_y_min)
    plates = {}
    for d in decks:
        up = _bw.up_faces(_bf.solid_faces(rd.geometry(d), d.xy, d.heading_deg), normal)
        plates[str(d.id)] = (_ring(d), up, d.deck_kind)
    if not any(not isinstance(_bw.route_of(r, rd.ways, law), str)
               for r, _u, _k in plates.values()):
        return {k: _bw.Witness(None, failed="W1 route: no mapped route") for k in plates}
    b = np.array([r.bounds for r, _u, _k in plates.values()])
    box = (b[:, 0].min() - 2.0, b[:, 1].min() - 2.0, b[:, 2].max() + 2.0, b[:, 3].max() + 2.0)
    placed = {str(q.id): _bf.solid_faces(rd.geometry(q), q.xy, q.heading_deg) for q in frame}
    faces = _bf.faces_in_box(placed.values(), box)
    bodies = {k: _bf.body_points(f) for k, f in placed.items() if len(f)}
    own = str(decks[0].id)
    return _bw.frame_witness(plates, faces, bodies, rd.ways, law, rd.ground, rd.water(box),
                             under=rd.under.for_unit(own, frozenset(placed)))


def _end(e) -> FreeEnd:
    line = tuple((float(x), float(y)) for x, y in (e.line or (e.point,)))
    return FreeEnd(line, float(e.top), (float(e.out[0]), float(e.out[1])), bool(e.land),
                   0.0 if math.isnan(e.run_on) else float(e.run_on))


def bridges_of(rings: _t.Mapping[str, Polygon], witnesses: _t.Mapping[str, _t.Any],
               free: _t.Collection[str], members: _t.Sequence[str], touch_m: float
               ) -> tuple[FreeBridge, ...]:
    """The free decks ``free`` of one frame (their ``rings`` and
    ``witnesses``) as bridges: decks whose rings come within ``touch_m``,
    transitively, are ONE bridge (22o); ``members`` every placement of the
    frame."""
    ids = sorted(free)
    root = {k: k for k in ids}

    def find(k: str) -> str:
        while root[k] != k:
            root[k] = root[root[k]]
            k = root[k]
        return k
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if rings[a].distance(rings[b]) <= touch_m:
                root[find(b)] = find(a)
    groups: dict[str, list[str]] = {}
    for k in ids:
        groups.setdefault(find(k), []).append(k)
    out = []
    for g in groups.values():
        decks = []
        for k in g:
            w = witnesses[k]
            decks.append(FreeDeck(k, tuple((float(x), float(y))
                                           for x, y in rings[k].exterior.coords[:-1]),
                                  tuple(int(x) for x in (w.route.ways if w.route else ())),
                                  tuple(_end(e) for e in w.ends), str(w.joined or "")))
        out.append(FreeBridge(FREE_PREFIX + g[0], tuple(members), tuple(decks)))
    return tuple(out)


@_dc.dataclass(frozen=True)
class _Frame:
    """A frame as ``frame_is_bridge`` reads a plan unit (its members)."""

    members: tuple = ()


def _read_free_bridges(airport, objects, cache, law
                       ) -> tuple[tuple[FreeBridge, ...], tuple[FreeBridge, ...], list[str]]:
    """``(every free bridge of the pack, every KEPT bridge — the witness-
    holding decks of all-deck frames (#2065 A3 rule 1, RULINGS 2026-11-14d),
    one note per deck read)`` (module doc, pack stage)."""
    from ..airport.bridge_class import DeckFacts, classify
    from ..airport.deck_stack import _Airside
    from ..airport.placement_family import frame_is_bridge
    from .deck_bridge import _frames
    if not objects or cache is None or law is None or getattr(airport, "frame", None) is None:
        return (), (), []
    from ..model.deck_stack import TRENCH
    st = law.tables.structures
    stacked = {str(pid) for s in getattr(airport, "deck_stacks", ()) or ()
               if s.kind == TRENCH for pid, _r in s.members}
    airside = _Airside(airport)
    rd: "_Read | None" = None
    out: list[FreeBridge] = []
    kept: list[FreeBridge] = []
    notes: list[str] = []
    for decks, frame in _frames(objects, float(st.tunnel.object.cover_placement_tol_m)):
        decks = [d for d in decks if d.deck_top_z is not None and str(d.id) not in stacked
                 and not airside.meets(d.hard_deck)]
        if not decks:
            continue
        # an all-deck frame keeps 22d / 22p's seat; its witness-holding decks
        # are KEPT bridges, their ends graded (#2065 A3 rule 1)
        all_deck = frame_is_bridge(_Frame(tuple(frame)))
        rd = rd or _Read(airport, objects, cache, law)
        wit = _frame_witness(decks, frame, rd)
        free = []
        for d in decks:
            v = classify(DeckFacts(witness=wit[str(d.id)]))
            if v.cls == "free_bridge":
                free.append(str(d.id))
            if not wit[str(d.id)].failed.startswith("W1 route"):
                cls = ("kept_bridge (all-deck frame)" if all_deck and v.cls == "free_bridge"
                       else v.cls)
                notes.append(f"{_name(d)}: {cls} ({v.reason})")
        if free:
            (kept if all_deck else out).extend(
                bridges_of({str(d.id): _ring(d) for d in decks}, wit, free,
                           [str(q.id) for q in frame], float(st.placement.footprint_touch_m)))
    return tuple(out), tuple(kept), notes


def read_bridges(airport, objects, cache, law) -> tuple[_t.Any, tuple, list[str]]:
    """``(airport with free_bridges, kept_bridges and their stacks, every
    bridge's end read — minted or not, notes)``: :func:`_read_free_bridges`,
    then each bridge's zero and land-end states (#2065 A3,
    ``airport/bridge_stack``); a bridge with a GRADED end is minted a stack
    and the ways rewritten (``airport/deck_stack.with_bridge_stacks``).  A
    free bridge rule 10 refuses leaves ``free_bridges`` (today's path)."""
    from ..airport.bridge_stack import bridge_stacks, log_lines
    from ..airport.deck_stack import with_bridge_stacks
    got, kept, notes = _read_free_bridges(airport, objects, cache, law)
    if not (got or kept or getattr(airport, "free_bridges", ())
            or getattr(airport, "kept_bridges", ())):
        return with_bridge_stacks(airport, (), law), (), notes
    airport = _dc.replace(airport, free_bridges=got, kept_bridges=kept)
    stacks, every, refused, more = bridge_stacks(airport, objects, cache, law)
    notes += more + [ln.split("] ", 2)[-1] for ln in log_lines("", every)]
    if refused:
        airport = _dc.replace(airport, free_bridges=tuple(
            fb for fb in got if fb.id not in refused))
    return with_bridge_stacks(airport, stacks, law), every, notes


def attach_free_bridges(airport, objects, cache, law, notes_out: "list | None" = None):
    """``airport`` with its free and kept bridges read and their stacks
    minted (:func:`read_bridges`)."""
    airport, _every, notes = read_bridges(airport, objects, cache, law)
    if notes_out is not None:
        notes_out.extend(notes)
    return airport


def admitted(bridges: _t.Sequence[FreeBridge], objects, classification, airport,
             decks=(), cut_objects=()) -> tuple[tuple[FreeBridge, ...], list[str]]:
    """``(the free bridges no earlier planar reader takes, notes)`` (module
    doc, planar stage): ``decks`` the hard-deck bridges read
    (``DeckBridge.members``), ``cut_objects`` every pack object cut's
    placement ids."""
    if not bridges:
        return (), []
    from .deck_bridge import CellRoles, _beside_a_building
    roles = CellRoles(classification, airport) if classification is not None else None
    hard = {str(m) for db in decks or () for m in (*db.members, db.object_id)}
    cut = {str(o) for o in cut_objects or ()}
    by_id = {str(o.id): o for o in objects or ()}
    # 22n reads the UNION of every free deck's ring of a frame (A2): in a
    # bridge of several decks each deck's bodies stand "outside" the others
    frame_rings: dict[frozenset, list] = {}
    for fb in bridges:
        frame_rings.setdefault(frozenset(fb.members), []).extend(
            Polygon(d.ring) for d in fb.decks)
    out, notes = [], []
    for fb in bridges:
        mem = set(fb.members)
        why = ""
        if mem & cut:
            why = "its frame holds a pack object cut (10-26d): cut_deck"
        elif mem & hard:
            why = "its frame is a hard-deck bridge's (class A): airside_hard_deck"
        elif roles is not None:
            frame = [by_id[m] for m in fb.members if m in by_id]
            if _beside_a_building(frame, unary_union(frame_rings[frozenset(fb.members)]),
                                  roles):
                why = "W6 free frame: a body stands beside a building (22n): attached_bridge"
        if why:
            notes.append(f"{fb.id}: not a free bridge -- {why}")
            continue
        out.append(fb)
        notes.append(f"{fb.id}: a free bridge of {len(fb.decks)} deck(s) "
                     f"{list(fb.deck_ids())}; its zero at its land ends (RULINGS 2026-10-22m)")
    return tuple(out), notes


def plated(bridges: _t.Sequence[FreeBridge], basins=(), objects=()
           ) -> tuple[tuple[FreeBridge, ...], list[str]]:
    """``(the free bridges no deck of which carries a split-level or walled
    plate, notes)`` (#2065 A3 rule 1: A1's ``plated_deck``, OTHH B05 — listed,
    nothing built, owner Q3 (a); its plate's reader seats it).  Its stack,
    if it had one, is dropped by :func:`planar_stacks`."""
    if not bridges:
        return (), []
    split = {str(m) for b in basins or () if getattr(b, "kind", "") == "split_level"
             for m in (*getattr(b, "member_ids", ()), getattr(b, "witness_id", ""))}
    walled = {str(o.id) for o in objects or () if getattr(o, "walled_plate", None) is not None}
    out, notes = [], []
    for fb in bridges:
        hit = sorted(set(fb.deck_ids()) & (split | walled))
        if hit:
            notes.append(f"{fb.id}: plated_deck {hit} (split-level / walled plate) — listed, "
                         "nothing graded (owner Q3 (a))")
            continue
        out.append(fb)
    return tuple(out), notes


def planar_stacks(stacks, free: _t.Sequence[FreeBridge], classification
                  ) -> tuple[tuple, list[str]]:
    """``(the free / kept stacks the planar stage keeps, notes)`` (#2065 A3
    C2 N2, rule 3): a FREE stack only of a bridge in ``free`` (admitted, no
    plated deck); a GRADED end whose path enters a gap-mint LOT piece within
    its run is HELD, ``end_on_lot`` (``model/planar.gap_part_kind``; built as
    today, 14f (4)); a stack left with no graded end is dropped.  A free
    bridge whose stack is dropped here is noted
    ``free_stack_refused_at_planar``."""
    from shapely.geometry import Point, Polygon

    from ..geom.deck_ground import path_line
    from ..model.deck_stack import FREE, TRENCH
    from ..model.planar import gap_part_kind
    ok = {str(fb.id) for fb in free}
    lots = [Polygon(c.ring, c.holes) for c in getattr(classification, "cells", ()) or ()
            if gap_part_kind(getattr(c, "ref", "")) == "lot" and len(c.ring) >= 3]
    out, notes = [], []
    for st in stacks:
        if st.kind == TRENCH:
            continue
        if st.kind == FREE and st.bridge not in ok:
            notes.append(f"{st.id}: free_stack_refused_at_planar (its bridge was not admitted "
                         "or carries a plate)")
            continue
        ends = []
        for e in st.ends:
            line = path_line(e, e.run) if e.state == "graded" else None
            hit = None if line is None else next((p for p in lots if p.intersects(line)), None)
            if hit is not None:
                meet = hit.intersection(line)
                s = min((line.project(Point(c)) for g in getattr(meet, "geoms", [meet])
                         for c in getattr(g, "coords", [])), default=0.0)
                e = _dc.replace(e, state="held",
                                why=f"end_on_lot: the path enters a lot piece at {s:.0f} m")
                notes.append(f"{st.id}: {e.object_id} end {e.side} {e.why}")
            ends.append(e)
        st = _dc.replace(st, ends=tuple(ends))
        if not st.graded_ends():
            notes.append(f"{st.id}: no GRADED end left at the planar stage — no stack"
                         + ("; free_stack_refused_at_planar" if st.kind == FREE else ""))
            continue
        out.append(st)
    return tuple(out), notes


def log_line(icao: str, bridges: _t.Sequence[FreeBridge], seconds: "float | None" = None) -> str:
    """The build log's one line on the free bridges read."""
    took = "" if seconds is None else f" in {seconds:.2f} s"
    decks = [d.object_id for fb in bridges for d in fb.decks]
    return (f"[{icao}] free bridges (#2065): {len(bridges)} bridge(s), {len(decks)} deck(s)"
            f"{took}" + (f" {decks}" if decks else ""))
