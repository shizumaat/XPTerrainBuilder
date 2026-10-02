#!/usr/bin/env python3
"""ONE AIRPORT'S ``apt.dat``, FROM THE X-PLANE SCENERY GATEWAY (issue #250).

Why this exists.  A full tile build reads airport geometry from an
X-Plane install — ``auto_patch.apt_dat_reader.find_airport_apt_dat``
searches ``<xplane root>/Custom Scenery/<pack>/Earth nav data/apt.dat``,
then the Global Airports pack, then the stock default scenery.  A GitHub
runner has no install, and X-Plane's own global ``apt.dat`` is not
redistributable.

The X-Plane Scenery Gateway is: it publishes the community's airport
submissions through a public API, one airport at a time, and that is the
ONE airport ``.github/workflows/win-tile-smoke.yml`` needs.  So this
fetches it, and — just as important — writes a RECORD of what it fetched
(or of why it could not), because a substituted build input that is not
written down is the thing the brief forbids.

TWO REQUESTS, which is how the Gateway is shaped:

1. ``/apiv1/airport/<ICAO>`` — the airport record, whose
   ``recommendedSceneryId`` names the pack the Gateway itself considers
   current for that airport.
2. ``/apiv1/scenery/<id>`` — that pack, carrying its files as a
   base64 ``masterZipBlob``.  The ``.dat`` inside is the apt.dat text.

STDLIB ONLY, deliberately: this runs in the workflow BEFORE the engine's
packages are necessarily importable, and it must never be the reason a
smoke run cannot start.

IT NEVER FAILS LOUDLY ON ITS OWN.  A Gateway outage is not an engine
defect, so ``--record`` is always written and the exit code says what
happened; the workflow treats a miss as a substitution (the repository's
own CYXY fixture) and reports it as a coverage gap rather than going red
for someone else's downtime.

Usage::

    fetch_gateway_apt.py CYXY --out apt.dat --record gateway.json
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile

# The console pin, before anything can print (RULINGS: one derivation
# site, ``src/O4_Console_Encoding.py``, never a fork).  Loaded by path
# because this helper runs outside an installed engine; a checkout that
# does not carry it is not a reason to refuse to fetch an apt.dat, so the
# import is guarded and the fallback is simply the interpreter's default.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Ortho4XP", "src"))
try:
    import O4_Console_Encoding as _CE
except Exception:                                         # pragma: no cover
    _CE = None
else:
    _CE.configure_console_streams()

GATEWAY = "https://gateway.x-plane.com/apiv1"
#: A Gateway request that has not answered in this long is a Gateway
#: problem, not an engine one — see the module docstring.
TIMEOUT_S = 60


def _get_json(url):
    request = urllib.request.Request(
        url, headers={"Accept": "application/json",
                      "User-Agent": "XPTerrainBuilder-CI/1.0 (issue #250)"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return json.loads(response.read().decode("utf-8"))


def _apt_dat_from_scenery(scenery):
    """The apt.dat text inside a Gateway scenery pack's base64 zip.

    The Gateway hands the whole pack as one base64 blob; the apt.dat is
    the ``.dat`` member.  A pack can also carry a DSF and objects, which
    this ignores — the tile build wants the airport's rows, nothing else.
    """
    blob = scenery.get("masterZipBlob")
    if not blob:
        raise RuntimeError("the scenery record carries no masterZipBlob")
    archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(blob)))
    names = [n for n in archive.namelist() if n.lower().endswith(".dat")]
    if not names:
        raise RuntimeError("the scenery zip holds no .dat member (%s)"
                           % ", ".join(archive.namelist()[:8]))
    # Shortest path wins: the airport's own apt.dat sits at the pack root
    # while anything else .dat is nested.
    name = sorted(names, key=lambda n: (n.count("/"), len(n)))[0]
    return name, archive.read(name).decode("utf-8", errors="replace")


def main(argv):
    parser = argparse.ArgumentParser(
        description="Fetch ONE airport's apt.dat from the X-Plane Scenery "
                    "Gateway, and record what was fetched.")
    parser.add_argument("icao", help="the airport, e.g. CYXY")
    parser.add_argument("--out", required=True,
                        help="where to write the apt.dat text")
    parser.add_argument("--record", required=True,
                        help="where to write the JSON provenance record")
    arguments = parser.parse_args(argv)

    icao = arguments.icao.strip().upper()
    record = {
        "icao": icao,
        "source": "X-Plane Scenery Gateway",
        "api": GATEWAY,
        "ok": False,
        "a_real_install_provides": (
            "the global apt.dat shipped in X-Plane's Global Scenery, plus "
            "every airport the user has in Custom Scenery"),
        "coverage_gap": (
            "one airport only — no Custom Scenery precedence, no "
            "duplicate-ICAO resolution and no stock-default fallback is "
            "exercised by this run"),
    }
    try:
        airport = _get_json("%s/airport/%s" % (GATEWAY, icao))
        scenery_id = ((airport.get("airport") or airport)
                      .get("recommendedSceneryId"))
        record["recommended_scenery_id"] = scenery_id
        if not scenery_id:
            raise RuntimeError(
                "the Gateway has no recommended scenery for %s — the "
                "airport is unsubmitted, or the record changed shape" % icao)
        scenery = _get_json("%s/scenery/%s" % (GATEWAY, scenery_id))
        member, text = _apt_dat_from_scenery(
            scenery.get("scenery") or scenery)
        with open(arguments.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        record.update({
            "ok": True,
            "zip_member": member,
            "bytes": os.path.getsize(arguments.out),
            "rows": text.count("\n") + 1,
            "has_airport_header": any(
                line.split()[:1] in (["1"], ["16"], ["17"])
                for line in text.splitlines()),
            "url_hosts": ["gateway.x-plane.com"],
        })
        print("fetched %s apt.dat from the Scenery Gateway: scenery %s, "
              "member %r, %d bytes"
              % (icao, scenery_id, member, record["bytes"]))
    except (urllib.error.URLError, OSError, ValueError, RuntimeError,
            KeyError, zipfile.BadZipFile) as error:
        record["error"] = "%s: %s" % (type(error).__name__, error)
        print("the Scenery Gateway fetch for %s did NOT succeed: %s"
              % (icao, record["error"]), file=sys.stderr)
        print("this is NOT an engine defect — the caller substitutes the "
              "repository fixture and records the coverage gap",
              file=sys.stderr)
    finally:
        with open(arguments.record, "w", encoding="utf-8",
                  newline="\n") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)

    return 0 if record["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
