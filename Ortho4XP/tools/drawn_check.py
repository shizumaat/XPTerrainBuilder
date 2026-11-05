"""DRAWN CHECK (#1903): what X-Plane DRAWS at every claimed cut, deck and
tunnel site, against the cut the patch asked for.

Every earlier tunnel/deck round "passed" on the engine's own numbers (patch
ways, replay records, the pre-write plan).  This reads the products X-Plane
loads instead:

- the WRITTEN pack DSF (``DSFTool --dsf2text``), each row placed the way
  X-Plane places it -- ``OBJECT``: zero = the drawn mesh under the anchor;
  ``OBJECT_AGL``: drawn mesh + elevation; ``OBJECT_MSL``: zero = the row's
  elevation.  In DSFTool text an ``OBJECT_MSL`` row is
  ``OBJECT_MSL idx lon lat ELEVATION HEADING`` (elevation BEFORE heading);
  the parse is the engine's own ``airport.dsf.read_dump``;
- the DRAWN tile mesh: the physical patches of the installed tile DSF,
  streamed through DSFTool (nothing large on disk) and sampled with the
  engine's ``MeshElevationSampler``;
- the patch (``<ICAO>_auto.patch.osm``) for the cut floor, its sidecar for
  the reader claims, and the object plan for each claim's fate.

Sites: the lowest node of every ``tunnel_ramp`` / ``tunnel_trench`` way and
every tunnel mouth of the sidecar (its floor = the lowest cut node within R,
else the drawn mesh there).  Per site, the claimed placements (written rows
whose resource -- split bodies ``<stem>__b<N>_<hash>`` folded to their
stem -- a reader claimed) with OBJ vertices within R, and their lowest
drawn vertex.  Bars (#1903 brief):

- CUT role (portal / tunnel_object / object_cut not also a deck_anchor):
  |drawn object bottom - cut floor| <= --tol (0.3 m);
- DECK role (the object is a deck_anchor): the deck stands over the floor
  (bottom - floor >= -tol); clearance reported;
- ramp relief (way top - floor) > 0 at a CUT-role ramp;
- no claimed object KEPT with "split undone" in its plan.

SPLIT-LEVEL BUILDINGS (the sidecar's ``basin_facilities`` of kind
``split_level``, ``planar/split_level_pit``): per building, its written
rows' drawn zero, its lower floor (zero + ``plate_y_m``) against the drawn
mesh over its floor, and its upper floor (+ ``floor_below_rim_m``) against
the drawn mesh 1 m outside each open side.  Bars: |lower floor - drawn
floor| <= tol; |upper floor - median open-side ground| <= tol; no open-side
station with the ground more than tol under the upper floor (a gap that
shows the open wall).

A site with no claimed object within R is UNCLAIMED (reported, no bar).
``lowest any`` is the lowest drawn vertex of ANY pack row within R -- the
rc1903 instrument's own column.  Exit 1 if any bar fails.

Usage (from Ortho4XP/):
    venv/bin/python tools/drawn_check.py ENTC --tile +69+018 \
        --patches /Users/noah/XPTerrainBuilderData/Patches
    venv/bin/python tools/drawn_check.py LOWS --tile +47+012 --tag T --out DIR
    ... --json OUT.json [--against BASE.json]   (controls: flag moved sites)
"""
from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import numpy

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Twin: ``tests/test_console_encoding.py``.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console  # noqa: E402, I001

_o4console.configure_console_streams()

from auto_patch.mesh_sampler import MeshElevationSampler  # noqa: E402
from auto_patch.obj8_reader import load_object_file  # noqa: E402
from auto_patch_v2.airport import dsf as dsf_text  # noqa: E402

M_PER_DEG = 111320.0
DECK_ANCHOR = "deck_anchor"
_BODY = re.compile(r"__b\d+_[0-9a-f]+$")
_CLAIM = re.compile(r"dsf:obj(\d+)(?:@(.+))?")


@dataclasses.dataclass
class Site:
    name: str
    lon: float
    lat: float
    floor: float          # nan: no cut node within R (mesh stands in)
    top: float            # way top; nan for a mouth
    kind: str             # tunnel_ramp / tunnel_trench / mouth


@dataclasses.dataclass
class Claim:
    kind: str             # portal / tunnel_object:<k> / object_cut / deck_anchor
    claim_id: str
    resource: str         # pristine def path ('' when unresolved)
    fate: str             # split / KEPT: <reason> / whole


# ── the drawn mesh ──────────────────────────────────────────────────────

def mesh_triangles(lines, bbox):
    """Physical-patch triangles of a DSFTool text stream touching ``bbox``
    ``(lon0, lat0, lon1, lat1)`` -> (vertices (3n,3), triangles (n,3))."""
    from O4_Default_Terrain_Map import _primitive_triangles
    lo0, la0, lo1, la1 = bbox
    out, physical, prim, buf = [], False, -1, []
    for raw in lines:
        if raw.startswith("PATCH_VERTEX"):
            if physical and prim >= 0:
                t = raw.split()
                buf.append((float(t[1]), float(t[2]), float(t[3])))
        elif raw.startswith("BEGIN_PATCH"):
            physical = bool(int(raw.split()[4]) & 1)
        elif raw.startswith("BEGIN_PRIMITIVE"):
            prim, buf = int(raw.split()[1]), []
        elif raw.startswith("END_PRIMITIVE"):
            if physical:
                for tri in _primitive_triangles(prim, buf):
                    if any(lo0 <= v[0] <= lo1 and la0 <= v[1] <= la1 for v in tri):
                        out.extend(tri)
            prim, buf = -1, []
    verts = numpy.array(out, dtype=numpy.float64).reshape(-1, 3)
    return verts, numpy.arange(len(verts)).reshape(-1, 3)


def stream_dsf(dsf_path):
    """Yield the DSFTool text of ``dsf_path`` line by line (fifo where the
    OS has one: a tile DSF's text is gigabytes)."""
    from auto_patch.dsf_reader import _dsftool_path
    tool = _dsftool_path()
    with tempfile.TemporaryDirectory() as d:
        txt = os.path.join(d, "dsf.txt")
        if hasattr(os, "mkfifo"):
            os.mkfifo(txt)
            proc = subprocess.Popen([tool, "--dsf2text", dsf_path, txt],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        else:
            subprocess.run([tool, "--dsf2text", dsf_path, txt], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc = None
        with open(txt, encoding="utf-8", errors="replace") as fh:
            yield from fh
        if proc is not None:
            proc.wait()


def drawn_mesh(sources, bbox):
    """One sampler over the drawn mesh of every source (each an iterable
    of DSF text lines)."""
    parts = [mesh_triangles(src, bbox) for src in sources]
    verts = numpy.concatenate([p[0] for p in parts])
    tris = numpy.arange(len(verts)).reshape(-1, 3)
    return MeshElevationSampler.from_arrays(
        verts, tris, numpy.zeros(len(tris), dtype=numpy.int64),
        (bbox[0], bbox[1], bbox[2], bbox[3]), 0.0)


def mesh_z(mesh, lon, lat):
    z = mesh.elevation_at_or_none(lat, lon)
    return float("nan") if z is None else z


# ── the patch: sites ────────────────────────────────────────────────────

def read_sites(patch_path, sidecar, radius_m):
    """Cut floors of the patch and the sidecar's tunnel mouths."""
    nodes, ways = {}, []
    for _ev, el in ET.iterparse(patch_path):
        if el.tag == "node":
            alt = [t.get("v") for t in el.findall("tag") if t.get("k") == "alt_abs"]
            nodes[el.get("id")] = (float(el.get("lon")), float(el.get("lat")),
                                   float(alt[0]) if alt else float("nan"))
        elif el.tag == "way":
            role = {t.get("k"): t.get("v") for t in el.findall("tag")}.get("role")
            if role in ("tunnel_ramp", "tunnel_trench"):
                ways.append((el.get("id"), role,
                             [n.get("ref") for n in el.findall("nd")]))
            el.clear()
    sites, cut_nodes = [], []
    for wid, role, refs in ways:
        pts = [nodes[r] for r in refs if r in nodes and not math.isnan(nodes[r][2])]
        if not pts:
            continue
        cut_nodes.extend(pts)
        lo = min(pts, key=lambda p: p[2])
        sites.append(Site(f"{role} {wid}", lo[0], lo[1], lo[2],
                          max(p[2] for p in pts), role))
    cut = numpy.array(cut_nodes, dtype=float).reshape(-1, 3)
    for r in sidecar.get("tunnel_mouth_depths", []):
        lat, lon = r["mouth_ll"]
        floor = float("nan")
        if len(cut):
            kx = M_PER_DEG * math.cos(math.radians(lat))
            d = numpy.hypot((cut[:, 0] - lon) * kx, (cut[:, 1] - lat) * M_PER_DEG)
            near = d <= radius_m
            if near.any():
                floor = float(cut[near, 2].min())
        sites.append(Site(f"mouth {r['id']}", lon, lat, floor, float("nan"),
                          "mouth"))
    return sites


def patch_bbox(patch_path, margin_deg):
    head = open(patch_path, encoding="utf-8", errors="replace").read()
    ll = numpy.array(re.findall(r"lat=['\"]([-0-9.]+)['\"] lon=['\"]([-0-9.]+)['\"]",
                                head), dtype=float)
    return (ll[:, 1].min() - margin_deg, ll[:, 0].min() - margin_deg,
            ll[:, 1].max() + margin_deg, ll[:, 0].max() + margin_deg)


# ── claims and their fate ───────────────────────────────────────────────

def plan_fates(plan):
    fates = {}
    for s in plan.get("splits", []):
        pl = s["placement"]
        fates[pl["index"]] = (pl.get("resource", ""), "split")
    for k in plan.get("kept", []):
        fates[k["index"]] = (k.get("resource", ""), f"KEPT: {k.get('reason')}")
    return fates


def read_claims(sidecar, tile, plans, pristine):
    """Every object a structure reader claimed, resolved to its pristine
    resource and its plan fate.  ``plans`` / ``pristine``: tile -> plan
    dict / pristine ``DsfDump``."""
    raw = [("portal", r["id"], r["portal"]) for r in sidecar.get("portal_cuts", [])]
    for r in sidecar.get("tunnel_objects", []):
        raw += [("tunnel_object:" + r["kind"], r["id"], o) for o in r["objects"]]
    for r in sidecar.get("object_cuts", []):
        raw += [("object_cut", r["id"], o) for o in r["objects"]]
    for r in sidecar.get("deck_anchors", []):
        raw.append((DECK_ANCHOR, f"{r.get('end', '')}", str(r.get("object", ""))))
    claims = []
    for kind, cid, obj in raw:
        m = _CLAIM.match(obj)
        if not m:
            continue
        i, t = int(m.group(1)), m.group(2) or tile
        res, fate = plan_fates(plans.get(t) or {}).get(i, ("", "whole"))
        dump = pristine.get(t)
        if not res and dump is not None and i < len(dump.placements):
            res = dump.placements[i].def_path
        claims.append(Claim(kind, cid, res, fate))
    return claims


def stem(def_path):
    return _BODY.sub("", os.path.splitext(def_path)[0])


# ── placing what X-Plane draws ──────────────────────────────────────────

class Drawn:
    """The written rows, each placed on the drawn mesh, vertices cached."""

    def __init__(self, placements, pack_root, mesh):
        self.rows = list(placements)
        self.root, self.mesh = pack_root, mesh
        self.anchors = numpy.array([[p.lon, p.lat] for p in self.rows]).reshape(-1, 2)
        self._geom, self._placed = {}, {}

    def vertices(self, i):
        """(lon, lat, z_abs) arrays of row ``i``'s OBJ vertices, or None."""
        if i in self._placed:
            return self._placed[i]
        p, out = self.rows[i], None
        path = os.path.join(self.root, p.def_path)
        if path not in self._geom:
            v = None
            if path.lower().endswith(".obj") and os.path.isfile(path):
                g = load_object_file(path).vertices
                v = numpy.array(g, dtype=float) if g else None
            self._geom[path] = v
        v = self._geom[path]
        if v is not None:
            h = math.radians(p.heading_deg)
            kx = M_PER_DEG * math.cos(math.radians(p.lat))
            east = v[:, 0] * math.cos(h) - v[:, 2] * math.sin(h)
            north = -v[:, 0] * math.sin(h) - v[:, 2] * math.cos(h)
            if p.kind == "OBJECT_MSL":
                base = p.elevation
            else:
                base = mesh_z(self.mesh, p.lon, p.lat) + (
                    p.elevation or 0.0 if p.kind == "OBJECT_AGL" else 0.0)
            out = (p.lon + east / kx, p.lat + north / M_PER_DEG, base + v[:, 1])
        self._placed[i] = out
        return out

    def bottoms_near(self, lon, lat, radius_m, reach_m=6000.0):
        """{row: lowest drawn z of its vertices within radius_m}."""
        kx = M_PER_DEG * math.cos(math.radians(lat))
        if not len(self.anchors):
            return {}
        far = numpy.hypot((self.anchors[:, 0] - lon) * kx,
                          (self.anchors[:, 1] - lat) * M_PER_DEG) > reach_m
        out = {}
        for i in numpy.flatnonzero(~far):
            v = self.vertices(int(i))
            if v is None:
                continue
            near = numpy.hypot((v[0] - lon) * kx, (v[1] - lat) * M_PER_DEG) <= radius_m
            if near.any() and not numpy.isnan(v[2][near]).all():
                out[int(i)] = float(numpy.nanmin(v[2][near]))
        return out


# ── the verdict ─────────────────────────────────────────────────────────

def check_site(site, drawn, claims, radius_m, tol):
    """One site's row: drawn bottom of the claimed object(s), floor, relief,
    split status and the failed bars."""
    zm = mesh_z(drawn.mesh, site.lon, site.lat)
    floor = site.floor if not math.isnan(site.floor) else zm
    by_stem = {}
    for c in claims:
        if c.resource:
            by_stem.setdefault(stem(c.resource), []).append(c)
    bottoms = drawn.bottoms_near(site.lon, site.lat, radius_m)
    row = {"site": site.name, "lat": round(site.lat, 6), "lon": round(site.lon, 6),
           "floor": round(floor, 2), "floor_from": "patch" if not math.isnan(site.floor)
           else "mesh", "mesh": round(zm, 2), "relief": None, "objects": [],
           "lowest_any": None, "role": "UNCLAIMED", "fails": []}
    if site.kind == "tunnel_ramp":
        row["relief"] = round(site.top - site.floor, 2)
    if bottoms:
        j = min(bottoms, key=bottoms.get)
        row["lowest_any"] = {"resource": drawn.rows[j].def_path,
                             "delta": round(bottoms[j] - floor, 2)}
    cut, deck = [], []
    for i, z in sorted(bottoms.items(), key=lambda kv: kv[1]):
        cs = by_stem.get(stem(drawn.rows[i].def_path))
        if not cs:
            continue
        is_deck = any(c.kind == DECK_ANCHOR for c in cs)
        fate = next((c.fate for c in cs if c.kind != DECK_ANCHOR), cs[0].fate)
        rec = {"row": i, "resource": drawn.rows[i].def_path,
               "kind": drawn.rows[i].kind, "bottom": round(z, 2),
               "delta": round(z - floor, 2), "role": "DECK" if is_deck else "CUT",
               "fate": fate}
        row["objects"].append(rec)
        (deck if is_deck else cut).append(rec)
        if "split undone" in fate:
            row["fails"].append(f"split undone: {rec['resource']}")
    if cut:
        row["role"] = "CUT"
        best = min(cut, key=lambda r: abs(r["delta"]))
        row["delta"] = best["delta"]
        if math.isnan(best["delta"]) or abs(best["delta"]) > tol:
            row["fails"].append(f"bottom-floor {best['delta']:+.2f} > {tol}")
        if row["relief"] is not None and not row["relief"] > 0.0:
            row["fails"].append(f"ramp relief {row['relief']:+.2f}")
    elif deck:
        row["role"] = "DECK"
        row["delta"] = min(r["delta"] for r in deck)
        if not row["delta"] >= -tol:
            row["fails"].append(f"deck under the floor {row['delta']:+.2f}")
    row["verdict"] = ("FAIL" if row["fails"] else
                      "PASS" if row["role"] != "UNCLAIMED" else "-")
    return row


def _base(drawn, i):
    """The drawn zero of written row ``i`` (module docstring's placement)."""
    p = drawn.rows[i]
    if p.kind == "OBJECT_MSL":
        return p.elevation
    return mesh_z(drawn.mesh, p.lon, p.lat) + (
        p.elevation or 0.0 if p.kind == "OBJECT_AGL" else 0.0)


def _outside(seg, centre, out_m, n=5):
    """``n`` (lon, lat) stations ``out_m`` outside the (lat, lon) segment
    ``seg``, away from ``centre`` (lon, lat)."""
    (la0, lo0), (la1, lo1) = seg[0], seg[-1]
    kx = M_PER_DEG * math.cos(math.radians(la0))
    x0, y0, x1, y1 = lo0 * kx, la0 * M_PER_DEG, lo1 * kx, la1 * M_PER_DEG
    L = math.hypot(x1 - x0, y1 - y0) or 1.0
    nx, ny = (y1 - y0) / L, -(x1 - x0) / L
    cx, cy = centre[0] * kx, centre[1] * M_PER_DEG
    if (cx - 0.5 * (x0 + x1)) * nx + (cy - 0.5 * (y0 + y1)) * ny > 0.0:
        nx, ny = -nx, -ny
    out = []
    for k in range(n):
        f = (k + 0.5) / n
        out.append(((x0 + f * (x1 - x0) + nx * out_m) / kx,
                    (y0 + f * (y1 - y0) + ny * out_m) / M_PER_DEG))
    return out


def check_split(rec, drawn, tol):
    """One split-level building's row (module docstring)."""
    stems = {stem(r) for r in rec.get("resources", [])}
    rows = [i for i, p in enumerate(drawn.rows) if stem(p.def_path) in stems]
    lon, lat = rec["anchor_longitude_latitude"]
    kx = M_PER_DEG * math.cos(math.radians(lat))
    rows = [i for i in rows if math.hypot((drawn.rows[i].lon - lon) * kx,
                                          (drawn.rows[i].lat - lat) * M_PER_DEG) < 300.0]
    y_lo = float(rec.get("plate_y_m") or 0.0)
    y_up = y_lo + float(rec.get("floor_below_rim_m") or 0.0)
    out = {"site": f"split_level {rec.get('floor_ref')}", "lat": round(lat, 6),
           "lon": round(lon, 6), "resources": sorted(stems), "rows": len(rows),
           "fails": [], "role": "SPLIT"}
    if not rows:
        out["fails"].append("no written row of the building")
        out["verdict"] = "FAIL"
        return out
    zeros = [_base(drawn, i) for i in rows]
    z0 = float(numpy.nanmedian(zeros))
    floor = mesh_z(drawn.mesh, lon, lat)
    ground = [mesh_z(drawn.mesh, x, y) for sd in rec.get("open_sides_ll", [])
              for x, y in _outside(sd, (lon, lat), 1.0)]
    ground = [g for g in ground if not math.isnan(g)]
    out.update({"zero": round(z0, 2), "zero_spread": round(max(zeros) - min(zeros), 2),
                "lower_floor": round(z0 + y_lo, 2), "drawn_floor": round(floor, 2),
                "patch_floor": rec.get("floor_m"), "upper_floor": round(z0 + y_up, 2),
                "open_ground_median": round(float(numpy.median(ground)), 2) if ground else None,
                "open_ground_min": round(min(ground), 2) if ground else None})
    d_lo = z0 + y_lo - floor
    out["delta"] = round(d_lo, 2)
    if math.isnan(d_lo) or abs(d_lo) > tol:
        out["fails"].append(f"lower floor - drawn floor {d_lo:+.2f} > {tol}")
    if out["zero_spread"] > tol:
        out["fails"].append(f"rows seated {out['zero_spread']:.2f} m apart")
    if ground:
        d_up = out["open_ground_median"] - (z0 + y_up)
        out["delta_upper"] = round(d_up, 2)
        if abs(d_up) > tol:
            out["fails"].append(f"open-side ground - upper floor {d_up:+.2f} > {tol}")
        gap = (z0 + y_up) - min(ground)
        if gap > tol:
            out["fails"].append(f"open wall shows a {gap:.2f} m gap to the terrain")
    else:
        out["fails"].append("no drawn ground outside the open side")
    out["verdict"] = "FAIL" if out["fails"] else "PASS"
    return out


def compare(rows, base_rows, tol=0.05):
    """Sites whose verdict or delta moved against a baseline run."""
    base = {r["site"]: r for r in base_rows}
    moved = []
    for r in rows:
        b = base.get(r["site"])
        if b is None:
            moved.append(f"{r['site']}: new site")
        elif b["verdict"] != r["verdict"] or (
                r.get("delta") is not None and b.get("delta") is not None
                and abs(r["delta"] - b["delta"]) > tol):
            moved.append(f"{r['site']}: {b['verdict']} {b.get('delta')} -> "
                         f"{r['verdict']} {r.get('delta')}")
    moved += [f"{s}: site gone" for s in base.keys() - {r["site"] for r in rows}]
    return moved


# ── inputs ──────────────────────────────────────────────────────────────

def resolve(args):
    """patch dir, tile-mesh DSF(s) from the args (owner products or a
    harness tag)."""
    tile_dsfs = []
    if args.tag:
        res = json.load(open(os.path.join(args.out, f"{args.tag}.result.json"),
                             encoding="utf-8"))
        patch_dir, build = res["patch_dir"], res["build_dir"]
        tile_dsfs = glob.glob(os.path.join(build, "Earth nav data", "*", "*.dsf"))
    else:
        lat, lon = int(args.tile[:3]), int(args.tile[3:])
        block = f"{lat // 10 * 10:+03d}{lon // 10 * 10:+04d}"
        patch_dir = os.path.join(args.patches, block, args.tile)
    return patch_dir, tile_dsfs


def load_plans(patch_dir, icao):
    plans = {}
    for p in glob.glob(os.path.join(os.path.dirname(patch_dir), "*",
                                    f"o4_v2_placement_{icao}.json")):
        try:
            plans[os.path.basename(os.path.dirname(p))] = json.load(
                open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return plans


def dump_dsf(path, tmp):
    from auto_patch.dsf_reader import _dsftool_path
    from auto_patch_v2.airport.dsf_write import dump
    out = os.path.join(tmp, f"{len(os.listdir(tmp))}.txt")
    return dsf_text.read_dump(dump(path, out, _dsftool_path()),
                              accept_polygon=lambda _p: False)


def run(args):
    patch_dir, tile_dsfs = resolve(args)
    tile = os.path.basename(patch_dir)
    patch = os.path.join(patch_dir, f"{args.icao}_auto.patch.osm")
    sidecar = json.load(open(patch + ".axes.json", encoding="utf-8"))
    plans = load_plans(patch_dir, args.icao)
    if tile not in plans:
        sys.exit(f"no o4_v2_placement_{args.icao}.json for {tile} under "
                 f"{os.path.dirname(patch_dir)}")
    pack_root = plans[tile]["pack_root"]
    if not tile_dsfs:
        scenery = os.path.dirname(pack_root)
        tile_dsfs = [f for t in plans for f in glob.glob(os.path.join(
            scenery, f"zOrtho4XP_{t}", "Earth nav data", "*", f"{t}.dsf"))]
    bbox = patch_bbox(patch, args.margin)
    from auto_patch_v2.airport.dsf_write import pristine_dsf_path
    written, pristine = [], {}
    with tempfile.TemporaryDirectory() as tmp:
        for t, plan in sorted(plans.items()):
            written += dump_dsf(plan["dsf_path"], tmp).placements
            pristine[t] = dump_dsf(pristine_dsf_path(plan["dsf_path"]), tmp)
    mesh = drawn_mesh([stream_dsf(f) for f in tile_dsfs], bbox)
    claims = read_claims(sidecar, tile, plans, pristine)
    drawn = Drawn(written, pack_root, mesh)
    rows = [check_site(s, drawn, claims, args.radius, args.tol)
            for s in read_sites(patch, sidecar, args.radius)]
    rows += [check_split(r, drawn, args.tol) for r in sidecar.get("basin_facilities", [])
             if r.get("kind") == "split_level"]
    return {"icao": args.icao, "tile": tile, "pack_root": pack_root,
            "tile_dsfs": tile_dsfs, "tol_m": args.tol, "radius_m": args.radius,
            "claims": [dataclasses.asdict(c) for c in claims], "sites": rows}


def print_report(rep):
    print(f"DRAWN CHECK {rep['icao']} {rep['tile']}  pack {rep['pack_root']}")
    for r in rep["sites"]:
        if r.get("role") == "SPLIT":
            print(f"{r['verdict']:4s} {r['site']} @{r['lat']},{r['lon']} "
                  f"{','.join(os.path.basename(x) for x in r['resources'])} rows {r['rows']}: "
                  f"lower floor {r.get('lower_floor')} on drawn floor {r.get('drawn_floor')} "
                  f"(patch {r.get('patch_floor')}), upper floor {r.get('upper_floor')} vs "
                  f"open-side ground {r.get('open_ground_median')} (min "
                  f"{r.get('open_ground_min')})")
            for f in r["fails"]:
                print(f"       FAIL {f}")
            continue
        rel = "" if r["relief"] is None else f" relief {r['relief']:+.2f}"
        low = r["lowest_any"]
        print(f"{r['verdict']:4s} {r['site']} @{r['lat']},{r['lon']} floor "
              f"{r['floor']:.2f} ({r['floor_from']}) mesh {r['mesh']:.2f}{rel} "
              f"[{r['role']}" + (f" {r['delta']:+.2f}]" if "delta" in r else "]")
              + (f" lowest any {low['delta']:+.2f} {os.path.basename(low['resource'])}"
                 if low else ""))
        for o in r["objects"]:
            print(f"       {o['role']:4s} {o['kind']} {o['resource']} bottom "
                  f"{o['bottom']:.2f} ({o['delta']:+.2f}) fate {o['fate']}")
        for f in r["fails"]:
            print(f"       FAIL {f}")
    n = sum(r["verdict"] == "FAIL" for r in rep["sites"])
    print(f"SUMMARY {rep['icao']} {rep['tile']}: {len(rep['sites'])} sites, "
          f"{sum(r['verdict'] == 'PASS' for r in rep['sites'])} PASS, {n} FAIL")
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("icao")
    ap.add_argument("--tile", help="+LL+LLL (owner products under --patches)")
    ap.add_argument("--patches", default=None,
                    help="Patches root (default: this tree's FNAMES.Patch_dir)")
    ap.add_argument("--tag", help="harness tag: read <out>/<tag>.result.json")
    ap.add_argument("--out", default="/tmp/harness", help="harness --out dir")
    ap.add_argument("--radius", type=float, default=15.0, metavar="M")
    ap.add_argument("--tol", type=float, default=0.3, metavar="M")
    ap.add_argument("--margin", type=float, default=0.012, metavar="DEG")
    ap.add_argument("--json", help="write the report here")
    ap.add_argument("--against", help="baseline --json: list moved sites")
    args = ap.parse_args(argv)
    if not (args.tile or args.tag):
        ap.error("--tile or --tag is required")
    if args.patches is None:
        import O4_File_Names as FNAMES
        args.patches = FNAMES.Patch_dir
    rep = run(args)
    fails = print_report(rep)
    if args.against:
        base = json.load(open(args.against, encoding="utf-8"))["sites"]
        moved = compare(rep["sites"], base)
        print(f"AGAINST {args.against}: {len(moved)} moved")
        for m in moved:
            print(f"   MOVED {m}")
        fails += len(moved)
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(rep, fh, indent=1)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
