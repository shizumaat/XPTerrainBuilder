"""Census of the draped-orthophoto witness over installed packs (#1916, #2115).

Reads every pack of a mod cache (its cached tile-DSF dumps) against its
installed folder and runs the ENGINE's own witness — ``pack_drapes.
photo_layers`` (witness (1)-(6)) and ``pack_drapes.draped_orthos`` (the
grid rule and the whole-set rule: what the app offers to hide) — with the
engine's own airport boxes (``drape_stage._airports``) and dump pick
(``dsf.find_text_dump`` of the pristine DSF).  It decides nothing itself.

Per pack it prints the photo definitions passing (1)-(6), the definitions
offered for hiding, and — for the reader's check only, by NAME — how many
of the passing ones are named like a weathering decal (dirt, skid, tyre,
oil, shadow …): the engine never reads a name.

``--src DIR`` imports the engine from another tree (a ``git archive`` of
the base ref), so one tool reads before and after:

    venv/bin/python tools/pack_drape_census.py --cache MOD_CACHE \\
        --scenery "~/X-Plane 12/Custom Scenery" --json after.json
    venv/bin/python tools/pack_drape_census.py ... --src /tmp/base/src \\
        --json before.json
    venv/bin/python tools/pack_drape_census.py --diff before.json after.json

Read-only: never runs DSFTool, never writes a pack.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

_DECAL = re.compile(r"dirt|skid|tyre|tire|rubber|oil|shadow|crack|grime|"
                    r"stain|weather|decal|patch|wear", re.I)


def _engine(src: str):
    sys.path.insert(0, src)
    from auto_patch import drape_stage as ds
    from auto_patch_v2.airport import dsf, dsf_write, pack_drapes
    return ds, dsf, dsf_write, pack_drapes


def _tiles(cache_dir: str) -> set[tuple[int, int]]:
    out = set()
    for f in os.listdir(cache_dir):
        m = re.match(r"([+-]\d\d)([+-]\d\d\d)\.dsf\..*text$", f)
        if m:
            out.add((int(m.group(1)), int(m.group(2))))
    return out


def census(cache: str, scenery: str, src: str) -> dict:
    ds, dsf, dsf_write, pd = _engine(src)
    rows: dict = {}
    for name in sorted(os.listdir(cache)):
        pack = os.path.join(scenery, name)
        cdir = os.path.join(cache, name)
        if not (os.path.isdir(pack) and os.path.isdir(cdir)):
            continue
        for lat, lon in sorted(_tiles(cdir)):
            dsf_path = dsf.dsf_path_in_pack(pack, lat, lon)
            if not os.path.isfile(dsf_path):
                continue
            pristine = dsf_write.pristine_dsf_path(dsf_path)
            dump = dsf.find_text_dump(cache, name, lat, lon, pristine)
            if not dump:
                continue
            areas, bounded, _apts = ds._airports(pack, lat, lon)
            if not areas:
                continue
            try:
                pl = pd.photo_layers(pack, dump, areas)
                hidden = pd.draped_orthos(pack, dump, areas, bounded=bounded)
            except Exception as exc:                       # one bad pack
                rows[f"{name}|{lat:+03d}{lon:+04d}"] = {"error": str(exc)}
                continue
            wit = [ly for ly in pl.layers if ly.witness]
            rows[f"{name}|{lat:+03d}{lon:+04d}"] = {
                "layers": len(pl.layers), "witness": len(wit),
                "decal_named": sorted(ly.path for ly in wit
                                      if _DECAL.search(ly.path + " " + ly.texture)),
                "hidden": len(hidden),
                "hidden_uses": sum(m.uses for m in hidden)}
    return rows


def diff(before: dict, after: dict) -> None:
    keys = sorted(set(before) | set(after))
    tot = {"wb": 0, "wa": 0, "hb": 0, "ha": 0, "db": 0, "da": 0}
    print(f"{'pack|tile':70s} {'wit b→a':>10s} {'hid b→a':>10s} {'decal b→a':>10s}")
    for k in keys:
        b, a = before.get(k, {}), after.get(k, {})
        wb, wa = b.get("witness", 0), a.get("witness", 0)
        hb, ha = b.get("hidden", 0), a.get("hidden", 0)
        db, da = len(b.get("decal_named", ())), len(a.get("decal_named", ()))
        for t, v in zip(("wb", "wa", "hb", "ha", "db", "da"),
                        (wb, wa, hb, ha, db, da), strict=True):
            tot[t] += v
        if (wb, hb, db) != (wa, ha, da):
            print(f"{k[:70]:70s} {wb:4d}→{wa:<5d} {hb:4d}→{ha:<5d} {db:4d}→{da:<5d}")
            for p in sorted(set(a.get("decal_named", ())) - set(b.get("decal_named", ()))):
                print(f"    + decal-named witness: {p}")
    print(f"TOTAL ({len(keys)} pack tiles): witness {tot['wb']}→{tot['wa']}, "
          f"offered {tot['hb']}→{tot['ha']}, decal-named witness "
          f"{tot['db']}→{tot['da']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", help="mod cache root (one folder per pack)")
    ap.add_argument("--scenery", help="the Custom Scenery folder")
    ap.add_argument("--src", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
    ap.add_argument("--json", help="write the rows here")
    ap.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"))
    args = ap.parse_args(argv)
    if args.diff:
        with open(args.diff[0]) as f0, open(args.diff[1]) as f1:
            diff(json.load(f0), json.load(f1))
        return 0
    if not (args.cache and args.scenery):
        ap.error("--cache and --scenery are required")
    rows = census(args.cache, os.path.expanduser(args.scenery), args.src)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rows, fh, indent=1, sort_keys=True)
    ok = [r for r in rows.values() if "error" not in r]
    print(f"{len(rows)} pack tiles, {len(ok)} read: witness "
          f"{sum(r['witness'] for r in ok)}, offered "
          f"{sum(r['hidden'] for r in ok)} definitions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
