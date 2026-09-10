"""THE RE-SEAT PLAN (RULINGS 2026-09-04i 04f-1; 06g): the anchor families,
their members' welded PARTS and the pack-wide ε-CONTACT GRAPH
(``airport/contact.py``), from the loader's AUTHORED reading of the
objects (``airport/pack.py`` restore-before-read).  Runs at PATCH time
inside the pipeline; the plan is the tile build's
``o4_v2_rebake_<ICAO>.json`` sidecar, seated after the mesh by
``emit/rebake.py`` / ``emit/clusters.py``.  Law: ``structures.toml
[rebake]``.  No environment is read here.
"""
from __future__ import annotations


import os
import typing as _t

import numpy as np

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY
from ..model.rebake import FlatDatum, Member, Part, RebakePlan, Unit
from . import contact as _contact
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
         below_grade: _t.Sequence[tuple[object, _t.Collection[str]]] = (),
         tunnel_objects: _t.Mapping[str, tuple[float, _t.Sequence[XY]]] | None = None
         ) -> RebakePlan:
    """The units and witnesses for ``airport``'s pack (see module doc).
    ``objects`` are the planar pass's placed objects (read from the
    AUTHORED files, the deck signature applied); ``deck_datum`` the
    solved surface's reading at a flagged deck ring; ``exclude`` the
    placement ids the TERRAIN adapted to (the basin facilities, RULINGS
    2026-08-26 / v1 ruling R4) — THAT MEMBER only is never re-seated
    (RULINGS 2026-09-09q (1): the anchor-family expansion is deleted —
    Aerosoft anchors LEMD's whole terminal pack at two points, so one
    wall-corridor member excluded 300 placements over 32 m of relief);
    every other member of the family seats per body (09d);
    ``below_grade`` the emitted below-grade regions ``(frame polygon,
    owner ids)`` — a CANDIDATE plate of a foreign family over one is a
    deck (``deck_signature.promote``); ``tunnel_objects`` the tunnel
    wall objects by placement id → ``(plate height, wall-band stations
    in frame xy)``: RE-SEATED so the plate sits on the ground at the
    band (RULINGS 2026-09-05n-4, ``tunnel.object.reseat``) — THAT OBJECT
    only (RULINGS 2026-09-09s (1): the whole-anchor-family expansion is
    withdrawn), never excluded, never a feet seat, and never the
    below-grade skip (their skirts are the tunnel)."""
    rb = law.tables.structures.rebake
    admission_m = law.tables.structures.basin.admission_depth_m
    # the basin records name their members by resource PATH
    # (``planar.basins``); the ids here match either spelling
    excluded = {o.id for o in objects if o.id in set(exclude) or o.path in set(exclude)}
    # TUNNEL WALL OBJECTS (RULINGS 2026-09-05n-4): plate-seated, by id
    plates: dict[str, tuple[float, _t.Sequence[XY]]] = dict(tunnel_objects or {})
    if not law.tables.structures.tunnel.object.reseat:
        plates = {}
    if below_grade:
        owners = {oid for _r, ids in below_grade for oid in ids}
        foreign = [o for o in objects if o.id not in owners and o.path not in owners]
        keep = {o.id for o in foreign}
        promoted, _n = _deck.promote(foreign, [r for r, _ids in below_grade])
        by_id = {o.id: o for o in promoted}
        objects = [by_id.get(o.id, o) if o.id in keep else o for o in objects]
    fam_of = {o.id: _deck.family_key(o) for o in objects if o.resolved is not None}
    # RULINGS 2026-09-09q (1): a structure the terrain adapted to excludes
    # THAT MEMBER, never its anchor family.  (The family expansion that
    # stood here is deleted with its law key ``structure_family_excluded``.)
    # RULINGS 2026-09-09s (1): 05n-4's "their whole anchor family with
    # them" is WITHDRAWN — a tunnel-wall / basin plate seats its OWN
    # object.  LEMD's pack anchors 300 placements at two origin points,
    # so the expansion re-made the very body 09q had just broken (two
    # plate units of 184 / 95 members, one rigid +0.62 / +0.60 m over
    # 32 m of relief).  Deck families (R12-2) are unchanged.
    deck_keys = {fam_of[o.id] for o in objects
                 if o.resolved is not None and o.deck_kind in ("flag", "signature")}
    to_xy, to_ll = airport.frame.transformers()
    to_ll_batch = _batch_to_ll(airport.frame)
    apt = airport.pack.apt_dat_path
    pack_root = os.path.dirname(os.path.dirname(apt)) if apt else ""
    counts: dict[str, int] = {"placements": 0, "unresolved": 0, "stock": 0,
                              "outside_pack": 0, "msl": 0, "multi_anchor": 0,
                              "units": 0, "members": 0, "deck_members": 0,
                              "parts": 0, "no_parts": 0, "contacts": 0, "pools": 0,
                              "structures": 0, "pairs_tested": 0, "pairs_unproved": 0,
                              "terrain_adapted": 0,
                              "below_grade": 0, "deck_families": len(deck_keys),
                              "plate_members": 0, "plate_objects": len(plates),
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
            skipped.setdefault(o.path, "basin facility / structure member: the terrain "
                                        "adapted to THIS member (08-26; v1 R4; 09q (1): "
                                        "never its anchor family) — never re-seated")
            continue
        in_deck_family = fam_of.get(o.id) in deck_keys
        in_plate_family = o.id in plates          # 09s (1): this object only
        deep = o.solid_min_depth_m is not None and o.solid_min_depth_m <= -admission_m
        if (o.below_grade is not None or deep) and not (in_deck_family
                                                          and rb.deck_family_seats_rigid) \
                and not in_plate_family:
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
    # a PLATE-seated resource at several anchors (OTHH tunnel1 × 2) is
    # planned per anchor: its file takes ONE delta only if the placements'
    # seats agree (``emit/rebake.py`` holds them otherwise)
    plate_paths = {o.path for o in objects if o.id in plates}
    for r in sorted(multi):
        if r in plate_paths:
            continue
        counts["multi_anchor"] += 1
        skipped[r] = (f"placed at {len(anchors_by_resource[r])} anchors — one "
                      "file cannot carry per-placement offsets (I-4)")
    multi -= plate_paths
    units_by_key: dict[tuple[float, float, float], dict[str, Member]] = {}
    # the placed geometry per member, in member order, for the partition
    placed: list[tuple[_obj8.PlacedObject, _obj8.ObjGeometry,
                       list[tuple[int, _obj8.Component]]]] = []
    member_ref: list[tuple[tuple[float, float, float], str]] = []
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
        # the genuine components with their index into ALL solid components
        # (``obj8.solid_components``): the writer maps ``Part.comp`` back
        # through the same deterministic partition of the authored file
        comps = [(i, c) for i, c in enumerate(cache.components(o.resolved))
                 if c.max_y - c.min_y >= cache.thickness_m]
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
        plate_y = None
        plate_stations: tuple[tuple[float, float], ...] = ()
        if o.id in plates:
            plate_y, st_xy = plates[o.id]
            plate_stations = tuple(to_ll(x, y) for x, y in st_xy)
            counts["plate_members"] += 1
        in_deck_family = fam_of.get(o.id) in deck_keys      # THIS member's family
        in_plate_family = o.id in plates          # 09s (1): this object only
        if not comps and deck_ring is None and plate_y is None \
                and not (in_deck_family and rb.deck_family_seats_rigid) and not in_plate_family:
            # a DECK-family member with no genuine solid (Bridge_01_LOD0_004:
            # a two-triangle sheet) still joins its family and takes the
            # deck's delta (R12-2 completeness: no member left at another
            # altitude); anywhere else nothing founds a seat for it
            counts["no_parts"] += 1
            skipped.setdefault(o.path, "no genuine solid component: nothing to seat")
            continue
        rel = os.path.relpath(live_path_of(o.resolved), pack_root) if pack_root \
            else live_path_of(o.resolved)
        members[o.path] = Member(o.id, rel, o.resolved, live_path_of(o.resolved),
                                 o.heading_deg, (), deck_ring, deck_top_y, deck_datum_z,
                                 o.deck_kind, deck_ends, deck_profile, tuple(o.deck_evidence),
                                 deck_stations, plate_y, plate_stations)
        placed.append((o, geom, list(comps)))
        member_ref.append((key, o.path))
    # THE PARTITION (06g): every member's genuine components as placed
    # parts, the pack-wide contact graph, the pool / structure counts
    part = _contact.partition(placed, rb.contact_epsilon_m, rb.contact_weld_m,
                              rb.contact_narrow_budget, rb.pool_overlap_m,
                              rb.contact_batch_rows,
                              law.tables.structures.basin.contact_band_m,
                              rb.foot_samples_max,
                              rb.elevated_base_m)
    parts_by_member: dict[int, list[Part]] = {}
    if part.parts:
        xs = np.array([p.centroid[0] for p in part.parts])
        ys = np.array([p.centroid[1] for p in part.parts])
        lats, lons = to_ll_batch(xs, ys)
        bx = np.array([p.plan_box for p in part.parts])
        la0, lo0 = to_ll_batch(bx[:, 0], bx[:, 1])
        la1, lo1 = to_ll_batch(bx[:, 2], bx[:, 3])
        # THE FEET (09s (2)) in one batched transform: their world y is
        # the AUTHORED y, so the seat reads mesh(foot) − y
        nf = np.array([0 if p.feet is None else p.feet.shape[0] for p in part.parts])
        if nf.sum():
            fxy = np.concatenate([p.feet for p in part.parts if p.feet is not None
                                  and p.feet.shape[0]])
            fla, flo = to_ll_batch(fxy[:, 0], fxy[:, 1])
        else:
            fxy = np.zeros((0, 3)); fla = flo = np.zeros(0)
        at = 0
        for p, la, lo, a0, o0, a1, o1 in zip(part.parts, lats, lons, la0, lo0, la1, lo1):
            k = int(nf[p.pid])
            feet = tuple((round(float(fla[at + j]), 8), round(float(flo[at + j]), 8),
                          round(float(fxy[at + j, 2]), 3)) for j in range(k))
            at += k
            # rounded to the millimetre (8 dp of a degree, 3 dp of a metre):
            # the plan is a witness set, and OTHH's 152 k parts are 26 MB unrounded
            parts_by_member.setdefault(p.member, []).append(
                Part(p.pid, p.comp, round(float(la), 8), round(float(lo), 8),
                     round(p.base_y, 3), round(p.area_m2, 3),
                     (round(float(min(a0, a1)), 8), round(float(min(o0, o1)), 8),
                      round(float(max(a0, a1)), 8), round(float(max(o0, o1)), 8)),
                     feet))
    for mi, (key, path) in enumerate(member_ref):
        m = units_by_key[key][path]
        ps = tuple(parts_by_member.get(mi, ()))
        units_by_key[key][path] = Member(m.id, m.resource, m.authored_path, m.live_path,
                                         m.heading_deg, ps, m.deck_ring, m.deck_top_y,
                                         m.deck_datum_z, m.deck_kind, m.deck_ends,
                                         m.deck_profile, m.deck_evidence, m.deck_stations,
                                         m.plate_y, m.plate_stations)
        counts["parts"] += len(ps)
    counts["contacts"] = len(part.contacts)
    counts["pools"] = part.pools
    counts["structures"] = part.structures
    counts["pairs_tested"] = part.pairs_tested
    counts["pairs_unproved"] = part.pairs_unproved
    units: list[Unit] = []
    for i, (key, members) in enumerate(sorted(units_by_key.items())):
        if not members:
            continue
        ms = tuple(members[k] for k in sorted(members))
        units.append(Unit(f"unit:{i}", (key[0], key[1]), key[2], ms))
        counts["members"] += len(ms)
    counts["units"] = len(units)
    # THE FLAT-SITE DATUM (RULINGS 2026-09-08d; spec othh-seat-artefacts-spec.md
    # §2): the verdict, Z0 and the datum region in lat/lon travel with the
    # plan — the post-mesh seat founds anchors and ground on Z0 inside it
    fv = airport.flat_site
    flat = None
    if fv is not None:
        flat = FlatDatum(fv.verdict, fv.z0_m, fv.source,
                         tuple((tuple(to_ll(x, y) for x, y in outer),
                                tuple(tuple(to_ll(x, y) for x, y in h) for h in holes))
                               for outer, holes in fv.region))
        counts["flat_site"] = int(flat.substitutes)
    return RebakePlan(airport.icao, airport.pack.name, pack_root, tuple(units),
                      tuple(sorted(skipped.items())), counts, part.contacts, flat)
