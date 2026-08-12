"""R17-2, the ELEVATION authority: the declared corridor grades at Z0.

The corridor joins the flat extent as its own constant inset — one per
declared box, never a grown extent (the R8-1 channel ruling: the open
water outside the box must stay sea, and a single box spanning airport
and island would flatten the channel between them).

And it is baked WITHOUT the R11-2 datum refusal.  That gate weighs
EVIDENCE — does the feather ring say these two surfaces belong together
— and it correctly refuses VHHH's causeway CLUSTER at a −10.82 m median,
because the channel it crosses is water.  A declaration is the owner
overruling that evidence on INTENT, which is the whole reason the
declaration exists.

Headless: the bake is stubbed; what is asserted is which insets are
offered to it, with which extents, at which Z0, and under which refusal.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402

OWNER_BOX = (22.3125624, 113.9426422, 22.3145276, 113.9469981)


class _DEM:
    def __init__(self):
        self.alt_dem = numpy.zeros((4, 4), dtype=numpy.float32)


class _Tile:
    lat = 22
    lon = 113
    airport_elevation_inset_feather_m = 60.0

    def __init__(self):
        self.dem = _DEM()


def _substitution(corridors):
    return [{
        "icao": "VHHH",
        "verdict": "flat_candidate",
        "z0_m": 7.315,
        "extent_deg": (0.85, 0.29, 0.96, 0.34),
        "extent_area_km2": 12.5,
        "object_clusters": [],
        "cluster_findings": [],
        "declared_corridors": corridors,
        "record": {},
    }]


def _run(monkeypatch, corridors):
    baked = []

    def _bake(tile, inset_path, feather_m, inset=None,
              refuse_datum_offset_over_m=None):
        baked.append({
            "label": getattr(inset, "label", None),
            "extent": (inset.x0, inset.y0, inset.x1, inset.y1),
            "elevation_m": inset.elevation_m,
            "refuse_over_m": refuse_datum_offset_over_m,
        })
        return 0.0

    monkeypatch.setattr(INSETS, "_bake_one_inset", _bake)
    import auto_patch.flat_site_mode as FSM
    monkeypatch.setattr(FSM, "flat_site_substitutions",
                        lambda tile, dico_airports=None: _substitution(
                            corridors))
    tile = _Tile()
    INSETS.overlay_flat_site_insets(tile)
    return tile, baked


class TestDeclaredCorridorInset:
    def test_one_inset_per_declared_box_at_the_airports_z0(self, monkeypatch):
        corridor = {"extent_deg": (0.9426422, 0.3125624,
                                   0.9469981, 0.3145276),
                    "corridor_wgs84": list(OWNER_BOX)}
        _tile, baked = _run(monkeypatch, [corridor])
        assert len(baked) == 2                      # extent + corridor
        corridor_bake = baked[-1]
        assert "declared corridor" in corridor_bake["label"]
        assert corridor_bake["elevation_m"] == 7.315
        # R17c-2: the RASTER is the declared box grown by the feather, so
        # the ramp lands outside the declaration and Z0 holds to its
        # boundary.  The declared box is what the PROVENANCE keeps (the
        # test below), because that is what the wall admission reads.
        assert corridor_bake["extent"] == INSETS._feather_outward_extent(
            _Tile(), *corridor["extent_deg"], 60.0)
        assert corridor_bake["extent"] != corridor["extent_deg"]

    def test_the_datum_refusal_is_not_applied_to_a_declaration(
            self, monkeypatch):
        corridor = {"extent_deg": (0.9426422, 0.3125624,
                                   0.9469981, 0.3145276),
                    "corridor_wgs84": list(OWNER_BOX)}
        _tile, baked = _run(monkeypatch, [corridor])
        assert baked[-1]["refuse_over_m"] is None

    def test_the_provenance_names_the_declared_ground(self, monkeypatch):
        corridor = {"extent_deg": (0.9426422, 0.3125624,
                                   0.9469981, 0.3145276),
                    "corridor_wgs84": list(OWNER_BOX)}
        tile, _baked = _run(monkeypatch, [corridor])
        stamped = tile.dem.synthetic_flat_site_provenance
        kinds = [entry["kind"] for entry in stamped]
        assert kinds == ["synthetic_flat_site", "declared_corridor"]
        assert stamped[-1]["corridor_wgs84"] == list(OWNER_BOX)
        assert stamped[-1]["z0_m"] == 7.315

    def test_no_declaration_bakes_only_the_airports_own_extent(
            self, monkeypatch):
        _tile, baked = _run(monkeypatch, [])
        assert len(baked) == 1
        assert "declared corridor" not in (baked[0]["label"] or "")

    def test_two_boxes_are_two_insets_never_their_union(self, monkeypatch):
        boxes = [
            {"extent_deg": (0.9426422, 0.3125624, 0.9469981, 0.3145276),
             "corridor_wgs84": list(OWNER_BOX)},
            {"extent_deg": (0.80, 0.20, 0.81, 0.21),
             "corridor_wgs84": [22.20, 113.80, 22.21, 113.81]},
        ]
        _tile, baked = _run(monkeypatch, boxes)
        assert len(baked) == 3
        extents = {b["extent"] for b in baked[1:]}
        # R17c-2: each declared box is grown by the feather ON ITS OWN —
        # two rasters, never one union, and never one grown extent.
        assert extents == {
            INSETS._feather_outward_extent(_Tile(), *b["extent_deg"], 60.0)
            for b in boxes}
