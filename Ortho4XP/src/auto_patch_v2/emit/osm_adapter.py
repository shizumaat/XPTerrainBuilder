"""The Ortho4XP ``.osm`` patch adapter (plan §1 row 7; Appendix A §5).

WHAT THE MESH READS (``src/O4_Vector_Map.py:2639-2826``, Appendix A §5):
way ``altitude`` / ``node_altitudes`` / ``cst_alt_abs``, node ``alt_abs``
(overrides the way), ``role`` only for the seawall/flood admission, and
the sidecar key ``road_bridge_decks``.  ``ref``, ``shapeID`` and
``aeroway`` are NOT read by the mesh — they are census inputs.

THE PATCH v2 WRITES:
  * one closed way per face ring, tags ``aeroway`` (the role register),
    ``role``, ``ref``, ``shapeID`` (= face id), ``code_letter`` /
    ``code_number`` where the face carries a class, ``o4_single_poly=1``
    on runway rings (the census's station-scoped lateral law, user
    2026-07-08), node ``alt_abs`` per vertex;
  * one closed way per UNCOVERED HOLE, tagged ``o4_feature=gap_interior_ring``
    exactly as v1 so the census keeps it out of the ring laws and the
    mesh still constrains it (``include_patches`` inserts every closed
    way as a ring; ``_parse_osm`` routes the feature class to
    ``feature_out``).  A hole every edge of which is already an edge of
    some face ring (the planar map's normal case: the hole IS the faces
    inside it) is NOT written — the ring would be a coincident duplicate
    carrying the parent's shapeID, which read in the sim as "shapeID 718
    gap_interior_ring" over what is apron 730 (owner, OTHH 2026-09-04);
  * one closed way per STRUCTURE RIM (``emit.graded.RIM_KIND``; RULINGS
    2026-09-06b (1)): the void face's exterior at the ground, tagged
    ``o4_feature=structure_rim`` with the structure's ``ref`` — a
    constrained ring the mesh makes the wall up to (no wall face);
  * one open way per ``runway_profile`` breakline tagged
    ``o4_feature=crown_spine`` — the ridge the census's ``runway_crown``
    reader measures the declared drops against (a ``DUMMY`` constrained
    line in the mesh; its chords are already ring edges of the runway
    halves, so the mesh's colinear re-dicing folds it);
  * node ids: ONE node per surface vertex — a coordinate is ONE node
    (the stacked-nodes family is impossible by construction);
  * lat/lon at ``identity_dp``; ``alt_abs`` is the surface's ONE
    quantisation (``GradedSurface`` z at the materiality precision).

THE SIDECAR (``<patch>.axes.json``) carries ONLY the census inputs v2
has, keys ⊆ :data:`SIDECAR_KEYS` (Appendix A §5): ``ruleset``; ``axes``
(every published centreline: ``[[lat, lon]…], cL, cT, ordinal,
is_service`` — the transverse walk and the spine membership);
``stretches`` (every taxi centreline STRETCH with its cap and letter,
RULINGS 2026-09-04t-3 — the per-stretch pair law v2 verify re-composes);
``crown_drops`` (``[lat, lon, drop]`` per runway-family vertex);
``airside_no_step_edges`` (``{a, b, budget_m}`` — the pairs the solver
priced, the census prices the same list); the always-empty
``terrace_joints`` / ``basin_facilities`` / ``road_bridge_decks``
(v2 has none: the mesh reads the last).  Nothing else: v1's 24 MB SPJC
sidecar was instrument-only (Appendix B §1).

The v1 census (``tools/harness/census.py``) is the ORACLE over this
output until ``verify/`` is proven equal on three airports (plan §1
``verify`` row).
"""
from __future__ import annotations

import dataclasses as _dc
import json
import typing as _t
from pathlib import Path
from xml.sax.saxutils import escape

from ..law.model import Law
from ..law.tables import role_cap
from .graded import z_decimals
from .surface import GradedSurface

__all__ = ["SIDECAR_KEYS", "PatchPaths", "write_patch", "render_patch",
           "render_sidecar", "tile_of_face", "write_tile_pieces"]

#: The sidecar keys v2 publishes, and nothing else (Appendix A §5).
SIDECAR_KEYS: tuple[str, ...] = (
    "ruleset", "axes", "routes", "runway_end_skirt", "crown_drops",
    "road_bridge_decks", "terrace_joints", "basin_facilities",
    "airside_no_step_edges", "pad_pavement_no_step_edges", "mesh_edges",
    "pair_caps", "seam_pins", "station_caps",
    "relaxed_rows",   # RULINGS 2026-09-04t(1): the rows the last resort relaxed, with their slacks (``solve/relax.py``)
    "pair_caps", "seam_pins", "station_caps", "stretches",
    "tunnel_objects",   # RULINGS 2026-09-05k-1: the object corridors (``pipeline/publication.tunnel_objects``)
    "taxi_route_pairs",  # RULINGS 2026-09-05ab: taxi within-shape pairs priced over the centreline route (``taxi.taxi_pair_routes``)
    "face_holes",  # RULINGS 2026-09-05ae(1): each face's holes by shapeID — the oracle's visibility polygon (``publication.face_holes_ll``)
    "apron_tier",  # RULINGS 2026-09-06w: the tiered apron law priced (preferred / max / fan) — the oracle's cap for apron rows (``publication.apron_tier``)
    "yielded_rows",  # RULINGS 2026-09-08d (2): the rows the yielding families hold above their cap, with their built grade (``constraints.yielding.yielded_rows``) — both readers count them apart
    "apron_over_preference",  # RULINGS 2026-09-06w (2): the built surface against the preference, per face (``constraints.apron.apron_preference_report``) — evidence
)

#: Feature class of a hole ring (v1 vocabulary the census and mesh read).
HOLE_FEATURE = "gap_interior_ring"
#: The structure rim's feature tag (a role-less closed way; the census
#: skips it as it skips the hole rings — ``check_grade.ROLE_LESS_FEATURE_CLASSES``).
RIM_FEATURE = "structure_rim"
#: Feature class of the runway ridge open way.
RIDGE_FEATURE = "crown_spine"
#: Breakline kinds emitted as open ways (the others are ring edges already).
_OPEN_WAY_KINDS = {"runway_profile": RIDGE_FEATURE}


@_dc.dataclass(frozen=True)
class PatchPaths:
    """Where a patch landed."""

    patch: Path
    sidecar: Path
    graded: Path
    ways: int
    nodes: int
    bytes_patch: int
    bytes_sidecar: int


def _fmt(v: float, dp: int) -> str:
    return f"{v:.{dp}f}"


def _q(v: object) -> str:
    """A single-quoted XML attribute — the v1 census's tag regex reads
    ``k='…' v='…'`` (single quotes) and nothing else."""
    return "'" + escape(str(v), {"'": "&apos;", '"': "&quot;"}) + "'"


def _edges(cycle: _t.Sequence[int]) -> set[tuple[int, int]]:
    """The unordered vertex-id edges of a closed cycle."""
    n = len(cycle)
    return {(min(cycle[i], cycle[(i + 1) % n]), max(cycle[i], cycle[(i + 1) % n]))
            for i in range(n)}


def render_patch(surface: GradedSurface, law: Law,
                 header: _t.Mapping[str, str] | None = None,
                 face_tags: _t.Mapping[int, _t.Mapping[str, str]] | None = None
                 ) -> tuple[str, int, int]:
    """``(text, ways, nodes)`` — the ``.osm`` document.  ``face_tags``:
    extra way tags per face id (``o4_grade_law_cap`` on a road bound to a
    stricter contiguous class)."""
    dp = surface.identity_dp
    zdp = z_decimals(law)
    reg = law.tables.precedence.roles
    lines: list[str] = ["<?xml version='1.0' encoding='UTF-8'?>"]
    attrs = {"version": "0.6", "upload": "false",
             "generator": "auto_patch_v2", "o4_engine": "auto_patch_v2/M2",
             "o4_ruleset": surface.ruleset, "o4_icao": surface.icao}
    attrs.update(header or {})
    lines.append("<osm " + " ".join(f"{k}={_q(v)}"
                                    for k, v in attrs.items()) + ">")
    nid_of: dict[int, int] = {}
    for v in surface.vertices:
        nid = -(v.id + 1)
        nid_of[v.id] = nid
        lines.append(f"  <node id='{nid}' action='modify' visible='true' "
                     f"lat='{_fmt(v.ll[0], dp)}' lon='{_fmt(v.ll[1], dp)}'>")
        lines.append(f"    <tag k='alt_abs' v='{_fmt(v.z, zdp)}' />")
        lines.append("  </node>")
    wid = -10000
    n_ways = 0

    def way(ids: _t.Sequence[int], tags: list[tuple[str, str]], closed: bool) -> None:
        nonlocal wid, n_ways
        wid -= 1
        n_ways += 1
        lines.append(f"  <way id='{wid}' action='modify' visible='true'>")
        seq = list(ids) + ([ids[0]] if closed else [])
        for v in seq:
            lines.append(f"    <nd ref='{nid_of[v]}' />")
        for k, val in tags:
            lines.append(f"    <tag k={_q(k)} v={_q(val)} />")
        lines.append("  </way>")

    from .graded import RIM_KIND
    ring_edges: set[tuple[int, int]] = set()
    for f in surface.faces:
        ring_edges.update(_edges(f.ring))
    for b in surface.breaklines:
        if b.kind == RIM_KIND:
            # a cut pavement's hole ring IS the rim: covered by it
            ring_edges.update(_edges(b.vertices[:-1] if b.vertices[0] == b.vertices[-1]
                                     else b.vertices))

    for f in surface.faces:
        spec = reg.get(f.role)
        extra = dict((face_tags or {}).get(f.id) or {})
        role = f.role
        if spec is not None and spec.oracle_role is not None:
            # THE ORACLE ALIAS (precedence.toml ``oracle_role``): the v1
            # census reads ``role`` from its own register, so an aliased
            # role is written under the name it judges, ``class`` names
            # the v2 role, and ``o4_grade_law_cap`` carries the v2 cap —
            # which the census composes as a MINIMUM with the alias's
            # cap, so it prices exactly the v2 table.
            role = spec.oracle_role
            extra["class"] = f.role
            rc = role_cap(law, f.role, f.code_number, f.code_letter)
            # THE ORACLE'S OWN CAP (``oracle_cap``, RULINGS 2026-09-08u (2)):
            # a structure ramp is priced in the PAIR frame at the ramp law's
            # ceiling, not at its face's longitudinal cap — the oracle reads
            # a 2.5 m-wide ramp's ring diagonals, which the face law does
            # not bound (measured: 181 lawful OTHH wall-corridor rows at
            # 8.2 % against the service_road alias's 8 %).  v2 verify keeps
            # the face cap and stays the stricter instrument.
            longitudinal = spec.oracle_cap if spec.oracle_cap is not None else \
                (None if rc is None else rc.longitudinal)
            if longitudinal is not None:
                prior = extra.get("o4_grade_law_cap")
                cap = longitudinal if prior is None else min(longitudinal, float(prior))
                extra["o4_grade_law_cap"] = f"{cap:g}"
            if spec.oracle_law is not None:
                # THE ORACLE'S LAW OVERRIDE (``oracle_law``): the v1 census
                # prices ``o4_grade_law=<law>`` at ROLE_GRADE_LIMITS[<law>]
                # composed with the cap tag — a door ramp under tunnel_ramp
                # reads service_road's 8 % (spec othh-terminal-ramps §4)
                extra["o4_grade_law"] = spec.oracle_law
        tags = [("aeroway", spec.aeroway if spec else "apron"),
                ("ref", f.ref), ("role", role), ("shapeID", str(f.id))]
        if f.code_letter:
            tags.append(("code_letter", f.code_letter))
        if f.code_number is not None:
            tags.append(("code_number", str(f.code_number)))
        if f.role == "runway":
            tags.append(("o4_single_poly", "1"))
        for k, val in sorted(extra.items()):
            tags.append((k, val))
        way(f.ring, tags, True)
        for h in f.holes:
            if _edges(h) <= ring_edges:
                continue                    # covered: the inner faces constrain it
            way(h, [("o4_feature", HOLE_FEATURE), ("shapeID", str(f.id))], True)
    for b in surface.breaklines:
        if b.kind == RIM_KIND and len(b.vertices) >= 3:
            # the rim: closed where the run is the whole ring (the first
            # vertex repeated), an open constrained chain where a tile
            # piece holds only part of it
            closed = b.vertices[0] == b.vertices[-1]
            way(b.vertices[:-1] if closed else b.vertices,
                [("o4_feature", RIM_FEATURE), ("ref", b.ref.split("@")[0])], closed)
            continue
        feat = _OPEN_WAY_KINDS.get(b.kind)
        if feat is None or len(b.vertices) < 2:
            continue
        way(b.vertices, [("o4_feature", feat), ("ref", b.ref)], False)
    lines.append("</osm>")
    return "\n".join(lines) + "\n", n_ways, len(surface.vertices)


def render_sidecar(law: Law, sidecar: _t.Mapping[str, _t.Any] | None) -> dict:
    """The sidecar document: the given keys (⊆ ``SIDECAR_KEYS``) plus
    ``ruleset`` and the always-empty declarations."""
    doc: dict[str, _t.Any] = {"ruleset": law.ruleset_key,
                              "terrace_joints": [], "basin_facilities": [],
                              "road_bridge_decks": []}
    for k, v in (sidecar or {}).items():
        if k not in SIDECAR_KEYS:
            raise ValueError(f"sidecar key {k!r} is not in SIDECAR_KEYS")
        doc[k] = v
    return doc


def write_patch(surface: GradedSurface, law: Law, out_dir: str | Path,
                sidecar: _t.Mapping[str, _t.Any] | None = None,
                header: _t.Mapping[str, str] | None = None,
                face_tags: _t.Mapping[int, _t.Mapping[str, str]] | None = None
                ) -> PatchPaths:
    """Write ``<out_dir>/<ICAO>_auto.patch.osm``, its ``.axes.json``
    sidecar (keys ⊆ :data:`SIDECAR_KEYS`; a key outside the register is
    an error) and ``<ICAO>.graded.json``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    text, n_ways, n_nodes = render_patch(surface, law, header, face_tags)
    patch = out / f"{surface.icao}_auto.patch.osm"
    patch.write_text(text)
    side = Path(str(patch) + ".axes.json")
    side.write_text(json.dumps(render_sidecar(law, sidecar), separators=(",", ":")))
    graded = out / f"{surface.icao}.graded.json"
    graded.write_text(surface.to_json(z_dp=z_decimals(law)))
    return PatchPaths(patch, side, graded, n_ways, n_nodes,
                      patch.stat().st_size, side.stat().st_size)


def tile_of_face(surface: GradedSurface, face) -> tuple[int, int]:
    """The 1° tile holding a face: the mean of its ring vertices (a face
    never straddles a tile line — the seam band is cut out of the map —
    so the mean of points inside one square is inside it)."""
    import math
    vs = {v.id: v for v in surface.vertices}
    lat = sum(vs[i].ll[0] for i in face.ring) / len(face.ring)
    lon = sum(vs[i].ll[1] for i in face.ring) / len(face.ring)
    return int(math.floor(lat)), int(math.floor(lon))


def write_tile_pieces(surface: GradedSurface, law: Law, out_dir: str | Path,
                      sidecar: _t.Mapping[str, _t.Any] | None = None,
                      header: _t.Mapping[str, str] | None = None,
                      face_tags: _t.Mapping[int, _t.Mapping[str, str]] | None = None
                      ) -> dict[tuple[int, int], PatchPaths]:
    """One patch per tile the surface touches, at the mesh's own path
    ``<out_dir>/<block>/<tile>/<ICAO>_auto.patch.osm`` (``O4_File_Names.
    patch_dir``: ``Patches/-20-080/-13-077/``), each carrying only the
    faces on that tile's side of the seam band, their vertices and the
    breakline runs inside them; the sidecar is the whole airport's (the
    census's axes and pairs are geometric, the tile filter is on faces).
    A single-tile surface writes one piece, identical to ``write_patch``."""
    import math
    by_tile: dict[tuple[int, int], list] = {}
    for f in surface.faces:
        by_tile.setdefault(tile_of_face(surface, f), []).append(f)
    vs = {v.id: v for v in surface.vertices}
    out: dict[tuple[int, int], PatchPaths] = {}
    for (lat, lon), faces in sorted(by_tile.items()):
        keep = {i for f in faces for i in f.ring} | \
            {i for f in faces for h in f.holes for i in h}
        # breakline stations INSIDE a face (the runway ridge's profile
        # stations are not ring vertices) travel with their tile, so the
        # piece's crown spine keeps the stations the census reads against
        for b in surface.breaklines:
            keep |= {i for i in b.vertices
                     if (int(math.floor(vs[i].ll[0])), int(math.floor(vs[i].ll[1]))) == (lat, lon)}
        verts = tuple(v for v in surface.vertices if v.id in keep)
        bls = []
        for b in surface.breaklines:
            run = [i for i in b.vertices if i in keep]
            if len(run) >= 2:
                bls.append(_dc.replace(b, vertices=tuple(run)))
        piece = _dc.replace(surface, vertices=verts, faces=tuple(faces),
                            breaklines=tuple(bls))
        block = f"{(lat // 10) * 10:+03d}{(lon // 10) * 10:+04d}"
        tile = f"{lat:+03d}{lon:+04d}"
        hdr = dict(header or {})
        hdr["o4_tile"] = tile
        out[(lat, lon)] = write_patch(piece, law, Path(out_dir) / block / tile,
                                      sidecar, hdr, face_tags)
    return out
