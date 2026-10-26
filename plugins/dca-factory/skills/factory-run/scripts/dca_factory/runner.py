"""The runner: the run of `factory.sh run` and of the requests it works — its stage arrays, and what the use cases
of a run ask of the process around them.

The shell tables the runner reads once at its start; then the ports of the run's use cases on this process: a
story's stages (`RunnerStages` for `RunStoryUseCase`), its integration (`RunnerIntegration` for
`IntegrateStoryUseCase`), the backlog (`RunnerBacklog` for `RunBacklogUseCase`), a request's skill
(`RunnerRequestSkill`). A story's worktree steps, the layout migrations, the stage files' skeletons, the tool's and
the gate's processes are adapters of their own.
"""

import contextlib
import glob
import hashlib
import os
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
from .delivery.adapter.outgoing.pipeline.stage_rows import ALL_KINDS, SHARED_WINDOWS, STAGE, STAGE_FILES, STAGE_ORDER, STAGES
from .sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .sharedkernel.adapter.outgoing.profile.profile_files import (
    place, PROFILE_FILE, read_profile,
    resolve_profile, set_places, shown)
from .delivery.adapter.outgoing.files.decision_record_files import (
    decisions_store, needs_human_ids, record_path)
from .delivery.adapter.outgoing.files.story_layout import (
    find_story, is_delivered, story_kind)
from .sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .delivery.adapter.outgoing.tools.streams import tokens_of
from .infrastructure.schedule import start_of
from .delivery.adapter.outgoing.claims.remote_claims import claim_config_here
from .delivery.adapter.outgoing.claims.checkout_claim import claim
from .delivery.adapter.outgoing.files.windows import freeze_all
from .delivery.adapter.outgoing.files.usage_files import journal_usage
from .delivery.adapter.outgoing.files.run_marks import (
    back_in, run_stories, STAGE_WORD, step_open, verdict_in)
from .delivery.adapter.outgoing.git.worktrees import has_worktree
from .delivery.adapter.outgoing.files.journal_files import journal_writer
from .delivery.adapter.outgoing.files.kept_files import stale_red_proof
from .delivery.adapter.outgoing.build.commands import run as run_command
from .delivery.adapter.outgoing.git.integration import (
    integration_target, lost_text, main_tests_lost)
from .delivery.adapter.outgoing.files.delivery_files import perspectives_of
from .delivery.adapter.outgoing.tools.agents import TOOL, TOOLS, tools_shell
from .delivery.adapter.outgoing.process.gate_process import file_sha, GateProcess, hashing
from .delivery.adapter.outgoing.tools.tool_choice import first_word, ToolChoice
from .delivery.adapter.outgoing.tools.tool_processes import (
    err, exit_field, flush, Stopped, TIMED_OUT, ToolProcesses, utc)
from .delivery.adapter.incoming.runner.usage import book_request_usage
from .delivery.application.requests.work_request import WorkRequestCommand
from .delivery.adapter.outgoing.files.request_files import out_path, prune_outputs, stamp_utc
from .delivery.adapter.outgoing.files.decision_record_files import project_record_path
from .delivery.application.shared.request_skill import SkillRun
from .infrastructure import requests as request_wiring
from .delivery.adapter.outgoing.process.console_lines import ConsoleLines
from .delivery.application.backlog.run_backlog import RunBacklogCommand, RunBacklogUseCase
from .delivery.application.shared.backlog_schedule import ScheduleRead
from .delivery.application.delivery.run_story import RunStoryCommand, RunStoryUseCase
from .delivery.application.delivery.integrate_story import IntegrateStoryCommand, IntegrateStoryUseCase
from .delivery.domain.model.stage import StageName, StoryKind, Window
from .delivery.domain.model.story_state import GateReport, Rounds, VerdictWord
from .delivery.adapter.outgoing.files.decision_record_files import request_records
from .delivery.adapter.outgoing.files.request_files import (
    default_by, REQUEST_JOURNAL, requests_dir)
from .delivery.application.requests.list_requests import target_text
from .delivery.application.shared.requests import KIND
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
# Its entry points — the arguments, the signals, the exit codes — are the incoming adapter
# `delivery/adapter/incoming/runner/run_command.py`; the composition root `infrastructure/runner.py` builds the run.

#: The cli flags a skill run for a request may call (WP-91): what the dialog skills read and record with — never one
#: that starts a run, a request, the factory or its page (`--run`, `--work-request`, `--request`, `--up`, `--serve`).
REQUEST_CLI_FLAGS = ("--contract", "--free-id", "--window-start", "--window-end", "--list-decisions", "--spec-delta",
                     "--spec-check", "--findings", "--reopen", "--owned-confirm", "--status", "--discover-list",
                     "--help-view", "--journal-line")
STAGE_SHELL = ("cd, ls, cat, head, tail, wc, sort, grep, diff, pwd, and git status, git diff, git log, git ls-files, "
               "git apply --check, and git rm (a file the plan removes)")


def newer(path, than):
    """`[ path -nt than ]`: path exists and is newer, or than does not exist."""
    if not os.path.exists(path):
        return False
    return not os.path.exists(than) or os.path.getmtime(path) > os.path.getmtime(than)


class RunnerRequestSkill:
    """A request's skill as the runner starts it: the prompt that names the skill, the request's arguments, the rules
    for a skill run for a request and where things are; the shell narrowed to what the dialog skills read and record
    with; the tool's process, its usage journaled and booked to the request."""

    def __init__(self, run):
        self._run = run

    def tool_for(self, unit, given):
        return self._run.tools.tool_for(unit, given)

    @staticmethod
    def known(tool):
        return bool(os.environ.get("FACTORY_TOOL_CMD")) or tool in TOOL

    def run(self, request, kind, unit, tool):
        run = self._run
        run.tool_in_flight = tool
        raw = out_path(request["id"])
        os.makedirs(os.path.dirname(raw), exist_ok=True)
        run.tools.allowed_override = self.request_allowed()
        started = time.time()
        run.request_in_flight = request["id"]
        try:
            code = run.invoke(tool, self.request_prompt(request, tool), raw, unit, None)
        finally:
            run.tools.allowed_override = None
            run.request_in_flight = ""
        measured = run.processes.record_usage(None, unit, tool, raw, int(time.time() - started), request["id"])
        book_request_usage(wiring.book_request_cost(run.home, place("runs")), request["id"], tool, measured)
        prune_outputs()
        return SkillRun(code, code == TIMED_OUT, shown(raw))

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
        reference = next((f"{d}/factory-run/reference/requests.md" for d in self._run.skill_dirs(tool)
                          if os.path.isfile(f"{d}/factory-run/reference/requests.md")), "")
        if not reference:
            own = os.path.abspath(os.path.join(self._run.scripts, "..", "reference", "requests.md"))
            reference = own[len(self._run.pwd) + 1:] if own.startswith(self._run.pwd + "/") else own
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
            records = [shown(path) for path, rid, _s in request_records(self._run.home, request["id"])]
            lines.append(f"This request ran before and asked; its question is answered now ({answered}: "
                         f"{', '.join(records)}). Read the answer and go on from there — write nothing the answer and "
                         f"the request do not settle.")
        story = (request.get("story") or "").split()
        lines.append(self._run.where_things_are(tool, story[0] if len(story) == 1 else None)
                     + " For a request, also `bash .agents/factory/factory.sh` backlog, status, decisions, discover, "
                     "spec-delta and help.")
        return "\n\n".join(lines)

    def request_allowed(self):
        """A request's shell: a stage's, with the cli narrowed to the flags the dialog skills read and record with, and
        the runner's reading verbs — no flag and no verb that starts a run, a request, the factory or its page."""
        cli = f"Bash({self._run.py} .agents/factory/factory-cli.py:*)"
        heads = [head for head in self._run.tools.allowed_commands().split(",") if head != cli]
        heads += [f"Bash({self._run.py} .agents/factory/factory-cli.py {flag}:*)" for flag in REQUEST_CLI_FLAGS]
        heads += [f"Bash(bash .agents/factory/factory.sh {verb}:*)"
                  for verb in ("backlog", "status", "decisions", "discover", "spec-delta", "help")]
        heads.append("Bash(date:*)")                # the backlog skill dates what it writes
        return ",".join(heads)


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
        self.gate_first = False
        self.max_stages = options.max_stages
        self.story_budget = options.story_budget
        self.shared_builder = options.builder == "shared"
        self.shared_verifier = options.verifier == "shared"
        self.parallel = options.parallel
        self.keep_going = getattr(options, "keep_going", False)
        self.stay = getattr(options, "stay", False)
        self.red_stale = {}                   # story → its tests whose red proof a merge left stale
        self.options = options
        self.add_dirs, self.read_dirs = [], []
        self.tool_in_flight = ""
        self.request_in_flight = ""         # the request whose process runs: a window it opens is its to measure
        self.pipeline_sha = os.environ.get("FACTORY_RUNNER_PIPELINE_SHA", "")
        self.claimed = False
        self.lock_held = False
        self.sleeping = False
        self.pending = None
        self.tools = ToolChoice(self.profile, self.py, self.gate_rel)
        self.timeout = self.tools.stage_timeout(self.gate_installed())
        self.processes = ToolProcesses(self, self.tools)
        self.gates = GateProcess(self)

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

    # --- the pipeline, unchanged ---------------------------------------------------------------------------
    def pipeline_hash(self, folder=None):
        """One SHA-256 over the installed files' digests — the stamp's `sha256:` line."""
        if not hashing():
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
    def protected_dirs(self):
        dirs = [".agents/factory", self.evidence_rel(), *TOOL_SKILL_DIRS, ".agents/skills"]
        return [d if os.path.isabs(d) or re.match(r"^[A-Za-z]:", d) else f"{self.home}/{d}" for d in dirs]

    def invoke(self, tool, prompt, raw, stage, story, count=True):
        """One stage's tool process (`ToolProcesses.invoke`), counted against `--max-stages` where `count`."""
        if count:
            self.invocations += 1
        return self.processes.invoke(tool, prompt, raw, stage, story)

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

    def bump_rounds(self, story):
        path = f"{self.evidence(story)}/.rounds"
        count = int("".join(c for c in read_text(path) if c.isdigit()) or 0) if os.path.isfile(path) else 0
        count += 1
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"{count}\n")
        return count

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
    def owned_invoke(self, story, window, call):
        """The tool of an owned window. Stopped inside it — an interrupt, a signal that ends the tool — the window is
        closed before the run ends: its end journaled, the person's parts compared and the digest gone, so a person
        may change the story before the next run."""
        try:
            return call()
        except (Stopped, KeyboardInterrupt):
            self.journal_line(story, f"{utc()}\tstage-end\t{window}\texit=stopped")
            self.gates.owned("end", window, story, 1)
            raise

    def gate(self, stage, story, gate_path=None):
        """The gate of <stage> over <story> (`GateProcess.gate`), never under a pipeline that changed under the run."""
        gate_path = gate_path or self.gate_path
        if not os.path.isfile(gate_path):
            err(f"factory: no gate at {gate_path} — run 'factory.sh setup'")
            return 2
        os.makedirs(f"{self.runs}/{story}", exist_ok=True)
        os.makedirs(self.evidence(story), exist_ok=True)
        if self.guard_pipeline(stage, story):
            raise Stopped(7)
        return self.gates.gate(stage, story, gate_path)

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
        self.gates.record("--record-base", story)
        self.gates.snapshot(story, f"before-{window}")
        self.gates.owned("start", window, story)
        tool = self.tools.tool_for(window, tool)
        self.journal_line(story, f"{utc()}\tstage-start\t{window}\ttool={tool}{self.tools.effort_field(tool, window)}"
                                 f"\tstages={','.join(stages)}")
        began = time.time()
        invoked = self.owned_invoke(story, window, lambda: self.invoke(tool, prompt, raw, window, story))
        self.processes.record_usage(story, window, tool, raw, int(time.time() - began))
        self.journal_line(story, f"{utc()}\tstage-end\t{window}\texit={exit_field(invoked)}")
        # What the window changed is recorded however it ended: a file a stage made before the tool failed or a signal
        # stopped it is the story's all the same, and only `stages-made.txt` takes an untracked file into its commit.
        self.gates.snapshot(story, f"after-{window}")
        self.gates.record("--record-changes", story, window)
        # The window closes before a signal that arrived ends the run: the person may change the story before the next.
        if self.gates.owned("end", window, story, invoked) != 0:
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

    def builder_window(self, story, tool, stages, start, dry):
        """Plan to tidy in one tool process, so each stage builds on what the one before read; the process runs each
        stage's gate itself. The tool's exit, 0 in a dry run."""
        tool = self.tools.tool_for("builder", tool)
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
            self.processes.dry_lines(tool, prompt, "builder")
            return 0
        refused = self.may_dispatch(story, "the shared stages")
        if refused == "budget":
            return self.budget_note(story, "the shared stages")
        if refused == "stages":
            err(f"factory: --max-stages {self.max_stages} reached before the shared stages of {story}.")
            return 4
        if refused:
            return refused
        return self.window(story, tool, "builder", stages, prompt)

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
                    f"{self.where_things_are(self.tools.tool_for(f'review:{name}', tool), story)}")
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
        used = {name: self.tools.tool_for(f"review:{name}", tool) for name in names}
        for name in names:
            self.journal_line(story, f"{utc()}\tstage-start\treview:{name}\ttool={used[name]}"
                                     f"{self.tools.effort_field(used[name], f'review:{name}')}")
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
            self.processes.record_usage(story, f"review:{name}", used[name], raws[name], seconds)
            self.journal_line(story, f"{utc()}\tstage-end\treview:{name}\texit={exit_field(codes.get(name, 1))}")
            if not os.path.isfile(f"{folder}/{name}.md"):
                err(f"factory: the {name} reviewer left no {folder}/{name}.md — the judge runs that pass itself and says so.")
        self.checkpoint()
        return 0

    def verifier_window(self, story, tool, stages, dry):
        """Judge and document in one tool process — never one process with the builder: the judge's independence
        from the builder is the point of the split. The tool's exit, 0 in a dry run."""
        tool = self.tools.tool_for("verifier", tool)
        document = (f" The skeleton: `{self.py} {self.cli_rel()} --document-skeleton {story}`; the document gate: "
                    f"`{self.py} {self.gate_rel} --story {story} --stage document --brief`.") if "document" in stages else ""
        prompt = (f"Carry out these stages of the delivery pipeline for backlog story {story}, one after another, in "
                  f"this one session: {', '.join(f'stage-{s}' for s in stages)}.{document} "
                  f"{self.where_things_are(tool, story)}")
        print(f"── stage {'+'.join(stages)}  (tool: {tool}, one shared context)")
        if dry:
            self.processes.dry_lines(tool, prompt, "verifier")
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
        return self.window(story, tool, "verifier", stages, prompt)

    # --- a story's stages ----------------------------------------------------------------------------------------
    def run_stages(self, story, tool, start=None, dry=False):
        """The story's stages from <start> on, in the checkout it is called in (`RunStoryUseCase`)."""
        shared = frozenset(window for window, on in ((Window.BUILDER, self.shared_builder),
                                                     (Window.VERIFIER, self.shared_verifier)) if on)
        gate_first, self.gate_first = self.gate_first, False
        use_case = RunStoryUseCase(RunnerStages(self, tool), ConsoleLines())
        return use_case.execute(RunStoryCommand(story, start, dry, gate_first, shared))

    def red_proof_stale(self, story, start):
        """A story whose red proof went stale goes to its test stage: a gate that holds the red proof (build, tidy)
        refuses a test changed after it was seen failing, and only the test stage can record it again — as a step of
        the runner, never as a stage's question and never as a round. A merge of the main line into the story's
        branch is what changes a test that way (the resumed story's merge, the integrate stage's resolution, the
        integration a gate refused afterwards); the test stage records the tests as they now are, a break where the
        code already meets them. True when it went stale."""
        self.profile()
        moved = stale_red_proof(os.getcwd(), place("runs"), story, start)
        if not moved:
            self.red_stale.pop(story, None)
            return False
        self.red_stale[story] = moved
        self.journal_line(story, f"{utc()}\tred-stale\ttest\tfrom={start}\ttests={len(moved)}")
        print(f"factory: {', '.join(moved)} changed after the test stage saw it fail — the red proof is about the "
              f"earlier version, so the story goes to its test stage to record it on the files as they are, then "
              f"'{start}' runs again.")
        return True

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

    def run_one(self, story, tool, stage):
        """One stage in a process of its own; 0 when it ran and its file stands, else the run's exit code."""
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
        self.gates.record("--record-base", story)
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
        self.gates.snapshot(story, f"before-{stage}")
        tool = self.tools.tool_for(stage, tool)
        flags, note = self.tools.model_choice(tool, stage)
        requested = self.tools.model_key(tool, stage)
        model_fields = (f"\tmodel_requested={requested}" if requested else "") + \
            (f"\tmodel_applied=no ({note})" if note else "")
        if note:
            print(f"factory: model.{tool}.{stage}: {requested} — {note}")
        self.gates.owned("start", stage, story)
        self.journal_line(story, f"{stage_started}\tstage-start\t{stage}\ttool={tool}{model_fields}"
                                 f"{self.tools.effort_field(tool, stage)}")
        raw = f"{evidence}/{stage}.{utc('%H%M%S')}.out"
        began = time.time()
        invoked = self.owned_invoke(story, stage, lambda: self.invoke(tool, self.prompt_for(stage, story), raw, stage, story))
        self.processes.record_usage(story, stage, tool, raw, int(time.time() - began))
        # recorded however the stage ended, as a shared window's: the files it made reach the story's commit
        self.gates.snapshot(story, f"after-{stage}")
        self.gates.record("--record-changes", story, stage)
        if self.gates.owned("end", stage, story, invoked) != 0:
            self.journal_line(story, f"{utc()}\tstage-end\t{stage}\texit=owned")
            return 7
        if invoked != 0:
            self.journal_line(story, f"{utc()}\tstage-end\t{stage}\texit={exit_field(invoked)}")
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
        return 0

    # --- a story in its worktree (WP-92) -------------------------------------------------------------------------
    def in_home(self, *args, merge=True):
        """A cli call made in the main checkout, as a person's would be there: (exit code, its lines)."""
        return self.cli(*args, merge=merge, quiet=False, cwd=os.environ.get("FACTORY_HOME") or self.home,
                        env=self.home_env())

    def link_worktree(self, story):
        self.run([sys.executable, self.cli_path, "--worktree-link", story], cwd=os.environ.get("FACTORY_HOME") or self.home,
                 env=self.home_env())

    def integration(self, tool):
        """The story's integration into the main line (`IntegrateStoryUseCase`), from the worktree it runs in."""
        return IntegrateStoryUseCase(RunnerIntegration(self, tool), ConsoleLines())

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
        self.gates.owned("start", "integrate", story)
        tool = self.tools.tool_for("integrate", tool)
        self.journal_line(story, f"{utc()}\tstage-start\tintegrate\ttool={tool}")
        code = self.owned_invoke(story, "integrate", lambda: self.invoke(
            tool, self.integrate_prompt(story, conflicts, lost), raw, "integrate", story))
        self.processes.record_usage(story, "integrate", tool, raw, int(time.time() - began))
        self.journal_line(story, f"{utc()}\tstage-end\tintegrate\texit={exit_field(code)}")
        if self.gates.owned("end", "integrate", story, code) != 0:
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
            code = self.integration(tool).resolve(story, out) if "\nconflict: " in "\n" + out else None
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
    def queue(self):
        """The requests as this runner works them (`RequestQueue`), read where the profile puts them."""
        return request_wiring.request_queue(self.home, self.worker, self.profile)

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
            request = self.queue().next(busy)
            if request is None or request["id"] in worked:
                return
            worked.add(request["id"])
            print(f"══ request {request['id']}  ({request['kind']} {target_text(request)}, by {request.get('by', '?')})")
            code, _ = self.run(self.request_argv(request, tool), cwd=self.home, env=self.request_env())
            self.queue().ended(request, code)

    def between_stages(self, story, tool):
        """Before a stage of a story the runner runs alone: a `stop` — the run ends here, as after a TERM, the story
        resumable —, then the requests that are not about it."""
        if self.options.child:
            return
        if self.queue().take_stop():
            self.pending = 0
            self.checkpoint()
        self.work_requests(tool, busy=(story,))
        self.profile()

    def wait_or_wake(self, interval):
        """The watch's pause, cut short by a request: a person's press runs within seconds, not after the interval."""
        end = time.time() + interval
        while time.time() < end:
            self.sleep(min(2, max(0.1, end - time.time())))
            if os.path.isfile(self.stop_file):
                return
            with contextlib.suppress(OSError):
                if self.queue().any_queued():
                    return

    # --- one request, in its own process ----------------------------------------------------------------------
    def request_use_case(self):
        """The use case that works one request, over the main checkout, under this runner's lock."""
        return request_wiring.work_request(self.home, self.runs_rel, self.profile, self.locked, RunnerRequestSkill(self))

    @contextlib.contextmanager
    def locked(self):
        self.take_lock()
        try:
            yield
        finally:
            self.drop_lock()

    def work_request(self, request_id, tool):
        """One request worked (`WorkRequestUseCase`): what it said and its exit — 0 when it is done (and gone), 3 when
        its skill asked a person (waiting), 1 when it failed (kept, `error:`)."""
        self.profile()
        return self.request_use_case().execute(WorkRequestCommand(request_id, tool, self.worker))

    def press(self, kind_name, fields, words, by):
        """A press as the request it would write: its fields, an id of now, the person who pressed."""
        return dict(fields, id=f"{utc('%Y%m%dT%H%M%S')}-{kind_name}", kind=kind_name, words=words,
                    by=" ".join((by or default_by(self.home)).split()), path=None)

    def default_tool(self):
        return first_word(self.profile().get("tool", "")) or "stand-in"

    def tools_ready(self, tool):
        """Before the first stage: every tool the run may start is a known record whose binary is on the PATH — a run
        that could not start a later unit's tool starts nothing. A `tool.<stage>` for a stage a shared process carries
        is named: the unit is the process (`tool.builder`, `tool.verifier`), never a silent split."""
        if os.environ.get("FACTORY_TOOL_CMD") or tool == "stand-in":
            return 0
        missing = [t for t in self.tools.tools_of_run(tool) if t not in TOOL or not shutil.which(TOOL[t].command[0])]
        if missing:
            err(f"factory: the run would start {', '.join(missing)}, which "
                + ("is" if len(missing) == 1 else "are") + " no known tool or not on the PATH (tool / tool.<unit> in "
                "the profile) — nothing started")
            return 2
        shared = {stage for stages in SHARED_WINDOWS.values() for stage in stages}
        for key in sorted(self.profile()):
            if key.startswith("tool.") and key[5:] in shared:
                print(f"factory: note — `{key}` names a stage a shared process carries; the unit is the process "
                      f"(`tool.builder` / `tool.verifier`), with `stages: separate` each stage is one")
        return 0

    # --- the backlog -------------------------------------------------------------------------------------------
    def parallel_slots(self):
        """How many stories run at once: --parallel, else FACTORY_PARALLEL, else the profile's `parallel:`, else 1."""
        given = self.parallel or os.environ.get("FACTORY_PARALLEL") or first_word(self.profile().get("parallel", "")) or "1"
        if not given.isdigit() or int(given) == 0:
            err(f"factory: parallel takes a whole number of stories, 1 or more — not '{given}'")
            return None
        return int(given)

    def run_backlog(self, tool, watch, interval, dry):
        """Story after story, in the order the schedule names, read off the files every time (`RunBacklogUseCase`)."""
        if not self.gate_installed():
            err(f"factory: no gate at {self.gate_rel} — run 'factory.sh setup'")
            return 2
        slots = self.parallel_slots()
        if slots is None:
            return 2
        backlog = RunnerBacklog(self, tool)
        use_case = RunBacklogUseCase(backlog, backlog, backlog, self.queue(), ConsoleLines())
        return use_case.execute(RunBacklogCommand(slots, watch, interval, dry, self.keep_going, self.stay))

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
        return ChildProcess(process, thread)

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
        return ChildProcess(process, thread)


class RunnerStages:
    """A story's stages on the runner (`StoryStages`): its files read with the package's readers, in the checkout or
    the worktree it runs in, its gates and its processes as the runner starts them."""

    def __init__(self, run, tool):
        self._run = run
        self._tool = tool

    def open_decisions(self, story):
        return self._run.open_decisions(story).split()

    def kind(self, story):
        return StoryKind(self._run.kind_of(story))

    def red_stale(self, story, start):
        return self._run.red_proof_stale(story, start.value)

    def pause(self, story):
        self._run.between_stages(story, self._tool)

    def gate(self, stage, story):
        return self._run.gate(stage, story)

    def quiet_gate(self, stage, story):
        return self._run.quiet_gate(stage, story)

    def report(self, story, stage):
        path = f"{self._run.runs}/{story}/.gate-{stage}.txt"
        return GateReport(read_text(path) if os.path.isfile(path) else "")

    def artefact(self, story, stage):
        return self._run.artefact(story, stage)

    def holds(self, story, stage):
        return os.path.isfile(self._run.artefact(story, stage))

    def refused_before(self, story, stage):
        return os.path.isfile(f"{self._run.runs}/{story}/.gate-{stage}.txt")

    def delivered(self, story):
        return self._run.delivered(story)

    def asks_human(self, story, stage):
        return self._run.asks_human(self._run.artefact(story, stage))

    def stopped_for_human(self, story, stage):
        return self._run.stopped_for_human(self._run.artefact(story, stage), stage, story)

    def stage(self, story, stage):
        self._announce(stage)
        return self._run.run_one(story, self._tool, stage)

    def dry(self, story, stage):
        tool = self._announce(stage)
        self._run.processes.dry_lines(tool, self._run.prompt_for(stage, story), stage)

    def _announce(self, stage):
        tool = self._run.tools.tool_for(stage, self._tool)      # the run's tool stays: every stage resolves its own
        print(f"── stage {stage}  (tool: {tool}, fresh context)")
        self._run.tool_in_flight = tool
        return tool

    def builder(self, story, stages, start, dry):
        return self._run.builder_window(story, self._tool, stages, start, dry)

    def reviews(self, story, kind, dry):
        return self._run.run_reviews(story, self._tool, dry, kind.value)

    def verifier(self, story, stages, dry):
        return self._run.verifier_window(story, self._tool, stages, dry)

    def sent_back(self, story):
        return self._run.back_to(story, "build") == "test"

    def repaired(self, story):
        return newer(f"{self._run.runs}/{story}/tidy.md", f"{self._run.runs}/{story}/build.md")

    def red_proof(self, story):
        ledger = self.red_ledger(story)
        return os.path.isfile(ledger) and os.path.getsize(ledger) > 0

    def red_ledger(self, story):
        return f"{self._run.evidence(story)}/.tests-red"

    def bump(self, story):
        return Rounds(self._run.bump_rounds(story))

    def resumes(self, story):
        start = self._run.start_stage(story)
        return StageName(start) if start and start != "none" else None

    def verdict(self, story):
        return VerdictWord(self._run.verdict_of(story) or "")

    def back(self, story):
        back = self._run.back_to(story)
        return StageName(back) if back else None

    def in_worktree(self):
        return bool(os.environ.get("FACTORY_HOME"))

    def integrate(self, story, dry):
        return self._run.integration(self._tool).execute(IntegrateStoryCommand(story, dry))


class RunnerIntegration:
    """A story's integration on the runner (`StoryIntegration`): from the story's worktree into the main checkout,
    the cli's integrate steps run there, the integrate stage and the gate as the runner starts them."""

    def __init__(self, run, tool):
        self._run = run
        self._tool = tool

    def lock(self):
        self._run.take_lock()

    def unlock(self):
        self._run.drop_lock()

    def step(self, story, work):
        with self._run.step(story, "integrate"):
            return work()

    def prepare(self, story):
        return self._run.in_home("--integrate-prepare", story)

    def session(self, story, conflicts, lost):
        return self._run.integrate_stage(story, self._tool, conflicts, list(lost) or None)

    def lost(self, story):
        return main_tests_lost(self._run.pwd, self._run.runs, story)

    def lost_text(self, lost):
        return lost_text(lost)

    def gate(self, story):
        home = os.environ.get("FACTORY_HOME") or self._run.home
        return self._run.gate("integrate", story, gate_path=f"{home}/{self._run.gate_rel}")

    def report(self, story):
        path = self.report_place(story)
        return GateReport(read_text(path) if os.path.isfile(path) else "")

    def report_place(self, story):
        return f"{self._run.runs}/{story}/.gate-integrate.txt"

    def published(self):
        return bool(claim_config_here(self._run.home))

    def worktree(self):
        return self._run.pwd

    def relink(self, story):
        self._run.take_lock()
        try:
            self._run.link_worktree(story)
        finally:
            self._run.drop_lock()
        self._run.journal_line(story, f"{utc()}\toutdated\tdocument.md\tby=integrate")

    def bump(self, story):
        return Rounds(self._run.bump_rounds(story))


class ChildProcess:
    """A story's or a request's process beside a parallel run, its lines pumped to the runner's."""

    def __init__(self, process, pump):
        self.process = process
        self.pump = pump

    def ended(self):
        if self.process.poll() is None:
            return None
        self.pump.join()
        return self.process.returncode


class RunnerBacklog:
    """The backlog run's ports on the runner (`BacklogSchedule`, `BacklogCheckout`, `BacklogWorker`): the schedule
    the cli prints, the checkout under the claim, the stories and requests as processes."""

    def __init__(self, run, tool):
        self._run = run
        self._tool = tool

    def read(self, slots, busy, skip):
        args = ["--schedule", "--slots", str(slots), "--busy", ",".join(busy)]
        args += ["--skip", ",".join(skip)] if skip else []
        code, out = self._run.cli(*args, merge=True)
        if code != 0:
            return ScheduleRead(False, out)
        lines = out.split("\n")
        named = [line[len("next: "):] for line in lines if line.startswith("next: ")]
        following = tuple((text.split(" ", 1)[0], text.split(" ", 1)[-1]) for text in named if not text.startswith("none"))
        return ScheduleRead(True, out, following, any(line.startswith("wait: yes") for line in lines))

    def prune(self):
        with self._run.locked():
            self._run.run([sys.executable, self._run.cli_path, "--worktree-prune"])

    def renew(self):
        return self._run.renew()

    def stop_asked(self):
        return self._run.stop_file if os.path.isfile(self._run.stop_file) else None

    def stop_place(self):
        return self._run.stop_file

    def claims(self):
        if not claim_config_here(self._run.home):
            return ""
        return self._run.cli("--claims-refresh", quiet=False)[1]

    def signalled(self):
        code, self._run.pending = self._run.pending, None
        return code

    def wait(self, interval):
        self._run.wait_or_wake(interval)

    def pause(self):
        time.sleep(2)

    def run(self, story, start):
        return self._run.run_story(story, self._tool, start, False)

    def fresh(self, story, start):
        self._run.reset_rounds(story, start)
        self._run.gates.fresh_window(story)

    def start(self, story, start):
        os.makedirs(f"{self._run.home}/{self._run.evidence_rel()}/{story}", exist_ok=True)
        return self._run.start_child(story, self._tool, start)

    def work(self, busy):
        self._run.work_requests(self._tool, busy)

    def start_request(self, request):
        return self._run.start_request_child(request, self._tool)

    def capped(self):
        return bool(self._run.max_stages and self._run.invocations >= self._run.max_stages)


TOOL_SKILL_DIRS = tuple(tool.skills for tool in TOOLS)


# --- what the runner reads from the project's files ----------------------------------------
# One reader for the profile, a stage file and a decision record: the gate's. The runner calls these in its
# own process; the cli prints the same answers for a person or a stage.

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


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def field_of(text, key):
    return next((line[len(key) + 2:] for line in text.split("\n") if line.startswith(f"{key}: ")), "")
