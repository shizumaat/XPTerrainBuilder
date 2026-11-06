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
    authored_crest_max_m: float        # object-placement spec §18 (3): the band a crest at the AUTHORED seat over the engine's own cut keeps its seat in
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
    # ── spec §33 (6) THE PACK'S STRUCTURE OBJECTS ARE THE CUT GEOMETRY
    # (owner RULINGS 2026-09-15e/15g, Fable 2026-09-15j; lane v2objcut)
    shell_floor_min_m: float           # B: the SHELL's largest horizontal plate stands at least this far below the object's zero — that plate IS the floor and its level is the AUTHORED depth
    cover_flush_m: float               # B: the COVER's HARD_DECK plate is FLUSH — |y| at most this
    # B: a SHELL's plates at or above its zero cover at most this share of
    # its trench outline; more is a building (#1726)
    shell_at_zero_max_fraction: float
    cover_placement_tol_m: float       # B: the cover stands at the SAME placement — position within this, same heading
    # #1903: a FLOOR object — its near-horizontal faces carry at least this
    # share of its solid surface
    floor_object_min_share: float
    # #1903: …whose cover stands its deep walls on this share of its ring
    floor_walled_min_share: float
    # #1883 round 3 / #1914: THE CONCAVE CUT SHELL (``airport/object_floor``,
    # ``geom/shape_class``): an open-top hollow whose top stands ``hollow_m``
    # under its own rim (its outline band, ``shell_rim_band_m`` wide) over
    # ``shell_hollow_min_share`` of its inner plan; two surfaces more than
    # ``shell_stacked_m`` apart are a cover over a floor; less relief than
    # ``shell_flat_m`` is a plate; the raster holds ``shell_raster_cells``
    hollow_m: float
    shell_hollow_min_share: float
    shell_stacked_m: float
    shell_flat_m: float
    shell_rim_band_m: float
    shell_raster_cells: int
    # #1883 r3 A5: the shell's footprint splits where its faces fold more
    # than this, so each cell is one plane of the shell
    crease_deg: float
    # #1914 (owner 2026-11-06T16:13Z "Yes, let's hide cut shells"): a shell
    # that is the deepest stated surface with its rim at grade (within
    # ``shell_rim_ground_m`` over ``shell_rim_ground_share`` of its outline)
    # is left out of the written DSF — the ground IS its surface
    hide_concave_shells: bool
    shell_rim_ground_m: float
    shell_rim_ground_share: float
    cover_station_m: float             # B: the cover's descending profile is binned this fine along the axis; each bin's LOWEST y is a ramp station
    parapet_max_height_m: float        # C: a thin surface wall is shorter than this
    parapet_max_width_m: float         # C: …and narrower than this in plan
    parapet_min_aspect: float          # C: …and at least this many times longer than it is high
    parapet_y_min: float               # C: …and sits ON the surface (its lowest authored vertex is no deeper than this)
    pair_spacing_min_m: float          # C: a PAIR's axes stand this far apart at least
    pair_spacing_max_m: float          # C: …and this far at most
    pair_overlap_min_fraction: float   # C: …and overlap this share of the shorter band along the axis
