"""``why`` — THE PIPELINE SIDE (lane v2route, RULINGS 2026-09-04q-3:
``solve/`` imports law and model only): rebuild the pipeline's own LP
(load → classify → planar → constraints → the HiGHS solve with duals,
seam passes included, no emit), resolve the target face from a shapeID /
a patch / a coordinate, and read the apt.dat 1202 code-letter evidence
along the centrelines touching it.  The analysis over the prepared LP
(bindings, chain trace, relax-one-family, the report) is
``solve/why.py``.
"""
from __future__ import annotations

import time
import typing as _t

import numpy as np

from ..law import Law
from ..model.planar import PlanarMap
from ..solve.api import Weights
from ..solve.why import Prepared, _drop, solve_with_duals
from ..solve.why import report as _report

__all__ = ["prepare", "resolve_faces", "taxi_letters", "report"]


def prepare(icao: str, inputs, law: Law | None = None,
            weights: Weights | None = None,
            out: _t.Callable[[str], None] = print,
            drop: _t.Sequence[str] = ()) -> Prepared:
    """Run the pipeline's stages up to the solve (the seam passes
    included, to a fixed point exactly as ``pipeline.build`` does).
    ``drop``: families (``family_of`` labels) removed BEFORE the solve —
    a labelled measurement arm ("with no-step relaxed, what binds
    next?"), never the build."""
    from ..airport.load import load_with_report
    from ..classify import classify, load_rules
    from ..constraints import generate
    from .build import DEFAULT_WEIGHTS
    from ..planar.build import build as build_planar
    w = weights or DEFAULT_WEIGHTS
    wall: dict[str, float] = {}
    t = time.perf_counter()
    law = law or Law.for_airport(icao)
    airport, _lrep = load_with_report(icao, inputs, law)
    wall["load"] = time.perf_counter() - t
    t = time.perf_counter()
    cl = classify(airport, law, load_rules())
    pm, _ps = build_planar(airport, cl, law)
    wall["classify+planar"] = time.perf_counter() - t
    t = time.perf_counter()
    cs, counts, _g = generate(pm, law, airport)
    cs = _drop(cs, drop)
    wall["constraints"] = time.perf_counter() - t
    t = time.perf_counter()
    prob, res = solve_with_duals(pm, cs, w)
    if res.status != 0:
        raise RuntimeError(f"[{icao}] why: the LP did not solve (status {res.status}: "
                           f"{res.message}); run `build` for the IIS")
    tol = law.tables.emit.materiality.elevation_m
    prev: frozenset[int] | None = None
    for _n in range(6):                     # the pipeline's seam passes
        if not pm.seam_vertices:
            break
        z = res.x[:prob.n]
        honoured = frozenset(v for v in pm.seam_vertices if pm.vertices[v].dem_z is not None
                             and abs(z[v] - pm.vertices[v].dem_z) <= tol)
        if len(honoured) == len(pm.seam_vertices) or honoured == prev:
            break
        prev = honoured
        cs, counts2, _g = generate(pm, law, airport, seam_honoured=honoured)
        cs = _drop(cs, drop)
        counts["seam_pin_pair_exempt"] = counts2["seam_pin_pair_exempt"]
        prob, res = solve_with_duals(pm, cs, w)
        if res.status != 0:
            raise RuntimeError(f"[{icao}] why: seam pass LP status {res.status}")
    wall["solve"] = time.perf_counter() - t
    z = np.asarray(res.x[:prob.n], float)
    esc = {g: float(res.x[col]) for g, col in prob.soft_cols.items()}
    if drop:
        out(f"[{icao}] why: ARM — families dropped before the solve: {list(drop)}")
    out(f"[{icao}] why: load {wall['load']:.2f} s  classify+planar "
        f"{wall['classify+planar']:.2f} s  constraints {wall['constraints']:.2f} s  "
        f"solve {wall['solve']:.2f} s  ({len(pm.vertices)} vertices, "
        f"{prob.A_ub.shape[0]}+{prob.A_eq.shape[0]} rows)")
    return Prepared(icao, airport, law, pm, cs, counts, w, prob, res, z, esc, wall)



# ── target resolution ────────────────────────────────────────────────────

def _face_polygon(pm: PlanarMap, fid: int):
    from shapely.geometry import Polygon
    f = pm.faces[fid]
    ring = [pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]
    holes = [[pm.vertices[v].xy for v in pm.ring_vertices(h)] for h in f.holes]
    p = Polygon(ring, holes)
    return p if p.is_valid else p.buffer(0)


def resolve_faces(prep: Prepared, shape: int | None = None,
                  at: tuple[float, float] | None = None,
                  patch: str | None = None) -> tuple[list[int], str]:
    """The face(s) a ``why`` targets: ``shape`` is the face id (the
    emitter writes ``shapeID`` = face id) — with ``patch`` the ring of
    that shapeID in the given patch is matched to the face of largest
    overlap instead (a patch from another build); ``at`` is a WGS84
    coordinate, the face containing it (or the nearest)."""
    from shapely.geometry import Point
    if at is not None:
        lat, lon = at
        to_xy, _ = prep.airport.frame.transformers()
        p = Point(to_xy(lon, lat))
        best: tuple[float, int] | None = None
        for fid in prep.pm.faces:
            d = _face_polygon(prep.pm, fid).distance(p)
            if best is None or d < best[0]:
                best = (d, fid)
            if d == 0.0:
                break
        if best is None:
            return [], "no faces"
        return [best[1]], (f"face containing {lat:.6f},{lon:.6f}" if best[0] == 0.0
                           else f"nearest face to {lat:.6f},{lon:.6f} ({best[0]:.1f} m off)")
    if shape is None:
        raise ValueError("why: one of shape / at")
    if patch is not None:
        from ..classify.explain import shape_polygon
        found = shape_polygon(patch, shape, prep.airport)
        if found is None:
            return [], f"no way with shapeID={shape} in {patch}"
        poly, tags = found
        best_f: tuple[float, int] | None = None
        for fid in prep.pm.faces:
            a = _face_polygon(prep.pm, fid).intersection(poly).area
            if best_f is None or a > best_f[0]:
                best_f = (a, fid)
        if best_f is None or best_f[0] <= 0.0:
            return [], f"shapeID={shape} of {patch} overlaps no face"
        return [best_f[1]], (f"shapeID {shape} of {patch} (role={tags.get('role')}) -> "
                             f"face {best_f[1]} by overlap {best_f[0]:,.0f}/{poly.area:,.0f} m2")
    if shape not in prep.pm.faces:
        return [], f"no face {shape} in this build ({len(prep.pm.faces)} faces)"
    return [shape], f"face {shape} (shapeID = face id in the v2 patch)"



# ── code-letter evidence ─────────────────────────────────────────────────

def taxi_letters(prep: Prepared, fid: int, near_m: float = 3.0) -> list[str]:
    """For every taxi centreline touching the face: the apt.dat 1202
    edges lying along it (by geometry, within ``near_m``) with their
    names and width-class letters, and the faces it bounds with their
    code letter and longitudinal cap — the evidence hypothesis (d) reads."""
    from shapely.geometry import LineString
    from ..constraints.precedence import view
    from ..law.tables import role_cap
    from ..solve.why import face_vertices
    vw = view(prep.pm, prep.law)
    verts = set(face_vertices(prep, fid))
    nodes = {k: n.xy for k, n in prep.airport.taxi_nodes.items()}
    out: list[str] = []
    for bid, b in prep.pm.breaklines.items():
        if b.kind != "taxi_centerline" or not (set(vw.chains[bid]) & verts):
            continue
        line = LineString([vw.xy[v] for v in vw.chains[bid]])
        band = line.buffer(near_m)
        along: dict[str, set[str]] = {}
        for e in prep.airport.taxi_edges:
            if e.is_runway or e.a not in nodes or e.b not in nodes:
                continue
            seg = LineString([nodes[e.a], nodes[e.b]])
            if seg.length <= 0.0:
                continue
            # along the chain when at least half the edge lies within near_m of it
            if band.intersection(seg).length >= 0.5 * seg.length:
                along.setdefault(e.name or "?", set()).add(e.width_class or "?")
        faces: dict[int, None] = {}
        for eid in b.edges:
            e = prep.pm.edges[eid]
            for f in (e.left_face, e.right_face):
                if f is not None:
                    faces[f] = None
        fl = []
        for f in faces:
            face = prep.pm.faces[f]
            rc = role_cap(prep.law, face.role, face.code_number, face.code_letter)
            fl.append(f"{f}:{face.role}/{face.code_letter or '-'}"
                      f"@{rc.longitudinal:.1%}" if rc else f"{f}:{face.role}/ungoverned")
        letters = "; ".join(f"{n} {sorted(ls)}" for n, ls in sorted(along.items())) or "-"
        out.append(f"  centreline {bid} ref={b.ref!r} ({line.length:.0f} m): apt.dat 1202 "
                   f"name/letters {letters}; faces " + ", ".join(fl))
    return out



def report(prep: Prepared, fid: int, **kw) -> str:
    """``solve.why.report`` with the code-letter evidence attached."""
    return _report(prep, fid, letters=taxi_letters(prep, fid), **kw)
