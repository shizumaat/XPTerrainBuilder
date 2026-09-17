"""``load(icao, inputs, law)`` — ONE :class:`Airport` in the local metric
frame from every input (M0 §4 step 1).  Every path is an argument
(``Inputs``); nothing is read from a cfg or the environment.

The frame origin is the airport reference point (apt.dat ``1302
datum_lat/lon``, else the runway-end mean) and the identity precision is
``law.emit.identity.coordinate_dp`` (memory ``canonical-identity-join``).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import sys as _sys
import typing as _t
import zlib

from ..law import Law
from ..law.tables import identity_dp, input_quantum_m
from ..model.airport import (Airport, Boundary, Building, DsfObject,
                             GroundRoute, LinearFeature, OsmWay, Pavement,
                             Runway, RunwayEnd, Startup, Surface, TaxiEdge,
                             TaxiNode)
from ..model.frame import XY, Frame
from . import apt_dat as _apt
from . import borrow as _borrow
from . import cifp as _cifp
from . import dem as _dem
from . import dsf as _dsf
from . import dsf_write as _dw
from . import obj8 as _obj8
from . import object_pavement as _objpav
from . import osm as _osm
from . import pack as _pack

__all__ = ["Inputs", "LoadReport", "load", "load_with_report",
           "normalise_surface", "runway_code_number", "runway_code_letter"]

#: ICAO Annex 14 Vol I Table 1-1: aerodrome reference code NUMBER by
#: reference field length (a DEFINITION, not a tunable; runway length is
#: the proxy for the reference field length).
CODE_NUMBER_BY_LENGTH_M: tuple[tuple[float, int], ...] = (
    (800.0, 1), (1200.0, 2), (1800.0, 3), (float("inf"), 4))
#: Code LETTER proxy by runway width (the repo's convention: letters are
#: wingspan / OMGWS classes, width is what apt.dat carries).
CODE_LETTER_BY_WIDTH_M: tuple[tuple[float, str], ...] = (
    (18.0, "A"), (23.0, "B"), (30.0, "C"), (45.0, "D"), (60.0, "E"),
    (float("inf"), "F"))
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
    buildings_by_source: dict[str, int] = _dc.field(default_factory=dict)
    dsf_dump_path: str | None = None
    #: the pack's tile DSF is newer than every cached text dump (refused)
    dsf_dump_stale: bool = False
    dsf_pavements: int = 0
    #: DSF pavement pages refused as another airport's (beyond the admission gate)
    dsf_pavements_far: int = 0
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
    dem_provenance: dict[str, str] = _dc.field(default_factory=dict)
    notes: list[str] = _dc.field(default_factory=list)
    #: The flat-site verdict record (``airport/flat_site.record``; set by
    #: the pipeline once the detector ran — ``report.load.flat_site``).
    flat_site: dict | None = None
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


def runway_code_number(length_m: float) -> int:
    for lim, code in CODE_NUMBER_BY_LENGTH_M:
        if length_m < lim:
            return code
    return 4


def runway_code_letter(width_m: float) -> str:
    for lim, letter in CODE_LETTER_BY_WIDTH_M:
        if width_m <= lim:
            return letter
    return "F"


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
    if inputs.apt_dat_path:
        sel = _pack.PackSelection(
            os.path.basename(os.path.dirname(os.path.dirname(inputs.apt_dat_path)))
            or "fixture", os.path.dirname(os.path.dirname(inputs.apt_dat_path)),
            inputs.apt_dat_path, False)
    else:
        sel = _pack.select_pack(inputs.xplane_root, icao, law)
        if sel is None:
            raise FileNotFoundError(f"{icao}: no apt.dat under {inputs.xplane_root}")
    block = _apt.read_airport_block(sel.apt_dat_path, icao)
    if not block:
        raise ValueError(f"{icao}: not in {sel.apt_dat_path}")
    apt = _apt.parse_airport_block(block)
    rep.apt_dat_path, rep.pack_name = sel.apt_dat_path, sel.name
    rep.helipads = tuple(h.name for h in apt.helipads)

    # THE FRAME IS THE CUSTOM BLOCK'S — taken BEFORE the borrow composes,
    # because §44 (2) is explicit that borrowing pavement does not move
    # the airport's reference point.
    lat0, lon0 = apt.reference_point()
    # ── §44 (3) THE PAVEMENT BORROW, composed HERE and nowhere else ────
    # (owner RULINGS 2026-09-15f; decided in ``pack.select_pack``).  The
    # Global Airports block's row-110 polygons are APPENDED to the pack's
    # own and its row-130 boundary taken only when the pack authored
    # none; everything else below reads the composed block exactly as it
    # reads an authored one.
    bres = _borrow.compose(sel.borrow, icao, apt)
    apt = bres.airport
    n_own_pav = bres.custom_pavements
    rep.pavement_source = bres.record(sel.name)
    rep.pavement_borrow_line = bres.line(icao)
    frame = Frame(icao, (lat0, lon0), identity_dp(law),
                  input_quantum_m=_entry_quantum(law))
    to_xy = _vector_to_xy(frame)
    tile = (int(math.floor(lat0)), int(math.floor(lon0)))

    # ── runways + CIFP ─────────────────────────────────────────────
    cifp_path = os.path.join(inputs.cifp_dir, f"{icao}.dat") if inputs.cifp_dir else ""
    cifp = _cifp.read_cifp_runways(cifp_path) if os.path.isfile(cifp_path) else {}
    rep.cifp_path = cifp_path if cifp else None
    missing: list[str] = []
    runways: list[Runway] = []
    for rw in apt.runways:
        ends = []
        for desig, lat, lon, disp, over in rw.ends:
            rec = _cifp.match_designator(desig, cifp)
            if rec is None:
                missing.append(desig)
            ends.append(RunwayEnd(desig, to_xy(lon, lat), (lat, lon), disp,
                                  over, rec.elevation_m if rec else None,
                                  rec.source if rec else ""))
        r = Runway(f"{ends[0].name}/{ends[1].name}", rw.width_m,
                   normalise_surface(rw.surface), (ends[0], ends[1]), None,
                   runway_code_letter(rw.width_m))
        runways.append(_dc.replace(r, code_number=runway_code_number(r.length_m)))
    rep.cifp_missing_ends = tuple(missing)

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
    if stale and inputs.dem_frame == "production" and not inputs.allow_degraded_dem:
        raise RuntimeError(
            f"{icao}: {len(stale)} cached road feed(s) were written under a "
            f"SUPERSEDED tag whitelist — the reading would be missing the "
            f"tags the current one keeps (ROADS_TAGS_OF_INTEREST / "
            f"ROAD_CACHE_TAG_SCHEMA {_osm.ROAD_CACHE_TAG_SCHEMA}), and the "
            f"structure readers would silently see fewer bores (measured at "
            f"OTHH: 8 against 16, corridors 7 against 9 — RULINGS "
            f"2026-09-15ar, attributed by lane v2othhdet): "
            + "; ".join(sorted(stale))
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
    dump_path = inputs.dsf_dump_path or (
        _dsf.find_text_dump(inputs.mod_cache_root, sel.name, *tile,
                            dsf_path=pack_dsf)
        if inputs.mod_cache_root else None)
    rep.dsf_dump_path = dump_path
    if (dump_path is None and inputs.mod_cache_root
            and os.path.isfile(pack_dsf)):
        rep.dsf_dump_stale = True
        raise RuntimeError(
            f"{icao}: the pack DSF {pack_dsf} is newer than every cached text "
            f"dump under {_dsf.mod_cache_dir(inputs.mod_cache_root, sel.name)} "
            f"(no fresh {os.path.basename(pack_dsf)}.<sha256[:8]>.text there — "
            "the dump is named for THIS file, RULINGS 2026-09-11m) "
            "— the pack's objects would be read from a stale dump (OTHH's tunnel "
            "walls, 2026-09-04). Refresh it explicitly: build_airport.py "
            "--refresh-data airport_mod_cache (the app's driver refreshes it "
            "before the build).")
    n_fac = n_obj = n_pol = 0
    dsf_pavements: list[Pavement] = []
    # THE ADMISSION GATE (RULINGS 2026-09-06a): the tile DSF carries EVERY
    # airport's pavement pages; a page is this airport's only within
    # ``identity.dsf_pavement_admission_m`` of its own apt.dat extent.
    own_extent = _own_extent(runways, pavements, boundaries,
                             law.tables.emit.identity.dsf_pavement_admission_m)
    n_far = 0
    if dump_path and os.path.isfile(dump_path):
        dump = _dsf.read_dump(
            dump_path, lambda p: _dsf.building_role_for_def(p) is not None
            or _dsf.is_pavement_def(p))
        for i, poly in enumerate(dump.polygons):
            if _dsf.is_pavement_def(poly.def_path):
                if own_extent is not None and not own_extent.intersects(
                        _shape_of(_ring(poly.windings[0], to_xy))):
                    n_far += 1
                    continue
                # Draped stock/material pavement pages ARE pavement (v1
                # ``read_dsf_pavements``): 136k m2 of CYXY's aprons ship
                # only as ``.pol`` polygons in the custom pack's DSF.
                # The overlay gate (a page painted ON apt.dat pavement)
                # is classification's, in ``classify/evidence.py``.
                dsf_pavements.append(Pavement(
                    f"dsf:pol{i}", normalise_surface(
                        _dsf.pavement_surface_code(poly.def_path)),
                    _ring(poly.windings[0], to_xy),
                    tuple(_ring(h, to_xy) for h in poly.windings[1:]),
                    poly.def_path))
                n_pol += 1
                continue
            role = _dsf.building_role_for_def(poly.def_path) or "building"
            if role == "bridge":
                continue
            buildings.append(Building(
                f"dsf:fac{i}", _ring(poly.windings[0], to_xy),
                tuple(_ring(h, to_xy) for h in poly.windings[1:]),
                f"dsf:fac:{role}", None, None))
            n_fac += 1
        # THE LIBRARY INDEX, read-only (M4b): ``lib/...`` placements
        # resolve through v1's cached merged index; absent = unresolved
        lib_path = _obj8.library_index_path(inputs.mod_cache_root, inputs.xplane_root) \
            if inputs.mod_cache_root and inputs.xplane_root else ""
        index = _obj8.read_library_index(lib_path)
        rep.library_index_path = lib_path if index is not None else None
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
                    resolved, restored = _pack.authored_source(resolved)
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
    rep.dsf_pavements = n_pol
    rep.dsf_pavements_far = n_far
    cache_path = inputs.footprint_cache_path or (
        os.path.join(_dsf.mod_cache_dir(inputs.mod_cache_root, sel.name),
                     f"o4_object_footprints_{tile[0]:+03d}{tile[1]:+04d}.cache")
        if inputs.mod_cache_root else None)
    if cache_path and os.path.isfile(cache_path):
        rep.footprint_cache_path = cache_path
        for i, (ring, kind) in enumerate(_dsf.read_footprint_cache(cache_path)):
            buildings.append(Building(f"dsf:object{i}", _ring(ring, to_xy), (),
                                      f"dsf:object:{kind}", None, None))
            n_obj += 1
    rep.buildings_by_source["dsf:fac"] = n_fac
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
    for k, body in enumerate(op_bodies):
        dsf_pavements.append(Pavement(
            f"dsf:objpav{k}", normalise_surface(
                _dsf.pavement_surface_code(body.resource)),
            tuple((float(x), float(y)) for x, y in body.polygon.exterior.coords[:-1]),
            tuple(tuple((float(x), float(y)) for x, y in r.coords[:-1])
                  for r in body.polygon.interiors),
            body.resource))
    pavements = pavements + tuple(dsf_pavements)

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
        tuple(dsf_objects), pack, dem, law.ruleset_key)
    return airport, rep


# ── helpers ──────────────────────────────────────────────────────────────

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

