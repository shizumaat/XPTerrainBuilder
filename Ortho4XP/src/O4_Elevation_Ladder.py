"""THE ONE ELEVATION PROVIDER LADDER (owner RULINGS 2026-11-27e).

Owner 2026-11-27T15:57Z: "Everything should use the same list and
fallbacks ... so even if I chose to build the whole tile at 1m, it
shouldn't be different sources at airports."  Every consumer that picks
an elevation provider -- the airport insets, the approach rings, the
coastline band and the tile-wide numeric ``elevation_level`` -- walks ONE
ranked list: the airport inset list
(:func:`O4_Airport_Elevation_Insets.select_provider_definitions` over
``airport_elevation_providers``: every enabled inset-role definition by
descending priority -- regional lidar, then national, then the global
fallbacks -- or the user's explicit order).  A consumer chooses only its
target resolution, and asks only what its fetch can be asked for:

* a box (an airport, a 0.1 degree cell) takes every provider whose
  coverage -- its declared box and, when known, its real footprint
  (#1466) -- reaches the box, and whose country rule admits it;
* a SURROUND cell (rings, coastline band: 0.1 degree, ~100 km2) takes a
  provider whose reader is windowed (:func:`reads_windows`: what it
  fetches follows the asked resolution), or one that opted into a ring
  class (``approach_ring_class``, RULINGS 2026-10-02c: the global
  fallbacks) for cells of that class or coarser.  A tile-download reader
  (a national campaign's native tiles, a point cloud, an AOI POST) is
  asked only for an airport box, never for a cell;
* the WHOLE TILE takes only providers whose access strategy reads windows
  (``supports_wide_area``) and that do not opt out of it -- fetching a
  whole tile through a tile-download strategy would pull an entire
  national campaign at native resolution.

Which rung of a chosen provider serves a class stays
:func:`O4_Elevation_Level.surround_rung_for_class` (RULINGS 2026-10-02f).
"""

from __future__ import annotations


def ranked_providers(providers_config="auto"):
    """THE list: the airport inset ranking, every consumer's own."""
    import O4_Airport_Elevation_Insets as INSETS

    return INSETS.select_provider_definitions(providers_config or "auto")


def providers_for_box(box, providers_config="auto", country=None):
    """The ranked providers whose coverage reaches ``box`` (west, south,
    east, north degrees) and that may serve ``country`` (ISO alpha-3, or
    ``None`` for a box with no country: coverage alone decides)."""
    from elevation_access import definitions as ea_definitions
    from elevation_access import footprints as ea_footprints

    return [
        definition
        for definition in ranked_providers(providers_config)
        if ea_definitions.provider_serves_country(definition, country)
        and ea_footprints.covers_box(definition, box)
    ]


def providers_for_cell(box, class_m, providers_config="auto"):
    """The ranked providers that may serve a surround cell of ``class_m``
    metres over ``box`` (approach rings, coastline band)."""
    return [
        definition
        for definition in providers_for_box(box, providers_config)
        if _opt_in_admits(definition, class_m)
    ]


def providers_for_tile(lat, lon, providers_config="auto"):
    """The ranked providers that may serve a whole-tile overlay."""
    return [
        definition
        for definition in providers_for_box(
            (lon, lat, lon + 1, lat + 1), providers_config
        )
        if reads_windows(definition)
    ]


def reads_windows(definition):
    """True when a whole tile may be fetched through ``definition``: its
    strategy class reads windows and the definition does not opt out (the
    USGS Original Product Resolution tiles, #153, are ~1 km GeoTIFFs a
    whole-tile overlay would read in full by the thousand)."""
    from elevation_access import registry as ea_registry

    strategy_factory = ea_registry.ACCESS_STRATEGIES.get(
        definition.get("access_strategy")
    )
    if strategy_factory is None or not getattr(
        strategy_factory, "supports_wide_area", False
    ):
        return False
    return str(definition.get("supports_wide_area", "")).strip().lower() \
        not in ("false", "0", "no")


def _opt_in_admits(definition, class_m):
    """May a cell of ``class_m`` be fetched through ``definition``?  A
    windowed reader always (its cost follows the class, not the product);
    any other only through a ring opt-in (``approach_ring_class``), and
    only for that ring's class or coarser (RULINGS 2026-10-02c)."""
    import O4_Elevation_Level as ELEVATION_LEVEL

    if reads_windows(definition):
        return True
    opted = ELEVATION_LEVEL.approach_ring_opt_in_rung(definition)
    if opted is None:
        return False
    for rung in ELEVATION_LEVEL.approach_rung_ladder():
        if rung.label == opted:
            return float(class_m) >= rung.resolution_m
    return False
