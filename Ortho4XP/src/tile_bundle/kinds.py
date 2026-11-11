"""PACKAGE KINDS (#2014 follow-up; owner 2026-11-11T16:10Z): what an
exported package holds, said in the same words in both apps.

Owner, verbatim: "Because airport patches and object mods are dependent on
their elevation data, we should support a couple package options: bundle
the whole tile for an exact match, or only a specific airport patch which
then requires the recipient to do a larger download and build. … Most
logical I think would be for exports to focus on a specific airport and
XPTerrainBuilder than aggregates them when building to minimize
downloads."

* :data:`EXACT` — one airport with the elevation and map data it was
  graded on: its insets, the approach-ring cells it uses
  (:mod:`.rings`), the tile's base rasters and OSM layers, and the
  airport's own custom patch and user edits.  The recipient rebuilds the
  airport offline except imagery (the tile's OTHER airports' elevation
  still downloads when the whole tile builds).
* :data:`PATCH` — only the airport's own custom patch and user edits
  (patch, editor sidecar, hand-set roles, hand-set object seats):
  smallest; the recipient's build downloads the elevation and map data.
* :data:`TILE` — the whole tile (every airport's insets and rings, every
  custom patch): exact reproduction of the tile; offered last.

An airport package (EXACT or PATCH) never holds an auto patch or another
airport's custom patch.  The manifest records the kind and what the
recipient still downloads (:func:`still_needs`), which the install sheet
says.  Several airport packages for one tile install side by side
(:mod:`.install` unions their data) and one build uses them together.
"""
from __future__ import annotations

__all__ = ["TILE", "EXACT", "PATCH", "COMBINED", "KINDS", "AIRPORT_KINDS", "TITLES",
           "EXPLANATIONS", "resolve", "still_needs", "size_text", "span_text",
           "combine", "figures_text"]

TILE = "tile"
EXACT = "exact"
PATCH = "patch"
#: Packages of different kinds combined (``merge.merge_packages``).
COMBINED = "combined"

#: The kinds in the order the export window offers them (whole tile last).
KINDS = (EXACT, PATCH, TILE)
AIRPORT_KINDS = (EXACT, PATCH)

#: Each kind's name and one-line explanation (both apps show these).
TITLES = {EXACT: "Exact match", PATCH: "Airport patch only", TILE: "Whole tile",
          COMBINED: "Combined packages"}
EXPLANATIONS = {
    EXACT: "The airport with the elevation and map data it was graded on; "
           "the recipient rebuilds it offline except imagery.",
    PATCH: "Only this airport's custom patch and edits (smallest); the "
           "recipient downloads elevation and map data and builds.",
    TILE: "Every airport and all data of the tile, for an exact copy of the "
          "tile (largest).",
    COMBINED: "Several packages in one; each airport is as its own package "
              "held it.",
}


def resolve(kind, airports) -> str:
    """The kind of a save: ``kind`` when given, else EXACT for an airport
    package and TILE without airports.

    :raises ValueError: an unknown kind, or an airport kind without an
        airport."""
    kind = str(kind or (EXACT if airports else TILE)).lower()
    if kind not in KINDS:
        raise ValueError("unknown package kind %r (one of %s)" % (kind, ", ".join(KINDS)))
    if kind in AIRPORT_KINDS and not airports:
        raise ValueError("Choose the airport to export.")
    return kind


def size_text(n) -> str:
    """``"12.3 MB"`` / ``"450 KB"`` — the size both apps print."""
    n = int(n or 0)
    return "%.1f MB" % (n / 1e6) if n >= 100_000 else "%d KB" % max(1, n // 1000)


def span_text(seconds, low=None, high=None) -> str:
    """``"14–19 min"`` (``low``-``high``, a range) or ``"14 min"``."""
    mid = max(1, round((seconds or 0) / 60.0))
    if low is None or high is None:
        return "%d min" % mid
    lo, hi = max(1, round(low / 60.0)), max(1, round(high / 60.0))
    return "%d min" % mid if lo >= hi else "%d–%d min" % (lo, hi)


def figures_text(package_bytes, download_bytes, build_seconds, low=None, high=None,
                 download_seconds=0.0, breakdown="") -> str:
    """One kind's figures as both export windows show them: the package,
    what the recipient downloads (timed at
    ``recipient_time.BYTES_PER_SECOND``) and how long until the tile is
    built, downloads included (``low``/``high``: its range); then, on a
    second line, ``breakdown`` (``recipient_time.breakdown_text``)."""
    from .recipient_time import BYTES_PER_SECOND
    if download_bytes:
        downloads = ("recipient downloads about %s plus imagery (about %s at %d MB/s)"
                     % (size_text(download_bytes),
                        span_text(download_seconds), BYTES_PER_SECOND // 1_000_000))
    else:
        downloads = "recipient downloads only imagery"
    text = "about %s · %s · builds in about %s (estimate)" % (
        size_text(package_bytes), downloads, span_text(build_seconds, low, high))
    return text + ("\n" + breakdown if breakdown else "")


def still_needs(kind: str, other_airport_bytes: int = 0, data_bytes: int = 0) -> list:
    """``[{"what", "text", "bytes"}]``: what a recipient's build of the
    package's tiles still downloads.  ``other_airport_bytes``: the tile's
    other airports' elevation an EXACT package leaves out;
    ``data_bytes``: the map and elevation data a PATCH package leaves out
    (each the bytes its sources cost to fetch, ``source_bytes``)."""
    rows = []
    if kind == PATCH:
        rows.append({"what": "data", "bytes": int(data_bytes),
                     "text": "Elevation and map data for the tile (about %s to download)"
                     % size_text(data_bytes)})
    elif kind == EXACT and other_airport_bytes:
        rows.append({"what": "other_airports", "bytes": int(other_airport_bytes),
                     "text": "Elevation for the tile's other airports (about %s to download)"
                     % size_text(other_airport_bytes)})
    rows.append({"what": "imagery", "bytes": None, "text": "Imagery"})
    return rows


def combine(manifests) -> dict:
    """The kind, still-needs rows and estimate of several manifests
    combined: one kind or :data:`COMBINED`; each still-needs row once
    (its largest figure); the longest build."""
    found = {m.get("kind") for m in manifests if m.get("kind")}
    needs: dict = {}
    for manifest in manifests:
        for row in manifest.get("still_needs") or []:
            held = needs.setdefault(row["what"], dict(row))
            if (row.get("bytes") or 0) > (held.get("bytes") or 0):
                needs[row["what"]] = dict(row)
    seconds = max([(m.get("estimate") or {}).get("build_seconds") or 0
                   for m in manifests] or [0])
    downloads = sum(r.get("bytes") or 0 for r in needs.values())
    return {"kind": found.pop() if len(found) == 1 else (COMBINED if found else ""),
            "still_needs": sorted(needs.values(), key=lambda r: r["what"] == "imagery"),
            "estimate": {"build_seconds": seconds, "download_bytes": downloads}}
