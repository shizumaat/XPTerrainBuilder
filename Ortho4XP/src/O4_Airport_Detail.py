"""The one Detail choice: where to add airport detail (issue #1985).

Owner, 2026-11-09: one setting decides whether to add detail at NO
airports, at airports with an ICAO code (the default) or at ALL airports,
and it applies to every per-airport option at once — the sharper airport
imagery, the grading, the high-resolution elevation and the measured sea
depth.  Choosing ICAO or All also sets the imagery to ZL16 outside the
airports and ZL18 at them.

This module is that table, read by the Qt app and mirrored row for row by
the Mac app (``Sources/XPTerrainBuilder/AirportDetail.swift``;
``tests/test_airport_detail.py`` fails when the two differ).  Detail is
NOT a stored key: a choice WRITES the per-feature keys (:func:`values`,
through the same paths a preset uses), and the control SHOWS the choice
whose keys all hold (:func:`matching`), else Custom.  The per-feature
settings stay in Settings for experts; changing one makes Detail Custom.
The engine itself never reads this module — its readers read the
per-feature keys as before, so a build outside the apps is unchanged.

:func:`migrate_cfg` carries an existing config over once (see there).
"""

from __future__ import annotations

import os

__all__ = [
    "CHOICES", "DEFAULT", "TITLE", "SUMMARY", "CUSTOM_TITLE", "OUTSIDE_ZL",
    "AIRPORT_ZL", "SCOPE_KEYS", "scope_values", "values", "zoom",
    "matching", "title", "migrate", "migrate_cfg",
]

#: The control's words (the Mac app uses the same ones).
TITLE = "Detail"
SUMMARY = ("Where to add sharper imagery, graded runways and taxiways, "
           "the best elevation and measured sea depth.")
CUSTOM_TITLE = "Custom"

#: (key, title) in menu order.
CHOICES = (
    ("none", "None"),
    ("icao", "ICAO airports"),
    ("all", "All airports"),
)
DEFAULT = "icao"

#: ICAO or All: the imagery zoom outside airports, and at them.
OUTSIDE_ZL = 16
AIRPORT_ZL = 18

#: The per-feature keys a choice decides, in display order.
SCOPE_KEYS = (
    "cover_airports_with_highres",
    "auto_patch",
    "airport_elevation_insets",
    "bathymetry_near_icao_airports",
    "bathymetry_near_other_airports",
)

_SCOPE = {
    "none": ("False", "None", "None", "False", "False"),
    "icao": ("ICAO", "ICAO", "ICAO", "True", "False"),
    "all": ("True", "All", "All", "True", "True"),
}


def _check(choice):
    if choice not in _SCOPE:
        raise KeyError(choice)


def title(choice):
    _check(choice)
    return dict(CHOICES)[choice]


def scope_values(choice):
    """The per-feature keys ``choice`` decides, as cfg literals."""
    _check(choice)
    return dict(zip(SCOPE_KEYS, _SCOPE[choice], strict=True))


def zoom(choice):
    """The build zoom ``choice`` sets, or ``None`` (None leaves it)."""
    _check(choice)
    return None if choice == "none" else OUTSIDE_ZL


def values(choice):
    """Every cfg key ``choice`` writes: its scope keys, plus the airport
    zoom (``cover_zl``) when it adds detail.  The build zoom is
    :func:`zoom` (a preference, not a cfg key)."""
    out = scope_values(choice)
    if zoom(choice) is not None:
        out["cover_zl"] = str(AIRPORT_ZL)
    return out


def matching(current, same=None):
    """The choice whose scope keys all hold in ``current`` (name -> cfg
    literal), else ``None`` (Custom).  ``same(name, a, b)`` compares two
    literals (default: equal text, booleans by meaning)."""
    same = same or _same
    for choice, _title in CHOICES:
        if all(name in current and same(name, str(current[name]), value)
               for name, value in scope_values(choice).items()):
            return choice
    return None


def _same(_name, first, second):
    first, second = first.strip(), second.strip()
    booleans = {"true": "True", "1": "True", "false": "False", "0": "False"}
    return booleans.get(first.lower(), first) == booleans.get(
        second.lower(), second)


# ── migrating an existing config (once) ─────────────────────────────────

#: Before #1985 the sharper airport imagery was the only airport-scope
#: choice the app offered; the other keys sat at the engine defaults
#: below.  Only those keys, at exactly those values, are ever rewritten.
_OLD_DEFAULTS = {
    "auto_patch": "ICAO",
    "airport_elevation_insets": "ICAO",
    "bathymetry_near_icao_airports": "True",
    "bathymetry_near_other_airports": "True",
}

#: The old imagery choice -> the Detail it now stands for.  ``False``
#: (Balanced, Light on disk) is NOT migrated: Detail None also stops
#: grading and the elevation insets, which a config never loses
#: silently — it shows Custom until the user picks.
_FROM_HIGHRES = {"ICAO": "icao", "True": "all"}


def migrate(raw, inherited=None):
    """The changes that carry the config ``raw`` (name -> literal) over
    to Detail: ``{name: new literal}``, possibly empty.

    The config's ``cover_airports_with_highres`` picks the choice; a
    scope key is rewritten only where it still holds its old engine
    default (in ``raw``, or inherited from ``inherited`` when ``raw``
    lacks it, as a sparse tile cfg does) — a value the user chose is
    never changed.
    """
    inherited = inherited or {}
    if "cover_airports_with_highres" not in raw:
        return {}
    choice = _FROM_HIGHRES.get(str(raw["cover_airports_with_highres"]).strip())
    if choice is None:
        return {}
    changes = {}
    for name, new in scope_values(choice).items():
        old = _OLD_DEFAULTS.get(name)
        if old is None:
            continue
        current = raw.get(name, inherited.get(name, old))
        if _same(name, str(current), old) and not _same(name, old, new):
            changes[name] = new
    return changes


#: The once-per-file register entry (``O4_Cfg_Vars``' ``<cfg>.defaults``).
REGISTER_ENTRY = "airport_detail"


def migrate_cfg(cfg_path, inherited_cfg=None):
    """Apply :func:`migrate` to the cfg file at ``cfg_path`` ONCE, recorded
    in its ``<cfg>.defaults`` register as :data:`REGISTER_ENTRY`; later a
    value set by hand is never touched.  A sparse tile cfg passes the
    global cfg it inherits from as ``inherited_cfg``.  The readers call
    it BEFORE they read the file, so the build that migrates already
    reads the new values.

    :returns: INFO lines for the caller to print.  Never raises.
    """
    try:
        if not cfg_path or not os.path.isfile(cfg_path):
            return []
        import O4_Cfg_Vars as CV
        import O4_Settings_Model as SETTINGS

        if REGISTER_ENTRY in CV._read_register(cfg_path):
            return []
        data = SETTINGS._parse_cfg(cfg_path, strip_quotes=False)
        inherited = (SETTINGS._parse_cfg(inherited_cfg, strip_quotes=False)
                     if inherited_cfg and os.path.isfile(inherited_cfg)
                     else None)
        changes = migrate(data, inherited)
        if changes:
            data.update(changes)
            SETTINGS._write_atomic_with_backup(cfg_path, data)
        with open(CV._register_path(cfg_path), "a", encoding="utf-8",
                  newline="\n") as f:
            f.write(REGISTER_ENTRY + "\n")
        return ["set %s=%s for the airport Detail choice in %s"
                % (name, value, cfg_path) for name, value in changes.items()]
    except Exception:
        return []
