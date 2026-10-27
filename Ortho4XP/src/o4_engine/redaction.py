"""Redaction of text that leaves the user's machine (issue #565).

Owner RULINGS 2026-10-12b: a failure report is REDACTED before it leaves
the machine and the user sees it before it is sent.  The issue tracker is
PUBLIC, and the engine log carries the user's home folder, user name and
whatever a proxy or provider URL carried.  This module is the ONE place
that removes them; :mod:`o4_engine.failure_report` is its only caller so
far, and any later channel (the relay, #566) passes through it too.

THE RULES (:data:`RULES` is the same list in the words the report prints):

1. Home folder and user name.  ``/Users/<name>``, ``/home/<name>``,
   ``/root``, ``X:\\Users\\<name>``, ``X:\\Documents and Settings\\<name>``
   and ``~`` become ``<home>`` whoever the user is; the names seen there,
   plus the ones the caller declares (login name, full name), become
   ``<user>`` wherever else they stand as a word.  A declared host name
   becomes ``<host>``.
2. Paths.  A path under a DECLARED root keeps everything below the root
   (``<data>/OSM_data/...``, ``<xplane>/Custom Scenery/<pack>/...``).  With
   no root declared, the folder names X-Plane and this engine give their
   own trees (:data:`ROOT_MARKERS`) are the witness: the path is kept from
   that folder down.  Any other absolute path is reduced to its last
   component (``<path>/session.py``).
3. Proxies.  The value of anything named ``...proxy...`` and every URL on
   a line that names a proxy become ``<proxy>``.
4. Credentials.  ``user:password@`` in a URL, secret-named URL query
   values, ``Bearer`` / ``Basic`` tokens and ``password=`` / ``token=`` /
   ``api_key=`` style assignments become ``<redacted>``.
5. E-mail addresses become ``<email>``.

KEPT ON PURPOSE: scenery pack names, airport names and identifiers, tile
names and coordinates — they are the diagnosis.

Over-redaction is the safe direction and is chosen wherever the text is
ambiguous: a path that contains spaces has no certain end, so prose that
follows one up to the next separator may be dropped with it.

Stdlib only (the frozen engine and the airport workers may import it).
"""

from __future__ import annotations

import os
import re
import socket
from typing import Iterable, List, Mapping, Optional, Tuple

try:  # POSIX only; the full name is one more spelling of the user.
    import pwd as _pwd
except ImportError:  # pragma: no cover - Windows
    _pwd = None

__all__ = ["RULES", "KEPT", "ROOT_MARKERS", "Redactor"]

RULES = (
    "your home folder and user name (shown as <home> and <user>)",
    "every path outside the scenery and data folders, reduced to its file "
    "name (shown as <path>/name)",
    "proxy addresses (<proxy>)",
    "passwords, tokens and keys (<redacted>)",
    "e-mail addresses (<email>)",
)
KEPT = "scenery pack names, airport names, tile names and coordinates"

# The folder names X-Plane and this engine give their own trees: a path is
# kept from the first of these down when no root was declared for it.
ROOT_MARKERS = {
    "custom scenery": "xplane",
    "global scenery": "xplane",
    "osm_data": "data",
    "elevation_data": "data",
    "orthophotos": "data",
    "geotiffs": "data",
    "masks": "data",
    "patches": "data",
    "tiles": "data",
    "previews": "data",
    "airport_mod_cache": "data",
    "default_dsf_cache": "data",
    "yortho4xp_overlays": "data",
}

_SEP = r"[\\/]"
_URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.\-]*://[^\s\"'<>]+")
_USERINFO = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*://)[^/@\s]+@")
_SECRET_NAME = (r"(?:pass(?:word|wd)?|pwd|token|api[_\-]?key|api|key|secret|sig"
                r"(?:nature)?|auth(?:orization)?|access[_\-]?(?:token|key)|"
                r"client[_\-]?secret|session(?:[_\-]?id)?|cookie)")
_SECRET_QUERY = re.compile(r"(?i)([?&;](?:[\w\-]*[_\-])?%s)=[^&#\s]*"
                           % _SECRET_NAME)
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=\-]{8,}")
_SECRET_ASSIGN = re.compile(
    r"(?i)\b((?:[\w\-]*[_\-])?%s)\b(\s*[=:]\s*)(?!<)\S+" % _SECRET_NAME)
_PROXY_ASSIGN = re.compile(r"(?i)\b([\w\-]*prox(?:y|ies)[\w\-]*)(\s*[=:]\s*)\S+")
_PROXY_WORD = re.compile(r"(?i)prox(?:y|ies)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")

# Home folders, whoever the user is.  A Windows name may hold spaces, so it
# runs to the next separator when there is one.
_WIN_HOME = re.compile(
    r"(?i)(?<![A-Za-z])[A-Z]:[\\/]+(?:Users|Documents and Settings)[\\/]+"
    r"(?:([^\\/:*?\"<>|\r\n]+?)(?=[\\/])|([^\\/\s:*?\"<>|]+))")
_POSIX_HOME = re.compile(r"(?<![<>])(?:/mnt/[a-z])?/(?:Users|home)/([^/\s\"']+)")
_ROOT_HOME = re.compile(r"(?<![\w<>/\\.])/root(?=[/\s\"']|$)")
_TILDE = re.compile(r"(?<![\w<>])~(?=[\\/])")

# Where an absolute path starts, and the text that certainly ends one.
_PATH_START = re.compile(
    r"<[a-z]+>(?=[\\/])"
    r"|(?<![A-Za-z])[A-Za-z]:[\\/]"
    r"|\\\\(?=[^\\\s])"
    r"|(?<![\w<>/\\.\x00])/(?=[^\s/])")
_PATH_STOP = re.compile(
    r"\t|  |[\"<>|*?\x00]|, |; |: | [\\/]| [A-Za-z]:[\\/]|$")
_PLACEHOLDER = re.compile(r"\x00(\d+)\x00")


def _root_pattern(path: str) -> Optional[re.Pattern]:
    """A declared root, matched with either separator (and without regard
    to case when it is a drive-letter path)."""
    parts = [p for p in re.split(_SEP, path.strip()) if p]
    # A bare drive ("E:\\") is no root: everything on it, a home folder
    # included, would be kept.  Its folders are read by ROOT_MARKERS.
    if not parts or (len(parts) == 1 and re.fullmatch(r"[A-Za-z]:", parts[0])):
        return None
    lead = ""
    stripped = path.strip()
    if stripped.startswith("\\\\") or stripped.startswith("//"):
        lead = _SEP + _SEP
    elif stripped[:1] in "\\/":
        lead = _SEP
    body = (_SEP + "+").join(re.escape(p) for p in parts)
    flags = re.IGNORECASE if re.match(r"[A-Za-z]:", parts[0]) else 0
    return re.compile(r"(?<![\w<>])" + lead + body + r"(?![\w.\-])", flags)


def _word_pattern(word: str) -> re.Pattern:
    return re.compile(r"(?i)(?<![A-Za-z0-9<])" + re.escape(word)
                      + r"(?![A-Za-z0-9>])")


class Redactor:
    """Applies :data:`RULES` to lines of text.

    ``roots`` maps a label to the folders it names, e.g. ``{"data":
    ["/Volumes/SSD/XPData"], "xplane": ["D:\\\\X-Plane 12"]}``: text below
    a root is kept under ``<label>``.  ``home``, ``users`` and ``hosts``
    declare what the pattern rules cannot see (a home outside ``/Users``,
    a full name, the machine name).  Names found in home paths while
    redacting are remembered for the following lines.
    """

    def __init__(self, roots: Optional[Mapping[str, Iterable[str]]] = None,
                 home: str = "", users: Iterable[str] = (),
                 hosts: Iterable[str] = ()) -> None:
        declared: List[Tuple[str, str]] = []
        for label, paths in (roots or {}).items():
            for path in ([paths] if isinstance(paths, str) else paths):
                if path and len(re.sub(_SEP, "", path)) > 1:
                    declared.append((path, "<%s>" % label))
        if home and len(re.sub(_SEP, "", home)) > 1:
            declared.append((home, "<home>"))
        declared.sort(key=lambda item: len(item[0]), reverse=True)
        self._roots = [(pattern, label) for pattern, label in
                       ((_root_pattern(p), label) for p, label in declared)
                       if pattern is not None]
        self._users: dict = {}
        self._hosts = [_word_pattern(h) for h in
                       sorted({h.strip() for h in hosts if len(h.strip()) > 1},
                              key=len, reverse=True)]
        for name in users:
            self._remember(name)
        if home:
            self._remember(re.split(_SEP, home.rstrip("\\/"))[-1])

    @classmethod
    def for_this_machine(cls, roots: Optional[Mapping[str, Iterable[str]]]
                         = None) -> "Redactor":
        """A redactor that knows this machine's home, login and host."""
        home = os.path.expanduser("~")
        users = [os.environ.get(k, "") for k in
                 ("USER", "USERNAME", "LOGNAME")]
        if _pwd is not None:
            try:
                entry = _pwd.getpwuid(os.getuid())
                users += [entry.pw_name, entry.pw_gecos.split(",")[0]]
            except (KeyError, OSError):
                pass
        try:
            host = socket.gethostname()
        except OSError:
            host = ""
        hosts = [host, host.split(".")[0]]
        if home in ("~", ""):
            home = ""
        return cls(roots=roots, home=home, users=users, hosts=hosts)

    # -- names -----------------------------------------------------------
    def _remember(self, name: str) -> None:
        name = (name or "").strip()
        if len(name) > 1 and name.lower() not in self._users:
            self._users[name.lower()] = _word_pattern(name)

    def _harvest(self, line: str) -> None:
        for match in _WIN_HOME.finditer(line):
            self._remember(match.group(1) or match.group(2))
        for match in _POSIX_HOME.finditer(line):
            self._remember(match.group(1))

    # -- the rules -------------------------------------------------------
    @staticmethod
    def _url(url: str, proxy_line: bool) -> str:
        if proxy_line:
            return "<proxy>"
        url = _USERINFO.sub(r"\1<redacted>@", url)
        return _SECRET_QUERY.sub(r"\1=<redacted>", url)

    @staticmethod
    def _reduce_path(span: str) -> str:
        """One absolute path and whatever prose the stop rule left on it:
        kept from a root marker down, else reduced to its last component."""
        segments = re.split("(" + _SEP + "+)", span)
        offset = 0
        last = len(segments) - 1
        for index, segment in enumerate(segments):
            key = segment.lower()
            label = ROOT_MARKERS.get(key)
            if label is None and index == last:
                head = key.split(" ")
                for size in (2, 1):
                    label = label or ROOT_MARKERS.get(" ".join(head[:size]))
            if label is not None and index > 0:
                return "<%s>/%s" % (label, span[offset:])
            offset += len(segment)
        tail = segments[-1]
        if not tail.strip() and len(segments) >= 3:
            return "<path>/" + segments[-3].strip() + "/" + tail
        name, space, rest = tail.partition(" ")
        return "<path>/" + name + space + rest

    def _paths(self, line: str) -> str:
        out: List[str] = []
        position = 0
        while True:
            start = _PATH_START.search(line, position)
            if start is None:
                break
            stop = _PATH_STOP.search(line, start.end())
            end = stop.start() if stop else len(line)
            out.append(line[position:start.start()])
            span = line[start.start():end]
            # A span under a root label is already what the report keeps;
            # only its extent matters, so a "/" inside it starts nothing.
            kept = start.group(0).startswith("<") and start.group(0) != "<home>"
            out.append(span if kept else self._reduce_path(span))
            position = end
        out.append(line[position:])
        return "".join(out)

    def line(self, line: str) -> str:
        """One line, redacted."""
        self._harvest(line)
        proxy_line = bool(_PROXY_WORD.search(line))
        line = line.replace("\x00", " ")
        line = _PROXY_ASSIGN.sub(r"\1\2<proxy>", line)
        kept: List[str] = []

        def stash(match: re.Match) -> str:
            kept.append(self._url(match.group(0), proxy_line))
            return "\x00%d\x00" % (len(kept) - 1)

        line = re.sub(r"\bfile://(?:localhost)?(?=/)", "", line)
        line = _URL.sub(stash, line)
        line = _BEARER.sub(r"\1 <redacted>", line)
        line = _SECRET_ASSIGN.sub(r"\1\2<redacted>", line)
        line = _EMAIL.sub("<email>", line)
        for pattern, label in self._roots:
            line = pattern.sub(lambda _m, label=label: label, line)
        line = _WIN_HOME.sub("<home>", line)
        line = _POSIX_HOME.sub("<home>", line)
        line = _ROOT_HOME.sub("<home>", line)
        line = _TILDE.sub("<home>", line)
        line = self._paths(line)
        for pattern in self._users.values():
            line = pattern.sub("<user>", line)
        for pattern in self._hosts:
            line = pattern.sub("<host>", line)
        return _PLACEHOLDER.sub(lambda m: kept[int(m.group(1))], line)

    def lines(self, lines: Iterable[str]) -> List[str]:
        """Many lines: every user name any of them reveals is removed from
        all of them, whichever line it first stood on."""
        lines = list(lines)
        for line in lines:
            self._harvest(line)
        return [self.line(line) for line in lines]

    def text(self, text: str) -> str:
        """A block of text, line by line (see :meth:`lines`)."""
        return "\n".join(self.lines(text.split("\n")))
