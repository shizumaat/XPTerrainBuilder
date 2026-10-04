#!/usr/bin/env python3
"""THE LAST STAGE READ AGAINST ITS BASE (spec §53): what a ``--late-from``
arm did to the standing ground, from the two ``--solved-out`` pickles.

    venv/bin/python tools/v2_late_read.py BASE/solved.pkl ARM/solved.pkl
        [--patches BASE.osm ARM.osm] [--ribbon REF ...] [--top N] [--json OUT]

It MEASURES NO LAW: every set is the engine's own (``pipeline/stage_one_map``
for the followers, the constants and the rim nodes; ``constraints/gap_follow``
for the follow rows; ``airside_value_delta.read_refs`` for a patch's way
groups).  Sections:

  JOIN       followers, constants, rim nodes; every FOREIGN vertex (on a
             standing face, in neither set, on no base edge) with its faces,
             the nearest base vertex / edge and the nearest follower face.
  FOLLOW     the follow rows the solved surface misses, by neighbour kind.
  STAND-OFF  per (piece, standing neighbour) the level difference across the
             stand-off beyond cap x distance — the stepping pairs.
  RIBBONS    per follower ribbon the worst offset to a fixed vertex within
             6 m, base against arm, and for one that GREW what holds it: a
             missed follow row, no follow row at all (no fixed ring within
             reach), or rows met (a span between two neighbours).
  GROUPS     (``--patches``) every standing ``(role, ref)`` way group of the
             base patch: identical in the arm in nodes AND levels, or named.

Promoted from lane gaps292's scratch ``r7_read.py`` / ``r11_read.py`` /
``ribbon_rows.py`` on their third use (lane gaps2, 2026-10-04)."""
from __future__ import annotations

import argparse
import collections
import json
import math
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]

#: metres: a moved level / a missed row (the lane's read tolerance)
TOL_M = 0.02
#: metres: a fixed vertex this near a ribbon vertex is its neighbour
RIBBON_NEIGHBOUR_M = 6.0
#: metres a ribbon's worst offset must grow by to be residue
GREW_M = 0.1


def _name(f) -> str:
    return f"{f.role}:{str(f.ref).split('#')[0]}"


class Late:
    """The two solved sets and the last stage's own derivation over them."""

    def __init__(self, base_pkl: Path, arm_pkl: Path) -> None:
        from auto_patch_v2.constraints.gap_follow import gap_follow_rows
        from auto_patch_v2.law import Law
        from auto_patch_v2.model.planar import face_vertex_set
        from auto_patch_v2.pipeline.stage_one_map import (late_fixed,
                                                          late_followers,
                                                          late_rim_levels)
        with open(base_pkl, "rb") as fh:
            b = pickle.load(fh)
        with open(arm_pkl, "rb") as fh:
            a = pickle.load(fh)
        self.icao = a["icao"]
        self.law = Law.for_airport(self.icao)
        self.pa, self.za, self.pb, self.zb = a["pm"], a["z"], b["pm"], b["z"]
        self.cs = a["cs"]
        self.to_xy, self.to_ll = a["airport"].frame.transformers()
        self.free, self.frep = late_followers(self.pa)
        self.fixed, self.jrep = late_fixed(self.pb, self.zb, self.pa, self.free)
        ident = float(self.law.tables.emit.identity.min_distinct_spacing_m)
        self.jrep["rim"] = late_rim_levels(self.pb, self.zb, self.pa, self.fixed,
                                           self.free, ident * 0.02)
        self.rows, self.grep = gap_follow_rows(self.pa, self.law, self.fixed)
        self.faces_of: dict[int, set] = collections.defaultdict(set)
        for f in self.pa.faces.values():
            for v in face_vertex_set(self.pa, f):
                self.faces_of[int(v)].add(f.id)
        self.base_at = {tuple(v.xy): i for i, v in self.pb.vertices.items()}

    def ll(self, v: int) -> str:
        la, lo = self.to_ll(*self.pa.vertices[v].xy)
        return f"{la:.7f},{lo:.7f}"

    def names(self, v: int) -> list[str]:
        return sorted({_name(self.pa.faces[i]) for i in self.faces_of[v]})

    def follower_faces(self) -> list:
        from auto_patch_v2.model.planar import (face_edge_ids, is_gap_ref,
                                                is_osm_ribbon_ref)
        gap = [f for f in self.pa.faces.values() if is_gap_ref(f.ref)]
        ge = set().union(*[face_edge_ids(f) for f in gap]) if gap else set()
        rib = [f for f in self.pa.faces.values()
               if f.role == "service_road" and is_osm_ribbon_ref(f.ref)
               and face_edge_ids(f) & ge]
        return [*gap, *rib]


def _poly(pm, f):
    from shapely.geometry import Polygon
    V = pm.vertices
    try:
        p = Polygon([V[v].xy for v in pm.ring_vertices(f.ring)],
                    [[V[v].xy for v in pm.ring_vertices(h)] for h in (f.holes or ())])
        return p if p.is_valid else p.buffer(0)
    except Exception:  # noqa: BLE001 — a degenerate ring has no polygon
        return None


def read_join(L: Late, top: int, out=print) -> dict:
    """The foreign vertices, each with what it is and what is beside it."""
    import shapely
    from shapely.strtree import STRtree
    V = L.pa.vertices
    foreign = sorted(j for j in V if j not in L.fixed and j not in L.free)
    off = [abs(float(L.za[v]) - z) for v, z in L.fixed.items()]
    out(f"[{L.icao}] JOIN: followers "
        f"{ {k: v for k, v in L.frep.items() if k != 'follower_ribbon_refs'} }; {L.jrep}")
    out(f"[{L.icao}] fixed vertices off their constant by > {TOL_M} m: "
        f"{sum(1 for d in off if d > TOL_M)} of {len(off)} (worst {max(off, default=0.0):.3f} m)")
    by = collections.Counter(n for j in foreign for n in L.names(j)
                             if not n.split(":", 1)[1].startswith("gap:"))
    out(f"[{L.icao}] FOREIGN vertices on standing faces: {len(foreign)}; "
        f"by standing face: {by.most_common(8)}")
    res = {"foreign": len(foreign), "by_face": dict(by), "list": []}
    if not foreign:
        return res
    bv = L.pb.vertices
    bedges = list(L.pb.edges.values())
    blines = shapely.linestrings([[bv[e.a].xy, bv[e.b].xy] for e in bedges])
    btree = STRtree(blines)
    fol = L.follower_faces()
    fpoly = [(f, _poly(L.pa, f)) for f in fol]
    fpoly = [(f, p) for f, p in fpoly if p is not None]
    ftree = STRtree([p for _f, p in fpoly])
    bfaces = collections.defaultdict(set)
    from auto_patch_v2.model.planar import face_vertex_set
    for f in L.pb.faces.values():
        bfaces[_name(f)] |= {tuple(bv[v].xy) for v in face_vertex_set(L.pb, f)}
    for j in foreign[:top]:
        pt = shapely.points(V[j].xy)
        k = int(btree.nearest(pt))
        d_edge = float(shapely.distance(blines[k], pt))
        e = bedges[k]
        e_faces = sorted({_name(L.pb.faces[i]) for i in
                          (e.left_face, e.right_face)
                          if i is not None and i in L.pb.faces})
        kf = int(ftree.nearest(pt))
        d_fol = float(shapely.distance(fpoly[kf][1], pt))
        rec = {"v": j, "ll": L.ll(j), "faces": L.names(j), "z": round(float(L.za[j]), 3),
               "base_edge_m": round(d_edge, 4), "base_edge_faces": e_faces,
               "follower": _name(fpoly[kf][0]), "follower_m": round(d_fol, 3)}
        res["list"].append(rec)
        out(f"    v{j} {rec['ll']} z {rec['z']:.2f} on {rec['faces']}; nearest base "
            f"edge {d_edge:.3f} m {e_faces}; nearest follower {rec['follower']} "
            f"{d_fol:.2f} m")
    return res


def read_follow(L: Late, out=print) -> dict:
    """The follow rows the solved surface misses, by the neighbour's kind."""
    def kind(n: str) -> str:
        return ("pad" if n.startswith("building") else
                "apron" if n.startswith("apron") else "other")
    miss: collections.Counter = collections.Counter()
    tot: collections.Counter = collections.Counter()
    cv = {c["v"] for c in L.grep["conflicts"]}
    worst = (0.0, None, "")
    for r in L.rows:
        v = r.terms[0][0]
        z = float(L.za[v])
        over = max(z - r.hi, r.lo - z)
        nb = r.source.inputs[1] if z > r.hi else r.source.inputs[0]
        tot[kind(nb)] += 1
        if over > TOL_M:
            miss[kind(nb)] += 1
            miss["at a conflict vertex"] += int(v in cv)
            if over > worst[0]:
                worst = (over, v, nb)
    n = sum(v for k, v in miss.items() if k != "at a conflict vertex")
    out(f"[{L.icao}] FOLLOW rows {len(L.rows)}; missed by > {TOL_M} m: {n} "
        f"{dict(miss)}; conflict vertices {len(cv)}"
        + (f"; worst {worst[0]:.2f} m at v{worst[1]} {L.ll(worst[1])} vs {worst[2]}"
           if worst[1] is not None else ""))
    return {"rows": len(L.rows), "missed": n, "by_kind": dict(miss),
            "conflict_vertices": len(cv)}


def read_standoff(L: Late, top: int, out=print) -> dict:
    """Per (piece, standing neighbour): the worst level difference across
    the stand-off beyond the piece's cap over the distance."""
    import shapely
    from shapely.strtree import STRtree
    from auto_patch_v2.classify.gap_mint import standoff_m
    from auto_patch_v2.law.tables import role_cap
    from auto_patch_v2.model.planar import (face_edge_ids, face_vertex_set,
                                            is_gap_ref, is_osm_ribbon_ref)
    V, za = L.pa.vertices, L.za
    gap = [f for f in L.pa.faces.values() if is_gap_ref(f.ref)]
    if not gap:
        out(f"[{L.icao}] STAND-OFF: no gap piece")
        return {}
    stand = standoff_m(L.law)
    cap = float(role_cap(L.law, gap[0].role).longitudinal)
    step = cap * stand
    segs, segz, segref = [], [], []
    for f in L.pa.faces.values():
        if is_gap_ref(f.ref) or (f.role == "service_road" and is_osm_ribbon_ref(f.ref)):
            continue
        for e in face_edge_ids(f):
            ed = L.pa.edges[e]
            segs.append([V[ed.a].xy, V[ed.b].xy])
            segz.append((float(za[ed.a]), float(za[ed.b])))
            segref.append(_name(f))
    lines = shapely.linestrings(segs)
    tree = STRtree(lines)
    area: dict = collections.defaultdict(float)
    worst: dict = {}
    for f in gap:
        ref = str(f.ref).split("#")[0]
        p = _poly(L.pa, f)
        if p is not None:
            area[ref] += p.area
        for v in face_vertex_set(L.pa, f):
            if v in L.fixed:
                continue
            pt = shapely.points(V[v].xy)
            for k in tree.query(pt, predicate="dwithin", distance=stand + 0.6):
                k = int(k)
                d = float(shapely.distance(lines[k], pt))
                if d < 0.3:
                    continue                 # a shared rim is not a stand-off
                length = float(shapely.length(lines[k]))
                t = float(shapely.line_locate_point(lines[k], pt)) / length if length else 0.0
                zs = (1 - t) * segz[k][0] + t * segz[k][1]
                dz = abs(float(za[v]) - zs) - cap * d + step
                key = (ref, segref[k])
                if key not in worst or dz > worst[key][0]:
                    worst[key] = (dz, d, L.ll(v), float(za[v]), zs)
    over = {k: w for k, w in worst.items() if w[0] > step}
    big = sum(1 for (ref, _n) in over if area[ref] >= 1000.0)
    out(f"[{L.icao}] STAND-OFF ({stand:.2f} m, cap {100 * cap:.0f} %): stepping pairs "
        f"{len(over)} of {len(worst)}; on pieces >= 1,000 m2: {big}")
    for (ref, nb), w in sorted(over.items(), key=lambda kv: -kv[1][0])[:top]:
        out(f"    {ref} ({area[ref]:,.0f} m2) | {nb}: {w[0]:.2f} m (piece {w[3]:.2f} vs "
            f"{w[4]:.2f}, {w[1]:.2f} m apart) at {w[2]}")
    return {"pairs": len(worst), "stepping": len(over), "stepping_big": big}


def read_ribbons(L: Late, top: int, refs: list[str], out=print) -> dict:
    """Per follower ribbon the worst offset to a fixed vertex within
    ``RIBBON_NEIGHBOUR_M``, base against arm; for a ribbon that grew, what
    its follow rows say."""
    import numpy as np
    from scipy.spatial import cKDTree
    from auto_patch_v2.model.planar import (face_vertex_set, is_osm_ribbon_ref)
    V, za = L.pa.vertices, L.za
    ids = sorted(L.fixed)
    kd = cKDTree(np.array([V[j].xy for j in ids]))
    fz = np.array([float(za[j]) for j in ids])
    bz = {xy: float(L.zb[i]) for xy, i in L.base_at.items()}
    row_of = {r.terms[0][0]: r for r in L.rows}
    rib: dict = collections.defaultdict(set)
    for f in L.follower_faces():
        if is_osm_ribbon_ref(f.ref):
            rib[str(f.ref)] |= set(face_vertex_set(L.pa, f))
    tab = []
    for ref, vs in rib.items():
        aft, bef = [], []
        for v in vs:
            d, k = kd.query(V[v].xy, distance_upper_bound=RIBBON_NEIGHBOUR_M)
            if np.isfinite(d) and d > 0.05:
                aft.append((abs(float(za[v]) - fz[k]), v, ids[k], float(d)))
                if tuple(V[v].xy) in bz:
                    bef.append(abs(bz[tuple(V[v].xy)] - fz[k]))
        mv = max((abs(float(za[v]) - bz[tuple(V[v].xy)]) for v in vs
                  if tuple(V[v].xy) in bz), default=0.0)
        if aft:
            tab.append({"ref": ref, "after": max(aft)[0], "at": max(aft),
                        "before": max(bef) if bef else float("nan"),
                        "moved": mv, "vertices": vs})
    tab.sort(key=lambda t: -t["after"])
    grew = [t for t in tab if t["after"] > t["before"] + GREW_M and t["moved"] > TOL_M]
    out(f"[{L.icao}] RIBBONS: {len(rib)} follower refs, {len(tab)} with a fixed vertex "
        f"within {RIBBON_NEIGHBOUR_M:g} m; worst offset GREW by > {GREW_M} m: {len(grew)}")
    res = {"follower_refs": len(rib), "grew": []}
    shown = grew + [t for t in tab if t["ref"] in refs and t not in grew]
    for t in shown[:max(top, len(grew))]:
        vs = t["vertices"]
        unknown = [v for v in vs if v not in L.fixed]
        rowed = [v for v in unknown if v in row_of]
        missed = [v for v in rowed
                  if max(float(za[v]) - row_of[v].hi, row_of[v].lo - float(za[v])) > TOL_M]
        _off, v, k, d = t["at"]
        r = row_of.get(v)
        if v in L.fixed:
            what = "the worst vertex is itself a CONSTANT (the offset is the base's)"
        elif r is None:
            what = (f"NO follow row on the worst vertex (no fixed ring within reach; "
                    f"its fixed neighbour is a vertex {d:.2f} m off: {L.names(k)})")
        elif max(float(za[v]) - r.hi, r.lo - float(za[v])) > TOL_M:
            what = (f"its follow row [{r.lo:.2f}, {r.hi:.2f}] {r.source.inputs} is MISSED "
                    f"(relaxed)")
        else:
            what = (f"its follow row [{r.lo:.2f}, {r.hi:.2f}] {r.source.inputs} is MET; "
                    f"the neighbour {L.names(k)} at {fz[ids.index(k)]:.2f} is not one of its rings")
        rec = {"ref": t["ref"], "before": round(t["before"], 2), "after": round(t["after"], 2),
               "moved": round(t["moved"], 2), "unknown": len(unknown), "rowed": len(rowed),
               "missed": len(missed), "what": what, "at": L.ll(v)}
        res["grew"].append(rec)
        out(f"    {t['ref']:<22} {t['before']:.2f} -> {t['after']:.2f} m (moved {t['moved']:.2f}); "
            f"{len(vs)} vertices, {len(unknown)} unknown, {len(rowed)} with a follow row, "
            f"{len(missed)} missed; v{v} z {float(za[v]):.2f} at {L.ll(v)}: {what}")
    return res


def read_groups(base_osm: Path, arm_osm: Path, top: int,
                followers: frozenset[str] = frozenset(), out=print) -> dict:
    """Every ``(role, ref)`` way group of the base patch against the arm's:
    the same node set (11-dp lat/lon) and the same levels.  A group whose
    ref is one of ``followers`` (the follower ribbons) is the last stage's
    own and is counted apart: the bar is on the STANDING groups."""
    from airside_value_delta import read_refs
    A, B = read_refs(base_osm), read_refs(arm_osm)
    same, diff = 0, []
    for k, na in A.items():
        nb = B.get(k)
        if nb is None:
            diff.append((k, "absent in the arm", 0, 0, 0.0))
            continue
        only_a, only_b = set(na) - set(nb), set(nb) - set(na)
        mv = max((abs(nb[c] - z) for c, z in na.items() if c in nb), default=0.0)
        if only_a or only_b or mv > TOL_M:
            diff.append((k, "", len(only_a), len(only_b), mv))
        else:
            same += 1
    new = [k for k in B if k not in A]
    fol = [d for d in diff if d[0][1].split("#")[0] in followers]
    standing = [d for d in diff if d not in fol]
    n_fol = sum(1 for k in A if k[1].split("#")[0] in followers)
    out(f"WAY GROUPS: STANDING {len(A) - n_fol - len(standing)} of {len(A) - n_fol} base "
        f"(role, ref) groups identical in the arm (nodes and levels at {TOL_M} m), "
        f"{len(standing)} differ; follower ribbons {n_fol - len(fol)} of {n_fol} identical; "
        f"{len(new)} groups only in the arm")
    for k, note, oa, ob, mv in sorted(standing, key=lambda d: -d[4])[:top]:
        out(f"    {k[0]}:{k[1]} {note} nodes only in base {oa}, only in arm {ob}, "
            f"worst level move {mv:.2f} m")
    return {"identical": same, "base_groups": len(A), "standing_differ": len(standing),
            "differ": [{"role": k[0], "ref": k[1], "only_base": oa, "only_arm": ob,
                        "moved_m": round(mv, 3),
                        "follower": k[1].split("#")[0] in followers}
                       for k, _n, oa, ob, mv in diff]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("base", type=Path, help="the base arm's --solved-out pickle")
    ap.add_argument("arm", type=Path, help="the --late-from arm's --solved-out pickle")
    ap.add_argument("--patches", nargs=2, type=Path, metavar=("BASE.osm", "ARM.osm"))
    ap.add_argument("--ribbon", action="append", default=[], metavar="REF")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    L = Late(a.base, a.arm)
    res = {"join": read_join(L, a.top), "follow": read_follow(L),
           "standoff": read_standoff(L, a.top),
           "ribbons": read_ribbons(L, a.top, a.ribbon)}
    if a.patches:
        res["groups"] = read_groups(
            a.patches[0], a.patches[1], a.top,
            frozenset(str(r).split("#")[0] for r in L.frep["follower_ribbon_refs"]))
    if a.json:
        a.json.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8",
                          newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
