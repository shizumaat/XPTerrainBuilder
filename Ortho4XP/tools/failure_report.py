#!/usr/bin/env python
"""THE FAILURE REPORT from a shell (issue #565, RULINGS 2026-10-12b): the
REDACTED report a user would send us for one tile, built from an engine
stderr log — the same text, issue title and prefilled new-issue URL the
apps get from the ``failure_report`` engine command
(``o4_engine.failure_report``; redaction rules in ``o4_engine.redaction``).

    venv/bin/python tools/failure_report.py --tile +45-123
        [--log PATH] [--code CODE --message TEXT --detail TEXT]
        [--airport ICAO ...] [--app-version V] [--app-name mac|qt]
        [--xplane-dir DIR] [--out FILE_OR_DIR] [--url]

``--log`` defaults to the mac app's log, then the data root's.  With no
``--code`` the failure is read from the log's own words and titled
``unclassified``.  Prints the report; ``--out`` also saves it, ``--url``
prints the issue title and URL after it.  Reads one file, writes at most
one; no network.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

from o4_engine import failure_report as FR  # noqa: E402

MAC_LOG = os.path.join("~", "Library", "Logs", "XPTerrainBuilder",
                       "engine-stderr.log")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tile", required=True, help="e.g. +45-123")
    parser.add_argument("--log", default="")
    parser.add_argument("--code", default="")
    parser.add_argument("--message", default="")
    parser.add_argument("--detail", default="")
    parser.add_argument("--airport", action="append", default=[])
    parser.add_argument("--app-version", default="")
    parser.add_argument("--app-name", default="")
    parser.add_argument("--xplane-dir", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--url", action="store_true")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[+-]\d\d[+-]\d\d\d", args.tile):
        parser.error("--tile is +LAT+LON, e.g. +45-123")
    log = args.log
    if not log:
        mac = os.path.expanduser(MAC_LOG)
        log = mac if os.path.isfile(mac) else ""
    failures = None
    if args.code or args.message or args.detail:
        failures = [{"code": args.code, "what": args.message,
                     "airports": args.airport, "detail": args.detail}]
    result = FR.failure_report(
        tile=args.tile, failures=failures, airports=args.airport or None,
        app_version=args.app_version, app_name=args.app_name,
        log_path=log, xplane_dir=args.xplane_dir, save_path=args.out)
    sys.stdout.write(result["report"])
    if args.url:
        sys.stdout.write("\n== Issue ==\n%s\n%s\n(%d characters)\n" % (
            result["title"], result["issue_url"], result["url_length"]))
    if result["saved_path"]:
        sys.stderr.write("saved %s\n" % result["saved_path"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
