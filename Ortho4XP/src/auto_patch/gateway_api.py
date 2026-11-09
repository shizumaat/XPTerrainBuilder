"""THE X-PLANE SCENERY GATEWAY, read (issue #1989).

Laminar's public JSON API (``gateway.x-plane.com/apiv1``; confirmed on
KEUG 2026-11-09, fixtures in ``tests/fixtures/gateway``):

* ``GET /airport/{ICAO}`` -> ``{"airport": {..., "recommendedSceneryId":
  N, "scenery": [...]}}`` — the airport and the scenery the Gateway
  recommends (the version X-Plane ships next);
* ``GET /scenery/{id}`` -> ``{"scenery": {..., "masterZipBlob": base64}}``
  — the upload: a zip holding ``ICAO.dat`` (the apt.dat block),
  ``ICAO.txt`` and, for a 3D airport, ``ICAO_Scenery_Pack.zip`` (the
  ready pack: ``Earth nav data/apt.dat`` and its DSF).

Every call is the user's explicit action or a build's update check, never
a test's: ``fetch`` (``url -> bytes``) is the one network seam and tests
hand in the fixtures.  A large upload can answer 502 (PANC, 2026-11-09):
any failure raises :class:`GatewayError` with the user's sentence.
"""
from __future__ import annotations

import base64
import io
import json
import posixpath
import typing as _t
import zipfile

__all__ = ["API_ROOT", "GatewayError", "airport", "recommended_id",
           "scenery", "pack_files"]

API_ROOT = "https://gateway.x-plane.com/apiv1"
TIMEOUT_S = 90
#: the most one pack may unpack to (a Gateway pack is ~0.1–20 MB)
MAX_PACK_BYTES = 400 * 1024 * 1024

Fetch = _t.Callable[[str], bytes]


class GatewayError(RuntimeError):
    """The Gateway could not be read; ``str()`` is the user's sentence."""


def _http_fetch(url: str) -> bytes:
    import requests
    try:
        answer = requests.get(url, timeout=TIMEOUT_S,
                              headers={"User-Agent": "XPTerrainBuilder"})
    except requests.RequestException as exc:
        raise GatewayError(f"the X-Plane Gateway could not be reached "
                           f"({type(exc).__name__})") from None
    if answer.status_code != 200:
        raise GatewayError(f"the X-Plane Gateway answered HTTP "
                           f"{answer.status_code}")
    return answer.content


def _get(path: str, key: str, fetch: Fetch | None) -> dict:
    body = (fetch or _http_fetch)(f"{API_ROOT}/{path}")
    try:
        doc = json.loads(body)
    except ValueError:
        raise GatewayError("the X-Plane Gateway answered with a page, "
                           "not data") from None
    obj = doc.get(key) if isinstance(doc, dict) else None
    if not isinstance(obj, dict):
        raise GatewayError(f"the X-Plane Gateway has no {key} at {path}")
    return obj


def airport(icao: str, fetch: Fetch | None = None) -> dict:
    """The Gateway's record of ``icao`` (``/airport/{ICAO}``)."""
    return _get(f"airport/{icao.upper()}", "airport", fetch)


def recommended_id(record: dict) -> int:
    """The scenery id the Gateway recommends for an airport record, 0
    when it names none."""
    try:
        return int(record.get("recommendedSceneryId") or 0)
    except (TypeError, ValueError):
        return 0


def scenery(scenery_id: int, fetch: Fetch | None = None) -> dict:
    """One upload (``/scenery/{id}``), its zip still base64."""
    return _get(f"scenery/{int(scenery_id)}", "scenery", fetch)


def _safe(name: str) -> str:
    """A zip member's path, or ``""`` when it would leave the pack."""
    norm = posixpath.normpath(name.replace("\\", "/"))
    if (not norm or norm.startswith(("/", "../")) or norm == ".."
            or ":" in norm.split("/")[0]):
        return ""
    return norm


def _members(zf: zipfile.ZipFile, prefix: str = "") -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    total = 0
    for info in zf.infolist():
        if info.is_dir() or not info.filename.startswith(prefix):
            continue
        rel = _safe(info.filename[len(prefix):])
        if not rel:
            continue
        total += info.file_size
        if total > MAX_PACK_BYTES:
            raise GatewayError("the Gateway pack is larger than expected")
        out[rel] = zf.read(info)
    return out


def pack_files(record: dict) -> dict[str, bytes]:
    """The custom airport pack of one upload: ``{relative path: bytes}``.

    The upload's own ``*_Scenery_Pack.zip`` when it has one (its top
    folder dropped); a 2D upload has only ``ICAO.dat``, which becomes the
    pack's ``Earth nav data/apt.dat``."""
    try:
        outer = zipfile.ZipFile(io.BytesIO(
            base64.b64decode(record.get("masterZipBlob") or "")))
    except (ValueError, zipfile.BadZipFile):
        raise GatewayError("the Gateway upload is not a zip") from None
    icao = str(record.get("icao") or "").upper()
    names = outer.namelist()
    inner = [n for n in names if n.lower().endswith("_scenery_pack.zip")]
    if inner:
        try:
            pack = zipfile.ZipFile(io.BytesIO(outer.read(inner[0])))
        except zipfile.BadZipFile:
            raise GatewayError("the Gateway scenery pack is not a zip") from None
        tops = {n.split("/", 1)[0] for n in pack.namelist() if "/" in n}
        prefix = (tops.pop() + "/") if len(tops) == 1 else ""
        files = _members(pack, prefix)
        if any(p.lower() == "earth nav data/apt.dat" for p in files):
            return files
    dat = [n for n in names if n.upper() == f"{icao}.DAT"]
    if not dat:
        raise GatewayError(f"the Gateway upload has no apt.dat for {icao}")
    return {"Earth nav data/apt.dat": outer.read(dat[0])}
