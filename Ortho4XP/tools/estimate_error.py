#!/usr/bin/env python3
"""How accurate are the tile build-time estimates?  (#2045)

Replays the engine's time model over the recorded tile builds
(``~/.ortho4xp/tile_build_times``) — each build predicted from the records
that existed before it — and prints the median and p90 error, split cached
vs cold and with vs without airport solves, with n.  Read only.

    venv/bin/python tools/estimate_error.py
    venv/bin/python tools/estimate_error.py --tile +39-105   # per build
    venv/bin/python tools/estimate_error.py --store DIR --json

The logic is ``src/o4_engine/estimate_error.py``; the predictor is the
model the code tree carries (``tile_time_model.predict_for_replay``).
"""

import argparse
import datetime
import json
import os
import sys

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

from o4_engine import airport_time_model as ATM  # noqa: E402
from o4_engine import estimate_error as EE  # noqa: E402
from o4_engine import tile_time_model as TTM  # noqa: E402


def _load(store):
    out = {}
    for name in sorted(os.listdir(store)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(store, name), encoding="utf-8") as f:
                records = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(records, list):
            out[name[:-5]] = records
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--store", default=TTM.STORE_DIRECTORY)
    ap.add_argument("--tile", help="print each build of this tile")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--airports-known", action="store_true",
                    help="price the vector step on the airports each build "
                         "actually solved (the estimate once they begin)")
    ap.add_argument("--airport-index",
                    help="the airport index TSV the size rule reads "
                         "(default: the data folder's)")
    args = ap.parse_args(argv)
    if args.airport_index:
        ATM.INDEX_PATH = args.airport_index
    rows = EE.replay(_load(args.store),
                     airports_known=args.airports_known)
    summary = EE.summarise(rows)
    if args.json:
        print(json.dumps({"summary": summary, "rows": rows}, indent=1,
                         default=str))
        return 0
    print("%-24s %4s %8s %8s %8s" % ("class", "n", "median", "p90",
                                     "bias"))
    for name in sorted(summary):
        s = summary[name]
        if not s.get("n"):
            continue
        print("%-24s %4d %7.2fx %7.2fx %7.2fx" % (
            name, s["n"], s["median_factor"], s["p90_factor"],
            s["median_ratio"]))
    print("factor = max(pred/actual, actual/pred); bias = median pred/actual")
    if args.tile:
        for row in rows:
            if row["tile"] != args.tile:
                continue
            when = datetime.datetime.fromtimestamp(
                row["finished_at"], datetime.timezone.utc)
            print("%s %s %s airports=%d predicted %.0fs actual %.0fs" % (
                row["tile"], when.strftime("%Y-%m-%dT%H:%MZ"),
                "cold" if row["cold"] else "cached", row["airports"],
                row["predicted"], row["actual"]))
            for key, (p, a) in row["steps"].items():
                print("    %-9s predicted %7.0fs actual %7.0fs" % (key, p, a))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
