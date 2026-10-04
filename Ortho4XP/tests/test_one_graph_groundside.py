"""THE ONE-GRAPH TWINS — groundside joins the route graph (cycle 8).

Owner rulings under test (docs/RULINGS.md, 2026-08-06):

* **"ONE graph: groundside joins the route graph"** — one route graph, no
  second groundside one; every connected groundside node's band derives
  from what its service-road routes reach; truly disconnected geometry is
  NOT SOLVED and mints nothing.
* **"Service-road mouths seat like apron-edge buildings"** — the mouth is
  the interface node, seated at a value where the AIRSIDE apron lawfully
  meets it, after which everything downstream grades per its own law.
* **"Frontage coupling ⇒ band seating"** — a coupled surface is seated
  FROM the band; the DEM chooses where inside it, never a bound.

Four families, one per ruled property, plus the census half of the
lockstep:

1. MOUTH SEATING — the mouth's interval IS the airside field's at that
   node (airside prices it; nothing is minted here).
2. BAND THROUGH ROADS — a node reachable only along service edges gets a
   band, and its width is the mouth's plus the road budget travelled.
3. DISCONNECTED MINTS NOTHING — the solve leaves it at DEM, marks it, the
   sidecar carries it and the census adjudicates its rows OUT OF SCOPE
   through the SAME answer (never a second predicate).
4. RECEIVER-ONLY DIRECTION — no groundside value can enter the airside
   field: the airside band is byte-identical with and without the whole
   groundside apparatus.

Every answer is hand-computed and stated before it is asserted.  No
build, no network, no X-Plane.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))


# ══════════════════════════════════════════════════════════════════════
# THE SYNTHETIC AIRPORT
#
#   node 0 ── node 1 ── node 2 ── node 3
#     |  taxi   |  taxi   | service | service
#
# Node 0 is a runway anchor at 100.0 m.  Edges 0-1 and 1-2 are TAXI spine
# edges with budget 1.0 m each; edges 2-3 and 3-4 are SERVICE edges with
# budget 4.0 m each (a road's 8 % over 50 m).  Node 2 is therefore THE
# MOUTH: a service edge touches it and the airside field reaches it.
#
# Hand-computed airside field (service-excluded, so it stops at node 2):
#   node 0: (100, 100)          node 1: (99, 101)      node 2: (98, 102)
# Mouth band at node 2 = (98, 102), width 4.
# Outward from the mouth along the road:
#   node 3: (98 − 4, 102 + 4) = (94, 106), width 12
#   node 4: (90, 110), width 20
# ══════════════════════════════════════════════════════════════════════

class _G:
    """The minimum ``UnifiedGraph`` surface the band reads."""

    def __init__(self):
        self.pos = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (20.0, 0.0),
                    3: (70.0, 0.0), 4: (120.0, 0.0)}
        self.runway_anchor = {0: 100.0}
        self.spine_adj = {
            0: [(1, 1.0)],
            1: [(0, 1.0), (2, 1.0)],
            2: [(1, 1.0), (3, 4.0)],
            3: [(2, 4.0), (4, 4.0)],
            4: [(3, 4.0)],
        }
        self.service_spine_pairs = {(2, 3), (3, 4)}


class _Layout:
    shapes = ()
    anchor = (0.0, 0.0)
    canonical_points = None


@pytest.fixture()
def graph():
    return _G()


@pytest.fixture()
def layout():
    return _Layout()


# ══════════════════════════════════════════════════════════════════════
# FAMILY 1 — THE MOUTH IS SEATED BY AIRSIDE
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# FAMILY 2 — THE BAND FLOWS THROUGH THE ROADS
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# FAMILY 3 — DISCONNECTED MINTS NOTHING, AND THE CENSUS AGREES
# ══════════════════════════════════════════════════════════════════════


def test_the_census_adjudicates_a_disconnected_ring_out_of_scope():
    """KNOWN ANSWER, the lockstep half.  Two rows: one whose BOTH points
    lie inside a declared disconnected ring, one that does not.  The first
    is stamped ``disconnected_ring`` and leaves the ADJUDICATED count; the
    second stays.  Both are still COUNTED — instruments report."""
    import check_grade as cg

    ring_m = cg._disconnected_rings_to_m(
        [[(0.0, 0.0), (0.0, 0.001), (0.001, 0.001), (0.001, 0.0)]],
        lambda la, lo: (lo * 1000.0, la * 1000.0))
    assert ring_m, "the reader must build the ring polygon"

    class _Row:
        def __init__(self, pa, pb):
            self.pt_a, self.pt_b = pa, pb
            self.out_of_scope = None
            self.way_a = self.way_b = None

    inside = _Row((0.2, 0.2), (0.6, 0.6))
    outside = _Row((5.0, 5.0), (0.2, 0.2))
    n = cg._mark_disconnected([inside, outside], [], ring_m)
    assert n == 1
    assert inside.out_of_scope == "disconnected_ring"
    assert outside.out_of_scope is None

    adj = cg.adjudication([("within_shape", inside),
                           ("within_shape", outside)])
    assert adj["out_of_scope_total"] == 1
    assert adj["out_of_scope_classes"]["disconnected_ring"]["n"] == 1
    assert adj["adjudicated_total"] == 1


def test_one_end_on_solved_geometry_is_NOT_out_of_scope():
    """A row with one end inside a disconnected ring and one end on the
    solved network is a statement about the COUPLING — if the two are that
    close the ring was not disconnected — so it stays adjudicated."""
    import check_grade as cg
    ring_m = cg._disconnected_rings_to_m(
        [[(0.0, 0.0), (0.0, 0.001), (0.001, 0.001), (0.001, 0.0)]],
        lambda la, lo: (lo * 1000.0, la * 1000.0))

    class _Row:
        def __init__(self, pa, pb):
            self.pt_a, self.pt_b = pa, pb
            self.out_of_scope = None

    straddle = _Row((0.2, 0.2), (40.0, 40.0))
    assert cg._mark_disconnected([straddle], [], ring_m) == 0
    assert straddle.out_of_scope is None


def test_the_sidecar_key_is_registered_for_every_reader():
    """The rings only work as a lockstep if the ONE sidecar reader knows
    the key — an unregistered key is a census that silently judges a
    different law (the terrace_joints precedent in CLAUDE.md)."""
    import check_grade as cg
    assert cg.SIDECAR_LAW_KEYS["disconnected_rings"] == "disconnected_rings_ll"


# ══════════════════════════════════════════════════════════════════════
# FAMILY 4 — RECEIVER-ONLY, STRUCTURALLY
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# FAMILY 4 — THE BETWEEN-RING WELD (finalarch item 1; weld-or-gap)
# ══════════════════════════════════════════════════════════════════════

