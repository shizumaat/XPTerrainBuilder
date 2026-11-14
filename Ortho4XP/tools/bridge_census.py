#!/usr/bin/env python3
"""THE BRIDGE CENSUS (#2065; spec ``docs/specs/bridge-classifier-spec.md`` §1
"Gate", round R1) — one row per pack ``flag`` / ``signature`` deck in the
corpus's rebake plans: its class (``auto_patch_v2.airport.bridge_class``),
the witness values (``bridge_witness`` W1-W6) and the first witness it fails.

    venv/bin/python tools/bridge_census.py [--plan P.json ...] [--icao ICAO ...]
        [--frames docs/frames.jsonl] [--patches DATA/Patches] [--jsonl OUT]
        [--only-plans]

PLANS: the latest (by mtime) rebake plan per airport among every plan the
frames register (``docs/frames.jsonl`` ``path`` entries: a plan file, or a
directory holding ``*rebake*.json``), every ``<data repo>/Patches/*/*/
o4_v2_rebake_<ICAO>.json`` and each ``--plan`` named.  Read-only.

PER PLAN: the decks' plates and every frame body read from the pack's own
OBJ8 files (``authored_path``, else ``live_path``), placed in the airport's
metric frame (``model.frame.Frame``); the mapped ways from the tile OSM
feeds through the engine's reader (``airport.osm.load_feed``: no network,
a missing feed is empty; the tile's ``water`` / ``coastline`` feeds give W5
its water polygons and waterway lines); the pre-solve DEM through ``airport.dem.load_dem``
(W5 only; absent DEM = W5 reads ways only).  The readers' own outcomes —
deck stack (the graded sidecar's ``object_floors[].stack``), pack cut
(``authored_seats`` records carrying ``cut_ring``), airside hard deck
(``plate_kind == "deck"``), road overpass (``plate_kind == "overpass"``),
all-deck frame (``placement_family.frame_is_bridge``), graded
(``deck_datum_z``) — are read off the plan, never re-derived.  Object pads
are not read offline (W6 checks containment only).

Prints the free bridges by airport first, then every class count and the
per-deck witness cost; ``--jsonl`` writes every row.
"""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os  # noqa: E402
import sys as _o4sys

_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.abspath(__file__)),
                                      "harness"))
import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

import argparse  # noqa: E402
import collections  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import types  # noqa: E402

import numpy as np  # noqa: E402
from auto_patch_v2.airport import bridge_witness as BW  # noqa: E402
from auto_patch_v2.airport.bridge_class import DeckFacts, classify  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PLAN_ICAO = re.compile(r"(?:o4_v2_rebake_)?([A-Z0-9]{3,4})(?:~\d+)?(?:\.rebake)?\.json$")
_DECK = ("flag", "signature")
#: the round-2 class-B reading's plated kinds (``free_bridge_seat.PLATED_KINDS``
#: on lothhdeck2): a deck carrying one was never a round-2 mover
_PLATED = {"deck", "overpass", "edge", "walled", "split_level"}


# ── the plans ───────────────────────────────────────────────────────────

def _plan_files(frames: str, patches: str, extra: list[str]) -> dict[str, str]:
    """ICAO -> the latest plan (by mtime) among the registered ones."""
    cands: list[str] = list(extra)
    if frames and os.path.isfile(frames):
        for line in open(frames, encoding="utf-8"):
            p = (json.loads(line).get("path") or "") if line.strip() else ""
            if isinstance(p, str) and os.path.isdir(p):
                cands += glob.glob(os.path.join(p, "*rebake*.json"))
            elif isinstance(p, str) and os.path.isfile(p) and "rebake" in os.path.basename(p):
                cands.append(p)
    if patches:
        cands += glob.glob(os.path.join(patches, "*", "*", "o4_v2_rebake_*.json"))
    best: dict[str, str] = {}
    for p in cands:
        m = _PLAN_ICAO.search(os.path.basename(p))
        if not m or "result" in p or ".screen." in p or not os.path.isfile(p):
            continue
        if p in extra or m.group(1) not in best or (
                best[m.group(1)] not in extra
                and os.path.getmtime(p) > os.path.getmtime(best[m.group(1)])):
            best[m.group(1)] = p
    return best


def _is_deck(m: dict) -> bool:
    return (m.get("deck_kind") in _DECK and m.get("deck_top_y") is not None
            and len(m.get("deck_ring") or ()) >= 3)


def _stack_ids(plan_path: str, icao: str) -> set[str]:
    """Deck members of a deck stack, from the graded sidecar beside the plan."""
    out: set[str] = set()
    for g in glob.glob(os.path.join(os.path.dirname(plan_path), f"{icao}*.graded.json")):
        try:
            d = json.load(open(g, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for rec in d.get("object_floors") or ():
            st = rec.get("stack") or {}
            out.update(str(x.get("object")) for x in st.get("decks") or ())
    return out


def _cut_ids(plan: dict) -> set[str]:
    """Every placement id a pack-cut seat record names (``cut_deck_seat.CUT_RING``)."""
    from auto_patch_v2.airport.cut_deck_seat import CUT_RING
    out: set[str] = set()
    for r in plan.get("authored_seats") or ():
        if r.get(CUT_RING):
            out.add(str(r.get("id")))
            out.update(str(x) for x in r.get("members") or ())
    return out


# ── the airport's frame, ways and ground ───────────────────────────────

def _frame(icao: str, origin):
    from auto_patch_v2.model.frame import Frame
    fr = Frame(icao, (float(origin[0]), float(origin[1])), 9)
    return fr, fr.transformers()[0]


def _ways(osm_root: str, decks, to_xy) -> list:
    """Every mapped way of the tile feeds near the decks, in the frame."""
    from auto_patch_v2.airport import osm as _osm
    from auto_patch_v2.airport.load import _osm_id
    lats = [q[0] for _u, m in decks for q in m["deck_ring"]]
    lons = [q[1] for _u, m in decks for q in m["deck_ring"]]
    c = ((min(lats) + max(lats)) / 2.0, (min(lons) + max(lons)) / 2.0)
    r = max(max(lats) - min(lats), max(lons) - min(lons)) / 2.0 + 0.01
    out = []
    for feed in ("airports", "airport_small_roads", "big_roads"):
        for w in _osm.load_feed(osm_root, feed, c[0], c[1], r).ways:
            pts = tuple(to_xy(lo, la) for la, lo in w.points)
            out.append(types.SimpleNamespace(id=_osm_id(w.id), points=pts, tags=w.tags))
    return out


_WATER_TAGS = frozenset(("natural", "water", "waterway", "landuse"))


def _water(osm_root: str, decks, to_xy) -> tuple[list, list]:
    """``(water polygons, waterway / coastline lines as crossing ways)`` of
    the decks' tile, read through the engine's OSM reader (no network)."""
    from auto_patch_v2.airport import osm as _osm
    la, lo = decks[0][1]["deck_ring"][0]
    tl, tn = math.floor(la), math.floor(lo)
    polys, lines = [], []
    for feed in ("water", "coastline"):
        path = _osm.feed_path(osm_root, tl, tn, feed)
        if not os.path.isfile(path):
            continue
        nodes, ways, _rep = _osm.read_osm_file(path, "w:", _WATER_TAGS)
        for _wid, nds, tags in ways:
            pts = [to_xy(nodes[n][1], nodes[n][0]) for n in nds if n in nodes]
            if len(pts) < 2:
                continue
            if feed == "coastline" or ("waterway" in tags and pts[0] != pts[-1]):
                lines.append(types.SimpleNamespace(
                    id=-(len(lines) + 1), points=tuple(pts),
                    tags={"waterway": tags.get("waterway", "coastline")}))
            elif len(pts) >= 4 and pts[0] == pts[-1]:
                p = Polygon(pts)
                polys.append(p if p.is_valid else p.buffer(0))
    return polys, lines


def _ground(frame, elev_root: str, icao: str):
    from auto_patch_v2.airport.dem import load_dem
    try:
        dem = load_dem(frame, elev_root, icao)
    except (OSError, ValueError) as e:
        print(f"  {icao}: no DEM ({e}); W5 reads ways only")
        return None
    return lambda xs, ys: dem.z_many(np.asarray(xs, float), np.asarray(ys, float))


# ── one frame ───────────────────────────────────────────────────────────

class _Geoms:
    """The pack's OBJ8 files, parsed once per plan."""

    def __init__(self) -> None:
        self._g: dict[str, object] = {}

    def of(self, m: dict):
        from auto_patch_v2.airport.obj8 import parse_obj8
        for p in (m.get("authored_path"), m.get("live_path")):
            if p and os.path.isfile(p):
                if p not in self._g:
                    try:
                        self._g[p] = parse_obj8(p)
                    except (OSError, ValueError):
                        self._g[p] = None
                return self._g[p]
        return None


def _placed(g, m: dict, to_xy) -> np.ndarray:
    xy = to_xy(float(m["origin"][1]), float(m["origin"][0]))
    return BW.placed_faces(g.vertices[:, :3], g.solid, xy, float(m.get("heading_deg") or 0.0))


def _ring(m: dict, to_xy) -> Polygon:
    p = Polygon([to_xy(q[1], q[0]) for q in m["deck_ring"]])
    if not p.is_valid:
        p = p.buffer(0)
    if p.geom_type != "Polygon":
        p = max(getattr(p, "geoms", [p]), key=lambda g: g.area)
    return p


def _bodies(members, geoms: _Geoms, to_xy, cap: int = 4000) -> dict:
    """id -> plan vertices of each member's solid faces (strided to ``cap``)."""
    out = {}
    for m in members:
        g = geoms.of(m)
        if g is None or not len(g.solid):
            continue
        f = _placed(g, m, to_xy)[:, :, :2].reshape(-1, 2)
        f = np.unique(np.round(f, 2), axis=0)
        out[str(m["id"])] = f[:: max(1, len(f) // cap)]
    return out


def _frame_faces(members, geoms: _Geoms, to_xy, box) -> np.ndarray:
    parts = []
    for m in members:
        g = geoms.of(m)
        if g is not None and len(g.solid):
            f = _placed(g, m, to_xy)
            lo, hi = f[:, :, :2].min(axis=1), f[:, :, :2].max(axis=1)
            parts.append(f[(hi[:, 0] >= box[0]) & (lo[:, 0] <= box[2])
                           & (hi[:, 1] >= box[1]) & (lo[:, 1] <= box[3])])
    return np.concatenate(parts) if parts else np.zeros((0, 3, 3))


def _unit_rows(u: dict, decks: list, ctx) -> tuple[list[dict], float]:
    """Every deck row of one frame, and the witness seconds it took."""
    from auto_patch_v2.airport.placement_family import frame_is_bridge
    law, to_xy, geoms = ctx["law"], ctx["to_xy"], ctx["geoms"]
    normal = float(law.tables.structures.bridge.deck_plate_normal_y_min)
    rings = {str(m["id"]): _ring(m, to_xy) for m in decks}
    live = any(not isinstance(BW.route_of(r, ctx["ways"], law), str) for r in rings.values())
    plates = {}
    for m in decks:
        g = geoms.of(m)
        up = BW.up_faces(_placed(g, m, to_xy), normal) if g is not None else np.zeros((0, 3, 3))
        plates[str(m["id"])] = (rings[str(m["id"])], up, m["deck_kind"])
    box = tuple(np.add(_bounds(rings), (-2.0, -2.0, 2.0, 2.0)))
    faces = _frame_faces(u["members"], geoms, to_xy, box) if live else np.zeros((0, 3, 3))
    bodies = _bodies(u["members"], geoms, to_xy) if live else {}
    t0 = time.perf_counter()
    near = [p for p in ctx["water"] if p.bounds[0] <= box[2] and p.bounds[2] >= box[0]
            and p.bounds[1] <= box[3] and p.bounds[3] >= box[1]]
    wit = BW.frame_witness(plates, faces, bodies, ctx["ways"], law, ctx["ground"], near)
    dt = time.perf_counter() - t0
    unit = types.SimpleNamespace(members=[types.SimpleNamespace(**x) for x in u["members"]])
    ids = {str(x["id"]) for x in u["members"]}
    rows = []
    for m in decks:
        w = wit[str(m["id"])]
        f = DeckFacts(in_stack=str(m["id"]) in ctx["stacks"], frame_cut=bool(ids & ctx["cuts"]),
                      airside=m.get("plate_kind") == "deck",
                      overpass=m.get("plate_kind") == "overpass",
                      all_deck_frame=frame_is_bridge(unit),
                      graded=m.get("deck_datum_z") is not None, witness=w)
        rows.append(_row(ctx["icao"], u, m, classify(f), w))
    return rows, dt


def _bounds(rings: dict) -> tuple:
    b = np.array([r.bounds for r in rings.values()])
    return (b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max())


def _row(icao: str, u: dict, m: dict, v, w) -> dict:
    r = w.route
    alld = all(x.get("deck_kind") in _DECK for x in u["members"])
    return {"icao": icao, "unit": u["id"], "id": m["id"],
            "resource": str(m.get("resource", "")).rsplit("/", 1)[-1],
            "deck_kind": m.get("deck_kind"), "plate_kind": m.get("plate_kind") or "",
            "members": len(u["members"]), "class": v.cls, "reason": v.reason,
            "failed": w.failed, "frame_failed": w.frame_failed, "joined": w.joined,
            "bridge_m": round(r.bridge_m, 1) if r else None,
            "cover": round(r.cover, 2) if r else None,
            "length_m": round(r.s_b - r.s_a, 1) if r else None,
            "ways": list(r.ways)[:8] if r else [],
            "surface_share": round(w.surface_share, 2), "roof_share": round(w.roof_share, 2),
            "span": w.span, "width_m": round(w.width_m, 1),
            "layer_ends": ([round(w.layer[0], 2), round(w.layer[-1], 2)] if w.layer else []),
            "r2_candidate": (not alld and m.get("deck_datum_z") is None
                             and (m.get("plate_kind") or "") not in _PLATED)}


def census_plan(path: str, icao: str, law, osm_root: str, elev_root: str
                ) -> tuple[list[dict], list[float]]:
    """Every deck row of one plan, and the witness seconds per deck."""
    plan = json.load(open(path, encoding="utf-8"))
    for u in plan.get("units") or ():
        for m in u.get("members") or ():
            # a plan before version 12 carries no member origin: its unit is
            # one anchor spelling (``model/rebake``), the placement's
            m["origin"] = m.get("origin") or u.get("anchor")
    units = [(u, [m for m in u.get("members") or () if _is_deck(m)])
             for u in plan.get("units") or ()]
    units = [(u, ds) for u, ds in units if ds]
    if not units:
        return [], []
    frame, to_xy = _frame(icao, units[0][1][0]["deck_ring"][0])
    decks = [(u, m) for u, ds in units for m in ds]
    water, streams = _water(osm_root, decks, to_xy)
    ctx = {"icao": icao, "law": law, "to_xy": to_xy, "geoms": _Geoms(),
           "ways": _ways(osm_root, decks, to_xy) + streams, "water": water,
           "ground": _ground(frame, elev_root, icao),
           "stacks": _stack_ids(path, icao), "cuts": _cut_ids(plan)}
    rows, cost = [], []
    for u, ds in units:
        got, dt = _unit_rows(u, ds, ctx)
        rows += got
        cost += [dt / len(ds)] * len(ds)
    return rows, cost


# ── report ──────────────────────────────────────────────────────────────

def _print(rows: list[dict], cost: list[float]) -> None:
    free = [r for r in rows if r["class"] == "free_bridge"]
    print(f"\n== FREE BRIDGES (F): {len(free)} decks at "
          f"{len({r['icao'] for r in free})} airports")
    for r in sorted(free, key=lambda r: (r["icao"], r["unit"], r["resource"])):
        print(f"  {r['icao']} {r['unit']:10} {r['resource'][:40]:40} {r['deck_kind'][:4]} "
              f"bridge {r['bridge_m']} m cover {r['cover']} len {r['length_m']} "
              f"surf {r['surface_share']} roof {r['roof_share']} {r['reason']}")
    att = [r for r in rows if r["class"] == "attached_bridge"]
    print(f"\n== ATTACHED BRIDGES (W1-W5 hold, W6 fails): {len(att)}")
    for r in sorted(att, key=lambda r: (r["icao"], r["unit"])):
        print(f"  {r['icao']} {r['unit']:10} {r['resource'][:40]:40} {r['frame_failed']}")
    print("\n== CLASSES")
    for k, n in collections.Counter(r["class"] for r in rows).most_common():
        print(f"  {k:18} {n}")
    print("\n== FIRST FAILED WITNESS (not_a_bridge)")
    for k, n in collections.Counter(r["failed"].split(":")[0] for r in rows
                                    if r["class"] == "not_a_bridge").most_common():
        print(f"  {k:18} {n}")
    if cost:
        print(f"\n== witness cost per deck: median {1e3 * float(np.median(cost)):.1f} ms, "
              f"max {1e3 * max(cost):.0f} ms over {len(cost)} decks")


def main(argv=None) -> int:
    from shared_repo_guard import DATA_REPO
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan", nargs="*", default=[], help="extra plans (win their airport)")
    ap.add_argument("--icao", nargs="*", default=[])
    ap.add_argument("--frames", default=os.path.join(REPO, "docs", "frames.jsonl"))
    ap.add_argument("--patches", default=str(DATA_REPO / "Patches"))
    ap.add_argument("--osm-root", default=str(DATA_REPO / "OSM_data"))
    ap.add_argument("--elevation-root", default=str(DATA_REPO / "Elevation_data"))
    ap.add_argument("--jsonl", default="")
    ap.add_argument("--only-plans", action="store_true", help="list the plans and stop")
    a = ap.parse_args(argv)
    from auto_patch_v2.law import Law
    law = Law.load()
    plans = _plan_files(a.frames, a.patches, [os.path.abspath(p) for p in a.plan])
    if a.icao:
        plans = {k: v for k, v in plans.items() if k in set(a.icao)}
    print(f"{len(plans)} plans (latest per airport)")
    if a.only_plans:
        for k, v in sorted(plans.items()):
            print(f"  {k} {v}")
        return 0
    rows, cost = [], []
    out = open(a.jsonl, "w", encoding="utf-8") if a.jsonl else None
    for icao, p in sorted(plans.items()):
        try:
            got, c = census_plan(p, icao, law, a.osm_root, a.elevation_root)
        except (OSError, ValueError, KeyError) as e:
            print(f"  {icao}: unreadable plan {p} ({e})")
            continue
        if got:
            print(f"  {icao}: {len(got)} decks, {sum(r['class'] == 'free_bridge' for r in got)} F"
                  f"  ({p})", flush=True)
        for r in got:
            r["plan"] = p
            if out is not None:
                out.write(json.dumps(r) + "\n")
        rows += got
        cost += c
    if out is not None:
        out.close()
    _print(rows, cost)
    return 0


if __name__ == "__main__":
    sys.exit(main())
