"""The web host (WP-91): one page in front of the factory, bound to this machine alone, opened with a token of its
start. It shows every context at once and decides nothing: the views are the factory's own JSON, read through
`factory-cli.py`, a process per call, so the page shows exactly what `factory.sh` shows; every press writes a request
through its use case. 127.0.0.1 only, a random token per start in the URL and on every call, the Host and, for a
write, the Origin checked: no other web page can read the factory or write to it.
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
import urllib.parse
import zlib

from ..building_blocks import UseCaseException
from ..sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from ..delivery.adapter.outgoing.files.request_files import default_by, stamp_utc
from ..delivery.adapter.outgoing.process.factory_process import (
    cli_path, own_file, read_json, say, SERVE_FILE, write_json)
from ..delivery.application.requests.retry_request import RetryRequestCommand
from ..delivery.application.requests.take_back_request import TakeBackRequestCommand
from ..delivery.application.requests.write_request import WriteRequestCommand
from ..delivery.application.shared.requests import DuplicateRequest, ID_WORD, KINDS, RequestRefused
from ..infrastructure import delivery as wiring
from .page import FAVICON, PAGE, SCRIPT_HASH

PORT_BASE, PORT_SPAN = 8700, 200    # where a project's page looks for its port, a stable one per project first


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

    def server_bind(self):
        """Bound without `HTTPServer`'s name lookup: it asks the resolver for 127.0.0.1's full name (`getfqdn`), which
        on some machines hangs for longer than a start may wait, and the page never uses the name."""
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

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
                    written = wiring.write_request(project).execute(
                        WriteRequestCommand(str(body.get("kind", "")), fields, str(body.get("words") or ""), by))
            except DuplicateRequest as same:
                return self.json(200, dict(id=same.existing, duplicate=True, message=str(same)))
            except (UseCaseException, GateError) as error:
                return self.refuse(400, str(error))
            return self.json(201, dict(id=written.id, path=os.path.relpath(written.path, project).replace(os.sep, "/")))
        if url.path in ("/api/requests/drop", "/api/requests/retry"):
            request_id = str(body.get("id", ""))
            try:
                with in_project(project):
                    if url.path.endswith("drop"):
                        wiring.take_back_request(project).execute(TakeBackRequestCommand(request_id))
                    else:
                        wiring.retry_request(project).execute(RetryRequestCommand(request_id))
            except (RequestRefused, OSError) as error:
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
    from ..sharedkernel.adapter.outgoing.profile.profile_files import read_profile, resolve_profile, set_places
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
