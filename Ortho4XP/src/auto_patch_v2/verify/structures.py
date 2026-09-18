"""The STRUCTURE readers (M4) over the emitted product — the law family
``wall_in_runway_strip`` (registered in ``families.toml``) and the
ACCEPTANCE checks (the canonical mouth of RULINGS 2026-08-30, deck
clearance, the basin floor at its declaration, the rim gap), each as a
pure function over :class:`Patch` returning rows in the census row
shape.  The acceptance checks are NOT law families (the v1 register has
none — the twin ``test_every_v1_family_has_a_v2_family`` holds the two
registers equal) and are published under their own keys beside the
families.

Populations are the ORACLE's own: ramps are the ``tunnel_ramp`` ROLE,
floors the ``tunnel_trench`` role, decks the ``bridge_deck:`` refs, and
the RIMS the ``structure_rim`` FEATURE ways (RULINGS 2026-09-06b (1):
the at-grade ring round a structure's void, ref ``tunnel_wall`` for a
tunnel, ``basin_wall:<k>`` for a basin; no wall band exists — the
``tunnel_wall_top_flat`` / ``tunnel_ramp_wall_gap`` / ``basin_wall_gap``
readers of the band retired with it).
"""
from __future__ import annotations

import math

from ..constraints.geometry import principal_axis
from ..law.tables import zone2_half_width_m
from ..model.structures import deck_z_on_faces

#: The corridor ring's own identity spacing (1 m), in DEGREES — the
#: published corridor is lon/lat and the tolerance travels with it.
_RING_TOL_DEG = 1.0 / 111320.0
from .frame import Patch, Row, Shape, row

__all__ = ["wall_in_runway_strip", "basin_floor_declaration", "tunnel_mouth_canonical",
           "tunnel_deck_clearance", "basin_floor_at_declaration", "structure_rim_gap",
           "ACCEPTANCE"]

_WALL_REF = "tunnel_wall"
_RIM_FEATURE = "structure_rim"


def _ramps(p: Patch) -> list[Shape]:
    return [sh for sh in p.shapes if sh.role == "tunnel_ramp"]


def _rims(p: Patch) -> list[Shape]:
    """Every structure rim (the ``structure_rim`` feature ways)."""
    return [sh for sh in p.features if sh.feature == _RIM_FEATURE]


def _walls(p: Patch) -> list[Shape]:
    """The tunnel rims (ref ``tunnel_wall`` exactly)."""
    return [sh for sh in _rims(p) if sh.ref == _WALL_REF]


def _decks(p: Patch) -> list[Shape]:
    return [sh for sh in p.shapes if sh.ref.startswith("bridge_deck:")]


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _seg_dist(px: float, py: float, a: tuple[float, float], b: tuple[float, float]) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    l2 = vx * vx + vy * vy
    t = 0.0 if l2 < 1e-18 else max(0.0, min(1.0, ((px - a[0]) * vx + (py - a[1]) * vy) / l2))
    return math.hypot(px - (a[0] + t * vx), py - (a[1] + t * vy))


def _inside(px: float, py: float, ring) -> bool:
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / ((yj - yi) or 1e-18) + xi:
            inside = not inside
        j = i
    return inside


# ── the law family ───────────────────────────────────────────────────────

def wall_in_runway_strip(p: Patch) -> list[Row]:
    """Every structure RIM vertex (the ``structure_rim`` feature ways —
    the void's at-grade edge, in place of the retired ``retaining_wall``
    band) inside a runway-family ring's strip keep-out
    (``zones.adjacent_ground`` runway half width for the runway's code;
    RULINGS 2026-08-21d, ``retaining_wall.in_runway_strip = false``) is
    a row; the family's roles stay the register's."""
    law = p.law
    runways = [sh for sh in p.shapes if sh.role in ("runway", "runway_crossing")]
    walls = _rims(p) + [sh for sh in p.shapes if sh.role == "retaining_wall"]
    if not runways or not walls:
        return []
    out: list[Row] = []
    for w in walls:
        for k, (x, y) in enumerate(w.xy):
            for r in runways:
                hw = zone2_half_width_m(law, "runway", r.code_number, r.code_letter)
                if not hw:
                    continue
                if _inside(x, y, r.xy):
                    d = 0.0
                else:
                    n = len(r.xy)
                    d = min(_seg_dist(x, y, r.xy[i], r.xy[(i + 1) % n]) for i in range(n))
                if d <= hw:
                    out.append(row("wall_in_runway_strip", ("retaining_wall", r.role),
                                   "airside", hw - d, None, None, d, (x, y), (x, y),
                                   w.key, r.key, lat=p.ll[w.ids[k]][0], lon=p.ll[w.ids[k]][1]))
                    break
    return out


def basin_floor_declaration(p: Patch) -> list[Row]:
    """THE DECLARATION ITSELF, judged (Appendix A §1; RULINGS 2026-08-26
    §2.2; v1 ``_check_basin_floor_declaration``): a published basin
    facility whose two bottom instruments — ``solid_minimum_y_m`` and
    ``body_depth_m`` — disagree by more than
    ``structures.basin.floor_disagreement_m`` is a floor its own geometry
    does not evidence.  Populations are the sidecar's ``basin_facilities``
    rows exactly as the oracle reads them."""
    tol = p.law.tables.structures.basin.floor_disagreement_m
    out: list[Row] = []
    for rec in p.publication.get("basin_facilities") or ():
        try:
            floor_m = float(rec["floor_m"])
            body = rec.get("body_depth_m")
            smin = rec.get("solid_minimum_y_m")
            if body is None or smin is None:
                continue
            dis = abs(float(smin) + float(body))
        except (KeyError, TypeError, ValueError):
            continue
        if dis <= tol:
            continue
        anchor = rec.get("anchor_longitude_latitude") or (None, None)
        lat = lon = None
        try:
            lon, lat = float(anchor[0]), float(anchor[1])
        except (TypeError, ValueError, IndexError):
            pass
        out.append(row("basin_floor_declaration", ("tunnel_trench",) * 2, "airside", dis,
                       0.0, 0.0, 0.0, (0.0, 0.0), (0.0, 0.0),
                       ",".join(str(r).split("/")[-1] for r in rec.get("resources") or ())
                       or "basin_facility", None, lat=lat, lon=lon,
                       out_of_scope=f"floor {floor_m:.2f}: solid {smin} vs body {body}"))
    return out


# ── the acceptance checks ────────────────────────────────────────────────

def _basin_floors(p: Patch) -> list[Shape]:
    return [sh for sh in p.shapes if sh.role == "tunnel_trench" and sh.ref.startswith("basin_floor:")]


def basin_floor_at_declaration(p: Patch) -> list[Row]:
    """M4b acceptance, RELATIVE since owner RULINGS 2026-09-10ba (spec
    §22.1c): a basin floor vertex stands the facility's published
    ``floor_below_rim_m`` under its NEAREST published RIM vertex, within
    the materiality floor.  The floor follows the rim and the rim follows
    the pavement, so there is no single declared floor left to join to —
    a patch published before 10ba carries no ``floor_below_rim_m`` and is
    judged against its flat ``floor_m`` exactly as before."""
    tol = p.law.tables.emit.materiality.elevation_m
    declared: dict[str, dict] = {}
    for rec in p.publication.get("basin_facilities") or ():
        ref = rec.get("floor_ref")
        try:
            declared[str(ref)] = {"floor_m": float(rec["floor_m"]),
                                  "wall_ref": str(rec.get("wall_ref") or ""),
                                  "depth": (None if rec.get("floor_below_rim_m") is None
                                            else float(rec["floor_below_rim_m"])),
                                  # §24 (5) (owner RULINGS 2026-09-13g): under a
                                  # ramp corridor the floor is the published
                                  # DECK minus the clearance, per station — the
                                  # one depth is not the law there
                                  "clearance": float(rec.get("floor_clearance_m") or 0.0),
                                  "ramp_faces": [[tuple(q) for q in t]
                                                 for t in (rec.get("ramp_faces_ll") or ())],
                                  "ramp_rings": [[tuple(q) for q in r]
                                                 for r in (rec.get("ramp_rings_ll") or ())]}
        except (KeyError, TypeError, ValueError):
            continue
    rims: dict[str, list[tuple[tuple[float, float], float]]] = {}
    floor_ids = {i for sh in _basin_floors(p) for i in sh.ids}
    # the rim is a ``structure_rim`` FEATURE way (09-06b (1)), with the
    # retired ``retaining_wall`` shape read beside it exactly as
    # :func:`wall_in_runway_strip` reads both
    for sh in _rims(p) + [x for x in p.shapes if x.role == "retaining_wall"]:
        key = sh.ref.split("#")[0]
        for k, i in enumerate(sh.ids):
            if i not in floor_ids:
                rims.setdefault(key, []).append((sh.xy[k], float(sh.z[k])))
    out: list[Row] = []
    for f in _basin_floors(p):
        rec = declared.get(f.ref.split("#")[0])
        if rec is None:
            out.append(row("basin_floor_at_declaration", ("tunnel_trench",) * 2, "airside", 0.0,
                           None, None, None, f.xy[0], f.xy[0], f.key, None,
                           out_of_scope=f"{f.ref}: no published facility"))
            continue
        rim = rims.get(rec["wall_ref"]) or []
        for k, z in enumerate(f.z):
            # the corridor is published in LON / LAT: the patch's metres are
            # not the planar frame's, and the join has to be in the one
            # coordinate system both carry
            vlat, vlon = p.ll[f.ids[k]]
            deck = deck_z_on_faces(rec.get("ramp_faces") or (), rec.get("ramp_rings") or (),
                                   vlon, vlat, ring_tol=_RING_TOL_DEG)
            if deck is not None:
                want = deck - rec["clearance"]
                what = f"ramp deck {deck:.2f} - {rec['clearance']:.2f}"
            elif rec["depth"] is not None and rim:
                x, y = f.xy[k]
                rz = min(rim, key=lambda q: (q[0][0] - x) ** 2 + (q[0][1] - y) ** 2)[1]
                want, what = rz - rec["depth"], f"rim {rz:.2f} - {rec['depth']:.2f}"
            else:
                want, what = rec["floor_m"], f"declared {rec['floor_m']:.2f}"
            if abs(z - want) > tol + 1e-9:
                out.append(row("basin_floor_at_declaration", ("tunnel_trench",) * 2, "airside",
                               abs(z - want), None, None, None, f.xy[k], f.xy[k], f.key, None,
                               lat=p.ll[f.ids[k]][0], lon=p.ll[f.ids[k]][1],
                               out_of_scope=f"{f.ref}: {z:.2f} vs {what}"))
    return out


def structure_rim_gap(p: Patch) -> list[Row]:
    """§47 (4) RE-FOUNDED (owner RULINGS 2026-09-17h; supersedes the
    09-06b (1) / 09-08a reading): the rim is the at-grade ring around the
    floor — under §47 (1) it is the wall's OUTER face and the floor ring
    its INNER face, so the DESIGNED band is the wall's own thickness
    ``t``, or the measured lattice floor ``F`` (``cutout.ring_floor_m``)
    where the wall is thinner and the rim yields to it (§47 (3)).  A rim
    vertex never shares an id with a floor / ramp vertex, and never stands
    closer than the designed band to one in plan (the void the mesh makes
    the wall in).  Each miss is a row naming the rim and the floor.

    §47 (4)'s "the bar is the DESIGNED band ``max(t, F)`` per corridor" IS
    REFUTED AS WRITTEN, and this is the measurement (lane ``v2wallface``,
    the §47 ring ladder through ``planar/build``): THE DESIGNED BAND
    CANNOT BE READ BACK OFF THE EMITTED PRODUCT, because the arrangement
    snap-rounds BOTH rings to the 0.5 m identity lattice
    (``planar/overlay.py:441``) and each vertex may move half a cell
    diagonal (0.354 m) toward the other.  Measured, designed band →
    smallest emitted rim-to-floor distance: 0.7071 → 0.500 (the 0.25 and
    0.55 m shells), 1.0000 → 0.707, 2.0000 → 1.803.  A bar of ``max(t, F)
    − materiality`` would report every lawful corridor; a bar of
    ``F − half a diagonal`` is 0.354 m, WEAKER than the identity spacing.
    So the bar stays the identity spacing — what two DISTINCT emitted
    vertices may be, which is exactly the fusion §47 (3) exists to
    prevent.  The rings NEVER fused at any rung of the ladder (shared
    vertices 0 at t = 0.25 / 0.55 / 1.00 / 2.00), and the EXACT band is
    asserted where it is real — on the planar cells, before the
    arrangement, in ``tests/auto_patch_v2/test_v2wallface.py``."""
    gap = p.law.tables.emit.identity.min_distinct_spacing_m
    # the reading's floor: a rim standing AT the stand-off reads 0.2–0.3 mm
    # under it in the patch's own frame (the census reprojects the emitted
    # lat/lon; measured OTHH 2026-09-08: 22 wall-corridor rims at 0.4997 m)
    # — a residual under the owner's materiality is no gap (2026-08-02)
    tol = p.law.tables.emit.materiality.elevation_m
    floors = [sh for sh in p.shapes if sh.role in ("tunnel_trench", "tunnel_ramp", "door_ramp",
                                                   "wall_corridor_ramp", "garage_ramp")]
    if not floors:
        return []
    floor_ids = {v: sh for sh in floors for v in sh.ids}
    cell = max(gap, 1.0)
    g = _grid_pts([(sh.xy[k], sh, k) for sh in floors for k in range(len(sh.ids))], cell)
    out: list[Row] = []
    for r in _rims(p):
        closed = r.feature_closed
        for k, v in enumerate(r.ids):
            if not closed and k in (0, len(r.ids) - 1):
                continue                  # an open rim chain ends on the ramp's top corners
            sh = floor_ids.get(v)
            if sh is not None:
                out.append(row("structure_rim_gap", ("retaining_wall", sh.role), "airside",
                               0.0, None, None, 0.0, r.xy[k], r.xy[k], r.key, sh.key,
                               lat=p.ll[v][0], lon=p.ll[v][1],
                               out_of_scope=f"{r.ref}: rim vertex shared with {sh.ref}"))
                continue
            x, y = r.xy[k]
            cx, cy = int(math.floor(x / cell)), int(math.floor(y / cell))
            worst = None
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for (q, fsh, fk) in g.get((cx + dx, cy + dy), ()):
                        d = _dist((x, y), q)
                        if d < gap - tol and (worst is None or d < worst[0]):
                            worst = (d, fsh, q)
            if worst is not None:
                d, fsh, q = worst
                out.append(row("structure_rim_gap", ("retaining_wall", fsh.role), "airside",
                               gap - d, None, None, d, (x, y), q, r.key, fsh.key,
                               lat=p.ll[v][0], lon=p.ll[v][1],
                               out_of_scope=f"{r.ref}: rim {d:.2f} m off {fsh.ref} < {gap}"))
    return out


def _grid_pts(items, cell: float):
    g: dict[tuple[int, int], list] = {}
    for (x, y), sh, k in items:
        g.setdefault((int(math.floor(x / cell)), int(math.floor(y / cell))), []).append(((x, y), sh, k))
    return g


def _ends(r: Shape) -> list[tuple[tuple[float, float], float]]:
    """The two ends of a ramp piece along its long axis: ``(centre,
    mean z)`` each."""
    n = len(r.xy)
    pa = principal_axis(list(r.xy))
    if pa is None:
        return [((r.xy[0][0], r.xy[0][1]), r.z[0])]
    a, b, _w = pa
    L = _dist(a, b) or 1.0
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    st = [((x - a[0]) * ux + (y - a[1]) * uy) for x, y in r.xy]
    lo, hi = min(st), max(st)
    out = []
    for target in (lo, hi):
        ks = [k for k in range(n) if abs(st[k] - target) <= 2.0]
        out.append(((sum(r.xy[k][0] for k in ks) / len(ks), sum(r.xy[k][1] for k in ks) / len(ks)),
                    sum(r.z[k] for k in ks) / len(ks)))
    return out


def _rim_edges(w: Shape, decks: list[Shape] = (), deck_reach: float = 0.0
               ) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """A rim's edges: every edge of a closed rim; an OPEN chain (a U: it
    ends on the ramp's top corners) without its two end chords — those
    stand at the ramp's top, not at a mouth.  With ``decks`` the edges
    within ``deck_reach`` of a deck ring are left out too: a deck severs
    the ramp and the void alike, and the void's edge along the ramp's
    line up to the deck is the portal under the bridge, never a cap."""
    n = len(w.xy)
    if w.feature_closed:
        edges = [(w.xy[k], w.xy[(k + 1) % n]) for k in range(n)]
    else:
        edges = [(w.xy[k], w.xy[k + 1]) for k in range(1, n - 2)]
    if not decks:
        return edges
    out = []
    for a, b in edges:
        m = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        if all(min(_seg_dist(m[0], m[1], d.xy[i], d.xy[(i + 1) % len(d.xy)])
                   for i in range(len(d.xy))) > deck_reach for d in decks):
            out.append((a, b))
    return out


def _mouth_end(r: Shape, others: list[Shape] = (), walls: list[Shape] = (),
               decks: list[Shape] = (), deck_reach: float = 0.0
               ) -> tuple[tuple[float, float], float]:
    """The ramp's mouth end: the end the wall's END CAP stands across —
    the end whose centre is nearest a wall edge (the cap at the gap; the
    open top end sees only the side bands, half a corridor away).  Not
    the lower end: where the ground beyond a mouth lies below the bore
    floor the ramp DESCENDS outward (the ±cap cone) and its low end is
    the top.  With no walls, the lower end; a piece flat at the datum
    (the covered stretch before a deck) takes the end no other ramp
    piece continues from."""
    ends = _ends(r)
    if len(ends) < 2:
        return ends[0]
    (pa, za), (pb, zb) = ends
    if walls:
        def near(pt):
            best = 1e9
            for w in walls:
                for a, b in _rim_edges(w, decks, deck_reach):
                    best = min(best, _seg_dist(pt[0], pt[1], a, b))
            return best
        da, db = near(pa), near(pb)
        if abs(da - db) > 0.5:
            return (pa, za) if da < db else (pb, zb)
    if abs(za - zb) > 0.02:
        return (pa, za) if za < zb else (pb, zb)
    da = min((min(_dist(pa, q) for q in o.xy) for o in others), default=1e9)
    db = min((min(_dist(pb, q) for q in o.xy) for o in others), default=1e9)
    return (pa, za) if da >= db else (pb, zb)


def tunnel_mouth_canonical(p: Patch) -> list[Row]:
    """THE CANONICAL MOUTH (RULINGS 2026-08-30): per tunnel id (the ramp
    ref's ``tunnel_ramp:<id>``), ONE ramp piece reaches the mouth line
    (the lowest piece), ONE rim answers it on BOTH sides and across the
    mouth (a rim vertex within ``wall_gap_m + wall_band_width_m + 1`` of
    the mouth edge's centre on the far side — the END CAP), and the
    mouth wall node (the rim's cap) stands ``bore_datum_m`` above the
    mouth node (2026-09-03b).  Each miss is a row naming the tunnel."""
    tn = p.law.tables.structures.tunnel
    tol = p.law.tables.emit.materiality.elevation_m
    reach = tn.wall_gap_m + tn.wall_band_width_m + 1.0
    walls = _walls(p)
    decks = _decks(p)
    deck_reach = tn.wall_gap_m + p.law.tables.emit.identity.min_distinct_spacing_m + 1.0
    out: list[Row] = []
    # sites: ramp pieces within the oracle's ``mouth_cluster_m`` (25 m)
    # of each other are one place a bore surfaces
    ramps_all = _ramps(p)
    parent = list(range(len(ramps_all)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(ramps_all)):
        for j in range(i + 1, len(ramps_all)):
            if min(_dist(a, b) for a in ramps_all[i].xy for b in ramps_all[j].xy) <= 25.0:
                parent[find(i)] = find(j)
    by_id: dict[str, list[Shape]] = {}
    for i, r in enumerate(ramps_all):
        by_id.setdefault(f"site{find(i)}", []).append(r)
    # THE OBJECT CORRIDORS (RULINGS 2026-09-05k-1; sidecar ``tunnel_objects``):
    # their mouth is the object's — floor = seat, crest = plate, a mouth
    # at each OPEN end with no cap — so the 09-03b mouth law (cap crest =
    # mouth + bore_datum_m) does not read them; a site whose ramps stand
    # on an object corridor's axis is out of this reader's scope
    obj_axes = []
    for rec in p.publication.get("tunnel_objects") or []:
        pts = [p.to_m(float(la), float(lo)) for la, lo in rec.get("axis_ll", [])]
        if len(pts) >= 2:
            obj_axes.append((pts, float(rec.get("width_m", 0.0)) / 2.0 + reach))

    def on_object(pt) -> bool:
        for pts, half in obj_axes:
            if any(_seg_dist(pt[0], pt[1], pts[k], pts[k + 1]) <= half
                   for k in range(len(pts) - 1)):
                return True
        return False

    for tid, ramps in by_id.items():
        if obj_axes and all(on_object(q) for r in ramps for q in r.xy[:1]):
            continue
        # the mouth piece: the one whose cap-side end is nearest a wall
        cand = [(r, _mouth_end(r, [o for o in ramps if o is not r], walls, decks, deck_reach))
                for r in ramps]
        low, (mouth, zmouth) = min(cand, key=lambda c: min(
            (_seg_dist(c[1][0][0], c[1][0][1], a, b)
             for w in walls for a, b in _rim_edges(w, decks, deck_reach)), default=1e9))
        # the END CAP: a wall EDGE within reach of the mouth line's centre
        # (the cap's vertices stand at the corners, its edge crosses the
        # centre); the wall pieces at the mouth are those with an edge
        # within the corridor's width of it
        near: list[tuple[Shape, int]] = []
        cap: list[tuple[Shape, int]] = []
        for w in walls:
            idx = {(a, b): k for k, (a, b) in enumerate(_rim_edges(w))}
            for (a, b) in _rim_edges(w, decks, deck_reach):
                k = idx[(a, b)]
                d = _seg_dist(mouth[0], mouth[1], a, b)
                kk = k if w.feature_closed else k + 1        # the edge's first vertex index
                if d <= 2.0 * reach + 30.0:
                    near.append((w, kk))
                    near.append((w, (kk + 1) % len(w.xy)))
                if d <= reach + 1.0:
                    cap.append((w, kk))
                    cap.append((w, (kk + 1) % len(w.xy)))
        pieces = {w.key for w, _k in near}
        if not cap:
            out.append(row("tunnel_mouth_canonical", ("tunnel_ramp", "retaining_wall"), "mixed",
                           0.0, None, None, None, mouth, mouth, low.key, None,
                           out_of_scope=f"{tid}: no end cap across the mouth"))
            continue
        # the MOUTH WALL NODE stands bore_datum_m above the mouth node
        # (09-03b): the cap edge's value at the point nearest the mouth
        # line's centre, interpolated along that edge (the crest follows
        # the DEM ACROSS the cap — SPJC's cap spans 0.5 m of relief)
        want = zmouth + tn.bore_datum_m
        best = None
        for w, k in cap:
            n = len(w.xy)
            a, b = w.xy[k], w.xy[(k + 1) % n]
            d = _seg_dist(mouth[0], mouth[1], a, b)
            if best is None or d < best[0]:
                vx, vy = b[0] - a[0], b[1] - a[1]
                l2 = vx * vx + vy * vy
                t = 0.0 if l2 < 1e-18 else max(0.0, min(1.0, ((mouth[0] - a[0]) * vx
                                                              + (mouth[1] - a[1]) * vy) / l2))
                best = (d, w.z[k] * (1 - t) + w.z[(k + 1) % n] * t)
        worst = abs(best[1] - want) if best else 0.0
        # the instrument envelope: the rate readers' quantum (the mouth
        # centre is a cluster mean; the cap crest is interpolated)
        if worst > p.law.tables.emit.instrument.coarse_noise_m:
            out.append(row("tunnel_mouth_canonical", ("tunnel_ramp", "retaining_wall"), "mixed",
                           worst, None, None, None, mouth, mouth, low.key, cap[0][0].key,
                           out_of_scope=f"{tid}: mouth wall {best[1]:.2f} vs ramp mouth "
                                        f"{zmouth:.2f} + {tn.bore_datum_m}"))
        if len(pieces) > 1:
            out.append(row("tunnel_mouth_canonical", ("retaining_wall",) * 2, "airside",
                           float(len(pieces)), None, None, None, mouth, mouth, low.key, None,
                           out_of_scope=f"{tid}: {len(pieces)} wall pieces at the mouth"))
        at_mouth = [r for r in ramps
                    if _dist(_mouth_end(r, [o for o in ramps if o is not r], walls, decks,
                                        deck_reach)[0], mouth) <= 25.0]
        if len(at_mouth) > 1:
            out.append(row("tunnel_mouth_canonical", ("tunnel_ramp",) * 2, "groundside",
                           float(len(at_mouth)), None, None, None, mouth, mouth, low.key, None,
                           out_of_scope=f"{tid}: {len(at_mouth)} ramp pieces at the mouth"))
    return out


def tunnel_deck_clearance(p: Patch) -> list[Row]:
    """2026-08-30c §4 / 08-30f: a deck stands ``bridge.clearance_m`` above
    the ramp abutting it — the lowest deck vertex vs the highest ramp
    vertex within the gap + 2 m of the deck ring."""
    br = p.law.tables.structures.bridge
    gap = p.law.tables.structures.tunnel.wall_gap_m
    tol = p.law.tables.emit.materiality.elevation_m
    out: list[Row] = []
    ramps = _ramps(p)
    for d in _decks(p):
        n = len(d.xy)
        zs = []
        for r in ramps:
            for k in range(len(r.ids)):
                x, y = r.xy[k]
                if min(_seg_dist(x, y, d.xy[i], d.xy[(i + 1) % n]) for i in range(n)) <= gap + 2.0:
                    zs.append(r.z[k])
        if not zs:
            continue
        clear = min(d.z) - max(zs)
        if clear < br.clearance_m - tol:
            out.append(row("tunnel_deck_clearance", ("service_road", "tunnel_ramp"), "groundside",
                           br.clearance_m - clear, None, None, None, d.xy[0], d.xy[0], d.key, None,
                           out_of_scope=f"{d.ref}: clearance {clear:.2f} < {br.clearance_m}"))
    return out


#: The acceptance readers, keyed as the census publishes them.
ACCEPTANCE = {
    "tunnel_mouth_canonical": tunnel_mouth_canonical,
    "tunnel_deck_clearance": tunnel_deck_clearance,
    "basin_floor_at_declaration": basin_floor_at_declaration,
    "structure_rim_gap": structure_rim_gap,
}
