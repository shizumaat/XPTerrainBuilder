"""THE PATCH LIBRARY GATE (#1699 phase 2) — an airport of a harness-built
tile published to a FAKE library and found, applied and reused in an
EMPTY data folder; then version 2; then a changed pack.

    venv/bin/python tools/patch_library_gate.py --build OUT/TAG --world DIR \
        [--icao KPDX] [--kind payware]

``OUT/TAG`` names a ``build_airport.py --tile`` run whose vector and mesh
steps ran (the airport's patch family current, its object plan written);
``DIR`` must not exist.  Run from ``Ortho4XP/`` in a lane worktree.

1. PUBLISH (this process, in the build's frame): GitHub device sign-in,
   fork, branch and pull request against the fake GitHub of
   ``tools/patch_library_fake.py`` (a bare git library seeded from
   ``library_template/``, whose ``publishers.json`` lists the gate's
   login as the pack's verified developer); the library's checks
   (``patch_library.checks.check_pull``), the auto-merge verdict, the
   merge and the index rebuild.
2. FIND + APPLY + SKIP (a CHILD process on an empty data folder,
   ``tile_bundle_gate.make_world``: only the global cfg and the tile cfg,
   an X-Plane folder whose Custom Scenery holds an APFS clone of the
   airport's pack): ``library_check`` must list the airport as
   ``available`` and usable as solved, ``library_apply`` must lay it down
   (``solved``), and the build's reuse gate
   (``auto_patch.driver._auto_patch_is_current``) must say current — the
   solve is skipped.  The child's ``ReadTrace`` must see no network.
3. VERSION 2 published the same way; the child must list ``newer`` and
   apply it.
4. A CHANGED PACK: a row is added to the airport's apt.dat block in the
   world's clone; the child must list ``pack_changed``, the reuse gate
   must rebuild (``o4_library``) and ``library_apply`` must answer
   ``re-solve``.

Reports ``DIR/gate.json``; rc 0 only when every step holds.  Nothing is
written outside ``DIR`` (no keychain: the token lives in this process).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "harness"))

import tile_bundle_gate as TBG  # noqa: E402

LOGIN, TOKEN = "gate-dev", "tok-gate-dev"



def _put(path, text):
    """Write ``text`` as UTF-8 with LF line ends (#92, #539)."""
    path.write_text(text, encoding="utf-8", newline="\n")


# ── the publisher (this process) ────────────────────────────────────────

def _publisher(build: dict, world: Path, icao: str):
    redirects = build["frame"].get("engine_cache_redirects") or {}
    for key, env in TBG._REDIRECT_ENVS.items():
        if redirects.get(key):
            os.environ[env] = redirects[key]
    import build_airport as BA
    BA.apply_xplane_install_paths()
    from patch_library import github as GITHUB
    from patch_library import key as KEY
    from patch_library_fake import FakeGitHub
    from tile_bundle.export import load_tile
    from tile_bundle.key import xplane_root
    lat, lon = build["result"]["tile"]
    tile = load_tile(lat, lon, build["result"]["build_dir"])
    pack = KEY.pack_now(xplane_root(tile), icao, lat, lon)
    template = world / "template"
    subprocess.run(["cp", "-R", str(ROOT.parent / "library_template"), str(template)],
                   check=True)
    _put(template / "publishers.json", json.dumps({
        "developers": [{"login": LOGIN, "packs": [{"pack": pack["pack"],
                                                  "airports": [icao]}]}],
        "reviewers": []}))
    fake = FakeGitHub(str(world / "github"), str(template), users={TOKEN: LOGIN})
    os.environ.update(fake.environ())
    GITHUB.TRANSPORT = fake.transport
    held = {}
    GITHUB.stored_token = lambda: held.get("t")
    GITHUB.store_token = lambda t: held.__setitem__("t", t)
    return fake, pack


def _sign_in() -> str:
    from patch_library import github as GITHUB
    start = GITHUB.device_start()
    for _attempt in range(5):
        got = GITHUB.device_poll(start["device_code"])
        if got["status"] == "ok":
            return got["login"]
    raise SystemExit("the fake sign-in never finished")


def _publish(fake, build: dict, icao: str, kind: str, notes: str) -> dict:
    from patch_library import publish as PUBLISH
    lat, lon = build["result"]["tile"]
    t0 = time.time()
    out = PUBLISH.publish(lat, lon, icao, build["result"]["build_dir"], kind,
                          notes, accept=True)
    out["publish_seconds"] = round(time.time() - t0, 1)
    verdict = fake.run_checks(out["number"])
    out["checks"] = {"ok": verdict["ok"], "auto_merge": verdict["auto_merge"],
                     "problems": verdict["problems"]}
    fake.merge(out["number"])
    return out


# ── the receiver (a child on the empty data folder) ─────────────────────

def child(args) -> int:
    import corpus_snapshot as CS
    trace = CS.ReadTrace().start()
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    from auto_patch import driver as DRIVER
    from o4_engine import library as LIB
    from tile_bundle.export import load_tile
    from tile_bundle.key import xplane_root
    lines: list = []
    real = UI.lvprint
    UI.lvprint = lambda *a, **k: (lines.append(" ".join(map(str, a[1:]))), real(*a, **k))
    commands = {name: LIB.patch_library_command(name)
                for name in ("library_check", "library_apply")}
    out: dict = {"data_root": FNAMES.current_data_root()}
    t0 = time.time()
    found = commands["library_check"](force=True)
    out["check_seconds"] = round(time.time() - t0, 1)
    out["rows"] = [r for r in found["rows"] if r["icao"] == args.icao]
    lat, lon = (int(v) for v in args.tile)
    tile = load_tile(lat, lon)
    patch = os.path.join(FNAMES.patch_dir(lat, lon), FNAMES.auto_patch_name(args.icao))
    if os.path.isfile(patch):             # what a build would decide before any press
        out["reuse_before"] = DRIVER._auto_patch_is_current(
            patch, xplane_root(tile), args.icao, tile=tile)
        out["gate_lines_before"] = [ln for ln in lines if args.icao in ln]
        del lines[:]
    if out["rows"]:
        t0 = time.time()
        out["apply"] = commands["library_apply"](entry=out["rows"][0]["entry"])
        out["apply_seconds"] = round(time.time() - t0, 1)
    out["reuse"] = DRIVER._auto_patch_is_current(patch, xplane_root(tile), args.icao,
                                                 tile=tile)
    out["gate_lines"] = [ln for ln in lines if args.icao in ln]
    trace.stop()
    events = [e for p in trace.record()["phases"].values() for e in p["network"]]
    out["library_reads"] = len([e for e in events if "file://" in e])
    out["network"] = [e for e in events if "file://" not in e]
    _put(Path(args.child_out), json.dumps(out, indent=1, default=str))
    return 0


def _run_child(world: Path, made: dict, build: dict, icao: str, phase: str) -> dict:
    out = world / ("child_%s.json" % phase)
    env = dict(os.environ, ORTHO4XP_DATA_ROOT=made["data"], O4_PACK_WRITES="measure_only")
    for name in TBG._REDIRECT_ENVS.values():
        env.pop(name, None)
    lat, lon = build["result"]["tile"]
    rc = subprocess.run([sys.executable, __file__, "--child", "--icao", icao,
                         "--tile", str(lat), str(lon), "--child-out", str(out)],
                        env=env, cwd=str(ROOT)).returncode
    if rc != 0 or not out.is_file():
        raise SystemExit("the receiver (%s) failed, rc=%d" % (phase, rc))
    return json.loads(out.read_text(encoding="utf-8"))


def _change_pack(made: dict, pack: str, icao: str) -> str:
    """One metadata row added to ``icao``'s block in the world's clone."""
    apt = Path(made["scenery"]) / pack / "Earth nav data" / "apt.dat"
    lines = apt.read_text(encoding="utf-8", errors="replace").split("\n")
    for at, line in enumerate(lines):
        parts = line.split()
        if parts[:1] in (["1"], ["16"], ["17"]) and len(parts) > 4 and parts[4] == icao:
            lines.insert(at + 1, "1302 xptb_gate_probe 1")
            break
    else:
        raise SystemExit("no %s block in %s" % (icao, apt))
    apt.unlink()                          # the clone: never the owner's file
    apt.write_text("\n".join(lines), encoding="utf-8", newline="")
    return str(apt)


def gate(args) -> int:
    world = Path(args.world)
    if world.exists():
        raise SystemExit(f"REFUSING: {world} exists; the gate starts empty")
    world.mkdir(parents=True)
    build = TBG._read_build(args.build)
    fake, pack = _publisher(build, world, args.icao)
    report: dict = {"icao": args.icao, "pack": pack, "login": _sign_in()}
    report["v1"] = _publish(fake, build, args.icao, args.kind, "")
    made = TBG.make_world(world / "world", build, {"airports": {
        args.icao: {"pack": pack["pack"], "custom": pack["custom"]}}})
    report["world"] = made
    report["found"] = _run_child(world, made, build, args.icao, "v1")
    report["v2"] = _publish(fake, build, args.icao, args.kind, "gate: version 2")
    report["newer"] = _run_child(world, made, build, args.icao, "v2")
    report["changed_apt_dat"] = _change_pack(made, pack["pack"], args.icao)
    report["changed"] = _run_child(world, made, build, args.icao, "changed")

    def row(phase):
        rows = report[phase]["rows"]
        return rows[0] if rows else {}

    checks = {
        "v1 merged by itself": report["v1"]["checks"]["auto_merge"],
        "found on app open": row("found").get("state") == "available"
        and row("found").get("solved_usable") is True,
        "applied as solved": (report["found"].get("apply") or {}).get("mode") == "solved",
        "solve skipped": report["found"]["reuse"] is True,
        "v2 reads newer": row("newer").get("state") == "newer"
        and row("newer").get("version") == 2 and row("newer").get("local_version") == 1,
        "v2 applied": (report["newer"].get("apply") or {}).get("mode") == "solved"
        and report["newer"]["reuse"] is True,
        "changed pack listed": row("changed").get("state") == "pack_changed",
        "changed pack: the build re-solves": report["changed"].get("reuse_before") is False
        and any("no longer matches" in ln for ln in report["changed"]["gate_lines_before"]),
        "changed pack: apply says re-solve": (report["changed"].get("apply") or {}).get(
            "mode") == "re-solve" and report["changed"]["reuse"] is False,
        "no network": not any(report[p]["network"] for p in ("found", "newer", "changed")),
    }
    report["checks"] = checks
    report["pass"] = all(checks.values())
    _put(world / "gate.json", json.dumps(report, indent=1, default=str))
    for name, ok in checks.items():
        print("%-36s %s" % (name, "PASS" if ok else "FAIL"))
    print("gate %s -> %s" % ("PASS" if report["pass"] else "FAIL", world / "gate.json"))
    return 0 if report["pass"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--build", help="OUT/TAG of a build_airport.py --tile run")
    ap.add_argument("--world", help="the gate's folder (must not exist)")
    ap.add_argument("--icao", default="KPDX")
    ap.add_argument("--kind", default="payware", choices=("freeware", "payware"))
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--tile", nargs=2, help=argparse.SUPPRESS)
    ap.add_argument("--child-out", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.child:
        return child(args)
    if not (args.build and args.world):
        ap.error("--build and --world are required")
    return gate(args)


if __name__ == "__main__":
    sys.exit(main())
