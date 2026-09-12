"""§17 THE COCKPIT FRAME, OBJECT STAGE (owner RULINGS 2026-09-12x/12y;
``object-placement-spec.md`` §17; ``design-surface-spec.md`` §31 (6)).

A CLASSIFICATION of the bars ``placement_census`` produces, never a new
reading: every number here comes out of a census dict that module already
returned, and the block says which of them the pilot SEES and which are
REPORT.  The two thresholds and the approach range are the SAME law keys
the terrain census reads (``emit.toml [cockpit]`` through
``auto_patch_v2.law.tables.cockpit``) — one frame for both stages, because
a second copy of a reading rule is the census-wrapper defect.

It lives beside ``placement_census`` rather than in it for the 1,000-line
file law (``tests/auto_patch_v2/test_model.py``), the same reason §16c
(5)'s torn-seam census lives in ``placement_seams``; both are re-exported
through ``placement_census``, which is the census front door.
"""
from __future__ import annotations

import typing as _t

from .placement_census import CARRIED_OWN_GROUND_TOL_M, STANDS_OVER_TOL_M

__all__ = ["cockpit_block", "cockpit_block_lines", "COCKPIT_RULING"]

#: The owner rulings this block reads under, quoted in its heading.
#: 12ad is round 2's span rule — it changes nothing at this stage (see
#: :func:`cockpit_block_lines`) and is cited so the two stages' headings
#: name the same law.
COCKPIT_RULING = "2026-09-12x/12y/12ad"


def _cockpit_law() -> dict:
    from ..law import tables as _T
    ck = _T.cockpit(_T.load_default())
    return {"motion_step_m": float(ck.motion_step_m),
            "visual_m": float(ck.visual_m),
            "approach_km": float(ck.approach_km)}


def _cockpit_coords(splits: _t.Sequence[_t.Mapping[str, _t.Any]]) -> dict:
    """resource name -> (lat, lon), off the plan's own placement rows.

    Both spellings a census names a body by: the placement's own resource
    and each body's ``new_resource``.  §31 (6) wants the worst of each
    bucket NAMED BY COORDINATE, and the plan already carries one per
    placement — nothing is measured here."""
    out: dict[str, tuple] = {}
    for s in splits:
        p = s.get("placement", {}) or {}
        ll = (p.get("lat"), p.get("lon"))
        if ll[0] is None:
            continue
        if p.get("resource"):
            out.setdefault(str(p["resource"]), ll)
        for b in s.get("bodies", ()) or ():
            if b.get("new_resource"):
                out[str(b["new_resource"])] = ll
    return out


def cockpit_block(*, splits: _t.Sequence[_t.Mapping[str, _t.Any]] = (),
                  v15: _t.Mapping[str, _t.Any] | None = None,
                  v16b: _t.Mapping[str, _t.Any] | None = None,
                  torn: _t.Mapping[str, _t.Any] | None = None,
                  law: _t.Mapping[str, float] | None = None) -> dict:
    """§17: the placement stage's rows in the COCKPIT frame.

    ``v15`` / ``v16b`` / ``torn`` are the dicts :func:`census_v15`,
    :func:`census_v16b` and :func:`census_torn_seams` returned — handed in,
    never recomputed.  Returns the CRITICAL VISUAL items (each with its
    count, worst value and worst coordinate), the CRITICAL MOTION reading,
    and the REPORT items.

    CRITICAL MOTION is not readable at this stage and says so: §17 prices
    an object that STANDS ON the pavement (a sign, a light, a marker) at
    ``motion_step_m``, and the placement plan carries no pavement role per
    body — the roles live in the terrain patch, which the plan does not
    join to.  An instrument limit, named rather than printed as a zero.
    """
    law = dict(law or _cockpit_law())
    vis = float(law["visual_m"])
    at = _cockpit_coords(splits)

    def _where(res: str) -> str:
        ll = at.get(str(res))
        return (f"{float(ll[0]):.7f},{float(ll[1]):.7f}"
                if ll and ll[0] is not None else "no coordinate")

    critical: list[dict] = []
    report: list[dict] = []

    def _item(kind: str, n: int, pairs, note: str, *, threshold: float,
              exact: bool = True) -> None:
        """One classified item.  ``pairs`` is [(value, name), ...] worst
        first; ``exact`` is False where the count was taken at a tolerance
        other than the cockpit threshold, which the line then states."""
        w = pairs[0] if pairs else None
        rec = {"kind": kind, "n": int(n), "note": note,
               "threshold_m": threshold, "exact": exact,
               "worst_m": (round(float(w[0]), 3) if w else None),
               "worst_name": (str(w[1]) if w else None),
               "worst_at": (_where(w[1]) if w else None)}
        (critical if n else report).append(rec)

    if v15 is not None:
        tol = float(v15.get("float_tol_m", STANDS_OVER_TOL_M))
        same = abs(tol - vis) < 1e-9
        _item("§15 carried body floating over its carrier",
              v15.get("carried_float_gt", 0),
              [(f, r) for f, r, _u in v15.get("carried_worst", ())],
              "a carried body takes its carrier's zero: any residual is a "
              "carrier the law chose wrongly (§15 (6), bar 0)",
              threshold=tol, exact=same)
        _item("§15 footed body floating over what it stands on",
              v15.get("footed_float_gt", 0),
              [(f, r) for f, r, _u in v15.get("footed_worst", ())],
              "reported by name: two footed bodies over genuinely "
              "different terrain lawfully differ",
              threshold=tol, exact=same)
        _item("§15 carried over a body the law REFUSES as a carrier",
              v15.get("carried_over_refused", 0),
              [(f, r) for f, r, _u in v15.get("carried_over_refused_worst", ())],
              "what this measures is the REFUSAL, not the placement",
              threshold=tol, exact=same)
        ro = list(v15.get("refused_ground_off", ()))
        _item("§16a (2) refused carrier: its own feet off its zero",
              sum(1 for off, _r in ro if float(off) > vis), ro,
              "a body whose zero stands off the ground under its own feet "
              "— the eye reads it wherever it stands",
              threshold=vis)
    if v16b is not None:
        tol = float(v16b.get("float_tol_m", CARRIED_OWN_GROUND_TOL_M))
        _item("§16b carried piece floating over its OWN ground",
              v16b.get("carried_own_ground_gt", 0),
              [(abs(d), r) for d, r in v16b.get("carried_own_ground_worst", ())],
              "read on the body's own written triangles (bar 0)",
              threshold=tol, exact=abs(tol - vis) < 1e-9)
        _item("§16b body wider than its terrain group",
              v16b.get("geom_span_gt", 0),
              [(d, r) for d, r in v16b.get("geom_span_worst", ())],
              "a rigid body wider than the terrain it stands on — a "
              "PARTITION bar at [placement] split_tol_m, not a cockpit "
              "threshold: it is REPORT under §31 (4) whatever its count",
              threshold=float(v16b.get("split_tol_m", 0.3)), exact=False)
        # the span bar is a partition choice (§17: "split_tol_m 0.3 stays
        # the CUT tolerance, not an acceptance") — never critical
        for rec in list(critical):
            if rec["kind"].startswith("§16b body wider"):
                critical.remove(rec)
                report.append(rec)
    if torn is not None:
        steps = [float(q) for q in torn.get("rigid_steps", ())]
        _item("§16c torn seam between two halves of one solid",
              sum(1 for q in steps if q > vis), [(q, "") for q in steps],
              f"a seam of {torn.get('rigid_seams', 0)} rigid torn seam(s); "
              f"the §16c bar itself is 0 seams at any step",
              threshold=vis)
    return {
        "ruling": COCKPIT_RULING,
        "motion_step_m": law["motion_step_m"],
        "visual_m": vis,
        "approach_km": law["approach_km"],
        "torn_seams_read": torn is not None,
        "critical_visual": critical,
        "critical_visual_n": sum(q["n"] for q in critical),
        "report": report,
        "report_n": sum(q["n"] for q in report),
        "motion_note": (
            "not readable at this stage — §17 prices an object STANDING ON "
            "the pavement at the motion threshold, and the placement plan "
            "carries no pavement role per body (an instrument limit, not a "
            "zero)"),
    }


def cockpit_block_lines(c: _t.Mapping[str, _t.Any]) -> list[str]:
    """:func:`cockpit_block`'s classification as the lines both tools
    print, FIRST, before the §14 bars (§31 (6))."""
    out = [f"   --- COCKPIT (owner RULINGS {c['ruling']}, object stage "
           f"§17): motion {c['motion_step_m']:g} m on pavement, visual "
           f"{c['visual_m']:g} m in view "
           f"(taxi scale: every body of this pack stands at the airport; "
           f"12ad's SPAN rule removes nothing here — a torn seam shares an "
           f"AUTHORED VERTEX and a float is two zeros at one place, so "
           f"every row below is welded by construction)"
           + ("" if c["torn_seams_read"] else "; torn seams NOT read in "
              "this run") + " ---",
           f"   COCKPIT motion: {c['motion_note']}",
           f"   COCKPIT CRITICAL visual: {c['critical_visual_n']} body/seam "
           f"row(s) over {c['visual_m']:g} m"
           + ("" if c["critical_visual_n"] else " — none")]
    for q in c["critical_visual"]:
        out.append(f"      {q['n']:5d}  {q['kind']} — worst "
                   f"{q['worst_m']:.2f} m {q['worst_name'] or ''} at "
                   f"{q['worst_at']}"
                   + ("" if q["exact"] else
                      f"  [counted at {q['threshold_m']:g} m, this "
                      f"census's own tolerance]"))
        out.append(f"             {q['note']}")
    out.append(f"   COCKPIT REPORT: {c['report_n']} row(s) — under the "
               f"visual threshold, or a partition choice (§31 (4)):")
    for q in c["report"]:
        out.append(f"      {q['n']:5d}  {q['kind']}"
                   + (f" — worst {q['worst_m']:.2f} m {q['worst_name'] or ''}"
                      if q["worst_m"] is not None else ""))
    if not c["report"]:
        out.append("      (none)")
    return out
