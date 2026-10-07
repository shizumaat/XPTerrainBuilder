"""Twin of ``tools/v2_late_site.py``: a place on a last-stage arm read off
two solved maps — the level on a face's own triangulation, a section's
in-face slope and face-to-face difference, a piece's welded rim."""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import v2_late_site as site                                    # noqa: E402

#   3----2----5  .  9----8      apron (level 5) | gap piece rising 5 -> 6 |
#   |    |    |  .  |    |      2 m of faceless ground | a road at level 9
#   0----1----4  .  6----7
XY = [(0, 0), (10, 0), (10, 10), (0, 10), (20, 0), (20, 10),
      (22, 0), (30, 0), (30, 10), (22, 10)]
Z = {0: 5.0, 1: 5.0, 2: 5.0, 3: 5.0, 4: 6.0, 5: 6.0, 6: 9.0, 7: 9.0, 8: 9.0, 9: 9.0}
FACES = [("apron", "pav1", (0, 1, 2, 3)),
         ("groundside_pavement", "gap:0", (1, 4, 5, 2)),
         ("service_road", "route3", (6, 7, 8, 9))]


def _pm(faces=FACES):
    eid: dict = {}
    edges: dict = {}
    rings: dict = {}
    fs = {}
    for i, (role, ref, ring) in enumerate(faces):
        cyc = []
        for k, a in enumerate(ring):
            b = ring[(k + 1) % len(ring)]
            key = frozenset((a, b))
            if key not in eid:
                eid[key] = 100 + len(eid)
                edges[eid[key]] = types.SimpleNamespace(a=a, b=b, left_face=i,
                                                        right_face=None)
            else:
                edges[eid[key]].right_face = i
            cyc.append(eid[key])
        rings[tuple(cyc)] = ring
        fs[i] = types.SimpleNamespace(id=i, role=role, ref=ref, ring=tuple(cyc),
                                      holes=(), side="groundside")
    return types.SimpleNamespace(
        vertices={i: types.SimpleNamespace(xy=(float(x), float(y)))
                  for i, (x, y) in enumerate(XY)},
        faces=fs, edges=edges, ring_vertices=lambda cyc: rings[tuple(cyc)])


def test_a_level_is_read_on_the_faces_own_triangles_and_nowhere_else():
    s = site.Surface(_pm(), Z)
    f, z = s.z_at((15.0, 5.0))
    assert f.ref == "gap:0" and z == pytest.approx(5.5)
    assert s.z_at((21.0, 5.0)) == (None, None)          # the faceless strip


def test_a_section_reads_the_slope_inside_a_face_and_the_difference_between_faces():
    pm = _pm()
    arm = site.Surface(pm, Z)
    base = site.Surface(_pm([FACES[0], FACES[2]]), Z)   # the map without the piece
    dem = types.SimpleNamespace(z=lambda x, y: 7.0)
    lines: list = []
    r = site.read_section(base, arm, dem, (15.0, 5.0), (1.0, 0.0), 12.0, 1.0,
                          "west -> east", lines.append)
    assert r["worst_slope"]["arm"] == pytest.approx(0.10)
    # the piece's rim at 6.0 against the road at 9.0 across the faceless 2 m
    assert r["worst_face_change"]["arm"] == pytest.approx(3.0, abs=0.11)
    # the base has no face over the piece: apron 5.0 against the road 9.0
    assert r["worst_face_change"]["base"] == pytest.approx(4.0)
    assert r["worst_slope"]["base"] == 0.0
    assert len(r["rows"]) == 25 and r["rows"][12]["base"] == ("-", None)


def test_a_piece_names_its_welded_rim_and_the_rim_no_face_shares():
    pm = _pm()
    late = types.SimpleNamespace(pa=pm, za=Z, fixed={1: 5.0, 2: 5.0})
    r = site.read_piece(late, "gap:0", {}, lambda _s: None)
    assert r["faces"] == 1 and r["area_m2"] == pytest.approx(100.0)
    assert r["welded"]["apron:pav1"]["shared_m"] == pytest.approx(10.0)
    assert r["welded"]["apron:pav1"]["z"] == (5.0, 5.0)
    assert r["welded"]["(no face: the mesh's own ground)"]["shared_m"] == pytest.approx(30.0)
    assert r["z"] == (5.0, 6.0)
