"""Unit tests for the conformance insert-altitude rule, exercised with
synthetic geometry (no airport build / X-Plane install required).

Regression pins for the de-seg residual A2 fix (HECA 2026-07-08): the
final ``enforce_conformance`` weld used a crown-UNAWARE lerp of the host
edge's emitted altitudes, so inserting an already-solved vertex into a
neighbour's crown-discontinuous edge re-derived a value the solver never
produced (136.298 re-lerped to 136.415; the emit consensus averaged the
two claims to 136.36 — a 3.57 % within-shape pair beside runway 05R).

Covered (``conformance._make_insert_altitude`` resolution order):
  * COINCIDENT-ADOPT — a T-junction insert coinciding (canonical-point
    registry tolerance) with an already-emitted solved vertex adopts
    that vertex's altitude instead of the edge lerp.
  * WALL GUARD — a coincident donor farther in value than
    ``VERTEX_ALT_MERGE_TOL_M`` from the edge lerp (a deliberate
    wall/cliff, the emitter's node-split rule) is NOT adopted.
  * CROWN-AWARE INTERPOLATION — when the host edge's endpoints carry
    different crown drops and no donor value exists, the insert takes
    the z′-space interpolation minus its own drop (the transform
    ``crown.extend_field_to_new_ring_nodes`` uses).
  * BYTE-IDENTICAL FALLBACK — equal endpoint drops + no donor value
    yield exactly the historical plain lerp.
"""
from __future__ import annotations

import math

from shapely.geometry import Polygon

from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.conformance import (
    CONFORMANCE_TOL_M,
    _resolve_edge_crossings,
    _resolve_yielding_tjunctions,
    enforce_conformance,
    weld_candidate_pairs,
)
from auto_patch.layout import (
    BuiltShape,
    PavementLayout,
    ROLE_JUNCTION,
    ROLE_RUNWAY,
    SHARED_VERTEX_TOL_M,
)


def _make_layout(*shapes: BuiltShape) -> PavementLayout:
    """Layout with a seeded canonical-point registry (production seeds
    every shape corner through ``get_or_add``; the tests mirror that)."""
    layout = PavementLayout(icao="TEST", anchor=(0.0, 0.0),
                            shapes=list(shapes))
    registry = CanonicalPointRegistry(tol_m=SHARED_VERTEX_TOL_M)
    for s in shapes:
        for (x, y) in list(s.polygon.exterior.coords):
            registry.get_or_add(float(x), float(y))
    layout.canonical_points = registry
    return layout


def _receiver_square(alt_left: float, alt_right: float) -> BuiltShape:
    """Receiver: a 20×20 junction whose BOTTOM edge runs (0,0)→(20,0)
    with altitudes ``alt_left`` → ``alt_right`` (the host edge every
    test inserts into, at its midpoint (10, 0), t = 0.5)."""
    ring = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_JUNCTION,
                      node_altitudes=[alt_left, alt_right,
                                      alt_right, alt_left])


def _donor_triangle(apex_alt: float | None) -> BuiltShape:
    """Donor: a triangle BELOW the receiver touching it only at its apex
    (10, 0) — the classic T-junction (a vertex of one shape on the
    interior of another's edge).  ``apex_alt=None`` emits the shape with
    no altitude model at all (no donor VALUE, geometry only)."""
    ring = [(5.0, -10.0), (15.0, -10.0), (10.0, 0.0)]
    alts = None if apex_alt is None else [9.9, 9.9, float(apex_alt)]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_JUNCTION,
                      node_altitudes=alts)


def _alt_at(shape: BuiltShape, x: float, y: float) -> float:
    ring = list(shape.polygon.exterior.coords)[:-1]
    alts = list(shape.node_altitudes)
    if len(alts) == len(ring) + 1:
        alts = alts[:-1]
    assert len(alts) == len(ring)
    for (vx, vy), a in zip(ring, alts):
        if abs(vx - x) < 1e-9 and abs(vy - y) < 1e-9:
            return a
    raise AssertionError(f"no vertex at ({x}, {y}) in {ring}")


def test_insert_adopts_coincident_solved_vertex():
    """A T-junction insert coinciding with an already-emitted solved
    vertex ADOPTS that vertex's altitude — the weld makes the two nodes
    ONE, so re-deriving a second value via the edge lerp only creates a
    disagreement the emit consensus then averages into a step."""
    receiver = _receiver_square(10.0, 10.4)      # lerp at midpoint: 10.2
    donor = _donor_triangle(apex_alt=10.05)      # solver's value there
    layout = _make_layout(receiver, donor)
    enforce_conformance(layout)
    assert _alt_at(receiver, 10.0, 0.0) == 10.05


def test_insert_adopts_through_registry_radius_drift():
    """Node identity is the registry's RADIUS rule (the same rule
    ``to_osm`` assigns OSM node ids by), not exact coordinates: ring
    reshaping leaves emitted vertices centimetres off their registered
    canonical point (HECA A2: 0.07 m), and the adopt must still fire.

    (2026-07-29, canonical-identity guard) The insert now lands AT the
    canonical point — the exact position ``to_osm`` will intern the
    node to — instead of at the drifted candidate coordinate (a
    candidate whose canonical point falls OFF the host edge is skipped
    entirely; see the CYXY service-sliver bowtie).  The adopt fires as
    before, keyed by the same radius rule."""
    receiver = _receiver_square(10.0, 10.4)      # lerp at midpoint: 10.2
    donor = _donor_triangle(apex_alt=10.05)
    layout = PavementLayout(icao="TEST", anchor=(0.0, 0.0),
                            shapes=[receiver, donor])
    registry = CanonicalPointRegistry(tol_m=SHARED_VERTEX_TOL_M)
    # Register a canonical point slightly OFF the shared vertex first,
    # so (10, 0) interns to it and is never its own exact entry.
    registry.get_or_add(10.03, 0.03)
    for s in (receiver, donor):
        for (x, y) in list(s.polygon.exterior.coords):
            registry.get_or_add(float(x), float(y))
    layout.canonical_points = registry
    assert registry.find_nearest(10.0, 0.0, registry.tol_m) != (10.0, 0.0)
    enforce_conformance(layout)
    # The vertex sits at the CANONICAL point (emitted node position),
    # with the donor's adopted altitude.
    assert _alt_at(receiver, 10.03, 0.03) == 10.05


def test_authority_receiver_never_adopts():
    """A RUNWAY ring is a value AUTHORITY (the FAA profile stamps it) —
    an insert into it keeps the edge's own interpolation, never a
    neighbour's claim (measured at KCLT: adopting into runway rings
    minted within 9 → 25 and runway_grade 0 → 5)."""
    receiver = _receiver_square(10.0, 10.4)
    receiver.role = ROLE_RUNWAY
    donor = _donor_triangle(apex_alt=10.05)
    layout = _make_layout(receiver, donor)
    enforce_conformance(layout)
    assert _alt_at(receiver, 10.0, 0.0) == 10.0 + 0.5 * (10.4 - 10.0)


def test_insert_never_adopts_across_a_wall():
    """A coincident donor farther in value than the emitter's node-split
    rule (``VERTEX_ALT_MERGE_TOL_M``) is a deliberate wall/cliff — the
    insert keeps the edge's own interpolation."""
    receiver = _receiver_square(10.0, 10.4)      # lerp at midpoint: 10.2
    donor = _donor_triangle(apex_alt=2.0)        # 8 m below: a wall
    layout = _make_layout(receiver, donor)
    enforce_conformance(layout)
    assert _alt_at(receiver, 10.0, 0.0) == 10.0 + 0.5 * (10.4 - 10.0)


def test_insert_interpolates_crown_aware_across_drop_discontinuity():
    """With no donor VALUE and endpoint crown drops that differ, the
    insert interpolates in uncrowned space z′ = z + c and subtracts its
    own drop — a plain z-space lerp across the discontinuity is the A2
    defect (it manufactures a within-shape grade step)."""
    receiver = _receiver_square(10.0, 10.4)
    donor = _donor_triangle(apex_alt=None)       # geometry-only donor
    layout = _make_layout(receiver, donor)
    registry = layout.canonical_points
    cp_left = registry.get_or_add(0.0, 0.0)
    cp_insert = registry.get_or_add(10.0, 0.0)
    layout._crown_drop_key = {cp_left: 0.30, cp_insert: 0.10}
    enforce_conformance(layout)
    # z′ lerp: (10.0 + 0.30) + 0.5 × ((10.4 + 0) − (10.0 + 0.30)) = 10.35
    # minus the insert's own drop 0.10 → 10.25.
    expected = (10.0 + 0.30) + 0.5 * ((10.4 + 0.0) - (10.0 + 0.30)) - 0.10
    assert abs(_alt_at(receiver, 10.0, 0.0) - expected) < 1e-9


def test_insert_plain_lerp_when_drops_equal_and_no_donor():
    """Equal endpoint drops + no coincident donor value = the historical
    plain lerp, expression-identical (byte-identical emit)."""
    receiver = _receiver_square(10.0, 10.4)
    donor = _donor_triangle(apex_alt=None)       # geometry-only donor
    layout = _make_layout(receiver, donor)
    enforce_conformance(layout)                  # no crown field at all
    assert _alt_at(receiver, 10.0, 0.0) == 10.0 + 0.5 * (10.4 - 10.0)


# ---------------------------------------------------------------------------
# Duplicate-insert dedupe (SPJC ``runway_end_resa`` 2026-07-25): the insert
# loop deduped by EXACT tuple equality only, so two donor rings carrying
# bitwise-distinct vertices at the same location (float noise apart — each
# ring re-derived the point through its own geometry ops) both passed the
# tolerance checks and were both inserted, minting a zero-length edge in the
# receiver ring (inserts #26/#27 both printed (-824.764, 1609.243), from two
# adjacent_ground donors).  Coordinate-identical within ``tol`` ⇒ ONE insert.
# ---------------------------------------------------------------------------

def _min_edge_len(shape: BuiltShape) -> float:
    ring = list(shape.polygon.exterior.coords)[:-1]
    n = len(ring)
    return min(math.hypot(ring[(i + 1) % n][0] - ring[i][0],
                          ring[(i + 1) % n][1] - ring[i][1])
               for i in range(n))


def test_insert_dedupes_float_noise_twin_donors():
    """Two donors whose apexes differ only by float noise yield ONE
    inserted vertex — never the coordinate-identical pair whose
    zero-length edge degenerates the receiver ring."""
    receiver = _receiver_square(10.0, 10.4)
    d1 = BuiltShape(polygon=Polygon([(5.0, -10.0), (9.9, -10.0),
                                     (10.0, 0.0)]), role=ROLE_JUNCTION)
    d2 = BuiltShape(polygon=Polygon([(10.1, -10.0), (15.0, -10.0),
                                     (10.0 + 1e-7, 0.0)]),
                    role=ROLE_JUNCTION)
    layout = _make_layout(receiver, d1, d2)
    n_shapes, n_inserted = enforce_conformance(layout)
    assert (n_shapes, n_inserted) == (1, 1)
    ring = list(receiver.polygon.exterior.coords)[:-1]
    hits = [p for p in ring
            if math.hypot(p[0] - 10.0, p[1]) <= SHARED_VERTEX_TOL_M]
    assert len(hits) == 1
    assert _min_edge_len(receiver) > SHARED_VERTEX_TOL_M
    # node_altitudes stays index-aligned with the 5-vertex ring.
    assert len(receiver.node_altitudes) == len(ring) + 1


def test_insert_keeps_distinct_tjunctions_beyond_tolerance():
    """The dedupe must not swallow REAL neighbours: two donor apexes
    farther apart than the tolerance are two T-junctions and both
    insert."""
    receiver = _receiver_square(10.0, 10.4)
    d1 = BuiltShape(polygon=Polygon([(3.0, -10.0), (6.9, -10.0),
                                     (7.0, 0.0)]), role=ROLE_JUNCTION)
    d2 = BuiltShape(polygon=Polygon([(13.1, -10.0), (17.0, -10.0),
                                     (13.0, 0.0)]), role=ROLE_JUNCTION)
    layout = _make_layout(receiver, d1, d2)
    n_shapes, n_inserted = enforce_conformance(layout)
    assert (n_shapes, n_inserted) == (1, 2)
    ring = list(receiver.polygon.exterior.coords)[:-1]
    assert any(math.hypot(p[0] - 7.0, p[1]) < 1e-9 for p in ring)
    assert any(math.hypot(p[0] - 13.0, p[1]) < 1e-9 for p in ring)


# ---------------------------------------------------------------------------
# The same duplicate-insert guard on the OTHER two insert loops of the
# planarize pass, which ran unguarded until 2026-07-25.
#
# ``_resolve_yielding_tjunctions`` (a lower-priority shape conforming to a
# strictly higher-priority shape's vertex) appended every qualifying candidate
# with no dedupe at all, so it carried BOTH failure modes: the same candidate
# accepted on two edges of one ring, and two donors a float-noise apart.
#
# ``_resolve_edge_crossings`` deduped per edge by rounded ``t`` only, which
# misses a crossing landing a nanometre from the edge's own corner (``0 < t <
# 1`` admits it) and misses noise-apart twins whose ``t`` values straddle a
# rounding boundary.
# ---------------------------------------------------------------------------

def _yield_receiver(ring, alts=None) -> BuiltShape:
    """Receiver at junction tier (3), which yields to runway tier (0)."""
    return BuiltShape(polygon=Polygon(ring), role=ROLE_JUNCTION,
                      node_altitudes=alts)


def _runway_donor(apex) -> BuiltShape:
    """Donor at runway tier: its apex is the vertex the receiver conforms
    to; the base sits 10 m clear of any receiver edge."""
    return BuiltShape(polygon=Polygon([(apex[0] - 5.0, -10.0),
                                       (apex[0] + 5.0, -10.0), apex]),
                      role=ROLE_RUNWAY)


def test_yielding_dedupes_candidate_qualifying_on_two_edges():
    """A donor vertex inside the neck of a sliver receiver qualifies as a
    T-junction on BOTH of the sliver's long edges.  Inserting it twice
    makes the rebuilt ring self-touch, so the invalid-polygon bail throws
    away every insert for that shape and its T-vertices become immortal —
    the receiver here came back completely unwelded (0 inserts).

    The donor sits 0.1 m off both edges: outside ``planarize_airside``'s
    tight collinear-insert tolerance (0.05 m) on each, so this pass is the
    only one that can weld it and the guard has to hold here."""
    receiver = _yield_receiver([(0.0, 0.0), (20.0, 0.0), (0.0, 0.4)],
                               alts=[10.0, 10.4, 10.2])
    donor = _runway_donor((10.0, 0.1))
    layout = _make_layout(receiver, donor)
    assert _resolve_yielding_tjunctions(layout, tol=CONFORMANCE_TOL_M) == 1
    ring = list(receiver.polygon.exterior.coords)[:-1]
    assert receiver.polygon.is_valid
    assert sum(1 for p in ring
               if math.hypot(p[0] - 10.0, p[1] - 0.1) < 1e-9) == 1
    assert len(receiver.node_altitudes) == len(ring) + 1


def test_yielding_dedupes_float_noise_twin_donors():
    """Two runway donors whose apexes differ only by float noise yield ONE
    inserted vertex — never the coordinate-identical pair whose
    zero-length edge degenerates the receiver ring."""
    receiver = _yield_receiver([(0.0, 0.0), (20.0, 0.0),
                                (20.0, 20.0), (0.0, 20.0)],
                               alts=[10.0, 10.4, 10.4, 10.0])
    layout = _make_layout(receiver, _runway_donor((10.0, 0.0)),
                          _runway_donor((10.0 + 1e-7, 0.0)))
    assert _resolve_yielding_tjunctions(layout, tol=CONFORMANCE_TOL_M) == 1
    ring = list(receiver.polygon.exterior.coords)[:-1]
    hits = [p for p in ring
            if math.hypot(p[0] - 10.0, p[1]) <= SHARED_VERTEX_TOL_M]
    assert len(hits) == 1
    assert _min_edge_len(receiver) > SHARED_VERTEX_TOL_M
    assert len(receiver.node_altitudes) == len(ring) + 1


def test_yielding_keeps_distinct_tjunctions_beyond_tolerance():
    """The dedupe must not swallow REAL neighbours here either: two donor
    apexes farther apart than the tolerance both insert."""
    receiver = _yield_receiver([(0.0, 0.0), (20.0, 0.0),
                                (20.0, 20.0), (0.0, 20.0)],
                               alts=[10.0, 10.4, 10.4, 10.0])
    layout = _make_layout(receiver, _runway_donor((7.0, 0.0)),
                          _runway_donor((13.0, 0.0)))
    assert _resolve_yielding_tjunctions(layout, tol=CONFORMANCE_TOL_M) == 2
    ring = list(receiver.polygon.exterior.coords)[:-1]
    assert any(math.hypot(p[0] - 7.0, p[1]) < 1e-9 for p in ring)
    assert any(math.hypot(p[0] - 13.0, p[1]) < 1e-9 for p in ring)


def test_crossing_insert_skipped_on_top_of_its_own_corner():
    """A partner clipping the receiver's corner crosses its bottom edge a
    nanometre from that corner: ``0 < t < 1`` admits the point, and
    inserting it mints a 2e-8 m edge right beside the corner.  The
    crossing the partner makes on its way back out is a real one and must
    still insert."""
    receiver = _yield_receiver([(0.0, 0.0), (20.0, 0.0),
                                (20.0, 10.0), (0.0, 10.0)],
                               alts=[10.0, 10.4, 10.4, 10.0])
    # Vertical edge 2e-8 m inside the corner; the hypotenuse leaves the
    # receiver 0.2 m along the bottom edge (a genuine second crossing).
    partner = BuiltShape(polygon=Polygon([(2e-8, -5.0), (0.4 + 2e-8, -5.0),
                                          (2e-8, 5.0)]), role=ROLE_JUNCTION)
    layout = _make_layout(receiver, partner)
    _resolve_edge_crossings(layout)
    ring = list(receiver.polygon.exterior.coords)[:-1]
    assert receiver.polygon.is_valid
    assert _min_edge_len(receiver) > 1e-6
    assert not [p for p in ring
                if 0.0 < math.hypot(p[0], p[1]) < 1e-6]
    assert any(abs(p[1]) < 1e-9 and 0.1 < p[0] < 0.3 for p in ring)
    assert len(receiver.node_altitudes) == len(ring) + 1


# ══════════════════════════════════════════════════════════════════════
# TASK #16 — THE WELD'S CANDIDATE PAIRS, EXPOSED
# ══════════════════════════════════════════════════════════════════════
#
# ``weld_candidate_pairs`` is the weld's OWN candidate enumeration, read
# without running it: the pad-host level family's membership relation is
# "will weld together" (``anchors._pad_lip_index``).  The twin that
# matters is not that the accessor returns something plausible — it is
# that the weld then identifies EXACTLY the pairs it predicted.  A second
# implementation that merely agreed by inspection is the census-wrapper
# defect; this asserts the shared code path from the outside.


def _weld_fixture():
    """A receiver square with THREE distinct donors on its bottom edge —
    one plain T-junction, one float-noise twin of it (the weld dedupes
    that one), and one well clear of the others."""
    receiver = _receiver_square(10.0, 10.4)
    donors = [_donor_triangle(apex_alt=10.05)]
    for apex, name in (((10.0 + 1e-9, 0.0), "twin"), ((4.0, 0.0), "far")):
        donors.append(BuiltShape(
            polygon=Polygon([(apex[0] - 3.0, -8.0), (apex[0] + 3.0, -8.0),
                             apex]),
            role=ROLE_JUNCTION, ref=name,
            node_altitudes=[9.9, 9.9, 10.05]))
    return receiver, donors


def test_weld_candidate_pairs_predicts_exactly_what_the_weld_welds():
    receiver, donors = _weld_fixture()
    layout = _make_layout(receiver, *donors)
    predicted = weld_candidate_pairs(layout, tol=CONFORMANCE_TOL_M)

    # PURITY: reading the prediction must not weld anything.
    rings_before = {id(s): list(s.polygon.exterior.coords)
                    for s in layout.shapes}
    weld_candidate_pairs(layout, tol=CONFORMANCE_TOL_M)
    assert all(list(s.polygon.exterior.coords) == rings_before[id(s)]
               for s in layout.shapes), "the accessor mutated the layout"

    n_shapes, n_verts = enforce_conformance(layout, tol=CONFORMANCE_TOL_M)
    assert n_verts == len(predicted) > 0, (
        f"the weld inserted {n_verts} vertices, the accessor predicted "
        f"{len(predicted)}")
    assert n_shapes == len({id(p.receiver) for p in predicted})
    # ...and each predicted pair IS a node of its receiver's welded ring.
    for pair in predicted:
        ring = list(pair.receiver.polygon.exterior.coords)
        assert any(math.hypot(x - pair.point[0], y - pair.point[1]) < 1e-9
                   for (x, y) in ring), (
            f"predicted weld at {pair.point} is absent from the ring")
    # A SECOND read predicts nothing: the weld is idempotent and so is
    # its prediction (no phantom pair survives the weld).
    assert weld_candidate_pairs(layout, tol=CONFORMANCE_TOL_M) == []


def test_weld_candidate_pairs_names_the_donor_and_its_edge():
    """The pair is (donor vertex → receiver edge): a consumer joins on
    the donor coordinate to find WHICH neighbour welds, and on the edge
    index to find WHERE on the receiver's boundary."""
    receiver, donors = _weld_fixture()
    layout = _make_layout(receiver, *donors)
    pairs = weld_candidate_pairs(layout, tol=CONFORMANCE_TOL_M)
    assert {p.donor_point for p in pairs} == {(10.0, 0.0), (4.0, 0.0)}, (
        "the float-noise twin must dedupe to ONE pair, as the weld does")
    assert all(id(p.receiver) == id(receiver) for p in pairs)
    # Both donors sit on the receiver's bottom edge — ring index 0.
    assert {p.edge_index for p in pairs} == {0}
    for p in pairs:
        assert 0.0 < p.t < 1.0
