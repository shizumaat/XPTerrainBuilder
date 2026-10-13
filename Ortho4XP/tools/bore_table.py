"""THE BORE TABLE — every mapped bore §34 (12) (5) was asked about, with its
witness readings and its verdict, and the diff of two arms.

    cd Ortho4XP && PYTHONPATH=src venv/bin/python tools/bore_table.py run ICAO --out DIR
    venv/bin/python tools/bore_table.py diff BASE_DIR BRANCH_DIR ICAO [ICAO ...] [--expect IDS ...]

``run`` is the dry structure replay (``python -m auto_patch_v2.planar ICAO
--stage structures --out DIR/ICAO``) with ``planar/structure_service.
terrain_tunnel_witness`` wrapped: each bore the engine asks is logged to
``DIR/ICAO.bores.json`` with its length, tags, ``layer``, classified cover,
rise over the mouth chord, fence membership, the pack building at each end and
the pack's open passage (``_PackBuildings.passage``) — the readings the
refusal line prints only for a REFUSED bore.  It measures no law and changes
no verdict.  ``diff`` prints one row per bore (base verdict -> branch verdict)
and exits non-zero when a verdict changed on a bore not named by ``--expect``.

Promoted on its second use (lane ``kclt546`` scratch ``bore_witness.py``, lane
``tunnel548``; RULINGS ``7e90032``).  Twin: ``tests/test_bore_table.py``.
"""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import argparse
import json
import os
import runpy
import sys
from pathlib import Path

__all__ = ["logged", "row_line", "diff", "main"]


def logged(service, rows: list, sink=None):
    """``service.terrain_tunnel_witness`` wrapped so every bore asked appends
    its readings to ``rows`` (and ``sink(rows)`` is called after each)."""
    from auto_patch_v2.planar.structure_approach import carriageway_width_m
    orig = service.terrain_tunnel_witness

    def wrapped(airport, law, on_field, osm_ways):
        inner = orig(airport, law, on_field, osm_ways)
        pack = service._PackBuildings(airport, law,
                                      getattr(on_field, "corridor_prints", ()) or (),
                                      getattr(on_field, "corridor_objects", ()) or ())
        to_ll = airport.frame.transformers()[1]
        tn = law.tables.structures.tunnel
        fence = service._fence_of(airport)

        def witness(bore):
            built, why = inner(bore)
            ln = bore.line
            width = max(carriageway_width_m(w.tags or {}, law) for w in bore.ways)
            over = pack.passage(ln, width, tn.terrain_cover_min_m)
            rise = service._rise_m(airport, ln)
            rows.append({
                "ids": "+".join(str(w.id) for w in bore.ways), "built": bool(built),
                "why": why, "len_m": round(ln.length, 1),
                "cover_m": round(on_field.cover_run_m(ln), 1),
                "layer": service._layer_of_bore(bore),
                "rise_m": None if rise is None else round(rise, 2),
                "mapped": service._osm_tunnel(bore, tn.admitted_values),
                "in_fence": bool(fence is not None and fence.covers(ln)),
                "ends_ll": [[round(c, 7) for c in to_ll(*bore.points[i])] for i in (0, -1)],
                "at_ends": [str(pack.at(bore.points[i])) for i in (0, -1)],
                "passage": None if over is None else [over[0], str(over[1]), round(over[2], 2)],
                "tags": [dict(w.tags or {}) for w in bore.ways]})
            if sink is not None:
                sink(rows)
            return built, why
        return witness
    return wrapped


def row_line(base: dict, branch: dict | None) -> str:
    """One table row: the base arm's readings and both verdicts."""
    verdict = lambda r: "BUILT" if r["built"] else "REFUSED"          # noqa: E731
    over = base["passage"]
    out = (f"  {base['ids']:<24} {base['len_m']:>7.1f} m  layer {base['layer']}  cover "
           f"{base['cover_m']}  rise {base['rise_m']}  passage "
           f"{'-' if not over else f'{os.path.basename(over[0])} @ {over[2]} m'}  | "
           f"{verdict(base)} [{base['why'][:72]}]")
    if branch is None:
        return out + "  -> (not asked)"
    out += f"  -> {verdict(branch)}"
    if branch["built"] != base["built"]:
        out += f"  *** CHANGED: {branch['why'][:240]}"
    return out


def diff(base_dir: Path, branch_dir: Path, icaos, expect=()) -> tuple[list[str], list[str]]:
    """``(lines, unexpected)`` — the table, and the bores whose verdict
    changed without being named in ``expect``."""
    lines: list[str] = []
    unexpected: list[str] = []
    for icao in icaos:
        arms = []
        for d in (base_dir, branch_dir):
            f = Path(d) / f"{icao}.bores.json"
            arms.append({r["ids"]: r for r in json.loads(f.read_text(encoding="utf-8"))} if f.exists() else {})
        lines.append(f"== {icao}: {len(arms[0])} bore(s) asked (base), {len(arms[1])} (branch)")
        for ids, row in arms[0].items():
            other = arms[1].get(ids)
            lines.append(row_line(row, other))
            if (other is None or other["built"] != row["built"]) and ids not in expect:
                unexpected.append(f"{icao} {ids}")
        unexpected += [f"{icao} {i} (branch only)" for i in arms[1] if i not in arms[0]]
    return lines, unexpected


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("icao")
    r.add_argument("--out", type=Path, required=True)
    d = sub.add_parser("diff")
    d.add_argument("base", type=Path)
    d.add_argument("branch", type=Path)
    d.add_argument("icaos", nargs="+")
    d.add_argument("--expect", nargs="*", default=[])
    a = ap.parse_args(argv)
    if a.cmd == "diff":
        lines, unexpected = diff(a.base, a.branch, a.icaos, set(a.expect))
        print("\n".join(lines))
        print("VERDICT: " + ("only the expected bores changed" if not unexpected
                             else "UNEXPECTED CHANGES: " + "; ".join(unexpected)))
        return 1 if unexpected else 0
    from auto_patch_v2.planar import structure_service
    a.out.mkdir(parents=True, exist_ok=True)
    log = a.out / f"{a.icao}.bores.json"
    log.write_text("[]", encoding="utf-8", newline="\n")
    structure_service.terrain_tunnel_witness = logged(
        structure_service, [], lambda rows: log.write_text(
            json.dumps(rows, indent=1), encoding="utf-8", newline="\n"))
    sys.argv = ["auto_patch_v2.planar", a.icao, "--stage", "structures",
                "--out", str(a.out / a.icao)]
    runpy.run_module("auto_patch_v2.planar", run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
