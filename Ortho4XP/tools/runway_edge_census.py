#!/usr/bin/env python3
"""THE RUNWAY EDGE CENSUS on a v2 CAPTURE (``v2_solve_replay --capture``).

    venv/bin/python tools/runway_edge_census.py CAPTURE.pkl
        [--face N] [--bound-walk] [--solved SOLVED.pkl] [--json OUT]

THE QUESTION IT ANSWERS.  Where does each runway's own ring sit against its
apt.dat HALF-WIDTH, in the generator's planar frame — and do the two
instruments that price the §40 (2) transverse law (the generator
``constraints.runway_profile.runway_transverse`` and the v2 verify
``verify.runway.runway_transverse``) price every runway ring vertex at the
same bound?  Issue #134 / RULINGS 2026-09-30ak: roughly HALF of every
runway's own edge vertices sit a hair BEYOND the half-width (slab-vs-chain
and noding, d − half spread ±0.4–0.9 m), and the step-function cap
(``lateral_m <= half_width_m``) flipped them between the runway's and the
shoulder's cap per vertex, per frame.

THREE READINGS, all on the capture's own planar map (no solve for the
first two; geometry only):

* default — per runway, the BODY ring vertices (faces whose largest cell
  overlap is not a ``runway_shoulder`` cell) and the SHOULDER-only
  vertices: count, how many sit beyond the half-width, how many within
  ±5 cm of it, and the d − half spread.  The ridge vertices are skipped.
* ``--face N`` — one runway face's ring walked vertex by vertex: d − half,
  the along-axis station, the incident faces and the nearest body vertex
  (the KASE face 0|14 attribution, 30ak).  With ``--solved`` (a
  ``v2_solve_replay --solved-out`` pickle) each vertex also carries its
  solved z, its ridge foot's z, the fall and the transverse bound.
* ``--bound-walk`` — THE RING WALK (twin of ``tests/auto_patch_v2/
  test_runway_transverse.py``): for every off-ridge, off-crossing
  ``runway`` face vertex, the generator's bound (planar foot on its own
  ridge chain, ``runway_half_widths``) against the verify's (the emitted
  crown spine in the census frame, ``Patch.of``, the published half
  width), both through ``law.tables.runway_transverse_bound``.  Emitted
  xy does not depend on z, so no solve is needed.  Prints the population,
  the one-sided vertices (a foot on one side only) and the worst
  |bound_gen − bound_verify|.

It measures geometry and prices through the engine's own accessors
(``_foot``, ``ridge_chains``, ``runway_half_widths``,
``verify.runway._nearest_ridge``, ``runway_transverse_bound``) — nothing
re-spelled.  Defect counts come from ``harness/census.py`` and the v2
verify, never from here.

Promoted 2026-09-30 (lane ``transverse134``) from the #134 spec author's
scratchpad ``r134/edge_census.py`` on its SECOND use (RULINGS
``7e90032``).
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load(path: Path) -> dict:
    with Path(path).open("rb") as fh:
        return pickle.load(fh)


def _law(cap: dict):
    from auto_patch_v2.law import Law
    return Law.for_airport(cap.get("icao") or cap.get("law_icao"))


def _face_vs(pm, f) -> list[int]:
    out, seen = [], set()
    for cyc in (f.ring, *f.holes):
        for eid in cyc:
            e = pm.edges[eid]
            for v in (e.a, e.b):
                if v not in seen:
                    seen.add(v)
                    out.append(v)
    return out


def face_kinds(pm, cl) -> dict[int, str]:
    """Runway face id -> ``body`` / ``shoulder`` / ``?`` by its largest
    overlap with a classified runway cell of its own ref."""
    from shapely.geometry import Polygon
    cells = [(Polygon(c.ring).buffer(0), c.kind, c.ref)
             for c in getattr(cl, "cells", ()) if getattr(c, "role", None) == "runway"]
    out: dict[int, str] = {}
    for fid, f in pm.faces.items():
        if f.role != "runway":
            continue
        poly = Polygon([pm.vertices[pm.edges[e].a].xy for e in f.ring]).buffer(0)
        best = None
        for cp, k, r in cells:
            if r != f.ref:
                continue
            a = cp.intersection(poly).area
            if best is None or a > best[0]:
                best = (a, k)
        out[fid] = (("body" if best[1] != "runway_shoulder" else "shoulder")
                    if best and best[0] > 0 else "?")
    return out


def edge_census(cap: dict) -> dict:
    """The default reading: per runway, body / shoulder-only ring vertices
    against the half-width (d from the generator's own foot)."""
    from auto_patch_v2.constraints.precedence import view
    from auto_patch_v2.constraints.runway_profile import (_foot, ridge_chains,
                                                          runway_half_widths)
    pm, cl, ap = cap["pm"], cap.get("cl"), cap["airport"]
    law = _law(cap)
    vw = view(pm, law)
    chains = ridge_chains(vw)
    half_of = runway_half_widths(ap)
    kind = face_kinds(pm, cl) if cl is not None else {}
    ridge = {v for chs in chains.values() for c in chs for v in c}
    body = collections.defaultdict(set)
    sh = collections.defaultdict(set)
    for fid, f in pm.faces.items():
        if f.role == "runway":
            (sh if kind.get(fid) == "shoulder" else body)[f.ref].update(_face_vs(pm, f))
    out = {"icao": cap.get("icao"), "face_kinds": dict(collections.Counter(kind.values())),
           "runways": {}}
    for ref, half in sorted(half_of.items()):
        rec = {"half_m": half}
        for label, vs in (("body", body.get(ref, set())),
                          ("shoulder_only", sh.get(ref, set()) - body.get(ref, set()))):
            ds = sorted(ft[0] - half for v in vs if v not in ridge
                        for ft in [_foot(vw, v, chains.get(ref, []))] if ft)
            if not ds:
                rec[label] = None
                continue
            near = [x for x in ds if abs(x) <= 0.05]
            rec[label] = {"n": len(ds), "beyond_half": sum(1 for x in ds if x > 0),
                          "within_5cm": len(near),
                          "within_5cm_beyond": sum(1 for x in near if x > 0),
                          "beyond_0_5m": sum(1 for x in ds if x > 0.5),
                          "beyond_5m": sum(1 for x in ds if x > 5.0),
                          "d_minus_half_min": round(ds[0], 4),
                          "d_minus_half_med": round(ds[len(ds) // 2], 4),
                          "d_minus_half_max": round(ds[-1], 4)}
        out["runways"][ref] = rec
    return out


def face_walk(cap: dict, face: int, solved: dict | None = None) -> list[dict]:
    """``--face N``: one runway face's ring, vertex by vertex."""
    from auto_patch_v2.constraints.geometry import project_to_chain
    from auto_patch_v2.constraints.precedence import view
    from auto_patch_v2.constraints.runway_profile import (_foot, ridge_chains,
                                                          runway_half_widths)
    from auto_patch_v2.law.tables import runway_transverse_bound
    pm, cl, ap = cap["pm"], cap.get("cl"), cap["airport"]
    law = _law(cap)
    vw = view(pm, law)
    chains = ridge_chains(vw)
    half_of = runway_half_widths(ap)
    f = pm.faces[face]
    chs = chains.get(f.ref, [])
    half = half_of.get(f.ref, 0.0)
    kind = face_kinds(pm, cl) if cl is not None else {}
    bring = [pm.vertices[v].xy for bf, k in kind.items()
             if k == "body" and pm.faces[bf].ref == f.ref
             for v in _face_vs(pm, pm.faces[bf])]
    z = None if solved is None else solved["z"]
    out = []
    for v in _face_vs(pm, f):
        xy = pm.vertices[v].xy
        ft = _foot(vw, v, chs)
        rec = {"v": v, "xy": [round(c, 3) for c in xy],
               "faces": [(i, pm.faces[i].role) for i in pm.vertices[v].incident_faces]}
        if ft is not None:
            d, a, b, t = ft
            best = min((project_to_chain(xy, [vw.xy[c] for c in ch]) for ch in chs
                        if len(ch) >= 2), key=lambda r: r[0])
            rec.update({"d_m": round(d, 4), "d_minus_half": round(d - half, 4),
                        "station_m": round(best[3], 1)})
            bound = runway_transverse_bound(law, d, half, f.code_letter, f.code_number)
            rec["bound_m"] = None if bound is None else round(bound, 4)
            if z is not None:
                zr = (1 - t) * z[a] + t * z[b]
                rec.update({"z": round(float(z[v]), 3), "ridge_z": round(float(zr), 3),
                            "fall_m": round(float(zr - z[v]), 4)})
        if bring:
            rec["nearest_body_vertex_m"] = round(min(math.dist(xy, p) for p in bring), 3)
        out.append(rec)
    return out


class _GeomSol:
    """The emit's solution interface with z zero: emitted xy is independent
    of z (``emit.graded.graded_surface`` rounds z, nothing else)."""

    def __init__(self, n: int):
        from auto_patch_v2.solve import Status
        self.z = [0.0] * n
        self.iterations = 0
        self.status = Status("optimal")
        self.residual = None


def bound_walk(cap: dict) -> dict:
    """THE RING WALK: generator vs verify bound per runway face vertex."""
    from auto_patch_v2.constraints.precedence import view
    from auto_patch_v2.constraints.runway_profile import (_foot, ridge_chains,
                                                          runway_half_widths)
    from auto_patch_v2.emit.graded import graded_surface
    from auto_patch_v2.law.tables import runway_transverse_bound
    from auto_patch_v2.verify.frame import Patch
    from auto_patch_v2.verify.runway import _nearest_ridge
    pm, ap = cap["pm"], cap["airport"]
    law = _law(cap)
    vw = view(pm, law)
    chains = ridge_chains(vw)
    half_of = runway_half_widths(ap)
    n = 1 + max(pm.vertices)
    surf = graded_surface(pm, law, _GeomSol(n), ap.frame.origin, ap.frame.crs, {})
    p = Patch.of(surf, law, {})
    spines: dict[str, list] = {}
    for sh in p.features:
        if sh.feature == "crown_spine" and sh.ref not in spines:
            spines[sh.ref] = [list(sh.closed_ring)]
    all_spines = [list(sh.closed_ring) for sh in p.features if sh.feature == "crown_spine"]
    xing: set[int] = set()
    for f in vw.faces_of_role(("runway_crossing",)):
        xing.update(vw.face_vertices(f.id))
    rows, gen_only, ver_only = [], [], []
    done: set[int] = set()
    for f in vw.faces_of_role(("runway",)):
        chs = chains.get(f.ref, [])
        if not chs:
            continue
        own = {v for c in chs for v in c}
        half = half_of.get(f.ref, 0.0)
        for v in vw.face_vertices(f.id):
            if v in done or v in own or v in xing:
                continue
            done.add(v)
            ft = _foot(vw, v, chs)
            dg = ft[0] if ft is not None and ft[0] > 0.0 else None
            dv, zr, _ = _nearest_ridge(*p.xy[v], spines.get(f.ref, all_spines))
            dv = dv if zr is not None and dv > 0.0 else None
            if dg is None and dv is None:
                continue
            if dv is None:
                gen_only.append(v)
                continue
            if dg is None:
                ver_only.append(v)
                continue
            bg = runway_transverse_bound(law, dg, half, f.code_letter, f.code_number)
            bv = runway_transverse_bound(law, dv, round(half, 4), f.code_letter,
                                         f.code_number)
            if bg is None or bv is None:
                continue
            rows.append({"v": v, "ref": f.ref, "d_gen": dg, "d_verify": dv,
                         "d_minus_half": dg - half, "bound_gen": bg, "bound_verify": bv,
                         "diff_m": abs(bg - bv)})
    rows.sort(key=lambda r: -r["diff_m"])
    return {"icao": cap.get("icao"), "vertices": len(rows), "gen_only": gen_only,
            "verify_only": ver_only,
            "max_diff_m": rows[0]["diff_m"] if rows else 0.0,
            "max_d_diff_m": max((abs(r["d_gen"] - r["d_verify"]) for r in rows), default=0.0),
            "worst": rows[:10], "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("capture", type=Path, help="v2_solve_replay --capture pickle")
    ap.add_argument("--face", type=int, help="walk one runway face's ring")
    ap.add_argument("--solved", type=Path,
                    help="v2_solve_replay --solved-out pickle (z for --face)")
    ap.add_argument("--bound-walk", action="store_true",
                    help="generator vs verify transverse bound per ring vertex")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    cap = _load(a.capture)
    res: dict = {}
    if a.bound_walk:
        res["bound_walk"] = bw = bound_walk(cap)
        print(f"{bw['icao']} RING WALK: {bw['vertices']} runway ring vertices priced on both "
              f"sides; gen-only {len(bw['gen_only'])}, verify-only {len(bw['verify_only'])}; "
              f"max |bound_gen - bound_verify| {1000 * bw['max_diff_m']:.3f} mm "
              f"(max |d_gen - d_verify| {1000 * bw['max_d_diff_m']:.1f} mm)")
        for r in bw["worst"][:5]:
            print(f"   v{r['v']} {r['ref']} d-half {r['d_minus_half']:+.4f} d_gen "
                  f"{r['d_gen']:.4f} d_verify {r['d_verify']:.4f} bound "
                  f"{r['bound_gen']:.4f}/{r['bound_verify']:.4f}")
    elif a.face is not None:
        solved = _load(a.solved) if a.solved else None
        res["face"] = rows = face_walk(cap, a.face, solved)
        for r in rows:
            print("   " + " ".join(f"{k}={v}" for k, v in r.items()))
    else:
        res["edge_census"] = ec = edge_census(cap)
        print(f"{ec['icao']} runway faces by kind: {ec['face_kinds']}")
        for ref, rec in ec["runways"].items():
            print(f"RUNWAY {ref} half={rec['half_m']}")
            for label in ("body", "shoulder_only"):
                s = rec[label]
                if s is None:
                    print(f"  {label}: none")
                    continue
                print(f"  {label}: n={s['n']} beyond_half={s['beyond_half']} "
                      f"within±5cm={s['within_5cm']} (beyond {s['within_5cm_beyond']}) "
                      f"beyond>0.5m={s['beyond_0_5m']} beyond>5m={s['beyond_5m']} "
                      f"d-half min/med/max={s['d_minus_half_min']}/"
                      f"{s['d_minus_half_med']}/{s['d_minus_half_max']}")
    if a.json:
        a.json.write_text(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
