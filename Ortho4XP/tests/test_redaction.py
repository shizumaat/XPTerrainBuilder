"""Twins for :mod:`o4_engine.redaction` (issue #565, RULINGS 2026-10-12b):
planted secrets on the three path styles never survive, and what the
diagnosis needs (pack names, airports, tiles, coordinates) always does."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

from o4_engine import redaction  # noqa: E402
from o4_engine.redaction import Redactor  # noqa: E402

PACK = "c_USA - 100_airport - KPDX (Flightbeam)"

# (style, home, user, xplane root outside home, private file)
STYLES = [
    ("mac", "/Users/zelda", "zelda", "/Volumes/Big Disk/X-Plane 12",
     "/Users/zelda/Documents/Tax 2026/notes.txt"),
    ("windows", r"C:\Users\Zelda Q", "Zelda Q", r"D:\Games\X-Plane 12",
     r"C:\Users\Zelda Q\Documents\Tax 2026\notes.txt"),
    ("linux", "/home/zelda", "zelda", "/mnt/games/X-Plane 12",
     "/home/zelda/.config/tax-2026/notes.txt"),
]


def _join(style: str, root: str, *parts: str) -> str:
    return root + "".join(("\\" if style == "windows" else "/") + p
                          for p in parts)


@pytest.mark.parametrize("style,home,user,xplane,private", STYLES)
def test_home_and_user_never_survive_without_any_declaration(
        style, home, user, xplane, private):
    lines = [
        "  [pav-builder] KPDX: apt.dat " + _join(
            style, home, "X-Plane 12", "Custom Scenery", PACK,
            "Earth nav data", "apt.dat"),
        "    * Recycling OSM data from " + _join(
            style, home, "XPData", "OSM_data", "+40-130", "+45-123",
            "+45-123_airports.osm.bz2"),
        'Traceback: File "%s", line 12, in build' % private,
        "Legacy config read from " + private + " for user " + user,
        "KPDX   Portland International Airport   3 runways, "
        "lat= 45.58, lon= -122.60",
    ]
    out = Redactor().lines(lines)
    joined = "\n".join(out)
    assert "zelda" not in joined.lower()
    assert "Tax" not in joined and "tax-2026" not in joined
    # The diagnosis survives: pack name, data path below its root, the
    # file name of the private path, the airport row untouched.
    assert "<xplane>/Custom Scenery" in out[0] and PACK in out[0]
    assert out[0].rstrip().endswith("apt.dat")
    assert "<data>/OSM_data" in out[1] and "+45-123_airports.osm.bz2" in out[1]
    assert "<path>/notes.txt" in out[2] and "line 12, in build" in out[2]
    assert "<user>" in out[3]
    assert out[4] == lines[4]


@pytest.mark.parametrize("style,home,user,xplane,private", STYLES)
def test_declared_root_keeps_what_is_below_it(style, home, user, xplane,
                                              private):
    redactor = Redactor(roots={"xplane": [xplane]}, home=home, users=[user])
    inside = _join(style, xplane, "Custom Scenery", PACK, "Earth nav data",
                   "apt.dat")
    sibling = _join(style, xplane.rsplit("\\" if style == "windows" else "/",
                                         1)[0], "Private Stuff", "list.txt")
    out = redactor.line("read %s but not %s" % (inside, sibling))
    assert out.startswith("read <xplane>")
    assert PACK in out and "Earth nav data" in out
    assert "Private Stuff" not in out and "<path>/list.txt" in out
    assert "Big Disk" not in out and "Games" not in out and "games" not in out


def test_windows_root_matches_either_separator_and_any_case():
    redactor = Redactor(roots={"data": [r"E:\XP Data"]})
    assert redactor.line("wrote e:/xp data/Tiles/zOrtho4XP_+45-123/x.dsf") == \
        "wrote <data>/Tiles/zOrtho4XP_+45-123/x.dsf"


def test_a_home_outside_the_usual_places_is_declared():
    redactor = Redactor(home="/data/people/zelda")
    out = redactor.line("cfg /data/people/zelda/o4.cfg (zelda's)")
    assert out == "cfg <path>/o4.cfg (<user>'s)"


def test_a_name_one_line_reveals_is_removed_from_every_line():
    out = Redactor().lines(["build started by zelda",
                            "log at /home/zelda/log.txt"])
    assert out == ["build started by <user>", "log at <path>/log.txt"]


def test_tilde_root_and_unc_paths():
    redactor = Redactor()
    assert redactor.line("see ~/Documents/a b/c.txt") == "see <path>/c.txt"
    assert redactor.line("ran in /root/work/x.py") == "ran in <path>/x.py"
    assert redactor.line(r"share \\nas\zelda\private\x.tif") == \
        "share <path>/x.tif"


@pytest.mark.parametrize("line,gone,kept", [
    ("ProxyError: cannot reach http://bob:hunter2@proxy.corp.example:8080",
     ["bob", "hunter2", "corp.example"], ["ProxyError"]),
    ("env HTTPS_PROXY=http://10.1.2.3:3128 no_proxy=intra.example",
     ["10.1.2.3", "intra.example"], ["HTTPS_PROXY=<proxy>"]),
    ("GET https://bob:hunter2@tiles.example.com/1/2/3.jpg failed",
     ["bob", "hunter2"], ["tiles.example.com/1/2/3.jpg"]),
    ("GET https://tiles.example.com/x.jpg?apikey=S3CR3T&z=12&token=T0K failed",
     ["S3CR3T", "T0K"], ["z=12", "tiles.example.com"]),
    ("Authorization: Bearer abcdefghijklmnop123", ["abcdefghijklmnop123"], []),
    ("login password=hunter2 api_key: ABCDEF client-secret=xyz",
     ["hunter2", "ABCDEF", "xyz"], ["login"]),
    ("contact zelda.q+xp@mail.example.co.uk about it",
     ["zelda", "mail.example"], ["contact <email> about it"]),
])
def test_proxies_credentials_and_mail(line, gone, kept):
    out = Redactor().line(line)
    for secret in gone:
        assert secret not in out, out
    for text in kept:
        assert text in out, out


def test_host_name_is_removed_when_declared():
    redactor = Redactor(hosts=["Zeldas-MacBook-Pro.local", "Zeldas-MacBook-Pro"])
    assert redactor.line("worker on Zeldas-MacBook-Pro.local died") == \
        "worker on <host> died"


@pytest.mark.parametrize("line", [
    "   KHIO   Hillsboro Airport          3 runways, lat= 45.54, lon= -122.95",
    "TopologyException: Ring edge missing at -185.7206345310361 80.6879973296",
    "Step 1 : Building vector data for tile +45-123 : ",
    "densified to 1/3 arc-second (worst actionable ideal-bake error 0.981 m)",
    "[provenance] KHIO patch: engine=v2 sha=absent version=1.50.1834 "
    "code=312205fa412410f7 law=0410d08c80e9 dem=production[N45W123] "
    "insets=Aeroacres Airport:USGS3DEP,KHIO:USGS3DEP",
    "Building pad building13 at 47.44512, -122.30150 (47,029 m²): released",
    "inset(s) Walter Sutton's Private Strip_usgs3dep.tif cover only 0 %",
])
def test_the_diagnosis_is_left_alone(line):
    assert Redactor().line(line) == line


def test_redaction_is_idempotent():
    redactor = Redactor(roots={"xplane": ["/Volumes/Big Disk/X-Plane 12"]})
    lines = [
        "apt.dat /Volumes/Big Disk/X-Plane 12/Custom Scenery/%s/Earth nav "
        "data/apt.dat and /Volumes/Big Disk/secret/x.txt" % PACK,
        "the pack DSF /Users/zelda/X-Plane 12/Global Scenery/Global Airports/"
        "Earth nav data/+40-130/+47-123.dsf is newer than every dump under "
        "/Users/zelda/XPData/Airport_mod_cache/Global Airports (no fresh one)",
        "password=hunter2 via proxy=http://p:1 from a@b.example ~/x/y.txt",
    ]
    once = redactor.lines(lines)
    assert redactor.lines(once) == once
    assert "<xplane>/Global Scenery/Global Airports" in once[1]
    assert "<data>/Airport_mod_cache/Global Airports" in once[1]


def test_for_this_machine_knows_home_login_and_host(monkeypatch):
    monkeypatch.setenv("HOME", "/srv/accounts/zelda")
    monkeypatch.setenv("USERPROFILE", "/srv/accounts/zelda")
    monkeypatch.setenv("USER", "zeldaq")
    monkeypatch.setattr(redaction.socket, "gethostname", lambda: "zbox.lan")
    redactor = Redactor.for_this_machine({"data": ["/srv/xp"]})
    out = redactor.line("zeldaq on zbox.lan: /srv/accounts/zelda/a.cfg, "
                        "/srv/xp/Tiles/t.dsf")
    assert out == "<user> on <host>: <path>/a.cfg, <data>/Tiles/t.dsf"


def test_the_printed_rules_name_every_placeholder():
    printed = " ".join(redaction.RULES)
    for placeholder in ("<home>", "<user>", "<path>", "<proxy>",
                        "<redacted>", "<email>"):
        assert placeholder in printed
    assert "pack names" in redaction.KEPT and "coordinates" in redaction.KEPT
