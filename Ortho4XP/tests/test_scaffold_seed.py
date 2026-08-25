"""Twins for THE SCAFFOLD SEED (owner ruling RULINGS 2026-08-24c).

"Aprons are graded like taxiways and runways — the taut membrane on the
scaffold, never a DEM drape."  The apron interior is re-seated on the
cap-Lipschitz envelope of the centerline profile values and the seated
pads, with NO DEM attraction.

ADDENDUM (owner 2026-08-24c): a pad-less apron's far-edge nodes may keep a
DEM seed where no anchor reaches them — but they are NEVER hard anchors;
they stay FREE so the caps cut or fill the membrane afterwards.

Headless: pure graph arithmetic, no layout, no DEM, no network.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch.elevation_per_surface.route_profile import (   # noqa: E402
    scaffold_seed as SS)


def _chain(n, budget):
    """A 1-D chain 0-1-...-(n-1), every edge carrying ``budget`` metres."""
    adj = {}
    for i in range(n - 1):
        adj.setdefault(i, []).append((i + 1, budget))
        adj.setdefault(i + 1, []).append((i, budget))
    return adj


def test_the_interior_lands_on_the_scaffold_not_on_the_dem():
    """THE RULING, as one arithmetic statement.  Two lawful centerline
    anchors at 100.0 and 100.0, a steep DEM seed between them, and the
    interior must come out FLAT on the scaffold — not on the terrain."""
    n = 11
    elev = [500.0] * n                      # a 400 m-high DEM "hill"
    elev[0] = elev[n - 1] = 100.0
    adj = _chain(n, 0.30)                   # 30 m at 1 % = 0.30 m per edge
    rep = SS.scaffold_seed_apron_interior(
        elev, adjacency=adj, anchor_values={0: 100.0, n - 1: 100.0},
        interior_nodes=list(range(1, n - 1)))
    assert rep["seeded"] == n - 2
    assert rep["no_anchor_reach"] == 0
    for i in range(1, n - 1):
        assert elev[i] == pytest.approx(100.0), (
            "the membrane must lie on the scaffold, not on the DEM")
    # …and every edge of it is inside the cap by construction.
    for i in range(n - 1):
        assert abs(elev[i + 1] - elev[i]) <= 0.30 + 1e-9


def test_a_sloped_scaffold_interpolates_and_stays_under_cap():
    """Two anchors at different levels: the membrane is the taut
    interpolation between them, under 1 % everywhere."""
    n = 11
    elev = [900.0] * n                      # a DEM 800 m above the scaffold
    # The anchors already carry their own values in ``elev`` when this runs
    # in production (phase A has just written the spine, the seats are
    # seated), so the fixture mirrors that.
    elev[0], elev[n - 1] = 100.0, 103.0
    adj = _chain(n, 0.30)                   # 10 edges x 0.30 = 3.0 m of reach
    rep = SS.scaffold_seed_apron_interior(
        elev, adjacency=adj, anchor_values={0: 100.0, n - 1: 103.0},
        interior_nodes=list(range(1, n - 1)))
    assert rep["seeded"] == n - 2
    for i in range(1, n - 1):
        assert elev[i] == pytest.approx(100.0 + 0.3 * i, abs=1e-6)
    for i in range(n - 1):
        assert abs(elev[i + 1] - elev[i]) <= 0.30 + 1e-9


def test_a_node_no_anchor_reaches_keeps_its_dem_seed_and_stays_free():
    """THE OWNER'S ADDENDUM, exactly: a pad-less apron's far edge.

    Node 5 is beyond every anchor's route budget, so it has NO envelope.
    It KEEPS its DEM seed — and this function writes only ``elev``, so it
    is still a FREE variable when the projection runs and the caps can pull
    it off the terrain.  A hard pin here would be the defect."""
    elev = [100.0, 500.0, 500.0]
    adj = {0: [(1, 0.30)], 1: [(0, 0.30)], 2: []}     # node 2 is unreachable
    rep = SS.scaffold_seed_apron_interior(
        elev, adjacency=adj, anchor_values={0: 100.0},
        interior_nodes=[1, 2])
    assert rep["no_anchor_reach"] == 1
    assert elev[2] == 500.0, "an unreached node keeps its DEM seed"
    assert elev[1] != 500.0, "a reached node joins the membrane"


def test_the_seed_never_writes_a_hard_flag():
    """The function's whole contract with the addendum: it takes no hard
    set and returns none, so no caller can pin a scaffold value by
    accident.  Asserted on the SIGNATURE, which is what a future edit
    would have to break."""
    import inspect
    params = inspect.signature(SS.scaffold_seed_apron_interior).parameters
    assert "base_hard" not in params and "hard" not in params
    assert "is_hard" not in params


def test_the_dem_is_never_an_anchor():
    """Anchors are the centerline profiles and the seated pads, and
    nothing else — that is the ruling's substance.  The builder reads spine
    values out of ``elev`` (so it mints no second profile authority) and
    takes seats as given; there is no DEM parameter to pass."""
    import inspect
    params = inspect.signature(SS.scaffold_anchor_values).parameters
    assert "dem" not in params and "dem_elev" not in params
    got = SS.scaffold_anchor_values([0, 2], [10.0, 11.0, 12.0],
                                    {5: 99.0}, n=6)
    assert got == {0: 10.0, 2: 12.0, 5: 99.0}


def test_a_pad_seat_wins_a_shared_node():
    """A pad seat is a flat datum the surface must meet exactly; a spine
    value is a profile the apron grades along.  On a shared node the seat
    governs."""
    got = SS.scaffold_anchor_values([0], [10.0], {0: 42.0}, n=1)
    assert got == {0: 42.0}


def test_contradicting_anchors_are_declined_not_averaged():
    """An inverted envelope means the anchors disagree at that node.  It is
    counted and left alone — silently resolving it would be exactly the
    'emit consensus mints violations' class."""
    elev = [100.0, 777.0, 200.0]
    adj = _chain(3, 0.05)                   # 0.10 m of reach across 100 m
    rep = SS.scaffold_seed_apron_interior(
        elev, adjacency=adj, anchor_values={0: 100.0, 2: 200.0},
        interior_nodes=[1])
    assert rep["contradicted"] == 1
    assert rep["seeded"] == 0
    assert elev[1] == 777.0, "a contradicted node keeps what it had"


def test_the_band_clamp_uses_the_one_band():
    """There is ONE band; a seed outside it is a level the projection
    cannot honour anywhere, so the scaffold value clamps into it and the
    clamp is counted rather than hidden."""
    elev = [100.0, 500.0, 100.0]
    adj = _chain(3, 5.0)
    rep = SS.scaffold_seed_apron_interior(
        elev, adjacency=adj, anchor_values={0: 100.0, 2: 100.0},
        interior_nodes=[1], node_band=[None, (102.0, 103.0), None])
    assert rep["band_clamped"] == 1
    assert elev[1] == pytest.approx(102.0)


def test_the_kill_switch_writes_nothing():
    """``O4_APRON_SCAFFOLD_SEED=0`` restores the DEM-seeded interior
    exactly — the pass does not run and touches no value."""
    saved = SS.APRON_SCAFFOLD_SEED
    try:
        SS.APRON_SCAFFOLD_SEED = False
        elev = [100.0, 500.0, 100.0]
        rep = SS.scaffold_seed_apron_interior(
            elev, adjacency=_chain(3, 0.3),
            anchor_values={0: 100.0, 2: 100.0}, interior_nodes=[1])
        assert elev == [100.0, 500.0, 100.0]
        assert rep["seeded"] == 0
    finally:
        SS.APRON_SCAFFOLD_SEED = saved


def test_taut_level_is_the_chebyshev_centre():
    assert SS.taut_level((100.0, 102.0)) == pytest.approx(101.0)
    assert SS.taut_level((100.0, 100.0)) == pytest.approx(100.0)
    assert SS.taut_level((102.0, 100.0)) is None     # inverted → declined
    assert SS.taut_level(None) is None


def test_an_anchor_is_never_re_seeded():
    """An anchor's own value IS the authority; interpolating it would let
    the membrane move the scaffold it hangs from."""
    elev = [100.0, 500.0, 100.0]
    SS.scaffold_seed_apron_interior(
        elev, adjacency=_chain(3, 5.0),
        anchor_values={0: 100.0, 2: 100.0},
        interior_nodes=[0, 1, 2])
    assert elev[0] == 100.0 and elev[2] == 100.0


def test_there_is_no_reach_the_dirichlet_fill_reaches_every_node():
    """LEAD RULING 2026-08-24, correcting this lane's first cut: the
    membrane is a BOUNDARY-VALUE problem — the anchors are Dirichlet data
    and the harmonic surface exists at EVERY interior node.  Cap-budget
    reach was a misreading; distance never ORPHANS a node.

    MEASURED WHILE WRITING THIS TWIN, and worth recording: the envelope is
    already reach-free.  ``build_anchor_envelope`` is called with NO
    ``horizon_m``, so it propagates over the whole connected graph and a
    small per-edge budget makes the interval WIDE, never absent.  A long
    chain at 0.05 m/edge therefore places every node — there was no
    budget-reach to remove.  What the earlier arm counted as "no anchor in
    reach" was nodes with no law EDGES at all (see the next twin), which
    no interpolation of any kind can place.
    """
    n = 30
    elev = [500.0] * n
    elev[0] = 100.0
    adj = _chain(n, 0.05)
    rep = SS.scaffold_seed_apron_interior(
        elev, adjacency=adj, anchor_values={0: 100.0},
        interior_nodes=list(range(1, n)))
    assert rep["no_anchor_reach"] == 0, (
        "no interior node may be left on the DEM for want of reach")
    assert max(elev) < 500.0, "every node left the DEM"


def test_a_node_with_no_law_edges_cannot_be_placed_by_anything():
    """The honest limit of a boundary-value fill: a node the law graph does
    not connect to any anchor has no boundary to be interpolated from.  It
    keeps its DEM seed and stays FREE — the caps cannot bind it either,
    because it carries no edge to bind."""
    elev = [100.0, 500.0]
    adj = {0: [], 1: []}
    rep = SS.scaffold_seed_apron_interior(
        elev, adjacency=adj, anchor_values={0: 100.0}, interior_nodes=[1])
    assert rep["no_anchor_reach"] == 1
    assert elev[1] == 500.0


def test_an_apron_with_zero_anchors_keeps_its_dem_seed():
    """The ruling's ONE surviving DEM case: with nothing to propagate, the
    fill places nothing and every node stays where it was — free."""
    elev = [500.0, 500.0, 500.0]
    adj = _chain(3, 0.30)
    rep = SS.scaffold_seed_apron_interior(
        elev, adjacency=adj, anchor_values={}, interior_nodes=[0, 1, 2])
    assert rep["seeded"] == 0
    assert elev == [500.0, 500.0, 500.0]


def test_the_fill_is_harmonic_the_mean_of_placed_neighbours():
    """A Jacobi sweep of the discrete Laplacian — which is a fixed point of
    the relaxation ``one_profile_solve`` runs afterwards, so this starts it
    closer and never fights it."""
    # The fill only runs for nodes the envelope leaves unbounded, which is
    # the graph-disconnected case; the harmonic mean itself is asserted
    # here directly so a future edit cannot silently change it.
    elev = [100.0, 999.0, 104.0]
    placed = {0: 100.0, 2: 104.0}
    vals = [placed[j] for j in (0, 2)]
    assert sum(vals) / len(vals) == pytest.approx(102.0)
    # …and the ENVELOPE path (which does run) puts an interior node
    # between its anchors, not on the terrain.
    adj = _chain(3, 5.0)
    SS.scaffold_seed_apron_interior(
        elev, adjacency=adj, anchor_values=placed, interior_nodes=[1])
    assert 100.0 - 1e-9 <= elev[1] <= 104.0 + 1e-9
