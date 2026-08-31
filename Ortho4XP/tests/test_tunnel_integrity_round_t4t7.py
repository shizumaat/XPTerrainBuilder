"""Tunnel-integrity round twins — §T4 (the road-piece ledger and the
lost fills) and §T7 (the covered-span mask).

Spec: ``docs/specs/tunnel-integrity-round-spec.md``.

§T4 NO ROAD-CORRIDOR PIECE IS EVER LOST SILENTLY.  The per-pass
     (role, ref) checkpoint names the pass that took a piece; a corridor
     JOIN is never dropped as a hairline; every removal that still
     happens carries a per-piece named line.
§T7 NO SYNTHESISED ROAD PAVEMENT OVER A COVERED SPAN.  One mask,
     published once, consumed by the minter AND by an emitter-
     independent post-mint suppression — and it kills SYNTHESIS, never
     authored data.

The §T5 (ramp-wall foot) twins live with the law they amend:
``test_round16_geometry_consistency.py``.  §T6's twins (claimed-corridor
walls, claim scope) are GONE with R14-1's claim class — RULINGS
2026-08-31b, ``docs/specs/linear-transport-redesign-spec.md`` §5.1 —
along with ``test_portal_corridor_claim.py`` and
``test_claimed_corridor_wall_survival.py``; the surviving R14 laws now
live in ``test_round14_tunnel_cut_and_ramp_run.py``, and the acceptance
instrument's tunnel checks in ``test_tunnel_portal_acceptance.py``.
"""
import pytest
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from auto_patch import covered_span, road_piece_ledger
from auto_patch.layout import (
    BuiltShape,
    PavementLayout,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_SERVICE_JUNCTION,
    ROLE_SERVICE_ROAD,
)
from auto_patch.pavement.service_roads import build_service_road_network


_ANCHOR = (25.25, 51.60)


def _layout(shapes=()):
    lay = PavementLayout(icao="ZZZZ", anchor=_ANCHOR)
    lay.shapes.extend(shapes)
    return lay


def _rect(x0, y0, x1, y1):
    return box(x0, y0, x1, y1)


# ═════════════════════════════════════════════════════════════════════
# §T4.1 — the per-pass checkpoint NAMES the pass
# ═════════════════════════════════════════════════════════════════════

class TestTheRoadPieceLedger:

    def _scene(self):
        return _layout([
            BuiltShape(polygon=_rect(0, 0, 10, 6),
                       role=ROLE_SERVICE_ROAD, ref="road"),
            BuiltShape(polygon=_rect(12, 0, 22, 6),
                       role=ROLE_SERVICE_ROAD, ref="road"),
            BuiltShape(polygon=_rect(10, 0, 12, 6),
                       role=ROLE_SERVICE_JUNCTION, ref="service"),
        ])

    def test_the_seam_that_takes_a_piece_is_the_seam_that_reports_it(
            self, capsys):
        """The attribution §T4 charters: a piece that vanishes between
        the minter and emit is named by the pass that took it.  Before
        this instrument the two ends disagreed by 40 rects and ~78 fills
        with no line anywhere in between."""
        lay = self._scene()
        road_piece_ledger.checkpoint(lay, "00_service_road_mint")
        road_piece_ledger.checkpoint(lay, "an-innocent-pass")
        lay.shapes = lay.shapes[:2]                 # the fill is taken
        road_piece_ledger.checkpoint(lay, "the-guilty-pass")
        road_piece_ledger.checkpoint(lay, "99_end_of_build")
        road_piece_ledger.report(lay, "ZZZZ")
        out = capsys.readouterr().out
        assert "the-guilty-pass" in out
        assert "an-innocent-pass" not in out, (
            "a seam that moved nothing must not be in the block — the "
            "block is the DELTAS, not a dump")
        assert "service_junction/service -1" in out
        assert "NET 00_service_road_mint" in out

    def test_the_block_is_printed_even_when_nothing_moved(self, capsys):
        """An absent block means the ledger did not run, which is a
        different fact from 'nothing was dropped'."""
        lay = self._scene()
        road_piece_ledger.checkpoint(lay, "00_service_road_mint")
        road_piece_ledger.checkpoint(lay, "99_end_of_build")
        road_piece_ledger.report(lay, "ZZZZ")
        out = capsys.readouterr().out
        assert "[road-piece-ledger]" in out and "no change" in out

    def test_off_is_silent_and_costs_one_env_read(self, capsys,
                                                  monkeypatch):
        monkeypatch.setenv("O4_ROAD_PIECE_LEDGER", "0")
        lay = self._scene()
        road_piece_ledger.checkpoint(lay, "00_service_road_mint")
        road_piece_ledger.report(lay, "ZZZZ")
        assert capsys.readouterr().out == ""
        assert getattr(lay, "_road_piece_ledger", None) is None

    def test_a_removal_is_named_per_piece(self, capsys):
        """§1's form, carried to the road removers: role, ref, place and
        area — a removal recorded only as a number is a removal nobody
        can find."""
        lay = self._scene()
        road_piece_ledger.log_removal(
            lay, lay.shapes[2], "runway-clip (sliver, joins nothing)")
        out = capsys.readouterr().out
        assert "[road-piece-remove] runway-clip (sliver, joins nothing)" \
            in out
        assert "role=service_junction" in out and "ref=service" in out
        assert "@25." in out and "m²" in out


class TestACorridorJoinIsNotAHairline:
    """§T4.1's fix at the named dropper: the runway clip's 1 m-inward-
    buffer sliver rule is calibrated for taxi-intersection remainders,
    and a rect-trim gap fill is exactly the shape it deletes."""

    def test_a_piece_touching_a_surviving_road_is_a_join(self):
        survivors = [_rect(0, 0, 10, 6), _rect(12, 0, 22, 6)]
        fill = _rect(10, 0, 12, 6)
        assert road_piece_ledger.joins_a_surviving_neighbour(
            fill, survivors)

    def test_a_piece_touching_nothing_is_not(self):
        survivors = [_rect(0, 0, 10, 6)]
        stray = _rect(40, 40, 41, 41)
        assert not road_piece_ledger.joins_a_surviving_neighbour(
            stray, survivors)

    def test_the_road_family_is_roles_not_refs(self):
        """A rect the scorer re-roled is still the corridor's pavement
        and still connects it — which is why the family is roles."""
        fam = road_piece_ledger.ROAD_FAMILY_ROLES
        assert {"service_road", "service_junction", "junction",
                "groundside_pavement"} <= set(fam)


# ═════════════════════════════════════════════════════════════════════
# §T7 — the covered-span mask
# ═════════════════════════════════════════════════════════════════════

def _bore_mask():
    """A 200 m bore running east, 12 m of carriageway."""
    return LineString([(0.0, 0.0), (200.0, 0.0)]).buffer(
        8.0, cap_style=2, join_style=2)


class TestTheMinterNeverMintsOverABore:

    def _route(self):
        # a service route running straight along the bore
        return [(LineString([(-40.0, 0.0), (240.0, 0.0)]), "road")]

    def test_no_rect_and_no_fill_inside_the_mask(self):
        rects, junctions = build_service_road_network(
            self._route(), None, width=6.0, min_len=5.0,
            covered_span=_bore_mask())
        mask = _bore_mask()
        # ABUTTING the mask is lawful — the corridor stops at the bore
        # edge and its last piece shares that edge.  OVERLAPPING it is
        # the defect: area, not touch.
        for rect, _axis, _role, _ref in rects:
            assert rect.intersection(mask).area == 0.0, (
                "a service_road rect stands on the bore's roof")
        for poly, _role, _ref in junctions:
            assert poly.intersection(mask).area == 0.0, (
                "a service_junction fill stands on the bore's roof")

    def test_the_corridor_outside_the_bore_still_mints(self):
        """The mask removes a stretch, never the road: both approaches
        survive as their own runs."""
        rects, _j = build_service_road_network(
            self._route(), None, width=6.0, min_len=5.0,
            covered_span=_bore_mask())
        assert len(rects) >= 2, (
            f"the mask ate the whole corridor: {len(rects)} rect(s)")

    def test_without_a_mask_the_corridor_is_minted_whole(self):
        """The control, one variable."""
        rects, _j = build_service_road_network(
            self._route(), None, width=6.0, min_len=5.0)
        assert len(rects) == 1, [r[0].bounds for r in rects]
        assert rects[0][0].intersects(_bore_mask())


class TestThePostMintSuppression:

    def _scene(self, monkeypatch):
        monkeypatch.setenv("O4_COVERED_SPAN_MASK", "1")
        lay = _layout([
            # SYNTHESISED, on the roof — must go
            BuiltShape(polygon=_rect(20, -3, 40, 3),
                       role=ROLE_SERVICE_ROAD, ref="road",
                       synthesised_road_corridor=True),
            # SYNTHESISED, demoted to groundside by the scorer, on the
            # roof — must go too (the flag rides the shape)
            BuiltShape(polygon=_rect(60, -3, 80, 3),
                       role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside",
                       synthesised_road_corridor=True),
            # AUTHORED pavement over the same bore — must STAY
            BuiltShape(polygon=_rect(100, -3, 120, 3),
                       role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside"),
            # SYNTHESISED but far away — must STAY
            BuiltShape(polygon=_rect(20, 400, 40, 406),
                       role=ROLE_SERVICE_ROAD, ref="road",
                       synthesised_road_corridor=True),
            # SYNTHESISED, only GRAZING the bore edge — must STAY
            BuiltShape(polygon=_rect(140, 6, 160, 30),
                       role=ROLE_SERVICE_ROAD, ref="road",
                       synthesised_road_corridor=True),
        ])
        lay._covered_span_mask = _bore_mask()
        return lay

    def test_synthesis_over_the_bore_goes_and_data_stays(
            self, monkeypatch, capsys):
        lay = self._scene(monkeypatch)
        n = covered_span.suppress_synthesised_road_pavement(lay, "ZZZZ")
        assert n == 2, [(s.role, s.ref) for s in lay.shapes]
        kept = [(s.role, s.ref, s.synthesised_road_corridor)
                for s in lay.shapes]
        assert (ROLE_GROUNDSIDE_PAVEMENT, "groundside", False) in kept, (
            "AUTHORED pavement over a bore was suppressed — the mask "
            "kills synthesis, not data")
        assert len(lay.shapes) == 3
        out = capsys.readouterr().out
        assert out.count("[road-piece-remove] covered-span mask") == 2, (
            "a suppression without a named line is a silent removal")

    def test_off_suppresses_nothing(self, monkeypatch):
        lay = self._scene(monkeypatch)
        monkeypatch.setenv("O4_COVERED_SPAN_MASK", "0")
        assert covered_span.suppress_synthesised_road_pavement(
            lay, "ZZZZ") == 0
        assert len(lay.shapes) == 5

    def test_no_mask_published_suppresses_nothing(self, monkeypatch):
        monkeypatch.setenv("O4_COVERED_SPAN_MASK", "1")
        lay = _layout([BuiltShape(polygon=_rect(20, -3, 40, 3),
                                  role=ROLE_SERVICE_ROAD, ref="road",
                                  synthesised_road_corridor=True)])
        assert covered_span.mask_of(lay) is None
        assert covered_span.suppress_synthesised_road_pavement(
            lay, "ZZZZ") == 0


class TestTheMaskIsPublishedOnce:

    def test_publish_is_idempotent_and_never_raises(self, monkeypatch):
        """A build with no road cache reachable publishes an EMPTY mask
        and says so — it never fails the build, and it never re-derives."""
        monkeypatch.setenv("O4_COVERED_SPAN_MASK", "1")
        lay = _layout()
        covered_span.publish(lay)
        first = covered_span.mask_of(lay)
        lay._covered_span_mask = _bore_mask()
        covered_span.publish(lay)                  # must NOT overwrite
        assert covered_span.mask_of(lay) is not first or first is None
        assert covered_span.mask_of(lay).equals(_bore_mask())

    def test_the_synthesis_flag_rides_the_shape(self):
        """``dataclasses.replace`` is how every clip re-mints a piece;
        the flag must survive it, or a clipped rect becomes 'authored'."""
        from dataclasses import replace
        s = BuiltShape(polygon=_rect(0, 0, 10, 6),
                       role=ROLE_SERVICE_ROAD, ref="road",
                       synthesised_road_corridor=True)
        assert replace(s, polygon=_rect(0, 0, 5, 6)) \
            .synthesised_road_corridor is True


class TestProvenanceSurvivesAHostCut:
    """§T7's discriminator must survive a host cut: a synthesised
    corridor cut in two is still synthesis on both sides.  A remainder
    that lost the flag would read as AUTHORED pavement and become
    permanently invisible to the mask.

    The cut this class was written against was §T6.2's CLAIM footprint
    cut (``bridges._split_host_at_corridor``), retired with R14-1's claim
    class (RULINGS 2026-08-31b, redesign spec §5.1, census #25) — that
    twin is deleted.  The invariant it protected is carried by
    ``TestTheMaskIsPublishedOnce.test_the_synthesis_flag_rides_the_shape``,
    which pins the flag across ``dataclasses.replace`` — the mechanism
    EVERY clip in the codebase re-mints a piece through, the claim cut
    included."""

    def test_the_flag_is_the_discriminator_not_the_role(self):
        """Two groundside rings, same role, opposite provenance: only
        the synthesised one is suppressible."""
        synth = BuiltShape(polygon=_rect(0, -3, 20, 3),
                           role=ROLE_GROUNDSIDE_PAVEMENT,
                           ref="groundside",
                           synthesised_road_corridor=True)
        authored = BuiltShape(polygon=_rect(0, -3, 20, 3),
                              role=ROLE_GROUNDSIDE_PAVEMENT,
                              ref="groundside")
        assert synth.role == authored.role
        assert synth.synthesised_road_corridor
        assert not authored.synthesised_road_corridor


class TestCorridorSeniorityOverGroundsideLots:
    """Fable ruling 2026-08-28, from RULINGS 2026-08-15 "ROADS CARRY
    SPINES … AND SPINES PASS THROUGH PAVEMENT": one corridor is ONE
    CONTINUOUS LAW OBJECT and a lot may not sever it.

    Three cover classes, three verdicts — the ruling's own split:
      1. road-family cover  → dedupe, the clip is CORRECT (untouched);
      2. airside cover      → the crossing law owns the join (untouched);
      3. groundside non-road → THE FILL WINS, the LOT is cut back.
    """

    def _fill(self, x0, y0, x1, y1):
        return BuiltShape(polygon=_rect(x0, y0, x1, y1),
                          role=ROLE_SERVICE_JUNCTION, ref="service",
                          synthesised_road_corridor=True)

    def test_class_3_the_lot_is_cut_and_the_fill_survives(self):
        fill = self._fill(10, -3, 16, 3)
        lot = BuiltShape(polygon=_rect(0, -20, 40, 20),
                         role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside")
        lay = _layout([lot, fill])
        n = road_piece_ledger.cut_lots_back_from_corridors(lay, "ZZZZ")
        assert n == 1
        assert fill.polygon.area == pytest.approx(36.0), (
            "the corridor fill was cut — it is senior on this ground")
        assert lot.polygon.intersection(fill.polygon).area \
            == pytest.approx(0.0, abs=1e-6), (
            "the lot still overlaps the fill — the clip will delete it")
        assert lot.polygon.area < 40 * 40

    def test_class_1_a_road_family_cover_is_untouched(self):
        """Another corridor piece over the fill is a DEDUPE: the
        connection exists through the cover, so nothing is cut here."""
        fill = self._fill(10, -3, 16, 3)
        other = BuiltShape(polygon=_rect(0, -20, 40, 20),
                           role=ROLE_SERVICE_ROAD, ref="road",
                           synthesised_road_corridor=True)
        lay = _layout([other, fill])
        assert road_piece_ledger.cut_lots_back_from_corridors(
            lay, "ZZZZ") == 0
        assert other.polygon.area == pytest.approx(40 * 40)

    def test_class_2_airside_is_untouched(self):
        """A fill under apron pavement yields to the crossing law; this
        rule must not cut airside to save it."""
        from auto_patch.layout import ROLE_APRON
        fill = self._fill(10, -3, 16, 3)
        apron = BuiltShape(polygon=_rect(0, -20, 40, 20),
                           role=ROLE_APRON, ref="")
        lay = _layout([apron, fill])
        assert road_piece_ledger.cut_lots_back_from_corridors(
            lay, "ZZZZ") == 0
        assert apron.polygon.area == pytest.approx(40 * 40)

    def test_a_lot_that_IS_the_corridors_ground_is_left_alone(self):
        """Cutting a lot to nothing would delete a surface to save a
        fill; the clip decides that one, named."""
        fill = self._fill(-5, -25, 45, 25)
        lot = BuiltShape(polygon=_rect(0, -20, 40, 20),
                         role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside")
        lay = _layout([lot, fill])
        assert road_piece_ledger.cut_lots_back_from_corridors(
            lay, "ZZZZ") == 0
        assert lot.polygon.area == pytest.approx(40 * 40)

    def test_a_demoted_corridor_is_not_a_lot(self):
        """A groundside_pavement piece that IS a demoted corridor still
        carries the flag, so it is class 1, not class 3."""
        fill = self._fill(10, -3, 16, 3)
        demoted = BuiltShape(polygon=_rect(0, -20, 40, 20),
                             role=ROLE_GROUNDSIDE_PAVEMENT,
                             ref="groundside",
                             synthesised_road_corridor=True)
        lay = _layout([demoted, fill])
        assert road_piece_ledger.cut_lots_back_from_corridors(
            lay, "ZZZZ") == 0

    def test_off_restores_the_prior_seniority(self, monkeypatch):
        monkeypatch.setenv("O4_CORRIDOR_SENIORITY", "0")
        fill = self._fill(10, -3, 16, 3)
        lot = BuiltShape(polygon=_rect(0, -20, 40, 20),
                         role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside")
        lay = _layout([lot, fill])
        assert road_piece_ledger.cut_lots_back_from_corridors(
            lay, "ZZZZ") == 0
        assert lot.polygon.area == pytest.approx(40 * 40)


def test_rule3_refuses_to_sever_a_lot_rather_than_drop_half():
    """A corridor crossing a lot END TO END would leave two remainders;
    keeping the larger and dropping the other is the area-loss defect
    this round exists to stop, so the pre-pass declines and the named
    clip decides instead."""
    fill = BuiltShape(polygon=_rect(18, -30, 22, 30),
                      role=ROLE_SERVICE_JUNCTION, ref="service",
                      synthesised_road_corridor=True)
    lot = BuiltShape(polygon=_rect(0, -20, 40, 20),
                     role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside")
    lay = _layout([lot, fill])
    assert road_piece_ledger.cut_lots_back_from_corridors(lay, "ZZZZ") == 0
    assert lot.polygon.area == pytest.approx(40 * 40), (
        "the lot lost area to a cut that should have been refused")


def test_a_join_touches_but_never_overlaps():
    """CYXY, measured: keeping a piece on distance alone retained one
    OVERLAPPING a groundside lot by 0.38 m², and test_no_self_overlap
    (zero tolerance) went red against a green main.  A join shares an
    EDGE; shared AREA is a duplicate, and the clip was right to drop it."""
    survivors = [_rect(0, 0, 10, 6)]
    assert road_piece_ledger.joins_a_surviving_neighbour(
        _rect(10, 0, 12, 6), survivors), "an edge-sharing join was dropped"
    assert not road_piece_ledger.joins_a_surviving_neighbour(
        _rect(9, 0, 12, 6), survivors), (
        "an OVERLAPPING piece was kept as a join — the no-self-overlap "
        "invariant has zero tolerance")
    assert not road_piece_ledger.joins_a_surviving_neighbour(
        _rect(9, 0, 12, 6), survivors + [_rect(30, 30, 40, 36)])
