"""THE RUNWAY AXIS IS A FUNCTION OF THE RUNWAY'S CORNERS (issue #190,
owner ruling ``RULINGS 2026-10-02v`` (7)).

``grade_law.runway_axis_and_width`` was a vertex-count-weighted PCA about
the CENTROID, so one vertex inserted anywhere on a runway ring tilted the
axis, moved the centroid, and with them every footprint built from them —
the graded strip, the RESA transverse band, the RAOA ring, the wall
keepout.  Measured under the margin-0 predicate: ONE extra ring vertex
2.6 km from a census row read 257 strip stations against 318 (#190, the
root cause under #116).

The axis is now the LONG SIDE of the minimum-area rotated rectangle of
the ring cloud's CONVEX HULL.  A vertex inserted ON an edge — a
densification step, a tile cut, a crossing split, a closed ring's
repeated first vertex — lies on or inside that hull, so it changes the
answer by NOTHING, not by a little.  That is the whole claim, and these
twins are what hold it:

  §1  insertion invariance, at the law function, to exact float equality;
  §2  the clean 4-corner runway still reads exactly what the PCA read, so
      this is a change of INVARIANT, not of law;
  §3  LOCKSTEP — the three live spellings of the fit (the law, the
      census's transcription, v2's mirror) return bit-identical answers,
      because the emitter and the census must never disagree about where
      a strip is.

The STATION-SET half of the claim (the reader visiting the same strip
stations) lives with the rest of #116 in
``tests/test_strip_station_invariance.py``.
"""
from __future__ import annotations

import math
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(_REPO, "src"), os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch.grade_law import runway_axis_and_width          # noqa: E402
from auto_patch_v2.constraints.geometry import (                # noqa: E402
    principal_axis as _v2_principal_axis)
from harness.law_support.grade_law import (                     # noqa: E402
    runway_axis_and_width as _census_axis)

#: The issue's own runway: 3,600 m x 45 m, vertices every 30 m.
_LENGTH_M = 3600.0
_HALF_WIDTH_M = 22.5
_SPACING_M = 30.0
#: Where the inserted vertex goes — deliberately NOT a multiple of the
#: spacing, so it is a genuinely new vertex strictly between two emitted
#: ones, and 1 km from the far end (the issue's "2.6 km from the row").
_INSERT_AT_M = 2600.0
#: Every assertion below is EXACT equality in metres; this is the float
#: slack for the rotated arms, where the two spellings differ only in the
#: order they multiply the same numbers.
_EXACT_M = 1e-9


def _corners(length_m=_LENGTH_M, half_width_m=_HALF_WIDTH_M):
    """The clean 4-corner runway rectangle, counter-clockwise."""
    return [(0.0, -half_width_m), (length_m, -half_width_m),
            (length_m, half_width_m), (0.0, half_width_m)]


def _densified(length_m=_LENGTH_M, half_width_m=_HALF_WIDTH_M,
               spacing_m=_SPACING_M):
    """The same rectangle as a real emitted ring carries it: both long
    edges stepped at ``spacing_m``."""
    n = int(round(length_m / spacing_m)) + 1
    xs = [i * spacing_m for i in range(n)]
    return ([(x, -half_width_m) for x in xs]
            + [(x, half_width_m) for x in reversed(xs)])


def _rotate(pts, deg, dx=1234.5, dy=-987.6):
    """``pts`` in a frame that is neither axis-aligned nor centred — a
    real layout frame, where nothing is exact for free."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(x * c - y * s + dx, x * s + y * c + dy) for x, y in pts]


def _axis_angle_deg(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0


def _same(got, want, what):
    """``(axis_a, axis_b, width)`` equal to the float slack."""
    assert got is not None and want is not None, f"{what}: degenerate fit"
    (ga, gb, gw), (wa, wb, ww) = got, want
    assert math.dist(ga, wa) < _EXACT_M, (
        f"{what}: axis end A moved {math.dist(ga, wa):.6f} m")
    assert math.dist(gb, wb) < _EXACT_M, (
        f"{what}: axis end B moved {math.dist(gb, wb):.6f} m")
    assert abs(gw - ww) < _EXACT_M, (
        f"{what}: width moved {abs(gw - ww):.6f} m")
    assert abs(_axis_angle_deg(ga, gb) - _axis_angle_deg(wa, wb)) < _EXACT_M, (
        f"{what}: axis tilted")


# ══════════════════════════════════════════════════════════════════════
# §1  INSERTION INVARIANCE
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("rotation_deg", [0.0, 23.0, 90.0, -61.5])
def test_one_extra_collinear_vertex_at_2_6_km_changes_nothing(rotation_deg):
    """THE ARM THAT BITES (#190).  A 3,600 m runway judged WITH and
    WITHOUT one extra collinear ring vertex 2.6 km along: identical axis
    and identical width.  Under the PCA this tilted the axis and dragged
    the centroid toward the denser edge."""
    base = _densified()
    inserted = sorted(set(base) | {(_INSERT_AT_M, -_HALF_WIDTH_M)})
    assert len(set(inserted)) == len(set(base)) + 1, (
        "the fixture inserted no new vertex")
    _same(runway_axis_and_width(_rotate(inserted, rotation_deg)),
          runway_axis_and_width(_rotate(base, rotation_deg)),
          f"one inserted vertex at {rotation_deg} deg")


@pytest.mark.parametrize("rotation_deg", [0.0, 23.0, -61.5])
def test_a_densified_ring_equals_the_four_corner_ring(rotation_deg):
    """Densification is not geometry: 242 vertices on the rectangle's
    edges answer exactly what its 4 corners answer."""
    _same(runway_axis_and_width(_rotate(_densified(), rotation_deg)),
          runway_axis_and_width(_rotate(_corners(), rotation_deg)),
          f"densified vs 4-corner at {rotation_deg} deg")


def test_a_one_sided_densification_keeps_the_axis_on_the_centreline():
    """The PCA's worst case, and the reason this is not a cosmetic fix: a
    ring densified along ONE long edge only (what a crossing split or a
    stub junction leaves) pulled the vertex-mass centroid 21.8 m off the
    centreline, so the "centreline axis" ran along the runway EDGE.  The
    hull rectangle's centre cannot move with vertex count."""
    n = int(_LENGTH_M / _SPACING_M) + 1
    one_sided = ([(i * _SPACING_M, -_HALF_WIDTH_M) for i in range(n)]
                 + [(_LENGTH_M, _HALF_WIDTH_M), (0.0, _HALF_WIDTH_M)])
    a, b, width = runway_axis_and_width(one_sided)
    assert a[1] == pytest.approx(0.0, abs=_EXACT_M)
    assert b[1] == pytest.approx(0.0, abs=_EXACT_M)
    assert width == pytest.approx(2.0 * _HALF_WIDTH_M, abs=_EXACT_M)


def test_the_closed_spelling_of_a_ring_equals_the_open_one():
    """``rsa`` amendment 4 measured 0.27-0.98 m of footprint drift from
    the repeated first vertex alone, and mitigated it by agreeing to pass
    the open ring everywhere.  The duplicate is now a no-op, so the
    agreement is no longer load-bearing."""
    ring = _densified()
    _same(runway_axis_and_width(ring + [ring[0]]),
          runway_axis_and_width(ring), "closed vs open ring")


def test_the_order_vertices_arrive_in_does_not_matter():
    """A tile cut leaves one runway as several ways and the caller
    concatenates them; the fit must not depend on how."""
    ring = _densified()
    _same(runway_axis_and_width(ring[57:] + ring[:57]),
          runway_axis_and_width(ring), "rotated arrival order")
    _same(runway_axis_and_width(sorted(ring)),
          runway_axis_and_width(ring), "sorted arrival order")


def test_a_vertex_strictly_inside_the_ring_changes_nothing():
    """The #116 fixture's own perturbation: a vertex 1 mm inside the
    runway's own edge."""
    ring = _densified()
    _same(runway_axis_and_width(ring + [(_INSERT_AT_M,
                                         -_HALF_WIDTH_M + 0.001)]),
          runway_axis_and_width(ring), "interior vertex")


# ══════════════════════════════════════════════════════════════════════
# §2  IT IS THE SAME LAW ON A CLEAN RUNWAY
# ══════════════════════════════════════════════════════════════════════

def _pca_axis_and_width(points):
    """The PCA + centroid fit this function carried until 2026-10-02,
    kept HERE and nowhere else: §2 is the claim that the two agree on a
    clean 4-corner runway, and a claim about the old answer needs the old
    answer."""
    pts = [(float(x), float(y)) for (x, y) in points]
    n = len(pts)
    if n < 2:
        return None
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = syy = sxy = 0.0
    for x, y in pts:
        ddx, ddy = x - cx, y - cy
        sxx += ddx * ddx
        syy += ddy * ddy
        sxy += ddx * ddy
    tr = sxx + syy
    disc = max(0.0, (0.5 * tr) ** 2 - (sxx * syy - sxy * sxy))
    lam = 0.5 * tr + math.sqrt(disc)
    if abs(sxy) > 1e-9:
        ux, uy = lam - syy, sxy
    else:
        ux, uy = (1.0, 0.0) if sxx >= syy else (0.0, 1.0)
    norm = math.hypot(ux, uy)
    if norm < 1e-12:
        return None
    ux, uy = ux / norm, uy / norm
    along = [(x - cx) * ux + (y - cy) * uy for x, y in pts]
    across = [(x - cx) * -uy + (y - cy) * ux for x, y in pts]
    s0, s1 = min(along), max(along)
    if s1 - s0 <= 0.0:
        return None
    return ((cx + s0 * ux, cy + s0 * uy), (cx + s1 * ux, cy + s1 * uy),
            max(across) - min(across))


@pytest.mark.parametrize("rotation_deg", [0.0, 23.0, -61.5])
@pytest.mark.parametrize("ring", ["corners", "densified"])
def test_the_clean_runway_reads_exactly_what_the_pca_read(ring, rotation_deg):
    """A change of INVARIANT, not of law.  A rectangle's dominant-variance
    direction IS its long side and its centroid IS its centre, so on the
    shape a runway actually is the two fits agree — which is why no
    reference moves for a symmetrically densified runway."""
    pts = _rotate(_corners() if ring == "corners" else _densified(),
                  rotation_deg)
    _same(runway_axis_and_width(pts), _pca_axis_and_width(pts),
          f"{ring} at {rotation_deg} deg vs the PCA")


def test_the_centreline_is_still_not_the_diagonal():
    """The alternative rejected when the PCA landed is still rejected: the
    longest-vertex PAIR of a 3,600 x 45 m rectangle is its diagonal, 0.7
    deg off the centreline."""
    a, b, width = runway_axis_and_width(_corners())
    assert width == pytest.approx(2.0 * _HALF_WIDTH_M)
    assert _axis_angle_deg(a, b) == pytest.approx(0.0, abs=_EXACT_M)
    assert math.dist(a, b) == pytest.approx(_LENGTH_M)
    diagonal_deg = math.degrees(math.atan2(2.0 * _HALF_WIDTH_M, _LENGTH_M))
    assert diagonal_deg > 0.5, "the fixture is too square to make the point"


def test_a_degenerate_cloud_still_says_none():
    assert runway_axis_and_width([]) is None
    assert runway_axis_and_width([(0.0, 0.0)]) is None
    assert runway_axis_and_width([(1.0, 2.0)] * 9) is None
    # all-collinear: a real axis, zero width (the pre-fix contract)
    assert runway_axis_and_width(
        [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]) == ((0.0, 0.0), (2.0, 0.0), 0.0)


# ══════════════════════════════════════════════════════════════════════
# §3  LOCKSTEP — THE THREE LIVE SPELLINGS ARE ONE ANSWER
# ══════════════════════════════════════════════════════════════════════

def _clouds():
    """Every shape the fit meets, plus pseudo-random ones: the lockstep
    claim is about the FUNCTION, not about one runway."""
    import random
    out = [_corners(), _densified(), _densified() + [(_INSERT_AT_M, -22.5)],
           _rotate(_densified(), 23.0), _rotate(_densified(), -61.5),
           # a tile-clipped ring with an oblique end cap
           [(0.0, -22.5), (3600.0, -22.5), (3520.0, 22.5), (0.0, 22.5)],
           [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)], [(0.0, 0.0), (10.0, 4.0)]]
    rng = random.Random(190)
    for _ in range(60):
        out.append([(rng.uniform(-3000.0, 3000.0), rng.uniform(-200.0, 200.0))
                    for _ in range(rng.randint(2, 40))])
    return out


def test_the_census_transcription_answers_what_the_law_answers():
    """``tools/harness/law_support/grade_law.py`` is the census's copy of
    the law (ruling (d) of the v1-retirement stage-B brief, twinned for
    TEXTUAL identity in ``tests/test_law_support.py``).  This is the same
    promise from the other end: identical answers, bit for bit, so the
    surface we build and the surface we census cannot classify one strip
    two ways."""
    for pts in _clouds():
        assert _census_axis(pts) == runway_axis_and_width(pts), pts[:4]


def test_v2s_mirror_answers_what_the_law_answers():
    """``auto_patch_v2.constraints.geometry.principal_axis`` is the fit
    BOTH the v2 constraint generators (``constraints/strips.py``,
    ``constraints/apron.py``) and the v2 verifiers (``verify/strips.py``,
    ``verify/runway.py``, ``verify/structures.py``) bind — the emitter and
    the census moving together, which is what ruling 2026-10-02v (7)
    requires."""
    for pts in _clouds():
        assert _v2_principal_axis(pts) == runway_axis_and_width(pts), pts[:4]


def test_the_runway_end_corner_tool_binds_the_law_rather_than_copying_it():
    """``tools/runway_end_ground.py`` carried its OWN transcription of the
    old closed form; a tool that must not "fit the runway differently from
    the law that priced it" cannot hold a second copy through a change of
    the fit."""
    import runway_end_ground as REG
    for pts in _clouds():
        law = runway_axis_and_width(pts)
        got = REG._principal_axis(pts)
        if law is None or math.dist(law[0], law[1]) <= 0.0:
            assert got is None
            continue
        a, b, unit, length, width = got
        assert (a, b, width) == law
        assert length == pytest.approx(math.dist(law[0], law[1]))
        assert math.hypot(*unit) == pytest.approx(1.0)
