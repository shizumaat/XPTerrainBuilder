"""GITHUB FOR "PUBLISH PATCH" (#1699 phase 2): device sign-in and the
REST calls of a publish.  Downloading never comes here.

SIGN-IN is GitHub's device flow: the app asks for a code
(:func:`device_start`), shows it with ``github.com/login/device``, and
polls (:func:`device_poll`) until the user has entered it — the app never
sees a password and holds no secret of its own (only the OAuth app's
public client id, ``config``).  The token is kept in the app's secure
credential store beside the data-provider sign-ins
(``O4_Authenticated_Sessions``; the Mac app's Keychain through the
secret broker).

A PUBLISH needs no git on the user's machine: the fork, the branch and
the commit are made through the REST API (git data: blobs, a tree over
the fork's branch head, a commit, a ref), then the pull request is
opened on the library.  :data:`TRANSPORT`, when set, replaces the HTTP
layer — the tests' and the gate's fake GitHub; nothing here calls the
network in a test.
"""
from __future__ import annotations

import base64
import json
import time
import typing as _t
import urllib.error
import urllib.parse
import urllib.request

from . import LibraryRefused
from . import config as _config

__all__ = ["SESSION", "SCOPE", "TRANSPORT", "device_start",
           "device_poll", "stored_token", "store_token", "forget_token", "Client"]

#: The credential-store session the token is kept under.
SESSION = "github_library"

#: What the token may do: fork and open pull requests on public repositories.
SCOPE = "public_repo"

#: ``(method, url, headers, body) -> (status, body bytes)`` replacing the
#: HTTP layer when set (tests, the gate).
TRANSPORT: _t.Callable | None = None

_TIMEOUT_S = 60


def _urllib(method: str, url: str, headers: dict, body: bytes | None) -> tuple:
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except (urllib.error.URLError, OSError) as error:
        raise LibraryRefused("GitHub cannot be reached (%s)"
                          % getattr(error, "reason", error)) from error


def _send(method: str, url: str, *, token: str | None = None, doc=None,
         form: dict | None = None) -> tuple:
    """``(status, parsed JSON or None)`` of one call."""
    headers = {"Accept": "application/json", "User-Agent": "XPTerrainBuilder"}
    body = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if doc is not None:
        body = json.dumps(doc).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif form is not None:
        body = urllib.parse.urlencode(form).encode("ascii")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    status, data = (TRANSPORT or _urllib)(method, url, headers, body)
    try:
        parsed = json.loads(data.decode("utf-8")) if data else None
    except ValueError:
        parsed = None
    return status, parsed


def device_start() -> dict:
    """ENGINE COMMAND ``library_signin_start``: ``{"user_code",
    "verification_uri", "device_code", "interval", "expires_in"}``."""
    s = _config.settings()
    if not _config.configured(publishing=True):
        raise LibraryRefused("Publishing is not set up in this app yet")
    status, doc = _send("POST", s["oauth_base"] + "/login/device/code",
                       form={"client_id": s["client_id"], "scope": SCOPE})
    if status != 200 or not isinstance(doc, dict) or "device_code" not in doc:
        raise LibraryRefused("GitHub did not start the sign-in (%s)" % status)
    return {k: doc.get(k) for k in ("user_code", "verification_uri", "device_code",
                                    "interval", "expires_in")}


def device_poll(device_code: str) -> dict:
    """ENGINE COMMAND ``library_signin_poll``: ``{"status": "ok" | "pending"
    | "slow_down" | "expired" | "denied", "login"}`` — on ``ok`` the token
    is stored and the login named."""
    s = _config.settings()
    status, doc = _send("POST", s["oauth_base"] + "/login/oauth/access_token",
                       form={"client_id": s["client_id"], "device_code": device_code,
                             "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
    doc = doc if isinstance(doc, dict) else {}
    if doc.get("access_token"):
        store_token(doc["access_token"])
        return {"status": "ok", "login": Client(doc["access_token"]).login()}
    error = doc.get("error", "")
    return {"status": {"authorization_pending": "pending", "slow_down": "slow_down",
                       "expired_token": "expired", "access_denied": "denied"}.get(
                           error, "denied" if status >= 400 else "pending"),
            "login": ""}


def stored_token() -> str | None:
    """The stored GitHub token, or ``None``."""
    import O4_Authenticated_Sessions as AUTH
    return AUTH.load_api_key(SESSION)


def store_token(token: str) -> None:
    import O4_Authenticated_Sessions as AUTH
    AUTH.store_api_key(SESSION, token)


def forget_token() -> dict:
    """ENGINE COMMAND ``library_signout``."""
    import O4_Authenticated_Sessions as AUTH
    AUTH.delete_api_key(SESSION)
    return {"signed_in": False}


class Client:
    """The REST calls of one publish, as the signed-in user."""

    def __init__(self, token: str):
        self.token = token
        self.api = _config.settings()["api_base"]

    def _call(self, method: str, path: str, doc=None, ok=(200, 201)) -> dict:
        status, parsed = _send(method, self.api + path, token=self.token, doc=doc)
        if status not in ok:
            message = (parsed or {}).get("message", "") if isinstance(parsed, dict) else ""
            if status == 401:
                raise LibraryRefused("Your GitHub sign-in has expired; sign in again")
            raise LibraryRefused("GitHub refused %s %s (%d%s)" % (
                method, path, status, ": " + message if message else ""))
        return parsed if isinstance(parsed, dict) else {}

    def login(self) -> str:
        return str(self._call("GET", "/user").get("login", ""))

    def fork(self, repo: str, login: str) -> str:
        """The user's fork of ``repo`` (made when absent), as ``owner/name``."""
        name = repo.split("/", 1)[1]
        status, _doc = _send("GET", "%s/repos/%s/%s" % (self.api, login, name),
                            token=self.token)
        if status != 200:
            self._call("POST", "/repos/%s/forks" % repo, {}, ok=(200, 202))
            for _attempt in range(30):              # GitHub forks asynchronously
                status, _doc = _send("GET", "%s/repos/%s/%s" % (self.api, login, name),
                                    token=self.token)
                if status == 200:
                    break
                time.sleep(2)
            else:
                raise LibraryRefused("GitHub did not finish making your fork")
        return "%s/%s" % (login, name)

    def sync(self, fork: str, branch: str) -> None:
        """Bring the fork's ``branch`` up to the library's."""
        self._call("POST", "/repos/%s/merge-upstream" % fork, {"branch": branch},
                   ok=(200, 409))

    def head(self, repo: str, branch: str) -> tuple:
        """``(commit sha, tree sha)`` of ``repo``'s ``branch``."""
        ref = self._call("GET", "/repos/%s/git/ref/heads/%s" % (repo, branch))
        commit = ref["object"]["sha"]
        tree = self._call("GET", "/repos/%s/git/commits/%s" % (repo, commit))["tree"]["sha"]
        return commit, tree

    def commit_files(self, repo: str, branch: str, base_branch: str,
                     files: dict, message: str) -> str:
        """Commit ``files`` (``{path: bytes}``) onto ``base_branch``'s head
        as the new ``branch`` of ``repo``; returns the commit sha."""
        parent, base_tree = self.head(repo, base_branch)
        items = []
        for path, data in sorted(files.items()):
            blob = self._call("POST", "/repos/%s/git/blobs" % repo, {
                "content": base64.b64encode(data).decode("ascii"),
                "encoding": "base64"})
            items.append({"path": path, "mode": "100644", "type": "blob",
                          "sha": blob["sha"]})
        tree = self._call("POST", "/repos/%s/git/trees" % repo,
                          {"base_tree": base_tree, "tree": items})["sha"]
        commit = self._call("POST", "/repos/%s/git/commits" % repo,
                            {"message": message, "tree": tree, "parents": [parent]})["sha"]
        self._call("POST", "/repos/%s/git/refs" % repo,
                   {"ref": "refs/heads/" + branch, "sha": commit})
        return commit

    def pull(self, repo: str, head: str, base: str, title: str, body: str) -> dict:
        """Open the pull request; ``{"number", "html_url"}``."""
        doc = self._call("POST", "/repos/%s/pulls" % repo,
                         {"title": title, "head": head, "base": base, "body": body})
        return {"number": doc.get("number"), "html_url": doc.get("html_url", "")}
