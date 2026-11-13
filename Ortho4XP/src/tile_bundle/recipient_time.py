"""THE RECIPIENT'S TIME (#2014 follow-up; owner 2026-11-11T16:45Z: "I
don't think the KLAX tile has ever built in 10 minutes, and is that
taking into account estimated download times?").

A recipient of a package builds the WHOLE tile (every airport on it is
graded against the recipient's packs) and first fetches what the package
left out.  Its time is a list of ROWS, one per step, each priced from
what THIS machine recorded (``o4_engine.tile_time_model``: the tile's
own builds first, then every tile's, then a fixed ballpark), with a
range:

* ``map`` — the OpenStreetMap layers left out: one Overpass query each
  (``source_bytes.OVERPASS_SECONDS_PER_LAYER``) plus their bytes;
* ``elevation`` — the rasters left out: their source bytes, plus the
  gridding of each airport inset and approach-ring (or band) cell.  The
  gridding is fitted on this machine's records (a build that fetched
  ``insets_fetched`` insets and ``rings_fetched`` ring cells spent that
  much more in its vector step than a warm one); the fit includes this
  machine's own fetch, so each cell's share of the planning download is
  taken out of it, never below :data:`MIN_GRID_SHARE` of it;
* ``vector`` — the map step without its airports (warm records:
  vector seconds minus ``autopatch_seconds``);
* ``airports`` — every airport of the tile graded, in parallel: the
  recorded finish of each airport (``airport_seconds``) scheduled on
  this machine's cores, longest first; without those, the recorded
  wall of the tile's airport phase (``autopatch_seconds``).  The pack
  partition is inside it (each airport reads its pack while grading);
* ``mesh`` — the mesh step, which ends with the object stage (the
  pack's objects split and seated on the new mesh);
* ``masks`` — the water masks.

Downloads are timed at :data:`BYTES_PER_SECOND` (a planning figure both
apps state; providers serve windowed reads well under a line rate:
0.7 MB/s measured on the arcgis lidar exports this machine recorded).
Imagery is the recipient's own and never counted.  Every figure is an
ESTIMATE.  No tile or airport is named here.
"""
from __future__ import annotations

import math
import os
import statistics

from . import source_bytes as _src

__all__ = ["BYTES_PER_SECOND", "SPREAD", "CELL_SECONDS", "MIN_GRID_SHARE", "LABELS",
           "processing_rows", "acquisition_rows", "grid_rate", "totals",
           "breakdown_text"]

#: The planning download rate (module doc), stated in both apps.
BYTES_PER_SECOND = 2_000_000
#: A range from fewer than three samples is widened to at least this
#: share of their middle (a few builds say roughly how long, not how
#: precisely).
SPREAD = (0.8, 1.25)
#: Fetching and gridding one elevation cell when this machine has too few
#: records (:func:`grid_rate` over the 264 fetching records of the
#: owner's machine, 2026-11-11: 11.2 s).
CELL_SECONDS = 11.2
#: The least share of a fitted cell time kept as gridding (module doc).
MIN_GRID_SHARE = 0.25

#: Each row's words, in the order both apps list them.
LABELS = {"map": "map data", "elevation": "elevation", "vector": "map processing",
          "airports": "airports", "mesh": "mesh and objects", "masks": "masks"}

_FALLBACK = {"vector": 30.0, "mesh": 60.0, "masks": 30.0}


def _finite(values) -> list:
    return [float(v) for v in values
            if isinstance(v, (int, float)) and math.isfinite(v) and v >= 0]


def _spread(samples, fallback: float) -> tuple:
    """``(middle, low, high)`` of ``samples`` (module doc)."""
    samples = _finite(samples)
    if not samples:
        return fallback, fallback * SPREAD[0], fallback * SPREAD[1]
    mid = statistics.median(samples)
    low, high = min(samples), max(samples)
    if len(samples) < 3:
        low, high = min(low, mid * SPREAD[0]), max(high, mid * SPREAD[1])
    return mid, low, high


def _features(record) -> dict:
    return record.get("features") or {} if isinstance(record, dict) else {}


def _step(record, step):
    return ((record.get("step_seconds") or {}).get(step)
            if isinstance(record, dict) else None)


def _warm(record) -> bool:
    f = _features(record)
    return not (f.get("insets_fetched") or f.get("rings_fetched"))


def _residual(record):
    vector = _step(record, "vector")
    if vector is None:
        return None
    return float(vector) - float(_features(record).get("autopatch_seconds") or 0.0)


def _row(step: str, label: str, mid: float, low: float, high: float,
         download_bytes: int = 0, download_seconds: float = 0.0) -> dict:
    return {"step": step, "label": label, "seconds": round(mid, 1),
            "low": round(low, 1), "high": round(high, 1),
            "download_bytes": int(download_bytes),
            "download_seconds": round(download_seconds, 1)}


def _makespan(seconds, slots: int) -> float:
    """The airports' wall time on ``slots`` workers, longest first."""
    loads = [0.0] * max(1, slots)
    for value in sorted(seconds, reverse=True):
        loads[loads.index(min(loads))] += value
    return max(loads)


def _airports_row(tile: list, every: list) -> dict:
    graded = [r for r in tile if (_features(r).get("airports") or 0) > 0]
    timed = [r for r in graded if _features(r).get("airport_seconds")]
    if timed:
        names = sorted(_features(timed[-1])["airport_seconds"])
        per = {icao: _finite(_features(r).get("airport_seconds", {}).get(icao)
                             for r in timed) for icao in names}
        slots = min(len(names), os.cpu_count() or 1)
        mids = {i: statistics.median(v) for i, v in per.items() if v}
        longest = max(mids, key=mids.get)
        return _row("airports", "%d airports in parallel (longest %s, about %d min)"
                    % (len(names), longest, round(mids[longest] / 60.0)),
                    _makespan(mids.values(), slots),
                    _makespan([min(v) for v in per.values() if v], slots),
                    _makespan([max(v) for v in per.values() if v], slots))
    if graded:
        count = int(_features(graded[-1]).get("airports") or 0)
        mid, low, high = _spread([_features(r).get("autopatch_seconds")
                                  for r in graded], 0.0)
        return _row("airports", "%d airports in parallel, as recorded here" % count,
                    mid, low, high)
    from o4_engine import tile_time_model
    per = [float(_features(r)["autopatch_seconds"]) / _features(r)["airports"]
           for r in every if (_features(r).get("airports") or 0) > 0
           and (_features(r).get("autopatch_seconds") or 0) > 0]
    low, high = (min(per), max(per)) if per else tile_time_model.DEFAULT_AIRPORT_SECONDS_RANGE
    return _row("airports", "the tile's airports (none recorded here)",
                statistics.median(per) if per else (low + high) / 2.0, low, high)


def processing_rows(lat: int, lon: int) -> list:
    """The ``vector``, ``airports``, ``mesh`` and ``masks`` rows of tile
    (lat, lon) on this machine (module doc)."""
    from o4_engine.tile_time_model import every_record, tile_records
    tile = tile_records(lat, lon)
    every = every_record()
    rows = []
    for step in ("vector", "airports", "mesh", "masks"):
        if step == "airports":
            rows.append(_airports_row(tile, every))
            continue
        pick = (_residual if step == "vector" else (lambda r, s=step: _step(r, s)))
        own = [pick(r) for r in tile if step != "vector" or _warm(r)]
        if not _finite(own):
            own = [pick(r) for r in every if step != "vector" or _warm(r)]
        mid, low, high = _spread(own, _FALLBACK[step])
        rows.append(_row(step, LABELS[step], mid, low, high))
    return rows


def grid_rate() -> float:
    """Seconds per elevation cell (an airport inset or an approach-ring
    or band cell): over every build this machine recorded that fetched
    cells, the median of what its vector step spent beyond a warm one,
    per cell (module doc; cells fetch in parallel, so a build of many
    cells costs less per cell); :data:`CELL_SECONDS` without one."""
    from o4_engine.tile_time_model import every_record
    every = every_record()
    warm = _finite(_residual(r) for r in every if _warm(r))
    base = statistics.median(warm) if warm else 0.0
    per = []
    for record in every:
        cells = (int(_features(record).get("insets_fetched") or 0)
                 + int(_features(record).get("rings_fetched") or 0))
        residual = _residual(record)
        if cells > 0 and residual is not None:
            per.append((residual - base) / cells)
    per = [p for p in _finite(per) if p > 0]
    return statistics.median(per) if len(per) >= 8 else CELL_SECONDS


def _gridding(row: dict, rate: float) -> float:
    """Gridding ``row``'s cells (module doc), seconds."""
    if not row or not row["files"]:
        return 0.0
    each = row["source_bytes"] / row["files"] / BYTES_PER_SECOND
    return row["files"] * max(MIN_GRID_SHARE * rate, rate - each)


def acquisition_rows(left: dict, rate: "float | None" = None) -> list:
    """The ``map`` and ``elevation`` rows of the data ``left``
    (``source_bytes.left_out``) out of a package (module doc)."""
    rows = []
    osm = left.get("osm")
    if osm:
        rows.append(_row(
            "map", "%d OpenStreetMap layers" % osm["files"], 0.0, 0.0, 0.0,
            osm["source_bytes"], osm["files"] * _src.OVERPASS_SECONDS_PER_LAYER
            + osm["source_bytes"] / BYTES_PER_SECOND))
    kinds = [k for k in ("base", "inset", "ring", "band", "sidecar") if left.get(k)]
    if kinds:
        rate = grid_rate() if rate is None else rate
        grid = sum(_gridding(left.get(k), rate) for k in ("inset", "ring", "band"))
        dl = sum(left[k]["source_bytes"] for k in kinds)
        words = {"base": "base rasters", "inset": "airport insets",
                 "ring": "approach-ring cells", "band": "band cells"}
        label = ", ".join("%d %s" % (left[k]["files"], words[k])
                          for k in kinds if k in words) or "elevation sidecars"
        rows.append(_row("elevation", label, grid, grid * SPREAD[0],
                         grid * SPREAD[1], dl, dl / BYTES_PER_SECOND))
    return rows


def totals(rows) -> dict:
    """``{"seconds", "low", "high", "download_bytes", "download_seconds"}``
    of ``rows``: each row's own time plus its download."""
    out = {"seconds": 0.0, "low": 0.0, "high": 0.0, "download_bytes": 0,
           "download_seconds": 0.0}
    for row in rows:
        for key in ("seconds", "low", "high"):
            out[key] += row[key] + row["download_seconds"]
        out["download_bytes"] += row["download_bytes"]
        out["download_seconds"] += row["download_seconds"]
    return {k: (round(v, 1) if isinstance(v, float) else v) for k, v in out.items()}


def _minutes(seconds: float) -> str:
    return "under 1 min" if seconds < 30 else "%d min" % round(seconds / 60.0)


def breakdown_text(rows) -> str:
    """The rows in one line, as both export windows show it."""
    return " · ".join("%s %s (%s)" % (LABELS[r["step"]], _minutes(
        r["seconds"] + r["download_seconds"]), r["label"])
        if r["step"] in ("map", "elevation", "airports")
        else "%s %s" % (LABELS[r["step"]], _minutes(r["seconds"])) for r in rows)
