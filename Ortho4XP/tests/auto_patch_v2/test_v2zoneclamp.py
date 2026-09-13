"""§32 THE ZONE BAND IS PROJECTED, LIKE THE RUNWAY (RULINGS 2026-09-12ag).

The twins of the two things the lane landed:

* :func:`auto_patch_v2.solve.project.project_zone_bands` — the per-vertex
  clamp: every corridor row it OWNS is held afterwards, a column carrying
  anything but governed ground vertices is never moved (the pad-rim /
  Flat-straddling classes that made the hard set infeasible), and the
  strip tie is not swept in by its shared generator;
* the seam-tear row's LAT/LON is the PAIR MIDPOINT, in both instruments —
  the v1 oracle (``tools/check_grade``) and the engine's own verify — so
  a row never points at a ring centroid 220 m from the tear.
"""
from __future__ import annotations

import dataclasses as _dc
import sys

import numpy as np
import pytest

from auto_patch_v2.law import load_default
from auto_patch_v2.model.constraints import Linear, Source
from auto_patch_v2.solve.project import (ZONE_GENERATOR, ZONE_RULING,
                                         foreign_hard_columns,
                                         project_zone_bands, zone_band_sides)
from auto_patch_v2.solve.rows import _Reduction, _law_sides

CORRIDOR = "zones.adjacent_ground (2026-08-01)"
TIE = ("zones.adjacent_ground.runway.band_max_down strip tie "
       "(2026-09-06b law 2; every vertex 2026-09-06p; two-way 2026-09-06q)")


@_dc.dataclass
class _FakeBase:
    red: _Reduction
    one: list
    #: §32 (4): the HARD row indices into ``one`` — the real ``solve.design
    #: .Base`` always carries them and :func:`foreign_hard_columns` reads
    #: them, so the fake states them too
    hard: list = _dc.field(default_factory=list)


def _base(n_vertices: int, rows, flats=(), hard=()):
    red = _Reduction(n_vertices)
    for g in flats:
        for v in g[1:]:
            red.union(g[0], v)
    red.finish()

    class _CS:
        diffs = ()
        offsets = ()
        bands = ()

    cs = _CS()
    cs.linears = list(rows)
    one, _eq = _law_sides(cs)
    return _FakeBase(red=red, one=one, hard=list(hard))


def _corridor(v, foot, lo, hi):
    """One one-way corridor row: ``lo <= z_v - z_foot <= hi``."""
    return Linear(((v, 1.0), (foot, -1.0)), lo, hi,
                  Source(ZONE_GENERATOR, CORRIDOR, (f"vertex:{v}",)),
                  follows=v)


def _x_of(base, z):
    """The reduced column vector carrying ``z`` (one value per vertex)."""
    x = np.zeros(base.red.n_cols)
    for v, zz in enumerate(z):
        c = int(base.red.col[v])
        if c >= 0:
            x[c] = zz
    return x


def _z_of(base, x):
    col = base.red.col
    return np.where(col >= 0, x[np.clip(col, 0, None)], base.red.value)


@pytest.fixture(scope="module")
def law():
    return load_default()


# ── the clamp ───────────────────────────────────────────────────────────

def test_the_pit_vertex_is_clamped_into_its_own_band(law):
    """§32 (1): a ground vertex 8 m below its corridor band comes back to
    the band's floor and nowhere else — the LEMD pit, in miniature.

    Vertex 0 is the ground, vertex 1 the pavement foot at 578.00; the band
    is the law's own lip range (0.09-0.15 m below the foot).
    """
    base = _base(2, [_corridor(0, 1, -0.1500, -0.0900)])
    x = _x_of(base, [569.76, 578.00])
    out, rep = project_zone_bands(None, law, base, x)
    z = _z_of(base, out)
    assert rep.ran and rep.status == "optimal"
    assert rep.vertices == 1 and rep.columns == 1 and rep.moved == 1
    assert z[1] == pytest.approx(578.00)          # the foot never moves
    assert z[0] == pytest.approx(577.85, abs=1e-6)
    assert rep.before_m == pytest.approx(8.09, abs=0.01)
    assert rep.after_m == pytest.approx(0.0, abs=1e-9)
    assert rep.after_owned_m == pytest.approx(0.0, abs=1e-9)


def test_a_vertex_already_inside_its_band_is_not_moved(law):
    base = _base(2, [_corridor(0, 1, -0.1500, -0.0900)])
    x = _x_of(base, [577.88, 578.00])
    out, rep = project_zone_bands(None, law, base, x)
    assert rep.moved == 0
    assert out == pytest.approx(x)


def test_the_pocket_rule_intersects_the_vertexs_rows(law):
    """A farther pavement contributes its FLOOR only (``zone_bands``'s
    pocket rule): the clamp must honour the INTERSECTION, not the last
    row it read."""
    rows = [_corridor(0, 1, -0.15, -0.09),        # nearest: floor + ceiling
            Linear(((0, 1.0), (2, -1.0)), -0.30, None,
                   Source(ZONE_GENERATOR, CORRIDOR, ("vertex:0",)), follows=0)]
    base = _base(3, rows)
    # foot 578.00 -> [577.85, 577.91]; the farther foot 578.10 floors at
    # 577.80, which is BELOW the nearest ceiling: the intersection is the
    # nearest band and the vertex lands on its floor.
    x = _x_of(base, [560.0, 578.00, 578.10])
    out, rep = project_zone_bands(None, law, base, x)
    z = _z_of(base, out)
    assert rep.conflicts == 0
    assert z[0] == pytest.approx(577.85, abs=1e-6)


def test_an_empty_band_intersection_is_reported_not_invented(law):
    """Where a farther pavement's floor stands ABOVE the nearest's
    ceiling the law states no precedence: the vertex goes to the midpoint
    (the value that minimises the worst of the two rows) and the count is
    REPORTED."""
    rows = [_corridor(0, 1, -0.15, -0.09),
            Linear(((0, 1.0), (2, -1.0)), 0.50, None,
                   Source(ZONE_GENERATOR, CORRIDOR, ("vertex:0",)), follows=0)]
    base = _base(3, rows)
    x = _x_of(base, [560.0, 578.00, 578.00])
    out, rep = project_zone_bands(None, law, base, x)
    z = _z_of(base, out)
    assert rep.conflicts == 1
    assert z[0] == pytest.approx(0.5 * (578.50 + 577.91), abs=1e-6)


def test_a_flat_group_carrying_an_UNGOVERNED_vertex_is_never_moved(law):
    """THE REFUTED CLASSES, kept out by construction (module comment): a
    detached pad's rim carries the band on ONE vertex and the ``Flat``
    carries the level to the rest, and a ``Flat`` straddling pavement
    holds pavement columns.  Either way the column is IMPURE and the
    projection leaves it alone — this is what the hard-set attempt could
    not do (KCLT / CYXY / SPLP / SPJC / OTHH went infeasible)."""
    base = _base(3, [_corridor(0, 2, -0.15, -0.09)], flats=[(0, 1)])
    x = _x_of(base, [569.76, 569.76, 578.00])
    out, rep = project_zone_bands(None, law, base, x)
    assert rep.columns == 0
    assert rep.impure_columns == 1
    assert rep.moved == 0
    assert out == pytest.approx(x)


def test_the_strip_tie_is_not_swept_in_by_its_shared_generator(law):
    """``zones.strip_transverse`` mints from the SAME generator under a
    head that ``startswith("zones.adjacent_ground")`` matches.  The
    projection owns the corridor rows only — the tie is two-way against a
    runway edge the runway projection has just moved."""
    tie = Linear(((0, 1.0), (1, -1.0)), -0.40, 0.40,
                 Source(ZONE_GENERATOR, TIE, ()), follows=0)
    base = _base(2, [tie])
    assert zone_band_sides(base) == []
    x = _x_of(base, [560.0, 578.00])
    out, rep = project_zone_bands(None, law, base, x)
    assert rep.rows == 0 and rep.moved == 0
    assert out == pytest.approx(x)
    assert ZONE_RULING == "zones.adjacent_ground"


# ── §32 (4) PURITY (Fable 2026-09-13; RULINGS 2026-09-13ac) ─────────────

PAD_CEIL = "structures.building_pad pad_slope_max ceiling (owner 2026-09-09c)"


def _hard_of(base, generator):
    """The ``base.one`` indices a generator's rows landed on.  A two-sided
    ``Linear`` becomes TWO one-sided rows (``_law_sides``), so a row's
    index is never its position in the list the twin wrote."""
    return [k for k, (_t, _b, row) in enumerate(base.one)
            if row.source.generator == generator]


def _pad_ceiling(a, b, cap):
    """The hard row main's worst violation was: the pad-slope ceiling
    between two rim vertices, ``z_a - z_b <= cap``."""
    return Linear(((a, 1.0), (b, -1.0)), None, cap,
                  Source("pads", PAD_CEIL, (f"vertex:{a}",)))


def test_a_zone_vertex_carrying_a_foreign_hard_row_is_left_to_the_solve(law):
    """§32 (4): main's worst hard row, in miniature.  v0 and v1 are a pad
    rim 3 cm apart, both governed by their own corridor bands and both
    carrying ONE pad-slope ceiling between them.  Clamped independently,
    the clamp answers the two bands and MINTS the ceiling (this is the
    0.1292 m at v8276/v8273, 13ac).  Under purity neither column is
    clampable, both keep the solve's value, and the ceiling holds."""
    rows = [_corridor(0, 2, -0.15, -0.09),
            _corridor(1, 3, -0.15, -0.09),
            _pad_ceiling(0, 1, 0.025)]
    base = _base(4, rows)
    base.hard = _hard_of(base, "pads")
    # the two feet stand 0.30 m apart, so the two bands pull the rim
    # vertices 0.30 m apart -- twelve times the ceiling
    x = _x_of(base, [577.60, 577.61, 578.00, 577.70])
    out, rep = project_zone_bands(None, law, base, x)
    z = _z_of(base, out)
    assert rep.vertices == 2
    assert rep.columns == 0
    assert rep.hard_columns == 2
    assert rep.impure_columns == 0
    assert rep.moved == 0
    assert out == pytest.approx(x)                 # left to the solve
    assert z[0] - z[1] <= 0.025 + 1e-9             # the ceiling still holds


def test_the_projection_still_clamps_a_PURE_column_byte_identically(law):
    """Purity narrows the population and nothing else: the same pit
    vertex of :func:`test_the_pit_vertex_is_clamped_into_its_own_band`,
    now with a pad ceiling elsewhere in the problem, is clamped to the
    same value it was before."""
    rows = [_corridor(0, 1, -0.1500, -0.0900),
            _pad_ceiling(2, 3, 0.025)]
    base = _base(4, rows)
    base.hard = _hard_of(base, "pads")
    x = _x_of(base, [569.76, 578.00, 600.0, 600.5])
    out, rep = project_zone_bands(None, law, base, x)
    z = _z_of(base, out)
    assert rep.columns == 1 and rep.hard_columns == 0 and rep.moved == 1
    assert z[0] == pytest.approx(577.85, abs=1e-6)
    assert z[2] == pytest.approx(600.0) and z[3] == pytest.approx(600.5)


def test_a_row_the_projection_OWNS_never_makes_its_own_column_impure(law):
    """The test is "no hard row it does NOT own".  A corridor row that is
    itself hard must not lock its own vertex out of the clamp."""
    base = _base(2, [_corridor(0, 1, -0.15, -0.09)])
    base.hard = _hard_of(base, ZONE_GENERATOR)
    x = _x_of(base, [569.76, 578.00])
    out, rep = project_zone_bands(None, law, base, x)
    assert rep.hard_columns == 0 and rep.columns == 1 and rep.moved == 1
    assert _z_of(base, out)[0] == pytest.approx(577.85, abs=1e-6)


def test_foreign_hard_columns_names_every_column_a_foreign_row_touches(law):
    """The test is stated ONCE so every projection that follows takes it
    (§32 (4) closing sentence): the helper is public and reads the whole
    hard set, not the zone rows' own view of it."""
    rows = [_corridor(0, 2, -0.15, -0.09), _pad_ceiling(0, 1, 0.025)]
    base = _base(3, rows)
    base.hard = _hard_of(base, "pads")
    bad = foreign_hard_columns(base, set())
    assert bad[int(base.red.col[0])] and bad[int(base.red.col[1])]
    assert not bad[int(base.red.col[2])]
    assert not foreign_hard_columns(base, set(base.hard)).any()


def test_the_law_can_turn_the_projection_off_by_name(law):
    """``[design] zone_projection = false`` is the diagnostic arm and the
    report says so rather than passing silently."""
    import copy

    off = copy.deepcopy(law)
    object.__setattr__(off.tables.emit.design, "zone_projection", False)
    base = _base(2, [_corridor(0, 1, -0.15, -0.09)])
    x = _x_of(base, [569.76, 578.00])
    out, rep = project_zone_bands(None, off, base, x)
    assert not rep.ran and "zone_projection" in rep.status
    assert out is x


# ── §32 (3): the seam-tear row carries the PAIR MIDPOINT ────────────────

#: two overlapping ``graded_strip`` rectangles, 3 m of seam apart and
#: 8.26 m of step: the LEMD tear's shape (node -12917 at 569.76 against
#: node -12474 at 578.02, 3.01 m = ``lip_width_m``).  They OVERLAP so the
#: open-ground floor (15 m) does not silence the pair.
_A = [(0.0, 0.0), (0.0, 6.0), (12.0, 6.0), (12.0, 0.0)]
_B = [(0.0, 3.0), (0.0, 9.0), (12.0, 9.0), (12.0, 3.0)]
_LAT0, _LON0 = 40.4609867, -3.5443920


def _seam_fixture():
    """``(vertices, ways, node_ll)`` for the two strips."""
    sys.path.insert(0, "tools")
    import check_grade as CG

    verts, node_ll = [], {}
    for w_idx, (pts, z, shape) in enumerate(((_A, 569.76, "474"),
                                             (_B, 578.02, "463"))):
        for k, (x, y) in enumerate(pts):
            nid = f"n{w_idx}_{k}"
            verts.append(CG.Vertex(way_idx=w_idx, nid=nid, x=x, y=y, elev=z))
            node_ll[nid] = (_LAT0 + y / 111320.0, _LON0 + x / 85000.0)
    ways = [_way("474"), _way("463")]
    return verts, ways, node_ll


def test_v1_seam_tear_row_carries_the_pair_midpoint_not_a_centroid():
    """``check_grade._check_strip_seam_tears``: the row's lat/lon lies
    BETWEEN its own two nodes.  Before 12ag it was null and ``run_checks``
    filled it with the offending way's RING CENTROID (``check_grade.py:
    9576-9589``) — 220 m from the LEMD tear."""
    sys.path.insert(0, "tools")
    import check_grade as CG

    verts, ways, node_ll = _seam_fixture()
    rows = CG._check_strip_seam_tears(verts, ways, node_ll)
    assert rows, "the 8.26 m step over 3 m must be flagged"
    by_nid = {v.nid: v for v in verts}
    centroids = [(sum(p[0] for p in _A) / 4.0, sum(p[1] for p in _A) / 4.0),
                 (sum(p[0] for p in _B) / 4.0, sum(p[1] for p in _B) / 4.0)]
    for r in rows:
        assert r.de_m == pytest.approx(8.26, abs=0.01)
        # the row's site is the MIDPOINT of its own pair, in lat and lon
        a = _nid_at(by_nid, node_ll, r.pt_a)
        b = _nid_at(by_nid, node_ll, r.pt_b)
        assert r.lat == pytest.approx(0.5 * (a[0] + b[0]))
        assert r.lon == pytest.approx(0.5 * (a[1] + b[1]))
        # ... and it is INSIDE the pair, never a ring centroid
        assert min(a[0], b[0]) <= r.lat <= max(a[0], b[0])
        assert min(a[1], b[1]) <= r.lon <= max(a[1], b[1])
        mid_xy = (0.5 * (r.pt_a[0] + r.pt_b[0]), 0.5 * (r.pt_a[1] + r.pt_b[1]))
        assert mid_xy not in centroids


def _nid_at(by_nid, node_ll, pt):
    for nid, v in by_nid.items():
        if (v.x, v.y) == (pt[0], pt[1]):
            return node_ll[nid]
    raise AssertionError(f"no node at {pt}")


def test_v1_seam_tear_row_without_node_lat_lon_still_reads():
    """The parameter is OPTIONAL and additive: a caller that passes no
    node table gets the pre-12ag behaviour (``lat`` null, so the reader's
    centroid fallback still fires), never a crash."""
    sys.path.insert(0, "tools")
    import check_grade as CG

    verts, ways, _ll = _seam_fixture()
    rows = CG._check_strip_seam_tears(verts, ways)
    assert rows and all(r.lat is None for r in rows)


def _way(shape_id):
    """One ``graded_strip`` way, the seam-tear reader's population."""
    sys.path.insert(0, "tools")
    import check_grade as CG

    return CG.Way(wid=f"w{shape_id}", role="graded_strip", ref="", aeroway="",
                  nids=[], elevs=[],
                  tags={"role": "graded_strip", "shapeID": shape_id})


def test_engine_verify_seam_tear_row_carries_the_pair_midpoint():
    """The TWIN of the above in the engine's own census
    (``verify/strips.strip_seam_tear``): the row's ``lat``/``lon`` is the
    pair midpoint read off ``Patch.ll``, not null."""
    import inspect

    from auto_patch_v2.verify import strips as V

    src = inspect.getsource(V.strip_seam_tear)
    assert "p.ll[vid]" in src and "p.ll[vid2]" in src, (
        "the engine's seam-tear row must carry the pair midpoint too")
    assert "lat=0.5 * (p.ll[vid][0] + p.ll[vid2][0])" in src
    assert "lon=0.5 * (p.ll[vid][1] + p.ll[vid2][1])" in src
