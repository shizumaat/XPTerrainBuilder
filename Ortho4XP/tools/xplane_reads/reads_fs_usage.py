"""fs_usage -w text -> X-Plane read records (#1992 read recorder).

``parse_line`` reads one fs_usage line; ``Tracker`` keeps the fd table
(keyed by process name and fd: two processes, or the recorder's own
self-test, can hold the same fd number) and turns calls on tracked files
into JSONL records; ``Scope`` says which paths are tracked and which are the
test packs'.  Standard library only; importable on any platform.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import time

from reads_page_cache import PAGE, cache_probe, snapshot

EXTS = (".dds", ".ter", ".dsf")
OPEN_CALLS = {"open", "open_nocancel", "openat", "openat_nocancel",
              "open_extended", "guarded_open_np", "open_dprotected_np",
              "guarded_open_dprotected_np", "openbyid_np"}
CLOSE_CALLS = {"close", "close_nocancel", "guarded_close_np"}
SEQ_READS = {"read", "read_nocancel", "readv", "readv_nocancel"}
POS_READS = {"pread", "pread_nocancel", "preadv", "preadv_nocancel"}
DISK_CALLS = ("PgIn", "RdData", "RdMeta", "PAGE_IN")   # prefixes
OFFSET_MASK = 0xFFFFFFFFFF   # fs_usage packs flag bits above bit 40 of O=

LINE = re.compile(r"^\s*(\d\d):(\d\d):(\d\d)\.(\d+)\s+(\S+)\s?(.*?)"
                  r"\s+(\d+\.\d{6})( W)?\s+(\S.*?)\s*$")
FIELD = re.compile(r"\b([FBOADS])=(0x[0-9a-fA-F]+|-?\d+)")
ERRNO = re.compile(r"\[\s*(\d+)\]")
MODE = re.compile(r"\([A-Za-z_]+\)")


def parse_line(line: str) -> dict | None:
    """One fs_usage -w line -> {tod, call, F, B, O, D, errno, dev, path,
    proc, pname}.  O= is the file offset with fs_usage's flag bits above
    bit 40 masked off (seen 2026-11-10: a pread at 0x800080 printed as
    O=0x01000000800080); pname is the process name without the thread id."""
    m = LINE.match(line)
    if not m:
        return None
    hh, mm, ss, frac, call, mid, elapsed, _wait, proc = m.groups()
    ev = {"tod": (int(hh), int(mm), int(ss), int(frac.ljust(6, "0")[:6])),
          "call": call, "proc": proc, "pname": proc.rsplit(".", 1)[0],
          "elapsed": float(elapsed)}
    for k, v in FIELD.findall(mid):
        ev[k] = int(v, 16) if v.startswith("0x") else int(v)
    if "O" in ev:
        ev["O"] &= OFFSET_MASK
    e = ERRNO.search(mid)
    if e:
        ev["errno"] = int(e.group(1))
    rest = MODE.sub(" ", ERRNO.sub(" ", FIELD.sub(" ", mid)))
    parts = [p.strip() for p in re.split(r"\s{2,}", rest) if p.strip()]
    devs = [p for p in parts if p.startswith("/dev/")]
    if devs:
        ev["dev"] = devs[0].split()[0]
        # "/dev/disk3s1 /path..." when only one space separates them
        tail = devs[0].split(None, 1)
        if len(tail) > 1:
            parts.append(tail[1])
    parts = [p for p in parts if not p.startswith("/dev/")]
    if parts:
        ev["path"] = parts[-1]
    return ev


def stamp_of(dt: _dt.datetime) -> dict:
    return {"utc": dt.isoformat(timespec="microseconds"),
            "t": round(dt.timestamp(), 6)}


class TodClock:
    """fs_usage prints local time of day only; anchor it to a date and roll
    over at midnight (a jump back of more than 12 h is the next day)."""

    def __init__(self, start: _dt.datetime):
        self.day = start.date()
        self.last: _dt.datetime | None = None

    def stamp(self, tod: tuple[int, int, int, int]) -> _dt.datetime:
        dt = _dt.datetime.combine(self.day, _dt.time(*tod))
        if self.last is not None and dt < self.last - _dt.timedelta(hours=12):
            self.day += _dt.timedelta(days=1)
            dt += _dt.timedelta(days=1)
        self.last = dt
        return dt.astimezone(_dt.timezone.utc)   # naive = local time


def _root(path: str) -> str:
    """A pack root as fs_usage prints it: the real path (packs are often
    symlinks to another disk), with one trailing slash."""
    real = os.path.realpath(path) if os.path.exists(path) else path
    return real.rstrip("/") + "/"


class Scope:
    """Which paths are tracked, and which are the test packs' (by real path:
    flight 1 matched basenames and also caught neighbouring packs' copies of
    the border textures).  tile = the test packs only; all = they plus the
    Custom Scenery roots; every = any .dds/.ter/.dsf."""

    def __init__(self, kind: str, tile_roots: list[str], cs_roots: list[str]):
        self.kind = kind
        self.tile = tuple(_root(r) for r in tile_roots)
        self.roots = self.tile + tuple(cs_roots)
        self._memo: dict[str, bool] = {}

    def tracked(self, path: str | None) -> bool:
        if not path or not path.lower().endswith(EXTS):
            return False
        if self.kind == "every":
            return True
        hit = self._memo.get(path)
        if hit is None:
            roots = self.tile if self.kind == "tile" else self.roots
            hit = path.startswith(roots)
            if len(self._memo) < 200000:
                self._memo[path] = hit
        return hit

    def in_tile(self, path: str | None) -> bool:
        return bool(path) and path.startswith(self.tile)


class Tracker:
    """fd table + filter; turns parsed fs_usage events into log records."""

    def __init__(self, emit, scope: Scope, proc_prefix: str | None,
                 probe: bool, evict: bool, samples: int = 3):
        self.emit, self.scope, self.proc = emit, scope, proc_prefix
        self.probe, self.evict = probe, evict
        self.fds: dict = {}  # (process name, fd) -> entry
        self.seen: dict[str, tuple] = {}
        self.counts: dict[str, int] = {}
        self.calls: dict[str, int] = {}
        self.unknown_calls: dict[str, int] = {}
        self.samples: dict[str, int] = {}
        self.nsample = samples
        self.unparsed = 0
        self.procs: dict[str, int] = {}

    def _bump(self, k: str, d: dict | None = None) -> None:
        d = self.counts if d is None else d
        d[k] = d.get(k, 0) + 1

    def _file_event(self, when, path: str) -> None:
        snap = snapshot(path) if path.startswith("/") else None
        key = (snap or {}).get("size"), (snap or {}).get("width")
        if self.seen.get(path) == key:
            return
        self.seen[path] = key
        self.emit({"kind": "file", **when, "file": os.path.basename(path),
                   "path": path, "tile": self.scope.in_tile(path),
                   **(snap or {"unreadable": True})})

    def seed(self, fd: int, path: str, seed_proc: str = "X-Plane") -> None:
        self.fds[(seed_proc, fd)] = {"path": path, "pos": None}

    def raw_bad(self, text: str, ln: int) -> None:
        """A line the parser could not read (header, error, wrap...)."""
        self.unparsed += 1
        if self.unparsed <= 40 and text.strip():
            self.emit({"kind": "unparsed", "ln": ln, "text": text[:400]})

    def feed(self, ev: dict, when: dict, text: str = "", ln: int = 0) -> None:
        """One parsed fs_usage event -> zero or more records."""
        self._bump("lines")
        call = ev["call"]
        self._bump(call, self.calls)
        self._bump(ev["pname"], self.procs)
        if self.samples.get(call, 0) < self.nsample:
            self.samples[call] = self.samples.get(call, 0) + 1
            self.emit({"kind": "sample", **when, "call": call, "ln": ln,
                       "text": text[:400]})
        if self.proc and not ev["proc"].startswith(self.proc):
            return
        rec = {"kind": None, **when, "call": call, "fd": ev.get("F"),
               "proc": ev["pname"], "ln": ln}
        if call in OPEN_CALLS:
            self._on_open(ev, rec, when)
        elif call in CLOSE_CALLS:
            self._on_close(ev, rec, when)
        elif call.startswith(DISK_CALLS):
            self._on_disk(ev, rec)
        else:
            self._on_fd_call(ev, rec)

    def _on_open(self, ev: dict, rec: dict, when: dict) -> None:
        fd, path = ev.get("F"), ev.get("path")
        if ev.get("errno"):
            if self.scope.tracked(path):
                self._bump("open_fail")
                self.emit({**rec, "kind": "open_fail",
                           "file": os.path.basename(path), "path": path,
                           "errno": ev["errno"]})
            return
        if fd is None or not path:
            return
        self.fds[(ev["pname"], fd)] = {"path": path, "pos": 0}
        if self.scope.tracked(path):
            self._bump("open")
            self._file_event(when, path)
            self.emit({**rec, "kind": "open", "file": os.path.basename(path),
                       "path": path, "tile": self.scope.in_tile(path)})

    def _on_close(self, ev: dict, rec: dict, when: dict) -> None:
        if ev.get("F") is None:
            return
        ent = self.fds.pop((ev["pname"], ev["F"]), None)
        if ent and self.scope.tracked(ent["path"]):
            self._bump("close")
            self.emit({**rec, "kind": "close",
                       "file": os.path.basename(ent["path"]),
                       "path": ent["path"]})
            self._after_close(when, ent["path"])

    def _on_disk(self, ev: dict, rec: dict) -> None:
        path = ev.get("path")
        if self.scope.tracked(path):
            self._bump("disk")
            self.emit({**rec, "kind": "disk", "file": os.path.basename(path),
                       "path": path, "D": ev.get("D"), "bytes": ev.get("B"),
                       "dev": ev.get("dev"),
                       **({"errno": ev["errno"]} if "errno" in ev else {})})

    def _on_fd_call(self, ev: dict, rec: dict) -> None:
        """lseek / read / pread / mmap / anything else on a known fd, or a
        path call (stat64, getattrlist...) on a tracked file."""
        call, fd, path = ev["call"], ev.get("F"), ev.get("path")
        ent = self.fds.get((ev["pname"], fd)) if fd is not None else None
        if call.startswith("lseek") and ent is not None:
            ent["pos"] = ev.get("O")
        elif call in SEQ_READS or call in POS_READS:
            self._on_read(ev, rec, ent)
        elif ent is not None and self.scope.tracked(ent["path"]):
            kind = "mmap" if call.startswith("mmap") else "fd_other"
            self._bump(kind)
            self.emit({**rec, "kind": kind,
                       "file": os.path.basename(ent["path"]),
                       "path": ent["path"], "bytes": ev.get("B"),
                       "offset": ev.get("O")})
        elif self.scope.tracked(path):
            self._bump("other")
            self.emit({**rec, "kind": "other", "file": os.path.basename(path),
                       "path": path, "bytes": ev.get("B"),
                       "offset": ev.get("O")})

    def _on_read(self, ev: dict, rec: dict, ent: dict | None) -> None:
        call = ev["call"]
        if ent is None:
            self._bump("read_unknown_fd")
            self._bump(call, self.unknown_calls)
            return
        nbytes = ev.get("B", 0)
        if not self.scope.tracked(ent["path"]):
            if call in SEQ_READS and ent["pos"] is not None:
                ent["pos"] += nbytes
            return
        if call in POS_READS:
            off, known = ev.get("O"), "O" in ev
        else:
            off, known = ent["pos"], ent["pos"] is not None
            if ent["pos"] is not None:
                ent["pos"] += nbytes
        self._bump("read")
        self.emit({**rec, "kind": "read", "file": os.path.basename(ent["path"]),
                   "path": ent["path"], "offset": off, "bytes": nbytes,
                   "offset_known": known,
                   **({"errno": ev["errno"]} if "errno" in ev else {})})

    def _after_close(self, when: dict, path: str) -> None:
        """Test-tile DDS closed: which pages are resident now = what this
        load touched (they were evicted after the previous load)."""
        if not (self.probe and self.scope.in_tile(path)
                and path.lower().endswith(".dds")):
            return
        t0 = time.time()
        got = cache_probe(path, self.evict)
        self._bump("resident")
        self.emit({"kind": "resident", **when, "file": os.path.basename(path),
                   "path": path, "probe_t": round(t0, 6),
                   "pages": got[0] if got else None,
                   "npages": got[1] if got else None, "page_size": PAGE,
                   "evicted": bool(got) and self.evict})


def feed_text(tracker: Tracker, clock: TodClock, text: str, ln: int) -> None:
    """One raw fs_usage line into the tracker (or its unparsed count)."""
    ev = parse_line(text)
    if ev:
        tracker.feed(ev, stamp_of(clock.stamp(ev["tod"])), text, ln)
    else:
        tracker.raw_bad(text, ln)
