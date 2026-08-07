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

* ``--sites`` — the law-true rows clustered into DEFECT SITES.  Row counts
  AMPLIFY: one over-cap region on one apron mints hundreds of
  edge-granularity rows (HECA's way -12407 alone carries ~800), so a
  battery total is a count of PAIRS THE LAW PRICED, not of things wrong
  with the surface, and the two differ by whatever the amplification
  factor is on that patch.  This reports the other number — how many
  DISTINCT sites, adjudicated and law-true; rows per site (the
  amplification factor itself); each site's worst |de| / step and worst
  grade excess; its families, role pairs and shape ids; its bbox and
  centroid; and a SIM-VISIBILITY flag (worst |de| >= 0.05 m of relief is
  a silhouette-visible candidate, ``--site-visibility`` to move it).  The
  clustering rule is printed with the numbers: same family AND (shared
  way id OR shared canonical node at the census's own weld tolerance).
  ``--sites-json`` dumps every site with its membership.

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
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

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


def _axis_frame_override(osm: Path, cg, frame: str) -> tuple[dict, dict]:
    """``(overrides, stamp)`` for the census's AXIS FRAME.

    ``own`` — the patch's own sidecar, unaltered.  THE default and the only
    frame whose numbers are defect counts.

    ``base`` — the same patch bytes read with the SERVICE axes removed from
    its sidecar: the axis frame a pre-road-feed sidecar carried.  It exists
    because a class can move between two builds either because the SURFACE
    moved or because the axis population the reader judges it against did,
    and those are different findings (cycle 9/10: HECA 10 000 m arm B read
    airside 4,610 in its own frame and 4,474 in this one — the whole gap
    was one instrument defect, since fixed).  Quoting it is a FRAME claim,
    never a defect count, which is why the frame is stamped in the report
    and printed rather than left to the reader's memory.

    Route ordinals are untouched: the ``routes`` list keeps its indices, so
    the surviving axes still point at the same routes.
    """
    if frame == "own":
        return {}, {"frame": "own", "axes_total": None, "axes_kept": None}
    ctx = cg.law_context_from_sidecar(osm, announce=False)
    axes = ctx.get("taxi_axes_ll") or []
    kept = [e for e in axes if not (len(e) > 4 and bool(e[4]))]
    return ({"taxi_axes_ll": kept},
            {"frame": "base", "axes_total": len(axes), "axes_kept": len(kept)})


def row_points(r):
    """The row's two ENDPOINTS in layout-local metres, as ``(a, b)``.

    ``pt_a``/``pt_b`` for a grade violation, ``vert_pt``/``proj_pt`` for an
    edge step — the two row shapes ``run_checks`` emits.  ONE spelling,
    because both the ``--rows-json`` itemisation and the ``--sites``
    clustering key on these points: a second copy that forgot the step
    shape would silently cluster every step row as pointless.
    """
    a, b = getattr(r, "pt_a", None), getattr(r, "pt_b", None)
    if a is None:
        a, b = getattr(r, "vert_pt", None), getattr(r, "proj_pt", None)
    return a, b


def row_ways(r):
    """The row's two WAYS, as ``(way_a, way_b)`` — ``way_v``/``way_e`` for a
    step row.  Same two shapes, same single spelling; ``cg.row_side`` and
    ``cg.row_roles`` resolve the pair exactly this way."""
    a = getattr(r, "way_a", None) or getattr(r, "way_v", None)
    b = getattr(r, "way_b", None) or getattr(r, "way_e", None)
    return a, b


def row_record(cg, family: str, r) -> dict:
    """ONE law-true row, itemised for the ``--rows-json`` dump.

    Every field comes from the law's own accessors (``row_roles`` /
    ``row_side`` / ``row_magnitude``) — the same ones the class table, the
    side split and the worst-N table use, so a row dump and the counts in
    the same report can never disagree.

    ``site_m`` is the row's endpoints in LAYOUT-LOCAL METRES (the emitter's
    own frame: ``pt_a``/``pt_b`` for a grade violation, the vertex and its
    projection for an edge step).  That is the join key for an A/B row
    diff: it is arm-independent wherever the arms share geometry, which
    lat/lon also is — but metres round without a projection choice, and a
    diff keyed on a rounded degree is keyed on ~1 cm at one latitude and
    ~2 cm at another.  ``lat``/``lon`` ride along for pointing a human (or
    a KML) at the spot.
    """
    a, b = row_points(r)
    wa, wb = row_ways(r)
    grade = getattr(r, "grade_pct", None)
    cap = getattr(r, "cap_pct", None)
    return {
        "family": family,
        "roles": "|".join(sorted(cg.row_roles(r))),
        "side": cg.row_side(r),
        "magnitude_m": round(cg.row_magnitude(r), 4),
        "grade_pct": round(float(grade), 4) if grade is not None else None,
        "cap_pct": round(float(cap), 4) if cap is not None else None,
        "distance_m": (round(float(getattr(r, "distance_m", 0.0)), 3)
                       if getattr(r, "distance_m", None) is not None
                       else None),
        "site_m": [[round(float(a[0]), 2), round(float(a[1]), 2)],
                   [round(float(b[0]), 2), round(float(b[1]), 2)]]
                  if a is not None and b is not None else None,
        "lat": getattr(r, "lat", None),
        "lon": getattr(r, "lon", None),
        "way_a": getattr(wa, "wid", None),
        "way_b": getattr(wb, "wid", None),
        "out_of_scope": getattr(r, "out_of_scope", None),
    }


# ══════════════════════════════════════════════════════════════════════
# THE SITE CENSUS (--sites) — how many DISTINCT DEFECTS, not how many rows
# ══════════════════════════════════════════════════════════════════════
#
# WHY IT LIVES HERE.  Row counts AMPLIFY.  One over-cap region on one
# apron mints hundreds of edge-granularity rows: at HECA way -12407 alone
# carries ~800 of them, and the 180 threshold-flip sites of the road-feed
# round live on 19 shapes with 72 % of them on four aprons.  A battery
# that reads "thousands of defects" is therefore not, by itself, a count
# of things wrong with the surface — it is a count of PAIRS the law
# priced, and the two differ by whatever the amplification factor happens
# to be on that patch.  This section reports the other number: how many
# DISTINCT sites exist, how many rows each mints, and whether each one is
# big enough to see.
#
# It is a FLAG on the census and not a tool of its own for the reason the
# census exists at all (owner ruling 7e90032, and the census-wrapper
# precedent in this file's header): the population it clusters must be the
# law-true one, and a private copy of that frame is the defect.  Nothing
# here re-runs a check — it reads the rows ``census_one`` already has, and
# the site rows' union IS ``all_rows``, twin-asserted.

#: SIM VISIBILITY, metres of relief.  A site whose worst |de| / step
#: reaches this is a SILHOUETTE-VISIBLE CANDIDATE: 5 cm is roughly where a
#: surface discontinuity stops being lost in the mesh's own noise and
#: starts casting an edge a pilot's eye can catch on the ground.  It is a
#: REPORTING threshold, never a law: the law adjudicates every row
#: regardless (RULINGS 2026-08-02, "compliance with grade law, not
#: instrument-zero"), and this only ranks which sites would be SEEN.  It
#: is deliberately ABOVE the campaign's 0.01 m materiality floor and
#: deliberately a knob (``--site-visibility``), because nothing has
#: measured the real threshold in the sim — quote it as an assumption.
DEFAULT_SITE_VISIBILITY_M = 0.05


def canonical_nodes(points, tol_m: float):
    """Assign each ``(x, y)`` in ``points`` to a CANONICAL NODE id.

    ``points`` is a sequence of layout-local metre coordinates (possibly
    with ``None`` holes, which come back as ``None``); the return is
    ``(ids, centres)`` — one id per input point, and the coordinate of
    each canonical node.

    THE SEMANTIC IS NOT NEW.  ``tol_m`` is the census's own
    ``LAW_TRUE_KNOBS["proximity_m"]`` — ``check_grade.SHARED_VERTEX_TOL_M``,
    the SOLVER'S WELD TOLERANCE, which is the tolerance the law itself
    already treats as "these two vertices are one node" (it is what the
    cross-shape proximity check is run at, and what the emitter's
    canonical-point registry spaces distinct points by).  Two rows that
    meet at a welded corner are two readings of one physical place, and
    this is the law's own predicate for that, not a proximity rule
    invented for a report.

    DETERMINISM.  Points are registered in sorted coordinate order, not in
    row order, so the partition does not depend on how the rows happened
    to be sorted; ties attach to the lowest-numbered canonical node.
    """
    cell = tol_m if tol_m > 0 else 1.0
    grid: dict = {}
    centres: list = []
    ids: list = [None] * len(points)
    order = sorted((i for i, p in enumerate(points) if p is not None),
                   key=lambda i: (float(points[i][0]), float(points[i][1]), i))
    for i in order:
        x, y = float(points[i][0]), float(points[i][1])
        cx, cy = int(math.floor(x / cell)), int(math.floor(y / cell))
        best = None
        best_d = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((cx + dx, cy + dy), ()):
                    px, py = centres[j]
                    d = math.hypot(x - px, y - py)
                    if d > tol_m:
                        continue
                    if best_d is None or d < best_d or (d == best_d
                                                        and j < best):
                        best, best_d = j, d
        if best is None:
            best = len(centres)
            centres.append((x, y))
            grid.setdefault((cx, cy), []).append(best)
        ids[i] = best
    return ids, centres


class _DisjointSet:
    """Union-find over row indices.  Boring on purpose: the clustering
    rule has to be auditable line by line, because a site count is about
    to become a headline number."""

    def __init__(self, n: int):
        self._p = list(range(n))

    def find(self, i: int) -> int:
        p = self._p
        while p[i] != i:
            p[i] = p[p[i]]
            i = p[i]
        return i

    def union(self, i: int, j: int) -> None:
        a, b = self.find(i), self.find(j)
        if a != b:
            # Lower index wins, so the representative of a site is its
            # earliest row and the grouping is order-stable.
            if b < a:
                a, b = b, a
            self._p[b] = a


#: THE CLUSTERING RULE, in one sentence, quoted verbatim into every
#: report header so a site count is never read without the rule that
#: produced it.
SITE_RULE = (
    "two law-true rows belong to ONE defect site iff they are in the SAME "
    "LAW FAMILY and they share a way id, or share a canonical node — where "
    "a canonical node is the census's own weld tolerance "
    "(LAW_TRUE_KNOBS['proximity_m'] = check_grade.SHARED_VERTEX_TOL_M) "
    "applied to the rows' endpoints in layout-local metres.  Sites are the "
    "connected components of that relation (union-find); no new proximity "
    "semantic and no magnitude, role or geometry test takes part in the "
    "clustering")


def cluster_sites(all_rows, cg, *, visibility_m: float = None,
                  tol_m: float = None, top: int = 10) -> dict:
    """``--sites``: cluster the census's own law-true rows into DEFECT SITES.

    ``all_rows`` is the ``(family_key, row)`` sequence ``census_one``
    builds — the same population every count in the report is taken from.
    Returns the section dict; the sites PARTITION ``all_rows``
    (``sum(site["rows"]) == len(all_rows)`` and the member index sets are
    disjoint and complete), twin-asserted in ``tests/test_harness.py``.

    THE QUESTION IT ANSWERS.  "15,530 adjudicated rows" and "N distinct
    sites, median M rows each, K of them big enough to see" send work to
    different places and rank it differently.  A row total is dominated by
    whichever defect happens to sit on the most-tessellated shape; a site
    total is not.

    WHAT EACH SITE CARRIES: its family, the ways (shape ids) and role
    pairs it spans, its row count (the AMPLIFICATION FACTOR), its worst
    |de| / step and worst grade excess, its bounding box and centroid, the
    law's own adjudication split (``check_grade.adjudication`` on the
    site's own rows — one implementation, never a second copy), and the
    SIM-VISIBILITY flag (``worst_m >= visibility_m``).

    THE RULE IS TRANSITIVE, AND THAT IS VISIBLE IN THE OUTPUT.  Sites are
    connected COMPONENTS, so a welded apron complex whose shapes all share
    corners reads as ONE site spanning many shapes rather than one site
    per ring (measured at HECA: 2,802 adjudicated rows over 81 ways and
    2.4 km of extent, in one component).  That is the intended reading —
    it IS one over-cap region — but it is also the reading a caller is
    most likely to want to check, so ``n_ways`` and ``extent_m`` ride on
    every site: a "site" 2.4 km across says so in its own row.
    """
    vis = (DEFAULT_SITE_VISIBILITY_M if visibility_m is None
           else float(visibility_m))
    tol = (float(cg.LAW_TRUE_KNOBS["proximity_m"]) if tol_m is None
           else float(tol_m))

    rows = list(all_rows)
    n = len(rows)
    # Endpoints, flattened: row i owns points 2i and 2i+1.
    pts: list = []
    for _key, r in rows:
        a, b = row_points(r)
        pts.append(a)
        pts.append(b)
    node_ids, _centres = canonical_nodes(pts, tol)

    ds = _DisjointSet(n)
    first_way: dict = {}
    first_node: dict = {}
    for i, (key, r) in enumerate(rows):
        for w in row_ways(r):
            wid = getattr(w, "wid", None)
            if wid is None:
                continue
            k = (key, "w", wid)
            j = first_way.setdefault(k, i)
            if j != i:
                ds.union(i, j)
        for slot in (2 * i, 2 * i + 1):
            nid = node_ids[slot]
            if nid is None:
                continue
            k = (key, "n", nid)
            j = first_node.setdefault(k, i)
            if j != i:
                ds.union(i, j)

    members: dict = {}
    for i in range(n):
        members.setdefault(ds.find(i), []).append(i)

    sites = []
    for _root, idxs in members.items():
        site_rows = [rows[i] for i in idxs]
        key = site_rows[0][0]
        worst_m = 0.0
        worst_excess = None
        ways = set()
        roles = Counter()
        xs: list = []
        ys: list = []
        lats: list = []
        lons: list = []
        for _k, r in site_rows:
            worst_m = max(worst_m, cg.row_magnitude(r))
            exc = getattr(r, "excess_pct", None)
            if exc is not None:
                exc = abs(float(exc))
                worst_excess = exc if worst_excess is None else max(
                    worst_excess, exc)
            for w in row_ways(r):
                wid = getattr(w, "wid", None)
                if wid is not None:
                    ways.add(str(wid))
            roles["|".join(sorted(cg.row_roles(r)))] += 1
            for p in row_points(r):
                if p is not None:
                    xs.append(float(p[0]))
                    ys.append(float(p[1]))
            lat, lon = getattr(r, "lat", None), getattr(r, "lon", None)
            if lat is not None and lon is not None:
                lats.append(float(lat))
                lons.append(float(lon))
        # THE ADJUDICATION SPLIT comes from the law's own implementation
        # applied to this site's own rows — never a second copy of the
        # deferred / out-of-scope registers (RULINGS d48bc0a + the
        # 2026-08-06 ONE-graph classes).
        adj = cg.adjudication(site_rows)
        sides = Counter(cg.row_side(r) for _k, r in site_rows)
        sites.append({
            "family": key,
            "rows": len(idxs),
            "row_indices": sorted(idxs),
            "worst_m": round(worst_m, 4),
            "worst_grade_excess_pct": (round(worst_excess, 4)
                                       if worst_excess is not None else None),
            "sim_visible": worst_m >= vis,
            "ways": sorted(ways),
            "n_ways": len(ways),
            "role_pairs": dict(roles.most_common()),
            "airside": sides.get("airside", 0),
            "groundside": sides.get("groundside", 0),
            "mixed": sides.get("mixed", 0),
            "unknown": sides.get("unknown", 0),
            "adjudicated": adj["adjudicated_total"],
            "deferred": adj["deferred_total"],
            "out_of_scope": adj["out_of_scope_total"],
            "bbox_m": ([round(min(xs), 2), round(min(ys), 2),
                        round(max(xs), 2), round(max(ys), 2)]
                       if xs else None),
            "extent_m": (round(max(max(xs) - min(xs), max(ys) - min(ys)), 2)
                         if xs else None),
            "centroid_lat": (round(sum(lats) / len(lats), 7) if lats
                             else None),
            "centroid_lon": (round(sum(lons) / len(lons), 7) if lons
                             else None),
            "bbox_ll": ([round(min(lats), 7), round(min(lons), 7),
                         round(max(lats), 7), round(max(lons), 7)]
                        if lats else None),
        })
    # Deterministic order: worst first, then the biggest amplifier, then
    # the family name and the site's earliest row.
    sites.sort(key=lambda s: (-s["worst_m"], -s["rows"], s["family"],
                              s["row_indices"][0]))

    def _quantiles(vals):
        if not vals:
            return {"median": 0.0, "mean": 0.0, "p90": 0.0, "max": 0}
        v = sorted(vals)
        m = len(v)
        med = (v[m // 2] if m % 2 else (v[m // 2 - 1] + v[m // 2]) / 2.0)
        return {"median": round(float(med), 2),
                "mean": round(sum(v) / m, 2),
                "p90": v[min(m - 1, int(math.ceil(0.9 * m)) - 1)],
                "max": v[-1]}

    adjudicated_sites = [s for s in sites if s["adjudicated"]]
    by_family: dict = {}
    for s in sites:
        d = by_family.setdefault(s["family"], {
            "sites": 0, "rows": 0, "visible_sites": 0,
            "adjudicated_sites": 0, "worst_m": 0.0, "rows_per_site": []})
        d["sites"] += 1
        d["rows"] += s["rows"]
        d["visible_sites"] += 1 if s["sim_visible"] else 0
        d["adjudicated_sites"] += 1 if s["adjudicated"] else 0
        d["worst_m"] = max(d["worst_m"], s["worst_m"])
        d["rows_per_site"].append(s["rows"])
    for d in by_family.values():
        d["median_rows_per_site"] = _quantiles(
            d.pop("rows_per_site"))["median"]
        d["worst_m"] = round(d["worst_m"], 4)

    return {
        "rule": SITE_RULE,
        "adjacency_tol_m": tol,
        "adjacency_tol_source": "LAW_TRUE_KNOBS['proximity_m'] "
                                "(check_grade.SHARED_VERTEX_TOL_M, the "
                                "solver's weld tolerance)",
        "visibility_m": vis,
        "visibility_note": (
            f"a site is a SILHOUETTE-VISIBLE CANDIDATE when its worst "
            f"|de| / step reaches {vis:g} m of relief; below that it is "
            f"reported as invisible.  A REPORTING threshold and an "
            f"ASSUMPTION — nothing has measured it in the sim — never a "
            f"law: the law adjudicates every row regardless"),
        "total_rows": n,
        "sites": len(sites),
        "sites_adjudicated": len(adjudicated_sites),
        "sites_visible": sum(1 for s in sites if s["sim_visible"]),
        "sites_visible_adjudicated": sum(
            1 for s in adjudicated_sites if s["sim_visible"]),
        "rows_per_site": _quantiles([s["rows"] for s in sites]),
        "rows_per_site_adjudicated": _quantiles(
            [s["adjudicated"] for s in adjudicated_sites]),
        "amplification": (round(n / len(sites), 2) if sites else 0.0),
        "by_family": {k: by_family[k] for k in sorted(by_family)},
        "top": [{k: v for k, v in s.items() if k != "row_indices"}
                for s in sites[:top]],
        "all_sites": sites,
    }


def census_one(osm: Path, cg, *, want_bare: bool = False,
               top: int = 10, want_zone_split: bool = False,
               band_edges=None, frame: str = "own",
               rows_out: Optional[Path] = None,
               want_sites: bool = False,
               site_visibility_m: Optional[float] = None,
               sites_out: Optional[Path] = None) -> dict:
    """The census of ONE patch.  Returns the report dict; prints nothing.

    ``frame`` selects the AXIS FRAME — see :func:`_axis_frame_override`.
    ``rows_out`` additionally itemises every law-true row to that path
    (``--rows-json``); ``want_sites`` adds the DEFECT-SITE section
    (``--sites``) and ``sites_out`` dumps every site with its membership
    (``--sites-json``)."""
    families: dict = {}
    axis_overrides, frame_stamp = _axis_frame_override(osm, cg, frame)
    within, cross, steps = cg.run_checks_law_true(
        osm, family_out=families, quiet=True, top_n=0, **axis_overrides)

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

    # EVERY law-true row, on request (``--rows-json``).  The class table
    # says a class moved by N; only the rows say WHICH N and WHERE — and a
    # net class delta hides equal churn by construction (a class that gains
    # 200 rows at one site and loses 18 at another reads as "+182").  This
    # is the same ``all_rows`` every count above is taken from: no second
    # frame, no re-derivation, the census's own population itemised.  The
    # frame stamps ride along so two dumps cannot be joined across frames
    # without it showing.
    if rows_out is not None:
        rows_out.parent.mkdir(parents=True, exist_ok=True)
        rows_out.write_text(json.dumps({
            "patch": str(osm),
            "provenance": prov["provenance"],
            "axis_frame": frame_stamp,
            "law_true_knobs": dict(cg.LAW_TRUE_KNOBS),
            "n_rows": len(all_rows),
            "rows": [row_record(cg, key, r) for key, r in all_rows],
        }, indent=1))

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
        # THE AXIS FRAME, always stamped — "own" for every default run, so
        # a report without the key is simply an older one and a report WITH
        # it can never be mistaken for the other frame.
        "axis_frame": frame_stamp,
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
    if band_edges is not None:
        report["magnitude_bands"] = magnitude_bands(all_rows, cg, band_edges)
    if want_sites or sites_out is not None:
        sec = cluster_sites(all_rows, cg, visibility_m=site_visibility_m,
                            top=top)
        # THE SITES PARTITION THE CENSUS'S OWN POPULATION — asserted here,
        # in production, not only in the twin.  A site table whose rows do
        # not add up to the total printed above it is the two-instruments
        # trap inside one report, and the whole claim of this section is
        # that it re-reads the census's rows rather than measuring again.
        seen = set()
        for s in sec["all_sites"]:
            seen.update(s["row_indices"])
        if len(seen) != len(all_rows) or sum(
                s["rows"] for s in sec["all_sites"]) != len(all_rows):
            raise SystemExit(
                f"REFUSING: the site clustering does not partition the "
                f"census's own rows ({len(seen)} distinct member indices, "
                f"{sum(s['rows'] for s in sec['all_sites'])} member slots, "
                f"{len(all_rows)} law-true rows) — the site counts and the "
                f"row counts in this report would describe two populations")
        all_sites = sec.pop("all_sites")
        if sites_out is not None:
            sites_out.parent.mkdir(parents=True, exist_ok=True)
            sites_out.write_text(json.dumps({
                "patch": str(osm),
                "provenance": prov["provenance"],
                "axis_frame": frame_stamp,
                "law_true_knobs": dict(cg.LAW_TRUE_KNOBS),
                "rule": sec["rule"],
                "adjacency_tol_m": sec["adjacency_tol_m"],
                "visibility_m": sec["visibility_m"],
                "n_rows": len(all_rows),
                "n_sites": len(all_sites),
                # ``row_indices`` index the census's OWN magnitude-sorted
                # ``all_rows`` — the same order ``--rows-json`` dumps, so
                # the two files join by position with no second key.
                "sites": all_sites,
            }, indent=1))
        report["sites"] = sec
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
        # OUT OF SCOPE — rows on geometry no law governs (the ONE-graph
        # ruling's unsolved rings).  Printed even at zero, so an absent
        # heading means the census predates the class and never a
        # silently dropped population.
        oos = adj.get("out_of_scope_classes") or {}
        print(f"    OUT OF SCOPE (reported, NOT adjudicated) "
              f"{adj.get('out_of_scope_total', 0)}"
              + (":" if oos else "  [no class fired]"))
        for key, d in oos.items():
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

    st = rep.get("sites")
    if st is not None:
        print("\n  === DEFECT SITES (--sites) ===")
        # THE RULE, printed with the numbers it produced.  A site count is
        # meaningless without it, and a reader who has to go and find the
        # clustering rule will assume one instead.
        print(f"    rule: {st['rule']}")
        print(f"    adjacency tolerance {st['adjacency_tol_m']:g} m "
              f"[{st['adjacency_tol_source']}]")
        rps = st["rows_per_site"]
        print(f"    SITES {st['sites']} (law-true) / "
              f"{st['sites_adjudicated']} carrying >=1 ADJUDICATED row, "
              f"over {st['total_rows']} row(s)")
        print(f"    AMPLIFICATION {st['amplification']} rows/site mean; "
              f"median {rps['median']:g}, p90 {rps['p90']}, "
              f"max {rps['max']}")
        print(f"    SIM-VISIBLE {st['sites_visible']} site(s) "
              f"({st['sites_visible_adjudicated']} of them adjudicated) at "
              f">= {st['visibility_m']:g} m relief; "
              f"{st['sites'] - st['sites_visible']} below it")
        print(f"      [{st['visibility_note']}]")
        if st["by_family"]:
            print(f"    {'FAMILY':<24}{'sites':>7}{'adj':>6}{'vis':>6}"
                  f"{'rows':>8}{'med/site':>10}{'worst m':>10}")
            print("    " + "-" * 71)
            for key, d in st["by_family"].items():
                print(f"    {key:<24}{d['sites']:>7}"
                      f"{d['adjudicated_sites']:>6}{d['visible_sites']:>6}"
                      f"{d['rows']:>8}{d['median_rows_per_site']:>10g}"
                      f"{d['worst_m']:>10.3f}")
        if st["top"]:
            print(f"    worst {len(st['top'])} site(s) "
                  f"(by |de| / step, then rows):")
            for s in st["top"]:
                where = ""
                if s["centroid_lat"] is not None:
                    where = (f" @({s['centroid_lat']:.5f},"
                             f"{s['centroid_lon']:.5f})")
                exc = ("" if s["worst_grade_excess_pct"] is None
                       else f" excess={s['worst_grade_excess_pct']:.2f}pp")
                print(f"      {s['family']:<22}rows={s['rows']:<6}"
                      f"|de|={s['worst_m']:7.3f} m{exc}"
                      f"  ways={s['n_ways']} extent={s['extent_m']} m"
                      f"  {'VISIBLE' if s['sim_visible'] else 'invisible'}"
                      f"{where}")
                print(f"        shapes {','.join(s['ways'][:6])}"
                      + (" …" if len(s["ways"]) > 6 else "")
                      + f"   roles {list(s['role_pairs'])[:3]}"
                      + f"   adj={s['adjudicated']} defer={s['deferred']} "
                        f"oos={s['out_of_scope']}")

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
        oost = [r["adjudication"].get("out_of_scope_total", 0)
                for r in reports]
        print(f"  {'(out of scope)':<24}"
              + "".join(f"{c:>18}" for c in oost)
              + f"{oost[-1] - oost[0]:>+15d}")
    if all(r.get("sites") for r in reports):
        # SITES beside ROWS in the A/B — the two move independently, and
        # which one moved is the finding (a fix that clears one site can
        # take a thousand rows with it; a fix that shaves every row by a
        # millimetre moves neither).
        for label, get in (("SITES", lambda r: r["sites"]["sites"]),
                           ("(sim-visible sites)",
                            lambda r: r["sites"]["sites_visible"]),
                           ("(adjudicated sites)",
                            lambda r: r["sites"]["sites_adjudicated"])):
            cells = [get(r) for r in reports]
            print(f"  {label:<24}" + "".join(f"{c:>18}" for c in cells)
                  + f"{cells[-1] - cells[0]:>+15d}")


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
    ap.add_argument("--frame", choices=("own", "base"), default="own",
                    help="the AXIS FRAME the census reads the patch in.  "
                         "'own' (default) is the patch's own sidecar and "
                         "the only frame whose numbers are defect counts.  "
                         "'base' re-reads the SAME patch bytes with the "
                         "SERVICE axes removed from its sidecar — the axis "
                         "population a pre-road-feed sidecar carried — so a "
                         "class that moved between two builds can be split "
                         "into 'the surface moved' and 'the axis frame "
                         "moved'.  A base-frame number is a FRAME claim, "
                         "never a defect count; the frame is stamped into "
                         "the report either way")
    ap.add_argument("--rows-json", type=Path, default=None,
                    metavar="OUT.json",
                    help="also itemise EVERY law-true row to this file "
                         "(family, role pair, side, magnitude, grade/cap, "
                         "site in layout-local metres, lat/lon, way ids).  "
                         "The class table says a class moved by N; only the "
                         "rows say which N and where, and a net class delta "
                         "hides equal churn by construction.  Same "
                         "population as every count in the report — an "
                         "itemisation, never a second measurement.  With "
                         "several patches the dumps are suffixed per patch")
    ap.add_argument("--sites", action="store_true",
                    help="also cluster the law-true rows into DEFECT SITES "
                         "and report how many DISTINCT defects there are, "
                         "how many rows each mints (the AMPLIFICATION "
                         "factor), each site's worst |de| / grade excess, "
                         "its shapes / families / role pairs, its bbox and "
                         "centroid, and whether it is big enough to see in "
                         "the sim.  Row counts amplify — one over-cap "
                         "region on one apron mints hundreds of "
                         "edge-granularity rows — so a row total ranks "
                         "nothing.  The sites PARTITION the census's own "
                         "population (refused if they do not)")
    ap.add_argument("--site-visibility", type=float, default=None,
                    metavar="M",
                    help=f"the SIM-VISIBILITY threshold for --sites, metres "
                         f"of relief (default {DEFAULT_SITE_VISIBILITY_M:g}). "
                         f"A site whose worst |de| / step reaches it is a "
                         f"silhouette-visible candidate.  A REPORTING "
                         f"threshold and an assumption — nothing has "
                         f"measured it in the sim — never a law")
    ap.add_argument("--sites-json", type=Path, default=None,
                    metavar="OUT.json",
                    help="also dump EVERY site with its full membership "
                         "(row indices into the census's own "
                         "magnitude-sorted row order, so this file joins "
                         "--rows-json by position).  With several patches "
                         "the dumps are suffixed per patch")
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
    multi = len(args.patches) > 1
    for osm in args.patches:
        if not osm.exists():
            raise SystemExit(f"REFUSING: no such patch {osm}")
        # One dump per patch, named after it — a single --rows-json /
        # --sites-json over several patches would otherwise silently keep
        # the last.
        def _per_patch(p, _osm=osm):
            if p is None or not multi:
                return p
            return p.with_name(f"{p.stem}.{_osm.stem}{p.suffix}")
        rows_out = _per_patch(args.rows_json)
        sites_out = _per_patch(args.sites_json)
        try:
            rep = census_one(osm, cg, want_bare=args.bare, top=args.top,
                             want_zone_split=args.zone_split,
                             band_edges=band_edges, frame=args.frame,
                             rows_out=rows_out, want_sites=args.sites,
                             site_visibility_m=args.site_visibility,
                             sites_out=sites_out)
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
