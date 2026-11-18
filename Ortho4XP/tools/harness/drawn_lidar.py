"""THE DRAWN GATE'S LIDAR LAYER (#2128 round 2, spec ``2128-R2.md`` §5 / plan
step 1): does the ground X-Plane draws near a judged site follow the
airport's credible survey?

``tools/harness/drawn_gate.py --site NAME=LAT,LON[,R] --lidar-dev``: the
drawn mesh is sampled on a :data:`GRID_M` grid inside each site's radius and
read against the airport's cached elevation inset (the provider ranking's
first raster naming the ICAO, ``O4_Airport_Elevation_Insets.
cached_inset_paths_for_icao``; bilinear).  Two readings per site:

* GROUND -- the share of drawn samples with ``|drawn - lidar| >``
  :data:`DEV_M`, OUTSIDE every hard-deck ring (the hull of a deck's two end
  lines, the sidecar ``deck_anchors`` stations: a survey reads the deck, the
  mesh the floor under it) and OUTSIDE the patch's kept airside pavement
  (closed ways of an airside pavement role: graded by law, never the
  survey).  FAIL over :data:`SHARE_BAR` (2.0 %).
* ROADS -- every mapped vehicle road (``drawn_roads.road_lines``; a mapped
  bridge is skipped, a stretch under one is not read) sampled every
  :data:`ROAD_STEP_M` farther than :data:`DECK_EDGE_M` from every deck ring:
  FAIL where ``|drawn - lidar|`` exceeds :data:`ROAD_DEV_M` (0.5 m).

Promotes the #2128 round-1 lane's scratch ``site_stats.py`` (its second
use).  The layer reads products and the shared inset only, never a capture.
Nothing here names an airport.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

__all__ = ["DEV_M", "SHARE_BAR", "ROAD_DEV_M", "DECK_EDGE_M", "GRID_M", "ROAD_STEP_M",
           "deck_rings", "airside_pavement", "inset_path", "Lidar", "lidar_layer"]

#: a drawn sample this far off the survey is visibly not the surveyed ground
DEV_M = 2.0
#: the share of ground samples (percent) a site may hold past :data:`DEV_M`
SHARE_BAR = 2.0
#: a mapped road farther than :data:`DECK_EDGE_M` from a deck follows the survey to this
ROAD_DEV_M = 0.5
#: roads within this of a deck ring are its trench's (the ring's own frame)
DECK_EDGE_M = 25.0
#: the ground grid and the road sampling step (m)
GRID_M = 1.0
ROAD_STEP_M = 1.0
_M_PER_DEG = 111320.0


def deck_rings(sidecar) -> list:
    """``[[(lat, lon), ...]]``: per deck object, the hull of its end lines'
    stations (sidecar ``deck_anchors``) -- the deck's ring as drawn."""
    from shapely.geometry import MultiPoint
    by: dict = {}
    for r in (sidecar or {}).get("deck_anchors", []) or ():
        by.setdefault(str(r.get("object")), []).extend(
            (float(la), float(lo)) for la, lo in r.get("stations", []) or ())
    out = []
    for pts in by.values():
        if len(pts) < 3:
            continue
        hull = MultiPoint([(lo, la) for la, lo in pts]).convex_hull
        if hull.geom_type == "Polygon":
            out.append([(la, lo) for lo, la in hull.exterior.coords])
    return out


def airside_pavement(patch_path, icao) -> list:
    """``[[(lat, lon), ...]]``: every closed patch way of an AIRSIDE PAVEMENT
    role (``law.tables.pavement_roles`` whose ``role_side`` is airside)."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import pavement_roles, role_side
    law = Law.for_airport(icao)
    paved = {r for r in pavement_roles(law) if role_side(law, r) == "airside"}
    nodes, out = {}, []
    for _ev, el in ET.iterparse(patch_path):
        if el.tag == "node":
            nodes[el.get("id")] = (float(el.get("lat")), float(el.get("lon")))
        elif el.tag == "way":
            role = {t.get("k"): t.get("v") for t in el.findall("tag")}.get("role")
            refs = [nd.get("ref") for nd in el.findall("nd")]
            if role in paved and len(refs) >= 4 and refs[0] == refs[-1]:
                out.append([nodes[r] for r in refs if r in nodes])
            el.clear()
    return out


def inset_path(icao, tile_lat, tile_lon) -> "str | None":
    """The airport's cached elevation inset (the provider ranking's first)."""
    import O4_Airport_Elevation_Insets as INS
    got = INS.cached_inset_paths_for_icao(tile_lat, tile_lon, icao)
    return got[0] if got else None


class Lidar:
    """Bilinear reads of one inset raster (nan off it or on nodata)."""

    def __init__(self, path=None, array=None, geotransform=None, nodata=None):
        import numpy as np
        if path is not None:
            from osgeo import gdal
            gdal.UseExceptions()
            ds = gdal.Open(path)
            band = ds.GetRasterBand(1)
            array, geotransform, nodata = band.ReadAsArray(), ds.GetGeoTransform(), \
                band.GetNoDataValue()
        a = np.asarray(array, dtype=float)
        if nodata is not None:
            a = np.where(a == nodata, np.nan, a)
        self.a, self.gt = a, tuple(geotransform)

    def z(self, lats, lons):
        """The survey at ``(lats, lons)`` (arrays)."""
        import numpy as np
        gt = self.gt
        c = (np.asarray(lons, dtype=float) - gt[0]) / gt[1] - 0.5
        r = (np.asarray(lats, dtype=float) - gt[3]) / gt[5] - 0.5
        c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int)
        ok = (c0 >= 0) & (r0 >= 0) & (c0 + 1 < self.a.shape[1]) & (r0 + 1 < self.a.shape[0])
        c0, r0 = np.where(ok, c0, 0), np.where(ok, r0, 0)
        fc, fr = c - c0, r - r0
        a = self.a
        v = (a[r0, c0] * (1 - fc) * (1 - fr) + a[r0, c0 + 1] * fc * (1 - fr)
             + a[r0 + 1, c0] * (1 - fc) * fr + a[r0 + 1, c0 + 1] * fc * fr)
        return np.where(ok, v, np.nan)


def _local(rings, lat0, lon0):
    """The rings as one shapely geometry in metres about ``(lat0, lon0)``."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    kx = _M_PER_DEG * math.cos(math.radians(lat0))
    polys = []
    for ring in rings:
        if len(ring) >= 3:
            p = Polygon([((lo - lon0) * kx, (la - lat0) * _M_PER_DEG) for la, lo in ring])
            polys.append(p if p.is_valid else p.buffer(0.0))
    return unary_union(polys) if polys else None


def lidar_layer(sites, sample_many, lidar, decks=(), paved=(), osm_root=None,
                grid=GRID_M, share_bar=SHARE_BAR, dev=DEV_M, road_dev=ROAD_DEV_M,
                deck_edge=DECK_EDGE_M):
    """The layer over ``sites`` (``(name, lat, lon, r)``).  ``sample_many(lats,
    lons)`` is the drawn mesh (an array, nan off it), ``lidar`` a
    :class:`Lidar`, ``decks`` / ``paved`` the excluded rings
    (:func:`deck_rings`, :func:`airside_pavement`), ``osm_root`` the road
    feeds (``None``: no road reading)."""
    import numpy as np
    import shapely
    rows, failed = [], 0
    for name, lat, lon, r in sites:
        kx = _M_PER_DEG * math.cos(math.radians(lat))
        h = int(r // grid)
        yy, xx = np.mgrid[-h:h + 1, -h:h + 1]
        x, y = (xx * grid).ravel().astype(float), (yy * grid).ravel().astype(float)
        keep = x * x + y * y <= r * r
        x, y = x[keep], y[keep]
        deck_g = _local(decks, lat, lon)
        out = _local([*decks, *paved], lat, lon)
        if out is not None:
            inside = shapely.contains_xy(out, x, y)
            x, y = x[~inside], y[~inside]
        la, lo = lat + y / _M_PER_DEG, lon + x / kx
        d = np.asarray(sample_many(la, lo), dtype=float) - lidar.z(la, lo)
        d = d[~np.isnan(d)]
        share = float(100.0 * (np.abs(d) > dev).mean()) if d.size else None
        row = {"site": name, "samples": int(d.size),
               "share_pct": None if share is None else round(share, 2),
               "above_pct": None if not d.size else round(float(100.0 * (d > dev).mean()), 2),
               "below_pct": None if not d.size else round(float(100.0 * (d < -dev).mean()), 2)}
        bad = share is not None and share > share_bar
        if osm_root is not None:
            worst = _roads(lat, lon, r, sample_many, lidar, deck_g, kx, osm_root, deck_edge)
            row.update(worst)
            bad = bad or (worst.get("road_dev_m") or 0.0) > road_dev
        row["verdict"] = "FAIL" if bad else "PASS" if d.size else "NOT MEASURED"
        failed += bad
        rows.append(row)
    measured = any(r["verdict"] != "NOT MEASURED" for r in rows)
    return {"dev_m": dev, "share_bar_pct": share_bar, "road_dev_m": road_dev,
            "deck_edge_m": deck_edge, "grid_m": grid, "sites": rows, "failed": failed,
            "verdict": "FAIL" if failed else "PASS" if measured else "NOT MEASURED"}


def _roads(lat, lon, r, sample_many, lidar, deck_g, kx, osm_root, deck_edge):
    """The worst ``|drawn - lidar|`` on the site's mapped roads off the decks."""
    import numpy as np
    import shapely
    from drawn_roads import _clip_runs, _under_bridge, road_lines
    bridges: list = []
    roads = road_lines(osm_root, lat, lon, r, bridges)
    under = _under_bridge(bridges, lat, lon)
    near = None if deck_g is None else deck_g.buffer(deck_edge)
    worst = {"road_dev_m": None, "road_samples": 0}
    for wid, hw, pts, *_t in roads:
        for run in _clip_runs(pts, lat, lon, r, ROAD_STEP_M):
            run = [p for p in run if not under(*p)]
            if not run:
                continue
            la = np.array([p[0] for p in run])
            lo = np.array([p[1] for p in run])
            if near is not None:
                off = ~shapely.contains_xy(near, (lo - lon) * kx, (la - lat) * _M_PER_DEG)
                la, lo = la[off], lo[off]
            if not la.size:
                continue
            d = np.asarray(sample_many(la, lo), dtype=float) - lidar.z(la, lo)
            ok = ~np.isnan(d)
            worst["road_samples"] += int(ok.sum())
            if not ok.any():
                continue
            k = int(np.argmax(np.where(ok, np.abs(d), -1.0)))
            if worst["road_dev_m"] is None or abs(d[k]) > worst["road_dev_m"]:
                worst.update(road_dev_m=round(float(abs(d[k])), 2), road_way=wid,
                             road_highway=hw, road_at=[round(float(la[k]), 6),
                                                       round(float(lo[k]), 6)],
                             road_delta=round(float(d[k]), 2))
    return worst
