"""Elevation access strategies: how each kind of server hands out terrain.

A PROVIDER is data: one ``Providers/Elevation/<CODE>.elv`` file of
``key=value`` lines.  Its ``access_strategy`` key names the code that
knows how to talk to that kind of server.  That code is an ACCESS
STRATEGY, and each one is ONE MODULE in ``strategies/``, named for its
key (``access_strategy=wcs`` is ``strategies/wcs.py``).

Most new providers need no code at all: write the ``.elv`` file and name
a strategy that already exists.

TO ADD A STRATEGY (a server that speaks something new)

1. Create ``strategies/<key>.py`` holding one class decorated with
   ``@register_access_strategy("<key>")``.  Give it the two methods of
   :class:`base.InsetAccessStrategy` (``discover`` and ``fetch``), or of
   :class:`base.BaseTileAccessStrategy` (``covers`` and ``ensure_tile``)
   for a whole-tile source.  Helpers only this strategy uses go in the
   same file.
2. Add ``<key>`` to the import list in ``strategies/__init__.py``.  That
   line is what makes the strategy exist -- in a source run and in the
   frozen app alike.
3. Add ``<key>`` and the class name to ``EXPECTED_STRATEGIES`` in
   ``registry.py`` -- the pinned set the frozen engine counts itself
   against (``--import-selfcheck``) and the twin reads.

Nothing in the pipeline (``O4_Airport_Elevation_Insets``) changes: it
looks the class up in :data:`registry.ACCESS_STRATEGIES` by the key the
definition names.

WHAT A STRATEGY MAY USE (the shared modules beside this file)

``base``            the two interfaces; ``TransientFetchError`` ("ask
                    again next run") and ``ProviderUnavailable`` ("this
                    run could not ask")
``registry``        ``ACCESS_STRATEGIES`` and the decorator
``definitions``     reading a definition: roles, numbers, coverage boxes
``discovery``       JSON listings and HTTP answer classes
``failures``        telling transient / mis-configured / capped apart
``fetch_slots``     per-server politeness cap
``downloads``       whole-file downloads into the cache
``warp``            sources -> one GeoTIFF; "does it hold data"
``vertical_units``  feet to metres
``capabilities``    can this run decode LERC / LAS / LAZ
``gdal_support``    ``gdal``, ``ogr``, ``osr``, ``has_gdal``
``stac_assets``     picking the terrain asset of a STAC item
``las_tiles``       what the point-cloud strategies share
``base_tiles``      whole-tile cache validity and coverage

A strategy module imports from those and never from the pipeline.  It
does not import another strategy either, with three standing exceptions:
``os_grid_bucket`` subclasses ``geojson_tile_index``;
``authenticated_token_search`` parses its answer with ``stac``'s search
parser; ``las_tile_index`` asks ``cwcb_lidar_api`` for the tile list of
an ``index_format=cwcb`` provider.

THE RULE THAT MUST NOT BREAK: a failure that says nothing about
coverage is RAISED, never returned as ``None``.  ``None`` is recorded as
a durable "this provider has nothing here" and is never asked again.
"""

from elevation_access import strategies  # noqa: F401  (registers them all)
from elevation_access.registry import ACCESS_STRATEGIES, register_access_strategy

__all__ = ["ACCESS_STRATEGIES", "register_access_strategy", "strategies"]
