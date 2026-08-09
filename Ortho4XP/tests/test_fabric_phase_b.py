"""SUCCESSOR TWINS for THE FABRIC MODEL Phase B (W2 + W3).

Charter: ``docs/specs/fabric-phase-b-spec.md``; RULINGS 2026-08-08 (THE
FABRIC MODEL, the five reg-set rulings); ``docs/specs/
fabric-model-reg-set.md`` §5.1 (the retire table, T1…T8).

WHAT THIS FILE IS FOR.  W2 retires machinery and flips consumers, so the
twins that pinned the retired behaviour cannot simply be deleted — the
spec requires "twins proving the SUCCESSOR behaviour" for every retire.
The pre-W2 twins were kept where they were and PINNED to their flag-OFF
arm (which makes them per-flag identity proofs); this file asserts the
other arm — the default build.

Each test names the reg-set row or ruling it enforces, so a reader can
go from a failure to the authority in one hop.
"""

import pytest
from shapely.geometry import Polygon

from auto_patch import fabric_sparse as FS
from auto_patch import grade_law as GL
from auto_patch.elevation_per_surface.route_profile import solve as SOLVE
from auto_patch.layout import BuiltShape, PavementLayout


@pytest.fixture(autouse=True)
def _inert_between_tests():
    FS.disarm()
    yield
    FS.disarm()


def _layout(shapes, icao="TEST", anchor=(30.1089375, 31.434664815)):
    lay = PavementLayout(icao=icao, anchor=anchor)
    lay.shapes = list(shapes)
    return lay


def _rect(x0, y0, x1, y1, role="apron", stations=0):
    bottom = [(x0, y0)]
    for k in range(1, stations + 1):
        bottom.append((x0 + (x1 - x0) * k / (stations + 1), y0))
    ring = bottom + [(x1, y0), (x1, y1), (x0, y1)]
    return BuiltShape(polygon=Polygon(ring), role=role)


# ══════════════════════════════════════════════════════════════════════
# W2 · the emission switch — scope is now the whole airport
# ══════════════════════════════════════════════════════════════════════

def test_sparse_all_arms_every_pavement_and_pad_at_any_airport():
    """The Phase-A scope was two declared clusters at two named
    airports.  W2's scope is a ROLE test, so an airport with no cluster
    (SPJC) is now fully in scope — that IS the generalization."""
    apron = _rect(0.0, 0.0, 400.0, 200.0, role="apron", stations=9)
    junc = _rect(400.0, 0.0, 900.0, 60.0, role="junction", stations=9)
    pad = _rect(10.0, 300.0, 40.0, 330.0, role="building")
    rwy = _rect(0.0, -400.0, 3000.0, -340.0, role="runway")
    lay = _layout([apron, junc, pad, rwy], icao="SPJC")
    assert FS.arm(lay, "SPJC") == 3
    assert FS.mode() == "w2"
    for s in (apron, junc, pad):
        assert FS.is_sparse(s) is True
    # RUNWAY-FAMILY SURFACES ARE REG SET and stay out of the sparse
    # scope entirely (Annex-14 graded strip, RESA/OFZ).
    assert FS.is_sparse(rwy) is False


def test_sparse_all_off_falls_back_to_the_phase_a_cluster(monkeypatch):
    """The per-flag OFF arm: with W2 disabled and the Phase-A gate
    unset, nothing arms at all — the pre-W2 world."""
    monkeypatch.setenv("O4_FABRIC_W2_SPARSE_ALL", "0")
    monkeypatch.delenv("O4_FABRIC_SPARSE", raising=False)
    apron = _rect(0.0, 0.0, 400.0, 200.0, stations=9)
    lay = _layout([apron], icao="SPJC")
    assert FS.arm(lay, "SPJC") == 0
    assert FS.mode() is None
    assert FS.is_sparse(apron) is False


def test_the_predicate_split_keeps_reg_bands_and_retires_apron_bands():
    """THE design decision of W2, asserted directly (reg-set R6/R9 vs
    T2/T3).  Every live taxiway is a ``junction`` shape and junctions
    ARE sparse — but the taxiway graded strip is reg set, so band scope
    and emission density must be different questions."""
    apron = _rect(0.0, 0.0, 400.0, 200.0, role="apron")
    junc = _rect(400.0, 0.0, 900.0, 60.0, role="junction")
    rwy = _rect(0.0, -400.0, 3000.0, -340.0, role="runway")
    lay = _layout([apron, junc, rwy], icao="SPJC")
    FS.arm(lay, "SPJC")
    assert FS.is_sparse(junc) is True
    assert FS.bands_declined(junc) is False, "taxiway strip is REG SET"
    assert FS.bands_declined(rwy) is False, "runway strip is REG SET"
    assert FS.bands_declined(apron) is True, "reg-set T2/T3, ruling 4"


def test_apron_band_retirement_is_separately_disable_able(monkeypatch):
    monkeypatch.setenv("O4_FABRIC_W2_RETIRE_APRON_SURROUND", "0")
    apron = _rect(0.0, 0.0, 400.0, 200.0, role="apron")
    lay = _layout([apron], icao="SPJC")
    FS.arm(lay, "SPJC")
    assert FS.is_sparse(apron) is True
    assert FS.bands_declined(apron) is False


def test_generic_stationing_retires_everywhere_and_bisects_alone(
        monkeypatch):
    """reg-set T8.  The 60 m pass is declined on every sparse shape, and
    turning ITS flag off restores it without disturbing the rest of W2."""
    from auto_patch.conformance import densify_long_edges
    s = _rect(0.0, 0.0, 500.0, 100.0, role="apron")
    lay = _layout([s], icao="SPJC")
    FS.arm(lay, "SPJC")
    assert FS.stationing_declined(s) is True
    assert densify_long_edges(lay, {"apron"}, 60.0) == 0

    monkeypatch.setenv("O4_FABRIC_W2_RETIRE_STATIONING", "0")
    s2 = _rect(0.0, 0.0, 500.0, 100.0, role="apron")
    lay2 = _layout([s2], icao="SPJC")
    FS.arm(lay2, "SPJC")
    assert FS.is_sparse(s2) is True, "still sparse — only stationing moved"
    assert FS.stationing_declined(s2) is False
    assert densify_long_edges(lay2, {"apron"}, 60.0) > 0


def test_ring_thinning_reaches_every_apron_not_just_a_cluster():
    """The Phase-A mechanics, verbatim, at airport scope: collinear
    generic stationing goes, the four corners stay."""
    apron = _rect(0.0, 0.0, 600.0, 300.0, role="apron", stations=19)
    lay = _layout([apron], icao="SPJC")
    FS.arm(lay, "SPJC")
    before = len(apron.polygon.exterior.coords)
    removed = FS.thin_rings(lay, "SPJC")
    assert removed > 0
    assert len(apron.polygon.exterior.coords) == before - removed
    assert FS.report()["thin"]["shapes_thinned"] == 1


# ══════════════════════════════════════════════════════════════════════
# W2 · fan zones RETIRE OUTRIGHT (reg-set T1, RULINGS scope answer 1)
# ══════════════════════════════════════════════════════════════════════

def test_fan_split_refuses_at_its_own_entry():
    """OUTRIGHT means a caller holding a plan of its own cannot re-open
    the family either."""
    from auto_patch.elevation_per_surface.route_profile import (
        apron_terrace as AT)
    plan = AT.FanRampPlan()
    plan.zones.append(object())          # non-empty: the early-out above
    lay = _layout([_rect(0.0, 0.0, 400.0, 200.0)], icao="SPJC")
    assert AT.split_aprons_at_fan_zones(lay, plan, icao="SPJC") == 0


def test_fan_retirement_is_separately_disable_able(monkeypatch):
    monkeypatch.setenv("O4_FABRIC_W2_RETIRE_FANS", "0")
    from auto_patch.fabric_flags import on as flag_on
    assert flag_on("O4_FABRIC_W2_RETIRE_FANS") is False


# ══════════════════════════════════════════════════════════════════════
# W2 · the law retires (reg-set T2/T3 · T4 · T5)
# ══════════════════════════════════════════════════════════════════════

def test_apron_surround_is_the_drape_under_icao():
    """Ruling 4 + F-3: ICAO governs NOTHING beyond an apron edge and
    states no taxiway/apron lip, so the corridor is zone-3 from the
    edge — floor free (a cliff is lawful), ceiling rising at the
    ungraded cap.  That is the drape, in the law function."""
    up = GL.get_ruleset("icao").ungraded_strip_max_up_slope
    for d in (0.5, 3.0, 12.0):
        floor, ceiling = GL.adjacent_ground_envelope(
            "apron", None, None, d, "icao")
        assert floor is None
        assert ceiling == pytest.approx(up * d)


def test_apron_edge_keeps_the_faa_item_4_lip():
    """reg-set §5.1's closing paragraph — "retiring the apron SHOULDER
    BAND is not the same act as retiring the apron EDGE".  ¶4.14.2 item
    4 is written for any unpaved surface adjacent to a paved one."""
    floor, ceiling = GL.adjacent_ground_envelope(
        "apron", None, None, 2.0, "faa")
    assert floor == pytest.approx(-0.055 * 2.0)
    assert ceiling == pytest.approx(-0.045 * 2.0)
    # …and beyond the 3 m lip the drape takes over: floor free.
    beyond_floor, _ = GL.adjacent_ground_envelope(
        "apron", None, None, 8.0, "faa")
    assert beyond_floor is None


def test_the_apron_shoulder_band_is_gone_on_both_rulesets():
    """T2/T3: the 1-3 % 3 m shoulder no longer bounds anything.  Its
    signature was a ceiling of exactly -0.01·d inside 3 m."""
    for key in ("faa", "icao"):
        _floor, ceiling = GL.adjacent_ground_envelope(
            "apron", None, None, 2.0, key)
        assert ceiling != pytest.approx(-0.01 * 2.0)


def test_service_road_shadow_is_ungoverned():
    """T5 — STANDARDS.md: "design choice, NOT an AASHTO mandate"."""
    for key in ("faa", "icao"):
        for d in (0.5, 6.0, 14.0, 100.0):
            assert GL.adjacent_ground_envelope(
                "service_road", None, None, d, key) == (None, None)
            assert GL.adjacent_ground_envelope(
                "service_junction", None, None, d, key) == (None, None)


def test_apron_edge_walls_refuse_inside_the_emitter():
    """T4 — refused in ``_emit_apron_walls`` itself, returning the
    emitter's own "nothing emitted" pair so caller arithmetic holds."""
    from auto_patch import adjacent_ground as AG
    out = AG._emit_apron_walls(
        _layout([]), [(0.0, 0.0), (5.0, 0.0)], [100.0, 100.0],
        [(0.0, 1.0), (0.0, 1.0)], lambda d: -0.03, 5.0,
        lambda x, y: 80.0, None, None)
    assert out == (0, None)


# ══════════════════════════════════════════════════════════════════════
# W2 · the flips (config.RULESET_W2_FLIPS)
# ══════════════════════════════════════════════════════════════════════

def test_icao_graded_strip_has_no_mandatory_fall_and_faa_is_unmoved():
    """Reg-set ruling 1 (PROVISIONAL).  ICAO's band ceiling stops
    descending past the lip; the FAA form is untouched, which is why
    KCLT is expected not to move on this flag."""
    icao_lip = GL.adjacent_ground_envelope("runway", 4, "E", 3.0, "icao")[1]
    for d in (10.0, 40.0, 74.0):
        assert GL.adjacent_ground_envelope("runway", 4, "E", d, "icao")[1] \
            == pytest.approx(icao_lip)
    faa = GL.adjacent_ground_envelope("runway", 4, "E", 40.0, "faa")[1]
    assert faa < icao_lip, "the FAA mandatory fall still accumulates"


def test_the_flip_ledger_is_complete_and_registered():
    from auto_patch import config as CFG
    from auto_patch import fabric_flags as FF
    assert len(CFG.RULESET_W2_FLIPS) == 3
    for _family, live, authority, key, flag in CFG.RULESET_W2_FLIPS:
        rs = CFG.get_ruleset(key)
        assert getattr(rs, live) != getattr(rs, authority)
        assert flag in FF.FLAG_INDEX


# ══════════════════════════════════════════════════════════════════════
# W3 · the seeder record (fabric-phase-b-spec.md W3)
# ══════════════════════════════════════════════════════════════════════

def test_every_hard_node_is_claimed_by_a_named_site():
    """Instrument truth: the classifier assigns a class to EVERY node in
    the hard set, and the residue class exists to be counted at zero."""
    cat = SOLVE.classify_projection_hard(
        {1, 2, 3, 4, 5, 6, 7, 8},
        seed_hard={7}, runway_nodes={1}, strip_freeze={4},
        runway_boundary={2}, runway_anchor={3}, seam_pins={5},
        string_pins={8}, feature_weld={6: "graded_strip"})
    assert set(cat) == {1, 2, 3, 4, 5, 6, 7, 8}
    assert SOLVE.PROJECTION_HARD_UNCLAIMED not in set(cat.values())
    assert cat[6] == "weld:graded_strip"


def test_an_unclaimed_node_is_named_not_folded():
    """The defect this record abolishes is an ANONYMOUS freeze, so a
    node no site claims must be visible rather than absorbed into a
    neighbouring class (the ``seed_rwy_seam`` blanket's cost)."""
    cat = SOLVE.classify_projection_hard(
        {42}, seed_hard=set(), runway_nodes=set(), strip_freeze=set(),
        runway_boundary=set(), runway_anchor=set(), seam_pins=set(),
        feature_weld={})
    assert cat == {42: SOLVE.PROJECTION_HARD_UNCLAIMED}


def test_precedence_is_most_specific_first():
    """A node several sites could claim takes the most specific one, so
    the census cannot double-count and the class sizes stay meaningful."""
    cat = SOLVE.classify_projection_hard(
        {1}, seed_hard={1}, runway_nodes={1}, strip_freeze={1},
        runway_boundary={1}, runway_anchor={1}, seam_pins={1},
        feature_weld={1: "graded_strip"})
    assert cat[1] == "rwy_profile"


def test_the_weld_class_carries_the_feature_family():
    """THE CONVERGENCE LEVER.  The pin attribution measured
    ``graded_strip`` at 93/96/90/89 % of the late freeze; a blanket
    "feature_weld" label could not have shown that, and could not show
    the class emptying when W2 retires the geometry."""
    welds = {1: "graded_strip", 2: "graded_strip", 3: "boundary"}
    cat = SOLVE.classify_projection_hard(
        {1, 2, 3}, seed_hard=set(), runway_nodes=set(), strip_freeze=set(),
        runway_boundary=set(), runway_anchor=set(), seam_pins=set(),
        feature_weld=welds)
    census: dict = {}
    for c in cat.values():
        census[c] = census.get(c, 0) + 1
    assert census == {"weld:graded_strip": 2, "weld:boundary": 1}
    # …and with that family retired, the class is simply not there.
    gone = SOLVE.classify_projection_hard(
        {3}, seed_hard=set(), runway_nodes=set(), strip_freeze=set(),
        runway_boundary=set(), runway_anchor=set(), seam_pins=set(),
        feature_weld={3: "boundary"})
    assert "weld:graded_strip" not in set(gone.values())


def test_the_record_is_a_pure_instrument():
    """W3 changes no bound and writes no value: the classifier only
    reads.  This is what makes its flag a bisector of COST, not of
    geometry — and it is why the W2 arms and the W3 arms compose."""
    hard = {1, 2}
    seed = {1, 2}
    SOLVE.classify_projection_hard(
        hard, seed_hard=seed, runway_nodes=set(), strip_freeze=set(),
        runway_boundary=set(), runway_anchor=set(), seam_pins=set(),
        feature_weld={})
    assert hard == {1, 2}
    assert seed == {1, 2}


def test_apron_terraces_retire_and_bisect_alone(monkeypatch):
    """The walls-to-carves ruling reaches the apron terrace: a terrace is
    a cut line plus a wall face on unregulated ground.  Its flag must
    also bisect ALONE — under W2 every apron is sparse, so a hook that
    consulted ``is_sparse`` would be un-disable-able."""
    apron = _rect(0.0, 0.0, 400.0, 200.0, role="apron")
    lay = _layout([apron], icao="SPJC")
    FS.arm(lay, "SPJC")
    assert FS.terraces_declined(apron) is True

    monkeypatch.setenv("O4_FABRIC_W2_RETIRE_APRON_TERRACES", "0")
    assert FS.is_sparse(apron) is True, "still sparse — only terraces moved"
    assert FS.terraces_declined(apron) is False


def test_every_w2_hook_predicate_bisects_independently(monkeypatch):
    """The registry's promise, asserted on the predicates themselves:
    turning ONE flag off restores ONE behaviour and leaves the rest of
    W2 in place."""
    apron = _rect(0.0, 0.0, 400.0, 200.0, role="apron")
    lay = _layout([apron], icao="SPJC")
    FS.arm(lay, "SPJC")
    assert (FS.bands_declined(apron), FS.terraces_declined(apron),
            FS.stationing_declined(apron)) == (True, True, True)
    for env, probe in (
            ("O4_FABRIC_W2_RETIRE_APRON_SURROUND", FS.bands_declined),
            ("O4_FABRIC_W2_RETIRE_APRON_TERRACES", FS.terraces_declined),
            ("O4_FABRIC_W2_RETIRE_STATIONING", FS.stationing_declined)):
        monkeypatch.setenv(env, "0")
        assert probe(apron) is False, env
        monkeypatch.delenv(env)
        assert probe(apron) is True, env


def test_phase_a_only_is_false_in_the_w2_world():
    """``phase_a_only`` is what the Phase-A-owned hooks consult, and it
    must be dark under W2 or those hooks stop being bisectable."""
    apron = _rect(0.0, 0.0, 400.0, 200.0, role="apron")
    lay = _layout([apron], icao="SPJC")
    FS.arm(lay, "SPJC")
    assert FS.mode() == "w2"
    assert FS.is_sparse(apron) is True
    assert FS.phase_a_only(apron) is False
