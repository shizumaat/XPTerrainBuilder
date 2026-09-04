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
  * one closed way per HOLE, tagged ``o4_feature=gap_interior_ring``
    exactly as v1 so the census keeps it out of the ring laws and the
    mesh still constrains it (``include_patches`` inserts every closed
    way as a ring; ``_parse_osm`` routes the feature class to
    ``feature_out``);
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
from .graded import z_decimals
from .surface import GradedSurface

__all__ = ["SIDECAR_KEYS", "PatchPaths", "write_patch", "render_patch",
           "render_sidecar", "tile_of_face", "write_tile_pieces"]

#: The sidecar keys v2 publishes, and nothing else (Appendix A §5).
SIDECAR_KEYS: tuple[str, ...] = (
    "ruleset", "axes", "routes", "runway_end_skirt", "crown_drops",
    "road_bridge_decks", "terrace_joints", "basin_facilities",
    "airside_no_step_edges", "mesh_edges", "pair_caps", "seam_pins",
)

#: Feature class of a hole ring (v1 vocabulary the census and mesh read).
HOLE_FEATURE = "gap_interior_ring"
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

    for f in surface.faces:
        spec = reg.get(f.role)
        tags = [("aeroway", spec.aeroway if spec else "apron"),
                ("ref", f.ref), ("role", f.role), ("shapeID", str(f.id))]
        if f.code_letter:
            tags.append(("code_letter", f.code_letter))
        if f.code_number is not None:
            tags.append(("code_number", str(f.code_number)))
        if f.role == "runway":
            tags.append(("o4_single_poly", "1"))
        for k, val in sorted(((face_tags or {}).get(f.id) or {}).items()):
            tags.append((k, val))
        way(f.ring, tags, True)
        for h in f.holes:
            way(h, [("o4_feature", HOLE_FEATURE), ("shapeID", str(f.id))], True)
    for b in surface.breaklines:
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
    by_tile: dict[tuple[int, int], list] = {}
    for f in surface.faces:
        by_tile.setdefault(tile_of_face(surface, f), []).append(f)
    out: dict[tuple[int, int], PatchPaths] = {}
    for (lat, lon), faces in sorted(by_tile.items()):
        keep = {i for f in faces for i in f.ring} | \
            {i for f in faces for h in f.holes for i in h}
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
