"""THE ``[tunnel.object]`` SCHEMA — the pack's tunnel WALL objects as the
tunnel authority (RULINGS 2026-09-05k-1 / 05n / 06c / 06f / 09w), and the
THIN-PLATE wall class of spec §33 (2) (RULINGS 2026-09-13i).

Split out of ``law/model.py`` (lane ``v2wallplate``) for the 1,000-line
file law that ``tests/auto_patch_v2/test_model.py`` enforces, exactly as
``flat_site_schema`` / ``rebake_schema`` / ``cutout_schema`` /
``basin_schema`` already are, and re-exported from ``law.model``.  No
numeric value appears here: the values live in ``law/structures.toml``.
"""
from __future__ import annotations

import dataclasses as _dc


@_dc.dataclass(frozen=True)
class TunnelObject:
    """Tunnel wall OBJECTS as the tunnel authority (05k-1, 05n, 06c; ``[tunnel.object]``)."""

    source_precedence: tuple[str, ...]
    plate_datum: str
    mouth_depth: str
    ramp_end: str
    trench: str
    wall_face_max_thickness_m: float
    wall_sample_m: float
    mouth_end: str
    reseat: bool
    skirt_min_depth_m: float
    plate_normal_y_min: float
    plate_bin_m: float
    plate_min_area_m2: float
    plate_min_height_m: float
    edge_wall_max_plate_m: float       # 2026-09-06c (2): below it an EDGE WALL (plan from the walls, depth from the bore law)
    edge_wall_min_skirt_m: float       # 2026-09-06f: the edge wall's skirt below ITS crest (the top band, wherever it lies vs the seat)
    skirt_perimeter_min_fraction: float  # 2026-09-09w (2): the skirt must stand under this share of the crest plate's PERIMETER — a slab over a floor is a roof
    hull_min_length_m: float
    end_cap_open_m: float
    bore_end_tolerance_m: float        # 2026-09-08o: a bore END within this of the plate is that object's mouth
    thin_plate_min_m: float            # spec §33 (2) (RULINGS 2026-09-13i): THE THIN-PLATE WALL CLASS — solids spanning at least this over a mapped bore / deck are an AUTHORED CORRIDOR
    merge_gap_m: float
