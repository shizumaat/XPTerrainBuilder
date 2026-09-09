#!/usr/bin/env python3
"""THE UNDULATION READ — the owner's 2026-09-08t complaint in a number.

"Still follows the DEM too closely — unrealistic undulation."  A designed
pavement is a SMOOTH sheet: its grade changes slowly along every chain.
This reads an emitted patch (v1's or v2's — both carry ``alt_abs`` per node
and ``role`` per way) and reports, per role and per way:

* the RMS SECOND DIFFERENCE of z along every chain — the grade change at
  each interior station, ``(z2−z1)/dn − (z1−z0)/dp``, dimensionless;
* the MAX GRADE CHANGE PER 100 m — that second difference divided by the
  station's own span, ×100: how fast the slope turns over the ground.

Lower is smoother.  The instrument is patch-only and law-free on purpose:
it compares a v1 patch, a v2 patch and a v2 patch from another engine
version on exactly the same footing.

    venv/bin/python tools/undulation.py PATCH.osm [PATCH.osm ...] [--json OUT]
        [--role ROLE ...] [--top N]

Promoted to ``tools/`` on its first shared use (lane ``v2smooth``, the
design-surface acceptance, spec ``auto-patch-v2/design-surface-spec.md`` §5).
"""
from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

#: Metres per degree of latitude (a local-flat read: the patch spans a
#: single airport, so a spherical correction is below the noise floor).
M_PER_DEG = 111_320.0


def read_patch(path: Path) -> tuple[dict[str, list], dict[int, tuple[float, float, float]]]:
    """``(ways by role, node -> (x, y, z))`` in local metres."""
    root = ET.parse(path).getroot()
    nodes: dict[int, tuple[float, float, float]] = {}
    lat0 = None
    raw: dict[int, tuple[float, float, float | None]] = {}
    for nd in root.findall("node"):
        nid = int(nd.get("id"))
        lat, lon = float(nd.get("lat")), float(nd.get("lon"))
        z = None
        for tg in nd.findall("tag"):
            if tg.get("k") == "alt_abs":
                z = float(tg.get("v"))
        raw[nid] = (lat, lon, z)
        lat0 = lat if lat0 is None else lat0
    if lat0 is None:
        return {}, {}
    cos = math.cos(math.radians(lat0))
    for nid, (lat, lon, z) in raw.items():
        if z is None:
            continue
        nodes[nid] = ((lon * M_PER_DEG * cos), (lat * M_PER_DEG), z)
    by_role: dict[str, list] = {}
    for w in root.findall("way"):
        tags = {tg.get("k"): tg.get("v") for tg in w.findall("tag")}
        role = tags.get("role") or tags.get("aeroway") or "unknown"
        refs = [int(nd.get("ref")) for nd in w.findall("nd")]
        by_role.setdefault(role, []).append((w.get("id"), tags.get("ref"), refs))
    return by_role, nodes


def chain_read(refs: list[int], nodes: dict[int, tuple[float, float, float]]
               ) -> list[tuple[float, float]]:
    """``(second difference, grade change per 100 m)`` per interior station."""
    pts = [nodes[r] for r in refs if r in nodes]
    if len(refs) > 2 and refs[0] == refs[-1]:
        pts = pts[:-1] + pts[:1]            # a ring: keep it closed, read it once
    out: list[tuple[float, float]] = []
    for k in range(1, len(pts) - 1):
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = pts[k - 1], pts[k], pts[k + 1]
        dp = math.hypot(x1 - x0, y1 - y0)
        dn = math.hypot(x2 - x1, y2 - y1)
        if dp <= 1e-6 or dn <= 1e-6:
            continue
        d2 = (z2 - z1) / dn - (z1 - z0) / dp
        out.append((d2, 100.0 * d2 / (0.5 * (dp + dn))))
    return out


def undulation(path: Path, roles: tuple[str, ...] = ()) -> dict:
    by_role, nodes = read_patch(path)
    per_role: dict[str, dict] = {}
    worst: list[tuple[float, str, str]] = []
    for role, ways in sorted(by_role.items()):
        if roles and role not in roles:
            continue
        d2s: list[float] = []
        g100: list[float] = []
        for wid, ref, refs in ways:
            got = chain_read(refs, nodes)
            for d2, g in got:
                d2s.append(d2)
                g100.append(abs(g))
                worst.append((abs(g), role, f"{ref or wid}"))
        if not d2s:
            continue
        per_role[role] = {
            "ways": len(ways), "stations": len(d2s),
            "rms_second_difference": round(math.sqrt(sum(v * v for v in d2s) / len(d2s)), 6),
            "max_grade_change_per_100m": round(max(g100), 4),
            "p95_grade_change_per_100m": round(sorted(g100)[int(0.95 * (len(g100) - 1))], 4),
        }
    allst = [v for r in per_role.values() for v in [r]]
    n = sum(r["stations"] for r in per_role.values()) or 1
    rms_all = math.sqrt(sum(r["rms_second_difference"] ** 2 * r["stations"]
                            for r in per_role.values()) / n)
    worst.sort(reverse=True)
    return {"patch": str(path), "stations": n, "roles": per_role,
            "rms_second_difference": round(rms_all, 6),
            "max_grade_change_per_100m": round(max((r["max_grade_change_per_100m"]
                                                    for r in per_role.values()), default=0.0), 4),
            "worst": [{"grade_change_per_100m": round(g, 4), "role": r, "way": w}
                      for g, r, w in worst[:10]],
            "_n_roles": len(allst)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patches", nargs="+", type=Path)
    ap.add_argument("--role", action="append", default=[])
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    out = []
    for p in a.patches:
        rec = undulation(p, tuple(a.role))
        out.append(rec)
        print(f"== {p.name}: {rec['stations']} stations over {rec['_n_roles']} roles; "
              f"RMS 2nd difference {rec['rms_second_difference']:.6f}; "
              f"max grade change {rec['max_grade_change_per_100m']:.3f} per 100 m")
        for role, r in sorted(rec["roles"].items(),
                              key=lambda kv: -kv[1]["rms_second_difference"])[:a.top]:
            print(f"   {role:22s} ways {r['ways']:5d} stations {r['stations']:7d}  "
                  f"RMS {r['rms_second_difference']:.6f}  p95/100m {r['p95_grade_change_per_100m']:.3f}  "
                  f"max/100m {r['max_grade_change_per_100m']:.3f}")
    if a.json:
        a.json.write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
