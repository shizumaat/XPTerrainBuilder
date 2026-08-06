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
* All law families, always, including the empty ones — an absent family
  line means the tool did not run, not that the family was clean.
* The ADJUDICATION section (owner ruling RULINGS ``d48bc0a``): the verdict
  is zero rows EXCLUDING the VERSION-DEFERRED classes, which are reported
  under their own heading and never dropped.  Instruments report, the law
  adjudicates — the register is ``check_grade.VERSION_DEFERRED_FAMILIES``
  and the split is ``check_grade.adjudication`` (one implementation; the
  tip battery used to subtract the deferred family by hand).
* AIRSIDE / GROUNDSIDE / MIXED per family, by the LAW's own role partition
  (``check_grade._is_groundside``).  MIXED is shown separately and counts
  against airside for acceptance ("airside is king").
* The worst-N rows with family, role pair, magnitude, grade/cap and site —
  absorbs the ``worst.py`` lane script.
* The sidecar's EVIDENCE fields: ruleset, seam-pin count, declared terrace
  joints, terrace certificates, triangle-plane unresolved count, and any
  ``unknown_keys`` the emitter has grown that no reader consumes yet.

* ``--zone-split`` — the WITHIN-SHAPE rows bucketed by FAN-RAMP ZONE
  membership (on a declared ramp piece / inside a zone / crossing one /
  unrelated).  A total cannot tell "the ramp law is granting relief where
  the defects are" from "…somewhere else"; this can.

* ``--magnitude-bands`` — every law-true row bucketed by SEVERITY
  (|de| / step height), default edges 0.01 / 0.1 / 1 / 10 m, configurable.
  A total says how many rows; the bands say what KIND of population they
  are, which is the reading that ranks ownership (the post-cycle-6 frame
  of record is stated in exactly these terms: 0.1-1 m 13,711 rows =
  45.1 %, 1-10 m 11,143 = 36.7 %, "82 % is in-band airside solver
  residual").  The first edge is also the materiality floor, so the
  below-floor rows are reported as their own band rather than mixed in.

Consolidated from (and replacing): ``scratchpad/*/census_lockstep.py``,
``scratchpad/refpull_interim/census.py``, ``scratchpad/testphase/census.py``,
``scratchpad/integrate/worst.py``, ``scratchpad/integrate/side.py``,
``scratchpad/fix2a/zone_split.py``, and the magnitude-band bucketing two
lanes wrote by hand (c6attr / c6tip — promote-on-reuse, RULINGS 7e90032).
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


#: DEFAULT MAGNITUDE BAND EDGES, metres.  The first edge is the campaign's
#: materiality floor (0.01 m, CLAUDE.md "convergence guards"): rows below it
#: are reported as their own band and never adjudicated away silently.  The
#: rest are the decades the frame-of-record readings are already stated in.
DEFAULT_BAND_EDGES = (0.01, 0.1, 1.0, 10.0)


def parse_band_edges(spec) -> tuple:
    """``"0.01,0.1,1,10"`` -> ``(0.01, 0.1, 1.0, 10.0)``.

    Edges must be positive and strictly ascending: a band table built on
    unsorted edges silently drops rows into the wrong bucket, and a report
    whose buckets do not partition its own population is the two-instruments
    trap in one table.
    """
    if spec is None or str(spec).strip() == "":
        return tuple(DEFAULT_BAND_EDGES)
    try:
        edges = tuple(float(p) for p in str(spec).replace(" ", "").split(",")
                      if p != "")
    except ValueError:
        raise SystemExit(
            f"REFUSING: --magnitude-bands {spec!r} is not a comma-separated "
            f"list of metre values (e.g. 0.01,0.1,1,10)") from None
    if not edges:
        raise SystemExit("REFUSING: --magnitude-bands needs at least one edge")
    if any(e <= 0 for e in edges):
        raise SystemExit(
            f"REFUSING: --magnitude-bands {spec!r} has a non-positive edge; "
            f"magnitudes are absolute values")
    if list(edges) != sorted(edges) or len(set(edges)) != len(edges):
        raise SystemExit(
            f"REFUSING: --magnitude-bands {spec!r} is not strictly ascending "
            f"— rows would land in the wrong band")
    return edges


def band_labels(edges) -> list:
    """The band labels for ``edges``, low to high.  ``len(edges) + 1`` of
    them: below the first edge, one per interval, and the open top."""
    def _n(v):
        return f"{v:g}"
    out = [f"<{_n(edges[0])}"]
    for lo, hi in zip(edges, edges[1:]):
        out.append(f"{_n(lo)}-{_n(hi)}")
    out.append(f">={_n(edges[-1])}")
    return out


def magnitude_bands(all_rows, cg, edges=DEFAULT_BAND_EDGES) -> dict:
    """``--magnitude-bands``: bucket the law-true rows by SEVERITY.

    WHY IT LIVES HERE.  Two lanes bucketed rows by magnitude by hand (the
    c6attr ownership ranking and the c6tip frame of record), which is the
    promotion signal — owner ruling 7e90032, promote-on-reuse.  It is a
    FLAG on the census and not a tool of its own for the reason the census
    exists: the population it buckets must be the law-true one, and a
    private copy of that frame is the census-wrapper defect.  Nothing here
    re-runs a check — it reads the rows ``census_one`` already has.

    THE QUESTION IT ANSWERS.  A total ranks nothing.  "30,402 rows" and
    "30,402 rows, 82 % of them between 0.1 m and 10 m" send work to
    different places: the first reads as a catastrophe, the second names
    an in-band solver residual with one owner.  Bands also separate the
    sub-materiality tail (below the first edge — the floor a convergence
    guard is entitled to stop at) from rows that are real.

    ``all_rows`` is the ``(family_key, row)`` sequence ``census_one``
    builds, so the bands PARTITION exactly the population the census
    reports: ``sum(band["n"]) == len(all_rows)``, twin-asserted.  Each
    band also carries the adjudicated/version-deferred split on the law's
    own register (``check_grade.VERSION_DEFERRED_FAMILIES``) — instruments
    report, the law adjudicates.
    """
    edges = tuple(edges)
    labels = band_labels(edges)

    def _index(mag: float) -> int:
        for i, e in enumerate(edges):
            if mag < e:
                return i
        return len(edges)

    n_bands = len(labels)
    counts = [Counter() for _ in range(n_bands)]
    worst = [0.0] * n_bands
    deferred = [0] * n_bands
    by_family: dict = {}
    for key, row in all_rows:
        mag = cg.row_magnitude(row)
        i = _index(mag)
        counts[i][cg.row_side(row)] += 1
        counts[i]["_n"] += 1
        worst[i] = max(worst[i], mag)
        if key in cg.VERSION_DEFERRED_FAMILIES:
            deferred[i] += 1
        row_counts = by_family.setdefault(key, [0] * n_bands)
        row_counts[i] += 1

    total = sum(c["_n"] for c in counts)
    bands = []
    for i, label in enumerate(labels):
        lo = 0.0 if i == 0 else edges[i - 1]
        hi = edges[i] if i < len(edges) else None
        bands.append({
            "label": label,
            "lo_m": lo,
            "hi_m": hi,
            "n": counts[i]["_n"],
            "pct": (round(100.0 * counts[i]["_n"] / total, 1)
                    if total else 0.0),
            "airside": counts[i].get("airside", 0),
            "groundside": counts[i].get("groundside", 0),
            "mixed": counts[i].get("mixed", 0),
            "unknown": counts[i].get("unknown", 0),
            "deferred": deferred[i],
            "adjudicated": counts[i]["_n"] - deferred[i],
            "worst_m": round(worst[i], 4),
            # The floor band is the one a convergence guard may stop at
            # (CLAUDE.md: "a residual below it is PASS-with-residual").
            "below_materiality": i == 0,
        })
    return {
        "edges_m": list(edges),
        "total": total,
        "bands": bands,
        "by_family": {k: dict(zip(labels, v))
                      for k, v in sorted(by_family.items()) if any(v)},
    }


def _both_buildings(step) -> bool:
    """The suite's step exemption (user 2026-06-20): two adjacent terminal
    pads are independent FLAT surfaces and may legitimately sit at different
    floor levels with a facade between them.  Applied here so the harness's
    step count is the same number ``test_pavement_grade`` caps."""
    return (step.way_v.tags.get("role") == "building"
            and step.way_e.tags.get("role") == "building")


def zone_split(osm: Path, cg, families: dict) -> dict:
    """``--zone-split``: bucket the WITHIN-SHAPE rows by FAN-RAMP ZONE
    membership.  Returns the section dict, or ``{}`` with a reason.

    WHY IT LIVES HERE.  It was a lane scratchpad script
    (``scratchpad/fix2a/zone_split.py``) and reached its second use, which
    is the promotion signal (CLAUDE.md, "Tool discipline" — owner ruling
    7e90032).  It is a FLAG on this tool and not a tool of its own for
    the reason that ruling exists: it needs the census's own law-true
    frame, and a copy of that frame is exactly the defect the census
    wrapper precedent cost (a wrapper that dropped ``terrace_joints_ll``
    reported lawful declared terraces as violations).  Nothing here
    re-runs a check — it reads the rows ``census_one`` already has.

    THE QUESTION IT ANSWERS.  The fan-ramp law declares ground that may
    carry 5 %.  Two things can be true and look identical in a total:
    the law is granting relief where the defects are, or it is granting
    relief somewhere else.  The buckets separate them:

      ramp_piece   the row is ON a declared ramp piece — it is judged at
                   the zone cap, so it is the LAW's own population
      in_zone      chord wholly inside a declared zone polygon
      crosses      chord enters and leaves a zone
      outside      no relation to any zone

    Measured with this, HECA's landed-but-inert law read: 808 zones,
    9 739 of 10 255 apron rows with neither end in one, 9 blocked by the
    whole-chord test.  That is the number that named the fix.
    """
    import json
    import math

    side_path = Path(str(osm) + ".axes.json")
    try:
        side = json.loads(side_path.read_text())
    except (OSError, ValueError):
        return {"reason": f"no readable sidecar at {side_path.name}"}
    anchor = side.get("anchor")
    if not anchor:
        return {"reason": "sidecar carries no anchor — no metre frame"}
    ll_to_m = cg._ll_to_m_factory({}, anchor=tuple(anchor))
    zones = cg._fan_ramp_zones_to_m(side.get("fan_ramp_zones"), ll_to_m)

    try:
        from shapely.geometry import LineString
        from shapely.ops import unary_union
    except ImportError:                                    # pragma: no cover
        return {"reason": "shapely unavailable"}

    union = (unary_union([p for (p, _c, _b, _pr) in zones])
             if zones else None)
    rows = families.get("within_shape") or []
    buckets = Counter()
    by_role = Counter()
    steeper_than_cap = 0
    cap = max((c for (_p, c, _b, _pr) in zones), default=0.0)
    for r in rows:
        tags = getattr(getattr(r, "way_a", None), "tags", {}) or {}
        if tags.get("o4_grade_law") == "fan_ramp":
            buckets["ramp_piece"] += 1
        elif union is None:
            buckets["outside"] += 1
        else:
            try:
                chord = LineString([r.pt_a, r.pt_b])
                if union.covers(chord):
                    buckets["in_zone"] += 1
                elif union.intersects(chord):
                    buckets["crosses"] += 1
                else:
                    buckets["outside"] += 1
            except Exception:                              # pragma: no cover
                buckets["outside"] += 1
        by_role["|".join(sorted(cg.row_roles(r)))] += 1
        if cap and getattr(r, "grade_pct", 0.0) / 100.0 > cap:
            steeper_than_cap += 1
    # HOW MANY PAIRS THE ZONE CAP ACTUALLY BINDS.  The count that says
    # whether a declared-ground grade law is INERT: a law can declare
    # square kilometres and price nothing, which is exactly what the
    # fan-ramp law did before its zones became shapes (808 zones, 170
    # edges).  Built from the ways the patch carries, through the law's
    # own ``shape_constraints`` — not estimated from vertex counts.
    ramp_pairs = ramp_ways = ramp_vertices = 0
    try:
        import auto_patch.grade_graph as _GG
        nodes, ways = cg._parse_osm(Path(osm))
        law_ctx = _GG.GradeContext(centerlines=[], routes=[])
        for w in ways:
            if (w.tags or {}).get("o4_grade_law") != "fan_ramp":
                continue
            ring = [ll_to_m(*nodes[n]) for n in w.nids if n in nodes]
            if len(ring) > 1 and ring[0] == ring[-1]:
                ring = ring[:-1]
            if len(ring) < 3:
                continue
            ramp_ways += 1
            ramp_vertices += len(ring)
            gs = _GG.GradeShape(role=(w.tags or {}).get("role", "apron"),
                                ring=ring, keys=list(range(len(ring))),
                                fan_ramp_zone=True)
            ramp_pairs += len(_GG.shape_constraints(gs, law_ctx).edges)
    except Exception as exc:                                # pragma: no cover
        ramp_pairs = -1
        ramp_ways = ramp_vertices = 0
        buckets["_pair_count_failed"] = repr(exc)[:80]

    return {
        "zones": len(zones),
        "ramp_ways": ramp_ways,
        "ramp_vertices": ramp_vertices,
        "ramp_law_pairs": ramp_pairs,
        "zone_area_m2": (round(float(union.area), 1) if union is not None
                         else 0.0),
        "zone_parts_area_m2": round(
            sum(float(p.area) for (p, _c, _b, _pr) in zones), 1),
        "caps": sorted({c for (_p, c, _b, _pr) in zones}),
        "within_rows": len(rows),
        "buckets": dict(buckets),
        # The rows a ramp cap CANNOT rescue however the zones are drawn.
        "steeper_than_zone_cap": steeper_than_cap,
        "top_role_pairs": dict(by_role.most_common(6)),
    }


def census_one(osm: Path, cg, *, want_bare: bool = False,
               top: int = 10, want_zone_split: bool = False,
               band_edges=None) -> dict:
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
    # DEFERRED ADJUDICATION (owner ruling RULINGS d48bc0a).  Instruments
    # report; the law adjudicates.  ``lawtrue`` stays the full measured
    # population — nothing is dropped — and ``adjudication`` carries the
    # verdict the acceptance gate is entitled to: zero rows EXCLUDING the
    # version-deferred classes, which appear under their own heading.  The
    # split is ``check_grade.adjudication`` (one implementation; the
    # battery used to do this subtraction by hand).
    adj = cg.adjudication(all_rows)
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
        "adjudication": adj,
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
    if want_zone_split:
        report["zone_split"] = zone_split(osm, cg, families)
    if band_edges is not None:
        report["magnitude_bands"] = magnitude_bands(all_rows, cg, band_edges)
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
    adj = rep.get("adjudication")
    if adj:
        a = adj["adjudicated_by_side"]
        print(f"\n  === ADJUDICATION (RULINGS {adj['ruling']}) ===")
        print(f"    ADJUDICATED {adj['adjudicated_total']}   "
              f"airside={a['airside']} groundside={a['groundside']} "
              f"mixed={a['mixed']}   verdict: "
              f"{'PASS' if adj['pass'] else 'FAIL'}")
        print(f"    VERSION-DEFERRED (reported, NOT adjudicated) "
              f"{adj['deferred_total']}:")
        for key, d in adj["deferred_families"].items():
            print(f"      {key:<24}{d['n']:>7}  {d['why']}")
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
    be = ev.get("band_excess")
    if isinstance(be, dict) and not be.get("error"):
        s = be.get("by_side") or {}
        print(f"  band membership (the BUILD's own report, evidence — "
              f"route_band lives in-memory and is not a census family): "
              f"{be.get('material', 0)} vertex(es) outside their band by > "
              f"{be.get('materiality_m', 0.01):g} m "
              f"(ceil={s.get('ceil', 0)} floor={s.get('floor', 0)} "
              f"pinned={s.get('pinned', 0)}, worst "
              f"{be.get('worst_m', 0.0)} m)")
    elif isinstance(be, dict):
        print(f"  band membership: NOT MEASURED this build "
              f"({be.get('error')})")
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

    mb = rep.get("magnitude_bands")
    if mb is not None:
        print("\n  === MAGNITUDE BANDS (--magnitude-bands) ===")
        print(f"    edges {mb['edges_m']} m; bands PARTITION the "
              f"{mb['total']} law-true row(s)")
        print(f"    {'BAND (m)':<12}{'n':>8}{'%':>7}{'airside':>9}{'gs':>7}"
              f"{'mixed':>7}{'adjud':>8}{'defer':>7}{'worst m':>10}")
        print("    " + "-" * 75)
        for b in mb["bands"]:
            tail = "  (below materiality floor)" if b["below_materiality"] \
                else ""
            print(f"    {b['label']:<12}{b['n']:>8}{b['pct']:>7.1f}"
                  f"{b['airside']:>9}{b['groundside']:>7}{b['mixed']:>7}"
                  f"{b['adjudicated']:>8}{b['deferred']:>7}"
                  f"{b['worst_m']:>10.3f}{tail}")
        if mb["by_family"]:
            print("    by family (nonzero only):")
            for key, row in mb["by_family"].items():
                cells = "  ".join(f"{lab}={n}" for lab, n in row.items() if n)
                print(f"      {key:<24}{cells}")

    zs = rep.get("zone_split")
    if zs is not None:
        print("\n  === FAN-RAMP ZONE SPLIT (--zone-split) ===")
        if zs.get("reason"):
            print(f"    not available: {zs['reason']}")
        else:
            print(f"    zones {zs['zones']} declared, union "
                  f"{zs['zone_area_m2']:,.0f} m² (parts sum "
                  f"{zs['zone_parts_area_m2']:,.0f} m² — zones OVERLAP, one "
                  f"per adjacent building pair), caps {zs['caps']}")
            print(f"    ramp PIECES {zs['ramp_ways']} "
                  f"({zs['ramp_vertices']} ring vertices) binding "
                  f"{zs['ramp_law_pairs']} law pair(s) at the zone cap "
                  f"— the number that says whether the law is INERT")
            b = zs["buckets"]
            print(f"    within-shape rows {zs['within_rows']}:")
            for k, label in (
                    ("ramp_piece", "ON a declared ramp piece (judged at "
                                   "the zone cap — the LAW's population)"),
                    ("in_zone", "chord wholly inside a zone polygon"),
                    ("crosses", "chord enters and leaves a zone"),
                    ("outside", "no relation to any zone")):
                print(f"      {k:<12}{b.get(k, 0):>8}  {label}")
            print(f"    rows already steeper than the zone cap: "
                  f"{zs['steeper_than_zone_cap']} — no ramp cap rescues "
                  f"these however the zones are drawn")
            print("    top role pairs: " + ", ".join(
                f"{k}={v}" for k, v in zs["top_role_pairs"].items()))


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
    if all(r.get("adjudication") for r in reports):
        adjt = [r["adjudication"]["adjudicated_total"] for r in reports]
        deft = [r["adjudication"]["deferred_total"] for r in reports]
        print(f"  {'ADJUDICATED':<24}" + "".join(f"{c:>18}" for c in adjt)
              + f"{adjt[-1] - adjt[0]:>+15d}")
        print(f"  {'(version-deferred)':<24}"
              + "".join(f"{c:>18}" for c in deft)
              + f"{deft[-1] - deft[0]:>+15d}")


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
    ap.add_argument("--magnitude-bands", nargs="?", const="", default=None,
                    metavar="EDGES",
                    help="also bucket every law-true row by SEVERITY "
                         "(|de| / step height) into magnitude bands — "
                         "default edges 0.01,0.1,1,10 m, or pass your own "
                         "ascending comma-separated metre list.  The bands "
                         "PARTITION the census's own population (below the "
                         "first edge is the materiality floor's own band) "
                         "and each carries the airside/groundside/mixed and "
                         "adjudicated/version-deferred splits — the reading "
                         "that ranks ownership rather than counting rows")
    ap.add_argument("--zone-split", action="store_true",
                    help="also bucket the WITHIN-SHAPE rows by FAN-RAMP "
                         "ZONE membership (on a declared ramp piece / "
                         "inside a zone / crossing one / unrelated) — the "
                         "reading that says whether the ramp law is "
                         "granting relief where the defects actually are")
    args = ap.parse_args(argv)

    band_edges = (parse_band_edges(args.magnitude_bands)
                  if args.magnitude_bands is not None else None)

    cg = load_check_grade()
    reports = []
    for osm in args.patches:
        if not osm.exists():
            raise SystemExit(f"REFUSING: no such patch {osm}")
        try:
            rep = census_one(osm, cg, want_bare=args.bare, top=args.top,
                             want_zone_split=args.zone_split,
                             band_edges=band_edges)
        except FileNotFoundError as exc:
            raise SystemExit(
                f"REFUSING: {exc}\n"
                f"  A census without the sidecar is the CONTEXT-FREE frame, "
                f"which overcounts by construction (588 rows vs 0 actionable "
                f"at KCLT).  If you only want that number for the record, "
                f"run tools/check_grade.py directly — it says so in its own "
                f"output.") from None
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
