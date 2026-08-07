"""Airside ENCLAVE REGIONS — one computation, three consumers.

An **enclave** is a bounded complement component of the airside∪building
union: a region of the airport that airside pavement (plus buildings,
which a vehicle cannot drive through) completely surrounds, with no
tunnel/bridge escape.  Owner law, G-ENCLAVE 2026-07-28 and its
2026-08-07 extension:

    "groundside can never be surrounded by airside pavement unless it
     has a tunnel or bridge service road to get out"
    "the principle covers EVERYTHING inside an airside-surrounded
     enclave, paved or bare — such an area is airside-interior and takes
     the GAP INTERIOR RING + SPINE treatment; a retaining wall or
     groundside terrace there is a defect regardless of which mechanism
     minted it."

Why a module of its own (spec ``docs/specs/enclave-region-law-spec.md``
§1, single-pass principle).  The geometry used to be built TWICE from
byte-identical role sets — ``pavement_scoring``'s ``airside_zone`` (a
buffered union, consumed as ring COVERAGE of one shape) and
``gap_fill._gap_detection_polys`` (the interior rings of the pavement
union).  Neither published anything, so the classifier's enclave test
was a per-shape predicate that only a shape FILLING the void could pass:
87.6 % of the specimen enclave is bare ground outside the shape universe
entirely, and the void's one pavement shape read 0.0 % ring coverage
(attribution: ``tmp/enclave_attrib/enclave_dossier.md`` §2).  Moving the
unit from the SHAPE to the REGION is the fix; publishing the region once
is what lets the three consumers agree about it:

  1. ``pavement_scoring.enact_classify`` — G-ENCLAVE is now
     point-in-enclave (no ring coverage, no ``GAP_M`` tolerance, no
     candidate-area floor, no birth-role restriction);
  2. ``gap_fill`` — a foreign shape inside a published enclave no longer
     vetoes the ruled ring+spine treatment of the ground around it;
  3. ``adjacent_ground`` — the band/wall consumer stands down inside a
     region the ruled treatment OWNS (see
     ``enclave_band_keepout_union``).

The published set is computed ONCE per build, in ``enact_classify``,
BEFORE the re-verdicts it feeds (a shape promoted out of GROUNDSIDE
becomes airside and would close its own enclave).  Later consumers read
the store; ``airside_enclaves`` recomputes lazily only when nothing was
published (scoring off, synthetic test layouts).

TWO UNIONS, ONE LAW — the ratified scoping (spec Phase-1 outcome
banner).  Consumers 1 and 2 answer "is this ground airside-interior?",
which is a question about what a VEHICLE can cross, so their surround
is airside ∪ BUILDINGS.  Consumer 3 answers a different question —
"does the ruled ring+spine treatment OWN this ground, so the band must
stand down?" — and the only authority on that is the gap law itself,
whose candidate geometry is the PAVEMENT-ONLY union.  Phase 1 fed
consumer 3 from the airside∪building set and deleted 175,671 m² of
band at HECA, 152,734 m² of it Annex 14 §3.4.11-13 graded strip: the
buildings standing in the 3.4 km² infield subdivide it into
pocket-width components, so ground the gap law holds as ONE region and
declines on WIDTH read as many pockets and the bands stood down over
all of them — a keep-out over ground nothing then owned.  The two
unions are therefore two LAWS, not two copies of one (the classifier's
question and the treatment-ownership question have different right
answers), and ``compute_gap_law_regions`` reads the gap law's OWN
detection function rather than reconstructing it here.
"""

from __future__ import annotations

from dataclasses import dataclass

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree

import O4_UI_Utils as UI

_GEOM_EXC = (ValueError, GEOSException, TopologicalError)

from .config import GAP_FILL_MAX_WIDTH_M
from .geom_safe import min_rotated_rect
from .layout import (
    ROLE_APRON,
    ROLE_BRIDGE_CAUSEWAY,
    ROLE_BRIDGE_TRENCH,
    ROLE_BUILDING,
    ROLE_CROSS_CONNECTOR,
    ROLE_JUNCTION,
    ROLE_PRIMARY_PARALLEL,
    ROLE_RUNWAY,
    ROLE_RUNWAY_CROSSING,
    ROLE_SECONDARY_PARALLEL,
    ROLE_STUB,
    ROLE_TUNNEL_RAMP,
    ROLE_TUNNEL_TRENCH,
)

# The surround.  Airside pavement a vehicle cannot cross without being on
# the airfield — the same eight roles ``clearance._AIRSIDE_PAVEMENT_ROLES``
# and ``pavement_scoring._CHAIN_ROLES`` carry (all three sets are pinned
# equal by ``tests/test_enclave_region.py``; they are three different laws
# that agree today, and a divergence must be a conscious act).
ENCLAVE_AIRSIDE_ROLES = frozenset({
    ROLE_RUNWAY, ROLE_RUNWAY_CROSSING, ROLE_PRIMARY_PARALLEL,
    ROLE_SECONDARY_PARALLEL, ROLE_STUB, ROLE_CROSS_CONNECTOR,
    ROLE_JUNCTION, ROLE_APRON,
})
# Buildings JOIN the surround (owner, CYXY building4 2026-07-28): a
# vehicle cannot leave through a building.
ENCLAVE_SURROUND_ROLES = ENCLAVE_AIRSIDE_ROLES | {ROLE_BUILDING}
# The owner's escape clause: a touching tunnel/bridge service road means
# the region is NOT an enclave.
ENCLAVE_ESCAPE_ROLES = frozenset({
    ROLE_TUNNEL_RAMP, ROLE_TUNNEL_TRENCH,
    ROLE_BRIDGE_TRENCH, ROLE_BRIDGE_CAUSEWAY,
})
# An escape shape this close to the region's ring gets out of it.  The
# value the shape-scoped predicate has always used.
ENCLAVE_ESCAPE_CONTACT_M = 1.0
# A gap polygon is enclave ground when at least this fraction of its area
# lies inside one published enclave (the gap candidates come from the
# pavement-only union, the enclaves from the airside∪building one, so a
# building on the rim can trim one against the other).
ENCLAVE_COVER_FRAC = 0.5

# The store: the published list and its derived geometry caches.
ENCLAVE_STORE_ATTRIBUTE = "airside_enclaves"
_STAGE_ATTRIBUTE = "_airside_enclave_stage"
_UNION_ATTRIBUTE = "_airside_enclave_union"
_INDEX_ATTRIBUTE = "_airside_enclave_index"
_GAP_REGIONS_ATTRIBUTE = "_gap_law_regions"
_KEEPOUT_ATTRIBUTE = "_airside_enclave_keepout"
_KEEPOUT_PREP_ATTRIBUTE = "_airside_enclave_keepout_prep"


@dataclass(frozen=True)
class Enclave:
    """One bounded complement component of the airside∪building union.

    ``polygon`` is the region itself (the union component's interior
    ring, as a filled polygon), ``short_side_m`` its minimum-rotated-rect
    short side — the gap law's own pocket-width metric — and
    ``escape_ids`` the ids of the tunnel/bridge shapes that let a vehicle
    out of it.  A record with ``escape_ids`` is NOT published: the
    owner's escape clause makes it not an enclave at all.
    """

    polygon: Polygon
    area_m2: float
    short_side_m: float | None
    escape_ids: tuple


def _surround_polygons(layout):
    """The polygons whose union bounds an enclave."""
    return [s.polygon for s in layout.shapes
            if s.role in ENCLAVE_SURROUND_ROLES
            and s.polygon is not None and not s.polygon.is_empty
            and s.polygon.geom_type in ("Polygon", "MultiPolygon")]


def _escape_shapes(layout):
    """The tunnel/bridge shapes that defeat an enclosure."""
    return [s for s in layout.shapes
            if s.polygon is not None and not s.polygon.is_empty
            and (s.role in ENCLAVE_ESCAPE_ROLES
                 or getattr(s, "is_bridge", False))]


def compute_airside_enclaves(layout) -> list:
    """THE enclave computation — bounded complement components of the
    airside∪building union, escape clause applied.

    Returns the PUBLISHABLE records only (escape-bearing regions are
    dropped here, so a consumer can never forget the clause).  Pure
    geometry: no roles are changed, nothing is stored.
    """
    polys = _surround_polygons(layout)
    if len(polys) < 2:
        return []
    try:
        union = unary_union(polys)
    except _GEOM_EXC:
        return []
    if union is None or union.is_empty:
        return []
    comps = ([union] if union.geom_type == "Polygon"
             else [g for g in getattr(union, "geoms", [])
                   if g.geom_type == "Polygon"])
    regions: list[Polygon] = []
    for comp in comps:
        for interior in comp.interiors:
            try:
                region = Polygon(list(interior.coords))
            except _GEOM_EXC:
                continue
            if region.is_empty or not region.is_valid or region.area <= 0.0:
                continue
            regions.append(region)
    return _publishable_records(layout, regions)


def _publishable_records(layout, regions) -> list:
    """Apply the owner's ESCAPE CLAUSE and measure pocket width — the
    step both region computations share, so the clause is written once
    and no consumer can be handed a region that still carries an escape.
    """
    if not regions:
        return []
    escapes = _escape_shapes(layout)
    escape_polys = [s.polygon for s in escapes]
    etree = STRtree(escape_polys) if escape_polys else None
    out: list[Enclave] = []
    for region in regions:
        if region is None or region.is_empty or not region.is_valid \
                or region.area <= 0.0:
            continue
        escape_ids: list = []
        if etree is not None:
            try:
                probe = region.buffer(ENCLAVE_ESCAPE_CONTACT_M)
            except _GEOM_EXC:
                probe = region
            for i in etree.query(probe):
                shape = escapes[int(i)]
                try:
                    if shape.polygon.distance(region) \
                            <= ENCLAVE_ESCAPE_CONTACT_M:
                        escape_ids.append(id(shape))
                except _GEOM_EXC:
                    continue
        if escape_ids:
            # The owner's escape clause: a vehicle can get out, so this
            # region is not an enclave.
            continue
        try:
            axes = min_rotated_rect(region)
            short = _short_side(axes)
        except _GEOM_EXC:
            short = None
        out.append(Enclave(polygon=region, area_m2=float(region.area),
                           short_side_m=short, escape_ids=()))
    return out


def compute_gap_law_regions(layout) -> list:
    """THE GAP LAW'S OWN REGIONS — bounded complement components of the
    PAVEMENT-ONLY union, escape clause applied.

    This is the geometry the band KEEP-OUT is scoped by, and it is read
    from ``gap_fill``'s own detection function rather than rebuilt here:
    the keep-out exists to stand the band down over ground the ruled
    ring + spine treatment OWNS, so the two must agree about which
    ground that is, and a second slightly-different construction of the
    same regions is exactly the duplicate the tool-discipline ruling
    calls a defect.  Reading the one function also inherits the gap
    law's SEAM HEALING and tile clipping for free — a pocket whose
    enclosing ring continues into the neighbour tile is one region for
    both laws or neither.

    NOT the same set as ``airside_enclaves`` and deliberately so (see
    the module docstring): buildings join the CLASSIFIER's surround
    because a vehicle cannot drive through one, but they are not
    pavement, and letting them subdivide an airfield infield into
    pocket-width components made the band stand down over 152,734 m² of
    Annex 14 graded strip that the gap law declines on width and the
    bands own.
    """
    # Deferred: ``gap_fill`` imports this module at module scope.
    from .gap_fill import _airside_shapes, _gap_detection_polys
    airside = _airside_shapes(layout)
    if len(airside) < 2:
        return []
    try:
        regions = _gap_detection_polys(layout, airside)
    except _GEOM_EXC:
        return []
    return _publishable_records(layout, regions)


def gap_law_regions(layout) -> list:
    """The gap law's regions for this layout, memoized.

    Cleared by every ``publish_airside_enclaves`` (so the settled
    republication re-reads the settled pavement union), and otherwise
    computed ONCE — which is also what keeps the pre-solve band march
    and the emit band march on the identical zone, the parity their
    station sequences depend on.
    """
    records = getattr(layout, _GAP_REGIONS_ATTRIBUTE, None)
    if records is not None:
        return records
    records = compute_gap_law_regions(layout)
    try:
        setattr(layout, _GAP_REGIONS_ATTRIBUTE, records)
    except AttributeError:
        pass
    return records


def _short_side(mrr):
    """Minimum-rotated-rect SHORT SIDE in metres, or ``None``."""
    if mrr is None or mrr.is_empty:
        return None
    try:
        ring = list(mrr.exterior.coords)
    except (AttributeError, _GEOM_EXC):
        return None
    if len(ring) < 4:
        return None
    sides = []
    for i in range(len(ring) - 1):
        dx = ring[i + 1][0] - ring[i][0]
        dy = ring[i + 1][1] - ring[i][1]
        sides.append((dx * dx + dy * dy) ** 0.5)
    if not sides:
        return None
    return float(min(sides[:2]) if len(sides) >= 2 else sides[0])


def publish_airside_enclaves(layout, stage: str = "classify") -> list:
    """Compute the enclave set and PUBLISH it on ``layout``.

    TWO STAGES, ONE COMPUTATION — and they are two FRAMES, not two
    copies of one task (measured at HECA, and the reason this parameter
    exists at all):

      * ``classify`` — from ``pavement_scoring.enact_classify``, before
        the enclave re-verdicts.  It MUST be here: a shape promoted out
        of GROUNDSIDE becomes airside and would close the very region
        being measured.  The pavement union is still mid-build, so it is
        more FRAGMENTED than the surface that ships: HECA publishes 192
        regions here (183 of them pocket-width, 1,427,961 m²) against
        161/150 (1,363,167 m²) once the geometry settles.
      * ``settled`` — once, before the pre-solve stage, when the pavement
        geometry is final.  This is the frame the GAP FACES and the BAND
        MARCH live in, and reading the classification frame there cost
        152,734 m² of Annex 14 §3.4.11-13 runway/taxiway graded strip at
        HECA: infield ground that the settled union holds in ONE 3.4 km²
        region (short side 1,264 m — never band keep-out) reads as
        several POCKET-width regions in the fragmented frame, and the
        band consumer stood down over all of them.

    The re-publication REPLACES the store and clears every derived cache,
    so there is never more than one live enclave set and no consumer can
    read a frame it was not built for.
    """
    records = compute_airside_enclaves(layout)
    setattr(layout, ENCLAVE_STORE_ATTRIBUTE, records)
    setattr(layout, _STAGE_ATTRIBUTE, stage)
    for attr in (_UNION_ATTRIBUTE, _INDEX_ATTRIBUTE,
                 _GAP_REGIONS_ATTRIBUTE,
                 _KEEPOUT_ATTRIBUTE, _KEEPOUT_PREP_ATTRIBUTE):
        if hasattr(layout, attr):
            setattr(layout, attr, None)
    if records:
        pocket = [e for e in records if _is_pocket(e)]
        UI.vprint(1,
            f"  [enclave] published {len(records)} airside enclave(s), "
            f"{sum(e.area_m2 for e in records):.0f} m2 "
            f"({len(pocket)} pocket-width, "
            f"{sum(e.area_m2 for e in pocket):.0f} m2) "
            f"[frame={stage}].")
    return records


def republish_airside_enclaves_settled(layout) -> list:
    """Re-publish the enclave regions in the SETTLED geometry frame.

    Called once from the pipeline at the pre-solve boundary — after every
    pavement shape exists and after the classification re-verdicts, before
    the gap-fill construction and the band march that consume it.  A no-op
    when nothing was published (no classifier ran): the lazy accessor
    then computes in this frame anyway.
    """
    if getattr(layout, ENCLAVE_STORE_ATTRIBUTE, None) is None:
        return []
    return publish_airside_enclaves(layout, stage="settled")


def airside_enclaves(layout) -> list:
    """The published enclave records — THE consumer entry point.

    Lazily computes and publishes when nothing was published (scoring
    off, synthetic layouts); never recomputes over a published store.
    """
    records = getattr(layout, ENCLAVE_STORE_ATTRIBUTE, None)
    if records is None:
        records = publish_airside_enclaves(layout)
    return records


def _is_pocket(enclave) -> bool:
    """POCKET-WIDTH: narrow enough that the owner's ruled ring+spine
    treatment is the form for it.

    The discriminator is the GAP LAW'S OWN pocket width
    (``GAP_FILL_MAX_WIDTH_M``) — never a second number here.  It is what
    separates an enclosed pocket from an airfield INFIELD: a big
    airport's runway/taxiway loops make the whole infield one bounded
    complement component (HECA: 3.38 km², short side far past the gap
    law's width), and that ground is the graded strips' territory —
    Annex 14 §3.4.11-13 prepares it.  The owner's "takes the gap
    interior ring and spine treatment" presupposes ground the gap law
    can treat, so the band stand-down is scoped to exactly that class.
    """
    short = enclave.short_side_m
    return short is not None and short <= GAP_FILL_MAX_WIDTH_M


def _enclave_index(layout):
    """Memoized ``(STRtree, records)`` over the published polygons."""
    idx = getattr(layout, _INDEX_ATTRIBUTE, None)
    if idx is not None:
        return idx
    records = airside_enclaves(layout)
    if not records:
        idx = (None, [])
    else:
        try:
            idx = (STRtree([e.polygon for e in records]), list(records))
        except _GEOM_EXC:
            idx = (None, list(records))
    try:
        setattr(layout, _INDEX_ATTRIBUTE, idx)
    except AttributeError:
        pass
    return idx


def enclave_at_point(layout, x: float, y: float):
    """The published enclave CONTAINING ``(x, y)``, or ``None``.

    THE G-ENCLAVE predicate (spec §2): point-in-enclave, not ring
    coverage — no tolerance to tune, no requirement that a shape FILL
    the region, and bare ground inside the region is reached by the same
    test that reaches pavement.
    """
    tree, records = _enclave_index(layout)
    if not records:
        return None
    pt = Point(x, y)
    if tree is None:
        candidates = range(len(records))
    else:
        try:
            candidates = [int(i) for i in tree.query(pt)]
        except _GEOM_EXC:
            candidates = range(len(records))
    for i in candidates:
        enclave = records[i]
        try:
            if enclave.polygon.contains(pt):
                return enclave
        except _GEOM_EXC:
            continue
    return None


def point_in_enclave(layout, x: float, y: float) -> bool:
    """``enclave_at_point`` as a predicate."""
    return enclave_at_point(layout, x, y) is not None


def shape_in_enclave(layout, shape) -> bool:
    """True when ``shape``'s representative point lies in an enclave.

    ``representative_point`` (not the centroid) so a horseshoe-shaped
    lot is judged by a point that is genuinely inside itself.
    """
    poly = getattr(shape, "polygon", None)
    if poly is None or poly.is_empty:
        return False
    try:
        rp = poly.representative_point()
    except _GEOM_EXC:
        return False
    return point_in_enclave(layout, rp.x, rp.y)


def enclave_covering(layout, poly):
    """The published enclave this polygon is INTERIOR GROUND OF, or
    ``None``.

    Used by ``gap_fill``: the gap candidates are holes of the
    pavement-only union while the enclaves are holes of the
    airside∪building one, so the two geometries can differ where a
    building sits on a rim.  A gap counts as enclave ground when
    ``ENCLAVE_COVER_FRAC`` of its area lies inside one enclave.
    """
    if poly is None or poly.is_empty:
        return None
    tree, records = _enclave_index(layout)
    if not records:
        return None
    try:
        need = ENCLAVE_COVER_FRAC * poly.area
    except _GEOM_EXC:
        return None
    if need <= 0.0:
        return None
    if tree is None:
        candidates = range(len(records))
    else:
        try:
            candidates = [int(i) for i in tree.query(poly)]
        except _GEOM_EXC:
            candidates = range(len(records))
    for i in candidates:
        enclave = records[i]
        try:
            if enclave.polygon.intersection(poly).area >= need:
                return enclave
        except _GEOM_EXC:
            continue
    return None


def enclave_band_keepout_union(layout):
    """The BAND KEEP-OUT zone — the POCKET-width regions of the GAP
    LAW's own union, or ``None`` (spec §4, ratified scoping).

    THE consumer entry point for ``adjacent_ground``, in the shape of the
    crossing-influence and collared-pocket zones it already consumes: a
    hard keep-out the station march tests each seed and outward probe
    against.  An enclave interior is airside-interior by law, so the
    band/wall consumer never runs there — a retaining wall inside an
    enclave is a defect regardless of which mechanism minted it (owner
    2026-08-07).

    SCOPE, and the whole of it: the regions of ``gap_law_regions`` that
    are POCKET-width (``_is_pocket``) — i.e. exactly the ground the
    ruled ring + spine treatment owns.  Not ``airside_enclaves``: that
    set answers the classifier's question and includes buildings in its
    surround, and scoping the keep-out by it deleted 152,734 m² of
    Annex 14 infield graded strip at HECA (module docstring).  A region
    the gap law declines on WIDTH is band territory, and one it owns is
    not; there is no third answer and no second width number here.
    """
    union = getattr(layout, _KEEPOUT_ATTRIBUTE, None)
    if union is not None:
        return None if union.is_empty else union
    regions = gap_law_regions(layout)
    records = [e for e in regions if _is_pocket(e)]
    UI.vprint(1,
        f"  [enclave] band keep-out: {len(records)} of {len(regions)} "
        f"gap-law region(s) are pocket-width "
        f"(<= {GAP_FILL_MAX_WIDTH_M:.0f} m), "
        f"{sum(e.area_m2 for e in records):.0f} m2 of "
        f"{sum(e.area_m2 for e in regions):.0f} m2 "
        f"[frame=pavement-only union].")
    union = None
    if records:
        try:
            union = unary_union([e.polygon for e in records])
        except _GEOM_EXC:
            union = None
    if union is None:
        union = Polygon()
    # An EMPTY union is cached too: the answer "no keep-out" is as
    # settled as any other, and re-deriving it would re-log the line
    # above once per consumer.
    try:
        setattr(layout, _KEEPOUT_ATTRIBUTE, union)
    except AttributeError:
        pass
    return None if union.is_empty else union


def enclave_band_keepout_prepared(layout):
    """Prepared-geometry form of the band keep-out for the march's
    per-station containment test, or ``None``."""
    prepared = getattr(layout, _KEEPOUT_PREP_ATTRIBUTE, None)
    if prepared is not None:
        return prepared
    union = enclave_band_keepout_union(layout)
    if union is None:
        return None
    try:
        prepared = prep(union)
    except _GEOM_EXC:
        return None
    try:
        setattr(layout, _KEEPOUT_PREP_ATTRIBUTE, prepared)
    except AttributeError:
        pass
    return prepared
