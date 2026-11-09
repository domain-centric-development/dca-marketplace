"""The claim one worker holds on a checkout: a file created exclusively in the git directory, renewed before every stage, stale when its holder stopped renewing it — and the listener's mark beside it."""

from __future__ import annotations

import contextlib
import json
import os
import socket
import typing
from datetime import datetime, timezone
from .....sharedkernel.adapter.outgoing.profile.profile_files import factory_home, in_worktree
from ..git.repository import git
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ..tools.streams import current_session
from ....application.status.texts import parse_time
from ..files.run_marks import stale_after


def claim_path(cwd: str) -> str:
    # One claim per main checkout: a stage in a story's worktree renews the runner's claim there, not one of its own.
    if in_worktree(cwd):
        cwd = typing.cast(str, factory_home())
    code, git_dir = git(cwd, "rev-parse", "--git-dir")
    if code == 0 and git_dir:
        return os.path.join(cwd, git_dir, "dca-factory-worker.lock")
    return os.path.join(cwd, ".agents", "factory", "worker.lock")


def session_owner() -> str:
    kind, session_id = current_session()
    return f"{kind}:{session_id}" if session_id else ""


def read_claim(path: str) -> typing.Optional[typing.Dict[str, typing.Any]]:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def write_claim(path: str, owner: str, since: typing.Optional[str]) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    temporary = f"{path}.{os.getpid()}"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump({"owner": owner, "since": since or stamp, "beat": stamp}, handle)
    os.replace(temporary, path)


def dead_runner(owner: typing.Any) -> typing.Optional[int]:
    """The pid of a runner's claim (`runner:<host>:<pid>`) on this host whose process no longer runs — the claim is
    then stale whatever its beat says: a killed runner leaves its claim, and nothing would free it for two hours. None
    for another host, another kind of owner, or a process that still runs (or cannot be asked: Windows, where a
    signal 0 would end the process, is never asked)."""
    parts = str(owner or "").split(":")
    if len(parts) != 3 or parts[0] != "runner" or not parts[2].isdigit() or os.name == "nt":
        return None
    if parts[1] != (socket.gethostname() or "host"):
        return None
    pid = int(parts[2])
    if pid <= 0 or pid == os.getpid():
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return pid
    except (PermissionError, OSError):
        return None
    return None


def claim(cwd: str, owner: str, say: typing.Callable[..., typing.Any] = print) -> int:
    """0 when `owner` holds the checkout now (claimed, renewed or taken over), 3 when another does; `say` gets
    the line that tells which."""
    path = claim_path(cwd)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Written aside, then linked into place: a link fails when the claim exists, so the file appears
    # with its content or not at all — an empty claim between create and write would read as unreadable.
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    temporary = f"{path}.{os.getpid()}.new"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump({"owner": owner, "since": stamp, "beat": stamp}, handle)
    try:
        os.link(temporary, path)
        say(f"claim: {owner} holds the checkout")
        return 0
    except FileExistsError:
        pass
    except OSError:                              # a file system without hard links
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(read_text(temporary))
            say(f"claim: {owner} holds the checkout")
            return 0
        except FileExistsError:
            pass
    finally:
        with contextlib.suppress(OSError):
            os.remove(temporary)
    held = read_claim(path) or {}
    if held.get("owner") == owner:
        write_claim(path, owner, held.get("since"))
        return 0
    beat = parse_time(held.get("beat"))
    if beat is None:                             # unreadable: aged by the file, not taken on sight
        with contextlib.suppress(OSError):
            beat = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc)
    age = (datetime.now(timezone.utc) - beat).total_seconds() if beat else None
    gone = dead_runner(held.get("owner"))
    if gone:
        write_claim(path, owner, None)
        say(f"claim: took over from {held.get('owner')} — its process {gone} no longer runs on this host, so it was "
            f"stopped or crashed")
        return 0
    if age is None or age > stale_after():
        write_claim(path, owner, None)
        say(f"claim: took over from {held.get('owner', 'an unreadable claim')} — no sign of life for "
              f"{int(age // 60) if age is not None else '?'} min, so it was stopped or crashed")
        return 0
    say(f"claim: the checkout is held by {held.get('owner')} since {held.get('since')} (last sign of life "
          f"{int(age // 60)} min ago) — one worker per checkout; this one does not start")
    return 3


# A session that listens on the backlog (`/loop /factory-run`) holds no claim while nothing is ready,
# so from outside a waiting listener and an ended one look the same. Each look leaves a mark next to
# the claim — who looked, and when — which `--status` shows. It only informs; it locks nothing.
def listener_path(cwd: str) -> str:
    return claim_path(cwd).replace("dca-factory-worker.lock", "dca-factory-listener.json") \
        if claim_path(cwd).endswith("dca-factory-worker.lock") else \
        os.path.join(cwd, ".agents", "factory", "listener.json")


def listen_stale_after() -> int:
    try:
        return max(60, int(os.environ.get("FACTORY_LISTEN_STALE", "3600")))
    except ValueError:
        return 3600


def mark_listening(cwd: str) -> int:
    owner = session_owner() or "a session without an id"
    path = listener_path(cwd)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_claim(path, owner, None)
    print(f"listening: {owner} looked at the backlog")
    return 0


def listener_line(cwd: str) -> typing.Optional[str]:
    """`listening: …` for the status, or None when no session has looked."""
    held = read_claim(listener_path(cwd))
    if not held:
        return None
    beat = parse_time(held.get("beat"))
    if not beat:
        return None
    minutes = int((datetime.now(timezone.utc) - beat).total_seconds() // 60)
    ended = minutes * 60 > listen_stale_after()
    return (f"listening: {held.get('owner')}, last look {minutes} min ago"
            + (" — no look for longer than a loop waits, probably ended" if ended else ""))


def release(cwd: str, owner: str) -> int:
    path = claim_path(cwd)
    held = read_claim(path)
    if held and held.get("owner") == owner:
        os.remove(path)
        print(f"claim: {owner} released the checkout")
    return 0
