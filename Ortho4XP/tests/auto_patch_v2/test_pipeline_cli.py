"""``auto_patch_v2 build``'s solver options are built FROM THE CLI
NAMESPACE by one function (lane ``rwyholes``; the RULINGS 2026-09-13dd
chip): at head every ``build`` died on ``Options.__init__() got an
unexpected keyword argument 'diagnose_iis'`` — the LP's IIS flag outlived
the LP (RULINGS 2026-09-08t deleted the IIS with the ladder) because
nothing constructed :class:`Options` from a parsed namespace off the
build path.  This twin does."""
from __future__ import annotations

import dataclasses

from auto_patch_v2.pipeline.__main__ import build_parser, options_from_args
from auto_patch_v2.solve import Options


def test_options_are_built_from_the_cli_namespace(tmp_path):
    ns = build_parser().parse_args(["build", "heca", "--out", str(tmp_path), "--verbose"])
    assert options_from_args(ns) == Options(verbose=True)
    ns = build_parser().parse_args(["build", "heca", "--out", str(tmp_path)])
    assert options_from_args(ns) == Options()
    # the class of the break: a namespace key the LP's options once took
    # and the design surface's do not
    assert "no_iis" not in vars(ns) and "diagnose_iis" not in vars(ns)
    fields = {f.name for f in dataclasses.fields(Options)}
    assert "diagnose_iis" not in fields and "verbose" in fields
