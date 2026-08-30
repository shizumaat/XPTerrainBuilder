"""THE ROAD BRIDGE DECK — RULINGS 2026-08-30c §1–§6.

Synthetic twins for the three clauses that decide the law's behaviour:
§1 detection (the tag, and only over an EMITTED structure), §3 protection
(the ramp cut passes a deck by), and §6 refusal (an abutment the road cap
cannot reach stands the bridge down).

The miniature is the LEMD site in the small: a service way tagged
``bridge=yes layer=1`` spanning a tunnel ramp, with the receiving surface
placed near or far to flip §6.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch import bridges, road_bridge_deck as deck
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.layout import (BuiltShape, ROLE_GROUNDSIDE_PAVEMENT,
                               ROLE_SERVICE_ROAD, ROLE_TUNNEL_RAMP)

ANCHOR = (40.4836, -3.5804)


class _Net:
    """Just enough of ``AirportRoadNetwork`` for §1/§2."""

    def __init__(self, ways, nodes, widths):
        self.ways = ways
        self.nodes = nodes
        self.widths = widths


class _Layout:
    def __init__(self):
        self.anchor = ANCHOR
        self.shapes: list = []
        self.icao = "TEST"
        self._to_m, self._m_to_ll = bridges._local_meter_projections(ANCHOR)
        self.canonical_points = CanonicalPointRegistry()
        self.airport_road_network = None

    def ll_to_m(self, lat, lon):
        return self._to_m(lon, lat)

    def m_to_ll(self, x, y):
        return self._m_to_ll(x, y)


def _ll(x_m, y_m):
    """Layout metres -> (lat, lon), through the layout's own projection."""
    _to_m, m_to_ll = bridges._local_meter_projections(ANCHOR)
    return m_to_ll(x_m, y_m)


def _rect(x0, x1, y0, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _make(*, bridge_tag="yes", ramp_top=600.17, east_receive=602.14,
          east_gap_m=17.9, with_ramp=True, tunnel_way=True):
    """A miniature crossing.

    The deck way runs west→east along y=0 from x=0 to x=84.2 (the LEMD
    span length).  A tunnel ramp sits under it, ending ``east_gap_m``
    short of the east abutment; the receiving groundside sits AT that
    abutment.
    """
    layout = _Layout()
    span = 84.2
    w_ll = _ll(0.0, 0.0)
    e_ll = _ll(span, 0.0)
    tags = {"highway": "service", "lanes": "4"}
    if bridge_tag is not None:
        tags["bridge"] = bridge_tag
        tags["layer"] = "1"
    ways = [("W1", ["n0", "n1"], tags)]
    nodes = {"n0": w_ll, "n1": e_ll}
    layout.airport_road_network = _Net(ways, nodes, {"W1": 14.0})

    # The mapped bore the prediction reads: a tunnel way whose end sits
    # just east of the span, so its portal walk can reach under it.
    if tunnel_way:
        b0 = _ll(span + 40.0, 0.0)
        b1 = _ll(span + 400.0, 0.0)
        layout._tunnel_road_network = (
            {"t0": b0, "t1": b1},
            [("T1", ["t0", "t1"],
              {"highway": "primary", "tunnel": "yes", "layer": "-2"})],
            None, {})

    if with_ramp:
        layout.shapes.append(BuiltShape(
            polygon=_rect(10.0, span - east_gap_m, -7.0, 7.0),
            role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
            node_altitudes=[ramp_top - 1.2, ramp_top,
                            ramp_top, ramp_top - 1.2]))
    # The receiving surface AT the east abutment.
    layout.shapes.append(BuiltShape(
        polygon=_rect(span - 2.0, span + 30.0, -9.0, 9.0),
        role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside",
        node_altitudes=[east_receive] * 4))
    # ...and one at the west abutment, high enough to be reachable.
    layout.shapes.append(BuiltShape(
        polygon=_rect(-40.0, 2.0, -9.0, 9.0),
        role=ROLE_SERVICE_ROAD, ref="road",
        node_altitudes=[605.0] * 4))
    return layout


def _mint_deck_pieces(layout):
    """Stand in for the corridor minter: one synthesised road piece
    covering the span, which ``stamp_shapes`` must recognise."""
    layout.shapes.append(BuiltShape(
        polygon=_rect(0.0, 84.2, -7.0, 7.0),
        role=ROLE_SERVICE_ROAD, ref="road",
        synthesised_road_corridor=True,
        node_altitudes=[600.9] * 4))


@pytest.fixture(autouse=True)
def _memoise_tunnel_network(monkeypatch):
    """``_load_tunnel_road_network`` reads caches off disk; the fixture
    hands the prediction its own miniature bore instead."""
    def _fake(layout):
        got = getattr(layout, "_tunnel_road_network", None)
        return got if got is not None else ({}, [], None, {})
    monkeypatch.setattr(bridges, "_load_tunnel_road_network", _fake)


# ── §1 — the tag is the ONLY trigger ────────────────────────────────
class TestScope:
    def test_a_bridge_tagged_way_over_a_bore_is_a_candidate(self):
        layout = _make()
        recs = deck.publish_candidates(layout)
        assert [r["way_id"] for r in recs] == ["W1"]

    def test_an_untagged_way_is_never_a_candidate(self):
        """"Where the bridge tag is absent, nothing changes: this law
        reads the tag, never infers a bridge from geometry.\""""
        layout = _make(bridge_tag=None)
        assert deck.publish_candidates(layout) == []

    def test_bridge_no_is_not_a_bridge(self):
        layout = _make(bridge_tag="no")
        assert deck.publish_candidates(layout) == []

    def test_no_reachable_bore_means_no_candidate(self):
        """§1 candidacy needs somewhere a below-grade structure can be."""
        layout = _make(tunnel_way=False)
        assert deck.publish_candidates(layout) == []

    def test_confirmation_needs_an_EMITTED_structure(self):
        """"`bridge=yes` alone mints nothing: with no emitted below-grade
        structure beneath it the way drapes exactly as today.\""""
        layout = _make(with_ramp=False)
        deck.publish_candidates(layout)
        _mint_deck_pieces(layout)
        deck.stamp_shapes(layout)
        report = deck.confirm_and_pin(layout)
        assert report["unconfirmed"] == 1 and report["confirmed"] == 0
        assert deck.pins_of(layout) == {}
        assert [r["verdict"] for r in deck.records_of(layout)] \
            == ["unconfirmed"]


# ── §2/§3 — what the flag does ──────────────────────────────────────
class TestProtection:
    def test_the_minted_piece_is_flagged_a_deck(self):
        layout = _make()
        deck.publish_candidates(layout)
        _mint_deck_pieces(layout)
        assert deck.stamp_shapes(layout) == 1
        assert any(deck.is_deck_shape(s) for s in layout.shapes)

    def test_the_ramp_cut_passes_a_deck_by(self):
        """§3: the SECOND exception to R14-2/A-3.  The identical piece
        WITHOUT the flag is cut, so this is the flag's own effect."""
        from auto_patch.bridges import cut_pavement_over_footprint
        footprint = _rect(10.0, 70.0, -8.0, 8.0)

        control = _make()
        _mint_deck_pieces(control)
        n_control = cut_pavement_over_footprint(
            control, footprint, cut_roles={ROLE_SERVICE_ROAD})

        armed = _make()
        deck.publish_candidates(armed)
        _mint_deck_pieces(armed)
        deck.stamp_shapes(armed)
        n_armed = cut_pavement_over_footprint(
            armed, footprint, cut_roles={ROLE_SERVICE_ROAD})

        assert n_control >= 1, "the control piece must be cuttable"
        assert n_armed == 0, "a deck is not cuttable pavement"

    def test_the_keep_out_covers_both_abutments(self):
        """§3: no free-end DEM tie at either abutment."""
        from shapely.geometry import Point
        layout = _make()
        deck.publish_candidates(layout)
        keep_out = deck.abutment_keep_out(layout)
        assert keep_out is not None
        # COVERS: an abutment sits exactly ON the corridor's end cap,
        # which is the point §3 exists to protect.
        assert keep_out.covers(Point(0.0, 0.0))
        assert keep_out.covers(Point(84.2, 0.0))

    def test_no_candidates_means_no_keep_out(self):
        layout = _make(bridge_tag=None)
        deck.publish_candidates(layout)
        assert deck.abutment_keep_out(layout) is None


# ── §4/§6 — the value and the refusal ───────────────────────────────
class TestValuationAndRefusal:
    def _run(self, **kw):
        layout = _make(**kw)
        deck.publish_candidates(layout)
        _mint_deck_pieces(layout)
        deck.stamp_shapes(layout)
        return layout, deck.confirm_and_pin(layout)

    def test_the_deck_value_is_the_surface_beneath_plus_the_clearance(self):
        """§4, through the config constant — never a hand-typed number."""
        from auto_patch.config import BRIDGE_ROAD_CLEARANCE_M
        layout, _ = self._run(east_gap_m=60.0)
        rec = deck.records_of(layout)[0]
        assert rec["highest_beneath_m"] == pytest.approx(600.17, abs=1e-3)
        assert rec["deck_value_m"] == pytest.approx(
            600.17 + float(BRIDGE_ROAD_CLEARANCE_M), abs=1e-3)

    def test_a_reachable_abutment_confirms_and_pins(self):
        """A long enough run to the receiving surface: the deck stands."""
        layout, report = self._run(east_gap_m=60.0)
        assert report["confirmed"] == 1 and report["refused"] == 0
        assert report["pins"] > 0
        assert deck.records_of(layout)[0]["verdict"] == "confirmed"

    def test_the_lemd_geometry_refuses(self):
        """§6, the owner's site in the small: 605.27 m of deck against a
        602.14 m receiver over 17.9 m is 17.5 %, past the 8 % road cap."""
        from auto_patch.config import SERVICE_ROAD_MAX_GRADE
        layout, report = self._run()
        assert report["refused"] == 1 and report["confirmed"] == 0
        rec = deck.records_of(layout)[0]
        assert rec["verdict"] == "refused"
        east = [c for c in rec["abutment_checks"] if c["side"] == "east"][0]
        assert east["run_m"] == pytest.approx(17.9, abs=0.6)
        assert east["grade_needed"] > float(SERVICE_ROAD_MAX_GRADE)
        assert deck.pins_of(layout) == {}

    def test_a_refused_deck_leaves_the_pre_law_surface(self):
        """§6 stand-down: a piece minted on BRIDGE EVIDENCE ALONE goes;
        the flag never survives a refusal."""
        layout = _make()
        deck.publish_candidates(layout)
        deck.note_bridge_evidence_only(layout, "W1", touched_pavement=False)
        _mint_deck_pieces(layout)
        deck.stamp_shapes(layout)
        before = len(layout.shapes)
        deck.confirm_and_pin(layout)
        assert len(layout.shapes) == before - 1
        assert not any(deck.is_deck_shape(s) for s in layout.shapes)

    def test_a_deck_that_touches_pavement_keeps_its_piece(self):
        """The stand-down restores TODAY's surface, and today's surface
        keeps a bridge way that passed the touching-pavement test."""
        layout = _make()
        deck.publish_candidates(layout)
        deck.note_bridge_evidence_only(layout, "W1", touched_pavement=True)
        _mint_deck_pieces(layout)
        deck.stamp_shapes(layout)
        before = len(layout.shapes)
        deck.confirm_and_pin(layout)
        assert len(layout.shapes) == before
        assert not any(deck.is_deck_shape(s) for s in layout.shapes)

    def test_the_structure_beneath_is_never_written(self):
        """§4: AIRSIDE IS KING is the DIRECTION of the constraint — the
        ramp keeps its authored profile whatever the deck does."""
        layout, _ = self._run(east_gap_m=60.0)
        ramp = [s for s in layout.shapes
                if s.role == ROLE_TUNNEL_RAMP][0]
        assert ramp.node_altitudes == pytest.approx(
            [598.97, 600.17, 600.17, 598.97])


class TestChainContinuity:
    """§2: "so the chain it belongs to is continuous end to end across
    the span".  A bridge that completes no ADMITTED chain is bridging
    nothing this build paves, and admitting it would mint road pavement
    where today there is none.  MEASURED at LEMD: the predicted extent
    alone makes 51 of the feed's 196 bridge ways candidates; requiring
    the chain join leaves 3, the owner's two among them.
    """

    def _with_neighbour(self, *, shares_node):
        layout = _make()
        span = 84.2
        # A plain (unbridged) way running west from the deck's west
        # abutment.  It shares node "n0" when it is the same chain.
        west = _ll(-120.0, 0.0)
        nbr_start = "n0" if shares_node else "nX"
        layout.airport_road_network.nodes["nW"] = west
        if not shares_node:
            layout.airport_road_network.nodes["nX"] = _ll(-1.0, 300.0)
        layout.airport_road_network.ways.append(
            (
                "W2", [nbr_start, "nW"],
                {"highway": "service", "lanes": "2"},
            ))
        layout.airport_road_network.widths["W2"] = 7.0
        return layout

    def test_a_bridge_joining_an_admitted_chain_is_a_candidate(self):
        layout = self._with_neighbour(shares_node=True)
        recs = deck.publish_candidates(
            layout, touches_pavement=lambda w, line: w == "W2")
        assert [r["way_id"] for r in recs] == ["W1"]

    def test_a_bridge_joining_nothing_admitted_is_dropped(self):
        """The whole point: it would mint pavement where today there is
        none, which is what §1's "drapes exactly as today" forbids."""
        layout = self._with_neighbour(shares_node=False)
        assert deck.publish_candidates(
            layout, touches_pavement=lambda w, line: w == "W2") == []

    def test_no_admitted_way_at_all_means_no_candidate(self):
        layout = self._with_neighbour(shares_node=True)
        assert deck.publish_candidates(
            layout, touches_pavement=lambda w, line: False) == []


class TestSlopedRampEncoding:
    """A TUNNEL RAMP IS A SLOPED RECT.  ``bridges`` builds it with
    ``altitude_high``/``altitude_low`` and NEITHER ``node_altitudes`` NOR
    ``altitude``, so a §1 reader that consults only the latter two sees
    no ramp at all.

    Measured at LEMD on 2026-08-30 (build ``lemddeck_closing``): four
    ramps lay beneath the owner's span, all four invisible, and both
    decks came back UNCONFIRMED instead of refused.  This is the twin
    for that miss.
    """

    def _sloped(self, low, high):
        return BuiltShape(
            polygon=_rect(10.0, 66.3, -7.0, 7.0),
            role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
            altitude_low=low, altitude_high=high)

    def test_a_sloped_ramp_is_seen_and_its_TOP_is_taken(self):
        layout = _make(with_ramp=False)
        layout.shapes.insert(0, self._sloped(598.97, 600.17))
        deck.publish_candidates(layout)
        _mint_deck_pieces(layout)
        deck.stamp_shapes(layout)
        deck.confirm_and_pin(layout)
        rec = deck.records_of(layout)[0]
        assert rec["structures_beneath"] == 1
        assert rec["highest_beneath_m"] == pytest.approx(600.17, abs=1e-3)

    def test_each_encoding_reports_the_same_top(self):
        """All three encodings are read, and the answer is the maximum
        elevation the shape carries however it spells it."""
        flat = BuiltShape(polygon=_rect(0, 1, 0, 1), role=ROLE_TUNNEL_RAMP,
                          ref="tunnel_ramp", altitude=600.17)
        sloped = self._sloped(598.97, 600.17)
        per_node = BuiltShape(
            polygon=_rect(0, 1, 0, 1), role=ROLE_TUNNEL_RAMP,
            ref="tunnel_ramp",
            node_altitudes=[598.97, 600.17, 600.17, 598.97])
        for s in (flat, sloped, per_node):
            assert deck._shape_top(s) == pytest.approx(600.17, abs=1e-3)

    def test_a_shape_carrying_no_elevation_is_skipped(self):
        bare = BuiltShape(polygon=_rect(0, 1, 0, 1),
                          role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp")
        assert deck._shape_top(bare) is None
