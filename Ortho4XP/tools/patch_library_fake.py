"""A FAKE GITHUB FOR THE PATCH LIBRARY (#1699 phase 2) — the tests' and
the gate's library, with no network.

The library is a BARE git repository (``ROOT/upstream.git``, branch
``main``) seeded from a template folder (``library_template/`` or a
test's own), a fork is another bare repository (``ROOT/forks/<login>.git``),
and the raw files the app reads are a working clone (``ROOT/served``,
``file://`` — what raw.githubusercontent.com serves).  :class:`FakeGitHub`
answers the calls ``patch_library.github`` makes — the device sign-in,
``/user``, forks, ``merge-upstream``, git data (blobs, trees, commits,
refs) and pull requests — through ``patch_library.github.TRANSPORT``, by
running git plumbing on those repositories.  The library's side is two
helpers: :meth:`FakeGitHub.run_checks` (the pull-request workflow:
``patch_library.checks.check_pull`` on checkouts of the head and the
base) and :meth:`FakeGitHub.merge` (merge, rebuild the index with
``patch_library.index.rebuild``, push, refresh ``served``).

    fake = FakeGitHub(root, template_dir, users={"tok-dev": "dev"})
    fake.environ()          # the XPTB_LIBRARY_* settings pointing at it
    patch_library.github.TRANSPORT = fake.transport
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse

__all__ = ["API", "OAUTH", "REPO", "FakeGitHub"]

API = "https://api.github.invalid"
OAUTH = "https://github.invalid"
REPO = "xptb-test/library"

_GIT_ENV = {"GIT_AUTHOR_NAME": "fake", "GIT_AUTHOR_EMAIL": "fake@invalid",
            "GIT_COMMITTER_NAME": "fake", "GIT_COMMITTER_EMAIL": "fake@invalid",
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _git(*args, cwd=None, git_dir=None, data=None, env=None) -> str:
    cmd = ["git"] + (["--git-dir", git_dir] if git_dir else []) + list(args)
    full = dict(os.environ, **_GIT_ENV, **(env or {}))
    out = subprocess.run(cmd, cwd=cwd, input=data, capture_output=True, env=full,
                         check=False)
    if out.returncode:
        raise RuntimeError("git %s failed: %s" % (" ".join(args),
                                                  out.stderr.decode("utf-8", "replace")))
    return out.stdout.decode("utf-8").strip()


class FakeGitHub:
    """One fake GitHub with one library repository (module doc)."""

    def __init__(self, root: str, template: str, users: dict,
                 polls_before_ok: int = 1):
        self.root = os.path.abspath(root)
        self.users = dict(users)                 # token -> login
        self.pulls: dict = {}
        self.polls_before_ok = polls_before_ok
        self._polls = 0
        self.upstream = os.path.join(self.root, "upstream.git")
        self.served = os.path.join(self.root, "served")
        os.makedirs(self.root, exist_ok=True)
        _git("init", "--bare", "-b", "main", self.upstream)
        seed = os.path.join(self.root, "seed")
        shutil.copytree(template, seed)
        _git("init", "-b", "main", cwd=seed)
        _git("add", "-A", cwd=seed)
        _git("commit", "-m", "library template", cwd=seed)
        _git("push", self.upstream, "main", cwd=seed)
        shutil.rmtree(seed)
        _git("clone", "-q", self.upstream, self.served)

    # ── settings ───────────────────────────────────────────────────────
    def environ(self) -> dict:
        return {"XPTB_LIBRARY_REPO": REPO, "XPTB_LIBRARY_RAW": "file://" + self.served,
                "XPTB_LIBRARY_API": API, "XPTB_LIBRARY_OAUTH": OAUTH,
                "XPTB_LIBRARY_CLIENT_ID": "fake-client-id", "XPTB_LIBRARY_BRANCH": "main"}

    def _repo_dir(self, full: str) -> str | None:
        if full == REPO:
            return self.upstream
        owner, _sep, name = full.partition("/")
        path = os.path.join(self.root, "forks", owner + ".git")
        return path if name == REPO.split("/")[1] and os.path.isdir(path) else None

    # ── the transport ──────────────────────────────────────────────────
    def transport(self, method: str, url: str, headers: dict, body: bytes | None):
        try:
            status, doc = self._route(method, url, headers, body)
        except _Http as error:
            status, doc = error.status, {"message": error.message}
        return status, json.dumps(doc).encode("utf-8")

    def _login(self, headers: dict) -> str:
        token = (headers.get("Authorization") or "").replace("Bearer ", "")
        if token not in self.users:
            raise _Http(401, "Bad credentials")
        return self.users[token]

    def _route(self, method, url, headers, body):
        if url.startswith(OAUTH):
            form = dict(urllib.parse.parse_qsl((body or b"").decode("ascii")))
            if url.endswith("/login/device/code"):
                return 200, {"device_code": "dev-code", "user_code": "WDJB-MJHT",
                             "verification_uri": OAUTH + "/login/device",
                             "interval": 0, "expires_in": 900}
            self._polls += 1
            if form.get("device_code") != "dev-code":
                return 200, {"error": "expired_token"}
            if self._polls <= self.polls_before_ok:
                return 200, {"error": "authorization_pending"}
            return 200, {"access_token": next(iter(self.users)), "token_type": "bearer"}
        path = url[len(API):]
        doc = json.loads(body.decode("utf-8")) if body else {}
        login = self._login(headers)
        if method == "GET" and path == "/user":
            return 200, {"login": login}
        m = re.match(r"^/repos/([^/]+/[^/]+)(/.*)?$", path)
        if m is None:
            raise _Http(404, "Not Found")
        full, rest = m.group(1), m.group(2) or ""
        if rest == "/forks" and method == "POST":
            return self._fork(full, login)
        repo = self._repo_dir(full)
        if repo is None:
            raise _Http(404, "Not Found")
        if rest == "" and method == "GET":
            return 200, {"full_name": full}
        return self._git_api(method, full, repo, rest, doc, login)

    def _fork(self, full: str, login: str):
        if full != REPO:
            raise _Http(404, "Not Found")
        path = os.path.join(self.root, "forks", login + ".git")
        if not os.path.isdir(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            _git("clone", "-q", "--bare", self.upstream, path)
        return 202, {"full_name": "%s/%s" % (login, REPO.split("/")[1])}

    def _git_api(self, method, full, repo, rest, doc, login):
        owner = full.split("/")[0]
        if owner != login and full != REPO and method != "GET":
            raise _Http(403, "Resource not accessible")
        if rest == "/merge-upstream" and method == "POST":
            _git("fetch", "-q", self.upstream, "+refs/heads/%s:refs/heads/%s"
                 % (doc["branch"], doc["branch"]), git_dir=repo)
            return 200, {"message": "synced"}
        m = re.match(r"^/git/ref/heads/(.+)$", rest)
        if m and method == "GET":
            return 200, {"object": {"sha": _git("rev-parse", "refs/heads/" + m.group(1),
                                                git_dir=repo)}}
        m = re.match(r"^/git/commits/([0-9a-f]+)$", rest)
        if m and method == "GET":
            return 200, {"tree": {"sha": _git("rev-parse", m.group(1) + "^{tree}",
                                              git_dir=repo)}}
        if rest == "/git/blobs" and method == "POST":
            data = base64.b64decode(doc["content"])
            return 201, {"sha": _git("hash-object", "-w", "--stdin", git_dir=repo,
                                     data=data)}
        if rest == "/git/trees" and method == "POST":
            return 201, {"sha": self._tree(repo, doc)}
        if rest == "/git/commits" and method == "POST":
            args = ["commit-tree", doc["tree"], "-m", doc["message"]]
            for parent in doc.get("parents") or []:
                args += ["-p", parent]
            return 201, {"sha": _git(*args, git_dir=repo)}
        if rest == "/git/refs" and method == "POST":
            _git("update-ref", doc["ref"], doc["sha"], git_dir=repo)
            return 201, {"ref": doc["ref"]}
        if rest == "/pulls" and method == "POST" and full == REPO:
            head_login, _sep, branch = doc["head"].partition(":")
            number = len(self.pulls) + 1
            self.pulls[number] = {"number": number, "author": login,
                                  "head_login": head_login, "branch": branch,
                                  "title": doc["title"], "body": doc["body"],
                                  "state": "open"}
            return 201, {"number": number,
                         "html_url": "https://github.invalid/%s/pull/%d" % (REPO, number)}
        raise _Http(404, "Not Found")

    def _tree(self, repo: str, doc: dict) -> str:
        handle, index = tempfile.mkstemp(prefix="fake_index_")
        os.close(handle)
        os.remove(index)
        env = {"GIT_INDEX_FILE": index}
        try:
            if doc.get("base_tree"):
                _git("read-tree", doc["base_tree"], git_dir=repo, env=env)
            for item in doc["tree"]:
                _git("update-index", "--add", "--cacheinfo",
                     "%s,%s,%s" % (item["mode"], item["sha"], item["path"]),
                     git_dir=repo, env=env)
            return _git("write-tree", git_dir=repo, env=env)
        finally:
            if os.path.exists(index):
                os.remove(index)

    # ── the library's side ─────────────────────────────────────────────
    def _fetch_pull(self, number: int, into: str) -> str:
        pull = self.pulls[number]
        fork = os.path.join(self.root, "forks", pull["head_login"] + ".git")
        _git("fetch", "-q", fork, "+refs/heads/%s:refs/pull/%d/head"
             % (pull["branch"], number), git_dir=into)
        return "refs/pull/%d/head" % number

    def _export(self, ref: str, folder: str) -> None:
        os.makedirs(folder, exist_ok=True)
        archive = subprocess.run(["git", "--git-dir", self.upstream, "archive", ref],
                                 capture_output=True, check=True,
                                 env=dict(os.environ, **_GIT_ENV)).stdout
        subprocess.run(["tar", "-x", "-C", folder], input=archive, check=True)

    def run_checks(self, number: int) -> dict:
        """The pull-request workflow (``check.yml``) on pull ``number``."""
        from patch_library import checks
        ref = self._fetch_pull(number, self.upstream)
        work = tempfile.mkdtemp(prefix="fake_pr_")
        try:
            head, base = os.path.join(work, "head"), os.path.join(work, "base")
            self._export(ref, head)
            self._export("main", base)
            changed = _git("diff", "--name-only", "main..." + ref,
                           git_dir=self.upstream).splitlines()
            return checks.check_pull(head, base, changed, self.pulls[number]["author"])
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def merge(self, number: int) -> None:
        """Merge pull ``number``, rebuild the index (``index.yml``), push,
        and refresh what the raw URLs serve."""
        from patch_library import index
        ref = self._fetch_pull(number, os.path.join(self.served, ".git"))
        _git("merge", "-q", "--no-ff", "-m", "Merge pull request #%d" % number, ref,
             cwd=self.served)
        index.rebuild(self.served)
        _git("add", "-A", "index", cwd=self.served)
        if _git("status", "--porcelain", cwd=self.served):
            _git("commit", "-q", "-m", "Rebuild the index", cwd=self.served)
        _git("push", "-q", "origin", "main", cwd=self.served)
        self.pulls[number]["state"] = "merged"


class _Http(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message
