"""#2249: the release's frozen tile and airport passes reach no server.

The Linux Beta 8 release failed at its deadline on busy Overpass servers;
a release must depend only on the bundle under test.  The passes run here
on the SOURCE entry (the same protocol, the same fixtures) with an audit
hook in every Python process of the run, which books and refuses any
DNS lookup or connection off loopback.  Both passes have imagery off, so
libcurl (below the hook) has nothing to fetch.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[1]
DRIVER = ENGINE.parent / "scripts" / "check_frozen_tile.py"

_GUARD = '''
import ipaddress, os, sys

def _loopback(host):
    if host in (None, "", "localhost"):
        return True
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return False

def _hook(event, args):
    if event == "socket.connect":
        if not isinstance(args[1], tuple):
            return                          # a unix socket
        host = args[1][0]
    elif event in ("socket.getaddrinfo", "socket.gethostbyname"):
        host = args[0]
    else:
        return
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if _loopback(host):
        return
    with open(os.environ["O4_NET_AUDIT_LOG"], "a", encoding="utf-8") as log:
        log.write("%s %s\\n" % (event, host))
    raise OSError("refused by the offline audit: %s" % host)

sys.addaudithook(_hook)
'''


def _driver():
    spec = importlib.util.spec_from_file_location("check_frozen_tile", DRIVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _audited_env(tmp_path):
    """The environment of a run whose every Python process is audited."""
    guard = tmp_path / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(_GUARD, encoding="utf-8",
                                            newline="\n")
    log = tmp_path / "network.log"
    path = os.pathsep.join(filter(None, [str(guard),
                                         os.environ.get("PYTHONPATH")]))
    return dict(os.environ, PYTHONPATH=path, O4_NET_AUDIT_LOG=str(log)), log


def test_the_audit_sees_a_lookup(tmp_path):
    """The instrument itself: a lookup is booked and refused."""
    env, log = _audited_env(tmp_path)
    code = ("import socket\n"
            "try:\n    socket.getaddrinfo('server.invalid', 443)\n"
            "except OSError as error:\n    print(error)\n")
    done = subprocess.run([sys.executable, "-c", code], env=env, text=True,
                          capture_output=True, timeout=60)
    assert "refused by the offline audit" in done.stdout
    assert "server.invalid" in log.read_text(encoding="utf-8")


def test_the_frozen_passes_reach_no_server(tmp_path):
    env, log = _audited_env(tmp_path)
    done = subprocess.run(
        [sys.executable, str(DRIVER), str(ENGINE / "Ortho4XP.py"),
         "--logs", str(tmp_path / "logs"),
         "--deadline", "280", "--airport-deadline", "280"],
        env=env, cwd=str(ENGINE), text=True, encoding="utf-8",
        errors="replace", capture_output=True, timeout=620)
    assert done.returncode == 0, done.stdout[-4000:] + done.stderr[-4000:]
    assert "AutoPatchBegin" in done.stdout
    assert not log.exists(), log.read_text(encoding="utf-8")


@pytest.mark.parametrize("line", ["    * Downloading OSM data for way",
                                  "   Refreshing the Geofabrik region index..."])
def test_a_network_attempt_in_the_log_fails_the_pass(line):
    assert len(_driver()._offline_breaches("before\n%s\nafter" % line)) == 1


def test_a_quiet_log_is_no_breach():
    assert _driver()._offline_breaches("   solve status=optimal") == []
