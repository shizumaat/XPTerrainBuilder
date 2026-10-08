"""Spec §56 (11) R-C — a pad's ``within_shape`` rows are read ONE PER
VERTEX (``check_grade._one_row_per_pad_vertex``).

A rigid pad is one level plane, so ONE vertex standing off it is over the
cap against every ring partner: the pair reading scaled with the ring
(OTHH 366 -> 1,095 on a simplified 1,111-vertex terminal outline while
the pad was FLATTER by the in-build ``pad_flat``).  The pair law and its
allowances are untouched — only the count is per vertex."""
from __future__ import annotations

import math
import sys

import pytest

_LAT0, _LON0 = 25.2647, 51.6116
_N = 24


@pytest.fixture(scope="module")
def CG():
    sys.path.insert(0, "tools")
    import check_grade
    return check_grade


def _pad(CG, role: str, z_of, wid: str = "pad"):
    """A 24-gon of 40 m radius as one closed way of ``role``."""
    nids, elevs, ll = [], [], {}
    for i in range(_N):
        a = 2.0 * math.pi * i / _N
        nid = f"{wid}_{i}"
        nids.append(nid)
        elevs.append(z_of(i))
        ll[nid] = (_LAT0 + 40.0 * math.sin(a) / 111320.0,
                   _LON0 + 40.0 * math.cos(a) / 100650.0)
    way = CG.Way(wid=wid, role=role, ref=role, aeroway="",
                 nids=nids + nids[:1], elevs=elevs + elevs[:1],
                 tags={"role": role, "shapeID": wid})
    return way, ll


def _rows(CG, role: str, z_of, relief=None):
    way, nodes = _pad(CG, role, z_of)
    return CG._check_within_shape(
        [way], nodes, CG._ll_to_m_factory(nodes), 0.015,
        pad_relief_by_nid=relief), nodes


def test_one_vertex_off_the_plane_is_one_row_at_that_vertex(CG):
    rows, nodes = _rows(CG, "building", lambda i: 102.0 if i == 5 else 100.0)
    assert len(rows) == 1
    assert (rows[0].lat, rows[0].lon) == nodes["pad_5"]
    assert rows[0].de_m == pytest.approx(2.0)
    # the pair reading it replaces counted that vertex per ring partner
    pairs, _n = _rows(CG, "apron", lambda i: 102.0 if i == 5 else 100.0)
    assert len(pairs) > 5


def test_two_vertices_off_are_two_rows_and_a_flat_pad_none(CG):
    rows, nodes = _rows(CG, "building",
                        lambda i: {5: 102.0, 17: 97.0}.get(i, 100.0))
    assert sorted((r.lat, r.lon) for r in rows) \
        == sorted((nodes["pad_5"], nodes["pad_17"]))
    assert _rows(CG, "building", lambda i: 100.0)[0] == []


def test_a_vertex_at_its_relief_target_is_no_row_and_off_it_is_one(CG):
    """11j: the reading is against the vertex's OWN relief target."""
    relief = {f"pad_{i}": (1.5 if i == 5 else 0.0) for i in range(_N)}
    at, _n = _rows(CG, "building", lambda i: 101.5 if i == 5 else 100.0, relief)
    assert at == []
    off, nodes = _rows(CG, "building", lambda i: 100.0, relief)
    assert len(off) == 1 and (off[0].lat, off[0].lon) == nodes["pad_5"]


def test_the_reading_is_the_same_whatever_the_ring_length(CG):
    """The count no longer scales with the ring: the same defect on the
    same pad drawn with twice the vertices is still one row."""
    def rows_at(n):
        nids, elevs, ll = [], [], {}
        for i in range(n):
            a = 2.0 * math.pi * i / n
            nids.append(f"p_{i}")
            elevs.append(102.0 if i == 0 else 100.0)
            ll[f"p_{i}"] = (_LAT0 + 40.0 * math.sin(a) / 111320.0,
                            _LON0 + 40.0 * math.cos(a) / 100650.0)
        way = CG.Way(wid="p", role="building", ref="building", aeroway="",
                     nids=nids + nids[:1], elevs=elevs + elevs[:1],
                     tags={"role": "building", "shapeID": "p"})
        return CG._check_within_shape([way], ll, CG._ll_to_m_factory(ll), 0.015)
    assert len(rows_at(12)) == len(rows_at(48)) == 1
