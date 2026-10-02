"""Twin for the suite's network guard (tests/conftest.py, issue #122).

Windows CI hung three times to the 600 s pytest-timeout.  The per-test
stack dump named the frame: a LIVE Overpass POST —
``O4_OSM_Utils._post_overpass_query_reporting_progress`` joining its
``send_request`` thread, which sat in ``ssl.read`` — reached from
``test_pack_set_change_refetches_a_cached_inset`` (the inset footprint
mask) and ``test_generate_then_regenerate_reuses`` (the airports-tile
prefetch).  The read timeout is the Overpass query timeout + 30 s and
``get_overpass_data`` retries eight times with back-off, so a slow server
is a hang the size of the test timeout.

These twins pin the guard's contract deterministically, with no network:
the SAME frame now ends in well under five seconds with a named refusal
the retry loop does not swallow, loopback stays reachable, and every
refusal is booked for the teardown that fails the reaching test.
"""
import os
import pathlib
import socket
import sys
import threading
import time

import pytest

import conftest


def _drop_refusals_since(start):
    """Un-book the refusals THIS twin provoked on purpose, so the autouse
    teardown does not fail the twin for doing its job."""
    with conftest._NETWORK_REFUSALS_LOCK:
        mine = conftest._NETWORK_REFUSALS[start:]
        del conftest._NETWORK_REFUSALS[start:]
    return mine


def _booked():
    with conftest._NETWORK_REFUSALS_LOCK:
        return len(conftest._NETWORK_REFUSALS)


def test_the_guard_is_armed_in_this_process():
    assert getattr(socket, "_o4_suite_network_guard", False)


def test_the_hung_frame_now_refuses_in_seconds_not_minutes():
    """The #122 frame, end to end: get_overpass_data -> the helper thread's
    session.post.  The refusal is NOT an OSError, so neither requests nor
    the eight-attempt back-off loop turns it into a wait."""
    import O4_OSM_Utils as OSM

    start = _booked()
    t0 = time.monotonic()
    try:
        with pytest.raises(conftest.SuiteNetworkRefused):
            OSM.get_overpass_data(
                'way["building"]', (60.70, -135.10, 60.72, -135.05))
    finally:
        refused = _drop_refusals_since(start)
    assert time.monotonic() - t0 < 5.0
    assert refused, "the refusal was not booked for the teardown"
    # The first reach is the server-selection probe (a pool thread per
    # server); either way it is an Overpass host, refused and booked.
    overpass_hosts = {url.split("/")[2] for url in OSM.overpass_servers.values()}
    assert {host for (_how, host, _port, _thread) in refused} <= overpass_hosts


@pytest.mark.parametrize("address", [("192.0.2.1", 80),       # TEST-NET-1
                                     ("2001:db8::1", 443)])  # documentation
def test_a_connect_to_a_routable_address_refuses_at_once(address):
    family = socket.AF_INET6 if ":" in address[0] else socket.AF_INET
    try:
        sock = socket.socket(family, socket.SOCK_STREAM)
    except OSError:                                     # pragma: no cover
        pytest.skip("no IPv6 on this runner")
    start = _booked()
    t0 = time.monotonic()
    try:
        with pytest.raises(conftest.SuiteNetworkRefused) as caught:
            sock.connect(address)
        assert not isinstance(caught.value, OSError)
        with pytest.raises(conftest.SuiteNetworkRefused):
            sock.connect_ex(address)
    finally:
        sock.close()
        refused = _drop_refusals_since(start)
    assert time.monotonic() - t0 < 1.0
    assert [how for (how, *_rest) in refused] == ["connect to", "connect to"]


def test_a_dns_lookup_of_a_remote_host_refuses():
    start = _booked()
    try:
        with pytest.raises(conftest.SuiteNetworkRefused):
            socket.getaddrinfo("overpass-api.de", 443)
    finally:
        refused = _drop_refusals_since(start)
    assert refused[0][:3] == ("DNS lookup of", "overpass-api.de", 443)


def test_loopback_stays_reachable():
    """A test's own local server is lawful."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(("127.0.0.1", port))
        assert socket.getaddrinfo("localhost", port)
    finally:
        client.close()
        server.close()


def test_a_background_thread_refusal_is_booked_with_its_thread_name():
    start = _booked()
    errors = []

    def reach():
        try:
            socket.getaddrinfo("example.org", 80)
        except conftest.SuiteNetworkRefused as exc:
            errors.append(exc)

    worker = threading.Thread(target=reach, name="twin-background-reach")
    worker.start()
    worker.join(5)
    refused = _drop_refusals_since(start)
    assert errors
    assert refused[0][3] == "twin-background-reach"


@pytest.mark.parametrize("host,expected", [
    (None, True), ("", True), ("localhost", True), ("127.0.0.1", True),
    ("127.8.9.10", True), ("::1", True), ("[::1]", True), ("0.0.0.0", True),
    (b"localhost", True), ("app.localhost", True),
    ("overpass-api.de", False), ("192.0.2.1", False), ("10.0.0.1", False),
    ("2001:db8::1", False),
])
def test_the_loopback_predicate(host, expected):
    assert conftest.is_loopback_host(host) is expected


# ---------------------------------------------------------------------------
# Issue #146: the guard must arm ONLY under pytest.  Ten tools import this
# conftest outside pytest for ``xplane_root()`` alone; before the fix the
# import armed the socket refusal and stripped the proxy variables in THEIR
# process, and every later network read died with a message that reads as
# transient (the harness had been offline since #122).  The three twins
# below pin both halves of the contract: armed at conftest IMPORT under
# pytest — controller and xdist worker alike, which is what #122 requires
# so no test module can import ``requests`` ahead of the guard — and inert
# on a plain ``import conftest``.
# ---------------------------------------------------------------------------

_NON_PYTEST_IMPORT_PROBE = """\
import os, socket, sys
sys.path.insert(0, sys.argv[1])
import conftest
print("armed=%r" % bool(getattr(socket, "_o4_suite_network_guard", False)))
print("armed_at_import=%r" % bool(conftest._GUARD_ARMED_AT_IMPORT))
print("under_pytest=%r" % bool(conftest.running_under_pytest()))
print("proxy=%r" % os.environ.get("HTTPS_PROXY"))
print("lower_proxy=%r" % os.environ.get("https_proxy"))
print("xplane_root=%r" % bool(conftest.xplane_root()))
"""


def test_a_non_pytest_import_of_conftest_neither_arms_nor_strips_proxies():
    """Issue #146 at the derivation site.  No connection is made here."""
    import subprocess

    environment = dict(os.environ)
    environment["HTTPS_PROXY"] = "http://proxy.invalid:3128"
    environment["https_proxy"] = "http://proxy.invalid:3128"
    environment.pop("PYTEST_CURRENT_TEST", None)
    environment.pop("PYTEST_XDIST_WORKER", None)
    environment.pop("O4_SUITE_ALLOW_NETWORK", None)
    completed = subprocess.run(
        [sys.executable, "-c", _NON_PYTEST_IMPORT_PROBE,
         str(pathlib.Path(conftest.__file__).parent)],
        capture_output=True, text=True, env=environment, timeout=300)
    assert completed.returncode == 0, completed.stderr
    reported = dict(
        line.split("=", 1) for line in completed.stdout.split("\n") if "=" in line)
    assert reported["under_pytest"] == "False", completed.stdout
    assert reported["armed"] == "False", completed.stdout
    assert reported["armed_at_import"] == "False", completed.stdout
    assert reported["proxy"] == "'http://proxy.invalid:3128'", completed.stdout
    assert reported["lower_proxy"] == "'http://proxy.invalid:3128'", completed.stdout
    # The reason the tools import conftest at all still works.
    assert reported["xplane_root"] == "True", completed.stdout


#: The OTHER two import-time side effects (#175).  Same shape as the probe
#: above, asking the two questions that matter in a TOOL's process: did the
#: ambient data root survive, and is ``keyring`` still the real module (i.e.
#: absent from ``sys.modules`` until something imports it for real)?
_NON_PYTEST_SIDE_EFFECT_PROBE = """\
import os, sys
sys.path.insert(0, sys.argv[1])
import conftest
print("under_pytest=%r" % bool(conftest.running_under_pytest()))
print("data_root=%r" % os.environ.get("ORTHO4XP_DATA_ROOT"))
print("keyring_faked=%r" % bool(
    "keyring" in sys.modules
    and not hasattr(sys.modules["keyring"], "__file__")))
print("xplane_root=%r" % bool(conftest.xplane_root()))
"""

_PROBE_DATA_ROOT = "/tmp/o4-175-ambient-data-root"


def test_a_non_pytest_import_of_conftest_touches_neither_data_root_nor_keyring():
    """Issue #175 at the same derivation site as #146.

    A tool that imports conftest for ``xplane_root()`` alone must keep the
    data root the shell gave it — a root that moves under a tool is the
    PRIVATE-CORPUS hazard the harness refuses everywhere else — and must
    keep the real ``keyring``, since a tool legitimately signs in."""
    import subprocess

    environment = dict(os.environ)
    environment["ORTHO4XP_DATA_ROOT"] = _PROBE_DATA_ROOT
    environment.pop("PYTEST_CURRENT_TEST", None)
    environment.pop("PYTEST_XDIST_WORKER", None)
    completed = subprocess.run(
        [sys.executable, "-c", _NON_PYTEST_SIDE_EFFECT_PROBE,
         str(pathlib.Path(conftest.__file__).parent)],
        capture_output=True, text=True, env=environment, timeout=300)
    assert completed.returncode == 0, completed.stderr
    reported = dict(
        line.split("=", 1) for line in completed.stdout.split("\n") if "=" in line)
    assert reported["under_pytest"] == "False", completed.stdout
    assert reported["data_root"] == repr(_PROBE_DATA_ROOT), completed.stdout
    assert reported["keyring_faked"] == "False", completed.stdout
    # The reason the tools import conftest at all still works.
    assert reported["xplane_root"] == "True", completed.stdout


def test_the_pytest_process_still_gets_both_side_effects():
    """The other half of #175: inside pytest the pop and the keyring fake
    are exactly as they were — this process is living proof."""
    assert conftest.running_under_pytest()
    assert "ORTHO4XP_DATA_ROOT" not in os.environ
    # The fake is a synthesised ModuleType, so it carries no ``__file__``.
    assert not hasattr(sys.modules["keyring"], "__file__")
    assert sys.modules["keyring"] is conftest._fake_keyring


def test_the_guard_is_armed_at_conftest_import_not_by_a_later_hook():
    """#122's timing requirement, kept: the arming happens while conftest
    itself is being imported — before pytest imports any test module, so
    nothing can import ``requests`` ahead of the guard."""
    assert conftest.running_under_pytest() is True
    assert conftest._GUARD_ARMED_AT_IMPORT is True
    assert getattr(socket, "_o4_suite_network_guard", False) is True
    with pytest.raises(conftest.SuiteNetworkRefused):
        try:
            socket.getaddrinfo("overpass-api.de", 443)
        finally:
            _drop_refusals_since(_booked() - 1)


def test_the_guard_is_armed_in_an_xdist_worker_too():
    """Run this file under ``-n2`` as well as ``-n0``: in a worker process
    the controller's arming is worth nothing, the worker must arm its own
    socket module at ITS conftest import."""
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    assert conftest._GUARD_ARMED_AT_IMPORT is True, worker
    assert getattr(socket, "_o4_suite_network_guard", False) is True, worker
    if worker:
        # ``"pytest" in sys.modules`` is what holds at conftest import in
        # BOTH processes (measured); the worker env var is a second marker.
        assert conftest.running_under_pytest() is True
    start = _booked()
    try:
        with pytest.raises(conftest.SuiteNetworkRefused):
            socket.getaddrinfo("example.org", 80)
    finally:
        _drop_refusals_since(start)
