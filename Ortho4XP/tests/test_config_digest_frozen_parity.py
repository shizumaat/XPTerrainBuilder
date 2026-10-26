"""#1321: the frozen and source engines compute the same ``o4_cfg`` digest.

The frozen engine ships no ``config.py``, so it reads the gate table the
freeze wrote as data (``config_gates.json``).  These tests freeze that table
from the checkout's source into a temp dir and hold the digest to the
source engine's.
"""
import json
import os

import pytest
from auto_patch import config_gates, provenance

SRC = os.path.dirname(os.path.dirname(os.path.abspath(provenance.__file__)))


@pytest.fixture
def frozen(monkeypatch, tmp_path):
    """The engine as frozen: no config source, the freeze's table beside
    ``config_gates``."""
    path = config_gates.write_freeze_gates(SRC, str(tmp_path))
    monkeypatch.setattr(provenance, "_config_source_path", lambda: None)
    real = config_gates.frozen_gate_defaults
    monkeypatch.setattr(config_gates, "frozen_gate_defaults",
                        lambda directory=None: real(str(tmp_path)))
    return path


def test_freeze_table_is_a_fresh_source_parse(tmp_path):
    """The table is regenerated from source, never hand-kept: what the
    freeze writes is exactly the source parse."""
    path = config_gates.write_freeze_gates(SRC, str(tmp_path))
    with open(path, encoding="utf-8") as handle:
        table = json.load(handle)
    source = config_gates.source_gate_defaults(
        os.path.join(SRC, "auto_patch", "config.py"))
    assert len(source) > 100, "gate introspection collapsed"
    assert table == source


def test_no_table_is_committed_beside_the_module():
    """A committed table would go stale the first time a gate is added; the
    freeze writes it into ``build/`` and the spec bundles it."""
    assert config_gates.frozen_gate_defaults() is None


def test_frozen_digest_equals_source_digest(frozen):
    frozen_gates = provenance.introspect_config_gates()
    assert frozen_gates, "the frozen engine fell back to no gates"
    assert frozen_gates == provenance.introspect_config_gates(
        os.path.join(SRC, "auto_patch", "config.py"))
    assert provenance.config_digest() == _source_digest()


def _source_digest():
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(provenance, "_config_source_path",
                   lambda: os.path.join(SRC, "auto_patch", "config.py"))
        return provenance.config_digest()


def test_frozen_digest_still_tracks_a_gate_flip(frozen, monkeypatch):
    monkeypatch.delenv("O4_CROWN_TAXI", raising=False)
    default = provenance.config_digest()
    monkeypatch.setenv("O4_CROWN_TAXI", "1")
    assert provenance.config_digest() != default
    assert provenance.config_digest() == _source_digest()


def test_neither_source_nor_table_is_unavailable(monkeypatch, tmp_path):
    """With neither present the digest still says so, and never compares
    equal to one built with the gates readable."""
    with_source = provenance.config_digest()
    monkeypatch.setattr(provenance, "_config_source_path", lambda: None)
    real = config_gates.frozen_gate_defaults
    monkeypatch.setattr(config_gates, "frozen_gate_defaults",
                        lambda directory=None: real(str(tmp_path)))
    assert provenance.introspect_config_gates() == {}
    assert provenance.config_digest() != with_source


def test_malformed_table_reads_as_absent(tmp_path):
    (tmp_path / config_gates.GATES_FILENAME).write_text(
        "not json", encoding="utf-8", newline="\n")
    assert config_gates.frozen_gate_defaults(str(tmp_path)) is None
    (tmp_path / config_gates.GATES_FILENAME).write_text(
        "{}", encoding="utf-8", newline="\n")
    assert config_gates.frozen_gate_defaults(str(tmp_path)) is None


def test_freeze_refuses_without_gates(tmp_path):
    (tmp_path / "auto_patch").mkdir()
    (tmp_path / "auto_patch" / "config.py").write_text(
        "X = 1\n", encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit):
        config_gates.write_freeze_gates(str(tmp_path), str(tmp_path / "out"))
