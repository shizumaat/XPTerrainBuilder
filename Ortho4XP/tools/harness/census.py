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
* BARE counts (``--bare``) — ``run_checks`` with no context at all, and
  with no registered step exemption applied.  Reported alongside the
  law-true total AND their difference, so the size of the gap between the
  two frames is a number in the report rather than an adjective
  (memory ``check-grade-needs-law-true-frame``).  Never a defect count.
* THE FRAME every number was taken in (RULINGS 2026-08-06 "Instrument
  truth is law"): the patch's own build provenance decoded from its
  ``<osm>`` root (sha, dirty flag, gate config, build time —
  ``auto_patch.provenance.parse_patch_provenance``, one decoder) and the
  law-true numeric knobs (``check_grade.LAW_TRUE_KNOBS``).  Without these
  two census JSONs from two trees are indistinguishable.
* The registered STEP EXEMPTIONS applied, by name and count
  (``check_grade.step_exempt`` / ``STEP_EXEMPTIONS`` — ONE authority, also
  read by the acceptance gate; it used to be a hand-written closure in
  both files at once).
* All law families, always, including the empty ones — an absent family
  line means the tool did not run, not that the family was clean.
* The ADJUDICATION section (owner ruling RULINGS ``d48bc0a``): the verdict
  is zero rows EXCLUDING the VERSION-DEFERRED classes, which are reported
  under their own heading and never dropped.  Instruments report, the law
  adjudicates — the register is ``check_grade.VERSION_DEFERRED_FAMILIES``
  and the split is ``check_grade.adjudication`` (one implementation; the
  tip battery used to subtract the deferred family by hand).
* AIRSIDE / GROUNDSIDE / MIXED per family, by the LAW's own role partition
  (``check_grade._is_groundside``).  MIXED is shown separately, and the
  ruling that a mixed row counts against airside ("airside is king") is
  APPLIED, not merely stated: ``airside_for_acceptance = airside + mixed``
  is reported for both the law-true and the adjudicated populations.
* The worst-N rows with family, role pair, magnitude, grade/cap and site —
  absorbs the ``worst.py`` lane script.
* The sidecar's EVIDENCE fields: ruleset, seam-pin count, declared terrace
  joints, terrace certificates, triangle-plane unresolved count, and any
  ``unknown_keys`` the emitter has grown that no reader consumes yet.

* ``--zone-split`` — the WITHIN-SHAPE rows bucketed by FAN-RAMP ZONE
  membership (on a declared ramp piece / inside a zone / crossing one /
  unrelated).  A total cannot tell "the ramp law is granting relief where
  the defects are" from "…somewhere else"; this can.

Consolidated from (and replacing): ``scratchpad/*/census_lockstep.py``,
``scratchpad/refpull_interim/census.py``, ``scratchpad/testphase/census.py``,
``scratchpad/integrate/worst.py``, ``scratchpad/integrate/side.py``,
``scratchpad/fix2a/zone_split.py``.
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


def load_provenance_reader():
    """``auto_patch.provenance.parse_patch_provenance``, or ``None``.

    Imported defensively and by name so a tree without the module (or a
    reader whose import raises) degrades to an explicit ``provenance:
    null`` with a stated reason rather than crashing a census.  ``ROOT/src``
    is already on ``sys.path`` after ``load_check_grade``; this adds it
    itself so the order of calls does not matter.
    """
    src = str(ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        from auto_patch.provenance import parse_patch_provenance
    except Exception:                                      # pragma: no cover
        return None
    return parse_patch_provenance


def patch_provenance(osm: Path) -> dict:
    """THE PATCH'S FRAME STAMP — ``{"provenance": …, "reason": …}``.

    RULINGS 2026-08-06 "Instrument truth is law", binding point 3: every
    reported number carries its frame.  A census JSON without this is
    indistinguishable from a census JSON of the same airport taken in
    another tree, at another sha, with another gate configuration — and
    equating two such numbers is the two-instruments trap by construction.

    The stamp is already ON the patch: ``PavementLayout.to_osm`` writes it
    to the ``<osm>`` root and ``auto_patch.provenance.parse_patch_provenance``
    is its ONE decoder (``tools/patch_provenance.py`` is the CLI over the
    same function).  Nothing is re-derived here.

    ``provenance`` is ``None`` — never absent, never a crash — whenever the
    stamp cannot be read, and ``reason`` says which of the two verified
    cases applies: the decoder is unavailable, or the decoder returned no
    stamp for this file.
    """
    reader = load_provenance_reader()
    if reader is None:                                     # pragma: no cover
        return {"provenance": None,
                "reason": "auto_patch.provenance not importable from "
                          f"{ROOT / 'src'}"}
    try:
        prov = reader(str(osm))
    except Exception as exc:                               # pragma: no cover
        return {"provenance": None,
                "reason": f"parse_patch_provenance raised {exc!r}"}
    if not prov:
        return {"provenance": None,
                "reason": "no o4_provenance_* attributes on the <osm> root"}
    return {"provenance": prov, "reason": None}


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
    #
    # FRAME (RULINGS 2026-08-06, binding point 3).  This count is taken in
    # a CONTEXT-FREE ``GradeContext`` — no centerlines, no routes — while
    # the census's own rows above come from ``run_checks_law_true`` in the
    # sidecar's real axes/routes frame.  Two frames in one report is the
    # two-instruments trap, so the frame is STAMPED, in the dict
    # (``law_ctx_frame``) and in the printed line, rather than left for the
    # reader to infer.  It is stamped rather than switched because (a) the
    # question is shape-local — how many pairs does THIS ring bind under
    # the shape law — and the empty context answers it deterministically,
    # and (b) switching would move a number that has no known-answer twin
    # telling us what the new value should be, which is the untwinned-
    # instrument defect this sweep exists to remove.  Feeding the sidecar's
    # real context is a follow-up that must land WITH its twin.
    ramp_pairs = ramp_ways = ramp_vertices = 0
    law_ctx_frame = "context-free GradeContext(centerlines=[], routes=[])"
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

    union_area = round(float(union.area), 1) if union is not None else 0.0
    parts_area = round(sum(float(p.area) for (p, _c, _b, _pr) in zones), 1)
    return {
        "zones": len(zones),
        "ramp_ways": ramp_ways,
        "ramp_vertices": ramp_vertices,
        "ramp_law_pairs": ramp_pairs,
        "ramp_law_pairs_frame": law_ctx_frame,
        "zone_area_m2": union_area,
        "zone_parts_area_m2": parts_area,
        # parts − union.  The two areas were already both in the report and
        # the printed line asserted a CAUSE for their difference ("zones
        # OVERLAP, one per adjacent building pair") that nothing here
        # measures.  The difference itself is arithmetic on two numbers the
        # section already holds, so it is reported as a number.
        "zone_overlap_m2": round(parts_area - union_area, 1),
        "caps": sorted({c for (_p, c, _b, _pr) in zones}),
        "within_rows": len(rows),
        "buckets": dict(buckets),
        # Rows whose measured grade exceeds ``cap_bound`` — the MAXIMUM over
        # the caps THIS patch's sidecar declares.  Reported with the bound so
        # the number carries the caps it was taken at; the bound is None (and
        # so is the count) when the sidecar declares no cap, because "steeper
        # than nothing" is not a question with an answer.
        "steeper_than_zone_cap": steeper_than_cap if cap else None,
        "steeper_than_zone_cap_bound": cap if cap else None,
        "top_role_pairs": dict(by_role.most_common(6)),
    }


def census_one(osm: Path, cg, *, want_bare: bool = False,
               top: int = 10, want_zone_split: bool = False) -> dict:
    """The census of ONE patch.  Returns the report dict; prints nothing."""
    families: dict = {}
    within, cross, steps = cg.run_checks_law_true(
        osm, family_out=families, quiet=True, top_n=0)

    # THE STEP EXEMPTION comes from the law register, not from a copy here
    # (``check_grade.step_exempt`` / ``STEP_EXEMPTIONS``).  It used to be a
    # closure in this file AND a second, hand-written closure in
    # ``tests/test_pavement_grade.py`` — one law, two copies, the
    # census-wrapper defect class.
    steps_kept = [s for s in steps if not cg.step_exempt(s)]
    exempt_by_rule = Counter()
    evidence = cg.sidecar_evidence(osm)
    declared = families.get("_ruleset_declared")
    active = families.get("_ruleset_active")

    rows_by_family = {}
    for key, title, bucket in cg.LAW_FAMILIES:
        rows = families.get(key, [])
        if key in cg.STEP_EXEMPT_FAMILIES:
            kept = []
            for s in rows:
                rule = cg.step_exempt(s)
                if rule:
                    exempt_by_rule[rule] += 1
                else:
                    kept.append(s)
            rows = kept
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
    prov = patch_provenance(osm)
    report = {
        "patch": str(osm),
        # THE FRAME (RULINGS 2026-08-06, binding point 3).  Two census JSONs
        # from two trees used to be indistinguishable: same keys, same
        # shape, nothing saying which sha, which gates, or which numeric
        # law knobs produced them.  Both halves are stamped here — the
        # patch's own build provenance and the law-true knob frame the
        # counts were taken in (``check_grade.LAW_TRUE_KNOBS``, read from
        # the module, never re-typed).
        "provenance": prov["provenance"],
        "provenance_reason": prov["reason"],
        "law_true_knobs": dict(cg.LAW_TRUE_KNOBS),
        "ruleset_declared": declared,
        "ruleset_active": active,
        "lawtrue": {
            "total": len(all_rows),
            "within": len(within),
            "cross": len(cross),
            "steps": len(steps_kept),
            "steps_raw": len(steps),
            "steps_exempt_by_rule": dict(exempt_by_rule),
            "airside": sides_total.get("airside", 0),
            "groundside": sides_total.get("groundside", 0),
            "mixed": sides_total.get("mixed", 0),
            "unknown": sides_total.get("unknown", 0),
            # "AIRSIDE IS KING" (RULINGS, owner standing): a MIXED row
            # counts AGAINST airside for acceptance.  The rule was stated
            # in the printed line and applied to no number; this is the
            # number it names.
            "airside_for_acceptance": (sides_total.get("airside", 0)
                                       + sides_total.get("mixed", 0)),
        },
        "adjudication": adj,
        "adjudicated_airside_for_acceptance": (
            adj["adjudicated_by_side"]["airside"]
            + adj["adjudicated_by_side"]["mixed"]),
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
    return report


def print_report(rep: dict, top: int) -> None:
    lt = rep["lawtrue"]
    print(f"\n=== CENSUS {rep['patch']} ===")
    # FRAME STAMP (RULINGS 2026-08-06, binding point 3) — the tree and gate
    # configuration the patch was BUILT by, decoded from its own <osm> root
    # by ``auto_patch.provenance.parse_patch_provenance``.
    prov = rep.get("provenance")
    if prov:
        print(f"  frame: sha={prov.get('sha') or 'absent'} "
              f"dirty={prov.get('dirty')} built={prov.get('built') or '?'} "
              f"icao={prov.get('icao') or '?'} "
              f"gates_nondefault={len(prov.get('gates_nondefault') or [])}"
              f"/{prov.get('gates_total')} "
              f"dem_raw={prov.get('dem_raw')}")
    else:
        print(f"  frame: provenance=None "
              f"({rep.get('provenance_reason') or 'not read'})")
    knobs = rep.get("law_true_knobs") or {}
    if knobs:
        print("  law-true knobs: " + " ".join(f"{k}={v:g}"
                                              for k, v in knobs.items()))
    # RULESET: declared / active / source.  Three verified facts; the line
    # used to add a CAUSE for a missing key ("predates the FAA/ICAO split")
    # that nothing here establishes, plus an instruction to the reader.
    if rep["ruleset_declared"]:
        print(f"  ruleset: declared={rep['ruleset_declared']!r} "
              f"active={rep['ruleset_active']!r} source=SIDECAR")
    else:
        print(f"  ruleset: declared=None "
              f"active={rep['ruleset_active']!r} source=DEFAULT")
    exempt = lt.get("steps_exempt_by_rule") or {}
    exempt_txt = (", ".join(f"{k}={v}" for k, v in sorted(exempt.items()))
                  or "none")
    print(f"  LAW-TRUE TOTAL {lt['total']}   within={lt['within']} "
          f"cross={lt['cross']} steps={lt['steps']} "
          f"(raw {lt['steps_raw']}, registered step exemptions: "
          f"{exempt_txt})")
    print(f"  sides: airside={lt['airside']} groundside={lt['groundside']} "
          f"mixed={lt['mixed']} unknown={lt['unknown']}   "
          f"airside_for_acceptance={lt['airside_for_acceptance']} "
          f"(=airside+mixed, RULINGS 'airside is king')")
    adj = rep.get("adjudication")
    if adj:
        a = adj["adjudicated_by_side"]
        print(f"\n  === ADJUDICATION (RULINGS {adj['ruling']}) ===")
        print(f"    ADJUDICATED {adj['adjudicated_total']}   "
              f"airside={a['airside']} groundside={a['groundside']} "
              f"mixed={a['mixed']}   airside_for_acceptance="
              f"{rep['adjudicated_airside_for_acceptance']}   verdict: "
              f"{'PASS' if adj['pass'] else 'FAIL'}")
        print(f"    VERSION-DEFERRED (reported, NOT adjudicated) "
              f"{adj['deferred_total']}:")
        for key, d in adj["deferred_families"].items():
            print(f"      {key:<24}{d['n']:>7}  {d['why']}")
    if "bare" in rep:
        b = rep["bare"]
        # BOTH totals and their DIFFERENCE.  The line used to assert
        # "OVERCOUNTS" while holding the two numbers that measure it; the
        # difference is now the number the reader sees.
        print(f"  BARE (context-free frame — no sidecar law context, no "
              f"registered step exemption): total={b['total']} "
              f"within={b['within']} cross={b['cross']} steps={b['steps']}")
        print(f"    bare {b['total']} − law-true {lt['total']} = "
              f"{b['total'] - lt['total']:+d} rows")
    ev = rep.get("evidence") or {}
    print(f"  sidecar evidence: seam_pins={ev.get('seam_pin_count')} "
          f"terrace_joints={ev.get('terrace_joint_count')} "
          f"terrace_certificates={ev.get('terrace_certificate_count')} "
          f"triangle_plane_unresolved="
          f"{ev.get('triangle_plane_unresolved')}")
    be = ev.get("band_excess")
    if isinstance(be, dict) and not be.get("error"):
        s = be.get("by_side") or {}
        # ZERO-OF-ZERO IS NOT A PASS (RULINGS 2026-08-06, binding point 2).
        # ``route_band_violations`` does not constrain a vertex whose band
        # reads ``None``, so a build whose band field could not be built at
        # all returns ZERO rows — and this line used to render that as a
        # clean membership report.  Measured live on HEAZ: the build logs
        # ``[reach-band] NO FIELD`` and the census printed a clean band
        # line in the same run.  The build's own report now publishes the
        # EXAMINED denominator; a census that has it must never print a
        # membership number without it.
        examined = be.get("examined")
        if examined == 0:
            print(f"  band membership: NOT MEASURED this build — ZERO of "
                  f"{be.get('candidates', 0)} candidate vertex(es) were "
                  f"examined ({be.get('off_net', 0)} off-net: band None, "
                  f"NOT constrained; {be.get('deduped', 0)} welded "
                  f"duplicate(s)).  Zero rows here is the ABSENCE of a "
                  f"measurement, not a clean surface.")
        else:
            denom = ("" if examined is None
                     else f" of {examined} EXAMINED vertex(es)")
            stale = (" [this build predates the EXAMINED denominator — the"
                     " zero-of-zero case is indistinguishable here]"
                     if examined is None else "")
            print(f"  band membership (the BUILD's own report, evidence — "
                  f"route_band lives in-memory and is not a census family): "
                  f"{be.get('material', 0)}{denom} outside their band by > "
                  f"{be.get('materiality_m', 0.01):g} m "
                  f"(ceil={s.get('ceil', 0)} floor={s.get('floor', 0)} "
                  f"pinned={s.get('pinned', 0)}, worst "
                  f"{be.get('worst_m', 0.0)} m){stale}")
        if be.get("sub_materiality_structurally_zero"):
            print(f"    sub-materiality split is STRUCTURALLY ZERO at these "
                  f"constants (noise floor "
                  f"{be.get('noise_floor_m')} m >= materiality "
                  f"{be.get('materiality_m')} m) — not evidence about the "
                  f"surface")
    elif isinstance(be, dict):
        print(f"  band membership: NOT MEASURED this build "
              f"({be.get('error')})")
    if ev.get("unknown_keys"):
        # The VERIFIED set difference, nothing more: the old line named a
        # cause (the emitter grew a field) and instructed the reader which
        # constant to edit.  What is computed is
        # ``set(sidecar) − (SIDECAR_LAW_KEYS ∪ SIDECAR_EVIDENCE_KEYS)``.
        print(f"  !! sidecar key(s) in neither SIDECAR_LAW_KEYS nor "
              f"SIDECAR_EVIDENCE_KEYS: {ev['unknown_keys']}")

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

    zs = rep.get("zone_split")
    if zs is not None:
        print("\n  === FAN-RAMP ZONE SPLIT (--zone-split) ===")
        if zs.get("reason"):
            print(f"    not available: {zs['reason']}")
        else:
            print(f"    zones {zs['zones']} declared, union "
                  f"{zs['zone_area_m2']:,.0f} m², parts sum "
                  f"{zs['zone_parts_area_m2']:,.0f} m², overlap "
                  f"{zs['zone_overlap_m2']:,.0f} m² (= parts − union), "
                  f"caps {zs['caps']}")
            print(f"    ramp PIECES {zs['ramp_ways']} "
                  f"({zs['ramp_vertices']} ring vertices) binding "
                  f"{zs['ramp_law_pairs']} law pair(s) at the zone cap")
            print(f"      [frame: {zs['ramp_law_pairs_frame']} — NOT the "
                  f"census's law-true frame above]")
            b = zs["buckets"]
            print(f"    within-shape rows {zs['within_rows']}:")
            for k, label in (
                    ("ramp_piece", "ON a declared ramp piece (judged at "
                                   "the zone cap — the LAW's population)"),
                    ("in_zone", "chord wholly inside a zone polygon"),
                    ("crosses", "chord enters and leaves a zone"),
                    ("outside", "no relation to any zone")):
                print(f"      {k:<12}{b.get(k, 0):>8}  {label}")
            bound = zs["steeper_than_zone_cap_bound"]
            if bound is None:
                print("    rows steeper than the zone cap: not measured "
                      "(this sidecar declares no cap)")
            else:
                print(f"    rows steeper than {bound * 100:g}% (the MAX "
                      f"over the {len(zs['caps'])} cap(s) this sidecar "
                      f"declares): {zs['steeper_than_zone_cap']}")
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
    ap.add_argument("--zone-split", action="store_true",
                    help="also bucket the WITHIN-SHAPE rows by FAN-RAMP "
                         "ZONE membership (on a declared ramp piece / "
                         "inside a zone / crossing one / unrelated) — the "
                         "reading that says whether the ramp law is "
                         "granting relief where the defects actually are")
    args = ap.parse_args(argv)

    cg = load_check_grade()
    reports = []
    for osm in args.patches:
        if not osm.exists():
            raise SystemExit(f"REFUSING: no such patch {osm}")
        try:
            rep = census_one(osm, cg, want_bare=args.bare, top=args.top,
                             want_zone_split=args.zone_split)
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
