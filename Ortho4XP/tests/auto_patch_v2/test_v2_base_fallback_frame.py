"""Issue #1743: a base cell the tile build read from a FALLBACK source
(#561/#1603) is a WARM production frame, resolved through the same chain
the core's reader walks (``base_fallback.fallback_cache_paths``) — never
"NO base raster" because the configured ``.hgt`` is absent.
"""
from __future__ import annotations

import os

from auto_patch_v2.airport import dem_production as DP


def _block(root, lat, lon):
    path = os.path.join(root, f"{(lat // 10) * 10:+03d}{(lon // 10) * 10:+04d}")
    os.makedirs(path, exist_ok=True)
    return path


def _fallback_name(lat, lon):
    import O4_Airport_Elevation_Insets as PROVIDERS
    from elevation_access import base_fallback

    if not PROVIDERS.elevation_providers_dict:
        PROVIDERS.initialize_elevation_providers_dict()
    paths = base_fallback.fallback_cache_paths(
        PROVIDERS.elevation_providers_dict, lat, lon)
    (code, path) = next(iter(paths.items()))
    return code, os.path.basename(path)


def test_a_fallback_base_cell_is_a_warm_frame(tmp_path):
    (lat, lon) = (63, -23)
    elevation = str(tmp_path / "e")
    (code, name) = _fallback_name(lat, lon)
    base = os.path.join(_block(elevation, lat, lon), name)
    with open(base, "wb") as fh:
        fh.write(b"\0" * 16)
    (state, problems) = DP.frame_state(elevation, str(tmp_path / "o"),
                                       lat, lon, "ZZZZ", expects_inset=False)
    assert state["base_raster"] == base
    assert state["base_raster_present"]
    assert state["base_raster_fallback"] == code
    assert not any("NO base raster" in p for p in problems)


def test_the_configured_hgt_wins_over_a_fallback(tmp_path):
    (lat, lon) = (63, -23)
    elevation = str(tmp_path / "e")
    block = _block(elevation, lat, lon)
    (_code, name) = _fallback_name(lat, lon)
    for leaf in ("N63W023.hgt", name):
        with open(os.path.join(block, leaf), "wb") as fh:
            fh.write(b"\0" * 16)
    (state, _problems) = DP.frame_state(elevation, str(tmp_path / "o"),
                                        lat, lon, "ZZZZ", expects_inset=False)
    assert state["base_raster"].endswith("N63W023.hgt")
    assert "base_raster_fallback" not in state


def test_no_base_at_all_is_cold_and_names_the_base_not_the_inset(tmp_path):
    import O4_Tile_Failures as FAIL

    (state, problems) = DP.frame_state(str(tmp_path / "e"),
                                       str(tmp_path / "o"), 63, -23, "ZZZZ",
                                       expects_inset=False)
    assert any("NO base raster" in p for p in problems)
    code = DP.cold_frame_code(state)
    assert code == DP.BASE_MISSING_CODE
    assert "detailed elevation" not in FAIL.CATALOGUE[code].why
