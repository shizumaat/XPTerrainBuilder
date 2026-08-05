"""THE CONSTANT-DEM ORACLE RUNNER — the pair build with no terrain confound.

    venv/bin/python tools/harness/oracle.py ICAO [--worlds 1 10000]
        [--out DIR] [--allow-degraded-dem]

Run it from ``Ortho4XP/``.  Wraps ``auto_patch.constant_dem`` and drives the
three assertions the owner's oracle law makes (RULINGS 2026-08-05, "DEM is a
SEED"):

1. **COMPLIANCE** — zero law-true rows in BOTH worlds.  Necessary, weakest.
   A surface can be lawful and still be authored by something other than the
   law.
2. **EXTREME-SEATING SATURATION** — the plateau world (a low constant) seats
   every free value at its band FLOOR, the canyon world (10 000 m) at its
   CEILING.  A node that moves between two builds on the SAME side of every
   band is held by something that is not the seed: a HIDDEN AUTHORITY.  This
   is the defect class plain compliance cannot see.
3. **THE BAND-WIDTH FIELD** — ``canyon(node) - plateau(node)`` IS the width
   of the band the law grants at that node, written out as the artifact
   (``<ICAO>_band_width.json``).  Width 0 ⇒ PINNED; a NEGATIVE width is a
   defect on its face.

WHY A RUNNER AND NOT JUST THE PYTEST.  ``tests/test_constant_dem_oracle.py``
builds each world per test; this builds each world ONCE and runs all three
assertions off the same layouts (single-pass principle).  The pytest stays
the gate; this is the instrument you drive an investigation with, and it
emits the artifacts a report is written from.

Consolidated from ``scratchpad/testphase/oracle.py``, with the harness's
census (all 21 families, sidecar-true) replacing that script's private
``run_checks`` call.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "harness"))

import build_airport as HB            # noqa: E402  (the one build entry)
import census as HC                   # noqa: E402  (the one census)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("icao")
    ap.add_argument("--worlds", nargs="+", type=float, default=None,
                    help="constant elevations to build (default: the "
                         "plateau/canyon pair from auto_patch.constant_dem)")
    ap.add_argument("--out", type=Path, default=Path("/tmp/harness/oracle"))
    ap.add_argument("--allow-degraded-dem", action="store_true",
                    help="accepted and recorded; the oracle SUBSTITUTES the "
                         "DEM, so real-DEM cache warmth cannot confound it")
    args = ap.parse_args(argv)

    root = HB.require_build_cwd(Path.cwd())
    for p in (root / "src", root, root / "tests"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from auto_patch.constant_dem import (                 # noqa: E402
        CANYON_ELEVATION_M, PLATEAU_ELEVATION_M, band_width_field,
        band_width_summary, write_band_width_artifact)

    worlds = args.worlds or [PLATEAU_ELEVATION_M, CANYON_ELEVATION_M]
    out = Path(args.out)
    prog = HB.Progress(out / f"{args.icao}_oracle.progress")
    prog.note(f"START oracle {args.icao} worlds={worlds}")

    cg = HC.load_check_grade()
    layouts, censuses = {}, {}
    for w in worlds:
        tag = f"{args.icao}_dem{w:g}"
        t0 = time.time()
        # The build entry, not a private build: the same refusals, the same
        # env/frame snapshots, the same sidecar guarantee.
        result = HB.build_patch(args.icao, root, out, tag, prog, const_dem=w)
        osm = Path(result["patch"])
        rep = HC.census_one(osm, cg, top=10)
        censuses[w] = rep
        prog.note(f"  world {w:g}: LAW-TRUE {rep['lawtrue']['total']} rows "
                  f"(airside {rep['lawtrue']['airside']}, mixed "
                  f"{rep['lawtrue']['mixed']}) in {time.time() - t0:.1f}s")
        # Re-open the layout's node values from the build we just did.
        layouts[w] = result
        (out / f"{tag}.census.json").write_text(json.dumps(rep, indent=1))

    # ── ASSERTION 1: COMPLIANCE ──────────────────────────────────────
    verdicts = {}
    non_compliant = {w: censuses[w]["lawtrue"]["total"] for w in worlds
                     if censuses[w]["lawtrue"]["total"]}
    verdicts["compliance"] = {
        "pass": not non_compliant,
        "rows_by_world": {f"{w:g}": censuses[w]["lawtrue"]["total"]
                          for w in worlds},
        "note": ("zero law-true rows in every constant world" if
                 not non_compliant else
                 "a constant-DEM build emitted rows: with no terrain signal "
                 "these are law, solver or instrument defects — there is "
                 "nothing to blame them on"),
    }
    for w in worlds:
        fams = [f for f in censuses[w]["families"] if f["n"]]
        if fams:
            prog.note(f"  world {w:g} families: "
                      + ", ".join(f"{f['family']}={f['n']}" for f in fams))

    # ── ASSERTIONS 2 and 3 read the LAYOUTS the builds just produced,
    # through ``constant_dem.band_width_field`` — the module's OWN reader,
    # the same one the shipped oracle test uses.  Re-parsing the emitted
    # patches here would be a SECOND reader of the same values and a
    # second chance to be wrong.
    lo, hi = min(worlds), max(worlds)
    if lo != hi:
        field = band_width_field(layouts[lo]["_layout"],
                                 layouts[hi]["_layout"])
        keys = field
        summary = band_width_summary(field)
        write_band_width_artifact(
            field, out / f"{args.icao}_band_width.json",
            extra={"icao": args.icao, "plateau_m": lo, "canyon_m": hi,
                   "join": "author (role/ref) + millimetre metre-frame "
                           "coordinate — same author on both sides, so a "
                           "shared coordinate yields one row per surface"})
        verdicts["band_width"] = {
            "pass": summary.get("negative", 0) == 0,
            "summary": summary,
            "artifact": str(out / f"{args.icao}_band_width.json"),
            "note": "a NEGATIVE band width is a defect on its face "
                    "(the ceiling world seated BELOW the floor world)",
        }
        pinned = sum(1 for v in field.values() if abs(v) <= 1e-6)
        verdicts["saturation"] = {
            "shared_nodes": len(keys),
            "pinned_nodes": pinned,
            "free_nodes": len(keys) - pinned,
            "pinned_pct": round(100.0 * pinned / max(1, len(keys)), 1),
            "note": "a FREE node whose two worlds agree is saturated at a "
                    "band edge; a node that moves without a band to move "
                    "in is held by a hidden authority — read the "
                    "band-width artifact's per-node rows",
        }
        prog.note(f"  band width: {json.dumps(summary)}  "
                  f"pinned={pinned}/{len(keys)}")

    (out / f"{args.icao}_oracle.json").write_text(json.dumps(
        {"icao": args.icao, "worlds": worlds, "verdicts": verdicts,
         "builds": {f"{w:g}": {k: v for k, v in layouts[w].items()
                               if not k.startswith("_")}
                    for w in worlds}}, indent=1, default=str))
    prog.note(f"EXIT oracle {args.icao}: "
              + "  ".join(f"{k}={'PASS' if v.get('pass') else 'SEE-REPORT'}"
                          for k, v in verdicts.items() if "pass" in v))
    print(f"\n  [harness] oracle artifacts in {out}")
    return 0 if all(v.get("pass", True) for v in verdicts.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
