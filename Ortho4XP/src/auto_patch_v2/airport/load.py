"""``load(icao, inputs, law)`` — ONE :class:`Airport` in the local metric
frame from every input (M0 §4 step 1).  Every path is an argument
(``Inputs``); nothing is read from a cfg or the environment.

The frame origin is the airport reference point (apt.dat ``1302
datum_lat/lon``, else the runway-end mean) and the identity precision is
``law.emit.identity.coordinate_dp`` (memory ``canonical-identity-join``).
"""
from __future__ import annotations

import dataclasses as _dc
import logging
import math
import os
import sys as _sys
import typing as _t
import zlib

from ..law import Law
from ..law.reference_code import is_instrument, runway_code_letter, runway_code_number
from ..law.tables import identity_dp, input_quantum_m
from ..model.airport import (GAP_SHEET_PREFIX, Airport, Boundary, Building,
                             DsfObject, FacadeRead, GroundRoute, LinearFeature, OsmWay, Pavement,
                             Runway, RunwayEnd, Startup, Surface, TaxiEdge,
                             TaxiNode)
from ..model.frame import XY, Frame
from . import approach as _approach
from . import apt_dat as _apt
from . import borrow as _borrow
from . import cifp as _cifp
from . import end_pins as _end_pins
from . import imagery_read as _imagery
from . import junction_witness as _junction_witness
from . import runway_end_witness as _end_witness
from . import runway_refs as _refs
from . import dem as _dem
from . import dsf as _dsf
from . import dsf_write as _dw
from . import facade as _facade
from . import obj8 as _obj8
from . import object_pavement as _objpav
from . import osm as _osm
from . import pack as _pack
from . import riders as _riders

_log = logging.getLogger(__name__)

__all__ = ["Inputs", "LoadReport", "load", "load_with_report", "join_cifp",
           "normalise_surface", "read_apt"]

#: OSM tags that make a closed way a building footprint (v1
#: ``_extract_osm_terminals`` / ``_is_building_evidence_tags``).
BUILDING_AEROWAY_TAGS = frozenset(("terminal", "hangar", "tower"))


@_dc.dataclass(frozen=True)
class Inputs:
    """Where the inputs live — all read-only.  ``apt_dat_path`` /
    ``dsf_dump_path`` / ``footprint_cache_path`` override pack discovery
    (fixtures); ``elevation_root`` may be ``""`` to skip the DEM (then
    ``Airport.dem`` is a sampler over nothing and the planar build
    refuses at I7)."""

    xplane_root: str
    cifp_dir: str
    osm_root: str
    elevation_root: str
    mod_cache_root: str
    feather_m: float = 60.0
    radius_deg: float = 0.05
    apt_dat_path: str | None = None
    dsf_dump_path: str | None = None
    footprint_cache_path: str | None = None
    #: ``"production"`` (03j: the core's composed tile DEM the mesh drapes
    #: on, ``dem_production.py``) or ``"authored"`` (the ``.hgt`` + inset
    #: sampler, fixtures and probes).
    dem_frame: str = "production"
    #: ``--allow-degraded-dem``: accept a cold production frame KNOWINGLY.
    allow_degraded_dem: bool = False
    #: PRE-COMPOSED production tile rasters, keyed ``(lat, lon)`` — the
    #: core ``O4_DEM_Utils.DEM`` objects a HOSTING tile build has already
    #: prepared (the tile driver's ``tile.dem``, the very surface
    #: ``include_patches`` drapes on).  A seeded tile is REUSED, never
    #: re-composed: the tile build's DEM prep is the frame of record, and
    #: composing it a second time in a worker is the class of drift the
    #: harness's warm-vs-cold refusals exist for.  Tiles a straddling
    #: airport touches beyond the seeds compose lazily as before.
    production_dem_tiles: _t.Any = None
    #: The caller RUNS INSIDE THE CORE (its data root already set, its
    #: ``src``/``Providers`` on ``sys.path``, its cwd whatever the engine
    #: process uses): the production loader must not assert the CLI's
    #: cwd/engine-root contract nor re-point the data root.  The corpus
    #: check (``elevation_root`` IS the core's ``Elevation_dir``) stays.
    core_hosted: bool = False
    #: THE CORE'S ROAD CLAMP KNOBS (RULINGS 2026-09-04t-4): the tile's
    #: ``road_grade_limit`` / ``lane_width`` — a hosted build passes the
    #: tile's own values, the CLI the global cfg's; ``None`` = the law
    #: defaults (``common.roles.service_road.longitudinal`` /
    #: ``emit.road_profile.lane_width_m``, the core's own cfg defaults).
    road_grade_limit: float | None = None
    lane_width_m: float | None = None
    #: THE PACK WALK THE TILE BUILD'S PARENT ALREADY TOOK (spec
    #: ``pack-read-once-fast-spec.md`` §B.4, issue #27): ``{pack root:
    #: partition_cache.pristine_stamps(root)}``, so a child never walks a
    #: pack its parent walked; ``None`` = walk here (standalone builds).
    pack_pristine: _t.Any = None
    #: THE BUILD'S AIRPORT IMAGERY (#1359; owner RULINGS 2026-10-26q / 26y):
    #: the orthophotos this build textures the airport with, as files — the
    #: tile build hands the airport's own textures it fetched FIRST (the
    #: patch waits for them, 26y); ``()`` with ``imagery_scenery_dir`` set
    #: reads the LIVE textures of the built ortho tiles under that folder
    #: (a standalone build, which has no imagery step of its own); neither
    #: set = no imagery: every imagery vote abstains.
    imagery_paths: tuple[str, ...] = ()
    imagery_scenery_dir: str = ""


class PackDumpStale(RuntimeError):
    """The pack's tile DSF has no fresh text dump (refused below).  The
    class and its two attributes are what ``O4_Tile_Failures`` reads to
    give the user a message (issue #562) — the wording is free to change."""

    failure_code = "pack_dump_stale"

    def __init__(self, pack: str, message: str):
        super().__init__(message)
        self.failure_params = {"pack": pack}


@_dc.dataclass
class LoadReport:
    """What the loader saw and did NOT turn into a graded input."""

    apt_dat_path: str = ""
    pack_name: str = ""
    #: §44 (4) (owner RULINGS 2026-09-15f): THE PAVEMENT BORROW —
    #: ``{"pack", "borrowed_from", "coverage", "custom_pavements",
    #: "borrowed_pavements", "borrowed_boundary", "reason",
    #: "coverage_max"}``.  ``borrowed_from`` is ``None`` when the pack's
    #: own pavement stood.
    pavement_source: dict = _dc.field(default_factory=dict)
    #: THE ONE §44 log line (``""`` when nothing was borrowed)
    pavement_borrow_line: str = ""
    helipads: tuple[str, ...] = ()
    cifp_path: str | None = None
    cifp_missing_ends: tuple[str, ...] = ()
    #: #119: one line per end joined (or REFUSED as ambiguous) by its
    #: threshold coordinate after its designator matched nothing
    cifp_coordinate_joins: tuple[str, ...] = ()
    #: THE RUNWAY-END PIN RULE (``end_pins.verify``; RULINGS 2026-10-25a):
    #: one record per runway end, the loud lines, and the cross-check
    #: sources whose cache held this airport
    end_pins: list = _dc.field(default_factory=list)
    end_pin_lines: tuple[str, ...] = ()
    end_pin_crosscheck: tuple[str, ...] = ()
    #: THE TERRAIN WITNESS (#1359): the textures it read (``source``,
    #: ``textures``) and one Q1 vote record per CIFP runway end, with the
    #: loud lines of every CIFP record the layout and the imagery outvoted
    #: (RULINGS 2026-10-26v)
    imagery: dict = _dc.field(default_factory=dict)
    witness_votes: list = _dc.field(default_factory=list)
    witness_lines: tuple[str, ...] = ()
    #: RULINGS 2026-10-27n: one record per pavement joining a runway — the
    #: share of its contact the imagery reads as pavement (``junction_witness``)
    paved_joins: list = _dc.field(default_factory=list)
    buildings_by_source: dict[str, int] = _dc.field(default_factory=dict)
    dsf_dump_path: str | None = None
    #: the pack's tile DSF is newer than every cached text dump (refused)
    dsf_dump_stale: bool = False
    dsf_pavements: int = 0
    #: DSF pavement pages refused as another airport's (beyond the admission gate)
    dsf_pavements_far: int = 0
    #: spec §60: draped ``.pol`` pages admitted by their own ``SURFACE``
    #: as GAP SHEETS (never a pavement source) — pages and their m2
    dsf_gap_sheets: int = 0
    dsf_gap_sheet_m2: float = 0.0
    #: §42 (3) (RULINGS 2026-09-13cv): the pack's DRAPED OBJ8 ground
    #: polygons admitted as source polygons — bodies, m2, per resource,
    #: and every draped resource refused with its reason
    object_pavements: _objpav.ObjectPavementReport = _dc.field(
        default_factory=_objpav.ObjectPavementReport)
    footprint_cache_path: str | None = None
    unresolved_objects: int = 0
    objects_resolved: int = 0
    #: placements whose geometry was read from ``<obj>.anchor_bak`` — the
    #: pack's AUTHORED state, restored for the read (RULINGS 04f-1)
    objects_restored_for_read: int = 0
    library_index_path: str | None = None
    osm_sources: tuple[str, ...] = ()
    #: ``osm.feed_witness`` of the feeds this load could read — the patch
    #: freshness gate's OSM input (``o4_osm``, #880); "" without a root
    osm_witness: str = ""
    #: §25 (RULINGS 2026-09-11aq item B): relations read, outer ways given
    #: the relation's tags, rings stitched, unclosable outers, inners dropped
    osm_relations: str = ""
    #: road feeds carrying NO ``o4_tag_schema`` at all — grandfathered
    #: (``airport_small_roads``'s writer has never stamped one), NAMED so
    #: the gap is not invisible.  Lane ``v2othhdet``: that writer,
    #: ``O4_Vector_Map._airport_auto_roads_layer``, recycles its cache on
    #: existence alone, so the 2026-09-15 whitelist bump never
    #: invalidated it — OTHH's is from 2026-07-27 and carries none of
    #: ``layer`` / ``cutting`` / ``covered`` / ``embankment``.
    osm_road_feeds_untagged: tuple[str, ...] = ()
    #: road feeds carrying a SUPERSEDED ``o4_tag_schema`` — a refusal in
    #: the production frame, a named degradation in a frozen one
    osm_road_feeds_stale: tuple[str, ...] = ()
    #: §37 (11) (7) (issue #72): the shore-structure feed files READ (the
    #: 3x3 neighbourhood) — empty means no tile around this airport has
    #: been filled (``--refresh-data shore``) and every coast here reads
    #: NATURAL for want of a declaration, not because none exists
    osm_shore_feeds: tuple[str, ...] = ()
    dem_provenance: dict[str, str] = _dc.field(default_factory=dict)
    notes: list[str] = _dc.field(default_factory=list)
    #: The flat-site verdict record (``airport/flat_site.record``; set by
    #: the pipeline once the detector ran — ``report.load.flat_site``).
    flat_site: dict | None = None
    #: The flat-pack witness record (``airport/flat_pack.record``; set by
    #: the pipeline once the pack partition is read — ``report.load.flat_pack``).
    flat_pack: dict | None = None
    #: the runway chord fit's coverage (RULINGS 2026-09-08d (1); ``constraints/runway_chord.py``)
    runway_chord: dict | None = None
    #: the taxi chains' trend fit coverage (owner RULINGS 2026-09-10v (1);
    #: ``constraints/taxi_trend.py``, spec §8.6)
    taxi_trend: dict | None = None
    #: the apron bodies' 2-D trend fit coverage (owner RULINGS
    #: 2026-09-10ar; ``constraints/apron_trend.py``, spec §8.7)
    apron_trend: dict | None = None
    #: the groundside roads' RAMP from their airside contacts to the DEM
    #: (owner RULINGS 2026-09-13j item 5, ruled 13aj;
    #: ``constraints/road_ramp.py``, spec §37 (6))
    road_ramp: dict | None = None
    #: THE EAT RAMP REACH (owner RULINGS 2026-09-13aa; spec §36 (5),
    #: ``constraints/eat.eat_reach_plan``): per pinned foot the drop, the
    #: taxi cap, the derived reach and the loop it has either side; the
    #: trend rows withdrawn over it; and every loop TOO SHORT to ramp
    #: lawfully, with the grade it is forced to.
    eat_reach: dict | None = None


def normalise_surface(code: int) -> Surface:
    """XP12 surface variants fold onto the 1100-spec codes: 20-38 are
    asphalt pages, 50-57 concrete pages; anything unknown is ASPHALT
    (a pavement is graded whatever its texture)."""
    if 20 <= code <= 38:
        return Surface.ASPHALT
    if 50 <= code <= 57:
        return Surface.CONCRETE
    try:
        return Surface(code)
    except ValueError:
        return Surface.ASPHALT


def load(icao: str, inputs: Inputs, law: Law | None = None) -> Airport:
    """The airport, loaded once."""
    return load_with_report(icao, inputs, law)[0]


def load_with_report(icao: str, inputs: Inputs, law: Law | None = None
                     ) -> tuple[Airport, LoadReport]:
    """``load`` plus the report of what was seen and not graded."""
    icao = icao.upper()
    law = law or Law.for_airport(icao)
    rep = LoadReport()

    # ── apt.dat ────────────────────────────────────────────────────
    sel, block, apt, bres, frame = read_apt(icao, inputs.xplane_root, law,
                                            inputs.apt_dat_path)
    rep.apt_dat_path, rep.pack_name = sel.apt_dat_path, sel.name
    rep.helipads = tuple(h.name for h in apt.helipads)
    n_own_pav = bres.custom_pavements
    rep.pavement_source = bres.record(sel.name)
    rep.pavement_borrow_line = bres.line(icao)
    lat0, lon0 = frame.origin
    to_xy = _vector_to_xy(frame)
    tile = (int(math.floor(lat0)), int(math.floor(lon0)))

    # ── runways + CIFP ─────────────────────────────────────────────
    cifp_path = os.path.join(inputs.cifp_dir, f"{icao}.dat") if inputs.cifp_dir else ""
    cifp = _cifp.read_cifp_runways(cifp_path) if os.path.isfile(cifp_path) else {}
    rep.cifp_path = cifp_path if cifp else None
    runways: list[Runway] = []
    tol = float(law.tables.emit.identity.cifp_threshold_join_m)
    recs, missing, joins = join_cifp(icao, apt.runways, cifp, to_xy, tol)
    approaches = (_cifp.read_cifp_approach_runways(cifp_path) if cifp else {})
    # #1358 (2): an end whose CIFP record lies beyond it on a SHIFTED runway
    # is pinned on the two thresholds' CIFP line (``end_pins.shifted_ends``)
    shifted, shift_lines = _end_pins.shifted_ends(icao, apt.runways, cifp, recs, to_xy, tol)
    joins = [*joins, *shift_lines]
    for _log_line in joins:
        _log.info(_log_line)
    for i, rw in enumerate(apt.runways):
        ends = []
        for k, (desig, lat, lon, disp, over) in enumerate(rw.ends):
            rec = recs[(i, k)]
            # THE APPROACH WITNESS PER END (owner RULINGS 2026-10-15m (2),
            # 15n; ``approach.end_approach``): the CIFP class of the record
            # the join found for this end (designator, or #119's threshold
            # fallback), strengthened by apt.dat precision markings
            cls, cat = _approach.end_approach(
                approaches.get(rec.designator) if rec is not None else None,
                *(getattr(rw, f, (0, 0))[k]
                  for f in ("markings", "approach_lights", "tdz_lights")))
            # #1358: a joined CIFP record pins at ITS OWN landing threshold,
            # projected onto the axis (``end_pins.cifp_station``)
            other = rw.ends[1 - k]
            along = (_end_pins.cifp_station(to_xy(lon, lat), to_xy(other[2], other[1]),
                                            to_xy(rec.lon, rec.lat))
                     if rec is not None else None)
            if (i, k) in shifted:
                z_line, far = shifted[(i, k)]
                ends.append(RunwayEnd(desig, to_xy(lon, lat), (lat, lon), disp, over,
                                      z_line, far.source, cls, cat, pin_along_m=None,
                                      pin_source=_end_pins.SHIFTED))
                continue
            ends.append(RunwayEnd(desig, to_xy(lon, lat), (lat, lon), disp,
                                  over, rec.elevation_m if rec else None,
                                  rec.source if rec else "", cls, cat,
                                  pin_along_m=along,
                                  pin_source="cifp" if rec is not None else ""))
        # INSTRUMENT: either end has an approach (``Runway.instrument``, the
        # status the RESA and the strip's end length are read by)
        instrument = any(is_instrument(e.approach) for e in ends)
        r = Runway(f"{ends[0].name}/{ends[1].name}", rw.width_m,
                   normalise_surface(rw.surface), (ends[0], ends[1]), None,
                   runway_code_letter(law, rw.width_m), instrument,
                   _apt.shoulder_width_m(rw.shoulder))
        # THE ONE CODE-NUMBER / LETTER STAMP (regulation-conformance spec
        # §3.1/§3.2): every reader takes these, the census from the sidecar
        runways.append(_dc.replace(r, code_number=runway_code_number(law, r.length_m)))
        _log.info("%s %s: code %s%s, ends %s", icao, r.id, runways[-1].code_number,
                  r.code_letter, " ".join(
                      f"{e.name}={e.approach}{'+CatII/III' if e.cat_ii_iii else ''}"
                      for e in ends))
    rep.cifp_missing_ends = tuple(missing)
    rep.cifp_coordinate_joins = tuple(joins)

    # ── pavements / lines / boundaries / network / startups ────────
    pavements = tuple(
        Pavement(f"pav{p.index}", normalise_surface(p.surface),
                 _ring(p.rings[0], to_xy),
                 tuple(_ring(h, to_xy) for h in p.rings[1:]), p.description,
                 _borrow.BORROWED_SOURCE if i >= n_own_pav else "")
        for i, p in enumerate(apt.pavements))
    lines = tuple(
        LinearFeature(f"line{ln.index}", ln.line_type,
                      tuple(to_xy(lo, la) for lo, la in ln.points), ln.closed)
        for ln in apt.lines)
    boundaries = tuple(
        Boundary(f"boundary{b.index}", _ring(b.rings[0], to_xy),
                 tuple(_ring(h, to_xy) for h in b.rings[1:]),
                 _borrow.BORROWED_SOURCE if bres.borrowed_boundary else "")
        for b in apt.boundaries)
    taxi_nodes = {n.id: TaxiNode(n.id, to_xy(n.lon, n.lat), n.usage)
                  for n in apt.taxi_nodes.values()}
    taxi_edges = tuple(
        TaxiEdge(e.a, e.b, e.name, e.one_way, e.kind == "runway",
                 e.kind.split("_", 1)[1] if e.kind.startswith("taxiway_") else None)
        for e in apt.taxi_edges if e.a in taxi_nodes and e.b in taxi_nodes)
    routes = tuple(GroundRoute(e.a, e.b, e.name, e.one_way)
                   for e in apt.truck_edges
                   if e.a in taxi_nodes and e.b in taxi_nodes)
    startups = tuple(Startup(s.name, to_xy(s.lon, s.lat), s.heading_deg, s.kind)
                     for s in apt.startups)

    # ── OSM ────────────────────────────────────────────────────────
    osm_ways: list[OsmWay] = []
    buildings: list[Building] = []
    sources: list[str] = []
    osm_relations = _osm.RelationReport()
    feed_schemas: dict[str, tuple[tuple[str, str | None], ...]] = {}
    if inputs.osm_root:
        for feed in _osm.FEEDS:
            doc = _osm.load_feed(inputs.osm_root, feed, lat0, lon0,
                                 inputs.radius_deg)
            sources.extend(doc.sources)
            feed_schemas[feed] = doc.tag_schemas
            osm_relations = osm_relations.merge(doc.relations)
            for w in doc.ways:
                pts = tuple(to_xy(lo, la) for la, lo in w.points)
                osm_ways.append(OsmWay(_osm_id(w.id), feed, pts, w.closed, w.tags))
                if w.closed and _is_building(w.tags):
                    buildings.append(Building(
                        f"osm:{w.id}", pts[:-1], (), "osm",
                        _float_or_none(w.tags.get("height")),
                        _int_or_none(w.tags.get("building:levels"))))
    rep.osm_sources = tuple(sources)
    if inputs.osm_root:
        rep.osm_witness = _osm.feed_witness(inputs.osm_root, lat0, lon0)
    rep.osm_shore_feeds = tuple(p for p, _s in feed_schemas.get(
        _osm.SHORE_FEED, ()))
    if inputs.osm_root and not rep.osm_shore_feeds:
        rep.notes.append(
            "no shore-structure feed around this airport (issue #72): every "
            "coast reads NATURAL for want of a quay/seawall declaration — "
            "fill it with build_airport.py --refresh-data shore")
    rep.osm_relations = osm_relations.line()
    # A ROAD FEED WRITTEN UNDER A SUPERSEDED TAG WHITELIST IS REFUSED BY
    # NAME (lane ``v2othhdet``; the ``dsf_dump_stale`` refusal below is
    # the precedent).  THE MEASUREMENT: main ``f6bd825d`` (owner 15i,
    # §45 (9)) added ``layer`` / ``cutting`` / ``covered`` / ``embankment``
    # to ``ROADS_TAGS_OF_INTEREST`` and bumped ``ROAD_CACHE_TAG_SCHEMA``
    # 2026-07-16 -> 2026-09-15, so every cache written before it carries
    # NEITHER those tags nor the ways they qualify.  Lane ``v2objcut``'s
    # two OTHH dry replays at one tree, 11:39 and 11:45 on 2026-09-15,
    # straddled the orchestrator's ``OTHH --refresh-data osm_layers``
    # (ledger ``OTHH_20260915T113518``) and read 8 bores against 16 —
    # ``corridors 7 / tunnels 42`` against ``9 / 44``, with ``tunnel west
    # 1.obj`` and ``tunnel west 3.obj`` refused "the mouth is
    # undetermined: no bore at either end" on the stale arm.  That was
    # reported as a READER nondeterminism (RULINGS 2026-09-15ar) and
    # invalidated a lane's byte-identity claim.  ``build_airport.py``
    # refuses a stale road layer (RULINGS 2026-09-15u); a DRY
    # ``planar --stage structures`` replay had no such gate, so the
    # refusal stands HERE, where every reader's input is loaded.
    stale: list[str] = []
    untagged: list[str] = []
    for feed in _osm.ROAD_FEEDS:
        for path, schema in feed_schemas.get(feed, ()):
            if schema is None:
                untagged.append(f"{path} ({feed})")
            elif schema != _osm.ROAD_CACHE_TAG_SCHEMA:
                stale.append(f"{path} (o4_tag_schema {schema})")
    rep.osm_road_feeds_untagged = tuple(untagged)
    rep.osm_road_feeds_stale = tuple(sorted(stale))
    # THE FROZEN FRAMES ARE EXEMPT, and only they.  ``dem_frame
    # "authored"`` is a pinned corpus a caller chose deliberately (the
    # checked-in ``tests/auto_patch_v2/fixtures/CYXY`` reads its own
    # 2026-07-16 feed and MUST keep reading it — a twin's frame is not
    # the shared corpus), and ``--allow-degraded-dem`` is the standing,
    # recorded "measure in the worse frame KNOWINGLY" override that
    # authorises no write (CLAUDE.md).  Either way the stale feeds are
    # NAMED on the report, never silent.
    # AN UNTAGGED FEED IS AS STALE AS A STALE-STAMPED ONE (owner RULINGS
    # 2026-09-17t, chip D; scout ``hecachannel``).  A cache carrying NO
    # ``o4_tag_schema`` at all predates the stamp, so it predates every
    # whitelist bump the stamp exists to detect — it is the WEAKER
    # evidence of the same fact, not an exemption.  Measured at HECA:
    # ``+30+031_airport_small_roads.osm.bz2`` (2026-07-27) carries no
    # stamp, so §45 (1) (d)'s ``layer`` / ``cutting`` / ``covered`` /
    # ``embankment`` gate — the whole point of the 2026-09-15 bump — was
    # structurally unavailable at HECA while the run reported nothing
    # but a record on ``osm_road_feeds_untagged``.  Same refusal, same
    # exemptions (a frozen ``authored`` frame, ``--allow-degraded-dem``),
    # same remedy: the LEDGERED ``--refresh-data osm_layers``, which is
    # the owner's act — a reader NEVER re-bakes a feed.
    suspect = sorted(stale) + [f"{u} — NO o4_tag_schema stamp at all"
                               for u in sorted(untagged)]
    if suspect and inputs.dem_frame == "production" and not inputs.allow_degraded_dem:
        raise RuntimeError(
            f"{icao}: {len(suspect)} cached road feed(s) were written under a "
            f"SUPERSEDED tag whitelist (or none) — the reading would be missing the "
            f"tags the current one keeps (ROADS_TAGS_OF_INTEREST / "
            f"ROAD_CACHE_TAG_SCHEMA {_osm.ROAD_CACHE_TAG_SCHEMA}), and the "
            f"structure readers would silently see fewer bores (measured at "
            f"OTHH: 8 against 16, corridors 7 against 9 — RULINGS "
            f"2026-09-15ar, attributed by lane v2othhdet; an UNSTAMPED feed is "
            f"the same fact on weaker evidence — RULINGS 2026-09-17t, HECA's "
            f"airport_small_roads): "
            + "; ".join(suspect)
            + ". Refresh them explicitly: build_airport.py <ICAO> "
              "--refresh-data osm_layers (never a build side effect).")
    rep.buildings_by_source["osm"] = len(buildings)

    # ── DSF: facades, object footprints, placements ────────────────
    dsf_objects: list[DsfObject] = []
    # THE READ FRAME (RULINGS 2026-09-11m): the PRISTINE DSF — the
    # ``.dsf.anchor_bak`` the object stage moved aside, else the live
    # file.  A plan derived from a WRITTEN DSF names the bodies the last
    # write minted (LEMD: 3,934 placements against a 3,021-row pristine
    # dump) and the write half refuses it.
    pack_dsf = _dw.pristine_dsf_path(_dsf.dsf_path_in_pack(sel.root, *tile))
    dump_path = inputs.dsf_dump_path or _pack_dump(icao, inputs, rep, sel.name, sel.root, tile)
    rep.dsf_dump_path = dump_path
    # #1630 (owner Q284 (a)): an OBJECT PACK replaces Global Airports'
    # objects only — the pavement pages X-Plane still draws are read from
    # the pack that serves them (``PackSelection.pages_root``)
    split = sel.pages_root != sel.root
    pages_path = (_pack_dump(icao, inputs, rep, sel.pages_name, sel.pages_root, tile)
                  if split else dump_path)
    n_fac = n_obj = n_agp = n_lot = 0
    # THE ADMISSION GATE (RULINGS 2026-09-06a): the tile DSF carries EVERY
    # airport's pavement pages; a page is this airport's only within
    # ``identity.dsf_pavement_admission_m`` of its own apt.dat extent.
    own_extent = _own_extent(runways, pavements, boundaries,
                             law.tables.emit.identity.dsf_pavement_admission_m)
    # THE LIBRARY INDEX, read-only (M4b): ``lib/...`` placements resolve
    # through v1's cached merged index; absent = unresolved.  Read BEFORE
    # the polygons: the pavement gate asks an abbreviation-named ``.pol``
    # (``conc_3.pol``) for its own SURFACE declaration (RULINGS
    # 2026-10-04d (2)), and the facade reader resolves each ``.fac`` and
    # its attached objects through it (§52).
    have = dump_path and os.path.isfile(dump_path)
    have_pages = split and pages_path and os.path.isfile(pages_path)
    index = None
    if have or have_pages:
        lib_path = _obj8.library_index_path(inputs.mod_cache_root, inputs.xplane_root) \
            if inputs.mod_cache_root and inputs.xplane_root else ""
        index = _obj8.read_library_index(lib_path)
        rep.library_index_path = lib_path if index is not None else None
    polys = _DsfPolygons(to_xy, own_extent)
    if have_pages:
        polys.read(pages_path, sel.pages_root, index, pages=True, rest=False)
    dump = (polys.read(dump_path, sel.root, index, pages=not split, rest=True)
            if have else None)
    buildings.extend(polys.buildings)
    dsf_pavements, pol_sheets = polys.pavements, polys.sheets
    n_fac, n_lot, n_far = polys.n_fac, polys.n_lot, polys.n_far
    if dump is not None:
        for i, pl in enumerate(dump.placements):
            if not pl.def_path.lower().endswith((".obj", ".agp")):
                continue
            if abs(pl.lat - lat0) > inputs.radius_deg or \
                    abs(pl.lon - lon0) > inputs.radius_deg:
                continue
            resolved = _obj8.resolve_resource(pl.def_path, sel.root, index)
            if resolved is None:
                rep.unresolved_objects += 1
            else:
                rep.objects_resolved += 1
                if law.tables.structures.rebake.restore_before_read:
                    # RESTORE BEFORE READ (04f-1): the authored file, never
                    # a previous bake — ``airport/pack.py``
                    resolved, restored = _pack.authored_source(resolved,
                                                               sel.root)
                    if restored:
                        rep.objects_restored_for_read += 1
            # the AGL offset, or the MSL elevation (``kind`` says which;
            # the tunnel-object floor law reads an MSL seat as absolute)
            agl = float(pl.elevation) if pl.kind in ("OBJECT_AGL", "OBJECT_MSL") \
                and pl.elevation is not None else 0.0
            # hardness / deck top / below-grade solids are read by the
            # structure pass from ``resolved_path`` (``airport/obj8.py``)
            dsf_objects.append(DsfObject(
                f"dsf:obj{i}", pl.def_path, to_xy(pl.lon, pl.lat),
                pl.heading_deg, None, False, None, agl, resolved, pl.kind))
            # ── .agp point-placed HANGARS are buildings (issue #263) ──
            # v1 ``dsf_reader.read_dsf_buildings``'s second source
            # (``AGP_BUILDINGS``, user 2026-06-17): a stock-library hangar
            # ``.agp`` is ONE placement whose footprint is the file's own
            # TILE / CROP_POLY about its ANCHOR_PT.  v2 read every ``.agp``
            # as a RIDER (spec §1 (1): "a placement the plan holds no
            # geometry for") and never as a footprint, so CYXY's
            # ``Med_Blue_Hangar.agp`` (``hangar_40x26_3_lb.agp``, 46 x 26 m)
            # got no pad.  Admitted like the ``.fac`` hangars: by def path
            # (``dsf.agp_building_role``), source ``dsf:agp:hangar``,
            # ``[buildings] sources`` gates it in ``classify/evidence``.
            _agp_role = _dsf.agp_building_role(pl.def_path)
            if _agp_role is not None and resolved is not None:
                _agp_ring = _riders.agp_footprint_xy(
                    resolved, dsf_objects[-1].xy, pl.heading_deg)
                if _agp_ring is not None and len(_agp_ring) >= 3:
                    buildings.append(Building(
                        f"dsf:agp{i}", _agp_ring, (), f"dsf:agp:{_agp_role}",
                        None, None, dsf_objects[-1]))
                    n_agp += 1
    rep.buildings_by_source["dsf:agp"] = n_agp
    rep.dsf_pavements = len(dsf_pavements)
    rep.dsf_pavements_far = n_far
    # issue #713: the sidecar the pack refresh writes for the PRISTINE DSF
    # (``engine_v2.fresh_object_footprints``) — named, as v1 names it, by
    # that file's stem: ``+30+031`` before the object stage first writes
    # the pack, ``+30+031.dsf`` (the ``.anchor_bak``'s) after
    cache_path = inputs.footprint_cache_path or (
        os.path.join(_dsf.mod_cache_dir(inputs.mod_cache_root, sel.name),
                     _dsf.footprint_cache_name(pack_dsf))
        if inputs.mod_cache_root else None)
    if cache_path and os.path.isfile(cache_path):
        rep.footprint_cache_path = cache_path
        for i, (ring, kind) in enumerate(_dsf.read_footprint_cache(cache_path)):
            buildings.append(Building(f"dsf:object{i}", _ring(ring, to_xy), (),
                                      f"dsf:object:{kind}", None, None))
            n_obj += 1
    rep.buildings_by_source["dsf:fac"] = n_fac
    rep.buildings_by_source["dsf:lot"] = n_lot
    rep.buildings_by_source["dsf:object"] = n_obj

    # ── §42 OBJECT-BASED PAVEMENT (RULINGS 2026-09-13cv) ───────────────
    # The pack's DRAPED OBJ8 ground polygons, per disjoint body, as source
    # polygons beside the ``.pol`` pages: ``airport/object_pavement.py``
    # holds the identification law and the measurement behind it.  They
    # are read AFTER the object footprints because the pads win where the
    # two overlap (§42 (1)), and admitted with a ``dsf:`` id so classify's
    # draped-page gates (``classify/evidence._dsf_pavements``: inside the
    # boundary buffer, the apt.dat overlay drop, the area floor) judge
    # them exactly as they judge a ``.pol`` page — §42 (2): no privileged
    # role, and where a body meets a mapped page the mapped page's
    # evidence governs.
    pads = [b for b in buildings if b.source.startswith("dsf:object")]
    pad_union = None
    if pads:
        from shapely.ops import unary_union as _uu
        parts = [_shape_of(b.outer) for b in pads if len(b.outer) >= 3]
        pad_union = _uu(parts) if parts else None
    op_bodies, rep.object_pavements = _objpav.read_object_pavements(
        [_objpav.Placement(o.id, o.path, o.resolved_path or "", o.xy,
                           o.heading_deg)
         for o in dsf_objects if o.resolved_path],
        law, pad_union)
    # 04o (a): a GAP SHEET's bodies never join the sources; the others keep
    # the numbering they had (a gap body takes no ``objpav`` index)
    gap_sheets: list[Pavement] = []
    k = 0
    for body in op_bodies:
        if body.gap_only:
            pid, into = f"{GAP_SHEET_PREFIX}{len(gap_sheets)}", gap_sheets
        else:
            pid = (f"{_objpav.HARD_PLANE_PREFIX}{k}" if body.hard_plane
                   else f"dsf:objpav{k}")
            into, k = dsf_pavements, k + 1
        into.append(Pavement(
            pid, normalise_surface(_dsf.pavement_surface_code(body.resource)),
            tuple((float(x), float(y)) for x, y in body.polygon.exterior.coords[:-1]),
            tuple(tuple((float(x), float(y)) for x, y in r.coords[:-1])
                  for r in body.polygon.interiors),
            body.resource))
    # §60: the ``.pol`` sheets follow the object sheets, in dump order
    for sheet in pol_sheets:
        gap_sheets.append(_dc.replace(
            sheet, id=f"{GAP_SHEET_PREFIX}{len(gap_sheets)}"))
    rep.dsf_gap_sheets = len(pol_sheets)
    rep.dsf_gap_sheet_m2 = float(sum(_sheet_area(s) for s in pol_sheets))
    pavements = pavements + tuple(dsf_pavements)
    # ── §44 (2) THE SCENERY STAGE of the borrow (#1160, RULINGS 2026-10-20al
    # (1)): the pack's own draped pavement — its ``.pol`` pages and §42
    # bodies, never a gap sheet (20bb) — counts toward the coverage; at or
    # above the key the borrow stage 1 decided is WITHDRAWN here, the one
    # place the scenery exists (``borrow.yield_to_scenery``).
    if bres.borrowed:
        bres = _borrow.yield_to_scenery(
            bres,
            [(p.outer, p.holes) for p in pavements
             if p.source != _borrow.BORROWED_SOURCE],
            [(p.outer, p.holes) for p in pavements
             if p.source == _borrow.BORROWED_SOURCE],
            len(dsf_pavements))
        if not bres.borrowed:
            pavements = tuple(p for p in pavements
                              if p.source != _borrow.BORROWED_SOURCE)
            boundaries = tuple(b for b in boundaries
                               if b.source != _borrow.BORROWED_SOURCE)
            sel = _dc.replace(sel, borrow=bres.decision)
        rep.pavement_source = bres.record(sel.name)
        rep.pavement_borrow_line = bres.line(icao)

    # ── DEM ────────────────────────────────────────────────────────
    if inputs.elevation_root and inputs.dem_frame == "production":
        from . import dem_production as _prod
        dem = _prod.load_production_dem(frame, icao, inputs.elevation_root,
                                        inputs.osm_root, inputs.xplane_root,
                                        allow_degraded=inputs.allow_degraded_dem,
                                        seed_tiles=inputs.production_dem_tiles,
                                        core_hosted=inputs.core_hosted)
    elif inputs.elevation_root and inputs.dem_frame == "authored":
        dem = _dem.load_dem(frame, inputs.elevation_root, icao, inputs.feather_m)
    elif inputs.elevation_root:
        raise ValueError(f"dem_frame {inputs.dem_frame!r}: production | authored")
    else:
        dem = _dem.DemSampler(frame, "", None, 0.0, {"base": "absent"})
        rep.notes.append("no elevation_root: DEM samples are NaN")
    rep.dem_provenance = dict(dem.provenance)

    pack = _pack.signature(sel, block, *tile)
    airport = Airport(
        icao, apt.name, frame, apt.elevation_ft * _apt.FT_TO_M,
        tuple(runways), pavements, lines, taxi_nodes, taxi_edges, routes,
        boundaries, startups, tuple(osm_ways), tuple(buildings),
        tuple(dsf_objects), pack, dem, law.ruleset_key,
        gap_sheets=tuple(gap_sheets))
    # THE THRESHOLD WITNESS (#1359; owner RULINGS 2026-10-26q / 26v): a CIFP
    # record the installed layout and the imagery both outvote is DROPPED
    # for its end before the pin rule judges it — ONE site
    # (``runway_end_witness``); the end then takes 26e's lidar rule
    textures, rep.imagery = _airport_imagery(inputs, lat0, lon0)
    airport, rep.witness_votes, w_lines = _end_witness.witness_runway_ends(
        airport, cifp, to_xy, textures, law)
    rep.witness_lines = tuple(w_lines)
    for _line in w_lines:
        _log.warning(_line)
    # THE RUNWAY-END PIN RULE (owner RULINGS 2026-10-25a / 26a; #1342):
    # every CIFP end is verified on the DEM and the cached cross-check
    # sources before it becomes a pin — ONE site (``end_pins``)
    refs = _refs.lookup(icao, inputs.mod_cache_root,
                        law.tables.runway_ends.crosscheck_order)
    airport, rep.end_pins, end_lines = _end_pins.verify(airport, law, refs)
    rep.end_pin_lines = tuple(end_lines)
    rep.end_pin_crosscheck = tuple(src for src, _e in refs)
    for _line in end_lines:
        _log.warning(_line)
    # THE JUNCTION WITNESS (owner RULINGS 2026-10-27n / 28b): which pavements
    # the imagery shows PAVED where they meet a STEEP runway — it flattens
    # only there, and a refuted one is not joined to it.  After the end pins,
    # which say how steep each runway is (``junction_witness``; no imagery =
    # it abstains)
    airport, rep.paved_joins, j_lines = _junction_witness.witness_paved_joins(
        airport, textures, law)
    rep.witness_lines = rep.witness_lines + tuple(j_lines)
    for _line in j_lines:
        _log.warning(_line)
    return airport, rep


# ── helpers ──────────────────────────────────────────────────────────────

def _airport_imagery(inputs: Inputs, lat: float, lon: float
                     ) -> "tuple[_imagery.TextureSet | None, dict]":
    """The textures the witness reads (``Inputs.imagery_paths``, else the
    built tiles under ``imagery_scenery_dir``) and their published record."""
    paths = tuple(inputs.imagery_paths or ())
    source = "build"
    if not paths and inputs.imagery_scenery_dir:
        paths = _imagery.built_tile_paths(inputs.imagery_scenery_dir, lat, lon)
        source = "built tiles"
    if not paths:
        return None, {"source": "none", "textures": 0}
    ts = _imagery.TextureSet.from_files(paths, lat, lon)
    return ts, {"source": source, "textures": len(ts),
                "sources": sorted({r.source for r in ts.refs})}



def read_apt(icao: str, xplane_root: str, law: Law,
             apt_dat_path: str | None = None
             ) -> tuple[_t.Any, list[str], _t.Any, _t.Any, Frame]:
    """``(pack selection, the airport's apt.dat block, composed apt.dat
    airport, borrow result, frame)``
    — THE apt.dat read and THE airport frame, one site for the build's
    load and DEM prep's flat-site decision (issue #932), so the two read
    one pack and speak one frame.  ``apt_dat_path`` overrides pack
    discovery (fixtures)."""
    if apt_dat_path:
        sel = _pack.PackSelection(
            os.path.basename(os.path.dirname(os.path.dirname(apt_dat_path)))
            or "fixture", os.path.dirname(os.path.dirname(apt_dat_path)),
            apt_dat_path, False)
    else:
        sel = _pack.select_pack(xplane_root, icao, law)
        if sel is None:
            raise FileNotFoundError(f"{icao}: no apt.dat under {xplane_root}")
    block = _apt.read_airport_block(sel.apt_dat_path, icao)
    if not block:
        raise ValueError(f"{icao}: not in {sel.apt_dat_path}")
    apt = _apt.parse_airport_block(block)
    # THE FRAME IS THE CUSTOM BLOCK'S — taken BEFORE the borrow composes,
    # because §44 (2) is explicit that borrowing pavement does not move
    # the airport's reference point.
    lat0, lon0 = apt.reference_point()
    # ── §44 (3) THE PAVEMENT BORROW, composed HERE and nowhere else ────
    # (owner RULINGS 2026-09-15f; decided in ``pack.select_pack``).  The
    # Global Airports block's row-110 polygons are APPENDED to the pack's
    # own and its row-130 boundary taken only when the pack authored
    # none; everything else reads the composed block exactly as it reads
    # an authored one.
    bres = _borrow.compose(sel.borrow, icao, apt)
    frame = Frame(icao, (lat0, lon0), identity_dp(law),
                  input_quantum_m=_entry_quantum(law))
    return sel, block, bres.airport, bres, frame


def join_cifp(icao: str, runways: _t.Sequence[_t.Any],
              cifp: dict[str, "_cifp.CifpRunway"],
              to_xy: _t.Callable[[float, float], XY], tol_m: float,
              ) -> tuple[dict[tuple[int, int], "_cifp.CifpRunway | None"],
                         list[str], list[str]]:
    """THE CIFP JOIN (issue #119), in two passes at this ONE site.

    Every apt.dat end ``(runway index, end index)`` by its DESIGNATOR
    first (:func:`cifp.match_designator`); then an end that matched nothing
    by its landing THRESHOLD — the apt.dat end advanced along the runway by
    its displaced distance, the point a CIFP ``RWY:`` record locates —
    against the records no designator claimed (:func:`cifp
    .match_threshold`, within ``tol_m`` = ``[identity]
    cifp_threshold_join_m``; one record or a refusal).  A CIFP cycle that
    RENUMBERED a runway keeps its coordinates: KCLT's Custom Data spells
    18R/36L and 18C/36C as 01L/19R and 01R/19L, and before this both
    runways were built with no pins at all (#117).

    A DESIGNATOR JOIN MUST AGREE IN PLACE (issue #994): a record whose
    landing threshold lies OFF the end it named — off its centreline by
    more than ``tol_m``, or outside its own half of the runway
    (:func:`_off_own_end`) — is a different runway carrying that
    designator (KEDW: the apt.dat keeps
    the lakebed runways as 05L/23R, 05R/23L, 07/25 and the paved ones as
    04L/22R, 04R/22L, 06/24, while the CIFP cycle renumbered the paved
    ones to 05L/23R, 05R/23L, 07/25 — the paved thresholds, 11 m above the
    lakebed and 4.6-7.2 km away, pinned the lakebed runways).  The join is
    refused, said in one line, and the record goes back to the pool the
    coordinate pass reads, where it finds the end it locates.

    Returns the record per end (``None`` = no pin), the designators left
    without one, and one line per coordinate join or ambiguity refusal."""
    out: dict[tuple[int, int], _cifp.CifpRunway | None] = {
        (i, k): _cifp.match_designator(e[0], cifp)
        for i, rw in enumerate(runways) for k, e in enumerate(rw.ends)}
    joins: list[str] = []
    for (i, k), r in out.items():
        if r is None:
            continue
        why = _off_own_end(runways[i], k, to_xy(r.lon, r.lat), to_xy, tol_m)
        if why:
            joins.append(f"CIFP designator join refused (#994): {icao} "
                         f"{runways[i].ends[k][0]} -> {r.designator} {why}")
            out[(i, k)] = None
    claimed = {r.designator for r in out.values() if r is not None}
    free_xy = {d: to_xy(r.lon, r.lat) for d, r in cifp.items() if d not in claimed}
    missing: list[str] = []
    for i, rw in enumerate(runways):
        for k, (desig, _lat, _lon, _disp, _over) in enumerate(rw.ends):
            if out[(i, k)] is None and free_xy:
                got, verdict, dist = _cifp.match_threshold(
                    _landing_xy(rw, k, to_xy), free_xy, tol_m)
                if verdict != "none":
                    joins.append(f"CIFP coordinate join (#119): {icao} {desig} -> "
                                 f"{got if got else '-'} {verdict} at {dist:.1f} m "
                                 f"(radius {tol_m:g} m)")
                if got is not None:
                    out[(i, k)] = cifp[got]
                    del free_xy[got]
            if out[(i, k)] is None:
                missing.append(desig)
    return out, missing, joins


def _off_own_end(rw: _t.Any, k: int, p: XY,
                 to_xy: _t.Callable[[float, float], XY], tol_m: float) -> str:
    """Why CIFP point ``p`` is NOT on apt.dat end ``k``'s own runway
    threshold, or ``""`` when it is.

    THE THRESHOLD IS WHATEVER THE AIRPORT DATA SAYS (owner RULINGS
    2026-10-22a, issue #1238): a CIFP landing threshold may lie any
    distance down the runway from the apt.dat end — the CIFP record names
    the displaced distance, and the apt.dat's may differ (CYYJ 32: CIFP
    390 ft, apt.dat 35 m; the old 30 m radius about the apt.dat threshold
    refused it and the end lost its pin).  So the point is judged against
    the runway's own geometry, with NO displaced-length cap: within
    ``tol_m`` of the centreline, and along it from ``tol_m`` before the
    end to the runway's midpoint (past the midpoint it is nearer the
    reciprocal end — the other end's threshold, not this one's)."""
    _desig, lat, lon, _disp, _over = rw.ends[k]
    other = rw.ends[1 - k]
    (x0, y0), (x1, y1) = to_xy(lon, lat), to_xy(other[2], other[1])
    L = math.hypot(x1 - x0, y1 - y0)
    if L <= 0.0:
        d = math.hypot(p[0] - x0, p[1] - y0)
        return "" if d <= tol_m else f"lies {d:.1f} m from the end (radius {tol_m:g} m)"
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    s = (p[0] - x0) * ux + (p[1] - y0) * uy
    lat_off = abs((p[0] - x0) * uy - (p[1] - y0) * ux)
    if lat_off > tol_m:
        return (f"lies {lat_off:.1f} m off the runway centreline "
                f"(tolerance {tol_m:g} m)")
    if not -tol_m <= s <= L / 2.0:
        return (f"lies {s:.1f} m along a {L:.0f} m runway from the end — "
                f"outside its own half (from -{tol_m:g} m to {L / 2.0:.0f} m)")
    return ""


def _landing_xy(rw: _t.Any, k: int, to_xy: _t.Callable[[float, float], XY]) -> XY:
    """The landing threshold of apt.dat end ``k`` — the end advanced
    along the runway by its displaced distance, the point a CIFP ``RWY:``
    record locates."""
    _desig, lat, lon, disp, _over = rw.ends[k]
    other = rw.ends[1 - k]
    (x0, y0), (x1, y1) = to_xy(lon, lat), to_xy(other[2], other[1])
    L = math.hypot(x1 - x0, y1 - y0)
    f = disp / L if L > 0.0 else 0.0
    return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f


def _entry_quantum(law: Law) -> float:
    """§46 (4): the law's ``input_quantum_m``, or the MEASUREMENT ARM's
    override of it.

    ONE quantiser in the tree (:meth:`model.frame.Frame.entry`) and one
    knob: ``Config.xplat_quantise_m`` / ``O4_V2_XPLAT_QUANTISE_M`` no
    longer runs a second quantiser of its own — it OVERRIDES this value
    for an arm, including with ``0`` (the pre-§46, unquantised arm, which
    is how (6)'s residues are attributed against the shipped law).  The
    override is reachable only when the dump recorder is armed, so the
    shipped path reads law and nothing else.
    """
    q = input_quantum_m(law)
    xplat = _projection_recorder()
    if xplat is not None:
        over = xplat.projection_quantum_override()
        if over is not None:
            q = float(over)
        xplat.record_quantum(q)
    return q


def _vector_to_xy(frame: Frame) -> _t.Callable[[float, float], XY]:
    """A scalar ``to_xy(lon, lat)`` — THE FRAME'S OWN, never a second one.

    This used to build its OWN ``pyproj`` transformer, byte-for-byte the
    frame's — so the module docstring's "the frame carries the transformer
    factory" was not true of the stage that produces every coordinate in
    the airport, and any change made at the frame (lane
    ``xplatdeterminism`` needed one to attribute a cross-platform
    divergence, and measured this duplicate by watching it have no effect)
    silently never reached the load.  One derivation site.

    IT IS THE **ENTRY** PROJECTION (§46 (9) census row 1).  Everything
    this stage projects — every apt.dat runway end, pavement and boundary
    ring, taxi node and startup, every OSM way point, every DSF ``.pol`` /
    ``.fac`` ring and object anchor — arrives from OUTSIDE the frame, so
    it is quantised at ``Frame.input_quantum_m`` once, here, and the three
    platforms are fed identical doubles (§46 (3)).  The frame's exact
    ``to_xy`` is for OUR OWN geometry and is not reached from this stage.

    THE DUMP HOOK (lane ``xplatspread``).  When — and ONLY when — the
    cross-platform projection recorder has been armed by
    ``pipeline/build.build`` under ``Config.xplat_dump``, the frame's
    function is wrapped so every ``(lon, lat) -> (x, y)`` it evaluates is
    recorded as exact ``float.hex()``.  Off, this function returns the
    frame's own callable UNCHANGED — not a wrapper that happens to be a
    no-op — so arming is byte-neutral by construction and cannot be
    reached from an environment variable (the package's own twin forbids
    reading one).  The recorder now RECORDS ONLY: the quantum it used to
    apply moved to the frame, where the law lives (``_entry_quantum``).
    """
    base = frame.entry()
    xplat = _projection_recorder()
    if xplat is None:
        return base

    def to_xy(lon: float, lat: float) -> XY:
        x, y = base(lon, lat)
        xplat.record_projection(lon, lat, x, y)
        return (x, y)

    return to_xy


def _projection_recorder():
    """The armed ``pipeline/xplat`` module, or ``None``.

    Looked up in ``sys.modules`` rather than imported: ``pipeline``
    imports this package, so an import here would be a cycle at module
    load.  When the recorder is armed, ``pipeline/build`` has necessarily
    already imported it, so the lookup always finds what exists.
    """
    root = __name__.rsplit(".", 2)[0]
    mod = _sys.modules.get(root + ".pipeline.xplat")
    if mod is None or not mod.projection_armed():
        return None
    return mod


def _pack_dump(icao: str, inputs: Inputs, rep: LoadReport, name: str, root: str,
               tile: tuple[int, int]) -> str | None:
    """The cached text dump of pack ``name``'s PRISTINE tile DSF; a pack
    DSF with none REFUSES the build (``PackDumpStale``)."""
    pack_dsf = _dw.pristine_dsf_path(_dsf.dsf_path_in_pack(root, *tile))
    dump_path = (_dsf.find_text_dump(inputs.mod_cache_root, name, *tile,
                                     dsf_path=pack_dsf)
                 if inputs.mod_cache_root else None)
    if (dump_path is None and inputs.mod_cache_root
            and os.path.isfile(pack_dsf)):
        rep.dsf_dump_stale = True
        # THE REAL CONDITION, in plain words (#560).  This said "the pack
        # DSF is newer than every cached text dump" for every cause — on
        # 2026-10-11 for a 0-byte dump of an UNCHANGED file.  A DSFTool
        # failure is raised earlier, by the refresh itself
        # (``engine_v2.fresh_pack_dump``); what reaches here is a dump
        # nobody made, an empty one, or dumps of another version.
        cache_dir = _dsf.mod_cache_dir(inputs.mod_cache_root, name)
        raise PackDumpStale(
            name,
            f"{icao}: the scenery pack file {pack_dsf} cannot be read: "
            f"{_dsf.missing_dump_reason(cache_dir, pack_dsf)}. The pack's "
            "objects are never read from a dump of another version of the "
            "file (RULINGS 2026-09-11m). The app makes this dump before "
            "each build and re-makes an empty one; with the harness, run "
            "build_airport.py --refresh-data airport_mod_cache.")
    return dump_path


class _DsfPolygons:
    """The polygons of a pack's tile DSF dump as the load reads them: the
    pavement PAGES (``dsf:pol`` sources and §60 gap sheets) and the REST
    (facades and open lots).  #1630: an object pack's dump is read for the
    rest and the serving pack's for the pages, so each read says which."""

    def __init__(self, to_xy, own_extent):
        self.to_xy, self.own_extent = to_xy, own_extent
        self.pavements: list[Pavement] = []
        self.sheets: list[Pavement] = []
        self.buildings: list[Building] = []
        self.n_fac = self.n_lot = self.n_far = 0

    def _near(self, ring) -> bool:
        return self.own_extent is None or self.own_extent.intersects(_shape_of(ring))

    def read(self, dump_path: str, root: str, index, *, pages: bool, rest: bool):
        """Read ``dump_path`` (resources resolve in ``root``); returns the dump."""
        to_xy = self.to_xy
        is_pavement = _dsf.pavement_gate(
            lambda p: _obj8.resolve_resource(p, root, index))

        def _named(p: str) -> bool:
            return _dsf.building_role_for_def(p) is not None \
                or is_pavement(p)[0] is not None

        # §52 (RULINGS 2026-10-04d (3) (c)): an OPEN-LOT facade is read by
        # what its FILE says, never by name — the only class the name gate
        # does not already carry that this stage admits
        dump = _dsf.read_dump(
            dump_path, lambda p: _named(p) or (rest and _facade.is_lot_def(p, root, index)))
        i = -1          # the id index counts the NAME-GATED polygons, as before
        # §60: a page admitted by its own SURFACE is a GAP SHEET.  It is
        # consumed BEFORE the index advances, so no ``dsf:pol<i>`` /
        # ``dsf:fac<i>`` id moves; it is numbered after the object sheets.
        for poly in dump.polygons:
            ring = _ring(poly.windings[0], to_xy)
            holes = tuple(_ring(h, to_xy) for h in poly.windings[1:])
            if not _named(poly.def_path):
                if rest and self._near(ring):
                    self.buildings.append(Building(
                        f"dsf:faclot{self.n_lot}", ring, holes,
                        _facade.LOT_SOURCE, None, None, None,
                        FacadeRead(poly.def_path, _facade.LOT)))
                    self.n_lot += 1
                continue
            kind, code = is_pavement(poly.def_path)
            if kind == _dsf.SHEET:
                if not pages:
                    continue
                if not self._near(ring):
                    self.n_far += 1
                    continue
                self.sheets.append(Pavement(
                    "", normalise_surface(_dsf.pavement_surface_code(poly.def_path, code)),
                    ring, holes, poly.def_path))
                continue
            i += 1
            if kind == _dsf.SOURCE:
                if not pages:
                    continue
                if not self._near(ring):
                    self.n_far += 1
                    continue
                # Draped stock/material pavement pages ARE pavement (v1
                # ``read_dsf_pavements``): 136k m2 of CYXY's aprons ship
                # only as ``.pol`` polygons in the custom pack's DSF.
                # The overlay gate (a page painted ON apt.dat pavement)
                # is classification's, in ``classify/evidence.py``.
                self.pavements.append(Pavement(
                    f"dsf:pol{i}", normalise_surface(
                        _dsf.pavement_surface_code(poly.def_path, code)),
                    ring, holes, poly.def_path))
                continue
            role = _dsf.building_role_for_def(poly.def_path) or "building"
            if role == "bridge" or not rest:
                continue
            self.buildings.append(Building(
                f"dsf:fac{i}", ring, holes, f"dsf:fac:{role}", None, None, None,
                _facade.read_placed(poly, root, index, to_xy)))
            self.n_fac += 1
        return dump


def _ring(pts: _t.Sequence[tuple[float, float]],
          to_xy: _t.Callable[[float, float], XY]) -> tuple[XY, ...]:
    """``(lon, lat)`` ring -> frame ring, closing duplicate dropped."""
    out = [to_xy(lo, la) for lo, la in pts]
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return tuple(out)


def _is_building(tags: _t.Mapping[str, str]) -> bool:
    b = tags.get("building", "").lower()
    if b and b not in ("no", "none"):
        return True
    if tags.get("building:part", "no") != "no":
        return True
    return tags.get("aeroway") in BUILDING_AEROWAY_TAGS


def _osm_id(wid: str) -> int:
    """Namespaced way id -> a stable int (tile prefix folded in).

    A non-numeric id — §25's stitched relation rings, ``-2#0`` — folds
    through CRC32, never ``hash()``: ``hash(str)`` is salted per process
    (PYTHONHASHSEED), so the same extract would name the same ring a
    different way on every run."""
    tail = wid.rsplit(":", 1)[-1]
    try:
        return int(tail)
    except ValueError:
        return -(zlib.crc32(wid.encode("utf-8")) % (1 << 31)) - 1


def _float_or_none(s: str | None) -> float | None:
    try:
        return float(s.split()[0]) if s else None
    except ValueError:
        return None


def _int_or_none(s: str | None) -> int | None:
    try:
        return int(float(s)) if s else None
    except ValueError:
        return None


def _sheet_area(sheet: Pavement) -> float:
    """Net area of a sheet page (outer minus holes), m2; 0 when degenerate."""
    if len(sheet.outer) < 3:
        return 0.0
    from shapely.geometry import Polygon
    return float(Polygon(sheet.outer, [h for h in sheet.holes
                                       if len(h) >= 3]).buffer(0).area)


def _shape_of(ring):
    from shapely.geometry import Polygon, LineString, Point
    pts = list(ring)
    if len(pts) >= 3:
        p = Polygon(pts)
        return p if p.is_valid else p.buffer(0)
    return LineString(pts) if len(pts) == 2 else Point(pts[0])


def _own_extent(runways, pavements, boundaries, margin_m: float):
    """The airport's OWN apt.dat extent (runway rectangles, 110 pavements,
    130 boundaries) buffered by ``margin_m``; ``None`` with no geometry."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    parts = []
    for rw in runways:
        try:
            (ax, ay), (bx, by) = rw.ends[0].xy, rw.ends[1].xy
            w = float(rw.width_m or 60.0) / 2.0
            import math as _m
            L = _m.hypot(bx - ax, by - ay) or 1.0
            nx, ny = -(by - ay) / L * w, (bx - ax) / L * w
            parts.append(Polygon([(ax + nx, ay + ny), (bx + nx, by + ny),
                                  (bx - nx, by - ny), (ax - nx, ay - ny)]))
        except Exception:
            continue
    for coll in (pavements, boundaries):
        for it in coll:
            if len(it.outer) >= 3:
                p = Polygon(list(it.outer))
                parts.append(p if p.is_valid else p.buffer(0))
    if not parts:
        return None
    return unary_union(parts).buffer(float(margin_m))

