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
its solved height and those runs (no census family prices it), and the
fence yard beside it (spec 2068 A2 F5: ``classify/fence_yard``).

THE YARD'S EDGE (spec 2068 A2 F5): every run of a yard's boundary vertices
stepping more than ``visual_m`` to the nearest vertex of another face
across the stand-off (the census's horizon, ``groundside_cutback_m`` +
``weld_spacing_m`` + the snap margin) is a declared ``wall_terrace`` joint
too (:func:`yard_edge_joints`)."""
from __future__ import annotations

import math
import statistics as _st
import typing as _t

__all__ = ["upper_pad_records", "upper_rim_joints", "yard_edge_joints"]

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
        if str(f.ref) == ref:
            runs.extend(_ring_runs(planar, f, lambda v: v in steps and abs(steps[v][0]) > vis))
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
                                                default=0.0), 3),
                    "yard": _yard_record(planar, law, ref, rec, z)})
    return out


def _yard_faces(planar) -> list:
    from ..model.planar import fence_yard_pad
    return [f for f in planar.faces.values() if fence_yard_pad(f.ref) is not None]


def _yard_steps(planar, law, yards, z) -> dict[int, float]:
    """``{yard boundary vertex: its step to the nearest vertex of another
    face within the stand-off horizon}``."""
    from ..law.tables import snap_margin_m
    horizon = float(law.tables.zones.adjacent_ground.groundside_cutback_m) \
        + float(law.tables.emit.identity.weld_spacing_m) + snap_margin_m(law)
    yard_ids = {f.id for f in yards}
    yard_vs = {v for f in yards for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)}
    other = sorted({v for f in planar.faces.values() if f.id not in yard_ids
                    for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)}
                   - yard_vs)
    if not other:
        return {}
    import numpy as np
    from scipy.spatial import cKDTree
    tree = cKDTree(np.array([planar.vertices[w].xy for w in other], dtype=float))
    out: dict[int, float] = {}
    for v in sorted(yard_vs):
        d, i = tree.query(planar.vertices[v].xy, distance_upper_bound=horizon)
        if math.isfinite(d):
            out[v] = float(z[v]) - float(z[other[int(i)]])
    return out


def yard_edge_joints(planar, law, z: "_t.Sequence[float] | None") -> list[dict[str, _t.Any]]:
    """One ``wall_terrace`` joint per run of yard edge stepping over
    ``visual_m`` across its stand-off (module docstring)."""
    yards = _yard_faces(planar)
    if not yards or z is None:
        return []
    vis = float(law.tables.emit.cockpit.visual_m)
    steps = _yard_steps(planar, law, yards, z)
    to_ll = _to_ll(planar)
    out = []
    for f in sorted(yards, key=lambda f: f.id):
        for run in _ring_runs(planar, f, lambda v: v in steps and abs(steps[v]) > vis):
            h = max(abs(steps[v]) for v in run)
            pts = [list(to_ll(*planar.vertices[v].xy)) for v in run]
            if len(pts) == 1:
                pts = pts * 2
            out.append({"points": pts, "step_m": round(h + _ROUND_M, 4),
                        "declared_step_m": round(h + _ROUND_M, 4), "faced": False,
                        "kind": "wall_terrace", "faces": [], "shapes": [f"fence_yard:{f.ref}"],
                        "gap": False, "roles": [], "pairs": len(run),
                        "length_m": round(sum(math.dist(planar.vertices[a].xy,
                                                        planar.vertices[b].xy)
                                              for a, b in zip(run, run[1:], strict=False)), 2),
                        "height_m": round(h, 3), "lots": 0})
    return out


def _ring_runs(planar, f, over_fn) -> list[list[int]]:
    """The runs of consecutive vertices of face ``f``'s rings that
    ``over_fn`` holds for, each walked from a vertex off every run (a run
    crossing the ring's first vertex is ONE run; a ring wholly over is one
    run, closed)."""
    runs: list[list[int]] = []
    for cyc in (f.ring, *f.holes):
        vs = list(planar.ring_vertices(cyc))
        over = [bool(over_fn(v)) for v in vs]
        if all(over):
            runs.append(vs + vs[:1])
            continue
        k = over.index(False)                   # start the walk off a run
        cur: list[int] = []
        for v, o in zip(vs[k:] + vs[:k], over[k:] + over[:k], strict=True):
            if o:
                cur.append(v)
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
    return runs


def _yard_record(planar, law, ref: str, rec, z) -> "dict[str, _t.Any] | None":
    """The fence yard beside level ``ref`` (``yard_plane`` on its landing
    record), or ``None``; with its road run (spec 2068 A3 R5: the free
    vertices' ``run_vertices`` and the ``infeasible`` count, re-read off
    the sources' final ``z``) and the G6' ratio."""
    pl = rec.get("yard_plane")
    if not pl:
        return None
    from ..model.planar import fence_yard_pad
    faces = [f for f in _yard_faces(planar) if fence_yard_pad(f.ref) == rec.get("pad")]
    vs = sorted({v for f in faces for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)})
    zs = [float(z[v]) for v in vs] if z is not None else []
    from ..constraints.yard_edge import yard_runs
    from ..solve.project_yard import run_bounds
    runs = [r for r in yard_runs(planar, law) if r.level == ref]
    bad = sum(1 for r in runs if z is not None
              for lo, hi in run_bounds(planar, law, r, z).values() if lo > hi)
    ratio = rec.get("yard_g6_ratio")
    return {"plane": [round(float(c), 6) for c in pl],
            "tilt": round(math.hypot(float(pl[1]), float(pl[2])), 4),
            "faces": [str(f.ref) for f in faces],
            "z": [round(min(zs), 3), round(max(zs), 3)] if zs else None,
            "g6_ratio": None if ratio is None else round(float(ratio), 3),
            "run_faces": sorted({str(planar.faces[f].ref) for r in runs for f in r.faces}),
            "run_vertices": sum(len(r.free) for r in runs),
            "infeasible": bad}
