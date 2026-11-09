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
of the features that are on (:func:`matching`), else Custom.

Owner, 2026-11-09T17:01Z and 17:05Z: every preset is Detail ICAO; the
presets differ in how much each airport feature does (the ZL18 imagery's
reach, the approach rings, the elevation detail), not in where it
applies — and a user may still turn a feature off by hand.  So Detail
reads the four airport FEATURES (:data:`FEATURES`): each is off (its
None value) or on for one choice; Detail is the one choice every
feature that is on agrees on (None when all are off), else Custom.
Switching between ICAO and All re-scopes the features that are on and
leaves the off ones off; choosing ICAO or All from None or Custom turns
them all on, with ZL16 outside the airports and ZL18 at them.
The engine itself never reads this module — its readers read the
per-feature keys as before, so a build outside the apps is unchanged.

:func:`migrate_cfg` carries an existing config over once (see there).
"""

from __future__ import annotations

import os

__all__ = ["CHOICES", "DEFAULT", "TITLE", "SUMMARY", "CUSTOM_TITLE", "OUTSIDE_ZL",
    "AIRPORT_ZL", "SCOPE_KEYS", "FEATURES", "scope_values", "values",
    "zoom", "feature_states", "from_states", "migrate_cfg"]

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

#: The airport features, each by its keys, in :data:`SCOPE_KEYS` order:
#: sharper imagery, grading, high-resolution elevation, measured depth.
FEATURES = (
    ("cover_airports_with_highres",),
    ("auto_patch",),
    ("airport_elevation_insets",),
    ("bathymetry_near_icao_airports", "bathymetry_near_other_airports"),
)

_SCOPE = {
    "none": ("False", "None", "None", "False", "False"),
    "icao": ("ICAO", "ICAO", "ICAO", "True", "False"),
    "all": ("True", "All", "All", "True", "True"),
}


def _check(choice):
    if choice not in _SCOPE:
        raise KeyError(choice)


def scope_values(choice):
    """The per-feature keys ``choice`` decides, as cfg literals."""
    _check(choice)
    return dict(zip(SCOPE_KEYS, _SCOPE[choice], strict=True))


def _full(choice, current):
    """Whether choosing ``choice`` turns every feature on: from None or
    Custom (``current`` the shown choice), never to None."""
    return choice != "none" and current not in ("icao", "all")


def zoom(choice, current=None):
    """The build zoom ``choice`` sets coming from ``current`` (the shown
    choice, None: Custom), or ``None`` (leave it)."""
    _check(choice)
    return OUTSIDE_ZL if _full(choice, current) else None


def values(choice, current=None, states=None):
    """Every cfg key choosing ``choice`` writes, coming from the shown
    choice ``current`` with feature ``states`` (:func:`feature_states`).
    From None or Custom: every scope key, plus the airport zoom
    (``cover_zl``) for ICAO or All.  From ICAO or All: the keys of the
    features that are on, re-scoped (to None: every key off).  The build
    zoom is :func:`zoom` (a preference, not a cfg key)."""
    full = scope_values(choice)
    if _full(choice, current):
        full["cover_zl"] = str(AIRPORT_ZL)
        return full
    if choice == "none" or states is None:
        return full
    return {name: full[name]
            for keys, state in zip(FEATURES, states, strict=True)
            if state not in (None, "none") for name in keys}


def feature_states(current, same=None):
    """Each feature's state in ``current`` (name -> cfg literal): the
    choice its keys equal (``"none"``: off), or ``None`` (neither)."""
    same = same or _same
    states = []
    for keys in FEATURES:
        state = None
        for choice, _title in CHOICES:
            wanted = scope_values(choice)
            if all(name in current
                   and same(name, str(current[name]), wanted[name])
                   for name in keys):
                state = choice
                break
        states.append(state)
    return states


def from_states(states):
    """The Detail the feature ``states`` show, or ``None`` (Custom)."""
    if None in states:
        return None
    on = {state for state in states if state != "none"}
    if not on:
        return "none"
    return on.pop() if len(on) == 1 else None


def _matching(current, same=None):
    """The choice ``current`` (name -> cfg literal) shows, else ``None``
    (Custom).  ``same(name, a, b)`` compares two literals (default: equal
    text, booleans by meaning)."""
    return from_states(feature_states(current, same))


def _same(_name, first, second):
    first, second = first.strip(), second.strip()
    booleans = {"true": "True", "1": "True", "false": "False", "0": "False"}
    return booleans.get(first.lower(), first) == booleans.get(
        second.lower(), second)


# ── migrating an existing config (once) ─────────────────────────────────

#: Before #1985 the sharper airport imagery and the grading were the
#: airport-scope choices the app offered; the other keys sat at the engine
#: defaults below.  Only those keys, at exactly those values, are ever
#: rewritten.
_OLD_DEFAULTS = {
    "auto_patch": "ICAO",
    "airport_elevation_insets": "ICAO",
    "bathymetry_near_icao_airports": "True",
    "bathymetry_near_other_airports": "True",
}

#: The old choice -> the Detail it now stands for: the sharper imagery's
#: scope when it is on, else the grading's.  Grading off with imagery
#: off is not migrated (it already reads as None or Custom).
_FROM_HIGHRES = {"ICAO": "icao", "True": "all"}
_FROM_GRADING = {"ICAO": "icao", "All": "all"}


def _migrate(raw, inherited=None):
    """The changes that carry the config ``raw`` (name -> literal) over
    to Detail: ``{name: new literal}``, possibly empty.

    The config's sharper-imagery scope picks the choice, else its grading
    scope; a feature that is ON is re-scoped to it, and only where a key
    still holds its old engine default (in ``raw``, or inherited from
    ``inherited`` when ``raw`` lacks it, as a sparse tile cfg does) — a
    value the user chose is never changed, and nothing is turned on or
    off.  A sparse tile cfg that sets neither scope is left to its global.
    """
    inherited = inherited or {}

    def value(name, default=""):
        return str(raw.get(name, inherited.get(name, default))).strip()

    if ("cover_airports_with_highres" not in raw
            and "auto_patch" not in raw):
        return {}
    choice = _FROM_HIGHRES.get(value("cover_airports_with_highres")) \
        or _FROM_GRADING.get(value("auto_patch", "ICAO"))
    if choice is None:
        return {}
    changes = {}
    for name, new in scope_values(choice).items():
        old = _OLD_DEFAULTS.get(name)
        if old is None:
            continue
        current = value(name, old)
        if _same(name, current, old) and not _same(name, old, new):
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
        changes = _migrate(data, inherited)
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
