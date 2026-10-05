"""THE WALL CORRIDORS, READ FAMILY BY FAMILY (law and reading:
``airport/wall_corridors.py``, whose records, stats and geometry helpers
this module reads with; split from it by responsibility, issue #362).

A read of the wall corridors is an INTAKE (:func:`wall_families`: the
anchor families in sorted key order, each family's members in ``objects``
order), ONE READING PER FAMILY (:func:`read_family`, through the
:class:`WallReader` every family shares — it reads no other family's
READING) and an ASSEMBLY (:func:`assemble`: the readings taken in the
intake's order, where a corridor's ``@k`` and the order of every refusal
line come from).  :func:`read_wall_corridors` is the three in one loop;
``airport/reader_work.py`` hands the families to work-pool workers and
assembles the same way.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import time
import typing as _t

from shapely.geometry import LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..model import pulse as _pulse
from ..model.airport import Airport
from ..model.frame import XY
from . import obj8 as _obj8
from .below_zero import read_below_zero, read_wall_height
from .deck_signature import family_key
from .tunnel_walls import midline, read_wall_lines, stations_along
from .wall_corridor_probe import _floor_road, _floor_slab, _RoadLevels, mouth_roads
from .wall_corridors import (CLASS_BAY, CLASS_GARAGE, CLASS_LEVEL, ID_PREFIX,
                             WallCorridorRecord, WallCorridorStats, _bands_of, _end_cover,
                             _floor_profile, _headroom, _slice, _trench)
from .wall_geometry import _DENSIFY_M, _FamilyFaces, _merge_walls, _overlap_along, _seat_base
from .wall_mouth import FieldCover, MouthIndex, WallField, admit

__all__ = ["WallReader", "WallField", "wall_reader", "wall_families", "read_family",
           "assemble", "read_wall_corridors"]


@_dc.dataclass
class WallReader:
    """What every family's reading takes besides its members: the inputs of
    ONE read of the wall corridors (:func:`wall_reader`).  ``bz_store`` is
    the per-placement / per-resource memo of ``below_zero`` — pure, so a
    read split over several processes simply fills one each.

    ``pack`` is EVERY placed object of the pack — the mouth clauses (spec
    §12h) read what any placement puts across a candidate's mouth — and
    ``cover`` the field's index (``None`` = no field handed: FIELD is NOT
    READ).  ``mouth_index`` is the pack-wide index over ``pack``, built on
    the first mouth query of the process (:meth:`mouths`)."""

    airport: Airport
    pack: _t.Sequence[_obj8.PlacedObject]
    cache: _obj8.ResourceCache
    law: Law
    measure: bool = False
    roads: list = _dc.field(default_factory=list)
    road_tree: _t.Any = None
    levels: _t.Any = None
    bz_store: dict = _dc.field(default_factory=dict)
    #: the frame's ``to_ll`` — two pyproj transformers to build, so ONCE per
    #: reader, never per family (KASE: 2,191 families, 12 s of a 0.3 s read)
    to_ll: _t.Any = None
    cover: FieldCover | None = None
    mouth_index: MouthIndex | None = None

    def mouths(self) -> MouthIndex:
        """THE pack-wide mouth index — ONE per reader (per process), built
        when the first candidate reaches a mouth query (§12h (5))."""
        if self.mouth_index is None:
            self.mouth_index = MouthIndex(self.pack, self.cache, self.airport.dem.z,
                                          self.law)
        return self.mouth_index


def wall_reader(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
                cache: _obj8.ResourceCache, law: Law, classification: _t.Any = None,
                measure: bool = False, field: WallField | None = None) -> WallReader:
    """The reader of one read: ``objects`` the WHOLE pack's placements
    (the mouth index's population, never one family's), ``field`` the
    classified cover the FIELD clause reads (``None`` = not read)."""
    # RULINGS 2026-09-10ad: (b'') is DELETED (refuted in 10z/10ab); the
    # roads survive as the round-4 PROBE's reading alone (``measure``), and
    # so does the LEVEL reader for a mouth road (RULINGS 2026-09-10ab (i))
    roads = mouth_roads(airport, classification) if measure else []
    return WallReader(airport, objects, cache, law, measure, roads,
                      STRtree([r.geom for r in roads]) if roads else None,
                      _RoadLevels(airport, law) if measure else None,
                      to_ll=airport.frame.transformers()[1],
                      cover=None if field is None else FieldCover(field))


def wall_families(objects: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
                  law: Law) -> tuple[int, list[tuple[tuple, list[int]]]]:
    """THE INTAKE: ``(placements read, [(family key, the members' positions
    in objects), …])``, the families in sorted key order — the order
    :func:`assemble` takes their readings in — and each family's members in
    the order ``objects`` has them."""
    wc = law.tables.structures.cutout.wall_corridor
    placements = 0
    fams: dict[tuple, list[int]] = {}
    # MEASURED ORDER-DEPENDENT AND NOT FIXED HERE (lane v2othhdet, dry
    # OTHH pair): this intake's order decides the family members' order,
    # which decides which band of a pair is A (and so which RESOURCE
    # names the corridor) and which pairs are admitted at all.  Sorting
    # it by ``object_cut.placement_key`` moved OTHH's reading
    # 73 -> 75 wall corridors (Bridge_02 ids replacing Bridge_06 ids at
    # the same sites, ``OTHH_Terminal_Parking_006@0`` admitted,
    # ``..._VCN_004@0/a,b,@2/a,b,@3`` gone) — a GEOMETRY change, not a
    # relabelling, and neither order is more right than the other until
    # the band-pair choice is ruled.  Reported, not attempted: the sorted
    # intake is arbitrary in exactly the way the DSF order is.
    for k, o in enumerate(objects):
        if o.resolved is None or _obj8.is_stock_library_resource(o.path):
            continue
        placements += 1
        vmin = cache.y_range(o.resolved)[0]
        if vmin == math.inf or vmin > -wc.min_wall_depth_m:
            continue
        fams.setdefault(family_key(o), []).append(k)
    return placements, sorted(fams.items(), key=lambda kv: kv[0])


def read_family(rd: WallReader, fk: tuple, members: _t.Sequence[_obj8.PlacedObject]
                ) -> tuple[WallCorridorStats, list[tuple[str, str, list[WallCorridorRecord]]]]:
    """ONE FAMILY's reading: its own stats (refusals and admission lines in
    the order the pairs are met) and, per pair that reached the corridor
    rule, ``(resource, name, records)``.

    A PURE FUNCTION of its members, THE WHOLE PACK's placements and parsed
    geometry (the mouth clauses read what ANY placement puts across a
    candidate's mouth — spec §12h (5)), the DEM, the law and the field —
    and of NO OTHER FAMILY'S READING: the one thing the serial read
    carried from family to family, the ``@k`` of a corridor id, is assigned
    by :func:`assemble`.  So the readings are the same at any worker count
    and in any completion order.

    THE ONE ADMISSION SITE of Law C (§12h (4)): rules 1-5 and the kerb
    test as before, then FIELD, W1s and W3 (``wall_mouth.admit``), cheapest
    refusal first; no clause is evaluated anywhere else and no consumer
    vetoes."""
    airport, cache, law, measure = rd.airport, rd.cache, rd.law, rd.measure
    roads, road_tree, levels, bz_store = rd.roads, rd.road_tree, rd.levels, rd.bz_store
    stats = WallCorridorStats()
    pairs: list[tuple[str, str, list[WallCorridorRecord]]] = []
    wc = law.tables.structures.cutout.wall_corridor
    ob = law.tables.structures.tunnel.object
    bl = law.tables.structures.basin
    co = law.tables.structures.cutout
    grid = law.tables.emit.identity.min_distinct_spacing_m
    dem_z = airport.dem.z
    to_ll = rd.to_ll
    bands: list[WallBand] = []
    verticals: list[tuple] = []
    by_id = {o.id: o for o in members}
    for o in members:
        bs, verts = _bands_of(o, cache, dem_z, law)
        bands.extend(bs)
        if verts:
            verticals.append((o, verts))
    if len(bands) < 2:
        return stats, pairs
    bands = _merge_walls(bands, wc.parallel_max_deg, ob.wall_face_max_thickness_m,
                         wc.merge_gap_m)
    stats.families += 1
    stats.bands += len(bands)
    # THE FAMILY'S VERTICAL FACES ARE READ WHEN A PAIR REACHES RULE 4
    # (#362): only the end-cap test reads them, and at OTHH 14 of 69
    # pairs get that far — one plan segment per vertical triangle of
    # every member of every family was most of this pass's 120 s.
    ends = _FamilyFaces(verticals, cache, wc.min_wall_depth_m, measure)
    fam_name = f"{fk[0]:.3f},{fk[1]:.3f},{fk[2]:.3f}"
    # RULE 2: the pairs
    for i in range(len(bands)):
        for j in range(i + 1, len(bands)):
            A, B = bands[i], bands[j]
            dd = abs(A.bearing_deg - B.bearing_deg)
            dd = min(dd, 180.0 - dd)
            if dd > wc.parallel_max_deg:
                continue
            gap = A.poly.distance(B.poly)
            if not (wc.min_width_m <= gap <= wc.max_width_m):
                continue
            brg = math.radians(A.bearing_deg)
            u = (math.sin(brg), math.cos(brg))
            lo, hi, ov = _overlap_along(u, A, B)
            if ov < wc.min_wall_length_m:
                continue
            between = unary_union([A.poly, B.poly]).convex_hull.difference(
                unary_union([A.poly.buffer(grid), B.poly.buffer(grid)]))
            third = False
            for k, C in enumerate(bands):
                if k in (i, j) or not C.poly.intersects(between):
                    continue
                _l, _h, ov3 = _overlap_along(u, A, C)
                if C.poly.intersection(between).area > 1e-6 and ov3 >= wc.min_wall_length_m:
                    third = True
                    break
            if third:
                continue
            stats.pairs += 1
            o0 = by_id[A.owner]
            name = os.path.basename(A.resource)
            la, lo_ = to_ll(*A.poly.centroid.coords[0])
            site = f"{la:.6f},{lo_:.6f}"
            plate = unary_union([A.poly, B.poly])
            walls = read_wall_lines(plate, law)
            if isinstance(walls, str):
                stats.refused.append(f"{name} at {site}: the pair {A.comp}/{B.comp} is not "
                                     f"two readable bands ({walls})")
                continue
            if walls.kind != "II":
                stats.refused.append(f"{name} at {site}: the pair {A.comp}/{B.comp} reads as "
                                     f"{walls.kind}, not two bands")
                continue
            axis = midline(walls, ob.wall_sample_m)
            sts = stations_along(axis, walls, ob.wall_sample_m, grid)
            if len(sts) < 2:
                stats.refused.append(f"{name} at {site}: the inner faces leave no station")
                continue
            axis_ln = LineString(axis)
            orig_s = [st.s for st in sts]
            floors, floors_y = _floor_profile((A, B), axis_ln, orig_s, _DENSIFY_M)
            # RULINGS 2026-09-10ad: ONE SEAT PER CORRIDOR.  The pair is
            # one body (its kerbs and the deck over them weld) and the
            # rebake seats a body on the ground under it, so the floor
            # is the AUTHORED wall bottom under the ground at the
            # corridor's own plan centroid — not each band's own
            # reading (the two kerbs of a corridor on sloping ground
            # would seat centimetres apart) and never the pack's
            # anchor plane.
            seat_z = _seat_base(o0, plate.centroid.coords[0], dem_z)
            floors = [seat_z + y for y in floors_y]
            grounds = [float(dem_z(*axis_ln.interpolate(s).coords[0])) for s in orig_s]
            if any(math.isnan(z) for z in grounds):
                stats.refused.append(f"{name} at {site}: no DEM along the corridor")
                continue
            # RULE 3: level or descending
            zmin, zmax = min(floors), max(floors)
            depths = [g - z for g, z in zip(grounds, floors)]
            grades = [abs(floors[k + 1] - floors[k]) / max(orig_s[k + 1] - orig_s[k], 1e-9)
                      for k in range(len(floors) - 1)]
            max_grade = max(grades) if grades else 0.0
            if max_grade > wc.max_authored_grade:
                stats.refused.append(f"{name} at {site}: the wall bottom runs at "
                                     f"{100.0 * max_grade:.1f} % between stations (> "
                                     f"max_authored_grade {100.0 * wc.max_authored_grade:.0f} %)")
                continue
            # RULINGS 2026-09-10u: the corridor is admitted on AUTHORED
            # depth — the wall bottom under the OBJECT'S OWN local zero
            # at some station.  ``depths`` (against the DEM) stays the
            # MEASUREMENT of an admitted corridor (the mouth at grade,
            # the notes, ``depth_m``), never the admission.
            authored_depths = [-y for y in floors_y]
            head = f"candidate {name} bands {A.comp}/{B.comp} at {site}"
            if max(authored_depths) < wc.min_wall_depth_m:
                msg = (f"{name} at {site}: the wall bottom is authored at y "
                       f"{min(floors_y):+.2f} at its deepest station — never "
                       f"min_wall_depth_m {wc.min_wall_depth_m} under the "
                       f"object's own zero (10u)")
                stats.refused.append(msg)
                stats.admission.append(
                    f"{head}: (a) REFUSED — deepest authored y {min(floors_y):+.2f} m, "
                    f"never {wc.min_wall_depth_m} m under the object's zero; (b'') not read")
                continue
            clause_a = (f"(a) admitted — wall bottom authored {max(authored_depths):.2f} m "
                        f"under the object's zero")
            # RULINGS 2026-09-10af — (d) THE NARROW-CUT TEST: a
            # corridor is a road-width cut in a building that is
            # otherwise above its own zero; a placement whose whole
            # bottom stands below zero is FOUNDATIONS (the author's
            # slope affordance) and is left to its seat.
            bz = (read_below_zero([by_id[A.owner], by_id[B.owner]], cache,
                                  wc.min_wall_depth_m, plate.centroid.coords[0],
                                  ob.wall_face_max_thickness_m, store=bz_store)
                  if measure else None)
            cut_w, foot_w = (0.0, 0.0) if bz is None else bz.widths(u)
            frac = 0.0 if bz is None else bz.fraction
            # RULINGS 2026-09-10ao — THE WALL'S HEIGHT ABOVE THE
            # OBJECT'S ZERO: a kerb wall rises from its floor to the
            # deck it carries and no further; a cargo shed's
            # foundation sheet is the bottom of a BUILDING wall that
            # rises to a roof.  Read per band, in the object's own
            # authored frame (never the terrain).
            # ISSUE #12 [OTHH-1] (Q-12, shipped default-ON): read in
            # EVERY build now — it is the admission's (d) below.
            ha = read_wall_height(by_id[A.owner], cache, A.comp, grid,
                                  ob.wall_face_max_thickness_m, store=bz_store)
            hb = read_wall_height(by_id[B.owner], cache, B.comp, grid,
                                  ob.wall_face_max_thickness_m, store=bz_store)
            h_own = max([h.own_m for h in (ha, hb) if h is not None] or [0.0])
            h_step = max([h.step_m for h in (ha, hb) if h is not None] or [0.0])
            h_conn = max([h.connected_m for h in (ha, hb) if h is not None] or [0.0])
            h_conn_min = min([h.connected_m for h in (ha, hb) if h is not None] or [0.0])
            nc_row: dict | None = None
            if measure:
                nc_row = {"airport": airport.icao, "resource": name,
                          "bands": f"{A.comp}/{B.comp}", "site": site,
                          "spacing_m": round(gap, 2),
                          "width_m": None, "perimeter_m": 0.0 if bz is None
                          else round(bz.perimeter_m, 1),
                          "below_perimeter_m": 0.0 if bz is None
                          else round(bz.below_perimeter_m, 1),
                          "fraction": round(frac, 3),
                          "fraction_total": 0.0 if bz is None
                          else round(bz.fraction_total, 3),
                          "total_perimeter_m": 0.0 if bz is None
                          else round(bz.total_perimeter_m, 1),
                          "total_below_perimeter_m": 0.0 if bz is None
                          else round(bz.total_below_perimeter_m, 1),
                          "cut_width_m": round(cut_w, 1),
                          "footprint_width_m": round(foot_w, 1),
                          "width_ratio": round(cut_w / foot_w, 3) if foot_w > 0 else None,
                          "site_area_m2": 0.0 if bz is None
                          else round(bz.site_area_m2, 1),
                          "site_thickness_m": 0.0 if bz is None
                          else round(bz.site_thickness_m, 2),
                          "axis_inside_frac": 0.0 if bz is None else round(
                              axis_ln.intersection(bz.footprint).length
                              / max(axis_ln.length, 1e-9), 3),
                          "end_cover": [0.0, 0.0], "end_cover_below": [0.0, 0.0],
                          # RULINGS 2026-09-10ao — the wall's height
                          # above the object's zero, per band and for
                          # the wall connected above it
                          "wall_own_m": round(h_own, 2),
                          "wall_step_m": round(h_step, 2),
                          "wall_connected_m": round(h_conn, 2),
                          "wall_connected_min_m": round(h_conn_min, 2),
                          "wall_a_m": None if ha is None else round(ha.connected_m, 2),
                          "wall_b_m": None if hb is None else round(hb.connected_m, 2),
                          "wall_witness": (("A: " + ha.witness) if ha else "")
                                          + (("; B: " + hb.witness) if hb else ""),
                          "admitted": False}
                stats.narrow_cut.append(nc_row)
            # (d) THE KERB TEST (issue #12, OWNER QUESTION Q-12): a kerb
            # wall rises from its floor to the deck and no further; a
            # band whose OWN component stands more than
            # ``max_wall_height_m`` over the object's zero is the buried
            # bottom of a building / bridge wall — FOUNDATIONS (10af):
            # the object keeps its seat, the ground stays, no trench.
            # The OWN component, never the connected wall: #16's bay
            # (Terminal_Base_2_1@4) is a 0.63 m kerb whose one band
            # touches the terminal's 43.7 m facade.
            if h_own > wc.max_wall_height_m:
                msg = (f"{name} at {site}: its wall rises {h_own:.2f} m over the "
                       f"object's zero (> max_wall_height_m {wc.max_wall_height_m}) — "
                       f"the buried foot of a building wall, foundations, not a kerb "
                       f"corridor (#12)")
                stats.refused.append(msg)
                stats.admission.append(f"{head}: {clause_a}; (d) REFUSED — wall "
                                       f"{h_own:.2f} m over the zero: foundations")
                continue
            descending = (zmax - zmin) >= wc.min_wall_depth_m
            # RULE 4: the ends
            def end_line(k: int) -> tuple[XY, XY]:
                p = axis[0] if k == 0 else axis[-1]
                q = axis[1] if k == 0 else axis[-2]
                ux, uy = p[0] - q[0], p[1] - q[1]
                L = math.hypot(ux, uy) or 1.0
                nx, ny_ = -uy / L, ux / L
                st = sts[0] if k == 0 else sts[-1]
                return ((p[0] + nx * st.half_l, p[1] + ny_ * st.half_l),
                        (p[0] - nx * st.half_r, p[1] - ny_ * st.half_r))
            covers = [_end_cover(end_line(k), ends.faces, ends.tree, ob.end_cap_open_m)
                      for k in (0, 1)]
            covers_low = [_end_cover(end_line(k), ends.faces_low, ends.low_tree,
                                     ob.end_cap_open_m) for k in (0, 1)] \
                if measure else [0.0, 0.0]
            closed = [c >= wc.end_cap_cover_min for c in covers]
            width = 2.0 * sum((s.half_l + s.half_r) / 2.0 for s in sts) / len(sts)
            thick = sum((s.thick_l + s.thick_r) / 2.0 for s in sts) / len(sts)
            if nc_row is not None:
                nc_row["width_m"] = round(width, 2)
                nc_row["end_cover"] = [round(covers[0], 3), round(covers[1], 3)]
                nc_row["end_cover_below"] = [round(covers_low[0], 3),
                                             round(covers_low[1], 3)]
            trench0 = _trench(axis, sts)
            # THE MOUTHS: the open ends (a garage's shallow end).  A
            # pair closed at BOTH ends is a sunken yard, not a corridor.
            # (RULINGS 2026-09-10ad: the 10z (b'') groundside-mouth
            # clause is DELETED — it separated nothing, 10ab.)
            if descending:
                deep0 = 0 if floors[0] <= floors[-1] else 1
                mouth_ks = [1 - deep0]
            else:
                mouth_ks = [k for k in (0, 1) if not closed[k]]
            if not mouth_ks:
                msg = (f"{name} at {site}: closed at both ends (covers {covers[0]:.0%} / "
                       f"{covers[1]:.0%}): no mouth — a sunken yard between four kerbs, not "
                       f"a corridor")
                stats.refused.append(msg)
                stats.admission.append(f"{head}: {clause_a}; REFUSED — no mouth (both "
                                       f"ends closed)")
                continue
            # RULINGS 2026-09-10ab: the two discriminators MEASURED —
            # the REPLAY's instrument (``--stage structures``), never
            # a gate and never a build cost: neither separates LEMD
            # from OTHH (spec §12c), so nothing reads them in law.
            if measure:
                mouth_pts = [(k, axis[0] if k == 0 else axis[-1],
                              floors[0] if k == 0 else floors[-1]) for k in mouth_ks]
                fr = _floor_road(mouth_pts, roads, road_tree,
                                 wc.corridor_road_level_m, levels)
                slab_cover, slab_w = _floor_slab(
                    members, cache, trench0, axis_ln, orig_s, floors,
                    wc.corridor_floor_slab_max_thickness_m,
                    wc.corridor_floor_slab_tol_m, ob.plate_normal_y_min, dem_z)
                corridor_len = float(orig_s[-1] - orig_s[0])
                stats.floor_probe.append({
                    "airport": airport.icao, "candidate": head,
                    "resource": name, "bands": f"{A.comp}/{B.comp}", "site": site,
                    "length_m": round(corridor_len, 1),
                    "floor_min_z": round(zmin, 2), "floor_max_z": round(zmax, 2),
                    "mouth_floor_z": None if fr is None else round(fr.floor_z, 2),
                    "road_level_z": None if fr is None else round(fr.level_z, 2),
                    "road_dist_m": None if fr is None else round(fr.distance_m, 1),
                    "delta_m": None if fr is None else round(fr.delta_m, 2),
                    "road_source": "" if fr is None else fr.source,
                    "road_witness": "" if fr is None else fr.witness,
                    "within_tol": bool(fr is not None and abs(fr.delta_m)
                                       <= wc.corridor_floor_road_tol_m),
                    "ramp_reachable": bool(fr is not None and abs(fr.delta_m)
                                           <= wc.max_ramp_grade * max(corridor_len, 1e-9)),
                    "slab_cover": round(slab_cover, 3),
                    "slab": bool(slab_cover >= wc.corridor_floor_slab_cover_min),
                    "slab_witness": slab_w,
                })
            # RULE 5: headroom over the trench (a MEASUREMENT plus the
            # covered-slot gate; OPEN AIR PASSES — 10z deleted the deck
            # clause: seven OTHH corridors carry no plate of their own).
            headroom, deck_w, plate_plan = _headroom(members, cache, trench0, zmax,
                                                     ob.plate_normal_y_min, grid, dem_z)
            if headroom is not None and headroom < wc.min_headroom_m:
                msg = (f"{name} at {site}: headroom {headroom:.2f} m over the floor "
                       f"(< min_headroom_m {wc.min_headroom_m}): a covered slot, "
                       f"not a corridor")
                stats.refused.append(msg)
                stats.admission.append(f"{head}: {clause_a}; headroom "
                                       f"{headroom:.2f} m REFUSED under min_headroom_m "
                                       f"{wc.min_headroom_m} ({deck_w})")
                continue
            # §12h — FIELD, W1s, W3: THE OPEN MOUTH, read against the whole
            # pack and the field.  The ground at a mouth is the DEM at its
            # segment's midpoint (the station's own where that is cold).
            end_lines = [end_line(k) for k in (0, 1)]
            end_grounds = []
            for k, (p, q) in enumerate(end_lines):
                gz = float(dem_z((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0))
                end_grounds.append(grounds[-k] if math.isnan(gz) else gz)
            verdict = admit(rd.cover, rd.mouths, end_lines, mouth_ks,
                            (floors[0], floors[-1]), end_grounds,
                            deck_w if plate_plan is not None else None,
                            wc.end_cap_cover_min)
            clauses = (f"{head}: {clause_a}; (d) kerb {h_own:.2f} m; ends family "
                       f"{covers[0]:.0%}/{covers[1]:.0%}; headroom "
                       + ("open air" if headroom is None else f"{headroom:.2f} m ({deck_w})")
                       + f"; {verdict.text}")
            if nc_row is not None:
                nc_row.update(verdict.row)
            if verdict.refused_by:
                stats.refused.append(f"{name} at {site}: REFUSED by {verdict.refused_by} "
                                     f"(§12h) — {verdict.refusal}")
                stats.admission.append(clauses)
                continue
            # THE CLASS READS THE COMPOSED OPENNESS (§12h (1)): an end is
            # open iff rule 4 AND W1s leave it open
            family_closed = list(closed)
            closed = [k not in verdict.open_ks for k in (0, 1)]
            mouth_ends = verdict.ends
            notes_common = (
                f"bands {A.comp} ({A.thickness_m:.2f} m, {A.length_m:.1f} m) / {B.comp} "
                f"({B.thickness_m:.2f} m, {B.length_m:.1f} m) of {name}, inner faces {gap:.2f} m "
                f"apart, overlap {ov:.1f} m; wall bottom {zmin:.2f}..{zmax:.2f} (ground "
                f"{min(grounds):.2f}..{max(grounds):.2f}), max authored grade "
                f"{100.0 * max_grade:.1f} %; ends cover {covers[0]:.0%}/{covers[1]:.0%}; headroom "
                f"{'open air' if headroom is None else f'{headroom:.2f} m'}",)
            # the corridor's ``@k`` counts admitted pairs of the resource
            # ACROSS families: ``assemble`` assigns it; here an id is its
            # suffix alone (``""``, ``/a``, ``/b``), and so is a sibling
            base_id = ""
            objects_ids = tuple(sorted({A.owner, B.owner}))
            anchor = (o0.xy, float(o0.anchor_z), float(o0.agl_m))
            overlap = co.floor_overlap_m
            recs: list[WallCorridorRecord] = []
            if descending:
                # the deep end is the mouth (closed by the garage), the
                # shallow end must meet the ground
                deep = 0 if floors[0] <= floors[-1] else 1
                shallow_depth = depths[-1] if deep == 0 else depths[0]
                if shallow_depth > bl.contact_band_m:
                    stats.refused.append(f"{name} at {site}: the wall bottom descends "
                                         f"{zmax - zmin:.2f} m but its shallow end lies "
                                         f"{shallow_depth:.2f} m under the ground (> contact_band_m "
                                         f"{bl.contact_band_m}): no mouth at grade")
                    stats.admission.append(
                        f"{clauses} -> REFUSED — a descending pair whose shallow end lies "
                        f"{shallow_depth:.2f} m under the ground: no mouth at grade")
                    pairs.append((A.resource, name, []))   # its @k is spent
                    continue
                s_a, s_b = (orig_s[0], orig_s[-1]) if deep == 0 else (orig_s[-1], orig_s[0])
                ax2, st2, fl2, gr2 = _slice(axis_ln, sts, floors, s_a, s_b, overlap, 0.0,
                                            ob.wall_sample_m, dem_z)
                t_end = walls.end_thickness_m[deep] or thick
                recs.append(WallCorridorRecord(
                    base_id, A.resource, objects_ids, fam_name, CLASS_GARAGE, tuple(ax2),
                    tuple(st2), tuple(fl2), tuple(gr2), float(st2[-1].s), width, True, False,
                    t_end, 0.0, plate, _trench(ax2, st2), unary_union([plate, trench0]),
                    *anchor, headroom, max_grade, "",
                    notes_common + (f"garage ramp (2026-09-08n): the wall bottom descends "
                                    f"{zmax - zmin:.2f} m from the grade end to the garage, cut as "
                                    f"authored; the deep end closed by the garage",),
                    plate_plan=plate_plan))
            elif closed[0] or closed[1]:
                m = 0 if closed[0] else 1
                s_a, s_b = (orig_s[0], orig_s[-1]) if m == 0 else (orig_s[-1], orig_s[0])
                ax2, st2, fl2, gr2 = _slice(axis_ln, sts, floors, s_a, s_b, overlap, 0.0,
                                            ob.wall_sample_m, dem_z)
                # a FOREIGN placement across the mouth closes an end as a
                # family face does (owner RULINGS 2026-10-05h (2)): the bay
                # is at the other end, and the note names the closer
                by = (f"a family face ({covers[m]:.0%} covered)" if family_closed[m]
                      else f"the pack across its mouth ({mouth_ends[m].text(m)})")
                recs.append(WallCorridorRecord(
                    base_id, A.resource, objects_ids, fam_name, CLASS_BAY, tuple(ax2),
                    tuple(st2), tuple(fl2), tuple(gr2), float(st2[-1].s), width, True, False,
                    thick, 0.0, plate, _trench(ax2, st2), unary_union([plate, trench0]),
                    *anchor, headroom, max_grade, "",
                    notes_common + (f"closed bay: end {m} closed by {by}, a ramp beyond "
                                    f"the open end",),
                    plate_plan=plate_plan))
            else:
                # two capless halves meeting at the midpoint, each
                # climbing beyond its own end
                s_mid = (orig_s[0] + orig_s[-1]) / 2.0
                for tag, s_b in (("a", orig_s[0]), ("b", orig_s[-1])):
                    ax2, st2, fl2, gr2 = _slice(axis_ln, sts, floors, s_mid, s_b, 0.0, 0.0,
                                                ob.wall_sample_m, dem_z)
                    if len(ax2) < 2:
                        continue
                    other = f"{base_id}/{'b' if tag == 'a' else 'a'}"
                    recs.append(WallCorridorRecord(
                        f"{base_id}/{tag}", A.resource, objects_ids, fam_name, CLASS_LEVEL,
                        tuple(ax2), tuple(st2), tuple(fl2), tuple(gr2), float(st2[-1].s), width,
                        False, False, 0.0, 0.0, plate, _trench(ax2, st2),
                        unary_union([plate, trench0]), *anchor, headroom, max_grade, other,
                        notes_common + (f"level corridor open at both ends: half {tag} from the "
                                        f"midpoint, a ramp beyond its end",),
                        plate_plan=plate_plan))
            if nc_row is not None:
                nc_row["admitted"] = True
            stats.admission.append(f"{clauses} -> ADMITTED {recs[0].cls if recs else 'none'}")
            pairs.append((A.resource, name, recs))
    return stats, pairs


def assemble(placements: int, readings: _t.Iterable[tuple],
             field: WallField | None = None
             ) -> tuple[list[WallCorridorRecord], WallCorridorStats]:
    """The families' readings (:func:`read_family`), taken in sorted
    family order, as ONE reading: the counters summed, the refusal and
    admission lines concatenated, and each admitted pair given the next
    ``@k`` of its resource — in exactly the order one loop over the
    families assigned them.  ``field`` is the field the readers were
    handed: the stats say whether FIELD was read (§12h (4))."""
    stats = WallCorridorStats(placements=placements, field_read=field is not None,
                              field_cells=0 if field is None else len(field.polys))
    out: list[WallCorridorRecord] = []
    k_by_res: dict[str, int] = {}
    for fam, pairs in readings:
        stats.families += fam.families
        stats.bands += fam.bands
        stats.pairs += fam.pairs
        for name in ("refused", "admission", "floor_probe", "narrow_cut"):
            getattr(stats, name).extend(getattr(fam, name))
        for resource, name, recs in pairs:
            k_res = k_by_res.get(resource, 0)
            k_by_res[resource] = k_res + 1
            base_id = f"{ID_PREFIX}:{name}@{k_res}"
            for r in recs:
                out.append(_dc.replace(r, id=base_id + r.id,
                                       sibling=base_id + r.sibling if r.sibling else ""))
                stats.by_class[r.cls] = stats.by_class.get(r.cls, 0) + 1
            stats.corridors += 1 if recs else 0
    out.sort(key=lambda r: r.id)
    return out, stats


def read_wall_corridors(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
                        cache: _obj8.ResourceCache, law: Law, classification: _t.Any = None,
                        measure: bool = False, field: WallField | None = None
                        ) -> tuple[list[WallCorridorRecord], WallCorridorStats]:
    """Every wall corridor the pack's kerb-wall families state (module
    doc); the stats name every refusal and, per CANDIDATE, each admission
    clause with its witness (``stats.admission``).  ``field`` is the
    classified cover the FIELD clause reads (spec §12h): a BUILD always
    hands one; ``None`` (a caller with no classification) leaves FIELD NOT
    READ, said on every line and in ``stats.field_read``.
    ``classification``, when given, adds the patch's own road ribbons to
    the mouth-road test (10w (b)); without it only the OSM ways are
    read.  ``measure`` (the ``--stage structures`` replay alone) adds the
    RULINGS 2026-09-10ab reading of the two round-4 discriminators per
    candidate (``stats.floor_probe``) — a measurement, never a gate, and
    never a cost in a build."""
    t0 = time.perf_counter()
    rd = wall_reader(airport, objects, cache, law, classification, measure, field)
    placements, fams = wall_families(objects, cache, law)
    out, stats = assemble(placements, (
        read_family(rd, fk, [objects[k] for k in ks])
        for fk, ks in _pulse.each(fams, "wall corridors", "families")), field)
    stats.read_s = time.perf_counter() - t0
    return out, stats
