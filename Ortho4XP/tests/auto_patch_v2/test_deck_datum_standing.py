"""Twin of ``emit/rebake.deck_datum_from_surface`` (spec §60 (9) R2): the
object stage's deck datum reads STANDING cells only — a vertex only gap
pieces own is not read; a piece's vertex shared with a standing cell is."""
from __future__ import annotations

import types

from auto_patch_v2.emit.rebake import deck_datum_from_surface, standing_vertex_ids

RING = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def _to_xy(lon, lat):
    return lon, lat


def _surface(verts, faces):
    return types.SimpleNamespace(
        vertices=[types.SimpleNamespace(id=i, ll=(y, x), z=z)
                  for i, (x, y, z) in enumerate(verts)],
        faces=[types.SimpleNamespace(ref=ref, ring=tuple(ring), holes=tuple(holes))
               for ref, ring, holes in faces])


VERTS = [(1.0, 1.0, 3.63), (5.0, 1.0, 3.63), (5.0, 5.0, 3.63),      # 0-2 a piece's own
         (9.0, 9.0, 4.61), (9.0, 5.0, 4.61), (5.0, 9.0, 4.61),      # 3-5 a pad's
         (50.0, 50.0, 0.0)]                                          # 6 far away


def test_a_ring_over_gap_only_vertices_founds_no_datum():
    s = _surface(VERTS[:3] + VERTS[6:], [("gap:13", (0, 1, 2), ())])
    assert deck_datum_from_surface(s, RING, _to_xy) is None       # main's reading: end lines
    assert standing_vertex_ids(s) == {3}                          # an unowned vertex stands
    assert deck_datum_from_surface(_surface(VERTS[:3], []), RING, _to_xy) == 3.63


def test_a_datum_is_the_standing_cells_median_whatever_pieces_lie_under_the_deck():
    pad = ("building9", (3, 4, 5), ())
    with_piece = _surface(VERTS, [pad, ("gap:13/s0/lot", (0, 1, 2), ())])
    assert deck_datum_from_surface(with_piece, RING, _to_xy) == 4.61
    assert deck_datum_from_surface(_surface(VERTS, [pad]), RING, _to_xy) == 4.61 - 0.49  # all six read
    # a §59 apron part is a standing apron cell, and a vertex a piece SHARES
    # with a standing cell (a ring or a hole) is that cell's
    s = _surface(VERTS, [("gapapron:1", (0, 1, 2), ()), ("gap:2", (2, 3, 4), ())])
    assert standing_vertex_ids(s) == {0, 1, 2, 5, 6}
    s = _surface(VERTS, [("gap:2", (0, 1, 2), ()), ("pav7", (3, 4, 5), ((0, 1, 2),))])
    assert standing_vertex_ids(s) == {0, 1, 2, 3, 4, 5, 6}
