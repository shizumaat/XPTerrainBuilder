"""THE SENTINEL IN THE DESIGN SURFACE — lane ``v2zerocrater``'s twins
(RULINGS 2026-09-13m, attributed here; spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §23.4).

THE MEASURED DEFECT.  KCLT's build of 2026-09-12 22:15 emitted 20 vertices
of apron face 661 (``dsf:pol31``) at exactly ``z = 0.00`` over ground the
production DEM reads at 217.1-218.2 m — a 90 x 65 m pit to sea level in the
built mesh, with a 130 m skirt.  The DEM there is healthy; the DSF polygon
carries no elevation at all.  The zero is minted by the SOLVE:

* ``solve/rows._cotangent_laplacian`` CLAMPS an obtuse cotangent weight to
  zero (it keeps the operator PSD).  The crater's only triangle to the rest
  of the sheet is one 186 m² sliver, and both of its crater-touching edges
  are clamped — so no row couples those 20 columns to anything;
* ``solve/design`` §9 ("a sheet carrying neither a pin nor a chord nor a
  zone fit floats — it takes its own DEM plane") judged connectivity on the
  TRIANGULATION, which the sliver joins.  The piece read as anchored;
* the least-squares block left behind is homogeneous — bending rows only,
  every right-hand side zero — and its minimiser is exactly 0.

Same class as the degenerate hole of RULINGS 2026-09-10h, whose fix trimmed
the one geometry that produced it.  These twins hold the general closure.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.geom import face_triangles
from auto_patch_v2.solve.rows import (_Reduction, _Rows, _cotangent_laplacian,
                                      _level_free_columns, _sheet_components)



# ── the dumbbell: a ring the triangulation joins and no row does ───────

#: Two 40 x 40 lobes joined by a 0.4 m neck across a 30 m gap.  Measured
#: (lane ``v2zerocrater``): ``face_triangles`` spans it with 10 triangles,
#: every one of the neck's cotangent weights is obtuse and clamped, and the
#: Laplacian reaches 6 of the 12 ring vertices from lobe A.
_NECK_W = 0.4
_GAP = 30.0


def _dumbbell() -> dict[int, tuple[float, float]]:
    ring = [(0.0, 0.0), (40.0, 0.0), (40.0, 20.0 - _NECK_W / 2),
            (40.0 + _GAP, 20.0 - _NECK_W / 2), (40.0 + _GAP, 0.0),
            (80.0 + _GAP, 0.0), (80.0 + _GAP, 40.0), (40.0 + _GAP, 40.0),
            (40.0 + _GAP, 20.0 + _NECK_W / 2), (40.0, 20.0 + _NECK_W / 2),
            (40.0, 40.0), (0.0, 40.0)]
    return {i: p for i, p in enumerate(ring)}


class _XY:
    """The slice of ``PlanarMap`` the Laplacian reads: ``vertices[v].xy``."""

    class _V:
        __slots__ = ("xy",)

        def __init__(self, xy):
            self.xy = xy

    def __init__(self, xy):
        self.vertices = {v: _XY._V(p) for v, p in xy.items()}


def test_the_triangulation_joins_a_neck_no_bending_row_crosses():
    """THE MECHANISM, in isolation.  A sliver-joined region is ONE face to
    the triangulation — and ``_sheet_components`` therefore reads it as one
    SHEET — while the cotangent Laplacian clamps every weight across the
    neck, so no bending row ties the two halves together at all.  That gap
    is what §9's anchoring cannot see and what the belt closes."""
    xy = _dumbbell()
    n = len(xy)
    tris = face_triangles(xy, list(range(n)), [])
    assert tris, "the ring triangulates"
    L, area = _cotangent_laplacian(_XY(xy), tris, n)
    L = L.tocsr()
    red = _Reduction(n)
    red.finish()
    assert len(set(_sheet_components(tris, red).values())) == 1, \
        "the triangulation spans the neck: ONE sheet"
    seen, stack = {0}, [0]
    while stack:
        i = stack.pop()
        for j in L.indices[L.indptr[i]:L.indptr[i + 1]]:
            j = int(j)
            if j != i and area[i] > 0.0 and j not in seen:
                seen.add(j)
                stack.append(j)
    assert 0 < len(seen) < n, \
        ("no bending row crosses the neck: the objective's graph is in "
         f"pieces ({len(seen)} of {n} reached)")


# ── the level belt ─────────────────────────────────────────────────────

def _homogeneous_and_levelled() -> tuple[_Rows, _Reduction]:
    """Four columns: 0-1 carry a bending-shaped row AND a datum, 2-3 carry
    only a difference row — the crater's algebra in four columns."""
    red = _Reduction(4)
    red.finish()
    rows = _Rows(red)
    rows.add(((0, 1.0), (1, -1.0)), 0.0, 1.0, ("bend", 0))
    rows.add(((0, 1.0),), 700.0, 1.0, ("datum", 0))
    rows.add(((2, 1.0), (3, -1.0)), 0.0, 1.0, ("bend", 2))
    return rows, red


def test_the_belt_names_the_columns_that_reach_the_solve_with_no_level():
    rows, red = _homogeneous_and_levelled()
    free = _level_free_columns(rows, None, red)
    assert set(free) == {2, 3}, \
        "the levelled pair is held; the homogeneous pair is named"


def test_a_one_sided_band_is_a_level_and_a_diff_is_not():
    """A one-sided ABSOLUTE row (a band) levels its columns; a relative
    one-sided row (a ``Diff``) bounds a DIFFERENCE and levels nothing —
    which is exactly what a non-zero right-hand side cannot be read to
    mean, and why LEVEL is the coefficient SUM."""
    rows, red = _homogeneous_and_levelled()
    band = ((((2, 1.0),), 705.0, None),)
    assert set(_level_free_columns(rows, None, red, band)) == set()
    diff = ((((2, 1.0), (3, -1.0)), 0.3, None),)
    assert set(_level_free_columns(rows, None, red, diff)) == {2, 3}


def test_the_homogeneous_block_really_does_solve_to_zero():
    """WHY the belt exists: least squares puts a homogeneous block at 0,
    whatever the ground under it is."""
    rows, red = _homogeneous_and_levelled()
    A, b = rows.matrix(red.n_cols)
    x, *_ = np.linalg.lstsq(A.toarray(), b, rcond=None)
    assert x[0] == pytest.approx(700.0, abs=1e-6)
    assert x[2] == pytest.approx(0.0, abs=1e-9)
    assert x[3] == pytest.approx(0.0, abs=1e-9)


# ── the ship-side net: the census family ───────────────────────────────

def _check_grade():
    """``tools/check_grade.py`` loaded BY PATH from this tree, registered in
    ``sys.modules`` first (its dataclasses resolve annotations through
    ``sys.modules[cls.__module__]``) — the spelling ``tests/test_harness``
    and ``harness/census`` both use."""
    import importlib.util
    import pathlib
    import sys
    root = pathlib.Path(__file__).resolve().parents[2]
    for extra in (root / "src", root, root / "tests", root / "tools"):
        if str(extra) not in sys.path:
            sys.path.insert(0, str(extra))
    name = "v2zerocrater_check_grade"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, root / "tools" / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_PATCH_HEAD = (
    "<?xml version='1.0' encoding='UTF-8'?>\n"
    "<osm version='0.6' generator='test'>\n")


def _patch(tmp_path, elevations):
    """A one-ring patch whose nodes carry ``alt_abs``; returns its path."""
    parts = [_PATCH_HEAD]
    nids = []
    for i, z in enumerate(elevations):
        nid = -(i + 1)
        nids.append(nid)
        lat = 35.2139 + 0.00002 * i
        lon = -80.9478 + 0.00002 * i
        parts.append(
            f"<node id='{nid}' lat='{lat:.11f}' lon='{lon:.11f}' version='1'>"
            f"<tag k='alt_abs' v='{z:.2f}'/></node>\n")
    parts.append("<way id='-1000' version='1'>")
    for nid in [*nids, nids[0]]:
        parts.append(f"<nd ref='{nid}'/>")
    parts.append("<tag k='role' v='apron'/><tag k='aeroway' v='apron'/>"
                 "<tag k='ref' v='dsf:pol31'/></way>\n</osm>\n")
    p = tmp_path / "ZZZZ_auto.patch.osm"
    p.write_text("".join(parts))
    return p


def test_a_vertex_at_zero_over_215_m_ground_is_a_census_CRITICAL(tmp_path):
    """THE BAR the brief sets: a polygon vertex at 0.0 over 215 m ground
    never leaves the harness unheard."""
    cg = _check_grade()
    good = [215.0 + 0.01 * i for i in range(40)]
    nodes, ways = cg._parse_osm(_patch(tmp_path, good))
    assert cg._check_sentinel_elevation(ways, nodes) == []
    holed = list(good)
    holed[7] = 0.0
    nodes, ways = cg._parse_osm(_patch(tmp_path, holed))
    rows = cg._check_sentinel_elevation(ways, nodes)
    assert len(rows) == 1, "the one sentinel vertex is found"
    assert rows[0].de_m > 200.0
    assert rows[0].lat is not None and rows[0].lon is not None
    bucket, why = cg.cockpit_classify("sentinel_elevation", rows[0],
                                      law=cg.cockpit_law())
    assert (bucket, why) == (cg.COCKPIT_VISUAL, "sentinel"), \
        "a hole in the design surface is CRITICAL wherever it is"
    assert "sentinel_elevation" in {k for k, _t, _b in cg.LAW_FAMILIES}, \
        "registered in LAW_FAMILIES (tests/test_harness.py twin-asserts it)"


def test_the_sentinel_floor_is_the_law_s_own_number():
    from auto_patch_v2.law import tables as _T
    cg = _check_grade()
    assert cg.sentinel_drop_m() == pytest.approx(
        float(_T.cockpit(_T.load_default()).sentinel_drop_m))
