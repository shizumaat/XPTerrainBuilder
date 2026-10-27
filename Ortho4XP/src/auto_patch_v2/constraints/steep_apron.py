"""AN APRON JOINED TO A STEEP RUNWAY IS ONE TERRACE (owner RULINGS
2026-10-26n, Q162: "Generally yes, and especially at VNLK there are many
terraces and retaining walls"; replaces 2026-10-10j at a steep runway; spec
``docs/findings/vnlk-junctions-lvnlk.md``).

A STEEP runway is one carrying junction flats (``constraints/
runway_junctions``, published on ``PlanarMap.runway_caps``).  An APRON
pavement it joins — a pavement ref with an apron-role face, one of whose
faces is one of those junctions — is ONE PLANE over every vertex of every
face of that ref, its runway-shared vertices left out (the runway is fixed
before the apron, §20b; the weld is carried by the no-step rows across that
edge, the ``hard_plane`` precedent).  The plane's level and tilt are the
junction mouth's — within the taxi transverse cap there by construction —
and the apron's own hard caps bound its tilt.  It never follows the runway's
grade (``runway_yield.derive_taxi`` no longer yields it).

Geometry only, read off the published junction record; nothing here names
an airport.
"""
from __future__ import annotations

from ..law import Law
from ..law.tables import apron_roles
from ..model.airport import Airport
from ..model.constraints import Row, Source
from ..model.planar import PlanarMap
from .platform import coplanar_rows

__all__ = ["steep_apron_plane", "terrace_refs", "GEN", "RULING"]

GEN = "steep_apron_plane"
#: the row head (``[design] hard_rulings``, the apron tier)
RULING = "rulesets.apron terrace plane at a steep runway"

_RUNWAY_FAMILY = ("runway", "runway_crossing")


def terrace_refs(planar: PlanarMap, law: Law) -> list[str]:
    """The apron pavement refs a steep runway joins (module docstring)."""
    caps = getattr(planar, "runway_caps", None) or {}
    joined = {f for rc in caps.values() for jn in getattr(rc, "junctions", ())
              for f in jn.faces}
    if not joined:
        return []
    aprons = apron_roles(law)
    refs = {planar.faces[f].ref for f in joined if f in planar.faces}
    return sorted(r for r in refs if r and any(
        f.ref == r and f.role in aprons for f in planar.faces.values()))


def steep_apron_plane(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """ONE hard plane per terraced apron ref (module docstring)."""
    refs = terrace_refs(planar, law)
    if not refs:
        return []
    runway: set[int] = set()
    for f in planar.faces.values():
        if f.role in _RUNWAY_FAMILY:
            for cyc in (f.ring, *f.holes):
                runway.update(planar.ring_vertices(cyc))
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    rows: list[Row] = []
    for ref in refs:
        vs = sorted({v for f in planar.faces.values() if f.ref == ref
                     for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)}
                    - runway)
        if len(vs) < 4:
            continue
        src = Source(GEN, RULING + " (RULINGS 2026-10-26n Q162)",
                     (f"ref:{ref}", f"vertices:{len(vs)}"))
        # the plane's basis is drawn from the pavement's OWN vertices (no
        # foreign face): a vertex a pad fronts may give at its contact
        # (RULINGS 2026-10-08d (2)) and must not carry the whole terrace
        own = [v for v in vs if all(planar.faces[f].ref == ref
                                    for f in planar.vertices[v].incident_faces
                                    if f in planar.faces)]
        rows.extend(coplanar_rows(xy, vs, src, own) or ())
    return rows
