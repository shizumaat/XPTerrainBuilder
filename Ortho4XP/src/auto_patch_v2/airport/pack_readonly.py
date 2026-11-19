"""A READ-ONLY PACK IS ASKED ABOUT, never waited on (#2174, RULINGS
2026-11-19d: "Yes, definitely warn the user and ask.").

Before the object stage writes an airport's pack it calls :func:`gate`.
A writable pack passes at once.  A read-only one (``pack_access.
readonly_folders``) is named in ONE ``PackReadOnly(state="found")`` event
and its writes PAUSE in this tile's object stage until the user answers
in either app (``EngineSession.pack_readonly``):

* **Make writable** — the engine adds ``u+w`` to the pack's folders and
  files (``pack_access.make_writable``), logs what it changed and records
  ``writable``; the paused writer sees the pack writable and its writes
  go on in the same run.
* **Not now** — recorded as ``not_now``: the paused writer leaves the
  pack as it is, and every later build does too, quietly, until the user
  asks again from the tile's row under Modified airports (``rows``, read
  by ``object_rebake.modified_packs``: "read-only — not adjusted").

The answer travels through one small JSON file beside the other pack
answers (``pack_choice.store_path``), so a writer in a parallel worker
process sees an answer the app gave the parent engine.  Without a front
end (no engine session) nothing is asked and nothing waits; an answer
that never comes is "Not now" after :data:`WAIT_SECONDS`, and a stopped
build stops the wait.
"""
from __future__ import annotations

import json
import os
import time
import typing as _t

import O4_File_Names as _FN

from . import pack_access as _pa

__all__ = ["FILE", "WAIT_SECONDS", "gate", "rows", "choice"]

#: the answers file
FILE = "pack_readonly.json"
#: the longest a paused writer waits for the user's answer (s)
WAIT_SECONDS = 600.0
#: how often a paused writer looks for the answer (s)
POLL_SECONDS = 0.5

WAITING, NOT_NOW, WRITABLE = "waiting", "not_now", "writable"


def _key_of(pack_root: str) -> str:
    from . import pack_choice as _PC
    return _PC.pack_key(pack_root)


def _path() -> str:
    from . import pack_choice as _PC
    return _PC.store_path(FILE)


def _write(doc: dict) -> None:
    path = _path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = "%s.%d.tmp" % (path, os.getpid())
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        pass


def _entry(pack_root: str) -> dict:
    """The pack's recorded state (``{}`` when none)."""
    got = _FN.read_json_dict(_path()).get(_key_of(pack_root))
    return got if isinstance(got, dict) else {}


def _answer(pack_root: str, state: str, lat=None, lon=None) -> None:
    """Record the pack's state (``WAITING`` / ``NOT_NOW`` / ``WRITABLE``),
    adding tile ``lat``/``lon`` to those it was asked for, or forget the
    pack (``""``)."""
    doc = _FN.read_json_dict(_path())
    key = _key_of(pack_root)
    if not state:
        doc.pop(key, None)
    else:
        old = doc.get(key) if isinstance(doc.get(key), dict) else {}
        tiles = list(old.get("tiles") or [])
        if lat is not None and lon is not None:
            import O4_File_Names as FNAMES
            t = FNAMES.short_latlon(int(lat), int(lon))
            if t not in tiles:
                tiles.append(t)
        doc[key] = {"state": state, "pack_root": os.path.abspath(pack_root),
                    "pack": os.path.basename(os.path.normpath(pack_root)),
                    "tiles": tiles, "ts": time.time()}
    _write(doc)


def _event_fields(pack_root: str, lat, lon, state: str,
                 folders: _t.Sequence[str] = (), **extra) -> dict:
    """The ``PackReadOnly`` event's fields."""
    return dict(pack=os.path.basename(os.path.normpath(pack_root)),
                pack_root=pack_root, lat=int(lat or 0), lon=int(lon or 0),
                state=state,
                folders=_pa.relative_folders(pack_root, folders)[:8],
                **extra)


def _front_end() -> bool:
    import O4_UI_Utils as UI
    return getattr(UI, "engine_session", None) is not None


def _stopped() -> bool:
    import O4_UI_Utils as UI
    return bool(getattr(UI, "red_flag", False))


def _wait(pack_root: str, asked_at: float) -> bool:
    """Poll for the answer: True when the pack became writable (the app's
    Make writable, or the user's own change), False on Not now, a stop or
    :data:`WAIT_SECONDS` without an answer."""
    deadline = time.monotonic() + WAIT_SECONDS
    polls = 0
    while time.monotonic() < deadline and not _stopped():
        got = _entry(pack_root)
        if got.get("state") == NOT_NOW and got.get("ts", 0) >= asked_at:
            return False
        if (got.get("state") == WRITABLE or not polls % 4) and \
                not _pa.readonly_folders(pack_root):
            return True
        polls += 1
        time.sleep(POLL_SECONDS)
    return False


def gate(pack_root: str, lat: int, lon: int) -> bool:
    """Whether the object stage may write ``pack_root`` now (module doc).
    Never raises."""
    import O4_UI_Utils as UI
    try:
        folders = _pa.readonly_folders(pack_root)
        if not folders:
            if _entry(pack_root):
                _answer(pack_root, "")
            return True
        name = os.path.basename(os.path.normpath(pack_root))
        where = ", ".join(_pa.relative_folders(pack_root, folders)[:3])
        if _entry(pack_root).get("state") == NOT_NOW:
            _answer(pack_root, NOT_NOW, lat, lon)
            UI.vprint(0, f"  [pack] {name} is read-only (as it was downloaded): "
                         f"not adjusted, as you answered (Ask again is on its "
                         f"row under Modified airports)")
            return False
        asked_at = time.time()
        _answer(pack_root, WAITING, lat, lon)
        UI.pack_readonly(**_event_fields(pack_root, lat, lon, "found", folders))
        if not _front_end():
            UI.vprint(0, f"  [pack] {name} is read-only (as it was downloaded: "
                         f"{where}); it is left as it is")
            _answer(pack_root, NOT_NOW, lat, lon)
            return False
        UI.vprint(0, f"  [pack] {name} is read-only (as it was downloaded: "
                     f"{where}); its writes wait for your answer")
        if _wait(pack_root, asked_at):
            _answer(pack_root, "")
            UI.vprint(0, f"  [pack] {name} is writable now; its writes go on")
            return True
        if _entry(pack_root).get("state") != NOT_NOW:
            _answer(pack_root, NOT_NOW, lat, lon)
        UI.vprint(0, f"  [pack] {name}: left as it is (read-only — not adjusted)")
        return False
    except Exception as exc:                       # never fail the stage
        UI.vprint(1, f"  [pack] read-only check skipped ({exc})")
        return not _pa.readonly_folders(pack_root)


def rows(tile: str | None = None) -> list[dict]:
    """The packs left read-only (Not now), for the Modified airports rows:
    ``modified_packs``' entry shape with ``read_only`` true; with
    ``tile`` (``+41-087``) only the packs asked about for it."""
    out = []
    for key, got in sorted(_FN.read_json_dict(_path()).items()):
        if not isinstance(got, dict) or got.get("state") != NOT_NOW:
            continue
        tiles = list(got.get("tiles") or [])
        if tile is not None and tile not in tiles:
            continue
        root = got.get("pack_root") or key
        if not os.path.isdir(root):
            continue
        out.append({"pack_name": got.get("pack") or os.path.basename(root),
                    "pack_path": root, "objects": 0, "read_only": True,
                    "tiles": tiles})
    return out


def choice(pack_root: str, action: str, lat=None, lon=None) -> dict:
    """THE USER'S ANSWER (the ``pack_readonly`` command): ``action`` is
    ``"writable"`` (Make writable), ``"not_now"`` or ``"ask"`` (the row's
    Ask again).  Announces and returns the ``PackReadOnly`` fields.
    Never raises."""
    import O4_UI_Utils as UI
    name = os.path.basename(os.path.normpath(pack_root or ""))
    was = _entry(pack_root)
    la = lat if lat is not None else _first_tile(was)[0]
    lo = lon if lon is not None else _first_tile(was)[1]
    folders = _pa.readonly_folders(pack_root)
    out = _event_fields(pack_root, la, lo, "none", folders)
    if action == "not_now":
        _answer(pack_root, NOT_NOW, lat, lon)
        out["state"] = "not_now"
    elif action == "ask":
        out["state"] = "ask" if folders else "none"
        if not folders:
            _answer(pack_root, "")
    elif action == "writable":
        try:
            changed = _pa.make_writable(pack_root)
        except OSError as exc:
            out.update(state="failed", error=str(exc))
            UI.vprint(0, f"  [pack] {name}: could not be made writable ({exc}); "
                         f"it is as it was")
        else:
            waiting = was.get("state") == WAITING
            _answer(pack_root, WRITABLE if waiting else "")
            out.update(state="writable", changed=len(changed), folders=[],
                       rebuild=not waiting and was.get("state") == NOT_NOW)
            UI.vprint(0, f"  [pack] {name}: made writable — added your write "
                         f"permission (u+w) to {len(changed)} folder(s) and "
                         f"file(s): " + ", ".join(_pa.relative_folders(
                             pack_root, changed[:5]))
                      + (" …" if len(changed) > 5 else ""))
    else:
        out.update(state="failed", error=f"unknown action {action!r}")
    UI.pack_readonly(**out)
    return out


def _first_tile(got: dict) -> tuple:
    """The first tile the pack was asked for, as ``(lat, lon)``."""
    import O4_File_Names as FNAMES
    for t in got.get("tiles") or ():
        try:
            return tuple(FNAMES.parse_tile_key(t))
        except Exception:
            continue
    return (0, 0)
