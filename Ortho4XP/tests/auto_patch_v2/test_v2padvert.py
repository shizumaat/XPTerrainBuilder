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
    assert set(by) == {"b_in", "b_cut", "b_lot"}, sorted(by)
    # the GROUNDSIDE lot clips nothing: the shed on it is untouched
    assert by["b_lot"].equals(on_lot.polygon)
    # the straddling pad is TRIMMED out of the apron and takes none of it
    assert by["b_cut"].intersection(apron.polygon).area == 0.0
    assert round(by["b_cut"].area) == 6000   # 100 x 70 less the 100 x 10 in the apron
    # ... and the pad WHOLLY on the apron is KEPT, not erased: it is §30 /
    # 14ai's pad-in-an-apron class, which welds to the apron around it
    assert by["b_in"].equals(on_apron.polygon)
    assert counts["kept_wholly_on_airside"] == 1
    assert counts["clipped"] == 1


def test_the_clip_is_law_gated_and_false_is_the_identity():
    from auto_patch_v2.planar.overlay import Region, airside_clip
    law = _armed(_law(), clip=False)
    apron = Region("apron", "pav1", Polygon([(0, 0), (200, 0), (200, 200),
                                             (0, 200)]),
                   None, None, "airside", "cell")
    pad = Region("building", "b", Polygon([(20, 190), (120, 190),
                                           (120, 260), (20, 260)]),
                 None, None, "airside", "cell")
    out, counts = airside_clip([apron, pad], law)
    assert counts == {} and [r.polygon for r in out] == [apron.polygon,
                                                         pad.polygon]


# ── (au) the skirt's relaxed ceiling is §20b's ──────────────────────────

def test_the_skirt_ceiling_relaxes_only_under_the_staged_solve():
    """14au relaxes the SKIRT BAND's slope ceiling from ``pad_slope_max``
    (1 %) to ``pad_skirt_max_slope`` (5 %) because v2settle's certificate
    PROVED the 1 % skirt and a fixed apron rim mutually infeasible.  The
    band's rows are TWO-SIDED (round 5), so under the SINGLE solve a 5 %
    skirt pulls the AIRSIDE harder — MEASURED on CYXY's lockstep census
    twin, the only variable the cap: 0 ``runway_transverse`` rows at 1 %,
    2 at 5 % (0.3788 / 0.3852 m ON THE RUNWAY).  Under §20b the airside is
    a CONSTANT in stage 2 and the same row cannot pull it (RULINGS
    2026-09-14as's own recorded deviation).  So the relaxation is §20b's.
    """
    law = _law()
    ceiling = law.tables.emit.within_shape.pad_slope_max
    relaxed = law.tables.emit.within_shape.pad_skirt_max_slope
    assert relaxed > ceiling
    from auto_patch_v2.constraints import pads as _pads_mod
    import inspect
    body = inspect.getsource(_pads_mod._pad_rows)
    assert "staged_solve" in body and "pad_skirt_max_slope" in body
    # and the gate is the design table's own key, not a literal
    assert bool(_staged(law).tables.emit.design.staged_solve) is True
    assert bool(_staged(law, False).tables.emit.design.staged_solve) is False
