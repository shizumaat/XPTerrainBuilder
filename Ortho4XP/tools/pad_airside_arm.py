"""THE PAD/AIRSIDE INVARIANCE ARM (RULINGS 2026-09-14as (i), lane
``v2padvert``; promoted from that lane's scratchpad on its eighth use per
RULINGS ``7e90032``).

    venv/bin/python tools/pad_airside_arm.py --engine <engine tree> ICAO OUT.json
    V2PADVERT_ENGINE=<engine tree> venv/bin/python tools/pad_airside_arm.py ICAO OUT.json

ONE load, then classify+planar TWICE — ``[placement] pad_from_cluster``
OFF then ON — and a diff of §20b stage 1's OWN airside vertex population
(``solve/design_roles.airside_stage_vertices``, never a hand list) and the
apron face list between the two arms.  It answers "does deriving the pads
change the AIRSIDE PROBLEM", which is 14as (i)'s prerequisite, in ~3
minutes at HECA against a ~450 s build, and it is a READER: no solve, no
emit, nothing written but its own JSON.  The shared-repo write guard and
the lane-local cache redirects are armed through
``harness/build_airport.arm_shared_repo_protection`` (the ONE arming
composition), and every run prints ``[guard] shared repo UNCHANGED``.

It also prints what the clip and the rim snap did
(``classify/evidence.PAD_AIRSIDE``) and, per NEW airside vertex, how far
it stands from the OTHER arm's nearest airside vertex and from its
airside BOUNDARY — the two readings that say whether a minted vertex is a
clip crossing point or a grid artefact.

Twin: ``tests/auto_patch_v2/test_v2padvert.py``."""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Self-contained and ahead of every
# other import because a tool's own ``--help`` carries the house spelling
# (``Δ``, ``ε``, ``≥``, ``→``) and a Windows console RAISES on those
# rather than mangling them.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import dataclasses as _dc, json, sys, time
from pathlib import Path

import os
ROOT = Path(__file__).resolve()

#: The engine tree and the scratch/guard directory.  They are ``--engine``
#: and ``--out-dir``, each DEFAULTING to the historical environment variable
#: so no existing caller breaks — which is how the rest of the harness
#: spells an engine tree (#178).
ENGINE_VARIABLE = "V2PADVERT_ENGINE"
OUT_VARIABLE = "V2PADVERT_OUT"

#: Filled by ``arm_engine()``, called from ``main()`` AFTER ``parse_args()``
#: (#178).  NOTHING here runs at import: this module body used to read
#: ENGINE_VARIABLE (KeyError when unset), ``chdir`` into it
#: (FileNotFoundError when wrong), ``mkdir`` the output directory and ARM
#: the shared-repo write guard before ``argparse`` existed, so ``--help``
#: could not be run at all — the one tool of 80 whose help
#: ``tests/test_console_encoding.py`` had to skip.  The engine imports are
#: function-local for the same reason: they need ``<engine>/src`` on
#: ``sys.path``, which only ``arm_engine()`` knows.
ENGINE: Path | None = None
OUT: Path | None = None
GUARD = None
_RED = None


def arm_engine(engine: str | None = None, out: str | None = None):
    """Enter the engine tree and arm the shared-repo write guard.

    Everything this module used to do at import time, now behind
    ``parse_args()``.  ``engine``/``out`` fall back to ENGINE_VARIABLE /
    OUT_VARIABLE, then to ``<engine>/tmp/padvert``."""
    global ENGINE, OUT, GUARD, _RED
    engine = engine or os.environ.get(ENGINE_VARIABLE)
    if not engine:
        raise SystemExit(
            f"[arm] no engine tree: pass --engine <tree> or export "
            f"{ENGINE_VARIABLE}=<tree>")
    ENGINE = Path(engine).resolve()
    if not ENGINE.is_dir():
        raise SystemExit(f"[arm] --engine is not a directory: {ENGINE}")
    os.chdir(ENGINE)
    for entry in (ENGINE / "tools", ENGINE, ENGINE / "src"):
        sys.path.insert(0, str(entry))
    OUT = Path(out or os.environ.get(OUT_VARIABLE)
               or (ENGINE / "tmp" / "padvert"))
    OUT.mkdir(parents=True, exist_ok=True)
    from harness.build_airport import arm_shared_repo_protection
    GUARD, _RED = arm_shared_repo_protection(ENGINE, OUT, "v2padvert")
    return GUARD


def armed(law, on: bool | dict):
    """``on`` is either the historical bool (``pad_from_cluster``) or a dict
    of ``[placement]`` key -> value, coerced to the key's own type — the same
    arm form ``v2_solve_replay --placement KEY=V`` speaks (lane ``v2padqp``).
    An unknown key REFUSES BY NAME rather than arming nothing."""
    base = law.tables.structures.placement
    over = {"pad_from_cluster": bool(on)} if isinstance(on, bool) else dict(on)
    for k in over:
        if not hasattr(base, k):
            raise SystemExit(f"[arm] unknown [placement] key: {k}")
    over = {k: type(getattr(base, k))(v) if not isinstance(v, type(getattr(base, k)))
            else v for k, v in over.items()}
    p = _dc.replace(base, **over)
    st = _dc.replace(law.tables.structures, placement=p)
    return _dc.replace(law, tables=_dc.replace(law.tables, structures=st))


def _parse_arm(spec: str) -> dict:
    """``KEY=V,KEY=V`` -> dict, with ``true``/``false`` read as bools."""
    out: dict = {}
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        k, _, v = item.partition("=")
        vl = v.strip().lower()
        out[k.strip()] = True if vl == "true" else False if vl == "false" else v.strip()
    return out


def read(pm, law):
    """§20b stage 1's OWN population — solve/design_roles.airside_stage_vertices
    (the runway family, the taxi family and the apron; NOT the pad)."""
    from auto_patch_v2.solve.design_roles import (airside_stage_roles,
                                                  airside_stage_vertices)
    air = airside_stage_vertices(pm, law)
    roles = airside_stage_roles(law)
    vkeys = {pm.vertices[v].key for v in air}
    faces_by_role, apron, fv = {}, [], {}
    for f in pm.faces.values():
        faces_by_role[f.role] = faces_by_role.get(f.role, 0) + 1
        if f.role == "apron":
            apron.append(f.ref)
    for v in pm.vertices.values():
        fv[v.key] = tuple(sorted({f"{pm.faces[i].role}:{pm.faces[i].ref}"
                                  for i in v.incident_faces}))
    xy = {pm.vertices[v].key: pm.vertices[v].xy for v in air}
    # the AIRSIDE POLYGON of this arm, from its own faces
    from shapely.geometry import Polygon as _P
    from shapely.ops import unary_union as _u
    gs = []
    for f in pm.faces.values():
        if f.role not in roles:
            continue
        try:
            ring = [pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]
            if len(ring) >= 3:
                g = _P(ring)
                gs.append(g if g.is_valid else g.buffer(0.0))
        except Exception:
            pass
    poly = _u(gs) if gs else None
    return vkeys, sorted(apron), faces_by_role, fv, xy, poly


def run(icao="HECA", out="arm.json", arm_a=None, arm_b=None):
    from harness.build_airport import report_guard_churn
    if GUARD is None:
        raise SystemExit("[arm] arm_engine() must run before run()")
    GUARD.__enter__()
    try:
        _run(icao, out, arm_a, arm_b)
    finally:
        GUARD.__exit__(None, None, None)
        report_guard_churn(GUARD)
        print("[guard]", "shared repo UNCHANGED" if not GUARD.blocked
              else f"BLOCKED {GUARD.blocked}")


def _run(icao, out, arm_a=None, arm_b=None):
    # Engine imports are deferred: they need <engine>/src on sys.path, which
    # only arm_engine() knows, and importing them at module level is what
    # made --help unmeasurable (#178).
    from auto_patch_v2.planar.__main__ import default_inputs
    from auto_patch_v2.airport.load import load_with_report
    from auto_patch_v2.classify import classify, load_rules
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar.build import build

    law0 = Law.for_airport(icao)
    t = time.perf_counter()
    inputs = default_inputs()
    airport, lrep = load_with_report(icao, inputs, law0)
    print(f"load {time.perf_counter()-t:.1f}s", flush=True)
    # THE PACK PARTITION + GROUPS + CLUSTERS (pipeline/build.py:283-380,
    # verbatim in kind — v2_solve_replay.capture does the same for the
    # same reason; without them airport.clusters is EMPTY and
    # pad_from_cluster is silently inert)
    from auto_patch_v2.airport.obj8 import ResourceCache as _RCache
    from auto_patch_v2.airport.pack_partition import partition_pack
    from auto_patch_v2.law.tables import group_span_max_m as span_max
    from auto_patch_v2.planar.basins import read_objects
    from auto_patch_v2.planar.group import derive as derive_groups
    from auto_patch_v2.planar.cluster import clusters as derive_clusters
    t = time.perf_counter()
    ocache = _RCache(law0.tables.structures.basin.min_solid_thickness_m)
    pack_objects, pack_report = read_objects(airport, law0, ocache)
    part = partition_pack(airport, pack_objects, ocache, law0)
    to_xy, _ = airport.frame.transformers()

    def dem_at(lat, lon):
        x, y = to_xy(lon, lat)
        try:
            z = airport.dem.z(x, y)
        except Exception:
            return None
        if z is None:
            return None
        z = float(z)
        return None if z != z else z

    bank = float(law0.tables.emit.design.bank_slope)
    groups = derive_groups(part, span_max(law0), bank, dem_at=dem_at, bank_slope=bank)
    cls = derive_clusters(_dc.replace(airport, partition=part), law0)
    airport = _dc.replace(airport, partition=part, groups=groups, clusters=cls)
    print(f"partition+clusters {time.perf_counter()-t:.1f}s  clusters {len(cls)}",
          flush=True)
    rules = load_rules()
    res = {}
    arms = (("off", arm_a if arm_a is not None else False),
            ("on", arm_b if arm_b is not None else True))
    for name, on in arms:
        law = armed(law0, on)
        print(f"{name}: ARM {json.dumps(on if isinstance(on, dict) else {'pad_from_cluster': on})}",
              flush=True)
        t = time.perf_counter()
        cl = classify(airport, law, rules, cache=ocache)
        pm, _st = build(airport, cl, law, cache=ocache, objects=pack_objects,
                        object_report=pack_report)
        from auto_patch_v2.classify.evidence import CLUSTER_PADS
        from auto_patch_v2.planar.overlay import PAD_AIRSIDE
        print(f"{name}: CLUSTER_PADS {json.dumps(dict(CLUSTER_PADS))}", flush=True)
        print(f"{name}: PAD_AIRSIDE {json.dumps(dict(PAD_AIRSIDE))}", flush=True)
        print(f"{name}: classify+planar {time.perf_counter()-t:.1f}s "
              f"verts {len(pm.vertices)} faces {len(pm.faces)}", flush=True)
        res[name] = read(pm, law)
    v0, a0, r0, fv0, xy0, poly0 = res["off"]
    v1, a1, r1, fv1, xy1, poly1 = res["on"]
    gone, new = v0 - v1, v1 - v0
    print(f"AIRSIDE vertices: off {len(v0)}  on {len(v1)}  GONE {len(gone)}  NEW {len(new)}")
    print(f"apron faces: off {len(a0)}  on {len(a1)}")
    print("roles off:", json.dumps(r0, sort_keys=True))
    print("roles on :", json.dumps(r1, sort_keys=True))
    from collections import Counter
    print("GONE incident roles OFF:", Counter(fv0[k] for k in gone).most_common(12))
    print("GONE incident roles ON  (survivors):",
          Counter(fv1.get(k, ("<absent>",)) for k in gone).most_common(12))
    print("NEW incident roles ON:", Counter(fv1[k] for k in new).most_common(12))
    print("NEW  incident roles OFF (pre-existing):",
          Counter(fv0.get(k, ("<absent>",)) for k in new).most_common(12))
    # HOW FAR would a NEW airside vertex have to move to land on an
    # EXISTING one (the pad-independent OFF-arm airside vertex set)?  That
    # distance IS the price of rule (1)'s snap.
    import numpy as np
    from scipy.spatial import cKDTree
    k0 = sorted(v0)
    tree = cKDTree(np.array([xy0[k] for k in k0]))
    if new:
        d, _i = tree.query(np.array([xy1[k] for k in sorted(new)]))
        d = np.sort(d)
        print(f"NEW vertex -> nearest OFF-arm airside vertex (m): "
              f"min {d[0]:.3f} p50 {d[len(d)//2]:.3f} p90 {d[int(.9*len(d))]:.3f} "
              f"max {d[-1]:.3f}; over 1 m {int((d > 1.0).sum())}, over 5 m "
              f"{int((d > 5.0).sum())}")
    if new and poly0 is not None:
        from shapely.geometry import Point as _Pt
        b0 = poly0.boundary
        dd = sorted(b0.distance(_Pt(xy1[k])) for k in new)
        print(f"NEW vertex -> OFF-arm airside BOUNDARY (m): "
              f"on it (<0.01) {sum(1 for x in dd if x < 0.01)} of {len(dd)}; "
              f"p50 {dd[len(dd)//2]:.3f} max {dd[-1]:.3f}")
        print("NEW sample (lat,lon,dist-to-boundary):",
              [(k, round(b0.distance(_Pt(xy1[k])), 3)) for k in sorted(new)[:8]])
        print("GONE sample:", [(k, fv0[k]) for k in sorted(gone)[:10]])
        print("NEW  faces  :", [(k, fv1[k]) for k in sorted(new)[:10]])
    Path(out).write_text(json.dumps(
        {"gone": sorted(gone)[:4000], "new": sorted(new)[:4000],
         "apron_off": a0, "apron_on": a1, "roles_off": r0, "roles_on": r1}))
    print("->", out)


def main(argv=None):
    """``--help`` returns from HERE, before any env read, chdir, mkdir or
    guard arm — all of which happen in ``arm_engine()`` below (#178)."""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("icao", nargs="?", default="HECA")
    ap.add_argument("out", nargs="?", default="arm.json")
    ap.add_argument("--engine", metavar="TREE",
                    default=os.environ.get(ENGINE_VARIABLE),
                    help=f"the engine tree to run in (default: the "
                         f"{ENGINE_VARIABLE} environment variable)")
    ap.add_argument("--out-dir", metavar="DIR",
                    default=os.environ.get(OUT_VARIABLE),
                    help=f"guard/scratch directory (default: the "
                         f"{OUT_VARIABLE} environment variable, else "
                         f"<engine>/tmp/padvert)")
    ap.add_argument("--arm-a", metavar="KEY=V[,KEY=V]",
                    help="[placement] keys for the FIRST arm (default: "
                         "pad_from_cluster=false)")
    ap.add_argument("--arm-b", metavar="KEY=V[,KEY=V]",
                    help="[placement] keys for the SECOND arm (default: "
                         "pad_from_cluster=true)")
    a = ap.parse_args(argv)
    arm_engine(a.engine, a.out_dir)
    run(a.icao, a.out,
        _parse_arm(a.arm_a) if a.arm_a else None,
        _parse_arm(a.arm_b) if a.arm_b else None)


if __name__ == "__main__":
    main()
