"""GROUNDSIDE GRADES TO ITS LAW; THE DEM IS ONLY A SEED.

Fix cycle 2, item 2.  Owner law (docs/RULINGS.md 2026-08-05, "DEM's role,
and the constant-DEM invariant"): *DEM chooses WHERE in the lawful band a
thing seats.  It never shapes the band, never constrains, never blocks.*

WHAT WAS MEASURED (the mechanism, not a code reading).
``tools/harness/who_wrote.py HEAZ --dem 10000`` named the introducing
writer of every vertex sitting exactly on the constant DEM — 298 of them:

    168  service_junction     solve.py:_writeback  (LAW ISLANDS, below)
     92  groundside_pavement  groundside._merge_touching_groundside
     25  groundside_pavement  pipeline (the primary lot emit)
     13  groundside_pavement  groundside._separate_groundside_from_airside

All three groundside authors go through ``_dem_follow_polygon``, which
sampled the DEM at every vertex and ring-limited the result.  That is a
DEM DRAPE with a smoother on it: the terrain is the authority and the law
is a post-filter.  The welds are then overwritten at emit by the
higher-authority claimant (``to_osm``'s precedence resolution, which is
correct), so one lot ships with its weld vertices on the LAW and its
interior on the TERRAIN.

Measured in the emitted canyon patch, HEAZ way -10281 (63 nodes):

    17 weld nodes  ......  85.56 - 91.70 m   (service_junction values)
    47 interior nodes  ...  10 000.00 m      (raw constant DEM)
    within_shape step  ...  9 914.44 m       <- the campaign's worst row
                                                in BOTH flat worlds

A RING LIMITER CANNOT FIX THIS, and the arithmetic is the argument: at the
5 % lot cap over a 15 m densify step an edge may fall 0.75 m, so closing
9 914 m needs ~13 000 edges and the ring has 63.  Capping the SLOPE of a
surface whose DATUM is wrong only spreads the error out.  The datum must
come from the law — which is what this module's twins pin.

LAW ISLANDS ARE NOT FIXED BY THIS, deliberately.  A shape with NO weld to
any higher-authority surface (HEAZ canyon: ways -10033, -10034, -10066,
``sharedWithHigher=0``) has nothing to grade to.  Inventing a datum for it
would be minting.  Those shapes emit internally FLAT under a constant DEM
and produce no ``within_shape`` row, so they are not the worst-row class;
they are the separate law-island population and are attributed, not
papered over.
"""
import math

import pytest

from auto_patch.groundside import (
    _grade_limit_ring, _seat_ring_on_law_anchors, law_anchor_values)
from auto_patch.layout import (
    BuiltShape, PavementLayout, ROLE_APRON, ROLE_GRADED_STRIP,
    ROLE_GROUNDSIDE_PAVEMENT, ROLE_RUNWAY, ROLE_SERVICE_JUNCTION)

from shapely.geometry import Polygon

#: A straight 60 m run at 10 m spacing — the reduced HEAZ ring.
_RUN = [(float(i) * 10.0, 0.0) for i in range(7)]
_CAP = 0.05                      # GROUNDSIDE_MAX_GRADE (owner 2026-08-03)


def _worst_adjacent_grade(coords, alts):
    worst = 0.0
    n = len(coords)
    for i in range(n):
        j = (i + 1) % n
        d = math.hypot(coords[j][0] - coords[i][0],
                       coords[j][1] - coords[i][1])
        if d < 1e-6:
            continue
        worst = max(worst, abs(alts[j] - alts[i]) / d)
    return worst


def _shape(role, ring, alts=None, altitude=None):
    return BuiltShape(polygon=Polygon(ring + [ring[0]]), role=role, ref="",
                      node_altitudes=alts, altitude=altitude)


# ══════════════════════════════════════════════════════════════════════
# THE DATUM
# ══════════════════════════════════════════════════════════════════════

def test_a_constant_dem_lot_lands_ON_ITS_WELD_DATUM_not_on_the_terrain():
    """The oracle case.  DEM ≡ 10 000 m, two welds at ~86 m: every free
    vertex must take the LAW datum, because a constant DEM carries no
    relief and therefore says nothing about where the lot should sit."""
    dem = [10000.0] * 7
    anchors = {(0.0, 0.0): 86.0, (60.0, 0.0): 86.0}
    alts, pinned = _seat_ring_on_law_anchors(_RUN, dem, anchors, _CAP)
    assert pinned == frozenset({0, 6})
    assert alts == pytest.approx([86.0] * 7), (
        f"the lot is still on the terrain: {alts}. Under a constant DEM "
        f"the relief term is exactly zero, so every free vertex must equal "
        f"its nearest weld's law value")
    assert max(alts) - min(alts) == pytest.approx(0.0)


def test_the_9914m_step_is_GONE_end_to_end():
    """HEAZ way -10281 reduced to scale: welds at the ring's two ends
    carrying the measured 85.56 m and 91.70 m, everything between them on
    a 10 000 m DEM, at the real 15 m densify pitch.

    The shipped ring had a 9 914.44 m within-shape step.  Afterwards the
    only elevation change left is the 6.14 m the two LAW values genuinely
    differ by — spread across the ring at or under the lot cap.
    """
    ring = [(float(i) * 15.0, 0.0) for i in range(13)]   # 180 m of run
    dem = [10000.0] * 13
    anchors = {(0.0, 0.0): 85.56, (180.0, 0.0): 91.70}
    alts, pinned = _seat_ring_on_law_anchors(ring, dem, anchors, _CAP)
    alts = _grade_limit_ring(ring, alts, _CAP, pinned=pinned)
    spread = max(alts) - min(alts)
    assert spread == pytest.approx(6.14, abs=0.02), (
        f"spread {spread} — the surface must carry the difference between "
        f"the two LAW values and nothing else; 9 914 m of terrain is gone")
    # ``_grade_limit_ring`` stops at its own 1e-3 m residual, which over a
    # 15 m edge is 0.0067 % of slack — the limiter's pre-existing exit
    # tolerance, not slack this fix introduced.
    assert _worst_adjacent_grade(ring, alts) <= _CAP + 1e-3 / 15.0
    assert alts[0] == pytest.approx(85.56)
    assert alts[-1] == pytest.approx(91.70)


def test_the_DEM_still_supplies_RELIEF_under_real_terrain():
    """DEM is a seed, not a nullity: with real relief the lot FOLLOWS the
    ground — but only as far from its welds as its own cap allows."""
    dem = [10000.0, 10001.0, 10004.0, 10050.0, 10004.0, 10001.0, 10000.0]
    anchors = {(0.0, 0.0): 86.0, (60.0, 0.0): 86.0}
    alts, _p = _seat_ring_on_law_anchors(_RUN, dem, anchors, _CAP)
    assert alts[1] > alts[0], "the DEM's rise was discarded — that is not a seed"
    assert alts[3] == pytest.approx(86.0 + _CAP * 30.0), (
        "the 50 m DEM spike must be CLAMPED to the cap over the distance "
        "from its weld, not followed")


def test_a_law_island_is_LEFT_ALONE_never_given_an_invented_datum():
    """No weld ⇒ nothing to grade to.  Returning the DEM unchanged (and an
    empty pinned set) is the honest answer; minting a datum would make the
    island look lawful while hiding that it is unbound."""
    dem = [10000.0, 10001.0, 10002.0, 10003.0, 10002.0, 10001.0, 10000.0]
    alts, pinned = _seat_ring_on_law_anchors(_RUN, dem, {}, _CAP)
    assert alts == dem
    assert pinned == frozenset()


# ══════════════════════════════════════════════════════════════════════
# THE ANCHOR SOURCE — the emitter's own precedence order
# ══════════════════════════════════════════════════════════════════════

def test_the_anchors_come_from_shapes_that_OUTRANK_groundside():
    lay = PavementLayout(icao="T", anchor=(0.0, 0.0))
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    lay.shapes.append(_shape(ROLE_SERVICE_JUNCTION, ring, [90.0] * 4))
    anchors = law_anchor_values(lay)
    assert anchors[(0.0, 0.0)] == pytest.approx(90.0)


def test_a_SOFT_RECEIVER_is_never_an_anchor():
    """``graded_strip`` / ``runway_clearance`` ADOPT values at a shared
    node — they carry none of their own.  Anchoring a lot to an adopter
    would be circular, and at HEAZ way -10281 a runway_clearance touches
    13 of the ring's nodes, so this is the live case, not a hypothetical.
    """
    lay = PavementLayout(icao="T", anchor=(0.0, 0.0))
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    lay.shapes.append(_shape(ROLE_GRADED_STRIP, ring, [77.0] * 4))
    assert law_anchor_values(lay) == {}, (
        "a soft receiver supplied an anchor value; soft roles tail the "
        "authority order precisely because they do not carry values")


def test_groundside_never_anchors_ITSELF():
    lay = PavementLayout(icao="T", anchor=(0.0, 0.0))
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    lay.shapes.append(_shape(ROLE_GROUNDSIDE_PAVEMENT, ring, [70.0] * 4))
    assert law_anchor_values(lay) == {}


def test_the_HIGHEST_authority_wins_a_contested_weld():
    """Airside is king: where a runway and an apron both claim a
    coordinate, the lot grades to the RUNWAY value — the same winner
    ``to_osm`` will emit there, so surface and node cannot disagree."""
    lay = PavementLayout(icao="T", anchor=(0.0, 0.0))
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    lay.shapes.append(_shape(ROLE_APRON, ring, [50.0] * 4))
    lay.shapes.append(_shape(ROLE_RUNWAY, ring, [60.0] * 4))
    assert law_anchor_values(lay)[(0.0, 0.0)] == pytest.approx(60.0)


def test_the_anchor_order_IS_the_emitters_order():
    """One order, read from one place.  A private copy here is how the
    surface and the emitted node come to disagree."""
    import inspect
    from auto_patch import groundside as GS
    src = inspect.getsource(GS.law_anchor_values)
    assert "authority_rank" in src, (
        "law_anchor_values must read layout.authority_rank — the SAME "
        "total order to_osm resolves a shared node with")


# ══════════════════════════════════════════════════════════════════════
# THE PINNED RING LIMITER
# ══════════════════════════════════════════════════════════════════════

def test_the_limiter_never_moves_a_pinned_weld():
    """A weld carries a law value.  Relaxing it would make the lot's
    surface disagree with the node the emitter writes — reintroducing the
    tear this whole item removes."""
    coords = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (1.0, 1.0)]
    alts = [10.0, 10.0, 40.0, 10.0]
    out = _grade_limit_ring(coords, list(alts), _CAP, pinned=frozenset({2}))
    assert out[2] == pytest.approx(40.0), "a pinned law value was moved"


def test_two_disagreeing_LAW_values_are_LEFT_STANDING():
    """Both ends pinned and over cap is a law/anchor defect with an exact
    address.  Averaging it here would mint a value neither authority
    produced — the emit-consensus precedent this campaign already paid
    for (HECA's 1 497 minted groundside rows)."""
    coords = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (1.0, 1.0)]
    alts = [10.0, 40.0, 10.0, 10.0]
    out = _grade_limit_ring(coords, list(alts), _CAP,
                            pinned=frozenset({0, 1}))
    assert out[0] == pytest.approx(10.0)
    assert out[1] == pytest.approx(40.0)


def test_one_pinned_end_moves_the_FREE_end_by_the_WHOLE_excess():
    """Splitting the excess would move the weld.  The free side takes all
    of it."""
    coords = [(0.0, 0.0), (10.0, 0.0)]
    alts = [86.0, 96.0]                        # 10 m over 10 m = 100 %
    out = _grade_limit_ring(coords, list(alts), _CAP,
                            pinned=frozenset({0}))
    assert out[0] == pytest.approx(86.0)
    assert out[1] == pytest.approx(86.5, abs=1e-6), (
        "the free end must land exactly at cap distance from the weld")


def test_the_unpinned_limiter_is_unchanged():
    """Legacy callers pass no pins and must behave exactly as before —
    this fix adds an authority, it does not re-tune the smoother."""
    coords = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (10.0, 10.0)]
    alts = [0.0, 5.0, 0.0, 0.0]
    out = _grade_limit_ring(coords, list(alts), _CAP)
    assert _worst_adjacent_grade(coords, out) <= _CAP + 1e-3


# ══════════════════════════════════════════════════════════════════════
# CYCLE-6 INGESTION — one identity, the ladder, and the named island
# ══════════════════════════════════════════════════════════════════════

def test_the_anchor_identity_IS_the_emitters_identity_not_a_mm_key():
    """THE MECHANISM the ingestion round closed.

    ``law_anchor_values`` keyed on the millimetre-rounded coordinate,
    while ``to_osm`` interns a shared node through
    ``layout.canonical_points`` at ``SHARED_VERTEX_TOL_M`` (0.5 m).  So a
    lot vertex a few millimetres off the service-junction node it welds
    to found NO anchor at seat time, kept its raw DEM seed — and then had
    that very vertex OVERWRITTEN at emit by the higher authority.  One
    ring, welds on the law and interior on the terrain.

    Measured specimen, HECA ``--dem 1`` way shapeID 525: two nodes at
    99.06 / 99.07 m against four at 1.13-1.22 m, the 98.07 m
    ``within_shape`` row that headed the census.
    """
    from auto_patch.canonical_points import CanonicalPointRegistry
    from auto_patch.groundside import law_anchor_key
    lay = PavementLayout(icao="T", anchor=(0.0, 0.0))
    lay.canonical_points = CanonicalPointRegistry(tol_m=0.5)
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    for (x, y) in ring:                     # the emitter's own interning
        lay.canonical_points.get_or_add(x, y)
    lay.shapes.append(_shape(ROLE_SERVICE_JUNCTION, ring, [99.06] * 4))
    key = law_anchor_key(lay)
    anchors = law_anchor_values(lay)
    # the lot vertex, 3 mm away — a different millimetre key entirely
    assert (round(10.003, 3), round(0.002, 3)) not in anchors, (
        "the fixture is not exercising the miss it claims to")
    assert anchors.get(key(10.003, 0.002)) == pytest.approx(99.06), (
        "the weld was missed: the seat and the emitter must decide "
        "'this vertex IS that node' by the SAME rule")


def test_the_registry_is_queried_READ_ONLY():
    """``get_or_add`` would intern the lot's vertex, changing which LATER
    points intern together — i.e. moving the emitted surface from inside
    a lookup.  The keyer must use the read-only half."""
    from auto_patch.canonical_points import CanonicalPointRegistry
    from auto_patch.groundside import law_anchor_key
    lay = PavementLayout(icao="T", anchor=(0.0, 0.0))
    lay.canonical_points = CanonicalPointRegistry(tol_m=0.5)
    lay.canonical_points.get_or_add(0.0, 0.0)
    before = lay.canonical_points.size
    key = law_anchor_key(lay)
    key(500.0, 500.0)                       # nowhere near anything
    assert lay.canonical_points.size == before, (
        "the anchor keyer interned a point — an instrument that moves "
        "its subject")


def test_a_vertex_between_TWO_welds_is_INTERPOLATED_not_stair_stepped():
    """The nearest-anchor rule could only offer ONE datum, so a ring
    welded at 100 m and 110 m came out as two flat plateaus with the
    whole 10 m difference dumped on one interior edge.  The law value on
    a host ring edge is the INTERPOLATED one (the same insert law
    planarize uses)."""
    dem = [7.0] * 7                          # constant: no relief at all
    anchors = {(0.0, 0.0): 100.0, (30.0, 0.0): 110.0}
    alts, pinned = _seat_ring_on_law_anchors(_RUN, dem, anchors, _CAP)
    assert pinned == frozenset({0, 3})
    assert alts[1] == pytest.approx(100.0 + 10.0 / 3.0), (
        f"vertex 1 came out {alts[1]} — a third of the way between the "
        f"two welds along the ring, not at the nearer weld's value")
    assert alts[2] == pytest.approx(100.0 + 20.0 / 3.0)
    steps = [abs(alts[i + 1] - alts[i]) for i in range(3)]
    assert max(steps) == pytest.approx(10.0 / 3.0), (
        f"the ring still stair-steps: {alts}")


def test_a_piece_with_no_weld_inherits_ITS_OWN_PRIOR_FIELD():
    """A clip, a merge or a de-conflict is a GEOMETRY operation: the
    piece is the same surface it was a moment ago and its field was
    already law-seated.  Re-following the DEM there is how a lot that had
    lawful values got put back on the terrain."""
    from auto_patch.groundside import _prior_field_reader
    dem = [7.0] * 7
    prior_ring = [(0.0, 0.0), (60.0, 0.0), (60.0, 5.0), (0.0, 5.0)]
    prior_alts = [90.0, 96.0, 96.0, 90.0]
    reader = _prior_field_reader([(prior_ring, prior_alts)], tol_m=1.0)
    alts, pinned = _seat_ring_on_law_anchors(_RUN, dem, {}, _CAP,
                                             prior_at=reader)
    assert pinned == frozenset(), "a prior field is a datum, never a PIN"
    assert alts[0] == pytest.approx(90.0)
    assert alts[6] == pytest.approx(96.0)
    assert alts[3] == pytest.approx(93.0), (
        f"midpoint {alts[3]} — the prior ring's edge value at 30 m of a "
        f"60 m run carrying 90→96 m")
    assert all(abs(a - 7.0) > 1.0 for a in alts), "still on the DEM"


def test_a_WELD_outranks_the_pieces_own_prior_field():
    """One authority order, and it is the emitter's: where a higher
    surface claims the vertex, that value wins — the prior field is the
    rung BELOW it, not a competitor."""
    from auto_patch.groundside import _prior_field_reader
    dem = [7.0] * 7
    reader = _prior_field_reader(
        [([(0.0, 0.0), (60.0, 0.0), (60.0, 5.0), (0.0, 5.0)],
          [90.0, 90.0, 90.0, 90.0])], tol_m=1.0)
    alts, pinned = _seat_ring_on_law_anchors(
        _RUN, dem, {(0.0, 0.0): 120.0}, _CAP, prior_at=reader)
    assert 0 in pinned and alts[0] == pytest.approx(120.0)


def test_a_TRUE_law_island_is_COUNTED_not_silently_shipped():
    """No weld, no prior field: the DEM seed stands (inventing a datum
    would be minting) — but the ring is COUNTED, so it is named in the
    build's own report instead of shipping invisibly.  RULINGS
    2026-08-05: a datum-less report is a defect report, never a property
    of the ground."""
    dem = [10000.0] * 7
    stats = {}
    alts, pinned = _seat_ring_on_law_anchors(_RUN, dem, {}, _CAP,
                                             stats=stats)
    assert alts == dem and pinned == frozenset()
    assert stats["islands"] == 1
    assert stats["island_vertices"] == 7
    stats2 = {}
    _seat_ring_on_law_anchors(_RUN, dem, {(0.0, 0.0): 86.0}, _CAP,
                              stats=stats2)
    assert stats2.get("islands", 0) == 0, (
        "a ring WITH a weld was counted as an island")
    assert stats2["anchored"] == 1 and stats2["interpolated"] == 6


def test_the_prior_field_reuses_the_ONE_ring_interpolator():
    """Consult-before-create: ``adjacent_ground._interp_on_ring_law`` is
    THE authority for 'value at an arbitrary point on a ring'.  A fourth
    private copy of that projection is the duplicate-tool defect."""
    import inspect
    from auto_patch import groundside as GS
    src = inspect.getsource(GS._prior_field_reader)
    assert "_interp_on_ring_law" in src


def test_the_weld_is_found_by_NEAREST_WITHIN_TOLERANCE_not_key_equality():
    """The residual half of the identity fix, measured at HEAZ shape 279.

    Keying through the layout's registry is not enough on its own: a
    post-solve pass can move an authority ring AFTER its vertices were
    interned, so neither side resolves to a canonical point and both
    fall back to millimetre keys that differ.  Shape 279 shared fourteen
    vertices with ``service_junction`` shape 28 at 57.9-59.9 m, found
    none of them, and shipped its interior at 1-17 m — 748 of HEAZ's 751
    cluster-D rows from ONE ring.

    The emitter's rule is NEAREST REGISTERED POINT WITHIN
    ``SHARED_VERTEX_TOL_M``; the anchor lookup now asks exactly that,
    over the anchor coordinates themselves.
    """
    from auto_patch.groundside import law_anchor_key
    from auto_patch.layout import SHARED_VERTEX_TOL_M
    lay = PavementLayout(icao="T", anchor=(0.0, 0.0))      # NO registry
    anchors = {(10.0, 0.0): 59.81}
    key = law_anchor_key(lay, anchors)
    assert anchors.get(key(10.12, 0.09)) == pytest.approx(59.81), (
        "a vertex 0.15 m from the weld missed it — inside the very "
        "tolerance the emitter will use to make them ONE node")
    assert anchors.get(key(10.0 + 2 * SHARED_VERTEX_TOL_M, 0.0)) is None, (
        "a point beyond the shared-vertex tolerance was welded anyway — "
        "that is a proximity guess, not the emitter's identity")


def test_an_exact_key_still_wins_over_the_proximity_index():
    """Exact-first: where the millimetre key hits, nothing else is
    consulted, so the historical behaviour is a strict subset."""
    from auto_patch.groundside import law_anchor_key
    lay = PavementLayout(icao="T", anchor=(0.0, 0.0))
    anchors = {(10.0, 0.0): 59.81, (10.2, 0.0): 12.0}
    key = law_anchor_key(lay, anchors)
    assert anchors[key(10.0, 0.0)] == pytest.approx(59.81)
