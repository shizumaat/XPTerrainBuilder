"""POST-SOLVE MUTATION SEAM AUDIT — which pass moved the emitted surface.

Round 17 §R17-1(a).  ``final_grade_projection`` reports a post-solve
MUTATION SET (:func:`route_profile.solve.post_solve_mutation_set`): the
nodes whose value at the projection's entry differs from the value the
solve carried.  At VHHH that set is 8,438 moved nodes with p90 19.55 m —
a number that names the SIZE of the re-authoring but not its AUTHOR: the
window it is measured over spans every pipeline stage between the solve's
writeback and the projection.

This audit splits that window at the seams the pipeline ALREADY marks
(``pipeline._rod_ckpt``), diffing the EMITTED pavement values — the
values the shapes carry, which is what ships — across each seam and
naming the stage that moved them.  Same population as the band-membership
report (``grade_graph_validate._band_roles``), same positional node space
(rounded ``(x, y)`` in layout-local metres), so a site named here is the
same site the census and the band report name.

REPORT-ONLY and GATED (``O4_MUTATION_SEAM_AUDIT=1``).  It reads shape
altitudes and writes nothing but its own log records; with the gate off
the checkpoint is one environment read and a return.
"""

import os

#: |dz| under this is not a move (the convergence guards' elevation floor).
SEAM_MOVE_MATERIALITY_M = 0.01

#: The ROAD FAMILY, for the §1.3 ordering audit (spec
#: ``docs/specs/road-band-seal-scope-spec.md``).  With the road roles out
#: of the band seal, the question "what else can move a road node after
#: ``_grade_limit_groundside_chords``?" is answered by MEASUREMENT at the
#: seams the pipeline already marks, not by reading the source: a
#: post-limiter road author is the same defect shape the seal was.
#: Spelled as literals because this module deliberately imports nothing
#: from ``auto_patch.layout``; ``tests/test_road_band_seal_scope.py``
#: twins the two spellings.
ROAD_FAMILY_ROLES = frozenset({"service_road", "service_junction"})


def enabled() -> bool:
    """True when the audit is armed (``O4_MUTATION_SEAM_AUDIT=1``)."""
    return os.environ.get("O4_MUTATION_SEAM_AUDIT") == "1"


def dump_path() -> str:
    """The ROAD-RING DUMP path (``O4_MUTATION_SEAM_DUMP``), or ``""``.

    WHY A DUMP AND NOT ANOTHER PRINTED METRIC (spec
    ``docs/specs/road-surface-quality-spec.md`` §2, "one targeted probe
    run, not four blind fixes").  The §1.3 ordering audit answered WHICH
    seams move a road node and BY HOW MUCH; it cannot answer which of
    them authors the owner's *bumps*, because a count and a worst |dz|
    do not tell a smooth 5 m shift from a 5 m shift that also made the
    surface rough.  Deciding the metric AFTER the run — and being able
    to change it without a second 18-minute HECA build — is what the
    dump buys: every road-family ring, in RING ORDER (which is station
    order along each flank of a corridor ring), at every seam.

    Written only when the audit is armed AND the variable names a path;
    the file is the caller's (a lane scratchpad), never the shared data
    repo.
    """
    return (os.environ.get("O4_MUTATION_SEAM_DUMP", "")
            if enabled() else "")


def _road_rings(layout) -> list:
    """``[(shape_index, role, [(x, y, z), …]), …]`` over the ROAD FAMILY.

    Ring ORDER is preserved — that is the whole point.  ``_emitted_values``
    above keys by rounded coordinate because it answers "did this vertex
    move"; a roughness question needs the vertices' ADJACENCY, which only
    the ring order carries.
    """
    from .grade_graph_validate import _shape_elevs
    from .elevation_per_surface.solver_primitives import _open_ring
    out = []
    for idx, s in enumerate(getattr(layout, "shapes", ()) or ()):
        role = getattr(s, "role", "")
        if role not in ROAD_FAMILY_ROLES:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        try:
            ring = _open_ring(list(poly.exterior.coords))
        except Exception:                                  # pragma: no cover
            continue
        els = _shape_elevs(s, len(ring))
        if not els:
            continue
        pts = [(round(float(x), 3), round(float(y), 3), round(float(e), 3))
               for (x, y), e in zip(ring, els) if e is not None]
        if len(pts) >= 3:
            out.append((idx, role, pts))
    return out


def _ring_roughness(rings) -> dict:
    """The BUMP instrument: ring-edge grade statistics over the road family.

    A "bump" is a LOCAL grade excursion between adjacent emitted
    vertices — exactly what a ring edge is.  Reported as a population
    (``n_edges``, how many exceed the road's own longitudinal cap, the
    p90 and worst grade) plus the SECOND DIFFERENCE population
    (``n_kinks``): |grade(i) − grade(i−1)| over consecutive ring edges,
    which is what distinguishes a pass that TILTED a road from one that
    made it rough.  A pass that authors bumps raises these; a pass that
    shifts a road smoothly does not.
    """
    import math
    from .config import SERVICE_ROAD_MAX_GRADE
    grades = []
    kinks = []
    for _idx, _role, pts in rings:
        n = len(pts)
        gs = []
        for i in range(n):
            xa, ya, za = pts[i]
            xb, yb, zb = pts[(i + 1) % n]
            d = math.hypot(xb - xa, yb - ya)
            if d < 0.5:            # sub-metre ring edge: emit/weld noise
                gs.append(None)
                continue
            gs.append(abs(zb - za) / d)
        live = [g for g in gs if g is not None]
        grades.extend(live)
        for i in range(len(gs)):
            a, b = gs[i], gs[(i + 1) % len(gs)]
            if a is not None and b is not None:
                kinks.append(abs(b - a))
    def _p(vals, q):
        if not vals:
            return 0.0
        s = sorted(vals)
        return round(s[min(len(s) - 1, int(len(s) * q))], 5)
    return {
        "n_edges": len(grades),
        "over_cap": sum(1 for g in grades if g > SERVICE_ROAD_MAX_GRADE),
        "grade_p90": _p(grades, 0.90),
        "grade_worst": round(max(grades), 5) if grades else 0.0,
        "n_kinks": len(kinks),
        "kink_p90": _p(kinks, 0.90),
        "kink_worst": round(max(kinks), 5) if kinks else 0.0,
    }


def _emitted_values(layout) -> dict:
    """``{(x, y) rounded: (elevation, role)}`` over EVERY emitted shape.

    The population is deliberately the WHOLE patch, not the band report's
    airside roles: the VHHH runway-end canyons are ``graded_strip /
    adjacent_ground`` vertices, so an audit scoped to the band's roles
    would have watched the wrong population (the two-instruments trap in
    its usual costume).  Values are read through
    ``grade_graph_validate._shape_elevs`` — the same reader the band
    report and the census use — so "moved" here means moved in the frame
    those instruments read."""
    from .grade_graph_validate import _shape_elevs
    from .elevation_per_surface.solver_primitives import _open_ring
    out: dict = {}
    for s in getattr(layout, "shapes", ()) or ():
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        try:
            ring = _open_ring(list(poly.exterior.coords))
        except Exception:                                  # pragma: no cover
            continue
        els = _shape_elevs(s, len(ring))
        if not els:
            continue
        for (x, y), e in zip(ring, els):
            if e is None:
                continue
            out[(round(float(x), 2), round(float(y), 2))] = (
                float(e), getattr(s, "role", ""))
    return out


def checkpoint(layout, name: str) -> None:
    """Diff the emitted pavement against the previous seam; name the mover.

    Called from ``pipeline._rod_ckpt`` at every named post-solve seam.
    Gate off ⇒ one env read.
    """
    if not enabled():
        return
    try:
        cur = _emitted_values(layout)
    except Exception as exc:                               # pragma: no cover
        _vprint(f"  [mutation-seam] {name}: audit FAILED {exc!r}")
        return
    # THE ROAD-RING DUMP + THE BUMP INSTRUMENT (spec
    # ``road-surface-quality-spec.md`` §2).  Both read the SAME rings, so
    # the printed roughness and the dumped geometry can never describe
    # different populations.
    rough = None
    try:
        rings = _road_rings(layout)
        rough = _ring_roughness(rings)
        _dump = dump_path()
        if _dump:
            import json as _json
            with open(_dump, "a") as fh:
                fh.write(_json.dumps({
                    "seam": name,
                    "roughness": rough,
                    "rings": [{"shape": i, "role": r, "pts": p}
                              for (i, r, p) in rings]}) + "\n")
    except Exception as exc:                               # pragma: no cover
        _vprint(f"  [mutation-seam] {name}: road-ring dump FAILED {exc!r}")
    prev = getattr(layout, "_mutation_seam_prev", None)
    log = list(getattr(layout, "_mutation_seam_log", None) or [])
    if prev is None:
        layout._mutation_seam_prev = cur
        layout._mutation_seam_log = log
        if rough:
            layout._mutation_seam_log = log = [
                {"seam": name, "audited": len(cur), "moved": 0,
                 "road_moved": 0, "roughness": rough, "baseline": True}]
        _vprint(f"  [mutation-seam] {name}: BASELINE — "
                f"{len(cur)} audited vertex(es), "
                f"{sum(1 for (v, _r) in cur.values() if v <= 0.0)} "
                f"at or below 0 m."
                + (f"  ROAD RINGS: {rough['n_edges']} ring edge(s), "
                   f"{rough['over_cap']} over the road cap, grade p90 "
                   f"{rough['grade_p90'] * 100:.2f} % worst "
                   f"{rough['grade_worst'] * 100:.2f} %, kink p90 "
                   f"{rough['kink_p90'] * 100:.2f} %." if rough else ""))
        return
    moved = []
    for key, (val, role) in cur.items():
        old = prev.get(key)
        if old is None:
            continue
        dz = val - old[0]
        if abs(dz) > SEAM_MOVE_MATERIALITY_M:
            moved.append((abs(dz), dz, key[0], key[1], role))
    n_new = sum(1 for k in cur if k not in prev)
    n_gone = sum(1 for k in prev if k not in cur)
    # THE SUB-ZERO POPULATION (round 17 acceptance metric): how many
    # emitted vertices sit at or below 0 m after this seam, and how many
    # of them THIS seam minted.  A canyon is a population, not a worst
    # case, and the seam that grows it is the author.
    sub0 = sum(1 for (v, _r) in cur.values() if v <= 0.0)
    sub0_prev = sum(1 for (v, _r) in prev.values() if v <= 0.0)
    # THE ROAD-FAMILY SPLIT (spec §1.3 ordering audit): the same moved
    # set, restricted to the roles the seal no longer clamps.  A seam
    # with a non-zero count here is a post-limiter road author and is
    # NAMED in the report.
    road = [m for m in moved if m[4] in ROAD_FAMILY_ROLES]
    rec = {"seam": name, "audited": len(cur), "moved": len(moved),
           "new": n_new, "gone": n_gone, "worst_m": 0.0, "worst": [],
           "sub_zero": sub0, "sub_zero_delta": sub0 - sub0_prev,
           "road_moved": len(road), "road_worst_m": 0.0, "road_worst": []}
    if rough:
        rec["roughness"] = rough
        _prev_r = next((r.get("roughness") for r in reversed(log)
                        if r.get("roughness")), None)
        if _prev_r:
            rec["over_cap_delta"] = rough["over_cap"] - _prev_r["over_cap"]
            rec["kink_p90_delta"] = round(
                rough["kink_p90"] - _prev_r["kink_p90"], 5)
            _vprint(
                f"  [mutation-seam] {name}: ROAD ROUGHNESS "
                f"{rough['over_cap']} over-cap ring edge(s) "
                f"({rec['over_cap_delta']:+d}), grade p90 "
                f"{rough['grade_p90'] * 100:.2f} % worst "
                f"{rough['grade_worst'] * 100:.2f} %, kink p90 "
                f"{rough['kink_p90'] * 100:.2f} % "
                f"({rec['kink_p90_delta'] * 100:+.2f} pp).")
    if road:
        road.sort(reverse=True)
        rec["road_worst_m"] = round(road[0][0], 3)
        rec["road_worst"] = [{"dz_m": round(m[1], 3), "x": m[2], "y": m[3],
                              "role": m[4]} for m in road[:5]]
        _vprint(
            f"  [mutation-seam] {name}: ROAD FAMILY {len(road)} vertex(es) "
            f"moved (max {rec['road_worst_m']:.3f} m); worst: " + "; ".join(
                f"{w['dz_m']:+.2f} m on {w['role']} at "
                f"({w['x']:.0f},{w['y']:.0f})" for w in rec["road_worst"][:3]))
    if moved:
        moved.sort(reverse=True)
        rec["worst_m"] = round(moved[0][0], 3)
        rec["p50_m"] = round(moved[len(moved) // 2][0], 3)
        rec["p90_m"] = round(moved[int(len(moved) * 0.9)][0], 3)
        rec["worst"] = [{"dz_m": round(m[1], 3), "x": m[2], "y": m[3],
                         "role": m[4]} for m in moved[:5]]
        _vprint(
            f"  [mutation-seam] {name}: {len(moved)} vertex(es) MOVED "
            f"(p50 {rec['p50_m']:.3f} p90 {rec['p90_m']:.3f} max "
            f"{rec['worst_m']:.3f} m), {n_new} new, {n_gone} gone, of "
            f"{len(cur)} audited; sub-zero {sub0} "
            f"({rec['sub_zero_delta']:+d}); worst: " + "; ".join(
                f"{w['dz_m']:+.2f} m on {w['role']} at "
                f"({w['x']:.0f},{w['y']:.0f})" for w in rec["worst"][:3]))
    else:
        _vprint(f"  [mutation-seam] {name}: no material move "
                f"({n_new} new, {n_gone} gone, {len(cur)} audited; "
                f"sub-zero {sub0} {rec['sub_zero_delta']:+d}).")
    log.append(rec)
    layout._mutation_seam_log = log
    layout._mutation_seam_prev = cur


def report(layout, icao: str = "") -> None:
    """The seam ledger, worst seam first — the answer to "which pass"."""
    if not enabled():
        return
    log = list(getattr(layout, "_mutation_seam_log", None) or [])
    if not log:
        return
    ranked = sorted(log, key=lambda r: -float(r.get("worst_m", 0.0)))
    _vprint(f"  [mutation-seam] {icao}: SEAM LEDGER (worst move first) — "
            + " | ".join(
                f"{r['seam']} {r['moved']}@{r.get('worst_m', 0.0):.2f} m"
                for r in ranked[:8] if r.get("moved")))
    # THE ORDERING AUDIT (spec ``road-band-seal-scope-spec.md`` §1.3):
    # every seam that moved a ROAD-family vertex, in PIPELINE ORDER, so
    # the reader can see which of them run after the road chord limiter.
    road_seams = [r for r in log if int(r.get("road_moved", 0) or 0)]
    _vprint(f"  [mutation-seam] {icao}: ROAD-FAMILY LEDGER (pipeline order; "
            f"who moves a road node at each seam) — " + (" | ".join(
                f"{r['seam']} {int(r['road_moved'])}@"
                f"{float(r.get('road_worst_m', 0.0)):.2f} m"
                for r in road_seams) or "no seam moved a road vertex"))
    # THE BUMP LEDGER (spec ``road-surface-quality-spec.md`` §2.1): every
    # seam, in PIPELINE ORDER, with what it did to the road family's
    # ring-edge roughness.  This is the attribution read — a seam that
    # MOVES roads without raising these is not the bump author.
    _rough = [r for r in log if r.get("roughness")]
    if _rough:
        _vprint(f"  [mutation-seam] {icao}: ROAD ROUGHNESS LEDGER "
                f"(pipeline order; over-cap ring edges / kink p90) — "
                + " | ".join(
                    f"{r['seam']} {r['roughness']['over_cap']}"
                    + (f"({r['over_cap_delta']:+d})"
                       if "over_cap_delta" in r else "")
                    + f" k{r['roughness']['kink_p90'] * 100:.2f}%"
                    for r in _rough))
    minted = sorted(log, key=lambda r: -int(r.get("sub_zero_delta", 0) or 0))
    _vprint(f"  [mutation-seam] {icao}: SUB-ZERO LEDGER (who minted the "
            f"below-0 m population) — " + " | ".join(
                f"{r['seam']} {int(r.get('sub_zero_delta', 0)):+d} "
                f"(total {int(r.get('sub_zero', 0))})"
                for r in minted[:8]
                if int(r.get("sub_zero_delta", 0) or 0)))


def _vprint(msg: str) -> None:
    try:
        import O4_UI_Utils as _UI
        _UI.vprint(1, msg)
    except Exception:                                      # pragma: no cover
        pass
