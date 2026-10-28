"""Adjacent-ground ZONE regions (RULINGS 2026-08-01 zone law; memory
``adjacent-ground-zone-law``; ``law/zones.toml``).

Around every runway-family and taxi-family face: zone 1 (the lip,
``lip_width_m`` out from the pavement edge) and zone 2 (the graded band
out to ``zone_edge_offset_m`` from the edge for the class); beyond zone 2 the DEM is
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

import collections as _collections
import dataclasses as _dc
import threading as _threading
import weakref as _weakref

import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import split as _split
from shapely.ops import unary_union

from ..classify.pad_touch import is_rim_strip
from ..classify.roles import TAXI_FAMILY, Cell, is_runway_shoulder
from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline
from ..geom.rotated_rect import long_axis, rotated_rectangle
from ..law import Law
from ..law.tables import (
    input_quantum_m,
    runway_end_profile,
    runway_safety_area_length_m,
    runway_zone_edge_offset_m,
    snap_margin_m,
    zone2_half_width_m,
    zone_edge_offset_m,
)
from ..model.planar import is_gap_apron_ref, is_late_ref
from .road_yield import BandYield, road_cut_pieces
from .shore import SHORE_WALL_TAGS, ShoreVerdict, shore_contact, shore_declarations, shore_verdict
from .terrain_edge import EdgeReport, clip_to_terrain_edge

__all__ = ["ZoneRegion", "zone_regions", "shore_region", "shore_declarations",
           "SHORE_WALL_TAGS", "shore_wedge_m", "runway_end_breaks"]

RUNWAY_FAMILY = ("runway", "runway_crossing")
_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def shore_region(cells: tuple[Cell, ...], dem, sea_only: bool = True):
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
    sea beside the field — and the regions are then what they were.

    ``sea_only=False`` reads EVERY water body of the same witness
    (``dem.water_geometry``), minus the same land: THE ZONE CUT of owner
    RULINGS 2026-10-20k — runway end areas, safety areas and the adjacent
    graded ground stop at ANY water's edge (KOTH's estuary is an inland
    body to the coastline partition).  The cut AND the shore decision
    (quay / natural bank / wedge) read it; the sea-only reading above is
    the structures' (``planar/structures``, §34 (12) (2)).  This
    supersedes the inland carve-out argued above for the ZONES: an inland
    body's edge is decided as the coast's is, at that body's own level
    (``planar/shore.water_level_beside``)."""
    # THE SEA WITNESS ONLY.  A sampler that answers "is this wet" but not
    # "is this the SEA" claims NO shore here: no witness, no trim.
    fn = getattr(dem, "sea_geometry", None)
    if not callable(fn) or not cells:
        return None
    # every water body where the witness names them; a sampler that
    # knows only the sea cuts at the sea
    every = getattr(dem, "water_geometry", None)
    if not sea_only and callable(every):
        fn = every
    tiles = getattr(dem, "water_tile_keys", None)
    key = (id(dem), sea_only, tiles(), tuple((c.ring, c.holes) for c in cells)) \
        if callable(tiles) else None     # only a frame that names its water reads
    if key is not None:
        with _SHORE_LOCK:
            hit = _SHORE_MEMO.get(key)
        if hit is not None and hit[0]() is dem:
            return hit[1]
    land = unary_union([Polygon(c.ring, c.holes) for c in cells])
    try:
        w = fn(land.buffer(500.0).bounds)
    except Exception:                                   # pragma: no cover
        return None
    if w is not None and not w.is_empty:
        w = w.difference(land)
    w = None if w is None or w.is_empty else w
    if key is None:
        return w
    try:
        ref = _weakref.ref(dem)
    except TypeError:                                   # pragma: no cover
        return w
    with _SHORE_LOCK:
        _SHORE_MEMO[key] = (ref, w)
        while len(_SHORE_MEMO) > _SHORE_MEMO_SIZE:
            _SHORE_MEMO.popitem(last=False)
    return w


#: THE SHORE REGION IS READ ONCE PER CELL SET (issue #412): the structure
#: pass calls :func:`shore_region` on EVERY one of its overlap passes
#: (``unframed_ramp.MAX_OVERLAP_PASSES``) and twice per planar stage
#: (``planar/build.channels_after_basins`` and the build proper) with the
#: same cells, and each call buffers the whole airport union by 500 m —
#: HECA's ribbon-free planar stage spent 42.5 s of 85 in it.  The answer
#: is a pure function of the cells' rings and the DEM's sea, so it is
#: kept for the last few cell sets; the DEM is held WEAKLY (a production
#: frame is hundreds of MB) and a dead or different DEM is a miss.
#: Shapely geometries are immutable, so callers share the one answer.
_SHORE_MEMO: "_collections.OrderedDict" = _collections.OrderedDict()
_SHORE_MEMO_SIZE = 4
_SHORE_LOCK = _threading.Lock()


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
    #: THE RUNWAY whose band this region is (RULINGS 2026-10-15c (1), lane
    #: rwyzone15c phase 4): the band is built per runway, so its membership
    #: join is that runway's edges — never another runway of the same code
    #: (``constraints/zones``).  ``None`` for a taxi region.
    runway_ref: str | None = None


def _unclaimed(cell: Cell) -> bool:
    """A cell the zone CLAIM does not read (§59 the gap apron, §63 the rim
    strip): it stands outside every band by construction, and a band it
    does reach yields its ground to it alone."""
    return is_gap_apron_ref(getattr(cell, "ref", "")) or is_rim_strip(cell)


def runway_end_breaks(cells: tuple[Cell, ...], law: Law,
                      runways: tuple = ()) -> list[LineString]:
    """THE BREAKLINE AT THE STRIP'S END (owner RULINGS 2026-10-12q (1) (a);
    ``tables.runway_end_profile``): per runway, the line across the end
    band perpendicular to the runway's long axis at ``EndProfile.break_m``
    beyond each pavement end — where the strip's own cap hands over to the
    end skirt's.  The end band was ONE plane from the end edge to the
    outer ring, and one plane cannot fall at 1.75 % for 60 m and 5 % for
    the rest (measured CYCG 15: −2.77 % over the whole 74 m, #620).  The
    axis is the runway's own cells' rectangle (§40 (4): a shoulder minted
    no region and mints no break; ``geom.long_axis``), the runway grouped
    by ``ref`` so a crossing's cut does not shorten it.  Empty where the
    ruleset states no first segment."""
    by_ref: dict[str, list] = {}
    cls: dict[str, tuple[int | None, str | None]] = {}
    for c in cells:
        if c.role not in RUNWAY_FAMILY or len(c.ring) < 3 or is_runway_shoulder(c):
            continue
        if c.role != "runway":
            continue
        by_ref.setdefault(c.ref, []).append(Polygon(c.ring, c.holes))
        cls.setdefault(c.ref, (c.code_number, c.code_letter))
    # the runway's INSTRUMENT STATUS (RULINGS 2026-10-15k; #811 0 / 1 / 2):
    # the strip's end length and half-width are read by it
    # (``overlay._runway_records``' last slot)
    ins_of = {r[0]: int(r[6]) for r in runways if len(r) >= 7}
    out: list[LineString] = []
    for ref, polys in by_ref.items():
        cn, cl = cls[ref]
        ins = ins_of.get(ref, 0)
        prof = runway_end_profile(law, cn, cl, ins)
        brk = prof.break_m
        if not brk:
            continue
        u = unary_union(polys)
        if u.is_empty or u.area <= 0.0:
            continue
        ab = long_axis(rotated_rectangle(u.convex_hull))
        if ab is None:
            continue
        a, b = ab
        L = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        px, py = -uy, ux
        hw = (zone2_half_width_m(law, "runway", cn, cl, ins) or 0.0) + u.area / L + 1.0
        for s0 in (-brk, L + brk):
            cx, cy = a[0] + ux * s0, a[1] + uy * s0
            out.append(LineString([(cx - px * hw, cy - py * hw), (cx + px * hw, cy + py * hw)]))
    return out


def _break_pieces(g: Polygon, breaks: list[LineString]) -> list[Polygon]:
    """``g`` cut by every break line that crosses it (polygon parts only)."""
    parts = [g]
    for ln in breaks:
        nxt: list = []
        for part in parts:
            if not part.intersects(ln):
                nxt.append(part)
                continue
            nxt.extend(p for p in shapely.get_parts(_split(part, ln))
                       if p.geom_type == "Polygon" and not p.is_empty)
        parts = nxt
    return parts


def zone_regions(cells: tuple[Cell, ...], law: Law,
                 keepouts: tuple[tuple, ...] = (), dem=None, roads=(),
                 edge_report: EdgeReport | None = None,
                 declared: tuple = (),
                 shore_wedge_m: float | None = None,
                 pack_walls: tuple = (), runways: tuple = (),
                 carriageways: tuple = (),
                 yields: list | None = None,
                 rsa_carriageways: tuple | None = None,
                 plates: tuple = ()) -> list[ZoneRegion]:
    """Zone 1 / zone 2 regions around the airside runway and taxi faces,
    minus every cell (pavement, pads, roads), minus senior strips and
    minus the ``keepouts`` (structure footprints: the zones stop at the
    tunnel wall, M4).

    With a ``dem`` (and the tile's OSM road centrelines) every region is
    also CLIPPED BY THE TERRAIN EDGE at this single derivation site
    (``planar/terrain_edge.py``; owner RULINGS 2026-09-10b/10c, spec §19): the
    adjacent ground ends at a rim road or a crest.  Without one — every
    synthetic fixture — the regions are what they were.

    ``carriageways`` (``planar/road_yield.road_carriageways``: centreline,
    half-width) are the mapped roads; the bands yield the carriageway of
    every road running BESIDE them (owner 2026-10-19, #944), and zone 2
    yields the carriageway of every road running THROUGH it (owner RULINGS
    2026-10-20c, 39); each zone-2 yield is appended to ``yields`` as a
    :class:`~.road_yield.BandYield`.  A RUNWAY band's zone 2 yields only
    the ``rsa_carriageways`` (``road_yield.rsa_carriageways``; ``None``
    reads ``carriageways``): an airport service road through the safety
    area sits at grade on it (owner RULINGS 2026-10-28p (1), #1201).

    ``plates`` (``Airport.walled_plates``, #1201): a runway-end walled
    plate's footprint is cut from every band (owner RULINGS 2026-10-27t:
    the safety area ends at the plate's inner edge, also where that edge is
    oblique), and the plate's own step is never a terrain-edge crest."""
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
    # A MAPPED-ROAD RIBBON (``classify/roles.mint_osm_ribbons``, #100) gets
    # NO stand-off: inside a band the road grades WITH the zone (13ar) and
    # the kerb it shares with the band is the BAND's (spec-author 30e (4),
    # 29r — ``PlanarMap.band_kerb_vertices``), so the band and the ribbon
    # are welded, never terraced across a 0.6 m strip.  Where the ribbon
    # LEAVES the band it climbs from that shared kerb at the road cap
    # (29y / 29r); a 1206 route and every other groundside cell keep the
    # cut-back.
    # §59 A GAP-APRON CELL IS NOT IN THE CLAIM (owner RULINGS 2026-10-08g:
    # "with the runway held at zero").  ``gap_mint`` cuts every piece out of
    # the bands' envelope with the stand-off, so the cell reaches no band and
    # its absence changes no zone — while its PRESENCE in this union re-nodes
    # the claim along every runway edge (measured HECA: a 1.3 m2 hairline,
    # 1,689 m x 0.8 mm, passed the 1 m2 part floor beside 05C/23C and gave
    # the runway 143 new vertices 1.6 km from the nearest piece).  The bands
    # are the standing cells' by construction; a cell that does reach one is
    # subtracted from that band alone, below.
    # SPEC §63 (M1): A RIM STRIP IS NOT IN THE CLAIM EITHER, for the same
    # measured reason.  The strip is the knife's own stand-off beside a pad,
    # which the knifed BODY's buffer and the pad already claim; one more
    # polygon in this union re-noded it (HECA, lane weldverify: a 1.31 m2
    # hairline, 1,689 m x 0.8 mm, beside 05C/23C again — 163 new runway
    # vertices, 11 runway nodes moved up to 0.07 m, from 27 strips at pads).
    # With the strips out the claim is the knifed cells', as it was.
    # THE CLAIM IS DETERMINISTIC (issue #486, #637): every overlay below is
    # FIXED-PRECISION and the claim's members are unioned in a canonical
    # order (``geom/fixed_overlay``), so a band near a point is a function
    # of the cells near that point.  The floating cascade it replaces
    # re-noded every runway edge whenever any cell was added (HECA: an 11-
    # cell apron change minted a 1.31 m2, 0.8 mm hairline beside 05C/23C,
    # 1.6 km away; KCLT: a tunnel 940 m away moved 18 zone rings in their
    # last bits and flipped a runway vertex 227.08 / 227.13 m).
    gap_aprons = [Polygon(c.ring, c.holes) for c in cells if _unclaimed(c)]
    gap_apron_u = canonical_union(gap_aprons) if gap_aprons else None
    everything = canonical_union(
        [Polygon(c.ring, c.holes).buffer(cut, **_MITRE)
         if c.side == "groundside" and not is_late_ref(getattr(c, "ref", ""))
         else Polygon(c.ring, c.holes) for c in cells
         if not _unclaimed(c)]
        + [Polygon(k).buffer(cut, **_MITRE) for k in keepouts]) if cells else Polygon()
    # A PART NARROWER THAN TWO INPUT QUANTA is below the resolution every
    # source coordinate was snapped to (§46 (4)): an overlay residue, never
    # ground — dropped here, at the one derivation site (RULINGS 2026-08-30l)
    hairline_m = 2.0 * input_quantum_m(law)
    lip = ag.lip_width_m
    groups: dict[tuple[str, int | None, str | None], list[Polygon]] = {}
    letters: dict[str, str | None] = {}
    rw_polys: dict[str, list] = {}
    rw_class: dict[str, tuple] = {}
    for c in cells:
        # §40 (4) (owner RULINGS 2026-09-14s): a SHOULDER manufactures no
        # zone band — it inherits its host runway's, which it lies inside
        # (`rules.toml`'s own words, measured at VHHH: 587,849 m2 of
        # zone-2 band the shoulders minted).  The spec's §40 (4) MEASURED
        # table is the census of every RUNWAY_FAMILY reader.
        if c.role in RUNWAY_FAMILY and not is_runway_shoulder(c):
            # ONE RUNWAY, ONE BAND (owner RULINGS 2026-10-15c (1)/(2)): the
            # band is measured from the runway's own CENTRELINE and runs the
            # RSA length past its own ends, so it is built per runway ref
            # (:func:`_runway_band`); the third slot carries the ref
            # a CROSSING piece (ref ``a+b``) is pavement of BOTH runways: it
            # joins each one's group — alone it was a group of its own whose
            # fallback axis (a few metres square) swung the RSA rectangle
            # out 300 m across the field (measured CYXY replay: a code-4
            # zone2 vertex 300-500 m from every runway, 34 m over its DEM)
            for ref in str(c.ref).split("+"):
                rw_polys.setdefault(ref, []).append(Polygon(c.ring, c.holes))
                if c.role == "runway" or ref not in rw_class:
                    rw_class[ref] = (c.code_number, c.code_letter)
            continue
        elif c.role in TAXI_FAMILY:
            key = ("taxi", None, c.code_letter)
        else:
            continue
        groups.setdefault(key, []).append(Polygon(c.ring, c.holes))
    # each runway's group under ITS OWN class (a crossing piece carries the
    # senior's code)
    for ref, polys in rw_polys.items():
        cn, cl = rw_class[ref]
        groups[("runway", cn, _RUNWAY_KEY + ref)] = polys
        letters[ref] = cl

    status_of = {r[0]: int(r[6]) for r in runways if len(r) >= 7}

    def letter_of(key: tuple[str, int | None, str | None]) -> str | None:
        fam, _cn, cl = key
        return letters.get(cl[len(_RUNWAY_KEY):]) if fam == "runway" else cl

    def rank(key: tuple[str, int | None, str | None]) -> tuple[int, float, str]:
        fam, cn, cl = key
        # wider first: the runway by its centreline figure, a taxi group by
        # its reach from the edge (the buffer it is drawn with below)
        hw = (zone2_half_width_m(law, "runway", cn, letter_of(key),
                                 status_of.get(cl[len(_RUNWAY_KEY):], 0)) if fam == "runway"
              else zone_edge_offset_m(law, "junction", cn, cl)) or 0.0
        return (0 if fam == "runway" else 1, -hw, str(cl))

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
    # owner RULINGS 2026-10-20k: EVERY water body's edge (the sea's is
    # part of it) — the cut and the shore decision below read one region
    water = shore_region(cells, dem, sea_only=False)
    claimed = everything
    out: list[ZoneRegion] = []
    counters: dict[tuple, int] = {}
    breaks = runway_end_breaks(cells, law, runways)
    bands: dict[tuple, tuple] = {}
    for key in sorted(groups, key=rank):
        fam, cn, cl = key
        u = unary_union(groups[key])
        if fam == "runway":
            band = _runway_band(u, cl[len(_RUNWAY_KEY):], cn, letter_of(key), law,
                                runways)
            if band is None:
                continue
            inner, outer = band
        else:
            # THE TAXIWAY STRIP FROM THE CENTRELINE (RULINGS 2026-10-15l (1),
            # audit row 3; spec regulation-conformance §2.A A-1): the graded
            # portion (ICAO Annex 14 §3.11.4) / TSA (FAA AC §4.5.3) is a
            # centreline half-width, so the union is buffered by its reach
            # past the letter's pavement edge — THE derivation site
            hw = zone_edge_offset_m(law, "junction", cn, cl)
            if hw is None or hw <= 0:
                continue
            inner = u.buffer(min(lip, hw), **_MITRE)
            outer = u.buffer(hw, **_MITRE)
        bands[key] = (u, inner, outer)
    # THE ROAD BESIDE THE BAND TRUMPS THE BAND (owner 2026-10-19, #944;
    # ``planar/road_yield``): a road whose centreline runs OUTSIDE every
    # band envelope (and off the airside pavement) is the core's groundside
    # road — the bands yield its carriageway plus the groundside stand-off.
    # A road INSIDE a band is ribboned and grades with the zone (13ar/29r).
    # A ROAD THROUGH ZONE 2 IS CUT OUT OF IT (owner RULINGS 2026-10-20c, 39,
    # #951): the same cut with the zone-1 LIPS as the envelope, so every
    # carriageway whose centreline runs outside the lips leaves zone 2 its
    # half-width plus the stand-off — the road follows its own ground and
    # the band stops at the road's edge.  Zone 1 keeps the outer cut (13ar:
    # the road there is welded to the lip).
    beside = through = through_rsa = None
    if carriageways and bands:
        airside = [Polygon(c.ring, c.holes) for c in cells
                   if c.side != "groundside" and len(c.ring) >= 3]
        envelope = unary_union([b[2] for b in bands.values()] + airside)
        pieces = road_cut_pieces(carriageways, envelope, cut)
        beside = unary_union([g for _a, _h, g in pieces]) if pieces else None
        if yields is not None:
            yields.extend(BandYield(g, a, float(h)) for a, h, g in pieces)
        through = road_cut_pieces(carriageways,
                                  unary_union([b[1] for b in bands.values()] + airside),
                                  cut, extent=envelope, cap_style="square")
        through_rsa = through if rsa_carriageways is None else road_cut_pieces(
            rsa_carriageways,
            unary_union([b[1] for b in bands.values()] + airside),
            cut, extent=envelope, cap_style="square")
    plate_u = _plate_union(plates)
    plate_near = (None if plate_u is None else
                  plate_u.buffer(float(law.tables.emit.design.edge_probe_m), **_MITRE))
    for key, (u, inner, outer) in bands.items():
        fam, cn, cl = key
        z1 = fixed_difference(inner, claimed)
        z2 = fixed_difference(fixed_difference(outer, inner), claimed)
        z1 = fixed_difference(z1, beside)
        z2 = fixed_difference(z2, beside)
        mine_through = through_rsa if fam == "runway" else through
        if mine_through:
            z2 = _yield_zone2(z2, outer, key, mine_through, yields)
        if plate_u is not None:
            # 27t (#1201): the band ends at the plate — no stand-off
            z1 = fixed_difference(z1, plate_u)
            z2 = fixed_difference(z2, plate_u)
        cls = f"{cn}" if fam == "runway" else f"{cl or 'default'}"
        for zone, geom, seed in ((1, z1, u), (2, z2, inner)):
            if gap_apron_u is not None and geom.intersects(gap_apron_u):
                geom = fixed_difference(geom, gap_apron_u)
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
                                        edge_report, not_crest=plate_near)
            geom = clip.kept
            parts = shapely.get_parts(geom) if geom.geom_type != "Polygon" else [geom]
            # THE BREAK AT THE STRIP'S END (``runway_end_breaks``): the
            # zone-2 end band is cut AFTER every trim and shore decision,
            # so each piece inherits its part's verdict and edge
            if breaks and fam == "runway" and zone == 2:
                parts = [p for g0 in parts if g0.geom_type == "Polygon"
                         for p in _break_pieces(g0, breaks)]
            k = counters.get((fam, cls, zone), 0)
            for g in parts:
                if g.geom_type != "Polygon" or g.is_empty or g.area < 1.0 \
                        or is_hairline(g, hairline_m):
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
                                      g, zone, fam, cn, None if fam == "runway" else cl,
                                      clip.kind if mine else "none", mine, quay,
                                      natural, wedge, verdict,
                                      cl[len(_RUNWAY_KEY):] if fam == "runway" else None))
                k += 1
            counters[(fam, cls, zone)] = k
        claimed = canonical_union([claimed, outer])
    return out


def _plate_union(plates: tuple):
    """The union of the walled plates' footprints, or ``None``."""
    polys = []
    for p in plates or ():
        g = Polygon(getattr(p, "footprint", ()) or ())
        g = g if g.is_valid else g.buffer(0.0)
        if not g.is_empty and g.area > 0.0:
            polys.append(g)
    return canonical_union(polys) if polys else None


def _yield_zone2(z2, outer, key, through, yields: list | None):
    """``z2`` less every through-road cut that reaches it, each cut clipped
    to ``outer`` (this band's zone-2 extent) and recorded in ``yields``."""
    fam, cn, cl = key
    rwy = cl[len(_RUNWAY_KEY):] if fam == "runway" else None
    mine = []
    for axis, half, g in through:
        if not g.intersects(z2):
            continue
        piece = g.intersection(outer)
        if piece.is_empty or piece.area <= 0.0:
            continue
        mine.append(g)
        # a road BESIDE the band (its axis outside it) is #944's cut, already
        # made: only an axis through this band's zone 2 is its yield
        if yields is not None and axis.intersects(outer):
            yields.append(BandYield(piece, axis, float(half), fam, cn,
                                    None if fam == "runway" else cl, rwy, True))
    return fixed_difference(z2, unary_union(mine)) if mine else z2


#: The runway group key's third slot: the runway REF behind this prefix (a
#: taxi key carries its letter there).
_RUNWAY_KEY = "@"


def _runway_band(u, ref: str, cn: int | None, cl: str | None, law: Law,
                 runways: tuple) -> "tuple[Polygon, Polygon] | None":
    """``(zone-1 outer, zone-2 outer)`` of ONE runway (owner RULINGS
    2026-10-15c (1) "From the centreline", (2) "Full safety-area length"):

    * zone 1 is the lip, ``lip_width_m`` from the pavement edge;
    * zone 2 reaches ``tables.runway_zone_edge_offset_m`` from the edge
      (the half-width measured from the CENTRELINE) and, beyond each end,
      the RSA rectangle — the centreline ± the half-width from the runway
      END (``RunwayEnd.xy``, the blast pad inside) out
      ``tables.runway_safety_area_length_m``.  KBJC 12L: 152.4 m wide,
      304.8 m past the threshold (the band was 183 m wide, ending 76.2 m
      past the pad's far edge).

    ``runways`` are ``(ref, end_a_xy, end_b_xy, width_m[, len_a, len_b])``
    (the end areas' lengths, ``airport/end_area``); a ref without
    one (synthetic fixtures) reads the pavement's own rectangle — the slab
    ends and its width."""
    rec = next((r for r in runways if r[0] == ref), None)
    # the runway's instrument status (RULINGS 2026-10-15k; #811)
    ins = int(rec[6]) if rec is not None and len(rec) >= 7 else 0
    hw = zone2_half_width_m(law, "runway", cn, cl, ins)
    if hw is None or hw <= 0 or u.is_empty:
        return None
    lip = float(law.tables.zones.adjacent_ground.lip_width_m)
    if rec is not None:
        a, b, width = rec[1], rec[2], float(rec[3])
    else:
        ab = long_axis(rotated_rectangle(u.convex_hull))
        if ab is None:
            return None
        a, b = ab
        L0 = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        width = u.area / L0 if L0 > 0 else 0.0
    off = runway_zone_edge_offset_m(law, cn, cl, 0.5 * width, ins)
    L = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
    inner = u.buffer(min(lip, off), **_MITRE)
    outer = u.buffer(off, **_MITRE)
    if L > 0.0:
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        # each end's own length: the RSA, or the top of a drop (15g (C);
        # ``airport/end_area``, carried in the record)
        rsa = runway_safety_area_length_m(law, cn, cl, ins)
        la, lb = (float(rec[4]), float(rec[5])) \
            if rec is not None and len(rec) >= 6 and rec[4] is not None else (rsa, rsa)
        axis = LineString([(a[0] - ux * la, a[1] - uy * la),
                           (b[0] + ux * lb, b[1] + uy * lb)])
        outer = unary_union([outer, axis.buffer(hw, cap_style="flat")])
    return inner, outer


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
