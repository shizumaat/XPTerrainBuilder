"""THE DRAWN GATE (#1903): the harness's verdict on what X-Plane DRAWS.

Lane rounds on tunnels, decks and levels passed their bars and looked
unchanged in the sim (LOWS, LGAV, KIAH, KLAX) because every bar read an
engine record -- the replay's solver surface, the census's patch, the
pre-write placement plan -- and none read the products X-Plane loads.
This gate reads only those products, in three layers, and a lane's PASS
means all three passed:

1. MESH -- WHICH ground is drawn.  The tile's base-mesh DSF (a harness
   build's own ``build_dir`` DSF; the owner's products: the load order's,
   ``O4_Mesh_Order.drawn_mesh_dsf``).  FAIL when a pack above our tile in
   ``scenery_packs.ini`` draws its own base mesh there (``hidden by``,
   ``O4_Mesh_Order.tile_mesh_order``: nothing we build is seen) or when
   the DSF is older than the patch (the drawn mesh cannot carry it).
2. PATCH -> DRAWN -- does the drawn mesh carry the patch?  Every node of
   the airport's patch with an ``alt_abs`` inside the tile, sampled on the
   drawn mesh: a node of a pavement role (``law.tables.pavement_roles``)
   off by more than the pavement bar (0.05 m), any other node off by more
   than the ground bar (0.5 m), after ``XY_TOL_M`` of horizontal slack
   (the drawn heights within 0.15 m bound the node: a near-vertical step
   read at a fixed (x, y) is off by metres no eye sees) -- the owner's
   visibility bars, the ones
   ``tools/drawn_site.py`` judges by -- is a place where the sim shows
   something other than the patch: the class a census of the patch can
   never see.  Failing nodes within ``CLUSTER_M`` fold into one site.
3. OBJECTS -- ``tools/drawn_check.py``'s claimed cut / deck / trench /
   split-level sites, each written row placed the way X-Plane places it
   on the same drawn mesh.  Measured only when the written pack IS this
   product's (the owner's install, or a harness build's ``--pack-copy``);
   a harness build without a copy stood its pack writes down, so the pack
   on disk is the owner's old one and the layer is NOT MEASURED.

4. ROADS (#2072) -- with ``--site``: every mapped vehicle road within a
   site's radius sampled on the drawn mesh each metre; a step between two
   consecutive samples over ``--road-step`` (default 0.5 m, the ground bar)
   FAILs the site (``tools/harness/drawn_roads.py``).

Verdict: FAIL when any layer fails; INCOMPLETE when nothing failed but a
layer was not measured (a patch-only build has no drawn product; a tile
build without ``--pack-copy`` has no written objects); PASS otherwise.
Exit 0 only on PASS.  A round is judged where it worked and against its
control: ``--site NAME=LAT,LON[,R]`` (repeat; R 150 m) judges only the
sites within R (the rest are counted as ``elsewhere``), and ``--against
BASE.json`` (the control's ``--json``) fails any site new or worse by more
than ``MOVED_M`` -- a patch node by id, an object site by name.

``build_airport.py --tile`` runs it on its own products after every tile
build (``<tag>.drawn.json``, ``result["drawn_gate"]``, a ``DRAWN`` line in
the progress log); ``--no-drawn-gate`` skips it.

Usage (from Ortho4XP/):
    venv/bin/python tools/harness/drawn_gate.py LGAV --tag T [--out DIR]
    venv/bin/python tools/harness/drawn_gate.py LGAV --tile +37+023 \\
        [--patches ROOT] [--custom-scenery DIR]
    ... [--json OUT] [--top N]
"""
from __future__ import annotations

import argparse
import copy
import glob
import json
import math
import os
import sys
import time
import xml.etree.ElementTree as ET

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(os.path.dirname(_TOOLS), "src"), _TOOLS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Twin: ``tests/test_console_encoding.py``.
import O4_Console_Encoding as _o4console  # noqa: E402, I001

_o4console.configure_console_streams()

import drawn_check as DC  # noqa: E402
from drawn_site import GROUND_BAR_M, PAVEMENT_BAR_M  # noqa: E402

__all__ = ["CLUSTER_M", "XY_TOL_M", "SITE_RADIUS_M", "MOVED_M", "patch_nodes",
           "mesh_follows_patch", "mesh_layer", "gate", "judge", "after_build",
           "summary_line", "print_gate", "main"]

#: Failing patch nodes within this distance are one site.
CLUSTER_M = 10.0
#: The horizontal slack of a patch node's reading: the drawn heights within
#: this radius bound it.  The mesh carries a patch node a few cm off its
#: (x, y) (measured 0.01-0.07 m, LOWS / LGAV .mesh), and on a near-vertical
#: step (LOWS east: 469.20 -> 435.11 m over 0.49 m) a fixed-(x, y) read is
#: off by metres that no eye sees.
XY_TOL_M = 0.15
#: A ``--site`` judges what lies within this radius unless it names one.
SITE_RADIUS_M = 150.0
#: ``--against``: a site worse than its control by more than this moved.
MOVED_M = 0.05


# -- layer 2: does the drawn mesh carry the patch? -------------------------

def patch_nodes(patch_path):
    """``[(node_id, lon, lat, alt_abs, roles)]`` of every patch node with an
    ``alt_abs``; ``roles`` is the ``role`` (else ``o4_feature``) of each way
    through it, ``("(free)",)`` for a node on no way."""
    nodes, roles = {}, {}
    for _ev, el in ET.iterparse(patch_path):
        if el.tag == "node":
            alt = [t.get("v") for t in el.findall("tag") if t.get("k") == "alt_abs"]
            if alt:
                nodes[el.get("id")] = (float(el.get("lon")), float(el.get("lat")),
                                       float(alt[0]))
        elif el.tag == "way":
            tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
            role = tags.get("role") or tags.get("o4_feature") or "?"
            for nd in el.findall("nd"):
                roles.setdefault(nd.get("ref"), set()).add(role)
            el.clear()
    return [(nid, x, y, z, tuple(sorted(roles.get(nid, ()))) or ("(free)",))
            for nid, (x, y, z) in nodes.items()]


def _cluster(rows):
    """Greedy fold of failing node rows (worst first) into sites."""
    sites = []
    for r in sorted(rows, key=lambda r: -abs(r["delta"])):
        kx = DC.M_PER_DEG * math.cos(math.radians(r["lat"]))
        for s in sites:
            if math.hypot((s["lon"] - r["lon"]) * kx,
                          (s["lat"] - r["lat"]) * DC.M_PER_DEG) <= CLUSTER_M:
                s["nodes"] += 1
                s["roles"] = sorted(set(s["roles"]) | set(r["roles"]))
                break
        else:
            sites.append(dict(r, nodes=1, roles=list(r["roles"])))
    return sites


def _ring(sample, x, y, n=8):
    """Drawn heights on a circle of ``XY_TOL_M`` around (x, y)."""
    kx = DC.M_PER_DEG * math.cos(math.radians(y))
    out = []
    for k in range(n):
        a = 2.0 * math.pi * k / n
        z = sample(x + XY_TOL_M * math.cos(a) / kx, y + XY_TOL_M * math.sin(a) / DC.M_PER_DEG)
        if not math.isnan(z):
            out.append(z)
    return out


def _off_by(z, at, ring):
    """How far ``z`` lies outside the drawn heights near it (signed: drawn
    minus patch); 0 when the mesh passes through ``z`` within ``XY_TOL_M``."""
    lo, hi = min([at] + ring), max([at] + ring)
    return 0.0 if lo <= z <= hi else (lo - z if z < lo else hi - z)


def mesh_follows_patch(nodes, sample, tile_ll, pavement,
                       pavement_bar=PAVEMENT_BAR_M, ground_bar=GROUND_BAR_M):
    """Layer 2 over ``nodes`` (:func:`patch_nodes`) inside the tile
    ``tile_ll`` = (lat, lon); ``sample(lon, lat)`` is the drawn mesh height
    (nan off the mesh); ``pavement`` the pavement role names."""
    lat0, lon0 = tile_ll
    by_role, over, off_mesh, n = {}, [], 0, 0
    for nid, x, y, z, roles in nodes:
        if not (lat0 <= y < lat0 + 1 and lon0 <= x < lon0 + 1):
            continue
        m = sample(x, y)
        if math.isnan(m):
            off_mesh += 1
            continue
        n += 1
        paved = any(r in pavement for r in roles)
        bar = pavement_bar if paved else ground_bar
        d = _off_by(z, m, _ring(sample, x, y))
        key = ("pavement " if paved else "ground ") + "+".join(roles)
        st = by_role.setdefault(key, {"nodes": 0, "over_bar": 0, "worst": 0.0})
        st["nodes"] += 1
        if abs(d) > abs(st["worst"]):
            st["worst"] = round(d, 2)
        if abs(d) > bar:
            st["over_bar"] += 1
            over.append({"node": nid, "lat": round(y, 6), "lon": round(x, 6),
                         "patch": round(z, 2), "drawn": round(m, 2),
                         "delta": round(d, 2), "bar": bar, "roles": roles})
    return {"nodes": n, "off_mesh": off_mesh, "over_bar": len(over),
            "pavement_bar_m": pavement_bar, "ground_bar_m": ground_bar,
            "by_role": by_role, "sites": _cluster(over),
            "verdict": "FAIL" if over else "PASS" if n else "NOT MEASURED"}


# -- layer 1: which mesh is drawn ------------------------------------------

def mesh_layer(dsfs, patch_path, hidden_by):
    """Layer 1: the drawn DSF(s), a pack hiding our tile, a stale DSF."""
    fails = [f"hidden by {name}: its base mesh is drawn on this tile, ours is not"
             for name in hidden_by]
    patch_t = os.path.getmtime(patch_path)
    fails += [f"stale: {d} is older than the patch (the drawn mesh cannot carry it)"
              for d in dsfs if os.path.getmtime(d) < patch_t]
    verdict = "FAIL" if fails else "PASS" if dsfs else "NOT MEASURED"
    return {"dsfs": list(dsfs), "hidden_by": list(hidden_by), "fails": fails,
            "verdict": verdict}


# -- the products ----------------------------------------------------------

def _custom_scenery(explicit):
    if explicit:
        return explicit
    import O4_Config_Utils  # noqa: F401
    from auto_patch_v2.planar.__main__ import _cfg_value
    return (_cfg_value("custom_scenery_dir")
            or os.path.expanduser("~/X-Plane 12/Custom Scenery"))


def _products(args):
    """(patch path, tile ``+LL+LLL``, drawn DSF list, hidden_by, incomplete)."""
    import O4_Mesh_Order
    if args.tag:
        res = json.load(open(os.path.join(args.out, f"{args.tag}.result.json"),
                             encoding="utf-8"))
        if not res.get("build_dir"):
            raise SystemExit("NOT MEASURED: a patch-only build has no drawn "
                             "product -- rebuild with --tile")
        patch_dir, build_dir = res["patch_dir"], res["build_dir"]
        tile = os.path.basename(patch_dir)
        dsfs = sorted(glob.glob(os.path.join(build_dir, "Earth nav data", "*",
                                             f"{tile}.dsf")))
    else:
        tile, build_dir = args.tile, ""
        lat, lon = int(tile[:3]), int(tile[3:])
        patch_dir = os.path.join(
            args.patches, f"{lat // 10 * 10:+03d}{lon // 10 * 10:+04d}", tile)
        drawn = O4_Mesh_Order.drawn_mesh_dsf(args.custom_scenery, lat, lon)
        dsfs = [drawn] if drawn else []
    lat, lon = int(tile[:3]), int(tile[3:])
    order = O4_Mesh_Order.tile_mesh_order(args.custom_scenery, lat, lon,
                                          build_dir=build_dir)
    incomplete = [] if order["checked"] else [
        f"our tile is not in the load order of {args.custom_scenery}: whether "
        f"a pack above it would hide it is not known (today X-Plane draws "
        f"{O4_Mesh_Order.drawn_mesh_dsf(args.custom_scenery, lat, lon) or 'nothing'})"]
    patch = os.path.join(patch_dir, f"{args.icao}_auto.patch.osm")
    if not os.path.isfile(patch):
        raise SystemExit(f"NOT MEASURED: no patch {patch}")
    return patch, tile, dsfs, order["hidden_by"], incomplete


def gate(args):
    """The three layers and the verdict for ``args`` (see :func:`main`)."""
    t0 = time.time()
    args.custom_scenery = _custom_scenery(getattr(args, "custom_scenery", None))
    patch, tile, dsfs, hidden, incomplete = _products(args)
    rep = {"icao": args.icao, "tile": tile, "patch": patch,
           "mesh": mesh_layer(dsfs, patch, hidden), "incomplete": incomplete}
    if not dsfs:
        rep["patch_to_drawn"] = {"verdict": "NOT MEASURED"}
        rep["objects"] = {"verdict": "NOT MEASURED", "why": "no drawn DSF"}
        return _verdict(rep, t0)
    sampler = DC.drawn_mesh([DC.stream_dsf(d) for d in dsfs],
                            DC.patch_bbox(patch, 0.012))
    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import pavement_roles
    rep["patch_to_drawn"] = mesh_follows_patch(
        patch_nodes(patch), lambda x, y: DC.mesh_z(sampler, x, y),
        (int(tile[:3]), int(tile[3:])), set(pavement_roles(Law.for_airport(args.icao))))
    rep["objects"] = _objects(args, sampler, dsfs)
    sites = [parse_site(t) for t in getattr(args, "site", None) or ()]
    if sites:
        import O4_File_Names as FNAMES
        from drawn_roads import ROAD_STEP_M, road_layer
        step = getattr(args, "road_step", None)
        rep["roads"] = road_layer(sites, lambda x, y: DC.mesh_z(sampler, x, y),
                                  FNAMES.OSM_dir, ROAD_STEP_M if step is None else step)
    return _verdict(rep, t0)


def _objects(args, sampler, dsfs):
    """Layer 3 through ``drawn_check.run`` on the same sampler."""
    ns = argparse.Namespace(
        icao=args.icao, tile=getattr(args, "tile", None), tag=args.tag,
        out=getattr(args, "out", None), patches=getattr(args, "patches", None),
        radius=15.0, tol=0.3, margin=0.012, plan=None, mesh=None,
        sampler=sampler, sampler_dsfs=dsfs)
    try:
        rep = DC.run(ns)
    except SystemExit as exc:
        return {"verdict": "NOT MEASURED", "why": str(exc)}
    if not rep.get("pack_is_build_product", True):
        return {"verdict": "NOT MEASURED", "pack_root": rep["pack_root"],
                "why": "no --pack-copy: the pack on disk is the owner's install "
                       "as last written, not this build's objects"}
    sites = rep["sites"]
    failed = sum(s.get("verdict") == "FAIL" for s in sites)
    claimed = sum(s.get("verdict") in ("PASS", "FAIL") for s in sites)
    out = {"pack_root": rep["pack_root"], "sites": sites, "claimed": claimed,
           "failed": failed, "verdict": "FAIL" if failed else "PASS"}
    unclaimed = sum(s.get("role") == "UNCLAIMED" for s in sites)
    elsewhere = sorted({c["claim_id"] for c in rep["claims"] if not c["resource"]})
    if not claimed and (unclaimed or elsewhere):
        # a vacuous PASS is not a pass: cut sites with no object read
        # (a claim on a tile this build did not write -- LOWS +47+013's
        # mouths are claimed by +47+012's entrance object)
        out["verdict"] = "NOT MEASURED"
        out["why"] = (f"no claimed object read at {unclaimed} cut site(s)"
                      + (f"; {len(elsewhere)} claim(s) resolve to no written "
                         f"row here (a tile this build did not write?)"
                         if elsewhere else ""))
    return out


def _verdict(rep, t0):
    rep["seconds"] = round(time.time() - t0, 1)
    return judge(rep)


# -- judging a round: its sites, its control -------------------------------

def _near(row, sites):
    for _name, lat, lon, r in sites:
        kx = DC.M_PER_DEG * math.cos(math.radians(lat))
        if math.hypot((row["lon"] - lon) * kx, (row["lat"] - lat) * DC.M_PER_DEG) <= r:
            return True
    return False


def _moved(rep, base):
    """Sites new or worse than the control ``base`` (a gate ``--json``)."""
    out = []
    was = {s["node"]: s for s in base.get("patch_to_drawn", {}).get("sites", [])}
    for s in rep.get("patch_to_drawn", {}).get("sites", []):
        b = was.get(s["node"])
        if b is None or abs(s["delta"]) > abs(b["delta"]) + MOVED_M:
            out.append(f"patch->drawn node {s['node']} @{s['lat']},{s['lon']}: "
                       f"{'new' if b is None else b['delta']} -> {s['delta']:+.2f}")
    was = {r["site"]: r for r in base.get("roads", {}).get("sites", [])}
    for r in rep.get("roads", {}).get("sites", []):
        b = was.get(r["site"])
        if r.get("verdict") == "FAIL" and (b is None or b.get("max_step_m") is None or
                                           r["max_step_m"] > b["max_step_m"] + MOVED_M):
            out.append(f"roads {r['site']}: {'new' if b is None else b.get('max_step_m')} "
                       f"-> {r['max_step_m']:.2f} m step")
    was = {r["site"]: r for r in base.get("objects", {}).get("sites", [])}
    for r in rep.get("objects", {}).get("sites", []):
        if r.get("verdict") != "FAIL":
            continue
        b = was.get(r["site"])
        if b is None or b.get("verdict") != "FAIL":
            out.append(f"objects {r['site']}: {b.get('verdict') if b else 'new'} -> FAIL")
        elif (r.get("delta") is not None and b.get("delta") is not None
              and abs(r["delta"]) > abs(b["delta"]) + MOVED_M):
            out.append(f"objects {r['site']}: FAIL {b['delta']:+.2f} -> {r['delta']:+.2f}")
    return out


def judge(rep, sites=(), base=None):
    """Narrow ``rep``'s verdict to ``sites`` (``(name, lat, lon, r)``) and
    fail anything that moved against ``base``; records what it judged."""
    if sites:
        for layer in ("patch_to_drawn", "objects"):
            rows = rep.get(layer, {}).get("sites")
            if rows is None or rep[layer]["verdict"] == "NOT MEASURED":
                continue
            kept = [r for r in rows if _near(r, sites)]
            rep[layer]["elsewhere"] = len(rows) - len(kept)
            rep[layer]["sites"] = kept
            bad = [r for r in kept if layer == "patch_to_drawn" or r.get("verdict") == "FAIL"]
            if layer == "objects":
                rep[layer]["failed"] = len(bad)
                rep[layer]["claimed"] = sum(r.get("verdict") in ("PASS", "FAIL") for r in kept)
            else:
                rep[layer]["over_bar"] = sum(r["nodes"] for r in kept)
            rep[layer]["verdict"] = "FAIL" if bad else "PASS"
        rep["judged_sites"] = [list(s) for s in sites]
    if base is not None:
        rep["moved"] = _moved(rep, base)
    layers = [rep["mesh"]["verdict"], rep["patch_to_drawn"]["verdict"],
              rep["objects"]["verdict"]] + ([rep["roads"]["verdict"]] if "roads" in rep else [])
    rep["verdict"] = ("FAIL" if "FAIL" in layers or rep.get("moved") else
                      "INCOMPLETE" if "NOT MEASURED" in layers or rep["incomplete"]
                      else "PASS")
    return rep


def parse_site(text):
    """``NAME=LAT,LON[,R]`` -> ``(name, lat, lon, r)``."""
    name, _, rest = text.rpartition("=")
    parts = [float(v) for v in rest.split(",")]
    if len(parts) not in (2, 3):
        raise SystemExit(f"--site {text!r}: want NAME=LAT,LON[,R]")
    return (name or rest, parts[0], parts[1],
            parts[2] if len(parts) == 3 else SITE_RADIUS_M)


# -- reporting -------------------------------------------------------------

def summary_line(rep):
    """One line: the verdict and each layer's count."""
    p2d, obj = rep.get("patch_to_drawn", {}), rep.get("objects", {})
    tail = (f" ({obj['why']})" if obj.get("why") else
            f" ({obj['failed']} of {obj['claimed']} claimed sites FAIL)" if "failed" in obj
            else "")
    return (f"DRAWN {rep['verdict']} {rep['icao']} {rep['tile']}: mesh "
            f"{rep['mesh']['verdict']}; patch->drawn {p2d.get('verdict')} "
            f"({p2d.get('over_bar', '-')} of {p2d.get('nodes', '-')} nodes over the "
            f"bars, {len(p2d.get('sites', []))} sites); objects {obj.get('verdict')}"
            + tail + (f"; roads {rep['roads']['verdict']} ({rep['roads']['failed']} "
                      f"site(s) over {rep['roads']['bar_m']} m)" if rep.get("roads") else ""))


def print_gate(rep, top=20):
    m = rep["mesh"]
    print(f"DRAWN GATE {rep['icao']} {rep['tile']}  patch {rep['patch']}")
    print(f"  mesh {m['verdict']}: {', '.join(m['dsfs']) or 'no drawn DSF'}")
    for f in m["fails"] + rep["incomplete"]:
        print(f"     {f}")
    p2d = rep["patch_to_drawn"]
    if "sites" in p2d:
        print(f"  patch->drawn {p2d['verdict']}: {p2d['over_bar']} of {p2d['nodes']} "
              f"nodes over the bars (pavement {p2d['pavement_bar_m']} m, ground "
              f"{p2d['ground_bar_m']} m), {len(p2d['sites'])} sites")
        for s in p2d["sites"][:top]:
            print(f"     {s['delta']:+7.2f} @{s['lat']},{s['lon']} node {s['node']} "
                  f"patch {s['patch']:.2f} drawn {s['drawn']:.2f} ({s['nodes']} "
                  f"nodes; {'+'.join(s['roles'])})")
    obj = rep["objects"]
    print(f"  objects {obj['verdict']}: " + (obj["why"] if obj.get("why") else
          f"{obj['failed']} of {obj['claimed']} claimed sites FAIL"))
    for s in [s for s in obj.get("sites", []) if s.get("verdict") == "FAIL"][:top]:
        print(f"     FAIL {s['site']} @{s['lat']},{s['lon']}: {'; '.join(s['fails'])}")
    roads = rep.get("roads")
    if roads:
        print(f"  roads {roads['verdict']}: {roads['failed']} site(s) over a "
              f"{roads['bar_m']} m step between {roads['step_m']} m samples")
        for r in roads["sites"]:
            print(f"     {r['verdict']} {r['site']}: {r['roads']} road run(s), max step "
                  f"{r.get('max_step_m', '-')} m" + (f" @{r['lat']},{r['lon']} way {r['way']} "
                                                    f"({r['highway']}) drawn {r['drawn']}"
                                                    if r.get("lat") is not None else ""))
    if rep.get("judged_sites"):
        where = ", ".join(f"{n} {r:.0f} m" for n, _a, _o, r in rep["judged_sites"])
        print(f"  judged within {where}"
              f" (elsewhere: patch->drawn {p2d.get('elsewhere', 0)}, objects "
              f"{obj.get('elsewhere', 0)} sites, not judged)")
    for m in rep.get("moved", []):
        print(f"     MOVED {m}")
    print(summary_line(rep) + f"  [{rep['seconds']} s]")


# -- the harness hook ------------------------------------------------------

def after_build(icao, tag, out_dir, custom_scenery=None, prog=None):
    """``build_airport.py --tile``'s closing gate on its own products:
    writes ``<out>/<tag>.drawn.json`` and returns the record for
    ``result["drawn_gate"]``.  Never raises: an error is the record."""
    ns = argparse.Namespace(icao=icao, tag=tag, out=str(out_dir), tile=None,
                            patches=None, custom_scenery=custom_scenery)
    path = os.path.join(str(out_dir), f"{tag}.drawn.json")
    try:
        rep = gate(ns)
        line = summary_line(rep)
    except SystemExit as exc:
        rep = {"icao": icao, "verdict": "INCOMPLETE", "error": str(exc)}
        line = f"DRAWN INCOMPLETE {icao}: {exc}"
    except Exception as exc:  # noqa: BLE001 -- the build stands; the record says why
        rep = {"icao": icao, "verdict": "INCOMPLETE", "error": repr(exc)}
        line = f"DRAWN INCOMPLETE {icao}: the gate raised {exc!r}"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rep, fh, indent=1, default=str)
    if prog is not None:
        prog.note(line)
    return {"verdict": rep["verdict"], "json": path, "line": line}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("icao")
    ap.add_argument("--tag", help="a harness build: <out>/<tag>.result.json")
    ap.add_argument("--out", default="/tmp/harness", help="harness --out dir")
    ap.add_argument("--tile", help="+LL+LLL: the owner's installed products")
    ap.add_argument("--patches", default=None,
                    help="Patches root for --tile (default: FNAMES.Patch_dir)")
    ap.add_argument("--custom-scenery", default=None,
                    help="X-Plane Custom Scenery (default: the cfg's custom_scenery_dir)")
    ap.add_argument("--site", action="append", default=[], metavar="NAME=LAT,LON[,R]",
                    help=f"judge only within R (default {SITE_RADIUS_M:.0f} m) of it; repeat")
    ap.add_argument("--road-step", type=float, default=None, metavar="M",
                    help="the roads layer's bar: FAIL a --site whose mapped roads step "
                         "more than M between 1 m drawn samples (default 0.5)")
    ap.add_argument("--against", default=None, metavar="BASE.json",
                    help="the control's --json: fail any site new or worse")
    ap.add_argument("--json", default=None, help="write the full report here")
    ap.add_argument("--top", type=int, default=20, help="sites printed per layer")
    args = ap.parse_args(argv)
    if bool(args.tag) == bool(args.tile):
        ap.error("exactly one of --tag or --tile")
    if args.tile and args.patches is None:
        import O4_File_Names as FNAMES
        args.patches = FNAMES.Patch_dir
    full = gate(args)
    base = json.load(open(args.against, encoding="utf-8")) if args.against else None
    rep = judge(copy.deepcopy(full), [parse_site(t) for t in args.site], base)
    print_gate(rep, args.top)
    if args.json:
        # the WHOLE reading (a later round's --against control) and the
        # judged verdict beside it
        full["judged"] = {k: rep.get(k) for k in ("verdict", "judged_sites", "moved")}
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(full, fh, indent=1, default=str)
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
