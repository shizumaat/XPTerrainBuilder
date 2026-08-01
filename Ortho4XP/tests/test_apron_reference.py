"""Apron reference surface R — spec ``docs/specs/
apron-string-and-scheduling-spec.md`` B.4.

These pin the two mathematical claims the spec makes about R:

* the minimum-DIRICHLET-energy surface (squared gradient, ``1/d`` edge
  weights) restricted to a 1-D chain between two anchors IS the straight
  chord — the owner's ruling, and the reason revision 1's L1 form was
  rejected as degenerate (L1 ties every monotone profile);
* the POCS pass projects onto the per-edge cap slabs and leaves an
  anchor-vs-anchor contradiction alone (that belongs to the break-region
  quarantine, not to R).
"""
import math

from auto_patch.elevation_per_surface.apron_reference import (
    _dirichlet_solve, _gauss_seidel, _pocs_slabs)


def _chain(spacings):
    """Adjacency for a 1-D chain of ``len(spacings) + 1`` nodes."""
    adjacency = {}
    for k, d in enumerate(spacings):
        w = 1.0 / d
        adjacency.setdefault(k, []).append((k + 1, w))
        adjacency.setdefault(k + 1, []).append((k, w))
    return adjacency


def test_dirichlet_between_two_anchors_is_the_straight_chord():
    # uneven spacing on purpose: a chord is linear in DISTANCE, and only
    # the 1/d weighting reproduces that (uniform weights would space the
    # values evenly per NODE instead).
    spacings = [10.0, 40.0, 25.0, 5.0]
    total = sum(spacings)
    adjacency = _chain(spacings)
    fixed = {0: 100.0, 4: 110.0}
    z = _dirichlet_solve([1, 2, 3], adjacency, fixed)
    run = 0.0
    for k, d in enumerate(spacings[:-1]):
        run += d
        expected = 100.0 + 10.0 * (run / total)
        assert abs(z[k + 1] - expected) < 1e-9, (k, z, expected)


def test_gauss_seidel_fallback_agrees_with_the_direct_solve():
    spacings = [10.0, 40.0, 25.0, 5.0]
    adjacency = _chain(spacings)
    fixed = {0: 100.0, 4: 110.0}
    direct = _dirichlet_solve([1, 2, 3], adjacency, fixed)
    relaxed = _gauss_seidel([1, 2, 3], adjacency, fixed)
    for i in direct:
        assert abs(direct[i] - relaxed[i]) < 1e-3


def test_dirichlet_is_flat_when_every_anchor_is_level():
    """Flat is the PREFERENCE: level anchors ⇒ a level surface, whatever
    the graph shape (this is what an apron 'wants to be flat' means)."""
    adjacency = {}
    for (a, b, d) in ((0, 1, 12.0), (1, 2, 30.0), (2, 3, 7.0),
                      (3, 0, 19.0), (0, 2, 22.0), (1, 4, 9.0),
                      (4, 3, 14.0)):
        adjacency.setdefault(a, []).append((b, 1.0 / d))
        adjacency.setdefault(b, []).append((a, 1.0 / d))
    fixed = {0: 87.5, 3: 87.5}
    z = _dirichlet_solve([1, 2, 4], adjacency, fixed)
    for value in z.values():
        assert abs(value - 87.5) < 1e-9


def test_pocs_enforces_the_cap_slab_and_splits_between_free_ends():
    z = {1: 0.0, 2: 10.0}
    stuck = _pocs_slabs(z, {}, [(1, 2, 4.0)])
    assert stuck == 0
    assert abs(abs(z[1] - z[2]) - 4.0) < 1e-3
    # minimum displacement: the excess splits evenly between two free ends
    assert abs(z[1] - 3.0) < 1e-3 and abs(z[2] - 7.0) < 1e-3


def test_pocs_moves_only_the_free_end_against_an_anchor():
    z = {1: 0.0}
    fixed = {2: 10.0}
    _pocs_slabs(z, fixed, [(1, 2, 4.0)])
    assert abs(z[1] - 6.0) < 1e-3


def test_pocs_reports_an_anchor_contradiction_instead_of_moving_anchors():
    """Both ends anchored and over cap = a genuine anchor contradiction.
    R must NOT resolve it (owner: those surface as break regions)."""
    fixed = {1: 0.0, 2: 10.0}
    z = {}
    stuck = _pocs_slabs(z, fixed, [(1, 2, 4.0)])
    assert stuck == 1
    assert fixed == {1: 0.0, 2: 10.0}


def test_pocs_converges_on_a_chain_that_needs_the_whole_budget():
    """Two anchors 3 m apart over a 3-hop chain at 1 m per hop: the
    Dirichlet chord already rides the cap and POCS is a no-op."""
    spacings = [100.0, 100.0, 100.0]
    adjacency = _chain(spacings)
    fixed = {0: 0.0, 3: 3.0}
    z = _dirichlet_solve([1, 2], adjacency, fixed)
    slabs = [(0, 1, 1.0), (1, 2, 1.0), (2, 3, 1.0)]
    stuck = _pocs_slabs(z, fixed, slabs)
    assert stuck == 0
    values = [fixed[0], z[1], z[2], fixed[3]]
    for a, b in zip(values, values[1:]):
        assert abs(b - a) <= 1.0 + 1e-3
    assert abs(z[1] - 1.0) < 1e-6 and abs(z[2] - 2.0) < 1e-6


def test_isolated_free_node_does_not_blow_up():
    adjacency = {}
    z = _dirichlet_solve([7], adjacency, {})
    assert math.isfinite(z[7])
