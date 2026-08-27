"""NO-STEP TERM SPLIT — read the ``airside_no_step`` census family's two
terms apart.

WHY IT EXISTS.  RULINGS 2026-08-27 states ONE law as a PAIR of bounds —
"the runway-style grade + curvature pair" — and the spec registers them
as ONE census family, because they are one law over one population.  But
an A/B has to read them apart: the §1.1 direct-distance term prices a
SIDECAR-PUBLISHED edge list that only exists in a post-law build (so its
rows are pure un-blinding, never a regression), while the §1.2
rate-of-change term prices the emitted membrane's own polylines in both
arms (so ITS delta is a real before/after).  A single family count mixes
a new instrument's first reading with a genuine surface delta, which is
the two-instruments-one-population trap in its usual costume.

It also splits the §1.1 term by whether the SOLVE built to the pair:
spec Amendment 1 ruling 1 makes a tier2<->tier2 pair CENSUS-PRICED but
NOT solver-imposed (report-first, a profile-law docket), so those rows
must never be read as "a constraint the projection failed to meet".

**IT COUNTS NOTHING.**  Every row is read verbatim out of a
``tools/harness/census.py --rows-json`` dump — the only instrument in
this repo that produces defect counts — and the published edge list out
of the patch's own ``.axes.json``.

THE TERM DISCRIMINATOR IS STRUCTURAL, not a guess: a §1.1 row is priced
against a PUBLISHED BUDGET, so ``check_grade._check_published_law_edges``
fills ``cap_pct`` (= budget / distance); the §1.2 rate reader compares a
grade CHANGE against a rate and has no cap to state, so its rows carry
``cap_pct = None``.

    venv/bin/python tools/no_step_term_split.py ROWS.json PATCH.osm.axes.json
        [--json OUT.json]

Twin: ``tests/test_no_step_term_split.py``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

#: The family this tool splits.  ONE spelling, the census's own.
FAMILY = "airside_no_step"


def is_pair_row(row) -> bool:
    """True for a §1.1 DIRECT-DISTANCE row (see the discriminator note
    in the module docstring)."""
    return row.get("cap_pct") is not None


def split(rows_path, sidecar_path=None) -> dict:
    """The library entry.  ``sidecar_path`` is optional: without it the
    published-edge and imposed/report-first counts are ``None`` rather
    than guessed."""
    data = json.loads(Path(rows_path).read_text())
    rows = data.get("rows", data) if isinstance(data, dict) else data
    fam = [r for r in rows if r.get("family") == FAMILY]
    out = {"rows_json": str(rows_path), "family": FAMILY,
           "rows": len(fam),
           "published_edges": None, "published_imposed": None,
           "published_census_only": None,
           "grade_rows": 0, "grade_worst_de_m": 0.0,
           "rate_rows": 0, "rate_worst_de_m": 0.0}
    for r in fam:
        de = abs(float(r.get("de_m") or r.get("magnitude_m") or 0.0))
        if is_pair_row(r):
            out["grade_rows"] += 1
            out["grade_worst_de_m"] = max(out["grade_worst_de_m"], de)
        else:
            out["rate_rows"] += 1
            out["rate_worst_de_m"] = max(out["rate_worst_de_m"], de)
    if sidecar_path:
        side = json.loads(Path(sidecar_path).read_text())
        pub = side.get("airside_no_step_edges")
        if pub is not None:
            out["published_edges"] = len(pub)
            # ``imposed`` is absent on a patch built before Amendment 1;
            # reported as None rather than assumed either way.
            if pub and "imposed" in pub[0]:
                out["published_imposed"] = sum(
                    1 for r in pub if r.get("imposed"))
                out["published_census_only"] = (
                    len(pub) - out["published_imposed"])
    return out


def _print(res):
    pub = res["published_edges"]
    line = f"{Path(res['rows_json']).name}: {res['family']} rows=" \
           f"{res['rows']}"
    if pub is not None:
        line += f"  published edges={pub}"
        if res["published_imposed"] is not None:
            line += (f" ({res['published_imposed']} solver-imposed, "
                     f"{res['published_census_only']} census-only)")
    print(line)
    print(f"  §1.1 DIRECT-DISTANCE rows = {res['grade_rows']}  worst |de| "
          f"{res['grade_worst_de_m']:.3f} m")
    print(f"  §1.2 RATE-OF-CHANGE  rows = {res['rate_rows']}  worst |de| "
          f"{res['rate_worst_de_m']:.3f} m")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Split the airside_no_step census family into its "
                    "§1.1 grade and §1.2 rate terms.  It counts nothing: "
                    "every row is read verbatim from a census dump.")
    ap.add_argument("rows_json", help="tools/harness/census.py --rows-json")
    ap.add_argument("sidecar", nargs="?", help="PATCH.osm.axes.json")
    ap.add_argument("--json", dest="json_out")
    a = ap.parse_args(argv)
    res = split(a.rows_json, a.sidecar)
    _print(res)
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
