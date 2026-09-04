"""THE DECK SIGNATURE BY GEOMETRY (RULINGS 2026-09-04k; lane v2deck, M6b).

``ATTR_hard_deck`` is the PRIMARY deck signature (``airport/obj8.py``
reads it).  OTHH's ``Bridge_0x`` objects carry no hard attribute at all
(0 hard triangles in 60 files), so v2's deck law had nothing to govern
and the feet law seated them on the canal bank (+5.585 m where the owner
accepted +0.958).  v1 recognised them by a resource-path token
(``COSMETIC_BRIDGE_NAME_HINT = "bridge"``) — a name, not geometry.  This
module reads the geometry:

* A FAMILY is every placement sharing one anchor spelling (memory
  ``shared-datum-pack-authoring``: one datum, one rigid body; the same
  identity ``airport/rebake_plan.py`` seats by).  A family with a flagged
  member keeps the primary signature untouched.
* Its DECK PLANE is the largest-area bin (``deck_plane_bin_m``) of
  near-horizontal solid faces (``deck_plate_normal_y_min``) standing
  ``deck_min_elevation_m`` or more above the family's lowest feet — the
  reading v1's ``_dominant_height_plane`` made, which is the reading
  behind the R12 seats the owner accepted in the sim (2026-08-11).  The
  bins are of EFFECTIVE height (authored ``y`` + the placement's AGL,
  the height over the anchor's draped plane), as v1's were: the bin
  boundaries decide which kerb faces join the deck top (OTHH Bridge_04:
  the 4.83–4.87 kerb strip joins the 4.65 plate under effective
  binning and reads 4.868 — the accepted crest — where authored binning
  cuts it off at 4.654).  The plane must carry ``deck_min_area_m2`` of
  face.
* Per member, its PLATE is the union of its plane faces, closed at
  ``deck_close_m``; the plate's minimum rotated rectangle gives the deck
  AXIS and its two END LINES (the abutments, where the seat reads the
  ground — R12: the deck TOP lands at the abutment grade); its DECK TOP
  is the highest corner of its plane faces; its PROFILE is the highest
  near-horizontal corner per ``deck_profile_bin_m`` along the axis over
  the near-horizontal faces of the plate's OWN solid components (a ramp
  runs down from the plane to the ground within one component); its
  STATIONS are near-horizontal faces of those components spread along
  the axis — after the seat, the mesh under SOME station must lie
  ``deck_min_clearance_under_m`` under the seated face or be water: a
  bridge stands over something lower than itself (a ramp's stations
  run out over the canal), an elevated kerb road or a canopy over the
  ground it is built on does not, and the feet law governs it.  A plate shorter than ``deck_min_span_m``
  carries no end lines (a kerb piece founds nothing; it still seats
  with its family).
* THE SPANNING EVIDENCE decides: a plate is a deck only when it spans
  something the terrain cannot carry — a mapped bridge way (highway /
  railway with ``bridge != no``) crossing the family's plates, or an
  emitted below-grade region (a basin, a tunnel ramp) under them
  (``deck_spanning_evidence``).  A roof and a canopy are plates too; the
  evidence refuses them.  A plate without evidence is a CANDIDATE: the
  tunnel pass promotes one that crosses its ramp
  (``planar/structures.py``), the re-seat plan one over a basin.

Nothing here reads the DEM or the mesh: at OTHH the pack is authored
with its y = 0 plane at the canal (anchors over water), so in ANY frame
the authored deck ends stand 4 m under the land the DEM shows there —
that gap IS what the post-mesh seat closes; no plan-time ground test
can see a bridge.  Every number is an argument from ``structures.toml
[bridge]``; no environment is read.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import shapely
from shapely import affinity as _affinity
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..model.frame import XY
from . import obj8 as _obj8

__all__ = ["DeckPlate", "DeckFamily", "DeckReport", "classify", "promote",
           "is_bridge_way", "bridge_lines", "family_key"]

EVIDENCE_ROAD_BRIDGE = "road_bridge"
EVIDENCE_BELOW_GRADE = "below_grade"


@_dc.dataclass(frozen=True)
class DeckPlate:
    """One member's plate, in the airport frame (``ends`` / ``profile``
    are what ``emit/rebake.py`` reads; ``profile`` is ``(s, y)`` with
    ``s`` metres from the START end's midpoint along the axis and ``y``
    the authored deck-top height there)."""

    object_id: str
    path: str
    footprint: object                       # Polygon | MultiPolygon, frame
    rect: object                            # the plate's minimum rotated rectangle, frame
    axis: tuple[XY, XY]                     # (origin, unit) of the axis, frame
    ends: tuple[tuple[XY, XY], tuple[XY, XY]] | None
    length_m: float
    width_m: float
    area_m2: float
    deck_top_y: float
    plane_y: float
    elevation_above_feet_m: float
    profile: tuple[tuple[float, float], ...]
    evidence: tuple[str, ...]
    #: THE STATIONS: plan positions (frame) and authored heights of near-
    #: horizontal faces of the plate's own components, spread along the
    #: axis (at most ``deck_stations``) — where the seat asks "does this
    #: deck stand over something lower than itself?" (a ramp's stations
    #: run out over the canal; a kerb road's stand over the ground it is
    #: built on).
    stations: tuple[tuple[XY, float], ...] = ()


@_dc.dataclass(frozen=True)
class DeckFamily:
    key: tuple[float, float, float]
    members: tuple[str, ...]
    plates: tuple[str, ...]
    plane_y: float | None
    plane_area_m2: float
    spans: tuple[str, ...]
    accepted: bool
    note: str


@_dc.dataclass
class DeckReport:
    families: int = 0
    flagged_families: int = 0
    accepted: int = 0
    candidates: int = 0
    refused: dict[str, str] = _dc.field(default_factory=dict)
    records: list[DeckFamily] = _dc.field(default_factory=list)


# ── identity ─────────────────────────────────────────────────────────────

def family_key(o: _obj8.PlacedObject) -> tuple[float, float, float]:
    """One anchor spelling: frame position to the millimetre + AGL
    (canonical identity, never proximity)."""
    return (round(o.xy[0], 3), round(o.xy[1], 3), round(o.agl_m, 3))


def is_bridge_way(tags: _t.Mapping[str, str]) -> bool:
    """A mapped bridge: ``bridge`` set and not ``no`` on a highway or
    railway (the one predicate ``planar/structures.py`` uses too)."""
    b = tags.get("bridge")
    return bool(b) and b != "no" and ("highway" in tags or "railway" in tags)


def bridge_lines(osm_ways) -> list[tuple[int, LineString]]:
    out = []
    for w in osm_ways:
        if is_bridge_way(w.tags) and len(w.points) >= 2:
            try:
                out.append((w.id, LineString(w.points)))
            except (ValueError, TypeError):
                continue
    return out


# ── faces ────────────────────────────────────────────────────────────────

class _Faces:
    """Per resource, every solid triangle's plan ring (authored ``x, z``),
    mean height, top corner, plan area and |normal_y| — read once."""

    def __init__(self, geom: _obj8.ObjGeometry) -> None:
        v = geom.vertices
        t = geom.solid
        if t.shape[0] == 0:
            self.n = 0
            return
        p0, p1, p2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
        nrm = np.cross(p1 - p0, p2 - p0)
        ln = np.linalg.norm(nrm, axis=1)
        ok = ln > 1e-12
        # UNSIGNED, as v1 read it: OTHH's decks are not consistently wound
        # (signed normals move the interchange's plane from 3.0 to 1.0 and
        # break the accepted crests); a slab's underside ties its top in
        # area, and the tie rule below prefers the higher bin
        self.ny = np.zeros(t.shape[0])
        self.ny[ok] = np.abs(nrm[ok, 1] / ln[ok])
        self.cy = (p0[:, 1] + p1[:, 1] + p2[:, 1]) / 3.0
        self.ymax = np.maximum(np.maximum(p0[:, 1], p1[:, 1]), p2[:, 1])
        self.area = 0.5 * np.abs((p1[:, 0] - p0[:, 0]) * (p2[:, 2] - p0[:, 2])
                                 - (p2[:, 0] - p0[:, 0]) * (p1[:, 2] - p0[:, 2]))
        self.xz = np.stack([np.stack([p0[:, 0], p0[:, 2]], axis=1),
                            np.stack([p1[:, 0], p1[:, 2]], axis=1),
                            np.stack([p2[:, 0], p2[:, 2]], axis=1)], axis=1)
        self.n = int(t.shape[0])


def _rings(f: _Faces, idx: np.ndarray) -> list[list[tuple[float, float]]]:
    return [[(float(x), float(z)) for x, z in f.xz[i]] for i in idx.tolist()]


def _rect_axis(poly) -> tuple[XY, XY, float, float, tuple[tuple[XY, XY], tuple[XY, XY]]] | None:
    """``(origin, unit, length, width, (start end line, far end line))`` of
    the polygon's minimum rotated rectangle, the axis canonicalised on
    +x (tie on +z) so the end order is a property of the geometry."""
    try:
        rect = poly.minimum_rotated_rectangle
    except Exception:
        return None
    if rect.geom_type != "Polygon":
        return None
    c = list(rect.exterior.coords)[:4]
    if len(c) < 4:
        return None
    edges = [(c[i], c[(i + 1) % 4]) for i in range(4)]
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in edges]
    li = max(range(4), key=lambda i: lens[i])
    length = lens[li]
    if length <= 0.0:
        return None
    a, b = edges[li]
    unit = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
    if unit[0] < 0.0 or (unit[0] == 0.0 and unit[1] < 0.0):
        a, b = b, a
        unit = (-unit[0], -unit[1])
    order = sorted(range(4), key=lambda i: lens[i])
    shorts = [edges[order[0]], edges[order[1]]]

    def _proj(e):
        mx, mz = (e[0][0] + e[1][0]) / 2.0, (e[0][1] + e[1][1]) / 2.0
        return (mx - a[0]) * unit[0] + (mz - a[1]) * unit[1]
    shorts.sort(key=_proj)
    ends = tuple(((float(e[0][0]), float(e[0][1])), (float(e[1][0]), float(e[1][1])))
                 for e in shorts)
    return (float(a[0]), float(a[1])), unit, float(length), float(min(lens)), ends  # type: ignore[return-value]


def _profile(f: _Faces, near: np.ndarray, origin: XY, unit: XY, length: float,
             width: float, bin_m: float) -> tuple[tuple[float, float], ...]:
    """Highest near-horizontal corner per ``bin_m`` along the axis, over
    the faces whose centroid lies within the rectangle's width band;
    empty bins interpolate between neighbours (v1 ``_deck_top_profile``)."""
    if not near.any() or length <= 0.0:
        return ()
    cx = f.xz[near, :, 0].mean(axis=1)
    cz = f.xz[near, :, 1].mean(axis=1)
    s = (cx - origin[0]) * unit[0] + (cz - origin[1]) * unit[1]
    across = -(cx - origin[0]) * unit[1] + (cz - origin[1]) * unit[0]
    inside = (s >= -bin_m) & (s <= length + bin_m) & (np.abs(across) <= width)
    if not inside.any():
        return ()
    ys = f.ymax[near][inside]
    ss = s[inside]
    nb = max(1, int(math.ceil(length / bin_m)))
    best: dict[int, float] = {}
    for si, yi in zip(ss.tolist(), ys.tolist()):
        k = min(nb - 1, max(0, int(si / length * nb))) if length > 0 else 0
        if k not in best or yi > best[k]:
            best[k] = yi
    filled = sorted(best)
    out = []
    for k in range(nb):
        sc = (k + 0.5) * length / nb
        if k in best:
            out.append((sc, best[k]))
            continue
        lo = [i for i in filled if i < k]
        hi = [i for i in filled if i > k]
        if lo and hi:
            frac = (k - lo[-1]) / (hi[0] - lo[-1])
            out.append((sc, best[lo[-1]] + frac * (best[hi[0]] - best[lo[-1]])))
        elif lo:
            out.append((sc, best[lo[-1]]))
        else:
            out.append((sc, best[hi[0]]))
    return tuple(out)


# ── the signature ────────────────────────────────────────────────────────

def classify(objects: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache, law,
             bridges: _t.Sequence[tuple[int, LineString]] = (),
             below_grade: _t.Sequence = ()) -> tuple[list[_obj8.PlacedObject], DeckReport]:
    """The objects with the signature applied (see module doc) and the
    report.  ``bridges`` are ``(way id, LineString)`` in the frame;
    ``below_grade`` frame polygons of emitted below-grade regions."""
    br = law.tables.structures.bridge
    rep = DeckReport()
    faces: dict[str, _Faces | None] = {}

    def _faces_of(path: str) -> _Faces | None:
        if path not in faces:
            g = cache.geometry(path)
            faces[path] = _Faces(g) if g is not None else None
        return faces[path]

    fams: dict[tuple[float, float, float], list[int]] = {}
    for i, o in enumerate(objects):
        if o.resolved is None or o.kind == "OBJECT_MSL" or _obj8.is_stock_library_resource(o.path):
            continue
        fams.setdefault(family_key(o), []).append(i)
    out = list(objects)
    for key in sorted(fams):
        idx = fams[key]
        members = [objects[i] for i in idx]
        rep.families += 1
        if any(o.hard_deck is not None for o in members):
            rep.flagged_families += 1
            continue
        fam, plates = _read_family(members, cache, _faces_of, br, key)
        if fam is None:
            continue
        spans = _spans(plates, bridges, below_grade, br.deck_way_cover_min)
        accepted = bool(set(spans) & set(br.deck_spanning_evidence))
        rec = DeckFamily(key, tuple(o.id for o in members), tuple(sorted(plates)),
                         fam[0], fam[1], tuple(spans), accepted,
                         "" if accepted else "no spanning evidence: candidate")
        rep.records.append(rec)
        if accepted:
            rep.accepted += 1
        else:
            rep.candidates += 1
        for i, o in zip(idx, members):
            out[i] = _apply(o, plates.get(o.id), rec)
    return out, rep


def _read_family(members, cache, faces_of, br, key):
    """``((plane_y, plane_area), {object id: DeckPlate})`` or ``(None, {})``
    when the family carries no plate."""
    floor = math.inf
    for o in members:
        comps = cache.genuine(o.resolved) or cache.components(o.resolved)
        for c in comps:
            floor = min(floor, c.min_y)
    if not math.isfinite(floor):
        return None, {}
    sel: dict[str, np.ndarray] = {}
    area_by_bin: dict[int, float] = {}
    for o in members:
        f = faces_of(o.resolved)
        if f is None or f.n == 0:
            continue
        m = (f.ny >= br.deck_plate_normal_y_min) & (f.cy >= floor + br.deck_min_elevation_m)
        if not m.any():
            continue
        sel[o.id] = m
        keys = np.round((f.cy[m] + o.agl_m) / br.deck_plane_bin_m).astype(int)
        for k, a in zip(keys.tolist(), f.area[m].tolist()):
            area_by_bin[k] = area_by_bin.get(k, 0.0) + a
    if not area_by_bin:
        return None, {}
    # the dominant bin; a bin within ``deck_plane_area_tie`` of the
    # largest is a TIE (a slab's underside against its top, pier tops
    # thrown in) and the HIGHER bin is the deck top
    top_area = max(area_by_bin.values())
    dom = max(k for k, a in area_by_bin.items() if a >= br.deck_plane_area_tie * top_area)
    plane_area = area_by_bin[dom]
    if plane_area < br.deck_min_area_m2:
        return None, {}
    wsum = asum = 0.0
    plates: dict[str, DeckPlate] = {}
    for o in members:
        m = sel.get(o.id)
        if m is None:
            continue
        f = faces_of(o.resolved)
        inplane = m & (np.round((f.cy + o.agl_m) / br.deck_plane_bin_m).astype(int) == dom)
        if not inplane.any():
            continue
        wsum += float((f.cy[inplane] * f.area[inplane]).sum())
        asum += float(f.area[inplane].sum())
        pl = _plate(o, f, inplane, floor, br, cache.components(o.resolved))
        if pl is not None:
            plates[o.id] = pl
    if not plates:
        return None, {}
    plane_y = wsum / asum if asum > 0 else float(dom) * br.deck_plane_bin_m - members[0].agl_m
    plates = {k: _dc.replace(p, plane_y=plane_y) for k, p in plates.items()}
    return (plane_y, plane_area), plates


def _plate(o, f: _Faces, inplane: np.ndarray, floor: float, br, comps) -> DeckPlate | None:
    idx = np.nonzero(inplane)[0]
    u = _obj8._union_rings(_rings(f, idx))
    if u is None:
        return None
    closed = u.buffer(br.deck_close_m).buffer(-br.deck_close_m)
    if closed.is_empty:
        closed = u
    ax = _rect_axis(closed)
    if ax is None:
        return None
    origin, unit, length, width, ends_a = ax
    top = float(f.ymax[inplane].max())
    own = np.zeros(f.n, dtype=bool)
    for c in comps:
        if c.idx is not None and inplane[c.idx].any():
            own[c.idx] = True
    if not own.any():
        own = inplane
    near = own & (f.ny >= br.deck_plate_normal_y_min)
    prof = _profile(f, near, origin, unit, length, width, br.deck_profile_bin_m)
    stations: list[tuple[tuple[float, float], float]] = []
    if near.any():
        ids = np.nonzero(near)[0]
        cx = f.xz[ids, :, 0].mean(axis=1)
        cz = f.xz[ids, :, 1].mean(axis=1)
        sa = (cx - origin[0]) * unit[0] + (cz - origin[1]) * unit[1]
        order = ids[np.argsort(sa)]
        pick = np.linspace(0, order.shape[0] - 1, min(order.shape[0], br.deck_stations)
                           ).round().astype(int)
        for k in order[pick].tolist():
            stations.append(((float(f.xz[k, :, 0].mean()), float(f.xz[k, :, 1].mean())),
                             float(f.ymax[k])))
    mat = _obj8.placement_affine(o.xy, o.heading_deg)
    tf = _affinity.affine_transform
    foot = tf(closed, mat)
    if not foot.is_valid:
        foot = foot.buffer(0)
    rect = tf(closed.minimum_rotated_rectangle, mat)
    o_f = tf(shapely.points(*origin), mat)
    u_f = tf(shapely.points(origin[0] + unit[0], origin[1] + unit[1]), mat)
    axis_f = ((o_f.x, o_f.y), (u_f.x - o_f.x, u_f.y - o_f.y))
    ends = None
    if length >= br.deck_min_span_m:
        pts = [tf(shapely.points(x, z), mat) for e in ends_a for x, z in e]
        ends = (((pts[0].x, pts[0].y), (pts[1].x, pts[1].y)),
                ((pts[2].x, pts[2].y), (pts[3].x, pts[3].y)))
    ev = (f"plate: {float(f.area[inplane].sum()):.0f} m2 of near-horizontal face "
          f"(normal_y >= {br.deck_plate_normal_y_min}) in the family's deck plane",
          f"deck top y {top:.3f} authored, {top - floor:.2f} m above the family's lowest "
          f"feet (>= {br.deck_min_elevation_m})",
          f"axis {length:.1f} m x {width:.1f} m"
          + ("" if ends is not None else f" (< {br.deck_min_span_m} m: no abutment end lines)"))
    st_f = []
    for (sx, sz), sy in stations:
        sp = tf(shapely.points(sx, sz), mat)
        st_f.append(((sp.x, sp.y), sy))
    return DeckPlate(o.id, o.path, foot, rect, axis_f, ends, length, width,
                     float(f.area[inplane].sum()), top, 0.0, top - floor, prof, ev, tuple(st_f))


def way_cover(pl: DeckPlate, line: LineString) -> float:
    """How much of the plate's length a mapped way RUNS ALONG: the sum
    of the axis projections of the way's pieces inside the plate's
    rectangle, over the plate length (a way crossing a terminal slab
    transversally projects ~0 along the slab's axis; the trunk road on
    OTHH Bridge_05 reads 0.97)."""
    if pl.ends is None or pl.length_m <= 0.0:
        return 0.0
    seg = line.intersection(pl.rect)
    if seg.is_empty:
        return 0.0
    (ox, oy), (ux, uy) = pl.axis
    total = 0.0
    for part in shapely.get_parts(seg):
        if part.geom_type != "LineString":
            continue
        c = list(part.coords)
        for (x0, y0), (x1, y1) in zip(c[:-1], c[1:]):
            total += abs((x1 - x0) * ux + (y1 - y0) * uy)
    return total / pl.length_m


def _spans(plates: dict[str, DeckPlate], bridges, below_grade, cover_min: float) -> list[str]:
    if not plates:
        return []
    fp = unary_union([p.footprint for p in plates.values()])
    spans: list[str] = []
    carried: list[tuple[int, str, float]] = []
    for wid, ln in bridges:
        for p in plates.values():
            c = way_cover(p, ln)
            if c >= cover_min:
                carried.append((wid, p.path.rsplit("/", 1)[-1], c))
    if carried:
        spans.append(EVIDENCE_ROAD_BRIDGE)
        spans.append(f"{EVIDENCE_ROAD_BRIDGE}: mapped bridge way(s) run along the plate — "
                     + "; ".join(f"way {w} on {r} ({c:.0%} of its length)"
                                 for w, r, c in carried[:4]))
    hits = sum(1 for r in below_grade if r is not None and r.intersects(fp))
    if hits:
        spans.append(EVIDENCE_BELOW_GRADE)
        spans.append(f"{EVIDENCE_BELOW_GRADE}: {hits} emitted below-grade region(s) under the plate")
    return spans


def _apply(o: _obj8.PlacedObject, pl: DeckPlate | None, rec: DeckFamily) -> _obj8.PlacedObject:
    fam_ev = tuple(s for s in rec.spans if ": " in s) or ("no spanning evidence",)
    if pl is None:
        if not rec.accepted:
            return o
        return _dc.replace(o, deck_kind="family",
                           deck_evidence=("member of a deck family (no plate of its own): "
                                          "seats with its deck",) + fam_ev)
    if rec.accepted:
        return _dc.replace(o, hard_deck=pl.footprint,
                           deck_top_z=o.anchor_z + o.agl_m + pl.deck_top_y,
                           deck_kind="signature", deck_plate=pl,
                           deck_evidence=pl.evidence + fam_ev)
    return _dc.replace(o, deck_kind="candidate", deck_plate=pl,
                       deck_evidence=pl.evidence + fam_ev)


def promote(objects: _t.Sequence[_obj8.PlacedObject], regions: _t.Sequence,
            note: str = EVIDENCE_BELOW_GRADE) -> tuple[list[_obj8.PlacedObject], int]:
    """Candidate families whose plates cross one of ``regions`` (frame
    polygons of emitted below-grade structures) become decks; returns the
    objects and the number of families promoted."""
    regs = [r for r in regions if r is not None and not r.is_empty]
    if not regs:
        return list(objects), 0
    fams: dict[tuple[float, float, float], list[int]] = {}
    for i, o in enumerate(objects):
        if o.deck_kind in ("candidate", "family") or (o.deck_kind == "" and o.resolved):
            fams.setdefault(family_key(o), []).append(i)
    out = list(objects)
    n = 0
    for key, idx in fams.items():
        cands = [objects[i] for i in idx if objects[i].deck_kind == "candidate"]
        if not cands:
            continue
        fp = unary_union([c.deck_plate.footprint for c in cands])
        hits = sum(1 for r in regs if r.intersects(fp))
        if not hits:
            continue
        n += 1
        ev = (f"{note}: {hits} emitted below-grade region(s) under the plate",)
        rec = DeckFamily(key, tuple(objects[i].id for i in idx),
                         tuple(c.id for c in cands), cands[0].deck_plate.plane_y, 0.0,
                         (note,) + ev, True, "")
        for i in idx:
            o = objects[i]
            out[i] = _apply(o, o.deck_plate if o.deck_kind == "candidate" else None, rec)
    return out, n
