"""Airport search by code or name (issue #543, owner RULINGS 2026-10-17c).

The search field's ONE rule, shared by the Qt window (in-process) and the
macOS app (``Sources/SceneryKit/AirportSearch.swift``, the Swift half),
twinned on ``tests/fixtures/airport_search_cases.json``.  It reads only
what the airport index already holds -- code, name, city, country and the
size columns (:mod:`O4_Airport_Index`, :mod:`O4_Airport_Rank`); no city
list or other dataset is added.

* :func:`normalize` folds case and accents and turns punctuation into
  spaces: ``"Zürich-Kloten"`` -> ``"zurich kloten"``.
* A query MATCHES an airport when every query word is the start of a word
  in the airport's text.  How well it matches is a tier (lower better):

  0. the code equals the query;
  1. the code starts with the query (one word);
  2. the name starts with the query;
  3. every query word starts a word of the name;
  4. every query word starts a word of the name, city or country.

* Results are ordered by tier, then size (O4_Airport_Rank.rank_key), so
  among equal matches the larger airport comes first.

No airport is named here (owner standing 2026-10-05).
"""

import unicodedata
from typing import Iterable, List, Optional, Sequence

import O4_Airport_Rank as RANK

__all__ = [
    "NO_INDEX_TEXT",
    "MIN_QUERY_LENGTH",
    "RESULT_LIMIT",
    "normalize",
    "result_label",
    "no_match_text",
    "AirportSearchIndex",
]

# Fewer normalised characters than this search nothing.
MIN_QUERY_LENGTH = 2
# Rows in the live result list.
RESULT_LIMIT = 8

_SEPARATOR = " · "


def normalize(text: str) -> str:
    """Lower case, accents dropped (compatibility decomposition, then
    every non-spacing mark removed), anything but a letter or a number a
    space, runs of spaces collapsed."""
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    out = []
    for ch in decomposed:
        category = unicodedata.category(ch)
        if category == "Mn":
            continue
        out.append(ch if category[0] in "LN" else " ")
    return " ".join("".join(out).split())


def result_label(code: str, name: str, city: str = "",
                 country: str = "") -> str:
    """One result row: ``CODE · Name · City, Country`` (empty parts
    left out)."""
    place = ", ".join(p for p in (city.strip(), country.strip()) if p)
    return _SEPARATOR.join(p for p in (code, name.strip(), place) if p)


#: The result list's only row when there is no airport index at all.
NO_INDEX_TEXT = ("Airport search needs your X-Plane folder: set it in "
                 "Settings \u25b8 General")


def no_match_text(query: str) -> str:
    """The result list's only row when nothing matches."""
    return "No airport matches “%s”" % query.strip()


class _Row:
    __slots__ = ("entry", "code", "name", "name_words", "all_words", "key")

    def __init__(self, entry) -> None:
        self.entry = entry
        self.code = normalize(entry.code)
        self.name = normalize(entry.name)
        # Leading space: " tok" in it <=> tok starts one of its words.
        self.name_words = " " + self.name
        self.all_words = " " + " ".join(
            p for p in (self.name, normalize(entry.city),
                        normalize(entry.country)) if p)
        self.key = RANK.rank_key(entry.code, getattr(entry, "size_class",
                                                     RANK.UNKNOWN_SIZE_CLASS),
                                 getattr(entry, "runway_m", 0))


class AirportSearchIndex:
    """The index entries, normalised ONCE, searched per keystroke.

    ``entries`` are :class:`O4_Airport_Index.AirportEntry` rows (anything
    with ``code name city country`` and optionally the size columns).
    """

    def __init__(self, entries: Iterable) -> None:
        self._rows = [_Row(e) for e in entries]

    def search(self, query: str, limit: int = RESULT_LIMIT) -> List:
        """The best ``limit`` entries for ``query``, best first; ``[]``
        for a query shorter than :data:`MIN_QUERY_LENGTH` or one that
        matches nothing."""
        q = normalize(query)
        if len(q) < MIN_QUERY_LENGTH:
            return []
        words = q.split()
        needles = [" " + w for w in words]
        hits = []
        for row in self._rows:
            tier = _tier(row, q, words, needles)
            if tier is not None:
                hits.append((tier, row.key, row.entry))
        hits.sort(key=lambda h: (h[0], h[1]))
        return [entry for _, _, entry in hits[:max(0, limit)]]


def _tier(row: _Row, q: str, words: Sequence[str],
          needles: Sequence[str]) -> Optional[int]:
    if row.code == q:
        return 0
    if len(words) == 1 and row.code.startswith(q):
        return 1
    if row.name.startswith(q):
        return 2
    if all(n in row.name_words for n in needles):
        return 3
    if all(n in row.all_words for n in needles):
        return 4
    return None
