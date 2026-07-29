"""Phase-1 probe for ``docs/specs/single-space-string-audit-spec.md``.

WHY: the §10 taut-string rod is minted in the SOLVE's node space
(``solve_route_profile``) and re-attached in ``final_grade_projection``'s
REBUILT node space by canonical-registry key.  Only ~46 % of the links
survive that transport at HECA and nobody has attributed the drops.  This
module measures — it changes no law.

WHAT IT MEASURES
  * mint: every rod link's two endpoint canonical keys, their mint-time
    coordinates, the corridor piece they belong to, and whether the link
    is a SERVICE spine pair (``UnifiedGraph.service_spine_pairs``);
  * checkpoints: after each named post-solve pipeline pass, whether each
    watched key still RESOLVES (some admitted ring vertex would intern to
    exactly that canonical point) and, if not, the nearest ring vertex and
    its distance — so the first checkpoint that loses a key NAMES the pass;
  * carry: at the re-attach site, for every DROPPED link, which endpoint(s)
    failed, and the spec §2.3 verdict per failed endpoint —
    RE-KEYED (a rebuilt vertex within 1 mm of the mint coordinate: same
    physical point, different registry identity) vs MOVED (nearest rebuilt
    vertex is further than that; the distance is reported).

GATE: ``O4_ROD_CARRY_AUDIT=1``.  Default OFF and every entry point returns
before touching anything, so a default build is byte-identical.  The audit
NEVER calls ``registry.get_or_add`` (which would add canonical points and
perturb the very pipeline it measures) — only the read-only
``registry.find_nearest``.

Output: the report is printed (build log) and written as JSON to
``O4_ROD_CARRY_AUDIT_OUT`` (default ``/tmp/rod_carry_audit_<icao>.json``).
"""
from __future__ import annotations

import json
import math
import os

__all__ = ["enabled", "record_mint", "checkpoint", "report_carry"]

# Spec §2.3: "does ANY vertex exist in the rebuilt space within 1 mm of the
# mint coordinate?"  YES -> RE-KEYED, NO -> MOVED.
REKEY_TOL_M = 0.001


def enabled() -> bool:
    """True when the probe gate ``O4_ROD_CARRY_AUDIT=1`` is set."""
    return os.environ.get("O4_ROD_CARRY_AUDIT") == "1"


def _state(layout):
    return getattr(layout, "_rod_carry_audit", None)


# ── geometry helpers ────────────────────────────────────────────────────

def _admitted_ring_vertices(layout):
    """Every ring vertex ``_build_node_list`` would admit, as ``[(x, y)]``.

    Same admission rule (PAVEMENT_ROLES + the admitted terrain ``(role,
    ref)`` families), but READ-ONLY — no registry mutation.
    """
    from .elevation_per_surface.solver_primitives import PAVEMENT_ROLES
    try:
        from .elevation_per_surface.solver_primitives import (
            admitted_terrain_refs)
        refs = admitted_terrain_refs()
    except Exception:                                      # pragma: no cover
        refs = frozenset()
    out = []
    for s in layout.shapes:
        if (s.role not in PAVEMENT_ROLES
                and (s.role, getattr(s, "ref", None)) not in refs):
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        try:
            coords = list(poly.exterior.coords)
        except Exception:                                  # pragma: no cover
            continue
        if len(coords) > 1 and coords[0] == coords[-1]:
            coords = coords[:-1]
        for (x, y) in coords:
            out.append((float(x), float(y)))
    return out


class _Index:
    """Nearest-point index over a vertex list (cKDTree, grid fallback)."""

    def __init__(self, pts):
        self.pts = pts
        self._tree = None
        self._grid = None
        if pts:
            try:
                from scipy.spatial import cKDTree
                self._tree = cKDTree(pts)
            except Exception:                              # pragma: no cover
                self._grid = {}
                for i, (x, y) in enumerate(pts):
                    self._grid.setdefault(
                        (int(math.floor(x)), int(math.floor(y))), []
                    ).append(i)

    def nearest(self, x, y):
        """``(distance, (vx, vy))`` of the nearest vertex, or ``(inf, None)``."""
        if not self.pts:
            return (float("inf"), None)
        if self._tree is not None:
            d, i = self._tree.query([x, y], k=1)
            return (float(d), self.pts[int(i)])
        best_d, best = float("inf"), None                  # pragma: no cover
        cx, cy = int(math.floor(x)), int(math.floor(y))
        for r in range(0, 64):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if r and max(abs(dx), abs(dy)) != r:
                        continue
                    for i in self._grid.get((cx + dx, cy + dy), ()):
                        px, py = self.pts[i]
                        d = math.hypot(px - x, py - y)
                        if d < best_d:
                            best_d, best = d, (px, py)
            if best is not None and best_d <= r:
                break
        return (best_d, best)

    def within(self, x, y, radius):
        """Indices of every vertex within ``radius``."""
        if not self.pts:
            return []
        if self._tree is not None:
            return list(self._tree.query_ball_point([x, y], radius))
        out = []                                           # pragma: no cover
        cx, cy = int(math.floor(x)), int(math.floor(y))
        rr = int(math.ceil(radius)) + 1
        for dx in range(-rr, rr + 1):
            for dy in range(-rr, rr + 1):
                for i in self._grid.get((cx + dx, cy + dy), ()):
                    px, py = self.pts[i]
                    if math.hypot(px - x, py - y) <= radius:
                        out.append(i)
        return out


# ── phase 1: mint ───────────────────────────────────────────────────────

def record_mint(layout, rod_edges, nodes, key_of_idx, graph=None,
                pieces=None, icao=""):
    """Record the rod links at their mint point (``solve_route_profile``).

    ``rod_edges``   ``[(ia, ib, lo, hi)]`` in SOLVE node indices;
    ``nodes``       the solve's node coordinate list;
    ``key_of_idx``  ``{node_idx: canonical_key}`` (the exported identity);
    ``graph``       the ``UnifiedGraph`` (for ``service_spine_pairs``);
    ``pieces``      the strung corridor pieces (``_rod_pieces``).
    """
    if not enabled():
        return
    svc_pairs = set(getattr(graph, "service_spine_pairs", None) or ())
    corridor_of = {}
    for ci, piece in enumerate(pieces or ()):
        for i in piece:
            corridor_of.setdefault(int(i), ci)
    keys: dict = {}
    edges: list = []
    corridor_svc: dict = {}
    for (a, b, _lo, _hi) in rod_edges:
        ka = key_of_idx.get(a)
        kb = key_of_idx.get(b)
        if ka is None or kb is None:
            continue
        pair = (a, b) if a < b else (b, a)
        svc = pair in svc_pairs
        cid = corridor_of.get(a, corridor_of.get(b, -1))
        tally = corridor_svc.setdefault(cid, [0, 0])
        tally[0 if svc else 1] += 1
        edges.append({"ka": ka, "kb": kb, "svc": svc, "corridor": cid})
        for (k, i) in ((ka, a), (kb, b)):
            rec = keys.get(k)
            if rec is None:
                xy = (nodes[i] if 0 <= i < len(nodes) else k)
                rec = keys[k] = {
                    "xy": (float(xy[0]), float(xy[1])),
                    "svc": False, "corridors": set(), "lost_at": None,
                    "lost_evidence": None,
                }
            rec["svc"] = rec["svc"] or svc
            rec["corridors"].add(cid)
    layout._rod_carry_audit = {
        "icao": icao, "keys": keys, "edges": edges,
        "corridor_svc": corridor_svc, "checkpoints": [],
    }
    print(f"    [rod-audit] mint: {len(edges)} rod link(s), "
          f"{len(keys)} unique endpoint key(s), "
          f"{sum(1 for e in edges if e['svc'])} service link(s), "
          f"{len(corridor_svc)} corridor(s)")


# ── phase 2: per-pass checkpoints ───────────────────────────────────────

def checkpoint(layout, name):
    """Probe every watched key against the CURRENT layout geometry.

    A key RESOLVES when some admitted ring vertex would intern to exactly
    that canonical point (the condition ``_build_node_list`` needs for the
    key to appear in ``bucket_to_idx``).  The first checkpoint at which a
    key stops resolving names the pass that moved or re-keyed it.
    """
    if not enabled():
        return
    st = _state(layout)
    if not st:
        return
    reg = getattr(layout, "canonical_points", None)
    tol = float(getattr(reg, "tol_m", 0.5)) if reg is not None else 0.5
    verts = _admitted_ring_vertices(layout)
    index = _Index(verts)
    keys = st["keys"]
    n_res = 0
    newly_lost = []
    prev = st["checkpoints"][-1]["resolved"] if st["checkpoints"] else None
    resolved_now = set()
    for k, rec in keys.items():
        kx, ky = float(k[0]), float(k[1])
        hit = False
        for i in index.within(kx, ky, tol):
            vx, vy = verts[i]
            if reg is None:
                hit = math.hypot(vx - kx, vy - ky) <= 1e-9
            else:
                near = reg.find_nearest(vx, vy, tol)
                hit = near is not None and near == k
            if hit:
                break
        if hit:
            n_res += 1
            resolved_now.add(k)
        elif prev is None or k in prev:
            d, nv = index.nearest(kx, ky)
            evidence = {
                "pass": name, "key": [kx, ky], "mint_xy": list(rec["xy"]),
                "nearest_xy": (list(nv) if nv else None),
                "nearest_d_m": (None if d == float("inf") else d),
                "svc": rec["svc"],
            }
            if rec["lost_at"] is None:
                rec["lost_at"] = name
                rec["lost_evidence"] = evidence
            newly_lost.append(evidence)
    st["checkpoints"].append({"name": name, "resolved": resolved_now,
                              "n_resolved": n_res,
                              "newly_lost": newly_lost})
    lost_svc = sum(1 for e in newly_lost if e["svc"])
    print(f"    [rod-audit] ckpt {name:<34s} resolved={n_res}/{len(keys)} "
          f"newly_lost={len(newly_lost)} (svc {lost_svc})")
    if newly_lost:
        for e in sorted(newly_lost,
                        key=lambda r: -(r["nearest_d_m"] or 0.0))[:5]:
            d = e["nearest_d_m"]
            nv = e["nearest_xy"]
            nv_s = "none" if nv is None else "(%.3f,%.3f)" % (nv[0], nv[1])
            d_s = "inf" if d is None else "%.4f m" % d
            tag = " [service]" if e["svc"] else ""
            print(f"        lost key ({e['key'][0]:.3f},{e['key'][1]:.3f}) "
                  f"mint ({e['mint_xy'][0]:.3f},{e['mint_xy'][1]:.3f}) "
                  f"-> nearest now {nv_s} d={d_s}{tag}")


# ── phase 3: the carry site verdict ─────────────────────────────────────

def report_carry(layout, dropped, carried, nodes, icao=""):
    """Classify every dropped rod link at ``final_grade_projection``.

    ``dropped``  ``[(ka, kb, ka_missing, kb_missing, reason)]`` — the links
                 the carry could not re-attach, which endpoint(s) failed to
                 resolve, and the drop reason;
    ``carried``  count of links that DID re-attach;
    ``nodes``    the REBUILT node coordinate list.
    """
    if not enabled():
        return
    st = _state(layout)
    if not st:
        return
    keys = st["keys"]
    edge_class = {}
    for e in st["edges"]:
        edge_class[(e["ka"], e["kb"])] = e
    index = _Index([(float(x), float(y)) for (x, y) in nodes])

    n_drop = len(dropped)
    n_total = n_drop + carried
    svc_drop = taxi_drop = 0
    failed: dict = {}
    reasons: dict = {}
    for (ka, kb, a_miss, b_miss, reason) in dropped:
        info = edge_class.get((ka, kb)) or {"svc": False, "corridor": -1}
        if info["svc"]:
            svc_drop += 1
        else:
            taxi_drop += 1
        reasons[reason] = reasons.get(reason, 0) + 1
        for (k, miss) in ((ka, a_miss), (kb, b_miss)):
            if miss and k not in failed:
                failed[k] = info

    rekeyed, moved = [], []
    for k, info in failed.items():
        rec = keys.get(k) or {"xy": k, "svc": info["svc"], "lost_at": None,
                              "lost_evidence": None}
        d, nv = index.nearest(float(k[0]), float(k[1]))
        dm, _ = index.nearest(float(rec["xy"][0]), float(rec["xy"][1]))
        entry = {
            "key": [float(k[0]), float(k[1])],
            "mint_xy": [float(rec["xy"][0]), float(rec["xy"][1])],
            "nearest_rebuilt_xy": (list(nv) if nv else None),
            "d_key_m": (None if d == float("inf") else d),
            "d_mint_m": (None if dm == float("inf") else dm),
            "svc": bool(rec.get("svc") or info["svc"]),
            "lost_at": rec.get("lost_at"),
            "lost_evidence": rec.get("lost_evidence"),
        }
        if d <= REKEY_TOL_M:
            entry["verdict"] = "rekeyed"
            rekeyed.append(entry)
        else:
            entry["verdict"] = "moved"
            moved.append(entry)

    def _pct(a, b):
        return (100.0 * a / b) if b else 0.0

    lines = [
        "",
        f"    [rod-audit] ===== CARRY REPORT {icao} =====",
        f"    [rod-audit] links total={n_total} carried={carried} "
        f"({_pct(carried, n_total):.1f}%) dropped={n_drop} "
        f"({_pct(n_drop, n_total):.1f}%)",
        f"    [rod-audit] dropped links: taxi={taxi_drop} "
        f"({_pct(taxi_drop, n_drop):.1f}%) service={svc_drop} "
        f"({_pct(svc_drop, n_drop):.1f}%)",
        "    [rod-audit] drop reasons: " + ", ".join(
            f"{r}={c}" for r, c in sorted(reasons.items(),
                                          key=lambda kv: -kv[1])),
        f"    [rod-audit] failed endpoint keys={len(failed)}: "
        f"RE-KEYED={len(rekeyed)} ({_pct(len(rekeyed), len(failed)):.1f}%) "
        f"MOVED={len(moved)} ({_pct(len(moved), len(failed)):.1f}%) "
        f"[1 mm test]",
    ]
    if moved:
        ds = sorted(e["d_key_m"] for e in moved
                    if e["d_key_m"] is not None)
        if ds:
            def q(p):
                return ds[min(len(ds) - 1, int(p * (len(ds) - 1)))]
            lines.append(
                f"    [rod-audit] MOVED distance (m): min={ds[0]:.4f} "
                f"p50={q(0.5):.4f} p90={q(0.9):.4f} max={ds[-1]:.4f}")
        bins = [(0.001, 0.01), (0.01, 0.1), (0.1, 0.5), (0.5, 2.0),
                (2.0, 10.0), (10.0, 1e9)]
        for (lo, hi) in bins:
            c = sum(1 for e in moved if e["d_key_m"] is not None
                    and lo <= e["d_key_m"] < hi)
            inf = sum(1 for e in moved if e["d_key_m"] is None)
            if c:
                lines.append(f"    [rod-audit]   {lo:>8.3f}-{hi:<8.3f} m: {c}")
        n_inf = sum(1 for e in moved if e["d_key_m"] is None)
        if n_inf:
            lines.append(f"    [rod-audit]   no vertex found: {n_inf}")
    # attribution: which pass lost the key
    by_pass: dict = {}
    for e in list(moved) + list(rekeyed):
        p = e["lost_at"] or "(never lost at a checkpoint)"
        agg = by_pass.setdefault(p, {"moved": 0, "rekeyed": 0, "svc": 0})
        agg[e["verdict"]] += 1
        if e["svc"]:
            agg["svc"] += 1
    lines.append("    [rod-audit] attribution (first checkpoint the key "
                 "stopped resolving):")
    for p, agg in sorted(by_pass.items(), key=lambda kv: -sum(
            (kv[1]["moved"], kv[1]["rekeyed"]))):
        lines.append(f"    [rod-audit]   {p:<40s} moved={agg['moved']:<6d} "
                     f"rekeyed={agg['rekeyed']:<6d} service={agg['svc']}")
    lines.append("    [rod-audit] ===== END CARRY REPORT =====")
    print("\n".join(lines))

    out = os.environ.get("O4_ROD_CARRY_AUDIT_OUT") or (
        f"/tmp/rod_carry_audit_{icao or 'airport'}.json")
    try:
        payload = {
            "icao": icao,
            "links": {"total": n_total, "carried": carried,
                      "dropped": n_drop, "taxi_dropped": taxi_drop,
                      "service_dropped": svc_drop, "reasons": reasons},
            "endpoints": {"failed": len(failed),
                          "rekeyed": len(rekeyed), "moved": len(moved)},
            "rekeyed": rekeyed,
            "moved": moved,
            "checkpoints": [
                {"name": c["name"], "n_resolved": c["n_resolved"],
                 "newly_lost": c["newly_lost"]}
                for c in st["checkpoints"]],
            "corridor_svc": {str(k): v
                             for k, v in st["corridor_svc"].items()},
        }
        with open(out, "w") as fh:
            json.dump(payload, fh, indent=1)
        print(f"    [rod-audit] wrote {out}")
    except Exception as exc:                               # pragma: no cover
        print(f"    [rod-audit] could not write {out}: {exc}")
