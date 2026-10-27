"""THE SEAT AS WRITTEN — the census of the DSF the owner loads and the mesh
it drapes on, never of the plan (#1214 round 3, acceptance (i)-(iv)).

Rounds 1-2 passed because ``seat_feet_census --rebake-plan`` read the PLAN:
a plan body whose file was never written, or a deck the I-4 skip left on
its authored row, is invisible there.  Every reading here starts from a
WRITTEN DSF text dump and the files in the pack:

* :func:`missing_defs` — (i) an ``OBJECT_DEF`` the writer added (absent
  from the PRISTINE dump) that names no file in the pack;
* :func:`row_zero` — where a written row puts the AUTHORED ``y = 0`` of
  its resource: the row's own height (``OBJECT`` drapes at the mesh,
  ``OBJECT_AGL`` adds its column, ``OBJECT_MSL`` states it) less the
  offset its body file baked (the ``# o4 split of ... offset x y z``
  header ``obj8_split`` writes);
* :func:`deck_rows` — (ii)/(iii) per pack deck of the rebake plan, the
  deck top at each END LINE against the mesh there;
* :func:`frame_rows` — (iv) per lifted footed frame, the spread of its
  written zeros and where the author's ground plane ``y = -lift`` lands.
"""
from __future__ import annotations

import os
import re
import typing as _t

from .bridge_approach import _median

__all__ = ["missing_defs", "resource_of", "body_offset_y", "row_zero",
           "deck_rows", "frame_rows", "member_feet", "feet_lines", "written_lines"]

Surface = _t.Callable[[float, float], "float | None"]

_BODY = re.compile(r"__b\d+(?:_[0-9a-f]{8})?\.obj$")
_HEAD = re.compile(r"^# o4 split of .* offset (\S+) (\S+) (\S+)")


def resource_of(def_path: str) -> str:
    """The authored resource a body file was cut from (``objects/x__b3_
    0a1b2c3d.obj`` -> ``objects/x.obj``); a plain resource is itself."""
    return _BODY.sub(".obj", def_path)


def _file(pack_root: str, rel: str) -> str:
    return os.path.join(pack_root, *rel.replace("\\", "/").split("/"))


def missing_defs(written: _t.Any, pristine: _t.Any, pack_root: str) -> list[str]:
    """(i): the definitions the writer ADDED that name no file."""
    authored = set(getattr(pristine, "object_defs", ()) or ())
    return sorted(d for d in set(getattr(written, "object_defs", ()) or ())
                  if d not in authored and not os.path.isfile(_file(pack_root, d)))


def body_offset_y(pack_root: str, def_path: str, memo: dict) -> float:
    """The ``y`` a body file baked out of its vertices (0 for an authored
    resource, and for a file whose header names no offset)."""
    if def_path not in memo:
        y = 0.0
        if _BODY.search(def_path):
            try:
                with open(_file(pack_root, def_path), "r", encoding="latin-1") as fh:
                    for _i, ln in zip(range(40), fh, strict=False):
                        mt = _HEAD.match(ln)
                        if mt:
                            y = float(mt.group(2))
                            break
            except OSError:
                pass
        memo[def_path] = y
    return memo[def_path]


def row_zero(row: _t.Any, surface: Surface, pack_root: str, memo: dict
             ) -> "float | None":
    """World height of the authored ``y = 0`` a written row puts its
    resource at, or ``None`` off the mesh."""
    kind = getattr(row, "kind", "OBJECT")
    elev = float(getattr(row, "elevation", 0.0) or 0.0)
    if kind == "OBJECT_MSL":
        base = elev
    else:
        g = surface(float(row.lat), float(row.lon))
        if g is None:
            return None
        base = float(g) + (elev if kind == "OBJECT_AGL" else 0.0)
    return base - body_offset_y(pack_root, row.def_path, memo)


def _zeros_by_resource(written: _t.Any, surface: Surface, pack_root: str
                       ) -> dict[str, list[tuple[float, float, float]]]:
    memo: dict = {}
    out: dict[str, list[tuple[float, float, float]]] = {}
    for r in getattr(written, "placements", ()) or ():
        z = row_zero(r, surface, pack_root, memo)
        if z is not None:
            out.setdefault(resource_of(r.def_path), []).append(
                (float(r.lat), float(r.lon), z))
    return out


def _nearest_zero(rows: _t.Sequence[tuple[float, float, float]],
                  at: tuple[float, float], reach_deg: float = 0.003
                  ) -> "float | None":
    """The median zero of a resource's written rows standing near ``at``
    (a resource placed at N anchors has N groups of rows)."""
    near = [z for la, lo, z in rows
            if abs(la - at[0]) <= reach_deg and abs(lo - at[1]) <= reach_deg]
    return _median(near) if near else None


def deck_rows(written: _t.Any, rebake: _t.Any, surface: Surface, pack_root: str,
              step_m: float) -> list[dict]:
    """(ii)/(iii): per pack deck (``deck_kind`` flag / signature with a
    ring or two end lines), the written deck top at each end line against
    the mesh there.  Class A (a flag deck over airside, the solve's own
    ``deck_datum_z``, the airport's pavement running across it — RULINGS
    2026-10-27c) reads its end lines by ``airside_deck_seat``; a
    free-standing deck (``placement_family.frame_is_bridge``) reads its
    plate's end lines and the 22p classification."""
    from .airside_deck_seat import airside_end_ground, end_tops, pavement_runs_across
    from .anchor_rule import Datum
    from .bridge_approach import approach_seat, end_ground
    from .placement_family import frame_is_bridge
    from .rebake_plan import end_line_stations
    zeros = _zeros_by_resource(written, surface, pack_root)
    water = getattr(surface, "water", None)
    out = []
    for u in rebake.units:
        bridge = frame_is_bridge(u)
        for m in u.members:
            top = m.deck_top_y
            kind = m.deck_kind or ""
            if top is None or kind not in ("flag", "signature"):
                continue
            ring = tuple(m.deck_ring or ())
            at = ((sum(q[0] for q in ring) / len(ring), sum(q[1] for q in ring) / len(ring))
                  if ring else tuple(u.anchor))
            z0 = _nearest_zero(zeros.get(m.resource, ()), at)
            if z0 is None:
                continue
            row = {"resource": m.resource, "unit": u.id, "kind": kind,
                   "deck_top": z0 + float(top), "class": "", "ends": (), "note": ""}
            if (m.deck_datum_z is not None and ring
                    and pavement_runs_across(ring, surface, step_m)):
                got = airside_end_ground(ring, surface, step_m)
                row["class"] = "A airside"
                if got is None:
                    row["note"] = "no two airside end lines read"
                    out.append(row)
                    continue
                tops = end_tops(m, got[1], tuple(u.anchor), step_m)
                row["ends"] = tuple(z0 + t - g for t, g in zip(tops, got[0], strict=True))
            elif bridge and m.deck_ends:
                ends = tuple(tuple((float(q[0]), float(q[1])) for q in ln)
                             for ln in m.deck_ends)
                gs = [end_ground(end_line_stations([e], step_m), surface, water)
                      for e in ends]
                if any(g is None for g in gs):
                    continue
                row["class"] = "B overpass"
                row["ends"] = tuple(row["deck_top"] - g[0] for g in gs)
                seat = approach_seat(Datum(float(top), (), "deck top", ends=ends,
                                           step_m=step_m), surface,
                                     origin=tuple(u.anchor), authored_agl_m=u.agl_m)
                if seat is not None and "authored clearance" in seat.reason:
                    g0 = surface(*u.anchor)
                    row["note"] = ("authored clearance (22p): deck "
                                   f"{row['deck_top'] - float(g0):+.2f} over the road"
                                   if g0 is not None else "authored clearance (22p)")
            else:
                continue
            out.append(row)
    return out


def frame_rows(written: _t.Any, rebake: _t.Any, surface: Surface, pack_root: str,
               min_members: int = 20) -> list[dict]:
    """(iv): per footed frame lifted by an authored ``OBJECT_AGL`` with at
    least ``min_members`` members, the written zeros of its resources'
    rows (median, spread, rows more than 0.3 m off it) and the height of
    the author's ground plane ``y = -lift`` over the mesh at its anchor."""
    zeros = _zeros_by_resource(written, surface, pack_root)
    out = []
    for u in rebake.units:
        lift = float(u.agl_m or 0.0)
        if lift <= 0.0 or len(u.members) < min_members:
            continue
        zs = [z for m in u.members for _la, _lo, z in zeros.get(m.resource, ())]
        if not zs:
            continue
        med = _median(zs)
        g = surface(*u.anchor)
        out.append({"unit": u.id, "members": len(u.members), "rows": len(zs),
                    "zero": med, "spread": max(zs) - min(zs),
                    "off": sum(1 for z in zs if abs(z - med) > 0.3),
                    "author_ground": med - lift,
                    "mesh_at_anchor": None if g is None else float(g)})
    return out


def member_feet(written: _t.Any, rebake: _t.Any, surface: Surface, pack_root: str,
                min_members: int = 10, tol_m: float = 0.3) -> list[dict]:
    """RULINGS 2026-10-22q: per frame of at least ``min_members`` members,
    every member's ground-contact feet against the mesh as WRITTEN — the
    median of ``zero + foot y - ground`` (+ floats, - sinks) — and whether
    the member touches AIRSIDE (a foot on or within 1 m of an airside face,
    ``airside_group_seat``'s reading).  The airside members are the bar
    (their feet on the solved airside); the rest are the #1138 fill / cut
    sites, listed with how far they sink or float."""
    from . import anchor_rule as _ar
    from .airside_group_seat import _probes, airside_pavement
    roles = getattr(surface, "roles", None)
    airside_role = airside_pavement(surface)
    zeros = _zeros_by_resource(written, surface, pack_root)
    out = []
    for u in rebake.units:
        if len(u.members) < min_members:
            continue
        lift = float(u.agl_m or 0.0)
        for m in u.members:
            feet = [f for p in m.parts if not p.line for f in (p.feet or ())]
            if not feet:
                continue
            at = (sum(f[0] for f in feet) / len(feet), sum(f[1] for f in feet) / len(feet))
            z0 = _nearest_zero(zeros.get(m.resource, ()), at)
            if z0 is None:
                continue
            res, air_res = [], []
            for la, lo, y in feet:
                g = surface(la, lo)
                if g is not None:
                    res.append(z0 + float(y) - float(g))
            if roles is not None:
                pts = []
                for la, lo, _y in feet:
                    ml, mo = _ar._m_per_deg(la)
                    pts.extend(_probes(la, lo, ml, mo))
                got = roles.roles_many([q[0] for q in pts], [q[1] for q in pts])
                k = len(pts) // len(feet)
                for i, (_la, _lo, y) in enumerate(feet):
                    hit = next((j for j in range(k) if airside_role(got[i * k + j])), None)
                    if hit is None:
                        continue
                    g = surface(*pts[i * k + hit])
                    if g is not None:
                        air_res.append(z0 + float(y) - float(g))
            if res:
                out.append({"unit": u.id, "resource": m.resource, "airside": bool(air_res),
                            "offset": _median(air_res) if air_res else _median(res),
                            "all_feet": _median(res),
                            "feet": len(air_res) or len(res), "lift": lift})
    return out


def feet_lines(rows: _t.Sequence[dict], tol_m: float = 0.3) -> list[str]:
    """The 22q block: per frame, the airside members' foot offset and the
    members that sink or float (the #1138 fill / cut sites)."""
    out = ["   --- AIRSIDE GROUPS (RULINGS 2026-10-22q): member feet vs the mesh ---"]
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["unit"], []).append(r)
    for uid in sorted(by):
        rs = by[uid]
        air = [r for r in rs if r["airside"]]
        if not air:
            continue
        offs = sorted(r["offset"] for r in air)
        bad = [r for r in air if abs(r["offset"]) > tol_m]
        out.append(f"   {uid}: {len(air)} airside member(s), AIRSIDE-CONTACT foot offset median "
                   f"{offs[len(offs) // 2]:+.2f} m (range {offs[0]:+.2f}..{offs[-1]:+.2f}); "
                   f"> {tol_m:g} m off: {len(bad)}")
        for r in sorted(rs, key=lambda q: -abs(q["offset"])):
            if abs(r["offset"]) <= tol_m:
                break
            out.append(f"      {'airside ' if r['airside'] else 'other   '}"
                       f"{r['resource'].rsplit('/', 1)[-1]:28s} "
                       f"{'floats' if r['offset'] > 0 else 'sinks '} {abs(r['offset']):5.2f} m"
                       f" ({r['feet']} {'airside ' if r['airside'] else ''}feet; all feet "
                       f"{r['all_feet']:+.2f})")
    return out


def written_lines(missing: _t.Sequence[str], decks: _t.Sequence[dict],
                  frames: _t.Sequence[dict], tol_m: float = 0.3) -> list[str]:
    """The census block the tool prints."""
    out = ["   --- THE SEAT AS WRITTEN (DSF + mesh; #1214 round 3) ---",
           f"   (i) OBJECT_DEF files missing from the pack: {len(missing)} (bar 0)"
           + ("   *** VIOLATED ***" if missing else "")]
    out.extend(f"      {d}" for d in missing[:8])
    a = [d for d in decks if d["class"].startswith("A")]
    bad_a = [d for d in a if not d["ends"] or any(abs(e) > tol_m for e in d["ends"])]
    out.append(f"   (ii) airside hard decks: {len(a)}, an end line > {tol_m:g} m "
               f"off the mesh: {len(bad_a)} (bar 0)"
               + ("   *** VIOLATED ***" if bad_a else ""))
    for d in sorted(a, key=lambda q: q["resource"]):
        out.append(f"      {d['resource'].rsplit('/', 1)[-1]:24s} {d['unit']:9s} "
                   "deck top - mesh at its end lines "
                   + (" / ".join(f"{e:+.2f}" for e in d["ends"]) or d["note"]))
    b = [d for d in decks if d["class"].startswith("B")]
    bad_b = [d for d in b if not d["note"] and min(abs(e) for e in d["ends"]) > tol_m]
    out.append(f"   (iii) road overpasses: {len(b)}, nearer end > {tol_m:g} m off: "
               f"{len(bad_b)} (bar 0; the far-end gap is #1138's, listed)"
               + ("   *** VIOLATED ***" if bad_b else ""))
    for d in sorted(b, key=lambda q: q["resource"]):
        e = d["ends"]
        out.append(f"      {d['resource'].rsplit('/', 1)[-1]:24s} ends "
                   + " / ".join(f"{x:+.2f}" for x in e)
                   + (f"  {d['note']}" if d["note"] else
                      f"  far-end gap {max(abs(x) for x in e):.2f} m (#1138)"))
    out.append(f"   (iv) lifted footed frames: {len(frames)}")
    for f in frames:
        out.append(f"      {f['unit']:9s} {f['members']} members, {f['rows']} rows: zero "
                   f"{f['zero']:.2f}, spread {f['spread']:.2f} m, {f['off']} rows > 0.3 m "
                   f"off it; the author's ground plane at {f['author_ground']:.2f}"
                   + ("" if f["mesh_at_anchor"] is None
                      else f" (mesh at the anchor {f['mesh_at_anchor']:.2f})"))
    return out
