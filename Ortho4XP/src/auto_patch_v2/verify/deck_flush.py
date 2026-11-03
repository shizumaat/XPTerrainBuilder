"""THE DECK END LINE IS FLUSH — v2 verify's reader of the census family
``deck_end_flush`` (spec ``deck-end-anchors-20261103`` §6; owner RULINGS
2026-10-30a (1), 2026-11-03c; issue #1715).

The publication's ``deck_anchors`` names every pack hard deck's end-line
stations and tops; a station whose emitted elevation stands off the deck's
one zero (the mean over every station of ``z − top``) plus its end line's
top by more than ``[bridge] deck_flush_m``, or a held anchor off the level
it was pinned at, is a row — joined at the canonical identity as the pin
families are (``verify/pins._by_ll``).  The census reads the same record
(``check_grade_lib/families/deck_end_flush``)."""
from __future__ import annotations

from .frame import Patch, Row, row
from .pins import JOIN_DP, _by_ll

__all__ = ["FAMILY_DECK_END_FLUSH", "deck_end_flush"]

FAMILY_DECK_END_FLUSH = "deck_end_flush"


def _key(lat, lon) -> tuple[float, float]:
    return round(float(lat), JOIN_DP), round(float(lon), JOIN_DP)


def _read(ends, by_ll) -> list:
    """``(key, z, shape, top)`` of every station of one object, each once."""
    read, seen = [], set()
    for r in ends:
        for lat, lon in r.get("stations") or ():
            k = _key(lat, lon)
            if k in by_ll and k not in seen:
                seen.add(k)
                read.append((k, *by_ll[k], float(r.get("top_y") or 0.0)))
    return read


def deck_end_flush(p: Patch) -> list[Row]:
    """The family's rows (module doc)."""
    recs = p.publication.get("deck_anchors") or ()
    if not recs:
        return []
    by_ll = _by_ll(p)
    flush = float(p.law.tables.structures.bridge.deck_flush_m)
    by_obj: dict[str, list] = {}
    for r in recs:
        by_obj.setdefault(str(r.get("object")), []).append(r)
    out: list[Row] = []

    def add(k, z: float, want: float, sh) -> None:
        xy = p.to_m(*k)
        out.append(row(FAMILY_DECK_END_FLUSH, (sh.role,), p.side(sh.role), abs(z - want),
                       None, None, None, xy, xy, sh.ref, sh.ref, lat=k[0], lon=k[1]))
    for _oid, ends in sorted(by_obj.items()):
        read = _read(ends, by_ll)
        if read:
            zero = sum(z - top for _k, z, _sh, top in read) / len(read)
            for k, z, sh, top in read:
                if abs(z - zero - top) > flush:
                    add(k, z, zero + top, sh)
        for r in ends:
            if r.get("pinned") and not r.get("yielding") and r.get("at"):
                k = _key(*r["at"])
                if k in by_ll and abs(by_ll[k][0] - float(r["z_m"])) > flush:
                    add(k, by_ll[k][0], float(r["z_m"]), by_ll[k][1])
    out.sort(key=lambda q: -float(q["magnitude_m"]))
    return out
