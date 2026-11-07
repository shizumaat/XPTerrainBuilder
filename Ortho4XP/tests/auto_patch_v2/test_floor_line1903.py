"""#1903 fix 3: a signature-B shell's trench FLOOR is the object's own floor
per station — its plate where level, its ramp where it climbs to a portal —
never one level read at the object's zero and held to its ends (EGLL
``3a.obj``: −5.00 under its zero, rising to +0.02 at both portals; the flat
cut seated the whole tunnel 3.4 m down onto it and hung its walls 5 m under
the cut)."""
from __future__ import annotations

import numpy as np
import pytest
from auto_patch_v2.airport import obj8, object_cut
from auto_patch_v2.airport.tunnel_objects import _floor_profile
from auto_patch_v2.law import Law
from shapely.geometry import LineString


@pytest.fixture(scope="module")
def law():
    return Law.load()


def _geom(quads):
    verts, tris = [], []
    for q in quads:
        base = len(verts)
        verts.extend(q)
        tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    t = np.asarray(tris, dtype=np.int64)
    return obj8.ObjGeometry("shell.obj", np.asarray(verts, float), t,
                            np.full(t.shape[0], obj8.HARD_DECK, dtype=np.int64),
                            np.zeros((0, 3), dtype=np.int64))


def _ramped_shell(L=120.0, W=30.0, y=-5.0, ramp=30.0):
    """A trench whose floor ramps from grade at x = 0 down to ``y`` over
    ``ramp`` metres, runs level, and ramps back to grade at x = L — walled
    on both long sides to the floor's own depth."""
    a, b = ramp, L - ramp
    quads = [[(0.0, 0.0, 0.0), (a, y, 0.0), (a, y, W), (0.0, 0.0, W)],
             [(a, y, 0.0), (b, y, 0.0), (b, y, W), (a, y, W)],
             [(b, y, 0.0), (L, 0.0, 0.0), (L, 0.0, W), (b, y, W)]]
    for z in (0.0, W):
        quads.append([(0.0, y, z), (L, y, z), (L, 0.0, z), (0.0, 0.0, z)])
    return quads


def test_the_reading_keeps_the_floor_faces(law):
    g = _geom(_ramped_shell())
    r = object_cut.shell_reading(g, obj8.solid_components(g), law)
    assert not isinstance(r, str), r
    assert r.floor_y == pytest.approx(-5.0)
    assert r.floor_faces is not None and r.floor_faces.shape[1:] == (3, 3)


def test_a_hanging_cover_states_no_floor_faces(law):
    g = _geom(_ramped_shell())
    r = object_cut.shell_reading(g, obj8.solid_components(g), law, floor_y=-5.0)
    assert not isinstance(r, str), r
    assert r.floor_faces is None


def test_the_floor_line_follows_the_ramps_to_grade(law):
    g = _geom(_ramped_shell())
    r = object_cut.shell_reading(g, obj8.solid_components(g), law)
    mat = obj8.placement_affine((1000.0, 2000.0), 0.0)
    a, b, d, e, xo, yo = mat
    axis = LineString([(a * x + b * 15.0 + xo, d * x + e * 15.0 + yo) for x in (0.0, 120.0)])
    line = object_cut.floor_line(r.floor_faces, axis, mat, 100.0, 2.0)
    zs = [z for _x, _y, z in line]
    assert zs[0] == pytest.approx(100.0, abs=1e-6)          # grade at the portal
    assert zs[-1] == pytest.approx(100.0, abs=1e-6)
    assert min(zs) == pytest.approx(95.0, abs=1e-6)         # the floor 5 m under
    mid = line[len(line) // 4]                               # 30 m in: the ramp foot
    assert mid[2] == pytest.approx(95.0, abs=1e-6)
    quarter = line[7]                                        # 14 m in: on the ramp
    assert quarter[2] == pytest.approx(100.0 - 5.0 * 14.0 / 30.0, abs=1e-6)


def test_no_floor_faces_no_line():
    assert object_cut.floor_line(None, LineString([(0, 0), (10, 0)]),
                                 [1, 0, 0, 1, 0, 0], 0.0, 2.0) == ()


def test_the_profile_runs_from_the_corridors_mouth():
    line = ((10.0, 0.0, 5.0), (0.0, 0.0, 7.0), (5.0, 0.0, 6.0))
    prof = _floor_profile(line, [(10.0, 0.0), (0.0, 0.0)])
    assert prof == ((0.0, 5.0), (5.0, 6.0), (10.0, 7.0))
    assert _floor_profile(line[:1], [(0.0, 0.0), (1.0, 0.0)]) == ()


def test_a_cuts_own_frame_reads_its_end_lines_outside(monkeypatch):
    """#1903: the class-A seat of a frame holding a pack cut's own object
    reads the end lines one step OUTSIDE the deck — on its edge is the
    trench (EGLL 3/3a seated 1.25 m down the cut's slope) — and every
    other frame reads them on the edge, as before."""
    import types

    from auto_patch_v2.airport import airside_deck_seat as ADS
    seen = []
    monkeypatch.setattr(ADS, "airside_zero",
                        lambda m, *a, outside=False, **k: seen.append(outside))
    staged = [types.SimpleNamespace(m=types.SimpleNamespace(id="dsf:obj1")),
              types.SimpleNamespace(m=types.SimpleNamespace(id="dsf:obj2"))]
    ADS.airside_frame(staged, (), None, {}, 1.0, None, frozenset({"dsf:obj2"}))
    ADS.airside_frame(staged, (), None, {}, 1.0, None)
    assert seen == [True, True, False, False]
