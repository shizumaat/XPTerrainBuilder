"""Optional tiered storage on other drives (owner RULINGS 2026-11-12g):

    "External drives become OPTIONAL TIERED STORAGE, set in Storage
    settings: each mounted volume is listed as a tier with its own size.
    Sharp imagery is stored on a tier while it is mounted.  When a volume
    is absent, the app falls back to dynamic download."

* :func:`volumes` -- the mounted volumes other than the app's own (the
  data folder's and the Custom Scenery folder's), with their size and
  free space.
* :data:`SETTING` -- ``storage_tiers``: ``{"<mount>": gigabytes}`` (JSON);
  a size above 0 makes the volume a tier.
* :func:`storage_tiers` / :func:`storage_tier_set` -- the engine commands
  Settings ▸ Storage's "Storage tiers" rows read and write (both apps).
* :func:`stash` -- a sharp texture the on-demand budget makes low-res
  again (``imagery_downgrade``) MOVES to a mounted tier with room
  (``<mount>/XPTerrainBuilder Tier/DDS_cache``, the texture cache's own
  layout) instead of being deleted.
* :func:`find` -- where a mounted tier holds a texture key; the full
  texture lookup (``imagery_ondemand._full_entry``) copies it back into
  the texture cache and lands it as before.

A tier is never linked into Custom Scenery or the World pack (RULINGS
2026-11-12a (1)): it is a store the app reads while it is mounted.  An
absent volume is no source, and the follow job downloads again.

No tile or airport is named here.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import string
import sys
import threading
import time
from typing import Any, Dict, List, Optional

__all__ = ["SETTING", "TIER_DIR", "volumes", "configured", "find", "stash",
           "storage_tiers", "storage_tier_set"]

SETTING = "storage_tiers"
#: The app's folder on a tier volume.
TIER_DIR = "XPTerrainBuilder Tier"
_DDS = "DDS_cache"
_GB = 1024 ** 3
_USED: Dict[str, int] = {}
_LOCK = threading.Lock()


def _settings() -> dict:
    try:
        import O4_Settings_Model as SM
        return SM.read_global_raw()
    except Exception:                       # no readable settings
        return {}


_READ: Dict[str, Any] = {}
#: How long a read of the setting is reused (the texture lookup asks per key).
_READ_S = 5.0


def configured(raw: Optional[dict] = None) -> Dict[str, float]:
    """``{mount: gigabytes}`` of the tiers set (size > 0)."""
    if raw is None:
        now = time.monotonic()
        with _LOCK:
            if _READ and now - _READ["at"] < _READ_S:
                return dict(_READ["tiers"])
        tiers = configured(_settings())
        with _LOCK:
            _READ.update(at=now, tiers=tiers)
        return dict(tiers)
    text = raw.get(SETTING, "") or ""
    try:
        data = json.loads(text) if isinstance(text, str) else dict(text)
    except (ValueError, TypeError):
        return {}
    out = {}
    for mount, size in (data.items() if isinstance(data, dict) else ()):
        with contextlib.suppress(TypeError, ValueError):
            if float(size) > 0:
                out[str(mount)] = float(size)
    return out


def _candidates() -> List[str]:
    if sys.platform == "darwin":
        roots = ["/Volumes"]
    elif os.name == "nt":
        return ["%s:\\" % letter for letter in string.ascii_uppercase
                if os.path.isdir("%s:\\" % letter)]
    else:
        user = os.environ.get("USER", "")
        roots = ["/media", "/mnt"] + (
            [os.path.join("/media", user), os.path.join("/run/media", user)]
            if user else [])
    out = []
    for root in roots:
        with contextlib.suppress(OSError):
            for name in sorted(os.listdir(root)):
                path = os.path.join(root, name)
                if os.path.isdir(path) and os.path.ismount(path):
                    out.append(path)
    return out


def _device(path: str) -> Optional[int]:
    while path and not os.path.exists(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    try:
        return os.stat(path or os.sep).st_dev
    except OSError:
        return None


def _own_devices() -> set:
    """The volumes the app itself lives on (never a tier)."""
    import O4_File_Names as FNAMES
    from . import world_commands as WORLD
    paths = [os.sep, FNAMES.current_data_root(), WORLD.scenery_dir_or_default()]
    return {d for d in (_device(p) for p in paths if p) if d is not None}


def volumes() -> List[Dict[str, Any]]:
    """``[{"mount", "name", "total_bytes", "free_bytes"}]``: the mounted
    volumes other than the app's own."""
    own = _own_devices()
    out = []
    for mount in _candidates():
        if _device(mount) in own:
            continue
        try:
            usage = shutil.disk_usage(mount)
        except OSError:
            continue
        out.append({"mount": mount,
                    "name": os.path.basename(mount.rstrip("/\\")) or mount,
                    "total_bytes": int(usage.total),
                    "free_bytes": int(usage.free)})
    return out


def _store(mount: str) -> str:
    return os.path.join(mount, TIER_DIR, _DDS)


def _mounted(mount: str) -> bool:
    return os.path.isdir(mount) and (os.path.ismount(mount)
                                     or os.name == "nt")


def _used(mount: str) -> int:
    """Bytes the tier holds (walked once a process, then kept current)."""
    with _LOCK:
        if mount in _USED:
            return _USED[mount]
    total = 0
    for root, _dirs, names in os.walk(_store(mount)):
        for name in names:
            with contextlib.suppress(OSError):
                total += os.lstat(os.path.join(root, name)).st_size
    with _LOCK:
        _USED[mount] = total
    return total


def _add_used(mount: str, delta: int) -> None:
    with _LOCK:
        _USED[mount] = max(0, _USED.get(mount, 0) + int(delta))


def find(key: Optional[str]) -> Optional[str]:
    """The tier entry of texture ``key`` on a mounted tier, or ``None``."""
    if not key:
        return None
    import O4_DDS_Cache as DDSC
    for mount in configured():
        if not _mounted(mount):
            continue                        # absent: download again
        path = DDSC.entry_path(key, _store(mount))
        if os.path.isfile(path):
            return path
    return None


def stash(key: Optional[str], entry: str) -> int:
    """Move the cache ``entry`` of ``key`` to the first mounted tier with
    room; the local bytes that freed (0: no tier took it, the caller
    deletes as before).  Copied under a partial name and checked before
    the local file goes."""
    if not key or not os.path.isfile(entry):
        return 0
    import O4_DDS_Cache as DDSC
    size = os.path.getsize(entry)
    for mount, gigabytes in configured().items():
        if not _mounted(mount) or _used(mount) + size > gigabytes * _GB:
            continue
        target = DDSC.entry_path(key, _store(mount))
        partial = target + ".part"
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(entry, partial)
            if os.path.getsize(partial) != size:
                raise OSError("short copy")
            os.replace(partial, target)
            os.remove(entry)
        except OSError:
            with contextlib.suppress(OSError):
                os.remove(partial)
            continue
        _add_used(mount, size)
        return size
    return 0


def storage_tiers(**_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``storage_tiers``: ``{"volumes": [{"mount", "name",
    "total_bytes", "free_bytes", "size_gb", "used_bytes", "mounted"}]}`` --
    every mounted volume other than the app's own, and every tier set
    whose volume is absent (``mounted`` False: its imagery is downloaded
    again while it is away)."""
    tiers = configured()
    rows = []
    for volume in volumes():
        size = tiers.pop(volume["mount"], 0.0)
        rows.append({**volume, "size_gb": size, "mounted": True,
                     "used_bytes": _used(volume["mount"]) if size else 0})
    for mount, size in sorted(tiers.items()):
        rows.append({"mount": mount, "name": os.path.basename(mount) or mount,
                     "total_bytes": 0, "free_bytes": 0, "size_gb": size,
                     "used_bytes": 0, "mounted": False})
    return {"volumes": rows}


def storage_tier_set(mount: str, size_gb: float = 0.0,
                     **_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``storage_tier_set``: the tier on ``mount`` set to
    ``size_gb`` (0 removes it; the files it holds stay on the drive)."""
    import O4_Settings_Model as SM
    mount = str(mount or "").strip()
    if not mount:
        raise ValueError("storage_tier_set needs a volume")
    size = float(size_gb or 0)
    if size < 0:
        raise ValueError("a tier's size is 0 or more GB")
    raw = _settings()
    data = configured(raw)
    if size:
        data[mount] = size
    else:
        data.pop(mount, None)
    SM.write_global({SETTING: json.dumps(data, sort_keys=True)})
    with _LOCK:
        _READ.clear()
    return storage_tiers()
