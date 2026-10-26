"""What the patch editor copies for an issue report (#1281; the Mac app's
``SceneryKit/PatchShapeReference.swift``, twin-tested on
``tests/fixtures/patch_shape_reference.json``).

* :func:`shape_reference_text` — the pure formatter: one plain-text block
  that locates a shape exactly (tile, airport, patch file, engine version,
  way id, ``ref``/``role``/``name`` tags, centroid, vertex count, area,
  elevation range and the first vertices);
* :func:`shape_reference` — that block for one way of an open patch.

The node format is ``lat, lon`` with 9 decimals (``O4_Qt_Patch_Panel
.node_lat_lon``).  No Qt here: the clipboard is the caller's.
"""
from __future__ import annotations

import typing as _t

__all__ = ["COPY_COORDINATES", "COPY_SHAPE_REFERENCE", "FIRST_VERTICES", "REFERENCE_TAGS",
           "shape_reference_text", "shape_reference"]

#: The map right-click menu's items (the Mac's ``PatchCopyItem`` titles).
COPY_COORDINATES = "Copy coordinates"
COPY_SHAPE_REFERENCE = "Copy shape reference"

#: How many vertices the block lists.
FIRST_VERTICES = 5
#: The tags the block names, in this order, when the way has them.
REFERENCE_TAGS = ("ref", "role", "name")

Vertex = _t.Tuple[float, float, _t.Optional[float]]


def _lat_lon(lat: float, lon: float) -> str:
    return "%.9f, %.9f" % (lat, lon)


def shape_reference_text(tile: str, icao: str, patch_file: str, engine_version: str,
                         way_id: int, tags: _t.Mapping[str, str], closed: bool,
                         area_m2: float, vertices: _t.Sequence[Vertex]) -> str:
    """The block for one shape.  ``vertices`` are its ``(lat, lon, alt or
    None)`` in ring order without a closed way's repeated first node."""
    lines = ["Shape reference (XPTerrainBuilder)",
             "Tile: %s" % tile,
             "Airport: %s" % icao,
             "Patch file: %s" % patch_file,
             "Engine: %s" % (engine_version or "unknown"),
             "Way: %d" % way_id]
    lines += ["%s: %s" % (k, tags[k]) for k in REFERENCE_TAGS if tags.get(k)]
    if vertices:
        # a plain left fold, as the Swift twin sums (``sum`` compensates)
        lat = lon = 0.0
        for v in vertices:
            lat += v[0]
            lon += v[1]
        lines.append("Centroid: %s" % _lat_lon(lat / len(vertices), lon / len(vertices)))
    lines.append("Vertices: %d" % len(vertices))
    lines.append("Area: %.1f m²" % area_m2 if closed else "Area: open line")
    alts = [v[2] for v in vertices if v[2] is not None]
    if alts:
        text = "Elevation: %.2f – %.2f m" % (min(alts), max(alts))
        if len(alts) < len(vertices):
            text += " (%d from the mesh)" % (len(vertices) - len(alts))
    else:
        text = "Elevation: from the mesh"
    lines.append(text)
    lines.append("First vertices:")
    lines += [_lat_lon(v[0], v[1]) for v in vertices[:FIRST_VERTICES]]
    return "\n".join(lines)


def shape_reference(patch, doc, way_id: int, engine_version: str) -> str:
    """The block for way ``way_id`` of ``doc``, the open ``patch``
    (``O4_Qt_Patch_Model.LoadedPatch``)."""
    import O4_Qt_Patch_ShapePick as PICK
    way = next(w for w in doc.ways if w.id == way_id)
    refs = way.refs[:-1] if way.closed else way.refs
    vertices = [doc.nodes[r][1:] for r in refs if r in doc.nodes]
    return shape_reference_text(patch.tile, patch.icao, patch.file_name, engine_version,
                                way.id, way.tags, way.closed,
                                PICK.shape_stats(doc, way.id).area_m2, vertices)
