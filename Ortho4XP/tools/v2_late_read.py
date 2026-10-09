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
  FOLLOW     the follow rows the solved surface misses, by neighbour kind,
             each classed DECLARED (the stage refused that ring's bound: a
             merged station, or the other group's ring across a knife —
             the stage's own record, ``late_declared``) or OWN-GROUP (the
             bar), by part / ribbon and under / over the terrace floor;
             the lot rows the stage minted.
  STAND-OFF  per (piece, standing neighbour) the level difference across the
             stand-off beyond cap x distance — the stepping pairs.
  RIBBONS    per follower ribbon the worst offset to a fixed vertex within
             6 m over the vertices BOTH maps carry, base against arm (a new
             vertex's offset is printed apart), and for one that GREW: a
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
# The console is UTF-8 before anything prints (twin:
# ``tests/test_console_encoding.py``): ONE derivation, the engine's own.
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

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
        self.dem = a["airport"].dem
        self.free, self.frep = late_followers(self.pa)
        ident = float(self.law.tables.emit.identity.min_distinct_spacing_m)
        self.fixed, self.jrep = late_fixed(self.pb, self.zb, self.pa, self.free, ident)
        self.jrep["rim"] = late_rim_levels(self.pb, self.zb, self.pa, self.fixed,
                                           self.free, ident * 0.02)
        from auto_patch_v2.pipeline.late_stage import BEHIND_STEP
        rows, self.grep = gap_follow_rows(self.pa, self.law, self.fixed,
                                          behind_step=BEHIND_STEP)
        from auto_patch_v2.constraints.gap_follow import RULING as _FOLLOW
        from auto_patch_v2.constraints.gap_follow import LOT_RULING as _LOT
        # the follow rows over EVERY ring within reach (no part narrowing):
        # what the surface is read against.  Which of those bounds the stage
        # refused is the stage's own record (spec §55 (2) 5), never re-derived
        self.rows = [r for r in rows if r.source.ruling == _FOLLOW]
        self.declared = (None if "late_declared" not in a else
                         {(int(d["v"]), d["ring"]) for d in a["late_declared"]})
        # the lot rows the STAGE minted (§55 (3) 4: road+apron parts only);
        # an arm that predates the record is read against every lot's
        minted = [r for r in self.cs.rows() if r.source.ruling == _LOT]
        self.lot_rows = minted if self.declared is not None else \
            [r for r in rows if r.source.ruling == _LOT]
        # spec §55: the cut's own report (parts, knives, the stations the
        # floors merged) travels in the arm's pickle
        self.cut = a.get("late_cut") or {}
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
        from auto_patch_v2.model.planar import gap_follower_faces
        gap, rib = gap_follower_faces(self.pa)
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
    foreign = sorted(j for j in V if j not in L.fixed and j not in L.free)  # noqa: E501
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


def merged_stations(L: Late) -> list[dict]:
    """The stations the cut's floors merged away (spec §55 (2) 3), each with
    its piece: the ONLY stations a follow row may lawfully miss."""
    return [{**m, "piece": pc["ref"]} for pc in L.cut.get("pieces", ())
            for m in pc.get("conflicts_merged", ())]


def read_follow(L: Late, top: int = 20, out=print) -> dict:
    """The follow rows the solved surface misses, by the neighbour's kind,
    each classed (spec §55 (7), (14)): DECLARED — the stage refused the
    bound of that ring on that vertex (a station the floors merged, or the
    other group's ring across a knife: ``L.declared``, the stage's record)
    — or OWN-GROUP, the bar, counted by where it stands (a part / a ribbon)
    and against the terrace floor.  An arm with no such record
    (``L.declared is None``) is classed by the merged stations' rings near
    the vertex.  Then the lot rows the stage minted (§55 (3) 4)."""
    import math
    from auto_patch_v2.constraints.gap_follow import reach_m

    def kind(n: str) -> str:
        return ("pad" if n.startswith("building") else
                "apron" if n.startswith("apron") else "other")
    near = reach_m(L.law) + float(L.law.tables.emit.chords.station_spacing_m)
    floor = float(L.law.tables.emit.terrace.pad_terrace_floor_m)
    by_ring: dict = collections.defaultdict(list)
    for m in merged_stations(L):
        by_ring[m["ring"]].append(m)
    miss: collections.Counter = collections.Counter()
    cv = {c["v"] for c in L.grep["conflicts"]}
    named, own = [], []
    for r in L.rows:
        v = r.terms[0][0]
        z = float(L.za[v])
        over = max(z - r.hi, r.lo - z)
        nb = r.source.inputs[1] if z > r.hi else r.source.inputs[0]
        if over <= TOL_M:
            continue
        miss[kind(nb)] += 1
        miss["at a conflict vertex"] += int(v in cv)
        xy = L.pa.vertices[v].xy
        st = min((m for n in set(r.source.inputs) for m in by_ring.get(n, ())),
                 key=lambda m: math.dist(m["xy"], xy), default=None)
        if st is not None and math.dist(st["xy"], xy) > near:
            st = None
        if L.declared is None:
            declared = st is not None
        else:
            declared = any((v, n) in L.declared for n in r.source.inputs)
        (named if declared else own).append((over, v, nb, st))
    where: collections.Counter = collections.Counter()
    for over, v, _nb, _st in own:
        on_part = any("gap:" in x for x in L.names(v))
        where[("part" if on_part else "ribbon") + (" <= floor" if over <= floor else " > floor")] += 1
    n = len(named) + len(own)
    out(f"[{L.icao}] FOLLOW rows {len(L.rows)}; missed by > {TOL_M} m: {n} "
        f"{dict(miss)}; conflict vertices {len(cv)}; DECLARED "
        f"{'(merged station or the other group across a knife)' if L.declared is not None else '(near a merged station)'}"
        f" {len(named)}, OWN-GROUP {len(own)} (the bar: 0) {dict(sorted(where.items()))}"
        f" worst {max((o[0] for o in own), default=0.0):.2f} m")
    for label, recs in (("OWN-GROUP", own), ("declared", named)):
        for over, v, nb, st in sorted(recs, key=lambda t: -t[0])[:top]:
            faces = [x for x in L.names(v) if "gap:" in x or "small_roads" in x or "big_roads" in x]
            out(f"    {label} {over:.2f} m at v{v} {L.ll(v)} z {float(L.za[v]):.2f} vs {nb}"
                f" on {faces[:2]}"
                + (f"; merged station {st['ring']} {st['z']:.2f} of {st['piece']} group "
                   f"{st['group']} -> {st.get('into_group')}" if st is not None else ""))
    lot_miss = []
    for r in L.lot_rows:
        v = r.terms[0][0]
        over = max(float(L.za[v]) - r.hi, r.lo - float(L.za[v]))
        if over > TOL_M:
            lot_miss.append((over, v, r.source.inputs[0]))
    lot_parts = sorted({x.split(":", 1)[1] for r in L.lot_rows for x in L.names(r.terms[0][0])
                        if "gap:" in x and "/lot" in x})
    out(f"[{L.icao}] LOT rows {len(L.lot_rows)} on {len(lot_parts)} parts {lot_parts[:8]}; "
        f"missed by > {TOL_M} m: {len(lot_miss)}"
        + "".join(f"\n    {o:.2f} m at v{v} {L.ll(v)} vs {nb} on "
                  f"{[x for x in L.names(v) if 'gap:' in x][:2]}"
                  for o, v, nb in sorted(lot_miss, reverse=True)[:top]))
    return {"rows": len(L.rows), "missed": n, "by_kind": dict(miss),
            "conflict_vertices": len(cv), "missed_declared": len(named),
            "missed_own_group": len(own), "own_group_where": dict(where),
            "own_group_worst_m": round(max((o[0] for o in own), default=0.0), 3),
            "lot_rows": len(L.lot_rows), "lot_parts": lot_parts,
            "lot_missed": len(lot_miss)}


def read_knives(L: Late, top: int = 20, out=print) -> dict:
    """THE KNIVES (spec §55 (2) 4): every two parts of one piece whose rims
    stand within the gap-joint horizon of each other without touching — the
    declared steps — with the worst level difference rim to rim."""
    import shapely
    from shapely.strtree import STRtree
    from auto_patch_v2.model.planar import face_vertex_set, is_gap_ref
    tol = float(L.law.tables.emit.instrument.step_contact_tol_m)
    parts: dict = collections.defaultdict(set)
    for f in L.pa.faces.values():
        if is_gap_ref(f.ref) and "/" in str(f.ref):
            parts[str(f.ref).split("#")[0]] |= set(face_vertex_set(L.pa, f))
    refs = sorted(parts)
    V = L.pa.vertices
    pts = {r: shapely.multipoints([V[v].xy for v in sorted(parts[r])]) for r in refs}
    tree = STRtree([pts[r] for r in refs])
    pairs: dict = {}
    for i, r in enumerate(refs):
        for k in tree.query(pts[r], predicate="dwithin", distance=tol).tolist():
            q = refs[k]
            if k <= i or q.split("/")[0] != r.split("/")[0] or parts[r] & parts[q]:
                continue
            a = sorted(parts[r])
            b = sorted(parts[q])
            ta = STRtree(shapely.points([V[v].xy for v in b]))
            ia, ib = ta.query_nearest(shapely.points([V[v].xy for v in a]),
                                      max_distance=tol)
            best = max(((abs(float(L.za[a[x]]) - float(L.za[b[y]])), a[x])
                        for x, y in zip(ia.tolist(), ib.tolist())), default=None)
            if best is not None:
                pairs[(r, q)] = best
    out(f"[{L.icao}] KNIVES (the cut reports {L.cut.get('knives', '?')}): {len(pairs)} part "
        f"pairs within {tol:.1f} m; worst rim-to-rim level difference "
        f"{max((b[0] for b in pairs.values()), default=0.0):.2f} m")
    for (r, q), (dz, v) in sorted(pairs.items(), key=lambda kv: -kv[1][0])[:top]:
        out(f"    {r} | {q}: {dz:.2f} m at {L.ll(v)}")
    return {"pairs": len(pairs), "worst_m": max((b[0] for b in pairs.values()), default=0.0)}


def standoff_pairs(L: Late) -> dict:
    """Per (piece, standing neighbour): the worst level difference across
    the stand-off beyond the piece's cap over the distance —
    ``{"worst": {(piece, neighbour): (excess, d, ll, z_piece, z_neighbour)},
    "area": {piece: m2}, "stand": m, "cap": slope, "step": m}`` (a pair
    STEPS when its excess is over ``step``); empty with no gap piece."""
    import shapely
    from shapely.strtree import STRtree
    from auto_patch_v2.classify.gap_mint import standoff_m
    from auto_patch_v2.law.tables import role_cap
    from auto_patch_v2.model.planar import face_edge_ids, face_vertex_set, is_gap_ref
    V, za = L.pa.vertices, L.za
    gap = [f for f in L.pa.faces.values() if is_gap_ref(f.ref)]
    if not gap:
        return {}
    stand = standoff_m(L.law)
    cap = float(role_cap(L.law, gap[0].role).longitudinal)
    step = cap * stand
    segs, segz, segref = [], [], []
    follower = {f.id for f in L.follower_faces()}
    for f in L.pa.faces.values():
        if is_gap_ref(f.ref) or f.id in follower:
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
    return {"worst": worst, "area": area, "stand": stand, "cap": cap, "step": step}


def read_standoff(L: Late, top: int, out=print) -> dict:
    """The stepping pairs of ``standoff_pairs``, worst first."""
    sp = standoff_pairs(L)
    if not sp:
        out(f"[{L.icao}] STAND-OFF: no gap piece")
        return {}
    worst, area, stand, cap, step = (sp[k] for k in ("worst", "area", "stand", "cap", "step"))
    over = {k: w for k, w in worst.items() if w[0] > step}
    piece_m2: dict = collections.defaultdict(float)     # a part's PIECE (spec §55)
    for ref, m2 in area.items():
        piece_m2[ref.split("/")[0]] += m2
    big = sum(1 for (ref, _n) in over if piece_m2[ref.split("/")[0]] >= 1000.0)
    # A MERGED-SLIVER STEP (spec §55 (14) residual 3): the neighbour's own
    # group held only a sliver under the floors beside it; the floors merged
    # it into this part and the terrace stands at the neighbour's foot — the
    # cut's own merged-station record names it
    sliver = {(m["piece"], m["ring"]): m for m in merged_stations(L)}
    named = {k: sliver[(k[0].split("/")[0], k[1])] for k in over
             if (k[0].split("/")[0], k[1]) in sliver}
    out(f"[{L.icao}] STAND-OFF ({stand:.2f} m, cap {100 * cap:.0f} %): stepping pairs "
        f"{len(over)} of {len(worst)}; on pieces >= 1,000 m2: {big}; at a merged "
        f"station's ring (a MERGED-SLIVER step, declared by the cut): {len(named)}")
    for (ref, nb), w in sorted(over.items(), key=lambda kv: -kv[1][0])[:top]:
        m = named.get((ref, nb))
        out(f"    {ref} ({area[ref]:,.0f} m2) | {nb}: {w[0]:.2f} m (piece {w[3]:.2f} vs "
            f"{w[4]:.2f}, {w[1]:.2f} m apart) at {w[2]}"
            + (f"  MERGED-SLIVER: station {m['ring']} {m['z']:.2f}, group "
               f"{m['group']} -> {m.get('into_group')}" if m else ""))
    return {"pairs": len(worst), "stepping": len(over), "stepping_big": big,
            "stepping_merged_sliver": len(named)}


def read_ribbons(L: Late, top: int, refs: list[str], out=print) -> dict:
    """Per follower ribbon the worst offset to a fixed vertex within
    ``RIBBON_NEIGHBOUR_M``, base against arm; for a ribbon that grew, what
    its follow rows say."""
    import numpy as np
    from scipy.spatial import cKDTree
    from auto_patch_v2.law.tables import role_cap
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
        # THE SAME VERTICES in both arms: a ribbon vertex the base map
        # lacks has no "before", and counting it made a ribbon that moved
        # TOWARD its neighbour read as grown
        aft, bef, new = [], [], []
        for v in vs:
            d, k = kd.query(V[v].xy, distance_upper_bound=RIBBON_NEIGHBOUR_M)
            if np.isfinite(d) and d > 0.05:
                rec = (abs(float(za[v]) - fz[k]), v, ids[k], float(d))
                if tuple(V[v].xy) in bz:
                    aft.append(rec)
                    bef.append(abs(bz[tuple(V[v].xy)] - fz[k]))
                else:
                    new.append(rec)
        mv = max((abs(float(za[v]) - bz[tuple(V[v].xy)]) for v in vs
                  if tuple(V[v].xy) in bz), default=0.0)
        if aft:
            tab.append({"ref": ref, "after": max(aft)[0], "at": max(aft),
                        "before": max(bef) if bef else float("nan"),
                        "new_worst": max(new)[0] if new else 0.0,
                        "moved": mv, "vertices": vs})
    tab.sort(key=lambda t: -t["after"])
    grew = [t for t in tab if t["after"] > t["before"] + GREW_M and t["moved"] > TOL_M]
    out(f"[{L.icao}] RIBBONS: {len(rib)} follower refs, {len(tab)} with a fixed vertex "
        f"within {RIBBON_NEIGHBOUR_M:g} m; worst offset GREW by > {GREW_M} m: {len(grew)}")
    res = {"follower_refs": len(rib), "grew": []}
    shown = grew + [t for t in tab if t["ref"] in refs and t not in grew]
    for t in shown:
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
        # an offset to a vertex ``d`` metres off within the road cap is a
        # SLOPE, not a lift: say so before anything else
        cap_r = float(role_cap(L.law, "service_road").longitudinal)
        grade = _off / d if d else float("inf")
        what = (f"{100 * grade:.1f} % over {d:.2f} m "
                + ("(WITHIN the road cap: a slope, not a lift); "
                   if _off <= cap_r * d + TOL_M else "(OVER the road cap); ")) + what
        rec = {"ref": t["ref"], "before": round(t["before"], 2), "after": round(t["after"], 2),
               "grade": round(grade, 4), "within_cap": _off <= cap_r * d + TOL_M,
               "moved": round(t["moved"], 2), "unknown": len(unknown), "rowed": len(rowed),
               "missed": len(missed), "what": what, "at": L.ll(v)}
        res["grew"].append(rec)
        out(f"    {t['ref']:<22} {t['before']:.2f} -> {t['after']:.2f} m (moved {t['moved']:.2f}; "
            f"new vertices' worst {t['new_worst']:.2f}); "
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
    ap.add_argument("--site", nargs="+", action="append", default=[],
                    metavar="NAME LAT LON [TO_LAT TO_LON]",
                    help="read a PLACE instead of the bars (v2_late_site.py): the "
                         "face and piece at the point, its neighbours and their "
                         "levels, and sections on both arms against the DEM")
    ap.add_argument("--half", type=float, default=40.0, help="section half length, m")
    ap.add_argument("--step", type=float, default=1.0, help="section sample step, m")
    a = ap.parse_args(argv)
    L = Late(a.base, a.arm)
    if a.site:
        from v2_late_site import read_sites
        res = read_sites(L, a.site, a.half, a.step)
        if a.json:
            a.json.write_text(json.dumps(res, indent=1, default=str),
                              encoding="utf-8", newline="\n")
        return 0
    res = {"join": read_join(L, a.top), "follow": read_follow(L, a.top),
           "standoff": read_standoff(L, a.top), "knives": read_knives(L, a.top),
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
