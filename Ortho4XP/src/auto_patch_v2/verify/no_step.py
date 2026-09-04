"""``airside_no_step`` (RULINGS 2026-08-27) over the emitted rings:
§1.1 the PUBLISHED direct-distance pairs (``airside_no_step_edges``,
budget + the worse endpoint's instrument envelope — the v1
``_check_published_law_edges``) and §1.2 the rate of change along every
airside ring sequence (wrap triples included) at ``strip.arc_rate`` with
the rate reader's blind spot ``q·(1/dp + 1/dn)`` (``_rate_reader_blind_spot``,
``q`` = the coarse quantum)."""
from __future__ import annotations

import math

from ..constraints.no_step import no_step_roles
from .frame import Patch, Row, noise_m, row

__all__ = ["no_step_direct", "no_step_rate", "rate_breaches"]


def no_step_direct(p: Patch) -> list[Row]:
    law = p.law
    tol = law.tables.emit.identity.min_distinct_spacing_m
    cell = max(1.0, tol * 2.0)
    grid: dict[tuple[int, int], list[int]] = {}
    role_of: dict[int, str] = {}
    for sh in p.shapes:
        for vid in sh.ids:
            role_of.setdefault(vid, sh.role)
    for vid, (x, y) in p.xy.items():
        grid.setdefault((int(x // cell), int(y // cell)), []).append(vid)

    def find(x: float, y: float) -> int | None:
        best = None
        cx, cy = int(x // cell), int(y // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for vid in grid.get((cx + dx, cy + dy), ()):
                    px, py = p.xy[vid]
                    d = math.hypot(px - x, py - y)
                    if d <= tol and (best is None or d < best[0]):
                        best = (d, vid)
        return None if best is None else best[1]

    out: list[Row] = []
    for rec in p.publication.get("airside_no_step_edges") or []:
        ax, ay = p.to_m(float(rec["a"][0]), float(rec["a"][1]))
        bx, by = p.to_m(float(rec["b"][0]), float(rec["b"][1]))
        ka, kb = find(ax, ay), find(bx, by)
        if ka is None or kb is None:
            continue
        budget = float(rec["budget_m"])
        dz = abs(p.z[kb] - p.z[ka])
        ra, rb = role_of.get(ka, "?"), role_of.get(kb, "?")
        noise = max(noise_m(law, r) for r in (ra, rb) if r != "?") \
            if (ra != "?" or rb != "?") else law.tables.emit.instrument.rounding_noise_m
        if dz - budget <= noise:
            continue
        dist = math.hypot(bx - ax, by - ay)
        out.append(row("airside_no_step", (ra, rb),
                       "airside" if p.side(ra) == p.side(rb) == "airside" else "mixed",
                       dz, 100 * dz / dist if dist > 1e-9 else 0.0,
                       100 * budget / dist if dist > 1e-9 else None, dist,
                       (ax, ay), (bx, by), ka, kb))
    return out


def rate_breaches(pts, zs, closed: bool, rate: float, q: float):
    """``[(k_prev, k, k_next, change, allowed, dp, dn)]`` over a chain."""
    idx = list(range(len(pts)))
    if closed:
        idx = idx + [0, 1]
    s = [0.0]
    for k in range(1, len(idx)):
        (xa, ya), (xb, yb) = pts[idx[k - 1]], pts[idx[k]]
        s.append(s[-1] + math.hypot(xb - xa, yb - ya))
    out = []
    for k in range(1, len(idx) - 1):
        a, b, c = idx[k - 1], idx[k], idx[k + 1]
        if len({a, b, c}) < 3:
            continue
        dp, dn = s[k] - s[k - 1], s[k + 1] - s[k]
        if dp < 1e-6 or dn < 1e-6:
            continue
        change = abs((zs[c] - zs[b]) / dn - (zs[b] - zs[a]) / dp)
        allowed = rate * 0.5 * (dp + dn)
        if change - allowed <= q * (1.0 / dp + 1.0 / dn):
            continue
        out.append((a, b, c, change, allowed, dp, dn))
    return out


def no_step_rate(p: Patch) -> list[Row]:
    law = p.law
    r = law.ruleset.strip.arc_rate
    rate = r.grade / r.per_m
    q = law.tables.emit.instrument.coarse_noise_m
    roles = no_step_roles(law)
    out: list[Row] = []
    seen: set = set()
    for sh in p.shapes:
        if sh.role not in roles or len(sh.ids) < 3:
            continue
        for a, b, c, change, allowed, dp, dn in rate_breaches(sh.xy, sh.z, True, rate, q):
            site = tuple(sorted((round(sh.xy[a][0], 3), round(sh.xy[a][1], 3),
                                 round(sh.xy[b][0], 3), round(sh.xy[b][1], 3),
                                 round(sh.xy[c][0], 3), round(sh.xy[c][1], 3))))
            if site in seen:
                continue
            seen.add(site)
            out.append(row("airside_no_step", (sh.role, sh.role), p.side(sh.role),
                           abs(sh.z[c] - sh.z[a]), 100 * change, None,
                           0.5 * (dp + dn), sh.xy[a], sh.xy[c], sh.key, sh.key))
    return out
