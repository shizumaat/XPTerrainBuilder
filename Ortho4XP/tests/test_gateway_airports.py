"""#1989: Global Airports entries X-Plane flattens, the Gateway install
that replaces them without the flag, and the update watch.

No network: every Gateway answer is the KEUG fixture recorded on
2026-11-09 (``tests/fixtures/gateway``: ``/apiv1/airport/KEUG`` and
``/apiv1/scenery/110181``) or a variant built from it.  Every install
goes into a temp X-Plane folder, never the user's.
"""
from __future__ import annotations

import base64
import dataclasses
import io
import json
import os
import sys
import time
import types
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import O4_UI_Utils as UI  # noqa: E402
from auto_patch import gateway_api as API  # noqa: E402
from auto_patch import gateway_stage as GW  # noqa: E402
from auto_patch_v2.airport import apt_dat as APT  # noqa: E402
from auto_patch_v2.airport import apt_flatten as AF  # noqa: E402
from o4_engine import events as EV  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures",
                   "gateway")


def _load(name: str) -> bytes:
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


def _with_flatten(scenery: bytes, new_id: int | None = None) -> bytes:
    """The KEUG upload with ``1302 flatten 1`` added to its pack apt.dat."""
    doc = json.loads(scenery)
    outer = zipfile.ZipFile(io.BytesIO(base64.b64decode(
        doc["scenery"]["masterZipBlob"])))
    inner_name = [n for n in outer.namelist() if n.endswith(".zip")][0]
    inner = zipfile.ZipFile(io.BytesIO(outer.read(inner_name)))
    buf_inner = io.BytesIO()
    with zipfile.ZipFile(buf_inner, "w") as out:
        for info in inner.infolist():
            data = inner.read(info)
            if info.filename.endswith("apt.dat"):
                data = data.replace(b"1302 city Eugene",
                                    b"1302 city Eugene\n1302 flatten 1", 1)
            out.writestr(info.filename, data)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as out:
        for n in outer.namelist():
            out.writestr(n, buf_inner.getvalue() if n == inner_name
                         else outer.read(n))
    doc["scenery"]["masterZipBlob"] = base64.b64encode(buf.getvalue()).decode()
    if new_id:
        doc["scenery"]["sceneryId"] = new_id
    return json.dumps(doc).encode()


class Gateway:
    """The fixture Gateway: ``url -> bytes``, every call counted."""

    def __init__(self, flatten: bool = True):
        self.calls: list[str] = []
        self.recommended = 110181
        self.flatten = flatten

    def __call__(self, url: str) -> bytes:
        self.calls.append(url)
        if url.endswith("/airport/KEUG"):
            doc = json.loads(_load("keug_airport.json"))
            doc["airport"]["recommendedSceneryId"] = self.recommended
            return json.dumps(doc).encode()
        if url.endswith(f"/scenery/{self.recommended}"):
            raw = _load("keug_scenery.json")
            return _with_flatten(raw) if self.flatten else raw
        raise API.GatewayError("HTTP 404")


GLOBAL_APT = (
    "I\n1200 test\n\n"
    "1    373 0 0 KEUG Mahlon Sweet Fld\n1302 flatten 1\n"
    "100 45.72 1 0 0.25 0 2 1 03 44.11 -123.22 0 0 2 0 0 0 21 44.13 -123.21 0 0 2 0 0 0\n"
    "110 1 0.25 0.00 Pad\n111 44.12 -123.21\n113 44.121 -123.211\n\n"
    "1    100 0 0 KXXX Flat Field\n"
    "110 1 0.25 0.00 Pad\n111 44.2 -123.3\n113 44.21 -123.31\n\n99\n")


@pytest.fixture
def xp(tmp_path, monkeypatch):
    root = tmp_path / "X-Plane 12"
    ga = root / "Global Scenery" / "Global Airports" / "Earth nav data"
    ga.mkdir(parents=True)
    (ga / "apt.dat").write_text(GLOBAL_APT, encoding="utf-8", newline="")
    custom = root / "Custom Scenery"
    custom.mkdir()
    (custom / "Other Airport").mkdir()
    (custom / "scenery_packs.ini").write_text(
        "I\n1000 Version\nSCENERY\n\n"
        "SCENERY_PACK Custom Scenery/Other Airport/\n"
        "SCENERY_PACK *GLOBAL_AIRPORTS*\n"
        "SCENERY_PACK Custom Scenery/zzMesh/\n", encoding="utf-8", newline="")
    from auto_patch import pack_choice as PC
    monkeypatch.setattr(PC, "store_path",
                        lambda name: str(tmp_path / "prefs" / name))
    seen: list = []
    monkeypatch.setattr(UI, "gateway_airports", lambda **f: seen.append(f))
    monkeypatch.setattr(UI, "vprint", lambda *a, **k: None)
    monkeypatch.setattr(GW, "_codes_of_tile",
                        lambda root, lat, lon: ["KEUG", "KXXX"])
    GW._LATEST.clear()
    APT._SELECTION.clear()
    return types.SimpleNamespace(root=str(root), custom=str(custom),
                                 events=seen)


# ── the Gateway API ─────────────────────────────────────────────────────

def test_the_recorded_keug_answers_read():
    gw = Gateway(flatten=False)
    rec = API.airport("keug", gw)
    assert API.recommended_id(rec) == 110181
    assert gw.calls == [f"{API.API_ROOT}/airport/KEUG"]
    files = API.pack_files(API.scenery(110181, gw))
    assert "Earth nav data/apt.dat" in files
    assert "Earth nav data/+40-130/+44-124.dsf" in files
    assert not AF.carries_flatten(files["Earth nav data/apt.dat"])


def test_a_2d_upload_becomes_an_apt_dat_pack():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("KXXX.dat", "I\n1200 x\n\n1 100 0 0 KXXX F\n\n99\n")
        z.writestr("KXXX.txt", "notes")
    files = API.pack_files({"icao": "KXXX", "masterZipBlob":
                            base64.b64encode(buf.getvalue()).decode()})
    assert list(files) == ["Earth nav data/apt.dat"]


def test_a_member_leaving_the_pack_is_dropped():
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("K_Scenery_Pack/Earth nav data/apt.dat", "x")
        z.writestr("K_Scenery_Pack/../../evil.txt", "x")
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr("K_Scenery_Pack.zip", inner.getvalue())
    files = API.pack_files({"icao": "K", "masterZipBlob":
                            base64.b64encode(outer.getvalue()).decode()})
    assert list(files) == ["Earth nav data/apt.dat"]


def test_a_gateway_error_page_is_a_sentence():
    with pytest.raises(API.GatewayError, match="page"):
        API.airport("PANC", lambda url: b"<html>502 Bad Gateway</html>")


# ── detect ──────────────────────────────────────────────────────────────

def test_a_flattened_global_entry_is_offered(xp):
    rows = GW._offers(xp.root, ["KEUG", "KXXX"], check_updates=True,
                     fetch=Gateway())
    assert [(r["icao"], r["reason"], r["name"]) for r in rows] == [
        ("KEUG", "flatten", "Mahlon Sweet Fld")]


def test_the_build_announces_once_and_never_installs(xp):
    gw = Gateway()
    rows = GW.gateway_stage(44, -124, xp.root, ["KEUG", "KXXX"], fetch=gw)
    assert [r["icao"] for r in rows] == ["KEUG"]
    assert xp.events[0]["lat"] == 44 and xp.events[0]["lon"] == -124
    assert [e["state"] for e in xp.events] == ["found"]
    assert gw.calls == []
    assert sorted(os.listdir(xp.custom)) == ["Other Airport",
                                             "scenery_packs.ini"]


# ── install, watch, undo ────────────────────────────────────────────────

def test_install_writes_the_pack_without_flatten(xp):
    os.makedirs(os.path.join(xp.custom, "Unlisted Pack"))
    done = GW._install(xp.root, "KEUG", Gateway())
    pack = os.path.join(xp.custom, "KEUG Gateway Airport")
    assert done["pack_root"] == pack and done["scenery_id"] == 110181
    apt = os.path.join(pack, "Earth nav data", "apt.dat")
    assert done["flatten"] == "removed"
    assert not AF.carries_flatten(open(apt, "rb").read())
    assert AF.carries_flatten(open(apt + ".anchor_bak", "rb").read())
    assert os.path.isfile(os.path.join(pack, "Earth nav data", "+40-130",
                                       "+44-124.dsf"))
    side = GW._read_sidecar(pack)
    assert side["icao"] == "KEUG" and side["scenery_id"] == 110181
    ini = open(os.path.join(xp.custom, "scenery_packs.ini"),
               encoding="utf-8").read().splitlines()
    i = ini.index("SCENERY_PACK Custom Scenery/KEUG Gateway Airport/")
    assert i < ini.index("SCENERY_PACK *GLOBAL_AIRPORTS*")
    assert not [ln for ln in ini if "Unlisted Pack" in ln], \
        "only the installed pack is filed"
    # X-Plane now draws the pack: no flatten offer, and the pack is watched
    assert APT.select_apt_dat(xp.root, "KEUG") == apt
    assert GW._installed_pack(xp.root, "KEUG") == pack
    assert GW._offers(xp.root, ["KEUG"], check_updates=False) == []


def test_a_newer_gateway_version_is_offered_and_updates_in_place(xp):
    gw = Gateway()
    GW._install(xp.root, "KEUG", gw)
    GW._LATEST.clear()
    assert GW._offers(xp.root, ["KEUG"], check_updates=True, fetch=gw) == []
    gw.recommended = 120000
    GW._LATEST.clear()
    [row] = GW._offers(xp.root, ["KEUG"], check_updates=True, fetch=gw)
    assert (row["reason"], row["installed_id"], row["latest_id"]) == (
        "update", 110181, 120000)
    GW._install(xp.root, "KEUG", gw)
    pack = os.path.join(xp.custom, "KEUG Gateway Airport")
    assert GW._read_sidecar(pack)["scenery_id"] == 120000
    assert sorted(n for n in os.listdir(xp.custom)
                  if not n.endswith(".o4bak")) == [
        "KEUG Gateway Airport", "Other Airport", "scenery_packs.ini"]
    ini = open(os.path.join(xp.custom, "scenery_packs.ini"), encoding="utf-8").read()
    assert ini.count("KEUG Gateway Airport") == 1


def test_the_lane_build_never_reads_the_gateway(xp, monkeypatch):
    gw = Gateway()
    GW._install(xp.root, "KEUG", gw)
    gw.calls.clear()
    GW._LATEST.clear()
    monkeypatch.setenv("O4_PACK_WRITES", "measure_only")
    assert GW.gateway_stage(44, -124, xp.root, ["KEUG"], fetch=gw) == []
    assert gw.calls == []


def test_a_foreign_pack_of_that_name_is_never_replaced(xp):
    os.makedirs(os.path.join(xp.custom, "KEUG Gateway Airport"))
    with pytest.raises(API.GatewayError, match="not a pack"):
        GW._install(xp.root, "KEUG", Gateway())


def test_the_command_installs_the_ticked_and_remembers_the_rest(xp):
    out = GW.gateway_choice(xp.root, "install", 44, -124, items=["KEUG"],
                            shown=["KEUG", "KXXX"], fetch=Gateway())
    assert out["state"] == "installed" and out["error"] == ""
    assert out["items"][0]["pack"] == "KEUG Gateway Airport"
    assert GW.STORE.choice(GW._choice_key(xp.root, "KXXX")) == "never"
    undo = GW.gateway_choice(xp.root, "undo", 44, -124, items=["KEUG"])
    assert undo["state"] == "undone"
    apt = AF.apt_dat_of(os.path.join(xp.custom, "KEUG Gateway Airport"))
    assert AF.carries_flatten(open(apt, "rb").read())


def test_never_silences_and_ask_reports(xp):
    ask = GW.gateway_choice(xp.root, "ask", 44, -124, fetch=Gateway())
    assert ask["state"] == "ask" and ask["items"][0]["icao"] == "KEUG"
    GW.gateway_choice(xp.root, "never", 44, -124, shown=["KEUG"])
    assert GW.gateway_choice(xp.root, "ask", 44, -124,
                             fetch=Gateway())["state"] == "none"


def test_a_failed_install_says_why(xp):
    def down(url):
        raise API.GatewayError("the X-Plane Gateway answered HTTP 502")
    out = GW.gateway_choice(xp.root, "install", 44, -124, items=["KEUG"],
                            fetch=down)
    assert out["state"] == "failed" and "502" in out["error"]
    assert not os.path.exists(os.path.join(xp.custom, "KEUG Gateway Airport"))
    assert GW.gateway_choice(None, "ask")["state"] == "failed"


# ── the wire ────────────────────────────────────────────────────────────

def test_the_wire_name_fields_and_flag():
    assert EV.GatewayAirports.__name__ == "GatewayAirports"
    assert [f.name for f in dataclasses.fields(EV.GatewayAirports)
            if f.name not in ("seq", "ts")] == [
        "lat", "lon", "items", "files", "state", "error"]
    assert "gateway_airports" in EV.CAPABILITIES


def test_the_swift_client_and_the_forwarder_match_it():
    from o4_engine import parallel as P
    assert "GatewayAirports" in P._FORWARDED_EVENT_TYPES
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "OrthoEngineClient.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()
    assert 'case "GatewayAirports"' in text and '"gateway_airports"' in text


def test_the_command_is_registered_and_never_blocks(monkeypatch):
    from o4_engine import jsonl as J
    from o4_engine import xplane_root as PO
    from o4_engine.session import EngineSession

    session = EngineSession()
    assert J._build_handlers(session)["gateway_airports"] == \
        session.gateway_airports
    got = []
    session.subscribe(got.append)
    monkeypatch.setattr(PO, "xplane_root_for", lambda lat, lon: "/xp")

    def fake(root, action, lat, lon, items=None, shown=None):
        UI.gateway_airports(lat=lat, lon=lon, state="never",
                            items=[{"icao": i} for i in shown or ()],
                            error=root)

    monkeypatch.setattr(GW, "gateway_choice", fake)
    monkeypatch.setattr(UI, "engine_session", session)
    assert session.gateway_airports("never", 44, -124,
                                    shown=["KEUG"]) == {"status": "started"}
    deadline = time.time() + 10
    while not [e for e in got if isinstance(e, EV.GatewayAirports)] \
            and time.time() < deadline:
        time.sleep(0.01)
    [ev] = [e for e in got if isinstance(e, EV.GatewayAirports)]
    assert ev.state == "never" and ev.items == [{"icao": "KEUG"}]
    assert ev.error == "/xp"


def test_the_graded_airports_are_the_tiles_patches(tmp_path, monkeypatch):
    import O4_File_Names as FNAMES
    for name in ("KEUG_auto.patch.osm", "KXXX_mine.patch.osm", "notes.txt"):
        (tmp_path / name).write_text("", encoding="utf-8", newline="")
    monkeypatch.setattr(FNAMES, "patch_dir", lambda lat, lon: str(tmp_path))
    assert GW._graded_codes(44, -124) == ["KEUG", "KXXX"]
    monkeypatch.setattr(FNAMES, "patch_dir",
                        lambda lat, lon: str(tmp_path / "none"))
    assert GW._graded_codes(44, -124) == []


def test_a_built_tile_runs_the_check_off_the_build_thread(monkeypatch):
    from o4_engine import session as S
    from o4_engine import xplane_root as PO
    seen = []
    monkeypatch.setattr(PO, "xplane_root_for", lambda lat, lon: "/xp")
    monkeypatch.setattr(GW, "gateway_stage",
                        lambda lat, lon, root: seen.append((lat, lon, root)))
    S._offer_gateway_airports(44, -124)
    deadline = time.time() + 10
    while not seen and time.time() < deadline:
        time.sleep(0.01)
    assert seen == [(44, -124, "/xp")]
