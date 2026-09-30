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
import socket
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
