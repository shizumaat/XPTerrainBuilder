"""THROUGH-WELD FAIRING (owner defect 2026-07-27, HECA taxiway dip at
30.11221,31.41089): ``_fair_spine_chains`` broke chains at every
degree-≠2 node, so the vertical-curve K-factor was blind exactly at
junction welds — a through-taxiway crossing a descending spine carved a
solver-manufactured 10 m V under a strictly monotone DEM.  Chains whose
terminal segments continue near-straight through a weld now SPLICE and
fair across it; genuine turns keep separate chains."""
from __future__ import annotations

import math
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from auto_patch import config
from auto_patch.elevation_per_surface.route_profile import solve as S

K_RATE = 1.0 / 3000.0


def _line_graph(xs, weld_extra=None):
    """A straight E-W corridor with nodes at ``xs`` (y = 0).  Optional
    ``weld_extra`` = (weld_x, branch_node_xy) grafts one branch edge at
    the weld so its degree becomes 3 (a junction weld)."""
    nodes_xy = [(x, 0.0) for x in xs]
    adj = {}
    for i in range(len(xs) - 1):
        w = xs[i + 1] - xs[i]
        adj.setdefault(i, []).append((i + 1, w))
        adj.setdefault(i + 1, []).append((i, w))
    if weld_extra is not None:
        weld_x, branch_xy = weld_extra
        wi = xs.index(weld_x)
        bi = len(nodes_xy)
        nodes_xy.append(branch_xy)
        d = math.hypot(branch_xy[0] - weld_x, branch_xy[1])
        adj.setdefault(wi, []).append((bi, d))
        adj.setdefault(bi, []).append((wi, d))
    return nodes_xy, adj


def _v_profile(xs, weld_x, depth):
    """Anchored ends at 0.0; a V dipping ``depth`` at the weld."""
    half = max(abs(weld_x - xs[0]), abs(xs[-1] - weld_x))
    return [-depth * (1.0 - abs(x - weld_x) / half) for x in xs]


def test_v_at_a_weld_is_faired_through(monkeypatch):
    monkeypatch.setattr(config, "SPINE_FAIR_THROUGH_WELDS", True)
    xs = [0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0]
    weld_x = 300.0
    nodes_xy, adj = _line_graph(
        xs, weld_extra=(weld_x, (300.0, 80.0)))   # 90° branch at x=300
    elev = _v_profile(xs, weld_x, depth=15.0) + [0.0]
    before_bottom = elev[3]
    anchors = {0, len(xs) - 1}
    before_kink = abs(
        (elev[4] - elev[3]) / 100.0 - (elev[3] - elev[2]) / 100.0)
    assert before_kink > K_RATE * 100.0 + 1e-6, "fixture must start kinked"
    S._fair_spine_chains(elev, adj, anchors, None, nodes_xy, K_RATE)
    # The corridor triple AT the weld now obeys the K-factor (pre-fix
    # the chain BROKE there, so the pass could not even see the kink and
    # the bottom vertex never moved — the gate-off test proves that).
    g1 = (elev[3] - elev[2]) / 100.0
    g2 = (elev[4] - elev[3]) / 100.0
    assert abs(g2 - g1) <= K_RATE * 100.0 + 1e-4, (
        "the weld triple must obey the vertical-curve rate")
    assert elev[3] > before_bottom, "the V bottom must lift"


def test_gate_off_keeps_the_weld_break(monkeypatch):
    monkeypatch.setattr(config, "SPINE_FAIR_THROUGH_WELDS", False)
    xs = [0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0]
    weld_x = 300.0
    nodes_xy, adj = _line_graph(xs, weld_extra=(weld_x, (300.0, 80.0)))
    elev = _v_profile(xs, weld_x, depth=5.0) + [0.0]
    before = list(elev)
    anchors = {0, len(xs) - 1}
    S._fair_spine_chains(elev, adj, anchors, None, nodes_xy, K_RATE)
    # Legacy behavior: chains break at the weld; each half is a straight
    # line already (zero second difference inside each half), so the V
    # bottom itself never moves.
    assert elev[3] == before[3], "gate off: the weld vertex must not move"


def test_a_true_tee_does_not_fair_around_the_corner(monkeypatch):
    monkeypatch.setattr(config, "SPINE_FAIR_THROUGH_WELDS", True)
    # L-shaped: E-W arm then N-S arm meeting at 90° — deviation 90 >> 30,
    # so no splice; the corner vertex keeps its value.
    nodes_xy = [(0.0, 0.0), (100.0, 0.0), (200.0, 0.0),
                (200.0, 100.0), (200.0, 200.0)]
    adj = {}
    for a, b in ((0, 1), (1, 2), (2, 3), (3, 4)):
        w = math.hypot(nodes_xy[b][0] - nodes_xy[a][0],
                       nodes_xy[b][1] - nodes_xy[a][1])
        adj.setdefault(a, []).append((b, w))
        adj.setdefault(b, []).append((a, w))
    # Make node 2 degree-3 by grafting a stub, so it is a WELD, not a
    # plain degree-2 corner (degree-2 corners stay inside one chain).
    nodes_xy.append((260.0, -60.0))
    d = math.hypot(60.0, 60.0)
    adj.setdefault(2, []).append((5, d))
    adj.setdefault(5, []).append((2, d))
    elev = [0.0, -2.0, -4.0, -2.0, 0.0, -4.0]
    before = list(elev)
    S._fair_spine_chains(elev, adj, set(), None, nodes_xy, K_RATE)
    # The two arms meet at 90°: no splice may fair across node 2 (its
    # value may only move if some spliced chain contains it as interior
    # — which must not happen here).
    assert elev[2] == before[2], (
        "90-degree arms must not fair around the corner")


def test_chord_sag_cap_lifts_the_bowl(monkeypatch):
    """``SPINE_CHORD_MAX_SAG_M`` > 0 floors a chain's interior at
    (chord − cap): the K-factor alone cannot bound a long bowl's
    depth, only its curvature."""
    monkeypatch.setattr(config, "SPINE_FAIR_THROUGH_WELDS", True)
    monkeypatch.setattr(config, "SPINE_CHORD_MAX_SAG_M", 3.0)
    xs = [0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0]
    nodes_xy, adj = _line_graph(xs, weld_extra=(300.0, (300.0, 80.0)))
    elev = _v_profile(xs, 300.0, depth=15.0) + [0.0]
    anchors = {0, len(xs) - 1}
    S._fair_spine_chains(elev, adj, anchors, None, nodes_xy, K_RATE)
    # Chord is 0 → 0, so every interior node must sit at ≥ −3 m minus
    # whatever the subsequent rate sweeps move (they only LIFT a sag
    # centre, never deepen it below the clamp).
    assert min(elev[1:6]) >= -3.0 - 1e-6


def test_chord_sag_cap_off_by_default(monkeypatch):
    monkeypatch.setattr(config, "SPINE_FAIR_THROUGH_WELDS", True)
    monkeypatch.setattr(config, "SPINE_CHORD_MAX_SAG_M", 0.0)
    xs = [0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0]
    nodes_xy, adj = _line_graph(xs, weld_extra=(300.0, (300.0, 80.0)))
    elev = _v_profile(xs, 300.0, depth=15.0) + [0.0]
    anchors = {0, len(xs) - 1}
    S._fair_spine_chains(elev, adj, anchors, None, nodes_xy, K_RATE)
    # Rate-legal residual bowl survives well below any 3 m chord floor.
    assert min(elev[1:6]) < -3.0
