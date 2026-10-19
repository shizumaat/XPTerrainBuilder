"""A .lay ``timeout=`` sets that provider's HTTP timeout (#863).

USGS NAIP answers in 0.9-28 s; the global ``http_timeout`` (10 s) cuts
many of its answers short.  The key is parsed by the provider loader,
reaches every request of that provider, and a provider without it keeps
``http_timeout`` exactly.  Headless: scratch registry, stub session.
"""

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402
from PIL import Image  # noqa: E402

import O4_File_Names as FNAMES  # noqa: E402
import O4_Imagery_Utils as IMG  # noqa: E402

LAYER = (
    "request_type=wms\nwms_size=512\nwms_version=1.1.1\nepsg_code=3857\n"
    "url_prefix=https://wms.example/x?\nlayers=L\nimage_type=png\n"
)


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, format="PNG")
    return buf.getvalue()


class _Response:
    headers = {"Content-Type": "image/png"}

    def __init__(self):
        self.content = _png()

    def __str__(self):
        return "<Response [200]>"


class _Session:
    def __init__(self):
        self.timeouts = []

    def get(self, url, timeout=None, headers=None):
        self.timeouts.append(timeout)
        return _Response()


@pytest.fixture
def registry(tmp_path, monkeypatch):
    for name, folder in (("Provider_dir", "Providers"), ("Extent_dir", "Extents"),
                         ("Filter_dir", "Filters")):
        os.makedirs(str(tmp_path / folder))
        monkeypatch.setattr(FNAMES, name, str(tmp_path / folder))
    land = tmp_path / "Providers" / "Land"
    os.makedirs(str(land))
    for code, extra in (("SLOW", "timeout=45\n"), ("PLAIN", ""),
                        ("BAD", "timeout=soon\n")):
        (land / (code + ".lay")).write_text(LAYER + extra, encoding="utf-8",
                                                   newline="\n")
    monkeypatch.setattr(IMG, "providers_dict", {})
    IMG.initialize_providers_dict()
    return IMG.providers_dict


def test_the_key_is_parsed_and_an_invalid_one_falls_back(registry):
    assert registry["SLOW"]["timeout"] == 45.0
    assert "timeout" not in registry["PLAIN"]
    assert "timeout" not in registry["BAD"]  # a bad value never blocks the provider
    assert IMG.provider_timeout("0") is None
    assert IMG.provider_timeout("-3") is None
    assert IMG.provider_timeout("inf") is None
    assert IMG.provider_timeout("2.5") == 2.5


def test_each_request_carries_its_providers_timeout(registry):
    bbox = (0.0, 0.0, 100.0, 100.0)
    for code, expected in (("SLOW", 45.0), ("PLAIN", IMG.http_timeout),
                           ("BAD", IMG.http_timeout)):
        session = _Session()
        ok, _ = IMG.get_wms_image(bbox, 4, 4, registry[code], session)
        assert ok == 1 and session.timeouts == [expected], code


def test_default_is_the_global_http_timeout_read_at_call_time(monkeypatch):
    monkeypatch.setattr(IMG, "http_timeout", 7)
    session = _Session()
    IMG.http_request_to_image(4, 4, "https://t.example/1.png", None, session)
    assert session.timeouts == [7]


def test_the_shipped_naip_definition_waits_for_the_slow_server():
    path = os.path.join(FNAMES.Provider_dir, "United_States", "NAIP.lay")
    with open(path, encoding="utf-8") as handle:
        keys = dict(line.strip().split("=", 1) for line in handle
                    if "=" in line and not line.startswith("#"))
    assert IMG.provider_timeout(keys["timeout"]) >= 30
