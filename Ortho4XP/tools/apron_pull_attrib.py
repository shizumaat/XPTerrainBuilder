#!/usr/bin/env python3
"""WHAT PULLED THE APRON BACK TO THE TERRAIN — the binding constraint, per
node, at exit.

WHY THIS EXISTS.  The scaffold seed (RULINGS 2026-08-24c) re-seated 22,089
HECA apron-interior nodes onto the centerline scaffold, worst move 49 m,
and the emitted apron came out 0.14 m higher than the arm before it.  A
census cannot say why: it prices pairs, and a node returning to the DEM
breaks no law.  ``who_wrote`` answers "which PASS wrote this" but needs a
build to record the writes and its emitted-frame half only reads a
CONSTANT-DEM world.  ``arm_site_read`` answers one coordinate.  Nothing
answered "of the nodes the scaffold lifted, which constraint put them
back, and how are they distributed" — which is the question a mechanism
fix has to be aimed at.

IT MEASURES NO LAW AND COUNTS NO DEFECTS.  Geometry, elevations and the
metre frame come from the harness library's own reader
(``check_grade._parse_osm`` / ``_ll_to_m_factory`` about the sidecar
anchor); the DEM through ``apron_drape_read``'s loaders (hence
``flat_site_sweep``'s, hence the engine's own ``dem.alt``); the enforced
graph verbatim from the sidecar's ``pair_caps``; and the seed REPLAY from
the engine's own ``law_graph_budget.build_anchor_envelope`` and
``scaffold_seed.taut_level``, so the replayed value is the seed's own
arithmetic and not a re-derivation of it.

THE SEED VALUES ARE A REPLAY, NOT A RECORD — say so wherever they are
quoted.  Per-node seed values are not emitted, so this reconstructs them
from the EMITTED patch: anchors are the emitted spine and pad values,
where the real seed used phase-A spine values and the seats of that
moment.  The two agree wherever the projection did not move an anchor, and
the classification below depends on the SIGN and rough size of the lift,
not on its third decimal.

THE CLASSES, in the precedence they are applied:

  band          the node is in the sidecar's own ``band_clamp_nodes`` /
                ``band_excess`` — the writeback band clamped it.
  transect      the node carries a bound TRANSVERSE row (``xsection_spans``)
                whose far side sits on the DEM.
  weld_ground   a TIGHT enforced edge (|dz| within tolerance of its own
                budget) runs to a NON-apron neighbour that is itself
                DEM-following: the membrane is hung from a DEM edge.
  weld_apron    every tight edge runs to another apron node that is itself
                near the DEM: the pull propagated inside the apron.
  unbound       NO enforced edge is tight and no clamp applies — nothing
                held this node at the DEM; the value simply returned there.
                This is the projection-convergence class.

    venv/bin/python tools/apron_pull_attrib.py PATCH.osm
        [--lift-m 2.0] [--near-dem-m 0.5] [--limit 200] [--json OUT]
        [--compare WEEK_AGO.osm]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_ROOT / "src"), str(_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_grade as CG                                       # noqa: E402
import apron_drape_read as ADR                                 # noqa: E402
from auto_patch.elevation_per_surface.route_profile.law_graph_budget \
    import build_anchor_envelope                               # noqa: E402
from auto_patch.elevation_per_surface.route_profile.scaffold_seed \
    import taut_level                                          # noqa: E402

APRON_ROLE = "apron"
#: An edge is BINDING when it carries at least this fraction of its budget.
_TIGHT_FRAC = 0.98
#: A node is DEM-FOLLOWING when it sits this close to the terrain under it.
_DEM_FOLLOW_M = 0.35
#: ``pair_caps`` lat/lon are exported rounded; join on the same quantum the
#: census itself uses (``check_grade``'s own ``_pair_cap_map``).
_JOIN_DP = 7

CLASSES = ("band", "transect", "weld_ground", "weld_apron", "unbound")


def _key(la, lo):
    return (round(float(la), _JOIN_DP), round(float(lo), _JOIN_DP))


def load_arm(patch: Path, *, dem_source="airport-inset") -> dict:
    """Everything one arm contributes: geometry, emitted values, DEM,
    roles, the enforced graph and the sidecar's own clamp records."""
    nodes, ways = CG._parse_osm(patch)
    side = json.loads(Path(str(patch) + ".axes.json").read_text())
    anchor = side.get("anchor")
    ll_to_m = CG._ll_to_m_factory(
        nodes, anchor=tuple(anchor) if anchor else None)

    tile_lat, tile_lon = ADR._tile_of(nodes)
    icao = patch.name.split("_")[0].upper()
    dem, dem_path, _origin = ADR._load_dem(tile_lat, tile_lon, icao,
                                           dem_source)
    if dem is None:
        raise SystemExit(f"{patch}: no {dem_source} DEM cached for {icao}")

    z, role, dem_z = {}, {}, {}
    for w in ways:
        r = w.tags.get("role") or ""
        nids = w.nids[:-1] if (len(w.nids) > 1
                               and w.nids[0] == w.nids[-1]) else w.nids
        elevs = w.elevs[:len(nids)]
        for nid, e in zip(nids, elevs):
            if e is None or nid not in nodes:
                continue
            z[nid] = float(e)
            # AIRSIDE WINS a shared node, the engine's own convention.
            if nid not in role or r == APRON_ROLE:
                role[nid] = r
    for nid, (la, lo) in nodes.items():
        if nid in z:
            d = ADR._dem_at(dem, la, lo, tile_lat, tile_lon)
            if d is not None:
                dem_z[nid] = d

    by_key = {_key(*nodes[n]): n for n in z}

    # THE ENFORCED GRAPH, verbatim from the sidecar.
    adj: dict = {}
    for e in (side.get("pair_caps") or []):
        a = by_key.get(_key(e[0][0], e[0][1]))
        b = by_key.get(_key(e[1][0], e[1][1]))
        if a is None or b is None or a == b:
            continue
        try:
            bud = abs(float(e[2]))
        except (TypeError, ValueError):
            continue
        adj.setdefault(a, []).append((b, bud))
        adj.setdefault(b, []).append((a, bud))

    clamped = set()
    for row in (side.get("band_clamp_nodes") or []):
        k = _key(row[0], row[1]) if isinstance(row, (list, tuple)) else None
        if k and k in by_key:
            clamped.add(by_key[k])
    for row in (side.get("band_excess") or {}).values():
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            k = _key(row[0], row[1])
            if k in by_key:
                clamped.add(by_key[k])

    transect: dict = {}
    for span in (side.get("xsection_spans") or []):
        pts = span.get("ll") if isinstance(span, dict) else None
        if not pts:
            continue
        ids = [by_key.get(_key(p[0], p[1])) for p in pts]
        ids = [i for i in ids if i is not None]
        for i in ids:
            transect.setdefault(i, set()).update(x for x in ids if x != i)

    return {"patch": patch, "icao": icao, "nodes": nodes, "z": z,
            "role": role, "dem": dem_z, "adj": adj, "clamped": clamped,
            "transect": transect, "by_key": by_key, "ll_to_m": ll_to_m,
            "side": side, "dem_path": dem_path}


def replay_seed(arm: dict) -> dict:
    """The scaffold seed's own arithmetic, replayed on this arm.

    Anchors are the emitted SPINE values and the emitted BUILDING ring
    values — the two authorities the ruling names.  A REPLAY, not a
    record: see the module docstring."""
    spine_keys = set()
    for axis in (arm["side"].get("axes_exact") or []):
        for pt in (axis[0] if axis and isinstance(axis[0], list) else []):
            k = _key(pt[0], pt[1])
            if k in arm["by_key"]:
                spine_keys.add(arm["by_key"][k])
    anchors = {i: arm["z"][i] for i in spine_keys if i in arm["z"]}
    for nid, r in arm["role"].items():
        if r == "building" and nid in arm["z"]:
            anchors[nid] = arm["z"][nid]
    if not anchors:
        return {}
    idx = {n: k for k, n in enumerate(arm["adj"])}
    radj = {idx[n]: [(idx[m], b) for (m, b) in lst if m in idx]
            for n, lst in arm["adj"].items()}
    ranch = {idx[n]: v for n, v in anchors.items() if n in idx}
    env = build_anchor_envelope(radj, ranch)
    if env is None:
        return {}
    out = {}
    for n, k in idx.items():
        lvl = taut_level(env.box(k))
        if lvl is not None:
            out[n] = lvl
    return out


def classify(arm: dict, nid: str) -> tuple:
    """The binding constraint at exit, with its witness."""
    if nid in arm["clamped"]:
        return "band", "sidecar band_clamp/band_excess record"
    z, dem = arm["z"], arm["dem"]
    for far in arm["transect"].get(nid, ()):
        if far in dem and abs(z.get(far, 0.0) - dem[far]) <= _DEM_FOLLOW_M:
            return "transect", f"bound transect row, far side {far} on DEM"
    tight = []
    for (j, bud) in arm["adj"].get(nid, ()):
        if j not in z or bud <= 0:
            continue
        if abs(z[nid] - z[j]) >= _TIGHT_FRAC * bud:
            tight.append((j, bud))
    if not tight:
        return "unbound", "no enforced edge is tight at exit"
    for (j, bud) in tight:
        if (arm["role"].get(j) != APRON_ROLE and j in dem
                and abs(z[j] - dem[j]) <= _DEM_FOLLOW_M):
            return ("weld_ground",
                    f"tight edge to {arm['role'].get(j) or '?'} node {j} "
                    f"(budget {bud:.3f} m), which sits on the DEM")
    for (j, bud) in tight:
        if j in dem and abs(z[j] - dem[j]) <= _DEM_FOLLOW_M:
            return ("weld_apron",
                    f"tight edge to apron node {j} (budget {bud:.3f} m), "
                    f"itself on the DEM")
    return ("weld_apron",
            f"tight edges only ({len(tight)}), nearest neighbour "
            f"{tight[0][0]} at budget {tight[0][1]:.3f} m")


def run(patch: Path, *, lift_m: float, near_dem_m: float, limit: int,
        dem_source: str) -> dict:
    arm = load_arm(patch, dem_source=dem_source)
    seed = replay_seed(arm)
    z, dem, role = arm["z"], arm["dem"], arm["role"]

    picked = []
    for nid, s in seed.items():
        if role.get(nid) != APRON_ROLE or nid not in dem or nid not in z:
            continue
        lift = s - dem[nid]
        if lift < lift_m:
            continue
        if abs(z[nid] - dem[nid]) > near_dem_m:
            continue
        picked.append((s - z[nid], nid, s))
    picked.sort(reverse=True)
    picked = picked[:limit]

    rows, dist = [], {c: 0 for c in CLASSES}
    for (fell, nid, s) in picked:
        cls, why = classify(arm, nid)
        dist[cls] += 1
        la, lo = arm["nodes"][nid]
        rows.append({"node": nid, "lat": la, "lon": lo,
                     "seed_z_replayed": round(s, 3),
                     "emitted_z": round(z[nid], 3),
                     "dem_z": round(dem[nid], 3),
                     "fell_m": round(fell, 3),
                     "class": cls, "witness": why})
    return {"patch": str(patch), "icao": arm["icao"],
            "dem_path": arm["dem_path"],
            "apron_nodes_with_replayed_seed": sum(
                1 for n in seed if role.get(n) == APRON_ROLE),
            "selected": len(rows), "distribution": dist, "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("patch", type=Path)
    ap.add_argument("--lift-m", type=float, default=2.0)
    ap.add_argument("--near-dem-m", type=float, default=0.5)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--dem-source", default="airport-inset",
                    choices=("airport-inset", "base"))
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)

    rep = run(a.patch, lift_m=a.lift_m, near_dem_m=a.near_dem_m,
              limit=a.limit, dem_source=a.dem_source)
    print("=== APRON PULL ATTRIBUTION ===")
    print(f"  {rep['icao']}  {Path(rep['patch']).name}")
    print("  seed values are a REPLAY of the scaffold arithmetic on the "
          "EMITTED anchors, never a record of the build's own seed.")
    print(f"  apron nodes with a replayed seed: "
          f"{rep['apron_nodes_with_replayed_seed']}")
    print(f"  selected (seed >= DEM+{a.lift_m:g} m, emitted within "
          f"{a.near_dem_m:g} m of DEM): {rep['selected']}\n")
    tot = max(1, rep["selected"])
    for c in CLASSES:
        n = rep["distribution"][c]
        print(f"    {c:12s} {n:5d}  {100.0 * n / tot:5.1f} %")
    print("\n  worst 5 by how far the node fell back:")
    for r in rep["rows"][:5]:
        print(f"    {r['node']} @({r['lat']:.6f},{r['lon']:.6f})  "
              f"seed {r['seed_z_replayed']:.2f} -> emitted "
              f"{r['emitted_z']:.2f}  (DEM {r['dem_z']:.2f}, fell "
              f"{r['fell_m']:.2f} m)\n      {r['class']}: {r['witness']}")
    if a.json:
        a.json.write_text(json.dumps(rep, indent=2))
        print(f"\n  wrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
