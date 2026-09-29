"""Adjacent-ground ZONE regions (RULINGS 2026-08-01 zone law; memory
``adjacent-ground-zone-law``; ``law/zones.toml``).

Around every runway-family and taxi-family face: zone 1 (the lip,
``lip_width_m`` out from the pavement edge) and zone 2 (the graded band
out to ``zone2_half_width_m`` for the class); beyond zone 2 the DEM is
untouched, so no face exists there.  Zone regions are ``graded_strip``
faces (a non-value role: they trace a lawful bound) carrying the class
that keys the law (``code_number`` for runways, ``code_letter`` for
taxiways) so the M2 zone generator can call ``zone_bounds``.

Seniority: the runway family's strip claims first (``strip area never
apron population``, RULINGS :1672), then the taxi family's; pavement,
pads and roads are never strip.  Buffers are mitred so the rings stay
arc-free (v1 groundside clip convention).
"""
from __future__ import annotations

import dataclasses as _dc
import math

import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..classify.roles import TAXI_FAMILY, Cell, is_runway_shoulder
from ..law import Law
from ..law.tables import snap_margin_m, zone2_half_width_m
from .shore import (SHORE_WALL_TAGS, ShoreVerdict, shore_contact,
                    shore_declarations, shore_verdict)
from .terrain_edge import EdgeReport, clip_to_terrain_edge

__all__ = ["ZoneRegion", "zone_regions", "shore_region", "shore_declarations",
           "SHORE_WALL_TAGS", "shore_wedge_m", "road_exit_corridors",
           "road_exit_cutback", "RoadExit", "ROAD_EXIT_PREFIX"]

RUNWAY_FAMILY = ("runway", "runway_crossing")
_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def shore_region(cells: tuple[Cell, ...], dem):
    """§37 (11) (1) THE WATER REGION THE SHORE TRIMS THE ZONES WITH (owner
    RULINGS 2026-09-15f item 2; Fable 2026-09-15i).

    ONE WITNESS, and it is not this module's: ``dem.water_geometry`` —
    the production frame's ``TileWater``, built from the tile's cached
    coastline and water layers (``O4_Vector_Map.cached_tile_water``), the
    same product the mesh constrains and the same object the flat-site
    datum region is already cut with (owner 2026-09-09m (3)) and §39 (i)
    (RULINGS 2026-09-13cg) named as the emitter's shore witness.  Nothing
    here re-derives a coastline from the OSM ways.

    THE AIRPORT'S OWN SURFACES ARE LAND BY DECLARATION, and this is not a
    nicety: at VMMC **110,826 m² — 24.5 % — of the runway/taxi union lies
    INSIDE the coastline partition's sea**, because the field stands on
    reclaimed land OSM's coastline does not follow.  Clipping the zones
    by the raw witness would cut the band away from the pavement it
    serves.  The same reading is already law elsewhere: ``constraints/
    water.water_pins`` pins only GROUND vertices and never a pavement one
    ("an apron over water is a deck, not water").  So the water region is
    the witness MINUS every classified cell.

    THE SHORE IS THE SEA, NOT EVERY WET POLYGON.  The witness's own
    partition is read through ``sea_geometry`` where the sampler has one:
    §37 (11) is the COAST's law (its level is the tile's sea, its wall is
    the mesh's seawall breakline, the owner's words are "a taxiway in the
    water"), while an inland canal or retention basin keeps the 09-09m
    WATER DATUM — the ground stands over it and is PINNED to its median
    level.  Trimming the zones at an inland body would delete that law's
    whole population (measured: ``tests/auto_patch_v2/test_water_datum``'s
    canal), and it would cut the band at LEMD's retention basins, which
    are §24's region and not this one's.

    ``None`` where there is no witness (every synthetic fixture) or no
    sea beside the field — and the regions are then what they were."""
    # THE SEA WITNESS ONLY.  A sampler that answers "is this wet" but not
    # "is this the SEA" claims NO shore here: no witness, no trim.
    fn = getattr(dem, "sea_geometry", None)
    if not callable(fn) or not cells:
        return None
    land = unary_union([Polygon(c.ring, c.holes) for c in cells])
    try:
        w = fn(land.buffer(500.0).bounds)
    except Exception:                                   # pragma: no cover
        return None
    if w is None or w.is_empty:
        return None
    w = w.difference(land)
    return None if w.is_empty else w


# §37 (11) (7) / 29a: ``SHORE_WALL_TAGS`` and ``shore_declarations`` live
# in ``planar/shore`` (the one shore decision) and are re-exported here.


@_dc.dataclass(frozen=True)
class ZoneRegion:
    """One zone face source."""

    ref: str
    polygon: Polygon
    zone: int
    family: str
    code_number: int | None
    code_letter: str | None
    #: THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c; spec §19): which
    #: rule ended this region — ``"crest"``, ``"road"`` or ``"none"``.
    edge_kind: str = "none"
    #: The edge SEGMENTS this region's trim made, in the frame: the
    #: boundary beyond which there is no patch and no bank.
    edge_lines: tuple = ()
    #: §37 (11) (2) THE QUAY (owner RULINGS 2026-09-15f item 2): this
    #: region reaches the COASTLINE, so the land between the pavement
    #: edge and the water ran out before the band did — it is narrower
    #: than lip + half-width by construction.  Such land is ONE PLANE at
    #: the pavement edge's level, ending at the coastline in a SEA WALL;
    #: it takes no zone band (a relaxed band is still a fall).
    quay: bool = False
    #: §37 (11) (7) (owner RULINGS 2026-09-27a (7)): this region reaches a
    #: NATURAL shore — no quay or wall is declared there and the land is
    #: wider than the lip — so it SLOPES to the water line: its band falls
    #: at up to the bank slope (1:3, ``emit.design.bank_slope``) and its
    #: coastline vertices take the water level.  No vertical face.
    natural_shore: bool = False
    #: §37 (11) (7): the part of a natural-shore region the slope lives in —
    #: the land within ``shore_wedge_m`` of the coast (the run a 1:3 bank
    #: needs to fall from the field to the sea).  Only here does the band
    #: fall at the bank slope; farther ground keeps its class's band.
    #: ``None`` = the whole region (no wedge width stated).
    shore_wedge: Polygon | None = None
    #: §37 (11) THE SHORE DECISION (owner RULINGS 2026-09-29a): the verdict
    #: on this region's coastline contact (``planar/shore.shore_verdict``)
    #: — ``quay`` / ``natural_shore`` above are its kind; the witness and
    #: the height ride along for the report.  ``None`` = no contact.
    shore: ShoreVerdict | None = None


def zone_regions(cells: tuple[Cell, ...], law: Law,
                 keepouts: tuple[tuple, ...] = (), dem=None, roads=(),
                 edge_report: EdgeReport | None = None,
                 declared: tuple = (),
                 shore_wedge_m: float | None = None,
                 pack_walls: tuple = (),
                 road_cut: tuple = ()) -> list[ZoneRegion]:
    """Zone 1 / zone 2 regions around the airside runway and taxi faces,
    minus every cell (pavement, pads, roads), minus senior strips and
    minus the ``keepouts`` (structure footprints: the zones stop at the
    tunnel wall, M4).

    With a ``dem`` (and the tile's OSM road centrelines) every region is
    also CLIPPED BY THE TERRAIN EDGE at this single derivation site
    (``planar/terrain_edge.py``; owner RULINGS 2026-09-10b/10c, spec §19): the
    adjacent ground ends at a rim road or a crest.  Without one — every
    synthetic fixture — the regions are what they were."""
    ag = law.tables.zones.adjacent_ground
    # groundside pavement (roads, lots) buffered by the stand-off: a zone
    # band never shares a vertex with it — the gap terraces (groundside
    # terrace law; ``zones.toml groundside_cutback_m``).  The stand-off
    # holds AFTER the identity snap (``tables.snap_margin_m``, 04u): the
    # same construction as the pad set-back, so the band never enters the
    # gap a pad's knife opened in a lot
    cut = ag.groundside_cutback_m + snap_margin_m(law)
    # A ZONE BAND YIELDS ONLY TO A TUNNEL CORRIDOR (spec §34 (4) as
    # NARROWED, RULINGS 2026-09-13ar; owner item 8 = a road AT A TUNNEL).
    # The ``keepouts`` are the structure corridors' outer rings (mouth,
    # ramp, trench, underpass — ``planar/structures``), and they are
    # subtracted with the SAME stand-off a groundside cell gets, so the
    # band never shares a vertex with the corridor's rim: the gap terraces
    # against the ramp walls, which is what the corridor already is.
    # Round 2's general "yields to every mapped road" trim is WITHDRAWN —
    # measured, it exposed ``zone2#24``'s own outer ring (an 8.49 m edge
    # over 12.03 m at 40.5331907, −3.5748496, terrain the band used to
    # spread across its interior) and cost 671
    # ``graded_strip|graded_strip`` ``within_shape`` rows against zero in
    # the base.  A road elsewhere inside adjacent ground grades WITH the
    # zone (the standing law).
    everything = unary_union(
        [Polygon(c.ring, c.holes).buffer(cut, **_MITRE)
         if c.side == "groundside" else Polygon(c.ring, c.holes) for c in cells]
        + [Polygon(k).buffer(cut, **_MITRE) for k in keepouts]
        # ROAD EXIT CORRIDORS ARE GROUNDSIDE PAVEMENT HERE (spec road-exit
        # §1.1 (4), consumer row 1): already buffered by the same stand-off
        # and minus their mouth boxes (``road_exit_cutback``) — the ONE
        # stand-off mechanism; nothing else subtracts bands from corridors
        + list(road_cut)) if cells else Polygon()
    lip = ag.lip_width_m
    groups: dict[tuple[str, int | None, str | None], list[Polygon]] = {}
    for c in cells:
        # §40 (4) (owner RULINGS 2026-09-14s): a SHOULDER manufactures no
        # zone band — it inherits its host runway's, which it lies inside
        # (`rules.toml`'s own words, measured at VHHH: 587,849 m2 of
        # zone-2 band the shoulders minted).  The spec's §40 (4) MEASURED
        # table is the census of every RUNWAY_FAMILY reader.
        if c.role in RUNWAY_FAMILY and not is_runway_shoulder(c):
            key = ("runway", c.code_number, None)
        elif c.role in TAXI_FAMILY:
            key = ("taxi", None, c.code_letter)
        else:
            continue
        groups.setdefault(key, []).append(Polygon(c.ring, c.holes))

    def rank(key: tuple[str, int | None, str | None]) -> tuple[int, float]:
        fam, cn, cl = key
        hw = zone2_half_width_m(law, "runway" if fam == "runway" else "junction",
                                cn, cl) or 0.0
        return (0 if fam == "runway" else 1, -hw)

    # §37 (11) (1) THE SHORE TRIMS THE ZONES, at this single derivation
    # site and never as a per-consumer veto (owner RULINGS 2026-08-30l).
    # No zone ring, lip or band is emitted seaward of the coastline, so no
    # patch vertex stands on the water: VMMC 1.0.340 emitted 13 zone faces
    # ACROSS the coastline (3–195 m) whose rings stood at exactly 0.00 up
    # to 42 m seaward — the second, translucent water plane in the owner's
    # screenshot, and 193 ground vertices the water datum then pinned to
    # sea level.  Where the pavement edge IS the coastline the zone simply
    # has nowhere to go: the pavement edge is the SEA WALL (§37 (11) (2)),
    # and the mesh's own Round 7 / R17-3 sea-wall breaklines
    # (``O4_Vector_Map.seawall_breaklines``, authored for this airport)
    # make the vertical face from the ring the patch ends at.
    water = shore_region(cells, dem)
    claimed = everything
    out: list[ZoneRegion] = []
    for key in sorted(groups, key=rank):
        fam, cn, cl = key
        role = "runway" if fam == "runway" else "junction"
        hw = zone2_half_width_m(law, role, cn, cl)
        if hw is None or hw <= 0:
            continue
        u = unary_union(groups[key])
        inner = u.buffer(min(lip, hw), **_MITRE)
        outer = u.buffer(hw, **_MITRE)
        z1 = inner.difference(claimed)
        z2 = outer.difference(inner).difference(claimed)
        cls = f"{cn}" if fam == "runway" else f"{cl or 'default'}"
        for zone, geom, seed in ((1, z1, u), (2, z2, inner)):
            if water is not None and not geom.is_empty:
                wet = geom.intersection(water)
                if not wet.is_empty and wet.area > 0.0:
                    geom = geom.difference(water)
                    # the difference can hand back a GeometryCollection
                    # (zero-area slivers along the coast), whose
                    # ``boundary`` is None — VMMC's dry planar died here
                    # (issue #72 verification).  The zone is an AREA: its
                    # polygonal parts are the whole of it.
                    if geom.geom_type == "GeometryCollection":
                        geom = unary_union([
                            p for p in shapely.get_parts(geom)
                            if p.geom_type in ("Polygon", "MultiPolygon")])
                    if edge_report is not None:
                        edge_report.shore_cut_m2 += float(wet.area)
                        edge_report.shore_regions += 1
                        edge_report.shore_edge_m += float(
                            geom.boundary.intersection(
                                water.boundary.buffer(snap_margin_m(law))).length)
            # THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c, spec §19):
            # the extent ends at the physical edge, HERE, so every reader
            # downstream sees one trimmed polygon
            clip = clip_to_terrain_edge(geom, seed, dem, roads, law,
                                        edge_report)
            geom = clip.kept
            parts = shapely.get_parts(geom) if geom.geom_type != "Polygon" else [geom]
            k = 0
            for g in parts:
                if g.geom_type != "Polygon" or g.is_empty or g.area < 1.0:
                    continue
                mine = tuple(ln for ln in clip.lines
                             if ln.distance(g) <= snap_margin_m(law))
                # §37 (11) THE SHORE DECISION (owner RULINGS 2026-09-29a):
                # a part that REACHES the coastline is decided ONCE, by
                # precedence — declared, pack wall, pavement edge on the
                # coast, terrain profile, default natural
                # (``planar/shore.shore_verdict``).
                reach = bool(water is not None
                             and g.distance(water) <= snap_margin_m(law))
                quay = natural = False
                wedge = None
                verdict = None
                if reach:
                    verdict = shore_verdict(
                        shore_contact(g, water, law), pavement=u, water=water,
                        law=law, declared=declared, pack_walls=pack_walls,
                        dem=dem)
                    quay = verdict.kind == "quay"
                    natural = not quay
                    if natural and shore_wedge_m is not None:
                        wedge = g.intersection(water.buffer(shore_wedge_m, **_MITRE))
                out.append(ZoneRegion(f"adjacent_ground:{fam}:{cls}:zone{zone}#{k}",
                                      g, zone, fam, cn, cl,
                                      clip.kind if mine else "none", mine, quay,
                                      natural, wedge, verdict))
                k += 1
        claimed = unary_union([claimed, outer])
    return out


#: §37 (11) (7): the head room a natural-shore wedge is sized with above the
#: field elevation (a pavement edge standing a little over the apt.dat
#: field elevation still meets the sea inside the wedge).  An ASSUMPTION of
#: this lane, stated where it is used, never a law.
SHORE_WEDGE_HEADROOM_M = 1.0


def shore_wedge_m(law: Law, field_elevation_m: float) -> float:
    """§37 (11) (7): the width of land beside a natural coast in which the
    strip falls at the bank slope — the lip plus the run a 1:3 bank needs
    to fall from the field (``field_elevation_m`` above the sea, plus
    :data:`SHORE_WEDGE_HEADROOM_M`) to the water line."""
    bank = float(law.tables.emit.design.bank_slope)
    lip = float(law.tables.zones.adjacent_ground.lip_width_m)
    h = max(float(field_elevation_m), 0.0) + SHORE_WEDGE_HEADROOM_M
    return lip + h / bank


#: RULINGS 2026-09-29r: the ref prefix of a ROAD EXIT CORRIDOR region
#: (``road_exit_corridors``).  ``constraints/zones`` reads it so the band's
#: own seam vertices stay banded (the band is never lifted for the road).
ROAD_EXIT_PREFIX = "road_exit:"


@_dc.dataclass(frozen=True)
class RoadExit:
    """One road exit corridor (spec ``road-exit-corridor-spec.md`` §1):
    where a mapped road LEAVES an adjacent-ground band onto ground that is
    not the band's level, the stretch of its own lane ribbon the road cap
    needs to climb (or fall) from the band's level to the terrain."""

    ref: str
    polygon: Polygon
    exit_xy: tuple[float, float]
    step_m: float           # DEM at the exit minus the band-level estimate
    length_m: float         # the corridor's run along the road
    #: §1.1 (1) THE AXIS: the OSM way's own centreline from the mouth(s)
    #: outward, one polyline per mouth (published ``road_exit_axes``)
    axes: tuple = ()
    #: per axis: the pre-solve band-level estimate at its mouth (sizes the
    #: polygon and seeds the centreline profile target, §1.3 (3))
    z_mouth: tuple = ()
    #: §1.4 report: "terminal exit" / "runway-end corner" / "in-band pocket"
    kind: str = "terminal exit"
    #: §1.1 (4): the mouth keep-out boxes — the band is NOT cut back here
    mouths: tuple = ()
    #: §1.4: the whole OSM way the corridor lies on (its route frame axis)
    route: LineString | None = None
    #: §1.1 (4) v2: the corridor's BANK-FOOT strip — the axis buffered by
    #: the lane half-width plus ``w(s)``, the width a <= 1:3 bank needs to
    #: fall from the profile to the band's level (the band's cut-back)
    bank: Polygon | None = None


def road_exit_cutback(exits: list, law: Law) -> tuple:
    """§1.1 (4) / consumer row 1: the corridors as GROUNDSIDE PAVEMENT for
    :func:`zone_regions`' one cut-back — each corridor buffered by the
    stand-off (``groundside_cutback_m`` + snap), minus its mouth boxes so
    the band it exits is not cut at the mouth.  The band is trimmed at its
    single derivation site; the corridor stays one ribbon."""
    ag = law.tables.zones.adjacent_ground
    cut = float(ag.groundside_cutback_m) + snap_margin_m(law)
    out = []
    for rx in exits:
        g = rx.polygon.buffer(cut, **_MITRE)
        if rx.bank is not None and not rx.bank.is_empty:
            g = unary_union([g, rx.bank])
        for m in rx.mouths:
            g = g.difference(m)
        if not g.is_empty:
            out.append(g)
    return tuple(out)


def _family_levels(cells, zones, dem, law: Law):
    """The pre-solve level of a band of each family at a point: the DEM of
    the family's nearest pavement less its mandatory minimum fall over the
    distance (the in-band pocket's step estimate, §1.2)."""
    t = law.tables.zones.adjacent_ground
    fams = {}
    for c in cells or ():
        if c.side != "airside":
            continue
        if c.role in RUNWAY_FAMILY and not is_runway_shoulder(c):
            fams.setdefault("runway", []).append(Polygon(c.ring, c.holes))
        elif c.role in TAXI_FAMILY:
            fams.setdefault("taxi", []).append(Polygon(c.ring, c.holes))
    fams = {k: unary_union(v) for k, v in fams.items()}

    def level(fam: str, pt) -> float | None:
        u = fams.get(fam)
        if u is None or u.is_empty:
            return None
        from shapely.ops import nearest_points
        q = nearest_points(u, pt)[0]
        down = float((t.runway if fam == "runway" else t.taxi).band_min_down)
        return float(dem.z(q.x, q.y)) - down * u.distance(pt)
    return level


def road_exit_corridors(zones: list, cells: tuple[Cell, ...], law: Law,
                        dem, roads=(), water=None,
                        wedge_m: float | None = None) -> list[RoadExit]:
    """RULINGS 2026-09-29r/29u/29y/29ab; spec ``road-exit-corridor-spec.md``
    §1.  INSIDE one continuous adjacent-ground band the road grades WITH
    the zone (13ar — nothing is minted there).  Where a mapped road LEAVES
    the band onto ground whose DEM stands ``>= cockpit.visual_m`` off the
    band's (estimated) level, its own LANE RIBBON (``road_half_width_m``
    less the cut-back: the cut-back is not road face) is a ROAD from the
    MOUTH (the road centreline on the band boundary) outward along the OSM
    way, for as long as the 8 % cap needs to meet the DEM (+25 % slack +
    one edge grid).

    The ribbon is square-capped into the band and differenced by the UNCUT
    bands, the airside cells and every groundside cell, so its mouth
    cross-section is the band's own boundary.  NO stand-off is subtracted
    here: the stand-off is the band's cut-back from the corridor
    (:func:`road_exit_cutback` fed to :func:`zone_regions`).  The corridor
    is clipped by the sea widened by the natural-shore wedge
    (``wedge_m``), and a mouth inside that wedge is not minted: the road
    ends at the sea and the band's shore law governs there (§1.1 (5)).

    IN-BAND POCKET (29ab (1)): where the road, walking INWARD from the
    mouth, crosses from the exit band into a band of the other family whose
    estimated level differs by ``>= visual_m``, the corridor extends inward
    across that boundary for the cap's reach; its inner end is the mouth."""
    if dem is None or not roads or not zones:
        return []
    from .terrain_edge import road_half_width_m
    from ..law.tables import role_cap
    from shapely.geometry import Point
    from shapely.ops import substring
    ag = law.tables.zones.adjacent_ground
    cap = float(role_cap(law, "service_road").longitudinal)
    cutback = float(ag.groundside_cutback_m)
    half = road_half_width_m(law) - cutback       # the lane: §1.1 (2)
    grid = float(law.tables.emit.design.edge_grid_m)
    snap = snap_margin_m(law)
    min_step = float(law.tables.emit.cockpit.visual_m)
    weld = float(law.tables.emit.identity.weld_spacing_m)
    bank_slope = float(law.tables.emit.design.bank_slope)
    ROAD_EXIT_CANDIDATES.clear()
    bands = unary_union([z.polygon for z in zones])
    paved = unary_union([Polygon(c.ring, c.holes) for c in cells
                         if c.side == "airside"]) if cells else Polygon()
    ground_cells = unary_union([Polygon(c.ring, c.holes) for c in cells
                                if c.side != "airside"]) if cells else Polygon()
    inside = unary_union([bands, paved])
    sea = None
    if water is not None and not water.is_empty:
        sea = water.buffer(max(float(wedge_m or 0.0), snap), **_MITRE)
    blocked = unary_union([g for g in (inside, ground_cells, sea)
                           if g is not None and not g.is_empty])
    level = _family_levels(cells, zones, dem, law)
    zone_of = [(z, z.polygon) for z in zones]

    def fam_at(pt):
        for z, g in zone_of:
            if g.covers(pt):
                return z.family
        best = min(zone_of, key=lambda t_: t_[1].distance(pt), default=None)
        return best[0].family if best and best[1].distance(pt) <= snap else None

    out: list[RoadExit] = []
    k = 0
    for road in roads:
        if road.distance(bands) > snap:
            continue
        rest = road.difference(inside)
        for piece in getattr(rest, "geoms", [rest]):
            if piece.geom_type != "LineString" or piece.length < grid:
                continue
            a, b = piece.coords[0], piece.coords[-1]
            ends = [c for c in (a, b) if bands.distance(Point(c)) <= snap]
            stretches, axes, zm, mouths, steps = [], [], [], [], []
            kind = "terminal exit"
            for p0 in ends:
                # §1.1 (5): no mouth inside the shore wedge
                if sea is not None and sea.distance(Point(p0)) <= snap:
                    continue
                line = piece if p0 == a else LineString(piece.coords[::-1])
                # §1.2 v2 (29ae (iii)): the band's OWN level estimate at
                # the mouth (the family's nearest pavement less its
                # mandatory fall), and the DRAPE-EXCESS gate
                rd0 = road.project(Point(p0))
                fam_m = None
                for sgn in (-1.0, 1.0):
                    q = road.interpolate(rd0 + sgn * grid / 2.0)
                    if bands.covers(q):
                        fam_m = fam_at(q)
                        break
                z_band = level(fam_m, Point(p0)) if fam_m else None
                if z_band is None:
                    z_band = _band_level(paved, zones, p0, dem, law, grid)
                step = float(dem.z(p0[0], p0[1])) - z_band
                e, need = _drape_excess(line, z_band, dem, cap, grid)
                ROAD_EXIT_CANDIDATES.append(((float(p0[0]), float(p0[1])),
                                             step, e, e >= min_step, z_band))
                if e < min_step:
                    continue
                # §5 (4): the corridor runs until the cap-limited profile
                # meets the DEM (+25 % slack on the estimate, + one grid)
                run = min(line.length,
                          (1.25 * need if need is not None else line.length) + grid)
                st = substring(line, 0.0, run)
                # IN-BAND POCKET (29ab (1)): walk the road INWARD from the
                # mouth; a crossing into the other family's band with a
                # visible step extends the corridor across it
                inward = None
                rd = road.project(Point(p0))
                for sgn in (-1.0, 1.0):
                    q = road.interpolate(rd + sgn * grid / 2.0)
                    if bands.covers(q) or bands.distance(q) <= snap / 2.0:
                        inward = sgn
                        break
                fam0 = fam_at(road.interpolate(rd + (inward or 0.0) * grid / 2.0))
                if inward is not None and fam0 is not None:
                    s = grid / 2.0
                    reach = 60.0
                    while s <= reach:
                        dd = rd + inward * s
                        if dd <= 0.0 or dd >= road.length:
                            break
                        q = road.interpolate(dd)
                        if not bands.covers(q):
                            break
                        f1 = fam_at(q)
                        if f1 is not None and f1 != fam0:
                            z0 = level(fam0, q)
                            z1 = level(f1, q)
                            if z0 is not None and z1 is not None \
                                    and abs(z1 - z0) >= min_step:
                                ext = 1.25 * abs(z1 - z0) / cap + grid
                                d_in = max(0.0, min(road.length,
                                                    dd + inward * ext))
                                lo, hi = sorted((rd, d_in))
                                inner = substring(road, lo, hi)
                                if inner.length > 0.0:
                                    # the axis from the INNER end outward
                                    ic = list(inner.coords)
                                    if inward > 0:
                                        ic = ic[::-1]
                                    st = LineString(ic[:-1] + list(st.coords))
                                    p0 = ic[0]
                                    z_band = z1
                                    kind = "in-band pocket"
                            break
                        s += grid / 2.0
                if kind != "in-band pocket" and fam0 == "runway":
                    kind = "runway-end corner" if _past_runway_end(
                        cells, Point(p0)) else kind
                stretches.append(st)
                axes.append(st)
                zm.append(z_band)
                steps.append((p0, step, run))
                # the mouth box: the ribbon's first stand-off of run,
                # widened by the stand-off, is not cut out of the band
                cut = cutback + snap
                head = substring(st, 0.0, min(st.length, cut + grid / 5.0))
                back = LineString([
                    (2 * head.coords[0][0] - head.coords[-1][0],
                     2 * head.coords[0][1] - head.coords[-1][1]),
                    head.coords[0]]) if head.length > 0 else None
                # only the part BEHIND the mouth (inside the band it steps
                # from) is kept: ahead of it the band is cut back as along
                # the rest of the corridor
                if back is not None:
                    mouths.append(_mouth_box(back, half + cut, weld))
            if not stretches:
                continue
            # SQUARE caps: the ribbon starts INSIDE the band and the
            # difference hands back the band's own boundary as the mouth.
            # An in-band pocket corridor is cut out of the bands it crosses
            # (the ribbon is not differenced by them; the band cut-back
            # trims them instead).
            pocket = kind == "in-band pocket"
            ribbon = unary_union([s_.buffer(half, cap_style="flat" if pocket
                                            else "square", **_MITRE)
                                  for s_ in stretches])
            blk = blocked if not pocket else unary_union(
                [g for g in (paved, ground_cells, sea)
                 if g is not None and not g.is_empty])
            poly = ribbon.difference(blk)
            parts = [g for g in shapely.get_parts(poly)
                     if g.geom_type == "Polygon" and g.area >= 1.0
                     and any(g.distance(Point(p0)) <= half for p0, _s, _r in steps)]
            strip = unary_union([
                _bank_strip(ax, zb, dem, cap, half, cutback + snap, bank_slope, grid)
                for ax, zb in zip(axes, zm)])
            for g in parts:
                p0, step, run = min(steps, key=lambda t_: g.distance(Point(t_[0])))
                out.append(RoadExit(f"{ROAD_EXIT_PREFIX}{k}", g,
                                    (float(p0[0]), float(p0[1])), step,
                                    sum(r for _p, _s, r in steps),
                                    tuple(axes), tuple(zm), kind,
                                    tuple(mouths), road, strip))
                k += 1
    # two exits of one road may overlap at a short gap: the first keeps it
    kept: list[RoadExit] = []
    taken = Polygon()
    for r in out:
        g = r.polygon.difference(taken)
        if g.is_empty or g.area < 1.0:
            continue
        if g.geom_type != "Polygon":
            g = max(shapely.get_parts(g), key=lambda x: x.area)
        kept.append(_dc.replace(r, polygon=g))
        taken = unary_union([taken, g])
    return kept


#: §1.2 / §1.4 report: every mouth candidate of the last derivation —
#: ``((x, y), step_m, drape_excess_m, minted)``.
ROAD_EXIT_CANDIDATES: list = []


def _drape_excess(line, z0: float, dem, cap: float, grid: float):
    """§1.2 v2 (29ae (iii)): the road DRAPED from the band level ``z0`` at
    the mouth onto the DEM along ``line`` — ``e = max_s (|DEM(s) - z0| -
    cap s)`` over ``0 < s <= s_reach`` (the first station where the cap
    ramp meets the DEM, or the line's end).  Returns ``(e, s_reach)``;
    ``s_reach`` is ``None`` when the ramp never meets the DEM."""
    e = -math.inf
    s = grid / 2.0
    while s <= line.length:
        pt = line.interpolate(s)
        x = abs(float(dem.z(pt.x, pt.y)) - z0) - cap * s
        e = max(e, x)
        if x <= 0.0:
            return e, s
        s += grid / 2.0
    return e, None


def _profile_rise(line, s: float, z0: float, dem, cap: float) -> float:
    """``z_prof(s) - z0`` on the centreline (§1.3 (3)): the DEM's offset
    from the band level clamped to the cap ramp."""
    pt = line.interpolate(s)
    d = float(dem.z(pt.x, pt.y)) - z0
    return max(-cap * s, min(cap * s, d))


def _bank_strip(axis, z0: float, dem, cap: float, half: float, cut: float,
                bank_slope: float, grid: float):
    """§1.1 (4) v2: the variable-width strip ``half + w(s)``, ``w(s) =
    max(cut, |z_prof(s) - z_band| / bank_slope)``, one polygon tapered
    station by station (no jogs: both sides are offset polylines)."""
    if axis is None or axis.length <= 0.0:
        return Polygon()
    n = max(2, int(math.ceil(axis.length / grid)) + 1)
    left, right = [], []
    for i in range(n):
        s = axis.length * i / (n - 1)
        p = axis.interpolate(s)
        q0 = axis.interpolate(max(0.0, s - 0.5))
        q1 = axis.interpolate(min(axis.length, s + 0.5))
        dx, dy = q1.x - q0.x, q1.y - q0.y
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        w = half + max(cut, abs(_profile_rise(axis, s, z0, dem, cap)) / bank_slope)
        left.append((p.x + nx * w, p.y + ny * w))
        right.append((p.x - nx * w, p.y - ny * w))
    poly = Polygon(left + right[::-1])
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly


def _mouth_box(back, width: float, chamfer: float):
    """§1.1 (4) v2: the part of the band BEHIND a mouth that is not cut
    back — ``width`` either side of the axis at the mouth, widening by
    ``chamfer`` (``identity.weld_spacing_m``) over its depth, so the band
    ring's jog from the shared mouth edge to the cut-back line is one
    chamfered segment >= ``chamfer`` (attempt 1: a 0.50 m jog, exactly the
    census hairline spacing)."""
    (x0, y0), (x1, y1) = back.coords[0], back.coords[-1]   # back end -> mouth
    L = math.hypot(x1 - x0, y1 - y0) or 1.0
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    depth = L + chamfer
    bx, by = x1 - ux * depth, y1 - uy * depth
    wb = width + chamfer
    return Polygon([(x1 + nx * width, y1 + ny * width),
                    (bx + nx * wb, by + ny * wb),
                    (bx - nx * wb, by - ny * wb),
                    (x1 - nx * width, y1 - ny * width)])


def _past_runway_end(cells, pt) -> bool:
    """A mouth beyond a runway's end quadrant (the report's class only)."""
    for c in cells or ():
        if c.role not in RUNWAY_FAMILY or c.side != "airside":
            continue
        p = Polygon(c.ring, c.holes)
        r = p.minimum_rotated_rectangle
        xs = list(r.exterior.coords)[:4]
        import math as _m
        e0 = (xs[1][0] - xs[0][0], xs[1][1] - xs[0][1])
        e1 = (xs[2][0] - xs[1][0], xs[2][1] - xs[1][1])
        ax = e0 if _m.hypot(*e0) >= _m.hypot(*e1) else e1
        L = _m.hypot(*ax)
        if L <= 0:
            continue
        ux, uy = ax[0] / L, ax[1] / L
        cx, cy = r.centroid.x, r.centroid.y
        s = (pt.x - cx) * ux + (pt.y - cy) * uy
        if abs(s) > L / 2.0 and p.distance(pt) < 400.0:
            return True
    return False


def _band_level(paved, zones: list, p0, dem, law: Law, grid: float) -> float:
    """The pre-solve estimate of the band's level where a road leaves it
    (``road_exit_corridors``): the lowest DEM on the airside pavement edge
    within the nearest pavement distance plus the band's zone-2 half-width,
    less the band's mandatory minimum fall over the nearest distance."""
    from shapely.geometry import Point
    pt = Point(p0)
    dist = paved.distance(pt)
    near = min(zones, key=lambda z: z.polygon.distance(pt))
    hw = zone2_half_width_m(law, "runway" if near.family == "runway" else "junction",
                            near.code_number, near.code_letter) or 0.0
    edge = paved.boundary.intersection(pt.buffer(dist + hw + grid))
    zs = []
    for ln in getattr(edge, "geoms", [edge]):
        if ln.is_empty or ln.length <= 0.0:
            continue
        n = max(2, int(ln.length / grid) + 1)
        for i in range(n):
            q = ln.interpolate(i / (n - 1), normalized=True)
            zs.append(float(dem.z(q.x, q.y)))
    if not zs:
        from shapely.ops import nearest_points
        q = nearest_points(paved, pt)[0]
        zs = [float(dem.z(q.x, q.y))]
    return min(zs) - ag_min_down(law, zones, p0) * dist


def ag_min_down(law: Law, zones: list, p0) -> float:
    """The mandatory minimum fall of the band the exit ``p0`` leaves (the
    runway family's where a runway zone holds it, else the taxi's)."""
    from shapely.geometry import Point
    pt = Point(p0)
    near = min(zones, key=lambda z: z.polygon.distance(pt))
    t = law.tables.zones.adjacent_ground
    fam = t.runway if near.family == "runway" else t.taxi
    return float(fam.band_min_down)
