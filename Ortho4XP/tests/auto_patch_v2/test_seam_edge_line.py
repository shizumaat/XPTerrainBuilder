"""Twin for the seam pin's value (owner 2026-11-04, LOWS "yes"): a tile-seam
pin takes the TILE EDGE's straight line at its station — the DEM at the two
mesh edge points bracketing it, linearly between — never the dense DEM, so
the band between the pins and the edge is level across.  The edge points are
the mesh builder's own (``O4_Vector_Map.GLUE_SEGMENTS``); the law reads the
same count.  Synthetic DEM and frame; nothing here names an airport."""
from __future__ import annotations

import math
import os
import re
from types import SimpleNamespace

from auto_patch_v2.constraints.seams import seam_pin_z, seam_pins
from auto_patch_v2.law import Law
from auto_patch_v2.model.frame import Frame

LAW = Law.for_airport("ZZZZ")
N = LAW.tables.emit.seam.edge_segments


def test_the_law_reads_the_mesh_builders_edge_segments():
    src = os.path.join(os.path.dirname(__file__), "..", "..", "src", "O4_Vector_Map.py")
    with open(src, encoding="utf-8") as fh:
        got = re.search(r"^GLUE_SEGMENTS = (\d+)$", fh.read(), re.M)
    assert got is not None and int(got.group(1)) == N


def _site():
    frame = Frame("ZZZZ", origin=(47.8, 13.0), identity_dp=11)
    to_xy, to_ll = frame.transformers()

    class _Dem:
        provenance = {"synthetic": "curved along the seam"}

        def z(self, x, y):
            lat, _lon = to_ll(x, y)
            return 400.0 + 1e7 * (lat - 47.8) ** 2 + (0.5 if x > 0 else 0.0)

    return frame, to_xy, _Dem()


def test_a_seam_pin_takes_the_edge_line_and_an_edge_point_its_dem():
    frame, to_xy, dem = _site()
    lo = math.floor(47.8 * N) / N
    lats = (lo + 0.37 / N, lo, lo + 0.81 / N)
    keys = [(la, 13.0 - 0.00004) for la in lats] + [(lats[0], 13.0 + 0.00004)]
    planar = SimpleNamespace(
        seam_vertices=set(range(len(keys))),
        vertices={i: SimpleNamespace(key=k, dem_z=dem.z(*to_xy(k[1], k[0])))
                  for i, k in enumerate(keys)})
    got = seam_pin_z(planar, LAW, SimpleNamespace(dem=dem, frame=frame))

    def edge(lat, side):
        a = math.floor(lat * N) / N
        za, zb = (dem.z(*to_xy(13.0 + side * 0.01 / N, t)) for t in (a, a + 1.0 / N))
        return za + (zb - za) * (lat - a) * N
    for i, (la, lon) in enumerate(keys):
        side = -1.0 if lon < 13.0 else 1.0
        assert abs(got[i] - edge(la, side)) < 1e-9
    # the dense DEM is curved between the edge points: the pin does not follow it
    assert abs(got[0] - planar.vertices[0].dem_z) > 0.01
    # AT an edge point the pin is that point's DEM (the seam stays DEM-locked)
    assert abs(got[1] - dem.z(*to_xy(13.0 - 0.01 / N, lo))) < 1e-9
    # each side reads its own tile's raster
    assert abs((got[3] - got[0]) - 0.5) < 1e-9
    assert [p.z for p in seam_pins(planar, LAW, SimpleNamespace(dem=dem, frame=frame))] \
        == [got[i] for i in sorted(got)]
