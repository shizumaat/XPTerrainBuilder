"""THE FLAT-PACK WITNESS (owner direction 2026-10-20 17:44Z; answers
59-66, RULINGS 2026-10-20w-ad; spec ``docs/specs/flat-pack-terracing-spec.md`` §1) — did
the pack's author build for a FLAT airport?  A pure MEASUREMENT at load over
the pack partition (``Airport.partition``) and the DEM; PHASE 1 only
REPORTS it (``law/flat_pack.toml`` ``terrace = false``): nothing grades by
the verdict.

X-Plane draws an OBJ from its origin: the object's ``y = 0`` is the terrain
at its placement point, so a grounded foot is DRAWN at ``DEM(origin) +
AGL + y`` whatever the ground under the foot is.  Two witnesses:

* **seats** (RULINGS 2026-10-20x, "Greater than 90% of objects would all be at the
  same level"): per grounded OBJECT (a partition member with grounded
  feet) its drawn level is the median of its grounded feet's drawn
  heights; the LEVEL SHARE is the largest share of objects whose levels
  lie in ONE window ``flat_site.detector.seat_spread_max_m`` wide.  The
  witness holds when that share exceeds ``[detector] level_share_min``
  AND the ground under those objects has real relief — its ``p95 − p5``
  over their grounded feet exceeds the DEM source class's relief floor
  (``flat_site.detector.relief_floor_m``; a lidar or unknown class reads
  the fine floor).  Without the relief gate a pack on a genuinely flat
  site would read flat-assumed, and nothing about it would be wrong.
* **flatten_flag** (RULINGS 2026-10-20ac): the airport block's ``1302 flatten 1``
  (``SceneryPack.flatten_declared``) — the author asked X-Plane to
  flatten the airport.

A grounded foot is a non-scatter, non-line part's foot within
``[detector] grounded_band_m`` of the member's own ground read
(``base_profile['feet_y']``, else its lowest foot).  ``verdict`` =
``flat_assumed`` when either witness holds, ``no_data`` with fewer than
``[detector] min_members`` grounded objects and no flag, else
``follows_terrain``.  Terracing needs MORE than this verdict (RULINGS 2026-10-20w:
failure evidence — buildings that cannot be seated, steep paved grades);
that is phase 2's, not this module's.

Imports ``law`` and ``model`` only.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from ..law import Law
from ..law.inset_class import dem_source_class
from ..law.tables import flat_pack, flat_relief_floor_m, flat_site
from ..model.airport import Airport, FlatPackVerdict

__all__ = ["VERDICTS", "detect", "record", "log_line"]

FLAT_ASSUMED = "flat_assumed"
FOLLOWS_TERRAIN = "follows_terrain"
NO_DATA = "no_data"
VERDICTS = (FLAT_ASSUMED, FOLLOWS_TERRAIN, NO_DATA)

#: Percentiles of the relief measure (p95 − p5, the flat-site detector's).
_P_LO, _P_HI = 5.0, 95.0


def _sampler(airport: Airport) -> _t.Callable[[float, float], float | None]:
    """``(lat, lon) -> DEM z`` or ``None`` off the raster."""
    to_xy = airport.frame.transformers()[0]
    dem = airport.dem

    def z(lat: float, lon: float) -> float | None:
        x, y = to_xy(lon, lat)
        try:
            v = float(dem.z(x, y))
        except Exception:
            return None
        return v if math.isfinite(v) else None
    return z


def _grounded_feet(member, band_m: float) -> list[tuple[float, float, float]]:
    """The member's GROUNDED feet ``(lat, lon, y)`` (module docstring)."""
    feet = [f for pt in member.parts if not (pt.scatter or pt.line) for f in pt.feet]
    if not feet:
        return []
    low = min(f[2] for f in feet)
    fy = (member.base_profile or {}).get("feet_y")
    base = low if fy is None else float(fy)
    got = [f for f in feet if f[2] <= base + band_m]
    return got or [f for f in feet if f[2] <= low + band_m]


def _objects(airport: Airport, band_m: float) -> list[tuple[float, list[float]]]:
    """Per grounded object: ``(its drawn level, the DEM under its grounded
    feet)``."""
    z = _sampler(airport)
    out: list[tuple[float, list[float]]] = []
    for u in airport.partition.units:
        for m in u.members:
            if m.scatter or not m.parts:
                continue
            feet = _grounded_feet(m, band_m)
            origin = m.origin or u.anchor
            zo = z(*origin) if feet else None
            if zo is None:
                continue
            ground = [g for g in (z(la, lo) for la, lo, _y in feet) if g is not None]
            if not ground:
                continue
            seats = [zo + float(u.agl_m) + float(y) for _la, _lo, y in feet]
            out.append((float(np.median(seats)), ground))
    return out


def _level_window(levels: np.ndarray, width_m: float) -> tuple[int, int]:
    """``(start, stop)`` indices into SORTED ``levels`` of the window
    ``width_m`` wide holding the most objects (the first such)."""
    best, best_i, j = 0, 0, 0
    for i in range(len(levels)):
        while levels[i] - levels[j] > width_m:
            j += 1
        if i - j + 1 > best:
            best, best_i = i - j + 1, j
    return best_i, best_i + best


def _floor_m(airport: Airport, law: Law) -> tuple[float, str | None]:
    """The relief floor of the DEM's source class (fine for lidar or an
    unknown class) and the class."""
    klass, _pixel, _whence = dem_source_class(airport.dem, law)
    floor = flat_relief_floor_m(law, klass)
    return (flat_site(law).detector.relief_floor_m.fine if floor is None
            else float(floor)), klass


def detect(airport: Airport, law: Law) -> FlatPackVerdict:
    """The verdict for ``airport`` under ``law`` (module docstring)."""
    det = flat_pack(law).detector
    flag = bool(getattr(airport.pack, "flatten_declared", False))
    objs = (_objects(airport, det.grounded_band_m)
            if getattr(airport, "partition", None) is not None else [])
    signals: dict[str, _t.Any] = {"objects": len(objs), "flatten_flag": flag,
                                  "level_share_min": det.level_share_min}
    if len(objs) < det.min_members:
        verdict = FLAT_ASSUMED if flag else NO_DATA
        return FlatPackVerdict(verdict, "flatten_flag" if flag else "", None,
                               None, None, signals)
    order = sorted(range(len(objs)), key=lambda k: objs[k][0])
    levels = np.array([objs[k][0] for k in order])
    width = float(flat_site(law).detector.seat_spread_max_m)
    a, b = _level_window(levels, width)
    at = [objs[k] for k in order[a:b]]
    share = (b - a) / len(objs)
    level = float(np.median(levels[a:b]))
    ground = np.array([g for _lv, gs in at for g in gs])
    relief = float(np.percentile(ground, _P_HI) - np.percentile(ground, _P_LO))
    floor, klass = _floor_m(airport, law)
    miss = float(np.median([abs(lv - float(np.median(gs))) for lv, gs in at]))
    seats = bool(share > det.level_share_min and relief > floor)
    signals.update({"level_window_m": width, "level_objects": b - a,
                    "relief_floor_m": floor, "dem_class": klass,
                    "level_miss_p50_m": round(miss, 3),
                    "seats_witness": seats})
    witness = "+".join(w for w, on in (("seats", seats), ("flatten_flag", flag)) if on)
    return FlatPackVerdict(FLAT_ASSUMED if witness else FOLLOWS_TERRAIN, witness,
                           round(share, 4), round(level, 2), round(relief, 2), signals)


def record(v: FlatPackVerdict) -> dict:
    """``report.load.flat_pack``: the verdict and every signal, JSON-plain."""
    return {"verdict": v.verdict, "witness": v.witness,
            "level_share": v.level_share, "level_m": v.level_m,
            "relief_m": v.relief_m, "signals": dict(v.signals)}


def log_line(icao: str, v: FlatPackVerdict) -> str:
    """The one ``[flat-pack]`` line per airport."""
    s = v.signals

    def num(x, unit: str = " m") -> str:
        return "?" if x is None else f"{float(x):.2f}{unit}"
    return (f"[flat-pack] {icao}: {v.verdict}"
            + (f" ({v.witness})" if v.witness else "")
            + f" — {s.get('level_objects', 0)} of {s.get('objects', 0)} objects at one "
            f"level {num(v.level_m)} (share {num(v.level_share, '')}, need > "
            f"{num(s.get('level_share_min'), '')}), ground relief under them "
            f"{num(v.relief_m)} vs floor {num(s.get('relief_floor_m'))} "
            f"[{s.get('dem_class') or '?'}]; flatten flag "
            f"{'yes' if s.get('flatten_flag') else 'no'}  (report only)")
