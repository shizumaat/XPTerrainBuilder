"""THE TWIN for issue #245 — a tunnel corridor's principal axis, and the
SIDE SPLIT built on it, do not move when a ring vertex is inserted.

``tools/tunnel_portal_acceptance.py::_principal_axis`` was a vertex-MASS-
weighted PCA about the centroid until 2026-10-02: one vertex inserted
anywhere on a corridor ring — densification, a tile cut, a crossing
split, a closed ring's repeated first vertex — moved the centroid and
tilted the axis with nothing about the corridor's shape having changed.
That is the defect class issue #190 fixed at the RUNWAY axis under owner
ruling ``2026-10-02v`` (7), and the reason it matters HERE is that the
consequence is DISCRETE: the axis is the half-plane ``_side_cover``
splits a site's boundary with, so a fraction of a degree moves a face
from one side of the corridor to the other and changes a reported row.

The arms, in the order the issue asks for them:

* **the axis is insertion-invariant** — to EXACT float equality in the
  ring's own frame, and to float tolerance once the ring is rotated
  (where a "collinear" vertex is only collinear to float precision and
  can land a hair outside the hull);
* **the SIDE SPLIT is insertion-invariant** — ``_side_cover``'s
  ``(left, right)`` pair is bit-identical with and without the inserted
  vertices, which is the consequence the axis exists to serve;
* **a clean 4-corner corridor reads what the OLD PCA read** — so no
  reference moves for a corridor that was never the problem.  The old
  closed form is kept HERE and nowhere else;
* **the fit is the law's own** — it is ``auto_patch_v2.constraints.
  geometry``'s rectangle, not a second geometry fit in a tool;
* the degenerate contracts, and DETERMINISM under arrival order (the
  retiring ``numpy.linalg.svd`` was not even that).
"""
from __future__ import annotations

import importlib.util
import math
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "tunnel_portal_acceptance.py"
sys.path.insert(0, str(ROOT / "src"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tpa():
    return _load("tpa_axis_invariance", TOOL_PATH)


# ──────────────────────────────────────────────────────────────────
# THE RETIRING FIT, kept here and nowhere else.
# ──────────────────────────────────────────────────────────────────
def _old_pca_axis(pts):
    """``_principal_axis`` as it stood before 2026-10-02: the dominant
    right singular vector of the MEAN-CENTRED coordinates.

    Sign-canonicalised into the +x half-plane so a comparison measures
    the DIRECTION and not LAPACK's arbitrary choice of sign — the new
    fit canonicalises explicitly (``geometry._min_area_rect_of_points``),
    the old one never did, which is its own small defect.
    """
    import numpy
    p = numpy.asarray(pts, dtype=float)
    p = p - p.mean(axis=0)
    _u, _s, vt = numpy.linalg.svd(p, full_matrices=False)
    ax, ay = float(vt[0][0]), float(vt[0][1])
    n = math.hypot(ax, ay)
    if n <= 1e-9:                                        # pragma: no cover
        return None
    ax, ay = ax / n, ay / n
    return (-ax, -ay) if (ax < 0.0 or (ax == 0.0 and ay < 0.0)) else (ax, ay)


# ──────────────────────────────────────────────────────────────────
# Corridors as this instrument actually meets them.
# ──────────────────────────────────────────────────────────────────
#: A clean corridor: one ``tunnel_ramp`` rect, 200 m of run, 12 m wide.
CORRIDOR = [(0.0, 0.0), (200.0, 0.0), (200.0, 12.0), (0.0, 12.0)]
#: A WIDENING ramp — a mouth flares, so a corridor is not a rectangle.
RAMP = [(0.0, 0.0), (200.0, 0.0), (200.0, 20.0), (0.0, 8.0)]
#: A TURNING arm of a fork (``bridges._emit_fork_throat``'s Y).
ARM = [(0.0, 0.0), (120.0, 0.0), (120.0, 70.0),
       (108.0, 70.0), (108.0, 12.0), (0.0, 12.0)]
#: A fork's flat THROAT PLATE — near square, so its long axis is weakly
#: determined.  This is the shape the old fit swung 90° on.
PLATE = [(0.0, 0.0), (26.0, 0.0), (26.0, 24.0), (0.0, 24.0)]
#: An EXACT square: no long axis exists.  Its own case, below.
SQUARE = [(0.0, 0.0), (30.0, 0.0), (30.0, 30.0), (0.0, 30.0)]

SHAPES = {"corridor": CORRIDOR, "ramp": RAMP, "arm": ARM, "plate": PLATE}
#: Bearings a corridor actually runs at, including the two axis-aligned
#: ones the canonical-orientation branch turns on.
BEARINGS = (0.0, 23.0, 90.0, -61.5, 137.0)


def _rot(pts, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def _densify(pts, k, edges=None):
    """``pts`` with ``k`` evenly spaced COLLINEAR vertices inserted on
    each selected edge — what densification, a tile cut and a crossing
    split each leave behind."""
    n = len(pts)
    out = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        out.append(a)
        if edges is None or i in edges:
            for j in range(1, k + 1):
                t = j / (k + 1.0)
                out.append((a[0] + (b[0] - a[0]) * t,
                            a[1] + (b[1] - a[1]) * t))
    return out


#: The insertions, each one a thing an emitter really does.
INSERTIONS = {
    "both long edges x5": lambda p: _densify(p, 5, {0, 2}),
    "ONE long edge x5": lambda p: _densify(p, 5, {0}),
    "one vertex mid-edge": lambda p: _densify(p, 1, {0}),
    "every edge x3": lambda p: _densify(p, 3),
}


def _poly(pts):
    from shapely.geometry import Polygon
    return Polygon(pts)


def _angle_between(u, v):
    """Degrees between two undirected axes (0 when parallel)."""
    assert u is not None and v is not None
    d = abs(u[0] * v[0] + u[1] * v[1])
    return math.degrees(math.acos(max(0.0, min(1.0, d))))


# ──────────────────────────────────────────────────────────────────
# 1. THE AXIS DOES NOT MOVE
# ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("shape", sorted(SHAPES))
@pytest.mark.parametrize("insertion", sorted(INSERTIONS))
def test_inserted_ring_vertices_leave_the_axis_exactly_alone(
        tpa, shape, insertion):
    """EXACT equality, in the ring's own frame — the frame an emitter
    inserts a vertex in.  Not "close": the inserted vertex lies on the
    convex hull's edge, so it is dropped by the hull and the answer is
    the same floats."""
    base = SHAPES[shape]
    dense = INSERTIONS[insertion](base)
    assert len(dense) > len(base)
    got = tpa._principal_axis(_poly(dense))
    want = tpa._principal_axis(_poly(base))
    assert got == want, f"{shape} / {insertion}: {got} != {want}"


@pytest.mark.parametrize("shape", sorted(SHAPES))
@pytest.mark.parametrize("bearing", BEARINGS)
def test_the_axis_is_insertion_invariant_at_every_bearing(
        tpa, shape, bearing):
    """Rotated, to float tolerance.  Once a ring is rotated a
    "collinear" vertex is only collinear to float precision and can land
    a hair OUTSIDE the hull, which is worth a fraction of a
    micro-degree — against the old fit's 0.37° / 15.03° / 90.00° on the
    very same insertions."""
    base = _rot(SHAPES[shape], bearing)
    for label, fn in sorted(INSERTIONS.items()):
        moved = _angle_between(tpa._principal_axis(_poly(fn(base))),
                               tpa._principal_axis(_poly(base)))
        assert moved < 1e-5, f"{shape} @ {bearing}° / {label}: {moved}°"


def test_the_old_fit_moved_and_this_is_what_it_cost(tpa):
    """The defect, measured — so the twin fails if someone restores the
    old form, and the issue's numbers have a source.

    These are the corridor shapes the instrument meets, not contrived
    ones: a widening mouth, a fork's turning arm, a near-square throat
    plate.
    """
    worst = {}
    for name, shp in SHAPES.items():
        base = _rot(shp, 23.0)
        worst[name] = max(
            _angle_between(_old_pca_axis(fn(base)), _old_pca_axis(base))
            for fn in INSERTIONS.values())
    # A clean rectangle was always safe — which is why this went unnoticed.
    assert worst["corridor"] == pytest.approx(0.0, abs=1e-9)
    assert worst["ramp"] > 0.3            # a widening mouth: ~0.37°
    assert worst["arm"] > 10.0            # a fork's turning arm: ~15.03°
    assert worst["plate"] > 80.0          # a near-square plate: ~90°
    # And the new fit holds all four.
    for name, shp in SHAPES.items():
        base = _rot(shp, 23.0)
        for fn in INSERTIONS.values():
            assert _angle_between(tpa._principal_axis(_poly(fn(base))),
                                  tpa._principal_axis(_poly(base))) < 1e-5


# ──────────────────────────────────────────────────────────────────
# 2. THE SIDE SPLIT DOES NOT MOVE  (the consequence, not the statistic)
# ──────────────────────────────────────────────────────────────────
def _band_for(pts, offset=3.0):
    """A ``tunnel_wall`` band standing off both long sides of a corridor
    — the ``(wid, ref, geom)`` triples ``_side_cover`` consumes."""
    from shapely.geometry import Polygon
    (x0, y0), (x1, _y1) = pts[0], pts[1]
    top = max(p[1] for p in pts)
    out = []
    for i, y in enumerate((y0 - offset, top + offset)):
        out.append((-900 - i, "tunnel_wall",
                    Polygon([(x0, y - 1.0), (x1, y - 1.0),
                             (x1, y + 1.0), (x0, y + 1.0)])))
    return out


def _cover_with(tpa, pts, band, fit):
    """``_side_cover``'s ``(left, right)`` for a corridor, split by the
    axis ``fit`` gives it.  ``body.centroid`` is what the tool passes."""
    body = _poly(pts)
    axis = fit(pts) if fit is _old_pca_axis else fit(body)
    assert axis is not None
    c = body.centroid
    return tpa._side_cover(body, band, "tunnel_wall", (c.x, c.y), axis)


#: Per-side coverage is a ratio of two shapely lengths, so a ring with
#: MORE vertices sums it in a different order and the last bit can
#: differ — 1 ULP, measured at 1.3e-16 worst over every shape and
#: insertion here.  That is float summation in ``ring.length``, not the
#: axis, which is bit-identical (``test_inserted_ring_vertices_leave_
#: the_axis_exactly_alone``).  The bar below is four orders of magnitude
#: under the smallest consequence and ten orders under what the retiring
#: fit moved.
SIDE_COVER_ULP = 1e-12


@pytest.mark.parametrize("shape", sorted(SHAPES))
@pytest.mark.parametrize("insertion", sorted(INSERTIONS))
def test_the_side_split_does_not_move_under_insertion(
        tpa, shape, insertion):
    """``_side_cover``'s ``(left, right)`` — THE discrete consequence.

    The axis decides which half-plane a stretch of the site's boundary
    falls in, and ``min(wl, wr)`` against the per-side bar is pass/fail.
    Same shape, same answer.
    """
    base = SHAPES[shape]
    dense = INSERTIONS[insertion](base)
    band = _band_for(base)
    got = _cover_with(tpa, dense, band, tpa._principal_axis)
    want = _cover_with(tpa, base, band, tpa._principal_axis)
    assert got == pytest.approx(want, abs=SIDE_COVER_ULP), \
        f"{shape} / {insertion}: {got} != {want}"
    # A measurement reading (0.0, 0.0) on both sides would satisfy the
    # equality above while measuring nothing.  The fixture is walled.
    assert max(want) > 0.0


@pytest.mark.parametrize("shape", sorted(SHAPES))
@pytest.mark.parametrize("insertion", sorted(INSERTIONS))
def test_no_per_side_bar_changes_its_verdict_under_insertion(
        tpa, shape, insertion):
    """The consequence as the instrument reports it: ``canonical``
    requires ``min(wl, wr) >= bar``.  Swept across every bar the tool
    could be run at, no verdict moves."""
    base = SHAPES[shape]
    band = _band_for(base)
    a = _cover_with(tpa, base, band, tpa._principal_axis)
    b = _cover_with(tpa, INSERTIONS[insertion](base), band,
                    tpa._principal_axis)
    for bar in [i / 20.0 for i in range(21)]:
        assert (min(a) >= bar) == (min(b) >= bar), \
            f"{shape} / {insertion} flipped at bar {bar}"


def test_the_old_fit_moved_the_side_split_and_flipped_a_verdict(tpa):
    """THE DEFECT, END TO END — why this is not a cosmetic refit.

    A fork's turning ARM, densified along both long edges: the retiring
    fit moved its per-side coverage by **0.111 / 0.114** — eleven points
    — where the hull rectangle moves it by 1.3e-16.  And the movement
    crosses a bar: at a 0.30 per-side bar the SAME arm read **FAIL
    before the insertion and PASS after it**, so a densification step
    could retire a real finding.
    """
    base = SHAPES["arm"]
    dense = INSERTIONS["both long edges x5"](base)
    band = _band_for(base)

    ob = _cover_with(tpa, base, band, _old_pca_axis)
    od = _cover_with(tpa, dense, band, _old_pca_axis)
    assert abs(od[0] - ob[0]) > 0.10
    assert abs(od[1] - ob[1]) > 0.10

    bar = 0.30
    assert min(ob) < bar <= min(od), (ob, od)      # FAIL -> PASS

    # The same arm, the same insertion, under the fit that landed.
    nb = _cover_with(tpa, base, band, tpa._principal_axis)
    nd = _cover_with(tpa, dense, band, tpa._principal_axis)
    assert nd == pytest.approx(nb, abs=SIDE_COVER_ULP)
    assert (min(nb) >= bar) == (min(nd) >= bar)


def test_the_centroid_the_split_uses_was_never_the_defect(tpa):
    """``_side_cover`` is handed ``body.centroid`` — shapely's AREA
    centroid, which is already insertion-invariant.  Only the AXIS was
    vertex-mass-weighted, so only the axis is changed here.  Stated as a
    test so the next reader does not go looking for a second fix."""
    for shape, shp in SHAPES.items():
        for fn in INSERTIONS.values():
            a, b = _poly(shp).centroid, _poly(fn(shp)).centroid
            assert (a.x, a.y) == pytest.approx((b.x, b.y), abs=1e-9), shape


def test_an_unmerged_run_verdict_does_not_move_under_insertion(tpa):
    """``_unmerged_pairs`` compares two surfaces' axes against
    ``bearing_tol_deg`` — a pass/fail on an angle, so it is the other
    discrete consumer.  Two collinear touching pieces of one run read
    the same verdict however either ring is densified."""
    class _P:                      # the patch's ``by_wid`` is all it uses
        def __init__(self, spread):
            self.by_wid = {w: type("W", (), {"elevs": e})
                           for w, e in spread.items()}

    a = [(0.0, 0.0), (100.0, 0.0), (100.0, 12.0), (0.0, 12.0)]
    b = [(100.0, 0.0), (200.0, 0.0), (200.0, 12.0), (100.0, 12.0)]
    patch = _P({1: [0.0, 5.0], 2: [5.0, 10.0]})          # both descend
    base = [(1, "tunnel_ramp", _poly(a)), (2, "tunnel_ramp", _poly(b))]
    assert tpa._unmerged_pairs(base, patch, 5.0, 0.5) == 1
    for fn in INSERTIONS.values():
        dense = [(1, "tunnel_ramp", _poly(fn(a))),
                 (2, "tunnel_ramp", _poly(fn(b)))]
        assert tpa._unmerged_pairs(dense, patch, 5.0, 0.5) == 1


# ──────────────────────────────────────────────────────────────────
# 3. A CLEAN CORRIDOR READS WHAT IT ALWAYS READ
# ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bearing", BEARINGS)
def test_a_clean_four_corner_corridor_reads_what_the_old_pca_read(
        tpa, bearing):
    """No reference moves for a corridor that was never the problem.

    A rectangle's dominant-variance direction IS its long side, so the
    minimum-area rectangle of the hull reproduces the retiring answer —
    to float tolerance, and bit-identically at the bearings where no
    rotation error enters.
    """
    pts = _rot(CORRIDOR, bearing)
    assert _angle_between(tpa._principal_axis(_poly(pts)),
                          _old_pca_axis(pts)) < 1e-9


@pytest.mark.parametrize("short", (29.0, 27.0, 24.0, 20.0, 15.0, 6.0))
def test_it_agrees_with_the_old_pca_at_every_aspect_ratio_but_the_tie(
        tpa, short):
    """Down to a 30 x 29 m plate — aspect 1.034 — the two fits give the
    same direction.  The disagreement is confined to the EXACT tie."""
    pts = [(0.0, 0.0), (30.0, 0.0), (30.0, short), (0.0, short)]
    assert _angle_between(tpa._principal_axis(_poly(pts)),
                          _old_pca_axis(pts)) < 1e-9


def test_an_exact_square_has_no_long_axis_and_is_reported_as_such(tpa):
    """THE ONE SHAPE THE TWO FITS DISAGREE ON, and it is a tie, not an
    answer: every orientation of a square's bounding rectangle has the
    same area, so "the long axis of a square" does not exist.

    Both fits return an arbitrary direction there.  The new one's is at
    least INSERTION-INVARIANT and DETERMINISTIC, where the old one swung
    the full 90° on a single inserted vertex — so this is a strict
    improvement on a shape with no right answer, not a regression.  It is
    REPORTED here rather than tie-broken: which way a square-ish throat
    plate's sides face is a law question, not a tool's to decide.
    """
    sq = SQUARE
    # The disagreement is real and is a right angle.
    assert _angle_between(tpa._principal_axis(_poly(sq)),
                          _old_pca_axis(sq)) == pytest.approx(90.0)
    # The old fit moved on insertion; the new one does not.
    assert max(_angle_between(_old_pca_axis(fn(sq)), _old_pca_axis(sq))
               for fn in INSERTIONS.values()) > 80.0
    for fn in INSERTIONS.values():
        assert tpa._principal_axis(_poly(fn(sq))) == \
            tpa._principal_axis(_poly(sq))


# ──────────────────────────────────────────────────────────────────
# 4. ONE FIT, NOT TWO  +  DETERMINISM  +  DEGENERATE CONTRACTS
# ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("shape", sorted(SHAPES))
@pytest.mark.parametrize("bearing", BEARINGS)
def test_the_tool_binds_the_law_and_holds_no_second_fit(
        tpa, shape, bearing):
    """A second geometry fit is a second source of truth — the rule
    ``tests/test_runway_end_corners.py`` states for the runway axis and
    issue #190 acted on.  This tool's answer IS
    ``geometry._min_area_rect_of_points``'s long side, bit for bit."""
    from auto_patch_v2.constraints.geometry import _min_area_rect_of_points
    pts = _rot(SHAPES[shape], bearing)
    rect = _min_area_rect_of_points(pts)
    assert rect is not None
    assert tpa._principal_axis(_poly(pts)) == rect[0]


def test_the_source_carries_no_private_copy_of_the_closed_form(tpa):
    """In FACT, not just in contract: the retiring form's spelling is
    gone from the tool, so it cannot drift back in beside the binding."""
    src = TOOL_PATH.read_text(encoding="utf-8")
    body = src[src.index("def _principal_axis(poly):"):
               src.index("def _fmt(v):")]
    assert "svd" not in body.lower()
    assert "numpy" not in body
    assert "_min_area_rect_of_points" in body
    # and no other function grew one in its place
    assert "linalg" not in src


@pytest.mark.parametrize("shape", sorted(SHAPES) + ["square"])
def test_the_answer_does_not_depend_on_the_order_vertices_arrive_in(
        tpa, shape):
    """The retiring ``numpy.linalg.svd`` gave 2 distinct answers for a
    shuffled corridor and 4 for a shuffled arm; a shape's axis is a
    property of the shape."""
    pts = _rot(dict(SHAPES, square=SQUARE)[shape], 23.0)
    answers = set()
    for seed in range(12):
        p = list(pts)
        random.Random(seed).shuffle(p)
        answers.add(tpa._principal_axis(_poly(p)))
    assert len(answers) == 1, answers


def test_a_closed_ring_reads_what_the_same_ring_open_reads(tpa):
    """A shapely ring repeats its first vertex, and ``to_osm`` writes the
    repeat.  Under the old fit that repeat was extra MASS at one corner;
    under the hull it is a duplicate point the hull drops."""
    for shape, shp in SHAPES.items():
        closed = _poly(shp + [shp[0]])
        assert tpa._principal_axis(closed) == \
            tpa._principal_axis(_poly(shp)), shape


def test_degenerate_rings_report_no_axis_rather_than_an_arbitrary_one(
        tpa):
    """``None`` is the contract every caller already handles (``if aa is
    None ... continue``, ``if _aax is None: continue``, ``if axis``).

    The old fit returned an arbitrary unit vector for a cloud with no
    extent, because a zero covariance's dominant eigenvector is whatever
    LAPACK says — a corridor direction invented from nothing.
    """
    from shapely.geometry import Polygon
    assert tpa._principal_axis(Polygon()) is None
    one = Polygon([(5.0, 5.0)] * 4)
    assert tpa._principal_axis(one) is None
    assert tpa._principal_axis(object()) is None          # not a polygon


def test_two_distinct_points_still_give_the_run_direction(tpa):
    """A ring collapsed onto a line has no width but still has a RUN,
    and the old fit answered for it too — so the contract is kept."""
    from shapely.geometry import Polygon
    line = Polygon([(0.0, 0.0), (50.0, 0.0), (25.0, 0.0)])
    assert tpa._principal_axis(line) == (1.0, 0.0)
