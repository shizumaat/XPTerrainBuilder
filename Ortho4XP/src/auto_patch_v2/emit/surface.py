"""GradedSurface — THE format-agnostic product (plan "Portability
requirement"; M6 freezes the schema, M0 states it).

A graded surface is the planar map with a solved ``z`` per vertex: the
faces (role, ref), the edges implicitly (each face ring), and the
breaklines the mesh must keep as constrained lines.  The Ortho4XP
``.osm`` patch and the S2 elevation-layer adapter are both projections
of this object; nothing downstream of ``solve`` reads anything else.

JSON schema (``SCHEMA`` below, draft 2020-12 subset) — one file per
airport, ``<ICAO>.graded.json``:

    {"schema": "auto_patch_v2.graded_surface/1",
     "icao": "CYXY", "ruleset": "icao",
     "frame": {"origin": [lat, lon], "crs": "+proj=tmerc …", "identity_dp": 11},
     "vertices": [[id, lat, lon, z], …],           # lat/lon at identity_dp
     "faces":    [{"id", "role", "ref", "ring": [vertex ids], "holes": [[…]],
                   "code_number", "code_letter", "side"}, …],
     "breaklines": [{"id", "kind", "ref", "vertices": [ids]}, …],
     "provenance": {"planar_sha256", "constraints_sha256", "law_sha256",
                    "solver": {"backend", "status", "residual_m"}}}

Vertices carry lat/lon (not x/y): the product must survive the frame,
and the 11-dp identity IS the vertex.  ``z`` is emitted ONCE at the
materiality floor's precision (``emit.materiality.elevation_m``) — the
one quantisation (plan §1 row 7).
"""
from __future__ import annotations

import dataclasses as _dc
import json
import typing as _t

from ..model.frame import LL

__all__ = ["SCHEMA_ID", "SCHEMA", "SurfaceVertex", "SurfaceFace",
           "SurfaceBreakline", "GradedSurface"]

SCHEMA_ID = "auto_patch_v2.graded_surface/1"

SCHEMA: dict[str, _t.Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": SCHEMA_ID,
    "type": "object",
    "required": ["schema", "icao", "ruleset", "frame", "vertices", "faces",
                 "breaklines", "provenance"],
    "additionalProperties": False,
    "properties": {
        "schema": {"const": SCHEMA_ID},
        "icao": {"type": "string", "minLength": 3, "maxLength": 4},
        "ruleset": {"type": "string"},
        "frame": {
            "type": "object", "additionalProperties": False,
            "required": ["origin", "crs", "identity_dp"],
            "properties": {
                "origin": {"type": "array", "minItems": 2, "maxItems": 2,
                           "items": {"type": "number"}},
                "crs": {"type": "string"},
                "identity_dp": {"type": "integer", "minimum": 1}}},
        "vertices": {"type": "array", "items": {
            "type": "array", "minItems": 4, "maxItems": 4,
            "prefixItems": [{"type": "integer"}, {"type": "number"},
                            {"type": "number"}, {"type": "number"}]}},
        "faces": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "role", "ref", "ring", "holes", "side"],
            "properties": {
                "id": {"type": "integer"}, "role": {"type": "string"},
                "ref": {"type": "string"}, "side": {"type": "string"},
                "ring": {"type": "array", "minItems": 3,
                         "items": {"type": "integer"}},
                "holes": {"type": "array", "items": {
                    "type": "array", "minItems": 3,
                    "items": {"type": "integer"}}},
                "code_number": {"type": ["integer", "null"]},
                "code_letter": {"type": ["string", "null"]}}}},
        "breaklines": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "kind", "ref", "vertices"],
            "properties": {
                "id": {"type": "integer"}, "kind": {"type": "string"},
                "ref": {"type": "string"},
                "vertices": {"type": "array", "minItems": 2,
                             "items": {"type": "integer"}}}}},
        "provenance": {"type": "object"},
    },
}


@_dc.dataclass(frozen=True)
class SurfaceVertex:
    """One vertex: identity lat/lon and the solved elevation."""

    id: int
    ll: LL
    z: float


@_dc.dataclass(frozen=True)
class SurfaceFace:
    """One face by VERTEX ids (rings closed implicitly, first not
    repeated)."""

    id: int
    role: str
    ref: str
    ring: tuple[int, ...]
    holes: tuple[tuple[int, ...], ...]
    side: str
    code_number: int | None = None
    code_letter: str | None = None


@_dc.dataclass(frozen=True)
class SurfaceBreakline:
    """One breakline by vertex ids."""

    id: int
    kind: str
    ref: str
    vertices: tuple[int, ...]


@_dc.dataclass(frozen=True)
class GradedSurface:
    """The product.  ``to_json`` / ``from_json`` round-trip exactly
    (the M6 bar: CYXY round-trips)."""

    icao: str
    ruleset: str
    origin: LL
    crs: str
    identity_dp: int
    vertices: tuple[SurfaceVertex, ...]
    faces: tuple[SurfaceFace, ...]
    breaklines: tuple[SurfaceBreakline, ...]
    provenance: _t.Mapping[str, _t.Any]

    def to_dict(self, z_dp: int = 2) -> dict[str, _t.Any]:
        """The schema document.  ``z_dp`` is the ONE quantisation of
        elevation (2 = the 0.01 m materiality floor)."""
        return {
            "schema": SCHEMA_ID, "icao": self.icao, "ruleset": self.ruleset,
            "frame": {"origin": [self.origin[0], self.origin[1]],
                      "crs": self.crs, "identity_dp": self.identity_dp},
            "vertices": [[v.id, round(v.ll[0], self.identity_dp),
                          round(v.ll[1], self.identity_dp),
                          round(v.z, z_dp)] for v in self.vertices],
            "faces": [{"id": f.id, "role": f.role, "ref": f.ref,
                       "ring": list(f.ring),
                       "holes": [list(h) for h in f.holes],
                       "side": f.side, "code_number": f.code_number,
                       "code_letter": f.code_letter} for f in self.faces],
            "breaklines": [{"id": b.id, "kind": b.kind, "ref": b.ref,
                            "vertices": list(b.vertices)}
                           for b in self.breaklines],
            "provenance": dict(self.provenance),
        }

    def to_json(self, z_dp: int = 2) -> str:
        """Serialise (sorted keys, no whitespace variance: hashable)."""
        return json.dumps(self.to_dict(z_dp), sort_keys=True,
                          separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "GradedSurface":
        """Parse a schema document; raises ``ValueError`` on a wrong
        schema id or a missing section."""
        if d.get("schema") != SCHEMA_ID:
            raise ValueError(f"not a {SCHEMA_ID} document")
        for k in SCHEMA["required"]:
            if k not in d:
                raise ValueError(f"graded surface missing {k!r}")
        fr = d["frame"]
        return cls(
            icao=d["icao"], ruleset=d["ruleset"],
            origin=(float(fr["origin"][0]), float(fr["origin"][1])),
            crs=fr["crs"], identity_dp=int(fr["identity_dp"]),
            vertices=tuple(SurfaceVertex(int(i), (float(la), float(lo)),
                                         float(z))
                           for i, la, lo, z in d["vertices"]),
            faces=tuple(SurfaceFace(
                id=int(f["id"]), role=f["role"], ref=f["ref"],
                ring=tuple(f["ring"]),
                holes=tuple(tuple(h) for h in f["holes"]),
                side=f["side"], code_number=f.get("code_number"),
                code_letter=f.get("code_letter")) for f in d["faces"]),
            breaklines=tuple(SurfaceBreakline(
                id=int(b["id"]), kind=b["kind"], ref=b["ref"],
                vertices=tuple(b["vertices"])) for b in d["breaklines"]),
            provenance=dict(d["provenance"]))

    @classmethod
    def from_json(cls, text: str) -> "GradedSurface":
        """Parse serialised JSON."""
        return cls.from_dict(json.loads(text))
