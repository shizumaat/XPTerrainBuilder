"""THE FIVE KEEP-OUT / OVERLAP FAMILIES v2 ``verify`` reads off the emitted
plan (issue #186): where a face stands, not what it is solved to.

* ``ramp_in_road`` — §34 (10), owner RULINGS 2026-09-14bd: a ramp arriving
  at a road ends at the road's TRUE edge, so a RAMP vertex inside a ROAD
  ribbon is a lane of carriageway cut away.
* ``ramp_in_strip`` — §34 (5) (b), RULINGS 2026-09-15h: the covered extent
  of an underpass spans the pavement AND its graded strip, so a ramp vertex
  inside that strip is a trench in the ground an aircraft runs out onto.
* ``zone_on_pavement`` — §41 (2), RULINGS 2026-09-13co item 2: an
  ``adjacent_ground:*`` strip standing on an aircraft-pavement face's
  SOLID, priced as an AREA.
* ``object_cut_offset`` / ``object_cut_depth`` — §33 (6), RULINGS
  2026-09-15e/15g: where the pack authored the trench, the cut's PLAN and
  DEPTH are the object's, published as ``object_cuts``.

ALL FIVE ARE PLAN READINGS OF THE DESIGN SURFACE, which is what ``verify``
is handed (``pipeline/build.census_frame(surf, …)``): the ramp faces, the
road ribbons, the pavement faces and their holes, the zone bands and the
structure rims are all faces or features of that surface, and the object
witness is a sidecar key ``Patch.publication`` carries.  Three of the five
are PRESENCE families (``cockpit = "keepout"``) — one vertex in the wrong
place is the whole defect whatever its elevation — so they are the guards
on their derivation sites, not defect counts.

THE POPULATIONS ARE LAW-DERIVED, never typed here (the census-wrapper
precedent, and ``check_grade`` flags every one of its own spellings as a
blast role-literal hazard): the ramp family is the law's STRUCTURE roles,
the road family is ``constraints.roads.road_family_roles``, the pavement
set is ``emit.terrace.shape_roles``, and the strip-declaring split is
``law.tables.role_family`` over that same set.

THE FRAME IS THE SOLID, for both the pavement and the strip
(``check_grade._zone_on_pavement_area``, NLWF 2026-09-21 / #18): a
pavement ring may enclose a large lawful HOLE (HECA's
``primary_parallel:pav73`` is a 202,427 m² loop around a 162,110 m² hole)
and a zone-2 strip is a RING whose hole is the runway's own outline.  Read
ring-blind, HECA's 1.0.329 patch reports 74 strips / 586,619 m² "on
pavement" where the ruling's own frame reports 0.0, and NLWF reports one
34,069.6 m² row on an airport whose strips stand on nothing.  Here the
holes come from the surface's own faces (:func:`_holed`), which is the
same geometry the sidecar ``face_holes`` key is derived from.
"""
from __future__ import annotations

from ..law.tables import (governed_roles, is_structure_role, role_family,
                          zone2_half_width_m)
from .frame import Patch, Row, Shape, row
from .frontage import _holed

__all__ = ["FAMILY_RAMP_IN_ROAD", "FAMILY_RAMP_IN_STRIP",
           "FAMILY_ZONE_ON_PAVEMENT", "FAMILY_OBJECT_CUT_OFFSET",
           "FAMILY_OBJECT_CUT_DEPTH", "ZONE_REF_PREFIX",
           "ZONE_ON_PAVEMENT_MIN_AREA_M2", "OBJECT_CUT_OFFSET_M",
           "OBJECT_CUT_DEPTH_M", "OBJECT_CUT_RIM_FEATURES",
           "ramp_roles", "strip_roles", "pavement_roles", "weld_tol_m",
           "strip_half_width_m", "ramp_in_road", "ramp_in_strip",
           "zone_on_pavement", "object_cut_offset", "object_cut_depth"]

FAMILY_RAMP_IN_ROAD = "ramp_in_road"
FAMILY_RAMP_IN_STRIP = "ramp_in_strip"
FAMILY_ZONE_ON_PAVEMENT = "zone_on_pavement"
FAMILY_OBJECT_CUT_OFFSET = "object_cut_offset"
FAMILY_OBJECT_CUT_DEPTH = "object_cut_depth"

#: The ref prefix of an adjacent-ground zone band
#: (``check_grade.V2_ADJACENT_GROUND_REF_PREFIX``; ``verify.cutback``'s own).
ZONE_REF_PREFIX = "adjacent_ground:"

#: §41 (2): the overlap area above which a strip on pavement is CRITICAL
#: and not emit rounding (``check_grade.ZONE_ON_PAVEMENT_MIN_AREA_M2``).
ZONE_ON_PAVEMENT_MIN_AREA_M2 = 0.5

#: §33 (6): the emitter's own snap — how far outside its object's wall line
#: a cut vertex may stand (``check_grade.OBJECT_CUT_OFFSET_M``) …
OBJECT_CUT_OFFSET_M = 0.5
#: … and how far the emitted floor may stand off the AUTHORED floor plate
#: (``check_grade.OBJECT_CUT_DEPTH_M``).
OBJECT_CUT_DEPTH_M = 0.10

#: The FEATURE classes an object cut's geometry wears beside its ramp
#: faces: the corridor RIM (``check_grade._OBJECT_CUT_RIM_CLASSES``).
OBJECT_CUT_RIM_FEATURES = frozenset({"structure_rim"})

#: §34 (5) (b) / §41 (2): the strip families, as ``role_family`` names them.
_STRIP_FAMILIES = ("runway", "taxi")
#: The ``zone2_half_width_m`` key each strip family is declared under
#: (``check_grade._strip_half_width_m``).
_STRIP_KEY = {"runway": "runway", "taxi": "junction"}


def weld_tol_m(p: Patch) -> float:
    """THE WELD TOLERANCE — the law's "these two vertices are one node"
    predicate (``emit.identity.min_distinct_spacing_m``), which is
    ``check_grade.SHARED_VERTEX_TOL_M``.  A vertex welded to a ribbon's or
    a strip's edge is NOT inside it: the ramp ending exactly where the road
    or the strip ends is what the law asks for, and the line is this
    predicate — never a proximity semantic invented here."""
    return float(p.law.tables.emit.identity.min_distinct_spacing_m)


def ramp_roles(p: Patch) -> frozenset[str]:
    """§34 (10): the RAMP family — v2's STRUCTURE roles, from the law
    (``tunnel_ramp``, ``door_ramp``, ``wall_corridor_ramp``,
    ``garage_ramp``), so the census and the emitter cannot drift."""
    return frozenset(r for r in governed_roles(p.law)
                     if is_structure_role(p.law, r))


def pavement_roles(p: Patch) -> frozenset[str]:
    """§41 (2): the AIRCRAFT-pavement roles a zone strip may never stand
    on — the emitter's own ``emit.terrace.shape_roles``.  Roads, pads,
    buildings and groundside are NOT here: a zone band's stand-off from
    those is ``zones.toml groundside_cutback_m``, already priced by
    ``verify.cutback``."""
    return frozenset(p.law.tables.emit.terrace.shape_roles)


def strip_roles(p: Patch) -> frozenset[str]:
    """§34 (5) (b): the roles that DECLARE a graded strip — the pavement
    set restricted to the RUNWAY and TAXI families.  ``planar/zones``
    builds a zone band around those two and nothing else, so nothing else
    declares a strip; the apron's family is ``common`` and drops out here
    exactly as it does in ``check_grade._RAMP_IN_STRIP_*_ROLES``."""
    return frozenset(r for r in pavement_roles(p)
                     if role_family(p.law, r) in _STRIP_FAMILIES)


def strip_half_width_m(p: Patch, sh: Shape) -> float:
    """``sh``'s zone-2 half width — the band ``planar/zones`` grades
    (``zones.toml adjacent_ground.*half_width_m`` through the law's own
    ``zone2_half_width_m``), falling back to the lip where the class
    declares none.  0.0 for a role that declares no strip."""
    fam = role_family(p.law, sh.role)
    key = _STRIP_KEY.get(fam) if sh.role in pavement_roles(p) else None
    if key is None:
        return 0.0
    hw = zone2_half_width_m(p.law, key, sh.code_number, sh.code_letter)
    if hw and float(hw) > 0.0:
        return float(hw)
    return float(p.law.tables.zones.adjacent_ground.lip_width_m)


def _solid(p: Patch, sh: Shape):
    """``sh`` as its own SOLID: the outer ring minus its hole rings, through
    ``verify.frontage._holed`` — THE one spelling of that read in this
    layer (issue #191), never a second accessor."""
    g = _holed(p, sh)
    return g if g.is_valid else g.buffer(0)


def _keepout_row(p: Patch, family: str, sh: Shape, vid: int, depth: float,
                 other: Shape) -> Row:
    """One PRESENCE row: the offending vertex, how far in it stands."""
    la, lo = p.ll.get(vid, (None, None))
    xy = p.xy.get(vid)
    return row(family, (sh.role, other.role or sh.role),
               p.side(sh.role), depth, None, None, depth, xy, xy,
               sh.ref, other.ref, lat=la, lon=lo)


def _ramp_vertices(p: Patch, roles: frozenset[str]):
    """``(shape, vertex id, Point)`` per distinct vertex of every ramp
    face — the population both ramp keep-out families walk."""
    from shapely.geometry import Point
    for sh in p.shapes:
        if sh.role not in roles:
            continue
        for vid in dict.fromkeys(sh.ids):
            xy = p.xy.get(vid)
            if xy is not None:
                yield sh, int(vid), Point(xy)


def ramp_in_road(p: Patch) -> list[Row]:
    """§34 (10) NO RAMP VERTEX INSIDE A ROAD RIBBON (owner RULINGS
    2026-09-14bd: "we should generalize this to allow this margin for ramps
    arriving at a road, not special case it for OTHH").

    CRITICAL, and a PRESENCE family: one vertex inside the ribbon is the
    whole defect whatever its elevation — the road it cuts is a lane of
    carriageway, and the pinch the ramp is in does not license taking it.
    Measured at OTHH: 0 in the owner's 1.0.335 patch and 0 after, so the
    family is the GUARD on ``planar/wall_corridor_ramps.road_true_edge``."""
    from ..constraints.roads import road_family_roles

    roads = frozenset(road_family_roles(p.law))
    ribbons = [(_solid(p, sh), sh) for sh in p.shapes if sh.role in roads]
    ribbons = [(g, sh) for g, sh in ribbons if not g.is_empty]
    if not ribbons:
        return []
    tol = weld_tol_m(p)
    out: list[Row] = []
    for sh, vid, pt in _ramp_vertices(p, ramp_roles(p)):
        for g, rw in ribbons:
            if not g.contains(pt):
                continue
            depth = pt.distance(g.exterior)
            if depth <= tol:
                continue            # welded to the ribbon's edge is not in it
            out.append(_keepout_row(p, FAMILY_RAMP_IN_ROAD, sh, vid, depth, rw))
            break
    out.sort(key=lambda r: -float(r["magnitude_m"]))
    return out


def _strip_bands(p: Patch):
    """``(band, shape)`` per strip-declaring face: the face's own SOLID
    grown by its class's zone-2 half width, MINUS that solid and minus
    every pavement solid.

    BOTH SUBTRACTIONS WERE MEASURED, not chosen (``check_grade.
    _check_ramp_in_strip``).  Read ring-blind and disc-shaped the first arm
    reported 52 rows at LEMD, every one inside ``cross_connector:pav61``'s
    own 144,429 m² HOLE — a road tunnel in a void the taxiway merely
    encloses, up to 220 m from any kerb, which is no graded strip by any
    reading.  And a band the PAVEMENT itself covers is that pavement's,
    never a strip (the senior-claim order ``planar/zones`` already
    applies), so ``de_m`` can never exceed the class's own half width."""
    from shapely.ops import unary_union

    pav = frozenset(pavement_roles(p))
    solids, bands = [], []
    for sh in p.shapes:
        if sh.role not in pav:
            continue
        g = _solid(p, sh)
        if g.is_empty:
            continue
        solids.append(g)
        hw = strip_half_width_m(p, sh)
        if hw <= 0.0:
            continue
        band = g.buffer(hw, join_style="mitre", mitre_limit=2.0).difference(g)
        if not band.is_empty:
            bands.append((band, sh))
    if not bands:
        return []
    pav_u = unary_union(solids)
    out = [(b.difference(pav_u), sh) for b, sh in bands]
    return [(b, sh) for b, sh in out if not b.is_empty]


def ramp_in_strip(p: Patch) -> list[Row]:
    """§34 (5) (b) NO STRUCTURE RAMP INSIDE THE STRIP OF THE WAY IT PASSES
    UNDER (Fable 2026-09-15; RULINGS 2026-09-15h; owner 15e item 7).

    The mouth opens beyond the strip, the ramp descends outside it, and the
    rim between is the strip's own surface.  CRITICAL and a PRESENCE family
    like :func:`ramp_in_road`: the strip is the ground an aircraft leaving
    the pavement runs out onto, and a 5 m trench face in it is the owner's
    "hole in the taxiway" (LEMD 40.4611623,-3.5444804: ramp face 961 at
    15.5 m from a kerb whose code-E strip is 19.0 m, a 5.42 m unbanked drop
    and the airport's worst CRITICAL VISUAL row).  A vertex welded to the
    strip's outer edge is OUTSIDE it."""
    bands = _strip_bands(p)
    if not bands:
        return []
    tol = weld_tol_m(p)
    out: list[Row] = []
    for sh, vid, pt in _ramp_vertices(p, ramp_roles(p)):
        for g, pw in bands:
            if not g.contains(pt):
                continue
            depth = min((pt.distance(part.exterior)
                         for part in getattr(g, "geoms", [g])
                         if part.geom_type == "Polygon" and part.covers(pt)),
                        default=0.0)
            if depth <= tol:
                continue
            out.append(_keepout_row(p, FAMILY_RAMP_IN_STRIP, sh, vid, depth, pw))
            break
    out.sort(key=lambda r: -float(r["magnitude_m"]))
    return out


def zone_on_pavement(p: Patch) -> list[Row]:
    """§41 (2) ZONES ARE CLIPPED OUT OF PAVEMENT (owner RULINGS
    2026-09-13co item 2): an ``adjacent_ground:*`` strip standing on an
    aircraft-pavement face's SOLID.

    ONE ROW PER STRIP, its magnitude the OVERLAP AREA in m² and no grade
    priced — the defect is that two authorities own one patch of ground,
    which breaks no pair law (a face lying flat on another reports zero
    pair rows however wrong it is).  Measured on the owner's 1.0.329 HECA
    patch: 0 rows — ``planar/zones.py`` already subtracts every cell at the
    zone's own derivation site, so the family is the GUARD on that and the
    instrument the ruling is stated in."""
    from shapely.ops import unary_union

    pav = frozenset(pavement_roles(p))
    solids = [g for g in (_solid(p, sh) for sh in p.shapes
                          if sh.role in pav) if not g.is_empty]
    if not solids:
        return []
    pav_u = unary_union(solids)
    bar = float(ZONE_ON_PAVEMENT_MIN_AREA_M2)
    out: list[Row] = []
    for sh in p.shapes:
        if not str(sh.ref or "").startswith(ZONE_REF_PREFIX):
            continue
        s = _solid(p, sh)
        if s.is_empty:
            continue
        hit = s.intersection(pav_u)
        area = float(hit.area)
        if area <= bar:
            continue
        c = (hit if not hit.is_empty else s).representative_point()
        site = (c.x, c.y)
        la, lo = p.to_ll(c.x, c.y)
        out.append(row(FAMILY_ZONE_ON_PAVEMENT, (sh.role,), p.side(sh.role),
                       area, None, None, None, site, site, sh.ref, sh.ref,
                       lat=la, lon=lo))
    out.sort(key=lambda r: -float(r["magnitude_m"]))
    return out


def _object_cut_regions(p: Patch):
    """``(id, outline polygon in the census frame, authored floor)`` per
    published ``object_cuts`` record.  The outline is the OBJECT'S OWN wall
    line (``pipeline/publication.object_cuts``), never re-derived here —
    one witness, two instruments (the ``shore_edges`` precedent)."""
    from shapely.geometry import Polygon

    out = []
    for rec in (p.publication.get("object_cuts") or ()):
        if not isinstance(rec, dict):
            continue
        ring = [p.to_m(float(la), float(lo))
                for la, lo in (rec.get("outline_ll") or ())]
        if len(ring) < 3:
            continue
        g = Polygon(ring)
        if not g.is_valid:
            g = g.buffer(0)
        if g.is_empty:
            continue
        out.append((str(rec.get("id") or ""), g, rec.get("floor_m")))
    return out


def _cut_faces(p: Patch):
    """The faces and features an object cut's own geometry wears: the ramp
    faces and the corridor RIM (``structure_rim``)."""
    roles = ramp_roles(p)
    for sh in p.shapes:
        if sh.role in roles:
            yield sh
    for sh in p.features:
        if sh.feature in OBJECT_CUT_RIM_FEATURES:
            yield sh


def object_cut_offset(p: Patch) -> list[Row]:
    """§33 (6) THE CUT NEVER LEAVES ITS OBJECT (owner RULINGS
    2026-09-15e/15g): a vertex of a ramp or rim face that stands PARTLY
    INSIDE the object's wall line, standing outside it.

    THE SELECTION IS BY OVERLAP, not by ref: an emitted ramp face's ``ref``
    is its ROLE, the same string for every corridor in the patch, so a ref
    join would price every ramp of the airport against every object.  A
    face with at least one vertex inside the wall line is THAT object's
    cut; a face wholly outside is another corridor's and is not read here.

    Measured at VHHH before §33 (6): 25 of the 42 vertices of ramp way
    -11078 and 10 of way -10711's 20 stood outside ``tunnel5_done.obj``,
    the worst 76.25 m away, because the corridor was the OSM bore's and the
    object was read as a basin.  CRITICAL and a PRESENCE family."""
    from shapely.geometry import Point

    regions = _object_cut_regions(p)
    if not regions:
        return []
    tol = max(weld_tol_m(p), OBJECT_CUT_OFFSET_M)
    out: list[Row] = []
    for sh in _cut_faces(p):
        pts = [(int(v), Point(p.xy[v])) for v in dict.fromkeys(sh.ids)
               if v in p.xy]
        if not pts:
            continue
        for _cid, g, _floor in regions:
            if not any(g.contains(pt) for _v, pt in pts):
                continue                      # another corridor's face
            for vid, pt in pts:
                if g.contains(pt):
                    continue
                d = pt.distance(g)
                if d <= tol:
                    continue
                out.append(_keepout_row(p, FAMILY_OBJECT_CUT_OFFSET, sh,
                                        vid, d, sh))
            break
    out.sort(key=lambda r: -float(r["magnitude_m"]))
    return out


def object_cut_depth(p: Patch) -> list[Row]:
    """§33 (6) THE DEPTH IS AUTHORED: the emitted floor inside an object cut
    — the LOWEST ramp vertex standing in its wall line — against the floor
    the OBJECT states (``object_cuts[].floor_m``).

    "The FLOOR PLATE's level in the seated frame is the floor (the depth is
    AUTHORED — it overrides ``bore_datum_m``, which is the law for
    UNAUTHORED bores only)."  Measured at VHHH before §33 (6): the owner's
    site read 2.23 against the authored 1.31, 0.92 m too shallow, because
    the bore law's ``bore_datum_m`` 5.10 was subtracted from the DEM.

    One row per cut that misses :data:`OBJECT_CUT_DEPTH_M`, at the
    offending vertex.  A cut with no emitted ramp vertex inside it prices
    nothing — absence is the §29 / §34 (12) gates' business."""
    from shapely.geometry import Point

    regions = _object_cut_regions(p)
    if not regions:
        return []
    roles = ramp_roles(p)
    out: list[Row] = []
    for _cid, g, floor in regions:
        if floor is None:
            continue
        best: tuple[float, Shape, int] | None = None
        for sh in p.shapes:
            if sh.role not in roles:
                continue
            for vid in dict.fromkeys(sh.ids):
                xy, z = p.xy.get(vid), p.z.get(vid)
                if xy is None or z is None or not g.contains(Point(xy)):
                    continue
                if best is None or float(z) < best[0]:
                    best = (float(z), sh, int(vid))
        if best is None:
            continue
        z, sh, vid = best
        d = abs(z - float(floor))
        if d <= OBJECT_CUT_DEPTH_M:
            continue
        la, lo = p.ll.get(vid, (None, None))
        xy = p.xy.get(vid)
        out.append(row(FAMILY_OBJECT_CUT_DEPTH, (sh.role,), p.side(sh.role),
                       d, None, None, None, xy, xy, sh.ref, sh.ref,
                       lat=la, lon=lo))
    out.sort(key=lambda r: -float(r["magnitude_m"]))
    return out
