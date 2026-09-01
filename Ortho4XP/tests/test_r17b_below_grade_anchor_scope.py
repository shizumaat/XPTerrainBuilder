"""R17b-1 — BELOW-GRADE ANCHORS GOVERN ONLY THEIR OWN BODY.

THE DEFECT (measured at VHHH, 2026-08-11).  ``spine_value_fields`` seeds
its value fields from ``G.runway_anchor`` UNION the on-spine HARD TRUTH
the solve published (the BAND-SEED COMPLETENESS law).  That hard-truth
set is every node ``_seed_elevations`` hardened — which includes a
TUNNEL RAMP body standing at its BORE profile.  A bore floor is metres
below grade; the ceiling field is a MIN over anchors; and a min never
forgets.  One below-grade seed therefore drags the ceiling down along
every route it can reach.  At VHHH (flat site, Z0 7.315) the junction
ceiling read ``[-12.93, -12.14]`` where the solve said 7.01, and the
writeback clamp — obeying that carried band — authored the -13 m
runway-end canyons.

THE LAW.  A below-grade anchor contributes to the band ONLY for nodes
inside its own below-grade BODY.  Everywhere else the band comes from
surface-lawful anchors.  Inside the body the anchor still governs, so a
tunnel keeps its own lawful band (KCLT's round-10 tunnel table).

RE-KEYED, LAW UNCHANGED (RULINGS 2026-08-31b, redesign spec §5).  The
below-grade plate in these fixtures used to be R14-1's CLAIMED
``tunnel_road`` pavement, pinned by
``solver_primitives._build_tunnel_road_pins``.  That claim class and its
pin family are retired; the below-grade body is now the portal walk's
own ``tunnel_ramp`` (``ROLE_TUNNEL_RAMP``, ref ``tunnel_ramp``, in
``BELOW_GRADE_REFS``).  R17b-1 itself — a below-grade anchor governs
only its own body — is untouched, and so is every assertion here.

Headless: synthetic geometry, production's own functions.
"""

from __future__ import annotations

from shapely import geometry

from auto_patch.elevation_per_surface import building_feasibility as BF
from auto_patch.elevation_per_surface.building_feasibility import (
    below_grade_anchor_bodies, below_grade_bodies, below_grade_governed_nodes,
    spine_value_fields)
from auto_patch.groundside import (BELOW_GRADE_REFS, below_grade_family_shapes)


class _G:
    """Minimal unified-graph stand-in — the attributes the value fields
    read, plus ``pos`` (which is also the geometry the body membership
    test joins on)."""

    def __init__(self, runway_anchor, spine_adj, pos):
        self.runway_anchor = dict(runway_anchor)
        self.spine_adj = dict(spine_adj)
        self.pos = dict(pos)
        self.service_spine_pairs = set()


class _Shape:
    def __init__(self, ref, polygon, role="service_junction",
                 node_altitudes=None):
        self.ref = ref
        self.role = role
        self.polygon = polygon
        self.node_altitudes = node_altitudes


class _Layout:
    def __init__(self, shapes=()):
        self.shapes = list(shapes)
        self.anchor = (0.0, 0.0)


#: The bore value the ramp body stands at — VHHH's class.
BORE_M = -13.05
#: The surface runway anchor's value (VHHH's Z0 neighbourhood).
SURFACE_M = 7.01
#: One spine edge's budget.
BUDGET_M = 1.0


def _plate(x0, y0, x1, y1):
    return geometry.box(x0, y0, x1, y1)


def _vhhh_shape(with_plate=True):
    """Three spine nodes in a line, the far one inside a ramp body.

    * node 0 — a SURFACE runway anchor at 7.01 (the solve's own value);
    * node 1 — a free surface node one budget away;
    * node 2 — a HARD below-grade node at the bore depth, two budgets
      away, standing inside a ``tunnel_ramp`` body.

    Both anchors are seeds: node 0 through ``runway_anchor``, node 2
    through the published hard truth, exactly as production seeds them.
    """
    pos = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (20.0, 0.0)}
    G = _G(runway_anchor={0: SURFACE_M},
           spine_adj={0: [(1, BUDGET_M)],
                      1: [(0, BUDGET_M), (2, BUDGET_M)],
                      2: [(1, BUDGET_M)]},
           pos=pos)
    shapes = []
    if with_plate:
        shapes.append(_Shape("tunnel_ramp", _plate(15.0, -5.0, 25.0, 5.0),
                             role="tunnel_ramp",
                             node_altitudes=[BORE_M] * 4))
    layout = _Layout(shapes)
    # The hard-truth map is keyed by canonical point; a registry-less
    # layout joins on the raw position tuple, which the production
    # resolver already supports (its own docstring).
    layout._seed_hard_truth_values = {(20.0, 0.0): BORE_M}
    return layout, G


class TestTheFamilyIsOneEnumeration:
    """``groundside.below_grade_family_shapes`` is THE below-grade family
    test — the three enumerations that had to agree, in one place."""

    def test_every_below_grade_ref_is_a_body(self):
        shapes = [_Shape(ref, _plate(0, 0, 1, 1)) for ref in BELOW_GRADE_REFS]
        assert len(below_grade_family_shapes(_Layout(shapes))) == len(shapes)

    def test_the_tunnel_wall_ref_and_the_tunnel_roles_are_bodies(self):
        from auto_patch.gap_fill import (_TUNNEL_BLOCKER_REFS,
                                         _TUNNEL_BLOCKER_ROLES)
        shapes = [_Shape(ref, _plate(0, 0, 1, 1))
                  for ref in _TUNNEL_BLOCKER_REFS]
        shapes += [_Shape("whatever", _plate(0, 0, 1, 1), role=role)
                   for role in _TUNNEL_BLOCKER_ROLES]
        assert len(below_grade_family_shapes(_Layout(shapes))) == len(shapes)

    def test_surface_pavement_is_not_a_body(self):
        layout = _Layout([_Shape("apron3", _plate(0, 0, 1, 1), role="apron")])
        assert below_grade_family_shapes(layout) == []
        assert below_grade_bodies(layout) == []

    def test_abutting_plates_are_ONE_body(self):
        """A tunnel is emitted as a CHAIN of quads.  Grouping per QUAD
        would confine an anchor to the metre of ramp it stands on; the
        body is the connected structure, the same grouping
        ``groundside._BelowGradeIndex`` uses for its one portal."""
        layout = _Layout([_Shape("tunnel_ramp", _plate(0, 0, 10, 5)),
                          _Shape("tunnel_ramp", _plate(10, 0, 20, 5))])
        assert len(below_grade_bodies(layout)) == 1

    def test_disjoint_structures_are_two_bodies(self):
        layout = _Layout([_Shape("tunnel_ramp", _plate(0, 0, 10, 5)),
                          _Shape("tunnel_ramp", _plate(100, 0, 110, 5))])
        assert len(below_grade_bodies(layout)) == 2


class TestTheAnchorIsClassifiedByMEMBERSHIP:
    def test_the_ramp_body_anchor_is_below_grade(self):
        layout, G = _vhhh_shape()
        bodies = below_grade_anchor_bodies(layout, G, {0: SURFACE_M,
                                                       2: BORE_M})
        assert set(bodies) == {2}

    def test_a_ring_vertex_ON_the_boundary_is_INSIDE(self):
        """The body's own vertices are where its seeds sit — boundary
        membership is the point, not an edge case."""
        layout = _Layout([_Shape("tunnel_ramp", _plate(0, 0, 10, 10),
                                 role="tunnel_ramp")])
        G = _G({}, {}, {7: (0.0, 0.0)})
        assert set(below_grade_anchor_bodies(layout, G, {7: BORE_M})) == {7}

    def test_no_below_grade_geometry_means_no_classification(self):
        layout, G = _vhhh_shape(with_plate=False)
        assert below_grade_anchor_bodies(layout, G, {0: 1.0, 2: 2.0}) == {}
        assert below_grade_governed_nodes(layout, G, {0: 1.0, 2: 2.0}) == {}


class TestTheCanyonClass:
    """The measured VHHH mechanism, in miniature."""

    def test_RED_without_the_law_the_bore_poisons_the_surface(self,
                                                              monkeypatch):
        """MUTATION CHECK.  With the scoping removed — which is exactly
        the pre-R17b code — the ceiling at the SURFACE nodes is the bore
        value plus route budget, not the surface anchor's own."""
        layout, G = _vhhh_shape()
        monkeypatch.setattr(BF, "below_grade_governed_nodes",
                            lambda *a, **k: {})
        ceiling, _floor = spine_value_fields(layout, G)
        assert ceiling[1] < 0.0
        assert abs(ceiling[1] - (BORE_M + BUDGET_M)) < 1e-9
        assert abs(ceiling[0] - (BORE_M + 2 * BUDGET_M)) < 1e-9

    def test_GREEN_the_surface_ceiling_comes_from_a_surface_anchor(self):
        layout, G = _vhhh_shape()
        ceiling, _floor = spine_value_fields(layout, G)
        assert abs(ceiling[0] - SURFACE_M) < 1e-9
        assert abs(ceiling[1] - (SURFACE_M + BUDGET_M)) < 1e-9

    def test_the_BODY_keeps_its_own_lawful_band(self):
        """KCLT's round-10 tunnel table must hold: inside its body the
        below-grade anchor still governs, so the tunnel node keeps the
        bore ceiling it is entitled to."""
        layout, G = _vhhh_shape()
        ceiling, floor = spine_value_fields(layout, G)
        assert abs(ceiling[2] - BORE_M) < 1e-9
        # The floor is a MAX and the surface anchor is not restricted, so
        # it still reaches into the body — the law scopes the below-grade
        # anchor's REACH, it does not fence the body off from the network.
        assert abs(floor[2] - (SURFACE_M - 2 * BUDGET_M)) < 1e-9

    def test_the_governed_set_is_the_body_not_the_graph(self):
        layout, G = _vhhh_shape()
        governed = below_grade_governed_nodes(layout, G,
                                              {0: SURFACE_M, 2: BORE_M})
        assert governed[2] == frozenset({2}) | {2}
        assert 0 not in governed[2] and 1 not in governed[2]

    def test_the_field_is_byte_identical_with_no_below_grade_geometry(self):
        """The inert answer: an airport with no tunnel geometry runs the
        pre-change code path, node for node."""
        layout, G = _vhhh_shape(with_plate=False)
        ceiling, floor = spine_value_fields(layout, G)
        assert abs(ceiling[0] - min(SURFACE_M, BORE_M + 2 * BUDGET_M)) < 1e-9
        assert abs(floor[2] - max(BORE_M, SURFACE_M - 2 * BUDGET_M)) < 1e-9
