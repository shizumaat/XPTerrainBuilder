#!/usr/bin/env python3
"""A PLACE ON A LAST-STAGE ARM AGAINST ITS BASE (spec §53): the question an
owner's coordinate asks of a ``--late-from`` arm, read off the two
``--solved-out`` pickles ``v2_late_read.py`` already loads.

    venv/bin/python tools/v2_late_read.py BASE/solved.pkl ARM/solved.pkl \
        --site NAME LAT LON [TO_LAT TO_LON] [--site ...] [--half M] [--step M]

Per site:

  POINT     the face holding the point on each arm (none = the ground the
            patch leaves to the mesh), its level there and the DEM.
  PIECE     when the arm face is a gap piece: its faces, area and levels;
            its WELDED neighbours (a shared map edge: shared length and the
            levels along it), the rim no face shares, and its STAND-OFF
            neighbours (``v2_late_read.standoff_pairs``: the level difference
            across the stand-off and whether the pair steps).
  SECTIONS  both solved surfaces and the DEM sampled every ``--step`` along
            two lines through the point — toward ``TO`` and across it, or
            west-east and south-north — with the worst slope INSIDE a face
            and the worst level difference between two successive faces
            (across whatever faceless ground lies between them), per arm.

It MEASURES NO LAW and derives no class: faces, levels and pairs are the
maps' own.  A point no triangle of its face holds reads no level, never an
extrapolated one.  Promoted from lane gaps3's scratch ``site_read.py`` on
its second use (lane gaps4, 2026-10-06)."""
from __future__ import annotations

import collections
import math

from v2_late_read import Late, _name, _poly, standoff_pairs

#: barycentric slack: a sample this far outside every triangle has no level
_OUTSIDE = -0.05


def _piece(ref: object) -> str:
    return str(ref).split("#")[0]


class Surface:
    """One solved map as a surface to sample: the face at a point and the
    level on that face's own triangulation."""

    def __init__(self, pm, z) -> None:
        from shapely.strtree import STRtree
        self.pm, self.z = pm, z
        pairs = [(f, _poly(pm, f)) for f in pm.faces.values()]
        self.faces = [f for f, p in pairs if p is not None]
        self.polys = [p for _f, p in pairs if p is not None]
        self.tree = STRtree(self.polys)
        self._tris: dict = {}

    def face_at(self, xy):
        """The face covering ``xy`` (the smallest, where faces nest), or None."""
        from shapely.geometry import Point
        p = Point(xy)
        hit = [int(i) for i in self.tree.query(p) if self.polys[int(i)].covers(p)]
        if not hit:
            return None
        return self.faces[min(hit, key=lambda i: self.polys[i].area)]

    def z_at(self, xy):
        """``(face, level)``; the level is None off every triangle."""
        from auto_patch_v2.solve.rows import _face_triangles
        f = self.face_at(xy)
        if f is None:
            return None, None
        tris = self._tris.get(f.id)
        if tris is None:
            tris = self._tris[f.id] = _face_triangles(self.pm, f.id)
        V, (x, y) = self.pm.vertices, xy
        best = None
        for a, b, c in tris:
            (x1, y1), (x2, y2), (x3, y3) = V[a].xy, V[b].xy, V[c].xy
            d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
            if abs(d) < 1e-12:
                continue
            l1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / d
            l2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / d
            l3 = 1.0 - l1 - l2
            m = min(l1, l2, l3)
            if best is None or m > best[0]:
                best = (m, l1 * self.z[a] + l2 * self.z[b] + l3 * self.z[c])
            if m >= -1e-9:
                break
        if best is None or best[0] < _OUTSIDE:
            return f, None
        return f, float(best[1])


def read_piece(L: Late, piece: str, pairs: dict, out=print) -> dict:
    """The gap piece ``piece`` on the arm: size, levels, welded and
    stand-off neighbours."""
    from auto_patch_v2.model.planar import face_edge_ids, face_vertex_set
    pm, za, V = L.pa, L.za, L.pa.vertices
    faces = [f for f in pm.faces.values() if _piece(f.ref) == piece]
    ids = {f.id for f in faces}
    vs: set = set()
    area = 0.0
    for f in faces:
        vs |= {int(v) for v in face_vertex_set(pm, f)}
        p = _poly(pm, f)
        area += p.area if p is not None else 0.0
    zz = [float(za[v]) for v in vs]
    out(f"  PIECE {piece}: role {faces[0].role}, side {getattr(faces[0], 'side', '?')}, "
        f"{len(faces)} face(s), {area:,.0f} m2, {len(vs)} vertices "
        f"({sum(1 for v in vs if v not in L.fixed)} unknown), "
        f"levels {min(zz):.2f}..{max(zz):.2f}")
    welded: dict = collections.defaultdict(lambda: [0.0, []])
    for f in faces:
        for e in face_edge_ids(f):
            ed = pm.edges[e]
            other = [x for x in (ed.left_face, ed.right_face) if x not in ids]
            if not other and ed.left_face in ids and ed.right_face in ids:
                continue                     # an edge inside the piece
            o = other[0] if other else None
            name = "(no face: the mesh's own ground)" if o is None else _name(pm.faces[o])
            w = welded[name]
            w[0] += math.dist(V[ed.a].xy, V[ed.b].xy)
            w[1] += [float(za[ed.a]), float(za[ed.b])]
    out("  WELDED neighbours (a shared map edge): shared m; arm levels along it")
    res_w = {}
    for name, (m, zs) in sorted(welded.items(), key=lambda kv: -kv[1][0]):
        out(f"    {name}: {m:,.1f} m; {min(zs):.2f}..{max(zs):.2f}")
        res_w[name] = {"shared_m": m, "z": (min(zs), max(zs))}
    res_s = {}
    if pairs:
        cap, step = pairs["cap"], pairs["step"]
        mine = {nb: w for (ref, nb), w in pairs["worst"].items() if ref == piece}
        out(f"  STAND-OFF neighbours ({pairs['stand']:.2f} m, cap {100 * cap:.0f} %): "
            f"worst level difference, distance, where; STEPS = beyond cap x distance")
        for nb, w in sorted(mine.items(), key=lambda kv: -abs(kv[1][3] - kv[1][4])):
            dz = abs(w[3] - w[4])
            out(f"    {nb}: {dz:.2f} m (piece {w[3]:.2f} vs {w[4]:.2f}, {w[1]:.2f} m apart) "
                f"at {w[2]}{'  STEPS' if w[0] > step else ''}")
            res_s[nb] = {"dz": dz, "apart_m": w[1], "at": w[2], "piece_z": w[3],
                         "neighbour_z": w[4], "steps": bool(w[0] > step)}
    return {"piece": piece, "faces": len(faces), "area_m2": area,
            "z": (min(zz), max(zz)), "welded": res_w, "standoff": res_s}


def read_section(base: Surface, arm: Surface, dem, xy, u, half: float, step: float,
                 label: str, out=print) -> dict:
    """Both surfaces and the DEM along the line through ``xy`` with unit
    direction ``u``; the worst in-face slope and face-change step per arm."""
    out(f"  SECTION {label}: s m | base face, level | arm face, level | DEM")
    n = int(round(half / step))
    prev: dict = {}
    slope = {"base": (0.0, None), "arm": (0.0, None)}
    jump = {"base": (0.0, None), "arm": (0.0, None)}
    rows = []
    for i in range(-n, n + 1):
        s = i * step
        p = (xy[0] + u[0] * s, xy[1] + u[1] * s)
        cells = [f"{s:+7.1f}"]
        row = {"s": s, "dem": float(dem.z(*p))}
        for key, S in (("base", base), ("arm", arm)):
            f, z = S.z_at(p)
            nm = "-" if f is None else _name(f)
            cells.append(f"{nm[:36]:36s} {'' if z is None else format(z, '7.2f'):7s}")
            row[key] = (nm, z)
            if z is None:
                continue                     # no level here: the last one stands
            if key in prev:
                pz, pn, ps = prev[key]
                if pn == nm and abs(z - pz) / (s - ps) > slope[key][0]:
                    slope[key] = (abs(z - pz) / (s - ps), (s, nm))
                if pn != nm and abs(z - pz) > jump[key][0]:
                    jump[key] = (abs(z - pz), (s, pn, nm, s - ps))
            prev[key] = (z, nm, s)
        cells.append(f"{row['dem']:7.2f}")
        out("    " + " | ".join(cells))
        rows.append(row)
    for key in ("base", "arm"):
        g, at = slope[key]
        j, jat = jump[key]
        out(f"    {key}: worst slope inside a face {100 * g:.1f} %"
            f"{'' if at is None else f' at s={at[0]:+.1f} ({at[1]})'}; worst level "
            f"difference between two faces {j:.2f} m" + ("" if jat is None else
            f" at s={jat[0]:+.1f} ({jat[1]} -> {jat[2]}, {jat[3]:g} m apart)"))
    return {"label": label, "rows": rows,
            "worst_slope": {k: v[0] for k, v in slope.items()},
            "worst_face_change": {k: v[0] for k, v in jump.items()}}


def read_site(L: Late, base: Surface, arm: Surface, pairs: dict, name: str,
              lat: float, lon: float, to: "tuple[float, float] | None",
              half: float, step: float, out=print) -> dict:
    """One site: POINT, PIECE, SECTIONS."""
    from auto_patch_v2.model.planar import is_gap_ref
    xy = L.to_xy(lon, lat)
    res: dict = {"name": name, "lat": lat, "lon": lon, "dem": float(L.dem.z(*xy))}
    out(f"\n=== SITE {name} {lat:.7f}, {lon:.7f}  (x {xy[0]:.1f}, y {xy[1]:.1f})  "
        f"DEM {res['dem']:.2f}")
    for key, S in (("base", base), ("arm", arm)):
        f, z = S.z_at(xy)
        res[key] = None if f is None else {"face": _name(f), "id": f.id, "z": z,
                                           "side": getattr(f, "side", None)}
        out(f"  POINT on the {key}: " + (
            "no face (the mesh's own ground)" if f is None else
            f"{_name(f)} (face {f.id}, side {getattr(f, 'side', '?')}), level "
            f"{'none' if z is None else format(z, '.2f')}"))
    fa = arm.face_at(xy)
    if fa is not None and is_gap_ref(fa.ref):
        res["piece"] = read_piece(L, _piece(fa.ref), pairs, out)
    if to is not None:
        tx = L.to_xy(to[1], to[0])
        d = math.dist(xy, tx)
        u = ((tx[0] - xy[0]) / d, (tx[1] - xy[1]) / d)
        lines = [(f"toward {to[0]:.7f}, {to[1]:.7f} ({d:.1f} m off)", u),
                 ("across that line", (-u[1], u[0]))]
    else:
        lines = [("west -> east", (1.0, 0.0)), ("south -> north", (0.0, 1.0))]
    res["sections"] = [read_section(base, arm, L.dem, xy, u, half, step, label, out)
                       for label, u in lines]
    return res


def read_sites(L: Late, sites: list, half: float, step: float, out=print) -> dict:
    """Every ``--site NAME LAT LON [TO_LAT TO_LON]`` of the command line."""
    for s in sites:
        if len(s) not in (3, 5):
            raise SystemExit(f"--site takes NAME LAT LON [TO_LAT TO_LON], got {s}")
    base, arm = Surface(L.pb, L.zb), Surface(L.pa, L.za)
    pairs = standoff_pairs(L)
    return {s[0]: read_site(L, base, arm, pairs, s[0], float(s[1]), float(s[2]),
                            (float(s[3]), float(s[4])) if len(s) == 5 else None,
                            half, step, out)
            for s in sites}
