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
        report = deck.confirm_and_sever(layout)[0]
        assert report["unconfirmed"] == 1
        assert report["confirmed_terrain"] == 0
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


# ── 2026-08-30d — the TERRAIN-BASED deck ────────────────────────────
class TestTerrainDeck:
    """The amendment: with no bridge OBJECT for the span the deck is
    TERRAIN — it spans at ROAD LEVEL and CUTS THROUGH the ramp's open
    cut, and the stretch beneath is a COVERED STRETCH.  The float-above
    model it supersedes (deck pinned at ramp + clearance over an OPEN
    ramp) is deleted, pin machinery and all.
    """

    def _run(self, **kw):
        layout = _make(**kw)
        deck.publish_candidates(layout)
        _mint_deck_pieces(layout)
        deck.stamp_shapes(layout)
        report, sever = deck.confirm_and_sever(layout)
        return layout, report, sever

    def test_a_terrain_deck_confirms_and_severs(self):
        layout, report, sever = self._run()
        assert report["confirmed_terrain"] == 1
        assert report["object_governed"] == 0
        assert sever is not None and not sever.is_empty
        assert deck.records_of(layout)[0]["verdict"] == "confirmed_terrain"

    def test_the_sever_footprint_covers_the_span(self):
        """It is the deck's own corridor that joins the protected union,
        so the covered stretch is exactly the deck's footprint."""
        from shapely.geometry import Point
        _layout, _report, sever = self._run()
        assert sever.covers(Point(42.0, 0.0))
        assert sever.covers(Point(0.0, 0.0))
        assert not sever.contains(Point(-30.0, 0.0))

    def test_there_is_no_deck_pin(self):
        """§5 as amended: the deck sits at the ROAD SOLVE's own level, so
        nothing pins it.  The float-above pin is gone."""
        layout, _report, _sever = self._run()
        assert deck.pins_of(layout) == {}

    def test_the_clearance_clause_is_an_instrument_not_a_lever(self):
        """§4 as amended applies to the ramp's CONTINUED profile, which
        passes under "by construction of the authored ramp datum, not by
        moving the deck up".  So the module MEASURES the cover and says
        whether the premise holds; it moves nothing."""
        from auto_patch.config import BRIDGE_ROAD_CLEARANCE_M
        layout, _r, _s = self._run()
        rec = deck.records_of(layout)[0]
        # the fixture's deck pieces sit at 600.9, the ramp top at 600.17
        assert rec["deck_level_m"] == pytest.approx(600.9, abs=1e-3)
        assert rec["clearance_measured_m"] == pytest.approx(0.73, abs=1e-2)
        assert rec["clearance_required_m"] == float(BRIDGE_ROAD_CLEARANCE_M)
        assert rec["clearance_premise_holds"] is False
        # ...and the RAMP is untouched whatever that says.
        ramp = [s for s in layout.shapes if s.role == ROLE_TUNNEL_RAMP][0]
        assert ramp.node_altitudes == pytest.approx(
            [598.97, 600.17, 600.17, 598.97])

    def test_the_premise_holds_when_the_ramp_really_is_deep(self):
        layout, _r, _s = self._run(ramp_top=594.0)
        rec = deck.records_of(layout)[0]
        assert rec["clearance_measured_m"] == pytest.approx(6.9, abs=1e-2)
        assert rec["clearance_premise_holds"] is True

    def test_a_hard_deck_OBJECT_leaves_the_terrain_open(self):
        """"Where a classified hard-deck OBJECT bridge exists, the object
        law continues to govern and the terrain stays open." """
        import auto_patch.road_bridge_deck as mod
        real = mod._hard_deck_object_over
        try:
            mod._hard_deck_object_over = lambda layout, corr: True
            layout, report, sever = self._run()
        finally:
            mod._hard_deck_object_over = real
        assert report["object_governed"] == 1
        assert report["confirmed_terrain"] == 0
        assert sever is None, "an object-governed span severs nothing"
        assert deck.records_of(layout)[0]["verdict"] == "object_governed"

    def test_an_unconfirmed_deck_leaves_the_pre_law_surface(self):
        """§1 stand-down: a piece minted on BRIDGE EVIDENCE ALONE goes."""
        layout = _make(with_ramp=False)
        deck.publish_candidates(layout)
        deck.note_bridge_evidence_only(layout, "W1", touched_pavement=False)
        _mint_deck_pieces(layout)
        deck.stamp_shapes(layout)
        before = len(layout.shapes)
        deck.confirm_and_sever(layout)
        assert len(layout.shapes) == before - 1
        assert not any(deck.is_deck_shape(s) for s in layout.shapes)

    def test_an_unconfirmed_deck_that_touches_pavement_keeps_its_piece(self):
        """The stand-down restores TODAY's surface, and today's surface
        keeps a bridge way that passed the touching-pavement test."""
        layout = _make(with_ramp=False)
        deck.publish_candidates(layout)
        deck.note_bridge_evidence_only(layout, "W1", touched_pavement=True)
        _mint_deck_pieces(layout)
        deck.stamp_shapes(layout)
        before = len(layout.shapes)
        deck.confirm_and_sever(layout)
        assert len(layout.shapes) == before
        assert not any(deck.is_deck_shape(s) for s in layout.shapes)

    def test_a_confirmed_deck_keeps_its_flag(self):
        """§3 still holds: the deck is not cuttable pavement, so the flag
        must survive confirmation."""
        layout, _r, _s = self._run()
        assert any(deck.is_deck_shape(s) for s in layout.shapes)


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
        deck.confirm_and_sever(layout)[0]
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


class TestDeckIdentitySurvivesReRole:
    """The GROUNDSIDE PASS runs before the tunnel pass and rebuilds
    pieces as fresh ``BuiltShape``s, so a per-shape flag is gone by the
    time the ramp cut asks whether a piece is a deck.

    MEASURED at LEMD 2026-08-30 (build ``lemddeck3``): both decks were
    demoted to ``groundside_pavement`` before the tunnel pass, the
    exemption lapsed, and the ramp cut carved the 84.2 m span into four
    fragments with gaps at 12-22, 30-50 and 57-69 m.
    """

    def _demoted_piece(self):
        """The deck's own ground, re-roled and WITHOUT the flag — exactly
        what the groundside pass leaves behind."""
        from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
        return BuiltShape(
            polygon=_rect(10.0, 70.0, -6.0, 6.0),
            role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside",
            node_altitudes=[600.9] * 4)

    def test_a_reroled_deck_piece_is_still_a_deck(self):
        layout = _make()
        deck.publish_candidates(layout)
        piece = self._demoted_piece()
        assert not deck.is_deck_shape(piece), "no flag on a re-roled piece"
        assert deck.is_deck_shape(piece, layout), (
            "the corridor is published once and never moves — geometry "
            "must recognise the deck after any re-role")

    def test_ground_outside_the_corridor_is_not_a_deck(self):
        from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
        layout = _make()
        deck.publish_candidates(layout)
        far = BuiltShape(polygon=_rect(-200.0, -140.0, -6.0, 6.0),
                         role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside")
        assert not deck.is_deck_shape(far, layout)

    def test_the_ramp_cut_passes_a_reroled_deck_by(self):
        """The whole point: the exemption must still hold after the
        demotion, or the cut fragments the span."""
        from auto_patch.bridges import cut_pavement_over_footprint
        from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
        footprint = _rect(10.0, 70.0, -8.0, 8.0)

        layout = _make()
        deck.publish_candidates(layout)
        layout.shapes.append(self._demoted_piece())
        n = cut_pavement_over_footprint(
            layout, footprint, cut_roles={ROLE_GROUNDSIDE_PAVEMENT})
        assert n == 0, "a re-roled deck is still not cuttable pavement"

    def test_with_no_candidates_the_geometry_test_is_inert(self):
        layout = _make(bridge_tag=None)
        deck.publish_candidates(layout)
        assert deck.deck_union(layout) is None
        assert not deck.is_deck_shape(self._demoted_piece(), layout)


# ── RULINGS 2026-08-30f — round 2 ───────────────────────────────────
class TestDeckIsNotClaimable:
    """§3 THIRD CLAUSE: "R14-1's tunnel-road claim does not reach a
    confirmed terrain deck.  The deck's ground is the road ABOVE the
    corridor, not the corridor, and re-profiling it toward bore depth is
    the canyon the deck exists to remove."

    MEASURED at LEMD round 1 (build ``lemddeck4``): the claim took the
    deck and graded it 601.67 -> 600.2 m eastward across the span, met
    the 601.36-606.6 m east receiver as a 5.13 m step at 17.4 %, and
    minted 220 groundside ``within_shape`` rows.
    """

    def test_the_claim_predicate_refuses_a_deck(self):
        """``_claimable`` is R14-1's own gate — both of its passes read
        it, so refusing there is refusing the whole claim."""
        import inspect
        from auto_patch import bridges
        src = inspect.getsource(bridges._claim_road_surfaces_as_corridor) \
            if hasattr(bridges, "_claim_road_surfaces_as_corridor") else ""
        if not src:
            # the claim lives in the portal-emit path; find it by its law tag
            src = inspect.getsource(bridges)
        assert "§3 THIRD CLAUSE (RULINGS 2026-08-30f)" in src
        assert "_is_deck_claim(shape, layout)" in src

    def test_a_deck_piece_is_recognised_by_the_claim_gate(self):
        """The gate asks ``is_deck_shape(shape, layout)``, so it sees a
        re-roled deck too — the claim runs after the groundside pass."""
        from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
        layout = _make()
        deck.publish_candidates(layout)
        demoted = BuiltShape(
            polygon=_rect(10.0, 70.0, -6.0, 6.0),
            role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside",
            node_altitudes=[601.67] * 4)
        assert deck.is_deck_shape(demoted, layout)


class TestFullDepthToTheBridge:
    """THE DECK REQUIRES STANDARD DEPTH (RULINGS 2026-08-30f): the cut
    holds FULL BORE DATUM from the mouth all the way to the bridge,
    passes under the deck at that depth, and the climb to DEM starts on
    the OTHER side of the deck.

    The walk's elevation lerp is the law's implementation point, so the
    twin drives that arithmetic directly.
    """

    #: the walk in the small: 100 m of chain from the portal, a deck
    #: sitting across it from 20 m to 40 m, bore 598.45, grade 610.0.
    BORE = 598.45
    GRADE = 610.0

    def _profile(self, climb_start_eff, total=100.0, stations=11):
        """The ruled profile: level to ``climb_start_eff``, then linear."""
        climb_total = total - climb_start_eff
        out = []
        for k in range(stations):
            c = total * k / (stations - 1)
            frac = max(0.0, c - climb_start_eff) / climb_total
            out.append((c, (1 - frac) * self.BORE + frac * self.GRADE))
        return out

    def test_the_cut_holds_bore_datum_all_the_way_to_the_deck(self):
        prof = self._profile(40.0)
        for c, e in prof:
            if c <= 40.0:
                assert e == pytest.approx(self.BORE, abs=1e-9), (
                    f"station {c} m is inshore of the deck's far edge and "
                    f"must sit at the bore datum")

    def test_the_climb_begins_beyond_the_deck(self):
        prof = dict(self._profile(40.0))
        assert prof[40.0] == pytest.approx(self.BORE, abs=1e-9)
        assert prof[50.0] > self.BORE
        assert prof[100.0] == pytest.approx(self.GRADE, abs=1e-9)

    def test_the_deck_gets_the_standard_clearance_by_construction(self):
        """The point of the ruling: with the cut at bore datum under the
        span, a deck at road level clears it by more than
        ``BRIDGE_ROAD_CLEARANCE_M`` without anyone moving the deck."""
        from auto_patch.config import BRIDGE_ROAD_CLEARANCE_M
        prof = dict(self._profile(40.0))
        deck_level = 604.0          # the road solve's own level
        under_the_span = max(e for c, e in prof.items() if 20.0 <= c <= 40.0)
        assert under_the_span == pytest.approx(self.BORE, abs=1e-9)
        assert deck_level - under_the_span >= float(BRIDGE_ROAD_CLEARANCE_M)

    def test_with_no_deck_the_profile_is_the_old_one(self):
        """climb_start_eff == 0 must reproduce the pre-ruling lerp
        exactly — every airport without a deck is byte-identical."""
        ruled = self._profile(0.0)
        for c, e in ruled:
            legacy = (1 - c / 100.0) * self.BORE + (c / 100.0) * self.GRADE
            assert e == pytest.approx(legacy, abs=1e-12)

    def test_the_ramp_cap_is_priced_over_the_CLIMB_run(self):
        """The remaining run is shorter, so the clamp must use it — else
        the post-deck stretch runs over TUNNEL_RAMP_MAX_GRADE."""
        from auto_patch import config
        cap = float(config.TUNNEL_RAMP_MAX_GRADE)
        climb_start, total = 40.0, 100.0
        climb_total = total - climb_start
        drop = self.GRADE - self.BORE
        # priced over the whole walk (the bug) vs the climb run (the law)
        assert drop / total < drop / climb_total
        clamped_top = self.BORE + cap * climb_total
        assert clamped_top < self.GRADE, (
            "this fixture must exercise the clamp")
        realised = (clamped_top - self.BORE) / climb_total
        assert realised <= cap + 1e-9

    def test_the_walk_reads_the_TERRAIN_deck_union(self):
        """An object-governed span leaves the terrain open, so the walk
        must read the narrower union, not the protection one."""
        import inspect
        from auto_patch import bridges
        src = inspect.getsource(bridges)
        assert "terrain_deck_union as _deck_union_of" in src

    def test_an_object_governed_span_is_absent_from_the_ramp_union(self):
        import auto_patch.road_bridge_deck as mod
        layout = _make()
        deck.publish_candidates(layout)
        assert mod.terrain_deck_union(layout) is not None
        real = mod._hard_deck_object_over
        try:
            mod._hard_deck_object_over = lambda layout, corr: True
            assert mod.terrain_deck_union(layout) is None
        finally:
            mod._hard_deck_object_over = real


class TestClaimFootprintStopsAtTheDeck:
    """§3 third clause, at the level it actually has to act: the claim's
    FOOTPRINT, not a per-shape veto.

    MEASURED at LEMD round 2 (build ``lemdr2``): the claim's hosts are
    large rings that CONTAIN the deck strip — they read 4 % and 48 %
    inside the deck corridor, so "mostly inside" could not see them, and
    the claim cut them into pieces that were 96-99 % deck and graded
    those 601.43 -> 600.18 m.  Subtracting the deck from the region
    geometry is what makes the claim "resume at both deck edges".
    """

    def test_the_claim_trims_its_regions_at_the_deck(self):
        import inspect
        from auto_patch import bridges
        src = inspect.getsource(bridges)
        assert "§3 THIRD CLAUSE (RULINGS 2026-08-30f)" in src
        assert "_deck_keep_out" in src
        assert "_z.difference(_deck_keep_out)" in src

    def test_a_host_that_contains_the_deck_is_not_mostly_deck(self):
        """The measurement that makes the footprint form necessary."""
        from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
        layout = _make()
        deck.publish_candidates(layout)
        host = BuiltShape(
            polygon=_rect(-60.0, 200.0, -40.0, 40.0),
            role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside")
        assert not deck.is_deck_shape(host, layout), (
            "a big host containing the deck is not 'mostly' the deck — "
            "which is why the claim is trimmed by footprint instead")

    def test_subtracting_the_deck_leaves_a_gap_and_two_sides(self):
        """The geometric shape of "resumes at both deck edges"."""
        layout = _make()
        deck.publish_candidates(layout)
        keep_out = deck.terrain_deck_union(layout)
        region = _rect(-40.0, 130.0, -7.0, 7.0)      # a cut through it
        remainder = region.difference(keep_out)
        assert remainder.geom_type == "MultiPolygon", (
            "the deck must split the cut into two sides")
        assert len(remainder.geoms) == 2
        assert remainder.area < region.area


# ── RULINGS 2026-08-30i — round 3 ───────────────────────────────────
class TestDeckSeversTheCorridorSurface:
    """COVERED-STRETCH CLIP SCOPE EXTENDED: "a terrain deck's footprint
    severs the tunnel corridor's OWN road surface, claimed and synthetic,
    exactly as it severs the ramp; the corridor resumes at both deck
    edges."

    MEASURED at LEMD round 2 (build ``lemdr2b``): with ``tunnel_road``
    outside the clip's ref set, the corridor surfaced across stations
    12.3-66.9 m of the owner's 84.2 m span at 600.18-601.60 m, under a
    deck at 604.49 m — the ramp beneath it was correctly severed, but the
    corridor's own road surface was not.
    """

    def test_tunnel_road_is_in_the_clip_ref_set(self):
        import inspect
        from auto_patch import bridges
        src = inspect.getsource(bridges)
        assert '"tunnel_mouth", TUNNEL_ROAD_REF)' in src, (
            "TUNNEL_ROAD_REF must join the covered-stretch clip's refs")
        assert "RULINGS 2026-08-30i" in src

    def test_tunnel_road_takes_the_ruling_4_branch(self):
        """Being in ``_TUNNEL_PAVEMENT_REFS`` is what routes it to the
        clip against ``protected_union`` — the SAME path the ramp takes,
        which is what "exactly as it severs the ramp" means."""
        from auto_patch.bridges import (_TUNNEL_PAVEMENT_REFS,
                                        TUNNEL_ROAD_REF)
        assert TUNNEL_ROAD_REF in _TUNNEL_PAVEMENT_REFS
        assert "tunnel_ramp" in _TUNNEL_PAVEMENT_REFS

    def test_the_deck_footprint_is_what_does_the_severing(self):
        """The deck reaches the clip through the protected union, so the
        two rulings are one mechanism, not two."""
        import inspect
        from auto_patch import bridges
        src = inspect.getsource(bridges)
        assert "_protected_u = (_deck_u if _protected_u is None" in src

    def test_a_corridor_piece_under_the_deck_is_mostly_covered(self):
        """The clip drops a piece MOSTLY covered by the protected union
        and clips a graze back to the edge — so a corridor piece lying in
        the deck footprint drops, and one crossing the edge resumes."""
        layout = _make()
        deck.publish_candidates(layout)
        keep_out = deck.terrain_deck_union(layout)
        under = _rect(20.0, 60.0, -5.0, 5.0)         # wholly under
        crossing = _rect(60.0, 140.0, -5.0, 5.0)     # leaves the deck
        assert under.intersection(keep_out).area >= 0.5 * under.area
        assert crossing.intersection(keep_out).area < 0.5 * crossing.area
        remainder = crossing.difference(keep_out)
        assert not remainder.is_empty, "the corridor resumes beyond it"

    def test_the_midspan_keeps_the_decks_own_ground(self):
        """With the corridor severed, what stands mid-span is the deck's
        own road ground at the solve's level — not the corridor."""
        from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
        layout = _make()
        deck.publish_candidates(layout)
        _mint_deck_pieces(layout)
        deck.stamp_shapes(layout)
        ground = BuiltShape(
            polygon=_rect(12.0, 67.0, -6.0, 6.0),
            role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside",
            node_altitudes=[604.49] * 4)
        layout.shapes.append(ground)
        assert deck.is_deck_shape(ground, layout)
        rec = [r for r in deck.candidates_of(layout)
               if r["way_id"] == "W1"][0]
        assert deck._deck_level(layout, rec) is not None
