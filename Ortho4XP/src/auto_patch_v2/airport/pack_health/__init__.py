"""THE PACK HEALTH CHECK (issue #1978): known vendor defects that hurt the
sim, repaired automatically in our output of an airport pack and always
reported.

Owner (2026-11-09): "file that with the bad light issue from LFKC as
something to check for and fix when we process a package."  Health, not
taste: unlike "Optimise pack" (#1707) nothing is asked — every write of
a pack DSF (``dsf_write.write_pack``) applies every class to the dump of
the PRISTINE file, the vendor original stays as ``.anchor_bak`` (the
objects' never change), and Restore originals puts the pack back.  Each
repair is one build-log line and a count on the pack's row.

THE CLASSES, one module each (a new class is a new module here, applied
by :func:`repair_polygons` / :func:`repair_objects` or a sibling of them
that ``dsf_write`` calls):

* ``light_records`` / ``objects`` — a malformed ``LIGHT_*`` record in a
  pack object (wrong arity; LFKC, #1954): completed or dropped in our
  copy of the object, which the DSF names.
* ``stacked_polygons`` — exact duplicate and stacked sliver line and
  draped-polygon placements (CYYC, #1975): dropped from the DSF.

The record row (:data:`RECORD_KEY`, beside the DSF) says what the last
write repaired, for the pristine file it was written from
(:func:`recorded`), so the object stage knows when a pack still needs
the write (``auto_patch.health_stage``).
"""
from __future__ import annotations

import typing as _t

from . import objects as _ob
from . import stacked_polygons as _sp

__all__ = ["RECORD_KEY", "VERSION", "Health", "repair_polygons",
           "repair_objects", "record", "recorded", "generated_of", "count",
           "log_lines"]

#: the key of the record row (``o4_placement_provenance.json``)
RECORD_KEY = "pack_health"
#: the rules' version: a row written under another is not current, so a
#: new class reaches packs repaired before it
VERSION = 1


class Health(_t.NamedTuple):
    """What one write repaired."""

    polygons: _sp.Report | None
    lights: dict                  # {declared path: findings}

    @property
    def empty(self) -> bool:
        return not (self.polygons and self.polygons.dropped) and not self.lights


def repair_polygons(text: str) -> tuple[str, _sp.Report]:
    """The dump without its duplicate and stacked draped placements —
    applied BEFORE any definition is renumbered (the omission), so a
    definition left with no row is dropped with the others."""
    return _sp.repair_text(text)


def repair_objects(text: str, pack_root: str) -> tuple[str, dict, list[str]]:
    """The dump naming a repaired copy of every placed pack object with a
    malformed light record — applied LAST, to the rows still naming the
    vendor file — the findings, and the copies written (pack-relative)."""
    broken = _ob.broken_objects(pack_root, text)
    if not broken:
        return text, {}, []
    files = _ob.write_copies(pack_root, broken)
    text, _n = _ob.rename_rows(text, broken)
    return text, broken, files


def record(pristine_sha256: str, health: Health, generated: _t.Sequence[str],
           stamp: str) -> dict | None:
    """The record row of a write, or ``None`` when it repaired nothing."""
    if health.empty:
        return None
    p = health.polygons
    lights = {path: {"completed": sum(f.action == "completed" for f in fs),
                     "dropped": sum(f.action == "dropped" for f in fs)}
              for path, fs in sorted(health.lights.items())}
    top = sorted((p.by_def if p else {}).items(), key=lambda kv: -kv[1])[:5]
    return {"backup_sha256": pristine_sha256, "version": VERSION,
            "time": stamp,
            "polygons": {"dropped": p.dropped if p else 0,
                         "duplicates": p.duplicates if p else 0,
                         "stacked": p.stacked if p else 0,
                         "site": list(p.site) if p and p.site else [],
                         "by_def": dict(top)},
            "lights": lights, "generated": sorted(generated)}


def recorded(entry: _t.Mapping[str, _t.Any] | None,
             pristine_sha256: str) -> dict:
    """The row the last write recorded, when it was written from this
    pristine file under these rules; ``{}`` otherwise."""
    row = (entry or {}).get(RECORD_KEY)
    if (isinstance(row, dict) and row.get("backup_sha256") == pristine_sha256
            and row.get("version") == VERSION):
        return row
    return {}


def generated_of(entry: _t.Mapping[str, _t.Any] | None) -> list[str]:
    """The copies a DSF's record says the last write named."""
    row = (entry or {}).get(RECORD_KEY)
    files = row.get("generated") if isinstance(row, dict) else None
    return [f for f in (files or ()) if isinstance(f, str)]


def count(row: _t.Mapping[str, _t.Any] | None) -> int:
    """The repairs a row records: placements dropped + light records
    repaired (the pack row's number)."""
    if not isinstance(row, dict):
        return 0
    polys = (row.get("polygons") or {}).get("dropped", 0) or 0
    lights = sum(int(v.get("completed", 0)) + int(v.get("dropped", 0))
                 for v in (row.get("lights") or {}).values()
                 if isinstance(v, dict))
    return int(polys) + lights


def log_lines(pack_name: str, dsf: str, row: _t.Mapping[str, _t.Any]
              ) -> list[str]:
    """The build-log lines of a recorded row: one per class repaired."""
    out: list[str] = []
    p = row.get("polygons") or {}
    if p.get("dropped"):
        site = p.get("site") or []
        where = (f"; {site[2]:,} of them piled at {site[0]:.4f}, {site[1]:.4f}"
                 if len(site) == 3 and site[2] > 1 else "")
        names = ", ".join(k.rsplit("/", 1)[-1] for k in (p.get("by_def") or {}))
        out.append(f"  [pack health] {pack_name}: {dsf}: removed "
                   f"{p['dropped']:,} duplicate or stacked line/polygon "
                   f"placement(s) ({p.get('duplicates', 0):,} exact repeats, "
                   f"{p.get('stacked', 0):,} slivers in a pile{where}; "
                   f"{names})")
    for path, n in sorted((row.get("lights") or {}).items()):
        out.append(f"  [pack health] {pack_name}: {path}: "
                   f"{n.get('completed', 0)} malformed light record(s) "
                   f"completed, {n.get('dropped', 0)} dropped — in our copy "
                   f"{_ob.copy_path(path)}")
    return out
