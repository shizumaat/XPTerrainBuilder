"""R17c-1 — A BELOW-GRADE HARD VALUE ON A SURFACE NODE IS NOT A SEED.

THE WRITER, MEASURED (VHHH, round 17c, ``tools/trace_reach_route.py
--hard-seed-writers``).  r17b named the canyon's binding anchor — node
419 @(2077.5, 719.7) at −12.5370, a junction/adjacent_ground node INSIDE
the Z0 7.315 constant core, SURFACE-LAWFUL (so R17b-1's body scoping is
inert on it) — but not who wrote it.  The trace answers it:

  * the 38 sub-zero hard seeds are BORN IN SEEDING (present the moment
    ``_seed_elevations`` returns, not written by a later pass);
  * the DEM at each of them reads 7.3150 m, so the value is not terrain;
  * their COUNT matches the EAT anchor-rect pin family pass for pass —
    38 pins / 38 born in the first solve, 5 / 5 in each later one, the
    later five attributed ``eat_anchor_rect`` by name.

The writer is ``solver_primitives._build_eat_anchor_rect_pins``: the
end-around-taxiway rect pins pavement at ``end_elev +
eat_pavement_ceiling(...)`` — a design-aircraft TAIL clearance ~20.2 m
BELOW the runway end — onto junction and adjacent_ground/graded_strip
nodes that are ordinary airport surface.

THE LAW (round-17 amendment 2): such a value is unlawful AS A BAND SEED
and is refused at the seed-completeness union, counted.  The pin itself
still stands in the solve — moving upstream of the union is a separate,
owner-facing act.

Headless: synthetic geometry, production's own functions.
"""

from __future__ import annotations

from shapely import geometry

from auto_patch.config import FLAT_SITE_PACK_BELOW_GRADE_M
from auto_patch.elevation_per_surface import building_feasibility as BF
from auto_patch.elevation_per_surface.building_feasibility import (
    flat_core_below_grade_seed_refusals, spine_value_fields)

#: VHHH's own numbers.
Z0_M = 7.315
EAT_PIN_M = -12.5370
SURFACE_M = 7.01
BUDGET_M = 1.0


class _G:
    def __init__(self, runway_anchor, spine_adj, pos):
        self.runway_anchor = dict(runway_anchor)
        self.spine_adj = dict(spine_adj)
        self.pos = dict(pos)
        self.service_spine_pairs = set()


class _Shape:
    def __init__(self, ref, polygon, role="junction", node_altitudes=None):
        self.ref = ref
        self.role = role
        self.polygon = polygon
        self.node_altitudes = node_altitudes


class _Layout:
    def __init__(self, shapes=(), flat_site=True):
        self.shapes = list(shapes)
        self.anchor = (0.0, 0.0)
        if flat_site:
            # The stamp ``overlay_flat_site_insets`` writes, in the shape
            # ``flat_fast_path.substitution_entry`` reads.  The core is
            # derived from it by production, never spelled out here.
            self.dem_inset_provenance = {
                "synthetic_flat_site": {
                    "z0_m": Z0_M,
                    "extent_wgs84": [113.90, 22.30, 113.94, 22.33],
                    "feather_m": 60.0,
                }
            }

    #: layout-metre <-> lat/lon, the flat local frame the core is built in.
    _M_PER_DEG_LAT = 111320.0
    _M_PER_DEG_LON = 103000.0
    _LAT0, _LON0 = 22.30, 113.90

    def ll_to_m(self, lat, lon):
        return ((float(lon) - self._LON0) * self._M_PER_DEG_LON,
                (float(lat) - self._LAT0) * self._M_PER_DEG_LAT)

    def m_to_ll(self, x, y):
        return (self._LAT0 + float(y) / self._M_PER_DEG_LAT,
                self._LON0 + float(x) / self._M_PER_DEG_LON)


def _vhhh_shape(value=EAT_PIN_M, flat_site=True, shapes=(),
                pos_far=(1500.0, 1500.0)):
    """Two spine nodes: a surface runway anchor, and — one budget away —
    a node the EAT rect pinned below grade, DEEP INSIDE the core."""
    pos = {0: (1400.0, 1400.0), 1: pos_far}
    G = _G(runway_anchor={0: SURFACE_M},
           spine_adj={0: [(1, BUDGET_M)], 1: [(0, BUDGET_M)]},
           pos=pos)
    layout = _Layout(shapes, flat_site=flat_site)
    layout._seed_hard_truth_values = {pos_far: value}
    return layout, G


def _core_contains(layout, pos):
    from auto_patch import flat_fast_path as FFP
    entry = FFP.substitution_entry(layout)
    core = FFP.constant_core(layout, entry)
    return core is not None and core.contains(geometry.Point(*pos))


class TestTheFixtureIsTheRealGEOMETRY:
    def test_the_pinned_node_really_is_inside_the_constant_core(self):
        """The law's precondition, asserted rather than assumed — a
        fixture whose point sits outside the core would pass every
        assertion below for the wrong reason."""
        layout, _G_ = _vhhh_shape()
        assert _core_contains(layout, (1500.0, 1500.0))


class TestTheRefusal:
    def test_a_below_grade_value_on_a_surface_node_is_refused(self):
        layout, G = _vhhh_shape()
        refused = flat_core_below_grade_seed_refusals(
            layout, G, BF._hard_truth_spine_seeds(layout, G))
        assert refused == {1: EAT_PIN_M}

    def test_the_band_no_longer_carries_it(self):
        """THE POINT: the ceiling the writeback clamp obeys.  With the
        seed refused the node's ceiling comes from the surface anchor
        (7.01 + one budget), not from −12.537."""
        layout, G = _vhhh_shape()
        ceiling, _floor = spine_value_fields(layout, G)
        assert abs(ceiling[1] - (SURFACE_M + BUDGET_M)) < 1e-9

    def test_the_refusal_is_COUNTED_and_published(self):
        layout, G = _vhhh_shape()
        spine_value_fields(layout, G)
        assert layout._flat_core_seed_refusals == {1: EAT_PIN_M}

    def test_a_surface_lawful_seed_below_Z0_is_KEPT(self):
        """The margin is the owner's 1 m law, not zero: VHHH's own CIFP
        spread puts lawful anchors 0.6 m under Z0, and refusing those
        would delete the seed completeness the band needs."""
        value = Z0_M - 0.5 * FLAT_SITE_PACK_BELOW_GRADE_M
        layout, G = _vhhh_shape(value=value)
        assert flat_core_below_grade_seed_refusals(
            layout, G, BF._hard_truth_spine_seeds(layout, G)) == {}
        ceiling, _floor = spine_value_fields(layout, G)
        assert abs(ceiling[1] - value) < 1e-9


class TestWhatItMustNotTouch:
    def test_NO_FLAT_SITE_IS_INERT(self):
        """Every airport with no stamped substitution seeds exactly as
        before, node for node — KCLT, OTHH, SPJC."""
        layout, G = _vhhh_shape(flat_site=False)
        assert flat_core_below_grade_seed_refusals(
            layout, G, BF._hard_truth_spine_seeds(layout, G)) == {}
        ceiling, _floor = spine_value_fields(layout, G)
        assert abs(ceiling[1] - EAT_PIN_M) < 1e-9
        # Published EMPTY, never absent: "inert" is a stated fact.
        assert layout._flat_core_seed_refusals == {}

    def test_A_BELOW_GRADE_BODY_KEEPS_ITS_SEED(self):
        """KCLT's round-10 tunnel table and OTHH's 8/8 systems: inside a
        below-grade body the value IS the surface, and R17b-1 already
        scopes its reach to that body.  Membership is the family's own
        enumeration, never a value test."""
        plate = geometry.box(1450.0, 1450.0, 1550.0, 1550.0)
        layout, G = _vhhh_shape(shapes=[_Shape("tunnel_road", plate,
                                               role="tunnel_ramp")])
        assert flat_core_below_grade_seed_refusals(
            layout, G, BF._hard_truth_spine_seeds(layout, G)) == {}
        ceiling, _floor = spine_value_fields(layout, G)
        assert abs(ceiling[1] - EAT_PIN_M) < 1e-9

    def test_OUTSIDE_THE_CORE_IT_DOES_NOT_FIRE(self):
        """The law is about the CONSTANT core — where the ground is
        provably Z0.  Outside it a below-grade value may be the real
        surface, and this must not judge it."""
        far = (60000.0, 60000.0)
        layout, G = _vhhh_shape(pos_far=far)
        assert not _core_contains(layout, far)
        assert flat_core_below_grade_seed_refusals(
            layout, G, BF._hard_truth_spine_seeds(layout, G)) == {}

    def test_the_RUNWAY_ANCHOR_seeds_are_never_judged(self):
        """The law names the seed-completeness UNION.  A runway-join
        anchor is the band's own datum authority and stays one whatever
        its value — this refuses hard-truth seeds only."""
        layout, G = _vhhh_shape()
        G.runway_anchor = {0: SURFACE_M, 1: EAT_PIN_M}
        ceiling, _floor = spine_value_fields(layout, G)
        assert abs(ceiling[1] - EAT_PIN_M) < 1e-9

    def test_an_empty_hard_truth_is_the_inert_answer(self):
        layout, G = _vhhh_shape()
        assert flat_core_below_grade_seed_refusals(layout, G, {}) == {}


class TestTheRefusalIsONEUnion:
    """A value refused as a SEED is refused as the REFERENCE too.

    ``_record_band_inversions`` re-reads the hard truth to raise
    ``floor_above_own_hard_value`` wherever a hard node sits below its
    own band floor.  Left unrefused there, R17c-1 would guarantee an
    inversion at every node it refuses — the band's floor now comes from
    the surface anchors, ~19.9 m above the EAT pin — and
    ``assert_no_final_band_inversion`` would kill the build on the law's
    own doing.
    """

    def test_the_refused_node_mints_no_band_inversion(self):
        layout, G = _vhhh_shape()
        spine_value_fields(layout, G)
        rows = list(getattr(layout, "_final_band_inversions", None) or [])
        assert not [r for r in rows
                    if r.get("klass") == "floor_above_own_hard_value"]
        assert BF.assert_no_final_band_inversion(layout, "VHHH") == 0

    def test_an_UNREFUSED_below_grade_hard_node_still_reports(self):
        """The recorder is not disabled — a below-grade node inside its
        own BODY keeps both its seed and its inversion accounting."""
        layout, G = _vhhh_shape(flat_site=False)
        G.runway_anchor = {0: SURFACE_M}
        spine_value_fields(layout, G)
        # No refusal happened (no flat site), so the hard truth is intact
        # and the recorder saw all of it.
        assert layout._flat_core_seed_refusals == {}


class TestProductionSAYSWhatItDid:
    """Fired or inert, the build states it — and an inert law says WHY.

    Round 17c paid for this rule: two instrumented VHHH builds printed
    nothing here, and "the law did not fire" was indistinguishable from
    "it fired and the line was lost".
    """

    def test_it_publishes_the_refusal_map_even_when_empty(self):
        layout, G = _vhhh_shape(value=Z0_M)
        spine_value_fields(layout, G)
        assert layout._flat_core_seed_refusals == {}

    def test_the_inert_reason_names_a_missing_flat_site(self):
        layout, _G_ = _vhhh_shape(flat_site=False)
        assert "no flat-site substitution" in BF._flat_core_inert_reason(
            layout)

    def test_the_inert_reason_names_the_margin_when_the_site_is_there(self):
        layout, _G_ = _vhhh_shape()
        reason = BF._flat_core_inert_reason(layout)
        assert "below Z0=7.315" in reason and "core" in reason
