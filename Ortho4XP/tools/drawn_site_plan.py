"""THE PLAN READ ON THE DRAWN MESH (#1884 round 2, spec D): ``drawn_site.py
--plan``'s compare mode.

``drawn_site.py`` reads the WRITTEN pack; a lane that has only replayed
(``v2_rebake_replay.py plan --plan-out``) or must judge thousands of split
bodies needs the same judgement read off the placement plan.  The lane
metric this replaces (a scratch ``compare2.py``) judged every body by its
lowest point against the ground under it, so a roof seated on its walls
read as a 6 m "float" and a house buried rigidly 7 m read as "fixed".
Here every body is placed the way its plain ``OBJECT`` row draws it — y =
0 on the DRAWN mesh under its anchor, less its ``y_zero`` — and judged by
WHAT CARRIES IT:

* FOOTED (not elevated, feet in the plan): its FOOT points (the body's
  sampled points within ``FOOT_BAND_M`` of its lowest authored y) against
  the mesh: ``foot_min`` (+ = no foot touches: the body floats) and
  ``foot_max`` (− = every foot buried);
* RIDER (``carried by <file>`` / ``bound to <file>`` / ``merged_into``):
  its drawn zero less its CARRIER's, against the authored offset (0 in one
  frame; across frames the rigid offset the drawn mesh gives the two rows'
  origins) — ``offset``, bar 0.05 m;
* GROUP (a §16g unit or a 22o connected group, ``fu:N:M`` in the reason
  or ``unit_of``): its drawn zero less the group's median — ``offset``;
* OWN GROUND (§16 (3), ``footless_own_ground``; #1884's terrain-carried
  base among them): its BASE points against the mesh, ``foot_min`` /
  ``foot_max`` as a footed body's — named with its law, never a footed
  float.

``--base-plan`` judges a second plan on the same mesh and lists every body
whose figure got worse by more than ``--worse`` (default 0.1 m).  It reads
two JSON files and the drawn mesh; it writes nothing and derives no law.
"""
from __future__ import annotations

import json
import math
import re
import typing as _t

import numpy as np

#: a sampled point this close over the body's lowest authored y is a foot
FOOT_BAND_M = 0.5
#: owner bars (memory judge-by-visibility-bars; spec 1884-round2 §5)
RIDER_BAR_M = 0.05
FOOT_BAR_M = 0.3
GROUND_BAR_M = 0.5
_UNIT = re.compile(r"\b(fu:\d+:\d+)")
_FILE = re.compile(r"(?:carried by|bound to|rides?) (objects/\S+?\.obj)")
_OWN_GROUND = "footless_own_ground"
#: a written body file's content hash (``obj8_split.body_resource_name``)
_HASH = re.compile(r"_[0-9a-f]{8}\.obj$")


class Mesh(_t.Protocol):
    def z(self, lat, lon) -> np.ndarray: ...


def load_bodies(path: str) -> list[dict]:
    """Every body of a placement plan JSON (``o4_v2_placement_<ICAO>.json``
    or a replay's ``--plan-out``), flattened with its placement row."""
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    out = []
    for s in d.get("splits", ()):
        pl = s["placement"]
        for b in s["bodies"]:
            out.append(dict(b, placement=pl))
    return out


def body_key(b: dict) -> tuple:
    return (b["placement"]["resource"], b["placement"]["index"], b["body_id"])


def kind_of(b: dict) -> tuple[str, str]:
    """``(kind, carrier)``: footed / rider (carrier file) / group (unit id)
    / own_ground / elevated (no carrier named)."""
    # the seat that STANDS, never the one a later pass replaced ("; was: …")
    why = str(b.get("anchor_reason", "")).split("; was:")[0]
    if not b.get("elevated") and int(b.get("feet") or 0):
        return "footed", ""
    if why.startswith(_OWN_GROUND):
        return "own_ground", ""
    hit = _FILE.search(why)
    unit = _UNIT.search(why)
    if hit:
        return "rider", hit.group(1)
    if b.get("merged_into") and not unit:
        return "rider", str(b["merged_into"])
    if unit or b.get("unit_of"):
        return "group", unit.group(1) if unit else str(b["unit_of"])
    return "elevated", ""


def drawn_zeros(bodies: _t.Sequence[dict], mesh: Mesh, rigid: bool = False) -> np.ndarray:
    """Where each body's authored y = 0 is DRAWN: the mesh under its anchor
    less its ``y_zero`` (a plain ``OBJECT`` row); NaN off the mesh.
    ``rigid``: where its placement's own row, kept whole, draws it (the
    mesh under the row's origin) — the installed reading of an undone
    placement (spec 1884-round2 §5 (6))."""
    if rigid:
        return mesh.z([b["placement"]["lat"] for b in bodies],
                      [b["placement"]["lon"] for b in bodies])
    la = np.array([b["anchor"]["lat"] for b in bodies], float)
    lo = np.array([b["anchor"]["lon"] for b in bodies], float)
    y0 = np.array([float(b.get("y_zero") or 0.0) for b in bodies], float)
    return mesh.z(la, lo) - y0


def base_points(b: dict) -> list[tuple[float, float, float]]:
    """The body's sampled points within :data:`FOOT_BAND_M` of its lowest."""
    pts = [tuple(q) for q in (b.get("geom_pts") or ()) if len(q) >= 3]
    if not pts:
        return []
    y_min = min(q[2] for q in pts)
    return [q for q in pts if q[2] <= y_min + FOOT_BAND_M]


def judge(bodies: _t.Sequence[dict], mesh: Mesh, rigid: bool = False) -> list[dict]:
    """One row per body (module doc); ``rigid``: :func:`drawn_zeros`'s."""
    zero = drawn_zeros(bodies, mesh, rigid)
    by_file: dict[str, list[int]] = {}
    for i, b in enumerate(bodies):
        name = str(b.get("new_resource") or "")
        by_file.setdefault(name, []).append(i)
        by_file.setdefault(_HASH.sub(".obj", name), []).append(i)
    groups: dict[str, list[float]] = {}
    kinds = [kind_of(b) for b in bodies]
    for (k, c), z in zip(kinds, zero, strict=True):
        if k == "group" and not math.isnan(z):
            groups.setdefault(c, []).append(float(z))
    pts = [base_points(b) for b in bodies]
    flat = [q for p in pts for q in p]
    mz = mesh.z([q[0] for q in flat], [q[1] for q in flat]) if flat else np.array([])
    rows, at = [], 0
    for i, b in enumerate(bodies):
        k, c = kinds[i]
        n = len(pts[i])
        d = (zero[i] + np.array([q[2] for q in pts[i]]) - mz[at:at + n]) if n else np.array([])
        at += n
        d = d[~np.isnan(d)]
        unit = _UNIT.search(str(b.get("anchor_reason", "")).split("; was:")[0])
        row = {"key": list(body_key(b)), "kind": k, "carrier": c,
               "unit": unit.group(1) if unit else str(b.get("unit_of") or ""),
               "lat": b["anchor"]["lat"], "lon": b["anchor"]["lon"],
               "zero": _r(zero[i]), "reason": str(b.get("anchor_reason", ""))[:160],
               "foot_min": _r(d.min()) if d.size else None,
               "foot_max": _r(d.max()) if d.size else None, "offset": None}
        if k == "rider" and c in by_file:
            j = _nearest(by_file[c], b, bodies)
            row["offset"] = _r(zero[i] - zero[j] - _authored(b, bodies[j], mesh))
        elif k == "group" and groups.get(c):
            row["offset"] = _r(zero[i] - float(np.median(groups[c])))
        rows.append(row)
    return rows


def group_seats(rows: _t.Sequence[dict]) -> list[dict]:
    """THE CARRIER'S SEAT of every group a body rides (a unit or connected
    group): ALL its members' lowest base against the mesh — ``foot_min``
    over the group (+ = no member touches the ground)."""
    riding = {r["carrier"] for r in rows if r["kind"] == "group"}
    by: dict[str, list[dict]] = {}
    for r in rows:
        if r["unit"] in riding and r["foot_min"] is not None:
            by.setdefault(r["unit"], []).append(r)
    return sorted(({"group": g, "members": len(rs),
                    "foot_min": min(r["foot_min"] for r in rs),
                    "foot_max": max(r["foot_max"] for r in rs),
                    "lat": rs[0]["lat"], "lon": rs[0]["lon"]}
                   for g, rs in by.items()), key=lambda d: -d["foot_min"])


def _nearest(cands: _t.Sequence[int], b: dict, bodies: _t.Sequence[dict]) -> int:
    """The carrier a hash-less file name in a reason means: the candidate
    body anchored nearest the rider (one stem is written per placement)."""
    a = b["anchor"]
    return min(cands, key=lambda j: (bodies[j]["anchor"]["lat"] - a["lat"]) ** 2
               + (bodies[j]["anchor"]["lon"] - a["lon"]) ** 2)


def _authored(rider: dict, carrier: dict, mesh: Mesh) -> float:
    """The rider's authored zero over its carrier's: 0 in one frame; else
    the rigid offset the drawn mesh gives the two rows' origins."""
    a, c = rider["placement"], carrier["placement"]
    if (a["lat"], a["lon"]) == (c["lat"], c["lon"]):
        return 0.0
    z = mesh.z([a["lat"], c["lat"]], [a["lon"], c["lon"]])
    return 0.0 if np.isnan(z).any() else float(z[0] - z[1])


def _r(x) -> "float | None":
    return None if x is None or (isinstance(x, float) and math.isnan(x)) \
        else round(float(x), 3)


def summary(rows: _t.Sequence[dict]) -> dict:
    """The spec §5 bars over ``rows``: footed bodies within the ground bar,
    footed floats over :data:`FOOT_BAR_M`, riders and group members off
    their carrier by more than :data:`RIDER_BAR_M`, own-ground bodies."""
    footed = [r for r in rows if r["kind"] == "footed" and r["foot_min"] is not None]
    within = [r for r in footed if r["foot_min"] <= GROUND_BAR_M and r["foot_max"] >= -GROUND_BAR_M]
    off = [r for r in rows if r["offset"] is not None and abs(r["offset"]) > RIDER_BAR_M]
    return {"bodies": len(rows),
            "kinds": {k: sum(1 for r in rows if r["kind"] == k)
                      for k in sorted({r["kind"] for r in rows})},
            "footed_judged": len(footed), "footed_within_ground_bar": len(within),
            "footed_float": sorted((r for r in footed if r["foot_min"] > FOOT_BAR_M),
                                   key=lambda r: -r["foot_min"]),
            "carried_off": sorted(off, key=lambda r: -abs(r["offset"])),
            "own_ground_float": sorted((r for r in rows if r["kind"] == "own_ground"
                                        and (r["foot_min"] or 0.0) > GROUND_BAR_M),
                                       key=lambda r: -r["foot_min"]),
            "group_float": [g for g in group_seats(rows) if g["foot_min"] > GROUND_BAR_M]}


def figure(r: dict) -> "float | None":
    """A row's one judged number (worse = larger): the footed/own-ground
    body's float or burial past the ground, a carried body's |offset|."""
    if r["offset"] is not None:
        return abs(r["offset"])
    if r["foot_min"] is None:
        return None
    return max(r["foot_min"], -r["foot_max"], 0.0)


def worse(base: _t.Sequence[dict], new: _t.Sequence[dict], by: float) -> list[dict]:
    """Every body of ``new`` whose :func:`figure` exceeds ``base``'s by more
    than ``by`` (a body new to the plan is compared with nothing)."""
    old = {tuple(r["key"]): figure(r) for r in base}
    out = []
    for r in new:
        f, g = figure(r), old.get(tuple(r["key"]))
        if f is not None and g is not None and f - g > by:
            out.append(dict(r, was=g, now=f))
    return sorted(out, key=lambda r: -(r["now"] - r["was"]))


def box_of(paths: _t.Sequence[str], pad: float = 0.002) -> tuple[float, float, float, float]:
    """``(west, south, east, north)`` over every body anchor and point."""
    la, lo = [], []
    for p in paths:
        for b in load_bodies(p):
            la.append(b["anchor"]["lat"])
            lo.append(b["anchor"]["lon"])
            for q in b.get("geom_pts") or ():
                la.append(q[0])
                lo.append(q[1])
    return min(lo) - pad, min(la) - pad, max(lo) + pad, max(la) + pad


def compare(plan: str, mesh: Mesh, base_plan: "str | None" = None,
            worse_by: float = 0.1, base_rigid: bool = False,
            only: "_t.Callable[[dict], bool] | None" = None) -> dict:
    """The report: ``rows`` and ``summary`` of ``plan``; with ``base_plan``
    also its ``base_summary`` and the ``worse`` list.  ``base_rigid``: the
    base is ``plan`` itself drawn rigid (``base_plan`` unused).  ``only``:
    the bodies judged (a placement-row filter)."""
    pick = (lambda bs: [b for b in bs if only(b)]) if only else (lambda bs: bs)
    rows = judge(pick(load_bodies(plan)), mesh)
    rep = {"plan": plan, "rows": rows, "summary": summary(rows)}
    if base_rigid:
        base_plan = plan
    if base_plan:
        brows = judge(pick(load_bodies(base_plan)), mesh, rigid=base_rigid)
        rep.update(base_plan=base_plan, base_summary=summary(brows),
                   worse=worse(brows, rows, worse_by))
    return rep


def print_compare(rep: dict, top_n: int) -> None:
    def line(r):
        return (f"  {r['key'][0].split('/')[-1]}#{r['key'][1]} {r['key'][2]:<6} "
                f"{r['lat']:.5f},{r['lon']:.5f} {r['kind']:<10} foot "
                f"{r['foot_min']}..{r['foot_max']} offset {r['offset']}  {r['reason'][:90]}")
    for tag in ("base_summary", "summary"):
        s = rep.get(tag)
        if not s:
            continue
        print(f"{tag}: {s['bodies']} bodies {s['kinds']}; footed within "
              f"{GROUND_BAR_M} m {s['footed_within_ground_bar']} of {s['footed_judged']}; "
              f"footed floats > {FOOT_BAR_M} m {len(s['footed_float'])}; carried off > "
              f"{RIDER_BAR_M} m {len(s['carried_off'])}; own-ground floats > "
              f"{GROUND_BAR_M} m {len(s['own_ground_float'])}; group seats floating > "
              f"{GROUND_BAR_M} m {len(s['group_float'])}")
    s = rep["summary"]
    for name in ("footed_float", "carried_off", "own_ground_float", "group_float"):
        print(f"{name} (top {top_n}):")
        for r in s[name][:top_n]:
            print(line(r) if "key" in r else f"  {r}")
    if "worse" in rep:
        print(f"worse than the base plan by > its bar: {len(rep['worse'])}")
        for r in rep["worse"][:top_n]:
            print(f"{line(r)}  was {r['was']} now {r['now']}")
