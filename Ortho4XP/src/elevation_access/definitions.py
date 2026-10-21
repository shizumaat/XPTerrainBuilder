"""Reading a provider definition: roles, numbers, coverage boxes.

The vocabulary of a parsed ``.elv`` definition that strategies and the
pipeline both read: the ``role`` values, tolerant number / box parsing,
"does this provider cover this box", box reprojection, and the image
export format rule two strategies and the definition loader share.
"""

import json

from elevation_access.gdal_support import osr

__all__ = [
    "EXPORT_IMAGE_FORMATS",
    "GLOBAL_COUNTRY",
    "ROLE_AIRPORT_INSET",
    "ROLE_BASE",
    "ROLE_BATHYMETRY",
    "_WEB_MERCATOR_HALF_CIRCUMFERENCE",
    "_bounding_boxes_intersect",
    "_coverage_bbox_intersects",
    "_geojson_geometry_bounding_box",
    "_parse_boolean",
    "_parse_bounding_box",
    "_parse_bounding_boxes",
    "_parse_float",
    "coverage_boxes",
    "export_image_definition_refusal",
    "provider_countries",
    "provider_serves_country",
    "providers_share_country",
    "transform_bounding_box_to_epsg",
]


# Detail tier (spec section 3.6).  A definition without an explicit ``role``
# is an airport inset; ``role=base`` definitions describe tile-wide sources
# (the Phase A2 legacy refactor) and are ignored by the inset path here.
ROLE_AIRPORT_INSET = "airport_inset"


ROLE_BASE = "base"


# Coastal bathymetry (spec section 2.1).  Bathymetry providers deliver
# measured seabed depth on a LOCAL TIDAL vertical datum and are NEVER
# eligible for terrain grading (airport insets, base sources, the
# elevation_level wide-area overlay); :func:`select_bathymetry_definition`
# is their only entry point.  Every terrain-selection path filters this
# role out explicitly.
ROLE_BATHYMETRY = "bathymetry"


def _parse_boolean(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _parse_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_bounding_box(value):
    """Parse ``W,S,E,N`` into a ``(west, south, east, north)`` tuple."""
    try:
        parts = [float(item) for item in str(value).split(",")]
        if len(parts) == 4:
            return (parts[0], parts[1], parts[2], parts[3])
    except (TypeError, ValueError):
        pass
    return None


def _parse_bounding_boxes(value):
    """Parse ``W,S,E,N;W,S,E,N;...`` into a tuple of boxes.

    Owner RULINGS 2026-09-16c.  A provider whose data lives in DISJOINT
    regions (USGS 3DEP: CONUS, Alaska, Hawaii, PR/USVI, Guam/CNMI,
    American Samoa) could only declare the HULL of them, and a hull over
    the Pacific and the Caribbean reaches every airport between -- every
    one of which then records a ``no-coverage`` that 15ay's once-per-
    version door re-asks forever.  The declaration is now a LIST.

    ``;`` is the separator the reader already uses for a list of records
    (``exclude_tiles``, :func:`_parse_tile_list`), and
    :func:`initialize_elevation_providers_dict` additionally JOINS
    repeated ``coverage_bbox=`` lines with it, so a ``.elv`` file can
    give each box its own line and its own citation comment.

    A malformed box is skipped, not fatal: one bad line must not silently
    widen a provider to "no declared coverage" (which means EVERYWHERE).
    """
    boxes = []
    for chunk in str(value).split(";"):
        if not chunk.strip():
            continue
        box = _parse_bounding_box(chunk)
        if box is not None:
            boxes.append(box)
    return tuple(boxes)


def coverage_boxes(definition):
    """The provider's declared coverage as a tuple of boxes (possibly ())."""
    boxes = definition.get("coverage_bboxes")
    if boxes:
        return tuple(boxes)
    single = definition.get("coverage_bbox")
    if not single:
        return ()
    if not isinstance(single, (list, tuple)):
        # A definition assembled by hand (a test, a tool) may still hold the
        # raw string; parse it the same way the .elv reader does, so a
        # ``;``-separated string is a list there too.
        return _parse_bounding_boxes(single)
    return (tuple(single),)


def _coverage_bbox_intersects(definition, bounding_box_wgs84):
    """Cheap pre-filter: does the provider's optional coverage overlap?

    A provider may declare SEVERAL disjoint boxes (owner 2026-09-16c);
    overlap with ANY of them is coverage, and a provider that declares
    none covers everywhere (unchanged).
    """
    boxes = coverage_boxes(definition)
    if not boxes:
        return True
    (west, south, east, north) = bounding_box_wgs84
    return any(
        not (east < cw or west > ce or north < cs or south > cn)
        for (cw, cs, ce, cn) in boxes
    )


def _bounding_boxes_intersect(box_a, box_b):
    """Do two (west, south, east, north) boxes overlap?"""
    (west_a, south_a, east_a, north_a) = box_a[:4]
    (west_b, south_b, east_b, north_b) = box_b[:4]
    return not (
        east_a < west_b
        or east_b < west_a
        or north_a < south_b
        or north_b < south_a
    )


# THE COUNTRY RULE (owner RULINGS 2026-10-20bc, #1205).  A national or
# regional provider serves ONLY airports inside its own country, whatever
# coverage its catalog or box reports; with no provider of the airport's
# country the inset comes from the highest-resolution GLOBAL source.
# Every ``role=airport_inset`` ``.elv`` declares ``country=``: ISO 3166-1
# alpha-3 codes (the codes apt.dat's ``1302 country`` row leads with),
# comma-separated, or ``GLOBAL``.  A definition without the key (a user's
# own file) is treated as global -- the shipped set is twin-checked.
GLOBAL_COUNTRY = "GLOBAL"


def provider_countries(definition):
    """The provider's countries as a frozenset of ISO alpha-3 codes, or
    ``None`` for a global provider (``country=GLOBAL`` or undeclared)."""
    value = (definition or {}).get("country")
    if value is None:
        return None
    if isinstance(value, (list, tuple, set, frozenset)):
        tokens = [str(token) for token in value]
    else:
        tokens = str(value).split(",")
    codes = frozenset(token.strip().upper() for token in tokens
                      if token.strip())
    if not codes or GLOBAL_COUNTRY in codes:
        return None
    return codes


def provider_serves_country(definition, country):
    """May this provider serve an airport in ``country`` (ISO alpha-3)?

    A global provider serves every airport.  An airport whose country is
    unknown (``None``/``""``: no apt.dat country row) keeps the coverage
    box as its only test, as before the rule."""
    countries = provider_countries(definition)
    if countries is None or not country:
        return True
    return str(country).strip().upper() in countries


def providers_share_country(member, root):
    """May ``member`` join ``root``'s resolution ladder?  A national rung
    joins only a ladder rooted in one of its own countries; a global rung
    joins any ladder.  (A global root therefore takes no national rung:
    the airport's own national providers were ranked above it.)"""
    member_countries = provider_countries(member)
    if member_countries is None:
        return True
    root_countries = provider_countries(root)
    return root_countries is not None and bool(
        member_countries & root_countries)


_WEB_MERCATOR_HALF_CIRCUMFERENCE = 20037508.342789244


#: The two body formats the strategy decodes (``export_format``).
EXPORT_IMAGE_FORMATS = ("tiff", "lerc")


def export_image_definition_refusal(definition):
    """Why a definition cannot be asked at all, or ``None``.

    ``nodata`` is MANDATORY on an exportImage provider (spec §3.4, #155):
    with ``noData=`` empty an ArcGIS ImageServer answers 0.0 with NO
    nodata tag where its mosaic holds nothing -- a false sea level the
    bake cannot tell from data.  The same refusal covers a ``wcs_kvp``
    template that spells an ArcGIS exportImage request with an EMPTY
    ``noData=`` or with a ``{nodata}`` placeholder the definition does not
    fill."""
    strategy = definition.get("access_strategy")
    code = definition.get("code") or "elevation provider"
    nodata = str(definition.get("nodata", "") or "").strip()
    if strategy == "arcgis_export_image":
        if not nodata:
            return ("%s: arcgis_export_image without a nodata key - an "
                    "empty noData= reads 0.0 (false sea level) where the "
                    "service has no data (#155)" % code)
        if _parse_float(nodata, None) is None:
            return "%s: nodata=%s is not a number" % (code, nodata)
        if not str(definition.get("export_url", "") or "").strip():
            return "%s: arcgis_export_image without export_url" % code
        if not str(definition.get("source_epsg", "") or "").strip():
            return "%s: arcgis_export_image without source_epsg" % code
        export_format = str(definition.get("export_format", "tiff")).strip()
        if export_format not in EXPORT_IMAGE_FORMATS:
            return ("%s: export_format=%s is not one of %s"
                    % (code, export_format, "|".join(EXPORT_IMAGE_FORMATS)))
        rule = definition.get("rendering_rule")
        if rule is not None and str(rule).strip():
            try:
                json.loads(str(rule))
            except ValueError as error:
                return ("%s: rendering_rule is not JSON (%s)"
                        % (code, error))
        return None
    if strategy == "wcs_kvp":
        template = str(definition.get("wcs_getcoverage_template", ""))
        if "{nodata}" in template and not nodata:
            return ("%s: wcs_getcoverage_template carries {nodata} but the "
                    "definition has no nodata key (#155)" % code)
        if "exportimage" in template.lower():
            import re

            match = re.search(r"[?&]noData=([^&]*)", template)
            if match is None or not match.group(1).strip():
                return ("%s: an exportImage template with an empty noData= "
                        "reads 0.0 (false sea level) where the service has "
                        "no data - set noData={nodata} and nodata= (#155)"
                        % code)
        return None
    return None


def _geojson_geometry_bounding_box(geometry):
    """The (west, south, east, north) envelope of a GeoJSON geometry."""
    longitudes = []
    latitudes = []

    def _walk(node):
        if (
            isinstance(node, (list, tuple))
            and len(node) >= 2
            and all(isinstance(value, (int, float)) for value in node[:2])
        ):
            longitudes.append(float(node[0]))
            latitudes.append(float(node[1]))
        elif isinstance(node, (list, tuple)):
            for child in node:
                _walk(child)

    _walk((geometry or {}).get("coordinates") or [])
    if not longitudes:
        return None
    return (
        min(longitudes),
        min(latitudes),
        max(longitudes),
        max(latitudes),
    )


def transform_bounding_box_to_epsg(bounding_box_wgs84, source_epsg):
    """A WGS84 (west, south, east, north) box in another projected CRS.

    The envelope of the four transformed corners -- shared by every
    strategy that must pick projected-grid tiles (Taiwan's TWD97
    sheets, the German kilometre tile grids) from a geographic
    request box.
    """
    if source_epsg == 4326:
        return bounding_box_wgs84
    wgs84 = osr.SpatialReference()
    wgs84.ImportFromEPSG(4326)
    wgs84.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    target = osr.SpatialReference()
    target.ImportFromEPSG(source_epsg)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(wgs84, target)
    (west, south, east, north) = bounding_box_wgs84
    xs = []
    ys = []
    for (longitude, latitude) in (
        (west, south),
        (west, north),
        (east, south),
        (east, north),
    ):
        (x, y, _z) = transform.TransformPoint(longitude, latitude)
        xs.append(x)
        ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys))
