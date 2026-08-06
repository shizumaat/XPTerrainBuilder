"""CALIBRATION TWINS for the band / groundside-seat REPORTS.

RULINGS 2026-08-06, "Instrument truth is law" — the standing-instrument
sweep, lane VII.  Binding point 1: *a KNOWN-ANSWER TWIN, or it is not an
instrument*.  These are the twins the three report surfaces did not have:

  * the band-inversion HEADLINE and its ANCHOR-PAIR ROLLUP
    (``building_feasibility.assert_no_final_band_inversion``) — every
    number in the message was unasserted; only the LAW/RIDE and
    CIFP halves below them were twinned
    (``tests/test_final_band_inversion.py``);
  * the ``[reach-band] NO FIELD`` line — a catch-all bucket labelled with
    three candidate causes, with an ``except Exception`` swallowing
    everything on top;
  * the band-EXCESS membership line's POPULATION — measured live at HEAZ,
    where the band field cannot be built at all, every vertex reads
    off-net, and the line still rendered "every airside vertex INSIDE its
    band" directly beneath the ``no field could be built`` line.  Zero of
    zero is not a pass;
  * ``groundside.report_groundside_law_seat`` and its cross-pass
    aggregation — ZERO tests existed for the printer, only for the
    accumulator one level down.

Every assertion below is a NUMBER whose value is hand-derivable from the
fixture, or the ABSENCE of a sentence the report is no longer allowed to
print.  "The function runs" is not an assertion.
"""
import pytest

from auto_patch.elevation_per_surface.building_feasibility import (
    BandInversionError, FINAL_BAND_INVERSION_TOL_M, BAND_NODE_SPACE,
    assert_no_final_band_inversion, instrument_frame, instrument_tree_sha,
    reach_band_unified, spine_value_fields)


# ═════════════════════════════════════════════════════════════════════════
# Shared fixtures — the same two-anchor case tests/test_final_band_
# inversion.py uses, so the two files cannot describe different geometry.
# ═════════════════════════════════════════════════════════════════════════
class _FakeG:
    def __init__(self, anchors, adj, pos):
        self.runway_anchor = anchors
        self.spine_adj = adj
        self.pos = pos
        self.service_spine_pairs = set()


class _FakeLayout:
    pass


def _two_anchor_case(budget_a=4.0, budget_b=4.0):
    """Node 2 between anchors 0 (100 m) and 1 (110 m).  With 4 m of budget
    each way the ceiling at node 2 is 104 and the floor is 106 — inverted
    by exactly 2.0 m, and the two anchors are inverted through each other
    by 10 − 8 = 2.0 m as well.  Three nodes, three rows."""
    anchors = {0: 100.0, 1: 110.0}
    adj = {0: [(2, budget_a)], 1: [(2, budget_b)],
           2: [(0, budget_a), (1, budget_b)]}
    pos = {0: (0.0, 0.0), 1: (100.0, 0.0), 2: (50.0, 0.0)}
    return _FakeLayout(), _FakeG(anchors, adj, pos)


def _message(layout, icao="TEST"):
    return str(pytest.raises(
        BandInversionError,
        assert_no_final_band_inversion, layout, icao).value)


# ═════════════════════════════════════════════════════════════════════════
# 1 — THE HEADLINE (building_feasibility ~:1093-1101)
# ═════════════════════════════════════════════════════════════════════════
def test_the_headline_counts_are_a_known_answer():
    """3 of 3.  The fixture has exactly three nodes and all three are
    inverted (each anchor is out of the OTHER anchor's band, and the
    middle node is out of both) — so the headline's "N node(s) of M" is
    fully determined, and the denominator is the BAND-COVERED node count,
    not the layout's vertex count."""
    layout, G = _two_anchor_case()
    spine_value_fields(layout, G)
    assert layout._final_band_node_count == 3
    message = _message(layout)
    assert "TEST: the FINAL reach band is INVERTED at 3 node(s) of 3 " \
           "band-covered node(s)" in message
    assert f"(floor − ceiling > {FINAL_BAND_INVERSION_TOL_M:g} m)" in message
    # the law layer's own verdict stays — it is the LAW raising, which
    # binding point 2 licenses (and the reason this line is a "keep").
    assert "never a region to quarantine" in message


def test_the_headline_carries_a_frame_stamp():
    """Binding point 3.  ``_final_band_node_count`` is a NODE-SPACE
    quantity and the per-node ids below it resolve in exactly one space;
    both were printed bare while the CONSUMER
    (``tools/trace_reach_route.py``) carried the whole hazard in its own
    docstring."""
    layout, G = _two_anchor_case()
    spine_value_fields(layout, G)
    message = _message(layout)
    assert "[frame tree=" in message
    assert f"tree={instrument_tree_sha()}" in message
    assert "world=" in message and "crown_keys=0" in message
    assert BAND_NODE_SPACE in message
    # …and the per-node block says which space its bare ids are in.
    assert "node ids: " + BAND_NODE_SPACE in message
    assert "layout-local metres about layout.anchor" in message


def test_the_frame_stamp_names_the_dem_world_when_the_build_stamped_it():
    """The world is READ from what the build recorded, never re-derived —
    a second reading of the DEM would be a second instrument.  Absent, it
    stamps ``?`` rather than guessing (the ``provenance`` rule: an absent
    facet is stamped explicitly)."""
    layout, G = _two_anchor_case()
    assert "world=?" in instrument_frame(layout, "n/a")
    layout._dem_world_label = "ConstantDEM:<constant-dem 10000 m>"
    assert ("world=ConstantDEM:<constant-dem 10000 m>"
            in instrument_frame(layout, "n/a"))


def test_the_crown_stamp_is_a_count_not_an_adjective():
    layout, G = _two_anchor_case()
    assert "crown_keys=0" in instrument_frame(layout, "n/a")
    layout._crown_drop_key = {(0, 0): 0.1, (1, 1): 0.2}
    assert "crown_keys=2" in instrument_frame(layout, "n/a")


# ═════════════════════════════════════════════════════════════════════════
# 2 — THE ANCHOR-PAIR ROLLUP (building_feasibility ~:1120-1133)
# ═════════════════════════════════════════════════════════════════════════
def test_the_anchor_pair_rollup_is_a_known_answer():
    """ONE pair, hand-derived end to end.

    The floor field at node 2 is seeded from anchor 1 (110 m) and costs
    4 m; the ceiling from anchor 0 (100 m) at 4 m.  So the rollup's single
    pair is (floor anchor 1, ceiling anchor 0), its value spread is
    |110 − 100| = 10.000 m, its route budget is 4.00 + 4.00 = 8.000 m and
    the worst shortfall over that pair is 110 − 4 − (100 + 4) = 2.0000 m.
    Three nodes carry it."""
    layout, G = _two_anchor_case()
    spine_value_fields(layout, G)
    message = _message(layout)
    assert "contradictory ANCHOR PAIR(S): 1" in message
    assert ("anchors 1 (110.000 m) vs 0 (100.000 m): value spread "
            "10.000 m over a route budget of 8.000 m ⇒ shortfall "
            "2.0000 m at 3 node(s)") in message


def test_the_rollup_prices_each_pair_on_its_own_budget():
    """Asymmetric budgets: 1 m one way, 7 m the other.  The budget is the
    SUM (8.000 m, unchanged) but the two route legs are different numbers,
    and each per-node row must carry its own — a shared number here is the
    two-instruments trap in miniature."""
    layout, G = _two_anchor_case(1.0, 7.0)
    spine_value_fields(layout, G)
    message = _message(layout)
    assert "over a route budget of 8.000 m" in message
    assert "route: floor 7.00 m of budget, ceiling 1.00 m" in message


def test_no_rollup_line_when_no_pair_is_recorded():
    """A build whose rows carry no anchor provenance prints no pair block
    at all rather than an empty one labelled zero."""
    layout, G = _two_anchor_case()
    spine_value_fields(layout, G)
    for row in layout._final_band_inversions:
        row["floor_anchor"] = None
        row["ceil_anchor"] = None
    message = _message(layout)
    assert "ANCHOR PAIR" not in message
    assert "node 2" in message


# ═════════════════════════════════════════════════════════════════════════
# 3 — THE [reach-band] NO FIELD LINE (building_feasibility ~:1278-1280)
#
# The line that stood here — "no field could be built (no anchors / no
# pavement / grid over cap)" — named three candidate causes and
# distinguished none of them, while the ``except Exception`` above it
# swallowed every other one.  RULINGS 2026-08-06 binding point 2's named
# defect pattern, and live on HEAZ on every build.
# ═════════════════════════════════════════════════════════════════════════
def _capture_reach_band(monkeypatch, builder, layout, G):
    import O4_UI_Utils as UI
    from auto_patch.elevation_per_surface import raster_reach_band as RRB
    said = []
    monkeypatch.setattr(RRB, "build_raster_reach_band", builder)
    monkeypatch.setattr(UI, "vprint",
                        lambda level, *a: said.append(" ".join(str(x)
                                                              for x in a)))
    band = reach_band_unified(layout, G)
    return band, "\n".join(said)


def test_a_RAISING_band_builder_is_named_as_such(monkeypatch):
    """DEFECT half.  The builder raising and the builder answering "no
    band" have opposite dispositions and used to render identically."""
    def _boom(_layout, _G):
        raise ValueError("scipy went missing")

    layout, G = _two_anchor_case()
    band, said = _capture_reach_band(monkeypatch, _boom, layout, G)
    assert band(0.0, 0.0) is None, "behaviour is unchanged: still off-net"
    assert "the band BUILDER RAISED ValueError: scipy went missing" in said
    assert "no anchors / no pavement / grid over cap" not in said, (
        "the catch-all bucket must be gone")


def test_a_returned_None_names_the_falsified_precondition(monkeypatch):
    """LEGITIMATE half.  An empty graph falsifies three of the builder's
    documented graph-side preconditions, and the line names exactly those
    three — with the counts that make them checkable."""
    layout = _FakeLayout()
    G = _FakeG({}, {}, {})
    band, said = _capture_reach_band(
        monkeypatch, lambda _l, _g: None, layout, G)
    assert band(0.0, 0.0) is None
    assert "the builder RETURNED None; failing precondition(s):" in said
    assert "G.pos is empty (no node positions)" in said
    assert "G.runway_anchor is empty (no runway anchor to seed from)" in said
    assert "G.spine_adj is empty (no spine adjacency)" in said
    assert "G: nodes=0, runway anchors=0, spine-adjacent nodes=0" in said
    assert "BUILDER RAISED" not in said


def test_a_returned_None_with_every_graph_precondition_MET_says_so(
        monkeypatch):
    """The honest third case: nothing this frame can observe is wrong, so
    the report says the remaining preconditions are inside the builder
    instead of picking one of them.  Known answer: the fixture's graph
    carries 3 nodes, 2 runway anchors and 3 spine-adjacent nodes."""
    layout, G = _two_anchor_case()
    band, said = _capture_reach_band(
        monkeypatch, lambda _l, _g: None, layout, G)
    assert band(0.0, 0.0) is None
    assert "no graph-side precondition is falsified" in said
    assert "G: nodes=3, runway anchors=2, spine-adjacent nodes=3" in said
    assert "RASTER_REACH_BAND_MAX_CELLS" in said
    assert "failing precondition(s):" not in said


def test_the_no_field_line_says_the_measured_population_is_zero(monkeypatch):
    """The HEAZ coupling, stated at the source: with no field EVERY query
    reads off-net, so every band-scoped instrument downstream examines
    zero vertices.  Saying so here is what stops the next reader taking
    the membership line's clean pass at face value."""
    layout, G = _two_anchor_case()
    _band, said = _capture_reach_band(
        monkeypatch, lambda _l, _g: None, layout, G)
    assert "examines ZERO vertices this build" in said
    assert "[frame tree=" in said


# ═════════════════════════════════════════════════════════════════════════
# 4 — BAND MEMBERSHIP: THE POPULATION (grade_graph_validate ~:924-935)
# ═════════════════════════════════════════════════════════════════════════
def _excess_layout(band_values, roles=("junction",)):
    """A one-shape layout whose vertices are placed at the given
    ``(x, y) -> (elev, lo, hi) | (elev, None)`` table.  A 2-tuple ⇒ the
    band field has no answer there (off-net)."""
    from shapely.geometry import Polygon

    class _Shape:
        def __init__(self, role, poly, elevs):
            self.role = role
            self.polygon = poly
            self.node_altitudes = list(elevs)
            self.altitude = None
            self.altitude_high = None
            self.altitude_low = None

    pts = [xy for xy in band_values]
    poly = Polygon(pts + [pts[0]])
    elevs = [band_values[xy][0] for xy in pts]
    layout = _FakeLayout()
    layout.shapes = [_Shape(roles[0], poly, elevs)]

    def _band(x, y):
        entry = band_values.get((round(x, 6), round(y, 6)))
        if entry is None or len(entry) < 3:
            return None
        return (entry[1], entry[2])

    return layout, _band


def _report(monkeypatch, layout, band, **kw):
    from auto_patch.elevation_per_surface import building_feasibility as BF
    from auto_patch import grade_graph_validate as GGV
    monkeypatch.setattr(BF, "reach_band_unified", lambda _l, _g: band)
    return GGV.final_band_excess_report(layout, "TEST", G=object(), **kw)


def test_a_band_less_build_reports_NOT_MEASURED_not_a_clean_pass(monkeypatch):
    """★ THE HEAZ REGRESSION LOCK.  Every vertex off-net ⇒ examined = 0.
    The line must say NOT MEASURED and must NOT contain the universal
    claim, which is what shipped under HEAZ's own ``[reach-band] NO
    FIELD`` line."""
    from auto_patch import grade_graph_validate as GGV
    layout, _ = _excess_layout({(0.0, 0.0): (10.0, 0.0, 0.0),
                                (30.0, 0.0): (10.0, 0.0, 0.0),
                                (30.0, 30.0): (10.0, 0.0, 0.0)})
    rep = _report(monkeypatch, layout, lambda x, y: None)
    assert rep["examined"] == 0
    assert rep["off_net"] == 3
    assert rep["candidates"] == 3
    assert rep["rows"] == 0 and rep["material"] == 0
    line = GGV.format_final_band_excess(rep, "TEST")
    assert "NOT MEASURED" in line
    assert "ZERO vertices were examined" in line
    assert "INSIDE its band" not in line, (
        "zero-of-zero is not a pass — this is the exact sentence HEAZ "
        "shipped one line under 'no field could be built'")
    assert "off-net (band None — NOT constrained here)" in line


def test_a_clean_build_reports_the_size_of_its_own_population(monkeypatch):
    """The other side: 3 examined, 3 in band, 0 material.  The verdict is
    quantified by the population it is about."""
    from auto_patch import grade_graph_validate as GGV
    layout, band = _excess_layout({(0.0, 0.0): (10.0, 9.0, 11.0),
                                   (30.0, 0.0): (10.0, 9.0, 11.0),
                                   (30.0, 30.0): (10.0, 9.0, 11.0)})
    rep = _report(monkeypatch, layout, band)
    assert rep["examined"] == 3 and rep["in_band"] == 3
    assert rep["off_net"] == 0 and rep["material"] == 0
    line = GGV.format_final_band_excess(rep, "TEST")
    assert "0 of 3 EXAMINED vertex(es) outside their band" in line
    assert "examined 3 of 3 airside ring vertex(es)" in line
    assert "NOT MEASURED" not in line


def test_a_partly_off_net_build_reports_BOTH_numbers(monkeypatch):
    """The case the old line could not express at all: two vertices
    measured and in band, one never measured.  "Every airside vertex
    INSIDE its band" was false about the third and the report had no way
    to say so."""
    from auto_patch import grade_graph_validate as GGV
    layout, band = _excess_layout({(0.0, 0.0): (10.0, 9.0, 11.0),
                                   (30.0, 0.0): (10.0, 9.0, 11.0),
                                   (30.0, 30.0): (10.0,)})
    rep = _report(monkeypatch, layout, band)
    assert rep["examined"] == 2 and rep["off_net"] == 1
    assert rep["candidates"] == rep["examined"] + rep["off_net"] \
        + rep["deduped"], "the population must account for every candidate"
    line = GGV.format_final_band_excess(rep, "TEST")
    assert "0 of 2 EXAMINED vertex(es)" in line
    assert "1 off-net" in line


def test_the_material_line_quantifies_its_denominator(monkeypatch):
    """1 of 3, worst 0.53 m — one vertex at 11.53 m against a ceiling
    of 11.00 m.  The reported ``excess_m`` is the RAW ``e - hi``; the
    0.03 m rounding noise only decides whether the row exists at all."""
    from auto_patch import grade_graph_validate as GGV
    layout, band = _excess_layout({(0.0, 0.0): (10.0, 9.0, 11.0),
                                   (30.0, 0.0): (10.0, 9.0, 11.0),
                                   (30.0, 30.0): (11.53, 9.0, 11.0)})
    rep = _report(monkeypatch, layout, band)
    assert rep["examined"] == 3 and rep["material"] == 1
    assert rep["worst_m"] == pytest.approx(0.53, abs=1e-6)
    line = GGV.format_final_band_excess(rep, "TEST")
    assert "1 of 3 EXAMINED vertex(es) OUTSIDE their band" in line
    # the KEEP: the line names the law layer instead of adjudicating.
    assert ("REPORT, not a gate — the census and "
            "tests/test_route_band.py adjudicate.") in line


def test_both_floors_are_stamped_and_the_inert_split_says_it_is_inert(
        monkeypatch):
    """Binding point 3 on the band-excess line.  ``materiality_m`` was
    stamped; ``ELEV_ROUNDING_NOISE_M`` — the floor that actually decides
    which vertices become rows — was not, and ``sub_materiality`` was
    printed with no hint that it is zero BY CONSTRUCTION.  Known answer:
    0.03 > 0.01, so the flag is True on the shipped constants."""
    from auto_patch.config import ELEV_ROUNDING_NOISE_M
    from auto_patch import grade_graph_validate as GGV
    layout, band = _excess_layout({(0.0, 0.0): (10.0, 9.0, 11.0),
                                   (30.0, 0.0): (10.0, 9.0, 11.0),
                                   (30.0, 30.0): (10.0, 9.0, 11.0)})
    rep = _report(monkeypatch, layout, band)
    assert rep["noise_floor_m"] == pytest.approx(ELEV_ROUNDING_NOISE_M)
    assert rep["materiality_m"] == pytest.approx(
        GGV.FINAL_BAND_EXCESS_MATERIALITY_M)
    assert ELEV_ROUNDING_NOISE_M > GGV.FINAL_BAND_EXCESS_MATERIALITY_M
    assert rep["sub_materiality_structurally_zero"] is True
    line = GGV.format_final_band_excess(rep, "TEST")
    assert "floors: materiality 0.01 m, checker rounding noise 0.03 m" in line
    assert "STRUCTURALLY ZERO at these constants" in line
    assert "not evidence about the surface" in line


def test_the_structurally_zero_flag_FLIPS_when_the_floor_is_raised(
        monkeypatch):
    """Non-vacuity: the flag is a computation over the two constants, not
    a hard-coded True.  Ask for a 0.6 m floor — above the checker's noise
    — and the split becomes live again."""
    from auto_patch import grade_graph_validate as GGV
    layout, band = _excess_layout({(0.0, 0.0): (10.0, 9.0, 11.0),
                                   (30.0, 0.0): (10.0, 9.0, 11.0),
                                   (30.0, 30.0): (11.53, 9.0, 11.0)})
    rep = _report(monkeypatch, layout, band, tol=0.6)
    assert rep["sub_materiality_structurally_zero"] is False
    assert rep["material"] == 0 and rep["sub_materiality"] == 1
    line = GGV.format_final_band_excess(rep, "TEST")
    assert "1 sub-materiality row(s)." in line
    assert "STRUCTURALLY ZERO" not in line


def test_the_membership_line_carries_a_frame_stamp(monkeypatch):
    from auto_patch import grade_graph_validate as GGV
    layout, band = _excess_layout({(0.0, 0.0): (10.0, 9.0, 11.0),
                                   (30.0, 0.0): (10.0, 9.0, 11.0),
                                   (30.0, 30.0): (10.0, 9.0, 11.0)})
    layout._dem_world_label = "ConstantDEM:<constant-dem -500 m>"
    rep = _report(monkeypatch, layout, band)
    line = GGV.format_final_band_excess(rep, "TEST")
    assert f"tree={instrument_tree_sha()}" in line
    assert "world=ConstantDEM:<constant-dem -500 m>" in line
    assert "positional (x,y) rounded to 0.01 m" in line
    assert "NOT solver node ids" in line, (
        "this checker never touches a solver node id; equating its "
        "coordinates with the inversion rows' node ids is the two-"
        "instruments trap by construction")


def test_the_population_counters_do_not_move_the_verdict(monkeypatch):
    """SURFACE / VERDICT NEUTRALITY.  ``stats`` is a pure out-parameter:
    the rows the checker returns with and without it must be identical."""
    from auto_patch.elevation_per_surface import building_feasibility as BF
    from auto_patch import grade_graph_validate as GGV
    table = {(0.0, 0.0): (10.0, 9.0, 11.0),
             (30.0, 0.0): (13.0, 9.0, 11.0),
             (30.0, 30.0): (10.0, 9.0, 11.0)}
    layout, band = _excess_layout(table)
    monkeypatch.setattr(BF, "reach_band_unified", lambda _l, _g: band)
    bare = GGV.route_band_violations(layout, G=object())
    stats = {}
    withstats = GGV.route_band_violations(layout, G=object(), stats=stats)
    assert bare == withstats
    assert stats["examined"] == 3 and stats["in_band"] == 2
    assert len(bare) == 1


# ═════════════════════════════════════════════════════════════════════════
# 5 — THE PIPELINE PASS-WITH-RESIDUAL LINE (pipeline ~:6506-6508)
#
# The tolerance was HARD-CODED in the message text ("≤ 0.01 m") while the
# value came from ``FINAL_BAND_INVERSION_TOL_M`` — a literal free to drift
# from the constant it claims to report.  This is the drift lock.
# ═════════════════════════════════════════════════════════════════════════
def test_the_residual_line_interpolates_the_constant_it_reports():
    import inspect
    from auto_patch import pipeline as P
    src = inspect.getsource(P)
    marker = "sub-materiality inversion(s) "
    assert marker in src
    tail = src[src.index(marker):src.index(marker) + 400]
    assert "_band_tol" in tail, (
        "the tolerance must be interpolated from "
        "FINAL_BAND_INVERSION_TOL_M, never spelled in the message")
    assert "≤ 0.01 m" not in tail, "the literal is back"
    # the verdict itself is LICENSED and must stay: the law layer
    # RETURNED rather than raised, so PASS-with-residual is the law's
    # word, not the report's.
    assert "PASS-with-residual" in tail


def test_the_residual_count_the_line_reports_is_a_known_answer():
    """Half the floor, three nodes: the assertion returns 3 and raises
    nothing, which is what makes the line print at all."""
    deficit = 0.5 * FINAL_BAND_INVERSION_TOL_M
    half = 5.0 - 0.5 * deficit
    layout, G = _two_anchor_case(half, half)
    spine_value_fields(layout, G)
    assert assert_no_final_band_inversion(layout, "TEST") == 3


# ═════════════════════════════════════════════════════════════════════════
# 6 — THE [groundside-law-seat] INSTRUMENT (groundside ~:710-739)
#
# ZERO tests existed for the printer, the cross-pass aggregation or the
# re-seat line; only the accumulator one level down was twinned.
# ═════════════════════════════════════════════════════════════════════════
def _seat_book(layout, **passes):
    layout._gs_law_seat = {name: dict(st, where=name)
                           for name, st in passes.items()}
    return layout


def _say(monkeypatch):
    import O4_UI_Utils as UI
    said = []
    monkeypatch.setattr(UI, "vprint",
                        lambda level, *a: said.append(" ".join(str(x)
                                                              for x in a)))
    return said


def test_the_seat_printer_totals_ACROSS_PASSES(monkeypatch):
    """KNOWN ANSWER: two passes, 3+4 rings, 2+5 anchors, 1+0 from prior,
    6+9 interpolated, 1+2 islands over 7+11 vertices.  The totalling loop
    (~:724-726) had no test at all."""
    from auto_patch.groundside import report_groundside_law_seat
    layout = _seat_book(
        _FakeLayout(),
        emit_groundside_pavement_dem={
            "rings": 3, "anchored": 2, "from_prior": 1, "interpolated": 6,
            "islands": 1, "island_vertices": 7,
            "island_xy": [(10.0, 20.0)]},
        merge_touching_groundside={
            "rings": 4, "anchored": 5, "from_prior": 0, "interpolated": 9,
            "islands": 2, "island_vertices": 11,
            "island_xy": [(30.0, 40.0), (50.0, 60.0)]})
    said = _say(monkeypatch)
    tot = report_groundside_law_seat(layout, "ZZZZ")
    assert tot["rings"] == 7 and tot["anchored"] == 7
    assert tot["from_prior"] == 1 and tot["interpolated"] == 15
    assert tot["islands"] == 3 and tot["island_vertices"] == 18
    blob = "\n".join(said)
    assert ("ZZZZ: 7 ring(s) seated — 7 weld anchor(s), 1 vertex(es) from "
            "the piece's own prior field, 15 law-interpolated along the "
            "ring; 3 ring(s) (18 vertex(es))") in blob
    # per-pass island breakdown, worst first
    assert "2 island ring(s) at merge_touching_groundside" in blob
    assert "1 island ring(s) at emit_groundside_pavement_dem" in blob


def test_the_island_line_names_the_CONDITION_not_a_cause(monkeypatch):
    """RULINGS 2026-08-06 binding point 2.  ``islands`` is incremented at
    exactly one branch — the ladder ran and ``law_at`` came back empty —
    and the line must say that, not "had no law source", which was also
    describing rings the pass returned before the ladder was reached."""
    from auto_patch.groundside import report_groundside_law_seat
    layout = _seat_book(_FakeLayout(),
                        p={"rings": 1, "islands": 1, "island_vertices": 4})
    said = _say(monkeypatch)
    report_groundside_law_seat(layout, "ZZZZ")
    blob = "\n".join(said)
    assert ("reached the law ladder with NO weld anchor and NO prior field "
            "(condition: law_at empty)") in blob
    assert "had no law source" not in blob


def test_the_seat_printer_prints_at_ZERO(monkeypatch):
    """The KEEP: an absent line means the pass did not run, so a
    zero-island build still prints (~:711-718, ~:727)."""
    from auto_patch.groundside import report_groundside_law_seat
    layout = _seat_book(_FakeLayout(),
                        p={"rings": 2, "anchored": 2, "interpolated": 4})
    said = _say(monkeypatch)
    tot = report_groundside_law_seat(layout, "ZZZZ")
    assert tot["islands"] == 0
    assert "ZZZZ: 2 ring(s) seated" in "\n".join(said)
    assert "island ring(s) at" not in "\n".join(said)


def test_the_seat_line_carries_the_DEM_WORLD_and_the_tree(monkeypatch):
    """Binding point 3 on the WEAKEST-stamped instrument in the sweep: the
    line carried ``icao`` and nothing else, on an instrument whose entire
    subject is whether a value is DEM-derived."""
    from auto_patch.groundside import report_groundside_law_seat
    layout = _seat_book(_FakeLayout(), p={"rings": 1})
    layout._gs_dem_worlds = {"ConstantDEM:<constant-dem 10000 m>"}
    said = _say(monkeypatch)
    tot = report_groundside_law_seat(layout, "ZZZZ")
    blob = "\n".join(said)
    assert f"tree={instrument_tree_sha()}" in blob
    assert "dem_world=ConstantDEM:<constant-dem 10000 m>" in blob
    assert "NOT solver node ids" in blob
    assert tot["dem_worlds"] == ["ConstantDEM:<constant-dem 10000 m>"]


def test_two_DEM_worlds_in_one_build_are_BOTH_reported(monkeypatch):
    """A set, not a last-writer-wins string: a build that sampled two
    different DEMs is a fact worth surfacing, not one to overwrite."""
    from auto_patch.groundside import report_groundside_law_seat
    layout = _seat_book(_FakeLayout(), p={"rings": 1})
    layout._gs_dem_worlds = {"ConstantDEM:<constant-dem 10000 m>",
                             "DEM:/tiles/+30+031.hgt"}
    said = _say(monkeypatch)
    report_groundside_law_seat(layout, "ZZZZ")
    blob = "\n".join(said)
    assert ("dem_world=ConstantDEM:<constant-dem 10000 m>+"
            "DEM:/tiles/+30+031.hgt") in blob


def test_the_seat_line_reports_LOCATORS_so_a_count_can_be_attributed(
        monkeypatch):
    """``island_vertices`` was a bare total with no way to reach a single
    one of them, which defeats the docstring's own "a nonzero count is a
    defect to attribute" claim."""
    from auto_patch.groundside import report_groundside_law_seat
    layout = _seat_book(
        _FakeLayout(),
        p={"rings": 1, "islands": 2, "island_vertices": 9,
           "island_xy": [(12.34, 56.78), (-9.0, 4.5)]})
    said = _say(monkeypatch)
    tot = report_groundside_law_seat(layout, "ZZZZ")
    assert tot["island_xy"] == [(12.34, 56.78), (-9.0, 4.5)]
    assert "(12.34,56.78), (-9.00,4.50)" in "\n".join(said)


def test_the_accumulator_records_one_locator_per_island_ring():
    """The producer half of the same twin: the locator is the ring's own
    first vertex, one per island ring, counts never capped."""
    from auto_patch.groundside import (_seat_ring_on_law_anchors,
                                       GROUNDSIDE_MAX_GRADE, _ISLAND_XY_CAP)
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    stats = {}
    for _ in range(_ISLAND_XY_CAP + 3):
        _seat_ring_on_law_anchors(ring, [7.0] * 3, {}, GROUNDSIDE_MAX_GRADE,
                                  stats=stats)
    assert stats["islands"] == _ISLAND_XY_CAP + 3, "counts are never capped"
    assert len(stats["island_xy"]) == _ISLAND_XY_CAP, "locators are"
    assert stats["island_xy"][0] == (0.0, 0.0)


# ═════════════════════════════════════════════════════════════════════════
# 7 — THE RE-SEAT PASS AND ITS SKIP BUCKETS (groundside ~:664-707,
#     pipeline ~:5712-5715)
# ═════════════════════════════════════════════════════════════════════════
class _ConstDEM:
    def __init__(self, v=7.0):
        self.v = float(v)
        self.source_path = f"<constant-dem {self.v:g} m>"

    def alt(self, xy):
        return self.v

    def alt_strict(self, xy):
        return self.v


def _gs_layout(shapes):
    layout = _FakeLayout()
    layout.anchor = (0.0, 0.0)
    layout.shapes = list(shapes)
    return layout


def _gs_shape(role, pts, alts=None, seated=False):
    from shapely.geometry import Polygon
    from auto_patch.groundside import _LAW_SEATED_ATTR

    class _S:
        pass

    s = _S()
    s.role = role
    s.polygon = Polygon(pts + [pts[0]])
    s.node_altitudes = None if alts is None else list(alts)
    s.altitude = None
    s.altitude_high = None
    s.altitude_low = None
    if seated:
        setattr(s, _LAW_SEATED_ATTR, True)
    return s


def test_the_reseat_pass_counts_each_SKIP_at_its_own_branch(monkeypatch):
    """KNOWN ANSWER, one groundside ring per exit door.

    Four candidates: one already law-seated, one with no usable polygon,
    one with a 2-vertex ring, and one genuine law island (no higher
    authority anywhere).  Nothing is re-seated, and the four skips land in
    four DIFFERENT named buckets instead of one count labelled "had no law
    source" — the ruling's catch-all pattern."""
    from auto_patch.groundside import (seat_groundside_on_law,
                                       ROLE_GROUNDSIDE_PAVEMENT as _GS)
    from shapely.geometry import Polygon
    ok = _gs_shape(_GS, [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0)])
    seated = _gs_shape(_GS, [(50.0, 0.0), (70.0, 0.0), (70.0, 20.0)],
                       seated=True)
    empty = _gs_shape(_GS, [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])
    empty.polygon = Polygon()

    class _Ext:
        coords = [(0.0, 0.0), (1.0, 0.0)]

    class _TwoPointPoly:
        is_empty = False
        geom_type = "Polygon"
        exterior = _Ext()

    tiny = _gs_shape(_GS, [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])
    tiny.polygon = _TwoPointPoly()
    layout = _gs_layout([ok, seated, empty, tiny])
    n = seat_groundside_on_law(layout, _ConstDEM(), 0, 0)
    assert n == 0, "no higher authority exists, so nothing can be seated"
    st = layout._gs_law_seat["post_solve_groundside_law_seat"]
    assert st["candidates"] == 4
    assert st["reseated"] == 0
    assert st["skipped"]["already_law_seated"] == 1
    assert st["skipped"]["no_usable_polygon"] == 1
    assert st["skipped"]["ring_under_3_vertices"] == 1
    assert st["skipped"]["no_law_source_at_ladder"] == 1
    # the ladder-level counter still counts the ONE ring that reached it
    assert st["islands"] == 1 and st["island_vertices"] == 3


def test_a_ring_the_law_reaches_is_reseated_and_counted(monkeypatch):
    """The positive control: an apron at 100 m welded to the lot's first
    vertex.  The lot is seated on the law (100 m at the weld) instead of
    the 7 m DEM seed, ``reseated`` is 1 and no skip bucket fires."""
    from auto_patch.groundside import (seat_groundside_on_law,
                                       ROLE_GROUNDSIDE_PAVEMENT as _GS,
                                       _LAW_SEATED_ATTR)
    from auto_patch.layout import ROLE_APRON
    apron = _gs_shape(ROLE_APRON,
                      [(0.0, 0.0), (-20.0, 0.0), (-20.0, -20.0)],
                      alts=[100.0, 100.0, 100.0])
    lot = _gs_shape(_GS, [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0)])
    layout = _gs_layout([apron, lot])
    n = seat_groundside_on_law(layout, _ConstDEM(), 0, 0)
    assert n == 1
    st = layout._gs_law_seat["post_solve_groundside_law_seat"]
    assert st["candidates"] == 1 and st["reseated"] == 1
    assert st.get("skipped", {}) == {}
    assert st.get("islands", 0) == 0
    assert getattr(lot, _LAW_SEATED_ATTR) is True
    assert lot.node_altitudes[0] == pytest.approx(100.0), (
        "the weld vertex takes the LAW value, not the 7 m DEM seed")


def test_the_reseat_pass_stamps_the_DEM_WORLD_it_sampled():
    """The world stamp is taken at ``_dem_sampler`` — the one seam every
    groundside DEM read passes through — so it cannot describe a
    different DEM from the one that produced the seeds."""
    from auto_patch.groundside import (seat_groundside_on_law,
                                       ROLE_GROUNDSIDE_PAVEMENT as _GS)
    lot = _gs_shape(_GS, [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0)])
    layout = _gs_layout([lot])
    seat_groundside_on_law(layout, _ConstDEM(10000.0), 0, 0)
    assert layout._gs_dem_worlds == {"_ConstDEM:<constant-dem 10000 m>"}


def test_the_seed_unreadable_bucket_is_its_own_condition():
    """The branch the old report described but never counted: the DEM
    answers None AND the ring's own field is the wrong length.  This ring
    never reaches the law ladder, so it is NOT an observation about law
    reach — and it must not be filed under ``islands``."""
    from auto_patch.groundside import (seat_groundside_on_law,
                                       ROLE_GROUNDSIDE_PAVEMENT as _GS)

    class _NoneDEM:
        """Off-tile everywhere: ``elevation._sample_dem`` answers None."""
        source_path = "<off-tile-dem>"

        def alt(self, xy):
            raise ValueError("out of tile")

        def alt_strict(self, xy):
            raise ValueError("out of tile")

    lot = _gs_shape(_GS, [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0)],
                    alts=[5.0])                     # wrong length on purpose
    layout = _gs_layout([lot])
    n = seat_groundside_on_law(layout, _NoneDEM(), 0, 0)
    assert n == 0
    st = layout._gs_law_seat["post_solve_groundside_law_seat"]
    assert st["skipped"]["seed_altitudes_unreadable"] == 1
    assert st.get("islands", 0) == 0, (
        "a ring that never reached the ladder is not a law island")


def test_the_skip_buckets_reach_the_printed_line(monkeypatch):
    """End to end: the buckets counted at the branches are the buckets the
    log line names."""
    from auto_patch.groundside import (seat_groundside_on_law,
                                       report_groundside_law_seat,
                                       ROLE_GROUNDSIDE_PAVEMENT as _GS)
    lot = _gs_shape(_GS, [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0)])
    seated = _gs_shape(_GS, [(50.0, 0.0), (70.0, 0.0), (70.0, 20.0)],
                       seated=True)
    layout = _gs_layout([lot, seated])
    seat_groundside_on_law(layout, _ConstDEM(), 0, 0)
    said = _say(monkeypatch)
    tot = report_groundside_law_seat(layout, "ZZZZ")
    blob = "\n".join(said)
    assert "post-solve seat pass: 0 of 2 groundside ring(s) re-seated" in blob
    assert "no_law_source_at_ladder=1" in blob
    assert "already_law_seated=1" in blob
    assert tot["skipped"]["already_law_seated"] == 1


def test_the_reseat_line_in_the_pipeline_reports_the_pass_return_value():
    """``pipeline`` ~:5712-5715 prints ``seat_groundside_on_law``'s return
    value verbatim; the drift lock is that it reports THAT number and no
    re-derived one."""
    import inspect
    from auto_patch import pipeline as P
    src = inspect.getsource(P)
    marker = "_n_seated = seat_groundside_on_law("
    assert marker in src
    tail = src[src.index(marker):src.index(marker) + 500]
    assert "if _n_seated:" in tail
    assert "{_n_seated} groundside ring(s) that were still on" in tail
