"""#2084: densifying a valid face never hands a cell a MultiPolygon.

GEOS's densifier repairs a result its rounding made invalid, so
``shapely.segmentize`` of this valid four-vertex pit-floor face (a
near-collinear spike, read from the #2084 replay) returns three parts:
the face and two ~1e-13 m2 slivers.  ``geom.parts.densified_parts`` and
the three planar sites that densify cell faces must return Polygons only.
"""
from __future__ import annotations

import shapely
from auto_patch_v2.geom.parts import densified_parts
from shapely.geometry import Polygon

_SPIKE = ("01030000000100000005000000AA965C1E034998C06BD649B5B2409EC0FDC5D9472A4998C0"
          "FB669BE77AB79EC06B043ED8DC6098C0E998A05CB55C9EC0DB3D094D867698C076EAC10626"
          "769EC0AA965C1E034998C06BD649B5B2409EC0")


def _face() -> Polygon:
    return shapely.from_wkb(bytes.fromhex(_SPIKE))


def test_segmentize_of_the_face_is_multi_on_this_geos():
    """The premise: if GEOS stops repairing, this twin documents why it was needed."""
    face = _face()
    assert face.is_valid and face.geom_type == "Polygon"
    got = shapely.segmentize(face, 2.0)
    if got.geom_type == "Polygon":      # a GEOS that no longer repairs
        return
    assert got.geom_type == "MultiPolygon"


def test_densified_parts_are_polygons_with_the_face_area():
    face = _face()
    parts = densified_parts(face, 2.0)
    assert parts and all(p.geom_type == "Polygon" for p in parts)
    assert len(parts) == 1
    assert abs(sum(p.area for p in parts) - face.area) < 1e-6
    # densified: no edge longer than the step
    xy = shapely.get_coordinates(parts[0].exterior)
    seg = ((xy[1:] - xy[:-1]) ** 2).sum(axis=1) ** 0.5
    assert seg.max() <= 2.0 + 1e-9


def test_object_floor_faces_take_densified_parts():
    """The site of #2084: a one-plane floor's faces are its densified parts."""
    import types

    import numpy as np
    from auto_patch_v2.planar import object_floor_cells as ofc

    face = _face()
    tri = np.array([[[*face.exterior.coords[0], 0.0], [*face.exterior.coords[1], 0.0],
                     [*face.exterior.coords[2], 0.0]]])
    fl = types.SimpleNamespace(faces=tri)
    ob = types.SimpleNamespace(wall_sample_m=2.0, crease_deg=5.0, hollow_m=0.1)
    law = types.SimpleNamespace(tables=types.SimpleNamespace(
        structures=types.SimpleNamespace(tunnel=types.SimpleNamespace(object=ob))))
    faces = ofc._floor_faces(fl, face, [face], law)
    assert faces and all(q.geom_type == "Polygon" for q in faces)
