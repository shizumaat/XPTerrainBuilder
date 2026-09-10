#!/usr/bin/env python3
"""THE PAD-LEVEL INSTRUMENT (owner RULINGS 2026-09-10l "Pad takes the
apron edge level", 2026-09-10y "a pad is ONE PLANE fitted to its
frontage") — the three reads lane ``v2padlevel`` needed twice each,
promoted out of its scratch dir under the tool discipline.

    venv/bin/python tools/pad_level_report.py pads SOLVED.pkl [--ref REF]
        [--site LAT,LON]
    venv/bin/python tools/pad_level_report.py transect SOLVED.pkl
        --to LAT,LON --from-ref REF [--step M]
    venv/bin/python tools/pad_level_report.py delta A.osm B.osm
        [--role building] [--materiality M]

``pads``     — every rigid face (or the one named by ``--ref``): its rim,
               its PLANARITY (the residual of the least-squares plane
               through its own vertices — the ruling's 0.01 m bar), its
               TILT against the 1 % ceiling, the roles it FRONTS and how
               many vertices it shares with each, and, per fronting role,
               the pavement's own level in a band beside the contact
               against the pad's own — the fit's residual.
``transect`` — z along a straight line at 1 m stations, sampled over the
               patch's OWN triangulation (``solve.rows._face_triangles``),
               from the ring vertex of ``--from-ref`` nearest the target to
               the target vertex: the "does the apron still fall into the
               terminal" read of RULINGS 10h/10k.
``delta``    — the pad LEVEL change between two emitted patches, joined per
               way on its ``o4_ref`` / shapeID tag (never on proximity,
               memory ``canonical-identity-join``): how many pads moved
               beyond materiality, p50 / p90 / max, and the SPREAD of each
               pad's own ring before and after (a pad is one plane, so its
               spread is its tilt over its span).

The first two read a ``v2_solve_replay.py --solved-out`` pickle (the solve
arm); the third reads emitted patches (the build arm).  Read-only.
"""
from __future__ import annotations

import argparse
import math
import pickle
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


# ── shared reads ─────────────────────────────────────────────────────────

def _load(path: Path):
    with open(path, "rb") as fh:
        d = pickle.load(fh)
    return d["pm"], np.asarray(d["z"], float)


def _ring(pm, f) -> set[int]:
    vs = set(pm.ring_vertices(f.ring))
    for h in (f.holes or ()):
        vs |= set(pm.ring_vertices(h))
    return vs


def _nearest_vertex(pm, lat: float, lon: float) -> int:
    return min(pm.vertices, key=lambda v: (pm.vertices[v].key[0] - lat) ** 2
               + (pm.vertices[v].key[1] - lon) ** 2)


def plane_fit(xy: list[tuple[float, float]], z: np.ndarray
              ) -> tuple[float, float]:
    """``(max |residual| from the least-squares plane, tilt m/m)`` — the
    two numbers 09c's "ONE PLANE, flat within 1 %" is read with."""
    A = np.array([[1.0, x, y] for x, y in xy])
    coef, *_ = np.linalg.lstsq(A, z, rcond=None)
    return (float(np.abs(A @ coef - z).max()),
            float(math.hypot(coef[1], coef[2])))


# ── pads ─────────────────────────────────────────────────────────────────

def cmd_pads(a) -> int:
    from auto_patch_v2.constraints.pads import (pad_frontage, rigid_roles,
                                                pad_shared)
    from auto_patch_v2.law import Law
    pm, z = _load(a.pkl)
    law = Law.for_airport(a.icao) if a.icao else _law_of(pm)
    xy = {v: vx.xy for v, vx in pm.vertices.items()}
    front, shared = pad_frontage(pm, law), pad_shared(pm, law)
    roles = set(rigid_roles(law))
    if a.site:
        lat, lon = (float(x) for x in a.site.split(","))
        v0 = _nearest_vertex(pm, lat, lon)
        print(f"  site vertex {v0} z={z[v0]:.3f} "
              f"dem={pm.vertices[v0].dem_z:.3f}")
    n = 0
    for f in pm.faces.values():
        if f.role not in roles or (a.ref and f.ref != a.ref):
            continue
        vs = sorted(_ring(pm, f))
        if len(vs) < 3:
            continue
        n += 1
        resid, tilt = plane_fit([xy[v] for v in vs], z[vs])
        by_role = front.get(f.id, {})
        print(f"  PAD face {f.id} {f.ref} n={len(vs)} z {z[vs].min():.3f}.."
              f"{z[vs].max():.3f} mean {z[vs].mean():.3f} | PLANE resid "
              f"{resid:.3f} m tilt {tilt * 100:.3f} % | shares "
              f"{len(shared.get(f.id, ()))} | fronts "
              f"{ {r: len(v) for r, v in by_role.items()} }")
        for role, contacts in by_role.items():
            own = _own_band(pm, xy, role, set(vs), contacts, a.band)
            if own:
                print(f"      {role}: contacts mean {z[sorted(contacts)].mean():.3f}"
                      f"  pavement's own {a.band[0]:.0f}-{a.band[1]:.0f} m "
                      f"mean {z[sorted(own)].mean():.3f}  fit residual "
                      f"{z[sorted(own)].mean() - z[sorted(contacts)].mean():+.3f} m")
    print(f"  {n} pad(s) read")
    return 0


def _own_band(pm, xy, role, pad_vs, contacts, band) -> set[int]:
    own: set[int] = set()
    for f in pm.faces.values():
        if f.role != role:
            continue
        own |= _ring(pm, f) - pad_vs
    lo, hi = band
    out = set()
    for v in own:
        for c in contacts:
            d = math.hypot(xy[v][0] - xy[c][0], xy[v][1] - xy[c][1])
            if lo <= d <= hi:
                out.add(v)
                break
    return out


def _law_of(pm):
    from auto_patch_v2.law import Law
    return Law.for_airport(getattr(getattr(pm, "frame", None), "icao", "ZZZZ"))


# ── transect ─────────────────────────────────────────────────────────────

def cmd_transect(a) -> int:
    from shapely.geometry import Point, Polygon
    from shapely.strtree import STRtree

    from auto_patch_v2.solve.rows import _face_triangles
    pm, z = _load(a.pkl)
    xy = {v: vx.xy for v, vx in pm.vertices.items()}
    lat, lon = (float(x) for x in a.to.split(","))
    v1 = _nearest_vertex(pm, lat, lon)
    src = next(f for f in pm.faces.values() if f.ref == a.from_ref)
    x1, y1 = xy[v1]
    v0 = min(pm.ring_vertices(src.ring),
             key=lambda v: (xy[v][0] - x1) ** 2 + (xy[v][1] - y1) ** 2)
    x0, y0 = xy[v0]
    span = math.hypot(x1 - x0, y1 - y0)
    tris = [t for f in pm.faces.values() for t in _face_triangles(pm, f.id)]
    P = {v: np.array(xy[v]) for v in {v for t in tris for v in t}}
    tree = STRtree([Polygon([xy[c] for c in t]) for t in tris])

    def sample(p):
        for i in tree.query(Point(p), predicate="intersects"):
            A, B, C = (P[v] for v in tris[int(i)])
            T = np.array([[B[0] - A[0], C[0] - A[0]],
                          [B[1] - A[1], C[1] - A[1]]])
            det = T[0, 0] * T[1, 1] - T[0, 1] * T[1, 0]
            if abs(det) < 1e-12:
                continue
            r = p - A
            u = (T[1, 1] * r[0] - T[0, 1] * r[1]) / det
            w = (-T[1, 0] * r[0] + T[0, 0] * r[1]) / det
            if u >= -1e-9 and w >= -1e-9 and u + w <= 1 + 1e-9:
                aa, bb, cc = tris[int(i)]
                return (1 - u - w) * z[aa] + u * z[bb] + w * z[cc]
        return None

    ux, uy = (x1 - x0) / span, (y1 - y0) / span
    prof = []
    s = 0.0
    while s <= span:
        prof.append((s, sample(np.array([x0 + ux * s, y0 + uy * s]))))
        s += a.step
    got = [(s, v) for s, v in prof if v is not None]
    print(f"  transect v{v0}[{a.from_ref}] -> v{v1}: span {span:.1f} m, "
          f"{len(got)} station(s)")
    for s, v in got[:: max(1, len(got) // 8)]:
        print(f"      s={s:6.1f} z={v:.3f}")
    if len(got) >= 2:
        step = max(abs(got[i + 1][1] - got[i][1]) for i in range(len(got) - 1))
        print(f"   FALL over the span: {got[-1][1] - got[0][1]:+.3f} m "
              f"({got[0][1]:.3f} -> {got[-1][1]:.3f})")
        print(f"   max {a.step:.0f} m station step: {step:.3f} m")
    return 0


# ── delta ────────────────────────────────────────────────────────────────

def read_levels(path: Path, role: str) -> dict[str, tuple[float, float, float, int]]:
    """Per way of ``role``: ``(mean, min, max, n)`` of its nodes'
    ``alt_abs``, keyed by the way's own identity tag."""
    root = ET.parse(path).getroot()
    alt = {}
    for n in root.iter("node"):
        for tg in n.findall("tag"):
            if tg.get("k") == "alt_abs":
                alt[n.get("id")] = float(tg.get("v"))
    out = {}
    for w in root.iter("way"):
        tags = {tg.get("k"): tg.get("v") for tg in w.findall("tag")}
        if tags.get("o4_role") != role and tags.get("role") != role:
            continue
        zs = [alt[nd.get("ref")] for nd in w.findall("nd")
              if nd.get("ref") in alt]
        if not zs:
            continue
        key = (tags.get("o4_ref") or tags.get("shapeID") or tags.get("ref")
               or w.get("id"))
        out[key] = (sum(zs) / len(zs), min(zs), max(zs), len(zs))
    return out


def cmd_delta(a) -> int:
    A, B = read_levels(a.a, a.role), read_levels(a.b, a.role)
    keys = sorted(set(A) & set(B))
    d = sorted(abs(B[k][0] - A[k][0]) for k in keys)
    moved = [x for x in d if x > a.materiality]
    print(f"role {a.role}: {len(A)} / {len(B)} ways, {len(keys)} joined; "
          f"{len(moved)} moved > {a.materiality} m")

    def q(xs, p):
        return xs[min(len(xs) - 1, int(p * (len(xs) - 1)))] if xs else float("nan")

    if d:
        print(f"   |delta| over ALL joined: p50 {q(d, .5):.3f} "
              f"p90 {q(d, .9):.3f} max {d[-1]:.3f}")
    if moved:
        print(f"   |delta| over MOVED:      p50 {q(moved, .5):.3f} "
              f"p90 {q(moved, .9):.3f} max {moved[-1]:.3f}")
    up = sum(1 for k in keys if B[k][0] - A[k][0] > a.materiality)
    print(f"   rose {up}, fell {len(moved) - up}")
    sa = sorted(A[k][2] - A[k][1] for k in keys)
    sb = sorted(B[k][2] - B[k][1] for k in keys)
    if sa:
        print(f"   ring SPREAD (max-min) p50 {q(sa, .5):.3f} -> {q(sb, .5):.3f}"
              f"; max {sa[-1]:.3f} -> {sb[-1]:.3f}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pads")
    p.add_argument("pkl", type=Path)
    p.add_argument("--ref", help="only this face ref")
    p.add_argument("--icao", help="law for this airport (default: the map's)")
    p.add_argument("--site", metavar="LAT,LON")
    p.add_argument("--band", nargs=2, type=float, default=(10.0, 50.0),
                   metavar=("MIN_M", "MAX_M"),
                   help="the band the pavement's OWN level is read in "
                        "(default 10 50, constraints/pads' own)")
    p.set_defaults(fn=cmd_pads)
    p = sub.add_parser("transect")
    p.add_argument("pkl", type=Path)
    p.add_argument("--to", required=True, metavar="LAT,LON")
    p.add_argument("--from-ref", required=True, dest="from_ref")
    p.add_argument("--step", type=float, default=1.0, metavar="M")
    p.set_defaults(fn=cmd_transect)
    p = sub.add_parser("delta")
    p.add_argument("a", type=Path)
    p.add_argument("b", type=Path)
    p.add_argument("--role", default="building")
    p.add_argument("--materiality", type=float, default=0.05, metavar="M")
    p.set_defaults(fn=cmd_delta)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
