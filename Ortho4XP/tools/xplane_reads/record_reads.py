#!/usr/bin/env python3
"""record_reads.py: the #1992 read recorder (what X-Plane loads, at what
distance and mip level).

Logs which imagery files X-Plane opens and reads during a flight (DDS
textures, .ter terrain files, .dsf mesh tiles), with the aircraft and camera
position and the frame time once a second, into ONE JSONL file, and keeps
fs_usage's raw text beside it (gzip) so anything the parser misses can be
re-parsed offline (--from-text).

Standard library only (macOS /usr/bin/python3 3.9 or newer).  Needs root for
fs_usage, so the owner runs it in Terminal, X-Plane running:

    sudo python3 record_reads.py --pack PACK --check --out check.jsonl
    sudo python3 record_reads.py --pack PACK --minutes 30 --out flight.jsonl

then reads it with   python3 analyse_reads.py flight.jsonl

PACK (repeatable) is a test pack folder (zOrtho4XP_...): its DDS files are
evicted from the macOS file cache at start and after every X-Plane load, and
right after each close the kernel says which of their pages are resident
(mincore), hence which mip levels that load touched ("resident" records).
Evicting cached pages never changes a file; X-Plane just reads it from disk
again.  Neither tool writes into X-Plane or Custom Scenery.

What the flights taught (2026-11-10)
  * X-Plane does NOT read() its DDS textures: it opens the file, mmaps it,
    touches the mip levels it wants (page faults = fs_usage "PgIn" lines with
    the path, the disk block D= and the byte count B=, but no file offset),
    and closes it, all within a few milliseconds.  A page already in the
    file cache faults with no disk I/O and leaves no trace at all.
  * The Web API hands out new dataref ids when a flight loads: the poller
    forgets its ids on ANY error and retries every second.

Records (one JSON object per line, all with "utc" and "t"):
  meta, pos_refs, pos, pos_error, pos_resumed, file (size + DDS header +
  disk extents), open, open_fail, close, read (read/pread with offset),
  mmap, disk (PgIn/RdData page-ins of tracked files, with D and bytes),
  resident (pages resident right after a close -> what was read),
  start_cache (test-pack pages cached at start), held_at_start, fd_other,
  other (stat...), sample (the first raw lines of every fs_usage call name),
  unparsed, summary.  "ln" = the line number in the raw text.  pos carries
  frame_s (sim/time/framerate_period) when X-Plane publishes it.

Scopes: tile = the test packs only; all (default) = they plus every pack in
X-Plane's Custom Scenery (symlinks followed); every = any .dds/.ter/.dsf
anywhere (also X-Plane's own Resources).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import json
import mmap
import os
import select
import shutil
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reads_fs_usage import Scope, TodClock, Tracker, feed_text  # noqa: E402
from reads_page_cache import (F_NOCACHE, PAGE, cache_probe,  # noqa: E402
                              snapshot)
from reads_textures import mip_ranges  # noqa: E402

WEB_API = "http://localhost:8086/api/v2"
MAX_MINUTES = 240
VERSION = 3


def cache_reset(emit, scope: Scope, evict: bool) -> int:
    """At start: record which test-tile DDS pages are already cached, then
    evict them so the flight's loads all come from disk."""
    n = 0
    for root in scope.tile:
        d = os.path.join(root, "textures")
        if not os.path.isdir(d):
            continue
        for b in sorted(os.listdir(d)):
            if not b.lower().endswith(".dds") or b.startswith("."):
                continue
            p = os.path.realpath(os.path.join(d, b))
            got = cache_probe(p, evict)
            if got is None:
                continue
            n += 1
            emit({"kind": "start_cache", **now_stamp(), "file": b, "path": p,
                  "resident_pages": sum(e - s for s, e in got[0]),
                  "npages": got[1], "evicted": evict})
    return n


# position poller (X-Plane Web API, GET only)

# (key, dataref, required).  Optional ones are logged once as missing.
POS_REFS = (
    ("lat", "sim/flightmodel/position/latitude", True),
    ("lon", "sim/flightmodel/position/longitude", True),
    ("elev_m", "sim/flightmodel/position/elevation", True),
    ("agl_m", "sim/flightmodel/position/y_agl", False),
    ("hdg", "sim/flightmodel/position/true_psi", False),
    ("pitch", "sim/flightmodel/position/true_theta", False),
    ("gs_ms", "sim/flightmodel/position/groundspeed", False),
    ("ias_kt", "sim/flightmodel/position/indicated_airspeed", False),
    ("local_x", "sim/flightmodel/position/local_x", False),
    ("local_y", "sim/flightmodel/position/local_y", False),
    ("local_z", "sim/flightmodel/position/local_z", False),
    ("view_x", "sim/graphics/view/view_x", False),
    ("view_y", "sim/graphics/view/view_y", False),
    ("view_z", "sim/graphics/view/view_z", False),
    ("view_hdg", "sim/graphics/view/view_heading", False),
    ("view_pitch", "sim/graphics/view/view_pitch", False),
    ("view_type", "sim/graphics/view/view_type", False),
    ("fov_deg", "sim/graphics/view/field_of_view_deg", False),
    ("vis_sm", "sim/weather/aircraft/visibility_reported_sm", False),
    ("vis_m", "sim/weather/visibility_reported_m", False),
    ("paused", "sim/time/paused", False),
    ("sim_time_s", "sim/time/total_running_time_sec", False),
    ("frame_s", "sim/time/framerate_period", False),   # U10 stutter
)


def _get(url: str, timeout: float = 2.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def resolve_refs() -> tuple[dict[str, int], list[str]]:
    """Dataref name -> id (ids change when X-Plane reloads; re-resolve)."""
    ids, missing = {}, []
    for key, ref, req in POS_REFS:
        q = urllib.parse.quote(ref, safe="")
        data = _get(f"{WEB_API}/datarefs?filter%5Bname%5D={q}")["data"]
        if data:
            ids[key] = data[0]["id"]
        elif req:
            raise KeyError(f"required dataref missing: {ref}")
        else:
            missing.append(ref)
    return ids, missing


def read_position(ids: dict[str, int]) -> dict:
    rec = {"kind": "pos", **now_stamp()}
    for key, ident in ids.items():
        v = _get(f"{WEB_API}/datarefs/{ident}/value")["data"]
        rec[key] = round(float(v), 6) if isinstance(v, (int, float)) else v
    return rec


def poll_positions(emit, stop: threading.Event, period: float) -> None:
    """Never gives up: any failure (menu, flight load, Web API restart,
    stale ids -> 404) forgets the ids and retries every `period` s for the
    whole recording; at most one pos_error per 30 s; pos_resumed on the
    first good read after a failure."""
    ids: dict[str, int] = {}
    last_err, down_since, n_err = 0.0, None, 0
    while not stop.is_set():
        t0 = time.time()
        try:
            if not ids:
                ids, missing = resolve_refs()
                emit({"kind": "pos_refs", **now_stamp(), "found": sorted(ids),
                      "missing": missing})
            emit(read_position(ids))
            if down_since is not None:
                emit({"kind": "pos_resumed", **now_stamp(),
                      "down_s": round(t0 - down_since, 1), "errors": n_err})
                down_since, n_err = None, 0
        except Exception as e:          # menu, load, restart, stale ids...
            ids = {}
            n_err += 1
            if down_since is None:
                down_since = t0
            if t0 - last_err > 30:
                emit({"kind": "pos_error", **now_stamp(),
                      "error": repr(e)[:300], "errors_since_ok": n_err})
                last_err = t0
        stop.wait(max(0.05, period - (time.time() - t0)))


def now_stamp() -> dict:
    t = time.time()
    return {"utc": _dt.datetime.fromtimestamp(t, _dt.timezone.utc)
            .isoformat(timespec="milliseconds"), "t": round(t, 6)}



def xplane_dir(arg: str | None) -> str | None:
    if arg:
        return arg
    user = os.environ.get("SUDO_USER") or os.environ.get("USER") or ""
    for home in (os.path.expanduser(f"~{user}"), os.path.expanduser("~")):
        d = os.path.join(home, "X-Plane 12")
        if os.path.isdir(d):
            return d
    return None


def custom_scenery_roots(xp: str | None) -> list[str]:
    """Custom Scenery itself plus the real path of every pack in it (most
    Ortho4XP packs are symlinks to another disk; fs_usage prints the real
    path)."""
    if not xp:
        return []
    cs = os.path.join(xp, "Custom Scenery")
    out = {os.path.realpath(cs).rstrip("/") + "/", cs.rstrip("/") + "/"}
    try:
        for d in os.listdir(cs):
            p = os.path.join(cs, d)
            if os.path.isdir(p):
                out.add(os.path.realpath(p).rstrip("/") + "/")
    except OSError:
        pass
    return sorted(out)


def find_pid(name: str) -> int | None:
    try:
        out = subprocess.run(["pgrep", "-x", name], capture_output=True,
                             text=True, timeout=5).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None
    return int(out[0]) if out else None


def seed_from_lsof(tracker: Tracker, pid: int, emit) -> int:
    """Files X-Plane already holds open when recording starts."""
    try:
        out = subprocess.run(["lsof", "-n", "-P", "-p", str(pid), "-Ffn"],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    fd, n = None, 0
    for ln in out.splitlines():
        if ln.startswith("f"):
            fd = int(ln[1:]) if ln[1:].isdigit() else None
        elif ln.startswith("n") and fd is not None:
            tracker.seed(fd, ln[1:])
            if tracker.scope.tracked(ln[1:]):
                n += 1
                emit({"kind": "held_at_start", **now_stamp(), "fd": fd,
                      "file": os.path.basename(ln[1:]), "path": ln[1:]})
    return n


class Writer:
    def __init__(self, path: str):
        self.f = open(path, "a", buffering=1, encoding="utf-8",
                      newline="\n")
        self.lock = threading.Lock()
        self.n = 0

    def __call__(self, rec: dict) -> None:
        line = json.dumps(rec, separators=(",", ":"))
        with self.lock:
            self.f.write(line + "\n")
            self.n += 1

    def close(self) -> None:
        with self.lock:
            self.f.close()


def open_raw(path: str | None):
    if not path:
        return None
    if path.endswith(".gz"):
        return gzip.open(path, "at", compresslevel=1, encoding="utf-8",
                         newline="\n")
    return open(path, "a", encoding="utf-8", newline="\n")


def run_fs_usage(cmd: list[str], tracker: Tracker, clock: TodClock,
                 deadline: float, raw) -> str:
    """Stream fs_usage through a pty (line-buffered) until the deadline."""
    import fcntl
    import pty
    import termios
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 60, 1000, 0, 0))
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=slave,
                            stderr=slave, close_fds=True)
    os.close(slave)
    buf, why, ln = b"", "deadline", 0
    try:
        while True:
            if time.time() > deadline:
                break
            r, _, _ = select.select([master], [], [], 0.5)
            if not r:
                if proc.poll() is not None:
                    why = f"fs_usage exited {proc.returncode}"
                    break
                continue
            try:
                chunk = os.read(master, 1 << 16)
            except OSError:
                why = f"fs_usage exited {proc.poll()}"
                break
            if not chunk:
                break
            buf += chunk
            *lines, buf = buf.split(b"\n")
            for b in lines:
                ln += 1
                text = b.decode("utf-8", "replace").rstrip("\r")
                if raw:
                    raw.write(text + "\n")
                feed_text(tracker, clock, text, ln)
    except KeyboardInterrupt:
        why = "ctrl-c"
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        os.close(master)
    return why


def summary(out, tracker: Tracker, why: str) -> None:
    out({"kind": "summary", **now_stamp(), "version": VERSION,
         "stopped": why, "counts": tracker.counts,
         "calls": tracker.calls, "procs": tracker.procs,
         "read_unknown_fd_calls": tracker.unknown_calls,
         "unparsed": tracker.unparsed, "records": out.n})


def chown_back(*paths) -> None:
    uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if uid and gid:
        for f in filter(None, paths):
            try:
                os.chown(f, int(uid), int(gid))
            except OSError:
                pass


# --------------------------------------------------------------------------
# --check: 30 s pre-flight self-test
# --------------------------------------------------------------------------


def self_test_reads(path: str, report: dict) -> None:
    """Imitate X-Plane on one test-tile DDS (read-only): evict it, open,
    pread 64 KiB at the mip-1 start with the cache off, mmap it and touch
    the header and the last page, close.  The tracer must see all of it."""
    import fcntl
    try:
        info = snapshot(path) or {}
        mips = mip_ranges(info) if "width" in info else []
        off = mips[1][1] if len(mips) > 1 else 0
        cache_probe(path, True)
        fd = os.open(path, os.O_RDONLY)
        report["fd"] = fd
        try:
            try:
                fcntl.fcntl(fd, F_NOCACHE, 1)
            except OSError:
                pass
            os.pread(fd, 65536, off)
            report["pread_offset"] = off
            size = os.fstat(fd).st_size
            m = mmap.mmap(fd, size, prot=mmap.PROT_READ)
            _ = m[0], m[size - 1]
            m.close()
            report["size"] = size
        finally:
            os.close(fd)
        report["done_t"] = time.time()
    except Exception as e:              # reported by the check
        report["error"] = repr(e)


def calibrate_disk(disk: list[dict], info: dict | None) -> str:
    """Which unit turns D= into the F_LOG2PHYS device offset."""
    ext = (info or {}).get("extents")
    if not disk or not ext:
        return "n/a"
    for unit in (512, 4096, 1):
        for r in disk:
            d = r.get("D")
            if d is None:
                continue
            for fo, dev, ln in ext:
                if dev <= d * unit < dev + ln:
                    return (f"D x {unit} lands inside the file's extent "
                            f"(file offset {d * unit - dev + fo})")
    ds = sorted(r["D"] for r in disk if r.get("D") is not None)
    return (f"no direct match (D {ds[:3]}, extents {[e[1] for e in ext][:2]}); "
            "the analysis self-calibrates from the header page")


def run_check(a, scope: Scope, cs_roots: list[str]) -> int:
    print("record_reads.py --check  (about 30 s)", flush=True)
    results = []

    def res(name: str, ok, detail: str) -> None:
        tag = "PASS" if ok is True else ("WARN" if ok is None else "FAIL")
        results.append((tag, name, detail))
        print(f"  {tag}  {name}: {detail}", flush=True)

    out_path = a.out
    if os.path.exists(out_path):
        os.remove(out_path)
    out = Writer(out_path)
    out({"kind": "meta", **now_stamp(), "tool": "record_reads.py --check",
         "version": VERSION})

    free = shutil.disk_usage(os.path.dirname(os.path.abspath(out_path))).free
    res("disk space", free > 5e9, f"{free / 1e9:.0f} GB free next to the log")
    tiles = [os.path.join(r, "textures") for r in scope.tile]
    dds = sorted(os.path.realpath(os.path.join(d, b)) for d in tiles
                 if os.path.isdir(d) for b in os.listdir(d)
                 if b.lower().endswith(".dds") and not b.startswith("."))
    res("test packs", bool(dds), f"{len(dds)} DDS in {', '.join(scope.tile)}")
    if scope.kind == "all":
        res("Custom Scenery", bool(cs_roots) or None,
            f"{len(cs_roots)} pack folders tracked" if cs_roots else
            "X-Plane 12 folder not found (use --xplane); only the packs")

    try:
        ids, missing = resolve_refs()
        rec = read_position(ids)
        res("Web API", True, f"lat {rec['lat']:.5f} lon {rec['lon']:.5f} "
            f"elev {rec['elev_m']:.0f} m; {len(ids)} datarefs"
            + (f"; not available: "
               f"{', '.join(m.rsplit('/', 1)[-1] for m in missing)}"
               if missing else ""))
        out(rec)
    except Exception as e:
        res("Web API", False, f"{e!r} (is X-Plane running?)")

    if os.geteuid() != 0:
        res("fs_usage", False, "needs sudo:  sudo python3 record_reads.py "
            "--pack PACK --check --out check.jsonl")
        out.close()
        return finish_check(results)
    pid = find_pid(a.process)
    if not pid:
        res("X-Plane process", False, f"no process named {a.process}")
    tracker = Tracker(out, scope, None, probe=True, evict=True)
    report: dict = {}
    test = dds[0] if dds else None
    if test:
        threading.Timer(4.0, self_test_reads, (test, report)).start()
    secs = 14
    cmd = ["/usr/bin/fs_usage", "-w", "-f", "filesys", "-t", str(secs + 3)]
    cmd += ([a.process] if pid else []) + [str(os.getpid())]
    raw_path = out_path + ".raw.gz"
    if os.path.exists(raw_path):
        os.remove(raw_path)
    raw = open_raw(raw_path)
    why = run_fs_usage(cmd, tracker, TodClock(_dt.datetime.now()),
                       time.time() + secs, raw)
    raw.close()
    summary(out, tracker, why)
    out.close()
    chown_back(out_path, raw_path)

    xp_lines = sum(v for k, v in tracker.procs.items()
                   if k.startswith(a.process))
    res("fs_usage sees X-Plane", xp_lines > 0 if pid else False,
        f"{tracker.counts.get('lines', 0)} lines, {xp_lines} from "
        f"{a.process} ({why})")
    with open(out_path, encoding="utf-8") as f:
        recs = [json.loads(x) for x in f]
    mine = [r for r in recs if r.get("path") == test]
    rd = [r for r in mine if r["kind"] == "read"]
    ok = any(r.get("offset_known") and r.get("offset") == report.get(
        "pread_offset") for r in rd)
    res("DDS read attributed to file + offset", ok,
        (f"pread of {os.path.basename(test)} at {report.get('pread_offset')}"
         f" seen as fd {rd[0]['fd']} offset {rd[0]['offset']}") if rd else
        f"self-test read NOT seen ({report.get('error', 'ran' if report else 'did not run')};"
        f" opens seen {sum(r['kind'] == 'open' for r in mine)})")
    dk = [r for r in mine if r["kind"] == "disk"]
    rs = [r for r in mine if r["kind"] == "resident" and r.get("pages")]
    res("page-ins seen (how X-Plane reads DDS)", bool(dk) or None,
        f"{len(dk)} PgIn/RdData lines for the test file; "
        f"{calibrate_disk(dk, snapshot(test) if test else None)}")
    res("cache probe after close", bool(rs),
        f"resident pages after close: {rs[-1]['pages'] if rs else 'none'}")
    xd = [r for r in recs if r.get("kind") in ("open", "disk", "resident")
          and r.get("path") != test
          and str(r.get("file", "")).lower().endswith(".dds")]
    res("X-Plane DDS activity during the check", True if xd else None,
        f"{len(xd)} records (none is normal at the main menu or when "
        "sitting still)")
    print(f"  log: {out_path}\n  raw: {raw_path}")
    return finish_check(results)


def finish_check(results) -> int:
    bad = [r for r in results if r[0] == "FAIL"]
    print("\nCHECK " + ("FAILED: " + "; ".join(r[1] for r in bad) if bad
                        else "PASSED - ready to record"), flush=True)
    return 1 if bad else 0


# --------------------------------------------------------------------------


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--pack", action="append", default=[], metavar="DIR",
                   help="a test pack folder (repeatable): its DDS loads are "
                   "probed for mip levels; required to record or --check")
    p.add_argument("--out", required=True, help="the JSONL log to write")
    p.add_argument("--check", action="store_true",
                   help="30 s pre-flight self-test; prints PASS/FAIL")
    p.add_argument("--minutes", type=float,
                   help=f"stop after this long (bounded, at most {MAX_MINUTES})")
    p.add_argument("--scope", choices=("tile", "all", "every"), default="all",
                   help="tile: the test packs; all (default): they plus "
                   "every Custom Scenery pack; every: any .dds/.ter/.dsf")
    p.add_argument("--xplane", help="X-Plane folder (default ~/X-Plane 12)")
    p.add_argument("--process", default="X-Plane",
                   help="process name to trace (default X-Plane)")
    p.add_argument("--poll", type=float, default=1.0,
                   help="seconds between Web API position reads")
    p.add_argument("--raw", help="where to keep fs_usage's raw text "
                   "(default OUT.raw.gz; a name ending .gz is compressed)")
    p.add_argument("--no-raw", action="store_true",
                   help="do not keep the raw text (not recommended)")
    p.add_argument("--no-evict", action="store_true",
                   help="do not drop the test packs' DDS from the file cache "
                   "(re-reads of cached pages are then invisible)")
    p.add_argument("--from-text", metavar="FILE",
                   help="parse a saved fs_usage -w text dump (plain or .gz) "
                   "instead: no sudo, no Web API, no cache probing")
    p.add_argument("--date", help="with --from-text: the dump's local date "
                   "YYYY-MM-DD (default today)")
    a = p.parse_args(argv)
    if not a.from_text:
        if not a.pack:
            p.error("--pack DIR is required (the test pack to probe)")
        if not a.check and a.minutes is None:
            p.error("--minutes is required (or use --check / --from-text)")
        if a.minutes is not None and not 0 < a.minutes <= MAX_MINUTES:
            p.error(f"--minutes must be in (0, {MAX_MINUTES}]")
    return a


def write_meta(out, a, scope: Scope, xp, cs_roots, raw_path) -> None:
    out({"kind": "meta", **now_stamp(), "tool": "record_reads.py",
         "version": VERSION, "scope": a.scope, "process": a.process,
         "packs": a.pack, "tile_roots": list(scope.tile),
         "xplane": xp, "custom_scenery_roots": len(cs_roots),
         "minutes": a.minutes, "raw": raw_path, "evict": not a.no_evict,
         "page_size": PAGE, "source": a.from_text or "fs_usage"})


def parse_text_dump(a, scope: Scope) -> None:
    """--from-text: replay a saved fs_usage text dump through the tracker."""
    out = Writer(a.out)
    write_meta(out, a, scope, None, [], None)
    start = (_dt.datetime.strptime(a.date, "%Y-%m-%d") if a.date
             else _dt.datetime.now())
    tracker = Tracker(out, scope, a.process + ".", probe=False, evict=False)
    clock = TodClock(start)
    opener = gzip.open if a.from_text.endswith(".gz") else open
    with opener(a.from_text, "rt", encoding="utf-8", errors="replace") as f:
        for ln, text in enumerate(f, 1):
            feed_text(tracker, clock, text.rstrip("\n"), ln)
    summary(out, tracker, "end of text")
    out.close()
    print(f"parsed {a.from_text}: {tracker.counts} -> {a.out}")


def record(a, scope: Scope, xp, cs_roots) -> None:
    """The flight: fs_usage + the position poller until --minutes/Ctrl-C."""
    if os.geteuid() != 0:
        sys.exit("fs_usage needs root: run   sudo python3 record_reads.py "
                 "--pack PACK --minutes 30 --out flight.jsonl")
    free = shutil.disk_usage(os.path.dirname(os.path.abspath(a.out))).free
    if free < 3e9:
        sys.exit(f"only {free / 1e9:.1f} GB free next to {a.out}; need 3 GB")
    raw_path = None if a.no_raw else (a.raw or a.out + ".raw.gz")
    out = Writer(a.out)
    write_meta(out, a, scope, xp, cs_roots, raw_path)
    tracker = Tracker(out, scope, None, probe=True, evict=not a.no_evict)
    n = cache_reset(out, scope, not a.no_evict)
    print(f"test packs: {n} DDS " + ("evicted from the file cache"
                                     if not a.no_evict else "probed"))
    pid = find_pid(a.process)
    if pid:
        n = seed_from_lsof(tracker, pid, out)
        print(f"{a.process} pid {pid}; {n} tracked file(s) already open")
    else:
        print(f"{a.process} is not running yet; tracing by name anyway")
    stop = threading.Event()
    poller = threading.Thread(target=poll_positions,
                              args=(out, stop, a.poll), daemon=True)
    poller.start()
    secs = int(a.minutes * 60)
    cmd = ["/usr/bin/fs_usage", "-w", "-f", "filesys", "-t", str(secs + 5),
           a.process]
    raw = open_raw(raw_path)
    print(f"{time.strftime('%H:%M:%S')} recording for {a.minutes:g} min "
          f"-> {a.out}  (raw text -> {raw_path})   (Ctrl-C stops early)",
          flush=True)
    try:
        why = run_fs_usage(cmd, tracker, TodClock(_dt.datetime.now()),
                           time.time() + secs, raw)
    except KeyboardInterrupt:
        why = "ctrl-c"
    stop.set()
    poller.join(timeout=5)
    if raw:
        raw.close()
    summary(out, tracker, why)
    out.close()
    chown_back(a.out, raw_path)
    print(f"{time.strftime('%H:%M:%S')} stopped ({why}); {out.n} records; "
          f"counts {tracker.counts}")
    if why == "deadline":
        print("TIMED_OUT: --minutes reached")


def main(argv=None) -> None:
    a = parse_args(argv)
    if a.from_text:
        parse_text_dump(a, Scope(a.scope, a.pack, []))
        return
    xp = xplane_dir(a.xplane)
    cs_roots = custom_scenery_roots(xp) if a.scope == "all" else []
    scope = Scope(a.scope, a.pack, cs_roots)
    if a.check:
        sys.exit(run_check(a, scope, cs_roots))
    record(a, scope, xp, cs_roots)


if __name__ == "__main__":
    main()
