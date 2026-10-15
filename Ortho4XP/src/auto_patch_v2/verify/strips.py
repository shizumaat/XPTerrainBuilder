"""The graded-strip families over the emitted rings (reg-set 2026-08-08;
v1 ``_check_strip_longitudinal_grade`` / ``_check_strip_arc_rate`` /
``_check_resa_transverse_grade`` / ``_check_raoa_rate`` /
``_check_adjacent_ground_edges`` / ``_check_strip_seam_tears``):

* the footprint per runway from the emitted ``runway`` rings grouped by
  ``ref`` (``constraints.strips`` geometry: principal axis, lateral
  rectangle, end corridors), code from the emitted extent;
* ``strip_longitudinal`` / ``strip_arc``: along-axis runs inside the
  lateral rectangle, pavement-pavement pairs skipped, the strip
  reader's coarse envelope / rate blind spot, one row per physical site
  — the ``strip_longitudinal`` PAIR POPULATION and its pavement set are
  the generator's own helpers (``constraints.strips.strip_longitudinal_
  pairs`` / ``pavement_ring_vertices``, RULINGS 2026-09-05ae(3));
* ``resa_transverse``: across pairs inside an end corridor;
* ``runway_end_skirt`` (owner RULINGS 2026-10-12q (1) (d); #620): THE
  GROUND BEYOND THE END as v2 emits it — the ``graded_strip`` rings in
  the end corridors against ``law.tables.runway_end_profile``: along-axis
  ring pairs by the profile's increment between their stations, every
  vertex by the chord from the runway's end edge at its own plan
  distance (the generator's two forms, ``constraints/strips``), and the
  FAA grade-change rate over three stations where the authority states
  one.  Until this ruling the family read a ``runway_end_skirt`` ring v2
  never emits and judged nothing;
* ``raoa`` (ICAO): the s-sorted rate law inside the RAOA rectangle,
  EXACTLY as the census walks it (cross-width neighbours included — the
  reading v2 reports as a residual, ``constraints/strips.py``);
* ``adjacent_ground_tear``: a sub-metre strip edge with a metre-plus jump;
* ``strip_seam_tear``: two different strip rings' vertices within the
  seam radius, a metre-plus step at ≥ 50 % (wall exemptions vacuous:
  v2 emits no walls; the open-ground 15 m floor is NOT modelled — v2 has
  no ungraded ground inside its strips);
* ``strip_transverse`` (RULINGS 2026-09-06b law 2; 2026-09-06p (1)/(3)
  THE RUNWAY-EDGE TIE, read GEOMETRICALLY over EVERY vertex): every
  vertex of every ring and hole — any role but the runway family's own
  and a retaining wall's — inside a runway's lateral rectangle and
  runway zone, standing ABOVE or BELOW its nearest runway-family ring
  edge (interpolated at the foot) by more than
  ``tables.strip_transverse_bound(d)`` plus the quantum — TWO-WAY for
  every vertex (RULINGS 2026-09-06q (2); the 06b strip-only reading
  generalised).  Generator-independent by construction: the reader
  never consults a published pair list (06o: both instruments read only
  the pairs the generators published and were blind to a pair never
  priced).  :func:`runway_edge_tie` is the one geometric core — the v2
  reader, the v1 oracle (``check_grade``'s ``strip_transverse`` family)
  and ``tools/harness/runway_edge_tie.py`` all call it.
"""
from __future__ import annotations

import math
import typing as _t

from ..constraints.geometry import (longitudinal_runs, point_in_rect_ring,
                                    principal_axis, rect_ring)
from ..constraints.strips import (end_pair_bounds, end_transect_foot, end_transect_pairs,
                                  pavement_ring_vertices, strip_longitudinal_pairs)
from shapely.geometry import Point as _ShPoint

from ..law.tables import (end_profile_noise_m, runway_end_profile,
                          runway_safety_area_length_m, runway_zone_edge_offset_m,
                          snap_margin_m, strip_transverse_bound, zone2_half_width_m,
                          zone_bounds)
from .frame import Patch, Row, Shape, pair_side, row
from .no_step import rate_breaches

__all__ = ["groups", "published_slabs", "end_groups", "strip_longitudinal", "strip_arc", "resa_transverse",
           "runway_end_skirt", "raoa", "adjacent_ground_tear", "strip_seam_tear", "strip_transverse",
           "runway_edge_tie", "TiePoint", "TieEdge", "TieHit",
           "natural_shore_geometry", "road_cap_geometry"]

FAMILY_STRIP_TRANSVERSE = "strip_transverse"
RUNWAY_FAMILY = ("runway", "runway_crossing")
#: The role whose ring is a wall CREST: exempt from the tie (06p (1)).
WALL_ROLE = "retaining_wall"

#: One vertex the tie reads: ``both_ways`` for a strip-only vertex (the
#: 06b reading, fall side included); ``label`` is the reader's own tag
#: (a role set, a way id) carried into the hit.
TiePoint = tuple[int, float, float, float, bool, object]
#: One runway-family ring edge: ``((ax, ay, az), (bx, by, bz), ref,
#: code_number, code_letter)``.
TieEdge = tuple[tuple[float, float, float], tuple[float, float, float], str,
                int | None, str | None]


class TieHit(_t.NamedTuple):
    """One vertex over the tie: ``dz = z_v − z_foot`` (signed)."""

    vid: int
    x: float
    y: float
    z: float
    d: float
    z_foot: float
    dz: float
    bound: float
    foot: tuple[float, float]
    ref: str
    code_number: int | None
    code_letter: str | None
    label: object


def runway_edge_tie(points: _t.Iterable[TiePoint], edges: _t.Sequence[TieEdge],
                    axes: _t.Mapping[str, tuple[tuple[float, float], tuple[float, float], float]],
                    law, q: float, edge_tol: float,
                    all_hits: bool = False,
                    natural_shore=None, road_cap=None) -> list[TieHit]:
    """THE RUNWAY-EDGE TIE, geometric (module docstring; RULINGS
    2026-09-06p (1)/(3)): for every point its nearest runway-family ring
    edge whose runway's lateral extent holds it abeam (``axes[ref] =
    (a, unit, L)``: ``0 ≤ s ≤ L``; an edge with no axis is abeam
    everywhere) inside that class's zone-2 half width less ``edge_tol``
    (the corridor's outer ring sits at the half width to the identity
    floor); the foot interpolates the edge's elevation; the vertex is a
    hit when ``|dz| = |z − z_foot| > bound + q`` — EITHER way, for every
    point (RULINGS 2026-09-06q (2); ``both_ways`` is a label now: the 06b
    strip-only reading it named is the reading of every vertex) — with
    ``bound = strip_transverse_bound(law, d, code)``.  ``all_hits`` returns every
    point in reach with its reading (the harness tool's table).

    ``natural_shore`` (a shapely geometry in the points' frame, the
    published §37 (11) (7) wedges): a point inside it that stands BELOW
    its foot is read against the natural shore's own fall — the zone
    corridor with the band at the bank slope (``zone_bounds(...,
    band_max_down=bank_slope)``, owner RULINGS 2026-09-27a (7)); the rise
    side is unchanged."""
    if not edges:
        return []
    cell = max(zone2_half_width_m(law, "runway", e[3], e[4]) or 0.0 for e in edges)
    if cell <= 0.0:
        return []
    grid: dict[tuple[int, int], list[int]] = {}
    for k, (a, b, *_r) in enumerate(edges):
        for gx in range(int(min(a[0], b[0]) // cell), int(max(a[0], b[0]) // cell) + 1):
            for gy in range(int(min(a[1], b[1]) // cell), int(max(a[1], b[1]) // cell) + 1):
                grid.setdefault((gx, gy), []).append(k)
    half_of: dict[tuple, float | None] = {}
    out: list[TieHit] = []
    for vid, x, y, z, both, label in points:
        # OWNER RULINGS 2026-10-02ag (2) (#100) ROAD CAP GOVERNS: under a
        # mapped-road ribbon the tie is withdrawn (the generator minted no
        # row there); ``road_cap`` is the published set, one reading for
        # the verify and the census
        if road_cap is not None and road_cap.covers(_ShPoint(x, y)):
            continue
        cx, cy = int(x // cell), int(y // cell)
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k in grid.get((cx + dx, cy + dy), ()):
                    a, b, ref, cn, cl = edges[k]
                    key = (cn, cl, ref)
                    if key not in half_of:
                        # FROM THE CENTRELINE (2026-10-15c (1)): an axis that
                        # carries the runway's width reads the edge offset
                        ax4 = axes.get(ref)
                        half_of[key] = (runway_zone_edge_offset_m(law, cn, cl, 0.5 * ax4[3])
                                        if ax4 is not None and len(ax4) > 3
                                        else zone2_half_width_m(law, "runway", cn, cl))
                    half = half_of[key]
                    if half is None:
                        continue
                    vx, vy = b[0] - a[0], b[1] - a[1]
                    l2 = vx * vx + vy * vy
                    t = 0.0 if l2 < 1e-18 else max(0.0, min(1.0, ((x - a[0]) * vx + (y - a[1]) * vy) / l2))
                    d = math.hypot(x - (a[0] + t * vx), y - (a[1] + t * vy))
                    if d > half - edge_tol or d <= 0.0:
                        continue
                    ax_ = axes.get(ref)
                    if ax_ is not None:
                        (a0x, a0y), (ux, uy), L = ax_[:3]
                        s_ = (x - a0x) * ux + (y - a0y) * uy
                        if not (0.0 <= s_ <= L):
                            continue
                    if best is None or d < best[0]:
                        best = (d, a[2] + t * (b[2] - a[2]), ref, cn, cl,
                                (a[0] + t * vx, a[1] + t * vy))
        if best is None:
            continue
        d, z_foot, ref, cn, cl, foot = best
        bound = strip_transverse_bound(law, d, cn, cl, half_m=half_of.get((cn, cl, ref)))
        if bound is None:
            continue
        dz = z - z_foot
        if dz < 0.0 and natural_shore is not None and \
                natural_shore.covers(_ShPoint(x, y)):
            lo, _hi = zone_bounds(law, "runway", d, cn, cl,
                                  band_max_down=float(law.tables.emit.design.bank_slope),
                                  half_m=half_of.get((cn, cl, ref)))
            if lo is not None:
                bound = max(bound, -lo)
        # TWO-WAY for every point (RULINGS 2026-09-06q (2)): neither above
        # nor below the foot by more than the bound; ``both`` (a strip-
        # only point) is carried as a label only
        over = abs(dz) > bound + q
        if over or all_hits:
            out.append(TieHit(vid, x, y, z, d, z_foot, dz, bound, foot, ref, cn, cl, label))
    return out

#: The census's seam-tear knobs (``strip_seam_law``): the instrument's own.
SEAM_RADIUS_M = 6.0
SEAM_MIN_STEP_M = 1.0
SEAM_MIN_GRADE = 0.5
SEAM_MIN_DISTANCE_M = 0.01
TEAR_MAX_EDGE_M = 1.0
TEAR_MIN_JUMP_M = 1.0


def _code(length: float) -> int:
    return 4 if length >= 1800 else 3 if length >= 1200 else 2 if length >= 800 else 1


def groups(p: Patch):
    """``[(rings, unit, code, length, letter, axis_a, axis_b)]`` per runway."""
    law = p.law
    pts_by_ref: dict[str, list] = {}
    letter: dict[str, str | None] = {}
    for sh in p.shapes:
        if sh.role == "runway":
            pts_by_ref.setdefault(sh.ref, []).extend(sh.xy)
            letter.setdefault(sh.ref, sh.code_letter)
    out = []
    for ref, pts in pts_by_ref.items():
        ax = principal_axis(pts)
        if ax is None:
            continue
        a, b, width = ax
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1.0:
            continue
        unit = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        code = _code(L)
        half = zone2_half_width_m(law, "runway", code, letter.get(ref)) or 0.0
        end_half = max(width, half)
        len_a, len_b = rsa_end_lengths(p, ref, a, b, code, letter.get(ref))
        rings = (rect_ring(a, b, 0.0, L, half), rect_ring(a, b, -len_a, 0.0, end_half),
                 rect_ring(a, b, L, L + len_b, end_half))
        out.append((rings, unit, code, L, letter.get(ref), a, b))
    return out


def rsa_end_lengths(p: Patch, ref: str | None, a, b, code, letter
                    ) -> tuple[float, float]:
    """``(beyond a, beyond b)``: the RSA length (owner RULINGS 2026-10-15c
    (2); ``tables.runway_safety_area_length_m``) from the runway END, i.e.
    past the slab end less that end's published overrun — the generator's
    ``constraints.strips.runway_groups`` reading, the slab end matched to
    the nearer of ``a`` / ``b``."""
    rsa = runway_safety_area_length_m(p.law, code, letter)
    for r in p.publication.get("runway_axes") or ():
        if len(r) < 8 or str(r[0]) != str(ref):
            continue
        pa, pb = p.to_m(float(r[1]), float(r[2])), p.to_m(float(r[3]), float(r[4]))
        same = math.dist(pa, a) + math.dist(pb, b)
        flip = math.dist(pb, a) + math.dist(pa, b)
        # the END AREA's own length where published (RULINGS 2026-10-15g (C):
        # the RSA, or the top of a drop — ``airport/end_area``)
        la, lb = (float(r[8]), float(r[9])) if len(r) >= 10 else (rsa, rsa)
        oa, ob = (float(r[6]), float(r[7])) if same <= flip else (float(r[7]), float(r[6]))
        la, lb = (la, lb) if same <= flip else (lb, la)
        return max(0.01, la - oa), max(0.01, lb - ob)
    return rsa, rsa


def _runway_widths(p: Patch) -> dict[str, float]:
    """``{ref: width_m}`` — each runway's DECLARED width where the sidecar
    publishes it (``runway_axes`` ``half_m``: the width the generator's
    edge offset reads, ``Runway.width_m``), else off its own rings
    (:func:`geometry.principal_axis`, the frame :func:`groups` fits)."""
    pub = {str(r[0]): 2.0 * float(r[5]) for r in p.publication.get("runway_axes") or ()
           if len(r) >= 6}
    pts: dict[str, list] = {}
    for sh in p.shapes:
        if sh.role == "runway":
            pts.setdefault(sh.ref, []).extend(sh.xy)
    out = {}
    for ref, xs in pts.items():
        ax = principal_axis(xs)
        if ref in pub:
            out[ref] = pub[ref]
        elif ax is not None:
            out[ref] = float(ax[2])
    return out


def published_slabs(rows, to_m) -> dict[str, tuple]:
    """``{ref: (a, b, width_m)}`` — each runway's SLAB axis (physical end
    to physical end, overruns included: ``model.airport.Runway.
    slab_corners``) in the caller's metre frame, from the sidecar's
    ``runway_axes`` rows ``[ref, lat_a, lon_a, lat_b, lon_b, half_m,
    overrun_a_m, overrun_b_m]``.  THE FRAME OF THE RUNWAY-END PROFILE for
    every reader (#620): the generator prices the ground beyond an end
    from the slab's end (§40 (1)/(4): a shoulder moves no axis and mints
    no region), and a reader that fits the runway-role RINGS instead
    measures from the far edge of whatever shoulder lies beyond it —
    KASE 15, a 60 m paved pad: every end station read 60 m short and the
    last 15 m of the band was judged at the first 61 m's cap.  A row
    without the two overruns (a patch predating them) is not a slab and
    is left out: the caller keeps its fitted axis."""
    out: dict[str, tuple] = {}
    for r in rows or ():
        if len(r) < 8:
            continue
        a, b = to_m(float(r[1]), float(r[2])), to_m(float(r[3]), float(r[4]))
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1.0:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        out[str(r[0])] = ((a[0] - ux * float(r[6]), a[1] - uy * float(r[6])),
                          (b[0] + ux * float(r[7]), b[1] + uy * float(r[7])),
                          2.0 * float(r[5]))
    return out


def end_groups(p: Patch):
    """:func:`groups` rows WITH THEIR REF, in the frame the runway-end
    profile is priced in: the published slab where the patch carries one
    (:func:`published_slabs`), the fitted axis otherwise."""
    law = p.law
    slabs = published_slabs(p.publication.get("runway_axes"), p.to_m)
    out = []
    for rings, unit, code, L, letter, a, b in groups(p):
        ref = next((sh.ref for sh in p.shapes if sh.role == "runway"
                    and point_in_rect_ring(sh.xy[0][0], sh.xy[0][1], rings[0])), None)
        slab = slabs.get(ref) if ref else None
        if slab is not None:
            a, b, width = slab
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            unit = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
            code = _code(L)
            half = zone2_half_width_m(law, "runway", code, letter) or 0.0
            len_a, len_b = rsa_end_lengths(p, ref, a, b, code, letter)
            end_half = max(width, half)
            rings = (rect_ring(a, b, 0.0, L, half), rect_ring(a, b, -len_a, 0.0, end_half),
                     rect_ring(a, b, L, L + len_b, end_half))
        out.append((ref, rings, unit, code, L, letter, a, b))
    return out


def _strips(p: Patch) -> list[Shape]:
    return [sh for sh in p.shapes if sh.role == "graded_strip" and len(sh.ids) >= 2]


def _pavement_ids(p: Patch) -> frozenset[int]:
    """The generator's own pavement population (``constraints.strips.
    pavement_ring_vertices``, RULINGS 2026-09-05ae(3))."""
    return pavement_ring_vertices((p.cap(sh), sh.ids) for sh in p.shapes)


def strip_longitudinal(p: Patch) -> list[Row]:
    law = p.law
    q = law.tables.emit.instrument.coarse_noise_m
    pav = _pavement_ids(p)
    out: list[Row] = []
    seen: set = set()
    for rings, unit, code, L, letter, _a, _b in groups(p):
        cap = law.ruleset.strip.longitudinal.value(code, letter)
        if cap is None:
            continue
        for sh in _strips(p):
            # ONE population with the generator (05ae-3)
            for i, j, ds in strip_longitudinal_pairs(sh.ids, sh.xy, unit, rings[0], pav):
                site = tuple(sorted((tuple(round(c, 3) for c in sh.xy[i]),
                                     tuple(round(c, 3) for c in sh.xy[j]))))
                if site in seen:
                    continue
                seen.add(site)
                dz = abs(sh.z[j] - sh.z[i])
                if dz <= cap * ds + q:
                    continue
                out.append(row("strip_longitudinal", ("graded_strip",) * 2,
                               p.side("graded_strip"), dz, 100 * dz / ds, 100 * cap,
                               ds, sh.xy[i], sh.xy[j], sh.key, sh.key))
    return out


def strip_arc(p: Patch) -> list[Row]:
    law = p.law
    r = law.ruleset.strip.arc_rate
    rate = r.grade / r.per_m
    q = law.tables.emit.instrument.coarse_noise_m
    out: list[Row] = []
    seen: set = set()
    for rings, unit, code, L, letter, _a, _b in groups(p):
        for sh in _strips(p):
            inside = [point_in_rect_ring(x, y, rings[0]) for x, y in sh.xy]
            if not any(inside):
                continue
            for run in longitudinal_runs(sh.xy, unit, inside):
                pts = [(sh.xy[i][0] * unit[0] + sh.xy[i][1] * unit[1], 0.0) for i in run]
                zs = [sh.z[i] for i in run]
                for a, b, c, change, allowed, dp, dn in rate_breaches(pts, zs, False, rate, q,
                                                                        p.law.tables.emit.materiality.grade):
                    A, B, C = run[a], run[b], run[c]
                    site = tuple(sorted(tuple(round(v, 3) for v in sh.xy[i]) for i in (A, B, C)))
                    if site in seen:
                        continue
                    seen.add(site)
                    out.append(row("strip_arc", ("graded_strip",) * 2, p.side("graded_strip"),
                                   abs(sh.z[C] - sh.z[A]), 100 * change, None,
                                   0.5 * (dp + dn), sh.xy[A], sh.xy[C], sh.key, sh.key))
    return out


def resa_transverse(p: Patch) -> list[Row]:
    law = p.law
    q = law.tables.emit.instrument.coarse_noise_m
    rs = law.ruleset
    out: list[Row] = []
    # ROAD CAP GOVERNS (owner RULINGS 2026-10-02ag (2)): the published set
    cap_geom = road_cap_geometry(p.publication.get("road_cap_governs"), p.to_m, law)
    for rings, unit, code, L, letter, a0, _b in groups(p):
        ux, uy = unit
        px, py = -uy, ux
        for sh in _strips(p):
            for ring_idx in (1, 2):
                ring = rings[ring_idx]
                inside = [point_in_rect_ring(x, y, ring) for x, y in sh.xy]
                if not any(inside):
                    continue
                for i in range(len(sh.xy) - 1):
                    j = i + 1
                    if not (inside[i] and inside[j]):
                        continue
                    if cap_geom is not None and (cap_geom.covers(_ShPoint(*sh.xy[i]))
                                                 or cap_geom.covers(_ShPoint(*sh.xy[j]))):
                        continue
                    dx, dy = sh.xy[j][0] - sh.xy[i][0], sh.xy[j][1] - sh.xy[i][1]
                    along, across = abs(dx * ux + dy * uy), abs(dx * px + dy * py)
                    if across <= along or across < 1.0:
                        continue
                    s_mid = 0.5 * ((sh.xy[i][0] + sh.xy[j][0] - 2 * a0[0]) * ux
                                   + (sh.xy[i][1] + sh.xy[j][1] - 2 * a0[1]) * uy)
                    beyond = abs(s_mid) if ring_idx == 1 else max(0.0, s_mid - L)
                    near = rs.end_skirt.near_zone_m
                    if near is not None and beyond <= near and rs.resa.transverse_near_max:
                        cap = rs.resa.transverse_near_max.value(None, letter)
                    else:
                        cap = rs.resa.transverse_max
                    if not cap:
                        continue
                    dz = abs(sh.z[j] - sh.z[i])
                    if dz <= cap * across + q:
                        continue
                    out.append(row("resa_transverse", ("graded_strip",) * 2,
                                   p.side("graded_strip"), dz, 100 * dz / across,
                                   100 * cap, across, sh.xy[i], sh.xy[j], sh.key, sh.key))
    return out


FAMILY_RUNWAY_END_SKIRT = "runway_end_skirt"


def _runway_end_edges(p: Patch, ref: str, a0, unit, L: float, m: float):
    """The runway face's END EDGES in the census frame: ``(xa, za, xb, zb,
    end)`` for each ring edge of a ``runway`` shape of ``ref`` whose two
    vertices both stand at the start (1) or the end (2) station."""
    ux, uy = unit
    out = []
    for sh in p.shapes:
        if sh.role != "runway" or sh.ref != ref:
            continue
        n = len(sh.ids)
        for i in range(n):
            j = (i + 1) % n
            sa = (sh.xy[i][0] - a0[0]) * ux + (sh.xy[i][1] - a0[1]) * uy
            sb = (sh.xy[j][0] - a0[0]) * ux + (sh.xy[j][1] - a0[1]) * uy
            for end, s0 in ((1, 0.0), (2, L)):
                if abs(sa - s0) <= m and abs(sb - s0) <= m:
                    out.append((sh.xy[i], sh.z[i], sh.xy[j], sh.z[j], end))
    return out


def _end_pavement_edges(p: Patch, ref: str, a0, unit, L: float, ring_idx: int):
    """``((d_a, t_a), (d_b, t_b), z_a, z_b)`` for every outer-ring edge of
    a ``runway`` shape of ``ref`` reaching beyond end ``ring_idx`` — the
    generator's ``constraints.strips._end_pavement_edges`` in the census
    frame."""
    ux, uy = unit

    def dt(xy):
        s = (xy[0] - a0[0]) * ux + (xy[1] - a0[1]) * uy
        return (-s if ring_idx == 1 else s - L), -(xy[0] - a0[0]) * uy + (xy[1] - a0[1]) * ux

    out = []
    for sh in p.shapes:
        if sh.role != "runway" or sh.ref != ref:
            continue
        n = len(sh.ids)
        for i in range(n):
            j = (i + 1) % n
            pa, pb = dt(sh.xy[i]), dt(sh.xy[j])
            if max(pa[0], pb[0]) > 0.0:
                out.append((pa, pb, sh.z[i], sh.z[j]))
    return out


def end_chord_foot(x: float, y: float, edges, rect_of) -> tuple[float, float, int] | None:
    """``(d, z_foot, end)`` — the nearest point of the nearest runway end
    edge (``t`` clamped, §35) for a vertex inside that end's rect: the
    true plan distance to it and the edge's elevation interpolated there.
    ONE geometry with ``constraints.strips._end_feet``."""
    best = None
    for (ax, ay), za, (bx, by), zb, end in edges:
        if not rect_of(end, x, y):
            continue
        ex, ey = bx - ax, by - ay
        l2 = ex * ex + ey * ey
        if l2 < 1e-9:
            continue
        t = ((x - ax) * ex + (y - ay) * ey) / l2
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        d = math.hypot(x - (ax + t * ex), y - (ay + t * ey))
        if best is None or d < best[0]:
            best = (d, za + t * (zb - za), end)
    return best


def end_excess_m(prof, d_in: float, d_out: float, z_in: float, z_out: float,
                 q: float) -> float:
    """How far a pair (``d_in ≤ d_out`` beyond the end) stands OUTSIDE the
    profile's bounds on ``z_in − z_out`` (``end_pair_bounds``): > 0 is a
    breach — falling too fast (positive drop over ``hi``) or rising over
    the climb surface (below ``lo``).  0 inside."""
    lo, hi = end_pair_bounds(prof, d_in, d_out, q)
    drop = z_in - z_out
    if drop > hi:
        return drop - hi
    if lo is not None and drop < lo:
        return lo - drop
    return 0.0


def runway_end_skirt(p: Patch) -> list[Row]:
    """The runway-end profile read IN THE ENGINE'S METRIC
    (:meth:`Patch.in_metric_frame`): its bounds are functions of plan
    distance beyond the end, which the census frame reads 0.1-0.7 %
    short or long (lane rwyzone15c, the CYXY chord rows); every row's
    points go back to the census frame."""
    p, back = p.in_metric_frame()

    def end_row(family, roles, side, mag, grade, cap, d, a, b, *rest):
        return row(family, roles, side, mag, grade, cap, d, back(a), back(b), *rest)
    law = p.law
    q = end_profile_noise_m(law, reader=True)
    qc = law.tables.emit.instrument.coarse_noise_m
    m = law.tables.emit.identity.min_distinct_spacing_m
    pav = _pavement_ids(p)
    # ROAD CAP GOVERNS (owner RULINGS 2026-10-02ag (2)): a vertex under a
    # mapped-road ribbon is the road's — the generator states no end row
    # on it and the family reads none (the published set, one reading)
    cap_geom = road_cap_geometry(p.publication.get("road_cap_governs"), p.to_m, law)

    def road(xy) -> bool:
        return cap_geom is not None and cap_geom.covers(_ShPoint(xy[0], xy[1]))

    out: list[Row] = []
    seen: set = set()
    for ref, rings, unit, code, L, letter, a0, _b in end_groups(p):
        prof = runway_end_profile(law, code, letter)
        ux, uy = unit

        def beyond(xy, ring_idx):
            s = (xy[0] - a0[0]) * ux + (xy[1] - a0[1]) * uy
            return max(0.0, -s) if ring_idx == 1 else max(0.0, s - L)

        def rect_of(end, x, y):
            return point_in_rect_ring(x, y, rings[end])

        edges = _runway_end_edges(p, ref, a0, unit, L, m) if ref else []
        # the TRANSECT pairs (``constraints.strips.end_transect_pairs``)
        for ring_idx in (1, 2):
            st: dict = {}
            for sh in _strips(p):
                for k, v in enumerate(sh.ids):
                    if v in pav or v in st:
                        continue
                    x, y = sh.xy[k]
                    if not point_in_rect_ring(x, y, rings[ring_idx]) or road((x, y)):
                        continue
                    d = beyond((x, y), ring_idx)
                    if d <= 0.0:
                        continue
                    st[v] = (d, -(x - a0[0]) * uy + (y - a0[1]) * ux, sh.z[k], (x, y), sh.key)
            for vi, vo in end_transect_pairs([(v, d, t) for v, (d, t, _z, _xy, _k) in st.items()], m):
                site = tuple(sorted((tuple(round(c, 3) for c in st[vi][3]),
                                     tuple(round(c, 3) for c in st[vo][3]))))
                if site in seen:
                    continue
                seen.add(site)
                ex = end_excess_m(prof, st[vi][0], st[vo][0], st[vi][2], st[vo][2], q)
                if ex <= 0.0:
                    continue
                ds = st[vo][0] - st[vi][0]
                out.append(end_row(FAMILY_RUNWAY_END_SKIRT, ("graded_strip",) * 2,
                               p.side("graded_strip"), ex, 100 * (st[vo][2] - st[vi][2]) / ds,
                               100 * prof.down_cap_at(st[vo][0]), ds,
                               st[vi][3], st[vo][3], st[vi][4], st[vo][4]))
            # the TRANSECT FEET (``constraints.strips.end_transect_foot``):
            # the ground behind runway pavement that continues past the end
            pedges = _end_pavement_edges(p, ref, a0, unit, L, ring_idx) if ref else []
            for v, (d, t, z, xy, key) in st.items():
                hit = end_transect_foot(d, t, [(e[0], e[1]) for e in pedges], m)
                if hit is None:
                    continue
                k, tau, de = hit
                zf = pedges[k][2] + tau * (pedges[k][3] - pedges[k][2])
                ex = end_excess_m(prof, de, d, zf, z, q)
                if ex <= 0.0:
                    continue
                out.append(end_row(FAMILY_RUNWAY_END_SKIRT, ("graded_strip", "runway"),
                               pair_side(p, "graded_strip", "runway"), ex,
                               100 * (z - zf) / (d - de), 100 * prof.down_cap_at(d), d - de,
                               xy, xy, key, key))
        for sh in _strips(p):
            for ring_idx in (1, 2):
                inside = [point_in_rect_ring(x, y, rings[ring_idx]) for x, y in sh.xy]
                if not any(inside):
                    continue
                for run in longitudinal_runs(sh.xy, unit, inside):
                    for i, j in zip(run, run[1:]):
                        ds = abs((sh.xy[j][0] - sh.xy[i][0]) * ux + (sh.xy[j][1] - sh.xy[i][1]) * uy)
                        if ds < 1.0 or road(sh.xy[i]) or road(sh.xy[j]) \
                                or (sh.ids[i] in pav and sh.ids[j] in pav):
                            continue      # two pavement vertices: that pavement's own
                        site = tuple(sorted((tuple(round(c, 3) for c in sh.xy[i]),
                                             tuple(round(c, 3) for c in sh.xy[j]))))
                        if site in seen:
                            continue
                        seen.add(site)
                        di, dj = beyond(sh.xy[i], ring_idx), beyond(sh.xy[j], ring_idx)
                        (vi, vo) = (i, j) if di <= dj else (j, i)
                        ex = end_excess_m(prof, min(di, dj), max(di, dj), sh.z[vi], sh.z[vo], q)
                        if ex <= 0.0:
                            continue
                        dz = abs(sh.z[j] - sh.z[i])
                        out.append(end_row(FAMILY_RUNWAY_END_SKIRT, ("graded_strip",) * 2,
                                       p.side("graded_strip"), ex, 100 * dz / ds,
                                       100 * prof.down_cap_at(max(di, dj)), ds,
                                       sh.xy[i], sh.xy[j], sh.key, sh.key))
                    if prof.rate is not None:
                        pts = [(sh.xy[i][0] * ux + sh.xy[i][1] * uy, 0.0) for i in run]
                        zs = [sh.z[i] for i in run]
                        for a, b, c, change, allowed, dp, dn in rate_breaches(
                                pts, zs, False, prof.rate, qc,
                                law.tables.emit.materiality.grade):
                            A, B, C = run[a], run[b], run[c]
                            site = tuple(sorted(tuple(round(v, 3) for v in sh.xy[k]) for k in (A, B, C)))
                            if site in seen or any(sh.ids[k] in pav for k in (A, B, C)):
                                continue      # a pavement station: that pavement's own
                            seen.add(site)
                            out.append(end_row(FAMILY_RUNWAY_END_SKIRT, ("graded_strip",) * 2,
                                           p.side("graded_strip"), abs(sh.z[C] - sh.z[A]),
                                           100 * change, None, 0.5 * (dp + dn),
                                           sh.xy[A], sh.xy[C], sh.key, sh.key))
            if not edges:
                continue
            for k, v in enumerate(sh.ids):
                if v in pav or road(sh.xy[k]):
                    continue
                x, y = sh.xy[k]
                foot = end_chord_foot(x, y, edges, rect_of)
                if foot is None or foot[0] < 1.0:
                    continue
                d, zf, _end = foot
                site = ("chord", tuple(round(c, 3) for c in sh.xy[k]))
                if site in seen:
                    continue
                seen.add(site)
                ex = end_excess_m(prof, 0.0, d, zf, sh.z[k], q)
                if ex <= 0.0:
                    continue
                out.append(end_row(FAMILY_RUNWAY_END_SKIRT, ("graded_strip", "runway"),
                               pair_side(p, "graded_strip", "runway"), ex,
                               100 * (sh.z[k] - zf) / d, 100 * prof.down_cap_at(d), d,
                               sh.xy[k], sh.xy[k], sh.key, sh.key))
    return out


def raoa(p: Patch) -> list[Row]:
    law = p.law
    ra = law.ruleset.raoa
    if ra is None or not ra.length_m or not ra.half_width_m:
        return []
    rate = ra.max_grade_change.grade / ra.max_grade_change.per_m
    q = law.tables.emit.instrument.coarse_noise_m
    out: list[Row] = []
    seen: set = set()
    for rings, unit, code, L, letter, a0, b0 in groups(p):
        for thr, inward in ((a0, unit), (b0, (-unit[0], -unit[1]))):
            ux, uy = inward
            px, py = -uy, ux
            Lr, W = ra.length_m, ra.half_width_m
            corners = ((0.0, -W), (-Lr, -W), (-Lr, W), (0.0, W))
            ring = [(thr[0] + ux * s + px * t, thr[1] + uy * s + py * t) for (s, t) in corners]
            ring.append(ring[0])
            for sh in _strips(p):
                idx = [i for i, (x, y) in enumerate(sh.xy) if point_in_rect_ring(x, y, ring)]
                if len(idx) < 3:
                    continue
                s = [sh.xy[i][0] * ux + sh.xy[i][1] * uy for i in idx]
                t_lat = [sh.xy[i][0] * px + sh.xy[i][1] * py for i in idx]
                order = sorted(range(len(idx)), key=lambda k: s[k])
                s = [s[k] for k in order]
                t_lat = [t_lat[k] for k in order]
                src = [idx[k] for k in order]
                for k in range(1, len(s) - 1):
                    dp, dn = s[k] - s[k - 1], s[k + 1] - s[k]
                    if dp < 1e-6 or dn < 1e-6:
                        continue
                    # the profile runs ALONG the approach: a hop that is more
                    # across than along is a cross-width neighbour (M3a
                    # adjudication; the oracle reads the same since 91426d6c)
                    if abs(t_lat[k] - t_lat[k - 1]) > dp or abs(t_lat[k + 1] - t_lat[k]) > dn:
                        continue
                    z0, z1, z2 = sh.z[src[k - 1]], sh.z[src[k]], sh.z[src[k + 1]]
                    change = abs((z2 - z1) / dn - (z1 - z0) / dp)
                    allowed = rate * 0.5 * (dp + dn)
                    if change - allowed <= q * (1.0 / dp + 1.0 / dn):
                        continue
                    site = tuple(sorted(tuple(round(v, 3) for v in sh.xy[i])
                                        for i in (src[k - 1], src[k], src[k + 1])))
                    if site in seen:
                        continue
                    seen.add(site)
                    out.append(row("raoa", ("graded_strip",) * 2, p.side("graded_strip"),
                                   abs(z2 - z0), 100 * change, None, 0.5 * (dp + dn),
                                   sh.xy[src[k - 1]], sh.xy[src[k + 1]], sh.key, sh.key))
    return out


def adjacent_ground_tear(p: Patch) -> list[Row]:
    out: list[Row] = []
    for sh in _strips(p):
        n = len(sh.ids)
        for i in range(n):
            j = (i + 1) % n
            (xa, ya), (xb, yb) = sh.xy[i], sh.xy[j]
            d = math.hypot(xb - xa, yb - ya)
            de = abs(sh.z[i] - sh.z[j])
            if not (d < TEAR_MAX_EDGE_M and de > TEAR_MIN_JUMP_M):
                continue
            g = de / d if d > 1e-9 else float("inf")
            out.append(row("adjacent_ground_tear", ("graded_strip",) * 2,
                           p.side("graded_strip"), de, 100 * g, None, d,
                           sh.xy[i], sh.xy[j], sh.key, sh.key))
    return out


def adjacent_ground_step(p: Patch) -> list[Row]:
    """THE WITHIN-FACE WELDED STEP (spec §34 (4); lane ``v2rampwalk``) —
    the lockstep twin of ``check_grade._check_adjacent_ground_steps``: a
    consecutive pair of ONE adjacent-ground ring over the cockpit's
    visual threshold AND over its cliff grade (a cut, never a drape)."""
    ck = _cockpit(p)
    if ck is None:
        return []
    step_m, cliff = ck
    out: list[Row] = []
    for sh in _strips(p):
        n = len(sh.ids)
        for i in range(n):
            j = (i + 1) % n
            (xa, ya), (xb, yb) = sh.xy[i], sh.xy[j]
            d = math.hypot(xb - xa, yb - ya)
            de = abs(sh.z[i] - sh.z[j])
            if de <= step_m:
                continue
            g = de / d if d > 1e-9 else float("inf")
            if g <= cliff:
                continue
            out.append(row("adjacent_ground_step", ("graded_strip",) * 2,
                           p.side("graded_strip"), de, 100 * g, None, d,
                           sh.xy[i], sh.xy[j], sh.key, sh.key))
    return out


def _cockpit(p: Patch):
    """``(visual_m, cliff_grade)`` from the patch's own law tables."""
    law = getattr(p, "law", None)
    if law is None:
        return None
    from ..law import tables as _T
    return float(_T.cockpit(law).visual_m), float(_T.cliff_grade(law))


def strip_seam_tear(p: Patch) -> list[Row]:
    strips = _strips(p)
    pts: list[tuple[float, float, float, int, int]] = []
    for sh in strips:
        for k, vid in enumerate(sh.ids):
            pts.append((sh.xy[k][0], sh.xy[k][1], sh.z[k], sh.key, vid))
    cell = SEAM_RADIUS_M
    grid: dict[tuple[int, int], list[int]] = {}
    for i, (x, y, *_r) in enumerate(pts):
        grid.setdefault((int(x // cell), int(y // cell)), []).append(i)
    out: list[Row] = []
    for i, (x, y, z, key, vid) in enumerate(pts):
        cx, cy = int(x // cell), int(y // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((cx + dx, cy + dy), ()):
                    if j <= i:
                        continue
                    x2, y2, z2, key2, vid2 = pts[j]
                    if key2 == key or vid2 == vid:
                        continue
                    d = math.hypot(x2 - x, y2 - y)
                    if d > SEAM_RADIUS_M:
                        continue
                    de = abs(z2 - z)
                    if de <= SEAM_MIN_STEP_M or de / max(d, SEAM_MIN_DISTANCE_M) < SEAM_MIN_GRADE:
                        continue
                    # THE ROW CARRIES THE PAIR MIDPOINT (spec §32 (3);
                    # RULINGS 2026-09-12ag) — the twin of
                    # ``check_grade._check_strip_seam_tears``.  A row that
                    # left ``lat`` null was located by the reader's ring-
                    # centroid fallback, 220 m off the LEMD tear.
                    out.append(row("strip_seam_tear", ("graded_strip",) * 2,
                                   p.side("graded_strip"), de,
                                   100 * de / max(d, SEAM_MIN_DISTANCE_M), None, d,
                                   (x, y), (x2, y2), key, key2,
                                   lat=0.5 * (p.ll[vid][0] + p.ll[vid2][0]),
                                   lon=0.5 * (p.ll[vid][1] + p.ll[vid2][1])))
    out.sort(key=lambda r: -r["magnitude_m"])
    return out


def strip_transverse(p: Patch) -> list[Row]:
    """The tie read on the built surface (module docstring): EVERY
    vertex of every shape and feature — the runway family's own and the
    wall crests excluded — against its nearest abeam runway-family ring
    edge, EITHER way (06p (1) the rise side for every vertex; 06q (2)
    the fall side too); one row per vertex, the roles ``(vertex's role,
    runway)``."""
    law = p.law
    q = law.tables.emit.instrument.coarse_noise_m
    # the corridor's OUTER ring sits at the half width to the identity
    # floor: the census frame and the planar frame disagree there by the
    # frame's own rounding (measured 74.93 vs 75.08 m on the crown twin),
    # so the reader stops one identity floor short of the generator's edge
    edge_tol = law.tables.emit.identity.min_distinct_spacing_m
    exempt: set[int] = set()
    role_of: dict[int, str] = {}
    key_of: dict[int, int] = {}
    strip_only: set[int] = set()
    other: set[int] = set()
    for sh in p.shapes:
        if sh.role in RUNWAY_FAMILY or sh.role == WALL_ROLE:
            exempt.update(sh.ids)
            continue
        if sh.role == "graded_strip":
            strip_only.update(sh.ids)
        else:
            other.update(sh.ids)
        for vid in sh.ids:
            role_of.setdefault(vid, sh.role)
            key_of.setdefault(vid, sh.key)
    host_role = {sh.key: sh.role for sh in p.shapes}
    for sh in p.features:
        if sh.feature == "crown_spine":
            continue
        if sh.feature == "structure_rim":
            other.update(sh.ids)
        for vid in sh.ids:
            role_of.setdefault(vid, host_role.get(sh.host, sh.feature or "feature"))
            key_of.setdefault(vid, sh.host if sh.host is not None else sh.key)
    strip_only -= other
    # ABEAM is along the axis only (the generator's ``abeam``: 0 ≤ s ≤ L);
    # the lateral extent is the class's own zone-2 half width
    axes: dict[str, tuple] = {}
    widths = {ref: w for ref, w in _runway_widths(p).items()}
    for rings, unit, _code, L, _letter, a, _b in groups(p):
        ref_ = _ref_of(p, rings)
        axes[ref_] = (a, unit, L, widths.get(ref_, 0.0))
    edges: list[TieEdge] = []
    for sh in p.shapes:
        if sh.role not in RUNWAY_FAMILY:
            continue
        ref = sh.ref.split("+")[0]
        n = len(sh.ids)
        for i in range(n):
            j = (i + 1) % n
            edges.append(((*sh.xy[i], sh.z[i]), (*sh.xy[j], sh.z[j]), ref,
                          sh.code_number, sh.code_letter))
    pts: list[TiePoint] = [(vid, xy[0], xy[1], p.z[vid], vid in strip_only, role_of.get(vid, "?"))
                           for vid, xy in p.xy.items() if vid not in exempt and vid in role_of]
    pts.sort()
    out: list[Row] = []
    shore = natural_shore_geometry(p.publication.get("natural_shore"), p.to_m, law)
    road_cap = road_cap_geometry(p.publication.get("road_cap_governs"), p.to_m, law)
    for h in runway_edge_tie(pts, edges, axes, law, q, edge_tol,
                             natural_shore=shore, road_cap=road_cap):
        role = str(h.label)
        r = row(FAMILY_STRIP_TRANSVERSE, (role, "runway"),
                p.side(role) if role in law.tables.precedence.roles else p.side("graded_strip"),
                abs(h.dz), 100 * h.dz / h.d, 100 * h.bound / h.d, h.d, (h.x, h.y), h.foot,
                key_of.get(h.vid, h.vid), h.ref)
        r.update({"reading": "strip_transverse", "direction": "above" if h.dz > 0.0 else "below"})
        out.append(r)
    out.sort(key=lambda r: -r["magnitude_m"])
    return out


def _ref_of(p: Patch, rings) -> str:
    """The runway ref whose ``runway`` rings lie in ``rings[0]`` (the
    lateral rectangle ``groups`` built from them)."""
    for sh in p.shapes:
        if sh.role == "runway" and all(point_in_rect_ring(x, y, rings[0]) for x, y in sh.xy[:3]):
            return sh.ref
    return ""


def road_cap_geometry(points_ll, to_m, law):
    """OWNER RULINGS 2026-10-02ag (2): the published ``road_cap_governs``
    vertices (sidecar, ``[[lat, lon], ...]``) as ONE geometry in the
    reader's metres frame — each grown by the identity spacing so the
    emitted vertex reads inside.  ``None`` when the patch publishes none."""
    if not points_ll:
        return None
    from shapely.ops import unary_union
    r = float(law.tables.emit.identity.min_distinct_spacing_m)
    pts = [_ShPoint(*to_m(float(a), float(b))).buffer(r) for a, b in points_ll]
    return unary_union(pts) if pts else None


def natural_shore_geometry(rings_ll, to_m, law):
    """§37 (11) (7): the published natural-shore wedges (sidecar
    ``natural_shore``, ``[[[lat, lon], ...], ...]``) as ONE geometry in the
    reader's metres frame, grown by the snap margin so a wedge-edge vertex
    reads inside.  ``None`` when the patch publishes none — every patch
    written before the rule reads exactly as before."""
    if not rings_ll:
        return None
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = []
    for ring in rings_ll:
        pts = [to_m(float(a), float(b)) for a, b in ring]
        if len(pts) >= 3:
            polys.append(Polygon(pts).buffer(0))
    if not polys:
        return None
    return unary_union(polys).buffer(snap_margin_m(law))
