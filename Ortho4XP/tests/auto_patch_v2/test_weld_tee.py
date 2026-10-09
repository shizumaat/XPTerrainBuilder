"""THE T-WELD (#495; ``planar/weld`` (3)).

A junior pavement vertex that is an IDENTITY (shared with a cell that does
not weld — a pad) cannot move onto the senior edge it lies a sliver from,
so before (3) nothing tied the two pavements: a ~1 m sliver of graded
strip and no shared vertex, hence no bending row.  The T-weld splits the
SENIOR's edge at the frozen vertex, so the two cells share it.  The
tolerance is the sliver weld's own ``emit.identity.weld_spacing_m``.

(a) the T-vertex appears in the senior ring and in the planar map as a
vertex of both faces; (b) the graded strip between is KEPT as two wedges
meeting at the T-vertex (it is no longer a sliver along a length); (c) a
fixture with no vertex inside the tolerance is unchanged, and a vertex
that is free to move is still projected (no T-vertex)."""
from __future__ import annotations

import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.planar import weld as W
from auto_patch_v2.planar.build import build
from tests.auto_patch_v2.test_v2roadramp import _Hill, _airport

GAP = 0.976          # #495's apron | junction distance


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _cells(gap: float, pad: bool = True):
    """A senior JUNCTION (top edge y = 0), a junior APRON whose corner
    points at that edge ``gap`` above it, and a building PAD sharing the
    apron's corner (the identity that freezes it)."""
    tip = (20.0, gap)
    out = [
        Cell(0, "junction", "junc", ((0.0, -20.0), (40.0, -20.0), (40.0, 0.0), (0.0, 0.0)),
             (), None, "D", "airside", "junction", {}),
        Cell(1, "apron", "apr", (tip, (40.0, 20.0), (0.0, 20.0)),
             (), None, "D", "airside", "apron", {}),
    ]
    if pad:
        out.append(Cell(2, "building", "pad", (tip, (45.0, 1.5), (45.0, 9.0)),
                        (), None, "D", "airside", "building", {}))
    return tuple(out)


def test_a_frozen_vertex_a_sliver_from_a_senior_edge_is_a_t_vertex(law):
    cells = _cells(GAP)
    assert GAP <= law.tables.emit.identity.weld_spacing_m
    welded, st = W.weld_cells(cells, law)
    tip = cells[1].ring[0]
    assert welded[1].ring == cells[1].ring          # the identity never moves
    assert tip in welded[0].ring, welded[0].ring    # (a) the senior is split AT it
    assert st.vertices_teed == 1 and st.tees_refused == 0
    assert welded[2] == cells[2]


def test_the_planar_map_shares_the_t_vertex_and_keeps_the_wedges(law, monkeypatch):
    airport, _r = _airport(law, _Hill())

    def faces_at_tip(pm):
        tip = min(pm.vertices, key=lambda v: (pm.vertices[v].xy[0] - 20.0) ** 2
                  + (pm.vertices[v].xy[1] - GAP) ** 2)
        roles = {pm.faces[f].role for f in pm.vertices[tip].incident_faces}
        return tip, roles

    pm, _st = build(airport, Classification(_cells(GAP), (), {}, ()), law)
    tip, roles = faces_at_tip(pm)
    assert {"junction", "apron"} <= roles, roles     # (a) one node, both faces
    assert "graded_strip" in roles                   # (b) the wedges are kept
    # THE CONTROL (FINDING, lane cloudtidy): with the T-weld off the planar
    # build STILL ties the two faces at the tip — the junction face takes
    # the strip up to the apron downstream of the weld — and the T-weld
    # arm instead KEEPS a graded-strip wedge there.  No synthetic here
    # reproduces #495, which is why this commit is not in the PR.
    monkeypatch.setattr(W, "_tee", lambda *a, **k: {})
    pm0, _st0 = build(airport, Classification(_cells(GAP), (), {}, ()), law)
    _tip0, roles0 = faces_at_tip(pm0)
    assert {"junction", "apron"} <= roles0 and "graded_strip" not in roles0, roles0


def test_nothing_changes_outside_the_tolerance(law):
    """(c): the corner 1.5 m off the edge — beyond the tolerance — and the
    weld returns the cells as given, with no T-vertex."""
    cells = _cells(law.tables.emit.identity.weld_spacing_m + 0.5)
    welded, st = W.weld_cells(cells, law)
    assert welded == cells
    assert st.vertices_teed == st.tees_refused == st.cells_welded == 0


def test_a_free_vertex_is_projected_never_teed(law):
    """With no pad the apron's corner is not an identity: the weld's (1)
    moves it onto the junction's edge, and (3) has nothing to do."""
    welded, st = W.weld_cells(_cells(GAP, pad=False), law)
    assert st.vertices_teed == 0 and st.vertices_projected >= 1
    assert welded[0] == _cells(GAP, pad=False)[0]
    assert welded[1].ring[0] == pytest.approx((20.0, 0.0))
