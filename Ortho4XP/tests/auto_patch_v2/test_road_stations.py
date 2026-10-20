"""The road station table reads what GEOS reads (issue #412 C8)."""
from __future__ import annotations

import numpy as np
from shapely.geometry import LineString, Point

from auto_patch_v2.airport.road_stations import StationTable


def test_the_station_table_projects_as_geos():
    rng = np.random.default_rng(412)
    lines = [np.cumsum(rng.normal(0, 20, (int(rng.integers(2, 30)), 2)), axis=0)
             for _ in range(12)]
    lines.append(np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]))  # a U: ties
    table = StationTable(lines)
    geos = [LineString(xy) for xy in lines]
    pts = list(rng.uniform(-150, 150, (400, 2))) + [(5.0, 5.0), (10.0, 5.0), (-3.0, 0.0)]
    for x, y in pts:
        s, d = table.project(float(x), float(y))
        p = Point(x, y)
        for k, ln in enumerate(geos):
            assert abs(s[k] - ln.project(p)) < 1e-6
            assert abs(d[k] - ln.distance(p)) < 1e-9
