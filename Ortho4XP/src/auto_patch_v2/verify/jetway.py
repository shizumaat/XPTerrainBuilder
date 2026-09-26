"""THE JETWAY STRIP, read off the emitted product (owner RULINGS
2026-09-18t Q3: "UNDER THE JETWAYS THE APRON STRIP IS LEVEL WITH THE
TERMINAL"; jetway-strip spec §2 (6)).

The v2 twin of ``check_grade._check_jetway_strip``: the strips arrive
through the sidecar's ``jetway_strips`` (``pipeline/publication``), each
carrying its ONE level, its vertices by the canonical identity and the
clamps the projection (``solve/project_strip``) reported.  Rows:

  (a) a strip vertex off its level by more than §31's visual floor;
  (c) every reported clamp, carrying its metres.

(b), a transition pair over the apron ``max``, is ``within_shape``'s own
apron pair (the transition changes no role and no cap).
"""
from __future__ import annotations

from .frame import Patch, Row, row

__all__ = ["jetway_strip", "FAMILY", "TOL_M"]

FAMILY = "jetway_strip"

#: spec §5: the materiality — §31's visual floor
TOL_M = 0.05

_DP = 7


def jetway_strip(p: Patch) -> list[Row]:
    """One row per strip vertex off its level, and one per clamp."""
    strips = p.publication.get("jetway_strips") or ()
    if not strips:
        return []
    by_ll: dict[tuple[float, float], int] = {
        (round(la, _DP), round(lo, _DP)): vid for vid, (la, lo) in p.ll.items()}
    out: list[Row] = []
    for rec in strips:
        ref = f"jetway_strip:{rec.get('pad_ref', '')}"
        lvl = rec.get("level")
        if lvl is not None:
            for ll in (rec.get("vertices_ll") or ()):
                try:
                    lat, lon = float(ll[0]), float(ll[1])
                except (TypeError, ValueError, IndexError):
                    continue
                vid = by_ll.get((round(lat, _DP), round(lon, _DP)))
                if vid is None:
                    continue
                z = p.z.get(vid)
                if z is None or abs(z - float(lvl)) <= TOL_M:
                    continue
                xy = p.xy.get(vid, (0.0, 0.0))
                out.append(row(FAMILY, ("apron",) * 2, "airside",
                               abs(z - float(lvl)), 0.0, 0.0, 0.0, xy, xy,
                               ref, None, lat=lat, lon=lon))
        for c in (rec.get("clamps") or ()):
            try:
                lat, lon, m = float(c[0]), float(c[1]), float(c[3])
            except (TypeError, ValueError, IndexError):
                continue
            vid = by_ll.get((round(lat, _DP), round(lon, _DP)))
            xy = p.xy.get(vid, (0.0, 0.0)) if vid is not None else (0.0, 0.0)
            out.append(row(FAMILY, ("apron",) * 2, "airside", abs(m), 0.0,
                           0.0, 0.0, xy, xy, f"{ref}:clamp:{c[2]}", None,
                           lat=lat, lon=lon))
    return out
