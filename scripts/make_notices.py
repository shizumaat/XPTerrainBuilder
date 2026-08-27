#!/usr/bin/env python3
"""Generate THIRD-PARTY-NOTICES.txt for a release artifact.

Stdlib only, Python 3.  Run from anywhere — every input path is resolved
relative to this script's location, not the current working directory:

    python3 scripts/make_notices.py THIRD-PARTY-NOTICES.txt

The notices are assembled from the sources that are authoritative for each
component, never re-typed:

  * LICENSING.md sections 3 and 4 (the tree we actually ship)
  * Ortho4XP/Licence/copyright.txt — the 7-Zip block, verbatim, because
    7-Zip's license requires binary redistributions to reproduce it
  * Ortho4XP/Utils/osmium-tool-NOTICE.md — full text

Every extraction fails loudly: a heading that moved must break the release
build, not silently drop an obligation.  See LICENSING.md §6(d) and
docs/RELEASES-PLAN.md §G.
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

LICENSING = REPO / "LICENSING.md"
COPYRIGHT = REPO / "Ortho4XP" / "Licence" / "copyright.txt"
OSMIUM_NOTICE = REPO / "Ortho4XP" / "Utils" / "osmium-tool-NOTICE.md"

RULE = "=" * 78


class NoticeError(Exception):
    """An input file no longer contains a block we are obliged to ship."""


def read(path):
    if not path.is_file():
        raise NoticeError("missing input file: %s" % path)
    return path.read_text(encoding="utf-8")


def licensing_section(text, number):
    """Return the full text of LICENSING.md section `number`, heading included.

    Sections are `## <n>. <title>` and run to the next `## ` heading (or the
    `---` rule that precedes it) or end of file.
    """
    start = None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^##\s+%d\.\s" % number, line):
            start = i
            break
    if start is None:
        raise NoticeError(
            "LICENSING.md: heading for section %d not found "
            "(expected a line like '## %d. ...')" % (number, number)
        )
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    block = lines[start:end]
    while block and not block[-1].strip():
        block.pop()
    if len(block) < 2:
        raise NoticeError("LICENSING.md: section %d is empty" % number)
    return "\n".join(block)


def sevenzip_block(text):
    """Return the 7-Zip license block from copyright.txt, verbatim.

    Starts at the bare `7-Zip` heading line and ends just before the next
    full-width horizontal rule (the 78-dash separator that closes the block
    after the unRAR license restriction).  The rule must be full width: the
    block's own subsection underlines ("GNU LGPL information" etc.) are
    short dash runs and must not be mistaken for the closing separator.
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "7-Zip":
            start = i
            break
    if start is None:
        raise NoticeError(
            "%s: '7-Zip' heading line not found; the 7-Zip license MUST be "
            "reproduced verbatim in binary releases" % COPYRIGHT.name
        )
    end = None
    for j in range(start + 1, len(lines)):
        if re.match(r"^-{40,}$", lines[j].strip()):
            end = j
            break
    if end is None:
        raise NoticeError(
            "%s: could not find the rule closing the 7-Zip block" % COPYRIGHT.name
        )
    block = lines[start:end]
    while block and not block[-1].strip():
        block.pop()
    joined = "\n".join(block)
    # Distinctive strings from the START, MIDDLE and END of the block: a
    # truncated extraction must fail, not ship a partial license.
    for required in (
        "7-Zip Copyright",
        "GNU LGPL information",
        "Copyright (c) 2015-2016, Apple Inc. All rights reserved.",
        "not be used to develop a RAR (WinRAR) compatible archiver",
    ):
        if required not in joined:
            raise NoticeError(
                "%s: 7-Zip block is truncated — '%s' missing"
                % (COPYRIGHT.name, required)
            )
    return joined


HEADER = """\
XPTerrainBuilder — THIRD-PARTY NOTICES
{rule}

Generated from LICENSING.md by scripts/make_notices.py.  Do not edit by
hand: edit LICENSING.md and regenerate.

XPTerrainBuilder is not under a single license.

  * The application code (the macOS SwiftUI app, and everything under
    Sources/, Tests/, Resources/, scripts/, tools/, sim_review/) is
    MIT-licensed — see the LICENSE file shipped alongside this one.

  * The Ortho4XP engine (the whole Ortho4XP/ tree, including auto_patch/
    and o4_engine/) is licensed under the GNU General Public License,
    version 3.  The full GPL v3 text ships with this artifact as gpl.txt
    (in the repository: Ortho4XP/Licence/gpl.txt).  Source for the exact
    tree these binaries were built from is attached to the release as a
    source archive, and is published at
    https://github.com/shizumaat/XPTerrainBuilder

  * The bundled third-party components are listed below under their own
    terms.

LICENSING.md is the authoritative and complete statement; it ships with
this artifact.  Sections 3 and 4 of it are reproduced in full below.
"""

TRIANGLE = """\
Triangle / Triangle4XP (Jonathan Shewchuk; 4XP modifications by Oscar Pilote)
{rule}

This distribution includes Triangle, a two-dimensional quality mesh
generator and Delaunay triangulator by Jonathan Richard Shewchuk
(Carnegie Mellon University / University of California at Berkeley),
copyright 1993, 1995, 1997, 1998, 2002, 2005 Jonathan Richard Shewchuk.

THIS IS A MODIFIED VERSION.  The `Triangle4XP` binary is Oscar Pilote's
modified Triangle, adapted for Ortho4XP; the modifications are not the
work of, and are not endorsed by, Jonathan Shewchuk.  The extracted
modifications are licensed GPL v3 with author Oscar Pilote.

Complete source code for both the original and the modified triangulator
ships with this artifact in the Triangle-src/ directory (in the
repository: Ortho4XP/Utils/src/ — triangle.c, Triangle4XP.c,
Triangle4XP_v130.c), and the author's notice is retained intact in those
sources.

Triangle's license permits redistribution ONLY where no compensation is
received.  Commercial distribution is authorized only by direct
arrangement with Jonathan Shewchuk.  Accordingly XPTerrainBuilder is
distributed FREE OF CHARGE; you may redistribute this artifact only on
the same free-of-charge terms.  See LICENSING.md §6(a).
"""


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: make_notices.py OUTPUT_PATH\n")
        return 2
    out_path = Path(argv[1])

    licensing = read(LICENSING)
    parts = [
        HEADER.format(rule=RULE),
        "",
        RULE,
        licensing_section(licensing, 3),
        "",
        RULE,
        licensing_section(licensing, 4),
        "",
        RULE,
        TRIANGLE.format(rule=RULE),
        "",
        RULE,
        "7-Zip — reproduced verbatim from Ortho4XP/Licence/copyright.txt",
        RULE,
        "",
        sevenzip_block(read(COPYRIGHT)),
        "",
        RULE,
        "osmium-tool — reproduced from Ortho4XP/Utils/osmium-tool-NOTICE.md",
        RULE,
        "",
        read(OSMIUM_NOTICE).rstrip("\n"),
        "",
    ]
    text = "\n".join(parts).rstrip("\n") + "\n"

    if out_path.parent != Path(""):
        out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    sys.stderr.write(
        "wrote %s (%d lines, %d bytes)\n"
        % (out_path, text.count("\n"), len(text.encode("utf-8")))
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except NoticeError as exc:
        sys.stderr.write("ERROR: third-party notices could not be built: %s\n" % exc)
        sys.exit(1)
