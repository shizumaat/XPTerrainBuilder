"""Provider-account sign-in over the engine protocol
(docs/specs/swift-provider-signin-spec.md).

The macOS application has no Python of its own, so the login flows run
ENGINE-side behind three commands (``auth_providers``,
``provider_sign_in``, ``provider_sign_out``) whose completion arrives as
the ``SignInResult`` event.  Covered here: the registry lookup, the
descriptor shape and its status vocabulary, both SignInResult arms,
sign-out, and — the load-bearing one — the read-loop twin proving why
sign-in may not run on the transport's own thread.

All headless: the provider definitions are a fake registry module, the
login flows are monkeypatched, and the "front end" is the test answering
protocol lines over a pipe.  No network, no keyring, no X-Plane install.
"""

import json
import os
import sys
import threading
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Authenticated_Sessions as SESSIONS  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from o4_engine import jsonl  # noqa: E402
from o4_engine.secret_broker import SecretBroker  # noqa: E402
from o4_engine.session import EngineSession  # noqa: E402

from test_engine_jsonl import _CaptureStream, _is_event  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures and fakes
# ---------------------------------------------------------------------------
SESSION_DEFINITION = {
    "code": "PORTUGAL2M",
    "session_name": "dgterritorio",
    "login_flow": "keycloak_password",
    "login_url": "https://cdd.dgterritorio.gov.pt/auth/login",
    "registration_url": "https://cdd.dgterritorio.gov.pt/auth/login",
    "attribution": "Direcao-Geral do Territorio",
    "enabled": True,
}
SECOND_CODE_SAME_SESSION = dict(SESSION_DEFINITION, code="PORTUGALTIDAL")
API_KEY_DEFINITION = {
    "code": "DENMARK40CM",
    "session_name": "dataforsyningen",
    "credential_kind": "api_key",
    "registration_url": "https://dataforsyningen.dk/",
    "attribution": "Klimadatastyrelsen, Denmark",
    "setup_step_1": "Create a free account at https://dataforsyningen.dk/.",
    "setup_step_2": "Copy the token from your profile.",
    "enabled": True,
}
DISABLED_DEFINITION = {
    "code": "OFFLINE1M", "session_name": "nowhere", "enabled": False,
}
NO_ACCOUNT_DEFINITION = {"code": "ALOS", "enabled": True}


@pytest.fixture(autouse=True)
def reset_ui_routing():
    yield
    UI.secret_broker = None
    UI.engine_session = None
    UI.red_flag = False


@pytest.fixture
def fake_registry(monkeypatch):
    """Stand in for O4_Airport_Elevation_Insets' parsed .elv registry."""
    module = types.ModuleType("O4_Airport_Elevation_Insets")
    module.elevation_providers_dict = {
        definition["code"]: definition
        for definition in (SESSION_DEFINITION, SECOND_CODE_SAME_SESSION,
                           API_KEY_DEFINITION, DISABLED_DEFINITION,
                           NO_ACCOUNT_DEFINITION)
    }

    def _initialize(*_args, **_kwargs):  # never needed: the dict is filled
        raise AssertionError("the registry must not be re-parsed")

    module.initialize_elevation_providers_dict = _initialize
    monkeypatch.setitem(sys.modules, "O4_Airport_Elevation_Insets", module)
    return module


@pytest.fixture
def sessions_directory(monkeypatch, tmp_path):
    directory = str(tmp_path / "Sessions")
    os.makedirs(directory, exist_ok=True)
    monkeypatch.setattr(SESSIONS, "sessions_directory", lambda: directory)
    return directory


class _EventSink:
    """Collects a session's events; waits for one by type."""

    def __init__(self, session):
        self.events = []
        self._condition = threading.Condition()
        session.subscribe(self._receive)

    def _receive(self, event):
        with self._condition:
            self.events.append(event)
            self._condition.notify_all()

    def wait_for(self, name, timeout=10.0):
        with self._condition:
            if not self._condition.wait_for(
                    lambda: any(e.event == name for e in self.events),
                    timeout):
                raise AssertionError("no %s event arrived" % name)
            return next(e for e in self.events if e.event == name)


def _descriptors(session):
    return {d["session_name"]: d for d in session.auth_providers()}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def test_registry_maps_the_three_provider_commands():
    """The transport's command table reaches the session's methods 1:1."""
    session = EngineSession()
    handlers = jsonl._build_handlers(session)
    assert handlers["auth_providers"] == session.auth_providers
    assert handlers["provider_sign_in"] == session.provider_sign_in
    assert handlers["provider_sign_out"] == session.provider_sign_out


# ---------------------------------------------------------------------------
# Descriptors
# ---------------------------------------------------------------------------
def test_descriptor_shape_and_signed_out_status(fake_registry,
                                                sessions_directory):
    """One entry per ACCOUNT (not per provider code), carrying everything
    the sign-in sheet needs; nothing signed in yet."""
    session = EngineSession()
    descriptors = _descriptors(session)

    assert set(descriptors) == {"dgterritorio", "dataforsyningen"}  # not the
    # disabled one, not the definition with no account
    portugal = descriptors["dgterritorio"]
    assert portugal["codes"] == ["PORTUGAL2M", "PORTUGALTIDAL"]
    assert portugal["attribution"] == "Direcao-Geral do Territorio"
    assert portugal["credential_kind"] == "session"
    assert portugal["login_url"].startswith("https://cdd.dgterritorio")
    assert portugal["service_host"] == "cdd.dgterritorio.gov.pt"
    assert portugal["setup_steps"] == []
    assert portugal["signed_in"] is False
    assert portugal["username"] == ""
    assert portugal["status_text"] == "Not signed in"

    denmark = descriptors["dataforsyningen"]
    assert denmark["credential_kind"] == "api_key"
    assert denmark["service_host"] == "dataforsyningen.dk"  # registration_url
    assert denmark["setup_steps"] == [
        "Create a free account at https://dataforsyningen.dk/.",
        "Copy the token from your profile.",
    ]
    assert denmark["status_text"] == "No API key"


def test_descriptor_status_mirrors_local_state(fake_registry,
                                               sessions_directory,
                                               monkeypatch):
    """The Qt section's status vocabulary, derived from local state only —
    no network probe, and (session kinds) no secret-store read either."""
    monkeypatch.setattr(SESSIONS, "credential_store_available", lambda: True)
    session = EngineSession()

    # A saved cookie file alone: the session is usable, the account is not
    # remembered.
    with open(SESSIONS.cookie_file_path("dgterritorio"), "w") as handle:
        handle.write("# Netscape HTTP Cookie File\n")
    portugal = _descriptors(session)["dgterritorio"]
    assert portugal["signed_in"] is True
    assert portugal["status_text"] == "Session saved"

    # A remembered account: the username comes from the plain sidecar.
    monkeypatch.setattr(SESSIONS, "secret_set",
                        lambda session_name, account, secret: None)
    SESSIONS.store_credentials("dgterritorio", "user@example.org", "hunter2")
    portugal = _descriptors(session)["dgterritorio"]
    assert portugal["username"] == "user@example.org"
    assert portugal["status_text"] == "Signed in as user@example.org"
    assert portugal["credential_store_available"] is True

    # api_key kind, no broker: the store is read directly (Qt parity).
    monkeypatch.setattr(SESSIONS, "load_api_key",
                        lambda session_name: "a-stored-key")
    denmark = _descriptors(session)["dataforsyningen"]
    assert denmark["signed_in"] is True
    assert denmark["status_text"] == "API key stored"
    assert denmark["status_pending"] is False


# ---------------------------------------------------------------------------
# Sign-in / sign-out completion
# ---------------------------------------------------------------------------
def test_sign_in_reports_started_then_ok(fake_registry, sessions_directory,
                                         monkeypatch):
    calls = []
    monkeypatch.setattr(
        SESSIONS, "sign_in",
        lambda definition, username, password, remember=True:
            calls.append((definition["session_name"], username, password,
                          remember)))
    session = EngineSession()
    sink = _EventSink(session)

    assert session.provider_sign_in("dgterritorio", username="user",
                                    secret="hunter2",
                                    remember=True) == {"started": True}
    result = sink.wait_for("SignInResult")
    assert (result.session_name, result.ok, result.error_text) == (
        "dgterritorio", True, "")
    assert calls == [("dgterritorio", "user", "hunter2", True)]


def test_sign_in_api_key_arm_takes_the_secret_as_the_key(
        fake_registry, sessions_directory, monkeypatch):
    calls = []
    monkeypatch.setattr(
        SESSIONS, "sign_in_api_key",
        lambda definition, api_key, remember=True:
            calls.append((definition["session_name"], api_key, remember)))
    monkeypatch.setattr(SESSIONS, "sign_in", lambda *a, **k: pytest.fail(
        "an api_key provider must not use the username/password flow"))
    session = EngineSession()
    sink = _EventSink(session)

    session.provider_sign_in("dataforsyningen", username="",
                             secret="a-token", remember=True)
    assert sink.wait_for("SignInResult").ok is True
    assert calls == [("dataforsyningen", "a-token", True)]
    # The successful store is remembered, so the next descriptor is right.
    assert _descriptors(session)["dataforsyningen"]["status_text"] == \
        "API key stored"


def test_sign_in_login_error_arm_carries_the_message_verbatim(
        fake_registry, sessions_directory, monkeypatch):
    def _refuse(definition, username, password, remember=True):
        raise SESSIONS.LoginError(
            "The identity provider rejected the sign-in (wrong username "
            "or password, or an additional challenge is required).")

    monkeypatch.setattr(SESSIONS, "sign_in", _refuse)
    session = EngineSession()
    sink = _EventSink(session)

    session.provider_sign_in("dgterritorio", username="user", secret="wrong")
    result = sink.wait_for("SignInResult")
    assert result.ok is False
    assert result.error_text.startswith("The identity provider rejected")


def test_sign_in_other_exception_reports_its_own_text(
        fake_registry, sessions_directory, monkeypatch):
    """Anything not a LoginError is shown the same way (the Qt worker
    wraps it in LoginError(str(error)) — same text on the wire)."""
    def _explode(definition, username, password, remember=True):
        raise RuntimeError("connection reset by peer")

    monkeypatch.setattr(SESSIONS, "sign_in", _explode)
    session = EngineSession()
    sink = _EventSink(session)

    session.provider_sign_in("dgterritorio", username="user", secret="pw")
    result = sink.wait_for("SignInResult")
    assert (result.ok, result.error_text) == (False,
                                              "connection reset by peer")


def test_unknown_session_name_is_a_command_error(fake_registry,
                                                 sessions_directory):
    session = EngineSession()
    with pytest.raises(ValueError):
        session.provider_sign_in("nosuchprovider", username="u", secret="p")
    with pytest.raises(ValueError):
        session.provider_sign_out("nosuchprovider")


def test_sign_out_forgets_the_account_and_reports(fake_registry,
                                                  sessions_directory,
                                                  monkeypatch):
    signed_out = []
    monkeypatch.setattr(SESSIONS, "sign_out", signed_out.append)
    session = EngineSession()
    sink = _EventSink(session)

    assert session.provider_sign_out("dgterritorio") == {"started": True}
    result = sink.wait_for("SignInResult")
    assert (result.session_name, result.ok) == ("dgterritorio", True)
    assert signed_out == ["dgterritorio"]


# ---------------------------------------------------------------------------
# The read-loop twin (docs/specs/swift-provider-signin-spec.md, "THE
# DEADLOCK HAZARD")
# ---------------------------------------------------------------------------
def test_remember_store_fails_on_the_read_loop_but_the_worker_stores(
        fake_registry, monkeypatch, tmp_path):
    """Twin: the SAME remember=True store, on two threads.

    Arm A (the counterfactual): made on the thread that delivers brokered
    secret responses — what a synchronous ``provider_sign_in`` handler
    would be — the store fails fast rather than dead-block, and the
    credential is NOT saved.

    Arm B (the shipped path): the command replies ``{"started": true}``
    and its worker thread makes the same store, whose SecretRequest the
    front end answers over the protocol; the secret rides the broker and
    SignInResult reports success.
    """
    directory = str(tmp_path / "Sessions")
    monkeypatch.setattr(SESSIONS, "sessions_directory", lambda: directory)
    # The real registry initialization drags pyproj in (see the note in
    # test_secret_broker); these commands need no imagery providers.
    monkeypatch.setattr(jsonl, "_initialize_pipeline_registries", lambda: None)

    def fake_sign_in(definition, username, password, remember=True):
        """No network: just the remember=True store the hazard is about."""
        if remember:
            SESSIONS.store_credentials(definition["session_name"],
                                       username, password)

    monkeypatch.setattr(SESSIONS, "sign_in", fake_sign_in)

    # -- Arm A: the same store, on a broker's own service thread ---------
    refused = SecretBroker(send_request=lambda event: None,
                           service_thread=threading.current_thread())
    monkeypatch.setattr(UI, "secret_broker", refused, raising=False)
    with pytest.raises(SESSIONS.CredentialStoreUnavailable) as failure:
        fake_sign_in(SESSION_DEFINITION, "user@example.org", "hunter2")
    assert "read thread" in str(failure.value)
    assert not os.path.isfile(
        os.path.join(directory, "dgterritorio.account.json")), \
        "the refused store must not have saved anything"
    monkeypatch.setattr(UI, "secret_broker", None, raising=False)

    # -- Arm B: the command, over the transport, front end answering -----
    read_fd, write_fd = os.pipe()
    stdin = os.fdopen(read_fd, "r")
    writer = os.fdopen(write_fd, "w")
    capture = _CaptureStream()
    serve_thread = threading.Thread(target=jsonl.serve,
                                    args=(stdin, capture))
    serve_thread.start()
    try:
        assert capture.wait_for(lambda line: _is_event(line, "EngineHello"))
        writer.write(json.dumps({
            "cmd": "provider_sign_in", "id": 1,
            "session_name": "dgterritorio", "username": "user@example.org",
            "secret": "hunter2", "remember": True}) + "\n")
        writer.flush()
        # The reply comes back at once: the work has not been done yet.
        assert capture.wait_for(lambda line: '"reply": 1' in line
                                or '"reply":1' in line)
        reply = next(o for o in capture.objects() if o.get("reply") == 1)
        assert reply["ok"] is True and reply["result"] == {"started": True}

        # The worker's store became a SecretRequest; the front end answers.
        assert capture.wait_for(lambda line: _is_event(line, "SecretRequest"))
        request = next(o for o in capture.objects()
                       if o.get("event") == "SecretRequest")
        assert (request["operation"], request["session_name"],
                request["account"], request["secret"]) == (
            "set", "dgterritorio", "user@example.org", "hunter2")
        writer.write(json.dumps({
            "cmd": "secret_response", "id": 2,
            "request_id": request["request_id"], "ok": True}) + "\n")
        writer.flush()

        assert capture.wait_for(lambda line: _is_event(line, "SignInResult"))
        result = next(o for o in capture.objects()
                      if o.get("event") == "SignInResult")
        assert (result["session_name"], result["ok"], result["error_text"]) \
            == ("dgterritorio", True, "")
        writer.write(json.dumps({"cmd": "shutdown", "id": 3}) + "\n")
        writer.flush()
        serve_thread.join(30)
        assert not serve_thread.is_alive()
    finally:
        writer.close()
        stdin.close()
    # The username sidecar landed; the password went to the FRONT END's
    # store (the SecretRequest above), never to a keyring in this process.
    with open(os.path.join(directory, "dgterritorio.account.json")) as handle:
        assert json.load(handle) == {"username": "user@example.org"}


def test_api_key_status_is_probed_off_the_read_loop(fake_registry,
                                                    sessions_directory,
                                                    monkeypatch):
    """With a broker active, the api_key store read happens on a worker
    thread (it could never be answered on the command thread): the first
    descriptor says so with status_pending, the next one has the answer."""
    probed = threading.Event()

    def _load_api_key(session_name):
        assert threading.current_thread() is not command_thread
        probed.set()
        return "a-stored-key"

    monkeypatch.setattr(SESSIONS, "load_api_key", _load_api_key)
    monkeypatch.setattr(
        UI, "secret_broker",
        SecretBroker(send_request=lambda event: None,
                     service_thread=threading.current_thread()),
        raising=False)
    command_thread = threading.current_thread()
    session = EngineSession()

    first = _descriptors(session)["dataforsyningen"]
    assert (first["signed_in"], first["status_pending"]) == (False, True)
    assert probed.wait(10), "no probe worker read the store"
    for _ in range(100):
        second = _descriptors(session)["dataforsyningen"]
        if not second["status_pending"]:
            break
        threading.Event().wait(0.05)
    assert (second["signed_in"], second["status_pending"]) == (True, False)
    assert second["status_text"] == "API key stored"
