"""The factory as a process of its own (WP-91): `up` starts it in the background, `down` ends it between stages, and
`serve` puts a page in front of it — bound to this machine alone, opened with a token of its start.

    up      `factory.sh run --watch --stay` detached, its pid and log beside the run folder (`factory.json`,
            `factory.log`); a factory that is up already — started here, in a terminal or from a session — is named,
            and nothing starts
    down    the stop file and a TERM: the factory ends after its running stage (`--now`: an interrupt, which stops
            the running stage too); it waits until the claim is given back
    serve   one page and a JSON API over the factory's own views; every press writes a request — the page decides
            nothing. 127.0.0.1 only, a random token per start in the URL and on every call, the Host and, for a
            write, the Origin checked: no other web page can read the factory or write to it

The page and the API read through `factory-cli.py`, a process per call, so they show exactly what `factory.sh` shows.
"""

import base64
import contextlib
import hmac
import http.server
import json
import os
import queue
import secrets
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import zlib

from .contract import GateError, place
from .gate import posix_shell
from .state import claim_path, dead_runner, read_claim, running_stages, stale_after
from .reports import parse_time
from .requests import (
    default_by, drop_request, Duplicate, stamp_utc, factory_dir, ID_WORD, KINDS, RequestError, retry_request, write_request)
from .page import FAVICON, PAGE, SCRIPT_HASH


FACTORY_FILE = "factory.json"       # the factory `up` started: pid, start, log, who
SERVE_FILE = "serve.json"           # the page `serve` runs: pid, port, url with its token
LOG_FILE = "factory.log"
LOG_LIMIT = 5 * 1024 * 1024         # past it, `up` keeps the log as `factory.log.1` and begins a new one
STOP_MARK = "down"                  # the first word of a stop file `down` wrote — `down` removes its own alone
SESSION_VARIABLES = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT", "CODEX_SESSION_ID",
                     "CODEX_THREAD_ID")
PORT_BASE, PORT_SPAN = 8700, 200    # where a project's page looks for its port, a stable one per project first


def say(text):
    print(f"factory: {text}", flush=True)


def scripts_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cli_path():
    return os.path.join(scripts_dir(), "factory-cli.py")


def runner_path():
    return os.path.join(scripts_dir(), "factory.sh")


def own_file(name):
    return os.path.join(factory_dir(), name)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def write_json(path, data, private=False):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temporary = f"{path}.{os.getpid()}.tmp"
    descriptor = os.open(temporary, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600 if private else 0o644)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(temporary, path)


def alive(pid):
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


def owner_pid(owner):
    """The pid of a runner's claim on this host (`runner:<host>:<pid>`), else None."""
    parts = str(owner or "").split(":")
    if len(parts) == 3 and parts[0] == "runner" and parts[2].isdigit() and parts[1] == (socket.gethostname() or "host"):
        return int(parts[2])
    return None


def stop_file():
    return os.path.join(factory_dir(), "stop")


# --- the worker -------------------------------------------------------------------------------------------------------
def worker(cwd):
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


def worker_text(info):
    """The worker in a few words, as a view's header shows it."""
    if not info:
        return "down"
    if not info["alive"]:
        return f"{info['how']} — no sign of life"
    if info["stopping"]:
        return "stopping after its stage"
    return {"up": "up", "runner": "up — a runner from a terminal", "session": "up — a session's run"}[info["how"]]


def ended(cwd):
    """The factory `up` started that is gone without a `down` — {at, why, log}: its start and the last thing its log
    says since then (a refusal, a crash); None while it runs, after a `down` or a stop request (the stop file stays),
    or where nobody started one."""
    started = read_json(own_file(FACTORY_FILE)) or {}
    if not started.get("pid") or alive(started["pid"]) or os.path.isfile(stop_file()) or (worker(cwd) or {}).get("alive"):
        return None
    lines = [line.rstrip() for line in log_tail(started.get("log") or own_file(LOG_FILE), 200)]
    heads = [i for i, line in enumerate(lines) if line.startswith("== ")]
    said = []                                       # its messages since its start, a continued line joined to its own
    for line in lines[heads[-1] + 1 if heads else 0:]:
        text = line.split(":", 1)[1].strip() if line.startswith("factory:") else line.strip()
        if line.startswith("factory:   ") and said:
            said[-1] += " " + text
        elif text:
            said.append(text)
    return dict(at=started.get("started", ""), why=said[-1] if said else "no word in its log", log=started.get("log", ""))


def worker_line(info):
    if not info:
        return "factory: down — nobody holds the checkout (`factory.sh up` starts it)"
    how = {"up": "started by `factory.sh up`", "runner": "a runner", "session": "a session's run"}[info["how"]]
    state = "" if info["alive"] else " — no sign of life, probably ended"
    stopping = " — stopping after its stage" if info["stopping"] and info["alive"] else ""
    return f"factory: up — {info['owner']} since {info['since']} ({how}){state}{stopping}"


# --- up ------------------------------------------------------------------------------------------------------------------
def session_free_env():
    """The environment of a factory started in the background: none of the session it may have been started from —
    it is a process of its own, and a tool started under a session's variables takes itself for nested."""
    env = {k: v for k, v in os.environ.items() if k not in SESSION_VARIABLES and k != "FACTORY_HOME"}
    env["FACTORY_UP"] = "1"
    return env


def detached(argv, cwd, log, env):
    """A process that outlives this one: a session of its own (POSIX) or a new process group (Windows)."""
    kwargs = dict(cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(argv, **kwargs)


def log_tail(path, lines=20):
    with contextlib.suppress(OSError):
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.readlines()[-lines:]
    return []


def up(cwd, run_args=(), serve_too=False, port=None, by="", wait=20.0):
    """Start the factory in the background; 0 when it holds the checkout (or one was up already)."""
    if not os.path.isfile(os.path.join(cwd, ".agents", "factory", "story-gate.py")):
        say("no pipeline here (.agents/factory/story-gate.py) — `factory.sh setup` installs it; nothing started")
        return 2
    info = worker(cwd)
    if info and info["alive"]:
        print(worker_line(info))
        say("nothing started — one factory per checkout")
        return (serve(cwd, port, background=True) if serve_too else 0)
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
            return serve(cwd, port, background=True) if serve_too else 0
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
    return serve(cwd, port, background=True) if serve_too else 0


# --- down ----------------------------------------------------------------------------------------------------------------
def is_runner(pid):
    """Whether the process is a factory runner — a claim outlives a killed runner, and its pid may be another
    process's by now. Where the system cannot say (Windows), yes."""
    if os.name == "nt":
        return True
    found = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True)
    return found.returncode == 0 and ("factory-cli.py" in found.stdout or "factory.sh" in found.stdout)


def signal_runner(pid, now):
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


def stop_page():
    served = running_page(None) or {}                 # alive and answering on its port: not a reused pid
    if served.get("by_up"):
        with contextlib.suppress(OSError):
            os.kill(served["pid"], signal.SIGTERM)
        say(f"the page on port {served.get('port')} ended with the factory")


def down(cwd, now=False, wait=True, by=""):
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


def release_dead(cwd, info):
    """A claim whose runner is gone is given back — the claim would free itself, but `down` says it is down."""
    path = claim_path(cwd)
    held = read_claim(path) or {}
    if held.get("owner") == info["owner"] and info["pid"] and not alive(info["pid"]):
        with contextlib.suppress(OSError):
            os.remove(path)


# --- serve ---------------------------------------------------------------------------------------------------------------
def free_port(cwd, wanted=None):
    """The port the page binds: the one named, else the project's own — stable per checkout, so a bookmark holds —
    and the next free one after it where another factory's page (or anything else) has it."""
    if wanted:
        return wanted if bindable(wanted) else None
    first = PORT_BASE + zlib.crc32(os.path.realpath(cwd).encode("utf-8")) % PORT_SPAN
    for offset in range(PORT_SPAN):
        port = PORT_BASE + (first - PORT_BASE + offset) % PORT_SPAN
        if bindable(port):
            return port
    return None


#: A port the page left a moment ago (TIME_WAIT) is its own again at once, so a bookmark holds across a restart; on
#: Windows the option would let another process bind the same port beside it, so there it stays off.
REUSE_ADDRESS = os.name != "nt"


def bindable(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if REUSE_ADDRESS:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def answers(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def running_page(cwd):
    served = read_json(own_file(SERVE_FILE)) or {}
    if served.get("pid") and alive(served["pid"]) and served.get("port") and answers(served["port"]):
        return served
    return None


def serve(cwd, port=None, background=False, open_browser=False):
    """The page: a second `serve` in the same checkout names the running one; `background` starts it detached (`up
    --serve`), else it runs here until interrupted."""
    served = running_page(cwd)
    if served:
        say(f"the page runs already — {served['url']}")
        return 0
    if background:
        os.makedirs(factory_dir(), exist_ok=True)
        log = open(own_file("serve.log"), "a", encoding="utf-8")
        argv = [sys.executable, cli_path(), "--serve", "--by-up"] + (["--port", str(port)] if port else [])
        process = detached(argv, cwd, log, session_free_env())
        log.close()
        deadline = time.time() + 10
        while time.time() < deadline:
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
    return serve_here(cwd, port, open_browser)


def serve_here(cwd, port=None, open_browser=False, by_up=False):
    chosen = free_port(cwd, port)
    if not chosen:
        say(f"port {port} is taken — name another with --port" if port else
            f"no free port between {PORT_BASE} and {PORT_BASE + PORT_SPAN - 1} — name one with --port")
        return 2
    token = secrets.token_urlsafe(24)
    server = Server(("127.0.0.1", chosen), Handler)
    server.project, server.token, server.port = os.path.realpath(cwd), token, chosen
    url = f"http://127.0.0.1:{chosen}/?t={token}"
    write_json(own_file(SERVE_FILE), dict(pid=os.getpid(), port=chosen, url=url, started=stamp_utc(), by_up=by_up),
               private=True)
    say(f"the page for {os.path.basename(server.project)}: {url}")
    say("bound to 127.0.0.1 alone; the token is this start's — Ctrl-C ends the page, the factory runs on")
    if open_browser:
        import webbrowser
        with contextlib.suppress(Exception):
            webbrowser.open(url)

    def end(_signum, _frame):
        raise KeyboardInterrupt
    with contextlib.suppress(ValueError):
        signal.signal(signal.SIGTERM, end)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.end_followers()
        if (read_json(own_file(SERVE_FILE)) or {}).get("pid") == os.getpid():
            with contextlib.suppress(OSError):
                os.remove(own_file(SERVE_FILE))
    return 0


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = REUSE_ADDRESS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.followers, self.followers_lock = set(), threading.Lock()

    def end_followers(self):
        """The follow processes still streaming — a daemon thread dies with the page and never reaches its own
        `finally`, so the page ends them, or they outlive it."""
        with self.followers_lock:
            followers, self.followers = list(self.followers), set()
        for process in followers:
            with contextlib.suppress(OSError):
                process.terminate()
        for process in followers:
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                process.wait(timeout=5)


#: The views the page may read — fixed argument lists, the one value they take checked to be an id.
VIEWS = {
    "status": lambda q: ["--status", "--format", "json", "--live"],
    "story": lambda q: ["--status", "--story", q["id"], "--format", "json", "--live"],
    "epic": lambda q: ["--status", "--epic", q["id"], "--format", "json"],
    "decisions": lambda q: ["--list-decisions", "--format", "json"],
    "discover": lambda q: ["--discover-list", "--format", "json"],
    "requests": lambda q: ["--requests", "--format", "json"],
    "help": lambda q: ["--help-view", "--format", "json"],
    "spec-delta": lambda q: ["--spec-delta", q["id"], "--format", "json"],
    "output": lambda q: ["--follow", "--once", "--format", "json", "--lines", "400"]
                        + (["--story", q["id"]] if q.get("id") else [])
                        + (["--process", q["process"]] if q.get("process") else [])
                        + (["--request", q["request"]] if q.get("request") else []),
}


#: What a press may write: a request's kind and the fields the page sends; nothing else reaches the files.
REQUEST_FIELDS = ("story", "epic", "record", "topic", "proposal", "option", "from")


def cli_env():
    env = dict(os.environ)
    env.pop("FACTORY_HOME", None)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def run_cli(project, argv, timeout=60):
    try:
        done = subprocess.run([sys.executable, cli_path(), *argv], cwd=project, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout, env=cli_env())
    except subprocess.TimeoutExpired:
        return 124, "", f"factory-cli.py {' '.join(argv)} took longer than {timeout}s"
    return done.returncode, done.stdout, done.stderr


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "dca-factory"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):            # the page polls: its log would be noise
        if os.environ.get("FACTORY_SERVE_LOG"):
            sys.stderr.write("serve: " + (fmt % args) + "\n")

    # --- the checks every call passes ------------------------------------------------------------------------------
    def origins(self):
        return {f"http://127.0.0.1:{self.server.port}", f"http://localhost:{self.server.port}"}

    def host_ok(self):
        """The Host header names this server: a page that rebinds a name of its own to 127.0.0.1 is refused."""
        return self.headers.get("Host", "") in {f"127.0.0.1:{self.server.port}", f"localhost:{self.server.port}"}

    def token_ok(self, query):
        given = self.headers.get("X-Factory-Token") or (query.get("t") or [""])[0]
        return bool(given) and hmac.compare_digest(given.encode("utf-8"), self.server.token.encode("utf-8"))

    def write_ok(self):
        """A write comes from this page alone: its Origin, and where the browser says so, from the same site."""
        if self.headers.get("Origin", "") not in self.origins():
            return False
        site = self.headers.get("Sec-Fetch-Site")
        return site in (None, "same-origin")

    # --- answers ---------------------------------------------------------------------------------------------------
    def common_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")

    def answer(self, code, body, kind="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.common_headers()
        if self.command == "POST" and code >= 400:
            # refused before its body was read: the body would be read as the next request on this connection
            self.send_header("Connection", "close")
        if kind.startswith("text/html"):
            self.send_header("Content-Security-Policy",
                             f"default-src 'none'; script-src '{SCRIPT_HASH}'; style-src 'unsafe-inline'; "
                             "font-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
                             "form-action 'none'; "
                             "frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def json(self, code, value):
        self.answer(code, json.dumps(value, ensure_ascii=False))

    def refuse(self, code, why):
        self.json(code, dict(error=why))

    def guarded(self, query):
        if not self.host_ok():
            self.refuse(403, "this server answers to 127.0.0.1 and localhost alone")
            return False
        if not self.token_ok(query):
            self.refuse(403, "no token, or not this start's — open the URL `factory.sh serve` printed")
            return False
        return True

    # --- GET -------------------------------------------------------------------------------------------------------
    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(url.query)
        # what the page is drawn with — the same for everyone, no project's data in it: no token
        if url.path in ("/favicon.ico", "/favicon.svg"):
            return self.answer(200, FAVICON, "image/svg+xml")
        if url.path.startswith("/fonts/"):
            return self.font(url.path[len("/fonts/"):])
        if not self.guarded(query):
            return None
        if url.path == "/":
            return self.answer(200, PAGE, "text/html; charset=utf-8")
        if url.path == "/api/meta":
            return self.json(200, dict(project=os.path.basename(self.server.project), port=self.server.port,
                                       by=default_by(self.server.project),
                                       kinds=[dict(kind=k.name, keys=list(k.keys), words=k.words, option=k.option,
                                                   about=k.about) for k in KINDS]))
        if url.path.startswith("/api/view/"):
            return self.view(url.path[len("/api/view/"):], query)
        if url.path == "/api/follow":
            return self.follow(query)
        return self.refuse(404, "no such view")

    def font(self, name):
        from .fonts import FONTS                      # read once a page asks: the views never need them
        if name not in FONTS:
            return self.refuse(404, "no such font")
        data = base64.b64decode(FONTS[name])
        self.send_response(200)
        self.send_header("Content-Type", "font/woff2")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=86400")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)
        return None

    def view(self, name, query):
        if name not in VIEWS:
            return self.refuse(404, f"no view {name}")
        values = {k: v[0] for k, v in query.items() if k != "t"}
        for key, value in values.items():
            if not ID_WORD.match(value):
                return self.refuse(400, f"{key}: {value!r} is no id")
        if name in ("story", "epic", "spec-delta") and not values.get("id"):
            return self.refuse(400, f"the {name} view names an id")
        code, out, error = run_cli(self.server.project, VIEWS[name](values))
        start = out.find("{")
        if start < 0:
            return self.json(502, dict(error=(error or out).strip()[-2000:] or f"the view {name} printed nothing",
                                       exit=code))
        try:
            return self.json(200, json.loads(out[start:]))
        except ValueError:
            return self.json(502, dict(error=f"the view {name} printed no JSON", exit=code))

    def follow(self, query):
        """What a stage or a request in flight does, line by line, as server-sent events."""
        values = {k: v[0] for k, v in query.items() if k != "t"}
        for key, value in values.items():
            if not ID_WORD.match(value):
                return self.refuse(400, f"{key}: {value!r} is no id")
        argv = [sys.executable, cli_path(), "--follow"] + (["--story", values["story"]] if values.get("story") else []) \
            + (["--process", values["process"]] if values.get("process") else []) \
            + (["--request", values["request"]] if values.get("request") else [])
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.common_headers()
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        process = subprocess.Popen(argv, cwd=self.server.project, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   env=cli_env())
        with self.server.followers_lock:
            self.server.followers.add(process)
        lines = queue.Queue()

        def pump():
            for raw in iter(process.stdout.readline, b""):
                lines.put(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
            lines.put(None)
        threading.Thread(target=pump, daemon=True).start()
        try:
            while True:
                try:
                    line = lines.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": still here\n\n")          # a closed page is noticed on this write
                    self.wfile.flush()
                    continue
                if line is None:
                    self.wfile.write(b"event: end\ndata: \n\n")
                    self.wfile.flush()
                    return None
                self.wfile.write(f"data: {json.dumps(line, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return None
        finally:
            with self.server.followers_lock:
                self.server.followers.discard(process)
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                process.terminate()
                process.wait(timeout=5)

    # --- POST ------------------------------------------------------------------------------------------------------
    def do_POST(self):
        url = urllib.parse.urlsplit(self.path)
        if not self.guarded({}):
            return None
        if not self.write_ok():
            return self.refuse(403, "a write comes from this page alone")
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self.refuse(415, "a write sends JSON")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > 65536:
            return self.refuse(413, "a write is at most 64 KiB")
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("not an object")
        except ValueError as error:
            return self.refuse(400, f"no JSON object — {error}")
        project = self.server.project
        by = " ".join(str(body.get("by") or "").split())[:80] or default_by(project)
        if url.path == "/api/request":
            fields = {k: body[k] for k in REQUEST_FIELDS if body.get(k)}
            try:
                with in_project(project):
                    request_id, path = write_request(project, str(body.get("kind", "")), fields,
                                                     str(body.get("words") or ""), by)
            except Duplicate as same:
                return self.json(200, dict(id=same.existing, duplicate=True, message=str(same)))
            except (RequestError, GateError) as error:
                return self.refuse(400, str(error))
            return self.json(201, dict(id=request_id, path=os.path.relpath(path, project).replace(os.sep, "/")))
        if url.path in ("/api/requests/drop", "/api/requests/retry"):
            request_id = str(body.get("id", ""))
            try:
                with in_project(project):
                    (drop_request if url.path.endswith("drop") else retry_request)(request_id)
            except (RequestError, OSError) as error:
                return self.refuse(400, str(error))
            return self.json(200, dict(id=request_id))
        if url.path == "/api/up":
            code, out, error = run_cli(project, ["--up", "--by", by], timeout=60)
            return self.json(200 if code == 0 else 500, dict(exit=code, output=(out + error).strip()))
        if url.path == "/api/down":
            code, out, error = run_cli(project, ["--down", "--no-wait", "--by", by] + (["--now"] if body.get("now") else []),
                                       timeout=30)
            return self.json(200 if code == 0 else 500, dict(exit=code, output=(out + error).strip()))
        return self.refuse(404, "no such write")

    def do_HEAD(self):
        self.refuse(405, "GET or POST")


@contextlib.contextmanager
def in_project(project):
    """The places read from the project's profile, for a call that writes there from the server's thread."""
    from .contract import read_profile, resolve_profile, set_places
    lock = SERVER_LOCK
    with lock:
        here = os.getcwd()
        os.chdir(project)
        try:
            set_places(read_profile(resolve_profile(None, project)))
            yield
        finally:
            os.chdir(here)


SERVER_LOCK = threading.Lock()
