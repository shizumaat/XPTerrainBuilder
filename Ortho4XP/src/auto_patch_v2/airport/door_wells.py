"""THE DOOR WELLS (RULINGS 2026-09-08b/c LAW A; spec ``docs/specs/
auto-patch-v2/othh-terminal-ramps-spec.md`` §2; law ``structures.toml
[cutout.door]``): where a below-grade floor plate of an object REACHES
ITS EXTERIOR FACE — the plate boundary leaves the object family's own
at-grade geometry — it is a basement access DOOR, not a basement, and
the terrain gets a small ramp down to it.

THE READING, over the geometry the basin pass already parsed
(``obj8.ResourceCache``, never a second parse), per placement:

1. SILL WITNESS — a genuine solid component (``basin.min_solid_
   thickness_m``) carrying a near-horizontal floor plate
   (``basin.floor_plate_normal_y_min``) at least ``sill_min_depth_m``
   under the LOCAL ground (``obj8._witness`` at the door's own gate: the
   2.5 m basin gate never sees these — OTHH's six wells stand 1.57–1.70 m
   under) and shallower than the basin gate (a component reaching
   ``basin.admission_depth_m`` is the basin pass's, never read twice).
2. WELL — per ANCHOR FAMILY (one anchor spelling: the well's floor,
   walls and the building are often several resources — OTHH's
   Parking-Left_000/005/007), the union of the witnesses' below-ground
   footprints closed at ``basin.footprint_close_m``, one well per
   connected part.
3. THE DOOR TEST — the well's SHELL (its witness components: the floor
   and the walls welded to it) is read apart from the BUILDING (every
   other component of the family's members whose plan reaches the
   well): the well's boundary is partly INSIDE the building's at-grade
   geometry (``obj8.at_grade_geometry`` polygons: the footprint, a slab
   edge — that portion is the SILL LINE, ≥ ``sill_min_width_m``) and
   partly outside (the well's own outer walls); the PLATE lies under
   at-grade solids — the building's roof over it, or the shell's own
   lid — for less than ``basin.basement_cover_min`` of its area, else
   the well is a BASEMENT (the pad governs, nothing is cut: spec §5
   "the same well under the roof → basement, nothing"; measured OTHH
   Terminal_Parking_002: a lidded box at +0.83, refused).  Every refusal
   names its reason (04i).
4. THE FRAME — the face direction is the sill line's, the outward
   normal points from the sill into the well; the sill WIDTH is the
   plate's extent along the face; the well's reach along the normal is
   the plate's; the ground at the sill is the median DEM along the sill
   line.  The walls' thickness (the rim's law, 09-08a) is the planar
   layer's measurement (``planar/door_ramps.py``).

Nothing numeric lives here; every value is a law-table argument.
"""
from __future__ import annotations

from ..model.frame import rotated_rectangle

import dataclasses as _dc
import math
import os
import time
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY
from . import obj8 as _obj8
from .deck_signature import family_key

__all__ = ["DoorWell", "DoorStats", "read_door_wells", "ID_PREFIX"]

ID_PREFIX = "door"
_MITRE = dict(join_style="mitre", mitre_limit=2.0)


@_dc.dataclass(frozen=True)
class DoorWell:
    """One basement access well in the airport frame.  ``sill_mid`` is
    the point on the sill line nearest the plate's centre; ``normal``
    the unit outward normal (from the building into the well);
    ``face_dir`` the unit vector along the sill; ``sill_line`` the
    well boundary along the building; ``sill_z`` the rendered floor
    (the plate faces' own deepest y); ``ground_z`` the ground at the
    sill; ``plate_out_m`` how far the plate reaches along the normal
    from the sill line, ``well_out_m`` the shell."""

    id: str
    resource: str
    objects: tuple[str, ...]
    region: Polygon
    plate: Polygon
    sill_line: LineString
    sill_mid: XY
    normal: XY
    face_dir: XY
    sill_width_m: float
    plate_out_m: float
    well_out_m: float
    sill_z: float
    ground_z: float
    plate_cover: float
    anchor_xy: XY
    anchor_dem_z: float
    agl_m: float
    notes: tuple[str, ...] = ()

    @property
    def depth_m(self) -> float:
        return self.ground_z - self.sill_z


@_dc.dataclass
class DoorStats:
    """What the reader saw, admitted and refused (every refusal names its
    reason and the resource)."""

    placements: int = 0
    screened: int = 0
    sill_witnesses: int = 0
    basin_gate_components: int = 0
    families: int = 0
    regions: int = 0
    wells: int = 0
    refused: list[str] = _dc.field(default_factory=list)
    read_s: float = 0.0


def _sill_witnesses(objects: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
                    dem_z, law: Law, stats: DoorStats
                    ) -> list[tuple[_obj8.PlacedObject, _obj8.FloorWitness, int]]:
    """Rule 1: ``(placement, witness, id(component))`` for the components
    carrying a plate at the door's gate and above the basin's."""
    bl = law.tables.structures.basin
    dl = law.tables.structures.cutout.door
    out: list[tuple[_obj8.PlacedObject, _obj8.FloorWitness, int]] = []
    for o in objects:
        if o.resolved is None or _obj8.is_stock_library_resource(o.path):
            continue
        stats.placements += 1
        g = cache.geometry(o.resolved)
        if g is None:
            continue
        base = o.anchor_z + o.agl_m
        vmin, _vmax, x0, x1, z0, z1 = cache.y_range(o.resolved)
        if vmin == math.inf:
            continue
        corners = [_obj8._to_frame(o.xy, o.heading_deg, x, zz) for x in (x0, x1) for zz in (z0, z1)]
        grounds = [z for z in [o.anchor_z] + [float(dem_z(cx, cy)) for cx, cy in corners]
                   if not math.isnan(z)]
        if not grounds or base + vmin > max(grounds) - dl.sill_min_depth_m:
            continue
        stats.screened += 1
        mat = _obj8.placement_affine(o.xy, o.heading_deg)
        for comp in cache.genuine(o.resolved):
            cx, cy = _obj8._to_frame(o.xy, o.heading_deg, comp.cx, comp.cz)
            local = float(dem_z(cx, cy))
            if math.isnan(local):
                local = o.anchor_z
            if bl.shell_reaches_grade and base + comp.max_y < local - bl.contact_band_m:
                continue                                   # buried, never a well
            plane_sill = local - base - dl.sill_min_depth_m
            if comp.min_y > plane_sill:
                continue
            if comp.min_y <= local - base - bl.admission_depth_m:
                stats.basin_gate_components += 1           # the basin pass's
                continue
            w = _obj8._witness(g.vertices, comp, base, local, plane_sill,
                               bl.floor_plate_normal_y_min, mat)
            if w is None:
                continue
            out.append((o, w, id(comp)))
            stats.sill_witnesses += 1
    return out


def _unit(a: XY, b: XY) -> XY:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)


def _extent(poly: Polygon, origin: XY, d: XY) -> tuple[float, float]:
    """``(min, max)`` of the polygon's vertices projected on ``d`` from ``origin``."""
    vals = [(x - origin[0]) * d[0] + (y - origin[1]) * d[1] for x, y in poly.exterior.coords]
    return min(vals), max(vals)


def _rect_sides(poly: Polygon) -> list[tuple[XY, XY]] | None:
    """The four sides of the polygon's minimum rotated rectangle."""
    mrr = rotated_rectangle(poly)
    if mrr.geom_type != "Polygon":
        return None
    c = list(mrr.exterior.coords)
    if len(c) < 5:
        return None
    return [((c[i][0], c[i][1]), (c[i + 1][0], c[i + 1][1])) for i in range(4)]


def _median_dem(line: LineString, dem_z, step: float) -> float | None:
    n = max(2, int(math.ceil(line.length / max(step, 1e-6))))
    vals = []
    for i in range(n + 1):
        p = line.interpolate(line.length * i / n)
        z = float(dem_z(p.x, p.y))
        if not math.isnan(z):
            vals.append(z)
    return float(np.median(vals)) if vals else None


class _AtGrade:
    """The family members' at-grade / above-band polygons NEAR a well,
    read per region through the ``within`` window (the terminal's
    150,000-triangle members are read in milliseconds): the BUILDING's
    (every component but the sill witnesses', wider than a post), the
    SHELL's (the witnesses' own: a lid over the plate is cover too) and
    the solids ABOVE the band (the cover the scout measured against)."""

    def __init__(self, cache, dem_z, band: float, witness_ids: set[int], min_span: float) -> None:
        self.cache, self.dem_z, self.band, self.wit = cache, dem_z, band, witness_ids
        self.min_span = min_span

    def building(self, o, within):
        g = self.cache.geometry(o.resolved)
        v = g.vertices if g is not None else None

        def is_building(c, _v=v) -> bool:
            # a post or a bollard (narrower than a sill in every plan
            # direction: OTHH's car-park columns, 0.55 m square) is never
            # the building face the sill line is read against
            if id(c) in self.wit or _v is None:
                return False
            pts = _v[c.tris.reshape(-1)]
            return max(float(pts[:, 0].max() - pts[:, 0].min()),
                       float(pts[:, 2].max() - pts[:, 2].min())) >= self.min_span
        return _obj8.at_grade_geometry(o, self.cache, self.dem_z, self.band, is_building,
                                       within=within)[1]

    def shell(self, o, within):
        return _obj8.at_grade_geometry(o, self.cache, self.dem_z, self.band,
                                       lambda c: id(c) in self.wit, within=within)[1]

    def above(self, o, within):
        return _obj8.above_grade_footprint(o, self.cache, self.dem_z, self.band, within=within)


def read_door_wells(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
                    cache: _obj8.ResourceCache, law: Law
                    ) -> tuple[list[DoorWell], DoorStats]:
    """Every basement access well the pack's objects state (module doc),
    in the airport frame; the stats name every refusal."""
    t0 = time.perf_counter()
    stats = DoorStats()
    bl = law.tables.structures.basin
    dl = law.tables.structures.cutout.door
    grid = law.tables.emit.identity.min_distinct_spacing_m
    dem_z = airport.dem.z
    wits = _sill_witnesses(objects, cache, dem_z, law, stats)
    if not wits:
        stats.read_s = time.perf_counter() - t0
        return [], stats
    by_fam: dict[tuple, list[tuple[_obj8.PlacedObject, _obj8.FloorWitness, int]]] = {}
    for o, w, cid in wits:
        by_fam.setdefault(family_key(o), []).append((o, w, cid))
    stats.families = len(by_fam)
    members_of: dict[tuple, list[_obj8.PlacedObject]] = {}
    for o in objects:
        if o.resolved is not None and not _obj8.is_stock_library_resource(o.path) \
                and o.plan_bbox is not None:
            k = family_key(o)
            if k in by_fam:
                members_of.setdefault(k, []).append(o)
    grade = _AtGrade(cache, dem_z, bl.contact_band_m, {cid for _o, _w, cid in wits},
                     dl.sill_min_width_m)
    to_ll = airport.frame.transformers()[1]
    out: list[DoorWell] = []
    k_by_res: dict[str, int] = {}
    for fk, fam in sorted(by_fam.items(), key=lambda kv: kv[0]):
        members = members_of.get(fk, [])
        tree = STRtree([o.plan_bbox for o in members]) if members else None
        u = unary_union([w.below for _o, w, _c in fam])
        u = u.buffer(bl.footprint_close_m, **_MITRE).buffer(-bl.footprint_close_m, **_MITRE)
        parts = [g for g in shapely.get_parts(u) if g.geom_type == "Polygon" and g.area > grid * grid]
        stats.regions += len(parts)
        for ring in sorted(parts, key=lambda g: -g.area):
            region = Polygon(ring.exterior.coords)
            mem = [(o, w) for o, w, _c in fam if w.below.intersects(region)]
            if not mem:
                continue
            o0, w0 = min(mem, key=lambda ow: ow[0].anchor_z + ow[0].agl_m + ow[1].plate_y_min)
            name = os.path.basename(o0.path)
            la, lo = to_ll(*region.centroid.coords[0])
            site = f"{la:.6f},{lo:.6f}"
            plate = unary_union([w.plate for _o, w in mem]).intersection(region)
            plate = plate.buffer(0) if not plate.is_valid else plate
            if plate.geom_type != "Polygon":
                plate = max((g for g in shapely.get_parts(plate) if g.geom_type == "Polygon"),
                            key=lambda g: g.area, default=None)
            if plate is None or plate.is_empty:
                stats.refused.append(f"{name} at {site}: no sill plate inside the well")
                continue
            # the cheap gates first (OTHH's car parks: 300 post footings of
            # 0.3 m2 per family): a plate narrower than the sill's minimum
            # width in every direction carries no door
            mrr = rotated_rectangle(plate)
            if mrr.geom_type != "Polygon" or plate.area < dl.sill_min_width_m ** 2 \
                    or max(math.dist(mrr.exterior.coords[i], mrr.exterior.coords[i + 1])
                           for i in range(len(mrr.exterior.coords) - 1)) < dl.sill_min_width_m:
                stats.refused.append(f"{name} at {site}: sill plate {plate.area:.1f} m2 too small "
                                     f"for a sill of sill_min_width_m {dl.sill_min_width_m}")
                continue
            # rule 3: the building's and the shell's at-grade geometry over
            # the well, from the members whose plan reaches it
            near = region.buffer(bl.footprint_close_m)
            reach = region.buffer(dl.max_length_m)
            hit = [members[int(j)] for j in tree.query(near, predicate="intersects")] \
                if tree is not None else []
            hit_reach = [members[int(j)] for j in tree.query(reach, predicate="intersects")] \
                if tree is not None else []
            bld_polys = [p for p in (grade.building(o, near) for o in hit) if p is not None]
            shell_polys = [p for p in (grade.shell(o, near) for o in hit) if p is not None]
            above_polys = [p for p in (grade.above(o, reach) for o in hit_reach) if p is not None]
            bld = unary_union(above_polys) if above_polys else None
            cover_u = unary_union(bld_polys + shell_polys + above_polys) \
                if (bld_polys or shell_polys or above_polys) else None
            plate_cover = 0.0 if cover_u is None else cover_u.intersection(plate).area / plate.area
            if plate_cover >= bl.basement_cover_min:
                stats.refused.append(f"{name} at {site}: sill plate {plate.area:.1f} m2 {plate_cover:.0%} "
                                     f"under at-grade solids (a roof, a lid; >= basement_cover_min "
                                     f"{bl.basement_cover_min:.0%}) — a BASEMENT, not a door (spec §5)")
                continue
            if bld is None or bld.is_empty:
                stats.refused.append(f"{name} at {site}: no building solids above the contact band "
                                     f"reach the well ({region.area:.1f} m2) — a pit on its own, not a door")
                continue
            # THE FACE (spec §2): the well's longer rectangle side nearer the
            # MASS of the family's above-band solids around it (the building
            # the well is attached to; the ramp leaves away from it along
            # the outward normal), the EXIT its opposite side, which must
            # lie mostly outside that cover (a slot under a slab is no door).
            # Measured OTHH: the car-park wells are closed four-walled boxes
            # hanging from the facade lattice, the door a texture on the
            # building-side wall — the at-grade band, the above-band cover
            # and the shell's walls all read alike on both long sides; the
            # building's mass is the one side-discriminating signal left
            # (the OPEN QUESTION the lane reports: no pack geometry names the
            # door side).
            sides = _rect_sides(region)
            if sides is None:
                stats.refused.append(f"{name} at {site}: the well has no plan rectangle")
                continue
            above_u = unary_union(above_polys)
            cm = above_u.centroid
            lens = [math.dist(a_, b_) for a_, b_ in sides]
            frac = [LineString([a_, b_]).intersection(above_u).length / max(L_, 1e-9)
                    for (a_, b_), L_ in zip(sides, lens)]
            near_cm = [math.dist(((a_[0] + b_[0]) / 2.0, (a_[1] + b_[1]) / 2.0), (cm.x, cm.y))
                       for a_, b_ in sides]
            long_pair = sorted(range(4), key=lambda i: -lens[i])[:2]
            i_sill = min(long_pair, key=lambda i: near_cm[i])
            i_exit = (i_sill + 2) % 4
            a, b = sides[i_sill]
            if frac[i_exit] > dl.exit_max_fraction:
                stats.refused.append(f"{name} at {site}: the side opposite the face lies under "
                                     f"above-band solids over {frac[i_exit]:.0%} of its length (> "
                                     f"exit_max_fraction {dl.exit_max_fraction:.0%}) — covered, not a door")
                continue
            sill = LineString([a, b])
            outside = region.exterior.difference(above_u.buffer(grid))
            face_dir = _unit(a, b)
            n = (-face_dir[1], face_dir[0])
            ex = sides[i_exit]
            exm = ((ex[0][0] + ex[1][0]) / 2.0, (ex[0][1] + ex[1][1]) / 2.0)
            mid0 = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            if (exm[0] - mid0[0]) * n[0] + (exm[1] - mid0[1]) * n[1] < 0.0:
                n = (-n[0], -n[1])
            pc = plate.centroid
            t = (pc.x - mid0[0]) * face_dir[0] + (pc.y - mid0[1]) * face_dir[1]
            mid = (mid0[0] + face_dir[0] * t, mid0[1] + face_dir[1] * t)
            lo_f, hi_f = _extent(plate, mid, face_dir)
            width = hi_f - lo_f
            if width < dl.sill_min_width_m:
                stats.refused.append(f"{name} at {site}: sill plate {width:.2f} m wide along the face "
                                     f"(< sill_min_width_m {dl.sill_min_width_m})")
                continue
            if width > dl.sill_max_width_m:
                stats.refused.append(f"{name} at {site}: sill plate {width:.2f} m wide along the face "
                                     f"(> sill_max_width_m {dl.sill_max_width_m}: a yard or a pit, not a door)")
                continue
            mid = (mid[0] + face_dir[0] * (lo_f + hi_f) / 2.0, mid[1] + face_dir[1] * (lo_f + hi_f) / 2.0)
            _lo_n, plate_out = _extent(plate, mid, n)
            _lo_w, well_out = _extent(region, mid, n)
            if plate_out <= 0.0:
                stats.refused.append(f"{name} at {site}: the sill plate reaches nowhere outside the face")
                continue
            # a plate that DESCENDS at or under the door law's own ramp grade
            # over its reach is a ramp of the object's own (OTHH
            # Terminal_Parking_006: a 21 m car-park ramp loop, 5 %), never a
            # sill; a well's steps down to its door are far steeper
            span = max(o.anchor_z + o.agl_m + w.plate_y_max for o, w in mem) - \
                min(o.anchor_z + o.agl_m + w.plate_y_min for o, w in mem)
            if span > 0.0 and span / plate_out <= dl.ramp_grade:
                stats.refused.append(f"{name} at {site}: the plate ({plate.area:.1f} m2) descends "
                                     f"{span:.2f} m over its {plate_out:.1f} m reach ({100.0 * span / plate_out:.1f} % "
                                     f"<= ramp_grade {100.0 * dl.ramp_grade:.0f} %) — a ramp of the "
                                     f"object's own, not a door sill")
                continue
            sill_z = o0.anchor_z + o0.agl_m + w0.plate_y_min
            ground = _median_dem(sill, dem_z, bl.rim_sample_step_m)
            if ground is None:
                stats.refused.append(f"{name} at {site}: no DEM along the sill")
                continue
            depth = ground - sill_z
            if depth < dl.sill_min_depth_m:
                stats.refused.append(f"{name} at {site}: sill {depth:.2f} m under the ground at the "
                                     f"face (< sill_min_depth_m {dl.sill_min_depth_m})")
                continue
            k = k_by_res.get(o0.path, 0)
            k_by_res[o0.path] = k + 1
            notes = (f"well {region.area:.1f} m2, sill plate {plate.area:.1f} m2 at {sill_z:.2f} "
                     f"({depth:.2f} m under the ground {ground:.2f} at the face)",
                     f"sill {width:.2f} m wide along the face, the plate {plate_out:.2f} m out, "
                     f"the well {well_out:.2f} m out",
                     f"plate under at-grade solids {plate_cover:.0%} (< basement_cover_min "
                     f"{bl.basement_cover_min:.0%}); the face side {near_cm[i_sill]:.1f} m from the "
                     f"building mass, under above-band solids {frac[i_sill]:.0%}; the exit side "
                     f"{near_cm[i_exit]:.1f} m / {frac[i_exit]:.0%}; boundary outside {outside.length:.1f} m; "
                     f"{len(hit)} member(s) read at grade",
                     f"{len(mem)} witness component(s) of {len({o.id for o, _w in mem})} placement(s)")
            out.append(DoorWell(f"{ID_PREFIX}:{name}@{k}", o0.path,
                                tuple(sorted({o.id for o, _w in mem})), region, plate, sill, mid, n,
                                face_dir, float(width), float(plate_out), float(well_out),
                                float(sill_z), float(ground), float(plate_cover),
                                o0.xy, float(o0.anchor_z), float(o0.agl_m), notes))
            stats.wells += 1
    out.sort(key=lambda w: w.id)
    stats.read_s = time.perf_counter() - t0
    return out, stats
