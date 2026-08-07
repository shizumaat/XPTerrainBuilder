"""THE CYCLE-11 SERVICE-BAND INSTRUMENTS — known-answer twins.

Two report-only, default-OFF instruments land with the service-band
attribution (spec ``docs/specs/service-band-propagation-spec.md``, Job 1):

* ``O4_DUMP_SERVICE_STRINGING`` — per service centerline, WHICH condition
  stopped it stringing: no candidate node inside the perpendicular
  tolerance (`no_candidate_in_tol`, the recorded suspect), candidates
  inside it that the ELIGIBILITY restriction excluded
  (`ineligible_in_tol`, a different mechanism), or exactly one on-line
  node (`one_node`).
* ``O4_DUMP_SERVICE_BAND`` — the in-process counterfactual: the groundside
  route band built twice on one graph, with and without the service spine
  pairs, diffed node by node.

RULINGS 2026-08-06 (instrument truth) binding point 1: an instrument
carries a calibration twin feeding it a case whose answer is KNOWN, and
asserts the report.  Both cases below are decidable on paper — the
distances are chosen so the classification is arithmetic, and the
counterfactual graph has exactly one route to the far node.

Hand-built structures, no build, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch import grade_graph as GG                        # noqa: E402
from auto_patch import groundside as GS                         # noqa: E402


@pytest.fixture(autouse=True)
def _no_instrument_env(monkeypatch):
    for g in ("O4_DUMP_SERVICE_STRINGING", "O4_DUMP_SERVICE_BAND",
              "O4_PROBE_NO_SERVICE_EDGES", "O4_PROBE_NO_MOUTHS"):
        monkeypatch.delenv(g, raising=False)


# ── the stringing diagnostic ─────────────────────────────────────────
#
# THE KNOWN ANSWER.  Four service centerlines, each 100 m long along y = k,
# and a node set placed at hand-picked perpendicular offsets.  The service
# tolerance is ``SERVICE_ROAD_WIDTH_M/2 + 1.0`` = 4.0 m.
#
#   cl A (y=0)   two ELIGIBLE nodes at 3.0 m  -> strung          (2 on-line)
#   cl B (y=100) two nodes at 3.0 m, NEITHER eligible -> ineligible_in_tol
#   cl C (y=200) two eligible nodes at 9.0 m -> no_candidate_in_tol
#   cl D (y=300) ONE eligible node at 0.5 m  -> one_node
#
# Every number is chosen so no two classes can be confused: 3.0 < 4.0 and
# 9.0 > 4.0 with margin, and the eligibility sets are explicit.

def _stringing_case():
    def _cl(y, service=True):
        return GG.Centerline(pts=[(0.0, y), (100.0, y)], seg_caps=[0.08],
                             is_service=service)

    cls = [_cl(0.0), _cl(100.0), _cl(200.0), _cl(300.0)]
    # node idx -> (x, y).  Two per centerline except D.
    pos = {
        10: (20.0, 3.0), 11: (60.0, 3.0),          # A, eligible
        20: (20.0, 103.0), 21: (60.0, 103.0),      # B, NOT eligible
        30: (20.0, 209.0), 31: (60.0, 209.0),      # C, eligible but far
        40: (20.0, 300.5),                         # D, eligible, alone
    }
    eligible = {10, 11, 30, 31, 40}
    return cls, pos, eligible


def _run_stringing(tmp_path, monkeypatch):
    cls, pos, eligible = _stringing_case()
    out = tmp_path / "svc.json"
    monkeypatch.setenv("O4_DUMP_SERVICE_STRINGING", str(out))
    G = GG.UnifiedGraph()
    G.pos.update(pos)
    ctx = SimpleNamespace(centerlines=cls, service_source="test",
                          service_length_m=400.0)
    GG._build_global_spine(G, ctx, icao="TEST", road_nodes=eligible)
    layout = SimpleNamespace(icao="TEST",
                             m_to_ll=lambda x, y: (30.0 + y / 1e5,
                                                   31.0 + x / 1e5))
    GG._write_service_stringing_diag(layout, G)
    return json.loads(out.read_text())


def test_the_stringing_diagnostic_classifies_every_known_case(tmp_path,
                                                              monkeypatch):
    rec = _run_stringing(tmp_path, monkeypatch)
    got = {r["ci"]: r["class"] for r in rec["centerlines"]}
    assert got == {0: "strung", 1: "ineligible_in_tol",
                   2: "no_candidate_in_tol", 3: "one_node"}, (
        "the diagnostic collapsed two DIFFERENT stringing failures into "
        "one class — which is exactly the reading error it exists to stop")


def test_the_stringing_diagnostic_reports_the_distances_it_measured(
        tmp_path, monkeypatch):
    rec = _run_stringing(tmp_path, monkeypatch)
    by_ci = {r["ci"]: r for r in rec["centerlines"]}
    assert rec["service_perp_tol_m"] == pytest.approx(4.0)
    assert by_ci[0]["min_d_eligible_m"] == pytest.approx(3.0)
    assert by_ci[2]["min_d_eligible_m"] == pytest.approx(9.0)
    # the INELIGIBLE case must still report the distance it saw, or the
    # reader cannot tell "no geometry" from "geometry refused"
    assert by_ci[1]["min_d_any_m"] == pytest.approx(3.0)
    assert by_ci[1]["n_in_tol"] == 2 and by_ci[1]["n_eligible_in_tol"] == 0


def test_the_stringing_diagnostic_carries_canonical_identity(tmp_path,
                                                             monkeypatch):
    """11-decimal lat/lon is this repo's canonical identity spelling; a
    node reported without it can only be joined by proximity, which is the
    11.6%-wrong-object trap."""
    rec = _run_stringing(tmp_path, monkeypatch)
    for row in rec["centerlines"]:
        for n in row["nearest"]:
            assert n["ll"] is not None
            assert all(len(v.split(".")[1]) == 11 for v in n["ll"])


def test_the_stringing_diagnostic_is_silent_when_unset(tmp_path):
    cls, pos, eligible = _stringing_case()
    G = GG.UnifiedGraph()
    G.pos.update(pos)
    ctx = SimpleNamespace(centerlines=cls, service_source="test",
                          service_length_m=400.0)
    GG._build_global_spine(G, ctx, icao="TEST", road_nodes=eligible)
    assert getattr(G, "_service_stringing_diag", None) is None, (
        "the collector ran on a default build — the instrument is not free")


# ── the band counterfactual ──────────────────────────────────────────
#
# THE KNOWN ANSWER.  A 3-node chain 0 —taxi— 1 —SERVICE— 2, one mouth at
# node 0 whose airside interval is [1, 9].  The band's outward walk reaches
# node 2 ONLY through the service pair (1, 2).  Therefore dropping that
# pair must lose EXACTLY node 2 and nothing else.

class _FakeBand(dict):
    pass


def _band_case():
    G = SimpleNamespace(
        pos={0: (0.0, 0.0), 1: (10.0, 0.0), 2: (20.0, 0.0)},
        spine_adj={0: [(1, 0.5)], 1: [(0, 0.5), (2, 0.8)],
                   2: [(1, 0.8)]},
        service_spine_pairs={(1, 2)})
    return G


def _fake_band(src, mouths=1):
    def band(x, y):                                   # pragma: no cover
        return None
    band.src = src
    band.mouths = mouths
    band.sources = len(src)
    return band


def test_the_band_counterfactual_names_exactly_the_lost_node(tmp_path,
                                                             monkeypatch):
    G = _band_case()
    out = tmp_path / "band.json"
    monkeypatch.setenv("O4_DUMP_SERVICE_BAND", str(out))
    layout = SimpleNamespace(icao="TEST",
                             m_to_ll=lambda x, y: (30.0 + y / 1e5,
                                                   31.0 + x / 1e5))

    # THE ONE CODE PATH: the counterfactual re-calls the real band builder,
    # so the twin substitutes a builder whose answer is known rather than
    # re-implementing the band (a private copy would be the census-wrapper
    # defect this repo has already paid for).
    def _fake_builder(_layout, _G, **_kw):
        reach = {0: (1.0, 9.0), 1: (0.5, 9.5)}
        if (1, 2) in {(min(i, j), max(i, j))
                      for i, lst in _G.spine_adj.items() for (j, _b) in lst}:
            reach[2] = (-0.3, 10.3)
        return _fake_band(reach)

    monkeypatch.setattr(
        "auto_patch.elevation_per_surface.building_feasibility."
        "groundside_reach_band", _fake_builder)
    band = _fake_builder(layout, G)
    GS._service_edge_counterfactual(layout, G, band)
    rec = json.loads(out.read_text())
    assert rec["sources_full"] == 3
    assert rec["sources_no_service_edges"] == 2
    assert rec["lost_band_entirely"] == 1
    assert rec["band_interval_moved"] == 0
    assert rec["band_unchanged"] == 2
    assert [r["node"] for r in rec["sample_lost"]] == [2]
    assert rec["sample_lost"][0]["ll"] is not None


def test_the_band_counterfactual_restores_the_graph(tmp_path, monkeypatch):
    """A probe that reads a layout must leave it as it found it — the
    node-space discipline ``groundside_route_band`` already keeps."""
    G = _band_case()
    before = G.spine_adj
    monkeypatch.setenv("O4_DUMP_SERVICE_BAND", str(tmp_path / "b.json"))
    layout = SimpleNamespace(icao="TEST", m_to_ll=lambda x, y: (30.0, 31.0))
    monkeypatch.setattr(
        "auto_patch.elevation_per_surface.building_feasibility."
        "groundside_reach_band",
        lambda _l, _g, **_k: _fake_band({0: (1.0, 9.0)}))
    GS._service_edge_counterfactual(layout, G,
                                    _fake_band({0: (1.0, 9.0), 2: (0.0, 1.0)}))
    assert G.spine_adj is before


def test_the_band_counterfactual_is_silent_when_unset(tmp_path, monkeypatch):
    G = _band_case()
    calls = []
    monkeypatch.setattr(
        "auto_patch.elevation_per_surface.building_feasibility."
        "groundside_reach_band",
        lambda *_a, **_k: calls.append(1))
    GS._service_edge_counterfactual(SimpleNamespace(icao="T"), G,
                                    _fake_band({0: (1.0, 9.0)}))
    assert calls == [], ("the counterfactual ran a second Dijkstra on a "
                         "default build")
