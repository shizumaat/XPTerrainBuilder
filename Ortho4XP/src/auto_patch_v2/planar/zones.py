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
           "SHORE_WALL_TAGS", "shore_wedge_m"]

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
                 pack_walls: tuple = ()) -> list[ZoneRegion]:
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
        + [Polygon(k).buffer(cut, **_MITRE) for k in keepouts]) if cells else Polygon()
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
    """One road exit corridor: where a mapped road LEAVES an adjacent-
    ground band, the stretch of its own corridor the road cap needs to
    climb (or fall) from the band's level to the terrain."""

    ref: str
    polygon: Polygon
    exit_xy: tuple[float, float]
    step_m: float           # DEM at the exit minus the band-level estimate
    length_m: float         # the corridor's run along the road


def road_exit_corridors(zones: list, cells: tuple[Cell, ...], law: Law,
                        dem, roads=(), water=None) -> list[RoadExit]:
    """RULINGS 2026-09-29r (#100 cause 2; resolves 2026-08-12b vs 13ar by
    WHERE the road is): INSIDE an adjacent-ground band the road grades
    WITH the zone (13ar — this function mints nothing there).  Where the
    road LEAVES the band its own corridor — the road ribbon's half-width
    (``terrain_edge.road_half_width_m``: lane width + the 0.6 m
    ``groundside_cutback_m``) — is a ROAD, not zone-3 ground: it climbs
    from the band edge at <= the road cap (``service_road.longitudinal``,
    8 %) until the cap meets the DEM, and its sides terrace to the raw
    DEM.  No ground outside the corridor is minted or moved.

    Derived HERE, at the zone derivation site (owner 2026-08-30l): the
    corridor is the road piece OUTSIDE every band and cell, starting at
    the band boundary, as long as the cap needs (``step / cap``, the first
    station where ``|DEM(s) - z_band| <= cap * s``), minus the bands,
    the cells and the water.  The band level at the exit is ESTIMATED
    pre-solve (the DEM at the nearest pavement point less the band's
    mandatory minimum fall over the distance); the solve owns the real
    level — the corridor's length only has to cover the cap's reach.
    A step under ``emit.cockpit.visual_m`` (the step a pilot sees) needs
    no corridor."""
    if dem is None or not roads or not zones:
        return []
    from .terrain_edge import road_half_width_m
    from ..law.tables import role_cap
    ag = law.tables.zones.adjacent_ground
    cap = float(role_cap(law, "service_road").longitudinal)
    half = road_half_width_m(law)
    cutback = float(ag.groundside_cutback_m)
    grid = float(law.tables.emit.design.edge_grid_m)
    snap = snap_margin_m(law)
    # THE GATE IS THE BAND-EXIT STEP A PILOT SEES (``cockpit.visual_m``),
    # never a terrain drop: NLWF's road -3 west exit steps 2.4 m where the
    # pre-solve estimate read 1.8 m, under §19's 2 m ``edge_min_drop_m``
    min_step = float(law.tables.emit.cockpit.visual_m)
    bands = unary_union([z.polygon for z in zones])
    paved = unary_union([Polygon(c.ring, c.holes) for c in cells
                         if c.side == "airside"]) if cells else Polygon()
    inside = unary_union([bands, paved])
    blocked = inside if water is None else unary_union([inside, water])
    from shapely.geometry import Point
    from shapely.ops import nearest_points, substring
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
            da = bands.distance(Point(a))
            db = bands.distance(Point(b))
            ends = [c for c, d in ((a, da), (b, db)) if d <= snap]
            stretches = []
            steps = []
            for p0 in ends:
                line = piece if p0 == a else LineString(piece.coords[::-1])
                # the band level at the exit: the LOWEST pavement DEM
                # within the band's reach of it (a pavement cut into a
                # hill — NLWF's apron, 9.9 m off its DEM — is not the
                # band's level), less the band's mandatory minimum fall
                z_band = _band_level(paved, zones, p0, dem, law, grid)
                step = float(dem.z(p0[0], p0[1])) - z_band
                if abs(step) < min_step:
                    continue
                need = None
                s = grid / 2.0
                while s <= line.length:
                    pt = line.interpolate(s)
                    if abs(float(dem.z(pt.x, pt.y)) - z_band) <= cap * s:
                        need = s
                        break
                    s += grid / 2.0
                # the solve owns the band's real level: a quarter of slack
                # on the cap's reach so the corridor still meets the DEM
                run = min(line.length,
                          (1.25 * need if need is not None else line.length) + grid)
                stretches.append(substring(line, 0.0, run))
                steps.append((p0, step, run))
            if not stretches:
                continue
            # ONE corridor per road piece: two exits of one piece (a road
            # leaving a band over a hill and coming back) ramp as one road
            # SQUARE caps: the ribbon starts INSIDE the band and the
            # difference hands back the band's own boundary as the seam
            # (a flat cap across the band edge left a 0.5 m sliver and an
            # unwelded 3.8 m step at NLWF)
            ribbon = unary_union([st.buffer(half, cap_style="square", **_MITRE)
                                  for st in stretches]).difference(blocked)
            # 29u (ii) THE STAND-OFF: the corridor stands off every band
            # it does NOT exit by the 0.6 m cutback and WELDS only at the
            # MOUTH of the band it exits — a corridor running ALONGSIDE the
            # band it leaves shared the band's edge vertices over its whole
            # length and the band-follower rows pinned it to the band
            # (measured NLWF road -3 west exit: 4.3 m on a 6.1–7.6 m DEM,
            # 24.8 % where it met the DEM).  The mouth is the ribbon's
            # cross-section at the exit (a disc of the ribbon half-width).
            mouths = unary_union([Point(p0).buffer(half) for p0, _s, _r in steps])
            standoff = bands.buffer(cutback, **_MITRE).difference(mouths)
            poly = ribbon.difference(standoff)
            poly = _one_ribbon(poly, ribbon, mouths, stretches, half)
            parts = [g for g in shapely.get_parts(poly)
                     if g.geom_type == "Polygon" and g.area >= 1.0
                     and any(g.distance(Point(p0)) <= half for p0, _s, _r in steps)]
            for g in parts:
                p0, step, run = min(steps, key=lambda t: g.distance(Point(t[0])))
                out.append(RoadExit(f"{ROAD_EXIT_PREFIX}{k}", g,
                                    (float(p0[0]), float(p0[1])), step,
                                    sum(r for _p, _s, r in steps)))
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


def _one_ribbon(poly, ribbon, mouths, stretches, half: float):
    """29u (ii) ONE CONTINUOUS RIBBON: the stand-off may sever the corridor,
    or notch it past its centreline, where the road passes a band
    mid-course (NLWF road -3 behind the terminal: an earlier arm's
    stand-off left pieces with a DEM gap between them, 62 %; this arm's
    first cut notched the course at s 2124, 55 %).  The pieces are re-joined along the road's own
    CENTRELINE — the ribbon narrowed to a thin core there, never the
    band's edge — so the corridor is one face from its mouth to its end;
    only a core that the stand-off still cuts (the road itself inside the
    cutback of a band) welds there, the least contact the ribbon allows."""
    core = unary_union([st.buffer(0.25 * half, cap_style="flat") for st in stretches])
    joined = unary_union([poly, core.intersection(ribbon)])
    return joined


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
