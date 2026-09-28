"""§16g (10) (2) AMENDED — POSTS AND FLAT LINES CHAIN BUT DRAW NO OUTLINE
(issue #73, spec-author ruling to lane ``lacepad``).

With c16ccee8's wall-chord reading, ``building13``'s posts read as walls
and their bodies joined its cluster; their rings (and their bodies' flat
ground strips) made the pad outline LACE — 37 -> 184 holes over the
apron.  A component small in BOTH plan dimensions (a post) or flat and
under a metre wide (a line) still counts for the body's height and the
chain; it never draws the cluster's pad outline
(``placement_family.draws_outline``)."""
from __future__ import annotations

from auto_patch_v2.airport.placement_family import (
    FLAT_LINE_MAX_WIDTH_M, POST_MAX_AREA_M2, POST_MAX_EXTENT_M, draws_outline,
    plan_clusters)

from test_v2connector import _lat, _PMember  # noqa: E402
from test_v2padcluster import TOUCH, _part, _plan  # noqa: E402

LO0 = -3.0000
M_LON = 1.0 / 83_950.0          # ~1 m of longitude at 41 N


def _lo(m):
    return LO0 + m * M_LON


def _bldg():
    return _PMember("objects/b.obj", [_part(1, _lat(0), _lat(40), height=9.0,
                                            lo0=_lo(0), lo1=_lo(40))])


def _clusters(extra):
    return plan_clusters(_plan([_bldg(), *extra]), TOUCH, chain_min_height_m=2.5)


def test_73_a_POST_chains_but_draws_no_outline():
    post = _PMember("objects/post.obj", [_part(2, _lat(40.2), _lat(41.2), height=4.8,
                                               lo0=_lo(10), lo1=_lo(11))])
    got = _clusters([post])
    assert len(got) == 1 and got[0].bodies == 2 and got[0].walled == 2
    assert len(got[0].rings) == 1           # the building alone draws


def test_73_a_WALL_draws():
    wall = _PMember("objects/wall.obj", [_part(2, _lat(40.2), _lat(60.2), height=3.1,
                                               lo0=_lo(10), lo1=_lo(10.3))])
    got = _clusters([wall])
    assert len(got) == 1 and got[0].bodies == 2
    assert len(got[0].rings) == 2


def test_73_a_FLAT_LINE_in_a_walled_body_draws_nothing_a_slab_does():
    # one member, two parts: a rod (walls the body) and a flat strip
    strip = _part(3, _lat(40.2), _lat(60.2), height=0.06, lo0=_lo(20), lo1=_lo(20.2))
    rod = _part(2, _lat(40.2), _lat(40.4), height=8.5, lo0=_lo(20), lo1=_lo(20.2))
    m = _PMember("objects/plastic.obj", [rod])
    m2 = _PMember("objects/plastic2.obj", [strip])
    got = _clusters([m, m2])
    assert len(got) == 2                     # the strip is a leaf body
    main = max(got, key=lambda q: q.bodies)
    assert main.bodies == 2 and len(main.rings) == 1
    leaf = min(got, key=lambda q: q.bodies)
    assert leaf.walled == 0 and len(leaf.rings) == 0
    slab = _PMember("objects/slab.obj", [_part(4, _lat(40.2), _lat(60.2), height=0.3,
                                               lo0=_lo(0), lo1=_lo(20))])
    got = _clusters([slab])
    assert sum(len(q.rings) for q in got) == 2


def test_73_chaining_is_unchanged_by_the_outline_rule():
    """The chain reads every ring (``_Shim.rings``); only the outline
    (``PlanCluster.rings``) drops posts and lines."""
    posts = [_PMember(f"objects/p{i}.obj",
                      [_part(10 + i, _lat(40.2), _lat(41.2), height=4.8,
                             lo0=_lo(4 * i), lo1=_lo(4 * i + 1))])
             for i in range(8)]
    got = _clusters(posts)
    assert len(got) == 1 and got[0].bodies == 9 and got[0].walled == 9
    assert len(got[0].rings) == 1


def test_73_draws_outline_thresholds():
    class P:
        pass
    p = P()
    p.height_m = 5.0
    p.box = (_lat(0), _lo(0), _lat(1.5), _lo(1.5))
    p.rings = (((_lat(0), _lo(0)), (_lat(1.5), _lo(0)), (_lat(1.5), _lo(1.5)),
                (_lat(0), _lo(1.5))),)
    ml, mo = 111_132.0, 83_950.0
    assert not draws_outline(p, 2.5, ml, mo)                 # a post
    p.box = (_lat(0), _lo(0), _lat(1.5), _lo(POST_MAX_EXTENT_M + 1))
    p.rings = (((_lat(0), _lo(0)), (_lat(1.5), _lo(0)),
                (_lat(1.5), _lo(POST_MAX_EXTENT_M + 1)),
                (_lat(0), _lo(POST_MAX_EXTENT_M + 1))),)
    assert draws_outline(p, 2.5, ml, mo)                     # tall: a wall
    p.height_m = 0.1
    assert draws_outline(p, 2.5, ml, mo)                     # 1.5 m wide: > line
    assert POST_MAX_AREA_M2 == 4.0 and FLAT_LINE_MAX_WIDTH_M == 1.0
