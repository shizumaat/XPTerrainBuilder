"""THE SHAPE STAGE (owner RULINGS 2026-09-08k; spec ``heca-v1-parity-
spec.md`` §8): between the planar build (which labelled the shapes and
declared the joints, ``planar/shapes.py``) and the constraint generators.

1. The route bands (``constraints.no_step.reach_band_values``) and the
   WITHDRAW set: the hop-derived ``reach`` band of every non-station
   vertex of a ``terrace.band_roles`` face is withdrawn (labelled or not:
   owner RULINGS 2026-09-08p leaves the network's vertices unlabelled) (RULINGS
   2026-09-07g (2): the in-shape band measured INFEASIBLE under pairwise
   agreement — the kept rows carry the reach).
2. THE FILTER, ONCE, at assembly: every row of every generator whose
   endpoints carry two shapes is dropped here — never per generator —
   counted per generator.  A ``Flat`` row (a pad, a plate: one rigid
   value) is never dropped — a pad belongs to one shape (07c (3), the
   majority relabel) — and any that would straddle is counted.
3. THE YIELDING FAMILIES (08d (2), 08k (3)): the transform runs after the
   filter; a taxi-class row whose every vertex lies on the NETWORK stays
   hard (08p (2): the network is hard at its route law), the runway-contact
   chain excepted — it yields with NO ceiling (08i-1, 08r-1).
4. THE ROAD RAMPS (08r-2): a road crossing from one shape to another is
   unlabelled — no row of it straddles, it ramps at its own law — and
   ``joint_steps`` reports the built ramp per crossing, naming a road at
   its cap (too short to ramp the difference).

ONE solve pass (08k (4)): the joints are geometric, nothing is re-solved
on a built step.
"""
from __future__ import annotations

import dataclasses as _dc
import time
import typing as _t

from ..classify.roles import Classification
from ..constraints import generate
from ..constraints.no_step import reach_band_values
from ..constraints.roads import road_family_roles
from ..constraints.yielding import YieldStats, yield_rows
from ..law import Law
from ..law.tables import role_cap
from ..model.airport import Airport
from ..model.constraints import REACH_GENERATOR, Band, ConstraintSet, Flat, Row
from ..model.planar import PlanarMap
from ..planar.shapes import (NO_SHAPE, STATION_KIND, joint_planar_edges, network_vertices,
                             row_test_pairs, row_vertices, straddles, straddles_pairs)

__all__ = ["ShapeStage", "shape_stage", "shape_constraints", "apply_joints", "joint_steps"]


@_dc.dataclass
class ShapeStage:
    """What the stage produced: the map, the joint planar edges, the route
    bands, the withdraw set, the drop counts of the last assembly."""

    pm: PlanarMap
    edges: list[tuple[int, int, str, str]]
    bands: dict[int, tuple[float, float]]
    withdraw: frozenset[int] = frozenset()
    wall_s: float = 0.0
    dropped: dict[str, int] = _dc.field(default_factory=dict)
    flats_straddling: int = 0
    bands_withdrawn: int = 0

    def as_dict(self) -> dict[str, _t.Any]:
        return {"dropped_by_generator": dict(self.dropped),
                "flats_straddling": self.flats_straddling,
                "bands_withdrawn": self.bands_withdrawn,
                "withdraw_set": len(self.withdraw),
                "joint_edges": len(self.edges),
                "shapes": len({s for s in self.pm.shape_of_vertex.values() if s != NO_SHAPE}),
                "joints": len(self.pm.shape_joints),
                "gap_joints": sum(1 for j in self.pm.shape_joints if j.gap),
                "road_ramps": len(self.pm.road_ramps),
                "wall_s": round(self.wall_s, 3)}


def shape_stage(pm: PlanarMap, law: Law, airport: Airport,
                cl: Classification | None = None,
                out: _t.Callable[[str], None] = print) -> ShapeStage:
    """Run the stage (module docstring) and say what it found."""
    t0 = time.perf_counter()
    bands = reach_band_values(pm, law, airport)
    stations: set[int] = set()
    for b in pm.breaklines.values():
        if b.kind == STATION_KIND:
            stations.update(v for v in b.vertices(pm) if v in bands)
    band_roles = set(law.tables.emit.terrace.band_roles)
    # 08p: the label condition dropped — the population is every non-station
    # vertex of a band_roles face (a network junction's vertices lost the
    # band in round 1 too, as labelled; a body's ring on the network is
    # unlabelled now and loses it the same)
    withdraw = frozenset(
        v for v, vert in pm.vertices.items()
        if v not in stations and any(pm.faces[f].role in band_roles for f in vert.incident_faces))
    edges = joint_planar_edges(pm)
    stage = ShapeStage(pm, edges, bands, withdraw, time.perf_counter() - t0)
    n_shapes = len({s for s in pm.shape_of_vertex.values() if s != NO_SHAPE})
    n_gap = sum(1 for j in pm.shape_joints if j.gap)
    by_roles: dict[str, int] = {}
    for _a, _b, ra, rb in edges:
        by_roles[f"{ra}|{rb}"] = by_roles.get(f"{ra}|{rb}", 0) + 1
    out(f"[{pm.icao}] shapes (08k): {n_shapes} shapes over {len(pm.shape_of_vertex)} vertices; "
        f"joints {len(pm.shape_joints)} ({len(pm.shape_joints) - n_gap} contours, {n_gap} gap, "
        f"{sum(j.length_m for j in pm.shape_joints):,.0f} m); joint edges {len(edges)}" + (
            " (" + ", ".join(f"{k} {n}" for k, n in sorted(by_roles.items())) + ")" if by_roles else "")
        + f"; road ramps (08r-2) {len(pm.road_ramps)}"
        + f"; reach bands to withdraw {len(withdraw)} (stations {len(stations)}); {stage.wall_s:.2f} s")
    return stage


def apply_joints(cs: ConstraintSet, stage: ShapeStage) -> ConstraintSet:
    """THE FILTER (module docstring): the set without the rows across a
    joint, the withdrawn reach bands removed; the counts land on ``stage``."""
    pm = stage.pm
    dropped: dict[str, int] = {}
    flats = 0
    withdrawn = 0
    out: list[Row] = []
    for r in cs.rows():
        ids = row_vertices(r)
        if isinstance(r, Flat):
            if straddles(pm, ids):
                flats += 1
            out.append(r)
            continue
        if isinstance(r, Band) and r.source.generator == REACH_GENERATOR and r.v in stage.withdraw:
            withdrawn += 1
            continue
        pairs = row_test_pairs(r)
        if (straddles_pairs(pm, pairs) if pairs is not None
                else len(ids) >= 2 and straddles(pm, ids)):
            dropped[r.source.generator] = dropped.get(r.source.generator, 0) + 1
            continue
        out.append(r)
    stage.dropped = dropped
    stage.flats_straddling = flats
    stage.bands_withdrawn = withdrawn
    return ConstraintSet.from_rows(out)


def shape_constraints(pm: PlanarMap, law: Law, airport: Airport, stage: ShapeStage,
                      seam_honoured: _t.Container[int] | None = None
                      ) -> tuple[ConstraintSet, dict[str, int], dict[str, float]]:
    """``constraints.generate`` under the joints: the generators run
    unchanged, the filter runs once, then the yield transform; the counts
    carry ``joint_dropped.<generator>`` and ``yield.<family>`` beside the
    generators' own."""
    cs, counts, walls = generate(pm, law, airport, seam_honoured=seam_honoured)
    t = time.perf_counter()
    cs = apply_joints(cs, stage)
    walls["joint_filter"] = time.perf_counter() - t
    counts["joint_filter"] = sum(stage.dropped.values())
    t = time.perf_counter()
    ys = YieldStats()
    cs = yield_rows(cs, pm, law, ys, network=network_vertices(pm, law))
    walls["yield"] = time.perf_counter() - t
    counts["yield"] = sum(ys.by_family.values())
    for fam, n in sorted(ys.network_hard.items()):
        counts[f"yield.{fam}.network_hard"] = n
    for fam, n in sorted(ys.by_family.items()):
        counts[f"yield.{fam}"] = n
    for fam, n in sorted(ys.at_ceiling.items()):
        counts[f"yield.{fam}.at_ceiling"] = n
    for gen, n in sorted(stage.dropped.items()):
        counts[f"joint_dropped.{gen}"] = n
    counts["joint_flats_straddling"] = stage.flats_straddling
    counts["joint_bands_withdrawn"] = stage.bands_withdrawn
    return cs, counts, walls


def joint_steps(pm: PlanarMap, law: Law, stage: ShapeStage,
                z: _t.Sequence[float]) -> dict[str, _t.Any]:
    """The built steps across the joint planar edges — the max per role
    pair, per ROAD-family face (07g (4): a road's rows stop at the joint;
    the step it takes is reported) — and per declared joint."""
    roads = set(road_family_roles(law))
    by_roles: dict[str, dict[str, float | int]] = {}
    per_face: dict[int, float] = {}
    for a, b, ra, rb in stage.edges:
        step = abs(float(z[a]) - float(z[b]))
        key = f"{ra}|{rb}"
        rec = by_roles.setdefault(key, {"edges": 0, "max_step_m": 0.0})
        rec["edges"] += 1
        rec["max_step_m"] = max(rec["max_step_m"], step)
        for fid in set(pm.vertices[a].incident_faces) & set(pm.vertices[b].incident_faces):
            if pm.faces[fid].role in roads:
                per_face[fid] = max(per_face.get(fid, 0.0), step)
    for rec in by_roles.values():
        rec["max_step_m"] = round(float(rec["max_step_m"]), 3)
    road_rows = [{"face": fid, "role": pm.faces[fid].role, "ref": pm.faces[fid].ref,
                  "step_m": round(s, 3)} for fid, s in sorted(per_face.items(), key=lambda kv: -kv[1])]
    contours = [{"id": j.id, "length_m": round(j.length_m, 1), "roles": list(j.roles),
                 "shapes": list(j.shapes), "gap": j.gap, "pairs": len(j.pairs),
                 "step_m": round(max((abs(float(z[a]) - float(z[b])) for a, b in j.pairs), default=0.0), 3)}
                for j in pm.shape_joints]
    # THE ROAD RAMPS (owner RULINGS 2026-09-08r-2): per road crossing from one
    # shape to another, the built |dz| between its two contact centroids over
    # its axis length against the road's own cap (the core clamp); at the
    # cap the road was too short to ramp the difference — the shapes
    # conformed instead — and it is named
    tol_g = law.tables.emit.materiality.grade
    ramps = []
    for r in pm.road_ramps:
        f = pm.faces[r.face]
        rc = role_cap(law, f.role, f.code_number, f.code_letter)
        cap = rc.longitudinal if rc is not None else None
        za = sum(float(z[v]) for v in r.contacts_a) / max(1, len(r.contacts_a))
        zb = sum(float(z[v]) for v in r.contacts_b) / max(1, len(r.contacts_b))
        dz = abs(za - zb)
        grade = dz / r.length_m if r.length_m > 0.0 else 0.0
        ramps.append({"face": r.face, "ref": f.ref, "role": f.role, "shapes": list(r.shapes),
                      "length_m": round(r.length_m, 1), "dz_m": round(dz, 3), "grade": round(grade, 6),
                      "cap": cap, "too_short": bool(cap is not None and grade >= cap - tol_g)})
    ramps.sort(key=lambda d: -d["grade"])
    return {"by_roles": by_roles, "roads": road_rows, "contours": contours, "ramps": ramps}
