"""Which listed 3DEP project is the NEWER ground: acquisition, not publication.

A TNM listing dates each product by its ``publicationDate``, the day the
USGS staged it.  That is not when the ground was flown: KORD's box lists
IL_4_County_QL1_LiDAR_2016 (flown 2017-04/05, published 2024-11-18) beside
IL_MidNorth_D22 (flown 2022-03/06, published 2023-10-31), and ordering by
publication laid the 2017 survey -- flown during the O'Hare Modernization
earthworks, 15 m spoil mounds that are flat grass today -- OVER the 2022
one (RULINGS 2026-11-19g).

The acquisition date comes from the product's FGDC metadata, which 3DEP
stages beside every raster (``.../TIFF/<name>.tif`` ->
``.../metadata/<name>.xml``): the END of the first time period, the
idinfo ``timeperd``.  It is read ONCE per project directory, and only
when a listing holds more than one, so a single-project box asks
nothing more than before.  Without readable metadata, the year in the
project name (``_2016``; a delivery code ``_D22`` reads 2022) stands in.
Publication date breaks a tie.
"""

import re

#: The bound on one metadata read; a slow answer falls back to the name.
METADATA_TIMEOUT_S = 15

_TIME_PERIOD = re.compile(r"<timeperd>(.*?)</timeperd>", re.S | re.I)
_DATE_IN_PERIOD = re.compile(
    r"<(?:enddate|caldate|begdate)>\s*(\d{4})(\d{2})?(\d{2})?", re.I)
_NAME_YEAR = re.compile(r"(?:^|[_\s])((?:19|20)\d{2})(?=$|[_\s])")
_DELIVERY_CODE = re.compile(r"_[A-Z](\d{2})(?=$|[_\s])")


def _project_directory(download_url):
    """The project (work unit) directory a staged raster lives in, or None
    for a URL that is not a 3DEP staged product."""
    url = str(download_url or "").split("?", 1)[0]
    if not url.startswith("http") or "/TIFF/" not in url:
        return None
    return url.rsplit("/TIFF/", 1)[0]


def _metadata_url(download_url):
    """The FGDC XML staged beside a 3DEP raster, or None."""
    if _project_directory(download_url) is None:
        return None
    (head, name) = str(download_url).split("?", 1)[0].rsplit("/TIFF/", 1)
    return "%s/metadata/%s.xml" % (head, name.rsplit(".", 1)[0])


def _acquisition_date_from_fgdc(text):
    """``YYYY-MM-DD`` (or coarser): the latest date of the first FGDC time
    period -- the acquisition, not the publication -- or None."""
    period = _TIME_PERIOD.search(text or "")
    if period is None:
        return None
    dates = ["-".join(part for part in found if part)
             for found in _DATE_IN_PERIOD.findall(period.group(1))]
    return max(dates) if dates else None


def _year_from_project_name(title):
    """The acquisition year a 3DEP project name carries, or None: a
    four-digit year (``IL_4_County_QL1_LiDAR_2016_B16`` -> 2016), else a
    delivery code (``IL_MidNorth_D22`` -> 2022)."""
    text = str(title or "")
    years = _NAME_YEAR.findall(text)
    if years:
        return years[0]
    codes = _DELIVERY_CODE.findall(text)
    return "20" + codes[-1] if codes else None


def _read_metadata_text(url):
    """The metadata document at ``url``, or None on any failure."""
    import requests

    try:
        response = requests.get(url, timeout=METADATA_TIMEOUT_S)
    except Exception:
        return None
    if getattr(response, "status_code", None) != 200:
        return None
    return getattr(response, "text", None)


def order_newest_acquired(sources, read_text=None):
    """``sources`` newest ACQUISITION first, publication date the tie-break.

    Each source gains ``acquisition_date`` and ``acquisition_basis``
    (``metadata`` | ``project_name`` | None).  ``read_text(url)`` reads a
    metadata document (default: one bounded HTTP GET); it is asked once
    per project directory and only when the listing spans more than one.
    """
    read_text = read_text or _read_metadata_text
    directories = {_project_directory(s.get("download_url")) for s in sources}
    ask = len(directories) > 1
    by_directory = {}
    for source in sources:
        directory = _project_directory(source.get("download_url"))
        if ask and directory is not None and directory not in by_directory:
            text = read_text(_metadata_url(source.get("download_url")))
            by_directory[directory] = _acquisition_date_from_fgdc(text)
        date = by_directory.get(directory)
        basis = "metadata" if date else None
        if date is None:
            date = _year_from_project_name(source.get("title"))
            basis = "project_name" if date else None
        source["acquisition_date"] = date
        source["acquisition_basis"] = basis
    return sorted(
        sources,
        key=lambda s: (s.get("acquisition_date") or "",
                       s.get("publication_date") or ""),
        reverse=True)
