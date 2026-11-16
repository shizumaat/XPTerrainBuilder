"""LIBRARY of ``tools/bridge_census.py --agp`` (#2090; spec
``docs/specs/2090-agp-group-groundside-spec.md`` gate G1): THE AGP GROUPS
as the pack stage reads them, on a ``v2_solve_replay.py --capture``
pickle — per group its members (ground point, distance to the apt.dat
airside, chain step, ``zero_pred``), its joins with their votes and the
runner-up's, the governor, the refused joins (V2), and (spec B1 / C1, when
the record carries them) the deck joins and the plates.  The author's own
patch (``<pack>/Patches/*.patch.osm``) altitudes at each ground point are
printed as a CHECK, never a level witness (F7, owner Q3 (a)).

Read-only; writes nothing but ``--jsonl``.
"""
from __future__ import annotations

import glob
import math
import os
import pickle
import time
import xml.etree.ElementTree as ET

__all__ = ["agp_rows", "author_altitudes", "print_agp", "ramp_rows", "print_ramps"]


def author_altitudes(pack_root: str) -> list[tuple[list, dict]]:
    """``[(ring [(lat, lon)], tags)]`` per closed way of the pack's own
    patch files carrying an ``altitude`` / ``altitude_low`` tag."""
    out = []
    for path in sorted(glob.glob(os.path.join(pack_root or "", "Patches", "*.osm"))):
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError):
            continue
        nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon")))
                 for n in root.iter("node")}
        for w in root.iter("way"):
            refs = [nd.get("ref") for nd in w.iter("nd")]
            tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
            if len(refs) < 4 or refs[0] != refs[-1] or not (
                    "altitude" in tags or "altitude_low" in tags):
                continue
            ring = [nodes[r] for r in refs if r in nodes]
            if len(ring) >= 4:
                out.append((ring, tags))
    return out


def _inside(ring, lat: float, lon: float) -> bool:
    inside = False
    for (a_la, a_lo), (b_la, b_lo) in zip(ring, ring[1:], strict=False):
        if (a_la > lat) != (b_la > lat):
            x = a_lo + (lat - a_la) * (b_lo - a_lo) / (b_la - a_la)
            if lon < x:
                inside = not inside
    return inside


def _altitude_at(ways, lat: float, lon: float) -> str:
    hits = [t.get("altitude") or f"{t.get('altitude_low')}..{t.get('altitude_high')}"
            for ring, t in ways if _inside(ring, lat, lon)]
    return ",".join(sorted(set(hits))) if hits else "-"


def _census(x) -> dict:
    """A deck join's / plate's census record (its own ``census``)."""
    fn = getattr(x, "census", None)
    return fn() if callable(fn) else dict(x)


def agp_rows(pkl: str, law) -> tuple[str, list[dict], list[dict], list[str], float]:
    """``(icao, group rows, refused joins, notes, seconds)`` of the pack
    stage's AGP read on the capture ``pkl``."""
    from auto_patch_v2.airport import frame_entry as _fe
    from auto_patch_v2.airport.agp_group import read_groups
    from auto_patch_v2.airport.obj8 import ResourceCache
    from auto_patch_v2.planar.basins import read_objects
    from auto_patch_v2.planar.deck_stack_attach import attach_deck_stacks
    from auto_patch_v2.planar.free_bridge import read_bridges
    with open(pkl, "rb") as fh:
        cap = pickle.load(fh)
    icao, airport = cap["icao"], cap["airport"]
    t0 = time.perf_counter()
    groups, refused, notes = read_groups(airport, law)
    took = time.perf_counter() - t0
    # the deck joins (spec B1) are read with the bridges, as the pack stage
    # reads them (``planar/free_bridge.read_bridges``)
    import dataclasses as _dc
    cache = ResourceCache(law.tables.structures.basin.min_solid_thickness_m, _fe.quantum(law))
    objs, _rep = read_objects(airport, law, cache)
    airport = attach_deck_stacks(_dc.replace(airport, agp_groups=groups), objs, cache, law)
    airport, _every, more = read_bridges(airport, objs, cache, law)
    groups = airport.agp_groups
    notes += [n for n in more if "deck join" in n]
    ways = author_altitudes(getattr(airport.pack, "pack_root", "") or "")
    rows = []
    for g in groups:
        rows.append({
            "icao": icao, "id": g.id, "governor": g.governor, "why": g.why,
            "dem_gov": g.dem_gov,
            "members": [{"row": m.row, "resource": m.resource, "ground": list(m.ground_ll),
                         "airside_m": None if not math.isfinite(m.airside_m) else m.airside_m,
                         "airside": m.row in g.airside, "step": m.step,
                         "zero_pred": g.zero_pred(m.row),
                         "author_altitude": _altitude_at(ways, *m.ground_ll)}
                        for m in g.members],
            "joins": [{"a": j.a, "b": j.b, "step": j.step, "votes": j.votes,
                       "rival": j.rival, "contact": list(j.contact_ll)} for j in g.joins],
            "deck_joins": [_census(d) for d in g.deck_joins],
            "plates": [_census(p) for p in g.plates]})
    rej = [{"icao": icao, "a": j.a, "b": j.b, "step": j.step, "votes": j.votes,
            "rival": j.rival} for j in refused]
    return icao, rows, rej, notes, took


def print_agp(icao: str, rows: list[dict], rej: list[dict], took: float) -> None:
    print(f"[{icao}] the pack stage's AGP read: {took:.2f} s, {len(rows)} group(s)")
    for g in rows:
        print(f"  {g['id']}: governor {g['governor'] or '-'}"
              + (f" DEM {g['dem_gov']:.2f}" if g["dem_gov"] is not None else "")
              + (f" — {g['why']}" if g["why"] else ""))
        for m in g["members"]:
            zp = "-" if m["zero_pred"] is None else f"{m['zero_pred']:.2f}"
            st = "-" if m["step"] is None else f"{m['step']:+.2f}"
            am = "-" if m["airside_m"] is None else f"{m['airside_m']:.1f}"
            print(f"    member {m['row']:>14} {m['resource'].rsplit('/', 1)[-1]:28} gp "
                  f"{m['ground'][0]:.6f},{m['ground'][1]:.6f} airside {am:>7} m"
                  f"{' AIRSIDE' if m['airside'] else ''} step {st:>7} zero_pred {zp:>8}"
                  f"  author patch altitude {m['author_altitude']}")
        for j in g["joins"]:
            print(f"    join {j['a']} + {j['b']}: step {j['step']:+.3f} on {j['votes']} "
                  f"pair(s) against {j['rival']} at {j['contact'][0]:.6f},{j['contact'][1]:.6f}")
        for d in g["deck_joins"]:
            print(f"    deck join {d}")
        for p in g["plates"]:
            print(f"    plate {p}")
    for j in rej:
        print(f"  REFUSED (V2) {j['a']} + {j['b']}: step {j['step']:+.3f} on {j['votes']} "
              f"pair(s) against {j['rival']}")


def ramp_rows(solved_pkl: str) -> tuple[str, list[dict]]:
    """``(icao, rows)`` THE GROUP-SEEDED RAMPS (#2090 amendment B′ G2-B′) on a
    ``v2_solve_replay.py --solved-out`` pickle: per route carrying a vertex
    of ``PlanarMap.road_ramp_group`` (a ramp a datum-group deck end or a
    plate seeds), its stations with the solved level, the published §37 (6)
    target and the floor, and the steepest solved grade between stations at
    least 2 m apart."""
    import numpy as np
    with open(solved_pkl, "rb") as fh:
        d = pickle.load(fh)
    pm, z, ap = d["pm"], np.asarray(d["z"], float), d["airport"]
    to_ll = ap.frame.transformers()[1]
    grp = getattr(pm, "road_ramp_group", None) or {}
    fr = getattr(pm, "road_route_frame", None) or {}
    tz = getattr(pm, "road_ramp_z", None) or {}
    by: dict = {}
    for v in grp:
        if v in fr:
            by.setdefault(fr[v][0], {}).setdefault(round(float(fr[v][1]), 1), []).append(v)
    rows = []
    for r, st in sorted(by.items()):
        ss = sorted(st)
        zs = [float(np.mean([z[v] for v in st[s_]])) for s_ in ss]
        worst, last = (0.0, ss[0], ss[0]), 0
        for i in range(1, len(ss)):
            if ss[i] - ss[last] >= 2.0:
                g = abs(zs[i] - zs[last]) / (ss[i] - ss[last])
                worst = max(worst, (g, ss[last], ss[i]))
                last = i
        v0 = st[ss[0]][0]
        la, lo = to_ll(*pm.vertices[v0].xy)
        rows.append({"route": int(r), "group": grp[v0][0], "at": [round(la, 7), round(lo, 7)],
                     "stations": [{"s": s_, "z": round(zz, 3),
                                   "target": round(float(tz.get(st[s_][0], float("nan"))), 3),
                                   "floor": round(float(grp[st[s_][0]][1]), 3)}
                                  for s_, zz in zip(ss, zs, strict=True)],
                     "steepest": round(worst[0], 4), "steepest_s": [worst[1], worst[2]]})
    return str(d.get("icao", "")), rows


def print_ramps(icao: str, rows: list[dict], bar: float = 0.055) -> None:
    """One line per group-seeded ramp route; its stations when over ``bar``."""
    print(f"[{icao}] group-seeded ramps: {len(rows)} route(s)")
    for r in rows:
        flag = " OVER" if r["steepest"] > bar else ""
        print(f"  route {r['route']} at {r['at'][0]:.6f},{r['at'][1]:.6f} {r['group']}: "
              f"{len(r['stations'])} stations, steepest {100 * r['steepest']:.2f} % at s "
              f"{r['steepest_s'][0]:.0f}-{r['steepest_s'][1]:.0f}{flag}")
        if flag:
            for s_ in r["stations"]:
                print(f"      s {s_['s']:7.1f} z {s_['z']:.3f} target {s_['target']:.3f} "
                      f"floor {s_['floor']:.3f}")
