#!/usr/bin/env python3
"""HOW HEAVY IS AN AIRPORT PACK? (issue #1707, promoted from the
2026-10-30 KIAH frame-rate investigation's ``packstat.py``, its second
use).

For every tile DSF of a pack: the placements of the pack's OWN objects,
the triangles they draw (each OBJ's ``POINT_COUNTS`` x its placements),
the duplicate placements "Optimise pack" drops (D1) and the triangles
left, and the heaviest definitions.  The engine's own readers answer —
``auto_patch_v2/airport/pack_optimise`` (``dedupe.drop_set``,
``weight.estimate``) — so this prints what the object stage's offer
reads.  The PRISTINE file is read (``<dsf>.anchor_bak`` when present).

READ-ONLY on the pack: DSFTool dumps go into ``--work`` (default a temp
dir), never beside the pack or into the shared data repo.

    venv/bin/python tools/pack_weight.py "<Custom Scenery>/<pack>" [--top 8]
        [--text DUMP]... [--work DIR] [--json] [--xplane ROOT] [--far M]

``--text`` reads an existing dump instead of running DSFTool (one per
tile DSF, in order); the twin is ``tests/test_pack_optimise_write.py``.
``--xplane`` weighs the WHOLE recipe "Optimise" would write today with
that install's libraries (``pack_optimise.build_recipe``: the library
swaps and the object copies too), and ``--far`` (default 1000 m) adds
the triangles still drawn beyond that distance, before and after.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from auto_patch_v2.airport import pack_optimise as PO  # noqa: E402
from auto_patch_v2.airport.pack_optimise import weight as WT  # noqa: E402


def tile_dsfs(pack: str) -> list[str]:
    return sorted(glob.glob(os.path.join(pack, "Earth nav data", "*", "*.dsf")))


def weigh(pack: str, lines, top: int, exports_of=None,
          far_m: float | None = None) -> dict:
    """One tile dump's row: :func:`weight.estimate` and the D1 counts
    (with ``exports_of``, of the whole recipe ``build_recipe`` makes)."""
    recipe = PO.build_recipe(pack, lines, exports_of)
    drop, counts = PO.drop_ordinals(lines, recipe, frozenset())
    row = {**WT.estimate(pack, lines, drop, top=top, swaps=recipe.get("swap"),
                         far_m=far_m, copies=recipe.get("objects")), **counts}
    row["copies"] = len(recipe.get("objects") or ())
    row["offered"] = (row["tris_before"] > WT.OFFER_TRIANGLES
                      and (row.get("dropped", 0) > 0 or row["swapped"] > 0))
    return row


def _exports_of(xplane: str | None, dsf_name: str):
    """The install's ``exports_of`` for the tile a DSF name is."""
    if not xplane:
        return None
    from auto_patch import agp_reader as AGP
    stem = os.path.splitext(os.path.basename(dsf_name))[0]
    lat, lon = int(stem[:3]), int(stem[3:7])
    rows = AGP.export_files(xplane)
    return lambda v: AGP.files_at(rows.get(v.lower(), ()), lat, lon)


def main(argv=None) -> int:
    import O4_Console_Encoding as CE  # UTF-8 before anything prints (#171)
    CE.configure_console_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pack")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--text", action="append", default=[])
    ap.add_argument("--work")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--xplane", help="the X-Plane install whose libraries the "
                    "swap reads (the whole recipe is weighed)")
    ap.add_argument("--far", type=float, default=None,
                    help="also count the triangles drawn beyond this many m")
    a = ap.parse_args(argv)
    dsfs = tile_dsfs(a.pack)
    texts = list(a.text)
    if not texts:
        from auto_patch import dsf_reader as DSFR
        from auto_patch_v2.airport import dsf_write as W
        work = a.work or tempfile.mkdtemp(prefix="pack_weight_")
        os.makedirs(work, exist_ok=True)
        for dsf in dsfs:
            src = dsf + ".anchor_bak" if os.path.isfile(dsf + ".anchor_bak") else dsf
            out = os.path.join(work, os.path.basename(dsf) + ".txt")
            W.dump(src, out, DSFR._dsftool_path() or "DSFTool")
            texts.append(out)
    rows = {}
    names = [os.path.basename(d) for d in dsfs] or list(texts)
    for name, text in zip(names, texts, strict=False):
        with open(text, encoding="utf-8", errors="surrogateescape") as fh:
            lines = fh.read().splitlines(keepends=True)
        rows[name] = weigh(a.pack, lines, a.top, _exports_of(a.xplane, name),
                           a.far)
    if a.json:
        print(json.dumps(rows, indent=1))
        return 0
    for name, r in rows.items():
        print(f"{name}: {r['placements']:,} placements of the pack's own "
              f"objects, {r['tris_before'] / 1e6:.1f} M triangles; D1 drops "
              f"{r.get('dropped', 0):,} ({r.get('groups', 0):,} groups), "
              f"{r['swapped']:,} swapped, {r['copies']} copies -> "
              f"{r['tris_after'] / 1e6:.1f} M; offered: {r['offered']}")
        if "far_before" in r:
            print(f"  beyond {a.far:g} m: {r['far_before'] / 1e6:.1f} M -> "
                  f"{r['far_after'] / 1e6:.1f} M")
        for tn, t, n, path in r.get("top", ()):
            print(f"  {tn:13,d}  tris={t:7,d}  n={n:6,d}  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
