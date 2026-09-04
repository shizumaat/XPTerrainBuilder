"""The Ortho4XP ``.osm`` patch adapter — API (plan §1 row 7; Appendix A
§5).  M2 implements ``write_patch``; M0 freezes what it writes.

WHAT THE MESH READS (``src/O4_Vector_Map.py:2639-2826``, Appendix A §5):
way ``altitude`` / ``node_altitudes`` / ``cst_alt_abs``, node ``alt_abs``
(overrides the way), ``role`` only for the seawall/flood admission, and
the sidecar key ``road_bridge_decks``.  ``ref``, ``shapeID`` and
``aeroway`` are NOT read by the mesh — they are census inputs.

THE PATCH v2 WRITES:
  * one closed way per face ring (and one per hole, tagged
    ``o4_feature=gap_interior_ring`` exactly as v1 so the mesh treats
    it as a ring), tags ``aeroway`` (from the role register), ``role``,
    ``ref``, ``shapeID`` (= face id), node ``alt_abs`` per vertex;
  * one open way per breakline (``DUMMY`` in the mesh: a constrained
    line), node ``alt_abs`` per vertex, tag ``o4_breakline=<kind>``;
  * node ids: ONE node per surface vertex — a coordinate is ONE node
    (the stacked-nodes family is impossible by construction);
  * lat/lon at ``identity_dp``; ``alt_abs`` quantised ONCE at 2 dp.

THE SIDECAR (``<patch>.axes.json``) carries ONLY the census inputs
Appendix A §5 lists that v2 has: ``ruleset``, ``axes`` (taxi centreline
chains with per-letter caps — from the breaklines of kind
``taxi_centerline``), ``routes`` (the reach), ``runway_end_skirt``
stations, ``crown_drops``, ``road_bridge_decks`` (the one key the mesh
reads), ``terrace_joints`` (always empty in v2: no terraces),
``basin_facilities``, ``airside_no_step_edges`` (the direct-distance
pairs the solver priced), ``mesh_edges`` (junction triangles),
``pair_caps`` (per pair cap the solver used — the census prices against
the solve's own publication).  Nothing else: v1's 24 MB SPJC sidecar was
instrument-only (Appendix B §1).

The v1 census (``tools/harness/census.py``) is the ORACLE over this
output until ``verify/`` is proven equal on three airports (plan §1
``verify`` row).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t
from pathlib import Path

from ..law.model import Law
from .surface import GradedSurface

__all__ = ["SIDECAR_KEYS", "PatchPaths", "write_patch"]

#: The sidecar keys v2 publishes, and nothing else (Appendix A §5).
SIDECAR_KEYS: tuple[str, ...] = (
    "ruleset", "axes", "routes", "runway_end_skirt", "crown_drops",
    "road_bridge_decks", "terrace_joints", "basin_facilities",
    "airside_no_step_edges", "mesh_edges", "pair_caps",
)


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


def write_patch(surface: GradedSurface, law: Law, out_dir: str | Path,
                sidecar: _t.Mapping[str, _t.Any] | None = None
                ) -> PatchPaths:
    """Write ``<out_dir>/<ICAO>_auto.patch.osm``, its ``.axes.json``
    sidecar (keys ⊆ :data:`SIDECAR_KEYS`; a key outside the register is
    an error) and ``<ICAO>.graded.json``.  M2 implements; M0 raises."""
    raise NotImplementedError("write_patch is an M2 deliverable")
