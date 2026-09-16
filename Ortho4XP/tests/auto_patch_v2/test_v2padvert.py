"""RULINGS 2026-09-14as (i) — THE PAD DERIVATION LEAVES THE AIRSIDE VERTEX
SET ALONE, and RULINGS 2026-09-14au — THE PAD'S SKIRT YIELDS.

Both laws SHIP DISARMED on this branch (``[placement] pad_airside_clip``
false; the skirt relaxation armed only with ``[design] staged_solve``,
which is itself false), so every twin here ARMS what it reads, exactly as
the ``pad_from_cluster`` twins do.
"""
from __future__ import annotations

import dataclasses as _dc

from shapely.geometry import Polygon

from auto_patch_v2.geom.cluster_outline import AirsideRim, airside_vertex_snap
from auto_patch_v2.law import Law


def _law():
    return Law.for_airport("ZZZZ")


def _armed(law, *, clip=True, snap_max=5.0):
    p = _dc.replace(law.tables.structures.placement,
                    pad_airside_clip=clip, pad_airside_snap_max_m=snap_max)
    st = _dc.replace(law.tables.structures, placement=p)
    return _dc.replace(law, tables=_dc.replace(law.tables, structures=st))


def _staged(law, on=True):
    d = _dc.replace(law.tables.emit.design, staged_solve=on)
    em = _dc.replace(law.tables.emit, design=d)
    return _dc.replace(law, tables=_dc.replace(law.tables, emit=em))


# ── (i) the rim snap ────────────────────────────────────────────────────

def test_a_clip_crossing_point_is_quantised_to_the_rims_own_node():
    """The clip leaves the pad's rim running ALONG the airside boundary
    between two CROSSING POINTS, and those points are not rim nodes: noded
    into the arrangement they SPLIT the airside edge and mint a vertex
    that exists only because the pad does.  Within
    ``pad_airside_snap_max_m`` the crossing point moves to the rim's
    nearest node — the pad yields, the airside never does."""
    rim = AirsideRim(Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
                     0.0, 5.0)
    counts: dict = {}
    # a pad hanging off the south edge, crossing at x = 3 and x = 7 —
    # both within 5 m of a rim node (the corners at x = 0 and x = 10)
    got = airside_vertex_snap(
        Polygon([(3, 0), (7, 0), (7, -4), (3, -4)]), rim, counts)
    assert counts.get("snapped_pads") == 1
    assert counts.get("snapped_vertices") == 2
    on_rim = {round(x, 6) for x, y in got.exterior.coords if abs(y) < 1e-9}
    assert 3.0 not in on_rim and 7.0 not in on_rim   # the crossings are gone
    assert {0.0, 10.0} <= on_rim                     # onto the rim's nodes
    # THE AIRSIDE IS NEVER TAKEN: the snap may not push the pad back in
    assert got.intersection(rim.airside).area <= 1e-9


def test_a_crossing_too_far_from_any_node_stands_and_is_counted():
    """Quantising moves the pad ALONG the rim by that rim's own vertex
    spacing — at HECA p50 4.3 m but up to 87.6 m, and a 40 m synthetic
    shed's corner travelled 30 m and stopped being that shed.  Beyond
    ``pad_airside_snap_max_m`` the crossing point STANDS: one minted
    airside vertex is the smaller defect, and it is COUNTED, never
    silently taken."""
    rim = AirsideRim(Polygon([(0, 0), (100, 0), (100, 100), (0, 100)]),
                     0.0, 5.0)
    counts: dict = {}
    got = airside_vertex_snap(
        Polygon([(40, 0), (60, 0), (60, -4), (40, -4)]), rim, counts)
    assert counts.get("snap_too_far") == 2
    assert counts.get("snap_too_far_max_m") == 40.0
    assert "snapped_pads" not in counts
    assert {round(x, 6) for x, _y in got.exterior.coords} >= {40.0, 60.0}


def test_snap_max_zero_disarms_the_quantisation_entirely():
    rim = AirsideRim(Polygon([(0, 0), (100, 0), (100, 100), (0, 100)]),
                     0.0, 0.0)
    counts: dict = {}
    airside_vertex_snap(Polygon([(40, 0), (60, 0), (60, -4), (40, -4)]),
                        rim, counts)
    assert counts.get("snap_too_far") == 2 and "snapped_pads" not in counts


# ── (ax) the clip is the ARRANGEMENT's, and it trims, never deletes ────

def test_the_arrangement_clips_a_pad_by_the_ROLLED_ON_faces_only():
    """RULINGS 2026-09-14ax: the clip runs where the faces HAVE ROLES.
    Its set is ``law.tables.rolled_on_roles`` — the runway family, the
    taxi family and the airside, non-rigid apron roles — so a groundside
    lot, island or service pavement never clips a pad.  Round 1 ran it at
    ``classify/evidence`` against every apt.dat page and took the pad off
    a groundside island's shed (``test_round3``)."""
    from auto_patch_v2.law.tables import is_rigid_role, rolled_on_roles
    from auto_patch_v2.planar.overlay import Region, airside_clip
    law = _armed(_law())
    rolled = rolled_on_roles(law)
    assert "apron" in rolled and "runway" in rolled
    assert not any(r in rolled for r in
                   ("groundside_pavement", "parking_lot", "service_road",
                    "building"))

    def _reg(role, ref, poly):
        return Region(role, ref, poly, None, None, "airside", "cell")

    apron = _reg("apron", "pav1", Polygon([(0, 0), (200, 0), (200, 200),
                                           (0, 200)]))
    lot = _reg("groundside_pavement", "lot1",
               Polygon([(0, 200), (200, 200), (200, 400), (0, 400)]))
    on_apron = _reg("building", "b_in", Polygon([(150, 150), (190, 150),
                                                 (190, 190), (150, 190)]))
    straddle = _reg("building", "b_cut", Polygon([(20, 190), (120, 190),
                                                  (120, 260), (20, 260)]))
    on_lot = _reg("building", "b_lot", Polygon([(20, 300), (60, 300),
                                                (60, 340), (20, 340)]))
    assert is_rigid_role(law, "building")
    out, counts = airside_clip([apron, lot, on_apron, straddle, on_lot], law)
    by = {r.ref: r.polygon for r in out if r.role == "building"}
    # §16g (10) (12) (1) (Fable 2026-09-16; RULINGS 2026-09-16b): the pad
    # WHOLLY on the apron is DROPPED, not kept.  It was the §30 / 14ai
    # pad-in-an-apron class until (12), and this twin asserted it was
    # kept; MEASURED at HECA those 8 pads were the ONLY class of airside
    # re-node left once the arrangement noded the airside first — 548 of
    # the 553 minted airside nodes, every one STRICTLY INSIDE the airside
    # union.  (12) (1)'s own sentence is "a pad polygon is the cluster
    # outline MINUS the airside union" and §16g (10) (5) already said a
    # cluster wholly on airside pavement gets no pad: its bodies seat on
    # the pavement.  A building that really does stand in an apron is a
    # HOLE in that apron and keeps its pad that way (the re-founded
    # ``test_v2bank`` / ``test_constraints`` fixtures).
    assert set(by) == {"b_cut", "b_lot"}, sorted(by)
    # the GROUNDSIDE lot clips nothing: the shed on it is untouched
    assert by["b_lot"].equals(on_lot.polygon)
    # the straddling pad is TRIMMED out of the apron and takes none of it
    assert by["b_cut"].intersection(apron.polygon).area == 0.0
    assert round(by["b_cut"].area) == 6000   # 100 x 70 less the 100 x 10 in the apron
    assert counts["dropped_wholly_on_airside"] == 1
    assert counts["clipped"] == 1


def test_the_arrangement_clip_is_no_longer_law_gated():
    """RE-FOUNDED (§16g (10) (12), Fable 2026-09-16; RULINGS 2026-09-16b).

    This twin asserted that ``[placement] pad_airside_clip = false`` made
    the ARRANGEMENT's clip the identity.  (12) rules that the airside
    cells are computed before any pad exists and are NEVER re-cut by one,
    on EVERY arm — so a pad left overlapping the apron would split the
    apron's own edges and the OFF arm could never read
    ``pad_airside_renode`` 0, which is (12) (2)'s bar on both arms.  The
    key keeps its other two jobs (the mint's pre-split guard in
    ``classify/evidence``, the region subtraction in ``classify/roles``);
    at the arrangement the clip IS the law."""
    from auto_patch_v2.planar.overlay import Region, airside_clip
    law = _armed(_law(), clip=False)
    apron = Region("apron", "pav1", Polygon([(0, 0), (200, 0), (200, 200),
                                             (0, 200)]),
                   None, None, "airside", "cell")
    pad = Region("building", "b", Polygon([(20, 190), (120, 190),
                                           (120, 260), (20, 260)]),
                 None, None, "airside", "cell")
    out, counts = airside_clip([apron, pad], law)
    by = {r.ref: r.polygon for r in out if r.role == "building"}
    assert counts["clipped"] == 1
    assert by["b"].intersection(apron.polygon).area == 0.0


# ── (au) THE SKIRT IS WITHDRAWN (14ay/14bn) ────────────────────────────

def test_the_skirt_and_its_two_law_keys_are_GONE():
    """RE-FOUNDED (owner RULINGS 2026-09-14ay, confirmed 14bn; lane
    ``v2padjoin`` round 3).  This twin asserted 14au's relaxation — the
    skirt band's ceiling rising from ``pad_slope_max`` (1 %) to
    ``pad_skirt_max_slope`` (5 %) under §20b and only there.  The skirt
    itself is withdrawn: a pad touching an apron takes the apron's level
    along the shared edge and stays ONE PLANE inside its 1 % ceiling, and
    §30 (4)'s collar makes the apron planar where the pad meets it.  Both
    keys are deleted, the row head is out of every register, and
    ``_pad_rows`` no longer mentions either."""
    import inspect

    from auto_patch_v2.constraints import pads as _pads_mod
    from auto_patch_v2.solve.design_roles import hard_rulings, one_way_rulings
    law = _law()
    assert not hasattr(law.tables.emit.within_shape, "pad_skirt_max_slope")
    assert not hasattr(law.tables.structures.placement, "pad_skirt_m")
    body = inspect.getsource(_pads_mod._pad_rows)
    # the names survive only in the WHY (the comment recording what was
    # deleted and what it cost); no code reads them
    code = "\n".join(l for l in body.split("\n")
                     if not l.strip().startswith("#"))
    assert "pad_skirt" not in code and "skirt_ceiling" not in code
    head = "structures.building_pad airside skirt"
    assert head not in hard_rulings(law) and head not in one_way_rulings(law)


# ── §16g (10) (12) THE ARRANGEMENT CLIP PRESERVES THE AIRSIDE VERTEX SET
# (Fable 2026-09-16; RULINGS 2026-09-16b) ──────────────────────────────

def _renode_scene(law, pad_ring):
    """One apron, one runway strip's worth of breakline, and ONE pad —
    built through the real ``build_arrangement`` so the twin reads the
    noding itself and not a re-spelling of it."""
    from auto_patch_v2.classify.roles import Cell, Classification
    from auto_patch_v2.model.airport import (Airport, Runway, RunwayEnd,
                                             SceneryPack)
    from auto_patch_v2.model.frame import Frame
    from auto_patch_v2.planar.overlay import build_arrangement

    class _Flat:
        provenance = {"synthetic": "flat"}

        def z(self, x, y):
            return 700.0

        def bounds(self):
            return (-9000.0, -9000.0, 9000.0, 9000.0)

    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0,
                      "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0,
                      "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {},
                      (), (), (), (), (), (), (), pack, _Flat(),
                      law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27",
             ((-600, -22.5), (600, -22.5), (600, 22.5), (-600, 22.5)), (),
             3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apron1",
             ((-200, 100), (200, 100), (200, 300), (-200, 300)), (), None,
             "D", "airside", "apron", {}),
        Cell(2, "building", "pad1", pad_ring, (), None, None, "airside",
             "pad", {}),
    )
    cl = Classification(cells, (), {}, ())
    return build_arrangement(airport, cl, law)


def test_the_airside_vertex_set_barely_depends_on_whether_a_pad_exists():
    """§16g (10) (12) (1)/(2): the airside cells are noded BEFORE any pad
    exists, so adding a pad MINTS and DELETES no airside node.

    MEASURED at HECA (lane ``v2padclip``, ``tools/pad_airside_arm.py``,
    one tree one variable) before the rule: the clip alone took 1,008
    airside vertices away and minted 283, 228 of the minted ones over 1 m
    from ANY airside vertex of the other arm — the whole line set was
    noded in ONE snap-rounding union and a pad ring both split airside
    edges outright and moved unrelated airside nodes by half a grid cell.
    """
    from auto_patch_v2.planar.overlay import PAD_AIRSIDE
    law = _armed(_law())
    # a pad hanging off the apron's north edge: it CROSSES the rim, which
    # is the case that used to split an airside edge at each crossing
    _renode_scene(law, ((-60, 260), (60, 260), (60, 380), (-60, 380)))
    assert PAD_AIRSIDE["renode_deleted"] == 0, dict(PAD_AIRSIDE)
    # THE RESIDUAL, NAMED AND MEASURED (attempt cap, RULINGS 2026-09-16b):
    # this fixture's apron edge runs 400 m with its own nodes 57 m apart,
    # so NEITHER crossing point can reach one inside
    # ``pad_airside_snap_max_m`` and each stands on the rim and splits the
    # apron's edge — 2 minted nodes here, 5 at HECA.  The second attempt,
    # making such a crossing RETREAT off the rim by the hot-pixel band
    # instead, IS REFUTED: it takes the WELD with it (09-01g / §16g (10)
    # (6), "a vertex the pad shares with a pavement IS that pavement's
    # vertex") — ``test_v2padlevel::test_a_pad_between_two_pavements_...``
    # read ZERO shared vertices on both its frontages.  The un-tried lever
    # is the law value ``pad_airside_snap_max_m`` (5.0 m today), which
    # trades pad distortion along the rim for these nodes.
    assert PAD_AIRSIDE["renode_minted"] == 2, dict(PAD_AIRSIDE)
    assert PAD_AIRSIDE["renode_minted_on_rim"] == 2
    assert PAD_AIRSIDE["snap_too_far"] == 2
    # the rim the crossing points quantise to is the ARRANGEMENT's own
    # node set, not the region ring's — which is what made the snap
    # reachable (HECA: 6,272 ring nodes against 8,775 arrangement ones)
    assert PAD_AIRSIDE["rim_nodes_arrangement"] >= PAD_AIRSIDE["rim_nodes_ring"]


def test_a_pad_wholly_on_airside_is_dropped_and_mints_nothing():
    """§16g (10) (12) (1) / §16g (10) (5): a pad standing wholly on what an
    aircraft rolls on gets NO pad — its bodies seat on the pavement.  It
    was KEPT until (12) (the §30 / 14ai pad-in-an-apron class), and
    MEASURED at HECA those 8 pads were the ONLY re-node class left once
    the airside was noded first: 548 of 553 minted airside nodes, every
    one STRICTLY INSIDE the airside union."""
    from auto_patch_v2.planar.overlay import PAD_AIRSIDE
    law = _armed(_law())
    arr = _renode_scene(law, ((-60, 150), (60, 150), (60, 250), (-60, 250)))
    assert PAD_AIRSIDE.get("dropped_wholly_on_airside") == 1, dict(PAD_AIRSIDE)
    assert PAD_AIRSIDE["renode_minted"] == 0 and PAD_AIRSIDE["renode_deleted"] == 0
    assert not any(r.role == "building" for _p, r in arr.faces)


def test_the_densifier_may_not_node_the_rim_but_a_pad_corner_survives():
    """§16g (10) (12) (1): ``ring_lines`` densifies every ring at its own
    role's chord cap, so the `building` cap's midpoints would land on
    airside edges the airside cap spaced differently and SPLIT them — they
    are dropped.  A pad CORNER standing on the rim is the pad's own
    geometry and is never dropped: doing that collapsed the three
    ``test_v2padlevel`` fixtures whose pad merely touches its apron."""
    from shapely.geometry import LineString, Polygon
    from auto_patch_v2.planar.overlay import _drop_rim_midpoints, build_rim
    law = _armed(_law())
    air = Polygon([(0, 0), (400, 0), (400, 100), (0, 100)])
    rim = build_rim(air, law, nodes=[(0.0, 100.0), (400.0, 100.0)])
    # a pad edge running ALONG the rim: its two ends are the pad's own
    # corners, the point between is a densifier midpoint
    line = LineString([(100.0, 100.0), (200.0, 100.0), (300.0, 100.0)])
    own = {(100.0, 100.0), (300.0, 100.0)}
    out, gone = _drop_rim_midpoints([line], rim, {(0.0, 100.0), (400.0, 100.0)},
                                    own)
    assert gone == 1
    assert list(out[0].coords) == [(100.0, 100.0), (300.0, 100.0)]
