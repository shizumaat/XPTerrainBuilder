"""READING THE LIBRARY (#1699 phase 2) — never needs an account.

The library is plain files under ``config.settings()["raw_base"]``
(``https://raw.githubusercontent.com/<repo>/<branch>`` live; a
``file://`` folder for the tests and the gate).  :func:`fetch` reads
one; a missing file is ``None``, never an error (a region with no entry
has no index file).  The regional index is kept in the data folder
(``Library/index/<region>.json``) and fetched again at most once a day
unless the caller forces it (design: "at most once a day unless the user
asks").
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from . import INDEX_FORMAT, LibraryRefused
from . import config as _config
from . import layout as L
from .terms import DEFAULT_LICENCES

__all__ = ["INDEX_MAX_AGE_S", "TIMEOUT_S", "library_dir", "fetch",
           "fetch_json", "licences", "region_index"]

INDEX_MAX_AGE_S = 24 * 3600
TIMEOUT_S = 30


def library_dir() -> str:
    """``<data folder>/Library`` — the index cache and the signature cache."""
    import O4_File_Names as FNAMES
    return os.path.join(FNAMES.current_data_root(), "Library")


def _url_of(rel: str) -> str:
    """The URL of the library file ``rel`` (``/``-separated)."""
    base = _config.settings()["raw_base"]
    if not base:
        raise LibraryRefused("The patch library is not set up in this app yet")
    return base + "/" + urllib.parse.quote(rel.strip("/"))


def fetch(rel: str) -> bytes | None:
    """The bytes of library file ``rel``, or ``None`` when it is absent.

    :raises LibraryRefused: the library cannot be reached.
    """
    url = _url_of(rel)
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise LibraryRefused("The patch library answered %d for %s"
                             % (error.code, rel)) from error
    except FileNotFoundError:
        return None
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        if isinstance(reason, FileNotFoundError):
            return None
        raise LibraryRefused("The patch library cannot be reached (%s)"
                             % reason) from error


def fetch_json(rel: str):
    """A library JSON file's document, or ``None`` when it is absent."""
    data = fetch(rel)
    return None if data is None else json.loads(data.decode("utf-8"))


def licences() -> dict:
    """The library's licence gate (``licences.json``, :mod:`.terms`): fresh
    when the library answers (and cached), else the last cached copy,
    else :data:`.terms.DEFAULT_LICENCES`."""
    cache = os.path.join(library_dir(), L.LICENCES)
    try:
        doc = fetch_json(L.LICENCES)
    except LibraryRefused:
        try:
            with open(cache, "rb") as handle:
                return json.loads(handle.read().decode("utf-8"))
        except (OSError, ValueError):
            return DEFAULT_LICENCES
    if doc is None:
        return DEFAULT_LICENCES
    os.makedirs(library_dir(), exist_ok=True)
    with open(cache, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(doc, handle)
    return doc


def region_index(region: str, force: bool = False) -> dict:
    """``{icao: [row, ...]}`` of one region (``index.py``'s rows), from
    the day-old cache unless ``force``; ``{}`` when the region has none.
    An unreachable library falls back to the cache, however old."""
    cache = os.path.join(library_dir(), "index", region + ".json")
    fresh = False
    try:
        fresh = time.time() - os.path.getmtime(cache) < INDEX_MAX_AGE_S
    except OSError:
        pass
    if not (fresh and not force):
        try:
            doc = fetch_json(L.index_path(region)) or {
                "format": INDEX_FORMAT, "region": region, "airports": {}}
        except LibraryRefused:
            if not os.path.isfile(cache):
                raise
        else:
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
                json.dump(doc, handle)
            os.replace(cache + ".tmp", cache)
            return dict(doc.get("airports") or {})
    with open(cache, encoding="utf-8") as handle:
        return dict(json.load(handle).get("airports") or {})
