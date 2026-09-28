"""THE RIDERS (spec ``docs/specs/jetway-strip-spec.md`` §1 (1) and §4;
owner RULINGS 2026-09-18t (2)/(3), issues #31/#32).

A RIDER is a placement the plan holds NO GEOMETRY for — an ``.agp``, a
multi-anchor resource the pack partition dropped, a ``lib/`` resource,
anything the partition skipped — standing within ``rider_reach`` of a
unit's outline.  It is never a body (never in the contact graph, the
groups, the clusters or the plan's bodies, F.2); it is a SEAT RECORD on
its carrier, re-seated on write.  Name-free: the marshaller 40 m out
never rides, whatever it is called.

Two halves, one module:

* the DESIGN side (:func:`rider_candidates`) — per candidate placement
  its ``rider_reach``.  An ``.agp`` (a format class with gate logic, not
  a name — 18t holds) reaches ``[placement] rider_reach_max_m`` (12 m), a
  floor as well as a cap, and hosts a pad it stands INSIDE at gap 0
  (spec-author rulings on #31, 2026-09-28, (a)/(b), ``.agp`` ONLY).
  Every other rider keeps ``max(footprint_touch_m, declared plan
  half-extent)`` capped at the same 12 m (the OBJ8 plan box).
  ``constraints/jetway_strip`` reads it (it may not read files itself) to
  find the rider edges.
* the WRITE side (:func:`riders_for_dump`) — the §4 ``Rider`` seat
  records against the design surface the build emitted: ON GROUND where
  the terrain at the anchor already equals the host unit's datum within
  ``hard_tol_m`` (after the strip law, the normal case), ``OBJECT_MSL``
  = datum + authored offset only on a CLAMPED gate, and never for an
  ``.agp`` (spec §4 (3) / Q6 default: whether X-Plane honours
  ``OBJECT_MSL`` for an ``.agp`` is unverified, so the strip is its seat).
"""
from __future__ import annotations

import math
import os
import typing as _t

from ..law import Law
from . import obj8 as _obj8

__all__ = ["rider_candidates", "agp_half_extent_m", "obj_half_extent_m",
           "riders_for_dump", "rider_census", "SEAT_WHY"]

#: §4 (1): how a rider row is seated.
SEAT_WHY = ("on_ground", "msl_written", "no_host")

_EXTENT_MEMO: dict[str, float | None] = {}


def agp_half_extent_m(path: str) -> float | None:
    """The ``.agp``'s own declared plan half-extent in metres: the
    ``TILE s1 t1 s2 t2`` rectangle about its ``ANCHOR_PT``, in texture
    units scaled to metres by ``TEXTURE_WIDTH / TEXTURE_SCALE``.  HECA's
    ``HECA_Jetway_No_glass.agp``: ``TILE -5 -5 5 5``, scale 10, width 10
    -> 5.0 m.  ``None`` when the file carries no ``TILE``."""
    if path in _EXTENT_MEMO:
        return _EXTENT_MEMO[path]
    tile = anchor = None
    scale_s = width = None
    try:
        with open(path, "r", encoding="latin-1", errors="replace") as fh:
            for ln in fh:
                t = ln.split()
                if not t:
                    continue
                k = t[0]
                try:
                    if k == "TILE" and len(t) >= 5 and tile is None:
                        tile = tuple(float(x) for x in t[1:5])
                    elif k == "ANCHOR_PT" and len(t) >= 3 and anchor is None:
                        anchor = (float(t[1]), float(t[2]))
                    elif k == "TEXTURE_SCALE" and len(t) >= 2:
                        scale_s = float(t[1])
                    elif k == "TEXTURE_WIDTH" and len(t) >= 2:
                        width = float(t[1])
                except ValueError:
                    continue
    except OSError:
        _EXTENT_MEMO[path] = None
        return None
    if tile is None:
        _EXTENT_MEMO[path] = None
        return None
    ax, ay = anchor or (0.0, 0.0)
    units = max(abs(tile[0] - ax), abs(tile[2] - ax),
                abs(tile[1] - ay), abs(tile[3] - ay))
    m_per_unit = (width / scale_s) if (width and scale_s) else 1.0
    got = float(units * m_per_unit)
    _EXTENT_MEMO[path] = got
    return got


def obj_half_extent_m(path: str) -> float | None:
    """The OBJ8's plan half-extent about its origin: the largest ``|x|`` /
    ``|z|`` over its vertices (the plan box, authored frame).  ``None``
    for an unreadable file."""
    if path in _EXTENT_MEMO:
        return _EXTENT_MEMO[path]
    try:
        g = _obj8.parse_obj8(path)
    except (OSError, ValueError):
        _EXTENT_MEMO[path] = None
        return None
    v = g.vertices
    got = (float(max(abs(v[:, 0]).max(), abs(v[:, 2]).max()))
           if v.shape[0] else None)
    _EXTENT_MEMO[path] = got
    return got


def _no_geometry_paths(airport: _t.Any) -> tuple[frozenset[str], frozenset[str]]:
    """``(skipped, members)``: the resource paths the pack partition held
    no body for, and those it did.  A path in both (a plate re-added by
    ``extend_partition``) has geometry."""
    part = getattr(airport, "partition", None)
    if part is None:
        return frozenset(), frozenset()
    skipped = frozenset(p for p, _why in (getattr(part, "skipped", ()) or ()))
    members = frozenset(str(v[1]) for v in
                        (getattr(part, "member_object", None) or {}).values()
                        if isinstance(v, tuple) and len(v) > 1)
    return skipped, members


def rider_candidates(airport: _t.Any, law: Law) -> dict[str, tuple[float, str]]:
    """``DsfObject.id -> (rider_reach_m, kind)`` for every placement the
    plan holds no geometry for (spec §1 (1)): ``kind`` is ``agp`` /
    ``lib`` / ``skipped``.

    THE REACH (spec-author rulings on #31, 2026-09-28; owner RULINGS
    2026-09-28a (3)): an ``.agp`` reaches ``rider_reach_max_m`` — a floor
    as well as a cap, whatever its ``TILE`` says (the 5 m TILE left HECA's
    No_glass at 7.92 m and three LEMD ``LEMD_Jetway_alt`` at 6.8-8.5 m
    unhosted) — and ``constraints/jetway_strip.rider_hosts`` seats an
    ``.agp`` standing INSIDE a pad at gap 0.  ``.agp`` ONLY: every other
    rider keeps ``max(footprint_touch_m, declared plan half-extent)``
    capped at ``rider_reach_max_m``; one whose extent cannot be read keeps
    ``footprint_touch_m`` — the 0.5 m anchor rule of F.5 (1), never a
    guess.  ONE site: this is where every rider's reach is born."""
    pl = law.tables.structures.placement
    touch = float(pl.footprint_touch_m)
    cap = float(pl.rider_reach_max_m)
    skipped, members = _no_geometry_paths(airport)
    out: dict[str, tuple[float, str]] = {}
    for o in getattr(airport, "dsf_objects", ()) or ():
        p = o.path
        low = p.lower()
        if low.endswith(".agp"):
            kind = "agp"
        elif _obj8.is_stock_library_resource(p):
            kind = "lib"
        elif p in skipped and p not in members:
            kind = "skipped"
        else:
            continue
        if kind == "agp":
            out[o.id] = (max(touch, cap), kind)
            continue
        ext = None
        rp = getattr(o, "resolved_path", None)
        if rp and os.path.isfile(rp):
            ext = obj_half_extent_m(rp)
        reach = min(cap, max(touch, float(ext) if ext is not None
                             and math.isfinite(ext) else touch))
        out[o.id] = (reach, kind)
    return out


# ── §4 THE WRITE SIDE ────────────────────────────────────────────────────

def _ring_dist_m(lat: float, lon: float, ring: _t.Sequence[tuple[float, float]]
                 ) -> float:
    """Plan distance in metres from ``(lat, lon)`` to a ``(lat, lon)``
    ring's outline (equirectangular about the point — rings are a few km)."""
    ky = 111_320.0
    kx = ky * math.cos(math.radians(lat))
    pts = [((b - lon) * kx, (a - lat) * ky) for a, b in ring]
    best = math.inf
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 <= 0.0 else max(0.0, min(1.0, -(x0 * dx + y0 * dy) / L2))
        best = min(best, math.hypot(x0 + t * dx, y0 + t * dy))
    return best


def _inside(lat: float, lon: float, ring: _t.Sequence[tuple[float, float]]) -> bool:
    c = False
    n = len(ring)
    for i in range(n):
        (a0, b0), (a1, b1) = ring[i], ring[(i + 1) % n]
        if (a0 > lat) != (a1 > lat):
            x = b0 + (lat - a0) * (b1 - b0) / (a1 - a0)
            if lon < x:
                c = not c
    return c


def _gate_clamped(lat: float, lon: float, clamps: _t.Sequence[_t.Any],
                  gate_m: float | None) -> bool:
    """Is a clamp ``[lat, lon, why, metres]`` of the strip within
    ``gate_m`` of this anchor (any clamp at all when ``gate_m`` is
    ``None``)?"""
    if gate_m is None:
        return bool(clamps)
    ky = 111_320.0
    kx = ky * math.cos(math.radians(lat))
    for c in clamps:
        try:
            d = math.hypot((float(c[1]) - lon) * kx, (float(c[0]) - lat) * ky)
        except (TypeError, ValueError, IndexError):
            continue
        if d <= gate_m:
            return True
    return False


def riders_for_dump(dump: _t.Any, strips: _t.Sequence[_t.Mapping[str, _t.Any]],
                    pads: _t.Sequence[_t.Any], surface: _t.Callable,
                    split_idx: _t.AbstractSet[int], *, tol_m: float,
                    authored_ground: float | None = None,
                    gate_m: float | None = None) -> tuple:
    """§4: the ``Rider`` seat record of every placement the DESIGN side
    named a rider (the ``riders`` lists of the published ``jetway_strips``
    — ONE derivation of the population, never a second host search), in
    dump order.

    ``strips`` are the graded surface's ``provenance.jetway_strips``
    records (``pad_ref``, ``level``, ``riders`` as ``[lat, lon, path,
    reach_m, dump_index, host_ref, gap_m]`` — the last three since lane
    ``ridercensus``, #31 — ``clamps``); ``pads`` the emitted pad rings
    (``placement_read.pads_rims_from_graded_doc``).

    THE DATUM is the strip pad's own plane read by THE ONE PAD DATUM RULE
    (owner RULINGS 2026-09-17t): the MEDIAN over EVERY FACE of the ref,
    folded by ``anchor_rule.fold_pad_ref`` — the number
    ``footprint_unit.plan_unit_datums`` seats the unit at (the unit datum
    = the cluster pad plane, 17t; = ``L_strip`` through the pad, spec
    C15).  Reading the FIRST face of the ref instead was an
    iteration-order datum (fix C's defect again).

    THE JOIN is the rider's identity: its ``dump_index`` (``airport/load``
    names every placement ``dsf:obj<i>`` by its row in the SAME pristine
    dump), checked against the row's resource path.  A record written
    before the index (4 elements) falls back to the anchor at 7 decimal
    places and the path — which lost 6 of HECA's 105 riders to the
    0.5 mm projection round trip.  THE GAP is to the rider's OWN host
    pad (``host_ref``, every face), 0 inside it.

    A CLAMPED GATE (spec §4 (1), §5 bar 1: "its gate is in the
    ``jetway_strip`` clamp list"): a clamp of the rider's strip standing
    within ``gate_m`` (the strip depth ``[design] jetway_strip_m``, the
    gate's own apron) of the rider's anchor.  Reading "any clamp anywhere
    on the strip" instead wrote HECA T3's 31 non-``.agp`` riders
    ``OBJECT_MSL`` at the pad median, 20-318 m from the nearest clamp
    (0.06-0.27 m) and up to 1.46 m off the strip they stand on (lane
    ``ridercensus``, #31).  ``gate_m=None`` keeps the whole-strip reading
    for a caller that has no D."""
    from ..model.placement import Rider
    from .anchor_rule import fold_pad_ref
    from .footprint_unit import authored_offset
    folded: dict[str, _t.Any] = {}

    def _pad(ref: str) -> _t.Any:
        if ref not in folded:
            folded[ref] = fold_pad_ref(pads, ref) if ref else None
        return folded[ref]

    rows = list(getattr(dump, "placements", ()) or ())
    by_index: dict[int, tuple[dict, list]] = {}
    want: dict[tuple[float, float, str], tuple[dict, list]] = {}
    for s in strips:
        for r in s.get("riders", ()) or ():
            try:
                key = (round(float(r[0]), 7), round(float(r[1]), 7), str(r[2]))
            except (TypeError, ValueError, IndexError):
                continue
            idx = r[4] if len(r) > 4 else None
            if (isinstance(idx, int) and 0 <= idx < len(rows)
                    and rows[idx].def_path == str(r[2])):
                by_index[idx] = (s, list(r))
            else:
                want[key] = (s, list(r))
    if not want and not by_index:
        return ()
    out: list = []
    for i, p in enumerate(rows):
        hit = by_index.get(i)
        if hit is None:
            key = (round(float(p.lat), 7), round(float(p.lon), 7), p.def_path)
            hit = want.get(key)
        if hit is None or i in split_idx:
            continue
        s, r = hit
        ref = str(s.get("pad_ref", ""))
        pad = _pad(ref)
        host = str(r[5]) if len(r) > 5 and r[5] else ref
        reach = float(r[3]) if len(r) > 3 else 0.0
        if pad is None or not pad.z:
            out.append(Rider(i, p.def_path, float(p.lon), float(p.lat),
                             float(p.heading_deg), p.kind, "", host, 0.0, reach,
                             str(s.get("id", "")), None, "no_host"))
            continue
        zs = sorted(float(z) for z in pad.z)
        datum = zs[len(zs) // 2]
        hp = _pad(host) or pad
        rings = tuple(getattr(hp, "rings", ()) or ()) or (hp.ring,)
        gap = (0.0 if any(_inside(p.lat, p.lon, rg) for rg in rings)
               else min(_ring_dist_m(p.lat, p.lon, rg) for rg in rings))
        off = authored_offset(p, authored_ground)
        seat = datum + (off or 0.0)
        z = surface(p.lat, p.lon)
        clamped = _gate_clamped(p.lat, p.lon, s.get("clamps") or (), gate_m)
        on_datum = z is not None and abs(float(z) - datum) <= tol_m
        is_agp = p.def_path.lower().endswith(".agp")
        if on_datum or not clamped or is_agp or off is None:
            why = "on_ground"
        else:
            why = "msl_written"
        out.append(Rider(i, p.def_path, float(p.lon), float(p.lat),
                         float(p.heading_deg), p.kind, ref, host,
                         round(gap, 3), reach, str(s.get("id", "")),
                         round(seat, 3), why,
                         None if z is None else round(float(z), 3)))
    return tuple(out)


def rider_census(riders: _t.Sequence[_t.Any]) -> dict[str, int]:
    """§4 (2): per airport — riders / in a strip / on ground / MSL written
    / no host, plus how many stand ON their datum (bar 1's reading)."""
    c = {"riders": len(riders), "riders_in_a_strip": 0, "riders_on_ground": 0,
         "riders_msl_written": 0, "riders_no_host": 0, "riders_on_datum": 0}
    for r in riders:
        if r.strip_id:
            c["riders_in_a_strip"] += 1
        c[f"riders_{r.seat_why}"] = c.get(f"riders_{r.seat_why}", 0) + 1
        if (r.seat_z is not None and r.terrain_z is not None
                and abs(r.terrain_z - (r.seat_z)) <= 0.05):
            c["riders_on_datum"] += 1
    return c
