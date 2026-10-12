"""The bundled DSFTool is the one ``Utils/DSFTool.identity.json`` names (#587).

DSFTool is a vendored binary per platform.  Nothing in the engine names a
version, so a file swapped by hand, by a merge or by a half-applied
vendoring would ship unnoticed — and the three platforms could drift apart.
The identity file carries one row per file (sha256 + the ``--version``
line); it is rewritten only by ``docs/DSFTOOL-VENDORING.md``, in the commit
that replaces the binaries.

The release string is pinned too.  DSFTool writes it into line 2 of every
dump (``800 written by DSFTool 2.4.0-b1``) and the round-trip verify
compares that line as a structural row, while dumps are cached by the
DSF's bytes, not by tool: a tool that called itself anything else would
make every write whose pristine dump is already cached refuse.

Reads the repo's own files and runs the host's bundled tool with
``--version``: no network, no X-Plane install.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import pytest

from auto_patch_v2.airport import dsf_write

UTILS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Utils")
RELEASE = "DSFTool 2.4.0-b1"
HOST_FILE = {"darwin": "mac/DSFTool", "win32": "win/DSFTool.exe"}.get(
    sys.platform, "lin/DSFTool")


def _identity() -> dict:
    with open(os.path.join(UTILS, "DSFTool.identity.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_the_three_platform_files_are_the_recorded_ones():
    rows = _identity()["binaries"]

    assert sorted(rows) == ["lin/DSFTool", "mac/DSFTool", "win/DSFTool.exe"]
    for name, row in rows.items():
        with open(os.path.join(UTILS, *name.split("/")), "rb") as fh:
            found = hashlib.sha256(fh.read()).hexdigest()
        assert found == row["sha256"], (
            f"Utils/{name} is not the binary Utils/DSFTool.identity.json "
            "records — vendor it through docs/DSFTOOL-VENDORING.md")


def test_every_platform_is_the_same_release_and_the_same_build():
    identity = _identity()

    assert identity["release"] == RELEASE
    for name, row in identity["binaries"].items():
        assert row["version"].startswith(RELEASE + ","), name
    # a patched build comes from ONE CI run: no platform left behind
    assert (identity["ci_run"] is not None) == identity["patched"]


def test_the_host_tool_says_the_recorded_version():
    row = _identity()["binaries"][HOST_FILE]
    tool = os.path.join(UTILS, *HOST_FILE.split("/"))
    try:
        proc = subprocess.run([tool, "--version"], capture_output=True, timeout=60)
    except OSError as exc:                 # another architecture's binary
        pytest.skip(f"the bundled tool does not run on this host: {exc}")

    said = proc.stdout.decode("utf-8", "replace").splitlines()
    assert said[:1] == [row["version"]]
    assert said[1:2] == ["Part of X-Plane Scenery Tools release: 24-5"]


def test_a_tool_under_another_release_name_would_refuse_cached_round_trips():
    """Why the release string is pinned: line 2 of a dump is compared."""
    dump = ("A\n800 written by DSFTool 2.4.0-b1\nDSF2TEXT\n\n"
            "PROPERTY sim/overlay 1\nOBJECT_DEF a.obj\nOBJECT 0 1.0 2.0 3.0\n")

    assert dsf_write.compare_dumps(dump, dump).ok
    assert not dsf_write.compare_dumps(
        dump, dump.replace("2.4.0-b1", "2.4.0-b2")).ok
