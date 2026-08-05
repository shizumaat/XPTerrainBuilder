"""ZONE-NODE IDENTITY: two hosts' zone rows are two solve variables.

Owner decision (coordinator relay 2026-08-05): "implement separate solve
variables where two shapes' zone nodes collide; the canonical-identity
join must carry both to emit."

THE DEFECT.  Adjacent-ground zone rows are marched per HOST shape and
interned through the shared canonical registry (0.5 m).  Two different
hosts' rows that come within that tolerance therefore became ONE solve
variable — while the zone law is stated PER HOST against that host's own
foot datum.  One variable cannot satisfy two independent laws, and the
downstream code absorbed the collision instead of reporting it:
``_build_zone_row_constraints`` DROPPED the second host's edge (its
``n_cross_claimed`` counter is the tally) and ``_zone_foot_boxes``
INTERSECTED the two boxes, so a disjoint pair read as a declared conflict
the ground never had.

WHAT MUST NOT CHANGE — the standing identity law:
  * a zone node whose bucket is already claimed by a PAVEMENT / gap-spine
    / RESA node ADOPTS that variable (pavement wins as an identity; no
    band edge may constrain a pavement variable);
  * two zone nodes of the SAME host at one bucket are one point.

Hermetic: synthetic layout, no X-Plane install, no airport build.
"""
import pytest
from shapely.geometry import Polygon

from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.layout import BuiltShape, ROLE_APRON, ROLE_GRADED_STRIP
from auto_patch.elevation_per_surface.solver_primitives import (
    _build_node_list, zone_node_index)


class _Layout:
    def __init__(self):
        self.shapes = []
        self.canonical_points = CanonicalPointRegistry()
        self.adjacent_ground_presolve = []


def _apron(x0, y0, size=20.0):
    return BuiltShape(
        polygon=Polygon([(x0, y0), (x0 + size, y0),
                         (x0 + size, y0 + size), (x0, y0 + size)]),
        role=ROLE_APRON)


def _zn(x, y, host):
    return {"xy": (float(x), float(y)), "host": (float(host[0]),
                                                 float(host[1])),
            "floor_off": -0.5, "ceil_off": 0.5}


def _layout_with_two_hosts(zone_xy_a, zone_xy_b):
    """Two apron hosts, each with ONE zone node at the given position."""
    layout = _Layout()
    a, b = _apron(0.0, 0.0), _apron(100.0, 0.0)
    layout.shapes = [a, b]
    layout.adjacent_ground_presolve = [
        {"shape": a, "zone_nodes": [_zn(*zone_xy_a, host=(0.0, 0.0))]},
        {"shape": b, "zone_nodes": [_zn(*zone_xy_b, host=(100.0, 0.0))]},
    ]
    return layout, a, b


@pytest.fixture(autouse=True)
def _admit_zone_rows(monkeypatch):
    """The zone rows are admitted to the node list only when their
    (role, ref) family is; admit it for these twins."""
    import auto_patch.elevation_per_surface.solver_primitives as SP
    real = SP.admitted_terrain_refs
    monkeypatch.setattr(
        SP, "admitted_terrain_refs",
        lambda *a, **k: set(real(*a, **k)) | {(ROLE_GRADED_STRIP,
                                               "adjacent_ground")})


def test_two_hosts_colliding_zone_nodes_get_two_variables():
    """THE LAW.  The two zone nodes are 0.2 m apart — inside the 0.5 m
    registry tolerance, so they intern to ONE canonical bucket — but they
    belong to different hosts, so they must be two solve variables."""
    layout, a, b = _layout_with_two_hosts((-5.0, -5.0), (-5.0, -4.8))
    nodes, b2i = _build_node_list(layout)

    ia = zone_node_index(layout, b2i, (-5.0, -5.0), id(a))
    ib = zone_node_index(layout, b2i, (-5.0, -4.8), id(b))
    assert ia is not None and ib is not None
    assert ia != ib, (
        "two hosts' zone rows share one solve variable — one variable "
        "cannot carry two per-host zone laws")
    assert layout._zone_node_split_count == 1
    # both are ZONE variables (above the terrain-leaf threshold), so the
    # solver's index-threshold levers still classify them correctly.
    first = layout._adjacent_ground_first_zone_index
    assert ia >= first and ib >= first


def test_the_split_variable_carries_to_emit_by_the_canonical_join():
    """"the canonical-identity join must carry both to emit": the second
    host's variable is reachable ONLY through (bucket, host).  A
    bucket-only lookup — what every consumer used to do — still returns
    the FIRST claimant, which is precisely the read that lost the second
    host's value."""
    layout, a, b = _layout_with_two_hosts((-5.0, -5.0), (-5.0, -4.8))
    _nodes, b2i = _build_node_list(layout)
    cps = layout.canonical_points
    bucket_only = b2i[cps.get_or_add(-5.0, -4.8)]
    ia = zone_node_index(layout, b2i, (-5.0, -5.0), id(a))
    ib = zone_node_index(layout, b2i, (-5.0, -4.8), id(b))
    assert bucket_only == ia, "the bucket keeps pointing at the first claimant"
    assert ib != bucket_only
    assert layout._zone_node_owner[ib] == id(b)


def test_the_same_host_twice_at_one_bucket_is_one_point():
    """FALSIFIER 1: the split must be keyed on the HOST, not on
    'a bucket was seen twice'.  One host's two coincident rows are one
    point and must NOT mint a second variable."""
    layout = _Layout()
    a = _apron(0.0, 0.0)
    layout.shapes = [a]
    layout.adjacent_ground_presolve = [{
        "shape": a,
        "zone_nodes": [_zn(-5.0, -5.0, host=(0.0, 0.0)),
                       _zn(-5.0, -4.8, host=(0.0, 0.0))]}]
    _nodes, b2i = _build_node_list(layout)
    i0 = zone_node_index(layout, b2i, (-5.0, -5.0), id(a))
    i1 = zone_node_index(layout, b2i, (-5.0, -4.8), id(a))
    assert i0 == i1
    assert layout._zone_node_split_count == 0


def test_pavement_identity_adoption_is_untouched():
    """FALSIFIER 2: the standing law.  A zone node landing on a PAVEMENT
    ring vertex must ADOPT that pavement variable — pavement wins as an
    identity, and no band edge may constrain a pavement variable.  A
    split here would hand the band its own copy of a pavement node and
    silently decouple the weld."""
    layout = _Layout()
    a = _apron(0.0, 0.0)
    layout.shapes = [a]
    # (0, 0) IS a ring vertex of the apron.
    layout.adjacent_ground_presolve = [{
        "shape": a, "zone_nodes": [_zn(0.0, 0.0, host=(0.0, 0.0))]}]
    nodes, b2i = _build_node_list(layout)
    first = layout._adjacent_ground_first_zone_index
    i = zone_node_index(layout, b2i, (0.0, 0.0), id(a))
    assert i is not None and i < first, (
        "the zone node must adopt the pavement variable, not mint one")
    assert layout._zone_node_split_count == 0


def test_distant_zone_nodes_are_unaffected():
    """FALSIFIER 3: nodes that never collided keep exactly one variable
    each and the split counter stays 0 — so the counter cannot be read as
    'always splitting'."""
    layout, a, b = _layout_with_two_hosts((-5.0, -5.0), (105.0, -5.0))
    _nodes, b2i = _build_node_list(layout)
    ia = zone_node_index(layout, b2i, (-5.0, -5.0), id(a))
    ib = zone_node_index(layout, b2i, (105.0, -5.0), id(b))
    assert ia != ib
    assert layout._zone_node_split_count == 0


def test_a_shapeless_lookup_still_resolves_by_bucket():
    """The resolver must stay usable for the PAVEMENT reads that share
    it (a foot datum's a/b vertices), where there is no host key."""
    layout, a, _b = _layout_with_two_hosts((-5.0, -5.0), (-5.0, -4.8))
    _nodes, b2i = _build_node_list(layout)
    cps = layout.canonical_points
    assert zone_node_index(layout, b2i, (0.0, 0.0)) == \
        b2i[cps.get_or_add(0.0, 0.0)]


def test_the_constraint_builder_no_longer_drops_the_second_host():
    """END TO END on the constraint supply: with two variables the second
    host's zone edge is BUILT instead of counted as a cross-claim.  This
    is the behaviour the split exists for."""
    from auto_patch.elevation_per_surface.solver_primitives import (
        _build_adjacent_ground_zone_constraints)
    layout, a, b = _layout_with_two_hosts((-5.0, -5.0), (-5.0, -4.8))
    _nodes, b2i = _build_node_list(layout)
    sc, zone_idx, (n_pav, n_cross) = _build_adjacent_ground_zone_constraints(
        layout, b2i)
    assert n_cross == 0, (
        "a cross-host claim means one host's zone law was dropped again")
    assert len(zone_idx) == 2
    built = [e for entry in sc for e in entry["edges"]]
    assert len(built) == 2, (
        f"both hosts' zone edges must reach the solver; got {built}")
