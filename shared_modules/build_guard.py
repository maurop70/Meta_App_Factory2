"""
panel/build_guard.py — ClaudeAY panel, Phase 5b: the sanctioned-build choke.
═════════════════════════════════════════════════════════════════════════════
There is no single write-function every app-build calls — factory, Scribe, Designer,
the Docker writer, and skill registration all write the app tree across modules. So the
choke is not a function; it is a SANCTIONED SESSION. A `sys.addaudithook` refuses any
filesystem write whose RESOLVED path lands under a protected app root when no sanctioned
session is active. Every writer — current or future, any module, any variable name — is
caught by WHERE THE WRITE LANDS. Door four fails by construction, not by remembering to
route through a helper.

REQUIREMENT 1 — judge by resolved path, both directions:
  • a write dressed to look INSIDE the app tree (via `..` or a symlink) that RESOLVES
    OUTSIDE it is refused (escape);
  • a write dressed to look OUTSIDE that RESOLVES INSIDE is caught (it's an app write).
  Resolve first (realpath: symlinks + `..`), then decide. Same class as the Phase-1
  symlink-escape open item — closed here for the app tree.

SEAM 2 — select + taint sit on SESSION ENTRY (below). A build session opens ONLY on a
positive, plan-bound human Selection for its roots, verified by a registered verifier
(set_selection_verifier). This is the choke every build crosses — the same reasoning that
made the write-guard a session and not a function: gate the act every build must cross,
not a named door beside it.

C4 DEPLOYMENT INVARIANT (declared, not buried; canonical in DEPLOYMENT REQUIREMENTS D2):
if NO verifier is registered, session entry REFUSES (fail-closed). An unarmed lock means
builds do not proceed — never that they run unguarded. Consequence: any build path
(factory.create_app via /api/build/direct, forge_orchestrator.merge_to_live, and any
future caller) must load the panel select module (which registers the verifier) and hold
a Selection before scaffolding. This module holds the seam + the guard; no executor path.
"""
from __future__ import annotations

import functools
import os
import sys
import threading

_protected: set[str] = set()          # app roots that require a sanctioned session to write
_local = threading.local()            # per-thread session stack + re-entry flag
_installed = False
_selection_verifier = None            # seam 2: set by the panel; UNSET → session entry refuses


class ScaffoldBypass(Exception):
    """A write into the protected app tree from outside a sanctioned session, or an
    escape out of the session's app tree. Fail-closed: the write does not happen."""


class SelectionRequired(Exception):
    """A build session was opened without a positive, plan-bound human Selection for its
    roots (or with no verifier registered at all). Fail-closed: the session does not open,
    so no scaffolding happens. This is 'propose ≠ select' enforced on the choke."""


def set_selection_verifier(fn) -> None:
    """Arm the choke: register the human-select verifier `fn(roots) -> bool` that session
    entry consults. Loading the panel calls this. While UNSET, every app-root session
    entry refuses (the C4 fail-closed invariant)."""
    global _selection_verifier
    _selection_verifier = fn


def _norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(p))


def _resolved(p: str) -> str:
    return os.path.normcase(os.path.realpath(p))     # symlinks + `..`


def _under(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except Exception:
        return False


def _raw_abs(path) -> str:
    """Absolute form WITHOUT resolving symlinks or collapsing `..` — preserves an app-root
    prefix even when the path escapes via `..` (so the escape is detectable)."""
    s = os.fspath(path)
    if not os.path.isabs(s):
        s = os.path.join(os.getcwd(), s)
    return os.path.normcase(s)


def protect(app_root: str) -> str:
    """Register an app-scaffold root: writes resolving under it require a sanctioned
    session. Persistent and fail-closed — once known, it stays protected."""
    r = _resolved(app_root)
    _protected.add(r)
    _ensure_hook()
    return r


def _active() -> list[str]:
    out = []
    for entry in (getattr(_local, "stack", []) or []):
        out.extend(entry)
    return out


class sanctioned_session:
    """Context manager: within it, writes resolving under ANY of `app_dirs` are allowed;
    those roots are protected so writes to them from OUTSIDE any session are refused. A
    build writes more than one root (app_dir + repo/skills/<app>), so a session declares
    all of them. Entering is the one act every build must cross — where seam 2's
    select+taint will gate."""
    def __init__(self, *app_dirs: str):
        self.roots = [_resolved(d) for d in app_dirs if d]

    def __enter__(self):
        # SEAM 2 — propose ≠ select, on the one act every build crosses. A session over
        # app roots opens ONLY on a verified positive human Selection for those roots.
        # Fail-closed (C4/D2): unregistered verifier OR no matching Selection → REFUSE.
        # Silence refuses here by ABSENCE — a proposal never selected mints no Selection,
        # so verify_and_consume finds nothing. The fold refuses here too — a proposal's
        # own 'selected' flag is never consulted; only the Selection store is.
        if self.roots:
            v = _selection_verifier
            if v is None:
                raise SelectionRequired(
                    "no Selection verifier registered — sanctioned build session refused "
                    "(load the panel select module to arm the choke)")
            if not v(self.roots):
                raise SelectionRequired(
                    f"no positive human Selection for these roots — session refused "
                    f"(propose ≠ select): {self.roots}")
        for r in self.roots:
            _protected.add(r)
        stack = getattr(_local, "stack", None)
        if stack is None:
            stack = []; _local.stack = stack
        stack.append(list(self.roots))
        _ensure_hook()
        return self

    def __exit__(self, *exc):
        try:
            _local.stack.pop()
        except Exception:
            pass
        return False


def sanctioned_build(roots_fn):
    """Decorator: wrap a build entry point so its whole body runs inside a sanctioned
    session for the roots it writes. roots_fn(self, *a, **kw) -> str | list[str]."""
    def deco(fn):
        @functools.wraps(fn)
        def wrap(self, *a, **kw):
            roots = roots_fn(self, *a, **kw)
            if isinstance(roots, str):
                roots = [roots]
            with sanctioned_session(*roots):
                return fn(self, *a, **kw)
        return wrap
    return deco


_capture = None                               # discovery mode: a list collecting write paths


class capturing:
    """DISCOVERY mode — collect every write path during a build (log-only, no refusal), so
    the build itself reveals its app-output roots. Use to find roots empirically, never to
    hand-list them (a hand-list is complete only until the writer you forgot)."""
    def __enter__(self):
        global _capture
        _capture = []
        _ensure_hook()
        return _capture

    def __exit__(self, *exc):
        global _capture
        _capture = None
        return False


def _guard(path) -> None:
    if getattr(_local, "busy", False):        # re-entry guard: our own stat calls, etc.
        return
    if not isinstance(path, (str, bytes, os.PathLike)):
        return                                # a file-descriptor int / non-path event arg
    _local.busy = True
    try:
        if _capture is not None:              # discovery: record every write, never refuse
            _capture.append(_resolved(os.fspath(path)))
            return
        if not _protected:
            return
        raw = _raw_abs(path)
        res = _resolved(os.fspath(path))
        active = _active()
        for root in _protected:
            res_in = _under(res, root)
            # Direction 2 / normal: RESOLVES inside a protected app root -> needs a session.
            if res_in and not any(_under(res, a) for a in active):
                raise ScaffoldBypass(
                    f"write into protected app tree with NO sanctioned session: resolves to "
                    f"{res} (under {root})")
            # Direction 1 / escape: CLAIMS the app root (raw prefix, incl. via `..`/symlink)
            # but RESOLVES outside it -> escape from the sanctioned tree.
            if (root in active or _under(raw, root)) and _under(raw, root) and not res_in:
                raise ScaffoldBypass(
                    f"escape from sanctioned app tree: path claims {root} but resolves to {res}")
    finally:
        _local.busy = False


def _audit(event: str, args) -> None:
    if event == "open":
        if len(args) < 2:
            return
        mode = args[1]
        is_write = (isinstance(mode, str) and any(c in mode for c in "wax+")) or \
                   (isinstance(mode, int) and (mode & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND)))
        if not is_write:
            return
        _guard(args[0])
    elif event == "os.mkdir":                 # a CREATE (scaffolding); deletes are not guarded
        if args:
            _guard(args[0])
    elif event in ("os.rename", "os.replace", "os.link", "os.symlink"):
        # guard the DESTINATION (arg[1]) — that's what gets written
        if len(args) > 1:
            _guard(args[1])


def _ensure_hook() -> None:
    global _installed
    if not _installed:
        sys.addaudithook(_audit)
        _installed = True
