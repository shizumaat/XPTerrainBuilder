"""Parser for X-Plane ``apt.dat`` airport data files.

Loads runway, pavement (taxiway / apron / ramp) and boundary geometry
for a single airport.  This is the *patch-mesh authoritative* source
for airport pavement shapes — apt.dat polygons are exactly what the
X-Plane simulator renders as the pavement texture, so elevation
patches generated against these polygons align perfectly with the
ground texture (no visible seams).

Compared to OSM aerodrome data:

* apt.dat polygons are **disjoint by construction** — no overlapping
  shapes to subtract, no precision-drift artefacts.
* Taxiways are stored as **outline polygons**, not centerlines that
  we have to buffer to a guessed width.
* Curved taxiway shoulders use **Bezier control points** (rows 112,
  114) which we sample into polygon vertices.
* Each pavement carries its **surface type**, **roughness** and
  **orientation** so downstream code can apply per-surface grade
  rules.

Compared to CIFP, apt.dat does NOT have per-runway-threshold
elevations — runway row 100 only stores lat/lon, width, and
displaced-threshold offsets.  CIFP is still the source of truth for
runway elevations.

The parser is read-only and side-effect-free: given a path to an
``apt.dat`` file and an ICAO code, it returns an :class:`Airport`
object containing the parsed geometry.  The apt.dat that serves an airport
is v2's ``auto_patch_v2.airport.apt_dat.select_apt_dat`` (the build's own
selector); v1's ``find_airport_apt_dat``, its persistent index and the
unreached taxi/service centerline builders were retired in wave F (#852).
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

# Narrow exception tuple for shapely / numeric-geometry failure
# modes.  Programming errors propagate so they surface immediately.
_GEOM_EXC = (ValueError, GEOSException, TopologicalError)


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────
FT_TO_M = 0.3048

# Default number of straight-line segments to sample each Bezier curve
# into.  4 produces a visibly smooth corner without exploding the
# vertex count.  Tunable via the load_airport(..., bezier_segments=N)
# parameter.  With O4_ADAPTIVE_BEZIER on (default) this is only the
# LEGACY fallback — the per-span adaptive rule below decides.
DEFAULT_BEZIER_SEGMENTS = 4

# ADAPTIVE curve tessellation (user 2026-07-05: optimise for the MINIMUM
# node count that still yields a smooth profile — short curve chords are
# the "hairline factory": a pair's grade budget is rate·distance, so a
# 1.5 m tessellation chord turns millimetres of elevation into percents
# of grade, while the vertical-curve law never lets the profile wiggle
# between 4 m nodes anyway).  Per bezier span:
#   k_sagitta = ceil(sqrt(deviation_m / CURVE_SAGITTA_MAX_M))
#       — subdivision error shrinks ~quadratically; keeps the polyline
#         within the sagitta cap of the true curve where spacing allows.
#   k_spacing = floor(span_m / CURVE_MIN_VERTEX_SPACING_M)
#       — vertices never closer than the spacing floor: 0.2·rate·d ≥ the
#         ~1 cm system noise floor at d ≥ 4-5 m (1 % class), so every
#         minted pair is robust to rounding/smoothing.
#   k = max(1, min(k_sagitta, k_spacing))   — SPACING DOMINATES (the
#         user ruling); small corner fillets collapse to 1-2 chords.
# Deterministic per span, so every shape sharing a curve derives the
# same vertices (conformance holds by construction).
ADAPTIVE_BEZIER = os.environ.get("O4_ADAPTIVE_BEZIER", "1") == "1"
CURVE_SAGITTA_MAX_M = float(os.environ.get("O4_CURVE_SAGITTA_M", "0.4"))
CURVE_MIN_VERTEX_SPACING_M = float(
    os.environ.get("O4_CURVE_MIN_SPACING_M", "4.0"))

# Per user 2026-05-04: collapse Bezier to a straight line when the
# curve's max chord deviation falls below this threshold (in degrees,
# ≈ metres at airport latitudes).  Many apt.dat authors use Beziers
# just to soften 90° corners by 1-2 m for visual smoothness — the
# default 4-segment tessellation turns each into a 5-vertex arc that
# downstream residue/junction passes treat as real boundary detail
# and end up wrapping junction polygons around.  At SPJC stub C, two
# such corner-softening Beziers (chord deviations 1.04 m and 0.39 m)
# created the "wrong-side" junction vertex.  Real curves (taxiway
# turns, swept apron edges) have deviations well above this.
# Threshold expressed in DEGREES because the calculation runs in
# lat/lon space; 0.000014 deg ≈ 1.5 m.  Tunable in METRES via
# ``O4_BEZIER_FLATTEN_DEV_M`` (default 1.5) — set 0 to keep ALL source bezier
# curves (tight corner-softening arcs included), so tight curves grade smoothly
# instead of flattening to an abrupt corner.  Trade-off: the arc vertices can
# make downstream residue/junction passes wrap a junction around the corner
# (the original reason for the flatten — user 2026-05-04).
BEZIER_FLATTEN_DEV_DEG = float(os.environ.get("O4_BEZIER_FLATTEN_DEV_M", "1.5")) / 111111.0

# Row type codes (X-Plane apt.dat 1100 / 1200 spec).
ROW_AIRPORT_HEADER = 1
ROW_RUNWAY = 100
ROW_HELIPAD = 102
ROW_PAVEMENT_HEADER = 110
ROW_NODE = 111
ROW_NODE_BEZIER = 112
ROW_CLOSE = 113
ROW_CLOSE_BEZIER = 114
ROW_END_LINE = 115             # open-polyline terminator (plain)
ROW_END_LINE_BEZIER = 116      # open-polyline terminator (bezier)
ROW_LINE_HEADER = 120          # painted linear feature (taxi lines etc.)
ROW_BOUNDARY_HEADER = 130
ROW_TAXI_NODE = 1201
ROW_TAXI_EDGE = 1202
ROW_TRUCK_EDGE = 1206          # ground-vehicle (service-road) route edge
ROW_RAMP_START = 1300          # startup location (parking position)

# Row-120 painted-line type codes that mark a TAXIWAY CENTERLINE:
# 1 = solid yellow, 7 = centerline in non-movement area; 51/57 = the
# same with a black border (apt.dat 1100 spec).  Codes 2/3/8/9 are
# taxiway EDGE / queue markings, 4/5/6 hold-position bars, 20+ roadway.
CENTERLINE_PAINT_CODES = frozenset((1, 7, 51, 57))


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────
@dataclass
class Runway:
    """One paired runway (apt.dat row 100)."""
    desig_a: str
    desig_b: str
    lat_a: float
    lon_a: float
    lat_b: float
    lon_b: float
    width_m: float
    surface_code: int
    displaced_a_m: float
    displaced_b_m: float
    # The apt.dat row-100 PUBLISHED width, preserved when the shoulder
    # widening (``pipeline._widen_runway_rect``) overwrites ``width_m`` in
    # place with runway+shoulders (SPJC 16R/34L: 45 -> 81 m).  Rules keyed
    # on "the runway" mean the DECLARED runway — shoulders are a separate
    # feature (ICAO Annex 14 §3.2) — so anything citing runway width must
    # read ``declared_width_m``, not ``width_m``.  ``None`` until widened.
    published_width_m: float | None = None
    blast_a_m: float = 0.0   # blast pad / overrun length beyond end a
    blast_b_m: float = 0.0   # blast pad / overrun length beyond end b
    # row-100 shoulder field, encoded ``100 * width_m + surface_code``
    # (X-Plane 12 spec): > 100 ⇒ the 100s/1000s digits are the shoulder
    # width in whole metres per side; < 100 ⇒ bare surface code (no
    # explicit width); 0 ⇒ no shoulder.
    shoulder_code: int = 0
    # Per-end runway markings code (apt.dat 1000 spec: 0 none, 1 visual,
    # 2 non-precision, 3 precision, 4 UK non-precision, 5 UK precision).
    markings_a: int = 0
    markings_b: int = 0
    # Per-end approach-lighting code (0 none, 1 ALSF-I, 2 ALSF-II,
    # 3 Calvert, 4 Calvert ILS Cat II/III, 5 SSALR, 6 SSALF, 7 SALS,
    # 8 MALSR, 9 MALSF, 10 MALS, 11 ODALS, 12 RAIL).
    approach_lights_a: int = 0
    approach_lights_b: int = 0


    @property
    def declared_width_m(self) -> float:
        """The published runway width (m) — ``width_m`` unless the shoulder
        widening replaced it, in which case the preserved original.

        Use this for every rule that says "the runway width".  ICAO Annex 14
        §3.5.3 ("a RESA shall extend to a width of at least twice that of the
        runway") is the live case: fed the shoulder-widened value it sizes
        SPJC 16R's end corridor at 81 m instead of the correct 45 m factor.
        """
        published = self.published_width_m
        return float(published) if published else float(self.width_m)


@dataclass
class Pavement:
    """One pavement polygon (apt.dat row 110)."""
    polygon: Polygon            # exterior + interior holes
    surface_code: int
    roughness: float            # 0.0 (smooth) … 1.0 (rough)
    orientation: float          # texture rotation in degrees from N
    name: str = ""              # pavement label, e.g. "TWY A", "RAMP 1"


@dataclass
class PaintedLine:
    """One painted linear feature (apt.dat row 120).

    ``line`` vertices are (lon, lat) like ``Pavement`` rings, bezier
    nodes already tessellated.  ``paint_codes`` collects every
    line-type attribute seen on the feature's nodes — paint types are
    < 100, lighting types ≥ 100 (the apt.dat 1100 convention).  A
    feature closed by 113/114 has ``closed=True`` (its line repeats
    the first vertex at the end); 115/116-terminated features are
    open polylines.
    """
    line: LineString
    paint_codes: frozenset[int]
    closed: bool = False

    @property
    def is_centerline_paint(self) -> bool:
        return bool(self.paint_codes & CENTERLINE_PAINT_CODES)


@dataclass
class TaxiNode:
    """One taxi-network node (apt.dat row 1201).

    Format: ``1201 lat lon usage id [label]``

    ``usage`` is one of ``"init"``, ``"dest"``, ``"both"``, or
    ``"judge"`` — describes whether the node is a route endpoint.
    Not used for centerline construction but kept for completeness.
    """
    id: int
    lat: float
    lon: float
    usage: str = ""
    label: str = ""


@dataclass
class TaxiEdge:
    """One taxi-network edge (apt.dat row 1202).

    Format: ``1202 node_from node_to direction kind [name]``

    * ``direction`` is ``"oneway"`` or ``"twoway"``.
    * ``kind`` is an ICAO width category (``"taxiway_A"`` …
      ``"taxiway_F"``) or the literal ``"runway"`` for taxi paths
      crossing a runway.
    * ``name`` is the taxiway designator (``"G"``, ``"A1"``, …) or
      the runway designator (``"02/20"``) when ``kind == "runway"``.
      May be empty for unnamed connector edges.
    """
    node_from: int
    node_to: int
    direction: str
    kind: str
    name: str = ""


@dataclass
class Airport:
    """Parsed airport geometry from one apt.dat block."""
    icao: str
    name: str
    reference_elev_ft: int      # row 1 elevation, in feet (0 if absent)
    runways: list[Runway] = field(default_factory=list)
    pavements: list[Pavement] = field(default_factory=list)
    taxi_nodes: "dict[int, TaxiNode]" = field(default_factory=dict)
    taxi_edges: list[TaxiEdge] = field(default_factory=list)
    # Ground-vehicle (service-road) route edges (row 1206).  Reuse the
    # ``TaxiEdge`` shape with ``kind == "truck"``; share the 1201 nodes
    # in ``taxi_nodes``.  Drive the ``service_road`` rects (cap
    # ``config.SERVICE_ROAD_MAX_GRADE`` — the ONE grade number).
    truck_edges: list[TaxiEdge] = field(default_factory=list)
    # Ramp-start (startup location, row 1300) positions ``(lat, lon)`` —
    # used to TRIM the last dead-end taxi-route piece leading onto a
    # stand (user 2026-07-04: the lead-in line to a parking position
    # needs no spine; the apron covers the pavement).
    ramp_starts: list = field(default_factory=list)
    # Painted linear features (row 120) — taxiway centerlines, edge
    # lines, hold bars.  Carries the authored bezier curves; airports
    # without a 1201/1202 taxi network often have ONLY these.
    painted_lines: list[PaintedLine] = field(default_factory=list)
    boundary: Polygon | None = None
    source_path: str = ""

    @property
    def reference_elev_m(self) -> float:
        return self.reference_elev_ft * FT_TO_M


# ──────────────────────────────────────────────────────────────────────
# Public API: parsing an airport block
# ──────────────────────────────────────────────────────────────────────
def load_airport(
    aptdat_path: str,
    icao: str,
    bezier_segments: int = DEFAULT_BEZIER_SEGMENTS,
) -> Airport | None:
    """Parse the airport block for ``icao`` out of ``aptdat_path``.

    Args:
        aptdat_path: filesystem path to an apt.dat file.
        icao: 4-letter airport code (case-insensitive).
        bezier_segments: how many straight-line segments to subdivide
            each Bezier curve into.  4 is a good default for taxiway
            corners; raise it for tight curves.

    Returns:
        An :class:`Airport` object, or ``None`` if the airport block
        could not be found in the file.
    """
    if not aptdat_path or not os.path.isfile(aptdat_path):
        return None

    block = _read_airport_block(aptdat_path, icao)
    if block is None:
        return None

    header = block[0]
    # Row 1 format: ``1 elevation_ft tower_height beacon_type ICAO airport_name``
    # The name is everything after the ICAO and may contain spaces.
    parts = header.split(maxsplit=5)
    try:
        ref_elev = int(parts[1])
    except (IndexError, ValueError):
        ref_elev = 0
    name = parts[5] if len(parts) > 5 else ""

    airport = Airport(
        icao=icao.upper(),
        name=name.strip(),
        reference_elev_ft=ref_elev,
        source_path=aptdat_path,
    )

    pavement_rows: list[list[str]] = []
    boundary_rows: list[list[str]] = []
    line_rows: list[list[str]] = []
    in_pavement = False
    in_boundary = False
    in_line = False

    def flush_pavement():
        if pavement_rows:
            pav = _parse_pavement(pavement_rows, bezier_segments)
            if pav is not None:
                airport.pavements.append(pav)
            pavement_rows.clear()

    def flush_line():
        if line_rows:
            pl = _parse_painted_line(line_rows, bezier_segments)
            if pl is not None:
                airport.painted_lines.append(pl)
            line_rows.clear()

    def flush_boundary():
        if boundary_rows:
            poly = _parse_boundary(boundary_rows, bezier_segments)
            if poly is not None:
                # If we already have a boundary, union with the new one.
                if airport.boundary is None:
                    airport.boundary = poly
                else:
                    try:
                        merged = unary_union([airport.boundary, poly])
                        if isinstance(merged, Polygon):
                            airport.boundary = merged
                    except _GEOM_EXC:
                        pass
            boundary_rows.clear()

    for line in block[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        toks = stripped.split()
        try:
            row_type = int(toks[0])
        except ValueError:
            continue

        # Pavement / boundary / line blocks accumulate consecutive
        # node rows.
        if row_type == ROW_PAVEMENT_HEADER:
            flush_pavement()
            flush_boundary()
            flush_line()
            in_pavement = True
            in_boundary = False
            in_line = False
            pavement_rows.append(toks)
            continue
        if row_type == ROW_BOUNDARY_HEADER:
            flush_pavement()
            flush_boundary()
            flush_line()
            in_pavement = False
            in_boundary = True
            in_line = False
            boundary_rows.append(toks)
            continue
        if row_type == ROW_LINE_HEADER:
            flush_pavement()
            flush_boundary()
            flush_line()
            in_pavement = False
            in_boundary = False
            in_line = True
            line_rows.append(toks)
            continue
        if row_type in (ROW_NODE, ROW_NODE_BEZIER,
                        ROW_CLOSE, ROW_CLOSE_BEZIER):
            if in_pavement:
                pavement_rows.append(toks)
            elif in_boundary:
                boundary_rows.append(toks)
            elif in_line:
                line_rows.append(toks)
            continue
        if row_type in (ROW_END_LINE, ROW_END_LINE_BEZIER):
            # Open-polyline terminator: only meaningful inside a 120
            # block (115/116 appear nowhere else).
            if in_line:
                line_rows.append(toks)
                flush_line()
                in_line = False
            continue

        # Anything else terminates the current pavement / boundary /
        # line block (and contributes its own data).
        flush_pavement()
        flush_boundary()
        flush_line()
        in_pavement = False
        in_boundary = False
        in_line = False

        if row_type == ROW_RUNWAY:
            rwy = _parse_runway(toks)
            if rwy is not None:
                airport.runways.append(rwy)
        elif row_type == ROW_TAXI_NODE:
            tn = _parse_taxi_node(toks)
            if tn is not None:
                airport.taxi_nodes[tn.id] = tn
        elif row_type == ROW_TAXI_EDGE:
            te = _parse_taxi_edge(toks)
            if te is not None:
                airport.taxi_edges.append(te)
        elif row_type == ROW_RAMP_START:
            # ``1300 lat lon heading type traffic name`` — position only.
            try:
                airport.ramp_starts.append(
                    (float(toks[1]), float(toks[2])))
            except (ValueError, IndexError):
                pass
        elif row_type == ROW_TRUCK_EDGE:
            tk = _parse_truck_edge(toks)
            if tk is not None:
                airport.truck_edges.append(tk)

    # Final flush in case the block ends mid-pavement.
    flush_pavement()
    flush_boundary()
    flush_line()

    # Per user 2026-05-04: deduplicate near-identical pavement
    # polygons.  Some custom-scenery apt.dat files carry the same
    # logical pavement region drawn TWICE with slightly offset
    # vertices (e.g. SPJC's "Base Ramp" appears as both row-110
    # #39 and #40, with vertices ~0.3 m apart).  When ``unary_union``
    # later merges these duplicates, the slight offset creates
    # intersection-point artefacts on the boundary that downstream
    # residue/junction passes mistake for real apt.dat detail and
    # end up wrapping junction polygons around.  Two pavements with
    # the SAME name and a symmetric_difference / union ratio below
    # 1 % are treated as the same feature; the second one is dropped.
    if len(airport.pavements) >= 2:
        keep_idx = list(range(len(airport.pavements)))
        dropped: set = set()
        for i in range(len(airport.pavements)):
            if i in dropped:
                continue
            pi = airport.pavements[i]
            if pi.polygon is None or pi.polygon.is_empty:
                continue
            for j in range(i + 1, len(airport.pavements)):
                if j in dropped:
                    continue
                pj = airport.pavements[j]
                if pj.polygon is None or pj.polygon.is_empty:
                    continue
                if pi.name != pj.name:
                    continue
                try:
                    u = pi.polygon.union(pj.polygon)
                    if u.area <= 0:
                        continue
                    sd = pi.polygon.symmetric_difference(pj.polygon)
                    if sd.area / u.area < 0.01:
                        dropped.add(j)
                except _GEOM_EXC:
                    continue
        if dropped:
            airport.pavements = [
                p for k, p in enumerate(airport.pavements)
                if k not in dropped]

    return airport


# ──────────────────────────────────────────────────────────────────────
# Internal: the block reader
# ──────────────────────────────────────────────────────────────────────
def _read_airport_block(aptdat_path: str, icao: str) -> list[str] | None:
    """Return all lines from the row-1 header for `icao` up to (but
    not including) the next row-1 header.  None if not found.
    """
    icao = icao.upper()
    block: list[str] = []
    in_block = False
    try:
        with open(aptdat_path, "r", encoding="utf-8",
                  errors="replace") as f:
            for line in f:
                if line.startswith("1 ") or line.startswith("1\t"):
                    parts = line.split()
                    if len(parts) >= 5 and parts[0] == "1":
                        if in_block:
                            # Reached the next airport.
                            return block
                        if parts[4].upper() == icao:
                            in_block = True
                            block.append(line)
                            continue
                if in_block:
                    block.append(line)
    except OSError:
        return None
    return block if in_block else None


# ──────────────────────────────────────────────────────────────────────
# Internal: row parsers
# ──────────────────────────────────────────────────────────────────────
def _parse_runway(toks: list[str]) -> Runway | None:
    """Parse an apt.dat row 100 into a Runway.  Format:

    ``100 width surface shoulder smoothness centerline edge_lights distance_signs
         <end_a:9> <end_b:9>``

    Each end-of-runway block is 9 tokens:
    ``desig lat lon displaced blastpad markings approach_lights tdz_lights reil``

    ``blastpad`` (index 4 within the end block) is the length in
    metres of the blast pad / stopway / overrun surface beyond the
    threshold on that end.
    """
    if len(toks) < 25:
        return None
    try:
        width_m = float(toks[1])
        surface_code = int(toks[2])
        # toks[3] = shoulder, toks[4] = smoothness, toks[5] = centerline,
        # toks[6] = edge_lights, toks[7] = distance_signs
        try:
            shoulder_code = int(float(toks[3]))
        except (ValueError, IndexError):
            shoulder_code = 0
        end_a = toks[8:17]   # 9 fields
        end_b = toks[17:26]
        desig_a = end_a[0]
        lat_a = float(end_a[1])
        lon_a = float(end_a[2])
        displaced_a_m = float(end_a[3])
        blast_a_m = float(end_a[4])
        desig_b = end_b[0]
        lat_b = float(end_b[1])
        lon_b = float(end_b[2])
        displaced_b_m = float(end_b[3])
        blast_b_m = float(end_b[4])

        def _end_code(end_block: list[str], index: int) -> int:
            """Optional trailing end-block field (markings / approach
            lights); rows trimmed short of the full 9 tokens read 0."""
            try:
                return int(float(end_block[index]))
            except (ValueError, IndexError):
                return 0

        markings_a = _end_code(end_a, 5)
        approach_lights_a = _end_code(end_a, 6)
        markings_b = _end_code(end_b, 5)
        approach_lights_b = _end_code(end_b, 6)
    except (ValueError, IndexError):
        return None

    return Runway(
        desig_a=desig_a, desig_b=desig_b,
        lat_a=lat_a, lon_a=lon_a, lat_b=lat_b, lon_b=lon_b,
        width_m=width_m, surface_code=surface_code,
        displaced_a_m=displaced_a_m, displaced_b_m=displaced_b_m,
        blast_a_m=blast_a_m, blast_b_m=blast_b_m,
        shoulder_code=shoulder_code,
        markings_a=markings_a, markings_b=markings_b,
        approach_lights_a=approach_lights_a,
        approach_lights_b=approach_lights_b,
    )


def _parse_taxi_node(toks: list[str]) -> TaxiNode | None:
    """Parse an apt.dat row 1201 into a TaxiNode.

    Format: ``1201 lat lon usage id [label]``

    The label can contain spaces (e.g. ``"Props fuel truck_stop"``) —
    join all remaining tokens for it.
    """
    if len(toks) < 5:
        return None
    try:
        lat = float(toks[1])
        lon = float(toks[2])
        usage = toks[3]
        nid = int(toks[4])
    except (ValueError, IndexError):
        return None
    label = " ".join(toks[5:]) if len(toks) > 5 else ""
    return TaxiNode(id=nid, lat=lat, lon=lon, usage=usage, label=label)


def _parse_taxi_edge(toks: list[str]) -> TaxiEdge | None:
    """Parse an apt.dat row 1202 into a TaxiEdge.

    Format: ``1202 node_from node_to direction kind [name]``

    The taxiway/runway name field may be empty (the unnamed-connector
    case at CYXY — 9 of 65 edges).  The name can also contain
    spaces; join remaining tokens.
    """
    if len(toks) < 5:
        return None
    try:
        nf = int(toks[1])
        nt = int(toks[2])
    except (ValueError, IndexError):
        return None
    direction = toks[3]
    kind = toks[4]
    name = " ".join(toks[5:]) if len(toks) > 5 else ""
    return TaxiEdge(node_from=nf, node_to=nt,
                    direction=direction, kind=kind, name=name)


def _parse_truck_edge(toks: list[str]) -> TaxiEdge | None:
    """Parse an apt.dat row 1206 (ground-vehicle route edge) into a TaxiEdge.

    Format: ``1206 node_from node_to direction [name]``

    Unlike row 1202, there is no ICAO width ``kind`` field (service
    vehicles have no aircraft size class) — store ``kind == "truck"``.
    The name may be empty or contain spaces (``"Terminal fuel truck"``).
    Nodes are shared with the 1201 taxi-network nodes.
    """
    if len(toks) < 4:
        return None
    try:
        nf = int(toks[1])
        nt = int(toks[2])
    except (ValueError, IndexError):
        return None
    direction = toks[3]
    name = " ".join(toks[4:]) if len(toks) > 4 else ""
    return TaxiEdge(node_from=nf, node_to=nt,
                    direction=direction, kind="truck", name=name)


def _parse_pavement(rows: list[list[str]],
                    bezier_segments: int) -> Pavement | None:
    """Parse a row-110 header + node rows into a Pavement.

    The first contour (terminated by 113/114) is the exterior; any
    subsequent contours within the same pavement are interior holes.
    """
    if not rows:
        return None
    header = rows[0]
    try:
        surface_code = int(header[1])
        roughness = float(header[2])
        orientation = float(header[3])
    except (IndexError, ValueError):
        return None
    name = " ".join(header[4:]) if len(header) > 4 else ""

    contours = _split_contours(rows[1:])
    if not contours:
        return None

    rings = []
    for contour in contours:
        ring = _interpolate_contour(contour, bezier_segments)
        if ring:
            ring = _sparsify_ring_points(ring, True, ring[0][1])
        if len(ring) >= 3:
            # Close the ring explicitly.
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            rings.append(ring)
    if not rings:
        return None

    try:
        polygon = Polygon(rings[0], rings[1:] if len(rings) > 1 else None)
    except _GEOM_EXC:
        return None
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty:
        return None
    # buffer(0) on a self-intersecting source polygon can return a
    # MultiPolygon (the cleaned result split into disjoint pieces).
    # Take the largest component — at SPJC's custom apt.dat about 8
    # of 51 pavements take this path; the dropped slivers are tiny
    # geometric artefacts of the source data, not real pavement.
    if not isinstance(polygon, Polygon):
        if hasattr(polygon, "geoms"):
            try:
                polygon = max(polygon.geoms, key=lambda g: g.area)
            except _GEOM_EXC:
                return None
        else:
            return None
        if polygon.is_empty or not isinstance(polygon, Polygon):
            return None

    return Pavement(
        polygon=polygon,
        surface_code=surface_code,
        roughness=roughness,
        orientation=orientation,
        name=name.strip(),
    )


def _parse_boundary(rows: list[list[str]],
                    bezier_segments: int) -> Polygon | None:
    """Parse a row-130 header + node rows into a boundary Polygon.

    Boundaries follow the same node row format as pavements.  We
    treat the first contour as the exterior and any extra contours
    as interior holes (rare for boundaries but allowed by the spec).
    """
    if not rows:
        return None
    contours = _split_contours(rows[1:])
    if not contours:
        return None
    rings = []
    for contour in contours:
        ring = _interpolate_contour(contour, bezier_segments)
        if ring:
            ring = _sparsify_ring_points(ring, True, ring[0][1])
        if len(ring) >= 3:
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            rings.append(ring)
    if not rings:
        return None
    try:
        poly = Polygon(rings[0], rings[1:] if len(rings) > 1 else None)
    except _GEOM_EXC:
        return None
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or not isinstance(poly, Polygon):
        return None
    return poly


def _parse_painted_line(rows: list[list[str]],
                        bezier_segments: int) -> "PaintedLine | None":
    """Parse a row-120 header + node rows into a :class:`PaintedLine`.

    A 120 block is one polyline: 111/112 nodes terminated either by a
    113/114 row (closed loop — e.g. an apron edge outline) or a
    115/116 row (open line — the common taxiway-centerline case).
    Line-type attributes ride on the nodes (paint < 100, lighting
    ≥ 100); 115/116 terminators carry no attributes.
    """
    if len(rows) < 3:        # header + at least two nodes
        return None
    node_rows: list[list[str]] = []
    codes: set[int] = set()
    closed = False
    for row in rows[1:]:
        try:
            rt = int(row[0])
        except (ValueError, IndexError):
            continue
        if rt in (ROW_NODE, ROW_CLOSE):
            attr_start = 3
        elif rt in (ROW_NODE_BEZIER, ROW_CLOSE_BEZIER):
            attr_start = 5
        elif rt in (ROW_END_LINE, ROW_END_LINE_BEZIER):
            attr_start = None
        else:
            continue
        if rt in (ROW_CLOSE, ROW_CLOSE_BEZIER):
            closed = True
        if attr_start is not None:
            for tok in row[attr_start:attr_start + 2]:
                try:
                    codes.add(int(tok))
                except ValueError:
                    pass
        node_rows.append(row)
    if len(node_rows) < 2:
        return None
    if closed:
        pts = _interpolate_contour(node_rows, bezier_segments)
        if pts:
            pts = _sparsify_ring_points(pts, True, pts[0][1])
        if len(pts) >= 3 and pts[0] != pts[-1]:
            pts.append(pts[0])
    else:
        pts = _interpolate_open_polyline(node_rows, bezier_segments)
        if pts:
            pts = _sparsify_ring_points(pts, False, pts[0][1])
    if len(pts) < 2:
        return None
    try:
        ls = LineString(pts)
        if ls.is_empty or ls.length <= 0.0:
            return None
    except _GEOM_EXC:
        return None
    return PaintedLine(line=ls, paint_codes=frozenset(codes),
                       closed=closed)


def _interpolate_open_polyline(
        node_rows: list[list[str]],
        bezier_segments: int) -> list[tuple[float, float]]:
    """Open-polyline variant of :func:`_interpolate_contour`: same
    per-segment bezier conventions, no wraparound segment, and the
    final node IS appended."""
    n = len(node_rows)
    if n < 2:
        return []
    out: list[tuple[float, float]] = []
    for i in range(n - 1):
        a_row = node_rows[i]
        b_row = node_rows[i + 1]
        a_xy = _node_xy(a_row)
        b_xy = _node_xy(b_row)
        a_ctrl = _node_ctrl(a_row)
        b_ctrl = _node_ctrl(b_row)
        if not out or out[-1] != a_xy:
            out.append(a_xy)
        if a_ctrl is None and b_ctrl is None:
            continue
        if a_ctrl is not None and b_ctrl is None:
            ctrl_eff = a_ctrl
        elif a_ctrl is None and b_ctrl is not None:
            ctrl_eff = _mirror(b_ctrl, b_xy)
        else:
            mirrored = _mirror(b_ctrl, b_xy)
            mid = (0.5 * (a_xy[0] + b_xy[0]),
                   0.5 * (a_xy[1] + b_xy[1]))
            d1 = math.hypot(a_ctrl[0] - mid[0], a_ctrl[1] - mid[1])
            d2 = math.hypot(mirrored[0] - mid[0],
                            mirrored[1] - mid[1])
            if 0.5 * max(d1, d2) < BEZIER_FLATTEN_DEV_DEG:
                continue
            for pt in _cubic_bezier(a_xy, a_ctrl, mirrored, b_xy,
                                    _effective_bezier_segments(
                                        a_xy, (a_ctrl, mirrored), b_xy,
                                        bezier_segments))[1:-1]:
                if not out or out[-1] != pt:
                    out.append(pt)
            continue
        mid = (0.5 * (a_xy[0] + b_xy[0]),
               0.5 * (a_xy[1] + b_xy[1]))
        if 0.5 * math.hypot(ctrl_eff[0] - mid[0],
                            ctrl_eff[1] - mid[1]) \
                < BEZIER_FLATTEN_DEV_DEG:
            continue
        for pt in _quadratic_bezier(a_xy, ctrl_eff, b_xy,
                                    _effective_bezier_segments(
                                        a_xy, (ctrl_eff,), b_xy,
                                        bezier_segments))[1:-1]:
            if not out or out[-1] != pt:
                out.append(pt)
    b_last = _node_xy(node_rows[-1])
    if not out or out[-1] != b_last:
        out.append(b_last)
    return out


def _split_contours(node_rows: list[list[str]]) -> list[list[list[str]]]:
    """Walk a list of 111/112/113/114 rows and split into contours.

    A contour starts at the first row after the header (or after the
    previous contour's closing row) and ends at the next 113 / 114
    closing row.  Each returned contour is a list of node rows
    INCLUDING its closing 113/114 row.
    """
    contours: list[list[list[str]]] = []
    current: list[list[str]] = []
    for row in node_rows:
        if not row:
            continue
        try:
            row_type = int(row[0])
        except ValueError:
            continue
        if row_type not in (ROW_NODE, ROW_NODE_BEZIER,
                            ROW_CLOSE, ROW_CLOSE_BEZIER):
            continue
        current.append(row)
        if row_type in (ROW_CLOSE, ROW_CLOSE_BEZIER):
            contours.append(current)
            current = []
    # Drop a trailing un-closed contour.
    return contours


# ──────────────────────────────────────────────────────────────────────
# Internal: Bezier interpolation
# ──────────────────────────────────────────────────────────────────────
def _node_xy(row: list[str]) -> tuple[float, float]:
    """Return (lon, lat) for a node row (we use lon-first internally
    so shapely Polygons get the standard (x, y) order)."""
    return (float(row[2]), float(row[1]))


def _node_ctrl(row: list[str]) -> tuple[float, float] | None:
    """Return the Bezier control point for a 112/114/116 node, or
    None for a plain 111/113/115 node.
    """
    try:
        rt = int(row[0])
    except ValueError:
        return None
    if rt not in (ROW_NODE_BEZIER, ROW_CLOSE_BEZIER,
                  ROW_END_LINE_BEZIER):
        return None
    try:
        return (float(row[4]), float(row[3]))
    except (IndexError, ValueError):
        return None


def _sparsify_ring_points(points, closed, latitude):
    """Resample a tessellated ring/polyline to the MINIMUM vertex set
    that keeps its shape within ``CURVE_SAGITTA_MAX_M`` (user 2026-07-05:
    minimum nodes for a smooth profile).  The bezier rule alone barely
    moves the node count — most apt.dat density is AUTHORED as dense
    plain-node chains (HECA hand-tessellates its curves), so the same
    sagitta bound is applied to the assembled points via Douglas-Peucker.
    Endpoints (and for a ring, the first vertex and its antipode) are
    always kept, so a closed ring stays closed and abutting-shape
    conformance derives downstream from the same resampled geometry.
    Coordinates are (lon, lat) degrees; the tolerance converts at this
    ring's latitude."""
    if not ADAPTIVE_BEZIER or len(points) < (4 if closed else 3):
        return points
    lat_scale = 111320.0
    lon_scale = 111320.0 * math.cos(math.radians(latitude))
    tolerance_m = CURVE_SAGITTA_MAX_M

    def _perpendicular_m(point, start, end):
        sx = (end[0] - start[0]) * lon_scale
        sy = (end[1] - start[1]) * lat_scale
        px = (point[0] - start[0]) * lon_scale
        py = (point[1] - start[1]) * lat_scale
        seg_len = math.hypot(sx, sy)
        if seg_len < 1e-9:
            return math.hypot(px, py)
        return abs(px * sy - py * sx) / seg_len

    def _douglas_peucker(section):
        if len(section) <= 2:
            return section
        worst_index = 0
        worst_dev = -1.0
        for k in range(1, len(section) - 1):
            dev = _perpendicular_m(section[k], section[0], section[-1])
            if dev > worst_dev:
                worst_dev = dev
                worst_index = k
        if worst_dev <= tolerance_m:
            return [section[0], section[-1]]
        left = _douglas_peucker(section[:worst_index + 1])
        right = _douglas_peucker(section[worst_index:])
        return left[:-1] + right

    try:
        if closed:
            # Split at the first vertex and its antipode so the recursion
            # has two stable anchors; both survive, keeping the ring
            # closed and the result deterministic in the source geometry.
            half = len(points) // 2
            first = _douglas_peucker(points[:half + 1])
            second = _douglas_peucker(points[half:] + points[:1])
            out = first[:-1] + second[:-1]
            return out if len(out) >= 3 else points
        return _douglas_peucker(points)
    except RecursionError:
        # A pathological ring must degrade to the dense original, never
        # kill the airport build.
        return points


def _effective_bezier_segments(a_xy, control_points, b_xy,
                               legacy_segments):
    """Per-span ADAPTIVE segment count (see the ADAPTIVE_BEZIER constant
    block), or ``legacy_segments`` with the gate off.  Coordinates are
    (lon, lat) degrees; thresholds are metres, converted at this span's
    latitude.  Deterministic in the span's control points alone, so
    every shape sharing the curve tessellates identically."""
    if not ADAPTIVE_BEZIER:
        return legacy_segments
    lat_scale = 111320.0
    lon_scale = 111320.0 * math.cos(math.radians(a_xy[1]))

    def _meters(p, q):
        return math.hypot((p[0] - q[0]) * lon_scale,
                          (p[1] - q[1]) * lat_scale)

    control_list = list(control_points)
    span_m = 0.0
    previous = a_xy
    for point in control_list + [b_xy]:
        span_m += _meters(previous, point)
        previous = point
    chord_m = _meters(a_xy, b_xy)
    if chord_m < 1e-9:
        return max(1, legacy_segments)
    # Deviation bound: the curve never strays farther from the chord
    # than its control polygon does.
    unit_x = (b_xy[0] - a_xy[0]) * lon_scale / chord_m
    unit_y = (b_xy[1] - a_xy[1]) * lat_scale / chord_m
    deviation_m = 0.0
    for (cx, cy) in control_list:
        wx = (cx - a_xy[0]) * lon_scale
        wy = (cy - a_xy[1]) * lat_scale
        perpendicular = abs(wx * unit_y - wy * unit_x)
        if perpendicular > deviation_m:
            deviation_m = perpendicular
    if deviation_m <= 1e-9:
        return 1
    segments_for_sagitta = math.ceil(math.sqrt(
        deviation_m / max(1e-6, CURVE_SAGITTA_MAX_M)))
    segments_for_spacing = int(
        span_m // max(0.5, CURVE_MIN_VERTEX_SPACING_M))
    return max(1, min(segments_for_sagitta, segments_for_spacing))


def _quadratic_bezier(p0, p1, p2, n_segments):
    """Sample a quadratic Bezier from p0 → p2 with control p1.
    Returns a list of (n_segments + 1) points starting at p0 and
    ending at p2.
    """
    pts = []
    for i in range(n_segments + 1):
        t = i / n_segments
        omt = 1.0 - t
        x = omt * omt * p0[0] + 2 * omt * t * p1[0] + t * t * p2[0]
        y = omt * omt * p0[1] + 2 * omt * t * p1[1] + t * t * p2[1]
        pts.append((x, y))
    return pts


def _cubic_bezier(p0, p1, p2, p3, n_segments):
    """Sample a cubic Bezier from p0 → p3 with controls p1, p2.
    Returns a list of (n_segments + 1) points.
    """
    pts = []
    for i in range(n_segments + 1):
        t = i / n_segments
        omt = 1.0 - t
        b0 = omt * omt * omt
        b1 = 3 * omt * omt * t
        b2 = 3 * omt * t * t
        b3 = t * t * t
        x = b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0]
        y = b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1]
        pts.append((x, y))
    return pts


def _mirror(point, anchor):
    """Reflect `point` through `anchor`."""
    return (2 * anchor[0] - point[0], 2 * anchor[1] - point[1])


def _interpolate_contour(contour: list[list[str]],
                         bezier_segments: int) -> list[tuple[float, float]]:
    """Convert a contour (list of 111/112 rows ending in 113/114)
    into a flat list of (x, y) polygon vertices, sampling Bezier
    curves into straight-line segments.

    Bezier convention used here (matches X-Plane apt.dat 1100 spec):

    For each consecutive pair of nodes A → B:

    * If neither carries a control point: straight line A → B.
    * If only A has a control point (a 112 followed by a 111/113):
      quadratic Bezier from A through ctrl_a to B.
    * If only B has a control point (a 111 followed by a 112/114):
      quadratic Bezier from A through (mirror of ctrl_b across B) to B.
    * If both A and B carry control points: cubic Bezier from A,
      with controls ctrl_a and (mirror of ctrl_b across B), to B.
    """
    n = len(contour)
    if n < 2:
        return []

    # Build a closed ring of nodes (the closing 113/114 brings us
    # back to the first vertex; segment "last → first" closes the
    # contour).
    ring_nodes = list(contour)

    out: list[tuple[float, float]] = []
    for i in range(n):
        a_row = ring_nodes[i]
        b_row = ring_nodes[(i + 1) % n]
        a_xy = _node_xy(a_row)
        b_xy = _node_xy(b_row)
        a_ctrl = _node_ctrl(a_row)
        b_ctrl = _node_ctrl(b_row)

        # Append A only (B will be appended by the next iteration).
        if not out or out[-1] != a_xy:
            out.append(a_xy)

        # Zero-length span between split-handle duplicates.  WED encodes a
        # SPLIT bezier handle (independent in/out direction) as a RUN of
        # same-anchor nodes — the point before the break carries the
        # INCOMING handle, the point after the OUTGOING handle.  There is
        # no curve to draw across the zero-length gap; the duplicates'
        # handles already serve the adjacent real segments.  Without this
        # skip the degenerate span tessellates into a self-intersecting
        # SPIKE, which ``buffer(0)`` then repairs into a spurious HOLE
        # (or, for larger crossings, a MultiPolygon whose smaller pieces
        # are dropped) — losing real pavement (HECA's taxiway-fillet
        # pavements parsed with a teardrop hole).  Mirrors the DSF
        # reader's ``_interpolate_dsf_ring`` handling.
        if a_xy == b_xy:
            continue

        if a_ctrl is None and b_ctrl is None:
            # Straight line — nothing to interpolate, B will be added
            # next iteration.
            continue

        # Per user 2026-05-04: skip tessellation for Beziers whose
        # max chord deviation is below ``BEZIER_FLATTEN_DEV_DEG``.
        # These are "corner-softening" Beziers (~1 m visual rounding)
        # that don't matter for X-Plane mesh purposes but cause
        # downstream residue/junction artefacts when expanded into
        # multi-vertex arcs.
        if a_ctrl is not None and b_ctrl is None:
            ctrl_eff = a_ctrl
        elif a_ctrl is None and b_ctrl is not None:
            ctrl_eff = _mirror(b_ctrl, b_xy)
        else:
            # Cubic — measure deviation as max(|ctrl1 - midpoint|,
            # |ctrl2_mirrored - midpoint|) which bounds the curve.
            mirrored = _mirror(b_ctrl, b_xy)
            mid = (0.5 * (a_xy[0] + b_xy[0]),
                   0.5 * (a_xy[1] + b_xy[1]))
            d1 = math.hypot(a_ctrl[0] - mid[0], a_ctrl[1] - mid[1])
            d2 = math.hypot(mirrored[0] - mid[0],
                            mirrored[1] - mid[1])
            cubic_dev = 0.5 * max(d1, d2)
            if cubic_dev < BEZIER_FLATTEN_DEV_DEG:
                # Treat as straight line A→B.
                continue
            curve = _cubic_bezier(a_xy, a_ctrl, mirrored, b_xy,
                                  _effective_bezier_segments(
                                      a_xy, (a_ctrl, mirrored), b_xy,
                                      bezier_segments))
            for pt in curve[1:-1]:
                if not out or out[-1] != pt:
                    out.append(pt)
            continue
        # Quadratic Bezier path: max chord deviation is at t=0.5 and
        # equals 0.5 * dist(ctrl, midpoint(a, b)).
        mid = (0.5 * (a_xy[0] + b_xy[0]),
               0.5 * (a_xy[1] + b_xy[1]))
        quad_dev = 0.5 * math.hypot(ctrl_eff[0] - mid[0],
                                      ctrl_eff[1] - mid[1])
        if quad_dev < BEZIER_FLATTEN_DEV_DEG:
            # Treat as straight line A→B.
            continue
        curve = _quadratic_bezier(
            a_xy, ctrl_eff, b_xy,
            _effective_bezier_segments(a_xy, (ctrl_eff,), b_xy,
                                       bezier_segments))
        # Drop the first point (= a_xy, already in out) and the last
        # (= b_xy, will be appended next iteration).  Append only the
        # interior curve samples.
        for pt in curve[1:-1]:
            if not out or out[-1] != pt:
                out.append(pt)
    return out

