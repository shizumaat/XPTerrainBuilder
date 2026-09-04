"""THE RE-SEAT PLAN (RULINGS 2026-09-04i 04f-1): the units and witnesses
of an airport's pack, from the loader's AUTHORED reading of the objects
(``airport/pack.py`` restore-before-read).  Runs at PATCH time inside the
pipeline; the plan is the tile build's ``o4_v2_rebake_<ICAO>.json``
sidecar, seated after the mesh by ``emit/rebake.py``.  Law:
``structures.toml [rebake]``.  No environment is read here.
"""
from __future__ import annotations

import math
import os
import typing as _t

import numpy as np

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY
from ..model.rebake import Foot, Member, RebakePlan, Unit
from . import deck_signature as _deck
from . import obj8 as _obj8
from .pack import live_path_of

__all__ = ["plan", "DeckDatum"]

#: ``deck_datum(ring_xy) -> z | None``: the SOLVED surface's value at a
#: deck ring (``emit.rebake.deck_datum_from_surface`` bound to the emitted
#: surface by the pipeline); ``None`` = read the mesh at the ring instead.
DeckDatum = _t.Callable[[_t.Sequence[XY]], "float | None"]


def _inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) \
            == os.path.abspath(root)
    except ValueError:
        return False


def _thin(rows: np.ndarray, n: int) -> np.ndarray:
    """At most ``n`` rows, evenly spaced over the rows sorted by plan
    position (deterministic; a witness set, not a random sample)."""
    if rows.shape[0] <= n:
        return rows
    order = np.lexsort((rows[:, 2], rows[:, 0]))
    pick = np.linspace(0, rows.shape[0] - 1, n).round().astype(int)
    return rows[order][pick]


def _feet(geom: _obj8.ObjGeometry, comps: list[_obj8.Component], o: _obj8.PlacedObject,
          band_m: float, per_comp: int, per_member: int, to_ll_batch
          ) -> tuple[Foot, ...]:
    """The contact band of every genuine component, thinned per component
    and per member, in world position with its authored ``y``.
    ``to_ll_batch(xs, ys) -> (lats, lons)`` over arrays (one projection
    call per member: OTHH has 1,116 members)."""
    v = geom.vertices
    parts: list[np.ndarray] = []
    if not comps:
        return ()
    # THE OBJECT'S OWN LOWEST BAND: its feet are the genuine components
    # reaching within ``band_m`` of its lowest solid vertex (a roof piece
    # that is its own component has no feet of its own — v1 seats a rigid
    # unit on its GROUND-TOUCHING parts; measured OTHH AuxBuilding_02:
    # 162 components, 20 of them roof parts at y 7.5–8.9)
    floor = min(c.min_y for c in comps)
    for c in comps:
        if c.min_y > floor + band_m:
            continue
        ids = np.unique(np.asarray(c.tris).reshape(-1))
        pts = v[ids]
        pts = pts[pts[:, 1] <= floor + band_m]
        if pts.shape[0] == 0:
            continue
        parts.append(_thin(pts, per_comp))
    if not parts:
        return ()
    pts = _thin(np.concatenate(parts), per_member)
    h = math.radians(o.heading_deg)
    sn, cs = math.sin(h), math.cos(h)
    ex = o.xy[0] + pts[:, 0] * cs - pts[:, 2] * sn
    ny = o.xy[1] - (pts[:, 0] * sn + pts[:, 2] * cs)
    lats, lons = to_ll_batch(ex, ny)
    return tuple(Foot(float(la), float(lo), float(y))
                 for la, lo, y in zip(lats, lons, pts[:, 1].tolist()))


def _batch_to_ll(frame):
    """``(xs, ys) -> (lats, lons)`` over arrays, the frame's own CRS."""
    from pyproj import Transformer
    inv = Transformer.from_crs(frame.crs, "EPSG:4326", always_xy=True)

    def f(xs, ys):
        lons, lats = inv.transform(np.asarray(xs, dtype=float), np.asarray(ys, dtype=float))
        return np.asarray(lats, dtype=float), np.asarray(lons, dtype=float)
    return f


def plan(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
         cache: _obj8.ResourceCache, law: Law, deck_datum: DeckDatum | None = None,
         exclude: _t.Collection[str] = (),
         below_grade: _t.Sequence[tuple[object, _t.Collection[str]]] = ()) -> RebakePlan:
    """The units and witnesses for ``airport``'s pack (see module doc).
    ``objects`` are the planar pass's placed objects (read from the
    AUTHORED files, the deck signature applied); ``deck_datum`` the
    solved surface's reading at a flagged deck ring; ``exclude`` the
    placement ids the TERRAIN adapted to (the basin facilities, RULINGS
    2026-08-26 / v1 ruling R4) — never re-seated, and with
    ``[rebake] basin_family_excluded`` neither is any member of their
    anchor family (m6a Q3: Dewatering_01's rim pieces go with the pit);
    ``below_grade`` the emitted below-grade regions ``(frame polygon,
    owner ids)`` — a CANDIDATE plate of a foreign family over one is a
    deck (``deck_signature.promote``)."""
    rb = law.tables.structures.rebake
    admission_m = law.tables.structures.basin.admission_depth_m
    excluded = set(exclude)
    if below_grade:
        owners = {oid for _r, ids in below_grade for oid in ids}
        foreign = [o for o in objects if o.id not in owners]
        keep = {o.id for o in foreign}
        promoted, _n = _deck.promote(foreign, [r for r, _ids in below_grade])
        by_id = {o.id: o for o in promoted}
        objects = [by_id.get(o.id, o) if o.id in keep else o for o in objects]
    fam_of = {o.id: _deck.family_key(o) for o in objects if o.resolved is not None}
    if rb.basin_family_excluded:
        basin_keys = {fam_of[oid] for oid in excluded if oid in fam_of}
        excluded |= {o.id for o in objects if fam_of.get(o.id) in basin_keys}
    deck_keys = {fam_of[o.id] for o in objects
                 if o.resolved is not None and o.deck_kind in ("flag", "signature")}
    to_xy, to_ll = airport.frame.transformers()
    to_ll_batch = _batch_to_ll(airport.frame)
    apt = airport.pack.apt_dat_path
    pack_root = os.path.dirname(os.path.dirname(apt)) if apt else ""
    counts: dict[str, int] = {"placements": 0, "unresolved": 0, "stock": 0,
                              "outside_pack": 0, "msl": 0, "multi_anchor": 0,
                              "units": 0, "members": 0, "deck_members": 0,
                              "feet": 0, "no_feet": 0, "terrain_adapted": 0,
                              "below_grade": 0, "deck_families": len(deck_keys),
                              "signature_decks": sum(1 for o in objects
                                                     if o.deck_kind == "signature")}
    skipped: dict[str, str] = {}
    anchors_by_resource: dict[str, set[tuple[float, float, float]]] = {}
    keyed: list[tuple[tuple[float, float, float], _obj8.PlacedObject]] = []
    for o in objects:
        counts["placements"] += 1
        if o.resolved is None:
            counts["unresolved"] += 1
            continue
        if o.id in excluded:
            counts["terrain_adapted"] += 1
            skipped.setdefault(o.path, "basin facility (or its anchor family): the terrain "
                                        "adapted to it (08-26; v1 R4) — never re-seated")
            continue
        in_deck_family = fam_of.get(o.id) in deck_keys
        deep = o.solid_min_depth_m is not None and o.solid_min_depth_m <= -admission_m
        if (o.below_grade is not None or deep) and not (in_deck_family
                                                          and rb.deck_family_seats_rigid):
            # a genuine solid under the local grade is a FACILITY the
            # terrain adapts to (08-26), never feet to seat: OTHH's
            # Drainage bowls (−3.8 m floors) and TerminalRoads_Parking_005
            # (−9.1 m) would otherwise lift their whole families — floor
            # plate or not (``deep``: TerminalRoads_03_005, a skirt 4.7 m
            # under with 84 witnesses, founded a 403-member family +5.96
            # once the witness floor had stopped the 4-witness piece).
            # In a DECK family it is a pier footing under the canal bed:
            # it seats WITH its deck (R12-2 completeness; v1 wrote all 12
            # Bridge_01 members), never left behind.
            counts["below_grade"] += 1
            skipped.setdefault(o.path, "below-grade solids: the terrain adapts to it "
                                        "(08-26), never re-seated by its feet")
            continue
        if _obj8.is_stock_library_resource(o.path):
            counts["stock"] += 1
            skipped.setdefault(o.path, "stock library resource (shared, never baked)")
            continue
        live = live_path_of(o.resolved)
        if pack_root and not _inside(live, pack_root):
            counts["outside_pack"] += 1
            skipped.setdefault(o.path, "resolves outside the pack (a shared library "
                                        "object never carries one airport's offsets)")
            continue
        if o.kind == "OBJECT_MSL":
            counts["msl"] += 1
            skipped.setdefault(o.path, "OBJECT_MSL: not terrain-draped")
            continue
        lat, lon = to_ll(o.xy[0], o.xy[1])
        key = (round(lat, 9), round(lon, 9), round(o.agl_m, 3))
        anchors_by_resource.setdefault(o.path, set()).add(key)
        keyed.append((key, o))
    multi = {r for r, ks in anchors_by_resource.items() if len(ks) > 1}
    for r in sorted(multi):
        counts["multi_anchor"] += 1
        skipped[r] = (f"placed at {len(anchors_by_resource[r])} anchors — one "
                      "file cannot carry per-placement offsets (I-4)")
    units_by_key: dict[tuple[float, float, float], dict[str, Member]] = {}
    for key, o in keyed:
        if o.path in multi:
            continue
        members = units_by_key.setdefault(key, {})
        if o.path in members:
            continue        # the same resource at the same anchor twice: one bake
        geom = cache.geometry(o.resolved)
        if geom is None:
            skipped.setdefault(o.path, "unreadable OBJ8")
            continue
        feet = _feet(geom, cache.genuine(o.resolved), o, rb.foot_band_m,
                     rb.foot_samples_per_component, rb.foot_samples_per_member,
                     to_ll_batch)
        deck_ring = None
        deck_top_y = None
        deck_datum_z = None
        deck_ends = None
        deck_profile: tuple[tuple[float, float], ...] = ()
        deck_stations: tuple[tuple[float, float, float], ...] = ()
        if o.hard_deck is not None and o.deck_top_z is not None:
            poly = o.hard_deck
            if poly.geom_type != "Polygon":
                poly = max(poly.geoms, key=lambda g: g.area)
            ring_xy = [(float(x), float(y)) for x, y in poly.exterior.coords[:-1]]
            deck_ring = tuple(to_ll(x, y) for x, y in ring_xy)
            deck_top_y = float(o.deck_top_z - o.anchor_z - o.agl_m)
            if o.deck_kind == "signature" and o.deck_plate is not None:
                # THE ABUTMENTS (R12): the deck top lands at the ground at
                # the deck's END LINES, on land — read after the mesh by
                # ``emit/rebake.py``; the solved surface is not consulted
                # (a bridge over a canal stands outside every graded face)
                pl = o.deck_plate
                if pl.ends is not None:
                    deck_ends = tuple(tuple(to_ll(x, y) for x, y in e) for e in pl.ends)
                deck_profile = tuple(pl.profile)
                deck_stations = tuple((*to_ll(sx, sy), float(y)) for (sx, sy), y in pl.stations)
            else:
                deck_datum_z = deck_datum(ring_xy) if deck_datum is not None else None
            counts["deck_members"] += 1
        if not feet and deck_ring is None:
            counts["no_feet"] += 1
            skipped.setdefault(o.path, "no genuine solid component: nothing to seat")
            continue
        rel = os.path.relpath(live_path_of(o.resolved), pack_root) if pack_root \
            else live_path_of(o.resolved)
        members[o.path] = Member(o.id, rel, o.resolved, live_path_of(o.resolved),
                                 o.heading_deg, feet, deck_ring, deck_top_y, deck_datum_z,
                                 o.deck_kind, deck_ends, deck_profile, tuple(o.deck_evidence),
                                 deck_stations)
        counts["feet"] += len(feet)
    units: list[Unit] = []
    for i, (key, members) in enumerate(sorted(units_by_key.items())):
        if not members:
            continue
        ms = tuple(members[k] for k in sorted(members))
        units.append(Unit(f"unit:{i}", (key[0], key[1]), key[2], ms))
        counts["members"] += len(ms)
    counts["units"] = len(units)
    return RebakePlan(airport.icao, airport.pack.name, pack_root, tuple(units),
                      tuple(sorted(skipped.items())), counts)
