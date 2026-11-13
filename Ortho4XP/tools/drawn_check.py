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
  |drawn object bottom - cut floor| <= --tol (0.3 m); an OBJECT FLOOR's
  cut stands its ``clearance_m`` (sidecar ``object_floors``) beneath the
  floor (owner RULINGS 2026-11-06d (4): the floor drawn, never covered), so
  its bar is |bottom - floor - clearance| <= tol;
- DECK role (the object is a deck_anchor): the deck stands over the floor
  (bottom - floor >= -tol); clearance reported;
- ramp relief (way top - floor) > 0 at a CUT-role ramp;
- no claimed object KEPT with "split undone" in its plan.

DECK STACKS (#1971; the sidecar's ``object_floors`` rows carrying
``"stack"``): the stack's decks take the DECK bar, never the CUT bar, and
one STACK row per stack measures D1-D6 (:func:`check_stack`: one zero, the
floor under the decks, the end lines, nothing through a deck, the walls'
top, no pad on their caps).

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    #: an object floor's cut stands this far beneath its floor (2026-11-06d (4))
    clearance: float = 0.0


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
    clear = {}
    for r in sidecar.get("object_floors", []):
        # a deck stack's decks (#1971) stand OVER its floor: the DECK bar
        decks = {d["object"] for d in (r.get("stack") or {}).get("decks", [])}
        raw += [(DECK_ANCHOR if o in decks else "object_floor", r["id"], o)
                for o in r["objects"]]
        clear[r["id"]] = float(r.get("clearance_m", 0.0) or 0.0)
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
        claims.append(Claim(kind, cid, res, fate,
                            clear.get(cid, 0.0) if kind == "object_floor" else 0.0))
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
    if math.isnan(zm):
        # off the drawn mesh read (a mouth on the neighbour tile): no bar
        row.update(role="OFF MESH", verdict="-")
        return row
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
        clear = max((c.clearance for c in cs), default=0.0)
        rec = {"row": i, "resource": drawn.rows[i].def_path,
               "kind": drawn.rows[i].kind, "bottom": round(z, 2),
               "delta": round(z - floor, 2), "role": "DECK" if is_deck else "CUT",
               "fate": fate, "clearance": clear}
        row["objects"].append(rec)
        (deck if is_deck else cut).append(rec)
        if "split undone" in fate:
            row["fails"].append(f"split undone: {rec['resource']}")
    if cut:
        row["role"] = "CUT"
        best = min(cut, key=lambda r: abs(r["delta"] - r["clearance"]))
        row["delta"] = best["delta"]
        miss = best["delta"] - best["clearance"]
        if math.isnan(miss) or abs(miss) > tol:
            row["fails"].append(f"bottom-floor {best['delta']:+.2f}"
                                + (f" (clearance {best['clearance']:g})"
                                   if best["clearance"] else "") + f" > {tol}")
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


# ── a deck stack (#1971) ────────────────────────────────────────────────

def _local(lat0):
    kx = M_PER_DEG * math.cos(math.radians(lat0))
    return (lambda la, lo: ((lo - 0.0) * kx, la * M_PER_DEG),
            lambda x, y: (y / M_PER_DEG, x / kx))


def _every(pts, k):
    return pts[::k] + ([pts[-1]] if pts and (len(pts) - 1) % k else [])


#: THE STACK'S D BARS (spec ``interchange-levels-v2-20261113.md`` §8.3) on
#: the DRAWN mesh, and on the PREDICTED patch (§8.2) each at half its
#: tolerance: D2 |floor - walls' bottom|; D3 road / ground stations off the
#: plate's top; D4 the plate at the cell over the ground (least); D5 / D6
#: (under, over) the walls' top
STACK_BARS = {"D2": 0.10, "D3r": 0.30, "D3g": 0.50, "D4": -0.05,
              "D5": (0.50, 0.05), "D6": (0.50, 0.50)}
PREDICTED_BARS = {"D2": 0.05, "D3r": 0.15, "D3g": 0.25, "D4": 0.0,
                  "D5": (0.25, 0.0), "D6": (0.25, 0.0)}
#: a residual under this is reported, never failed (spec v2 §11: materiality)
MATERIALITY_M = 0.01
#: the patch roles a D3 station reads as ROAD (``model/planar.ROAD_ROLES``)
ROAD_ROLES = ("service_road", "service_junction", "groundside_pavement")


def _plate_at(d, to_m):
    """``f(x, y) -> plate y`` over deck ``d``'s published plate triangles
    (``plate``: ``[[lat, lon, y] x 3]``); off every triangle (or with no
    plate published) the plate's lowest point."""
    lo = float(d.get("plate_min_y", 0.0))
    tris = [[(*to_m(la, lo_), y) for la, lo_, y in t] for t in d.get("plate", [])]

    def at(x, y):
        best = None
        for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in tris:
            det = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
            if abs(det) < 1e-9:
                continue
            u = ((x - ax) * (cy - ay) - (cx - ax) * (y - ay)) / det
            v = ((bx - ax) * (y - ay) - (x - ax) * (by - ay)) / det
            if u >= -1e-6 and v >= -1e-6 and u + v <= 1 + 1e-6:
                z = az + u * (bz - az) + v * (cz - az)
                best = z if best is None else min(best, z)
        return lo if best is None else best
    return at


def _outward(pts, k, inside):
    """The unit normal of the wall line ``pts`` at its ``k``-th point, on
    the side away from ``inside`` (the floor's centreline point nearest
    it): "outside the wall line", which at a wall's end -- where the line
    runs past the floor's last station -- the direction to that station is
    not (spec v2 §8.3 D5 / D6)."""
    a, b = pts[max(0, k - 1)], pts[min(len(pts) - 1, k + 1)]
    t = numpy.subtract(b, a)
    n = numpy.array([-t[1], t[0]]) / (numpy.hypot(*t) or 1.0)
    return -n if float(numpy.dot(n, numpy.subtract(inside, pts[k]))) > 0.0 else n


class _Frame:
    """The stack's written rows as X-Plane places them, or -- with no
    written pack (a PREDICTED read without ``--plan``) -- the sidecar's own
    frame: every member at the stack's zero, the walls from feet to crest."""

    def __init__(self, rec, drawn, x0y0, to_m):
        st = rec["stack"]
        self.st, self.rows, self.elev = st, {}, {}
        mine = {stem(rec["resource"])} | {stem(d["resource"]) for d in st["decks"]}
        if drawn is not None:
            for i, p in enumerate(drawn.rows):
                if stem(p.def_path) in mine and math.hypot(
                        *numpy.subtract(to_m(p.lat, p.lon), x0y0)) <= 400.0:
                    self.rows.setdefault(stem(p.def_path), []).append(i)
                    self.elev[i] = _base(drawn, i)
        self.drawn = drawn
        self.walls = self.rows.get(stem(rec["resource"]), [])

    @property
    def written(self):
        return bool(self.rows)

    def spread(self):
        zs = list(self.elev.values()) if self.written else [self.st["zero_m"]]
        return max(zs) - min(zs)

    def walls_bottom_top(self):
        if not self.written:
            return self.st["zero_m"] + self.st["feet_y"], self.st["zero_m"] + self.st["crest_y"]
        if not self.walls:
            return None
        vw = self.drawn.vertices(self.walls[0])
        if vw is None:
            return None
        return float(numpy.nanmin(vw[2])), self.elev[self.walls[0]] + self.st["crest_y"]

    def deck_zero(self, d):
        if not self.written:
            return self.st["zero_m"]
        ids = self.rows.get(stem(d["resource"]), [])
        return self.elev[ids[0]] if ids else None


def check_stack(rec, drawn, claims, tol, step=5.0, faces=None, predict=False, standoff=1.0):
    """One deck stack's STACK row (spec interchange-levels v2 §8.3): D1 one
    zero (the members' written elevations); D2 the floor (drawn mesh on the
    floor's centreline against the walls' drawn bottom); D3 each end line,
    ``step`` outside it, its stations on a road face of the patch (D3r)
    and off it (D3g) against the plate's top; D4 nothing through a deck
    (the plate AT the cell over the drawn mesh, 2 m grid); D5 the walls'
    top (``band_m + 0.5`` m outside each wall line); D6 the caps (3 m
    outside, where a published cap covers the point; every point when the
    sidecar publishes none).  ``faces``: the patch's
    ``patch_faces.PatchFaces`` (the D3 stations' road / ground split; with
    ``predict`` the sampler itself, and a sample no face holds within
    ``standoff`` is UNCOVERED: the verdict is then INCOMPLETE, never a
    pass).  ``drawn``: the written rows over the mesh, or ``None`` for the
    sidecar's frame (``_Frame``).  ``claims`` / ``tol`` are kept for the
    caller's signature; the bars are :data:`STACK_BARS` /
    :data:`PREDICTED_BARS`."""
    from shapely.geometry import Point, Polygon
    del claims, tol
    bars = PREDICTED_BARS if predict else STACK_BARS
    st = rec["stack"]
    lat0, lon0 = st["floor_line"][len(st["floor_line"]) // 2]
    to_m, to_ll = _local(lat0)
    x0, y0 = to_m(lat0, lon0)
    mesh = drawn.mesh if drawn is not None else faces
    row = {"site": f"stack {st['id']}", "lat": round(lat0, 6), "lon": round(lon0, 6),
           "role": "STACK", "mode": "PREDICTED" if predict else "DRAWN", "fails": [],
           "objects": [], "relief": None, "lowest_any": None, "uncovered": {}, "samples": {},
           "no_face": {}}
    fr = _Frame(rec, drawn, (x0, y0), to_m)
    if drawn is not None and not fr.written:
        row.update(verdict="-", why="no member row written near the stack")
        return row
    if not fr.written:
        row["d1_from"] = "sidecar (no written pack)"

    def z_at(la, lo, key):
        row["samples"][key] = row["samples"].get(key, 0) + 1
        if predict and faces is not None and faces.at(la, lo) is None:
            row["no_face"][key] = row["no_face"].get(key, 0) + 1
            if faces.gap_m(la, lo) > standoff:
                row["uncovered"].setdefault(key, []).append([round(la, 7), round(lo, 7)])
        return mesh_z(mesh, lo, la)

    row["d1_spread"] = round(fr.spread(), 3)
    if row["d1_spread"] > 0.01:
        row["fails"].append(f"D1 the members stand {row['d1_spread']:.3f} m apart")
    bt = fr.walls_bottom_top()
    if bt is None:
        row["fails"].append("the walls' row is not drawn")
        row["verdict"] = "FAIL"
        return row
    bottom, top = bt
    row["walls_bottom"], row["walls_top"] = round(bottom, 2), round(top, 2)
    rings = [(d, Polygon([to_m(la, lo) for la, lo in d["ring"]])) for d in st["decks"]]
    # D2: the floor
    d2, d2_both = [], []
    lv = {d["level"] for d in st["decks"]}
    for la, lo in _every(st["floor_line"], 5):
        z = z_at(la, lo, "D2")
        if math.isnan(z):
            continue
        d2.append(z - bottom)
        if lv and {d["level"] for d, r in rings if r.contains(Point(to_m(la, lo)))} == lv:
            d2_both.append(z - bottom)
    row["d2_worst"] = round(max(d2, key=abs), 2) if d2 else None
    row["d2_under_all_decks"] = round(max(d2_both, key=abs), 2) if d2_both else None
    if d2 and abs(row["d2_worst"]) > bars["D2"] + MATERIALITY_M:
        row["fails"].append(f"D2 the floor stands {row['d2_worst']:+.2f} off the walls' feet "
                            f"(bar {bars['D2']})")
    row["d3"], row["d4"] = [], []
    for d, ring in rings:
        zd = fr.deck_zero(d)
        if zd is None:
            row["fails"].append(f"deck {d['object']} not drawn")
            continue
        c = ring.centroid
        for e in d["ends"]:
            pts = [to_m(la, lo) for la, lo in e["stations"]]
            u = numpy.subtract(numpy.mean(pts, axis=0), (c.x, c.y))
            u = u / (numpy.hypot(*u) or 1.0)
            ptop = zd + e["top"]
            got = {"r": [], "g": []}
            for x, y in pts:
                la, lo = to_ll(x + u[0] * step, y + u[1] * step)
                on = faces.at(la, lo) if faces is not None else None
                k = "r" if on is not None and on[1] in ROAD_ROLES else "g"
                z = z_at(la, lo, "D3" + k)
                if not math.isnan(z):
                    got[k].append(round(ptop - z, 2))
            rec3 = {"deck": d["object"], "piece": d["piece"], "end": e["end"],
                    "plate_top": round(ptop, 2), "road": got["r"], "ground": got["g"]}
            row["d3"].append(rec3)
            for k, name in (("r", "road"), ("g", "ground")):
                if got[k] and max(map(abs, got[k])) > bars["D3" + k] + MATERIALITY_M:
                    row["fails"].append(f"D3{k} {d['object']}#{d['piece']} end {e['end']}: "
                                        f"the {name} {got[k]} off the plate top "
                                        f"(bar {bars['D3' + k]})")
        plate_y = _plate_at(d, to_m)
        x_lo, y_lo, x_hi, y_hi = ring.bounds
        worst, at = math.inf, None
        for gx in numpy.arange(x_lo + 1.0, x_hi, 2.0):          # the 2 m cells' centres
            for gy in numpy.arange(y_lo + 1.0, y_hi, 2.0):
                if ring.contains(Point(gx, gy)):
                    la, lo = to_ll(gx, gy)
                    z = z_at(la, lo, "D4")
                    if not math.isnan(z) and zd + plate_y(gx, gy) - z < worst:
                        worst, at = zd + plate_y(gx, gy) - z, [round(float(la), 7),
                                                                round(float(lo), 7)]
        if math.isfinite(worst):
            row["d4"].append({"deck": d["object"], "piece": d["piece"],
                              "least": round(worst, 2), "at": at})
            if worst < bars["D4"] - MATERIALITY_M:
                row["fails"].append(f"D4 the ground stands {-worst:.2f} m through "
                                    f"{d['object']}#{d['piece']} at {at} (bar {bars['D4']})")
    # D5 / D6: the walls' top, beside the void band and on the caps
    line = [to_m(la, lo) for la, lo in st["floor_line"]]
    caps = [Polygon([to_m(la, lo) for la, lo in r]) for r in st.get("caps", []) if len(r) >= 3]
    out5 = float(st.get("band_m", 1.0)) + 0.5
    d5, d6 = [], []
    for rim in st["rim"]:
        pts = [to_m(la, lo) for la, lo in rim]
        for k in sorted({*range(0, len(pts), 5), len(pts) - 1}):
            x, y = pts[k]
            u = _outward(pts, k, min(line, key=lambda p: math.hypot(p[0] - x, p[1] - y)))
            for off, acc, key in ((out5, d5, "D5"), (3.0, d6, "D6")):
                q = (x + u[0] * off, y + u[1] * off)
                if key == "D6" and "caps" in st and not any(p.covers(Point(q)) for p in caps):
                    continue
                qa, qo = to_ll(*q)
                z = z_at(qa, qo, key)
                if not math.isnan(z):
                    acc.append(z - top)
    for key, vals in (("D5", d5), ("D6", d6)):
        row[key.lower() + "_range"] = [round(min(vals), 2), round(max(vals), 2)] if vals else None
        under, over = bars[key]
        if vals and (max(vals) > over + MATERIALITY_M or min(vals) < -under - MATERIALITY_M):
            row["fails"].append(f"{key} the ground {row[key.lower() + '_range']} off the walls' "
                                f"top (bar -{under} / +{over})")
    row["delta"] = row["d2_worst"]
    row["uncovered_n"] = {k: len(v) for k, v in row["uncovered"].items()}
    row["verdict"] = ("FAIL" if row["fails"] else "INCOMPLETE" if row["uncovered"] else "PASS")
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


def road_nodes(patch_path, icao):
    """(lon, lat, z) of every node of a GROUNDSIDE road way of the patch
    (a pavement role whose law side is groundside): the profile the ground
    behind a split-level building meets the wall at (owner
    2026-11-06T02:40Z)."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import pavement_roles, role_side
    law = Law.for_airport(icao)
    roads = {r for r in pavement_roles(law) if role_side(law, r) == "groundside"}
    nodes, keep = {}, set()
    for _ev, el in ET.iterparse(patch_path):
        if el.tag == "node":
            alt = [t.get("v") for t in el.findall("tag") if t.get("k") == "alt_abs"]
            if alt:
                nodes[el.get("id")] = (float(el.get("lon")), float(el.get("lat")),
                                       float(alt[0]))
        elif el.tag == "way":
            if {t.get("k"): t.get("v") for t in el.findall("tag")}.get("role") in roads:
                keep.update(n.get("ref") for n in el.findall("nd"))
            el.clear()
    return numpy.array([nodes[r] for r in keep if r in nodes], dtype=float).reshape(-1, 3)


#: a road node this near a back station is the road AT the building's base
#: (``run`` reads ``[building_pad] split_level_road_reach_m`` over it)
ROAD_AT_BASE_M = 6.0


def _road_at(roads, lon, lat):
    """The z of the groundside road node nearest (lon, lat) within
    :data:`ROAD_AT_BASE_M`, or ``None``."""
    if roads is None or not len(roads):
        return None
    kx = M_PER_DEG * math.cos(math.radians(lat))
    d = numpy.hypot((roads[:, 0] - lon) * kx, (roads[:, 1] - lat) * M_PER_DEG)
    j = int(numpy.argmin(d))
    return float(roads[j, 2]) if d[j] <= ROAD_AT_BASE_M else None


def _behind(closed, opened):
    """The ``closed`` (lat, lon) sides parallel (within 45 degrees) to an
    ``opened`` one: the sides behind the building; all of ``closed`` when
    it has no open side."""
    def axis(sd):
        (la0, lo0), (la1, lo1) = sd[0], sd[-1]
        kx = math.cos(math.radians(la0))
        d = ((lo1 - lo0) * kx, la1 - la0)
        n = math.hypot(*d) or 1.0
        return d[0] / n, d[1] / n
    if not opened:
        return list(closed)
    ax = [axis(o) for o in opened]
    return [c for c in closed
            if any(abs(axis(c)[0] * a[0] + axis(c)[1] * a[1]) >= math.sqrt(0.5) for a in ax)]


def body_offsets_y(plans):
    """{written body resource: its authored y offset} over the plans' split
    bodies: a body row's drawn zero is the AUTHORED point the cut moved to
    its origin, so the object's own zero is the row's minus this
    (``authored_landing.body_zero``)."""
    return {b["new_resource"]: float((b.get("authored_offset") or [0.0, 0.0])[1])
            for plan in plans for s in plan.get("splits", []) for b in s.get("bodies", [])
            if b.get("new_resource")}


def check_split(rec, drawn, tol, lifts=None, roads=None):
    """One split-level building's row (module docstring); ``lifts`` is
    :func:`body_offsets_y` (a split body's zero is its authored point)."""
    lifts = lifts or {}
    stems = {stem(r) for r in rec.get("resources", [])}
    rows = [i for i, p in enumerate(drawn.rows) if stem(p.def_path) in stems]
    lon, lat = rec["anchor_longitude_latitude"]
    kx = M_PER_DEG * math.cos(math.radians(lat))
    # the building's own placements: a pack places one resource many times,
    # so only the rows anchored within the building's reach (its open sides'
    # farthest point from its floor) are its own
    reach = max([math.hypot((q[1] - lon) * kx, (q[0] - lat) * M_PER_DEG)
                 for sd in rec.get("open_sides_ll", []) for q in sd] or [300.0])
    rows = [i for i in rows if math.hypot((drawn.rows[i].lon - lon) * kx,
                                          (drawn.rows[i].lat - lat) * M_PER_DEG) <= reach]
    # ... and of those, the ONE frame (anchor) whose vertices centre nearest
    # its floor: the split-level family is one placement frame
    if rows:
        def centre_d(i):
            v = drawn.vertices(i)
            if v is None:
                return math.inf
            return math.hypot((float(numpy.mean(v[0])) - lon) * kx,
                              (float(numpy.mean(v[1])) - lat) * M_PER_DEG)
        best = drawn.rows[min(rows, key=centre_d)]
        rows = [i for i in rows if abs(drawn.rows[i].lon - best.lon) * kx < 0.05
                and abs(drawn.rows[i].lat - best.lat) * M_PER_DEG < 0.05]
    y_lo = float(rec.get("plate_y_m") or 0.0)
    y_up = y_lo + float(rec.get("floor_below_rim_m") or 0.0)
    out = {"site": f"split_level {rec.get('floor_ref')}", "lat": round(lat, 6),
           "lon": round(lon, 6), "resources": sorted(stems), "rows": len(rows),
           "fails": [], "role": "SPLIT"}
    if not rows:
        out["fails"].append("no written row of the building")
        out["verdict"] = "FAIL"
        return out
    zeros = [_base(drawn, i) - lifts.get(drawn.rows[i].def_path, 0.0) for i in rows]
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
    # THE BACK IS CUT DOWN (owner sim read 2026-11-05T23:55Z): the drawn
    # ground 1 m outside the tall side(s) BEHIND the building -- across from
    # its airside face (parallel to an open side) -- stands at the lower
    # floor; a tall side running up the slope between them reads both
    behind = _behind(rec.get("closed_sides_ll", []), rec.get("open_sides_ll", []))
    # ... or, where a groundside road runs along the base, at the ROAD's
    # height there (owner 2026-11-06T02:40Z: "at SBSP the road at the base
    # of the building on the groundside is sloping up")
    # -- the pit's own reading, per side: a side with a road at its base is
    # judged at its road stations only (past the road's end it is the
    # governed ground, no bar); a side with none, at the lower floor
    back, ref, n_road = [], [], 0
    for sd in behind:
        st = _outside(sd, (lon, lat), 1.0)
        at = [_road_at(roads, x, y) for x, y in st]
        roaded = any(r is not None for r in at)
        for (x, y), road in zip(st, at, strict=True):
            g = mesh_z(drawn.mesh, x, y)
            if math.isnan(g) or (roaded and road is None):
                continue
            back.append(g)
            ref.append(z0 + y_lo if road is None else road)
            n_road += road is not None
    out["back_on_road"] = n_road
    if back:
        d_b = [g - r for g, r in zip(back, ref, strict=True)]
        out["back_ground_median"] = round(float(numpy.median(back)), 2)
        out["delta_back_max"] = round(max(d_b, key=abs), 2)
        if abs(out["delta_back_max"]) > tol:
            out["fails"].append(f"back ground - lower floor / road {out['delta_back_max']:+.2f}"
                                f" > {tol}")
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
        # ``build_airport.py --tile --pack-copy DIR``: the lane's own pack
        args.pack_copy = ((res.get("engine_cache_redirects") or {})
                          .get("pack_copy") or {}).get("dir")
    else:
        lat, lon = int(args.tile[:3]), int(args.tile[3:])
        block = f"{lat // 10 * 10:+03d}{lon // 10 * 10:+04d}"
        patch_dir = os.path.join(args.patches, block, args.tile)
    return patch_dir, tile_dsfs


def drawn_tile_dsfs(custom_scenery, tiles):
    """The base-mesh DSF X-Plane draws on each of ``tiles`` (``+LL+LLL``)
    from ``custom_scenery``'s load order (``O4_Mesh_Order.drawn_mesh_dsf``)."""
    import O4_Mesh_Order
    found = (O4_Mesh_Order.drawn_mesh_dsf(custom_scenery, int(t[:3]), int(t[3:]))
             for t in sorted(tiles))
    return [f for f in found if f]


def pack_is_build_product(args, pack_root):
    """Is the written pack the one these products drew?  The owner's
    products (``--tile``) and a harness build's ``--pack-copy`` are; a
    harness tag WITHOUT a copy stood its pack writes down, so the pack read
    is the owner's install as last written -- not this build's objects."""
    if not getattr(args, "tag", None) or getattr(args, "plan", None):
        return True
    copy = getattr(args, "pack_copy", None)
    return bool(copy) and os.path.realpath(pack_root).startswith(
        os.path.realpath(copy) + os.sep)


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
    if getattr(args, "plan", None):
        # a pack COPY's written plan (``v2_rebake_replay.py plan --write-pack
        # COPY --plan-out PLAN``): its ``pack_root`` / ``dsf_path`` name the copy
        plans[tile] = json.load(open(args.plan, encoding="utf-8"))
    if tile not in plans:
        sys.exit(f"no o4_v2_placement_{args.icao}.json for {tile} under "
                 f"{os.path.dirname(patch_dir)}")
    pack_root = plans[tile]["pack_root"]
    copy = getattr(args, "pack_copy", None)
    if copy and not os.path.realpath(pack_root).startswith(
            os.path.realpath(copy) + os.sep):
        sys.exit(f"the placement plan for {tile} names {pack_root}, not the "
                 f"build's pack copy under {copy}: the object stage did not "
                 f"write the copy (read its [v2 placement] lines)")
    if not tile_dsfs:
        # THE LOAD ORDER'S MESH, never a folder name: the owner's tiles now
        # live in the World pack, and a ``zOrtho4XP_<tile>`` beside the
        # pack (when one is left) may be disabled or hidden (#1903)
        tile_dsfs = drawn_tile_dsfs(os.path.dirname(pack_root), plans)
    if not tile_dsfs:
        sys.exit(f"no base-mesh DSF is drawn on {sorted(plans)} in the load "
                 f"order of {os.path.dirname(pack_root)}")
    bbox = patch_bbox(patch, args.margin)
    from auto_patch_v2.airport.dsf_write import pristine_dsf_path
    written, pristine = [], {}
    with tempfile.TemporaryDirectory() as tmp:
        for t, plan in sorted(plans.items()):
            written += dump_dsf(plan["dsf_path"], tmp).placements
            pristine[t] = dump_dsf(pristine_dsf_path(plan["dsf_path"]), tmp)
    mesh, tile_dsfs = _sampler(args, tile_dsfs, bbox)
    claims = read_claims(sidecar, tile, plans, pristine)
    drawn = Drawn(written, pack_root, mesh)
    rows = [check_site(s, drawn, claims, args.radius, args.tol)
            for s in read_sites(patch, sidecar, args.radius)]
    lifts = body_offsets_y(plans.values())
    roads = road_nodes(patch, args.icao)
    global ROAD_AT_BASE_M
    from auto_patch_v2.law import Law
    ROAD_AT_BASE_M = float(getattr(Law.for_airport(args.icao).tables.structures.building_pad,
                                   "split_level_road_reach_m", 0.0) or ROAD_AT_BASE_M)
    rows += [check_split(r, drawn, args.tol, lifts, roads)
             for r in sidecar.get("basin_facilities", []) if r.get("kind") == "split_level"]
    # #2042: every graded facade's feet on the drawn ground
    import drawn_facade
    with tempfile.TemporaryDirectory() as tmp:
        rows += drawn_facade.check([p["dsf_path"] for _t, p in sorted(plans.items())],
                                   pack_root, mesh, tmp)
    step = float(Law.for_airport(args.icao).tables.structures.bridge.abutment_sample_step_m)
    rows += [check_stack(r, drawn, claims, args.tol, step, faces=_stack_faces(patch, r))
             for r in sidecar.get("object_floors", []) if r.get("stack")]
    return {"icao": args.icao, "tile": tile, "pack_root": pack_root,
            "pack_is_build_product": pack_is_build_product(args, pack_root),
            "tile_dsfs": tile_dsfs, "tol_m": args.tol, "radius_m": args.radius,
            "claims": [dataclasses.asdict(c) for c in claims], "sites": rows}


def _sampler(args, tile_dsfs, bbox):
    """The drawn mesh: the caller's sampler, a built ``.mesh`` or the tile
    DSF(s) streamed."""
    if getattr(args, "sampler", None) is not None:
        # the caller's sampler over the same drawn DSF(s) (the harness
        # drawn gate streams the tile once for every layer it reads)
        mesh, tile_dsfs = args.sampler, list(args.sampler_dsfs)
    elif getattr(args, "mesh", None):
        # the tile's built ``Data+XX+YYY.mesh`` -- the triangles the tile DSF
        # is written from -- where the build ran the geometry half only
        mesh = MeshElevationSampler(args.mesh, bbox)
        tile_dsfs = [args.mesh]
    else:
        mesh = drawn_mesh([stream_dsf(f) for f in tile_dsfs], bbox)
    return mesh, tile_dsfs


def _stack_faces(patch, rec, dem=None, standoff=0.0):
    """The patch's faces about one stack (``patch_faces.PatchFaces``)."""
    from patch_faces import PatchFaces
    fl = rec["stack"]["floor_line"]
    return PatchFaces(patch, fl[len(fl) // 2], 400.0, dem=dem, standoff=standoff)


def run_predict(args):
    """``--predict PATCH`` (spec interchange-levels v2 §8.2): the STACK rows
    of :func:`check_stack` over the emitted patch itself -- a point reads
    the face covering it, else the build's DEM (UNCOVERED).  The members'
    rows are the written pack copy's (``--plan``, ``v2_rebake_replay.py
    plan --write-pack COPY --plan-out PLAN``), else the sidecar's frame."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import snap_margin_m
    patch = args.predict
    sidecar = json.load(open(patch + ".axes.json", encoding="utf-8"))
    law = Law.for_airport(args.icao)
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    standoff = (float(law.tables.zones.adjacent_ground.groundside_cutback_m)
                + snap_margin_m(law))
    written, pack_root = [], None
    if getattr(args, "plan", None):
        plan = json.load(open(args.plan, encoding="utf-8"))
        pack_root = plan["pack_root"]
        with tempfile.TemporaryDirectory() as tmp:
            written = dump_dsf(plan["dsf_path"], tmp).placements
    rows = []
    for r in sidecar.get("object_floors", []):
        if not r.get("stack"):
            continue
        faces = _stack_faces(patch, r, standoff=standoff)
        drawn = Drawn(written, pack_root, faces) if written else None
        rows.append(check_stack(r, drawn, [], args.tol, step, faces=faces, predict=True,
                                standoff=standoff))
    return {"icao": args.icao, "tile": "PREDICTED", "pack_root": pack_root or "(sidecar frame)",
            "pack_is_build_product": True, "tile_dsfs": [patch], "tol_m": args.tol,
            "radius_m": args.radius, "claims": [], "sites": rows, "predicted": True}


def print_report(rep):
    print(f"DRAWN CHECK {rep['icao']} {rep['tile']}  pack {rep['pack_root']}")
    print(f"  mesh {', '.join(rep['tile_dsfs'])}")
    if not rep.get("pack_is_build_product", True):
        print("  WARNING: the pack read is the owner's install as last written, "
              "NOT this build's objects (no --pack-copy): the object rows below "
              "do not measure this build")
    for r in rep["sites"]:
        if r.get("role") == "FACADE":
            print(f"{r['verdict']:4s} {r['site']} @{r['lat']},{r['lon']} plane "
                  f"{r['plane']:.2f} (first wall {r['anchor'][0]},{r['anchor'][1]}) "
                  f"worst foot {r['delta']:+.2f} at {r['worst'][0]},{r['worst'][1]}")
            for f in r["fails"]:
                print(f"       FAIL {f}")
            continue
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
        if r.get("role") == "STACK":
            print(f"{r['verdict']:4s} {r['site']} [{r.get('mode', 'DRAWN')}] @{r['lat']},"
                  f"{r['lon']} D1 spread {r.get('d1_spread')} walls bottom "
                  f"{r.get('walls_bottom')} top {r.get('walls_top')}; D2 worst "
                  f"{r.get('d2_worst')} (under all decks {r.get('d2_under_all_decks')}); "
                  f"D5 {r.get('d5_range')}; D6 {r.get('d6_range')}")
            for e in r.get("d3", []):
                print(f"       D3 {e['deck']}#{e['piece']} end {e['end']}: plate top "
                      f"{e['plate_top']} - road {e['road']} - ground {e['ground']}")
            for e in r.get("d4", []):
                print(f"       D4 {e['deck']}#{e['piece']}: least clearance {e['least']:+.2f} "
                      f"at {e.get('at')}")
            if r.get("samples"):
                print("       samples " + ", ".join(
                    f"{k} {r.get('uncovered_n', {}).get(k, 0)}/{n} uncovered "
                    f"({r.get('no_face', {}).get(k, 0)} on no face)"
                    for k, n in sorted(r["samples"].items())))
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
    n = sum(r["verdict"] in ("FAIL", "INCOMPLETE") for r in rep["sites"])
    print(f"SUMMARY {rep['icao']} {rep['tile']}: {len(rep['sites'])} sites, "
          f"{sum(r['verdict'] == 'PASS' for r in rep['sites'])} PASS, {n} FAIL")
    return n


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if any(a == "--pack" or a.startswith("--pack=") for a in argv):
        # the per-site reading of the installed pack (``tools/drawn_site.py``)
        import drawn_site
        return drawn_site.main(argv)
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
    ap.add_argument("--plan", help="the written o4_v2_placement_<ICAO>.json of a pack copy")
    ap.add_argument("--mesh", help="the tile's Data+XX+YYY.mesh in place of its DSF")
    ap.add_argument("--predict", metavar="PATCH",
                    help="PREDICTED stack rows on an emitted patch (replay --emit): faces "
                         "else the DEM, coverage bar; --plan for the written rows")
    ap.add_argument("--json", help="write the report here")
    ap.add_argument("--against", help="baseline --json: list moved sites")
    args = ap.parse_args(argv)
    if not (args.tile or args.tag or args.predict):
        ap.error("--tile, --tag or --predict is required")
    if args.patches is None:
        import O4_File_Names as FNAMES
        args.patches = FNAMES.Patch_dir
    rep = run_predict(args) if args.predict else run(args)
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
