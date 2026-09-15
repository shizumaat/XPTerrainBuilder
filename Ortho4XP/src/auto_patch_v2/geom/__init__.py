"""THE LEAF GEOMETRY (owner RULINGS 2026-09-11x (4)).

A package BELOW ``law``: it imports nothing of ``auto_patch_v2`` at all,
so any layer may read it.  It exists because two layers that may not
import each other — ``solve`` (the sheet's curvature domain) and
``constraints`` (where in a face a foot stands) — need the SAME
triangulation of a face, and a copy of a geometry routine is a defect.

Only shape lives here: no law value, no model type, no I/O.
"""
from __future__ import annotations

from .cluster_outline import (OUTLINE_SIMPLIFY_M, AirsideRim,
                              airside_vertex_snap, cluster_outlines)
from .triangulate import face_triangles

__all__ = ["face_triangles", "cluster_outlines", "OUTLINE_SIMPLIFY_M",
           "AirsideRim", "airside_vertex_snap"]
