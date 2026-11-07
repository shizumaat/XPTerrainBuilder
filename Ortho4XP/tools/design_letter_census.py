#!/usr/bin/env python3
"""THE RUNWAY DESIGN-LETTER CENSUS (owner RULINGS 2026-11-07a: "Census over
apt.dat before landing"; #1947).

Every runway of the Global Airports apt.dat and of every installed custom
pack's apt.dat is lettered twice by THE ENGINE'S OWN classifier
(``law/reference_code.runway_code_letter``, never a second implementation):
OLD = pavement width alone (``precision=None``), NEW = the 11-07a rule as
the loader reads it (``airport/approach.design_letter``: row-100 markings
cap, largest row-1301 ramp-start size class lifts, width breaks the tie,
the wide-runway floor, no witness = width).  For each it reads the zone-2 half-width the build would
take (``law/tables.zone2_half_width_m`` under the airport's own ruleset,
``law/airports_schema.resolve_ruleset``), the instrument status read off
the markings alone (no CIFP join: a CIFP-only ILS end reads non-precision
here, so the status column is a floor).

Prints counts by letter change and by zone-2 change, per source (global /
custom), and the rows of ``--spot`` airports.  ``--json OUT`` writes every
runway row.  Read-only, offline: only rows ``1``/``16``/``17``, ``100``,
``1300``, ``1301``, parsed by ``airport/apt_dat.parse_airport_block``.

    venv/bin/python tools/design_letter_census.py [--xplane-root DIR]
        [--spot ICAO ...] [--json OUT] [--no-custom]
"""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py`` (twin: ``tests/test_console_encoding.py``).
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import argparse  # noqa: E402
import collections  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import typing as _t  # noqa: E402

from auto_patch_v2.airport import apt_dat as A  # noqa: E402
from auto_patch_v2.airport.approach import (  # noqa: E402
    airport_ramp_class, design_letter, precision_markings)
from auto_patch_v2.law.airports_schema import resolve_ruleset  # noqa: E402
from auto_patch_v2.law.model import Law, load_tables  # noqa: E402
from auto_patch_v2.law.reference_code import (  # noqa: E402
    INSTRUMENT, NON_INSTRUMENT, PRECISION, runway_code_letter, runway_code_number)
from auto_patch_v2.law.tables import zone2_half_width_m  # noqa: E402

DEFAULT_XP = "/Users/noah/X-Plane 12"
_KEEP = frozenset((A.ROW_RUNWAY, A.ROW_STARTUP, A.ROW_STARTUP_ATTRS))
_HEADERS = frozenset((1, 16, 17))
_NPI_MARKINGS = frozenset((2, 4))


def airport_blocks(path: str) -> _t.Iterator[list[str]]:
    """Each airport block of ``path``, reduced to its header and the rows
    the letter reads (runways, ramp starts and their attributes)."""
    block: list[str] = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            head = line.split(None, 1)
            if not head or not head[0].isdigit():
                continue
            rt = int(head[0])
            if rt in _HEADERS:
                if block:
                    yield block
                block = [line.rstrip("\n")]
            elif block and rt in _KEEP:
                block.append(line.rstrip("\n"))
    if block:
        yield block


def _length_m(rw: A.AptRunway) -> float:
    (_, la1, lo1, *_), (_, la2, lo2, *_) = rw.ends
    k = math.pi * 6371008.8 / 180.0
    return math.hypot((lo2 - lo1) * k * math.cos(math.radians((la1 + la2) / 2)),
                      (la2 - la1) * k)


def _status(markings: tuple[int, int]) -> int:
    """The instrument status the markings alone witness."""
    if any(precision_markings(m) for m in markings):
        return PRECISION
    return INSTRUMENT if any(int(m) in _NPI_MARKINGS for m in markings) else NON_INSTRUMENT


def runway_rows(ap: A.AptAirport, law: Law, source: str) -> list[dict]:
    """One row per runway of ``ap``: old and new letter, zone-2 half-width."""
    ramp = airport_ramp_class(ap)
    out = []
    for rw in ap.runways:
        cn = runway_code_number(law, _length_m(rw))
        st = _status(rw.markings)
        old = runway_code_letter(law, rw.width_m)
        new = design_letter(law, rw, ramp)
        z = [zone2_half_width_m(law, "runway", cn, x, st) for x in (old, new)]
        out.append({"icao": ap.icao, "source": source, "rwy": "/".join(e[0] for e in rw.ends),
                    "ruleset": law.ruleset_key, "width_m": round(rw.width_m, 2),
                    "markings": list(rw.markings), "ramp_class": ramp, "code": cn,
                    "status": st, "old": old, "new": new,
                    "zone2_old_m": z[0], "zone2_new_m": z[1]})
    return out


def apt_files(xp: str, custom: bool) -> list[tuple[str, str]]:
    """``(source, path)``: the Global Airports apt.dat, then each pack's."""
    files = [("global", os.path.join(xp, "Global Scenery", "Global Airports",
                                     "Earth nav data", "apt.dat"))]
    if custom:
        files += [("custom", p) for p in sorted(glob.glob(os.path.join(
            glob.escape(xp), "Custom Scenery", "*", "Earth nav data", "apt.dat")))]
    return [(s, p) for s, p in files if os.path.isfile(p)]


def census(xp: str, custom: bool = True) -> list[dict]:
    """Every runway row of every apt.dat :func:`apt_files` names."""
    tables = load_tables(Law.default_dir())
    laws: dict[str, Law] = {}
    rows: list[dict] = []
    for source, path in apt_files(xp, custom):
        for block in airport_blocks(path):
            ap = A.parse_airport_block(block)
            if not ap.runways:
                continue
            rk = resolve_ruleset(tables.resolution, ap.icao)
            law = laws.setdefault(rk, Law(tables=tables, ruleset_key=rk))
            rows += runway_rows(ap, law, source)
    return rows


def summarise(rows: list[dict]) -> str:
    """Counts by letter change and zone-2 change, per source."""
    lines = []
    for src in sorted({r["source"] for r in rows}):
        rs = [r for r in rows if r["source"] == src]
        ch = [r for r in rs if r["old"] != r["new"]]
        zc = [r for r in rs if r["zone2_old_m"] != r["zone2_new_m"]]
        narrow = sum(1 for r in zc if (r["zone2_new_m"] or 0) < (r["zone2_old_m"] or 0))
        lines.append(f"[{src}] runways {len(rs)} at {len({r['icao'] for r in rs})} airports; "
                     f"letter changes {len(ch)}; zone-2 changes {len(zc)} "
                     f"(narrower {narrow}, wider {len(zc) - narrow})")
        by = collections.Counter(f"{r['old']}->{r['new']}" for r in ch)
        lines.append("  letter: " + ", ".join(f"{k} {v}" for k, v in by.most_common()))
        bz = collections.Counter(f"{r['ruleset']} {r['zone2_old_m']}->{r['zone2_new_m']}"
                                 for r in zc)
        lines.append("  zone-2 m: " + ", ".join(f"{k} {v}" for k, v in bz.most_common(12)))
        lines.append(f"  airports with a 1301 class: "
                     f"{len({r['icao'] for r in rs if r['ramp_class']})}")
    return "\n".join(lines)


def spot_line(r: dict) -> str:
    return (f"  {r['icao']:5} {r['source']:6} {r['rwy']:8} {r['ruleset']} w={r['width_m']} "
            f"mk={r['markings']} ramp={r['ramp_class']} code {r['code']} st {r['status']}: "
            f"{r['old']}->{r['new']}  zone2 {r['zone2_old_m']}->{r['zone2_new_m']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--xplane-root", default=DEFAULT_XP)
    ap.add_argument("--spot", nargs="*", default=[])
    ap.add_argument("--json")
    ap.add_argument("--no-custom", action="store_true")
    a = ap.parse_args(argv)
    rows = census(a.xplane_root, not a.no_custom)
    print(summarise(rows))
    want = {s.upper() for s in a.spot}
    for r in rows:
        if r["icao"] in want:
            print(spot_line(r))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
