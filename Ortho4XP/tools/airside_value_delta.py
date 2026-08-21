#!/usr/bin/env python3
"""THE AIRSIDE VALUE DELTA between two emitted patches.

    venv/bin/python tools/airside_value_delta.py A.osm B.osm
        [--tol 0.01] [--top 20] [--json OUT.json]

THE QUESTION IT ANSWERS.  "Did this lane move airside?"  A census A/B
cannot answer it: a value can move by 0.13 m and cross no law threshold,
so the row tables read IDENTICAL while airside has in fact been pulled —
which is exactly what "airside is king" (RULINGS 2026-07-30) forbids and
what an airside-frozen lane must prove it did not do.  ``census_rows_diff``
joins ROWS; ``arm_site_read`` answers one named PLACE; ``osm_site`` dumps
one way.  This is the whole-patch VALUE read the airside-frozen posture is
adjudicated on.

**IT MEASURES NO LAW AND COUNTS NO DEFECTS.**  Geometry and altitudes come
from the harness library's own reader (``check_grade._parse_osm``), the
groundside partition from ``check_grade._GROUNDSIDE_ROLES``, the road
family from ``check_grade._ROAD_FAMILY_ROLES``, and the solve's own node
population from ``solver_primitives.PAVEMENT_ROLES`` + ``solve_stage``.
Every set is IMPORTED, never re-spelled — the census-wrapper precedent
(RULINGS ``7e90032``).  Defect counts come from ``harness/census.py`` and
nowhere else.

THE JOIN IS CANONICAL, NEVER PROXIMITY.  Nodes are keyed by their
11-decimal lat/lon spelling — the identity that carries solver node ids
exactly (memory ``canonical-identity-join``).  A node present in only one
arm is an ADDED or REMOVED vertex and is reported in its own column: it is
not a moved value, and folding it into one would turn every densification
into a phantom pull.

TWO FRAMES, BOTH PRINTED, because "airside" names two populations here and
quoting one number would be the two-instruments trap (memory
``two-instruments-one-assumed-population``):

  ROW-SIDE      every role NOT in ``check_grade._GROUNDSIDE_ROLES`` — the
                census's own ``row_side`` partition.  It counts the
                SOFT-RECEIVER terrain roles (``graded_strip``,
                ``boundary``, ``retaining_wall``, the clearance cuts) as
                airside, and those ADOPT their value from whatever
                pavement they abut, so a lawful groundside move carries
                them.  This is the frame an airside ROW COUNT lives in.
  SOLVE-OWNED   a node claimed by a shape whose role is in
                ``PAVEMENT_ROLES`` and whose stage is A — the variables
                the airside solve actually fixes.  This is the frame the
                claim "C3 never moves an airside value the airside solve
                has fixed" is about, and the smaller of the two.

THE ROAD-WELD SPLIT.  Each moved solve-owned node is additionally
classified by whether any way claiming it is in the ROAD FAMILY: a shared
(welded) vertex is the channel a groundside pull travels down, and a moved
node with NO road contact is the soft-receiver adoption class instead.
That split is the difference between "the lane pulled airside" and "the
lane moved groundside and airside's neighbours followed", and it is a
JOIN, not a guess.

A node whose altitude is absent on either side is reported, never counted
as 0.0 — no authority claimed it is a real state.

Promoted 2026-08-20 from the C3-rework lane's scratchpad reader on its
SECOND use (RULINGS ``7e90032``, promote-on-reuse): first the lane's own
airside-frozen proof, then the attribution of its 34-node residual.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Materiality floor for an elevation class (RULINGS, convergence guards).
DEFAULT_TOL_M = 0.01


def _check_grade():
    """The harness library, loaded the way the census loads it."""
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    mod = sys.modules.get("_avd_check_grade")
    if mod is not None:
        return mod
    spec = importlib.util.spec_from_file_location(
        "_avd_check_grade", ROOT / "tools" / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_avd_check_grade"] = mod
    spec.loader.exec_module(mod)
    return mod


def role_sets():
    """``(groundside, solve_owned_airside, road_family)`` — all IMPORTED."""
    cg = _check_grade()
    from auto_patch.elevation_per_surface.solver_primitives import (
        PAVEMENT_ROLES)
    from auto_patch.solve_stage import stage_of_role, STAGE_A
    return (frozenset(cg._GROUNDSIDE_ROLES),
            frozenset(r for r in PAVEMENT_ROLES
                      if stage_of_role(r) == STAGE_A),
            frozenset(cg._ROAD_FAMILY_ROLES))


def read_patch(path):
    """``{key: (roles, alt_or_None)}`` keyed by the canonical 11-decimal
    lat/lon spelling.  ``alt`` is the way-carried value at that node; when
    two ways disagree the EMITTED consensus has already run, so they agree
    by construction and ``max`` simply picks the one value present."""
    cg = _check_grade()
    nodes, ways = cg._parse_osm(Path(path))
    roles: dict = {}
    alt: dict = {}
    for w in ways:
        for nid, e in zip(w.nids, w.elevs):
            ll = nodes.get(nid)
            if ll is None:
                continue
            key = (f"{ll[0]:.11f}", f"{ll[1]:.11f}")
            roles.setdefault(key, set()).add(w.role)
            if e is not None:
                v = round(float(e), 6)
                alt[key] = v if key not in alt else max(alt[key], v)
    return {k: (frozenset(rs), alt.get(k)) for k, rs in roles.items()}


def _frame_members(patch, frame, gs, solve_air):
    if frame == "row-side":
        return {k for k, (rs, _a) in patch.items() if not (rs <= gs)}
    return {k for k, (rs, _a) in patch.items() if rs & solve_air}


def compare(a_path, b_path, tol_m: float = DEFAULT_TOL_M) -> dict:
    """The result the CLI prints — one function, so the tool and any
    caller read one number (the CLI's JSON IS this dict)."""
    gs, solve_air, road = role_sets()
    A, B = read_patch(a_path), read_patch(b_path)
    out = {"a": str(a_path), "b": str(b_path), "tol_m": float(tol_m),
           "frames": {}}
    for frame in ("row-side", "solve-owned"):
        sa = _frame_members(A, frame, gs, solve_air)
        sb = _frame_members(B, frame, gs, solve_air)
        both = sa & sb
        moved, no_value = [], 0
        for k in sorted(both):
            va, vb = A[k][1], B[k][1]
            if va is None or vb is None:
                no_value += 1
                continue
            d = abs(va - vb)
            if d > tol_m:
                rs = tuple(sorted(A[k][0] | B[k][0]))
                moved.append({"dz_m": round(d, 6), "lat": k[0], "lon": k[1],
                              "roles": rs,
                              "welded_to_road": bool(set(rs) & road)})
        moved.sort(key=lambda r: -r["dz_m"])
        out["frames"][frame] = {
            "n_a": len(sa), "n_b": len(sb), "n_both": len(both),
            "a_only": len(sa - sb), "b_only": len(sb - sa),
            "n_moved": len(moved),
            "worst_dz_m": (moved[0]["dz_m"] if moved else 0.0),
            "n_no_value": no_value,
            "welded_to_road": sum(1 for r in moved if r["welded_to_road"]),
            "no_road_contact": sum(1 for r in moved
                                   if not r["welded_to_road"]),
            "moved": moved,
        }
    return out


def _print(res, top: int) -> None:
    print("=== AIRSIDE VALUE DELTA (verbatim read; no law, no defect "
          "counts) ===")
    print(f"  A {res['a']}")
    print(f"  B {res['b']}")
    print(f"  materiality {res['tol_m']} m; canonical 11-decimal lat/lon "
          f"join (never proximity)")
    for frame, f in res["frames"].items():
        label = ("row-side (census row_side partition; soft-receiver "
                 "terrain roles included)" if frame == "row-side"
                 else "solve-owned airside pavement (PAVEMENT_ROLES ∩ "
                      "stage A)")
        print(f"\n  FRAME {frame} — {label}")
        print(f"    nodes: A={f['n_a']} B={f['n_b']} in BOTH={f['n_both']}"
              f"   A-only={f['a_only']} B-only={f['b_only']}"
              f"  (added/removed vertices, NOT moved values)")
        print(f"    MOVED by > {res['tol_m']} m: {f['n_moved']}"
              f"   WORST |dz| = {f['worst_dz_m']:.4f} m")
        print(f"    of those: {f['welded_to_road']} welded to the road "
              f"family, {f['no_road_contact']} with no road contact "
              f"(soft-receiver adoption)")
        if f["n_no_value"]:
            print(f"    nodes with NO emitted altitude on one side: "
                  f"{f['n_no_value']} (reported, never counted as 0.0)")
        for r in f["moved"][:top]:
            print(f"      |dz|={r['dz_m']:.4f} m @({r['lat']},{r['lon']}) "
                  f"roles={r['roles']}"
                  f"{' WELDED-TO-ROAD' if r['welded_to_road'] else ''}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    ap.add_argument("--tol", type=float, default=DEFAULT_TOL_M,
                    help="materiality floor in metres (default 0.01)")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    for p in (args.a, args.b):
        if not p.is_file():
            print(f"REFUSED: not a file: {p}", file=sys.stderr)
            return 2
    res = compare(args.a, args.b, args.tol)
    _print(res, args.top)
    if args.json:
        args.json.write_text(json.dumps(res, indent=1))
        print(f"\nJSON -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
