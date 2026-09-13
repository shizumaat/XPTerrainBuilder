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

import dataclasses as _dc
import time
import typing as _t

import numpy as np

from ..law import Law
from ..model.planar import PlanarMap
from ..solve.why import Prepared, _drop, solve_with_pressure
from ..solve.why import report as _report

__all__ = ["prepare", "_prepare_solved", "resolve_faces", "taxi_letters",
           "design_block", "report", "chain_kml"]


def prepare(icao: str, inputs, law: Law | None = None,
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
    from ..planar.build import build as build_planar
    wall: dict[str, float] = {}
    t = time.perf_counter()
    law = law or Law.for_airport(icao)
    airport, _lrep = load_with_report(icao, inputs, law)
    wall["load"] = time.perf_counter() - t
    t = time.perf_counter()
    cl = classify(airport, law, load_rules())
    pm, _ps = build_planar(airport, cl, law)
    wall["classify+planar"] = time.perf_counter() - t
    return _prepare_solved(icao, airport, pm, law, out, drop, wall, cl=cl)


def _prepare_solved(icao: str, airport, pm: PlanarMap, law: Law,
                    out: _t.Callable[[str], None] = print, drop: _t.Sequence[str] = (),
                    wall: dict[str, float] | None = None, cl=None) -> Prepared:
    """From a built planar map: the rows, THE DESIGN SURFACE solve with the
    per-row pressures, the seam passes — ``prepare``'s solve half, so a twin
    can drive it on a synthetic airport.  There is no infeasible branch any
    more (RULINGS 2026-09-08t): the least-squares solve always answers."""
    from .shapes import shape_constraints, shape_stage
    wall = wall if wall is not None else {"load": 0.0, "classify+planar": 0.0}
    t = time.perf_counter()
    # THE SHAPE STAGE (2026-09-08k): the rows ``why`` reads are the build's
    stage = shape_stage(pm, law, airport, cl, out=out)
    pm = stage.pm
    # THE TAXI CHAIN'S TARGET PROFILE (spec §8.6): the pipeline publishes
    # it into ``taxi_trend_z`` before the solve, so ``why`` publishes it
    # too — without it the objective table cannot name the ``taxi_trend``
    # term at all and a vertex held by its trend reads as "held by bending
    # alone", the exact sentence 10o was attributed on.
    # REPORTED, NOT FIXED HERE: ``why`` does NOT publish the RUNWAY profile
    # (``preferred_z``) either, and never has — its LP is the pipeline's
    # minus that channel.  Adding it reds `test_why`'s chain-trace twin
    # (the trace's own dz changes), which is §21's ground, not this
    # round's; the lane reports it rather than widening someone else's twin.
    from ..constraints.apron_trend import with_apron_trend
    from ..constraints.taxi_trend import with_taxi_trend
    pm = with_taxi_trend(pm, law, airport)
    # THE APRON BODY'S 2-D TREND (spec §8.7) is published for the same
    # reason and in the same order the pipeline publishes it: without it an
    # apron vertex held by its trend reads "held by bending alone" and the
    # objective table cannot name the ``apron_trend`` term at all.
    pm = with_apron_trend(pm, law, airport)
    # THE EAT RAMP'S REACH (spec §36 (5)): the pipeline WITHDRAWS both
    # trend channels over the derived ramp reach before it solves, so
    # ``why`` must too — otherwise a ramp vertex reads as held by a
    # ``taxi_trend`` row the build does not have.
    from ..constraints.eat import withdraw_trend_over_reach
    pm = withdraw_trend_over_reach(pm, law, airport)
    stage = _dc.replace(stage, pm=pm)
    cs, counts, _g = shape_constraints(pm, law, airport, stage)
    cs = _drop(cs, drop)
    wall["constraints"] = time.perf_counter() - t
    t = time.perf_counter()
    # §38 (1) (owner RULINGS 2026-09-13ah): the seam is a ``Pin``, so the
    # pipeline runs ONE solve and this twin does too — the fixed-point
    # "seam passes" loop is deleted on both sides.
    sol, rep, press = solve_with_pressure(pm, cs, law)
    wall["solve"] = time.perf_counter() - t
    z = np.asarray(sol.z, float)
    if drop:
        out(f"[{icao}] why: ARM — families dropped before the solve: {list(drop)}")
    out(f"[{icao}] why: load {wall['load']:.2f} s  classify+planar "
        f"{wall['classify+planar']:.2f} s  constraints {wall['constraints']:.2f} s  "
        f"solve {wall['solve']:.2f} s  ({len(pm.vertices)} vertices, "
        f"{rep.rows} rows)")
    out(f"[{icao}] why: {rep.line()}")
    return Prepared(icao, airport, law, pm, cs, counts, rep, z, wall, press)


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



def design_block(prep: Prepared) -> list[str]:
    """THE DESIGN SURFACE's residual (RULINGS 2026-09-08t) as ``why`` states
    it: the objective's energy per term, and the law families whose targets
    the surface missed — the reading that replaced the relaxed-mode and
    apron-preference blocks (both deleted with the machinery they read)."""
    rep = prep.design
    L = [f"-- design surface (08t): {rep.rounds} active-set round(s)"
         f"{'' if rep.converged else ' — THE SET DID NOT SETTLE'}, {rep.unknowns} unknowns, "
         f"{rep.triangles} triangles in {rep.components} complexes ({rep.detached} detached)"]
    L.append("   objective energy by term: " + ", ".join(
        f"{k} {v:g}" for k, v in sorted(rep.terms.items(), key=lambda kv: -kv[1])))
    missed = sorted(((v["max_m"], k, v) for k, v in rep.families.items() if v["missed"]),
                    reverse=True)
    if not missed:
        L.append("   every law target met inside the materiality floor")
        return L
    L.append("   targets missed (family: missed/rows, worst metres):")
    for mx, k, v in missed[:12]:
        L.append(f"   {k:26s} {v['missed']:6d}/{v['rows']:<6d} {mx:.3f} m")
    return L


def report(prep: Prepared, fid: int, **kw) -> str:
    """``solve.why.report`` with the code-letter evidence attached and the
    design surface's residual block (08t)."""
    text = _report(prep, fid, letters=taxi_letters(prep, fid), **kw)
    block = design_block(prep)
    return text + ("\n" + "\n".join(block) if block else "")


# ── the chain as a KML (the owner's reading surface) ─────────────────────

_KML_COLOURS = {
    # aabbggrr — the family classes the owner reads on the ground
    "taxi_centreline": "ff00ff00", "taxi_chain": "ff00ff00", "taxi_box": "ff00ff00",
    "no_step_pairs": "ff00ffff",
    "junction_mesh": "ffff8800", "runway_profile": "ffffffff", "runway_crown": "ffffffff",
    "runway_vertical_curve": "ffffffff", "runway_chain": "ffffffff", "runway_pins": "ffffffff",
    "apron_within_shape": "ff0000ff", "apron_chain": "ff0000ff", "apron_edge_portion": "ff0000ff",
    "apron_preference": "ff0000ff",
    "pads": "ffff00ff", "zone_bands": "ff888888", "strip_transverse": "ff888888",
}


def chain_kml(prep: Prepared, fid: int, path: str, title: str | None = None,
              tol: float | None = None) -> _t.Any:
    """Write the ``why`` CHAIN TRACE of face ``fid`` as a KML — one
    LineString per binding row from the shape to the nearest hard
    terminal, named ``i. family length cap dz (faces)`` and coloured by
    family (taxi green, no_step yellow, junction orange, runway white,
    apron red), plus the start and terminal points — the owner's reading
    surface for "which rows hold this shape" (RULINGS 2026-09-05aa /
    06n were ruled on exactly this artefact).  Returns the trace."""
    from xml.sax.saxutils import escape
    from ..model.constraints import Diff
    from ..solve.why import BIND_TOL_M, chain_trace, face_vertices
    tr = chain_trace(prep, face_vertices(prep, fid), BIND_TOL_M if tol is None else tol)
    _to_xy, to_ll = prep.airport.frame.transformers()
    pm, z = prep.pm, prep.z

    def ll(v: int) -> str:
        la, lo = to_ll(*pm.vertices[v].xy)
        return f"{lo:.8f},{la:.8f},0"

    def faces_of(u: int, v: int) -> str:
        fs = set(pm.vertices[u].incident_faces) | set(pm.vertices[v].incident_faces)
        names = sorted(f"{pm.faces[f].role}#{f}" for f in fs)
        return ",".join(names[:3]) + ("…" if len(names) > 3 else "")

    f = pm.faces[fid]
    L: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>',
                    '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
                    f"<name>{escape(title or f'{prep.icao} why chain: {f.role} {f.ref} (face {fid})')}</name>"]
    for fam, col in _KML_COLOURS.items():
        L.append(f'<Style id="{fam}"><LineStyle><color>{col}</color><width>4</width></LineStyle></Style>')
    L.append('<Style id="other"><LineStyle><color>ffaaaaaa</color><width>4</width></LineStyle></Style>')
    if tr is None:
        L.append("<Placemark><name>no terminal reached: nothing binds the shape to a pin</name></Placemark>")
    else:
        fams: dict[str, float] = {}
        for s in tr.steps:
            fams[s.family] = fams.get(s.family, 0.0) + s.dz
        L.append("<Folder><name>chain by family: " + escape(", ".join(
            f"{k} {v:+.2f} m" for k, v in sorted(fams.items(), key=lambda kv: -abs(kv[1])))) + "</name>")
        for i, s in enumerate(tr.steps):
            r = s.row
            geom = (f"{r.d:.0f} m {r.cap:.2%}" if isinstance(r, Diff)
                    else f"{type(r).__name__} {r.source.ruling[:30]}")
            name = f"{i + 1}. {s.family} {geom} dz {s.dz:+.3f} ({faces_of(s.v, s.u)})"
            style = s.family if s.family in _KML_COLOURS else "other"
            L.append(f"<Placemark><name>{escape(name)}</name><styleUrl>#{style}</styleUrl>"
                     f"<LineString><coordinates>{ll(s.v)} {ll(s.u)}</coordinates></LineString></Placemark>")
        L.append("</Folder>")
        L.append(f"<Placemark><name>{escape(f'START {f.role} {f.ref} v{tr.start} z {z[tr.start]:.2f}')}</name>"
                 f"<Point><coordinates>{ll(tr.start)}</coordinates></Point></Placemark>")
        L.append(f"<Placemark><name>{escape(f'TERMINAL {tr.terminal_kind} v{tr.terminal} z {z[tr.terminal]:.2f}: {tr.terminal_note}')}</name>"
                 f"<Point><coordinates>{ll(tr.terminal)}</coordinates></Point></Placemark>")
    L.append("</Document></kml>")
    with open(path, "w") as fh:
        fh.write("\n".join(L) + "\n")
    return tr
