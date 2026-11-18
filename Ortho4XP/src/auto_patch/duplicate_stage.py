"""THE OFFER TO DISABLE THE LOWER OF TWO PACKS DEFINING ONE AIRPORT
(issue #2145, RULINGS 17s; the reading is ``auto_patch_v2.airport.
pack_duplicate``).

* :func:`rows` — the scenery folder's reading for a built tile: every
  enabled Custom Scenery pack's ``Earth nav data/apt.dat`` idents
  (``apt_dat.airports_in``), each pair sharing one and touching the tile
  (one of the two has a DSF on it) one row of the ``PackOverlaps`` event,
  ``"kind": "duplicate"``.  Its offer and the structure-pair question
  share the event, the picker and Apply (``overlap_stage``), and a
  same-airport pair is never also asked about as a structure pair.
* :func:`answer` — the ``pack_overlaps`` command's answer for those rows:
  ``"disable"`` marks the lower pack's ``scenery_packs.ini`` row
  ``SCENERY_PACK_DISABLED`` (``O4_Scenery_Packs``' writer: the user's ini
  kept as ``.o4bak`` the first time, the write atomic; the pack's own
  files are never touched; X-Plane reads it at its next start);
  ``"keep"`` is remembered and never asked again; no answer (Not now)
  asks again.  ``"undo"`` forgets the answer only.

A row: ``{"key", "kind": "duplicate", "packs": [upper, lower],
"airport", "default": "disable", "winner", "lower", "count", "rows": [],
"summary"}``; a pair with a pack the ini does not list is a report row
(``lower`` and ``default`` ``""``: no picker).  Nothing here names an
airport or a pack.
"""
from __future__ import annotations

import os
import typing as _t

import O4_UI_Utils as UI
from auto_patch_v2.airport import pack_duplicate as _pd

__all__ = ["KIND", "family", "rows", "answer"]

#: the ``kind`` of a same-airport row
KIND = "duplicate"


def family(scenery_dir: str, airports: _t.Collection[str] = ()
           ) -> tuple[_t.Callable[[str, str], bool], _t.Callable[[str], bool]]:
    """``(same, is_airport)``: ``same(a, b)`` when packs ``a`` and ``b``
    (names in ``scenery_dir``) are one larger package (``pack_family.
    same_family``, RULINGS 17s); ``is_airport(name)`` when the pack
    carries a runway (memoised; ``airports`` are names known to)."""
    from auto_patch_v2.airport import pack_family as _pf

    from .drape_stage import _runway_apt
    try:
        names = sorted(n for n in os.listdir(scenery_dir)
                       if os.path.isdir(os.path.join(scenery_dir, n)))
    except OSError:
        names = []
    seen: dict[str, bool] = dict.fromkeys(airports, True)

    def is_airport(name: str) -> bool:
        if name not in seen:
            seen[name] = bool(_runway_apt(os.path.join(scenery_dir, name)))
        return seen[name]

    return (lambda a, b: _pf.same_family(a, b, names, is_airport)), is_airport


def _idents(scenery_dir: str) -> dict[str, tuple[str, ...]]:
    """Every enabled pack's airport idents (packs with none left out):
    not Global Airports, not the app's own overlay pack."""
    import O4_Overlay_Pack as _OP
    import O4_Scenery_Packs as _SP
    from auto_patch_v2.airport import apt_dat as _ad
    from auto_patch_v2.airport import apt_flatten as _af
    out = {}
    for name in sorted(_SP.enabled_pack_names(scenery_dir) - _SP.NEVER_FILTERED):
        root = os.path.join(scenery_dir, name)
        apt = _af.apt_dat_of(root)
        if not apt or os.path.isfile(os.path.join(root, _OP.MARKER)):
            continue
        ids = _ad.airports_in(apt)
        if ids:
            out[name] = ids
    return out


def _summary(d: _pd.Duplicate) -> str:
    a, b = d.packs
    ids = ", ".join(d.idents)
    if not d.lower:
        return (f"{a} and {b} both define {ids}; "
                f"{' and '.join(d.unlisted)} is not listed in scenery_packs.ini, "
                "so which one X-Plane uses is not known until X-Plane lists it.")
    return (f"{a} and {b} both define {ids}. X-Plane uses {a}'s layout "
            f"(higher in scenery_packs.ini); {b}'s scenery may still overlap it.")


def rows(scenery_dir: str, on_tile: _t.Collection[str]) -> list[dict]:
    """THE READING (module doc): one row per same-airport pair with a
    pack in ``on_tile`` (pack names)."""
    import O4_Scenery_Packs as _SP
    try:
        idents = _idents(scenery_dir)
    except OSError:
        return []
    order, _disabled = _SP.parse_ini(os.path.join(scenery_dir, _SP.INI_FILENAME))
    found = _pd.duplicates(idents, order, family(scenery_dir)[0])
    out = []
    for d in found:
        if not set(d.packs) & set(on_tile):
            continue
        key = _pd.pair_key(scenery_dir, *d.packs)
        out.append({"key": key, "kind": KIND, "packs": list(d.packs),
                    "airport": ", ".join(d.idents),
                    "default": _pd.DISABLE if d.lower else "",
                    "winner": _pd.STORE.choice(key), "lower": d.lower,
                    "count": len(d.idents), "rows": [], "summary": _summary(d)})
    return out


def _disable(scenery_dir: str, name: str) -> bool:
    """Mark ``name``'s ``scenery_packs.ini`` row disabled (module doc);
    True when the ini changed (a second call changes nothing)."""
    import O4_Scenery_Packs as _SP
    ini = os.path.join(scenery_dir, _SP.INI_FILENAME)
    lines, newline = _SP.read_ini_lines(ini)
    if not _SP.set_rows_enabled(lines, [name], False):
        return False
    _SP.write_ini_lines(ini, lines, newline)
    return True


def _lower(scenery_dir: str, a: str, b: str) -> tuple[str, bool]:
    """``(the lower pack, already disabled)`` of a pair by the ini;
    ``ValueError`` when the ini does not place both."""
    import O4_Scenery_Packs as _SP
    order, disabled = _SP.parse_ini(os.path.join(scenery_dir, _SP.INI_FILENAME))
    off = [n for n in (a, b) if n in disabled]
    if off:
        return off[0], True
    if a not in order or b not in order:
        raise ValueError(f"{a!r} and {b!r} are not both listed in scenery_packs.ini")
    return (b if order.index(a) < order.index(b) else a), False


def answer(action: str, items: _t.Sequence[_t.Mapping]) -> dict:
    """THE USER'S ANSWER for same-airport rows (module doc):
    ``{"items", "files"}`` — ``files`` the ini when it changed."""
    out, files = [], []
    for it in items:
        key = str(it.get("key") or "")
        parsed = _pd.parse_key(key)
        if parsed is None:
            continue
        scenery, a, b = parsed
        value = "" if action == "undo" else str(it.get("winner") or "")
        if value not in ("", _pd.DISABLE, _pd.KEEP):
            raise ValueError(f"{value!r} is not an answer to a same-airport pair")
        row = {"key": key, "kind": KIND, "packs": [a, b], "winner": value}
        if value == _pd.DISABLE:
            lower, done = _lower(scenery, a, b)
            if not done and _disable(scenery, lower):
                files.append(os.path.join(scenery, "scenery_packs.ini"))
            row["lower"] = lower
            UI.vprint(0, f"  [overlap] {lower} disabled in scenery_packs.ini "
                      "(its files are untouched); restart X-Plane to use the change")
        if value or action == "undo":
            _pd.STORE.remember(key, value)
        out.append(row)
    return {"items": out, "files": sorted(set(files))}
