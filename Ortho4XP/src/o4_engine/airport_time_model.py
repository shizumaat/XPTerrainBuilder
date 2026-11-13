"""How long ONE airport's patch solve takes, before it runs (#2045).

The tile progress bar and the time estimates price the vector step as its
OSM overhead plus the airports it solves.  An airport solve is the
dominant cost of a cached tile (``+39-105`` on 2026-11-13: KDEN 1,340 s of
a 1,837 s build), so pricing the step as "the vector step's median" left
the bar still for most of the build.  One airport is priced from, in
order:

1. its OWN recorded solves, the median of the newest
   :data:`OWN_WINDOW` — the per-airport store
   ``~/.ortho4xp/auto_patch_build_times/<ICAO>.json`` (the store the
   harness's ``check_build_time.py`` writes v2 stage clocks into; the
   session appends one ``"source": "app"`` record per solved airport,
   :func:`record`) and the per-airport seconds the tile store carries
   (``features.airport_seconds``).  v1 records (no ``engine`` key) are a
   retired engine and never count;
2. its SIZE — the square root of its extent's area in km² from the
   engine's airport index (``O4_Airport_Index``), times a rate learned
   over every recorded solve with a size;
3. :data:`DEFAULT_SECONDS`.

Measured over the owner's 1,296 logged solves (World pack
``build_logs``, 2026-11-13; ``Auto-patch: X took Ns``), replayed in order:
an airport's own last three solves predict the next within 1.36x (median;
p90 2.2x); the size rule within 1.72x (p90 4.0x) — runway count 1.85x
(6.0x), a constant 2.68x (6.5x).  Size is a weak witness (the scenery
pack's object count dominates: KDEN's custom pack solves 1,340 s on a
10 km field); history wins whenever it exists.

Airports solve in parallel workers, so a tile's airport WALL time is the
longest of its airports, not their sum (:func:`wall_seconds`).  Advisory
only: every function swallows its errors.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import time

__all__ = ["STORE_DIRECTORY", "record", "predict_each",
           "wall_seconds", "size_km"]

STORE_DIRECTORY = os.path.join(
    os.path.expanduser("~"), ".ortho4xp", "auto_patch_build_times")

#: Records kept per airport (newest last); the same window as a tile's.
RECORDS_KEPT = 8
#: Solves of the airport's own history the estimate is the median of.
OWN_WINDOW = 3
#: Seconds per km of airport size before any sized solve is recorded:
#: the median over the owner's logged solves.
DEFAULT_SIZE_RATE = 44.5
#: An airport with no history and no known size.
DEFAULT_SECONDS = 120.0

#: The airport index file; None = the data folder's
#: (``O4_File_Names.airport_index_cache``).  Tests and the replay set it.
INDEX_PATH = None

_INDEX: dict = {}


def _finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value) \
        and value > 0


def size_km(icao, index_path=None):
    """The airport's size: sqrt of its extent's area (km²) in the airport
    index, or None (no index, no extent).  The index is read once per
    file stamp."""
    try:
        index_path = index_path or INDEX_PATH
        if index_path is None:
            import O4_File_Names as FNAMES
            index_path = FNAMES.airport_index_cache()
        stamp = (index_path, os.path.getmtime(index_path))
        if _INDEX.get("stamp") != stamp:
            import O4_Airport_Index as AIRPORT_INDEX
            sizes = {}
            for entry in AIRPORT_INDEX.load_index(index_path):
                if entry.extent:
                    (s, w, n, e) = entry.extent
                    area = ((n - s) * 111.0) * ((e - w) * 111.0
                                                * math.cos(math.radians(entry.lat)))
                    sizes[entry.code] = math.sqrt(max(area, 0.01))
            _INDEX.clear()
            _INDEX.update(stamp=stamp, sizes=sizes)
        return _INDEX["sizes"].get(str(icao).upper())
    except Exception:
        return None


def _path(icao, store):
    return os.path.join(store or STORE_DIRECTORY, f"{str(icao).upper()}.json")


def _load(icao, store=None):
    try:
        with open(_path(icao, store), encoding="utf-8") as f:
            records = json.load(f)
        return [r for r in records if isinstance(r, dict)] \
            if isinstance(records, list) else []
    except Exception:
        return []


def record(icao, seconds, size=None, store=None, now=None):
    """Append one solved airport's wall seconds (atomic write, newest
    :data:`RECORDS_KEPT` kept).  Never raises."""
    try:
        if not icao or not _finite(seconds):
            return
        entry = {"finished_at": float(now if now is not None else time.time()),
                 "engine": "v2", "source": "app", "phase_seconds": {},
                 "total_seconds": round(float(seconds), 2)}
        if _finite(size):
            entry["features"] = {"size_km": round(float(size), 3)}
        records = (_load(icao, store) + [entry])[-RECORDS_KEPT:]
        os.makedirs(store or STORE_DIRECTORY, exist_ok=True)
        path = _path(icao, store)
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as f:
            json.dump(records, f, indent=1)
        os.replace(path + ".tmp", path)
    except Exception:
        pass


def _own_samples(icao, tile_records, store, before):
    """``[(finished_at, seconds)]`` of this airport's v2 solves, oldest
    first."""
    out = []
    for r in _load(icao, store):
        at = float(r.get("finished_at") or 0)
        if r.get("engine") == "v2" and _finite(r.get("total_seconds")) \
                and (before is None or at < before):
            out.append((at, float(r["total_seconds"])))
    for r in tile_records or ():
        seconds = ((r.get("features") or {}).get("airport_seconds")
                   or {}).get(str(icao).upper())
        at = float(r.get("finished_at") or 0)
        if _finite(seconds) and (before is None or at < before):
            out.append((at, float(seconds)))
    return sorted(out)


def _size_rate(store=None, before=None):
    """Median seconds per km of size over every recorded solve with a
    size, else :data:`DEFAULT_SIZE_RATE`."""
    rates = []
    try:
        names = os.listdir(store or STORE_DIRECTORY)
    except Exception:
        names = []
    for name in names:
        if not name.endswith(".json"):
            continue
        for r in _load(name[:-5], store):
            size = (r.get("features") or {}).get("size_km")
            if (r.get("engine") == "v2" and _finite(size)
                    and _finite(r.get("total_seconds"))
                    and (before is None
                         or float(r.get("finished_at") or 0) < before)):
                rates.append(float(r["total_seconds"]) / float(size))
    return statistics.median(rates) if rates else DEFAULT_SIZE_RATE


def _predict(icao, size=None, tile_records=(), store=None, before=None,
            rate=None):
    """One airport's predicted solve seconds (the module docstring's
    order).  ``before`` limits the history to records finished before it
    (the estimate-error replay); ``rate`` is a precomputed size rate."""
    try:
        own = _own_samples(icao, tile_records, store, before)
        if own:
            return float(statistics.median(
                [s for _at, s in own[-OWN_WINDOW:]]))
        if _finite(size):
            if rate is None:
                rate = _size_rate(store, before)
            return float(rate) * float(size)
    except Exception:
        pass
    return DEFAULT_SECONDS


def wall_seconds(airports, tile_records=(), store=None, before=None):
    """The tile's airport WALL seconds: the longest of its airports
    (they solve in parallel workers).  ``airports`` maps ICAO -> size
    (km, or None: looked up in the airport index).  0.0 for none."""
    airports = {icao: (size if _finite(size) else size_km(icao))
                for icao, size in dict(airports or {}).items()}
    if not airports:
        return 0.0
    rate = _size_rate(store, before) \
        if any(_finite(s) for s in airports.values()) else None
    return max(_predict(icao, size, tile_records, store, before, rate)
               for icao, size in airports.items())


def predict_each(airports, tile_records=(), store=None):
    """``{icao: seconds}`` for each airport (the session's per-airport
    shares of the vector step)."""
    sizes = {icao: size_km(icao) for icao in airports or ()}
    rate = _size_rate(store) if any(_finite(s) for s in sizes.values()) \
        else None
    return {icao: _predict(icao, size, tile_records, store, None, rate)
            for icao, size in sizes.items()}
