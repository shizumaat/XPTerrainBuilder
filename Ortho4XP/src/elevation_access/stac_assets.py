"""Choosing the terrain raster out of a STAC item (the three STAC strategies).
"""

__all__ = [
    "_select_stac_dtm_assets",
    "_stac_asset_href_to_vsicurl",
]


def _select_stac_dtm_assets(items, prefer_asset_keys, target_resolution_m=None):
    """Pick one Cloud-Optimized GeoTIFF DTM asset href from each STAC item.

    STAC items expose named assets; elevation collections publish a Digital
    Terrain Model (bare earth) and often a Digital Surface Model (canopy /
    buildings) too.  We prefer the DTM: an asset whose key matches one of
    ``prefer_asset_keys`` (in order) wins; otherwise the first asset whose
    key or roles suggest a DTM; otherwise a GeoTIFF-typed asset picked by
    resolution: the COARSEST still at-or-finer-than ``target_resolution_m``
    when given (a 3 m inset needs swisstopo's 2 m tiles, not ~36x the
    bytes of its 0.5 m ones — observed 2026-07-23: ~100 MB per airport of
    half-metre data resampled straight down to 3 m), the finest otherwise.
    Returns a list of ``(href, native_resolution_m_or_None)`` for the
    chosen assets, skipping items with no usable asset.
    """
    chosen = []
    for item in items:
        assets = item.get("assets") or {}
        properties = item.get("properties") or {}
        href = None
        asset_resolution = None
        # 1. Explicit preference order (e.g. "dtm", "dtm-1m").  A
        #    preference token matches an exact asset key first, else any
        #    key CONTAINING it -- catalogs like Finland's Paituli mirror
        #    key their assets "<dataset>_at_paituli_tiff", so exact keys
        #    cannot be written into a definition file.
        for preference in prefer_asset_keys:
            matched = None
            if preference in assets:
                matched = assets[preference]
            else:
                for (key, asset) in assets.items():
                    if preference in key:
                        matched = asset
                        break
            if matched is not None and matched.get("href"):
                href = matched["href"]
                asset_resolution = _stac_asset_resolution(matched)
                break
        # 2. Any asset that looks like a DTM by key or declared role.
        if href is None:
            for key, asset in assets.items():
                roles = [str(role).lower() for role in asset.get("roles", [])]
                if (
                    "dtm" in key.lower()
                    or "data" in roles
                    and "dtm" in " ".join(roles)
                ) and asset.get("href"):
                    href = asset["href"]
                    asset_resolution = _stac_asset_resolution(asset)
                    break
        # 3. Fall back to a GeoTIFF-typed asset picked by resolution:
        #    some catalogs (swisstopo's, for one) publish several
        #    resolutions of the same tile as filename-keyed assets
        #    carrying their own eo:gsd, so "first GeoTIFF" would be
        #    dictionary-order luck.  Among the assets that OVERSAMPLE
        #    the target the coarsest is the cheapest sufficient one;
        #    only when none is fine enough (or no target/gsd is known)
        #    does finest-wins apply.
        if href is None:
            geotiff_assets = []
            for asset in assets.values():
                media_type = str(asset.get("type", "")).lower()
                if ("tiff" in media_type or "geotiff" in media_type) and asset.get(
                    "href"
                ):
                    geotiff_assets.append(asset)
            sufficient = []
            if target_resolution_m:
                sufficient = [
                    asset for asset in geotiff_assets
                    if _stac_asset_resolution(asset) is not None
                    and _stac_asset_resolution(asset) <= target_resolution_m
                ]
            if sufficient:
                cheapest = max(sufficient, key=_stac_asset_resolution)
                href = cheapest["href"]
                asset_resolution = _stac_asset_resolution(cheapest)
            elif geotiff_assets:
                finest = min(
                    geotiff_assets,
                    key=lambda asset: (
                        _stac_asset_resolution(asset)
                        if _stac_asset_resolution(asset) is not None
                        else float("inf")
                    ),
                )
                href = finest["href"]
                asset_resolution = _stac_asset_resolution(finest)
        if href is None:
            continue
        resolution = (
            asset_resolution
            or properties.get("gsd")
            or properties.get("resolution")
            or None
        )
        chosen.append((href, resolution))
    return chosen


def _stac_asset_resolution(asset):
    """The asset-level ground sample distance in metres, if declared."""
    for key in ("eo:gsd", "gsd", "resolution"):
        value = asset.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _stac_asset_href_to_vsicurl(href):
    """Turn a STAC asset href into a GDAL virtual path for a window read.

    ``https://`` / ``http://`` hrefs become ``/vsicurl/<url>``; an ``s3://``
    href becomes ``/vsis3/<bucket/key>``; an already-virtual path is left
    untouched.  Only the requested window is read regardless.
    """
    if href.startswith("/vsi"):
        return href
    if href.startswith("s3://"):
        return "/vsis3/" + href[len("s3://") :]
    return "/vsicurl/" + href
