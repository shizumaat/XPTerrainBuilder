"""THE ISLAND'S SHORE ROADS STAND AT THE FLAT LEVEL (issue #1885; owner
2026-11-04T18:57Z, verbatim: "specifically for 'flat' airports like VHHH on
fill, when the road is close to the airport and the other side nearby is
water, we should include that in the airport 'island' area").

THE DEFECT.  The flat-site plateau is a fill, not a cut (RULINGS
2026-10-26r / 27d, ``auto_patch/flat_site_relief.py``): off the held ground
(pavement, runways, the pack's pavement pages, the runway strips) every
post whose honest surface stands more than 0.5 m above Z0 gets that
surface back.  Outside the aerodrome boundary nothing grades the roads
(the patch ribbons roads only up to ``osm_roads.boundary_reach_m``
outside it), so a road on the restored surface follows it.  At VHHH that
surface along the east shore is the 5 m DEM's own reading of the
flyovers, ramps and kerbs the roads stand on — 1 to 11 m lumps under the
Airport Expressway interchange and round the north-east corner, on
reclaimed ground the rest of the island holds flat at Z0.

THE RULE (one geometry, handed to the fill-only pass as more held ground):
a station of a mapped road — a ribbon class, never a mapped bore
(``deck_signature.is_tunnel_way``: a tunnel keeps its ramps) — is held at
Z0 when it stands

  * OUTSIDE the aerodrome (the decision record's margin-0 ``gate``: inside
    it the patch grades the groundside roads by their own rules, RULINGS
    2026-10-27v (1)),
  * ON THE AIRPORT'S SEA-BOUNDED ISLAND (the R21 island component, the
    land-component test RULINGS 2026-08-12 made the connection law: "the
    other side nearby is water"; a mainland component is never flattened),
  * BESIDE THE FLAT LEVEL — somewhere on two rings round the station (half
    and all of the carriageway's half-width + ``side_probe_m``) the honest
    surface stands within ``flat_site_relief.REAL_FROM_M`` of Z0 (the
    height under which the fill-only pass still holds the plateau in
    part).  The hill guard: a road climbing real high ground has it all
    round and keeps the real surface — VHHH's Scenic Hill roads and the
    expressway's tunnel approaches into it; a road whose own deck or
    embankment the DEM reads as a lump has the fill beside it.

"Close to the airport" is the plateau's own reach: only a post the stamp
lowered is ever restored, so the hold acts inside the stamped footprint
(boundary ⊕ ``[detector] margin_m`` and each admitted claimed-object
cluster) and nowhere else.  The caller gates the site: a substituting flat
verdict ON FILL (``[shore_roads] fill_min_m``).  Each held stretch is the
carriageway (``road_ways.ribbon_half_width_m``) grown one DEM post diagonal
— the bilinear stencil the runway strips are held with
(``flat_site_prep.decide``) — and clipped back from the aerodrome by the
same diagonal, and from the roads the patch itself ribbons up to
``osm_roads.boundary_reach_m`` outside it, so no DEM post the solve reads
changes (airside is king, RULINGS 2026-07-30).

Pure: tile-relative degrees in, tile-relative degrees out; it reads no
file and writes nothing.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np
from shapely import affinity, contains_xy
from shapely.geometry import LineString
from shapely.ops import unary_union

from .deck_signature import is_tunnel_way
from .road_ways import ribbon_half_width_m

__all__ = ["shore_road_hold", "on_fill", "site_hold"]


def _metres(geom, scale):
    return affinity.scale(geom, scale[0], scale[1], origin=(0.0, 0.0))


def _stations(line: LineString, step_m: float) -> np.ndarray:
    n = max(2, int(math.ceil(line.length / step_m)) + 1)
    return np.array([line.interpolate(d).coords[0]
                     for d in np.linspace(0.0, line.length, n)])


#: The hill guard's compass: the honest surface is read this many ways
#: round each station, at half and at the full reach.
_BEARINGS = 16


def _beside_flat(st: np.ndarray, honest, scale, level: float,
                 reach_m: float) -> np.ndarray:
    """Per station: does the honest surface stand at or under ``level``
    anywhere on the two rings (``reach_m`` / 2 and ``reach_m``) round it —
    the flat level beside the road, which a lump the road itself makes
    has and a hill it climbs does not (module doc)."""
    a = np.linspace(0.0, 2.0 * math.pi, _BEARINGS, endpoint=False)
    ring = np.concatenate([np.column_stack((np.cos(a), np.sin(a))) * r
                           for r in (0.5 * reach_m, reach_m)])
    px = (st[:, 0][:, None] + ring[None, :, 0]) / scale[0]
    py = (st[:, 1][:, None] + ring[None, :, 1]) / scale[1]
    z = honest(px.ravel(), py.ravel()).reshape(px.shape)
    return np.nanmin(z, axis=1) <= level


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    out, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j + 1 < len(mask) and mask[j + 1]:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def shore_road_hold(ways: _t.Iterable[_t.Any], highways: _t.Collection[str],
                    gate, island, honest: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                    z0_m: float, flat_within_m: float, side_probe_m: float,
                    post_m: float, metres_per_degree: tuple[float, float],
                    tile_lat: int, tile_lon: int, law,
                    clear_m: float = 0.0) -> tuple[_t.Any, dict]:
    """``(held, report)`` — the shore-road carriageways to hold at Z0 as one
    tile-relative geometry (``None`` when none qualifies) and the counts
    (module doc).  ``ways`` carry ``points`` ``(lat, lon)`` and ``tags``
    (``osm.RawWay``); ``honest(xs, ys)`` reads the surface before the
    stamp at tile-relative points; ``flat_within_m`` the hill guard's
    height over Z0; ``post_m`` the DEM posting; ``clear_m`` how far outside
    the aerodrome the patch itself grades the roads (none of it is held)."""
    report = {"ways": 0, "held_m": 0.0, "stations": 0, "hill_kept": 0}
    if gate is None or island is None or island.is_empty:
        return None, report
    sx, sy = metres_per_degree
    gate_m, island_m = _metres(gate, (sx, sy)), _metres(island, (sx, sy))
    pieces = []
    for w in ways:
        tags = getattr(w, "tags", None) or {}
        if tags.get("highway") not in highways or is_tunnel_way(tags):
            continue
        pts = [((lon - tile_lon) * sx, (lat - tile_lat) * sy)
               for lat, lon in getattr(w, "points", ())]
        if len(pts) < 2:
            continue
        line = LineString(pts)
        if line.length <= 0 or not line.intersects(island_m):
            continue
        st = _stations(line, post_m)
        ok = (contains_xy(island_m, st[:, 0], st[:, 1])
              & ~contains_xy(gate_m, st[:, 0], st[:, 1]))
        if not ok.any():
            continue
        half = ribbon_half_width_m(tags, law)
        beside_flat = _beside_flat(st, honest, (sx, sy), z0_m + flat_within_m,
                                   half + side_probe_m)
        report["hill_kept"] += int((ok & ~beside_flat).sum())
        ok &= beside_flat
        runs = _runs(ok)
        if not runs:
            continue
        report["ways"] += 1
        grow = half + post_m * math.sqrt(2.0)
        for i, j in runs:
            seg = st[i:j + 1]
            report["stations"] += len(seg)
            part = (LineString(seg) if len(seg) > 1
                    else LineString([seg[0], seg[0] + 1e-6]))
            report["held_m"] += part.length
            pieces.append(part.buffer(grow))
    report["held_m"] = round(report["held_m"], 1)
    if not pieces:
        return None, report
    # AIRSIDE IS KING: the hold stays out of the ground the PATCH grades —
    # the aerodrome and its roads up to ``clear_m`` outside it — and one
    # post diagonal beyond (the bilinear stencil an edge vertex reads), so
    # no DEM post the solve reads changes; a patch road welded to an apron
    # would otherwise carry the new ground onto the apron
    held = unary_union(pieces).difference(
        gate_m.buffer(clear_m + post_m * math.sqrt(2.0)))
    if held.is_empty:
        return None, report
    return _metres(held, (1.0 / sx, 1.0 / sy)), report


def on_fill(record: _t.Mapping, fill_min_m: float) -> bool:
    """Does the plateau RAISE this airport — Z0 at least ``fill_min_m``
    above the detector's honest S2 median (``[shore_roads] fill_min_m``)?"""
    s2 = ((record.get("signals") or {}).get("s2") or {})
    median, z0 = s2.get("median_m"), record.get("z0_m")
    return (median is not None and z0 is not None
            and float(z0) - float(median) >= float(fill_min_m))


def _snapshot_sampler(snapshot, frame):
    """``honest(xs, ys)`` — nearest post of the fill-only pass's snapshot
    (``flat_site_relief.snapshot_window``) at tile-relative points; NaN
    off the window."""
    row_min, _row_max, col_min, _col_max, before = snapshot
    x0, x1, y0, y1, nx, ny = frame
    x_step, y_step = (x1 - x0) / (nx - 1), (y1 - y0) / (ny - 1)

    def honest(xs, ys):
        c = np.rint((np.asarray(xs) - x0) / x_step).astype(int) - col_min
        r = np.rint((y1 - np.asarray(ys)) / y_step).astype(int) - row_min
        inside = (c >= 0) & (r >= 0) & (c < before.shape[1]) & (r < before.shape[0])
        out = np.full(c.shape, np.nan)
        out[inside] = before[r[inside], c[inside]]
        return out
    return honest, (x_step, y_step)


def site_hold(record: _t.Mapping, law, gate, snapshot, frame, island_of,
              ways_of, highways, tile_lat: int, tile_lon: int,
              metres_per_degree: tuple[float, float], real_from_m: float,
              clear_m: float = 0.0):
    """``(held, why)`` — one airport's shore-road hold for the fill-only
    pass (tile-relative degrees, ``None`` when nothing is held) and a
    one-line reason or count.  ``gate`` is the record's ``gate_ll`` as a
    tile-relative geometry; ``frame`` the working grid's ``(x0, x1, y0, y1,
    nx, ny)``; ``island_of(gate)`` the R21 island component (``(island,
    refusal)``); ``ways_of(lat0, lon0, lat1, lon1)`` the mapped roads over
    that box; ``metres_per_degree`` ``(lon_m, lat_m)`` the fill-only pass's
    own scale.  ``real_from_m`` is the fill-only pass's own constant
    (``flat_site_relief.REAL_FROM_M``): the hill guard's flat level is
    ``Z0 + real_from_m``, the height from which that pass gives the honest
    surface back in full; ``clear_m`` the patch's own road reach outside
    the aerodrome (``osm_roads.boundary_reach_m``), which is never held."""
    cfg = law.tables.flat_site.shore_roads
    if not cfg.enabled or snapshot is None or gate is None:
        return None, "off"
    if not on_fill(record, cfg.fill_min_m):
        return None, "not on fill"
    island, refusal = island_of(gate)
    if island is None:
        return None, f"no island ({refusal})"
    honest, (x_step, y_step) = _snapshot_sampler(snapshot, frame)
    lon_m, lat_m = metres_per_degree
    row_min, row_max, col_min, col_max, _before = snapshot
    x0, _x1, _y0, y1, _nx, _ny = frame
    lon0, lon1 = tile_lon + x0 + col_min * x_step, tile_lon + x0 + col_max * x_step
    lat0, lat1 = tile_lat + y1 - row_max * y_step, tile_lat + y1 - row_min * y_step
    held, rep = shore_road_hold(
        ways_of(lat0, lon0, lat1, lon1), highways, gate, island, honest,
        float(record["z0_m"]), real_from_m, cfg.side_probe_m,
        abs(x_step) * lon_m, (lon_m, lat_m), tile_lat, tile_lon, law, clear_m)
    return held, (f"{rep['ways']} way(s), {rep['held_m']:.0f} m of carriageway "
                  f"on the sea-bounded island outside the aerodrome held at "
                  f"Z0; {rep['hill_kept']} station(s) on high ground keep "
                  f"the real surface")
