"""THE airport-selection predicates: ONE spelling of the mode filter.

Spec: ``docs/specs/insets-follow-patch-set-spec.md`` §A (rev 2), ruled by
``docs/RULINGS.md`` 2026-09-18b (insets entry) as amended by 18c and 18e.

Two independent settings select two independent populations, and both use
the SAME three-valued mode vocabulary:

* ``auto_patch``               → which airports get an auto-patch
* ``airport_elevation_insets`` → which airports get a lidar elevation inset

Before this module the mode filter was spelled inline in three places
(``driver.generate_auto_patches``, ``O4_Vector_Map.include_patches``) and
the inset set consulted nothing at all — which is how tile +38-010 spent
~3 h fetching ~190 MB insets for 17 name-keyed private strips of a tile
nobody was building (RULINGS 2026-09-18b).

PURITY: module level imports stdlib only.  Core modules
(``O4_Settings_Model``, ``O4_Cfg_Vars`` consumers, the insets module) import
the normalisers, so nothing here may drag the auto-patch pipeline in;
``auto_patch/__init__`` resolves ``generate_auto_patches`` lazily so that
``import auto_patch.selection`` does not import ``driver``.
"""
from __future__ import annotations

#: Ordered weakest → strongest.  ``None`` < ``ICAO`` < ``All``.
MODES = ("None", "ICAO", "All")

#: Rank used by the ordered comparisons (§B.2 completion stamp).
MODE_RANK = {mode: index for (index, mode) in enumerate(MODES)}

#: Legacy scalar values a config file, a JSONL front end or an in-process
#: tile object may still carry, per key.  ``auto_patch`` was a bool long
#: before it became an enum (True ⇒ every airport); ``airport_elevation_insets``
#: became an enum on 2026-09-18 and the owner RULED its map (RULINGS 18e):
#: CHECKED/True ⇒ ``"ICAO"``, UNCHECKED/False ⇒ ``"None"`` (Off).
LEGACY_TRUE = {"auto_patch": "All", "airport_elevation_insets": "ICAO"}
LEGACY_FALSE = {"auto_patch": "None", "airport_elevation_insets": "None"}

#: Textual spellings of the legacy booleans a str-typed read produces.
_TRUE_TOKENS = ("True", "true", "1")
_FALSE_TOKENS = ("False", "false", "0")

#: What an unreadable value falls back to, per key.
DEFAULT_MODE = {"auto_patch": "ICAO", "airport_elevation_insets": "ICAO"}


def normalize_mode(value, key: str, *, warn=None) -> str:
    """*value* as one of :data:`MODES`, for the setting *key*.

    Accepts, from any source: a real bool; the three mode strings (any
    surrounding whitespace); the legacy string tokens ``"True"``/``"true"``/
    ``"1"`` and ``"False"``/``"false"``/``"0"``; ``None``/absent.  Anything
    else yields one warning through *warn* (a ``callable(str)``) and the
    key's default.

    :raises KeyError: if *key* is not a mode-valued setting.
    """
    default = DEFAULT_MODE[key]
    if value is None:
        return default
    if value is True:
        return LEGACY_TRUE[key]
    if value is False:
        return LEGACY_FALSE[key]
    text = str(value).strip()
    if text in MODES:
        return text
    if text in _TRUE_TOKENS:
        return LEGACY_TRUE[key]
    if text in _FALSE_TOKENS:
        return LEGACY_FALSE[key]
    if not text:
        return default
    if warn is not None:
        warn("   WARNING: %s=%r is not one of %s — using %r."
             % (key, value, "/".join(MODES), default))
    return default


def _ui_warn(message: str) -> None:
    try:
        import O4_UI_Utils as UI

        UI.vprint(1, message)
    except Exception:                                   # pragma: no cover
        print(message)


def mode_admits(code: str, mode: str) -> bool:
    """Does selection *mode* admit the airport identified by *code*?

    THE one spelling.  ``"None"`` admits nothing, ``"All"`` admits every
    (non-empty) identifier, ``"ICAO"`` admits a 4-letter alphabetic code.

    *code* is a CIFP identifier for the patch set and a ``dico_airports``
    KEY (ICAO / IATA / local_ref / NAME) for the inset set — deliberately
    different strings, the same predicate.  Under ``"ICAO"`` a 3-letter
    IATA key, an ``LP63``-class local ref and a ``"Pista de Lavre"`` name
    key all fail, which is exactly the 17-strip class of RULINGS 18b.
    """
    if mode not in MODES:
        mode = normalize_mode(mode, "auto_patch", warn=_ui_warn)
    if mode == "None":
        return False
    code = (code or "").strip()
    if not code:
        return False
    if mode == "All":
        return True
    return len(code) == 4 and code.isalpha()


def resolved_auto_patch_mode(tile) -> str:
    """``tile.auto_patch`` normalised (moved from ``O4_Vector_Map``)."""
    return normalize_mode(getattr(tile, "auto_patch", None), "auto_patch",
                          warn=_ui_warn)


def resolved_inset_mode(tile) -> str:
    """``tile.airport_elevation_insets`` normalised.

    ``"None"`` keeps the FULL old ``False`` meaning — master gate off,
    nothing fetched and nothing on disk used (owner OQ2, RULINGS 18e).
    """
    return normalize_mode(getattr(tile, "airport_elevation_insets", None),
                          "airport_elevation_insets", warn=_ui_warn)


def inset_keys(dico_airports, mode: str) -> list:
    """The ``dico_airports`` keys the inset selection *mode* admits.

    Tuple-keyed unnamed strips are skipped before the predicate, as the
    box builder already does.
    """
    out = []
    for key in dico_airports:
        if not isinstance(key, str):
            continue
        if mode_admits(str(key).strip().upper(), mode):
            out.append(key)
    return out
