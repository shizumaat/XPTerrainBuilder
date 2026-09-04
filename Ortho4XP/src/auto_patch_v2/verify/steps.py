"""The cross-shape and step families over the emitted rings (v1
``_check_cross_shape_proximity`` / ``_check_vertex_to_edge_step`` /
``_check_edge_midpoint_step`` / ``_check_stacked_nodes``):

* ``cross_shape``: vertices of DIFFERENT rings within the proximity
  knob (``identity.min_distinct_spacing_m``) at the stricter cap
  (+ rounding); a shared vertex must agree (v2: one node per
  coordinate, so it does by construction);
* ``vertex_to_edge_step`` / ``mid_edge_step``: a vertex (or an edge
  midpoint) against the nearest edge of another ring within the contact
  tolerance, step over ``materiality.step_m``; airside↔groundside and
  road↔non-road pairs are designed separations and skip; pad↔pad steps
  are the registered exemption (06-20);
* ``stacked_nodes``: distinct node ids at one coordinate with
  disagreeing values (impossible by construction: one id per key).
"""
from __future__ import annotations

import math

from ..constraints.roads import road_family_roles
from ..law.tables import role_cap
from .frame import Patch, Row, Shape, pair_side, row

__all__ = ["cross_shape", "vertex_to_edge_step", "mid_edge_step", "stacked_nodes"]


def _designed_separation(p: Patch, ra: str, rb: str) -> bool:
    roads = set(road_family_roles(p.law))
    if (ra in roads) != (rb in roads):
        return True
    return (p.side(ra) == "groundside") != (p.side(rb) == "groundside")


def _grid(items, cell: float):
    g: dict[tuple[int, int], list[int]] = {}
    for i, (x, y) in enumerate(items):
        g.setdefault((int(math.floor(x / cell)), int(math.floor(y / cell))), []).append(i)
    return g


def cross_shape(p: Patch) -> list[Row]:
    law = p.law
    prox = law.tables.emit.identity.min_distinct_spacing_m
    noise = law.tables.emit.instrument.rounding_noise_m
    verts = [(sh, k) for sh in p.shapes for k in range(len(sh.ids))]
    g = _grid([sh.xy[k] for sh, k in verts], max(prox, 0.5))
    cell = max(prox, 0.5)
    out: list[Row] = []
    for i, (sa, ka) in enumerate(verts):
        xa, ya = sa.xy[ka]
        cx, cy = int(math.floor(xa / cell)), int(math.floor(ya / cell))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in g.get((cx + dx, cy + dy), ()):
                    if j <= i:
                        continue
                    sb, kb = verts[j]
                    if sb.key == sa.key:
                        continue
                    xb, yb = sb.xy[kb]
                    d = math.hypot(xa - xb, ya - yb)
                    if d > prox or _designed_separation(p, sa.role, sb.role):
                        continue
                    ca, cb = p.cap(sa), p.cap(sb)
                    if ca is None or cb is None:
                        continue
                    de = abs(sa.z[ka] - sb.z[kb])
                    if sa.ids[ka] == sb.ids[kb] or d < 0.05:
                        if de <= 0.15:
                            continue
                        out.append(row("cross_shape", (sa.role, sb.role),
                                       pair_side(p, sa.role, sb.role), de, float("inf"),
                                       None, d, (xa, ya), (xb, yb), sa.key, sb.key))
                        continue
                    cap = min(ca, cb)
                    if de <= cap * d + noise:
                        continue
                    out.append(row("cross_shape", (sa.role, sb.role),
                                   pair_side(p, sa.role, sb.role), de, 100 * de / d,
                                   100 * cap, d, (xa, ya), (xb, yb), sa.key, sb.key))
    return out


def _edges(p: Patch):
    out = []
    for sh in p.shapes:
        n = len(sh.ids)
        for i in range(n):
            j = (i + 1) % n
            out.append((sh, sh.xy[i], sh.xy[j], sh.z[i], sh.z[j]))
    return out


def _step_rows(p: Patch, family: str, probes, edges, search: float,
               ctol: float, step_m: float) -> list[Row]:
    exempt_pad = p.law.tables.structures.building_pad.step_exemption_pad_to_pad
    cell = max(search, 1.0)
    g: dict[tuple[int, int], list[int]] = {}
    for k, (sh, a, b, _za, _zb) in enumerate(edges):
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        for gx in range(int(math.floor(x0 / cell)) - 1, int(math.floor(x1 / cell)) + 2):
            for gy in range(int(math.floor(y0 / cell)) - 1, int(math.floor(y1 / cell)) + 2):
                g.setdefault((gx, gy), []).append(k)
    out: list[Row] = []
    for (sv, (x, y), z) in probes:
        if p.cap(sv) is None:
            continue
        cx, cy = int(math.floor(x / cell)), int(math.floor(y / cell))
        best = None
        for k in g.get((cx, cy), ()):
            se, a, b, za, zb = edges[k]
            if se.key == sv.key or p.cap(se) is None:
                continue
            if _designed_separation(p, sv.role, se.role):
                continue
            if exempt_pad and p.is_rigid(sv.role) and p.is_rigid(se.role):
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            l2 = dx * dx + dy * dy
            t = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / l2))
            px, py = a[0] + t * dx, a[1] + t * dy
            d2 = (x - px) ** 2 + (y - py) ** 2
            if best is None or d2 < best[0]:
                best = (d2, k, t, px, py)
        if best is None or best[0] > ctol * ctol:
            continue
        _d2, k, t, px, py = best
        se, a, b, za, zb = edges[k]
        proj = za + t * (zb - za)
        step = abs(z - proj)
        if step > step_m + 1e-5:
            out.append(row(family, (sv.role, se.role), pair_side(p, sv.role, se.role),
                           step, None, None, math.sqrt(_d2), (x, y), (px, py),
                           sv.key, se.key))
    return out


def vertex_to_edge_step(p: Patch) -> list[Row]:
    ins = p.law.tables.emit.instrument
    probes = [(sh, sh.xy[k], sh.z[k]) for sh in p.shapes for k in range(len(sh.ids))]
    return _step_rows(p, "vertex_to_edge_step", probes, _edges(p), ins.edge_search_m,
                      ins.step_contact_tol_m, p.law.tables.emit.materiality.step_m)


def mid_edge_step(p: Patch) -> list[Row]:
    ins = p.law.tables.emit.instrument
    probes = [(sh, (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1])), 0.5 * (za + zb))
              for sh, a, b, za, zb in _edges(p)]
    return _step_rows(p, "mid_edge_step", probes, _edges(p), ins.edge_search_m,
                      ins.step_contact_tol_m, p.law.tables.emit.materiality.step_m)


def stacked_nodes(p: Patch) -> list[Row]:
    """Distinct ids within 5 cm with values apart by > 5 cm."""
    ids = list(p.xy)
    g = _grid([p.xy[v] for v in ids], 0.05)
    out: list[Row] = []
    for i, v in enumerate(ids):
        x, y = p.xy[v]
        cx, cy = int(math.floor(x / 0.05)), int(math.floor(y / 0.05))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in g.get((cx + dx, cy + dy), ()):
                    if j <= i:
                        continue
                    u = ids[j]
                    if math.hypot(p.xy[u][0] - x, p.xy[u][1] - y) > 0.05:
                        continue
                    de = abs(p.z[u] - p.z[v])
                    if de > 0.05:
                        out.append(row("stacked_nodes", ("?", "?"), "unknown", de,
                                       None, None, 0.0, (x, y), p.xy[u], v, u))
    return out
