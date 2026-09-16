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
