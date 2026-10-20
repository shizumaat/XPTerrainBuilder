"""Issue #737: the graded-surface replay reads ONLY ON THE SURFACE.

``tools/obj8_split_report.surface_from_graded`` (and through it
``seat_feet_census``, ``jetway_rider_census``) and ``v2_rebake_replay``'s
``--sampler graded`` interpolate over a Delaunay of the graded vertices.
Between two faces the triangles span ungraded ground from one face's
vertices to the other's, so a point there read a height the surface never
stated, and a slab piece added NEAR it (not under it) re-drew those
triangles and moved the reading: HECA read 8 Seasonal Terminal bodies up
to 2.5 m worse where the app mesh moved none.

Hand answers on two 20 m apron squares 80 m apart (z 10 and z 30):

* a point in the 80 m gap reads ``None`` (off-sheet), before and after a
  third face is added 2 m from it — under the old reader it read ~20 m
  and the new face moved it;
* a point on a face reads that face's height, unchanged by the addition;
* a point in a 0.2 m SEAM between two abutting faces still reads (the
  emitted faces do not tile the field; the mesh carries the join).
"""
from __future__ import annotations

import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))
import obj8_split_report as RPT  # noqa: E402

_LA0, _LO0 = 30.0527, 31.2133
_KLA = 6_378_137.0 * math.pi / 180.0
_KLO = _KLA * math.cos(math.radians(_LA0))


def _ll(x: float, y: float) -> tuple[float, float]:
    return (_LA0 + y / _KLA, _LO0 + x / _KLO)


class _Doc:
    def __init__(self) -> None:
        self.vertices: list = []
        self.faces: list = []

    def square(self, x0: float, y0: float, w: float, h: float, z: float,
               ref: str) -> None:
        ids = []
        for x, y in ((x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)):
            vid = len(self.vertices) + 1
            self.vertices.append([vid, *_ll(x, y), z])
            ids.append(vid)
        self.faces.append({"ring": ids, "role": "apron", "ref": ref,
                           "holes": []})

    def write(self, path) -> str:
        path.write_text(json.dumps({"vertices": self.vertices,
                                    "faces": self.faces,
                                    "breaklines": []}),
                        encoding="utf-8", newline="")
        return str(path)


def _two_aprons() -> _Doc:
    d = _Doc()
    d.square(0.0, 0.0, 20.0, 20.0, 10.0, "A")
    d.square(100.0, 0.0, 20.0, 20.0, 30.0, "B")
    return d


_GAP = _ll(60.0, 10.0)
_ON_A = _ll(10.0, 10.0)


def test_a_point_between_faces_reads_off_sheet(tmp_path):
    sampler, _p, _r = RPT.surface_from_graded(
        _two_aprons().write(tmp_path / "g.json"))
    assert sampler(*_GAP) is None
    assert sampler.many([_GAP[0]], [_GAP[1]]) == [None]
    assert sampler(*_ON_A) == pytest.approx(10.0)


def test_a_face_added_near_the_gap_moves_no_reading(tmp_path):
    """The defect's mechanism: the interpolator alone DOES move at the
    gap point when a face is added 2 m from it (asserted, so the twin is
    not vacuous); the sampler reads off-sheet both times, and on-face
    readings do not change."""
    d0 = _two_aprons()
    d1 = _two_aprons()
    d1.square(62.0, 0.0, 6.0, 20.0, 0.0, "slab")
    s0, _p, _r = RPT.surface_from_graded(d0.write(tmp_path / "g0.json"))
    s1, _p, _r = RPT.surface_from_graded(d1.write(tmp_path / "g1.json"))

    def raw(doc):
        f = RPT.GradedInterpolator([v[1:3] for v in doc.vertices],
                                   [v[3] for v in doc.vertices])
        return float(f(*_GAP)[0])
    assert abs(raw(d0) - raw(d1)) > 1.0           # the old reading moved
    assert s0(*_GAP) is None and s1(*_GAP) is None
    on_b = _ll(110.0, 10.0)
    assert s0(*_ON_A) == s1(*_ON_A) == pytest.approx(10.0)
    assert s0(*on_b) == s1(*on_b) == pytest.approx(30.0)


def test_a_point_in_a_seam_between_abutting_faces_still_reads(tmp_path):
    d = _Doc()
    d.square(0.0, 0.0, 20.0, 20.0, 10.0, "A")
    d.square(20.2, 0.0, 20.0, 20.0, 10.0, "B")      # a 0.2 m seam
    sampler, _p, _r = RPT.surface_from_graded(d.write(tmp_path / "s.json"))
    assert sampler(*_ll(20.1, 10.0)) == pytest.approx(10.0)
    assert RPT.FACE_REACH_M > 0.1


def test_a_document_with_no_faces_reads_as_before():
    """No faces states no extent: the mask lets every point through."""
    m = RPT.GradedFaceMask({"vertices": [[1, *_ON_A, 1.0]]}, (_LA0, _LO0))
    assert m.on_surface([_GAP[0]], [_GAP[1]]).tolist() == [True]
