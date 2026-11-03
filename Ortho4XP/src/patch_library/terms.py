"""PER-SOURCE TERMS (owner Q319, 2026-11-03) — stdlib only.

The library's ``licences.json`` sorts every source provider into one of
three classes: ``allowed`` (redistribution with attribution is open),
``noncommercial`` (it publishes, and the entry is marked non-commercial
AS A WHOLE) and ``held`` (it refuses the entry: redistribution ruled
out, registration required, or no terms found).  A provider in no class
refuses too.  Each row carries the source's licence, the attribution an
entry credits, the URL of the terms that were read, and a one-line
summary.

An entry's own licence follows from its sources: ODbL 1.0 (the library's
structure, and OpenStreetMap's licence) when every source is open,
:data:`LICENCE_NC` when any source is non-commercial.  The app annotates
the sources it packages (:func:`annotate`); the library's checks
re-derive the class from the library's own file (:func:`problems`), so a
manifest cannot claim an open licence for a non-commercial source.
"""
from __future__ import annotations

from . import LICENCE, LICENCE_NC

__all__ = ["CLASSES", "DEFAULT_LICENCES", "NC_MARK", "classify", "annotate",
           "held", "entry_licence", "source_line", "statement", "problems"]

#: How a list row marks a non-commercial entry (both apps write it so).
NC_MARK = " · non-commercial"

#: The classes of ``licences.json``, open first.
CLASSES = ("allowed", "noncommercial", "held")

#: The gate a library without ``licences.json`` uses: OpenStreetMap and
#: the engine's base elevation only.
DEFAULT_LICENCES = {
    "allowed": {"OpenStreetMap": {"licence": "ODbL-1.0",
                                  "attribution": "© OpenStreetMap contributors"},
                "base:auto": {"licence": "the engine's base elevation"}},
    "noncommercial": {}, "held": {}}


def classify(licences: dict, provider: str) -> tuple:
    """``(class, row)`` of ``provider`` in ``licences`` — ``(None, {})``
    when no class lists it.  A row given as a bare string is its licence."""
    for name in CLASSES:
        row = ((licences or DEFAULT_LICENCES).get(name) or {}).get(provider)
        if row is not None:
            return name, (row if isinstance(row, dict) else {"licence": str(row)})
    return None, {}


def annotate(sources: list, licences: dict) -> list:
    """``sources`` with each one's terms from ``licences``: ``terms`` (the
    URL), ``noncommercial``, and the library's attribution as ``credit``
    when it has one."""
    out = []
    for source in sources:
        name, row = classify(licences, str(source.get("provider", "")))
        item = dict(source, terms=str(row.get("terms", "")),
                    noncommercial=name == "noncommercial")
        if row.get("attribution"):
            item["credit"] = str(row["attribution"])
        out.append(item)
    return out


def held(sources: list, licences: dict) -> list:
    """``[(provider, why)]`` of the sources ``licences`` holds."""
    out = []
    for source in sources:
        name, row = classify(licences, str(source.get("provider", "")))
        if name == "held":
            out.append((source["provider"], row.get("summary") or row.get("licence", "")))
    return out


def entry_licence(sources: list) -> str:
    """The licence of an entry with these (annotated) sources."""
    return LICENCE_NC if any(s.get("noncommercial") for s in sources) else LICENCE


def source_line(source: dict) -> str:
    """One source's line in an ATTRIBUTION.txt: provider, licence, the
    non-commercial mark, credit and the terms URL."""
    return "- %s (%s%s)%s%s" % (
        source["provider"], source["licence"],
        "; non-commercial" if source.get("noncommercial") else "",
        ": " + source["credit"] if source.get("credit") else "",
        "\n  terms: " + source["terms"] if source.get("terms") else "")


def statement(licence: str, what: str = "entry") -> str:
    """The licence sentence an ATTRIBUTION.txt and pull request say of an
    ``what`` (an airport entry, a tile bundle) under ``licence``."""
    if licence == LICENCE_NC:
        return ("NON-COMMERCIAL: this " + what + " is built from a source whose terms "
                "allow non-commercial use only, so the whole " + what + " is offered "
                "for non-commercial use, under each source's terms listed "
                "above (the library's structure is ODbL 1.0). © OpenStreetMap "
                "contributors.")
    return ("Published under the Open Database License (ODbL) 1.0, the "
            "licence of the OpenStreetMap data it is built from, and each "
            "source's terms listed above. © OpenStreetMap contributors.")


def problems(doc: dict, licences: dict) -> list:
    """The licence problems of a manifest against the library's gate."""
    out, noncommercial = [], False
    for source in doc.get("sources") or []:
        provider = str(source.get("provider", ""))
        name, row = classify(licences, provider)
        if name == "held":
            out.append("source %s is held (%s)" % (provider, row.get("summary")
                                                   or row.get("licence", "")))
        elif name is None:
            out.append("source %s is not on the library's licence allowlist"
                       % provider)
        noncommercial |= name == "noncommercial"
    if not any(s.get("provider") == "OpenStreetMap" for s in doc.get("sources") or []):
        out.append("the sources do not credit OpenStreetMap")
    want = LICENCE_NC if noncommercial else LICENCE
    if doc.get("licence") != want:
        out.append("an entry with these sources is published under %s, not %r"
                   % (want, doc.get("licence")))
    if bool(doc.get("noncommercial")) != noncommercial:
        out.append("the manifest's non-commercial mark is %s; its sources make it %s"
                   % (bool(doc.get("noncommercial")), noncommercial))
    return out
