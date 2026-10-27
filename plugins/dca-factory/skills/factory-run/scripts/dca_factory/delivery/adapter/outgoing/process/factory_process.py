"""The factory as a process of its own (WP-91): `up` starts it in the background, `down` ends it between stages, and
the page `serve` shows is started beside it — what a person sees of it is the worker: who holds the checkout, since
when, whether it lives, whether it ended on its own.

    up      `factory.sh run --watch --stay` detached, its pid and log beside the run folder (`factory.json`,
            `factory.log`); a factory that is up already — started here, in a terminal or from a session — is named,
            and nothing starts
    down    the stop file and a TERM: the factory ends after its running stage (`--now`: an interrupt, which stops
            the running stage too); it waits until the claim is given back
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import place
from ..stack.commands import posix_shell
from ....application.status.texts import parse_time
from ..claims.checkout_claim import claim_path, dead_runner, read_claim
from ..files.run_marks import running_stages, stale_after
from ..files.request_files import default_by, factory_dir, stamp_utc

#: What the worker, the page or an ended factory is, as its file and the claim say it.
Info = typing.Dict[str, typing.Any]


FACTORY_FILE = "factory.json"       # the factory `up` started: pid, start, log, who
SERVE_FILE = "serve.json"           # the page `serve` runs: pid, port, url with its token
LOG_FILE = "factory.log"
LOG_LIMIT = 5 * 1024 * 1024         # past it, `up` keeps the log as `factory.log.1` and begins a new one
STOP_MARK = "down"                  # the first word of a stop file `down` wrote — `down` removes its own alone
SESSION_VARIABLES = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT", "CODEX_SESSION_ID",
                     "CODEX_THREAD_ID")


def say(text: str) -> None:
    print(f"factory: {text}", flush=True)


def scripts_dir() -> str:
    """The folder of the pipeline's entry points — the package's parent."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))


def cli_path() -> str:
    return os.path.join(scripts_dir(), "factory-cli.py")


def runner_path() -> str:
    return os.path.join(scripts_dir(), "factory.sh")


def own_file(name: str) -> str:
    return os.path.join(factory_dir(), name)


def read_json(path: str) -> typing.Any:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def write_json(path: str, data: typing.Any, private: bool = False) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temporary = f"{path}.{os.getpid()}.tmp"
    descriptor = os.open(temporary, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600 if private else 0o644)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(temporary, path)


def alive(pid: typing.Optional[int]) -> bool:
    """Whether a process of this host runs — never asked with a signal on Windows, where it would end it."""
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        found = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in found.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def owner_pid(owner: typing.Optional[str]) -> typing.Optional[int]:
    """The pid of a runner's claim on this host (`runner:<host>:<pid>`), else None."""
    parts = str(owner or "").split(":")
    if len(parts) == 3 and parts[0] == "runner" and parts[2].isdigit() and parts[1] == (socket.gethostname() or "host"):
        return int(parts[2])
    return None


def stop_file() -> str:
    return os.path.join(factory_dir(), "stop")


# --- the worker -------------------------------------------------------------------------------------------------------
def worker(cwd: str) -> typing.Optional[Info]:
    """Who holds the checkout, as every view shows it: {owner, since, beat, how, pid, alive, log, stopping} — `how`
    is `up` (started by `factory.sh up`), `runner` (a runner started in a terminal or by a view) or `session` (a
    session's own run). None when nobody holds it."""
    held = read_claim(claim_path(cwd))
    if not held or not held.get("owner"):
        return None
    owner = held["owner"]
    pid = owner_pid(owner)
    started = read_json(own_file(FACTORY_FILE)) or {}
    beat = parse_time(held.get("beat"))
    age = (time.time() - beat.timestamp()) if beat else None
    living = not dead_runner(owner) and (age is None or age <= stale_after())
    how = "up" if pid and started.get("pid") == pid else "runner" if owner.startswith("runner:") else "session"
    return dict(owner=owner, since=held.get("since"), beat=held.get("beat"), how=how, pid=pid, alive=living,
                log=started.get("log", "") if how == "up" else "", by=started.get("by", "") if how == "up" else "",
                stopping=os.path.isfile(stop_file()))


def ended(cwd: str) -> typing.Optional[Info]:
    """The factory `up` started that is gone without a `down` — {at, why, log}: its start and the last thing its log
    says since then (a refusal, a crash); None while it runs, after a `down` or a stop request (the stop file stays),
    or where nobody started one."""
    started = read_json(own_file(FACTORY_FILE)) or {}
    if not started.get("pid") or alive(started["pid"]) or os.path.isfile(stop_file()) or (worker(cwd) or {}).get("alive"):
        return None
    lines = [line.rstrip() for line in log_tail(started.get("log") or own_file(LOG_FILE), 200)]
    heads = [i for i, line in enumerate(lines) if line.startswith("== ")]
    said: typing.List[str] = []                                       # its messages since its start, a continued line joined to its own
    for line in lines[heads[-1] + 1 if heads else 0:]:
        text = line.split(":", 1)[1].strip() if line.startswith("factory:") else line.strip()
        if line.startswith("factory:   ") and said:
            said[-1] += " " + text
        elif text:
            said.append(text)
    return dict(at=started.get("started", ""), why=said[-1] if said else "no word in its log", log=started.get("log", ""))


def worker_line(info: typing.Optional[Info]) -> str:
    if not info:
        return "factory: down — nobody holds the checkout (`factory.sh up` starts it)"
    how = {"up": "started by `factory.sh up`", "runner": "a runner", "session": "a session's run"}[info["how"]]
    state = "" if info["alive"] else " — no sign of life, probably ended"
    stopping = " — stopping after its stage" if info["stopping"] and info["alive"] else ""
    return f"factory: up — {info['owner']} since {info['since']} ({how}){state}{stopping}"


# --- up ------------------------------------------------------------------------------------------------------------------
def session_free_env() -> typing.Dict[str, str]:
    """The environment of a factory started in the background: none of the session it may have been started from —
    it is a process of its own, and a tool started under a session's variables takes itself for nested."""
    env = {k: v for k, v in os.environ.items() if k not in SESSION_VARIABLES and k != "FACTORY_HOME"}
    env["FACTORY_UP"] = "1"
    return env


def detached(argv: typing.List[str], cwd: str, log: typing.IO[str],
             env: typing.Dict[str, str]) -> "subprocess.Popen[bytes]":
    """A process that outlives this one: a session of its own (POSIX) or a new process group (Windows)."""
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        return subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                creationflags=flags)
    return subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)


def log_tail(path: str, lines: int = 20) -> typing.List[str]:
    with contextlib.suppress(OSError):
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.readlines()[-lines:]
    return []


def up(cwd: str, run_args: typing.Sequence[str] = (), serve_too: bool = False, port: typing.Optional[int] = None,
       by: str = "", wait: float = 20.0) -> int:
    """Start the factory in the background; 0 when it holds the checkout (or one was up already)."""
    if not os.path.isfile(os.path.join(cwd, ".agents", "factory", "story-gate.py")):
        say("no pipeline here (.agents/factory/story-gate.py) — `factory.sh setup` installs it; nothing started")
        return 2
    info = worker(cwd)
    if info and info["alive"]:
        print(worker_line(info))
        say("nothing started — one factory per checkout")
        return (start_page(cwd, port) if serve_too else 0)
    if os.path.isfile(stop_file()):
        os.remove(stop_file())
        say(f"{stop_file()} removed — it would have ended the factory before its first story")
    log_path = own_file(LOG_FILE)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with contextlib.suppress(OSError):             # one log per start would scatter it; one forever would grow
        if os.path.getsize(log_path) > LOG_LIMIT:
            os.replace(log_path, log_path + ".1")
    by = by or default_by(cwd)
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"\n== {stamp_utc()} up by {by}: factory.sh run --watch --stay {' '.join(run_args)}\n")
        log.flush()
        # the bash the gate runs profile commands with: on Windows Git Bash, never System32's WSL launcher
        process = detached([posix_shell() or os.environ.get("FACTORY_BASH") or "bash", runner_path(), "run", "--watch",
                            "--stay", *run_args], cwd, log, session_free_env())
    started = stamp_utc()
    record = dict(pid=process.pid, started=started, log=log_path.replace(os.sep, "/"), by=by, args=list(run_args))
    write_json(own_file(FACTORY_FILE), record)
    deadline = time.time() + wait
    while time.time() < deadline:
        held = read_claim(claim_path(cwd)) or {}
        runner = owner_pid(held.get("owner"))
        # the runner's claim: its pid is the one started here — or, where bash's `exec` starts a process of its own
        # (Git Bash), a runner of this host that claimed the checkout since this start
        if runner and (runner == process.pid or str(held.get("since", "")) >= started):
            if runner != process.pid:
                write_json(own_file(FACTORY_FILE), dict(record, pid=runner))
            say(f"up — pid {runner}, its log {log_path}; `factory.sh down` ends it after its running stage")
            return start_page(cwd, port) if serve_too else 0
        code = process.poll()
        if code:                                   # 0: a shell that handed over to its runner, which claims next
            say(f"the factory ended at once (exit {code}) — its log, {log_path}:")
            for line in log_tail(log_path):
                print("  " + line.rstrip())
            if (read_json(own_file(FACTORY_FILE)) or {}).get("pid") == process.pid:   # never another `up`'s record
                with contextlib.suppress(OSError):
                    os.remove(own_file(FACTORY_FILE))
            return code
        time.sleep(0.25)
    say(f"started (pid {process.pid}) but it holds no claim yet — its log: {log_path}")
    return start_page(cwd, port) if serve_too else 0


# --- down ----------------------------------------------------------------------------------------------------------------
def is_runner(pid: int) -> bool:
    """Whether the process is a factory runner — a claim outlives a killed runner, and its pid may be another
    process's by now. Where the system cannot say (Windows), yes."""
    if os.name == "nt":
        return True
    found = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True)
    return found.returncode == 0 and ("factory-cli.py" in found.stdout or "factory.sh" in found.stdout)


def signal_runner(pid: int, now: bool) -> None:
    """TERM ends a runner between stages (and a wait at once); with --now an interrupt to its process group stops the
    running stage too — its tools first, as an interrupt in its terminal would. On Windows a signal ends a process at
    once, so there the stop file alone ends the runner — before its next story, or at once where it waits — and
    `--now` ends it outright."""
    if (os.name == "nt" and not now) or not is_runner(pid):
        return
    with contextlib.suppress(OSError):
        if now and os.name != "nt" and os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGINT)
        else:
            os.kill(pid, signal.SIGINT if now else signal.SIGTERM)


def stop_page() -> None:
    served = running_page(None) or {}                 # alive and answering on its port: not a reused pid
    if served.get("by_up"):
        with contextlib.suppress(OSError):
            os.kill(served["pid"], signal.SIGTERM)
        say(f"the page on port {served.get('port')} ended with the factory")


def down(cwd: str, now: bool = False, wait: bool = True, by: str = "") -> int:
    """End the factory after its running stage; 0 when it is down."""
    info = worker(cwd)
    started = read_json(own_file(FACTORY_FILE)) or {}
    if not info or not info["alive"]:
        if started and not alive(started.get("pid")):
            with contextlib.suppress(OSError):
                os.remove(own_file(FACTORY_FILE))
        if info and not info["alive"]:
            release_dead(cwd, info)
        say("down — nobody holds the checkout")
        stop_page()
        return 0
    if now and not info["pid"]:
        say(f"{info['owner']} is no runner of this host — `--now` cannot stop it; it ends after its stage")
    os.makedirs(factory_dir(), exist_ok=True)
    ours = not os.path.isfile(stop_file())
    if ours:
        with open(stop_file(), "w", encoding="utf-8") as handle:
            handle.write(f"{STOP_MARK} by {by or default_by(cwd)} at {stamp_utc()}\n")
    if info["pid"]:
        signal_runner(info["pid"], now)
    say(f"stopping {info['owner']} — " + ("its running stage is interrupted" if now and info["pid"] else
                                            "after its running stage, nothing more starts"))
    if not wait:
        return 0
    last = time.time()
    try:
        while True:
            held = read_claim(claim_path(cwd)) or {}
            if held.get("owner") != info["owner"] or (info["pid"] and not alive(info["pid"])):
                break
            if time.time() - last >= 30:
                last = time.time()
                stages = ", ".join(f"{story} {stage}" for story, stage, _t in running_stages(place("runs")))
                say("still waiting for the running stage" + (f" — {stages}" if stages else ""))
            time.sleep(1)
    except KeyboardInterrupt:
        say(f"no longer waiting — the factory still ends after its stage ({stop_file()} stays until it did)")
        return 130
    release_dead(cwd, info)
    if ours and os.path.isfile(stop_file()):
        with contextlib.suppress(OSError):
            os.remove(stop_file())
    with contextlib.suppress(OSError):
        if (read_json(own_file(FACTORY_FILE)) or {}).get("pid") in (info["pid"], None) or not alive(started.get("pid")):
            os.remove(own_file(FACTORY_FILE))
    stop_page()
    say("down")
    return 0


def release_dead(cwd: str, info: Info) -> None:
    """A claim whose runner is gone is given back — the claim would free itself, but `down` says it is down."""
    path = claim_path(cwd)
    held = read_claim(path) or {}
    if held.get("owner") == info["owner"] and info["pid"] and not alive(info["pid"]):
        with contextlib.suppress(OSError):
            os.remove(path)


def answers(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def running_page(cwd: typing.Optional[str]) -> typing.Optional[Info]:
    served = read_json(own_file(SERVE_FILE)) or {}
    if served.get("pid") and alive(served["pid"]) and served.get("port") and answers(served["port"]):
        return served
    return None


def start_page(cwd: str, port: typing.Optional[int] = None) -> int:
    """The page started detached (`serve --background`, `up --serve`); a second one in the same checkout names the
    running one."""
    served = running_page(cwd)
    if served:
        say(f"the page runs already — {served['url']}")
        return 0
    os.makedirs(factory_dir(), exist_ok=True)
    log = open(own_file("serve.log"), "a", encoding="utf-8")
    argv = [sys.executable, cli_path(), "--serve", "--by-up"] + (["--port", str(port)] if port else [])
    process = detached(argv, cwd, log, session_free_env())
    log.close()
    deadline = time.time() + 30                       # a loaded machine imports the package slowly; a page that
    while time.time() < deadline:                     # answers ends the wait at once
        served = running_page(cwd)
        if served and served.get("pid") == process.pid:
            say(f"the page: {served['url']}")
            return 0
        if process.poll() is not None:
            say(f"the page did not start (exit {process.returncode}) — {own_file('serve.log')}")
            return 1
        time.sleep(0.2)
    say(f"the page did not answer in time — {own_file('serve.log')}")
    return 1
