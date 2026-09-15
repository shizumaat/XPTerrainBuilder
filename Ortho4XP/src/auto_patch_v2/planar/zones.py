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
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..classify.roles import TAXI_FAMILY, Cell, is_runway_shoulder
from ..law import Law
from ..law.tables import snap_margin_m, zone2_half_width_m
from .terrain_edge import EdgeReport, clip_to_terrain_edge

__all__ = ["ZoneRegion", "zone_regions", "shore_region"]

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

    ``None`` where there is no witness (every synthetic fixture) or no
    water beside the field — and the regions are then what they were."""
    fn = getattr(dem, "water_geometry", None)
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


def zone_regions(cells: tuple[Cell, ...], law: Law,
                 keepouts: tuple[tuple, ...] = (), dem=None, roads=(),
                 edge_report: EdgeReport | None = None) -> list[ZoneRegion]:
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
                # §37 (11) (2): a part that REACHES the coastline is a QUAY
                quay = bool(water is not None
                            and g.distance(water) <= snap_margin_m(law))
                out.append(ZoneRegion(f"adjacent_ground:{fam}:{cls}:zone{zone}#{k}",
                                      g, zone, fam, cn, cl,
                                      clip.kind if mine else "none", mine, quay))
                k += 1
        claimed = unary_union([claimed, outer])
    return out
