"""The ``vertical_unit`` key: heights delivered in feet become metres.

One table of metres-per-unit and one resolver the raster warp and the
LAS gridder share, so a provider's declared unit, the unit its raster
states, and the factor applied are decided in one place and stamped on
the output.
"""

from elevation_access.base import ProviderUnavailable
from elevation_access.gdal_support import gdal, osr

__all__ = [
    "VERTICAL_UNIT_FACTOR_RELATIVE_TOLERANCE",
    "VERTICAL_UNIT_GRIDDED_IN_METRES",
    "VERTICAL_UNIT_STAMP_APPLIED",
    "VERTICAL_UNIT_STAMP_DECLARED",
    "VERTICAL_UNIT_STAMP_SOURCE",
    "VERTICAL_UNIT_TO_M",
    "_raster_vertical_unit",
    "resolve_warp_vertical_unit",
]


# ---------------------------------------------------------------------
# THE VERTICAL-UNIT KEY (spec us-holder-providers §2, RULINGS 2026-09-30bm)
# ---------------------------------------------------------------------
#: Metres per unit of a provider's ``vertical_unit`` key -- the ONE table
#: the raster warp (:func:`warp_vsicurl_sources_to_geotiff`) and the LAS
#: gridder (:func:`grid_las_tile`) share.  ``ftUS`` is the US survey foot,
#: 1200/3937 m by definition (exact, not the rounded 0.3048006).
VERTICAL_UNIT_TO_M = {"ftUS": 1200.0 / 3937.0, "ft": 0.3048, "m": 1.0}


#: What the LAS site hands the shared warp: its per-tile DTMs are already
#: metres (the gridder converted the points by ``vertical_unit``).
VERTICAL_UNIT_GRIDDED_IN_METRES = "m"


#: A source CRS's vertical unit matches a table unit when the metres-per-
#: unit factors agree to this relative tolerance (GDAL reports the US
#: survey foot as 0.304800609601219, the table holds 1200/3937).
VERTICAL_UNIT_FACTOR_RELATIVE_TOLERANCE = 1e-9


#: GDAL metadata items the shared warp stamps on a raster whose provider
#: declared ``vertical_unit``: the unit the .elv declared, where the unit
#: was read from (``elv`` | ``elv=crs``) and the unit the cells now hold.
#: A raster from a provider WITHOUT the key carries none of them (the warp
#: is a strict no-op there, byte for byte).
VERTICAL_UNIT_STAMP_DECLARED = "O4_VERTICAL_UNIT_DECLARED"


VERTICAL_UNIT_STAMP_SOURCE = "O4_VERTICAL_UNIT_SOURCE"


VERTICAL_UNIT_STAMP_APPLIED = "O4_VERTICAL_UNIT_APPLIED"


def _raster_vertical_unit(definition):
    """The ``vertical_unit`` a RASTER strategy hands the shared warp.

    ``None`` when the .elv carries no key -- the warp is then a strict
    no-op (no source CRS read, no scale, no stamp), which is what keeps
    every provider written before the key byte-identical.  An unknown
    unit is a provider that cannot be asked this run:
    :class:`ProviderUnavailable`, never a guess."""
    value = definition.get("vertical_unit")
    if value is None or not str(value).strip():
        return None
    value = str(value).strip()
    if value not in VERTICAL_UNIT_TO_M:
        raise ProviderUnavailable(
            "%s: .elv vertical_unit=%s is not one of %s"
            % (definition.get("code"), value,
               "|".join(sorted(VERTICAL_UNIT_TO_M))))
    return value


def _vertical_unit_name_for_factor(factor):
    """The table unit whose metres-per-unit is ``factor``, or ``None``."""
    for (name, metres) in VERTICAL_UNIT_TO_M.items():
        if abs(factor - metres) <= (
                VERTICAL_UNIT_FACTOR_RELATIVE_TOLERANCE * metres):
            return name
    return None


def _declared_vertical_unit_factor(srs_text):
    """Metres per unit of the VERTICAL axis a CRS declares, or ``None``
    when it declares none (a horizontal-only CRS, or nothing readable).
    Only a compound (or purely vertical) CRS declares one."""
    if not srs_text:
        return None
    try:
        srs = osr.SpatialReference()
        if srs.SetFromUserInput(str(srs_text)) != 0:
            return None
        if not (srs.IsCompound() or srs.IsVertical()):
            return None
        factor = float(srs.GetTargetLinearUnits("VERT_CS"))
    except Exception:
        return None
    return factor if factor > 0 else None


def _warp_input_srs_text(source):
    """The CRS a warp input carries (WKT), or ``None`` when unreadable.
    An open :class:`gdal.Dataset` is asked directly; a path is opened
    (header only) under the caller's configuration options."""
    try:
        dataset = source if not isinstance(source, str) else gdal.Open(source)
    except Exception:
        return None
    if dataset is None:
        return None
    try:
        return dataset.GetProjection() or None
    except Exception:
        return None


def resolve_warp_vertical_unit(warp_inputs, vertical_unit, source_srs=None,
                               provider_code=None):
    """``(factor, vertical_unit_source)`` for one warp, or raise.

    The ``.elv`` key is checked against every input's own CRS BEFORE any
    cell is scaled (spec §2 refusal): a compound CRS whose vertical unit
    contradicts the key raises :class:`ProviderUnavailable` (``unavailable``
    record, the ladder climbs -- never a silent scale, never a durable
    no-coverage); inputs declaring DIFFERENT vertical units refuse exactly
    as :func:`_refuse_mixed_vertical_datums` does for datums.  Inputs with
    no vertical CRS trust the ``.elv``.  An explicit ``source_srs``
    overrides every input's CRS for the warp, so it is the one checked."""
    expected = VERTICAL_UNIT_TO_M[vertical_unit]
    label = provider_code or "elevation provider"
    if source_srs:
        declared = [("source_srs " + str(source_srs),
                     _declared_vertical_unit_factor(source_srs))]
    else:
        declared = [(source if isinstance(source, str) else "an open dataset",
                     _declared_vertical_unit_factor(
                         _warp_input_srs_text(source)))
                    for source in warp_inputs]
    declared = [(name, factor) for (name, factor) in declared
                if factor is not None]
    units = sorted({_vertical_unit_name_for_factor(factor) or repr(factor)
                    for (_name, factor) in declared})
    if len(units) > 1:
        raise ProviderUnavailable(
            "%s: the mosaic's sources declare different vertical units "
            "(%s) - refused, never mixed" % (label, ", ".join(units)))
    for (name, factor) in declared:
        if abs(factor - expected) > (
                VERTICAL_UNIT_FACTOR_RELATIVE_TOLERANCE * expected):
            declared_name = _vertical_unit_name_for_factor(factor)
            raise ProviderUnavailable(
                "%s: .elv vertical_unit=%s but %s declares %s"
                % (label, vertical_unit, name,
                   {"m": "metre", "ft": "foot", "ftUS": "US survey foot"}
                   .get(declared_name, "%r m per unit" % factor)))
    return (expected, "elv=crs" if declared else "elv")
