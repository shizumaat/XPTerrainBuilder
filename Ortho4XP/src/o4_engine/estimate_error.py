"""How accurate are the tile build-time estimates?  (#2045)

The engine never logged its predictions, so this REPLAYS them: every
recorded build in the tile store (``tile_time_model.STORE_DIRECTORY``) is
predicted again from the records that existed BEFORE it finished — the
history the live estimate had — and compared with what it measured.

A tile build is a GROUP of records: the phase-aware run records each step
of a tile on its own (``+39-105`` writes vector, mesh, masks, imagery and
overlays as five records), so consecutive records of one tile whose steps
do not repeat and that finished within :data:`BUILD_GAP_S` of each other
are one build.  Each build is classed:

* ``cold`` — it downloaded something the store counts (textures, airport
  elevation insets, approach rings, or spent download seconds); else
  ``cached``;
* ``airports`` — its vector step graded at least one airport; else
  ``no airports``.

Prediction features are the record's own, with the planned download count
set to what the build actually downloaded: the replay measures the TIME
MODEL, not the pre-build cache guess.  ``predict(step, features,
same_tile, every)`` is injectable so a candidate model is judged on the
same builds.  Pure: no writes, never touches the network.
"""

from __future__ import annotations

import math
import statistics

__all__ = ["replay", "summarise", "BUILD_GAP_S"]

#: Records of one tile further apart than this are separate builds.
BUILD_GAP_S = 3600.0


def _features(record):
    return dict(record.get("features") or {})


def _is_cold(feature_list):
    for f in feature_list:
        for key in ("textures_downloaded", "insets_fetched", "rings_fetched",
                    "download_seconds"):
            value = f.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return True
    return False


def _builds(records_by_tile):
    """``[{"tile", "records": [...], "finished_at"}]`` — each tile's
    records grouped into builds (oldest first within a tile)."""
    out = []
    for tile, records in records_by_tile.items():
        records = sorted((r for r in records if isinstance(r, dict)),
                         key=lambda r: float(r.get("finished_at") or 0))
        current, steps, last = [], set(), None
        for record in records:
            keys = set((record.get("step_seconds") or {}).keys())
            at = float(record.get("finished_at") or 0)
            if current and (keys & steps or at - last > BUILD_GAP_S):
                out.append({"tile": tile, "records": current})
                current, steps = [], set()
            current.append(record)
            steps |= keys
            last = at
        if current:
            out.append({"tile": tile, "records": current})
    for build in out:
        build["finished_at"] = float(
            build["records"][-1].get("finished_at") or 0)
    return out


def _error_ratio(predicted, actual):
    """``predicted / actual`` (1.0 = exact); None for a zero actual."""
    if not actual or actual <= 0:
        return None
    return float(predicted) / float(actual)


def _planned_airports(same_tile_records):
    """The airports the tile's newest earlier vector record solved —
    what a build knows before its vector step starts — or None."""
    for record in reversed(same_tile_records):
        seconds = (record.get("features") or {}).get("airport_seconds")
        if "vector" in (record.get("step_seconds") or {}) \
                and isinstance(seconds, dict):
            return {icao: None for icao in seconds}
    return None


def replay(records_by_tile, predict=None, airports_known=False):
    """One row per build: ``tile, cold, airports, predicted, actual,
    steps {key: (predicted, actual)}``.  ``predict(step_key, features,
    same_tile_records, all_records, before)`` returns seconds.

    The vector step is told the airports it will solve
    (``airports_planned``) as a build knows them when it is PLANNED —
    the tile's previous solve list — or, with ``airports_known``, the
    list the build actually solved (what the session learns when the
    airports begin).  ``predict`` defaults to the model this tree
    carries (``tile_time_model.predict_for_replay``)."""
    if predict is None:
        from .tile_time_model import predict_for_replay as predict
    every = [(tile, r) for tile, rs in records_by_tile.items() for r in rs
             if isinstance(r, dict)]
    rows = []
    for build in _builds(records_by_tile):
        first_at = min(float(r.get("finished_at") or 0)
                       for r in build["records"])
        steps, feature_list, airports = {}, [], 0
        for record in build["records"]:
            # the history the estimate had when this build was planned
            before = [r for (_t, r) in every
                      if float(r.get("finished_at") or 0) < first_at]
            same = [r for (t, r) in every if t == build["tile"]
                    and float(r.get("finished_at") or 0) < first_at]
            features = _features(record)
            feature_list.append(features)
            features["textures_to_download"] = int(
                features.get("textures_downloaded") or 0)
            solved = features.pop("airport_seconds", None)
            planned = ({icao: None for icao in solved}
                       if airports_known and isinstance(solved, dict)
                       else _planned_airports(same))
            if planned is not None:
                features["airports_planned"] = planned
            airports = max(airports, int(features.get("airports") or 0))
            for key, actual in (record.get("step_seconds") or {}).items():
                if not isinstance(actual, (int, float)):
                    continue
                guess = predict(key, features, same, before, first_at)
                steps[key] = (float(guess or 0.0), float(actual))
        predicted = sum(p for p, _a in steps.values())
        actual = sum(a for _p, a in steps.values())
        rows.append({"tile": build["tile"], "finished_at": build["finished_at"],
                     "cold": _is_cold(feature_list), "airports": airports,
                     "predicted": predicted, "actual": actual,
                     "steps": steps})
    return rows


def _stats(ratios):
    """median and p90 of the ABSOLUTE error ``|log ratio|`` read back as a
    factor (1.0 = exact, 2.0 = off by 2x either way), and the median
    signed ratio (above 1 = over-estimate)."""
    ratios = [r for r in ratios if r and r > 0 and math.isfinite(r)]
    if not ratios:
        return {"n": 0}
    factors = sorted(math.exp(abs(math.log(r))) for r in ratios)
    p90 = factors[min(len(factors) - 1, int(math.ceil(0.9 * len(factors))) - 1)]
    return {"n": len(ratios), "median_factor": statistics.median(factors),
            "p90_factor": p90, "median_ratio": statistics.median(ratios)}


def summarise(rows, min_actual_s=1.0):
    """``{class: stats}`` for the tile totals by class, plus ``step:<key>``
    per-step rows.  A build or step under ``min_actual_s`` is noise."""
    classes = {}
    for row in rows:
        if row["actual"] < min_actual_s:
            continue
        ratio = _error_ratio(row["predicted"], row["actual"])
        cache = "cold" if row["cold"] else "cached"
        solve = "airports" if row["airports"] else "no-airports"
        for name in ("all", cache, solve, f"{cache}+{solve}"):
            classes.setdefault(name, []).append(ratio)
        for key, (p, a) in row["steps"].items():
            if a >= min_actual_s:
                classes.setdefault(f"step:{key}", []).append(_error_ratio(p, a))
    return {name: _stats(ratios) for name, ratios in classes.items()}
