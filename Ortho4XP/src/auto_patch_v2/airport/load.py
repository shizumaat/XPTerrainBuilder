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
import typing as _t

from ..law import Law
from ..law.tables import identity_dp
from ..model.airport import (Airport, Boundary, Building, DsfObject,
                             GroundRoute, LinearFeature, OsmWay, Pavement,
                             Runway, RunwayEnd, Startup, Surface, TaxiEdge,
                             TaxiNode)
from ..model.frame import XY, Frame
from . import apt_dat as _apt
from . import cifp as _cifp
from . import dem as _dem
from . import dsf as _dsf
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


@_dc.dataclass
class LoadReport:
    """What the loader saw and did NOT turn into a graded input."""

    apt_dat_path: str = ""
    pack_name: str = ""
    helipads: tuple[str, ...] = ()
    cifp_path: str | None = None
    cifp_missing_ends: tuple[str, ...] = ()
    buildings_by_source: dict[str, int] = _dc.field(default_factory=dict)
    dsf_dump_path: str | None = None
    dsf_pavements: int = 0
    footprint_cache_path: str | None = None
    unresolved_objects: int = 0
    osm_sources: tuple[str, ...] = ()
    dem_provenance: dict[str, str] = _dc.field(default_factory=dict)
    notes: list[str] = _dc.field(default_factory=list)


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
        sel = _pack.select_pack(inputs.xplane_root, icao)
        if sel is None:
            raise FileNotFoundError(f"{icao}: no apt.dat under {inputs.xplane_root}")
    block = _apt.read_airport_block(sel.apt_dat_path, icao)
    if not block:
        raise ValueError(f"{icao}: not in {sel.apt_dat_path}")
    apt = _apt.parse_airport_block(block)
    rep.apt_dat_path, rep.pack_name = sel.apt_dat_path, sel.name
    rep.helipads = tuple(h.name for h in apt.helipads)

    lat0, lon0 = apt.reference_point()
    frame = Frame(icao, (lat0, lon0), identity_dp(law))
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
                 tuple(_ring(h, to_xy) for h in p.rings[1:]), p.description)
        for p in apt.pavements)
    lines = tuple(
        LinearFeature(f"line{ln.index}", ln.line_type,
                      tuple(to_xy(lo, la) for lo, la in ln.points), ln.closed)
        for ln in apt.lines)
    boundaries = tuple(
        Boundary(f"boundary{b.index}", _ring(b.rings[0], to_xy),
                 tuple(_ring(h, to_xy) for h in b.rings[1:]))
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
    if inputs.osm_root:
        for feed in _osm.FEEDS:
            doc = _osm.load_feed(inputs.osm_root, feed, lat0, lon0,
                                 inputs.radius_deg)
            sources.extend(doc.sources)
            for w in doc.ways:
                pts = tuple(to_xy(lo, la) for la, lo in w.points)
                osm_ways.append(OsmWay(_osm_id(w.id), feed, pts, w.closed, w.tags))
                if w.closed and _is_building(w.tags):
                    buildings.append(Building(
                        f"osm:{w.id}", pts[:-1], (), "osm",
                        _float_or_none(w.tags.get("height")),
                        _int_or_none(w.tags.get("building:levels"))))
    rep.osm_sources = tuple(sources)
    rep.buildings_by_source["osm"] = len(buildings)

    # ── DSF: facades, object footprints, placements ────────────────
    dsf_objects: list[DsfObject] = []
    dump_path = inputs.dsf_dump_path or (
        _dsf.find_text_dump(inputs.mod_cache_root, sel.name, *tile)
        if inputs.mod_cache_root else None)
    rep.dsf_dump_path = dump_path
    n_fac = n_obj = n_pol = 0
    dsf_pavements: list[Pavement] = []
    if dump_path and os.path.isfile(dump_path):
        dump = _dsf.read_dump(
            dump_path, lambda p: _dsf.building_role_for_def(p) is not None
            or _dsf.is_pavement_def(p))
        for i, poly in enumerate(dump.polygons):
            if _dsf.is_pavement_def(poly.def_path):
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
        for i, pl in enumerate(dump.placements):
            if not pl.def_path.lower().endswith((".obj", ".agp")):
                continue
            if abs(pl.lat - lat0) > inputs.radius_deg or \
                    abs(pl.lon - lon0) > inputs.radius_deg:
                continue
            local = os.path.join(sel.root, pl.def_path)
            hardness = _dsf.obj8_hardness(local) if not pl.def_path.startswith("lib/") \
                else None
            if hardness is None:
                rep.unresolved_objects += 1
            dsf_objects.append(DsfObject(
                f"dsf:obj{i}", pl.def_path, to_xy(pl.lon, pl.lat),
                pl.heading_deg, None, bool(hardness and hardness[1]), None,
                0.0))
    rep.dsf_pavements = n_pol
    pavements = pavements + tuple(dsf_pavements)
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

    # ── DEM ────────────────────────────────────────────────────────
    if inputs.elevation_root and inputs.dem_frame == "production":
        from . import dem_production as _prod
        dem = _prod.load_production_dem(frame, icao, inputs.elevation_root,
                                        inputs.osm_root, inputs.xplane_root,
                                        allow_degraded=inputs.allow_degraded_dem)
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

def _vector_to_xy(frame: Frame) -> _t.Callable[[float, float], XY]:
    """A scalar ``to_xy(lon, lat)`` over ONE pyproj transformer."""
    from pyproj import Transformer  # local: geodesy lives in the loaders
    fwd = Transformer.from_crs("EPSG:4326", frame.crs, always_xy=True)

    def to_xy(lon: float, lat: float) -> XY:
        x, y = fwd.transform(lon, lat)
        return (float(x), float(y))
    return to_xy


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
    """Namespaced way id -> a stable int (tile prefix folded in)."""
    tail = wid.rsplit(":", 1)[-1]
    try:
        return int(tail)
    except ValueError:
        return abs(hash(wid)) % (1 << 31)


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

