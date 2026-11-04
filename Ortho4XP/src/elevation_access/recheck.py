"""When a recorded inset answer is asked again: its age and its provider's version.

Owner 2026-11-04 ("some sort of date stamp check ... not every build"):
a recorded answer about an airport -- a durable ``no-coverage``, a
delivered inset's finer-rung listing -- is asked again only when it is
older than the ``elevation_recheck_days`` setting (default 30) or when
THE PROVIDER changed: its definition (the ``.elv`` file, the query law)
or the capabilities this run has for it.  The engine's own version is
not a reason: before this, every engine release re-asked every
capability-free negative once (owner RULINGS 2026-09-15aq (4)), so each
new build of the app re-probed providers that had already said "nothing
here" days before.

:func:`provider_version` is that per-provider version; :func:`is_due`
the age test.  Both are pure: no network, no file.
"""

from __future__ import annotations

import datetime
import hashlib
import sys

__all__ = [
    "RECHECK_DAYS_DEFAULT",
    "is_due",
    "provider_version",
    "recheck_days",
]

#: The default of the ``elevation_recheck_days`` setting.
RECHECK_DAYS_DEFAULT = 30.0

#: Definition keys that do not change what the provider ANSWERS: the
#: user's ranking and switch, and the per-airport LAS footprint the
#: ladder records once.
_NOT_THE_QUESTION = ("priority", "enabled", "footprint_polygon_wgs84")


def recheck_days() -> float:
    """The ``elevation_recheck_days`` setting (a float >= 0).

    Read from ``O4_Config_Utils`` when it is loaded (it is, at build
    time) -- never imported here, which would run its global config
    creation from a passive check."""
    try:
        cfg = sys.modules.get("O4_Config_Utils")
        value = float(getattr(cfg, "elevation_recheck_days",
                              RECHECK_DAYS_DEFAULT)
                      if cfg is not None else RECHECK_DAYS_DEFAULT)
    except (TypeError, ValueError):
        value = RECHECK_DAYS_DEFAULT
    return max(0.0, value)


def _stable(value):
    """``value`` with every set sorted, so its repr is the same in every
    process (a frozenset's iteration order follows string hashing)."""
    if isinstance(value, (set, frozenset)):
        return sorted(_stable(item) for item in value)
    if isinstance(value, dict):
        return sorted((str(key), _stable(item)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return [_stable(item) for item in value]
    return value


def provider_version(definition, capabilities=(), law=None) -> str:
    """The version of what asking ``definition`` means, 16 hex digits.

    A digest of the definition's keys (all but :data:`_NOT_THE_QUESTION`),
    the required capabilities this run HAS (``capabilities``) and the
    query law the answer is judged under (``law``).  Editing the ``.elv``
    -- a new endpoint, layer, strategy or ``provider_version=`` line --
    changes it; a new engine release does not."""
    items = [(str(key), repr(_stable(value)))
             for (key, value) in sorted((definition or {}).items(),
                                        key=lambda kv: str(kv[0]))
             if key not in _NOT_THE_QUESTION]
    payload = repr((items, sorted(capabilities or ()), law))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _as_date(value):
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def is_due(checked, days=None, today=None) -> bool:
    """Is an answer checked on ``checked`` (ISO date) old enough to ask again?

    True when it is MORE than ``days`` (default :func:`recheck_days`) old.
    An unreadable or absent date is not due: a record that cannot say
    when it was asked is dated by its migration, never re-probed for the
    schema change alone."""
    when = _as_date(checked)
    if when is None:
        return False
    if days is None:
        days = recheck_days()
    today = today or datetime.date.today()
    return (today - when).days > float(days)
