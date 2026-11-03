"""THE LIBRARY'S ENTRY CHECKS (#1699 phase 2) — stdlib only.

ONE implementation for two callers: the app runs it on the entry it is
about to publish (``patch_library.publish``, the publisher sees what the
library will say), and the library's pull-request workflow runs it from
a sparse checkout of this repository (``library_template/.github/
workflows/check.yml``).  It READS AN ENTRY AS DATA and never runs
anything from it: JSON is parsed, ``.xz`` members are decompressed and
hashed and their text searched; nothing is imported, unpickled or
executed.

What it refuses (each problem is one sentence for the pull request):

* a file outside the layout (:mod:`.layout`) or a name it does not allow;
* a manifest that is not the format, or that disagrees with its folder;
* a file whose sha256 or size is not the manifest's, or that is too big;
* a LOCAL PATH in any text (a home folder, a drive letter) — the app
  tokenises every path on the way out;
* a SOURCE not on the library's licence allowlist (``licences.json``;
  owner Q304: the library is ODbL 1.0);
* a COMMUNITY entry for a PAYWARE pack: it needs pack-relative encoding
  (owner Q303), which is not built yet — a verified developer's entry for
  their own pack is exempt;
* a version that skips one, or a change to a version already published.

``auto_merge`` is true only for a verified developer (``publishers.json``)
whose pull request adds one entry for one of their own packs and passes
every check; anything else goes to the community reviewers.

    python -m patch_library.checks --head DIR --base DIR --author LOGIN \
        --changed FILE [--json OUT]
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import lzma
import os
import re
import sys

from . import FORMAT, LICENCE
from . import layout as L

__all__ = ["MAX_FILE_BYTES", "MAX_ENTRY_BYTES", "PACK_KINDS",
           "DEFAULT_LICENCES", "LOCAL_PATH_RE", "load_json", "local_paths",
           "verified_for", "check_entry", "check_pull", "main"]

#: A compressed file's cap (GitHub refuses a blob over 100 MB).
MAX_FILE_BYTES = 50 * 1024 * 1024
#: An entry's cap, every file together.
MAX_ENTRY_BYTES = 100 * 1024 * 1024

#: What a pack is: the global default airports (Global Airports, X-Plane's
#: own), a free pack, or a paid one.
PACK_KINDS = ("default", "freeware", "payware")

#: The allowlist a library without ``licences.json`` uses: OpenStreetMap
#: and the engine's base elevation only.
DEFAULT_LICENCES = {"allowed": {"OpenStreetMap": "ODbL-1.0",
                                "base:auto": "the engine's base elevation"},
                    "held": {}}

#: A local path in any spelling a build writes: a home or volume folder,
#: as is or URL-quoted, or a Windows drive.
LOCAL_PATH_RE = re.compile(
    r"(?:/(?:Users|home|Volumes|private|mnt)/[^/\s'\"<>]"
    r"|%2F(?:Users|home|Volumes|private|mnt)%2F"
    r"|(?<![A-Za-z0-9])[A-Za-z]:(?:\\\\?|/|%5[Cc]|%2F)(?=[A-Za-z0-9_ .-]))")

_HEX = re.compile(r"^[0-9a-f]+$")


def load_json(path: str, default=None):
    """A JSON file's document, or ``default`` when it is absent."""
    try:
        with open(path, "rb") as handle:
            return json.loads(handle.read().decode("utf-8"))
    except FileNotFoundError:
        return default


def local_paths(text: str) -> list:
    """The local paths :data:`LOCAL_PATH_RE` finds in ``text`` (at most 3)."""
    return [m.group(0) for m in LOCAL_PATH_RE.finditer(text)][:3]


def verified_for(publishers: dict, login: str, icao: str, pack: str) -> bool:
    """Whether ``login`` is a verified developer (``publishers.json``)
    whose packs include ``pack`` for ``icao`` — names matched as the
    developer listed them (``fnmatch`` patterns)."""
    for dev in (publishers or {}).get("developers") or []:
        if str(dev.get("login", "")).lower() != str(login or "").lower():
            continue
        for row in dev.get("packs") or []:
            airports = [a.upper() for a in row.get("airports") or []]
            if fnmatch.fnmatch(pack, str(row.get("pack", ""))) and (
                    not airports or icao.upper() in airports):
                return True
    return False


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_problems(doc: dict, where: dict) -> list:
    out = []
    if doc.get("format") != FORMAT:
        return ["manifest.json is format %r, not %r" % (doc.get("format"), FORMAT)]
    for key, kind in (("icao", str), ("tile", str), ("version", int),
                      ("pack", dict), ("signature", str), ("law", dict),
                      ("solve", str), ("engine_version", str),
                      ("min_engine", str), ("publisher", str),
                      ("licence", str), ("sources", list), ("files", dict)):
        if not isinstance(doc.get(key), kind):
            out.append("manifest.json has no %s (%s)" % (key, kind.__name__))
    if out:
        return out
    if doc["icao"] != where["icao"]:
        out.append("the manifest is for %s but its folder is %s"
                   % (doc["icao"], where["icao"]))
    if doc["version"] != where["version"]:
        out.append("the manifest is version %d but its folder is v%d"
                   % (doc["version"], where["version"]))
    if not (len(doc["signature"]) >= 32 and _HEX.match(doc["signature"])
            and doc["signature"][:12] == where["sig"]):
        out.append("the pack signature does not match the entry's folder")
    if not L.TILE_RE.match(doc["tile"]):
        out.append("%r is not a tile" % doc["tile"])
    if doc["licence"] != LICENCE:
        out.append("an entry is published under %s, not %r" % (LICENCE, doc["licence"]))
    kind = (doc["pack"] or {}).get("kind")
    if kind not in PACK_KINDS:
        out.append("the pack's kind is %r; say one of %s" % (kind, ", ".join(PACK_KINDS)))
    if kind == "default" and (doc["pack"] or {}).get("custom"):
        out.append("a custom pack is not the global default airports")
    if L.pack_slug(str((doc["pack"] or {}).get("name", ""))) != where["pack"]:
        out.append("the pack name does not match the entry's folder")
    for key in ("fresh_v", "cfg", "code", "ap_engine"):
        if not isinstance(doc["law"].get(key), str) or not doc["law"][key]:
            out.append("the manifest's law has no %s" % key)
    return out


def _licence_problems(doc: dict, licences: dict) -> list:
    allowed = (licences or DEFAULT_LICENCES).get("allowed") or {}
    held = (licences or DEFAULT_LICENCES).get("held") or {}
    out = []
    for source in doc.get("sources") or []:
        provider = str(source.get("provider", ""))
        if provider in held:
            out.append("source %s is held (%s)" % (provider, held[provider]))
        elif provider not in allowed:
            out.append("source %s is not on the library's licence allowlist"
                       % provider)
    if not any(s.get("provider") == "OpenStreetMap" for s in doc.get("sources") or []):
        out.append("the sources do not credit OpenStreetMap")
    return out


def _file_problems(root: str, rel: str, doc: dict, icao: str) -> list:
    """Every file of the entry folder against the manifest: names, sizes,
    hashes, local paths."""
    folder = os.path.join(root, *rel.split("/"))
    out, total = [], 0
    listed = dict(doc.get("files") or {})
    present = []
    for base, _dirs, names in os.walk(folder):
        for name in names:
            present.append(os.path.relpath(os.path.join(base, name), folder)
                           .replace(os.sep, "/"))
    for name in sorted(present):
        if name in (L.MANIFEST, L.EDITS, L.ATTRIBUTION):
            continue
        part, _sep, base = name.partition("/")
        stem = base[:-3] if base.endswith(".xz") else ""
        match = (L.SOLVED_NAME_RE.match(stem) if part == L.SOLVED
                 else L.EDITED_NAME_RE.match(stem) if part == L.EDITED else None)
        if match is None or "/" in base:
            out.append("%s is not a file an entry may carry" % name)
            continue
        named = match.groupdict().get("icao") or match.groupdict().get("plan")
        if named != icao:
            out.append("%s is not %s's" % (name, icao))
        meta = listed.pop(name, None)
        if meta is None:
            out.append("%s is not in the manifest" % name)
            continue
        with open(os.path.join(folder, *name.split("/")), "rb") as handle:
            data = handle.read()
        total += len(data)
        if len(data) > MAX_FILE_BYTES:
            out.append("%s is %d MB; the cap is %d MB"
                       % (name, len(data) >> 20, MAX_FILE_BYTES >> 20))
        if _sha(data) != meta.get("sha256") or len(data) != meta.get("bytes"):
            out.append("%s does not match the manifest's hash" % name)
            continue
        try:
            raw = lzma.decompress(data)
        except lzma.LZMAError:
            out.append("%s is not xz data" % name)
            continue
        if _sha(raw) != meta.get("raw_sha256"):
            out.append("%s's content does not match the manifest" % name)
        found = local_paths(raw.decode("utf-8", "replace"))
        if found:
            out.append("%s holds a local path (%s)" % (name, found[0]))
    for name in sorted(listed):
        out.append("the manifest lists %s, which is not in the entry" % name)
    for name in (L.EDITS, L.ATTRIBUTION):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            out.append("the entry has no %s" % name)
            continue
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8", "replace")
        if local_paths(text):
            out.append("%s holds a local path" % name)
    if total > MAX_ENTRY_BYTES:
        out.append("the entry is %d MB; the cap is %d MB"
                   % (total >> 20, MAX_ENTRY_BYTES >> 20))
    return out


def check_entry(root: str, rel: str, *, publishers=None, licences=None,
                author: str | None = None, published=None) -> dict:
    """Check the entry folder ``rel`` (``entries/…/v<N>``) of the library
    checkout ``root``; ``published``, when given, is the versions the
    library already has for this pack version (the app's pre-publish
    check, whose ``root`` holds only the new entry), else they are read
    from ``root``.

    :returns: ``{"entry", "problems": [sentence, ...], "verified": bool}``
        — ``verified`` when the publisher is a verified developer of this
        pack (and, with ``author``, is the pull request's author).
    """
    where = L.parse_entry_dir(rel)
    if where is None:
        return {"entry": rel, "problems": ["%s is not an entry folder "
                                           "(entries/<ICAO>/<pack>/<pack "
                                           "version>/v<N>)" % rel],
                "verified": False}
    doc = load_json(os.path.join(root, *rel.split("/"), L.MANIFEST))
    if not isinstance(doc, dict):
        return {"entry": rel, "problems": ["the entry has no manifest.json"],
                "verified": False}
    problems = _manifest_problems(doc, where)
    if problems:
        return {"entry": rel, "problems": problems, "verified": False}
    publisher = doc["publisher"]
    if author is not None and publisher.lower() != author.lower():
        problems.append("the entry names %s as its publisher, but %s opened "
                        "the pull request" % (publisher, author))
    verified = verified_for(publishers, publisher, doc["icao"], doc["pack"]["name"])
    if doc["pack"]["kind"] == "payware" and not verified:
        problems.append(
            "a community entry for a payware pack needs pack-relative "
            "encoding (owner Q303), which the library does not take yet; "
            "the pack's own developer can publish it as a verified developer")
    problems += _licence_problems(doc, licences)
    problems += _file_problems(root, rel, doc, doc["icao"])
    if where["version"] > 1:
        prev = rel.rsplit("/", 1)[0] + "/v%d" % (where["version"] - 1)
        if (where["version"] - 1 not in published) if published is not None else \
                not os.path.isfile(os.path.join(root, *prev.split("/"), L.MANIFEST)):
            problems.append("version %d is published before version %d"
                            % (where["version"], where["version"] - 1))
    return {"entry": rel, "problems": problems, "verified": verified}


def _entry_of(path: str) -> str | None:
    parts = path.strip("/").split("/")
    return "/".join(parts[:5]) if len(parts) > 5 and parts[0] == L.ENTRIES else None


def check_pull(head: str, base: str, changed, author: str, *,
               publishers=None, licences=None) -> dict:
    """A pull request's verdict: ``changed`` its changed paths, ``head``
    and ``base`` checkouts of its head and of the library's branch.

    Publishers and licences are read from ``base`` (a pull request cannot
    make itself verified).

    :returns: ``{"ok", "auto_merge", "problems", "entries": [check_entry
        result, ...]}``
    """
    publishers = publishers if publishers is not None else load_json(
        os.path.join(base, L.PUBLISHERS), {})
    licences = licences if licences is not None else load_json(
        os.path.join(base, L.LICENCES), DEFAULT_LICENCES)
    problems, entries = [], {}
    for path in sorted(set(changed)):
        entry = _entry_of(path)
        if entry is None:
            problems.append("%s is outside entries/: a reviewer must read it" % path)
            continue
        if os.path.exists(os.path.join(base, *entry.split("/"), L.MANIFEST)):
            problems.append("%s is already published; a published version "
                            "never changes (publish the next one)" % entry)
        entries.setdefault(entry, None)
    results = [check_entry(head, e, publishers=publishers, licences=licences,
                           author=author) for e in sorted(entries)]
    problems += [p for r in results for p in r["problems"]]
    ok = not problems and bool(results)
    return {"ok": ok, "problems": problems, "entries": results,
            "auto_merge": ok and len(results) == 1 and results[0]["verified"]}


def main(argv=None) -> int:
    """The workflow's entry point: rc 0 when every check passes."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--head", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--changed", required=True,
                        help="a file listing the changed paths, one a line")
    parser.add_argument("--json", default="")
    args = parser.parse_args(argv)
    with open(args.changed, encoding="utf-8") as handle:
        changed = [line.strip() for line in handle if line.strip()]
    verdict = check_pull(args.head, args.base, changed, args.author)
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(verdict, handle, indent=1)
    for line in verdict["problems"]:
        print("- " + line)
    print("auto_merge=%s" % ("true" if verdict["auto_merge"] else "false"))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
