"""Issue #516 twin: A RAMP END THAT SINKS INTO THE GROUND leaves the pad.

A unit's pad is the union of its members' footprints; a sloped road deck
whose low end, at the unit's level, stands under the natural ground used
to take its whole footprint into the flat pad, cutting the ground away
under it (SPJC −12.0318118, −77.1134626: the ramp end 3.9 m under the
DEM).  ``airport/sunken_ramp`` returns that ground as a shade; a flat roof
in the same cut is a building and keeps its pad.
"""
from __future__ import annotations

import types

import pytest
from shapely.geometry import Point

from auto_patch_v2.airport import sunken_ramp as sr
from auto_patch_v2.airport.rebake_plan import _mpd
from auto_patch_v2.law import load_default

LAT0, LON0 = 10.0, 20.0
ML, MO = _mpd(LAT0)


def to_xy(lon, lat):
    return ((lon - LON0) * MO, (lat - LAT0) * ML)


def ll(e, n):
    return (LAT0 + n / ML, LON0 + e / MO)


def _obj(path, quads, skirt=True):
    """An OBJ8 of flat-shaded quads ``[(x0, x1, z0, z1, y0, y1)]`` whose
    ``y`` runs from ``y0`` at ``z0`` to ``y1`` at ``z1``."""
    vt, idx = [], []
    for x0, x1, z0, z1, y0, y1 in quads:
        b = len(vt)
        vt += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1)]
        idx += [b, b + 1, b + 2, b, b + 2, b + 3]
    if skirt:   # the walls the pack runs under the zero ("sink into the ground")
        x0, x1, z0, z1 = quads[0][:4]
        b = len(vt)
        vt += [(x0, -3.0, z0), (x1, -3.0, z0), (x1, 0.0, z0), (x0, 0.0, z0)]
        idx += [b, b + 1, b + 2, b, b + 2, b + 3]
    lines = ["I", "800", "OBJ", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    lines += [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vt]
    lines += [f"IDX {i}" for i in idx]
    lines += [f"TRIS 0 {len(idx)}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return str(path)


def _member(path, name, e0, e1, n0, n1):
    ring = (ll(e0, n0), ll(e1, n0), ll(e1, n1), ll(e0, n1), ll(e0, n0))
    return types.SimpleNamespace(
        resource=name, heading_deg=0.0, origin=(LAT0, LON0),
        live_path=path, authored_path=path,
        parts=(types.SimpleNamespace(rings=(ring,), base_y=-3.0),)), ring


class _Dem:
    def __init__(self, f):
        self.f = f

    def z(self, x, y):
        return self.f(x, y)


def _airport(tmp_path, ramp_y1, roof_y, dem):
    # a ramp 8 m wide, 100 m long, from y 0 (south) to ramp_y1 (north),
    # beside a 40 x 60 m building whose roof is flat at roof_y
    ramp = _obj(tmp_path / "ramp.obj", [(0, 8, 0, -100, 0.0, ramp_y1)])
    bldg = _obj(tmp_path / "bldg.obj", [(20, 60, 0, -60, roof_y, roof_y)])
    m1, r1 = _member(ramp, "ramp.obj", 0, 8, 0, 100)
    m2, r2 = _member(bldg, "bldg.obj", 20, 60, 0, 60)
    unit = types.SimpleNamespace(id="unit:0", anchor=(LAT0, LON0),
                                 members=(m1, m2))
    cl = types.SimpleNamespace(id="unit:0#0", unit="unit:0",
                               members=("ramp.obj", "bldg.obj"),
                               rings=(r1, r2))
    return types.SimpleNamespace(partition=types.SimpleNamespace(units=(unit,)),
                                 clusters=(cl,), dem=_Dem(dem))


def _ground(x, y):
    # the building's ground flat at 10 m; the ramp's ground falls north
    # from 14 m at its south end (its low end, y = 0, is 4 m under it)
    return 14.0 - 0.04 * y if x < 10.0 else 10.0


@pytest.fixture
def law():
    return load_default()


def test_sunken_ramp_end_leaves_the_pad(tmp_path, law):
    ap = _airport(tmp_path, 5.6, 12.0, _ground)
    shade = sr.sunken_ramp_shades(ap, law, to_xy)
    assert shade is not None, "the sunken ramp end must leave the pad"
    # the low end (deck 3.9 m under the ground) and the stretch where the
    # deck rises out of the ground are not the pad's ...
    assert shade.contains(Point(4.0, 10.0))
    assert shade.contains(Point(4.0, 60.0))
    # ... where the ground is at the pad's level the pad stays
    assert not shade.contains(Point(4.0, 97.0))
    # the building on the same pad keeps its ground
    assert not shade.intersects(Point(40.0, 30.0).buffer(5.0))
    assert sr.SUNKEN["count"] == 1
    assert sr.SUNKEN["ramps"][0]["member"] == "ramp.obj"


def test_a_flat_roof_in_a_cut_is_not_a_ramp(tmp_path, law):
    # the same footprint, a FLAT top 1 m over its zero: it never climbs
    # through the ground, so it is a building in a cut and keeps its pad
    ap = _airport(tmp_path, 1.0, 12.0, _ground)
    assert sr.sunken_ramp_shades(ap, law, to_xy) is None


def test_a_ramp_whose_end_meets_the_ground_keeps_its_pad(tmp_path, law):
    # the low end stands ON the ground (the pad's level): nothing is cut,
    # nothing leaves (10-03e's landings own a ramp end over the ground)
    ap = _airport(tmp_path, 5.6, 12.0, lambda x, y: 10.0)
    assert sr.sunken_ramp_shades(ap, law, to_xy) is None


def test_the_shade_travels_on_the_airport(tmp_path, law):
    """The mint (``classify``) and the census (``constraints``, which may
    not import ``airport``) read ONE derivation: ``Airport.sunken_ramps``,
    unioned with the welded decks' shades by ``geom.with_shade``."""
    import dataclasses as dc

    from auto_patch_v2.geom import with_shade
    from auto_patch_v2.model.airport import Airport

    ap = _airport(tmp_path, 5.6, 12.0, _ground)
    sunk = sr.sunken_ramp_shades(ap, law, to_xy)
    assert "sunken_ramps" in {f.name for f in dc.fields(Airport)}
    other = Point(500.0, 500.0).buffer(3.0)
    both = with_shade(other, sunk)
    assert both.contains(Point(500.0, 500.0)) and both.contains(Point(4.0, 10.0))
    assert with_shade(None, sunk).equals(sunk)
    assert with_shade(other, None) is other


def test_the_top_surface_tool_reads_the_engines_raster(tmp_path):
    """``tools/obj8_top_surface.py`` (its INDEX row): the deck's top over
    the fixture ramp — its low end at its zero, climbing north."""
    import importlib.util
    import math as _m
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "obj8_top_surface",
        Path(__file__).resolve().parents[2] / "tools" / "obj8_top_surface.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    obj = _obj(tmp_path / "ramp.obj", [(0, 8, 0, -100, 0.0, 5.6)], skirt=False)
    ys, xs, T = mod.top_grid(obj, LAT0, LON0, 0.0, *ll(4.0, 50.0), 60.0, 4.0)
    col = int(_m.floor((0.0 - xs[0]) / 4.0))
    south = T[int((-46.0 - ys[0]) // 4.0), col]
    north = T[int((46.0 - ys[0]) // 4.0), col]
    assert 0.0 <= south < 0.5 and 5.0 < north <= 5.6
    assert _m.isnan(T[0, 0])
    assert "the site is the centre" in mod.render(ys, xs, T)[0]
