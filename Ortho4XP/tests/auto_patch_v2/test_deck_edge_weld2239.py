"""#2239 / #2241: every vertex on a deck's end EDGE, corner to corner, is a
station of its end line (``constraints/deck_edge_weld``; owner 2026-11-26
"the weld must span the deck's full width including shoulders")."""
from __future__ import annotations

import types

from auto_patch_v2.constraints.deck_edge_weld import edge_vertices

RING = [(0.0, 0.0), (68.0, 0.0), (68.0, 28.0), (0.0, 28.0)]
LINE = [(float(x), 0.0) for x in range(10, 61, 5)]


def _planar(points, roles=None):
    roles = roles or {}
    return types.SimpleNamespace(
        vertices={v: types.SimpleNamespace(xy=p) for v, p in points.items()},
        roles_at=lambda v: roles.get(v, ("primary_parallel",)))


def test_the_shoulder_and_the_pavement_between_stations_are_welded():
    pts = {1: (2.0, 0.1), 2: (33.0, -0.2), 3: (12.0, 0.0), 4: (2.0, 1.5), 5: (40.0, 0.0),
           6: (66.0, 0.2)}
    deck = types.SimpleNamespace(ring=RING)
    e = types.SimpleNamespace(deck=deck, line=LINE, depth=7.5, tops=())
    got = edge_vertices(_planar(pts, {5: ("tunnel_ramp",)}), [e], 0.35,
                        frozenset({"tunnel_ramp"}), {3})
    # the shoulder past the pavement (1, 6) and pavement between stations (2)
    # are welded; a station (3), a floor vertex (5) and one off the edge (4) not
    assert set(got) == {1, 2, 6}
    assert all(k == 0 and d == 7.5 for k, d in got.values())


def test_a_slab_falling_along_its_line_is_read_along_the_edge():
    pts = {1: (10.0, 0.0), 2: (60.0, 0.0), 3: (0.0, 0.0), 4: (68.0, 0.0)}
    deck = types.SimpleNamespace(ring=RING)
    e = types.SimpleNamespace(deck=deck, line=LINE, depth=7.5, tops=((1, 7.0), (2, 8.0)))
    got = edge_vertices(_planar(pts), [e], 0.35, frozenset(), {1, 2})
    assert abs(got[3][1] - 6.8) < 1e-9 and abs(got[4][1] - 8.16) < 1e-9


def test_a_welded_vertex_sheds_its_dem_pin():
    from auto_patch_v2.constraints.edge_deck import _edge_rows, release_governed
    from auto_patch_v2.model.constraints import Pin, Source
    rows = _edge_rows("o", [(((1, 0.5), (2, 0.5)), 7.5)], 0.04, [None], None, {9: (0, 7.5)})
    (r,) = rows
    assert r.terms[0] == (9, 1.0) and abs(r.lo + 0.04) < 1e-12 and abs(r.hi - 0.04) < 1e-12
    dem = Pin(9, 164.6, Source("structures", "tunnel.object.plate_datum = ground", ("t",)))
    assert release_governed([*rows, dem]) == rows
