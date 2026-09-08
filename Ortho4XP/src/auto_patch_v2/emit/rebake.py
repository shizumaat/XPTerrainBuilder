"""THE SEAT (RULINGS 2026-09-04i 04f-1; THE CONTACT-CLUSTER LAW 2026-09-06g):
after the tile mesh is built, every placed object of an airport v2
patched is re-seated against the NEW terrain — "otherwise the objects
would not comply with the terrain the patch produced".  Law:
``structures.toml [rebake]``.

:func:`seat` runs AFTER the mesh, over the tile build's plan
(``model/rebake.py``, built by ``airport/rebake_plan.py``) and a sampler
of the built mesh (``sampler(lat, lon) -> (z, is_water) | None``).  Two
laws share it:

* THE STRUCTURE SEATS, per anchor family: a deck member founds its
  family's deck seat (memory ``othh-bridge-deck-datum-r12``: the datum is
  the deck TOP, never the authored y = 0 plane) — a SIGNATURE deck
  (``airport/deck_signature.py``) at its ABUTMENTS: the ground is sampled
  along each deck-end line, a sample on water is discarded and the line
  WALKS LANDWARD along the axis until ``abutment_min_land_samples`` stand
  on land (R12 amendment 1, the mesh's own water bits the authority —
  amendment 2), the member delta is ``grade − (base + deck top)``, and
  the family's deck members take the agreeing coalition of member deltas
  (amendments 3/4); a flagged deck at the solved surface / its ring.
  After the seat the mesh under a deck's CREST must lie
  ``deck_min_clearance_under_m`` under the seated crest or be water — a
  bridge stands over something lower than itself; a plate seated onto
  the ground it covers spans nothing, the deck seat is refused with a
  finding and the cluster law governs its parts.  A tunnel wall object
  seats its top PLATE on the ground at its wall band (05n-4), a basin
  family its floor plate on the trench floor (06b-3): the whole family
  rigidly.  A structure seat is exempt from ``min_delta_m``.
* THE CLUSTER SEAT, for everything else (``emit/clusters.py``): the
  members' welded parts and the pack-wide contact graph, cut where two
  adjacent ground parts' seat targets disagree by more than
  ``cluster_seat_tolerance_m``; every cluster seats on the median ground
  under its ground parts, each resource's delta measured from ITS OWN
  anchor ground and written PER VERTEX (one file may carry several
  deltas); elevated parts inherit the cluster they contact most; a
  deck's own family parts in contact with the plate seat WITH it, and
  the deck never founds the ground parts around or under it; the
  facility rule (05p / 05q) at cluster level.

A unit whose anchor is off the mesh is HELD — the pack's current bytes
are kept and a finding is raised; a cluster with no measured ground
part likewise.

THE FLAT-SITE DATUM AT THE SEAT (RULINGS 2026-09-08d; spec
``othh-seat-artefacts-spec.md``): on a flat-candidate site the plan
carries the verdict, Z0 and the datum region (``RebakePlan.flat``) and
the pack's seats are authoritative inside it — (a) an anchor on WATER
takes Z0 (HELD where no datum exists, ``anchor_water_founds_seat``); a
land anchor within ``basin.contact_band_m`` of Z0 takes Z0
(``flat_site_anchor_datum``), a deeper one is a CUT the mesh made and
keeps the mesh (the plate seat compensates it: Dewatering_01 +13.14);
(b) a flag deck's ring needs ABUTMENT RELIEF (water, or a land spread ≥
the band) or the deck seat stands down; (d) a structure seat under
``min_delta_m`` stays unless ``structure_seat_threshold_exempt``; (e)
inside the region the pack's seat is authoritative
(``flat_site_ground_datum``): a cluster ground part reads its object's
AUTHORED ``y = 0`` plane as its ground (delta 0 — never the canal bank,
never the raw inset DEM, never ``−agl``), a deck unit keeps its authored
deck;
plate stations always read the raw mesh (a floor or a rim by
construction: the cut compensations).

Nothing here writes: the deltas are handed to the v1 driver hook
(``engine_v2.rebake_after_mesh``), which rewrites the pack's OBJ8 vertex
``y`` tokens through v1's ``object_rebake.apply`` — the ONE writer both
engines share, with its ``.anchor_bak`` backup discipline, provenance
sidecar and reversion pass.  No environment is read here.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics
import typing as _t

import numpy as np

from ..law import Law
from ..model.frame import LL, XY
from ..model.rebake import (DATUM_CLUSTER, DATUM_DECK_TOP, DATUM_PLATE, PLAN_FILENAME,
                            PLAN_VERSION, ClusterSeat, FlatDatum, Member, MemberSeat,
                            PadRequest, Part, RebakePlan, SeatResult, Unit, UnitSeat)
from . import clusters as _cl
from .clusters import coalition as _coalition, metres_per_degree as _metres_per_degree

__all__ = ["seat", "deck_datum_from_surface", "Sampler", "Part", "Member", "Unit",
           "RebakePlan", "FlatDatum", "MemberSeat", "UnitSeat", "ClusterSeat", "PadRequest", "SeatResult",
           "PLAN_VERSION", "PLAN_FILENAME", "DATUM_CLUSTER", "DATUM_DECK_TOP", "DATUM_PLATE"]

#: ``sampler(lat, lon) -> (z, is_water)`` or ``None`` off the mesh.
Sampler = _t.Callable[[float, float], "tuple[float, bool] | None"]


class _Datum:
    """THE FLAT-SITE DATUM's reach at the seat (module doc, 08d): ``z0``
    and the region it is priced over; inactive (every read is the raw
    mesh) when the plan carries no substituting verdict."""

    def __init__(self, plan_: RebakePlan, band: float) -> None:
        f = plan_.flat
        self.active = f is not None and f.substitutes and bool(f.region)
        self.z0 = float(f.z0_m) if self.active else None
        self.band = band
        self._polys = []
        if self.active:
            from shapely.geometry import Polygon
            from shapely.prepared import prep
            for outer, holes in f.region:
                if len(outer) < 3:
                    continue
                try:
                    poly = Polygon([(lo, la) for la, lo in outer],
                                   [[(lo, la) for la, lo in h] for h in holes if len(h) >= 3])
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    if not poly.is_empty:
                        self._polys.append(prep(poly))
                except (ValueError, TypeError):
                    continue
            self.active = bool(self._polys)

    def inside(self, lat: float, lon: float) -> bool:
        if not self.active:
            return False
        from shapely.geometry import Point
        pt = Point(lon, lat)
        return any(pp.contains(pt) for pp in self._polys)

    def anchor(self, smp: "tuple[float, bool] | None", lat: float, lon: float, rb
               ) -> tuple[float | None, str]:
        """Rule (a): ``(ground, note)`` — ``None`` = HELD (off the mesh,
        or water without a datum)."""
        if smp is None:
            return None, "anchor off the mesh"
        z, water = float(smp[0]), bool(smp[1])
        if water and not rb.anchor_water_founds_seat:
            if self.active and self.inside(lat, lon):
                return self.z0, f"anchor on water: the site datum Z0 {self.z0:.2f} founds it (08d)"
            return None, "anchor on water and no site datum (anchor_water_founds_seat off)"
        if rb.flat_site_anchor_datum and self.active and not water and self.inside(lat, lon) \
                and abs(z - self.z0) <= self.band:
            return self.z0, (f"anchor within {self.band} m of Z0: the datum {self.z0:.2f} "
                             f"founds it (mesh {z:.3f})")
        if self.active and not water and self.inside(lat, lon):
            return z, f"anchor in a cut {self.z0 - z:.2f} m under Z0: the mesh founds it"
        return z, ""

    def authored(self, lat: float, lon: float, rb) -> bool:
        """Rule (e): whether a footprint point inside the region reads
        the pack's AUTHORED seat instead of the mesh."""
        return bool(self.active and rb.flat_site_ground_datum and self.inside(lat, lon))


def deck_datum_from_surface(surface, ring_xy: _t.Sequence[XY], to_xy,
                            buffer_m: float = 0.5) -> float | None:
    """The SOLVED surface's value at a deck: the median ``z`` of the
    graded surface's vertices inside the deck ring (buffered by
    ``buffer_m`` so the ring's own vertices count).  ``None`` when the
    surface has no vertex there (the deck founds no solved value)."""
    from shapely import contains_xy
    from shapely.geometry import Polygon
    if surface is None or len(ring_xy) < 3 or not surface.vertices:
        return None
    try:
        poly = Polygon(ring_xy).buffer(buffer_m)
    except Exception:
        return None
    xs = []; ys = []; zs = []
    for sv in surface.vertices:
        x, y = to_xy(sv.ll[1], sv.ll[0])
        xs.append(x); ys.append(y); zs.append(sv.z)
    mask = contains_xy(poly, np.asarray(xs), np.asarray(ys))
    inside = [z for z, m in zip(zs, mask) if m]
    return float(statistics.median(inside)) if inside else None


def _abutment_grade(ends: tuple[tuple[LL, LL], tuple[LL, LL]], sampler: Sampler, br,
                    water_founds: bool) -> tuple[float | None, list[str], int, int, int]:
    """THE ABUTMENT GRADE of a signature deck (R12 amendments 1–2): per
    deck-end line, samples ``abutment_sample_step_m`` apart; a sample on
    a water triangle is discarded; with fewer than
    ``abutment_min_land_samples`` on land the line moves LANDWARD (away
    from the other end) one step at a time up to ``abutment_walk_max_m``.
    Returns ``(median grade over the ends that found land, records,
    land samples, water samples, off-mesh samples)``."""
    mids = [((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0) for a, b in ends]
    m_lat, m_lon = _metres_per_degree(mids[0][0])
    pooled: list[float] = []
    records: list[str] = []
    n_land = n_water = n_off = 0
    for i, (a, b) in enumerate(ends):
        other = mids[1 - i]
        dx = (mids[i][1] - other[1]) * m_lon
        dy = (mids[i][0] - other[0]) * m_lat
        norm = math.hypot(dx, dy)
        landward = (dx / norm, dy / norm) if norm > 1e-6 else None
        length = math.hypot((b[1] - a[1]) * m_lon, (b[0] - a[0]) * m_lat)
        steps = max(2, int(math.ceil(length / br.abutment_sample_step_m)))
        walked = 0.0
        kept: list[float] = []
        lost = off = 0
        while True:
            off_lat = (landward[1] * walked / m_lat) if landward else 0.0
            off_lon = (landward[0] * walked / m_lon) if landward else 0.0
            kept, lost, off = [], 0, 0
            for k in range(steps + 1):
                f = k / steps
                la = a[0] + (b[0] - a[0]) * f + off_lat
                lo = a[1] + (b[1] - a[1]) * f + off_lon
                smp = sampler(la, lo)
                if smp is None:
                    off += 1
                elif smp[1] and not water_founds:
                    lost += 1
                else:
                    kept.append(float(smp[0]))
            if len(kept) >= br.abutment_min_land_samples:
                break
            if landward is None or walked + br.abutment_sample_step_m > br.abutment_walk_max_m:
                break
            walked += br.abutment_sample_step_m
        found = len(kept) >= br.abutment_min_land_samples
        records.append(f"{'start' if i == 0 else 'far'} end: walked {walked:.0f} m, "
                       f"{len(kept)} land / {lost} water / {off} off-mesh samples"
                       + (f", grade {statistics.median(kept):.3f}" if found else ", no land found"))
        n_land += len(kept); n_water += lost; n_off += off
        if found:
            pooled.extend(kept)
    grade = float(statistics.median(pooled)) if pooled else None
    return grade, records, n_land, n_water, n_off


def _mid_span(m: Member, base: float, delta: float, sampler: Sampler, br
              ) -> tuple[bool, str]:
    """AFTER the seat: the mesh under SOME station of the deck (near-
    horizontal faces of the plate's own components, spread along the
    axis) must lie ``deck_min_clearance_under_m`` under the seated face
    there, or be water — a bridge stands over something lower than
    itself; a kerb road or a canopy over the ground it is built on does
    not.  ``(ok, record)``."""
    if not m.deck_stations:
        return True, "stations: none recorded"
    best = -math.inf
    water = off = 0
    for la, lo, y in m.deck_stations:
        smp = sampler(la, lo)
        if smp is None:
            off += 1
            continue
        if smp[1]:
            water += 1
            continue
        best = max(best, base + delta + y - float(smp[0]))
    n = len(m.deck_stations)
    if water:
        return True, f"{water}/{n} stations over water" \
            + (f", best land clearance {best:.2f} m" if best > -math.inf else "")
    if best == -math.inf:
        return True, f"stations: all {n} off the mesh"
    ok = best >= br.deck_min_clearance_under_m
    return ok, (f"best clearance under the seated deck {best:.2f} m over {n} stations "
                + ("" if ok else f"< {br.deck_min_clearance_under_m}: the deck stands on the "
                   "ground it covers, deck seat refused"))


def _plate_reading(m: Member, base: float, sampler: Sampler, rb) -> MemberSeat | None:
    """THE WALL PLATE (RULINGS 2026-09-05n-4; ``tunnel.object.plate_datum
    = "ground"``): a tunnel wall object seats so that its rendered plate
    (``base + plate_y``) equals the GROUND at its wall band — the median
    of the mesh at the band's stations (land only); ``None`` for every
    other member."""
    if m.plate_y is None or not m.plate_stations:
        return None
    zs: list[float] = []
    water = off = 0
    for la, lo in m.plate_stations:
        s = sampler(la, lo)
        if s is None:
            off += 1
        elif s[1] and not rb.water_founds_seat:
            water += 1
        else:
            zs.append(float(s[0]))
    ground = float(statistics.median(zs)) if zs else None
    delta = None if ground is None else ground - (base + m.plate_y)
    return MemberSeat(m.resource, DATUM_PLATE, delta, len(zs), water, off, 0,
                      f"ground at the wall band ({len(zs)} stations) − rendered plate "
                      f"(base {base:.3f} + plate {m.plate_y:.3f})" if ground is not None
                      else "no wall-band station on land within the mesh")


def _deck_reading(m: Member, base: float, sampler: Sampler, rb, br, band: float
                  ) -> MemberSeat | None:
    """The deck-top reading of a deck member, ``None`` for a foot member;
    ``band`` the abutment-relief floor of a flag deck's ring (08d b)."""
    if m.deck_ring is None or rb.deck_datum != DATUM_DECK_TOP or m.deck_top_y is None:
        return None
    if m.deck_kind == "signature":
        if m.deck_ends is None:
            return MemberSeat(m.resource, DATUM_DECK_TOP, None, 0, 0, 0, 0,
                              "signature deck without end lines (plate under "
                              f"{br.deck_min_span_m} m): seats with its family",
                              tuple(m.deck_evidence))
        grade, recs, nl, nw, noff = _abutment_grade(m.deck_ends, sampler, br,
                                                    rb.water_founds_seat)
        delta = None if grade is None else grade - (base + m.deck_top_y)
        return MemberSeat(m.resource, DATUM_DECK_TOP, delta, nl, nw, noff, 0,
                          "abutment grade at the deck-end lines (R12)" if grade is not None
                          else "no abutment on land within the walk",
                          tuple(recs) + tuple(m.deck_evidence))
    datum_z = m.deck_datum_z
    water = off = 0
    n = 1 if datum_z is not None else 0
    note = "solved surface at the deck" if datum_z is not None else ""
    if datum_z is None:
        zs = []
        for la, lo in m.deck_ring:
            s = sampler(la, lo)
            if s is None:
                off += 1
            elif s[1] and not rb.water_founds_seat:
                water += 1
            else:
                zs.append(float(s[0]))
        n = len(zs)
        datum_z = float(statistics.median(zs)) if zs else None
        note = "mesh at the deck ring (no solved value there)"
        if zs and not water and (max(zs) - min(zs)) < band:
            # RULINGS 2026-09-08d (b): no abutment relief at the ring — a
            # plate over the plane it is built on is not a bridge over a
            # cut (OTHH's elevated TerminalRoads decks were seated −10.87)
            return MemberSeat(m.resource, DATUM_DECK_TOP, None, n, water, off, 0,
                              f"ring samples flat (land spread {max(zs) - min(zs):.3f} m < "
                              f"{band} m, no water): not a bridge over a cut — no deck seat (08d)",
                              tuple(m.deck_evidence))
    delta = None if datum_z is None else datum_z - (base + m.deck_top_y)
    return MemberSeat(m.resource, DATUM_DECK_TOP, delta, n, water, off, 0, note,
                      tuple(m.deck_evidence))


def _structure_seat(u: Unit, base: float, ground: Sampler, raw: Sampler, rb, br, band: float
                    ) -> tuple[str, float | None, list[bool], list[MemberSeat | None], list[str]]:
    """The unit's STRUCTURE seat: ``(datum, delta, founding, readings,
    findings)`` — the deck / plate members' readings, their agreeing
    coalition and the clearance confirmation (module doc).  ``ground``
    serves the deck reads, ``raw`` the plate stations (one sampler today;
    a flat site's authored deck never reaches here, 08d e)."""
    decks = [_deck_reading(m, base, ground, rb, br, band) or _plate_reading(m, base, raw, rb)
             for m in u.members]
    findings: list[str] = []
    measurable = [(k, d) for k, d in enumerate(decks) if d is not None and d.delta_m is not None]
    founding = [False] * len(u.members)
    if not measurable:
        return DATUM_CLUSTER, None, founding, decks, findings
    vals = [d.delta_m for _k, d in measurable]
    if len(vals) == 1:
        delta, coal_idx = vals[0], [0]
    else:
        coal, why = _coalition(vals, rb.agreement_window_m)
        if coal is not None:
            delta = float(statistics.median(coal))
            coal_idx = [i for i, v in enumerate(vals) if v in coal]
            if len(coal) < len(vals):
                findings.append(f"deck coalition {len(coal)}/{len(vals)} members within "
                                f"{rb.agreement_window_m} m; {len(vals) - len(coal)} "
                                "outlier member(s)")
        else:
            # R12 amendment 4: a tie is genuine ambiguity, no coalition is
            # no measurement — the deck seat stands down
            findings.append(f"deck seat refused: deck members disagree ({why}), "
                            f"spread {max(vals) - min(vals):.3f} m over {len(vals)} — "
                            "the cluster law governs (R12 amendment 4)")
            return DATUM_CLUSTER, None, founding, decks, findings
    spans = []
    for j in coal_idx:
        k, d = measurable[j]
        ok, rec = _mid_span(u.members[k], base, delta, ground, br)
        decks[k] = _dc.replace(d, records=d.records + (rec,))
        spans.append(ok)
    if not any(spans):
        findings.append("deck seat refused: no founding deck member stands over "
                        f"anything lower than itself (clearance < "
                        f"{br.deck_min_clearance_under_m} m over land) — the cluster law "
                        "governs")
        return DATUM_CLUSTER, None, founding, decks, findings
    datum = DATUM_PLATE if all(measurable[j][1].datum == DATUM_PLATE for j in coal_idx) \
        else DATUM_DECK_TOP
    for j, ok in zip(coal_idx, spans):
        founding[measurable[j][0]] = bool(ok)
    return datum, float(delta), founding, decks, findings


def seat(plan_: RebakePlan, sampler: Sampler, law: Law) -> SeatResult:
    """The structure seats per unit, then the cluster seat over every
    other part (module doc)."""
    rb = law.tables.structures.rebake
    br = law.tables.structures.bridge
    band = law.tables.structures.basin.contact_band_m
    datum_ = _Datum(plan_, band)
    authored: dict[int, float] = {}             # rule (e): part id -> its authored y = 0 plane
    stay: set[str] = set()                      # rule (d): the fixed units that stay
    base_by: dict[tuple[int, int], float | None] = {}
    fixed: dict[tuple[int, int], tuple[str, float]] = {}
    family: dict[tuple[int, int], str] = {}
    per_unit: list[dict] = []
    for ui, u in enumerate(plan_.units):
        a, why = datum_.anchor(sampler(u.anchor[0], u.anchor[1]), u.anchor[0], u.anchor[1], rb)
        rec = {"anchor_ground": None, "base": None, "datum": DATUM_CLUSTER, "delta": None,
               "founding": [False] * len(u.members), "readings": [None] * len(u.members),
               "findings": [], "whole": set(), "held": why if a is None else "",
               "below": None}
        per_unit.append(rec)
        if a is None:
            for mi in range(len(u.members)):
                base_by[(ui, mi)] = None
            continue
        if why:
            rec["findings"].append(why)
        rec["anchor_ground"] = float(a)
        base = rec["base"] = float(a) + u.agl_m        # the rendered y = 0 plane
        for mi in range(len(u.members)):
            base_by[(ui, mi)] = base
            for p in u.members[mi].parts:
                if datum_.authored(p.lat, p.lon, rb):
                    # the pack's seat: the part's ground IS its object's
                    # authored y = 0 plane (the cluster seats that plane on
                    # its ground), so its delta is 0 whatever its base_y
                    authored[p.pid] = base
        has_plate = any(m.plate_y is not None and m.plate_stations for m in u.members)
        has_deck = any(m.deck_ring is not None for m in u.members)
        if has_deck and not has_plate and datum_.authored(u.anchor[0], u.anchor[1], rb):
            # RULINGS 2026-09-08d (e): on the flat site the pack's authored
            # deck IS the seat — the ring / abutment reads (the canal bank,
            # the plane under an elevated kerb road) found nothing
            rec["datum"] = DATUM_DECK_TOP
            rec["below"] = ("below_threshold: flat site — the authored deck seat is the seat "
                            f"(Z0 {datum_.z0:.2f}, 08d e); the structure stays at its authored y")
            stay.add(u.id)
            for mi in range(len(u.members)):
                fixed[(ui, mi)] = (u.id, 0.0)
            continue
        datum, delta, founding, readings, findings = _structure_seat(
            u, base, sampler, sampler, rb, br, band)
        rec.update(datum=datum, delta=delta, founding=founding, readings=readings,
                   findings=rec["findings"] + findings)
        if delta is None:
            continue
        if not rb.structure_seat_threshold_exempt and abs(delta) < rb.min_delta_m:
            # RULINGS 2026-09-08d (d): a structure seat under the threshold
            # STAYS — its members keep their authored y and are never
            # handed to the cluster law (OTHH Drainage_06 was written +0.001)
            rec["below"] = (f"below_threshold: {datum} seat |{delta:+.3f}| m < {rb.min_delta_m} m"
                            " — the structure stays at its authored y")
            rec["delta"] = None
            stay.add(u.id)
            for mi in range(len(u.members)):
                fixed[(ui, mi)] = (u.id, 0.0)
            continue
        if datum == DATUM_PLATE:
            # a plate family seats rigidly, whole (05n-4 / 06b-3)
            for mi in range(len(u.members)):
                fixed[(ui, mi)] = (u.id, delta)
                rec["whole"].add(mi)
            continue
        for mi, m in enumerate(u.members):
            if founding[mi]:
                fixed[(ui, mi)] = (u.id, delta)
            elif m.deck_kind == "family" and rb.deck_family_seats_rigid:
                family[(ui, mi)] = u.id
                if not m.parts:
                    rec["whole"].add(mi)          # a part-less sheet takes the deck's delta (R12-2)
    out = _cl.seat_clusters(plan_, sampler, law, base_by, fixed, family, authored, stay)
    units: list[UnitSeat] = []
    for ui, u in enumerate(plan_.units):
        rec = per_unit[ui]
        resources = tuple(m.resource for m in u.members)
        if rec["anchor_ground"] is None:
            units.append(UnitSeat(u.id, resources, None, DATUM_CLUSTER, None, None, tuple(
                MemberSeat(m.resource, DATUM_CLUSTER, None, 0, 0, 0, 0, rec["held"])
                for m in u.members), "held: " + rec["held"], (), True))
            continue
        base = rec["base"]
        datum, delta = rec["datum"], rec["delta"]
        if rec["below"] is not None:
            units.append(UnitSeat(u.id, resources, rec["anchor_ground"], datum, None, None, tuple(
                MemberSeat(m.resource, datum, None, 0, 0, 0, 0, rec["below"],
                           tuple(rd.records) if rd is not None else ())
                for m, rd in zip(u.members, rec["readings"])), rec["below"],
                tuple(rec["findings"]) + (rec["below"],), False))
            continue
        seats: list[MemberSeat] = []
        for mi, m in enumerate(u.members):
            mp = out.members[(ui, mi)]
            rd = rec["readings"][mi]
            if (ui, mi) in fixed or mi in rec["whole"]:
                base_seat = rd if rd is not None else MemberSeat(m.resource, datum, delta, 0, 0, 0, 0,
                                                                  "seats with its family's structure seat")
                seats.append(_dc.replace(base_seat, datum=datum, delta_m=delta,
                                         founding=rec["founding"][mi],
                                         part_deltas=tuple(mp.part_deltas)))
                continue
            note = ""
            if rd is not None:
                note = f"deck reading: {rd.note}" + (f" delta {rd.delta_m:.3f}" if rd.delta_m is not None else "") + "; "
            ks = sorted(mp.clusters)
            one = mp.one_delta
            if not mp.part_deltas:
                note += "no part: nothing to seat"
            elif one is not None:
                note += f"cluster{'s' if len(ks) > 1 else ''} {ks}: delta {one:+.3f} m"
            else:
                ds = sorted({d for _c, _k, d in mp.part_deltas if d is not None})
                note += (f"clusters {ks}: " + (f"per-vertex deltas {ds[0]:+.3f} … {ds[-1]:+.3f} m"
                                               if ds else "no part seated")
                         + (f", {sum(1 for _c, _k, d in mp.part_deltas if d is None)} part(s) stay"
                            if ds else ""))
            if mp.facility:
                note += " — facility member (05p at cluster level): authored y kept"
            seats.append(MemberSeat(m.resource, DATUM_CLUSTER, one, mp.witnesses, mp.water,
                                    mp.off_mesh, mp.outliers, note,
                                    tuple(rd.records) if rd is not None else (), False,
                                    mp.facility, mp.ground_m, tuple(mp.part_deltas)))
        findings = list(rec["findings"])
        n_fac = sum(1 for s in seats if s.facility)
        if n_fac:
            findings.append(f"{n_fac} facility member(s) (05p at cluster level) keep their authored y")
        n_multi = sum(1 for s in seats if s.delta_m is None
                      and len({d for _c, _k, d in s.part_deltas if d is not None}) > 1)
        if n_multi:
            findings.append(f"{n_multi} member(s) carry several per-vertex deltas (06g)")
        skip: str | None = None
        held = False
        if delta is None and not any(s.bakes for s in seats):
            reasons = sorted({k.skip_reason.split(":")[0] for k in out.clusters
                              if k.skip_reason and any(k.id in cl for cl in
                                                       (out.members[(ui, mi)].clusters
                                                        for mi in range(len(u.members))))})
            if [r for r in reasons if not r.startswith("facility")] == ["below_threshold"]:
                skip = (f"below_threshold: every cluster moves less than {rb.min_delta_m} m — stays"
                        + ("; facility cluster(s) keep their authored y" if len(reasons) > 1 else ""))
            elif reasons == ["held"]:
                skip, held = "held: no measured ground part under any cluster — current bytes kept", True
            else:
                skip = "no seat: " + ", ".join(reasons) if reasons else "no part: nothing to seat"
        units.append(UnitSeat(u.id, resources, rec["anchor_ground"], datum, delta,
                              None if delta is None else base + delta, tuple(seats), skip,
                              tuple(findings), held))
    return SeatResult(plan_.icao, tuple(_one_file_one_delta(units, rb)), tuple(out.clusters),
                      tuple(out.pad_requests), out.cut_edges, out.structures)


def _one_file_one_delta(units: list[UnitSeat], rb) -> list[UnitSeat]:
    """A resource planned at SEVERAL anchors (a plate-seated wall object
    placed twice: OTHH tunnel1) has ONE file: its units bake only when
    their deltas agree within ``agreement_window_m``; otherwise every
    one of them is HELD with a finding naming the spread (never the last
    writer's delta)."""
    by_res: dict[str, list[int]] = {}
    eff: dict[str, list[float]] = {}
    for i, u in enumerate(units):
        for m in u.members:
            by_res.setdefault(m.resource, []).append(i)
            if u.bakes and m.bakes:
                eff.setdefault(m.resource, []).extend(
                    [m.delta_m] if m.delta_m is not None
                    else [d for _c, _k, d in m.part_deltas if d is not None])
    held: dict[int, str] = {}
    for r, idx in by_res.items():
        if len(idx) < 2:
            continue
        vals = eff.get(r, [])
        if len(vals) >= 2 and max(vals) - min(vals) > rb.agreement_window_m:
            for i in idx:
                held[i] = (f"held: {r.rsplit('/', 1)[-1]} is placed at {len(idx)} anchors and its "
                           f"seats disagree (spread {max(vals) - min(vals):.3f} m > "
                           f"{rb.agreement_window_m} m): one file, no single delta")
    return [_dc.replace(u, delta_m=None, seat_datum_m=None, skip_reason=held[i],
                        findings=u.findings + (held[i],), held=True) if i in held else u
            for i, u in enumerate(units)]
