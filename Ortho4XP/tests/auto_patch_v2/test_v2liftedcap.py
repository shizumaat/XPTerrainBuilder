"""§34 (9) THE PINCHED RAMP — THE CENSUS TAKES THE LIFTED CAP.

Owner RULINGS 2026-09-14ak (the ruling) and 2026-09-14am (the census read:
"the BUILD cap is lifted, the JUDGED cap is not ... RULED: the census takes
the lifted cap — a per-shape ``lifted_cap`` channel"), against the
2026-09-12m class "a build steeper than the judged cap mints a violation by
construction".

ONE CHANNEL, TWO READERS.  ``pipeline/publication.lifted_caps`` is the
single derivation (face -> the corridor's ``Tunnel.pinched`` record by the
same nearest-axis join ``structure_geometry.ramp_targets`` aims the ramp's
own vertices with).  The v1 census reads it off the emitted way tag
``o4_grade_law_cap_lifted``; v2 verify reads the same map through
``Patch.of(lifted_caps=…)``.  Both are twinned here, and so is the
NON-LEAK: a neighbouring face is untouched, and ``Patch.cap`` still returns
the ramp's ROLE cap for the three readers a ``None`` there would have
broken (``strips._pavement_ids``, ``steps`` cross-shape / vertex-to-edge).
"""
from __future__ import annotations

import math
import sys

import pytest


def _cg():
    sys.path.insert(0, "tools")
    import check_grade as CG
    return CG


# ── the fixture: a 12 m ramp carrying 3.6 m (30 %) and a flat taxi face ──

_LAT0, _LON0 = 25.2647, 51.6116


def _ring(CG, wid, role, z_of, tags, xs_ys):
    """One closed way plus its node lat/lons, at ``z_of(i)`` per vertex."""
    nids, elevs, ll = [], [], {}
    for i, (x, y) in enumerate(xs_ys):
        nid = f"{wid}_{i}"
        nids.append(nid)
        elevs.append(z_of(i))
        ll[nid] = (_LAT0 + y / 111320.0, _LON0 + x / 100650.0)
    nids.append(nids[0])
    elevs.append(elevs[0])
    t = {"role": role, "shapeID": wid}
    t.update(tags)
    return CG.Way(wid=wid, role=role, ref=role, aeroway="taxiway",
                  nids=nids, elevs=elevs, tags=t), ll


def _fixture(CG, lifted: bool):
    """``(ways, nodes, ll_to_m)``: the pinched ramp (30 % along x) and a
    neighbouring taxi face standing 0.9 m over 12 m (7.5 %, well over the
    taxi 1.5 %) — the face the lift must NEVER reach."""
    ramp_xy = [(0.0, 0.0), (0.0, 3.0), (12.0, 3.0), (12.0, 0.0)]
    tags = {"o4_grade_law": "structure_ramp", "o4_grade_law_cap": "0.1"}
    if lifted:
        tags[CG.LIFTED_CAP_TAG] = "0.37"
    ramp, ll_a = _ring(CG, "ramp", "tunnel_ramp",
                       lambda i: 0.0 if i < 2 else 3.6, tags, ramp_xy)
    taxi_xy = [(0.0, 20.0), (0.0, 23.0), (12.0, 23.0), (12.0, 20.0)]
    taxi, ll_b = _ring(CG, "taxi", "taxiway",
                       lambda i: 0.0 if i < 2 else 0.9, {}, taxi_xy)
    nodes = dict(ll_a)
    nodes.update(ll_b)
    return [ramp, taxi], nodes, CG._ll_to_m_factory(nodes)


def _rows(CG, lifted: bool):
    ways, nodes, to_m = _fixture(CG, lifted)
    out = CG._check_within_shape(ways, nodes, to_m, 0.015)
    by_way = {}
    for v in out:
        by_way.setdefault(v.way_a.wid, []).append(v)
    return by_way


def test_v1_census_prices_the_unlifted_pinched_ramp():
    """WITHOUT the lift the 30 % ramp mints ``within_shape`` rows against
    its ``structure_ramp`` 10 % cap — the 14am population, by
    construction."""
    CG = _cg()
    by_way = _rows(CG, lifted=False)
    assert by_way.get("ramp"), "the un-lifted ramp must be priced"
    assert max(v.grade_pct for v in by_way["ramp"]) > 10.0


def test_v1_census_takes_the_lift_on_the_pinched_ramp_only():
    """WITH the lift the ramp reads 0 rows and the NEIGHBOUR is untouched
    — the same count, row for row, as the un-lifted arm."""
    CG = _cg()
    off = _rows(CG, lifted=False)
    on = _rows(CG, lifted=True)
    assert on.get("ramp", []) == [], "§34 (9): the pinched run's cap is LIFTED"
    assert len(on.get("taxi", [])) == len(off.get("taxi", [])) > 0, (
        "the lift reached a neighbouring face — it is scoped to the WAY")
    assert [v.de_m for v in on["taxi"]] == [v.de_m for v in off["taxi"]]


def test_v1_lift_is_counted_never_hidden():
    """The reader tallies what it took (``_LIFTED_CAP_STATS``), so the
    census can print the lift's own size beside the family."""
    CG = _cg()
    _rows(CG, lifted=True)
    assert CG._LIFTED_CAP_STATS["ways"] == 1
    assert CG._LIFTED_CAP_STATS["pairs"] > 0


def test_v1_lift_tag_reader_both_ways():
    CG = _cg()
    ways, _n, _m = _fixture(CG, lifted=True)
    assert CG._lifted_cap_tag(ways[0]) == pytest.approx(0.37)
    assert CG._lifted_cap_tag(ways[1]) is None
    off, _n, _m = _fixture(CG, lifted=False)
    assert CG._lifted_cap_tag(off[0]) is None


def test_v1_lift_does_not_touch_the_role_cap_readers():
    """``_role_grade_limit`` is UNTOUCHED: the ramp keeps its 10 % cap in
    ``cross_shape`` (``_pair_grade_limit``), the step families and every
    other reader.  §34 (9) lifts the within-shape longitudinal reading and
    nothing else."""
    CG = _cg()
    ways, _n, _m = _fixture(CG, lifted=True)
    assert CG._role_grade_limit(ways[0], 0.015) == pytest.approx(0.1)
    assert CG._pair_grade_limit(ways[0], ways[1], 0.015) == pytest.approx(0.015)


def test_lifted_caps_is_a_registered_sidecar_key():
    """The report record is EVIDENCE — classified, so the census's
    unknown-key tripwire stays silent and no reader can ignore it by
    accident."""
    CG = _cg()
    assert "lifted_caps" in CG.SIDECAR_EVIDENCE_KEYS
    assert "lifted_caps" not in CG.SIDECAR_LAW_KEYS
    from auto_patch_v2.emit.osm_adapter import SIDECAR_KEYS
    assert "lifted_caps" in SIDECAR_KEYS


# ── the engine twin: verify/frame + verify/within ───────────────────────

def _patch(lifted: bool):
    """The same two faces as a v2 ``Patch`` (the verify frame's own data
    classes — no solve, no emit)."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.verify.frame import Patch, Shape

    law = Law.for_airport("ZZZZ")
    xy, z, ll = {}, {}, {}
    shapes = []
    for k, (wid, role, y0, dz) in enumerate(
            ((1, "wall_corridor_ramp", 0.0, 3.6), (2, "apron", 20.0, 0.9))):
        pts = [(0.0, y0), (0.0, y0 + 3.0), (12.0, y0 + 3.0), (12.0, y0)]
        ids = []
        for i, (x, y) in enumerate(pts):
            vid = 100 * k + i
            ids.append(vid)
            xy[vid] = (x, y)
            z[vid] = 0.0 if i < 2 else dz
            ll[vid] = (_LAT0 + y / 111320.0, _LON0 + x / 100650.0)
        shapes.append(Shape(wid, role, role, tuple(ids),
                            tuple(xy[i] for i in ids), tuple(z[i] for i in ids),
                            None, None, None, False, None,
                            0.37 if (lifted and role.endswith("ramp")) else None))
    return Patch(law, _LAT0, _LON0, xy, z, ll, tuple(shapes), (), {})


def _within(p):
    from auto_patch_v2.verify.within import within_shape
    rows, _xsec = within_shape(p)
    out = {}
    for r in rows:
        out.setdefault(r["way_a"], []).append(r)
    return out


def test_engine_verify_prices_the_unlifted_ramp():
    off = _within(_patch(lifted=False))
    assert off.get(1), "the un-lifted ramp must be priced by v2 verify too"


def test_engine_verify_takes_the_lift_on_the_pinched_ramp_only():
    off, on = _within(_patch(False)), _within(_patch(True))
    assert on.get(1, []) == [], "§34 (9): the pinched run's cap is LIFTED"
    assert on.get(2) == off.get(2), "the neighbouring taxi face moved"


def test_patch_cap_still_returns_the_role_cap_for_a_lifted_shape():
    """THE NON-LEAK the 30l consumer census found: ``Patch.cap`` is read by
    ``strips._pavement_ids`` (a shape with a cap IS pavement) and by
    ``steps`` (``cap = min(ca, cb)`` for ``cross_shape``; ``cap is None``
    skips the shape from ``vertex_to_edge`` / ``mid_edge``).  The lift is
    read through ``Patch.lifted``, so those three families see exactly the
    ramp they saw before."""
    on = _patch(lifted=True)
    off = _patch(lifted=False)
    ramp_on = next(s for s in on.shapes if s.role.endswith("ramp"))
    ramp_off = next(s for s in off.shapes if s.role.endswith("ramp"))
    assert on.cap(ramp_on) == off.cap(ramp_off) is not None
    assert on.cap_t(ramp_on) == off.cap_t(ramp_off)
    assert on.lifted(ramp_on) == pytest.approx(0.37)
    assert off.lifted(ramp_off) is None
    taxi = next(s for s in on.shapes if s.role == "apron")
    assert on.lifted(taxi) is None


def test_patch_of_carries_the_lifted_map_by_face_id():
    """``Patch.of(lifted_caps=…)`` lands the value on the RIGHT shape."""
    import inspect

    from auto_patch_v2.verify.frame import Patch
    src = inspect.getsource(Patch.of)
    assert "(lifted_caps or {}).get(f.id)" in src


# ── the derivation: publication.lifted_caps ─────────────────────────────

class _V:
    def __init__(self, xy):
        self.xy = xy


class _F:
    def __init__(self, fid, role, ring):
        self.id, self.role, self.ring = fid, role, ring
        self.ref = f"f{fid}"


class _T:
    def __init__(self, tid, axis, pinched):
        self.id, self.axis, self.pinched = tid, axis, pinched


class _PM:
    """The narrowest planar-map shape ``lifted_caps`` reads."""

    def __init__(self, faces, vertices, tunnels):
        self.faces, self.vertices, self.structures = faces, vertices, tunnels

    def ring_vertices(self, cycle):
        return tuple(cycle)


def _pm():
    v = {i: _V(p) for i, p in enumerate(
        [(0.0, 0.0), (0.0, 3.0), (12.0, 3.0), (12.0, 0.0),          # pinched
         (0.0, 60.0), (0.0, 63.0), (12.0, 63.0), (12.0, 60.0),      # unpinched
         (0.0, 6.0), (0.0, 9.0), (12.0, 9.0), (12.0, 6.0)])}        # neighbour
    faces = {1: _F(1, "wall_corridor_ramp", (0, 1, 2, 3)),
             2: _F(2, "wall_corridor_ramp", (4, 5, 6, 7)),
             3: _F(3, "taxiway", (8, 9, 10, 11))}
    tunnels = [_T("pinched", ((0.0, 1.5), (12.0, 1.5)), ("route7", 5.1, 0.3698)),
               _T("plain", ((0.0, 61.5), (12.0, 61.5)), None)]
    return _PM(faces, v, tunnels)


def test_lifted_caps_names_the_pinched_corridors_ramp_faces_only():
    from auto_patch_v2.pipeline.publication import lifted_caps
    got = lifted_caps(_pm())
    assert set(got) == {1}, "the lift reached a face outside the pinched corridor"
    assert got[1] == pytest.approx(0.3698)


def test_lifted_caps_is_empty_where_nothing_pinched():
    from auto_patch_v2.pipeline.publication import lifted_caps
    pm = _pm()
    pm.structures = [t for t in pm.structures if t.pinched is None]
    assert lifted_caps(pm) == {}


def test_lifted_records_carry_the_report_the_ruling_asks_for():
    """§34 (9) (3): "the report names each pinched ramp (corridor, road,
    span, grade)"."""
    from auto_patch_v2.pipeline.publication import _lifted_records
    rec = _lifted_records(_pm())
    assert len(rec) == 1
    fid, corridor, road, span, grade = rec[0]
    assert (fid, corridor, road) == (1, "pinched", "route7")
    assert span == pytest.approx(5.1)
    assert grade == pytest.approx(0.3698)


def test_the_tunnel_record_is_the_single_source_of_the_pinch():
    """The pinch is READ off ``Tunnel.pinched`` — the record
    ``wall_corridor_ramps.stop_and_steepen`` wrote — never re-derived from
    a steepened ``design_grade`` (which a §34 (8) moved mouth also
    carries)."""
    import dataclasses as dc

    from auto_patch_v2.model.structures import Tunnel
    fields = {f.name for f in dc.fields(Tunnel)}
    assert "pinched" in fields
    assert Tunnel.__dataclass_fields__["pinched"].default is None


def test_the_face_join_is_the_one_ramp_targets_uses():
    """LOCKSTEP: the face -> corridor join and the ramp ROLE set are the
    ones ``structure_geometry.ramp_targets`` aims the ramp's own vertices
    with — the face judged at the lifted cap is the face built at the
    lifted grade."""
    import inspect

    from auto_patch_v2.planar import structure_geometry as SG
    from auto_patch_v2.pipeline.publication import RAMP_ROLES
    src = inspect.getsource(SG.ramp_targets)
    for role in RAMP_ROLES:
        assert f'"{role}"' in src, f"{role} is not a ramp role to ramp_targets"
    assert "axes[k].distance(Point(" in src


def test_the_lift_rides_on_the_face_tags_channel():
    """``publication.face_tags`` stamps the tag the v1 census reads, and
    the tag name is ONE constant on both sides."""
    from auto_patch_v2.pipeline.publication import LIFTED_CAP_TAG, face_tags
    CG = _cg()
    assert LIFTED_CAP_TAG == CG.LIFTED_CAP_TAG

    class _Law:
        pass

    pm = _pm()
    pm.edge_kind_of_ref = {}
    import auto_patch_v2.pipeline.publication as P
    orig = P.road_law_caps
    P.road_law_caps = lambda *a, **k: {}
    try:
        tags = face_tags(pm, _Law(), None)
    finally:
        P.road_law_caps = orig
    assert tags[1][LIFTED_CAP_TAG] == "0.3698"
    assert LIFTED_CAP_TAG not in (tags.get(2) or {})
    assert LIFTED_CAP_TAG not in (tags.get(3) or {})


def test_the_ruling_is_not_the_axis_average():
    """WHY THE LIFT IS THE PRESENCE AND NOT THE VALUE (the measurement
    behind the design, OTHH ``v2othhfix_r2``): ``route7``'s pinch is 5.1 m
    of axis at 36.98 %, but the ramp's two long edges run 4.93 m and
    3.81 m and its emitted ring carries a 1.118 m chord holding 0.96 m =
    85.8 %.  A cap SET to the designed grade would leave 9 of the 20 rows
    the ruling calls lawful, so the reader takes the presence."""
    worst = 0.96 / 1.118
    assert worst > 0.3698
    assert math.isclose(worst, 0.8586, abs_tol=5e-4)
