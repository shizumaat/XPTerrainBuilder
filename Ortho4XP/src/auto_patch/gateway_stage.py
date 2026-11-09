"""GLOBAL AIRPORTS THAT ASK X-PLANE TO FLATTEN, and the Gateway packs
the app installs in their place (issue #1989).

Owner (2026-11-09): "many global airports include a flatten tag, which
prevents our grading from working. We should identify any airports that
we're grading that have this turned on, and ask the user if they would
like to install the latest from the gateway and remove the flatten tag.
We would then need to monitor any airports we install whenever the tile
is built to check if a newer version is available on the gateway."

* :func:`_offers` — THE REPORT for a list of graded airports: every one
  X-Plane draws from its Global Airports entry (``apt_dat.
  select_apt_dat`` picks a :func:`apt_dat.global_candidates` file) whose
  block carries ``1302 flatten 1`` (reason ``"flatten"``), and, with
  ``check_updates``, every Gateway pack the app installed whose Gateway
  recommendation moved on (reason ``"update"``).  An airport the user
  answered "never" for is not listed.
* :func:`gateway_stage` — the build's call, once a tile is built
  (``o4_engine.session``, on a thread of its own): the report for the
  airports the tile's patches graded, announced as
  ``GatewayAirports(state="found")``.  The update check reads the
  Gateway only for a pack the app installed, and never on a lane build
  (``O4_PACK_WRITES`` set).  Never installs; never raises.
* :func:`_install` — THE USER'S ACT: the Gateway's recommended upload
  (``gateway_api``) written as the custom airport pack
  ``"<ICAO> Gateway Airport"`` in Custom Scenery, its flatten rows
  removed through #1916's path (``apt_flatten.strip_flatten``: the
  shipped apt.dat kept as ``apt.dat.anchor_bak``, put back by Undo or
  the pack's Restore originals), its Gateway scenery id recorded in
  :data:`SIDECAR`, and the pack filed in ``scenery_packs.ini`` with the
  airports (``O4_Scenery_Packs_Tidy``).  An update replaces only a pack
  carrying the sidecar.
* :func:`gateway_choice` — the ``gateway_airports`` command: ``"ask"``,
  ``"install"`` (the rows ticked; a row shown and left unticked is
  remembered as "never"), ``"never"``, ``"undo"`` (the flatten rows put
  back in the installed pack).
"""
from __future__ import annotations

import json
import os
import shutil
import time
import traceback
import typing as _t

from . import gateway_api as _api
from . import pack_choice as _PC

__all__ = ["ACTIONS", "SIDECAR", "gateway_stage", "gateway_choice"]

#: the actions of the ``gateway_airports`` command
ACTIONS = ("install", "never", "undo", "ask")
#: the file in a pack the app installed from the Gateway: what it is
SIDECAR = "xptb_gateway.json"
#: how long one Gateway answer stands for the update check (one build
#: reads it once for all its tiles)
LATEST_TTL_S = 3600.0

STORE = _PC.Store(_PC.GATEWAY_CHOICES)
_LATEST: dict[str, tuple[float, int]] = {}


def _pack_name(icao: str) -> str:
    """The Custom Scenery folder a Gateway install of ``icao`` goes in."""
    return f"{icao.upper()} Gateway Airport"


def _choice_key(xplane_root: str, icao: str) -> str:
    """The answers-store key of one airport (an absolute path, as the
    per-pack stores key theirs)."""
    return os.path.join(os.path.abspath(xplane_root), "Global Scenery",
                        "Global Airports", icao.upper())


def _say(level: int, text: str) -> None:
    import O4_UI_Utils as UI
    UI.vprint(level, text)


def _block(xplane_root: str, icao: str) -> tuple[str, list[str]]:
    from auto_patch_v2.airport import apt_dat as _apt
    chosen = _apt.select_apt_dat(xplane_root, icao) or ""
    block = _apt.read_airport_block(chosen, icao) if chosen else None
    return chosen, list(block or [])


def _name_of(block: list[str]) -> str:
    return " ".join(block[0].split()[5:]) if block else ""


def _global_flatten(xplane_root: str, icao: str) -> dict | None:
    """The ``"flatten"`` row of ``icao``, or None: X-Plane draws it from
    a Global Airports entry carrying ``1302 flatten 1``."""
    from auto_patch_v2.airport import apt_dat as _apt
    from auto_patch_v2.airport import apt_flatten as _af
    chosen, block = _block(xplane_root, icao)
    if not chosen or chosen not in _apt.global_candidates(xplane_root):
        return None
    if not any(_af.is_flatten_row(ln) for ln in block):
        return None
    return _row(icao, _name_of(block), "flatten")


def _row(icao: str, name: str, reason: str, installed_id: int = 0,
         latest_id: int = 0, pack: str = "") -> dict:
    return {"icao": icao.upper(), "name": name, "reason": reason,
            "installed_id": int(installed_id), "latest_id": int(latest_id),
            "pack": pack}


def _read_sidecar(pack_root: str) -> dict:
    """The :data:`SIDECAR` of a pack, ``{}`` when it is not one the app
    installed from the Gateway."""
    try:
        with open(os.path.join(pack_root, SIDECAR), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) and doc.get("icao") else {}


def _installed_pack(xplane_root: str, icao: str) -> str:
    """The Gateway pack the app installed that X-Plane draws ``icao``
    from, ``""`` when it draws another file."""
    chosen, _ = _block(xplane_root, icao)
    root = os.path.dirname(os.path.dirname(chosen)) if chosen else ""
    side = _read_sidecar(root) if root else {}
    return root if str(side.get("icao", "")).upper() == icao.upper() else ""


def _latest_id(icao: str, fetch: _api.Fetch | None = None) -> int:
    """The Gateway's recommended scenery id of ``icao`` (one answer per
    :data:`LATEST_TTL_S`)."""
    now = time.monotonic()
    hit = _LATEST.get(icao.upper())
    if hit is not None and now - hit[0] < LATEST_TTL_S:
        return hit[1]
    sid = _api.recommended_id(_api.airport(icao, fetch))
    _LATEST[icao.upper()] = (now, sid)
    return sid


def _update_row(xplane_root: str, icao: str, fetch) -> dict | None:
    pack = _installed_pack(xplane_root, icao)
    if not pack:
        return None
    have = int(_read_sidecar(pack).get("scenery_id") or 0)
    try:
        latest = _latest_id(icao, fetch)
    except _api.GatewayError as exc:
        _say(1, f"  [gateway] {icao}: the update check failed ({exc})")
        return None
    if not latest or latest == have:
        return None
    _, block = _block(xplane_root, icao)
    return _row(icao, _name_of(block), "update", have, latest,
                os.path.basename(pack))


def _offers(xplane_root: str, codes: _t.Iterable[str], *,
           check_updates: bool, fetch: _api.Fetch | None = None) -> list[dict]:
    """THE REPORT (module doc): one row per airport of ``codes`` to
    offer, in ``codes`` order."""
    out: list[dict] = []
    for icao in dict.fromkeys(str(c).upper() for c in codes if c):
        if STORE.choice(_choice_key(xplane_root, icao)) == "never":
            continue
        row = _global_flatten(xplane_root, icao)
        if row is None and check_updates:
            row = _update_row(xplane_root, icao, fetch)
        if row is not None:
            out.append(row)
    return out


def _announce(lat: int, lon: int, state: str, items=(), error: str = "",
              files=()) -> dict:
    import O4_UI_Utils as UI
    fields = {"lat": int(lat or 0), "lon": int(lon or 0), "state": state,
              "items": [dict(r) for r in items], "error": error,
              "files": list(files)}
    UI.gateway_airports(**fields)
    return fields


def _graded_codes(lat: int, lon: int) -> list[str]:
    """The airports the tile's mesh graded: one per patch in its
    ``Patches`` folder (``ICAO_auto.patch.osm``, or a manual patch named
    for the ICAO before its first ``_``)."""
    import O4_File_Names as FNAMES
    try:
        names = sorted(os.listdir(FNAMES.patch_dir(lat, lon)))
    except OSError:
        return []
    return [n[:-len(".patch.osm")].split("_")[0] for n in names
            if n.endswith(".patch.osm")]


def gateway_stage(lat: int, lon: int, xplane_root: str | None,
                  codes: _t.Iterable[str] | None = None,
                  fetch: _api.Fetch | None = None) -> list[dict]:
    """The report for a built tile's graded airports (``codes``, default
    :func:`_graded_codes`), announced as ``state="found"`` when a row
    offers.  Never raises."""
    try:
        if not xplane_root:
            return []
        if codes is None:
            codes = _graded_codes(lat, lon)
        check = os.environ.get("O4_PACK_WRITES") is None
        rows = _offers(xplane_root, codes, check_updates=check, fetch=fetch)
        for r in rows:
            _say(0, f"  [gateway] {r['icao']}: "
                    + ("X-Plane flattens this Global Airports entry "
                       "(1302 flatten 1), so the graded ground is not what "
                       "the sim draws; the app offers the Gateway's latest "
                       "version without the flag"
                       if r["reason"] == "flatten" else
                       f"the Gateway has a newer version "
                       f"({r['installed_id']} -> {r['latest_id']})"))
        if rows:
            _announce(lat, lon, "found", rows)
        return rows
    except Exception as exc:
        _say(1, f"  [gateway] the Gateway airport check failed ({exc})")
        _say(2, traceback.format_exc())
        return []


def _write_pack(dest: str, files: dict[str, bytes]) -> None:
    for rel, data in files.items():
        path = os.path.join(dest, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)


def _install(xplane_root: str, icao: str,
            fetch: _api.Fetch | None = None) -> dict:
    """THE USER'S ACT (module doc).  Returns ``{"pack", "pack_root",
    "scenery_id", "flatten", "files"}``; raises :class:`gateway_api.
    GatewayError` or ``OSError`` with the install as it was."""
    import O4_Scenery_Packs_Tidy as _TIDY
    from auto_patch_v2.airport import apt_flatten as _af
    from auto_patch_v2.airport import backup_state as _bs
    icao = icao.upper()
    custom = os.path.join(xplane_root, "Custom Scenery")
    if not os.path.isdir(custom):
        raise _api.GatewayError(f"no Custom Scenery folder at {custom}")
    name = _pack_name(icao)
    dest = os.path.join(custom, name)
    if os.path.exists(dest) and not _read_sidecar(dest):
        raise _api.GatewayError(f"“{name}” is already in Custom Scenery and "
                                f"is not a pack this app installed")
    record = _api.airport(icao, fetch)
    sid = _api.recommended_id(record)
    if not sid:
        raise _api.GatewayError(f"the Gateway recommends no scenery for {icao}")
    upload = _api.scenery(sid, fetch)
    files = _api.pack_files(upload)
    fresh, old = dest + ".o4new", dest + ".o4old"
    for leftover in (fresh, old):
        shutil.rmtree(leftover, ignore_errors=True)
    try:
        _write_pack(fresh, files)
        apt = _af.apt_dat_of(fresh)
        flatten = _af.strip_flatten(apt) if apt else ""
        with open(os.path.join(fresh, SIDECAR), "w", encoding="utf-8",
                  newline="") as fh:
            json.dump({"icao": icao, "scenery_id": sid,
                       "date_approved": upload.get("dateApproved") or "",
                       "installed": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                  time.gmtime()),
                       "flatten_removed": flatten == "removed",
                       "source": f"{_api.API_ROOT}/scenery/{sid}"},
                      fh, indent=1)
        if os.path.exists(dest):
            os.replace(dest, old)
        os.replace(fresh, dest)
    finally:
        shutil.rmtree(fresh, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)
    _bs.invalidate_memo()
    _TIDY.tidy_scenery_packs(custom, kinds={name: "airport"}, names=[name])
    _LATEST[icao] = (time.monotonic(), sid)
    _say(0, f"  [gateway] {icao}: installed the Gateway's scenery {sid} as "
            f"“{name}”" + (" without its '1302 flatten 1' (the original "
                           "apt.dat is kept as apt.dat.anchor_bak)"
                           if flatten == "removed" else ""))
    return {"pack": name, "pack_root": dest, "scenery_id": sid,
            "flatten": flatten, "files": sorted(files)}


def _undo(xplane_root: str, icao: str) -> list[str]:
    """The flatten rows put back in the Gateway pack of ``icao``."""
    from auto_patch_v2.airport import apt_flatten as _af
    from auto_patch_v2.airport import backup_state as _bs
    root = os.path.join(xplane_root, "Custom Scenery", _pack_name(icao))
    apt = _af.apt_dat_of(root) if _read_sidecar(root) else ""
    if not apt or _af.classify(apt).state is not _bs.State.OURS:
        return []
    shutil.copy2(_af.classify(apt).backup, apt)
    _bs.invalidate_memo()
    return [apt]


def _codes_of_tile(xplane_root: str, lat: int, lon: int) -> list[str]:
    import O4_Airport_Apt_Identity as _ID
    return [e.code for e in _ID.tile_apt_dat_airports(
        lat, lon, xplane_root=xplane_root)]


def gateway_choice(xplane_root: str | None, action: str,
                   lat: int | None = None, lon: int | None = None,
                   items: _t.Iterable[str] | None = None,
                   shown: _t.Iterable[str] | None = None,
                   fetch: _api.Fetch | None = None) -> dict:
    """THE USER'S ANSWER (the ``gateway_airports`` command), announced as
    a ``GatewayAirports`` event.  ``state``: ``"ask"`` | ``"installed"``
    | ``"never"`` | ``"undone"`` | ``"none"`` | ``"failed"`` (``error``
    says why; an install that failed for one airport still installs the
    others).  Never raises."""
    la, lo = int(lat or 0), int(lon or 0)
    picked = [str(x).upper() for x in (items or ())]
    seen = [str(x).upper() for x in (shown if shown is not None else picked)]
    rows: list[dict] = []
    files: list[str] = []
    errors: list[str] = []
    state = "none"
    try:
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        if not xplane_root or not os.path.isdir(xplane_root):
            raise ValueError("no X-Plane install for this tile")
        if action == "ask":
            rows = _offers(xplane_root, _codes_of_tile(xplane_root, la, lo),
                          check_updates=True, fetch=fetch)
            state = "ask" if rows else "none"
        elif action == "never":
            for icao in seen:
                STORE.remember(_choice_key(xplane_root, icao), "never")
            state = "never"
        elif action == "undo":
            for icao in picked:
                files += _undo(xplane_root, icao)
            state = "undone" if files else "none"
        else:
            for icao in seen:
                if icao not in picked:
                    STORE.remember(_choice_key(xplane_root, icao), "never")
            for icao in picked:
                try:
                    done = _install(xplane_root, icao, fetch)
                except (_api.GatewayError, OSError) as exc:
                    errors.append(f"{icao}: {exc}")
                    _say(0, f"  [gateway] {icao}: the install failed ({exc})")
                    continue
                STORE.remember(_choice_key(xplane_root, icao), "")
                rows.append(_row(icao, "", "installed",
                                 done["scenery_id"], done["scenery_id"],
                                 done["pack"]))
                files.append(done["pack_root"])
            state = "installed" if rows else ("failed" if errors else "none")
    except Exception as exc:
        state, errors = "failed", [str(exc)]
        _say(0, f"  [gateway] Gateway airports {action} failed ({exc})")
        _say(2, traceback.format_exc())
    return _announce(la, lo, state, rows, "; ".join(errors), files)
