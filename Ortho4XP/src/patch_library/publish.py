"""PUBLISH PATCH (#1699 phase 2): an airport of a built tile → a pull
request on the library, from the app.

:func:`preview` packages the entry (:mod:`.entry`) and runs the checks
the library will run (:mod:`.checks`, with the library's own
``publishers.json`` and ``licences.json``), and shows what will be
published: the files and sizes, the version, the problems, whether it
merges by itself (a verified developer's own pack) or goes to review.

:func:`publish` does it: the publisher has accepted the library licence
(ODbL 1.0 and each source's terms, once; owner Q304/Q319) and is
signed in to GitHub (:mod:`.github`).
The app forks the library into the publisher's account, commits the
entry to a new branch there and opens the pull request.  Publishing
needs a GitHub account (owner, 2026-11-02); nothing is hosted by us.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile

from . import LICENCE, LibraryRefused
from . import checks as _checks
from . import client as _client
from . import config as _config
from . import entry as _entry
from . import github as _github
from . import layout as L
from . import terms as _terms

__all__ = ["ACCEPTED_NAME",
           "preview", "publish"]

ACCEPTED_NAME = "licence_accepted.json"


def _licence_accepted() -> bool:
    """Whether the publisher accepted the library licence on this machine."""
    return os.path.isfile(os.path.join(_client.library_dir(), ACCEPTED_NAME))


def _accept_licence() -> None:
    folder = _client.library_dir()
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, ACCEPTED_NAME), "w", encoding="utf-8", newline="\n") as h:
        json.dump({"licence": LICENCE}, h)


def _published_versions(icao: str, tile_key: str, signature: str) -> list:
    """The versions the library has of ``icao`` for this pack signature,
    from a fresh index."""
    rows = _client.region_index(L.region_of(tile_key), force=True).get(icao, [])
    return sorted(v for r in rows if r["signature"] == signature
                  for v in r.get("versions") or [r["latest"]])


def _next_version(icao: str, tile_key: str, signature: str) -> int:
    """One past the library's latest version of ``icao`` for this pack
    signature (1 for a first entry)."""
    return 1 + max(_published_versions(icao, tile_key, signature) or [0])


def _tile(lat, lon, working_dir: str):
    import O4_File_Names as FNAMES
    from tile_bundle.export import load_tile
    custom = working_dir if working_dir and os.path.normpath(working_dir) != \
        os.path.normpath(FNAMES.Tile_dir) else ""
    return load_tile(int(lat), int(lon), os.path.join(custom, "") if custom else "")


def _licences() -> dict:
    """The library's licence gate (``licences.json``, :mod:`.terms`)."""
    return _client.fetch_json(L.LICENCES) or _terms.DEFAULT_LICENCES


def _package(lat, lon, icao, working_dir, kind, login, notes, licences) -> tuple:
    import O4_File_Names as FNAMES
    from tile_bundle.key import xplane_root

    from . import key as _key
    if not _config.configured():
        raise LibraryRefused("The patch library is not set up in this app yet")
    tile = _tile(lat, lon, working_dir)
    root = xplane_root(tile)
    if not root:
        raise LibraryRefused("No X-Plane folder is set; the pack cannot be read")
    signature = _key.pack_now(root, icao.upper(), tile.lat, tile.lon)["signature"]
    version = _next_version(icao.upper(), FNAMES.short_latlon(tile.lat, tile.lon),
                           signature)
    return tile, _entry.package(tile, icao, kind=kind, publisher=login,
                                version=version, notes=notes, licences=licences)


def _check(entry: dict, login: str | None, licences: dict) -> dict:
    publishers = _client.fetch_json(L.PUBLISHERS) or {}
    root = tempfile.mkdtemp(prefix="xptb_publish_")
    try:
        _entry.write_folder(root, entry)
        m = entry["manifest"]
        return _checks.check_entry(
            root, entry["rel"], publishers=publishers, licences=licences,
            author=login, published=set(_published_versions(
                m["icao"], m["tile"], m["signature"])))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _login() -> tuple:
    token = _github.stored_token()
    if not token:
        return None, None
    return token, _github.Client(token).login()


def preview(lat, lon, icao: str, working_dir: str = "", kind: str = "",
            notes: str = "") -> dict:
    """ENGINE COMMAND ``library_publish_preview``: what "Publish patch"
    would publish for ``icao`` of the built tile.

    :returns: ``{"icao", "entry", "version", "pack", "kind", "files":
        [{"name", "bytes"}], "bytes", "problems", "verified",
        "signed_in", "licence", "noncommercial", "sources",
        "licence_accepted", "attribution"}`` — ``sources``: ``[{"provider",
        "licence", "terms", "noncommercial"}]``, each source's terms
    """
    _token, login = _login()
    licences = _licences()
    _tile_, entry = _package(lat, lon, icao, working_dir, kind, login or "", notes,
                             licences)
    verdict = _check(entry, login, licences)
    manifest = entry["manifest"]
    problems = list(verdict["problems"])
    return {"icao": manifest["icao"], "entry": entry["rel"],
            "version": manifest["version"], "pack": manifest["pack"]["name"],
            "kind": manifest["pack"]["kind"],
            "files": [{"name": n, "bytes": len(d)} for n, d in sorted(entry["files"].items())],
            "bytes": sum(len(d) for d in entry["files"].values()),
            "problems": problems, "verified": verdict["verified"],
            "signed_in": login or "", "licence": manifest["licence"],
            "noncommercial": bool(manifest["noncommercial"]),
            "sources": [{k: s.get(k, "") for k in ("provider", "licence", "terms")}
                        | {"noncommercial": bool(s.get("noncommercial"))}
                        for s in manifest["sources"]],
            "licence_accepted": _licence_accepted(),
            "attribution": entry["files"][L.ATTRIBUTION].decode("utf-8")}


def _body(entry: dict, verdict: dict) -> str:
    m = entry["manifest"]
    lines = ["Airport patch **%s** version %d for the pack `%s` (%s)." % (
        m["icao"], m["version"], m["pack"]["name"], m["pack"]["kind"]), "",
        "- tile %s, engine %s, pack signature `%s`" % (m["tile"], m["engine_version"],
                                                       m["signature"][:12]),
        "- %s" % ("verified developer of this pack: merges when the checks pass"
                  if verdict["verified"] else "community entry: goes to review"),
        "", "Published from XPTerrainBuilder. " + _terms.statement(m["licence"])]
    if m.get("notes"):
        lines += ["", m["notes"]]
    return "\n".join(lines)


def publish(lat, lon, icao: str, working_dir: str = "", kind: str = "",
            notes: str = "", accept: bool = False) -> dict:
    """ENGINE COMMAND ``library_publish``: fork the library, commit the
    entry to a branch and open the pull request.

    :param accept: the publisher accepts the library licence now (asked
        once; refused while it was never accepted).
    :returns: ``{"pull_url", "number", "entry", "version", "auto_merge"}``
    """
    if accept:
        _accept_licence()
    if not _licence_accepted():
        raise LibraryRefused("Accept the library licence (%s and each "
                             "source's terms) to publish" % LICENCE)
    if not _config.configured(publishing=True):
        raise LibraryRefused("Publishing is not set up in this app yet")
    token, login = _login()
    if not token or not login:
        raise LibraryRefused("Sign in to GitHub to publish")
    licences = _licences()
    _tile_, entry = _package(lat, lon, icao, working_dir, kind, login, notes, licences)
    verdict = _check(entry, login, licences)
    if verdict["problems"]:
        raise LibraryRefused("The library would refuse this patch: "
                             + verdict["problems"][0])
    s = _config.settings()
    hub = _github.Client(token)
    fork = hub.fork(s["repo"], login)
    hub.sync(fork, s["branch"])
    m = entry["manifest"]
    branch = "xptb/%s-%s-v%d" % (m["icao"], m["signature"][:8], m["version"])
    files = {entry["rel"] + "/" + name: data for name, data in entry["files"].items()}
    hub.commit_files(fork, branch, s["branch"], files,
                     "%s v%d (%s)" % (m["icao"], m["version"], m["pack"]["name"]))
    pull = hub.pull(s["repo"], "%s:%s" % (login, branch), s["branch"],
                    "%s v%d — %s" % (m["icao"], m["version"], m["pack"]["name"]),
                    _body(entry, verdict))
    return {"pull_url": pull["html_url"], "number": pull["number"],
            "entry": entry["rel"], "version": m["version"],
            "auto_merge": bool(verdict["verified"])}
