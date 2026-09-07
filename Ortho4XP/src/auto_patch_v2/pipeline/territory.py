"""THE TERRITORY STAGE (RULINGS 2026-09-07g; spec ``apron-reach-territory-
spec.md`` §2b): between the planar build and the constraint generators.

1. The route bands (``constraints.no_step.reach_band_values``) and the
   serving-contact labels (``planar/territories.py``).
2. THE FEASIBILITY FALLBACK (07g (1)): runways whose pins reach no other
   runway's pins through the network are joined by the shortest in-shape
   apron path (``PlanarMap.route_links``) — the bands and labels re-run
   over the linked graph; reported.
3. The joint planar edges and the declared contours (``LabelJoint``).
4. THE FILTER, ONCE, at assembly (07g (3)): every row of every generator
   whose endpoints straddle a joint is dropped here — never per generator
   — counted per generator; the hop-derived ``reach`` bands of labelled
   non-station vertices are WITHDRAWN (``planar/territories.py``: the
   07g (2) in-shape band measured infeasible under pairwise agreement).  A
   ``Flat`` row (a pad, a plate: one rigid value) is never dropped — a
   pad belongs to one territory (07c (3), the majority relabel) — and any
   that would straddle is counted and reported.
"""
from __future__ import annotations

import dataclasses as _dc
import time
import typing as _t

import numpy as np
from scipy.sparse.csgraph import dijkstra

from ..classify.roles import Classification
from ..constraints import generate
from ..constraints.no_step import reach_band_values
from ..constraints.precedence import view
from ..constraints.roads import road_family_roles
from ..constraints.routes import routes
from ..constraints.runway_profile import ridge_chains, threshold_pins
from ..law import Law
from ..law.tables import snap_margin_m
from ..model.airport import Airport
from ..model.constraints import REACH_GENERATOR, Band, ConstraintSet, Flat, Row
from ..model.planar import LabelJoint, PlanarMap
from ..planar.terraces import strip_keepout
from ..planar.territories import (NO_LABEL, Territories, fallback_links, joint_planar_edges,
                                  label_joints, label_territories, row_vertices)

__all__ = ["TerritoryStage", "territory_stage", "territory_constraints", "apply_joints",
           "joint_steps"]


@_dc.dataclass
class TerritoryStage:
    """What the stage produced: the (possibly linked) map, the labels, the
    joint edges, the declared contours, the route bands, the drop counts
    of the last assembly."""

    pm: PlanarMap
    terr: Territories
    edges: list[tuple[int, int, str, str]]
    joints: tuple[LabelJoint, ...]
    bands: dict[int, tuple[float, float]]
    wall_s: float = 0.0
    dropped: dict[str, int] = _dc.field(default_factory=dict)
    flats_straddling: int = 0
    bands_withdrawn: int = 0        # reach bands withdrawn (labelled non-station vertices)

    def as_dict(self) -> dict[str, _t.Any]:
        st = _dc.asdict(self.terr.stats)
        st["dropped_by_generator"] = dict(self.dropped)
        st["flats_straddling"] = self.flats_straddling
        st["bands_withdrawn"] = self.bands_withdrawn
        st["route_links"] = [list(map(float, l)) for l in self.pm.route_links]
        st["wall_s"] = round(self.wall_s, 3)
        return st


def _runway_systems(pm: PlanarMap, law: Law, airport: Airport,
                    stations: frozenset[int]) -> list[frozenset[int]]:
    """The route SYSTEMS: runways grouped by mutual reach of their pins,
    each as the set of runway-connected contacts it reaches; one system
    (or none) when every pinned runway reaches every other."""
    pins = threshold_pins(pm, law, airport)
    if not pins:
        return []
    chains = ridge_chains(view(pm, law))
    rw_of: dict[int, str] = {}
    for rid, chs in chains.items():
        for ch in chs:
            for v in ch:
                if v in pins:
                    rw_of[v] = rid
    by_rw: dict[str, list[int]] = {}
    for v, rid in rw_of.items():
        by_rw.setdefault(rid, []).append(v)
    if len(by_rw) < 2:
        return []
    g = routes(pm, law, airport)
    m = g.csr("length")
    ids = sorted(by_rw)
    reach_of: dict[str, set[int]] = {}
    for rid in ids:
        src = [v for v in by_rw[rid] if v in g.nodes]
        if not src:
            reach_of[rid] = set()
            continue
        D = dijkstra(m, directed=True, indices=src, min_only=True)
        verts = np.arange(g.n)
        ok = np.isfinite(D[g.inbound(verts)])
        reach_of[rid] = {int(v) for v in verts[ok] if int(v) in g.nodes}
    parent = {rid: rid for rid in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a in ids:
        for b in ids:
            if a < b and (any(v in reach_of[a] for v in by_rw[b])
                          or any(v in reach_of[b] for v in by_rw[a])):
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    groups: dict[str, set[int]] = {}
    for rid in ids:
        groups.setdefault(find(rid), set()).update(v for v in reach_of[rid] if v in stations)
    return [frozenset(s) for _k, s in sorted(groups.items())]


def territory_stage(pm: PlanarMap, law: Law, airport: Airport,
                    cl: Classification | None = None,
                    out: _t.Callable[[str], None] = print) -> TerritoryStage:
    """Run the stage (module docstring) and say what it found."""
    t0 = time.perf_counter()
    bands = reach_band_values(pm, law, airport)
    terr = label_territories(pm, law, bands, cl)
    systems = _runway_systems(pm, law, airport, terr.contacts)
    if len(systems) >= 2:
        links = fallback_links(pm, law, terr, systems)
        if links:
            pm = _dc.replace(pm, route_links=tuple(pm.route_links) + tuple(links))
            bands = reach_band_values(pm, law, airport)
            terr = label_territories(pm, law, bands, cl)
            terr.stats.links = [[a, b, round(d, 1)] for a, b, _c, d in links]
    keep = strip_keepout(cl, law) if cl is not None else None
    edges = joint_planar_edges(pm, terr, keep)
    faces: list[int] = []
    for fid, f in pm.faces.items():
        labels = {terr.label.get(v, NO_LABEL) for cyc in (f.ring, *f.holes)
                  for v in pm.ring_vertices(cyc)} - {NO_LABEL}
        if len(labels) < 2:
            continue
        ls = sorted(labels)
        if any(terr.joint(ls[i], ls[j]) for i in range(len(ls)) for j in range(i + 1, len(ls))):
            faces.append(fid)
    _to_xy, to_ll = airport.frame.transformers()
    joints = label_joints(pm, terr, faces, lambda x, y: tuple(map(float, to_ll(x, y))),
                          extend_m=snap_margin_m(law))
    stage = TerritoryStage(pm, terr, edges, joints, bands, time.perf_counter() - t0)
    st = terr.stats
    out(f"[{pm.icao}] territories (07g): complexes {st.complexes} ({st.complexes_labelled} labelled, "
        f"{st.contacts} contacts)  vertices labelled {st.labelled} (unlabelled {st.unlabelled}, "
        f"notch fallback {st.notch_fallback} of which isolated {st.isolated_fallback}, "
        f"pads relabelled {st.pads_relabelled}, road corridor {st.road_vertices_labelled})  labels {st.labels}  adjacent label pairs "
        f"{st.adjacent_pairs}: joints {st.joint_pairs} (floor-only {st.floor_only_pairs})  "
        f"joint edges {st.joint_edges} " + (
            "(" + ", ".join(f"{k} {n}" for k, n in sorted(st.joint_edges_by_roles.items())) + ")"
            if st.joint_edges_by_roles else "") +
        f"  in strip {st.joint_edges_in_strip}  contours {st.contours} ({st.contour_length_m:,.0f} m, "
        f"dangling faces {st.dangling_faces})  welded: route {st.welded_route_pairs} strip "
        f"{st.welded_strip_pairs}  fallback links {len(st.links)}  {stage.wall_s:.2f} s "
        f"(graph {st.wall_graph_s:.1f} s over {st.graph_nodes} nodes, labels {st.wall_label_s:.1f} s)")
    for a, b, d, *_rest in st.links:
        out(f"    FALLBACK LINK (07g (1)): contacts {a}–{b} joined across an apron, {d:.1f} m")
    return stage


def apply_joints(cs: ConstraintSet, stage: TerritoryStage) -> ConstraintSet:
    """THE FILTER (module docstring): the set without the rows across a
    joint, the reach bands of labelled vertices replaced; the counts
    land on ``stage``."""
    terr = stage.terr
    dropped: dict[str, int] = {}
    flats = 0
    withdrawn = 0
    out: list[Row] = []
    for r in cs.rows():
        ids = row_vertices(r)
        if isinstance(r, Flat):
            if terr.straddles(ids):
                flats += 1
            out.append(r)
            continue
        if isinstance(r, Band) and r.source.generator == REACH_GENERATOR \
                and r.v not in terr.contacts and terr.label.get(r.v, NO_LABEL) != NO_LABEL:
            withdrawn += 1          # withdrawn (module docstring)
            continue
        if len(ids) >= 2 and terr.straddles(ids):
            dropped[r.source.generator] = dropped.get(r.source.generator, 0) + 1
            continue
        out.append(r)
    stage.dropped = dropped
    stage.flats_straddling = flats
    stage.bands_withdrawn = withdrawn
    return ConstraintSet.from_rows(out)


def territory_constraints(pm: PlanarMap, law: Law, airport: Airport, stage: TerritoryStage,
                          seam_honoured: _t.Container[int] | None = None
                          ) -> tuple[ConstraintSet, dict[str, int], dict[str, float]]:
    """``constraints.generate`` under the joints: the generators run
    unchanged, the filter runs once; the counts carry
    ``joint_dropped.<generator>`` beside the generators' own."""
    cs, counts, walls = generate(pm, law, airport, seam_honoured=seam_honoured)
    t = time.perf_counter()
    cs = apply_joints(cs, stage)
    walls["joint_filter"] = time.perf_counter() - t
    counts["joint_filter"] = sum(stage.dropped.values())
    for gen, n in sorted(stage.dropped.items()):
        counts[f"joint_dropped.{gen}"] = n
    counts["joint_flats_straddling"] = stage.flats_straddling
    counts["joint_bands_withdrawn"] = stage.bands_withdrawn
    return cs, counts, walls


def joint_steps(pm: PlanarMap, law: Law, stage: TerritoryStage,
                z: _t.Sequence[float]) -> dict[str, _t.Any]:
    """The built steps across the joint planar edges: the max per role
    pair, and per ROAD-family face (07g (4): a road's rows stop at the
    joint; the step it takes is reported, a ramp needs a ruling)."""
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
                 "pairs": len(j.pairs),
                 "step_m": round(max((abs(float(z[a]) - float(z[b])) for a, b in j.pairs), default=0.0), 3)}
                for j in stage.joints]
    return {"by_roles": by_roles, "roads": road_rows, "contours": contours}
