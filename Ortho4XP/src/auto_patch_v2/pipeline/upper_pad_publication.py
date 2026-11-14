"""THE ``upper_pads`` SIDECAR KEY AND THE RIM'S DECLARED STEP (#2068, RULINGS
2026-11-13aa (1); spec ``docs/specs/2068-upper-pad-spec.md`` §2 sidecar,
amendment A1 (2) (c)).

An upper pad's level (``planar/group_up``: the pad under a unit's upper
storey, held at its block's datum + the storey) is climbed to by a road
arm at the cap; where the arm arrives under the level, the step at the
level's RIM (``airport/road_ramp.road_terrace``'s ``rim``) is a DECLARED
terrace joint — :func:`upper_rim_joints` publishes every run of rim
vertices stepping more than ``[cockpit] visual_m`` from the arm beside them
through the ``wall_terrace`` channel (``publication.wall_terrace_joints``),
so the census forgives exactly that step.  :func:`upper_pad_records` is the
REPORT key the drawn check and the master read: one record per level with
its solved height and those runs (no census family prices it)."""
from __future__ import annotations

import math
import statistics as _st
import typing as _t

__all__ = ["upper_pad_records", "upper_rim_joints"]

#: the patch writes elevations to the centimetre (``publication._EMIT_Z_ROUND_M``)
_ROUND_M = 0.01


def _levels(planar) -> dict[str, dict]:
    from ..model.registries import GROUP_UP
    lands = getattr(getattr(planar, "registries", None), "landings", None) or {}
    return {r: rec for r, rec in lands.items() if rec.get("witness") == GROUP_UP}


def _rim_steps(planar, levels, z) -> dict[int, tuple[float, int]]:
    """``{rim vertex: (its step to the nearest arm vertex beside it, that
    vertex)}`` — the arm's vertices being the road faces' vertices off the
    level."""
    rim = (getattr(planar, "road_terrace", None) or {}).get("rim") or {}
    out: dict[int, tuple[float, int]] = {}
    for v in rim:
        vx, vy = planar.vertices[v].xy
        best = None
        for fid in planar.vertices[v].incident_faces:
            f = planar.faces[fid]
            if str(f.ref) in levels or "road" not in str(f.role):
                continue
            for cyc in (f.ring, *f.holes):
                for w in planar.ring_vertices(cyc):
                    if w in rim or w == v:
                        continue
                    d = math.hypot(planar.vertices[w].xy[0] - vx, planar.vertices[w].xy[1] - vy)
                    if best is None or d < best[0]:
                        best = (d, w)
        if best is not None:
            out[v] = (float(z[v]) - float(z[best[1]]), best[1])
    return out


def _rim_runs(planar, ref: str, steps, vis: float) -> list[list[int]]:
    """The runs of consecutive rim vertices (along the level's own rings)
    whose step exceeds ``vis``."""
    runs: list[list[int]] = []
    for f in planar.faces.values():
        if str(f.ref) != ref:
            continue
        for cyc in (f.ring, *f.holes):
            vs = list(planar.ring_vertices(cyc))
            cur: list[int] = []
            for v in vs + vs[:1]:
                if v in steps and abs(steps[v][0]) > vis:
                    if not cur or cur[-1] != v:
                        cur.append(v)
                    continue
                if cur:
                    runs.append(cur)
                cur = []
            if cur:
                runs.append(cur)
    return runs


def _to_ll(planar):
    from .ribbon_steps import _to_ll as f
    return f(planar)


def upper_rim_joints(planar, law, z: "_t.Sequence[float] | None") -> list[dict[str, _t.Any]]:
    """One ``wall_terrace`` joint per rim run (module docstring): the run's
    points, ``step_m`` / ``height_m`` the largest step over it plus the
    emit's rounding."""
    levels = _levels(planar)
    if not levels or z is None:
        return []
    vis = float(law.tables.emit.cockpit.visual_m)
    steps = _rim_steps(planar, levels, z)
    to_ll = _to_ll(planar)
    out = []
    for ref in sorted(levels):
        for run in _rim_runs(planar, ref, steps, vis):
            h = max(abs(steps[v][0]) for v in run)
            pts = [list(to_ll(*planar.vertices[v].xy)) for v in run]
            if len(pts) == 1:
                pts = pts * 2
            out.append({"points": pts, "step_m": round(h + _ROUND_M, 4),
                        "declared_step_m": round(h + _ROUND_M, 4), "faced": False,
                        "kind": "wall_terrace", "faces": [], "shapes": [f"upper_rim:{ref}"],
                        "gap": False, "roles": [], "pairs": len(run),
                        "length_m": round(sum(math.dist(planar.vertices[a].xy,
                                                        planar.vertices[b].xy)
                                              for a, b in zip(run, run[1:])), 2),
                        "height_m": round(h, 3), "lots": 0})
    return out


def upper_pad_records(planar, law, z: "_t.Sequence[float] | None") -> list[dict[str, _t.Any]]:
    """The ``upper_pads`` records (module docstring)."""
    levels = _levels(planar)
    if not levels:
        return []
    vis = float(law.tables.emit.cockpit.visual_m)
    steps = _rim_steps(planar, levels, z) if z is not None else {}
    to_ll = _to_ll(planar)
    out = []
    for ref, rec in sorted(levels.items()):
        vs = sorted({v for f in planar.faces.values() if str(f.ref) == ref
                     for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)})
        lz = round(float(_st.median(float(z[v]) for v in vs)), 3) if z is not None and vs else None
        runs = _rim_runs(planar, ref, steps, vis) if steps else []
        out.append({"level": ref, "pad": rec.get("pad"), "block": rec.get("block"),
                    "y": rec.get("y"), "level_z": lz, "arms": list(rec.get("arms", ())),
                    "rim": [{"ll": [list(to_ll(*planar.vertices[v].xy)) for v in r],
                             "height_m": round(max(abs(steps[v][0]) for v in r), 3)}
                            for r in runs],
                    "rim_max_step_m": round(max((abs(s) for s, _w in steps.values()),
                                                default=0.0), 3)})
    return out
