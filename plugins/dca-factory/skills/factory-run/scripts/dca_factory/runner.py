"""The runner: `factory.sh run` and the requests it works — its stage arrays, and the run of a story, of the backlog
and of a request.

The shell tables the runner reads once at its start, then one process per stage of a story in its worktree, the
gate between them, the integration, the requests between stories and the parallel slots. A story's worktree steps,
the layout migrations and the stage files' skeletons are adapters of their own (`git/worktree_steps.py`,
`files/migrations.py`, `files/skeletons.py`).
"""

import argparse
import contextlib
import glob
import hashlib
import os
import re
import secrets
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from .contract import (
    ALL_KINDS, GateError, OWNED_DIGEST, SHARED_WINDOWS, STAGE, STAGE_FILES,
    STAGE_ORDER, STAGES, WINDOW_DIGEST)
from .sharedkernel.adapter.outgoing.profile.profile_files import (
    evidence_dir, evidence_rel, place, PROFILE_FILE, read_profile,
    resolve_profile, set_places, shown)
from .delivery.adapter.outgoing.git.repository import git, git_identity
from .delivery.adapter.outgoing.files.decision_record_files import (
    decisions_store, needs_human_ids, record_path, stamp_applied)
from .delivery.adapter.outgoing.files.story_layout import (
    find_story, is_delivered, story_kind)
from .sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .delivery.adapter.outgoing.tools.streams import stream_limit, tokens_of, usage_lines
from .state import start_of
from .delivery.adapter.outgoing.claims.remote_claims import claim_config_here
from .delivery.adapter.outgoing.claims.checkout_claim import claim
from .delivery.adapter.outgoing.files.windows import freeze_all
from .delivery.adapter.outgoing.files.stream_records import freeze_stream
from .delivery.adapter.outgoing.files.usage_files import journal_usage
from .delivery.adapter.outgoing.files.run_marks import (
    back_in, run_stories, STAGE_WORD, step_open, verdict_in)
from .delivery.adapter.outgoing.git.worktrees import has_worktree
from .delivery.adapter.outgoing.files.journal_files import journal_path, journal_writer
from .delivery.adapter.outgoing.files.kept_files import stale_red_proof
from .delivery.adapter.outgoing.files.delivery_writes import story_journals
from .delivery.adapter.outgoing.git.change import in_places, people_places
from .delivery.adapter.outgoing.build.commands import run as run_command, tail
from .delivery.adapter.outgoing.git.integration import (
    integration_target, lost_text, main_tests_lost)
from .delivery.adapter.outgoing.files.delivery_files import perspectives_of
from .delivery.adapter.outgoing.tools.agents import isolation_args, TOOL, tool_command, TOOLS, tools_shell
from .building_blocks import UseCaseException
from .delivery.adapter.incoming.runner.usage import book_request_usage
from .delivery.adapter.outgoing.files.decision_record_files import project_record_path, request_records
from .delivery.adapter.outgoing.files.journal_files import mark_questioned
from .delivery.adapter.outgoing.files.request_files import (
    default_by, find_request, list_requests, out_path, prune_outputs, read_request, REQUEST_JOURNAL, requests_dir,
    stamp_utc, update_request)
from .delivery.adapter.outgoing.files.request_files import journal as request_journal
from .delivery.application.requests.check_request import CheckRequestCommand
from .delivery.application.requests.list_requests import target_text
from .delivery.application.shared.requests import KIND, RequestRefused, stories_of, written_keys
from .infrastructure import delivery as wiring


FILE_WORD = re.compile(r"[a-z0-9][a-z0-9_.-]*")


def stage_names(kind=None, window=None, every=False):
    """The table's stage names in its order: the run order (every row with `every`), narrowed to the stages a story
    of `kind` runs and to those `window` carries."""
    return [s.name for s in STAGES if (every or s.in_order) and (kind is None or kind in s.kinds)
            and (window is None or s.window == window)]


def stages_shell(places=()):
    """The table as the runner reads it once at its start, one bash assignment per line: the run order, the steps
    after it, each shared window's stages, which gate runs before and which after its stage, the stages whose gate
    runs the mapped tests without the suite, the stages under the guard, which kind runs which row, the hand-over each stage writes — and the
    places asked for, quoted. Every name is the table's, checked to be a plain word; nothing is read from a file."""
    names = [s.name for s in STAGES] + list(SHARED_WINDOWS) + list(ALL_KINDS)
    bad = [name for name in names if not STAGE_WORD.fullmatch(name)]
    bad += [file for file in STAGE_FILES.values() if not FILE_WORD.fullmatch(file)]
    if bad:
        print(f"factory-cli: the stage table holds a name the runner cannot take as a word: {', '.join(bad)}",
              file=sys.stderr)
        return 2
    array = lambda name, values: f"{name}=({' '.join(values)})"
    lines = [array("STAGES", STAGE_ORDER), array("STEPS", [s.name for s in STAGES if not s.in_order])]
    lines += [array(f"{window.upper().replace('-', '_')}_STAGES", stages) for window, stages in SHARED_WINDOWS.items()]
    lines += [array("PRE_GATED", [s.name for s in STAGES if s.in_order and s.gated and not s.post_gated]),
              array("POST_GATED", [s.name for s in STAGES if s.in_order and s.post_gated]),
              array("RED_STAGES", [s.name for s in STAGES if s.in_order and s.tested and not s.suite]),
              array("GUARDED_STAGES", [s.name for s in STAGES if s.guarded])]
    lines.append("KIND_STAGES=' " + " ".join(f"{kind}:{s.name}" for s in STAGES for kind in s.kinds) + " '")
    lines.append("STAGE_FILES=' " + " ".join(f"{name}:{file}" for name, file in STAGE_FILES.items()) + " '")
    tools = tools_shell()
    if tools is None:
        return 2
    lines += tools + [f"PLACE_{key.upper()}={shlex.quote(place(key))}" for key in places]
    print("\n".join(lines))
    return 0


# --- the run: what `factory.sh run` starts once its checks before the first stage passed -------------------------
# One process per stage, so every stage starts with a fresh context and reads only its story and its predecessor's
# file. The runner composes and starts; every project file it reads it reads with the cli's readers, in its own
# process, after `Run.profile` set the places from where it stands — the checkout or a story's worktree — exactly
# as a cli started there would. What changes the checkout's state — the claim, a skeleton, a worktree — runs as
# the cli, a process of its own (`Run.cli`); what it may not decide — whether a stage is done — is the gate's, a
# process of its own as well.
#
# Exit codes: 0 the story ran through, 1 a failure, 2 a usage error, 3 it stopped for a decision, 4 at --max-stages
# or --story-budget, 5 another worker holds the checkout, 7 the pipeline or a person's file changed under it,
# 124 a stage ran past its time limit is reported as a failure (1), 129/130/143 a hang-up, an interrupt, a TERM.

#: The shell a stage may use without asking, beside the gate, the cli and the profile's commands: the ordinary
#: reading and text tools, the git verbs that look without changing anything (`git apply --check` is how a stage
#: tries a break patch), and `git rm` — how a stage removes a file its plan says `removed`; it takes tracked files
#: only, which git still holds, and the pipeline's own files are watched by the run (WP-102). What writes or runs
#: anything else stays out — `rm`, `sed -i`, `xargs`, `find -exec`, a redirect of `echo`/`printf`, `mkdir`: each
#: allowed head is allowed with every argument (WP-94). Measured on the bench: without the reading tools a stage hit
#: the allow-list about three times per story, each a wasted turn; without a delete the build left a planned removal.
STAGE_SHELL_HEADS = ("cd", "ls", "cat", "head", "tail", "wc", "sort", "grep", "diff", "pwd",
                     "git status", "git diff", "git log", "git ls-files", "git apply --check", "git rm")
#: The cli flags a skill run for a request may call (WP-91): what the dialog skills read and record with — never one
#: that starts a run, a request, the factory or its page (`--run`, `--work-request`, `--request`, `--up`, `--serve`).
REQUEST_CLI_FLAGS = ("--contract", "--free-id", "--window-start", "--window-end", "--list-decisions", "--spec-delta",
                     "--spec-check", "--findings", "--reopen", "--owned-confirm", "--status", "--discover-list",
                     "--help-view", "--journal-line")
STAGE_SHELL = ("cd, ls, cat, head, tail, wc, sort, grep, diff, pwd, and git status, git diff, git log, git ls-files, "
               "git apply --check, and git rm (a file the plan removes)")

#: The first line of a snapshot written without a hash: the observer reads such a snapshot as absent, because a
#: snapshot of empty digests compares equal to every other and would read as "this stage changed nothing".
NO_HASHES = "# no-sha256-command: names only, no content hashes"

#: Where a tool ran past this many seconds, it is stopped (0: no limit) — FACTORY_STAGE_TIMEOUT, else the profile's
#: `stageTimeout:`. A number with `s`, `m` or `h`; a bare number is seconds.
TIMEOUT_UNITS = {"": 1, "s": 1, "m": 60, "h": 3600}
TIMED_OUT = 124
#: The usage limit (#161): the wait where the tool names no reset, the margin past the one it names, how often the
#: wait looks at the stop file and renews the claim — seconds.
LIMIT_FALLBACK, LIMIT_MARGIN, LIMIT_POLL = 1800, 60, 60
SIGNAL_EXITS = {"SIGTERM": 143, "SIGHUP": 129, "SIGINT": 130}


class Stopped(Exception):
    """The run ends here with this exit code — the pipeline changed under it, a signal arrived."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def utc(fmt="%Y-%m-%dT%H:%M:%SZ"):
    return time.strftime(fmt, time.gmtime())


def seconds_of(text):
    """`90`, `90s`, `30m`, `2h` → seconds; None for anything else."""
    match = re.fullmatch(r"\s*(\d+)\s*([smh]?)\s*", str(text or ""))
    return int(match.group(1)) * TIMEOUT_UNITS[match.group(2)] if match else None


def first_word(value):
    parts = str(value or "").split()
    return parts[0] if parts else ""


def newer(path, than):
    """`[ path -nt than ]`: path exists and is newer, or than does not exist."""
    if not os.path.exists(path):
        return False
    return not os.path.exists(than) or os.path.getmtime(path) > os.path.getmtime(than)


class Run:
    """One runner process: the story or the backlog it runs, and what it keeps between stages."""

    def __init__(self, options, home, runs, worker=None):
        self.py = os.environ.get("FACTORY_RUNNER_PYTHON") or "python3"   # the name the prompts and the list carry
        self.scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cli_path = os.path.join(self.scripts, "factory-cli.py")
        self.gate_rel = ".agents/factory/story-gate.py"
        self.gate_path = self.gate_rel
        self.home = home
        self.pwd = os.getcwd()
        self.runs_rel = runs
        self.runs = runs
        absolute = os.path.isabs(runs) or re.match(r"^[A-Za-z]:", runs)
        parent = os.path.dirname(runs) if absolute else os.path.join(home, os.path.dirname(runs))
        self.stop_file = os.path.join(parent, "stop").replace("\\", "/") if absolute else f"{home}/{os.path.dirname(runs)}/stop"
        self.lock_dir = f"{os.path.dirname(runs)}/integrate.lock" if absolute else f"{home}/{os.path.dirname(runs)}/integrate.lock"
        self.worker = worker or f"runner:{socket.gethostname() or 'host'}:{os.getpid()}"
        self.suites_key = secrets.token_hex(16)
        self.invocations = 0
        self.nested_code = 0
        self.gate_first = False
        self.max_stages = options.max_stages
        self.story_budget = options.story_budget
        self.shared_builder = options.builder == "shared"
        self.shared_verifier = options.verifier == "shared"
        self.parallel = options.parallel
        self.keep_going = getattr(options, "keep_going", False)
        self.stay = getattr(options, "stay", False)
        self.allowed_override = None
        self.skipped = {}                     # --keep-going: story → the exit it stopped with
        self.red_stale = {}                   # story → its tests whose red proof a merge left stale
        self.options = options
        self.add_dirs, self.read_dirs = [], []
        self.tool_in_flight = ""
        self.request_in_flight = ""         # the request whose process runs: a window it opens is its to measure
        self.settled_commit = ""            # the commit of the last request the factory settled itself
        self.pipeline_sha = os.environ.get("FACTORY_RUNNER_PIPELINE_SHA", "")
        self.claimed = False
        self.lock_held = False
        self.sleeping = False
        self.pending = None
        self.timeout = self.stage_timeout()

    # --- processes -----------------------------------------------------------------------------------------
    def wait(self, process, timeout=None):
        return process.wait(timeout=timeout)

    def checkpoint(self):
        """A TERM or HUP that arrived ends the run here — between stages, never inside one."""
        if self.pending is not None:
            code, self.pending = self.pending, None
            raise Stopped(code)

    def run(self, argv, *, capture=False, quiet=False, merge=False, cwd=None, env=None, stdin=None, stdout=None):
        """A child process run to its end: (exit code, its stdout when captured)."""
        out = subprocess.PIPE if capture else stdout
        errors = subprocess.STDOUT if merge else (subprocess.DEVNULL if quiet else None)
        flush()
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=stdin, stdout=out, stderr=errors)
        data = b""
        if capture:
            data, _ = process.communicate()
            code = process.returncode
        else:
            code = self.wait(process)
        # A Python child on Windows writes its lines with \r\n: read as bytes, the \r would stay on every field.
        text = data.decode("utf-8", errors="replace").replace("\r\n", "\n") if capture else ""
        return code, text.rstrip("\n")

    def cli(self, *args, quiet=True, merge=False, cwd=None, env=None):
        """The cli beside this runner: (exit code, stdout without its last newlines)."""
        return self.run([sys.executable, self.cli_path, *args], capture=True, quiet=quiet and not merge, merge=merge,
                        cwd=cwd, env=env)

    def profile(self):
        """The stack profile as a cli started here would read it, with the places set from it — in a story's
        worktree the main checkout's (FACTORY_HOME). Read again on every question: a person may edit the profile
        while a run waits, and the places change as the runner moves between the checkout and a worktree."""
        profile = read_profile(resolve_profile(os.environ.get("FACTORY_PROFILE") or None, os.getcwd()))
        set_places(profile)
        return profile

    def home_env(self):
        """The environment of a call made in the main checkout: no FACTORY_HOME, as there."""
        env = dict(os.environ)
        env.pop("FACTORY_HOME", None)
        return env

    def journal_line(self, story, line):
        """Every journal line is numbered under the journal's lock, a folder — the same for the gate, the cli and
        a reviewer appending beside the runner."""
        self.profile()
        if not story:                       # a request's process belongs to no story: the request journal takes it
            with contextlib.suppress(OSError):
                os.makedirs(requests_dir(), exist_ok=True)
                with open(os.path.join(requests_dir(), REQUEST_JOURNAL), "a", encoding="utf-8", newline="\n") as handle:
                    handle.write(line + "\n")
            return
        with contextlib.suppress(OSError, GateError, ValueError):   # an unwritable journal costs the line, not the run
            journal_writer(place("runs"), story).write(line + "\n")

    @contextlib.contextmanager
    def step(self, story, name):
        """A step the runner works itself — integrate, merge, format — journaled as running (`step-start`/
        `step-end`), so the status shows it with its clock; no stage's reader counts it as a stage run. A delivery
        ends its integrate step itself, before its commit; the runner ends a step the journal still shows open."""
        self.journal_line(story, f"{utc()}\tstep-start\t{name}\tby=runner")
        code = None
        try:
            yield
            code = 0
        finally:
            if step_open(place("runs"), story, name):
                self.journal_line(story, f"{utc()}\tstep-end\t{name}\texit={'0' if code == 0 else 'stopped'}")

    def gate_installed(self):
        return os.path.isfile(self.gate_path)

    # --- places --------------------------------------------------------------------------------------------
    def evidence(self, story):
        parent = os.path.dirname(self.runs)
        parent = ".dca-factory" if parent in (".", "") else parent
        return f"{parent}/evidence/{story}"

    def evidence_rel(self):
        parent = os.path.dirname(self.runs_rel)
        parent = ".dca-factory" if parent in (".", "") else parent
        return f"{parent}/evidence"

    def stage_file(self, stage):
        return STAGE_FILES.get(stage, "")

    def artefact(self, story, stage):
        return f"{self.runs}/{story}/{self.stage_file(stage)}"

    @staticmethod
    def kind_runs(kind, stage):
        return stage in STAGE and kind in STAGE[stage].kinds

    def back_for(self, kind, stage):
        """Where a round goes back to: <stage>, or the last builder stage before it the kind runs."""
        if self.kind_runs(kind, stage):
            return stage
        back = stage
        for st in SHARED_WINDOWS["builder"]:
            if self.kind_runs(kind, st):
                back = st
            if st == stage:
                break
        return back

    # --- the pipeline, unchanged ---------------------------------------------------------------------------
    @staticmethod
    def hashing():
        return os.environ.get("FACTORY_SHA256", "") != "none"

    def pipeline_hash(self, folder=None):
        """One SHA-256 over the installed files' digests — the stamp's `sha256:` line."""
        if not self.hashing():
            return None
        folder = folder or os.path.join(self.home, ".agents", "factory")
        listing = ""
        for name in PIPELINE_FILES:
            path = os.path.join(folder, name)
            if name.endswith("/"):
                if not os.path.isdir(path):
                    listing += f"missing  {name}\n"
                    continue
                for module in package_modules(path):
                    listing += f"{file_sha(os.path.join(path, module))}  {name}{module}\n"
            elif os.path.isfile(path):
                listing += f"{file_sha(path)}  {name}\n"
            else:
                listing += f"missing  {name}\n"
        return hashlib.sha256(listing.encode("utf-8")).hexdigest()

    def guard_pipeline_start(self):
        stamp = os.path.join(self.home, STAMP)
        if not os.path.isfile(stamp):
            return 0
        self.pipeline_sha = self.pipeline_hash() or ""
        if not self.pipeline_sha:
            return 0
        stamped = next((line.split(":", 1)[1].strip() for line in read_text(stamp).splitlines()
                        if line.startswith("sha256:")), "")
        if not stamped:
            err(f"factory: {STAMP} carries no hash (installed before 0.68.0) — the gates compare against the pipeline as it")
            err("factory:   is now; 'factory.sh update' records one.")
        elif stamped != self.pipeline_sha:
            err(f"factory: the installed pipeline is not the one {STAMP} records — a file under .agents/factory/ changed")
            err("factory:   since the install. Nothing was started; 'factory.sh update' installs it again.")
            return 7
        return 0

    def guard_pipeline(self, stage, story):
        """Before every gate the runner runs: the pipeline is still the one the run started with."""
        if not self.pipeline_sha:
            return 0
        now = self.pipeline_hash()
        if not now or now == self.pipeline_sha:
            return 0
        err(f"factory: the installed pipeline changed during {story}'s run, before its {stage} gate — a stage never writes")
        err("factory:   .agents/factory/. Nothing more runs; 'factory.sh update' installs it again, and the story runs")
        err("factory:   from the stage that changed it.")
        self.journal_line(story, f"{utc()}\tpipeline-changed\t{stage}")
        with contextlib.suppress(OSError):
            open(self.stop_file, "w").close()
        return 7

    # --- the checkout ----------------------------------------------------------------------------------------
    def take_checkout(self):
        if not self.gate_installed():
            err(f"factory: no gate at {self.gate_rel} — the checkout is not claimed; install the pipeline")
            return 0
        if self.take_claim(print) != 0:
            err("factory: another worker holds this checkout — see 'factory.sh status'. Nothing was started.")
            return 5
        self.claimed = True
        return 0

    def release(self):
        if self.claimed:
            self.claimed = False
            with contextlib.suppress(Exception):
                subprocess.run([sys.executable, self.cli_path, "--release", self.worker], cwd=self.home,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=self.home_env())

    def renew(self):
        """The claim, renewed before a stage: False when another worker took the checkout over."""
        if not self.gate_installed():
            return True
        return self.take_claim(lambda _line: None) == 0

    def take_claim(self, say):
        """Take or renew the checkout's claim — one per main checkout, so a worktree renews its home's — after the
        stories' journals are frozen, as every command that writes does. 3 when another worker holds it; 1 when the
        claim cannot be written."""
        self.profile()
        freeze_all(place("runs"))
        try:
            return claim(os.getcwd(), self.worker, say)
        except (OSError, ValueError):
            return 1

    def take_lock(self):
        """One integration at a time: the git work in the main checkout runs under a lock beside the run folder."""
        with contextlib.suppress(OSError):
            os.makedirs(os.path.dirname(self.lock_dir), exist_ok=True)
        stale = int(os.environ.get("FACTORY_STALE_AFTER") or 7200)
        while True:
            try:
                os.mkdir(self.lock_dir)
                self.lock_held = True
                return 0
            except FileExistsError:
                pass
            except OSError:
                if not os.path.isdir(os.path.dirname(self.lock_dir)):
                    err(f"factory: no place for the lock at {self.lock_dir}")
                    return 1
            try:
                age = int(time.time() - os.path.getmtime(self.lock_dir))
            except OSError:
                age = 0
            if age > stale:
                err(f"factory: {self.lock_dir} is {age}s old — its holder ended without giving it back; taken over.")
                with contextlib.suppress(OSError):
                    os.rmdir(self.lock_dir)
                continue
            self.sleep(2)

    def drop_lock(self):
        if self.lock_held:
            self.lock_held = False
            with contextlib.suppress(OSError):
                os.rmdir(self.lock_dir)
        return 0

    def sleep(self, seconds):
        """A pause a TERM or HUP ends at once — nothing runs beside it."""
        self.checkpoint()
        self.sleeping = True
        try:
            time.sleep(seconds)
        finally:
            self.sleeping = False
        self.checkpoint()

    # --- the tool ----------------------------------------------------------------------------------------------
    def stage_timeout(self):
        given = os.environ.get("FACTORY_STAGE_TIMEOUT")
        if given is None:
            given = first_word(self.profile().get("stageTimeout", "")) if self.gate_installed() else ""
        value = seconds_of(given) if given else 0
        if given and value is None:
            err(f"factory: the stage time limit '{given}' is no number of seconds (90, 90s, 30m, 2h) — no limit applies")
        return value or 0

    @staticmethod
    def isolated():
        return os.environ.get("FACTORY_ISOLATION", "on") != "off"

    def isolation_flags(self, tool):
        if not self.isolated():
            return ""
        return (" ".join(shlex.quote(w) for w in isolation_args(TOOL[tool])) if tool in TOOL else "") + " "

    def allowed_commands(self):
        if getattr(self, "allowed_override", None):
            return self.allowed_override
        heads = [f"Bash({self.py} {self.gate_rel}:*)", f"Bash({self.py} .agents/factory/factory-cli.py:*)"]
        for head in command_heads(self.profile()) + list(STAGE_SHELL_HEADS):
            if f"Bash({head}:*)" not in heads:
                heads.append(f"Bash({head}:*)")
        return ",".join(heads)

    def model_key(self, tool, stage):
        return model_for(self.profile(), tool, (stage or "").split(":")[0])

    @staticmethod
    def tool_args(tool):
        record = TOOL.get(tool)
        return os.environ.get(record.args_env, "") if record and record.args_env else ""

    def env_model(self, tool):
        match = re.search(r".*(?:^| )(?:-m|--model)[ =]([^ ]*)", self.tool_args(tool))
        return match.group(1) if match else ""

    @staticmethod
    def unit_keys(unit):
        """The profile keys a unit is named by, most specific first: `review:ddd` → review.ddd, review."""
        unit = (unit or "").replace(":", ".")
        head = unit.split(".")[0]
        return [unit] + ([head] if head != unit else [])

    def tool_for(self, unit, given):
        """The tool one unit runs with: `--tool` when the person named one for this run (FACTORY_TOOL_EXPLICIT), else
        the profile's `tool.<unit>` (a review `tool.review.<perspective>`, then `tool.review`), else `tool:`, else
        the run's tool. A unit is what one process carries: the shared builder and verifier, a review, a separate
        stage, the integrate step."""
        if os.environ.get("FACTORY_TOOL_EXPLICIT") or os.environ.get("FACTORY_TOOL_CMD"):
            return given
        profile = self.profile()
        for key in self.unit_keys(unit):
            named = first_word(profile.get(f"tool.{key}", ""))
            if named:
                return named
        return first_word(profile.get("tool", "")) or given

    def effort_choice(self, tool, unit):
        """(level, note) — the reasoning effort of one unit: the profile's `effort.<tool>.<unit>`, else
        `effort.<tool>`; a `--effort`/`model_reasoning_effort` in FACTORY_<TOOL>_ARGS wins, and a tool that takes no
        effort gets a note, never a silent drop."""
        profile = self.profile()
        level = next((first_word(profile.get(f"effort.{tool}.{key}", "")) for key in self.unit_keys(unit)
                      if first_word(profile.get(f"effort.{tool}.{key}", ""))), "") \
            or first_word(profile.get(f"effort.{tool}", ""))
        if not level:
            return "", ""
        if re.search(r"(--effort|model_reasoning_effort)", self.tool_args(tool)):
            return "", f"overridden by FACTORY_{tool.upper()}_ARGS"
        if tool not in TOOL or not TOOL[tool].effort:
            return "", f"effort not applied — tool {tool} takes none"
        return level, ""

    def effort_field(self, tool, unit):
        level, note = self.effort_choice(tool, unit)
        if note:
            print(f"factory: effort for {unit}: {note}")
        return f"\teffort={level}" if level else (f"\teffort=no ({note})" if note else "")

    def tools_of_run(self, given):
        """Every tool this run may start: the given one and every `tool`/`tool.<unit>` the profile names."""
        named = {first_word(v) for k, v in self.profile().items() if (k == "tool" or k.startswith("tool.")) and v}
        return sorted({given} | {n for n in named if n})

    def model_choice(self, tool, stage):
        """The model flag for one stage, and why a request does not become one: (flag words, note). The model is
        the project's choice, stated in the profile per tool and stage (`model.<tool>.<stage>`, falling back to
        `model.<tool>`); the pipeline names none. A `--model`/`-m` in FACTORY_<TOOL>_ARGS wins — the person's local
        override — and the run says so. Exactly one model flag is ever passed."""
        requested = self.model_key(tool, stage)
        if not requested:
            return "", ""
        if os.environ.get("FACTORY_TOOL_CMD"):
            return "", "passed as FACTORY_MODEL to the custom command"
        if self.env_model(tool):
            return "", f"overridden by FACTORY_{tool.upper()}_ARGS ({self.env_model(tool)})"
        flag = TOOL[tool].model_flag if tool in TOOL else ""
        return (f"{flag} {requested}", "") if flag else ("", f"no model flag for tool {tool}")

    def model_flag(self, tool, stage=""):
        """The model a tool ran with, where its output does not say."""
        if stage and self.model_key(tool, stage) and not self.env_model(tool):
            return self.model_key(tool, stage)
        match = re.search(r".*(?:-m|--model)[ =]([^ ]*)", self.tool_args(tool))
        return match.group(1) if match else ""

    def protected_dirs(self):
        dirs = [".agents/factory", self.evidence_rel(), *TOOL_SKILL_DIRS, ".agents/skills"]
        return [d if os.path.isabs(d) or re.match(r"^[A-Za-z]:", d) else f"{self.home}/{d}" for d in dirs]

    def usage_format(self, tool):
        if os.environ.get("FACTORY_TOOL_CMD"):
            return os.environ.get("FACTORY_USAGE_FORMAT") or "none"
        return (TOOL[tool].usage if tool in TOOL else "") or "none"

    def dry_lines(self, tool, prompt, model_stage):
        print(f"   would run: {prompt}")
        isolation = os.environ.get("FACTORY_ISOLATION")
        print(f"   tool flags: {self.isolation_flags(tool)}" + (f"(FACTORY_ISOLATION={isolation})" if isolation else ""))
        print(f"   shell allowed: {self.allowed_commands()}")
        flags, note = self.model_choice(tool, model_stage)
        print(f"   model: {flags}{note}")

    def invoke(self, tool, prompt, raw, stage, story, count=True):
        """One stage's tool process; its output kept in <raw>, where the tool also says what the stage cost. A process
        that ran into the tool's usage limit is kept beside it (`<raw>` with `-limit<n>` before `.out`, its usage
        journaled), the runner waits for the reset and the same stage runs again — no round counted, no story set
        aside (#161)."""
        attempt = 0
        while True:
            code = self.invoke_once(tool, prompt, raw, stage, story, count and attempt == 0)
            fmt = self.usage_format(tool)
            limited = stream_limit(raw, None if fmt == "none" else fmt) if raw != os.devnull else None
            if not limited:
                return code
            attempt += 1
            kept = f"{raw[:-len('.out')]}-limit{attempt}.out" if raw.endswith(".out") else f"{raw}.limit{attempt}"
            with contextlib.suppress(OSError):
                os.replace(raw, kept)
            self.record_usage(story, stage, tool, kept)
            if not self.wait_for_limit(story, stage, tool, limited):
                return code if code != 0 else 1
            if attempt == 1:
                prompt += (" An earlier process of this stage stopped at the tool's usage limit before it finished: "
                           "read the files as they are and go on from there.")

    def wait_for_limit(self, story, stage, tool, limited):
        """Until a minute past the reset the tool named — or FACTORY_LIMIT_WAIT (30m) where it named none, or one past.
        The claim is renewed while it waits, and the journal says until when, so the schedule reads the stage as
        running, not as interrupted. False where the stop file, another worker or a signal ends the wait."""
        now = time.time()
        fallback = seconds_of(os.environ.get("FACTORY_LIMIT_WAIT", "")) or LIMIT_FALLBACK
        until = limited["until"] + LIMIT_MARGIN if limited.get("until") and limited["until"] > now else now + fallback
        when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(until))
        self.journal_line(story, f"{utc()}\tlimit\t{stage}\ttool={tool}\tuntil={when}")
        said = f" ({limited['text']})" if limited.get("text") else ""
        print(f"factory: {tool} reached its usage limit during {stage}{said} — waiting until {when}, then {stage} runs "
              f"again; {self.stop_file} ends the wait.")
        main = threading.current_thread() is threading.main_thread()
        while time.time() < until:
            if os.path.isfile(self.stop_file):
                err(f"factory: {self.stop_file} exists — the wait for the usage limit ends; {stage} did not finish.")
                return False
            if main and not self.renew():
                err("factory: another worker took over this checkout while the run waited for the usage limit.")
                return False
            self.sleep(min(LIMIT_POLL, max(1, until - time.time())))
        print(f"factory: the usage limit reset — {stage} runs again.")
        return True

    def invoke_once(self, tool, prompt, raw, stage, story, count=True):
        """One tool process, as `invoke` starts it."""
        if count:
            self.invocations += 1
        flags, _note = self.model_choice(tool, stage)
        command = os.environ.get("FACTORY_TOOL_CMD")
        env = dict(os.environ, FACTORY_WORKER=self.worker, FACTORY_STAGE=stage or "", FACTORY_STORY=story or "",
                   FACTORY_REQUEST=self.request_in_flight)
        if command:
            env.update(FACTORY_PROMPT=prompt, FACTORY_RUNS=self.runs, FACTORY_MODEL=self.model_key(tool, stage))
            code = self.tool_process(["sh", "-c", command], env, raw, stdin=None, stage=stage)
            if raw != os.devnull and not os.environ.get("FACTORY_USAGE_FORMAT"):
                with contextlib.suppress(OSError):
                    sys.stdout.write(read_text(raw))
                    flush()
            return code
        if tool not in TOOL:
            err(f"factory: unknown tool '{tool}'")
            return 2
        level, _note = self.effort_choice(tool, stage)
        variables, argv = tool_command(TOOL[tool], model=flags.split(" ", 1)[1] if flags else "",
                                       writable=self.add_dirs, readable=self.read_dirs,
                                       protected=self.protected_dirs(), allowed=self.allowed_commands(), effort=level)
        env.update(variables)
        return self.tool_process(spawnable(argv + [prompt]), env, raw, stdin=subprocess.DEVNULL, stage=stage)

    def tool_process(self, argv, env, raw, stdin, stage):
        """A tool started in a session of its own, so a time limit or an interrupt stops it with what it started."""
        flush()
        with open(raw, "wb") as out:
            try:
                process = subprocess.Popen(argv, env=env, stdin=stdin, stdout=out, start_new_session=os.name != "nt")
            except OSError as error:
                err(f"factory: the tool could not be started — {error}")
                return 127
            try:
                return self.wait(process, timeout=self.timeout or None)
            except subprocess.TimeoutExpired:
                stop_group(process)
                err(f"factory: stage '{stage}' ran past its time limit of {self.timeout}s (FACTORY_STAGE_TIMEOUT, the "
                    f"profile's stageTimeout:) — the tool was stopped.")
                return TIMED_OUT
            except KeyboardInterrupt:
                stop_group(process, signal.SIGINT)
                raise Stopped(SIGNAL_EXITS["SIGINT"])

    def exit_field(self, code):
        return "0" if code == 0 else "timeout" if code == TIMED_OUT else "nonzero"

    def record_usage(self, story, stage, tool, raw, seconds=None, request=""):
        """One `usage` line in the story's journal per invocation — a request's in the request journal, with its id —
        and the stage's final message on screen. Returns the measured fields."""
        fmt = self.usage_format(tool)
        model = self.model_flag(tool, stage)
        try:
            lines = "\n".join(usage_lines(fmt, raw, model)).split("\n")
        except Exception:                   # a raw output no reader understands costs the line, never the run
            lines = ["unknown"]
        fields = lines[0]
        if seconds is not None:
            fields += f"\tseconds={seconds}"
        if fmt != "none" and len(lines) > 1:
            print("\n".join(lines[1:]))
        self.journal_line(story, f"{utc()}\tusage\t{stage}\ttool={tool}" + (f"\trequest={request}" if request else "")
                          + f"\t{fields}")
        # what only the stream says — a shared window's parts, the denied calls — goes into the journal now (WP-150)
        if story and os.path.isfile(raw):
            with contextlib.suppress(OSError, GateError, ValueError):
                freeze_stream(journal_path(place("runs"), story), raw)
        return fields

    # --- what the files say --------------------------------------------------------------------------------
    def verdict_of(self, story):
        self.profile()
        return verdict_of_story(place("runs"), story)

    def asks_human(self, path):
        self.profile()
        return needs_human_lines(path) is not None

    def back_to(self, story, stage=None):
        """The stage a refusal sends the story back to: from the judge's file (`build` without one); with a stage,
        `test` where that stage found the defect in a test's own code, else nothing."""
        self.profile()
        path = os.path.join(place("runs"), story, STAGE_FILES[stage] if stage else "judge.md")
        if stage:
            return "test" if os.path.isfile(path) and back_in(read_text(path)) == "test" else ""
        return back_in(read_text(path)) if os.path.isfile(path) else "build"

    def start_stage(self, story):
        self.profile()
        found = start_of(os.getcwd(), place("epics"), place("runs"), story, 1)
        return "" if found is None else found[1] or "none"

    def open_decisions(self, story):
        self.profile()
        return "\n".join(open_decision_files(os.getcwd(), story))

    def delivered(self, story):
        self.profile()
        try:
            return is_delivered(read_front_matter(find_story(place("epics"), story))[0])
        except GateError:
            return False

    def kind_of(self, story):
        """`story`, `journey`, `adopt` or `task` — `story` for one that cannot be read."""
        self.profile()
        try:
            return story_kind(read_front_matter(find_story(place("epics"), story))[0])
        except GateError:
            return "story"

    def stopped_for_human(self, artefact, stage, story):
        """A stage that ends with a needs-human section has stopped: name the record and the command that resumes.
        3 when the question is a record — what a backlog run can wait on —, 1 when the section names none."""
        err(f"factory: stage '{stage}' ends with a needs-human section — the run stops here.")
        self.profile()
        rows = [line.split("\t") for line in needs_human_lines(artefact, story) or [] if line.strip()]
        ids = [row[0] for row in rows]
        if not ids:
            err("factory:   the section names no 'decision: <id>' — the stage has to write the question as")
            err("factory:   <story>/decisions/<nn>.md in the story's folder; the next gate refuses a question nobody was asked.")
        for rid in ids:
            record = next((row[2] for row in rows if row[0] == rid and len(row) > 2), "")
            if record and record != "-" and os.path.isfile(record):
                applies = next((row[1] for row in rows if row[0] == rid and len(row) > 1 and row[1] != "-"), "")
                err(f"factory:   decision {rid} → {record} — answer it there under '## Answer'")
                err(f"factory:   with answer:, by: and at:, then: factory.sh run --story {story} — it resumes at "
                    f"{applies or stage}, or earlier where the answer's applies: names an earlier stage")
            else:
                err(f"factory:   decision {rid} is named but its record {record or 'beside the story'} does not exist.")
        err(f"factory:   read {artefact} and decide; the stages after it were not run.")
        return 3 if ids else 1

    def refused_from(self, story, refused):
        """The stage a refused gate's round starts at: the refused stage, or an earlier one whose file the story's
        state reads as an earlier pass's."""
        start = self.start_stage(story)
        for st in STAGE_ORDER:
            if st == refused:
                break
            if st == start:
                return start
        return refused

    def bump_rounds(self, story):
        path = f"{self.evidence(story)}/.rounds"
        count = int("".join(c for c in read_text(path) if c.isdigit()) or 0) if os.path.isfile(path) else 0
        count += 1
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"{count}\n")
        return count

    def environment_refused(self, stage, story):
        """A refusal whose cause is the machine: no stage can put a tool on the PATH, so no round is counted."""
        report = f"{self.runs}/{story}/.gate-{stage}.txt"
        lines = read_text(report).splitlines() if os.path.isfile(report) else []
        if not any(line.startswith("gate:fail environment") for line in lines):
            return False
        reason = next((line[len("gate:fail environment — "):] for line in lines
                       if line.startswith("gate:fail environment — ")), "")
        err(f"factory: gate '{stage}' refused on the environment, not on the story — {reason}")
        err(f"factory:   no round is counted. Fix it, then: factory.sh run --story {story}")
        return True

    def reset_rounds(self, story, given_from):
        """A person's --from restarts the story's count; the old one is kept beside it, never deleted."""
        path = f"{self.evidence(story)}/.rounds"
        if not os.path.isfile(path):
            return
        os.replace(path, f"{self.evidence(story)}/rounds.{utc('%Y%m%dT%H%M%SZ')}")
        self.journal_line(story, f"{utc()}\trounds-reset\t-\tby=--from")
        print(f"factory: --from {given_from} starts a new count of rounds for {story} (the old one is under "
              f"{self.evidence(story)}/).")

    # --- what a stage is told ----------------------------------------------------------------------------------
    def skill_dirs(self, tool):
        first = TOOL[tool].skills if tool in TOOL else ""
        return [d for d in (first, *TOOL_SKILL_DIRS, ".agents/skills") if d]

    def where_things_are(self, tool, story):
        """What a stage otherwise searches for — the profile, the run folder, the gate's expectations, the
        catalog — named in its prompt."""
        common = next((f"{d}/factory-run/reference/stage-common.md" for d in self.skill_dirs(tool)
                       if os.path.isfile(f"{d}/factory-run/reference/stage-common.md")), "")
        own = os.path.abspath(os.path.join(self.scripts, "..", "reference", "stage-common.md"))
        if not common and os.path.isfile(own):
            common = own[len(self.pwd) + 1:] if own.startswith(self.pwd + "/") else own
        common = f" The rules every stage holds to: {common}." if common else ""
        catalog = ""
        profile = self.profile()
        knowledge = first_word(profile.get("knowledge", ""))
        if knowledge:
            at = next((f"{d}/{knowledge}/catalog/" for d in self.skill_dirs(tool)
                       if os.path.isdir(f"{d}/{knowledge}/catalog")), "")
            if at:
                catalog = f" The {knowledge} skill's catalog: {at}."
                read = [f"{at}{path}" for path in profile.get("knowledge.read", "").replace(",", " ").split()
                        if os.path.isfile(f"{at}{path}")]
                if read:
                    catalog += f" Before you write code, read once: {', '.join(read)}."
        cli_path = self.cli_rel()
        folders = (f"; the story's run folder {self.runs}/{story}/; its evidence folder {self.evidence_rel()}/{story}/"
                   if story else "")
        return (f"Where things are: the stack profile is {PROFILE_FILE}{folders}; what the gate checks in a stage's file: "
                f"`{self.py} {cli_path} --contract <stage>`.{common}{catalog} The shell you have without asking: "
                f"the gate, the cli, the profile's commands, and {STAGE_SHELL}.")

    def cli_rel(self):
        """The cli as a stage's prompt names it: the project's copy by the path its allow-list grants
        (`.agents/factory/factory-cli.py`, linked into a story's worktree), else relative to where the stage works.
        An absolute path is a command the allow-list does not cover, and the stage is refused it."""
        if os.path.isfile(".agents/factory/factory-cli.py"):
            return ".agents/factory/factory-cli.py"
        return self.cli_path[len(self.pwd) + 1:] if self.cli_path.startswith(self.pwd + "/") else self.cli_path

    def later_refusals(self, story, stage, where):
        """The reports of the gates after <stage> that refused the story and sent it back."""
        found, seen = "", False
        for later in STAGE_ORDER:
            if later == stage:
                seen = True
                continue
            if seen and os.path.isfile(f"{self.runs}/{story}/.gate-{later}.txt"):
                found += (f" The {later} gate refused the story and sent it back to {where}: "
                          f"{self.runs}/{story}/.gate-{later}.txt.")
        return found

    def worktree_sentence(self):
        home = os.environ.get("FACTORY_HOME")
        return f" This story's own worktree: {self.pwd}; the main checkout: {home}." if home else ""

    def guard_sentence(self):
        guard = first_word(self.profile().get("carrier.guard", ""))
        return f" The guard (the profile's carrier.guard): the {guard} skill." if guard else ""

    def prompt_for(self, stage, story):
        repeat = ""
        if os.path.isfile(f"{self.runs}/{story}/.gate-{stage}.txt"):
            repeat = f" The gate refused this stage before: {self.runs}/{story}/.gate-{stage}.txt."
        later = self.later_refusals(story, stage, "this stage")
        if later and stage == self.start_stage(story):
            repeat += later
        if stage == "test" and self.back_to(story, "build") == "test":
            repeat += f" The build stage sent the story back: {self.runs}/{story}/build.md."
        if stage == "test":
            repeat += self.red_stale_sentence(story)
        if stage == "judge" and os.path.isfile(f"{self.runs}/{story}/.judge-previous.md"):
            repeat = f" This is a repeat round; the previous verdict: {self.runs}/{story}/.judge-previous.md."
        guard = self.guard_sentence() if stage in STAGE and STAGE[stage].guarded else ""
        return (f"Apply the stage-{stage} skill for backlog story {story}.{self.worktree_sentence()} "
                f"{self.where_things_are(self.tool_in_flight, story)}{guard}{repeat}")

    def integrate_prompt(self, story, conflicts, lost=None):
        if lost:
            target = integration_target(self.runs, story) or "the main line"
            return (f"Apply the stage-integrate skill for backlog story {story}. The resolution of the merge changed a "
                    f"test the main line holds — {lost_text(lost)}. Put the main line's side back beside the story's "
                    f"(`git show {target}:<file>` shows it) and edit nothing else; the merge is committed, add a row "
                    f"for each file to integrate.md.{self.worktree_sentence()} "
                    f"{self.where_things_are(self.tool_in_flight, story)}")
        return (f"Apply the stage-integrate skill for backlog story {story}. Merging the main line into this story's "
                f"branch stopped on conflicts in: {conflicts}. Their list: {self.evidence(story)}/conflicts."
                f"{self.worktree_sentence()} {self.where_things_are(self.tool_in_flight, story)}")

    # --- the gate --------------------------------------------------------------------------------------------
    def owned(self, edge, window, story, code=None):
        """What is the person's is unchanged across a stage window — recorded at its start, compared at its end."""
        if not self.gate_installed():
            return 0
        return self.run([sys.executable, self.gate_path, "--owned", edge, window,
                         *([str(code)] if code is not None else []), "--story", story])[0]

    def owned_invoke(self, story, window, call):
        """The tool of an owned window. Stopped inside it — an interrupt, a signal that ends the tool — the window is
        closed before the run ends: its end journaled, the person's parts compared and the digest gone, so a person
        may change the story before the next run."""
        try:
            return call()
        except (Stopped, KeyboardInterrupt):
            self.journal_line(story, f"{utc()}\tstage-end\t{window}\texit=stopped")
            self.owned("end", window, story, 1)
            raise

    def fresh_window(self, story):
        """`--from <stage>`: a person names where the story starts, so a window a killed run left open is closed —
        its digest of the story is gone, and a story the person changed since reads as changed after its plan,
        never as changed under a stage."""
        self.profile()
        folder = evidence_dir(place("runs"), story)
        left = [name for name in (OWNED_DIGEST, WINDOW_DIGEST) if os.path.isfile(os.path.join(folder, name))]
        for name in left:
            with contextlib.suppress(OSError):
                os.remove(os.path.join(folder, name))
        if OWNED_DIGEST in left:
            self.journal_line(story, f"{utc()}\twindow-closed\t-\tby=--from")
            print(f"factory: --from closes the stage window an earlier run of {story} left open.")

    def record(self, flag, story, *more):
        """`--record-base` / `--record-changes <stage>`: what the story's diff is taken against, and what it changed."""
        if self.gate_installed():
            self.run([sys.executable, self.gate_path, flag, *more, "--story", story], quiet=True,
                     stdout=subprocess.DEVNULL)

    def gate(self, stage, story, gate_path=None):
        gate_path = gate_path or self.gate_path
        if not os.path.isfile(gate_path):
            err(f"factory: no gate at {gate_path} — run 'factory.sh setup'")
            return 2
        report = f"{self.runs}/{story}/.gate-{stage}.txt"
        journal = self.evidence(story)
        os.makedirs(f"{self.runs}/{story}", exist_ok=True)
        os.makedirs(journal, exist_ok=True)
        if self.guard_pipeline(stage, story):
            raise Stopped(7)
        flush()
        env = dict(os.environ, FACTORY_SUITES_KEY=self.suites_key)
        process = subprocess.Popen([sys.executable, gate_path, "--story", story, "--stage", stage, "--record-suites"],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        with open(report, "wb") as kept:
            for chunk in iter(lambda: process.stdout.readline(), b""):
                kept.write(chunk)
                sys.stdout.buffer.write(chunk)
                sys.stdout.flush()
        code = process.wait()
        # Every gate run is kept for the observer, with its verdict; only a refusal is kept where the next stage
        # reads it. 3 is not a refusal: every check passed and a human is asked (acceptance).
        shutil.copy(report, f"{journal}/gate-{stage}.{utc('%H%M%S')}.txt")
        if code in (0, 3):
            os.remove(report)
        return code

    def snapshot(self, story, label):
        """What the working tree looks like right now, so a later stage's claim about what it changed can be
        checked rather than believed."""
        journal = self.evidence(story)
        os.makedirs(journal, exist_ok=True)
        hashing = self.hashing()
        if not hashing:
            err("factory: no sha256 command found (shasum, sha256sum, openssl) — the tree snapshots")
            err("factory:   record file names without content, and factory-verify reports every check")
            err("factory:   that needs a digest as not observed. Install one of the three for full evidence.")
        lines = [NO_HASHES] if not hashing else []
        prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], capture_output=True, text=True).stdout.strip()
        status = subprocess.run(["git", "-c", "core.fileMode=false", "status", "--porcelain", "-z", "-uall", "--", "."],
                                capture_output=True).stdout.decode("utf-8", errors="replace")
        strip = lambda name: name[len(prefix):] if prefix and name.startswith(prefix) else name
        origin = ""
        for entry in status.split("\0"):
            if not entry:
                continue
            if origin:                          # -z writes a rename's source as the next entry
                if origin == "R":
                    lines.append(f"deleted  {strip(entry)}")
                origin = ""
                continue
            code, name = entry[:2], strip(entry[3:])
            if code[:1] in ("R", "C"):
                origin = code[:1]
            if "D" in code:
                lines.append(f"deleted  {name}")
                continue
            if not os.path.isfile(name):
                continue
            lines.append(f"{file_sha(name) if hashing else '-'}  {name}")
        with contextlib.suppress(OSError):
            with open(f"{journal}/tree-{label}.txt", "w", encoding="utf-8", newline="\n") as handle:
                handle.write("".join(line + "\n" for line in lines))

    def adopt_gate(self, story, tool, dry):
        """Every scenario on a green test, the judge's pass, a break for every test the adoption wrote: passed, it
        delivers the story; refused, the test stage runs again, one round counted."""
        print("── gate adopt")
        if dry:
            return 0
        if self.gate("adopt", story) == 0:
            if os.environ.get("FACTORY_HOME"):
                return self.integrate_story(story, tool, dry)
            print(f"factory: story {story} is delivered (adopted: checked, nothing built).")
            return 0
        if self.environment_refused("adopt", story):
            return 1
        rounds = self.bump_rounds(story)
        if rounds >= 3:
            err(f"factory: gate 'adopt' refused in round {rounds} — three rounds did not converge. needs-human.")
            return 1
        err(f"factory: gate 'adopt' refused — round {rounds} runs the test stage again with the gate's report.")
        return self.run_stages(story, tool, "test", dry)

    # --- the budget before a dispatch ------------------------------------------------------------------------
    def used_tokens(self, story):
        try:
            self.profile()
            runs = place("runs")
            return sum(tokens_of(entry) for s in run_stories(runs) if s == story for entry in journal_usage(runs, s).values())
        except (OSError, ValueError, GateError):
            return 0

    def may_dispatch(self, story, what, count=1):
        """The claim renewed, the story's budget and the cap on stages checked before an invocation, never after.
        None when it may run, else the exit code (5 the checkout is gone, 4 a limit)."""
        self.checkpoint()
        if not self.renew():
            err(f"factory: the checkout was taken over by another worker before {what} — stopping.")
            return 5
        if self.story_budget and self.used_tokens(story) >= self.story_budget:
            return "budget"
        if self.max_stages and self.invocations + count - 1 >= self.max_stages:
            return "stages"
        return None

    def window(self, story, tool, window, stages, prompt):
        """One shared process — the builder or the verifier — from its snapshot to its usage line; the tool's exit
        code, or 7 when a person's file changed in it."""
        raw = f"{self.evidence(story)}/{window}.{utc('%H%M%S')}.out"
        self.record("--record-base", story)
        self.snapshot(story, f"before-{window}")
        self.owned("start", window, story)
        tool = self.tool_for(window, tool)
        self.journal_line(story, f"{utc()}\tstage-start\t{window}\ttool={tool}{self.effort_field(tool, window)}"
                                 f"\tstages={','.join(stages)}")
        began = time.time()
        invoked = self.owned_invoke(story, window, lambda: self.invoke(tool, prompt, raw, window, story))
        self.record_usage(story, window, tool, raw, int(time.time() - began))
        self.journal_line(story, f"{utc()}\tstage-end\t{window}\texit={self.exit_field(invoked)}")
        # What the window changed is recorded however it ended: a file a stage made before the tool failed or a signal
        # stopped it is the story's all the same, and only `stages-made.txt` takes an untracked file into its commit.
        self.snapshot(story, f"after-{window}")
        self.record("--record-changes", story, window)
        # The window closes before a signal that arrived ends the run: the person may change the story before the next.
        if self.owned("end", window, story, invoked) != 0:
            return 7
        self.checkpoint()
        if invoked != 0:
            err("factory: the tool exited non-zero during the shared stages.")
            return 1
        return 0

    # --- the shared processes ----------------------------------------------------------------------------------
    def budget_note(self, story, what):
        err(f"factory: story {story} has reached its --story-budget {self.story_budget} — {what} are not dispatched.")
        return 4

    def run_shared_builder(self, story, tool, start, dry, kind="story"):
        """Plan to tidy in one tool process, so each stage builds on what the one before read. The process runs
        each stage's gate itself; the runner checks, not believes: the red proof must exist and the gates after
        it run again here."""
        tool = self.tool_for("builder", tool)
        stages, on = [], False
        for st in SHARED_WINDOWS["builder"]:
            on = on or st == start
            if self.kind_runs(kind, st) and on:
                stages.append(st)
        if not stages:
            return 0
        prompt = (f"Carry out these stages of the delivery pipeline for backlog story {story}, one after another, in "
                  f"this one session: {', '.join(f'stage-{s}' for s in stages)}. The gate: "
                  f"`{self.py} {self.gate_rel} --story {story} --stage <stage> --brief`; the skeletons: "
                  f"`{self.py} {self.cli_rel()} --files-skeleton {story} <stage>`, "
                  f"`{self.py} {self.cli_rel()} --plan-skeleton {story}`. {self.where_things_are(tool, story)}")
        prompt += self.guard_sentence()
        if self.back_to(story, "build") == "test":
            prompt += f" The build stage sent the story back: {self.runs}/{story}/build.md."
        if "test" in stages:
            prompt += self.red_stale_sentence(story)
        for refused in stages:
            if os.path.isfile(f"{self.runs}/{story}/.gate-{refused}.txt"):
                prompt += f" The gate refused stage {refused} before: {self.runs}/{story}/.gate-{refused}.txt."
        prompt += self.later_refusals(story, stages[-1], f"stage {start}")
        if os.path.isfile(f"{self.runs}/{story}/judge.md") and self.verdict_of(story) == "changes-requested":
            prompt += f" The judge asked for changes: {self.runs}/{story}/judge.md."
        print(f"── stage {'+'.join(stages)}  (tool: {tool}, one shared context)")
        if dry:
            self.dry_lines(tool, prompt, "builder")
            return 0
        refused = self.may_dispatch(story, "the shared stages")
        if refused == "budget":
            return self.budget_note(story, "the shared stages")
        if refused == "stages":
            err(f"factory: --max-stages {self.max_stages} reached before the shared stages of {story}.")
            return 4
        if refused:
            return refused
        code = self.window(story, tool, "builder", stages, prompt)
        if code:
            return code
        # A `back: test` the session already acted on is no round: tidy.md newer than build.md says it repaired the
        # test, built again and tidied — the re-checked gates below decide.
        repaired = "tidy" in stages and newer(f"{self.runs}/{story}/tidy.md", f"{self.runs}/{story}/build.md")
        sent_back = "build" in stages and self.back_to(story, "build") == "test"
        if sent_back and repaired:
            print("factory: build.md names a defect in a test's own code that the shared session repaired before tidy "
                  "— the gates re-check it.")
        if sent_back and not repaired:
            rounds = self.bump_rounds(story)
            if rounds >= 3:
                err(f"factory: the build stage sent the story back in round {rounds} — three rounds did not converge. "
                    "needs-human.")
                return 1
            err(f"factory: the build stage found a defect in a test's own code — round {rounds} goes back to the test stage.")
            self.nested_code = self.run_stages(story, tool, "test", dry)
            return 99
        for st in stages:
            artefact = self.artefact(story, st)
            if not os.path.isfile(artefact):
                err(f"factory: the shared stages produced no {artefact} — stage '{st}' is not finished.")
                return 1
            if self.asks_human(artefact):
                return self.stopped_for_human(artefact, st, story)
        # Checked, not believed: a story's tests were seen red; a journey's and an adoption's are green at their
        # test gate, so that gate runs again here.
        for st in stages:
            if not (STAGE[st].in_order and STAGE[st].tested and not STAGE[st].suite):
                continue
            if kind != "story":
                print(f"── gate {st}  (re-checked by the runner)")
                if self.gate(st, story) != 0:
                    err(f"factory: the runner's re-check of gate '{st}' refused the shared stages' work.")
                    return 1
            elif not os.path.isfile(f"{self.evidence(story)}/.tests-red") \
                    or not os.path.getsize(f"{self.evidence(story)}/.tests-red"):
                err(f"factory: the shared stages left no red proof ({self.evidence(story)}/.tests-red) — the {st} "
                    f"gate never saw the tests fail.")
                return 1
        for st in stages:
            if not STAGE[st].post_gated or (STAGE[st].tested and not STAGE[st].suite):
                continue
            print(f"── gate {st}  (re-checked by the runner)")
            if self.gate(st, story) != 0:
                if self.environment_refused(st, story):
                    return 1
                rounds = self.bump_rounds(story)
                if rounds >= 3:
                    err(f"factory: the runner's re-check of gate '{st}' refused in round {rounds} — three rounds did "
                        "not converge. needs-human.")
                    return 1
                err(f"factory: the runner's re-check of gate '{st}' refused — round {rounds} runs the shared stages "
                    f"again from '{st}' with the gate's report.")
                self.nested_code = self.run_stages(story, tool, st, dry)
                return 99
        return 0

    def run_reviews(self, story, tool, dry, kind="story"):
        """One tool process per perspective, started at once, each writing reviews/<perspective>.md; the judge then
        converges from the files. An adoption reviews no change and gets none."""
        if kind == "adopt":
            return 0
        self.profile()
        rows = [(name, carrier) for name, carrier in perspectives_of(read_profile(resolve_profile(None, os.getcwd())))
                if name]
        if not rows:
            return 0
        names = [row[0] for row in rows]
        carriers = [row[1] for row in rows]
        folder = f"{self.runs}/{story}/reviews"
        print(f"   reviews: {', '.join(names)} — one process each, at once; the judge converges from "
              "reviews/<perspective>.md")
        prompts = [(f"Review the change of backlog story {story} from the {name} perspective: apply the `{carrier}` "
                    f"skill to the diff {self.evidence(story)}/story.diff, as *A review the runner started* in the "
                    f"rules every stage holds to says. Its input beside the diff: the story and its epic (epic.md "
                    f"beside it), {self.runs}/{story}/plan.md, tests.md and build.md, and the product and technical "
                    f"description. Your report: {folder}/{name}.md. "
                    f"{self.where_things_are(self.tool_for(f'review:{name}', tool), story)}")
                   for name, carrier in zip(names, carriers)]
        if dry:
            for name, prompt in zip(names, prompts):
                print(f"   would run (review:{name}): {prompt}")
            return 0
        refused = self.may_dispatch(story, "the reviews", count=len(names))
        if refused == "budget":
            return self.budget_note(story, "the reviews")
        if refused == "stages":
            err(f"factory: --max-stages {self.max_stages} reached before the reviews of {story} ({len(names)} process(es)).")
            return 4
        if refused:
            return refused
        os.makedirs(folder, exist_ok=True)
        os.makedirs(self.evidence(story), exist_ok=True)
        for old in glob.glob(f"{folder}/*.md"):           # a repeat round reviews today's change, never last round's
            os.remove(old)
        began = time.time()
        raws = {}
        used = {name: self.tool_for(f"review:{name}", tool) for name in names}
        for name in names:
            self.journal_line(story, f"{utc()}\tstage-start\treview:{name}\ttool={used[name]}"
                                     f"{self.effort_field(used[name], f'review:{name}')}")
            raws[name] = f"{self.evidence(story)}/review-{name}.{utc('%H%M%S')}.out"
        codes = {}
        threads = [threading.Thread(target=lambda n=name, p=prompt: codes.__setitem__(
                       n, self.invoke(used[n], p, raws[n], f"review:{n}", story, count=False)))
                   for name, prompt in zip(names, prompts)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.invocations += len(names)
        seconds = int(time.time() - began)
        for name in names:
            self.record_usage(story, f"review:{name}", used[name], raws[name], seconds)
            self.journal_line(story, f"{utc()}\tstage-end\treview:{name}\texit={self.exit_field(codes.get(name, 1))}")
            if not os.path.isfile(f"{folder}/{name}.md"):
                err(f"factory: the {name} reviewer left no {folder}/{name}.md — the judge runs that pass itself and says so.")
        self.checkpoint()
        return 0

    def judged(self, story, tool, dry, kind):
        """The judge's verdict decides what comes next — read from its file, never assumed. None to go on."""
        verdict = self.verdict_of(story)
        if verdict == "pass":
            print("factory: judge verdict 'pass'.")
            return None
        if verdict == "changes-requested":
            rounds = self.bump_rounds(story)
            if rounds >= 3:
                err(f"factory: judge verdict 'changes-requested' in round {rounds} — three rounds did not converge. "
                    "needs-human.")
                return 1
            back = self.back_for(kind, self.back_to(story) or "build")
            err(f"factory: judge verdict 'changes-requested' — round {rounds} goes back to the {back} stage.")
            return self.run_stages(story, tool, back, dry)
        if verdict == "story-conflict":
            err("factory: judge verdict 'story-conflict' — the story or the plan is wrong. This never goes back to the "
                f"build stage. needs-human: read {self.runs}/{story}/judge.md.")
            return 1
        if not verdict:
            err(f"factory: {self.runs}/{story}/judge.md carries no 'verdict:' line — the judge stage is not finished.")
            return 1
        err(f"factory: judge verdict '{verdict}' is not one of pass|changes-requested|story-conflict.")
        return 1

    def accepting(self, story):
        err(f"factory: story {story} waits for a human's acceptance — answer it with /factory-decisions;")
        err("factory:   the story holds the checkout until then.")
        return 3

    def run_shared_verifier(self, story, tool, dry, kind="story"):
        """Judge and document in one tool process — never one process with the builder: the judge's independence
        from the builder is the point of the split."""
        tool = self.tool_for("verifier", tool)
        stages = [st for st in SHARED_WINDOWS["verifier"] if self.kind_runs(kind, st)]
        document = (f" The skeleton: `{self.py} {self.cli_rel()} --document-skeleton {story}`; the document gate: "
                    f"`{self.py} {self.gate_rel} --story {story} --stage document --brief`.") if kind != "adopt" else ""
        prompt = (f"Carry out these stages of the delivery pipeline for backlog story {story}, one after another, in "
                  f"this one session: {', '.join(f'stage-{s}' for s in stages)}.{document} "
                  f"{self.where_things_are(tool, story)}")
        print(f"── stage {'+'.join(stages)}  (tool: {tool}, one shared context)")
        if dry:
            self.dry_lines(tool, prompt, "verifier")
            return 0
        refused = self.may_dispatch(story, "the shared stages")
        if refused == "budget":
            return self.budget_note(story, "the shared stages")
        if refused == "stages":
            err(f"factory: --max-stages {self.max_stages} reached before the shared stages of {story}.")
            return 4
        if refused:
            return refused
        judge = f"{self.runs}/{story}/judge.md"
        if os.path.isfile(judge):
            os.replace(judge, f"{self.runs}/{story}/.judge-previous.md")
        code = self.window(story, tool, "verifier", stages, prompt)
        if code:
            return code
        if not os.path.isfile(judge):
            err(f"factory: the shared stages produced no {judge} — stage 'judge' is not finished.")
            return 1
        if self.asks_human(judge):
            return self.stopped_for_human(judge, "judge", story)
        code = self.judged(story, tool, dry, kind)
        if code is not None:
            return code
        if self.kind_runs(kind, "adopt"):
            return self.adopt_gate(story, tool, dry)
        artefact = f"{self.runs}/{story}/document.md"
        if not os.path.isfile(artefact):
            err(f"factory: the shared stages produced no {artefact} — stage 'document' is not finished.")
            return 1
        if self.asks_human(artefact):
            return self.stopped_for_human(artefact, "document", story)
        print("── gate document  (re-checked by the runner)")
        gate_code = self.gate("document", story)
        if gate_code == 3:
            return self.accepting(story)
        if gate_code != 0:
            if self.environment_refused("document", story):
                return 1
            rounds = self.bump_rounds(story)
            if rounds >= 3:
                err(f"factory: gate 'document' refused in round {rounds} — three rounds did not converge. needs-human.")
                return 1
            again = self.refused_from(story, "document")
            err(f"factory: gate 'document' refused — round {rounds} runs stage '{again}' again with the gate's report.")
            return self.run_stages(story, tool, again, dry)
        return 0

    # --- a story's stages ----------------------------------------------------------------------------------------
    def run_stages(self, story, tool, start=None, dry=False):
        """The story's stages from <start> on, in the checkout it is called in."""
        start = start or STAGE_ORDER[0]
        waiting = self.open_decisions(story)
        if waiting:
            err(f"factory: story {story} waits for a decision — no stage runs until it is answered:")
            for record in waiting.split():
                err(f"factory:   {record}")
            err("factory:   answer under '## Answer' with answer:, by: and at:, then run the stage that asked (--from <stage>).")
            return 3
        kind = self.kind_of(story)
        # Every gate passed in the story's worktree: only the integration is left, and it delivers the story; an
        # adopted story whose judge passed: only the adopt gate.
        if start == "integrate":
            return self.integrate_story(story, tool, dry)
        if start == "adopt":
            return self.adopt_gate(story, tool, dry)
        start = self.red_proof_start(story, kind, start, dry)
        started, ran, built = False, [], False
        for stage in STAGE_ORDER:
            started = started or stage == start
            if not started:
                continue
            if not dry and (stage == start or not (self.shared_builder and STAGE[stage].window == "builder")):
                self.between_stages(story, tool)
            row = STAGE[stage]
            if not self.kind_runs(kind, stage):
                why = {"journey": "a journey builds nothing", "adopt": "an adopted story is not built",
                       "task": "a task has no criterion to test — the existing suite is its evidence"}.get(
                    kind, f"a {kind} story does not run it")
                print(f"── stage {stage}  (skipped: {why})")
                continue
            if row.gated and not row.post_gated:
                print(f"── gate {stage}")
                if self.gate(stage, story) != 0:
                    err(f"factory: gate '{stage}' refused the story. Fix it before the stage runs.")
                    return 1
            if self.shared_builder and row.window == "builder":
                if not built:
                    code = self.run_shared_builder(story, tool, stage, dry, kind)
                    if code == 99:                  # a refused re-check ran the story again from there
                        return self.nested_code
                    if code != 0:
                        return code
                    built = True
                ran.append(stage)
                continue
            # The reviews come before the judge: one process per perspective, at once.
            if stage == "judge":
                code = self.run_reviews(story, tool, dry, kind)
                if code != 0:
                    return code
            # The verifier runs where the judge would; resumed at the document stage alone it runs in its own context.
            if self.shared_verifier and stage == SHARED_WINDOWS["verifier"][0]:
                code = self.run_shared_verifier(story, tool, dry, kind)
                if code != 0:
                    return code
                ran += [st for st in SHARED_WINDOWS["verifier"] if self.kind_runs(kind, st)]
                break
            artefact = self.artefact(story, stage)
            # Resumed at a gated stage whose file exists: the gate decides first, on today's tree.
            if self.gate_first and stage == start and not dry and stage != "document" and row.post_gated \
                    and os.path.isfile(artefact):
                self.gate_first = False
                print(f"── gate {stage}  (the file exists — checked before the stage is invoked)")
                if self.quiet_gate(stage, story) == 0:
                    print(f"factory: {artefact} already holds — stage '{stage}' is not invoked again.")
                    ran.append(stage)
                    continue
                if self.environment_refused(stage, story):
                    return 1
            self.gate_first = False
            # A resumed story whose document file exists and was never refused: its gate decides first.
            if stage == "document" and not dry and os.path.isfile(artefact) \
                    and not os.path.isfile(f"{self.runs}/{story}/.gate-document.txt") and not self.delivered(story):
                print("── gate document  (the file exists — checked before the stage is invoked)")
                if self.quiet_gate("document", story) == 0:
                    print(f"factory: {artefact} already holds — the document stage is not invoked again.")
                    ran.append("document")
                    break
            unit_tool = self.tool_for(stage, tool)      # the run's tool stays `tool`: every stage resolves its own
            print(f"── stage {stage}  (tool: {unit_tool}, fresh context)")
            self.tool_in_flight = unit_tool
            if dry:
                self.dry_lines(unit_tool, self.prompt_for(stage, story), stage)
            else:
                code = self.run_one(story, tool, stage, dry)
                if code is not None:
                    return code
            if row.post_gated:
                print(f"── gate {stage}")
                gate_code = 0 if dry else self.gate(stage, story)
                if gate_code == 3:
                    return self.accepting(story)
                if gate_code != 0:
                    if self.environment_refused(stage, story):
                        return 1
                    rounds = self.bump_rounds(story)
                    if rounds >= 3:
                        err(f"factory: gate '{stage}' refused in round {rounds} — three rounds did not converge. needs-human.")
                        return 1
                    again = self.refused_from(story, stage)
                    err(f"factory: gate '{stage}' refused — round {rounds} runs stage '{again}' again with the gate's report.")
                    return self.run_stages(story, tool, again, dry)
            ran.append(stage)
            if stage == "judge" and not dry:
                code = self.judged(story, tool, dry, kind)
                if code is not None:
                    return code
                if self.kind_runs(kind, "adopt"):
                    return self.adopt_gate(story, tool, dry)
        # What ran, not what the script knows how to run.
        print(f"factory: story {story} ran through {','.join(ran) or 'nothing'}.")
        if os.environ.get("FACTORY_HOME") and not dry and self.start_stage(story) == "integrate":
            return self.integrate_story(story, tool, dry)
        return 0

    def red_proof_start(self, story, kind, start, dry):
        """Where a story whose red proof went stale starts: a gate that holds the red proof (build, tidy) refuses a
        test changed after it was seen failing, and only the test stage can record it again — so the story goes to
        its test stage, as a step of the runner, never as a stage's question and never as a round. A merge of the
        main line into the story's branch is what changes a test that way (the resumed story's merge, the integrate
        stage's resolution, the integration a gate refused afterwards); the test stage records the tests as they now
        are, a break where the code already meets them."""
        if dry or start not in STAGE or not STAGE[start].lists or STAGE[start].red or not self.kind_runs(kind, "test"):
            return start
        self.profile()
        moved = stale_red_proof(os.getcwd(), place("runs"), story, start)
        if not moved:
            self.red_stale.pop(story, None)
            return start
        self.red_stale[story] = moved
        self.journal_line(story, f"{utc()}\tred-stale\ttest\tfrom={start}\ttests={len(moved)}")
        print(f"factory: {', '.join(moved)} changed after the test stage saw it fail — the red proof is about the "
              f"earlier version, so the story goes to its test stage to record it on the files as they are, then "
              f"'{start}' runs again.")
        return "test"

    def red_stale_sentence(self, story):
        moved = self.red_stale.get(story)
        if not moved:
            return ""
        return (f" The story's tests changed after the test stage saw them fail — the main line was merged into the "
                f"story's branch: {', '.join(moved)}. Record each as it now is and change nothing it asserts: red "
                f"where the code before this story fails it, else its break under {self.runs}/{story}/breaks/ "
                f"(`<Class>--<method>.patch`, the smallest change to the production code that turns it red).")

    def quiet_gate(self, stage, story):
        """A gate whose lines nobody reads — the runner asks it only whether a file already holds."""
        with open(os.devnull, "w") as null:
            saved = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = null
            try:
                return self.gate(stage, story)
            finally:
                sys.stdout, sys.stderr = saved

    def run_one(self, story, tool, stage, dry):
        """One stage in a process of its own; None when it ran and its file stands, else the run's exit code."""
        self.checkpoint()
        if not self.renew():
            err(f"factory: the checkout was taken over by another worker before stage '{stage}' — stopping.")
            return 5
        if self.story_budget and self.used_tokens(story) >= self.story_budget:
            err(f"factory: story {story} has used {self.used_tokens(story)} tokens of its")
            err(f"factory:   --story-budget {self.story_budget} — stage '{stage}' is not dispatched; the work so far stays.")
            return 4
        if self.max_stages and self.invocations >= self.max_stages:
            err(f"factory: --max-stages {self.max_stages} reached before stage '{stage}' of {story} — nothing more is")
            err("factory:   dispatched; the work so far stays as it is and the next run continues from it.")
            return 4
        stage_started = utc()
        # The previous verdict is an input to the next one, not something to overwrite.
        if stage == "judge" and os.path.isfile(f"{self.runs}/{story}/judge.md"):
            os.replace(f"{self.runs}/{story}/judge.md", f"{self.runs}/{story}/.judge-previous.md")
        self.record("--record-base", story)
        artefact = self.artefact(story, stage)
        evidence = self.evidence(story)
        had_file = os.path.isfile(artefact)
        # The plan's and the document's file start as the pipeline's skeleton; a skeleton the pipeline wrote is kept
        # aside, so a stage that left it untouched produced nothing. A file an earlier pass left is no skeleton.
        skeleton = {"document": "--document-skeleton", "plan": "--plan-skeleton"}.get(stage)
        if skeleton and self.gate_installed():
            self.cli(skeleton, story)
        with contextlib.suppress(OSError):
            os.remove(f"{evidence}/{stage}.skeleton")
        if not had_file and skeleton and os.path.isfile(artefact):
            os.makedirs(evidence, exist_ok=True)
            shutil.copy(artefact, f"{evidence}/{stage}.skeleton")
        self.snapshot(story, f"before-{stage}")
        tool = self.tool_for(stage, tool)
        flags, note = self.model_choice(tool, stage)
        requested = self.model_key(tool, stage)
        model_fields = (f"\tmodel_requested={requested}" if requested else "") + \
            (f"\tmodel_applied=no ({note})" if note else "")
        if note:
            print(f"factory: model.{tool}.{stage}: {requested} — {note}")
        self.owned("start", stage, story)
        self.journal_line(story, f"{stage_started}\tstage-start\t{stage}\ttool={tool}{model_fields}"
                                 f"{self.effort_field(tool, stage)}")
        raw = f"{evidence}/{stage}.{utc('%H%M%S')}.out"
        began = time.time()
        invoked = self.owned_invoke(story, stage, lambda: self.invoke(tool, self.prompt_for(stage, story), raw, stage, story))
        self.record_usage(story, stage, tool, raw, int(time.time() - began))
        # recorded however the stage ended, as a shared window's: the files it made reach the story's commit
        self.snapshot(story, f"after-{stage}")
        self.record("--record-changes", story, stage)
        if self.owned("end", stage, story, invoked) != 0:
            self.journal_line(story, f"{utc()}\tstage-end\t{stage}\texit=owned")
            return 7
        if invoked != 0:
            self.journal_line(story, f"{utc()}\tstage-end\t{stage}\texit={self.exit_field(invoked)}")
            self.checkpoint()
            err(f"factory: the tool exited non-zero during stage '{stage}'.")
            return 1
        self.journal_line(story, f"{utc()}\tstage-end\t{stage}\texit=0")
        self.checkpoint()
        if not os.path.isfile(artefact):
            err(f"factory: stage '{stage}' produced no {artefact} — a stage is finished when its file exists.")
            return 1
        kept = f"{evidence}/{stage}.skeleton"
        if os.path.isfile(kept) and read_bytes(kept) == read_bytes(artefact):
            err(f"factory: stage '{stage}' produced no {artefact} beyond the pipeline's skeleton — a stage is finished "
                "when it wrote its file.")
            return 1
        # The build stage found a defect in a test's own code: the round goes to the test stage, no human is asked.
        sent_back = self.back_to(story, stage) if stage == "build" else ""
        if sent_back:
            rounds = self.bump_rounds(story)
            if rounds >= 3:
                err(f"factory: the build stage sent the story back in round {rounds} — three rounds did not converge. "
                    "needs-human.")
                return 1
            err(f"factory: the build stage found a defect in a test's own code — round {rounds} goes back to the "
                f"{sent_back} stage.")
            return self.run_stages(story, tool, sent_back, dry)
        # A stage that ends with a needs-human section has stopped, whatever its file otherwise says.
        if self.asks_human(artefact):
            return self.stopped_for_human(artefact, stage, story)
        return None

    # --- a story in its worktree (WP-92) -------------------------------------------------------------------------
    def in_home(self, *args, merge=True):
        """A cli call made in the main checkout, as a person's would be there: (exit code, its lines)."""
        return self.cli(*args, merge=merge, quiet=False, cwd=os.environ.get("FACTORY_HOME") or self.home,
                        env=self.home_env())

    def link_worktree(self, story):
        self.run([sys.executable, self.cli_path, "--worktree-link", story], cwd=os.environ.get("FACTORY_HOME") or self.home,
                 env=self.home_env())

    def resolve_merge(self, story, tool, out, lost=None):
        """A merge of the main line into the story that stopped on conflicts (`conflict: <path>` lines in <out>): the
        stage-integrate agent resolves them in the worktree, then the merge is committed and squashed. A resolution
        that dropped what the main line added to a test (#151) goes back to the same stage, naming the lines, at most
        twice — never to a person, and never to the story's own stages, whose gates would call it the story's change.
        `lost` starts with such a repair (the integrate gate refused `main-tests`). None when it holds, else the run's
        exit code."""
        conflicts = "".join(line[len("conflict: "):] + " " for line in out.split("\n") if line.startswith("conflict: "))
        for attempt in (1, 2, 3):
            stopped = self.integrate_stage(story, tool, conflicts, lost)
            if stopped is not None:
                return stopped
            lost = main_tests_lost(self.pwd, self.runs, story)
            if not lost:
                return None
            if attempt < 3:
                print(f"factory: the resolution of {story} changed a test the main line holds — {lost_text(lost)}; "
                      f"back to the integrate stage (attempt {attempt + 1}).")
        err(f"factory: three resolutions of {story} kept dropping the main line's side of a test — {lost_text(lost)}. "
            f"needs-human: the worktree {self.pwd} holds the merge.")
        return 1

    def integrate_stage(self, story, tool, conflicts, lost=None):
        """One stage-integrate session — the conflicts, or a repair of a resolution that lost the main line's side of a
        test — then the profile's formatter and the merge committed and squashed. None when it is, else an exit code."""
        what = f"the resolution lost the main line's side of {', '.join(rel for rel, _ in lost)}" if lost \
            else f"the merge stopped on: {conflicts}"
        print(f"── stage integrate  (tool: {tool}, fresh context — {what})")
        self.link_worktree(story)
        self.tool_in_flight = tool
        raw = f"{self.evidence(story)}/integrate.{utc('%H%M%S')}.out"
        began = time.time()
        self.owned("start", "integrate", story)
        tool = self.tool_for("integrate", tool)
        self.journal_line(story, f"{utc()}\tstage-start\tintegrate\ttool={tool}")
        code = self.owned_invoke(story, "integrate", lambda: self.invoke(
            tool, self.integrate_prompt(story, conflicts, lost), raw, "integrate", story))
        self.record_usage(story, "integrate", tool, raw, int(time.time() - began))
        self.journal_line(story, f"{utc()}\tstage-end\tintegrate\texit={self.exit_field(code)}")
        if self.owned("end", "integrate", story, code) != 0:
            return 7
        self.checkpoint()
        record = f"{self.runs}/{story}/integrate.md"
        if os.path.isfile(record) and self.asks_human(record):
            self.drop_lock()
            return self.stopped_for_human(record, "integrate", story)
        # The formatter is mechanical: what the resolution left for it is corrected here, not spent as a round.
        fix = self.profile().get("formatFix", "").strip()
        if fix:
            print(f"── formatFix  (the profile's, over what the integrate stage resolved: {fix})")
            with self.step(story, "format"):
                fixed, said = run_command(fix, self.pwd)
            if fixed != 0:
                err(f"factory: the profile's formatFix exited {fixed} — the gate's format check decides: "
                    f"{said.strip()[-300:]}")
        code, out = self.in_home("--integrate-finish", story)
        print(out)
        if code != 0:
            err(f"factory: the conflicts of {story} are not resolved — needs-human: the worktree {self.pwd} holds the "
                "merge.")
            return 1
        return None

    def integrate_story(self, story, tool, dry):
        """Delivered is the integration: the main line merged into the story (a stage-integrate agent where git stops
        on a conflict), squashed, the gate once more on that tree, the main checkout fast-forwarded — under the lock,
        journaled as the runner's own step. A refusal on the main line runs the build stage again, after the step."""
        print("── integrate")
        if dry:
            print(f"   would merge {story}'s branch with the main line and fast-forward the main checkout")
            return 0
        with self.step(story, "integrate"):
            code = self.integrate_attempts(story, tool)
        if code != "round":
            return code
        # the integration took the links down; the build stage works with them again — and document.md is an
        # earlier pass's: the document stage writes it for the story as it now is, or its gate passes it as it is
        self.take_lock()
        try:
            self.link_worktree(story)
        finally:
            self.drop_lock()
        self.journal_line(story, f"{utc()}\toutdated\tdocument.md\tby=integrate")
        return self.run_stages(story, tool, "build", dry)

    def integrate_attempts(self, story, tool):
        """The integration, again where the main line moved meanwhile: an exit code, or "round" where the gate
        refused the story on the main line and the build stage runs again."""
        home = os.environ.get("FACTORY_HOME") or self.home
        attempt, repairs = 0, 0
        while attempt < 3:
            attempt += 1
            self.take_lock()
            try:
                code, out = self.in_home("--integrate-prepare", story)
                print(out)
                if code == 3:
                    stopped = self.resolve_merge(story, tool, out)
                    if stopped is not None:
                        return stopped
                elif code != 0:
                    err(f"factory: {story} could not be merged with the main line — the worktree {self.pwd} keeps it as it was.")
                    return 1
                print("── gate integrate")
                code = self.gate("integrate", story, gate_path=f"{home}/{self.gate_rel}")
            finally:
                self.drop_lock()
            if code == 0:
                if claim_config_here(self.home):
                    print(f"factory: story {story} is delivered on its branch and published — a person merges it.")
                else:
                    print(f"factory: story {story} is integrated and delivered.")
                return 0
            report = f"{self.runs}/{story}/.gate-integrate.txt"
            # the checks that failed — not the report's closing `gate:fail story <id> stage <stage>` line
            fails = [line for line in (read_text(report).splitlines() if os.path.isfile(report) else [])
                     if line.startswith("gate:fail ") and not line.startswith("gate:fail story ")]
            if fails and all(line.startswith("gate:fail moved") for line in fails):
                print(f"factory: the main line moved on while {story} was merged — merged again (attempt {attempt + 1}).")
                continue
            # #151: the resolution dropped what the main line added to a test — the integrate stage's to put back
            if any(line.startswith("gate:fail main-tests") for line in fails) and repairs < 2:
                lost = main_tests_lost(self.pwd, self.runs, story)
                if lost:
                    repairs += 1
                    attempt -= 1
                    print(f"factory: the integrate gate named a test of the main line the resolution changed — "
                          f"back to the integrate stage, not a round ({lost_text(lost)}).")
                    self.take_lock()
                    try:
                        stopped = self.resolve_merge(story, tool, "", lost)
                    finally:
                        self.drop_lock()
                    if stopped is not None:
                        return stopped
                    continue
            if any(line.startswith("gate:fail checkout") for line in fails):
                err(f"factory: the main checkout could not take {story} — see {report}; then: factory.sh run --story "
                    f"{story} --from integrate")
                return 1
            if self.environment_refused("integrate", story):
                return 1
            rounds = self.bump_rounds(story)
            if rounds >= 3:
                err(f"factory: gate 'integrate' refused in round {rounds} — three rounds did not converge. needs-human.")
                return 1
            err(f"factory: gate 'integrate' refused the story on the main line — round {rounds} runs the build stage "
                "again with the gate's report.")
            return "round"
        err(f"factory: the main line moved on three times while {story} was integrated — run it again.")
        return 1

    def run_story(self, story, tool, start, dry):
        """Every story in its worktree: made or brought up to date and linked, under the lock; the stages run in it
        with the run folder named absolutely and FACTORY_HOME naming this checkout; delivered, its worktree goes."""
        if dry:
            return self.run_stages(story, tool, start, dry)
        # Several factories on one backlog (WP-93): the story is claimed on the remote before anything runs —
        # another factory's claim skips it, a branch rule or an id collision stops for a person.
        if claim_config_here(self.home):
            code, out = self.cli("--claim-story", story, quiet=False)
            if out:
                print(out)
            if code == 3:
                return 0
            if code != 0:
                err(f"factory: {story} could not be claimed — needs-human (see above).")
                return 1
        # A story resumed in its worktree is merged with the main line here: the runner's own step, shown running.
        resumed = has_worktree(story, self.home)
        with self.step(story, "merge") if resumed else contextlib.nullcontext():
            self.take_lock()
            try:
                _, out = self.cli("--worktree-prepare", story, quiet=False)
            finally:
                self.drop_lock()
        wt = out.split("\n")[-1] if out else ""
        if wt.startswith("none"):
            print(f"factory: {story} runs in the checkout — {wt[len('none — '):] if wt.startswith('none — ') else wt}")
            return self.run_stages(story, tool, start, dry)
        if not wt:
            err(f"factory: no worktree could be made for {story} — nothing ran.")
            return 1
        print(f"factory: {story} works in its worktree, {wt[len(self.home) + 1:] if wt.startswith(self.home + '/') else wt}")
        self.profile()
        self.add_dirs = [f"{self.home}/{linked}" for linked in (self.runs_rel, place("epics"), place("discovery"))
                         if linked and os.path.isdir(f"{self.home}/{linked}")]
        self.read_dirs = [f"{self.home}/{linked}" for linked in
                          (".agents/factory", self.evidence_rel(), *TOOL_SKILL_DIRS, ".agents/skills")
                          if os.path.isdir(f"{self.home}/{linked}")]
        os.chdir(wt)
        self.pwd = wt
        os.environ["FACTORY_HOME"] = self.home
        self.runs = f"{self.home}/{self.runs_rel}"
        try:
            # Resumed onto a main line that changed what the story changes: the conflicts are resolved first, so the
            # next stage works on the main line as it is.
            code = self.resolve_merge(story, tool, out) if "\nconflict: " in "\n" + out else None
            if code is None:
                if "\nconflict: " in "\n" + out:
                    self.link_worktree(story)
                code = self.run_stages(story, tool, start, dry)
        finally:
            os.chdir(self.home)
            self.pwd = self.home
            os.environ.pop("FACTORY_HOME", None)
            self.runs = self.runs_rel
            self.add_dirs, self.read_dirs = [], []
            self.profile()
        if code == 0 and self.delivered(story):
            self.take_lock()
            try:
                self.run([sys.executable, self.cli_path, "--worktree-remove", story])
            finally:
                self.drop_lock()
        return code

    # --- requests (WP-91) --------------------------------------------------------------------------------------
    # A request is worked in a process of its own, `factory-cli.py --work-request <id>`, in the main checkout and under
    # this runner's claim: before the next story, between the stages of a running one (never one about that story), and
    # in a slot of its own in a parallel run. `run` and `stop` are the runner's own: a story to run next, the end.
    def requeue_orphans(self):
        """A request a factory left `running` when it ended — crashed, killed — is queued again at the next start:
        this runner holds the claim now, so nobody else works it."""
        self.profile()
        for request in list_requests():
            if request["state"] == "running" and request.get("worker") != self.worker:
                update_request(request, state="queued", worker=None, started=None)
                print(f"factory: request {request['id']} was left running by {request.get('worker') or 'a factory'} "
                      f"— queued again")

    def wake_waiting(self):
        """A waiting request whose records are all answered is queued again, with the answers to read."""
        self.profile()
        for request in list_requests():
            if request["state"] != "waiting":
                continue
            records = request_records(self.home, request["id"])
            if not records:                     # its record was removed by hand: it runs again and asks again
                update_request(request, state="queued", record_file=None)
                print(f"factory: request {request['id']} waited on a record that is gone — it runs again")
                continue
            if all(state in ("answered", "applied") for _p, _id, state in records):
                update_request(request, state="queued", record_file=None,
                               answered=" ".join(rid for _p, rid, _s in records))
                print(f"factory: request {request['id']} — its question is answered; it runs again")

    def next_request(self, busy=(), kinds=None):
        """The oldest queued request this runner may work now: of the kinds given (else every kind a skill works), and
        about no story in <busy>."""
        self.wake_waiting()
        for request in list_requests():
            if request["state"] != "queued" or request.get("kind") not in KIND:
                continue
            kind = KIND[request["kind"]]
            if (kinds is not None and kind.name not in kinds) or (kinds is None and not kind.skill):
                continue
            if stories_of(request) & set(busy):
                continue
            return request
        return None

    def take_stop_request(self):
        """A `stop` request ends this factory after the running stage: taken, journaled, gone. True when there was one."""
        request = self.next_request(kinds=("stop",))
        if not request:
            return False
        with contextlib.suppress(OSError):
            os.remove(request["path"])
        request_journal("request", "stop", request["id"], "-", f"by={request.get('by', '')}", "exit=0")
        print(f"factory: request {request['id']} — {request.get('by') or 'a person'} stops the factory; nothing more starts.")
        return True

    def request_argv(self, request, tool):
        argv = [sys.executable, self.cli_path, "--work-request", request["id"], "--tool", tool]
        return argv

    def request_env(self):
        env = self.home_env()
        env.update(FACTORY_RUNNER_WORKER=self.worker, FACTORY_RUNNER_PIPELINE_SHA=self.pipeline_sha,
                   FACTORY_RUNNER_PYTHON=self.py)
        return env

    def work_requests(self, tool, busy=()):
        """Every request a skill works that is not about a story in <busy>, one after another, each in its own process
        in the main checkout. A signal that arrived ends the loop between two of them."""
        if not self.gate_installed():
            return
        worked = set()
        while True:
            self.checkpoint()
            request = self.next_request(busy)
            if request is None or request["id"] in worked:
                return
            worked.add(request["id"])
            print(f"══ request {request['id']}  ({request['kind']} {target_text(request)}, by {request.get('by', '?')})")
            code, _ = self.run(self.request_argv(request, tool), cwd=self.home, env=self.request_env())
            self.request_ended(request, code)

    def request_ended(self, request, code):
        """After a request's process: one that ended without saying how — killed, a crash before its first line — is
        failed, so it is never taken again on its own."""
        if code in (0, 3):
            return
        if os.path.isfile(request["path"]):
            now = read_request(request["path"])
            if now["state"] in ("queued", "running") and (code in SIGNAL_EXITS.values() or code < 0):
                update_request(now, state="queued", worker=None, started=None)      # stopped, not failed: again next time
                err(f"factory: request {request['id']} was stopped — queued again for the next start.")
                return
            if now["state"] in ("queued", "running"):
                update_request(now, state="failed", worker=None,
                               error=f"its process ended with exit {code} before it said how")
        err(f"factory: request {request['id']} ended with exit {code} — `factory.sh requests` says why; the "
            "factory goes on.")

    def between_stages(self, story, tool):
        """Before a stage of a story the runner runs alone: a `stop` — the run ends here, as after a TERM, the story
        resumable —, then the requests that are not about it."""
        if self.options.child:
            return
        if self.take_stop_request():
            self.pending = 0
            self.checkpoint()
        self.work_requests(tool, busy=(story,))
        self.profile()

    def run_request_start(self, request):
        """(start stage or None, why not) — where a `run` request's story begins: the stage it names, else where its
        files say, as `run --story` decides it."""
        story, start = request["story"], request.get("from", "")
        if start:
            return start, ""
        self.profile()
        found = start_of(self.home, place("epics"), place("runs"), story, 1)
        if found is None:
            return None, f"no story {story}"
        state, start, detail = found
        if not start:
            return None, f"{story} is {state}" + (f" — {detail}" if detail else "")
        return start, ""

    def take_run_request(self, busy=()):
        """The oldest `run` request whose story is not running: (request, start) — its story starts next — or a failed
        request said and set aside. None when there is none."""
        while True:
            request = self.next_request(busy, kinds=("run",))
            if not request:
                return None
            start, why = self.run_request_start(request)
            if start:
                if request.get("from"):
                    self.reset_rounds(request["story"], start)
                    self.fresh_window(request["story"])
                with contextlib.suppress(OSError):
                    os.remove(request["path"])
                request_journal("request", "run", request["id"], request["story"], f"by={request.get('by', '')}",
                                f"from={start}")
                print(f"factory: request {request['id']} — {request.get('by') or 'a person'} runs {request['story']} "
                      f"from {start} now")
                return request, start
            update_request(request, state="failed", error=f"nothing runs: {why}")
            request_journal("request", "run", request["id"], request["story"], f"by={request.get('by', '')}",
                            "exit=1", why)
            err(f"factory: request {request['id']} — {why}; nothing runs.")

    def wait_or_wake(self, interval):
        """The watch's pause, cut short by a request: a person's press runs within seconds, not after the interval."""
        end = time.time() + interval
        while time.time() < end:
            self.sleep(min(2, max(0.1, end - time.time())))
            if os.path.isfile(self.stop_file):
                return
            with contextlib.suppress(OSError):
                if any(r["state"] == "queued" for r in list_requests()):
                    return

    # --- one request, in its own process ----------------------------------------------------------------------
    def request_skill(self, kind):
        """The skill a request's kind runs, as its prompt names it."""
        if kind.skill == "description":
            return ("the project's description skill — the skill whose description says it writes the project "
                    "description, `dca-describe` in a DCA project —")
        return f"the {kind.skill} skill"

    @staticmethod
    def request_arguments(request):
        """The arguments a session would give the skill for this request — the same words the cockpit sends."""
        kind, words, option = request["kind"], request.get("words", ""), request.get("option", "")
        story, record = request.get("story", ""), request.get("record", "")
        if kind in ("wish", "discover", "describe"):
            return words
        if kind == "release":
            return f"release {request.get('story') or request.get('epic')}"
        if kind in ("stories", "journey"):
            return f"{kind} {request['epic']}"
        if kind == "epic-from":
            return f"epic {request['proposal']} --from {request['report']}"
        if kind == "answer":
            given = option or words
            why = f" — rationale: {words}" if option and words else ""
            return f"{story + ' ' if story else ''}{record}: answer {given}{why}"
        if kind == "accept":
            return f"{story} {record}: answer accepted"
        if kind == "correct":
            code = f"{option}: " if option else ""
            return f"{story}{' ' + record if record else ''}: correction: {code}{words}"
        return words

    def request_prompt(self, request, tool):
        kind = KIND[request["kind"]]
        reference = next((f"{d}/factory-run/reference/requests.md" for d in self.skill_dirs(tool)
                          if os.path.isfile(f"{d}/factory-run/reference/requests.md")), "")
        if not reference:
            own = os.path.abspath(os.path.join(self.scripts, "..", "reference", "requests.md"))
            reference = own[len(self.pwd) + 1:] if own.startswith(self.pwd + "/") else own
        by = request.get("by") or "a person"
        topic_file = shown(project_record_path(request["id"], request["kind"]))
        lines = [
            f"Apply {self.request_skill(kind)} with the arguments: {self.request_arguments(request)}",
            f"This is request {request['id']} of the factory, written by {by} at {request.get('asked', '?')}. You run "
            f"headless: no person reads this session and nobody answers in it. The rules for a skill run for a request "
            f"are in {reference} — read them first.",
            f"In short: the request is {by}'s confirmation of what it names — write it as theirs (`by: {by}`), as the "
            f"skill would on their confirmation. Where the skill would ask the person and the files do not settle it, do "
            f"not guess and do not ask here: write the question as one decision record with `request: {request['id']}` "
            f"in its front matter and its file name without `.md` as its `id:` — beside the story it concerns, else as "
            f"{topic_file} — and end. The factory shows it "
            f"and runs this request again once it is answered. Start no stage and no `factory.sh run`, commit nothing: "
            f"the factory commits what this request wrote.",
            f"Now is {stamp_utc()} (UTC) — the time a field such as `created:` takes.",
        ]
        if kind.name == "wish":
            lines.append("A wish becomes a backlog item kept as a draft (`status: draft`): the person releases it.")
        if kind.name == "correct" and not request.get("option"):
            lines.append("The person named no reason code for the correction: where their words point to exactly one, "
                         "write that one; else ask it as a record whose options are the codes.")
        answered = request.get("answered", "")
        if answered:
            records = [shown(path) for path, rid, _s in request_records(self.home, request["id"])]
            lines.append(f"This request ran before and asked; its question is answered now ({answered}: "
                         f"{', '.join(records)}). Read the answer and go on from there — write nothing the answer and "
                         f"the request do not settle.")
        story = (request.get("story") or "").split()
        lines.append(self.where_things_are(tool, story[0] if len(story) == 1 else None)
                     + " For a request, also `bash .agents/factory/factory.sh` backlog, status, decisions, discover, "
                     "spec-delta and help.")
        return "\n\n".join(lines)

    def request_allowed(self):
        """A request's shell: a stage's, with the cli narrowed to the flags the dialog skills read and record with, and
        the runner's reading verbs — no flag and no verb that starts a run, a request, the factory or its page."""
        cli = f"Bash({self.py} .agents/factory/factory-cli.py:*)"
        heads = [head for head in self.allowed_commands().split(",") if head != cli]
        heads += [f"Bash({self.py} .agents/factory/factory-cli.py {flag}:*)" for flag in REQUEST_CLI_FLAGS]
        heads += [f"Bash(bash .agents/factory/factory.sh {verb}:*)"
                  for verb in ("backlog", "status", "decisions", "discover", "spec-delta", "help")]
        heads.append("Bash(date:*)")                # the backlog skill dates what it writes
        return ",".join(heads)

    def people_paths(self):
        """What a request may write and the factory commits — what a person writes and no code is
        (`people_places`, the same the commit hook takes as the backlog alone): (folders, files, never)."""
        self.profile()
        return people_places()

    def dirty_files(self):
        """{path: digest} of everything git sees changed or new in the main checkout, outside the factory's folder.
        A story's decision records count: a request's question and a person's answer are written there."""
        # not through `git()`, which strips the answer: the first entry's leading blank is its status column
        done = subprocess.run(["git", "status", "--porcelain", "-z", "--untracked-files=all", "--no-renames"],
                              cwd=self.home, capture_output=True, text=True, encoding="utf-8", errors="replace")
        found = {}
        if done.returncode != 0:
            return found
        for entry in done.stdout.split("\0"):
            if len(entry) < 4:
                continue
            path = entry[3:]
            if path.startswith((self.runs_rel.rstrip("/") + "/", evidence_rel() + "/", ".dca-factory/")):
                continue
            full = os.path.join(self.home, path)
            try:
                with open(full, "rb") as handle:
                    found[path] = hashlib.sha256(handle.read()).hexdigest()
            except OSError:
                found[path] = "deleted"
        return found

    def request_wrote(self, request, before):
        """What a request wrote so far — the people's paths it changed that were clean before, and what an earlier
        attempt of it wrote —, kept in its file when it fails or is interrupted: an attempt after it commits them as
        its own, never as a person's."""
        places = self.people_paths()
        after = self.dirty_files()
        new = {p for p, digest in after.items() if before.get(p) != digest and p not in before}
        own = set(str(request.get("wrote") or "").split())
        return " ".join(sorted(p for p in (new | own) & set(after) if in_places(p, places)))

    def commit_request(self, request, before):
        """What the request wrote, committed on its own: the paths it changed that were clean before — or that an
        earlier attempt of it wrote (`wrote:`) — and that are the backlog or the description. A path a person had
        changed before, or code, stays as it is and is named."""
        after = self.dirty_files()
        own = set(str(request.get("wrote") or "").split())
        changed = sorted(p for p, digest in after.items() if before.get(p) != digest or p in own)
        places = self.people_paths()
        mine = [p for p in changed if (p not in before or p in own) and in_places(p, places)]
        theirs = [p for p in changed if p in before and p not in own]
        stray = [p for p in changed if p not in before and p not in mine]
        if theirs:
            print(f"factory: request {request['id']} changed what was changed by hand before — left uncommitted: "
                  f"{', '.join(theirs[:8])}")
        if stray:
            err(f"factory: request {request['id']} changed what is neither backlog nor description (code, the spec) — "
                f"left uncommitted: "
                f"{', '.join(stray[:8])}")
        self.commit_refusal = ""
        if not mine:
            return ""
        mine += story_journals(self.home)       # what it did to a story is in that story's record too
        self.take_lock()
        try:
            git(self.home, "add", "--", *mine)
            message = (f"chore(backlog): {request['kind']} {target_text(request)}\n\nRequest: {request['id']}\n"
                       f"By: {request.get('by', '')}\n")
            # through the commit hook, as a person's backlog commit: it runs what the profile's `checks.backlog:` names
            done = git(self.home, *git_identity(self.home), "commit", "--quiet", "-m", message, "--", *mine)
            if done[0] != 0:
                git(self.home, "reset", "--quiet", "--", *mine)
        finally:
            self.drop_lock()
        if done[0] != 0:
            self.commit_refusal = f"what it wrote could not be committed — {tail(done[1], 1500)}"
            err(f"factory: request {request['id']}: {self.commit_refusal}; it stays in the checkout, unstaged")
            return ""
        return git(self.home, "rev-parse", "--short", "HEAD")[1].strip()

    def work_request(self, request_id, tool):
        """One request worked: its skill run headless with the request as the person's confirmation. Exit 0 when it is
        done (and gone), 3 when its skill asked a person (waiting), 1 when it failed (kept, `error:`)."""
        self.profile()
        try:
            request = find_request(request_id)
        except RequestRefused as error:
            err(f"factory: {error}")
            return 1
        if request["state"] != "queued":
            print(f"factory: request {request_id} is {request['state']} — nothing to do")
            return 0
        kind = KIND[request["kind"]]
        if not kind.skill:
            update_request(request, state="failed", error=f"a {kind.name} request is the runner's, no skill works it")
            return 1
        if request.get("worked"):
            return self.commit_worked(request, kind)
        # what held when it was written may not hold now — an answer given by hand, a story released meanwhile. A
        # request resumed after its own question is past that: what its first run did (an answer written, an
        # acceptance taken) is why its record no longer reads open, so it is not checked again.
        if not request.get("answered"):
            fields = {k: request[k] for k in written_keys(kind) if request.get(k)}
            try:
                wiring.check_request(self.home).execute(CheckRequestCommand(kind.name, fields, request.get("words", "")))
            except (UseCaseException, GateError) as error:
                update_request(request, state="failed", error=f"no longer holds — {error}")
                request_journal("request-end", kind.name, request["id"], "exit=1", "state=failed", str(error))
                err(f"factory: request {request['id']} no longer holds — {error}")
                return 1
        if not request.get("answered"):
            settled = self.settle_request(request, kind)
            if settled is not None:
                return settled
        unit = f"request:{kind.name}"
        unit_tool = self.tool_for(unit, tool)
        if not os.environ.get("FACTORY_TOOL_CMD") and unit_tool not in TOOL:
            update_request(request, state="failed", error=f"no known tool {unit_tool!r} to run it with")
            return 1
        attempts = int(request.get("attempts") or 0) + 1
        update_request(request, state="running", worker=self.worker, started=utc(), attempts=str(attempts), error=None)
        request_journal("request-start", kind.name, request["id"], target_text(request),
                        f"by={request.get('by', '')}", f"tool={unit_tool}", f"attempt={attempts}")
        self.tool_in_flight = unit_tool
        raw = out_path(request["id"])
        os.makedirs(os.path.dirname(raw), exist_ok=True)
        before = self.dirty_files()
        self.allowed_override = self.request_allowed()
        started = time.time()
        self.request_in_flight = request["id"]
        try:
            code = self.invoke(unit_tool, self.request_prompt(request, unit_tool), raw, unit, None)
        except (Stopped, KeyboardInterrupt):
            update_request(request, state="queued", worker=None, started=None, wrote=self.request_wrote(request, before))
            request_journal("request-end", kind.name, request["id"], "exit=stopped", "state=queued")
            raise
        finally:
            self.allowed_override = None
            self.request_in_flight = ""
        measured = self.record_usage(None, unit, unit_tool, raw, int(time.time() - started), request["id"])
        book_request_usage(wiring.book_request_cost(self.home, place("runs")), request["id"], unit_tool, measured)
        prune_outputs()
        if code != 0:
            why = "ran past its time limit" if code == TIMED_OUT else f"ended with exit {code}"
            update_request(request, state="failed", worker=None, wrote=self.request_wrote(request, before),
                           error=f"the tool {why} — its output: {shown(raw)}")
            request_journal("request-end", kind.name, request["id"], f"exit={code}", "state=failed")
            err(f"factory: request {request['id']} — the tool {why}; it stays as failed (`factory.sh requests`).")
            return 1
        asked = [(path, rid) for path, rid, state in request_records(self.home, request["id"])
                 if state in ("open", "draft")]
        if asked:
            commit = self.commit_request(request, before)
            update_request(request, state="waiting", worker=None, record_file=shown(asked[0][0]),
                           wrote=self.request_wrote(request, before) if self.commit_refusal else None)
            request_journal("request-end", kind.name, request["id"], "exit=0", "state=waiting",
                            f"record={asked[0][1]}", f"commit={commit or '-'}")
            print(f"factory: request {request['id']} asks a person — {shown(asked[0][0])}; it runs again once answered.")
            return 3
        for path, _rid, state in request_records(self.home, request["id"]):
            if state == "answered":
                stamp_applied(path, "request")
        if kind.name in ("wish", "stories"):
            mark_questioned(self.home, place("runs"), self.request_wrote(request, before).split(), request["id"])
        # gone before its commit: a crash between the two leaves what it wrote uncommitted — never a request that
        # would run its skill a second time
        with contextlib.suppress(OSError):
            os.remove(request["path"])
        commit = self.commit_request(request, before)
        if self.commit_refusal:
            # its skill did its part; what it wrote waits in the checkout for a person, as the failed request says —
            # and its retry commits it, never running the skill again (`worked:`)
            update_request(request, restore=True, state="failed", worker=None, error=self.commit_refusal,
                           wrote=self.request_wrote(request, before), worked=utc())
            request_journal("request-end", kind.name, request["id"], "exit=0", "state=failed", "commit=refused")
            return 1
        request_journal("request-end", kind.name, request["id"], "exit=0", "state=done", f"commit={commit or '-'}")
        print(f"factory: request {request['id']} done" + (f" — committed {commit}" if commit else " — nothing to commit"))
        return 0

    def settle_request(self, request, kind):
        """A request the factory settles itself (`settle`): written and committed at once, no tool started. None where
        a skill must work it. A request settled on a press (`settle_command`) has no file: nothing to keep or remove."""
        before = self.dirty_files()
        try:
            wrote = wiring.settlement(self.home, place("runs")).settle(request, utc())
        except (UseCaseException, GateError) as error:
            if request.get("path"):
                update_request(request, state="failed", error=f"no longer holds — {error}")
            request_journal("request-end", kind.name, request["id"], "exit=1", "state=failed", str(error))
            err(f"factory: request {request['id']} no longer holds — {error}")
            return 1
        if wrote is None:
            return None
        request_journal("request-start", kind.name, request["id"], target_text(request),
                        f"by={request.get('by', '')}", "tool=factory", "attempt=1")
        if request.get("path"):
            with contextlib.suppress(OSError):
                os.remove(request["path"])
        commit = self.commit_request(request, before)
        self.settled_commit = commit
        if self.commit_refusal:
            if request.get("path"):
                update_request(request, restore=True, state="failed", worker=None, error=self.commit_refusal,
                               wrote=self.request_wrote(request, before), worked=utc())
            request_journal("request-end", kind.name, request["id"], "exit=0", "state=failed", "commit=refused")
            return 1
        request_journal("request-end", kind.name, request["id"], "exit=0", "state=done", "by=factory",
                        f"commit={commit or '-'}")
        print(f"factory: request {request['id']} settled by the factory, no tool" +
              (f" — committed {commit}" if commit else ""))
        return 0

    def commit_worked(self, request, kind):
        """A request whose skill did its part and whose commit was refused, queued again: what it wrote is committed —
        the skill is not run again, and what it wrote is not checked as a new request (an answer it wrote reads as
        answered by now). Refused again, it stays failed with the reason."""
        commit = self.commit_request(request, self.dirty_files())
        if self.commit_refusal or not commit:
            why = self.commit_refusal or "nothing it wrote is left in the checkout to commit"
            update_request(request, state="failed", worker=None, error=why)
            request_journal("request-end", kind.name, request["id"], "exit=1", "state=failed", "commit=refused")
            err(f"factory: request {request['id']}: {why}")
            return 1
        with contextlib.suppress(OSError):
            os.remove(request["path"])
        request_journal("request-end", kind.name, request["id"], "exit=0", "state=done", f"commit={commit}")
        print(f"factory: request {request['id']} done — committed {commit}")
        return 0

    # --- the backlog -------------------------------------------------------------------------------------------
    def parallel_slots(self):
        """How many stories run at once: --parallel, else FACTORY_PARALLEL, else the profile's `parallel:`, else 1."""
        given = self.parallel or os.environ.get("FACTORY_PARALLEL") or first_word(self.profile().get("parallel", "")) or "1"
        if not given.isdigit() or int(given) == 0:
            err(f"factory: parallel takes a whole number of stories, 1 or more — not '{given}'")
            return None
        return int(given)

    def skip(self, story, code):
        """--keep-going: a story that stopped is set aside for the rest of this run — the schedule skips it and what
        depends on it — unless the stop concerns the whole run: the checkout taken over (5), the run's --max-stages
        (4 with the cap reached), a configuration nothing could run with (2). True when the run goes on."""
        if not self.keep_going or code in (2, 5) or (code == 4 and self.max_stages and self.invocations >= self.max_stages):
            return False
        self.skipped[story] = code
        err(f"factory: story {story} stopped (exit {code}) — --keep-going skips it and what depends on it; the "
            f"backlog run goes on.")
        return True

    def skip_args(self):
        return ("--skip", ",".join(self.skipped)) if self.skipped else ()

    def skipped_summary(self):
        """The run's exit once nothing more can start: 0, or the first stop's code where --keep-going skipped one."""
        if not self.skipped:
            return 0
        err("factory: stopped in this run and skipped: "
            + ", ".join(f"{story} (exit {code})" for story, code in self.skipped.items())
            + " — `factory.sh status` says why.")
        return next(iter(self.skipped.values()))

    def nothing_more(self, out, watch):
        print(out)
        print("factory: nothing more can run" + (", and nothing waits on an answer that would change that" if watch else "")
              + ".")

    def waiting_note(self, out, previous, interval):
        """Waiting is reading files, never asking an agent: an unchanged schedule is said once."""
        if out != previous:
            print(out)
            what = "an answer" if "\nwait: yes" in "\n" + out else "a released story or a request"
            print(f"factory: waiting for {what} — the schedule is read again every {interval}s; {self.stop_file} "
                  "ends the watch.")
        return out

    def run_backlog(self, tool, watch, interval, dry):
        """Story after story, in the order the schedule names, read off the files every time. A failure ends it."""
        if not self.gate_installed():
            err(f"factory: no gate at {self.gate_rel} — run 'factory.sh setup'")
            return 2
        slots = self.parallel_slots()
        if slots is None:
            return 2
        # a superseded story's worktree has nothing to integrate; it goes before the first story starts
        if not dry:
            self.take_lock()
            try:
                self.run([sys.executable, self.cli_path, "--worktree-prune"])
            finally:
                self.drop_lock()
        if not dry:
            self.requeue_orphans()
        if slots > 1 and not dry:
            return self.run_parallel(tool, watch, interval, slots)
        previous, last = "", ""
        while True:
            # waiting is working too: the claim is renewed on every look
            if not dry and not self.renew():
                err("factory: another worker took over this checkout — the backlog run ends here.")
                return 5
            if os.path.isfile(self.stop_file):
                print(f"factory: {self.stop_file} exists — the backlog run stops here. Remove it to run again.")
                return 0
            # a person's requests go before the next story: a stop, what a skill works, a story to run now
            if not dry:
                if self.take_stop_request():
                    return 0
                self.work_requests(tool)
                asked = self.take_run_request()
                if asked:
                    request, start = asked
                    print(f"══ story {request['story']} from {start}  (request {request['id']})")
                    code = self.run_story(request["story"], tool, start, False)
                    request_journal("request-end", "run", request["id"], f"exit={code}")
                    if code in (0, 3) or self.skip(request["story"], code):
                        last = ""
                        continue
                    err(f"factory: story {request['story']} stopped (exit {code}) — the backlog run ends here.")
                    return code
            if claim_config_here(self.home) and not dry:
                _c, claimed = self.cli("--claims-refresh", quiet=False)
                if claimed and claimed != getattr(self, "last_claims", ""):
                    print(claimed)
                self.last_claims = claimed
            code, out = self.cli("--schedule", "--slots", "1", *self.skip_args(), merge=True)
            if code != 0:
                err(out)
                err("factory: the schedule could not be read.")
                return 1
            following = next((line[len("next: "):] for line in out.split("\n") if line.startswith("next: ")), "")
            if following and not following.startswith("none"):
                story, start = following.split(" ", 1)[0], following.split(" ", 1)[-1]
                if following == last:
                    print(out)
                    err(f"factory: {story} ran from {start} and the schedule names it there again — no progress, stopping.")
                    if self.skip(story, 1):
                        last = ""
                        continue
                    return 1
                print(f"══ story {story} from {start}")
                if dry:
                    print(out)
                    print(f"   would run: factory.sh run --story {story} --from {start}")
                    return 0
                code = self.run_story(story, tool, start, False)
                if code == 0:
                    last = following
                    continue
                if code == 3:                       # waits for a decision; the schedule skips it now
                    last = ""
                    continue
                if self.skip(story, code):
                    last = ""
                    continue
                err(f"factory: story {story} stopped (exit {code}) — the backlog run ends here.")
                return code
            if not watch or not (self.stay or any(line.startswith("wait: yes") for line in out.split("\n"))):
                self.nothing_more(out, watch)
                return self.skipped_summary()
            previous = self.waiting_note(out, previous, interval)
            last = ""
            self.wait_or_wake(interval)

    def run_parallel(self, tool, watch, interval, slots):
        """Several stories at once, each in its worktree, each a runner process of its own whose lines carry its id.
        A failure starts nothing more and lets the running ones finish; so does the stop file and a TERM."""
        children, seen, failed, stopping, previous, out = {}, set(), 0, None, "", ""
        asked, ran_for = {}, {}             # a request's process by its id; a `run` request by the story it runs
        while True:
            if stopping is None and self.pending is not None:
                stopping, failed = self.pending, failed or self.pending
                self.pending = None
                err("factory: stopped by a signal — no further story starts; the running ones finish.")
            if stopping is None and not self.renew():
                err("factory: another worker took over this checkout — no further story starts.")
                stopping, failed = 5, 5
            if stopping is None and os.path.isfile(self.stop_file):
                print(f"factory: {self.stop_file} exists — no further story starts; the running ones finish.")
                stopping = "stop"
            if stopping is None and self.take_stop_request():
                stopping = "stop"
            for request_id, (process, request, pump) in list(asked.items()):
                if process.poll() is None:
                    continue
                pump.join()
                del asked[request_id]
                self.request_ended(request, process.returncode)
            for story, (process, start, pump) in list(children.items()):
                if process.poll() is None:
                    continue
                pump.join()
                del children[story]
                code = process.returncode
                if story in ran_for:
                    request_journal("request-end", "run", ran_for.pop(story), f"exit={code}")
                if code == 0:
                    seen.add(f"{story}@{start}")
                elif code != 3 and self.skip(story, code):
                    pass
                elif code != 3:
                    err(f"factory: story {story} stopped (exit {code}) — no further story starts; the running ones finish.")
                    stopping = stopping if stopping is not None else code
                    failed = failed or code
            launched = False
            if stopping is None:
                # a person's request takes the next free slot, before any story; one about a running story waits.
                # One at a time: requests work in the main checkout, and two at once would commit each other's files
                busy = set(children) | {s for _p, r, _t in asked.values() for s in stories_of(r)}
                while len(children) + len(asked) < slots and not asked:
                    request = self.next_request(busy)
                    if request is None or request["id"] in asked:
                        break
                    asked[request["id"]] = self.start_request_child(request, tool)
                    busy |= stories_of(request)
                    launched = True
                while len(children) + len(asked) < slots:
                    taken = self.take_run_request(busy)
                    if not taken:
                        break
                    request, start = taken
                    print(f"══ story {request['story']} from {start}  (request {request['id']}, slots: {slots})")
                    os.makedirs(f"{self.home}/{self.evidence_rel()}/{request['story']}", exist_ok=True)
                    children[request["story"]] = self.start_child(request["story"], tool, start)
                    ran_for[request["story"]] = request["id"]
                    busy.add(request["story"])
                    launched = True
                loose = sum(1 for _p, r, _t in asked.values() if not stories_of(r))
                code, out = self.cli("--schedule", "--slots", str(max(0, slots - loose)), "--busy", ",".join(sorted(busy)),
                                     *self.skip_args(), merge=True)
                if code != 0:
                    err(out)
                    err("factory: the schedule could not be read.")
                    stopping, failed = 1, 1
                else:
                    for following in [line[len("next: "):] for line in out.split("\n") if line.startswith("next: ")]:
                        if following.startswith("none") or len(children) + len(asked) >= slots:
                            continue
                        story, start = following.split(" ", 1)[0], following.split(" ", 1)[-1]
                        if f"{story}@{start}" in seen:
                            err(f"factory: {story} ran from {start} and the schedule names it there again — no "
                                "progress, not started again.")
                            if self.skip(story, 1):
                                continue
                            failed = failed or 1
                            stopping = stopping if stopping is not None else 1
                            continue
                        print(f"══ story {story} from {start}  (slots: {slots})")
                        os.makedirs(f"{self.home}/{self.evidence_rel()}/{story}", exist_ok=True)
                        children[story] = self.start_child(story, tool, start)
                        launched = True
            if not children and not asked and not launched:
                if stopping is not None:
                    return failed if isinstance(stopping, int) or failed else 0
                if not watch or not (self.stay or any(line.startswith("wait: yes") for line in out.split("\n"))):
                    self.nothing_more(out, watch)
                    return failed or self.skipped_summary()
                previous = self.waiting_note(out, previous, interval)
                self.wait_or_wake(interval)
                continue
            time.sleep(2)

    def start_request_child(self, request, tool):
        """A request's process beside the stories of a parallel run, its lines named with the request's id."""
        print(f"══ request {request['id']}  ({request['kind']} {target_text(request)}, by {request.get('by', '?')})")
        flush()
        process = subprocess.Popen(self.request_argv(request, tool), cwd=self.home, env=self.request_env(),
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def pump():
            for line in iter(process.stdout.readline, b""):
                sys.stdout.write(f"[request {request['id']}] "
                                 f"{line.decode('utf-8', errors='replace').rstrip(chr(13) + chr(10))}\n")
                sys.stdout.flush()
        thread = threading.Thread(target=pump, daemon=True)
        thread.start()
        return process, request, thread

    def start_child(self, story, tool, start):
        """One story's run as a runner process of its own — the same worker on the claim, the run's pipeline hash —
        its lines named with the story's id."""
        options = self.options
        argv = [sys.executable, self.cli_path, "--run", "--child", "--story", story, "--from", start, "--tool", tool,
                "--builder", options.builder, "--verifier", options.verifier]
        argv += ["--max-stages", str(options.max_stages)] if options.max_stages else []
        argv += ["--story-budget", str(options.story_budget)] if options.story_budget else []
        env = dict(os.environ, FACTORY_RUNNER_WORKER=self.worker, FACTORY_RUNNER_PIPELINE_SHA=self.pipeline_sha)
        flush()
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)

        def pump():
            for line in iter(process.stdout.readline, b""):
                sys.stdout.write(f"[{story}] {line.decode('utf-8', errors='replace').rstrip(chr(13) + chr(10))}\n")
                sys.stdout.flush()
        thread = threading.Thread(target=pump, daemon=True)
        thread.start()
        return process, start, thread


TOOL_SKILL_DIRS = tuple(tool.skills for tool in TOOLS)


# --- what the runner reads from the project's files ----------------------------------------
# One reader for the profile, a stage file and a decision record: the gate's. The runner calls these in its
# own process; the cli prints the same answers for a person or a stage.

COMMAND_KEYS = ("compile", "test", "e2eTest", "architecture", "format", "formatFix")


def command_heads(profile):
    """The first word of every command the profile declares, once each, in the profile's order."""
    heads = []
    for key, value in profile.items():
        if key in COMMAND_KEYS or key.startswith("test."):
            head = first_word(value)
            if head and not head.startswith("{{") and head not in heads:
                heads.append(head)
    return heads


def model_for(profile, tool, stage):
    return first_word(profile.get(f"model.{tool}.{stage}") or profile.get(f"model.{tool}") or "")


def verdict_of_story(runs, story_id):
    path = os.path.join(runs, story_id, "judge.md")
    return verdict_in(read_text(path)) if os.path.isfile(path) else ""


def needs_human_lines(path, story_id=None):
    """`<id>\\t<stage>\\t<record path>` for every decision the file's needs-human section names; None when it
    asks nobody. The record lives beside the story, so the story's id says where to look."""
    ids = needs_human_ids(read_text(path)) if os.path.isfile(path) else None
    if ids is None:
        return None
    lines = []
    for decision_id in ids:
        record, stage = "", ""
        try:
            record = record_path(story_id, decision_id) if story_id else ""
        except GateError:
            record = ""
        if record and os.path.isfile(record):
            try:
                stage = str(read_front_matter(record)[0].get("stage", "") or "")
            except GateError:
                stage = ""
        lines.append(f"{decision_id}\t{stage or '-'}\t{shown(record) if record else '-'}")
    return lines


def open_decision_files(cwd, story_id):
    """The records beside the story that carry no `## Answer` yet — the cheap check a run makes
    before a stage; the gate does the fine reading (a draft without a name is still open)."""
    try:
        store = decisions_store(find_story(place("epics"), story_id))
    except GateError:
        return []
    if not os.path.isdir(store):
        return []
    found = []
    for name in sorted(os.listdir(store)):
        if not name.endswith(".md"):
            continue
        text = read_text(os.path.join(store, name))
        if not re.search(r"^## Answer", text, re.M):
            found.append(shown(os.path.join(store, name)))
    return found




# --- the run's start ---------------------------------------------------------------------------------------------
STAMP = ".agents/factory/gate.installed"
#: The files the install puts into .agents/factory/, in the stamp's order; a name ending in `/` is the package.
PIPELINE_FILES = ("story-gate.py", "factory-cli.py", "observe.py", "factory.sh", "dca_factory/")


def package_modules(folder):
    """Every module of the package under <folder>, its subpackages' too, by its path below the folder with `/` —
    in the order the install's hash lists them (the C locale's, as Python sorts)."""
    found = []
    for top, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        below = os.path.relpath(top, folder).replace(os.sep, "/")
        found += [name if below == "." else f"{below}/{name}" for name in files if name.endswith(".py")]
    return sorted(found)


def file_sha(path):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return ""


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def field_of(text, key):
    return next((line[len(key) + 2:] for line in text.split("\n") if line.startswith(f"{key}: ")), "")


def flush():
    sys.stdout.flush()
    sys.stderr.flush()


def err(text):
    sys.stdout.flush()
    print(text, file=sys.stderr, flush=True)


def stop_group(process, first=None):
    """A tool and what it started, stopped: <first> (TERM by default), then KILL after five seconds."""
    if os.name == "nt":
        process.kill()
        process.wait()
        return
    for sig, grace in ((first or signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        with contextlib.suppress(OSError):
            os.killpg(process.pid, sig)
        try:
            process.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            continue


def spawnable(argv):
    """On Windows a tool found on the PATH may be a script or a `.cmd`, which no process starts by itself."""
    if os.name != "nt":
        return argv
    found = shutil.which(argv[0]) or argv[0]
    if found.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", found, *argv[1:]]
    if not found.lower().endswith((".exe", ".com")):
        return ["sh", found, *argv[1:]]
    return [found, *argv[1:]]


def run_options(argv):
    parser = argparse.ArgumentParser(prog="factory.sh run", description="the runner, started by `factory.sh run`")
    parser.add_argument("--story")
    parser.add_argument("--tool", default="")
    parser.add_argument("--from", dest="start", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--stay", action="store_true",
                        help="with --watch: keep waiting when nothing waits on an answer — for a person's requests")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--max-stages", type=int, default=0)
    parser.add_argument("--story-budget", type=int, default=0)
    parser.add_argument("--builder", choices=("shared", "separate"), default="shared")
    parser.add_argument("--verifier", choices=("shared", "separate"), default="shared")
    parser.add_argument("--parallel", default="")
    parser.add_argument("--child", action="store_true", help="one story of a parallel run, under its parent's claim")
    parser.add_argument("--keep-going", action="store_true",
                        help="a stopped story is skipped with what depends on it; the backlog run ends when nothing can start")
    return parser.parse_args(argv)


def run_main(argv):
    """`factory.sh run` once its checks passed: the claim, the pipeline's hash, the story or the backlog, and the
    claim and the lock given back however the run ends."""
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(line_buffering=True)
    options = run_options(argv)
    cwd = os.getcwd()
    home = os.environ.get("FACTORY_HOME") or os.path.realpath(cwd)
    set_places(read_profile(resolve_profile(os.environ.get("FACTORY_PROFILE") or None, cwd)))
    run = Run(options, home, place("runs"), worker=os.environ.get("FACTORY_RUNNER_WORKER") if options.child else None)

    def stop(signum, _frame):
        name = signal.Signals(signum).name
        err("factory: stopped by a hang-up — after the running stage, nothing more starts" if name == "SIGHUP" else
            "factory: stopped by a signal — after the running stage, nothing more starts")
        run.pending = SIGNAL_EXITS[name]
        if run.sleeping:
            run.pending = None
            raise Stopped(SIGNAL_EXITS[name])
    for name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), stop)
    try:
        code = run_start(run, options)
        run.checkpoint()
        return code
    except Stopped as stopped:
        return stopped.code
    except KeyboardInterrupt:
        err("factory: interrupted — the claim and the lock are given back; the stage's files stay as they are.")
        return SIGNAL_EXITS["SIGINT"]
    finally:
        run.drop_lock()
        if not options.child:
            run.release()


def request_main(argv):
    """`factory-cli.py --work-request <id> [--tool <tool>]`: one request worked, as the runner starts it — under the
    runner's claim (FACTORY_RUNNER_WORKER), or, started alone, under a claim of its own."""
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(prog="factory-cli.py --work-request")
    parser.add_argument("request")
    parser.add_argument("--tool", default="")
    given = parser.parse_args(argv)
    cwd = os.getcwd()
    set_places(read_profile(resolve_profile(os.environ.get("FACTORY_PROFILE") or None, cwd)))
    worker = os.environ.get("FACTORY_RUNNER_WORKER")
    run = Run(run_options(["--tool", given.tool]), os.path.realpath(cwd), place("runs"), worker=worker)
    tool = given.tool or first_word(run.profile().get("tool", "")) or "stand-in"
    if not worker:
        code = tools_ready(run, tool) or run.take_checkout()
        if code:
            return code
    try:
        return run.work_request(given.request, tool)
    except Stopped as stopped:
        return stopped.code
    except KeyboardInterrupt:
        return SIGNAL_EXITS["SIGINT"]
    finally:
        if not worker:
            run.release()


def settle_command(cwd, kind_name, fields, words, by):
    """`factory.sh request <kind> … --settle`: the request settled at once where the factory can (`settle`), no file
    written and no tool started — a press in a session's view takes the same shortcut a page's request takes.
    Exit 0 settled (and committed), 3 where a skill must work it (nothing written), 2 refused, 1 failed. The settle
    and its commit hold the checkout's commit lock, as the factory's own requests do, whether a factory is up or not."""
    set_places(read_profile(resolve_profile(os.environ.get("FACTORY_PROFILE") or None, cwd)))
    checked = wiring.check_request(cwd).execute(CheckRequestCommand(kind_name, fields, words, against_waiting=True))
    fields, words = checked.fields, checked.words
    run = Run(run_options([]), os.path.realpath(cwd), place("runs"), worker=os.environ.get("FACTORY_RUNNER_WORKER"))
    request = dict(fields, id=f"{utc('%Y%m%dT%H%M%S')}-{kind_name}", kind=kind_name, words=words,
                   by=" ".join((by or default_by(cwd)).split()), path=None)
    code = run.settle_request(request, KIND[kind_name])
    return (3 if code is None else code), request["id"], run.settled_commit


def tools_ready(run, tool):
    """Before the first stage: every tool the run may start is a known record whose binary is on the PATH — a run
    that could not start a later unit's tool starts nothing. A `tool.<stage>` for a stage a shared process carries
    is named: the unit is the process (`tool.builder`, `tool.verifier`), never a silent split."""
    if os.environ.get("FACTORY_TOOL_CMD") or tool == "stand-in":
        return 0
    missing = [t for t in run.tools_of_run(tool) if t not in TOOL or not shutil.which(TOOL[t].command[0])]
    if missing:
        err(f"factory: the run would start {', '.join(missing)}, which "
            + ("is" if len(missing) == 1 else "are") + " no known tool or not on the PATH (tool / tool.<unit> in the "
            "profile) — nothing started")
        return 2
    shared = {stage for stages in SHARED_WINDOWS.values() for stage in stages}
    for key in sorted(run.profile()):
        if key.startswith("tool.") and key[5:] in shared:
            print(f"factory: note — `{key}` names a stage a shared process carries; the unit is the process "
                  f"(`tool.builder` / `tool.verifier`), with `stages: separate` each stage is one")
    return 0


def run_start(run, options):
    tool = options.tool
    if not options.dry_run and not options.child:
        code = tools_ready(run, tool or "stand-in")
        if code:
            return code
    if options.child:
        run.gate_first = False
        return run.run_story(options.story, tool or "stand-in", options.start, False)
    if options.story:
        story, start = options.story, options.start
        if not start:
            # No stage named: the story starts where its files say, as the backlog run would start it.
            code, answer = run.cli("--story", story, "--start", "--slots", "1", quiet=False)
            if code != 0:
                return code
            state, start, detail = field_of(answer, "state"), field_of(answer, "start"), field_of(answer, "detail")
            if start in ("none", ""):
                if state == "delivered":
                    print(f"factory: story {story} is delivered" + (f" ({detail})" if detail else "") + " — nothing runs.")
                    return 0
                if state == "waiting":
                    err(f"factory: story {story} waits for {detail} — answer it with /factory-decisions.")
                    return 3
                if state == "running":
                    err(f"factory: story {story} is running ({detail}) — one run at a time.")
                    return 5
                err(f"factory: story {story} is {state}" + (f" — {detail}" if detail else "") + ".")
                err(f"factory:   nothing runs; name the stage to run it anyway: factory.sh run --story {story} --from <stage>")
                return 1
            print(f"factory: story {story} starts at {start}" + (f" — {detail}" if detail else ""))
        else:
            names = [s.name for s in STAGES if s.in_order] + [s.name for s in STAGES if not s.in_order]
            if start not in names:
                err(f"factory: --from {start} names no stage ({' '.join(names)}) — nothing ran, the rounds are as they were")
                return 2
            if not options.dry_run:
                run.reset_rounds(story, start)
        run.gate_first = True
        if not options.dry_run:
            code = run.take_checkout() or run.guard_pipeline_start()
            if code:
                return code
            if options.start:
                run.fresh_window(story)
        return run.run_story(story, tool or "stand-in", start, options.dry_run)
    if not options.dry_run:
        code = run.take_checkout() or run.guard_pipeline_start()
        if code:
            return code
    return run.run_backlog(tool or "stand-in", options.watch, max(1, min(3600, options.interval)), options.dry_run)
