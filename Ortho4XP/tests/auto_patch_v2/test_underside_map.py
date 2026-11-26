"""The underside height map (RULINGS 2026-11-25m; spec
``docs/specs/underside-height-map-20261125.md`` step 1): the layers, the
contact plan, the perimeter stations, the interiors and ``t``
(``geom/underside_map``); the population twin against ``plan_clusters``
(U2) through ``airport/unit_underside``; the composite test
(``airport/underside_composite``); admission S3
(``airport/underside_admission``)."""
from __future__ import annotations

import dataclasses as _dc
from types import SimpleNamespace

import numpy as np
from auto_patch_v2.airport import underside_admission as adm
from auto_patch_v2.airport import underside_composite as uc
from auto_patch_v2.airport import unit_underside as uu
from auto_patch_v2.airport.obj8 import Component
from auto_patch_v2.airport.placement_family import plan_clusters
from auto_patch_v2.geom import underside_map as um
from auto_patch_v2.model.rebake import Member, Part, Unit

_FACES = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
          (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]


def _box(x0, x1, y0, y1, z0, z1):
    """``(vertices, tris)`` of a closed box, authored ``(x, y, z)``."""
    v = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1],
                  [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]], float)
    return v, np.array(_FACES)


def _tris(*boxes):
    """``(n, 3, 3)`` triangles of ``boxes`` as east/north/y (heading 0 at
    the origin: east = x, north = -z)."""
    out = []
    for b in boxes:
        v, t = _box(*b)
        p = v[t]
        out.append(np.stack([p[:, :, 0], -p[:, :, 2], p[:, :, 1]], -1))
    return np.concatenate(out)


def _layers(boxes, grounded):
    p = _tris(*boxes)
    nrm = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    floor_ok = np.abs(nrm[:, 2]) >= 0.7 * np.linalg.norm(nrm, axis=1)
    foot = np.concatenate([np.full(12, b[2] + 1.0 if g else -np.inf)
                           for b, g in zip(boxes, grounded, strict=True)])
    return um.rasterise_layers(p, floor_ok, foot)


def _none(e, n):
    return np.zeros(len(e), dtype=bool)


def test_a_slab_is_its_own_contact_plan_and_its_top_is_t():
    g = _layers([(0, 20, -0.3, 0.0, -10, 0)], [True])
    assert g.step == 1.0
    m = um.underside(g, ("a",), "u", _none, 3.0)
    assert m.plan.sum() == 200 and len(m.e) > 0
    assert abs(m.t) < 1e-6 and m.t_from == "feet"      # the tread, not the buried side
    assert np.all(m.lo <= m.h + 1e-6) and not m.interiors and m.flat


def test_an_overhang_sets_no_perimeter():
    g = _layers([(0, 20, -0.3, 0.0, -10, 0), (25, 45, 6.0, 6.3, -10, 0)], [True, False])
    m = um.underside(g, ("a",), "u", _none, 3.0)
    ii, jj = np.nonzero(m.plan)
    e, _n = g.centres(ii, jj)
    assert e.max() < 21.0                      # the canopy is in no contact plan
    assert np.isfinite(g.top).sum() > m.plan.sum()   # though it is in the layers


def test_a_car_park_ramp_ends_a_storey_up():
    ramp = [(20 + k, 21 + k, 0.5 * k - 0.2, 0.5 * k, -10, 0) for k in range(20)]
    g = _layers([(0, 20, -0.3, 0.0, -10, 0), *ramp], [True] + [False] * 20)
    m = um.underside(g, ("a",), "u", _none, 3.0)
    assert np.nanmax(g.top[m.plan]) <= 3.0 + 1e-6
    assert np.nanmax(g.top) > 9.0


def test_an_open_basement_is_an_interior_and_airside_reads_t():
    g = _layers([(0, 6, -0.3, 0.0, -20, 0), (14, 20, -0.3, 0.0, -20, 0),
                 (6, 14, -0.3, 0.0, -20, -14), (6, 14, -0.3, 0.0, -6, 0),
                 (6, 14, -3.3, -3.0, -14, -6)], [True] * 5)
    near = lambda e, n: e < 2.0                # noqa: E731 -- the west edge is airside
    m = um.underside(g, ("a",), "u", near, 3.0)
    assert [i.kind for i in m.interiors] == ["open"]
    assert abs(m.interiors[0].floor + 3.3) < 1e-6      # its lowest flat surface
    assert m.t_from == "airside" and abs(m.t) < 1e-6 and m.airside.any()


def test_compose_takes_max_top_and_min_low_on_one_lattice():
    a = _layers([(0, 10, 0.0, 1.0, -10, 0)], [True])
    b = _layers([(5, 15, 0.0, 4.0, -10, 0)], [True])
    c = um.compose([a, b])
    assert c.top.shape[1] == 16 and np.nanmax(c.top) == 4.0 and np.nanmin(c.low) == 0.0


# ── the airport layer: the population twin (U2) ─────────────────────────

_ML, _MO = 110574.0, 111320.0


def _part(pid, x0, x1, z0, z1, y0, y1):
    lat0, lat1 = -z1 / _ML, -z0 / _ML
    lon0, lon1 = x0 / _MO, x1 / _MO
    ring = ((lat0, lon0), (lat0, lon1), (lat1, lon1), (lat1, lon0))
    return Part(pid, 0, 0.5 * (lat0 + lat1), 0.5 * (lon0 + lon1), y0,
                (x1 - x0) * (z1 - z0), (lat0, lon0, lat1, lon1),
                ((lat0, lon0, y0),), False, (ring,), y1 - y0)


class _Cache:
    def __init__(self, files):
        self.files = files

    def geometry(self, path):
        v, t = self.files[path]
        return SimpleNamespace(vertices=v, solid=t, animated=np.zeros(0, bool),
                               under_terrain=np.zeros(0, bool))

    def components(self, path):
        v, t = self.files[path]
        ys = v[t][:, :, 1]
        return [Component(t, float(ys.min()), float(ys.max()), 0.0, 0.0, False,
                          np.arange(len(t)))]


def _airport():
    """Two walled buildings at one anchor, 40 m apart, the west one at
    airside pavement: two clusters, two maps."""
    files = {"a.obj": _box(0, 20, 0, 8, -10, 0), "b.obj": _box(60, 80, -2, 6, -10, 0)}
    ma = Member("dsf:obj1", "a.obj", "a.obj", "a.obj", 0.0,
                parts=(_part(0, 0, 20, -10, 0, 0.0, 8.0),), origin=(0.0, 0.0))
    mb = Member("dsf:obj2", "b.obj", "b.obj", "b.obj", 0.0,
                parts=(_part(1, 60, 80, -10, 0, -2.0, 6.0),), origin=(0.0, 0.0))
    part = SimpleNamespace(units=(Unit("unit:0", (0.0, 0.0), 0.0, (ma, mb)),),
                           contacts=(), pack_root="", icao="TEST")
    cl = plan_clusters(part, 1.0, chain_min_height_m=2.0)
    frame = SimpleNamespace(entry=lambda: (lambda lon, lat: (lon * _MO, lat * _ML)),
                            transformers=lambda: (None, lambda x, y: (y / _ML, x / _MO)))
    pav = SimpleNamespace(id="pav1", outer=((-30, -5), (-1, -5), (-1, 5), (-30, 5)),
                          holes=())
    dem = SimpleNamespace(z_many=lambda x, y: np.full(len(x), 100.0))
    law = SimpleNamespace(tables=SimpleNamespace(structures=SimpleNamespace(
        basin=SimpleNamespace(floor_plate_normal_y_min=0.7, contact_band_m=1.0),
        building_pad=SimpleNamespace(low_level_min_step_m=3.0),
        placement=SimpleNamespace(chain_min_height_m=2.0))))
    ap = SimpleNamespace(partition=part, clusters=tuple(cl), frame=frame, pavements=(pav,),
                         taxi_nodes={}, taxi_edges=(), dem=dem)
    return ap, law, _Cache(files)


def _rows(ap, c):
    return tuple(sorted({m.id for u in ap.partition.units for m in u.members
                         for p in m.parts if p.pid in c.pids}))


def test_one_map_per_cluster_keyed_by_its_rows_twin_of_plan_clusters():
    ap, law, cache = _airport()
    assert len(ap.clusters) == 2 and all(c.pids for c in ap.clusters)
    maps = uu.derive(ap, law, cache)["maps"]
    by_rows = {_rows(ap, c): c for c in ap.clusters}
    assert set(maps) == set(by_rows)
    for key, m in maps.items():
        c = by_rows[key]
        assert m.unit == c.id
        # the map's ground contact is the cluster's own ground floor
        assert abs(float(np.nanmin(m.layers.foot)) - min(c.floors)) < 1e-6
        assert m.base == min(c.floors)
    west, east = maps[("dsf:obj1",)], maps[("dsf:obj2",)]
    assert west.t_from == "airside" and abs(west.t) < 1e-6
    assert east.t_from == "feet" and abs(east.t + 2.0) < 1e-6


def test_a_second_cluster_on_the_same_rows_takes_its_id():
    ap, _law, _cache = _airport()
    c = ap.clusters[0]
    ap.clusters = (c, _dc.replace(c, id=c.id + "x"))
    keys = [k for k, _cid, _p in uu.unit_population(ap)]
    assert keys[0] == keys[1][:-1] and keys[1][-1] == f"@{c.id}x"


def test_no_composite_without_a_sheet_and_the_log_line():
    ap, law, cache = _airport()
    got = uu.derive(ap, law, cache)
    joined = uc.join(ap, law, got["maps"], got["sets"])
    assert set(joined) == set(got["maps"]) and not any(m.composite for m in joined.values())
    assert "2 grounded unit(s)" in uu.log_line("TEST", joined)


def test_a_paved_skirt_on_our_ground_is_a_composite():
    n = 60
    u = (np.arange(n) + 0.5) / n
    top = np.tile(40.0 * u * u, (n, 1)).astype(np.float32)     # a modelled hollow
    g = um.Layers(0.0, 0.0, 1.0, top, top - 0.2, top - 0.2, top - 0.2, top)
    dem = lambda e, n_: 100.0 + 40.0 * (e / n) ** 2  # noqa: E731
    assert uc.is_composite(g, dem) is not None
    flat = lambda e, n_: np.full(len(e), 100.0)      # noqa: E731 -- our ground explains none
    assert uc.is_composite(g, flat) is None


# ── admission S3 ─────────────────────────────────────────────────────────

def _m(t, base, t_from="airside", composite=False, h=None):
    h = np.zeros(4) if h is None else np.asarray(h, float)
    return SimpleNamespace(t=t, base=base, t_from=t_from, composite=composite,
                           footless=False, h=h, airside=np.array([1, 0, 0, 0], bool))


def test_admission_verdicts():
    assert adm.admit(_m(0.0, 0.01), 100.0)[0] == "coherent"
    assert adm.admit(_m(0.0, 0.0), None)[0] == "exception"
    v, d = adm.admit(_m(-7.0, 0.0, composite=True), 366.0)
    assert v == "composite" and d["z0"] == 373.0
    g = np.full(4, 366.0)            # our ground confirms the floor 7 m down
    v, d = adm.admit(_m(-7.0, 0.0, h=[-7, -7, -7, -7]), 366.0, g)
    assert v == "mis-zeroed" and d["z0"] == 373.0
    v, d = adm.admit(_m(-7.0, 0.0, t_from="feet", composite=True), 366.0)
    assert v == "doubt" and d["z0"] == 366.0        # never welded but by airside
