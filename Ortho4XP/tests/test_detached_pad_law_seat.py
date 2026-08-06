"""DETACHED BUILDING PADS SEAT BY LAW — item 3(b), 2026-08-05.

OWNER LAW (RULINGS 2026-08-05, "DEM's role, and the constant-DEM
invariant"): *"DEM chooses WHERE in the lawful band a thing seats.  It
never shapes the band, never constrains, never blocks."*

A pad that touches no qualifying airside pavement used to be HARD-PINNED
at its raw-DEM footprint median for the whole solve
(``build_detached_pad_dem_pins`` + ``config.DETACHED_PAD_DEM_PIN``), and
excluded from every movable-pad relaxation.  Both are DELETED.  These
twins pin the replacement:

* the pad is a GROUNDSIDE object, so its datum is the SOLVED groundside
  pavement it abuts, resolved by the adjacent-ground foot rule
  (interpolate two solved host ring variables);
* buildings are FLAT, so the lawful levels are the INTERSECTION over the
  pad's contacts of ``[datum − cap·d, datum + cap·d]``;
* the DEM seed picks the point INSIDE that box and nothing else — which
  is the constant-DEM oracle in unit form: the same solved hosts give the
  SAME box in the plateau and canyon worlds, while the seat saturates at
  the FLOOR and the CEILING respectively;
* NO HOST ⇒ NO BOX and no write.  A missing datum never falls back to
  the DEM sample; that fallback is the defect this replaced.

No network, no DEM, no fixtures: a stub layout and arithmetic.
"""
from __future__ import annotations

import os
import sys

import pytest
from shapely.geometry import Polygon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    anchors as A)
from auto_patch.layout import (                               # noqa: E402
    ROLE_BUILDING, ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD)

CAP = 0.05                      # GROUNDSIDE_MAX_GRADE, the lot's own cap


class _CPS:
    """Exact-coordinate registry (the real one interns within 0.5 m;
    these twins place every point far enough apart that the two agree)."""

    def get_or_add(self, x, y):
        return (round(float(x), 6), round(float(y), 6))


class _Shape:
    def __init__(self, role, ring):
        self.role = role
        self.polygon = Polygon(ring + [ring[0]])


class _Layout:
    def __init__(self, shapes):
        self.canonical_points = _CPS()
        self.shapes = list(shapes)


# ── the fixture geometry ─────────────────────────────────────────────
# A groundside LOT (y ≤ 10) solved at 100 m, and a building pad hovering
# 1 m clear of its edge.  The pad's two near vertices foot onto the lot's
# top edge at d = 1 m; its far vertices are 5 m away, past the contact
# radius, so they contribute nothing.
_LOT = [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0)]
_PAD = [(5.0, 11.0), (9.0, 11.0), (9.0, 15.0), (5.0, 15.0)]
_ROAD = [(0.0, 15.0), (20.0, 15.0), (20.0, 20.0), (0.0, 20.0)]

_B2I = {(0.0, 0.0): 0, (20.0, 0.0): 1, (20.0, 10.0): 2, (0.0, 10.0): 3,
        (5.0, 11.0): 4, (9.0, 11.0): 5, (9.0, 15.0): 6, (5.0, 15.0): 7,
        (0.0, 15.0): 8, (20.0, 15.0): 9, (20.0, 20.0): 10,
        (0.0, 20.0): 11}
_PAD_IDX = [4, 5, 6, 7]


def _elev(pad_seed, lot=100.0, road=110.0):
    return [lot, lot, lot, lot,
            pad_seed, pad_seed, pad_seed, pad_seed,
            road, road, road, road]


def _layout(with_road=False):
    shapes = [_Shape(ROLE_GROUNDSIDE_PAVEMENT, _LOT),
              _Shape(ROLE_BUILDING, _PAD)]
    if with_road:
        shapes.append(_Shape(ROLE_SERVICE_ROAD, _ROAD))
    return _Layout(shapes)


def _pad_shape(layout):
    return [s for s in layout.shapes if s.role == ROLE_BUILDING][0]


# ══════════════════════════════════════════════════════════════════════
# THE DEM PIN IS GONE
# ══════════════════════════════════════════════════════════════════════

class TestThePinIsDeleted:
    def test_the_dem_pin_builder_no_longer_exists(self):
        assert not hasattr(A, "build_detached_pad_dem_pins"), (
            "the raw-DEM hard pin is DEM as a constraint (RULINGS "
            "2026-08-05); it was replaced by a groundside law seat")

    def test_the_gate_no_longer_exists(self):
        from auto_patch import config
        assert not hasattr(config, "DETACHED_PAD_DEM_PIN")

    def test_no_pass_publishes_the_detached_exclusion_set(self):
        """``layout._detached_pad_node_idx`` kept detached pads out of
        every movable-pad relaxation because they carried a DEM value to
        protect.  With the value chosen by law and bounded by a
        ``seat_boxes`` box, the exclusion is retired — a detached pad is
        an ordinary movable FLAT pad group."""
        import inspect
        from auto_patch.elevation_per_surface.route_profile import solve
        src = inspect.getsource(solve)
        assert "layout._detached_pad_node_idx = " not in src
        assert "seat_detached_pads_by_law" in src


# ══════════════════════════════════════════════════════════════════════
# MEMBERSHIP + THE BAND WITHHOLDING (the attributed writer)
# ══════════════════════════════════════════════════════════════════════

class TestMembership:
    def test_a_pad_with_no_seated_ring_node_is_detached(self):
        lay = _layout()
        pads = A.detached_pad_nodes(lay, _B2I, {})
        assert [idx for (_s, idx) in pads] == [_PAD_IDX]

    def test_a_seated_ring_node_disqualifies_the_pad(self):
        """The SEAT producer owns the airside-service verdict; this reads
        it rather than re-deriving it (one instrument, one population —
        the exact failure that let the airside band reach a pad the seat
        had refused)."""
        lay = _layout()
        assert A.detached_pad_nodes(lay, _B2I, {5: 100.0}) == []


class TestBandWithholding:
    def test_the_airside_band_is_withheld_from_exactly_the_pad_nodes(self):
        """THE SOURCE FIX.  ``raster_reach_band._domain_geom`` admits every
        ROLE_BUILDING polygon to the airside propagation domain with no
        service test, so a detached pad inherits an airside route FLOOR
        (``spine_value_fields``) that ``one_profile_solve`` clamps it up
        to at warm start and holds every sweep — the measured KBNA
        plateau.  Withholding the band is what removes that writer."""
        lay = _layout()
        pads = A.detached_pad_nodes(lay, _B2I, {})
        band = [(170.0, 175.0)] * 12
        withheld, kept = A.withhold_airside_band_from_detached_pads(band, pads)
        assert withheld == set(_PAD_IDX) and kept == 0
        assert all(band[i] is None for i in _PAD_IDX)
        assert all(band[i] == (170.0, 175.0)
                   for i in range(12) if i not in _PAD_IDX)

    def test_withholding_never_adds_a_bound(self):
        """Constant-DEM safety by construction: the pass only ever writes
        ``None``, so it cannot manufacture a bound in either world."""
        import inspect
        src = inspect.getsource(A.withhold_airside_band_from_detached_pads)
        assigns = [ln for ln in src.splitlines()
                   if "node_band[i]" in ln and "=" in ln]
        assert assigns and all("None" in ln for ln in assigns)


# ══════════════════════════════════════════════════════════════════════
# THE LAW BOX — solved host variables only
# ══════════════════════════════════════════════════════════════════════

class TestLawBox:
    def test_the_box_is_the_host_datum_plus_or_minus_cap_times_reach(self):
        lay = _layout()
        lo, hi, n_c, n_x = A.detached_pad_law_box(
            lay, _B2I, _elev(1.0), _pad_shape(lay), _PAD_IDX, CAP)
        assert n_c == 2 and n_x == 0        # the two near vertices only
        assert lo == pytest.approx(100.0 - CAP * 1.0)
        assert hi == pytest.approx(100.0 + CAP * 1.0)

    def test_the_datum_is_the_foot_lerp_of_two_solved_host_variables(self):
        """A SLOPED host (2 %, inside the lot's own cap): the pad's near
        vertices foot at x = 5 and x = 9 on the lot's top edge, whose ends
        are solved 100.0 and 100.4.  The datum is the INTERPOLATION of two
        solved variables — the adjacent-ground foot rule — and the box is
        the intersection of the two contacts' intervals.  No DEM term
        appears anywhere in it."""
        lay = _layout()
        elev = _elev(1.0)
        elev[3] = 100.0                     # (0, 10)
        elev[2] = 100.4                     # (20, 10)
        lo, hi, n_c, n_x = A.detached_pad_law_box(
            lay, _B2I, elev, _pad_shape(lay), _PAD_IDX, CAP)
        # foot at x=5 → 100.10, at x=9 → 100.18, both at d = 1 m
        assert n_c == 2 and n_x == 0
        assert lo == pytest.approx(100.18 - CAP)
        assert hi == pytest.approx(100.10 + CAP)

    def test_no_host_means_no_box_never_a_dem_fallback(self):
        lay = _Layout([_Shape(ROLE_BUILDING, _PAD)])   # nothing to abut
        assert A.detached_pad_law_box(
            lay, _B2I, _elev(1.0), _pad_shape(lay), _PAD_IDX,
            CAP) == (None, None, 0, 0)

    def test_an_empty_intersection_is_a_DECLARED_conflict(self):
        """Two hosts a flat pad cannot both meet is the split-level-seat
        law's trigger (RULINGS 2026-08-04) — counted and reported, never
        silently resolved; the first claimant's box is kept, exactly as
        the adjacent-ground foot rule does."""
        lay = _layout(with_road=True)
        lo, hi, n_c, n_x = A.detached_pad_law_box(
            lay, _B2I, _elev(1.0), _pad_shape(lay), _PAD_IDX, CAP)
        assert n_c == 4 and n_x == 2
        assert lo == pytest.approx(100.0 - CAP)        # first claimant
        assert hi == pytest.approx(100.0 + CAP)


# ══════════════════════════════════════════════════════════════════════
# THE SEAT — and the constant-DEM oracle in unit form
# ══════════════════════════════════════════════════════════════════════

class TestSeat:
    def _seat(self, pad_seed):
        lay = _layout()
        elev = _elev(pad_seed)
        pads = A.detached_pad_nodes(lay, _B2I, {})
        seats, stats = A.seat_detached_pads_by_law(
            lay, _B2I, elev, pads, CAP)
        return lay, elev, seats, stats

    def test_the_pad_seats_flat_inside_its_box(self):
        _lay, elev, seats, stats = self._seat(100.02)
        # (seated, unhosted, contact-conflicts, band-wins, narrowed, split)
        assert stats == (1, 0, 0, 0, 0, 0)
        assert len({round(v, 9) for v in seats.values()}) == 1
        assert seats[4] == pytest.approx(100.02)
        assert all(elev[i] == pytest.approx(100.02) for i in _PAD_IDX)

    def test_the_box_is_registered_on_the_seat_boxes_channel(self):
        """The ratified bounded-yield channel: fp#8 and the final
        projection both resolve ``seat_boxes`` by canonical key, so the
        pad rides the existing group-bounds machinery."""
        lay, _elev, _seats, _stats = self._seat(100.0)
        from auto_patch.elevation_per_surface.node_space import store_of
        boxes = store_of(lay).raw("seat_boxes")
        for (x, y) in _PAD:
            assert boxes[(x, y)] == pytest.approx(
                (100.0 - CAP, 100.0 + CAP))

    # ── THE ORACLE ────────────────────────────────────────────────────
    def test_the_box_is_identical_in_both_constant_dem_worlds(self):
        """ASSERTION: the DEM never shapes the band.  Same solved hosts,
        two seeds 10 km apart, one box."""
        from auto_patch.constant_dem import (
            CANYON_ELEVATION_M, PLATEAU_ELEVATION_M)
        lay = _layout()
        box_lo = A.detached_pad_law_box(
            lay, _B2I, _elev(PLATEAU_ELEVATION_M), _pad_shape(lay),
            _PAD_IDX, CAP)
        box_hi = A.detached_pad_law_box(
            lay, _B2I, _elev(CANYON_ELEVATION_M), _pad_shape(lay),
            _PAD_IDX, CAP)
        assert box_lo == box_hi

    def test_the_plateau_world_seats_at_the_floor_the_canyon_at_the_ceiling(
            self):
        """ADDENDUM assertion 2 (extreme-seating saturation) and 3 (the
        band-width field): the two worlds differ by exactly the box
        width, which is what the emitted difference field must show."""
        from auto_patch.constant_dem import (
            CANYON_ELEVATION_M, PLATEAU_ELEVATION_M)
        _l, _e, lo_seats, _s = self._seat(PLATEAU_ELEVATION_M)
        _l2, _e2, hi_seats, _s2 = self._seat(CANYON_ELEVATION_M)
        assert lo_seats[4] == pytest.approx(100.0 - CAP)   # FLOOR
        assert hi_seats[4] == pytest.approx(100.0 + CAP)   # CEILING
        assert hi_seats[4] - lo_seats[4] == pytest.approx(2 * CAP)

    def test_a_hostless_pad_keeps_its_seed_and_is_reported(self):
        lay = _Layout([_Shape(ROLE_BUILDING, _PAD)])
        elev = _elev(158.0)
        before = list(elev)
        pads = A.detached_pad_nodes(lay, _B2I, {})
        seats, stats = A.seat_detached_pads_by_law(
            lay, _B2I, elev, pads, CAP)
        assert seats == {} and stats == (0, 1, 0, 0, 0, 0)
        assert elev == before


# ══════════════════════════════════════════════════════════════════════
# CYCLE-7 FIX 2 — FRONTAGE COUPLING ⇒ BAND SEATING (owner 2026-08-06)
# ══════════════════════════════════════════════════════════════════════
# Owner, verbatim intent: "A building close enough to have frontage and
# be coupled with the apron has to be seated based on the route graph
# that allows the apron to grade smoothly to its frontage within the
# apron's grade law."  Band-withholding keys on FRONTAGE COUPLING, not
# on touch; no DEM-datum value may bound a frontage-coupled node; a pad
# whose frontage band cannot be derived is a LOUD defect report, never a
# fallback to the datum pin.
#
# THE KNOWN ANSWER these twins are calibrated against (RULINGS 2026-08-06
# "Instrument truth is law", item 1) is the measured HECA carrier:
# building172, band WITHHELD, contact box [1.6576, 1.6576] at the
# groundside datum, an apron partner banded from 62.495 m across a
# 0.0646 m chord budget — a permanent clamp/sweep 2-cycle whose residual
# is 60.772738 m at sweep 1 and at sweep 49,600 alike.  Every case below
# is that arithmetic in eleven nodes.

_APRON_BAND = (162.0, 172.0)          # the coupled airside node's band
_APRON_NODE = 2                       # a lot vertex, standing in as the
#                                       banded airside partner
_BUDGET = 0.0646                      # 1 % apron cap over a 6.46 m chord


def _bands(apron=_APRON_BAND):
    """``node_band`` with the pad's own entries WITHHELD (``None``) —
    what the pre-ruling withhold left on every detached pad."""
    band = [None] * 12
    band[_APRON_NODE] = apron
    return band


def _coupled(partner=_APRON_NODE, budget=_BUDGET):
    """One pad (ordinal 0) with one frontage coupling."""
    return {0: ((partner, budget),)}


def _seat_with(frontage, node_band, pad_seed=100.02):
    lay = _layout()
    elev = _elev(pad_seed)
    pads = A.detached_pad_nodes(lay, _B2I, {})
    seats, stats = A.seat_detached_pads_by_law(
        lay, _B2I, elev, pads, CAP,
        frontage_coupled=frontage, node_band=node_band)
    return lay, elev, seats, stats


class TestFrontageBandSeating:
    def test_a_frontage_coupled_pad_seats_FROM_THE_BAND_not_the_datum(self):
        """The carrier class, resolved.

        The groundside contact datum admits ~100 m; the pad's frontage
        chord to a partner banded [162, 172] admits [161.94, 172.06].
        The ruling is not "reconcile" — the datum is NOT ITS LAW: the
        seat comes from the band, and DEM only chooses inside it.
        """
        _lay, elev, seats, stats = _seat_with(_coupled(), _bands())
        assert stats[3] == 1, "one pad seated from its frontage band"
        assert stats[4] == 0 and stats[5] == 0
        # The DEM seed (100.02) is below the lawful range, so the seat
        # takes its nearest lawful point — seed, never bound.
        assert seats[4] == pytest.approx(_APRON_BAND[0] - _BUDGET)
        assert all(elev[i] == pytest.approx(_APRON_BAND[0] - _BUDGET)
                   for i in _PAD_IDX)

    def test_the_contact_datum_never_bounds_a_frontage_coupled_pad(self):
        """"No DEM-datum value may be a bound on any frontage-coupled
        node" — so a seed INSIDE the band's range is honoured even
        though the contact box would have forbidden it."""
        _lay, _elev_, seats, stats = _seat_with(
            _coupled(), _bands(), pad_seed=165.0)
        assert stats[3] == 1
        assert seats[4] == pytest.approx(165.0), (
            "DEM chooses WHERE inside the lawful range; the 100 m "
            "contact box has no say")

    def test_a_pad_with_no_frontage_coupling_stays_a_groundside_citizen(self):
        """Ruling item 2: only a building with NO frontage coupling is a
        pure groundside citizen — it seats at DEM inside its contact box
        and affects nothing airside."""
        _lay, _elev_, seats, stats = _seat_with({}, _bands())
        assert stats[3] == 0 and stats[4] == 0 and stats[5] == 0
        assert seats[4] == pytest.approx(100.02)

    def test_an_underivable_frontage_band_is_LOUD_and_never_falls_back(self):
        """A frontage-coupled pad whose partner carries no band cannot be
        seated by this law.  The ruling forbids the fallback outright, so
        the pad is left unbounded on its seed and COUNTED."""
        lay = _layout()
        elev = _elev(100.02)
        before = list(elev)
        pads = A.detached_pad_nodes(lay, _B2I, {})
        seats, stats = A.seat_detached_pads_by_law(
            lay, _B2I, elev, pads, CAP,
            frontage_coupled=_coupled(), node_band=[None] * 12)
        assert stats[4] == 1, "counted as underivable"
        assert stats[3] == 0 and stats[0] == 0
        assert seats == {} and elev == before, "no write, no datum pin"

    def test_contradictory_frontage_couplings_are_a_LOUD_split_level(self):
        """Two couplings no single flat level meets is the split-level
        sectioned-seat law's trigger (RULINGS 2026-08-04) — reported,
        never silently resolved, and never resolved to the datum."""
        band = [None] * 12
        band[2] = (162.0, 172.0)
        band[3] = (100.0, 100.0)
        lay = _layout()
        elev = _elev(100.02)
        before = list(elev)
        pads = A.detached_pad_nodes(lay, _B2I, {})
        seats, stats = A.seat_detached_pads_by_law(
            lay, _B2I, elev, pads, CAP,
            frontage_coupled={0: ((2, _BUDGET), (3, _BUDGET))},
            node_band=band)
        assert stats[5] == 1 and stats[3] == 0
        assert seats == {} and elev == before

    def test_omitting_the_coupling_leaves_the_pre_ruling_behaviour(self):
        """Absent instrument ⇒ absent law: no pad is frontage-coupled."""
        lay = _layout()
        elev = _elev(100.02)
        pads = A.detached_pad_nodes(lay, _B2I, {})
        seats, stats = A.seat_detached_pads_by_law(lay, _B2I, elev, pads, CAP)
        assert stats == (1, 0, 0, 0, 0, 0)
        assert seats[4] == pytest.approx(100.02)

    def test_the_seat_interval_is_the_band_widened_by_the_chord_budget(self):
        """A pad coupled by a frontage chord of budget B to a node banded
        [lo, hi] may sit anywhere in [lo - B, hi + B]: from any such
        level the chord grades within the apron's law to some in-band
        partner value.  That IS the owner's sentence, read forward."""
        lo, hi, n = A.frontage_band_seat_interval(
            _PAD_IDX, ((_APRON_NODE, _BUDGET),), _bands())
        assert n == 1
        assert lo == pytest.approx(_APRON_BAND[0] - _BUDGET)
        assert hi == pytest.approx(_APRON_BAND[1] + _BUDGET)


class TestFrontageWithholding:
    """Ruling item 2 — the withholding keys on COUPLING, not on touch."""

    def test_a_frontage_coupled_pad_KEEPS_its_band(self):
        band = [(1.0, 2.0)] * 12
        pads = A.detached_pad_nodes(_layout(), _B2I, {})
        withheld, kept = A.withhold_airside_band_from_detached_pads(
            band, pads, 12, frontage_coupled=_coupled())
        assert kept == 1 and withheld == set()
        assert all(b is not None for b in band)

    def test_an_uncoupled_pad_still_has_its_band_withheld(self):
        band = [(1.0, 2.0)] * 12
        pads = A.detached_pad_nodes(_layout(), _B2I, {})
        withheld, kept = A.withhold_airside_band_from_detached_pads(
            band, pads, 12, frontage_coupled={})
        assert kept == 0 and withheld == set(_PAD_IDX)
        assert all(band[i] is None for i in _PAD_IDX)

    def test_no_coupling_map_is_the_unconditional_pre_ruling_form(self):
        band = [(1.0, 2.0)] * 12
        pads = A.detached_pad_nodes(_layout(), _B2I, {})
        withheld, kept = A.withhold_airside_band_from_detached_pads(
            band, pads, 12)
        assert kept == 0 and withheld == set(_PAD_IDX)


class TestFrontageCouplingRecognition:
    """The coupling test itself — touching AND near-miss, ruling item 1."""

    class _Cap:
        def at(self, d, _z):
            return 0.01 * d           # the apron's 1 % law

    class _G:
        def __init__(self, edges, families, pos):
            self.edges = edges
            self.edge_family = families
            self.pos = pos

    def _graph(self, family):
        # pad node 4 <-> node 2 (an apron vertex) at 6.46 m
        pos = {2: (5.0, 4.54), 4: (5.0, 11.0)}
        return self._G([(2, 4, self._Cap(), False)], [family], pos)

    def test_a_touching_apron_chord_IS_frontage(self):
        pads = A.detached_pad_nodes(_layout(), _B2I, {})
        out = A.detached_pad_frontage_coupling(
            pads, self._graph("unified:apron"))
        assert 0 in out
        (partner, budget), = out[0]
        assert partner == 2 and budget == pytest.approx(0.0646)

    def test_a_groundside_chord_is_NOT_frontage(self):
        """A building that only abuts a lot or a service road is the pure
        groundside citizen the ruling exempts."""
        pads = A.detached_pad_nodes(_layout(), _B2I, {})
        assert A.detached_pad_frontage_coupling(
            pads, self._graph("unified:groundside_pavement")) == {}

    def test_a_near_miss_edge_IS_frontage(self):
        """Ruling item 3: the near-miss law minted the EDGE without the
        SEAT derivation.  This is the missing half's input."""
        pads = A.detached_pad_nodes(_layout(), _B2I, {})
        out = A.detached_pad_frontage_coupling(
            pads, self._graph("unified:groundside_pavement"),
            near_miss_edges=[(9, 5, 0.02)])
        assert out == {0: ((9, 0.02),)}

    def test_an_intra_pad_chord_is_not_a_coupling(self):
        """A rigid flat group cannot constrain its own level."""
        pads = A.detached_pad_nodes(_layout(), _B2I, {})
        g = self._G([(4, 5, self._Cap(), False)], ["unified:apron"],
                    {4: (5.0, 11.0), 5: (9.0, 11.0)})
        assert A.detached_pad_frontage_coupling(pads, g) == {}

    def test_the_tightest_budget_wins_on_a_duplicate_pair(self):
        pads = A.detached_pad_nodes(_layout(), _B2I, {})
        out = A.detached_pad_frontage_coupling(
            pads, self._graph("unified:apron"),
            near_miss_edges=[(2, 4, 0.001)])
        assert out == {0: ((2, 0.001),)}
