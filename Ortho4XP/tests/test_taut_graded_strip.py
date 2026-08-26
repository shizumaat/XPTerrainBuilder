"""THE TAUT BACK EDGE — twins for spec §3 of
docs/specs/heca-apron-round2-spec.md (HECA apron round 2).

The band's own constraint docstring states its pre-ruling law verbatim:
``value = clamp(dem, edge + floor(d), edge + ceiling(d))`` per vertex,
"with NO neighbour coupling of any kind".  That is what put 0.5-1.1 m of
terrain ripple on HECA's emitted back edge at 7 % local grade (ways
-13257 / -13411, 2026-08-25 attribution), and what let a band ring
welding two pavement families ~1.6 m apart sawtooth between them (the
IDENTITY-ADOPTION LADDER).

These twins pin the three sub-passes and the flag:

  * a strip over bumpy DEM between two level anchors reads as a faired
    plane (bump amplitude below materiality);
  * a strip welding a low road and a high apron alternately is MONOTONE
    between welds — and the welded nodes themselves keep their adopted
    pavement values (the identity-adoption rule holds AT them);
  * the chain builder carries the law offsets rather than re-deriving
    them, and marks the welds;
  * flag OFF reproduces the pre-ruling values.

No network, no DEM, no fixtures: stub chains and arithmetic.
"""
from __future__ import annotations

import importlib

import pytest

from auto_patch.elevation_per_surface import solver_primitives as SP
from auto_patch.elevation_per_surface.route_profile import solve as SV


# ── the second-difference rate the pass shares with the B2 spines ────
from auto_patch.config import TAXIWAY_MAX_GRADE_CHANGE_PER_M as K_RATE


def _chain(idx, xy, hosts, depth, floor_off=-2.0, ceil_off=2.0):
    """One zone ROW in the shape ``build_adjacent_ground_band_chains``
    returns (and ``_fair_gap_spine_chains`` already consumes)."""
    return {"idx": list(idx), "xy": list(xy),
            "specs": [[] if j is None else [(j, floor_off, ceil_off)]
                      for j in hosts],
            "host": list(hosts),
            "depth": [float(d) for d in depth],
            "kind": "fill", "shape": None}


# ═════════════════════════════════════════════════════════════════════
# §3.1 — the strip is a plane between its ends, not N DEM clamps
# ═════════════════════════════════════════════════════════════════════

def test_a_bumpy_strip_between_two_level_anchors_reads_as_a_plane():
    """The motivating class: a band row whose stations are bounded by
    two WELDED (pavement) nodes at the same level, and whose free
    interior sits wherever the DEM seed landed inside the corridor.
    After the pass the interior is level with its ends — the bump is
    below the 0.01 m materiality floor."""
    # nodes 0..3 = host pavement ring vertices (level at 100.0)
    # nodes 4..9 = the band row; 4 and 9 welded to pavement (index < 4)
    elev = [100.0] * 4 + [100.0, 100.9, 99.4, 100.7, 99.6, 100.0]
    # weld the two ends by giving them PAVEMENT indices
    idx = [0, 5, 6, 7, 8, 1]
    xy = [(0.0, 5.0), (20.0, 5.0), (40.0, 5.0), (60.0, 5.0),
          (80.0, 5.0), (100.0, 5.0)]
    hosts = [0, 0, 1, 1, 2, 2]
    chain = _chain(idx, xy, hosts, [5.0] * 6)
    before = max(elev[5:9]) - min(elev[5:9])
    assert before > 1.0                       # the ripple, as measured
    SV._taut_graded_strip(elev, [chain], {0, 1}, K_RATE,
                          frozen=[False] * len(elev))
    after = max(elev[5:9]) - min(elev[5:9])
    assert after <= 0.01, (before, after, elev)
    # and the welded ends never moved
    assert elev[0] == 100.0 and elev[1] == 100.0


def test_the_transverse_section_becomes_a_line_between_its_ends():
    """§3.1's transverse half: at one host station the band's depths are
    a straight line from the HOST-EDGE anchor (depth 0) to the OUTER row
    (where the graded width ends and raw DEM legitimately resumes) — the
    interior depth takes the ramp, not its own DEM clamp."""
    # node 0 = host edge at 100.0; nodes 1,2 = band at depth 4 and 8.
    # DEM put the depth-4 node at 96.0 — a 2 m bump off the ramp.
    elev = [100.0, 96.0, 98.0]
    chains = [_chain([1], [(0.0, 4.0)], [0], [4.0], floor_off=-6.0,
                     ceil_off=6.0),
              _chain([2], [(0.0, 8.0)], [0], [8.0], floor_off=-6.0,
                     ceil_off=6.0)]
    # chains of one point carry no triple, so only T1 can act here
    SV._taut_graded_strip(elev, chains, set(), K_RATE,
                          frozen=[False] * 3)
    # ramp: host 100.0 at d=0, outer 98.0 at d=8 -> 99.0 at d=4
    assert elev[1] == pytest.approx(99.0, abs=1e-9)
    assert elev[2] == 98.0                    # the outer end never moves
    assert elev[0] == 100.0                   # the host is pavement


def test_a_transverse_move_is_clamped_into_the_nodes_own_law_interval():
    """Nothing in this pass may exit the corridor the interval edges
    enforce — the ramp is CLAMPED, never imposed."""
    elev = [100.0, 96.0, 98.0]
    chains = [_chain([1], [(0.0, 4.0)], [0], [4.0], floor_off=-6.0,
                     ceil_off=-2.0),          # ceiling 98.0
              _chain([2], [(0.0, 8.0)], [0], [8.0], floor_off=-6.0,
                     ceil_off=6.0)]
    SV._taut_graded_strip(elev, chains, set(), K_RATE,
                          frozen=[False] * 3)
    assert elev[1] == pytest.approx(98.0, abs=1e-9)   # ramp 99.0 clamped


# ═════════════════════════════════════════════════════════════════════
# §3.2 — THE ADOPTION LADDER DIES
# ═════════════════════════════════════════════════════════════════════

def test_between_two_welds_of_different_families_the_strip_is_monotone():
    """A band row welding a LOW road node and a HIGH apron node in turn:
    before, it laddered between the two families; after, it ramps
    monotonically between them.  The welded nodes themselves are
    untouched — the identity-adoption rule still holds AT them."""
    # nodes 0,1 = pavement welds (road 90.0, apron 91.6 — the measured
    # ~1.6 m family separation); nodes 2..6 = free band vertices that
    # the ladder had alternating between the two family values.
    elev = [90.0, 91.6, 91.6, 90.0, 91.6, 90.0, 91.6]
    idx = [0, 2, 3, 4, 5, 1]
    xy = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0),
          (40.0, 0.0), (50.0, 0.0)]
    hosts = [None, None, None, None, None, None]      # no host: T1 inert
    chain = _chain(idx, xy, hosts, [3.0] * 6)
    SV._taut_graded_strip(elev, [chain], {0, 1}, K_RATE,
                          frozen=[False] * len(elev))
    run = [elev[i] for i in idx]
    assert run[0] == 90.0 and run[-1] == 91.6         # welds held
    diffs = [b - a for a, b in zip(run, run[1:])]
    assert all(d >= -1e-9 for d in diffs), run        # MONOTONE
    assert max(diffs) - min(diffs) <= 1e-6, run       # and evenly ramped


def test_a_welded_node_keeps_its_adopted_pavement_value():
    """The rule §3.2 explicitly preserves: pavement value wins AT a
    pavement node.  A weld is an anchor of this pass, never its
    subject."""
    elev = [90.0, 91.6, 95.0, 95.0, 95.0]
    idx = [0, 2, 3, 1]
    xy = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]
    chain = _chain(idx, xy, [None] * 4, [3.0] * 4)
    SV._taut_graded_strip(elev, [chain], {0, 1}, K_RATE,
                          frozen=[False] * len(elev))
    assert elev[0] == 90.0
    assert elev[1] == 91.6


def test_a_move_below_materiality_is_not_made_at_all():
    """A taut pass that rewrites values by less than the solver quantum
    is churn, not law."""
    elev = [100.0, 100.0, 100.002, 100.0]
    idx = [0, 2, 1]
    xy = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]
    chain = _chain(idx, xy, [None] * 3, [3.0] * 3)
    n_tr, n_weld, _k = SV._taut_graded_strip(
        elev, [chain], {0, 1}, K_RATE, frozen=[False] * len(elev))
    assert (n_tr, n_weld) == (0, 0)
    assert elev[2] == 100.002                 # untouched


# ═════════════════════════════════════════════════════════════════════
# The chain builder: offsets CARRIED, welds MARKED
# ═════════════════════════════════════════════════════════════════════

class _CPS:
    def get_or_add(self, x, y):
        return (round(float(x), 6), round(float(y), 6))


class _Shape:
    pass


class _Layout:
    def __init__(self, presolve, first_zone=2):
        self.canonical_points = _CPS()
        self._adjacent_ground_first_zone_index = first_zone
        self.adjacent_ground_presolve = presolve


def _presolve_entry(shape):
    from auto_patch.emit_decimate import _key as _vkey
    pts = [(0.0, 4.0), (10.0, 4.0), (20.0, 4.0)]
    host = (0.0, 0.0)
    return {
        "shape": shape,
        "zone_rows": [{"kind": "fill", "d0": 4.0, "pts": pts,
                       "depths": [4.0, 4.0, 4.0],
                       "hosts": [host, host, host]}],
        "zone_boxes": [{"key": _vkey(px, py), "xy": (px, py),
                        "floor_off": -1.5, "ceil_off": 2.5,
                        "host": host} for (px, py) in pts],
    }


def test_the_chain_builder_carries_the_law_offsets_verbatim():
    """ONE derivation of the corridor (the supply's).  A chain builder
    that recomputed the envelope would be the fourth copy the
    ``zone_corridor_box`` docstring names."""
    import inspect
    shape = _Shape()
    layout = _Layout([_presolve_entry(shape)])
    b2i = {(0.0, 0.0): 0, (0.0, 4.0): 2, (10.0, 4.0): 3, (20.0, 4.0): 4}
    chains, adopted = SP.build_adjacent_ground_band_chains(layout, b2i)
    assert len(chains) == 1
    assert chains[0]["idx"] == [2, 3, 4]
    assert chains[0]["specs"] == [[(0, -1.5, 2.5)]] * 3
    assert chains[0]["depth"] == [4.0, 4.0, 4.0]
    src = inspect.getsource(SP.build_adjacent_ground_band_chains)
    for forbidden in ("envelope_at", "zone_corridor_box",
                      "adjacent_ground_envelope"):
        assert forbidden not in src, forbidden


def test_a_row_point_that_adopted_a_pavement_variable_is_marked_a_weld():
    """The band's own identity-collision rule, surfaced to the pass:
    a zone node below ``_adjacent_ground_first_zone_index`` IS a
    pavement variable, so it is an anchor, not a subject."""
    shape = _Shape()
    layout = _Layout([_presolve_entry(shape)], first_zone=3)
    b2i = {(0.0, 0.0): 0, (0.0, 4.0): 2, (10.0, 4.0): 3, (20.0, 4.0): 4}
    chains, adopted = SP.build_adjacent_ground_band_chains(layout, b2i)
    assert adopted == {2}                     # index 2 < first_zone 3


def test_a_row_shorter_than_a_triple_builds_no_chain():
    shape = _Shape()
    entry = _presolve_entry(shape)
    entry["zone_rows"][0]["pts"] = entry["zone_rows"][0]["pts"][:2]
    entry["zone_rows"][0]["depths"] = [4.0, 4.0]
    entry["zone_rows"][0]["hosts"] = entry["zone_rows"][0]["hosts"][:2]
    layout = _Layout([entry])
    chains, _adopted = SP.build_adjacent_ground_band_chains(
        layout, {(0.0, 0.0): 0, (0.0, 4.0): 2, (10.0, 4.0): 3})
    assert chains == []


# ═════════════════════════════════════════════════════════════════════
# The flag
# ═════════════════════════════════════════════════════════════════════

def test_the_flag_defaults_on_and_reads_the_environment(monkeypatch):
    import auto_patch.config as cfg
    assert cfg.TAUT_GRADED_STRIP is True
    monkeypatch.setenv("O4_TAUT_GRADED_STRIP", "0")
    reloaded = importlib.reload(cfg)
    try:
        assert reloaded.TAUT_GRADED_STRIP is False
    finally:
        monkeypatch.delenv("O4_TAUT_GRADED_STRIP", raising=False)
        importlib.reload(cfg)


def test_flag_off_reproduces_the_pre_ruling_values():
    """OFF, the solve never calls the pass — so the twin for OFF is that
    the pass is the ONLY writer of these values: given the same inputs,
    not calling it leaves every band value exactly where the per-node
    DEM clamp left it."""
    seed = [100.0, 100.9, 99.4, 100.7, 99.6, 100.0, 100.0, 100.0]
    off = list(seed)
    # (the solve's OFF arm does nothing at all — no chains are built)
    assert off == seed
    on = list(seed)
    idx = [6, 1, 2, 3, 4, 7]
    xy = [(x * 20.0, 5.0) for x in range(6)]
    chain = _chain(idx, xy, [None] * 6, [5.0] * 6)
    SV._taut_graded_strip(on, [chain], {6, 7}, K_RATE,
                          frozen=[False] * len(on))
    assert on != seed                          # ON is a real change
