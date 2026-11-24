"""When a bathymetry provider's SOURCE changes, its recorded negatives expire.

``index.json`` keeps a durable ``no_coverage`` per cell.  That answer is
only as good as the source that gave it: GEBCO's dead mirror turned a
404 into "no data" on every cell it was asked for (#2265).  A provider
whose ``.elv`` declares ``source_revision=N`` says "answers recorded
before revision N are not evidence".  Reading a stamp through
:func:`healed_stamp` drops that provider's negatives and the settle
records that relied on them, so the next pass asks again, once.

Stamp keys (both absent on a stamp with nothing to say):

* ``source_revisions`` -- ``{code: N}``: the revision a provider's cells
  were last fully answered under.
* ``refetch`` -- codes with cells still to ask (a heal, or a pass that
  ended on a transient failure).
"""
from __future__ import annotations

from typing import Callable, Optional

__all__ = ["PENDING", "declared_revision", "healed_stamp", "provider_state"]

#: A step-key value: this provider still has cells to ask for.
PENDING = "pending"

_NO_COVERAGE = "no_coverage"


def declared_revision(definition: dict) -> int:
    """The ``source_revision`` of a provider definition; 0 when none."""
    try:
        return int(definition.get("source_revision", 0))
    except (TypeError, ValueError):
        return 0


def _recorded(stamp: dict) -> dict:
    revisions = stamp.get("source_revisions")
    return dict(revisions) if isinstance(revisions, dict) else {}


def _refetch(stamp: dict) -> list:
    codes = stamp.get("refetch")
    return list(codes) if isinstance(codes, list) else []


def _record_relies_on(record, code: str) -> bool:
    """Did this settle record walk ``code``?  A legacy record names only
    the provider it settled on."""
    if not isinstance(record, dict):
        return False
    reached = record.get("reached")
    if isinstance(reached, list):
        return code in reached
    return record.get("provider") == code


def healed_stamp(stamp: dict, definitions,
                 stem_provider: Callable[[str, list], Optional[str]]) -> dict:
    """``stamp`` with expired negatives removed; the same object when
    nothing expired, so an unaffected tile reads and writes as before."""
    expired = [
        d["code"] for d in definitions
        if declared_revision(d) > int(_recorded(stamp).get(d["code"], 0))
    ]
    if not expired or not isinstance(stamp.get("cells"), dict):
        return stamp
    cells = dict(stamp["cells"])
    stale = {
        stem: stem_provider(stem, expired) for (stem, outcome) in cells.items()
        if outcome == _NO_COVERAGE
    }
    stale = {stem: code for (stem, code) in stale.items() if code}
    if not stale:
        return stamp
    for stem in stale:
        del cells[stem]
    codes = set(stale.values())
    healed = dict(stamp)
    healed["cells"] = cells
    healed["refetch"] = sorted(set(_refetch(stamp)) | codes)
    gatings = stamp.get("gatings")
    if isinstance(gatings, dict):
        healed["gatings"] = {
            text: record for (text, record) in gatings.items()
            if not any(_record_relies_on(record, code) for code in codes)
        }
    elif stamp.get("provider") in codes:
        # A legacy stamp's one implied record relied on this provider.
        healed["gatings"] = {}
    return healed


def provider_state(previous: dict, definitions, passes: dict) -> tuple:
    """``(source_revisions, refetch)`` after this pass.  ``passes`` maps
    each provider walked to whether all its cells got an answer."""
    revisions = _recorded(previous)
    refetch = set(_refetch(previous))
    for definition in definitions:
        code = definition["code"]
        if code not in passes:
            continue
        revision = declared_revision(definition)
        if not revision:
            continue
        if passes[code]:
            revisions[code] = revision
            refetch.discard(code)
        else:
            refetch.add(code)
    return (revisions, sorted(refetch))
