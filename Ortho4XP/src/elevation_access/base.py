"""What an access strategy IS: the two interfaces and the two errors.

An access strategy is the code that knows how ONE kind of server hands
out elevation (a STAC search, a WCS request, a tile index of LAS files).
A provider is DATA -- a ``Providers/Elevation/<CODE>.elv`` file naming
the strategy it speaks in its ``access_strategy`` key.

The pipeline talks to a strategy only through the methods of
:class:`InsetAccessStrategy` (airport insets, bathymetry) or
:class:`BaseTileAccessStrategy` (whole 1x1 degree base tiles), and a
strategy tells the pipeline "ask again later" or "this run cannot ask"
only by raising :class:`TransientFetchError` or
:class:`ProviderUnavailable`.
"""

from typing import Any, Mapping, Optional, Protocol, Tuple, runtime_checkable

__all__ = [
    "BaseTileAccessStrategy",
    "BoundingBox",
    "Definition",
    "InsetAccessStrategy",
    "ProviderUnavailable",
    "TransientFetchError",
]

#: A parsed ``.elv`` provider definition: its ``key=value`` lines.
Definition = Mapping[str, Any]

#: ``(west, south, east, north)`` in WGS84 degrees.
BoundingBox = Tuple[float, float, float, float]


@runtime_checkable
class InsetAccessStrategy(Protocol):
    """A strategy that cuts a raster over a bounding box (airport insets,
    bathymetry, the wide-area overlay).  The registry holds the CLASS; the
    pipeline makes a fresh instance per call (``ACCESS_STRATEGIES[key]()``),
    so a strategy keeps no state between calls.
    """

    def discover(self, definition: Definition,
                 bounding_box_wgs84: BoundingBox) -> Optional[list]:
        """What the provider holds over the box, without downloading it.

        A non-empty list of source records, or ``None`` / empty for "the
        provider answered and has nothing here" (a durable no-coverage).
        A failure that says nothing about coverage is RAISED
        (:class:`TransientFetchError`, :class:`ProviderUnavailable`),
        never returned as ``None``.
        """
        ...

    def fetch(self, definition: Definition, bounding_box_wgs84: BoundingBox,
              target_resolution_m: float,
              destination_path: str) -> Optional[dict]:
        """Write a GeoTIFF of the box to ``destination_path``.

        Returns the provenance dictionary recorded beside the inset, or
        ``None`` for no usable coverage.  Raises like :meth:`discover`.
        """
        ...


@runtime_checkable
class BaseTileAccessStrategy(Protocol):
    """A strategy that supplies a whole 1x1 degree base tile
    (``role=base`` definitions)."""

    def covers(self, definition: Definition, lat: int, lon: int) -> bool:
        """Does this provider publish the tile at all?  No network."""
        ...

    def ensure_tile(self, definition: Definition, lat: int, lon: int,
                    verbose: bool = True) -> int:
        """Make the tile present in the cache.  ``1`` when it is there
        afterwards, ``0`` when it could not be obtained."""
        ...


class TransientFetchError(Exception):
    """A network-shaped fetch failure that may succeed on a later run.

    Raised (instead of a no-coverage answer) when a remote read dies in a
    way that says nothing about whether the provider has data: curl
    timeouts, connection failures, 5xx server responses, 429 rate
    limits.  The module-wide
    convention every :func:`fetch_inset` caller honours: a RAISED failure
    is never recorded as a durable no-coverage negative, while a returned
    ``None`` is.
    """


class ProviderUnavailable(Exception):
    """THIS RUN could not ask the provider -- a missing CAPABILITY.

    Raised (instead of a ``None`` no-coverage answer) when the engine
    itself is what is missing: no LERC decoder, no GDAL, a download that
    failed for anything but a 404.  It says nothing about coverage, so
    the caller records ``unavailable:<reason>`` -- a status class of its
    own that the reader never reads as no-coverage and that no later run
    short-circuits on.

    Sibling of :class:`TransientFetchError` (the NETWORK had a bad
    moment) and deliberately distinct from it: a transient failure
    leaves no record at all, while this one leaves a legible "the tier
    here is degraded because the engine could not decode it" in the
    index.  Owner RULINGS 2026-09-13b.
    """

    def __init__(self, reason):
        super().__init__(str(reason))
        self.reason = str(reason)
