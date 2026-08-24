"""Twins for THE TRANSECT WALK — one station set, both readers.

Spec ``docs/specs/transverse-hyperplane-solve-spec.md`` step 2 / twin (c);
owner ruling RULINGS 2026-08-21.

The owner moved the ``transverse`` family into the SOLVE.  That makes the
station set a shared law object: a span the solve binds which is not a
station the census prices buys nothing, and the two used to be produced by
two separate walks (``check_grade._check_transverse_grade`` inline, and
``lateral_spine_nodes._bracket_feet`` in a different shape) with a test
asserting only that three of their CONSTANTS agreed.  Constants agreeing
is not station sets agreeing.

So there is one walker, and these twins assert the two properties a
shared walker has to have:

  (1) IDENTITY — the census's own path and a direct call produce the SAME
      station ids and the same spans, on the same geometry;
  (2) INSERT-INVARIANCE — a ring that gained COLLINEAR vertices (the
      post-projection weld inserts, which is exactly what makes a
      pre-solve walk and an emitted-ring walk disagree) yields the same
      station set, the same widths and the same interpolated heights.
"""
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from auto_patch import transect_walk as TW        # noqa: E402


# ── the fixture: a 20 m apron strip with a taxi axis down its middle ────
#
# The corridor runs along +x from x=0 to x=60; the apron spans y=-10..+10.
# A station every 10 m therefore crosses a 20 m span whose two hits sit on
# the two long edges — the census's own shape of row.
_LONG = 60.0
_HALF_W = 10.0


def _plain_ring(z_lo=10.0, z_hi=10.0):
    """Four corners, counter-clockwise, y=-10 edge at ``z_lo``."""
    return [(0.0, -_HALF_W, z_lo), (_LONG, -_HALF_W, z_lo),
            (_LONG, _HALF_W, z_hi), (0.0, _HALF_W, z_hi)]


def _inserted_ring(z_lo=10.0, z_hi=10.0):
    """The SAME polygon after a projection dropped collinear vertices onto
    both long edges — geometrically identical, four extra nodes."""
    return [(0.0, -_HALF_W, z_lo), (20.0, -_HALF_W, z_lo),
            (40.0, -_HALF_W, z_lo), (_LONG, -_HALF_W, z_lo),
            (_LONG, _HALF_W, z_hi), (35.0, _HALF_W, z_hi),
            (15.0, _HALF_W, z_hi), (0.0, _HALF_W, z_hi)]


def _axis():
    return TW.TransectAxis(poly=[(0.0, 0.0), (_LONG, 0.0)],
                           seg_caps=[0.01], is_service=False)


def _priced(_axis_obj):
    return {"apron"}


def _walk(ring, key="W1"):
    shapes = [TW.TransectShape(role="apron", ring=ring, key=key)]
    return list(TW.walk_transects(shapes, [_axis()], _priced))


# ── (1) the walk itself ────────────────────────────────────────────────

def test_the_walk_prices_the_corridor_cross_section():
    st = _walk(_plain_ring(10.0, 10.4))
    assert st, "the fixture corridor was not priced at all"
    for s in st:
        assert s.width_m == pytest.approx(2 * _HALF_W)
        assert s.dz == pytest.approx(0.4)
        assert s.cap_l == 0.01
        # the hits are edge-INTERPOLATED, not ring vertices
        assert s.z_lo == pytest.approx(10.0)
        assert s.z_hi == pytest.approx(10.4)


def test_station_ids_are_deterministic_and_ordered():
    a = [s.station_id for s in _walk(_plain_ring())]
    b = [s.station_id for s in _walk(_plain_ring())]
    assert a == b and a == sorted(a), "the station set is not deterministic"
    assert len({s for s in a}) == len(a), "duplicate station ids"
    # (axis, segment, station, shape_key)
    assert all(len(s) == 4 and s[0] == 0 and s[1] == 0 for s in a)


# ── (2) INSERT-INVARIANCE — the property the two walks did not have ────

def test_collinear_inserts_do_not_move_the_station_set():
    """THE regression this walker exists for.  A weld/projection insert on
    a ring EDGE changes the node set and changes nothing physical, so the
    station set, the spans and the interpolated heights must be
    identical.  Two separate walks had no reason to agree here; one walk
    agrees by construction."""
    plain = _walk(_plain_ring(10.0, 10.4))
    inserted = _walk(_inserted_ring(10.0, 10.4))
    assert [s.station_id for s in plain] == [s.station_id for s in inserted]
    for p, q in zip(plain, inserted):
        assert p.width_m == pytest.approx(q.width_m)
        assert p.z_lo == pytest.approx(q.z_lo)
        assert p.z_hi == pytest.approx(q.z_hi)
        assert p.point_lo() == pytest.approx(q.point_lo())
        assert p.point_hi() == pytest.approx(q.point_hi())
    # …and the EDGE the hit lands on genuinely differs — otherwise the
    # twin would be asserting invariance over a change that did not happen.
    assert ([s.edge_lo for s in plain] != [s.edge_lo for s in inserted]
            or [s.t_lo for s in plain] != [s.t_lo for s in inserted])


def test_a_non_collinear_vertex_does_move_the_reading():
    """The other side of the same coin: a vertex that genuinely lifts the
    boundary is a different surface and the walk must say so."""
    bent = _inserted_ring(10.0, 10.4)
    bent[1] = (20.0, -_HALF_W, 10.9)          # one long-edge node lifted
    plain = _walk(_plain_ring(10.0, 10.4))
    got = _walk(bent)
    assert [s.station_id for s in plain] == [s.station_id for s in got]
    assert any(abs(p.dz - q.dz) > 0.01 for p, q in zip(plain, got))


# ── (3) IDENTITY between the two readers ───────────────────────────────

_PATCH = """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6' generator='transect-twin'>
%(nodes)s
  <way id='-10'>
%(refs)s
    <tag k='role' v='apron' />
    <tag k='shapeID' v='T1' />
  </way>
</osm>
"""


def _write_patch(tmp_path, ring_m, anchor=(30.0, 31.0)):
    """An emitted patch whose apron ring IS ``ring_m`` (metres), plus the
    sidecar axis the census walks.  Metres → lat/lon through the census's
    own factory, inverted analytically so the round trip is exact enough
    for a 20 m corridor."""
    import check_grade as cg
    lat0, lon0 = anchor
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(lat0))

    def to_ll(x, y):
        return (lat0 + y / m_per_deg_lat, lon0 + x / m_per_deg_lon)

    nodes, refs = [], []
    for i, (x, y, z) in enumerate(ring_m):
        la, lo = to_ll(x, y)
        nodes.append(f"  <node id='-{i + 1}' lat='{la:.11f}' "
                     f"lon='{lo:.11f}'>\n    <tag k='alt_abs' "
                     f"v='{z:.2f}' /></node>")
        refs.append(f"    <nd ref='-{i + 1}' />")
    refs.append("    <nd ref='-1' />")
    osm = tmp_path / "t.osm"
    osm.write_text(_PATCH % {"nodes": "\n".join(nodes),
                             "refs": "\n".join(refs)})
    axis_ll = [list(to_ll(x, 0.0)) for x in (0.0, _LONG)]
    side = {"anchor": [lat0, lon0],
            "axes_exact": [[axis_ll, [0.01], 0]],
            "routes_exact": [axis_ll]}
    Path(str(osm) + ".axes.json").write_text(json.dumps(side))
    return osm, cg


def test_the_census_walks_the_same_stations_as_a_direct_call(tmp_path):
    """IDENTITY (twin (c)): the census's own path and a direct walk agree
    on the station ids and on every span they select."""
    ring = _inserted_ring(10.0, 10.9)         # over cap: 4.5 % across 20 m
    osm, cg = _write_patch(tmp_path, ring)
    ctx = cg.law_context_from_sidecar(osm, announce=False)
    nodes, ways = cg._parse_osm(Path(osm))
    ll = cg._ll_to_m_factory(nodes, anchor=ctx.get("anchor"))
    axes = cg._axes_to_m(ctx.get("taxi_axes_ll"), ll)
    seen: list = []
    rows, n_stations, n_rows, n_shapes = cg._check_transverse_grade(
        ways, nodes, ll, axes, stations_out=seen)
    assert n_stations > 0 and seen, "the census walked no station"
    assert n_rows == len(seen)
    assert rows, "the fixture is over cap and must produce rows"

    # …the same geometry, walked directly.
    direct = list(TW.walk_transects(
        [TW.TransectShape(role="apron",
                          ring=[(*ll(*nodes[nid]), float(e))
                                for nid, e in zip(ways[0].nids[:-1],
                                                  ways[0].elevs)],
                          key=("-10", 0))],
        [TW.TransectAxis(poly=axes[0][0], seg_caps=axes[0][1],
                         is_service=False)],
        lambda _a: {"apron"}))
    assert [s.station_id for s in direct] == [s.station_id for s in seen]
    for a, b in zip(direct, seen):
        assert a.width_m == pytest.approx(b.width_m)
        assert a.z_lo == pytest.approx(b.z_lo)
        assert a.z_hi == pytest.approx(b.z_hi)
        assert a.cap_l == pytest.approx(b.cap_l)


def test_the_budget_the_census_applies_is_the_law_functions(tmp_path):
    """The walk carries the LONGITUDINAL cap; the budget is the one law
    function; the census adds only its own envelope."""
    from auto_patch import grade_law as GL
    osm, cg = _write_patch(tmp_path, _inserted_ring(10.0, 10.9))
    ctx = cg.law_context_from_sidecar(osm, announce=False)
    nodes, ways = cg._parse_osm(Path(osm))
    ll = cg._ll_to_m_factory(nodes, anchor=ctx.get("anchor"))
    seen: list = []
    rows, _st, _nr, _ns = cg._check_transverse_grade(
        ways, nodes, ll, cg._axes_to_m(ctx.get("taxi_axes_ll"), ll),
        stations_out=seen)
    st = seen[0]
    assert (cg._transverse_span_budget(st.cap_l, st.width_m)
            == pytest.approx(GL.transverse_span_budget_m(st.cap_l,
                                                         st.width_m)))
    # the row's own excess is measured against budget + this reader's
    # quantization envelope, never against the bare law
    r = rows[0]
    assert r.de_m > cg._transverse_span_budget(st.cap_l, st.width_m)
