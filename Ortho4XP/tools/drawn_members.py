"""THE DRAWN GATE'S MEMBER ROWS (spec ``object-gate-member-floors-20261113.md``
§3, §5.3, §6; #1903 / #1918): what ``tools/drawn_check.py`` reads of a
FRAME'S MEMBERS, a LEVEL FLOOR and a rigid frame's MISFIT -- beside its site
rows, from the same written rows (``drawn_check.Drawn``) over the same mesh
(the drawn tile, or the predicted patch ``patch_faces.PatchAtlas``).

* THE FOOT BAR (:func:`foot_verdict`): a frame member's foot -- the median
  height over the mesh of its vertices standing within
  ``drawn_site_bars.FOOT_BAND_M`` of its lowest near the site -- never
  floats more than ``tol``; one buried more than the ground bar
  (``drawn_site.GROUND_BAR_M``) is listed BURIED, never failed (owner Q4,
  :data:`BURIED_FOOT_PASSES`): a wall has no clearance (RULINGS 2026-11-06d
  (4) "If there's no floor then just to the wall depth is good").
* FEET (:func:`check_feet`): one row per channel record carrying
  ``member_feet``: each published foot (authored y on its member) placed on
  its WRITTEN row's zero, against the mesh at the foot.  FAIL when a
  ``floor`` or ``ledge`` foot floats more than ``tol``; ``end`` / ``unmet``
  feet and buried feet are counted and listed.
* THE FLOOR BAR (:func:`check_level_floor`): a sunken road's LEVEL FLOOR
  under a mound (``level_floor``): the plate (the written row's zero plus
  ``plate_y_m``) sampled along its axis every 10 m and across it; FAIL when
  the mesh stands more than ``tol`` over the plate anywhere (the ground
  through the floor) or the plate's median height over the mesh exceeds the
  ground bar (the floor floats).  No skirt, no relief bar.
* FRAME (:func:`frame_rows`): a hidden shell's rim against the ground
  (``object_floors[].rim_misfit_m``), printed, never failed.
"""
from __future__ import annotations

import math
import os
import sys

import numpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drawn_site import GROUND_BAR_M  # noqa: E402
from drawn_site_bars import FOOT_BAND_M  # noqa: E402

__all__ = ["BURIED_FOOT_PASSES", "FRAME_MEMBER", "foot_verdict", "check_feet",
           "check_level_floor", "level_row", "frame_rows", "written_zeros", "GROUND_BAR_M",
           "FOOT_BAND_M"]

M_PER_DEG = 111320.0
#: the claim kind of a member of an object floor's frame that owns no ground
FRAME_MEMBER = "frame_member"
#: OWNER Q4 (spec §9, RULINGS 2026-11-13q (4) "Yes"): a member's foot
#: buried more than the ground bar passes (listed BURIED); ``False`` fails it
BURIED_FOOT_PASSES = True
#: the FLOOR bar's stations along a level floor's axis
LEVEL_STEP_M = 10.0
#: ...and across it (fractions of ``width_m``); the outermost stand this far
#: inside the plate's edge (its rim is the wall's, not the floor's)
LEVEL_ACROSS = (0.0, 0.25, -0.25, 0.5, -0.5)
LEVEL_EDGE_M = 1.0


def foot_verdict(gap: float, tol: float) -> "tuple[str, str | None]":
    """``(state, fail)`` of one member foot ``gap`` metres over the mesh:
    FLOAT (fails), BURIED (listed; fails only with
    :data:`BURIED_FOOT_PASSES` off) or ON."""
    if math.isnan(gap):
        return "NO MESH", None
    if gap > tol:
        return "FLOAT", f"foot floats {gap:+.2f} > {tol}"
    if gap < -GROUND_BAR_M:
        return "BURIED", (None if BURIED_FOOT_PASSES
                          else f"foot buried {gap:+.2f} < -{GROUND_BAR_M}")
    return "ON", None


def written_zeros(drawn, pristine: dict, tile: str, stem) -> dict:
    """``{"dsf:objN": drawn zero}``: each pristine placement's WRITTEN row
    (the row of its stem whose anchor stands nearest the pristine anchor)
    placed as X-Plane places it (``drawn_check._base``)."""
    from drawn_check import _base
    by_stem: dict = {}
    for i, p in enumerate(drawn.rows):
        by_stem.setdefault(stem(p.def_path), []).append(i)
    cache: dict = {}

    def zero(pid: str):
        if pid in cache:
            return cache[pid]
        out = None
        try:
            i = int(pid.split("obj", 1)[1].split("@")[0])
            t = pid.split("@", 1)[1] if "@" in pid else tile
            pp = pristine[t].placements[i]
        except (IndexError, KeyError, ValueError, AttributeError):
            pp = None
        if pp is not None:
            rows = by_stem.get(stem(pp.def_path), [])
            if rows:
                kx = M_PER_DEG * math.cos(math.radians(pp.lat))
                j = min(rows, key=lambda r: math.hypot((drawn.rows[r].lon - pp.lon) * kx,
                                                       (drawn.rows[r].lat - pp.lat) * M_PER_DEG))
                out = _base(drawn, j)
        cache[pid] = out
        return out
    return zero


def check_feet(rec: dict, drawn, zero, tol: float) -> dict:
    """One channel record's FEET row (module doc); ``zero(pid)`` the written
    row's drawn zero (:func:`written_zeros`)."""
    from drawn_check import mesh_z
    row = {"site": f"FEET {rec['id']}", "role": "FEET", "fails": [], "objects": [],
           "relief": None, "lowest_any": None, "counts": {}, "groups": {}, "floating": [],
           "buried": 0, "no_row": 0}
    worst, at = -math.inf, None
    for la, lo, y, pid, kind in rec["member_feet"]:
        row["counts"][kind] = row["counts"].get(kind, 0) + 1
        z0 = zero(pid)
        if z0 is None:
            row["no_row"] += 1
            continue
        gap = z0 + float(y) - mesh_z(drawn.mesh, lo, la)
        if math.isnan(gap):
            continue
        g = row["groups"].setdefault(f"{pid} {kind}", [])
        g.append(round(gap, 2))
        if gap < -GROUND_BAR_M:
            row["buried"] += 1
        if kind in ("floor", "ledge"):
            if gap > worst:
                worst, at = gap, (la, lo)
            if gap > tol:
                row["floating"].append([round(la, 7), round(lo, 7), pid, kind, round(gap, 2)])
    first = rec["member_feet"][0] if rec["member_feet"] else (0.0, 0.0)
    row["lat"], row["lon"] = (round(v, 6) for v in (at or first[:2]))
    row["delta"] = round(worst, 2) if math.isfinite(worst) else None
    row["groups"] = {k: {"n": len(v), "float": sum(g > tol for g in v),
                         "p95": round(float(numpy.percentile(v, 95)), 2),
                         "worst": max(v)} for k, v in sorted(row["groups"].items())}
    if row["floating"]:
        row["fails"].append(f"{len(row['floating'])} floor/ledge feet float > {tol} "
                            f"(worst {row['delta']:+.2f})")
    row["verdict"] = "FAIL" if row["fails"] else "PASS"
    return row


def check_level_floor(rec: dict, drawn, zero, tol: float) -> dict:
    """The FLOOR bar of one ``level_floor`` record (module doc):
    ``{"plate", "over_max", "over_at", "float_median", "fails"}``."""
    from drawn_check import mesh_z
    z0 = zero(rec["objects"][0]) if rec.get("objects") else None
    out = {"fails": [], "plate": None}
    if z0 is None:
        out["fails"].append("the level floor's row is not drawn")
        return out
    plate = z0 + float(rec.get("plate_y_m", 0.0))
    if math.isnan(plate):
        out["fails"].append("the level floor's row stands on no read mesh (its zero is nan)")
        return out
    out["plate"] = round(plate, 2)
    ax = rec["axis_ll"]
    lat0 = ax[0][0]
    kx = M_PER_DEG * math.cos(math.radians(lat0))
    xy = [((lo - ax[0][1]) * kx, (la - lat0) * M_PER_DEG) for la, lo in ax]
    half = max(0.0, 0.5 * float(rec.get("width_m", 0.0)) - LEVEL_EDGE_M)
    over, d = [], []
    for (ax_, ay), (bx, by) in zip(xy, xy[1:], strict=False):
        seg = math.hypot(bx - ax_, by - ay)
        if seg < 1e-6:
            continue
        ux, uy = (bx - ax_) / seg, (by - ay) / seg
        for t in numpy.arange(0.0, seg, LEVEL_STEP_M):
            for f in LEVEL_ACROSS:
                o = 2.0 * f * half
                x, y = ax_ + ux * t - uy * o, ay + uy * t + ux * o
                la, lo = lat0 + y / M_PER_DEG, ax[0][1] + x / kx
                m = mesh_z(drawn.mesh, lo, la)
                if not math.isnan(m):
                    over.append((m - plate, la, lo))
                    d.append(plate - m)
    if not over:
        out["fails"].append("no mesh read over the level floor")
        return out
    worst = max(over)
    out["over_max"], out["over_at"] = round(float(worst[0]), 2), [round(float(worst[1]), 7),
                                                                round(float(worst[2]), 7)]
    out["float_median"] = round(float(numpy.median(d)), 2)
    out["samples"] = len(over)
    if worst[0] > tol:
        out["fails"].append(f"FLOOR the ground stands {worst[0]:+.2f} over the level floor "
                            f"{plate:.2f} at {out['over_at']} (bar {tol})")
    if out["float_median"] > GROUND_BAR_M:
        out["fails"].append(f"FLOOR the level floor floats {out['float_median']:+.2f} over "
                            f"the mesh (median; bar {GROUND_BAR_M})")
    return out


def level_row(rec: dict, drawn, zero, tol: float) -> dict:
    """One ``LEVEL <id>`` row per level floor: :func:`check_level_floor` at
    the plate's mid-axis (its vertices may stand nowhere near a cut site)."""
    bar = check_level_floor(rec, drawn, zero, tol)
    ax = rec["axis_ll"]
    mid = ax[len(ax) // 2]
    return {"site": f"LEVEL {rec['id']}", "role": "LEVEL", "lat": round(mid[0], 6),
            "lon": round(mid[1], 6), "level": {rec["id"]: bar}, "fails": list(bar["fails"]),
            "objects": [], "relief": None, "lowest_any": None, "delta": bar.get("over_max"),
            "verdict": "FAIL" if bar["fails"] else "PASS"}


def frame_rows(sidecar: dict, anchor_of) -> list[dict]:
    """One FRAME row per object floor publishing ``rim_misfit_m`` (spec §6;
    never failed); ``anchor_of(pid)`` the (lat, lon) of its row or None."""
    out = []
    for r in sidecar.get("object_floors", []):
        m = r.get("rim_misfit_m")
        if not m:
            continue
        ll = anchor_of(r.get("object") or (r.get("objects") or [""])[0]) or (0.0, 0.0)
        out.append({"site": f"FRAME {r['id']}", "role": "FRAME", "lat": round(ll[0], 6),
                    "lon": round(ll[1], 6), "misfit": m, "off_share": r.get("rim_off_share"),
                    "hidden": r.get("hidden"), "fails": [], "objects": [], "relief": None,
                    "lowest_any": None, "verdict": "-"})
    return out
