"""Twins for the ROUTE-DISTANCE SEAT COUPLING round (spec
``docs/specs/route-distance-seat-coupling-spec.md``).

THE DEFECT — two instruments over one population.  The seat coupler admits
and prices pairs in a STRAIGHT-CHORD frame (``polygon.distance ≤
BUILDING_REACH_CORRIDOR_M``, a 97 %-on-pavement visibility chord, limit
``APRON_MAX_GRADE·gap``), while the projection enforces the cap along the
WITHIN-SHAPE LAW GRAPH.  The dossier's HEAZ certificate is the type
specimen: ``building4↔building5`` are 17.6 m apart by chord (limit
0.176 m) but bound by the 2-hop chain ``35 —0.0578— 1295 —0.1015— 37``,
so the REAL budget is **0.1593 m** — and the pair was rejected outright as
"separated by grass".

Hermetic — no airport build, no fixtures.  Every twin drives
``anchors.build_building_seats`` directly with a hand-made band, DEM
sampler and LAW GRAPH, so a coupler that reads the geometry instead of the
graph fails them.  Covers:

  * the route budget IS the limit (the 35/1295/37 geometry) — there is no
    chord frame left to fall back to;
  * admission SUBSUMES the retired ``O4_SEAT_COUPLE_SHARED_SURFACE``
    predicate;
  * a route-unreachable pad is NOT admitted (no law binds it);
  * the BUDGET-IDENTITY property (spec §4): the coupler's pair budget IS
    the budget a real ``feasibility_project`` run settles at, within 1 %;
  * the loud empty-polytope attribution is unchanged.
"""
import pytest
from shapely.geometry import Polygon

from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.config import (APRON_MAX_GRADE, EMIT_QUANTIZATION_MARGIN_M)
from auto_patch.layout import BuiltShape, ROLE_APRON, ROLE_BUILDING
from auto_patch.elevation_per_surface import building_feasibility as BF
from auto_patch.elevation_per_surface.route_profile import anchors as AN
from auto_patch.elevation_per_surface.route_profile import one_solve as OS


# The dossier's own two hops (HEAZ 35 —0.0578(6.78 m)— 1295 —0.1015(11.15 m)
# — 37), quoted as the RAW budgets the graph carries; the projection sweeps
# them margined, and 0.0578 + 0.1015 = 0.1593 is the number that binds.
_RAW_A = 0.0678
_RAW_B = 0.1115
_ROUTE = (OS._margined_budget(_RAW_A, EMIT_QUANTIZATION_MARGIN_M)
          + OS._margined_budget(_RAW_B, EMIT_QUANTIZATION_MARGIN_M))
_CHORD_GAP_M = 17.6
_CHORD = APRON_MAX_GRADE * _CHORD_GAP_M


class _FakeLayout:
    """Only what ``build_building_seats`` reads."""

    def __init__(self, shapes):
        self.shapes = shapes
        self.canonical_points = CanonicalPointRegistry()
        self.apt_taxi_centerlines = []


def _shape(ring, role, ref=""):
    return BuiltShape(polygon=Polygon(ring), role=role, ref=ref)


def _register(layout, shapes):
    cps = layout.canonical_points
    bucket_to_idx, idx = {}, 0
    for s in shapes:
        for (x, y) in list(s.polygon.exterior.coords)[:-1]:
            k = cps.get_or_add(float(x), float(y))
            if k not in bucket_to_idx:
                bucket_to_idx[k] = idx
                idx += 1
    return bucket_to_idx


def _idx(layout, b2i, x, y):
    return b2i[layout.canonical_points.get(float(x), float(y))]


def _law_graph(layout, b2i, edges):
    """One ``shape_constraints`` entry over EXPLICIT ``(xy, xy, raw budget)``
    edges — the graph the projection would enforce, handed to the coupler."""
    out = [(_idx(layout, b2i, *a), _idx(layout, b2i, *b), float(w))
           for (a, b, w) in edges]
    nodes = sorted({i for e in out for i in e[:2]})
    return [{"nodes": nodes, "edges": out, "flat": False}]


def _seats(layout, b2i, band, dem, levels, monkeypatch, law_graph=None):
    monkeypatch.setattr(BF, "building_feasible_levels", lambda *a, **k: levels)
    return AN.build_building_seats(layout, b2i, band, dem, [],
                                   law_graph=law_graph,
                                   n_nodes=(None if law_graph is None
                                            else len(b2i)))


def _level_of(seats, b2i, cps, shape):
    x, y = list(shape.polygon.exterior.coords)[0]
    return seats.get(b2i[cps.get(float(x), float(y))])


# ── the divergence geometry: chord 17.6 m, route 0.1593 m ────────────────

def _divergence_layout():
    """Two pads 17.6 m apart ON one apron, whose LAW-GRAPH path between them
    is the dossier's 2-hop chain through an apron node.

    The chord between them is fully pavement-visible, so BOTH frames admit
    the pair — the twin isolates the LIMIT, not the admission: chord pricing
    says 0.176 m, the graph says 0.1593 m.
    """
    apron = _shape([(0.0, 0.0), (28.8, 0.0), (100.0, 0.0), (100.0, 80.0),
                    (0.0, 80.0)], ROLE_APRON, "apron1")
    a = _shape([(0.0, 40.0), (20.0, 40.0), (20.0, 60.0), (0.0, 60.0)],
               ROLE_BUILDING, "building4")
    b = _shape([(37.6, 40.0), (57.6, 40.0), (57.6, 60.0), (37.6, 60.0)],
               ROLE_BUILDING, "building5")
    return _FakeLayout([apron, a, b]), apron, a, b


def _divergence_band(x, y):
    """padA's ring reaches 100.0, padB's 101.108 (the dossier's 1.108 m
    value gap).  Floors are far below, so the pair's own boxes never bind
    before the coupling limit does."""
    return (95.0, 100.0) if x < 30.0 else (95.0, 101.108)


def _divergence_case(monkeypatch):
    layout, apron, a, b = _divergence_layout()
    b2i = _register(layout, [apron, a, b])
    lg = _law_graph(layout, b2i, [((20.0, 40.0), (28.8, 0.0), _RAW_A),
                                  ((28.8, 0.0), (37.6, 40.0), _RAW_B)])
    seats = _seats(layout, b2i, _divergence_band, lambda x, y: 200.0,
                   {id(a): 100.0, id(b): 101.108}, monkeypatch, law_graph=lg)
    cps = layout.canonical_points
    return (_level_of(seats, b2i, cps, a), _level_of(seats, b2i, cps, b))


def test_the_geometry_is_a_real_divergence():
    """Guard the twin itself: if the two frames ever agreed, the tests below
    would pass without measuring anything."""
    assert _ROUTE == pytest.approx(0.1593, abs=1e-6)
    assert _CHORD == pytest.approx(0.176, abs=1e-6)
    assert _ROUTE < _CHORD


def test_there_is_no_chord_frame_to_fall_back_to(monkeypatch, capsys):
    """STANDING LAW: with NO ``O4_`` var set — what a user build does — the
    pair is priced on the ROUTE, and the chord limit appears only as the
    census figure the report names."""
    lv_a, lv_b = _divergence_case(monkeypatch)
    assert abs(lv_b - lv_a) == pytest.approx(_ROUTE, abs=1e-3)
    assert abs(lv_b - lv_a) != pytest.approx(_CHORD, abs=1e-3)
    assert "ROUTE METRIC" in capsys.readouterr().out


def test_route_budget_replaces_the_chord_limit(monkeypatch, capsys):
    """THE ROUND: the pair is priced at the budget the projection enforces
    along the law graph (0.1593 m), not at ``APRON_MAX_GRADE·chord``."""
    lv_a, lv_b = _divergence_case(monkeypatch)
    assert abs(lv_b - lv_a) == pytest.approx(_ROUTE, abs=1e-3)
    text = capsys.readouterr().out
    assert "ROUTE METRIC" in text
    assert "1 coupled pair(s) of 1" in text
    assert "TIGHTENED" in text
    assert "budget identity OK" in text
    assert "not_visible 0" in text


def test_the_law_graph_is_read_not_the_geometry(monkeypatch):
    """Same geometry, different GRAPH ⇒ different limit.  A coupler that
    priced the chord could not tell these two runs apart."""
    layout, apron, a, b = _divergence_layout()
    b2i = _register(layout, [apron, a, b])
    lg = _law_graph(layout, b2i, [((20.0, 40.0), (28.8, 0.0), 0.30),
                                  ((28.8, 0.0), (37.6, 40.0), 0.30)])
    seats = _seats(layout, b2i, _divergence_band, lambda x, y: 200.0,
                   {id(a): 100.0, id(b): 101.108}, monkeypatch, law_graph=lg)
    cps = layout.canonical_points
    lv_a = _level_of(seats, b2i, cps, a)
    lv_b = _level_of(seats, b2i, cps, b)
    # 0.29 + 0.29 = 0.58 of budget — LOOSER than the chord's 0.176.
    assert abs(lv_b - lv_a) == pytest.approx(0.58, abs=1e-3)


# ── §4 BUDGET IDENTITY — measured against a real projection run ──────────

def test_the_coupler_budget_is_the_projections_binding_budget():
    """Spec §4, the point of the round: the coupler's pair budget equals the
    budget ``feasibility_project`` actually settles at, within 1 %.

    Node 0 is a hard anchor; node 2 starts far above and the sweeps drive it
    down until the 2-hop chain is satisfied.  Where it stops IS the binding
    budget — and it is the number the coupler prices with."""
    edges = [(0, 1, _RAW_A), (1, 2, _RAW_B)]
    elev = [100.0, 500.0, 500.0]
    OS.feasibility_project(elev, [{"edges": list(edges)}], {0},
                           force_scalar=True, max_iters=20000, tol=1e-6)
    achieved = elev[2] - elev[0]
    budgets, diag = AN._pad_route_budgets(
        [{"edges": list(edges), "nodes": [0, 1, 2], "flat": False}],
        [{0}, {2}], n_nodes=3)
    assert budgets[(0, 1)] == pytest.approx(achieved, rel=0.01), (
        "coupler and projection must price the same path in the same frame "
        "— a larger disagreement is two instruments again, and the spec's "
        "STOP")
    assert diag["ident_worst"] <= 0.01
    assert not diag["ident_over"]


def test_the_frame_split_is_reported_law_route_vs_margin(monkeypatch,
                                                         capsys):
    """ATTRIBUTION, not a second authority: the enforced budget is the
    margined one, but the margin is subtracted PER EDGE, so a multi-hop
    route loses one margin per hop (``raw_law_sweeps_enabled`` §1b).  The
    dossier's own pair is the specimen — 0.1593 margined is TIGHTER than the
    0.176 chord, while its RAW-law route (0.1793) is LOOSER: the tightening
    is the margin's, not the law's, and the report must say so."""
    _divergence_case(monkeypatch)
    text = capsys.readouterr().out
    assert "tightening attribution" in text
    assert "0 of 1 tightened pair(s) are tighter than the chord in the RAW" \
        in text
    assert "raw-law route 0.1793 m (~2 hop(s) of margin)" in text


def test_raw_budgets_ride_the_diagnostics_only():
    edges = [(0, 1, 0.05), (1, 2, 0.07)]
    budgets, diag = AN._pad_route_budgets(
        [{"edges": list(edges), "nodes": [0, 1, 2], "flat": False}],
        [{0}, {2}], n_nodes=3)
    assert budgets[(0, 1)] == pytest.approx(0.10, abs=1e-9)
    assert diag["raw_budgets"][(0, 1)] == pytest.approx(0.12, abs=1e-9)


def test_budget_identity_is_symmetric_on_every_pair():
    """The in-round check the build reports: pricing a pair from either
    endpoint must agree.  Asymmetry means a truncated or one-sided walk."""
    edges = [(0, 1, 0.05), (1, 2, 0.07), (2, 3, 0.02), (0, 3, 0.5)]
    budgets, diag = AN._pad_route_budgets(
        [{"edges": list(edges), "nodes": [0, 1, 2, 3], "flat": False}],
        [{0}, {2}, {3}], n_nodes=4)
    assert diag["ident_worst"] == pytest.approx(0.0, abs=1e-9)
    # min-budget path 0→2 is 0.05+0.07 margined = 0.04+0.06 = 0.10, NOT the
    # direct-ish 0.5 edge via 3 (0.49 + 0.01).
    assert budgets[(0, 1)] == pytest.approx(0.10, abs=1e-9)


def test_tightest_budget_wins_on_duplicate_pairs():
    """The projection's own dedup rule (``one_solve._build_adjacency``):
    several constraints on one index pair ⇒ the binding one is the minimum."""
    edges = [(0, 1, 0.90), (0, 1, 0.20)]
    budgets, _diag = AN._pad_route_budgets(
        [{"edges": list(edges), "nodes": [0, 1], "flat": False}],
        [{0}, {1}], n_nodes=2)
    assert budgets[(0, 1)] == pytest.approx(
        OS._margined_budget(0.20, EMIT_QUANTIZATION_MARGIN_M), abs=1e-9)


def test_interval_edges_are_not_routed_through():
    """A one-sided slab (adjacent-ground zone / RESA cut) has no symmetric
    route price and must never become a coupling path."""
    edges = [(0, 1, None, 2.0), (1, 2, -3.0, None)]
    budgets, diag = AN._pad_route_budgets(
        [{"edges": list(edges), "nodes": [0, 1, 2], "flat": False}],
        [{0}, {2}], n_nodes=3)
    assert budgets == {}
    assert diag["interval_edges"] == 2


def test_unregulated_and_out_of_range_edges_are_dropped():
    edges = [(0, 1, None), (1, 2, -1.0), (0, 2, 0.4), (0, 9, 0.1)]
    budgets, _d = AN._pad_route_budgets(
        [{"edges": list(edges), "nodes": [0, 1, 2], "flat": False}],
        [{0}, {2}], n_nodes=3)
    assert budgets[(0, 1)] == pytest.approx(
        OS._margined_budget(0.4, EMIT_QUANTIZATION_MARGIN_M), abs=1e-9)


def test_touching_pads_merge_into_one_rigid_unit():
    """Two pads sharing a ring node act as ONE flat group in the projection;
    their coupling budget is 0 by law, not by proximity."""
    budgets, _d = AN._pad_route_budgets(
        [{"edges": [(0, 5, 0.4)], "nodes": [0, 5], "flat": False}],
        [{0, 1}, {1, 2}], n_nodes=8)
    assert budgets[(0, 1)] == 0.0


# ── admission: supersession, reachability, horizon ───────────────────────

def _u_layout():
    """The dossier's shape: a U-shaped apron with a pad on each arm.  The
    straight chord across the U's mouth is off pavement (the visibility
    fraction rejects the pair) while a THROUGH-SURFACE path exists — the
    ``O4_SEAT_COUPLE_SHARED_SURFACE`` case, which route admission subsumes.
    ``padF`` stands on its own ground: no route, no law, no coupling."""
    apron = _shape([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (80.0, 60.0),
                    (80.0, 20.0), (20.0, 20.0), (20.0, 60.0), (0.0, 60.0)],
                   ROLE_APRON, "apronU")
    left = _shape([(0.0, 60.0), (20.0, 60.0), (20.0, 80.0), (0.0, 80.0)],
                  ROLE_BUILDING, "padL")
    right = _shape([(80.0, 60.0), (100.0, 60.0), (100.0, 80.0),
                    (80.0, 80.0)], ROLE_BUILDING, "padR")
    far = _shape([(150.0, 150.0), (170.0, 150.0), (170.0, 170.0),
                  (150.0, 170.0)], ROLE_BUILDING, "padF")
    return _FakeLayout([apron, left, right, far]), apron, left, right, far


def _u_band(x, y):
    if x < 50.0:
        return (95.0, 100.0)
    if x < 120.0:
        return (95.0, 102.0)
    return (95.0, 110.0)


def _u_case(monkeypatch, extra_edges=()):
    layout, apron, left, right, far = _u_layout()
    b2i = _register(layout, [apron, left, right, far])
    lg = _law_graph(layout, b2i,
                    [((20.0, 60.0), (20.0, 20.0), 0.20),
                     ((20.0, 20.0), (80.0, 20.0), 0.60),
                     ((80.0, 20.0), (80.0, 60.0), 0.20)] + list(extra_edges))
    levels = {id(left): 100.0, id(right): 102.0, id(far): 105.0}
    seats = _seats(layout, b2i, _u_band, lambda x, y: 105.0, levels,
                   monkeypatch, law_graph=lg)
    cps = layout.canonical_points
    return (_level_of(seats, b2i, cps, left),
            _level_of(seats, b2i, cps, right),
            _level_of(seats, b2i, cps, far))


def test_route_admission_subsumes_the_shared_surface_predicate(
        monkeypatch, capsys):
    """The pair the visibility fraction rejected as "separated by grass" is
    offered to the solver — with NO shared-surface gate set."""
    lv_l, lv_r, _lv_f = _u_case(monkeypatch)
    limit = sum(OS._margined_budget(w, EMIT_QUANTIZATION_MARGIN_M)
                for w in (0.20, 0.60, 0.20))
    assert abs(lv_r - lv_l) <= limit + 1e-3
    text = capsys.readouterr().out
    assert "ROUTE METRIC" in text
    assert "shared-surface adjacency admitted" not in text


def test_the_retired_shared_surface_var_has_no_effect(monkeypatch, capsys):
    """The predicate is GONE, not merged: setting its old env var is inert
    (a stale script must never quietly re-arm a retired instrument)."""
    off = _u_case(monkeypatch)
    capsys.readouterr()
    monkeypatch.setenv("O4_SEAT_COUPLE_SHARED_SURFACE", "1")
    on = _u_case(monkeypatch)
    assert off == on
    assert "shared-surface adjacency admitted" not in capsys.readouterr().out


def test_a_pad_off_the_law_graph_is_not_admitted(monkeypatch, capsys):
    """Route-unreachable pads do not couple — no law binds them, and
    coupling them was never meaningful (spec §2)."""
    _lv_l, _lv_r, lv_f = _u_case(monkeypatch)
    assert lv_f == pytest.approx(105.0)
    assert "unit off the law graph 2" in capsys.readouterr().out


def test_a_route_beyond_the_horizon_is_not_admitted(monkeypatch, capsys):
    """Admission is the corridor dial expressed in the metric the law
    enforces: 200 m at the apron cap = 2.0 m of route budget."""
    horizon, dial = AN.route_coupling_horizon_m()
    assert (horizon, dial) == (pytest.approx(2.0), pytest.approx(200.0))
    # the U's through-route now costs 3.0 m of budget — beyond the horizon
    layout, apron, left, right, far = _u_layout()
    b2i = _register(layout, [apron, left, right, far])
    lg = _law_graph(layout, b2i, [((20.0, 60.0), (80.0, 60.0), 3.0)])
    levels = {id(left): 100.0, id(right): 102.0, id(far): 105.0}
    seats = _seats(layout, b2i, _u_band, lambda x, y: 105.0, levels,
                   monkeypatch, law_graph=lg)
    cps = layout.canonical_points
    assert _level_of(seats, b2i, cps, left) == pytest.approx(100.0)
    assert _level_of(seats, b2i, cps, right) == pytest.approx(102.0)
    assert "route-unreachable 1" in capsys.readouterr().out


def test_the_coupler_says_so_when_the_solve_passes_no_law_graph(monkeypatch,
                                                                capsys):
    """A wiring defect is never a silent fallback to the chord."""
    layout, apron, a, b = _divergence_layout()
    b2i = _register(layout, [apron, a, b])
    _seats(layout, b2i, _divergence_band, lambda x, y: 200.0,
           {id(a): 100.0, id(b): 101.108}, monkeypatch, law_graph=None)
    assert "passed no law graph" in capsys.readouterr().out


# ── the loud empty polytope is unchanged ─────────────────────────────────

def test_touching_pads_are_seated_as_one_unit_not_as_a_zero_budget_pair(
        monkeypatch, capsys):
    """MERGED RIGID UNITS (standing law).  padD and padE share two ring
    vertices, so they are ONE unit — there is no |L_D − L_E| ≤ 0 pair for
    the POCS to approximate and no group mean for the projection to mint.
    Their boxes are disjoint, which is a LAW DEFECT and is named."""
    apron = _shape([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (40.0, 60.0),
                    (20.0, 60.0), (0.0, 60.0)], ROLE_APRON, "apron1")
    d = _shape([(0.0, 60.0), (20.0, 60.0), (20.0, 80.0), (0.0, 80.0)],
               ROLE_BUILDING, "padD")
    e = _shape([(20.0, 60.0), (40.0, 60.0), (40.0, 80.0), (20.0, 80.0)],
               ROLE_BUILDING, "padE")
    layout = _FakeLayout([apron, d, e])
    b2i = _register(layout, [apron, d, e])
    lg = _law_graph(layout, b2i, [((0.0, 0.0), (100.0, 0.0), 0.5)])
    seats = _seats(layout, b2i,
                   lambda x, y: (95.0, 100.0) if x < 20.0 else (104.0, 106.0),
                   lambda x, y: 105.0 + 0.05 * y, {id(d): 100.0, id(e): 106.0},
                   monkeypatch, law_graph=lg)
    cps = layout.canonical_points
    assert _level_of(seats, b2i, cps, d) == _level_of(seats, b2i, cps, e)
    text = capsys.readouterr().out
    assert "MERGED RIGID unit(s) covering 2 pad(s)" in text
    assert "EMPTY member-box intersection" in text


# ── the loud empty polytope is unchanged ─────────────────────────────────

def test_empty_polytope_stays_loud_under_route_pricing(monkeypatch, capsys):
    """RULINGS 2026-08-04 (split-level building seats): an empty coupling
    polytope is LOUD attribution, never a silent ship.

    Two pads that do NOT touch (0.5 m apart, so two separate units) bound
    by a 0.01 m route budget, with disjoint boxes: no joint level exists."""
    apron = _shape([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)],
                   ROLE_APRON, "apron1")
    d = _shape([(0.0, 60.0), (20.0, 60.0), (20.0, 80.0), (0.0, 80.0)],
               ROLE_BUILDING, "padD")
    e = _shape([(20.5, 60.0), (40.0, 60.0), (40.0, 80.0), (20.5, 80.0)],
               ROLE_BUILDING, "padE")
    layout = _FakeLayout([apron, d, e])
    b2i = _register(layout, [apron, d, e])
    lg = _law_graph(layout, b2i, [((20.0, 60.0), (20.5, 60.0), 0.02)])
    seats = _seats(layout, b2i,
                   lambda x, y: (95.0, 100.0) if x <= 20.0 else (104.0, 106.0),
                   lambda x, y: 105.0 + 0.05 * y, {id(d): 100.0, id(e): 106.0},
                   monkeypatch, law_graph=lg)
    cps = layout.canonical_points
    assert _level_of(seats, b2i, cps, d) == pytest.approx(100.0)
    assert _level_of(seats, b2i, cps, e) == pytest.approx(106.0)
    text = capsys.readouterr().out
    assert "EMPTY POLYTOPE" in text
    assert "padD" in text and "padE" in text
    assert "chord_lim" in text          # the pair-by-pair split accounting
