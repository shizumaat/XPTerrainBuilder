"""Twin for the architecture decision records (code-quality-beta3-spec §4,
RULINGS 2026-10-17a Q7, #854): `docs/adr/NNNN-slug.md`.

Asserts the folder's shape, never its prose: numbering contiguous from 0001
and unique; every ADR carries the five headings (Date, Status, Context,
Decision, Consequences) in that order; the status is one of proposed /
accepted / superseded by NNNN; a superseded ADR names a successor that exists
and is newer; and `tools/docq.py adr NNNN` reads each one.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)
import docq  # noqa: E402

HEADINGS = ("Date", "Status", "Context", "Decision", "Consequences")
_STATUS = re.compile(r"^(proposed|accepted|superseded by (\d{4}))$")


def _sections(path: str) -> dict[str, str]:
    """``{heading: body}`` for every `## heading` in file order."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}


def _md_names() -> list[str]:
    return sorted(n for n in os.listdir(docq.ADR_DIR) if n.endswith(".md"))


def test_every_markdown_file_is_named_nnnn_slug():
    bad = [n for n in _md_names() if not docq.ADR_FILE.match(n)]
    assert not bad, f"ADR files must be NNNN-slug.md (lowercase slug): {bad}"


def test_numbering_is_contiguous_from_0001_and_unique():
    nums = [docq.ADR_FILE.match(n).group(1) for n in _md_names() if docq.ADR_FILE.match(n)]
    assert nums, "no ADRs found"
    assert len(nums) == len(set(nums)), f"duplicate ADR numbers: {nums}"
    assert nums == [f"{i:04d}" for i in range(1, len(nums) + 1)], nums


@pytest.mark.parametrize("num", sorted(docq.adr_paths()))
def test_adr_has_the_five_headings_and_a_title(num):
    path = docq.adr_paths()[num]
    with open(path, encoding="utf-8") as f:
        first = f.readline().rstrip("\n")
    assert first.startswith(f"# {num} "), f"{path}: title must start '# {num} '"
    secs = _sections(path)
    assert tuple(secs) == HEADINGS, f"{path}: headings {tuple(secs)} != {HEADINGS}"
    assert all(secs[h] for h in HEADINGS), f"{path}: an empty section"


@pytest.mark.parametrize("num", sorted(docq.adr_paths()))
def test_status_is_valid_and_a_successor_exists(num):
    paths = docq.adr_paths()
    status = _sections(paths[num])["Status"]
    m = _STATUS.match(status)
    assert m, f"ADR {num}: status {status!r} is not proposed / accepted / superseded by NNNN"
    successor = m.group(2)
    if successor:
        assert successor in paths, f"ADR {num} is superseded by {successor}, which does not exist"
        assert successor > num, f"ADR {num} is superseded by an older ADR {successor}"


def test_docq_adr_reads_one_and_refuses_a_miss():
    text = docq.adr_entry("1")
    assert text.startswith("# 0001 ")
    missing = f"{len(docq.adr_paths()) + 1:04d}"
    with pytest.raises(SystemExit, match=f"no ADR {missing}"):
        docq.adr_entry(missing)
    with pytest.raises(SystemExit, match="digits"):
        docq.adr_entry("v2")
    cli = subprocess.run([sys.executable, os.path.join(TOOLS, "docq.py"), "adr", "0003"],
                         capture_output=True, text=True, encoding="utf-8")
    assert cli.returncode == 0 and cli.stdout.startswith("# 0003 "), cli.stderr
