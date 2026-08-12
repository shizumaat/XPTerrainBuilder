"""Offscreen tests for the Provider accounts rows (settings window).

Owner ruling 2026-08-12: every provider row carries ONE context-aware
button — what it says is what it does — pinned to the row's right edge,
with the status text taking the space that is left (elided, full text as
the tooltip).  These tests pin the state table (credential kind x local
stored state -> label / action / enabled), the busy behaviour and the
right-edge layout.  Headless: QT_QPA_PLATFORM=offscreen, no network.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from PySide6.QtWidgets import QApplication

import O4_Airport_Elevation_Insets as ELEVATION_PROVIDERS
import O4_Authenticated_Sessions as SESSIONS
import O4_Qt_Settings as QS


SESSION_ROW = "sess"
BASIC_ROW = "basic"
KEY_ROW = "key"

DEFINITIONS = {
    "SESS": {
        "code": "SESS",
        "attribution": "Session Provider",
        "session_name": SESSION_ROW,
        "credential_kind": SESSIONS.CREDENTIAL_KIND_SESSION,
        "enabled": True,
    },
    "BASIC": {
        "code": "BASIC",
        "attribution": "Basic Provider",
        "session_name": BASIC_ROW,
        "credential_kind": SESSIONS.CREDENTIAL_KIND_HTTP_BASIC,
        "enabled": True,
    },
    "KEY": {
        "code": "KEY",
        "attribution": "Key Provider",
        "session_name": KEY_ROW,
        "credential_kind": SESSIONS.CREDENTIAL_KIND_API_KEY,
        "enabled": True,
    },
}


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeState:
    """Local sign-in state, without a keychain or a cookie jar."""

    def __init__(self):
        self.credentials = {}   # session_name -> (user, password)
        self.api_keys = {}      # session_name -> key
        self.signed_out = []    # sign_out() calls, in order

    @staticmethod
    def save_cookies(session_name):
        """A saved cookie jar (the 'Session saved' state)."""
        open(SESSIONS.cookie_file_path(session_name), "w").close()


@pytest.fixture
def state(monkeypatch, tmp_path):
    fake = _FakeState()
    monkeypatch.setattr(
        ELEVATION_PROVIDERS, "elevation_providers_dict", dict(DEFINITIONS)
    )
    monkeypatch.setattr(
        SESSIONS, "load_credentials", lambda name: fake.credentials.get(name)
    )
    monkeypatch.setattr(
        SESSIONS, "load_api_key", lambda name: fake.api_keys.get(name)
    )
    monkeypatch.setattr(
        SESSIONS,
        "cookie_file_path",
        lambda name: str(tmp_path / ("%s.cookies" % name)),
    )

    def _sign_out(name):
        fake.signed_out.append(name)
        fake.credentials.pop(name, None)
        fake.api_keys.pop(name, None)
        try:
            os.remove(SESSIONS.cookie_file_path(name))
        except OSError:
            pass

    monkeypatch.setattr(SESSIONS, "sign_out", _sign_out)
    yield fake


def _section(state, qapp):
    section = QS._ProviderSignInSection()
    section.resize(620, 200)
    return section


def _row(section, session_name):
    """(status label, action button) for one provider row."""
    _definition, status, button = section._rows[session_name]
    return status, button


# ---------------------------------------------------------------------
# The state table
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "api_key_kind,is_stored,action,label",
    [
        (False, False, QS.ACTION_SIGN_IN, "Sign in…"),
        (False, True, QS.ACTION_SIGN_OUT, "Sign out"),
        (True, False, QS.ACTION_ADD_API_KEY, "Add API Key…"),
        (True, True, QS.ACTION_EDIT_API_KEY, "Edit…"),
    ],
)
def test_state_table(api_key_kind, is_stored, action, label):
    assert QS.provider_row_action(api_key_kind, is_stored) == action
    assert QS.ACTION_LABELS[action] == label


def test_only_dialog_opening_actions_carry_an_ellipsis():
    for action, label in QS.ACTION_LABELS.items():
        opens_dialog = action != QS.ACTION_SIGN_OUT
        assert label.endswith("…") is opens_dialog, label


def test_rows_start_signed_out_with_one_button_each(state, qapp):
    section = _section(state, qapp)
    for name, label, status_text in (
        (SESSION_ROW, "Sign in…", "Not signed in"),
        (BASIC_ROW, "Sign in…", "Not signed in"),
        (KEY_ROW, "Add API Key…", "No API key"),
    ):
        status, button = _row(section, name)
        assert button.text() == label
        assert button.isEnabled(), "the only control is always actionable"
        assert status.full_text() == status_text
    # Exactly one button per row: the second control is gone.
    for name in section._rows:
        container = section._rows[name][2].parentWidget()
        buttons = [
            container.layout().itemAt(i).widget()
            for i in range(container.layout().count())
        ]
        assert sum(isinstance(w, QS.QPushButton) for w in buttons) == 1


def test_signed_in_states_flip_the_button_to_sign_out(state, qapp):
    state.credentials[SESSION_ROW] = ("ada", "secret")
    state.save_cookies(BASIC_ROW)  # a cookie jar alone counts as signed in
    state.api_keys[KEY_ROW] = "abc123"
    section = _section(state, qapp)
    status, button = _row(section, SESSION_ROW)
    assert (button.text(), status.full_text()) == (
        "Sign out", "Signed in as ada"
    )
    status, button = _row(section, BASIC_ROW)
    assert (button.text(), status.full_text()) == ("Sign out", "Session saved")
    status, button = _row(section, KEY_ROW)
    assert (button.text(), status.full_text()) == ("Edit…", "API key stored")
    assert all(_row(section, n)[1].isEnabled() for n in section._rows)


def test_sign_out_runs_directly_without_a_dialog(state, qapp, monkeypatch):
    opened = []
    monkeypatch.setattr(
        QS, "_SignInDialog", lambda *a, **k: opened.append(a) or None
    )
    state.credentials[SESSION_ROW] = ("ada", "secret")
    section = _section(state, qapp)
    _status, button = _row(section, SESSION_ROW)
    assert button.text() == "Sign out"
    section._activate(SESSION_ROW)
    _drain_sign_out(section, qapp, SESSION_ROW)
    assert state.signed_out == [SESSION_ROW]
    assert opened == [], "sign out must not open the credentials dialog"
    status, button = _row(section, SESSION_ROW)
    assert (button.text(), status.full_text()) == (
        "Sign in…", "Not signed in"
    )


@pytest.mark.parametrize(
    "name,stored", [(SESSION_ROW, False), (KEY_ROW, False), (KEY_ROW, True)]
)
def test_dialog_actions_open_the_sign_in_dialog(
    state, qapp, monkeypatch, name, stored
):
    opened = []

    class _StubDialog:
        def __init__(self, definition, parent=None):
            opened.append(definition)

        def exec(self):
            return 0  # cancelled: nothing to refresh

    monkeypatch.setattr(QS, "_SignInDialog", _StubDialog)
    if stored:
        state.api_keys[name] = "abc123"
    section = _section(state, qapp)
    section._activate(name)
    assert [d["session_name"] for d in opened] == [name]
    assert state.signed_out == []


def test_busy_keeps_the_label_and_disables_the_button(state, qapp):
    state.credentials[SESSION_ROW] = ("ada", "secret")
    section = _section(state, qapp)
    _status, button = _row(section, SESSION_ROW)
    section._busy.add(SESSION_ROW)
    # Even with the underlying state already gone, an in-flight row keeps
    # the label the user pressed.
    state.credentials.pop(SESSION_ROW)
    section._refresh_statuses()
    assert button.text() == "Sign out"
    assert not button.isEnabled()
    # Other rows are untouched by one row's busy state.
    assert _row(section, KEY_ROW)[1].isEnabled()
    section._finish_sign_out(SESSION_ROW)
    assert button.isEnabled()
    assert button.text() == "Sign in…"


def _drain_sign_out(section, qapp, session_name, timeout=5.0):
    """Wait for the worker thread's finished signal to be delivered."""
    import time

    deadline = time.time() + timeout
    while session_name in section._busy and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    qapp.processEvents()
    assert session_name not in section._busy, "sign-out never finished"


# ---------------------------------------------------------------------
# Layout: the button is pinned right, the status takes what is left
# ---------------------------------------------------------------------
def test_status_is_the_only_elastic_element(state, qapp):
    section = _section(state, qapp)
    status, button = _row(section, SESSION_ROW)
    row = button.parentWidget().layout()
    stretches = [
        row.stretch(i) for i in range(row.count())
    ]
    assert stretches.count(0) == row.count() - 1, (
        "exactly one elastic element in the row"
    )
    assert row.stretch(row.indexOf(status)) == 1
    assert row.stretch(row.indexOf(button)) == 0


def test_buttons_share_a_right_edge_whatever_the_status_says(state, qapp):
    state.credentials[SESSION_ROW] = ("ada-with-a-very-long-account-name",)
    section = _section(state, qapp)
    section.show()
    qapp.processEvents()
    edges = {
        name: button.mapTo(section, button.rect().topRight()).x()
        for name, (_d, _s, button) in section._rows.items()
    }
    assert len(set(edges.values())) == 1, (
        "signed-in and signed-out rows must share a trailing edge: %r"
        % (edges,)
    )
    section.close()


def test_status_absorbs_the_slack_and_the_title_keeps_its_ideal_width(
    state, qapp
):
    state.credentials[SESSION_ROW] = ("ada-with-a-very-long-account-name",)
    section = _section(state, qapp)
    status, button = _row(section, SESSION_ROW)
    title = button.parentWidget().layout().itemAt(0).widget()
    section.show()
    qapp.processEvents()
    narrow_title, narrow_status = title.width(), status.width()
    section.resize(section.width() + 280, section.height())
    qapp.processEvents()
    assert title.width() == narrow_title == title.sizeHint().width(), (
        "the provider title keeps its ideal width"
    )
    assert status.width() == narrow_status + 280, (
        "the status is what grows with the row"
    )
    section.close()


def test_a_long_status_elides_instead_of_squeezing_the_button(state, qapp):
    state.credentials[SESSION_ROW] = ("ada-with-a-very-long-account-name",)
    section = _section(state, qapp)
    status, button = _row(section, SESSION_ROW)
    section.show()
    qapp.processEvents()
    section.resize(340, section.height())  # narrower than the full status
    qapp.processEvents()
    assert button.width() == button.sizeHint().width(), (
        "the button never gives up room to the status"
    )
    assert status.text() != status.full_text() and status.text().endswith("…")
    assert status.toolTip() == "Signed in as ada-with-a-very-long-account-name"
    section.close()


def test_elided_label_truncates_and_tooltips_the_full_text(qapp):
    label = QS._ElidedLabel("Signed in as an-extremely-long-account-name")
    label.resize(70, 20)
    label.show()
    qapp.processEvents()
    assert label.toolTip() == label.full_text()
    assert label.text() != label.full_text()
    assert label.text().endswith("…")
    label.close()
