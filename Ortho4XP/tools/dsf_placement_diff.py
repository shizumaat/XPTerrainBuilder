"""THE DRY RUN of the DSF placement edit — old line -> new line, writes
nothing (spec ``docs/specs/auto-patch-v2/object-placement-spec.md`` §3).

What it answers: *if we made every MSL/AGL placement of this pack sit on
the ground, which rows change, and to what?*  It is the instrument in
front of the writer (``auto_patch_v2.airport.dsf_write``), never a second
implementation of it: the tool builds a ``PlacementPlan``, runs the same
pure ``edit_dump`` the writer runs, and prints the rows that moved.

    venv/bin/python tools/dsf_placement_diff.py \\
        --dsf "/…/Custom Scenery/<pack>/Earth nav data/+30-100/+39-095.dsf" \\
        --pack-root "/…/Custom Scenery/<pack>" [--limit 20] [--json]

    venv/bin/python tools/dsf_placement_diff.py --dump <dump>.text \\
        --pack-root <pack> [--plan o4_v2_placement_KMCI.json]

With ``--plan`` the plan is READ instead of derived (the split half of
the spec, lane ``v2objsplit``, writes one); without it the §5 rule is
applied: every ``OBJECT_MSL`` / ``OBJECT_AGL`` placement converts — pack
and stock ``lib/…`` resources alike (owner RULINGS 2026-09-11d: a
placement edit modifies no object); nothing is kept at this step.

``--sweep-noop DIR`` (#23) is the CLASS instrument: every DSFTool dump
under DIR (``*.dsf*.text``, one per content tag) goes through the writer's
own NO-OP write — ``edit_dump`` with an EMPTY plan (only the §12a
ownership mark added), ``encode``, ``verify_roundtrip`` — in a TEMP dir,
and the failures are listed.  ``--raw`` runs the pre-#23 arm (plain
``DSFTool --text2dsf``, no property repair) for a before/after count.
Read-only on DIR; ``--max-mb`` skips dumps above a size (the long-row scan
it also prints covers every dump regardless).

    venv/bin/python tools/dsf_placement_diff.py --sweep-noop Airport_mod_cache \\
        [--raw] [--max-mb 20] [--jobs 6]

``--verify`` additionally encodes the edited text with DSFTool into a
TEMP directory and runs ``verify_roundtrip`` on it — still writing
nothing into the pack.  The tool never writes a pack at all; the writer
does, and refuses a live X-Plane install without an explicit opt-in.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

# v1 owns the DSFTool resolver (one implementation); v2 imports no v1
# module, so the binary is resolved HERE and passed down.

from auto_patch.dsf_reader import _dsftool_path                    # noqa: E402
from auto_patch_v2.airport import dsf as _dsf                      # noqa: E402
from auto_patch_v2.airport import dsf_write as _w                  # noqa: E402
from auto_patch_v2.model.placement import (PlacementPlan,          # noqa: E402
                                           Provenance)


def build_plan(dump_obj, dump_text_path: str, dsf_path: str, pack_root: str,
               icao: str) -> PlacementPlan:
    conversions, kept = _w.conversions_for_dump(dump_obj, pack_root)
    return PlacementPlan(
        icao=icao, pack_name=os.path.basename(pack_root.rstrip("/")),
        pack_root=pack_root, dsf_path=dsf_path,
        dsf_backup_path=dsf_path + ".anchor_bak",
        provenance=Provenance(dump_sha="", engine_version="", law_digest=""),
        conversions=tuple(conversions), kept=tuple(kept))


def _noop_one(args: tuple[str, str, bool]) -> dict:
    """One dump through the writer's no-op write (``--sweep-noop``)."""
    import shutil
    path, tool, raw = args
    tmp = tempfile.mkdtemp(prefix="o4_dsf_noop_")
    try:
        with open(path, "r", encoding="utf-8", errors="surrogateescape") as fh:
            text = fh.read()
        long_rows = sum(1 for ln in text.splitlines()
                        if len(ln) > _w.DSFTOOL_LINE_MAX
                        and not ln.startswith("#"))
        plan = PlacementPlan(
            icao="", pack_name="", pack_root="", dsf_path="",
            dsf_backup_path="",
            provenance=Provenance(dump_sha="", engine_version="", law_digest=""),
            conversions=(), kept=())
        edited = _w.edit_dump(text, plan, "noop-sweep")
        etext = os.path.join(tmp, "e.text")
        out = os.path.join(tmp, "e.dsf")
        with open(etext, "w", encoding="utf-8", errors="surrogateescape",
                  newline="\n") as fh:
            fh.write(edited)
        if raw:
            _w._run([tool, "--text2dsf", etext, out])
        else:
            _w.encode(etext, out, tool)
        rep = _w.verify_roundtrip(out, edited, tool)
        return {"dump": path, "ok": rep.ok, "long_rows": long_rows,
                "findings": list(rep.findings[:3])}
    except Exception as exc:                          # noqa: BLE001
        return {"dump": path, "ok": False, "long_rows": -1,
                "findings": [f"{type(exc).__name__}: {str(exc)[:300]}"]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sweep_noop(root: str, tool: str, *, raw: bool = False,
               max_mb: float = 0.0, jobs: int = 4) -> dict:
    """``--sweep-noop``: the no-op round trip over every dump under
    ``root``, deduplicated by (folder, content tag)."""
    import re
    from concurrent.futures import ProcessPoolExecutor
    tag_re = re.compile(r"\.([0-9a-f]{8})\.text$")
    seen: dict[tuple[str, str], str] = {}
    skipped = []
    for d, _subs, files in os.walk(root, followlinks=True):
        for f in sorted(files):
            if ".dsf" not in f or not f.endswith(".text"):
                continue
            p = os.path.join(d, f)
            m = tag_re.search(f)
            key = (d, m.group(1)) if m else (d, f)
            if key in seen:
                continue
            if max_mb and os.path.getsize(p) > max_mb * 1e6:
                skipped.append(p)
                continue
            seen[key] = p
    work = [(p, tool, raw) for p in sorted(seen.values())]
    with ProcessPoolExecutor(max_workers=max(1, jobs)) as ex:
        results = list(ex.map(_noop_one, work))
    fails = [r for r in results if not r["ok"]]
    return {"root": root, "arm": "raw" if raw else "encode",
            "dumps": len(results), "failed": len(fails),
            "skipped_over_max_mb": len(skipped), "failures": fails}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsf", help="the pack DSF (dumped into a temp dir)")
    ap.add_argument("--dump", help="an existing DSFTool text dump")
    ap.add_argument("--pack-root")
    ap.add_argument("--sweep-noop", metavar="DIR",
                    help="no-op round trip of every dump under DIR (#23)")
    ap.add_argument("--raw", action="store_true",
                    help="--sweep-noop: plain DSFTool encode (the pre-#23 arm)")
    ap.add_argument("--max-mb", type=float, default=0.0,
                    help="--sweep-noop: skip dumps larger than this")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--plan", help="a PlacementPlan JSON to apply instead of §5")
    ap.add_argument("--icao", default="")
    ap.add_argument("--limit", type=int, default=20,
                    help="rows to print per class (0 = all)")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--verify", action="store_true",
                    help="encode into a TEMP dir and verify the round trip")
    ap.add_argument("--dsftool", default=None,
                    help="DSFTool binary (default: the bundled one v1 resolves)")
    a = ap.parse_args(argv)
    if a.sweep_noop:
        rep = sweep_noop(a.sweep_noop, a.dsftool or _dsftool_path(), raw=a.raw,
                         max_mb=a.max_mb, jobs=a.jobs)
        if a.json:
            print(json.dumps(rep, indent=1, sort_keys=True))
        else:
            print(f"arm {rep['arm']}: {rep['dumps']} dumps, {rep['failed']} failed, "
                  f"{rep['skipped_over_max_mb']} skipped (> --max-mb)")
            for r in rep["failures"]:
                print(f"  FAIL {r['dump']} (long rows {r['long_rows']})")
                for f in r["findings"]:
                    print(f"       {f[:240]}")
        return 1 if rep["failed"] else 0
    if not a.pack_root:
        ap.error("--pack-root is required")
    if not a.dsf and not a.dump:
        ap.error("one of --dsf / --dump is required")

    tool = a.dsftool or _dsftool_path()
    tmp = tempfile.mkdtemp(prefix="o4_dsf_diff_")
    dump_path = a.dump
    if dump_path is None:
        # the ONE resolver (11m): a DSF the object stage has written
        # carries its own bodies; the pristine backup beside it is what
        # a plan is derived from.
        dump_path = _w.dump(_w.pristine_dsf_path(a.dsf),
                            os.path.join(tmp, "pristine.text"), tool)
    with open(dump_path, "r", errors="replace") as fh:
        text = fh.read()
    dump_obj = _dsf.read_dump(dump_path)

    if a.plan:
        with open(a.plan) as fh:
            plan = PlacementPlan.from_json(fh.read())
    else:
        plan = build_plan(dump_obj, dump_path, a.dsf or "", a.pack_root, a.icao)

    lines = text.splitlines()
    rows = {o: (i, toks) for o, i, toks in _w.placement_rows(
        [ln + "\n" for ln in lines])}
    edited = _w.edit_dump(text, plan)

    per_resource: dict[str, int] = {}
    changes = []
    for c in plan.conversions:
        i, toks = rows[c.index]
        per_resource[c.resource] = per_resource.get(c.resource, 0) + 1
        hdg = toks[5] if len(toks) > 5 else "0.000000"
        changes.append({"index": c.index, "line": i + 1, "resource": c.resource,
                        "old": " ".join(toks),
                        "new": " ".join(("OBJECT", toks[1], toks[2], toks[3], hdg))})
    kept_by_reason: dict[str, int] = {}
    for k in plan.kept:
        kept_by_reason[k.reason] = kept_by_reason.get(k.reason, 0) + 1

    report = {"dump": dump_path, "counts": plan.counts(),
              "placements": len(dump_obj.placements),
              "per_resource": per_resource, "kept_by_reason": kept_by_reason,
              "lines_before": len(lines), "lines_after": len(edited.splitlines())}

    if a.verify:
        out = os.path.join(tmp, "edited.dsf")
        etext = os.path.join(tmp, "edited.text")
        with open(etext, "w") as fh:
            fh.write(edited)
        _w.encode(etext, out, tool)
        rep = _w.verify_roundtrip(out, edited, tool)
        report["roundtrip"] = rep.to_dict()

    if a.json:
        report["changes"] = changes
        print(json.dumps(report, indent=1, sort_keys=True))
        return 0

    print(f"dump              {dump_path}")
    print(f"placements        {len(dump_obj.placements)}")
    for k, v in sorted(plan.counts().items()):
        print(f"  {k:<18}{v}")
    print("per resource (conversions):")
    for r, n in sorted(per_resource.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {n:>6}  {r}")
    if kept_by_reason:
        print("kept:")
        for r, n in sorted(kept_by_reason.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>6}  {r}")
    lim = len(changes) if a.limit <= 0 else a.limit
    print(f"rows (first {min(lim, len(changes))} of {len(changes)}):")
    for c in changes[:lim]:
        print(f"  L{c['line']}  {c['old']}")
        print(f"  {'':>{len(str(c['line'])) + 3}}-> {c['new']}")
    print(f"lines {report['lines_before']} -> {report['lines_after']}")
    if "roundtrip" in report:
        r = report["roundtrip"]
        print(f"roundtrip ok={r['ok']} placements={r['placements']} "
              f"unmatched={r['unmatched']} max_deg={r['max_deg']:.3g} "
              f"max_hdg={r['max_heading_deg']:.4g} max_elev_m={r['max_elev_m']:.4g}")
        for f in r["findings"]:
            print("  finding:", f)
        return 0 if r["ok"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
