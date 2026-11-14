"""The CLASS BARS of ``tools/drawn_site.py`` (#1903): its per-component
readings of what X-Plane draws, judged per placed OBJECT, one line each.
An object is one written row, or every split body ``<stem>__b<N>_<hash>``
of one stem on one tile (the engine's split of one authored object: a
body may hang in the air because its supports went to another body).

* CLEARANCE (every object) -- the least height of any STILL solid vertex
  (a wheel, a column, a foot; a moving part only when everything moves,
  #1984) over what is drawn under it (the mesh, or another placement's
  surface: an interior on its terminal's floor): over the ground bar
  nothing of the object rests on anything and it FLOATS;
* BASE (cut structures only: a footed concave cut shell whose rim stands
  at grade -- a car's body, a roof or an overhang stands over the ground
  by design) -- the worst footed component's seat, its median
  bottom minus the drawn mesh (``drawn_site._floor_read``): FLOAT / BURY
  against the ground bar; other objects list it, unjudged;
* DECK END -- a deck's open edges that join at their top: the step to the
  drawn surface beyond (pavement, or another object's hard surface); in
  END-EDGE MODE (``drawn_site --end-lines PLAN``) the run at each of the
  plan's END LINES instead (a ramp's long sides and its floor openings are
  edges, spec othh-deck-round2 S5);
* MOUTH (footed bodies -- a cut shell, a covered or a convex body, never
  a thin part or a plate -- and, with ``--mouth``, one per SITE: the
  opening nearest the named site, within its radius -- the owner names
  the mouth he saw;
  every other floor opening is listed) -- its floor against the drawn
  ground 1.5 m out (and 3 m out, for reference), and the drawn ramp's
  width at the floor's level against the opening;
* EDGE -- every other open edge's step, listed and NOT judged: a wall's
  end cap over the ramp that continues past it is a lawful drop.

Seams are judged against ``tol`` (``SEAM_TOL_M``, ``drawn_check``'s
``--tol``).  It reads only the readings dict; it measures nothing."""
from __future__ import annotations

import math
import os
import re

__all__ = ["SEAM_TOL_M", "RAMP_WIDTH_SLACK_M", "object_bars", "bar_lines", "print_bars"]

#: the seam bar (drawn_check's ``--tol``, the #1903 gate)
SEAM_TOL_M = 0.3
#: a ramp narrower than its mouth's opening by more than this fails
RAMP_WIDTH_SLACK_M = 1.0
#: components whose bottom stands this close to the object's lowest still
#: vertex are its feet (the parts that meet the ground)
FOOT_BAND_M = 1.0
#: the shapes that carry a mouth (a stair, a mast or a pad has none)
MOUTH_SHAPES = ("concave cut shell", "covered (deck/roof over floor)", "convex body")
#: a concave shell whose rim stands within this of the ground is a cut
CUT_RIM_M = 3.0
#: a split body's suffix (``obj8_split``; ``drawn_check._BODY``)
_BODY = re.compile(r"__b\d+_[0-9a-f]+(?=\.obj$)", re.IGNORECASE)


def _stem(path: str) -> str:
    """An OBJ's file stem, a split body's suffix removed (the key a rebake
    plan's member resource and a written body share)."""
    return _BODY.sub("", os.path.basename(str(path))).rsplit(".", 1)[0].lower()


def _verdict(bad: bool) -> str:
    return "FAIL" if bad else "PASS"


def _floor_read(rec: dict) -> dict:
    """A component's SEAT: for a concave cut shell its open floor (the
    floor must sit on the cut under it, however deep), for anything else
    its open plan less the part spanning a cut (a portal's grade plate or
    a deck over the road in the cut); the whole bottom where neither has
    a reading."""
    keys = (("open_floor_minus_mesh",) if rec["shape"]["class"] == "concave cut shell"
            else ("seat_minus_mesh", "open_floor_minus_mesh"))
    for k in keys:
        if rec.get(k, {}).get("n"):
            return rec[k]
    return rec["bottom_minus_mesh"]


def object_key(rec: dict) -> tuple:
    """``(pack, tile, row or split stem)``: split bodies fold to one."""
    name = rec["def"]
    stem = _BODY.sub("", name)
    return (rec["pack"], rec["tile"], stem if stem != name else rec["row"])


def object_bars(comps: list[dict], tol: float, ground_bar: float,
                min_run_m: float, placements: list[dict] = (),
                site: tuple[float, float, float] | None = None,
                end_lines: "dict | None" = None) -> list[dict]:
    """The class bars (the module docstring) per object of one site's
    components and placement clearances; seams against ``tol``, the base
    and the clearance against ``ground_bar``; open edges shorter than
    ``min_run_m`` are not read; the mouth nearest ``site`` ``(lat, lon,
    radius_m)`` is judged.  ``end_lines`` (END-EDGE MODE): ``{OBJ stem:
    [end line, ...]}`` off the rebake plan's deck members — a deck's END is
    read at its end lines (:func:`_true_ends`)."""
    gaps: dict = {}
    for p in placements:
        if p.get("clearance_m") is not None:
            gaps.setdefault((p["pack"], p["tile"], p["row"]), p)
    groups: dict = {}
    for rec in comps:
        groups.setdefault(object_key(rec), []).append(rec)
    out = []
    for key, recs in groups.items():
        big = max(recs, key=lambda q: q["plan_m2"])
        rows = sorted({q["row"] for q in recs})
        o = {"pack": key[0], "tile": key[1], "rows": rows, "def": big["def"],
             "anchor": big["anchor"], "shape": big["shape"]["class"],
             "components": len(recs), "moving_components": sum(q["moving"] for q in recs)}
        gap = [gaps[(key[0], key[1], r)] for r in rows if (key[0], key[1], r) in gaps]
        if gap:
            g = min(gap, key=lambda p: p["clearance_m"])
            o["clearance"] = {"m": g["clearance_m"], "at": g["at"], "of": g["of"],
                              "verdict": "FLOAT" if g["clearance_m"] > ground_bar else "PASS"}
        footed = _footed(recs, min((p["lowest_z"] for p in gap), default=None))
        if footed:
            cut = any(_cut_shell(q, ground_bar) for q, _fp in footed)
            o["base"] = _base(footed, ground_bar, judged=cut)
        lines = None if end_lines is None else end_lines.get(_stem(big["def"]), [])
        o.update(_seams(recs, {q["component"] for q, _fp in footed}, tol, min_run_m, lines))
        out.append(o)
    _judge_mouth(out, site, tol)
    for o in out:
        verdicts = [o[k]["verdict"] for k in ("base", "clearance")
                    if k in o and o[k]["verdict"] != "not judged"]
        verdicts += [d["verdict"] for d in o["deck_ends"]]
        verdicts += [m[k] for m in o["mouths"] for k in ("floor_verdict", "width_verdict")]
        o["verdict"] = "FAIL" if any(v != "PASS" for v in verdicts) else "PASS"
    return sorted(out, key=lambda o: (o["verdict"] == "PASS", o["tile"], o["rows"]))


def _cut_shell(rec: dict, ground_bar: float) -> bool:
    """A CUT STRUCTURE: a concave cut shell whose own rim stands at grade
    (within :data:`CUT_RIM_M` of the drawn ground beside it) -- a flat
    roof behind its parapet is a hollow too, 10 m up."""
    sh = rec["shape"]
    rim = sh.get("rim_minus_ground")
    return sh["class"] == "concave cut shell" and rim is not None and abs(rim) <= CUT_RIM_M


def _footed(recs: list[dict], lowest_z: float | None) -> list[tuple[dict, dict]]:
    """``(component, its seat)`` of the still non-deck components whose
    bottom stands within :data:`FOOT_BAND_M` of ``lowest_z`` (the
    object's lowest still vertex; else the lowest such component)."""
    base = [(q, _floor_read(q)) for q in recs
            if not q["deck"] and not q["moving"] and _floor_read(q).get("n")]
    if not base:
        return []
    low = lowest_z if lowest_z is not None else min(q["bottom_z"] for q, _fp in base)
    return [b for b in base if b[0]["bottom_z"] <= low + FOOT_BAND_M]


def _base(footed: list[tuple[dict, dict]], ground_bar: float, judged: bool) -> dict:
    """The BASE bar: the footed component whose seat is worst."""
    q, fp = max(footed, key=lambda b: abs(b[1]["p50"]))
    d = fp["p50"]
    verdict = "FLOAT" if d > ground_bar else "BURY" if d < -ground_bar else "PASS"
    return {"minus_mesh_p50": d, "component": q["component"],
            "footed_components": [b[0]["component"] for b in footed],
            "floating_pct": fp["floating_pct"], "buried_pct": fp["buried_pct"],
            "moving": q["moving"], "at": q["centre"],
            "verdict": verdict if judged else "not judged", "reading": verdict}


#: END-EDGE MODE: an open run is a deck's END when its middle lies within
#: this of one of the plan's end lines (spec othh-deck-round2 S5)
END_MATCH_M = 15.0


def _to_line_m(at, line) -> float:
    """Metres from ``at`` ``(lat, lon)`` to an end line ``((lat, lon), (lat, lon))``."""
    k = 111_320.0
    c = math.cos(math.radians(at[0]))
    (a0, o0), (a1, o1) = line
    px, py = (at[1] - o0) * k * c, (at[0] - a0) * k
    dx, dy = (o1 - o0) * k * c, (a1 - a0) * k
    t = max(0.0, min(1.0, (px * dx + py * dy) / ((dx * dx + dy * dy) or 1.0)))
    return math.hypot(px - t * dx, py - t * dy)


def _true_ends(rows: list[dict], end_lines) -> tuple[list[dict], list[dict]]:
    """END-EDGE MODE: ``(deck ends, other runs)`` — per plan end line the
    open run nearest it within :data:`END_MATCH_M` is the deck's end; the
    deck's long sides and floor openings are edges."""
    ends: dict[int, tuple[float, dict]] = {}
    for k, ln in enumerate(end_lines):
        for r in rows:
            d = _to_line_m(r["at"], ln)
            if d <= END_MATCH_M and (k not in ends or d < ends[k][0]):
                ends[k] = (d, r)
    picked = {id(r) for _d, r in ends.values()}
    return ([dict(r, end_line=k + 0, dist_m=round(d, 1)) for k, (d, r) in sorted(ends.items())],
            [r for r in rows if id(r) not in picked])


def _seams(recs: list[dict], footed_ids: set, tol: float, min_run_m: float,
           end_lines=None) -> dict:
    """The DECK END readings and the floor openings of the footed
    components (``mouth_candidates``, judged by :func:`_judge_mouth`), and
    the EDGE readings.  ``end_lines`` (END-EDGE MODE, ``drawn_site
    --end-lines``): a deck's ends are the runs at the plan's end lines
    (:func:`_true_ends`), not every open run that joins at its top."""
    decks, mouths, edges = [], [], []
    for q in recs:
        bodied = q["shape"]["class"] in MOUTH_SHAPES
        for m in (q.get("mouths", []) if bodied and q["component"] in footed_ids else []):
            fs = m["floor_step"].get("p50")
            mouths.append({"at": m["at"], "floor_step": fs, "component": q["component"],
                           "floor_minus_ramp_3m": m["floor_minus_ramp_3m"],
                           "opening_m": m["opening_m"], "ramp_width_m": m["ramp_width_m"]})
        for r in q["open_runs"]:
            if r["length_m"] < min_run_m or r["step_m"] is None:
                continue
            row = {"at": r["at"], "step": r["step_m"], "length_m": r["length_m"],
                   "joins": r["joins"], "verdict": _verdict(abs(r["step_m"]) > tol)}
            if end_lines is not None:
                (decks if q["deck"] else edges).append(row)
                continue
            (decks if q["deck"] and r["joins"] == "top" else edges).append(row)
    if end_lines is not None:
        decks, other = _true_ends(decks, end_lines)
        edges += other
    return {"deck_ends": decks, "mouths": [], "mouth_candidates": mouths,
            "edges": sorted(edges, key=lambda e: -abs(e["step"]))}


def _judge_mouth(objects: list[dict], site, tol: float) -> None:
    """Move the floor opening nearest ``site`` (within its radius) into
    its object's judged ``mouths``; none without a site."""
    if site is None:
        return
    lat0, lon0, radius = site
    kx = math.cos(math.radians(lat0))

    def dist(m):
        return math.hypot((m["at"][0] - lat0) * 111320.0, (m["at"][1] - lon0) * 111320.0 * kx)
    best = min(((dist(m), i, k) for i, o in enumerate(objects)
                for k, m in enumerate(o["mouth_candidates"])), default=None)
    if best is None or best[0] > radius:
        return
    o = objects[best[1]]
    m = o["mouth_candidates"].pop(best[2])
    fs = m["floor_step"]
    m["floor_verdict"] = _verdict(fs is None or abs(fs) > tol)
    m["width_verdict"] = _verdict(m["ramp_width_m"] + RAMP_WIDTH_SLACK_M < m["opening_m"])
    m["dist_m"] = round(best[0], 1)
    o["mouths"] = [m]


def bar_lines(o: dict) -> str:
    """One object's class bars on one line."""
    parts = []
    c = o.get("clearance")
    if c:
        parts.append(f"clearance {c['m']:+.2f} {c['verdict']}"
                     f"{'' if c['of'] == 'still parts' else ' (all parts move)'}")
    b = o.get("base")
    if b:
        tag = b["verdict"] if b["verdict"] != "not judged" else f"({b['reading']}, not judged)"
        parts.append(f"base {b['minus_mesh_p50']:+.2f} {tag}"
                     f"{' (moving part)' if b['moving'] else ''}")
    if o["deck_ends"]:
        parts.append("deck ends " + "/".join(f"{d['step']:+.2f}" for d in o["deck_ends"][:4])
                     + (" FAIL" if any(d["verdict"] == "FAIL" for d in o["deck_ends"])
                        else " PASS"))
    for m in o["mouths"]:
        fs = "n/a" if m["floor_step"] is None else f"{m['floor_step']:+.2f}"
        r3 = m["floor_minus_ramp_3m"]
        parts.append(f"MOUTH @{m['at'][0]:.5f},{m['at'][1]:.5f} ({m['dist_m']} m from site)"
                     f" floor-drawn {fs} ({'n/a' if r3 is None else f'{r3:+.2f}'} at 3 m)"
                     f" {m['floor_verdict']}, opening {m['opening_m']} / ramp"
                     f" {m['ramp_width_m']} m {m['width_verdict']}")
    if o.get("mouth_candidates"):
        parts.append(f"{len(o['mouth_candidates'])} floor openings listed")
    if o["edges"]:
        e = o["edges"][0]
        nf = sum(x["verdict"] == "FAIL" for x in o["edges"])
        parts.append(f"edges (not judged) worst {e['step']:+.2f} ({e['joins']}),"
                     f" {nf}/{len(o['edges'])} over tol")
    name = os.path.basename(o["def"])
    mv = f", {o['moving_components']} moving" if o["moving_components"] else ""
    rows = "+".join(f"obj{r}" for r in o["rows"][:3]) + ("+..." if len(o["rows"]) > 3 else "")
    return f"  {o['verdict']} {o['tile']} {rows} {name} [{o['shape']}{mv}]: " + " | ".join(parts)


def print_bars(rep: dict, ground_bar: float) -> None:
    """The one-screen summary: every object's class bars, per site."""
    print(f"\nCLASS BARS (seam tol {rep['tol_m']:.2f} m, ground bar {ground_bar:.2f} m;"
          f" ANIM at rest, datarefs {rep['datarefs_at_rest'] or 'all 0'})")
    for s in rep["sites"]:
        objs = s.get("objects", [])
        nf = sum(o["verdict"] == "FAIL" for o in objs)
        print(f"SITE {s['name']} @{s['lat']:.6f},{s['lon']:.6f} r {s['radius_m']:g} m:"
              f" {len(objs)} objects, {nf} FAIL, drawn mesh {s['mesh_z']}")
        for o in objs:
            print(bar_lines(o))
