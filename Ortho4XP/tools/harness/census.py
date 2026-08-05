"""THE CENSUS — full law-true defect census for one or more emitted patches.

    venv/bin/python tools/harness/census.py PATCH.osm [PATCH.osm ...]
        [--json OUT.json] [--top 10] [--bare] [--quiet]

Run it from ``Ortho4XP/``.  Every lane measures with THIS tool; a
lane-private census wrapper is a defect (see CLAUDE.md, "The standard test
harness").  The two frame errors that made this tool necessary were both
produced by hand-written copies of its innards:

* one lane's wrapper omitted ``terrace_joints_ll`` — it judged apron
  terraces that the build had declared lawful as grade violations;
* another omitted ``ruleset`` (so an FAA airport was censused under ICAO
  law) *and* enumerated only 12 of the 21 law families, reporting 9.

Both are now impossible by construction, not by discipline:

* every law keyword comes from ``check_grade.law_context_from_sidecar`` —
  ONE reader, wired to the sidecar contract in one place;
* every family comes from ``run_checks(family_out=...)``, which the law
  reader itself fills as it emits — nothing here enumerates families, and
  ``tests/test_harness.py`` asserts the register covers all 21 and that
  the family rows partition the returned lists exactly.

WHAT IT REPORTS

* LAW-TRUE counts — the frame ``tests/test_pavement_grade.py`` judges in
  (patch's own sidecar: axes/routes, anchor, seam pins, solver mesh,
  crown field, baked pair caps, declared terrace joints, region ruleset).
  These are the only numbers that may be quoted as defect counts.
* BARE counts (``--bare``) — ``run_checks`` with no context at all.
  Overcounts by construction (memory ``check-grade-needs-law-true-frame``);
  reported for the record, never as a defect count.
* All 21 families, always, including the empty ones — an absent family
  line means the tool did not run, not that the family was clean.
* AIRSIDE / GROUNDSIDE / MIXED per family, by the LAW's own role partition
  (``check_grade._is_groundside``).  MIXED is shown separately and counts
  against airside for acceptance ("airside is king").
* The worst-N rows with family, role pair, magnitude, grade/cap and site —
  absorbs the ``worst.py`` lane script.
* The sidecar's EVIDENCE fields: ruleset, seam-pin count, declared terrace
  joints, terrace certificates, triangle-plane unresolved count, and any
  ``unknown_keys`` the emitter has grown that no reader consumes yet.

Consolidated from (and replacing): ``scratchpad/*/census_lockstep.py``,
``scratchpad/refpull_interim/census.py``, ``scratchpad/testphase/census.py``,
``scratchpad/integrate/worst.py``, ``scratchpad/integrate/side.py``.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_check_grade():
    """Load ``tools/check_grade.py`` from THIS tree (never an installed copy).

    Loaded by path rather than imported so a census always measures with the
    tree it was invoked from — a lane that runs the harness from its worktree
    gets its own law, which is the whole point of an A/B.
    """
    for p in (ROOT / "src", ROOT, ROOT / "tests", ROOT / "tools"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location(
        "harness_check_grade", ROOT / "tools" / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _both_buildings(step) -> bool:
    """The suite's step exemption (user 2026-06-20): two adjacent terminal
    pads are independent FLAT surfaces and may legitimately sit at different
    floor levels with a facade between them.  Applied here so the harness's
    step count is the same number ``test_pavement_grade`` caps."""
    return (step.way_v.tags.get("role") == "building"
            and step.way_e.tags.get("role") == "building")


def census_one(osm: Path, cg, *, want_bare: bool = False,
               top: int = 10) -> dict:
    """The census of ONE patch.  Returns the report dict; prints nothing."""
    families: dict = {}
    within, cross, steps = cg.run_checks_law_true(
        osm, family_out=families, quiet=True, top_n=0)

    steps_kept = [s for s in steps if not _both_buildings(s)]
    evidence = cg.sidecar_evidence(osm)
    declared = families.get("_ruleset_declared")
    active = families.get("_ruleset_active")

    rows_by_family = {}
    for key, title, bucket in cg.LAW_FAMILIES:
        rows = families.get(key, [])
        if key in ("vertex_to_edge_step", "mid_edge_step"):
            rows = [s for s in rows if not _both_buildings(s)]
        rows_by_family[key] = (title, bucket, rows)

    fam_report = []
    for key, (title, bucket, rows) in rows_by_family.items():
        sides = Counter(cg.row_side(r) for r in rows)
        worst = max(rows, key=cg.row_magnitude, default=None)
        fam_report.append({
            "family": key,
            "title": title,
            "bucket": bucket,
            "n": len(rows),
            "airside": sides.get("airside", 0),
            "groundside": sides.get("groundside", 0),
            "mixed": sides.get("mixed", 0),
            "unknown": sides.get("unknown", 0),
            "worst_m": round(cg.row_magnitude(worst), 4) if worst else None,
            "worst_roles": ("|".join(sorted(cg.row_roles(worst)))
                            if worst is not None else None),
        })

    all_rows = [(k, r) for k, (_t, _b, rs) in rows_by_family.items()
                for r in rs]
    all_rows.sort(key=lambda kr: -cg.row_magnitude(kr[1]))
    worst_rows = []
    for key, r in all_rows[:top]:
        grade = getattr(r, "grade_pct", None)
        cap = getattr(r, "cap_pct", None)
        worst_rows.append({
            "family": key,
            "roles": "|".join(sorted(cg.row_roles(r))),
            "side": cg.row_side(r),
            "magnitude_m": round(cg.row_magnitude(r), 4),
            "grade_pct": (round(float(grade), 3) if grade is not None
                          else None),
            "cap_pct": round(float(cap), 3) if cap is not None else None,
            "lat": getattr(r, "lat", None),
            "lon": getattr(r, "lon", None),
        })

    # CLASS table (family::role-pair), the lockstep census's own column —
    # kept because every drain list in this repo is keyed by it.
    classes = Counter()
    for key, r in all_rows:
        classes[f"{key}::{'|'.join(sorted(cg.row_roles(r)))}"] += 1

    sides_total = Counter(cg.row_side(r) for _k, r in all_rows)
    report = {
        "patch": str(osm),
        "ruleset_declared": declared,
        "ruleset_active": active,
        "lawtrue": {
            "total": len(all_rows),
            "within": len(within),
            "cross": len(cross),
            "steps": len(steps_kept),
            "steps_raw": len(steps),
            "airside": sides_total.get("airside", 0),
            "groundside": sides_total.get("groundside", 0),
            "mixed": sides_total.get("mixed", 0),
            "unknown": sides_total.get("unknown", 0),
        },
        "families": fam_report,
        "worst": worst_rows,
        "classes": dict(classes.most_common()),
        "evidence": evidence,
    }

    if want_bare:
        # BARE frame: no context at all.  A separate module instance so the
        # ruleset global the law-true run set cannot leak into it.
        cg_bare = load_check_grade()
        bw, bc, bs = cg_bare.run_checks(Path(osm), max_grade_pct=1.5,
                                        top_n=0, quiet=True)
        report["bare"] = {"within": len(bw), "cross": len(bc),
                          "steps": len(bs),
                          "total": len(bw) + len(bc) + len(bs)}
    return report


def print_report(rep: dict, top: int) -> None:
    lt = rep["lawtrue"]
    print(f"\n=== CENSUS {rep['patch']} ===")
    if rep["ruleset_declared"]:
        print(f"  ruleset: {rep['ruleset_declared']!r}   (DECLARED by the "
              f"patch sidecar — the authority the BUILD ran under)")
    else:
        print(f"  ruleset: {rep['ruleset_active']!r}   !! NOT DECLARED — "
              f"this patch's sidecar carries no 'ruleset' key, so it "
              f"predates the FAA/ICAO split and was judged under the "
              f"DEFAULT.  Rebuild for a law-true judgment.")
    print(f"  LAW-TRUE TOTAL {lt['total']}   within={lt['within']} "
          f"cross={lt['cross']} steps={lt['steps']} "
          f"(raw {lt['steps_raw']}, building↔building exempt)")
    print(f"  sides: airside={lt['airside']} groundside={lt['groundside']} "
          f"mixed={lt['mixed']} unknown={lt['unknown']}   "
          f"(mixed counts AGAINST airside — airside is king)")
    if "bare" in rep:
        b = rep["bare"]
        print(f"  BARE (context-free, OVERCOUNTS — never a defect count): "
              f"total={b['total']} within={b['within']} cross={b['cross']} "
              f"steps={b['steps']}")
    ev = rep.get("evidence") or {}
    print(f"  sidecar evidence: seam_pins={ev.get('seam_pin_count')} "
          f"terrace_joints={ev.get('terrace_joint_count')} "
          f"terrace_certificates={ev.get('terrace_certificate_count')} "
          f"triangle_plane_unresolved="
          f"{ev.get('triangle_plane_unresolved')}")
    if ev.get("unknown_keys"):
        print(f"  !! sidecar carries key(s) NO reader consumes: "
              f"{ev['unknown_keys']} — the emitter grew a field the law "
              f"register does not know (fix check_grade.SIDECAR_*_KEYS)")

    print(f"\n  {'FAMILY':<24}{'n':>7}{'airside':>9}{'gs':>6}{'mixed':>7}"
          f"{'worst m':>10}  title")
    print("  " + "-" * 96)
    for f in rep["families"]:
        flag = " " if f["n"] == 0 else "*"
        worst = f"{f['worst_m']:.3f}" if f["worst_m"] is not None else "-"
        print(f" {flag}{f['family']:<24}{f['n']:>7}{f['airside']:>9}"
              f"{f['groundside']:>6}{f['mixed']:>7}{worst:>10}  "
              f"{f['title'][:40]}")
    print(f"  (all {len(rep['families'])} law families listed, empty ones "
          f"included — an absent line means the tool did not run)")

    if rep["worst"]:
        print(f"\n  === worst {min(top, len(rep['worst']))} rows "
              f"(by |de| / step height) ===")
        for r in rep["worst"]:
            extra = ""
            if r["grade_pct"] is not None:
                extra = f" grade={r['grade_pct']:.2f}%" + (
                    f"/cap={r['cap_pct']:.2f}%" if r["cap_pct"] is not None
                    else "")
            site = ""
            if r["lat"] is not None and r["lon"] is not None:
                site = f" @({r['lat']:.5f},{r['lon']:.5f})"
            print(f"    {r['family']:<22}{r['roles']:<34}"
                  f"{r['side']:<11}|de|={r['magnitude_m']:7.3f} m"
                  f"{extra}{site}")


def print_compare(reports: list) -> None:
    """Side-by-side family table across patches — the A/B reading."""
    if len(reports) < 2:
        return
    labels = [Path(r["patch"]).stem[-16:] for r in reports]
    print(f"\n=== A/B: {len(reports)} patches ===")
    print(f"  {'FAMILY':<24}" + "".join(f"{lab:>18}" for lab in labels)
          + f"{'Δ last-first':>15}")
    print("  " + "-" * (24 + 18 * len(labels) + 15))
    keys = [f["family"] for f in reports[0]["families"]]
    for key in keys:
        cells = [next(f["n"] for f in r["families"] if f["family"] == key)
                 for r in reports]
        if not any(cells):
            continue
        print(f"  {key:<24}" + "".join(f"{c:>18}" for c in cells)
              + f"{cells[-1] - cells[0]:>+15d}")
    tot = [r["lawtrue"]["total"] for r in reports]
    print(f"  {'TOTAL':<24}" + "".join(f"{c:>18}" for c in tot)
          + f"{tot[-1] - tot[0]:>+15d}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patches", nargs="+", type=Path,
                    help="emitted patch .osm file(s); each needs its "
                         ".axes.json sidecar next to it")
    ap.add_argument("--json", type=Path, default=None,
                    help="write the full report(s) here as JSON")
    ap.add_argument("--top", type=int, default=10,
                    help="worst-N rows to print (default 10)")
    ap.add_argument("--bare", action="store_true",
                    help="also run the context-free frame (overcounts; "
                         "for the record only)")
    ap.add_argument("--quiet", action="store_true",
                    help="JSON only, no table")
    args = ap.parse_args(argv)

    cg = load_check_grade()
    reports = []
    for osm in args.patches:
        if not osm.exists():
            raise SystemExit(f"REFUSING: no such patch {osm}")
        rep = census_one(osm, cg, want_bare=args.bare, top=args.top)
        reports.append(rep)
        if not args.quiet:
            print_report(rep, args.top)
    if not args.quiet:
        print_compare(reports)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(
            reports[0] if len(reports) == 1 else reports, indent=1))
        print(f"\nJSON -> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
