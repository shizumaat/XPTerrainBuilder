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
  block carries ``1302 flatten 1`` (reason ``"flatten"``), every one
  whose patch published taxiway decks or road bridges its Global
  Airports entry cannot carry (reason ``"bridges"``, #2169; RULINGS
  2026-11-16y (2): "offer to install and modify it like we do with the
  flatten removal"), and, with
  ``check_updates``, every Gateway pack the app installed whose Gateway
  recommendation moved on (reason ``"update"``).  An airport the user
  answered "never" for is not listed.
* :func:`gateway_early` — THE EARLY REPORT (#2169 follow-up; owner
  2026-11-19T00:21Z: "Can't we detect ahead of time if we need it so we
  don't have to build the patch twice?"): at run start, before any patch
  is built, the run's tiles' Global Airports airports that flatten, or
  whose OSM feeds already on disk show a deck / road-bridge candidate
  (``auto_patch_v2.planar.offer_witness``), so an Install lands before
  the patch and the same run builds it against the Gateway pack.
* ONCE PER RUN (:func:`begin_run`): an airport is asked at most once per
  run, however many tiles it spans (the early report and every tile's
  :func:`gateway_stage` share the run's asked set); an airport installed
  this run whose patch a tile still built against Global Airports
  (``generated.offer`` on its graded surface) is named by
  :func:`stale_patches`, and the run builds that tile's vector step again
  (``o4_engine``), once per tile and airport.
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
  remembered as "never"), ``"never"``, ``"later"`` (Not now: the patches
  waiting for the answer go on, #2212), ``"undo"`` (the flatten rows put
  back in the installed pack).  Each answer is recorded with its time
  (``gateway_wait.note_answer``) for a patch that waits on it.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
import traceback
import typing as _t

from auto_patch_v2.airport import pack_choice as _PC

from . import gateway_api as _api
from . import gateway_wait as _WAIT

__all__ = ["ACTIONS", "SIDECAR", "gateway_stage", "gateway_choice",
           "gateway_early", "begin_run", "stale_patches"]

#: the actions of the ``gateway_airports`` command
ACTIONS = ("install", "never", "undo", "ask", "later")
#: the file in a pack the app installed from the Gateway: what it is
SIDECAR = "xptb_gateway.json"
#: how long one Gateway answer stands for the update check (one build
#: reads it once for all its tiles)
LATEST_TTL_S = 3600.0

STORE = _PC.Store(_PC.GATEWAY_CHOICES)
_LATEST: dict[str, tuple[float, int]] = {}
#: THE RUN'S MEMORY (module doc, :func:`begin_run`): the ICAOs asked, the
#: ICAOs installed, and the ``(lat, lon, ICAO)`` patches sent back
_RUN: dict[str, set] = {"asked": set(), "installed": set(), "repatched": set()}
_RUN_LOCK = threading.Lock()


def begin_run() -> None:
    """A new run: nothing asked, installed or sent back yet."""
    with _RUN_LOCK:
        for seen in _RUN.values():
            seen.clear()


def _unasked(rows: list[dict]) -> list[dict]:
    """``rows`` whose airport this run has not asked about (now asked)."""
    with _RUN_LOCK:
        out = [r for r in rows if r["icao"] not in _RUN["asked"]]
        _RUN["asked"].update(r["icao"] for r in out)
    return out


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


def _global_entry(xplane_root: str, icao: str) -> list[str]:
    """The Global Airports block X-Plane draws ``icao`` from, ``[]`` when
    it draws another file."""
    from auto_patch_v2.airport import apt_dat as _apt
    chosen, block = _block(xplane_root, icao)
    if not chosen or chosen not in _apt.global_candidates(xplane_root):
        return []
    return block


def _graded_offer(patch_dir: str, icao: str) -> bool:
    """The patch of ``icao`` in ``patch_dir`` published generated decks /
    road bridges only a pack of its own can carry
    (``generated_publication``'s ``"offer"``)."""
    from auto_patch_v2.model.rebake import graded_surface_path
    if not patch_dir:
        return False
    try:
        with open(graded_surface_path(patch_dir, icao), encoding="utf-8") as fh:
            gen = (json.load(fh).get("provenance") or {}).get("generated") or {}
    except (OSError, ValueError, AttributeError):
        return False
    return bool(gen.get("offer"))


def _global_bridges(xplane_root: str, icao: str, patch_dir: str) -> dict | None:
    """The ``"bridges"`` row of ``icao``, or None: X-Plane draws it from
    a Global Airports entry and its patch (``patch_dir``) published
    generated decks / road bridges (:func:`_graded_offer`)."""
    if not patch_dir:
        return None
    block = _global_entry(xplane_root, icao)
    if not block or not _graded_offer(patch_dir, icao):
        return None
    return _row(icao, _name_of(block), "bridges")


def _early_bridges(xplane_root: str, icao: str, osm_root: str,
                   cache: dict) -> dict | None:
    """The ``"bridges"`` row of ``icao`` before its patch is built, or
    None: X-Plane draws it from a Global Airports entry and the tile's OSM
    feeds show a deck / road-bridge candidate (``planar/offer_witness``)."""
    block = _global_entry(xplane_root, icao)
    if not block or not osm_root:
        return None
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar import offer_witness as _OW
    law = Law.for_airport(icao)
    try:
        record = _OW.read_airport(icao, xplane_root, osm_root, law, cache=cache)
        notes = _OW.offer_notes(record, law) if record is not None else []
    except (OSError, ValueError) as exc:
        _say(2, f"  [gateway] {icao}: the early bridge check could not read "
                f"it ({exc})")
        return None
    if not notes:
        return None
    _say(1, f"  [gateway] {icao}: {len(notes)} deck / road-bridge "
            f"candidate(s) before the patch is built, e.g. {notes[0]}")
    return _row(icao, _name_of(block), "bridges")


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
           check_updates: bool, fetch: _api.Fetch | None = None,
           patch_dir: str = "") -> list[dict]:
    """THE REPORT (module doc): one row per airport of ``codes`` to
    offer, in ``codes`` order."""
    out: list[dict] = []
    for icao in dict.fromkeys(str(c).upper() for c in codes if c):
        if STORE.choice(_choice_key(xplane_root, icao)) == "never":
            continue
        row = _global_flatten(xplane_root, icao) \
            or _global_bridges(xplane_root, icao, patch_dir)
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


def _patch_dir(lat: int, lon: int) -> str:
    import O4_File_Names as FNAMES
    try:
        return FNAMES.patch_dir(lat, lon)
    except Exception:
        return ""


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
        rows = _offers(xplane_root, codes, check_updates=check, fetch=fetch,
                       patch_dir=_patch_dir(lat, lon))
        rows = _unasked(rows)
        _say_rows(rows, "its patch has")
        if rows:
            _announce(lat, lon, "found", rows)
        return rows
    except Exception as exc:
        _say(1, f"  [gateway] the Gateway airport check failed ({exc})")
        _say(2, traceback.format_exc())
        return []


def _say_rows(rows: list[dict], has: str) -> None:
    for r in rows:
        _say(0, f"  [gateway] {r['icao']}: "
                + ("X-Plane flattens this Global Airports entry "
                   "(1302 flatten 1), so the graded ground is not what "
                   "the sim draws; the app offers the Gateway's latest "
                   "version without the flag"
                   if r["reason"] == "flatten" else
                   f"{has} taxiway decks / road bridges that X-Plane's "
                   "Global Airports entry cannot carry; the app offers the "
                   "Gateway's latest version as a pack it can modify"
                   if r["reason"] == "bridges" else
                   f"the Gateway has a newer version "
                   f"({r['installed_id']} -> {r['latest_id']})"))


def gateway_early(tiles: _t.Iterable[tuple[int, int]],
                  xplane_root_of: _t.Callable[[int, int], str | None],
                  osm_root: str | None = None) -> list[dict]:
    """THE EARLY REPORT (module doc) for the run's ``tiles``, before any
    patch is built: one ``state="found"`` event per tile with a row, each
    airport once per run.  ``xplane_root_of(lat, lon)`` names the install;
    ``osm_root`` the OSM feeds (default ``O4_File_Names.OSM_dir``).
    Never raises."""
    out: list[dict] = []
    try:
        if osm_root is None:
            import O4_File_Names as FNAMES
            osm_root = FNAMES.OSM_dir
        for lat, lon in tiles:
            root = xplane_root_of(lat, lon)
            if not root:
                continue
            cache: dict = {}            # one parse of a tile's feeds
            rows = []
            for icao in _codes_of_tile(root, lat, lon):
                icao = icao.upper()
                with _RUN_LOCK:
                    if icao in _RUN["asked"]:
                        continue
                if STORE.choice(_choice_key(root, icao)) == "never":
                    continue
                row = _global_flatten(root, icao) \
                    or _early_bridges(root, icao, osm_root, cache)
                if row is not None:
                    rows.append(row)
            rows = _unasked(rows)
            _say_rows(rows, "its taxiways cross roads that need")
            if rows:
                _announce(lat, lon, "found", rows)
            out += rows
    except Exception as exc:
        _say(1, f"  [gateway] the early Gateway airport check failed ({exc})")
        _say(2, traceback.format_exc())
    return out


def stale_patches(lat: int, lon: int) -> list[str]:
    """The airports installed from the Gateway this run whose patch in
    tile ``lat``/``lon`` was still built against Global Airports (its
    graded surface publishes ``generated.offer``): the tile's vector step
    runs again, once per tile and airport.  Cheap when nothing was
    installed this run.  Never raises."""
    with _RUN_LOCK:
        installed = sorted(_RUN["installed"])
    if not installed:
        return []
    try:
        patch_dir = _patch_dir(lat, lon)
        stale = [icao for icao in installed if _graded_offer(patch_dir, icao)]
    except Exception:
        return []
    with _RUN_LOCK:
        stale = [i for i in stale if (int(lat), int(lon), i) not in _RUN["repatched"]]
        _RUN["repatched"].update((int(lat), int(lon), i) for i in stale)
    return stale


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
                          check_updates=True, fetch=fetch,
                          patch_dir=_patch_dir(la, lo))
            state = "ask" if rows else "none"
        elif action == "never":
            for icao in seen:
                STORE.remember(_choice_key(xplane_root, icao), "never")
                _WAIT.note_answer(xplane_root, icao, "never")
            state = "never"
        elif action == "later":
            for icao in seen:
                _WAIT.note_answer(xplane_root, icao, "later")
        elif action == "undo":
            for icao in picked:
                files += _undo(xplane_root, icao)
            state = "undone" if files else "none"
        else:
            for icao in seen:
                if icao not in picked:
                    STORE.remember(_choice_key(xplane_root, icao), "never")
                    _WAIT.note_answer(xplane_root, icao, "never")
            for icao in picked:
                _WAIT.note_answer(xplane_root, icao, "installing")
            for icao in picked:
                try:
                    done = _install(xplane_root, icao, fetch)
                except (_api.GatewayError, OSError) as exc:
                    errors.append(f"{icao}: {exc}")
                    _say(0, f"  [gateway] {icao}: the install failed ({exc})")
                    _WAIT.note_answer(xplane_root, icao, "failed")
                    continue
                _WAIT.note_answer(xplane_root, icao, "install")
                STORE.remember(_choice_key(xplane_root, icao), "")
                with _RUN_LOCK:
                    _RUN["installed"].add(icao)
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
