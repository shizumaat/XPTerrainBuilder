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


def test_73_thresholds_are_law_keys_and_zero_disarms():
    """The three thresholds are ``[placement]`` law keys
    (``structures.toml``), read at the ONE derivation site
    ``planar/cluster._outline_law``; 0 disarms the post and line tests."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar.cluster import _outline_law
    law = Law.for_airport("HECA")
    pl = law.tables.structures.placement
    assert (pl.post_max_area_m2, pl.post_max_extent_m,
            pl.flat_line_max_width_m) == (4.0, 3.0, 1.0)
    assert _outline_law(law) == (4.0, 3.0, 1.0)
    post = _PMember("objects/post.obj", [_part(2, _lat(40.2), _lat(41.2), height=4.8,
                                               lo0=_lo(10), lo1=_lo(11))])
    off = plan_clusters(_plan([_bldg(), post]), TOUCH, chain_min_height_m=2.5,
                        outline_law=(0.0, 0.0, 0.0))
    assert len(off) == 1 and len(off[0].rings) == 2      # the post draws again


# ── rule 2a: A POST STILL CHAINS, SO THE UNIT IS ONE (lane courtyards) ──

def _xy(lo, la):
    return ((lo - LO0) / M_LON, (la - 41.0) * 111_132.0)


def _two_halves(post_lo0, post_lo1):
    """Two 20 x 20 m walled halves 1.2 m apart (wider than the 0.5 m
    close), and a 5 m post at lon ``post_lo0 .. post_lo1`` (metres)."""
    a = _PMember("objects/a.obj", [_part(1, _lat(0), _lat(20), height=9.0,
                                         lo0=_lo(0), lo1=_lo(20))])
    b = _PMember("objects/b2.obj", [_part(2, _lat(0), _lat(20), height=9.0,
                                          lo0=_lo(21.2), lo1=_lo(41.2))])
    post = _PMember("objects/post.obj", [_part(3, _lat(9), _lat(9.8), height=5.0,
                                               lo0=_lo(post_lo0), lo1=_lo(post_lo1))])
    return plan_clusters(_plan([a, b, post]), TOUCH, chain_min_height_m=2.5)


def test_73_2a_a_post_touching_both_pieces_closes_the_outline():
    """OTHH ``OTHH_Mace.obj`` (unit:58#0, ONE body): its two canopy rows
    touch only through 39 posts 5 m tall, 0.83 m2, 1.28 m gap; without
    the close the one body minted TWO pads (5,869 -> 3,107 + 2,699 m2)."""
    from auto_patch_v2.geom import cluster_outlines
    cl = _two_halves(20.2, 21.0)
    assert len(cl) == 1 and cl[0].bodies == 3 and len(cl[0].bridges) == 1
    split, c0 = cluster_outlines(cl, _xy, TOUCH)
    assert len(split) == 2 and c0["post_bridged"] == 0
    one, c1 = cluster_outlines(cl, _xy, TOUCH, bridge_m=1.0)
    assert len(one) == 1 and c1["post_bridged"] == 1
    g = one[0][2]
    assert not g.interiors and 800.0 < g.area < 805.0     # the post and its two gap fans only


def test_73_2a_a_post_reaching_one_piece_adds_nothing():
    """A post that touches ONE piece closes nothing (that is the lace)."""
    from auto_patch_v2.geom import cluster_outlines
    cl = _two_halves(19.0, 19.8)            # inside the first half's reach only
    got, c = cluster_outlines(cl, _xy, TOUCH, bridge_m=1.0)
    assert c["post_bridged"] == 0
    assert sum(len(q.rings) for q in cl) == 2


def test_73_2a_a_flat_line_across_open_ground_closes_nothing():
    """HECA ``Plastic.obj``: 0.72 m flat strips 90-150 m long ran from the
    192,033 m2 piece to a 1,911 m2 one 2.72 m away; drawing them redrew
    the lace (holes 32 -> 84).  No plan point of the line lies within
    ``bridge_m`` of both pieces, so nothing closes."""
    import dataclasses as _dc
    from auto_patch_v2.geom import cluster_outlines

    def sq(la0, la1, lo0, lo1):
        return ((_lat(la0), _lo(lo0)), (_lat(la1), _lo(lo0)),
                (_lat(la1), _lo(lo1)), (_lat(la0), _lo(lo1)))
    base = _two_halves(20.2, 21.0)[0]
    far = _dc.replace(base, rings=(sq(0, 20, 0, 20), sq(0, 20, 23, 43)),
                      bridges=(sq(9.4, 9.8, 5, 38),))
    got, c = cluster_outlines([far], _xy, TOUCH, bridge_m=1.0)
    assert c["post_bridged"] == 0 and len(got) == 2
    near = _dc.replace(far, rings=(sq(0, 20, 0, 20), sq(0, 20, 21.5, 41.5)))
    got2, c2 = cluster_outlines([near], _xy, TOUCH, bridge_m=1.0)
    assert c2["post_bridged"] == 1 and len(got2) == 1   # a 1.5 m gap closes


def test_73b_post_bridge_gap_is_per_side_1_25_bridges_2_06_not_2_72():
    """Owner RULINGS 2026-09-29c / 29g (Q-73b): OTHH terminal parking
    ``unit:24#0`` is ONE pad — its halves (33,392 + 21,316 m2) stand
    2.06 m apart joined by markings and one 4.4 m post, and the dry mint
    on ``frames/sheetchain/OTHH.pkl`` reads 54,714 m2 in one piece at the
    law value (``tools/pad_gap_diff.py``).  The key is PER SIDE, so the
    shipped 1.25 bridges a plan gap up to 2.5 m: 2.06 m closes, HECA's
    2.72 m lace gap (``Plastic.obj``) does not."""
    import dataclasses as _dc
    from auto_patch_v2.geom import cluster_outlines
    from auto_patch_v2.law import Law
    for icao in ("OTHH", "HECA", "KCLT"):
        assert Law.for_airport(icao).tables.structures.placement.post_bridge_gap_m == 1.25
    import auto_patch_v2.law.rebake_schema as _rs
    defaults = [f.default for cls in vars(_rs).values() if _dc.is_dataclass(cls)
                for f in _dc.fields(cls) if f.name == "post_bridge_gap_m"]
    assert defaults == [1.25]                                # the schema default agrees
    gap_m = Law.for_airport("OTHH").tables.structures.placement.post_bridge_gap_m

    def sq(la0, la1, lo0, lo1):
        return ((_lat(la0), _lo(lo0)), (_lat(la1), _lo(lo0)),
                (_lat(la1), _lo(lo1)), (_lat(la0), _lo(lo1)))
    base = _two_halves(20.2, 21.0)[0]

    def arm(gap):                     # a post spanning the whole gap
        c = _dc.replace(base, rings=(sq(0, 20, 0, 20), sq(0, 20, 20 + gap, 40 + gap)),
                        bridges=(sq(9.0, 9.8, 19.8, 20.2 + gap),))
        return cluster_outlines([c], _xy, TOUCH, bridge_m=gap_m)
    got, c = arm(2.06)
    assert c["post_bridged"] == 1 and len(got) == 1          # the garage: one pad
    got, c = arm(2.72)
    assert c["post_bridged"] == 0 and len(got) == 2          # the lace stays open
    got, c = cluster_outlines([_dc.replace(base, rings=(sq(0, 20, 0, 20), sq(0, 20, 22.06, 42.06)),
                                           bridges=(sq(9.0, 9.8, 19.8, 22.26),))],
                              _xy, TOUCH, bridge_m=1.0)
    assert c["post_bridged"] == 0 and len(got) == 2          # the pre-29c value missed it


def test_pad_gap_diff_reports_the_merge_with_its_plan_gap():
    """``tools/pad_gap_diff.py`` (the instrument RULINGS 2026-09-29g cites):
    over one cluster minted at two bridge values it names the MERGE, the
    pieces joined and their plan gap, and the mint call is the classify
    mint's own (``cluster_outlines`` — the arms here are the same call)."""
    import dataclasses as _dc
    import importlib.util
    from pathlib import Path
    from auto_patch_v2.geom import cluster_outlines
    spec = importlib.util.spec_from_file_location(
        "pad_gap_diff", Path(__file__).resolve().parents[2] / "tools" / "pad_gap_diff.py")
    pgd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pgd)

    def sq(la0, la1, lo0, lo1):
        return ((_lat(la0), _lo(lo0)), (_lat(la1), _lo(lo0)),
                (_lat(la1), _lo(lo1)), (_lat(la0), _lo(lo1)))
    base = _two_halves(20.2, 21.0)[0]
    c = _dc.replace(base, rings=(sq(0, 20, 0, 20), sq(0, 20, 22.06, 42.06)),
                    bridges=(sq(9.0, 9.8, 19.8, 22.26),))
    ga, _ = cluster_outlines([c], _xy, TOUCH, bridge_m=1.0)
    gb, _ = cluster_outlines([c], _xy, TOUCH, bridge_m=1.25)
    r = pgd.diff(ga, gb, lambda x, y: (y, x))
    assert [(x["pads_a"], x["pads_b"]) for x in r["changed"]] == [(2, 1)]
    (m,) = [e for e in r["events"] if e["kind"] == "merge"]
    assert m["gaps_m"] == [2.06] and sorted(m["pieces_m2_a"]) == [400, 400]
    assert pgd.diff(ga, ga, lambda x, y: (y, x)) == {"changed": [], "events": []}
