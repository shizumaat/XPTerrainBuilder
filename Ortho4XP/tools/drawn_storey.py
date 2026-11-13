"""THE STOREY-SHELL LAYER of the drawn check (#2062, RULINGS 2026-11-13w;
spec ``2062-storey-shell-spec`` §3 R1 step 5, bar B5): at every run of a
split-level building's outline, does the drawn ground stand at the
building's zero plus that run's foot?

Reads the sidecar's ``storey_shells`` records (``pipeline/
storey_publication``) and a drawn surface (the tile mesh, or the emitted
patch's faces under ``--predict``).  The ZERO is the building's written
rows' drawn zero (each row's own lift taken off) where they are read, else
the record's solved ``zero``.  Each run with a foot is judged at stations
``OUT_M`` outside it (on its LEFT: a run has its building on its right):
``drawn - (zero + foot)`` within ``AIRSIDE_TOL_M`` on a run facing the
airside, ``GROUNDSIDE_TOL_M`` on the groundside, and no station of any run
with the ground under the foot by more than the run's bar (an open side
showing).  MINOR runs (their foot's level did not count, spec A1 (2)) are
listed with their numbers and never judged.
"""
from __future__ import annotations

import math
import statistics as _st
import typing as _t

__all__ = ["AIRSIDE_TOL_M", "GROUNDSIDE_TOL_M", "OUT_M", "check", "print_row"]

#: the bars (spec §4 B5) and the stations' reach outside a run
AIRSIDE_TOL_M = 0.05
GROUNDSIDE_TOL_M = 0.5
OUT_M = 1.0
_STATIONS = 5


def _outside(seg, out_m: float, n: int) -> list[tuple[float, float]]:
    """``n`` (lon, lat) stations ``out_m`` to the LEFT of the (lat, lon)
    segment ``seg`` (``drawn_check._outside``'s frame)."""
    from drawn_check import _outside as outside
    return outside(seg, None, out_m, n)


def check(rec: _t.Mapping, mesh, zero: "float | None" = None,
          zeros: _t.Sequence[float] = ()) -> dict:
    """One storey shell's row (module docstring).  ``zero`` the drawn
    zero of its written rows (``zeros`` each row's), else the record's."""
    from drawn_check import mesh_z
    lon, lat = rec["anchor_longitude_latitude"]
    z0 = float(zero) if zero is not None else rec.get("zero")
    out = {"site": f"storey_shell {rec['pad_ref']}", "lat": round(lat, 6),
           "lon": round(lon, 6), "role": "STOREY", "resources": list(rec.get("resources", [])),
           "zero": None if z0 is None else round(z0, 3), "zero_from": (
               "rows" if zero is not None else "sidecar"),
           "sidecar_zero": rec.get("zero"), "levels": rec.get("levels"),
           "zero_spread": round(max(zeros) - min(zeros), 3) if zeros else None,
           "runs": [], "minor": [], "fails": []}
    if z0 is None:
        out["fails"].append("no zero (no written row and no solved block)")
        out["verdict"] = "FAIL"
        return out
    worst_air = worst_gnd = 0.0
    under = 0
    for i, r in enumerate(rec.get("runs", [])):
        if r.get("foot") is None:
            continue
        g = [mesh_z(mesh, x, y) for x, y in _outside(r["ll"], OUT_M, _STATIONS)]
        g = [v for v in g if not math.isnan(v)]
        if not g:
            continue
        d = [v - (z0 + float(r["foot"])) for v in g]
        row = {"run": i, "foot": r["foot"], "airside": bool(r.get("airside")),
               "worst": round(max(d, key=abs), 3), "lowest": round(min(d), 3),
               "median": round(_st.median(d), 3), "ll": r["ll"][0]}
        if r.get("minor"):
            out["minor"].append(row)
            continue
        out["runs"].append(row)
        tol = AIRSIDE_TOL_M if row["airside"] else GROUNDSIDE_TOL_M
        if row["airside"]:
            worst_air = max(worst_air, abs(row["worst"]))
        else:
            worst_gnd = max(worst_gnd, abs(row["worst"]))
        if abs(row["worst"]) > tol:
            out["fails"].append(f"run {i} ({'airside' if row['airside'] else 'groundside'}, "
                                f"foot {r['foot']:+.2f}) drawn - (zero + foot) "
                                f"{row['worst']:+.2f} > {tol}")
        under += row["lowest"] < -tol
    out.update({"airside_worst": round(worst_air, 3), "groundside_worst": round(worst_gnd, 3),
                "runs_under_foot": under, "delta": round(max(worst_air, worst_gnd), 3)})
    if zeros and out["zero_spread"] > AIRSIDE_TOL_M:
        out["fails"].append(f"rows seated {out['zero_spread']:.3f} m apart")
    out["verdict"] = "FAIL" if out["fails"] else "PASS"
    return out


def print_row(r: _t.Mapping) -> None:
    """The report lines of one storey row."""
    print(f"{r['verdict']:4s} {r['site']} @{r['lat']},{r['lon']} zero {r['zero']} "
          f"({r['zero_from']}; sidecar {r['sidecar_zero']}) levels {r['levels']}: runs "
          f"airside worst {r.get('airside_worst')} groundside worst "
          f"{r.get('groundside_worst')}, {r.get('runs_under_foot')} under the foot; "
          f"{len(r['minor'])} minor")
    for m in r["minor"]:
        print(f"       minor run {m['run']} foot {m['foot']:+.2f}: drawn - (zero + foot) "
              f"{m['worst']:+.2f} (lowest {m['lowest']:+.2f})")
    for f in r["fails"]:
        print(f"       FAIL {f}")
