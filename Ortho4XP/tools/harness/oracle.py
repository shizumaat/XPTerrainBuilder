"""THE CONSTANT-DEM ORACLE RUNNER — the pair build with no terrain confound.

    venv/bin/python tools/harness/oracle.py ICAO [--worlds 1 10000]
        [--out DIR] [--allow-degraded-dem]

Run it from ``Ortho4XP/``.  Wraps ``auto_patch.constant_dem`` and drives the
three assertions the owner's oracle law makes (RULINGS 2026-08-05, "DEM is a
SEED"):

1. **COMPLIANCE** — zero ADJUDICATED law-true rows in BOTH worlds.  Necessary,
   weakest.  A surface can be lawful and still be authored by something other
   than the law.  ADJUDICATED excludes the VERSION-DEFERRED classes per owner
   ruling RULINGS ``d48bc0a`` ("flat-world zero is … zero adjudicated rows
   EXCLUDING the version-deferred classes, which appear in every report under
   their own heading") — those rows are still measured, still printed, and
   carried in the verdict under ``version_deferred_by_world``.  The register
   is ``check_grade.VERSION_DEFERRED_FAMILIES``.
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


def _analytic_band(layout):
    """The ANALYTIC reach band for ``layout``, or ``None``.

    ``building_feasibility.reach_band_unified`` — the cap-Dijkstra from the
    runway anchors over the unified grade graph.  This is the band the
    SOLVER bound nodes with and the band ``grade_graph_validate.
    route_band_violations`` confirms against, so assertion 2 reads one law
    rather than minting a second opinion about it.

    Why it is the right supplier and the pair is not: the band-width field
    is the two worlds differenced, so testing "is the node at the pair's
    edge" is circular — it is true by construction.  This band is derived
    from anchors, caps and geometry ALONE, none of which the DEM touches,
    so it is identical in both worlds and genuinely independent of the seed.

    Returns a callable ``band_of((x, y)) -> (floor, ceiling) | None``, or
    ``None`` when no band exists at all (no anchors / no pavement / the
    raster grid refused).  ``None`` is reported as NOT EVALUATED — never as
    a pass, which is the failure mode this whole item is repairing.

    THE ADAPTER IS DELIBERATE.  The engine's contract is ``band(x, y)``
    (two positional arguments); the reader's is ``band_of(xy)`` (one point,
    because ``_node_values`` hands it a coordinate).  Adapting HERE, at the
    single place the two meet, is the whole of the impedance mismatch — the
    alternative, teaching the reader to try both call shapes, is a
    dual-contract that would hide the next supplier's signature error the
    same way the key-shape bug hid this assertion for the whole campaign.
    """
    try:
        from auto_patch import grade_graph as GG
        from auto_patch.elevation_per_surface.solver_primitives import (
            _build_node_list)
        from auto_patch.elevation_per_surface.building_feasibility import (
            reach_band_unified)
        nodes, b2i = _build_node_list(layout)
        if not nodes:
            return None
        band = reach_band_unified(layout, GG.build_unified_graph(layout, b2i))
        if band is None:
            return None
        return lambda xy: band(xy[0], xy[1])
    except Exception as exc:                              # pragma: no cover
        print(f"  [harness] analytic band unavailable: {exc!r}")
        return None


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
        band_width_summary, saturation_report, saturation_summary,
        write_band_width_artifact)

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
    # ADJUDICATED, not instrument-zero (owner rulings: 2026-08-02 "the goal
    # is LAW COMPLIANCE, not instrument-zero", and RULINGS d48bc0a, which
    # states flat-world zero IS "zero adjudicated rows EXCLUDING the
    # version-deferred classes, which appear in every report under their
    # own heading").  This verdict used to read ``lawtrue.total``, i.e. it
    # tested instrument-zero and could never pass while a deferred class
    # existed; the deferred rows are still REPORTED here, under their own
    # key, and the census carries the same split from the same register
    # (``check_grade.VERSION_DEFERRED_FAMILIES`` /
    # ``check_grade.adjudication`` — one implementation, no hand
    # subtraction).
    verdicts = {}
    adjs = {w: censuses[w]["adjudication"] for w in worlds}
    non_compliant = {w: adjs[w]["adjudicated_total"] for w in worlds
                     if adjs[w]["adjudicated_total"]}
    verdicts["compliance"] = {
        "pass": not non_compliant,
        "ruling": cg.DEFERRED_ADJUDICATION_RULING,
        "adjudicated_by_world": {f"{w:g}": adjs[w]["adjudicated_total"]
                                 for w in worlds},
        "rows_by_world": {f"{w:g}": censuses[w]["lawtrue"]["total"]
                          for w in worlds},
        "version_deferred_by_world": {
            f"{w:g}": {"total": adjs[w]["deferred_total"],
                       "families": {k: d["n"] for k, d
                                    in adjs[w]["deferred_families"].items()}}
            for w in worlds},
        "version_deferred_why": {
            k: d["why"] for k, d
            in adjs[worlds[0]]["deferred_families"].items()},
        "note": ("zero ADJUDICATED law-true rows in every constant world "
                 "(version-deferred classes excluded per RULINGS "
                 f"{cg.DEFERRED_ADJUDICATION_RULING} and reported under "
                 "'version_deferred_by_world')" if not non_compliant else
                 "a constant-DEM build emitted ADJUDICATED rows: with no "
                 "terrain signal these are law, solver or instrument "
                 "defects — there is nothing to blame them on.  The "
                 "version-deferred classes are excluded from this verdict "
                 f"per RULINGS {cg.DEFERRED_ADJUDICATION_RULING} and listed "
                 "separately"),
    }
    for w in worlds:
        a = adjs[w]
        prog.note(f"  world {w:g}: ADJUDICATED {a['adjudicated_total']} "
                  f"(airside {a['adjudicated_by_side']['airside']}) + "
                  f"VERSION-DEFERRED {a['deferred_total']} "
                  f"[RULINGS {a['ruling']}] = law-true "
                  f"{censuses[w]['lawtrue']['total']}")
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
        prog.note(f"  band width: {json.dumps(summary)}  "
                  f"pinned={pinned}/{len(keys)}")

        # ── ASSERTION 2: EXTREME-SEATING SATURATION ──────────────────
        # NOW ACTUALLY EVALUATED (fix cycle 2 item 3).  This block used to
        # report pinned/free COUNTS off the band-width field and call that
        # saturation.  It is not: the band-width field IS the pair, so
        # "seated at the pair's own edge" is true by construction and says
        # nothing.  The assertion needs an INDEPENDENT band, and the engine
        # already publishes one — ``reach_band_unified``, the cap-Dijkstra
        # from the runway anchors, whose contract is coordinate-keyed
        # (``band(x, y) -> (floor, ceiling) | None``) and joins the reader
        # without any index or proximity hazard.  It is the SAME band the
        # solver bound the nodes with and the validator confirms against,
        # so a node off its edge is a disagreement inside one law, not
        # between two instruments.
        sat: dict = {"shared_nodes": len(keys), "pinned_nodes": pinned,
                     "free_nodes": len(keys) - pinned,
                     "pinned_pct": round(100.0 * pinned / max(1, len(keys)),
                                         1)}
        for world_name, w in (("plateau", lo), ("canyon", hi)):
            layout = layouts[w]["_layout"]
            band = _analytic_band(layout)
            if band is None:
                sat[world_name] = {"evaluated": False,
                                   "why": "no reach band could be built for "
                                          "this layout (no anchors, no "
                                          "pavement, or the grid refused) — "
                                          "assertion 2 is NOT EVALUATED, "
                                          "which is not a pass"}
                prog.note(f"  saturation {world_name}: NOT EVALUATED "
                          f"(no analytic band)")
                continue
            rows = saturation_report(layout, world_name, band)
            rep = saturation_summary(rows)
            rep["evaluated"] = True
            sat[world_name] = rep
            (out / f"{args.icao}_{world_name}_saturation.json").write_text(
                json.dumps({"world": world_name,
                            "rows": [r.as_dict() for r in rows]}, indent=1))
            top = ", ".join(f"{a['author']}={a['n']}"
                            f"(worst {a['worst_off_edge_m']:+.2f} m)"
                            for a in rep["by_author"][:5]) or "none"
            prog.note(f"  saturation {world_name}: {rep['unsaturated']} "
                      f"unsaturated node(s) across {rep['authors']} "
                      f"author(s) — {top}")
        evaluated = [v for k, v in sat.items()
                     if k in ("plateau", "canyon") and isinstance(v, dict)]
        sat["pass"] = bool(evaluated) and all(
            v.get("evaluated") and v.get("unsaturated", 1) == 0
            for v in evaluated)
        sat["note"] = ("every free node must sit at the band edge nearest "
                       "its seed; an unsaturated node is held by something "
                       "that is not the seed, and its AUTHOR is named in "
                       "<ICAO>_<world>_saturation.json")
        verdicts["saturation"] = sat

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
