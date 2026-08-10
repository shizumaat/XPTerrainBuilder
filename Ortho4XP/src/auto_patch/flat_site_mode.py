"""FLAT-SITE mode (phase 2) — the DEM-prep SUBSTITUTION DECISION.

Spec: ``docs/specs/flat-site-mode-spec.md`` (2026-08-09, FROZEN).  Phase 1
(``auto_patch/flat_site.py``) is the report-only detector; this module is
the half of phase 2 that DECIDES, per airport, whether DEM prep should
substitute a synthetic constant surface, and at what elevation and over
what footprint.  It writes NO raster: the blend itself lives beside the
feathering machinery it reuses
(``O4_Airport_Elevation_Insets.overlay_flat_site_insets``), so there is
exactly ONE inset-blend implementation in the tree.

THE ONE DESIGN IDEA (spec §1).  FLAT-SITE mode is a **DEM SOURCE
SUBSTITUTION, not a new solve path.**  When the detector returns
``flat_candidate`` — and only then — DEM prep manufactures a synthetic
CONSTANT inset at ``Z0`` (the CIFP threshold consensus) over the
detector's own ``(pavement ∪ boundary) ⊕ margin`` extent and feathers it
into the base raster with the code that already does exactly that at
every inset airport.  Everything downstream is blind to it and runs
against a truthful flat input.

WHAT THIS MODULE MAY AND MAY NOT TOUCH.  It CONSUMES the detector's
interface — the verdict string, ``z0_m`` and ``extent_from_apt`` — and
never its classification internals or constants (a sibling lane owns
those).  It reads only the airport's OWN inputs (CIFP thresholds, the
apt.dat record the pipeline itself picks) so the extent measured here and
the extent the pipeline's report-only detector measures are the SAME
footprint over the SAME population.

ORDERING (spec §2.1).  The classification runs on the REAL surface: the
caller invokes this AFTER the airport smoothing and the cached-inset bake
and BEFORE anything consumes the raster, so S2 reads the honest DEM and
the substitution lands on top of it.  It runs on EVERY build — warm inset
cache or cold, insets or none — because it hangs off DEM ASSEMBLY and not
off any feature that may have nothing to do.

NO SHARED-CORPUS WRITE (spec §3.3).  The synthetic surface is derived
arithmetic, never data: it exists as an in-memory raster for the length
of one build and is never cached into ``Elevation_data`` or the inset
cache.  A cached synthetic raster would poison the real-DEM path and the
refresh ledger's meaning.
"""
from __future__ import annotations

import math
import os

import O4_UI_Utils as UI

from . import config as _config

__all__ = [
    "flat_site_mode_enabled",
    "set_build_xplane_root",
    "build_xplane_root",
    "flat_site_substitutions",
    "substituting_verdicts",
    "tile_icao_candidates",
    "extent_bounds_tile_degrees",
]

#: Local-metre projection constant — ``layout.R_EARTH``'s value, kept
#: here (as the detector keeps it) so this module stays importable
#: without the layout package.
_R_EARTH = 6378137.0

#: The detector's OWNER-DECLARATION verdict (detector spec v3).  Named
#: by its wire string as well as by the detector's constant: this module
#: must not depend on the sibling lane's landing order, and the string —
#: not the constant — is what a sidecar record actually carries.
VERDICT_FLAT_DECLARED = "flat_declared"


def flat_site_mode_enabled() -> bool:
    """The gate (spec §2.2).  ``O4_FLAT_SITE_MODE=0`` kills the mode."""
    return bool(getattr(_config, "FLAT_SITE_MODE", False))


def substituting_verdicts() -> frozenset:
    """The detector verdicts this mode substitutes on (spec §1).

    ``flat_candidate`` (measured) and ``flat_declared`` (the owner's
    declaration, detector spec v3) are EQUIVALENT here: same
    substitution, same Z0, which in both cases is read from the
    record's ``z0_m`` and never recomputed.  Every other verdict —
    ``not_flat``, ``lidar_credible``, ``no_data``, and any string a
    future detector adds — takes the normal path untouched.  That is
    an ALLOW-LIST on purpose: an unknown verdict must degrade to the
    real DEM, never to a substitution nobody specified.
    """
    from . import flat_site as _flat_site

    return frozenset((
        _flat_site.VERDICT_FLAT_CANDIDATE,
        getattr(_flat_site, "VERDICT_FLAT_DECLARED", VERDICT_FLAT_DECLARED),
    ))


# ──────────────────────────────────────────────────────────────────────
# Which airports DEM prep considers
# ──────────────────────────────────────────────────────────────────────
def tile_icao_candidates(dico_airports) -> list:
    """The 4-letter ICAO codes on this tile, sorted.

    ``dico_airports`` is the engine's own per-tile airport dictionary —
    the SAME population the airport smoothing and the real inset fetch
    loop over (``O4_Airport_Elevation_Insets._airport_bounding_boxes``),
    so flat-site mode never considers an airport the inset machinery
    would not.  Non-string keys are unnamed strips (``key_type``
    ``repr_node``) and IATA / local_ref keys cannot name an apt.dat
    block; both are skipped.
    """
    out = set()
    for key in (dico_airports or {}):
        if not isinstance(key, str):
            continue
        icao = key.strip().upper()
        if len(icao) == 4 and icao.isalpha():
            out.add(icao)
    return sorted(out)


def _dico_airports_from_cache(tile):
    """The tile's airport dictionary rebuilt from the CACHED OSM layer.

    The fallback for callers that hold no dictionary (the step-2 mesh
    raster-refresh path).  Network-free by construction: it runs only
    when the tile's ``airports`` OSM cache is already on disk, exactly
    as ``auto_patch.elevation._load_airport_dem`` does.  Returns ``{}``
    when the cache is absent.
    """
    import O4_File_Names as _FNAMES
    import O4_OSM_Utils as _OSM
    import O4_Vector_Map as _VMAP

    tile_lat = int(math.floor(tile.lat))
    tile_lon = int(math.floor(tile.lon))
    cache = _FNAMES.osm_cached(tile_lat, tile_lon, "airports")
    if not os.path.isfile(cache):
        return {}
    layer = _OSM.OSM_layer()
    _OSM.OSM_queries_to_OSM_layer(
        _VMAP.AIRPORTS_QUERIES, layer, tile_lat, tile_lon, ["all"],
        cached_suffix="airports")
    return _VMAP.build_airports_dico(tile, layer)


#: THE BUILD'S OWN X-PLANE ROOT, set once by
#: ``pipeline.build_airport_pavement`` before anything can compose a DEM.
#:
#: WHY IT IS BUILD-SCOPED AND NOT A PARAMETER (measured 2026-08-09, the
#: OTHH acceptance build that substituted NOTHING).  DEM prep is entered
#: from SEVERAL call sites — ``elevation._compute_elevations`` reaches
#: ``_load_airport_dem(tile_centre)`` BEFORE the per-surface solver does,
#: and ``finalize`` / ``verification`` have their own calls — and
#: ``elevation._DEM_CACHE`` memoises the composed tile DEM per process.
#: So whichever caller composes FIRST decides the surface for the whole
#: build, and a root threaded through one call site only is a root the
#: first caller does not have: the classification bailed with "no
#: X-Plane root resolved", the cache froze the real surface, and every
#: later call — including the one that DID carry the root — got the
#: memoised, unsubstituted DEM back.  A build-scoped value cannot be
#: raced by call order.
_BUILD_XPLANE_ROOT: str | None = None


def set_build_xplane_root(xplane_root: str | None) -> None:
    """Record the install this build reads CIFP and apt.dat under."""
    global _BUILD_XPLANE_ROOT
    _BUILD_XPLANE_ROOT = str(xplane_root) if xplane_root else None


def build_xplane_root() -> str | None:
    """The root :func:`set_build_xplane_root` recorded, if any."""
    return _BUILD_XPLANE_ROOT


def _resolve_xplane_root() -> str | None:
    """The X-Plane root DEM prep should read CIFP and apt.dat under.

    The BUILD's own root first (see :data:`_BUILD_XPLANE_ROOT` — a
    dev/lane config ships both CIFP keys empty, so the config chain
    alone silently disables the whole mode outside production), then the
    same resolution ``O4_Vector_Map.run_auto_patch_generation`` uses for
    the auto-patch pass: the configured CIFP directory, then the Custom
    Scenery directory's parent — so DEM prep and the patch generator
    read one install.
    """
    if _BUILD_XPLANE_ROOT:
        return _BUILD_XPLANE_ROOT
    try:
        import O4_Config_Utils as _CFG
    except Exception:                                # pragma: no cover
        return None
    cifp_path = getattr(_CFG, "cifp_data_path", "") or ""
    if cifp_path:
        from .cifp_reader import xplane_root_from_cifp_path

        root = xplane_root_from_cifp_path(cifp_path)
        if root:
            return root
    custom_scenery = getattr(_CFG, "custom_scenery_dir", "") or ""
    if custom_scenery:
        root = os.path.dirname(os.path.normpath(custom_scenery))
        if os.path.isdir(root):
            return root
    return None


# ──────────────────────────────────────────────────────────────────────
# The extent, in the frame the inset bake speaks
# ──────────────────────────────────────────────────────────────────────
def extent_bounds_tile_degrees(extent_m, anchor, tile_lat: int,
                               tile_lon: int):
    """The extent's bounding box as ``(x0, y0, x1, y1)`` TILE-RELATIVE degrees.

    The inverse of the projection ``layout._projection(anchor)`` applies,
    expressed in the frame ``O4_DEM_Utils.DEM``'s ``x0..x1`` / ``y0..y1``
    use — degrees measured from the tile's SW corner.  That is the frame
    the inset bake's window arithmetic reads, so the synthetic inset can
    be handed to it exactly as a fetched GeoTIFF is.

    The BOUNDING BOX, not the polygon, is deliberate (spec §2, §2.4): a
    fetched inset is a rectangle and the bake feathers from its
    RECTANGULAR data edge.  Handing the machinery a polygon-shaped
    footprint would need a distance transform it does not have — new
    machinery the spec forbids — and would leave a cliff at the polygon
    edge where the rectangular ramp reads full weight.  The detector's
    extent already carries ``FLAT_SITE_MARGIN_M`` of margin, and a real
    airport inset is fetched over the boundary bbox plus
    ``airport_elevation_inset_margin_m`` (2 km by default), so this
    footprint is the tighter of the two.

    Returns ``None`` when the extent is empty.
    """
    if extent_m is None or extent_m.is_empty:
        return None
    xmin, ymin, xmax, ymax = extent_m.bounds
    lat0, lon0 = float(anchor[0]), float(anchor[1])
    cos0 = math.cos(math.radians(lat0))
    if abs(cos0) < 1e-9:                             # pragma: no cover
        return None

    def _to_ll(x_m, y_m):
        return (lat0 + math.degrees(y_m / _R_EARTH),
                lon0 + math.degrees(x_m / (_R_EARTH * cos0)))

    lat_lo, lon_lo = _to_ll(xmin, ymin)
    lat_hi, lon_hi = _to_ll(xmax, ymax)
    return (lon_lo - tile_lon, lat_lo - tile_lat,
            lon_hi - tile_lon, lat_hi - tile_lat)


# ──────────────────────────────────────────────────────────────────────
# The decision
# ──────────────────────────────────────────────────────────────────────
def flat_site_substitutions(tile, dico_airports=None,
                            xplane_root: str | None = None) -> list:
    """Every flat-site substitution this tile's DEM should carry.

    One entry per airport the detector calls ``flat_candidate`` or
    ``flat_declared`` (:func:`substituting_verdicts`)::

        {"icao", "z0_m", "extent_deg": (x0, y0, x1, y1),
         "extent_area_km2", "record": <the detector's evidence record>}

    ``extent_deg`` is tile-relative degrees (see
    :func:`extent_bounds_tile_degrees`).  Returns ``[]`` — and reads
    nothing beyond the gate — when the mode is off, so the gate-off arm
    costs one boolean.

    S1 SHORT-CIRCUIT: an airport whose CIFP threshold consensus fails is
    skipped before its apt.dat is opened.  Both substituting verdicts
    require S1 (``flat_candidate`` is S1 ∧ S2; an owner declaration is
    an override of S2, not of the instrument truth S1 supplies), so this
    cannot change any verdict; it keeps DEM prep from loading
    twenty-five apt.dat blocks on a busy tile to classify airports that
    cannot qualify.
    """
    if not flat_site_mode_enabled():
        return []
    dem = getattr(tile, "dem", None)
    if dem is None or getattr(dem, "alt_dem", None) is None:
        return []

    from . import apt_dat_reader as _APR
    from . import flat_site as _flat_site
    from . import provenance as _provenance
    from .layout import _airport_anchor, _projection
    from .osm_load import _pick_best_apt_dat_against_osm

    if xplane_root is None:
        # The install THIS build was handed (recorded on the Tile by
        # ``elevation._load_airport_dem``) wins over the engine config:
        # a dev/lane config ships both CIFP keys empty.
        xplane_root = (getattr(tile, "auto_patch_xplane_root", None)
                       or _resolve_xplane_root())
    if not xplane_root:
        UI.vprint(1, "   [flat-site] mode ON but no X-Plane root resolved "
                     "(no cifp_data_path, no custom_scenery_dir) — no "
                     "airport classified, DEM prep unchanged.")
        return []

    if not dico_airports:
        dico_airports = _dico_airports_from_cache(tile)
    icaos = tile_icao_candidates(dico_airports)
    if not icaos:
        return []

    tile_lat = int(math.floor(tile.lat))
    tile_lon = int(math.floor(tile.lon))
    accepted = substituting_verdicts()
    out = []
    for icao in icaos:
        elevations = _flat_site.cifp_threshold_elevations(xplane_root, icao)
        if _flat_site.threshold_consensus(elevations).get("pass") is not True:
            continue
        apt_path = _pick_best_apt_dat_against_osm(xplane_root, icao)
        if apt_path is None:
            continue
        apt = _APR.load_airport(apt_path, icao)
        if apt is None:
            continue
        anchor = _airport_anchor(apt)
        extent_m = _flat_site.extent_from_apt(apt, _projection(anchor))
        record = _flat_site.classify_site(
            icao=icao, cifp_elevations_m=elevations, dem=dem,
            tile_lat=tile_lat, tile_lon=tile_lon, anchor=anchor,
            extent_m=extent_m,
            dem_meta=_provenance.dem_provenance_from_dem(dem, icao=icao))
        UI.vprint(1, _flat_site.format_log_line(record))
        if record.get("verdict") not in accepted:
            continue
        bounds = extent_bounds_tile_degrees(extent_m, anchor,
                                            tile_lat, tile_lon)
        # Z0 comes from the RECORD, never recomputed here: with an owner
        # declaration the detector may put a declared elevation there,
        # and two derivations of one number is how this repo gets two
        # instruments over one population.
        if bounds is None or record.get("z0_m") is None:
            continue
        out.append({
            "icao": icao,
            "verdict": record.get("verdict"),
            "z0_m": float(record["z0_m"]),
            "extent_deg": bounds,
            "extent_area_km2": round(extent_m.area / 1e6, 4),
            "record": record,
        })
    return out
