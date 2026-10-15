"""Issue #610 (lane roofs2, owner sim read of 1.0.392): KCLT's covered
fuel canopy (``007_ALB``, 35.2177062,-80.9305842) — ten posts at y 0, a
roof at 4.8 and beams at 5.34-5.45 with no feet — took its zero on a beam
stand-in, read elevated and rode a kiosk 40 m away, its posts 2.5-2.7 m
over the mesh.  ``anchor_rule.roof_on_posts`` names the shape (footed
parts taller than their plan span, reaching the feetless roof, which
covers more plan than they do) and ``anchor_for`` re-takes an anchor that
landed on such a body's stand-in from the posts' feet alone.  Every other
body reads as before — the shape is the whole rule (the general re-take,
lane roofs610's aec5725d2, moved 54 HECA bodies and was reverted, RULINGS
2026-10-14j (3)).
"""
from __future__ import annotations

from auto_patch_v2.airport import anchor_rule as _ar


def _posts(n, y=0.0):
    return tuple((40.0 + 1e-5 * k, -3.0, y, ((40.0 + 1e-5 * k, -3.0, y),))
                 for k in range(n))


def _surface(la, lo):
    # the roof's centroid reads the lowest ground: the low-side rule's pick
    return 214.9 if lo > -2.99999 else 215.0 + (la - 40.0) * 4e3


ROOF = (40.00002, -2.99998, 4.8, ())


def _geom(parts, solids):
    return _ar.BodyGeometry(parts, 40.0, -3.0, solids=solids)


def test_a_canopy_on_posts_anchors_on_its_posts_not_its_roof():
    posts = _posts(6)
    g = _geom(posts + (ROOF,),
              ((4.8, 7.1, 2.7),) * 6 + ((6.0, 1184.0, 34.0),))
    assert _ar.roof_on_posts(g, 0.3)
    a = _ar.anchor_for("other", g, _surface, tol_m=0.3)
    assert a.y_zero == 0.0, (a.y_zero, a.reason)
    assert abs(float(a.surface_z) - 215.0) < 0.25
    # main's reading (no solids published): the roof stands in and wins
    b = _ar.anchor_for("other", _ar.BodyGeometry(posts + (ROOF,), 40.0, -3.0),
                       _surface, tol_m=0.3)
    assert b.y_zero == 4.8


def test_not_a_roof_on_posts_reads_as_before():
    posts = _posts(6)
    # a pane INSIDE the walls' height: the walls reach above it
    pane = (40.00002, -2.99998, 2.0, ())
    g = _geom(posts + (pane,), ((4.8, 7.1, 2.7),) * 6 + ((3.0, 50.0, 8.0),))
    assert not _ar.roof_on_posts(g, 0.3)
    # squat footed parts (a plinth, a step) are no posts
    g = _geom(posts + (ROOF,), ((4.8, 40.0, 6.0),) * 6 + ((6.0, 1184.0, 34.0),))
    assert not _ar.roof_on_posts(g, 0.3)
    # a feetless part smaller than its supports (a pane over a pane)
    g = _geom(posts + (ROOF,), ((4.8, 7.1, 2.7),) * 6 + ((6.0, 4.0, 2.0),))
    assert not _ar.roof_on_posts(g, 0.3)
    # a roof that does not meet the posts' tops
    g = _geom(posts + (ROOF,), ((3.0, 7.1, 2.0),) * 6 + ((6.0, 1184.0, 34.0),))
    assert not _ar.roof_on_posts(g, 0.3)
    # a plan with no heights publishes no solids
    assert not _ar.roof_on_posts(_geom(posts + (ROOF,), ()), 0.3)
