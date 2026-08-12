"""Pavement scoring classifier v2 — evidence fusion (shadow phase).

Spec: ``docs/specs/pavement-scoring-classifier-spec.md`` (owner decisions
2026-07-27: full 4-class scope, shadow-first rollout, legacy verdict as
the development fallback, chain retirement as the end goal).

Every pavement shape accumulates weighted points toward the four classes
the owner named — APRON, TAXI, SERVICE, GROUNDSIDE — from every evidence
layer available at this airport, each layer scaled by a per-airport
RELIABILITY factor so a sparse source's silence is never read as negative
evidence.  Owner rulings are HARD GATES that remove candidate classes
before the argmax; scores only ever decide within the space the law
leaves open.

SINGLE-SPINE CONSTRAINT (owner, verbatim intent): the apt.dat 1201/1202
route-arc spine remains the only linework that slices pavement or carries
taxi identity.  Everything this module reads — OSM taxiway lines, painted
lines, road feeds — is a buffered COVERAGE layer.  Nothing here is ever
merged into the spine.

Shadow mode (``"shadow"``) runs at the very end of the pipeline, scores
every final pavement shape, logs agreement against the legacy chain's
verdict, and MUTATES NOTHING.  Enactment (``"on"``, the default since
the owner's 2026-07-28 approval) is Phase B: ``enact_classify`` runs in
the ``classify_pavement_v1`` slot, its verdicts BECOME the roles, and
the legacy passes it subsumes are gated off in the pipeline.
"""
from __future__ import annotations

import os as _os
from dataclasses import dataclass, field

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

import O4_UI_Utils as UI
from .config import (
    DSF_OBJECT_PAVEMENT_MIN_AIRCRAFT_WIDTH_M,
    DSF_OBJECT_PAVEMENT_OPENING_RATIO,
    PAVEMENT_SCORE_AEROWAY_PIECE_MIN_M2,
    PAVEMENT_SCORE_AEROWAY_SEVER_MIN_M2,
    PAVEMENT_SCORE_AEROWAY_SEVER_MIX_FRAC,
    PAVEMENT_SCORE_AIRCRAFT_PATH_WIDTH_M,
    PAVEMENT_SCORE_APRON_MIN_HALF_WIDTH_M,
    PAVEMENT_SCORE_RUNWAY_CONTACT_MIN_FRAC,
    PAVEMENT_SCORE_RUNWAY_CONTACT_MIN_M,
    PAVEMENT_SCORE_RUNWAY_CONTACT_TOL_M,
    PAVEMENT_SCORE_TUNNEL_VETO_FRAC,
    PAVEMENT_CLASS_TAIL_AXIS_ROAD_FRAC,
    PAVEMENT_CLASS_TAIL_MAX_WIDTH_M,
    PAVEMENT_CLASS_TAIL_MIN_LENGTH_M,
    PAVEMENT_SCORE_BOUNDARY_OUT_FRAC,
    PAVEMENT_SCORE_MARGIN_HIGH,
    PAVEMENT_SCORE_MARGIN_MED,
    PAVEMENT_SCORE_MIN_AREA_M2,
    PAVEMENT_SCORE_PURE,
    PAVEMENT_SCORE_RELIABILITY,
    PAVEMENT_SCORE_SPINE_BUFFER_M,
    PAVEMENT_SCORE_TAXI_MAJOR_MIN,
    PAVEMENT_SCORE_THREAD_MIN_FRAC,
    PAVEMENT_SCORE_TRUCK_BUFFER_M,
    PAVEMENT_SCORE_V2,
    PAVEMENT_SCORE_VETO_FRAC,
    PAVEMENT_SCORE_WEIGHTS,
    PAVEMENT_SCORE_WIDE_HALF_M,
    SCORER_SERVICE_ADJ,
)
from .enclaves import publish_airside_enclaves, shape_in_enclave
from .layout import (
    BuiltShape,
    ROLE_APRON,
    ROLE_BUILDING,
    ROLE_CROSS_CONNECTOR,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_JUNCTION,
    ROLE_PRIMARY_PARALLEL,
    ROLE_RUNWAY,
    ROLE_RUNWAY_CROSSING,
    ROLE_SECONDARY_PARALLEL,
    ROLE_SERVICE_JUNCTION,
    ROLE_SERVICE_ROAD,
    ROLE_STUB,
)
from .pavement_classification import (
    _GEOM_EXC,
    CoverIndex,
    _cover_index,
    _is_tail,
    _pavement_adjacency_index,
    evidence_sources,
)

__all__ = [
    "CLASS_APRON", "CLASS_TAXI", "CLASS_SERVICE", "CLASS_GROUNDSIDE",
    "CLASSES", "ScoreSources", "SourceReliability", "score_sources",
    "source_reliability", "ensure_alt_sources", "shape_features",
    "score_shape", "shadow_classify", "enact_classify",
    "runway_connectivity", "sever_unreachable",
    "reclass_building_faces",
]

# Layout metre space is anchored at the airport anchor.
_ORIGIN = Point(0.0, 0.0)

CLASS_APRON = "APRON"
CLASS_TAXI = "TAXI"
CLASS_SERVICE = "SERVICE"
CLASS_GROUNDSIDE = "GROUNDSIDE"
CLASSES = (CLASS_APRON, CLASS_TAXI, CLASS_SERVICE, CLASS_GROUNDSIDE)

# Legacy final role → the 4-class vocabulary, for the shadow diff.
# Runway family, buildings, boundary, clearance features etc. are out of
# scope (spec §3) and simply not scored.
LEGACY_ROLE_TO_CLASS = {
    ROLE_APRON: CLASS_APRON,
    ROLE_JUNCTION: CLASS_TAXI,
    ROLE_PRIMARY_PARALLEL: CLASS_TAXI,
    ROLE_SECONDARY_PARALLEL: CLASS_TAXI,
    ROLE_STUB: CLASS_TAXI,
    ROLE_CROSS_CONNECTOR: CLASS_TAXI,
    ROLE_SERVICE_ROAD: CLASS_SERVICE,
    ROLE_SERVICE_JUNCTION: CLASS_SERVICE,
    ROLE_GROUNDSIDE_PAVEMENT: CLASS_GROUNDSIDE,
}

# apt.dat row-110 ``name`` keyword buckets (spec §5).  Checked in this
# order — "SERVICE ROAD" must land service, not road-the-noun-elsewhere;
# PARKING in apt.dat names means AIRCRAFT parking (a stand), not cars.
_NAME_SERVICE_TOKENS = ("SERVICE", "SVC", "ROAD", "PERIMETER", "PERIM",
                        "VEHICLE", "GSE")
_NAME_TAXI_TOKENS = ("TAXIWAY", "TAXILANE", "TWY", "TXWY", "TWLN", "TAXI")
_NAME_APRON_TOKENS = ("APRON", "RAMP", "STAND", "GATE", "TERMINAL", "TERM",
                      "PARKING", "PAD", "TARMAC")

# Feature → reliability-source key (None = pure geometry, r = 1).
_FEATURE_SOURCE = {
    "name_apron": "apt_names", "name_taxi": "apt_names",
    "name_service": "apt_names",
    "osm_apron": "osm_aeroway", "osm_stand": "osm_aeroway",
    "osm_taxi": "osm_aeroway", "osm_taxi_major": "osm_aeroway",
    "spine_cover": "spine", "spine_thread": "spine",
    "truck_cover": "truck", "truck_thread": "truck",
    "truck_corridor": "truck",
    "road_cover": "road_feed", "road_thread": "road_feed",
    "road_narrow": "road_feed", "parking_cover": "road_feed",
    "alt_name_apron": "alt_apt", "alt_name_taxi": "alt_apt",
    "alt_name_service": "alt_apt", "alt_taxi_cover": "alt_apt",
}


def _line_index(line_union):
    """``(STRtree, pieces)`` over a thread layer's union pieces."""
    if line_union is None or getattr(line_union, "is_empty", True):
        return None
    pieces = list(getattr(line_union, "geoms", [line_union]))
    if len(pieces) < 8:
        return None
    try:
        from shapely.strtree import STRtree
        return (STRtree(pieces), pieces)
    except _GEOM_EXC:
        return None


def _cut_length(polygon, line_union, index) -> float:
    """Length of ``line_union`` inside ``polygon``.

    With an index, only nearby pieces are unioned and cut — exact for
    any overlap structure, because pieces that miss the polygon add no
    length inside it.
    """
    if index is None:
        return line_union.intersection(polygon).length
    tree, pieces = index
    hits = [pieces[int(i)]
            for i in tree.query(polygon, predicate="intersects")]
    if not hits:
        return 0.0
    sub = hits[0] if len(hits) == 1 else unary_union(hits)
    return sub.intersection(polygon).length


def _name_bucket(name: str) -> str | None:
    """``"service" | "taxi" | "apron" | None`` for one row-110 name."""
    up = (name or "").upper()
    if not up:
        return None
    for token in _NAME_SERVICE_TOKENS:
        if token in up:
            return "service"
    for token in _NAME_TAXI_TOKENS:
        if token in up:
            return "taxi"
    for token in _NAME_APRON_TOKENS:
        if token in up:
            return "apron"
    return None


# ═════════════════════════════════════════════════════════════════════
# Stage 1 — evidence layers beyond pavement_classification's
# ═════════════════════════════════════════════════════════════════════

@dataclass
class ScoreSources:
    """The v2-only layers (the rest come from ``EvidenceSources``)."""
    name_apron: CoverIndex = field(default_factory=lambda: CoverIndex([]))
    name_taxi: CoverIndex = field(default_factory=lambda: CoverIndex([]))
    name_service: CoverIndex = field(default_factory=lambda: CoverIndex([]))
    unpaved: CoverIndex = field(default_factory=lambda: CoverIndex([]))
    truck_corridors: CoverIndex = field(
        default_factory=lambda: CoverIndex([]))
    truck_lines: object | None = None
    spine_buffers: CoverIndex = field(default_factory=lambda: CoverIndex([]))
    apt_only: CoverIndex = field(default_factory=lambda: CoverIndex([]))
    named_area_m2: float = 0.0
    truck_len_m: float = 0.0
    spine_len_m: float = 0.0
    # Global-airports cross-reference (owner 2026-07-27): the DEFAULT
    # apt.dat's named polygons + taxi-network territory, as COVERAGE
    # evidence only.  Populated by ``ensure_alt_sources``.
    alt_name_apron: CoverIndex = field(default_factory=lambda: CoverIndex([]))
    alt_name_taxi: CoverIndex = field(default_factory=lambda: CoverIndex([]))
    alt_name_service: CoverIndex = field(
        default_factory=lambda: CoverIndex([]))
    alt_taxi_territory: CoverIndex = field(
        default_factory=lambda: CoverIndex([]))
    alt_path: str = ""
    # ``(STRtree, pieces)`` over each thread layer's union pieces, so a
    # corridor shape intersects only nearby pieces instead of the whole
    # airport's multiline (a per-shape build-budget hotspot).
    spine_thread_index: object | None = None
    truck_thread_index: object | None = None
    road_thread_index: object | None = None
    # OSM ``aeroway=aerodrome`` boundary polygon(s) (owner ruling
    # 2026-07-28: airside never exists outside it — G-BOUNDARY).  None
    # when the tile's OSM layer has no closed aerodrome way for this
    # airport; the gate is then inert.  ``aerodrome_prep`` is the
    # prepared geometry for the cheap fully-inside fast path.
    aerodrome: object | None = None
    aerodrome_prep: object | None = None
    # G-RUNWAY-CONTACT (owner ruling 2026-08-10: "pavement touching a
    # runway cannot be apron").  The RUNWAY RING dilated by the contact
    # tolerance — intersecting a candidate's own ring with it measures
    # SHARED PERIMETER directly.  Built once from
    # ``evidence_sources(layout).runway_union``; ``None`` when the
    # airport has no runway union, which leaves the gate inert.
    runway_edge_halo: object | None = None


def score_sources(layout) -> ScoreSources:
    """Build (once, memoized) the v2-only evidence layers."""
    cached = getattr(layout, "_pavement_score_sources", None)
    if cached is not None:
        return cached
    ss = ScoreSources()
    # apt.dat name priors + unpaved surface codes.
    apron_p, taxi_p, service_p, unpaved_p = [], [], [], []
    named_area = 0.0
    for record in getattr(layout, "apt_pavement_records", None) or []:
        try:
            polygon, name, surface_code = record
        except (TypeError, ValueError):
            continue
        if polygon is None or polygon.is_empty:
            continue
        bucket = _name_bucket(name)
        if bucket is not None:
            named_area += polygon.area
            (apron_p if bucket == "apron"
             else taxi_p if bucket == "taxi" else service_p).append(polygon)
        try:
            if int(surface_code) not in (1, 2):     # asphalt / concrete
                unpaved_p.append(polygon)
        except (TypeError, ValueError):
            pass
    ss.name_apron = _cover_index(apron_p)
    ss.name_taxi = _cover_index(taxi_p)
    ss.name_service = _cover_index(service_p)
    ss.unpaved = _cover_index(unpaved_p)
    ss.named_area_m2 = named_area
    # Truck-route territory (apt.dat 1206) — corridors + raw lines.
    truck_lines, truck_parts, truck_len = [], [], 0.0
    for entry in getattr(layout, "apt_service_centerlines", None) or []:
        # Entries are ``TaxiCenterline`` (``.line``) in the built layout,
        # ``(LineString, name)`` tuples in older/stub layouts.
        line = entry[0] if isinstance(entry, tuple) else \
            getattr(entry, "line", entry)
        if line is None or getattr(line, "is_empty", True):
            continue
        truck_lines.append(line)
        truck_len += line.length
        try:
            truck_parts.append(line.buffer(PAVEMENT_SCORE_TRUCK_BUFFER_M))
        except _GEOM_EXC:
            pass
    ss.truck_corridors = _cover_index(truck_parts)
    ss.truck_len_m = truck_len
    if truck_lines:
        try:
            ss.truck_lines = unary_union(truck_lines)
        except _GEOM_EXC:
            ss.truck_lines = None
    # Spine territory: buffered pieces of the ONE taxi spine (coverage
    # evidence only — never new linework; spec §3 single-spine law).
    ev = evidence_sources(layout)
    spine = ev.taxi_centerlines
    spine_parts = []
    if spine is not None and not spine.is_empty:
        ss.spine_len_m = float(spine.length)
        for piece in getattr(spine, "geoms", [spine]):
            try:
                spine_parts.append(
                    piece.buffer(PAVEMENT_SCORE_SPINE_BUFFER_M))
            except _GEOM_EXC:
                pass
    ss.spine_buffers = _cover_index(spine_parts)
    ss.spine_thread_index = _line_index(spine)
    ss.truck_thread_index = _line_index(ss.truck_lines)
    ss.road_thread_index = _line_index(ev.road_lines)
    # apt.dat-only pavement (pre-DSF snapshot) → third-party provenance.
    ss.apt_only = _cover_index(
        list(getattr(layout, "apt_only_pavement_polys", None) or []))
    # AIRPORT BOUNDARY for role classification (owner rulings
    # 2026-07-28 G-BOUNDARY + 2026-07-29 "ensure we have airport
    # boundary data").  THREE sources, best-first, all in metre space:
    #   1. closed ``aeroway=aerodrome`` WAYS from the tile OSM layer;
    #   2. ``aeroway=aerodrome`` RELATIONS (multipolygons) — outer
    #      member ways stitched into closed rings (endpoint chaining;
    #      an unstitchable ring — e.g. a member outside the 9-tile
    #      merge — is skipped, never guessed);
    #   3. the apt.dat ROW-130 boundary (``layout.airport_boundary``,
    #      already despiked + metre-space) when OSM contributes
    #      nothing — so classification always has a fence wherever
    #      apt.dat drew one.
    # SCOPING (unchanged): the layer's bbox (~5 km) can contain a
    # NEIGHBOURING airport's aerodrome polygon (HECA/HEAZ sit ~1 km
    # apart) — an OSM polygon only joins the boundary when it
    # intersects THIS airport's own source pavement, else every shape
    # here would read "outside".
    features = getattr(layout, "_osm_airport_features", None)
    aerodrome_polys: list = []
    _bnd_n_ways = _bnd_n_rels = 0
    if features and features[0] and features[1]:
        nodes, ways = features[0], features[1]
        ll_to_m = layout.ll_to_m
        own = getattr(layout, "source_pavement_union", None)

        def _admit_ring(points):
            """Closed metre-space ring -> admitted Polygon or None."""
            if len(points) < 4:
                return None
            try:
                p = Polygon(points).buffer(0)
                if p.is_empty or p.area <= 0.0:
                    return None
                if own is not None and not own.is_empty:
                    if not p.intersects(own):
                        return None
                elif p.distance(_ORIGIN) > 2000.0:
                    # No pavement union to test against — accept only
                    # a polygon around the anchor itself.
                    return None
                return p
            except _GEOM_EXC:
                return None

        for _way_id, node_refs, tags in ways:
            if tags.get("aeroway", "") != "aerodrome":
                continue
            points = [ll_to_m(*ll) for ll in
                      (nodes.get(ref) for ref in node_refs)
                      if ll is not None]
            if (points
                    and abs(points[0][0] - points[-1][0]) < 0.5
                    and abs(points[0][1] - points[-1][1]) < 0.5):
                p = _admit_ring(points)
                if p is not None:
                    aerodrome_polys.append(p)
                    _bnd_n_ways += 1
        # RELATION-mapped aerodromes (owner 2026-07-29: the loader
        # already returns relations as ``(id, [outer member way ref,
        # ...], tags)`` but the pipeline used to drop them).  Stitch
        # each relation's outer member ways into closed rings by
        # endpoint chaining (members arrive unordered and possibly
        # reversed).
        relations = features[2] if len(features) > 2 else ()
        way_nds = {wid: nds for (wid, nds, _t) in ways}
        for _rid, outer_ids, tags in (relations or ()):
            if tags.get("aeroway", "") != "aerodrome":
                continue
            frags = [list(way_nds[w]) for w in outer_ids if w in way_nds]
            frags = [f for f in frags if len(f) >= 2]
            while frags:
                chain = frags.pop(0)
                grew = True
                while grew and chain[0] != chain[-1]:
                    grew = False
                    for k, f in enumerate(frags):
                        if f[0] == chain[-1]:
                            chain += f[1:]
                        elif f[-1] == chain[-1]:
                            chain += f[-2::-1]
                        elif f[-1] == chain[0]:
                            chain = f[:-1] + chain
                        elif f[0] == chain[0]:
                            chain = f[::-1][:-1] + chain
                        else:
                            continue
                        frags.pop(k)
                        grew = True
                        break
                if chain[0] != chain[-1]:
                    continue          # unstitchable — skip, never guess
                points = [ll_to_m(*ll) for ll in
                          (nodes.get(ref) for ref in chain)
                          if ll is not None]
                p = _admit_ring(points)
                if p is not None:
                    aerodrome_polys.append(p)
                    _bnd_n_rels += 1
    _bnd_src = "osm"
    if not aerodrome_polys:
        # ROW-130 FALLBACK: apt.dat's own hand-traced fence.  Already
        # metre-space + despiked; no scoping test needed (it IS this
        # airport's boundary by construction).
        _row130 = getattr(layout, "airport_boundary", None)
        if _row130 is not None and not _row130.is_empty:
            aerodrome_polys = [_row130]
            _bnd_src = "row130"
    if aerodrome_polys:
        try:
            ss.aerodrome = unary_union(aerodrome_polys)
            from shapely.prepared import prep as _prep
            ss.aerodrome_prep = _prep(ss.aerodrome)
        except _GEOM_EXC:
            ss.aerodrome = None
            ss.aerodrome_prep = None
    if _os.environ.get("O4_STEP_DEBUG") == "1":
        print(f"    [pav-scoring] boundary: "
              f"{'none' if ss.aerodrome is None else _bnd_src} "
              f"(osm ways={_bnd_n_ways} relation rings={_bnd_n_rels})")
    # G-RUNWAY-CONTACT halo (owner 2026-08-10) — the runway ring, once.
    _rwy_u = getattr(ev, "runway_union", None)
    if _rwy_u is not None and not _rwy_u.is_empty:
        try:
            ss.runway_edge_halo = _rwy_u.boundary.buffer(
                PAVEMENT_SCORE_RUNWAY_CONTACT_TOL_M)
        except _GEOM_EXC:
            ss.runway_edge_halo = None
    layout._pavement_score_sources = ss
    return ss


# ═════════════════════════════════════════════════════════════════════
# Stage 0 — per-airport source reliability
# ═════════════════════════════════════════════════════════════════════

@dataclass
class SourceReliability:
    """r ∈ [0,1] per evidence source at THIS airport (spec §4).

    Scales how many points a source's evidence can contribute — a sparse
    source's silence must never read as negative evidence.
    """
    apt_names: float = 0.0
    osm_aeroway: float = 0.0
    road_feed: float = 0.0
    truck: float = 0.0
    spine: float = 0.0
    alt_apt: float = 0.0

    def of(self, feature: str) -> float:
        source = _FEATURE_SOURCE.get(feature)
        return 1.0 if source is None else float(getattr(self, source, 0.0))


def _clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else x)


def source_reliability(layout) -> SourceReliability:
    """Compute (once, memoized) the per-source reliability factors."""
    cached = getattr(layout, "_pavement_score_reliability", None)
    if cached is not None:
        return cached
    ev = evidence_sources(layout)
    ss = score_sources(layout)
    rel = SourceReliability()
    knobs = PAVEMENT_SCORE_RELIABILITY
    source_union = getattr(layout, "source_pavement_union", None)
    src_area = float(getattr(source_union, "area", 0.0) or 0.0)
    if src_area > 0.0:
        rel.apt_names = _clamp01(ss.named_area_m2 / src_area)
        try:
            airside_geometry = ev.osm_airside.geometry()
            airside_area = float(getattr(airside_geometry, "area", 0.0)
                                 or 0.0)
        except _GEOM_EXC:
            airside_area = 0.0
        area_term = _clamp01(
            airside_area / (knobs["osm_area_ratio"] * src_area))
        count_term = _clamp01(ev.n_osm_ways / knobs["osm_ways"])
        rel.osm_aeroway = 0.5 * area_term + 0.5 * count_term
    rel.road_feed = _clamp01(ev.n_road_ways / knobs["road_ways"])
    rel.truck = _clamp01(ss.truck_len_m / knobs["truck_len_m"])
    rel.spine = _clamp01(ss.spine_len_m / knobs["spine_len_m"])
    rel.alt_apt = float(getattr(layout, "_pavement_score_alt_rel", 0.0))
    layout._pavement_score_reliability = rel
    return rel


# ═════════════════════════════════════════════════════════════════════
# Global-airports cross-reference (owner request 2026-07-27)
# ═════════════════════════════════════════════════════════════════════

def _load_alt_airport(path: str, icao: str):
    """``load_airport`` via a byte-seek straight to ``icao``'s block.

    The Global Airports apt.dat is ~450 MB and the reader's line scan
    to a deep block costs ~1 s of the build budget.  ``mmap.find`` on
    the raw bytes locates the same row-1 header ``_read_airport_block``
    would accept (line-anchored, ``parts[0] == "1"``, ``parts[4] ==
    ICAO``), the same next-header block end, and hands the identical
    block bytes to ``load_airport`` through a temp file.  ANY miss or
    error falls back to the plain full-file call.
    """
    from .apt_dat_reader import load_airport
    try:
        import mmap
        import os as _os
        import tempfile
        target = icao.upper().encode("ascii")

        def _next_header(mm, search_from):
            # Each token search is bounded by the best candidate so far
            # — an absent token must not scan the remaining file.
            best = None
            for token in (b"\n1 ", b"\n1\t"):
                probe = search_from
                while True:
                    limit = mm.size() if best is None else best
                    nxt = mm.find(token, probe, limit)
                    if nxt == -1:
                        break
                    ls = nxt + 1
                    le = mm.find(b"\n", ls)
                    le = mm.size() if le == -1 else le
                    parts = mm[ls:le].split()
                    if len(parts) >= 5 and parts[0] == b"1":
                        best = ls if best is None else min(best, ls)
                        break
                    probe = nxt + 1
            return best

        with open(path, "rb") as handle:
            mm = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                start = line_end = None
                pos = mm.find(target)
                while pos != -1:
                    ls = mm.rfind(b"\n", 0, pos) + 1
                    le = mm.find(b"\n", pos)
                    le = mm.size() if le == -1 else le
                    parts = mm[ls:le].split()
                    if (len(parts) >= 5 and parts[0] == b"1"
                            and parts[4].upper() == target):
                        start, line_end = ls, le
                        break
                    pos = mm.find(target, pos + 1)
                if start is None:
                    return load_airport(path, icao)
                end = _next_header(mm, line_end)
                block = mm[start:mm.size() if end is None else end]
            finally:
                mm.close()
        tmp = tempfile.NamedTemporaryFile(mode="wb", suffix=".dat",
                                          delete=False)
        try:
            tmp.write(block)
            tmp.close()
            alt = load_airport(tmp.name, icao)
        finally:
            _os.unlink(tmp.name)
        if alt is None:
            return load_airport(path, icao)
        alt.source_path = path
        return alt
    except Exception:
        return load_airport(path, icao)


def ensure_alt_sources(layout, icao: str, xplane_root: str | None) -> None:
    """Load the DEFAULT (Global Airports) apt.dat as CROSS-REFERENCE
    evidence, when the layout was built from a different pack.

    Why: custom packs sometimes ship a WORSE pavement layout and naming
    than the default airport because the author draws everything with
    DSF objects instead (HECA).  The default's named row-110 polygons
    and taxi-network territory then carry real signal the selected pack
    lacks.  Coverage layers only — the single-spine law (spec §3) is
    untouched.

    Alignment self-discounts: reliability = geometric agreement between
    the alt pavement and the pack's own source pavement, times the alt
    file's informativeness (naming coverage + network richness).  A
    stale or offset default layout scores itself down; "there won't be
    perfect alignment" is priced in rather than assumed away.
    """
    if getattr(layout, "_pavement_score_alt_done", False):
        return
    layout._pavement_score_alt_done = True
    layout._pavement_score_alt_rel = 0.0
    if not xplane_root or not icao:
        return
    ss = score_sources(layout)
    try:
        from shapely.ops import transform as shp_transform
        from .apt_dat_reader import find_all_airport_apt_dats
        selected = getattr(layout, "apt_dat_path", None) or ""
        candidates = [p for p in
                      (find_all_airport_apt_dats(xplane_root, icao) or [])
                      if p and p != selected]
        # Prefer the default Global Airports file — that is the whole
        # point of the cross-reference; fall back to any other pack.
        candidates.sort(key=lambda p: 0 if "global airport" in p.lower()
                        else 1)
        alt = None
        for path in candidates:
            alt = _load_alt_airport(path, icao)
            if alt is not None and (alt.pavements or alt.taxi_edges):
                break
            alt = None
        if alt is None:
            return
        ll_to_m = layout.ll_to_m
        to_m = (lambda lon, lat, z=None: ll_to_m(lat, lon))
        apron_p, taxi_p, service_p, all_p = [], [], [], []
        named_area = total_area = 0.0
        for pav in alt.pavements:
            if pav.polygon is None or pav.polygon.is_empty:
                continue
            try:
                pm = shp_transform(to_m, pav.polygon)
            except _GEOM_EXC:
                continue
            for piece in getattr(pm, "geoms", [pm]):
                if piece.geom_type != "Polygon" or piece.is_empty:
                    continue
                total_area += piece.area
                all_p.append(piece)
                bucket = _name_bucket(pav.name)
                if bucket is None:
                    continue
                named_area += piece.area
                (apron_p if bucket == "apron" else
                 taxi_p if bucket == "taxi" else service_p).append(piece)
        # Taxi-network territory: buffered 1202 edges (kind != runway).
        net_parts, net_len = [], 0.0
        nodes = alt.taxi_nodes
        from shapely.geometry import LineString
        for edge in alt.taxi_edges:
            if edge.kind == "runway":
                continue
            a, b = nodes.get(edge.node_from), nodes.get(edge.node_to)
            if a is None or b is None:
                continue
            try:
                line = LineString([ll_to_m(a.lat, a.lon),
                                   ll_to_m(b.lat, b.lon)])
            except _GEOM_EXC:
                continue
            if line.length < 0.5:
                continue
            net_len += line.length
            net_parts.append(line.buffer(PAVEMENT_SCORE_SPINE_BUFFER_M))
        # Reliability: alignment × informativeness.
        source_union = getattr(layout, "source_pavement_union", None)
        alignment = 0.0
        if source_union is not None and total_area > 0.0:
            try:
                alt_union = unary_union(all_p)
                alignment = _clamp01(
                    alt_union.intersection(source_union).area / total_area)
            except _GEOM_EXC:
                alignment = 0.0
        elif total_area == 0.0 and net_len > 0.0:
            alignment = 0.5      # network-only alt file: half trust
        knobs = PAVEMENT_SCORE_RELIABILITY
        informativeness = 0.5 * _clamp01(
            named_area / total_area if total_area > 0.0 else 0.0) \
            + 0.5 * _clamp01(net_len / knobs["spine_len_m"])
        layout._pavement_score_alt_rel = alignment * informativeness
        ss.alt_name_apron = _cover_index(apron_p)
        ss.alt_name_taxi = _cover_index(taxi_p)
        ss.alt_name_service = _cover_index(service_p)
        ss.alt_taxi_territory = _cover_index(net_parts)
        ss.alt_path = alt.source_path or ""
        # Reliability may already be memoized without the alt factor.
        cached_rel = getattr(layout, "_pavement_score_reliability", None)
        if cached_rel is not None:
            cached_rel.alt_apt = layout._pavement_score_alt_rel
    except Exception:
        # Cross-reference is strictly additive evidence — a failure to
        # load it must never break the build.
        layout._pavement_score_alt_rel = 0.0


# ═════════════════════════════════════════════════════════════════════
# Runway touch-chain (the legacy connectivity law, computed here so the
# scorer never reads the legacy passes' conclusions)
# ═════════════════════════════════════════════════════════════════════

_CHAIN_ROLES = frozenset({
    ROLE_RUNWAY, ROLE_RUNWAY_CROSSING, ROLE_PRIMARY_PARALLEL,
    ROLE_SECONDARY_PARALLEL, ROLE_STUB, ROLE_CROSS_CONNECTOR,
    ROLE_JUNCTION, ROLE_APRON,
})
_TOUCH_TOL_M = 0.05          # legacy touch tolerance
_TOUCH_MIN_SHARED_M = 1.0    # point contact does not carry aircraft


_ROUTE_TOUCH_TOL_M = 2.0     # authored 1201/1202 network touch distance
_ZONE_UNSET = object()       # sentinel: "compute the zone here"


def _reach_zone(layout) -> tuple | None:
    """The taxiable core: ``(reach, spine, half)``, or None when inert.

    Owner ruling 2026-07-28 (CYXY #104): groundside "is determined
    based on the ability of aircraft to reach it … no pavement
    connections wide enough for an aircraft to access it without
    hitting a building".  A link is therefore not any shared edge — the
    aircraft must FIT: the aircraft-role pavement union, minus building
    pads, is eroded by half ``PAVEMENT_SCORE_AIRCRAFT_PATH_WIDTH_M``;
    the eroded components touching a runway are the taxiable core
    (``reach``).  Narrow necks and building pinches break the core
    exactly where an aircraft cannot pass.  ``spine`` is the AUTHORED
    1201/1202 non-service network (or None) — route-touch trumps the
    erosion (see ``runway_connectivity``).  Returns None when the
    airport has no ``ROLE_BUILDING`` (the legacy terminal-less guard:
    no terminal ⇒ no landside ⇒ inert), no runways, or no core.

    Shared by ``runway_connectivity`` and ``sever_unreachable`` —
    severance cuts partition member polygons without changing their
    union, so a zone computed before the cut stays valid after it.
    """
    if not any(s.role == ROLE_BUILDING for s in layout.shapes):
        return None
    members = [s for s in layout.shapes
               if s.role in _CHAIN_ROLES
               and s.polygon is not None and not s.polygon.is_empty]
    if not members:
        return None
    half = 0.5 * PAVEMENT_SCORE_AIRCRAFT_PATH_WIDTH_M
    runway_polys = [s.polygon for s in members
                    if s.role in (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING)]
    if not runway_polys:
        return None
    try:
        pav = unary_union([s.polygon for s in members])
        buildings = [s.polygon for s in layout.shapes
                     if s.role == ROLE_BUILDING
                     and s.polygon is not None
                     and not s.polygon.is_empty]
        if buildings:
            # Buildings block with WINGTIP clearance, not just their
            # footprint (owner: "without HITTING a building") — a strip
            # of pavement squeezing past a hangar wall is not an
            # aircraft path even when the gear fits.
            from .config import PAVEMENT_SCORE_BUILDING_CLEARANCE_M
            pav = pav.difference(unary_union(buildings).buffer(
                PAVEMENT_SCORE_BUILDING_CLEARANCE_M))
        core = pav.buffer(-half)
        if core.is_empty:
            return None
        reachable = [c for c in getattr(core, "geoms", [core])
                     if any(c.intersects(r) for r in runway_polys)]
        if not reachable:
            return None
        reach = unary_union(reachable)
    except _GEOM_EXC:
        return None
    # The authored taxi ROUTE trumps the erosion (owner 2026-07-28,
    # CYXY 223/224: "direct taxiway connection … apron, not
    # groundside"; the original #104 ruling was "no taxi routes TOUCH
    # it" — route-touch is itself proof of reachability).  A narrow but
    # routed link is an aircraft path; the erosion only decides for
    # pavement the network does not vouch for.  STRICTLY the AUTHORED
    # 1201/1202 network: the derived centerlines union also carries
    # synthetic gap-fill/junction spines, and those re-connected the
    # CYXY lot the owner ruled unreachable.
    spine = None
    routed = [getattr(cl, "line", None)
              for cl in (getattr(layout, "apt_taxi_centerlines", None)
                         or [])
              if not getattr(cl, "is_service", False)]
    # Ramp lead-ins trimmed from the slicing spine are still AUTHORED
    # aircraft routes — they vouch for reachability (owner 2026-07-28,
    # CYXY building2: the trimmed hangar-face route left real taxi
    # frontage reading unreachable).
    routed += [getattr(cl, "line", None)
               for cl in (getattr(layout, "apt_taxi_leadin_centerlines",
                                  None) or [])
               if not getattr(cl, "is_service", False)]
    routed = [ln for ln in routed if ln is not None and not ln.is_empty]
    if routed:
        try:
            spine = unary_union(routed)
        except _GEOM_EXC:
            spine = None
    return reach, spine, half


def runway_connectivity(layout, zone=_ZONE_UNSET) -> dict[int, bool]:
    """``id(shape) → aircraft-REACHABLE-from-a-runway``.

    The reachability law lives in ``_reach_zone`` (erosion-based core +
    authored-route touch); this applies it per shape: a shape is
    connected iff it lies within half an aircraft-path width of the
    taxiable core (an aircraft on the core can enter it) or touches the
    authored taxi network.  Returns {} when the zone is inert (no
    terminal, no runways, no core).  Pass a precomputed ``zone`` (from
    ``_reach_zone``) to skip recomputing the erosion.
    """
    if zone is _ZONE_UNSET:
        zone = _reach_zone(layout)
    if zone is None:
        return {}
    reach, spine, half = zone
    members = [s for s in layout.shapes
               if s.role in _CHAIN_ROLES
               and s.polygon is not None and not s.polygon.is_empty]
    out: dict[int, bool] = {}
    for s in members:
        if s.role in (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING):
            out[id(s)] = True
            continue
        try:
            connected = s.polygon.distance(reach) <= half + _TOUCH_TOL_M
            if not connected and spine is not None:
                connected = spine.distance(s.polygon) <= _ROUTE_TOUCH_TOL_M
            out[id(s)] = connected
        except _GEOM_EXC:
            out[id(s)] = True      # unmeasurable must never demote
    # SHADOW-BAND second chance (owner CYXY building2/4, 2026-07-28):
    # a shape failing the erosion is still connected when it shares a
    # LONG edge (≥ PAVEMENT_SCORE_SEVER_PINCH_MAX_M) with a connected
    # shape — it is that surface's building-clearance edge band, not a
    # separate lot (aircraft stand on it from the open side).  A
    # genuine landside lot meets airside over a pinch far shorter than
    # the bar (CYXY #104: 11-13 m), and a lot with a long OPEN border
    # is already connected by the erosion itself — only
    # clearance-shadowed frontage gains here.  Measured against the
    # first-pass verdicts only (no chaining through flipped shapes).
    from .config import PAVEMENT_SCORE_SEVER_PINCH_MAX_M
    winners = [s for s in members if out.get(id(s))]
    if winners:
        try:
            connected_union = unary_union(
                [s.polygon for s in winners]).buffer(0.1)
            for s in members:
                if out.get(id(s)):
                    continue
                try:
                    shared = s.polygon.boundary.intersection(
                        connected_union).length
                    if shared >= PAVEMENT_SCORE_SEVER_PINCH_MAX_M:
                        out[id(s)] = True
                except _GEOM_EXC:
                    continue
        except _GEOM_EXC:
            pass
    return out


# ═════════════════════════════════════════════════════════════════════
# Severance — cut landside from airside at the reachability contour
# (owner ruling 2026-07-28, round 4: "we need to sever landside from
# airside so we can classify correctly")
# ═════════════════════════════════════════════════════════════════════

# Only roles whose connectivity the chain computes can straddle the
# contour meaningfully — service shapes are not chain members and score
# with ``connected=None``.
_SEVER_ROLES = frozenset({ROLE_APRON, ROLE_JUNCTION})
# The cut stands off slightly beyond the connectivity threshold: a
# remainder cut exactly AT ``half + _TOUCH_TOL_M`` would sit exactly on
# the ``distance <= half + tol`` boundary and re-score as connected —
# the standoff puts severed pieces decisively past it.
_SEVER_STANDOFF_M = 0.5


def sever_unreachable(layout, zone=_ZONE_UNSET) -> int:
    """Cut shapes that straddle the aircraft-reachability contour.

    ``runway_connectivity`` is whole-shape: one corner within reach of
    the taxiable core marks the entire polygon connected, so a shape
    lying across a building pinch or narrow neck classifies airside
    wholesale even though an aircraft can never pass the pinch (the
    owner's CYXY round-4 cases).  Here the shape is CUT at the contour:
    ``reachable_part = shape ∩ dilate(reach core, half-width)``; every
    unreachable remainder piece at or above
    ``PAVEMENT_SCORE_SEVER_MIN_AREA_M2`` splits off as its own shape.
    Enactment then re-scores each piece against its own connectivity —
    one side airside, one groundside/service.  The cut is purely
    geometric (a distance contour, not tied to route-line ends), so it
    also covers the free-interval scoping edge (service line running
    THROUGH a shape) and widen-cut cases.

    Route-touch (owner, CYXY 223/224: the AUTHORED 1201/1202
    non-service network trumps the erosion) applies PER PIECE: a
    remainder piece the authored network touches would re-score
    connected anyway, so severing it would buy nothing but a seam — it
    stays welded to the reachable side.  A piece the network does not
    vouch for is severed and scores against its own (dis)connectivity.

    Pure geometry: pieces keep the parent role, ref, and the
    already-kept-pavement protection flags; sub-threshold unreachable
    slivers stay welded to the reachable side (no dropped coverage).
    Returns the number of shapes cut.
    """
    from .config import PAVEMENT_SCORE_SEVER_MIN_AREA_M2
    if zone is _ZONE_UNSET:
        zone = _reach_zone(layout)
    if zone is None:
        return 0
    reach, spine, half = zone
    try:
        # Mitre joins keep the cut boundary arc-free (same reason as the
        # apron route-proximity cut).  A mitre buffer covers at least
        # the true distance contour, so everything OUTSIDE ``access`` is
        # strictly beyond the connectivity threshold.
        access = reach.buffer(half + _TOUCH_TOL_M + _SEVER_STANDOFF_M,
                              join_style=2)
        # SHADOW-BAND extension (owner CYXY building2, 2026-07-28): the
        # clearance shadow of a building pushes the core back by up to
        # clearance + half-width, so frontage hugging a CONNECTED
        # NEIGHBOUR reads unreachable even though aircraft stand on it
        # from the open side.  Per straddler, the reachable side of the
        # cut extends by that band around OTHER connected shapes (never
        # the shape's own polygon — self-banding would swallow every
        # lobe) — the cut then lands at the true pinch (the building
        # corner), and the frontage strip stays with (or re-scores as)
        # airside via the shadow-band second chance in
        # ``runway_connectivity``.
        from .config import PAVEMENT_SCORE_BUILDING_CLEARANCE_M
        conn = runway_connectivity(layout, zone)
        shadow_band_m = PAVEMENT_SCORE_BUILDING_CLEARANCE_M + half
        winner_polys = [(id(s), s.polygon) for s in layout.shapes
                        if conn.get(id(s)) and s.polygon is not None
                        and not s.polygon.is_empty]
    except _GEOM_EXC:
        return 0

    def _access_for(shape):
        """Base access plus the shadow band of connected NEIGHBOURS."""
        try:
            near = [p for sid, p in winner_polys
                    if sid != id(shape)
                    and p.distance(shape.polygon) <= shadow_band_m]
            if not near:
                return access
            return access.union(unary_union(near).buffer(
                shadow_band_m, join_style=2))
        except _GEOM_EXC:
            return access
    from shapely.prepared import prep
    covered = prep(access)
    # Building footprints (bare walls + a hair, NOT wingtip clearance)
    # — hard blockers for the route-vouch frontage flood.
    building_pads = None
    try:
        pads = [s.polygon for s in layout.shapes
                if s.role == ROLE_BUILDING and s.polygon is not None
                and not s.polygon.is_empty]
        if pads:
            building_pads = unary_union(pads).buffer(0.5, join_style=2)
    except _GEOM_EXC:
        building_pads = None
    # A cut needs a scoreable reachable side AND a splittable remainder.
    min_parent = PAVEMENT_SCORE_MIN_AREA_M2 + PAVEMENT_SCORE_SEVER_MIN_AREA_M2
    new_shapes: list = []
    n_cut = 0
    for s in layout.shapes:
        poly = s.polygon
        if (s.role not in _SEVER_ROLES or poly is None or poly.is_empty
                or poly.geom_type != "Polygon"
                or poly.area < min_parent):
            new_shapes.append(s)
            continue
        try:
            if covered.covers(poly):        # fully reachable — common case
                new_shapes.append(s)
                continue
            unreach = poly.difference(_access_for(s))
            raw_pieces = [
                g for g in getattr(unreach, "geoms", [unreach])
                if g.geom_type == "Polygon"
                and g.area >= PAVEMENT_SCORE_SEVER_MIN_AREA_M2]
            remainder = []
            for g in raw_pieces:
                if (spine is None
                        or spine.distance(g) > _ROUTE_TOUCH_TOL_M):
                    remainder.append(g)
                    continue
                # ROUTE-VOUCHED PART (owner rulings 2026-07-28): the
                # authored network vouches for the pavement it actually
                # REACHES — the route corridor plus any aircraft-wide
                # region connected to it (CYXY 223/224: a route INTO a
                # wide lot vouches the whole lot).  Pavement beyond a
                # sub-aircraft neck the route never crosses is NOT
                # vouched and severs (CYXY building2: the lot past the
                # 4.8 m corner wrap; the routed frontage strip stays).
                try:
                    seed = g.intersection(
                        spine.buffer(half + _TOUCH_TOL_M))
                    core_g = g.buffer(-half)
                    comps = [c for c in getattr(core_g, "geoms",
                                                [core_g])
                             if not c.is_empty and c.intersects(seed)]
                    vouched = seed
                    if comps:
                        vouched = unary_union(
                            [seed] + [c.buffer(half + _TOUCH_TOL_M,
                                               join_style=2)
                                      for c in comps])
                    # FRONTAGE FLOOD (owner refinement 2026-07-28,
                    # building2: "the entire airside facia of the
                    # building should be welded smoothly to airside
                    # pavement").  The vouched region extends along
                    # building faces through vehicle-width channels
                    # (building footprints as hard blockers); the
                    # flood dies at a sub-width neck, so the cut lands
                    # at the narrowest chord off the building corner —
                    # and no groundside sliver survives on the facia.
                    from .config import PAVEMENT_SCORE_SEVER_FRONTAGE_W_M
                    fw = 0.5 * PAVEMENT_SCORE_SEVER_FRONTAGE_W_M
                    dom = (g.difference(building_pads)
                           if building_pads is not None else g)
                    fcore = dom.buffer(-fw)
                    fcomps = [c for c in getattr(fcore, "geoms",
                                                 [fcore])
                              if not c.is_empty
                              and c.intersects(vouched)]
                    if fcomps:
                        vouched = unary_union(
                            [vouched] + [c.buffer(fw + 0.05,
                                                  join_style=2)
                                         for c in fcomps])
                    unvouched = g.difference(vouched)
                except _GEOM_EXC:
                    continue        # unmeasurable: weld whole (legacy)
                for h in getattr(unvouched, "geoms", [unvouched]):
                    if (h.geom_type == "Polygon"
                            and h.area
                            >= PAVEMENT_SCORE_SEVER_MIN_AREA_M2):
                        remainder.append(h)
        except _GEOM_EXC:
            new_shapes.append(s)
            continue
        if not remainder:
            new_shapes.append(s)
            continue
        # SHADOW-BAND vs PINCH test (owner CYXY building4 + building2,
        # 2026-07-28): a remainder that is itself a thin BAND hugging
        # the reachable side over a long interface is the
        # building-clearance shadow of the same surface — aircraft
        # stand on it from the open side ("the pavement around
        # building4 should all be apron"); it stays welded.  A
        # remainder that hangs through a NARROW interface (a true
        # pinch), or that is DEEP behind its interface (a lot, not a
        # band — CYXY #64: 9.5 k m² behind a 274 m frontage), is
        # genuinely landside and severs.
        try:
            from .config import PAVEMENT_SCORE_SEVER_PINCH_MAX_M
            kept0 = poly.difference(unary_union(remainder))
            if not kept0.is_empty:
                band = kept0.buffer(0.1)
                def _is_shadow_band(g):
                    iface = g.boundary.intersection(band).length
                    if iface < PAVEMENT_SCORE_SEVER_PINCH_MAX_M:
                        return False            # true pinch → sever
                    return g.area / iface <= shadow_band_m
                remainder = [g for g in remainder
                             if not _is_shadow_band(g)]
        except _GEOM_EXC:
            new_shapes.append(s)
            continue
        if not remainder:
            new_shapes.append(s)
            continue
        # Subtract only the KEPT remainder pieces from the parent, so
        # sub-threshold unreachable slivers stay with the reachable
        # side instead of vanishing (coverage is preserved).
        try:
            reach_part = poly.difference(unary_union(remainder))
        except _GEOM_EXC:
            new_shapes.append(s)
            continue
        kept = [g for g in getattr(reach_part, "geoms", [reach_part])
                if g.geom_type == "Polygon" and g.area > 1.0]
        if not kept:
            # Nothing reachable survives: the shape is wholly landside
            # and the whole-shape connectivity verdict already handles
            # it — no cut.
            new_shapes.append(s)
            continue
        # Snap piece rings onto the PARENT ring (weld-bucket tolerance,
        # SHARED_VERTEX_TOL_M): a cut vertex landing 0.1-0.4 m from an
        # existing welded corner leaves a near-coincident pair that the
        # downstream weld/clip chain sweeps back and forth across the
        # neighbour's edge, minting lens overlaps it never converges
        # out of (SPJC severed piece, 1.27 m² sliver).  Snapping makes
        # the cut endpoints coincide exactly with canonical vertices;
        # both pieces share the parent reference, so the partition
        # stays a partition.
        from shapely.ops import snap as _snap
        def _weld_to_parent(g):
            try:
                snapped = _snap(g, poly.boundary, 0.5)
                if (snapped.geom_type == "Polygon" and snapped.is_valid
                        and not snapped.is_empty):
                    return snapped
            except _GEOM_EXC:
                pass
            return g
        for g in kept + remainder:
            g = _weld_to_parent(g)
            new_shapes.append(BuiltShape(
                polygon=g, role=s.role, ref=s.ref,
                from_severance_cut=True,
                from_route_proximity_cut=True))
        n_cut += 1
    if n_cut:
        layout.shapes = new_shapes
    return n_cut


def sever_mixed_aeroway(layout) -> int:
    """Cut BIG apron/junction shapes at the mapped-taxiway zone (owner
    axis-A ruling 2026-07-29, HECA mega-apron).

    The slice can weld true aprons and mapped-taxiway corridors into ONE
    shape (HECA: a 1.03M m² apron spanning 3 km of terminal fabric).  A
    whole-shape verdict then paints the corridors with the apron 1 %
    all-pair law, and its SHORT-HOP composition across the interior
    buries the far end (~1 % × 2.9 km ≈ 29 m of lawful rise where the
    real field climbs 40+) — no pair pricing can fix a mis-roled rate.
    Where the aeroway layer maps BOTH classes on one big shape, cut at
    the taxiway zone (taxi cover minus apron/stand cover) so each piece
    scores on its own mapping — ``osm_taxi_major`` then keeps corridor
    pieces at the taxi cap.  Same discipline as ``sever_unreachable``:
    the cut partitions the polygon (no dropped coverage), pieces keep
    the parent role/ref, sub-floor slivers stay welded to the parent
    side, and piece rings are snapped onto the parent ring so the weld
    chain sees canonical vertices.  Returns the number of shapes cut.
    """
    if _os.environ.get("O4_PAVEMENT_SEVER_AEROWAY", "1") != "1":
        return 0
    from .pavement_classification import evidence_sources
    ev = evidence_sources(layout)
    if not ev.osm_taxi.parts or not (ev.osm_apron.parts
                                     or ev.osm_stand.parts):
        return 0            # distinction not expressed at this airport
    try:
        taxi_u = unary_union(ev.osm_taxi.parts)
        apron_u = unary_union(list(ev.osm_apron.parts)
                              + list(ev.osm_stand.parts))
        taxi_zone = taxi_u.difference(apron_u)
        if taxi_zone.is_empty:
            return 0
    except _GEOM_EXC:
        return 0
    from shapely.ops import snap as _snap
    frac = PAVEMENT_SCORE_AEROWAY_SEVER_MIX_FRAC
    n_cut = 0
    new_shapes: list = []
    for s in layout.shapes:
        poly = s.polygon
        if (s.role not in (ROLE_APRON, ROLE_JUNCTION) or poly is None
                or poly.is_empty or poly.geom_type != "Polygon"
                or poly.area < PAVEMENT_SCORE_AEROWAY_SEVER_MIN_M2):
            new_shapes.append(s)
            continue
        t_frac = ev.osm_taxi.cover_fraction(poly)
        a_frac = max(ev.osm_apron.cover_fraction(poly),
                     ev.osm_stand.cover_fraction(poly))
        if t_frac < frac or a_frac < frac:
            new_shapes.append(s)
            continue
        try:
            inside = poly.intersection(taxi_zone)
        except _GEOM_EXC:
            new_shapes.append(s)
            continue
        kept_taxi = [g for g in getattr(inside, "geoms", [inside])
                     if g.geom_type == "Polygon"
                     and g.area >= PAVEMENT_SCORE_AEROWAY_PIECE_MIN_M2]
        if not kept_taxi:
            new_shapes.append(s)
            continue
        try:
            rest = poly.difference(unary_union(kept_taxi))
        except _GEOM_EXC:
            new_shapes.append(s)
            continue
        rest_polys = [g for g in getattr(rest, "geoms", [rest])
                      if g.geom_type == "Polygon" and g.area > 1.0]
        if not rest_polys:
            new_shapes.append(s)
            continue

        def _weld(g):
            try:
                snapped = _snap(g, poly.boundary, 0.5)
                if (snapped.geom_type == "Polygon" and snapped.is_valid
                        and not snapped.is_empty):
                    return snapped
            except _GEOM_EXC:
                pass
            return g

        for g in kept_taxi + rest_polys:
            new_shapes.append(BuiltShape(
                polygon=_weld(g), role=s.role, ref=s.ref,
                from_severance_cut=True))
        n_cut += 1
    if n_cut:
        layout.shapes = new_shapes
        layout._pavement_score_abut_unions = None
    return n_cut


# ═════════════════════════════════════════════════════════════════════
# Enclave test — the airside/groundside topology rule
# (owner ruling 2026-07-28: "groundside can never be surrounded by
# airside pavement unless it has a tunnel or bridge service road to
# get out … it's possible to draw a single continuous boundary around
# all airside; ALL airside shapes are on one side of the line, and all
# groundside are on the other"; extended to bare ground 2026-08-07)
#
# THE TEST LIVES IN ``enclaves.py`` NOW — one published REGION set, three
# consumers (this classifier, ``gap_fill``, ``adjacent_ground``).  The
# shape-scoped ring-coverage predicate this module used to carry
# (``_enclosed_by_airside`` + its ``PAVEMENT_SCORE_ENCLAVE_GAP_M``
# tolerance) is RETIRED: it asked whether one shape FILLS the void, so
# it was structurally blind to a void that is 87.6 % bare ground and it
# read 0.0 % coverage for the one shape that was in it.  See
# ``enclaves.enclave_at_point`` and the spec's §1-§2.
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# Abutment layers — the standing free-road law + the building ruling
# ═════════════════════════════════════════════════════════════════════

# SERVICE is gated off a road corridor whose boundary shares at least
# this fraction with apron pavement (standing law: "any portion of a
# defined service road running along the edge of, or through an apron,
# becomes apron" — one full flank of a two-sided corridor ≈ 0.45).
PAVEMENT_SCORE_APRON_EDGE_FRAC = 0.4
# A building abutment counts from this much shared edge.
_BUILDING_ABUT_MIN_M = 5.0
# SERVICE-ADJACENCY (owner lateral-contiguity ruling 2026-08-02,
# classification corollary): "road-width pavement sharing an edge with a
# service-road spine is SERVICE ROAD, never groundside".  A SUBSTANTIAL
# shared boundary is the discriminator: an end-connection (one road face
# meeting the next along the same road) shares only a MOUTH — at most a
# road width — while a road running ALONGSIDE the service network shares a
# long flank.  Either bar qualifies: an absolute length (a mouth cannot
# reach it) or a fraction of the perimeter (a short stub whose whole flank
# is the shared edge).
_SERVICE_ADJ_MIN_M = 20.0
_SERVICE_ADJ_MIN_FRAC = 0.20


def _abutment_index(layout):
    """Memoized ``(apron_tree, apron_polys, apron_ids, bld_union, …)``.

    The apron side is an STRtree with owner ids so a shape never
    counts its OWN polygon as an apron edge; the building/terminal
    side is one buffered union (buildings are never scored).  The
    SERVICE layer is the same shape as the apron one (tree + owner ids)
    and feeds the ``service_adj`` feature.  Roles are read at memo time
    — enact and shadow each clear the memo on entry so the layers track
    the current classification.
    """
    cached = getattr(layout, "_pavement_score_abut_unions", None)
    if cached is not None:
        return cached
    aprons, apron_ids, buildings = [], [], []
    chain, chain_ids = [], []
    service, service_ids = [], []
    for s in layout.shapes:
        p = s.polygon
        if p is None or p.is_empty:
            continue
        if s.role == ROLE_APRON:
            aprons.append(p)
            apron_ids.append(id(s))
        elif s.role in (ROLE_BUILDING, "terminal"):
            buildings.append(p)
        if s.role in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION):
            service.append(p)
            service_ids.append(id(s))
        if s.role in _CHAIN_ROLES:
            chain.append(p)
            chain_ids.append(id(s))
    tree = None
    if aprons:
        try:
            from shapely.strtree import STRtree
            tree = STRtree(aprons)
        except _GEOM_EXC:
            tree = None
    bld_u = bld_shadow_u = None
    try:
        if buildings:
            raw = unary_union(buildings)
            bld_u = raw.buffer(0.6)
            # The building's CLEARANCE SHADOW: pavement wholly inside
            # it is disconnected BY the very building it fronts (the
            # erosion subtracts clearance + half a path width) — the
            # G-ABUT airside-face gate must not be defeated by that
            # self-shadowing (owner CYXY hangar strip, 2026-07-28).
            from .config import PAVEMENT_SCORE_BUILDING_CLEARANCE_M
            bld_shadow_u = raw.buffer(
                PAVEMENT_SCORE_BUILDING_CLEARANCE_M
                + 0.5 * PAVEMENT_SCORE_AIRCRAFT_PATH_WIDTH_M,
                join_style=2)
    except _GEOM_EXC:
        bld_u = bld_shadow_u = None
    chain_tree = None
    if chain:
        try:
            from shapely.strtree import STRtree
            chain_tree = STRtree(chain)
        except _GEOM_EXC:
            chain_tree = None
    service_tree = None
    if service:
        try:
            from shapely.strtree import STRtree
            service_tree = STRtree(service)
        except _GEOM_EXC:
            service_tree = None
    layout._pavement_score_abut_unions = (
        tree, aprons, apron_ids, bld_u,
        (chain_tree, chain, chain_ids), bld_shadow_u,
        (service_tree, service, service_ids))
    return layout._pavement_score_abut_unions


def reclass_building_faces(layout) -> int:
    """Late sweep for the building-airside-face ruling (owner
    2026-07-28, SPJC #182): SERVICE shapes minted AFTER enactment (the
    adoption/carve splitters) that share a real edge with a building
    AND with aircraft pavement sit on the building's airside face —
    they become apron ("apron should always abut the airside side of
    buildings").  Service only: groundside verdicts already carry the
    G-CHAIN/enclave reasoning, and a landside lot may legitimately
    share both edges through a pinch.  Returns shapes re-roled.
    """
    layout._pavement_score_abut_unions = None
    try:
        (_t, _p, _i, bld_u, chain_u, _shadow,
         _svc_layer) = _abutment_index(layout)
    except _GEOM_EXC:
        return 0
    if bld_u is None or chain_u is None:
        return 0
    n_flip = 0
    for s in layout.shapes:
        if s.role not in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION):
            continue
        p = s.polygon
        if p is None or p.is_empty or p.geom_type != "Polygon":
            continue
        try:
            if p.distance(bld_u) > 0.0 or p.distance(chain_u) > 0.0:
                continue
            ring = p.exterior
            if (ring.intersection(bld_u).length < _BUILDING_ABUT_MIN_M
                    or ring.intersection(chain_u).length
                    < _BUILDING_ABUT_MIN_M):
                continue
        except _GEOM_EXC:
            continue
        s.role = ROLE_APRON
        s.node_altitudes = None
        s.adopts_apron_grade = False
        n_flip += 1
    return n_flip


# ═════════════════════════════════════════════════════════════════════
# Stage 2 — per-shape features
# ═════════════════════════════════════════════════════════════════════

def _sampled_flank_fraction(polygon, index, owner=None,
                            clear_m: float = 5.0,
                            samples: int = 32) -> float:
    """Sampled stand-in for ``_flank_contact_fraction`` (build budget).

    The exact version unions every neighbour's halo and intersects the
    boundary against it — the #1 per-shape profile cost.  Here the
    exterior is sampled at ``samples`` stations and each station asks
    "is OTHER pavement within ``clear_m``" via ONE bulk ``dwithin``
    STRtree query.  1/32 resolution is ample for a [0,1] evidence
    feature; same clear distance as the legacy flank law (5 m).
    """
    if index is None:
        return 0.0
    tree, polys, owners = index
    skip = None if owner is None else id(owner)
    try:
        boundary = polygon.exterior
        total = boundary.length
        if total <= 0.0:
            return 1.0
        points = [boundary.interpolate((i + 0.5) * total / samples)
                  for i in range(samples)]
        import numpy as _np
        pairs = tree.query(_np.array(points, dtype=object),
                           predicate="dwithin", distance=clear_m)
        hit_stations = {int(pi) for pi, gi in zip(pairs[0], pairs[1])
                        if owners[int(gi)] != skip}
        return len(hit_stations) / float(samples)
    except _GEOM_EXC:
        return 1.0


def _bulk_flank_fractions(polys, index, owners,
                          clear_m: float = 5.0,
                          samples: int = 32) -> list:
    """``_sampled_flank_fraction`` for many shapes via ONE bulk query.

    Same stations, same dwithin predicate, same owner skip — only the
    per-shape query round trips collapse (build budget: the flank
    query was the #2 per-shape cost after cover fractions).
    """
    if index is None:
        return [0.0] * len(polys)
    tree, _parts, owner_ids = index
    results: list = [None] * len(polys)
    points, slots = [], []
    for pi, polygon in enumerate(polys):
        try:
            boundary = polygon.exterior
            total = boundary.length
            if total <= 0.0:
                results[pi] = 1.0
                continue
            stations = [boundary.interpolate((i + 0.5) * total / samples)
                        for i in range(samples)]
        except _GEOM_EXC:
            results[pi] = 1.0
            continue
        for si, point in enumerate(stations):
            slots.append((pi, si))
            points.append(point)
    if points:
        try:
            import numpy as _np
            pairs = tree.query(_np.array(points, dtype=object),
                               predicate="dwithin", distance=clear_m)
            hit_stations: list = [set() for _ in polys]
            for qi, gi in zip(pairs[0], pairs[1]):
                pi, si = slots[int(qi)]
                if owner_ids[int(gi)] != id(owners[pi]):
                    hit_stations[pi].add(si)
            for pi in range(len(polys)):
                if results[pi] is None:
                    results[pi] = len(hit_stations[pi]) / float(samples)
        except _GEOM_EXC:
            pass
    return [1.0 if r is None else r for r in results]


def _thread_fraction(polygon, line_union, index=None) -> float:
    """Fraction of the shape's long axis a layer's centerline threads."""
    if line_union is None:
        return 0.0
    try:
        axis_m = 0.5 * polygon.exterior.length
        if axis_m <= 0.0:
            return 0.0
        return _clamp01(_cut_length(polygon, line_union, index) / axis_m)
    except _GEOM_EXC:
        return 0.0


def shape_features(polygon, layout, *, adjacency=None, owner=None,
                   connected: bool | None = None) -> dict:
    """The raw (un-scaled, un-weighted) feature vector for one polygon."""
    ev = evidence_sources(layout)
    ss = score_sources(layout)
    # ``shadow_classify`` precomputes every cover fraction and the flank
    # via bulk tree queries (one per layer instead of one per shape per
    # layer — the dominant build-budget term); a standalone call takes
    # the identical per-call path.
    rows = getattr(layout, "_pavement_score_feature_rows", None)
    row = rows.get(id(polygon)) if rows is not None else None

    def _cov(key, index):
        return row[key] if row is not None else index.cover_fraction(polygon)

    x: dict[str, float] = {}
    x["name_apron"] = _cov("name_apron", ss.name_apron)
    x["name_taxi"] = _cov("name_taxi", ss.name_taxi)
    x["name_service"] = _cov("name_service", ss.name_service)
    x["unpaved_cover"] = _cov("unpaved_cover", ss.unpaved)
    x["osm_apron"] = _cov("osm_apron", ev.osm_apron)
    x["osm_stand"] = _cov("osm_stand", ev.osm_stand)
    x["osm_taxi"] = _cov("osm_taxi", ev.osm_taxi)
    x["spine_cover"] = _cov("spine_cover", ss.spine_buffers)
    x["truck_cover"] = _cov("truck_cover", ss.truck_corridors)
    x["road_cover"] = _cov("road_cover", ev.road_corridors)
    x["tunnel_cover"] = _cov("tunnel_cover", ev.tunnel_corridors)
    x["parking_cover"] = _cov("parking_cover", ev.parking_corridors)
    x["alt_name_apron"] = _cov("alt_name_apron", ss.alt_name_apron)
    x["alt_name_taxi"] = _cov("alt_name_taxi", ss.alt_name_taxi)
    x["alt_name_service"] = _cov("alt_name_service", ss.alt_name_service)
    x["alt_taxi_cover"] = _cov("alt_taxi_cover", ss.alt_taxi_territory)

    # Morphology — ONE erosion cascade, widest first, each result
    # implying the next test's answer where it can (build-budget: these
    # buffers were the #2 profile cost when run independently).
    # ``wide_blob``: ≥ ~50 m across somewhere; a wide blob trivially
    # fits an aircraft, so the vehicle-opening test is skipped for it.
    # A bbox dimension under the erosion diameter proves the buffer
    # empty without computing it (an inscribed disk of radius r needs
    # 2r in both axes).
    try:
        minx, miny, maxx, maxy = polygon.bounds
        wide = (maxx - minx >= 2.0 * PAVEMENT_SCORE_WIDE_HALF_M
                and maxy - miny >= 2.0 * PAVEMENT_SCORE_WIDE_HALF_M
                and not polygon.buffer(-PAVEMENT_SCORE_WIDE_HALF_M).is_empty)
    except _GEOM_EXC:
        wide = False
    x["wide_blob"] = 1.0 if wide else 0.0
    taxi_corridor = not wide                       # == _is_tail(poly, 25)
    road_corridor = (False if wide else
                     _is_tail(polygon,
                              0.5 * PAVEMENT_CLASS_TAIL_MAX_WIDTH_M))
    x["road_corridor"] = 1.0 if road_corridor else 0.0   # no weight; gate
    # G-APRON-WIDTH (owner ruling 2026-08-10): "the entire shape narrower
    # than a taxiway cannot be apron".  Same cascade: a shape that
    # survived the ROAD erosion (or is wide) trivially survives this far
    # smaller one, so only a road-width corridor pays for the buffer.
    sub_taxi_width = (
        road_corridor
        and _is_tail(polygon, PAVEMENT_SCORE_APRON_MIN_HALF_WIDTH_M))
    x["sub_taxi_width"] = 1.0 if sub_taxi_width else 0.0  # no weight; gate
    if wide:
        x["narrow_only"] = 0.0
    else:
        try:
            # Same bbox proof as above: below the aircraft width the
            # erosion is empty, the opening recovers nothing, and the
            # patch is vehicle-only without running the opening.
            minx, miny, maxx, maxy = polygon.bounds
            if (DSF_OBJECT_PAVEMENT_OPENING_RATIO > 0.0
                    and polygon.area > 0.0
                    and (maxx - minx < DSF_OBJECT_PAVEMENT_MIN_AIRCRAFT_WIDTH_M
                         or maxy - miny
                         < DSF_OBJECT_PAVEMENT_MIN_AIRCRAFT_WIDTH_M)):
                x["narrow_only"] = 1.0
            else:
                from .object_footprints import is_vehicle_pavement_patch
                x["narrow_only"] = 1.0 if is_vehicle_pavement_patch(
                    polygon, DSF_OBJECT_PAVEMENT_MIN_AIRCRAFT_WIDTH_M,
                    DSF_OBJECT_PAVEMENT_OPENING_RATIO) else 0.0
        except _GEOM_EXC:
            x["narrow_only"] = 0.0

    # Threading: corridor-shaped AND the layer's centerline runs most of
    # the long axis.  Road threading is the legacy ``_is_road_corridor``
    # predicate inlined against the precomputed ``road_corridor``.
    spine_thread = (_thread_fraction(polygon, ev.taxi_centerlines,
                                     ss.spine_thread_index)
                    if taxi_corridor else 0.0)
    x["spine_thread"] = (spine_thread
                         if spine_thread >= PAVEMENT_SCORE_THREAD_MIN_FRAC
                         else 0.0)
    truck_thread = (_thread_fraction(polygon, ss.truck_lines,
                                     ss.truck_thread_index)
                    if road_corridor else 0.0)
    x["truck_thread"] = (truck_thread
                         if truck_thread >= PAVEMENT_SCORE_THREAD_MIN_FRAC
                         else 0.0)
    x["road_thread"] = 0.0
    if road_corridor and ev.road_lines is not None:
        try:
            run_m = _cut_length(polygon, ev.road_lines,
                                ss.road_thread_index)
            axis_m = 0.5 * polygon.exterior.length
            if (axis_m > 0.0
                    and run_m >= PAVEMENT_CLASS_TAIL_MIN_LENGTH_M
                    and run_m >= PAVEMENT_CLASS_TAIL_AXIS_ROAD_FRAC
                    * axis_m):
                x["road_thread"] = 1.0
        except _GEOM_EXC:
            pass

    # Owner ruling 2026-07-28: "narrow+road-covered should vote
    # service" — a vehicle-only shape riding a road corridor is a road,
    # not a landside lot, even when it is too short to THREAD.
    x["road_narrow"] = (x["road_cover"]
                        if x["narrow_only"] >= 1.0 else 0.0)

    # NAME×TRUCK suppression (CYXY ground truth 2026-07-28): airport
    # authors name their ROADS "Taxiway" (CYXY "New Taxiway 40" is a
    # service road).  The 1206 truck network is the authoritative
    # vehicles-drive-here signal, so truck coverage discounts the
    # taxi-name prior.  ``name_apron`` is deliberately NOT suppressed —
    # a stand legitimately served by a truck route is still a stand.
    x["name_taxi"] *= (1.0 - x["truck_cover"])

    # TRUCK-OVER-SPINE on road-width corridors (CYXY #45/#46, owner
    # 2026-07-28): a service road runs INSIDE the taxi spine's 25 m
    # halo, so territory coverage cannot tell them apart; on corridor
    # shapes the truck network is the identity signal — it discounts
    # spine territory and votes SERVICE directly.
    if road_corridor:
        x["spine_cover"] *= (1.0 - x["truck_cover"])
        x["truck_corridor"] = x["truck_cover"]
    else:
        x["truck_corridor"] = 0.0

    # MAPPED-TAXIWAY DOMINANCE (owner standing report, HECA burial
    # 2026-07-29: within-fence classification "still terribly
    # inaccurate" — between-terminal junction fabric mapped mostly
    # aeroway=taxiway flipped to APRON on the geometry priors alone,
    # wide_blob + enclosed_by_airside + apron_edge_bound outscoring the
    # actual mapping; the resulting 1 % all-pair caps buried the south
    # terminals under a km-scale pairwise-cap chain).  When the OSM
    # aeroway layer actively maps this shape as taxiway MORE than as
    # apron/stand — and nothing names it an apron — that mapping is
    # direct evidence the geometry priors must not swamp.  Comparative
    # and binary like ``taxi_contact``: the priors keep their votes,
    # the dominant mapping gets a decisive one of its own.  Dominance
    # is only a statement where the mapper EXPRESSED the apron-vs-
    # taxiway distinction: at an airport whose OSM maps no apron/stand
    # at all (CYXY), "taxiway beats apron" is vacuous — any incidental
    # taxiway sliver over an apt.dat apron would fire — so the feature
    # stays inert there (absence of the source is never evidence).
    x["osm_taxi_major"] = 0.0
    if ((ev.osm_apron.parts or ev.osm_stand.parts)
            and x["osm_taxi"] >= PAVEMENT_SCORE_TAXI_MAJOR_MIN
            and x["osm_taxi"] > max(x["osm_apron"], x["osm_stand"],
                                    x["name_apron"])):
        x["osm_taxi_major"] = 1.0

    # Connectivity (already computed airport-wide; None = guard inert).
    if connected is None:
        x["runway_connected"] = 0.0
        x["runway_disconnected"] = 0.0
    else:
        x["runway_connected"] = 1.0 if connected else 0.0
        x["runway_disconnected"] = 0.0 if connected else 1.0

    # Perimeter enclosure vs the rest of the airport's pavement.
    # ``owner`` skips the shape's own entry in the adjacency index —
    # without it every shape reads as fully enclosed by itself.
    flank = (row["_flank"] if row is not None
             else _sampled_flank_fraction(polygon, adjacency, owner=owner))
    x["enclosed_by_airside"] = flank
    x["open_perimeter"] = 1.0 - flank

    # BUILDING-FRONTAGE ruling (owner 2026-07-28, CYXY building4): a
    # narrow strip FULLY flanked by other built shapes, with no road or
    # truck evidence at all, is stand/frontage pavement — nothing says
    # vehicles-only except its width, and width alone must not turn
    # hangar frontage into a road or a landside lot (CYXY #62/#279:
    # SERVICE/GROUNDSIDE tied at 1.5 on narrow_only alone).  The
    # vehicle-only penalty is therefore withdrawn and the strip leans
    # APRON (it grades with what surrounds it).
    x["pavement_frontage"] = 0.0
    if (x["narrow_only"] >= 1.0 and flank >= 0.97
            and x["road_cover"] < 0.05 and x["truck_cover"] < 0.05
            and x["road_thread"] == 0.0 and x["truck_thread"] == 0.0):
        x["narrow_only"] = 0.0
        x["pavement_frontage"] = 1.0

    # Provenance: fraction NOT covered by apt.dat's own polygons.
    if ss.apt_only:
        x["third_party_source"] = 1.0 - _cov("_apt_only_cover", ss.apt_only)
    else:
        x["third_party_source"] = 0.0

    # Abutment (standing free-road law + owner 2026-07-28 building
    # ruling).  ``apron_edge_bound``: fraction of the boundary shared
    # with apron pavement — a road corridor bound to an apron edge is
    # the apron's own surface, not a free road.  ``building_abut``: the
    # shape shares a real edge with a building/terminal; combined with
    # a not-disconnected verdict it marks the building's AIRSIDE face,
    # which apron must abut.  The shape's own entry never
    # self-counts (both unions exclude non-apron/building roles).
    x["apron_edge_bound"] = 0.0
    x["building_abut"] = 0.0
    x["airside_contact"] = 0.0
    x["taxi_contact"] = 0.0
    x["building_shadow"] = 0.0
    x["service_adj"] = 0.0
    try:
        (apron_tree, apron_polys, apron_ids, bld_u,
         chain_layer, bld_shadow_u, service_layer) = _abutment_index(layout)
        boundary = polygon.exterior
        if apron_tree is not None:
            skip = id(owner) if owner is not None else None
            near = [
                int(k) for k in apron_tree.query(
                    polygon, predicate="dwithin", distance=0.6)
                if apron_ids[int(k)] != skip
                and apron_polys[int(k)] is not polygon]
            if near:
                halo = unary_union(
                    [apron_polys[k] for k in near]).buffer(0.6)
                x["apron_edge_bound"] = _clamp01(
                    boundary.intersection(halo).length
                    / max(boundary.length, 1e-9))
        if bld_u is not None and polygon.distance(bld_u) == 0.0:
            if boundary.intersection(bld_u).length >= _BUILDING_ABUT_MIN_M:
                x["building_abut"] = 1.0
        chain_tree, chain_polys, chain_ids = chain_layer
        chain_shared = 0.0
        if chain_tree is not None:
            skip = id(owner) if owner is not None else None
            near_chain = [
                int(k) for k in chain_tree.query(
                    polygon, predicate="dwithin", distance=0.6)
                if chain_ids[int(k)] != skip
                and chain_polys[int(k)] is not polygon]
            if near_chain:
                chain_halo = unary_union(
                    [chain_polys[k] for k in near_chain]).buffer(0.6)
                chain_shared = boundary.intersection(chain_halo).length
        # Aircraft-pavement contact, NEVER self-counted (a chain-role
        # shape must not vouch for itself).  ``taxi_contact`` is the
        # access signal for the taxi-only law (owner 2026-07-28,
        # CYXY #208: "the difference is the service road connections
        # to 104... while 208 has taxiway and no roads").
        if chain_shared >= 3.0:
            x["taxi_contact"] = 1.0
        if x["building_abut"] >= 1.0 and (
                chain_shared >= _BUILDING_ABUT_MIN_M
                or (owner is not None and owner.role in _CHAIN_ROLES)):
            # The face disambiguator: touching aircraft pavement —
            # or BEING aircraft pavement (a chain-role owner is airside
            # by identity) — marks the building's AIRSIDE face; a
            # landside road behind the terminal is neither.
            x["airside_contact"] = 1.0
        if x["building_abut"] >= 1.0 and bld_shadow_u is not None:
            # Fraction of the shape inside the buildings' clearance
            # shadow — near 1.0 means any erosion disconnection is
            # SELF-shadowing by the abutted building (see G-ABUT).
            x["building_shadow"] = _clamp01(
                polygon.intersection(bld_shadow_u).area
                / max(polygon.area, 1e-9))
        # SERVICE-ADJACENCY (owner lateral-contiguity ruling 2026-08-02,
        # classification corollary): road-width pavement sharing a
        # SUBSTANTIAL boundary with the service-road network is a service
        # road, never a landside lot.  Restricted to ROAD-WIDTH shapes
        # (the same ``road_corridor`` predicate G-FREE-ROAD gates SERVICE
        # on — the free-road width semantics, one source) so a wide lot
        # that merely fronts a road never qualifies, and to a shared edge
        # no MOUTH could reach (see ``_SERVICE_ADJ_MIN_M``), so a road's
        # own end-connections never vote for it.  The shape's own entry
        # never self-counts.
        if (SCORER_SERVICE_ADJ and road_corridor
                and service_layer[0] is not None):
            svc_tree, svc_polys, svc_ids = service_layer
            skip = id(owner) if owner is not None else None
            near_svc = [
                int(k) for k in svc_tree.query(
                    polygon, predicate="dwithin", distance=0.6)
                if svc_ids[int(k)] != skip
                and svc_polys[int(k)] is not polygon]
            if near_svc:
                svc_halo = unary_union(
                    [svc_polys[k] for k in near_svc]).buffer(0.6)
                shared_m = boundary.intersection(svc_halo).length
                per = max(boundary.length, 1e-9)
                if (shared_m >= _SERVICE_ADJ_MIN_M
                        or shared_m / per >= _SERVICE_ADJ_MIN_FRAC):
                    x["service_adj"] = 1.0
    except _GEOM_EXC:
        pass

    # RUNWAY CONTACT (owner ruling 2026-08-10: "pavement touching a
    # runway cannot be apron").  Measured as SHARED PERIMETER against
    # the runway ring — the same "either bar qualifies" shape as
    # ``service_adj``: an absolute length, or a fraction of the
    # candidate's OWN perimeter.  0.0 when the airport publishes no
    # runway union (absence of the source is never evidence), which
    # leaves G-RUNWAY-CONTACT inert.
    x["runway_contact"] = 0.0                       # no weight; gate
    halo = ss.runway_edge_halo
    if halo is not None:
        try:
            boundary = polygon.exterior
            if boundary.intersects(halo):
                shared_m = boundary.intersection(halo).length
                per = max(boundary.length, 1e-9)
                if (shared_m >= PAVEMENT_SCORE_RUNWAY_CONTACT_MIN_M
                        or shared_m / per
                        >= PAVEMENT_SCORE_RUNWAY_CONTACT_MIN_FRAC):
                    x["runway_contact"] = 1.0
        except _GEOM_EXC:
            pass

    # Fraction of the shape OUTSIDE the OSM aerodrome boundary (owner
    # ruling 2026-07-28, G-BOUNDARY: airside never exists outside it).
    # 0.0 whenever no aerodrome polygon is mapped — absence of the
    # source is never evidence.  Prepared-covers fast path: nearly all
    # shapes are fully inside and never pay for the intersection.
    x["outside_boundary"] = 0.0
    if ss.aerodrome is not None:
        try:
            if not ss.aerodrome_prep.covers(polygon):
                inside = polygon.intersection(ss.aerodrome).area
                x["outside_boundary"] = _clamp01(
                    1.0 - inside / max(polygon.area, 1e-9))
        except _GEOM_EXC:
            pass
    return x


# ═════════════════════════════════════════════════════════════════════
# Stages 3+4 — gates, argmax, confidence
# ═════════════════════════════════════════════════════════════════════

# G-APRON-AIRSIDE (owner ruling 2026-08-11b, RULINGS c366c13): the
# AIRSIDE-CONTACT features — the exact set the KMCI shapeID 995
# adjudication enumerated, spelled with the production feature
# registry's own names.  Each one is a statement that AIRCRAFT reach
# this shape: the airport's own name for it (``name_apron``), the
# mapper's apron/stand tagging (``osm_apron`` / ``osm_stand``), an
# aircraft touch-chain to a runway (``runway_connected``), a
# building's airside face (``airside_contact``), or a shared edge with
# aircraft pavement (``taxi_contact``).  Nothing is invented here and
# nothing is added: a feature outside this list may still SCORE apron,
# it just cannot open the gate.
_AIRSIDE_CONTACT_FEATURES = (
    "name_apron", "osm_apron", "osm_stand",
    "runway_connected", "airside_contact", "taxi_contact",
)

def score_shape(polygon, layout, *, adjacency=None, owner=None,
                connected: bool | None = None,
                legacy_class: str | None = None,
                enclosed: bool | None = None) -> dict:
    """Score one polygon: features → points → gates → verdict.

    ``enclosed=True`` fires G-ENCLAVE (owner ruling 2026-07-28:
    groundside can never be fully surrounded by airside pavement
    without a tunnel/bridge escape) — GROUNDSIDE is removed from the
    candidates.  The caller decides enclosure (it needs the settled
    airport-wide roles); pass None to leave the gate inert.

    Returns a decision record (all floats rounded for the log):
    ``features``, ``scores``, ``gates``, ``candidates``, ``winner``,
    ``margin``, ``band``, ``legacy``, ``final`` — where ``final`` applies
    the development ruling (LOW band ⇒ legacy verdict when available).
    """
    rel = source_reliability(layout)
    x = shape_features(polygon, layout, adjacency=adjacency, owner=owner,
                       connected=connected)
    if enclosed:
        # Topologically locked inside airside: the enclave defaults
        # toward the apron law (it grades with its surroundings).
        x["airside_enclave"] = 1.0
    scores = {c: 0.0 for c in CLASSES}
    for feature, value in x.items():
        if value == 0.0:
            continue
        weights = PAVEMENT_SCORE_WEIGHTS.get(feature)
        if not weights:
            continue
        r = rel.of(feature)
        if r <= 0.0:
            continue
        for cls, points in weights.items():
            scores[cls] += points * r * value

    # Hard gates — owner law (spec §7).  Gates REMOVE candidates.
    gates: list[str] = []
    candidates = set(CLASSES)
    road_corridor = x.get("road_corridor", 0.0) >= 1.0
    if not road_corridor:
        # G-FREE-ROAD + wide-residue ruling: only road-width corridors
        # may grade as service roads.
        candidates.discard(CLASS_SERVICE)
        gates.append("G-FREE-ROAD")
    elif x.get("tunnel_cover", 0.0) >= PAVEMENT_SCORE_TUNNEL_VETO_FRAC:
        # G-TUNNEL-ROAD (owner 2026-08-10): "tunneled roads are not
        # surface roads".  A corridor painted over a BORE is not a free
        # surface road — the road it traces runs below our pavement, so
        # SERVICE is off the table (OTHH sid103, a 2.5 m ribbon over the
        # mapped tunnel pair -9169/-9170).  The below-grade ways are
        # already out of the SURFACE feed, so the shape carries no
        # road_cover of its own to argue with.
        candidates.discard(CLASS_SERVICE)
        gates.append("G-TUNNEL-ROAD")
    elif x.get("apron_edge_bound", 0.0) >= PAVEMENT_SCORE_APRON_EDGE_FRAC:
        # Standing free-road law (owner, canonical text in
        # groundside.free_road_subsegments; restated 2026-07-28): "any
        # portion of a defined service road running along the edge of,
        # or through an apron, becomes apron" — an apron-bound corridor
        # is not a FREE road, so SERVICE is off the table.
        candidates.discard(CLASS_SERVICE)
        gates.append("G-APRON-EDGE")
    abut_fired = (
        x.get("building_abut", 0.0) >= 1.0
        and x.get("airside_contact", 0.0) >= 1.0
        and (connected is not False
             or x.get("building_shadow", 0.0) >= 0.95
             # Owner CYXY #178 (round 9): a building-fronting shape
             # SUBSTANTIALLY WRAPPED by apron edges is that apron's own
             # frontage even when the erosion cannot reach it — the
             # #104 lot touches airside only over its pinch, far below
             # this bar.
             or x.get("apron_edge_bound", 0.0)
             >= PAVEMENT_SCORE_APRON_EDGE_FRAC))
    if abut_fired:
        # Owner ruling 2026-07-28 (SPJC): "apron should always abut the
        # airside side of buildings" — building-face pavement on the
        # aircraft side (it also touches aircraft pavement) is
        # stand/frontage surface, never a road or a landside lot.  A
        # landside road behind the terminal touches no aircraft
        # pavement and keeps its candidates.  A DISCONNECTED shape
        # still gates when it lies wholly inside the buildings'
        # clearance shadow — its disconnection is self-shadowing by
        # the very building it fronts (CYXY hangar strip); a real
        # landside lot extends far beyond the shadow and keeps the
        # connectivity guard (#104).
        candidates -= {CLASS_SERVICE, CLASS_GROUNDSIDE}
        gates.append("G-ABUT")
    # G-VETO (R-VETO): the owner's ruling protects APRONS — "a road
    # inside, or sharing an edge with a real apron must follow the
    # apron's grade".  So: APRON-flavored evidence blocks the LANDSIDE
    # demotion only.  It must NOT block SERVICE (TAXI-vs-SERVICE is a
    # scores question — CYXY ground truth 2026-07-28: taxi-line/name
    # evidence vetoing SERVICE flipped true service roads 42/43/166 to
    # TAXI even though SERVICE outscored TAXI 2-3×), and taxi names/
    # lines are not apron evidence.
    apron_evidence = max(x["osm_apron"], x["osm_stand"], x["name_apron"])
    if apron_evidence >= PAVEMENT_SCORE_VETO_FRAC:
        candidates.discard(CLASS_GROUNDSIDE)
        gates.append("G-VETO")
    runway_contact = x.get("runway_contact", 0.0) >= 1.0
    if runway_contact:
        # G-RUNWAY-CONTACT (owner ruling 2026-08-10, verbatim):
        # "Pavement touching a runway cannot be apron".  A runway is
        # never bounded by aircraft PARKING — what abuts it is the
        # maneuvering surface that feeds it, so the shape falls to
        # junction/taxiway under the existing enactment.  The legacy
        # near-runway apron rule said the same thing and is dead under
        # v2 (``pipeline`` gates it behind ``_scorer_owns_roles``);
        # this is its v2 rebirth.  Specimen: OTHH sid102, 376 m², 51 %
        # of its perimeter on the runway.
        candidates.discard(CLASS_APRON)
        gates.append("G-RUNWAY-CONTACT")
    sub_taxi_width = x.get("sub_taxi_width", 0.0) >= 1.0
    if sub_taxi_width:
        # G-APRON-WIDTH (owner ruling 2026-08-10, verbatim): "the
        # entire shape narrower than a taxiway cannot be apron".  No
        # aircraft can stand on a ribbon that vanishes under a 2 m
        # erosion.  Specimens: OTHH sid105 (4.1 m OBB width), sid104
        # (2.4 m).
        candidates.discard(CLASS_APRON)
        gates.append("G-APRON-WIDTH")
    # G-APRON-AIRSIDE (owner ruling 2026-08-11b, verbatim intent):
    # "``wide_blob`` may MAGNIFY but never AUTHOR apron absent at least
    # one airside-contact feature".  A shape may be APRON only if at
    # least one of ``_AIRSIDE_CONTACT_FEATURES`` is positive.  "Large
    # paved blob" is not evidence of airside use — every big car park is
    # a large paved blob, and at KMCI two of them (idx 139 / 1052,
    # 36.6k and 53.2k m² of landside terminal-frontage parking) were
    # promoted GROUNDSIDE → APRON at HIGH margin on ``wide_blob`` 1.0
    # ALONE, with every airside feature reading zero.
    #
    # THE GATE IS STRUCTURAL, NOT A WEIGHT (the ruling's own emphasis):
    # ``wide_blob`` keeps its full weight wherever an airside feature is
    # present, so a real apron's size still magnifies its evidence; what
    # the gate removes is AUTHORSHIP, and no future re-weighting of
    # ``wide_blob`` (or of any other feature) can un-rule it, because
    # the candidate is gone before the argmax ever sees the scores.
    airside_any = any(x.get(f, 0.0) > 0.0
                      for f in _AIRSIDE_CONTACT_FEATURES)
    if not airside_any:
        candidates.discard(CLASS_APRON)
        gates.append("G-APRON-AIRSIDE")
    if connected is False:
        # G-CHAIN: no aircraft touch-chain to a runway (terminal guard
        # already applied — ``connected`` is None when the guard bites).
        candidates -= {CLASS_APRON, CLASS_TAXI}
        gates.append("G-CHAIN")
    if enclosed:
        # G-ENCLAVE (owner 2026-07-28): "groundside can never be
        # surrounded by airside pavement unless it has a tunnel or
        # bridge service road to get out" — a fully-surrounded shape
        # with no escape cannot be groundside.
        candidates.discard(CLASS_GROUNDSIDE)
        gates.append("G-ENCLAVE")
    taxi_only_fired = (
        x.get("taxi_contact", 0.0) >= 1.0
        and x.get("road_cover", 0.0) < 0.05
        and x.get("truck_cover", 0.0) < 0.05
        and x.get("road_thread", 0.0) == 0.0
        and x.get("truck_thread", 0.0) == 0.0)
    if taxi_only_fired:
        # G-TAXI-ONLY (owner ruling 2026-07-28, CYXY #208 vs #104):
        # access type decides — pavement whose only connection is
        # TAXIWAY pavement, with zero road/truck evidence, is airside
        # ("208 has taxiway and no roads"); the #104 lot carries its
        # service-road connections and keeps its landside candidates.
        # Fires regardless of the erosion (the whole point: aircraft
        # pavement serves it, vehicles have no way in).
        candidates -= {CLASS_SERVICE, CLASS_GROUNDSIDE}
        gates.append("G-TAXI-ONLY")
    if not candidates:
        # The gates contradicted each other (e.g. OSM says apron, the
        # chain says unreachable).  The law gives no answer — fall back
        # to scores over ALL classes and flag it.  An enclave still
        # cannot be groundside, an airside building face still cannot
        # be a road or a lot, and taxi-only-access pavement stays
        # airside (all topological rules are absolute — they resolve
        # against G-CHAIN, not the other way).  The two 2026-08-10
        # apron gates are absolute in the same sense: they are
        # statements about what the shape IS (it touches the runway; no
        # aircraft fits on it), not about which evidence outweighs
        # which.  G-APRON-AIRSIDE is absolute in that same sense (no
        # airside feature is positive — nothing says aircraft reach
        # it), and it can only ever REMOVE apron, so it never empties
        # the reset.  {TAXI} always survives, so the reset never
        # re-empties.
        candidates = set(CLASSES)
        if enclosed:
            candidates.discard(CLASS_GROUNDSIDE)
        if abut_fired or taxi_only_fired:
            candidates -= {CLASS_SERVICE, CLASS_GROUNDSIDE}
        if runway_contact or sub_taxi_width or not airside_any:
            candidates.discard(CLASS_APRON)
        gates.append("G-CONFLICT")
    if x.get("outside_boundary", 0.0) >= PAVEMENT_SCORE_BOUNDARY_OUT_FRAC:
        # G-BOUNDARY (owner 2026-07-28, refined same day): a shape
        # ENTIRELY outside the OSM aerodrome boundary is guaranteed
        # groundside or a road.  A shape merely CROSSING the fence
        # gets no gate — contiguous pavement legitimately spans the
        # boundary (airside apron + outside parking lot) and the rest
        # of the rules decide it; its outside fraction still weighs in
        # as GROUNDSIDE evidence.  The guarantee overrides the other
        # gates, including R-VETO (contradictory OSM data logs both).
        candidates &= {CLASS_GROUNDSIDE, CLASS_SERVICE}
        if not candidates:
            candidates = {CLASS_GROUNDSIDE, CLASS_SERVICE}
        gates.append("G-BOUNDARY")

    # Deterministic tie-break: equal scores rank in CLASSES order
    # (bare set iteration is hash-seed dependent — CYXY #62/#279 tied
    # SERVICE/GROUNDSIDE at 1.5 and flipped between runs).
    _rank = {c: i for i, c in enumerate(CLASSES)}
    ranked = sorted(candidates, key=lambda c: (-scores[c], _rank[c]))
    top = scores[ranked[0]]
    second = scores[ranked[1]] if len(ranked) > 1 else 0.0
    if top <= 0.0:
        winner, margin, band = None, 0.0, "LOW"     # no evidence: no guess
    else:
        winner = ranked[0]
        margin = (top - second) / top
        band = ("HIGH" if margin >= PAVEMENT_SCORE_MARGIN_HIGH
                else "MED" if margin >= PAVEMENT_SCORE_MARGIN_MED
                else "LOW")
    # Development ruling (owner 2026-07-27): LOW margin ⇒ legacy verdict,
    # until the scorer earns the chain's retirement.
    final = winner
    if (band == "LOW" or winner is None) and legacy_class is not None:
        final = legacy_class
    return {
        "features": {k: round(v, 3) for k, v in x.items()},
        "scores": {c: round(s, 3) for c, s in scores.items()},
        "gates": gates,
        "candidates": sorted(candidates),
        "winner": winner,
        "margin": round(margin, 3),
        "band": band,
        "legacy": legacy_class,
        "final": final,
    }


# ═════════════════════════════════════════════════════════════════════
# Shadow pass
# ═════════════════════════════════════════════════════════════════════

def _precompute_feature_rows(layout, candidates, adjacency) -> dict:
    """``id(polygon) → precomputed feature row`` for the shadow loop.

    One bulk STRtree pass per evidence layer plus one for the flank
    stations, instead of per-shape × per-layer queries — the dominant
    build-budget term.  ``shape_features`` reads these rows through
    ``layout._pavement_score_feature_rows``; values match the per-call
    path to the CoverIndex equivalence discipline.  Must run AFTER
    ``ensure_alt_sources`` (the alt layers are populated in place).
    """
    ev = evidence_sources(layout)
    ss = score_sources(layout)
    polys = [s.polygon for s in candidates]
    layers = (
        ("name_apron", ss.name_apron),
        ("name_taxi", ss.name_taxi),
        ("name_service", ss.name_service),
        ("unpaved_cover", ss.unpaved),
        ("osm_apron", ev.osm_apron),
        ("osm_stand", ev.osm_stand),
        ("osm_taxi", ev.osm_taxi),
        ("spine_cover", ss.spine_buffers),
        ("truck_cover", ss.truck_corridors),
        ("road_cover", ev.road_corridors),
        ("tunnel_cover", ev.tunnel_corridors),
        ("parking_cover", ev.parking_corridors),
        ("alt_name_apron", ss.alt_name_apron),
        ("alt_name_taxi", ss.alt_name_taxi),
        ("alt_name_service", ss.alt_name_service),
        ("alt_taxi_cover", ss.alt_taxi_territory),
        ("_apt_only_cover", ss.apt_only),
    )
    rows: list[dict] = [{} for _ in polys]
    for key, index in layers:
        for entry, frac in zip(rows, index.cover_fractions(polys)):
            entry[key] = frac
    for entry, frac in zip(rows, _bulk_flank_fractions(polys, adjacency,
                                                       candidates)):
        entry["_flank"] = frac
    return {id(p): entry for p, entry in zip(polys, rows)}


def shadow_classify(layout, icao: str = "",
                    xplane_root: str | None = None) -> dict:
    """Score every final pavement shape; log agreement vs legacy.

    MUTATES NOTHING (spec §10.4).  Stashes per-shape records on
    ``layout.pavement_score_decisions`` and a summary on
    ``layout.pavement_score_summary``; prints one line.
    """
    summary = {"mode": PAVEMENT_SCORE_V2, "shapes": 0, "agree": 0,
               "disagree": 0, "low": 0, "confusion": {}, "seconds": 0.0,
               "apron_gated": 0}
    if PAVEMENT_SCORE_V2 == "off":
        layout.pavement_score_summary = summary
        return summary
    import time as _time
    started = _time.perf_counter()
    candidates = [
        s for s in layout.shapes
        if s.role in LEGACY_ROLE_TO_CLASS
        and s.polygon is not None and not s.polygon.is_empty
        and s.polygon.area >= PAVEMENT_SCORE_MIN_AREA_M2]
    if not candidates:
        layout.pavement_score_summary = summary
        return summary
    layout._pavement_score_abut_unions = None    # final roles here
    ensure_alt_sources(layout, icao, xplane_root)
    connectivity = runway_connectivity(layout)
    adjacency = _pavement_adjacency_index(layout)
    decisions: list[dict] = []
    reliability = source_reliability(layout)
    layout._pavement_score_feature_rows = _precompute_feature_rows(
        layout, candidates, adjacency)
    # ``shapeID`` in the emitted patch is the index in layout.shapes
    # (layout.to_osm) — record it so a patch shape the owner flags maps
    # 1:1 to its decision (CYXY evaluation 2026-07-28: centroid-matching
    # slot-time records against final shapes misattributed 3 shapes).
    shape_index = {id(s): i for i, s in enumerate(layout.shapes)}
    try:
        for shape in candidates:
            legacy_class = LEGACY_ROLE_TO_CLASS[shape.role]
            record = score_shape(
                shape.polygon, layout, adjacency=adjacency, owner=shape,
                connected=(connectivity.get(id(shape)) if connectivity
                           else None),
                legacy_class=legacy_class)
            record["shape_index"] = shape_index.get(id(shape))
            record["ref"] = shape.ref
            record["role"] = shape.role
            record["area_m2"] = round(shape.polygon.area, 1)
            try:
                centroid = shape.polygon.centroid
                record["lat"], record["lon"] = layout.m_to_ll(centroid.x,
                                                              centroid.y)
            except _GEOM_EXC:
                pass
            decisions.append(record)
            summary["shapes"] += 1
            if "G-APRON-AIRSIDE" in record["gates"]:
                summary["apron_gated"] += 1
            if record["band"] == "LOW" or record["winner"] is None:
                summary["low"] += 1
            verdict = record["winner"] or legacy_class
            if verdict == legacy_class:
                summary["agree"] += 1
            else:
                summary["disagree"] += 1
                key = f"{legacy_class}->{verdict}"
                summary["confusion"][key] = \
                    summary["confusion"].get(key, 0) + 1
    finally:
        # Rows are keyed by ``id`` — never leave them to outlive the
        # polygons they were computed for.
        layout._pavement_score_feature_rows = None
    summary["reliability"] = {
        "apt_names": round(reliability.apt_names, 3),
        "osm_aeroway": round(reliability.osm_aeroway, 3),
        "road_feed": round(reliability.road_feed, 3),
        "truck": round(reliability.truck, 3),
        "spine": round(reliability.spine, 3),
        "alt_apt": round(reliability.alt_apt, 3),
    }
    alt_path = getattr(score_sources(layout), "alt_path", "")
    if alt_path:
        summary["alt_apt_path"] = alt_path
    summary["seconds"] = _time.perf_counter() - started
    if getattr(layout, "pavement_score_decisions", None):
        # Enactment already stashed its slot-time records — keep them
        # reachable; the FINAL-shape records (shapeID-joinable) win the
        # primary slot the report tool reads.
        layout.pavement_score_enact_decisions = \
            layout.pavement_score_decisions
    layout.pavement_score_decisions = decisions
    layout.pavement_score_summary = summary
    total = max(1, summary["shapes"])
    UI.vprint(1,
        f"  [pav-score] {icao}: shadow v2 — {summary['agree']}/{total} "
        f"agree with legacy ({100 * summary['agree'] / total:.0f}%), "
        f"{summary['disagree']} differ, {summary['low']} low-margin; "
        f"rel {summary['reliability']}; {summary['seconds']:.2f} s.")
    UI.vprint(1,
        f"  [pav-score] {icao}: G-APRON-AIRSIDE gated "
        f"{summary['apron_gated']} of {total} shape(s) out of APRON "
        f"(no airside-contact feature — wide_blob may magnify, never "
        f"author).")
    return summary


# ═════════════════════════════════════════════════════════════════════
# Phase B — enactment (owner approval 2026-07-28: "turn it on so I can
# test it"; low legacy agreement at HECA is EXPECTED — the legacy
# chain misclassifies HECA, matching it is not the goal)
# ═════════════════════════════════════════════════════════════════════

_ENACT_ROLES = (ROLE_APRON, ROLE_JUNCTION, ROLE_SERVICE_ROAD,
                ROLE_SERVICE_JUNCTION)


def _enact_verdict(shape, record, dem_at, law_anchors=None,
                   anchor_key=None, stats=None) -> bool:
    """Apply one verdict to ``shape``.  Returns True when it moved.

    Under ``PAVEMENT_SCORE_PURE`` (the validation default, owner
    2026-07-28) a LOW margin still enacts the argmax — nothing falls
    through to the legacy passes, so the in-sim result IS the scorer.
    Hybrid mode (``O4_PAVEMENT_SCORE_PURE=0``) leaves LOW shapes to the
    un-gated legacy passes instead.  A shape with NO winner (zero
    evidence) always keeps its current role.
    """
    if record["winner"] is None:
        return False
    if record["band"] == "LOW" and not PAVEMENT_SCORE_PURE:
        return False
    current = LEGACY_ROLE_TO_CLASS[shape.role]
    target = record["winner"]
    if target == current:
        return False
    if target == CLASS_GROUNDSIDE:
        from .pavement_classification import _demote
        if not _demote(shape, ROLE_GROUNDSIDE_PAVEMENT, dem_at,
                       law_anchors=law_anchors, anchor_key=anchor_key,
                       stats=stats):
            record["band"] = "LOW"          # DEM re-follow failed: keep
            return False
        return True
    if target == CLASS_SERVICE:
        threads = (record["features"].get("road_thread", 0.0) > 0.0
                   or record["features"].get("truck_thread", 0.0) > 0.0)
        shape.role = ROLE_SERVICE_ROAD if threads else ROLE_SERVICE_JUNCTION
        shape.node_altitudes = None
        if shape.ref == "groundside":
            shape.ref = ""
        return True
    shape.role = ROLE_APRON if target == CLASS_APRON else ROLE_JUNCTION
    # A shape can arrive here from an earlier same-build demotion (the
    # enclave re-verdict promotes enacted groundside back) — drop the
    # DEM-followed altitudes and the groundside ref so the solver
    # treats it as ordinary unsolved airside.
    shape.node_altitudes = None
    if shape.ref == "groundside":
        shape.ref = ""
    # Deliberately NOT setting ``reclassified_from_junction``: that flag
    # invites the legacy neck-split re-eval to overturn this verdict,
    # and under enactment the scorer is the only classifier (owner
    # 2026-07-28).  Neck-split still runs as geometry; pieces keep the
    # scorer's role.
    return True


def enact_classify(layout, icao: str = "", dem=None,
                   tile_lat: int = 0, tile_lon: int = 0,
                   xplane_root: str | None = None) -> dict:
    """Score AND enact: every candidate shape takes the scorer's class.

    Runs in the ``classify_pavement_v1`` slot (the pipeline gates that
    vote, the first unscoped runway-disconnected pass, and the
    groundside route-corridor promotion off when this mode is on —
    their laws live here as G-CHAIN and the SERVICE verdicts).  After
    the first round, connectivity is recomputed once so shapes orphaned
    BY an enacted demotion cascade in the same build (the severing
    contract the v1 slot documents).
    """
    summary = {"mode": PAVEMENT_SCORE_V2, "shapes": 0, "enacted": 0,
               "low": 0, "severed": 0, "flips": {}, "seconds": 0.0,
               "apron_gated": 0}
    if PAVEMENT_SCORE_V2 != "on":
        layout.pavement_score_summary = summary
        return summary
    import time as _time
    started = _time.perf_counter()

    def _candidates():
        return [
            s for s in layout.shapes
            if s.role in _ENACT_ROLES
            and s.polygon is not None and not s.polygon.is_empty
            and s.polygon.area >= PAVEMENT_SCORE_MIN_AREA_M2]

    candidates = _candidates()
    if not candidates:
        layout.pavement_score_summary = summary
        return summary
    layout._pavement_score_abut_unions = None    # roles are current here
    ensure_alt_sources(layout, icao, xplane_root)
    # SEVERANCE (owner round-4 ruling): cut contour-straddling shapes
    # BEFORE scoring, so each piece is a candidate scored against its
    # own connectivity.  The cut partitions member polygons without
    # changing their union, so the zone stays valid for the
    # connectivity pass below.
    zone = _reach_zone(layout)
    summary["severed"] = sever_unreachable(layout, zone)
    # AEROWAY-EVIDENCE severance (owner axis-A ruling 2026-07-29): cut
    # big mixed-mapping blobs at the taxiway zone BEFORE scoring, so a
    # slice-welded mega-apron's corridors score on their own mapping.
    summary["aeroway_severed"] = sever_mixed_aeroway(layout)
    if summary["severed"] or summary["aeroway_severed"]:
        candidates = _candidates()
    connectivity = runway_connectivity(layout, zone)
    adjacency = _pavement_adjacency_index(layout)
    from .groundside import (_dem_sampler, law_anchor_values,
                             law_anchor_key, _law_seat_stats)
    dem_at = (_dem_sampler(layout, dem, tile_lat, tile_lon)
              if dem is not None else None)
    # ONCE per pass — the law datum a demoted piece seats on, and the
    # EMITTER'S vertex identity for finding it (cycle-6 ingestion: the
    # millimetre key missed welds the emitter later resolved at 0.5 m,
    # which is how a lot shipped with its welds on the law and its
    # interior on the DEM).
    _law_anchors = law_anchor_values(layout)
    _anchor_key = law_anchor_key(layout, _law_anchors)
    _seat_stats = _law_seat_stats(layout, "enact_classify")
    decisions: list[dict] = []
    n_groundside = 0

    def decide_and_apply(shape, connected, enclosed=None):
        nonlocal n_groundside
        legacy_class = LEGACY_ROLE_TO_CLASS[shape.role]
        record = score_shape(shape.polygon, layout, adjacency=adjacency,
                             owner=shape, connected=connected,
                             legacy_class=legacy_class, enclosed=enclosed)
        record["ref"] = shape.ref
        record["role"] = shape.role
        record["area_m2"] = round(shape.polygon.area, 1)
        if getattr(shape, "from_severance_cut", False):
            record["severed"] = True
        try:
            centroid = shape.polygon.centroid
            record["lat"], record["lon"] = layout.m_to_ll(centroid.x,
                                                          centroid.y)
        except _GEOM_EXC:
            pass
        moved = _enact_verdict(shape, record, dem_at,
                               law_anchors=_law_anchors,
                               anchor_key=_anchor_key, stats=_seat_stats)
        record["enacted"] = moved
        if moved:
            summary["enacted"] += 1
            key = f"{legacy_class}->{record['winner']}"
            summary["flips"][key] = summary["flips"].get(key, 0) + 1
            if record["winner"] == CLASS_GROUNDSIDE:
                n_groundside += 1
        if record["band"] == "LOW" or record["winner"] is None:
            summary["low"] += 1
        if "G-APRON-AIRSIDE" in record["gates"]:
            summary["apron_gated"] += 1
        decisions.append(record)
        return moved

    for shape in candidates:
        decide_and_apply(
            shape,
            connectivity.get(id(shape)) if connectivity else None)
    summary["shapes"] = len(candidates)

    # Orphan sweep: an enacted demotion severs touch-chains; shapes that
    # were connected in round 1 and are airside-classed now get one
    # re-verdict against the post-enactment connectivity.  SEVER FIRST
    # (owner CYXY #64/#69, 2026-07-28): round-1 flips move shapes INTO
    # the chain (service→junction), and those were invisible to the
    # pre-score severance — cutting them here lets a straddler keep its
    # reachable side instead of being demoted wholesale by the sweep.
    # New pieces have no round-1 connectivity entry (`get` → None, not
    # False), so a disconnected piece re-verdicts below like any
    # orphan; a reachable piece keeps its post-flip role.
    latest_connectivity = connectivity
    if summary["enacted"] and connectivity:
        zone2 = _reach_zone(layout)
        n_sever2 = sever_unreachable(layout, zone2)
        if n_sever2:
            summary["severed"] += n_sever2
            candidates = _candidates()
        connectivity2 = runway_connectivity(layout, zone2)
        if connectivity2:
            latest_connectivity = connectivity2
            for shape in candidates:
                if shape.role not in (ROLE_APRON, ROLE_JUNCTION):
                    continue
                if connectivity.get(id(shape)) is not False \
                        and connectivity2.get(id(shape)) is False:
                    decide_and_apply(shape, False)

    # ENCLAVE re-verdict (owner topological rule 2026-07-28, extended to
    # bare ground 2026-08-07).  THE enclave regions are computed and
    # PUBLISHED here — once per build, by ``enclaves.py``, and here
    # because this is the moment the airside roles settle and the moment
    # BEFORE the re-verdicts below change them (a shape promoted out of
    # GROUNDSIDE becomes airside and would close its own enclave).  Two
    # later consumers read the same store: ``gap_fill``'s foreign-shape
    # blocker and ``adjacent_ground``'s band keep-out.
    #
    # THE PREDICATE IS POINT-IN-ENCLAVE (spec
    # docs/specs/enclave-region-law-spec.md §2), not the ring COVERAGE
    # test it replaces.  The old one asked whether a SHAPE was covered by
    # the airside union to within ``PAVEMENT_SCORE_ENCLAVE_GAP_M``, which
    # only a shape FILLING the void could pass — the specimen's 5.58 m²
    # sliver read 0.0 % coverage inside a void whose rim is 100 % apron,
    # because a whole flank of it faces the void's own bare interior
    # (dossier §2).  A region test has no such blind spot, needs no
    # tolerance, and — with the candidate set below — no longer requires
    # the shape to be a scoring candidate at all.
    summary["enclaves"] = 0
    enclave_records = publish_airside_enclaves(layout)
    if enclave_records:
        # THE CANDIDATE SET (spec §2): every shape currently classed
        # groundside, read off ``layout.shapes`` — so no 10 m² candidate
        # floor (the specimen sliver is 5.58 m²), no ``_ENACT_ROLES``
        # birth-role restriction (a shape BORN groundside was never a
        # candidate and could never be re-verdicted), and the
        # POST-DEMOTION state (the refreshed ``candidates`` list drops
        # every shape demoted this round — HECA logged 1 re-verdict
        # against 1,103 demotions).
        for shape in layout.shapes:
            if shape.role != ROLE_GROUNDSIDE_PAVEMENT:
                continue
            poly = shape.polygon
            if (poly is None or poly.is_empty
                    or poly.geom_type != "Polygon"):
                continue
            if not shape_in_enclave(layout, shape):
                continue
            if decide_and_apply(
                    shape,
                    (latest_connectivity.get(id(shape))
                     if latest_connectivity else None),
                    enclosed=True):
                summary["enclaves"] += 1

    if n_groundside and dem is not None:
        from .groundside import _separate_groundside_from_airside
        try:
            _separate_groundside_from_airside(layout, dem, tile_lat,
                                              tile_lon)
        except _GEOM_EXC:
            pass

    reliability = source_reliability(layout)
    summary["reliability"] = {
        "apt_names": round(reliability.apt_names, 3),
        "osm_aeroway": round(reliability.osm_aeroway, 3),
        "road_feed": round(reliability.road_feed, 3),
        "truck": round(reliability.truck, 3),
        "spine": round(reliability.spine, 3),
        "alt_apt": round(reliability.alt_apt, 3),
    }
    summary["seconds"] = _time.perf_counter() - started
    layout.pavement_score_decisions = decisions
    layout.pavement_score_summary = summary
    low_note = ("enacted by argmax (PURE)" if PAVEMENT_SCORE_PURE
                else "left to legacy passes")
    sever_note = (f"; {summary['severed']} shape(s) severed at the "
                  f"reachability contour" if summary["severed"] else "")
    if summary.get("aeroway_severed"):
        sever_note += (f"; {summary['aeroway_severed']} mixed-mapping "
                       f"shape(s) severed at the aeroway boundary")
    if summary.get("enclaves"):
        sever_note += (f"; {summary['enclaves']} airside-enclave "
                       f"re-verdict(s)")
    UI.vprint(1,
        f"  [pav-score] {icao}: ENACT v2 — {summary['enacted']} of "
        f"{summary['shapes']} shape(s) re-classed "
        f"({summary['flips']}), {summary['low']} low-margin "
        f"{low_note}{sever_note}; {summary['seconds']:.2f} s.")
    # The gate's own census line (owner 2026-08-11b: "one loud census
    # line counts gated shapes per build").  Counts DECISIONS, not
    # shapes: a shape re-verdicted by the orphan or enclave sweep is
    # counted once per decision it received, which is what "how often
    # did the law bite" means here.
    UI.vprint(1,
        f"  [pav-score] {icao}: G-APRON-AIRSIDE gated "
        f"{summary['apron_gated']} of {len(decisions)} decision(s) out "
        f"of APRON (no airside-contact feature — wide_blob may magnify, "
        f"never author).")
    return summary
